#!/usr/bin/env python3
"""Build a lightweight relationship graph from canonical memory files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

from index_memory import default_db_path
from memorylib import extract_summary, load_memories, repo_relative_path, repo_root


SAFE_GRAPH_SENSITIVITIES = {"public", "internal"}
MEMORY_ID_RE = re.compile(r"\bmem_[a-z0-9_/-]+\b")


@dataclass(frozen=True)
class GraphMemory:
    id: str
    title: str
    path: str
    memory_type: str
    status: str
    scope: str
    project: str | None
    tags: list[str]
    sensitivity: str
    confidence: float
    summary: str
    updated_at: str
    content: str


def node(node_id: str, label: str, kind: str, **properties: Any) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "kind": kind,
        "properties": {key: value for key, value in properties.items() if value is not None},
    }


def edge(source: str, target: str, relation: str) -> dict[str, str]:
    return {"source": source, "target": target, "relation": relation}


def stable_id(kind: str, value: str) -> str:
    clean = value.strip().lower().replace(" ", "-")
    return f"{kind}:{clean}"


def build_graph(root: Path, include_sensitive: bool = False, prefer_index: bool = True) -> dict[str, Any]:
    """Return nodes and edges for memories, tags, projects, types, and references."""
    memories = load_graph_memories(root, include_sensitive=include_sensitive, prefer_index=prefer_index)
    return graph_from_memories(memories)


def load_graph_memories(root: Path, include_sensitive: bool = False, prefer_index: bool = True) -> list[GraphMemory]:
    if prefer_index:
        db_path = default_db_path(root)
        if db_path.exists():
            return load_graph_memories_from_index(db_path, include_sensitive=include_sensitive)
    return load_graph_memories_from_markdown(root, include_sensitive=include_sensitive)


def load_graph_memories_from_index(db_path: Path, include_sensitive: bool = False) -> list[GraphMemory]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, path, title, type, status, scope, project, tags, updated_at,
                   confidence, sensitivity, summary, raw_content
            FROM memories
            ORDER BY path
            """
        ).fetchall()
    finally:
        conn.close()

    memories: list[GraphMemory] = []
    for row in rows:
        if row["sensitivity"] == "secret-prohibited":
            continue
        if not include_sensitive and row["sensitivity"] not in SAFE_GRAPH_SENSITIVITIES:
            continue
        memories.append(
            GraphMemory(
                id=str(row["id"]),
                title=str(row["title"]),
                path=str(row["path"]),
                memory_type=str(row["type"]),
                status=str(row["status"]),
                scope=str(row["scope"]),
                project=str(row["project"]) if row["project"] else None,
                tags=split_tags(row["tags"]),
                sensitivity=str(row["sensitivity"]),
                confidence=float(row["confidence"]),
                summary=str(row["summary"] or ""),
                updated_at=str(row["updated_at"]),
                content=str(row["raw_content"] or ""),
            )
        )
    return memories


def load_graph_memories_from_markdown(root: Path, include_sensitive: bool = False) -> list[GraphMemory]:
    memories: list[GraphMemory] = []
    for document in load_memories(root):
        data = document.frontmatter
        if data.get("sensitivity") == "secret-prohibited":
            continue
        if not include_sensitive and data.get("sensitivity") not in SAFE_GRAPH_SENSITIVITIES:
            continue
        memories.append(
            GraphMemory(
                id=str(data["id"]),
                title=str(data["title"]),
                path=repo_relative_path(document.path, root),
                memory_type=str(data["type"]),
                status=str(data["status"]),
                scope=str(data["scope"]),
                project=str(data["project"]) if data.get("project") else None,
                tags=[str(tag) for tag in data.get("tags", [])],
                sensitivity=str(data["sensitivity"]),
                confidence=float(data["confidence"]),
                summary=extract_summary(document.content, 180),
                updated_at=str(data["updated_at"]),
                content=document.content,
            )
        )
    return memories


def split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [tag for tag in str(value).split() if tag]


def graph_from_memories(memories: list[GraphMemory]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, str]] = {}
    memory_ids = {memory.id for memory in memories}

    for memory in memories:
        memory_id = memory.id
        nodes[memory_id] = node(
            memory_id,
            memory.title,
            "memory",
            path=memory.path,
            type=memory.memory_type,
            status=memory.status,
            scope=memory.scope,
            sensitivity=memory.sensitivity,
            confidence=memory.confidence,
            summary=memory.summary,
            updated_at=memory.updated_at,
        )

        type_id = stable_id("type", memory.memory_type)
        nodes.setdefault(type_id, node(type_id, memory.memory_type, "type"))
        add_edge(edges, memory_id, type_id, "has_type")

        scope_id = stable_id("scope", memory.scope)
        nodes.setdefault(scope_id, node(scope_id, memory.scope, "scope"))
        add_edge(edges, memory_id, scope_id, "has_scope")

        if memory.project:
            project_id = stable_id("project", memory.project)
            nodes.setdefault(project_id, node(project_id, memory.project, "project"))
            add_edge(edges, memory_id, project_id, "belongs_to_project")

        for tag in memory.tags:
            tag_id = stable_id("tag", tag)
            nodes.setdefault(tag_id, node(tag_id, tag, "tag"))
            add_edge(edges, memory_id, tag_id, "tagged")

        referenced = set(MEMORY_ID_RE.findall(memory.content))
        for referenced_id in sorted(referenced & memory_ids):
            if referenced_id != memory_id:
                add_edge(edges, memory_id, referenced_id, "references")

    return {
        "nodes": sorted(nodes.values(), key=lambda item: (item["kind"], item["id"])),
        "edges": sorted(edges.values(), key=lambda item: (item["source"], item["relation"], item["target"])),
    }


def add_edge(edges: dict[tuple[str, str, str], dict[str, str]], source: str, target: str, relation: str) -> None:
    edges[(source, target, relation)] = edge(source, target, relation)


def graph_summary(graph: dict[str, Any]) -> dict[str, int]:
    kinds: dict[str, int] = {}
    for graph_node in graph["nodes"]:
        kind = str(graph_node["kind"])
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        **{f"{kind}_nodes": count for kind, count in sorted(kinds.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--include-sensitive", action="store_true", help="Include private/sensitive memories.")
    parser.add_argument("--json", action="store_true", help="Emit full graph JSON.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    graph = build_graph(root, include_sensitive=args.include_sensitive)
    if args.json:
        print(json.dumps(graph, indent=2))
    else:
        summary = graph_summary(graph)
        print(
            f"Memory graph: {summary['nodes']} node(s), {summary['edges']} edge(s), "
            f"{summary.get('memory_nodes', 0)} memory node(s)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
