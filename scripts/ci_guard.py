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
    entries = _step_direct_mapping_entries(step)
    if_values = [normalize(value) for key, value in entries if key.lower() == "if"]
    expected_conditions = {
        "${{ github.event_name == 'pull_request' }}",
        '${{ github.event_name == "pull_request" }}',
    }
    has_exact_gate = len(if_values) == 1 and if_values[0] in expected_conditions
    has_env_mapping = sum(1 for key, value in entries if key.lower() == "env" and not value) == 1
    has_exact_url = bool(
        re.search(
            r"(?m)^\s*AI_DEMEMORY_PR_URL:\s*"
            r"\$\{\{\s*github\.event\.pull_request\.html_url\s*}}\s*$",
            step,
        )
    )
    return has_exact_gate and has_env_mapping and has_exact_url


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


def _strip_yaml_comment(line: str) -> str:
    """Remove an unquoted YAML comment while preserving quoted scalars."""

    single_quoted = False
    double_quoted = False
    escaped = False
    previous_significant: str | None = None
    for index, character in enumerate(line):
        if double_quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                double_quoted = False
            continue
        if single_quoted:
            if character == "'":
                if index + 1 < len(line) and line[index + 1] == "'":
                    continue
                single_quoted = False
            continue
        quote_can_start = previous_significant is None or previous_significant in ":-[{,"
        if character == '"' and quote_can_start:
            double_quoted = True
        elif character == "'" and quote_can_start:
            single_quoted = True
        elif character == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
        elif not character.isspace():
            previous_significant = character
    return line


def _workflow_yaml_structure(text: str) -> str:
    """Return YAML structure without comments or block-scalar payloads."""

    structure: list[str] = []
    block_parent_indent: int | None = None
    for raw_line in text.splitlines():
        line = _strip_yaml_comment(raw_line).rstrip()
        if block_parent_indent is not None:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent > block_parent_indent:
                continue
            block_parent_indent = None
        structure.append(line)
        if re.search(r":\s*[>|][+\-0-9]*\s*$", line):
            block_parent_indent = len(line) - len(line.lstrip(" "))
    return "\n".join(structure)


def _mask_yaml_quoted_scalars(text: str) -> str:
    """Mask quoted content so anchor checks inspect YAML tokens only."""

    masked: list[str] = []
    single_quoted = False
    double_quoted = False
    escaped = False
    previous_significant: str | None = None
    for character in text:
        if double_quoted:
            masked.append("\n" if character == "\n" else " ")
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                double_quoted = False
            continue
        if single_quoted:
            masked.append("\n" if character == "\n" else " ")
            if character == "'":
                single_quoted = False
            continue
        if character == "\n":
            previous_significant = None
            masked.append(character)
            continue
        quote_can_start = previous_significant is None or previous_significant in ":-[{,"
        if character == '"' and quote_can_start:
            double_quoted = True
            masked.append(" ")
        elif character == "'" and quote_can_start:
            single_quoted = True
            masked.append(" ")
        else:
            masked.append(character)
            if not character.isspace():
                previous_significant = character
    return "".join(masked)


def _simple_yaml_mapping(line: str) -> tuple[str, str] | None:
    """Return a plain mapping key/value pair used by the strict workflow subset."""

    stripped = line.lstrip(" ")
    if not stripped or stripped.startswith("-"):
        return None
    match = re.match(r"(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*(?P<value>.*)$", stripped)
    if not match:
        return None
    return match.group("key"), match.group("value")


