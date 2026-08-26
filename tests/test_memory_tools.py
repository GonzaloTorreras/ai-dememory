from __future__ import annotations

import json
import io
import os
import signal
import shlex
from contextlib import ExitStack, nullcontext, redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from http import HTTPStatus
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MCP_SERVER = ROOT / "mcp" / "server"
PINNED_TEST_IMAGE = "registry.example/ai-dememory@sha256:" + ("a" * 64)
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(MCP_SERVER))

from ai_dememory_tool import __version__ as PACKAGE_VERSION  # noqa: E402
from acceptance_guard import validate_acceptance_checklist, validate_acceptance_checklist_text  # noqa: E402
from adr_guard import validate_adr_docs, validate_adr_text  # noqa: E402
from index_memory import rebuild_index  # noqa: E402
from export_context import export_context  # noqa: E402
from capture_miss import capture_miss, main as capture_miss_main, render_miss_text  # noqa: E402
from consolidate_memory import main as consolidate_main, build_report as build_consolidation_report  # noqa: E402
from context_memory import assemble_context, context_defaults, main as context_main  # noqa: E402
from command_render import render_copy_command  # noqa: E402
from eval_recall import evaluate, load_fixtures  # noqa: E402
import graph_memory  # noqa: E402
from git_lessons import (  # noqa: E402
    MAX_GIT_OUTPUT_BYTES,
    MAX_REPOSITORIES,
    classify_commit,
    learn_git,
    main as git_lessons_main,
    run_git,
)
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
    serialize_hook_command,
    uninstall_hook_instructions,
    write_hook_capture_report,
)
from http_api import (  # noqa: E402
    MUTATION_INTENT_HEADER,
    MUTATION_INTENT_VALUE,
    ApiError,
    main as api_main,
    parse_json_body,
    read_json_body,
    read_request_body,
    require_safe_request_context,
    serve,
)
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
    assert_setup_plan,
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
    TIMEOUT_EXIT_CODE,
    conflict_review_summary,
    dry_run_maintenance,
    generated_artifact_freshness,
    main as maintenance_main,
    maintenance_lock,
    maintenance_status,
    process_is_running,
    read_lock_record,
    review_due_summary,
    review_recommendation_summary,
    run_maintenance,
    run_supervised_maintenance,
    run_supervised_process,
)
from manual_acceptance import (  # noqa: E402
    ACCEPTANCE_ITEMS,
    ACCEPTANCE_REVISIONS,
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
from memory_mcp import TOOLS, call_tool, handle_rpc, main as memory_mcp_main  # noqa: E402
from mcp_client_smoke import ClientSmokeError, bind_config_runtime_root, main as mcp_client_smoke_main, override_launch, run_client_config_smoke, run_tools_list_pages, select_server_config, verify_enabled_tools  # noqa: E402
from mcp_inventory import INVENTORY_DOCS, build_inventory, main as mcp_inventory_main, validate_inventory_docs, validate_inventory_texts  # noqa: E402
from mcp_runtime_smoke import MCP_INITIALIZED, assert_unique_field, collect_paginated_items, rpc_response, run_fixture_smoke, send_notification  # noqa: E402
from memorylib import (  # noqa: E402
    MemoryError,
    content_hash,
    discover_markdown_files,
    discover_memory_files,
    load_memory,
    repo_relative_path,
    safe_write_text,
    validate_memories,
)
from provider_import import capture_source, configure_provider, configure_provider_preview, configured_import_path, default_provider_paths, detect_providers, import_chats, main as provider_main, provider_setup_plan, providers_status  # noqa: E402
from publish_guard import (  # noqa: E402
    validate_legacy_preflight_workflow_text,
    validate_publisher_inventory,
    validate_publish_workflow,
    validate_publish_workflow_text,
)
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
from release_checklist_guard import (  # noqa: E402
    GENERATED_ARTIFACTS_VAULT_PRECONDITION,
    validate_release_checklist,
    validate_release_checklist_text,
)
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
    write_report as write_release_evidence_report,
)
from release_check import (  # noqa: E402
    EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS,
    EXPECTED_PLUGIN_MCP_TOOLS,
    check_pr_gate,
    check_codex_plugin,
    load_json as release_load_json,
    plugin_version_for_package,
    plugin_skill_safety_issues,
)
from doctor import main as doctor_main, run_checks as run_doctor_checks  # noqa: E402
from config_file import CONFIG_WRITE_LOCK_NAME, ConfigError, load_config, set_section  # noqa: E402
from schedule_memory import (  # noqa: E402
    SCHEDULE_OPERATION_LOCK_NAME,
    SCHEDULE_VERIFICATION_TTL_SECONDS,
    active_schedule_receipt_source,
    build_cron_entries,
    build_schedule_commands,
    configure_schedule,
    main as schedule_main,
    mark_schedule_verified,
    remove_platform_schedule_files,
    render_cron_entries,
    run_install_commands,
    run_remove_commands,
    run_schedule_command,
    schedule_environment,
    schedule_plan_fingerprint,
    schedule_namespace,
    schedule_plan,
    schedule_status,
    systemd_service,
    windows_restore_commands,
)
from search_memory import search  # noqa: E402
from secret_scan import scan_paths  # noqa: E402
from setup_plan import mcp_config_command, main as setup_plan_main, setup_health, setup_plan  # noqa: E402
from onboarding import main as onboarding_main  # noqa: E402
from sleep_consolidation import SleepError, apply_review_packets, build_sleep_plan, main as sleep_main, write_sleep_report  # noqa: E402
from vector_gate import VectorReadiness, evaluate_vector_readiness, write_vector_report  # noqa: E402
from validate_memory import main as validate_main, validate_repo, validate_repo_result  # noqa: E402
from verify_mcp_contract import validate_contract  # noqa: E402
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
from ai_dememory_tool.cli import (  # noqa: E402
    COMMAND_CONTEXTUAL_ROOT_CONTRACTS,
    COMMAND_ROOT_POLICIES,
    COMMANDS,
    PARSER_OWNED_COMMANDS,
    CommandRootPolicy,
    build_mcp_config,
    copy_template_tree,
    export_vault_template,
    find_memory_root,
    is_tool_checkout,
    is_within_tool_checkout,
    main as cli_main,
    mcp_config,
)
from ai_dememory_tool.vault_binding import (  # noqa: E402
    resolve_runtime_vault,
    save_default_vault,
)
from ci_guard import (  # noqa: E402
    validate_ci_workflow,
    validate_ci_workflow_text,
    validate_solo_maintainer_review_boundary,
    validate_workflow_supply_chain,
)
from artifact_guard import validate_artifact_paths, validate_staged_artifacts  # noqa: E402
from vault_setup_guard import REQUIRED_IGNORES, validate_create_memory_repo_text, validate_gitignore_text, validate_vault_setup  # noqa: E402
from durable_provenance import audit_durable_provenance, render_markdown as render_provenance_markdown  # noqa: E402


def initialize_minimal_runtime_vault(root: Path) -> Path:
    """Create only the structural marker needed by runtime-bound CLI tests."""
    root.mkdir(parents=True, exist_ok=True)
    marker = root / ".ai-dememory.toml"
    marker.write_text("", encoding="utf-8")
    return marker


