#!/usr/bin/env python3
"""Build a lightweight relationship graph from canonical memory files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

from index_memory import default_db_path
from memorylib import (
    MemoryError as MemoryToolError,
    content_hash,
    discover_memory_files,
    extract_summary,
    is_memory_file,
    load_memory,
    logical_relative_path,
    path_is_link_like,
    read_bounded_text,
    repo_relative_path,
    repo_root,
    validate_document,
)
from secret_scan import scan_text
from resource_limits import (
    GRAPH_DEFAULT_LIMIT,
    GRAPH_MAX_EDGES,
    GRAPH_MAX_INDEX_ROWS_SCANNED,
    GRAPH_MAX_LIMIT,
    GRAPH_MAX_NODES,
    GRAPH_MAX_OFFSET,
)


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


def build_graph(
    root: Path,
    include_sensitive: bool = False,
    prefer_index: bool = True,
    public_only: bool = False,
    limit: int = GRAPH_DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    """Return nodes and edges for memories, tags, projects, types, and references."""
    if public_only and include_sensitive:
        raise ValueError("public-only graph cannot include sensitive memory")
    if not 1 <= limit <= GRAPH_MAX_LIMIT:
        raise ValueError(f"graph limit must be between 1 and {GRAPH_MAX_LIMIT}")
    if not 0 <= offset <= GRAPH_MAX_OFFSET:
        raise ValueError(f"graph offset must be between 0 and {GRAPH_MAX_OFFSET}")
    memories = load_graph_memories(
        root,
        include_sensitive=include_sensitive,
        prefer_index=prefer_index,
        public_only=public_only,
        max_results=offset + limit + 1,
    )
    page_memories = memories[offset : offset + limit]
    graph = graph_from_memories(page_memories)
    has_more = len(memories) > offset + limit
    graph["page"] = {
        "offset": offset,
        "limit": limit,
        "returned_memories": len(page_memories),
        "has_more": has_more,
        "next_offset": offset + len(page_memories) if has_more else None,
    }
    return graph


def load_graph_memories(
    root: Path,
    include_sensitive: bool = False,
    prefer_index: bool = True,
    public_only: bool = False,
    max_results: int = GRAPH_DEFAULT_LIMIT + 1,
) -> list[GraphMemory]:
    if prefer_index:
        db_path = default_db_path(root)
        if db_path.exists():
            return load_graph_memories_from_index(
                root,
                db_path,
                include_sensitive=include_sensitive,
                public_only=public_only,
                max_results=max_results,
            )
    return load_graph_memories_from_markdown(
        root,
        include_sensitive=include_sensitive,
        public_only=public_only,
        max_results=max_results,
    )


def load_graph_memories_from_index(
    root: Path,
    db_path: Path,
    include_sensitive: bool = False,
    public_only: bool = False,
    max_results: int = GRAPH_DEFAULT_LIMIT + 1,
) -> list[GraphMemory]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    memories: list[GraphMemory] = []
    try:
        rows = conn.execute(
            """
            SELECT id, path, content_hash
            FROM memories
            ORDER BY path
            """
        )
        rows_scanned = 0
        for row in rows:
            rows_scanned += 1
            if rows_scanned > GRAPH_MAX_INDEX_ROWS_SCANNED:
                raise ValueError(
                    "graph index scan exceeded the "
                    f"{GRAPH_MAX_INDEX_ROWS_SCANNED} row limit"
                )
            memory = canonical_graph_memory(root, row)
            if memory is None:
                continue
            if public_only and memory.sensitivity != "public":
                continue
            if not include_sensitive and memory.sensitivity not in SAFE_GRAPH_SENSITIVITIES:
                continue
            memories.append(memory)
            if len(memories) >= max_results:
                break
    finally:
        conn.close()
    return memories


def load_graph_memories_from_markdown(
    root: Path,
    include_sensitive: bool = False,
    public_only: bool = False,
    max_results: int = GRAPH_DEFAULT_LIMIT + 1,
) -> list[GraphMemory]:
    memories: list[GraphMemory] = []
    for path in discover_memory_files(root):
        document = load_memory(path)
        if validate_document(document):
            continue
        assert_graph_document_safe(root, document.path)
        data = document.frontmatter
        if data.get("sensitivity") == "secret-prohibited":
            continue
        if public_only and data.get("sensitivity") != "public":
            continue
        if not include_sensitive and data.get("sensitivity") not in SAFE_GRAPH_SENSITIVITIES:
            continue
        memories.append(graph_memory_from_document(root, document))
        if len(memories) >= max_results:
            break
    return memories


def assert_graph_document_safe(root: Path, path: Path) -> None:
    relative = logical_relative_path(path, root)
    current = root
    for part in relative.parts:
        current = current / part
        if path_is_link_like(current):
            raise ValueError(f"graph memory path must not contain symlinks or junctions: {relative}")
    document = load_memory(path)
    text = read_bounded_text(path)
    if scan_text(text, relative.as_posix()):
        raise ValueError(f"graph memory rejected by secret scan: {relative.as_posix()}")


def graph_memory_from_document(root: Path, document: Any) -> GraphMemory:
    data = document.frontmatter
    return GraphMemory(
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


def canonical_graph_memory(root: Path, row: sqlite3.Row) -> GraphMemory | None:
    indexed_path = str(row["path"]).replace("\\", "/")
    try:
        candidate = Path(os.path.abspath(root / indexed_path))
        if not candidate.is_file() or not is_memory_file(candidate, root):
            return None
        assert_graph_document_safe(root, candidate)
        document = load_memory(candidate)
    except (MemoryToolError, OSError, UnicodeError, ValueError):
        return None
    if validate_document(document):
        return None
    data = document.frontmatter
    if repo_relative_path(candidate, root) != indexed_path:
        return None
    if data.get("id") != row["id"]:
        return None
    if content_hash(data, document.content) != row["content_hash"]:
        return None
    return graph_memory_from_document(root, document)


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
        add_node(
            nodes,
            node(
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
            ),
        )

        type_id = stable_id("type", memory.memory_type)
        add_node(nodes, node(type_id, memory.memory_type, "type"))
        add_edge(edges, memory_id, type_id, "has_type")

        scope_id = stable_id("scope", memory.scope)
        add_node(nodes, node(scope_id, memory.scope, "scope"))
        add_edge(edges, memory_id, scope_id, "has_scope")

        if memory.project:
            project_id = stable_id("project", memory.project)
            add_node(nodes, node(project_id, memory.project, "project"))
            add_edge(edges, memory_id, project_id, "belongs_to_project")

        for tag in memory.tags:
            tag_id = stable_id("tag", tag)
            add_node(nodes, node(tag_id, tag, "tag"))
            add_edge(edges, memory_id, tag_id, "tagged")

        referenced = set(MEMORY_ID_RE.findall(memory.content))
        for referenced_id in sorted(referenced & memory_ids):
            if referenced_id != memory_id:
                add_edge(edges, memory_id, referenced_id, "references")

    return {
        "nodes": sorted(nodes.values(), key=lambda item: (item["kind"], item["id"])),
        "edges": sorted(edges.values(), key=lambda item: (item["source"], item["relation"], item["target"])),
    }


def add_node(nodes: dict[str, dict[str, Any]], graph_node: dict[str, Any]) -> None:
    node_id = str(graph_node["id"])
    if node_id not in nodes and len(nodes) >= GRAPH_MAX_NODES:
        raise ValueError(f"graph exceeded the {GRAPH_MAX_NODES} node limit")
    nodes.setdefault(node_id, graph_node)


def add_edge(edges: dict[tuple[str, str, str], dict[str, str]], source: str, target: str, relation: str) -> None:
    if (source, target, relation) not in edges and len(edges) >= GRAPH_MAX_EDGES:
        raise ValueError(f"graph exceeded the {GRAPH_MAX_EDGES} edge limit")
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
    parser.add_argument("--public-only", action="store_true", help="Return only revalidated public memories.")
    parser.add_argument("--limit", type=int, default=GRAPH_DEFAULT_LIMIT, help="Maximum memories in one graph page.")
    parser.add_argument("--offset", type=int, default=0, help="Memory offset for graph pagination.")
    parser.add_argument("--json", action="store_true", help="Emit full graph JSON.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    graph = build_graph(
        root,
        include_sensitive=args.include_sensitive,
        public_only=args.public_only,
        limit=args.limit,
        offset=args.offset,
    )
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
