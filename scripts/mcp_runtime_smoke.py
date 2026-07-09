#!/usr/bin/env python3
"""Run MCP stdio runtime smoke checks after the PR gate is satisfied."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from hook_event import capture_hook_event
from memorylib import repo_root

MAX_LIST_PAGES = 20
MCP_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class SmokeError(RuntimeError):
    pass


def ensure_pr_gate(allow_without_pr: bool) -> str:
    pr_url = os.environ.get("AI_DEMEMORY_PR_URL", "").strip()
    if pr_url:
        return pr_url
    if allow_without_pr:
        return "<manual override>"
    raise SmokeError(
        "AI_DEMEMORY_PR_URL is not set. Create the PR before running MCP runtime smoke checks."
    )


def start_server(checkout_root: Path, memory_root: Path | None = None) -> subprocess.Popen[str]:
    command = [sys.executable, "-m", "ai_dememory_tool.cli", "mcp"]
    if memory_root is not None:
        command.extend(["--root", str(memory_root)])
    command.append("--stdio")
    return subprocess.Popen(
        command,
        cwd=checkout_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def rpc_response(process: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    if process.stdin is None or process.stdout is None:
        raise SmokeError("MCP server pipes were not created")
    request_id = request.get("id")
    if not isinstance(request_id, int):
        raise SmokeError("MCP runtime smoke requests must use integer ids")
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    while True:
        line = process.stdout.readline()
        if not line:
            stderr = process.stderr.read() if process.stderr else ""
            raise SmokeError(f"MCP server returned no response. stderr={stderr}")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise SmokeError("MCP server returned a non-object JSON-RPC message")
        response_id = response.get("id")
        if response_id is None:
            continue
        if response_id != request_id:
            continue
        return response


def rpc(process: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    response = rpc_response(process, request)
    if "error" in response:
        raise SmokeError(f"{request.get('method')} failed: {response['error']}")
    return response["result"]


def send_notification(process: subprocess.Popen[str], notification: dict[str, Any]) -> None:
    if process.stdin is None:
        raise SmokeError("MCP server stdin was not created")
    process.stdin.write(json.dumps(notification) + "\n")
    process.stdin.flush()


def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def list_request(method: str, request_id: int, cursor: str | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if cursor is not None:
        request["params"] = {"cursor": cursor}
    return request


def collect_paginated_items(pages: list[dict[str, Any]], result_key: str, method: str) -> list[dict[str, Any]]:
    if not pages:
        raise SmokeError(f"{method} returned no pages")
    if pages[-1].get("nextCursor") is not None:
        raise SmokeError(f"{method} pagination did not reach the final page")
    items: list[dict[str, Any]] = []
    for page_index, page in enumerate(pages):
        page_items = page.get(result_key)
        if not isinstance(page_items, list):
            raise SmokeError(f"{method} missing {result_key} array")
        for item_index, item in enumerate(page_items):
            if not isinstance(item, dict):
                raise SmokeError(f"{method} {result_key} item {page_index}:{item_index} is not an object")
            items.append(item)
    return items


def assert_unique_field(items: list[dict[str, Any]], field: str, method: str) -> set[str]:
    values: list[str] = []
    for index, item in enumerate(items):
        value = item.get(field)
        if not isinstance(value, str) or not value:
            raise SmokeError(f"{method} item {index} missing non-empty {field}")
        values.append(value)
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise SmokeError(f"{method} returned duplicate {field} values: " + ", ".join(duplicates[:5]))
    return set(values)


def paginated_list(
    process: subprocess.Popen[str],
    method: str,
    result_key: str,
    request_id: int,
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor: str | None = None
    for page_index in range(MAX_LIST_PAGES):
        result = rpc(process, list_request(method, request_id + page_index, cursor))
        pages.append(result)
        next_cursor = result.get("nextCursor")
        if next_cursor is None:
            return collect_paginated_items(pages, result_key, method)
        if not isinstance(next_cursor, str) or not next_cursor:
            raise SmokeError(f"{method} returned invalid nextCursor")
        cursor = next_cursor
    raise SmokeError(f"{method} pagination exceeded safety limit")


def write_fixture_memory(
    root: Path,
    relpath: str,
    memory_id: str,
    sensitivity: str = "internal",
    body: str = "ai DeMemory fixture content.",
    aliases: list[str] | None = None,
    title: str = "ai DeMemory Fixture",
) -> None:
    aliases = aliases or ["fixture memory"]
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {memory_id}
title: {title}
type: tool
status: active
scope: tool
project: null
tags: [codex, memory]
aliases: {json.dumps(aliases)}
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.9
sensitivity: {sensitivity}
source:
  kind: manual
  ref: mcp-smoke
pin: false
decay: normal
review_after: 2026-09-14
---

# {title}

{body}
""",
        encoding="utf-8",
    )


def write_provider_fixture(root: Path) -> None:
    provider_dir = root / "provider-fixtures" / "codex"
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "session.txt").write_text(
        "Codex provider import fixture with non-secret setup notes.\n",
        encoding="utf-8",
    )
    (root / ".ai-dememory.toml").write_text(
        f"""[providers.codex]
enabled = true
path = "{provider_dir.as_posix()}"
capture_raw = false
""",
        encoding="utf-8",
    )