def _block_style_workflow_jobs(structure_text: str) -> tuple[list[tuple[str, str]], str | None]:
    """Return static block-style job IDs and their structural YAML blocks."""

    lines = structure_text.splitlines()
    jobs_entries = [
        (index, line, entry)
        for index, line in enumerate(lines)
        if line.strip()
        and len(line) == len(line.lstrip(" "))
        and (entry := _simple_yaml_mapping(line)) is not None
        and entry[0].lower() == "jobs"
    ]
    if len(jobs_entries) != 1:
        return [], "workflow must contain exactly one top-level block-style jobs mapping"

    jobs_index, jobs_line, jobs_entry = jobs_entries[0]
    if jobs_entry[1]:
        return [], "workflow jobs must use a block-style mapping"
    jobs_indent = len(jobs_line) - len(jobs_line.lstrip(" "))
    end_index = len(lines)
    for candidate_index in range(jobs_index + 1, len(lines)):
        candidate = lines[candidate_index]
        if not candidate.strip():
            continue
        candidate_indent = len(candidate) - len(candidate.lstrip(" "))
        if candidate_indent <= jobs_indent:
            end_index = candidate_index
            break

    job_candidates = [
        (candidate_index, lines[candidate_index])
        for candidate_index in range(jobs_index + 1, end_index)
        if lines[candidate_index].strip()
        and _simple_yaml_mapping(lines[candidate_index]) is not None
    ]
    if not job_candidates:
        return [], "workflow jobs mapping must contain at least one static job"
    job_indent = min(
        len(candidate) - len(candidate.lstrip(" "))
        for _, candidate in job_candidates
    )
    job_starts = [
        (candidate_index, candidate)
        for candidate_index, candidate in job_candidates
        if len(candidate) - len(candidate.lstrip(" ")) == job_indent
    ]

    jobs: list[tuple[str, str]] = []
    for position, (job_index, job_line) in enumerate(job_starts):
        job_entry = _simple_yaml_mapping(job_line)
        if job_entry is None or job_entry[1]:
            return [], "workflow job definitions must use static block-style mappings"
        job_end = job_starts[position + 1][0] if position + 1 < len(job_starts) else end_index
        jobs.append((job_entry[0], "\n".join(lines[job_index:job_end])))
    return jobs, None


def _top_level_mapping_block(structure_text: str, key_name: str) -> tuple[str | None, str | None]:
    """Return one top-level block-style mapping and its descendants."""

    lines = structure_text.splitlines()
    matches = [
        (index, line, entry)
        for index, line in enumerate(lines)
        if line.strip()
        and len(line) == len(line.lstrip(" "))
        and (entry := _simple_yaml_mapping(line)) is not None
        and entry[0].lower() == key_name.lower()
    ]
    if len(matches) != 1:
        return None, f"workflow must contain exactly one top-level {key_name} mapping"
    start_index, start_line, entry = matches[0]
    if entry[1]:
        return None, f"workflow {key_name} must use a block-style mapping"
    base_indent = len(start_line) - len(start_line.lstrip(" "))
    end_index = len(lines)
    for candidate_index in range(start_index + 1, len(lines)):
        candidate = lines[candidate_index]
        if not candidate.strip():
            continue
        if len(candidate) - len(candidate.lstrip(" ")) <= base_indent:
            end_index = candidate_index
            break
    return "\n".join(lines[start_index:end_index]), None


def _direct_mapping_entries(block: str) -> list[tuple[str, str]]:
    """Return the direct child mappings of the first mapping in a YAML block."""

    lines = block.splitlines()[1:]
    candidates = [
        line
        for line in lines
        if line.strip() and _simple_yaml_mapping(line) is not None
    ]
    if not candidates:
        return []
    direct_indent = min(len(line) - len(line.lstrip(" ")) for line in candidates)
    return [
        entry
        for line in candidates
        if len(line) - len(line.lstrip(" ")) == direct_indent
        and (entry := _simple_yaml_mapping(line)) is not None
    ]


