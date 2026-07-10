from __future__ import annotations

import json
import io
import os
import shlex
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MCP_SERVER = ROOT / "mcp" / "server"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(MCP_SERVER))

from acceptance_guard import validate_acceptance_checklist, validate_acceptance_checklist_text  # noqa: E402
from adr_guard import validate_adr_docs, validate_adr_text  # noqa: E402
from index_memory import rebuild_index  # noqa: E402
from export_context import export_context  # noqa: E402
from capture_miss import capture_miss, main as capture_miss_main, render_miss_text  # noqa: E402
from consolidate_memory import main as consolidate_main, build_report as build_consolidation_report  # noqa: E402
from context_memory import assemble_context, context_defaults, main as context_main  # noqa: E402
from eval_recall import evaluate, load_fixtures  # noqa: E402
import graph_memory  # noqa: E402
from git_lessons import classify_commit, learn_git, main as git_lessons_main  # noqa: E402
from graph_memory import build_graph  # noqa: E402
from hook_event import (  # noqa: E402
    HookEventError,
    archive_reviewed_hook_captures,
    capture_hook_event,
    hook_config,
    hook_capture_summary,
    hook_events,
    main as hook_event_main,
    read_hook_frontmatter,
    render_hook_capture_report,
    review_hook_capture,
    hook_status,
    hook_status_summary,
    install_hook_instructions,
    uninstall_hook_instructions,
    write_hook_capture_report,
)
from http_api import main as api_main, serve  # noqa: E402
from api_smoke import run_api_smoke  # noqa: E402
from install_smoke import (  # noqa: E402
    InstallSmokeError,
    SmokeStep,
    assert_doctor_summary,
    assert_maintenance_status_artifacts,
    assert_mcp_initialize_and_ping,
    assert_release_evidence_report_unavailable,
    assert_release_evidence_unavailable,
    assert_roadmap_status,
    assert_publish_plan,
    assert_schedule_plan,
    assert_vault_template_export,
    docker_client_smoke_command,
    docker_maintenance_status_command,
    docker_publish_plan_command,
    docker_roadmap_status_command,
    docker_release_evidence_command,
    docker_schedule_plan_command,
    docker_vault_template_export_command,
    local_ai_dememory_command,
    mcp_payload,
    package_smoke_commands,
    run_step,
    write_install_smoke_memory,
    venv_paths,
)
from package_build_smoke import (  # noqa: E402
    assert_dist_artifacts,
    assert_no_stale_build_paths,
    cleanup_created_build_paths,
    main as package_build_smoke_main,
)
from lifecycle import (  # noqa: E402
    lifecycle_scores,
    main as lifecycle_main,
    mark_seen as lifecycle_mark_seen,
    record_outcome,
    write_lifecycle_report,
)
from maintenance import (  # noqa: E402
    conflict_review_summary,
    dry_run_maintenance,
    generated_artifact_freshness,
    main as maintenance_main,
    maintenance_status,
    review_due_summary,
    review_recommendation_summary,
    run_maintenance,
)
from manual_acceptance import (  # noqa: E402
    ACCEPTANCE_ITEMS,
    DEFAULT_ACCEPTANCE_PACKET_ARCHIVE_DIR,
    DEFAULT_ACCEPTANCE_PACKET_REPORT,
    DEFAULT_ACCEPTANCE_PLAN_REPORT,
    SUGGESTED_ACCEPTANCE_ARTIFACTS,
    acceptance_packet_archive_retention_plan,
    acceptance_packet_archive_status,
    acceptance_packet_archive_path,
    acceptance_plan,
    acceptance_record_command,
    acceptance_status,
    acceptance_template,
    annotate_acceptance_packet_plan,
    command_arg,
    main as acceptance_main,
    paginate_acceptance_packet_plan,
    record_acceptance,
    render_acceptance_packet_report,
    render_acceptance_plan_report,
    remaining_acceptance_items,
    verify_acceptance,
    write_acceptance_packet_archive,
    write_acceptance_packet_report,
)
from memory_mcp import TOOLS, call_tool, handle_rpc  # noqa: E402
from mcp_client_smoke import override_launch, run_client_config_smoke, run_tools_list_pages, verify_enabled_tools  # noqa: E402
from mcp_inventory import build_inventory, validate_inventory_docs, validate_inventory_texts  # noqa: E402
from mcp_runtime_smoke import MCP_INITIALIZED, assert_unique_field, collect_paginated_items, rpc_response, run_fixture_smoke, send_notification  # noqa: E402
from memorylib import load_memory, repo_relative_path, validate_memories  # noqa: E402
from provider_import import capture_source, configure_provider, configure_provider_preview, detect_providers, import_chats, main as provider_main, provider_setup_plan, providers_status  # noqa: E402
from publish_guard import validate_publish_workflow, validate_publish_workflow_text  # noqa: E402
import publish_plan as publish_plan_module  # noqa: E402
from publish_plan import (  # noqa: E402
    WORKFLOW_URL_PLACEHOLDER,
    github_owner_repo_from_remote,
    publish_plan,
    publish_plan_next_actions,
    publish_readiness_blockers,
    render_text as render_publish_plan_text,
)
from pr_draft_guard import validate_pr_draft, validate_pr_draft_text  # noqa: E402
from pr_template_guard import validate_pr_template, validate_template_text  # noqa: E402
from recall_fixtures import (  # noqa: E402
    DEFAULT_REVIEW_PACKET_ARCHIVE_DIR,
    annotate_recall_review_packet_plan,
    load_recall_miss,
    main as recall_fixtures_main,
    paginate_recall_review_plan,
    promote_miss_to_fixture,
    recall_fixture_freshness,
    recall_miss_candidate,
    recall_fixture_review_plan,
    recall_review_packet_archive_path,
    recall_review_packet_archive_retention_plan,
    recall_review_packet_archive_status,
    render_recall_review_packet,
    review_recall_miss,
    write_recall_review_packet_archive,
    write_recall_review_packet,
    write_recall_review_report,
)
from release_checklist_guard import validate_release_checklist, validate_release_checklist_text  # noqa: E402
from roadmap_status import render_markdown as render_roadmap_status_markdown, roadmap_status  # noqa: E402
from release_evidence import (  # noqa: E402
    blocked_acceptance_items,
    build_release_evidence,
    evidence_to_dict,
    main as release_evidence_main,
    release_blockers,
    release_handoff_commands,
    release_next_actions,
    render_markdown,
)
from release_check import (  # noqa: E402
    EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS,
    EXPECTED_PLUGIN_MCP_TOOLS,
    check_pr_gate,
    check_codex_plugin,
)
from doctor import main as doctor_main, run_checks as run_doctor_checks  # noqa: E402
from schedule_memory import build_cron_entries, build_schedule_commands, configure_schedule, main as schedule_main, render_cron_entries, schedule_environment, schedule_plan, schedule_status  # noqa: E402
from search_memory import search  # noqa: E402
from secret_scan import scan_paths  # noqa: E402
from setup_plan import main as setup_plan_main, setup_health, setup_plan  # noqa: E402
from sleep_consolidation import SleepError, apply_review_packets, build_sleep_plan, main as sleep_main, write_sleep_report  # noqa: E402
from vector_gate import evaluate_vector_readiness  # noqa: E402
from validate_memory import main as validate_main, validate_repo, validate_repo_result  # noqa: E402
from working_memory import handoff, show_current, snapshot, working_status  # noqa: E402
from review_memory import (  # noqa: E402
    REVIEW_MODE_ALIASES,
    REVIEW_MODES,
    ReviewError,
    active_review_mode,
    archive_review_recommendations,
    archived_review_recommendations,
    capture_review_recommendation,
    configure_review_mode,
    conflict_reviews,
    dismiss_conflict,
    false_positive_review_after_days,
    false_positive_reviews,
    ignore_false_positive,
    review_plan,
    review_modes,
    record_review_recommendation_outcome,
    review_recommendations,
    review_policy_config,
    review_state_path,
    restore_archived_review_recommendation,
    main as review_main,
    resolve_conflict,
    stale_false_positive_suppressions,
    unignore_false_positive,
    write_conflict_report,
    write_false_positive_report,
    write_review_recommendation_outcome_report,
    write_stale_false_positive_report,
)
from ai_dememory_tool.cli import build_mcp_config, copy_template_tree, export_vault_template, main as cli_main, mcp_config  # noqa: E402
from ci_guard import validate_ci_workflow, validate_ci_workflow_text  # noqa: E402
from artifact_guard import validate_artifact_paths  # noqa: E402
from vault_setup_guard import validate_create_memory_repo_text, validate_vault_setup  # noqa: E402
from durable_provenance import audit_durable_provenance, render_markdown as render_provenance_markdown  # noqa: E402


class MemoryToolTests(unittest.TestCase):
    def test_repo_vault_template_matches_packaged_template(self) -> None:
        packaged = ROOT / "ai_dememory_tool" / "templates" / "vault"
        repo_template = ROOT / "vault-template"
        packaged_files = {
            path.relative_to(packaged).as_posix(): path.read_text(encoding="utf-8")
            for path in packaged.rglob("*")
            if path.is_file()
        }
        repo_files = {
            path.relative_to(repo_template).as_posix(): path.read_text(encoding="utf-8")
            for path in repo_template.rglob("*")
            if path.is_file()
        }

        self.assertEqual(repo_files, packaged_files)

    def test_init_template_creates_private_vault_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "my-memory"
            copied = copy_template_tree(root)

            self.assertTrue((root / ".ai-dememory.toml").exists())
            self.assertTrue((root / "memories" / "durable" / "README.md").exists())
            self.assertTrue((root / "inbox" / "llm-captures" / "README.md").exists())
            self.assertGreater(len(copied), 5)

    def test_vault_template_export_matches_repository_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "ai-dememory-vault-template"
            copied = export_vault_template(target)
            repo_template = ROOT / "vault-template"
            exported_files = {
                path.relative_to(target).as_posix(): path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file()
            }
            repo_files = {
                path.relative_to(repo_template).as_posix(): path.read_text(encoding="utf-8")
                for path in repo_template.rglob("*")
                if path.is_file()
            }

        self.assertEqual(exported_files, repo_files)
        self.assertIn(".ai-dememory.toml", exported_files)
        self.assertIn(".gitignore", exported_files)
        self.assertGreater(len(copied), 5)

    def test_cli_vault_template_export_emits_json_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "template"
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = cli_main(["vault-template", "export", str(target), "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(Path(payload["target"]), target.resolve())
            self.assertTrue((target / ".ai-dememory.toml").exists())
            self.assertIn("Mark the repository as a GitHub template if it will be reused.", payload["next_steps"])

    def test_fresh_vault_doctor_warns_only_on_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            output = io.StringIO()

            checks = run_doctor_checks(root)
            with redirect_stdout(output):
                exit_code = doctor_main(["--root", str(root), "--json", "--summary"])

        failures = [check for check in checks if check.status == "fail"]
        warnings = [check for check in checks if check.status == "warn"]
        names = {check.name for check in checks}
        summary = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertFalse(failures)
        self.assertEqual([warning.name for warning in warnings], ["index"])
        self.assertNotIn("mcp_contract", names)
        self.assertEqual(summary["profile"], "vault")
        self.assertEqual(summary["summary"]["warn"], 1)
        self.assertFalse(any(check["name"] == "mcp_contract" for check in summary["checks"]))

    def test_mcp_config_points_to_vault_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = mcp_config(["--client", "codex", "--root", str(root)])

            self.assertEqual(exit_code, 0)
            data = tomllib.loads(output.getvalue())
            config = data["mcp_servers"]["ai-dememory"]
            self.assertEqual(config["command"], "ai-dememory")
            self.assertEqual(config["args"], ["mcp", "--stdio"])
            self.assertEqual(Path(config["env"]["AI_DEMEMORY_ROOT"]), root.resolve())

    def test_codex_mcp_config_is_toml_safe_for_unicode_and_quotes(self) -> None:
        root = Path('C:/vault/emoji-U0001f9e0/quoted-"root"')
        rendered = build_mcp_config(
            "codex", "installed", root, command='ai-"dememory', command_args=["--label", "brain-U0001f9e0"]
        )
        config = tomllib.loads(rendered)["mcp_servers"]["ai-dememory"]
        self.assertEqual(config["command"], 'ai-"dememory')
        self.assertEqual(config["args"], ["--label", "brain-U0001f9e0", "mcp", "--stdio"])
        self.assertEqual(config["env"]["AI_DEMEMORY_ROOT"], str(root))

    def test_cli_accepts_global_root_before_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            output = io.StringIO()

            with patch("sys.stdout", output), patch.dict(os.environ, {}, clear=False):
                exit_code = cli_main(["--root", str(root), "maintenance", "status"])

        self.assertEqual(exit_code, 0)
        self.assertIn("recent_reports", output.getvalue())

    def test_mcp_config_can_emit_docker_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = mcp_config(["--client", "generic", "--mode", "docker", "--root", str(root)])

            self.assertEqual(exit_code, 0)
            data = json.loads(output.getvalue())
            self.assertEqual(data["command"], "docker")
            self.assertIn("ai-dememory:local", data["args"])
            self.assertIn(f"{root.resolve()}:/memory", data["args"])
            self.assertEqual(data["env"], {})

    def test_mcp_config_supports_checkout_command_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = mcp_config(
                    [
                        "--client",
                        "generic",
                        "--root",
                        str(root),
                        "--command",
                        "python3",
                        "--command-arg",
                        "scripts/ai_dememory.py",
                    ]
                )
            data = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["command"], "python3")
        self.assertEqual(data["args"], ["scripts/ai_dememory.py", "mcp", "--stdio"])

    def test_mcp_client_smoke_launches_generated_checkout_config(self) -> None:
        config = build_mcp_config(
            "generic",
            "installed",
            ROOT,
            command=sys.executable,
            command_args=["scripts/ai_dememory.py"],
        )
        config["cwd"] = str(ROOT)

        result = run_client_config_smoke(config, ROOT.parent)

        self.assertEqual(Path(result.cwd), ROOT)
        self.assertTrue(result.initialized)
        self.assertTrue(result.pinged)
        self.assertFalse(result.enabled_tools_verified)
        self.assertEqual(result.enabled_tool_count, 0)

    def test_mcp_runtime_fixture_smoke_exercises_v2_tools(self) -> None:
        checks = run_fixture_smoke(ROOT)

        self.assertIn("fixture memory.capture_miss inbox only", checks)
        self.assertIn("fixture memory.recall_miss_candidate", checks)
        self.assertIn("fixture memory.recall_fixture_status", checks)
        self.assertIn("fixture memory.recall_review_packet", checks)
        self.assertIn("fixture memory.recall_review_packet_archive_status", checks)
        self.assertIn("fixture memory.vector_status", checks)
        self.assertIn("fixture memory.roadmap_status", checks)
        self.assertIn("fixture memory.provenance_status", checks)
        self.assertIn("fixture memory.validate_status", checks)
        self.assertIn("fixture memory.working_state", checks)
        self.assertIn("fixture memory.context auto", checks)
        self.assertIn("fixture memory.doctor", checks)
        self.assertIn("fixture memory.import_chats inbox only", checks)
        self.assertIn("fixture memory.schedule_plan", checks)
        self.assertIn("fixture memory.acceptance_status", checks)
        self.assertIn("fixture memory.acceptance_verify", checks)
        self.assertIn("fixture memory.acceptance_plan", checks)
        self.assertIn("fixture memory.acceptance_template", checks)
        self.assertIn("fixture memory.acceptance_packet", checks)
        self.assertIn("fixture memory.acceptance_packet_archive_status", checks)
        self.assertIn("fixture memory.release_evidence unavailable", checks)
        self.assertIn("fixture memory.release_evidence_report unavailable", checks)
        self.assertIn("fixture memory.false_positive_unignore", checks)
        self.assertIn("fixture memory.sleep_apply_reviewed inbox only", checks)
        self.assertIn("fixture memory.conflict_merge_proposal inbox only", checks)
        self.assertIn("fixture memory.conflict_keep", checks)
        self.assertIn("fixture memory.conflict_keep recommendation link", checks)
        self.assertIn("fixture memory.conflict_dismiss", checks)
        self.assertIn("fixture memory.review_configure_mode", checks)
        self.assertIn("fixture memory.review_recommendation inbox only", checks)
        self.assertIn("fixture memory.review_recommendation_archive_status", checks)
        self.assertIn("fixture memory.review_recommendation_archive_restore_preview", checks)
        self.assertIn("fixture memory.review_recommendation_outcome", checks)
        self.assertIn("fixture memory.review_recommendation_outcome_report", checks)

    def test_mcp_runtime_smoke_collects_paginated_list_items(self) -> None:
        pages = [
            {"tools": [{"name": "memory.search"}], "nextCursor": "1"},
            {"tools": [{"name": "memory.context"}]},
        ]

        items = collect_paginated_items(pages, "tools", "tools/list")

        self.assertEqual([item["name"] for item in items], ["memory.search", "memory.context"])
        with self.assertRaisesRegex(Exception, "final page"):
            collect_paginated_items([pages[0]], "tools", "tools/list")
        with self.assertRaisesRegex(Exception, "tools array"):
            collect_paginated_items([{"nextCursor": None}], "tools", "tools/list")
        with self.assertRaisesRegex(Exception, "not an object"):
            collect_paginated_items([{"tools": ["memory.search"]}], "tools", "tools/list")

    def test_mcp_runtime_smoke_rejects_duplicate_list_identities(self) -> None:
        items = [{"name": "memory.search"}, {"name": "memory.context"}]

        self.assertEqual(assert_unique_field(items, "name", "tools/list"), {"memory.search", "memory.context"})
        with self.assertRaisesRegex(Exception, "duplicate name values"):
            assert_unique_field(
                [{"name": "memory.search"}, {"name": "memory.search"}],
                "name",
                "tools/list",
            )
        with self.assertRaisesRegex(Exception, "missing non-empty uri"):
            assert_unique_field([{"name": "memory.search"}], "uri", "resources/list")

    def test_mcp_runtime_smoke_writes_initialized_notification(self) -> None:
        class DummyProcess:
            stdin = io.StringIO()

        process = DummyProcess()

        send_notification(process, MCP_INITIALIZED)  # type: ignore[arg-type]

        self.assertEqual(
            json.loads(process.stdin.getvalue()),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

    def test_mcp_runtime_smoke_matches_response_id_after_notification(self) -> None:
        class DummyProcess:
            stdin = io.StringIO()
            stdout = io.StringIO(
                json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info"}})
                + "\n"
                + json.dumps({"jsonrpc": "2.0", "id": 7, "result": {"ok": True}})
                + "\n"
            )
            stderr = io.StringIO()

        process = DummyProcess()

        response = rpc_response(process, {"jsonrpc": "2.0", "id": 7, "method": "ping"})  # type: ignore[arg-type]

        self.assertEqual(response["result"], {"ok": True})
        self.assertEqual(json.loads(process.stdin.getvalue()), {"jsonrpc": "2.0", "id": 7, "method": "ping"})

    def test_validator_catches_invalid_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "memories" / "durable" / "bad.md"
            bad.parent.mkdir(parents=True)
            bad.write_text("---\nid: Bad ID\n---\n# Bad\n", encoding="utf-8")
            bad_id = root / "memories" / "durable" / "bad-id.md"
            bad_id.write_text(
                valid_memory_text(memory_id="Bad ID"),
                encoding="utf-8",
            )

            _, errors = validate_memories(root)

        self.assertTrue(any("missing required field 'title'" in error for error in errors))
        self.assertTrue(any("id must match" in error for error in errors))

    def test_validator_requires_reviewed_marker_for_durable_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/durable/unreviewed.md",
                memory_id="mem_unreviewed",
                memory_type="durable",
                reviewed=False,
            )

            _, errors = validate_memories(root)

        self.assertTrue(any("durable memories must include reviewed: true" in error for error in errors))

    def test_validator_requires_durable_review_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/durable/reviewed.md",
                memory_id="mem_reviewed",
                memory_type="durable",
                reviewed=True,
                reviewed_by=None,
                reviewed_at=None,
            )

            _, errors = validate_memories(root)

        self.assertTrue(any("reviewed_by must be a non-empty string" in error for error in errors))
        self.assertTrue(any("reviewed_at must use YYYY-MM-DD" in error for error in errors))

    def test_validate_repo_runs_non_blocking_conflict_scan_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")

            exit_code, messages = validate_repo(root)
            result = validate_repo_result(root)

        self.assertEqual(exit_code, 0)
        self.assertTrue(any(message.startswith("Validated 2 memory file(s).") for message in messages))
        self.assertIn("Conflict review scan: 1 conflict(s), 1 active (non-blocking).", messages)
        self.assertIs(result["ok"], True)
        self.assertEqual(result["memory_count"], 2)
        self.assertEqual(result["errors"], [])
        conflict_review = result["conflict_review"]
        self.assertIsInstance(conflict_review, dict)
        self.assertEqual(conflict_review["status"], "scanned")
        self.assertEqual(conflict_review["conflicts"], 1)
        self.assertEqual(conflict_review["active_conflicts"], 1)
        self.assertIs(conflict_review["blocking"], False)

    def test_validate_repo_respects_conflict_scan_policy_toggles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", "scan_on_validate = false", ""]),
                encoding="utf-8",
            )
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            skipped_exit_code, skipped_messages = validate_repo(root)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", "enabled = false", ""]),
                encoding="utf-8",
            )
            disabled_exit_code, disabled_messages = validate_repo(root)
            disabled_result = validate_repo_result(root)

        self.assertEqual(skipped_exit_code, 0)
        self.assertIn("Conflict review scan: skipped by policy.", skipped_messages)
        self.assertEqual(disabled_exit_code, 0)
        self.assertIn("Conflict review scan: disabled by policy.", disabled_messages)
        conflict_review = disabled_result["conflict_review"]
        self.assertIsInstance(conflict_review, dict)
        self.assertEqual(conflict_review["status"], "disabled")
        self.assertIs(conflict_review["blocking"], False)

    def test_validate_main_emits_json_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = validate_main(["--root", str(root), "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIs(payload["ok"], True)
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["memory_count"], 2)
        self.assertEqual(payload["conflict_review"]["status"], "scanned")
        self.assertIn("Validated 2 memory file(s).", payload["messages"])

    def test_validate_main_emits_json_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_path = root / "memories" / "tools" / "bad.md"
            bad_path.parent.mkdir(parents=True)
            bad_path.write_text("---\nid: mem_bad\n---\n\n# Bad\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = validate_main(["--root", str(root), "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(payload["messages"], [])
        self.assertTrue(payload["errors"])
        self.assertEqual(payload["conflict_review"]["status"], "not_run")

    def test_durable_provenance_audit_reports_missing_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/durable/good.md",
                memory_id="mem_good",
                memory_type="durable",
                reviewed=True,
            )
            write_memory(
                root,
                "memories/durable/bad.md",
                memory_id="mem_bad",
                memory_type="durable",
                reviewed=True,
                reviewed_by=None,
                reviewed_at=None,
            )

            audit = audit_durable_provenance(root)
            markdown = render_provenance_markdown(audit)

        self.assertEqual(audit.durable_count, 2)
        self.assertEqual(audit.issue_count, 2)
        self.assertIn("reviewed_by", markdown)
        self.assertIn("reviewed_at", markdown)

    def test_cli_provenance_writes_report_to_custom_in_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/durable/good.md",
                memory_id="mem_good",
                memory_type="durable",
                reviewed=True,
            )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = cli_main(
                    [
                        "--root",
                        str(root),
                        "provenance",
                        "--write-report",
                        "--report-path",
                        "reports/custom-durable-provenance.md",
                        "--json",
                    ]
                )
            result = json.loads(output.getvalue())
            report_text = (root / result["report_path"]).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["report_path"], "reports/custom-durable-provenance.md")
        self.assertIn("Durable Provenance Audit", report_text)

    def test_cli_provenance_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            write_memory(
                root,
                "memories/durable/good.md",
                memory_id="mem_good",
                memory_type="durable",
                reviewed=True,
            )
            outside = Path(tmp) / "durable-provenance.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = cli_main(
                    [
                        "--root",
                        str(root),
                        "provenance",
                        "--write-report",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay under reports/", error.getvalue())
        self.assertFalse(outside.exists())

    def test_cli_provenance_report_rejects_inside_root_non_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/durable/good.md",
                memory_id="mem_good",
                memory_type="durable",
                reviewed=True,
            )
            target = root / "docs" / "durable-provenance.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = cli_main(
                    [
                        "--root",
                        str(root),
                        "provenance",
                        "--write-report",
                        "--report-path",
                        str(target),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay under reports/", error.getvalue())
        self.assertFalse(target.exists())

    def test_consolidate_writes_custom_in_root_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_consolidate_codex")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = consolidate_main(
                    [
                        "--root",
                        str(root),
                        "--dry-run",
                        "--report-path",
                        "reports/custom-consolidation.md",
                    ]
                )
            report_path = root / "reports" / "custom-consolidation.md"
            report_text = report_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("reports/custom-consolidation.md", output.getvalue())
        self.assertIn("Consolidation Dry Run", report_text)

    def test_consolidate_output_alias_still_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_consolidate_codex")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = consolidate_main(
                    [
                        "--root",
                        str(root),
                        "--dry-run",
                        "--output",
                        "reports/compat-consolidation.md",
                    ]
                )
            report_path = root / "reports" / "compat-consolidation.md"
            report_exists = report_path.exists()

        self.assertEqual(exit_code, 0)
        self.assertIn("reports/compat-consolidation.md", output.getvalue())
        self.assertTrue(report_exists)

    def test_consolidate_report_includes_conflict_scan_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")

            report = build_consolidation_report(root)

        self.assertIn("## Conflict Review Scan", report)
        self.assertIn("- status: `scanned`", report)
        self.assertIn("- conflicts: 1", report)
        self.assertIn("- active_conflicts: 1", report)
        self.assertIn("- active_ids:", report)

    def test_consolidate_report_respects_conflict_scan_policy_toggles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", "scan_on_consolidate = false", ""]),
                encoding="utf-8",
            )
            skipped_report = build_consolidation_report(root)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", "enabled = false", ""]),
                encoding="utf-8",
            )
            disabled_report = build_consolidation_report(root)

        self.assertIn("- status: `skipped`", skipped_report)
        self.assertIn("Conflict review scan skipped by policy.", skipped_report)
        self.assertIn("- status: `disabled`", disabled_report)
        self.assertIn("Conflict review scan disabled by policy.", disabled_report)

    def test_consolidate_rejects_outside_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            write_memory(root, "memories/tools/codex.md", memory_id="mem_consolidate_codex")
            outside = Path(tmp) / "consolidation.md"
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = consolidate_main(
                    [
                        "--root",
                        str(root),
                        "--dry-run",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_secret_scanner_detects_fake_secrets_and_redacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("a" * 40)
            github_token = "ghp_" + ("b" * 36)
            private_block = "-----BEGIN " + "PRIVATE KEY-----"
            private_key_field = '"private_' + 'key"'
            path = root / "capture.txt"
            path.write_text(
                f"OPENAI_API_KEY={secret}\n"
                f"{{{private_key_field}:\"{private_block}{secret}-----END PRIVATE KEY-----\"}}\n"
                f"tokens: {secret} {github_token}\n",
                encoding="utf-8",
            )

            findings = scan_paths(root, ["capture.txt"])

        redacted = "\n".join(finding.redacted_line for finding in findings)
        self.assertGreaterEqual(len(findings), 4)
        self.assertNotIn(secret, redacted)
        self.assertNotIn(github_token, redacted)
        self.assertNotIn("-----END PRIVATE KEY-----", redacted)
        self.assertIn("<redacted:", redacted)

    def test_secret_scanner_detects_env_and_database_url_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stripe_secret = "sk_" + "live_" + ("c" * 32)
            database_url = "postgres" + "://user:passw0rd@example.test/db"
            env = root / ".env"
            env.write_text(
                f"stripe_secret_key={stripe_secret}\n"
                "password=lowercase-secret\n"
                f"DATABASE_URL={database_url}\n",
                encoding="utf-8",
            )

            findings = scan_paths(root, [".env"])

        kinds = {finding.kind for finding in findings}
        redacted = "\n".join(finding.redacted_line for finding in findings)
        self.assertIn(".env-content", kinds)
        self.assertIn("sensitive-assignment", kinds)
        self.assertNotIn(stripe_secret, redacted)
        self.assertNotIn(database_url, redacted)
        self.assertNotIn("lowercase-secret", redacted)

    def test_false_positive_review_suppresses_and_unignores_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")

            report_path, initial_reviews = write_false_positive_report(root)
            target = initial_reviews[0]
            ignore_false_positive(
                root,
                target.id,
                "Documented test fixture redaction.",
                "Unit Test",
                review_after_days=30,
            )
            ignored_reviews = false_positive_reviews(root)
            with patch("review_memory.today", return_value=date(2099, 1, 1)):
                due_reviews = false_positive_reviews(root)
                due_report_path, _ = write_false_positive_report(root)
                due_report = due_report_path.read_text(encoding="utf-8")
                due_only_path, due_only_reviews = write_false_positive_report(
                    root,
                    Path("reports/due-only.md"),
                    due_only=True,
                )
                due_only_report = due_only_path.read_text(encoding="utf-8")
            unignore_false_positive(root, target.id, "Unit Test")
            active_reviews = false_positive_reviews(root)

        self.assertTrue(report_path.as_posix().endswith("reports/false-positives.md"))
        self.assertTrue(target.id.startswith("fp_"))
        self.assertTrue(any(item.id == target.id and item.ignored for item in ignored_reviews))
        ignored = next(item for item in ignored_reviews if item.id == target.id)
        self.assertEqual(ignored.reviewer, "Unit Test")
        self.assertIsNotNone(ignored.reviewed_at)
        self.assertIsNotNone(ignored.review_after)
        self.assertFalse(ignored.review_due)
        self.assertEqual(ignored.review_after_status, "scheduled")
        due = next(item for item in due_reviews if item.id == target.id)
        self.assertTrue(due.review_due)
        self.assertEqual(due.review_after_status, "due")
        self.assertIn("- review_due: 1", due_report)
        self.assertIn("- review_after_status: `due`", due_report)
        self.assertEqual([item.id for item in due_only_reviews], [target.id])
        self.assertIn("- filter: `due_only`", due_only_report)
        self.assertIn("- review_due: 1", due_only_report)
        self.assertTrue(any(item.id == target.id and not item.ignored for item in active_reviews))

    def test_false_positive_review_rejects_invalid_or_unknown_ids_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]
            injected = f"{target.id}]\n[conflicts.conf_0000000000000000"

            with self.assertRaisesRegex(ReviewError, "invalid false-positive id"):
                ignore_false_positive(root, injected, "Documented test fixture redaction.", "Unit Test")
            with self.assertRaisesRegex(ReviewError, "unknown false-positive id"):
                ignore_false_positive(root, "fp_0000000000000000", "Documented test fixture redaction.", "Unit Test")
            with self.assertRaisesRegex(ReviewError, "unknown false-positive id"):
                unignore_false_positive(root, "fp_0000000000000000", "Unit Test")

            self.assertFalse((root / ".ai-dememory-ignore.toml").exists())

    def test_false_positive_ignore_uses_configured_review_window_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[false_positives]", "review_after_days = 14", ""]),
                encoding="utf-8",
            )
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]

            with patch("review_memory.today", return_value=date(2026, 6, 21)):
                configured_days = false_positive_review_after_days(root)
                explicit_days = false_positive_review_after_days(root, 3)
                ignore_false_positive(root, target.id, "Documented test fixture redaction.", "Unit Test")
                ignored = false_positive_reviews(root)[0]
                ignore_false_positive(root, target.id, "Documented test fixture redaction.", "Unit Test", review_after_days=3)
                explicit = false_positive_reviews(root)[0]

        self.assertEqual(configured_days, 14)
        self.assertEqual(explicit_days, 3)
        self.assertEqual(ignored.review_after, "2026-07-05")
        self.assertEqual(ignored.review_after_status, "scheduled")
        self.assertEqual(explicit.review_after, "2026-06-24")

    def test_mcp_false_positive_ignore_uses_configured_review_window_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            config = root / ".ai-dememory.toml"
            config.write_text(
                config.read_text(encoding="utf-8") + "\n[false_positives]\nreview_after_days = 7\n",
                encoding="utf-8",
            )
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]

            with patch("review_memory.today", return_value=date(2026, 6, 21)):
                receipt = call_tool(
                    "memory.false_positive_ignore",
                    {
                        "id": target.id,
                        "reason": "Documented test fixture redaction.",
                        "reviewer": "Unit Test",
                    },
                    root,
                )

        self.assertEqual(receipt["review_after"], "2026-06-28")
        self.assertEqual(receipt["review_after_status"], "scheduled")
        self.assertFalse(receipt["canonical_memory_updated"])

    def test_mcp_false_positive_unignore_reports_state_for_stale_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]

            ignore_false_positive(
                root,
                target.id,
                "Documented test fixture redaction.",
                "Unit Test",
                review_after_days=30,
            )
            path.unlink()
            stale = stale_false_positive_suppressions(root)
            receipt = call_tool(
                "memory.false_positive_unignore",
                {
                    "id": target.id,
                    "reviewer": "Unit Test",
                },
                root,
            )

        self.assertEqual([item.id for item in stale], [target.id])
        self.assertEqual(receipt["path"], ".ai-dememory-ignore.toml")
        self.assertEqual(receipt["id"], target.id)
        self.assertFalse(receipt["ignored"])
        self.assertEqual(receipt["reviewer"], "Unit Test")
        self.assertIsNotNone(receipt["reviewed_at"])
        self.assertFalse(receipt["review_due"])
        self.assertEqual(receipt["review_after_status"], "not_ignored")
        self.assertFalse(receipt["canonical_memory_updated"])

    def test_review_state_path_can_be_configured_for_false_positives_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[false_positives]",
                        "allow_ignore_file = true",
                        "ignore_file = \"review/state.toml\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            finding = false_positive_reviews(root)[0]
            conflict = conflict_reviews(root)[0]

            state_path = review_state_path(root)
            fp_path = ignore_false_positive(root, finding.id, "Documented test fixture redaction.", "Unit Test")
            dismiss_path = dismiss_conflict(root, conflict.id, "Intentional duplicate fixture.", "Unit Test")
            ignored = false_positive_reviews(root)[0]
            dismissed = conflict_reviews(root)[0]
            configured_state_exists = (root / "review" / "state.toml").exists()
            default_state_exists = (root / ".ai-dememory-ignore.toml").exists()

        self.assertEqual(repo_relative_path(state_path, root), "review/state.toml")
        self.assertEqual(fp_path, state_path)
        self.assertEqual(dismiss_path, state_path)
        self.assertTrue(ignored.ignored)
        self.assertEqual(dismissed.status, "dismissed")
        self.assertTrue(configured_state_exists)
        self.assertFalse(default_state_exists)

    def test_review_state_path_rejects_outside_configured_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            finding = false_positive_reviews(root)[0]
            outside = Path(tmp) / "review-state.toml"
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[false_positives]",
                        "allow_ignore_file = true",
                        f"ignore_file = \"{outside.as_posix()}\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ReviewError, "review state path must stay inside"):
                ignore_false_positive(root, finding.id, "Documented test fixture redaction.", "Unit Test")

        self.assertFalse(outside.exists())

    def test_review_state_path_rejects_disabled_custom_ignore_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[false_positives]",
                        "allow_ignore_file = false",
                        "ignore_file = \"review/state.toml\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ReviewError, "configured false-positive ignore file is disabled"):
                review_state_path(root)

    def test_review_state_path_rejects_symlinked_in_root_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            secret = "sk-" + "proj-" + ("f" * 40)
            target = root / "docs" / "example.md"
            target.parent.mkdir(parents=True)
            target.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            finding = false_positive_reviews(root)[0]
            memory_target = root / "memories" / "tools" / "canonical.md"
            memory_target.parent.mkdir(parents=True)
            memory_target.write_text("---\nid: mem_canonical\n---\nCanonical memory.\n", encoding="utf-8")
            state = root / "review" / "state.toml"
            state.parent.mkdir(parents=True)
            try:
                os.symlink(memory_target, state)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[false_positives]",
                        "allow_ignore_file = true",
                        "ignore_file = \"review/state.toml\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ReviewError, "config path"):
                ignore_false_positive(root, finding.id, "Documented test fixture redaction.", "Unit Test")

            self.assertIn("Canonical memory.", memory_target.read_text(encoding="utf-8"))

    def test_false_positive_due_only_cli_filters_review_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]
            ignore_false_positive(root, target.id, "Documented test fixture redaction.", "Unit Test", review_after_days=1)
            output = io.StringIO()

            with patch("review_memory.today", return_value=date(2099, 1, 1)), redirect_stdout(output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "false-positives",
                        "--due-only",
                        "--report-path",
                        "reports/due-only.md",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            report_text = (root / "reports" / "due-only.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["due_only"])
        self.assertEqual(payload["returned_count"], 1)
        self.assertEqual(payload["findings"][0]["id"], target.id)
        self.assertIn("- filter: `due_only`", report_text)

    def test_false_positive_ignore_links_review_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            configure_review_mode(root, "balanced", reviewer="Unit Test")
            target = false_positive_reviews(root)[0]
            recommendation = capture_review_recommendation(
                root,
                kind="false-positive",
                target_id=target.id,
                recommendation="ignore_false_positive",
                rationale="Reviewed fixture secret is expected.",
                recommended_by="Unit Test LLM",
            )

            ignore_false_positive(
                root,
                target.id,
                "Documented test fixture redaction.",
                "Unit Test",
                recommendation_id=recommendation.id,
            )
            ignored = false_positive_reviews(root)[0]
            report_path, _ = write_false_positive_report(root)
            report_text = report_path.read_text(encoding="utf-8")
            state_text = review_state_path(root).read_text(encoding="utf-8")

        self.assertEqual(ignored.recommendation_id, recommendation.id)
        self.assertEqual(ignored.recommendation_path, recommendation.path)
        self.assertEqual(ignored.recommendation_action, "ignore_false_positive")
        self.assertFalse(ignored.recommendation_policy_violation)
        self.assertIn(f'recommendation_id = "{recommendation.id}"', state_text)
        self.assertIn(f"- recommendation_id: `{recommendation.id}`", report_text)

    def test_false_positive_link_rejects_symlinked_recommendation_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            configure_review_mode(root, "balanced", reviewer="Unit Test")
            target = false_positive_reviews(root)[0]
            recommendation = capture_review_recommendation(
                root,
                kind="false-positive",
                target_id=target.id,
                recommendation="ignore_false_positive",
                rationale="Do not trust symlinked recommendation artifacts.",
                recommended_by="Unit Test LLM",
            )
            recommendation_path = root / recommendation.path
            outside = Path(tmp) / "outside-recommendation.md"
            outside.write_text(recommendation_path.read_text(encoding="utf-8"), encoding="utf-8")
            recommendation_path.unlink()
            try:
                os.symlink(outside, recommendation_path)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ReviewError, "unknown review recommendation id"):
                ignore_false_positive(
                    root,
                    target.id,
                    "Documented test fixture redaction.",
                    "Unit Test",
                    recommendation_id=recommendation.id,
                )
            ignored = false_positive_reviews(root)[0]
            state_exists = review_state_path(root).exists()

        self.assertIsNone(ignored.recommendation_id)
        self.assertFalse(state_exists)

    def test_review_report_json_includes_policy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[false_positives]",
                        "enabled = false",
                        "",
                        "[conflicts]",
                        "enabled = false",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            fp_output = io.StringIO()
            conflict_output = io.StringIO()

            with redirect_stdout(fp_output):
                fp_exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "false-positives",
                        "--json",
                    ]
                )
            with redirect_stdout(conflict_output):
                conflict_exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "conflicts",
                        "--json",
                    ]
                )

            fp_payload = json.loads(fp_output.getvalue())
            conflict_payload = json.loads(conflict_output.getvalue())

        self.assertEqual(fp_exit_code, 0)
        self.assertFalse(fp_payload["enabled"])
        self.assertEqual(fp_payload["policy"]["triage_policy"], "human_only")
        self.assertEqual(fp_payload["returned_count"], 0)
        self.assertEqual(conflict_exit_code, 0)
        self.assertFalse(conflict_payload["enabled"])
        self.assertEqual(conflict_payload["policy"]["resolution_policy"], "human_only")
        self.assertEqual(conflict_payload["conflicts"], [])

    def test_mcp_false_positive_due_only_filters_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]
            ignore_false_positive(root, target.id, "Documented test fixture redaction.", "Unit Test", review_after_days=1)

            with patch("review_memory.today", return_value=date(2099, 1, 1)):
                result = call_tool("memory.review_false_positives", {"due_only": True}, root)

        self.assertTrue(result["due_only"])
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["findings"][0]["id"], target.id)
        self.assertTrue(result["findings"][0]["review_due"])

    def test_stale_false_positive_suppression_report_and_mcp_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]
            ignore_false_positive(root, target.id, "Documented test fixture redaction.", "Unit Test", review_after_days=1)
            path.unlink()

            stale = stale_false_positive_suppressions(root)
            report_path, report_items = write_stale_false_positive_report(root)
            report_text = report_path.read_text(encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "stale-false-positives",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            mcp_result = call_tool("memory.review_stale_false_positives", {}, root)

        self.assertEqual([item.id for item in stale], [target.id])
        self.assertEqual(report_items[0].id, target.id)
        self.assertIn("Stale False-Positive Suppression Review", report_text)
        self.assertIn("- stale_suppressions: 1", report_text)
        self.assertIn("## Review Policy", report_text)
        self.assertIn("- enabled: `true`", report_text)
        self.assertIn("- triage_policy: `human_only`", report_text)
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["stale_count"], 1)
        self.assertEqual(payload["items"][0]["id"], target.id)
        self.assertEqual(mcp_result["stale_count"], 1)
        self.assertEqual(mcp_result["items"][0]["status"], "stale_suppression")

    def test_false_positive_report_writes_custom_in_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "false-positives",
                        "--report-path",
                        "reports/custom-false-positives.md",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["path"]).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["path"], "reports/custom-false-positives.md")
        self.assertIn("False Positive Review", report_text)
        self.assertNotIn(secret, report_text)

    def test_false_positive_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "false-positives.md"
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "false-positives",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_false_positive_and_stale_reports_reject_canonical_memory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]
            ignore_false_positive(root, target.id, "Documented test fixture redaction.", "Unit Test")

            with self.assertRaisesRegex(ReviewError, "report path must stay under reports"):
                write_false_positive_report(root, root / "memories" / "false-positives.md")
            with self.assertRaisesRegex(ReviewError, "report path must stay under reports"):
                write_stale_false_positive_report(root, root / "memories" / "stale-false-positives.md")

            self.assertFalse((root / "memories" / "false-positives.md").exists())
            self.assertFalse((root / "memories" / "stale-false-positives.md").exists())

    def test_conflict_review_detects_dismisses_and_writes_merge_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")

            report_path, conflicts = write_conflict_report(root)
            conflict = conflicts[0]
            dismiss_conflict(root, conflict.id, "Intentional duplicate fixture.", "Unit Test")
            dismissed = conflict_reviews(root)[0]
            resolve_conflict(root, conflict.id, "Unit Test", merge_proposal=True)
            proposed = conflict_reviews(root)[0]
            resolve_conflict(root, conflict.id, "Unit Test", keep="mem_conflict_one")
            resolved = conflict_reviews(root)[0]
            proposals = list((root / "inbox" / "conflict-resolution").glob("*.md"))
            proposal_text = proposals[0].read_text(encoding="utf-8")

        self.assertTrue(report_path.as_posix().endswith("reports/conflicts.md"))
        self.assertTrue(conflict.id.startswith("conf_"))
        self.assertEqual(conflict.category, "duplicate")
        self.assertEqual(dismissed.status, "dismissed")
        self.assertEqual(proposed.status, "review_proposed")
        self.assertEqual(resolved.status, "resolved")
        self.assertEqual(resolved.decision, "keep:mem_conflict_one")
        self.assertEqual(len(proposals), 1)
        self.assertIn("Conflict Merge Proposal", proposal_text)

    def test_conflict_review_rejects_invalid_or_unknown_ids_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            conflict = conflict_reviews(root)[0]
            injected = f"{conflict.id}]\n[false_positives.fp_0000000000000000"

            with self.assertRaisesRegex(ReviewError, "invalid conflict id"):
                dismiss_conflict(root, injected, "Intentional duplicate fixture.", "Unit Test")
            with self.assertRaisesRegex(ReviewError, "unknown conflict id"):
                dismiss_conflict(root, "conf_0000000000000000", "Intentional duplicate fixture.", "Unit Test")
            with self.assertRaisesRegex(ReviewError, "unknown conflict id"):
                resolve_conflict(root, "conf_0000000000000000", "Unit Test", keep="mem_conflict_one")
            with self.assertRaisesRegex(ReviewError, "unknown conflict id"):
                resolve_conflict(root, "conf_0000000000000000", "Unit Test", merge_proposal=True)
            with self.assertRaisesRegex(ReviewError, "keep memory id must belong to conflict"):
                resolve_conflict(root, conflict.id, "Unit Test", keep="mem_unrelated")

            self.assertFalse((root / ".ai-dememory-ignore.toml").exists())
            self.assertFalse((root / "inbox" / "conflict-resolution").exists())

    def test_conflict_resolution_links_review_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            configure_review_mode(root, "balanced", reviewer="Unit Test")
            conflict = conflict_reviews(root)[0]
            recommendation = capture_review_recommendation(
                root,
                kind="conflict",
                target_id=conflict.id,
                recommendation="keep_memory",
                rationale="Keep the first memory after human review.",
                recommended_by="Unit Test LLM",
            )

            resolve_conflict(
                root,
                conflict.id,
                "Unit Test",
                keep="mem_conflict_one",
                recommendation_id=recommendation.id,
            )
            resolved = conflict_reviews(root)[0]
            report_path, _ = write_conflict_report(root)
            report_text = report_path.read_text(encoding="utf-8")
            state_text = review_state_path(root).read_text(encoding="utf-8")

        self.assertEqual(resolved.recommendation_id, recommendation.id)
        self.assertEqual(resolved.recommendation_path, recommendation.path)
        self.assertEqual(resolved.recommendation_action, "keep_memory")
        self.assertFalse(resolved.recommendation_policy_violation)
        self.assertIn(f'recommendation_id = "{recommendation.id}"', state_text)
        self.assertIn(f"- recommendation_id: `{recommendation.id}`", report_text)

    def test_conflict_resolution_rejects_mismatched_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            conflict = conflict_reviews(root)[0]
            recommendation = capture_review_recommendation(
                root,
                kind="conflict",
                target_id=conflict.id,
                recommendation="collect_evidence",
                rationale="Collecting evidence is not an accepted keep decision.",
                recommended_by="Unit Test LLM",
            )

            with self.assertRaisesRegex(ReviewError, "expected one of keep_memory"):
                resolve_conflict(
                    root,
                    conflict.id,
                    "Unit Test",
                    keep="mem_conflict_one",
                    recommendation_id=recommendation.id,
                )
            state_exists = review_state_path(root).exists()

        self.assertFalse(state_exists)

    def test_conflict_review_classifies_stale_and_tool_policy_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale_title = "Scheduler Setup Notes"
            policy_title = "GitHub Tool Policy"
            stale_active = valid_memory_text(
                "mem_stale_current",
                title=stale_title,
                body="Current scheduler setup guidance.",
            ).replace("aliases: [codex test]", "aliases: []")
            stale_old = valid_memory_text(
                "mem_stale_old",
                title=stale_title,
                body="Older scheduler setup guidance.",
            ).replace("status: active", "status: stale").replace("aliases: [codex test]", "aliases: []")
            policy_one = valid_memory_text(
                "mem_policy_one",
                title=policy_title,
                body="Prefer the native GitHub connector.",
            ).replace("tags: [codex, memory]", "tags: [codex, memory, policy]").replace("aliases: [codex test]", "aliases: []")
            policy_two = valid_memory_text(
                "mem_policy_two",
                title=policy_title,
                body="Use gh only as a fallback.",
            ).replace("tags: [codex, memory]", "tags: [codex, memory, policy]").replace("aliases: [codex test]", "aliases: []")
            for relpath, text in (
                ("memories/tools/stale-current.md", stale_active),
                ("memories/tools/stale-old.md", stale_old),
                ("memories/tools/policy-one.md", policy_one),
                ("memories/tools/policy-two.md", policy_two),
            ):
                path = root / relpath
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            report_path, conflicts = write_conflict_report(root)
            report_text = report_path.read_text(encoding="utf-8")

        by_category = {conflict.category: conflict for conflict in conflicts}
        self.assertEqual(set(by_category), {"stale_vs_current", "tool_policy_conflict"})
        self.assertEqual(by_category["stale_vs_current"].memory_ids, ["mem_stale_current", "mem_stale_old"])
        self.assertIn("stale, be superseded, or be refreshed", by_category["stale_vs_current"].suggested_action)
        self.assertEqual(by_category["tool_policy_conflict"].memory_ids, ["mem_policy_one", "mem_policy_two"])
        self.assertIn("tool-policy precedence", by_category["tool_policy_conflict"].suggested_action)
        self.assertIn("stale_vs_current", report_text)
        self.assertIn("tool_policy_conflict", report_text)

    def test_conflict_report_writes_custom_in_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "conflicts",
                        "--report-path",
                        "reports/custom-conflicts.md",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["path"]).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["path"], "reports/custom-conflicts.md")
        self.assertIn("Memory Conflict Review", report_text)
        self.assertEqual(len(payload["conflicts"]), 1)

    def test_conflict_review_uses_configured_report_and_proposal_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[conflicts]",
                        "report_path = \"reports/review/custom-conflicts.md\"",
                        "proposal_path = \"inbox/custom-conflicts\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")

            report_path, conflicts = write_conflict_report(root)
            resolve_conflict(root, conflicts[0].id, "Unit Test", merge_proposal=True)
            reviewed = conflict_reviews(root)[0]
            proposals = list((root / "inbox" / "custom-conflicts").glob("*.md"))

        self.assertEqual(repo_relative_path(report_path, root), "reports/review/custom-conflicts.md")
        self.assertEqual(len(proposals), 1)
        self.assertTrue(reviewed.proposal_path.startswith("inbox/custom-conflicts/"))

    def test_conflict_merge_proposal_rejects_configured_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "conflict-proposals"
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", f"proposal_path = \"{outside}\"", ""]),
                encoding="utf-8",
            )
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            conflict = conflict_reviews(root)[0]

            with self.assertRaisesRegex(ReviewError, "conflict proposal path must stay inside"):
                resolve_conflict(root, conflict.id, "Unit Test", merge_proposal=True)

        self.assertFalse(outside.exists())

    def test_conflict_merge_proposal_rejects_canonical_memory_and_symlink_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", "proposal_path = \"memories/conflict-resolution\"", ""]),
                encoding="utf-8",
            )
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            conflict = conflict_reviews(root)[0]

            with self.assertRaisesRegex(ReviewError, "conflict proposal path must stay under inbox"):
                resolve_conflict(root, conflict.id, "Unit Test", merge_proposal=True)

            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", "proposal_path = \"inbox/conflict-resolution\"", ""]),
                encoding="utf-8",
            )
            symlink_target = root / "memories" / "symlink-proposals"
            symlink_target.mkdir(parents=True)
            link = root / "inbox" / "conflict-resolution"
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.symlink(symlink_target, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ReviewError, "config path"):
                resolve_conflict(root, conflict.id, "Unit Test", merge_proposal=True)

            self.assertEqual(list(symlink_target.glob("*.md")), [])

    def test_conflict_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "conflicts.md"
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "conflicts",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_conflict_report_rejects_canonical_memory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")

            with self.assertRaisesRegex(ReviewError, "report path must stay under reports"):
                write_conflict_report(root, root / "memories" / "conflicts.md")

            self.assertFalse((root / "memories" / "conflicts.md").exists())

    def test_review_modes_configure_policy_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)

            default_mode = active_review_mode(root)
            configure_review_mode(root, "assisted", reviewer="Unit Test")
            assisted_mode = active_review_mode(root)
            plan = review_plan(root, "conflict")
            configure_review_mode(root, "balanced", reviewer="Unit Test")
            balanced_mode = active_review_mode(root)
            configure_review_mode(root, "batch", reviewer="Unit Test")
            alias_mode = active_review_mode(root)
            inbox_plan = review_plan(root, "inbox")
            modes = review_modes(root)
            config_text = (root / ".ai-dememory.toml").read_text(encoding="utf-8")
            secret = "sk-" + "proj-" + ("g" * 40)
            with self.assertRaises(ReviewError):
                configure_review_mode(root, "missing")
            with self.assertRaises(ReviewError):
                configure_review_mode(root, "strict", reviewer=secret)

        self.assertEqual(default_mode.name, "strict")
        self.assertEqual(assisted_mode.name, "assisted")
        self.assertTrue(assisted_mode.allow_llm_merge_proposals)
        self.assertEqual(plan.mode, "assisted")
        self.assertIn("Draft conflict merge proposals", "\n".join(plan.allowed_llm_actions))
        self.assertEqual(balanced_mode.name, "balanced")
        self.assertFalse(balanced_mode.allow_llm_merge_proposals)
        self.assertEqual(alias_mode.name, "autonomous_proposals")
        self.assertTrue(alias_mode.allow_autonomous_inbox_proposals)
        self.assertIn("low-risk inbox proposals", "\n".join(inbox_plan.allowed_llm_actions))
        self.assertEqual(REVIEW_MODE_ALIASES["batch"], "autonomous_proposals")
        self.assertEqual({mode["name"] for mode in modes["modes"]}, set(REVIEW_MODES))
        self.assertIn('mode = "autonomous_proposals"', config_text)

    def test_configure_review_mode_rejects_symlinked_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside.toml"
            copy_template_tree(root)
            outside.write_text("[review]\nmode = \"strict\"\n", encoding="utf-8")
            config = root / ".ai-dememory.toml"
            config.unlink()
            try:
                os.symlink(outside, config)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "config path"):
                configure_review_mode(root, "balanced", reviewer="Unit Test")

            self.assertEqual(outside.read_text(encoding="utf-8"), "[review]\nmode = \"strict\"\n")

    def test_review_recommendation_writes_advisory_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            configure_review_mode(root, "assisted", reviewer="Unit Test")

            result = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conf_123",
                recommendation="merge_proposal",
                rationale="The two memories describe the same policy and should be merged after review.",
                recommended_by="Unit Test LLM",
                confidence=0.82,
                evidence=["mem_a", "mem_b"],
            )
            artifact = root / result.path
            text = artifact.read_text(encoding="utf-8")

        self.assertTrue(result.path.startswith("inbox/review-recommendations/"))
        self.assertTrue(result.id.startswith("rec_"))
        self.assertEqual(result.mode, "assisted")
        self.assertTrue(result.allowed_by_mode)
        self.assertFalse(result.policy_violation)
        self.assertTrue(result.requires_human_approval)
        self.assertTrue(result.writes_files)
        self.assertFalse(result.applies_review_decision)
        self.assertFalse(result.writes_canonical_memory)
        self.assertIn("type: review-recommendation", text)
        self.assertIn("requires_human_approval: true", text)
        self.assertIn("does not suppress false positives, resolve conflicts, promote memory, or edit canonical memory", text)

    def test_review_recommendation_records_policy_violation_without_applying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)

            result = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conf_123",
                recommendation="keep_memory",
                rationale="A strict-mode recommendation should be captured only as audit evidence.",
                recommended_by="Unit Test LLM",
            )

        self.assertEqual(result.mode, "strict")
        self.assertFalse(result.allowed_by_mode)
        self.assertTrue(result.policy_violation)
        self.assertFalse(result.applies_review_decision)
        self.assertFalse(result.writes_canonical_memory)

    def test_review_recommendation_rejects_secret_like_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            secret = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz"

            with self.assertRaisesRegex(ReviewError, "rationale contains secret-like content"):
                capture_review_recommendation(
                    root,
                    kind="conflict",
                    target_id="conf_123",
                    recommendation="merge_proposal",
                    rationale=secret,
                    recommended_by="Unit Test LLM",
                )

            recommendation_files = [
                path for path in (root / "inbox" / "review-recommendations").glob("*.md") if path.name != "README.md"
            ]

        self.assertEqual(recommendation_files, [])

    def test_review_recommendation_rejects_symlinked_inbox_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            inbox_root = root / "inbox" / "review-recommendations"
            outside_inbox = root / "active"
            for path in inbox_root.glob("*"):
                path.unlink()
            inbox_root.rmdir()
            try:
                os.symlink(outside_inbox, inbox_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ReviewError, "inbox path must not contain symlinks"):
                capture_review_recommendation(
                    root,
                    kind="conflict",
                    target_id="conf_123",
                    recommendation="merge_proposal",
                    rationale="A symlinked recommendation inbox must not redirect writes.",
                    recommended_by="Unit Test LLM",
                )
            active_files = list(outside_inbox.glob("*.md"))

        self.assertEqual(active_files, [])

    def test_review_recommendation_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            configure_review_mode(root, "balanced", reviewer="Unit Test")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendation",
                        "--kind",
                        "conflict",
                        "--target-id",
                        "conf_123",
                        "--recommendation",
                        "keep_memory",
                        "--rationale",
                        "Keep the newer policy memory after human review.",
                        "--recommended-by",
                        "Unit Test LLM",
                        "--confidence",
                        "0.7",
                        "--evidence",
                        "mem_policy_new",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "conflict")
        self.assertEqual(payload["recommendation"], "keep_memory")
        self.assertEqual(payload["mode"], "balanced")
        self.assertTrue(payload["allowed_by_mode"])
        self.assertTrue(payload["path"].startswith("inbox/review-recommendations/"))

    def test_review_recommendations_lists_filters_and_invalid_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            configure_review_mode(root, "balanced", reviewer="Unit Test")
            capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conf_allowed",
                recommendation="keep_memory",
                rationale="Keep the newer memory after review.",
                recommended_by="Unit Test LLM",
                confidence=0.7,
                evidence=["mem_new"],
            )
            configure_review_mode(root, "strict", reviewer="Unit Test")
            capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conf_violation",
                recommendation="keep_memory",
                rationale="Strict mode should flag this recommendation.",
                recommended_by="Unit Test LLM",
            )
            invalid = root / "inbox" / "review-recommendations" / "bad.md"
            invalid.write_text("---\ntype: note\n---\n", encoding="utf-8")

            all_items = review_recommendations(root)
            violations = review_recommendations(root, policy_violations_only=True)
            conflicts = review_recommendations(root, kind="conflict")

        self.assertEqual(all_items["total_count"], 2)
        self.assertEqual(all_items["invalid_count"], 1)
        self.assertEqual(all_items["policy_violation_count"], 1)
        self.assertEqual(all_items["allowed_count"], 1)
        self.assertEqual(all_items["requires_human_approval_count"], 2)
        self.assertFalse(all_items["mutates_system"])
        self.assertFalse(all_items["writes_files"])
        self.assertFalse(all_items["applies_review_decisions"])
        self.assertFalse(all_items["writes_canonical_memory"])
        self.assertIn("Fix or remove malformed", "\n".join(all_items["next_actions"]))
        self.assertEqual(violations["total_count"], 1)
        self.assertEqual(violations["recommendations"][0]["target_id"], "conf_violation")
        self.assertEqual(conflicts["total_count"], 2)

    def test_review_recommendations_redacts_secret_like_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation_dir = root / "inbox" / "review-recommendations"
            fake_key = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz"
            artifact = recommendation_dir / "secret.md"
            artifact.write_text(
                "---\n"
                "id: rec_secret\n"
                "type: review-recommendation\n"
                "kind: conflict\n"
                "target_id: conf_secret\n"
                "recommendation: collect_evidence\n"
                "confidence: 0.5\n"
                f"recommended_by: {fake_key}\n"
                "mode: strict\n"
                "allowed_by_mode: true\n"
                "policy_violation: false\n"
                "requires_human_approval: true\n"
                "applies_review_decision: false\n"
                "writes_canonical_memory: false\n"
                "created_at: 2026-06-21T00:00:00+00:00\n"
                "evidence:\n"
                "  - conf_secret\n"
                "---\n",
                encoding="utf-8",
            )

            result = review_recommendations(root)

        self.assertEqual(result["total_count"], 1)
        self.assertTrue(result["recommendations"][0]["redacted_fields"])
        self.assertEqual(result["recommendations"][0]["recommended_by"], "<redacted:secret-like>")

    def test_review_recommendations_cli_json_and_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Review weekly maintenance output.",
                recommended_by="Unit Test LLM",
            )
            cli_output = io.StringIO()

            with patch("sys.stdout", cli_output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations",
                        "--kind",
                        "maintenance",
                        "--json",
                    ]
                )
            cli_payload = json.loads(cli_output.getvalue())
            mcp_payload = call_tool("memory.review_recommendations", {"kind": "maintenance"}, root)

        self.assertEqual(exit_code, 0)
        self.assertEqual(cli_payload["total_count"], 1)
        self.assertEqual(cli_payload["filters"]["kind"], "maintenance")
        self.assertFalse(cli_payload["writes_files"])
        self.assertEqual(mcp_payload["total_count"], 1)
        self.assertFalse(mcp_payload["applies_review_decisions"])

    def test_review_recommendation_outcome_records_reviewed_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Review weekly maintenance output.",
                recommended_by="Unit Test LLM",
            )

            result = record_review_recommendation_outcome(
                root,
                recommendation.id,
                "accepted",
                reviewer="Unit Test",
                reason="Accepted after maintenance review.",
            )
            status = review_recommendations(root)
            accepted = review_recommendations(root, outcome_status="accepted")
            pending = review_recommendations(root, outcome_status="pending")
            text = (root / recommendation.path).read_text(encoding="utf-8")

        self.assertEqual(result["path"], recommendation.path)
        self.assertEqual(result["outcome_status"], "accepted")
        self.assertFalse(result["outcome_applies_review_decision"])
        self.assertFalse(result["outcome_writes_canonical_memory"])
        self.assertFalse(result["writes_canonical_memory"])
        self.assertFalse(result["applies_review_decision"])
        self.assertEqual(status["accepted_count"], 1)
        self.assertEqual(status["pending_count"], 0)
        self.assertEqual(accepted["total_count"], 1)
        self.assertEqual(pending["total_count"], 0)
        self.assertEqual(status["recommendations"][0]["outcome_status"], "accepted")
        self.assertIn("outcome_status: \"accepted\"", text)
        self.assertIn("outcome_writes_canonical_memory: false", text)

    def test_review_recommendation_outcome_cli_and_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conf_cli",
                recommendation="collect_evidence",
                rationale="Collect evidence before review.",
                recommended_by="Unit Test LLM",
            )
            cli_output = io.StringIO()

            with patch("sys.stdout", cli_output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendation-outcome",
                        "--id",
                        recommendation.id,
                        "--status",
                        "rejected",
                        "--reviewer",
                        "Unit Test",
                        "--reason",
                        "Rejected after human review.",
                        "--json",
                    ]
                )
            cli_payload = json.loads(cli_output.getvalue())
            mcp_recommendation = call_tool(
                "memory.review_recommendation",
                {
                    "kind": "maintenance",
                    "target_id": "weekly",
                    "recommendation": "maintenance_follow_up",
                    "rationale": "Review weekly maintenance output.",
                    "recommended_by": "Unit Test LLM",
                },
                root,
            )
            mcp_payload = call_tool(
                "memory.review_recommendation_outcome",
                {
                    "id": mcp_recommendation["id"],
                    "status": "accepted",
                    "reviewer": "Unit Test",
                    "reason": "Accepted after review.",
                },
                root,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(cli_payload["outcome_status"], "rejected")
        self.assertFalse(cli_payload["writes_canonical_memory"])
        self.assertEqual(mcp_payload["outcome_status"], "accepted")
        self.assertEqual(mcp_payload["recommendation"]["outcome_status"], "accepted")
        self.assertFalse(mcp_payload["outcome_writes_canonical_memory"])

    def test_review_recommendation_outcome_report_writes_review_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            accepted = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Accepted outcome report fixture.",
                recommended_by="Unit Test LLM",
            )
            rejected = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conflict",
                recommendation="collect_evidence",
                rationale="Rejected outcome report fixture.",
                recommended_by="Unit Test LLM",
            )
            pending = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="pending",
                recommendation="maintenance_follow_up",
                rationale="Pending outcome report fixture.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, accepted.id, "accepted", "Unit Test", "Accepted.")
            record_review_recommendation_outcome(root, rejected.id, "rejected", "Unit Test", "Rejected.")

            report_path, payload = write_review_recommendation_outcome_report(root)
            accepted_path, accepted_payload = write_review_recommendation_outcome_report(
                root,
                "reports/accepted-recommendation-outcomes.md",
                outcome_status="accepted",
            )
            accepted_exists = accepted_path.exists()
            report_text = report_path.read_text(encoding="utf-8")
            output = io.StringIO()
            outside_error = io.StringIO()
            with patch("sys.stdout", output):
                cli_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendation-outcomes",
                        "--kind",
                        "maintenance",
                        "--json",
                    ]
                )
            with redirect_stderr(outside_error):
                outside_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendation-outcomes",
                        "--report-path",
                        str(Path(tmp).parent / "outside.md"),
                    ]
                )
            canonical_error = io.StringIO()
            canonical_path = root / "memories" / "review-recommendation-outcomes.md"
            with redirect_stderr(canonical_error):
                canonical_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendation-outcomes",
                        "--report-path",
                        str(canonical_path),
                    ]
                )
            cli_payload = json.loads(output.getvalue())

        self.assertEqual(repo_relative_path(report_path, root), "reports/review-recommendation-outcomes.md")
        self.assertEqual(payload["total_count"], 2)
        self.assertEqual(payload["accepted_count"], 1)
        self.assertEqual(payload["rejected_count"], 1)
        self.assertEqual(accepted_payload["total_count"], 1)
        self.assertEqual(accepted_payload["recommendations"][0]["id"], accepted.id)
        self.assertIn("# Review Recommendation Outcomes", report_text)
        self.assertIn(accepted.id, report_text)
        self.assertIn(rejected.id, report_text)
        self.assertNotIn(pending.id, report_text)
        self.assertFalse(payload["applies_review_decisions"])
        self.assertFalse(payload["writes_canonical_memory"])
        self.assertTrue(accepted_exists)
        self.assertEqual(cli_exit, 0)
        self.assertTrue(cli_payload["writes_files"])
        self.assertEqual(cli_payload["filters"]["kind"], "maintenance")
        self.assertEqual(cli_payload["total_count"], 1)
        self.assertEqual(outside_exit, 1)
        self.assertIn("report path must stay inside", outside_error.getvalue())
        self.assertEqual(canonical_exit, 1)
        self.assertIn("report path must stay under reports/", canonical_error.getvalue())
        self.assertFalse(canonical_path.exists())

    def test_mcp_review_recommendation_outcome_report_renders_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            accepted = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Accepted MCP outcome report fixture.",
                recommended_by="Unit Test LLM",
            )
            rejected = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conflict",
                recommendation="collect_evidence",
                rationale="Rejected MCP outcome report fixture.",
                recommended_by="Unit Test LLM",
            )
            pending = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="pending",
                recommendation="maintenance_follow_up",
                rationale="Pending MCP outcome report fixture.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, accepted.id, "accepted", "Unit Test", "Accepted.")
            record_review_recommendation_outcome(root, rejected.id, "rejected", "Unit Test", "Rejected.")

            result = call_tool("memory.review_recommendation_outcome_report", {}, root)
            accepted_only = call_tool(
                "memory.review_recommendation_outcome_report",
                {"outcome_status": "accepted"},
                root,
            )

        self.assertEqual(result["total_count"], 2)
        self.assertEqual(result["accepted_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertFalse(result["writes_files"])
        self.assertFalse(result["applies_review_decisions"])
        self.assertFalse(result["writes_canonical_memory"])
        self.assertIsNone(result["report_path"])
        self.assertIn("Review Recommendation Outcomes", result["markdown"])
        self.assertIn(accepted.id, result["markdown"])
        self.assertIn(rejected.id, result["markdown"])
        self.assertNotIn(pending.id, result["markdown"])
        self.assertEqual(accepted_only["total_count"], 1)
        self.assertEqual(accepted_only["recommendations"][0]["id"], accepted.id)

    def test_review_recommendation_outcome_report_escapes_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Escaped outcome report fixture.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(
                root,
                recommendation.id,
                "accepted",
                "Reviewer `quoted`",
                "Reason `quoted`\n- injected",
            )

            report_path, _payload = write_review_recommendation_outcome_report(root)
            report_text = report_path.read_text(encoding="utf-8")
            mcp_payload = call_tool("memory.review_recommendation_outcome_report", {}, root)

        for markdown in (report_text, mcp_payload["markdown"]):
            self.assertIn("outcome_reviewed_by: `` Reviewer `quoted` ``", markdown)
            self.assertIn("outcome_reason: ``Reason `quoted` - injected``", markdown)
            self.assertNotIn("\n- injected", markdown)

    def test_mcp_review_recommendation_outcome_report_secret_scans_structured_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation_dir = root / "inbox" / "review-recommendations"
            secret_like = "sk-" + "proj-" + ("e" * 26)
            (recommendation_dir / "broken-secret.md").write_text(
                "---\n"
                "id: broken-secret\n"
                "type: review-recommendation\n"
                "kind: maintenance\n"
                "target_id: weekly\n"
                "recommendation: maintenance_follow_up\n"
                f"confidence: {secret_like}\n"
                "---\n\n"
                "Malformed secret-bearing recommendation fixture.\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "payload rejected by secret scan"):
                call_tool("memory.review_recommendation_outcome_report", {}, root)

    def test_review_recommendation_outcome_report_paginates_records_and_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            for idx in range(3):
                recommendation = capture_review_recommendation(
                    root,
                    kind="maintenance",
                    target_id=f"weekly-{idx}",
                    recommendation="maintenance_follow_up",
                    rationale=f"Paginated outcome report fixture {idx}.",
                    recommended_by="Unit Test LLM",
                )
                record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            recommendation_dir = root / "inbox" / "review-recommendations"
            for idx in range(3):
                (recommendation_dir / f"broken-{idx}.md").write_text(
                    "---\n"
                    f"id: broken-{idx}\n"
                    "---\n\n"
                    "Malformed recommendation outcome report fixture.\n",
                    encoding="utf-8",
                )

            first_page_path, first_page = write_review_recommendation_outcome_report(root, limit=2)
            second_page_path, second_page = write_review_recommendation_outcome_report(
                root,
                "reports/outcome-page-2.md",
                limit=2,
                offset=2,
                invalid_offset=2,
            )
            mcp_second_page = call_tool(
                "memory.review_recommendation_outcome_report",
                {"limit": 2, "offset": 2, "invalid_offset": 2},
                root,
            )
            output = io.StringIO()
            with patch("sys.stdout", output):
                cli_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendation-outcomes",
                        "--limit",
                        "2",
                        "--offset",
                        "2",
                        "--invalid-offset",
                        "2",
                        "--json",
                    ]
                )
            cli_payload = json.loads(output.getvalue())
            second_text = second_page_path.read_text(encoding="utf-8")
            first_page_exists = first_page_path.exists()

            with self.assertRaisesRegex(ReviewError, "offset"):
                write_review_recommendation_outcome_report(root, offset=-1)
            with self.assertRaisesRegex(ReviewError, "invalid_offset"):
                write_review_recommendation_outcome_report(root, invalid_offset=-1)

        self.assertEqual(first_page["total_count"], 3)
        self.assertEqual(first_page["returned_count"], 2)
        self.assertEqual(first_page["offset"], 0)
        self.assertEqual(first_page["next_offset"], 2)
        self.assertTrue(first_page["has_more"])
        self.assertEqual(first_page["invalid_count"], 3)
        self.assertEqual(first_page["invalid_returned_count"], 2)
        self.assertEqual(first_page["invalid_next_offset"], 2)
        self.assertTrue(first_page["invalid_has_more"])
        self.assertEqual(second_page["returned_count"], 1)
        self.assertEqual(second_page["offset"], 2)
        self.assertIsNone(second_page["next_offset"])
        self.assertFalse(second_page["has_more"])
        self.assertEqual(second_page["invalid_returned_count"], 1)
        self.assertEqual(second_page["invalid_offset"], 2)
        self.assertIsNone(second_page["invalid_next_offset"])
        self.assertFalse(second_page["invalid_has_more"])
        self.assertIn("next_offset: `None`", second_text)
        self.assertEqual(mcp_second_page["returned_count"], 1)
        self.assertEqual(mcp_second_page["invalid_returned_count"], 1)
        self.assertFalse(mcp_second_page["writes_files"])
        self.assertEqual(cli_exit, 0)
        self.assertTrue(cli_payload["writes_files"])
        self.assertEqual(cli_payload["returned_count"], 1)
        self.assertEqual(cli_payload["invalid_returned_count"], 1)
        self.assertTrue(first_page_exists)

    def test_review_recommendation_archive_previews_and_moves_reviewed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            pending = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="pending",
                recommendation="maintenance_follow_up",
                rationale="Keep this recommendation pending.",
                recommended_by="Unit Test LLM",
            )
            accepted = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="accepted",
                recommendation="collect_evidence",
                rationale="Archive this accepted recommendation.",
                recommended_by="Unit Test LLM",
            )
            rejected = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="rejected",
                recommendation="dismiss_conflict",
                rationale="Archive this rejected recommendation.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, accepted.id, "accepted", "Unit Test", "Accepted.")
            record_review_recommendation_outcome(root, rejected.id, "rejected", "Unit Test", "Rejected.")

            preview = archive_review_recommendations(root)
            accepted_only = archive_review_recommendations(root, outcome_status="accepted")
            with patch("review_memory.today", return_value=date(1999, 1, 1)):
                gated = archive_review_recommendations(root, min_outcome_days=1)
            applied = archive_review_recommendations(root, apply=True)
            status_after = review_recommendations(root)
            pending_exists = (root / pending.path).exists()
            accepted_archive_exists = (root / applied.archived[0]["archive_path"]).exists() if applied.archived else False

        self.assertTrue(preview.dry_run)
        self.assertEqual(preview.eligible_count, 2)
        self.assertEqual(preview.archived_count, 0)
        self.assertFalse(preview.writes_files)
        self.assertFalse(preview.applies_review_decisions)
        self.assertFalse(preview.canonical_memory_updated)
        self.assertEqual(accepted_only.eligible_count, 1)
        self.assertEqual(accepted_only.candidates[0]["id"], accepted.id)
        self.assertEqual(gated.eligible_count, 0)
        self.assertTrue(any(item["reason"] == "outcome_too_recent" for item in gated.skipped))
        self.assertFalse(applied.dry_run)
        self.assertEqual(applied.archived_count, 2)
        self.assertTrue(applied.writes_files)
        self.assertTrue(accepted_archive_exists)
        self.assertTrue(pending_exists)
        self.assertEqual(status_after["total_count"], 1)
        self.assertEqual(status_after["pending_count"], 1)

    def test_review_recommendation_archive_cli_json_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Archive this reviewed recommendation.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            preview_output = io.StringIO()
            apply_output = io.StringIO()
            outside_error = io.StringIO()

            with patch("sys.stdout", preview_output):
                preview_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive",
                        "--json",
                    ]
                )
            with patch("sys.stdout", apply_output):
                apply_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive",
                        "--apply",
                        "--json",
                    ]
                )
            with redirect_stderr(outside_error):
                outside_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive",
                        "--archive-root",
                        str(Path(tmp) / "outside"),
                    ]
                )

            preview_payload = json.loads(preview_output.getvalue())
            apply_payload = json.loads(apply_output.getvalue())

        self.assertEqual(preview_exit, 0)
        self.assertEqual(preview_payload["eligible_count"], 1)
        self.assertTrue(preview_payload["dry_run"])
        self.assertEqual(apply_exit, 0)
        self.assertEqual(apply_payload["archived_count"], 1)
        self.assertTrue(apply_payload["archived"][0]["archive_path"].startswith("archive/review-recommendations/"))
        self.assertEqual(outside_exit, 1)
        self.assertIn("archive/review-recommendations", outside_error.getvalue())

    def test_review_recommendation_archive_rejects_symlink_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Do not archive through a symlinked archive root.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_parent = root / "archive"
            archive_parent.mkdir(parents=True, exist_ok=True)
            archive_root = archive_parent / "review-recommendations"
            outside_archive = Path(tmp) / "outside-archive"
            outside_archive.mkdir()
            if archive_root.exists() or archive_root.is_symlink():
                if archive_root.is_dir() and not archive_root.is_symlink():
                    self.skipTest("archive root already exists as a directory")
                archive_root.unlink()
            try:
                os.symlink(outside_archive, archive_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ReviewError, "must not contain symlinks"):
                archive_review_recommendations(root, apply=True)
            inbox_exists = (root / recommendation.path).exists()
            outside_files = list(outside_archive.glob("*.md"))

        self.assertTrue(inbox_exists)
        self.assertEqual(outside_files, [])

    def test_review_recommendation_archive_rejects_symlink_inbox_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Do not archive from a symlinked inbox root.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            inbox_root = root / "inbox" / "review-recommendations"
            outside_inbox = Path(tmp) / "outside-inbox"
            outside_inbox.mkdir()
            outside_file = outside_inbox / "external.md"
            outside_file.write_text((root / recommendation.path).read_text(encoding="utf-8"), encoding="utf-8")
            for path in inbox_root.glob("*"):
                path.unlink()
            inbox_root.rmdir()
            try:
                os.symlink(outside_inbox, inbox_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ReviewError, "inbox path must not contain symlinks"):
                archive_review_recommendations(root, apply=True)
            outside_exists = outside_file.exists()

        self.assertTrue(outside_exists)

    def test_review_recommendation_archive_restore_rejects_symlink_inbox_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Do not restore into a symlinked inbox root.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_result = archive_review_recommendations(root, apply=True)
            archive_path = root / archive_result.archived[0]["archive_path"]
            inbox_root = root / "inbox" / "review-recommendations"
            outside_inbox = Path(tmp) / "outside-inbox"
            outside_inbox.mkdir()
            for path in inbox_root.glob("*"):
                path.unlink()
            inbox_root.rmdir()
            try:
                os.symlink(outside_inbox, inbox_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ReviewError, "inbox path must not contain symlinks"):
                restore_archived_review_recommendation(root, recommendation.id, apply=True)
            archive_exists = archive_path.exists()
            outside_files = list(outside_inbox.glob("*.md"))

        self.assertTrue(archive_exists)
        self.assertEqual(outside_files, [])

    def test_review_recommendation_archive_status_lists_archived_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            accepted = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="accepted",
                recommendation="maintenance_follow_up",
                rationale="Accepted archive status fixture.",
                recommended_by="Unit Test LLM",
            )
            rejected = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="rejected",
                recommendation="collect_evidence",
                rationale="Rejected archive status fixture.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, accepted.id, "accepted", "Unit Test", "Accepted.")
            record_review_recommendation_outcome(root, rejected.id, "rejected", "Unit Test", "Rejected.")
            archive_review_recommendations(root, apply=True)

            status = archived_review_recommendations(root)
            maintenance_only = archived_review_recommendations(root, kind="maintenance")
            accepted_only = archived_review_recommendations(root, outcome_status="accepted")
            limited = archived_review_recommendations(root, limit=1)

        self.assertEqual(status["archive_root"], "archive/review-recommendations")
        self.assertEqual(status["total_count"], 2)
        self.assertEqual(status["returned_count"], 2)
        self.assertEqual(status["accepted_count"], 1)
        self.assertEqual(status["rejected_count"], 1)
        self.assertEqual(status["status_counts"], {"accepted": 1, "rejected": 1})
        self.assertEqual(status["kind_counts"], {"conflict": 1, "maintenance": 1})
        self.assertFalse(status["writes_files"])
        self.assertFalse(status["applies_review_decisions"])
        self.assertEqual(maintenance_only["total_count"], 1)
        self.assertEqual(maintenance_only["recommendations"][0]["id"], accepted.id)
        self.assertEqual(accepted_only["total_count"], 1)
        self.assertEqual(accepted_only["recommendations"][0]["outcome_status"], "accepted")
        self.assertEqual(limited["total_count"], 2)
        self.assertEqual(limited["returned_count"], 1)
        self.assertEqual(len(limited["recommendations"]), 1)

    def test_review_recommendation_archive_status_redacts_invalid_secret_like_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            archive_dir = root / "archive" / "review-recommendations"
            archive_dir.mkdir(parents=True, exist_ok=True)
            secret = "sk-" + "proj-" + ("a" * 40)
            (archive_dir / "broken-secret.md").write_text(
                "---\n"
                "id: broken-secret\n"
                "type: review-recommendation\n"
                "kind: maintenance\n"
                "target_id: weekly\n"
                "recommendation: maintenance_follow_up\n"
                f"confidence: {secret}\n"
                "---\n\n"
                "Malformed archived recommendation fixture.\n",
                encoding="utf-8",
            )

            status = archived_review_recommendations(root)
            with self.assertRaisesRegex(ValueError, "archive status rejected by secret scan"):
                call_tool("memory.review_recommendation_archive_status", {}, root)
            status_text = json.dumps(status, sort_keys=True)

        self.assertEqual(status["invalid_count"], 1)
        self.assertEqual(status["invalid"][0]["path"], "archive/review-recommendations/broken-secret.md")
        self.assertTrue(status["invalid"][0]["redacted"])
        self.assertIn("<redacted:", status["invalid"][0]["error"])
        self.assertNotIn(secret, status_text)

    def test_review_recommendation_archive_status_scans_recursive_partitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Archived in a date partition.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_review_recommendations(
                root,
                apply=True,
                archive_root="archive/review-recommendations/2026/06",
            )

            shallow = archived_review_recommendations(root)
            recursive = archived_review_recommendations(root, recursive=True)
            mcp_recursive = call_tool(
                "memory.review_recommendation_archive_status",
                {"recursive": True},
                root,
            )

        self.assertEqual(shallow["total_count"], 0)
        self.assertEqual(shallow["filters"]["recursive"], False)
        self.assertEqual(recursive["total_count"], 1)
        self.assertEqual(recursive["filters"]["recursive"], True)
        self.assertTrue(recursive["recommendations"][0]["path"].startswith("archive/review-recommendations/2026/06/"))
        self.assertEqual(mcp_recursive["total_count"], 1)
        self.assertFalse(mcp_recursive["writes_files"])

    def test_review_recommendation_archive_status_paginates_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            for idx in range(3):
                recommendation = capture_review_recommendation(
                    root,
                    kind="maintenance",
                    target_id=f"weekly-{idx}",
                    recommendation="maintenance_follow_up",
                    rationale=f"Paginated archive fixture {idx}.",
                    recommended_by="Unit Test LLM",
                )
                record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_review_recommendations(root, apply=True, limit=3)

            first_page = archived_review_recommendations(root, limit=2)
            second_page = archived_review_recommendations(root, limit=2, offset=2)
            mcp_second_page = call_tool(
                "memory.review_recommendation_archive_status",
                {"limit": 2, "offset": 2},
                root,
            )
            output = io.StringIO()
            with patch("sys.stdout", output):
                cli_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive-status",
                        "--limit",
                        "2",
                        "--offset",
                        "2",
                        "--json",
                    ]
                )
            cli_payload = json.loads(output.getvalue())

            with self.assertRaisesRegex(ReviewError, "offset"):
                archived_review_recommendations(root, offset=-1)

        self.assertEqual(first_page["total_count"], 3)
        self.assertEqual(first_page["returned_count"], 2)
        self.assertEqual(first_page["offset"], 0)
        self.assertEqual(first_page["next_offset"], 2)
        self.assertTrue(first_page["has_more"])
        self.assertEqual(second_page["returned_count"], 1)
        self.assertEqual(second_page["offset"], 2)
        self.assertIsNone(second_page["next_offset"])
        self.assertFalse(second_page["has_more"])
        self.assertEqual(mcp_second_page["returned_count"], 1)
        self.assertEqual(mcp_second_page["filters"]["offset"], 2)
        self.assertEqual(cli_exit, 0)
        self.assertEqual(cli_payload["returned_count"], 1)
        self.assertEqual(cli_payload["offset"], 2)

    def test_review_recommendation_archive_status_paginates_invalid_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            archive_dir = root / "archive" / "review-recommendations"
            archive_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(3):
                (archive_dir / f"broken-{idx}.md").write_text(
                    "---\n"
                    f"id: broken-{idx}\n"
                    "---\n\n"
                    "Malformed archived recommendation fixture.\n",
                    encoding="utf-8",
                )

            first_page = archived_review_recommendations(root, limit=2)
            second_page = archived_review_recommendations(root, limit=2, invalid_offset=2)
            mcp_second_page = call_tool(
                "memory.review_recommendation_archive_status",
                {"limit": 2, "invalid_offset": 2},
                root,
            )
            output = io.StringIO()
            with patch("sys.stdout", output):
                cli_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive-status",
                        "--limit",
                        "2",
                        "--invalid-offset",
                        "2",
                        "--json",
                    ]
                )
            cli_payload = json.loads(output.getvalue())

            with self.assertRaisesRegex(ReviewError, "invalid_offset"):
                archived_review_recommendations(root, invalid_offset=-1)

        self.assertEqual(first_page["total_count"], 0)
        self.assertEqual(first_page["returned_count"], 0)
        self.assertEqual(first_page["invalid_count"], 3)
        self.assertEqual(first_page["invalid_returned_count"], 2)
        self.assertEqual(first_page["invalid_offset"], 0)
        self.assertEqual(first_page["invalid_next_offset"], 2)
        self.assertTrue(first_page["invalid_has_more"])
        self.assertEqual([item["path"] for item in first_page["invalid"]], [
            "archive/review-recommendations/broken-0.md",
            "archive/review-recommendations/broken-1.md",
        ])
        self.assertEqual(second_page["invalid_returned_count"], 1)
        self.assertEqual(second_page["invalid_offset"], 2)
        self.assertIsNone(second_page["invalid_next_offset"])
        self.assertFalse(second_page["invalid_has_more"])
        self.assertEqual(mcp_second_page["invalid_returned_count"], 1)
        self.assertEqual(mcp_second_page["filters"]["invalid_offset"], 2)
        self.assertEqual(cli_exit, 0)
        self.assertEqual(cli_payload["invalid_returned_count"], 1)
        self.assertEqual(cli_payload["invalid_offset"], 2)

    def test_review_recommendation_archive_status_cli_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Accepted archive status CLI fixture.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_review_recommendations(root, apply=True)
            output = io.StringIO()
            outside_error = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive-status",
                        "--outcome-status",
                        "accepted",
                        "--json",
                    ]
                )
            with redirect_stderr(outside_error):
                outside_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive-status",
                        "--archive-root",
                        str(Path(tmp) / "outside"),
                    ]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["total_count"], 1)
        self.assertEqual(payload["recommendations"][0]["id"], recommendation.id)
        self.assertFalse(payload["writes_files"])
        self.assertEqual(outside_exit, 1)
        self.assertIn("archive/review-recommendations", outside_error.getvalue())

    def test_mcp_review_recommendation_archive_status_lists_archived_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="List this archived recommendation from MCP.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_review_recommendations(root, apply=True)

            status = call_tool(
                "memory.review_recommendation_archive_status",
                {"kind": "maintenance", "outcome_status": "accepted"},
                root,
            )
            limited = call_tool("memory.review_recommendation_archive_status", {"limit": 1}, root)
            outside_error = None
            try:
                call_tool(
                    "memory.review_recommendation_archive_status",
                    {"archive_root": str(Path(tmp) / "outside")},
                    root,
                )
            except Exception as exc:
                outside_error = str(exc)

        self.assertEqual(status["archive_root"], "archive/review-recommendations")
        self.assertEqual(status["total_count"], 1)
        self.assertEqual(status["returned_count"], 1)
        self.assertEqual(status["accepted_count"], 1)
        self.assertEqual(status["rejected_count"], 0)
        self.assertEqual(status["kind_counts"], {"maintenance": 1})
        self.assertEqual(status["recommendations"][0]["id"], recommendation.id)
        self.assertFalse(status["writes_files"])
        self.assertFalse(status["applies_review_decisions"])
        self.assertFalse(status["writes_canonical_memory"])
        self.assertEqual(limited["returned_count"], 1)
        self.assertIsNotNone(outside_error)
        self.assertIn("archive/review-recommendations", outside_error or "")

    def test_review_recommendation_archive_restore_previews_and_moves_one_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Restore this reviewed recommendation.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_result = archive_review_recommendations(root, apply=True)
            archive_path = root / archive_result.archived[0]["archive_path"]

            preview = restore_archived_review_recommendation(root, recommendation.id)
            status_before_apply = review_recommendations(root)
            applied = restore_archived_review_recommendation(root, recommendation.id, apply=True)
            status_after_apply = review_recommendations(root)
            archive_status_after_apply = archived_review_recommendations(root)
            inbox_path = root / applied.restored[0]["restore_path"]
            inbox_exists = inbox_path.exists()
            archive_exists_after_apply = archive_path.exists()

        self.assertTrue(preview.dry_run)
        self.assertEqual(preview.requested_id, recommendation.id)
        self.assertEqual(len(preview.candidates), 1)
        self.assertEqual(preview.restored_count, 0)
        self.assertFalse(preview.writes_files)
        self.assertFalse(preview.applies_review_decisions)
        self.assertFalse(preview.canonical_memory_updated)
        self.assertEqual(status_before_apply["total_count"], 0)
        self.assertFalse(applied.dry_run)
        self.assertEqual(applied.restored_count, 1)
        self.assertTrue(applied.writes_files)
        self.assertTrue(inbox_exists)
        self.assertFalse(archive_exists_after_apply)
        self.assertEqual(status_after_apply["total_count"], 1)
        self.assertEqual(status_after_apply["accepted_count"], 1)
        self.assertEqual(archive_status_after_apply["total_count"], 0)

    def test_review_recommendation_archive_restore_scans_recursive_partitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Restore this partitioned archived recommendation.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_result = archive_review_recommendations(
                root,
                apply=True,
                archive_root="archive/review-recommendations/2026/06",
            )
            archive_path = root / archive_result.archived[0]["archive_path"]

            shallow = restore_archived_review_recommendation(root, recommendation.id)
            recursive_preview = restore_archived_review_recommendation(root, recommendation.id, recursive=True)
            mcp_preview = call_tool(
                "memory.review_recommendation_archive_restore_preview",
                {"id": recommendation.id, "recursive": True},
                root,
            )
            recursive_apply = restore_archived_review_recommendation(root, recommendation.id, apply=True, recursive=True)
            inbox_exists = (root / recursive_apply.restored[0]["restore_path"]).exists()
            archive_exists_after_apply = archive_path.exists()

        self.assertEqual(shallow.skipped[0]["reason"], "not_found")
        self.assertFalse(shallow.recursive)
        self.assertTrue(recursive_preview.recursive)
        self.assertEqual(len(recursive_preview.candidates), 1)
        self.assertTrue(recursive_preview.candidates[0]["path"].startswith("archive/review-recommendations/2026/06/"))
        self.assertTrue(mcp_preview["recursive"])
        self.assertEqual(len(mcp_preview["candidates"]), 1)
        self.assertFalse(mcp_preview["writes_files"])
        self.assertEqual(recursive_apply.restored_count, 1)
        self.assertTrue(inbox_exists)
        self.assertFalse(archive_exists_after_apply)

    def test_review_recommendation_archive_restore_cli_json_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Restore this archived recommendation from the CLI.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_result = archive_review_recommendations(root, apply=True)
            archived_text = (root / archive_result.archived[0]["archive_path"]).read_text(encoding="utf-8")
            (root / recommendation.path).parent.mkdir(parents=True, exist_ok=True)
            (root / recommendation.path).write_text(archived_text, encoding="utf-8")
            blocked_output = io.StringIO()
            outside_error = io.StringIO()
            missing_output = io.StringIO()

            with patch("sys.stdout", blocked_output):
                blocked_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive-restore",
                        "--id",
                        recommendation.id,
                        "--apply",
                        "--json",
                    ]
                )
            with redirect_stderr(outside_error):
                outside_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive-restore",
                        "--id",
                        recommendation.id,
                        "--archive-root",
                        str(Path(tmp) / "outside"),
                    ]
                )
            with patch("sys.stdout", missing_output):
                missing_exit = review_main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "recommendations-archive-restore",
                        "--id",
                        "rec_missing",
                        "--json",
                    ]
                )

            blocked_payload = json.loads(blocked_output.getvalue())
            missing_payload = json.loads(missing_output.getvalue())

        self.assertEqual(blocked_exit, 0)
        self.assertEqual(blocked_payload["restored_count"], 0)
        self.assertTrue(any(item["reason"] == "restore_path_exists" for item in blocked_payload["skipped"]))
        self.assertTrue(blocked_payload["writes_files"])
        self.assertEqual(outside_exit, 1)
        self.assertIn("archive/review-recommendations", outside_error.getvalue())
        self.assertEqual(missing_exit, 0)
        self.assertEqual(missing_payload["skipped"][0]["reason"], "not_found")

    def test_review_recommendation_archive_restore_rejects_symlink_entries_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            archive_dir = root / "archive" / "review-recommendations"
            archive_dir.mkdir(parents=True, exist_ok=True)
            secret = "sk-" + "proj-" + ("s" * 40)
            outside = Path(tmp) / "outside-secret.md"
            outside.write_text(
                "---\n"
                "id: rec_symlink_escape\n"
                "type: review-recommendation\n"
                "kind: maintenance\n"
                "target_id: weekly\n"
                "recommendation: maintenance_follow_up\n"
                f"confidence: {secret}\n"
                "---\n\n"
                "This external file must not be read through the archive symlink.\n",
                encoding="utf-8",
            )
            link = archive_dir / "linked-secret.md"
            try:
                os.symlink(outside, link)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            status = archived_review_recommendations(root)
            preview = restore_archived_review_recommendation(root, "rec_symlink_escape")
            status_text = json.dumps(status, sort_keys=True)
            preview_text = json.dumps(preview.__dict__, sort_keys=True)

        self.assertEqual(status["total_count"], 0)
        self.assertEqual(status["invalid_count"], 1)
        self.assertIn("symlink", status["invalid"][0]["error"])
        self.assertEqual(preview.malformed_count, 0)
        self.assertEqual(preview.skipped[0]["reason"], "symlink_archive_entry")
        self.assertNotIn(secret, status_text)
        self.assertNotIn(secret, preview_text)

    def test_mcp_review_recommendation_archive_restore_preview_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Preview restoring this archived recommendation from MCP.",
                recommended_by="Unit Test LLM",
            )
            record_review_recommendation_outcome(root, recommendation.id, "accepted", "Unit Test", "Accepted.")
            archive_result = archive_review_recommendations(root, apply=True)
            archive_path = root / archive_result.archived[0]["archive_path"]
            inbox_path = root / recommendation.path

            preview = call_tool(
                "memory.review_recommendation_archive_restore_preview",
                {"id": recommendation.id},
                root,
            )
            outside_error = None
            try:
                call_tool(
                    "memory.review_recommendation_archive_restore_preview",
                    {"id": recommendation.id, "archive_root": str(Path(tmp) / "outside")},
                    root,
                )
            except Exception as exc:
                outside_error = str(exc)
            archive_exists_after_preview = archive_path.exists()
            inbox_exists_after_preview = inbox_path.exists()

        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview["requested_id"], recommendation.id)
        self.assertEqual(len(preview["candidates"]), 1)
        self.assertEqual(preview["restored_count"], 0)
        self.assertFalse(preview["writes_files"])
        self.assertFalse(preview["applies_review_decisions"])
        self.assertFalse(preview["writes_canonical_memory"])
        self.assertFalse(preview["canonical_memory_updated"])
        self.assertTrue(archive_exists_after_preview)
        self.assertFalse(inbox_exists_after_preview)
        self.assertIsNotNone(outside_error)
        self.assertIn("archive/review-recommendations", outside_error or "")

    def test_mcp_review_recommendation_archive_restore_preview_secret_scans_malformed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            archive_root = root / "archive" / "review-recommendations"
            archive_root.mkdir(parents=True, exist_ok=True)
            secret_like = "sk-" + "proj-" + ("f" * 26)
            (archive_root / "broken-secret.md").write_text(
                "---\n"
                "id: broken-secret\n"
                "type: review-recommendation\n"
                "kind: maintenance\n"
                "target_id: weekly\n"
                "recommendation: maintenance_follow_up\n"
                f"confidence: {secret_like}\n"
                "---\n\n"
                "Malformed secret-bearing archived recommendation fixture.\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "restore preview rejected by secret scan"):
                call_tool(
                    "memory.review_recommendation_archive_restore_preview",
                    {"id": "not-present"},
                    root,
                )

    def test_review_recommendation_outcome_rejects_secret_like_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            recommendation = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="weekly",
                recommendation="maintenance_follow_up",
                rationale="Review weekly maintenance output.",
                recommended_by="Unit Test LLM",
            )
            secret = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz"

            with self.assertRaisesRegex(ReviewError, "reason contains secret-like content"):
                record_review_recommendation_outcome(
                    root,
                    recommendation.id,
                    "accepted",
                    reviewer="Unit Test",
                    reason=secret,
                )
            status = review_recommendations(root)

        self.assertEqual(status["pending_count"], 1)
        self.assertEqual(status["accepted_count"], 0)

    def test_mcp_conflict_keep_links_review_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            configure_review_mode(root, "balanced", reviewer="Unit Test")
            conflict = conflict_reviews(root)[0]
            recommendation = call_tool(
                "memory.review_recommendation",
                {
                    "kind": "conflict",
                    "target_id": conflict.id,
                    "recommendation": "keep_memory",
                    "rationale": "Keep the first memory after human review.",
                    "recommended_by": "Unit Test LLM",
                },
                root,
            )

            receipt = call_tool(
                "memory.conflict_keep",
                {
                    "id": conflict.id,
                    "keep": "mem_conflict_one",
                    "reviewer": "Unit Test",
                    "recommendation_id": recommendation["id"],
                },
                root,
            )

        self.assertEqual(receipt["recommendation_id"], recommendation["id"])
        self.assertEqual(receipt["recommendation_path"], recommendation["path"])
        self.assertEqual(receipt["recommendation_action"], "keep_memory")
        self.assertFalse(receipt["recommendation_policy_violation"])

    def test_mcp_conflict_keep_rejects_memory_outside_conflict_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            conflict = conflict_reviews(root)[0]

            with self.assertRaisesRegex(Exception, "keep memory id must belong to conflict"):
                call_tool(
                    "memory.conflict_keep",
                    {"id": conflict.id, "keep": "mem_unrelated", "reviewer": "Unit Test"},
                    root,
                )

            state_exists = review_state_path(root).exists()

        self.assertFalse(state_exists)

    def test_review_policy_config_normalizes_policy_defaults_and_custom_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[review]",
                        'mode = "balanced"',
                        "",
                        "[false_positives]",
                        "enabled = false",
                        'triage_policy = "llm_suggests"',
                        "allow_ignore_file = true",
                        'ignore_file = "review/state.toml"',
                        "review_after_days = 14",
                        "",
                        "[conflicts]",
                        "enabled = true",
                        "scan_on_validate = false",
                        "scan_on_consolidate = true",
                        'resolution_policy = "llm_preselects"',
                        "llm_preselect_min_confidence = 0.9",
                        'human_required_severities = ["critical"]',
                        'llm_auto_deny_categories = ["restricted", "durable"]',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            policy = review_policy_config(root)
            modes = review_modes(root)
            plan = review_plan(root, "conflict")
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[false_positives]",
                        'triage_policy = "robot_only"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ReviewError, "unknown false-positive triage policy"):
                review_policy_config(root)

        self.assertFalse(policy["false_positives"]["enabled"])
        self.assertEqual(policy["false_positives"]["triage_policy"], "llm_suggests")
        self.assertEqual(policy["false_positives"]["ignore_file"], "review/state.toml")
        self.assertEqual(policy["false_positives"]["review_after_days"], 14)
        self.assertFalse(policy["conflicts"]["scan_on_validate"])
        self.assertEqual(policy["conflicts"]["resolution_policy"], "llm_preselects")
        self.assertEqual(policy["conflicts"]["llm_preselect_min_confidence"], 0.9)
        self.assertEqual(policy["conflicts"]["human_required_severities"], ["critical"])
        self.assertEqual(policy["conflicts"]["llm_auto_deny_categories"], ["restricted", "durable"])
        self.assertEqual(modes["policy"], policy)
        self.assertEqual(plan.policy, policy)

    def test_disabled_false_positive_review_returns_empty_reads_and_rejects_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[false_positives]", "enabled = false", ""]),
                encoding="utf-8",
            )
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")

            reviews = false_positive_reviews(root)
            report_path, report_reviews = write_false_positive_report(root)
            report_text = report_path.read_text(encoding="utf-8")
            stale = stale_false_positive_suppressions(root)
            stale_report_path, stale_report_reviews = write_stale_false_positive_report(root)
            stale_report_text = stale_report_path.read_text(encoding="utf-8")
            mcp_result = call_tool("memory.review_false_positives", {}, root)
            stale_mcp_result = call_tool("memory.review_stale_false_positives", {}, root)
            with self.assertRaisesRegex(ReviewError, "false-positive review is disabled"):
                ignore_false_positive(root, "fp_disabled", "Reviewed fixture redaction.", "Unit Test")
            with self.assertRaisesRegex(ReviewError, "false-positive review is disabled"):
                unignore_false_positive(root, "fp_disabled", "Unit Test")

        self.assertEqual(reviews, [])
        self.assertEqual(report_reviews, [])
        self.assertIn("_No suspected secret findings._", report_text)
        self.assertIn("## Review Policy", report_text)
        self.assertIn("- enabled: `false`", report_text)
        self.assertIn("- triage_policy: `human_only`", report_text)
        self.assertEqual(stale, [])
        self.assertEqual(stale_report_reviews, [])
        self.assertIn("## Review Policy", stale_report_text)
        self.assertIn("- enabled: `false`", stale_report_text)
        self.assertIn("- review_after_days: `90`", stale_report_text)
        self.assertFalse(mcp_result["enabled"])
        self.assertEqual(mcp_result["policy"]["triage_policy"], "human_only")
        self.assertEqual(mcp_result["returned_count"], 0)
        self.assertEqual(mcp_result["findings"], [])
        self.assertFalse(stale_mcp_result["enabled"])
        self.assertEqual(stale_mcp_result["stale_count"], 0)

    def test_disabled_conflict_review_returns_empty_reads_and_rejects_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(["[conflicts]", "enabled = false", ""]),
                encoding="utf-8",
            )
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")

            conflicts = conflict_reviews(root)
            report_path, report_conflicts = write_conflict_report(root)
            report_text = report_path.read_text(encoding="utf-8")
            mcp_result = call_tool("memory.review_conflicts", {}, root)
            with self.assertRaisesRegex(ReviewError, "conflict review is disabled"):
                dismiss_conflict(root, "conf_disabled", "Intentional duplicate fixture.", "Unit Test")
            with self.assertRaisesRegex(ReviewError, "conflict review is disabled"):
                resolve_conflict(root, "conf_disabled", "Unit Test", keep="mem_conflict_one")

        self.assertEqual(conflicts, [])
        self.assertEqual(report_conflicts, [])
        self.assertIn("_No conflicts detected._", report_text)
        self.assertIn("## Review Policy", report_text)
        self.assertIn("- enabled: `false`", report_text)
        self.assertIn("- resolution_policy: `human_only`", report_text)
        self.assertFalse(mcp_result["enabled"])
        self.assertEqual(mcp_result["policy"]["resolution_policy"], "human_only")
        self.assertEqual(mcp_result["conflicts"], [])

    def test_index_builds_and_search_returns_known_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/durable/codex.md", memory_id="mem_codex_test")
            db_path, count = rebuild_index(root, root / "indexes" / "memory.sqlite")
            results = search("codex", root, db_path=db_path)
            hyphen_results = search("ai-dememory", root, db_path=db_path)

        self.assertEqual(count, 1)
        self.assertEqual(results[0].id, "mem_codex_test")
        self.assertEqual(hyphen_results[0].id, "mem_codex_test")
        self.assertIn("codex", results[0].snippet.lower())
        self.assertIn("fts", results[0].why)
        self.assertIn("lifecycle_strength", results[0].why)
        self.assertIn("codex", results[0].why["matched_terms"])
        self.assertIn("raw_content", results[0].why["matched_fields"])
        self.assertIn("codex", results[0].why["matched_tags"])
        self.assertIn("codex", results[0].why["matched_aliases"])

    def test_context_assembly_respects_budget_and_excludes_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            write_memory(
                root,
                "memories/tools/sensitive.md",
                memory_id="mem_sensitive",
                sensitivity="sensitive",
                body="Sensitive phrase must not enter default context.",
            )
            snapshot(root, "Current work", "Working note about ai dememory.", task="unit-test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            context = assemble_context(root, "codex", budget_tokens=700)

        self.assertLessEqual(context["estimated_tokens"], 700)
        self.assertEqual(context["query_source"], "explicit")
        self.assertTrue(any(item["id"] == "mem_codex_test" for item in context["items"]))
        self.assertIn("matched_terms", context["items"][0]["why"])
        self.assertIn("Working Memory", context["text"])
        self.assertNotIn("Sensitive phrase", context["text"])

    def test_context_cli_auto_uses_working_memory_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/tools/scheduler.md",
                memory_id="mem_scheduler_test",
                body="Scheduler setup notes for ai-dememory maintenance.",
            )
            snapshot(root, "Scheduler work", "Need scheduler setup notes.", task="scheduler")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = context_main(["--root", str(root), "--auto", "--budget", "700", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["query_source"], "working_memory")
        self.assertIn("Scheduler work", payload["query"])
        self.assertTrue(any(item["id"] == "mem_scheduler_test" for item in payload["items"]))

    def test_context_cli_uses_config_defaults_and_allows_flag_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            snapshot(root, "Current work", "Working note about ai dememory.", task="unit-test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[context]",
                        "default_budget_tokens = 650",
                        "include_working_memory = false",
                        "explain_results = true",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            defaults = context_defaults(root)
            configured_output = io.StringIO()
            with redirect_stdout(configured_output):
                configured_exit = context_main(["--root", str(root), "codex", "--json"])

            override_output = io.StringIO()
            with redirect_stdout(override_output):
                override_exit = context_main(
                    [
                        "--root",
                        str(root),
                        "codex",
                        "--budget",
                        "700",
                        "--include-working-memory",
                        "--no-why",
                        "--json",
                    ]
                )

        configured = json.loads(configured_output.getvalue())
        override = json.loads(override_output.getvalue())
        self.assertEqual(configured_exit, 0)
        self.assertEqual(defaults.budget_tokens, 650)
        self.assertFalse(defaults.include_working_memory)
        self.assertTrue(defaults.explain_results)
        self.assertEqual(configured["budget_tokens"], 650)
        self.assertTrue(configured["explain_results"])
        self.assertIn("Why selected:", configured["text"])
        self.assertNotIn("Working Memory", configured["text"])
        self.assertEqual(override_exit, 0)
        self.assertEqual(override["budget_tokens"], 700)
        self.assertFalse(override["explain_results"])
        self.assertNotIn("Why selected:", override["text"])
        self.assertIn("Working Memory", override["text"])

    def test_mcp_context_uses_config_defaults_and_allows_argument_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            snapshot(root, "Current work", "Working note about ai dememory.", task="unit-test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[context]",
                        "default_budget_tokens = 650",
                        "include_working_memory = false",
                        "explain_results = true",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            configured = call_tool("memory.context", {"query": "codex"}, root)
            override = call_tool(
                "memory.context",
                {
                    "query": "codex",
                    "budget_tokens": 700,
                    "include_working_memory": True,
                    "explain_results": False,
                },
                root,
            )

        self.assertEqual(configured["budget_tokens"], 650)
        self.assertTrue(configured["explain_results"])
        self.assertIn("Why selected:", configured["text"])
        self.assertNotIn("Working Memory", configured["text"])
        self.assertEqual(override["budget_tokens"], 700)
        self.assertFalse(override["explain_results"])
        self.assertNotIn("Why selected:", override["text"])
        self.assertIn("Working Memory", override["text"])

    def test_eval_recall_passes_and_fails_expected_rankings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "known",
                            "query": "codex",
                            "expected_ids": ["mem_codex_test"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        },
                        {
                            "id": "missing",
                            "query": "codex",
                            "expected_ids": ["mem_missing"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        },
                    ]
                ),
                encoding="utf-8",
            )

            results = evaluate(root, fixtures_path)

        self.assertTrue(results[0].passed)
        self.assertFalse(results[1].passed)
        self.assertEqual(results[1].missing_ids, ["mem_missing"])

    def test_vector_gate_not_justified_when_recall_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "known",
                            "query": "codex",
                            "expected_ids": ["mem_codex_test"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            readiness = evaluate_vector_readiness(root, fixtures_path)

        self.assertEqual(readiness.decision, "not_justified")
        self.assertEqual(readiness.recall["recall"], 1.0)

    def test_vector_gate_marks_experiment_eligible_after_measured_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "missing-one",
                            "query": "codex",
                            "expected_ids": ["mem_missing_one"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        },
                        {
                            "id": "missing-two",
                            "query": "codex",
                            "expected_ids": ["mem_missing_two"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        },
                    ]
                ),
                encoding="utf-8",
            )

            readiness = evaluate_vector_readiness(root, fixtures_path, recall_threshold=0.85, min_failed_cases=2)

        self.assertEqual(readiness.decision, "eligible_for_vector_experiment")
        self.assertEqual(readiness.failed_case_ids, ["missing-one", "missing-two"])

    def test_cli_vector_status_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "known",
                            "query": "codex",
                            "expected_ids": ["mem_codex_test"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = cli_main(["--root", str(root), "vector", "status", "--write-report", "--json"])
            result = json.loads(output.getvalue())
            report_text = (root / result["report_path"]).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["decision"], "not_justified")
        self.assertEqual(result["report_path"], "reports/vector-readiness.md")
        self.assertIn("Vector Readiness", report_text)

    def test_cli_vector_status_writes_report_to_custom_in_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "known",
                            "query": "codex",
                            "expected_ids": ["mem_codex_test"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = cli_main(
                    [
                        "--root",
                        str(root),
                        "vector",
                        "status",
                        "--write-report",
                        "--report-path",
                        "reports/custom-vector-readiness.md",
                        "--json",
                    ]
                )
            result = json.loads(output.getvalue())
            report_text = (root / result["report_path"]).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["report_path"], "reports/custom-vector-readiness.md")
        self.assertIn("Vector Readiness", report_text)

    def test_cli_vector_status_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "known",
                            "query": "codex",
                            "expected_ids": ["mem_codex_test"],
                            "min_rank": 1,
                            "include_sensitive": False,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            outside = Path(tmp) / "vector-readiness.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = cli_main(
                    [
                        "--root",
                        str(root),
                        "vector",
                        "status",
                        "--write-report",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_capture_miss_writes_feedback_and_rejects_secret_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = capture_miss(
                root,
                "missing codex policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
            )
            secret = "sk-" + "proj-" + ("d" * 40)
            with self.assertRaises(ValueError):
                capture_miss(root, secret, "Expected result was absent.", expected_id="mem_policy")
            text = path.read_text(encoding="utf-8")

        self.assertTrue(path.as_posix().endswith(".md"))
        self.assertIn("inbox/recall-feedback", path.as_posix())
        self.assertIn("missing codex policy", text)

    def test_capture_miss_dry_run_renders_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = capture_miss_main(
                    [
                        "--root",
                        str(root),
                        "--query",
                        "missing codex policy",
                        "--reason",
                        "Expected policy memory was absent.",
                        "--expected-id",
                        "mem_policy",
                        "--dry-run",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

            self.assertFalse((root / "inbox" / "recall-feedback").exists())

        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["writes_files"])
        self.assertIn("Recall Miss: missing codex policy", payload["markdown"])
        self.assertIn("expected_id: \"mem_policy\"", payload["markdown"])

    def test_capture_miss_json_reports_written_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = capture_miss_main(
                    [
                        "--root",
                        str(root),
                        "--query",
                        "missing codex policy",
                        "--reason",
                        "Expected policy memory was absent.",
                        "--expected-id",
                        "mem_policy",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            path = root / payload["path"]
            self.assertTrue(path.exists())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["writes_files"])
        self.assertTrue(payload["path"].startswith("inbox/recall-feedback/"))

    def test_capture_miss_rejects_symlink_feedback_dir_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            inbox = root / "inbox"
            inbox.mkdir()
            outside_feedback = Path(outside_tmp) / "external-feedback"
            outside_feedback.mkdir()
            try:
                os.symlink(outside_feedback, inbox / "recall-feedback", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                capture_miss(
                    root,
                    "missing codex policy",
                    "Expected policy memory was absent.",
                    expected_id="mem_policy",
                )

            outside_files = list(outside_feedback.iterdir())

        self.assertEqual(outside_files, [])

    def test_render_miss_text_rejects_secret_like_fields(self) -> None:
        secret = "sk-" + "proj-" + ("q" * 40)

        with self.assertRaisesRegex(ValueError, "secret scan"):
            render_miss_text(secret, "Expected result was absent.", expected_id="mem_policy")

    def test_recall_miss_candidate_reports_missing_expected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/tools/policy.md",
                memory_id="mem_policy",
                body="This policy memory intentionally does not contain the searched wording.",
            )
            rebuild_index(root)

            result = recall_miss_candidate(
                root,
                "unmatched scheduler installation phrase",
                expected_id="mem_policy",
                min_rank=3,
                limit=3,
            )
            inbox_exists = (root / "inbox" / "recall-feedback").exists()

        self.assertTrue(result.candidate_miss)
        self.assertIsNone(result.expected_rank)
        self.assertFalse(result.writes_files)
        self.assertIn("--dry-run", result.capture_dry_run_command)
        self.assertFalse(inbox_exists)

    def test_recall_miss_candidate_cli_reports_non_miss_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/policy.md", memory_id="mem_policy")
            rebuild_index(root)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "check-miss",
                        "--query",
                        "ai dememory search",
                        "--expected-path",
                        "memories/tools/policy.md",
                        "--min-rank",
                        "5",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["candidate_miss"])
        self.assertEqual(payload["expected_id"], "mem_policy")
        self.assertIsInstance(payload["expected_rank"], int)
        self.assertFalse(payload["writes_files"])
        self.assertEqual(payload["capture_dry_run_command"], [])
        self.assertEqual(payload["capture_write_command"], [])
        self.assertIn("top_results", payload)

    def test_recall_fixture_promotion_appends_reviewed_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/policy.md", memory_id="mem_policy")
            rebuild_index(root)
            miss = capture_miss(
                root,
                "missing codex policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
            )

            result = promote_miss_to_fixture(
                root,
                miss,
                "Unit Test",
                fixture_id="recall_policy",
                notes="Reviewed weekly miss.",
                min_rank=3,
            )
            fixtures = load_fixtures(root / result.fixtures_path)
            miss_data = load_recall_miss(miss)

        self.assertEqual(result.fixtures_path, "quality/recall-fixtures.json")
        self.assertEqual(fixtures[0]["id"], "recall_policy")
        self.assertEqual(fixtures[0]["expected_ids"], ["mem_policy"])
        self.assertEqual(fixtures[0]["min_rank"], 3)
        self.assertEqual(fixtures[0]["reviewed_by"], "Unit Test")
        self.assertIn("inbox/recall-feedback", fixtures[0]["source_ref"])
        self.assertEqual(miss_data["status"], "promoted")
        self.assertEqual(miss_data["promoted_fixture_id"], "recall_policy")
        self.assertEqual(miss_data["reviewed_by"], "Unit Test")

    def test_recall_fixture_promotion_resolves_expected_path_and_rejects_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/policy.md", memory_id="mem_policy")
            rebuild_index(root)
            miss = capture_miss(
                root,
                "missing codex policy",
                "Expected policy memory was absent.",
                expected_path="memories/tools/policy.md",
            )
            duplicate_miss = capture_miss(
                root,
                "ai dememory policy duplicate",
                "Expected policy memory was absent.",
                expected_path="memories/tools/policy.md",
            )

            promote_miss_to_fixture(root, miss, "Unit Test", fixture_id="recall_policy")
            with self.assertRaisesRegex(ValueError, "already resolved"):
                promote_miss_to_fixture(root, miss, "Unit Test", fixture_id="recall_policy")
            with self.assertRaisesRegex(ValueError, "already exists"):
                promote_miss_to_fixture(root, duplicate_miss, "Unit Test", fixture_id="recall_policy")
            fixtures = load_fixtures(root / "quality" / "recall-fixtures.json")
            plan = recall_fixture_review_plan(root)

        self.assertEqual(fixtures[0]["expected_ids"], ["mem_policy"])
        self.assertEqual(plan.pending_count, 1)

    def test_recall_fixture_promotion_rejects_secret_like_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/policy.md", memory_id="mem_policy")
            miss = capture_miss(
                root,
                "missing codex policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
            )
            secret = "sk-" + "proj-" + ("e" * 40)

            with self.assertRaisesRegex(ValueError, "secret scan"):
                promote_miss_to_fixture(root, miss, "Unit Test", notes=f"Do not store {secret}")

            self.assertFalse((root / "quality" / "recall-fixtures.json").exists())

    def test_recall_fixture_promotion_rejects_failing_fixture_and_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/tools/policy.md",
                memory_id="mem_policy",
                body="This policy memory intentionally lacks the reviewed miss wording.",
            )
            rebuild_index(root)
            miss = capture_miss(
                root,
                "unmatched scheduler installation phrase",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
            )

            with self.assertRaisesRegex(ValueError, "does not pass"):
                promote_miss_to_fixture(root, miss, "Unit Test", fixture_id="recall_policy")

            self.assertFalse((root / "quality" / "recall-fixtures.json").exists())
            self.assertEqual(load_recall_miss(miss)["status"], "proposed")

    def test_recall_miss_review_closes_pending_miss_without_fixture_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            miss = capture_miss(
                root,
                "missing codex policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
            )

            result = review_recall_miss(
                root,
                miss,
                "rejected",
                "Unit Test",
                "Expected memory was obsolete.",
            )
            miss_data = load_recall_miss(miss)
            plan = recall_fixture_review_plan(root)

        self.assertEqual(result.path, repo_relative_path(miss, root))
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reviewed_by, "Unit Test")
        self.assertEqual(result.reason, "Expected memory was obsolete.")
        self.assertFalse(result.fixture_updated)
        self.assertFalse(result.canonical_memory_updated)
        self.assertEqual(miss_data["status"], "rejected")
        self.assertEqual(miss_data["reviewed_by"], "Unit Test")
        self.assertEqual(miss_data["review_reason"], "Expected memory was obsolete.")
        self.assertFalse((root / "quality" / "recall-fixtures.json").exists())
        self.assertEqual(plan.pending_count, 0)
        self.assertEqual(plan.resolved_count, 1)
        self.assertEqual(plan.recent_resolved_misses[0].path, repo_relative_path(miss, root))
        self.assertEqual(plan.recent_resolved_misses[0].status, "rejected")
        self.assertEqual(plan.recent_resolved_misses[0].review_reason, "Expected memory was obsolete.")

    def test_recall_miss_review_rejects_secret_reason_and_resolved_miss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            miss = capture_miss(
                root,
                "missing codex policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
            )
            secret = "sk-" + "proj-" + ("g" * 40)

            with self.assertRaisesRegex(ValueError, "secret scan"):
                review_recall_miss(root, miss, "dismissed", "Unit Test", f"contains {secret}")

            review_recall_miss(root, miss, "dismissed", "Unit Test", "No longer reproducible.")
            with self.assertRaisesRegex(ValueError, "already resolved"):
                review_recall_miss(root, miss, "rejected", "Unit Test", "Duplicate decision.")

            miss_data = load_recall_miss(miss)

        self.assertEqual(miss_data["status"], "dismissed")
        self.assertEqual(miss_data["review_reason"], "No longer reproducible.")

    def test_recall_miss_mutations_reject_symlink_feedback_dir_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            inbox = root / "inbox"
            inbox.mkdir()
            outside_feedback = Path(outside_tmp) / "external-feedback"
            outside_feedback.mkdir()
            external_miss = outside_feedback / "external.md"
            external_miss.write_text(
                "---\n"
                "type: recall-miss\n"
                "query: external secret query must not be mutated\n"
                "expected_id: mem_external\n"
                "status: proposed\n"
                "---\n",
                encoding="utf-8",
            )
            try:
                os.symlink(outside_feedback, inbox / "recall-feedback", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            miss_path = "inbox/recall-feedback/external.md"

            with self.assertRaisesRegex(ValueError, "symlink"):
                review_recall_miss(root, miss_path, "rejected", "Unit Test", "Reject redirected writes.")
            with self.assertRaisesRegex(ValueError, "symlink"):
                promote_miss_to_fixture(root, miss_path, "Unit Test", fixture_id="recall_external")
            contents = external_miss.read_text(encoding="utf-8")

        self.assertNotIn("reviewed_by", contents)
        self.assertNotIn("promoted_fixture_id", contents)
        self.assertFalse((root / "quality" / "recall-fixtures.json").exists())

    def test_recall_review_plan_limits_recent_resolved_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            first = capture_miss(root, "first missing policy", "Expected policy was absent.", expected_id="mem_policy")
            second = capture_miss(root, "second missing policy", "Expected policy was absent.", expected_id="mem_policy")

            review_recall_miss(root, first, "rejected", "Unit Test", "Obsolete.")
            review_recall_miss(root, second, "dismissed", "Unit Test", "No longer reproducible.")
            plan = recall_fixture_review_plan(root, resolved_limit=1)

        self.assertEqual(plan.resolved_count, 2)
        self.assertEqual(len(plan.recent_resolved_misses), 1)
        self.assertEqual(plan.recent_resolved_misses[0].status, "dismissed")

    def test_recall_fixture_status_reports_seed_only_fixtures_as_needing_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "recall_seed",
                            "query": "seed memory",
                            "expected_ids": ["mem_seed"],
                            "min_rank": 3,
                            "include_sensitive": False,
                            "created_at": "2026-06-17",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            status = recall_fixture_freshness(root, today=date(2026, 6, 19))
            with redirect_stdout(io.StringIO()):
                exit_code = recall_fixtures_main(["--root", str(root), "status", "--strict"])

        self.assertEqual(status.status, "needs_reviewed_promotion")
        self.assertEqual(status.reviewed_promotions, 0)
        self.assertTrue(status.stale)
        self.assertEqual(exit_code, 1)

    def test_recall_fixture_status_accepts_recent_reviewed_promotion(self) -> None:
        today = date.today()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            today = datetime.now(timezone.utc).date()
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "recall_reviewed",
                            "query": "reviewed memory",
                            "expected_ids": ["mem_reviewed"],
                            "min_rank": 3,
                            "include_sensitive": False,
                            "created_at": today.isoformat(),
                            "reviewed_by": "Unit Test",
                            "reviewed_at": today.isoformat(),
                        }
                    ]
                ),
                encoding="utf-8",
            )

            status = recall_fixture_freshness(root, max_age_days=14, today=today)
            with redirect_stdout(io.StringIO()):
                exit_code = recall_fixtures_main(["--root", str(root), "status", "--strict", "--max-age-days", "14"])

        self.assertEqual(status.status, "fresh")
        self.assertEqual(status.reviewed_promotions, 1)
        self.assertFalse(status.stale)
        self.assertEqual(exit_code, 0)

    def test_recall_fixture_review_plan_lists_pending_and_invalid_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "recall_seed",
                            "query": "seed query",
                            "expected_ids": ["mem_seed"],
                            "min_rank": 3,
                            "include_sensitive": False,
                            "notes": "Seed.",
                            "source_ref": "seed",
                            "created_at": "2026-06-17",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            capture_miss(root, "missing codex policy", "Expected policy was absent.", expected_id="mem_policy")
            bad = root / "inbox" / "recall-feedback" / "bad.md"
            bad.write_text("---\ntype: note\n---\n", encoding="utf-8")

            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))

        self.assertEqual(plan.status, "pending_review")
        self.assertEqual(plan.pending_count, 1)
        self.assertEqual(plan.invalid_count, 1)
        self.assertEqual(plan.resolved_count, 0)
        self.assertEqual(plan.pending_misses[0].query, "missing codex policy")
        self.assertEqual(
            plan.candidate_check_command[:3],
            ["ai-dememory", "recall-fixtures", "check-miss"],
        )
        self.assertIn("promote-miss", "\n".join(plan.next_actions))

    def test_recall_fixture_review_plan_skips_symlink_miss_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            feedback = root / "inbox" / "recall-feedback"
            feedback.mkdir(parents=True)
            outside = Path(outside_tmp) / "external.md"
            outside.write_text(
                "---\n"
                "type: recall-miss\n"
                "query: external secret query must not be read\n"
                "expected_id: mem_external\n"
                "---\n",
                encoding="utf-8",
            )
            link = feedback / "external.md"
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))
            rendered = json.dumps(plan, default=lambda value: getattr(value, "__dict__", str(value)))

        self.assertEqual(plan.pending_count, 0)
        self.assertEqual(plan.invalid_count, 1)
        self.assertIn("symlink", plan.invalid_misses[0].error)
        self.assertNotIn("external secret query", rendered)

    def test_recall_fixture_review_plan_rejects_symlink_feedback_dir_before_listing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            inbox = root / "inbox"
            inbox.mkdir()
            outside_feedback = Path(outside_tmp) / "external-feedback"
            outside_feedback.mkdir()
            (outside_feedback / "sensitive-filename.md").write_text(
                "---\ntype: recall-miss\nquery: external secret query must not be read\nexpected_id: mem_external\n---\n",
                encoding="utf-8",
            )
            try:
                os.symlink(outside_feedback, inbox / "recall-feedback", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))
            rendered = json.dumps(plan, default=lambda value: getattr(value, "__dict__", str(value)))

        self.assertEqual(plan.pending_count, 0)
        self.assertEqual(plan.invalid_count, 1)
        self.assertEqual(plan.invalid_misses[0].path, "inbox/recall-feedback")
        self.assertIn("symlink", plan.invalid_misses[0].error)
        self.assertNotIn("sensitive-filename", rendered)
        self.assertNotIn("external secret query", rendered)

    def test_recall_fixture_review_plan_writes_generated_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            capture_miss(root, "missing codex policy", "Expected policy was absent.", expected_id="mem_policy")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "review-plan",
                        "--write-report",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["report_path"]).read_text(encoding="utf-8")

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rejected = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "review-plan",
                        "--write-report",
                        "--report-path",
                        str(Path(tmp).parent / "outside.md"),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["report_path"], "reports/recall-review-plan.md")
        self.assertIn("Recall Review Plan", report_text)
        self.assertIn("Candidate Check", report_text)
        self.assertIn("recall-fixtures check-miss", report_text)
        self.assertIn("Pending Misses", report_text)
        self.assertIn("missing codex policy", report_text)
        self.assertIn("does not promote fixtures", report_text)
        self.assertEqual(rejected, 1)

    def test_recall_fixture_review_report_rejects_rendered_secret_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))
            report = root / "reports" / "recall-review-plan.md"

            with patch("recall_fixtures.scan_text", return_value=[object()]):
                with self.assertRaisesRegex(ValueError, "recall review report rejected by secret scan"):
                    write_recall_review_report(root, plan)

        self.assertFalse(report.exists())

    def test_recall_fixture_review_packet_writes_generated_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            capture_miss(root, "missing codex policy", "Expected policy was absent.", expected_id="mem_policy")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--write-report",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["report_path"]).read_text(encoding="utf-8")

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rejected = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--write-report",
                        "--report-path",
                        str(Path(tmp).parent / "outside.md"),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["mutates_system"])
        self.assertFalse(payload["records_fixture_promotions"])
        self.assertFalse(payload["writes_fixture_file"])
        self.assertFalse(payload["closes_miss_files"])
        self.assertTrue(payload["writes_files"])
        self.assertEqual(payload["report_path"], "reports/recall-review-packet.md")
        self.assertIn("Recall Review Packet", report_text)
        self.assertIn("Reviewer Fill-In", report_text)
        self.assertIn("recall-fixtures check-miss", report_text)
        self.assertIn("promote-miss", report_text)
        self.assertIn("review-miss", report_text)
        self.assertIn("eval-recall", report_text)
        self.assertIn("does not record reviewed fixture promotions", report_text)
        self.assertEqual(rejected, 1)

    def test_recall_fixture_review_packet_rejects_inside_root_non_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            canonical_path = root / "memories" / "tools" / "recall-review-packet.md"

            with self.assertRaisesRegex(ValueError, "report path must stay under reports/"):
                write_recall_review_packet(root, paginate_recall_review_plan(recall_fixture_review_plan(root)), canonical_path)

        self.assertFalse(canonical_path.exists())

    def test_recall_fixture_review_packet_rejects_symlinked_reports_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            outside_reports = root / "active"
            outside_reports.mkdir()
            reports = root / "reports"
            try:
                os.symlink(outside_reports, reports, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "report path must not contain symlinks"):
                write_recall_review_packet(root, paginate_recall_review_plan(recall_fixture_review_plan(root)))
            redirected_files = list(outside_reports.glob("*.md"))

        self.assertEqual(redirected_files, [])

    def test_recall_fixture_review_packet_writes_timestamped_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            capture_miss(root, "missing archived recall policy", "Expected policy was absent.", expected_id="mem_policy")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--reviewer",
                        "Unit Reviewer",
                        "--archive",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            archive_path = root / payload["archive_path"]
            archive_text = archive_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["writes_files"])
        self.assertTrue(payload["writes_archive"])
        self.assertIsNone(payload["report_path"])
        self.assertTrue(payload["archive_path"].startswith("reports/recall-review-packets/"))
        self.assertRegex(payload["archive_path"], r"recall-review-packet-\d{8}T\d{6}Z\.md$")
        self.assertIn("Recall Review Packet", archive_text)
        self.assertIn("reviewer: `Unit Reviewer`", archive_text)

    def test_recall_fixture_review_packet_archive_path_is_unique_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 6, 22, 12, 34, 56, tzinfo=timezone.utc)
            first = recall_review_packet_archive_path(root, now=now)
            first.parent.mkdir(parents=True)
            first.write_text("first\n", encoding="utf-8")
            second = recall_review_packet_archive_path(root, now=now)

            with self.assertRaisesRegex(ValueError, "archive dir must stay inside the memory root"):
                recall_review_packet_archive_path(root, Path(tmp).parent / "outside")

        self.assertEqual(first.name, "recall-review-packet-20260622T123456Z.md")
        self.assertEqual(second.name, "recall-review-packet-20260622T123456Z-1.md")
        self.assertTrue(first.as_posix().endswith("reports/recall-review-packets/recall-review-packet-20260622T123456Z.md"))

    def test_recall_fixture_review_packet_archive_rejects_symlinked_reports_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            outside_reports = root / "active"
            outside_reports.mkdir()
            reports = root / "reports"
            try:
                os.symlink(outside_reports, reports, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "archive dir must not contain symlinks"):
                write_recall_review_packet_archive(root, paginate_recall_review_plan(recall_fixture_review_plan(root)))
            redirected_files = list(outside_reports.rglob("*.md"))

        self.assertEqual(redirected_files, [])

    def test_recall_fixture_review_packet_archive_rejects_symlinked_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            archive_parent = root / "reports"
            archive_parent.mkdir()
            outside_archive = root / "active"
            outside_archive.mkdir()
            archive_root = archive_parent / "recall-review-packets"
            try:
                os.symlink(outside_archive, archive_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "archive dir must not contain symlinks"):
                write_recall_review_packet_archive(root, paginate_recall_review_plan(recall_fixture_review_plan(root)))
            redirected_files = list(outside_archive.glob("*.md"))

        self.assertEqual(redirected_files, [])

    def test_recall_fixture_review_packet_invalid_archive_dir_writes_no_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            outside = Path(tmp).parent / "outside"

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--write-report",
                        "--archive",
                        "--archive-dir",
                        str(outside),
                    ]
                )

            report_exists = (root / "reports" / "recall-review-packet.md").exists()

        self.assertEqual(exit_code, 1)
        self.assertFalse(report_exists)

    def test_recall_fixture_review_packet_archive_status_lists_paginated_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            plan = paginate_recall_review_plan(recall_fixture_review_plan(root))
            first = write_recall_review_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            second = write_recall_review_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc),
            )

            first_page = recall_review_packet_archive_status(root, limit=1)
            second_page = recall_review_packet_archive_status(root, limit=1, offset=1)

        self.assertEqual(first_page["archive_root"], "reports/recall-review-packets")
        self.assertEqual(first_page["total_count"], 2)
        self.assertEqual(first_page["returned_count"], 1)
        self.assertEqual(first_page["next_offset"], 1)
        self.assertTrue(first_page["has_more"])
        self.assertEqual(first_page["archives"][0]["path"], repo_relative_path(second, root))
        self.assertEqual(first_page["archives"][0]["generated_at"], "2026-06-23T12:00:00Z")
        self.assertGreater(first_page["archives"][0]["size_bytes"], 0)
        self.assertFalse(first_page["writes_files"])
        self.assertFalse(first_page["records_fixture_promotions"])
        self.assertFalse(first_page["writes_fixture_file"])
        self.assertFalse(first_page["closes_miss_files"])
        self.assertEqual(second_page["archives"][0]["path"], repo_relative_path(first, root))
        self.assertIsNone(second_page["next_offset"])
        self.assertFalse(second_page["has_more"])

    def test_recall_fixture_review_packet_archive_status_cli_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            plan = paginate_recall_review_plan(recall_fixture_review_plan(root))
            write_recall_review_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(["--root", str(root), "packet-archive-status", "--json"])
            payload = json.loads(output.getvalue())

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_limit = recall_fixtures_main(["--root", str(root), "packet-archive-status", "--limit", "0"])
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_offset = recall_fixtures_main(["--root", str(root), "packet-archive-status", "--offset", "-1"])
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_dir = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet-archive-status",
                        "--archive-dir",
                        str(Path(tmp).parent / "outside"),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["total_count"], 1)
        self.assertEqual(payload["archives"][0]["generated_at"], "2026-06-22T12:00:00Z")
        self.assertEqual(bad_limit, 1)
        self.assertEqual(bad_offset, 1)
        self.assertEqual(bad_dir, 1)

    def test_recall_fixture_review_packet_archive_retention_plan_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            plan = paginate_recall_review_plan(recall_fixture_review_plan(root))
            oldest = write_recall_review_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc),
            )
            middle = write_recall_review_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            newest = write_recall_review_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc),
            )

            retention = recall_review_packet_archive_retention_plan(root, keep=1, limit=1)
            second_page = recall_review_packet_archive_retention_plan(root, keep=1, limit=1, offset=1)
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(
                    ["--root", str(root), "packet-archive-retention-plan", "--keep", "1", "--json"]
                )
            cli_payload = json.loads(output.getvalue())
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_keep = recall_fixtures_main(["--root", str(root), "packet-archive-retention-plan", "--keep", "0"])
            newest_exists = newest.exists()
            middle_exists = middle.exists()
            oldest_exists = oldest.exists()

        self.assertEqual(retention["archive_root"], "reports/recall-review-packets")
        self.assertEqual(retention["total_count"], 3)
        self.assertEqual(retention["keep"], 1)
        self.assertEqual(retention["retained_count"], 1)
        self.assertEqual(retention["prunable_count"], 2)
        self.assertEqual(retention["returned_count"], 1)
        self.assertEqual(retention["next_offset"], 1)
        self.assertTrue(retention["has_more"])
        self.assertEqual(retention["prune_candidates"][0]["path"], repo_relative_path(middle, root))
        self.assertEqual(second_page["prune_candidates"][0]["path"], repo_relative_path(oldest, root))
        self.assertFalse(retention["writes_files"])
        self.assertFalse(retention["deletes_files"])
        self.assertFalse(retention["records_fixture_promotions"])
        self.assertFalse(retention["writes_fixture_file"])
        self.assertFalse(retention["closes_miss_files"])
        self.assertTrue(newest_exists)
        self.assertTrue(middle_exists)
        self.assertTrue(oldest_exists)
        self.assertEqual(exit_code, 0)
        self.assertEqual(cli_payload["prunable_count"], 2)
        self.assertEqual(bad_keep, 1)

    def test_recall_fixture_review_packet_archive_retention_keeps_newest_same_second_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            plan = paginate_recall_review_plan(recall_fixture_review_plan(root))
            now = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)
            first = write_recall_review_packet_archive(root, plan, now=now)
            second = write_recall_review_packet_archive(root, plan, now=now)
            third = write_recall_review_packet_archive(root, plan, now=now)

            status = recall_review_packet_archive_status(root, limit=3)
            retention = recall_review_packet_archive_retention_plan(root, keep=1, limit=2)

        self.assertEqual(status["archives"][0]["path"], repo_relative_path(third, root))
        self.assertEqual(status["archives"][1]["path"], repo_relative_path(second, root))
        self.assertEqual(status["archives"][2]["path"], repo_relative_path(first, root))
        self.assertEqual(retention["retained_count"], 1)
        self.assertEqual(retention["prune_candidates"][0]["path"], repo_relative_path(second, root))
        self.assertEqual(retention["prune_candidates"][1]["path"], repo_relative_path(first, root))

    def test_recall_fixture_review_packet_paginates_pending_and_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            for idx in range(3):
                capture_miss(
                    root,
                    f"missing paginated recall policy {idx}",
                    "Expected policy was absent.",
                    expected_id="mem_policy",
                )
            feedback = root / "inbox" / "recall-feedback"
            for idx in range(3):
                (feedback / f"broken-{idx}.md").write_text(
                    "---\n"
                    f"id: broken-{idx}\n"
                    "---\n\n"
                    "Malformed recall miss fixture.\n",
                    encoding="utf-8",
                )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--limit",
                        "2",
                        "--pending-offset",
                        "2",
                        "--invalid-offset",
                        "2",
                        "--write-report",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["report_path"]).read_text(encoding="utf-8")
            mcp_payload = call_tool(
                "memory.recall_review_packet",
                {"limit": 2, "pending_offset": 2, "invalid_offset": 2},
                root,
            )
            mcp_plan_payload = call_tool(
                "memory.recall_review_plan",
                {"limit": 2, "pending_offset": 2, "invalid_offset": 2},
                root,
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_offset = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--pending-offset",
                        "-1",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["pending_count"], 3)
        self.assertEqual(payload["pending_returned_count"], 1)
        self.assertEqual(payload["pending_offset"], 2)
        self.assertIsNone(payload["pending_next_offset"])
        self.assertFalse(payload["pending_has_more"])
        self.assertEqual(payload["invalid_count"], 3)
        self.assertEqual(payload["invalid_returned_count"], 1)
        self.assertEqual(payload["invalid_offset"], 2)
        self.assertIsNone(payload["invalid_next_offset"])
        self.assertFalse(payload["invalid_has_more"])
        self.assertEqual(len(payload["pending_misses"]), 1)
        self.assertEqual(len(payload["invalid_misses"]), 1)
        self.assertIn("pending returned: `1`", report_text)
        self.assertIn("invalid returned: `1`", report_text)
        self.assertEqual(mcp_payload["pending_returned_count"], 1)
        self.assertEqual(mcp_payload["invalid_returned_count"], 1)
        self.assertFalse(mcp_payload["writes_files"])
        self.assertEqual(len(mcp_payload["pending_misses"]), 1)
        self.assertEqual(len(mcp_payload["invalid_misses"]), 1)
        self.assertEqual(mcp_plan_payload["pending_returned_count"], 1)
        self.assertEqual(mcp_plan_payload["invalid_returned_count"], 1)
        self.assertEqual(mcp_plan_payload["pending_offset"], 2)
        self.assertEqual(mcp_plan_payload["invalid_offset"], 2)
        self.assertIsNone(mcp_plan_payload["reviewer"])
        self.assertIsNone(mcp_plan_payload["pr_url"])
        self.assertEqual(len(mcp_plan_payload["pending_misses"]), 1)
        self.assertEqual(len(mcp_plan_payload["invalid_misses"]), 1)
        self.assertEqual(bad_offset, 1)

    def test_recall_fixture_review_packet_includes_reviewer_and_pr_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            capture_miss(root, "missing metadata recall policy", "Expected policy was absent.", expected_id="mem_policy")
            pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/212"
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = recall_fixtures_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--reviewer",
                        "Unit Reviewer",
                        "--pr-url",
                        pr_url,
                        "--write-report",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["report_path"]).read_text(encoding="utf-8")
            mcp_payload = call_tool(
                "memory.recall_review_packet",
                {"reviewer": "Unit Reviewer", "pr_url": pr_url},
                root,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["reviewer"], "Unit Reviewer")
        self.assertEqual(payload["pr_url"], pr_url)
        self.assertIn("reviewer: `Unit Reviewer`", report_text)
        self.assertIn(f"pr_url: `{pr_url}`", report_text)
        self.assertEqual(mcp_payload["reviewer"], "Unit Reviewer")
        self.assertEqual(mcp_payload["pr_url"], pr_url)
        self.assertIn("reviewer: `Unit Reviewer`", mcp_payload["markdown"])

    def test_recall_fixture_review_packet_metadata_escapes_inline_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            capture_miss(root, "missing metadata recall policy", "Expected policy was absent.", expected_id="mem_policy")
            plan = annotate_recall_review_packet_plan(
                paginate_recall_review_plan(recall_fixture_review_plan(root, today=date(2026, 6, 19))),
                reviewer="Reviewer `quoted`\n- injected",
                pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/213 ``x``\n- fake",
            )

            packet = render_recall_review_packet(plan)

        self.assertIn("reviewer: ``Reviewer `quoted` - injected``", packet)
        self.assertIn("pr_url: ```https://github.com/GonzaloTorreras/ai-dememory/pull/213 ``x`` - fake```", packet)
        self.assertNotIn("\n- injected", packet)
        self.assertNotIn("\n- fake", packet)

    def test_recall_fixture_review_packet_metadata_is_secret_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            secret_like_reviewer = "sk-" + "proj-" + ("b" * 26)
            plan = annotate_recall_review_packet_plan(
                paginate_recall_review_plan(recall_fixture_review_plan(root, today=date(2026, 6, 19))),
                reviewer=secret_like_reviewer,
            )
            report = root / "reports" / "recall-review-packet.md"

            with self.assertRaisesRegex(ValueError, "recall review packet rejected by secret scan"):
                write_recall_review_packet(root, plan)

        self.assertFalse(report.exists())

    def test_recall_fixture_review_packet_archive_rejects_rendered_secret_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            secret_like_reviewer = "sk-" + "proj-" + ("d" * 26)
            plan = annotate_recall_review_packet_plan(
                paginate_recall_review_plan(recall_fixture_review_plan(root, today=date(2026, 6, 19))),
                reviewer=secret_like_reviewer,
            )
            archive_root = root / DEFAULT_REVIEW_PACKET_ARCHIVE_DIR

            with self.assertRaisesRegex(ValueError, "recall review packet archive rejected by secret scan"):
                write_recall_review_packet_archive(root, plan)

        self.assertFalse(archive_root.exists())

    def test_recall_fixture_review_packet_rejects_rendered_secret_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))
            report = root / "reports" / "recall-review-packet.md"

            with patch("recall_fixtures.scan_text", return_value=[object()]):
                with self.assertRaisesRegex(ValueError, "recall review packet rejected by secret scan"):
                    write_recall_review_packet(root, plan)

        self.assertFalse(report.exists())

    def test_recall_fixture_review_packet_renders_boundary_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))

        packet = render_recall_review_packet(plan)

        self.assertIn("generated review guidance only", packet)
        self.assertIn("does not write `quality/recall-fixtures.json`", packet)
        self.assertIn("release-evidence --strict", packet)

    def test_recall_fixture_review_plan_redacts_secret_like_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            feedback = root / "inbox" / "recall-feedback"
            feedback.mkdir(parents=True)
            miss = feedback / "secret.md"
            fake_key = "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz"
            miss.write_text(
                "---\n"
                "type: recall-miss\n"
                "status: proposed\n"
                "created_at: 2026-06-19\n"
                f"query: {fake_key}\n"
                "expected_id: mem_policy\n"
                "expected_path: null\n"
                "source_ref: test\n"
                "---\n",
                encoding="utf-8",
            )

            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))

        self.assertTrue(plan.pending_misses[0].redacted_fields)
        self.assertEqual(plan.pending_misses[0].query, "<redacted:secret-like>")

    def test_repo_recall_fixtures_are_valid(self) -> None:
        fixtures = load_fixtures(ROOT / "quality" / "recall-fixtures.json")

        self.assertGreaterEqual(len(fixtures), 5)

    def test_search_filters_sensitive_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/internal.md", memory_id="mem_internal")
            write_memory(
                root,
                "memories/tools/sensitive.md",
                memory_id="mem_sensitive",
                sensitivity="sensitive",
            )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            default_results = search("codex", root, db_path=db_path)
            sensitive_results = search("codex", root, db_path=db_path, include_sensitive=True)

        self.assertEqual({result.id for result in default_results}, {"mem_internal"})
        self.assertEqual({result.id for result in sensitive_results}, {"mem_internal", "mem_sensitive"})

    def test_context_export_filters_sensitive_memories_from_all_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/internal.md", memory_id="mem_internal")
            write_memory(
                root,
                "memories/tools/sensitive.md",
                memory_id="mem_sensitive",
                sensitivity="sensitive",
                body="Sensitive-only phrase must not be exported.",
            )

            written = export_context(root, root / "distilled")
            combined = "\n".join(path.read_text(encoding="utf-8") for path in written)

        self.assertNotIn("Sensitive-only phrase", combined)

    def test_mcp_tools_validate_and_write_proposals_to_inbox(self) -> None:
        tool_names = {tool["name"] for tool in TOOLS}
        self.assertIn("memory.search", tool_names)
        self.assertIn("memory.graph", tool_names)
        self.assertIn("memory.write_proposal", tool_names)
        self.assertIn("memory.secret_scan", tool_names)
        search_tool = next(tool for tool in TOOLS if tool["name"] == "memory.search")
        self.assertIn("outputSchema", search_tool)
        self.assertTrue(search_tool["annotations"]["readOnlyHint"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            search_result = call_tool("memory.search", {"query": "codex", "limit": 1}, root)
            graph_result = call_tool("memory.graph", {}, root)
            proposal_result = call_tool(
                "memory.write_proposal",
                {
                    "title": "Session Capture: quoted #1",
                    "content": "Remember that proposals stay in inbox.",
                    "project": "ai-dememory",
                    "tags": ["codex", "proposal"],
                    "source_kind": "claude",
                    "source_ref": "unit:test",
                },
                root,
            )
            secret = "sk-" + "proj-" + ("b" * 40)
            with self.assertRaises(ValueError):
                call_tool(
                    "memory.write_proposal",
                    {
                        "title": "Bad Capture",
                        "content": f"OPENAI_API_KEY={secret}",
                        "project": "ai-dememory",
                    },
                    root,
                )
            proposal_files = list((root / "inbox" / "llm-captures").glob("*.md"))
            proposal = load_memory(proposal_files[0])

        self.assertEqual(search_result[0]["id"], "mem_codex_test")
        self.assertIn("matched_terms", search_result[0]["why"])
        self.assertIn("codex", search_result[0]["why"]["matched_terms"])
        self.assertTrue(any(node["id"] == "mem_codex_test" for node in graph_result["nodes"]))
        self.assertTrue(proposal_result["path"].startswith("inbox/llm-captures/"))
        self.assertEqual(proposal.frontmatter["title"], "Session Capture: quoted #1")
        self.assertEqual(proposal.frontmatter["source"]["kind"], "claude")
        self.assertEqual(len(proposal_files), 1)

    def test_mcp_resources_and_prompts_are_discoverable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")

            resources = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "resources/list"}, root)
            resource_uri = resources["resources"][0]["uri"]
            resource = handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "resources/read",
                    "params": {"uri": resource_uri},
                },
                root,
            )
            prompts = handle_rpc({"jsonrpc": "2.0", "id": 3, "method": "prompts/list"}, root)
            prompt = handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "prompts/get",
                    "params": {"name": "memory_recall_context", "arguments": {"query": "codex"}},
                },
                root,
            )

        self.assertEqual(resources["resources"][0]["name"], "mem_codex_test")
        self.assertIn("Codex Test Memory", resource["contents"][0]["text"])
        self.assertIn("memory_recall_context", {item["name"] for item in prompts["prompts"]})
        self.assertIn("memory.search", prompt["messages"][0]["content"]["text"])

    def test_mcp_tool_call_returns_structured_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            response = handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "memory.search", "arguments": {"query": "codex", "limit": 1}},
                },
                root,
            )

        self.assertFalse(response["isError"])
        self.assertEqual(response["structuredContent"]["results"][0]["id"], "mem_codex_test")

    def test_mcp_get_rejects_non_memory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_file = root / "docs" / "architecture.md"
            docs_file.parent.mkdir(parents=True)
            docs_file.write_text(valid_memory_text("mem_docs_architecture"), encoding="utf-8")

            with self.assertRaises(PermissionError):
                call_tool("memory.get", {"path": "docs/architecture.md"}, root)

    def test_mcp_secret_scan_rejects_paths_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaises(PermissionError):
                call_tool("memory.secret_scan", {"paths": ["../outside.txt"]}, root)
            with self.assertRaises(PermissionError):
                call_tool("memory.secret_scan", {"paths": [str(Path(tmp).parent / "outside.txt")]}, root)

    def test_mcp_lifecycle_handles_initialize_and_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialized = handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                },
                root,
            )
            notification = handle_rpc(
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                root,
            )
            cancelled = handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/cancelled",
                    "params": {"requestId": 2, "reason": "unit test"},
                },
                root,
            )
            ping = handle_rpc({"jsonrpc": "2.0", "id": 3, "method": "ping"}, root)

        self.assertEqual(initialized["protocolVersion"], "2025-11-25")
        self.assertIsNone(notification)
        self.assertIsNone(cancelled)
        self.assertEqual(ping, {})

    def test_mark_seen_records_retrieval_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            receipt = call_tool(
                "memory.mark_seen",
                {
                    "query": "codex",
                    "selected_memory_id": "mem_codex_test",
                    "score": 0.9,
                    "used_by": "unittest",
                },
                root,
            )
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT count(*) FROM retrieval_log").fetchone()[0]
            lifecycle = conn.execute(
                "SELECT retrieval_count, strength FROM memory_lifecycle WHERE memory_id = ?",
                ("mem_codex_test",),
            ).fetchone()
            conn.close()

        self.assertEqual(count, 1)
        self.assertEqual(receipt["selected_memory_id"], "mem_codex_test")
        self.assertTrue(receipt["lifecycle_updated"])
        self.assertEqual(receipt["query"], "codex")
        self.assertEqual(lifecycle[0], 1)
        self.assertGreater(lifecycle[1], 0.0)

    def test_mark_seen_rejects_secret_like_selected_memory_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            secret = "sk-" + "proj-" + ("m" * 40)

            with self.assertRaisesRegex(ValueError, "selected_memory_id"):
                call_tool(
                    "memory.mark_seen",
                    {
                        "query": "codex",
                        "selected_memory_id": secret,
                        "score": 0.9,
                        "used_by": "unittest",
                    },
                    root,
                )

    def test_lifecycle_mark_seen_cli_emits_json_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = lifecycle_main(
                    [
                        "--root",
                        str(root),
                        "mark-seen",
                        "--id",
                        "mem_codex_test",
                        "--query",
                        "codex",
                        "--score",
                        "0.9",
                        "--used-by",
                        "unit-test",
                        "--json",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["memory_id"], "mem_codex_test")
        self.assertEqual(payload["query"], "codex")
        self.assertEqual(payload["score"], 0.9)
        self.assertEqual(payload["used_by"], "unit-test")
        self.assertTrue(payload["lifecycle_updated"])

    def test_lifecycle_outcome_records_feedback_for_last_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")

            lifecycle_mark_seen(root, "mem_codex_test", query="codex", score=0.9)
            outcome = record_outcome(root, None, "good", note="Useful memory.")
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT positive_outcomes, strength FROM memory_lifecycle WHERE memory_id = ?",
                ("mem_codex_test",),
            ).fetchone()
            conn.close()

        self.assertEqual(outcome["memory_id"], "mem_codex_test")
        self.assertEqual(outcome["target_source"], "last_seen")
        self.assertEqual(outcome["positive_outcomes"], 1)
        self.assertEqual(outcome["negative_outcomes"], 0)
        self.assertTrue(outcome["note_recorded"])
        self.assertTrue(outcome["lifecycle_updated"])
        self.assertEqual(row[0], 1)
        self.assertGreater(row[1], 0.0)

    def test_lifecycle_outcome_rejects_secret_like_explicit_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            secret = "sk-" + "proj-" + ("n" * 40)

            with self.assertRaisesRegex(ValueError, "memory id"):
                record_outcome(root, secret, "good", note="Useful memory.")

    def test_lifecycle_outcome_rejects_secret_like_last_seen_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            secret = "sk-" + "proj-" + ("p" * 40)
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                INSERT INTO retrieval_log (query, selected_memory_id, score, used_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("codex", secret, 0.1, "unit-test", "2026-07-04T00:00:00+00:00"),
            )
            conn.commit()
            conn.close()

            with self.assertRaisesRegex(ValueError, "memory id"):
                record_outcome(root, None, "bad", note="Bad memory.")

    def test_lifecycle_outcome_cli_emits_json_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            lifecycle_mark_seen(root, "mem_codex_test", query="codex", score=0.9)
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = lifecycle_main(
                    [
                        "--root",
                        str(root),
                        "outcome",
                        "--last",
                        "--good",
                        "--note",
                        "Useful memory.",
                        "--json",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["memory_id"], "mem_codex_test")
        self.assertEqual(payload["target_source"], "last_seen")
        self.assertEqual(payload["outcome"], "good")
        self.assertTrue(payload["note_recorded"])
        self.assertEqual(payload["positive_outcomes"], 1)
        self.assertEqual(payload["negative_outcomes"], 0)
        self.assertGreater(payload["strength"], 0.0)
        self.assertGreaterEqual(payload["reward_factor"], 1.0)
        self.assertTrue(payload["lifecycle_updated"])

    def test_lifecycle_scores_survive_index_rebuild_and_write_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            lifecycle_mark_seen(root, "mem_codex_test", query="codex", score=0.9)
            record_outcome(root, "mem_codex_test", "good", note="Useful result.")

            before = lifecycle_scores(root)[0]
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            after = lifecycle_scores(root)[0]
            report_path, report_scores = write_lifecycle_report(root)
            report_text = report_path.read_text(encoding="utf-8")

        self.assertEqual(before.memory_id, "mem_codex_test")
        self.assertEqual(after.memory_id, "mem_codex_test")
        self.assertEqual(after.retrieval_count, 1)
        self.assertEqual(after.positive_outcomes, 1)
        self.assertGreater(after.score, 0.0)
        self.assertEqual(report_scores[0].memory_id, "mem_codex_test")
        self.assertIn("Lifecycle Scores", report_text)

    def test_lifecycle_scores_exclude_sensitive_metadata_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/public.md", memory_id="mem_public")
            write_memory(
                root,
                "memories/tools/private.md",
                memory_id="mem_private",
                sensitivity="private",
            )
            write_memory(
                root,
                "memories/tools/sensitive.md",
                memory_id="mem_sensitive",
                sensitivity="sensitive",
            )
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            default_ids = {score.memory_id for score in lifecycle_scores(root)}
            included_ids = {score.memory_id for score in lifecycle_scores(root, include_sensitive=True)}

        self.assertEqual(default_ids, {"mem_public"})
        self.assertEqual(included_ids, {"mem_public", "mem_private", "mem_sensitive"})

    def test_lifecycle_report_writes_custom_in_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            lifecycle_mark_seen(root, "mem_codex_test", query="codex", score=0.9)
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = lifecycle_main(
                    [
                        "--root",
                        str(root),
                        "report",
                        "--report-path",
                        "reports/custom-lifecycle.md",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["path"]).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["path"], "reports/custom-lifecycle.md")
        self.assertIn("Lifecycle Scores", report_text)

    def test_lifecycle_scores_rejects_outside_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            outside = Path(tmp) / "lifecycle.json"
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = lifecycle_main(
                    [
                        "--root",
                        str(root),
                        "scores",
                        "--output",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertFalse(outside.exists())
        self.assertIn("must stay inside", error.getvalue())

    def test_lifecycle_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            outside = Path(tmp) / "lifecycle.md"
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = lifecycle_main(
                    [
                        "--root",
                        str(root),
                        "report",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_sleep_consolidation_plans_and_writes_review_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/one.md", memory_id="mem_sleep_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_sleep_two")
            inbox = root / "inbox" / "llm-captures" / "candidate.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Candidate\n\nRemember non-secret setup notes.", encoding="utf-8")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            plan = build_sleep_plan(root)
            report_path, report = write_sleep_report(root)
            selected = [item for item in plan.candidates if item.kind == "inbox_candidate"][0]
            packets = apply_review_packets(root, [selected.id])
            packet_text = packets[0].read_text(encoding="utf-8")

        self.assertTrue(any(item.kind == "active_conflict" for item in plan.candidates))
        self.assertTrue(any(item.kind == "inbox_candidate" for item in plan.candidates))
        self.assertEqual(len(report.candidates), len(plan.candidates))
        self.assertIn("reports/sleep-plan.md", report_path.as_posix())
        self.assertEqual(len(packets), 1)
        self.assertIn("inbox/sleep-consolidation", packets[0].as_posix())
        self.assertIn("Sleep Review Packet", packet_text)

    def test_sleep_top_level_dry_run_and_propose_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/one.md", memory_id="mem_sleep_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_sleep_two")
            inbox = root / "inbox" / "llm-captures" / "candidate.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Candidate\n\nRemember non-secret setup notes.", encoding="utf-8")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            dry_output = io.StringIO()
            with redirect_stdout(dry_output):
                dry_exit = sleep_main(["--root", str(root), "--dry-run", "--json"])
            dry_payload = json.loads(dry_output.getvalue())
            selected = [
                item
                for item in dry_payload["plan"]["candidates"]
                if item["kind"] == "inbox_candidate"
            ][0]
            report_exists_after_dry_run = (root / "reports" / "sleep-plan.md").exists()
            packets_after_dry_run = list((root / "inbox" / "sleep-consolidation").glob("sleep_*.md"))

            propose_output = io.StringIO()
            with redirect_stdout(propose_output):
                propose_exit = sleep_main(
                    [
                        "--root",
                        str(root),
                        "--propose",
                        "--id",
                        selected["id"],
                        "--json",
                    ]
                )
            propose_payload = json.loads(propose_output.getvalue())

        self.assertEqual(dry_exit, 0)
        self.assertTrue(dry_payload["dry_run"])
        self.assertFalse(dry_payload["writes_files"])
        self.assertFalse(dry_payload["writes_canonical_memory"])
        self.assertFalse(report_exists_after_dry_run)
        self.assertEqual(packets_after_dry_run, [])
        self.assertEqual(propose_exit, 0)
        self.assertEqual(len(propose_payload["written"]), 1)
        self.assertTrue(propose_payload["written"][0].startswith("inbox/sleep-consolidation/"))
        self.assertTrue(propose_payload["writes_files"])
        self.assertFalse(propose_payload["writes_canonical_memory"])
        self.assertFalse(propose_payload["deletes_files"])

    def test_sleep_top_level_apply_reviewed_alias_requires_review_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/one.md", memory_id="mem_sleep_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_sleep_two")
            inbox = root / "inbox" / "llm-captures" / "candidate.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Candidate\n\nRemember non-secret setup notes.", encoding="utf-8")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            plan = build_sleep_plan(root)
            selected = [item for item in plan.candidates if item.kind == "inbox_candidate"][0]

            error = io.StringIO()
            with redirect_stderr(error):
                missing_scope_exit = sleep_main(["--root", str(root), "--apply-reviewed", "--json"])
            apply_output = io.StringIO()
            with redirect_stdout(apply_output):
                apply_exit = sleep_main(
                    [
                        "--root",
                        str(root),
                        "--apply-reviewed",
                        "--id",
                        selected.id,
                        "--json",
                    ]
                )
            apply_payload = json.loads(apply_output.getvalue())

        self.assertEqual(missing_scope_exit, 1)
        self.assertIn("--apply-reviewed requires", error.getvalue())
        self.assertEqual(apply_exit, 0)
        self.assertEqual(apply_payload["alias"], "apply-reviewed")
        self.assertEqual(len(apply_payload["written"]), 1)
        self.assertTrue(apply_payload["written"][0].startswith("inbox/sleep-consolidation/"))
        self.assertFalse(apply_payload["writes_canonical_memory"])
        self.assertFalse(apply_payload["deletes_files"])

    def test_sleep_apply_reviewed_subcommand_all_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/one.md", memory_id="mem_sleep_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_sleep_two")
            inbox = root / "inbox" / "llm-captures" / "candidate.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Candidate\n\nRemember non-secret setup notes.", encoding="utf-8")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = sleep_main(["--root", str(root), "apply-reviewed", "--all", "--json"])
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(len(payload["written"]), 1)
        self.assertTrue(all(path.startswith("inbox/sleep-consolidation/") for path in payload["written"]))

    def test_sleep_apply_reviewed_rejects_symlinked_packet_dir_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside_packets = Path(tmp) / "outside-packets"
            copy_template_tree(root)
            outside_packets.mkdir()
            write_memory(root, "memories/tools/one.md", memory_id="mem_sleep_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_sleep_two")
            inbox = root / "inbox" / "llm-captures" / "candidate.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Candidate\n\nRemember non-secret setup notes.", encoding="utf-8")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            (root / "inbox").mkdir(exist_ok=True)
            try:
                os.symlink(outside_packets, root / "inbox" / "sleep-consolidation", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            plan = build_sleep_plan(root)
            selected = [item for item in plan.candidates if item.kind == "inbox_candidate"][0]

            with self.assertRaisesRegex(SleepError, "symlink"):
                apply_review_packets(root, [selected.id])

            self.assertEqual(list(outside_packets.glob("**/*")), [])

    def test_sleep_plan_writes_custom_in_root_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_sleep_codex")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = sleep_main(
                    [
                        "--root",
                        str(root),
                        "plan",
                        "--report-path",
                        "reports/custom-sleep-plan.md",
                    ]
                )
            report_path = root / "reports" / "custom-sleep-plan.md"
            report_text = report_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("reports/custom-sleep-plan.md", output.getvalue())
        self.assertIn("Sleep Consolidation Plan", report_text)

    def test_sleep_plan_writes_custom_in_root_json_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_sleep_codex")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = sleep_main(
                    [
                        "--root",
                        str(root),
                        "plan",
                        "--json",
                        "--json-report-path",
                        "reports/custom-sleep-plan.json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_data = json.loads((root / payload["path"]).read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["path"], "reports/custom-sleep-plan.json")
        self.assertIn("candidates", payload["plan"])
        self.assertIn("candidates", report_data)

    def test_sleep_plan_rejects_outside_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            copy_template_tree(root)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_sleep_codex")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            outside = Path(tmp) / "sleep-plan.md"
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = sleep_main(
                    [
                        "--root",
                        str(root),
                        "plan",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_working_memory_snapshot_and_handoff_are_reviewable_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            current = snapshot(root, "Implement context", "Need to finish context command.", task="memory")
            handoff_path = handoff(root, "Session handoff", "Next: review context output.")
            status = working_status(root, limit=1)

            current_text = current.read_text(encoding="utf-8")
            handoff_text = handoff_path.read_text(encoding="utf-8")

        self.assertIn("working/current.json", current.as_posix())
        self.assertIn("working/handoffs", handoff_path.as_posix())
        self.assertIn("Implement context", current_text)
        self.assertIn("Session handoff", handoff_text)
        self.assertTrue(status["current_exists"])
        self.assertTrue(status["recent_session_exists"])
        self.assertEqual(status["handoff_count"], 1)
        self.assertEqual(status["handoffs"][0]["title"], "Session handoff")

    def test_working_memory_rejects_symlinked_working_dir_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside"
            root.mkdir()
            outside.mkdir()
            try:
                os.symlink(outside, root / "working", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                snapshot(root, "Escaping snapshot", "Do not write outside.", task="memory")
            with self.assertRaisesRegex(ValueError, "symlink"):
                handoff(root, "Escaping handoff", "Do not write outside.")

            self.assertFalse((outside / "current.json").exists())
            self.assertFalse((outside / "handoffs").exists())


    def test_working_memory_rejects_symlinked_read_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside"
            working = root / "working"
            handoffs = working / "handoffs"
            working.mkdir(parents=True)
            handoffs.mkdir()
            outside.mkdir()
            outside_current = outside / "current.json"
            outside_current.write_text('{"task":"outside"}\n', encoding="utf-8")
            outside_handoff_dir = outside / "handoffs"
            outside_handoff_dir.mkdir()
            (outside_handoff_dir / "20260704T000000Z_outside.md").write_text(
                "# Outside Handoff\n\nGenerated at: `2026-07-04T00:00:00+00:00`\n",
                encoding="utf-8",
            )

            try:
                os.symlink(outside_current, working / "current.json")
                handoffs.rmdir()
                os.symlink(outside_handoff_dir, handoffs, target_is_directory=True)
                os.symlink(outside_current, handoffs / "20260704T000001Z_entry.md")
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                show_current(root)

            status = working_status(root)

        self.assertFalse(status["current_exists"])
        self.assertIsNone(status["current_path"])
        self.assertEqual(status["handoff_count"], 0)
        self.assertEqual(status["handoffs"], [])

    def test_working_status_limits_handoff_reads_before_summarizing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff_dir = root / "working" / "handoffs"
            handoff_dir.mkdir(parents=True)
            (handoff_dir / "20260615T000000Z_old.md").write_text(
                "# Old Handoff\n\nGenerated at: `2026-06-15T00:00:00+00:00`\n",
                encoding="utf-8",
            )
            (handoff_dir / "20260616T000000Z_new.md").write_text(
                "# New Handoff\n\nGenerated at: `2026-06-16T00:00:00+00:00`\n",
                encoding="utf-8",
            )

            calls: list[Path] = []

            def fake_summary(summary_root: Path, path: Path) -> dict[str, Any]:
                calls.append(path)
                return {"path": path.name, "title": path.stem, "generated_at": None}

            with patch("working_memory.handoff_summary", side_effect=fake_summary):
                status = working_status(root, limit=1)

        self.assertEqual(status["handoff_count"], 2)
        self.assertEqual(len(status["handoffs"]), 1)
        self.assertEqual(status["handoffs"][0]["path"], "20260616T000000Z_new.md")
        self.assertEqual([path.name for path in calls], ["20260616T000000Z_new.md"])

    def test_mark_seen_rejects_secret_like_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            secret = "sk-" + "proj-" + ("c" * 40)

            with self.assertRaises(ValueError):
                call_tool("memory.mark_seen", {"query": secret}, root)

    def test_graph_filters_sensitive_memories_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/internal.md", memory_id="mem_internal")
            write_memory(
                root,
                "memories/tools/sensitive.md",
                memory_id="mem_sensitive",
                sensitivity="sensitive",
            )

            default_graph = build_graph(root)
            sensitive_graph = build_graph(root, include_sensitive=True)

        self.assertIn("mem_internal", {node["id"] for node in default_graph["nodes"]})
        self.assertNotIn("mem_sensitive", {node["id"] for node in default_graph["nodes"]})
        self.assertIn("mem_sensitive", {node["id"] for node in sensitive_graph["nodes"]})
        self.assertTrue(any(edge["relation"] == "tagged" for edge in default_graph["edges"]))

    def test_graph_uses_index_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            with patch.object(graph_memory, "load_memories", side_effect=AssertionError("should use index")):
                graph = build_graph(root)

        self.assertTrue(any(node["id"] == "mem_codex_test" for node in graph["nodes"]))

    def test_local_api_serves_health_search_graph_and_requires_key_when_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            server = serve(root, "127.0.0.1", 0, api_key="test-key", log_requests=False)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(f"{base_url}/health", timeout=5)
                self.assertEqual(ctx.exception.code, 401)
                ctx.exception.close()

                health = api_get(f"{base_url}/health", "test-key")
                search_result = api_get(f"{base_url}/search?query=codex&limit=1", "test-key")
                graph_result = api_get(f"{base_url}/graph", "test-key")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(health["status"], "ok")
        self.assertEqual(search_result["results"][0]["id"], "mem_codex_test")
        self.assertTrue(any(node["id"] == "mem_codex_test" for node in graph_result["nodes"]))

    def test_api_refuses_unauthenticated_network_bind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with patch("sys.stderr", io.StringIO()):
                exit_code = api_main(["--root", str(root), "--host", "0.0.0.0", "--port", "8765"])

        self.assertEqual(exit_code, 2)

    def test_api_smoke_exercises_local_rest_api_contract(self) -> None:
        steps = run_api_smoke()
        names = {step.name for step in steps}

        self.assertIn("health", names)
        self.assertIn("search", names)
        self.assertIn("graph", names)
        self.assertIn("proposal", names)
        self.assertIn("network_refusal", names)

    def test_provider_import_writes_review_candidates_and_rejects_secret_like_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            root.mkdir()
            (provider / "session.jsonl").write_text('{"message":"Remember codex setup notes."}\n', encoding="utf-8")
            secret = "sk-" + "proj-" + ("e" * 40)
            (provider / "secret.txt").write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")

            configure_provider(root, "codex", provider)
            result = import_chats(root, "codex")
            candidates = list((root / "inbox" / "imports" / "codex").glob("*.md"))
            candidate_text = candidates[0].read_text(encoding="utf-8")

        self.assertEqual(len(result["written"]), 1)
        self.assertEqual(len(candidates), 1)
        self.assertTrue(result["skipped"])
        self.assertIn("review candidate", candidate_text)

    def test_provider_import_rejects_symlinked_inbox_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            outside_inbox = Path(tmp) / "outside-inbox"
            provider.mkdir(parents=True)
            root.mkdir()
            outside_inbox.mkdir()
            (provider / "session.jsonl").write_text('{"message":"Review candidate."}\n', encoding="utf-8")
            configure_provider(root, "codex", provider)
            try:
                os.symlink(outside_inbox, root / "inbox", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                import_chats(root, "codex")

            self.assertEqual(list(outside_inbox.glob("**/*")), [])

    def test_capture_source_rejects_symlinked_import_dir_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside_imports = Path(tmp) / "outside-imports"
            root.mkdir()
            (root / "inbox").mkdir()
            outside_imports.mkdir()
            try:
                os.symlink(outside_imports, root / "inbox" / "imports", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                capture_source(root, "text", text="Review candidate.", title="Candidate")

            self.assertEqual(list(outside_imports.glob("**/*")), [])

    def test_mcp_capture_import_rejects_symlinked_kind_dir_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside_kind = Path(tmp) / "outside-text"
            root.mkdir()
            (root / "inbox" / "imports").mkdir(parents=True)
            outside_kind.mkdir()
            try:
                os.symlink(outside_kind, root / "inbox" / "imports" / "text", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                call_tool(
                    "memory.capture_import",
                    {"kind": "text", "text": "Review candidate.", "title": "Candidate"},
                    root,
                )

            self.assertEqual(list(outside_kind.glob("**/*")), [])

    def test_capture_source_writes_markdown_candidate_and_rejects_secret_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = Path(tmp) / "note.md"
            source.write_text("# Lesson\n\nUse local MCP stdio for memory.", encoding="utf-8")

            result = capture_source(root, "markdown", source_path=source)
            secret = "sk-" + "proj-" + ("i" * 40)
            secret_result = capture_source(root, "text", text=f"token {secret}", title="Secret text")
            candidate = root / result["written"][0]
            candidate_text = candidate.read_text(encoding="utf-8")

        self.assertTrue(result["written"][0].startswith("inbox/imports/markdown/"))
        self.assertEqual(secret_result["written"], [])
        self.assertEqual(secret_result["skipped"][0]["reason"], "secret-like content")
        self.assertIn("Use local MCP stdio", candidate_text)

    def test_capture_source_extracts_chatgpt_export_conversations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = Path(tmp) / "conversations.json"
            export.write_text(
                json.dumps(
                    [
                        {
                            "title": "Memory setup",
                            "mapping": {
                                "a": {
                                    "message": {
                                        "author": {"role": "user"},
                                        "create_time": 1,
                                        "content": {"parts": ["Remember this project uses review inboxes."]},
                                    }
                                },
                                "b": {
                                    "message": {
                                        "author": {"role": "assistant"},
                                        "create_time": 2,
                                        "content": {"parts": ["Capture proposals only."]},
                                    }
                                },
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )

            result = capture_source(root, "chatgpt", source_path=export)
            candidate_text = (root / result["written"][0]).read_text(encoding="utf-8")

        self.assertEqual(result["examined"], 1)
        self.assertTrue(result["written"][0].startswith("inbox/imports/chatgpt/"))
        self.assertIn("Memory setup", candidate_text)
        self.assertIn("user: Remember this project", candidate_text)
        self.assertIn("assistant: Capture proposals only.", candidate_text)

    def test_cli_capture_alias_reads_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output), patch("sys.stdin", io.StringIO("Review-first capture.")):
                exit_code = cli_main(["--root", str(root), "capture", "text", "--stdin", "--title", "CLI Capture", "--json"])

            result = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["written"][0].startswith("inbox/imports/text/"))

    def test_git_lessons_classify_and_write_review_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            (repo / "app.txt").write_text("initial\n", encoding="utf-8")
            git(repo, "add", "app.txt")
            git(repo, "commit", "-m", "initial commit")
            (repo / "app.txt").write_text("initial\nfix\n", encoding="utf-8")
            git(repo, "add", "app.txt")
            git(repo, "commit", "-m", "fix auth regression in build pipeline")

            result = learn_git(root, [repo], days=30, dry_run=False)
            duplicate_dry_run = learn_git(root, [repo], days=30, dry_run=True)
            duplicate_write = learn_git(root, [repo], days=30, dry_run=False)
            candidate_text = (root / result["written"][0]).read_text(encoding="utf-8")
            lesson_file_count = len(list((root / "inbox" / "git-lessons").glob("*.md")))

        self.assertEqual(result["examined"], 1)
        self.assertTrue(result["written"][0].startswith("inbox/git-lessons/"))
        self.assertIn("fix auth regression", candidate_text)
        self.assertIn("Categories:", candidate_text)
        self.assertIn("fingerprint:", candidate_text)
        self.assertEqual(duplicate_dry_run["written"], [])
        self.assertEqual(duplicate_dry_run["skipped"][0]["reason"], "already captured")
        self.assertTrue(duplicate_dry_run["skipped"][0]["existing"].startswith("inbox/git-lessons/"))
        self.assertEqual(duplicate_write["written"], [])
        self.assertEqual(duplicate_write["skipped"][0]["reason"], "already captured")
        self.assertEqual(lesson_file_count, 1)
        self.assertEqual(classify_commit("deploy hotfix for migration bug"), ["bug", "hotfix", "migration", "deploy"])

    def test_git_lessons_reject_secret_like_commit_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            secret = "sk-" + "proj-" + ("j" * 40)
            (repo / "app.txt").write_text("secret fixture\n", encoding="utf-8")
            git(repo, "add", "app.txt")
            git(repo, "commit", "-m", f"fix auth token {secret}")

            result = learn_git(root, [repo], days=30, dry_run=False)

        self.assertEqual(result["written"], [])
        self.assertTrue(result["skipped"])
        self.assertFalse((root / "inbox" / "git-lessons").exists())

    def test_cli_learn_git_alias_runs_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            (repo / "ci.yml").write_text("pipeline\n", encoding="utf-8")
            git(repo, "add", "ci.yml")
            git(repo, "commit", "-m", "fix ci workflow")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = cli_main(["--root", str(root), "learn", "--git", "--repo", str(repo), "--days", "30", "--dry-run", "--json"])

            result = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["examined"], 1)
        self.assertEqual(result["written"], [])
        self.assertEqual(result["candidates"][0]["categories"], ["fix", "ci"])
        self.assertFalse((root / "inbox" / "git-lessons").exists())

    def test_cli_learn_git_defaults_to_dry_run_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            (repo / "ci.yml").write_text("pipeline\n", encoding="utf-8")
            git(repo, "add", "ci.yml")
            git(repo, "commit", "-m", "fix ci workflow")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = cli_main(["--root", str(root), "learn", "--git", "--repo", str(repo), "--days", "30", "--json"])

            result = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["written"], [])
        self.assertEqual(result["examined"], 1)
        self.assertFalse((root / "inbox" / "git-lessons").exists())

    def test_cli_learn_git_write_flag_writes_review_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            (repo / "ci.yml").write_text("pipeline\n", encoding="utf-8")
            git(repo, "add", "ci.yml")
            git(repo, "commit", "-m", "fix ci workflow")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = cli_main(["--root", str(root), "learn", "--git", "--repo", str(repo), "--days", "30", "--write", "--json"])

            result = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["examined"], 1)
        self.assertEqual(len(result["written"]), 1)
        self.assertTrue(result["written"][0].startswith("inbox/git-lessons/"))

    def test_git_lessons_rejects_symlinked_inbox_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            outside_inbox = Path(tmp) / "outside-inbox"
            root.mkdir()
            repo.mkdir()
            outside_inbox.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            (repo / "ci.yml").write_text("pipeline\n", encoding="utf-8")
            git(repo, "add", "ci.yml")
            git(repo, "commit", "-m", "fix ci workflow")
            try:
                os.symlink(outside_inbox, root / "inbox", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                learn_git(root, [repo], days=30, dry_run=False)

            self.assertEqual(list(outside_inbox.glob("**/*")), [])

    def test_git_lessons_cli_dry_run_counts_duplicate_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            (repo / "app.txt").write_text("initial\n", encoding="utf-8")
            git(repo, "add", "app.txt")
            git(repo, "commit", "-m", "initial commit")
            (repo / "app.txt").write_text("initial\nfix\n", encoding="utf-8")
            git(repo, "add", "app.txt")
            git(repo, "commit", "-m", "fix auth regression in build pipeline")
            learn_git(root, [repo], days=30, dry_run=False)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = git_lessons_main(["--root", str(root), "--git", "--repo", str(repo), "--days", "30", "--dry-run"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Would write 0 git lesson candidate(s).", output.getvalue())
        self.assertIn("Skipped 1 repo/item(s).", output.getvalue())

    def test_git_lessons_cli_dry_run_counts_secret_like_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            secret = "sk-" + "proj-" + ("j" * 40)
            (repo / "app.txt").write_text("secret fixture\n", encoding="utf-8")
            git(repo, "add", "app.txt")
            git(repo, "commit", "-m", f"fix auth token {secret}")
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = git_lessons_main(["--root", str(root), "--git", "--repo", str(repo), "--days", "30", "--dry-run"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Would write 0 git lesson candidate(s).", output.getvalue())
        self.assertIn("Skipped 1 repo/item(s).", output.getvalue())

    def test_mcp_git_lessons_does_not_return_secret_like_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            repo = Path(tmp) / "repo"
            root.mkdir()
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            secret = "sk-" + "proj-" + ("j" * 40)
            (repo / "app.txt").write_text("secret fixture\n", encoding="utf-8")
            git(repo, "add", "app.txt")
            git(repo, "commit", "-m", f"fix auth token {secret}")

            result = call_tool(
                "memory.git_lessons",
                {"repo": str(repo), "days": 30, "limit": 5},
                root,
            )["result"]
            rendered = json.dumps(result)

        self.assertEqual(result["written"], [])
        self.assertEqual(result["candidates"], [])
        self.assertTrue(result["skipped"])
        self.assertNotIn(secret, rendered)
        self.assertFalse((root / "inbox" / "git-lessons").exists())

    def test_provider_detection_reports_configured_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            root.mkdir()
            configure_provider(root, "codex", provider)

            candidates = {candidate.name: candidate for candidate in detect_providers(root)}

        self.assertTrue(candidates["codex"].configured)
        self.assertTrue(candidates["codex"].enabled)
        self.assertTrue(candidates["codex"].exists)

    def test_provider_configure_dry_run_previews_without_writing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            root.mkdir()
            output = io.StringIO()

            preview = configure_provider_preview(root, "codex", provider)
            with patch("sys.stdout", output):
                exit_code = provider_main(
                    [
                        "--root",
                        str(root),
                        "configure",
                        "codex",
                        "--path",
                        str(provider),
                        "--dry-run",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            config_exists = (root / ".ai-dememory.toml").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(preview["provider"], "codex")
        self.assertEqual(preview["section"], "providers.codex")
        self.assertEqual(preview["config_path"], ".ai-dememory.toml")
        self.assertTrue(preview["path_exists"])
        self.assertTrue(preview["dry_run"])
        self.assertFalse(preview["mutates_config"])
        self.assertFalse(preview["writes_files"])
        self.assertFalse(preview["reads_provider_files"])
        self.assertFalse(preview["writes_import_candidates"])
        self.assertEqual(payload["values"]["path"], str(provider.resolve()))
        self.assertTrue(payload["path_exists"])
        self.assertFalse(config_exists)

    def test_provider_status_reports_import_readiness_without_importing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            root.mkdir()
            (provider / "session.jsonl").write_text('{"message":"Review candidate."}\n', encoding="utf-8")
            configure_provider(root, "codex", provider)
            configure_provider(root, "claude", Path(tmp) / "missing")

            status = providers_status(root)
            providers = {item["name"]: item for item in status["providers"]}
            inbox_exists = (root / "inbox" / "imports").exists()

        self.assertEqual(status["configured_count"], 2)
        self.assertEqual(status["enabled_count"], 2)
        self.assertEqual(status["import_ready_count"], 1)
        self.assertFalse(status["mutates_system"])
        self.assertTrue(providers["codex"]["import_ready"])
        self.assertEqual(providers["codex"]["reason"], "ready")
        self.assertFalse(providers["claude"]["import_ready"])
        self.assertEqual(providers["claude"]["reason"], "path_missing")
        self.assertFalse(inbox_exists)

    def test_provider_setup_plan_returns_reviewable_commands_without_importing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            root.mkdir()
            (provider / "session.jsonl").write_text('{"message":"Review candidate."}\n', encoding="utf-8")
            configure_provider(root, "codex", provider)

            plan = provider_setup_plan(root, command="ai-dememory")
            providers = {item["name"]: item for item in plan["providers"]}
            inbox_exists = (root / "inbox" / "imports").exists()

        self.assertFalse(plan["mutates_system"])
        self.assertFalse(plan["reads_provider_files"])
        self.assertFalse(plan["writes_import_candidates"])
        self.assertEqual(providers["codex"]["reason"], "ready_for_import")
        self.assertEqual(
            providers["codex"]["configure_command"],
            ["ai-dememory", "providers", "configure", "codex", "--path", str(provider.resolve())],
        )
        self.assertEqual(
            providers["codex"]["configure_dry_run_command"],
            ["ai-dememory", "providers", "configure", "codex", "--path", str(provider.resolve()), "--dry-run", "--json"],
        )
        self.assertEqual(providers["codex"]["import_dry_run_command"], ["ai-dememory", "import-chats", "codex", "--dry-run", "--json"])
        self.assertEqual(providers["codex"]["import_command"], ["ai-dememory", "import-chats", "codex"])
        self.assertFalse(inbox_exists)

    def test_provider_import_dry_run_reads_without_writing_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            root.mkdir()
            (provider / "session.jsonl").write_text('{"message":"Review candidate."}\n', encoding="utf-8")
            configure_provider(root, "codex", provider)

            dry_run = import_chats(root, "codex", dry_run=True)
            inbox_exists_after_dry_run = (root / "inbox" / "imports").exists()
            imported = import_chats(root, "codex")
            duplicate_dry_run = import_chats(root, "codex", dry_run=True)
            duplicate_import = import_chats(root, "codex")
            imported_text = (root / imported["written"][0]).read_text(encoding="utf-8")
            import_file_count = len(list((root / "inbox" / "imports" / "codex").glob("*.md")))

        self.assertTrue(dry_run["dry_run"])
        self.assertTrue(dry_run["reads_provider_files"])
        self.assertFalse(dry_run["writes_import_candidates"])
        self.assertEqual(dry_run["written"], [])
        self.assertEqual(len(dry_run["would_write"]), 1)
        self.assertTrue(dry_run["would_write"][0].startswith("inbox/imports/codex/"))
        self.assertFalse(inbox_exists_after_dry_run)
        self.assertFalse(imported["dry_run"])
        self.assertTrue(imported["writes_import_candidates"])
        self.assertTrue(imported["written"][0].startswith("inbox/imports/codex/"))
        self.assertIn("fingerprint:", imported_text)
        self.assertEqual(duplicate_dry_run["written"], [])
        self.assertEqual(duplicate_dry_run["would_write"], [])
        self.assertEqual(duplicate_dry_run["skipped"][0]["reason"], "already imported")
        self.assertTrue(duplicate_dry_run["skipped"][0]["existing"].startswith("inbox/imports/codex/"))
        self.assertEqual(duplicate_import["written"], [])
        self.assertFalse(duplicate_import["writes_import_candidates"])
        self.assertEqual(duplicate_import["skipped"][0]["reason"], "already imported")
        self.assertEqual(import_file_count, 1)

    def test_provider_import_cli_dry_run_emits_json_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            root.mkdir()
            (provider / "session.jsonl").write_text('{"message":"Review candidate."}\n', encoding="utf-8")
            configure_provider(root, "codex", provider)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = provider_main(["--root", str(root), "import", "codex", "--dry-run", "--json"])

            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["written"], [])
        self.assertEqual(len(payload["would_write"]), 1)
        self.assertFalse((root / "inbox" / "imports").exists())

    def test_setup_plan_returns_review_first_install_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()

            plan = setup_plan(root, client="codex", mode="both", command="ai-dememory", image="ai-dememory:test")
            mcp_configs = plan["commands"]["mcp_configs"]
            generated_reports = plan["commands"]["generated_reports"]
            generated_archive_status = plan["commands"]["generated_archive_status"]
            generated_archive_retention = plan["commands"]["generated_archive_retention"]

        self.assertFalse(plan["mutates_system"])
        self.assertFalse(plan["writes_files"])
        self.assertFalse(plan["reads_provider_files"])
        self.assertFalse(plan["writes_import_candidates"])
        self.assertFalse(plan["installs_schedules"])
        self.assertFalse(plan["installs_hooks"])
        self.assertTrue(plan["suggests_generated_reports"])
        self.assertTrue(plan["suggests_generated_archive_status"])
        self.assertTrue(plan["suggests_generated_archive_retention"])
        self.assertEqual(plan["commands"]["provider_plan"], ["ai-dememory", "providers", "plan", "--json"])
        self.assertEqual(plan["commands"]["schedule_environment"], ["ai-dememory", "schedule", "doctor", "--json"])
        self.assertEqual(plan["commands"]["schedule_plan"], ["ai-dememory", "schedule", "plan", "--json"])
        self.assertEqual(plan["commands"]["schedule_cron"], ["ai-dememory", "schedule", "cron"])
        self.assertEqual(
            plan["commands"]["docker_schedule_environment"],
            ["ai-dememory", "schedule", "doctor", "--json", "--mode", "docker"],
        )
        self.assertEqual(
            plan["commands"]["docker_schedule_plan"],
            ["ai-dememory", "schedule", "plan", "--json", "--mode", "docker", "--image", "ai-dememory:test"],
        )
        self.assertEqual(
            plan["commands"]["docker_schedule_cron"],
            ["ai-dememory", "schedule", "cron", "--mode", "docker", "--image", "ai-dememory:test"],
        )
        self.assertEqual(
            generated_reports["recall_review_plan"],
            ["ai-dememory", "recall-fixtures", "review-plan", "--write-report"],
        )
        self.assertEqual(
            generated_reports["recall_review_packet"],
            ["ai-dememory", "recall-fixtures", "packet", "--write-report"],
        )
        self.assertEqual(
            generated_reports["manual_acceptance_plan"],
            ["ai-dememory", "acceptance", "plan", "--write-report"],
        )
        self.assertEqual(
            generated_reports["manual_acceptance_packet"],
            ["ai-dememory", "acceptance", "packet", "--write-report"],
        )
        self.assertEqual(
            generated_reports["hook_capture_review"],
            ["ai-dememory", "hooks", "captures", "--write-report"],
        )
        self.assertEqual(generated_reports["release_evidence"], ["ai-dememory", "release-evidence", "--write-report"])
        self.assertEqual(
            generated_archive_status["recall_review_packets"],
            ["ai-dememory", "recall-fixtures", "packet-archive-status", "--json"],
        )
        self.assertEqual(
            generated_archive_status["manual_acceptance_packets"],
            ["ai-dememory", "acceptance", "packet-archive-status", "--json"],
        )
        self.assertEqual(
            generated_archive_retention["recall_review_packets"],
            ["ai-dememory", "recall-fixtures", "packet-archive-retention-plan", "--json"],
        )
        self.assertEqual(
            generated_archive_retention["manual_acceptance_packets"],
            ["ai-dememory", "acceptance", "packet-archive-retention-plan", "--json"],
        )
        self.assertEqual(len(mcp_configs), 2)
        self.assertEqual(mcp_configs[0][:6], ["ai-dememory", "mcp-config", "--client", "codex", "--mode", "installed"])
        self.assertIn("--image", mcp_configs[1])
        self.assertIn("provider_plan", plan)

    def test_setup_plan_human_output_includes_generated_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = setup_plan_main(["--root", str(root), "plan"])

        self.assertEqual(exit_code, 0)
        self.assertIn("- generated_reports:", output.getvalue())
        self.assertIn("- schedule_plan: ai-dememory schedule plan --json", output.getvalue())
        self.assertIn("- schedule_cron: ai-dememory schedule cron", output.getvalue())
        self.assertIn("recall_review_packet: ai-dememory recall-fixtures packet --write-report", output.getvalue())
        self.assertIn(
            "recall_review_packets: ai-dememory recall-fixtures packet-archive-status --json",
            output.getvalue(),
        )
        self.assertIn(
            "recall_review_packets: ai-dememory recall-fixtures packet-archive-retention-plan --json",
            output.getvalue(),
        )
        self.assertIn("manual_acceptance_plan: ai-dememory acceptance plan --write-report", output.getvalue())
        self.assertIn("manual_acceptance_packet: ai-dememory acceptance packet --write-report", output.getvalue())
        self.assertIn(
            "manual_acceptance_packets: ai-dememory acceptance packet-archive-status --json",
            output.getvalue(),
        )
        self.assertIn(
            "manual_acceptance_packets: ai-dememory acceptance packet-archive-retention-plan --json",
            output.getvalue(),
        )

    def test_daily_maintenance_builds_index_graph_weights_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")

            result = run_maintenance(root, "daily")
            index_exists = (root / "indexes" / "memory.sqlite").exists()
            graph_exists = (root / "indexes" / "memory-graph.json").exists()
            weights_exists = (root / "indexes" / "memory-weights.json").exists()
            lifecycle_scores_exists = (root / "indexes" / "memory-lifecycle.json").exists()
            lifecycle_report_exists = (root / "reports" / "lifecycle.md").exists()
            report_exists = (root / result.report).exists()
            weights = json.loads((root / "indexes" / "memory-weights.json").read_text(encoding="utf-8"))
            report_text = (root / result.report).read_text(encoding="utf-8")

        self.assertEqual(result.profile, "daily")
        self.assertEqual(result.index_count, 1)
        self.assertEqual(result.lifecycle_count, 1)
        self.assertEqual(result.lifecycle_scores, "indexes/memory-lifecycle.json")
        self.assertEqual(result.lifecycle_report, "reports/lifecycle.md")
        self.assertIsNone(result.hook_capture_report)
        self.assertIsNone(result.hook_captures)
        self.assertIsNone(result.sleep_plan_report)
        self.assertTrue(index_exists)
        self.assertTrue(graph_exists)
        self.assertTrue(weights_exists)
        self.assertTrue(lifecycle_scores_exists)
        self.assertTrue(lifecycle_report_exists)
        self.assertTrue(report_exists)
        self.assertIn("lifecycle_score", weights[0])
        self.assertIn("lifecycle_scores: `indexes/memory-lifecycle.json`", report_text)
        self.assertEqual(result.review_due["due_findings"], 0)
        self.assertEqual(result.review_due["stale_suppressions"], 0)
        self.assertEqual(result.conflict_review["active_conflicts"], 0)
        self.assertEqual(result.artifact_freshness["stale_count"], 0)
        self.assertFalse(result.artifact_freshness["writes_files"])
        self.assertFalse(result.artifact_freshness["artifacts"]["weights"]["stale"])
        self.assertEqual(result.generated_packet_archives["summary"]["total_count"], 0)
        self.assertFalse(result.generated_packet_archives["deletes_files"])
        self.assertIn("false_positive_review_due: `0`", report_text)
        self.assertIn("false_positive_stale_suppressions: `0`", report_text)
        self.assertIn("active_conflicts: `0`", report_text)
        self.assertIn("artifact_freshness_stale: `0`", report_text)
        self.assertIn("generated_packet_archive_prunable: `0`", report_text)
        self.assertIn("## Review Due", report_text)
        self.assertIn("## Conflict Review", report_text)
        self.assertIn("## Generated Artifact Freshness", report_text)
        self.assertIn("## Generated Packet Archives", report_text)

    def test_weekly_maintenance_writes_hook_capture_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            captured = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Review weekly hook capture."}')
            if captured is not None:
                text = captured.read_text(encoding="utf-8")
                captured.write_text(
                    "\n".join(
                        "review_after: 2026-06-20" if line.startswith("review_after: ") else line
                        for line in text.splitlines()
                    )
                    + "\n",
                    encoding="utf-8",
                )

            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                result = run_maintenance(root, "weekly")
            hook_report = root / "reports" / "hook-captures.md"
            sleep_report = root / "reports" / "sleep-plan.md"
            hook_report_exists = hook_report.exists()
            sleep_report_exists = sleep_report.exists()
            hook_report_text = hook_report.read_text(encoding="utf-8")
            sleep_report_text = sleep_report.read_text(encoding="utf-8")
            maintenance_report_text = (root / result.report).read_text(encoding="utf-8")
            status = maintenance_status(root)
            newer_capture = capture_hook_event(root, "Stop", '{"source":"newer hook capture"}')
            if newer_capture is not None:
                newer_mtime = hook_report.stat().st_mtime + 120
                os.utime(newer_capture, (newer_mtime, newer_mtime))
            weekly_freshness_after_new_capture = generated_artifact_freshness(root, profile="weekly")

        self.assertIsNotNone(captured)
        self.assertEqual(result.hook_capture_report, "reports/hook-captures.md")
        self.assertIsNotNone(result.hook_captures)
        self.assertEqual(result.sleep_plan_report, "reports/sleep-plan.md")
        self.assertEqual(result.hook_captures["review_due_count"], 1)
        self.assertTrue(hook_report_exists)
        self.assertTrue(sleep_report_exists)
        self.assertIn("# Hook Capture Review", hook_report_text)
        self.assertIn("# Sleep Consolidation Plan", sleep_report_text)
        self.assertIn("review_due: `true`", hook_report_text)
        self.assertIn("sleep_plan_report: `reports/sleep-plan.md`", maintenance_report_text)
        self.assertIn("hook_capture_report: `reports/hook-captures.md`", maintenance_report_text)
        self.assertIn("hook_capture_review_due: `1`", maintenance_report_text)
        self.assertIn("## Hook Captures", maintenance_report_text)
        self.assertTrue(status["artifacts"]["hook_capture_report"]["exists"])
        self.assertTrue(status["artifacts"]["sleep_plan_report"]["exists"])
        self.assertEqual(status["hook_captures"]["review_due_count"], 1)
        self.assertIsNotNone(newer_capture)
        self.assertTrue(weekly_freshness_after_new_capture["artifacts"]["hook_capture_report"]["stale"])
        self.assertEqual(weekly_freshness_after_new_capture["artifacts"]["hook_capture_report"]["status"], "stale")
        self.assertEqual(
            weekly_freshness_after_new_capture["artifacts"]["hook_capture_report"]["latest_source_path"],
            repo_relative_path(newer_capture, root),
        )

    def test_maintenance_dry_run_previews_imports_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            provider = Path(tmp) / "provider"
            provider.mkdir()
            (provider / "session.jsonl").write_text('{"message":"Review candidate."}\n', encoding="utf-8")
            configure_provider(root, "codex", provider)

            preview = dry_run_maintenance(root, "daily")
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = maintenance_main(["--root", str(root), "run", "--profile", "daily", "--dry-run", "--json"])
            payload = json.loads(output.getvalue())
            mcp_preview = call_tool("memory.maintenance_run", {"profile": "daily", "dry_run": True}, root)["result"]
            weekly_preview = dry_run_maintenance(root, "weekly")

        self.assertEqual(exit_code, 0)
        self.assertTrue(preview["dry_run"])
        self.assertFalse(preview["mutates_system"])
        self.assertFalse(preview["writes_files"])
        self.assertFalse(preview["writes_import_candidates"])
        self.assertTrue(preview["reads_provider_files"])
        self.assertEqual(len(preview["would_imports"]), 1)
        self.assertEqual(preview["would_imports"][0]["provider"], "codex")
        self.assertTrue(preview["would_imports"][0]["would_write"])
        self.assertIn("indexes/memory.sqlite", preview["would_generate"])
        self.assertFalse(preview["would_write_hook_capture_report"])
        self.assertIn("reports/hook-captures.md", weekly_preview["would_generate"])
        self.assertIn("reports/sleep-plan.md", weekly_preview["would_generate"])
        self.assertTrue(weekly_preview["would_write_hook_capture_report"])
        self.assertTrue(weekly_preview["would_write_sleep_plan_report"])
        self.assertTrue(preview["would_review_generated_packet_archives"])
        self.assertFalse(preview["would_delete_generated_packet_archives"])
        self.assertIn("artifact_freshness", preview)
        self.assertFalse(preview["artifact_freshness"]["writes_files"])
        self.assertTrue(preview["artifact_freshness"]["needs_maintenance"])
        self.assertEqual(payload["would_imports"][0]["provider"], "codex")
        self.assertFalse(payload["would_delete_generated_packet_archives"])
        self.assertIn("artifact_freshness", payload)
        self.assertEqual(mcp_preview["would_imports"][0]["provider"], "codex")
        self.assertFalse(mcp_preview["would_delete_generated_packet_archives"])
        self.assertIn("artifact_freshness", mcp_preview)
        self.assertFalse((root / "inbox").exists())
        self.assertFalse((root / "indexes").exists())
        self.assertFalse((root / "reports").exists())

    def test_daily_maintenance_writes_custom_in_root_report_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")

            result = run_maintenance(root, "daily", report_dir=Path("reports/custom-maintenance"))
            report_path = root / result.report
            report_text = report_path.read_text(encoding="utf-8")

        self.assertTrue(result.report.startswith("reports/custom-maintenance/"))
        self.assertTrue(result.report.endswith("-daily.md"))
        self.assertIn("Daily Maintenance", report_text)

    def test_maintenance_cli_rejects_outside_report_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            outside = Path(tmp) / "maintenance"
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = maintenance_main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "--profile",
                        "daily",
                        "--report-dir",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("maintenance report directory must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())
        self.assertFalse((root / "indexes").exists())
        self.assertFalse((root / "reports").exists())
        self.assertFalse((root / "inbox").exists())

    def test_maintenance_status_reports_generated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = maintenance_status(root)
            provider_dir = root / "provider"
            provider_dir.mkdir()
            configure_provider(root, "codex", provider_dir)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            missing_freshness = generated_artifact_freshness(root)
            run_maintenance(root, "daily")
            after = maintenance_status(root)
            fresh = generated_artifact_freshness(root)
            weekly_freshness = generated_artifact_freshness(root, profile="weekly")

        before_artifacts = before["artifacts"]
        after_artifacts = after["artifacts"]
        self.assertFalse(before_artifacts["index"]["exists"])
        self.assertIn("artifact_freshness", before)
        self.assertTrue(before["artifact_freshness"]["needs_maintenance"])
        self.assertEqual(missing_freshness["missing_count"], len(missing_freshness["artifacts"]))
        self.assertFalse(missing_freshness["writes_files"])
        self.assertEqual(before_artifacts["lifecycle_scores"]["path"], "indexes/memory-lifecycle.json")
        self.assertEqual(before_artifacts["hook_capture_report"]["path"], "reports/hook-captures.md")
        self.assertEqual(before_artifacts["sleep_plan_report"]["path"], "reports/sleep-plan.md")
        self.assertFalse(before_artifacts["hook_capture_report"]["exists"])
        self.assertFalse(before_artifacts["sleep_plan_report"]["exists"])
        self.assertNotIn("hook_capture_report", missing_freshness["artifacts"])
        self.assertNotIn("sleep_plan_report", missing_freshness["artifacts"])
        self.assertTrue(after_artifacts["index"]["exists"])
        self.assertTrue(after_artifacts["graph"]["exists"])
        self.assertTrue(after_artifacts["weights"]["exists"])
        self.assertTrue(after_artifacts["lifecycle_scores"]["exists"])
        self.assertTrue(after_artifacts["lifecycle_report"]["exists"])
        self.assertFalse(after_artifacts["hook_capture_report"]["exists"])
        self.assertIsInstance(after_artifacts["weights"]["updated_at"], str)
        self.assertEqual(fresh["stale_count"], 0)
        self.assertFalse(fresh["needs_maintenance"])
        self.assertEqual(fresh["next_action"], "Daily generated artifacts are current.")
        self.assertLess(fresh["missing_count"], missing_freshness["missing_count"])
        self.assertIn("hook_capture_report", weekly_freshness["artifacts"])
        self.assertTrue(weekly_freshness["needs_maintenance"])
        self.assertEqual(weekly_freshness["next_action"], "Run ai-dememory maintenance run --profile weekly.")
        self.assertFalse(fresh["artifacts"]["weights"]["stale"])
        self.assertIn("artifact_freshness", after)
        self.assertEqual(after["artifact_freshness"]["stale_count"], fresh["stale_count"])
        self.assertIn("provider_readiness", after)
        self.assertEqual(after["provider_readiness"]["import_ready_count"], 1)
        self.assertFalse(after["provider_readiness"]["reads_provider_files"])
        self.assertIn("review_due", after)
        self.assertEqual(after["review_due"]["due_findings"], 0)
        self.assertEqual(after["review_due"]["stale_suppressions"], 0)
        self.assertFalse(after["review_due"]["canonical_memory_updated"])
        self.assertIn("conflict_review", after)
        self.assertIn("hook_captures", after)
        self.assertFalse(after["hook_captures"]["reads_raw_payloads"])
        self.assertTrue(after["conflict_review"]["available"])
        self.assertEqual(after["conflict_review"]["active_conflicts"], 0)
        self.assertFalse(after["conflict_review"]["canonical_memory_updated"])
        self.assertIn("generated_packet_archives", after)
        self.assertEqual(after["generated_packet_archives"]["summary"]["total_count"], 0)
        self.assertFalse(after["generated_packet_archives"]["writes_files"])
        self.assertFalse(after["generated_packet_archives"]["deletes_files"])

    def test_maintenance_status_reports_generated_packet_archive_retention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            plan = paginate_acceptance_packet_plan(acceptance_plan(root))
            for index in range(31):
                write_acceptance_packet_archive(
                    root,
                    plan,
                    now=datetime(2026, 6, 1, 0, 0, index, tzinfo=timezone.utc),
                )

            before_paths = sorted((root / DEFAULT_ACCEPTANCE_PACKET_ARCHIVE_DIR).glob("*.md"))
            status = maintenance_status(root)
            mcp_status = call_tool("memory.maintenance_status", {}, root)
            result = run_maintenance(root, "daily")
            after_paths = sorted((root / DEFAULT_ACCEPTANCE_PACKET_ARCHIVE_DIR).glob("*.md"))
            report_text = (root / result.report).read_text(encoding="utf-8")

        archives = status["generated_packet_archives"]
        self.assertTrue(archives["available"])
        self.assertEqual(archives["summary"]["total_count"], 31)
        self.assertEqual(archives["summary"]["prunable_count"], 1)
        self.assertTrue(archives["summary"]["has_prunable"])
        self.assertEqual(archives["manual_acceptance_packets"]["total_count"], 31)
        self.assertEqual(archives["manual_acceptance_packets"]["retained_count"], 30)
        self.assertEqual(archives["manual_acceptance_packets"]["prunable_count"], 1)
        self.assertFalse(archives["writes_files"])
        self.assertFalse(archives["deletes_files"])
        self.assertEqual(mcp_status["generated_packet_archives"]["summary"]["prunable_count"], 1)
        self.assertFalse(mcp_status["generated_packet_archives"]["deletes_files"])
        self.assertEqual(result.generated_packet_archives["summary"]["prunable_count"], 1)
        self.assertIn("generated_packet_archive_prunable: `1`", report_text)
        self.assertIn("## Generated Packet Archives", report_text)
        self.assertIn('"deletes_files": false', report_text)
        self.assertEqual([path.name for path in before_paths], [path.name for path in after_paths])

    def test_maintenance_status_reports_due_false_positive_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "false-positive-fixture.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            finding = false_positive_reviews(root)[0]
            ignore_false_positive(root, finding.id, "Reviewed fixture.", "Unit Test", review_after_days=1)

            with patch("review_memory.today", return_value=date(2099, 1, 1)):
                summary = review_due_summary(root)
                status = maintenance_status(root)

        self.assertGreaterEqual(summary["false_positive_findings"], 1)
        self.assertEqual(summary["ignored_findings"], 1)
        self.assertEqual(summary["due_findings"], 1)
        self.assertEqual(summary["due_ids"], [finding.id])
        self.assertEqual(summary["status_counts"]["due"], 1)
        self.assertEqual(status["review_due"]["due_findings"], 1)
        self.assertEqual(status["review_due"]["due_ids"], [finding.id])
        self.assertEqual(status["review_due"]["stale_suppressions"], 0)
        self.assertFalse(status["review_due"]["canonical_memory_updated"])

    def test_maintenance_status_reports_stale_false_positive_suppressions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "false-positive-fixture.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            finding = false_positive_reviews(root)[0]
            ignore_false_positive(root, finding.id, "Reviewed fixture.", "Unit Test", review_after_days=1)
            path.unlink()

            with patch("review_memory.today", return_value=date(2099, 1, 1)):
                summary = review_due_summary(root)
                status = maintenance_status(root)
                result = run_maintenance(root, "daily")

            report_text = (root / result.report).read_text(encoding="utf-8")

        self.assertEqual(summary["false_positive_findings"], 0)
        self.assertEqual(summary["stale_suppressions"], 1)
        self.assertEqual(summary["stale_ids"], [finding.id])
        self.assertEqual(summary["stale_review_due"], 1)
        self.assertEqual(summary["stale_review_due_ids"], [finding.id])
        self.assertEqual(status["review_due"]["stale_suppressions"], 1)
        self.assertEqual(result.review_due["stale_suppressions"], 1)
        self.assertIn("false_positive_stale_suppressions: `1`", report_text)
        self.assertIn('"stale_review_due": 1', report_text)

    def test_maintenance_status_reports_conflict_review_follow_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_conflict_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_conflict_two")
            active = conflict_review_summary(root)
            conflict = conflict_reviews(root)[0]
            dismiss_conflict(root, conflict.id, "Intentional duplicate fixture.", "Unit Test")
            reviewed = conflict_review_summary(root)
            status = maintenance_status(root)
            result = run_maintenance(root, "daily")
            report_text = (root / result.report).read_text(encoding="utf-8")

        self.assertTrue(active["available"])
        self.assertEqual(active["conflicts"], 1)
        self.assertEqual(active["active_conflicts"], 1)
        self.assertEqual(active["active_ids"], [conflict.id])
        self.assertEqual(active["category_counts"], {"duplicate": 1})
        self.assertEqual(reviewed["active_conflicts"], 0)
        self.assertEqual(reviewed["reviewed_conflicts"], 1)
        self.assertEqual(reviewed["status_counts"], {"dismissed": 1})
        self.assertEqual(status["conflict_review"]["reviewed_conflicts"], 1)
        self.assertEqual(result.conflict_review["reviewed_conflicts"], 1)
        self.assertIn("active_conflicts: `0`", report_text)
        self.assertIn("## Conflict Review", report_text)
        self.assertIn('"reviewed_conflicts": 1', report_text)

    def test_maintenance_status_reports_review_recommendation_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            pending = capture_review_recommendation(
                root,
                kind="maintenance",
                target_id="maint_pending",
                recommendation="maintenance_follow_up",
                rationale="Review this pending maintenance follow-up.",
                recommended_by="Unit Test",
            )
            accepted = capture_review_recommendation(
                root,
                kind="conflict",
                target_id="conf_reviewed",
                recommendation="collect_evidence",
                rationale="Review this accepted conflict follow-up.",
                recommended_by="Unit Test",
            )
            record_review_recommendation_outcome(
                root,
                accepted.id,
                "accepted",
                "Unit Test",
                "Accepted for status coverage.",
            )

            summary = review_recommendation_summary(root)
            status = maintenance_status(root)
            result = run_maintenance(root, "daily")
            report_text = (root / result.report).read_text(encoding="utf-8")
            health = setup_health(root, target_platform="linux", mode="installed")
            mcp_status = call_tool("memory.maintenance_status", {}, root)

        self.assertTrue(summary["available"])
        self.assertEqual(summary["total_count"], 2)
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["rejected_count"], 0)
        self.assertEqual(summary["pending_ids"], [pending.id])
        self.assertEqual(summary["status_counts"], {"pending": 1, "accepted": 1, "rejected": 0})
        self.assertEqual(summary["kind_counts"], {"conflict": 1, "maintenance": 1})
        self.assertFalse(summary["applies_review_decisions"])
        self.assertFalse(summary["canonical_memory_updated"])
        self.assertEqual(status["review_recommendations"]["pending_ids"], [pending.id])
        self.assertEqual(result.review_recommendations["pending_count"], 1)
        self.assertIn("pending_review_recommendations: `1`", report_text)
        self.assertIn("## Review Recommendations", report_text)
        self.assertIn('"accepted_count": 1', report_text)
        self.assertEqual(health["review_recommendations"]["pending_ids"], [pending.id])
        self.assertTrue(any("review recommendations" in action for action in health["next_actions"]))
        self.assertEqual(mcp_status["review_recommendations"]["pending_count"], 1)
        self.assertFalse(mcp_status["review_recommendations"]["applies_review_decisions"])

    def test_schedule_plan_generates_windows_tasks_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = build_schedule_commands(root, "install", target_platform="windows")

        self.assertEqual({command.name for command in commands}, {"ai-dememory-daily", "ai-dememory-weekly"})
        self.assertTrue(all(command.command[0] == "schtasks" for command in commands))
        self.assertTrue(any("/SC" in command.command for command in commands))
        self.assertTrue(any(command.run_command and command.run_command[0] == "ai-dememory" for command in commands))

    def test_schedule_plan_supports_docker_maintenance_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = build_schedule_commands(
                root,
                "install",
                mode="docker",
                image="ai-dememory:test",
                target_platform="windows",
            )

        daily = next(command for command in commands if command.name == "ai-dememory-daily")
        self.assertIsNotNone(daily.run_command)
        self.assertEqual(daily.run_command[:2], ["docker", "run"])
        self.assertIn("AI_DEMEMORY_ROOT=/memory", daily.run_command)
        self.assertIn(f"{root}:/memory", daily.run_command)
        self.assertIn("ai-dememory:test", daily.run_command)
        self.assertIn("maintenance", daily.command[daily.command.index("/TR") + 1])

    def test_schedule_plan_uses_windows_quoting_for_schtasks_run_command(self) -> None:
        root = Path("C:/Vault Path")
        commands = build_schedule_commands(
            root,
            "install",
            mode="docker",
            image="ai-dememory:test",
            target_platform="windows",
        )

        daily = next(command for command in commands if command.name == "ai-dememory-daily")
        run_line = daily.command[daily.command.index("/TR") + 1]
        volume_arg = f"{root}:/memory"
        self.assertIn(f'-v "{volume_arg}"', run_line)
        self.assertNotIn(f"'{volume_arg}'", run_line)
        self.assertIn("ai-dememory:test maintenance run --profile daily", run_line)

    def test_schedule_cron_export_generates_installed_and_docker_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = build_cron_entries(root, daily_time="01:15", weekly_day="MON", weekly_time="02:30")
            docker = build_cron_entries(
                root,
                mode="docker",
                image="ai-dememory:test",
                daily_time="03:05",
                weekly_day="SAT",
                weekly_time="04:10",
            )
            rendered = render_cron_entries(installed)

        self.assertEqual(installed[0].schedule, "15 1 * * *")
        self.assertEqual(installed[1].schedule, "30 2 * * 1")
        self.assertIn("ai-dememory maintenance run --profile daily", installed[0].line)
        self.assertEqual(docker[0].schedule, "5 3 * * *")
        self.assertEqual(docker[1].schedule, "10 4 * * 6")
        self.assertEqual(docker[0].command[:2], ["docker", "run"])
        self.assertIn("ai-dememory:test", docker[0].command)
        self.assertIn("# ai-dememory maintenance schedule", rendered)

    def test_schedule_cron_export_shell_quotes_metacharacters(self) -> None:
        root = Path("vault's;$(touch pwn)`")
        installed = build_cron_entries(root, command="ai-dememory;touch pwn")
        docker = build_cron_entries(root, mode="docker", image="ai-dememory:local;touch pwn")

        self.assertIn("'ai-dememory;touch pwn'", installed[0].line)
        self.assertIn("'vault'\"'\"'s;$(touch pwn)`'", installed[0].line)
        self.assertNotIn(" ai-dememory;touch pwn maintenance ", installed[0].line)
        self.assertIn("'vault'\"'\"'s;$(touch pwn)`:/memory'", docker[0].line)
        self.assertIn("'ai-dememory:local;touch pwn'", docker[0].line)
        self.assertNotIn(" ai-dememory:local;touch pwn maintenance ", docker[0].line)

    def test_schedule_plan_cli_reports_commands_and_cron_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            plan = schedule_plan(
                root,
                target_platform="linux",
                mode="docker",
                image="ai-dememory:test",
                daily_time="01:15",
                weekly_day="MON",
                weekly_time="02:30",
            )
            with patch("sys.stdout", output):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "plan",
                        "--platform",
                        "linux",
                        "--mode",
                        "docker",
                        "--image",
                        "ai-dememory:test",
                        "--daily-time",
                        "01:15",
                        "--weekly-day",
                        "MON",
                        "--weekly-time",
                        "02:30",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, plan)
        self.assertEqual(payload["action"], "install")
        self.assertEqual(payload["platform"], "linux")
        self.assertEqual(payload["mode"], "docker")
        self.assertFalse(payload["mutates_system"])
        self.assertFalse(payload["runs_commands"])
        self.assertFalse(payload["writes_files"])
        self.assertFalse(payload["installs_schedules"])
        self.assertFalse((root / ".ai-dememory.toml").exists())
        self.assertTrue(any(command["command"][:2] == ["systemctl", "--user"] for command in payload["commands"]))
        self.assertTrue(any(entry["command"][:2] == ["docker", "run"] for entry in payload["cron_entries"]))

    def test_mcp_schedule_plan_matches_cli_scheduler_plan_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = schedule_plan(root, target_platform="linux")

            payload = call_tool("memory.schedule_plan", {"platform": "linux", "action": "install"}, root)

        self.assertEqual(payload, expected)
        schedule_plan_tool = next(tool for tool in TOOLS if tool["name"] == "memory.schedule_plan")
        output_schema = schedule_plan_tool["outputSchema"]
        schema_keys = set(output_schema["properties"])
        self.assertEqual(set(payload) - schema_keys, set())
        self.assertEqual(set(output_schema["required"]), set(payload))
        self.assertFalse(output_schema["additionalProperties"])
        self.assertEqual(len(payload["cron_entries"]), 2)
        self.assertFalse(payload["mutates_system"])
        self.assertFalse(payload["installs_schedules"])

    def test_schedule_environment_reports_required_and_optional_commands(self) -> None:
        def fake_which(command: str) -> str | None:
            return f"/usr/bin/{command}" if command in {"systemctl", "crontab"} else None

        with patch("schedule_memory.shutil.which", side_effect=fake_which):
            installed = schedule_environment(target_platform="linux", mode="installed")
            docker = schedule_environment(target_platform="linux", mode="docker")

        self.assertTrue(installed["ready"])
        self.assertFalse(installed["mutates_system"])
        self.assertFalse(installed["runs_commands"])
        self.assertEqual(installed["required_missing"], [])
        docker_check = next(check for check in installed["checks"] if check["name"] == "docker")
        self.assertFalse(docker_check["required"])
        self.assertFalse(docker_check["available"])
        self.assertFalse(docker["ready"])
        self.assertEqual(docker["required_missing"], ["docker"])

    def test_schedule_doctor_cli_reports_environment_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("schedule_memory.shutil.which", return_value=None), patch("sys.stdout", output):
                exit_code = schedule_main(["--root", str(root), "doctor", "--platform", "windows", "--json"])

            result = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["platform"], "windows")
        self.assertFalse(result["ready"])
        self.assertFalse(result["mutates_system"])
        self.assertFalse(result["runs_commands"])
        self.assertFalse((root / ".ai-dememory.toml").exists())

    def test_schedule_rejects_invalid_time_and_weekday_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaisesRegex(ValueError, "daily_time"):
                build_cron_entries(root, daily_time="25:00")
            with self.assertRaisesRegex(ValueError, "weekly_day"):
                build_schedule_commands(root, "install", weekly_day="FUNDAY", target_platform="windows")
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    schedule_main(["--root", str(root), "cron", "--weekly-day", "FUNDAY"])

        self.assertEqual(error.exception.code, 2)

    def test_schedule_status_reports_invalid_config_without_status_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            (root / ".ai-dememory.toml").write_text(
                '[schedule]\nenabled = true\ndaily_time = "01:15"\nweekly_day = "FUNDAY"\nweekly_time = "02:30"\n',
                encoding="utf-8",
            )

            status = schedule_status(root, target_platform="linux")

        self.assertTrue(status["configured"])
        self.assertFalse(status["valid"])
        self.assertTrue(status["validation_errors"])
        self.assertEqual(status["status_commands"], [])

    def test_mcp_schedule_status_reports_invalid_config_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            (root / ".ai-dememory.toml").write_text(
                '[schedule]\nenabled = true\ndaily_time = "01:15"\nweekly_day = "FUNDAY"\nweekly_time = "02:30"\n',
                encoding="utf-8",
            )

            status = call_tool("memory.schedule_status", {"platform": "linux"}, root)

        self.assertTrue(status["configured"])
        self.assertFalse(status["valid"])
        self.assertTrue(status["validation_errors"])
        self.assertEqual(status["status_commands"], [])
        self.assertFalse(status["mutates_system"])

    def test_schedule_status_reports_review_due_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            configure_schedule(root, "01:15", "MON", "02:30", "installed", "")
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "false-positive-fixture.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            finding = false_positive_reviews(root)[0]
            ignore_false_positive(root, finding.id, "Reviewed fixture.", "Unit Test", review_after_days=1)

            with patch("review_memory.today", return_value=date(2099, 1, 1)):
                status = schedule_status(root, target_platform="linux")
                mcp_status = call_tool("memory.schedule_status", {"platform": "linux"}, root)

        self.assertTrue(status["configured"])
        self.assertTrue(status["valid"])
        self.assertEqual(status["review_due"]["due_findings"], 1)
        self.assertEqual(status["review_due"]["due_ids"], [finding.id])
        self.assertEqual(status["review_due"]["stale_suppressions"], 0)
        self.assertFalse(status["review_due"]["canonical_memory_updated"])
        self.assertEqual(mcp_status["review_due"]["due_findings"], 1)
        self.assertEqual(mcp_status["review_due"]["due_ids"], [finding.id])
        self.assertFalse(mcp_status["mutates_system"])

    def test_schedule_dry_run_does_not_write_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = schedule_main(["--root", str(root), "setup", "--dry-run", "--platform", "windows"])

            config_exists = (root / ".ai-dememory.toml").exists()
            commands = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertFalse(config_exists)
        self.assertEqual(len(commands), 2)

    def test_schedule_status_reports_configured_state_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            unconfigured = schedule_status(root, target_platform="linux")
            configure_schedule(root, "01:15", "MON", "02:30", "docker", "ai-dememory:test")
            configured = schedule_status(root, target_platform="linux")

        self.assertFalse(unconfigured["configured"])
        self.assertTrue(configured["configured"])
        self.assertEqual(configured["platform"], "linux")
        self.assertEqual(configured["mode"], "docker")
        self.assertEqual(configured["image"], "ai-dememory:test")
        self.assertFalse(configured["mutates_system"])
        self.assertEqual(configured["schedule"]["daily_time"], "01:15")
        self.assertEqual(configured["schedule"]["weekly_day"], "MON")
        self.assertEqual(configured["schedule"]["weekly_time"], "02:30")
        self.assertIn("review_due", configured)
        self.assertEqual(configured["review_due"]["due_findings"], 0)
        self.assertEqual(configured["review_due"]["stale_suppressions"], 0)
        self.assertEqual(len(configured["status_commands"]), 2)
        self.assertTrue(all(item["action"] == "status" for item in configured["status_commands"]))

    def test_schedule_plan_generates_linux_and_macos_install_remove_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            linux_install = build_schedule_commands(root, "install", target_platform="linux")
            linux_remove = build_schedule_commands(root, "remove", target_platform="linux")
            macos_install = build_schedule_commands(root, "install", target_platform="macos")
            macos_remove = build_schedule_commands(root, "remove", target_platform="macos")

        self.assertEqual(linux_install[0].command, ["systemctl", "--user", "daemon-reload"])
        self.assertTrue(any(command.command[:3] == ["systemctl", "--user", "enable"] for command in linux_install))
        self.assertTrue(all("disable" in command.command for command in linux_remove))
        self.assertTrue(all(command.command[:2] == ["launchctl", "load"] for command in macos_install))
        self.assertTrue(all(command.command[:2] == ["launchctl", "unload"] for command in macos_remove))

    def test_setup_health_summarizes_read_only_local_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()

            health = setup_health(root, target_platform="linux", mode="installed")
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = setup_plan_main(["--root", str(root), "health", "--platform", "linux", "--json"])
            payload = json.loads(output.getvalue())
            mcp_health = call_tool("memory.setup_health", {"platform": "linux", "mode": "installed"}, root)

        self.assertEqual(exit_code, 0)
        self.assertEqual(health["platform"], "linux")
        self.assertEqual(payload["platform"], "linux")
        self.assertEqual(mcp_health["platform"], "linux")
        self.assertFalse(health["mutates_system"])
        self.assertFalse(health["runs_commands"])
        self.assertFalse(health["writes_files"])
        self.assertIn("validation_status", health)
        self.assertTrue(health["validation_status"]["ok"])
        self.assertEqual(health["validation_status"]["exit_code"], 0)
        self.assertIn("recall_review", health)
        self.assertFalse(health["recall_review"]["available"])
        self.assertEqual(health["recall_review"]["status"], "unavailable")
        self.assertIn("context_config", health)
        self.assertTrue(health["context_config"]["valid"])
        self.assertIn("manual_acceptance", health)
        self.assertFalse(health["manual_acceptance"]["complete"])
        self.assertEqual(health["manual_acceptance"]["remaining_count"], len(ACCEPTANCE_ITEMS))
        self.assertFalse(health["manual_acceptance"]["records_evidence"])
        self.assertIn("vector_readiness", health)
        self.assertFalse(health["vector_readiness"]["available"])
        self.assertEqual(health["vector_readiness"]["decision"], "unavailable")
        self.assertFalse(health["vector_readiness"]["creates_embeddings"])
        self.assertIn("schedule_environment", health)
        self.assertIn("schedule_status", health)
        self.assertIn("hook_status", health)
        self.assertIn("provider_readiness", health)
        self.assertIn("maintenance_preflight", health)
        self.assertIn("generated_packet_archives", health)
        self.assertTrue(health["generated_packet_archives"]["available"])
        self.assertEqual(health["generated_packet_archives"]["summary"]["total_count"], 0)
        self.assertFalse(health["generated_packet_archives"]["writes_files"])
        self.assertFalse(health["generated_packet_archives"]["deletes_files"])
        self.assertIn("review_due", health)
        self.assertIn("conflict_review", health)
        self.assertIn("artifacts", health)
        self.assertIn("artifact_freshness", health)
        self.assertTrue(health["artifact_freshness"]["needs_maintenance"])
        self.assertFalse(health["artifact_freshness"]["writes_files"])
        self.assertTrue(health["next_actions"])
        self.assertTrue(any("generated artifacts" in action for action in health["next_actions"]))
        self.assertFalse(mcp_health["mutates_system"])
        self.assertFalse(mcp_health["runs_commands"])
        self.assertFalse(mcp_health["writes_files"])
        self.assertIn("validation_status", mcp_health)
        self.assertTrue(mcp_health["validation_status"]["ok"])
        self.assertIn("recall_review", mcp_health)
        self.assertEqual(mcp_health["recall_review"]["status"], "unavailable")
        self.assertIn("context_config", mcp_health)
        self.assertTrue(mcp_health["context_config"]["valid"])
        self.assertIn("manual_acceptance", mcp_health)
        self.assertFalse(mcp_health["manual_acceptance"]["complete"])
        self.assertFalse(mcp_health["manual_acceptance"]["records_evidence"])
        self.assertIn("vector_readiness", mcp_health)
        self.assertFalse(mcp_health["vector_readiness"]["creates_embeddings"])
        self.assertIn("hook_status", mcp_health)
        self.assertIn("generated_packet_archives", mcp_health)
        self.assertEqual(mcp_health["generated_packet_archives"]["summary"]["prunable_count"], 0)
        self.assertFalse(mcp_health["generated_packet_archives"]["deletes_files"])
        self.assertIn("artifact_freshness", mcp_health)
        self.assertFalse(mcp_health["artifact_freshness"]["writes_files"])
        self.assertFalse(mcp_health["hook_status"]["writes_files"])
        self.assertIn("captures", mcp_health["hook_status"])
        self.assertFalse(mcp_health["hook_status"]["captures"]["reads_raw_payloads"])
        self.assertFalse(health["maintenance_preflight"]["reads_provider_files"])
        self.assertFalse(health["maintenance_preflight"]["writes_files"])
        self.assertFalse(health["maintenance_preflight"]["writes_import_candidates"])
        self.assertIn("indexes/memory.sqlite", health["maintenance_preflight"]["daily_artifacts"])
        self.assertEqual(
            payload["maintenance_preflight"]["daily_dry_run_command"],
            ["ai-dememory", "maintenance", "run", "--profile", "daily", "--dry-run", "--json"],
        )
        self.assertEqual(
            mcp_health["maintenance_preflight"]["weekly_dry_run_command"],
            ["ai-dememory", "maintenance", "run", "--profile", "weekly", "--dry-run", "--json"],
        )
        self.assertTrue(any("quality/recall-fixtures.json" in action for action in health["recall_review"]["next_actions"]))

    def test_setup_health_reports_generated_packet_archive_retention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            plan = paginate_acceptance_packet_plan(acceptance_plan(root))
            for index in range(31):
                write_acceptance_packet_archive(
                    root,
                    plan,
                    now=datetime(2026, 6, 1, 0, 0, index, tzinfo=timezone.utc),
                )

            health = setup_health(root, target_platform="linux", mode="installed")
            mcp_health = call_tool("memory.setup_health", {"platform": "linux", "mode": "installed"}, root)

        archives = health["generated_packet_archives"]
        self.assertTrue(archives["available"])
        self.assertEqual(archives["summary"]["total_count"], 31)
        self.assertEqual(archives["summary"]["prunable_count"], 1)
        self.assertTrue(archives["summary"]["has_prunable"])
        self.assertEqual(archives["manual_acceptance_packets"]["total_count"], 31)
        self.assertEqual(archives["manual_acceptance_packets"]["retained_count"], 30)
        self.assertEqual(archives["manual_acceptance_packets"]["prunable_count"], 1)
        self.assertFalse(archives["writes_files"])
        self.assertFalse(archives["deletes_files"])
        self.assertFalse(archives["records_evidence"])
        self.assertTrue(any("generated packet archive retention" in action for action in health["next_actions"]))
        self.assertEqual(mcp_health["generated_packet_archives"]["summary"]["prunable_count"], 1)
        self.assertFalse(mcp_health["generated_packet_archives"]["deletes_files"])

    def test_setup_health_reports_pending_recall_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir()
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "seed",
                            "query": "setup health recall",
                            "expected_ids": ["mem_setup_recall"],
                            "min_rank": 3,
                            "created_at": "2026-06-17",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            capture_miss(
                root,
                "missing setup health recall",
                "Expected setup health recall memory was absent.",
                expected_id="mem_setup_recall",
            )

            health = setup_health(root, target_platform="linux", mode="installed")

        self.assertEqual(health["recall_review"]["status"], "pending_review")
        self.assertTrue(health["recall_review"]["available"])
        self.assertEqual(health["recall_review"]["pending_count"], 1)
        self.assertFalse(health["vector_readiness"]["available"])
        self.assertIn("index", health["vector_readiness"]["rationale"])
        self.assertFalse(health["vector_readiness"]["creates_embeddings"])
        self.assertTrue(any("pending recall misses" in action for action in health["next_actions"]))

    def test_setup_health_reports_vector_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            write_memory(
                root,
                "memories/tools/vector.md",
                memory_id="mem_vector_test",
                title="Vector Readiness Memory",
                body="Vector readiness stays deferred while recall fixtures pass.",
            )
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir()
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "vector-ready",
                            "query": "vector readiness recall fixtures",
                            "expected_ids": ["mem_vector_test"],
                            "min_rank": 5,
                            "created_at": "2026-06-17",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            health = setup_health(root, target_platform="linux", mode="installed")

        self.assertTrue(health["vector_readiness"]["available"])
        self.assertEqual(health["vector_readiness"]["decision"], "not_justified")
        self.assertEqual(health["vector_readiness"]["recall"]["failed_cases"], 0)
        self.assertFalse(health["vector_readiness"]["creates_embeddings"])

    def test_setup_health_reports_invalid_context_config_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[context]",
                        'default_budget_tokens = "tiny"',
                        "include_working_memory = maybe",
                        "explain_results = sometimes",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            health = setup_health(root, target_platform="linux", mode="installed")
            mcp_health = call_tool("memory.setup_health", {"platform": "linux", "mode": "installed"}, root)

        self.assertFalse(health["context_config"]["valid"])
        self.assertEqual(
            health["context_config"]["settings"]["default_budget_tokens"]["source"],
            "defaulted_invalid",
        )
        self.assertEqual(health["context_config"]["settings"]["default_budget_tokens"]["value"], 2000)
        self.assertEqual(
            health["context_config"]["settings"]["include_working_memory"]["source"],
            "defaulted_invalid",
        )
        self.assertEqual(
            health["context_config"]["settings"]["explain_results"]["source"],
            "defaulted_invalid",
        )
        self.assertTrue(health["context_config"]["errors"])
        self.assertTrue(any("[context]" in action for action in health["next_actions"]))
        self.assertFalse(mcp_health["context_config"]["valid"])

    def test_setup_health_reports_manual_acceptance_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            record_acceptance(
                root,
                "mcp-client-installed",
                "blocked",
                "Reviewer",
                "MCP GUI client was not available on this workstation.",
                artifacts=["manual note"],
            )

            health = setup_health(root, target_platform="linux", mode="installed")

        self.assertFalse(health["manual_acceptance"]["complete"])
        self.assertEqual(health["manual_acceptance"]["total"], len(ACCEPTANCE_ITEMS))
        self.assertEqual(health["manual_acceptance"]["completed_count"], 0)
        self.assertEqual(health["manual_acceptance"]["blocked_count"], 1)
        self.assertEqual(health["manual_acceptance"]["remaining_count"], len(ACCEPTANCE_ITEMS))
        self.assertTrue(any("blocked manual acceptance" in action for action in health["next_actions"]))
        self.assertTrue(any("remaining manual acceptance" in action for action in health["next_actions"]))

    def test_setup_health_reports_validation_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            bad_path = root / "memories" / "tools" / "bad.md"
            bad_path.parent.mkdir(parents=True)
            bad_path.write_text("---\nid: mem_bad\n---\n\n# Bad\n", encoding="utf-8")

            health = setup_health(root, target_platform="linux", mode="installed")

        self.assertFalse(health["ready"])
        self.assertFalse(health["validation_status"]["ok"])
        self.assertEqual(health["validation_status"]["exit_code"], 1)
        self.assertTrue(health["validation_status"]["errors"])
        self.assertTrue(any("validate --json" in action for action in health["next_actions"]))

    def test_setup_health_reports_due_hook_captures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            captured = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Review hook capture."}')
            if captured is not None:
                text = captured.read_text(encoding="utf-8")
                captured.write_text(
                    "\n".join(
                        "review_after: 2026-06-20" if line.startswith("review_after: ") else line
                        for line in text.splitlines()
                    )
                    + "\n",
                    encoding="utf-8",
                )

            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                health = setup_health(root, target_platform="linux", mode="installed")

        self.assertIsNotNone(captured)
        self.assertEqual(health["hook_status"]["captures"]["review_due_count"], 1)
        self.assertTrue(any("hook capture" in action for action in health["next_actions"]))

    def test_release_check_validates_codex_plugin_structure(self) -> None:
        result = check_codex_plugin(ROOT)

        self.assertEqual(result.status, "ok")
        self.assertIn(f"{len(EXPECTED_PLUGIN_MCP_TOOLS)} tools", result.detail)
        self.assertIn(f"{len(EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS)} server-only tools classified", result.detail)
        self.assertIn("5 skills", result.detail)

    def test_release_check_classifies_every_mcp_tool_for_plugin_boundary(self) -> None:
        inventory = build_inventory(ROOT)
        classified = set(EXPECTED_PLUGIN_MCP_TOOLS) | set(EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS)

        self.assertEqual(set(inventory["tools"]) - classified, set())
        self.assertEqual(classified - set(inventory["tools"]), set())
        self.assertEqual(set(EXPECTED_PLUGIN_MCP_TOOLS) & set(EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS), set())

    def test_codex_plugin_working_session_skill_documents_review_boundary(self) -> None:
        path = ROOT / "plugins" / "ai-dememory" / "skills" / "memory-working-session" / "SKILL.md"
        text = path.read_text(encoding="utf-8")

        self.assertIn("name: memory-working-session", text)
        self.assertIn("memory.working_current", text)
        self.assertIn("memory.working_status", text)
        self.assertIn("memory.working_snapshot", text)
        self.assertIn("memory.working_handoff", text)
        self.assertIn("not canonical durable memory", text)

    def test_mcp_inventory_matches_documented_tool_surface(self) -> None:
        inventory = build_inventory(ROOT)
        issues = validate_inventory_docs(ROOT)

        self.assertEqual(inventory["tool_count"], len(TOOLS))
        self.assertEqual(inventory["tool_count"], 74)
        self.assertFalse(issues)

    def test_mcp_inventory_text_validation_catches_stale_docs(self) -> None:
        inventory = {"tool_count": 2, "tools": ["memory.one", "memory.two"]}
        documents = {
            "README.md": "2 MCP tools\n- `memory.one`",
            "docs/adr/0010-mcp-inventory-drift-check.md": "1 MCP tools",
            "docs/adr/0088-mcp-client-tools-list-pagination-smoke.md": "2 MCP tools",
            "docs/mcp-v2-gap-analysis.md": "1 MCP tools",
            "mcp/README.md": "2 MCP tools\n- `memory.one`",
            "mcp/server/README.md": "2 MCP tools",
        }

        issues = validate_inventory_texts(inventory, documents)

        self.assertTrue(any(issue.target == "docs/mcp-v2-gap-analysis.md" for issue in issues))
        self.assertTrue(any(issue.target == "docs/adr/0010-mcp-inventory-drift-check.md" for issue in issues))
        self.assertTrue(any(issue.target == "README.md" and "memory.two" in issue.message for issue in issues))
        self.assertTrue(any(issue.target == "mcp/README.md" and "memory.two" in issue.message for issue in issues))

    def test_mcp_inventory_text_validation_requires_exact_tool_names(self) -> None:
        inventory = {
            "tool_count": 2,
            "tools": ["memory.review_recommendation", "memory.review_recommendations"],
        }
        documents = {
            "README.md": "2 MCP tools\n- `memory.review_recommendations`",
            "docs/adr/0010-mcp-inventory-drift-check.md": "2 MCP tools",
            "docs/adr/0088-mcp-client-tools-list-pagination-smoke.md": "2 MCP tools",
            "docs/mcp-v2-gap-analysis.md": "2 MCP tools",
            "mcp/README.md": "2 MCP tools\n- `memory.review_recommendations`",
            "mcp/server/README.md": "2 MCP tools",
        }

        issues = validate_inventory_texts(inventory, documents)

        self.assertTrue(
            any(issue.target == "README.md" and "memory.review_recommendation" in issue.message for issue in issues)
        )
        self.assertTrue(
            any(issue.target == "mcp/README.md" and "memory.review_recommendation" in issue.message for issue in issues)
        )

    def test_install_smoke_validates_mcp_initialize_and_ping(self) -> None:
        good = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        with_notification = (
            '{"jsonrpc":"2.0","method":"notifications/message","params":{"level":"info"}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
        )
        bad = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        missing_ping = '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
        unexpected_id = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":99,"result":{}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        invalid_id = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":"2","result":{}}\n'
        )
        null_id = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":null,"result":{}}\n'
        )
        duplicate_id = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        missing_result = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":2}\n'
        )
        non_object_initialize = (
            '{"jsonrpc":"2.0","id":1,"result":[]}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        non_object_ping = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":2,"result":[]}\n'
        )
        missing_protocol = (
            '{"jsonrpc":"2.0","id":1,"result":{}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        invalid_protocol = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":20251125}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )

        assert_mcp_initialize_and_ping(good)
        assert_mcp_initialize_and_ping(with_notification)
        with self.assertRaises(InstallSmokeError):
            assert_mcp_initialize_and_ping(bad)
        with self.assertRaisesRegex(InstallSmokeError, "ping response id 2 was missing"):
            assert_mcp_initialize_and_ping(missing_ping)
        with self.assertRaisesRegex(InstallSmokeError, "unexpected response id"):
            assert_mcp_initialize_and_ping(unexpected_id)
        with self.assertRaisesRegex(InstallSmokeError, "non-integer response id"):
            assert_mcp_initialize_and_ping(invalid_id)
        with self.assertRaisesRegex(InstallSmokeError, "non-integer response id"):
            assert_mcp_initialize_and_ping(null_id)
        with self.assertRaisesRegex(InstallSmokeError, "duplicate response id"):
            assert_mcp_initialize_and_ping(duplicate_id)
        with self.assertRaisesRegex(InstallSmokeError, "did not include result or error"):
            assert_mcp_initialize_and_ping(missing_result)
        with self.assertRaisesRegex(InstallSmokeError, "initialize returned a non-object result"):
            assert_mcp_initialize_and_ping(non_object_initialize)
        with self.assertRaisesRegex(InstallSmokeError, "ping returned a non-object result"):
            assert_mcp_initialize_and_ping(non_object_ping)
        with self.assertRaisesRegex(InstallSmokeError, "missing protocolVersion"):
            assert_mcp_initialize_and_ping(missing_protocol)
        with self.assertRaisesRegex(InstallSmokeError, "protocolVersion was not a string"):
            assert_mcp_initialize_and_ping(invalid_protocol)
        payload = [json.loads(line) for line in mcp_payload().splitlines()]
        self.assertEqual([message.get("method") for message in payload], ["initialize", "notifications/initialized", "ping"])

    def test_install_smoke_validates_doctor_summary(self) -> None:
        good = json.dumps(
            {
                "profile": "vault",
                "summary": {"ok": 4, "warn": 1, "fail": 0, "total": 5},
                "checks": [
                    {"name": "repo", "status": "ok", "detail": "README.md"},
                    {"name": "sqlite_fts5", "status": "ok", "detail": "3.50.4"},
                    {"name": "schema", "status": "ok", "detail": "0 memory file(s)"},
                    {"name": "secret_scan", "status": "ok", "detail": "no suspected issues"},
                    {"name": "index", "status": "warn", "detail": "missing index"},
                ],
            }
        )
        wrong_profile = json.dumps({"profile": "distribution", "summary": {"fail": 0, "total": 0}, "checks": []})
        failing = json.dumps({"profile": "vault", "summary": {"fail": 1, "total": 1}, "checks": [{}]})
        missing_count = json.dumps({"profile": "vault", "summary": {"fail": 0, "total": 0}, "checks": []})
        non_integer_count = json.dumps(
            {"profile": "vault", "summary": {"ok": True, "warn": 0, "fail": 0, "total": 0}, "checks": []}
        )
        wrong_ok_count = json.dumps(
            {
                "profile": "vault",
                "summary": {"ok": 2, "warn": 1, "fail": 0, "total": 3},
                "checks": [
                    {"name": "repo", "status": "ok", "detail": "README.md"},
                    {"name": "index", "status": "warn", "detail": "missing index"},
                    {"name": "schema", "status": "warn", "detail": "no memory files"},
                ],
            }
        )
        unexpected_status = json.dumps(
            {
                "profile": "vault",
                "summary": {"ok": 0, "warn": 0, "fail": 0, "total": 1},
                "checks": [{"name": "repo", "status": "skipped", "detail": "README.md"}],
            }
        )

        assert_doctor_summary(good)
        with self.assertRaises(InstallSmokeError):
            assert_doctor_summary(wrong_profile)
        with self.assertRaises(InstallSmokeError):
            assert_doctor_summary(failing)
        with self.assertRaisesRegex(InstallSmokeError, "ok count was not an integer"):
            assert_doctor_summary(missing_count)
        with self.assertRaisesRegex(InstallSmokeError, "ok count was not an integer"):
            assert_doctor_summary(non_integer_count)
        with self.assertRaisesRegex(InstallSmokeError, "ok count does not match checks"):
            assert_doctor_summary(wrong_ok_count)
        with self.assertRaisesRegex(InstallSmokeError, "unexpected status"):
            assert_doctor_summary(unexpected_status)

    def test_install_smoke_validates_release_evidence_unavailable(self) -> None:
        good = json.dumps(
            {
                "available": False,
                "reason": "release evidence requires a git distribution checkout",
                "evidence": None,
            }
        )
        available = json.dumps(
            {"available": True, "reason": None, "evidence": {"release_ready": False}}
        )
        missing_evidence = json.dumps(
            {"available": False, "reason": "release evidence requires a git distribution checkout"}
        )
        missing_reason = json.dumps({"available": False, "reason": "plain vault", "evidence": None})
        report_shape_for_evidence = json.dumps(
            {
                "available": False,
                "reason": "release evidence requires a git distribution checkout",
                "markdown": None,
            }
        )
        good_report = json.dumps(
            {
                "available": False,
                "reason": "release evidence report requires a git distribution checkout",
                "markdown": None,
            }
        )
        evidence_shape_for_report = json.dumps(
            {
                "available": False,
                "reason": "release evidence report requires a git distribution checkout",
                "evidence": None,
            }
        )
        report_with_markdown = json.dumps(
            {
                "available": False,
                "reason": "release evidence report requires a git distribution checkout",
                "markdown": "# v2 Release Evidence",
            }
        )

        assert_release_evidence_unavailable(good)
        assert_release_evidence_report_unavailable(good_report)
        with self.assertRaises(InstallSmokeError):
            assert_release_evidence_unavailable(available)
        with self.assertRaises(InstallSmokeError):
            assert_release_evidence_unavailable(missing_evidence)
        with self.assertRaises(InstallSmokeError):
            assert_release_evidence_unavailable(report_shape_for_evidence)
        with self.assertRaises(InstallSmokeError):
            assert_release_evidence_unavailable(missing_reason)
        with self.assertRaises(InstallSmokeError):
            assert_release_evidence_report_unavailable(evidence_shape_for_report)
        with self.assertRaises(InstallSmokeError):
            assert_release_evidence_report_unavailable(report_with_markdown)

    def test_mcp_release_evidence_unavailable_when_git_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("memory_mcp.subprocess.run", side_effect=FileNotFoundError):
                result = call_tool("memory.release_evidence", {}, root)

        self.assertFalse(result["available"])
        self.assertIn("distribution checkout", result["reason"])
        self.assertIsNone(result["evidence"])

    def test_mcp_release_evidence_unavailable_for_private_git_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            completed = subprocess.CompletedProcess(
                ["git", "rev-parse", "--show-toplevel"],
                0,
                stdout=str(root),
                stderr="",
            )
            with patch("memory_mcp.subprocess.run", return_value=completed):
                evidence = call_tool("memory.release_evidence", {}, root)
                report = call_tool("memory.release_evidence_report", {}, root)

        self.assertFalse(evidence["available"])
        self.assertIn("distribution checkout", evidence["reason"])
        self.assertIsNone(evidence["evidence"])
        self.assertFalse(report["available"])
        self.assertFalse(report["writes_files"])
        self.assertIsNone(report["markdown"])
        self.assertIn("distribution checkout", report["reason"])

    def test_mcp_release_evidence_report_renders_distribution_markdown_without_writing(self) -> None:
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/250"
        result = call_tool(
            "memory.release_evidence_report",
            {"pr_url": pr_url, "reviewer": "Unit Reviewer"},
            ROOT,
        )
        evidence = call_tool(
            "memory.release_evidence",
            {"pr_url": pr_url, "reviewer": "Unit Reviewer"},
            ROOT,
        )

        self.assertTrue(result["available"])
        self.assertFalse(result["records_evidence"])
        self.assertFalse(result["writes_files"])
        self.assertIsNone(result["report_path"])
        self.assertIn("# v2 Release Evidence", result["markdown"])
        self.assertIn(pr_url, result["markdown"])
        self.assertIn("Reviewer: `Unit Reviewer`", result["markdown"])
        self.assertIsInstance(result["release_blocker_count"], int)
        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["evidence"]["reviewer"], "Unit Reviewer")
        self.assertEqual(evidence["evidence"]["pr_url"], pr_url)
        remaining_plan_item = next(
            item for item in evidence["evidence"]["manual_acceptance_plan"]["items"] if item["pass_command"]
        )
        self.assertIn(
            "--reviewed-by 'Unit Reviewer'",
            remaining_plan_item["pass_command"],
        )

    def test_release_evidence_report_metadata_escapes_inline_markdown(self) -> None:
        reviewer = "Reviewer `quoted`\n- injected"
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/212 ``x``\n- fake"
        output = io.StringIO()

        with patch("sys.stdout", output):
            exit_code = release_evidence_main(
                ["--root", str(ROOT), "--json", "--pr-url", pr_url, "--reviewer", reviewer, "--write-report"]
            )
        payload = json.loads(output.getvalue())
        report_text = (ROOT / payload["report_path"]).read_text(encoding="utf-8")
        mcp_payload = call_tool("memory.release_evidence_report", {"pr_url": pr_url, "reviewer": reviewer}, ROOT)

        self.assertEqual(exit_code, 0)
        for markdown in (report_text, mcp_payload["markdown"]):
            self.assertIn("Reviewer: ``Reviewer `quoted` - injected``", markdown)
            self.assertIn("PR URL: ```https://github.com/GonzaloTorreras/ai-dememory/pull/212 ``x`` - fake```", markdown)
            self.assertIn("pass: ```ai-dememory acceptance record", markdown)
            self.assertIn("--reviewed-by 'Reviewer `quoted` - injected'", markdown)
            self.assertIn("strict_release_evidence:", markdown)
            self.assertIn("``x`` - fake", markdown)
            self.assertNotIn("\n- injected", markdown)
            self.assertNotIn("\n- fake", markdown)

    def test_mcp_release_evidence_report_unavailable_when_git_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("memory_mcp.subprocess.run", side_effect=FileNotFoundError):
                result = call_tool("memory.release_evidence_report", {}, root)

        self.assertFalse(result["available"])
        self.assertFalse(result["writes_files"])
        self.assertIsNone(result["markdown"])
        self.assertIn("distribution checkout", result["reason"])

    def test_mcp_publish_plan_summarizes_manual_dispatch_without_publishing(self) -> None:
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/239"
        result = call_tool("memory.publish_plan", {"repository": "testpypi", "pr_url": pr_url}, ROOT)

        self.assertEqual(result["repository"], "testpypi")
        self.assertEqual(result["dispatch_inputs"], {"repository": "testpypi", "confirm": "publish", "pr_url": pr_url})
        self.assertFalse(result["publishes_package"])
        self.assertFalse(result["writes_files"])
        self.assertTrue(result["runs_commands"])
        self.assertFalse(result["runs_publish_commands"])
        self.assertFalse(result["runs_preflight_commands"])
        self.assertTrue(result["local_inspection_commands"])
        self.assertTrue(result["requires_manual_dispatch"])
        self.assertTrue(result["requires_confirmation"])
        self.assertTrue(result["requires_pr_url"])
        self.assertTrue(result["uses_trusted_publishing"])
        self.assertIsInstance(result["preflight_commands"], list)
        self.assertIsInstance(result["next_actions"], list)
        self.assertIn("publish_ready", result)
        self.assertEqual(
            result["workflow_url"],
            "https://github.com/GonzaloTorreras/ai-dememory/actions/workflows/publish.yml",
        )
        self.assertTrue(result["release_evidence_available"])

    def test_mcp_publish_plan_output_schema_matches_payload(self) -> None:
        result = call_tool(
            "memory.publish_plan",
            {"repository": "testpypi", "pr_url": "https://github.com/GonzaloTorreras/ai-dememory/pull/239"},
            ROOT,
        )
        tool = next(item for item in TOOLS if item["name"] == "memory.publish_plan")
        schema = tool["outputSchema"]
        properties = schema["properties"]
        required = set(schema["required"])

        for key in result:
            self.assertIn(key, properties)
            self.assertIn(key, required)
        self.assertFalse(schema.get("additionalProperties", True))

    def test_mcp_publish_plan_reports_unavailable_release_evidence_from_plain_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("memory_mcp.subprocess.run", side_effect=FileNotFoundError):
                result = call_tool("memory.publish_plan", {"repository": "pypi"}, root)

        self.assertEqual(result["repository"], "pypi")
        self.assertFalse(result["release_evidence_available"])
        self.assertEqual(result["release_blocker_ids"], ["release_evidence_unavailable"])
        self.assertFalse(result["publishes_package"])
        self.assertFalse(result["writes_files"])
        self.assertFalse(result["runs_publish_commands"])
        self.assertFalse(result["runs_preflight_commands"])
        self.assertIn("TestPyPI", " ".join(result["next_actions"]))

    def test_install_smoke_validates_maintenance_status_artifacts(self) -> None:
        good = json.dumps(
            {
                "schedule": {},
                "providers": {},
                "recent_reports": [],
                "lock_exists": False,
                "review_due": {
                    "false_positive_findings": 0,
                    "active_findings": 0,
                    "ignored_findings": 0,
                    "due_findings": 0,
                    "due_ids": [],
                    "stale_suppressions": 0,
                    "stale_ids": [],
                    "stale_review_due": 0,
                    "stale_review_due_ids": [],
                    "status_counts": {},
                    "canonical_memory_updated": False,
                },
                "conflict_review": {
                    "available": True,
                    "errors": [],
                    "conflicts": 0,
                    "active_conflicts": 0,
                    "reviewed_conflicts": 0,
                    "active_ids": [],
                    "status_counts": {},
                    "category_counts": {},
                    "canonical_memory_updated": False,
                },
                "review_recommendations": {
                    "available": True,
                    "errors": [],
                    "total_count": 0,
                    "pending_count": 0,
                    "accepted_count": 0,
                    "rejected_count": 0,
                    "invalid_count": 0,
                    "policy_violation_count": 0,
                    "requires_human_approval_count": 0,
                    "pending_ids": [],
                    "status_counts": {"pending": 0, "accepted": 0, "rejected": 0},
                    "kind_counts": {},
                    "latest_created_at": None,
                    "applies_review_decisions": False,
                    "writes_canonical_memory": False,
                    "canonical_memory_updated": False,
                },
                "generated_packet_archives": {
                    "available": True,
                    "errors": [],
                    "summary": {
                        "total_count": 0,
                        "prunable_count": 0,
                        "has_prunable": False,
                    },
                    "recall_review_packets": {},
                    "manual_acceptance_packets": {},
                    "mutates_system": False,
                    "runs_commands": False,
                    "writes_files": False,
                    "deletes_files": False,
                    "records_evidence": False,
                    "records_fixture_promotions": False,
                },
                "artifacts": {
                    "index": {
                        "path": "indexes/memory.sqlite",
                        "exists": True,
                        "updated_at": "2026-06-19T00:00:00+00:00",
                        "size_bytes": 1024,
                    },
                    "graph": {
                        "path": "indexes/memory-graph.json",
                        "exists": True,
                        "updated_at": "2026-06-19T00:00:00+00:00",
                        "size_bytes": 128,
                    },
                    "weights": {
                        "path": "indexes/memory-weights.json",
                        "exists": True,
                        "updated_at": "2026-06-19T00:00:00+00:00",
                        "size_bytes": 64,
                    },
                    "lifecycle_scores": {
                        "path": "indexes/memory-lifecycle.json",
                        "exists": False,
                        "updated_at": None,
                        "size_bytes": None,
                    },
                    "lifecycle_report": {
                        "path": "reports/lifecycle.md",
                        "exists": False,
                        "updated_at": None,
                        "size_bytes": None,
                    },
                    "hook_capture_report": {
                        "path": "reports/hook-captures.md",
                        "exists": False,
                        "updated_at": None,
                        "size_bytes": None,
                    },
                    "sleep_plan_report": {
                        "path": "reports/sleep-plan.md",
                        "exists": False,
                        "updated_at": None,
                        "size_bytes": None,
                    },
                },
                "artifact_freshness": {
                    "profile": "daily",
                    "source_count": 1,
                    "latest_source_path": "memories/tools/codex.md",
                    "latest_source_updated_at": "2026-06-19T00:00:00+00:00",
                    "missing_count": 2,
                    "stale_count": 0,
                    "fresh_count": 3,
                    "needs_maintenance": True,
                    "next_action": "Run ai-dememory maintenance run --profile daily.",
                    "artifacts": {
                        "index": {
                            "path": "indexes/memory.sqlite",
                            "exists": True,
                            "updated_at": "2026-06-19T00:00:00+00:00",
                            "status": "fresh",
                            "stale": False,
                        },
                        "graph": {
                            "path": "indexes/memory-graph.json",
                            "exists": True,
                            "updated_at": "2026-06-19T00:00:00+00:00",
                            "status": "fresh",
                            "stale": False,
                        },
                        "weights": {
                            "path": "indexes/memory-weights.json",
                            "exists": True,
                            "updated_at": "2026-06-19T00:00:00+00:00",
                            "status": "fresh",
                            "stale": False,
                        },
                        "lifecycle_scores": {
                            "path": "indexes/memory-lifecycle.json",
                            "exists": False,
                            "updated_at": None,
                            "status": "missing",
                            "stale": True,
                        },
                        "lifecycle_report": {
                            "path": "reports/lifecycle.md",
                            "exists": False,
                            "updated_at": None,
                            "status": "missing",
                            "stale": True,
                        },
                    },
                    "mutates_system": False,
                    "runs_commands": False,
                    "writes_files": False,
                    "deletes_files": False,
                },
            }
        )
        missing = json.dumps(
            {"artifacts": {"index": {"path": "indexes/memory.sqlite", "exists": True}}}
        )
        malformed = json.dumps(
            {
                "artifacts": {
                    "index": {"path": "indexes/memory.sqlite", "exists": "yes"},
                    "graph": {"path": "indexes/memory-graph.json", "exists": True},
                    "weights": {"path": "indexes/memory-weights.json", "exists": True},
                    "lifecycle_scores": {"path": "indexes/memory-lifecycle.json", "exists": True},
                    "lifecycle_report": {"path": "reports/lifecycle.md", "exists": True},
                    "hook_capture_report": {"path": "reports/hook-captures.md", "exists": True},
                    "sleep_plan_report": {"path": "reports/sleep-plan.md", "exists": True},
                }
            }
        )

        assert_maintenance_status_artifacts(good)
        with self.assertRaises(InstallSmokeError):
            assert_maintenance_status_artifacts(missing)
        with self.assertRaises(InstallSmokeError):
            assert_maintenance_status_artifacts(malformed)
        missing_review_due = json.dumps({**json.loads(good), "review_due": {}})
        with self.assertRaises(InstallSmokeError):
            assert_maintenance_status_artifacts(missing_review_due)
        missing_recommendations = json.dumps({**json.loads(good), "review_recommendations": {}})
        with self.assertRaises(InstallSmokeError):
            assert_maintenance_status_artifacts(missing_recommendations)
        missing_freshness = json.dumps({**json.loads(good), "artifact_freshness": {}})
        with self.assertRaises(InstallSmokeError):
            assert_maintenance_status_artifacts(missing_freshness)
        missing_packet_archives = json.dumps({**json.loads(good), "generated_packet_archives": {}})
        with self.assertRaises(InstallSmokeError):
            assert_maintenance_status_artifacts(missing_packet_archives)

    def test_install_smoke_validates_vault_template_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault-template-export"
            copy_template_tree(target)
            good = json.dumps({"target": str(target.resolve()), "copied": 27})
            docker_good = json.dumps({"target": "/template", "copied": 27})
            wrong_target = json.dumps({"target": str(Path(tmp) / "other"), "copied": 27})

            assert_vault_template_export(good, target)
            assert_vault_template_export(docker_good, target, expected_reported_target="/template")
            with self.assertRaises(InstallSmokeError):
                assert_vault_template_export(wrong_target, target)
            missing_file = target / ".gitignore"
            missing_file.unlink()
            with self.assertRaises(InstallSmokeError):
                assert_vault_template_export(good, target)

    def test_install_smoke_validates_schedule_plan_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = json.dumps(
                {
                    "root": str(root.resolve()),
                    "action": "install",
                    "platform": "linux",
                    "mode": "installed",
                    "image": "",
                    "schedule": {
                        "daily_time": "03:00",
                        "weekly_day": "SUN",
                        "weekly_time": "04:00",
                    },
                    "commands": [
                        {
                            "name": "ai-dememory-daily",
                            "platform": "linux",
                            "action": "install",
                            "command": ["systemctl", "--user", "enable", "--now", "ai-dememory-daily.timer"],
                            "run_command": [
                                "ai-dememory",
                                "maintenance",
                                "run",
                                "--profile",
                                "daily",
                                "--root",
                                str(root.resolve()),
                            ],
                        },
                        {
                            "name": "ai-dememory-weekly",
                            "platform": "linux",
                            "action": "install",
                            "command": ["systemctl", "--user", "enable", "--now", "ai-dememory-weekly.timer"],
                            "run_command": [
                                "ai-dememory",
                                "maintenance",
                                "run",
                                "--profile",
                                "weekly",
                                "--root",
                                str(root.resolve()),
                            ],
                        },
                    ],
                    "cron_entries": [
                        {
                            "name": "ai-dememory-daily",
                            "profile": "daily",
                            "schedule": "0 3 * * *",
                            "command": ["ai-dememory", "maintenance", "run", "--profile", "daily"],
                            "line": "0 3 * * * ai-dememory maintenance run --profile daily",
                        },
                        {
                            "name": "ai-dememory-weekly",
                            "profile": "weekly",
                            "schedule": "0 4 * * 0",
                            "command": ["ai-dememory", "maintenance", "run", "--profile", "weekly"],
                            "line": "0 4 * * 0 ai-dememory maintenance run --profile weekly",
                        },
                    ],
                    "mutates_system": False,
                    "runs_commands": False,
                    "writes_files": False,
                    "installs_schedules": False,
                }
            )
            missing_flags = json.dumps({**json.loads(good), "writes_files": True})
            missing_cron = json.dumps({**json.loads(good), "cron_entries": []})
            wrong_root = json.dumps({**json.loads(good), "root": "/memory"})
            missing_weekly_run_payload = json.loads(good)
            missing_weekly_run_payload["commands"][1]["run_command"] = [
                "ai-dememory",
                "maintenance",
                "run",
                "--profile",
                "daily",
                "--root",
                str(root.resolve()),
            ]
            duplicate_daily_cron_payload = json.loads(good)
            duplicate_daily_cron_payload["cron_entries"][1] = {
                **duplicate_daily_cron_payload["cron_entries"][0],
                "name": "ai-dememory-daily-copy",
            }
            mismatched_weekly_command_payload = json.loads(good)
            mismatched_weekly_command_payload["commands"].append(
                {
                    "name": "ai-dememory-extra-weekly",
                    "platform": "linux",
                    "action": "install",
                    "command": ["systemctl", "--user", "status", "ai-dememory-weekly.timer"],
                    "run_command": [
                        "ai-dememory",
                        "maintenance",
                        "run",
                        "--profile",
                        "weekly",
                        "--root",
                        str(root.resolve()),
                    ],
                }
            )
            mismatched_weekly_command_payload["commands"][1]["run_command"] = [
                "ai-dememory",
                "maintenance",
                "run",
                "--profile",
                "daily",
                "--root",
                str(root.resolve()),
            ]
            mismatched_weekly_cron_payload = json.loads(good)
            mismatched_weekly_cron_payload["cron_entries"][1]["line"] = (
                "0 4 * * 0 ai-dememory maintenance run --profile daily"
            )
            mismatched_weekly_cron_payload["cron_entries"][1]["command"] = [
                "ai-dememory",
                "maintenance",
                "run",
                "--profile",
                "daily",
            ]

            assert_schedule_plan(good, expected_root=str(root.resolve()))
            with self.assertRaises(InstallSmokeError):
                assert_schedule_plan(missing_flags, expected_root=str(root.resolve()))
            with self.assertRaises(InstallSmokeError):
                assert_schedule_plan(missing_cron, expected_root=str(root.resolve()))
            with self.assertRaises(InstallSmokeError):
                assert_schedule_plan(wrong_root, expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "weekly maintenance run command"):
                assert_schedule_plan(json.dumps(missing_weekly_run_payload), expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "one daily and one weekly cron entry"):
                assert_schedule_plan(json.dumps(duplicate_daily_cron_payload), expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "weekly maintenance run command"):
                assert_schedule_plan(json.dumps(mismatched_weekly_command_payload), expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "weekly maintenance cron line"):
                assert_schedule_plan(json.dumps(mismatched_weekly_cron_payload), expected_root=str(root.resolve()))

    def test_install_smoke_validates_roadmap_status_payload(self) -> None:
        good = json.dumps(
            {
                "phase_count": 11,
                "status_counts": {"implemented": 10, "gated": 1},
                "writes_files": False,
                "mutates_files": False,
                "phases": [{"phase": index, "status": "implemented"} for index in range(11)],
            }
        )

        assert_roadmap_status(good)
        with self.assertRaisesRegex(InstallSmokeError, "11 v2 phases"):
            assert_roadmap_status(json.dumps({**json.loads(good), "phase_count": 10}))
        with self.assertRaisesRegex(InstallSmokeError, "must not write"):
            assert_roadmap_status(json.dumps({**json.loads(good), "writes_files": True}))
        with self.assertRaisesRegex(InstallSmokeError, "counts do not match"):
            assert_roadmap_status(json.dumps({**json.loads(good), "status_counts": {"implemented": 10}}))
        with self.assertRaisesRegex(InstallSmokeError, "stable phase numbers"):
            assert_roadmap_status(json.dumps({**json.loads(good), "phases": [{"status": "implemented"}] * 11}))

    def test_install_smoke_validates_publish_plan_payload(self) -> None:
        good = json.dumps(
            {
                "repository": "testpypi",
                "dispatch_inputs": {"repository": "testpypi", "confirm": "publish", "pr_url": "<pr-url>"},
                "mutates_system": False,
                "runs_commands": True,
                "runs_publish_commands": False,
                "runs_preflight_commands": False,
                "writes_files": False,
                "publishes_package": False,
                "local_inspection_commands": ["git remote get-url origin"],
                "requires_manual_dispatch": True,
                "requires_confirmation": True,
                "requires_pr_url": True,
                "preflight_commands": [["ai-dememory", "publish-guard"]],
                "workflow_url": "https://github.com/<owner>/<repo>/actions/workflows/publish.yml",
                "next_actions": ["Review publish plan."],
            }
        )

        assert_publish_plan(good)
        with self.assertRaisesRegex(InstallSmokeError, "default to TestPyPI"):
            assert_publish_plan(json.dumps({**json.loads(good), "repository": "pypi"}))
        with self.assertRaisesRegex(InstallSmokeError, "publishes_package"):
            assert_publish_plan(json.dumps({**json.loads(good), "publishes_package": True}))
        with self.assertRaisesRegex(InstallSmokeError, "confirmation"):
            assert_publish_plan(json.dumps({**json.loads(good), "dispatch_inputs": {}}))
        with self.assertRaisesRegex(InstallSmokeError, "workflow URL"):
            assert_publish_plan(json.dumps({**json.loads(good), "workflow_url": ""}))

    def test_docker_schedule_plan_command_mounts_memory_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            command = docker_schedule_plan_command(vault, "ai-dememory:test")

        self.assertEqual(command[:4], ["docker", "run", "--rm", "-v"])
        self.assertIn(f"{vault}:/memory", command)
        self.assertIn("AI_DEMEMORY_ROOT=/memory", command)
        self.assertIn("ai-dememory:test", command)
        self.assertEqual(command[-3:], ["schedule", "plan", "--json"])

    def test_docker_roadmap_status_command_mounts_memory_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            command = docker_roadmap_status_command(vault, "ai-dememory:test")

        self.assertEqual(command[:4], ["docker", "run", "--rm", "-v"])
        self.assertIn(f"{vault}:/memory", command)
        self.assertIn("AI_DEMEMORY_ROOT=/memory", command)
        self.assertIn("ai-dememory:test", command)
        self.assertEqual(command[-3:], ["roadmap", "status", "--json"])

    def test_package_build_smoke_validates_distribution_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            wheel = dist / "ai_dememory-2.0.0-py3-none-any.whl"
            sdist = dist / "ai_dememory-2.0.0.tar.gz"
            wheel.write_text("wheel", encoding="utf-8")
            sdist.write_text("sdist", encoding="utf-8")

            artifacts = assert_dist_artifacts(dist)

            self.assertEqual(set(artifacts), {wheel, sdist})
            wheel.unlink()
            with self.assertRaises(InstallSmokeError):
                assert_dist_artifacts(dist)

    def test_package_build_smoke_cleans_only_created_build_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preexisting = root / "dist"
            created = root / "ai_dememory.egg-info"
            preexisting.mkdir()
            created.mkdir()
            existing = {preexisting.resolve()}

            cleanup_created_build_paths(root, existing)

            self.assertTrue(preexisting.exists())
            self.assertFalse(created.exists())

    def test_package_build_smoke_rejects_stale_build_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ai_dememory.egg-info").mkdir()

            with self.assertRaisesRegex(InstallSmokeError, "stale generated package build artifact"):
                assert_no_stale_build_paths(root)

    def test_package_build_smoke_check_clean_exits_on_stale_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                clean_exit = package_build_smoke_main(["--root", str(root), "--check-clean", "--json"])

            (root / "build").mkdir()
            error = io.StringIO()
            with patch("sys.stderr", error):
                stale_exit = package_build_smoke_main(["--root", str(root), "--check-clean"])

        self.assertEqual(clean_exit, 0)
        self.assertIn('"clean": true', output.getvalue())
        self.assertEqual(stale_exit, 1)
        self.assertIn("stale generated package build artifact", error.getvalue())

    def test_install_smoke_venv_paths_are_platform_specific(self) -> None:
        python_path, pip_path, command_path = venv_paths(Path("venv"))

        if os.name == "nt":
            self.assertEqual(python_path, Path("venv") / "Scripts" / "python.exe")
            self.assertEqual(pip_path, Path("venv") / "Scripts" / "pip.exe")
            self.assertEqual(command_path, Path("venv") / "Scripts" / "ai-dememory.exe")
        else:
            self.assertEqual(python_path, Path("venv") / "bin" / "python")
            self.assertEqual(pip_path, Path("venv") / "bin" / "pip")
            self.assertEqual(command_path, Path("venv") / "bin" / "ai-dememory")

    def test_install_smoke_run_step_allows_expected_nonzero_exit(self) -> None:
        steps: list[SmokeStep] = []
        completed = run_step(
            steps,
            "expected nonzero",
            [sys.executable, "-c", "import sys; print('valid payload'); sys.exit(1)"],
            allowed_returncodes={0, 1},
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(steps[0].returncode, 1)
        with self.assertRaises(InstallSmokeError):
            run_step([], "unexpected nonzero", [sys.executable, "-c", "import sys; sys.exit(1)"])

    def test_install_smoke_command_list_covers_v2_cli_surfaces(self) -> None:
        commands = {name: args for name, args in package_smoke_commands()}

        self.assertEqual(commands["provenance"], ["provenance", "--json"])
        self.assertEqual(
            commands["working snapshot"],
            [
                "working",
                "snapshot",
                "--title",
                "Install Smoke Working State",
                "--task",
                "install-smoke",
                "--notes",
                "Use install smoke package policy.",
            ],
        )
        self.assertEqual(commands["context auto"], ["context", "--auto", "--budget", "700", "--json"])
        self.assertEqual(
            commands["mark seen receipt"],
            ["mark-seen", "--id", "mem_install_smoke_policy", "--query", "install smoke package policy", "--json"],
        )
        self.assertEqual(
            commands["outcome receipt"],
            ["outcome", "--last", "--good", "--note", "Install smoke selected expected memory.", "--json"],
        )
        self.assertEqual(
            commands["recall fixtures packet archive status"],
            ["recall-fixtures", "packet-archive-status", "--json"],
        )
        self.assertEqual(commands["acceptance status"], ["acceptance", "status", "--json"])
        self.assertEqual(commands["acceptance plan"], ["acceptance", "plan", "--json"])
        self.assertEqual(
            commands["acceptance plan report"],
            ["acceptance", "plan", "--write-report", "--json"],
        )
        self.assertEqual(
            commands["acceptance packet report"],
            ["acceptance", "packet", "--write-report", "--json"],
        )
        self.assertEqual(
            commands["acceptance packet archive status"],
            ["acceptance", "packet-archive-status", "--json"],
        )
        self.assertEqual(
            commands["acceptance template"],
            ["acceptance", "template", "--item", "mcp-client-installed", "--json"],
        )
        self.assertEqual(commands["acceptance verify help"], ["acceptance", "verify", "--help"])
        self.assertEqual(commands["publish plan"], ["publish-plan", "--json"])
        self.assertEqual(
            commands["mcp release evidence unavailable"],
            ["mcp", "--call", "memory.release_evidence", "--args", "{}"],
        )
        self.assertEqual(
            commands["mcp release evidence report unavailable"],
            ["mcp", "--call", "memory.release_evidence_report", "--args", "{}"],
        )
        self.assertEqual(commands["mcp publish plan"], ["mcp", "--call", "memory.publish_plan", "--args", "{}"])
        self.assertEqual(commands["api smoke"], ["api-smoke"])
        self.assertEqual(commands["vault template export"], ["vault-template", "export", "{template_export}", "--json"])
        self.assertEqual(commands["setup plan"], ["setup", "plan", "--json"])
        self.assertEqual(commands["setup health"], ["setup", "health", "--json"])
        self.assertEqual(
            commands["plugin mcp config smoke"],
            ["mcp-client-smoke", "--config", "{plugin_mcp}", "--command", "{ai_dememory}"],
        )
        self.assertEqual(commands["recall fixtures status"], ["recall-fixtures", "status", "--json"])
        self.assertEqual(
            commands["capture recall miss dry run"],
            [
                "capture-miss",
                "--query",
                "missing install smoke policy",
                "--expected-id",
                "mem_install_smoke_policy",
                "--reason",
                "Expected install smoke policy memory was absent.",
                "--dry-run",
                "--json",
            ],
        )
        self.assertEqual(
            commands["recall miss candidate check"],
            [
                "recall-fixtures",
                "check-miss",
                "--query",
                "install smoke package policy",
                "--expected-id",
                "mem_install_smoke_policy",
                "--json",
            ],
        )
        self.assertEqual(commands["recall fixtures review plan"], ["recall-fixtures", "review-plan", "--json"])
        self.assertEqual(
            commands["recall fixtures review report"],
            ["recall-fixtures", "review-plan", "--write-report", "--json"],
        )
        self.assertEqual(
            commands["recall fixtures review packet"],
            ["recall-fixtures", "packet", "--write-report", "--json"],
        )
        self.assertEqual(commands["recall fixtures help"], ["recall-fixtures", "promote-miss", "--help"])
        self.assertEqual(commands["recall miss review help"], ["recall-fixtures", "review-miss", "--help"])
        self.assertEqual(commands["roadmap status"], ["roadmap", "status", "--json"])
        self.assertEqual(commands["providers plan"], ["providers", "plan", "--json"])
        self.assertEqual(commands["hooks archive help"], ["hooks", "archive", "--help"])
        self.assertEqual(commands["maintenance dry run"], ["maintenance", "run", "--profile", "daily", "--dry-run", "--json"])
        self.assertEqual(commands["schedule doctor"], ["schedule", "doctor", "--json"])
        self.assertEqual(commands["schedule plan"], ["schedule", "plan", "--json"])
        self.assertEqual(
            commands["docker schedule dry run"],
            ["schedule", "setup", "--dry-run", "--mode", "docker", "--image", "ai-dememory:local"],
        )
        self.assertEqual(commands["cron schedule export"], ["schedule", "cron", "--json"])
        self.assertEqual(commands["review modes"], ["review", "modes"])
        self.assertEqual(
            commands["review false positives due only"],
            ["review", "false-positives", "--due-only", "--json"],
        )
        self.assertEqual(commands["review plan conflict"], ["review", "plan", "--kind", "conflict"])
        self.assertEqual(
            commands["review recommendation"],
            [
                "review",
                "recommendation",
                "--kind",
                "conflict",
                "--target-id",
                "conf_install_smoke",
                "--recommendation",
                "collect_evidence",
                "--rationale",
                "Install smoke records advisory recommendation capture.",
                "--recommended-by",
                "Install Smoke",
                "--json",
            ],
        )
        self.assertEqual(commands["review recommendations"], ["review", "recommendations", "--json"])
        self.assertEqual(commands["review recommendation outcome help"], ["review", "recommendation-outcome", "--help"])
        self.assertEqual(commands["review recommendation outcomes help"], ["review", "recommendation-outcomes", "--help"])
        self.assertEqual(commands["review recommendations archive help"], ["review", "recommendations-archive", "--help"])
        self.assertEqual(commands["review recommendations archive status"], ["review", "recommendations-archive-status", "--json"])
        self.assertEqual(
            commands["review recommendations archive restore help"],
            ["review", "recommendations-archive-restore", "--help"],
        )
        self.assertEqual(commands["working status"], ["working", "status", "--json"])

    def test_docker_client_smoke_command_supports_source_and_installed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"

            self.assertEqual(local_ai_dememory_command(root), ["ai-dememory"])
            self.assertEqual(
                docker_client_smoke_command(root, vault, "ai-dememory:test"),
                [
                    "ai-dememory",
                    "--root",
                    str(vault),
                    "mcp-client-smoke",
                    "--mode",
                    "docker",
                    "--image",
                    "ai-dememory:test",
                ],
            )
            self.assertEqual(
                docker_release_evidence_command(vault, "ai-dememory:test"),
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{vault}:/memory",
                    "-e",
                    "AI_DEMEMORY_ROOT=/memory",
                    "ai-dememory:test",
                    "mcp",
                    "--call",
                    "memory.release_evidence",
                    "--args",
                    "{}",
                ],
            )
            self.assertEqual(
                docker_publish_plan_command(vault, "ai-dememory:test"),
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{vault}:/memory",
                    "-e",
                    "AI_DEMEMORY_ROOT=/memory",
                    "ai-dememory:test",
                    "mcp",
                    "--call",
                    "memory.publish_plan",
                    "--args",
                    "{}",
                ],
            )
            self.assertEqual(
                docker_maintenance_status_command(vault, "ai-dememory:test"),
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{vault}:/memory",
                    "-e",
                    "AI_DEMEMORY_ROOT=/memory",
                    "ai-dememory:test",
                    "maintenance",
                    "status",
                ],
            )
            self.assertEqual(
                docker_roadmap_status_command(vault, "ai-dememory:test"),
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{vault}:/memory",
                    "-e",
                    "AI_DEMEMORY_ROOT=/memory",
                    "ai-dememory:test",
                    "roadmap",
                    "status",
                    "--json",
                ],
            )
            self.assertEqual(
                docker_vault_template_export_command(root / "template", "ai-dememory:test"),
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{root / 'template'}:/template",
                    "ai-dememory:test",
                    "vault-template",
                    "export",
                    "/template",
                    "--force",
                    "--json",
                ],
            )

            script = root / "scripts" / "ai_dememory.py"
            script.parent.mkdir()
            script.write_text("# test shim\n", encoding="utf-8")

            self.assertEqual(local_ai_dememory_command(root), [sys.executable, str(script)])

    def test_mcp_client_smoke_overrides_config_launch_without_mutating_source(self) -> None:
        config = {
            "mcpServers": {
                "ai-dememory": {
                    "command": "ai-dememory",
                    "args": ["mcp", "--stdio"],
                    "env": {},
                    "enabled_tools": ["memory.search"],
                }
            }
        }

        overridden = override_launch(
            config,
            command=sys.executable,
            command_args=["scripts/ai_dememory.py"],
        )
        server = overridden["mcpServers"]["ai-dememory"]

        self.assertEqual(config["mcpServers"]["ai-dememory"]["command"], "ai-dememory")
        self.assertEqual(config["mcpServers"]["ai-dememory"]["args"], ["mcp", "--stdio"])
        self.assertEqual(server["command"], sys.executable)
        self.assertEqual(server["args"], ["scripts/ai_dememory.py", "mcp", "--stdio"])
        self.assertEqual(server["enabled_tools"], ["memory.search"])

    def test_mcp_client_smoke_verifies_enabled_tools_from_tools_list(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25"}}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "result": {}}),
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "result": {"tools": [{"name": "memory.search"}], "nextCursor": "1"},
                    }
                ),
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "result": {"tools": [{"name": "memory.context"}]},
                    }
                ),
            ]
        )

        verify_enabled_tools(stdout, ["memory.search", "memory.context"])

        with self.assertRaisesRegex(Exception, "memory.missing"):
            verify_enabled_tools(stdout, ["memory.search", "memory.missing"])

        with self.assertRaisesRegex(Exception, "final page"):
            verify_enabled_tools(
                stdout.splitlines()[0] + "\n" + stdout.splitlines()[1] + "\n" + stdout.splitlines()[2],
                ["memory.search", "memory.context"],
            )

    def test_mcp_client_smoke_sends_initialized_notification_before_ping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = Path(tmp) / "requires_initialized.py"
            server.write_text(
                """
import json
import sys

initialized = False

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2025-11-25"}
    elif method == "notifications/initialized":
        initialized = True
        print(json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info"}}), flush=True)
        continue
    elif method == "ping" and initialized:
        result = {}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": "not initialized"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)
""".lstrip(),
                encoding="utf-8",
            )
            config = {"command": sys.executable, "args": [str(server)]}

            result = run_client_config_smoke(config, Path(tmp))

        self.assertTrue(result.initialized)
        self.assertTrue(result.pinged)

    def test_mcp_client_smoke_follows_tools_pagination_in_one_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = Path(tmp) / "session_server.py"
            server.write_text(
                """
import json
import sys

initialized = False
seen_first_page = False

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}
    if method == "initialize":
        result = {"protocolVersion": "2025-11-25"}
    elif method == "notifications/initialized":
        initialized = True
        print(json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info"}}), flush=True)
        continue
    elif method == "ping" and initialized:
        result = {}
    elif method == "tools/list" and initialized:
        cursor = params.get("cursor")
        if cursor is None:
            seen_first_page = True
            result = {"tools": [{"name": "memory.search"}], "nextCursor": "page-2"}
        elif cursor == "page-2" and seen_first_page:
            result = {"tools": [{"name": "memory.context"}]}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": "stale cursor"}}), flush=True)
            continue
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)
""".lstrip(),
                encoding="utf-8",
            )

            stdout = run_tools_list_pages(sys.executable, [str(server)], Path(tmp), dict(os.environ))

        verify_enabled_tools(stdout, ["memory.search", "memory.context"])

    def test_plugin_mcp_config_smoke_verifies_enabled_tool_allowlist(self) -> None:
        config_path = ROOT / "plugins" / "ai-dememory" / ".mcp.json"
        config = override_launch(
            json.loads(config_path.read_text(encoding="utf-8")),
            command=sys.executable,
            command_args=["scripts/ai_dememory.py"],
        )

        result = run_client_config_smoke(config, ROOT)

        self.assertTrue(result.enabled_tools_verified)
        self.assertEqual(result.enabled_tool_count, len(EXPECTED_PLUGIN_MCP_TOOLS))

    def test_install_smoke_sample_memory_is_valid_for_recall_fixture_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_install_smoke_memory(root)
            _, errors = validate_memories(root)

        self.assertEqual(path.as_posix().split("/")[-1], "install-smoke-policy.md")
        self.assertFalse(errors)

    def test_publish_guard_accepts_current_workflow(self) -> None:
        issues = validate_publish_workflow(ROOT)

        self.assertFalse(issues)

    def test_publish_guard_rejects_automatic_or_token_publish(self) -> None:
        unsafe = """
name: Publish
on:
  push:
    branches: [main]
jobs:
  publish:
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
"""

        issues = validate_publish_workflow_text(unsafe)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("stored PyPI tokens", messages)
        self.assertIn("canonical release workflow is missing: tags:", messages)
        self.assertIn("canonical release workflow is missing: concurrency:", messages)
        self.assertIn("canonical release workflow is missing: python scripts/ai_release_guard.py --tag", messages)
        self.assertIn("canonical release workflow is missing: release_artifact_smoke.py", messages)
        self.assertIn("canonical release workflow is missing: SHA256SUMS", messages)
        self.assertIn("recovery must require confirm=recover-<immutable-tag>", messages)

    def test_publish_guard_requires_exact_recovery_confirmation(self) -> None:
        misplaced = """
name: Publish Python Package

on:
  workflow_dispatch:
    inputs:
      repository:
        required: true
      confirm:
        required: true
      pr_url:
        required: true

env:
  AI_DEMEMORY_PR_URL: ${{ inputs.pr_url }}
  PUBLISH_REPOSITORY: ${{ inputs.repository }}

jobs:
  validate-inputs:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ inputs.confirm }}"
  preflight:
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/ai_dememory.py publish-plan --repository "$PUBLISH_REPOSITORY" --pr-url "$AI_DEMEMORY_PR_URL" --strict
"""

        issues = validate_publish_workflow_text(misplaced)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("recovery must require confirm=recover-<immutable-tag>", messages)
        self.assertIn("release distributions must be built exactly once", messages)

    def test_publish_plan_summarizes_manual_dispatch_without_publishing(self) -> None:
        plan = publish_plan(
            ROOT,
            repository="testpypi",
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250",
        )

        self.assertEqual(plan["repository"], "testpypi")
        self.assertEqual(plan["target_environment"], "testpypi")
        self.assertEqual(
            plan["dispatch_inputs"],
            {
                "repository": "testpypi",
                "confirm": "publish",
                "pr_url": "https://github.com/GonzaloTorreras/ai-dememory/pull/250",
            },
        )
        self.assertFalse(plan["mutates_system"])
        self.assertTrue(plan["runs_commands"])
        self.assertFalse(plan["runs_publish_commands"])
        self.assertFalse(plan["runs_preflight_commands"])
        self.assertFalse(plan["writes_files"])
        self.assertFalse(plan["publishes_package"])
        self.assertTrue(plan["local_inspection_commands"])
        self.assertTrue(plan["requires_manual_dispatch"])
        self.assertTrue(plan["requires_confirmation"])
        self.assertTrue(plan["requires_pr_url"])
        self.assertTrue(plan["uses_trusted_publishing"])
        self.assertEqual(plan["guard_issue_count"], 0)
        self.assertTrue(plan["release_evidence_available"])
        self.assertEqual(plan["publish_ready"], not bool(plan["publish_blocker_ids"]))
        self.assertIn("manual_acceptance_remaining", plan["release_blocker_ids"])
        # A fresh public source snapshot intentionally excludes private manual
        # acceptance receipts, so publishing remains blocked until new public
        # release evidence is reviewed and recorded.
        self.assertIn("manual_acceptance_remaining", plan["publish_blocker_ids"])
        self.assertEqual(plan["deferred_manual_acceptance_items"], [ACCEPTANCE_ITEMS["testpypi-publish"]])
        self.assertEqual(
            plan["workflow_url"],
            "https://github.com/GonzaloTorreras/ai-dememory/actions/workflows/publish.yml",
        )
        self.assertTrue(any(command[:2] == ["ai-dememory", "publish-guard"] for command in plan["preflight_commands"]))
        self.assertIn("Dispatch the publish workflow manually", plan["next_actions"][-1])

    def test_publish_plan_parses_github_remote_urls(self) -> None:
        self.assertEqual(
            github_owner_repo_from_remote("https://github.com/GonzaloTorreras/ai-dememory.git"),
            "GonzaloTorreras/ai-dememory",
        )
        self.assertEqual(
            github_owner_repo_from_remote("git@github.com:GonzaloTorreras/ai-dememory.git"),
            "GonzaloTorreras/ai-dememory",
        )
        self.assertEqual(
            github_owner_repo_from_remote("ssh://git@github.com/GonzaloTorreras/ai-dememory.git"),
            "GonzaloTorreras/ai-dememory",
        )
        self.assertIsNone(github_owner_repo_from_remote("https://example.com/GonzaloTorreras/ai-dememory.git"))
        self.assertIsNone(github_owner_repo_from_remote("https://github.com/GonzaloTorreras"))

    def test_publish_readiness_rejects_placeholder_and_cross_repo_pr_urls(self) -> None:
        zero_pr_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/0",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )
        cross_repo_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://github.com/Other/repo/pull/250",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )
        extra_path_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250/files",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )
        query_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250?view=files",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )
        fragment_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250#discussion",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )
        trailing_slash_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250/",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )
        port_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://github.com:443/GonzaloTorreras/ai-dememory/pull/250",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )
        userinfo_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [],
            pr_url="https://release-review@github.com/GonzaloTorreras/ai-dememory/pull/250",
            expected_owner_repo="GonzaloTorreras/ai-dememory",
        )

        self.assertEqual(zero_pr_blockers[0]["id"], "pr_url_required")
        self.assertIn("canonical GitHub HTTPS pull request URL", zero_pr_blockers[0]["summary"])
        self.assertEqual(cross_repo_blockers[0]["id"], "pr_url_required")
        self.assertIn("belong to this repository", cross_repo_blockers[0]["summary"])
        self.assertEqual(extra_path_blockers[0]["id"], "pr_url_required")
        self.assertIn("canonical GitHub HTTPS pull request URL", extra_path_blockers[0]["summary"])
        self.assertEqual(query_blockers[0]["id"], "pr_url_required")
        self.assertIn("canonical GitHub HTTPS pull request URL", query_blockers[0]["summary"])
        self.assertEqual(fragment_blockers[0]["id"], "pr_url_required")
        self.assertIn("canonical GitHub HTTPS pull request URL", fragment_blockers[0]["summary"])
        self.assertEqual(trailing_slash_blockers[0]["id"], "pr_url_required")
        self.assertIn("canonical GitHub HTTPS pull request URL", trailing_slash_blockers[0]["summary"])
        self.assertEqual(port_blockers[0]["id"], "pr_url_required")
        self.assertIn("canonical GitHub HTTPS pull request URL", port_blockers[0]["summary"])
        self.assertEqual(userinfo_blockers[0]["id"], "pr_url_required")
        self.assertIn("canonical GitHub HTTPS pull request URL", userinfo_blockers[0]["summary"])

    def test_publish_plan_text_escapes_dispatch_inputs(self) -> None:
        plan = {
            "repository": "testpypi",
            "workflow": ".github/workflows/publish.yml",
            "target_environment": "testpypi",
            "publishes_package": False,
            "release_ready": False,
            "publish_ready": False,
            "guard_issue_count": 0,
            "release_blocker_count": 1,
            "publish_blocker_count": 1,
            "dispatch_inputs": {
                "repository": "testpypi",
                "confirm": "publish",
                "pr_url": "https://github.com/GonzaloTorreras/ai-dememory/pull/250 ``x``\n- fake",
            },
            "preflight_commands": [["ai-dememory", "publish-plan"]],
            "next_actions": ["Review publish plan."],
        }

        text = render_publish_plan_text(plan)

        self.assertIn("```https://github.com/GonzaloTorreras/ai-dememory/pull/250 ``x`` - fake```", text)
        self.assertNotIn("\n- fake", text)

    def test_publish_plan_reports_unavailable_release_evidence_from_plain_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = publish_plan(root, repository="testpypi")

        self.assertFalse(plan["release_evidence_available"])
        self.assertEqual(plan["release_blocker_ids"], ["release_evidence_unavailable"])
        self.assertEqual(
            plan["publish_blocker_ids"],
            ["publish_guard_issues", "pr_url_required", "release_evidence_unavailable"],
        )
        self.assertFalse(plan["publish_ready"])
        self.assertEqual(plan["workflow_url"], WORKFLOW_URL_PLACEHOLDER)
        self.assertIn("canonical release workflow is missing", plan["guard_issues"][0]["message"])
        self.assertIn("git distribution checkout", " ".join(plan["next_actions"]))

    def test_publish_plan_next_actions_require_testpypi_before_pypi(self) -> None:
        actions = publish_plan_next_actions("pypi", [], True, True, [])

        self.assertIn("Publish to TestPyPI and verify install evidence before publishing to PyPI.", actions)

    def test_publish_readiness_defers_only_testpypi_acceptance_for_testpypi(self) -> None:
        blocker = {
            "id": "manual_acceptance_remaining",
            "kind": "manual_acceptance",
            "summary": "Manual acceptance remains.",
            "count": 2,
            "items": [
                "Export the generated vault template and inspect Obsidian-compatible templates; open it in Obsidian when a GUI reviewer is available.",
                "Publish to TestPyPI only after package and Docker smoke pass in CI and publish workflow preflight.",
            ],
        }

        testpypi_blockers = publish_readiness_blockers(
            "testpypi",
            [],
            [blocker],
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250",
        )
        pypi_blockers = publish_readiness_blockers(
            "pypi",
            [],
            [blocker],
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250",
        )

        self.assertEqual(testpypi_blockers[0]["count"], 1)
        self.assertNotIn("Publish to TestPyPI", "\n".join(testpypi_blockers[0]["items"]))
        self.assertEqual(pypi_blockers[0]["count"], 2)

    def test_publish_plan_requires_real_pr_url_for_strict_publish_ready(self) -> None:
        evidence = type(
            "Evidence",
            (),
            {
                "release_ready": False,
                "release_blockers": [
                    {
                        "id": "manual_acceptance_remaining",
                        "kind": "manual_acceptance",
                        "summary": "Manual acceptance remains.",
                        "count": 1,
                        "items": [
                            "Publish to TestPyPI only after package and Docker smoke pass in CI and publish workflow preflight.",
                        ],
                    }
                ],
                "manual_acceptance_remaining": [
                    "Publish to TestPyPI only after package and Docker smoke pass in CI and publish workflow preflight.",
                ],
                "recall_fixture_freshness": {"status": "fresh"},
            },
        )()

        with (
            patch.object(publish_plan_module, "build_release_evidence", return_value=evidence),
            patch.object(publish_plan_module, "validate_publish_workflow", return_value=[]),
        ):
            missing_pr = publish_plan(ROOT, repository="testpypi")
            testpypi = publish_plan(
                ROOT,
                repository="testpypi",
                pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250",
            )
            pypi = publish_plan(
                ROOT,
                repository="pypi",
                pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250",
            )

        self.assertFalse(missing_pr["publish_ready"])
        self.assertEqual(missing_pr["publish_blocker_ids"], ["pr_url_required"])
        self.assertTrue(testpypi["publish_ready"])
        self.assertFalse(testpypi["release_ready"])
        self.assertFalse(pypi["publish_ready"])
        self.assertEqual(pypi["publish_blocker_ids"], ["manual_acceptance_remaining"])

    def test_release_check_rejects_cross_repo_pr_url(self) -> None:
        check = check_pr_gate(ROOT, "https://github.com/Other/repo/pull/250")
        extra_path = check_pr_gate(ROOT, "https://github.com/GonzaloTorreras/ai-dememory/pull/250/files")
        query = check_pr_gate(ROOT, "https://github.com/GonzaloTorreras/ai-dememory/pull/250?view=files")
        fragment = check_pr_gate(ROOT, "https://github.com/GonzaloTorreras/ai-dememory/pull/250#discussion")
        trailing_slash = check_pr_gate(ROOT, "https://github.com/GonzaloTorreras/ai-dememory/pull/250/")
        port = check_pr_gate(ROOT, "https://github.com:443/GonzaloTorreras/ai-dememory/pull/250")
        userinfo = check_pr_gate(ROOT, "https://release-review@github.com/GonzaloTorreras/ai-dememory/pull/250")

        self.assertEqual(check.status, "fail")
        self.assertIn("GonzaloTorreras/ai-dememory", check.detail)
        self.assertEqual(extra_path.status, "fail")
        self.assertIn("canonical GitHub HTTPS pull request URL", extra_path.detail)
        self.assertEqual(query.status, "fail")
        self.assertIn("canonical GitHub HTTPS pull request URL", query.detail)
        self.assertEqual(fragment.status, "fail")
        self.assertIn("canonical GitHub HTTPS pull request URL", fragment.detail)
        self.assertEqual(trailing_slash.status, "fail")
        self.assertIn("canonical GitHub HTTPS pull request URL", trailing_slash.detail)
        self.assertEqual(port.status, "fail")
        self.assertIn("canonical GitHub HTTPS pull request URL", port.detail)
        self.assertEqual(userinfo.status, "fail")
        self.assertIn("canonical GitHub HTTPS pull request URL", userinfo.detail)

    def test_ci_guard_accepts_current_workflow(self) -> None:
        issues = validate_ci_workflow(ROOT)

        self.assertFalse(issues)

    def test_ci_guard_rejects_missing_required_v2_gates(self) -> None:
        incomplete = """
name: CI
on:
  pull_request:
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m unittest discover -s tests
"""

        issues = validate_ci_workflow_text(incomplete)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("pushes to main", messages)
        self.assertIn("python scripts/ai_dememory.py install-smoke", messages)
        self.assertIn("python scripts/ai_dememory.py package-build-smoke", messages)
        self.assertIn("python scripts/ai_dememory.py artifact-guard", messages)
        self.assertIn("python scripts/ai_dememory.py package-build-smoke --check-clean", messages)
        self.assertIn("python scripts/ai_dememory.py vault-setup-guard", messages)
        self.assertIn("python scripts/ai_dememory.py pr-template-guard", messages)
        self.assertIn("python scripts/ai_dememory.py pr-draft-guard", messages)
        self.assertIn("python scripts/ai_dememory.py acceptance-guard", messages)
        self.assertIn("python scripts/ai_dememory.py adr-guard", messages)
        self.assertIn("python scripts/ai_dememory.py release-checklist-guard", messages)
        self.assertIn("python scripts/ai_dememory.py roadmap status --json", messages)
        self.assertIn("python scripts/ai_dememory.py release-check --strict", messages)
        self.assertIn("python scripts/ai_dememory.py api-smoke", messages)
        self.assertIn("python scripts/ai_dememory.py mcp-smoke", messages)
        self.assertIn("missing required PR-gated step name: Strict PR release readiness check", messages)
        self.assertIn("missing required PR-gated step name: MCP runtime smoke", messages)
        self.assertIn("python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci", messages)

    def test_ci_guard_rejects_mcp_smoke_without_pr_url_gate(self) -> None:
        incomplete = """
name: CI
on:
  pull_request:
  push:
    branches:
      - main
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m compileall -q scripts mcp/server ai_dememory_tool
      - run: python scripts/ai_dememory.py validate
      - run: python scripts/ai_dememory.py secret-scan
      - run: python scripts/ai_dememory.py verify-mcp
      - run: python scripts/ai_dememory.py artifact-guard
      - run: python scripts/ai_dememory.py vault-setup-guard
      - run: python scripts/ai_dememory.py pr-template-guard
      - run: python scripts/ai_dememory.py pr-draft-guard
      - run: python scripts/ai_dememory.py acceptance-guard
      - run: python scripts/ai_dememory.py adr-guard
      - run: python scripts/ai_dememory.py release-checklist-guard
      - run: python scripts/ai_dememory.py release-check
      - run: python scripts/ai_dememory.py roadmap status --json
      - run: python scripts/ai_dememory.py api-smoke
      - run: python -m unittest discover -s tests
      - run: python scripts/ai_dememory.py index
      - run: python scripts/ai_dememory.py search codex --limit 1
      - run: python scripts/ai_dememory.py eval-recall
      - name: MCP runtime smoke
        run: python scripts/ai_dememory.py mcp-smoke
      - run: python scripts/ai_dememory.py install-smoke
      - run: python scripts/ai_dememory.py package-build-smoke
      - run: python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci
      - name: Final package build artifact guard
        run: python scripts/ai_dememory.py package-build-smoke --check-clean
"""

        issues = validate_ci_workflow_text(incomplete)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("pull_request events", messages)
        self.assertIn("AI_DEMEMORY_PR_URL", messages)
        self.assertIn("python scripts/ai_dememory.py release-check --strict", messages)

    def test_ci_guard_rejects_strict_release_check_without_own_pr_gate(self) -> None:
        incomplete = """
name: CI
on:
  pull_request:
  push:
    branches:
      - main
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m compileall -q scripts mcp/server ai_dememory_tool
      - run: python scripts/ai_dememory.py validate
      - run: python scripts/ai_dememory.py secret-scan
      - run: python scripts/ai_dememory.py verify-mcp
      - run: python scripts/ai_dememory.py artifact-guard
      - run: python scripts/ai_dememory.py vault-setup-guard
      - run: python scripts/ai_dememory.py pr-template-guard
      - run: python scripts/ai_dememory.py pr-draft-guard
      - run: python scripts/ai_dememory.py acceptance-guard
      - run: python scripts/ai_dememory.py adr-guard
      - run: python scripts/ai_dememory.py release-checklist-guard
      - run: python scripts/ai_dememory.py release-check
      - run: python scripts/ai_dememory.py roadmap status --json
      - run: python scripts/ai_dememory.py api-smoke
      - run: python -m unittest discover -s tests
      - run: python scripts/ai_dememory.py index
      - run: python scripts/ai_dememory.py search codex --limit 1
      - run: python scripts/ai_dememory.py eval-recall
      - name: Strict PR release readiness check
        run: python scripts/ai_dememory.py release-check --strict
      - name: MCP runtime smoke
        if: ${{ github.event_name == 'pull_request' }}
        env:
          AI_DEMEMORY_PR_URL: ${{ github.event.pull_request.html_url }}
        run: python scripts/ai_dememory.py mcp-smoke
      - run: python scripts/ai_dememory.py install-smoke
      - run: python scripts/ai_dememory.py package-build-smoke
      - run: python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci
      - name: Final package build artifact guard
        run: python scripts/ai_dememory.py package-build-smoke --check-clean
"""

        issues = validate_ci_workflow_text(incomplete)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Strict PR release readiness check must run only on pull_request events", messages)

    def test_ci_guard_rejects_mcp_smoke_without_own_pr_url_env(self) -> None:
        incomplete = """
name: CI
on:
  pull_request:
  push:
    branches:
      - main
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m compileall -q scripts mcp/server ai_dememory_tool
      - run: python scripts/ai_dememory.py validate
      - run: python scripts/ai_dememory.py secret-scan
      - run: python scripts/ai_dememory.py verify-mcp
      - run: python scripts/ai_dememory.py artifact-guard
      - run: python scripts/ai_dememory.py vault-setup-guard
      - run: python scripts/ai_dememory.py pr-template-guard
      - run: python scripts/ai_dememory.py pr-draft-guard
      - run: python scripts/ai_dememory.py acceptance-guard
      - run: python scripts/ai_dememory.py adr-guard
      - run: python scripts/ai_dememory.py release-checklist-guard
      - run: python scripts/ai_dememory.py release-check
      - run: python scripts/ai_dememory.py roadmap status --json
      - run: python scripts/ai_dememory.py api-smoke
      - run: python -m unittest discover -s tests
      - run: python scripts/ai_dememory.py index
      - run: python scripts/ai_dememory.py search codex --limit 1
      - run: python scripts/ai_dememory.py eval-recall
      - name: Strict PR release readiness check
        if: ${{ github.event_name == 'pull_request' }}
        env:
          AI_DEMEMORY_PR_URL: ${{ github.event.pull_request.html_url }}
        run: python scripts/ai_dememory.py release-check --strict
      - name: MCP runtime smoke
        if: ${{ github.event_name == 'pull_request' }}
        run: python scripts/ai_dememory.py mcp-smoke
      - run: python scripts/ai_dememory.py install-smoke
      - run: python scripts/ai_dememory.py package-build-smoke
      - run: python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci
      - name: Final package build artifact guard
        run: python scripts/ai_dememory.py package-build-smoke --check-clean
"""

        issues = validate_ci_workflow_text(incomplete)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("MCP runtime smoke must run only on pull_request events", messages)

    def test_ci_guard_rejects_strict_release_check_before_index_search(self) -> None:
        incomplete = """
name: CI
on:
  pull_request:
  push:
    branches:
      - main
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m compileall -q scripts mcp/server ai_dememory_tool
      - run: python scripts/ai_dememory.py validate
      - run: python scripts/ai_dememory.py secret-scan
      - run: python scripts/ai_dememory.py verify-mcp
      - run: python scripts/ai_dememory.py artifact-guard
      - run: python scripts/ai_dememory.py vault-setup-guard
      - run: python scripts/ai_dememory.py pr-template-guard
      - run: python scripts/ai_dememory.py pr-draft-guard
      - run: python scripts/ai_dememory.py acceptance-guard
      - run: python scripts/ai_dememory.py adr-guard
      - run: python scripts/ai_dememory.py release-checklist-guard
      - run: python scripts/ai_dememory.py release-check
      - run: python scripts/ai_dememory.py roadmap status --json
      - run: python scripts/ai_dememory.py api-smoke
      - run: python -m unittest discover -s tests
      - run: python scripts/ai_dememory.py eval-recall
      - name: Strict PR release readiness check
        if: ${{ github.event_name == 'pull_request' }}
        env:
          AI_DEMEMORY_PR_URL: ${{ github.event.pull_request.html_url }}
        run: python scripts/ai_dememory.py release-check --strict
      - name: MCP runtime smoke
        if: ${{ github.event_name == 'pull_request' }}
        env:
          AI_DEMEMORY_PR_URL: ${{ github.event.pull_request.html_url }}
        run: python scripts/ai_dememory.py mcp-smoke
      - run: python scripts/ai_dememory.py index
      - run: python scripts/ai_dememory.py search codex --limit 1
      - run: python scripts/ai_dememory.py install-smoke
      - run: python scripts/ai_dememory.py package-build-smoke
      - run: python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci
      - name: Final package build artifact guard
        run: python scripts/ai_dememory.py package-build-smoke --check-clean
"""

        issues = validate_ci_workflow_text(incomplete)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("after index/search/recall smoke", messages)

    def test_ci_guard_rejects_missing_final_artifact_guard(self) -> None:
        incomplete = """
name: CI
on:
  pull_request:
  push:
    branches:
      - main
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m compileall -q scripts mcp/server ai_dememory_tool
      - run: python scripts/ai_dememory.py validate
      - run: python scripts/ai_dememory.py secret-scan
      - run: python scripts/ai_dememory.py verify-mcp
      - run: python scripts/ai_dememory.py artifact-guard
      - run: python scripts/ai_dememory.py vault-setup-guard
      - run: python scripts/ai_dememory.py pr-template-guard
      - run: python scripts/ai_dememory.py pr-draft-guard
      - run: python scripts/ai_dememory.py acceptance-guard
      - run: python scripts/ai_dememory.py adr-guard
      - run: python scripts/ai_dememory.py release-checklist-guard
      - run: python scripts/ai_dememory.py release-check
      - run: python scripts/ai_dememory.py roadmap status --json
      - run: python scripts/ai_dememory.py api-smoke
      - run: python -m unittest discover -s tests
      - run: python scripts/ai_dememory.py index
      - run: python scripts/ai_dememory.py search codex --limit 1
      - run: python scripts/ai_dememory.py eval-recall
      - run: python scripts/ai_dememory.py install-smoke
      - run: python scripts/ai_dememory.py package-build-smoke
      - run: python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci
"""

        issues = validate_ci_workflow_text(incomplete)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("python scripts/ai_dememory.py package-build-smoke --check-clean", messages)
        self.assertIn("missing required post-smoke step name", messages)

    def test_pr_template_guard_accepts_current_template(self) -> None:
        issues = validate_pr_template(ROOT)

        self.assertFalse(issues)

    def test_pr_template_guard_rejects_missing_required_gates(self) -> None:
        incomplete = """
## Summary

## Validation

- [ ] `python3 scripts/ai_dememory.py doctor`

## MCP Runtime

- [ ] `python3 scripts/ai_dememory.py mcp-smoke`

## Safety
"""

        issues = validate_template_text(incomplete)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("python3 scripts/ai_dememory.py release-check", messages)
        self.assertIn("python3 scripts/ai_dememory.py package-build-smoke", messages)
        self.assertIn("python3 scripts/ai_dememory.py vault-setup-guard", messages)
        self.assertIn("python3 scripts/ai_dememory.py pr-template-guard", messages)
        self.assertIn("python3 scripts/ai_dememory.py pr-draft-guard", messages)
        self.assertIn("python3 scripts/ai_dememory.py adr-guard", messages)
        self.assertIn("python3 scripts/ai_dememory.py release-checklist-guard", messages)
        self.assertIn("python3 scripts/ai_dememory.py roadmap status --json", messages)
        self.assertIn("AI_DEMEMORY_PR_URL", messages)

    def test_pr_draft_guard_accepts_current_handoff_doc(self) -> None:
        issues = validate_pr_draft(ROOT)

        self.assertFalse(issues)

    def test_pr_draft_guard_rejects_stale_pr_specific_text(self) -> None:
        stale = """
# PR Handoff

Published PR:

https://github.com/GonzaloTorreras/ai-dememory/pull/1

PR title:

```text
[codex] Build memory MVP toolchain
```

The PR has been marked ready for review.
"""

        issues = validate_pr_draft_text(stale)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("pull/1", messages)
        self.assertIn("[codex] Build memory MVP toolchain", messages)
        self.assertIn("Published PR", messages)
        self.assertIn("marked ready for review", messages)

    def test_acceptance_guard_accepts_current_checklist(self) -> None:
        issues = validate_acceptance_checklist(ROOT)

        self.assertFalse(issues)

    def test_adr_guard_accepts_current_decision_records(self) -> None:
        issues = validate_adr_docs(ROOT)

        self.assertFalse(issues)

    def test_adr_guard_rejects_missing_tradeoff_sections(self) -> None:
        incomplete = """# ADR 0031: Missing Tradeoffs

Status: Accepted

## Context

Needs a decision.

## Decision

Do the thing.
"""

        issues = validate_adr_text("docs/adr/0031-missing-tradeoffs.md", incomplete, 31)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("benefits", messages)
        self.assertIn("limitations", messages)
        self.assertIn("future_risks", messages)
        self.assertIn("Dependencies", messages)

    def test_adr_guard_accepts_legacy_section_names_before_dependency_cutoff(self) -> None:
        legacy = """# ADR 0002: Legacy Shape

Status: Accepted

## Context

Need compatibility.

## Decision

Keep old names.

## Consequences

This records benefits.

## Caveats

This records limitations.

## Future Work

This records future risks.
"""

        issues = validate_adr_text("docs/adr/0002-legacy-shape.md", legacy, 2)

        self.assertFalse(issues)

    def test_release_checklist_guard_accepts_current_checklist(self) -> None:
        issues = validate_release_checklist(ROOT)

        self.assertFalse(issues)

    def test_roadmap_status_reports_current_v2_phases(self) -> None:
        payload = roadmap_status(ROOT)
        phases = payload["phases"]
        statuses = {phase["phase"]: phase["status"] for phase in phases}

        self.assertFalse(payload["mutates_files"])
        self.assertFalse(payload["writes_files"])
        self.assertEqual(payload["phase_count"], 11)
        self.assertEqual(statuses[0], "implemented")
        self.assertEqual(statuses[1], "implemented")
        self.assertEqual(statuses[10], "gated")
        self.assertEqual(payload["status_counts"]["implemented"], 10)
        self.assertEqual(payload["status_counts"]["gated"], 1)
        self.assertNotIn("missing_evidence", payload["status_counts"])

    def test_roadmap_status_markdown_includes_phase_evidence(self) -> None:
        text = render_roadmap_status_markdown(roadmap_status(ROOT))

        self.assertIn("# v2 Roadmap Status", text)
        self.assertIn("Phase 1: Token-budgeted context and explainable search", text)
        self.assertIn("`scripts/context_memory.py`", text)
        self.assertIn("status: `gated`", text)

    def test_release_checklist_guard_rejects_missing_required_gates(self) -> None:
        incomplete = """
# v2.0 Release Checklist

## Static Checks

- [ ] `python3 scripts/ai_dememory.py doctor`

## Manual Acceptance

- [ ] Record reviewed manual proof with `ai-dememory acceptance record --item <item-id>`.
"""

        issues = validate_release_checklist_text(incomplete)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("Package Install Smoke", messages)
        self.assertIn("python3 scripts/ai_dememory.py pr-draft-guard", messages)
        self.assertIn("python3 scripts/ai_dememory.py roadmap status --json", messages)
        self.assertIn("python3 scripts/ai_dememory.py release-checklist-guard", messages)
        self.assertIn("docker build -t ai-dememory:local .", messages)
        self.assertIn("AI_DEMEMORY_PR_URL", messages)

    def test_acceptance_guard_rejects_missing_registry_items(self) -> None:
        incomplete = """
# v2.0 Release Checklist

## Manual Acceptance

- [ ] `obsidian-vault`: Export the generated vault template and inspect Obsidian-compatible templates; open it in Obsidian when a GUI reviewer is available.
- [ ] Record reviewed manual proof with `ai-dememory acceptance record --item <item-id>`.
"""

        issues = validate_acceptance_checklist_text(incomplete)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("mcp-client-installed", messages)
        self.assertIn("Use one real MCP client with installed CLI config.", messages)
        self.assertIn("testpypi-publish", messages)

    def test_artifact_guard_accepts_source_and_docs_paths(self) -> None:
        issues = validate_artifact_paths(
            [
                "README.md",
                "docs/release-v2-checklist.md",
                "scripts/artifact_guard.py",
                "ai_dememory_tool/cli.py",
            ]
        )

        self.assertFalse(issues)

    def test_artifact_guard_rejects_generated_and_cache_paths(self) -> None:
        issues = validate_artifact_paths(
            [
                "indexes/memory.sqlite",
                "reports/v2-release-evidence.md",
                "distilled/session.md",
                "working/current.json",
                "working/handoffs/2026-07-04-handoff.md",
                "build/lib/ai_dememory_tool/cli.py",
                "dist/ai_dememory-2.0.0.tar.gz",
                "ai_dememory.egg-info/PKG-INFO",
                "scripts/__pycache__/artifact_guard.cpython-312.pyc",
                ".pytest_cache/v/cache/nodeids",
            ]
        )

        reasons = {issue.path: issue.reason for issue in issues}
        self.assertIn("indexes/memory.sqlite", reasons)
        self.assertIn("reports/v2-release-evidence.md", reasons)
        self.assertIn("distilled/session.md", reasons)
        self.assertIn("working/current.json", reasons)
        self.assertIn("working/handoffs/2026-07-04-handoff.md", reasons)
        self.assertIn("build/lib/ai_dememory_tool/cli.py", reasons)
        self.assertIn("dist/ai_dememory-2.0.0.tar.gz", reasons)
        self.assertIn("ai_dememory.egg-info/PKG-INFO", reasons)
        self.assertIn("scripts/__pycache__/artifact_guard.cpython-312.pyc", reasons)
        self.assertIn(".pytest_cache/v/cache/nodeids", reasons)

    def test_vault_setup_guard_accepts_current_docs_and_template(self) -> None:
        issues = validate_vault_setup(ROOT)

        self.assertFalse(issues)

    def test_vault_setup_guard_rejects_whole_generated_directory_git_add(self) -> None:
        text = """# Create A Memory Repo

```bash
git add README.md .gitignore memories distilled indexes reports
```

Private vault setup does not stage generated artifact directories.
Commit placeholders: distilled/README.md indexes/README.md reports/README.md.
"""

        issues = validate_create_memory_repo_text(text)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("`distilled/`", messages)
        self.assertIn("`indexes/`", messages)
        self.assertIn("`reports/`", messages)

    def test_release_evidence_summarizes_automated_and_manual_state(self) -> None:
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/250"
        evidence = build_release_evidence(ROOT, pr_url=pr_url, reviewer="Unit Reviewer")
        markdown = render_markdown(evidence)

        self.assertEqual(evidence.pr_url, pr_url)
        self.assertEqual(evidence.reviewer, "Unit Reviewer")
        self.assertEqual(evidence.mcp_tool_count, 74)
        self.assertEqual(evidence.publish_guard_issues, 0)
        self.assertEqual(evidence.inventory_doc_issues, 0)
        self.assertEqual(evidence.automated_summary["total"], len(evidence.automated_checks))
        self.assertEqual(evidence.automated_summary["fail"], 0)
        pr_gate = next(check for check in evidence.automated_checks if check["name"] == "pr_gate")
        self.assertEqual(pr_gate["status"], "ok")
        self.assertEqual(pr_gate["detail"], pr_url)
        warning_names = {check["name"] for check in evidence.automated_checks if check["status"] == "warn"}
        self.assertNotIn("pr_gate", warning_names)
        self.assertFalse(evidence.release_ready)
        blocker_ids = {item["id"] for item in evidence.release_blockers}
        self.assertIn("manual_acceptance_remaining", blocker_ids)
        recall_eval_clean = (
            bool(evidence.vector_readiness["available"])
            and evidence.vector_readiness["decision"] == "not_justified"
            and int(evidence.vector_readiness.get("recall", {}).get("failed_cases", 0)) == 0
        )
        if recall_eval_clean:
            self.assertNotIn("recall_fixture_review", blocker_ids)
        else:
            self.assertIn("recall_fixture_review", blocker_ids)
        self.assertIn("next_actions", evidence_to_dict(evidence))
        self.assertTrue(evidence.next_actions)
        self.assertIn(
            "Record reviewed passing manual acceptance evidence for remaining items.",
            evidence.next_actions,
        )
        self.assertIn("handoff_commands", evidence_to_dict(evidence))
        self.assertFalse(evidence.handoff_commands["payload_mutates_system"])
        self.assertFalse(evidence.handoff_commands["payload_runs_commands"])
        self.assertFalse(evidence.handoff_commands["payload_records_evidence"])
        self.assertFalse(evidence.handoff_commands["payload_writes_files"])
        self.assertFalse(evidence.handoff_commands["commands_mutate_system"])
        self.assertTrue(evidence.handoff_commands["commands_run_commands"])
        self.assertFalse(evidence.handoff_commands["commands_record_evidence"])
        self.assertTrue(evidence.handoff_commands["commands_write_files"])
        self.assertFalse(evidence.handoff_commands["commands_publish_package"])
        command_side_effects = evidence.handoff_commands["command_side_effects"]
        self.assertTrue(command_side_effects["release_evidence_report"]["writes_files"])
        self.assertTrue(command_side_effects["acceptance_packet"]["writes_files"])
        self.assertTrue(command_side_effects["recall_review_packet"]["writes_files"])
        self.assertFalse(command_side_effects["strict_release_evidence"]["writes_files"])
        self.assertTrue(command_side_effects["publish_plan_testpypi"]["runs_commands"])
        self.assertFalse(command_side_effects["publish_plan_testpypi"]["publishes_package"])
        self.assertEqual(
            evidence.handoff_commands["commands"]["strict_release_evidence"],
            [
                "ai-dememory",
                "release-evidence",
                "--strict",
                "--pr-url",
                pr_url,
                "--reviewer",
                "Unit Reviewer",
            ],
        )
        self.assertIn("reports/v2-release-evidence.md", evidence.handoff_commands["commands"]["release_evidence_report"])
        self.assertEqual(
            evidence.handoff_commands["commands"]["acceptance_plan"],
            [
                "ai-dememory",
                "acceptance",
                "plan",
                "--reviewer",
                "Unit Reviewer",
                "--pr-url",
                pr_url,
                "--json",
            ],
        )
        self.assertEqual(
            evidence.handoff_commands["commands"]["acceptance_template"],
            [
                "ai-dememory",
                "acceptance",
                "template",
                "--item",
                "<item-id>",
                "--reviewer",
                "Unit Reviewer",
                "--pr-url",
                pr_url,
                "--json",
            ],
        )
        self.assertEqual(
            evidence.handoff_commands["commands"]["publish_plan_testpypi"],
            [
                "ai-dememory",
                "publish-plan",
                "--repository",
                "testpypi",
                "--pr-url",
                pr_url,
            ],
        )
        self.assertEqual(
            evidence.handoff_commands["commands"]["publish_plan_pypi"],
            [
                "ai-dememory",
                "publish-plan",
                "--repository",
                "pypi",
                "--pr-url",
                pr_url,
            ],
        )
        self.assertEqual(
            evidence.handoff_commands["commands"]["acceptance_verify"],
            ["ai-dememory", "acceptance", "verify"],
        )
        self.assertEqual(evidence.recall_fixture_freshness["status"], "needs_reviewed_promotion")
        self.assertTrue(evidence.recall_fixture_freshness["stale"])
        self.assertEqual(evidence.recall_fixture_review_plan["status"], "needs_reviewed_promotion")
        self.assertIn("next_actions", evidence.recall_fixture_review_plan)
        self.assertIn("candidate_check_command", evidence.recall_fixture_review_plan)
        self.assertIn("check-miss", evidence.recall_fixture_review_plan["candidate_check_command"])
        self.assertIn("resolved_count", evidence.recall_fixture_review_plan)
        self.assertIn("recent_resolved_misses", evidence.recall_fixture_review_plan)
        self.assertIn(evidence.vector_readiness["decision"], {"not_justified", "unavailable"})
        if evidence.vector_readiness["available"]:
            self.assertEqual(evidence.vector_readiness["decision"], "not_justified")
        self.assertFalse(evidence.vector_readiness["creates_embeddings"])
        self.assertFalse(evidence.vector_readiness["mutates_system"])
        self.assertIn("setup_health_summary", evidence_to_dict(evidence))
        self.assertFalse(evidence.setup_health_summary["mutates_system"])
        self.assertFalse(evidence.setup_health_summary["runs_commands"])
        self.assertFalse(evidence.setup_health_summary["writes_files"])
        self.assertTrue(evidence.setup_health_summary["validation_ok"])
        self.assertIn("manual_acceptance", evidence.setup_health_summary)
        self.assertEqual(
            evidence.setup_health_summary["manual_acceptance"]["remaining_count"],
            evidence.manual_acceptance_total - len(evidence.manual_acceptance_completed),
        )
        self.assertIn("recall_review", evidence.setup_health_summary)
        self.assertIn("vector_readiness", evidence.setup_health_summary)
        self.assertFalse(evidence.setup_health_summary["vector_readiness"]["creates_embeddings"])
        self.assertIn("generated_packet_archives", evidence.setup_health_summary)
        self.assertFalse(evidence.setup_health_summary["generated_packet_archives"]["writes_files"])
        self.assertFalse(evidence.setup_health_summary["generated_packet_archives"]["deletes_files"])
        self.assertIn("prunable_count", evidence.setup_health_summary["generated_packet_archives"])
        self.assertIn("maintenance_summary", evidence_to_dict(evidence))
        self.assertFalse(evidence.maintenance_summary["mutates_system"])
        self.assertFalse(evidence.maintenance_summary["runs_commands"])
        self.assertFalse(evidence.maintenance_summary["writes_files"])
        self.assertFalse(evidence.maintenance_summary["deletes_files"])
        self.assertIn("generated_packet_archives", evidence.maintenance_summary)
        self.assertIn("prunable_count", evidence.maintenance_summary["generated_packet_archives"])
        self.assertFalse(evidence.maintenance_summary["generated_packet_archives"]["writes_files"])
        self.assertFalse(evidence.maintenance_summary["generated_packet_archives"]["deletes_files"])
        self.assertIn("artifact_freshness", evidence.maintenance_summary)
        self.assertIn("stale_count", evidence.maintenance_summary["artifact_freshness"])
        self.assertFalse(evidence.maintenance_summary["artifact_freshness"]["writes_files"])
        self.assertIn("provider_readiness", evidence.maintenance_summary)
        self.assertFalse(evidence.maintenance_summary["provider_readiness"]["reads_provider_files"])
        self.assertFalse(evidence.maintenance_summary["provider_readiness"]["writes_import_candidates"])
        self.assertIn("review_recommendations", evidence.maintenance_summary)
        self.assertFalse(evidence.maintenance_summary["review_recommendations"]["applies_review_decisions"])
        self.assertIn("next_actions", evidence.setup_health_summary)
        self.assertEqual(evidence.manual_acceptance_total, len(ACCEPTANCE_ITEMS))
        self.assertTrue(evidence.manual_acceptance_remaining)
        self.assertIsInstance(evidence.manual_acceptance_completed, list)
        self.assertIsInstance(evidence.manual_acceptance_blocked, list)
        self.assertEqual(
            evidence.manual_acceptance_plan["remaining_count"],
            evidence.manual_acceptance_total - len(evidence.manual_acceptance_completed),
        )
        self.assertEqual(evidence.manual_acceptance_plan["reviewer"], "Unit Reviewer")
        self.assertEqual(evidence.manual_acceptance_plan["pr_url"], pr_url)
        remaining_plan_item = next(item for item in evidence.manual_acceptance_plan["items"] if item["pass_command"])
        self.assertIn(f"--artifact '{pr_url}'", remaining_plan_item["pass_command"])
        self.assertTrue(evidence.manual_acceptance_plan["next_actions"])
        self.assertIn("Release ready", markdown)
        self.assertIn("Reviewer: `Unit Reviewer`", markdown)
        self.assertIn("Release Blockers", markdown)
        self.assertIn("Next Actions", markdown)
        self.assertIn("Handoff Commands", markdown)
        self.assertIn("strict_release_evidence", markdown)
        self.assertIn("--reviewer 'Unit Reviewer'", markdown)
        self.assertNotIn("--reviewer Unit Reviewer", markdown)
        self.assertIn("acceptance_plan", markdown)
        self.assertIn("acceptance_template", markdown)
        self.assertIn("publish_plan_testpypi", markdown)
        self.assertIn("publish_plan_pypi", markdown)
        self.assertIn("acceptance_packet", markdown)
        self.assertIn("recall_review_packet", markdown)
        self.assertIn("Recall Fixture Freshness", markdown)
        self.assertIn("Recall Review Plan", markdown)
        self.assertIn("Vector Readiness", markdown)
        self.assertIn("creates embeddings", markdown)
        self.assertIn("Setup Health Summary", markdown)
        self.assertIn("Maintenance Summary", markdown)
        self.assertIn("validation ok", markdown)
        self.assertIn("scheduler ready", markdown)
        self.assertIn("generated packet archive prunable", markdown)
        self.assertIn("artifact freshness stale", markdown)
        self.assertIn("deletes archives", markdown)
        self.assertIn("candidate check", markdown)
        self.assertIn("resolved misses", markdown)
        if recall_eval_clean:
            self.assertNotIn("- `recall_fixture_review`", markdown)
        else:
            self.assertIn("recall_fixture_review", markdown)
        self.assertIn("manual_acceptance_remaining", markdown)
        self.assertIn("Record reviewed passing manual acceptance evidence", markdown)
        self.assertIn(f"completed: `{len(evidence.manual_acceptance_completed)}/", markdown)
        self.assertIn("Manual Acceptance Completed", markdown)
        self.assertIn("Manual Acceptance Blocked", markdown)
        self.assertIn("Manual Acceptance Remaining", markdown)
        self.assertIn("Manual Acceptance Plan", markdown)
        self.assertIn("suggested artifacts", markdown)
        self.assertIn("ai-dememory acceptance record --item", markdown)
        self.assertIn("Automated Evidence", markdown)
        self.assertIn("pr_gate", markdown)

    def test_release_handoff_commands_use_pr_placeholder_without_recording_evidence(self) -> None:
        commands = release_handoff_commands()

        self.assertFalse(commands["payload_mutates_system"])
        self.assertFalse(commands["payload_runs_commands"])
        self.assertFalse(commands["payload_records_evidence"])
        self.assertFalse(commands["payload_writes_files"])
        self.assertFalse(commands["commands_mutate_system"])
        self.assertTrue(commands["commands_run_commands"])
        self.assertFalse(commands["commands_record_evidence"])
        self.assertTrue(commands["commands_write_files"])
        self.assertFalse(commands["commands_publish_package"])
        self.assertTrue(commands["command_side_effects"]["release_evidence_report"]["writes_files"])
        self.assertTrue(commands["command_side_effects"]["acceptance_packet"]["writes_files"])
        self.assertTrue(commands["command_side_effects"]["recall_review_packet"]["writes_files"])
        self.assertFalse(commands["command_side_effects"]["acceptance_plan"]["writes_files"])
        self.assertTrue(commands["command_side_effects"]["publish_plan_pypi"]["runs_commands"])
        self.assertFalse(commands["command_side_effects"]["publish_plan_pypi"]["publishes_package"])
        self.assertIn("<pr-url>", commands["commands"]["strict_release_evidence"])
        self.assertIn("<reviewer>", commands["commands"]["strict_release_evidence"])
        self.assertIn("<pr-url>", commands["commands"]["acceptance_plan"])
        self.assertIn("<reviewer>", commands["commands"]["acceptance_plan"])
        self.assertIn("<item-id>", commands["commands"]["acceptance_template"])
        self.assertEqual(commands["commands"]["publish_plan_testpypi"][-1], "<pr-url>")
        self.assertEqual(commands["commands"]["publish_plan_pypi"][-1], "<pr-url>")
        self.assertIn("--reviewer", commands["commands"]["acceptance_packet"])
        self.assertIn("--max-age-days", commands["commands"]["recall_review_status"])
        self.assertEqual(commands["commands"]["publish_guard"], ["ai-dememory", "publish-guard"])

    def test_release_blockers_include_vector_readiness_review_when_eligible(self) -> None:
        vector_readiness = {
            "available": True,
            "decision": "eligible_for_vector_experiment",
            "rationale": "Recall fixtures are below threshold.",
            "recall": {"recall": 0.5, "passed_cases": 1, "total_cases": 3},
            "failed_case_ids": ["miss-one", "miss-two"],
            "creates_embeddings": False,
            "mutates_system": False,
        }

        blockers = release_blockers(
            "",
            [],
            [],
            [],
            {"freshness": {"stale": False}},
            vector_readiness,
        )

        self.assertEqual(blockers[0]["id"], "vector_readiness_review")
        self.assertEqual(blockers[0]["kind"], "quality")
        self.assertEqual(blockers[0]["count"], 2)
        self.assertEqual(blockers[0]["items"][0]["decision"], "eligible_for_vector_experiment")

    def test_release_next_actions_deduplicates_and_bounds_existing_guidance(self) -> None:
        blockers = [
            {"id": "manual_acceptance_remaining"},
            {"id": "recall_fixture_review"},
            {"id": "manual_acceptance_remaining"},
        ]
        actions = release_next_actions(
            blockers,
            {"next_actions": ["Review generated packet archive retention previews before cleanup."]},
            {"next_actions": ["Promote reviewed recall miss."]},
            {"next_actions": ["Review vector readiness evidence before approving any vector experiment."]},
            {"next_actions": ["Review setup health."]},
            {
                "generated_packet_archives": {"prunable_count": 2},
                "review_recommendations": {"pending_count": 1},
            },
            limit=5,
        )

        self.assertEqual(len(actions), 5)
        self.assertEqual(
            actions[0],
            "Record reviewed passing manual acceptance evidence for remaining items.",
        )
        self.assertEqual(actions.count("Review generated packet archive retention previews before cleanup."), 1)

    def test_release_evidence_writes_generated_report_to_in_root_path(self) -> None:
        output = io.StringIO()

        with patch("sys.stdout", output):
            exit_code = release_evidence_main(
                [
                    "--root",
                    str(ROOT),
                    "--pr-url",
                    "https://github.com/GonzaloTorreras/ai-dememory/pull/250",
                    "--write-report",
                    "--report-path",
                    "reports/test-v2-release-evidence.md",
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        report = ROOT / payload["report_path"]
        report_text = report.read_text(encoding="utf-8")
        report.unlink()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["report_path"], "reports/test-v2-release-evidence.md")
        self.assertIn("# v2 Release Evidence", report_text)
        self.assertIn("Release Blockers", report_text)
        self.assertIn("Manual Acceptance Plan", report_text)

    def test_release_evidence_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "v2-release-evidence.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = release_evidence_main(
                    [
                        "--root",
                        str(ROOT),
                        "--write-report",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay under reports/", error.getvalue())
        self.assertFalse(outside.exists())

    def test_release_evidence_report_rejects_inside_root_non_report_path(self) -> None:
        target = ROOT / "docs" / "test-v2-release-evidence.md"
        error = io.StringIO()

        with patch("sys.stderr", error):
            exit_code = release_evidence_main(
                [
                    "--root",
                    str(ROOT),
                    "--write-report",
                    "--report-path",
                    str(target),
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay under reports/", error.getvalue())
        self.assertFalse(target.exists())

    def test_manual_acceptance_records_reviewed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = record_acceptance(
                root,
                "mcp-client-installed",
                "passed",
                "Unit Test",
                "Generated config was used with a real MCP client.",
                artifacts=["https://github.com/GonzaloTorreras/ai-dememory/pull/250"],
            )
            statuses = acceptance_status(root)
            remaining = remaining_acceptance_items(root)

        self.assertIn("inbox/release-acceptance", path.as_posix())
        completed = {item.id for item in statuses if item.completed}
        self.assertIn("mcp-client-installed", completed)
        self.assertNotIn(ACCEPTANCE_ITEMS["mcp-client-installed"], remaining)

    def test_manual_acceptance_rejects_symlink_acceptance_dir_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            inbox = root / "inbox"
            inbox.mkdir()
            outside_acceptance = Path(outside_tmp) / "external-acceptance"
            outside_acceptance.mkdir()
            try:
                os.symlink(outside_acceptance, inbox / "release-acceptance", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                record_acceptance(
                    root,
                    "mcp-client-installed",
                    "passed",
                    "Unit Test",
                    "Generated config was used with a real MCP client.",
                )

            outside_files = list(outside_acceptance.iterdir())

        self.assertEqual(outside_files, [])

    def test_manual_acceptance_ignores_symlinked_external_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            inbox = root / "inbox"
            inbox.mkdir()
            outside_acceptance = Path(outside_tmp) / "external-acceptance"
            outside_acceptance.mkdir()
            (outside_acceptance / "external.md").write_text(
                "---\n"
                "type: manual-acceptance\n"
                "status: passed\n"
                "acceptance_item: mcp-client-installed\n"
                "reviewed_by: External\n"
                "reviewed_at: 2026-07-04\n"
                "summary: External evidence must not count.\n"
                "artifacts: []\n"
                "---\n",
                encoding="utf-8",
            )
            try:
                os.symlink(outside_acceptance, inbox / "release-acceptance", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            statuses = acceptance_status(root)

        completed = {item.id for item in statuses if item.completed}
        self.assertNotIn("mcp-client-installed", completed)

    def test_release_evidence_reports_blocked_manual_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = record_acceptance(
                root,
                "mcp-client-docker",
                "blocked",
                "Unit Test",
                "Docker was unavailable on the manual acceptance workstation.",
                artifacts=["https://github.com/GonzaloTorreras/ai-dememory/pull/250"],
            )
            statuses = acceptance_status(root)
            remaining = remaining_acceptance_items(root)
            blocked = blocked_acceptance_items(statuses)

        self.assertIn(ACCEPTANCE_ITEMS["mcp-client-docker"], remaining)
        self.assertEqual(blocked[0]["id"], "mcp-client-docker")
        self.assertEqual(blocked[0]["description"], ACCEPTANCE_ITEMS["mcp-client-docker"])
        self.assertIn("inbox/release-acceptance", blocked[0]["records"][0]["path"])
        self.assertEqual(blocked[0]["records"][0]["path"], path.relative_to(root).as_posix())
        self.assertEqual(blocked[0]["records"][0]["reviewed_by"], "Unit Test")

    def test_manual_acceptance_verify_fails_until_all_items_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_acceptance(
                root,
                "mcp-client-docker",
                "blocked",
                "Unit Test",
                "Docker was unavailable on the manual acceptance workstation.",
            )
            partial = verify_acceptance(acceptance_status(root))

            for item_id in ACCEPTANCE_ITEMS:
                record_acceptance(
                    root,
                    item_id,
                    "passed",
                    "Unit Test",
                    f"Reviewed {item_id} acceptance.",
                )
            complete = verify_acceptance(acceptance_status(root))

        self.assertFalse(partial.complete)
        self.assertTrue(any(item["id"] == "mcp-client-docker" for item in partial.blocked))
        self.assertTrue(any(item["id"] == "mcp-client-docker" for item in partial.remaining))
        self.assertTrue(complete.complete)
        self.assertEqual(len(complete.completed), len(ACCEPTANCE_ITEMS))

    def test_manual_acceptance_latest_record_controls_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_acceptance(
                root,
                "mcp-client-docker",
                "passed",
                "Unit Test",
                "Docker MCP client worked.",
            )
            record_acceptance(
                root,
                "mcp-client-docker",
                "blocked",
                "Unit Test",
                "Docker became unavailable on the acceptance workstation.",
            )
            blocked = verify_acceptance(acceptance_status(root))
            blocked_plan = acceptance_plan(root)

            record_acceptance(
                root,
                "mcp-client-docker",
                "passed",
                "Unit Test",
                "Docker MCP client worked again.",
            )
            passed = verify_acceptance(acceptance_status(root))
            passed_plan = acceptance_plan(root)

        blocked_by_id = {item.id: item for item in blocked_plan.items}
        passed_by_id = {item.id: item for item in passed_plan.items}
        self.assertTrue(any(item["id"] == "mcp-client-docker" for item in blocked.blocked))
        self.assertTrue(any(item["id"] == "mcp-client-docker" for item in blocked.remaining))
        self.assertEqual(blocked_by_id["mcp-client-docker"].status, "blocked")
        self.assertFalse(blocked_by_id["mcp-client-docker"].completed)
        self.assertIn("--item mcp-client-docker", blocked_by_id["mcp-client-docker"].pass_command or "")
        self.assertFalse(any(item["id"] == "mcp-client-docker" for item in passed.blocked))
        self.assertTrue(any(item["id"] == "mcp-client-docker" for item in passed.completed))
        self.assertEqual(passed_by_id["mcp-client-docker"].status, "passed")
        self.assertTrue(passed_by_id["mcp-client-docker"].completed)

    def test_acceptance_plan_guides_remaining_and_blocked_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_acceptance(
                root,
                "mcp-client-installed",
                "passed",
                "Unit Test",
                "Generated config was used with a real MCP client.",
            )
            record_acceptance(
                root,
                "mcp-client-docker",
                "blocked",
                "Unit Test",
                "Docker was unavailable on the manual acceptance workstation.",
            )

            plan = acceptance_plan(root)
            with redirect_stdout(io.StringIO()):
                exit_code = acceptance_main(["--root", str(root), "plan", "--json"])

        by_id = {item.id: item for item in plan.items}
        self.assertFalse(plan.complete)
        self.assertEqual(plan.completed_count, 1)
        self.assertEqual(plan.blocked_count, 1)
        self.assertEqual(plan.remaining_count, len(ACCEPTANCE_ITEMS) - 1)
        self.assertEqual(by_id["mcp-client-installed"].status, "passed")
        self.assertIsNone(by_id["mcp-client-installed"].pass_command)
        self.assertEqual(by_id["mcp-client-docker"].status, "blocked")
        self.assertIn("--status blocked", by_id["mcp-client-docker"].blocked_command or "")
        self.assertIn("--item obsidian-vault", by_id["obsidian-vault"].pass_command or "")
        for item_id in ACCEPTANCE_ITEMS:
            self.assertEqual(by_id[item_id].suggested_artifacts, SUGGESTED_ACCEPTANCE_ARTIFACTS[item_id])
        self.assertEqual(exit_code, 0)

    def test_acceptance_plan_output_includes_suggested_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(["--root", str(root), "plan"])

        self.assertEqual(exit_code, 0)
        self.assertIn("suggested artifacts:", output.getvalue())
        self.assertIn("client log or PR comment showing initialize and ping with installed CLI", output.getvalue())
        self.assertIn("publish workflow preflight log showing install, package build, and Docker smoke", output.getvalue())

    def test_acceptance_plan_prefills_reviewer_and_pr_url_in_record_commands(self) -> None:
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/244"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            plan = acceptance_plan(root, reviewer="Unit Reviewer", pr_url=pr_url)
            with patch("sys.stdout", output):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "plan",
                        "--reviewer",
                        "Unit Reviewer",
                        "--pr-url",
                        pr_url,
                        "--json",
                    ]
                )

        payload = json.loads(output.getvalue())
        by_id = {item.id: item for item in plan.items}
        self.assertEqual(exit_code, 0)
        self.assertEqual(plan.reviewer, "Unit Reviewer")
        self.assertEqual(plan.pr_url, pr_url)
        self.assertIn("--reviewed-by 'Unit Reviewer'", by_id["obsidian-vault"].pass_command or "")
        self.assertIn(f"--artifact '{pr_url}'", by_id["obsidian-vault"].pass_command or "")
        self.assertEqual(payload["reviewer"], "Unit Reviewer")
        self.assertEqual(payload["pr_url"], pr_url)
        self.assertIn(f"--artifact '{pr_url}'", payload["items"][0]["pass_command"])

    def test_acceptance_command_arg_uses_single_quoted_literals(self) -> None:
        quoted = command_arg("Reviewer $(whoami) `Get-Secret` 'quoted'")

        self.assertTrue(quoted.startswith("'"))
        self.assertTrue(quoted.endswith("'"))
        self.assertIn("$(whoami)", quoted)
        self.assertIn("`Get-Secret`", quoted)
        self.assertNotIn('"$(whoami)"', quoted)
        self.assertIn("'\"'\"'quoted'\"'\"'", quoted)

    def test_acceptance_record_command_round_trips_with_posix_parser(self) -> None:
        reviewer = "Reviewer $(whoami) `Get-Secret` 'quoted'"
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/248?note=$(whoami)"

        command = acceptance_record_command("obsidian-vault", reviewer=reviewer, pr_url=pr_url)
        parts = shlex.split(command, posix=True)

        self.assertEqual(parts[:4], ["ai-dememory", "acceptance", "record", "--item"])
        self.assertEqual(parts[4], "obsidian-vault")
        self.assertEqual(parts[parts.index("--reviewed-by") + 1], reviewer)
        self.assertEqual(parts[parts.index("--summary") + 1], "Reviewed evidence summary.")
        self.assertEqual(parts[parts.index("--artifact") + 1], pr_url)

    def test_manual_acceptance_plan_writes_generated_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(["--root", str(root), "plan", "--write-report", "--json"])

            payload = json.loads(output.getvalue())
            report = root / DEFAULT_ACCEPTANCE_PLAN_REPORT
            report_text = report.read_text(encoding="utf-8")
            rendered_text = render_acceptance_plan_report(acceptance_plan(root))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["report_path"], "reports/manual-acceptance-plan.md")
        self.assertEqual(report_text, rendered_text)
        self.assertIn("# Manual Acceptance Plan", report_text)
        self.assertIn("Suggested Artifacts", report_text)
        self.assertIn("Record Commands", report_text)
        self.assertIn("does not record evidence", report_text)
        self.assertIn("ai-dememory acceptance record --item", report_text)

    def test_manual_acceptance_packet_writes_generated_review_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_acceptance(
                root,
                "mcp-client-installed",
                "passed",
                "Unit Test",
                "Generated config was used with a real MCP client.",
            )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(["--root", str(root), "packet", "--write-report", "--json"])

            payload = json.loads(output.getvalue())
            report = root / DEFAULT_ACCEPTANCE_PACKET_REPORT
            report_text = report.read_text(encoding="utf-8")
            rendered_text = render_acceptance_packet_report(paginate_acceptance_packet_plan(acceptance_plan(root)))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["report_path"], "reports/manual-acceptance-packet.md")
        self.assertEqual(payload["limit"], 50)
        self.assertEqual(payload["offset"], 0)
        self.assertFalse(payload["records_evidence"])
        self.assertFalse(payload["writes_acceptance_records"])
        self.assertTrue(payload["writes_files"])
        self.assertIn("# Manual Acceptance Packet", report_text)
        self.assertEqual(report_text, rendered_text)
        self.assertIn("Reviewer Fill-In", report_text)
        self.assertIn("Pass Command", report_text)
        self.assertIn("Block Command", report_text)
        self.assertIn("Final Gates", report_text)
        self.assertIn("not acceptance evidence", report_text)
        self.assertIn("ai-dememory acceptance record --item", report_text)

    def test_manual_acceptance_packet_writes_timestamped_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--reviewer",
                        "Unit Reviewer",
                        "--archive",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            archive_path = root / payload["archive_path"]
            archive_text = archive_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["writes_files"])
        self.assertTrue(payload["writes_archive"])
        self.assertIsNone(payload["report_path"])
        self.assertTrue(payload["archive_path"].startswith("reports/manual-acceptance-packets/"))
        self.assertRegex(payload["archive_path"], r"manual-acceptance-packet-\d{8}T\d{6}Z\.md$")
        self.assertIn("Manual Acceptance Packet", archive_text)
        self.assertIn("reviewer: `Unit Reviewer`", archive_text)

    def test_manual_acceptance_packet_archive_path_is_unique_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 6, 22, 12, 34, 56, tzinfo=timezone.utc)
            first = acceptance_packet_archive_path(root, now=now)
            first.parent.mkdir(parents=True)
            first.write_text("first\n", encoding="utf-8")
            second = acceptance_packet_archive_path(root, now=now)

            with self.assertRaisesRegex(ValueError, "archive dir must stay inside the memory root"):
                acceptance_packet_archive_path(root, Path(tmp).parent / "outside")

        self.assertEqual(first.name, "manual-acceptance-packet-20260622T123456Z.md")
        self.assertEqual(second.name, "manual-acceptance-packet-20260622T123456Z-1.md")
        self.assertTrue(first.as_posix().endswith("reports/manual-acceptance-packets/manual-acceptance-packet-20260622T123456Z.md"))

    def test_manual_acceptance_packet_archive_rejects_symlinked_reports_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside_reports = root / "active"
            outside_reports.mkdir()
            reports = root / "reports"
            try:
                os.symlink(outside_reports, reports, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "archive dir must not contain symlinks"):
                write_acceptance_packet_archive(root, paginate_acceptance_packet_plan(acceptance_plan(root)))
            redirected_files = list(outside_reports.rglob("*.md"))

        self.assertEqual(redirected_files, [])

    def test_manual_acceptance_packet_archive_rejects_symlinked_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            archive_parent = root / "reports"
            archive_parent.mkdir(parents=True)
            outside_archive = root / "active"
            outside_archive.mkdir()
            archive_root = archive_parent / "manual-acceptance-packets"
            try:
                os.symlink(outside_archive, archive_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "archive dir must not contain symlinks"):
                write_acceptance_packet_archive(root, paginate_acceptance_packet_plan(acceptance_plan(root)))
            redirected_files = list(outside_archive.glob("*.md"))

        self.assertEqual(redirected_files, [])

    def test_manual_acceptance_packet_invalid_archive_dir_writes_no_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp).parent / "outside"

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--write-report",
                        "--archive",
                        "--archive-dir",
                        str(outside),
                    ]
                )

            report_exists = (root / DEFAULT_ACCEPTANCE_PACKET_REPORT).exists()

        self.assertEqual(exit_code, 1)
        self.assertFalse(report_exists)

    def test_manual_acceptance_packet_archive_rejects_rendered_secret_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_like_reviewer = "sk-" + "proj-" + ("c" * 26)
            plan = annotate_acceptance_packet_plan(
                paginate_acceptance_packet_plan(acceptance_plan(root)),
                reviewer=secret_like_reviewer,
            )
            archive_root = root / DEFAULT_ACCEPTANCE_PACKET_ARCHIVE_DIR

            with self.assertRaisesRegex(ValueError, "acceptance packet archive rejected by secret scan"):
                write_acceptance_packet_archive(root, plan)

        self.assertFalse(archive_root.exists())

    def test_manual_acceptance_packet_archive_status_lists_paginated_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = paginate_acceptance_packet_plan(acceptance_plan(root))
            first = write_acceptance_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            second = write_acceptance_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc),
            )

            first_page = acceptance_packet_archive_status(root, limit=1)
            second_page = acceptance_packet_archive_status(root, limit=1, offset=1)

        self.assertEqual(first_page["archive_root"], "reports/manual-acceptance-packets")
        self.assertEqual(first_page["total_count"], 2)
        self.assertEqual(first_page["returned_count"], 1)
        self.assertEqual(first_page["next_offset"], 1)
        self.assertTrue(first_page["has_more"])
        self.assertEqual(first_page["archives"][0]["path"], repo_relative_path(second, root))
        self.assertEqual(first_page["archives"][0]["generated_at"], "2026-06-23T12:00:00Z")
        self.assertGreater(first_page["archives"][0]["size_bytes"], 0)
        self.assertFalse(first_page["writes_files"])
        self.assertFalse(first_page["records_evidence"])
        self.assertFalse(first_page["writes_acceptance_records"])
        self.assertEqual(second_page["archives"][0]["path"], repo_relative_path(first, root))
        self.assertIsNone(second_page["next_offset"])
        self.assertFalse(second_page["has_more"])

    def test_manual_acceptance_packet_archive_status_cli_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = paginate_acceptance_packet_plan(acceptance_plan(root))
            write_acceptance_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(["--root", str(root), "packet-archive-status", "--json"])
            payload = json.loads(output.getvalue())

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_limit = acceptance_main(["--root", str(root), "packet-archive-status", "--limit", "0"])
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_offset = acceptance_main(["--root", str(root), "packet-archive-status", "--offset", "-1"])
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_dir = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet-archive-status",
                        "--archive-dir",
                        str(Path(tmp).parent / "outside"),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["total_count"], 1)
        self.assertEqual(payload["archives"][0]["generated_at"], "2026-06-22T12:00:00Z")
        self.assertEqual(bad_limit, 1)
        self.assertEqual(bad_offset, 1)
        self.assertEqual(bad_dir, 1)

    def test_manual_acceptance_packet_archive_retention_plan_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = paginate_acceptance_packet_plan(acceptance_plan(root))
            oldest = write_acceptance_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc),
            )
            middle = write_acceptance_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            newest = write_acceptance_packet_archive(
                root,
                plan,
                now=datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc),
            )

            retention = acceptance_packet_archive_retention_plan(root, keep=1, limit=1)
            second_page = acceptance_packet_archive_retention_plan(root, keep=1, limit=1, offset=1)
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = acceptance_main(["--root", str(root), "packet-archive-retention-plan", "--keep", "1", "--json"])
            cli_payload = json.loads(output.getvalue())
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_keep = acceptance_main(["--root", str(root), "packet-archive-retention-plan", "--keep", "0"])
            newest_exists = newest.exists()
            middle_exists = middle.exists()
            oldest_exists = oldest.exists()

        self.assertEqual(retention["archive_root"], "reports/manual-acceptance-packets")
        self.assertEqual(retention["total_count"], 3)
        self.assertEqual(retention["keep"], 1)
        self.assertEqual(retention["retained_count"], 1)
        self.assertEqual(retention["prunable_count"], 2)
        self.assertEqual(retention["returned_count"], 1)
        self.assertEqual(retention["next_offset"], 1)
        self.assertTrue(retention["has_more"])
        self.assertEqual(retention["prune_candidates"][0]["path"], repo_relative_path(middle, root))
        self.assertEqual(second_page["prune_candidates"][0]["path"], repo_relative_path(oldest, root))
        self.assertFalse(retention["writes_files"])
        self.assertFalse(retention["deletes_files"])
        self.assertFalse(retention["records_evidence"])
        self.assertFalse(retention["writes_acceptance_records"])
        self.assertTrue(newest_exists)
        self.assertTrue(middle_exists)
        self.assertTrue(oldest_exists)
        self.assertEqual(exit_code, 0)
        self.assertEqual(cli_payload["prunable_count"], 2)
        self.assertEqual(bad_keep, 1)

    def test_manual_acceptance_packet_archive_retention_keeps_newest_same_second_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = paginate_acceptance_packet_plan(acceptance_plan(root))
            now = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)
            first = write_acceptance_packet_archive(root, plan, now=now)
            second = write_acceptance_packet_archive(root, plan, now=now)
            third = write_acceptance_packet_archive(root, plan, now=now)

            status = acceptance_packet_archive_status(root, limit=3)
            retention = acceptance_packet_archive_retention_plan(root, keep=1, limit=2)

        self.assertEqual(status["archives"][0]["path"], repo_relative_path(third, root))
        self.assertEqual(status["archives"][1]["path"], repo_relative_path(second, root))
        self.assertEqual(status["archives"][2]["path"], repo_relative_path(first, root))
        self.assertEqual(retention["retained_count"], 1)
        self.assertEqual(retention["prune_candidates"][0]["path"], repo_relative_path(second, root))
        self.assertEqual(retention["prune_candidates"][1]["path"], repo_relative_path(first, root))

    def test_manual_acceptance_packet_paginates_incomplete_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_acceptance(
                root,
                "mcp-client-installed",
                "passed",
                "Unit Test",
                "Generated config was used with a real MCP client.",
            )
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--limit",
                        "3",
                        "--offset",
                        "3",
                        "--write-report",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["report_path"]).read_text(encoding="utf-8")
            mcp_payload = call_tool("memory.acceptance_packet", {"limit": 3, "offset": 3}, root)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                bad_offset = acceptance_main(["--root", str(root), "packet", "--offset", "-1"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["remaining_count"], len(ACCEPTANCE_ITEMS) - 1)
        self.assertEqual(payload["returned_count"], 3)
        self.assertEqual(payload["offset"], 3)
        self.assertEqual(payload["next_offset"], 6)
        self.assertTrue(payload["has_more"])
        self.assertEqual(len(payload["items"]), 3)
        self.assertIn("returned_count: `3`", report_text)
        self.assertIn("next_offset: `6`", report_text)
        self.assertEqual(mcp_payload["returned_count"], 3)
        self.assertEqual(mcp_payload["offset"], 3)
        self.assertEqual(mcp_payload["next_offset"], 6)
        self.assertTrue(mcp_payload["has_more"])
        self.assertFalse(mcp_payload["writes_files"])
        self.assertEqual(len(mcp_payload["items"]), 3)
        self.assertEqual(bad_offset, 1)

    def test_manual_acceptance_packet_includes_reviewer_and_pr_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/211"
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--reviewer",
                        "Unit Reviewer",
                        "--pr-url",
                        pr_url,
                        "--write-report",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["report_path"]).read_text(encoding="utf-8")
            mcp_payload = call_tool(
                "memory.acceptance_packet",
                {"reviewer": "Unit Reviewer", "pr_url": pr_url},
                root,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["reviewer"], "Unit Reviewer")
        self.assertEqual(payload["pr_url"], pr_url)
        self.assertIn("reviewer: `Unit Reviewer`", report_text)
        self.assertIn(f"pr_url: `{pr_url}`", report_text)
        self.assertEqual(mcp_payload["reviewer"], "Unit Reviewer")
        self.assertEqual(mcp_payload["pr_url"], pr_url)
        self.assertIn("reviewer: `Unit Reviewer`", mcp_payload["markdown"])

    def test_manual_acceptance_packet_metadata_escapes_inline_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviewer = "Reviewer `quoted`\n- injected"
            pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/212 ``x``\n- fake"
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--reviewer",
                        reviewer,
                        "--pr-url",
                        pr_url,
                        "--write-report",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            report_text = (root / payload["report_path"]).read_text(encoding="utf-8")
            mcp_payload = call_tool("memory.acceptance_packet", {"reviewer": reviewer, "pr_url": pr_url}, root)

        self.assertEqual(exit_code, 0)
        for packet in (report_text, mcp_payload["markdown"]):
            self.assertIn("reviewer: ``Reviewer `quoted` - injected``", packet)
            self.assertIn("pr_url: ```https://github.com/GonzaloTorreras/ai-dememory/pull/212 ``x`` - fake```", packet)
            self.assertNotIn("\n- injected", packet)
            self.assertNotIn("\n- fake", packet)

    def test_manual_acceptance_packet_metadata_is_secret_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_like_reviewer = "sk-" + "proj-" + ("a" * 26)
            plan = annotate_acceptance_packet_plan(
                paginate_acceptance_packet_plan(acceptance_plan(root)),
                reviewer=secret_like_reviewer,
            )
            report = root / DEFAULT_ACCEPTANCE_PACKET_REPORT

            with self.assertRaisesRegex(ValueError, "acceptance packet report rejected by secret scan"):
                write_acceptance_packet_report(root, plan)

        self.assertFalse(report.exists())

    def test_manual_acceptance_plan_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "manual-acceptance-plan.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "plan",
                        "--write-report",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_manual_acceptance_plan_report_rejects_inside_root_non_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            canonical_path = root / "memories" / "tools" / "manual-acceptance-plan.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "plan",
                        "--write-report",
                        "--report-path",
                        str(canonical_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay under reports/", error.getvalue())
        self.assertFalse(canonical_path.exists())

    def test_manual_acceptance_plan_report_rejects_symlinked_reports_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside_reports = root / "active"
            outside_reports.mkdir()
            reports = root / "reports"
            try:
                os.symlink(outside_reports, reports, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = acceptance_main(["--root", str(root), "plan", "--write-report"])
            redirected_files = list(outside_reports.glob("*.md"))

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must not contain symlinks", error.getvalue())
        self.assertEqual(redirected_files, [])

    def test_manual_acceptance_packet_report_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "manual-acceptance-packet.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--write-report",
                        "--report-path",
                        str(outside),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay inside the memory root", error.getvalue())
        self.assertFalse(outside.exists())

    def test_manual_acceptance_packet_report_rejects_inside_root_non_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            canonical_path = root / "memories" / "tools" / "manual-acceptance-packet.md"
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(root),
                        "packet",
                        "--write-report",
                        "--report-path",
                        str(canonical_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must stay under reports/", error.getvalue())
        self.assertFalse(canonical_path.exists())

    def test_manual_acceptance_packet_report_rejects_symlinked_reports_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside_reports = root / "active"
            outside_reports.mkdir()
            reports = root / "reports"
            try:
                os.symlink(outside_reports, reports, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            error = io.StringIO()

            with patch("sys.stderr", error):
                exit_code = acceptance_main(["--root", str(root), "packet", "--write-report"])
            redirected_files = list(outside_reports.glob("*.md"))

        self.assertEqual(exit_code, 1)
        self.assertIn("report path must not contain symlinks", error.getvalue())
        self.assertEqual(redirected_files, [])

    def test_acceptance_template_guides_review_without_recording_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = acceptance_template("mcp-client-installed")
            inbox_exists = (root / "inbox" / "release-acceptance").exists()

        self.assertEqual(template.item, "mcp-client-installed")
        self.assertFalse(template.mutates_system)
        self.assertFalse(template.writes_files)
        self.assertFalse(template.records_evidence)
        self.assertIn("ai-dememory acceptance record", template.command)
        self.assertIn("Suggested Artifacts", template.markdown)
        self.assertFalse(inbox_exists)

    def test_acceptance_template_cli_outputs_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/244"

            with patch("sys.stdout", output):
                exit_code = acceptance_main(
                    [
                        "--root",
                        str(tmp),
                        "template",
                        "--item",
                        "mcp-client-installed",
                        "--reviewer",
                        "Unit Reviewer",
                        "--pr-url",
                        pr_url,
                        "--json",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["item"], "mcp-client-installed")
        self.assertEqual(payload["reviewer"], "Unit Reviewer")
        self.assertEqual(payload["pr_url"], pr_url)
        self.assertFalse(payload["records_evidence"])
        self.assertIn("--reviewed-by 'Unit Reviewer'", payload["command"])
        self.assertIn(f"--artifact '{pr_url}'", payload["command"])

    def test_manual_acceptance_verify_cli_returns_nonzero_when_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incomplete_output = io.StringIO()

            with patch("sys.stdout", incomplete_output):
                incomplete_exit = acceptance_main(["--root", str(root), "verify", "--json"])

            for item_id in ACCEPTANCE_ITEMS:
                record_acceptance(root, item_id, "passed", "Unit Test", f"Reviewed {item_id} acceptance.")

            complete_output = io.StringIO()
            with patch("sys.stdout", complete_output):
                complete_exit = acceptance_main(["--root", str(root), "verify", "--json"])

        incomplete_payload = json.loads(incomplete_output.getvalue())
        complete_payload = json.loads(complete_output.getvalue())
        self.assertEqual(incomplete_exit, 1)
        self.assertEqual(complete_exit, 0)
        self.assertFalse(incomplete_payload["complete"])
        self.assertTrue(complete_payload["complete"])

    def test_manual_acceptance_rejects_secret_like_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("h" * 40)

            with self.assertRaisesRegex(ValueError, "secret scan"):
                record_acceptance(
                    root,
                    "mcp-client-installed",
                    "passed",
                    "Unit Test",
                    f"Do not store {secret}",
                )

            self.assertFalse((root / "inbox" / "release-acceptance").exists())

    def test_release_evidence_cli_uses_pr_url_environment(self) -> None:
        output = io.StringIO()
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/250"

        with patch("sys.stdout", output), patch.dict(os.environ, {"AI_DEMEMORY_PR_URL": pr_url}):
            exit_code = release_evidence_main(["--root", str(ROOT), "--json"])
        payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["pr_url"], pr_url)

    def test_release_evidence_strict_returns_nonzero_until_ready(self) -> None:
        output = io.StringIO()
        pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/250"

        with patch("sys.stdout", output), patch.dict(os.environ, {"AI_DEMEMORY_PR_URL": pr_url}):
            exit_code = release_evidence_main(["--root", str(ROOT), "--json", "--strict"])
        payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["release_ready"])
        self.assertIn("recall_fixture_freshness", payload)
        self.assertIn("recall_fixture_review_plan", payload)
        self.assertTrue(payload["manual_acceptance_remaining"])

    def test_hook_event_captures_metadata_without_raw_payload_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = '{"prompt":"Remember this private draft."}'

            path = capture_hook_event(root, "UserPromptSubmit", payload)
            duplicate = capture_hook_event(root, "UserPromptSubmit", payload)
            text = path.read_text(encoding="utf-8") if path else ""
            files = list((root / "inbox" / "session-events").glob("*.md"))

        self.assertIsNotNone(path)
        self.assertEqual(duplicate, path)
        self.assertEqual(len(files), 1)
        self.assertIn("inbox/session-events", path.as_posix())
        self.assertIn("Payload fingerprint", text)
        self.assertIn("fingerprint_mode: \"canonical-json\"", text)
        self.assertIn("fingerprint:", text)
        self.assertNotIn("private draft", text)

    def test_hook_event_capture_rejects_symlinked_inbox_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside-session-events"
            outside.mkdir()
            inbox = root / "inbox"
            inbox.mkdir(parents=True)
            try:
                os.symlink(outside, inbox / "session-events", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(HookEventError, "inbox path must not contain symlinks"):
                capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Do not escape vault."}')

            self.assertEqual(list(outside.glob("*.md")), [])

    def test_hook_event_canonicalizes_json_payload_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_payload = '{"prompt":"Remember this note.","metadata":{"b":2,"a":1}}'
            second_payload = '{\n  "metadata": {"a": 1, "b": 2},\n  "prompt": "Remember this note."\n}'

            first = capture_hook_event(root, "UserPromptSubmit", first_payload)
            second = capture_hook_event(root, "UserPromptSubmit", second_payload)
            files = list((root / "inbox" / "session-events").glob("*.md"))
            text = first.read_text(encoding="utf-8") if first else ""

        self.assertEqual(second, first)
        self.assertEqual(len(files), 1)
        self.assertIn("Fingerprint mode: `canonical-json`", text)

    def test_hook_event_supports_claude_and_rejects_secret_raw_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = capture_hook_event(root, "SessionStart", '{"source":"startup"}', provider="claude")
            secret = "sk-" + "proj-" + ("h" * 40)
            rejected = capture_hook_event(
                root,
                "UserPromptSubmit",
                f'{{"prompt":"{secret}"}}',
                capture_raw=True,
                provider="claude",
            )
            text = path.read_text(encoding="utf-8") if path else ""

        self.assertIsNotNone(path)
        self.assertIsNone(rejected)
        self.assertIn("source:\n  kind: claude", text)
        self.assertIn("Claude hook event SessionStart", text)
        self.assertNotIn("startup", text)

    def test_hook_capture_summary_counts_frontmatter_without_payload_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Remember hook status."}')
            second = capture_hook_event(root, "SessionStart", '{"source":"startup"}', provider="claude")
            if first is not None:
                first_text = first.read_text(encoding="utf-8")
                first.write_text(
                    "\n".join(
                        "created_at: 2026-06-19"
                        if line.startswith("created_at: ")
                        else "review_after: 2026-06-20"
                        if line.startswith("review_after: ")
                        else line
                        for line in first_text.splitlines()
                    )
                    + "\n",
                    encoding="utf-8",
                )
            if second is not None:
                second_text = second.read_text(encoding="utf-8")
                second.write_text(
                    "\n".join(
                        "created_at: 2026-06-21"
                        if line.startswith("created_at: ")
                        else "review_after: not-a-date"
                        if line.startswith("review_after: ")
                        else line
                        for line in second_text.splitlines()
                    )
                    + "\n",
                    encoding="utf-8",
                )
            missing_review = capture_hook_event(root, "Stop", '{"source":"stop"}', provider="codex")
            if missing_review is not None:
                missing_text = missing_review.read_text(encoding="utf-8")
                missing_review.write_text(
                    "\n".join(
                        "created_at: 2026-06-22" if line.startswith("created_at: ") else line
                        for line in missing_text.splitlines()
                        if not line.startswith("review_after: ")
                    )
                    + "\n",
                    encoding="utf-8",
                )
            malformed = root / "inbox" / "session-events" / "broken.md"
            malformed.write_text("---\nid: broken\n", encoding="utf-8")

            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                summary = hook_capture_summary(root)
                status = hook_status_summary(root)
                filtered_claude = hook_capture_summary(
                    root,
                    provider="claude",
                    event="SessionStart",
                    review_status="pending",
                )
                filtered_codex_stop = hook_status_summary(root, capture_provider="codex", capture_event="Stop")
                filtered_created = hook_capture_summary(root, created_from="2026-06-20", created_to="2026-06-22")
                filtered_review_after = hook_capture_summary(
                    root,
                    review_after_from="2026-06-20",
                    review_after_to="2026-06-20",
                )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertIsNotNone(missing_review)
        self.assertEqual(summary["total_count"], 3)
        self.assertEqual(summary["unfiltered_total_count"], 3)
        self.assertEqual(summary["filters"], {})
        self.assertEqual(summary["malformed_count"], 1)
        self.assertEqual(summary["by_provider"], {"claude": 1, "codex": 2})
        self.assertEqual(summary["by_event"], {"SessionStart": 1, "Stop": 1, "UserPromptSubmit": 1})
        self.assertEqual(summary["pending_count"], 3)
        self.assertEqual(summary["resolved_count"], 0)
        self.assertEqual(summary["review_status_counts"], {"pending": 3})
        self.assertEqual(summary["review_due_count"], 2)
        self.assertEqual(summary["review_after_status_counts"], {"due": 1, "invalid": 1, "missing": 1})
        self.assertEqual(len(summary["review_due_paths"]), 2)
        self.assertFalse(summary["reads_raw_payloads"])
        self.assertFalse(summary["writes_files"])
        self.assertEqual(len(summary["latest"]), 3)
        self.assertIn("inbox/session-events", summary["latest"][0]["path"])
        self.assertIn(summary["latest"][0]["review_after_status"], {"due", "invalid", "missing"})
        self.assertIn("broken.md", summary["malformed"][0]["path"])
        self.assertNotIn(str(root), summary["malformed"][0]["error"])
        self.assertEqual(status["captures"]["total_count"], 3)
        self.assertEqual(status["captures"]["review_due_count"], 2)
        self.assertEqual(filtered_claude["filters"], {"event": "SessionStart", "provider": "claude", "review_status": "pending"})
        self.assertEqual(filtered_claude["unfiltered_total_count"], 3)
        self.assertEqual(filtered_claude["total_count"], 1)
        self.assertEqual(filtered_claude["by_provider"], {"claude": 1})
        self.assertEqual(filtered_claude["by_event"], {"SessionStart": 1})
        self.assertEqual(filtered_codex_stop["captures"]["filters"], {"event": "Stop", "provider": "codex"})
        self.assertEqual(filtered_codex_stop["captures"]["total_count"], 1)
        self.assertEqual(filtered_created["filters"], {"created_from": "2026-06-20", "created_to": "2026-06-22"})
        self.assertEqual(filtered_created["total_count"], 2)
        self.assertEqual(filtered_review_after["filters"], {"review_after_from": "2026-06-20", "review_after_to": "2026-06-20"})
        self.assertEqual(filtered_review_after["total_count"], 1)

    def test_hook_capture_summary_stops_malformed_frontmatter_before_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "inbox" / "session-events"
            inbox.mkdir(parents=True)
            malformed = inbox / "broken.md"
            malformed.write_bytes(
                b"---\nid: broken\nsource:\n  ref: \"hook:codex:Stop\"\n# Raw Payload\n"
                + b"OPENAI_API_KEY=sk-proj-" + (b"x" * 40) + b"\xff\xfe\n"
            )

            summary = hook_capture_summary(root)

        rendered = json.dumps(summary)
        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(summary["malformed_count"], 1)
        self.assertEqual(summary["malformed"][0]["path"], "inbox/session-events/broken.md")
        self.assertIn("missing closing frontmatter delimiter", summary["malformed"][0]["error"])
        self.assertNotIn("OPENAI_API_KEY", rendered)
        self.assertNotIn("sk-proj", rendered)

    def test_hook_capture_summary_caps_long_malformed_frontmatter_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "inbox" / "session-events"
            inbox.mkdir(parents=True)
            malformed = inbox / "long-frontmatter.md"
            hidden_marker = b"SHOULD_NOT_SURFACE"
            malformed.write_bytes(b"---\nid: broken\npayload: " + (b"x" * (70 * 1024)) + hidden_marker + b"\n")

            summary = hook_capture_summary(root)

        rendered = json.dumps(summary)
        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(summary["malformed_count"], 1)
        self.assertEqual(summary["malformed"][0]["path"], "inbox/session-events/long-frontmatter.md")
        self.assertIn("frontmatter exceeds maximum size", summary["malformed"][0]["error"])
        self.assertNotIn(hidden_marker.decode("ascii"), rendered)

    def test_hook_capture_summary_caps_long_malformed_first_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "inbox" / "session-events"
            inbox.mkdir(parents=True)
            malformed = inbox / "long-first-line.md"
            hidden_marker = b"FIRST_LINE_MARKER"
            malformed.write_bytes((b"x" * (70 * 1024)) + hidden_marker + b"\n")

            summary = hook_capture_summary(root)

        rendered = json.dumps(summary)
        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(summary["malformed_count"], 1)
        self.assertEqual(summary["malformed"][0]["path"], "inbox/session-events/long-first-line.md")
        self.assertIn("frontmatter exceeds maximum size", summary["malformed"][0]["error"])
        self.assertNotIn(hidden_marker.decode("ascii"), rendered)

    def test_hook_capture_summary_treats_indented_heading_as_body_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "inbox" / "session-events"
            inbox.mkdir(parents=True)
            malformed = inbox / "indented-heading.md"
            hidden_marker = b"INDENTED_HEADING_SECRET"
            malformed.write_bytes(b"---\nid: broken\n  # Raw Payload\n" + hidden_marker + b"\xff\xfe\n")

            summary = hook_capture_summary(root)

        rendered = json.dumps(summary)
        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(summary["malformed_count"], 1)
        self.assertEqual(summary["malformed"][0]["path"], "inbox/session-events/indented-heading.md")
        self.assertIn("missing closing frontmatter delimiter", summary["malformed"][0]["error"])
        self.assertNotIn(hidden_marker.decode("ascii"), rendered)

    def test_hook_capture_review_due_uses_local_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Review local date."}')
            if captured is not None:
                text = captured.read_text(encoding="utf-8")
                captured.write_text(
                    "\n".join(
                        "review_after: 2026-06-21" if line.startswith("review_after: ") else line
                        for line in text.splitlines()
                    )
                    + "\n",
                    encoding="utf-8",
                )

            with patch("hook_event.date") as mock_date:
                mock_date.today.return_value = date(2026, 6, 21)
                mock_date.fromisoformat.side_effect = date.fromisoformat
                summary = hook_capture_summary(root)

        self.assertIsNotNone(captured)
        self.assertEqual(summary["review_due_count"], 1)
        self.assertEqual(summary["review_after_status_counts"], {"due": 1})

    def test_hook_capture_summary_skips_symlink_capture_entries_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            captured = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Review local date."}')
            outside = Path(tmp) / "outside-capture.md"
            if captured is not None:
                outside.write_text(captured.read_text(encoding="utf-8"), encoding="utf-8")
                captured.unlink()
            try:
                os.symlink(outside, captured)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            summary = hook_capture_summary(root)

        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(summary["malformed_count"], 1)
        self.assertEqual(summary["malformed"][0]["path"], repo_relative_path(captured, root))
        self.assertEqual(summary["malformed"][0]["error"], "symlink capture entry")
        self.assertNotIn(str(outside), json.dumps(summary))

    def test_hook_capture_review_records_outcome_and_clears_due_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Review this hook capture."}')
            if captured is not None:
                text = captured.read_text(encoding="utf-8")
                captured.write_text(
                    "\n".join(
                        "review_after: 2026-06-20" if line.startswith("review_after: ") else line
                        for line in text.splitlines()
                    )
                    + "\n",
                    encoding="utf-8",
                )
            relpath = repo_relative_path(captured, root) if captured else ""

            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                before = hook_capture_summary(root)
                result = review_hook_capture(root, relpath, "dismissed", "Unit Test", "No durable memory.")
                after = hook_capture_summary(root)
                resolved = hook_capture_summary(root, review_status="resolved")
            updated = captured.read_text(encoding="utf-8") if captured else ""
            report = render_hook_capture_report(after)

        self.assertIsNotNone(captured)
        self.assertEqual(before["review_due_count"], 1)
        self.assertEqual(result.path, relpath)
        self.assertEqual(result.review_status, "dismissed")
        self.assertEqual(result.reviewed_by, "Unit Test")
        self.assertEqual(result.reviewed_at, "2026-06-21")
        self.assertFalse(result.canonical_memory_updated)
        self.assertEqual(after["pending_count"], 0)
        self.assertEqual(after["resolved_count"], 1)
        self.assertEqual(after["review_due_count"], 0)
        self.assertEqual(after["review_status_counts"], {"dismissed": 1})
        self.assertEqual(resolved["filters"], {"review_status": "resolved"})
        self.assertEqual(resolved["total_count"], 1)
        self.assertEqual(resolved["review_status_counts"], {"dismissed": 1})
        self.assertIn("reviewed: true", updated)
        self.assertIn("review_status: \"dismissed\"", updated)
        self.assertIn("reviewed_by: \"Unit Test\"", updated)
        self.assertIn("review_reason: \"No durable memory.\"", updated)
        self.assertIn("- review_status: `dismissed`", report)

    def test_hook_capture_review_rejects_symlinked_inbox_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside-session-events"
            outside.mkdir()
            capture = outside / "capture.md"
            capture.write_text(
                "\n".join(
                    [
                        "---",
                        "id: hook_escape",
                        "title: \"Hook escape\"",
                        "type: session",
                        "status: proposed",
                        "review_after: 2026-06-20",
                        "source:",
                        "  kind: codex",
                        "  ref: \"hook:codex:UserPromptSubmit\"",
                        "---",
                        "",
                        "# External hook capture",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            inbox = root / "inbox"
            inbox.mkdir(parents=True)
            try:
                os.symlink(outside, inbox / "session-events", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(HookEventError, "inbox path must not contain symlinks"):
                review_hook_capture(root, "inbox/session-events/capture.md", "dismissed", "Unit Test", "Rejected.")

            self.assertNotIn("review_status", capture.read_text(encoding="utf-8"))

    def test_hook_capture_review_rejects_symlinked_capture_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside-capture.md"
            outside.write_text(
                "\n".join(
                    [
                        "---",
                        "id: hook_leaf_escape",
                        "title: \"Hook leaf escape\"",
                        "type: session",
                        "status: proposed",
                        "review_after: 2026-06-20",
                        "source:",
                        "  kind: codex",
                        "  ref: \"hook:codex:UserPromptSubmit\"",
                        "---",
                        "",
                        "# External hook capture",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            capture = root / "inbox" / "session-events" / "capture.md"
            capture.parent.mkdir(parents=True)
            try:
                os.symlink(outside, capture)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(HookEventError, "review path must not contain symlinks"):
                review_hook_capture(root, "inbox/session-events/capture.md", "dismissed", "Unit Test", "Rejected.")

            self.assertNotIn("review_status", outside.read_text(encoding="utf-8"))

    def test_hook_capture_review_rejects_symlinked_capture_parent_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside_dir = Path(tmp) / "outside-dir"
            outside_dir.mkdir()
            outside = outside_dir / "capture.md"
            outside.write_text(
                "\n".join(
                    [
                        "---",
                        "id: hook_parent_escape",
                        "title: \"Hook parent escape\"",
                        "type: session",
                        "status: proposed",
                        "review_after: 2026-06-20",
                        "source:",
                        "  kind: codex",
                        "  ref: \"hook:codex:UserPromptSubmit\"",
                        "---",
                        "",
                        "# External hook capture",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            link = root / "inbox" / "session-events" / "link"
            link.parent.mkdir(parents=True)
            try:
                os.symlink(outside_dir, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(HookEventError, "review path must not contain symlinks"):
                review_hook_capture(root, "inbox/session-events/link/capture.md", "dismissed", "Unit Test", "Rejected.")

            self.assertNotIn("review_status", outside.read_text(encoding="utf-8"))

    def test_hook_capture_review_preserves_non_utf8_payload_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Review metadata only."}')
            non_utf8_body = b"\n## Raw Payload\n\n\xff\xfe\xfd opaque payload bytes\n"
            if captured is not None:
                with captured.open("ab") as handle:
                    handle.write(non_utf8_body)
            relpath = repo_relative_path(captured, root) if captured else ""

            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                result = review_hook_capture(root, relpath, "reviewed", "Unit Test", "Metadata reviewed.")
            raw = captured.read_bytes() if captured else b""
            frontmatter = read_hook_frontmatter(captured) if captured else {}

        self.assertIsNotNone(captured)
        self.assertEqual(result.review_status, "reviewed")
        self.assertEqual(frontmatter["review_status"], "reviewed")
        self.assertEqual(frontmatter["reviewed_by"], "Unit Test")
        self.assertTrue(raw.endswith(non_utf8_body))

    def test_hook_capture_review_cli_json_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = capture_hook_event(root, "Stop", '{"source":"stop"}')
            secret_candidate = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"secret guard"}')
            relpath = repo_relative_path(captured, root) if captured else ""
            secret_relpath = repo_relative_path(secret_candidate, root) if secret_candidate else ""
            output = io.StringIO()
            blocked_value = "sk-" + "proj-" + ("h" * 40)
            blocked_error = io.StringIO()
            outside = root / "outside.md"
            outside.write_text("---\nid: outside\n---\n", encoding="utf-8")
            outside_error = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = hook_event_main(
                    [
                        "review",
                        "--root",
                        str(root),
                        "--path",
                        relpath,
                        "--status",
                        "reviewed",
                        "--reviewed-by",
                        "Unit Test",
                        "--reason",
                        "Captured review metadata only.",
                        "--json",
                    ]
                )
            with redirect_stderr(blocked_error):
                blocked_review_exit = hook_event_main(
                    [
                        "review",
                        "--root",
                        str(root),
                        "--path",
                        secret_relpath,
                        "--status",
                        "rejected",
                        "--reviewed-by",
                        "Unit Test",
                        "--reason",
                        f"Secret-like {blocked_value}",
                    ]
                )
            with redirect_stderr(outside_error):
                outside_exit = hook_event_main(
                    [
                        "review",
                        "--root",
                        str(root),
                        "--path",
                        str(outside),
                        "--status",
                        "reviewed",
                        "--reviewed-by",
                        "Unit Test",
                        "--reason",
                        "Outside path.",
                    ]
                )
            payload = json.loads(output.getvalue())

        self.assertIsNotNone(captured)
        self.assertIsNotNone(secret_candidate)
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["path"], relpath)
        self.assertEqual(payload["review_status"], "reviewed")
        self.assertFalse(payload["canonical_memory_updated"])
        self.assertEqual(blocked_review_exit, 1)
        self.assertIn("secret scan", blocked_error.getvalue())
        self.assertEqual(outside_exit, 1)
        self.assertIn("must stay under inbox/session-events", outside_error.getvalue())

    def test_hook_capture_archive_previews_and_moves_reviewed_captures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Archive reviewed capture."}')
            pending = capture_hook_event(root, "Stop", '{"source":"pending"}')
            relpath = repo_relative_path(resolved, root) if resolved else ""
            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                review_hook_capture(root, relpath, "dismissed", "Unit Test", "No durable memory.")
                preview = archive_reviewed_hook_captures(root)
                source_exists_after_preview = resolved.exists() if resolved else False
                gated = archive_reviewed_hook_captures(root, min_reviewed_days=1)
                applied = archive_reviewed_hook_captures(root, apply=True)
                after = hook_capture_summary(root)
                archive_exists = (root / applied.archived[0]["archive_path"]).exists() if applied.archived else False

        self.assertIsNotNone(resolved)
        self.assertIsNotNone(pending)
        self.assertTrue(source_exists_after_preview)
        self.assertTrue(preview.dry_run)
        self.assertEqual(preview.eligible_count, 1)
        self.assertEqual(preview.archived_count, 0)
        self.assertFalse(preview.writes_files)
        self.assertFalse(preview.canonical_memory_updated)
        self.assertEqual(preview.candidates[0]["path"], relpath)
        self.assertEqual(gated.eligible_count, 0)
        self.assertEqual(gated.skipped[0]["reason"], "reviewed_too_recent")
        self.assertFalse(applied.dry_run)
        self.assertEqual(applied.archived_count, 1)
        self.assertTrue(applied.writes_files)
        self.assertFalse(resolved.exists())
        self.assertTrue(archive_exists)
        self.assertEqual(after["total_count"], 1)
        self.assertEqual(after["latest"][0]["path"], repo_relative_path(pending, root))

    def test_hook_capture_archive_cli_json_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = capture_hook_event(root, "SessionStart", '{"source":"archive"}', provider="claude")
            relpath = repo_relative_path(captured, root) if captured else ""
            preview_output = io.StringIO()
            apply_output = io.StringIO()
            outside_error = io.StringIO()

            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                review_hook_capture(root, relpath, "reviewed", "Unit Test", "Reviewed metadata.")
                with redirect_stdout(preview_output):
                    preview_exit = hook_event_main(
                        [
                            "archive",
                            "--root",
                            str(root),
                            "--provider",
                            "claude",
                            "--review-status",
                            "reviewed",
                            "--json",
                        ]
                    )
                with redirect_stdout(apply_output):
                    apply_exit = hook_event_main(
                        [
                            "archive",
                            "--root",
                            str(root),
                            "--provider",
                            "claude",
                            "--apply",
                            "--json",
                        ]
                    )
                with redirect_stderr(outside_error):
                    outside_exit = hook_event_main(
                        [
                            "archive",
                            "--root",
                            str(root),
                            "--archive-root",
                            "reports/session-events",
                            "--json",
                        ]
                    )
            preview = json.loads(preview_output.getvalue())
            applied = json.loads(apply_output.getvalue())

        self.assertIsNotNone(captured)
        self.assertEqual(preview_exit, 0)
        self.assertEqual(preview["filters"], {"provider": "claude", "review_status": "reviewed"})
        self.assertEqual(preview["eligible_count"], 1)
        self.assertFalse(preview["writes_files"])
        self.assertFalse(preview["canonical_memory_updated"])
        self.assertEqual(apply_exit, 0)
        self.assertEqual(applied["archived_count"], 1)
        self.assertTrue(applied["archived"][0]["archive_path"].startswith("archive/session-events/"))
        self.assertEqual(outside_exit, 1)
        self.assertIn("archive/session-events", outside_error.getvalue())

    def test_hook_capture_archive_rejects_symlink_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            resolved = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Archive reviewed capture."}')
            relpath = repo_relative_path(resolved, root) if resolved else ""
            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                review_hook_capture(root, relpath, "dismissed", "Unit Test", "No durable memory.")
            archive_parent = root / "archive"
            archive_parent.mkdir(parents=True, exist_ok=True)
            archive_root = archive_parent / "session-events"
            outside_archive = Path(tmp) / "outside-archive"
            outside_archive.mkdir()
            try:
                os.symlink(outside_archive, archive_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(HookEventError, "archive path must not contain symlinks"):
                archive_reviewed_hook_captures(root, apply=True)
            outside_files = list(outside_archive.glob("*.md"))
            captured_still_exists = resolved.exists() if resolved else False

        self.assertIsNotNone(resolved)
        self.assertTrue(captured_still_exists)
        self.assertEqual(outside_files, [])

    def test_hook_capture_archive_rejects_symlink_inbox_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            resolved = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Archive reviewed capture."}')
            relpath = repo_relative_path(resolved, root) if resolved else ""
            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                review_hook_capture(root, relpath, "dismissed", "Unit Test", "No durable memory.")
            inbox_root = root / "inbox" / "session-events"
            outside_inbox = Path(tmp) / "outside-inbox"
            outside_inbox.mkdir()
            for path in inbox_root.glob("*"):
                path.unlink()
            inbox_root.rmdir()
            try:
                os.symlink(outside_inbox, inbox_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(HookEventError, "inbox path must not contain symlinks"):
                archive_reviewed_hook_captures(root, apply=True)
            outside_files = list(outside_inbox.glob("*.md"))

        self.assertIsNotNone(resolved)
        self.assertEqual(outside_files, [])

    def test_hook_capture_archive_skips_symlink_capture_entries_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            captured = capture_hook_event(root, "UserPromptSubmit", '{"prompt":"Archive reviewed capture."}')
            relpath = repo_relative_path(captured, root) if captured else ""
            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                review_hook_capture(root, relpath, "dismissed", "Unit Test", "No durable memory.")
            outside = Path(tmp) / "outside.md"
            if captured is not None:
                outside.write_text(captured.read_text(encoding="utf-8"), encoding="utf-8")
                captured.unlink()
            try:
                os.symlink(outside, captured)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            result = archive_reviewed_hook_captures(root, apply=True)
            outside_exists = outside.exists()

        self.assertEqual(result.archived_count, 0)
        self.assertEqual(result.skipped[0]["reason"], "symlink_capture_entry")
        self.assertTrue(outside_exists)

    def test_hook_capture_report_writes_frontmatter_only_review_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = capture_hook_event(
                root,
                "UserPromptSubmit",
                '{"prompt":"private draft hook payload"}',
                capture_raw=True,
            )
            if captured is not None:
                text = captured.read_text(encoding="utf-8")
                captured.write_text(
                    "\n".join(
                        "review_after: 2026-06-20" if line.startswith("review_after: ") else line
                        for line in text.splitlines()
                    )
                    + "\n",
                    encoding="utf-8",
                )

            with patch("hook_event.today", return_value=date(2026, 6, 21)):
                path, summary = write_hook_capture_report(root, limit=10)
            report = path.read_text(encoding="utf-8")
            rendered = render_hook_capture_report(summary)
            captured_text = captured.read_text(encoding="utf-8") if captured else ""

        self.assertIsNotNone(captured)
        self.assertEqual(repo_relative_path(path, root), "reports/hook-captures.md")
        self.assertEqual(summary["review_due_count"], 1)
        self.assertIn("# Hook Capture Review", report)
        self.assertIn("- reads_raw_payloads: `false`", report)
        self.assertIn("- writes_files: `false`", report)
        self.assertIn("inbox/session-events", report)
        self.assertIn("review_due: `true`", report)
        self.assertIn("private draft hook payload", captured_text)
        self.assertNotIn("private draft hook payload", report)
        self.assertNotIn("private draft hook payload", rendered)

    def test_hook_capture_report_rejects_paths_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "outside.md"
            error_output = io.StringIO()
            in_root = root / "README.md"
            in_root_error = io.StringIO()

            with redirect_stderr(error_output):
                exit_code = hook_event_main(
                    [
                        "captures",
                        "--root",
                        str(root),
                        "--write-report",
                        "--report-path",
                        str(outside),
                    ]
                )
            with redirect_stderr(in_root_error):
                in_root_exit = hook_event_main(
                    [
                        "captures",
                        "--root",
                        str(root),
                        "--write-report",
                        "--report-path",
                        str(in_root),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("must stay inside the memory root", error_output.getvalue())
        self.assertFalse(outside.exists())
        self.assertEqual(in_root_exit, 1)
        self.assertIn("must stay under reports", in_root_error.getvalue())
        self.assertFalse(in_root.exists())

    def test_hook_capture_report_rejects_symlinked_reports_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside_reports = Path(tmp) / "outside-reports"
            outside_reports.mkdir()
            try:
                os.symlink(outside_reports, root / "reports", target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(HookEventError, "report path must not contain symlinks"):
                write_hook_capture_report(root)

        self.assertEqual(list(outside_reports.glob("*")), [])

    def test_hook_capture_cli_reports_json_summary_and_written_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_capture = capture_hook_event(root, "Stop", '{"source":"stop"}')
            claude_capture = capture_hook_event(root, "SessionStart", '{"source":"startup"}', provider="claude")
            for path, created_at in ((codex_capture, "2026-06-21"), (claude_capture, "2026-06-19")):
                if path is not None:
                    text = path.read_text(encoding="utf-8")
                    path.write_text(
                        "\n".join(
                            f"created_at: {created_at}" if line.startswith("created_at: ") else line
                            for line in text.splitlines()
                        )
                        + "\n",
                        encoding="utf-8",
                    )
            summary_output = io.StringIO()
            report_output = io.StringIO()

            with redirect_stdout(summary_output):
                summary_exit = hook_event_main(
                    [
                        "captures",
                        "--root",
                        str(root),
                        "--provider",
                        "codex",
                        "--event",
                        "Stop",
                        "--review-status",
                        "pending",
                        "--created-from",
                        "2026-06-20",
                        "--created-to",
                        "2026-06-21",
                        "--json",
                    ]
                )
            with redirect_stdout(report_output):
                report_exit = hook_event_main(
                    [
                        "captures",
                        "--root",
                        str(root),
                        "--provider",
                        "claude",
                        "--write-report",
                        "--json",
                    ]
                )

            summary = json.loads(summary_output.getvalue())
            report = json.loads(report_output.getvalue())

        self.assertEqual(summary_exit, 0)
        self.assertEqual(report_exit, 0)
        self.assertEqual(summary["total_count"], 1)
        self.assertEqual(summary["unfiltered_total_count"], 2)
        self.assertEqual(
            summary["filters"],
            {
                "created_from": "2026-06-20",
                "created_to": "2026-06-21",
                "event": "Stop",
                "provider": "codex",
                "review_status": "pending",
            },
        )
        self.assertEqual(report["report_path"], "reports/hook-captures.md")
        self.assertEqual(report["summary"]["total_count"], 1)
        self.assertEqual(report["summary"]["filters"], {"provider": "claude"})

    def test_hook_config_generates_provider_specific_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude = hook_config("claude", root=root)
            codex = hook_config("codex", root=root)
            events = hook_events("claude")

        claude_command = claude["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        codex_command = codex["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        self.assertIn("SessionStart", events["claude"])
        self.assertIn("--provider claude", claude_command)
        self.assertIn(str(root), claude_command)
        self.assertIn("commandWindows", codex["hooks"]["UserPromptSubmit"][0]["hooks"][0])
        self.assertIn("--provider codex", codex_command)

    def test_hook_instruction_install_is_idempotent_and_removable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "AGENTS.md"
            agents.write_text("# Existing Instructions\n\nKeep this line.\n", encoding="utf-8")

            first = install_hook_instructions(root, ["codex"])
            first_text = agents.read_text(encoding="utf-8")
            second = install_hook_instructions(root, ["codex"])
            second_text = agents.read_text(encoding="utf-8")
            status = hook_status(root, ["codex"])
            summary = hook_status_summary(root, ["codex"])
            removed = uninstall_hook_instructions(root, ["codex"])
            removed_text = agents.read_text(encoding="utf-8")

        self.assertTrue(first[0].changed)
        self.assertFalse(second[0].changed)
        self.assertEqual(first_text, second_text)
        self.assertTrue(status[0].installed)
        self.assertFalse(summary["writes_files"])
        self.assertEqual(summary["installed_count"], 1)
        self.assertTrue(summary["all_installed"])
        self.assertEqual(summary["hooks"][0]["client"], "codex")
        self.assertEqual(summary["captures"]["total_count"], 0)
        self.assertTrue(removed[0].changed)
        self.assertIn("Keep this line.", removed_text)
        self.assertNotIn("BEGIN AI-DEMEMORY HOOKS:codex", removed_text)

    def test_hook_instruction_install_creates_claude_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            results = install_hook_instructions(root, ["claude"])
            claude_text = (root / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertTrue(results[0].changed)
        self.assertIn("BEGIN AI-DEMEMORY HOOKS:claude", claude_text)
        self.assertIn("ai-dememory hooks config --client claude", claude_text)

    def test_hook_instruction_install_rejects_symlinked_instruction_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside-agents.md"
            root.mkdir()
            outside.write_text("# Outside\n", encoding="utf-8")
            try:
                os.symlink(outside, root / "AGENTS.md")
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                install_hook_instructions(root, ["codex"])

            self.assertEqual(outside.read_text(encoding="utf-8"), "# Outside\n")

    def test_hook_instruction_uninstall_rejects_symlinked_instruction_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside-agents.md"
            root.mkdir()
            outside.write_text("# Outside\n", encoding="utf-8")
            try:
                os.symlink(outside, root / "AGENTS.md")
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                uninstall_hook_instructions(root, ["codex"])

            self.assertEqual(outside.read_text(encoding="utf-8"), "# Outside\n")

    def test_mcp_exposes_maintenance_import_schedule_and_capture_tools(self) -> None:
        tool_names = {tool["name"] for tool in TOOLS}

        self.assertIn("memory.capture_miss", tool_names)
        self.assertIn("memory.recall_miss_candidate", tool_names)
        self.assertIn("memory.doctor", tool_names)
        self.assertIn("memory.recall_fixture_status", tool_names)
        self.assertIn("memory.recall_review_plan", tool_names)
        self.assertIn("memory.recall_review_packet", tool_names)
        self.assertIn("memory.recall_review_packet_archive_status", tool_names)
        self.assertIn("memory.recall_review_packet_archive_retention_plan", tool_names)
        self.assertIn("memory.recall_miss_review", tool_names)
        self.assertIn("memory.vector_status", tool_names)
        self.assertIn("memory.roadmap_status", tool_names)
        self.assertIn("memory.validate_status", tool_names)
        self.assertIn("memory.provenance_status", tool_names)
        self.assertIn("memory.working_current", tool_names)
        self.assertIn("memory.working_status", tool_names)
        self.assertIn("memory.working_snapshot", tool_names)
        self.assertIn("memory.working_handoff", tool_names)
        self.assertIn("memory.context", tool_names)
        self.assertIn("memory.outcome", tool_names)
        self.assertIn("memory.lifecycle_scores", tool_names)
        self.assertIn("memory.sleep_plan", tool_names)
        self.assertIn("memory.sleep_apply_reviewed", tool_names)
        self.assertIn("memory.maintenance_status", tool_names)
        maintenance_status_tool = next(tool for tool in TOOLS if tool["name"] == "memory.maintenance_status")
        maintenance_status_schema = maintenance_status_tool["outputSchema"]
        maintenance_status_properties = maintenance_status_schema["properties"]
        maintenance_status_required = set(maintenance_status_schema["required"])
        self.assertIn("hook_captures", maintenance_status_properties)
        self.assertIn("artifact_freshness", maintenance_status_properties)
        self.assertIn("hook_captures", maintenance_status_required)
        self.assertIn("artifact_freshness", maintenance_status_required)
        setup_health_tool = next(tool for tool in TOOLS if tool["name"] == "memory.setup_health")
        setup_health_schema = setup_health_tool["outputSchema"]
        setup_health_properties = setup_health_schema["properties"]
        setup_health_required = set(setup_health_schema["required"])
        self.assertIn("artifact_freshness", setup_health_properties)
        self.assertIn("artifact_freshness", setup_health_required)
        self.assertIn("memory.import_chats", tool_names)
        self.assertIn("memory.capture_import", tool_names)
        self.assertIn("memory.git_lessons", tool_names)
        self.assertIn("memory.maintenance_run", tool_names)
        self.assertIn("memory.schedule_plan", tool_names)
        self.assertIn("memory.schedule_status", tool_names)
        self.assertIn("memory.schedule_environment", tool_names)
        self.assertIn("memory.acceptance_status", tool_names)
        self.assertIn("memory.acceptance_verify", tool_names)
        self.assertIn("memory.acceptance_plan", tool_names)
        self.assertIn("memory.acceptance_template", tool_names)
        self.assertIn("memory.acceptance_packet", tool_names)
        self.assertIn("memory.acceptance_packet_archive_status", tool_names)
        self.assertIn("memory.acceptance_packet_archive_retention_plan", tool_names)
        self.assertIn("memory.release_evidence", tool_names)
        self.assertIn("memory.release_evidence_report", tool_names)
        self.assertIn("memory.publish_plan", tool_names)
        self.assertIn("memory.hook_events", tool_names)
        self.assertIn("memory.hook_config", tool_names)
        self.assertIn("memory.hook_status", tool_names)
        self.assertIn("memory.hook_capture_review", tool_names)
        self.assertIn("memory.providers_detect", tool_names)
        self.assertIn("memory.providers_status", tool_names)
        self.assertIn("memory.providers_plan", tool_names)
        self.assertIn("memory.setup_plan", tool_names)
        self.assertIn("memory.setup_health", tool_names)
        self.assertIn("memory.review_false_positives", tool_names)
        self.assertIn("memory.review_stale_false_positives", tool_names)
        self.assertIn("memory.false_positive_ignore", tool_names)
        self.assertIn("memory.false_positive_unignore", tool_names)
        self.assertIn("memory.review_conflicts", tool_names)
        self.assertIn("memory.conflict_dismiss", tool_names)
        self.assertIn("memory.conflict_merge_proposal", tool_names)
        self.assertIn("memory.conflict_keep", tool_names)
        self.assertIn("memory.review_modes", tool_names)
        self.assertIn("memory.review_configure_mode", tool_names)
        self.assertIn("memory.review_plan", tool_names)
        self.assertIn("memory.review_recommendation", tool_names)
        self.assertIn("memory.review_recommendations", tool_names)
        self.assertIn("memory.review_recommendation_archive_status", tool_names)
        self.assertIn("memory.review_recommendation_archive_restore_preview", tool_names)
        self.assertIn("memory.review_recommendation_outcome_report", tool_names)
        self.assertIn("memory.review_recommendation_outcome", tool_names)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            write_memory(root, "memories/tools/codex-copy.md", memory_id="mem_codex_copy")
            write_memory(
                root,
                "memories/tools/dismiss-one.md",
                memory_id="mem_dismiss_one",
                title="Dismiss Conflict Memory",
            )
            write_memory(
                root,
                "memories/tools/dismiss-two.md",
                memory_id="mem_dismiss_two",
                title="Dismiss Conflict Memory",
            )
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            mark_seen_receipt = call_tool("memory.mark_seen", {"query": "codex", "selected_memory_id": "mem_codex_test"}, root)
            status = call_tool("memory.maintenance_status", {}, root)
            plan = call_tool("memory.schedule_plan", {"platform": "windows"}, root)
            schedule = call_tool("memory.schedule_status", {"platform": "windows"}, root)
            schedule_env = call_tool("memory.schedule_environment", {"platform": "windows"}, root)
            docker_plan = call_tool(
                "memory.schedule_plan",
                {"platform": "windows", "mode": "docker", "image": "ai-dememory:test"},
                root,
            )
            acceptance = call_tool("memory.acceptance_status", {}, root)
            verification = call_tool("memory.acceptance_verify", {}, root)
            pr_url = "https://github.com/GonzaloTorreras/ai-dememory/pull/244"
            acceptance_plan_result = call_tool(
                "memory.acceptance_plan",
                {"reviewer": "Unit Reviewer", "pr_url": pr_url},
                root,
            )
            acceptance_template_result = call_tool(
                "memory.acceptance_template",
                {"item": "mcp-client-installed", "reviewer": "Unit Reviewer", "pr_url": pr_url},
                root,
            )
            acceptance_packet_result = call_tool("memory.acceptance_packet", {}, root)
            archived_acceptance_packet = write_acceptance_packet_archive(
                root,
                paginate_acceptance_packet_plan(acceptance_plan(root)),
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            acceptance_packet_archive_status_result = call_tool(
                "memory.acceptance_packet_archive_status",
                {},
                root,
            )
            acceptance_packet_archive_retention_result = call_tool(
                "memory.acceptance_packet_archive_retention_plan",
                {},
                root,
            )
            vault_release_evidence = call_tool("memory.release_evidence", {}, root)
            vault_release_evidence_report = call_tool("memory.release_evidence_report", {}, root)
            vault_roadmap_status = call_tool("memory.roadmap_status", {}, root)
            doctor = call_tool("memory.doctor", {}, root)
            validate_status = call_tool("memory.validate_status", {}, root)
            hook_list = call_tool("memory.hook_events", {"provider": "claude"}, root)
            hook_fragment = call_tool("memory.hook_config", {"client": "claude"}, root)
            hook_capture_path = capture_hook_event(root, "SessionStart", '{"source":"unit"}', provider="claude")
            hook_capture_relpath = repo_relative_path(hook_capture_path, root) if hook_capture_path else ""
            hook_status_result = call_tool("memory.hook_status", {"client": "claude"}, root)
            hook_status_filtered = call_tool(
                "memory.hook_status",
                {
                    "client": "claude",
                    "capture_provider": "claude",
                    "capture_event": "SessionStart",
                    "capture_review_status": "pending",
                    "capture_created_from": "2020-01-01",
                    "capture_created_to": "2099-12-31",
                },
                root,
            )
            hook_review_receipt = call_tool(
                "memory.hook_capture_review",
                {
                    "path": hook_capture_relpath,
                    "status": "dismissed",
                    "reviewed_by": "Unit Test",
                    "reason": "No durable memory needed.",
                },
                root,
            )
            hook_status_after_review = call_tool("memory.hook_status", {"client": "claude"}, root)
            context = call_tool("memory.context", {"query": "codex", "budget_tokens": 700}, root)
            outcome = call_tool("memory.outcome", {"last": True, "outcome": "good"}, root)
            lifecycle = call_tool("memory.lifecycle_scores", {}, root)
            recall_candidate = call_tool(
                "memory.recall_miss_candidate",
                {
                    "query": "ai dememory search",
                    "expected_id": "mem_codex_test",
                    "min_rank": 5,
                    "limit": 5,
                },
                root,
            )
            sleep_plan = call_tool("memory.sleep_plan", {}, root)
            sleep_packet = call_tool(
                "memory.sleep_apply_reviewed",
                {"ids": [sleep_plan["candidates"][0]["id"]]},
                root,
            )
            working_snapshot = call_tool(
                "memory.working_snapshot",
                {
                    "title": "Unit Working State",
                    "task": "unit-test",
                    "notes": "Generated working state for MCP test.",
                },
                root,
            )
            working_current = call_tool("memory.working_current", {}, root)
            working_handoff = call_tool(
                "memory.working_handoff",
                {"title": "Unit Handoff", "notes": "Review generated working state."},
                root,
            )
            working_status_result = call_tool("memory.working_status", {"limit": 1}, root)
            auto_context = call_tool("memory.context", {"auto": True, "budget_tokens": 700}, root)
            miss = call_tool(
                "memory.capture_miss",
                {
                    "query": "missing scheduler notes",
                    "reason": "Expected scheduler memory did not rank.",
                    "expected_id": "mem_scheduler",
                },
                root,
            )
            miss_review = call_tool(
                "memory.recall_miss_review",
                {
                    "miss": miss["path"],
                    "status": "rejected",
                    "reviewer": "Unit Test",
                    "reason": "Expected memory is not a valid fixture target.",
                },
                root,
            )
            pending_miss = call_tool(
                "memory.capture_miss",
                {
                    "query": "missing weekly review notes",
                    "reason": "Expected review memory did not rank.",
                    "expected_id": "mem_review",
                },
                root,
            )
            recall_status = call_tool("memory.recall_fixture_status", {}, root)
            recall_review = call_tool("memory.recall_review_plan", {}, root)
            recall_packet = call_tool("memory.recall_review_packet", {}, root)
            archived_recall_packet = write_recall_review_packet_archive(
                root,
                paginate_recall_review_plan(recall_fixture_review_plan(root)),
                now=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            )
            recall_packet_archive_status_result = call_tool(
                "memory.recall_review_packet_archive_status",
                {},
                root,
            )
            recall_packet_archive_retention_result = call_tool(
                "memory.recall_review_packet_archive_retention_plan",
                {},
                root,
            )
            vector_status = call_tool("memory.vector_status", {}, root)
            distribution_roadmap_status = call_tool("memory.roadmap_status", {}, ROOT)
            provenance_status = call_tool("memory.provenance_status", {}, root)
            provider_status = call_tool("memory.providers_status", {}, root)
            provider_plan = call_tool("memory.providers_plan", {}, root)
            setup_result = call_tool("memory.setup_plan", {"client": "codex", "mode": "both"}, root)
            setup_health_result = call_tool("memory.setup_health", {"platform": "linux", "mode": "installed"}, root)
            maintenance_preview = call_tool("memory.maintenance_run", {"profile": "daily", "dry_run": True}, root)
            provider_fixture = Path(tmp) / "provider"
            provider_fixture.mkdir()
            (provider_fixture / "session.jsonl").write_text('{"message":"Review candidate."}\n', encoding="utf-8")
            configure_provider(root, "codex", provider_fixture)
            import_dry_run = call_tool("memory.import_chats", {"provider": "codex", "dry_run": True}, root)
            captured = call_tool(
                "memory.capture_import",
                {
                    "kind": "text",
                    "text": "Capture a non-secret review candidate.",
                    "title": "MCP Capture",
                },
                root,
            )
            with self.assertRaises(PermissionError):
                call_tool("memory.capture_import", {"kind": "markdown", "path": str(Path(tmp) / "outside.md")}, root)
            lesson_repo = Path(tmp) / "lesson-repo"
            lesson_repo.mkdir()
            git(lesson_repo, "init")
            git(lesson_repo, "config", "user.email", "unit@example.test")
            git(lesson_repo, "config", "user.name", "Unit Test")
            (lesson_repo / "ci.yml").write_text("pipeline\n", encoding="utf-8")
            git(lesson_repo, "add", "ci.yml")
            git(lesson_repo, "commit", "-m", "fix ci workflow")
            git_dry_run = call_tool(
                "memory.git_lessons",
                {"repo": str(lesson_repo), "days": 30, "limit": 5},
                root,
            )
            git_lessons_exists_after_dry_run = (root / "inbox" / "git-lessons").exists()
            git_write = call_tool(
                "memory.git_lessons",
                {"repo": str(lesson_repo), "days": 30, "limit": 5, "dry_run": False},
                root,
            )
            secret = "sk-" + "proj-" + ("f" * 40)
            false_positive_fixture = root / "docs" / "false-positive-fixture.md"
            false_positive_fixture.parent.mkdir(parents=True, exist_ok=True)
            false_positive_fixture.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            false_positive_findings = call_tool("memory.review_false_positives", {}, root)
            stale_false_positive_findings = call_tool("memory.review_stale_false_positives", {}, root)
            false_positive_id = false_positive_findings["findings"][0]["id"]
            false_positive_receipt = call_tool(
                "memory.false_positive_ignore",
                {
                    "id": false_positive_id,
                    "reason": "Unit test false-positive fixture.",
                    "reviewer": "Unit Test",
                    "review_after_days": 30,
                },
                root,
            )
            false_positive_unignore_receipt = call_tool(
                "memory.false_positive_unignore",
                {"id": false_positive_id, "reviewer": "Unit Test"},
                root,
            )
            conflicts = call_tool("memory.review_conflicts", {}, root)
            keep_conflict = next(item for item in conflicts["conflicts"] if "mem_codex_test" in item["memory_ids"])
            dismiss_conflict_result = next(
                item for item in conflicts["conflicts"] if "mem_dismiss_one" in item["memory_ids"]
            )
            conflict_id = keep_conflict["id"]
            dismiss_receipt = call_tool(
                "memory.conflict_dismiss",
                {
                    "id": dismiss_conflict_result["id"],
                    "reason": "Unit test intentional duplicate.",
                    "reviewer": "Unit Test",
                },
                root,
            )
            merge = call_tool(
                "memory.conflict_merge_proposal",
                {"id": conflict_id, "reviewer": "Unit Test"},
                root,
            )
            keep = call_tool(
                "memory.conflict_keep",
                {"id": conflict_id, "keep": "mem_codex_test", "reviewer": "Unit Test"},
                root,
            )
            modes = call_tool("memory.review_modes", {}, root)
            review_mode_config = call_tool(
                "memory.review_configure_mode",
                {"mode": "balanced", "reviewer": "Unit Test"},
                root,
            )
            review_policy = call_tool("memory.review_plan", {"kind": "conflict"}, root)
            review_recommendation = call_tool(
                "memory.review_recommendation",
                {
                    "kind": "conflict",
                    "target_id": conflict_id,
                    "recommendation": "keep_memory",
                    "rationale": "Keep the canonical memory after human review.",
                    "recommended_by": "Unit Test LLM",
                    "confidence": 0.71,
                    "evidence": ["mem_codex_test"],
                },
                root,
            )
            review_recommendations_result = call_tool(
                "memory.review_recommendations",
                {"kind": "conflict"},
                root,
            )

        self.assertIn("recent_reports", status)
        self.assertIn("artifacts", status)
        self.assertIn("lifecycle_scores", status["artifacts"])
        self.assertIn("provider_readiness", status)
        self.assertIn("providers", status["provider_readiness"])
        self.assertIn("review_due", status)
        self.assertFalse(status["review_due"]["canonical_memory_updated"])
        self.assertIn("review_recommendations", status)
        self.assertFalse(status["review_recommendations"]["applies_review_decisions"])
        self.assertEqual(len(plan["commands"]), 2)
        self.assertEqual(len(plan["cron_entries"]), 2)
        self.assertFalse(plan["mutates_system"])
        self.assertTrue(any("ai-dememory maintenance run --profile daily" in entry["line"] for entry in plan["cron_entries"]))
        self.assertFalse(schedule["configured"])
        self.assertEqual(schedule["platform"], "windows")
        self.assertFalse(schedule["mutates_system"])
        self.assertEqual(len(schedule["status_commands"]), 2)
        self.assertTrue(all(command["command"][0] == "schtasks" for command in schedule["status_commands"]))
        self.assertEqual(schedule_env["platform"], "windows")
        self.assertFalse(schedule_env["mutates_system"])
        self.assertFalse(schedule_env["runs_commands"])
        self.assertTrue(any(check["name"] == "host_scheduler" for check in schedule_env["checks"]))
        self.assertEqual(docker_plan["commands"][0]["run_command"][:2], ["docker", "run"])
        self.assertIn("ai-dememory:test", docker_plan["commands"][0]["run_command"])
        self.assertTrue(any(entry["command"][:2] == ["docker", "run"] for entry in docker_plan["cron_entries"]))
        self.assertEqual(len(acceptance["items"]), len(ACCEPTANCE_ITEMS))
        self.assertFalse(verification["verification"]["complete"])
        self.assertEqual(verification["verification"]["total"], len(ACCEPTANCE_ITEMS))
        self.assertEqual(acceptance_plan_result["plan"]["remaining_count"], len(ACCEPTANCE_ITEMS))
        self.assertEqual(acceptance_plan_result["plan"]["blocked_count"], 0)
        self.assertEqual(acceptance_plan_result["plan"]["reviewer"], "Unit Reviewer")
        self.assertEqual(acceptance_plan_result["plan"]["pr_url"], pr_url)
        self.assertTrue(acceptance_plan_result["plan"]["next_actions"])
        self.assertTrue(
            all(item["suggested_artifacts"] for item in acceptance_plan_result["plan"]["items"] if not item["completed"])
        )
        self.assertFalse(acceptance_template_result["records_evidence"])
        self.assertFalse(acceptance_template_result["writes_files"])
        self.assertEqual(acceptance_template_result["reviewer"], "Unit Reviewer")
        self.assertEqual(acceptance_template_result["pr_url"], pr_url)
        self.assertIn("--reviewed-by 'Unit Reviewer'", acceptance_template_result["command"])
        self.assertIn(f"--artifact '{pr_url}'", acceptance_template_result["command"])
        self.assertFalse(acceptance_packet_result["records_evidence"])
        self.assertFalse(acceptance_packet_result["writes_files"])
        self.assertIn("Manual Acceptance Packet", acceptance_packet_result["markdown"])
        self.assertEqual(acceptance_packet_archive_status_result["archive_root"], "reports/manual-acceptance-packets")
        self.assertEqual(acceptance_packet_archive_status_result["total_count"], 1)
        self.assertEqual(
            acceptance_packet_archive_status_result["archives"][0]["path"],
            repo_relative_path(archived_acceptance_packet, root),
        )
        self.assertEqual(
            acceptance_packet_archive_status_result["archives"][0]["generated_at"],
            "2026-06-22T12:00:00Z",
        )
        self.assertFalse(acceptance_packet_archive_status_result["writes_files"])
        self.assertFalse(acceptance_packet_archive_status_result["records_evidence"])
        self.assertFalse(acceptance_packet_archive_status_result["writes_acceptance_records"])
        self.assertEqual(acceptance_packet_archive_retention_result["archive_root"], "reports/manual-acceptance-packets")
        self.assertEqual(acceptance_packet_archive_retention_result["total_count"], 1)
        self.assertEqual(acceptance_packet_archive_retention_result["keep"], 30)
        self.assertEqual(acceptance_packet_archive_retention_result["prunable_count"], 0)
        self.assertFalse(acceptance_packet_archive_retention_result["writes_files"])
        self.assertFalse(acceptance_packet_archive_retention_result["deletes_files"])
        self.assertFalse(acceptance_packet_archive_retention_result["records_evidence"])
        self.assertFalse(acceptance_packet_archive_retention_result["writes_acceptance_records"])
        self.assertFalse(vault_release_evidence["available"])
        self.assertIn("distribution checkout", vault_release_evidence["reason"])
        self.assertFalse(vault_release_evidence_report["available"])
        self.assertFalse(vault_release_evidence_report["writes_files"])
        self.assertIsNone(vault_release_evidence_report["markdown"])
        self.assertIn("distribution checkout", vault_release_evidence_report["reason"])
        self.assertFalse(vault_roadmap_status["writes_files"])
        self.assertFalse(vault_roadmap_status["mutates_files"])
        self.assertEqual(vault_roadmap_status["phase_count"], 11)
        self.assertGreater(vault_roadmap_status["status_counts"].get("missing_evidence", 0), 0)
        self.assertEqual(doctor["profile"], "vault")
        self.assertGreaterEqual(doctor["summary"]["total"], 5)
        self.assertTrue(any(check["name"] == "schema" for check in doctor["checks"]))
        self.assertTrue(validate_status["ok"])
        self.assertEqual(validate_status["exit_code"], 0)
        self.assertGreaterEqual(validate_status["memory_count"], 4)
        self.assertEqual(validate_status["conflict_review"]["status"], "scanned")
        self.assertIn("SessionStart", hook_list["providers"]["claude"])
        self.assertIn("SessionStart", hook_fragment["config"]["hooks"])
        self.assertEqual(hook_status_result["captures"]["total_count"], 1)
        self.assertEqual(hook_status_result["captures"]["pending_count"], 1)
        self.assertEqual(
            hook_status_filtered["captures"]["filters"],
            {
                "created_from": "2020-01-01",
                "created_to": "2099-12-31",
                "event": "SessionStart",
                "provider": "claude",
                "review_status": "pending",
            },
        )
        self.assertEqual(hook_status_filtered["captures"]["total_count"], 1)
        self.assertEqual(hook_review_receipt["path"], hook_capture_relpath)
        self.assertEqual(hook_review_receipt["review_status"], "dismissed")
        self.assertEqual(hook_review_receipt["reviewed_by"], "Unit Test")
        self.assertIsNotNone(hook_review_receipt["reviewed_at"])
        self.assertFalse(hook_review_receipt["canonical_memory_updated"])
        self.assertEqual(hook_status_after_review["captures"]["pending_count"], 0)
        self.assertEqual(hook_status_after_review["captures"]["resolved_count"], 1)
        self.assertTrue(any(item["id"] == "mem_codex_test" for item in context["items"]))
        self.assertEqual(mark_seen_receipt["selected_memory_id"], "mem_codex_test")
        self.assertTrue(mark_seen_receipt["lifecycle_updated"])
        self.assertEqual(outcome["memory_id"], "mem_codex_test")
        self.assertEqual(outcome["target_source"], "last_seen")
        self.assertTrue(outcome["lifecycle_updated"])
        self.assertEqual(outcome["positive_outcomes"], 1)
        self.assertTrue(any(item["memory_id"] == "mem_codex_test" for item in lifecycle["scores"]))
        self.assertFalse(recall_candidate["candidate_miss"])
        self.assertLessEqual(recall_candidate["expected_rank"], 5)
        self.assertFalse(recall_candidate["writes_files"])
        self.assertEqual(recall_candidate["capture_dry_run_command"], [])
        self.assertTrue(sleep_plan["candidates"])
        self.assertTrue(sleep_packet["written"][0].startswith("inbox/sleep-consolidation/"))
        self.assertEqual(working_snapshot["path"], "working/current.json")
        self.assertEqual(working_current["current"]["task"], "unit-test")
        self.assertTrue(working_handoff["path"].startswith("working/handoffs/"))
        self.assertTrue(working_status_result["current_exists"])
        self.assertEqual(working_status_result["handoff_count"], 1)
        self.assertEqual(len(working_status_result["handoffs"]), 1)
        self.assertEqual(auto_context["query_source"], "working_memory")
        self.assertIn("Unit Working State", auto_context["query"])
        self.assertTrue(miss["path"].startswith("inbox/recall-feedback/"))
        self.assertEqual(miss_review["path"], miss["path"])
        self.assertEqual(miss_review["status"], "rejected")
        self.assertEqual(miss_review["reviewed_by"], "Unit Test")
        self.assertFalse(miss_review["fixture_updated"])
        self.assertFalse(miss_review["canonical_memory_updated"])
        self.assertTrue(pending_miss["path"].startswith("inbox/recall-feedback/"))
        self.assertEqual(recall_status["fixtures_path"], "quality/recall-fixtures.json")
        self.assertEqual(recall_status["status"], "needs_reviewed_promotion")
        self.assertEqual(recall_review["pending_count"], 1)
        self.assertEqual(recall_review["resolved_count"], 1)
        self.assertIn("check-miss", recall_review["candidate_check_command"])
        self.assertTrue(recall_review["pending_misses"][0]["path"].startswith("inbox/recall-feedback/"))
        self.assertEqual(recall_review["recent_resolved_misses"][0]["path"], miss["path"])
        self.assertEqual(recall_review["recent_resolved_misses"][0]["status"], "rejected")
        self.assertEqual(recall_packet["pending_count"], 1)
        self.assertFalse(recall_packet["writes_files"])
        self.assertFalse(recall_packet["writes_fixture_file"])
        self.assertFalse(recall_packet["closes_miss_files"])
        self.assertIn("Recall Review Packet", recall_packet["markdown"])
        self.assertEqual(recall_packet_archive_status_result["archive_root"], "reports/recall-review-packets")
        self.assertEqual(recall_packet_archive_status_result["total_count"], 1)
        self.assertEqual(
            recall_packet_archive_status_result["archives"][0]["path"],
            repo_relative_path(archived_recall_packet, root),
        )
        self.assertEqual(
            recall_packet_archive_status_result["archives"][0]["generated_at"],
            "2026-06-22T12:00:00Z",
        )
        self.assertFalse(recall_packet_archive_status_result["writes_files"])
        self.assertFalse(recall_packet_archive_status_result["records_fixture_promotions"])
        self.assertFalse(recall_packet_archive_status_result["writes_fixture_file"])
        self.assertFalse(recall_packet_archive_status_result["closes_miss_files"])
        self.assertEqual(recall_packet_archive_retention_result["archive_root"], "reports/recall-review-packets")
        self.assertEqual(recall_packet_archive_retention_result["total_count"], 1)
        self.assertEqual(recall_packet_archive_retention_result["keep"], 30)
        self.assertEqual(recall_packet_archive_retention_result["prunable_count"], 0)
        self.assertFalse(recall_packet_archive_retention_result["writes_files"])
        self.assertFalse(recall_packet_archive_retention_result["deletes_files"])
        self.assertFalse(recall_packet_archive_retention_result["records_fixture_promotions"])
        self.assertFalse(recall_packet_archive_retention_result["writes_fixture_file"])
        self.assertFalse(recall_packet_archive_retention_result["closes_miss_files"])
        self.assertEqual(vector_status["decision"], "insufficient_evidence")
        self.assertEqual(vector_status["recall"]["failed_cases"], 0)
        self.assertFalse(distribution_roadmap_status["writes_files"])
        self.assertEqual(distribution_roadmap_status["status_counts"]["implemented"], 10)
        self.assertEqual(distribution_roadmap_status["status_counts"]["gated"], 1)
        self.assertEqual(provenance_status["issue_count"], 0)
        self.assertIn("issues", provenance_status)
        self.assertTrue(captured["result"]["written"][0].startswith("inbox/imports/text/"))
        self.assertEqual(false_positive_receipt["path"], ".ai-dememory-ignore.toml")
        self.assertEqual(stale_false_positive_findings["stale_count"], 0)
        self.assertEqual(false_positive_receipt["id"], false_positive_id)
        self.assertTrue(false_positive_receipt["ignored"])
        self.assertEqual(false_positive_receipt["reviewer"], "Unit Test")
        self.assertIsNotNone(false_positive_receipt["reviewed_at"])
        self.assertIsNotNone(false_positive_receipt["review_after"])
        self.assertFalse(false_positive_receipt["review_due"])
        self.assertEqual(false_positive_receipt["review_after_status"], "scheduled")
        self.assertFalse(false_positive_receipt["canonical_memory_updated"])
        self.assertEqual(false_positive_unignore_receipt["path"], ".ai-dememory-ignore.toml")
        self.assertEqual(false_positive_unignore_receipt["id"], false_positive_id)
        self.assertFalse(false_positive_unignore_receipt["ignored"])
        self.assertEqual(false_positive_unignore_receipt["reviewer"], "Unit Test")
        self.assertIsNotNone(false_positive_unignore_receipt["reviewed_at"])
        self.assertFalse(false_positive_unignore_receipt["review_due"])
        self.assertEqual(false_positive_unignore_receipt["review_after_status"], "not_ignored")
        self.assertFalse(false_positive_unignore_receipt["canonical_memory_updated"])
        self.assertTrue(conflicts["conflicts"])
        self.assertEqual(dismiss_receipt["path"], ".ai-dememory-ignore.toml")
        self.assertEqual(dismiss_receipt["id"], dismiss_conflict_result["id"])
        self.assertEqual(dismiss_receipt["status"], "dismissed")
        self.assertEqual(dismiss_receipt["decision"], "Unit test intentional duplicate.")
        self.assertEqual(dismiss_receipt["reviewer"], "Unit Test")
        self.assertIsNotNone(dismiss_receipt["reviewed_at"])
        self.assertFalse(dismiss_receipt["canonical_memory_updated"])
        self.assertEqual(merge["path"], ".ai-dememory-ignore.toml")
        self.assertEqual(merge["id"], conflict_id)
        self.assertEqual(merge["status"], "review_proposed")
        self.assertEqual(merge["decision"], "merge_proposal")
        self.assertEqual(merge["reviewer"], "Unit Test")
        self.assertIsNotNone(merge["reviewed_at"])
        self.assertTrue(merge["proposal_path"].startswith("inbox/conflict-resolution/"))
        self.assertFalse(merge["canonical_memory_updated"])
        self.assertEqual(keep["path"], ".ai-dememory-ignore.toml")
        self.assertEqual(keep["status"], "resolved")
        self.assertEqual(keep["decision"], "keep:mem_codex_test")
        self.assertEqual(keep["reviewer"], "Unit Test")
        self.assertIsNotNone(keep["reviewed_at"])
        self.assertFalse(keep["canonical_memory_updated"])
        self.assertEqual(modes["active"], "strict")
        self.assertEqual(review_mode_config["path"], ".ai-dememory.toml")
        self.assertEqual(review_mode_config["requested_mode"], "balanced")
        self.assertEqual(review_mode_config["active"], "balanced")
        self.assertEqual(review_mode_config["reviewer"], "Unit Test")
        self.assertFalse(review_mode_config["allow_llm_merge_proposals"])
        self.assertFalse(review_mode_config["canonical_memory_updated"])
        self.assertEqual(review_policy["mode"], "balanced")
        self.assertTrue(review_recommendation["path"].startswith("inbox/review-recommendations/"))
        self.assertEqual(review_recommendation["mode"], "balanced")
        self.assertTrue(review_recommendation["allowed_by_mode"])
        self.assertFalse(review_recommendation["policy_violation"])
        self.assertTrue(review_recommendation["requires_human_approval"])
        self.assertFalse(review_recommendation["applies_review_decision"])
        self.assertFalse(review_recommendation["writes_canonical_memory"])
        self.assertEqual(review_recommendations_result["total_count"], 1)
        self.assertFalse(review_recommendations_result["writes_files"])
        self.assertFalse(review_recommendations_result["applies_review_decisions"])
        self.assertFalse(review_recommendations_result["writes_canonical_memory"])
        self.assertIn("providers", provider_status)
        self.assertGreaterEqual(provider_status["configured_count"], 0)
        self.assertGreaterEqual(provider_status["enabled_count"], 0)
        self.assertGreaterEqual(provider_status["import_ready_count"], 0)
        self.assertFalse(provider_status["mutates_system"])
        self.assertFalse(provider_status["reads_provider_files"])
        self.assertFalse(provider_status["writes_import_candidates"])
        self.assertIn("providers", provider_plan)
        self.assertFalse(provider_plan["mutates_system"])
        self.assertFalse(provider_plan["reads_provider_files"])
        self.assertFalse(provider_plan["writes_import_candidates"])
        self.assertTrue(import_dry_run["result"]["dry_run"])
        self.assertEqual(import_dry_run["result"]["written"], [])
        self.assertFalse(import_dry_run["result"]["writes_import_candidates"])
        self.assertTrue(git_dry_run["result"]["dry_run"])
        self.assertEqual(git_dry_run["result"]["written"], [])
        self.assertEqual(git_dry_run["result"]["examined"], 1)
        self.assertFalse(git_lessons_exists_after_dry_run)
        self.assertFalse(git_write["result"]["dry_run"])
        self.assertTrue(git_write["result"]["written"][0].startswith("inbox/git-lessons/"))
        self.assertIn("commands", setup_result)
        self.assertFalse(setup_result["mutates_system"])
        self.assertFalse(setup_result["writes_files"])
        self.assertFalse(setup_result["installs_schedules"])
        self.assertFalse(setup_result["installs_hooks"])
        self.assertTrue(setup_result["suggests_generated_reports"])
        self.assertTrue(setup_result["suggests_generated_archive_status"])
        self.assertTrue(setup_result["suggests_generated_archive_retention"])
        self.assertEqual(
            setup_result["commands"]["generated_reports"]["manual_acceptance_plan"][-2:],
            ["plan", "--write-report"],
        )
        self.assertEqual(
            setup_result["commands"]["generated_reports"]["recall_review_packet"][-2:],
            ["packet", "--write-report"],
        )
        self.assertEqual(
            setup_result["commands"]["generated_archive_status"]["manual_acceptance_packets"][-2:],
            ["packet-archive-status", "--json"],
        )
        self.assertEqual(
            setup_result["commands"]["generated_archive_status"]["recall_review_packets"][-2:],
            ["packet-archive-status", "--json"],
        )
        self.assertEqual(
            setup_result["commands"]["generated_archive_retention"]["manual_acceptance_packets"][-2:],
            ["packet-archive-retention-plan", "--json"],
        )
        self.assertEqual(
            setup_result["commands"]["generated_archive_retention"]["recall_review_packets"][-2:],
            ["packet-archive-retention-plan", "--json"],
        )
        self.assertEqual(len(setup_result["commands"]["mcp_configs"]), 2)
        self.assertIn("schedule_environment", setup_health_result)
        self.assertIn("validation_status", setup_health_result)
        self.assertTrue(setup_health_result["validation_status"]["ok"])
        self.assertIn("recall_review", setup_health_result)
        self.assertIn("next_actions", setup_health_result["recall_review"])
        self.assertIn("schedule_status", setup_health_result)
        self.assertIn("provider_readiness", setup_health_result)
        self.assertIn("generated_packet_archives", setup_health_result)
        self.assertIn("prunable_count", setup_health_result["generated_packet_archives"]["summary"])
        self.assertFalse(setup_health_result["generated_packet_archives"]["writes_files"])
        self.assertFalse(setup_health_result["generated_packet_archives"]["deletes_files"])
        self.assertIn("artifact_freshness", setup_health_result)
        self.assertFalse(setup_health_result["artifact_freshness"]["writes_files"])
        self.assertIn("maintenance_preflight", setup_health_result)
        self.assertIn("review_due", setup_health_result)
        self.assertIn("conflict_review", setup_health_result)
        self.assertIn("hook_status", setup_health_result)
        self.assertFalse(setup_health_result["hook_status"]["writes_files"])
        self.assertFalse(hook_status_result["writes_files"])
        self.assertIn("captures", hook_status_result)
        self.assertFalse(hook_status_result["captures"]["reads_raw_payloads"])
        self.assertEqual(hook_status_result["hooks"][0]["client"], "claude")
        self.assertFalse(setup_health_result["mutates_system"])
        self.assertFalse(setup_health_result["runs_commands"])
        self.assertFalse(setup_health_result["writes_files"])
        self.assertTrue(setup_health_result["next_actions"])
        self.assertFalse(setup_health_result["maintenance_preflight"]["reads_provider_files"])
        self.assertFalse(setup_health_result["maintenance_preflight"]["writes_files"])
        self.assertTrue(maintenance_preview["result"]["dry_run"])
        self.assertFalse(maintenance_preview["result"]["writes_files"])
        self.assertFalse(maintenance_preview["result"]["writes_import_candidates"])
        self.assertIn("artifact_freshness", maintenance_preview["result"])
        self.assertIn("indexes/memory.sqlite", maintenance_preview["result"]["would_generate"])


def write_memory(
    root: Path,
    relpath: str,
    memory_id: str,
    sensitivity: str = "internal",
    memory_type: str = "tool",
    reviewed: bool | None = None,
    reviewed_by: str | None = "Gonzalo Torreras",
    reviewed_at: str | None = "2026-06-14",
    body: str = "ai DeMemory search should find this document.",
    title: str = "Codex Test Memory",
) -> Path:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        valid_memory_text(memory_id, sensitivity, memory_type, reviewed, reviewed_by, reviewed_at, body, title),
        encoding="utf-8",
    )
    return path


def valid_memory_text(
    memory_id: str,
    sensitivity: str = "internal",
    memory_type: str = "tool",
    reviewed: bool | None = None,
    reviewed_by: str | None = "Gonzalo Torreras",
    reviewed_at: str | None = "2026-06-14",
    body: str = "ai DeMemory search should find this document.",
    title: str = "Codex Test Memory",
) -> str:
    reviewed_line = ""
    if reviewed is not None:
        reviewed_line = f"reviewed: {'true' if reviewed else 'false'}\n"
        if reviewed_by is not None:
            reviewed_line += f"reviewed_by: {reviewed_by}\n"
        if reviewed_at is not None:
            reviewed_line += f"reviewed_at: {reviewed_at}\n"
    return f"""---
id: {memory_id}
title: {title}
type: {memory_type}
{reviewed_line}status: active
scope: tool
project: null
tags: [codex, memory]
aliases: [codex test]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.9
sensitivity: {sensitivity}
source:
  kind: manual
  ref: unittest
pin: false
decay: normal
review_after: 2026-09-14
---

# Codex Test Memory

{body}
"""


def api_get(url: str, api_key: str) -> dict[str, object]:
    request = Request(url, headers={"X-API-Key": api_key})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


if __name__ == "__main__":
    unittest.main()