def write_recall_fixture(root: Path) -> None:
    fixture_path = root / "quality" / "recall-fixtures.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        json.dumps(
            [
                {
                    "id": "recall_runtime_smoke",
                    "query": "resource exposure",
                    "expected_ids": ["mem_fixture_internal"],
                    "min_rank": 3,
                    "include_sensitive": False,
                    "notes": "Runtime smoke seed fixture for MCP status coverage.",
                    "source_ref": "mcp-runtime-smoke",
                    "created_at": "2026-06-19",
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def stop_server(process: subprocess.Popen[str]) -> None:
    if process.stdin:
        process.stdin.close()
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    for stream in (process.stdout, process.stderr):
        if stream:
            stream.close()


def tool_call(
    process: subprocess.Popen[str],
    request_id: int,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = rpc(
        process,
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    assert_condition(result.get("isError") is False, f"{name} returned isError")
    structured = result.get("structuredContent")
    assert_condition(isinstance(structured, dict), f"{name} missing structuredContent")
    return structured


def run_fixture_smoke(checkout_root: Path) -> list[str]:
    checks: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        fixture_root = Path(tmp)
        write_provider_fixture(fixture_root)
        write_recall_fixture(fixture_root)
        write_fixture_memory(
            fixture_root,
            "memories/tools/internal.md",
            "mem_fixture_internal",
            body="Internal fixture memory for resource exposure.",
        )
        write_fixture_memory(
            fixture_root,
            "memories/tools/sensitive.md",
            "mem_fixture_sensitive",
            sensitivity="sensitive",
            body="Sensitive fixture phrase must not appear in resources.",
        )
        write_fixture_memory(
            fixture_root,
            "memories/tools/duplicate-one.md",
            "mem_fixture_duplicate_one",
            body="Duplicate runtime smoke memory for conflict review.",
            aliases=["runtime duplicate"],
            title="Runtime Merge Conflict Fixture",
        )
        write_fixture_memory(
            fixture_root,
            "memories/tools/duplicate-two.md",
            "mem_fixture_duplicate_two",
            body="Duplicate runtime smoke memory for conflict review.",
            aliases=["runtime duplicate"],
            title="Runtime Merge Conflict Fixture",
        )
        write_fixture_memory(
            fixture_root,
            "memories/tools/dismiss-one.md",
            "mem_fixture_dismiss_one",
            body="Dismissed runtime smoke memory for conflict review.",
            aliases=["runtime dismiss"],
            title="Runtime Dismiss Conflict Fixture",
        )
        write_fixture_memory(
            fixture_root,
            "memories/tools/dismiss-two.md",
            "mem_fixture_dismiss_two",
            body="Dismissed runtime smoke memory for conflict review.",
            aliases=["runtime dismiss"],
            title="Runtime Dismiss Conflict Fixture",
        )
        hook_capture = capture_hook_event(
            fixture_root,
            "UserPromptSubmit",
            '{"prompt":"Runtime smoke hook capture review."}',
            provider="codex",
        )
        hook_capture_path = hook_capture.relative_to(fixture_root).as_posix() if hook_capture else ""

        process = start_server(checkout_root, fixture_root)
        try:
            reindex = tool_call(process, 99, "memory.reindex")
            assert_condition(reindex.get("count", 0) >= 3, "memory.reindex did not index fixture memories")
            checks.append("fixture memory.reindex")

            resources = paginated_list(process, "resources/list", "resources", 100)
            resource_names = {resource["name"] for resource in resources}
            assert_condition("mem_fixture_internal" in resource_names, "internal fixture resource missing")
            assert_condition(
                "mem_fixture_sensitive" not in resource_names,
                "sensitive fixture leaked into resources/list",
            )
            checks.append("fixture resources sensitive filter")

            sensitive_read = rpc_response(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 101,
                    "method": "resources/read",
                    "params": {"uri": "memory://id/mem_fixture_sensitive"},
                },
            )
            assert_condition("error" in sensitive_read, "sensitive resource read was not rejected")
            checks.append("fixture resources/read sensitive rejection")

            seen = tool_call(
                process,
                102,
                "memory.mark_seen",
                {
                    "query": "runtime smoke fixture",
                    "selected_memory_id": "mem_fixture_internal",
                    "score": 1.0,
                    "used_by": "mcp-smoke",
                },
            )
            assert_condition("created_at" in seen, "memory.mark_seen missing created_at")
            assert_condition(
                seen.get("selected_memory_id") == "mem_fixture_internal",
                "memory.mark_seen missing selected memory receipt",
            )
            assert_condition(seen.get("lifecycle_updated") is True, "memory.mark_seen missing lifecycle receipt")
            checks.append("fixture memory.mark_seen")

            outcome = tool_call(process, 103, "memory.outcome", {"last": True, "outcome": "good"})
            assert_condition(outcome.get("memory_id") == "mem_fixture_internal", "memory.outcome returned wrong id")
            assert_condition(outcome.get("target_source") == "last_seen", "memory.outcome did not report last_seen source")
            assert_condition(outcome.get("lifecycle_updated") is True, "memory.outcome missing lifecycle receipt")
            assert_condition(outcome.get("positive_outcomes") == 1, "memory.outcome did not report positive counter")
            assert_condition("strength" in outcome, "memory.outcome missing lifecycle strength")
            checks.append("fixture memory.outcome")

            lifecycle = tool_call(process, 104, "memory.lifecycle_scores")
            lifecycle_ids = {item["memory_id"] for item in lifecycle.get("scores", [])}
            assert_condition("mem_fixture_internal" in lifecycle_ids, "memory.lifecycle_scores missing fixture id")
            checks.append("fixture memory.lifecycle_scores")

            proposal = tool_call(
                process,
                105,
                "memory.write_proposal",
                {
                    "title": "Runtime Smoke Proposal",
                    "content": "This non-secret proposal should stay in inbox.",
                    "project": "ai-dememory",
                    "tags": ["smoke", "proposal"],
                    "source_kind": "codex",
                },
            )
            proposal_path = proposal["path"]
            assert_condition(
                proposal_path.startswith("inbox/llm-captures/"),
                "proposal path escaped inbox/llm-captures",
            )
            assert_condition((fixture_root / proposal_path).exists(), "proposal file was not written")
            checks.append("fixture write_proposal inbox only")

            miss = tool_call(
                process,
                106,
                "memory.capture_miss",
                {
                    "query": "missing runtime smoke fixture",
                    "reason": "Expected fixture did not rank in this smoke scenario.",
                    "expected_id": "mem_fixture_internal",
                },
            )
            miss_path = miss["path"]
            assert_condition(miss_path.startswith("inbox/recall-feedback/"), "capture_miss path escaped recall inbox")
            assert_condition((fixture_root / miss_path).exists(), "capture_miss file was not written")
            checks.append("fixture memory.capture_miss inbox only")

            candidate = tool_call(
                process,
                107,
                "memory.recall_miss_candidate",
                {
                    "query": "internal fixture memory",
                    "expected_id": "mem_fixture_internal",
                    "min_rank": 3,
                    "limit": 5,
                },
            )
            assert_condition(candidate.get("writes_files") is False, "recall_miss_candidate should be read-only")
            assert_condition(candidate.get("candidate_miss") is False, "recall_miss_candidate should find fixture memory")
            assert_condition(candidate.get("expected_rank") == 1, "recall_miss_candidate returned wrong rank")
            assert_condition(candidate.get("capture_dry_run_command") == [], "non-miss candidate should not suggest capture")
            checks.append("fixture memory.recall_miss_candidate")

            miss_review = tool_call(
                process,
                124,
                "memory.recall_miss_review",
                {
                    "miss": miss_path,
                    "status": "rejected",
                    "reviewer": "Runtime Smoke",
                    "reason": "Runtime smoke closes the first captured miss.",
                },
            )
            assert_condition(miss_review.get("path") == miss_path, "recall_miss_review returned wrong path")
            assert_condition(miss_review.get("status") == "rejected", "recall_miss_review returned wrong status")
            assert_condition(
                miss_review.get("canonical_memory_updated") is False,
                "recall_miss_review should not update canonical memory",
            )
            checks.append("fixture memory.recall_miss_review")

            pending_miss = tool_call(
                process,
                126,
                "memory.capture_miss",
                {
                    "query": "missing second runtime smoke fixture",
                    "reason": "Expected fixture did not rank in this smoke scenario.",
                    "expected_id": "mem_fixture_internal",
                },
            )
            assert_condition(
                pending_miss.get("path", "").startswith("inbox/recall-feedback/"),
                "second capture_miss path escaped recall inbox",
            )

            recall_status = tool_call(process, 125, "memory.recall_fixture_status", {"max_age_days": 14})
            assert_condition(
                recall_status.get("status") == "needs_reviewed_promotion",
                "recall_fixture_status should report seed-only fixtures",
            )
            assert_condition(
                recall_status.get("total_fixtures") == 1,
                "recall_fixture_status returned wrong fixture count",
            )
            checks.append("fixture memory.recall_fixture_status")

            recall_review = tool_call(process, 129, "memory.recall_review_plan", {"max_age_days": 14})
            assert_condition(
                recall_review.get("pending_count") == 1,
                "recall_review_plan should report the captured miss as pending",
            )
            assert_condition(
                recall_review.get("resolved_count") == 1,
                "recall_review_plan should report the rejected miss as resolved",
            )
            assert_condition(
                recall_review.get("pending_misses", [{}])[0].get("path", "").startswith("inbox/recall-feedback/"),
                "recall_review_plan pending miss escaped recall inbox",
            )
            assert_condition(
                recall_review.get("recent_resolved_misses", [{}])[0].get("path") == miss_path,
                "recall_review_plan resolved miss did not match reviewed miss",
            )
            assert_condition(
                "check-miss" in recall_review.get("candidate_check_command", []),
                "recall_review_plan missing candidate check command",
            )
            checks.append("fixture memory.recall_review_plan")

            recall_packet = tool_call(process, 9151, "memory.recall_review_packet", {"max_age_days": 14})
            assert_condition(
                recall_packet.get("pending_count") == 1,
                "recall_review_packet should report the captured miss as pending",
            )
            assert_condition(recall_packet.get("limit") == 50, "recall_review_packet wrong default limit")
            assert_condition(
                recall_packet.get("pending_returned_count") == 1,
                "recall_review_packet wrong pending returned count",
            )
            assert_condition(
                recall_packet.get("pending_offset") == 0,
                "recall_review_packet wrong pending offset",
            )
            assert_condition(
                recall_packet.get("pending_has_more") is False,
                "recall_review_packet should not have more pending pages",
            )
            assert_condition(
                recall_packet.get("writes_files") is False,
                "recall_review_packet must not write report files",
            )
            assert_condition(
                recall_packet.get("writes_fixture_file") is False,
                "recall_review_packet must not write fixtures",
            )
            assert_condition(
                recall_packet.get("reviewer") is None,
                "recall_review_packet should default reviewer metadata to null",
            )
            assert_condition(
                recall_packet.get("pr_url") is None,
                "recall_review_packet should default pr_url metadata to null",
            )
            assert_condition(
                "Recall Review Packet" in recall_packet.get("markdown", ""),
                "recall_review_packet missing packet markdown",
            )
            checks.append("fixture memory.recall_review_packet")

            recall_archive_status = tool_call(process, 9152, "memory.recall_review_packet_archive_status")
            assert_condition(
                recall_archive_status.get("writes_files") is False,
                "recall_review_packet_archive_status must not write files",
            )
            assert_condition(
                recall_archive_status.get("records_fixture_promotions") is False,
                "recall_review_packet_archive_status must not promote fixtures",
            )
            assert_condition(
                recall_archive_status.get("writes_fixture_file") is False,
                "recall_review_packet_archive_status must not write fixtures",
            )
            assert_condition(
                recall_archive_status.get("closes_miss_files") is False,
                "recall_review_packet_archive_status must not close misses",
            )
            assert_condition(
                recall_archive_status.get("archive_root") == "reports/recall-review-packets",
                "recall_review_packet_archive_status wrong archive root",
            )
            assert_condition(
                recall_archive_status.get("limit") == 50,
                "recall_review_packet_archive_status wrong default limit",
            )
            assert_condition(
                recall_archive_status.get("offset") == 0,
                "recall_review_packet_archive_status wrong default offset",
            )
            checks.append("fixture memory.recall_review_packet_archive_status")

            recall_archive_retention = tool_call(process, 9153, "memory.recall_review_packet_archive_retention_plan")
            assert_condition(
                recall_archive_retention.get("writes_files") is False,
                "recall_review_packet_archive_retention_plan must not write files",
            )
            assert_condition(
                recall_archive_retention.get("deletes_files") is False,
                "recall_review_packet_archive_retention_plan must not delete files",
            )
            assert_condition(
                recall_archive_retention.get("records_fixture_promotions") is False,
                "recall_review_packet_archive_retention_plan must not promote fixtures",
            )
            assert_condition(
                recall_archive_retention.get("writes_fixture_file") is False,
                "recall_review_packet_archive_retention_plan must not write fixtures",
            )
            assert_condition(
                recall_archive_retention.get("closes_miss_files") is False,
                "recall_review_packet_archive_retention_plan must not close misses",
            )
            assert_condition(
                recall_archive_retention.get("archive_root") == "reports/recall-review-packets",
                "recall_review_packet_archive_retention_plan wrong archive root",
            )
            assert_condition(
                recall_archive_retention.get("keep") == 30,
                "recall_review_packet_archive_retention_plan wrong default keep",
            )
            checks.append("fixture memory.recall_review_packet_archive_retention_plan")

            vector_status = tool_call(process, 127, "memory.vector_status")
            assert_condition(
                vector_status.get("decision") == "not_justified",
                "vector_status should keep vector search unjustified when fixtures pass",
            )
            assert_condition(
                vector_status.get("recall", {}).get("failed_cases") == 0,
                "vector_status returned failed recall cases for passing fixture",
            )
            checks.append("fixture memory.vector_status")

            roadmap = tool_call(process, 1291, "memory.roadmap_status")
            assert_condition(roadmap.get("writes_files") is False, "roadmap_status must not write files")
            assert_condition(roadmap.get("mutates_files") is False, "roadmap_status must not mutate files")
            assert_condition(roadmap.get("phase_count") == 11, "roadmap_status wrong phase count")
            assert_condition(
                int(roadmap.get("status_counts", {}).get("missing_evidence", 0)) > 0,
                "roadmap_status should report missing implementation evidence in a plain fixture vault",
            )
            checks.append("fixture memory.roadmap_status")

            provenance_status = tool_call(process, 128, "memory.provenance_status")
            assert_condition(
                provenance_status.get("issue_count") == 0,
                "provenance_status should report no durable provenance issues in fixture vault",
            )
            assert_condition("issues" in provenance_status, "provenance_status missing issues list")
            checks.append("fixture memory.provenance_status")

            capture = tool_call(
                process,
                107,
                "memory.capture_import",
                {
                    "kind": "text",
                    "text": "Non-secret imported note for runtime smoke.",
                    "title": "Runtime Smoke Import",
                },
            )
            capture_path = capture["result"]["written"][0]
            assert_condition(
                capture_path.startswith("inbox/imports/text/"),
                "capture_import path escaped inbox/imports/text",
            )
            assert_condition((fixture_root / capture_path).exists(), "capture import file was not written")
            checks.append("fixture capture_import inbox only")

            lesson_repo = fixture_root / "lesson-repo"
            lesson_repo.mkdir()
            subprocess.run(["git", "init"], cwd=lesson_repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(
                ["git", "config", "user.email", "runtime@example.test"],
                cwd=lesson_repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "config", "user.name", "Runtime Smoke"],
                cwd=lesson_repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            (lesson_repo / "ci.yml").write_text("pipeline\n", encoding="utf-8")
            subprocess.run(["git", "add", "ci.yml"], cwd=lesson_repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(
                ["git", "commit", "-m", "fix ci workflow"],
                cwd=lesson_repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            git_lessons = tool_call(
                process,
                130,
                "memory.git_lessons",
                {"repo": str(lesson_repo), "days": 30, "limit": 5},
            )
            assert_condition(git_lessons["result"].get("dry_run") is True, "git_lessons should default to dry-run")
            assert_condition(git_lessons["result"].get("written") == [], "git_lessons dry-run wrote candidates")
            assert_condition(git_lessons["result"].get("examined") == 1, "git_lessons did not find fixture commit")
            assert_condition(
                not (fixture_root / "inbox" / "git-lessons").exists(),
                "git_lessons dry-run created inbox/git-lessons",
            )
            checks.append("fixture memory.git_lessons dry-run")

            import_preview = tool_call(
                process,
                129,
                "memory.import_chats",
                {"provider": "codex", "limit": 1, "dry_run": True},
            )
            preview_result = import_preview["result"]
            assert_condition(preview_result.get("dry_run") is True, "import_chats dry-run flag missing")
            assert_condition(preview_result.get("written") == [], "import_chats dry-run wrote candidates")
            assert_condition(
                preview_result.get("writes_import_candidates") is False,
                "import_chats dry-run reported candidate writes",
            )
            assert_condition(
                any(path.startswith("inbox/imports/codex/") for path in preview_result.get("would_write", [])),
                "import_chats dry-run missing provider inbox preview path",
            )
            checks.append("fixture memory.import_chats dry-run")

            imported = tool_call(process, 108, "memory.import_chats", {"provider": "codex", "limit": 1})
            import_path = imported["result"]["written"][0]
            assert_condition(import_path.startswith("inbox/imports/codex/"), "import_chats path escaped provider inbox")
            assert_condition((fixture_root / import_path).exists(), "import_chats file was not written")
            checks.append("fixture memory.import_chats inbox only")

            doctor = tool_call(process, 126, "memory.doctor")
            doctor_summary = doctor.get("summary", {})
            assert_condition(doctor.get("profile") == "vault", "doctor returned wrong profile")
            assert_condition(doctor_summary.get("total", 0) >= 5, "doctor returned too few checks")
            assert_condition("checks" in doctor, "doctor missing checks")
            checks.append("fixture memory.doctor")

            validation = tool_call(process, 127, "memory.validate_status")
            assert_condition(validation.get("ok") is True, "validate_status should pass for fixture vault")
            assert_condition(validation.get("memory_count", 0) >= 2, "validate_status returned too few memories")
            assert_condition("conflict_review" in validation, "validate_status missing conflict review")
            assert_condition(
                validation["conflict_review"].get("status") in {"scanned", "skipped", "disabled"},
                "validate_status returned unexpected conflict review status",
            )
            checks.append("fixture memory.validate_status")

            maintenance = tool_call(process, 109, "memory.maintenance_status")
            assert_condition("recent_reports" in maintenance, "maintenance_status missing reports")
            assert_condition("providers" in maintenance, "maintenance_status missing providers")
            assert_condition("provider_readiness" in maintenance, "maintenance_status missing provider readiness")
            assert_condition(
                maintenance["provider_readiness"].get("reads_provider_files") is False,
                "maintenance_status provider readiness must not read provider files",
            )
            assert_condition("review_due" in maintenance, "maintenance_status missing review due summary")
            assert_condition(
                maintenance["review_due"].get("canonical_memory_updated") is False,
                "maintenance_status review due summary must not mutate canonical memory",
            )
            assert_condition(
                isinstance(maintenance["review_due"].get("stale_suppressions"), int),
                "maintenance_status missing stale suppression summary",
            )
            assert_condition("conflict_review" in maintenance, "maintenance_status missing conflict review summary")
            assert_condition(
                isinstance(maintenance["conflict_review"].get("active_conflicts"), int),
                "maintenance_status missing active conflict summary",
            )
            assert_condition(
                maintenance["conflict_review"].get("canonical_memory_updated") is False,
                "maintenance_status conflict review summary must not mutate canonical memory",
            )
            assert_condition("review_recommendations" in maintenance, "maintenance_status missing review recommendation summary")
            assert_condition(
                isinstance(maintenance["review_recommendations"].get("pending_count"), int),
                "maintenance_status missing pending review recommendation count",
            )
            assert_condition(
                maintenance["review_recommendations"].get("applies_review_decisions") is False,
                "maintenance_status recommendation summary must not apply review decisions",
            )
            assert_condition(
                "generated_packet_archives" in maintenance,
                "maintenance_status missing generated packet archive summary",
            )
            assert_condition(
                isinstance(maintenance["generated_packet_archives"].get("summary", {}).get("prunable_count"), int),
                "maintenance_status generated packet archive summary missing prunable count",
            )
            assert_condition(
                maintenance["generated_packet_archives"].get("deletes_files") is False,
                "maintenance_status generated packet archive summary must not delete files",
            )
            assert_condition("artifacts" in maintenance, "maintenance_status missing generated artifacts")
            assert_condition(
                "lifecycle_scores" in maintenance["artifacts"],
                "maintenance_status missing lifecycle artifact status",
            )
            assert_condition(
                "artifact_freshness" in maintenance,
                "maintenance_status missing generated artifact freshness",
            )
            assert_condition(
                isinstance(maintenance["artifact_freshness"].get("stale_count"), int),
                "maintenance_status artifact freshness missing stale count",
            )
            assert_condition(
                maintenance["artifact_freshness"].get("writes_files") is False,
                "maintenance_status artifact freshness must not write files",
            )
            checks.append("fixture memory.maintenance_status")

            maintenance_preview = tool_call(
                process,
                910,
                "memory.maintenance_run",
                {"profile": "daily", "dry_run": True},
            )
            maintenance_preview_result = maintenance_preview.get("result", {})
            assert_condition(maintenance_preview_result.get("dry_run") is True, "maintenance_run dry-run flag missing")
            assert_condition(
                maintenance_preview_result.get("writes_files") is False,
                "maintenance_run dry-run must not write files",
            )
            assert_condition(
                maintenance_preview_result.get("writes_import_candidates") is False,
                "maintenance_run dry-run must not write import candidates",
            )
            assert_condition(
                "indexes/memory.sqlite" in maintenance_preview_result.get("would_generate", []),
                "maintenance_run dry-run missing index artifact preview",
            )
            assert_condition(
                isinstance(maintenance_preview_result.get("would_imports"), list),
                "maintenance_run dry-run missing provider import previews",
            )
            assert_condition(
                maintenance_preview_result.get("would_delete_generated_packet_archives") is False,
                "maintenance_run dry-run must not delete generated packet archives",
            )
            assert_condition(
                "artifact_freshness" in maintenance_preview_result,
                "maintenance_run dry-run missing artifact freshness",
            )
            assert_condition(
                maintenance_preview_result["artifact_freshness"].get("writes_files") is False,
                "maintenance_run dry-run artifact freshness must not write files",
            )
            weekly_maintenance_preview = tool_call(
                process,
                911,
                "memory.maintenance_run",
                {"profile": "weekly", "dry_run": True},
            )
            weekly_maintenance_preview_result = weekly_maintenance_preview.get("result", {})
            assert_condition(
                weekly_maintenance_preview_result.get("writes_files") is False,
                "weekly maintenance_run dry-run must not write files",
            )
            assert_condition(
                weekly_maintenance_preview_result.get("would_write_hook_capture_report") is True,
                "weekly maintenance_run dry-run must preview hook capture report",
            )
            assert_condition(
                weekly_maintenance_preview_result.get("would_write_sleep_plan_report") is True,
                "weekly maintenance_run dry-run must preview sleep plan report",
            )
            assert_condition(
                "reports/hook-captures.md" in weekly_maintenance_preview_result.get("would_generate", []),
                "weekly maintenance_run dry-run missing hook capture report target",
            )
            assert_condition(
                "reports/sleep-plan.md" in weekly_maintenance_preview_result.get("would_generate", []),
                "weekly maintenance_run dry-run missing sleep plan report target",
            )
            checks.append("fixture memory.maintenance_run dry-run")

            providers = tool_call(process, 110, "memory.providers_detect")
            provider_names = {item["name"] for item in providers.get("providers", [])}
            assert_condition("codex" in provider_names, "providers_detect missing codex")
            checks.append("fixture memory.providers_detect")

            provider_status = tool_call(process, 111, "memory.providers_status")
            assert_condition("providers" in provider_status, "providers_status missing providers")
            assert_condition(provider_status.get("mutates_system") is False, "providers_status must be read-only")
            assert_condition(
                provider_status.get("configured_count", -1) >= 0,
                "providers_status missing configured count",
            )
            assert_condition(
                any(item.get("name") == "codex" for item in provider_status["providers"]),
                "providers_status missing codex provider",
            )
            checks.append("fixture memory.providers_status")

            provider_plan = tool_call(process, 912, "memory.providers_plan")
            assert_condition("providers" in provider_plan, "providers_plan missing providers")
            assert_condition(provider_plan.get("mutates_system") is False, "providers_plan must be read-only")
            assert_condition(provider_plan.get("reads_provider_files") is False, "providers_plan must not read provider files")
            assert_condition(
                provider_plan.get("writes_import_candidates") is False,
                "providers_plan must not write import candidates",
            )
            codex_provider_plan = next(
                (item for item in provider_plan.get("providers", []) if item.get("name") == "codex"),
                {},
            )
            assert_condition(
                codex_provider_plan.get("configure_dry_run_command", [])[-2:] == ["--dry-run", "--json"],
                "providers_plan must include configure dry-run command",
            )
            checks.append("fixture memory.providers_plan")

            setup = tool_call(process, 913, "memory.setup_plan", {"client": "codex", "mode": "both"})
            assert_condition("commands" in setup, "setup_plan missing commands")
            assert_condition(setup.get("mutates_system") is False, "setup_plan must be read-only")
            assert_condition(setup.get("writes_files") is False, "setup_plan must not write files")
            assert_condition(setup.get("installs_schedules") is False, "setup_plan must not install schedules")
            assert_condition(setup.get("installs_hooks") is False, "setup_plan must not install hooks")
            assert_condition(setup.get("suggests_generated_reports") is True, "setup_plan should flag report commands")
            assert_condition(
                setup.get("suggests_generated_archive_status") is True,
                "setup_plan should flag archive status commands",
            )
            assert_condition(
                setup.get("suggests_generated_archive_retention") is True,
                "setup_plan should flag archive retention commands",
            )
            assert_condition(
                setup["commands"].get("schedule_cron") == ["ai-dememory", "schedule", "cron"],
                "setup_plan should include installed cron export command",
            )
            assert_condition(
                setup["commands"].get("docker_schedule_cron", [])[:4]
                == ["ai-dememory", "schedule", "cron", "--mode"],
                "setup_plan should include Docker cron export command",
            )
            report_commands = setup["commands"].get("generated_reports", {})
            assert_condition(
                report_commands.get("manual_acceptance_plan", [])[-2:] == ["plan", "--write-report"],
                "setup_plan should include manual acceptance report command",
            )
            assert_condition(
                report_commands.get("manual_acceptance_packet", [])[-2:] == ["packet", "--write-report"],
                "setup_plan should include manual acceptance packet command",
            )
            assert_condition(
                report_commands.get("recall_review_packet", [])[-2:] == ["packet", "--write-report"],
                "setup_plan should include recall review packet command",
            )
            archive_status_commands = setup["commands"].get("generated_archive_status", {})
            assert_condition(
                archive_status_commands.get("manual_acceptance_packets", [])[-2:] == ["packet-archive-status", "--json"],
                "setup_plan should include manual acceptance packet archive status command",
            )
            assert_condition(
                archive_status_commands.get("recall_review_packets", [])[-2:] == ["packet-archive-status", "--json"],
                "setup_plan should include recall review packet archive status command",
            )
            archive_retention_commands = setup["commands"].get("generated_archive_retention", {})
            assert_condition(
                archive_retention_commands.get("manual_acceptance_packets", [])[-2:]
                == ["packet-archive-retention-plan", "--json"],
                "setup_plan should include manual acceptance packet archive retention command",
            )
            assert_condition(
                archive_retention_commands.get("recall_review_packets", [])[-2:]
                == ["packet-archive-retention-plan", "--json"],
                "setup_plan should include recall review packet archive retention command",
            )
            assert_condition(
                len(setup["commands"].get("mcp_configs", [])) == 2,
                "setup_plan should return installed and docker configs for client=codex mode=both",
            )
            checks.append("fixture memory.setup_plan")

            setup_health = tool_call(process, 914, "memory.setup_health", {"platform": "linux"})
            assert_condition(setup_health.get("mutates_system") is False, "setup_health must be read-only")
            assert_condition(setup_health.get("runs_commands") is False, "setup_health must not run commands")
            assert_condition(setup_health.get("writes_files") is False, "setup_health must not write files")
            assert_condition("validation_status" in setup_health, "setup_health missing validation status")
            assert_condition(setup_health["validation_status"].get("ok") is True, "setup_health validation status failed")
            assert_condition("recall_review" in setup_health, "setup_health missing recall review")
            assert_condition("next_actions" in setup_health["recall_review"], "setup_health recall review missing actions")
            assert_condition("context_config" in setup_health, "setup_health missing context config")
            assert_condition(setup_health["context_config"].get("valid") is True, "setup_health context config invalid")
            assert_condition("manual_acceptance" in setup_health, "setup_health missing manual acceptance")
            assert_condition(
                setup_health["manual_acceptance"].get("records_evidence") is False,
                "setup_health manual acceptance must not record evidence",
            )
            assert_condition("vector_readiness" in setup_health, "setup_health missing vector readiness")
            assert_condition(
                setup_health["vector_readiness"].get("creates_embeddings") is False,
                "setup_health vector readiness must not create embeddings",
            )
            assert_condition("schedule_environment" in setup_health, "setup_health missing scheduler environment")
            assert_condition("schedule_status" in setup_health, "setup_health missing scheduler status")
            assert_condition("provider_readiness" in setup_health, "setup_health missing provider readiness")
            assert_condition("generated_packet_archives" in setup_health, "setup_health missing generated packet archives")
            archive_health = setup_health["generated_packet_archives"]
            assert_condition(
                archive_health.get("writes_files") is False,
                "setup_health generated packet archives must not write files",
            )
            assert_condition(
                archive_health.get("deletes_files") is False,
                "setup_health generated packet archives must not delete files",
            )
            assert_condition(
                isinstance(archive_health.get("summary", {}).get("prunable_count"), int),
                "setup_health generated packet archives missing prunable count",
            )
            assert_condition("maintenance_preflight" in setup_health, "setup_health missing maintenance preflight")
            assert_condition(
                setup_health["maintenance_preflight"].get("reads_provider_files") is False,
                "setup_health maintenance preflight must not read provider files",
            )
            assert_condition(
                setup_health["maintenance_preflight"].get("writes_files") is False,
                "setup_health maintenance preflight must not write files",
            )
            assert_condition(
                "indexes/memory.sqlite" in setup_health["maintenance_preflight"].get("daily_artifacts", []),
                "setup_health maintenance preflight missing artifact targets",
            )
            assert_condition("artifact_freshness" in setup_health, "setup_health missing artifact freshness")
            assert_condition(
                setup_health["artifact_freshness"].get("writes_files") is False,
                "setup_health artifact freshness must not write files",
            )
            assert_condition("review_due" in setup_health, "setup_health missing review due summary")
            assert_condition("conflict_review" in setup_health, "setup_health missing conflict review summary")
            assert_condition("review_recommendations" in setup_health, "setup_health missing review recommendation summary")
            assert_condition(isinstance(setup_health.get("next_actions"), list), "setup_health missing next actions")
            checks.append("fixture memory.setup_health")

            schedule = tool_call(process, 112, "memory.schedule_plan", {"platform": "linux", "action": "install"})
            schedule_commands = schedule.get("commands", [])
            assert_condition(len(schedule_commands) >= 2, "schedule_plan should return commands")
            assert_condition(
                all(command["command"][0] == "systemctl" for command in schedule_commands),
                "schedule_plan returned unexpected linux command",
            )
            assert_condition(
                any("ai-dememory-daily.timer" in command["command"] for command in schedule_commands),
                "schedule_plan missing daily timer command",
            )
            cron_entries = schedule.get("cron_entries", [])
            assert_condition(len(cron_entries) == 2, "schedule_plan should return daily and weekly cron entries")
            assert_condition(
                any("ai-dememory maintenance run --profile daily" in entry.get("line", "") for entry in cron_entries),
                "schedule_plan missing installed cron daily line",
            )
            assert_condition(schedule.get("mutates_system") is False, "schedule_plan must be read-only")
            assert_condition(schedule.get("runs_commands") is False, "schedule_plan must not run commands")
            assert_condition(schedule.get("writes_files") is False, "schedule_plan must not write files")
            assert_condition(schedule.get("installs_schedules") is False, "schedule_plan must not install schedules")
            docker_schedule = tool_call(
                process,
                113,
                "memory.schedule_plan",
                {"platform": "linux", "action": "install", "mode": "docker", "image": "ai-dememory:local"},
            )
            docker_commands = docker_schedule.get("commands", [])
            assert_condition(
                any(
                    command.get("run_command", [])[:2] == ["docker", "run"]
                    for command in docker_commands
                    if command.get("run_command")
                ),
                "docker schedule_plan missing docker run command",
            )
            docker_cron_entries = docker_schedule.get("cron_entries", [])
            assert_condition(
                any(entry.get("command", [])[:2] == ["docker", "run"] for entry in docker_cron_entries),
                "docker schedule_plan missing docker cron command",
            )
            checks.append("fixture memory.schedule_plan")

            schedule_status = tool_call(process, 114, "memory.schedule_status", {"platform": "linux"})
            assert_condition(schedule_status.get("platform") == "linux", "schedule_status returned wrong platform")
            assert_condition(schedule_status.get("mutates_system") is False, "schedule_status must be read-only")
            assert_condition(
                len(schedule_status.get("status_commands", [])) == 2,
                "schedule_status should return daily and weekly status commands",
            )
            assert_condition(
                isinstance(schedule_status.get("review_due"), dict),
                "schedule_status missing review due summary",
            )
            assert_condition(
                isinstance(schedule_status["review_due"].get("stale_suppressions"), int),
                "schedule_status missing stale suppression summary",
            )
            assert_condition(
                all(command["command"][0] == "systemctl" for command in schedule_status["status_commands"]),
                "schedule_status returned unexpected linux command",
            )
            checks.append("fixture memory.schedule_status")

            config_path = fixture_root / ".ai-dememory.toml"
            original_config = config_path.read_text(encoding="utf-8") if config_path.exists() else None
            config_path.write_text(
                '[schedule]\nenabled = true\ndaily_time = "01:15"\nweekly_day = "FUNDAY"\nweekly_time = "02:30"\n',
                encoding="utf-8",
            )
            invalid_schedule_status = tool_call(process, 141, "memory.schedule_status", {"platform": "linux"})
            if original_config is None:
                config_path.unlink(missing_ok=True)
            else:
                config_path.write_text(original_config, encoding="utf-8")
            assert_condition(
                invalid_schedule_status.get("valid") is False,
                "invalid schedule_status should report valid=false",
            )
            assert_condition(
                invalid_schedule_status.get("validation_errors"),
                "invalid schedule_status should report validation errors",
            )
            assert_condition(
                invalid_schedule_status.get("status_commands") == [],
                "invalid schedule_status should return no platform status commands",
            )
            assert_condition(
                isinstance(invalid_schedule_status.get("review_due"), dict),
                "invalid schedule_status missing review due summary",
            )
            checks.append("fixture memory.schedule_status invalid config")

            schedule_environment = tool_call(process, 142, "memory.schedule_environment", {"platform": "linux"})
            assert_condition(
                schedule_environment.get("mutates_system") is False,
                "schedule_environment must be read-only",
            )
            assert_condition(
                schedule_environment.get("runs_commands") is False,
                "schedule_environment must not run scheduler commands",
            )
            assert_condition(
                any(check.get("name") == "host_scheduler" for check in schedule_environment.get("checks", [])),
                "schedule_environment missing host scheduler check",
            )
            checks.append("fixture memory.schedule_environment")

            acceptance = tool_call(process, 123, "memory.acceptance_status")
            acceptance_items = acceptance.get("items", [])
            assert_condition(acceptance_items, "acceptance_status returned no items")
            assert_condition(
                all("id" in item and "completed" in item for item in acceptance_items),
                "acceptance_status returned malformed items",
            )
            checks.append("fixture memory.acceptance_status")

            verification = tool_call(process, 124, "memory.acceptance_verify")
            acceptance_verification = verification.get("verification", {})
            assert_condition(
                acceptance_verification.get("complete") is False,
                "acceptance_verify should be incomplete for fixture vault",
            )
            assert_condition(
                acceptance_verification.get("total") == len(acceptance_items),
                "acceptance_verify total does not match status items",
            )
            checks.append("fixture memory.acceptance_verify")

            plan_result = tool_call(process, 129, "memory.acceptance_plan")
            acceptance_plan = plan_result.get("plan", {})
            assert_condition(
                acceptance_plan.get("remaining_count") == len(acceptance_items),
                "acceptance_plan wrong remaining count",
            )
            assert_condition(acceptance_plan.get("next_actions"), "acceptance_plan missing next actions")
            assert_condition(
                all(item.get("pass_command") for item in acceptance_plan.get("items", []) if not item.get("completed")),
                "acceptance_plan missing pass commands for remaining items",
            )
            checks.append("fixture memory.acceptance_plan")

            acceptance_template_result = tool_call(
                process,
                914,
                "memory.acceptance_template",
                {"item": "mcp-client-installed"},
            )
            assert_condition(
                acceptance_template_result.get("records_evidence") is False,
                "acceptance_template must not record evidence",
            )
            assert_condition(
                "ai-dememory acceptance record" in acceptance_template_result.get("command", ""),
                "acceptance_template missing record command",
            )
            checks.append("fixture memory.acceptance_template")

            acceptance_packet_result = tool_call(process, 915, "memory.acceptance_packet")
            assert_condition(
                acceptance_packet_result.get("records_evidence") is False,
                "acceptance_packet must not record evidence",
            )
            assert_condition(
                acceptance_packet_result.get("writes_files") is False,
                "acceptance_packet must not write report files",
            )
            assert_condition(acceptance_packet_result.get("limit") == 50, "acceptance_packet wrong default limit")
            assert_condition(
                acceptance_packet_result.get("offset") == 0,
                "acceptance_packet wrong default offset",
            )
            assert_condition(
                acceptance_packet_result.get("has_more") is False,
                "acceptance_packet should not have more pages in fixture",
            )
            assert_condition(
                acceptance_packet_result.get("reviewer") is None,
                "acceptance_packet should default reviewer metadata to null",
            )
            assert_condition(
                acceptance_packet_result.get("pr_url") is None,
                "acceptance_packet should default pr_url metadata to null",
            )
            assert_condition(
                "Manual Acceptance Packet" in acceptance_packet_result.get("markdown", ""),
                "acceptance_packet missing packet markdown",
            )
            checks.append("fixture memory.acceptance_packet")

            acceptance_archive_status = tool_call(process, 916, "memory.acceptance_packet_archive_status")
            assert_condition(
                acceptance_archive_status.get("writes_files") is False,
                "acceptance_packet_archive_status must not write files",
            )
            assert_condition(
                acceptance_archive_status.get("records_evidence") is False,
                "acceptance_packet_archive_status must not record evidence",
            )
            assert_condition(
                acceptance_archive_status.get("writes_acceptance_records") is False,
                "acceptance_packet_archive_status must not write acceptance records",
            )
            assert_condition(
                acceptance_archive_status.get("archive_root") == "reports/manual-acceptance-packets",
                "acceptance_packet_archive_status wrong archive root",
            )
            assert_condition(
                acceptance_archive_status.get("limit") == 50,
                "acceptance_packet_archive_status wrong default limit",
            )
            assert_condition(
                acceptance_archive_status.get("offset") == 0,
                "acceptance_packet_archive_status wrong default offset",
            )
            checks.append("fixture memory.acceptance_packet_archive_status")

            acceptance_archive_retention = tool_call(process, 917, "memory.acceptance_packet_archive_retention_plan")
            assert_condition(
                acceptance_archive_retention.get("writes_files") is False,
                "acceptance_packet_archive_retention_plan must not write files",
            )
            assert_condition(
                acceptance_archive_retention.get("deletes_files") is False,
                "acceptance_packet_archive_retention_plan must not delete files",
            )
            assert_condition(
                acceptance_archive_retention.get("records_evidence") is False,
                "acceptance_packet_archive_retention_plan must not record evidence",
            )
            assert_condition(
                acceptance_archive_retention.get("writes_acceptance_records") is False,
                "acceptance_packet_archive_retention_plan must not write acceptance records",
            )
            assert_condition(
                acceptance_archive_retention.get("archive_root") == "reports/manual-acceptance-packets",
                "acceptance_packet_archive_retention_plan wrong archive root",
            )
            assert_condition(
                acceptance_archive_retention.get("keep") == 30,
                "acceptance_packet_archive_retention_plan wrong default keep",
            )
            checks.append("fixture memory.acceptance_packet_archive_retention_plan")

            release_evidence = tool_call(process, 130, "memory.release_evidence")
            assert_condition(
                release_evidence.get("available") is False,
                "release_evidence should be unavailable in fixture vault",
            )
            assert_condition(
                "distribution checkout" in str(release_evidence.get("reason")),
                "release_evidence unavailable reason should mention distribution checkout",
            )
            checks.append("fixture memory.release_evidence unavailable")

            release_evidence_report = tool_call(process, 1311, "memory.release_evidence_report")
            assert_condition(
                release_evidence_report.get("available") is False,
                "release_evidence_report should be unavailable in fixture vault",
            )
            assert_condition(
                release_evidence_report.get("writes_files") is False,
                "release_evidence_report must not write report files",
            )
            assert_condition(
                release_evidence_report.get("markdown") is None,
                "release_evidence_report should not render markdown in a plain vault",
            )
            checks.append("fixture memory.release_evidence_report unavailable")

            hook_events = tool_call(process, 113, "memory.hook_events", {"provider": "codex"})
            assert_condition("UserPromptSubmit" in hook_events["providers"]["codex"], "hook_events missing codex event")
            checks.append("fixture memory.hook_events")

            hook_config = tool_call(process, 114, "memory.hook_config", {"client": "codex"})
            assert_condition("hooks" in hook_config["config"], "hook_config missing hooks")
            checks.append("fixture memory.hook_config")

            hook_status = tool_call(process, 131, "memory.hook_status", {"client": "codex"})
            assert_condition(hook_status.get("writes_files") is False, "hook_status must be read-only")
            assert_condition(hook_status.get("hooks"), "hook_status missing hooks")
            assert_condition(hook_status["hooks"][0].get("client") == "codex", "hook_status returned wrong client")
            assert_condition("captures" in hook_status, "hook_status missing capture summary")
            assert_condition(
                hook_status["captures"].get("reads_raw_payloads") is False,
                "hook_status capture summary must not read raw payloads",
            )
            assert_condition("review_due_count" in hook_status["captures"], "hook_status missing review due count")
            assert_condition(
                "review_status_counts" in hook_status["captures"],
                "hook_status missing review status counts",
            )
            checks.append("fixture memory.hook_status")

            filtered_hook_status = tool_call(
                process,
                134,
                "memory.hook_status",
                {
                    "client": "codex",
                    "capture_provider": "codex",
                    "capture_event": "UserPromptSubmit",
                    "capture_review_status": "pending",
                    "capture_created_from": "2020-01-01",
                    "capture_created_to": "2099-12-31",
                },
            )
            assert_condition(
                filtered_hook_status["captures"].get("filters")
                == {
                    "created_from": "2020-01-01",
                    "created_to": "2099-12-31",
                    "event": "UserPromptSubmit",
                    "provider": "codex",
                    "review_status": "pending",
                },
                "hook_status capture filters were not applied",
            )
            assert_condition(
                filtered_hook_status["captures"].get("total_count") == 1,
                "hook_status capture filter returned wrong count",
            )
            checks.append("fixture memory.hook_status filtered")

            hook_review = tool_call(
                process,
                132,
                "memory.hook_capture_review",
                {
                    "path": hook_capture_path,
                    "status": "dismissed",
                    "reviewed_by": "Runtime Smoke",
                    "reason": "No durable memory needed.",
                },
            )
            assert_condition(
                hook_review.get("path") == hook_capture_path,
                "hook_capture_review returned unexpected path",
            )
            assert_condition(
                hook_review.get("review_status") == "dismissed",
                "hook_capture_review returned wrong status",
            )
            assert_condition(
                hook_review.get("canonical_memory_updated") is False,
                "hook_capture_review must not promote canonical memory",
            )
            reviewed_hook_status = tool_call(process, 133, "memory.hook_status", {"client": "codex"})
            assert_condition(
                reviewed_hook_status["captures"].get("resolved_count") == 1,
                "hook_capture_review did not clear capture as resolved",
            )
            checks.append("fixture memory.hook_capture_review")

            sleep_plan = tool_call(process, 115, "memory.sleep_plan")
            candidates = sleep_plan.get("candidates", [])
            assert_condition(candidates, "sleep_plan returned no candidates")
            checks.append("fixture memory.sleep_plan")

            sleep_packets = tool_call(
                process,
                116,
                "memory.sleep_apply_reviewed",
                {"ids": [candidates[0]["id"]]},
            )
            packet_path = sleep_packets["written"][0]
            assert_condition(
                packet_path.startswith("inbox/sleep-consolidation/"),
                "sleep_apply_reviewed path escaped sleep inbox",
            )
            assert_condition((fixture_root / packet_path).exists(), "sleep review packet was not written")
            checks.append("fixture memory.sleep_apply_reviewed inbox only")

            working_snapshot = tool_call(
                process,
                117,
                "memory.working_snapshot",
                {
                    "title": "Runtime Smoke Working State",
                    "task": "mcp-runtime-smoke",
                    "notes": "Track generated working state without canonical memory mutation.",
                },
            )
            assert_condition(
                working_snapshot["path"] == "working/current.json",
                "working_snapshot wrote unexpected path",
            )
            assert_condition((fixture_root / "working" / "recent-session.md").exists(), "recent session missing")

            working_current = tool_call(process, 118, "memory.working_current")
            assert_condition(working_current.get("exists") is True, "working_current should exist after snapshot")
            assert_condition(
                working_current.get("current", {}).get("task") == "mcp-runtime-smoke",
                "working_current returned wrong task",
            )

            working_handoff = tool_call(
                process,
                119,
                "memory.working_handoff",
                {
                    "title": "Runtime Smoke Handoff",
                    "notes": "Continue by reviewing the generated working state.",
                },
            )
            assert_condition(
                working_handoff["path"].startswith("working/handoffs/"),
                "working_handoff path escaped handoff directory",
            )
            assert_condition((fixture_root / working_handoff["path"]).exists(), "working handoff was not written")

            working_status = tool_call(process, 120, "memory.working_status", {"limit": 1})
            assert_condition(working_status.get("current_exists") is True, "working_status missing current state")
            assert_condition(working_status.get("recent_session_exists") is True, "working_status missing recent session")
            assert_condition(working_status.get("handoff_count") == 1, "working_status wrong handoff count")
            assert_condition(len(working_status.get("handoffs", [])) == 1, "working_status did not honor limit")
            checks.append("fixture memory.working_state")

            auto_context = tool_call(process, 1201, "memory.context", {"auto": True, "budget_tokens": 700})
            assert_condition(
                auto_context.get("query_source") == "working_memory",
                "memory.context auto did not report working memory query source",
            )
            assert_condition(
                "Runtime Smoke Working State" in auto_context.get("query", ""),
                "memory.context auto did not use working state as query",
            )
            checks.append("fixture memory.context auto")

            false_secret = "sk-" + "proj-" + ("f" * 40)
            secret_fixture = fixture_root / "docs" / "false-positive-fixture.md"
            secret_fixture.parent.mkdir(parents=True, exist_ok=True)
            secret_fixture.write_text(f"OPENAI_API_KEY={false_secret}\n", encoding="utf-8")
            false_positives = tool_call(process, 121, "memory.review_false_positives")
            findings = false_positives.get("findings", [])
            assert_condition(findings, "review_false_positives returned no findings")
            assert_condition(false_positives.get("enabled") is True, "review_false_positives missing enabled policy")
            assert_condition(
                false_positives.get("policy", {}).get("triage_policy") == "human_only",
                "review_false_positives missing policy metadata",
            )
            assert_condition(false_positives.get("due_only") is False, "review_false_positives defaulted to due-only")
            assert_condition(
                false_positives.get("returned_count") == len(findings),
                "review_false_positives returned_count mismatch",
            )
            assert_condition(findings[0]["id"].startswith("fp_"), "review_false_positives returned unstable id")
            checks.append("fixture memory.review_false_positives")

            stale_false_positives = tool_call(process, 1222, "memory.review_stale_false_positives")
            assert_condition(
                isinstance(stale_false_positives.get("stale_count"), int),
                "review_stale_false_positives missing stale_count",
            )
            assert_condition(
                stale_false_positives.get("enabled") is True,
                "review_stale_false_positives missing enabled policy",
            )
            assert_condition(
                isinstance(stale_false_positives.get("items"), list),
                "review_stale_false_positives missing items",
            )
            checks.append("fixture memory.review_stale_false_positives")

            ignored = tool_call(
                process,
                121,
                "memory.false_positive_ignore",
                {
                    "id": findings[0]["id"],
                    "reason": "Runtime smoke false-positive fixture.",
                    "reviewer": "MCP Smoke",
                    "review_after_days": 30,
                },
            )
            assert_condition(ignored["path"] == ".ai-dememory-ignore.toml", "false_positive_ignore wrote unexpected path")
            assert_condition(ignored["id"] == findings[0]["id"], "false_positive_ignore returned wrong id")
            assert_condition(ignored["ignored"] is True, "false_positive_ignore did not report ignored state")
            assert_condition(ignored["reviewer"] == "MCP Smoke", "false_positive_ignore missing reviewer")
            assert_condition(ignored.get("review_after"), "false_positive_ignore missing review_after")
            assert_condition(ignored.get("review_due") is False, "false_positive_ignore should not be due immediately")
            assert_condition(
                ignored.get("review_after_status") == "scheduled",
                "false_positive_ignore missing scheduled review_after status",
            )
            assert_condition(
                ignored["canonical_memory_updated"] is False,
                "false_positive_ignore should not mutate canonical memory",
            )
            checks.append("fixture memory.false_positive_ignore")

            unignored = tool_call(
                process,
                912,
                "memory.false_positive_unignore",
                {"id": findings[0]["id"], "reviewer": "MCP Smoke"},
            )
            assert_condition(
                unignored["path"] == ".ai-dememory-ignore.toml",
                "false_positive_unignore wrote unexpected path",
            )
            assert_condition(unignored["id"] == findings[0]["id"], "false_positive_unignore returned wrong id")
            assert_condition(unignored["ignored"] is False, "false_positive_unignore did not report unignored state")
            assert_condition(unignored["reviewer"] == "MCP Smoke", "false_positive_unignore missing reviewer")
            assert_condition(
                unignored["canonical_memory_updated"] is False,
                "false_positive_unignore should not mutate canonical memory",
            )
            checks.append("fixture memory.false_positive_unignore")

            conflicts = tool_call(process, 122, "memory.review_conflicts")
            conflict_rows = conflicts.get("conflicts", [])
            assert_condition(conflicts.get("enabled") is True, "review_conflicts missing enabled policy")
            assert_condition(
                conflicts.get("policy", {}).get("resolution_policy") == "human_only",
                "review_conflicts missing policy metadata",
            )
            assert_condition(len(conflict_rows) >= 2, "review_conflicts returned too few conflicts")
            assert_condition(conflict_rows[0]["id"].startswith("conf_"), "review_conflicts returned unstable id")
            checks.append("fixture memory.review_conflicts")

            dismiss_conflict_row = next(
                row for row in conflict_rows if "mem_fixture_dismiss_one" in row.get("memory_ids", [])
            )
            dismissed = tool_call(
                process,
                1221,
                "memory.conflict_dismiss",
                {
                    "id": dismiss_conflict_row["id"],
                    "reason": "Runtime smoke intentional duplicate.",
                    "reviewer": "MCP Smoke",
                },
            )
            assert_condition(dismissed["path"] == ".ai-dememory-ignore.toml", "conflict_dismiss wrote unexpected path")
            assert_condition(dismissed["id"] == dismiss_conflict_row["id"], "conflict_dismiss returned wrong id")
            assert_condition(dismissed["status"] == "dismissed", "conflict_dismiss did not record dismissed status")
            assert_condition(dismissed["decision"] == "Runtime smoke intentional duplicate.", "conflict_dismiss wrong decision")
            assert_condition(dismissed["reviewer"] == "MCP Smoke", "conflict_dismiss missing reviewer")
            assert_condition(dismissed.get("reviewed_at"), "conflict_dismiss missing reviewed_at")
            assert_condition(
                dismissed["canonical_memory_updated"] is False,
                "conflict_dismiss should not mutate canonical memory",
            )
            checks.append("fixture memory.conflict_dismiss")

            active_conflict_row = next(
                row for row in conflict_rows if "mem_fixture_duplicate_one" in row.get("memory_ids", [])
            )

            merge = tool_call(
                process,
                123,
                "memory.conflict_merge_proposal",
                {"id": active_conflict_row["id"], "reviewer": "MCP Smoke"},
            )
            assert_condition(
                merge["proposal_path"].startswith("inbox/conflict-resolution/"),
                "conflict_merge_proposal path escaped conflict inbox",
            )
            assert_condition(merge["path"] == ".ai-dememory-ignore.toml", "conflict_merge_proposal wrote unexpected path")
            assert_condition(merge["id"] == active_conflict_row["id"], "conflict_merge_proposal returned wrong id")
            assert_condition(merge["status"] == "review_proposed", "conflict_merge_proposal wrong status")
            assert_condition(merge["decision"] == "merge_proposal", "conflict_merge_proposal wrong decision")
            assert_condition(merge["reviewer"] == "MCP Smoke", "conflict_merge_proposal missing reviewer")
            assert_condition(merge.get("reviewed_at"), "conflict_merge_proposal missing reviewed_at")
            assert_condition(
                merge["canonical_memory_updated"] is False,
                "conflict_merge_proposal should not mutate canonical memory",
            )
            assert_condition((fixture_root / merge["proposal_path"]).exists(), "conflict proposal was not written")
            checks.append("fixture memory.conflict_merge_proposal inbox only")

            keep = tool_call(
                process,
                1231,
                "memory.conflict_keep",
                {"id": active_conflict_row["id"], "keep": active_conflict_row["memory_ids"][0], "reviewer": "MCP Smoke"},
            )
            assert_condition(keep["path"] == ".ai-dememory-ignore.toml", "conflict_keep wrote unexpected path")
            assert_condition(keep["status"] == "resolved", "conflict_keep did not record resolved status")
            assert_condition(keep["decision"].startswith("keep:"), "conflict_keep did not record keep decision")
            assert_condition(keep["reviewer"] == "MCP Smoke", "conflict_keep missing reviewer")
            assert_condition(keep.get("reviewed_at"), "conflict_keep missing reviewed_at")
            assert_condition(keep["canonical_memory_updated"] is False, "conflict_keep should not mutate canonical memory")
            checks.append("fixture memory.conflict_keep")

            modes = tool_call(process, 124, "memory.review_modes")
            assert_condition(modes.get("active") in {"strict", "assisted"}, "review_modes missing active mode")
            assert_condition(
                modes.get("policy", {}).get("conflicts", {}).get("resolution_policy") == "human_only",
                "review_modes missing conflict policy",
            )
            checks.append("fixture memory.review_modes")

            plan = tool_call(process, 125, "memory.review_plan", {"kind": "conflict"})
            assert_condition(plan.get("kind") == "conflict", "review_plan returned wrong kind")
            assert_condition(
                plan.get("policy", {}).get("false_positives", {}).get("triage_policy") == "human_only",
                "review_plan missing false-positive policy",
            )
            checks.append("fixture memory.review_plan")

            configured_mode = tool_call(
                process,
                913,
                "memory.review_configure_mode",
                {"mode": "balanced", "reviewer": "MCP Smoke"},
            )
            assert_condition(
                configured_mode["path"] == ".ai-dememory.toml",
                "review_configure_mode wrote unexpected path",
            )
            assert_condition(configured_mode["requested_mode"] == "balanced", "review_configure_mode wrong request")
            assert_condition(configured_mode["active"] == "balanced", "review_configure_mode did not activate mode")
            assert_condition(configured_mode["reviewer"] == "MCP Smoke", "review_configure_mode missing reviewer")
            assert_condition(
                configured_mode["canonical_memory_updated"] is False,
                "review_configure_mode should not mutate canonical memory",
            )
            configured_modes = tool_call(process, 914, "memory.review_modes")
            assert_condition(configured_modes.get("active") == "balanced", "review_modes did not see configured mode")
            checks.append("fixture memory.review_configure_mode")

            recommendation = tool_call(
                process,
                915,
                "memory.review_recommendation",
                {
                    "kind": "conflict",
                    "target_id": active_conflict_row["id"],
                    "recommendation": "keep_memory",
                    "rationale": "Keep the canonical memory after human review.",
                    "recommended_by": "MCP Smoke",
                    "confidence": 0.7,
                    "evidence": ["mem_codex_test"],
                },
            )
            assert_condition(
                recommendation["path"].startswith("inbox/review-recommendations/"),
                "review_recommendation escaped review recommendation inbox",
            )
            assert_condition(recommendation["mode"] == "balanced", "review_recommendation used wrong mode")
            assert_condition(recommendation["allowed_by_mode"] is True, "review_recommendation policy mismatch")
            assert_condition(
                recommendation["applies_review_decision"] is False,
                "review_recommendation should not apply review decisions",
            )
            assert_condition(
                recommendation["writes_canonical_memory"] is False,
                "review_recommendation should not mutate canonical memory",
            )
            checks.append("fixture memory.review_recommendation inbox only")

            linked_keep = tool_call(
                process,
                9151,
                "memory.conflict_keep",
                {
                    "id": active_conflict_row["id"],
                    "keep": active_conflict_row["memory_ids"][0],
                    "reviewer": "MCP Smoke",
                    "recommendation_id": recommendation["id"],
                },
            )
            assert_condition(
                linked_keep["recommendation_id"] == recommendation["id"],
                "conflict_keep did not link recommendation id",
            )
            assert_condition(
                linked_keep["recommendation_path"] == recommendation["path"],
                "conflict_keep did not return recommendation path",
            )
            assert_condition(
                linked_keep["recommendation_action"] == "keep_memory",
                "conflict_keep linked wrong recommendation action",
            )
            assert_condition(
                linked_keep["canonical_memory_updated"] is False,
                "linked conflict_keep should not mutate canonical memory",
            )
            checks.append("fixture memory.conflict_keep recommendation link")

            recommendations = tool_call(
                process,
                916,
                "memory.review_recommendations",
                {"kind": "conflict"},
            )
            assert_condition(recommendations["total_count"] >= 1, "review_recommendations missed recommendation")
            assert_condition(
                recommendations["writes_files"] is False,
                "review_recommendations should be read-only",
            )
            assert_condition(
                recommendations["applies_review_decisions"] is False,
                "review_recommendations should not apply decisions",
            )
            assert_condition(
                recommendations["writes_canonical_memory"] is False,
                "review_recommendations should not mutate canonical memory",
            )
            checks.append("fixture memory.review_recommendations status")

            archive_status = tool_call(
                process,
                91605,
                "memory.review_recommendation_archive_status",
            )
            assert_condition(
                archive_status["writes_files"] is False,
                "review recommendation archive status should not write files",
            )
            assert_condition(
                archive_status["applies_review_decisions"] is False,
                "review recommendation archive status should not apply decisions",
            )
            assert_condition(
                archive_status["writes_canonical_memory"] is False,
                "review recommendation archive status should not mutate canonical memory",
            )
            assert_condition(
                archive_status["archive_root"] == "archive/review-recommendations",
                "review recommendation archive status wrong archive root",
            )
            assert_condition(
                archive_status["filters"]["recursive"] is False,
                "review recommendation archive status should default to non-recursive",
            )
            assert_condition(archive_status["offset"] == 0, "review recommendation archive status wrong offset")
            assert_condition(
                archive_status["has_more"] is False,
                "empty review recommendation archive status should not have more pages",
            )
            assert_condition(
                archive_status["invalid_offset"] == 0,
                "review recommendation archive status wrong invalid offset",
            )
            assert_condition(
                archive_status["invalid_has_more"] is False,
                "empty review recommendation archive status should not have more invalid pages",
            )
            checks.append("fixture memory.review_recommendation_archive_status")

            restore_preview = tool_call(
                process,
                9161,
                "memory.review_recommendation_archive_restore_preview",
                {"id": recommendation["id"]},
            )
            assert_condition(restore_preview["dry_run"] is True, "archive restore preview should be dry-run")
            assert_condition(
                restore_preview["recursive"] is False,
                "archive restore preview should default to non-recursive",
            )
            assert_condition(
                restore_preview["writes_files"] is False,
                "archive restore preview should not write files",
            )
            assert_condition(
                restore_preview["applies_review_decisions"] is False,
                "archive restore preview should not apply decisions",
            )
            assert_condition(
                restore_preview["writes_canonical_memory"] is False,
                "archive restore preview should not mutate canonical memory",
            )
            assert_condition(
                any(item.get("reason") == "not_found" for item in restore_preview["skipped"]),
                "archive restore preview should report non-archived recommendation as not_found",
            )
            checks.append("fixture memory.review_recommendation_archive_restore_preview")

            outcome = tool_call(
                process,
                917,
                "memory.review_recommendation_outcome",
                {
                    "id": recommendation["id"],
                    "status": "accepted",
                    "reviewer": "MCP Smoke",
                    "reason": "Accepted after smoke review.",
                },
            )
            assert_condition(outcome["path"] == recommendation["path"], "review_recommendation_outcome wrong path")
            assert_condition(outcome["outcome_status"] == "accepted", "review_recommendation_outcome wrong status")
            assert_condition(
                outcome["outcome_applies_review_decision"] is False,
                "review_recommendation_outcome should not apply decisions",
            )
            assert_condition(
                outcome["outcome_writes_canonical_memory"] is False,
                "review_recommendation_outcome should not mutate canonical memory",
            )
            accepted_recommendations = tool_call(
                process,
                918,
                "memory.review_recommendations",
                {"kind": "conflict", "outcome_status": "accepted"},
            )
            assert_condition(
                accepted_recommendations["accepted_count"] >= 1,
                "review_recommendations missed accepted outcome",
            )
            checks.append("fixture memory.review_recommendation_outcome")

            outcome_report = tool_call(
                process,
                919,
                "memory.review_recommendation_outcome_report",
                {"kind": "conflict", "outcome_status": "accepted"},
            )
            assert_condition(
                outcome_report["writes_files"] is False,
                "review_recommendation_outcome_report should not write files",
            )
            assert_condition(
                outcome_report["applies_review_decisions"] is False,
                "review_recommendation_outcome_report should not apply decisions",
            )
            assert_condition(
                outcome_report["writes_canonical_memory"] is False,
                "review_recommendation_outcome_report should not mutate canonical memory",
            )
            assert_condition(
                "Review Recommendation Outcomes" in outcome_report["markdown"],
                "review_recommendation_outcome_report missing markdown",
            )
            assert_condition(
                outcome_report["accepted_count"] >= 1,
                "review_recommendation_outcome_report missed accepted outcome",
            )
            assert_condition(outcome_report["offset"] == 0, "review_recommendation_outcome_report wrong offset")
            assert_condition(
                outcome_report["has_more"] is False,
                "review_recommendation_outcome_report should not have more pages",
            )
            assert_condition(
                outcome_report["invalid_offset"] == 0,
                "review_recommendation_outcome_report wrong invalid offset",
            )
            assert_condition(
                outcome_report["invalid_has_more"] is False,
                "review_recommendation_outcome_report should not have more invalid pages",
            )
            checks.append("fixture memory.review_recommendation_outcome_report")
        finally:
            stop_server(process)
    return checks


def run_smoke(root: Path, allow_without_pr: bool = False) -> list[str]:
    gate = ensure_pr_gate(allow_without_pr)
    checks: list[str] = [f"pr_gate={gate}"]
    process = start_server(root)
    try:
        init = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}},
            },
        )
        assert_condition(init["protocolVersion"] == "2025-11-25", "protocol negotiation failed")
        checks.append("initialize")

        send_notification(process, MCP_INITIALIZED)
        checks.append("notifications/initialized")

        ping = rpc(process, {"jsonrpc": "2.0", "id": 8, "method": "ping"})
        assert_condition(ping == {}, "ping did not return an empty result")
        checks.append("ping")

        tools = paginated_list(process, "tools/list", "tools", 2000)
        tool_names = assert_unique_field(tools, "name", "tools/list")
        expected_tools = {
            "memory.search",
            "memory.get",
            "memory.context",
            "memory.write_proposal",
            "memory.doctor",
            "memory.validate_status",
            "memory.mark_seen",
            "memory.outcome",
            "memory.lifecycle_scores",
            "memory.sleep_plan",
            "memory.sleep_apply_reviewed",
            "memory.reindex",
            "memory.consolidate",
            "memory.secret_scan",
            "memory.graph",
            "memory.capture_miss",
            "memory.recall_miss_candidate",
            "memory.recall_fixture_status",
            "memory.recall_review_plan",
            "memory.recall_review_packet",
            "memory.recall_review_packet_archive_status",
            "memory.recall_review_packet_archive_retention_plan",
            "memory.recall_miss_review",
            "memory.vector_status",
            "memory.roadmap_status",
            "memory.provenance_status",
            "memory.working_current",
            "memory.working_status",
            "memory.working_snapshot",
            "memory.working_handoff",
            "memory.maintenance_status",
            "memory.import_chats",
            "memory.capture_import",
            "memory.git_lessons",
            "memory.maintenance_run",
            "memory.schedule_plan",
            "memory.schedule_status",
            "memory.schedule_environment",
            "memory.acceptance_status",
            "memory.acceptance_verify",
            "memory.acceptance_plan",
            "memory.acceptance_template",
            "memory.acceptance_packet",
            "memory.acceptance_packet_archive_status",
            "memory.acceptance_packet_archive_retention_plan",
            "memory.release_evidence",
            "memory.release_evidence_report",
            "memory.publish_plan",
            "memory.hook_events",
            "memory.hook_config",
            "memory.hook_status",
            "memory.hook_capture_review",
            "memory.providers_detect",
            "memory.providers_status",
            "memory.providers_plan",
            "memory.setup_plan",
            "memory.setup_health",
            "memory.review_false_positives",
            "memory.review_stale_false_positives",
            "memory.false_positive_ignore",
            "memory.false_positive_unignore",
            "memory.review_conflicts",
            "memory.conflict_dismiss",
            "memory.conflict_merge_proposal",
            "memory.conflict_keep",
            "memory.review_modes",
            "memory.review_configure_mode",
            "memory.review_plan",
            "memory.review_recommendation",
            "memory.review_recommendations",
            "memory.review_recommendation_archive_status",
            "memory.review_recommendation_archive_restore_preview",
            "memory.review_recommendation_outcome_report",
            "memory.review_recommendation_outcome",
        }
        assert_condition(expected_tools <= tool_names, "tools/list missing expected tools")
        checks.append("tools/list")

        resources = paginated_list(process, "resources/list", "resources", 2100)
        assert_unique_field(resources, "uri", "resources/list")
        checks.append("resources/list")

        prompts = paginated_list(process, "prompts/list", "prompts", 2200)
        prompt_names = assert_unique_field(prompts, "name", "prompts/list")
        assert_condition("memory_recall_context" in prompt_names, "prompts/list missing recall prompt")
        checks.append("prompts/list")

        search = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "memory.search",
                    "arguments": {"query": "ai-dememory", "limit": 1},
                },
            },
        )
        assert_condition(search.get("isError") is False, "memory.search returned isError")
        assert_condition("structuredContent" in search, "memory.search missing structuredContent")
        checks.append("tools/call memory.search")

        graph = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "memory.graph", "arguments": {}},
            },
        )
        assert_condition(graph.get("isError") is False, "memory.graph returned isError")
        assert_condition("nodes" in graph["structuredContent"], "memory.graph missing nodes")
        assert_condition("edges" in graph["structuredContent"], "memory.graph missing edges")
        checks.append("tools/call memory.graph")

        context = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "memory.context",
                    "arguments": {"query": "ai-dememory", "budget_tokens": 1200, "limit": 3},
                },
            },
        )
        assert_condition(context.get("isError") is False, "memory.context returned isError")
        assert_condition("text" in context["structuredContent"], "memory.context missing text")
        checks.append("tools/call memory.context")

        release_evidence = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "memory.release_evidence",
                    "arguments": {"pr_url": gate if gate.startswith("https://github.com/") else None},
                },
            },
        )
        assert_condition(release_evidence.get("isError") is False, "memory.release_evidence returned isError")
        structured = release_evidence["structuredContent"]
        assert_condition(structured.get("available") is True, "memory.release_evidence should be available in checkout")
        assert_condition(
            "release_blockers" in structured.get("evidence", {}),
            "memory.release_evidence missing release blockers",
        )
        assert_condition(
            "setup_health_summary" in structured.get("evidence", {}),
            "memory.release_evidence missing setup health summary",
        )
        assert_condition(
            "maintenance_summary" in structured.get("evidence", {}),
            "memory.release_evidence missing maintenance summary",
        )
        assert_condition(
            "next_actions" in structured.get("evidence", {}),
            "memory.release_evidence missing next actions",
        )
        assert_condition(
            isinstance(structured["evidence"].get("next_actions"), list),
            "memory.release_evidence next actions should be a list",
        )
        assert_condition(
            structured["evidence"]["maintenance_summary"].get("generated_packet_archives", {}).get("deletes_files")
            is False,
            "memory.release_evidence maintenance summary must not delete archives",
        )
        checks.append("tools/call memory.release_evidence")

        release_evidence_report = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 111,
                "method": "tools/call",
                "params": {
                    "name": "memory.release_evidence_report",
                    "arguments": {"pr_url": gate if gate.startswith("https://github.com/") else None},
                },
            },
        )
        assert_condition(
            release_evidence_report.get("isError") is False,
            "memory.release_evidence_report returned isError",
        )
        report_structured = release_evidence_report["structuredContent"]
        assert_condition(
            report_structured.get("available") is True,
            "memory.release_evidence_report should be available in checkout",
        )
        assert_condition(
            report_structured.get("writes_files") is False,
            "memory.release_evidence_report must not write report files",
        )
        assert_condition(
            "# v2 Release Evidence" in str(report_structured.get("markdown") or ""),
            "memory.release_evidence_report missing markdown report",
        )
        assert_condition(
            "## Maintenance Summary" in str(report_structured.get("markdown") or ""),
            "memory.release_evidence_report missing maintenance summary",
        )
        assert_condition(
            "## Next Actions" in str(report_structured.get("markdown") or ""),
            "memory.release_evidence_report missing next actions",
        )
        checks.append("tools/call memory.release_evidence_report")

        publish_plan = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 112,
                "method": "tools/call",
                "params": {
                    "name": "memory.publish_plan",
                    "arguments": {
                        "repository": "testpypi",
                        "pr_url": gate if gate.startswith("https://github.com/") else None,
                    },
                },
            },
        )
        assert_condition(publish_plan.get("isError") is False, "memory.publish_plan returned isError")
        publish_structured = publish_plan["structuredContent"]
        assert_condition(publish_structured.get("repository") == "testpypi", "memory.publish_plan wrong repository")
        assert_condition(
            publish_structured.get("publishes_package") is False,
            "memory.publish_plan must not publish packages",
        )
        assert_condition(
            publish_structured.get("writes_files") is False,
            "memory.publish_plan must not write files",
        )
        assert_condition(
            publish_structured.get("runs_commands") is True,
            "memory.publish_plan should report read-only local inspection commands",
        )
        assert_condition(
            publish_structured.get("runs_publish_commands") is False,
            "memory.publish_plan must not run publish commands",
        )
        assert_condition(
            publish_structured.get("runs_preflight_commands") is False,
            "memory.publish_plan must not run preflight commands",
        )
        assert_condition(
            publish_structured.get("dispatch_inputs", {}).get("confirm") == "publish",
            "memory.publish_plan missing manual confirmation input",
        )
        checks.append("tools/call memory.publish_plan")

        if resources:
            first_uri = resources[0]["uri"]
            resource = rpc(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "resources/read",
                    "params": {"uri": first_uri},
                },
            )
            assert_condition(resource["contents"][0]["mimeType"] == "text/markdown", "bad resource MIME")
            checks.append("resources/read")

        denied = rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "memory.secret_scan", "arguments": {"paths": ["../outside.txt"]}},
            },
        )
        assert_condition(denied.get("isError") is True, "out-of-repo secret scan was not rejected")
        checks.append("secret_scan path boundary")
    finally:
        stop_server(process)
    checks.extend(run_fixture_smoke(root))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument(
        "--allow-without-pr",
        action="store_true",
        help="Bypass AI_DEMEMORY_PR_URL gate for local debugging.",
    )
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        checks = run_smoke(root, allow_without_pr=args.allow_without_pr)
    except SmokeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for check in checks:
        print(f"OK {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