def _job_step_blocks(job_block: str) -> tuple[list[str], str | None]:
    """Return static step blocks from one block-style job."""

    lines = job_block.splitlines()
    property_candidates = [
        (index, line, entry)
        for index, line in enumerate(lines[1:], start=1)
        if line.strip() and (entry := _simple_yaml_mapping(line)) is not None
    ]
    if not property_candidates:
        return [], "verify job must contain a block-style steps mapping"
    property_indent = min(
        len(line) - len(line.lstrip(" "))
        for _, line, _ in property_candidates
    )
    steps_entries = [
        (index, line, entry)
        for index, line, entry in property_candidates
        if len(line) - len(line.lstrip(" ")) == property_indent
        and entry[0].lower() == "steps"
    ]
    if len(steps_entries) != 1 or steps_entries[0][2][1]:
        return [], "verify job must contain exactly one block-style steps mapping"

    steps_index, steps_line, _ = steps_entries[0]
    steps_indent = len(steps_line) - len(steps_line.lstrip(" "))
    end_index = len(lines)
    for candidate_index in range(steps_index + 1, len(lines)):
        candidate = lines[candidate_index]
        if not candidate.strip():
            continue
        candidate_indent = len(candidate) - len(candidate.lstrip(" "))
        if candidate_indent <= steps_indent:
            end_index = candidate_index
            break
    step_candidates = [
        (index, lines[index])
        for index in range(steps_index + 1, end_index)
        if lines[index].lstrip(" ").startswith("- ")
    ]
    if not step_candidates:
        return [], "verify job steps mapping must contain static block-style steps"
    step_indent = min(len(line) - len(line.lstrip(" ")) for _, line in step_candidates)
    step_starts = [
        (index, line)
        for index, line in step_candidates
        if len(line) - len(line.lstrip(" ")) == step_indent
    ]
    return [
        "\n".join(
            lines[
                step_index : (
                    step_starts[position + 1][0]
                    if position + 1 < len(step_starts)
                    else end_index
                )
            ]
        )
        for position, (step_index, _) in enumerate(step_starts)
    ], None


def _step_direct_mapping_entries(step_block: str) -> list[tuple[str, str]]:
    """Return direct mappings for a dash-prefixed block-style workflow step."""

    lines = step_block.splitlines()
    entries: list[tuple[int, tuple[str, str]]] = []
    first = lines[0].lstrip(" ")[2:]
    first_entry = _simple_yaml_mapping(first)
    if first_entry is not None:
        entries.append((0, first_entry))
    nested_candidates = [
        line
        for line in lines[1:]
        if line.strip() and _simple_yaml_mapping(line) is not None
    ]
    if nested_candidates:
        direct_indent = min(len(line) - len(line.lstrip(" ")) for line in nested_candidates)
        entries.extend(
            (index, entry)
            for index, line in enumerate(nested_candidates, start=1)
            if len(line) - len(line.lstrip(" ")) == direct_indent
            and (entry := _simple_yaml_mapping(line)) is not None
        )
    return [entry for _, entry in entries]


def _step_nested_mapping_entries(step_block: str, parent_key: str) -> list[tuple[str, str]] | None:
    """Return direct children of one direct step mapping, or None when absent/ambiguous."""

    lines = step_block.splitlines()
    candidates = [
        (index, line, entry)
        for index, line in enumerate(lines[1:], start=1)
        if line.strip() and (entry := _simple_yaml_mapping(line)) is not None
    ]
    if not candidates:
        return None
    direct_indent = min(len(line) - len(line.lstrip(" ")) for _, line, _ in candidates)
    parents = [
        (index, line, entry)
        for index, line, entry in candidates
        if len(line) - len(line.lstrip(" ")) == direct_indent
        and entry[0].lower() == parent_key.lower()
    ]
    if len(parents) != 1 or parents[0][2][1]:
        return None
    parent_index = parents[0][0]
    end_index = len(lines)
    for candidate_index in range(parent_index + 1, len(lines)):
        candidate = lines[candidate_index]
        if not candidate.strip():
            continue
        if len(candidate) - len(candidate.lstrip(" ")) <= direct_indent:
            end_index = candidate_index
            break
    children = [
        line
        for line in lines[parent_index + 1 : end_index]
        if line.strip() and _simple_yaml_mapping(line) is not None
    ]
    if not children:
        return []
    child_indent = min(len(line) - len(line.lstrip(" ")) for line in children)
    return [
        entry
        for line in children
        if len(line) - len(line.lstrip(" ")) == child_indent
        and (entry := _simple_yaml_mapping(line)) is not None
    ]