class MemoryToolTests(unittest.TestCase):
    def setUp(self) -> None:
        # Never let a developer's selected default vault influence a test that
        # intentionally exercises rootless/error paths.
        self._default_selector_home = tempfile.TemporaryDirectory()
        self._default_selector_patch = patch.dict(
            os.environ,
            {"AI_DEMEMORY_CONFIG_HOME": self._default_selector_home.name},
            clear=False,
        )
        self._default_selector_patch.start()
        self.addCleanup(self._default_selector_home.cleanup)
        self.addCleanup(self._default_selector_patch.stop)

    def test_command_root_policy_covers_every_generic_command_exactly(self) -> None:
        expected_parser_owned = {
            "mcp",
            "api",
            "hook-event",
            "hooks",
            "setup",
            "onboard",
            "providers",
            "import-chats",
            "capture",
            "maintenance",
            "schedule",
        }

        self.assertEqual(PARSER_OWNED_COMMANDS, expected_parser_owned)
        self.assertEqual(
            set(COMMAND_ROOT_POLICIES),
            set(COMMANDS) - expected_parser_owned,
        )
        self.assertFalse(set(COMMAND_ROOT_POLICIES) & expected_parser_owned)
        self.assertEqual(len(COMMANDS), 56)
        self.assertEqual(len(COMMAND_ROOT_POLICIES), 45)

    def test_command_root_policy_groups_are_exhaustive_and_disjoint(self) -> None:
        expected_by_policy = {
            CommandRootPolicy.SOURCE_BOUND: {
                "release-check",
                "install-smoke",
                "package-build-smoke",
                "publish-guard",
                "ci-guard",
                "artifact-guard",
                "vault-setup-guard",
                "pr-template-guard",
                "pr-draft-guard",
                "acceptance-guard",
                "adr-guard",
                "release-checklist-guard",
                "release-evidence",
                "mcp-smoke",
            },
            CommandRootPolicy.VAULT_BOUND: {
                "context",
                "graph",
                "recall-fixtures",
                "vector",
                "capture-miss",
                "provenance",
                "export-context",
                "consolidate",
                "sleep",
                "learn",
                "turn-context",
                "working",
                "lifecycle",
                "mark-seen",
                "outcome",
                "review",
                "false-positive",
                "conflict",
                "mcp-client-smoke",
            },
            CommandRootPolicy.CONTEXTUAL: {
                "doctor",
                "validate",
                "secret-scan",
                "index",
                "search",
                "eval-recall",
                "roadmap",
                "acceptance",
                "publish-plan",
                "mcp-inventory",
            },
            CommandRootPolicy.ROOTLESS: {"api-smoke", "verify-mcp"},
        }

        actual_by_policy = {
            policy: {
                command
                for command, command_policy in COMMAND_ROOT_POLICIES.items()
                if command_policy is policy
            }
            for policy in CommandRootPolicy
        }
        self.assertEqual(actual_by_policy, expected_by_policy)
        flattened = set().union(*actual_by_policy.values())
        self.assertEqual(flattened, set(COMMAND_ROOT_POLICIES))
        self.assertEqual(
            sum(len(commands) for commands in actual_by_policy.values()),
            len(flattened),
        )

    def test_contextual_root_contracts_define_terminal_branches(self) -> None:
        contextual_commands = {
            command
            for command, policy in COMMAND_ROOT_POLICIES.items()
            if policy is CommandRootPolicy.CONTEXTUAL
        }

        self.assertEqual(set(COMMAND_CONTEXTUAL_ROOT_CONTRACTS), contextual_commands)
        for command, contract in COMMAND_CONTEXTUAL_ROOT_CONTRACTS.items():
            with self.subTest(command=command):
                self.assertTrue(contract.selector.strip())
                self.assertGreaterEqual(len(contract.branches), 2)
                labels = [label for label, _ in contract.branches]
                self.assertEqual(len(labels), len(set(labels)))
                self.assertTrue(all(label.strip() for label in labels))
                self.assertTrue(
                    all(
                        policy in {
                            CommandRootPolicy.SOURCE_BOUND,
                            CommandRootPolicy.VAULT_BOUND,
                            CommandRootPolicy.ROOTLESS,
                        }
                        for _, policy in contract.branches
                    )
                )

    def test_command_aliases_share_root_policy_and_dispatch_module(self) -> None:
        alias_groups = (
            ("lifecycle", "mark-seen", "outcome"),
            ("review", "false-positive", "conflict"),
        )
        for aliases in alias_groups:
            with self.subTest(aliases=aliases):
                self.assertEqual(
                    {COMMAND_ROOT_POLICIES[command] for command in aliases},
                    {CommandRootPolicy.VAULT_BOUND},
                )
                self.assertEqual(
                    len({COMMANDS[command][1] for command in aliases}),
                    1,
                )

    def test_verify_mcp_contract_is_package_bound_not_source_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_root = Path(tmp) / "not-a-checkout-or-vault"

            self.assertFalse(missing_root.exists())
            self.assertEqual(validate_contract(missing_root), [])

    def test_mcp_inventory_reads_source_only_for_check_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_root = Path(tmp) / "not-a-checkout-or-vault"

            inventory_output = io.StringIO()
            with (
                patch("mcp_inventory.repo_root", return_value=missing_root),
                redirect_stdout(inventory_output),
            ):
                self.assertEqual(mcp_inventory_main(["--json"]), 0)
            self.assertEqual(json.loads(inventory_output.getvalue())["tool_count"], len(TOOLS))

            profile_output = io.StringIO()
            with (
                patch("mcp_inventory.repo_root", return_value=missing_root),
                redirect_stdout(profile_output),
            ):
                self.assertEqual(mcp_inventory_main(["--profile", "core", "--json"]), 0)
            self.assertEqual(json.loads(profile_output.getvalue())["profile"], "core")

            documentation_output = io.StringIO()
            with (
                patch("mcp_inventory.repo_root", return_value=missing_root),
                redirect_stdout(documentation_output),
            ):
                self.assertEqual(mcp_inventory_main(["--check-docs", "--json"]), 1)
            issues = json.loads(documentation_output.getvalue())
            self.assertEqual({issue["target"] for issue in issues}, set(INVENTORY_DOCS))
            self.assertFalse(missing_root.exists())

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
            self.assertEqual(
                config["args"],
                [
                    "mcp",
                    "--stdio",
                    "--idle-timeout-seconds",
                    "600",
                    "--profile",
                    "core",
                    "--require-bound-root",
                ],
            )
            self.assertEqual(Path(config["env"]["AI_DEMEMORY_ROOT"]), root.resolve())

    def test_mcp_config_requires_binding_before_ambient_checkout_discovery(self) -> None:
        error = io.StringIO()
        with (
            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
            patch("ai_dememory_tool.cli.find_memory_root", return_value=ROOT) as root_resolver,
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            mcp_config(["--client", "codex"])

        self.assertEqual(raised.exception.code, 2)
        root_resolver.assert_not_called()
        self.assertIn("runtime vault binding requires", error.getvalue())

    def test_tool_checkout_recognizes_the_source_that_loaded_the_cli(self) -> None:
        self.assertTrue(is_tool_checkout(ROOT))

    def test_source_archive_is_detected_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source-archive"
            (source / "ai_dememory_tool").mkdir(parents=True)
            (source / "memories").mkdir()
            (source / "ai_dememory_tool" / "cli.py").write_text(
                "# source marker\n",
                encoding="utf-8",
            )
            (source / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\n',
                encoding="utf-8",
            )

            self.assertTrue(is_tool_checkout(source))

    def test_installed_site_packages_is_not_a_source_checkout_or_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site_packages = base / "site-packages"
            package = site_packages / "ai_dememory_tool"
            unrelated = base / "unrelated"
            package.mkdir(parents=True)
            unrelated.mkdir()
            module = package / "cli.py"
            module.write_text("# installed module\n", encoding="utf-8")

            self.assertFalse(is_tool_checkout(site_packages))
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                patch("ai_dememory_tool.cli.__file__", str(module)),
                self.assertRaises(RuntimeError),
            ):
                find_memory_root(start=unrelated)

    def test_unrelated_git_vault_is_not_a_tool_checkout_even_with_mutable_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            nested = vault / "memories" / "projects"
            (vault / ".git").mkdir(parents=True)
            (vault / "docs").mkdir()
            (vault / "scripts").mkdir()
            nested.mkdir(parents=True)
            (vault / ".ai-dememory.toml").write_text("version = 1\n", encoding="utf-8")
            (vault / "docs" / "schema.md").write_text("# Private vault\n", encoding="utf-8")
            (vault / ".git" / "config").write_text(
                '[remote "origin"]\n'
                "\turl = https://github.com/example/private-memory.git\n",
                encoding="utf-8",
            )

            self.assertFalse(is_tool_checkout(vault))
            self.assertFalse(is_within_tool_checkout(nested))

    def test_mcp_config_requires_a_bound_vault_without_ambient_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ambient_root = Path(temporary) / "ambient-vault"
            (ambient_root / "memories").mkdir(parents=True)
            error = io.StringIO()
            original_cwd = Path.cwd()
            try:
                os.chdir(ambient_root)
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    mcp_config(["--client", "generic"])
            finally:
                os.chdir(original_cwd)

        self.assertEqual(raised.exception.code, 2)
        root_resolver.assert_not_called()
        self.assertIn("runtime vault binding requires", error.getvalue())

    def test_mcp_config_accepts_explicit_checkout_descendant_bindings(self) -> None:
        root = ROOT / "vault-template"
        bindings = (
            ("argument", ["--client", "generic", "--root", str(root)], ""),
            ("environment", ["--client", "generic"], str(root)),
        )
        for label, argv, environment_root in bindings:
            with self.subTest(binding=label):
                output = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                    redirect_stdout(output),
                ):
                    self.assertEqual(mcp_config(argv), 0)

                config = json.loads(output.getvalue())
                self.assertEqual(Path(config["env"]["AI_DEMEMORY_ROOT"]), root.resolve())

    def test_mcp_config_accepts_an_environment_bound_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": str(root)}),
                redirect_stdout(output),
            ):
                exit_code = mcp_config(["--client", "codex"])

        self.assertEqual(exit_code, 0)
        config = tomllib.loads(output.getvalue())["mcp_servers"]["ai-dememory"]
        self.assertEqual(Path(config["env"]["AI_DEMEMORY_ROOT"]), root.resolve())

    def test_setup_and_onboarding_require_bound_roots_without_discovery(self) -> None:
        invocations = (
            ("setup plan", ["setup", "plan", "--client", "codex", "--json"]),
            ("setup wizard", ["setup", "wizard", "--json"]),
            ("onboard", ["onboard", "--json"]),
        )
        for label, argv in invocations:
            with self.subTest(command=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                root_resolver.assert_not_called()
                self.assertIn("runtime vault binding requires", error.getvalue())

    def test_parser_owned_mutating_commands_reject_ambient_tool_checkout_roots(self) -> None:
        invocations = (
            (
                "providers configure",
                ["providers", "configure", "codex", "--path", str(ROOT)],
            ),
            (
                "providers import",
                ["providers", "import", "codex", "--path", str(ROOT)],
            ),
            (
                "providers capture",
                ["providers", "capture", "text", "--text", "Review candidate."],
            ),
            ("import chats", ["import-chats", "codex", "--path", str(ROOT)]),
            ("capture", ["capture", "text", "--text", "Review candidate."]),
            ("schedule", ["schedule", "setup"]),
            (
                "schedule with a global command option",
                ["schedule", "--command", "ai-dememory", "setup"],
            ),
            ("schedule status", ["schedule", "status"]),
        )
        roots = (
            ROOT,
            ROOT / "vault-template",
            ROOT / "ai_dememory_tool" / "templates" / "vault",
        )
        for label, argv in invocations:
            for root in roots:
                with self.subTest(command=label, root=root):
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                        patch("ai_dememory_tool.cli.find_memory_root", return_value=root) as root_resolver,
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        cli_main(argv)

                    self.assertEqual(raised.exception.code, 2)
                    root_resolver.assert_not_called()
                    self.assertIn("runtime vault binding requires", error.getvalue())

    def test_maintenance_commands_require_bound_roots_without_discovery(self) -> None:
        invocations = (
            ("status", ["maintenance", "status", "--json"]),
            ("real run", ["maintenance", "run"]),
            ("dry run", ["maintenance", "run", "--dry-run", "--json"]),
            (
                "supervised run",
                ["maintenance", "run", "--timeout-seconds", "300", "--json"],
            ),
        )
        for label, argv in invocations:
            with self.subTest(command=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                root_resolver.assert_not_called()
                self.assertIn("runtime vault binding requires", error.getvalue())

    def test_parser_owned_preview_commands_reject_ambient_tool_checkout_roots(self) -> None:
        invocations = (
            ("providers plan", ["providers", "plan", "--json"]),
            (
                "providers configure preview",
                ["providers", "configure", "codex", "--path", str(ROOT), "--dry-run"],
            ),
            ("schedule plan", ["schedule", "plan", "--json"]),
            ("schedule cron", ["schedule", "cron", "--json"]),
            ("schedule setup preview", ["schedule", "setup", "--dry-run"]),
            ("schedule install preview", ["schedule", "install", "--dry-run"]),
        )
        for label, argv in invocations:
            with self.subTest(command=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root", return_value=ROOT) as root_resolver,
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                root_resolver.assert_not_called()
                self.assertIn("runtime vault binding requires", error.getvalue())

    def test_setup_and_onboarding_accept_deliberate_bindings(self) -> None:
        checkout_root = ROOT / "vault-template"
        bindings = (
            ("argument", ["setup", "--root", str(checkout_root), "plan", "--json"], ""),
            ("environment", ["setup", "plan", "--json"], str(checkout_root)),
        )
        for label, argv, environment_root in bindings:
            with self.subTest(binding=label):
                output = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                    redirect_stdout(output),
                ):
                    self.assertEqual(cli_main(argv), 0)

                self.assertEqual(Path(json.loads(output.getvalue())["root"]), checkout_root.resolve())

        onboarding_output = io.StringIO()
        with (
            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
            redirect_stdout(onboarding_output),
        ):
            self.assertEqual(
                cli_main(
                    [
                        "onboard",
                        "--root",
                        str(checkout_root),
                        "--reviewed-by",
                        "Unit Test",
                        "--value",
                        "Prefer safe work.",
                        "--preference",
                        "Run narrow tests first.",
                        "--recommendation",
                        "Recall reviewed memory.",
                        "--json",
                    ]
                ),
                0,
            )

        self.assertEqual(
            Path(json.loads(onboarding_output.getvalue())["root"]),
            checkout_root.resolve(),
        )

        for label, argv in (
            ("setup", ["setup", "plan", "--json"]),
            ("onboard", ["onboard", "--json"]),
        ):
            with self.subTest(command=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                root_resolver.assert_not_called()
                self.assertIn("runtime vault binding requires", error.getvalue())

    def test_direct_setup_and_onboarding_fail_without_a_runtime_vault_binding(self) -> None:
        for label, target, argv, expected_message in (
            (
                "setup plan",
                setup_plan_main,
                ["plan", "--client", "codex", "--json"],
                "runtime vault binding requires",
            ),
            (
                "setup plan with empty root",
                setup_plan_main,
                ["--root=", "plan", "--client", "codex", "--json"],
                "--root requires a non-empty vault path",
            ),
            (
                "setup health",
                setup_plan_main,
                ["health", "--json"],
                "runtime vault binding requires",
            ),
            (
                "onboarding",
                onboarding_main,
                ["--json"],
                "runtime vault binding requires",
            ),
            (
                "onboarding with empty root",
                onboarding_main,
                ["--root=", "--json"],
                "--root requires a non-empty vault path",
            ),
        ):
            for environment_root, environment_message in (
                ("", expected_message),
                (" ", "AI_DEMEMORY_ROOT requires a non-empty vault path"),
            ):
                with self.subTest(entrypoint=label, environment_root=repr(environment_root)):
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                        redirect_stdout(output),
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        target(argv)

                    self.assertEqual(raised.exception.code, 2)
                    self.assertEqual(output.getvalue(), "")
                    message = (
                        expected_message
                        if any(argument == "--root" or argument.startswith("--root=") for argument in argv)
                        else environment_message
                    )
                    self.assertIn(message, error.getvalue())

    def test_setup_and_onboarding_reject_relative_bindings_before_discovery(self) -> None:
        invocations = (
            ("global setup root", ["--root", ".", "setup", "plan", "--json"], ""),
            ("post-command setup root", ["setup", "--root", ".", "plan", "--json"], ""),
            ("environment setup root", ["setup", "plan", "--json"], "."),
            ("global onboard root", ["--root", ".", "onboard", "--json"], ""),
            ("post-command onboard root", ["onboard", "--root", ".", "--json"], ""),
            ("environment onboard root", ["onboard", "--json"], "."),
        )
        for label, argv, environment_root in invocations:
            with self.subTest(binding=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                root_resolver.assert_not_called()
                self.assertIn("requires an absolute vault path", error.getvalue())

    def test_setup_and_onboarding_explicit_roots_win_malformed_environment(self) -> None:
        onboarding_arguments = [
            "--reviewed-by",
            "Unit Test",
            "--value",
            "Prefer safe work.",
            "--preference",
            "Run narrow tests first.",
            "--recommendation",
            "Recall reviewed memory.",
            "--json",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            invocations = (
                ("global setup root", ["--root", str(root), "setup", "plan", "--json"]),
                ("post-command setup root", ["setup", "--root", str(root), "plan", "--json"]),
                ("post-command onboard root", ["onboard", "--root", str(root), *onboarding_arguments]),
            )
            for label, argv in invocations:
                with self.subTest(binding=label):
                    output = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": " \t"}),
                        patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                        redirect_stdout(output),
                    ):
                        self.assertEqual(cli_main(argv), 0)

                    root_resolver.assert_not_called()
                    self.assertEqual(Path(json.loads(output.getvalue())["root"]), root.resolve())

    def test_direct_setup_and_onboarding_reject_relative_runtime_bindings(self) -> None:
        invocations = (
            ("setup explicit", setup_plan_main, ["--root", ".", "plan", "--json"], "C:/vault"),
            ("setup environment", setup_plan_main, ["plan", "--json"], "."),
            ("onboard explicit", onboarding_main, ["--root", ".", "--json"], "C:/vault"),
            ("onboard environment", onboarding_main, ["--json"], "."),
        )
        for label, target, argv, environment_root in invocations:
            with self.subTest(binding=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    target(argv)

                self.assertEqual(raised.exception.code, 2)
                self.assertIn("requires an absolute vault path", error.getvalue())

    def test_maintenance_commands_reject_relative_bindings_before_work(self) -> None:
        command_forms = (
            ("status", ["status", "--json"]),
            ("real run", ["run"]),
            ("dry run", ["run", "--dry-run", "--json"]),
        )
        for command_label, command_argv in command_forms:
            invocations = (
                (
                    "global root",
                    ["--root", ".", "maintenance", *command_argv],
                    "",
                ),
                (
                    "post-command root",
                    ["maintenance", "--root", ".", *command_argv],
                    "",
                ),
                ("environment root", ["maintenance", *command_argv], "."),
            )
            for binding_label, argv, environment_root in invocations:
                with self.subTest(command=command_label, binding=binding_label, entrypoint="unified"):
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                        patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                        patch("ai_dememory_tool.admin.maintenance.maintenance_status") as status,
                        patch("ai_dememory_tool.admin.maintenance.dry_run_maintenance") as dry_run,
                        patch("ai_dememory_tool.admin.maintenance.run_maintenance") as run,
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        cli_main(argv)

                    self.assertEqual(raised.exception.code, 2)
                    root_resolver.assert_not_called()
                    self.assertIn("requires an absolute vault path", error.getvalue())
                    status.assert_not_called()
                    dry_run.assert_not_called()
                    run.assert_not_called()

            direct_invocations = (
                ("explicit root", ["--root", ".", *command_argv], ""),
                ("environment root", command_argv, "."),
            )
            for binding_label, argv, environment_root in direct_invocations:
                with self.subTest(command=command_label, binding=binding_label, entrypoint="direct"):
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                        patch("maintenance.maintenance_status") as status,
                        patch("maintenance.dry_run_maintenance") as dry_run,
                        patch("maintenance.run_maintenance") as run,
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        maintenance_main(argv)

                    self.assertEqual(raised.exception.code, 2)
                    self.assertIn("requires an absolute vault path", error.getvalue())
                    status.assert_not_called()
                    dry_run.assert_not_called()
                    run.assert_not_called()

    def test_maintenance_run_explicit_bindings_override_malformed_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "explicit-vault"
            copy_template_tree(root)
            invocations = (
                (
                    "global root",
                    ["--root", str(root), "maintenance", "run", "--dry-run", "--json"],
                ),
                (
                    "post-command root",
                    ["maintenance", "--root", str(root), "run", "--dry-run", "--json"],
                ),
            )
            for binding_label, argv in invocations:
                with self.subTest(binding=binding_label):
                    output = io.StringIO()
                    preview = {"dry_run": True, "binding": binding_label}
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": " \t"}),
                        patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                        patch(
                            "ai_dememory_tool.admin.maintenance.dry_run_maintenance",
                            return_value=preview,
                        ) as dry_run,
                        redirect_stdout(output),
                    ):
                        self.assertEqual(cli_main(argv), 0)

                    root_resolver.assert_not_called()
                    self.assertEqual(dry_run.call_args.args[0], root.resolve())
                    self.assertEqual(json.loads(output.getvalue()), preview)

            direct_output = io.StringIO()
            direct_preview = {"dry_run": True, "binding": "direct"}
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": " \t"}),
                patch("maintenance.dry_run_maintenance", return_value=direct_preview) as dry_run,
                redirect_stdout(direct_output),
            ):
                self.assertEqual(
                    maintenance_main(
                        ["--root", str(root), "run", "--dry-run", "--json"]
                    ),
                    0,
                )

            self.assertEqual(dry_run.call_args.args[0], root.resolve())
            self.assertEqual(json.loads(direct_output.getvalue()), direct_preview)

    def test_unified_maintenance_parses_invalid_grammar_before_root_resolution(self) -> None:
        invalid_commands = (
            ["--root", r"\\attacker\share", "maintenance", "status", "--bogus"],
            ["maintenance", "status", "--root", r"\\attacker\share"],
            ["maintenance", "--ro", r"\\attacker\share", "status"],
            ["--root=", "maintenance", "status"],
            ["maintenance", "--root=", "status"],
            [
                "--root",
                "C:/vault-a",
                "maintenance",
                "--root",
                "C:/vault-b",
                "status",
            ],
        )
        for argv in invalid_commands:
            with self.subTest(argv=argv):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                    patch("ai_dememory_tool.cli.resolve_runtime_vault") as wrapper_resolver,
                    patch(
                        "ai_dememory_tool.admin.maintenance.resolve_runtime_vault"
                    ) as maintenance_resolver,
                    patch("ai_dememory_tool.admin.maintenance.maintenance_status") as status,
                    redirect_stderr(error),
                ):
                    try:
                        exit_code = cli_main(argv)
                    except SystemExit as exc:
                        exit_code = int(exc.code)

                self.assertEqual(exit_code, 2)
                self.assertTrue(error.getvalue())
                root_discovery.assert_not_called()
                wrapper_resolver.assert_not_called()
                maintenance_resolver.assert_not_called()
                status.assert_not_called()

    def test_direct_provider_commands_fail_without_a_vault_binding(self) -> None:
        invocations = (
            (
                "provider configure",
                provider_main,
                ["configure", "codex", "--path", str(ROOT)],
                "provider_import.load_config",
            ),
            (
                "provider plan",
                provider_main,
                ["plan", "--json"],
                "provider_import.load_config",
            ),
            (
                "provider configure preview",
                provider_main,
                ["configure", "codex", "--path", str(ROOT), "--dry-run", "--json"],
                "provider_import.load_config",
            ),
            (
                "provider import",
                provider_main,
                ["import", "codex"],
                "provider_import.load_config",
            ),
            (
                "provider capture",
                provider_main,
                ["capture", "text", "--text", "Review candidate."],
                "provider_import.load_config",
            ),
        )
        for label, target, argv, resolver in invocations:
            with self.subTest(entrypoint=label):
                for environment_root in ("", " "):
                    with self.subTest(environment_root=repr(environment_root)):
                        output = io.StringIO()
                        error = io.StringIO()
                        with (
                            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                            patch(resolver) as root_resolver,
                            redirect_stdout(output),
                            redirect_stderr(error),
                            self.assertRaises(SystemExit) as raised,
                        ):
                            target(argv)

                        self.assertEqual(raised.exception.code, 2)
                        self.assertEqual(output.getvalue(), "")
                        root_resolver.assert_not_called()
                        expected_message = (
                            "runtime vault binding requires"
                            if environment_root == ""
                            else "AI_DEMEMORY_ROOT requires a non-empty vault path"
                        )
                        self.assertIn(expected_message, error.getvalue())

    def test_direct_schedule_commands_require_binding_without_discovery(self) -> None:
        commands = (
            ("plan", ["plan", "--json"]),
            ("cron", ["cron", "--json"]),
            ("setup", ["setup", "--json"]),
            ("setup dry run", ["setup", "--dry-run", "--json"]),
            ("install", ["install", "--json"]),
            ("install dry run", ["install", "--dry-run", "--json"]),
            ("status", ["status", "--json"]),
            ("status dry run", ["status", "--dry-run", "--json"]),
            ("remove", ["remove", "--json"]),
            ("remove dry run", ["remove", "--dry-run", "--json"]),
        )
        for label, argv in commands:
            for environment_root, expected_message in (
                ("", "runtime vault binding requires"),
                (" ", "AI_DEMEMORY_ROOT requires a non-empty vault path"),
            ):
                with self.subTest(command=label, environment_root=repr(environment_root)):
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                        patch("memorylib.repo_root") as legacy_root,
                        patch(
                            "schedule_memory.resolve_runtime_vault",
                            wraps=resolve_runtime_vault,
                        ) as binding_resolver,
                        redirect_stdout(output),
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        schedule_main(argv)

                    self.assertEqual(raised.exception.code, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertIn(expected_message, error.getvalue())
                    binding_resolver.assert_called_once_with(None)
                    legacy_root.assert_not_called()

    def test_schedule_lock_reentry_keeps_the_single_resolved_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first_root = base / "first"
            changed_default = base / "changed-default"
            copy_template_tree(first_root)
            copy_template_tree(changed_default)
            first_binding = resolve_runtime_vault(str(first_root))
            changed_binding = resolve_runtime_vault(str(changed_default))
            error = io.StringIO()

            with patch(
                "schedule_memory.resolve_runtime_vault",
                side_effect=[first_binding, changed_binding],
            ) as resolver, redirect_stderr(error):
                exit_code = schedule_main(
                    ["--root", str(first_root), "status", "--platform", "windows"]
                )

            self.assertEqual(exit_code, 2)
            resolver.assert_called_once_with(str(first_root))
            self.assertTrue((first_root / SCHEDULE_OPERATION_LOCK_NAME).is_file())
            self.assertFalse((changed_default / SCHEDULE_OPERATION_LOCK_NAME).exists())

    def test_unified_schedule_commands_require_binding_without_wrapper_discovery(self) -> None:
        commands = (
            ["schedule", "plan", "--json"],
            ["schedule", "cron", "--json"],
            ["schedule", "setup", "--dry-run", "--json"],
            ["schedule", "install", "--dry-run", "--json"],
            ["schedule", "status", "--dry-run", "--json"],
            ["schedule", "remove", "--dry-run", "--json"],
        )
        for argv in commands:
            with self.subTest(command=argv[1]):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                    patch(
                        "ai_dememory_tool.admin.schedule_memory.resolve_runtime_vault",
                        wraps=resolve_runtime_vault,
                    ) as binding_resolver,
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                self.assertIn("runtime vault binding requires", error.getvalue())
                binding_resolver.assert_called_once_with(None)
                root_discovery.assert_not_called()

    def test_schedule_saved_default_and_binding_precedence_are_identical_direct_and_unified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config_home = base / "config-home"
            default_root = base / "default-vault"
            environment_root = base / "environment-vault"
            explicit_root = base / "explicit-vault"
            for root in (default_root, environment_root, explicit_root):
                copy_template_tree(root)
            saved_config_home = os.environ.get("AI_DEMEMORY_CONFIG_HOME")
            save_default_vault(
                default_root,
                environ={
                    "AI_DEMEMORY_CONFIG_HOME": str(config_home),
                    "AI_DEMEMORY_ROOT": "",
                },
            )

            cases = (
                ("default", "", [], default_root.resolve()),
                ("environment", str(environment_root), [], environment_root.resolve()),
                (
                    "argument",
                    str(environment_root),
                    ["--root", str(explicit_root)],
                    explicit_root.resolve(),
                ),
            )
            for binding, environment_value, root_args, expected_root in cases:
                entrypoints = [
                    (
                        "direct",
                        schedule_main,
                        [*root_args, "plan", "--platform", "windows", "--json"],
                    ),
                    (
                        "unified",
                        cli_main,
                        ["schedule", *root_args, "plan", "--platform", "windows", "--json"],
                    ),
                ]
                if root_args:
                    entrypoints.append(
                        (
                            "unified global root",
                            cli_main,
                            [*root_args, "schedule", "plan", "--platform", "windows", "--json"],
                        )
                    )
                for entrypoint, target, argv in entrypoints:
                    with self.subTest(binding=binding, entrypoint=entrypoint):
                        output = io.StringIO()
                        with (
                            patch.dict(
                                os.environ,
                                {
                                    "AI_DEMEMORY_CONFIG_HOME": str(config_home),
                                    "AI_DEMEMORY_ROOT": environment_value,
                                },
                            ),
                            patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                            redirect_stdout(output),
                        ):
                            self.assertEqual(target(argv), 0)

                        payload = json.loads(output.getvalue())
                        self.assertEqual(Path(payload["root"]), expected_root)
                        self.assertEqual(
                            payload["commands"],
                            schedule_plan(
                                expected_root,
                                target_platform="windows",
                            )["commands"],
                        )
                        root_discovery.assert_not_called()

            self.assertEqual(
                os.environ.get("AI_DEMEMORY_CONFIG_HOME"),
                saved_config_home,
            )

    def test_schedule_doctor_is_rootless_direct_and_unified(self) -> None:
        for entrypoint, target, argv, resolver in (
            (
                "direct",
                schedule_main,
                ["doctor", "--platform", "windows", "--json"],
                "schedule_memory.resolve_runtime_vault",
            ),
            (
                "unified",
                cli_main,
                ["schedule", "doctor", "--platform", "windows", "--json"],
                "ai_dememory_tool.admin.schedule_memory.resolve_runtime_vault",
            ),
        ):
            with self.subTest(entrypoint=entrypoint):
                output = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": " \t"}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                    patch(resolver) as binding_resolver,
                    patch("shutil.which", return_value=None),
                    redirect_stdout(output),
                ):
                    self.assertEqual(target(argv), 0)

                result = json.loads(output.getvalue())
                self.assertEqual(result["platform"], "windows")
                self.assertFalse(result["mutates_system"])
                binding_resolver.assert_not_called()
                root_discovery.assert_not_called()

    def test_unified_schedule_parses_invalid_grammar_before_any_root_resolution(self) -> None:
        invalid_commands = (
            ["--root", r"\\attacker\share", "schedule", "plan", "--bogus"],
            ["schedule", "plan", "--root", r"\\attacker\share"],
            [
                "--root",
                "C:/vault-a",
                "schedule",
                "--root",
                "C:/vault-b",
                "plan",
            ],
        )
        for argv in invalid_commands:
            with self.subTest(argv=argv):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                    patch("ai_dememory_tool.cli.resolve_runtime_vault") as wrapper_resolver,
                    patch(
                        "ai_dememory_tool.admin.schedule_memory.resolve_runtime_vault"
                    ) as schedule_resolver,
                    redirect_stderr(error),
                ):
                    try:
                        exit_code = cli_main(argv)
                    except SystemExit as exc:
                        exit_code = int(exc.code)

                self.assertEqual(exit_code, 2)
                self.assertTrue(error.getvalue())
                root_discovery.assert_not_called()
                wrapper_resolver.assert_not_called()
                schedule_resolver.assert_not_called()

    def test_unified_provider_commands_require_binding_without_discovery(self) -> None:
        commands = (
            ("providers plan", ["providers", "plan", "--json"]),
            ("import-chats alias", ["import-chats", "codex", "--dry-run", "--json"]),
            ("capture alias", ["capture", "text", "--text", "Reviewed candidate.", "--json"]),
        )
        for label, argv in commands:
            with self.subTest(command=label):
                output = io.StringIO()
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    redirect_stdout(output),
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(output.getvalue(), "")
                self.assertIn("runtime vault binding requires", error.getvalue())
                root_resolver.assert_not_called()

    def test_unified_provider_arguments_are_parsed_before_path_resolution(self) -> None:
        invalid_commands = (
            (
                "invalid provider option with UNC global root",
                ["--root", r"\\attacker\share", "providers", "plan", "--bogus"],
            ),
            (
                "trailing root is not promoted",
                [
                    "providers",
                    "configure",
                    "codex",
                    "--path",
                    "C:/provider",
                    "--dry-run",
                    "--root",
                    r"\\attacker\share",
                ],
            ),
            (
                "end of options root is not promoted",
                ["providers", "plan", "--", "--root", r"\\attacker\share"],
            ),
        )
        for label, argv in invalid_commands:
            with self.subTest(command=label):
                output = io.StringIO()
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    patch("ai_dememory_tool.cli.resolve_runtime_vault") as cli_binding_resolver,
                    patch(
                        "ai_dememory_tool.admin.provider_import.resolve_runtime_vault"
                    ) as binding_resolver,
                    redirect_stdout(output),
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(output.getvalue(), "")
                self.assertIn("unrecognized arguments", error.getvalue())
                root_resolver.assert_not_called()
                cli_binding_resolver.assert_not_called()
                binding_resolver.assert_not_called()

    def test_unified_provider_bindings_reach_valid_commands_without_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "explicit-vault"
            copy_template_tree(root)
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": str(root)}),
                patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                patch(
                    "ai_dememory_tool.admin.provider_import.provider_setup_plan",
                    return_value={"providers": []},
                ) as plan,
                redirect_stdout(output),
            ):
                self.assertEqual(cli_main(["providers", "plan", "--json"]), 0)

            root_resolver.assert_not_called()
            self.assertEqual(plan.call_args.args[0], root.resolve())
            self.assertEqual(json.loads(output.getvalue()), {"providers": []})

            output = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": "."}),
                patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                patch(
                    "ai_dememory_tool.admin.provider_import.provider_setup_plan",
                    return_value={"providers": []},
                ) as plan,
                redirect_stdout(output),
            ):
                self.assertEqual(
                    cli_main(["providers", "--root", str(root), "plan", "--json"]),
                    0,
                )

            root_resolver.assert_not_called()
            self.assertEqual(plan.call_args.args[0], root.resolve())

    def test_provider_static_help_remains_rootless_before_discovery(self) -> None:
        direct_commands = (
            ("plan", ["plan", "--help"]),
            ("capture", ["capture", "--help"]),
        )
        for command_label, argv in direct_commands:
            with self.subTest(entrypoint=f"direct {command_label}"):
                output = io.StringIO()
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch.object(
                        Path,
                        "home",
                        side_effect=AssertionError("static help resolved provider home"),
                    ),
                    patch("provider_import.resolve_runtime_vault") as root_resolver,
                    patch("provider_import.detect_local_providers") as detect,
                    redirect_stdout(output),
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    provider_main(argv)

                self.assertEqual(raised.exception.code, 0)
                self.assertIn("usage:", output.getvalue())
                self.assertIn(
                    "Resolution order: --root, AI_DEMEMORY_ROOT, then a saved local default",
                    " ".join(output.getvalue().split()),
                )
                self.assertIn(
                    "ai-dememory vault use <absolute-vault-path>",
                    " ".join(output.getvalue().split()),
                )
                self.assertIn(
                    "uses the working directory to discover a vault",
                    " ".join(output.getvalue().split()),
                )
                self.assertEqual(error.getvalue(), "")
                root_resolver.assert_not_called()
                detect.assert_not_called()

        unified_commands = (
            ("providers plan", ["providers", "plan", "--help"]),
            ("capture alias", ["capture", "--help"]),
        )
        for command_label, argv in unified_commands:
            with self.subTest(entrypoint=f"unified {command_label}"):
                output = io.StringIO()
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch.object(
                        Path,
                        "home",
                        side_effect=AssertionError("static help resolved provider home"),
                    ),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                    redirect_stdout(output),
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    cli_main(argv)

                self.assertEqual(raised.exception.code, 0)
                self.assertIn("usage:", output.getvalue())
                self.assertIn(
                    "Resolution order: --root, AI_DEMEMORY_ROOT, then a saved local default",
                    " ".join(output.getvalue().split()),
                )
                self.assertIn(
                    "ai-dememory vault use <absolute-vault-path>",
                    " ".join(output.getvalue().split()),
                )
                self.assertIn(
                    "uses the working directory to discover a vault",
                    " ".join(output.getvalue().split()),
                )
                self.assertEqual(error.getvalue(), "")
                root_resolver.assert_not_called()

        for label, target, argv in (
            ("direct providers", provider_main, ["--help"]),
            ("unified providers", cli_main, ["providers", "--help"]),
        ):
            with self.subTest(entrypoint=label):
                output = io.StringIO()
                error = io.StringIO()
                with (
                    patch.object(
                        Path,
                        "home",
                        side_effect=AssertionError("static help resolved provider home"),
                    ),
                    patch("provider_import.resolve_runtime_vault") as direct_resolver,
                    patch(
                        "ai_dememory_tool.admin.provider_import.resolve_runtime_vault"
                    ) as packaged_resolver,
                    patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                    redirect_stdout(output),
                    redirect_stderr(error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    target(argv)

                self.assertEqual(raised.exception.code, 0)
                self.assertIn(
                    "Legacy --root is accepted for compatibility but ignored by `detect`",
                    " ".join(output.getvalue().split()),
                )
                self.assertEqual(error.getvalue(), "")
                direct_resolver.assert_not_called()
                packaged_resolver.assert_not_called()
                root_discovery.assert_not_called()

    def test_provider_detect_is_invariant_to_vault_selectors_config_and_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_a = base / "vault-a"
            vault_b = base / "vault-b"
            cwd_a = base / "cwd-a"
            cwd_b = base / "cwd-b"
            host = base / "host"
            selector_home = base / "selector-home"
            for path in (vault_a, vault_b, cwd_a, cwd_b, host, selector_home):
                path.mkdir()
            vault_a_config = vault_a / ".ai-dememory.toml"
            vault_a_config.write_text(
                '[providers.codex]\nenabled = true\npath = "vault-config-canary"\n',
                encoding="utf-8",
            )
            vault_b_config = vault_b / ".ai-dememory.toml"
            vault_b_config.write_bytes(b"\xff")
            selector = selector_home / "default-vault.json"
            selector.write_text("{invalid-selector", encoding="utf-8")
            codex_path = host / "codex"
            codex_path.mkdir()
            local_paths = {
                "codex": [codex_path],
                "claude": [host / "claude"],
                "chatgpt": [host / "conversations.json"],
                "cursor": [host / "cursor"],
                "windsurf": [host / "windsurf"],
            }
            protected_bytes = {
                vault_a_config: vault_a_config.read_bytes(),
                vault_b_config: vault_b_config.read_bytes(),
                selector: selector.read_bytes(),
            }
            network_root = r"\\server\share\vault-root-canary"
            invocations = (
                ("direct unbound", provider_main, ["detect", "--json"], cwd_a),
                (
                    "direct legacy network root",
                    provider_main,
                    ["--root", network_root, "detect", "--json"],
                    cwd_b,
                ),
                (
                    "unified global root",
                    cli_main,
                    ["--root", str(vault_a), "providers", "detect", "--json"],
                    cwd_a,
                ),
                (
                    "unified provider root",
                    cli_main,
                    ["providers", "--root", str(vault_b), "detect", "--json"],
                    cwd_b,
                ),
            )
            payloads: list[list[dict[str, object]]] = []
            previous_cwd = Path.cwd()
            with ExitStack() as stack:
                stack.enter_context(
                    patch.dict(
                        os.environ,
                        {
                            "AI_DEMEMORY_ROOT": str(vault_b),
                            "AI_DEMEMORY_CONFIG_HOME": str(selector_home),
                        },
                    )
                )
                stack.enter_context(
                    patch("provider_import.default_provider_paths", return_value=local_paths)
                )
                stack.enter_context(
                    patch(
                        "ai_dememory_tool.admin.provider_import.default_provider_paths",
                        return_value=local_paths,
                    )
                )
                boundaries = (
                    stack.enter_context(
                        patch(
                            "provider_import.resolve_runtime_vault",
                            side_effect=AssertionError("rootless detect resolved a vault"),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "ai_dememory_tool.admin.provider_import.resolve_runtime_vault",
                            side_effect=AssertionError(
                                "packaged rootless detect resolved a vault"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "provider_import.load_config",
                            side_effect=AssertionError("rootless detect read vault config"),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "ai_dememory_tool.admin.provider_import.load_config",
                            side_effect=AssertionError(
                                "packaged rootless detect read vault config"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "provider_import.provider_config",
                            side_effect=AssertionError(
                                "rootless detect requested provider config"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "ai_dememory_tool.admin.provider_import.provider_config",
                            side_effect=AssertionError(
                                "packaged rootless detect requested provider config"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "ai_dememory_tool.cli.load_default_vault",
                            side_effect=AssertionError(
                                "rootless detect read the saved selector"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "ai_dememory_tool.cli.find_memory_root",
                            side_effect=AssertionError("rootless detect discovered the CWD"),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "provider_import.read_provider_file",
                            side_effect=AssertionError(
                                "rootless detect read provider content"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch(
                            "ai_dememory_tool.admin.provider_import.read_provider_file",
                            side_effect=AssertionError(
                                "packaged rootless detect read provider content"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch.object(
                            Path,
                            "open",
                            side_effect=AssertionError(
                                "rootless detect opened provider content"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch.object(
                            Path,
                            "read_bytes",
                            side_effect=AssertionError(
                                "rootless detect read provider bytes"
                            ),
                        )
                    ),
                    stack.enter_context(
                        patch.object(
                            Path,
                            "read_text",
                            side_effect=AssertionError(
                                "rootless detect read provider text"
                            ),
                        )
                    ),
                )
                try:
                    for label, target, argv, cwd in invocations:
                        with self.subTest(entrypoint=label):
                            os.chdir(cwd)
                            output = io.StringIO()
                            with redirect_stdout(output):
                                self.assertEqual(target(argv), 0)
                            self.assertNotIn(network_root, output.getvalue())
                            payloads.append(json.loads(output.getvalue()))
                finally:
                    os.chdir(previous_cwd)

            for boundary in boundaries:
                boundary.assert_not_called()
            for path, expected in protected_bytes.items():
                self.assertEqual(path.read_bytes(), expected)

        self.assertTrue(payloads)
        self.assertTrue(all(payload == payloads[0] for payload in payloads[1:]))
        self.assertEqual(
            {item["name"] for item in payloads[0]},
            {"chatgpt", "claude", "codex", "cursor", "windsurf"},
        )
        rows = {item["name"]: item for item in payloads[0]}
        self.assertEqual(rows["codex"]["path"], str(codex_path))
        self.assertTrue(rows["codex"]["exists"])
        for name in ("chatgpt", "claude", "cursor", "windsurf"):
            self.assertEqual(rows[name]["path"], str(local_paths[name][0]))
            self.assertFalse(rows[name]["exists"])
        for item in payloads[0]:
            self.assertEqual(
                set(item),
                {"name", "path", "exists", "configured", "enabled"},
            )
            self.assertTrue(Path(str(item["path"])).is_absolute())
            self.assertIsInstance(item["exists"], bool)
            self.assertFalse(item["configured"])
            self.assertFalse(item["enabled"])

    def test_provider_detect_human_output_marks_vault_config_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            local_paths = {
                name: [base / name]
                for name in ("codex", "claude", "chatgpt", "cursor", "windsurf")
            }
            output = io.StringIO()
            network_root = r"\\server\share\human-output-root-canary"
            with (
                patch("provider_import.default_provider_paths", return_value=local_paths),
                patch(
                    "provider_import.resolve_runtime_vault",
                    side_effect=AssertionError("rootless detect resolved a legacy root"),
                ) as root_resolver,
                patch(
                    "provider_import.load_config",
                    side_effect=AssertionError("rootless detect read config"),
                ) as config_reader,
                redirect_stdout(output),
            ):
                self.assertEqual(provider_main(["--root", network_root, "detect"]), 0)

            root_resolver.assert_not_called()
            config_reader.assert_not_called()

        rendered = output.getvalue()
        self.assertEqual(rendered.count("config=n/a"), 5)
        self.assertNotIn("disabled", rendered)
        self.assertNotIn(network_root, rendered)

    def test_provider_detect_rejects_invalid_root_grammar_before_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_a = str((Path(tmp) / "vault-a").resolve())
            root_b = str((Path(tmp) / "vault-b").resolve())
            invocations = (
                (
                    "direct blank",
                    provider_main,
                    ["--root=", "detect", "--json"],
                    "provider_import.detect_local_providers",
                ),
                (
                    "direct duplicate",
                    provider_main,
                    ["--root", root_a, "--root", root_b, "detect", "--json"],
                    "provider_import.detect_local_providers",
                ),
                (
                    "direct misplaced",
                    provider_main,
                    ["detect", "--root", root_a, "--json"],
                    "provider_import.detect_local_providers",
                ),
                (
                    "unified blank",
                    cli_main,
                    ["--root=", "providers", "detect", "--json"],
                    "ai_dememory_tool.admin.provider_import.detect_local_providers",
                ),
                (
                    "unified duplicate",
                    cli_main,
                    ["--root", root_a, "providers", "--root", root_b, "detect", "--json"],
                    "ai_dememory_tool.admin.provider_import.detect_local_providers",
                ),
                (
                    "unified misplaced",
                    cli_main,
                    ["providers", "detect", "--root", root_a, "--json"],
                    "ai_dememory_tool.admin.provider_import.detect_local_providers",
                ),
            )
            for label, target, argv, detector_name in invocations:
                with self.subTest(entrypoint=label):
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch(detector_name) as detector,
                        redirect_stdout(output),
                        redirect_stderr(error),
                    ):
                        try:
                            exit_code = target(argv)
                        except SystemExit as exc:
                            exit_code = int(exc.code)

                    self.assertEqual(exit_code, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertTrue(error.getvalue())
                    detector.assert_not_called()

    def test_provider_detect_rejects_unsafe_home_before_candidate_probe(self) -> None:
        targets = (
            ("direct", provider_main, ["detect", "--json"]),
            ("packaged", cli_main, ["providers", "detect", "--json"]),
        )
        home_cases = (
            ("relative", {"return_value": Path("relative/home")}),
            ("unc", {"return_value": Path("//server/share/home")}),
            (
                "unavailable",
                {"side_effect": RuntimeError("sensitive-home-resolution-canary")},
            ),
        )
        expected_error = (
            "provider home path is unavailable or unsafe "
            "[provider_home_unsafe]\n"
        )
        for entrypoint, target, argv in targets:
            for case, home_behavior in home_cases:
                with self.subTest(entrypoint=entrypoint, home=case):
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch.object(Path, "home", **home_behavior),
                        patch.object(
                            Path,
                            "exists",
                            side_effect=AssertionError(
                                "unsafe home reached a candidate existence probe"
                            ),
                        ) as path_probe,
                        redirect_stdout(output),
                        redirect_stderr(error),
                    ):
                        self.assertEqual(target(argv), 2)

                    self.assertEqual(output.getvalue(), "")
                    self.assertEqual(error.getvalue(), expected_error)
                    self.assertNotIn("sensitive-home-resolution-canary", error.getvalue())
                    path_probe.assert_not_called()

    def test_default_provider_paths_use_platform_native_cwd_invariant_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            cwd_a = base / "cwd-a"
            cwd_b = base / "cwd-b"
            for path in (home, cwd_a, cwd_b):
                path.mkdir()

            windows_missing = default_provider_paths(
                environ={},
                home=home,
                platform="win32",
            )
            windows_blank = default_provider_paths(
                environ={"APPDATA": "  "},
                home=home,
                platform="win32",
            )
            windows_network = default_provider_paths(
                environ={"APPDATA": r"\\server\share\roaming"},
                home=home,
                platform="win32",
            )
            windows_slash_network = default_provider_paths(
                environ={"APPDATA": "//server/share/roaming"},
                home=home,
                platform="win32",
            )
            previous_cwd = Path.cwd()
            windows_relative_results = []
            linux_relative_results = []
            try:
                for cwd in (cwd_a, cwd_b):
                    os.chdir(cwd)
                    windows_relative_results.append(
                        default_provider_paths(
                            environ={"APPDATA": "relative/roaming"},
                            home=home,
                            platform="win32",
                        )
                    )
                    linux_relative_results.append(
                        default_provider_paths(
                            environ={"XDG_CONFIG_HOME": "relative/config"},
                            home=home,
                            platform="linux",
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            windows_config = home / "AppData" / "Roaming"
            custom_windows_config = base / "custom-roaming"
            custom_windows = default_provider_paths(
                environ={"APPDATA": str(custom_windows_config)},
                home=home,
                platform="win32",
            )
            macos = default_provider_paths(
                environ={"APPDATA": str(base / "ignored-windows-config")},
                home=home,
                platform="darwin",
            )
            linux_missing = default_provider_paths(
                environ={},
                home=home,
                platform="linux",
            )
            linux_network = default_provider_paths(
                environ={"XDG_CONFIG_HOME": "//server/share/config"},
                home=home,
                platform="linux",
            )
            linux_unknown_user = default_provider_paths(
                environ={
                    "XDG_CONFIG_HOME": "~ai_dememory_user_that_does_not_exist/config"
                },
                home=home,
                platform="linux",
            )
            custom_linux_config = base / "xdg-config"
            custom_linux = default_provider_paths(
                environ={"XDG_CONFIG_HOME": str(custom_linux_config)},
                home=home,
                platform="linux",
            )

        self.assertEqual(windows_missing, windows_blank)
        self.assertEqual(windows_missing, windows_network)
        self.assertEqual(windows_missing, windows_slash_network)
        self.assertEqual(windows_relative_results, [windows_missing, windows_missing])
        self.assertEqual(
            windows_missing["cursor"],
            [windows_config / "Cursor" / "User"],
        )
        self.assertEqual(
            custom_windows["cursor"],
            [custom_windows_config / "Cursor" / "User"],
        )
        self.assertEqual(
            macos["cursor"],
            [home / "Library" / "Application Support" / "Cursor" / "User"],
        )
        self.assertEqual(linux_missing, linux_network)
        self.assertEqual(linux_missing, linux_unknown_user)
        self.assertEqual(linux_relative_results, [linux_missing, linux_missing])
        self.assertEqual(
            linux_missing["cursor"],
            [home / ".config" / "Cursor" / "User"],
        )
        self.assertEqual(
            custom_linux["cursor"],
            [custom_linux_config / "Cursor" / "User"],
        )
        self.assertTrue(
            all(
                path.is_absolute()
                for candidates in (windows_missing, macos, linux_missing)
                for paths in candidates.values()
                for path in paths
            )
        )

    def test_direct_maintenance_requires_runtime_binding_before_work(self) -> None:
        invocations = (
            ("status", ["status", "--json"]),
            ("real run", ["run"]),
            ("dry run", ["run", "--dry-run", "--json"]),
            ("supervised run", ["run", "--timeout-seconds", "300", "--json"]),
        )
        for label, argv in invocations:
            for environment_root, expected_message in (
                ("", "runtime vault binding requires"),
                (" ", "AI_DEMEMORY_ROOT requires a non-empty vault path"),
            ):
                with self.subTest(command=label, environment_root=repr(environment_root)):
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                        patch("maintenance.maintenance_lock") as lock,
                        patch("maintenance.enabled_providers") as providers,
                        patch("maintenance.import_chats") as provider_import,
                        patch("maintenance.maintenance_status") as status,
                        patch("maintenance.dry_run_maintenance") as dry_run,
                        patch("maintenance.run_maintenance") as run,
                        patch("maintenance.run_supervised_maintenance") as supervised_run,
                        patch("maintenance.run_supervised_process") as child_process,
                        redirect_stdout(output),
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        maintenance_main(argv)

                    self.assertEqual(raised.exception.code, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertIn(expected_message, error.getvalue())
                    for work_boundary in (
                        lock,
                        providers,
                        provider_import,
                        status,
                        dry_run,
                        run,
                        supervised_run,
                        child_process,
                    ):
                        work_boundary.assert_not_called()

    def test_structurally_invalid_selected_vault_stops_before_stateful_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "missing-vault-marker"
            root.mkdir()
            cases = (
                (
                    "mcp stdio",
                    memory_mcp_main,
                    ["--root", str(root), "--stdio"],
                    ("memory_mcp.run_stdio",),
                ),
                (
                    "api socket",
                    api_main,
                    ["--root", str(root), "--host", "127.0.0.1", "--port", "0"],
                    ("http_api.serve",),
                ),
                (
                    "hook config",
                    hook_event_main,
                    ["config", "--root", str(root), "--client", "codex"],
                    ("hook_event.hook_config",),
                ),
                (
                    "setup plan",
                    setup_plan_main,
                    ["--root", str(root), "plan", "--json"],
                    ("setup_plan.setup_plan",),
                ),
                (
                    "provider writer",
                    provider_main,
                    [
                        "--root",
                        str(root),
                        "capture",
                        "text",
                        "--text",
                        "reviewed fixture",
                        "--json",
                    ],
                    ("provider_import.capture_source",),
                ),
                (
                    "maintenance lock provider and child",
                    maintenance_main,
                    ["--root", str(root), "run", "--timeout-seconds", "300", "--json"],
                    (
                        "maintenance.maintenance_lock",
                        "maintenance.enabled_providers",
                        "maintenance.import_chats",
                        "maintenance.run_maintenance",
                        "maintenance.run_supervised_maintenance",
                        "maintenance.run_supervised_process",
                    ),
                ),
                (
                    "schedule lock and writer",
                    schedule_main,
                    ["--root", str(root), "setup", "--json"],
                    (
                        "schedule_memory.vault_operation_lock",
                        "schedule_memory.build_schedule_commands",
                        "schedule_memory.run_install_commands",
                        "schedule_memory.safe_write_text",
                    ),
                ),
            )

            for label, target, argv, boundary_names in cases:
                with self.subTest(surface=label):
                    output = io.StringIO()
                    error = io.StringIO()
                    with ExitStack() as stack:
                        boundaries = [
                            stack.enter_context(patch(boundary_name))
                            for boundary_name in boundary_names
                        ]
                        stack.enter_context(
                            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""})
                        )
                        stack.enter_context(redirect_stdout(output))
                        stack.enter_context(redirect_stderr(error))
                        raised = stack.enter_context(self.assertRaises(SystemExit))
                        target(argv)

                    self.assertEqual(raised.exception.code, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertIn("vault is missing .ai-dememory.toml", error.getvalue())
                    for boundary in boundaries:
                        boundary.assert_not_called()

    def test_structural_validation_leaves_provider_detect_and_help_rootless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            invalid_root = Path(tmp) / "missing-vault-marker"
            invalid_root.mkdir()
            detect_output = io.StringIO()
            with (
                patch("provider_import.resolve_runtime_vault") as resolver,
                patch("provider_import.detect_local_providers", return_value=[]),
                redirect_stdout(detect_output),
            ):
                self.assertEqual(
                    provider_main(
                        ["--root", str(invalid_root), "detect", "--json"]
                    ),
                    0,
                )

            resolver.assert_not_called()
            self.assertEqual(json.loads(detect_output.getvalue()), [])

            help_output = io.StringIO()
            with (
                patch("provider_import.resolve_runtime_vault") as resolver,
                redirect_stdout(help_output),
                self.assertRaises(SystemExit) as raised,
            ):
                provider_main(["--root", str(invalid_root), "plan", "--help"])

            self.assertEqual(raised.exception.code, 0)
            self.assertIn("usage:", help_output.getvalue())
            resolver.assert_not_called()

    def test_maintenance_status_uses_strict_precedence_and_ignores_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            default_root = base / "default-vault"
            environment_root = base / "environment-vault"
            explicit_root = base / "explicit-vault"
            poisoned_cwd = base / "poisoned-cwd-vault"
            for root in (default_root, environment_root, explicit_root, poisoned_cwd):
                copy_template_tree(root)
            save_default_vault(default_root)

            invocations = (
                (
                    "direct default",
                    maintenance_main,
                    ["status", "--json"],
                    "maintenance.maintenance_status",
                    "",
                    default_root,
                ),
                (
                    "direct environment",
                    maintenance_main,
                    ["status", "--json"],
                    "maintenance.maintenance_status",
                    str(environment_root),
                    environment_root,
                ),
                (
                    "direct explicit",
                    maintenance_main,
                    ["--root", str(explicit_root), "status", "--json"],
                    "maintenance.maintenance_status",
                    str(environment_root),
                    explicit_root,
                ),
                (
                    "unified default",
                    cli_main,
                    ["maintenance", "status", "--json"],
                    "ai_dememory_tool.admin.maintenance.maintenance_status",
                    "",
                    default_root,
                ),
                (
                    "unified environment",
                    cli_main,
                    ["maintenance", "status", "--json"],
                    "ai_dememory_tool.admin.maintenance.maintenance_status",
                    str(environment_root),
                    environment_root,
                ),
                (
                    "unified global explicit",
                    cli_main,
                    ["--root", str(explicit_root), "maintenance", "status", "--json"],
                    "ai_dememory_tool.admin.maintenance.maintenance_status",
                    str(environment_root),
                    explicit_root,
                ),
                (
                    "unified post-command explicit",
                    cli_main,
                    ["maintenance", "--root", str(explicit_root), "status", "--json"],
                    "ai_dememory_tool.admin.maintenance.maintenance_status",
                    str(environment_root),
                    explicit_root,
                ),
            )

            original_cwd = Path.cwd()
            try:
                os.chdir(poisoned_cwd)
                for label, target, argv, status_target, configured_root, expected_root in invocations:
                    with self.subTest(entrypoint=label):
                        output = io.StringIO()

                        def status_payload(root: Path) -> dict[str, str]:
                            return {"root": str(root)}

                        with (
                            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": configured_root}),
                            patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                            patch(status_target, side_effect=status_payload) as status,
                            redirect_stdout(output),
                        ):
                            self.assertEqual(target(argv), 0)

                        root_discovery.assert_not_called()
                        status.assert_called_once_with(expected_root.resolve())
                        self.assertEqual(
                            Path(json.loads(output.getvalue())["root"]),
                            expected_root.resolve(),
                        )
            finally:
                os.chdir(original_cwd)

    def test_maintenance_status_help_is_rootless_direct_and_unified(self) -> None:
        invocations = (
            (
                "direct",
                maintenance_main,
                ["status", "--help"],
                "maintenance.resolve_runtime_vault",
            ),
            (
                "unified",
                cli_main,
                ["maintenance", "status", "--help"],
                "ai_dememory_tool.admin.maintenance.resolve_runtime_vault",
            ),
        )
        for label, target, argv, resolver_target in invocations:
            with self.subTest(entrypoint=label):
                output = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": " \t"}),
                    patch("ai_dememory_tool.cli.find_memory_root") as root_discovery,
                    patch(resolver_target) as binding_resolver,
                    redirect_stdout(output),
                    self.assertRaises(SystemExit) as raised,
                ):
                    target(argv)

                self.assertEqual(raised.exception.code, 0)
                self.assertIn("usage:", output.getvalue())
                binding_resolver.assert_not_called()
                root_discovery.assert_not_called()

    def test_maintenance_status_preserves_payload_and_vault_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)

            def snapshot() -> dict[str, tuple[bytes, int]]:
                return {
                    path.relative_to(root).as_posix(): (
                        path.read_bytes(),
                        path.stat().st_mtime_ns,
                    )
                    for path in root.rglob("*")
                    if path.is_file()
                }

            before = snapshot()
            expected = maintenance_status(root.resolve())
            self.assertEqual(snapshot(), before)

            output = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                redirect_stdout(output),
            ):
                self.assertEqual(
                    maintenance_main(
                        ["--root", str(root), "status", "--json"]
                    ),
                    0,
                )

            self.assertEqual(json.loads(output.getvalue()), expected)
            self.assertEqual(snapshot(), before)

    def test_maintenance_status_rejects_invalid_config_without_traceback_or_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            config = root / ".ai-dememory.toml"
            original = b"\xff"
            config.write_bytes(original)
            output = io.StringIO()
            error = io.StringIO()

            with (
                patch("maintenance.artifact_status") as artifacts,
                patch("maintenance.providers_status") as providers,
                patch("maintenance.run_supervised_process") as child_process,
                redirect_stdout(output),
                redirect_stderr(error),
            ):
                exit_code = maintenance_main(["--root", str(root), "status", "--json"])

            self.assertEqual(exit_code, 2)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("valid UTF-8", error.getvalue())
            self.assertNotIn("traceback", error.getvalue().lower())
            self.assertEqual(config.read_bytes(), original)
            artifacts.assert_not_called()
            providers.assert_not_called()
            child_process.assert_not_called()

    def test_provider_config_commands_reject_invalid_config_before_writes(self) -> None:
        invocations = (
            ("plan", ["plan", "--json"]),
            (
                "configure preview",
                ["configure", "codex", "--path", "C:/provider", "--dry-run", "--json"],
            ),
            ("configure", ["configure", "codex", "--path", "C:/provider"]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            config = root / ".ai-dememory.toml"
            canary = "provider-config-value-canary"
            original = f'[providers.codex]\nenabled = "{canary}"\n'.encode("utf-8")

            for label, command in invocations:
                with self.subTest(command=label):
                    config.write_bytes(original)
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch("config_file.safe_write_text") as config_writer,
                        redirect_stdout(output),
                        redirect_stderr(error),
                    ):
                        exit_code = provider_main(["--root", str(root), *command])

                    self.assertEqual(exit_code, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertIn("config error [invalid_type]", error.getvalue())
                    self.assertNotIn(canary, error.getvalue())
                    self.assertNotIn("traceback", error.getvalue().lower())
                    self.assertEqual(config.read_bytes(), original)
                    config_writer.assert_not_called()

    def test_schedule_config_commands_reject_invalid_config_before_host_work(self) -> None:
        invocations = (
            ("plan", ["plan", "--json"]),
            ("cron", ["cron", "--json"]),
            ("status", ["status", "--platform", "linux", "--json"]),
            ("remove", ["remove", "--platform", "linux", "--json"]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            config = root / ".ai-dememory.toml"
            canary = "schedule-config-value-canary"
            original = f'[schedule]\nenabled = "{canary}"\n'.encode("utf-8")

            for label, command in invocations:
                with self.subTest(command=label):
                    config.write_bytes(original)
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch("schedule_memory.run_owned_process") as host_process,
                        patch("schedule_memory.write_platform_schedule_files") as definition_writer,
                        patch("schedule_memory.set_section") as receipt_writer,
                        redirect_stdout(output),
                        redirect_stderr(error),
                    ):
                        exit_code = schedule_main(["--root", str(root), *command])

                    self.assertEqual(exit_code, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertIn("config error [invalid_type]", error.getvalue())
                    self.assertNotIn(canary, error.getvalue())
                    self.assertNotIn("traceback", error.getvalue().lower())
                    self.assertEqual(config.read_bytes(), original)
                    host_process.assert_not_called()
                    definition_writer.assert_not_called()
                    receipt_writer.assert_not_called()

    def test_direct_strict_commands_reject_ambiguous_root_options_before_resolution(self) -> None:
        invocations = (
            (
                "maintenance status",
                maintenance_main,
                ["status", "--json"],
                "maintenance.resolve_runtime_vault",
            ),
            (
                "maintenance run",
                maintenance_main,
                ["run", "--dry-run", "--json"],
                "maintenance.resolve_runtime_vault",
            ),
            (
                "provider detect",
                provider_main,
                ["detect", "--json"],
                "provider_import.detect_local_providers",
            ),
            (
                "provider plan",
                provider_main,
                ["plan", "--json"],
                "provider_import.resolve_runtime_vault",
            ),
            (
                "provider configure",
                provider_main,
                ["configure", "codex", "--path", "C:/provider"],
                "provider_import.resolve_runtime_vault",
            ),
            (
                "provider import",
                provider_main,
                ["import", "codex"],
                "provider_import.resolve_runtime_vault",
            ),
            (
                "provider capture",
                provider_main,
                ["capture", "text", "--text", "Reviewed candidate."],
                "provider_import.resolve_runtime_vault",
            ),
            ("schedule plan", schedule_main, ["plan", "--json"], "schedule_memory.resolve_runtime_vault"),
            ("schedule setup", schedule_main, ["setup"], "schedule_memory.resolve_runtime_vault"),
            ("schedule install", schedule_main, ["install"], "schedule_memory.resolve_runtime_vault"),
            ("schedule status", schedule_main, ["status"], "schedule_memory.resolve_runtime_vault"),
            ("schedule remove", schedule_main, ["remove"], "schedule_memory.resolve_runtime_vault"),
            ("schedule doctor", schedule_main, ["doctor", "--json"], "schedule_memory.resolve_runtime_vault"),
            ("schedule cron", schedule_main, ["cron", "--json"], "schedule_memory.resolve_runtime_vault"),
        )
        invalid_prefixes = (
            # With allow_abbrev=False, the value following --ro cannot become
            # a root binding; argparse rejects it as an invalid command token.
            ("abbreviation", ["--ro", "C:/vault-a"], "invalid choice: 'C:/vault-a'"),
            (
                "separate duplicates",
                ["--root", "C:/vault-a", "--root", "C:/vault-b"],
                "security-sensitive options may be specified at most once: --root",
            ),
            (
                "equals duplicates",
                ["--root=C:/vault-a", "--root=C:/vault-b"],
                "security-sensitive options may be specified at most once: --root",
            ),
            ("empty equals", ["--root="], "--root requires a non-empty vault path"),
            ("equals whitespace", ["--root= "], "--root requires a non-empty vault path"),
            ("whitespace", ["--root", " "], "--root requires a non-empty vault path"),
        )

        for label, target, command, resolver in invocations:
            for kind, prefix, message in invalid_prefixes:
                with self.subTest(entrypoint=label, invalid_root=kind):
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                        patch(resolver) as root_resolver,
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        target([*prefix, *command])

                    self.assertEqual(raised.exception.code, 2)
                    root_resolver.assert_not_called()
                    self.assertIn(message, error.getvalue())

    def test_direct_setup_and_onboarding_accept_explicit_bindings(self) -> None:
        onboarding_arguments = [
            "--reviewed-by",
            "Unit Test",
            "--value",
            "Prefer safe work.",
            "--preference",
            "Run narrow tests first.",
            "--recommendation",
            "Recall reviewed memory.",
            "--json",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            setup_output = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": str(root)}),
                redirect_stdout(setup_output),
            ):
                self.assertEqual(
                    setup_plan_main(["plan", "--client", "codex", "--json"]),
                    0,
                )

            onboarding_outputs: list[io.StringIO] = []
            for label, argv, environment_root in (
                ("argument", ["--root", str(root), *onboarding_arguments], ""),
                ("environment", onboarding_arguments, str(root)),
            ):
                with self.subTest(onboarding_binding=label):
                    output = io.StringIO()
                    onboarding_outputs.append(output)
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                        redirect_stdout(output),
                    ):
                        self.assertEqual(onboarding_main(argv), 0)

            health_output = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": str(root)}),
                patch("setup_plan.setup_health", return_value={"compatible": True}),
                redirect_stdout(health_output),
            ):
                self.assertEqual(setup_plan_main(["health", "--json"]), 0)

        self.assertEqual(Path(json.loads(setup_output.getvalue())["root"]), root.resolve())
        for output in onboarding_outputs:
            self.assertEqual(Path(json.loads(output.getvalue())["root"]), root.resolve())
        self.assertEqual(json.loads(health_output.getvalue()), {"compatible": True})

    def test_empty_root_arguments_reject_before_ambient_vault_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ambient_root = Path(tmp) / "ambient-vault"
            copy_template_tree(ambient_root)
            unified_invocations = (
                (
                    "global equals",
                    ["--root=", "setup", "plan", "--client", "codex", "--json"],
                ),
                (
                    "global whitespace",
                    ["--root", " \t", "setup", "plan", "--client", "codex", "--json"],
                ),
                (
                    "post-command equals",
                    ["setup", "--root=", "plan", "--client", "codex", "--json"],
                ),
                (
                    "post-command whitespace",
                    ["setup", "--root", " \t", "plan", "--client", "codex", "--json"],
                ),
            )
            for label, argv in unified_invocations:
                with self.subTest(entrypoint=f"unified {label}"):
                    output = io.StringIO()
                    error = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": str(ambient_root)}),
                        patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
                        redirect_stdout(output),
                        redirect_stderr(error),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        cli_main(argv)

                    self.assertEqual(raised.exception.code, 2)
                    self.assertEqual(output.getvalue(), "")
                    root_resolver.assert_not_called()
                    self.assertIn("--root requires a non-empty vault path", error.getvalue())

            direct_invocations = (
                (
                    "mcp config",
                    mcp_config,
                    ["--client", "generic"],
                    "ai_dememory_tool.cli.find_memory_root",
                ),
                (
                    "setup plan",
                    setup_plan_main,
                    ["plan", "--client", "codex", "--json"],
                ),
                (
                    "onboarding",
                    onboarding_main,
                    ["--json"],
                ),
                (
                    "maintenance dry run",
                    maintenance_main,
                    ["run", "--dry-run", "--json"],
                ),
            )
            for invocation in direct_invocations:
                label, target, suffix, *resolver = invocation
                for root_option in (("--root=",), ("--root", " \t")):
                    with self.subTest(entrypoint=label, root_option=root_option):
                        output = io.StringIO()
                        error = io.StringIO()
                        context = (
                            patch(resolver[0]) if resolver else nullcontext()
                        )
                        with (
                            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": str(ambient_root)}),
                            context as root_resolver,
                            redirect_stdout(output),
                            redirect_stderr(error),
                            self.assertRaises(SystemExit) as raised,
                        ):
                            target([*root_option, *suffix])

                        self.assertEqual(raised.exception.code, 2)
                        self.assertEqual(output.getvalue(), "")
                        if resolver:
                            root_resolver.assert_not_called()
                        self.assertIn("--root requires a non-empty vault path", error.getvalue())

    def test_unified_root_binding_prefers_explicit_vault_over_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            explicit_root = Path(tmp) / "explicit-vault"
            ambient_root = Path(tmp) / "ambient-vault"
            copy_template_tree(explicit_root)
            copy_template_tree(ambient_root)
            invocations = (
                (
                    "global explicit root",
                    [
                        "--root",
                        str(explicit_root),
                        "setup",
                        "plan",
                        "--client",
                        "codex",
                        "--json",
                    ],
                    explicit_root,
                    ambient_root,
                ),
                (
                    "post-command explicit root",
                    [
                        "setup",
                        "--root",
                        str(explicit_root),
                        "plan",
                        "--client",
                        "codex",
                        "--json",
                    ],
                    explicit_root,
                    ambient_root,
                ),
                (
                    "environment root",
                    ["setup", "plan", "--client", "codex", "--json"],
                    ambient_root,
                    ambient_root,
                ),
            )
            for label, argv, expected_root, expected_environment_root in invocations:
                with self.subTest(binding=label):
                    output = io.StringIO()
                    with (
                        patch.dict(os.environ, {"AI_DEMEMORY_ROOT": str(ambient_root)}),
                        redirect_stdout(output),
                    ):
                        self.assertEqual(cli_main(argv), 0)
                        self.assertEqual(
                            os.environ["AI_DEMEMORY_ROOT"],
                            str(expected_environment_root.resolve()),
                        )

                    self.assertEqual(
                        Path(json.loads(output.getvalue())["root"]),
                        expected_root.resolve(),
                    )

    def test_direct_whitespace_root_argument_is_rejected_before_resolution(self) -> None:
        output = io.StringIO()
        direct_error = io.StringIO()
        with (
            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
            patch("provider_import.resolve_runtime_vault") as root_resolver,
            redirect_stdout(output),
            redirect_stderr(direct_error),
            self.assertRaises(SystemExit) as raised,
        ):
            provider_main(["--root", " ", "plan", "--json"])

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(output.getvalue(), "")
        root_resolver.assert_not_called()
        self.assertIn("--root requires a non-empty vault path", direct_error.getvalue())

    def test_cli_help_binds_the_mcp_config_example_to_a_vault(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli_main([]), 0)

        self.assertIn(
            "ai-dememory --root ~/code/my-memory mcp-config --client codex",
            output.getvalue(),
        )

    def test_codex_mcp_config_is_toml_safe_for_unicode_and_quotes(self) -> None:
        root = Path('C:/vault/emoji-🧠/quoted-"root"')
        rendered = build_mcp_config(
            "codex", "installed", root, command='ai-"dememory', command_args=["--label", "brain-🧠"]
        )
        config = tomllib.loads(rendered)["mcp_servers"]["ai-dememory"]
        self.assertEqual(config["command"], 'ai-"dememory')
        self.assertEqual(
            config["args"],
            [
                "--label",
                "brain-🧠",
                "mcp",
                "--stdio",
                "--idle-timeout-seconds",
                "600",
                "--profile",
                "core",
                "--require-bound-root",
            ],
        )
        self.assertEqual(config["env"]["AI_DEMEMORY_ROOT"], str(root))

    def test_mcp_client_smoke_selects_server_from_codex_toml(self) -> None:
        rendered = build_mcp_config("codex", "installed", Path("C:/vault"))
        server, selected_name = select_server_config(rendered)
        self.assertEqual(selected_name, "ai-dememory")
        self.assertEqual(server["command"], "ai-dememory")
        self.assertEqual(
            server["args"],
            [
                "mcp",
                "--stdio",
                "--idle-timeout-seconds",
                "600",
                "--profile",
                "core",
                "--require-bound-root",
            ],
        )

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
            self.assertNotIn("--require-version", data["args"])
            self.assertEqual(data["env"], {})

    def test_mcp_config_supports_checkout_command_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
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
        self.assertEqual(
            data["args"],
            [
                "scripts/ai_dememory.py",
                "mcp",
                "--stdio",
                "--idle-timeout-seconds",
                "600",
                "--profile",
                "core",
                "--require-bound-root",
            ],
        )

    def test_mcp_client_smoke_launches_source_code_against_separate_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            copy_template_tree(vault)
            config = build_mcp_config(
                "generic",
                "installed",
                vault,
                command=sys.executable,
                command_args=[str(ROOT / "scripts" / "ai_dememory.py")],
            )
            server, _ = select_server_config(config)

            self.assertIs(
                COMMAND_ROOT_POLICIES["mcp-client-smoke"],
                CommandRootPolicy.VAULT_BOUND,
            )
            self.assertEqual(server["env"]["AI_DEMEMORY_ROOT"], str(vault))
            result = run_client_config_smoke(config, vault)

        self.assertEqual(Path(result.cwd), vault)
        self.assertTrue(result.initialized)
        self.assertTrue(result.pinged)
        self.assertFalse(result.enabled_tools_verified)
        self.assertEqual(result.enabled_tool_count, 0)

    def test_mcp_client_smoke_binds_checked_in_config_to_explicit_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            copy_template_tree(vault)
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                patch("mcp_client_smoke.repo_root", return_value=vault),
                redirect_stdout(output),
            ):
                exit_code = mcp_client_smoke_main(
                    [
                        "--root",
                        str(vault),
                        "--config",
                        str(ROOT / "plugins" / "ai-dememory" / ".mcp.json"),
                        "--command",
                        sys.executable,
                        "--command-arg",
                        str(ROOT / "scripts" / "ai_dememory.py"),
                        "--json",
                    ]
                )
            result = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(Path(result["cwd"]), vault)
        self.assertTrue(result["initialized"])
        self.assertTrue(result["pinged"])
        self.assertTrue(result["enabled_tools_verified"])
        self.assertEqual(result["enabled_tool_count"], 3)

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
        self.assertIn("fixture memory.public_only", checks)
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

    def test_secret_scanner_does_not_skip_canonical_memory_named_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("z" * 40)
            memory = root / "memories" / "projects" / "build" / "policy.md"
            memory.parent.mkdir(parents=True)
            memory.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")

            findings = scan_paths(root)

        self.assertTrue(findings)
        self.assertEqual({finding.path for finding in findings}, {"memories/projects/build/policy.md"})

    def test_secret_scanner_skips_virtual_environments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "sk-" + "proj-" + ("v" * 40)
            path = root / ".venv" / "lib" / "package.py"
            path.parent.mkdir(parents=True)
            path.write_text(f"API_KEY={secret}\n", encoding="utf-8")

            findings = scan_paths(root)

        self.assertEqual(findings, [])

    def test_secret_scanner_does_not_follow_discovered_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            secret = "sk-" + "proj-" + ("s" * 40)
            outside.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            linked = root / "linked.txt"
            try:
                os.symlink(outside, linked)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            findings = scan_paths(root)
            with self.assertRaisesRegex(ValueError, "stay inside the memory root"):
                scan_paths(root, ["linked.txt"])

        self.assertEqual(findings, [])

    def test_secret_scanner_fails_closed_on_file_and_entry_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            oversized = root / "oversized.txt"
            oversized.write_text("x" * 65, encoding="utf-8")
            oversized_findings = scan_paths(root, max_file_bytes=64)

            oversized.unlink()
            for index in range(3):
                (root / f"file-{index}.txt").write_text("safe\n", encoding="utf-8")
            entry_findings = scan_paths(root, max_scan_entries=2)

        self.assertEqual({item.kind for item in oversized_findings}, {"scan-limit"})
        self.assertEqual({item.kind for item in entry_findings}, {"scan-limit"})

    def test_memory_discovery_and_load_enforce_resource_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "memories" / "tools" / "first.md"
            second = root / "memories" / "tools" / "second.md"
            first.parent.mkdir(parents=True)
            first.write_text("x" * 32, encoding="utf-8")
            second.write_text("y" * 32, encoding="utf-8")

            with self.assertRaisesRegex(MemoryError, "file limit"):
                discover_memory_files(root, max_files=1)
            with self.assertRaisesRegex(MemoryError, "byte limit"):
                load_memory(first, max_file_bytes=16)

    def test_markdown_discovery_bounds_inbox_and_excludes_generated_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "inbox" / "captures" / "candidate.md"
            packet = root / "inbox" / "sleep-consolidation" / "generated.md"
            candidate.parent.mkdir(parents=True)
            packet.parent.mkdir(parents=True)
            candidate.write_text("# Candidate\n", encoding="utf-8")
            packet.write_text("# Generated\n", encoding="utf-8")

            files = discover_markdown_files(
                root,
                "inbox",
                excluded_dirs=("inbox/sleep-consolidation",),
            )
            with self.assertRaisesRegex(MemoryError, "file limit"):
                discover_markdown_files(root, "inbox", max_files=1)

        self.assertEqual(files, [candidate])

    def test_search_and_lifecycle_reject_indexes_above_runtime_row_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/one.md", memory_id="mem_limit_one")
            write_memory(root, "memories/tools/two.md", memory_id="mem_limit_two")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            with patch("search_memory.MAX_MEMORY_FILES", 1):
                with self.assertRaisesRegex(RuntimeError, "row limit"):
                    search("memory", root)
            with patch("lifecycle.MAX_LIFECYCLE_ROWS", 1):
                with self.assertRaisesRegex(RuntimeError, "row limit"):
                    lifecycle_scores(root)

    def test_secret_scanner_rejects_explicit_path_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside.txt"
            root.mkdir()
            outside.write_text("non-secret outside fixture\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "stay inside the memory root"):
                scan_paths(root, [str(outside)])

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
            set_section(root, "false_positives", {"review_after_days": 7})
            secret = "sk-" + "proj-" + ("f" * 40)
            path = root / "docs" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            target = false_positive_reviews(root)[0]

            with patch.dict(
                call_tool.__globals__["ignore_false_positive"].__globals__,
                {"today": lambda: date(2026, 6, 21)},
            ):
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

            with patch("ai_dememory_tool.admin.review_memory.today", return_value=date(2099, 1, 1)):
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
                "\n".join(["[conflicts]", f"proposal_path = {json.dumps(str(outside))}", ""]),
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

    def test_safe_writer_never_follows_existing_target_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside.txt"
            root.mkdir()
            outside.write_text("preserve\n", encoding="utf-8")
            target = root / "report.md"
            try:
                os.symlink(outside, target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                safe_write_text(target, "replacement\n", root=root, overwrite=True)

            self.assertEqual(outside.read_text(encoding="utf-8"), "preserve\n")

    def test_safe_writer_exclusive_mode_preserves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "proposal.md"
            target.write_text("original\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                safe_write_text(target, "replacement\n", root=root, overwrite=False)

            self.assertEqual(target.read_text(encoding="utf-8"), "original\n")

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

    def test_search_loads_lifecycle_state_with_one_database_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(12):
                write_memory(
                    root,
                    f"memories/tools/codex-{index:02d}.md",
                    memory_id=f"mem_codex_{index:02d}",
                    body=f"Codex project guidance {index}.",
                )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")

            with patch("search_memory.sqlite3.connect", wraps=sqlite3.connect) as connect:
                results = search("codex", root, db_path=db_path)

        self.assertTrue(results)
        self.assertEqual(connect.call_count, 1)

    def test_search_public_only_filters_before_applying_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/tools/a-internal.md",
                memory_id="mem_internal_first",
                sensitivity="internal",
            )
            write_memory(
                root,
                "memories/tools/z-public.md",
                memory_id="mem_public_second",
                sensitivity="public",
            )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")

            results = search("codex", root, db_path=db_path, limit=1, public_only=True)

        self.assertEqual([result.id for result in results], ["mem_public_second"])

    def test_search_public_only_rejects_stale_public_index_after_canonical_downgrade(self) -> None:
        marker = "CANONICAL_INTERNAL_AFTER_REINDEX_REQUIRED"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_memory(
                root,
                "memories/tools/public-before.md",
                memory_id="mem_stale_public",
                sensitivity="public",
                body="Public before-index content.",
            )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            path.write_text(
                valid_memory_text(
                    "mem_stale_public",
                    sensitivity="internal",
                    body=marker,
                ),
                encoding="utf-8",
            )

            results = search("codex", root, db_path=db_path, public_only=True)
            mcp_results = call_tool(
                "memory.search",
                {"query": "codex", "public_only": True},
                root,
            )
            context = call_tool(
                "memory.context",
                {
                    "query": "codex",
                    "public_only": True,
                    "include_working_memory": False,
                },
                root,
            )

        serialized = json.dumps({"search": mcp_results, "context": context})
        self.assertEqual(results, [])
        self.assertEqual(mcp_results, [])
        self.assertEqual(context["items"], [])
        self.assertNotIn(marker, serialized)
        self.assertNotIn("mem_stale_public", serialized)

    def test_search_public_only_ranking_ignores_hidden_corpus_and_lifecycle(self) -> None:
        def projection(results: list[Any]) -> list[dict[str, Any]]:
            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "snippet": result.snippet,
                    "why": result.why,
                }
                for result in results
            ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/tools/a-public.md",
                memory_id="mem_public_alpha",
                sensitivity="public",
                body="Public codex alpha guidance.",
            )
            write_memory(
                root,
                "memories/tools/b-public.md",
                memory_id="mem_public_beta",
                sensitivity="public",
                body="Public codex beta guidance.",
            )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            baseline = projection(search("codex", root, db_path=db_path, public_only=True))

            for index in range(12):
                write_memory(
                    root,
                    f"memories/tools/internal-{index:02d}.md",
                    memory_id=f"mem_internal_hidden_{index:02d}",
                    sensitivity="internal",
                    body=f"Hidden codex corpus marker {index}.",
                )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            for _ in range(6):
                lifecycle_mark_seen(root, "mem_public_beta", query="private usage", used_by="unit-test")
            for index in range(12):
                lifecycle_mark_seen(
                    root,
                    f"mem_internal_hidden_{index:02d}",
                    query="private usage",
                    used_by="unit-test",
                )
            after_hidden_state = projection(search("codex", root, db_path=db_path, public_only=True))

        self.assertEqual(after_hidden_state, baseline)
        self.assertTrue(baseline)
        self.assertTrue(all(item["why"]["text_score_source"] == "canonical_public" for item in baseline))
        self.assertTrue(all(item["why"]["lifecycle_strength"] == 0.0 for item in baseline))

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
        self.assertEqual(context["items"][0]["sensitivity"], "internal")
        self.assertIn("matched_terms", context["items"][0]["why"])
        self.assertIn("Working Memory", context["text"])
        self.assertTrue(context["working_memory"]["included"])
        self.assertEqual(context["working_memory"]["sensitivity"], "internal")
        self.assertIn("## Working Memory\n\n- sensitivity: `internal`", context["text"])
        self.assertIn("- sensitivity: `internal`", context["text"])
        self.assertNotIn("Sensitive phrase", context["text"])

    def test_context_public_only_filters_internal_and_working_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/tools/public.md",
                memory_id="mem_public_codex",
                sensitivity="public",
                body="Public codex guidance.",
            )
            write_memory(
                root,
                "memories/tools/internal.md",
                memory_id="mem_internal_codex",
                sensitivity="internal",
                body="Internal codex guidance must not enter public context.",
            )
            snapshot(root, "Current work", "Internal working note about codex.", task="unit-test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            with patch(
                "context_memory.working_context",
                side_effect=AssertionError("public-only context must not read generated working state"),
            ):
                context = assemble_context(
                    root,
                    "codex",
                    budget_tokens=900,
                    include_working_memory=True,
                    public_only=True,
                )

        self.assertTrue(context["public_only"])
        self.assertEqual([item["id"] for item in context["items"]], ["mem_public_codex"])
        self.assertTrue(context["working_memory"]["filtered"])
        self.assertFalse(context["working_memory"]["included"])
        self.assertIn("non_public_working_memory_filtered", context["degradation"])
        self.assertEqual(context["non_public_filtered_items"], 0)
        self.assertNotIn("non_public_memory_filtered", context["degradation"])
        self.assertNotIn("Working Memory", context["text"])
        self.assertNotIn("Internal codex guidance", context["text"])
        self.assertIn("- sensitivity: `public`", context["text"])
        self.assertNotIn("mem_internal_codex", json.dumps(context))

    def test_context_cli_public_only_rejects_auto_without_reading_working_query(self) -> None:
        marker = "TOP_INTERNAL_WORKING_MARKER_42"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot(root, "Private working state", marker, task="unit-test")
            output = io.StringIO()
            errors = io.StringIO()

            with redirect_stdout(output), redirect_stderr(errors):
                exit_code = context_main(
                    ["--root", str(root), "--public-only", "--auto", "--json"]
                )

        rendered = output.getvalue() + errors.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("requires an explicit query", rendered)
        self.assertNotIn(marker, rendered)

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

    def test_mcp_public_only_context_search_and_get_enforce_public_ceiling(self) -> None:
        marker = "TOP_INTERNAL_MCP_MARKER_73"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            write_memory(
                root,
                "memories/tools/a-internal.md",
                memory_id="mem_internal_mcp",
                sensitivity="internal",
                body=marker,
            )
            write_memory(
                root,
                "memories/tools/z-public.md",
                memory_id="mem_public_mcp",
                sensitivity="public",
                body="Public MCP guidance.",
            )
            snapshot(root, "Private working state", marker, task="unit-test")
            rebuild_index(root, root / "indexes" / "memory.sqlite")

            context = call_tool(
                "memory.context",
                {
                    "query": "codex",
                    "limit": 1,
                    "include_working_memory": True,
                    "public_only": True,
                },
                root,
            )
            search_results = call_tool(
                "memory.search",
                {"query": "codex", "limit": 1, "public_only": True},
                root,
            )
            public_memory = call_tool(
                "memory.get",
                {"id": "mem_public_mcp", "public_only": True},
                root,
            )
            with self.assertRaisesRegex(ValueError, "requires an explicit query") as auto_error:
                call_tool(
                    "memory.context",
                    {"auto": True, "public_only": True},
                    root,
                )
            with self.assertRaisesRegex(PermissionError, "public-only sensitivity ceiling"):
                call_tool(
                    "memory.get",
                    {"id": "mem_internal_mcp", "public_only": True},
                    root,
                )

        serialized = json.dumps(
            {
                "context": context,
                "search": search_results,
                "public_memory": public_memory,
                "auto_error": str(auto_error.exception),
            }
        )
        self.assertTrue(context["public_only"])
        self.assertEqual([item["id"] for item in context["items"]], ["mem_public_mcp"])
        self.assertEqual([item["id"] for item in search_results], ["mem_public_mcp"])
        self.assertEqual(public_memory["frontmatter"]["sensitivity"], "public")
        self.assertNotIn(marker, serialized)
        self.assertNotIn("mem_internal_mcp", serialized)
        context_tool = next(tool for tool in TOOLS if tool["name"] == "memory.context")
        output_schema = context_tool["outputSchema"]
        self.assertEqual(set(context), set(output_schema["properties"]))
        self.assertEqual(set(context), set(output_schema["required"]))
        self.assertFalse(output_schema["additionalProperties"])

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

    def test_vector_report_rejects_canonical_memory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "memories" / "durable" / "values.md"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("canonical memory\n", encoding="utf-8")
            readiness = VectorReadiness(
                decision="not_justified",
                rationale="Recall is healthy.",
                recall_threshold=0.85,
                min_failed_cases=2,
                recall={},
                failed_case_ids=[],
                generated_at="2026-07-27T00:00:00+00:00",
            )

            with self.assertRaisesRegex(ValueError, "under reports/"):
                write_vector_report(root, readiness, canonical)
            preserved = canonical.read_text(encoding="utf-8")

        self.assertEqual(preserved, "canonical memory\n")

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

    def test_capture_miss_validates_config_before_directory_or_deduplication(self) -> None:
        canary = "capture-miss-config-must-not-escape"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".ai-dememory.toml"
            original = f'[recall]\nenabled = "{canary}"\n'.encode("utf-8")
            config.write_bytes(original)
            before = {config.name: config.read_bytes()}

            with self.assertRaises(ValueError) as direct_error:
                capture_miss(
                    root,
                    "missing strict policy",
                    "Expected policy memory was absent.",
                    expected_id="mem_policy",
                )
            self.assertNotIn(canary, str(direct_error.exception))
            self.assertFalse((root / "inbox").exists())

            for dry_run in (False, True):
                output = io.StringIO()
                error = io.StringIO()
                command = [
                    "--root",
                    str(root),
                    "--query",
                    "missing strict policy",
                    "--reason",
                    "Expected policy memory was absent.",
                    "--expected-id",
                    "mem_policy",
                    "--json",
                ]
                if dry_run:
                    command.append("--dry-run")
                with redirect_stdout(output), redirect_stderr(error):
                    exit_code = capture_miss_main(command)
                self.assertEqual(exit_code, 1)
                self.assertEqual(output.getvalue(), "")
                self.assertNotIn(canary, error.getvalue())
                self.assertNotIn("traceback", error.getvalue().lower())
                self.assertFalse((root / "inbox").exists())
                self.assertEqual({config.name: config.read_bytes()}, before)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = capture_miss(
                root,
                "deduplicated strict policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
                max_pending=2,
            )
            config = root / ".ai-dememory.toml"
            config.write_text(
                f'[recall]\nenabled = "{canary}"\n',
                encoding="utf-8",
            )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            with self.assertRaises(ValueError):
                capture_miss(
                    root,
                    "deduplicated strict policy",
                    "Expected policy memory was absent.",
                    expected_id="mem_policy",
                    max_pending=2,
                )

            self.assertTrue(existing.exists())
            self.assertEqual(
                {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file()
                },
                before,
            )

    def test_capture_miss_deduplicates_and_enforces_pending_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = capture_miss(
                root,
                "missing first policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
                max_pending=1,
            )
            duplicate = capture_miss(
                root,
                "missing first policy",
                "Expected policy memory was absent.",
                expected_id="mem_policy",
                max_pending=1,
            )
            with self.assertRaisesRegex(ValueError, "pending-item capacity"):
                capture_miss(
                    root,
                    "missing second policy",
                    "Expected policy memory was absent.",
                    expected_id="mem_policy",
                    max_pending=1,
                )

        self.assertEqual(duplicate, first)

    def test_capture_miss_bounds_all_rendered_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "expected_path"):
                capture_miss(
                    root,
                    "missing policy",
                    "Expected policy memory was absent.",
                    expected_path="x" * 4001,
                )
            with self.assertRaisesRegex(ValueError, "source_ref"):
                capture_miss(
                    root,
                    "missing policy",
                    "Expected policy memory was absent.",
                    expected_id="mem_policy",
                    source_ref="x" * 4001,
                )

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

    def test_recall_fixture_review_report_rejects_canonical_memory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_path = root / "quality" / "recall-fixtures.json"
            fixtures_path.parent.mkdir(parents=True)
            fixtures_path.write_text("[]\n", encoding="utf-8")
            canonical = root / "memories" / "durable" / "values.md"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("canonical memory\n", encoding="utf-8")
            plan = recall_fixture_review_plan(root, today=date(2026, 6, 19))

            with self.assertRaisesRegex(ValueError, "under reports/"):
                write_recall_review_report(root, plan, canonical)
            preserved = canonical.read_text(encoding="utf-8")

        self.assertEqual(preserved, "canonical memory\n")

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

    def test_mcp_get_by_id_rejects_noncanonical_index_path(self) -> None:
        marker = "NONCANONICAL_INDEX_MARKER_91"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = write_memory(
                root,
                "memories/tools/canonical.md",
                memory_id="mem_index_target",
            )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            noncanonical = root / "docs" / "indexed.md"
            noncanonical.parent.mkdir(parents=True)
            noncanonical.write_text(
                valid_memory_text("mem_index_target", body=marker),
                encoding="utf-8",
            )
            document = load_memory(noncanonical)
            canonical.unlink()
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "UPDATE memories SET path = ?, content_hash = ? WHERE id = ?",
                    (
                        "docs/indexed.md",
                        content_hash(document.frontmatter, document.content),
                        "mem_index_target",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(FileNotFoundError):
                call_tool("memory.get", {"id": "mem_index_target"}, root)

    def test_mcp_get_by_id_revalidates_index_identity_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical_a = write_memory(
                root,
                "memories/tools/a.md",
                memory_id="mem_index_a",
                body="CANONICAL_A_MARKER_52",
            )
            canonical_b = write_memory(
                root,
                "memories/tools/b.md",
                memory_id="mem_index_b",
                body="REDIRECTED_B_MARKER_63",
            )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            document_a = load_memory(canonical_a)
            document_b = load_memory(canonical_b)
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("DELETE FROM memories WHERE id = ?", ("mem_index_b",))
                conn.execute(
                    "UPDATE memories SET path = ?, content_hash = ? WHERE id = ?",
                    (
                        repo_relative_path(canonical_b, root),
                        content_hash(document_b.frontmatter, document_b.content),
                        "mem_index_a",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            identity_result = call_tool("memory.get", {"id": "mem_index_a"}, root)
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "UPDATE memories SET path = ?, content_hash = ? WHERE id = ?",
                    (
                        repo_relative_path(canonical_a, root),
                        content_hash(document_a.frontmatter, document_a.content),
                        "mem_index_a",
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            canonical_a.write_text(
                valid_memory_text("mem_index_a", body="FRESH_A_MARKER_74"),
                encoding="utf-8",
            )
            stale_hash_result = call_tool("memory.get", {"id": "mem_index_a"}, root)

        self.assertEqual(identity_result["frontmatter"]["id"], "mem_index_a")
        self.assertIn("CANONICAL_A_MARKER_52", identity_result["content"])
        self.assertNotIn("REDIRECTED_B_MARKER_63", identity_result["content"])
        self.assertEqual(stale_hash_result["frontmatter"]["id"], "mem_index_a")
        self.assertIn("FRESH_A_MARKER_74", stale_hash_result["content"])

    def test_mcp_get_by_id_rejects_index_path_through_linked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "vault"
            canonical = write_memory(
                root,
                "memories/tools/canonical.md",
                memory_id="mem_link_target",
                body="CANONICAL_LINK_MARKER_85",
            )
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")
            outside = base / "outside"
            external = write_memory(
                outside,
                "linked.md",
                memory_id="mem_link_target",
                body="LINK_ESCAPE_MARKER_96",
            )
            linked_parent = root / "docs" / "linked"
            linked_parent.parent.mkdir(parents=True)
            try:
                os.symlink(outside, linked_parent, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            external_document = load_memory(external)
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "UPDATE memories SET path = ?, content_hash = ? WHERE id = ?",
                    (
                        "docs/linked/linked.md",
                        content_hash(external_document.frontmatter, external_document.content),
                        "mem_link_target",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            result = call_tool("memory.get", {"id": "mem_link_target"}, root)

        self.assertEqual(result["path"], repo_relative_path(canonical, root))
        self.assertIn("CANONICAL_LINK_MARKER_85", result["content"])
        self.assertNotIn("LINK_ESCAPE_MARKER_96", result["content"])

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

    def test_lifecycle_logs_are_pruned_and_remain_bounded_after_reindex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(root, "memories/tools/codex.md", memory_id="mem_codex_test")
            db_path, _ = rebuild_index(root, root / "indexes" / "memory.sqlite")

            with (
                patch("index_memory.MAX_RETRIEVAL_LOG_ROWS", 3),
                patch("index_memory.MAX_OUTCOME_LOG_ROWS", 2),
            ):
                for index in range(5):
                    lifecycle_mark_seen(
                        root,
                        "mem_codex_test",
                        query=f"query-{index}",
                        score=0.5,
                    )
                for index in range(4):
                    record_outcome(
                        root,
                        "mem_codex_test",
                        "good",
                        note=f"outcome-{index}",
                    )
                rebuild_index(root, db_path)

            conn = sqlite3.connect(db_path)
            retrieval_rows = conn.execute(
                "SELECT query FROM retrieval_log ORDER BY id"
            ).fetchall()
            outcome_rows = conn.execute(
                "SELECT note FROM memory_outcomes ORDER BY id"
            ).fetchall()
            lifecycle = conn.execute(
                "SELECT retrieval_count, positive_outcomes FROM memory_lifecycle "
                "WHERE memory_id = ?",
                ("mem_codex_test",),
            ).fetchone()
            conn.close()

        self.assertEqual([row[0] for row in retrieval_rows], ["query-2", "query-3", "query-4"])
        self.assertEqual([row[0] for row in outcome_rows], ["outcome-2", "outcome-3"])
        self.assertEqual(lifecycle, (5, 4))

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

            with patch.object(
                graph_memory,
                "discover_memory_files",
                side_effect=AssertionError("should use index"),
            ):
                graph = build_graph(root)

        self.assertTrue(any(node["id"] == "mem_codex_test" for node in graph["nodes"]))

    def test_graph_paginates_memory_nodes_and_reports_next_offset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(3):
                write_memory(
                    root,
                    f"memories/tools/{index}.md",
                    memory_id=f"mem_graph_{index}",
                )

            first = build_graph(root, prefer_index=False, limit=2)
            second = build_graph(root, prefer_index=False, limit=2, offset=2)

        first_ids = {node["id"] for node in first["nodes"] if node["kind"] == "memory"}
        second_ids = {node["id"] for node in second["nodes"] if node["kind"] == "memory"}
        self.assertEqual(len(first_ids), 2)
        self.assertEqual(len(second_ids), 1)
        self.assertTrue(first["page"]["has_more"])
        self.assertEqual(first["page"]["next_offset"], 2)
        self.assertFalse(second["page"]["has_more"])
        self.assertIsNone(second["page"]["next_offset"])

    def test_graph_revalidates_stale_index_sensitivity_and_public_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_path = write_memory(
                root,
                "memories/tools/public.md",
                memory_id="mem_graph_public",
                sensitivity="public",
            )
            write_memory(
                root,
                "memories/tools/internal.md",
                memory_id="mem_graph_internal",
                sensitivity="internal",
            )
            rebuild_index(root, root / "indexes" / "memory.sqlite")
            public_text = public_path.read_text(encoding="utf-8")
            public_path.write_text(
                public_text.replace("sensitivity: public", "sensitivity: sensitive"),
                encoding="utf-8",
            )

            default_graph = build_graph(root)
            public_graph = build_graph(root, public_only=True)

        self.assertNotIn("mem_graph_public", {node["id"] for node in default_graph["nodes"]})
        self.assertNotIn("mem_graph_internal", {node["id"] for node in public_graph["nodes"]})
        self.assertEqual(
            {node["id"] for node in public_graph["nodes"] if node["kind"] == "memory"},
            set(),
        )

    def test_graph_markdown_fallback_rejects_secret_like_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_memory(
                root,
                "memories/tools/unsafe.md",
                memory_id="mem_graph_unsafe",
                body="Credential sk-proj-" + ("q" * 40),
            )

            with self.assertRaisesRegex(ValueError, "secret scan"):
                build_graph(root, prefer_index=False)

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
                self.assertFalse(thread.is_alive())

        self.assertEqual(health["status"], "ok")
        self.assertEqual(search_result["results"][0]["id"], "mem_codex_test")
        self.assertTrue(any(node["id"] == "mem_codex_test" for node in graph_result["nodes"]))

    def test_api_requires_a_runtime_binding_before_starting_a_socket(self) -> None:
        error = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("http_api.serve") as start_server,
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            api_main(["--host", "127.0.0.1", "--port", "8765"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("runtime vault binding requires", error.getvalue())
        start_server.assert_not_called()

    def test_cli_api_does_not_discover_an_ambient_root(self) -> None:
        error = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            cli_main(["api"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("runtime vault binding requires", error.getvalue())
        root_resolver.assert_not_called()

    def test_api_explicit_binding_wins_over_a_malformed_environment_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "explicit-vault"
            copy_template_tree(root)
            error = io.StringIO()
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": " \t"}),
                patch("http_api.serve", side_effect=OSError("socket fixture")) as start_server,
                redirect_stderr(error),
            ):
                exit_code = api_main(["--root", str(root)])

        self.assertEqual(exit_code, 2)
        self.assertIn("API startup failed", error.getvalue())
        self.assertEqual(start_server.call_args.args[0], root.resolve())

    def test_direct_api_entrypoint_rejects_duplicate_roots(self) -> None:
        error = io.StringIO()
        with (
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            api_main(["--root", "first-vault", "--root", "second-vault"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--root may be specified at most once", error.getvalue())

    def test_direct_api_entrypoint_rejects_relative_root_before_starting(self) -> None:
        error = io.StringIO()
        with (
            patch("http_api.serve") as start_server,
            redirect_stderr(error),
            self.assertRaises(SystemExit) as raised,
        ):
            api_main(["--root", "."])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--root requires an absolute vault path", error.getvalue())
        start_server.assert_not_called()

    def test_api_refuses_unauthenticated_network_bind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)

            with patch("sys.stderr", io.StringIO()):
                exit_code = api_main(["--root", str(root), "--host", "0.0.0.0", "--port", "8765"])

        self.assertEqual(exit_code, 2)

    def test_api_serve_boundary_refuses_network_bind_without_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "require an API key"):
                serve(
                    Path(tmp),
                    "0.0.0.0",
                    0,
                    tls_cert="fixture-cert.pem",
                    tls_key="fixture-key.pem",
                    log_requests=False,
                )

    def test_api_refuses_cleartext_network_bind_even_with_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            with (
                patch.dict(os.environ, {"AI_DEMEMORY_API_KEY": "test-key"}),
                patch("sys.stderr", io.StringIO()),
            ):
                exit_code = api_main(["--root", str(root), "--host", "0.0.0.0", "--port", "8765"])
            with self.assertRaisesRegex(ValueError, "require --tls-cert"):
                serve(root, "0.0.0.0", 0, api_key="test-key", log_requests=False)

        self.assertEqual(exit_code, 2)

    def test_api_rejects_cross_site_and_unmarked_mutation_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = serve(root, "127.0.0.1", 0, log_requests=False)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                cross_site = Request(
                    f"{base_url}/health",
                    headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
                )
                with self.assertRaises(HTTPError) as cross_site_error:
                    urlopen(cross_site, timeout=5)
                self.assertEqual(cross_site_error.exception.code, 403)
                cross_site_error.exception.close()

                unmarked_body = b'{"malformed":'
                unmarked = Request(
                    f"{base_url}/reindex",
                    data=unmarked_body,
                    headers={"Content-Type": "text/plain"},
                    method="POST",
                )
                consumed_bodies: list[bytes] = []

                def track_body(handler: Any) -> bytes:
                    raw = read_request_body(handler)
                    consumed_bodies.append(raw)
                    return raw

                with (
                    patch("http_api.read_request_body", side_effect=track_body),
                    self.assertRaises(HTTPError) as unmarked_error,
                ):
                    urlopen(unmarked, timeout=5)
                self.assertEqual(unmarked_error.exception.code, 403)
                unmarked_error.exception.close()
                self.assertEqual(consumed_bodies, [unmarked_body])

                wrong_type = Request(
                    f"{base_url}/reindex",
                    data=b'{"malformed":',
                    headers={
                        "Content-Type": "text/plain",
                        MUTATION_INTENT_HEADER: MUTATION_INTENT_VALUE,
                    },
                    method="POST",
                )
                with self.assertRaises(HTTPError) as wrong_type_error:
                    urlopen(wrong_type, timeout=5)
                self.assertEqual(wrong_type_error.exception.code, 415)
                wrong_type_error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())

    def test_api_allows_a_matching_loopback_proxy_context(self) -> None:
        require_safe_request_context(
            "127.0.0.1",
            "localhost:3000",
            "http://localhost:3000",
            "same-origin",
        )

    def test_api_rejects_negative_content_length_before_read(self) -> None:
        handler = type("FakeHandler", (), {})()
        handler.headers = {
            "Content-Length": "-1",
            "Content-Type": "application/json",
        }
        handler.rfile = io.BytesIO(b'{"oversized":"ignored"}')

        with self.assertRaises(ApiError) as error:
            read_json_body(handler)

        self.assertEqual(error.exception.status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(handler.rfile.tell(), 0)

    def test_api_consumes_bounded_body_before_rejecting_content_type(self) -> None:
        handler = type("FakeHandler", (), {})()
        handler.headers = {
            "Content-Length": "2",
            "Content-Type": "text/plain",
        }
        handler.rfile = io.BytesIO(b"{}")

        raw = read_request_body(handler)
        with self.assertRaises(ApiError) as error:
            parse_json_body(handler, raw)

        self.assertEqual(error.exception.status, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(handler.rfile.tell(), 2)

    def test_direct_json_body_helper_preserves_content_type_first_validation(self) -> None:
        handler = type("FakeHandler", (), {})()
        handler.headers = {"Content-Type": "text/plain"}
        handler.rfile = io.BytesIO(b"{}")

        with self.assertRaises(ApiError) as error:
            read_json_body(handler)

        self.assertEqual(error.exception.status, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(handler.rfile.tell(), 0)

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

    def test_provider_import_progresses_past_previously_imported_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            source = Path(tmp) / "provider"
            root.mkdir()
            source.mkdir()
            for index in range(45):
                (source / f"session-{index:03d}.json").write_text(
                    json.dumps({"session": index, "summary": f"Reviewed project note {index}"}),
                    encoding="utf-8",
                )

            first = import_chats(
                root,
                "codex",
                source_path=source,
                limit=20,
                max_scan_entries=100,
            )
            second = import_chats(
                root,
                "codex",
                source_path=source,
                limit=20,
                max_scan_entries=100,
            )
            third = import_chats(
                root,
                "codex",
                source_path=source,
                limit=20,
                max_scan_entries=100,
            )

        self.assertEqual(first["new_candidates"], 20)
        self.assertEqual(second["new_candidates"], 20)
        self.assertGreaterEqual(second["already_imported"], 20)
        self.assertEqual(third["new_candidates"], 5)
        self.assertGreaterEqual(third["already_imported"], 40)

    def test_provider_import_enforces_profile_and_scan_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            source = Path(tmp) / "provider"
            root.mkdir()
            source.mkdir()
            (root / ".ai-dememory.toml").write_text(
                '[automation]\nintensity = "minimal"\nmodel_policy = "off"\n',
                encoding="utf-8",
            )
            for index in range(120):
                (source / f"session-{index:03d}.json").write_text(
                    json.dumps({"session": index, "summary": f"Bounded note {index}"}),
                    encoding="utf-8",
                )

            result = import_chats(
                root,
                "codex",
                source_path=source,
                max_scan_entries=100,
                dry_run=True,
            )
            configure_provider(root, "codex", source)
            mcp_result = call_tool(
                "memory.import_chats",
                {"provider": "codex", "dry_run": True},
                root,
            )["result"]

        self.assertEqual(result["limits"]["max_new_candidates"], 5)
        self.assertEqual(result["limits"]["max_scan_entries"], 100)
        self.assertEqual(result["new_candidates"], 5)
        self.assertEqual(result["scanned_entries"], 100)
        self.assertTrue(result["scan_truncated"])
        self.assertEqual(mcp_result["limits"]["max_new_candidates"], 5)
        self.assertEqual(mcp_result["limits"]["max_scan_entries"], 500)

    def test_provider_import_surfaces_truncated_window_starvation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            source = Path(tmp) / "provider"
            root.mkdir()
            source.mkdir()
            for index in range(120):
                (source / f"session-{index:03d}.json").write_text(
                    json.dumps({"session": index, "summary": f"Bounded note {index}"}),
                    encoding="utf-8",
                )

            first = import_chats(
                root,
                "codex",
                source_path=source,
                limit=100,
                max_scan_entries=100,
            )
            second = import_chats(
                root,
                "codex",
                source_path=source,
                limit=100,
                max_scan_entries=100,
            )

        self.assertTrue(first["scan_truncated"])
        self.assertEqual(first["new_candidates"], 100)
        self.assertTrue(second["coverage_blocked"])
        self.assertFalse(second["coverage_complete"])
        self.assertEqual(second["new_candidates"], 0)
        self.assertEqual(second["suggested_scan_entries"], 200)
        self.assertIn("--scan-limit 200", second["next_action"])

    def test_provider_import_rejects_file_identity_change_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            source = Path(tmp) / "provider"
            root.mkdir()
            source.mkdir()
            source_file = source / "session.txt"
            replacement = Path(tmp) / "replacement.txt"
            source_file.write_text("Original reviewed provider note.", encoding="utf-8")
            replacement.write_text("Replacement content must not be imported.", encoding="utf-8")
            real_open = os.open
            swapped = False

            def replace_before_open(path: object, flags: int) -> int:
                nonlocal swapped
                if not swapped and Path(path) == source_file:
                    os.replace(replacement, source_file)
                    swapped = True
                return real_open(path, flags)

            with patch("provider_import.os.open", side_effect=replace_before_open):
                result = import_chats(root, "codex", source_path=source, dry_run=True)

        self.assertTrue(swapped)
        self.assertEqual(result["new_candidates"], 0)
        self.assertTrue(any("changed before" in item["reason"] for item in result["skipped"]))

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

    def test_capture_source_quotes_untrusted_frontmatter_fields(self) -> None:
        injected_title = 'Reviewed title"\nsensitivity: public\nsource:\n  kind: forged\nx: "'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = capture_source(
                root,
                "text",
                text="Candidate body with ``` embedded fence.",
                title=injected_title,
            )
            candidate = load_memory(root / result["written"][0])

        self.assertEqual(candidate.frontmatter["title"], injected_title)
        self.assertEqual(candidate.frontmatter["sensitivity"], "internal")
        self.assertEqual(candidate.frontmatter["source"]["kind"], "import")
        self.assertNotIn("x", candidate.frontmatter)

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
            initialize_minimal_runtime_vault(root)
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

    def test_git_lessons_rejects_unbounded_repository_fanout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, f"at most {MAX_REPOSITORIES} repositories"):
                learn_git(
                    root,
                    [root] * (MAX_REPOSITORIES + 1),
                    days=7,
                    dry_run=True,
                )

    def test_git_subprocess_rejects_output_over_hard_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "unit@example.test")
            git(repo, "config", "user.name", "Unit Test")
            (repo / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", "fixture.txt")
            oversized_message = "fix bounded output\n\n" + ("x" * (MAX_GIT_OUTPUT_BYTES + 4096))
            subprocess.run(
                ["git", "commit", "-F", "-"],
                cwd=repo,
                input=oversized_message,
                text=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            with self.assertRaisesRegex(ValueError, "git command output exceeded"):
                run_git(repo, ["log", "-1", "--pretty=format:%B"])

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
            mcp_candidates = {
                candidate["name"]: candidate
                for candidate in call_tool("memory.providers_detect", {}, root)["providers"]
            }

        self.assertTrue(candidates["codex"].configured)
        self.assertTrue(candidates["codex"].enabled)
        self.assertTrue(candidates["codex"].exists)
        self.assertTrue(mcp_candidates["codex"]["configured"])
        self.assertTrue(mcp_candidates["codex"]["enabled"])
        self.assertTrue(mcp_candidates["codex"]["exists"])

    def test_vault_bound_provider_detection_rejects_relative_config_before_cwd_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "vault"
            cwd_with_candidate = base / "cwd-with-candidate"
            other_cwd = base / "other-cwd"
            for path in (root, cwd_with_candidate / "relative" / "provider", other_cwd):
                path.mkdir(parents=True)
            (root / ".ai-dememory.toml").write_text(
                '[providers.codex]\nenabled = true\npath = "relative/provider"\n',
                encoding="utf-8",
            )
            invocations = (
                ("direct detect", lambda: detect_providers(root)),
                ("direct status", lambda: providers_status(root)),
                ("direct plan", lambda: provider_setup_plan(root)),
                ("direct import", lambda: import_chats(root, "codex", dry_run=True)),
                ("mcp detect", lambda: call_tool("memory.providers_detect", {}, root)),
                ("mcp status", lambda: call_tool("memory.providers_status", {}, root)),
                ("mcp plan", lambda: call_tool("memory.providers_plan", {}, root)),
            )
            errors: list[str] = []
            previous_cwd = Path.cwd()
            try:
                for label, target in invocations:
                    for cwd in (cwd_with_candidate, other_cwd):
                        with self.subTest(entrypoint=label, cwd=cwd.name):
                            os.chdir(cwd)
                            with (
                                patch.object(
                                    Path,
                                    "exists",
                                    side_effect=AssertionError(
                                        "relative provider path reached a filesystem probe"
                                    ),
                                ) as path_probe,
                                self.assertRaises(ValueError) as raised,
                            ):
                                target()
                            path_probe.assert_not_called()
                            errors.append(str(raised.exception))
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(
            set(errors),
            {"configured provider path is unsafe [provider_path_unsafe] (provider=codex)"},
        )

    def test_explicit_relative_provider_override_remains_cwd_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "vault"
            cwd = base / "working-directory"
            provider = cwd / "relative" / "provider"
            root.mkdir()
            provider.mkdir(parents=True)
            previous_cwd = Path.cwd()
            try:
                os.chdir(cwd)
                resolved = configured_import_path(
                    root,
                    "codex",
                    Path("relative/provider"),
                )
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(resolved, provider.resolve())

    def test_provider_configure_dry_run_previews_without_writing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            provider = Path(tmp) / "provider"
            provider.mkdir(parents=True)
            copy_template_tree(root)
            config_before = (root / ".ai-dememory.toml").read_bytes()
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
            config_after = (root / ".ai-dememory.toml").read_bytes()

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
        self.assertEqual(
            preview["configure_command"][:4],
            ["ai-dememory", "--root", str(root.resolve()), "providers"],
        )
        self.assertEqual(payload["values"]["path"], str(provider.resolve()))
        self.assertTrue(payload["path_exists"])
        self.assertEqual(config_after, config_before)

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
            custom_plan = provider_setup_plan(root, command="memory-wrapper")
            providers = {item["name"]: item for item in plan["providers"]}
            inbox_exists = (root / "inbox" / "imports").exists()

        self.assertFalse(plan["mutates_system"])
        self.assertFalse(plan["reads_provider_files"])
        self.assertFalse(plan["writes_import_candidates"])
        self.assertEqual(providers["codex"]["reason"], "ready_for_import")
        self.assertEqual(
            providers["codex"]["configure_command"],
            [
                "ai-dememory",
                "--root",
                str(root.resolve()),
                "providers",
                "configure",
                "codex",
                "--path",
                str(provider.resolve()),
            ],
        )
        self.assertEqual(
            providers["codex"]["configure_dry_run_command"],
            [
                "ai-dememory",
                "--root",
                str(root.resolve()),
                "providers",
                "configure",
                "codex",
                "--path",
                str(provider.resolve()),
                "--dry-run",
                "--json",
            ],
        )
        self.assertEqual(
            providers["codex"]["import_dry_run_command"],
            ["ai-dememory", "--root", str(root.resolve()), "import-chats", "codex", "--dry-run", "--json"],
        )
        self.assertEqual(
            providers["codex"]["import_command"],
            ["ai-dememory", "--root", str(root.resolve()), "import-chats", "codex"],
        )
        self.assertEqual(
            custom_plan["providers"][0]["import_command"][:4],
            ["memory-wrapper", "--root", str(root.resolve()), "import-chats"],
        )
        self.assertFalse(inbox_exists)

    def test_provider_plan_human_output_renders_quoted_bound_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault'$(Write-Output PWNED);"
            provider_path = Path(tmp) / "provider"
            root.mkdir()
            provider_path.mkdir()
            configure_provider(root, "codex", provider_path)
            provider = next(
                item
                for item in provider_setup_plan(root)["providers"]
                if item["name"] == "codex"
            )
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = provider_main(["--root", str(root), "plan"])

        rendered = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn(
            "  preview: " + render_copy_command(provider["configure_dry_run_command"]),
            rendered,
        )
        self.assertIn(
            "  configure: " + render_copy_command(provider["configure_command"]),
            rendered,
        )
        self.assertIn(
            "  import: " + render_copy_command(provider["import_command"]),
            rendered,
        )

    def test_provider_setup_plan_commands_keep_the_planned_root_when_run_elsewhere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_a = Path(tmp) / "vault-a"
            root_b = Path(tmp) / "vault-b"
            copy_template_tree(root_a)
            copy_template_tree(root_b)
            root_a_config = root_a / ".ai-dememory.toml"
            root_b_config = root_b / ".ai-dememory.toml"
            root_a_config_before = root_a_config.read_bytes()
            root_b_config_before = root_b_config.read_bytes()
            expected_root_a = str(root_a.resolve())
            command = provider_setup_plan(root_a)["providers"][0]["configure_command"]
            output = io.StringIO()
            previous_cwd = Path.cwd()

            try:
                os.chdir(root_b)
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    redirect_stdout(output),
                ):
                    exit_code = cli_main(command[1:])
            finally:
                os.chdir(previous_cwd)

            root_a_config_after = root_a_config.read_bytes()
            root_b_config_after = root_b_config.read_bytes()

        self.assertEqual(command[:4], ["ai-dememory", "--root", expected_root_a, "providers"])
        self.assertEqual(command.count("--root"), 1)
        self.assertEqual(exit_code, 0)
        self.assertNotEqual(root_a_config_after, root_a_config_before)
        self.assertEqual(root_b_config_after, root_b_config_before)

    def test_provider_mutations_keep_root_a_when_dispatched_from_root_b(self) -> None:
        class CapturedModule:
            dispatched: list[dict[str, object]] = []

            @staticmethod
            def main(argv: list[str]) -> int:
                CapturedModule.dispatched.append(
                    {
                        "root": os.environ.get("AI_DEMEMORY_ROOT"),
                        "argv": list(argv),
                    }
                )
                return 0

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root_a = parent / "vault-a"
            root_b = parent / "vault-b"
            root_a.mkdir()
            root_b.mkdir()
            plan = provider_setup_plan(root_a)
            codex = next(item for item in plan["providers"] if item["name"] == "codex")
            root_a_value = str(root_a.resolve())
            commands = {
                "configure": codex["configure_command"],
                "import": codex["import_command"],
                "capture": [
                    "ai-dememory",
                    "--root",
                    root_a_value,
                    "capture",
                    "text",
                    "--text",
                    "Review candidate.",
                ],
            }
            original_cwd = Path.cwd()
            try:
                os.chdir(root_b)
                with (
                    patch("ai_dememory_tool.cli.configure_imports"),
                    patch(
                        "ai_dememory_tool.cli.importlib.import_module",
                        return_value=CapturedModule,
                    ),
                ):
                    for command in commands.values():
                        with patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}):
                            self.assertEqual(cli_main(command[1:]), 0)
            finally:
                os.chdir(original_cwd)

        self.assertEqual(len(CapturedModule.dispatched), 3)
        for action, dispatched in zip(("configure", "import", "capture"), CapturedModule.dispatched):
            self.assertEqual(Path(str(dispatched["root"])), root_a.resolve())
            self.assertEqual(dispatched["argv"][0], action)
            self.assertNotIn("--root", dispatched["argv"])
            self.assertNotEqual(Path(str(dispatched["root"])), root_b.resolve())

    def test_mcp_provider_setup_plan_binds_commands_to_the_invocation_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            expected_root = str(root.resolve())
            plan = call_tool("memory.providers_plan", {}, root)

        for provider in plan["providers"]:
            for key in (
                "configure_dry_run_command",
                "configure_command",
                "disable_command",
                "import_dry_run_command",
                "import_command",
            ):
                command = provider[key]
                self.assertEqual(command[:3], ["ai-dememory", "--root", expected_root])
                self.assertEqual(command.count("--root"), 1)

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

            plan = setup_plan(root, client="codex", mode="both", command="ai-dememory", image=PINNED_TEST_IMAGE)
            mcp_configs = plan["commands"]["mcp_configs"]
            generated_reports = plan["commands"]["generated_reports"]
            generated_archive_status = plan["commands"]["generated_archive_status"]
            generated_archive_retention = plan["commands"]["generated_archive_retention"]
            setup_preview = plan["commands"]["setup_preview"]
            setup_apply = plan["commands"]["setup_apply"]
            onboarding_preview = plan["commands"]["optional_onboarding_preview"]
            onboarding_apply = plan["commands"]["optional_onboarding_apply"]

        self.assertFalse(plan["mutates_system"])
        self.assertFalse(plan["writes_files"])
        self.assertFalse(plan["reads_provider_files"])
        self.assertFalse(plan["writes_import_candidates"])
        self.assertFalse(plan["installs_schedules"])
        self.assertFalse(plan["installs_hooks"])
        self.assertTrue(plan["docker_schedule_installable"])
        self.assertTrue(plan["suggests_generated_reports"])
        self.assertTrue(plan["suggests_generated_archive_status"])
        self.assertTrue(plan["suggests_generated_archive_retention"])
        commands = plan["commands"]
        root_prefix = ["ai-dememory", "--root", str(root)]
        emitted_commands: list[list[str]] = []
        for value in commands.values():
            if isinstance(value, dict):
                emitted_commands.extend(value.values())
            elif isinstance(value, list) and value:
                if all(isinstance(argument, str) for argument in value):
                    emitted_commands.append(value)
                else:
                    emitted_commands.extend(value)
        for provider in plan["provider_plan"]["providers"]:
            for key in (
                "configure_dry_run_command",
                "configure_command",
                "disable_command",
                "import_dry_run_command",
                "import_command",
            ):
                emitted_commands.append(provider[key])

        self.assertGreater(len(emitted_commands), 20)
        for emitted in emitted_commands:
            self.assertIsInstance(emitted, list)
            self.assertTrue(all(isinstance(argument, str) for argument in emitted))
            self.assertEqual(emitted[:3], root_prefix)
            self.assertEqual(emitted.count("--root"), 1)

        self.assertEqual(setup_preview[:5], [*root_prefix, "setup", "wizard"])
        self.assertNotIn("--require-version", setup_preview)
        self.assertIn("--json", setup_preview)
        self.assertIn("--apply", setup_apply)
        self.assertIn("--expect-plan-sha256", setup_apply)
        self.assertEqual(onboarding_preview[:4], [*root_prefix, "onboard"])
        self.assertIn("<reviewed-onboarding.json>", onboarding_preview)
        self.assertNotIn("--apply", onboarding_preview)
        self.assertIn("--apply", onboarding_apply)
        self.assertEqual(commands["provider_plan"], [*root_prefix, "providers", "plan", "--json"])
        self.assertEqual(commands["schedule_environment"], [*root_prefix, "schedule", "doctor", "--json"])
        self.assertEqual(
            commands["schedule_plan"],
            [*root_prefix, "schedule", "plan", "--intensity", "balanced", "--json"],
        )
        self.assertEqual(
            commands["schedule_cron"],
            [*root_prefix, "schedule", "cron", "--intensity", "balanced"],
        )
        self.assertEqual(
            commands["docker_schedule_environment"],
            [*root_prefix, "schedule", "doctor", "--json", "--mode", "docker"],
        )
        self.assertEqual(
            commands["docker_schedule_plan"],
            [
                *root_prefix,
                "schedule",
                "plan",
                "--json",
                "--mode",
                "docker",
                "--intensity",
                "balanced",
                "--image",
                PINNED_TEST_IMAGE,
            ],
        )
        self.assertEqual(
            commands["docker_schedule_cron"],
            [
                *root_prefix,
                "schedule",
                "cron",
                "--intensity",
                "balanced",
                "--mode",
                "docker",
                "--image",
                PINNED_TEST_IMAGE,
            ],
        )
        self.assertEqual(
            generated_reports["recall_review_plan"],
            [*root_prefix, "recall-fixtures", "review-plan", "--write-report"],
        )
        self.assertEqual(
            generated_reports["recall_review_packet"],
            [*root_prefix, "recall-fixtures", "packet", "--write-report"],
        )
        self.assertEqual(
            generated_reports["manual_acceptance_plan"],
            [*root_prefix, "acceptance", "plan", "--write-report"],
        )
        self.assertEqual(
            generated_reports["manual_acceptance_packet"],
            [*root_prefix, "acceptance", "packet", "--write-report"],
        )
        self.assertEqual(
            generated_reports["hook_capture_review"],
            [*root_prefix, "hooks", "captures", "--write-report"],
        )
        self.assertEqual(generated_reports["release_evidence"], [*root_prefix, "release-evidence", "--write-report"])
        self.assertEqual(
            generated_archive_status["recall_review_packets"],
            [*root_prefix, "recall-fixtures", "packet-archive-status", "--json"],
        )
        self.assertEqual(
            generated_archive_status["manual_acceptance_packets"],
            [*root_prefix, "acceptance", "packet-archive-status", "--json"],
        )
        self.assertEqual(
            generated_archive_retention["recall_review_packets"],
            [*root_prefix, "recall-fixtures", "packet-archive-retention-plan", "--json"],
        )
        self.assertEqual(
            generated_archive_retention["manual_acceptance_packets"],
            [*root_prefix, "acceptance", "packet-archive-retention-plan", "--json"],
        )
        self.assertEqual(len(mcp_configs), 2)
        self.assertEqual(mcp_configs[0][:8], [*root_prefix, "mcp-config", "--client", "codex", "--mode", "installed"])
        self.assertIn(["--profile", "core"], [
            mcp_configs[0][index : index + 2]
            for index in range(len(mcp_configs[0]) - 1)
        ])
        for command in mcp_configs:
            self.assertNotIn("--require-version", command)
        self.assertIn("--image", mcp_configs[1])
        self.assertIn("provider_plan", plan)
        assert_setup_plan(
            json.dumps(plan),
            expected_root=root,
        )
        rootless = json.loads(json.dumps(plan))
        rootless["commands"]["daily_maintenance"] = [
            "ai-dememory",
            "maintenance",
            "run",
            "--profile",
            "daily",
        ]
        with self.assertRaisesRegex(InstallSmokeError, "global vault root"):
            assert_setup_plan(
                json.dumps(rootless),
                expected_root=root,
            )

    def test_setup_plan_command_keeps_its_root_when_run_from_another_vault(self) -> None:
        class CapturedModule:
            dispatched: dict[str, object] = {}

            @staticmethod
            def main(argv: list[str]) -> int:
                CapturedModule.dispatched = {
                    "root": os.environ.get("AI_DEMEMORY_ROOT"),
                    "argv": list(argv),
                }
                return 0

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            vault_a = parent / "vault-a"
            vault_b = parent / "vault-b"
            copy_template_tree(vault_a)
            copy_template_tree(vault_b)
            original_cwd = Path.cwd()
            try:
                os.chdir(parent)
                plan = setup_plan(
                    Path("vault-a"),
                    client="codex",
                    mode="both",
                    image=PINNED_TEST_IMAGE,
                )
            finally:
                os.chdir(original_cwd)

            command = plan["commands"]["daily_maintenance"]
            emitted_commands: list[list[str]] = []

            def collect_generated_commands(value: object) -> None:
                if isinstance(value, list):
                    if value and value[0] == "ai-dememory":
                        emitted_commands.append(value)
                    else:
                        for item in value:
                            collect_generated_commands(item)
                elif isinstance(value, dict):
                    for item in value.values():
                        collect_generated_commands(item)

            collect_generated_commands(plan["commands"])
            collect_generated_commands(plan["provider_plan"])

            try:
                os.chdir(vault_b)
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}),
                    patch("ai_dememory_tool.cli.configure_imports"),
                    patch(
                        "ai_dememory_tool.cli.importlib.import_module",
                        return_value=CapturedModule,
                    ),
                ):
                    exit_code = cli_main(command[1:])
            finally:
                os.chdir(original_cwd)

        root_prefix = ["ai-dememory", "--root", str(vault_a.resolve())]
        self.assertEqual(plan["root"], str(vault_a.resolve()))
        self.assertGreater(len(emitted_commands), 20)
        for emitted in emitted_commands:
            self.assertEqual(emitted[:3], root_prefix)
            self.assertEqual(emitted.count("--root"), 1)
        self.assertEqual(command[:3], root_prefix)
        self.assertEqual(exit_code, 0)
        self.assertEqual(Path(str(CapturedModule.dispatched["root"])), vault_a.resolve())
        self.assertEqual(
            CapturedModule.dispatched["argv"],
            ["run", "--profile", "daily"],
        )
        self.assertNotEqual(Path(str(CapturedModule.dispatched["root"])), vault_b.resolve())

    def test_setup_plan_mcp_config_uses_the_global_root_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            vault_a = parent / "vault-a"
            vault_b = parent / "vault-b"
            copy_template_tree(vault_a)
            copy_template_tree(vault_b)
            output = io.StringIO()
            original_cwd = Path.cwd()
            try:
                os.chdir(parent)
                direct_command = mcp_config_command(
                    "ai-dememory",
                    "codex",
                    "installed",
                    Path("vault-a"),
                    PINNED_TEST_IMAGE,
                    600,
                    "core",
                )
                command = setup_plan(Path("vault-a"), client="codex")["commands"]["mcp_configs"][0]
            finally:
                os.chdir(original_cwd)

            try:
                os.chdir(vault_b)
                with patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}), redirect_stdout(output):
                    exit_code = cli_main(command[1:])
            finally:
                os.chdir(original_cwd)

        config = tomllib.loads(output.getvalue())["mcp_servers"]["ai-dememory"]
        root_prefix = ["ai-dememory", "--root", str(vault_a.resolve())]
        self.assertEqual(direct_command[:3], root_prefix)
        self.assertEqual(command[:3], root_prefix)
        self.assertEqual(exit_code, 0)
        self.assertEqual(Path(config["env"]["AI_DEMEMORY_ROOT"]), vault_a.resolve())

    def test_setup_plan_accepts_prebound_nested_provider_commands_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            prebound = [
                "ai-dememory",
                "--root",
                str(vault.resolve()),
                "providers",
                "configure",
                "codex",
                "--path",
                str((Path(tmp) / "provider").resolve()),
            ]
            with patch(
                "setup_plan.provider_setup_plan",
                return_value={"providers": [{"configure_command": prebound}]},
            ):
                plan = setup_plan(vault)

        emitted = plan["provider_plan"]["providers"][0]["configure_command"]
        self.assertEqual(emitted, prebound)
        self.assertEqual(emitted.count("--root"), 1)

    def test_setup_plan_rejects_nested_provider_commands_bound_to_another_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_a = Path(tmp) / "vault-a"
            vault_b = Path(tmp) / "vault-b"
            vault_a.mkdir()
            vault_b.mkdir()
            wrong_root_command = [
                "ai-dememory",
                "--root",
                str(vault_b),
                "providers",
                "configure",
                "codex",
                "--path",
                str(Path(tmp) / "provider"),
            ]
            with (
                patch(
                    "setup_plan.provider_setup_plan",
                    return_value={"providers": [{"configure_command": wrong_root_command}]},
                ),
                self.assertRaisesRegex(ValueError, "different vault root"),
            ):
                setup_plan(vault_a)

    def test_setup_plan_rejects_nested_provider_commands_with_duplicate_root_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            duplicate_root_command = [
                "ai-dememory",
                "--root",
                str(vault),
                "providers",
                "configure",
                "codex",
                "--path",
                str(Path(tmp) / "provider"),
                "--root",
                str(vault),
            ]
            with (
                patch(
                    "setup_plan.provider_setup_plan",
                    return_value={"providers": [{"configure_command": duplicate_root_command}]},
                ),
                self.assertRaisesRegex(ValueError, "exactly one global --root binding"),
            ):
                setup_plan(vault)

    def test_setup_plan_direct_script_prefers_source_over_stale_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            shadow = Path(tmp) / "shadow" / "ai_dememory_tool"
            shadow.mkdir(parents=True)
            (shadow / "__init__.py").write_text(
                '__version__ = "2.0.0"\n',
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(shadow.parent)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "setup_plan.py"),
                    "--root",
                    str(root),
                    "plan",
                    "--client",
                    "codex",
                    "--mode",
                    "both",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["generated_by_version"], PACKAGE_VERSION)
        self.assertEqual(payload["mode"], "both")
        self.assertEqual(len(payload["commands"]["mcp_configs"]), 2)
        for command in payload["commands"]["mcp_configs"]:
            self.assertNotIn("--require-version", command)

    def test_setup_plan_accepts_legacy_version_arguments_after_an_upgrade(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stdout", output):
            copy_template_tree(Path(tmp))
            expected_root = str(Path(tmp).resolve())
            exit_code = setup_plan_main(
                ["--root", tmp, "plan", "--require-version", "0.0.0", "--json"]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["root"], expected_root)
        for command in payload["commands"]["mcp_configs"]:
            self.assertNotIn("--require-version", command)

    def test_release_smoke_direct_scripts_start_without_installed_package(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        for script in ("install_smoke.py", "package_build_smoke.py"):
            with self.subTest(script=script):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPTS / script), "--help"],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertIn("usage:", completed.stdout)

    def test_setup_plan_hides_mutating_docker_schedule_commands_for_mutable_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = setup_plan(Path(tmp), image="ai-dememory:latest")

        self.assertFalse(plan["docker_schedule_installable"])
        self.assertEqual(plan["commands"]["docker_schedule_dry_run"], [])
        self.assertEqual(plan["commands"]["docker_schedule_cron"], [])
        self.assertIn("Resolve the Docker image", plan["next_actions"][0])

    def test_setup_plan_rejects_option_shaped_docker_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for image in ("--privileged", "--volume=/:/host"):
                with self.subTest(image=image), self.assertRaises(ValueError):
                    setup_plan(Path(tmp), mode="docker", image=image)

        for argv in (
            ["plan", "--mo", "docker"],
            ["plan", "--mode", "installed", "--mode", "docker"],
            ["plan", "--image", "ai-dememory:local", "--image", "--privileged"],
        ):
            with self.subTest(argv=argv), patch("sys.stderr", io.StringIO()), self.assertRaises(
                SystemExit
            ) as raised:
                setup_plan_main(argv)
            self.assertEqual(raised.exception.code, 2)

    def test_setup_plan_human_output_includes_generated_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            copy_template_tree(root)
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = setup_plan_main(["--root", str(root), "plan"])

        self.assertEqual(exit_code, 0)
        command_prefix = ["ai-dememory", "--root", str(root)]
        self.assertIn("- generated_reports:", output.getvalue())
        self.assertIn(
            "- schedule_plan: "
            + render_copy_command(
                [*command_prefix, "schedule", "plan", "--intensity", "balanced", "--json"]
            ),
            output.getvalue(),
        )
        self.assertIn(
            "- schedule_cron: "
            + render_copy_command(
                [*command_prefix, "schedule", "cron", "--intensity", "balanced"]
            ),
            output.getvalue(),
        )
        self.assertIn(
            "recall_review_packet: "
            + render_copy_command(
                [*command_prefix, "recall-fixtures", "packet", "--write-report"]
            ),
            output.getvalue(),
        )
        self.assertIn(
            "recall_review_packets: "
            + render_copy_command(
                [*command_prefix, "recall-fixtures", "packet-archive-status", "--json"]
            ),
            output.getvalue(),
        )
        self.assertIn(
            "recall_review_packets: "
            + render_copy_command(
                [
                    *command_prefix,
                    "recall-fixtures",
                    "packet-archive-retention-plan",
                    "--json",
                ]
            ),
            output.getvalue(),
        )
        self.assertIn(
            "manual_acceptance_plan: "
            + render_copy_command([*command_prefix, "acceptance", "plan", "--write-report"]),
            output.getvalue(),
        )
        self.assertIn(
            "manual_acceptance_packet: "
            + render_copy_command([*command_prefix, "acceptance", "packet", "--write-report"]),
            output.getvalue(),
        )
        self.assertIn(
            "manual_acceptance_packets: "
            + render_copy_command(
                [*command_prefix, "acceptance", "packet-archive-status", "--json"]
            ),
            output.getvalue(),
        )
        self.assertIn(
            "manual_acceptance_packets: "
            + render_copy_command(
                [
                    *command_prefix,
                    "acceptance",
                    "packet-archive-retention-plan",
                    "--json",
                ]
            ),
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

    def test_maintenance_preflights_review_state_before_preview_or_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "[false_positives]\n"
                "enabled = false\n"
                "[conflicts]\n"
                "enabled = true\n",
                encoding="utf-8",
            )
            review_state = root / ".ai-dememory-ignore.toml"
            canary = b"review-state-bytes-must-not-escape"
            review_state.write_bytes(b"\xff" + canary)

            def snapshot() -> list[tuple[str, bool, bytes | None]]:
                return [
                    (
                        path.relative_to(root).as_posix(),
                        path.is_dir(),
                        path.read_bytes() if path.is_file() else None,
                    )
                    for path in sorted(root.rglob("*"))
                ]

            before = snapshot()
            with (
                patch("maintenance.enabled_providers") as providers,
                patch("maintenance.import_chats") as importer,
                patch("maintenance.maintenance_lock") as lock,
                patch("maintenance.rebuild_index") as index_writer,
                patch("maintenance.safe_write_text") as file_writer,
            ):
                for profile in ("daily", "weekly"):
                    for label, operation in (
                        ("apply", run_maintenance),
                        ("preview", dry_run_maintenance),
                    ):
                        with self.subTest(profile=profile, operation=label):
                            with self.assertRaises(ReviewError) as raised:
                                operation(root, profile)
                            diagnostic = str(raised.exception)
                            self.assertNotIn(canary.decode("ascii"), diagnostic)
                            self.assertNotIn("Traceback", diagnostic)
                            self.assertEqual(snapshot(), before)

                for profile in ("daily", "weekly"):
                    for dry_run in (False, True):
                        with self.subTest(profile=profile, cli_dry_run=dry_run):
                            output = io.StringIO()
                            error = io.StringIO()
                            command = [
                                "--root",
                                str(root),
                                "run",
                                "--profile",
                                profile,
                            ]
                            if dry_run:
                                command.extend(["--dry-run", "--json"])
                            with redirect_stdout(output), redirect_stderr(error):
                                exit_code = maintenance_main(command)
                            self.assertEqual(exit_code, 1)
                            self.assertEqual(output.getvalue(), "")
                            self.assertIn("review state", error.getvalue())
                            self.assertNotIn(canary.decode("ascii"), error.getvalue())
                            self.assertNotIn("traceback", error.getvalue().lower())
                            self.assertEqual(snapshot(), before)

                with self.assertRaises(ReviewError) as status_error:
                    maintenance_status(root)
                self.assertNotIn(canary.decode("ascii"), str(status_error.exception))
                status_output = io.StringIO()
                status_stderr = io.StringIO()
                with redirect_stdout(status_output), redirect_stderr(status_stderr):
                    status_exit = maintenance_main(
                        ["--root", str(root), "status", "--json"]
                    )
                self.assertEqual(status_exit, 2)
                self.assertEqual(status_output.getvalue(), "")
                self.assertIn("review state", status_stderr.getvalue())
                self.assertNotIn(canary.decode("ascii"), status_stderr.getvalue())
                self.assertNotIn("traceback", status_stderr.getvalue().lower())
                self.assertEqual(snapshot(), before)

            providers.assert_not_called()
            importer.assert_not_called()
            lock.assert_not_called()
            index_writer.assert_not_called()
            file_writer.assert_not_called()

    def test_maintenance_reports_invalid_resource_policy_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            set_section(root, "resources", {"provider_file_limit": 999})

            with self.assertRaisesRegex(ValueError, "provider_file_limit"):
                run_maintenance(root, "daily")
            with self.assertRaisesRegex(ValueError, "provider_file_limit"):
                dry_run_maintenance(root, "daily")

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
            initialize_minimal_runtime_vault(root)
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
        self.assertEqual(
            weekly_freshness["next_action"],
            "Run ai-dememory --root <vault-path> maintenance run --profile weekly.",
        )
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

        namespace = schedule_namespace(root)
        self.assertEqual(
            {command.name for command in commands},
            {f"{namespace}-daily", f"{namespace}-weekly"},
        )
        self.assertTrue(all(command.command[0] == "schtasks" for command in commands))
        self.assertTrue(any("/SC" in command.command for command in commands))
        self.assertTrue(any(command.run_command and command.run_command[0] == "ai-dememory" for command in commands))
        daily = next(command for command in commands if command.name.endswith("-daily"))
        self.assertEqual(daily.run_command[:4], ["ai-dememory", "--root", str(root), "maintenance"])
        self.assertIn("--timeout-seconds", daily.run_command)
        self.assertEqual(daily.run_command[daily.run_command.index("--timeout-seconds") + 1], "300")

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

        daily = next(command for command in commands if command.name.endswith("-daily"))
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

        daily = next(command for command in commands if command.name.endswith("-daily"))
        run_line = daily.command[daily.command.index("/TR") + 1]
        volume_arg = f"{root}:/memory"
        self.assertIn(f'-v "{volume_arg}"', run_line)
        self.assertNotIn(f"'{volume_arg}'", run_line)
        self.assertIn("ai-dememory:test --root /memory maintenance run --profile daily", run_line)
        self.assertIn("--timeout-seconds 300", run_line)

    def test_schedule_plan_human_output_uses_copy_safe_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault'$(Write-Output PWNED);"
            initialize_minimal_runtime_vault(root)
            plan = schedule_plan(root, target_platform="windows")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = schedule_main(
                    ["--root", str(root), "plan", "--platform", "windows"]
                )

        first_command = plan["commands"][0]
        self.assertEqual(exit_code, 0)
        self.assertIn(
            f"- {first_command['name']}: "
            + render_copy_command(first_command["command"], windows=True),
            output.getvalue(),
        )

    def test_schedule_cron_export_generates_installed_and_docker_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = build_cron_entries(root, daily_time="01:15", weekly_day="MON", weekly_time="02:30")
            docker = build_cron_entries(
                root,
                mode="docker",
                image=PINNED_TEST_IMAGE,
                daily_time="03:05",
                weekly_day="SAT",
                weekly_time="04:10",
            )
            rendered = render_cron_entries(installed)

        self.assertEqual(installed[0].schedule, "15 1 * * *")
        self.assertEqual(installed[1].schedule, "30 2 * * 1")
        self.assertIn("ai-dememory --root", installed[0].line)
        self.assertIn("maintenance run --profile daily --timeout-seconds 300", installed[0].line)
        self.assertEqual(docker[0].schedule, "5 3 * * *")
        self.assertEqual(docker[1].schedule, "10 4 * * 6")
        self.assertEqual(docker[0].command[:2], ["docker", "run"])
        self.assertIn(PINNED_TEST_IMAGE, docker[0].command)
        self.assertIn("# ai-dememory maintenance schedule", rendered)

    def test_generated_installed_schedule_command_is_accepted_by_unified_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            daily = build_cron_entries(root, daily_enabled=True, weekly_enabled=False)[0]
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = cli_main([*daily.command[1:], "--dry-run", "--json"])
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["profile"], "daily")
        self.assertTrue(payload["dry_run"])
        self.assertFalse((root / "indexes").exists())

    def test_supervised_maintenance_keeps_the_source_checkout_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            report_dir = Path("reports/maintenance")
            with patch(
                "maintenance.run_supervised_process",
                return_value=(0, False, 1234),
            ) as supervised_process:
                self.assertEqual(
                    run_supervised_maintenance(
                        root,
                        "daily",
                        report_dir,
                        300,
                        json_output=True,
                    ),
                    0,
                )

        supervised_process.assert_called_once_with(
            [
                sys.executable,
                str(ROOT / "scripts" / "ai_dememory.py"),
                "--root",
                str(root),
                "maintenance",
                "run",
                "--profile",
                "daily",
                "--report-dir",
                str(report_dir),
                "--json",
            ],
            300,
        )

    def test_supervised_process_terminates_owned_child_at_timeout(self) -> None:
        exit_code, timed_out, pid = run_supervised_process(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            0.1,
        )

        self.assertEqual(exit_code, TIMEOUT_EXIT_CODE)
        self.assertTrue(timed_out)
        self.assertFalse(process_is_running(pid))

    def test_supervised_process_terminates_owned_descendant_tree_at_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            child_pid_path = Path(tmp) / "child.pid"
            child_code = "import time; time.sleep(30)"
            parent_code = (
                "from pathlib import Path; import subprocess, sys, time; "
                f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
                f"Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='utf-8'); "
                "time.sleep(30)"
            )
            exit_code, timed_out, parent_pid = run_supervised_process(
                [sys.executable, "-c", parent_code],
                1,
            )
            child_pid = int(child_pid_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, TIMEOUT_EXIT_CODE)
        self.assertTrue(timed_out)
        self.assertFalse(process_is_running(parent_pid))
        self.assertFalse(process_is_running(child_pid))

    def test_supervised_process_reaps_descendant_after_leader_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            child_pid_path = Path(tmp) / "child.pid"
            child_code = "import time; time.sleep(30)"
            parent_code = (
                "from pathlib import Path; import subprocess, sys; "
                f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
                f"Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='utf-8')"
            )
            exit_code, timed_out, parent_pid = run_supervised_process(
                [sys.executable, "-c", parent_code],
                5,
            )
            child_pid = int(child_pid_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertFalse(timed_out)
        self.assertFalse(process_is_running(parent_pid))
        self.assertFalse(process_is_running(child_pid))

    def test_maintenance_lock_recovers_stale_legacy_lock_and_preserves_live_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "indexes" / ".maintenance.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("2000-01-01T00:00:00+00:00", encoding="utf-8")

            with maintenance_lock(root, stale_after_seconds=1):
                record = read_lock_record(lock_path)
                self.assertEqual(record["pid"], os.getpid())
                with self.assertRaisesRegex(RuntimeError, "maintenance already running"):
                    with maintenance_lock(root, stale_after_seconds=1):
                        pass

            self.assertFalse(lock_path.exists())

    def test_schedule_cron_export_shell_quotes_metacharacters(self) -> None:
        root = Path("vault's;$(touch pwn)`")
        installed = build_cron_entries(root, command="ai-dememory;touch pwn")
        docker = build_cron_entries(root, mode="docker", image=PINNED_TEST_IMAGE)

        self.assertIn("'ai-dememory;touch pwn'", installed[0].line)
        self.assertIn("'vault'\"'\"'s;$(touch pwn)`'", installed[0].line)
        self.assertNotIn(" ai-dememory;touch pwn maintenance ", installed[0].line)
        self.assertIn("'vault'\"'\"'s;$(touch pwn)`:/memory'", docker[0].line)
        self.assertIn(PINNED_TEST_IMAGE, docker[0].line)
        with self.assertRaisesRegex(ValueError, "immutable sha256"):
            build_cron_entries(root, mode="docker", image="ai-dememory:local;touch pwn")

    def test_schedule_plan_cli_reports_commands_and_cron_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = initialize_minimal_runtime_vault(root)
            config_before = config_path.read_bytes()
            output = io.StringIO()

            plan = schedule_plan(
                root,
                target_platform="linux",
                mode="docker",
                image=PINNED_TEST_IMAGE,
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
                        PINNED_TEST_IMAGE,
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
            config_after = config_path.read_bytes()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, plan)
        self.assertEqual(payload["action"], "install")
        self.assertEqual(payload["platform"], "linux")
        self.assertEqual(payload["mode"], "docker")
        self.assertTrue(payload["docker_image_immutable"])
        self.assertTrue(payload["installable"])
        self.assertFalse(payload["mutates_system"])
        self.assertFalse(payload["runs_commands"])
        self.assertFalse(payload["writes_files"])
        self.assertFalse(payload["installs_schedules"])
        self.assertEqual(config_after, config_before)
        self.assertTrue(any(command["command"][:2] == ["systemctl", "--user"] for command in payload["commands"]))
        self.assertTrue(any(entry["command"][:2] == ["docker", "run"] for entry in payload["cron_entries"]))

    def test_schedule_plan_blocks_invalid_resource_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            set_section(root, "resources", {"provider_file_limit": 999})

            plan = schedule_plan(root, target_platform="windows")

        self.assertFalse(plan["resource_policy_valid"])
        self.assertFalse(plan["installable"])
        self.assertEqual(plan["commands"], [])
        self.assertEqual(plan["cron_entries"], [])
        self.assertEqual(plan["apply_command"], [])
        self.assertTrue(
            any("provider_file_limit" in error for error in plan["validation_errors"])
        )
        self.assertIn("Fix the invalid resource policy", plan["next_actions"][0])

    def test_schedule_install_refuses_invalid_resource_policy_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            set_section(root, "resources", {"provider_file_limit": 999})
            plan = schedule_plan(root, target_platform="windows")
            config_path = root / ".ai-dememory.toml"
            config_before = config_path.read_text(encoding="utf-8")
            error = io.StringIO()

            with (
                patch("schedule_memory.write_platform_schedule_files") as write_files,
                patch("schedule_memory.run_install_commands") as run_install,
                redirect_stderr(error),
            ):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

            config_after = config_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertIn("provider_file_limit", error.getvalue())
        self.assertEqual(config_after, config_before)
        write_files.assert_not_called()
        run_install.assert_not_called()

    def test_schedule_cron_refuses_invalid_resource_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            set_section(root, "resources", {"provider_file_limit": 999})
            output = io.StringIO()
            error = io.StringIO()

            with redirect_stdout(output), redirect_stderr(error):
                exit_code = schedule_main(
                    ["--root", str(root), "cron", "--json"]
                )

        self.assertEqual(exit_code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("provider_file_limit", error.getvalue())

    def test_schedule_install_rechecks_policy_immediately_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            plan = schedule_plan(root, target_platform="windows")
            error = io.StringIO()

            def invalidate_policy(expected: str, actual: str) -> bool:
                set_section(root, "resources", {"provider_file_limit": 999})
                return expected == actual

            with (
                patch("schedule_memory.hmac.compare_digest", side_effect=invalidate_policy),
                patch("schedule_memory.write_platform_schedule_files") as write_files,
                patch("schedule_memory.run_install_commands") as run_install,
                redirect_stderr(error),
            ):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("changed or is invalid", error.getvalue())
        self.assertIn("provider_file_limit", error.getvalue())
        write_files.assert_not_called()
        run_install.assert_not_called()

    def test_schedule_namespaces_and_fingerprints_are_stable_per_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_root = Path(tmp) / "first-vault"
            second_root = Path(tmp) / "second-vault"
            first_root.mkdir()
            second_root.mkdir()
            first = schedule_plan(first_root, target_platform="windows")
            repeated = schedule_plan(first_root, target_platform="windows")
            second = schedule_plan(second_root, target_platform="windows")

        self.assertEqual(first["task_namespace"], repeated["task_namespace"])
        self.assertEqual(first["plan_sha256"], repeated["plan_sha256"])
        self.assertNotEqual(first["task_namespace"], second["task_namespace"])
        self.assertNotEqual(first["plan_sha256"], second["plan_sha256"])
        self.assertTrue(
            all(
                command["name"].startswith(f"{first['task_namespace']}-")
                for command in first["commands"]
            )
        )

    def test_schedule_intensity_controls_cadence_and_docker_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            minimal = schedule_plan(
                root,
                target_platform="windows",
                mode="docker",
                intensity="minimal",
            )
            active = schedule_plan(
                root,
                target_platform="windows",
                mode="docker",
                intensity="active",
            )

        self.assertFalse(minimal["schedule"]["daily_enabled"])
        self.assertTrue(minimal["schedule"]["weekly_enabled"])
        self.assertEqual(len(minimal["commands"]), 1)
        minimal_run = minimal["commands"][0]["run_command"]
        self.assertEqual(minimal_run[minimal_run.index("--cpus") + 1], "0.5")
        self.assertEqual(minimal_run[minimal_run.index("--memory") + 1], "256m")
        self.assertEqual(minimal_run[minimal_run.index("--pids-limit") + 1], "64")
        self.assertEqual(len(active["commands"]), 2)
        active_run = active["commands"][0]["run_command"]
        self.assertEqual(active_run[active_run.index("--cpus") + 1], "2.0")
        self.assertEqual(active_run[active_run.index("--memory") + 1], "1g")
        self.assertEqual(active_run[active_run.index("--pids-limit") + 1], "256")

    def test_schedule_refuses_mutable_docker_image_for_unattended_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = initialize_minimal_runtime_vault(root)
            config_before = config_path.read_bytes()
            plan = schedule_plan(
                root,
                target_platform="windows",
                mode="docker",
                image="ai-dememory:latest",
            )
            error = io.StringIO()

            with redirect_stderr(error):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--mode",
                        "docker",
                        "--image",
                        "ai-dememory:latest",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )
            config_after = config_path.read_bytes()

        self.assertFalse(plan["docker_image_immutable"])
        self.assertFalse(plan["installable"])
        self.assertEqual(plan["apply_command"], [])
        self.assertEqual(plan["cron_entries"], [])
        self.assertEqual(exit_code, 2)
        self.assertIn("immutable", error.getvalue())
        self.assertEqual(config_after, config_before)

    def test_windows_schedule_install_does_not_force_replace_existing_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            commands = build_schedule_commands(
                Path(tmp),
                "install",
                target_platform="windows",
            )

        self.assertTrue(commands)
        self.assertTrue(all("/F" not in command.command for command in commands))

    def test_schedule_install_requires_exact_plan_and_records_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = initialize_minimal_runtime_vault(root)
            config_before = config_path.read_bytes()
            plan = schedule_plan(root, target_platform="windows")
            with redirect_stderr(io.StringIO()):
                mismatch = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        "0" * 64,
                    ]
                )
            self.assertEqual(mismatch, 2)
            self.assertEqual(config_path.read_bytes(), config_before)

            with patch("schedule_memory.run_install_commands", return_value=(1, True)), redirect_stderr(
                io.StringIO()
            ):
                failed = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )
            self.assertEqual(failed, 1)
            self.assertEqual(config_path.read_bytes(), config_before)

            definition_digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            with patch("schedule_memory.run_install_commands", return_value=(0, True)), patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=(definition_digests, []),
            ):
                installed = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )
            before_verification = schedule_status(root, target_platform="windows")
            with self.assertRaisesRegex(ValueError, "differ"):
                mark_schedule_verified(root, {"task:forged": "b" * 64})

        self.assertEqual(installed, 0)
        self.assertTrue(before_verification["install_receipt_valid"])
        self.assertTrue(before_verification["host_state_verified"])

    def test_schedule_status_clears_verification_on_definition_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = {"task:daily": "a" * 64}
            plan = schedule_plan(
                root,
                target_platform="windows",
                daily_time="01:15",
                weekly_day="MON",
                weekly_time="02:30",
            )
            configure_schedule(
                root,
                "01:15",
                "MON",
                "02:30",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests=expected,
            )

            with patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=({"task:daily": "c" * 64}, []),
            ), redirect_stderr(io.StringIO()):
                exit_code = schedule_main(
                    ["--root", str(root), "status", "--platform", "windows"]
                )
            status = schedule_status(root, target_platform="windows")

        self.assertEqual(exit_code, 1)
        self.assertTrue(status["install_receipt_valid"])
        self.assertFalse(status["host_state_verified"])

    def test_schedule_receipt_failure_rolls_back_installed_host_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = initialize_minimal_runtime_vault(root)
            config_before = config_path.read_bytes()
            plan = schedule_plan(root, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }

            with patch("schedule_memory.run_install_commands", return_value=(0, True)), patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=(digests, []),
            ), patch("schedule_memory._configure_schedule", side_effect=OSError("disk full")), patch(
                "schedule_memory.run_commands",
                return_value=0,
            ) as rollback, redirect_stderr(io.StringIO()):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )
            config_after = config_path.read_bytes()

        self.assertEqual(exit_code, 1)
        self.assertTrue(rollback.called)
        self.assertEqual(config_after, config_before)

    def test_linux_install_verification_failure_reloads_restored_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            definition = root / "owned.service"
            plan = schedule_plan(root, target_platform="linux")
            error = io.StringIO()

            with patch(
                "schedule_memory.platform_schedule_paths",
                return_value=[definition],
            ), patch(
                "schedule_memory.write_platform_schedule_files",
                return_value=[definition],
            ), patch(
                "schedule_memory.run_install_commands",
                return_value=(0, True),
            ), patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=({}, ["host readback failed"]),
            ), patch(
                "schedule_memory.run_commands",
                return_value=0,
            ) as host_rollback, patch(
                "schedule_memory.restore_schedule_files",
                return_value=True,
            ) as file_rollback, patch(
                "schedule_memory.run_schedule_command",
                return_value=(0, False, 101),
            ) as reload_command, redirect_stderr(error):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "linux",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

            payload = json.loads(error.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertTrue(payload["rollback_complete"])
        self.assertEqual(payload["verification_errors"], ["host readback failed"])
        host_rollback.assert_called_once()
        file_rollback.assert_called_once()
        reload_command.assert_called_once()
        compensation = reload_command.call_args.args[0]
        self.assertEqual(compensation.platform, "linux")
        self.assertEqual(compensation.action, "restore")
        self.assertEqual(
            compensation.command,
            ["systemctl", "--user", "daemon-reload"],
        )

    def test_linux_receipt_failure_reports_incomplete_if_compensating_reload_times_out(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            definition = root / "owned.service"
            plan = schedule_plan(root, target_platform="linux")
            error = io.StringIO()

            with patch(
                "schedule_memory.platform_schedule_paths",
                return_value=[definition],
            ), patch(
                "schedule_memory.write_platform_schedule_files",
                return_value=[definition],
            ), patch(
                "schedule_memory.run_install_commands",
                return_value=(0, True),
            ), patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=({}, []),
            ), patch(
                "schedule_memory._configure_schedule",
                side_effect=OSError("receipt unavailable"),
            ), patch(
                "schedule_memory.run_commands",
                return_value=0,
            ), patch(
                "schedule_memory.restore_schedule_files",
                return_value=True,
            ), patch(
                "schedule_memory.run_schedule_command",
                return_value=(124, True, 102),
            ) as reload_command, redirect_stderr(error):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "linux",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

            payload = json.loads(error.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["rollback_complete"])
        self.assertIn("schedule receipt write failed", payload["error"])
        reload_command.assert_called_once()

    def test_schedule_command_batch_stops_without_rollback_after_lock_loss(self) -> None:
        commands = build_schedule_commands(
            Path("D:/vault"),
            "install",
            target_platform="windows",
        )
        rollback_commands = build_schedule_commands(
            Path("D:/vault"),
            "remove",
            target_platform="windows",
        )
        validations = 0

        def validate() -> None:
            nonlocal validations
            validations += 1
            if validations == 2:
                raise ConfigError("config_lock_error", source="schedule")

        with patch(
            "schedule_memory.run_schedule_command",
            return_value=(0, False, 123),
        ) as runner, self.assertRaises(ConfigError):
            run_install_commands(commands, rollback_commands, validate)

        self.assertEqual(runner.call_count, 1)

    def test_schedule_command_batches_compensate_keyboard_interrupt(self) -> None:
        root = Path("D:/vault")
        install_commands = build_schedule_commands(
            root,
            "install",
            target_platform="windows",
        )
        remove_commands = build_schedule_commands(
            root,
            "remove",
            target_platform="windows",
        )
        cases = (
            (run_install_commands, install_commands, remove_commands),
            (run_remove_commands, remove_commands, install_commands),
        )

        for runner_fn, commands, rollback_commands in cases:
            with self.subTest(runner=runner_fn.__name__), patch(
                "schedule_memory.run_schedule_command",
                side_effect=[
                    (0, False, 101),
                    KeyboardInterrupt(),
                    (0, False, 102),
                    (0, False, 103),
                ],
            ) as runner:
                exit_code, rollback_complete = runner_fn(commands, rollback_commands)

            self.assertEqual(exit_code, 130)
            self.assertTrue(rollback_complete)
            self.assertEqual(runner.call_count, 4)
            rolled_back_names = {
                call.args[0].name for call in runner.call_args_list[2:]
            }
            self.assertEqual(
                rolled_back_names,
                {commands[0].name, commands[1].name},
            )

    def test_schedule_command_batches_compensate_timeout_and_oserror(self) -> None:
        root = Path("D:/vault")
        install_commands = build_schedule_commands(
            root,
            "install",
            target_platform="windows",
        )
        remove_commands = build_schedule_commands(
            root,
            "remove",
            target_platform="windows",
        )
        runners = (
            (run_install_commands, install_commands, remove_commands),
            (run_remove_commands, remove_commands, install_commands),
        )
        failures = (
            (subprocess.TimeoutExpired(["scheduler"], 60), 124),
            (OSError("scheduler launch failed"), 1),
        )

        for runner_fn, commands, rollback_commands in runners:
            for failure, expected_exit in failures:
                with self.subTest(
                    runner=runner_fn.__name__,
                    failure=type(failure).__name__,
                ), patch(
                    "schedule_memory.run_schedule_command",
                    side_effect=[
                        (0, False, 101),
                        failure,
                        (0, False, 102),
                        (0, False, 103),
                    ],
                ) as runner:
                    exit_code, rollback_complete = runner_fn(
                        commands,
                        rollback_commands,
                    )

                self.assertEqual(exit_code, expected_exit)
                self.assertTrue(rollback_complete)
                self.assertEqual(runner.call_count, 4)
                self.assertEqual(
                    {
                        call.args[0].name
                        for call in runner.call_args_list[2:]
                    },
                    {commands[0].name, commands[1].name},
                )

    def test_schedule_command_batches_compensate_timeout_return(self) -> None:
        root = Path("D:/vault")
        install_commands = build_schedule_commands(
            root,
            "install",
            target_platform="windows",
        )
        remove_commands = build_schedule_commands(
            root,
            "remove",
            target_platform="windows",
        )

        for runner_fn, commands, rollback_commands in (
            (run_install_commands, install_commands, remove_commands),
            (run_remove_commands, remove_commands, install_commands),
        ):
            with self.subTest(runner=runner_fn.__name__), patch(
                "schedule_memory.run_schedule_command",
                side_effect=[
                    (0, False, 101),
                    (124, True, 102),
                    (0, False, 103),
                    (0, False, 104),
                ],
            ) as runner:
                exit_code, rollback_complete = runner_fn(
                    commands,
                    rollback_commands,
                )

            self.assertEqual(exit_code, 124)
            self.assertTrue(rollback_complete)
            self.assertEqual(runner.call_count, 4)
            self.assertEqual(
                {call.args[0].name for call in runner.call_args_list[2:]},
                {commands[0].name, commands[1].name},
            )

    def test_schedule_install_interrupt_during_readback_restores_owned_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            plan = schedule_plan(root, target_platform="windows")
            error = io.StringIO()

            with patch(
                "schedule_memory.run_install_commands",
                return_value=(0, True),
            ), patch(
                "schedule_memory.observe_schedule_definitions",
                side_effect=KeyboardInterrupt,
            ), patch(
                "schedule_memory.run_commands",
                return_value=0,
            ) as host_rollback, patch(
                "schedule_memory.restore_schedule_files",
                return_value=True,
            ) as file_rollback, patch(
                "schedule_memory._configure_schedule"
            ) as receipt, redirect_stderr(error):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

            payload = json.loads(error.getvalue())

        self.assertEqual(exit_code, 130)
        self.assertTrue(payload["interrupted"])
        self.assertTrue(payload["rollback_complete"])
        host_rollback.assert_called_once()
        file_rollback.assert_called_once()
        receipt.assert_not_called()

    def test_schedule_install_interrupt_during_definition_write_restores_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            plan = schedule_plan(root, target_platform="windows")
            error = io.StringIO()

            with patch(
                "schedule_memory.write_platform_schedule_files",
                side_effect=KeyboardInterrupt,
            ), patch(
                "schedule_memory.restore_schedule_files",
                return_value=True,
            ) as restore, patch(
                "schedule_memory.run_install_commands"
            ) as host_install, redirect_stderr(error):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

            payload = json.loads(error.getvalue())

        self.assertEqual(exit_code, 130)
        self.assertTrue(payload["interrupted"])
        self.assertTrue(payload["rollback_complete"])
        restore.assert_called_once()
        host_install.assert_not_called()

    def test_schedule_receipt_interrupt_distinguishes_before_and_after_commit(self) -> None:
        import schedule_memory

        for commit_before_interrupt in (False, True):
            with self.subTest(commit_before_interrupt=commit_before_interrupt), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                initialize_minimal_runtime_vault(root)
                plan = schedule_plan(root, target_platform="windows")
                digests = {
                    f"task:{command['name']}": "a" * 64
                    for command in plan["commands"]
                }
                real_configure = schedule_memory._configure_schedule

                def interrupt_receipt(*args: object, **kwargs: object) -> None:
                    if commit_before_interrupt:
                        real_configure(*args, **kwargs)  # type: ignore[arg-type]
                    raise KeyboardInterrupt

                error = io.StringIO()
                with patch(
                    "schedule_memory.run_install_commands",
                    return_value=(0, True),
                ), patch(
                    "schedule_memory.observe_schedule_definitions",
                    return_value=(digests, []),
                ), patch(
                    "schedule_memory._configure_schedule",
                    side_effect=interrupt_receipt,
                ), patch(
                    "schedule_memory.run_commands",
                    return_value=0,
                ) as rollback, patch(
                    "schedule_memory.restore_schedule_files",
                    return_value=True,
                ) as file_rollback, redirect_stderr(error):
                    exit_code = schedule_main(
                        [
                            "--root",
                            str(root),
                            "install",
                            "--platform",
                            "windows",
                            "--expect-plan-sha256",
                            str(plan["plan_sha256"]),
                        ]
                    )

                payload = json.loads(error.getvalue())
                receipt = load_config(root).get("schedule", {})

                if commit_before_interrupt:
                    self.assertEqual(exit_code, 0)
                    self.assertTrue(payload["installed"])
                    self.assertTrue(payload["interrupted_after_commit"])
                    self.assertTrue(receipt.get("enabled", False))
                    rollback.assert_not_called()
                    file_rollback.assert_not_called()
                else:
                    self.assertEqual(exit_code, 130)
                    self.assertTrue(payload["interrupted"])
                    self.assertFalse(receipt.get("enabled", False))
                    rollback.assert_called_once()
                    file_rollback.assert_called_once()

    def test_schedule_remove_interrupt_during_file_removal_restores_host_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = schedule_plan(root, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            configure_schedule(
                root,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests=digests,
            )
            error = io.StringIO()

            with patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=(digests, []),
            ), patch(
                "schedule_memory.run_remove_commands",
                return_value=(0, True),
            ), patch(
                "schedule_memory.remove_platform_schedule_files",
                side_effect=KeyboardInterrupt,
            ), patch(
                "schedule_memory.restore_schedule_files",
                return_value=True,
            ) as file_restore, patch(
                "schedule_memory.run_commands",
                return_value=0,
            ) as host_restore, redirect_stderr(error):
                exit_code = schedule_main(
                    ["--root", str(root), "remove", "--platform", "windows"]
                )

            payload = json.loads(error.getvalue())

        self.assertEqual(exit_code, 130)
        self.assertTrue(payload["interrupted"])
        self.assertTrue(payload["rollback_complete"])
        file_restore.assert_called_once()
        host_restore.assert_called_once()

    def test_schedule_sigint_is_deferred_across_install_commit_boundaries(self) -> None:
        import schedule_memory

        phases = (
            "install_files_published",
            "install_host_published",
            "install_readback_complete",
        )
        for phase in phases:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                initialize_minimal_runtime_vault(root)
                plan = schedule_plan(root, target_platform="windows")
                digests = {
                    f"task:{command['name']}": "a" * 64
                    for command in plan["commands"]
                }
                previous_handler = signal.getsignal(signal.SIGINT)
                requested = False

                def request_at_checkpoint(current_phase: str) -> None:
                    nonlocal requested
                    if current_phase != phase or requested:
                        return
                    requested = True
                    installed_handler = signal.getsignal(signal.SIGINT)
                    self.assertTrue(callable(installed_handler))
                    self.assertIsNot(installed_handler, previous_handler)
                    installed_handler(signal.SIGINT, None)  # type: ignore[operator]

                error = io.StringIO()
                with patch(
                    "schedule_memory.run_install_commands",
                    return_value=(0, True),
                ), patch(
                    "schedule_memory.observe_schedule_definitions",
                    return_value=(digests, []),
                ), patch(
                    "schedule_memory._schedule_phase_checkpoint",
                    side_effect=request_at_checkpoint,
                ), redirect_stderr(error):
                    exit_code = schedule_main(
                        [
                            "--root",
                            str(root),
                            "install",
                            "--platform",
                            "windows",
                            "--expect-plan-sha256",
                            str(plan["plan_sha256"]),
                        ]
                    )

                receipt = load_config(root).get("schedule", {})
                self.assertTrue(requested)
                self.assertEqual(exit_code, 130)
                self.assertTrue(receipt.get("enabled", False))
                self.assertIn("consistent transaction boundary", error.getvalue())
                self.assertIs(signal.getsignal(signal.SIGINT), previous_handler)

    def test_schedule_sigint_is_deferred_across_remove_commit_boundaries(self) -> None:
        import schedule_memory

        phases = ("remove_host_published", "remove_files_published")
        for phase in phases:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan = schedule_plan(root, target_platform="windows")
                digests = {
                    f"task:{command['name']}": "a" * 64
                    for command in plan["commands"]
                }
                configure_schedule(
                    root,
                    "03:00",
                    "SUN",
                    "04:00",
                    "installed",
                    "",
                    target_platform="windows",
                    plan_sha256=str(plan["plan_sha256"]),
                    definition_digests=digests,
                )
                previous_handler = signal.getsignal(signal.SIGINT)
                requested = False

                def request_at_checkpoint(current_phase: str) -> None:
                    nonlocal requested
                    if current_phase != phase or requested:
                        return
                    requested = True
                    installed_handler = signal.getsignal(signal.SIGINT)
                    self.assertTrue(callable(installed_handler))
                    self.assertIsNot(installed_handler, previous_handler)
                    installed_handler(signal.SIGINT, None)  # type: ignore[operator]

                error = io.StringIO()
                with patch(
                    "schedule_memory.observe_schedule_definitions",
                    return_value=(digests, []),
                ), patch(
                    "schedule_memory.run_remove_commands",
                    return_value=(0, True),
                ), patch(
                    "schedule_memory._schedule_phase_checkpoint",
                    side_effect=request_at_checkpoint,
                ), redirect_stderr(error):
                    exit_code = schedule_main(
                        ["--root", str(root), "remove", "--platform", "windows"]
                    )

                receipt = load_config(root).get("schedule", {})
                self.assertTrue(requested)
                self.assertEqual(exit_code, 130)
                self.assertFalse(receipt.get("enabled", False))
                self.assertIn("consistent transaction boundary", error.getvalue())
                self.assertIs(signal.getsignal(signal.SIGINT), previous_handler)

    def test_schedule_sigint_fence_is_inert_in_worker_threads(self) -> None:
        import schedule_memory

        states: list[bool] = []

        def worker() -> None:
            with schedule_memory.defer_schedule_sigint() as state:
                states.append(state.requested)

        with patch("schedule_memory.signal.signal") as install_handler:
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(states, [False])
        install_handler.assert_not_called()

    @unittest.skipUnless(hasattr(signal, "SIGBREAK"), "Ctrl+Break is Windows-specific")
    def test_schedule_fence_defers_sigbreak_and_restores_handler(self) -> None:
        import schedule_memory

        sigbreak = signal.SIGBREAK  # type: ignore[attr-defined]

        def outer_handler(_signum: int, _frame: object) -> None:
            return

        original_handler = signal.signal(sigbreak, outer_handler)
        try:
            with schedule_memory.defer_schedule_sigint() as state:
                installed_handler = signal.getsignal(sigbreak)
                self.assertTrue(callable(installed_handler))
                installed_handler(sigbreak, None)  # type: ignore[operator]
            self.assertTrue(state.requested)
            self.assertIs(signal.getsignal(sigbreak), outer_handler)
        finally:
            signal.signal(sigbreak, original_handler)

    @unittest.skipUnless(hasattr(signal, "SIGBREAK"), "Ctrl+Break is Windows-specific")
    def test_schedule_sigbreak_defers_through_install_transaction(self) -> None:
        sigbreak = signal.SIGBREAK  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            plan = schedule_plan(root, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            previous_handler = signal.getsignal(sigbreak)
            requested = False

            def request_at_host_boundary(phase: str) -> None:
                nonlocal requested
                if phase != "install_host_published" or requested:
                    return
                requested = True
                installed_handler = signal.getsignal(sigbreak)
                self.assertTrue(callable(installed_handler))
                self.assertIsNot(installed_handler, previous_handler)
                installed_handler(sigbreak, None)  # type: ignore[operator]

            error = io.StringIO()
            with patch(
                "schedule_memory.run_install_commands",
                return_value=(0, True),
            ), patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=(digests, []),
            ), patch(
                "schedule_memory._schedule_phase_checkpoint",
                side_effect=request_at_host_boundary,
            ), redirect_stderr(error):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

            self.assertTrue(requested)
            self.assertEqual(exit_code, 130)
            self.assertTrue(load_config(root)["schedule"]["enabled"])
            self.assertIn("consistent transaction boundary", error.getvalue())
            self.assertIs(signal.getsignal(sigbreak), previous_handler)

    def test_schedule_lock_loss_after_host_install_requires_manual_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = initialize_minimal_runtime_vault(root)
            config_before = config_path.read_bytes()
            plan = schedule_plan(root, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            error = io.StringIO()

            with patch(
                "schedule_memory.run_install_commands",
                return_value=(0, True),
            ), patch(
                "schedule_memory.observe_schedule_definitions",
                return_value=(digests, []),
            ), patch(
                "schedule_memory._configure_schedule",
                side_effect=ConfigError("config_lock_error", source="schedule"),
            ), patch("schedule_memory.run_commands") as rollback, patch(
                "schedule_memory.restore_schedule_files"
            ) as file_rollback, redirect_stderr(error):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "install",
                        "--platform",
                        "windows",
                        "--expect-plan-sha256",
                        str(plan["plan_sha256"]),
                    ]
                )

            payload = json.loads(error.getvalue())
            config_after = config_path.read_bytes()

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["installed"])
        self.assertFalse(payload["rollback_complete"])
        self.assertTrue(payload["manual_recovery_required"])
        rollback.assert_not_called()
        file_rollback.assert_not_called()
        self.assertEqual(config_after, config_before)

    def test_schedule_partial_install_removes_every_job_attempted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_commands = build_schedule_commands(root, "install", target_platform="windows")
            remove_commands = build_schedule_commands(root, "remove", target_platform="windows")
            results = [
                (0, False, 101),
                (1, False, 102),
                (0, False, 103),
                (0, False, 104),
            ]

            with patch("schedule_memory.run_owned_process", side_effect=results) as runner:
                exit_code, rollback_complete = run_install_commands(
                    install_commands,
                    remove_commands,
                )

        self.assertEqual(exit_code, 1)
        self.assertTrue(rollback_complete)
        self.assertEqual(runner.call_count, 4)
        self.assertEqual(
            [call.args[0] for call in runner.call_args_list[2:]],
            [remove_commands[1].command, remove_commands[0].command],
        )

    def test_schedule_partial_remove_restores_every_job_attempted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remove_commands = build_schedule_commands(root, "remove", target_platform="windows")
            install_commands = build_schedule_commands(root, "install", target_platform="windows")
            results = [
                (0, False, 101),
                (1, False, 102),
                (0, False, 103),
                (0, False, 104),
            ]

            with patch("schedule_memory.run_owned_process", side_effect=results) as runner:
                exit_code, rollback_complete = run_remove_commands(
                    remove_commands,
                    install_commands,
                )

        self.assertEqual(exit_code, 1)
        self.assertTrue(rollback_complete)
        self.assertEqual(runner.call_count, 4)
        self.assertEqual(
            [call.args[0] for call in runner.call_args_list[2:]],
            [install_commands[0].command, install_commands[1].command],
        )

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
            initialize_minimal_runtime_vault(root)

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

    def test_schedule_status_rejects_malformed_disabled_review_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            (root / ".ai-dememory.toml").write_text(
                "[false_positives]\n"
                "enabled = false\n"
                "[conflicts]\n"
                "enabled = true\n",
                encoding="utf-8",
            )
            canary = "schedule-review-state-must-not-escape"
            (root / ".ai-dememory-ignore.toml").write_bytes(
                b"\xff" + canary.encode("ascii")
            )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            with patch("schedule_memory.build_schedule_commands") as commands:
                with self.assertRaises(ValueError) as raised:
                    schedule_status(root, target_platform="linux")
                output = io.StringIO()
                error = io.StringIO()
                with redirect_stdout(output), redirect_stderr(error):
                    exit_code = schedule_main(
                        ["--root", str(root), "status", "--platform", "linux", "--json"]
                    )

            self.assertEqual(exit_code, 2)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("review state", str(raised.exception))
            self.assertIn("review state", error.getvalue())
            self.assertNotIn(canary, str(raised.exception))
            self.assertNotIn(canary, error.getvalue())
            self.assertNotIn("traceback", error.getvalue().lower())
            self.assertEqual(
                {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file()
                },
                before,
            )
            commands.assert_not_called()

    def test_schedule_host_status_operations_are_serialized_per_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = schedule_plan(root, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            configure_schedule(
                root,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests=digests,
            )
            first_observe = threading.Event()
            release_first = threading.Event()
            calls: list[int] = []
            calls_lock = threading.Lock()
            results: list[int] = []

            def observe(*args: object, **kwargs: object) -> tuple[dict[str, str], list[str]]:
                with calls_lock:
                    calls.append(len(calls) + 1)
                    call_number = len(calls)
                if call_number == 1:
                    first_observe.set()
                    if not release_first.wait(timeout=5):
                        raise TimeoutError("test schedule release timed out")
                return digests, []

            def run_status() -> None:
                results.append(
                    schedule_main(
                        ["--root", str(root), "status", "--platform", "windows"]
                    )
                )

            with patch("schedule_memory.observe_schedule_definitions", side_effect=observe):
                first = threading.Thread(target=run_status, daemon=True)
                second = threading.Thread(target=run_status, daemon=True)
                first.start()
                self.assertTrue(first_observe.wait(timeout=5))
                second.start()
                time.sleep(0.05)
                self.assertEqual(calls, [1])
                self.assertTrue(second.is_alive())
                release_first.set()
                first.join(timeout=5)
                second.join(timeout=5)

            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(sorted(results), [0, 0])
            self.assertEqual(calls, [1, 2])

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
            plan = schedule_plan(
                root,
                target_platform="linux",
                daily_time="01:15",
                weekly_day="MON",
                weekly_time="02:30",
            )
            configure_schedule(
                root,
                "01:15",
                "MON",
                "02:30",
                "installed",
                "",
                target_platform="linux",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests={"file:test.timer": "b" * 64},
            )
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
            config_path = initialize_minimal_runtime_vault(root)
            config_before = config_path.read_bytes()
            output = io.StringIO()

            with patch("sys.stdout", output):
                exit_code = schedule_main(["--root", str(root), "setup", "--dry-run", "--platform", "windows"])

            config_after = config_path.read_bytes()
            commands = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(config_after, config_before)
        self.assertEqual(len(commands), 2)

    def test_schedule_status_reports_configured_state_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_template_tree(root)
            unconfigured = schedule_status(root, target_platform="linux")
            plan = schedule_plan(
                root,
                target_platform="linux",
                daily_time="01:15",
                weekly_day="MON",
                weekly_time="02:30",
                mode="docker",
                image=PINNED_TEST_IMAGE,
            )
            configure_schedule(
                root,
                "01:15",
                "MON",
                "02:30",
                "docker",
                PINNED_TEST_IMAGE,
                target_platform="linux",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests={"file:test.timer": "b" * 64},
            )
            configured = schedule_status(root, target_platform="linux")

        self.assertFalse(unconfigured["configured"])
        self.assertTrue(configured["configured"])
        self.assertEqual(configured["platform"], "linux")
        self.assertEqual(configured["mode"], "docker")
        self.assertEqual(configured["image"], PINNED_TEST_IMAGE)
        self.assertTrue(configured["install_receipt_valid"])
        self.assertTrue(configured["host_state_verified"])
        self.assertFalse(configured["mutates_system"])
        self.assertEqual(configured["schedule"]["daily_time"], "01:15")
        self.assertEqual(configured["schedule"]["weekly_day"], "MON")
        self.assertEqual(configured["schedule"]["weekly_time"], "02:30")
        self.assertIn("review_due", configured)
        self.assertEqual(configured["review_due"]["due_findings"], 0)
        self.assertEqual(configured["review_due"]["stale_suppressions"], 0)
        self.assertEqual(len(configured["status_commands"]), 2)
        self.assertTrue(all(item["action"] == "status" for item in configured["status_commands"]))

    def test_schedule_receipt_remains_removable_after_resource_policy_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = schedule_plan(
                root,
                target_platform="windows",
                intensity="active",
                daily_enabled=True,
                weekly_enabled=True,
            )
            configure_schedule(
                root,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                daily_enabled=True,
                weekly_enabled=True,
                intensity="active",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests={
                    f"task:{command['name']}": "a" * 64
                    for command in plan["commands"]
                },
            )
            set_section(root, "automation", {"intensity": "minimal"})

            status = schedule_status(root, target_platform="windows")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = schedule_main(
                    [
                        "--root",
                        str(root),
                        "remove",
                        "--dry-run",
                        "--json",
                        "--platform",
                        "windows",
                    ]
                )
            commands = json.loads(output.getvalue())

        self.assertTrue(status["install_receipt_valid"])
        self.assertEqual(status["schedule"]["intensity"], "active")
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(commands), 2)
        self.assertEqual(
            {command["name"].rsplit("-", 1)[-1] for command in commands},
            {"daily", "weekly"},
        )

    def test_schedule_receipt_detects_persisted_plan_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = schedule_plan(root, target_platform="windows")
            configure_schedule(
                root,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests={"task:daily": "a" * 64},
            )
            config_path = root / ".ai-dememory.toml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    'daily_time = "03:00"',
                    'daily_time = "03:01"',
                ),
                encoding="utf-8",
            )

            status = schedule_status(root, target_platform="windows")

        self.assertFalse(status["install_receipt_valid"])
        self.assertFalse(status["host_state_verified"])
        self.assertFalse(status["schedule"]["plan_projection_valid"])

    def test_schedule_cached_verification_expires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = schedule_plan(root, target_platform="windows")
            configure_schedule(
                root,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests={"task:daily": "a" * 64},
            )
            config_path = root / ".ai-dememory.toml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    next(
                        line
                        for line in config_path.read_text(encoding="utf-8").splitlines()
                        if line.startswith("verified_at = ")
                    ),
                    'verified_at = "2000-01-01T00:00:00+00:00"',
                ),
                encoding="utf-8",
            )

            status = schedule_status(root, target_platform="windows")

        self.assertEqual(status["verification_ttl_seconds"], SCHEDULE_VERIFICATION_TTL_SECONDS)
        self.assertFalse(status["verification_fresh"])
        self.assertFalse(status["host_state_verified"])
        self.assertEqual(status["last_verified_at"], "2000-01-01T00:00:00+00:00")

    def test_moved_vault_uses_receipted_namespace_but_requires_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original"
            moved = Path(tmp) / "moved"
            original.mkdir()
            plan = schedule_plan(original, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            configure_schedule(
                original,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests=digests,
            )
            original_namespace = schedule_namespace(original)
            original.rename(moved)

            status = schedule_status(moved, target_platform="windows")
            stderr = io.StringIO()
            with (
                patch(
                    "schedule_memory.observe_schedule_definitions",
                    return_value=(digests, []),
                ) as observe,
                patch("schedule_memory.run_remove_commands") as remove_commands,
                patch("schedule_memory.remove_platform_schedule_files", return_value=[]) as remove_files,
                redirect_stderr(stderr),
            ):
                exit_code = schedule_main(
                    ["--root", str(moved), "remove", "--platform", "windows"]
                )

        self.assertTrue(status["install_receipt_valid"])
        self.assertTrue(status["schedule"]["root_moved"])
        self.assertEqual(status["schedule"]["task_namespace"], original_namespace)
        self.assertTrue(
            all(original_namespace in item["name"] for item in status["status_commands"])
        )
        self.assertEqual(exit_code, 2)
        self.assertIn("reconcile", stderr.getvalue())
        self.assertIn("transfer schedule ownership", stderr.getvalue())
        observe.assert_not_called()
        remove_commands.assert_not_called()
        remove_files.assert_not_called()

    def test_copied_vault_cannot_remove_original_enabled_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original"
            copied = Path(tmp) / "copied"
            original.mkdir()
            copied.mkdir()
            plan = schedule_plan(original, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            configure_schedule(
                original,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests=digests,
            )
            (copied / ".ai-dememory.toml").write_text(
                (original / ".ai-dememory.toml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            status = schedule_status(copied, target_platform="windows")
            stderr = io.StringIO()
            with (
                patch("schedule_memory.observe_schedule_definitions") as observe,
                patch("schedule_memory.run_remove_commands") as remove_commands,
                redirect_stderr(stderr),
            ):
                exit_code = schedule_main(
                    ["--root", str(copied), "remove", "--platform", "windows"]
                )

        self.assertTrue(status["install_receipt_valid"])
        self.assertTrue(status["schedule"]["root_moved"])
        self.assertEqual(exit_code, 2)
        self.assertIn("copy of an enabled schedule receipt", stderr.getvalue())
        observe.assert_not_called()
        remove_commands.assert_not_called()

    def test_copied_vault_with_dangling_source_link_cannot_remove_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original"
            copied = Path(tmp) / "copied"
            missing = Path(tmp) / "missing-original"
            original.mkdir()
            copied.mkdir()
            plan = schedule_plan(original, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            configure_schedule(
                original,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests=digests,
            )
            (copied / ".ai-dememory.toml").write_text(
                (original / ".ai-dememory.toml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (original / ".ai-dememory.toml").unlink()
            (original / CONFIG_WRITE_LOCK_NAME).unlink()
            (original / SCHEDULE_OPERATION_LOCK_NAME).unlink()
            original.rmdir()
            try:
                os.symlink(missing, original, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            stderr = io.StringIO()
            with (
                patch("schedule_memory.observe_schedule_definitions") as observe,
                patch("schedule_memory.run_remove_commands") as remove_commands,
                redirect_stderr(stderr),
            ):
                exit_code = schedule_main(
                    ["--root", str(copied), "remove", "--platform", "windows"]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("copy of an enabled schedule receipt", stderr.getvalue())
        observe.assert_not_called()
        remove_commands.assert_not_called()

    def test_copied_vault_with_dangling_source_config_cannot_remove_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original"
            copied = Path(tmp) / "copied"
            original.mkdir()
            copied.mkdir()
            plan = schedule_plan(original, target_platform="windows")
            digests = {
                f"task:{command['name']}": "a" * 64
                for command in plan["commands"]
            }
            configure_schedule(
                original,
                "03:00",
                "SUN",
                "04:00",
                "installed",
                "",
                target_platform="windows",
                plan_sha256=str(plan["plan_sha256"]),
                definition_digests=digests,
            )
            source_config = original / ".ai-dememory.toml"
            (copied / ".ai-dememory.toml").write_text(
                source_config.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            source_config.unlink()
            try:
                os.symlink(Path(tmp) / "missing-config", source_config)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            stderr = io.StringIO()
            with (
                patch("schedule_memory.observe_schedule_definitions") as observe,
                patch("schedule_memory.run_remove_commands") as remove_commands,
                redirect_stderr(stderr),
            ):
                exit_code = schedule_main(
                    ["--root", str(copied), "remove", "--platform", "windows"]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("copy of an enabled schedule receipt", stderr.getvalue())
        observe.assert_not_called()
        remove_commands.assert_not_called()

    def test_moved_receipt_source_fails_closed_without_source_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "copied"
            source = Path(tmp) / "missing-source"
            status = {
                "schedule": {
                    "root_moved": True,
                    "configured_root": str(source),
                    "task_namespace": "ai-dememory-fixture-1234567890",
                    "plan_sha256": "a" * 64,
                }
            }
            with patch("schedule_memory.Path") as path_probe, patch(
                "schedule_memory.path_is_link_like"
            ) as link_probe, patch("schedule_memory.load_config") as config_probe:
                conflict = active_schedule_receipt_source(root, status)

        self.assertEqual(conflict, root)
        path_probe.assert_not_called()
        link_probe.assert_not_called()
        config_probe.assert_not_called()

    def test_unc_moved_receipt_remove_never_probes_or_renders_source(self) -> None:
        import schedule_memory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_minimal_runtime_vault(root)
            untrusted_unc = r"\\attacker.invalid\vault"
            status = {
                "install_receipt_valid": True,
                "schedule": {
                    "root_moved": True,
                    "configured_root": untrusted_unc,
                    "task_namespace": "ai-dememory-fixture-1234567890",
                    "plan_sha256": "a" * 64,
                }
            }
            real_load_config = schedule_memory.load_config

            def guarded_load_config(candidate: Path) -> dict[str, dict[str, object]]:
                self.assertEqual(Path(candidate).resolve(), root.resolve())
                return real_load_config(candidate)

            stderr = io.StringIO()
            with patch(
                "schedule_memory.schedule_status",
                return_value=status,
            ), patch(
                "schedule_memory.load_config",
                side_effect=guarded_load_config,
            ) as config_reads, patch(
                "schedule_memory.path_is_link_like",
            ) as source_probe, patch(
                "schedule_memory.observe_schedule_definitions"
            ) as observe, patch(
                "schedule_memory.run_remove_commands"
            ) as remove_commands, redirect_stderr(stderr):
                exit_code = schedule_main(
                    ["--root", str(root), "remove", "--platform", "windows"]
                )

        self.assertEqual(exit_code, 2)
        self.assertGreater(config_reads.call_count, 0)
        source_probe.assert_not_called()
        observe.assert_not_called()
        remove_commands.assert_not_called()
        self.assertNotIn(untrusted_unc, stderr.getvalue())
        self.assertIn("reconcile", stderr.getvalue())
        self.assertIn("transfer schedule ownership", stderr.getvalue())

    def test_moved_vault_removes_linux_files_from_receipted_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            original = Path(tmp) / "original"
            moved = Path(tmp) / "moved"
            original.mkdir()
            moved.mkdir()
            original_namespace = schedule_namespace(original)
            unit_dir = home / ".config" / "systemd" / "user"
            unit_dir.mkdir(parents=True)
            expected = {
                unit_dir / f"{original_namespace}-daily.service",
                unit_dir / f"{original_namespace}-daily.timer",
            }
            for path in expected:
                path.write_text("fixture", encoding="utf-8")
            wrong_namespace_path = (
                unit_dir / f"{schedule_namespace(moved)}-daily.service"
            )
            wrong_namespace_path.write_text("preserve", encoding="utf-8")

            with patch("schedule_memory.Path.home", return_value=home):
                removed = remove_platform_schedule_files(
                    moved,
                    "linux",
                    daily_enabled=True,
                    weekly_enabled=False,
                    task_namespace=original_namespace,
                )
            wrong_namespace_preserved = (
                wrong_namespace_path.read_text(encoding="utf-8") == "preserve"
            )

        self.assertEqual(set(removed), expected)
        self.assertTrue(wrong_namespace_preserved)

    def test_windows_rollback_recreates_exact_captured_task_xml(self) -> None:
        definition = '<?xml version="1.0" encoding="UTF-16"?><Task><URI>exact</URI></Task>'
        command = windows_restore_commands({"ai-dememory-vault-1234567890-daily": definition})[0]
        captured: dict[str, object] = {}

        def execute(runtime_command: list[str], timeout: float) -> tuple[int, bool, int]:
            xml_path = Path(runtime_command[runtime_command.index("/XML") + 1])
            captured["definition"] = xml_path.read_text(encoding="utf-16")
            captured["timeout"] = timeout
            return 0, False, 123

        with patch("schedule_memory.run_owned_process", side_effect=execute):
            result = run_schedule_command(command)

        self.assertEqual(result, (0, False, 123))
        self.assertEqual(captured["definition"], definition)
        self.assertEqual(captured["timeout"], 60)

    def test_scheduler_escapes_percent_for_cron_and_systemd(self) -> None:
        entries = build_cron_entries(
            Path("vault"),
            command="ai%dememory",
            daily_enabled=True,
            weekly_enabled=False,
        )
        service = systemd_service(
            "daily",
            ["ai%dememory", "maintenance", "run"],
        )

        self.assertIn(r"ai\%dememory", entries[0].line)
        self.assertIn("ai%%dememory", service)

    def test_schedule_apply_command_preserves_root_and_custom_command(self) -> None:
        root = Path("D:/vault with spaces")
        plan = schedule_plan(
            root,
            target_platform="windows",
            command="D:/Tools/ai-dememory.exe",
        )

        self.assertEqual(
            plan["apply_command"][:8],
            [
                "ai-dememory",
                "schedule",
                "--root",
                str(root),
                "--command",
                "D:/Tools/ai-dememory.exe",
                "setup",
                "--platform",
            ],
        )

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
            (root / ".ai-dememory.toml").write_text("", encoding="utf-8")

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
        self.assertIn("resource_policy", health)
        self.assertEqual(health["resource_policy"]["intensity"], "balanced")
        self.assertEqual(health["resource_policy"]["runtime_model_calls_per_maintenance_run"], 0)
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
        self.assertIn(
            "Review provider setup with `ai-dememory --root <vault-path> providers plan --json` before importing chats.",
            health["next_actions"],
        )
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
            [
                "ai-dememory",
                "--root",
                str(root.resolve()),
                "maintenance",
                "run",
                "--profile",
                "daily",
                "--dry-run",
                "--json",
            ],
        )
        self.assertEqual(
            mcp_health["maintenance_preflight"]["weekly_dry_run_command"],
            [
                "ai-dememory",
                "--root",
                str(root.resolve()),
                "maintenance",
                "run",
                "--profile",
                "weekly",
                "--dry-run",
                "--json",
            ],
        )
        self.assertTrue(any("quality/recall-fixtures.json" in action for action in health["recall_review"]["next_actions"]))
        self.assertTrue(health["core_ready"])
        self.assertFalse(health["retrieval_evaluated"])
        self.assertFalse(health["maintenance_ready"])
        self.assertFalse(health["manual_maintenance_ready"])
        self.assertFalse(health["automation_ready"])
        self.assertFalse(health["autonomy_ready"])
        self.assertFalse(health["integrations_ready"])
        self.assertFalse(health["release_ready"])
        self.assertTrue(health["ready_deprecated"])
        self.assertEqual(health["ready_scope"], "core_ready")
        self.assertEqual(health["ready"], health["core_ready"])
        self.assertEqual(payload["readiness"], health["readiness"])
        self.assertEqual(mcp_health["release_ready"], health["release_ready"])

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
        self.assertFalse(health["retrieval_evaluated"])
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

    def test_setup_health_reports_semantically_invalid_context_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[context]",
                        "default_budget_tokens = 999999",
                        "include_working_memory = false",
                        "explain_results = true",
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
            "clamped_max",
        )
        self.assertEqual(health["context_config"]["settings"]["default_budget_tokens"]["value"], 20000)
        self.assertEqual(
            health["context_config"]["settings"]["include_working_memory"]["source"],
            "configured",
        )
        self.assertFalse(health["context_config"]["settings"]["include_working_memory"]["value"])
        self.assertEqual(
            health["context_config"]["settings"]["explain_results"]["source"],
            "configured",
        )
        self.assertTrue(health["context_config"]["settings"]["explain_results"]["value"])
        self.assertTrue(health["context_config"]["errors"])
        self.assertTrue(any("[context]" in action for action in health["next_actions"]))
        self.assertFalse(mcp_health["context_config"]["valid"])

    def test_setup_health_never_reports_ready_with_invalid_resource_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "[resources]\nprovider_file_limit = 100000\n"
                "[recall]\nmin_relevance_score = 2.0\n",
                encoding="utf-8",
            )

            health = setup_health(root, target_platform="linux", mode="installed")

        self.assertFalse(health["resource_policy"]["valid"])
        self.assertFalse(health["core_ready"])
        self.assertFalse(health["manual_maintenance_ready"])
        self.assertFalse(health["autonomy_ready"])
        self.assertFalse(health["release_ready"])
        self.assertTrue(any("resource settings" in action for action in health["next_actions"]))

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

    def test_release_check_rejects_persistent_plugin_mcp_version_pin(self) -> None:
        mcp_path = ROOT / "plugins" / "ai-dememory" / ".mcp.json"
        original_mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        variants = (
            ("separate argument", ["--require-version", "0.0.0"]),
            ("equals argument", ["--require-version=0.0.0"]),
        )
        for label, extra_args in variants:
            with self.subTest(variant=label):
                pinned_mcp = json.loads(json.dumps(original_mcp))
                pinned_mcp["mcpServers"]["ai-dememory"]["args"].extend(extra_args)

                def load_json_with_persistent_version_pin(
                    path: Path,
                    errors: list[str],
                    config_label: str,
                ) -> dict[str, object] | None:
                    if path == mcp_path:
                        return pinned_mcp
                    return release_load_json(path, errors, config_label)

                with patch("release_check.load_json", side_effect=load_json_with_persistent_version_pin):
                    result = check_codex_plugin(ROOT)

                self.assertEqual(result.status, "fail")
                self.assertIn("must not emit obsolete persistent --require-version", result.detail)

    def test_plugin_version_maps_release_candidates_to_exact_semver(self) -> None:
        self.assertEqual(plugin_version_for_package("2.1.0rc1"), "2.1.0-rc.1")
        self.assertEqual(plugin_version_for_package("2.1.0"), "2.1.0")
        with self.assertRaisesRegex(ValueError, "unsupported package version"):
            plugin_version_for_package("2.1")

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
        self.assertIn("do not read or inject generated working state", text)
        self.assertIn("memory.context(public_only=true, include_working_memory=false)", text)
        self.assertFalse(plugin_skill_safety_issues("memory-working-session", text))

    def test_codex_plugin_recall_skill_enforces_public_repository_ceiling(self) -> None:
        path = ROOT / "plugins" / "ai-dememory" / "skills" / "memory-recall" / "SKILL.md"
        text = path.read_text(encoding="utf-8")

        self.assertIn("`public_only=true`", text)
        self.assertIn("`include_working_memory=false`", text)
        self.assertIn("do not call `memory.working_status`", text)
        self.assertIn("MCP resources/prompts", text)
        self.assertFalse(plugin_skill_safety_issues("memory-recall", text))
        self.assertTrue(
            plugin_skill_safety_issues(
                "memory-recall",
                "Call memory.context and memory.search with their defaults.",
            )
        )

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
            f'{{"jsonrpc":"2.0","id":1,"result":{{"protocolVersion":"2025-11-25",'
            f'"serverInfo":{{"name":"ai-dememory","version":"{PACKAGE_VERSION}","profile":"core"}}}}}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        with_notification = (
            '{"jsonrpc":"2.0","method":"notifications/message","params":{"level":"info"}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
            f'{{"jsonrpc":"2.0","id":1,"result":{{"protocolVersion":"2025-11-25",'
            f'"serverInfo":{{"name":"ai-dememory","version":"{PACKAGE_VERSION}","profile":"core"}}}}}}\n'
        )
        missing_server_info = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
        )
        wrong_server_version = (
            '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25",'
            '"serverInfo":{"name":"ai-dememory","version":"0.0.0","profile":"core"}}}\n'
            '{"jsonrpc":"2.0","id":2,"result":{}}\n'
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
        with self.assertRaisesRegex(InstallSmokeError, "missing serverInfo"):
            assert_mcp_initialize_and_ping(missing_server_info)
        with self.assertRaisesRegex(InstallSmokeError, "did not match installed package"):
            assert_mcp_initialize_and_ping(wrong_server_version)
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
        evidence = build_release_evidence(ROOT, pr_url=pr_url, reviewer=reviewer)
        report_text = render_markdown(evidence)
        mcp_payload = call_tool("memory.release_evidence_report", {"pr_url": pr_url, "reviewer": reviewer}, ROOT)

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
        self.assertEqual(
            result["dispatch_inputs"],
            {"repository": "testpypi", "confirm": "preflight", "pr_url": pr_url},
        )
        self.assertFalse(result["publishes_package"])
        self.assertFalse(result["writes_files"])
        self.assertTrue(result["runs_commands"])
        self.assertFalse(result["runs_publish_commands"])
        self.assertFalse(result["runs_preflight_commands"])
        self.assertTrue(result["local_inspection_commands"])
        self.assertTrue(result["requires_manual_dispatch"])
        self.assertTrue(result["requires_confirmation"])
        self.assertTrue(result["requires_pr_url"])
        self.assertFalse(result["uses_trusted_publishing"])
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
                "resource_policy": {
                    "valid": True,
                    "intensity": "balanced",
                    "runtime_model_calls_per_maintenance_run": 0,
                    "runtime_embedding_calls_per_maintenance_run": 0,
                },
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
                    "next_action": "Run ai-dememory --root <vault-path> maintenance run --profile daily.",
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
            namespace = schedule_namespace(root)
            fingerprint = "a" * 64
            good = json.dumps(
                {
                    "root": str(root.resolve()),
                    "action": "install",
                    "platform": "linux",
                    "mode": "installed",
                    "command": "ai-dememory",
                    "image": "",
                    "docker_image_immutable": True,
                    "installable": True,
                    "resource_policy_valid": True,
                    "validation_errors": [],
                    "task_namespace": namespace,
                    "intensity": "balanced",
                    "schedule": {
                        "daily_enabled": True,
                        "weekly_enabled": True,
                        "daily_time": "03:00",
                        "weekly_day": "SUN",
                        "weekly_time": "04:00",
                    },
                    "commands": [
                        {
                            "name": f"{namespace}-daemon-reload",
                            "platform": "linux",
                            "action": "install",
                            "command": ["systemctl", "--user", "daemon-reload"],
                            "run_command": None,
                        },
                        {
                            "name": f"{namespace}-daily",
                            "platform": "linux",
                            "action": "install",
                            "command": ["systemctl", "--user", "enable", "--now", f"{namespace}-daily.timer"],
                            "run_command": [
                                "ai-dememory",
                                "--root",
                                str(root.resolve()),
                                "maintenance",
                                "run",
                                "--profile",
                                "daily",
                                "--timeout-seconds",
                                "300",
                            ],
                        },
                        {
                            "name": f"{namespace}-weekly",
                            "platform": "linux",
                            "action": "install",
                            "command": ["systemctl", "--user", "enable", "--now", f"{namespace}-weekly.timer"],
                            "run_command": [
                                "ai-dememory",
                                "--root",
                                str(root.resolve()),
                                "maintenance",
                                "run",
                                "--profile",
                                "weekly",
                                "--timeout-seconds",
                                "300",
                            ],
                        },
                    ],
                    "cron_entries": [
                        {
                            "name": f"{namespace}-daily",
                            "profile": "daily",
                            "schedule": "0 3 * * *",
                            "command": [
                                "ai-dememory",
                                "--root",
                                str(root.resolve()),
                                "maintenance",
                                "run",
                                "--profile",
                                "daily",
                                "--timeout-seconds",
                                "300",
                            ],
                            "line": (
                                f"0 3 * * * ai-dememory --root {root.resolve()} maintenance run "
                                "--profile daily --timeout-seconds 300"
                            ),
                        },
                        {
                            "name": f"{namespace}-weekly",
                            "profile": "weekly",
                            "schedule": "0 4 * * 0",
                            "command": [
                                "ai-dememory",
                                "--root",
                                str(root.resolve()),
                                "maintenance",
                                "run",
                                "--profile",
                                "weekly",
                                "--timeout-seconds",
                                "300",
                            ],
                            "line": (
                                f"0 4 * * 0 ai-dememory --root {root.resolve()} maintenance run "
                                "--profile weekly --timeout-seconds 300"
                            ),
                        },
                    ],
                    "mutates_system": False,
                    "runs_commands": False,
                    "writes_files": False,
                    "installs_schedules": False,
                    "plan_sha256": fingerprint,
                    "apply_command": [
                        "ai-dememory",
                        "schedule",
                        "--root",
                        str(root.resolve()),
                        "--command",
                        "ai-dememory",
                        "setup",
                        "--platform",
                        "linux",
                        "--mode",
                        "installed",
                        "--daily-time",
                        "03:00",
                        "--weekly-day",
                        "SUN",
                        "--weekly-time",
                        "04:00",
                        "--daily",
                        "--weekly",
                        "--intensity",
                        "balanced",
                        "--expect-plan-sha256",
                        fingerprint,
                    ],
                }
            )
            canonical_good = json.loads(good)
            for entry in canonical_good["cron_entries"]:
                rendered_command = shlex.join(entry["command"]).replace("%", r"\%")
                entry["line"] = f"{entry['schedule']} {rendered_command}"
            fingerprint = schedule_plan_fingerprint(canonical_good)
            canonical_good["plan_sha256"] = fingerprint
            fingerprint_index = canonical_good["apply_command"].index("--expect-plan-sha256")
            canonical_good["apply_command"][fingerprint_index + 1] = fingerprint
            good = json.dumps(canonical_good)
            missing_flags = json.dumps({**json.loads(good), "writes_files": True})
            missing_cron = json.dumps({**json.loads(good), "cron_entries": []})
            wrong_root = json.dumps({**json.loads(good), "root": "/memory"})
            missing_weekly_run_payload = json.loads(good)
            missing_weekly_run_payload["commands"][2]["run_command"] = [
                "ai-dememory",
                "--root",
                str(root.resolve()),
                "maintenance",
                "run",
                "--profile",
                "daily",
            ]
            duplicate_daily_cron_payload = json.loads(good)
            duplicate_daily_cron_payload["cron_entries"][1] = {
                **duplicate_daily_cron_payload["cron_entries"][0],
                "name": "ai-dememory-daily-copy",
            }
            mismatched_weekly_command_payload = json.loads(good)
            mismatched_weekly_command_payload["commands"][2]["run_command"] = [
                "ai-dememory",
                "--root",
                str(root.resolve()),
                "maintenance",
                "run",
                "--profile",
                "daily",
            ]
            mismatched_weekly_cron_payload = json.loads(good)
            mismatched_weekly_cron_payload["cron_entries"][1]["line"] = (
                f"0 4 * * 0 ai-dememory --root {root.resolve()} maintenance run --profile daily"
            )

            def mutate_root(command: list[str], defect: str, *, apply: bool = False) -> list[str]:
                tokens = list(command)
                root_index = tokens.index("--root")
                root_pair = tokens[root_index : root_index + 2]
                if defect == "missing":
                    del tokens[root_index : root_index + 2]
                elif defect == "misplaced":
                    del tokens[root_index : root_index + 2]
                    marker_index = tokens.index("setup" if apply else "maintenance")
                    insertion_index = marker_index + (1 if apply else 2)
                    tokens[insertion_index:insertion_index] = root_pair
                elif defect == "duplicate":
                    tokens[root_index:root_index] = root_pair
                elif defect == "incorrect":
                    tokens[root_index + 1] = "/unexpected-vault"
                else:
                    self.fail(f"unsupported root defect: {defect}")
                return tokens

            installed_plan = schedule_plan(
                root,
                target_platform="linux",
                intensity="balanced",
            )
            assert_schedule_plan(
                json.dumps(installed_plan),
                expected_root=str(root.resolve()),
            )
            assert_schedule_plan(good, expected_root=str(root.resolve()))
            docker_plan = schedule_plan(
                root,
                mode="docker",
                image=PINNED_TEST_IMAGE,
                target_platform="linux",
                intensity="balanced",
            )
            assert_schedule_plan(
                json.dumps(docker_plan),
                expected_mode="docker",
                expected_root=str(root.resolve()),
                expected_image=PINNED_TEST_IMAGE,
            )
            with self.assertRaises(InstallSmokeError):
                assert_schedule_plan(missing_flags, expected_root=str(root.resolve()))
            with self.assertRaises(InstallSmokeError):
                assert_schedule_plan(missing_cron, expected_root=str(root.resolve()))
            with self.assertRaises(InstallSmokeError):
                assert_schedule_plan(wrong_root, expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "weekly maintenance run command"):
                assert_schedule_plan(json.dumps(missing_weekly_run_payload), expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "weekly cron entry"):
                assert_schedule_plan(json.dumps(duplicate_daily_cron_payload), expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "weekly maintenance run command"):
                assert_schedule_plan(json.dumps(mismatched_weekly_command_payload), expected_root=str(root.resolve()))
            with self.assertRaisesRegex(InstallSmokeError, "weekly maintenance cron line"):
                assert_schedule_plan(json.dumps(mismatched_weekly_cron_payload), expected_root=str(root.resolve()))
            for command_kind, error_pattern in (
                ("run", "daily maintenance run command"),
                ("cron", "daily maintenance cron command"),
                ("apply", "fingerprint-bound apply command"),
            ):
                for defect in ("missing", "misplaced", "duplicate", "incorrect"):
                    with self.subTest(command_kind=command_kind, root_defect=defect):
                        payload = json.loads(good)
                        if command_kind == "run":
                            source = payload["commands"][1]["run_command"]
                            payload["commands"][1]["run_command"] = mutate_root(source, defect)
                        elif command_kind == "cron":
                            source = payload["cron_entries"][0]["command"]
                            payload["cron_entries"][0]["command"] = mutate_root(source, defect)
                        else:
                            source = payload["apply_command"]
                            payload["apply_command"] = mutate_root(source, defect, apply=True)
                        with self.assertRaisesRegex(InstallSmokeError, error_pattern):
                            assert_schedule_plan(
                                json.dumps(payload),
                                expected_root=str(root.resolve()),
                            )

            def clone(payload: dict[str, object]) -> dict[str, object]:
                return json.loads(json.dumps(payload))

            def named_command(payload: dict[str, object], profile: str) -> dict[str, object]:
                expected_name = f"{payload['task_namespace']}-{profile}"
                return next(command for command in payload["commands"] if command["name"] == expected_name)

            def named_cron(payload: dict[str, object], profile: str) -> dict[str, object]:
                expected_name = f"{payload['task_namespace']}-{profile}"
                return next(entry for entry in payload["cron_entries"] if entry["name"] == expected_name)

            for non_object in ("[]", "null", json.dumps("schedule plan")):
                with self.subTest(non_object=non_object):
                    with self.assertRaisesRegex(InstallSmokeError, "JSON must be an object"):
                        assert_schedule_plan(non_object, expected_root=str(root.resolve()))

            malformed_argv_cases: list[tuple[str, dict[str, object]]] = []
            malformed_scheduler_argv = clone(installed_plan)
            named_command(malformed_scheduler_argv, "daily")["command"][0] = 7
            malformed_argv_cases.append(("scheduler", malformed_scheduler_argv))
            malformed_run_argv = clone(installed_plan)
            named_command(malformed_run_argv, "daily")["run_command"][0] = 7
            malformed_argv_cases.append(("run", malformed_run_argv))
            malformed_cron_argv = clone(installed_plan)
            named_cron(malformed_cron_argv, "daily")["command"][0] = 7
            malformed_argv_cases.append(("cron", malformed_cron_argv))
            malformed_apply_argv = clone(installed_plan)
            malformed_apply_argv["apply_command"][0] = 7
            malformed_argv_cases.append(("apply", malformed_apply_argv))
            for argv_kind, payload in malformed_argv_cases:
                with self.subTest(non_string_argv=argv_kind):
                    with self.assertRaises(InstallSmokeError):
                        assert_schedule_plan(json.dumps(payload), expected_root=str(root.resolve()))

            for mode, source in (("installed", installed_plan), ("docker", docker_plan)):
                missing_executable = clone(source)
                del named_command(missing_executable, "daily")["run_command"][0]
                extra_argument = clone(source)
                named_command(extra_argument, "daily")["run_command"].append("--extra")
                for defect, payload in (
                    ("missing executable", missing_executable),
                    ("extra argument", extra_argument),
                ):
                    with self.subTest(mode=mode, run_defect=defect):
                        with self.assertRaisesRegex(InstallSmokeError, "daily maintenance run command"):
                            assert_schedule_plan(
                                json.dumps(payload),
                                expected_mode=mode,
                                expected_root=str(root.resolve()),
                                expected_image=PINNED_TEST_IMAGE if mode == "docker" else None,
                            )

            for defect in ("missing", "misplaced", "duplicate", "incorrect"):
                for command_kind in ("run", "cron"):
                    payload = clone(docker_plan)
                    owner = (
                        named_command(payload, "daily")
                        if command_kind == "run"
                        else named_cron(payload, "daily")
                    )
                    owner["run_command" if command_kind == "run" else "command"] = mutate_root(
                        owner["run_command" if command_kind == "run" else "command"],
                        defect,
                    )
                    with self.subTest(mode="docker", command_kind=command_kind, root_defect=defect):
                        with self.assertRaises(InstallSmokeError):
                            assert_schedule_plan(
                                json.dumps(payload),
                                expected_mode="docker",
                                expected_root=str(root.resolve()),
                                expected_image=PINNED_TEST_IMAGE,
                            )

            missing_image_field = clone(docker_plan)
            del missing_image_field["image"]
            missing_run_image = clone(docker_plan)
            named_command(missing_run_image, "daily")["run_command"].remove(PINNED_TEST_IMAGE)
            missing_apply_image = clone(docker_plan)
            del missing_apply_image["apply_command"][-2:]
            for defect, payload, error_pattern in (
                ("plan image", missing_image_field, "missing image"),
                ("run image", missing_run_image, "daily maintenance run command"),
                ("apply image", missing_apply_image, "fingerprint-bound apply command"),
            ):
                with self.subTest(docker_image_defect=defect):
                    with self.assertRaisesRegex(InstallSmokeError, error_pattern):
                        assert_schedule_plan(
                            json.dumps(payload),
                            expected_mode="docker",
                            expected_root=str(root.resolve()),
                            expected_image=PINNED_TEST_IMAGE,
                        )

            for marker in ("--network", "--cpus", "--memory", "--pids-limit", "-e", "-v"):
                payload = clone(docker_plan)
                run_command = named_command(payload, "daily")["run_command"]
                run_command.insert(run_command.index(marker) + 1, "unexpected")
                with self.subTest(non_adjacent_docker_option=marker):
                    with self.assertRaisesRegex(InstallSmokeError, "daily maintenance run command"):
                        assert_schedule_plan(
                            json.dumps(payload),
                            expected_mode="docker",
                            expected_root=str(root.resolve()),
                            expected_image=PINNED_TEST_IMAGE,
                        )

            bogus_apply_prefix = clone(installed_plan)
            bogus_apply_prefix["apply_command"][0] = "python"
            missing_schedule_prefix = clone(installed_plan)
            del missing_schedule_prefix["apply_command"][1]
            extra_apply_argument = clone(installed_plan)
            extra_apply_argument["apply_command"].append("--extra")
            for defect, payload in (
                ("bogus prefix", bogus_apply_prefix),
                ("missing schedule", missing_schedule_prefix),
                ("extra argument", extra_apply_argument),
            ):
                with self.subTest(apply_defect=defect):
                    with self.assertRaisesRegex(InstallSmokeError, "fingerprint-bound apply command"):
                        assert_schedule_plan(json.dumps(payload), expected_root=str(root.resolve()))

            duplicate_command = clone(installed_plan)
            valid_daily_command = clone(named_command(duplicate_command, "daily"))
            del named_command(duplicate_command, "daily")["run_command"][0]
            duplicate_command["commands"].append(valid_daily_command)
            with self.assertRaisesRegex(InstallSmokeError, "exactly one named daily scheduler command"):
                assert_schedule_plan(json.dumps(duplicate_command), expected_root=str(root.resolve()))

            duplicate_cron = clone(installed_plan)
            valid_daily_cron = clone(named_cron(duplicate_cron, "daily"))
            del named_cron(duplicate_cron, "daily")["command"][0]
            duplicate_cron["cron_entries"].append(valid_daily_cron)
            with self.assertRaisesRegex(InstallSmokeError, "exactly one daily and one weekly cron entry"):
                assert_schedule_plan(json.dumps(duplicate_cron), expected_root=str(root.resolve()))

            extra_cron_argument = clone(installed_plan)
            named_cron(extra_cron_argument, "daily")["command"].append("--extra")
            with self.assertRaisesRegex(InstallSmokeError, "daily maintenance cron command"):
                assert_schedule_plan(json.dumps(extra_cron_argument), expected_root=str(root.resolve()))

            noncanonical_cron_line = clone(installed_plan)
            named_cron(noncanonical_cron_line, "daily")["line"] += " --extra"
            with self.assertRaisesRegex(InstallSmokeError, "daily maintenance cron line"):
                assert_schedule_plan(json.dumps(noncanonical_cron_line), expected_root=str(root.resolve()))

    def test_install_smoke_validates_exact_host_schedule_commands_and_plan_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected_root = str(root.resolve())

            def clone(payload: dict[str, object]) -> dict[str, object]:
                return json.loads(json.dumps(payload))

            def profile_command(payload: dict[str, object], profile: str) -> dict[str, object]:
                expected_name = f"{payload['task_namespace']}-{profile}"
                return next(command for command in payload["commands"] if command["name"] == expected_name)

            def validate(payload: dict[str, object], mode: str) -> None:
                assert_schedule_plan(
                    json.dumps(payload),
                    expected_mode=mode,
                    expected_root=expected_root,
                    expected_image=PINNED_TEST_IMAGE if mode == "docker" else None,
                )

            plans: dict[tuple[str, str], dict[str, object]] = {}
            for platform in ("windows", "macos", "linux"):
                for mode in ("installed", "docker"):
                    plan = schedule_plan(
                        root,
                        target_platform=platform,
                        mode=mode,
                        image=PINNED_TEST_IMAGE,
                        intensity="balanced",
                    )
                    plans[(platform, mode)] = plan
                    with self.subTest(positive_platform=platform, positive_mode=mode):
                        validate(plan, mode)

            for platform in ("windows", "macos", "linux"):
                for profile in ("daily", "weekly"):
                    payload = clone(plans[(platform, "installed")])
                    profile_command(payload, profile)["command"].append("--extra")
                    with self.subTest(mutated_host_argv=platform, profile=profile):
                        with self.assertRaisesRegex(InstallSmokeError, "host command"):
                            validate(payload, "installed")

            reordered = clone(plans[("windows", "installed")])
            reordered["commands"][0], reordered["commands"][1] = (
                reordered["commands"][1],
                reordered["commands"][0],
            )
            extra = clone(plans[("macos", "installed")])
            extra["commands"].append(
                {
                    "name": "unexpected-host-command",
                    "platform": "macos",
                    "action": "install",
                    "command": ["launchctl", "list"],
                    "run_command": None,
                }
            )
            duplicate = clone(plans[("windows", "installed")])
            duplicate["commands"].append(clone(profile_command(duplicate, "daily")))
            for defect, payload, error_pattern in (
                ("reordered", reordered, "exact ordered"),
                ("extra", extra, "exact ordered"),
                ("duplicate", duplicate, "exactly one named daily"),
            ):
                with self.subTest(host_set_defect=defect):
                    with self.assertRaisesRegex(InstallSmokeError, error_pattern):
                        validate(payload, "installed")

            illegal_windows_daemon = clone(plans[("windows", "installed")])
            illegal_windows_daemon["commands"].insert(
                0,
                {
                    "name": f"{illegal_windows_daemon['task_namespace']}-daemon-reload",
                    "platform": "windows",
                    "action": "install",
                    "command": ["systemctl", "--user", "daemon-reload"],
                    "run_command": None,
                },
            )
            missing_linux_daemon = clone(plans[("linux", "installed")])
            del missing_linux_daemon["commands"][0]
            duplicate_linux_daemon = clone(plans[("linux", "installed")])
            duplicate_linux_daemon["commands"].insert(1, clone(duplicate_linux_daemon["commands"][0]))
            malformed_linux_daemon = clone(plans[("linux", "installed")])
            malformed_linux_daemon["commands"][0]["command"].append("--extra")
            daemon_with_maintenance = clone(plans[("linux", "installed")])
            daemon_with_maintenance["commands"][0]["run_command"] = clone(
                profile_command(daemon_with_maintenance, "daily")
            )["run_command"]
            for defect, payload, error_pattern in (
                ("illegal on Windows", illegal_windows_daemon, "exact ordered"),
                ("missing on Linux", missing_linux_daemon, "exact ordered"),
                ("duplicate on Linux", duplicate_linux_daemon, "exact ordered"),
                ("malformed on Linux", malformed_linux_daemon, "host command"),
                ("maintenance on daemon", daemon_with_maintenance, "must not include a maintenance command"),
            ):
                with self.subTest(daemon_reload_defect=defect):
                    with self.assertRaisesRegex(InstallSmokeError, error_pattern):
                        validate(payload, "installed")

            wrong_platform_field = clone(plans[("windows", "installed")])
            profile_command(wrong_platform_field, "daily")["platform"] = "linux"
            wrong_action_field = clone(plans[("windows", "installed")])
            profile_command(wrong_action_field, "daily")["action"] = "status"
            wrong_name_field = clone(plans[("windows", "installed")])
            profile_command(wrong_name_field, "daily")["name"] = "wrong-name"
            for defect, payload, error_pattern in (
                ("platform", wrong_platform_field, "wrong platform or action"),
                ("action", wrong_action_field, "wrong platform or action"),
                ("name", wrong_name_field, "exactly one named daily"),
            ):
                with self.subTest(host_metadata_defect=defect):
                    with self.assertRaisesRegex(InstallSmokeError, error_pattern):
                        validate(payload, "installed")

            unsupported_platform = clone(plans[("windows", "installed")])
            unsupported_platform["platform"] = "evil"
            platform_index = unsupported_platform["apply_command"].index("--platform")
            unsupported_platform["apply_command"][platform_index + 1] = "evil"
            with self.assertRaisesRegex(InstallSmokeError, "target platform"):
                validate(unsupported_platform, "installed")

            alien_namespace = clone(plans[("windows", "installed")])
            original_namespace = alien_namespace["task_namespace"]
            replacement_namespace = schedule_namespace(root / "other-vault")
            alien_namespace["task_namespace"] = replacement_namespace
            for command in alien_namespace["commands"]:
                command["name"] = command["name"].replace(original_namespace, replacement_namespace)
                command["command"] = [
                    argument.replace(original_namespace, replacement_namespace)
                    for argument in command["command"]
                ]
            for entry in alien_namespace["cron_entries"]:
                entry["name"] = entry["name"].replace(original_namespace, replacement_namespace)
            alien_namespace["plan_sha256"] = schedule_plan_fingerprint(alien_namespace)
            fingerprint_index = alien_namespace["apply_command"].index("--expect-plan-sha256")
            alien_namespace["apply_command"][fingerprint_index + 1] = alien_namespace["plan_sha256"]
            with self.assertRaisesRegex(InstallSmokeError, "namespace does not match"):
                validate(alien_namespace, "installed")

            safety_cases = (
                ("installable", False, "installable"),
                ("resource_policy_valid", False, "resource policy"),
                ("validation_errors", ["broken"], "validation errors"),
                ("docker_image_immutable", False, "immutability"),
            )
            for mode in ("installed", "docker"):
                for field, value, error_pattern in safety_cases:
                    payload = clone(plans[("windows", mode)])
                    payload[field] = value
                    with self.subTest(mode=mode, safety_field=field):
                        with self.assertRaisesRegex(InstallSmokeError, error_pattern):
                            validate(payload, mode)

            forged_fingerprint = clone(plans[("windows", "installed")])
            forged_fingerprint["plan_sha256"] = "0" * 64
            fingerprint_index = forged_fingerprint["apply_command"].index("--expect-plan-sha256")
            forged_fingerprint["apply_command"][fingerprint_index + 1] = "0" * 64
            with self.assertRaisesRegex(InstallSmokeError, "canonical plan projection"):
                validate(forged_fingerprint, "installed")

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
                "dispatch_inputs": {"repository": "testpypi", "confirm": "preflight", "pr_url": "<pr-url>"},
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
                "uses_trusted_publishing": False,
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
            commands["context public only"],
            [
                "context",
                "public",
                "ceiling",
                "package",
                "recall",
                "--public-only",
                "--no-working-memory",
                "--limit",
                "1",
                "--budget",
                "700",
                "--json",
            ],
        )
        self.assertEqual(
            commands["search public only"],
            ["search", "public", "ceiling", "package", "recall", "--public-only", "--limit", "1", "--json"],
        )
        self.assertIn('"public_only":true', commands["mcp public context"][-1])
        self.assertEqual(
            commands["turn context"],
            ["turn-context", "continue install smoke package policy", "--cwd", "{vault}", "--json"],
        )
        self.assertEqual(
            commands["hook prompt dispatch"],
            ["hook-event", "dispatch", "--client", "codex", "--event", "UserPromptSubmit"],
        )
        self.assertIn("--apply", commands["onboarding apply"])
        self.assertNotIn("--apply", commands["onboarding preview"])
        self.assertEqual(
            commands["setup preview"],
            [
                "setup",
                "wizard",
                "--intensity",
                "balanced",
                "--json",
            ],
        )
        self.assertIn("--apply", commands["setup apply"])
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
        self.assertEqual(
            commands["setup plan"],
            [
                "setup",
                "plan",
                "--client",
                "codex",
                "--mode",
                "both",
                "--json",
            ],
        )
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
            commands["docker schedule plan"],
            [
                "schedule",
                "plan",
                "--mode",
                "docker",
                "--image",
                "sha256:" + ("a" * 64),
                "--json",
            ],
        )
        self.assertEqual(
            commands["docker schedule dry run"],
            ["schedule", "setup", "--dry-run", "--mode", "docker", "--image", "sha256:" + ("a" * 64)],
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

    def test_mcp_client_smoke_binds_loaded_config_to_selected_vault(self) -> None:
        config = {
            "mcpServers": {
                "ai-dememory": {
                    "command": "ai-dememory",
                    "args": ["mcp", "--stdio"],
                    "env": {},
                }
            }
        }
        vault = Path("C:/private/smoke-vault")

        bound = bind_config_runtime_root(config, vault)

        self.assertEqual(config["mcpServers"]["ai-dememory"]["env"], {})
        self.assertEqual(
            bound["mcpServers"]["ai-dememory"]["env"],
            {"AI_DEMEMORY_ROOT": str(vault)},
        )

    def test_mcp_client_smoke_normalizes_conflicting_root_env_case_insensitively(self) -> None:
        config = {
            "mcpServers": {
                "ai-dememory": {
                    "command": "ai-dememory",
                    "args": ["mcp", "--stdio"],
                    "env": {
                        "AI_DEMEMORY_ROOT": "C:/private/stale-vault",
                        "ai_dememory_root": "C:/private/attacker-vault",
                        "KEEP_ME": "yes",
                    },
                }
            }
        }
        vault = Path("C:/private/selected-vault")

        bound = bind_config_runtime_root(config, vault)

        self.assertEqual(
            bound["mcpServers"]["ai-dememory"]["env"],
            {"KEEP_ME": "yes", "AI_DEMEMORY_ROOT": str(vault)},
        )
        self.assertEqual(
            config["mcpServers"]["ai-dememory"]["env"]["ai_dememory_root"],
            "C:/private/attacker-vault",
        )

    def test_mcp_client_smoke_rejects_loaded_config_root_arguments(self) -> None:
        for args in (
            ["--root", "C:/private/old-vault", "mcp", "--stdio"],
            ["--root=C:/private/old-vault", "mcp", "--stdio"],
        ):
            with self.subTest(args=args), self.assertRaisesRegex(
                ClientSmokeError,
                "must not contain --root",
            ):
                bind_config_runtime_root(
                    {"command": "ai-dememory", "args": args, "env": {}},
                    Path("C:/private/selected-vault"),
                )

    def test_mcp_client_smoke_rejects_loaded_docker_config(self) -> None:
        config = build_mcp_config(
            "generic",
            "docker",
            Path("C:/private/old-vault"),
        )

        with self.assertRaisesRegex(ClientSmokeError, "use --mode docker"):
            bind_config_runtime_root(
                config,
                Path("C:/private/selected-vault"),
            )

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
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            copy_template_tree(root)
            config_path = ROOT / "plugins" / "ai-dememory" / ".mcp.json"
            config = override_launch(
                json.loads(config_path.read_text(encoding="utf-8")),
                command=sys.executable,
                command_args=["scripts/ai_dememory.py"],
            )
            config["mcpServers"]["ai-dememory"]["env"] = {
                "AI_DEMEMORY_ROOT": str(root.resolve()),
            }

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

    def test_publish_guard_rejects_duplicate_shell_tag_syntax_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            for name in ("release.yml", "publish.yml", "tag-release.yml"):
                text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
                if name == "tag-release.yml":
                    text = text.replace(
                        'test "$RELEASE_CONFIRM" = "release-$RELEASE_TAG@$APPROVED_SHA"',
                        'test "$RELEASE_CONFIRM" = "release-$RELEASE_TAG@$APPROVED_SHA"\n'
                        '          [[ "$RELEASE_TAG" =~ ^v[0-9]+\\.[0-9]+\\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]',
                        1,
                    )
                (workflows / name).write_text(text, encoding="utf-8")

            issues = validate_publish_workflow(root)

        self.assertIn(
            "tag syntax must be centralized in ai_release_guard.py",
            "\n".join(issue.message for issue in issues),
        )

    def test_publish_guard_requires_identity_validation_before_tag_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            identity = 'python scripts/ai_release_guard.py --tag "$RELEASE_TAG" --version-only'
            for name in ("release.yml", "publish.yml", "tag-release.yml"):
                text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
                if name == "tag-release.yml":
                    text = text.replace(identity, "true # identity validation moved", 1)
                    text += f"\n      - run: {identity}\n"
                (workflows / name).write_text(text, encoding="utf-8")

            issues = validate_publish_workflow(root)

        self.assertIn(
            "canonical tag identity validation must run before tag mutation",
            "\n".join(issue.message for issue in issues),
        )

    def test_publish_guard_rejects_ambient_post_ci_tagger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            for name in ("release.yml", "publish.yml"):
                (workflows / name).write_text(
                    (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            (workflows / "tag-release.yml").write_text(
                """
name: unsafe ambient tagger
on:
  workflow_run:
    workflows: ["CI"]
jobs:
  tag:
    if: vars.AI_RELEASE_ENABLED == 'true'
    steps:
      - run: git push origin v2.1.0
""",
                encoding="utf-8",
            )

            issues = validate_publish_workflow(root)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("workflow_dispatch-only", messages)
        self.assertIn("tagger must be workflow_dispatch-only", messages)
        self.assertIn("exact tag and commit", messages)
        self.assertIn("current main", messages)
        self.assertIn("successful push CI", messages)

    def test_publish_guard_rejects_legacy_alternate_publisher(self) -> None:
        unsafe = """
name: Legacy publisher
on:
  workflow_dispatch:
jobs:
  publish:
    environment: pypi
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: pypa/gh-action-pypi-publish@release/v1
"""

        issues = validate_legacy_preflight_workflow_text(unsafe)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("confirm=preflight", messages)
        self.assertIn("write permissions", messages)
        self.assertIn("publishing environments", messages)
        self.assertIn("OIDC publishing permission", messages)
        self.assertIn("PyPI publisher action", messages)

    def test_publish_guard_rejects_new_alternate_publisher_workflow(self) -> None:
        workflows = {
            Path(".github/workflows/release.yml"): "id-token: write\npypa/gh-action-pypi-publish",
            Path(".github/workflows/rogue.yml"): """
permissions:
  id-token: write
jobs:
  upload:
    environment:
      name: pypi
    steps:
      - uses: PyPA/gh-action-pypi-publish@release/v1
      - run: gh release create v9.9.9 rogue.whl
      - run: uv publish
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.ROGUE_TOKEN }}
""",
        }

        issues = validate_publisher_inventory(workflows)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("OIDC write permission", messages)
        self.assertIn("PyPI publisher action", messages)
        self.assertIn("GitHub Release creation", messages)
        self.assertIn("uv package upload", messages)
        self.assertIn("stored GitHub secret reference", messages)
        self.assertIn("package-index environments", messages)
        self.assertTrue(all(issue.target.startswith(".github/workflows/rogue.yml") for issue in issues))

    def test_publish_guard_allows_oidc_only_for_guarded_pages_delivery(self) -> None:
        release = Path(".github/workflows/release.yml")
        pages = Path(".github/workflows/pages.yml")
        pages_text = (ROOT / pages).read_text(encoding="utf-8")

        allowed = validate_publisher_inventory(
            {
                release: "id-token: write\npypa/gh-action-pypi-publish",
                pages: pages_text,
            }
        )
        weakened = validate_publisher_inventory(
            {
                release: "id-token: write\npypa/gh-action-pypi-publish",
                pages: pages_text.replace("pages: write", "contents: write"),
            }
        )

        self.assertFalse(allowed)
        self.assertIn("OIDC write permission", "\n".join(issue.message for issue in weakened))

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
        self.assertIn("must not reference stored GitHub secrets", messages)
        self.assertIn("canonical release workflow is missing: workflow_dispatch:", messages)
        self.assertIn("canonical release must be workflow_dispatch-only", messages)
        self.assertIn("canonical release workflow is missing: concurrency:", messages)
        self.assertIn("canonical release workflow is missing: python scripts/ai_release_guard.py --tag", messages)
        self.assertIn("canonical release workflow is missing: release_artifact_smoke.py", messages)
        self.assertIn("canonical release workflow is missing: SHA256SUMS", messages)
        self.assertIn("exact intent, tag, and commit confirmation", messages)

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
        self.assertIn("exact intent, tag, and commit confirmation", messages)
        self.assertIn("release distributions must be built exactly once", messages)

    def test_publish_guard_rejects_direct_tag_trigger(self) -> None:
        current = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        unsafe = current.replace(
            "on:\n  workflow_dispatch:",
            'on:\n  push:\n    tags:\n      - "v*"\n  workflow_dispatch:',
            1,
        )

        issues = validate_publish_workflow_text(unsafe)

        self.assertTrue(
            any("workflow_dispatch-only" in issue.message for issue in issues)
        )

    def test_publish_guard_rejects_any_alternate_release_event(self) -> None:
        current = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        unsafe = current.replace(
            "on:\n  workflow_dispatch:",
            "on:\n  workflow_call:\n  workflow_dispatch:",
            1,
        )

        issues = validate_publish_workflow_text(unsafe)

        self.assertTrue(
            any("workflow_dispatch-only" in issue.message for issue in issues)
        )

    def test_publish_guard_keeps_tagger_separate_from_publisher_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            for name in ("release.yml", "publish.yml", "tag-release.yml"):
                text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
                if name == "tag-release.yml":
                    text = text.replace("actions: read", "actions: write")
                    text += "\n      - run: gh workflow run release.yml\n"
                (workflows / name).write_text(text, encoding="utf-8")

            issues = validate_publish_workflow(root)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Actions read-only", messages)
        self.assertIn("must not dispatch the publisher automatically", messages)

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
                "confirm": "preflight",
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
        self.assertFalse(plan["uses_trusted_publishing"])
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
        self.assertIn("legacy hosted preflight cannot publish", plan["next_actions"][-1])

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
                "confirm": "preflight",
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

        self.assertIn(
            "Use a canonical prerelease tag for TestPyPI and verify install evidence before a PyPI release.",
            actions,
        )

    def test_publish_readiness_defers_only_testpypi_acceptance_for_testpypi(self) -> None:
        blocker = {
            "id": "manual_acceptance_remaining",
            "kind": "manual_acceptance",
            "summary": "Manual acceptance remains.",
            "count": 2,
            "items": [
                "Export the generated vault template and inspect Obsidian-compatible templates; open it in Obsidian when a GUI reviewer is available.",
                ACCEPTANCE_ITEMS["testpypi-publish"],
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
        self.assertNotIn(ACCEPTANCE_ITEMS["testpypi-publish"], testpypi_blockers[0]["items"])
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
                        "items": [ACCEPTANCE_ITEMS["testpypi-publish"]],
                    }
                ],
                "manual_acceptance_remaining": [ACCEPTANCE_ITEMS["testpypi-publish"]],
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

    def test_ci_guard_binds_all_required_commands_to_the_protected_verify_job(self) -> None:
        current = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        weakened = current.replace("\n  verify:\n", "\n  full-validation:\n", 1)
        weakened += """
  verify:
    runs-on: ubuntu-latest
    steps:
      - run: echo trivial-required-check
"""

        issues = validate_ci_workflow_text(weakened)
        targets = {issue.target for issue in issues}

        self.assertIn("ci.yml:compile", targets)
        self.assertIn("ci.yml:unit_tests", targets)
        self.assertIn("ci.yml:docker_smoke", targets)
        self.assertNotIn(".github/workflows/ci.yml:required_verify_job", targets)

    def test_ci_guard_rejects_verify_skip_and_command_interpreter_overrides(self) -> None:
        current = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        weakened = current.replace(
            "  verify:\n    runs-on: ubuntu-latest",
            "  verify:\n    runs-on: self-hosted\n    container: attacker/example:latest\n    continue-on-error: true",
            1,
        ).replace(
            "      - name: Unit tests\n        run: python -m unittest discover -s tests -t .",
            "      - name: Unit tests\n        if: ${{ false }}\n        shell: echo {0}\n        env:\n          PYTHONPATH: ./fake\n        run: python -m unittest discover -s tests -t .",
            1,
        )

        issues = validate_ci_workflow_text(weakened)
        targets = {issue.target for issue in issues}

        self.assertIn("ci.yml:verify_continue-on-error", targets)
        self.assertIn("ci.yml:verify_container", targets)
        self.assertIn("ci.yml:verify_runner", targets)
        self.assertIn("ci.yml:verify_step_shell", targets)
        self.assertIn("ci.yml:unit_tests_condition", targets)
        self.assertIn("ci.yml:unit_tests_env", targets)

    def test_ci_guard_rejects_plain_scalar_command_continuation(self) -> None:
        current = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        weakened = current.replace(
            "        run: python -m unittest discover -s tests -t .",
            "        run: python -m unittest discover -s tests -t .\n          || true",
            1,
        )
        mapping_like = current.replace(
            "        run: python -m unittest discover -s tests -t .",
            "        run: python -m unittest discover -s tests -t .\n          true:|| true",
            1,
        )
        sequence_like = current.replace(
            "        run: python -m unittest discover -s tests -t .",
            "        run: python -m unittest discover -s tests -t .\n          - x|| true",
            1,
        )

        issues = validate_ci_workflow_text(weakened)
        targets = {issue.target for issue in issues}
        mapping_like_targets = {issue.target for issue in validate_ci_workflow_text(mapping_like)}
        sequence_like_targets = {issue.target for issue in validate_ci_workflow_text(sequence_like)}

        self.assertIn(".github/workflows/ci.yml:scalar_continuation", targets)
        self.assertIn(".github/workflows/ci.yml:scalar_continuation", mapping_like_targets)
        self.assertIn(".github/workflows/ci.yml:scalar_continuation", sequence_like_targets)

    def test_ci_guard_rejects_extra_verify_steps_and_checkout_ref_override(self) -> None:
        current = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        extra_step = current.replace(
            "      - name: Compile Python",
            "      - name: Replace reviewed tree\n"
            "        run: git checkout --force d5effee51cb115a055310c2858ac8ea2f7c06251\n"
            "      - name: Compile Python",
            1,
        )
        checkout_override = current.replace(
            "          persist-credentials: false",
            "          persist-credentials: false\n          ref: main",
        )

        extra_targets = {issue.target for issue in validate_ci_workflow_text(extra_step)}
        checkout_targets = {issue.target for issue in validate_ci_workflow_text(checkout_override)}

        self.assertIn("ci.yml:verify_step_inventory", extra_targets)
        self.assertIn("ci.yml:verify_step_inventory", checkout_targets)

    def test_ci_guard_rejects_duplicate_or_renamed_protected_check(self) -> None:
        current = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        duplicate_name = current.replace(
            "    name: compatibility (${{ matrix.os }}, Python ${{ matrix.python }})",
            "    name: verify",
            1,
        )
        renamed_verify = current.replace(
            "  verify:\n    runs-on: ubuntu-latest",
            "  verify:\n    name: not-verify\n    runs-on: ubuntu-latest",
            1,
        )
        dynamic_duplicate = current.replace(
            "    name: compatibility (${{ matrix.os }}, Python ${{ matrix.python }})",
            "    name: ${{ 'ver' }}${{ 'ify' }}",
            1,
        )

        duplicate_targets = {issue.target for issue in validate_ci_workflow_text(duplicate_name)}
        renamed_targets = {issue.target for issue in validate_ci_workflow_text(renamed_verify)}
        dynamic_targets = {issue.target for issue in validate_ci_workflow_text(dynamic_duplicate)}

        self.assertIn(".github/workflows/ci.yml:duplicate_verify_name", duplicate_targets)
        self.assertIn(".github/workflows/ci.yml:required_verify_name", renamed_targets)
        self.assertIn(".github/workflows/ci.yml:dynamic_job_name", dynamic_targets)

    def test_ci_guard_rejects_extended_false_pr_gate(self) -> None:
        current = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        weakened = current.replace(
            "if: ${{ github.event_name == 'pull_request' }}",
            "if: ${{ github.event_name == 'pull_request' && false }}",
            1,
        )

        issues = validate_ci_workflow_text(weakened)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("Strict PR release readiness check must run only on pull_request events", messages)

    def test_ci_guard_rejects_spoofed_trigger_and_broadened_permissions(self) -> None:
        current = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        weakened = current.replace(
            "  pull_request:\n",
            "  pull_request_target:\n  # pull_request:\n",
            1,
        ).replace(
            "permissions:\n  contents: read",
            "permissions:\n  contents: write",
            1,
        )

        issues = validate_ci_workflow_text(weakened)
        messages = "\n".join(issue.message for issue in issues)

        self.assertIn("exactly once on pull_request", messages)
        self.assertIn("forbidden additional triggers: pull_request_target", messages)
        self.assertIn("only top-level contents: read", messages)

    def test_ci_guard_rejects_mutable_actions_and_persisted_checkout_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "unsafe.yml").write_text(
                """name: unsafe
jobs:
  test:
    steps:
      - name: Checkout
        uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        with:
          persist-credentials: true
      - name: Mutable setup
        uses: actions/setup-python@v5
""",
                encoding="utf-8",
            )

            issues = validate_workflow_supply_chain(root)

        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("full commit SHA", messages)
        self.assertIn("persist-credentials: false", messages)

    def test_solo_review_boundary_accepts_current_repository(self) -> None:
        issues = validate_solo_maintainer_review_boundary(ROOT)

        self.assertFalse(issues)

    def test_solo_review_boundary_rejects_forgeable_automation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "rogue.yml").write_text(
                """
permissions:
  pull-requests: write
  statuses: write
  checks: write
jobs:
  forge:
    steps:
      # codex-double-check
      - run: gh api /pulls/1/reviews -f event='APPROVE'
""",
                encoding="utf-8",
            )
            (workflows / "auto-approve.yml").write_text(
                "name: legacy auto approval\n",
                encoding="utf-8",
            )
            (workflows / "inline.yml").write_text(
                'permissions: {"checks": "write", statuses: write}\n',
                encoding="utf-8",
            )
            (workflows / "write-all.yml").write_text(
                "permissions: write-all\n",
                encoding="utf-8",
            )
            (workflows / "flow-write-all.yml").write_text(
                "jobs:\n  forge: {runs-on: ubuntu-latest, permissions: write-all}\n",
                encoding="utf-8",
            )
            (workflows / "multiline-write.yml").write_text(
                "permissions:\n  checks:\n    write\n",
                encoding="utf-8",
            )
            (workflows / "explicit-mapping.yml").write_text(
                """permissions:
  contents: read
  ? checks
  : write
jobs:
  ? verify
  :
    runs-on: ubuntu-latest
""",
                encoding="utf-8",
            )
            (workflows / "dynamic-job-name.yml").write_text(
                """jobs:
  gate:
    name: ${{ 'verify' }}
    runs-on: ubuntu-latest
""",
                encoding="utf-8",
            )
            (workflows / "duplicate-verify.yml").write_text(
                """permissions: read-all
jobs:
  verify:
    runs-on: ubuntu-latest
  impersonate:
    name: verify
    runs-on: ubuntu-latest
""",
                encoding="utf-8",
            )
            (workflows / "anchored.yml").write_text(
                """x-write: &level write
permissions:
  checks: *level
""",
                encoding="utf-8",
            )
            (workflows / "anchored-write-all.yml").write_text(
                "permissions: &1 write-all\n",
                encoding="utf-8",
            )
            (workflows / "permission-block.yml").write_text(
                '"checks": >-\n  write\n',
                encoding="utf-8",
            )
            (workflows / "permission-tag.yml").write_text(
                "'checks': !!str write\n",
                encoding="utf-8",
            )
            (workflows / "quoted-permission.yml").write_text(
                'permissions: "read-all"\n',
                encoding="utf-8",
            )
            (workflows / "quoted-verify.yml").write_text(
                """permissions: read-all
jobs:
  "verify":
    runs-on: ubuntu-latest
""",
                encoding="utf-8",
            )
            (workflows / "inline-verify.yml").write_text(
                'jobs: {gate: {name: "verify", runs-on: ubuntu-latest}}\n',
                encoding="utf-8",
            )
            (workflows / "escaped-verify.yml").write_text(
                'jobs: {"ver\\u0069fy": {runs-on: ubuntu-latest}}\n',
                encoding="utf-8",
            )
            (workflows / "escaped-name.yml").write_text(
                'jobs: {gate: {name: "ver\\u0069fy", runs-on: ubuntu-latest}}\n',
                encoding="utf-8",
            )
            (workflows / "safe-block-scalar.yml").write_text(
                """name: it's safe
description: "&not-an-anchor"
permissions: read-all
jobs:
  document:
    runs-on: ubuntu-latest
    steps:
      - run: |
          echo 'checks: write &anchor *alias <<:'
""",
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text(
                (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            docs = root / "docs"
            docs.mkdir()
            (docs / "solo-maintainer-review.md").write_text(
                (ROOT / "docs" / "solo-maintainer-review.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            issues = validate_solo_maintainer_review_boundary(root)
            targets = {issue.target for issue in issues}

        self.assertIn(".github/workflows/rogue.yml:pull_requests_write", targets)
        self.assertIn(".github/workflows/rogue.yml:statuses_write", targets)
        self.assertIn(".github/workflows/rogue.yml:checks_write", targets)
        self.assertIn(".github/workflows/rogue.yml:automated_approval", targets)
        self.assertIn(".github/workflows/rogue.yml:legacy_receipt", targets)
        self.assertIn(".github/workflows/auto-approve.yml", targets)
        self.assertIn(".github/workflows/inline.yml:checks_write", targets)
        self.assertIn(".github/workflows/inline.yml:statuses_write", targets)
        self.assertIn(".github/workflows/write-all.yml:write_all", targets)
        self.assertIn(".github/workflows/flow-write-all.yml:write_all", targets)
        self.assertIn(
            ".github/workflows/flow-write-all.yml:flow_job",
            targets,
        )
        self.assertIn(
            ".github/workflows/multiline-write.yml:multiline_permission",
            targets,
        )
        self.assertIn(
            ".github/workflows/explicit-mapping.yml:yaml_indirection",
            targets,
        )
        self.assertIn(
            ".github/workflows/dynamic-job-name.yml:dynamic_job_name",
            targets,
        )
        self.assertIn(
            ".github/workflows/duplicate-verify.yml:required_check_job",
            targets,
        )
        self.assertIn(
            ".github/workflows/duplicate-verify.yml:required_check_name",
            targets,
        )
        self.assertIn(".github/workflows/anchored.yml:yaml_indirection", targets)
        self.assertIn(
            ".github/workflows/anchored-write-all.yml:yaml_indirection",
            targets,
        )
        self.assertIn(
            ".github/workflows/permission-block.yml:yaml_indirection",
            targets,
        )
        self.assertIn(
            ".github/workflows/permission-tag.yml:yaml_indirection",
            targets,
        )
        self.assertIn(
            ".github/workflows/quoted-permission.yml:yaml_indirection",
            targets,
        )
        self.assertIn(
            ".github/workflows/quoted-verify.yml:required_check_job",
            targets,
        )
        self.assertIn(
            ".github/workflows/inline-verify.yml:required_check_name",
            targets,
        )
        self.assertIn(
            ".github/workflows/inline-verify.yml:flow_jobs",
            targets,
        )
        self.assertIn(
            ".github/workflows/escaped-verify.yml:yaml_indirection",
            targets,
        )
        self.assertIn(
            ".github/workflows/escaped-name.yml:yaml_indirection",
            targets,
        )
        self.assertFalse(
            any(target.startswith(".github/workflows/safe-block-scalar.yml") for target in targets)
        )

    def test_solo_review_boundary_requires_auditable_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "AGENTS.md").write_text("missing receipt contract\n", encoding="utf-8")

            issues = validate_solo_maintainer_review_boundary(root)
            targets = {issue.target for issue in issues}

        self.assertIn("AGENTS.md:receipt", targets)
        self.assertIn("docs/solo-maintainer-review.md", targets)

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
      - run: python -m unittest discover -s tests -t .
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
      - run: python -m unittest discover -s tests -t .
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
      - run: python -m unittest discover -s tests -t .
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
      - run: python -m unittest discover -s tests -t .
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
      - run: python -m unittest discover -s tests -t .
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
      - run: python -m unittest discover -s tests -t .
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

    def test_pr_template_guard_rejects_relative_mcp_client_smoke_child(self) -> None:
        current = (ROOT / ".github" / "pull_request_template.md").read_text(
            encoding="utf-8"
        )
        weakened = current.replace(
            "<absolute-checkout>/scripts/ai_dememory.py",
            "scripts/ai_dememory.py",
        )

        issues = validate_template_text(weakened)

        self.assertTrue(
            any("must use an absolute" in issue.message for issue in issues),
            issues,
        )

    def test_pr_template_guard_requires_python_mcp_client_smoke_child(self) -> None:
        current = (ROOT / ".github" / "pull_request_template.md").read_text(
            encoding="utf-8"
        )
        weakened = current.replace(
            " --command-arg <absolute-checkout>/scripts/ai_dememory.py",
            "",
        )

        issues = validate_template_text(weakened)

        self.assertTrue(
            any("requires exactly one absolute" in issue.message for issue in issues),
            issues,
        )

    def test_pr_draft_guard_accepts_current_handoff_doc(self) -> None:
        issues = validate_pr_draft(ROOT)

        self.assertFalse(issues)

    def test_pr_draft_guard_requires_solo_maintainer_merge_contract(self) -> None:
        current = (ROOT / "docs" / "pr-draft.md").read_text(encoding="utf-8")
        weakened = (
            current.replace("codex-solo-review", "review receipt")
            .replace("expected_head_sha", "head check")
            .replace("Do not publish packages", "Avoid package publication")
        )

        issues = validate_pr_draft_text(weakened)
        targets = {issue.target for issue in issues}

        self.assertIn("pr_draft:solo_review_receipt", targets)
        self.assertIn("pr_draft:expected_head", targets)
        self.assertIn("pr_draft:high_risk_gate", targets)

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

    def test_adr_guard_rejects_duplicate_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adr_dir = root / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            template = """# ADR 0031: {title}

Status: Accepted

## Context
Context.
## Decision
Decision.
## Consequences
Benefit.
## Limitations
Limit.
## Future Work
Future.
## Dependencies
Dependency.
"""
            (adr_dir / "0031-first.md").write_text(template.format(title="First"), encoding="utf-8")
            (adr_dir / "0031-second.md").write_text(template.format(title="Second"), encoding="utf-8")

            issues = validate_adr_docs(root)

        self.assertTrue(any("duplicate ADR 0031" in issue.message for issue in issues))

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

    def test_release_checklist_guard_rejects_impossible_actions_creation_bypass(self) -> None:
        stale = """
## Publishing

- [ ] The ruleset rejects tag creation except for the GitHub Actions integration.
"""

        issues = validate_release_checklist_text(stale)

        self.assertTrue(
            any(
                issue.target == "release_checklist:impossible_native_actions_creation_bypass"
                for issue in issues
            )
        )

    def test_release_checklist_guard_requires_vault_binding_before_artifacts(self) -> None:
        stale = f"""
## Generated Artifacts

- [ ] `python3 scripts/ai_dememory.py index`
- [ ] {GENERATED_ARTIFACTS_VAULT_PRECONDITION}
"""

        issues = validate_release_checklist_text(stale)

        self.assertTrue(
            any(
                issue.target == "release_checklist:generated_artifacts_vault_binding"
                for issue in issues
            )
        )

    def test_release_checklist_guard_ignores_fenced_heading_decoy(self) -> None:
        stale = f"""
```markdown
## Generated Artifacts

- [ ] {GENERATED_ARTIFACTS_VAULT_PRECONDITION}
```

## Generated Artifacts

- [ ] `python3 scripts/ai_dememory.py index`
"""

        issues = validate_release_checklist_text(stale)

        self.assertTrue(
            any(
                issue.target == "release_checklist:generated_artifacts_vault_binding"
                for issue in issues
            )
        )

    def test_release_checklist_guard_rejects_duplicate_artifact_heading(self) -> None:
        stale = f"""
## Generated Artifacts

- [ ] {GENERATED_ARTIFACTS_VAULT_PRECONDITION}

## Generated Artifacts

- [ ] `python3 scripts/ai_dememory.py index`
"""

        issues = validate_release_checklist_text(stale)

        self.assertTrue(
            any(
                issue.target == "release_checklist:artifacts"
                and "duplicate heading" in issue.message
                for issue in issues
            )
        )

    def test_release_checklist_guard_ignores_false_fence_closer(self) -> None:
        stale = f"""
```markdown
```not-a-commonmark-close
## Generated Artifacts

- [ ] {GENERATED_ARTIFACTS_VAULT_PRECONDITION}
```
"""

        issues = validate_release_checklist_text(stale)

        self.assertTrue(
            any(issue.target == "release_checklist:artifacts" for issue in issues)
        )

    def test_release_checklist_guard_ignores_html_comment_heading(self) -> None:
        stale = f"""
<!--
## Generated Artifacts

- [ ] {GENERATED_ARTIFACTS_VAULT_PRECONDITION}
-->
"""

        issues = validate_release_checklist_text(stale)

        self.assertTrue(
            any(issue.target == "release_checklist:artifacts" for issue in issues)
        )

    def test_release_checklist_guard_rejects_indented_precondition_decoy(self) -> None:
        stale = f"""
## Generated Artifacts

    - [ ] {GENERATED_ARTIFACTS_VAULT_PRECONDITION}
"""

        issues = validate_release_checklist_text(stale)

        self.assertTrue(
            any(
                issue.target == "release_checklist:generated_artifacts_vault_binding"
                for issue in issues
            )
        )

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

    def test_release_checklist_guard_rejects_relative_mcp_client_smoke_child(self) -> None:
        current = (ROOT / "docs" / "release-v2-checklist.md").read_text(
            encoding="utf-8"
        )
        weakened = current.replace(
            "<absolute-checkout>/scripts/ai_dememory.py",
            "scripts/ai_dememory.py",
        )

        issues = validate_release_checklist_text(weakened)

        self.assertTrue(
            any("must use an absolute" in issue.message for issue in issues),
            issues,
        )

    def test_release_checklist_guard_requires_python_mcp_client_smoke_child(self) -> None:
        current = (ROOT / "docs" / "release-v2-checklist.md").read_text(
            encoding="utf-8"
        )
        weakened = current.replace(
            " --command-arg <absolute-checkout>/scripts/ai_dememory.py",
            "",
        )

        issues = validate_release_checklist_text(weakened)

        self.assertTrue(
            any("requires exactly one absolute" in issue.message for issue in issues),
            issues,
        )

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

    def test_artifact_guard_rejects_generated_artifact_already_committed_in_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "config", "user.email", "unit@example.test")
            git(root, "config", "user.name", "Unit Test")
            generated = root / "indexes" / "memory.sqlite"
            generated.parent.mkdir(parents=True)
            generated.write_bytes(b"SQLite fixture")
            git(root, "add", "-f", "indexes/memory.sqlite")
            git(root, "commit", "-m", "add generated artifact fixture")

            issues = validate_staged_artifacts(root)

        self.assertEqual([issue.path for issue in issues], ["indexes/memory.sqlite"])

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

    def test_vault_setup_guard_rejects_force_broad_pathspec_and_gitignore_negation(self) -> None:
        docs = """# Create A Memory Repo

```bash
git add --force .
git add :(glob)reports/**
```

Private vault setup does not stage generated artifact directories.
Commit placeholders: distilled/README.md indexes/README.md reports/README.md.
ai-dememory vault-template export does not create a GitHub repository.
Generated distilled indexes reports.
"""
        unsafe_gitignore = "\n".join((*REQUIRED_IGNORES, "!**/*.md"))

        doc_issues = validate_create_memory_repo_text(docs)
        ignore_issues = validate_gitignore_text("vault-template/.gitignore", unsafe_gitignore)

        doc_messages = "\n".join(issue.message for issue in doc_issues)
        self.assertIn("must not use force", doc_messages)
        self.assertIn("broad pathspec", doc_messages)
        self.assertIn("unsafe gitignore negation", "\n".join(issue.message for issue in ignore_issues))

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
        evidence = build_release_evidence(
            ROOT,
            pr_url="https://github.com/GonzaloTorreras/ai-dememory/pull/250",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = write_release_evidence_report(
                root,
                evidence,
                "reports/test-v2-release-evidence.md",
            )
            report_text = report.read_text(encoding="utf-8")
            report_path = report.relative_to(root).as_posix()

        self.assertEqual(report_path, "reports/test-v2-release-evidence.md")
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
        self.assertIn("report path must stay inside the memory root", error.getvalue())
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

    def test_manual_acceptance_pass_requires_reviewed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "requires at least one reviewed artifact"):
                record_acceptance(
                    root,
                    "mcp-client-installed",
                    "passed",
                    "Unit Test",
                    "A summary without a reproducible artifact is insufficient.",
                )

            self.assertFalse((root / "inbox" / "release-acceptance").exists())

    def test_legacy_testpypi_acceptance_does_not_complete_current_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "inbox" / "release-acceptance"
            directory.mkdir(parents=True)
            (directory / "20260701T000000Z_testpypi-publish.md").write_text(
                "\n".join(
                    [
                        "---",
                        "type: manual-acceptance",
                        "status: passed",
                        "acceptance_item: testpypi-publish",
                        "reviewed_by: Legacy Reviewer",
                        "reviewed_at: 2026-07-01",
                        "summary: Legacy publish.yml evidence.",
                        "artifacts: []",
                        "---",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            legacy_status = next(
                item for item in acceptance_status(root) if item.id == "testpypi-publish"
            )
            new_path = record_acceptance(
                root,
                "testpypi-publish",
                "passed",
                "Unit Test",
                "Both exact-tuple dispatches and the TestPyPI install were reviewed.",
                artifacts=["https://test.pypi.org/project/ai-dememory/2.1.0/"],
            )
            current_status = next(
                item for item in acceptance_status(root) if item.id == "testpypi-publish"
            )
            new_record_text = new_path.read_text(encoding="utf-8")

        self.assertFalse(legacy_status.completed)
        self.assertEqual(legacy_status.required_revision, 3)
        self.assertEqual(legacy_status.records[-1].revision, 1)
        self.assertTrue(current_status.completed)
        self.assertEqual(current_status.records[-1].revision, ACCEPTANCE_REVISIONS["testpypi-publish"])
        self.assertIn(
            "acceptance_revision: 3",
            new_record_text,
        )

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
                    artifacts=["unit-test:mcp-client-installed"],
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
                    artifacts=[f"unit-test:{item_id}"],
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
                artifacts=["unit-test:mcp-client-docker"],
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
                artifacts=["unit-test:mcp-client-docker-retry"],
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
                artifacts=["unit-test:mcp-client-installed"],
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
        self.assertIn(
            "release workflow validation, exact-artifact build, TestPyPI publish, and post-index install logs",
            output.getvalue(),
        )

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
                artifacts=["unit-test:mcp-client-installed"],
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
                artifacts=["unit-test:mcp-client-installed"],
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
                record_acceptance(
                    root,
                    item_id,
                    "passed",
                    "Unit Test",
                    f"Reviewed {item_id} acceptance.",
                    artifacts=[f"unit-test:{item_id}"],
                )

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

    def test_hook_event_capture_stops_at_pending_capacity_but_keeps_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = capture_hook_event(
                root,
                "UserPromptSubmit",
                '{"prompt":"First reviewed candidate."}',
                max_pending=1,
            )
            duplicate = capture_hook_event(
                root,
                "UserPromptSubmit",
                '{"prompt":"First reviewed candidate."}',
                max_pending=1,
            )
            blocked = capture_hook_event(
                root,
                "UserPromptSubmit",
                '{"prompt":"Second reviewed candidate."}',
                max_pending=1,
            )
            files = list((root / "inbox" / "session-events").glob("*.md"))

        self.assertIsNotNone(first)
        self.assertEqual(duplicate, first)
        self.assertIsNone(blocked)
        self.assertEqual(len(files), 1)

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

    def test_hook_event_raw_payload_uses_non_injectable_dynamic_fence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = "before\n```\n# injected heading\n```json\nafter"

            path = capture_hook_event(
                root,
                "UserPromptSubmit",
                payload,
                capture_raw=True,
            )
            text = path.read_text(encoding="utf-8") if path else ""

        self.assertIsNotNone(path)
        self.assertIn("\n````json\n", text)
        self.assertIn("\n````\n", text)
        self.assertIn(payload, text)

    def test_fresh_vault_hook_captures_ignores_inbox_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            init_output = io.StringIO()
            with redirect_stdout(init_output):
                init_exit = cli_main(["init", str(root), "--no-wizard"])
            captures_output = io.StringIO()
            with redirect_stdout(captures_output):
                captures_exit = cli_main(["--root", str(root), "hooks", "captures", "--json"])
            summary = json.loads(captures_output.getvalue())
            health = setup_health(root, target_platform="linux", mode="installed")

        self.assertEqual(init_exit, 0)
        self.assertEqual(captures_exit, 0)
        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(summary["malformed_count"], 0)
        self.assertEqual(summary["malformed"], [])
        self.assertTrue(health["recall_review"]["available"])
        self.assertEqual(health["recall_review"]["freshness"]["reviewed_promotions"], 0)
        self.assertFalse(health["retrieval_evaluated"])
        self.assertFalse(health["release_ready"])

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
            copy_template_tree(root)
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
            copy_template_tree(root)
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
            copy_template_tree(root)
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
            copy_template_tree(root)
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

    def test_generated_hook_command_keeps_shell_metacharacters_in_root_argument(self) -> None:
        sentinel = "AI_DEMEMORY_HOOK_INJECTION_SENTINEL"
        root = Path(f"C:\\vault&echo.{sentinel}") if os.name == "nt" else Path(f"/tmp/vault&echo {sentinel}")
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "hook-event").write_text(
                "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            config = hook_config("codex", command=sys.executable, root=root)
            definition = config["hooks"]["UserPromptSubmit"][0]["hooks"][0]
            command_line = definition["commandWindows"] if os.name == "nt" else definition["command"]

            completed = subprocess.run(
                command_line,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                cwd=tmp,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        observed_args = json.loads(completed.stdout.strip())
        self.assertEqual(observed_args[-2:], ["--root", str(root)])
        expected = serialize_hook_command(
            [
                sys.executable,
                "hook-event",
                "dispatch",
                "--provider",
                "codex",
                "--event",
                "UserPromptSubmit",
                "--public-only",
                "--root",
                str(root),
            ],
            windows=os.name == "nt",
        )
        self.assertEqual(command_line, expected)

    @unittest.skipUnless(os.name == "nt", "cmd.exe environment expansion is Windows-specific")
    def test_windows_hook_command_does_not_expand_environment_from_root(self) -> None:
        sentinel = "AI_DEMEMORY_PERCENT_EXPANSION_SENTINEL"
        root = Path("C:\\vault%AI_DEMEMORY_HOOK_POC%")
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "hook-event").write_text(
                "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            config = hook_config("codex", command=sys.executable, root=root)
            command_line = config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["commandWindows"]
            environment = os.environ.copy()
            environment["AI_DEMEMORY_HOOK_POC"] = f'"&echo.{sentinel}&echo "'

            completed = subprocess.run(
                command_line,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                env=environment,
                cwd=tmp,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        observed_args = json.loads(completed.stdout.strip())
        self.assertEqual(observed_args[-2:], ["--root", str(root)])
        self.assertNotIn("%AI_DEMEMORY_HOOK_POC%", command_line)

    @unittest.skipUnless(os.name == "nt", "Windows launcher round-trip is Windows-specific")
    def test_windows_hook_command_round_trips_argv_without_shell_interpolation(self) -> None:
        payload = 'C:\\vault%AI_DEMEMORY_HOOK_POC%&echo.bad!VALUE!`$()'
        command_line = serialize_hook_command(
            [sys.executable, "-c", "import sys; print(repr(sys.argv[1]))", payload],
            windows=True,
        )
        environment = os.environ.copy()
        environment["AI_DEMEMORY_HOOK_POC"] = '"&whoami&echo "'

        completed = subprocess.run(
            command_line,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=environment,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), repr(payload))

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
        self.assertIn("source checkout is never an implicit vault", first_text)
        self.assertIn("only `public`-sensitivity recall may influence", first_text)
        self.assertIn("`public_only=true`, `include_working_memory=false`", first_text)
        self.assertIn("`memory.search` (`public_only=true`)", first_text)
        self.assertIn("Do not use auto context", first_text)
        self.assertIn("treat the whole injected block as tainted context", first_text)
        self.assertNotIn("public/internal", first_text)
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
        self.assertIn("source checkout is never an implicit vault", claude_text)
        self.assertIn("only `public`-sensitivity recall may influence", claude_text)
        self.assertIn("`public_only=true`, `include_working_memory=false`", claude_text)
        self.assertIn("Do not use auto context", claude_text)
        self.assertNotIn("public/internal", claude_text)

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
        context_tool = next(tool for tool in TOOLS if tool["name"] == "memory.context")
        search_tool = next(tool for tool in TOOLS if tool["name"] == "memory.search")
        get_tool = next(tool for tool in TOOLS if tool["name"] == "memory.get")
        self.assertIn("public_only", context_tool["inputSchema"]["properties"])
        self.assertIn("public_only", search_tool["inputSchema"]["properties"])
        self.assertIn("public_only", get_tool["inputSchema"]["properties"])
        self.assertIn("non_public_filtered_items", context_tool["outputSchema"]["properties"])
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
                {"platform": "windows", "mode": "docker", "image": PINNED_TEST_IMAGE},
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
        self.assertTrue(
            any(
                "ai-dememory --root" in entry["line"]
                and "maintenance run --profile daily --timeout-seconds 300" in entry["line"]
                for entry in plan["cron_entries"]
            )
        )
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
        self.assertIn(PINNED_TEST_IMAGE, docker_plan["commands"][0]["run_command"])
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
