#!/usr/bin/env python3
"""Export compact generated context bundles for LLM sessions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from memorylib import MemoryDocument, extract_summary, repo_relative_path, repo_root, validate_memories
from secret_scan import scan_paths


DEFAULT_OUTPUT_DIR = Path("distilled")


def export_context(root: Path, output_dir: Path | None = None) -> list[Path]:
    output_dir = output_dir or root / DEFAULT_OUTPUT_DIR
    documents, errors = validate_memories(root)
    if errors:
        raise RuntimeError("memory validation failed:\n" + "\n".join(errors))

    targets = [repo_relative_path(document.path, root) for document in documents]
    findings = scan_paths(root, targets)
    if findings:
        formatted = "\n".join(
            f"{finding.path}:{finding.line}: {finding.kind}: {finding.redacted_line}"
            for finding in findings
        )
        raise RuntimeError(f"secret scan failed before context export:\n{formatted}")

    output_dir.mkdir(parents=True, exist_ok=True)

    durable = active_documents(documents, "durable")
    active = [
        document
        for document in documents
        if document.frontmatter["type"] in {"active", "project", "tool"}
        and document.frontmatter["status"] in {"active", "proposed", "stale"}
        and safe_for_context(document)
    ]
    recent = sorted(
        [document for document in documents if safe_for_context(document)],
        key=lambda document: document.frontmatter["updated_at"],
        reverse=True,
    )[:20]

    outputs = {
        "durable.md": render_bundle("Durable Memory", durable, root),
        "active-context.md": render_bundle("Active Context", active, root),
        "recent-summary.md": render_bundle("Recent Summary", recent, root),
    }

    written: list[Path] = []
    for name, content in outputs.items():
        path = output_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def active_documents(documents: list[MemoryDocument], memory_type: str) -> list[MemoryDocument]:
    return [
        document
        for document in documents
        if document.frontmatter["type"] == memory_type
        and document.frontmatter["status"] == "active"
        and safe_for_context(document)
    ]


def safe_for_context(document: MemoryDocument) -> bool:
    return document.frontmatter["sensitivity"] in {"public", "internal"}


def render_bundle(title: str, documents: list[MemoryDocument], root: Path) -> str:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        f"# {title}",
        "",
        f"Generated at: {generated_at}",
        "",
        "This file is generated from canonical Markdown memory. Do not edit it directly.",
        "",
    ]
    if not documents:
        lines.append("_No matching memories._")
        lines.append("")
        return "\n".join(lines)

    for document in documents:
        data = document.frontmatter
        relpath = repo_relative_path(document.path, root)
        project = data.get("project") or "none"
        tags = ", ".join(data.get("tags", [])) or "none"
        lines.extend(
            [
                f"## {data['title']}",
                "",
                f"- id: `{data['id']}`",
                f"- path: `{relpath}`",
                f"- type/status: `{data['type']}` / `{data['status']}`",
                f"- project: `{project}`",
                f"- confidence: `{float(data['confidence']):.2f}`",
                f"- tags: {tags}",
                "",
                extract_summary(document.content) or "_No summary available._",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--output-dir", default=None, help="Output directory.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    output_dir = Path(args.output_dir) if args.output_dir else root / DEFAULT_OUTPUT_DIR
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    try:
        written = export_context(root, output_dir)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for path in written:
        print(f"Wrote {repo_relative_path(path, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
