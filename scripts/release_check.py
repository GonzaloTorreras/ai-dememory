#!/usr/bin/env python3
"""Run non-runtime v2 release readiness checks."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import urlparse

from acceptance_guard import validate_acceptance_checklist
from adr_guard import validate_adr_docs
from ci_guard import validate_ci_workflow
from artifact_guard import validate_staged_artifacts
from doctor import run_checks
from eval_recall import load_fixtures
from memorylib import repo_root
from mcp_inventory import build_inventory, validate_inventory_docs
from pr_draft_guard import validate_pr_draft
from pr_template_guard import validate_pr_template
from publish_guard import validate_publish_workflow
from release_checklist_guard import validate_release_checklist
from roadmap_status import roadmap_status
from vault_setup_guard import validate_vault_setup
from verify_mcp_contract import validate_contract


EXPECTED_VERSION = "2.0.0rc3"
EXPECTED_PLUGIN_MCP_TOOLS = (
    "memory.search",
    "memory.get",
    "memory.context",
    "memory.graph",
    "memory.doctor",
    "memory.validate_status",
    "memory.write_proposal",
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
    "memory.outcome",
    "memory.lifecycle_scores",
    "memory.sleep_plan",
    "memory.working_current",
    "memory.working_status",
    "memory.working_snapshot",
    "memory.working_handoff",
    "memory.maintenance_status",
    "memory.providers_detect",
    "memory.providers_status",
    "memory.providers_plan",
    "memory.setup_plan",
    "memory.setup_health",
    "memory.capture_import",
    "memory.git_lessons",
    "memory.schedule_plan",
    "memory.schedule_status",
    "memory.schedule_environment",
    "memory.provenance_status",
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
    "memory.review_false_positives",
    "memory.review_stale_false_positives",
    "memory.false_positive_ignore",
    "memory.false_positive_unignore",
    "memory.review_conflicts",
    "memory.conflict_dismiss",
    "memory.conflict_keep",
    "memory.conflict_merge_proposal",
    "memory.review_modes",
    "memory.review_configure_mode",
    "memory.review_plan",
    "memory.review_recommendation",
    "memory.review_recommendations",
    "memory.review_recommendation_archive_status",
    "memory.review_recommendation_archive_restore_preview",
    "memory.review_recommendation_outcome_report",
    "memory.review_recommendation_outcome",
)
EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS = (
    "memory.consolidate",
    "memory.import_chats",
    "memory.maintenance_run",
    "memory.mark_seen",
    "memory.reindex",
    "memory.secret_scan",
    "memory.sleep_apply_reviewed",
)


@dataclass(frozen=True)
class ReleaseCheck:
    name: str
    status: str
    detail: str


def ok(name: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(name, "ok", detail)


def warn(name: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(name, "warn", detail)


def fail(name: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(name, "fail", detail)


def check_doctor(root: Path) -> ReleaseCheck:
    checks = run_checks(root)
    failures = [check for check in checks if check.status == "fail"]
    if failures:
        return fail("doctor", f"{len(failures)} failing check(s)")
    warnings = [check for check in checks if check.status == "warn"]
    if warnings:
        return warn("doctor", f"{len(warnings)} warning(s)")
    return ok("doctor", f"{len(checks)} check(s)")


def check_versions(root: Path) -> ReleaseCheck:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    init_text = (root / "ai_dememory_tool" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", init_text)
    package_version = match.group(1) if match else None
    if project_version != package_version:
        return fail("version", f"pyproject={project_version}, package={package_version}")
    if project_version != EXPECTED_VERSION:
        return warn("version", f"current version is {project_version}, expected {EXPECTED_VERSION}")
    return ok("version", project_version)


def check_required_docs(root: Path) -> ReleaseCheck:
    required = [
        "LICENSE",
        "AGENTS.md",
        "CLAUDE.md",
        "Dockerfile",
        ".dockerignore",
        "docs/mcp-v2.md",
        "docs/mcp-v2-gap-analysis.md",
        "docs/install.md",
        "docs/distribution.md",
        "docs/create-memory-repo.md",
        "docs/import-capture.md",
        "docs/git-lessons.md",
        "docs/vector-migration.md",
        "docs/local-mcp.md",
        "docs/local-api.md",
        "docs/memory-graph.md",
        "docs/operational-loop.md",
        "docs/roadmap-status.md",
        "docs/scheduler.md",
        "docs/scheduler-plugin-blueprint.md",
        "docs/hooks.md",
        "docs/codex-plugin.md",
        "docs/review-workflows.md",
        "docs/sleep-consolidation.md",
        "docs/adr/0001-review-and-conflict-workflows.md",
        "docs/adr/0002-configurable-review-modes.md",
        "docs/adr/0003-lifecycle-scoring.md",
        "docs/adr/0004-safe-sleep-consolidation.md",
        "docs/adr/0005-hook-provider-config.md",
        "docs/adr/0006-managed-hook-instruction-blocks.md",
        "docs/adr/0007-import-capture-review-candidates.md",
        "docs/adr/0008-git-lesson-capture.md",
        "docs/adr/0009-measured-vector-search-gate.md",
        "docs/adr/0010-mcp-inventory-drift-check.md",
        "docs/adr/0011-reusable-install-smoke-runner.md",
        "docs/adr/0012-manual-trusted-publishing-guard.md",
        "docs/adr/0013-v2-release-evidence-report.md",
        "docs/adr/0014-generated-mcp-client-config-smoke.md",
        "docs/adr/0015-durable-provenance-audit.md",
        "docs/adr/0016-manual-acceptance-evidence.md",
        "docs/adr/0017-recall-fixture-promotion.md",
        "docs/adr/0018-expanded-install-smoke-v2-commands.md",
        "docs/adr/0019-ci-workflow-guard.md",
        "docs/adr/0020-generated-artifact-stage-guard.md",
        "docs/adr/0021-expanded-mcp-runtime-smoke.md",
        "docs/adr/0022-local-rest-api-smoke.md",
        "docs/adr/0023-pr-template-guard.md",
        "docs/adr/0231-pr-draft-handoff-guard.md",
        "docs/adr/0232-roadmap-status.md",
        "docs/adr/0233-mcp-roadmap-status.md",
        "docs/adr/0234-roadmap-status-smoke.md",
        "docs/adr/0024-manual-acceptance-checklist-guard.md",
        "docs/adr/0025-blocked-manual-acceptance-evidence.md",
        "docs/adr/0026-docker-maintenance-schedule-plan.md",
        "docs/adr/0027-canonical-review-mode-names.md",
        "docs/adr/0028-cron-maintenance-export.md",
        "docs/adr/0029-manual-acceptance-verify-gate.md",
        "docs/adr/0030-mcp-manual-acceptance-readiness.md",
        "docs/adr/0031-adr-quality-guard.md",
        "docs/adr/0032-release-checklist-guard.md",
        "docs/adr/0033-release-evidence-readiness-summary.md",
        "docs/adr/0034-recall-fixture-freshness-status.md",
        "docs/adr/0035-mcp-recall-fixture-status.md",
        "docs/adr/0036-mcp-vector-readiness-status.md",
        "docs/adr/0037-mcp-durable-provenance-status.md",
        "docs/adr/0038-mcp-working-memory-tools.md",
        "docs/adr/0039-codex-plugin-working-session-skill.md",
        "docs/adr/0040-mcp-doctor-status.md",
        "docs/adr/0041-profile-aware-doctor.md",
        "docs/adr/0042-doctor-profile-summary.md",
        "docs/adr/0043-install-smoke-doctor-summary.md",
        "docs/adr/0044-docker-client-config-smoke.md",
        "docs/adr/0045-recall-fixture-review-plan.md",
        "docs/adr/0046-mcp-recall-review-plan.md",
        "docs/adr/0047-manual-acceptance-plan.md",
        "docs/adr/0048-mcp-manual-acceptance-plan.md",
        "docs/adr/0049-release-evidence-acceptance-plan.md",
        "docs/adr/0050-release-evidence-blockers.md",
        "docs/adr/0051-mcp-release-evidence.md",
        "docs/adr/0052-install-smoke-release-evidence.md",
        "docs/adr/0053-docker-smoke-release-evidence.md",
        "docs/adr/0054-maintenance-lifecycle-artifacts.md",
        "docs/adr/0055-maintenance-artifact-status.md",
        "docs/adr/0056-install-smoke-maintenance-artifact-status.md",
        "docs/adr/0057-docker-smoke-maintenance-artifact-status.md",
        "docs/adr/0058-manual-acceptance-artifact-guidance.md",
        "docs/adr/0059-search-match-explanations.md",
        "docs/adr/0060-working-status-summary.md",
        "docs/adr/0061-lifecycle-feedback-receipts.md",
        "docs/adr/0062-outcome-feedback-receipts.md",
        "docs/adr/0063-mcp-auto-context.md",
        "docs/adr/0064-mcp-conflict-keep-resolution.md",
        "docs/adr/0065-mcp-false-positive-ignore-receipts.md",
        "docs/adr/0066-mcp-schedule-status.md",
        "docs/adr/0067-mcp-provider-status.md",
        "docs/adr/0068-plugin-mcp-tool-surface-guard.md",
        "docs/adr/0069-plugin-mcp-config-smoke.md",
        "docs/adr/0070-readme-mcp-inventory-guard.md",
        "docs/adr/0071-private-vault-setup-artifact-guard.md",
        "docs/adr/0072-vault-setup-ci-gate.md",
        "docs/adr/0073-vault-template-export-command.md",
        "docs/adr/0074-install-smoke-vault-template-export.md",
        "docs/adr/0075-docker-smoke-vault-template-export.md",
        "docs/adr/0076-publish-workflow-preflight.md",
        "docs/adr/0077-package-build-smoke.md",
        "docs/adr/0105-package-build-stale-artifact-preflight.md",
        "docs/adr/0106-ci-post-smoke-artifact-guard.md",
        "docs/adr/0107-ci-pr-gated-mcp-runtime-smoke.md",
        "docs/adr/0108-docker-vault-template-export-target.md",
        "docs/adr/0109-release-evidence-without-git.md",
        "docs/adr/0127-publish-workflow-smoke-gates.md",
        "docs/adr/0128-testpypi-acceptance-publish-preflight.md",
        "docs/adr/0129-capture-miss-dry-run.md",
        "docs/adr/0130-recall-miss-candidate-check.md",
        "docs/adr/0131-mcp-recall-miss-candidate.md",
        "docs/adr/0132-recall-review-candidate-guidance.md",
        "docs/adr/0133-scheduler-plugin-blueprint.md",
        "docs/adr/0134-mcp-schedule-plan-cron-entries.md",
        "docs/adr/0229-cli-schedule-plan.md",
        "docs/adr/0135-setup-plan-cron-export-commands.md",
        "docs/adr/0136-maintenance-provider-readiness.md",
        "docs/adr/0137-provider-import-dry-run.md",
        "docs/adr/0138-provider-import-idempotency.md",
        "docs/adr/0139-mcp-git-lessons.md",
        "docs/adr/0140-git-lesson-idempotency.md",
        "docs/adr/0141-hook-event-idempotency.md",
        "docs/adr/0142-scheduler-input-validation.md",
        "docs/adr/0143-hook-json-fingerprints.md",
        "docs/adr/0144-mcp-schedule-validation-status.md",
        "docs/adr/0145-scheduler-environment-diagnostic.md",
        "docs/adr/0146-false-positive-review-due-status.md",
        "docs/adr/0147-maintenance-review-due-summary.md",
        "docs/adr/0148-false-positive-due-only-filter.md",
        "docs/adr/0149-stale-false-positive-suppression-audit.md",
        "docs/adr/0150-maintenance-stale-suppression-summary.md",
        "docs/adr/0151-scheduler-review-due-summary.md",
        "docs/adr/0152-maintenance-conflict-review-summary.md",
        "docs/adr/0153-setup-health-summary.md",
        "docs/adr/0154-maintenance-profile-dry-run.md",
        "docs/adr/0155-setup-health-maintenance-preflight.md",
        "docs/adr/0110-release-evidence-recall-freshness.md",
        "docs/adr/0111-release-evidence-recall-review-plan.md",
        "docs/adr/0112-recall-promotion-closes-source-miss.md",
        "docs/adr/0113-recall-miss-review-outcomes.md",
        "docs/adr/0114-recall-review-resolved-summary.md",
        "docs/adr/0115-recall-review-plan-report.md",
        "docs/adr/0116-manual-acceptance-plan-report.md",
        "docs/adr/0186-manual-acceptance-packet.md",
        "docs/adr/0187-recall-review-packet.md",
        "docs/adr/0207-recall-review-packet-pagination.md",
        "docs/adr/0210-recall-review-packet-metadata.md",
        "docs/adr/0212-recall-review-packet-archive.md",
        "docs/adr/0214-recall-review-packet-archive-status.md",
        "docs/adr/0216-mcp-recall-review-packet-archive-status.md",
        "docs/adr/0218-generated-packet-archive-retention-plan.md",
        "docs/adr/0219-setup-plan-generated-archive-retention.md",
        "docs/adr/0220-setup-health-generated-packet-archives.md",
        "docs/adr/0221-maintenance-generated-packet-archives.md",
        "docs/adr/0222-release-evidence-maintenance-summary.md",
        "docs/adr/0223-release-evidence-next-actions.md",
        "docs/adr/0235-release-evidence-handoff-commands.md",
        "docs/adr/0236-publish-plan.md",
        "docs/adr/0237-mcp-publish-plan.md",
        "docs/adr/0238-mcp-publish-plan-smoke.md",
        "docs/adr/0239-release-evidence-publish-plan-commands.md",
        "docs/adr/0240-publish-plan-workflow-url.md",
        "docs/adr/0241-plugin-server-only-tool-classification.md",
        "docs/adr/0242-acceptance-plan-template-metadata.md",
        "docs/adr/0243-release-evidence-acceptance-metadata.md",
        "docs/adr/0244-acceptance-command-safe-quoting.md",
        "docs/adr/0224-maintenance-artifact-freshness.md",
        "docs/adr/0225-sleep-dry-run-propose-aliases.md",
        "docs/adr/0226-sleep-apply-reviewed-alias.md",
        "docs/adr/0227-weekly-maintenance-sleep-plan-report.md",
        "docs/adr/0230-schedule-plan-smoke.md",
        "docs/adr/0208-manual-acceptance-packet-pagination.md",
        "docs/adr/0209-manual-acceptance-packet-metadata.md",
        "docs/adr/0211-manual-acceptance-packet-archive.md",
        "docs/adr/0213-manual-acceptance-packet-archive-status.md",
        "docs/adr/0215-mcp-manual-acceptance-packet-archive-status.md",
        "docs/adr/0188-review-recommendation-artifacts.md",
        "docs/adr/0189-review-recommendation-status.md",
        "docs/adr/0190-review-recommendation-outcome-links.md",
        "docs/adr/0191-review-recommendation-outcome-status.md",
        "docs/adr/0204-review-recommendation-outcome-report.md",
        "docs/adr/0205-mcp-review-recommendation-outcome-report.md",
        "docs/adr/0206-review-recommendation-outcome-report-pagination.md",
        "docs/adr/0192-mcp-manual-acceptance-packet.md",
        "docs/adr/0193-mcp-recall-review-packet.md",
        "docs/adr/0194-mcp-release-evidence-report.md",
        "docs/adr/0195-maintenance-review-recommendation-summary.md",
        "docs/adr/0196-review-recommendation-archive.md",
        "docs/adr/0197-review-recommendation-archive-status.md",
        "docs/adr/0198-review-recommendation-archive-restore.md",
        "docs/adr/0199-mcp-review-recommendation-archive-restore-preview.md",
        "docs/adr/0200-mcp-review-recommendation-archive-status.md",
        "docs/adr/0201-review-recommendation-recursive-archive-partitions.md",
        "docs/adr/0202-review-recommendation-archive-status-pagination.md",
        "docs/adr/0203-review-recommendation-archive-invalid-pagination.md",
        "docs/adr/0117-setup-plan-generated-reports.md",
        "docs/adr/0217-setup-plan-generated-archive-status.md",
        "docs/adr/0118-release-evidence-report-path-guard.md",
        "docs/adr/0119-vector-readiness-report-path-guard.md",
        "docs/adr/0120-durable-provenance-report-path-guard.md",
        "docs/adr/0121-lifecycle-report-path-guard.md",
        "docs/adr/0122-sleep-plan-report-path-guard.md",
        "docs/adr/0123-consolidation-report-path-guard.md",
        "docs/adr/0124-review-report-path-guard.md",
        "docs/adr/0125-maintenance-report-dir-guard.md",
        "docs/adr/0126-recall-review-report-secret-scan.md",
        "docs/adr/0078-provider-setup-plan.md",
        "docs/adr/0228-provider-configure-dry-run.md",
        "docs/adr/0079-local-setup-plan.md",
        "docs/adr/0080-manual-acceptance-template.md",
        "docs/adr/0081-mcp-false-positive-unignore.md",
        "docs/adr/0082-mcp-review-mode-configuration.md",
        "docs/adr/0083-mcp-conflict-dismiss-receipts.md",
        "docs/adr/0084-mcp-conflict-merge-proposal-receipts.md",
        "docs/adr/0085-mcp-conflict-keep-reviewer-receipts.md",
        "docs/adr/0086-plugin-review-receipt-tools.md",
        "docs/adr/0087-mcp-client-enabled-tools-smoke.md",
        "docs/adr/0088-mcp-client-tools-list-pagination-smoke.md",
        "docs/adr/0089-mcp-runtime-list-pagination-smoke.md",
        "docs/adr/0090-mcp-runtime-list-identity-smoke.md",
        "docs/adr/0091-mcp-client-single-session-pagination-smoke.md",
        "docs/adr/0092-mcp-client-initialized-notification-smoke.md",
        "docs/adr/0093-mcp-runtime-initialized-notification-smoke.md",
        "docs/adr/0094-mcp-client-response-id-smoke.md",
        "docs/adr/0095-mcp-runtime-response-id-smoke.md",
        "docs/adr/0096-install-smoke-initialized-notification.md",
        "docs/adr/0097-install-smoke-response-id.md",
        "docs/adr/0098-install-smoke-missing-response-diagnostics.md",
        "docs/adr/0099-install-smoke-unexpected-response-id.md",
        "docs/adr/0100-install-smoke-invalid-response-id.md",
        "docs/adr/0101-install-smoke-duplicate-response-id.md",
        "docs/adr/0102-install-smoke-result-field-diagnostics.md",
        "docs/adr/0103-install-smoke-result-type-diagnostics.md",
        "docs/adr/0104-install-smoke-protocol-version-diagnostics.md",
        "docs/memory-quality.md",
        "docs/operations.md",
        "docs/mcp-client-config.md",
        "docs/pr-draft.md",
        "docs/release-v2-checklist.md",
        ".github/workflows/publish.yml",
        ".github/pull_request_template.md",
        "vault-template/.ai-dememory.toml",
        "vault-template/README.md",
        "vault-template/inbox/conflict-resolution/README.md",
        "vault-template/inbox/sleep-consolidation/README.md",
        "quality/recall-fixtures.json",
        "mcp/README.md",
        "mcp/server/README.md",
        "scripts/mcp_runtime_smoke.py",
        "scripts/mcp_client_smoke.py",
        "scripts/api_smoke.py",
        "scripts/install_smoke.py",
        "scripts/package_build_smoke.py",
        "scripts/ci_guard.py",
        "scripts/artifact_guard.py",
        "scripts/vault_setup_guard.py",
        "scripts/pr_template_guard.py",
        "scripts/pr_draft_guard.py",
        "scripts/acceptance_guard.py",
        "scripts/adr_guard.py",
        "scripts/release_checklist_guard.py",
        "scripts/mcp_inventory.py",
        "scripts/publish_guard.py",
        "scripts/roadmap_status.py",
        "scripts/release_evidence.py",
        "scripts/manual_acceptance.py",
        "scripts/eval_recall.py",
        "scripts/recall_fixtures.py",
        "scripts/capture_miss.py",
        "scripts/durable_provenance.py",
        "scripts/context_memory.py",
        "scripts/working_memory.py",
        "scripts/lifecycle.py",
        "scripts/sleep_consolidation.py",
        "scripts/review_memory.py",
        "scripts/graph_memory.py",
        "scripts/http_api.py",
        "scripts/context_memory.py",
        "scripts/working_memory.py",
        "scripts/lifecycle.py",
        "scripts/provider_import.py",
        "scripts/setup_plan.py",
        "scripts/git_lessons.py",
        "scripts/vector_gate.py",
        "scripts/maintenance.py",
        "scripts/schedule_memory.py",
        "scripts/hook_event.py",
        "scripts/verify_mcp_contract.py",
        "scripts/doctor.py",
        "skills/ai-dememory/SKILL.md",
        "skills/ai-dememory/agents/openai.yaml",
        ".agents/plugins/marketplace.json",
        "plugins/ai-dememory/.codex-plugin/plugin.json",
        "plugins/ai-dememory/.mcp.json",
        "plugins/ai-dememory/hooks/hooks.json",
        "plugins/ai-dememory/skills/memory-setup/SKILL.md",
        "plugins/ai-dememory/skills/memory-recall/SKILL.md",
        "plugins/ai-dememory/skills/memory-working-session/SKILL.md",
        "plugins/ai-dememory/skills/memory-review-inbox/SKILL.md",
        "plugins/ai-dememory/skills/memory-maintenance/SKILL.md",
    ]
    missing = [path for path in required if not (root / path).exists()]
    if missing:
        return fail("required_docs", "missing " + ", ".join(missing))
    return ok("required_docs", f"{len(required)} file(s)")


def check_license(root: Path) -> ReleaseCheck:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    license_text = (pyproject["project"].get("license") or {}).get("text", "")
    license_file = (root / "LICENSE").read_text(encoding="utf-8") if (root / "LICENSE").exists() else ""
    if "Private" in license_text:
        return fail("license", "pyproject still marks the package private")
    if "Apache-2.0" not in license_text:
        return fail("license", f"unexpected pyproject license: {license_text}")
    if "Apache License" not in license_file or "Version 2.0" not in license_file:
        return fail("license", "LICENSE does not describe Apache-2.0")
    return ok("license", license_text)


def check_vault_template(root: Path) -> ReleaseCheck:
    packaged = root / "ai_dememory_tool" / "templates" / "vault"
    repo_template = root / "vault-template"
    if not packaged.exists() or not repo_template.exists():
        return fail("vault_template", "missing packaged or repository vault template")
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
    if packaged_files != repo_files:
        return fail("vault_template", "vault-template/ differs from packaged template")
    return ok("vault_template", f"{len(repo_files)} file(s)")


def check_recall_fixtures(root: Path) -> ReleaseCheck:
    fixtures_path = root / "quality" / "recall-fixtures.json"
    try:
        fixtures = load_fixtures(fixtures_path)
    except (OSError, ValueError) as exc:
        return fail("recall_fixtures", str(exc))
    if not fixtures:
        return warn("recall_fixtures", "no recall fixtures defined")
    return ok("recall_fixtures", f"{len(fixtures)} fixture(s)")


def check_hook_instruction_blocks(root: Path) -> ReleaseCheck:
    expected = {
        "AGENTS.md": ("<!-- BEGIN AI-DEMEMORY HOOKS:codex -->", "<!-- END AI-DEMEMORY HOOKS:codex -->"),
        "CLAUDE.md": ("<!-- BEGIN AI-DEMEMORY HOOKS:claude -->", "<!-- END AI-DEMEMORY HOOKS:claude -->"),
    }
    missing: list[str] = []
    for relpath, markers in expected.items():
        path = root / relpath
        if not path.exists():
            missing.append(relpath)
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                missing.append(f"{relpath}:{marker}")
    if missing:
        return fail("hook_instruction_blocks", "missing " + ", ".join(missing))
    return ok("hook_instruction_blocks", "codex and claude managed blocks")


def check_contract(root: Path) -> ReleaseCheck:
    issues = validate_contract(root)
    if issues:
        return fail("mcp_contract", f"{len(issues)} issue(s)")
    return ok("mcp_contract", "valid")


def check_mcp_inventory_docs(root: Path) -> ReleaseCheck:
    issues = validate_inventory_docs(root)
    if issues:
        return fail("mcp_inventory_docs", f"{len(issues)} issue(s)")
    return ok("mcp_inventory_docs", "documented tool inventory matches server")


def check_publish_workflow(root: Path) -> ReleaseCheck:
    issues = validate_publish_workflow(root)
    if issues:
        return fail("publish_workflow", f"{len(issues)} issue(s)")
    return ok("publish_workflow", "manual Trusted Publishing workflow")


def check_ci_workflow(root: Path) -> ReleaseCheck:
    issues = validate_ci_workflow(root)
    if issues:
        return fail("ci_workflow", f"{len(issues)} issue(s)")
    return ok("ci_workflow", "required v2 gates present")


def check_staged_artifacts(root: Path) -> ReleaseCheck:
    issues = validate_staged_artifacts(root)
    if issues:
        detail = "; ".join(f"{issue.path}: {issue.reason}" for issue in issues[:3])
        return fail("staged_artifacts", f"{len(issues)} issue(s): {detail}")
    return ok("staged_artifacts", "no generated artifacts staged")


def check_vault_setup(root: Path) -> ReleaseCheck:
    issues = validate_vault_setup(root)
    if issues:
        detail = "; ".join(issue.message for issue in issues[:3])
        return fail("vault_setup", f"{len(issues)} issue(s): {detail}")
    return ok("vault_setup", "private vault setup docs avoid generated artifacts")


def check_pr_template(root: Path) -> ReleaseCheck:
    issues = validate_pr_template(root)
    if issues:
        detail = "; ".join(issue.message for issue in issues[:3])
        return fail("pr_template", f"{len(issues)} issue(s): {detail}")
    return ok("pr_template", "validation checklist matches v2 gates")


def check_pr_draft(root: Path) -> ReleaseCheck:
    issues = validate_pr_draft(root)
    if issues:
        detail = "; ".join(issue.message for issue in issues[:3])
        return fail("pr_draft", f"{len(issues)} issue(s): {detail}")
    return ok("pr_draft", "draft PR handoff is reusable and current")


def check_acceptance_checklist(root: Path) -> ReleaseCheck:
    issues = validate_acceptance_checklist(root)
    if issues:
        detail = "; ".join(issue.message for issue in issues[:3])
        return fail("acceptance_checklist", f"{len(issues)} issue(s): {detail}")
    return ok("acceptance_checklist", "manual acceptance items match registry")


def check_adr_docs(root: Path) -> ReleaseCheck:
    issues = validate_adr_docs(root)
    if issues:
        detail = "; ".join(issue.message for issue in issues[:3])
        return fail("adr_docs", f"{len(issues)} issue(s): {detail}")
    return ok("adr_docs", "ADR structure matches v2 decision record contract")


def check_release_checklist(root: Path) -> ReleaseCheck:
    issues = validate_release_checklist(root)
    if issues:
        detail = "; ".join(issue.message for issue in issues[:3])
        return fail("release_checklist", f"{len(issues)} issue(s): {detail}")
    return ok("release_checklist", "release checklist lists current v2 gates")


def check_roadmap_status(root: Path) -> ReleaseCheck:
    payload = roadmap_status(root)
    counts = dict(payload.get("status_counts") or {})
    missing = int(counts.get("missing_evidence", 0))
    if missing:
        return fail("roadmap_status", f"{missing} roadmap phase(s) missing evidence")
    implemented = int(counts.get("implemented", 0))
    gated = int(counts.get("gated", 0))
    return ok("roadmap_status", f"{implemented} implemented phase(s), {gated} gated phase(s)")


def check_codex_plugin(root: Path) -> ReleaseCheck:
    plugin_root = root / "plugins" / "ai-dememory"
    errors: list[str] = []
    manifest = load_json(plugin_root / ".codex-plugin" / "plugin.json", errors, "plugin manifest")
    mcp = load_json(plugin_root / ".mcp.json", errors, "plugin MCP config")
    hooks = load_json(plugin_root / "hooks" / "hooks.json", errors, "plugin hooks")
    marketplace = load_json(root / ".agents" / "plugins" / "marketplace.json", errors, "marketplace")

    if manifest:
        if manifest.get("name") != "ai-dememory":
            errors.append("plugin name must be ai-dememory")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version") or "")):
            errors.append("plugin version must be semver")
        if manifest.get("skills") not in {"./skills/", "skills"}:
            errors.append("plugin skills path must point to ./skills/")
        if manifest.get("mcpServers") not in {"./.mcp.json", ".mcp.json"}:
            errors.append("plugin mcpServers path must point to ./.mcp.json")
        if "hooks" in manifest:
            errors.append("plugin manifest must not use unsupported hooks field")

    inventory = build_inventory(root)
    inventory_tools = set(inventory["tools"])
    plugin_tools = set(EXPECTED_PLUGIN_MCP_TOOLS)
    server_only_tools = set(EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS)
    overlapping_classification = sorted(plugin_tools & server_only_tools)
    if overlapping_classification:
        errors.append("plugin MCP tool classifications overlap " + ", ".join(overlapping_classification[:5]))
    unclassified_tools = sorted(inventory_tools - plugin_tools - server_only_tools)
    if unclassified_tools:
        errors.append("plugin MCP tool classifications missing " + ", ".join(unclassified_tools[:5]))
    stale_classifications = sorted((plugin_tools | server_only_tools) - inventory_tools)
    if stale_classifications:
        errors.append("plugin MCP tool classifications stale " + ", ".join(stale_classifications[:5]))

    if mcp:
        servers = mcp.get("mcpServers") or {}
        if not isinstance(servers, dict) or "ai-dememory" not in servers:
            errors.append("plugin MCP config must define ai-dememory server")
        else:
            server = servers["ai-dememory"]
            if not isinstance(server, dict):
                errors.append("plugin MCP ai-dememory server must be an object")
            else:
                enabled_tools = server.get("enabled_tools")
                if not isinstance(enabled_tools, list) or not all(isinstance(tool, str) for tool in enabled_tools):
                    errors.append("plugin MCP enabled_tools must be a list of strings")
                else:
                    actual_tools = set(enabled_tools)
                    missing_tools = sorted(plugin_tools - actual_tools)
                    extra_tools = sorted(actual_tools - plugin_tools)
                    if missing_tools:
                        errors.append("plugin MCP enabled_tools missing " + ", ".join(missing_tools[:5]))
                    if extra_tools:
                        errors.append("plugin MCP enabled_tools has unexpected " + ", ".join(extra_tools[:5]))
                    if len(enabled_tools) != len(actual_tools):
                        errors.append("plugin MCP enabled_tools contains duplicates")

    docs_text = (root / "docs" / "codex-plugin.md").read_text(encoding="utf-8")
    missing_docs = [tool for tool in EXPECTED_PLUGIN_MCP_TOOLS if tool not in docs_text]
    if missing_docs:
        errors.append("docs/codex-plugin.md missing plugin tool " + ", ".join(missing_docs[:5]))
    if "Server-only MCP tools" not in docs_text:
        errors.append("docs/codex-plugin.md missing Server-only MCP tools section")
    missing_server_only_docs = [tool for tool in EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS if tool not in docs_text]
    if missing_server_only_docs:
        errors.append("docs/codex-plugin.md missing server-only tool " + ", ".join(missing_server_only_docs[:5]))

    if hooks:
        hook_events = set((hooks.get("hooks") or {}).keys())
        expected_events = {"UserPromptSubmit", "PreCompact", "PostCompact", "Stop"}
        missing_events = expected_events - hook_events
        if missing_events:
            errors.append("plugin hooks missing " + ", ".join(sorted(missing_events)))

    if marketplace:
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list) or not any(
            item.get("name") == "ai-dememory"
            and (item.get("source") or {}).get("path") == "./plugins/ai-dememory"
            for item in plugins
            if isinstance(item, dict)
        ):
            errors.append("marketplace must expose ./plugins/ai-dememory")

    skill_root = plugin_root / "skills"
    expected_skills = {
        "memory-setup",
        "memory-recall",
        "memory-working-session",
        "memory-review-inbox",
        "memory-maintenance",
    }
    for skill in expected_skills:
        path = skill_root / skill / "SKILL.md"
        if not path.exists():
            errors.append(f"missing plugin skill {skill}")
            continue
        frontmatter = extract_frontmatter(path)
        if not frontmatter:
            errors.append(f"plugin skill {skill} missing frontmatter")
            continue
        if "name:" not in frontmatter or "description:" not in frontmatter:
            errors.append(f"plugin skill {skill} must include name and description")

    if errors:
        return fail("codex_plugin", f"{len(errors)} issue(s): " + "; ".join(errors[:3]))
    return ok(
        "codex_plugin",
        f"manifest, MCP config with {len(EXPECTED_PLUGIN_MCP_TOOLS)} tools, "
        f"{len(EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS)} server-only tools classified, "
        f"hooks, marketplace, and {len(expected_skills)} skills",
    )


def load_json(path: Path, errors: list[str], label: str) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing {label}")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return data


def extract_frontmatter(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    closing = text.find("\n---", 4)
    if closing == -1:
        return None
    return text[4:closing]


def github_owner_repo_from_remote(remote_url: str) -> str | None:
    normalized = remote_url.strip()
    if not normalized:
        return None
    if normalized.startswith("git@github.com:"):
        path = normalized.split(":", 1)[1]
    else:
        parsed = urlparse(normalized)
        if parsed.hostname != "github.com":
            return None
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return "/".join(parts)


def owner_repo_from_project_metadata(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    urls = data.get("project", {}).get("urls", {})
    if not isinstance(urls, dict):
        return None
    repository = urls.get("Repository") or urls.get("Homepage")
    if not isinstance(repository, str):
        return None
    return github_owner_repo_from_remote(repository)


def owner_repo_from_git_remote(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return github_owner_repo_from_remote(completed.stdout.strip())


def expected_pr_owner_repo(root: Path) -> str | None:
    return owner_repo_from_project_metadata(root) or owner_repo_from_git_remote(root)


def github_pr_url_parts(pr_url: str) -> tuple[str, int] | None:
    if any(character.isspace() for character in pr_url):
        return None
    parsed = urlparse(pr_url)
    parts = parsed.path.split("/")
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        return None
    if parsed.query or parsed.fragment:
        return None
    if len(parts) != 5 or parts[0] != "" or parts[3] != "pull" or not parts[4].isdigit():
        return None
    pr_number = int(parts[4])
    if pr_number <= 0:
        return None
    return f"{parts[1]}/{parts[2]}", pr_number


def check_pr_gate(root: Path, pr_url: str | None = None) -> ReleaseCheck:
    pr_url = (pr_url or os.environ.get("AI_DEMEMORY_PR_URL", "")).strip()
    if not pr_url:
        return warn("pr_gate", "AI_DEMEMORY_PR_URL is not set; MCP runtime smoke remains gated")
    parts = github_pr_url_parts(pr_url)
    if parts is None:
        return fail("pr_gate", "AI_DEMEMORY_PR_URL must be a canonical GitHub HTTPS pull request URL")
    actual_owner_repo, pr_number = parts
    expected_owner_repo = expected_pr_owner_repo(root)
    if expected_owner_repo and actual_owner_repo.lower() != expected_owner_repo.lower():
        return fail(
            "pr_gate",
            f"AI_DEMEMORY_PR_URL must target {expected_owner_repo}; got {actual_owner_repo}/pull/{pr_number}",
        )
    return ok("pr_gate", pr_url)


def run_release_checks(root: Path, pr_url: str | None = None) -> list[ReleaseCheck]:
    return [
        check_doctor(root),
        check_versions(root),
        check_required_docs(root),
        check_license(root),
        check_vault_template(root),
        check_recall_fixtures(root),
        check_hook_instruction_blocks(root),
        check_contract(root),
        check_mcp_inventory_docs(root),
        check_ci_workflow(root),
        check_staged_artifacts(root),
        check_vault_setup(root),
        check_pr_template(root),
        check_pr_draft(root),
        check_acceptance_checklist(root),
        check_adr_docs(root),
        check_release_checklist(root),
        check_roadmap_status(root),
        check_publish_workflow(root),
        check_codex_plugin(root),
        check_pr_gate(root, pr_url=pr_url),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    checks = run_release_checks(root)
    has_failures = any(check.status == "fail" for check in checks)
    has_warnings = any(check.status == "warn" for check in checks)
    exit_code = 1 if has_failures or (args.strict and has_warnings) else 0

    if args.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        for check in checks:
            print(f"{check.status.upper():<4} {check.name}: {check.detail}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