def _workflow_structure_contract_issues(
    structure_text: str,
    display: str,
    *,
    canonical_ci: bool,
) -> list[CiGuardIssue]:
    """Reject multiline permission scalars and ambiguous non-CI job names."""

    issues: list[CiGuardIssue] = []
    lines = structure_text.splitlines()
    for line in lines:
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("- ") or _simple_yaml_mapping(line) is not None:
            continue
        issues.append(
            CiGuardIssue(
                f"{display}:scalar_continuation",
                "workflow plain-scalar continuation lines are forbidden; use one canonical same-line value",
            )
        )
    sensitive_permissions = {"permissions", "pull-requests", "statuses", "checks"}
    for index, line in enumerate(lines):
        entry = _simple_yaml_mapping(line)
        if not entry or entry[0].lower() not in sensitive_permissions or entry[1]:
            continue
        key = entry[0].lower()
        if key != "permissions":
            issues.append(
                CiGuardIssue(
                    f"{display}:multiline_permission",
                    "permission capability values must use canonical same-line scalars",
                )
            )
            continue
        base_indent = len(line) - len(line.lstrip(" "))
        next_structural = next(
            (candidate for candidate in lines[index + 1 :] if candidate.strip()),
            None,
        )
        if next_structural is None:
            issues.append(
                CiGuardIssue(
                    f"{display}:multiline_permission",
                    "permissions must be an explicit mapping, read-all, or empty mapping",
                )
            )
            continue
        next_indent = len(next_structural) - len(next_structural.lstrip(" "))
        if next_indent <= base_indent or _simple_yaml_mapping(next_structural) is None:
            issues.append(
                CiGuardIssue(
                    f"{display}:multiline_permission",
                    "permissions must be an explicit mapping, read-all, or empty mapping",
                )
            )

    jobs, jobs_error = _block_style_workflow_jobs(structure_text)
    if jobs_error:
        target = "job_structure"
        if not canonical_ci and jobs_error == "workflow jobs must use a block-style mapping":
            target = "flow_jobs"
        elif not canonical_ci and jobs_error == "workflow job definitions must use static block-style mappings":
            target = "flow_job"
        issues.append(CiGuardIssue(f"{display}:{target}", jobs_error))
        return issues

    if canonical_ci:
        verify_jobs = [job for job in jobs if job[0] == "verify"]
        if len(verify_jobs) != 1:
            issues.append(
                CiGuardIssue(
                    f"{display}:required_verify_job",
                    "canonical CI must contain exactly one static block-style verify job",
                )
            )
        for job_id, job_block in jobs:
            names = [
                value.strip("'\"")
                for key, value in _direct_mapping_entries(job_block)
                if key.lower() == "name"
            ]
            if len(names) > 1 or (job_id == "verify" and names and names != ["verify"]):
                issues.append(
                    CiGuardIssue(
                        f"{display}:required_verify_name",
                        "the verify job check name must remain the static value verify",
                    )
                )
            if job_id != "verify" and "verify" in names:
                issues.append(
                    CiGuardIssue(
                        f"{display}:duplicate_verify_name",
                        "only the canonical verify job may emit the required verify check name",
                    )
                )
            expected_compatibility_name = "compatibility (${{ matrix.os }}, Python ${{ matrix.python }})"
            if job_id != "verify" and any("${{" in name for name in names):
                if job_id != "compatibility" or names != [expected_compatibility_name]:
                    issues.append(
                        CiGuardIssue(
                            f"{display}:dynamic_job_name",
                            "canonical CI permits a dynamic check name only for the exact compatibility matrix",
                        )
                    )
        return issues

    for _, job_block in jobs:
        for key, value in _direct_mapping_entries(job_block):
            if key.lower() == "name" and (not value or "${{" in value):
                issues.append(
                    CiGuardIssue(
                        f"{display}:dynamic_job_name",
                        "non-CI job check names must be static same-line scalars",
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

    def workflow_key_value_pattern(key_name: str, value_name: str) -> str:
        key = re.escape(key_name)
        value = re.escape(value_name)
        return (
            rf"(?im)(?:^|[{{,])\s*[\"']?{key}[\"']?\s*:\s*"
            rf"[\"']?{value}[\"']?(?=\s*(?:$|[,}}#]))"
        )

    forbidden_workflow_patterns = {
        "pull_requests_write": workflow_key_value_pattern("pull-requests", "write"),
        "statuses_write": workflow_key_value_pattern("statuses", "write"),
        "checks_write": workflow_key_value_pattern("checks", "write"),
        "write_all": workflow_key_value_pattern("permissions", "write-all"),
        "automated_approval": r"(?:event=['\"]APPROVE|/pulls/[^\s\"']+/reviews)",
        "legacy_receipt": r"codex-double-check",
    }
    workflow_root = root / WORKFLOW_DIR
    for path in sorted(workflow_root.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        structure_text = _workflow_yaml_structure(text)
        unquoted_structure = _mask_yaml_quoted_scalars(structure_text)
        display = path.relative_to(root).as_posix()
        for name, pattern in forbidden_workflow_patterns.items():
            search_text = text if name in {"automated_approval", "legacy_receipt"} else structure_text
            if re.search(pattern, search_text):
                issues.append(
                    CiGuardIssue(
                        f"{display}:{name}",
                        "solo-maintainer review forbids automated approvals and forgeable review/status checks",
                    )
                )
        yaml_token_indirection_patterns = (
            r"(?m)(?:^|[\s\[{,:])(?:&|\*)[^\s\[\]{},]+",
            r"(?m)(?:^|[{,])\s*<<\s*:",
            r"(?m)(?:^|[{,])\s*[?:]\s+",
            r"(?m)(?:^|[\[{,:])\s*!(?:!|<|[A-Za-z_])[^\s\[\]{},]*",
        )
        sensitive_value_indirection_patterns = (
            r"(?im)(?:^|[{,])\s*[\"']?(?:permissions|pull-requests|statuses|checks)[\"']?\s*:\s*!",
            r"(?im)^\s*[\"']?(?:permissions|pull-requests|statuses|checks|name)[\"']?\s*:\s*[>|]",
            r"(?im)(?:^|[{,])\s*[\"']?(?:permissions|pull-requests|statuses|checks)[\"']?\s*:\s*[\"']",
            r"(?im)(?:^|[{,])\s*[\"']?name[\"']?\s*:\s*\"[^\"\n]*\\",
            r"(?m)(?:^|[{,])\s*(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*')\s*:",
        )
        has_yaml_indirection = any(
            re.search(pattern, unquoted_structure)
            for pattern in yaml_token_indirection_patterns
        ) or any(
            re.search(pattern, structure_text)
            for pattern in sensitive_value_indirection_patterns
        )
        if has_yaml_indirection:
            issues.append(
                CiGuardIssue(
                    f"{display}:yaml_indirection",
                    "workflow YAML anchors, aliases, merge keys, tags, and permission block scalars are forbidden",
                )
            )
        canonical_ci = path.relative_to(root) == WORKFLOW_PATH
        issues.extend(
            _workflow_structure_contract_issues(
                structure_text,
                display,
                canonical_ci=canonical_ci,
            )
        )
        if not canonical_ci:
            duplicate_verify_patterns = {
                "required_check_job": (
                    r"(?im)(?:^[ \t]+|[{,]\s*)(?:verify|\"verify\"|'verify')\s*:"
                ),
                "required_check_name": (
                    r"(?im)(?:^|[{,])\s*[\"']?name[\"']?\s*:\s*"
                    r"(?:verify|\"verify\"|'verify')(?=\s*(?:$|[,}#]))"
                ),
            }
            for name, pattern in duplicate_verify_patterns.items():
                if re.search(pattern, structure_text):
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
            "yaml_indirection": "YAML anchors",
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
    structure_text = _workflow_yaml_structure(text)
    issues.extend(
        _workflow_structure_contract_issues(
            structure_text,
            WORKFLOW_PATH.as_posix(),
            canonical_ci=True,
        )
    )
    jobs, jobs_error = _block_style_workflow_jobs(structure_text)
    verify_blocks = [block for job_id, block in jobs if job_id == "verify"] if not jobs_error else []
    verify_block = verify_blocks[0] if len(verify_blocks) == 1 else ""

    top_level_entries = [
        entry
        for line in structure_text.splitlines()
        if line.strip()
        and len(line) == len(line.lstrip(" "))
        and (entry := _simple_yaml_mapping(line)) is not None
    ]
    for forbidden_key in ("defaults", "env"):
        if any(key.lower() == forbidden_key for key, _ in top_level_entries):
            issues.append(
                CiGuardIssue(
                    f"ci.yml:workflow_{forbidden_key}",
                    f"canonical CI must not override workflow-level {forbidden_key}",
                )
            )

    on_block, on_error = _top_level_mapping_block(structure_text, "on")
    if on_error or on_block is None:
        issues.append(CiGuardIssue("ci.yml:on", on_error or "workflow must declare triggers"))
    else:
        trigger_entries = _direct_mapping_entries(on_block)
        trigger_names = [key.lower() for key, _ in trigger_entries]
        if trigger_names.count("pull_request") != 1:
            issues.append(CiGuardIssue("ci.yml:on", "workflow must run exactly once on pull_request"))
        if trigger_names.count("push") != 1 or not re.search(r"(?m)^\s+-\s+main\s*$", on_block):
            issues.append(CiGuardIssue("ci.yml:on", "workflow must run on pushes to main"))
        unexpected_triggers = sorted(set(trigger_names) - {"pull_request", "push"})
        if unexpected_triggers:
            issues.append(
                CiGuardIssue(
                    "ci.yml:on",
                    "canonical CI has forbidden additional triggers: " + ", ".join(unexpected_triggers),
                )
            )

    permissions_block, permissions_error = _top_level_mapping_block(structure_text, "permissions")
    permissions_entries = _direct_mapping_entries(permissions_block) if permissions_block else []
    if permissions_error or permissions_entries != [("contents", "read")]:
        issues.append(
            CiGuardIssue(
                "ci.yml:permissions",
                "canonical CI must grant only top-level contents: read",
            )
        )
    if "python-version: \"3.12\"" not in verify_block and "python-version: '3.12'" not in verify_block:
        issues.append(CiGuardIssue("ci.yml:python", "verify job must use Python 3.12"))

    if verify_block:
        forbidden_job_properties = {
            "continue-on-error",
            "container",
            "defaults",
            "env",
            "environment",
            "if",
            "needs",
            "permissions",
            "services",
            "strategy",
            "uses",
        }
        verify_entries = _direct_mapping_entries(verify_block)
        for key, _ in verify_entries:
            if key.lower() in forbidden_job_properties:
                issues.append(
                    CiGuardIssue(
                        f"ci.yml:verify_{key.lower()}",
                        f"canonical verify job must not set {key}",
                    )
                )
        runs_on = [normalize(value) for key, value in verify_entries if key.lower() == "runs-on"]
        if runs_on != ["ubuntu-latest"]:
            issues.append(
                CiGuardIssue(
                    "ci.yml:verify_runner",
                    "canonical verify job must run exactly once on ubuntu-latest",
                )
            )

    step_blocks, steps_error = _job_step_blocks(verify_block) if verify_block else ([], None)
    if verify_block and steps_error:
        issues.append(CiGuardIssue("ci.yml:verify_steps", steps_error))
    run_steps: dict[str, list[tuple[int, str]]] = {}
    for position, step_block in enumerate(step_blocks):
        entries = _step_direct_mapping_entries(step_block)
        run_values = [normalize(value) for key, value in entries if key.lower() == "run"]
        if len(run_values) > 1:
            issues.append(
                CiGuardIssue(
                    "ci.yml:verify_step_run",
                    "each verify step may contain only one static same-line run command",
                )
            )
        for run_value in run_values:
            run_steps.setdefault(run_value, []).append((position, step_block))
        for key, _ in entries:
            if key.lower() in {"continue-on-error", "shell", "working-directory"}:
                issues.append(
                    CiGuardIssue(
                        f"ci.yml:verify_step_{key.lower()}",
                        f"verify steps must not override {key}",
                    )
                )

    required_steps: dict[str, tuple[int, str]] = {}
    for name, command in REQUIRED_COMMANDS.items():
        matches = run_steps.get(normalize(command), [])
        if len(matches) != 1:
            message = (
                f"missing required command: {command}"
                if not matches
                else f"required command must appear exactly once: {command}"
            )
            issues.append(CiGuardIssue(f"ci.yml:{name}", message))
        else:
            required_steps[name] = matches[0]

    for name, (_, step_block) in required_steps.items():
        entries = _step_direct_mapping_entries(step_block)
        if_values = [value for key, value in entries if key.lower() == "if"]
        if name not in {"strict_pr_release_check", "mcp_smoke"} and if_values:
            issues.append(
                CiGuardIssue(
                    f"ci.yml:{name}_condition",
                    "required verify commands must not be conditionally skipped",
                )
            )
        env_entries = _step_nested_mapping_entries(step_block, "env")
        if name in {"strict_pr_release_check", "mcp_smoke"}:
            expected_env = [("AI_DEMEMORY_PR_URL", "${{ github.event.pull_request.html_url }}")]
            if env_entries != expected_env:
                issues.append(
                    CiGuardIssue(
                        f"ci.yml:{name}_env",
                        "PR-gated verify steps may set only the exact pull request URL environment binding",
                    )
                )
        elif any(key.lower() == "env" for key, _ in entries):
            issues.append(
                CiGuardIssue(
                    f"ci.yml:{name}_env",
                    "required verify commands must not override their execution environment",
                )
            )

    docker_step = required_steps.get("docker_smoke")
    final_step = required_steps.get("post_smoke_package_build_artifact_guard")
    final_names = (
        [
            value.strip("'\"")
            for key, value in _step_direct_mapping_entries(final_step[1])
            if key.lower() == "name"
        ]
        if final_step
        else []
    )
    if final_names != [FINAL_ARTIFACT_GUARD_NAME]:
        issues.append(
            CiGuardIssue(
                "ci.yml:final_artifact_guard",
                f"missing required post-smoke step name: {FINAL_ARTIFACT_GUARD_NAME}",
            )
        )
    elif docker_step is None or final_step is None or final_step[0] <= docker_step[0]:
        issues.append(
            CiGuardIssue(
                "ci.yml:final_artifact_guard",
                "final package build artifact guard must run after Docker local MCP smoke",
            )
        )

    strict_release_step = required_steps.get("strict_pr_release_check")
    strict_names = (
        [
            value.strip("'\"")
            for key, value in _step_direct_mapping_entries(strict_release_step[1])
            if key.lower() == "name"
        ]
        if strict_release_step
        else []
    )
    if strict_names != [STRICT_PR_RELEASE_CHECK_NAME]:
        issues.append(
            CiGuardIssue(
                "ci.yml:strict_pr_release_check",
                f"missing required PR-gated step name: {STRICT_PR_RELEASE_CHECK_NAME}",
            )
        )
    elif not step_has_pr_gate_and_url(strict_release_step[1]):
        issues.append(
            CiGuardIssue(
                "ci.yml:strict_pr_release_check",
                "Strict PR release readiness check must run only on pull_request events and set AI_DEMEMORY_PR_URL from the pull request URL",
            )
        )

    mcp_step = required_steps.get("mcp_smoke")
    mcp_names = (
        [
            value.strip("'\"")
            for key, value in _step_direct_mapping_entries(mcp_step[1])
            if key.lower() == "name"
        ]
        if mcp_step
        else []
    )
    if mcp_names != [MCP_RUNTIME_SMOKE_NAME]:
        issues.append(CiGuardIssue("ci.yml:mcp_smoke", f"missing required PR-gated step name: {MCP_RUNTIME_SMOKE_NAME}"))
    elif not step_has_pr_gate_and_url(mcp_step[1]):
        issues.append(
            CiGuardIssue(
                "ci.yml:mcp_smoke",
                "MCP runtime smoke must run only on pull_request events and set AI_DEMEMORY_PR_URL from the pull request URL",
            )
        )

    ordered_names = (
        "release_check",
        "api_smoke",
        "index",
        "search",
        "eval_recall",
        "strict_pr_release_check",
        "mcp_smoke",
        "install_smoke",
    )
    if all(name in required_steps for name in ordered_names) and not all(
        required_steps[left][0] < required_steps[right][0]
        for left, right in zip(ordered_names, ordered_names[1:])
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
