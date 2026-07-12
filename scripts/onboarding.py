#!/usr/bin/env python3
"""Preview or apply the minimum reviewed ai-dememory baseline."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from memorylib import repo_root, slugify
from secret_scan import scan_text


BASELINE_KINDS = ("values", "preferences", "recommendations")
ALLOWED_SENSITIVITY = {"public", "internal"}
DEFAULT_CLIENTS = ["codex", "claude"]


def onboarding_plan(root: Path, answers: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free onboarding plan."""
    root = Path(root).resolve()
    normalized = normalize_answers(answers)
    documents = render_documents(normalized)
    writes: list[dict[str, Any]] = []
    for relative_path, content in documents.items():
        target = safe_target(root, relative_path)
        writes.append(planned_write(root, target, content, kind="memory", allow_update=False))

    config_path = safe_target(root, ".ai-dememory.toml")
    current_config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    updated_config = merge_onboarding_config(current_config, normalized)
    writes.append(planned_write(root, config_path, updated_config, kind="config", allow_update=True))

    conflicts = [item["path"] for item in writes if item["status"] == "conflict"]
    plan = {
        "root": str(root),
        "reviewed_by": normalized["reviewed_by"],
        "clients": normalized["clients"],
        "recall": normalized["recall"],
        "learning": normalized["learning"],
        "writes": writes,
        "created_count": sum(item["status"] == "create" for item in writes),
        "updated_count": sum(item["status"] == "update" for item in writes),
        "unchanged_count": sum(item["status"] == "unchanged" for item in writes),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "can_apply": not conflicts,
        "mutates_system": False,
        "writes_files": False,
        "durable_memory_reviewed": True,
        "auto_promotes": False,
    }
    plan["plan_sha256"] = plan_fingerprint(plan)
    return plan


def apply_onboarding(root: Path, answers: dict[str, Any], expected_plan_sha256: str | None = None) -> dict[str, Any]:
    """Apply exactly one reviewed onboarding plan, refusing memory overwrites."""
    root = Path(root).resolve()
    plan = onboarding_plan(root, answers)
    if not expected_plan_sha256:
        raise ValueError("--expect-plan-sha256 is required; preview and review the onboarding plan first")
    if not hmac.compare_digest(expected_plan_sha256, str(plan["plan_sha256"])):
        raise ValueError("onboarding plan changed after preview; review the new plan before apply")
    if plan["conflicts"]:
        raise ValueError("onboarding conflicts must be reviewed before apply: " + ", ".join(plan["conflicts"]))

    normalized = normalize_answers(answers)
    documents = render_documents(normalized)
    payloads: dict[str, str] = dict(documents)
    config_path = safe_target(root, ".ai-dememory.toml")
    current_config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    payloads[".ai-dememory.toml"] = merge_onboarding_config(current_config, normalized)

    changed: list[str] = []
    batch: list[tuple[Path, str, bool]] = []
    for item in plan["writes"]:
        if item["status"] == "unchanged":
            continue
        relative_path = str(item["path"])
        target = safe_target(root, relative_path)
        batch.append((target, payloads[relative_path], item["kind"] == "config"))
        changed.append(relative_path)
    atomic_batch_write(batch)

    applied = dict(plan)
    applied.update(
        {
            "applied": True,
            "changed": changed,
            "mutates_system": bool(changed),
            "writes_files": bool(changed),
        }
    )
    return applied


