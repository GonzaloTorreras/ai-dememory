#!/usr/bin/env python3
"""Validate that CI keeps required v2 verification gates."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


WORKFLOW_PATH = Path(".github/workflows/ci.yml")
LEGACY_AUTO_APPROVE_WORKFLOW_PATH = Path(".github/workflows/auto-approve.yml")
SOLO_REVIEW_DOC_PATH = Path("docs/solo-maintainer-review.md")
PAGES_VALIDATE_WORKFLOW_PATH = Path(".github/workflows/pages-validate.yml")
PAGES_DEPLOY_WORKFLOW_PATH = Path(".github/workflows/pages.yml")
WORKFLOW_DIR = Path(".github/workflows")
PINNED_ACTION_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_ACTION = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
UPLOAD_PAGES_ACTION = "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9"
DEPLOY_PAGES_ACTION = "actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128"

REQUIRED_COMMANDS = {
    "compile": "python -m compileall -q scripts mcp/server ai_dememory_tool",
    "validate": "python scripts/ai_dememory.py validate",
    "secret_scan": "python scripts/ai_dememory.py secret-scan",
    "verify_mcp": "python scripts/ai_dememory.py verify-mcp",
    "artifact_guard": "python scripts/ai_dememory.py artifact-guard",
    "vault_setup_guard": "python scripts/ai_dememory.py vault-setup-guard",
    "pr_template_guard": "python scripts/ai_dememory.py pr-template-guard",
    "pr_draft_guard": "python scripts/ai_dememory.py pr-draft-guard",
    "acceptance_guard": "python scripts/ai_dememory.py acceptance-guard",
    "adr_guard": "python scripts/ai_dememory.py adr-guard",
    "release_checklist_guard": "python scripts/ai_dememory.py release-checklist-guard",
    "release_check": "python scripts/ai_dememory.py release-check",
    "roadmap_status": "python scripts/ai_dememory.py roadmap status --json",
    "strict_pr_release_check": "python scripts/ai_dememory.py release-check --strict",
    "mcp_smoke": "python scripts/ai_dememory.py mcp-smoke",
    "api_smoke": "python scripts/ai_dememory.py api-smoke",
    "unit_tests": "python -m unittest discover -s tests -t .",
    "index": "python scripts/ai_dememory.py index",
    "search": "python scripts/ai_dememory.py search codex --limit 1",
    "eval_recall": "python scripts/ai_dememory.py eval-recall",
    "install_smoke": "python scripts/ai_dememory.py install-smoke",
    "package_build_smoke": "python scripts/ai_dememory.py package-build-smoke",
    "docker_smoke": "python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci",
    "post_smoke_package_build_artifact_guard": "python scripts/ai_dememory.py package-build-smoke --check-clean",
}

FINAL_ARTIFACT_GUARD_NAME = "Final package build artifact guard"
STRICT_PR_RELEASE_CHECK_NAME = "Strict PR release readiness check"
MCP_RUNTIME_SMOKE_NAME = "MCP runtime smoke"


@dataclass(frozen=True)
class CiGuardIssue:
    target: str
    message: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_step_block(text: str, step_name: str) -> str | None:
    marker = f"- name: {step_name}"
    start = text.find(marker)
    if start == -1:
        return None
    next_step = text.find("\n      - ", start + len(marker))
    if next_step == -1:
        return text[start:]
    return text[start:next_step]


def validate_pages_validation_workflow_text(text: str) -> list[CiGuardIssue]:
    """Keep pull-request validation separate from every Pages write capability."""

    issues: list[CiGuardIssue] = []
    required_fragments = {
        "pull_request": "pull_request:",
        "permissions": "permissions:\n  contents: read",
        "checkout": CHECKOUT_ACTION,
        "setup_python": SETUP_PYTHON_ACTION,
        "checkout_credentials": "persist-credentials: false",
        "python": 'python-version: "3.12"',
        "workflow_guard": "python scripts/ci_guard.py",
        "docs_guard": "python scripts/docs_site_guard.py",
        "artifact_guard": "python scripts/pages_artifact_guard.py",
        "focused_tests": "python -m unittest tests.test_docs_site tests.test_pages_delivery",
        "deploy_workflow_path": '".github/workflows/pages.yml"',
        "validation_workflow_path": '".github/workflows/pages-validate.yml"',
        "gitattributes_path": '".gitattributes"',
        "site_path": '"site/**"',
        "docs_path": '"docs/**"',
        "readme_path": '"README.md"',
        "security_path": '"SECURITY.md"',
        "metadata_path": '"pyproject.toml"',
        "artifact_guard_path": '"scripts/pages_artifact_guard.py"',
        "docs_guard_path": '"scripts/docs_site_guard.py"',
        "resource_policy_path": '"scripts/resource_policy.py"',
        "workflow_guard_path": '"scripts/ci_guard.py"',
        "docs_tests_path": '"tests/test_docs_site.py"',
        "tests_path": '"tests/test_pages_delivery.py"',
    }
    for name, fragment in required_fragments.items():
        if fragment not in text:
            issues.append(
                CiGuardIssue(
                    f"pages-validate.yml:{name}",
                    f"Pages validation workflow is missing required guard: {fragment}",
                )
            )

    forbidden_triggers = re.findall(
        r"(?m)^  (push|pull_request_target|workflow_dispatch|workflow_run|schedule):\s*$",
        text,
    )
    for trigger in forbidden_triggers:
        issues.append(
            CiGuardIssue(
                f"pages-validate.yml:{trigger}",
                f"Pages validation workflow must not use privileged or non-PR trigger: {trigger}",
            )
        )
    forbidden_fragments = {
        "pages_write": "pages: write",
        "oidc": "id-token: write",
        "environment": "environment:",
        "upload": "actions/upload-pages-artifact@",
        "deploy": "actions/deploy-pages@",
        "configure": "actions/configure-pages@",
        "secrets": "secrets.",
        "contents_write": "contents: write",
    }
    for name, fragment in forbidden_fragments.items():
        if fragment in text:
            issues.append(
                CiGuardIssue(
                    f"pages-validate.yml:{name}",
                    f"Pages validation workflow must not contain privileged capability: {fragment}",
                )
            )
    return issues


def validate_pages_deploy_workflow_text(text: str) -> list[CiGuardIssue]:
    """Require a manual, exact-main, least-privilege Pages deployment workflow."""

    issues: list[CiGuardIssue] = []
    required_fragments = {
        "manual_trigger": "workflow_dispatch:",
        "approved_sha_input": "approved_sha:",
        "confirm_input": "confirm:",
        "default_permissions": "permissions: {}",
        "concurrency": "group: ai-dememory-pages",
        "no_cancel": "cancel-in-progress: false",
        "prepare_contents": "contents: read",
        "main_ref": 'test "$GITHUB_REF" = "refs/heads/main"',
        "event_sha": 'test "$GITHUB_SHA" = "$APPROVED_SHA"',
        "confirmation": 'test "$DEPLOY_CONFIRM" = "deploy-pages@$APPROVED_SHA"',
        "live_main_query": 'gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha',
        "live_main_match": 'test "$live_main_sha" = "$APPROVED_SHA"',
        "checkout": CHECKOUT_ACTION,
        "approved_checkout": "ref: ${{ inputs.approved_sha }}",
        "checkout_credentials": "persist-credentials: false",
        "setup_python": SETUP_PYTHON_ACTION,
        "workflow_guard": "python scripts/ci_guard.py",
        "docs_guard": "python scripts/docs_site_guard.py",
        "focused_tests": "python -m unittest tests.test_docs_site tests.test_pages_delivery",
        "artifact_guard": "python scripts/pages_artifact_guard.py",
        "guard_upload_adjacency": (
            "      - name: Guard exact Pages artifact\n"
            "        run: python scripts/pages_artifact_guard.py\n\n"
            "      - name: Upload exact GitHub Pages artifact\n"
            f"        uses: {UPLOAD_PAGES_ACTION}"
        ),
        "upload": UPLOAD_PAGES_ACTION,
        "artifact_name": "name: github-pages",
        "artifact_path": "path: site",
        "retention": "retention-days: 1",
        "hidden_nojekyll": "include-hidden-files: true",
        "dependency": "needs: prepare",
        "deploy_revalidation": (
            "      - name: Revalidate current main after environment gate\n"
            "        env:\n"
            "          APPROVED_SHA: ${{ inputs.approved_sha }}\n"
            "          GH_TOKEN: ${{ github.token }}\n"
            "        shell: bash\n"
            "        run: |\n"
            "          set -euo pipefail\n"
            "          test \"$GITHUB_REF\" = \"refs/heads/main\"\n"
            "          test \"$GITHUB_SHA\" = \"$APPROVED_SHA\"\n"
            "          live_main_sha=\"$(gh api \"repos/$GITHUB_REPOSITORY/commits/main\" --jq .sha)\"\n"
            "          test \"$live_main_sha\" = \"$APPROVED_SHA\""
        ),
        "pages_permission": "pages: write",
        "oidc_permission": "id-token: write",
        "environment": "name: github-pages",
        "environment_url": "url: ${{ steps.deployment.outputs.page_url }}",
        "deployment_id": "id: deployment",
        "deploy": DEPLOY_PAGES_ACTION,
        "deployed_artifact": "artifact_name: github-pages",
    }
    for name, fragment in required_fragments.items():
        if fragment not in text:
            issues.append(
                CiGuardIssue(
                    f"pages.yml:{name}",
                    f"Pages deployment workflow is missing required guard: {fragment}",
                )
            )

    forbidden_triggers = re.findall(
        r"(?m)^  (push|pull_request|pull_request_target|workflow_run|schedule):\s*$",
        text,
    )
    for trigger in forbidden_triggers:
        issues.append(
            CiGuardIssue(
                f"pages.yml:{trigger}",
                f"Pages deployment workflow must remain manual-only; forbidden trigger: {trigger}",
            )
        )
    forbidden_fragments = {
        "secrets": "secrets.",
        "contents_write": "contents: write",
        "actions_write": "actions: write",
        "packages": "packages:",
        "configure": "actions/configure-pages@",
        "artifact_download": "actions/download-artifact@",
        "cache": "actions/cache@",
    }
    for name, fragment in forbidden_fragments.items():
        if fragment in text:
            issues.append(
                CiGuardIssue(
                    f"pages.yml:{name}",
                    f"Pages deployment workflow must not contain: {fragment}",
                )
            )

    for permission, expected in (("contents: read", 2), ("pages: write", 1), ("id-token: write", 1)):
        if text.count(permission) != expected:
            issues.append(
                CiGuardIssue(
                    "pages.yml:permissions",
                    f"Pages deployment workflow must contain {permission!r} exactly {expected} time(s)",
                )
            )

    prepare_end = text.find("\n  deploy:\n")
    artifact_guard_index = text.find("python scripts/pages_artifact_guard.py")
    upload_index = text.find(UPLOAD_PAGES_ACTION)
    if prepare_end == -1:
        issues.append(CiGuardIssue("pages.yml:deploy_job", "Pages deployment job is missing"))
    else:
        if not (0 <= artifact_guard_index < upload_index < prepare_end):
            issues.append(
                CiGuardIssue(
                    "pages.yml:artifact_order",
                    "exact artifact guard must run immediately before the Pages upload boundary",
                )
            )
        deploy_block = text[prepare_end:]
        deploy_actions = re.findall(r"\buses:\s*([^\s#]+)", deploy_block)
        if deploy_actions != [DEPLOY_PAGES_ACTION]:
            issues.append(
                CiGuardIssue(
                    "pages.yml:deploy_actions",
                    "deploy job may invoke only the pinned deploy-pages action",
                )
            )
        if (
            deploy_block.count("run:") != 1
            or deploy_block.count("shell: bash") != 1
            or CHECKOUT_ACTION in deploy_block
            or SETUP_PYTHON_ACTION in deploy_block
            or UPLOAD_PAGES_ACTION in deploy_block
        ):
            issues.append(
                CiGuardIssue(
                    "pages.yml:deploy_steps",
                    "deploy job may run only the exact current-main revalidation before deploy-pages",
                )
            )
    return issues


def step_has_pr_gate_and_url(step: str) -> bool:
    has_pr_gate = "github.event_name == 'pull_request'" in step or 'github.event_name == "pull_request"' in step
    return has_pr_gate and "AI_DEMEMORY_PR_URL" in step and "github.event.pull_request.html_url" in step


def validate_ci_workflow(root: Path) -> list[CiGuardIssue]:
    path = root / WORKFLOW_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [CiGuardIssue(str(WORKFLOW_PATH), "CI workflow is missing")]
    issues = validate_ci_workflow_text(text)
    issues.extend(validate_solo_maintainer_review_boundary(root))
    for workflow_path, validator in (
        (PAGES_VALIDATE_WORKFLOW_PATH, validate_pages_validation_workflow_text),
        (PAGES_DEPLOY_WORKFLOW_PATH, validate_pages_deploy_workflow_text),
    ):
        path = root / workflow_path
        try:
            workflow_text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            issues.append(CiGuardIssue(str(workflow_path), "required Pages workflow is missing"))
        else:
            issues.extend(validator(workflow_text))
    issues.extend(validate_workflow_supply_chain(root))
    return issues


def validate_workflow_supply_chain(root: Path) -> list[CiGuardIssue]:
    """Require immutable third-party actions and non-persisted checkout tokens."""

    issues: list[CiGuardIssue] = []
    workflow_root = root / WORKFLOW_DIR
    for path in sorted(workflow_root.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        display = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = re.search(r"\buses:\s*([^\s#]+)", line)
            if not match:
                continue
            action = match.group(1)
            if action.startswith("./"):
                continue
            if not PINNED_ACTION_RE.fullmatch(action):
                issues.append(
                    CiGuardIssue(
                        f"{display}:{line_number}",
                        f"third-party action must be pinned to a full commit SHA: {action}",
                    )
                )
        for match in re.finditer(
            r"(?ms)^\s*-\s+name:[^\n]*\n(?:(?!^\s*-\s+name:).)*?"
            r"^\s*uses:\s*actions/checkout@[0-9a-f]{40}[^\n]*\n"
            r"(?P<body>(?:(?!^\s*-\s+name:).)*)",
            text,
        ):
            if not re.search(r"(?m)^\s*persist-credentials:\s*false\s*$", match.group("body")):
                line_number = text[: match.start()].count("\n") + 1
                issues.append(
                    CiGuardIssue(
                        f"{display}:{line_number}",
                        "actions/checkout must set persist-credentials: false",
                    )
                )
    return issues


def validate_solo_maintainer_review_boundary(root: Path) -> list[CiGuardIssue]:
    """Keep solo-maintainer review auditable without forgeable bot approval."""

    issues: list[CiGuardIssue] = []
    legacy_path = root / LEGACY_AUTO_APPROVE_WORKFLOW_PATH
    if legacy_path.exists():
        issues.append(
            CiGuardIssue(
                LEGACY_AUTO_APPROVE_WORKFLOW_PATH.as_posix(),
                "legacy bot auto-approval workflow must be removed for solo-maintainer review",
            )
        )

    def permission_write_pattern(permission: str) -> str:
        key = re.escape(permission)
        return (
            rf"(?im)(?:^|[{{,])\s*[\"']?{key}[\"']?\s*:\s*"
            rf"[\"']?write[\"']?(?=\s*(?:$|[,}}#]))"
        )

    forbidden_workflow_patterns = {
        "pull_requests_write": permission_write_pattern("pull-requests"),
        "statuses_write": permission_write_pattern("statuses"),
        "checks_write": permission_write_pattern("checks"),
        "write_all": r"(?im)^\s*[\"']?permissions[\"']?\s*:\s*[\"']?write-all[\"']?\s*(?:#.*)?$",
        "automated_approval": r"(?:event=['\"]APPROVE|/pulls/[^\s\"']+/reviews)",
        "legacy_receipt": r"codex-double-check",
    }
    workflow_root = root / WORKFLOW_DIR
    for path in sorted(workflow_root.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        display = path.relative_to(root).as_posix()
        for name, pattern in forbidden_workflow_patterns.items():
            if re.search(pattern, text):
                issues.append(
                    CiGuardIssue(
                        f"{display}:{name}",
                        "solo-maintainer review forbids automated approvals and forgeable review/status checks",
                    )
                )
        if path.relative_to(root) != WORKFLOW_PATH:
            duplicate_verify_patterns = {
                "required_check_job": r"(?im)^[ \t]+verify\s*:\s*(?:#.*)?$",
                "required_check_name": r"(?im)^[ \t]+name\s*:\s*[\"']?verify[\"']?\s*(?:#.*)?$",
            }
            for name, pattern in duplicate_verify_patterns.items():
                if re.search(pattern, text):
                    issues.append(
                        CiGuardIssue(
                            f"{display}:{name}",
                            "only ci.yml may emit the required verify check name",
                        )
                    )

    policy_requirements = {
        Path("AGENTS.md"): {
            "receipt": "<!-- codex-solo-review pr=<number> head=<head-sha> base=<base-sha> -->",
            "expected_head": "expected_head_sha",
            "no_aliases": "Do not create aliases, secondary accounts, bot approvals",
        },
        SOLO_REVIEW_DOC_PATH: {
            "zero_approvals": "required_approving_review_count=0",
            "no_last_push": "require_last_push_approval=false",
            "no_bot_approval": "can_approve_pull_request_reviews=false",
            "boundary_scope": "Scope: security-boundary",
            "checks_write": "checks: write",
            "write_all": "permissions: write-all",
        },
    }
    for path, fragments in policy_requirements.items():
        try:
            text = (root / path).read_text(encoding="utf-8")
        except FileNotFoundError:
            issues.append(
                CiGuardIssue(
                    path.as_posix(),
                    "solo-maintainer review policy file is missing",
                )
            )
            continue
        for name, fragment in fragments.items():
            if fragment not in text:
                issues.append(
                    CiGuardIssue(
                        f"{path.as_posix()}:{name}",
                        f"solo-maintainer review policy is missing required contract: {fragment}",
                    )
                )
    return issues


def validate_ci_workflow_text(text: str) -> list[CiGuardIssue]:
    issues: list[CiGuardIssue] = []
    compact = normalize(text)
    if not re.search(r"(?m)^on:\s*$", text):
        issues.append(CiGuardIssue("ci.yml:on", "workflow must declare triggers"))
    if "pull_request:" not in text:
        issues.append(CiGuardIssue("ci.yml:on", "workflow must run on pull_request"))
    if "push:" not in text or "main" not in text:
        issues.append(CiGuardIssue("ci.yml:on", "workflow must run on pushes to main"))
    if "python-version: \"3.12\"" not in text and "python-version: '3.12'" not in text:
        issues.append(CiGuardIssue("ci.yml:python", "workflow must use Python 3.12"))
    for name, command in REQUIRED_COMMANDS.items():
        if normalize(command) not in compact:
            issues.append(CiGuardIssue(f"ci.yml:{name}", f"missing required command: {command}"))
    docker_index = compact.find(normalize(REQUIRED_COMMANDS["docker_smoke"]))
    final_name_index = compact.find(normalize(FINAL_ARTIFACT_GUARD_NAME))
    final_command_index = compact.find(normalize(REQUIRED_COMMANDS["post_smoke_package_build_artifact_guard"]))
    if final_name_index == -1:
        issues.append(
            CiGuardIssue(
                "ci.yml:final_artifact_guard",
                f"missing required post-smoke step name: {FINAL_ARTIFACT_GUARD_NAME}",
            )
        )
    elif docker_index == -1 or final_name_index < docker_index or final_command_index < docker_index:
        issues.append(
            CiGuardIssue(
                "ci.yml:final_artifact_guard",
                "final package build artifact guard must run after Docker local MCP smoke",
            )
        )
    mcp_name_index = compact.find(normalize(MCP_RUNTIME_SMOKE_NAME))
    mcp_command_index = compact.find(normalize(REQUIRED_COMMANDS["mcp_smoke"]))
    release_check_index = compact.find(normalize(REQUIRED_COMMANDS["release_check"]))
    strict_release_check_index = compact.find(normalize(REQUIRED_COMMANDS["strict_pr_release_check"]))
    api_smoke_index = compact.find(normalize(REQUIRED_COMMANDS["api_smoke"]))
    index_index = compact.find(normalize(REQUIRED_COMMANDS["index"]))
    search_index = compact.find(normalize(REQUIRED_COMMANDS["search"]))
    eval_recall_index = compact.find(normalize(REQUIRED_COMMANDS["eval_recall"]))
    install_smoke_index = compact.find(normalize(REQUIRED_COMMANDS["install_smoke"]))
    strict_release_name_index = compact.find(normalize(STRICT_PR_RELEASE_CHECK_NAME))
    strict_release_step = find_step_block(text, STRICT_PR_RELEASE_CHECK_NAME)
    mcp_step = find_step_block(text, MCP_RUNTIME_SMOKE_NAME)
    if strict_release_name_index == -1:
        issues.append(
            CiGuardIssue(
                "ci.yml:strict_pr_release_check",
                f"missing required PR-gated step name: {STRICT_PR_RELEASE_CHECK_NAME}",
            )
        )
    elif strict_release_step is None or not step_has_pr_gate_and_url(strict_release_step):
        issues.append(
            CiGuardIssue(
                "ci.yml:strict_pr_release_check",
                "Strict PR release readiness check must run only on pull_request events and set AI_DEMEMORY_PR_URL from the pull request URL",
            )
        )
    if mcp_name_index == -1:
        issues.append(CiGuardIssue("ci.yml:mcp_smoke", f"missing required PR-gated step name: {MCP_RUNTIME_SMOKE_NAME}"))
    elif mcp_step is None or not step_has_pr_gate_and_url(mcp_step):
        issues.append(
            CiGuardIssue(
                "ci.yml:mcp_smoke",
                "MCP runtime smoke must run only on pull_request events and set AI_DEMEMORY_PR_URL from the pull request URL",
            )
        )
    if (
        mcp_name_index != -1
        and mcp_command_index != -1
        and release_check_index != -1
        and strict_release_check_index != -1
        and api_smoke_index != -1
        and index_index != -1
        and search_index != -1
        and eval_recall_index != -1
        and install_smoke_index != -1
        and not (
            release_check_index
            < api_smoke_index
            < index_index
            < search_index
            < eval_recall_index
            < strict_release_check_index
            < mcp_name_index
            <= mcp_command_index
            < install_smoke_index
        )
    ):
        issues.append(
            CiGuardIssue(
                "ci.yml:mcp_smoke",
                "strict PR release-check and MCP runtime smoke must run after index/search/recall smoke and before install smoke",
            )
        )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_ci_workflow(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"CI workflow guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("CI workflow guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