def plan_fingerprint(plan: dict[str, Any]) -> str:
    canonical = {
        "root": plan["root"],
        "reviewed_by": plan["reviewed_by"],
        "clients": plan["clients"],
        "recall": plan["recall"],
        "learning": plan["learning"],
        "writes": [
            {key: item[key] for key in ("path", "kind", "status", "sha256")}
            for item in plan["writes"]
        ],
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_answers(answers: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(answers, dict):
        raise ValueError("onboarding input must be a JSON object")
    reviewed_by = clean_scalar(answers.get("reviewed_by"))
    if not reviewed_by:
        raise ValueError("reviewed_by is required before durable onboarding")

    baseline = {kind: clean_list(answers.get(kind)) for kind in BASELINE_KINDS}
    missing = [kind for kind, values in baseline.items() if not values]
    if missing:
        raise ValueError("minimum onboarding requires: " + ", ".join(missing))

    sensitivity = clean_scalar(answers.get("sensitivity")) or "internal"
    if sensitivity not in ALLOWED_SENSITIVITY:
        raise ValueError("sensitivity must be public or internal for injectable baseline memory")

    clients = clean_list(answers.get("clients")) or list(DEFAULT_CLIENTS)
    clients = unique(slugify(client, fallback="") for client in clients)
    clients = [client for client in clients if client]
    if not clients:
        raise ValueError("at least one client is required")

    recall_input = answers.get("recall") if isinstance(answers.get("recall"), dict) else {}
    learning_input = answers.get("learning") if isinstance(answers.get("learning"), dict) else {}
    default_budget = bounded_int(recall_input.get("default_budget_tokens"), 1200, 200, 8000)
    baseline_budget = bounded_int(
        recall_input.get("baseline_budget_tokens"),
        min(480, default_budget),
        0,
        default_budget,
    )
    recall = {
        "enabled": clean_bool(recall_input.get("enabled"), True),
        "per_turn": clean_bool(recall_input.get("per_turn"), True),
        "default_budget_tokens": default_budget,
        "baseline_budget_tokens": baseline_budget,
        "max_keywords": bounded_int(recall_input.get("max_keywords"), 12, 3, 30),
        "project_from_cwd": clean_bool(recall_input.get("project_from_cwd"), True),
        "min_relevance_score": bounded_float(recall_input.get("min_relevance_score"), 0.18, 0.0, 1.0),
    }
    learning = {
        "hook_metadata": clean_bool(learning_input.get("hook_metadata"), True),
        "session_proposals": clean_bool(learning_input.get("session_proposals"), False),
    }
    projects = normalize_projects(answers.get("projects"))
    return {
        "reviewed_by": reviewed_by,
        **baseline,
        "projects": projects,
        "sensitivity": sensitivity,
        "clients": clients,
        "recall": recall,
        "learning": learning,
    }


def render_documents(answers: dict[str, Any]) -> dict[str, str]:
    today = date.today()
    documents: dict[str, str] = {}
    titles = {
        "values": "Personal Values",
        "preferences": "Working Preferences",
        "recommendations": "Agent Recommendations",
    }
    for kind in BASELINE_KINDS:
        relative_path = f"memories/durable/onboarding-{kind}.md"
        documents[relative_path] = render_memory(
            memory_id=f"onboarding_{kind}",
            title=titles[kind],
            memory_type="durable",
            scope="personal",
            project=None,
            tags=["onboarding", kind],
            aliases=[kind, titles[kind].lower()],
            reviewed_by=answers["reviewed_by"],
            sensitivity=answers["sensitivity"],
            review_after=today + timedelta(days=180),
            body="\n".join(f"- {item}" for item in answers[kind]),
        )

    for project in answers["projects"]:
        slug = slugify(project["name"])
        lines = [f"- Project: `{project['name']}`"]
        if project["paths"]:
            lines.extend(["", "## Paths", "", *[f"- `{item}`" for item in project["paths"]]])
        if project["keywords"]:
            lines.extend(["", "## Recall keywords", "", *[f"- {item}" for item in project["keywords"]]])
        if project["recommendations"]:
            lines.extend(["", "## Recommendations", "", *[f"- {item}" for item in project["recommendations"]]])
        documents[f"memories/projects/{slug}.md"] = render_memory(
            memory_id=f"project_{slug}",
            title=f"{project['name']} Project Profile",
            memory_type="project",
            scope="project",
            project=project["name"],
            tags=unique(["onboarding", "project", slug, *project["keywords"]]),
            aliases=unique([project["name"], *project["aliases"], *project["paths"]]),
            reviewed_by=answers["reviewed_by"],
            sensitivity=answers["sensitivity"],
            review_after=today + timedelta(days=90),
            body="\n".join(lines),
        )

    for path, content in documents.items():
        if scan_text(content, f"<onboarding:{path}>"):
            raise ValueError(f"onboarding content rejected by secret scan: {path}")
    return documents


def render_memory(
    *,
    memory_id: str,
    title: str,
    memory_type: str,
    scope: str,
    project: str | None,
    tags: list[str],
    aliases: list[str],
    reviewed_by: str,
    sensitivity: str,
    review_after: date,
    body: str,
) -> str:
    today = date.today().isoformat()
    project_value = "null" if project is None else yaml_string(project)
    return f"""---
id: {memory_id}
title: {yaml_string(title)}
type: {memory_type}
reviewed: true
reviewed_by: {yaml_string(reviewed_by)}
reviewed_at: {today}
status: active
scope: {scope}
project: {project_value}
tags: {yaml_list(tags)}
aliases: {yaml_list(aliases)}
created_at: {today}
updated_at: {today}
confidence: 1.0
sensitivity: {sensitivity}
source:
  kind: manual
  ref: onboarding-wizard
pin: true
decay: none
review_after: {review_after.isoformat()}
---

# {title}

{body}
"""


def normalize_projects(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("projects must be a list")
    output: list[dict[str, Any]] = []
    project_slugs: set[str] = set()
    for item in value:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            raise ValueError("each project must be an object or name")
        name = clean_scalar(item.get("name"))
        if not name:
            raise ValueError("each project requires a name")
        project_slug = slugify(name)
        if project_slug in project_slugs:
            raise ValueError(f"project names must have unique normalized slugs: {project_slug}")
        project_slugs.add(project_slug)
        output.append(
            {
                "name": name,
                "aliases": clean_list(item.get("aliases")),
                "paths": clean_list(item.get("paths")),
                "keywords": clean_list(item.get("keywords")),
                "recommendations": clean_list(item.get("recommendations")),
            }
        )
    return output


def merge_onboarding_config(text: str, answers: dict[str, Any]) -> str:
    sections = {
        "recall": {**answers["recall"], "clients": answers["clients"]},
        "learning": {**answers["learning"], "clients": answers["clients"]},
    }
    updated = text.rstrip() + ("\n" if text.strip() else "")
    for name, values in sections.items():
        updated = merge_toml_section(updated, name, values)
    if scan_text(updated, "<onboarding-config>"):
        raise ValueError("onboarding config rejected by secret scan")
    return updated.rstrip() + "\n"


def merge_toml_section(text: str, section: str, values: dict[str, Any]) -> str:
    lines = text.splitlines()
    header = f"[{section}]"
    start = next((index for index, line in enumerate(lines) if line.strip() == header), None)
    rendered = [f"{key} = {toml_value(value)}" for key, value in values.items()]
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([header, *rendered])
        return "\n".join(lines) + "\n"
    end = next(
        (index for index in range(start + 1, len(lines)) if re.fullmatch(r"\s*\[[^]]+\]\s*", lines[index])),
        len(lines),
    )
    managed = set(values)
    body = [
        line
        for line in lines[start + 1 : end]
        if not ("=" in line and line.split("=", 1)[0].strip() in managed)
    ]
    while body and not body[-1].strip():
        body.pop()
    lines[start:end] = [header, *body, *rendered, *([""] if end < len(lines) else [])]
    return "\n".join(lines) + "\n"


def planned_write(root: Path, path: Path, content: str, *, kind: str, allow_update: bool) -> dict[str, Any]:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        status = "unchanged" if current == content else ("update" if allow_update else "conflict")
    else:
        status = "create"
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": kind,
        "status": status,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def safe_target(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("onboarding paths must stay inside the vault")
    target = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"onboarding path must not contain symlinks: {relative_path}")
    return target


def atomic_batch_write(batch: list[tuple[Path, str, bool]]) -> None:
    """Stage every file first, then commit with best-effort rollback on failure."""
    staged: list[tuple[Path, Path, bool]] = []
    states: list[dict[str, Any]] = []
    committed = False
    try:
        for path, content, allow_update in batch:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and not allow_update and path.read_text(encoding="utf-8") != content:
                raise FileExistsError(f"refusing to overwrite canonical memory: {path}")
            handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            temp_path = Path(temp_name)
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            staged.append((path, temp_path, allow_update))

        for path, temp_path, allow_update in staged:
            state: dict[str, Any] = {"path": path, "backup": None, "installed": False}
            states.append(state)
            if path.exists():
                if not allow_update:
                    if path.read_text(encoding="utf-8") == temp_path.read_text(encoding="utf-8"):
                        temp_path.unlink()
                        continue
                    raise FileExistsError(f"refusing to overwrite canonical memory: {path}")
                backup = path.with_name(f".{path.name}.{os.getpid()}.bak")
                if backup.exists():
                    raise FileExistsError(f"onboarding backup path already exists: {backup}")
                os.replace(path, backup)
                state["backup"] = backup
            os.replace(temp_path, path)
            state["installed"] = True
        committed = True
    except Exception as original_error:
        rollback_errors: list[str] = []
        for state in reversed(states):
            path = state["path"]
            backup = state["backup"]
            try:
                if state["installed"] and path.exists():
                    path.unlink()
                if isinstance(backup, Path) and backup.exists():
                    os.replace(backup, path)
            except OSError as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        if rollback_errors:
            raise RuntimeError(
                "onboarding rollback incomplete; preserve any .bak files and review: "
                + "; ".join(rollback_errors)
            ) from original_error
        raise
    finally:
        for _, temp_path, _ in staged:
            if temp_path.exists():
                temp_path.unlink()
        if committed:
            for state in states:
                backup = state["backup"]
                if isinstance(backup, Path) and backup.exists():
                    try:
                        backup.unlink()
                    except OSError:
                        pass


def load_answers(args: argparse.Namespace) -> dict[str, Any]:
    sources = sum(bool(value) for value in (args.input_json, args.input_file, args.stdin))
    if sources > 1:
        raise ValueError("choose only one of --input-json, --input-file, or --stdin")
    if args.input_json:
        data = json.loads(args.input_json)
    elif args.input_file:
        data = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
    elif args.stdin:
        data = json.load(sys.stdin)
    elif args.reviewed_by or args.value or args.preference or args.recommendation or args.project:
        data = {
            "reviewed_by": args.reviewed_by,
            "values": args.value,
            "preferences": args.preference,
            "recommendations": args.recommendation,
            "projects": [parse_project_flag(item) for item in args.project],
            "clients": args.client,
            "recall": {"default_budget_tokens": args.budget_tokens} if args.budget_tokens else {},
            "learning": {"session_proposals": args.enable_auto_learning},
        }
    else:
        data = interactive_answers()
    if not isinstance(data, dict):
        raise ValueError("onboarding input must be a JSON object")
    return data


def interactive_answers() -> dict[str, Any]:
    if not sys.stdin.isatty():
        raise ValueError("non-interactive onboarding requires JSON/stdin or explicit flags")
    reviewed_by = input("Reviewer name: ").strip()
    values = prompt_list("Values (semicolon-separated): ")
    preferences = prompt_list("Working preferences (semicolon-separated): ")
    recommendations = prompt_list("Recommendations for agents (semicolon-separated): ")
    project_name = input("Primary project name (optional): ").strip()
    enable_learning = input("Create review-first Stop learning proposals? [y/N]: ").strip().lower() in {"y", "yes"}
    return {
        "reviewed_by": reviewed_by,
        "values": values,
        "preferences": preferences,
        "recommendations": recommendations,
        "projects": [{"name": project_name}] if project_name else [],
        "clients": list(DEFAULT_CLIENTS),
        "learning": {"session_proposals": enable_learning},
    }


def prompt_list(prompt: str) -> list[str]:
    return [item.strip() for item in input(prompt).split(";") if item.strip()]


def parse_project_flag(value: str) -> dict[str, Any]:
    parts = [item.strip() for item in value.split("|")]
    return {
        "name": parts[0],
        "paths": [parts[1]] if len(parts) > 1 and parts[1] else [],
        "aliases": [item.strip() for item in parts[2].split(",") if item.strip()] if len(parts) > 2 else [],
    }


def clean_scalar(value: Any) -> str:
    return " ".join(str(value).split()).strip() if value is not None else ""


def clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("onboarding list fields must be arrays")
    return unique(clean_scalar(item) for item in value if clean_scalar(item))


def clean_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid integer")
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"integer must be between {minimum} and {maximum}")
    return parsed


def bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    if value is None:
        return default
    parsed = float(value)
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"number must be between {minimum} and {maximum}")
    return parsed


def unique(values: Any) -> list[Any]:
    return list(dict.fromkeys(values))


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    return "[" + ", ".join(yaml_string(value) for value in values) + "]"


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Memory vault root.")
    parser.add_argument("--input-json", default=None, help="Inline onboarding JSON object.")
    parser.add_argument("--input-file", default=None, help="Path to onboarding JSON.")
    parser.add_argument("--stdin", action="store_true", help="Read onboarding JSON from stdin.")
    parser.add_argument("--reviewed-by", default=None)
    parser.add_argument("--value", action="append", default=[])
    parser.add_argument("--preference", action="append", default=[])
    parser.add_argument("--recommendation", action="append", default=[])
    parser.add_argument("--project", action="append", default=[], help="name|path|alias1,alias2")
    parser.add_argument("--client", action="append", default=[])
    parser.add_argument("--budget-tokens", type=int, default=None)
    parser.add_argument("--enable-auto-learning", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Apply a plan whose preview fingerprint was reviewed.")
    parser.add_argument("--expect-plan-sha256", default=None, help="Fingerprint returned by the reviewed preview.")
    parser.add_argument("--dry-run", action="store_true", help="Explicit preview alias; preview is the default.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run are mutually exclusive")
    try:
        root = repo_root(args.root)
        answers = load_answers(args)
        result = (
            apply_onboarding(root, answers, args.expect_plan_sha256)
            if args.apply
            else onboarding_plan(root, answers)
        )
        result.setdefault("applied", False)
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": True, **result}, indent=2, ensure_ascii=False))
    else:
        action = "Applied" if result["applied"] else "Preview"
        print(f"{action}: {result['created_count']} create, {result['updated_count']} update, "
              f"{result['unchanged_count']} unchanged, {result['conflict_count']} conflict")
        for item in result["writes"]:
            print(f"- {item['status']}: {item['path']}")
        if not result["applied"] and result.get("can_apply"):
            fingerprint = result["plan_sha256"]
            print(f"plan_sha256: {fingerprint}")
            print(
                "Next: rerun the same answers with "
                f"--apply --expect-plan-sha256 {fingerprint}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
