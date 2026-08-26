#!/usr/bin/env python3
"""Validate the dependency-free documentation site and its source contracts."""

from __future__ import annotations

import hashlib
import re
import shlex
import sys
import tomllib
import ast
import operator
from functools import lru_cache
from enum import Enum
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "site"

# These directories are distributed as public agent instructions. They are a
# first-run surface just like README/install.md: adding another text guide here
# must not silently create a route to an unpublished source package.
PUBLIC_SKILL_GUIDE_ROOTS = (
    Path("skills/ai-dememory"),
    Path("plugins/ai-dememory/skills"),
)
PUBLIC_SKILL_GUIDE_SUFFIXES = frozenset({".json", ".md", ".yaml", ".yml"})
PUBLIC_SKILL_FIRST_RUN_GUIDES = frozenset(
    {
        "skills/ai-dememory/SKILL.md",
        "plugins/ai-dememory/skills/memory-setup/SKILL.md",
    }
)
PUBLIC_SKILL_FRONTMATTER_FIELDS = frozenset({"name", "description"})
PUBLIC_SKILL_FRONTMATTER_NAME_RE = re.compile(r"[a-z][a-z0-9-]*\Z")
PUBLIC_SKILL_FRONTMATTER_ENTRY_RE = re.compile(
    r"(?P<key>[A-Za-z][A-Za-z0-9_-]*):[ \t]+(?P<value>\S.*)\Z"
)
PUBLIC_AGENT_SKILL_YAML_SCHEMAS = {
    "skills/ai-dememory/agents/openai.yaml": {
        "interface": (
            "display_name",
            "short_description",
            "default_prompt",
        )
    }
}
PUBLIC_AGENT_SKILL_LITERAL_TOKEN_RE = re.compile(
    r"(?<![$A-Za-z0-9_])\$ai-dememory(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
# A pending-release exception is intentionally narrower than a generic Markdown
# heading convention.  These are the reviewed, user-facing docs that retain
# source-checkout diagnostics, and only their exact labelled sections may do so.
PENDING_SOURCE_MAINTAINER_SECTION_TITLES = {
    "docs/local-mcp.md": ("Maintainer-only Checkout Diagnostics",),
    "docs/mcp-client-config.md": ("Maintainer-Only Checkout And PR Checks",),
    "docs/scheduler.md": ("Maintainer-only Docker schedule diagnostics",),
    "docs/operations.md": ("Maintainer: Source Checkout Release Validation",),
    "docs/codex-plugin.md": ("Maintainer-only Plugin Template Diagnostics",),
    "docs/distribution.md": (
        "Source checkout: contributors only",
        "Docker source-image diagnostics: maintainers only",
    ),
}
_STABLE_SOURCE_ROUTE_CACHE_SENTINEL = "__stable-source-route-cache__"

REQUIRED_PAGES = (
    "index.html",
    "install/index.html",
    "architecture/index.html",
    "security/index.html",
    "404.html",
)
CONTEXTUAL_INSTALLER_PAGES = frozenset(
    {
        "architecture/index.html",
        "security/index.html",
    }
)

SOURCE_PATHS = (
    "README.md",
    "pyproject.toml",
    "docs/architecture.md",
    "docs/install.md",
    "docs/codex-plugin.md",
    "docs/local-mcp.md",
    "docs/mcp-client-config.md",
    "docs/mcp-tool-profiles.md",
    "docs/operations.md",
    "docs/development-status.md",
    "docs/schema.md",
    "docs/adr/0254-python-node-runtime-boundary.md",
    "docs/adr/0257-bounded-autonomy-and-resource-profiles.md",
    "docs/adr/0259-manual-github-pages-deployment.md",
    ".github/workflows/pages-validate.yml",
    ".github/workflows/pages.yml",
    "scripts/ci_guard.py",
    "scripts/pages_artifact_guard.py",
    "scripts/resource_policy.py",
)

REQUIRED_COMMANDS = (
    "pipx install ai-dememory",
    "ai-dememory init ~/code/my-memory --wizard",
)

STABLE_RELEASE_CONTRACTS = {
    "2.1.1": {
        "required": (
            "pipx install ai-dememory",
            "pipx install --force ai-dememory",
            "ai-dememory init ~/code/my-memory --wizard",
            "ai-dememory --root ~/code/my-memory mcp-config --client codex",
        ),
        # Every visible <pre> is a copyable release surface. Keep this list
        # literal and deliberately smaller than the broader Markdown command
        # allowlist: it is the complete set rendered by the static site.
        "copyable": (
            "pipx install ai-dememory",
            "pipx install --force ai-dememory",
            "uv tool install ai-dememory",
            "ai-dememory init ~/code/my-memory --wizard",
            "ai-dememory --root ~/code/my-memory mcp-config --client codex",
            "ai-dememory --version",
        ),
        "source_only": (),
    },
}

# A release-preparation source can be ahead of its last published stable
# package, but only as an explicit, reviewable state.  Keep this empty when
# source and published release agree: adding a future entry remains a narrow
# opt-in that binds the source to one already-published compatibility route.
# In particular, a future pending entry never grants a package command for the
# pending source version.
RELEASE_PENDING_CONTRACTS: dict[str, dict[str, object]] = {
    "2.1.2": {
        "published_version": "2.1.1",
        "scope_markers": (
            "Source candidate: 2.1.2, unreleased",
            "not installable from a package index until it is tagged and published",
        ),
    },
}

# A pending source has no active TestPyPI package route. A future candidate may
# add exactly one reviewed contract only after its immutable tag, release
# workflow, TestPyPI readback, and GitHub prerelease exist. Historical
# prereleases are release evidence only and never a copyable-install surface.
ACTIVE_PRERELEASE_REQUIRED_COMMANDS: tuple[str, ...] = ()
ACTIVE_PRERELEASE_CONTRACTS: dict[str, dict[str, object]] = {}

# Retain the immutable rc2 provenance in the public handoff without treating
# it as an installation option. Do not add package commands to this contract.
HISTORICAL_PRERELEASE_CONTRACTS = {
    "2.1.1rc2": {
        "status_evidence": (
            "v2.1.1rc2",
            "https://test.pypi.org/project/ai-dememory/2.1.1rc2/",
            "https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v2.1.1rc2",
        ),
        "status_marker": "historical prerelease evidence",
    },
}

RELEASE_SCOPE_DOCS = (
    "README.md",
    "docs/install.md",
    "docs/codex-plugin.md",
    "docs/operations.md",
)

STABLE_INSTALL_DOCS = (
    *RELEASE_SCOPE_DOCS,
    # These are user-facing setup/operations guides even though their
    # release-scope wording is not part of the short release-status set above.
    # Keep them in the full audit so checkout recipes cannot bypass the same
    # public-route policy as README/install.
    "docs/local-mcp.md",
    "docs/mcp-client-config.md",
    "docs/create-memory-repo.md",
    "docs/distribution.md",
    "docs/mcp-tool-profiles.md",
    "docs/scheduler.md",
    "docs/scheduler-plugin-blueprint.md",
)

# This is intentionally a curated public-reader boundary, rather than a
# recursive ``docs/**/*.md`` glob. ADRs, release checklists, planning records,
# and CI evidence legitimately describe source-checkout execution and are not
# installation/user guidance. The stable first-run set, every user/product page
# reachable from the public documentation portal, and the PyPI package README
# belong here. Keep this list explicit and covered by an end-to-end mutation
# test below.
PUBLIC_SOURCE_ROUTE_DOCS = (
    *STABLE_INSTALL_DOCS,
    "README-PYPI.md",
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
)

STABLE_PACKAGE_COMMAND_RE = re.compile(
    r"(?P<command>"
    r"(?:pipx(?:\.exe)?\s+(?:install|upgrade|reinstall)"
    r"|uv(?:\.exe)?\s+(?:tool\s+install|pip\s+install)"
    r"|pip(?:3(?:\.\d+)?)?(?:\.exe)?\s+install"
    r"|(?:python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?(?:\s+-3(?:\.\d+)?)?)\s+-m\s+pip\s+install)"
    r"(?:(?!ai[-_.]+dememory)[^\r\n`<])*?"
    r"ai[-_.]+dememory[^\r\n`<]*"
    r")"
    ,
    re.IGNORECASE,
)

STABLE_DOC_REQUIRED_COMMANDS = {
    "README.md": (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
    ),
    "docs/install.md": (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
    ),
    "docs/local-mcp.md": (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
        "ai-dememory --root ~/code/my-memory mcp-config --client codex",
    ),
    "docs/mcp-client-config.md": (
        "pipx install --force ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
        "ai-dememory --root ~/code/my-memory mcp-config --client codex",
    ),
    "docs/codex-plugin.md": (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
    ),
    "docs/operations.md": (
        "pipx install --force ai-dememory",
        "ai-dememory --root ~/code/my-memory mcp-config --client codex",
    ),
    "docs/distribution.md": (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
    ),
    "docs/create-memory-repo.md": (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
    ),
    "docs/scheduler-plugin-blueprint.md": (
        "ai-dememory init ~/code/my-memory --wizard",
    ),
}

EXPLICIT_ROOT_MCP_DOCS = {"docs/mcp-tool-profiles.md"}

MCP_CLIENT_SMOKE_GUIDES = (
    "docs/codex-plugin.md",
    "docs/local-mcp.md",
    "docs/mcp-client-config.md",
    "docs/operations.md",
    "scripts/README.md",
)
MCP_CLIENT_SMOKE_PATH_PLACEHOLDER_RE = re.compile(
    r"<(?P<kind>absolute-checkout|initialized-[A-Za-z0-9-]+)>",
    re.IGNORECASE,
)

SITE_PAGE_REQUIRED_COMMANDS = {
    "index.html": (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
    ),
    "install/index.html": (
        "pipx install ai-dememory",
        "pipx install --force ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
        "ai-dememory --root ~/code/my-memory mcp-config --client codex",
    ),
}

ALLOWED_EXTERNAL_HOSTS = {"github.com"}
PRODUCTION_ASSET_BUDGET = 250 * 1024
JAVASCRIPT_BUDGET = 8 * 1024
RASTER_BUDGET = 120 * 1024
# ``site.js`` is a deliberately tiny, review-only progressive enhancement.  It
# is not a general JavaScript extension point: any byte-level change must be
# reviewed and paired with an intentional update to this contract.
SITE_JAVASCRIPT_SHA256 = "a574b87570d84d44b9dfdd34d92b0b0c8fdc495f11ccf87cc9a4689d9573f9df"
ALLOWED_LOCAL_ACTIVE_ASSETS = frozenset(
    {
        "assets/favicon.svg",
        "assets/site.css",
        "assets/site.js",
    }
)
LOCAL_ACTIVE_ASSET_TAGS = frozenset({"embed", "iframe", "link", "object", "script"})
LOCAL_ACTIVE_ASSET_SUFFIXES = frozenset({".css", ".htm", ".html", ".js", ".mjs", ".svg"})
URL_REFERENCE_ATTRIBUTES = (
    "background",
    "codebase",
    "data",
    "dynsrc",
    "href",
    "lowsrc",
    "manifest",
    "poster",
    "src",
    "xlink:href",
)
URL_LIST_REFERENCE_ATTRIBUTES = ("imagesrcset", "srcset")
AUTOMATIC_RESOURCE_ATTRIBUTES = frozenset(
    {
        "background",
        "codebase",
        "data",
        "dynsrc",
        "imagesrcset",
        "lowsrc",
        "manifest",
        "poster",
        "src",
        "srcset",
    }
)
AUTOMATIC_HREF_REFERENCE_TAGS = frozenset({"feimage", "image", "link", "use"})
SVG_URL_PRESENTATION_ATTRIBUTES = frozenset(
    {
        "clip-path",
        "cursor",
        "fill",
        "filter",
        "marker",
        "marker-end",
        "marker-mid",
        "marker-start",
        "mask",
        "stroke",
    }
)
SVG_DYNAMIC_CONTENT_TAGS = frozenset(
    {
        "animate",
        "animatecolor",
        "animatemotion",
        "animatetransform",
        "discard",
        "set",
    }
)
STATIC_INTERACTIVE_CONTROL_TAGS = frozenset(
    {"button", "form", "input", "optgroup", "option", "select", "textarea"}
)
DECLARATIVE_SHADOW_DOM_ATTRIBUTES = frozenset(
    {
        "shadowrootmode",
        "shadowrootclonable",
        "shadowrootdelegatesfocus",
        "shadowrootserializable",
    }
)
SVG_ACTIVE_CONTENT_RE = re.compile(
    r"<\s*(?:[^\s:/<>]+:)?"
    r"(?:animate(?:color|motion|transform)?|discard|embed|foreignobject|iframe|object|script|set)\b|"
    r"\bon[a-z0-9_-]+\s*=|(?:href|xlink:href)\s*=|@import\b|\burl\s*\(",
    re.IGNORECASE,
)
SVG_DYNAMIC_QNAME_ELEMENT_RE = re.compile(
    r"<\s*(?P<name>[^\s:/<>]+:(?:animate(?:color|motion|transform)?|discard|set))\b",
    re.IGNORECASE,
)
CSS_ESCAPE_RE = re.compile(
    r"\\(?:(?P<hex>[0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?|(?P<character>[^\r\n\f]))"
)
CSS_RESOURCE_REFERENCE_RE = re.compile(
    r"@import\b|(?:url|image-set|image)\s*\(",
    re.IGNORECASE,
)
CSS_URL_FUNCTION_RE = re.compile(r"url\s*\(\s*(?P<target>[^)]*)\s*\)", re.IGNORECASE)
CSS_NON_URL_RESOURCE_FUNCTION_RE = re.compile(r"(?:image-set|image)\s*\(", re.IGNORECASE)
CSS_CONTENT_DECLARATION_RE = re.compile(
    r"(?<![-\w])content\s*:\s*(?P<value>[^;{}]+)", re.IGNORECASE
)
CSS_COMMENT_TOKEN_RE = re.compile(r"/\*|\*/")
ALLOWED_CSS_GENERATED_CONTENT = frozenset(
    {
        '""',
        '"≠"',
        '"✓"',
        '"→"',
        '"↓"',
        "attr(data-label)",
        "counter(process, decimal-leading-zero)",
    }
)
ALLOWED_CSS_DATA_LABELS = frozenset(
    {
        "Boundary",
        "Can see or change",
        "Cadence",
        "Candidates",
        "File / scan ceilings",
        "Future Node plane",
        "Python owns now",
        "Recall",
    }
)


def _release_pending_contract(
    stable_version: str,
    source_version: str | None,
) -> dict[str, object] | None:
    """Return the only legal published-stable/source-pending pairing, if any."""
    if source_version is None:
        return None
    contract = RELEASE_PENDING_CONTRACTS.get(source_version)
    if contract is None:
        return None
    if contract.get("published_version") != stable_version:
        return None
    return contract


def _release_contract_errors(stable_version: str, source_version: str) -> list[str]:
    """Reject implicit package availability when source and PyPI differ.

    ``source != stable`` is deliberately not enough to authorize a candidate.
    The only exception is a listed pending contract tied to the exact published
    compatibility version, and that state must not retain a TestPyPI route.
    """
    pending_contract = RELEASE_PENDING_CONTRACTS.get(source_version)
    if pending_contract is not None:
        errors: list[str] = []
        if source_version == stable_version:
            errors.append(
                "docs site guard: a release-pending source must differ from its "
                "published stable package"
            )
        if pending_contract.get("published_version") != stable_version:
            errors.append(
                "docs site guard: release-pending source does not bind to the "
                "documented published stable package"
            )
        markers = pending_contract.get("scope_markers")
        if not isinstance(markers, tuple) or len(markers) != 2 or not all(
            isinstance(marker, str) and marker for marker in markers
        ):
            errors.append(
                "docs site guard: release-pending source must define two explicit "
                "public scope markers"
            )
        if ACTIVE_PRERELEASE_CONTRACTS:
            errors.append(
                "docs site guard: release-pending source must not retain an active "
                "TestPyPI prerelease contract"
            )
        if ACTIVE_PRERELEASE_REQUIRED_COMMANDS:
            errors.append(
                "docs site guard: release-pending source must not retain active "
                "prerelease command requirements"
            )
        return errors
    if source_version == stable_version:
        if ACTIVE_PRERELEASE_CONTRACTS:
            return [
                "docs site guard: active TestPyPI prerelease contracts must be empty "
                "when source version matches the documented stable release"
            ]
        return []
    if len(ACTIVE_PRERELEASE_CONTRACTS) != 1:
        return [
            "docs site guard: source differing from the published stable package "
            "requires exactly one explicit active TestPyPI prerelease contract or "
            "a release-pending contract"
        ]
    return []


def _published_release_label(stable_version: str, source_version: str) -> str:
    if _release_pending_contract(stable_version, source_version) is not None:
        return f"published-{stable_version}"
    return f"stable-{stable_version}"


def release_scope_markers(stable_version: str, source_version: str) -> tuple[str, ...]:
    markers = ["current stable", stable_version]
    pending_contract = _release_pending_contract(stable_version, source_version)
    if pending_contract is not None:
        markers.extend(pending_contract["scope_markers"])
        return tuple(markers)
    if source_version != stable_version:
        # A reviewed TestPyPI route may stay available while a future source
        # candidate advances. Its availability is explicitly reviewed rather
        # than inferred from source version; historical prereleases are
        # deliberately excluded from this active documentation contract.
        markers.extend(
            contract["scope_marker"]
            for contract in ACTIVE_PRERELEASE_CONTRACTS.values()
        )
        if source_version not in ACTIVE_PRERELEASE_CONTRACTS:
            markers.append(f"source candidate {source_version} is unreleased")
    return tuple(markers)


def site_release_lens(stable_version: str, source_version: str) -> str:
    pending_contract = _release_pending_contract(stable_version, source_version)
    if pending_contract is not None:
        return pending_contract["scope_markers"][0]
    if source_version != stable_version:
        contract = ACTIVE_PRERELEASE_CONTRACTS.get(source_version)
        if contract is not None:
            return contract["site_lens"]
        return f"Source candidate: {source_version}, unreleased"
    return f"Stable release: {source_version}"


EXECUTABLE_COMMAND_START_RE = re.compile(
    r"^(?:&[ \t]*)?[\"']?(?:"
    r"ai-dememory(?:\.exe)?|pipx(?:\.exe)?|uvx(?:\.exe)?|uv(?:\.exe)?|pip(?:3(?:\.\d+)?)?(?:\.exe)?|"
    r"python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?(?:[ \t]+-3(?:\.\d+)?)?|"
    r"cd|pushd|echo|sudo|command|env|cmd(?:\.exe)?|powershell(?:\.exe)?|"
    r"pwsh(?:\.exe)?|bash|sh|wsl(?:\.exe)?|docker(?:\.exe)?|docker-compose(?:\.exe)?|poetry(?:\.exe)?|start|call"
    r")[\"']?(?:[ \t]|$)",
    re.IGNORECASE,
)

SENSITIVE_CLI_COMMAND_RE = re.compile(
    r"ai[-_.]+dememory(?:\.py)?[^\r\n]*(?:mcp-config|setup[ \t]+(?:wizard|plan)|version-check)",
    re.IGNORECASE,
)
INLINE_MARKDOWN_CODE_RE = re.compile(
    r"(?P<ticks>`+)(?P<body>.*?)(?P=ticks)",
    re.DOTALL,
)
INLINE_HTML_CODE_RE = re.compile(
    r"<code(?:[ \t][^>]*)?>(?P<body>.*?)</code>",
    re.IGNORECASE | re.DOTALL,
)
DYNAMIC_SHELL_SYNTAX_RE = re.compile(
    r"(?:\$(?:@|\(|\{|[A-Za-z_']|[0-9*#?-])|"
    r"%[A-Za-z_][^%\r\n]*%|![A-Za-z_][^!\r\n]*!|"
    r"`|\^(?=\S)|\{[^{}\r\n]*\}|"
    r"&[ \t]*\(|\+[ \t]*['\"]|['\"][ \t]*\+)",
    re.IGNORECASE,
)
SHELL_LINE_CONTINUATION_RE = re.compile(r"(?:\\|\^)[ \t]*\r?\n")
SHELL_TOKEN_FRAGMENT_RE = re.compile(r"[\\\"']")
# The documentation site has no untracked package-install examples. Every
# supported Python installer and every supported ai-dememory package route
# belongs in a literal release block. Recognize common package-tool spellings
# here rather than trying to emulate shell parsing in prose, then reject dynamic
# spellings near an installer verb separately below.
UNTRACKED_PACKAGE_ACTION_RE = re.compile(
    r"(?:"
    r"\b(?:pipx|pip(?:3(?:\.\d+)?)?|uvx?|conda|pipenv|poetry|pdm)(?:\.exe)?\b"
    r"[^\r\n<]{0,120}?\b(?:install|upgrade|reinstall|run|add)\b"
    r"|\b(?:python(?:3(?:\.\d+)?)?|pypy(?:3(?:\.\d+)?)?|py)(?:\.exe)?\b"
    r"[^\r\n<]{0,120}?\b-m\s+(?:pip|pipx|uv)\b"
    r"[^\r\n<]{0,120}?\b(?:install|upgrade|reinstall|run|add)\b"
    r")",
    re.IGNORECASE,
)
UNTRACKED_AI_DEMEMORY_PACKAGE_ACTION_RE = re.compile(
    r"\b[a-z][a-z0-9_.-]*(?:\.exe)?\b[^\r\n<]{0,120}?"
    r"\b(?:install|upgrade|reinstall|run|add|exec|dlx)\b[^\r\n<]{0,120}?"
    r"\bai[-_.]+dememory\b",
    re.IGNORECASE,
)
UNTRACKED_AI_DEMEMORY_RUNNER_RE = re.compile(
    r"\b(?:npx|bunx|uvx)(?:\.exe)?\b[^\r\n<]{0,120}?"
    r"\bai[-_.]+dememory\b",
    re.IGNORECASE,
)
EXPANDED_DOCKER_RUN_RE = re.compile(
    r"(?:&[ \t]*)?['\"]?"
    r"(?:\$(?:\{[A-Za-z_][A-Za-z0-9_]*\}|env:[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)|"
    r"%[A-Za-z_][A-Za-z0-9_]*%|![A-Za-z_][A-Za-z0-9_]*!)"
    r"['\"]?(?:[ \t]+[^;&|\r\n \t]+)*[ \t]+run(?:[ \t]|$)",
    re.IGNORECASE,
)


def _normalized_shell_whitespace(text: str) -> str:
    return "".join(" " if character.isspace() else character for character in text).strip()


def _decode_css_escape(match: re.Match[str]) -> str:
    hexadecimal = match.group("hex")
    if hexadecimal is None:
        return match.group("character")
    codepoint = int(hexadecimal, 16)
    if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
        return "\ufffd"
    return chr(codepoint)


def _contains_css_resource_reference(text: str) -> bool:
    """Recognize CSS resource tokens after decoding CSS identifier escapes."""
    decoded = CSS_ESCAPE_RE.sub(_decode_css_escape, text)
    return CSS_RESOURCE_REFERENCE_RE.search(decoded) is not None


def _contains_unapproved_css_generated_content(text: str) -> bool:
    """Allow only the site's reviewed decorative CSS generated content."""
    decoded = CSS_ESCAPE_RE.sub(_decode_css_escape, text)
    for match in CSS_CONTENT_DECLARATION_RE.finditer(decoded):
        value = re.sub(r"\s+", " ", match.group("value").strip())
        if value not in ALLOWED_CSS_GENERATED_CONTENT:
            return True
    return False


def _contains_css_comment_token(text: str) -> bool:
    """CSS comments are not needed by the reviewed static stylesheet."""
    return CSS_COMMENT_TOKEN_RE.search(text) is not None


def _contains_unapproved_svg_presentation_resource(text: str) -> bool:
    """Allow only local SVG fragment URLs in presentation attributes.

    A ``url(#fragment)`` names an element in the same inline SVG and does not
    load a resource. Every other URL plus the CSS ``image`` resource functions
    is outside the static site's reviewed SVG policy.
    """
    decoded = CSS_ESCAPE_RE.sub(_decode_css_escape, text)
    if CSS_NON_URL_RESOURCE_FUNCTION_RE.search(decoded) is not None:
        return True
    for match in CSS_URL_FUNCTION_RE.finditer(decoded):
        target = match.group("target").strip().strip("'\"")
        if not target.startswith("#"):
            return True
    return False


def _collapsed_dynamic_shell_text(text: str) -> str:
    """Erase dynamic shell fragments to recognize security-sensitive stems."""
    collapsed = text.casefold().replace("^", "").replace("`", "")
    collapsed = re.sub(
        r"\$(['\"])([^'\"\r\n]*)\1",
        lambda match: match.group(2),
        collapsed,
    )
    collapsed = re.sub(r"\$\{[^{}\r\n]*\}", "", collapsed)
    collapsed = re.sub(r"\$\([^()\r\n]*\)", "", collapsed)
    collapsed = re.sub(r"\$(?:@|\*|[0-9#?-]|[A-Za-z_][A-Za-z0-9_]*)", "", collapsed)
    collapsed = re.sub(r"%[^%\r\n]*%|![^!\r\n]*!", "", collapsed)
    return re.sub(
        r"\{([^{}\r\n.]*)\.\.[^{}\r\n]*\}",
        lambda match: match.group(1),
        collapsed,
    )


def _contains_unquoted_sensitive_cli(text: str) -> bool:
    """Detect a security-sensitive CLI command outside prose code spans."""
    if _contains_disallowed_code_span_concatenation(text):
        return True
    without_html_code = INLINE_HTML_CODE_RE.sub("", text)
    without_inline_code = INLINE_MARKDOWN_CODE_RE.sub("", without_html_code)
    if _contains_disallowed_sensitive_markdown(without_inline_code):
        return True
    if _contains_disallowed_sensitive_shell_syntax(without_inline_code):
        return True
    if SENSITIVE_CLI_COMMAND_RE.search(without_inline_code) is not None:
        return True
    try:
        token_variants = _shell_token_variants(without_inline_code)
    except ValueError:
        return False
    return any(_tokens_trigger_sensitive_command(tokens) for tokens in token_variants)


def _contains_disallowed_code_span_concatenation(text: str) -> bool:
    """Reject code spans used as shell token fragments rather than containers."""
    matches = tuple(INLINE_MARKDOWN_CODE_RE.finditer(text))
    if not matches:
        return False
    rendered = INLINE_MARKDOWN_CODE_RE.sub(lambda match: match.group("body"), text)
    rendered_probe = _rendered_markdown_probe(rendered)
    if _contains_disallowed_sensitive_shell_syntax(rendered_probe):
        return True
    if not _rendered_probe_contains_sensitive_command(rendered_probe):
        return False
    outside = INLINE_MARKDOWN_CODE_RE.sub("", text)
    if _starts_with_executable_command(_normalized_shell_whitespace(outside)):
        return True
    for match in matches:
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        if (
            (before and before in "-_")
            or (after and after in "-_")
            or before.isalnum()
            or after.isalnum()
        ):
            return True
    return False


class _InlineVisibleTextParser(HTMLParser):
    """Collect visible inline HTML text without interpreting attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._nonrendered_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in COMMAND_AUDIT_EXCLUDED_CONTAINER_TAGS:
            self._nonrendered_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in COMMAND_AUDIT_EXCLUDED_CONTAINER_TAGS and self._nonrendered_depth:
            self._nonrendered_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._nonrendered_depth == 0:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(unescape(f"&#{name};"))


def _html_visible_text(text: str) -> str:
    parser = _InlineVisibleTextParser()
    parser.feed(text)
    parser.close()
    return "".join(parser.parts)


def _rendered_markdown_probe(text: str) -> str:
    """Approximate copyable text only for conservative command rejection."""
    text = INLINE_MARKDOWN_CODE_RE.sub(lambda match: match.group("body"), text)
    text = INLINE_HTML_CODE_RE.sub(lambda match: match.group("body"), text)
    rendered = _html_visible_text(text)
    rendered = re.sub(r"[\u2010-\u2015\u2212]", "-", rendered)
    rendered = _strip_balanced_markdown_link_destinations(rendered)
    for _ in range(4):
        previous = rendered
        rendered = re.sub(r"!?\[([^\]\r\n]*)\]\[[^\]\r\n]*\]", r"\1", rendered)
        rendered = re.sub(r"\[([^\]\r\n]*)\]", r"\1", rendered)
        rendered = (
            rendered.replace("**", "")
            .replace("__", "")
            .replace("~~", "")
            .replace("*", "")
        )
        if rendered == previous:
            break
    return rendered


def _strip_balanced_markdown_link_destinations(text: str) -> str:
    """Keep link labels while removing balanced inline destinations."""
    output: list[str] = []
    index = 0
    while index < len(text):
        label_end = text.find("](", index)
        if label_end < 0:
            output.append(text[index:])
            break
        label_start = text.rfind("[", index, label_end)
        if label_start < 0:
            output.append(text[index : label_end + 2])
            index = label_end + 2
            continue
        depth = 1
        cursor = label_end + 2
        escaped = False
        while cursor < len(text) and depth:
            character = text[cursor]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            cursor += 1
        if depth:
            output.append(text[index:])
            break
        output.append(text[index:label_start])
        output.append(text[label_start + 1 : label_end])
        index = cursor
    return "".join(output)


def _rendered_probe_contains_sensitive_command(rendered: str) -> bool:
    normalized = _normalized_shell_whitespace(rendered)
    if SENSITIVE_CLI_COMMAND_RE.search(normalized) is not None:
        return True
    try:
        normalized_token_variants = _shell_token_variants(normalized)
    except ValueError:
        return True
    if any(
        _tokens_trigger_sensitive_command(tokens)
        for tokens in normalized_token_variants
    ):
        return True
    for line in rendered.splitlines() or [rendered]:
        try:
            token_variants = _shell_token_variants(_normalized_shell_whitespace(line))
        except ValueError:
            return True
        if any(_tokens_trigger_sensitive_command(tokens) for tokens in token_variants):
            return True
    return False


def _contains_disallowed_sensitive_markdown(text: str) -> bool:
    """Reject rendered token concatenation; commands must remain literal text."""
    rendered = _rendered_markdown_probe(text)
    if rendered == text:
        return False
    return _rendered_probe_contains_sensitive_command(rendered)


def _multiline_comment_sensitive_entries(text: str) -> tuple[tuple[int, str], ...]:
    """Find commands reconstructed by removing a multiline HTML comment."""
    entries: list[tuple[int, str]] = []
    for match in re.finditer(r"<!--.*?-->", text, flags=re.DOTALL):
        if "\n" not in match.group(0) and "\r" not in match.group(0):
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end < 0:
            line_end = len(text)
        reconstructed = text[line_start : match.start()] + text[match.end() : line_end]
        rendered = _rendered_markdown_probe(reconstructed)
        if _rendered_probe_contains_sensitive_command(rendered):
            entries.append((text.count("\n", 0, line_start) + 1, reconstructed))
    return tuple(entries)


def _inline_command_entries(text: str) -> tuple[tuple[int, str, bool, bool], ...]:
    entries: list[tuple[int, str, bool, bool]] = []
    matches = [*INLINE_MARKDOWN_CODE_RE.finditer(text), *INLINE_HTML_CODE_RE.finditer(text)]
    for match in sorted(matches, key=lambda item: item.start()):
        if match.re is INLINE_MARKDOWN_CODE_RE:
            line_start = text.rfind("\n", 0, match.start()) + 1
            prefix = text[line_start : match.start()]
            if len(match.group("ticks")) >= 3 and not prefix.strip():
                # Fenced blocks are already validated as physical/logical shell
                # lines; they are not one giant inline code span.
                continue
        snippet = match.group("body")
        line_number = text.count("\n", 0, match.start()) + 1
        if snippet:
            normalized = _normalized_shell_whitespace(snippet)
            if _starts_with_executable_command(normalized) or _contains_unquoted_sensitive_cli(normalized):
                unsupported_whitespace = any(
                    character.isspace() and character not in " \t"
                    for character in snippet
                )
                entries.append((line_number, normalized, unsupported_whitespace, False))
    return tuple(entries)


MAX_RENDERED_SOFTBREAK_LINES = 12
INCOMPLETE_SOFTBREAK_SHELL_PREFIX_RE = re.compile(
    r"^(?:&[ \t]*)?(?:(?:call|command|env|start|sudo|wsl)[ \t]+)?"
    r"(?:docker(?:\.exe)?(?:[ \t]+(?:run|--\S+))|"
    r"(?:bash|sh|cmd(?:\.exe)?|powershell(?:\.exe)?|pwsh(?:\.exe)?)[ \t]+"
    r"(?:-[^ \t]*c|/c|/k|-command))",
    re.IGNORECASE,
)


def _multiline_rendered_sensitive_entries(text: str) -> tuple[tuple[int, str], ...]:
    """Reject commands created only by bounded CommonMark softbreak whitespace."""
    entries: list[tuple[int, str]] = []
    lines = text.splitlines()
    fenced_lines: set[int] = set()
    active_fence: tuple[str, int] | None = None
    for index, raw_line in enumerate(lines):
        fence_match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", raw_line)
        if active_fence is not None:
            fenced_lines.add(index)
            marker, minimum = active_fence
            if re.match(rf"^[ \t]{{0,3}}{re.escape(marker)}{{{minimum},}}[ \t]*$", raw_line):
                active_fence = None
            continue
        if fence_match is not None:
            marker_text = fence_match.group(1)
            active_fence = (marker_text[0], len(marker_text))
            fenced_lines.add(index)
    for index in range(len(lines)):
        if index in fenced_lines or not lines[index].strip():
            continue
        initial = _normalized_shell_whitespace(_rendered_markdown_probe(lines[index]))
        if not initial:
            continue
        rendered_parts: list[str] = []
        for end in range(index, min(len(lines), index + MAX_RENDERED_SOFTBREAK_LINES)):
            if end in fenced_lines or not lines[end].strip():
                break
            rendered = _normalized_shell_whitespace(_rendered_markdown_probe(lines[end]))
            if not rendered:
                break
            rendered_parts.append(rendered)
        if len(rendered_parts) < 2:
            continue

        left = rendered_parts[0]
        right = " ".join(rendered_parts[1:])
        candidate = f"{left} {right}"
        sensitive_cli_boundary = (
            re.search(r"(?:^|[ \t])ai[-_.]+dememory(?:\.exe)?$", left, re.IGNORECASE)
            is not None
            and re.match(
                r"^(?:mcp-config(?:[ \t]|$)|version-check(?:[ \t]|$)|"
                r"setup[ \t]+(?:wizard|plan)(?:[ \t]|$)|"
                r"mcp(?:[ \t].*--stdio(?:[ \t]|$))|"
                r"init(?:[ \t].*)?--wizard(?:[ \t]|$))",
                right,
                re.IGNORECASE,
            )
            is not None
        )
        package_boundary = False
        try:
            combined_token_variants = _shell_token_variants(candidate)
        except ValueError:
            combined_token_variants = ()
        sensitive_shell_candidate = (
            _starts_with_executable_command(candidate)
            and any(
                _tokens_trigger_softbreak_shell_boundary(tokens)
                for tokens in combined_token_variants
            )
        )
        expanded_docker_candidate = (
            EXPANDED_DOCKER_RUN_RE.search(candidate) is not None
            and re.search(r"\bai[-_.]+dememory(?:\b|:)", candidate, re.IGNORECASE)
            is not None
        )
        next_index = index + len(rendered_parts)
        window_exhausted = (
            len(rendered_parts) == MAX_RENDERED_SOFTBREAK_LINES
            and next_index < len(lines)
            and next_index not in fenced_lines
            and bool(lines[next_index].strip())
            and bool(_rendered_markdown_probe(lines[next_index]).strip())
        )
        unbounded_shell_candidate = (
            window_exhausted
            and _starts_with_executable_command(candidate)
            and (
                INCOMPLETE_SOFTBREAK_SHELL_PREFIX_RE.match(candidate) is not None
                or any(
                    _tokens_start_incomplete_softbreak_shell_boundary(tokens)
                    for tokens in combined_token_variants
                )
            )
        )
        if any(_tokens_contain_package_install(tokens) for tokens in combined_token_variants):
            left_mentions_package = re.search(
                r"ai[-_.]+dememory(?:==[^ \t]+)?", left, re.IGNORECASE
            ) is not None
            package_boundary = (
                not left_mentions_package
                and re.search(
                    r"(?:pipx|pip(?:3(?:\.\d+)?)?|python(?:3(?:\.\d+)?)?[ \t]+-m[ \t]+pip|"
                    r"py(?:[ \t]+-3(?:\.\d+)?)?[ \t]+-m[ \t]+pip|uv[ \t]+tool)"
                    r"[ \t]+install(?:[ \t]+--?[A-Za-z0-9_.=-]+)*$",
                    left,
                    re.IGNORECASE,
                )
                is not None
                and re.match(
                    r"^ai[-_.]+dememory(?:==[^ \t]+)?(?:[ \t]|$)",
                    right,
                    re.IGNORECASE,
                )
                is not None
            )
            if not package_boundary:
                package_boundary = (
                    re.search(
                        r"(?:^|[ \t])(?:pipx|pip(?:3(?:\.\d+)?)?|uv[ \t]+tool)$",
                        left,
                        re.IGNORECASE,
                    )
                    is not None
                    and re.match(
                        r"^install[ \t]+ai[-_.]+dememory(?:==[^ \t]+)?(?:[ \t]|$)",
                        right,
                        re.IGNORECASE,
                    )
                    is not None
                )
        if (
            sensitive_cli_boundary
            or package_boundary
            or sensitive_shell_candidate
            or expanded_docker_candidate
            or unbounded_shell_candidate
        ):
            entries.append((index + 1, candidate))
    return tuple(entries)


def _contains_disallowed_sensitive_shell_syntax(text: str) -> bool:
    """Reject dynamic/escaped spellings instead of attempting shell emulation."""
    collapsed = _collapsed_dynamic_shell_text(text)
    dynamic = DYNAMIC_SHELL_SYNTAX_RE.search(text) is not None
    # Match an executable/package stem, not an environment variable such as
    # ``AI_DEMEMORY_ROOT``. Strip shell token fragments first so quoted package
    # spellings such as ``ai-'dememory'`` cannot evade the literal-route rule.
    # The trailing-boundary check still excludes the Docker diagnostic's
    # ``AI_DEMEMORY_ROOT`` environment assignment.
    package_stem_probe = SHELL_TOKEN_FRAGMENT_RE.sub("", collapsed)
    ai_package_shape = re.search(
        r"(?<![a-z0-9])ai[-_.]+dememory(?:\.py)?(?![a-z0-9_-])",
        package_stem_probe,
    ) is not None
    sensitive_components = (
        ("mcp" in collapsed and "config" in collapsed)
        or ("version" in collapsed and "check" in collapsed)
        or ("setup" in collapsed and ("wizard" in collapsed or "plan" in collapsed))
    )
    installer_shape = (
        "install" in collapsed
        and ai_package_shape
        and any(
            launcher in collapsed
            for launcher in ("pipx", "pip ", "pip3", "uv ", "uvx", "python", "py ")
        )
    )
    dynamic_launcher = re.match(
        r"^[ \t]*(?:&[ \t]*)?(?:\$|%[^%]+%|![^!]+!|\()",
        text,
    ) is not None
    brace_range = re.search(r"\{[^{}\r\n]*\.\.[^{}\r\n]*\}", text) is not None
    dynamic_docker_launcher = re.search(
        r"(?:^|[;&| \t/\\])docker(?:\.exe)?(?=[;&| \t]|$)",
        collapsed,
    ) is not None
    dynamic_docker_run = (
        dynamic
        and ai_package_shape
        and re.search(r"(?:^|[ \t])run(?:[ \t]|$)", collapsed) is not None
        and (dynamic_launcher or dynamic_docker_launcher)
    )
    expanded_docker_run = (
        dynamic
        and ai_package_shape
        and EXPANDED_DOCKER_RUN_RE.search(text) is not None
    )
    sensitive_shape = (
        installer_shape
        or (sensitive_components and (ai_package_shape or dynamic_launcher))
        or (ai_package_shape and brace_range)
        or dynamic_docker_run
        or expanded_docker_run
    )
    pure_powershell_env_assignment = re.fullmatch(
        r"[ \t]*\$env:[A-Za-z_][A-Za-z0-9_]*[ \t]*=[^;&|\r\n]*",
        text,
        re.IGNORECASE,
    ) is not None
    command_candidate = (
        sensitive_shape
        or (dynamic_launcher and sensitive_components)
    )
    escaped_sensitive_stem = re.search(
        r"(?:ai|mcp|version)[A-Za-z0-9_-]*[\\^`][A-Za-z0-9_-]+",
        text,
        re.IGNORECASE,
    ) is not None
    quoted_package_stem = (
        installer_shape
        and re.search(
            r"(?:[\"']ai[-_.]*|ai[-_.]*[\"']|[\"'][A-Za-z0-9_.-]*memory)",
            text,
            re.IGNORECASE,
        )
        is not None
    )
    return (
        dynamic
        and not pure_powershell_env_assignment
        and command_candidate
    ) or escaped_sensitive_stem or quoted_package_stem


def _launcher_name(token: str) -> str:
    """Return a cross-platform executable basename without a Windows suffix."""
    normalized = token.replace("\\", "/").casefold()
    name = normalized.rsplit("/", 1)[-1].removesuffix(".exe")
    # POSIX shlex consumes unquoted Windows backslashes. A drive prefix remains,
    # so recover only an exact known launcher suffix rather than any basename.
    if ":" in name:
        versioned_launcher = re.search(
            r"(?:python|pip)3(?:\.\d+)?$",
            name,
            re.IGNORECASE,
        )
        if versioned_launcher is not None:
            return versioned_launcher.group(0).casefold()
        for launcher in (
            "ai-dememory",
            "docker",
            "pipx",
            "uvx",
            "uv",
            "python",
            "pip",
            "py",
            "bash",
            "sh",
            "cmd",
            "powershell",
            "pwsh",
        ):
            if name.endswith(launcher):
                return launcher
    return name


SHELL_LAUNCHER_NAMES = frozenset({"bash", "sh", "cmd", "powershell", "pwsh"})
EXECUTABLE_LAUNCHER_NAMES = frozenset(
    {
        "ai-dememory",
        "bash",
        "call",
        "cd",
        "cmd",
        "command",
        "docker",
        "docker-compose",
        "echo",
        "env",
        "pipx",
        "poetry",
        "pushd",
        "pwsh",
        "py",
        "powershell",
        "sh",
        "start",
        "sudo",
        "uv",
        "uvx",
        "wsl",
    }
)

POWERSHELL_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)


def _normalized_powershell_quotes(text: str) -> str:
    """Normalize every Unicode quote delimiter recognized by PowerShell."""
    return text.translate(POWERSHELL_QUOTE_TRANSLATION)


def _leading_command_token(text: str) -> str:
    """Return the literal leading launcher even when the rest will not parse."""
    stripped = _normalized_powershell_quotes(text).lstrip(" \t")
    if stripped.startswith("&"):
        stripped = stripped[1:].lstrip(" \t")
    if not stripped:
        return ""
    if stripped[0] in {"\"", "'"}:
        closing_index = stripped.find(stripped[0], 1)
        if closing_index < 0:
            return stripped[1:].split(maxsplit=1)[0]
        return stripped[1:closing_index]
    return re.split(r"[ \t;&|<>]", stripped, maxsplit=1)[0]


def _starts_with_executable_command(text: str) -> bool:
    """Classify path-qualified launchers by normalized executable basename."""
    try:
        tokens = _preferred_shell_tokens(text)
    except ValueError:
        token = _leading_command_token(text)
        arguments: tuple[str, ...] = ()
    else:
        index = 1 if tokens and tokens[0] == "&" else 0
        token = tokens[index] if index < len(tokens) else ""
        arguments = tokens[index + 1 :]
    launcher = _launcher_name(token)
    if launcher in SHELL_LAUNCHER_NAMES:
        path_qualified = any(separator in token for separator in ("/", "\\", ":"))
        if path_qualified or not arguments:
            return True
        first_argument = arguments[0].casefold()
        if launcher in {"bash", "sh"}:
            return first_argument.startswith("-") or first_argument.endswith(".sh")
        if launcher == "cmd":
            return first_argument.startswith("/")
        return first_argument.startswith(("-", "/")) or first_argument.endswith(".ps1")
    if launcher in {"docker", "docker-compose"}:
        path_qualified = any(separator in token for separator in ("/", "\\", ":"))
        if path_qualified:
            return True
        if not arguments:
            return False
        first_argument = arguments[0].casefold()
        return first_argument.startswith("-") or first_argument in {
            "build",
            "buildx",
            "compose",
            "image",
            "run",
        }
    return (
        launcher in EXECUTABLE_LAUNCHER_NAMES
        or re.fullmatch(r"python(?:3(?:\.\d+)?)?", launcher) is not None
        or re.fullmatch(r"pip(?:3(?:\.\d+)?)?", launcher) is not None
        or EXECUTABLE_COMMAND_START_RE.match(text) is not None
    )


def _is_ai_dememory_cli_token(token: str) -> bool:
    return _launcher_name(token) in {"ai-dememory", "ai_dememory.py"}


def _tokens_contain_sensitive_cli(tokens: tuple[str, ...]) -> bool:
    folded = tuple(token.casefold() for token in tokens)
    for index, token in enumerate(tokens):
        if not _is_ai_dememory_cli_token(token):
            continue
        tail = folded[index + 1 :]
        if "mcp-config" in tail or "version-check" in tail:
            return True
        if "mcp" in tail:
            return True
        if "init" in tail and "--wizard" in tail:
            return True
        if any(
            tail[position : position + 2] in (("setup", "wizard"), ("setup", "plan"))
            for position in range(len(tail) - 1)
        ):
            return True
    return False


PACKAGE_SPEC_TOKEN_RE = re.compile(r"^ai[-_.]+dememory(?:==[^\s]+)?$", re.IGNORECASE)
SENSITIVE_OPTION_FLAGS = (
    "--client",
    "--command",
    "--image",
    "--idle-timeout-seconds",
    "--mode",
    "--profile",
    "--require-bound-root",
    "--require-version",
    "--root",
    "--stdio",
    "--wizard",
)
SINGLETON_SECURITY_OPTIONS = (
    *SENSITIVE_OPTION_FLAGS,
)


def _tokens_may_execute_sensitive_cli(tokens: tuple[str, ...]) -> bool:
    if _tokens_contain_sensitive_cli(tokens):
        return True
    folded = tuple(token.casefold() for token in tokens)
    for index, token in enumerate(tokens):
        if not _is_ai_dememory_cli_token(token):
            continue
        tail = folded[index + 1 :]
        if "init" in tail and any(
            option.startswith("--")
            and option != "--wizard"
            and "--wizard".startswith(option.partition("=")[0])
            for option in tail
        ):
            return True
    return False


def _abbreviated_sensitive_options(tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Return argparse-style prefixes that could weaken a documented guard."""
    if not _tokens_may_execute_sensitive_cli(tokens):
        return ()
    abbreviations: list[str] = []
    for token in tokens:
        option = token.partition("=")[0].casefold()
        if (
            option.startswith("--")
            and option not in SENSITIVE_OPTION_FLAGS
            and any(flag.startswith(option) for flag in SENSITIVE_OPTION_FLAGS)
        ):
            abbreviations.append(token)
    return tuple(abbreviations)


def _duplicate_security_options(tokens: tuple[str, ...]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for token in tokens:
        option = token.partition("=")[0].casefold()
        if option in SINGLETON_SECURITY_OPTIONS:
            counts[option] = counts.get(option, 0) + 1
    return tuple(sorted(option for option, count in counts.items() if count > 1))


def _package_installer_command_ends(tokens: tuple[str, ...]) -> tuple[int, ...]:
    """Return the token positions immediately after supported installer verbs."""
    folded = tuple(token.casefold() for token in tokens)

    def command_end_after(start: int, commands: frozenset[str]) -> int:
        for position in range(start, len(folded)):
            if folded[position] in commands:
                return position + 1
        return -1

    command_ends: list[int] = []
    for index, token in enumerate(folded):
        launcher = _launcher_name(token)
        command_end = -1
        if launcher == "pipx":
            command_end = command_end_after(
                index + 1, frozenset({"install", "upgrade", "reinstall"})
            )
        elif launcher == "uv":
            tail = folded[index + 1 :]
            if "tool" in tail or "pip" in tail:
                command_end = command_end_after(index + 1, frozenset({"install"}))
        elif re.fullmatch(r"pip(?:3(?:\.\d+)?)?", launcher):
            command_end = command_end_after(index + 1, frozenset({"install"}))
        elif re.fullmatch(r"python(?:3(?:\.\d+)?)?", launcher):
            for module_index in range(index + 1, len(folded) - 1):
                if (
                    folded[module_index] == "-m"
                    and folded[module_index + 1] in {"pip", "pipx", "uv"}
                ):
                    command_end = command_end_after(
                        module_index + 2,
                        frozenset({"install", "upgrade", "reinstall"}),
                    )
                    break
        elif launcher == "py":
            cursor = index + 1
            if cursor < len(folded) and re.fullmatch(r"-3(?:\.\d+)?", folded[cursor]):
                cursor += 1
            for module_index in range(cursor, len(folded) - 1):
                if (
                    folded[module_index] == "-m"
                    and folded[module_index + 1] in {"pip", "pipx", "uv"}
                ):
                    command_end = command_end_after(
                        module_index + 2,
                        frozenset({"install", "upgrade", "reinstall"}),
                    )
                    break
        if command_end >= 0:
            command_ends.append(command_end)
    return tuple(command_ends)


def _tokens_contain_package_install(tokens: tuple[str, ...]) -> bool:
    """Detect supported package installers that contain a literal package spec."""
    return any(
        any(PACKAGE_SPEC_TOKEN_RE.fullmatch(value) for value in tokens[command_end:])
        for command_end in _package_installer_command_ends(tokens)
    )


def _tokens_contain_mutable_runner(tokens: tuple[str, ...]) -> bool:
    """Detect ephemeral package runners, including wrapped launcher forms.

    Stable documentation never uses a runner whose environment can be resolved
    afresh at execution time. Even an apparently pinned runner is rejected so
    the documented install, version check, and executed binary remain one
    inspectable environment.
    """
    folded = tuple(token.casefold() for token in tokens)

    def command_end_after(start: int, command: str) -> int:
        for position in range(start, len(folded)):
            if folded[position] == command:
                return position + 1
        return -1

    def contains_package_or_cli(values: tuple[str, ...]) -> bool:
        for index, value in enumerate(values):
            if PACKAGE_SPEC_TOKEN_RE.fullmatch(value) is not None or _is_ai_dememory_cli_token(value):
                return True
            folded_value = value.casefold()
            if folded_value.startswith(("--with=", "--with-editable=")):
                if PACKAGE_SPEC_TOKEN_RE.fullmatch(value.partition("=")[2]) is not None:
                    return True
            if folded_value in {"--with", "--with-editable"} and index + 1 < len(values):
                if PACKAGE_SPEC_TOKEN_RE.fullmatch(values[index + 1]) is not None:
                    return True
        return False

    for index, token in enumerate(folded):
        launcher = _launcher_name(token)
        command_end = -1
        if launcher == "pipx":
            command_end = command_end_after(index + 1, "run")
        elif launcher == "uvx":
            command_end = index + 1
        elif launcher == "uv":
            command_end = command_end_after(index + 1, "run")
        elif re.fullmatch(r"python(?:3(?:\.\d+)?)?", launcher):
            for module_index in range(index + 1, len(folded) - 1):
                if folded[module_index] != "-m":
                    continue
                module = folded[module_index + 1]
                if module in {"pipx", "uv"}:
                    command_end = command_end_after(module_index + 2, "run")
                    break
        elif launcher == "py":
            cursor = index + 1
            if cursor < len(folded) and re.fullmatch(r"-3(?:\.\d+)?", folded[cursor]):
                cursor += 1
            for module_index in range(cursor, len(folded) - 1):
                if (
                    folded[module_index] == "-m"
                    and folded[module_index + 1] in {"pipx", "uv"}
                ):
                    command_end = command_end_after(module_index + 2, "run")
                    break
        if command_end >= 0 and contains_package_or_cli(tokens[command_end:]):
            return True
    return False


def _has_shell_continuation(text: str) -> bool:
    """Return whether a physical line ends in a supported shell continuation."""
    if not text:
        return False
    if text[-1] in {"\\", "^"}:
        return True
    # A Markdown inline-code closing tick is paired on the same physical line;
    # a PowerShell continuation is the unmatched final tick.
    return text[-1] == "`" and text.count("`") % 2 == 1


def _executable_command_entries(text: str) -> tuple[tuple[int, str, bool, bool], ...]:
    """Return line, logical command, unsupported-space, and continuation state.

    Stable documentation accepts Bash, PowerShell, and cmd continuation
    markers, but reconstructs their shell meaning before validation so a
    security-sensitive command cannot hide its subcommand or package spec on
    the next physical line. In particular, a marker in the middle of a token
    removes the newline without adding whitespace (``pi\\`` + ``p`` is
    ``pip`` in Bash), whereas a space on either side retains a token boundary.
    """
    entries: list[tuple[int, str, bool, bool]] = []
    parts: list[str] = []
    start_line = 0
    unsupported_whitespace = False
    continuation_requires_separator = False
    for line_number, raw_line in enumerate(text.split("\n"), start=1):
        line = raw_line.removesuffix("\r")
        if not parts:
            start_line = line_number
            unsupported_whitespace = False

        unsupported_whitespace = unsupported_whitespace or any(
            character.isspace() and character not in " \t"
            for character in line
        )
        trimmed = line.rstrip(" \t")
        continued = _has_shell_continuation(trimmed)
        if continued:
            before_marker = trimmed[:-1]
            fragment = before_marker.strip(" \t")
            # A shell continuation removes only the marker/newline. Preserve a
            # separator when it was already present before the marker, or when
            # the next physical line begins with one; otherwise concatenate the
            # fragments exactly as the shell would.
            continuation_requires_separator = bool(
                before_marker and before_marker[-1] in " \t"
            )
        else:
            fragment = line.strip(" \t")
        if parts:
            separator = (
                " " if continuation_requires_separator or line[:1] in {" ", "\t"} else ""
            )
            parts.append(f"{separator}{fragment}")
        else:
            parts.append(fragment)
        if continued:
            continue

        command = "".join(parts)
        probe = _normalized_shell_whitespace(command)
        if _starts_with_executable_command(probe) or _contains_unquoted_sensitive_cli(probe):
            entries.append((start_line, command, unsupported_whitespace, False))
        parts = []
        continuation_requires_separator = False

    if parts:
        command = "".join(parts)
        probe = _normalized_shell_whitespace(command)
        if _starts_with_executable_command(probe) or _contains_unquoted_sensitive_cli(probe):
            entries.append((start_line, command, unsupported_whitespace, True))
    entries.extend(_inline_command_entries(text))
    return tuple(entries)


def _executable_command_lines(text: str) -> tuple[str, ...]:
    """Return literal copy/paste commands, excluding prose/comments/echo."""
    return tuple(command for _, command, _, _ in _executable_command_entries(text))


def _shell_tokens(
    command: str,
    *,
    preserve_windows_backslashes: bool = False,
) -> tuple[str, ...]:
    lexer = shlex.shlex(
        _normalized_powershell_quotes(command),
        posix=True,
        punctuation_chars=";&|<>",
    )
    if preserve_windows_backslashes:
        # POSIX shlex consumes unquoted Windows separators. Keep a second,
        # non-interpreting representation for path-qualified Windows launchers.
        lexer.escape = ""
        lexer.escapedquotes = ""
    lexer.whitespace_split = True
    lexer.commenters = "#"
    return tuple(lexer)


def _shell_token_variants(command: str) -> tuple[tuple[str, ...], ...]:
    """Return normal shell tokens plus a Windows-path-preserving variant."""
    default_tokens = _shell_tokens(command)
    if "\\" not in command:
        return (default_tokens,)
    windows_tokens = _shell_tokens(command, preserve_windows_backslashes=True)
    if windows_tokens == default_tokens:
        return (default_tokens,)
    return default_tokens, windows_tokens


def _tokenization_security_score(tokens: tuple[str, ...]) -> tuple[int, int]:
    """Prefer a tokenization that preserves a recognizable executable path."""
    recognizable_launchers = 0
    for token in tokens:
        launcher = _launcher_name(token)
        if (
            launcher in EXECUTABLE_LAUNCHER_NAMES
            or re.fullmatch(r"python(?:3(?:\.\d+)?)?", launcher) is not None
            or re.fullmatch(r"pip(?:3(?:\.\d+)?)?", launcher) is not None
        ):
            recognizable_launchers += 1
    return recognizable_launchers, sum(token.count("\\") for token in tokens)


def _preferred_shell_tokens(command: str) -> tuple[str, ...]:
    """Choose the lossless Windows form only when it improves recognition."""
    return max(_shell_token_variants(command), key=_tokenization_security_score)


def _shell_segments(tokens: tuple[str, ...]) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]:
    """Split a tokenized shell line without interpreting any wrapper."""
    segments: list[tuple[str, ...]] = []
    operators: list[str] = []
    current: list[str] = []
    for token in tokens:
        if token and all(character in ";&|<>" for character in token):
            if current:
                segments.append(tuple(current))
                current = []
            operators.append(token)
            continue
        current.append(token)
    if current:
        segments.append(tuple(current))
    return tuple(segments), tuple(operators)


PYTHON_COMMAND_TOKEN_RE = re.compile(
    r"^(?:python(?:3(?:\.\d+)?)?|py)$",
    re.IGNORECASE,
)

INTERNAL_PYTHON_ENTRYPOINTS = {"setup_plan.py", "onboarding.py", "memory_mcp.py"}


def _tokens_execute_internal_python_entrypoint(tokens: tuple[str, ...]) -> bool:
    """Reject Python entrypoints that bypass the supported version-gated CLI."""
    folded = tuple(token.casefold() for token in tokens)
    for index, token in enumerate(folded):
        launcher = _launcher_name(token)
        if not PYTHON_COMMAND_TOKEN_RE.fullmatch(launcher):
            continue
        cursor = index + 1
        if launcher == "py" and cursor < len(folded) and re.fullmatch(r"-3(?:\.\d+)?", folded[cursor]):
            cursor += 1
        tail = folded[cursor:]
        for position, argument in enumerate(tail):
            if argument == "-m" and position + 1 < len(tail):
                module = tail[position + 1]
                if module == "ai_dememory_tool" or module.startswith("ai_dememory_tool."):
                    return True
                if module == "runpy" and any("ai_dememory_tool" in value for value in tail[position + 2 :]):
                    return True
            if argument == "-c" and position + 1 < len(tail):
                code = tail[position + 1]
                if "ai_dememory_tool" in code or any(name in code for name in INTERNAL_PYTHON_ENTRYPOINTS):
                    return True
        if any(
            value.replace("\\", "/").rsplit("/", 1)[-1] in INTERNAL_PYTHON_ENTRYPOINTS
            for value in tail
        ):
            return True
    return False


DOCKER_GLOBAL_OPTIONS_REQUIRING_VALUE = frozenset(
    {
        "--config",
        "--context",
        "--host",
        "--log-level",
        "--tlscacert",
        "--tlscert",
        "--tlskey",
        "-c",
        "-h",
        "-l",
    }
)

CONTAINER_BUILD_OPTIONS_REQUIRING_VALUE = frozenset(
    {
        "-f",
        "-p",
        "-t",
        "--build-arg",
        "--cache-from",
        "--cache-to",
        "--env-file",
        "--file",
        "--label",
        "--platform",
        "--profile",
        "--progress",
        "--project-directory",
        "--project-name",
        "--secret",
        "--ssh",
        "--tag",
        "--target",
    }
)


def _leading_docker_run_index(
    segment: tuple[str, ...], docker_index: int
) -> int | None:
    """Find a Docker ``run`` only after syntactically global Docker options.

    This deliberately does not search arbitrary prose after a leading ``docker``
    word.  It is used for rendered soft-break reconstruction, where a sentence
    such as ``Docker smoke ... Run ai-dememory ...`` must not become a command.
    """
    index = docker_index + 1
    while index < len(segment):
        argument = segment[index]
        folded = argument.casefold()
        if folded == "run":
            return index
        if not argument.startswith("-") or argument == "--":
            return None
        option = folded.split("=", 1)[0]
        if "=" not in argument and option in DOCKER_GLOBAL_OPTIONS_REQUIRING_VALUE:
            if index + 1 >= len(segment) or segment[index + 1] == "--":
                return None
            index += 2
        else:
            index += 1
    return None


def _is_leading_raw_ai_dememory_docker_run(
    segment: tuple[str, ...], docker_index: int
) -> bool:
    """Recognize an ordered leading ``docker [flags] run ... image`` form."""
    run_index = _leading_docker_run_index(segment, docker_index)
    return run_index is not None and any(
        re.search(r"(?:^|/)ai-dememory(?::|@|$)", value.casefold()) is not None
        for value in segment[run_index + 1 :]
    )


def _is_raw_ai_dememory_docker_run(tokens: tuple[str, ...]) -> bool:
    for launcher_index, token in enumerate(tokens):
        if _launcher_name(token) != "docker":
            continue
        folded_tail = tuple(value.casefold() for value in tokens[launcher_index + 1 :])
        try:
            run_index = folded_tail.index("run")
        except ValueError:
            continue
        if any(
            re.search(r"(?:^|/)ai-dememory(?::|@|$)", value) is not None
            for value in folded_tail[run_index + 1 :]
        ):
            return True
    return False


class _NestedShellInspection(Enum):
    SAFE = "safe"
    RAW_DOCKER = "raw_docker"
    OPAQUE = "opaque"


NESTED_SHELL_MAX_DEPTH = 3
NESTED_SHELL_LAUNCHERS = SHELL_LAUNCHER_NAMES
TRANSPARENT_SHELL_WRAPPERS = frozenset({"call", "command", "env", "start", "sudo", "wsl"})
SAFE_NESTED_PAYLOAD_LAUNCHERS = {
    "bash": frozenset({":", "echo", "false", "printf", "true"}),
    "sh": frozenset({":", "echo", "false", "printf", "true"}),
    "cmd": frozenset({"echo", "rem", "ver"}),
    "powershell": frozenset({"write-host", "write-output"}),
    "pwsh": frozenset({"write-host", "write-output"}),
}
SAFE_NESTED_LITERAL_ARGUMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,:/@%+=_-]*$")


def _segment_shell_launcher_index(segment: tuple[str, ...]) -> int | None:
    """Locate an executed shell, ignoring shell names used as ordinary arguments."""
    if not segment:
        return None
    first_launcher = _launcher_name(segment[0])
    if first_launcher in NESTED_SHELL_LAUNCHERS:
        return 0
    if first_launcher not in TRANSPARENT_SHELL_WRAPPERS:
        return None
    if len(segment) > 1 and _launcher_name(segment[1]) in NESTED_SHELL_LAUNCHERS:
        return 1
    return None


def _is_shell_prose_heading(segment: tuple[str, ...], launcher_index: int) -> bool:
    """Keep existing prose labels such as ``PowerShell equivalent:`` benign."""
    if launcher_index != 0:
        return False
    normalized = " ".join(segment).casefold()
    return normalized in {
        "bash users can run the equivalent command below.",
        "powershell users can run the equivalent command below.",
        "powershell equivalent:",
        "powershell direct smoke examples:",
    }


def _is_nonexecuting_shell_reference(segment: tuple[str, ...], shell_index: int) -> bool:
    """Recognize a few wrapper options whose value merely names a shell."""
    first = _launcher_name(segment[0]) if segment else ""
    if first == "command":
        return len(segment) == 3 and segment[1] in {"-V", "-v"} and shell_index == 2
    if first == "sudo":
        return (
            len(segment) > 3
            and segment[1].casefold() in {"-g", "--group", "-u", "--user"}
            and shell_index == 2
        )
    if first == "wsl":
        return (
            len(segment) > 3
            and segment[1].casefold() in {"-d", "--distribution", "-u", "--user"}
            and shell_index == 2
        )
    return False


def _shell_invocation_is_opaque(
    segment: tuple[str, ...],
    launcher_index: int,
) -> bool:
    """Require flags that suppress implicit profile/startup execution."""
    launcher = _launcher_name(segment[launcher_index])
    arguments = segment[launcher_index + 1 :]
    if launcher in {"bash", "sh"}:
        command_indices = [
            index
            for index, argument in enumerate(arguments)
            if argument.startswith("-")
            and not argument.startswith("--")
            and "c" in argument[1:].casefold()
        ]
        if len(command_indices) != 1:
            return True
        return arguments[: command_indices[0] + 1] != ("-c",)
    if launcher == "cmd":
        command_indices = [
            index
            for index, argument in enumerate(arguments)
            if argument.casefold() in {"/c", "/k"}
        ]
        if len(command_indices) != 1:
            return True
        prefix = tuple(value.casefold() for value in arguments[: command_indices[0]])
        return "/d" not in prefix or any(value not in {"/d", "/q", "/s"} for value in prefix)
    if launcher in {"powershell", "pwsh"}:
        command_indices = [
            index
            for index, argument in enumerate(arguments)
            if argument.casefold() in {"-c", "-command"}
        ]
        if len(command_indices) != 1:
            return True
        prefix = tuple(value.casefold() for value in arguments[: command_indices[0]])
        allowed = {"-nologo", "-noninteractive", "-noprofile"}
        return "-noprofile" not in prefix or any(value not in allowed for value in prefix)
    return True


def _nested_payload_is_literal(payload: str, launcher: str) -> bool:
    """Accept only one static, non-executing diagnostic/output command."""
    if DYNAMIC_SHELL_SYNTAX_RE.search(payload) is not None:
        return False
    try:
        tokens = _preferred_shell_tokens(payload)
    except ValueError:
        return False
    segments, operators = _shell_segments(tokens)
    if operators or len(segments) != 1 or not segments[0]:
        return False
    command, *arguments = segments[0]
    return (
        _launcher_name(command) in SAFE_NESTED_PAYLOAD_LAUNCHERS.get(launcher, frozenset())
        and all(SAFE_NESTED_LITERAL_ARGUMENT_RE.fullmatch(argument) is not None for argument in arguments)
    )


def _powershell_uses_opaque_execution_mode(arguments: tuple[str, ...]) -> bool:
    """Reject encoded, file-backed, and otherwise non-literal PowerShell input."""
    opaque_parameters = ("encodedarguments", "encodedcommand", "file", "commandwithargs")
    for argument in arguments:
        if not argument.startswith(("-", "/")):
            continue
        option = argument.lstrip("-/").split(":", 1)[0].split("=", 1)[0].casefold()
        if option in {"c", "command"}:
            continue
        if option and any(parameter.startswith(option) for parameter in opaque_parameters):
            return True
    return False


def _inline_shell_payload(
    segment: tuple[str, ...],
    launcher_index: int,
) -> str | None:
    """Return literal inline code, or None when the shell source is opaque."""
    launcher = _launcher_name(segment[launcher_index])
    arguments = segment[launcher_index + 1 :]
    if launcher in {"bash", "sh"}:
        command_indices: list[int] = []
        for index, argument in enumerate(arguments):
            if not argument.startswith("-") or argument.startswith("--"):
                continue
            options = argument[1:]
            if "s" in options.casefold():
                return None
            if "c" in options.casefold():
                command_indices.append(index)
        if len(command_indices) != 1:
            return None
        command_index = command_indices[0]
        if any(not value.startswith("-") for value in arguments[:command_index]):
            return None
        if command_index + 1 >= len(arguments):
            return None
        return arguments[command_index + 1]

    if launcher == "cmd":
        command_indices = [
            index
            for index, argument in enumerate(arguments)
            if argument.casefold() in {"/c", "/k"}
        ]
        if len(command_indices) != 1:
            return None
        command_index = command_indices[0]
        if command_index + 1 >= len(arguments):
            return None
        return " ".join(arguments[command_index + 1 :])

    if launcher in {"powershell", "pwsh"}:
        if _powershell_uses_opaque_execution_mode(arguments):
            return None
        command_indices = [
            index
            for index, argument in enumerate(arguments)
            if argument.casefold() in {"-c", "-command"}
        ]
        if len(command_indices) != 1:
            return None
        command_index = command_indices[0]
        if command_index + 1 >= len(arguments):
            return None
        payload = " ".join(arguments[command_index + 1 :])
        return None if payload == "-" else payload

    return None


def _inspect_nested_shell(
    tokens: tuple[str, ...],
    *,
    remaining_depth: int = NESTED_SHELL_MAX_DEPTH,
) -> _NestedShellInspection:
    """Inspect literal nested shell strings and fail closed on opaque execution."""
    if _is_raw_ai_dememory_docker_run(tokens):
        return _NestedShellInspection.RAW_DOCKER

    result = _NestedShellInspection.SAFE
    segments, _ = _shell_segments(tokens)
    for segment in segments:
        launcher_index = _segment_shell_launcher_index(segment)
        if launcher_index is None:
            shell_indices = [
                index
                for index, token in enumerate(segment)
                if _launcher_name(token) in NESTED_SHELL_LAUNCHERS
            ]
            if shell_indices and not all(
                _is_nonexecuting_shell_reference(segment, index)
                for index in shell_indices
            ):
                result = _NestedShellInspection.OPAQUE
            continue
        if _is_shell_prose_heading(segment, launcher_index):
            continue
        if remaining_depth <= 0:
            result = _NestedShellInspection.OPAQUE
            continue
        payload = _inline_shell_payload(segment, launcher_index)
        if payload is None:
            result = _NestedShellInspection.OPAQUE
            continue
        try:
            nested_tokens = _preferred_shell_tokens(payload)
        except ValueError:
            result = _NestedShellInspection.OPAQUE
            continue
        nested_result = _inspect_nested_shell(
            nested_tokens,
            remaining_depth=remaining_depth - 1,
        )
        if nested_result is _NestedShellInspection.RAW_DOCKER:
            return nested_result
        launcher = _launcher_name(segment[launcher_index])
        if (
            nested_result is _NestedShellInspection.OPAQUE
            or _shell_invocation_is_opaque(segment, launcher_index)
            or not _nested_payload_is_literal(payload, launcher)
        ):
            result = nested_result
            if result is _NestedShellInspection.SAFE:
                result = _NestedShellInspection.OPAQUE
    return result


def _tokens_trigger_sensitive_shell_boundary(tokens: tuple[str, ...]) -> bool:
    """Recognize Docker and nested-shell execution that must not cross softbreaks."""
    return _inspect_nested_shell(tokens) is not _NestedShellInspection.SAFE


def _tokens_start_raw_ai_dememory_docker_run(tokens: tuple[str, ...]) -> bool:
    """Require an actual leading Docker invocation before reconstructing softbreaks."""
    segments, operators = _shell_segments(tokens)
    if operators or len(segments) != 1:
        return False
    segment = segments[0]
    index = 1 if segment and segment[0] == "&" else 0
    if index < len(segment) and _launcher_name(segment[index]) in TRANSPARENT_SHELL_WRAPPERS:
        index += 1
    if index >= len(segment):
        return False
    return (
        _launcher_name(segment[index]) == "docker"
        and _is_leading_raw_ai_dememory_docker_run(segment, index)
    )


def _tokens_start_softbreak_shell_boundary(tokens: tuple[str, ...]) -> bool:
    """Limit softbreak reconstruction to actual Docker or nested-shell launchers."""
    if _tokens_start_raw_ai_dememory_docker_run(tokens):
        return True
    segments, operators = _shell_segments(tokens)
    return (
        not operators
        and len(segments) == 1
        and _segment_shell_launcher_index(segments[0]) is not None
    )


def _tokens_start_incomplete_softbreak_shell_boundary(tokens: tuple[str, ...]) -> bool:
    """Fail closed when an executable Docker/shell prefix outgrows its window."""
    segments, operators = _shell_segments(tokens)
    if operators or len(segments) != 1:
        return False
    segment = segments[0]
    index = 1 if segment and segment[0] == "&" else 0
    if index < len(segment) and _launcher_name(segment[index]) in TRANSPARENT_SHELL_WRAPPERS:
        index += 1
    if index >= len(segment):
        return False
    if _launcher_name(segment[index]) == "docker":
        tail = segment[index + 1 :]
        return bool(tail) and (tail[0].casefold() == "run" or tail[0].startswith("-"))
    launcher_index = _segment_shell_launcher_index(segment)
    return (
        launcher_index is not None
        and not _is_shell_prose_heading(segment, launcher_index)
        and _shell_invocation_is_opaque(segment, launcher_index)
    )


def _tokens_trigger_softbreak_shell_boundary(tokens: tuple[str, ...]) -> bool:
    """Send reconstructed Docker/nested-shell candidates through shared checks."""
    return (
        _tokens_start_softbreak_shell_boundary(tokens)
        and _tokens_trigger_sensitive_command(tokens)
    )


def _tokens_trigger_sensitive_command(tokens: tuple[str, ...]) -> bool:
    """Apply every command boundary check to one parsed source representation."""
    return (
        _tokens_contain_sensitive_cli(tokens)
        or _tokens_contain_package_install(tokens)
        or _tokens_contain_mutable_runner(tokens)
        or _tokens_execute_internal_python_entrypoint(tokens)
        or _tokens_trigger_sensitive_shell_boundary(tokens)
    )


def _ai_dememory_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize installed and documented source-checkout CLI launchers."""
    if not tokens:
        return ()
    launcher_index = 0
    raw_launcher = tokens[launcher_index]
    if raw_launcher.casefold() in {"ai-dememory", "ai-dememory.exe"}:
        return ("ai-dememory", *tokens[launcher_index + 1 :])
    if any(separator in raw_launcher for separator in ("/", "\\", ":")):
        return ()
    python_launcher = _launcher_name(raw_launcher)
    if not PYTHON_COMMAND_TOKEN_RE.fullmatch(python_launcher):
        return ()
    index = launcher_index + 1
    if python_launcher == "py" and index < len(tokens) and re.fullmatch(r"-3(?:\.\d+)?", tokens[index]):
        index += 1
    if index >= len(tokens):
        return ()
    script_path = tokens[index].replace("\\", "/")
    if script_path not in {"scripts/ai_dememory.py", "./scripts/ai_dememory.py"}:
        return ()
    return ("ai-dememory", *tokens[index + 1 :])


def _is_mcp_config_tokens(tokens: tuple[str, ...]) -> bool:
    tokens = _ai_dememory_tokens(tokens)
    if not tokens:
        return False
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            index += 2
            continue
        if argument.startswith("--root="):
            index += 1
            continue
        break
    return index < len(tokens) and tokens[index] == "mcp-config"


def _is_setup_wizard_tokens(tokens: tuple[str, ...]) -> bool:
    tokens = _ai_dememory_tokens(tokens)
    if not tokens:
        return False
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            index += 2
            continue
        if argument.startswith("--root="):
            index += 1
            continue
        break
    return tokens[index : index + 2] == ("setup", "wizard")


def _is_setup_plan_tokens(tokens: tuple[str, ...]) -> bool:
    tokens = _ai_dememory_tokens(tokens)
    if not tokens:
        return False
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            index += 2
            continue
        if argument.startswith("--root="):
            index += 1
            continue
        break
    return tokens[index : index + 2] == ("setup", "plan")


def _is_direct_mcp_tokens(tokens: tuple[str, ...]) -> bool:
    tokens = _ai_dememory_tokens(tokens)
    if not tokens:
        return False
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            index += 2
            continue
        if argument.startswith("--root="):
            index += 1
            continue
        break
    return index < len(tokens) and tokens[index] == "mcp"


def _is_init_wizard_tokens(tokens: tuple[str, ...]) -> bool:
    tokens = _ai_dememory_tokens(tokens)
    if not tokens:
        return False
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            index += 2
            continue
        if argument.startswith("--root="):
            index += 1
            continue
        break
    return (
        index < len(tokens)
        and tokens[index] == "init"
        and "--wizard" in tokens[index + 1 :]
    )


def _mcp_global_root_values(tokens: tuple[str, ...]) -> tuple[str, ...]:
    tokens = _ai_dememory_tokens(tokens)
    if not tokens:
        return ()
    values: list[str] = []
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            if index + 1 >= len(tokens):
                return ()
            values.append(tokens[index + 1])
            index += 2
            continue
        if argument.startswith("--root="):
            values.append(argument.partition("=")[2])
            index += 1
            continue
        break
    return tuple(values)


def _all_root_values(tokens: tuple[str, ...]) -> tuple[str, ...]:
    tokens = _ai_dememory_tokens(tokens)
    if not tokens:
        return ()
    values: list[str] = []
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            if index + 1 >= len(tokens):
                return ()
            values.append(tokens[index + 1])
            index += 2
            continue
        if argument.startswith("--root="):
            values.append(argument.partition("=")[2])
        index += 1
    return tuple(values)


def _option_values(tokens: tuple[str, ...], option: str) -> tuple[str, ...]:
    """Return literal values supplied for a non-abbreviated CLI option."""
    tokens = _ai_dememory_tokens(tokens)
    values: list[str] = []
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        if argument == option:
            if index + 1 >= len(tokens):
                values.append("")
                break
            values.append(tokens[index + 1])
            index += 2
            continue
        if argument.startswith(f"{option}="):
            values.append(argument.partition("=")[2])
        index += 1
    return tuple(values)


def _normalized_package_command(command: str) -> str:
    normalized = re.sub(
        r"ai[-_.]+dememory",
        "ai-dememory",
        command,
        flags=re.IGNORECASE,
    )
    return " ".join(normalized.split()).casefold()


def _approved_package_commands(stable_version: str) -> set[str]:
    del stable_version
    commands = {
        "pipx install ai-dememory",
        "pipx install --force ai-dememory",
        "uv tool install ai-dememory",
        "python3 -m pip install ai-dememory",
        "py -3 -m pip install ai-dememory",
    }
    # Only an explicit active prerelease contract may add an index command.
    # With stable source this mapping is required to be empty, so historical
    # TestPyPI artifacts are evidence rather than allowlisted installs.
    commands.update(
        contract["package_command"]
        for contract in ACTIVE_PRERELEASE_CONTRACTS.values()
    )
    return commands


def _untracked_site_command_errors(
    text: str,
    label: str,
    *,
    allowed_package_commands: set[str] | None = None,
) -> list[str]:
    """Reject installer-like text outside a reviewed release command block.

    A few architecture/security explanations intentionally show the exact
    already-audited package command as a standalone inline-code line.  Permit
    only those literal lines after the regular stable-command audit has run;
    prose, flags, wrappers, chaining, and every other installer spelling stay
    subject to this fail-closed check.
    """
    errors: list[str] = []
    normalized_allowed = {
        _normalized_package_command(command)
        for command in (allowed_package_commands or set())
    }
    filtered_text = "\n".join(
        ""
        if _normalized_package_command(line.strip()) in normalized_allowed
        else line
        for line in text.splitlines()
    )
    direct_package_action = UNTRACKED_PACKAGE_ACTION_RE.search(filtered_text) is not None
    direct_ai_dememory_action = (
        UNTRACKED_AI_DEMEMORY_PACKAGE_ACTION_RE.search(filtered_text) is not None
    )
    direct_ai_dememory_runner = UNTRACKED_AI_DEMEMORY_RUNNER_RE.search(filtered_text) is not None
    normalized_fragments = SHELL_LINE_CONTINUATION_RE.sub(
        "", filtered_text
    )
    normalized_fragments = SHELL_TOKEN_FRAGMENT_RE.sub("", normalized_fragments)
    fragmented_package_action = (
        UNTRACKED_PACKAGE_ACTION_RE.search(normalized_fragments) is not None
    )
    fragmented_ai_dememory_action = (
        UNTRACKED_AI_DEMEMORY_PACKAGE_ACTION_RE.search(normalized_fragments)
        is not None
    )
    fragmented_ai_dememory_runner = (
        UNTRACKED_AI_DEMEMORY_RUNNER_RE.search(normalized_fragments) is not None
    )
    if (
        direct_package_action
        or direct_ai_dememory_action
        or direct_ai_dememory_runner
        or fragmented_package_action
        or fragmented_ai_dememory_action
        or fragmented_ai_dememory_runner
    ):
        errors.append(f"{label}: untracked package installer text is forbidden")
    if (
        DYNAMIC_SHELL_SYNTAX_RE.search(text) is not None
        or SHELL_LINE_CONTINUATION_RE.search(text) is not None
    ):
        errors.append(
            f"{label}: dynamic or fragmented shell syntax is forbidden in untracked auditable site content"
        )
    else:
        if (
            (fragmented_package_action and not direct_package_action)
            or (fragmented_ai_dememory_action and not direct_ai_dememory_action)
            or (fragmented_ai_dememory_runner and not direct_ai_dememory_runner)
        ):
            errors.append(
                f"{label}: dynamic or fragmented shell syntax is forbidden in untracked auditable site content"
            )
    return errors


def _stable_command_errors(
    text: str,
    stable_version: str,
    label: str,
    *,
    source_version: str | None = None,
    check_executable_lines: bool = True,
    required_executable_commands: tuple[str, ...] = (),
    require_explicit_mcp_root: bool = False,
) -> list[str]:
    errors: list[str] = []
    for line_number, reconstructed in _multiline_comment_sensitive_entries(text):
        errors.append(
            f"{label}:{line_number}: security-sensitive command must use literal Markdown-free command text: {reconstructed!r}"
        )
    allowed_package_commands = _approved_package_commands(stable_version)
    normalized_allowed_package_commands = {
        _normalized_package_command(command) for command in allowed_package_commands
    }
    command_entries = _executable_command_entries(text)
    if check_executable_lines:
        for line_number, rendered in _multiline_rendered_sensitive_entries(text):
            errors.append(
                f"{label}:{line_number}: rendered Markdown must not create a security-sensitive command across soft line breaks: {rendered!r}"
            )
    package_sources = [
        (line_number, raw_line)
        for line_number, raw_line in enumerate(text.split("\n"), start=1)
    ]
    package_sources.extend((line_number, command) for line_number, command, _, _ in command_entries)
    seen_package_commands: set[tuple[int, str]] = set()
    for line_number, source in package_sources:
        for match in STABLE_PACKAGE_COMMAND_RE.finditer(source):
            command = " ".join(match.group("command").split())
            key = (line_number, _normalized_package_command(command))
            if key in seen_package_commands:
                continue
            seen_package_commands.add(key)
            if _normalized_package_command(command) not in normalized_allowed_package_commands:
                errors.append(
                    f"{label}:{line_number}: package command is not allowlisted for the approved release contracts: {command!r}"
                )

    if not check_executable_lines:
        return errors

    commands = tuple(command for _, command, _, _ in command_entries)
    validation_commands: list[tuple[int, str]] = []
    for line_number, command, unsupported_whitespace, unterminated in command_entries:
        normalized = _normalized_shell_whitespace(command)
        if unsupported_whitespace and _rendered_probe_contains_sensitive_command(normalized):
            errors.append(
                f"{label}:{line_number}: executable command contains unsupported shell whitespace: {command!r}"
            )
        if unterminated:
            errors.append(
                f"{label}:{line_number}: executable command has an unterminated shell continuation: {command!r}"
            )
        if re.match(r"^&[ \t]*", normalized):
            errors.append(
                f"{label}:{line_number}: executable command must not use a PowerShell call operator: {command!r}"
            )
        if _contains_disallowed_sensitive_shell_syntax(normalized):
            errors.append(
                f"{label}:{line_number}: security-sensitive command must use literal shell syntax without expansion or escaping: {command!r}"
            )
        if _contains_disallowed_sensitive_markdown(normalized):
            errors.append(
                f"{label}:{line_number}: security-sensitive command must use literal Markdown-free command text: {command!r}"
            )
        if _contains_disallowed_code_span_concatenation(normalized):
            errors.append(
                f"{label}:{line_number}: security-sensitive command must not concatenate Markdown code spans with shell tokens: {command!r}"
            )
        validation_commands.append((line_number, normalized))
    for required in required_executable_commands:
        if required not in commands:
            errors.append(
                f"{label}: required executable stable command is missing: {required!r}"
            )
    exact_check = f"ai-dememory version-check {stable_version}"
    for line_number, command in validation_commands:
        try:
            tokens = _preferred_shell_tokens(command)
        except ValueError as exc:
            errors.append(f"{label}:{line_number}: malformed executable command {command!r}: {exc}")
            continue
        abbreviated_options = _abbreviated_sensitive_options(tokens)
        if abbreviated_options:
            errors.append(
                f"{label}:{line_number}: security-sensitive options must not use argparse abbreviations "
                f"{abbreviated_options!r}: {command!r}"
            )
        duplicate_options = _duplicate_security_options(tokens)
        if duplicate_options and _tokens_may_execute_sensitive_cli(tokens):
            errors.append(
                f"{label}:{line_number}: security-sensitive options must be specified at most once "
                f"{duplicate_options!r}: {command!r}"
            )
        nested_shell_inspection = _inspect_nested_shell(tokens)
        if nested_shell_inspection is _NestedShellInspection.RAW_DOCKER:
            errors.append(
                f"{label}:{line_number}: raw docker run for ai-dememory is forbidden in stable documentation; use generated MCP config or mcp-client-smoke: {command!r}"
            )
        elif nested_shell_inspection is _NestedShellInspection.OPAQUE:
            errors.append(
                f"{label}:{line_number}: nested shell execution cannot be fully inspected; use a literal supported -c/-command, cmd /c or cmd /k command string: {command!r}"
            )
        if _tokens_execute_internal_python_entrypoint(tokens):
            errors.append(
                f"{label}:{line_number}: stable documentation must not execute the internal Python CLI API: {command!r}"
            )
        recognized_package_install = _tokens_contain_package_install(tokens)
        if recognized_package_install:
            tokenized_package_command = " ".join(tokens)
            key = (line_number, _normalized_package_command(tokenized_package_command))
            if key not in seen_package_commands:
                seen_package_commands.add(key)
                if key[1] not in normalized_allowed_package_commands:
                    errors.append(
                        f"{label}:{line_number}: package command is not allowlisted for the approved release contracts: {tokenized_package_command!r}"
                    )
        if _tokens_contain_mutable_runner(tokens):
            errors.append(
                f"{label}:{line_number}: ephemeral package runners are forbidden in stable documentation: {command!r}"
            )
        segments, operators = _shell_segments(tokens)
        mcp_segments = tuple(segment for segment in segments if _is_mcp_config_tokens(segment))
        wizard_segments = tuple(segment for segment in segments if _is_setup_wizard_tokens(segment))
        plan_segments = tuple(segment for segment in segments if _is_setup_plan_tokens(segment))
        direct_mcp_segments = tuple(segment for segment in segments if _is_direct_mcp_tokens(segment))
        init_wizard_segments = tuple(segment for segment in segments if _is_init_wizard_tokens(segment))
        contains_ai_launcher = any(_is_ai_dememory_cli_token(token) for token in tokens)
        contains_ai_reference = contains_ai_launcher or any(
            re.search(r"ai[-_.]+dememory(?:\.py)?", token, re.IGNORECASE)
            for token in tokens
        )
        mentions_mcp_config = contains_ai_reference and any(
            "mcp-config" in token.casefold() for token in tokens
        )
        folded_tokens = tuple(token.casefold() for token in tokens)
        mentions_setup_wizard = contains_ai_reference and any(
            folded_tokens[index : index + 2] == ("setup", "wizard")
            for index in range(len(folded_tokens) - 1)
        )
        mentions_setup_plan = contains_ai_reference and any(
            folded_tokens[index : index + 2] == ("setup", "plan")
            for index in range(len(folded_tokens) - 1)
        )
        mentions_version_check = contains_ai_reference and any(
            "version-check" in token.casefold() for token in tokens
        )
        mentions_direct_mcp = contains_ai_reference and any(
            token.casefold() == "mcp" for token in tokens
        )
        mentions_init_wizard = (
            contains_ai_reference
            and any(token.casefold() == "init" for token in tokens)
            and any(token.casefold() == "--wizard" for token in tokens)
        )
        if mentions_mcp_config and not mcp_segments:
            errors.append(
                f"{label}:{line_number}: executable line mentions mcp-config but is not an analyzable ai-dememory command: {command!r}"
            )
        if mcp_segments and operators:
            errors.append(
                f"{label}:{line_number}: MCP configuration command must not contain shell chaining or redirection: {command!r}"
            )
        for segment in mcp_segments:
            if require_explicit_mcp_root:
                global_root_values = _mcp_global_root_values(segment)
                all_root_values = _all_root_values(segment)
                if (
                    len(global_root_values) != 1
                    or not global_root_values[0]
                    or all_root_values != global_root_values
                ):
                    errors.append(
                        f"{label}:{line_number}: MCP configuration command must select exactly one explicit vault with global --root and no later override: {command!r}"
                    )
        if wizard_segments and operators:
            errors.append(
                f"{label}:{line_number}: setup wizard command must not contain shell chaining or redirection: {command!r}"
            )
        if mentions_setup_wizard and not wizard_segments:
            errors.append(
                f"{label}:{line_number}: executable line mentions setup wizard but is not an analyzable ai-dememory command: {command!r}"
            )
        if plan_segments and operators:
            errors.append(
                f"{label}:{line_number}: setup plan command must not contain shell chaining or redirection: {command!r}"
            )
        if mentions_setup_plan and not plan_segments:
            errors.append(
                f"{label}:{line_number}: executable line mentions setup plan but is not an analyzable ai-dememory command: {command!r}"
            )
        if mentions_direct_mcp and not direct_mcp_segments:
            errors.append(
                f"{label}:{line_number}: executable line mentions a direct MCP server but is not an analyzable ai-dememory command: {command!r}"
            )
        allowed_stdio_input_pipe = (
            operators == ("|",)
            and len(segments) == 2
            and segments[-1] in direct_mcp_segments
        )
        if direct_mcp_segments and operators and not allowed_stdio_input_pipe:
            errors.append(
                f"{label}:{line_number}: direct MCP server command permits only one stdin pipe and no chaining or output redirection: {command!r}"
            )
        for segment in direct_mcp_segments:
            normalized_segment = _ai_dememory_tokens(segment)
            if normalized_segment.count("--require-bound-root") != 1:
                errors.append(
                    f"{label}:{line_number}: direct MCP server command must include exactly one --require-bound-root: {command!r}"
                )
            idle_values = [
                normalized_segment[index + 1]
                for index, token in enumerate(normalized_segment[:-1])
                if token == "--idle-timeout-seconds"
            ]
            idle_values.extend(
                token.partition("=")[2]
                for token in normalized_segment
                if token.startswith("--idle-timeout-seconds=")
            )
            if idle_values and (
                len(idle_values) != 1
                or not idle_values[0].isdigit()
                or int(idle_values[0]) < 1
            ):
                errors.append(
                    f"{label}:{line_number}: stable direct MCP server commands must keep a positive idle lease: {command!r}"
                )
        if mentions_init_wizard and not init_wizard_segments:
            errors.append(
                f"{label}:{line_number}: executable line mentions init --wizard but is not an analyzable ai-dememory command: {command!r}"
            )
        if init_wizard_segments and operators:
            errors.append(
                f"{label}:{line_number}: init --wizard command must not contain shell chaining or redirection: {command!r}"
            )
        sensitive_segments = (
            *mcp_segments,
            *wizard_segments,
            *plan_segments,
            *direct_mcp_segments,
            *init_wizard_segments,
        )
        pending_contract = _release_pending_contract(stable_version, source_version)
        if pending_contract is not None:
            for segment in segments:
                normalized_segment = _ai_dememory_tokens(segment)
                if (
                    not normalized_segment
                    or not _tokens_contain_sensitive_cli(normalized_segment)
                ):
                    continue
                version_values = _option_values(segment, "--require-version")
                if version_values:
                    errors.append(
                        f"{label}:{line_number}: release-pending public documentation must not pass "
                        f"--require-version; exact version checks are release-evidence-only: "
                        f"{command!r}"
                    )
        elif source_version == stable_version and any(
            token == "--require-version" or token.startswith("--require-version=")
            for token in _ai_dememory_tokens(tokens)
        ):
            errors.append(
                f"{label}:{line_number}: stable documentation must not retain a persistent "
                f"--require-version gate: {command!r}"
            )
        for segment in sensitive_segments:
            root_values = _all_root_values(segment)
            if len(root_values) > 1:
                errors.append(
                    f"{label}:{line_number}: security-sensitive command must not override --root: {command!r}"
                )
        version_check_segments = 0
        for segment in segments:
            normalized_segment = _ai_dememory_tokens(segment)
            if len(normalized_segment) >= 2 and normalized_segment[:2] == ("ai-dememory", "version-check"):
                version_check_segments += 1
                if operators or " ".join(normalized_segment) != exact_check:
                    errors.append(
                        f"{label}:{line_number}: version check must be the exact executable line {exact_check!r}"
                    )
        if mentions_version_check and version_check_segments == 0:
            errors.append(
                f"{label}:{line_number}: executable line mentions version-check but is not an analyzable ai-dememory command: {command!r}"
            )
    return errors


def public_skill_guide_required_commands(
    stable_version: str,
    source_version: str,
) -> dict[str, tuple[str, str]]:
    """Return first-run commands that are legal for the active release state."""

    # First-run public skills always name the package, not a release pin.  The
    # pending-release guard still constrains source routes elsewhere, but a
    # pinned wizard would turn a routine setup into a brittle runtime gate.
    del stable_version, source_version
    commands = (
        "pipx install ai-dememory",
        "ai-dememory init ~/code/my-memory --wizard",
    )
    return {relative: commands for relative in PUBLIC_SKILL_FIRST_RUN_GUIDES}


def _public_skill_cli_command_names() -> tuple[frozenset[str], list[str]]:
    """Derive public CLI command names from the checked-in dispatcher source.

    Frontmatter policy must recognize every current top-level command without
    maintaining a second hand-written command list.  This is deliberately a
    bounded AST read rather than an import: importing the CLI would execute
    dependency and environment setup while a documentation guard is running.
    """

    source_path = REPO_ROOT / "ai_dememory_tool" / "cli.py"
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        return frozenset(), [
            "public skill command namespace cannot read ai_dememory_tool/cli.py: "
            f"{exc}"
        ]
    try:
        module = ast.parse(source, filename=str(source_path))
    except SyntaxError as exc:
        return frozenset(), [
            "public skill command namespace cannot parse ai_dememory_tool/cli.py: "
            f"{exc.msg}"
        ]

    command_maps: dict[str, ast.Dict] = {}
    for node in module.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            not isinstance(target, ast.Name)
            or target.id not in {"LOCAL_COMMANDS", "COMMANDS"}
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            return frozenset(), [
                "public skill command namespace requires literal "
                f"{target.id} mapping in ai_dememory_tool/cli.py"
            ]
        command_maps[target.id] = node.value

    missing_maps = {"LOCAL_COMMANDS", "COMMANDS"}.difference(command_maps)
    if missing_maps:
        return frozenset(), [
            "public skill command namespace is missing literal mappings: "
            f"{', '.join(sorted(missing_maps))}"
        ]

    command_names = {"dev"}
    for map_name, command_map in command_maps.items():
        for key in command_map.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                return frozenset(), [
                    "public skill command namespace requires string keys in "
                    f"{map_name}"
                ]
            command_names.add(key.value.casefold())
    return frozenset(command_names), []


def _public_skill_frontmatter(
    relative: str,
    text: str,
) -> tuple[dict[str, str], str, list[str]]:
    """Read the deliberately small, fail-closed SKILL.md metadata subset.

    Public skill metadata is displayed by hosts but is not a command transport.
    The checked-in skills need only a one-line ``name`` and ``description``.
    Rejecting YAML features outside that subset avoids a dependency-bearing YAML
    parser and prevents quoted, folded, flow, tag, alias, or escape syntax from
    changing the command text that reaches a host.
    """

    lines = text.splitlines()
    errors: list[str] = []
    if not lines or lines[0].strip() != "---":
        return {}, text, [f"{relative}: public skill must start with frontmatter"]

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        return {}, text, [f"{relative}: public skill frontmatter is missing its closing delimiter"]

    values: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing_index], start=2):
        entry = PUBLIC_SKILL_FRONTMATTER_ENTRY_RE.fullmatch(line)
        if entry is None:
            errors.append(
                f"{relative}:{line_number}: public skill frontmatter must use a single-line "
                "name or description scalar"
            )
            continue
        key = entry.group("key")
        raw_value = entry.group("value")
        if key not in PUBLIC_SKILL_FRONTMATTER_FIELDS:
            errors.append(
                f"{relative}:{line_number}: public skill frontmatter field {key!r} is not allowed"
            )
            continue
        if key in values:
            errors.append(
                f"{relative}:{line_number}: public skill frontmatter field {key!r} is duplicated"
            )
            continue
        value = _public_skill_frontmatter_scalar(relative, line_number, key, raw_value, errors)
        if value is not None:
            values[key] = value

    missing = PUBLIC_SKILL_FRONTMATTER_FIELDS.difference(values)
    for key in sorted(missing):
        errors.append(f"{relative}: public skill frontmatter is missing {key!r}")
    if "name" in values and PUBLIC_SKILL_FRONTMATTER_NAME_RE.fullmatch(values["name"]) is None:
        errors.append(f"{relative}: public skill frontmatter name must be a simple slug")

    body = "\n".join(lines[closing_index + 1 :]).lstrip("\n")
    return values, body, errors


def _public_skill_frontmatter_scalar(
    relative: str,
    line_number: int,
    key: str,
    raw_value: str,
    errors: list[str],
    *,
    surface: str = "public skill frontmatter",
    allow_literal_skill_token: bool = False,
) -> str | None:
    """Normalize the only scalar forms accepted in public skill metadata."""

    dynamic_probe = raw_value
    if allow_literal_skill_token:
        dynamic_probe = PUBLIC_AGENT_SKILL_LITERAL_TOKEN_RE.sub("", dynamic_probe)
    if DYNAMIC_SHELL_SYNTAX_RE.search(dynamic_probe) is not None:
        errors.append(
            f"{relative}:{line_number}: {surface} {key!r} must not use dynamic shell syntax"
        )
        return None

    if raw_value.startswith(('"', "'")):
        quote = raw_value[0]
        if (
            len(raw_value) < 2
            or not raw_value.endswith(quote)
            or quote in raw_value[1:-1]
            or "\\" in raw_value
        ):
            errors.append(
                f"{relative}:{line_number}: {surface} {key!r} must not use "
                "escapes, multiline, flow, tag, or alias syntax"
            )
            return None
        return raw_value[1:-1]

    if (
        raw_value.startswith(("!", "&", "*", "[", "{", "|", ">", "-", "#"))
        or any(character in raw_value for character in "\\[]{}&*!|>#'\"")
    ):
        errors.append(
            f"{relative}:{line_number}: {surface} {key!r} must use "
            "a single-line plain or quote-only scalar"
        )
        return None
    return raw_value


def _metadata_cli_command_index(
    tokens: tuple[str, ...],
    start: int,
    command_names: frozenset[str],
) -> int | None:
    """Return a real top-level CLI command after an installed launcher."""

    index = start
    while index < len(tokens):
        argument = tokens[index]
        if argument == "--root":
            index += 2
            continue
        if argument.startswith("--root="):
            index += 1
            continue
        break
    if index < len(tokens) and tokens[index].casefold() in command_names:
        return index
    return None


def _is_python_source_dispatcher(tokens: tuple[str, ...], script_index: int) -> bool:
    """Recognize the checked-in Python dispatcher without accepting arbitrary scripts."""

    script_path = tokens[script_index].replace("\\", "/")
    is_path_dispatcher = script_path in {
        "scripts/ai_dememory.py",
        "./scripts/ai_dememory.py",
    }
    is_module_dispatcher = tokens[script_index].casefold() == "scripts.ai_dememory"
    if not is_path_dispatcher and not is_module_dispatcher:
        return False
    for launcher_index, launcher_token in enumerate(tokens[:script_index]):
        launcher = _launcher_name(launcher_token)
        if PYTHON_COMMAND_TOKEN_RE.fullmatch(launcher) is None:
            continue
        intervening = tokens[launcher_index + 1 : script_index]
        if is_path_dispatcher:
            # Any interpreter flags before the checked-in dispatcher still run
            # source code. Treat uncommon flag forms as source execution too.
            return True
        if any(argument == "-m" for argument in intervening):
            return True
    return False


def _tokens_contain_source_dispatcher(tokens: tuple[str, ...]) -> bool:
    """Detect a Python/py call to the public source-checkout dispatcher."""

    for segment in _shell_segments(tokens)[0]:
        for index, token in enumerate(segment):
            if _is_python_source_dispatcher(segment, index):
                return True
    return False


def _source_execution_segments(tokens: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Keep non-executing echo text out of release-pending route checks.

    Shell operators are already split by ``_shell_segments``.  Thus an
    ``echo ...; docker build .`` still leaves the Docker invocation as a
    separately inspectable segment, while ``echo docker build .`` remains a
    literal display command rather than a source-build route.
    """

    return tuple(
        segment
        for segment in _shell_segments(tokens)[0]
        if not segment or _launcher_name(segment[0]) != "echo"
    )


def _container_build_subcommand_index(
    segment: tuple[str, ...],
    index: int,
) -> int | None:
    """Find ``build`` after container-subcommand options without losing values."""

    while index < len(segment):
        argument = segment[index]
        if argument.casefold() == "build":
            return index
        if not argument.startswith("-") or argument == "--":
            return None
        option = argument.casefold().split("=", 1)[0]
        if "=" not in argument and option in CONTAINER_BUILD_OPTIONS_REQUIRING_VALUE:
            if index + 1 >= len(segment):
                return None
            index += 2
            continue
        if "=" not in argument and option not in CONTAINER_BUILD_OPTIONS_REQUIRING_VALUE:
            # Unknown pre-build flags are not safe to interpret.  If they still
            # lead to ``build``, treat the route as a pending source build.
            return next(
                (
                    position
                    for position in range(index + 1, len(segment))
                    if segment[position].casefold() == "build"
                ),
                None,
            )
        index += 1
    return None


def _leading_container_build(
    segment: tuple[str, ...],
    launcher_index: int,
) -> tuple[int, bool] | None:
    """Find a supported Docker/Compose build action and its source semantics."""

    launcher = _launcher_name(segment[launcher_index])
    if launcher == "docker-compose":
        build_index = _container_build_subcommand_index(segment, launcher_index + 1)
        return (build_index, True) if build_index is not None else None

    if launcher != "docker":
        return None
    index = launcher_index + 1
    while index < len(segment):
        argument = segment[index]
        folded = argument.casefold()
        if folded == "build":
            return index, False
        if not argument.startswith("-") or argument == "--":
            break
        option = folded.split("=", 1)[0]
        if "=" not in argument and option in DOCKER_GLOBAL_OPTIONS_REQUIRING_VALUE:
            if index + 1 >= len(segment) or segment[index + 1] == "--":
                break
            index += 2
        else:
            index += 1
    if index >= len(segment) or segment[index].casefold() not in {"image", "buildx", "compose"}:
        return None
    compose_build = segment[index].casefold() == "compose"
    build_index = _container_build_subcommand_index(segment, index + 1)
    return (build_index, compose_build) if build_index is not None else None


def _tokens_build_source_docker_image(tokens: tuple[str, ...]) -> bool:
    """Detect a Docker build that uses the checked-out local build context."""

    for segment in _shell_segments(tokens)[0]:
        for index, token in enumerate(segment):
            build = _leading_container_build(segment, index)
            if build is None:
                continue
            build_index, implicit_checkout_context = build
            if implicit_checkout_context:
                return True
            tail = segment[build_index + 1 :]
            if any(
                argument in {".", "./", ".\\"}
                or argument.startswith(("./", ".\\"))
                for argument in tail
            ):
                return True
    return False


def _is_local_source_argument(token: str) -> bool:
    """Return whether an installer argument resolves outside the stable package.

    Editable assignments are package arguments even though their path is joined
    to the option (``--editable=.``).  A local ``file:`` URI and a shell or
    PowerShell expansion after an installer verb are likewise not a stable,
    reviewable package route while source is release-pending.
    """

    argument = token
    option, separator, assigned_value = token.partition("=")
    if separator and option.casefold() in {"--editable", "-e"}:
        argument = assigned_value

    if DYNAMIC_SHELL_SYNTAX_RE.search(argument) is not None:
        return True
    if argument.casefold().startswith("file:"):
        return True

    return (
        argument in {".", "./", ".\\"}
        or argument.startswith(("./", ".\\", ".["))
    )


def _tokens_install_local_source(tokens: tuple[str, ...]) -> bool:
    """Detect pending-release installs/builds that consume the local checkout."""

    for segment in _shell_segments(tokens)[0]:
        folded = tuple(value.casefold() for value in segment)
        for index, token in enumerate(segment):
            launcher = _launcher_name(token)
            if launcher == "poetry" and index + 1 < len(segment) and folded[index + 1] == "install":
                return True
            if launcher == "uv" and index + 1 < len(segment) and folded[index + 1] == "sync":
                return True
        for command_end in _package_installer_command_ends(segment):
            if any(_is_local_source_argument(value) for value in segment[command_end:]):
                return True
    return False


def _source_execution_route(tokens: tuple[str, ...]) -> str | None:
    """Classify a source-only execution route without trusting its wrapper."""

    source_segments = _source_execution_segments(tokens)
    if any(_tokens_contain_source_dispatcher(segment) for segment in source_segments):
        return "source dispatcher"
    if any(_tokens_build_source_docker_image(segment) for segment in source_segments):
        return "source Docker build"
    if any(_tokens_install_local_source(segment) for segment in source_segments):
        return "local source install"
    return None


def _dynamic_source_execution_errors(
    text: str,
    label: str,
    *,
    allow_explicit_maintainer_sections: bool,
    recognized_source_lines: set[int],
) -> list[str]:
    """Fail closed on escaped source routes before shell tokenization.

    Shell parsers can reconstruct launchers that a token parser cannot see,
    such as ``p^ip``/``p%EMPTY%ip`` in cmd or a Bash continuation in the
    middle of a token. Inspect only a raw line or inline-code span whose
    *collapsed* text starts with a known executable; normal prose that merely
    mentions shell syntax remains outside this route check.
    """

    errors: list[str] = []
    seen_candidates: set[tuple[int, str]] = set()

    def inspect(line_number: int, candidate: str) -> None:
        key = (line_number, candidate)
        if key in seen_candidates or line_number in recognized_source_lines:
            return
        seen_candidates.add(key)
        if (
            DYNAMIC_SHELL_SYNTAX_RE.search(candidate) is None
            and SHELL_LINE_CONTINUATION_RE.search(candidate) is None
        ):
            return
        collapsed = _collapsed_dynamic_shell_text(
            SHELL_LINE_CONTINUATION_RE.sub("", candidate)
        )
        probe = _normalized_shell_whitespace(collapsed)
        if not _starts_with_executable_command(probe):
            return
        try:
            route = _source_execution_route(_preferred_shell_tokens(probe))
        except ValueError:
            # The candidate has already crossed the dynamic source-route
            # boundary. Do not interpret an incomplete shell construct as safe.
            route = "source execution"
        if route is None:
            return
        if allow_explicit_maintainer_sections and _is_explicit_maintainer_source_section(
            text, line_number, label
        ):
            return
        errors.append(
            f"{label}:{line_number}: public user guidance must not execute a {route} "
            "through dynamic or fragmented shell syntax; use the published compatibility "
            "route or move the recipe below an explicit Maintainer-only/Maintainer: Source "
            "Checkout heading"
        )

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        inspect(line_number, raw_line)
    for match in (*INLINE_MARKDOWN_CODE_RE.finditer(text), *INLINE_HTML_CODE_RE.finditer(text)):
        snippet = match.group("body")
        if snippet:
            inspect(text.count("\n", 0, match.start()) + 1, snippet)
    return errors


def _tokens_contain_nested_shell_execution(tokens: tuple[str, ...]) -> bool:
    """Treat actual nested-shell execution shapes as metadata command transport."""

    for segment in _shell_segments(tokens)[0]:
        for index, argument in enumerate(segment):
            launcher = _launcher_name(argument)
            arguments = segment[index + 1 :]
            if launcher in {"bash", "sh"}:
                if any(
                    value.startswith("-")
                    and not value.startswith("--")
                    and "c" in value[1:].casefold()
                    for value in arguments
                ):
                    return True
                if any(
                    value.startswith(("./", ".\\", "/", "~/"))
                    or value.casefold().endswith((".sh", ".bash"))
                    for value in arguments
                ):
                    return True
            elif launcher == "cmd":
                if any(value.casefold() in {"/c", "/k"} for value in arguments):
                    return True
                if any(value.casefold().endswith((".cmd", ".bat")) for value in arguments):
                    return True
            elif launcher in {"powershell", "pwsh"}:
                if any(
                    value.casefold() in {"-c", "-command", "-file", "-encodedcommand"}
                    for value in arguments
                ):
                    return True
                if any(value.casefold().endswith(".ps1") for value in arguments):
                    return True
    return False


def _metadata_contains_command_shape(
    value: str,
    command_names: frozenset[str],
) -> bool:
    """Recognize commands in normalized host metadata without banning prose.

    A product mention such as ``ai-dememory tool`` is descriptive prose.  A bare
    launcher followed by a command derived from the CLI source, a source
    dispatcher, an installer, a mutable runner, or a local Docker build is an
    executable transport and is forbidden in host metadata.
    """

    try:
        tokens = _preferred_shell_tokens(value)
    except ValueError:
        # The scalar grammar already rejects quotes and escapes that could make
        # tokenization ambiguous. Treat any remaining malformed shell form as
        # non-command prose and let the bounded scalar check be authoritative.
        return False
    if _package_installer_command_ends(tokens) or _tokens_contain_mutable_runner(tokens):
        return True
    if (
        _tokens_contain_nested_shell_execution(tokens)
        or _tokens_contain_source_dispatcher(tokens)
        or _tokens_execute_internal_python_entrypoint(tokens)
        or _tokens_build_source_docker_image(tokens)
        or _tokens_install_local_source(tokens)
    ):
        return True
    for segment in _shell_segments(tokens)[0]:
        for index, argument in enumerate(segment):
            launcher = _launcher_name(argument)
            if launcher == "ai_dememory.py":
                return True
            if launcher != "ai-dememory":
                continue
            command_index = _metadata_cli_command_index(segment, index + 1, command_names)
            if command_index is not None:
                return True
    return False


def _public_skill_metadata_command_errors(
    values: dict[str, str],
    relative: str,
    command_names: frozenset[str],
    *,
    surface: str,
) -> list[str]:
    """Keep host-visible public metadata out of every command transport."""

    errors: list[str] = []
    for key, value in values.items():
        normalized = " ".join(value.split())
        if key == "name" and normalized.casefold() == "ai-dememory":
            continue
        if _metadata_contains_command_shape(normalized, command_names):
            errors.append(
                f"{relative}: {surface} {key!r} must not include an executable command"
            )
    return errors


def _public_agent_skill_token_command_errors(
    values: dict[str, str],
    relative: str,
    command_names: frozenset[str],
) -> list[str]:
    """Allow the agent skill token itself, but never a CLI continuation of it."""

    value = values.get("default_prompt")
    if value is None:
        return []
    try:
        tokens = _preferred_shell_tokens(value)
    except ValueError:
        return []
    for segment in _shell_segments(tokens)[0]:
        for index, token in enumerate(segment):
            if token.casefold() != "$ai-dememory":
                continue
            if _metadata_cli_command_index(segment, index + 1, command_names) is not None:
                return [
                    f"{relative}: public agent YAML 'default_prompt' must not turn the "
                    "$ai-dememory skill token into a CLI command"
                ]
    return []


def _public_agent_skill_yaml_errors(
    relative: str,
    text: str,
    command_names: frozenset[str],
) -> list[str]:
    """Validate the only supported standalone public agent YAML surface.

    Agent metadata is host-visible, not a command channel. Unknown YAML files
    are rejected instead of accepting another YAML dialect that could change a
    quoted or folded value after this guard has inspected its raw spelling.
    """

    schema = PUBLIC_AGENT_SKILL_YAML_SCHEMAS.get(relative)
    if schema is None:
        return [f"{relative}: public skill YAML is not an explicitly supported schema"]

    lines = text.splitlines()
    errors: list[str] = []
    if not lines or lines[0] != "interface:":
        return [f"{relative}: public agent YAML must begin with the interface mapping"]
    expected_fields = schema["interface"]
    values: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:], start=2):
        if not line:
            errors.append(f"{relative}:{line_number}: public agent YAML must not contain blank lines")
            continue
        match = re.fullmatch(
            r"  (?P<key>[A-Za-z][A-Za-z0-9_-]*):[ \t]+(?P<value>\S.*)", line
        )
        if match is None:
            errors.append(
                f"{relative}:{line_number}: public agent YAML must use a simple "
                "single-line interface scalar"
            )
            continue
        key = match.group("key")
        if key not in expected_fields:
            errors.append(f"{relative}:{line_number}: public agent YAML field {key!r} is not allowed")
            continue
        if key in values:
            errors.append(f"{relative}:{line_number}: public agent YAML field {key!r} is duplicated")
            continue
        value = _public_skill_frontmatter_scalar(
            relative,
            line_number,
            key,
            match.group("value"),
            errors,
            surface="public agent YAML",
            allow_literal_skill_token=key == "default_prompt",
        )
        if value is not None:
            values[key] = value

    for key in expected_fields:
        if key not in values:
            errors.append(f"{relative}: public agent YAML is missing {key!r}")
    return (
        errors
        + _public_skill_metadata_command_errors(
            values,
            relative,
            command_names,
            surface="public agent YAML",
        )
        + _public_agent_skill_token_command_errors(values, relative, command_names)
    )


def _is_explicit_maintainer_source_section(
    text: str,
    line_number: int,
    label: str,
) -> bool:
    """Allow only the reviewed source-diagnostic sections of known user docs."""

    allowed_titles = PENDING_SOURCE_MAINTAINER_SECTION_TITLES.get(label, ())
    if not allowed_titles:
        return False
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        match = re.fullmatch(r"(?P<marks>#{1,6})[ \t]+(?P<title>.*?)[ \t]*#*", line)
        if match is not None:
            headings.append((index, len(match.group("marks")), match.group("title")))

    for index, level, title in headings:
        if title not in allowed_titles or index > line_number:
            continue
        end = next(
            (
                later_index
                for later_index, later_level, _ in headings
                if later_index > index and later_level <= level
            ),
            len(text.splitlines()) + 1,
        )
        if index < line_number < end:
            return True
    return False


@lru_cache(maxsize=128)
def _stable_source_execution_errors(
    text: str,
    label: str,
    allow_explicit_maintainer_sections: bool,
) -> tuple[str, ...]:
    """Cache stable source-route scans across repeated static-site audits."""

    return tuple(
        _pending_source_execution_errors(
            text,
            _STABLE_SOURCE_ROUTE_CACHE_SENTINEL,
            _STABLE_SOURCE_ROUTE_CACHE_SENTINEL,
            label,
            allow_explicit_maintainer_sections=allow_explicit_maintainer_sections,
        )
    )


def _pending_source_execution_errors(
    text: str,
    stable_version: str,
    source_version: str,
    label: str,
    *,
    allow_explicit_maintainer_sections: bool,
) -> list[str]:
    """Keep public user guidance off source-only execution routes.

    Source/published drift tightens release wording, but must never be the only
    protection against a checkout command leaking into a user-facing guide.
    Stable releases therefore enforce the same explicit maintainer-section
    boundary; an unknown future source state remains the caller's release
    contract error rather than an implicit allowance here.
    """

    if stable_version != _STABLE_SOURCE_ROUTE_CACHE_SENTINEL and source_version == stable_version:
        return list(
            _stable_source_execution_errors(
                text,
                label,
                allow_explicit_maintainer_sections,
            )
        )

    if (
        source_version != stable_version
        and _release_pending_contract(stable_version, source_version) is None
    ):
        return []

    errors: list[str] = []
    recognized_source_lines: set[int] = set()
    for line_number, command, _, _ in _executable_command_entries(text):
        try:
            tokens = _preferred_shell_tokens(command)
        except ValueError:
            continue
        route = _source_execution_route(tokens)
        if route is None:
            continue
        recognized_source_lines.add(line_number)
        if allow_explicit_maintainer_sections and _is_explicit_maintainer_source_section(
            text, line_number, label
        ):
            continue
        errors.append(
            f"{label}:{line_number}: public user guidance must not execute a {route}; "
            "use the published compatibility route or move the recipe below an explicit "
            "Maintainer-only/Maintainer: Source Checkout heading"
        )
    errors.extend(
        _dynamic_source_execution_errors(
            text,
            label,
            allow_explicit_maintainer_sections=allow_explicit_maintainer_sections,
            recognized_source_lines=recognized_source_lines,
        )
    )
    return errors


def _mcp_client_smoke_command_errors(text: str, label: str) -> list[str]:
    """Require documented client smokes to bind a vault and source path."""
    errors: list[str] = []
    for line_number, command, _, _ in _executable_command_entries(text):
        parseable_command = MCP_CLIENT_SMOKE_PATH_PLACEHOLDER_RE.sub(
            lambda match: (
                "__ai_dememory_path_"
                + match.group("kind").casefold().replace("-", "_")
                + "__"
            ),
            command,
        )
        try:
            tokens = _preferred_shell_tokens(parseable_command)
        except ValueError:
            continue
        folded = tuple(token.casefold() for token in tokens)
        for command_index, token in enumerate(folded):
            if token != "mcp-client-smoke":
                continue

            root_positions = [
                index
                for index, value in enumerate(folded[:command_index])
                if value == "--root" or value.startswith("--root=")
            ]
            root_is_complete = len(root_positions) == 1
            root_value = ""
            if root_is_complete:
                root_position = root_positions[0]
                root_option = tokens[root_position]
                if root_option.casefold() == "--root":
                    root_is_complete = (
                        root_position + 1 < command_index
                        and bool(tokens[root_position + 1].strip())
                        and not tokens[root_position + 1].startswith("--")
                    )
                    if root_is_complete:
                        root_value = tokens[root_position + 1]
                else:
                    root_value = root_option.partition("=")[2].strip()
                    root_is_complete = bool(root_value)
            if root_is_complete:
                normalized_root = root_value.replace("\\", "/")
                root_is_complete = (
                    normalized_root.startswith(
                        ("/", "~", "__ai_dememory_path_initialized_")
                    )
                    or re.match(r"^[A-Za-z]:/", normalized_root) is not None
                )
            if not root_is_complete:
                errors.append(
                    f"{label}:{line_number}: mcp-client-smoke requires exactly one "
                    "absolute initialized-vault --root before the command; bind a separate vault"
                )

            argument_index = command_index + 1
            while argument_index < len(tokens):
                option = folded[argument_index]
                source_argument: str | None = None
                if option == "--command-arg" and argument_index + 1 < len(tokens):
                    source_argument = tokens[argument_index + 1]
                    argument_index += 1
                elif option.startswith("--command-arg="):
                    source_argument = tokens[argument_index].partition("=")[2]
                if source_argument is not None:
                    normalized = source_argument.replace("\\", "/")
                    if normalized.casefold().endswith("scripts/ai_dememory.py"):
                        anchored = (
                            normalized.startswith(
                                ("/", "~", "__ai_dememory_path_absolute_checkout__/")
                            )
                            or re.match(r"^[A-Za-z]:/", normalized) is not None
                        )
                        if not anchored:
                            errors.append(
                                f"{label}:{line_number}: mcp-client-smoke source launch "
                                "must use an absolute scripts/ai_dememory.py path because "
                                "the child runs from the bound vault"
                            )
                argument_index += 1
    return errors


def audit_public_skill_guides(
    repo_root: Path,
    stable_version: str,
    source_version: str,
) -> list[str]:
    """Audit every checked-in public skill instruction surface.

    Public skills are often copied into an agent without the surrounding
    documentation site, so they cannot rely on site-only release validation.
    Discover text files below each public skill root rather than maintaining a
    partial allowlist; the two first-run guides additionally require commands
    derived from the active stable/pending release contract.
    """

    errors: list[str] = []
    discovered: set[str] = set()
    required_commands = public_skill_guide_required_commands(
        stable_version, source_version
    )
    command_names, command_namespace_errors = _public_skill_cli_command_names()
    errors.extend(command_namespace_errors)
    for relative_root in PUBLIC_SKILL_GUIDE_ROOTS:
        root = repo_root / relative_root
        if not root.is_dir():
            errors.append(f"{relative_root.as_posix()}: public skill guide root is missing")
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in PUBLIC_SKILL_GUIDE_SUFFIXES:
                continue
            relative = path.relative_to(repo_root).as_posix()
            discovered.add(relative)
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"{relative}: public skill guide must be UTF-8 text")
                continue
            if relative.endswith(".md"):
                frontmatter, body, frontmatter_errors = _public_skill_frontmatter(relative, text)
                errors.extend(frontmatter_errors)
                errors.extend(
                    _public_skill_metadata_command_errors(
                        frontmatter,
                        relative,
                        command_names,
                        surface="public skill frontmatter",
                    )
                )
                text = body
            elif path.suffix.casefold() in {".yaml", ".yml"}:
                errors.extend(_public_agent_skill_yaml_errors(relative, text, command_names))
                continue
            elif path.suffix.casefold() == ".json":
                errors.append(
                    f"{relative}: public skill JSON is not an explicitly supported schema"
                )
                continue
            errors.extend(
                _pending_source_execution_errors(
                    text,
                    stable_version,
                    source_version,
                    relative,
                    allow_explicit_maintainer_sections=False,
                )
            )
            errors.extend(
                _stable_command_errors(
                    text,
                    stable_version,
                    relative,
                    source_version=source_version,
                    required_executable_commands=required_commands.get(relative, ()),
                )
            )
    for relative in sorted(required_commands):
        if relative not in discovered:
            errors.append(f"{relative}: required public first-run skill guide is missing")
    return errors


HTML_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
NON_RENDERED_CONTAINER_TAGS = {
    "audio",
    "canvas",
    "datalist",
    "head",
    "iframe",
    "noembed",
    "noframes",
    "noscript",
    "object",
    "script",
    "select",
    "style",
    "template",
    "video",
}
# Stable command validation must cover authored text a reader can see in any
# supported state. Canonical release blocks retain the stricter visibility
# model above; this narrower set excludes only inert document containers.
COMMAND_AUDIT_EXCLUDED_CONTAINER_TAGS = {"head", "script", "style", "template"}
NON_RENDERED_CLASS_NAMES = {"visually-hidden"}
RELEASE_VISIBLE_ANCESTOR_TAGS = {"html", "body", "main", "article", "section", "div"}
VISIBLE_TEXT_BREAK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "code",
    "dd",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


class DocumentParser(HTMLParser):
    """Collect the structural facts needed by the static-site guard."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = ""
        self.title_parts: list[str] = []
        self.in_title = False
        self.main_count = 0
        self.h1_count = 0
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.references: list[tuple[str, str, str]] = []
        self.description = ""
        self.viewport = ""
        self.images_without_alt = 0
        self.inline_styles: list[str] = []
        self.inline_script_count = 0
        self.meta_refresh = False
        self.base_count = 0
        self.in_style = False
        self.style_parts: list[str] = []
        self.release_blocks: dict[str, list[str]] = {}
        self.release_block_texts: dict[str, list[list[str]]] = {}
        self.release_block_violations: list[str] = []
        self.data_labels: list[str] = []
        self.visible_text_parts: list[str] = []
        self.auditable_text_parts: list[str] = []
        self.untracked_auditable_text_parts: list[str] = []
        self._active_release_block: list[str] | None = None
        self._active_release = ""
        self._release_depth = 0
        self._hidden_depth = 0
        self._element_stack: list[tuple[str, bool]] = []
        self._audit_nonrendered_depth = 0
        self._audit_element_stack: list[bool] = []
        self._svg_depth = 0
        self._svg_element_stack: list[bool] = []

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()

    @property
    def visible_text(self) -> str:
        return "".join(self.visible_text_parts)

    @property
    def auditable_text(self) -> str:
        return "".join(self.auditable_text_parts)

    @property
    def untracked_auditable_text(self) -> str:
        return "".join(self.untracked_auditable_text_parts)

    def _append_visible_text(self, data: str) -> None:
        self.visible_text_parts.append(data)
        if self._active_release:
            self.release_blocks[self._active_release].append(data)
            assert self._active_release_block is not None
            self._active_release_block.append(data)

    def _append_auditable_text(self, data: str) -> None:
        self.auditable_text_parts.append(data)
        if not self._active_release:
            self.untracked_auditable_text_parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values: dict[str, str] = {}
        for raw_key, raw_value in attrs:
            key = raw_key.casefold()
            if key.startswith("on"):
                self.release_block_violations.append(
                    f"inline HTML event handler attribute {key!r} is forbidden"
                )
            if key in values:
                self.release_block_violations.append(
                    f"duplicate HTML attribute {key!r} makes visibility ambiguous"
                )
                continue
            values[key] = raw_value or ""
        if tag == "iframe" and "srcdoc" in values:
            self.release_block_violations.append(
                "iframe srcdoc is forbidden because embedded HTML bypasses "
                "command, script, and resource auditing"
            )
        if DECLARATIVE_SHADOW_DOM_ATTRIBUTES.intersection(values):
            self.release_block_violations.append(
                "declarative Shadow DOM attributes are forbidden because they bypass "
                "the static command-surface audit"
            )
        if tag in STATIC_INTERACTIVE_CONTROL_TAGS:
            self.release_block_violations.append(
                f"static interactive <{tag}> controls are forbidden; use the audited local enhancement"
            )
        if tag == "script" and values.get("type", "").strip().casefold() == "module":
            self.release_block_violations.append(
                "module scripts are forbidden because their import graph is not allowlisted"
            )
        if "ping" in values:
            self.release_block_violations.append(
                "HTML ping attribute is forbidden because it can initiate browser requests"
            )
        style = values.get("style", "")
        class_names = {name.casefold() for name in values.get("class", "").split()}
        own_hidden = (
            tag in NON_RENDERED_CONTAINER_TAGS
            or bool(class_names.intersection(NON_RENDERED_CLASS_NAMES))
            or "hidden" in values
            or values.get("aria-hidden", "").strip().casefold() == "true"
            or "popover" in values
            or (tag in {"dialog", "details"} and "open" not in values)
            or re.search(
                r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\b",
                style,
                re.IGNORECASE,
            )
            is not None
        )
        hidden = self._hidden_depth > 0 or own_hidden
        own_audit_nonrendered = tag in COMMAND_AUDIT_EXCLUDED_CONTAINER_TAGS
        audit_nonrendered = self._audit_nonrendered_depth > 0 or own_audit_nonrendered
        is_void = tag in HTML_VOID_TAGS
        local_tag = tag.rsplit(":", 1)[-1]
        in_svg = self._svg_depth > 0 or local_tag == "svg"

        if in_svg:
            if local_tag in SVG_DYNAMIC_CONTENT_TAGS:
                self.release_block_violations.append(
                    f"SVG dynamic <{tag}> element is forbidden"
                )
            for attribute in SVG_URL_PRESENTATION_ATTRIBUTES:
                value = values.get(attribute)
                if value and _contains_unapproved_svg_presentation_resource(value):
                    self.release_block_violations.append(
                        f"SVG URL-bearing presentation attribute {attribute!r} is forbidden"
                    )

        if not is_void:
            self._element_stack.append((tag, own_hidden))
            self._audit_element_stack.append(own_audit_nonrendered)
            own_svg = local_tag == "svg"
            self._svg_element_stack.append(own_svg)
            if own_hidden:
                self._hidden_depth += 1
            if own_audit_nonrendered:
                self._audit_nonrendered_depth += 1
            if own_svg:
                self._svg_depth += 1

        if not hidden and tag in VISIBLE_TEXT_BREAK_TAGS:
            self._append_visible_text("\n")
        if not audit_nonrendered and tag in VISIBLE_TEXT_BREAK_TAGS:
            self._append_auditable_text("\n")

        release_marker = values.get("data-release", "")
        copy_marker = "data-copy-block" in values
        if copy_marker and not release_marker:
            self.release_block_violations.append(
                "copyable command blocks must carry a nonempty data-release marker"
            )
        if self._active_release:
            if release_marker:
                self.release_block_violations.append(
                    f"nested data-release marker {release_marker!r} is not allowed"
                )
            if tag not in {"pre", "code"}:
                self.release_block_violations.append(
                    "release command blocks must not contain nested markup"
                )
            elif tag == "pre" and values != {"tabindex": "0"}:
                self.release_block_violations.append(
                    "release command blocks must use a plain focusable <pre>"
                )
            elif tag == "code" and values:
                self.release_block_violations.append(
                    "release command blocks must use plain <code> content"
                )
            if not is_void:
                self._release_depth += 1
        elif release_marker:
            release_container_is_canonical = (
                tag == "div"
                and class_names == {"code-block"}
                and set(values) == {"class", "data-copy-block", "data-release"}
            )
            ancestors_are_canonical = all(
                ancestor_tag in RELEASE_VISIBLE_ANCESTOR_TAGS
                for ancestor_tag, _ in self._element_stack[:-1]
            )
            if not release_container_is_canonical or not ancestors_are_canonical:
                self.release_block_violations.append(
                    f"data-release marker {release_marker!r} must use the canonical visible code-block container"
                )
            if hidden or is_void:
                self.release_block_violations.append(
                    f"data-release marker {release_marker!r} is attached to non-rendered content"
                )
            elif release_container_is_canonical and ancestors_are_canonical:
                self._active_release = release_marker
                self._release_depth = 1
                self.release_blocks.setdefault(self._active_release, [])
                self._active_release_block = []
                self.release_block_texts.setdefault(self._active_release, []).append(
                    self._active_release_block
                )
        # Closed <details>, aria-hidden, visually-hidden, popover, and noscript
        # content can all become user-reachable. Only parser-only containers are
        # excluded from the command-surface contract.
        if tag == "pre" and not audit_nonrendered:
            if not self._active_release:
                self.release_block_violations.append(
                    "preformatted command blocks must use a canonical tracked data-release command block"
                )
        if tag == "html":
            self.lang = values.get("lang", "")
        elif tag == "title":
            self.in_title = True
        elif tag == "style":
            self.in_style = True
        elif tag == "script" and not values.get("src"):
            self.inline_script_count += 1
        elif tag == "base":
            self.base_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "h1":
            self.h1_count += 1

        element_id = values.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)

        if tag == "meta":
            if values.get("name", "").lower() == "description":
                self.description = values.get("content", "").strip()
            if values.get("name", "").lower() == "viewport":
                self.viewport = values.get("content", "").strip()
            if values.get("http-equiv", "").lower() == "refresh":
                self.meta_refresh = True

        if values.get("style"):
            self.inline_styles.append(values["style"])

        for attribute in URL_REFERENCE_ATTRIBUTES:
            value = values.get(attribute)
            if value:
                reference_tag = (
                    "svg-resource"
                    if in_svg and tag != "a" and attribute in {"href", "xlink:href"}
                    else tag
                )
                self.references.append((reference_tag, attribute, value.strip()))
        for attribute in URL_LIST_REFERENCE_ATTRIBUTES:
            value = values.get(attribute)
            if not value:
                continue
            for candidate in value.split(","):
                resource = candidate.strip().split(maxsplit=1)[0]
                if resource:
                    self.references.append((tag, attribute, resource))

        if tag == "img" and "alt" not in values:
            self.images_without_alt += 1
        if "data-label" in values:
            self.data_labels.append(values["data-label"])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in HTML_VOID_TAGS:
            return
        if not self._element_stack or self._element_stack[-1][0] != tag:
            expected = self._element_stack[-1][0] if self._element_stack else "none"
            self.release_block_violations.append(
                f"mismatched closing tag </{tag}>; expected </{expected}>"
            )
            return

        if tag == "title":
            self.in_title = False
        elif tag == "style":
            self.in_style = False

        if self._hidden_depth == 0 and tag in VISIBLE_TEXT_BREAK_TAGS:
            self._append_visible_text("\n")
        if self._audit_nonrendered_depth == 0 and tag in VISIBLE_TEXT_BREAK_TAGS:
            self._append_auditable_text("\n")

        if self._active_release:
            self._release_depth -= 1
            if self._release_depth == 0:
                self._active_release = ""
                self._active_release_block = None

        _, own_hidden = self._element_stack.pop()
        if own_hidden:
            self._hidden_depth -= 1
        own_audit_nonrendered = self._audit_element_stack.pop()
        if own_audit_nonrendered:
            self._audit_nonrendered_depth -= 1
        own_svg = self._svg_element_stack.pop()
        if own_svg:
            self._svg_depth -= 1

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in HTML_VOID_TAGS:
            self.release_block_violations.append(
                f"self-closing syntax on non-void <{tag.casefold()}> is ambiguous in text/html"
            )

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_style:
            self.style_parts.append(data)
        if self._hidden_depth == 0:
            self._append_visible_text(data)
        if self._audit_nonrendered_depth == 0:
            self._append_auditable_text(data)

    def _reject_auditable_nontext_token(self, token: str) -> None:
        if self._audit_nonrendered_depth:
            return
        if self._active_release:
            self.release_block_violations.append(
                f"release command blocks must not contain {token}"
            )
        else:
            self.release_block_violations.append(
                f"{token} are forbidden in auditable site content"
            )

    def handle_comment(self, data: str) -> None:
        self._reject_auditable_nontext_token("HTML comments")

    def handle_decl(self, decl: str) -> None:
        if decl.strip().casefold() == "doctype html" and not self._element_stack:
            return
        self._reject_auditable_nontext_token("HTML declarations")

    def unknown_decl(self, data: str) -> None:
        self._reject_auditable_nontext_token("unknown HTML declarations")

    def handle_pi(self, data: str) -> None:
        self._reject_auditable_nontext_token("processing instructions")

    def close(self) -> None:
        super().close()
        if self._element_stack:
            self.release_block_violations.append(
                "unclosed HTML elements make visibility ambiguous: "
                + ", ".join(tag for tag, _ in self._element_stack[-5:])
            )


def _parse_page(path: Path) -> DocumentParser:
    parser = DocumentParser()
    text = path.read_text(encoding="utf-8")
    parser.feed(text)
    parser.close()
    for match in SVG_DYNAMIC_QNAME_ELEMENT_RE.finditer(text):
        name = match.group("name")
        if not name.isascii():
            parser.release_block_violations.append(
                f"SVG dynamic QName <{name}> is forbidden because non-ASCII namespace parsing is unsupported"
            )
    return parser


def _is_automatic_reference(tag: str, attribute: str) -> bool:
    return (
        attribute in AUTOMATIC_RESOURCE_ATTRIBUTES
        or (
            tag in AUTOMATIC_HREF_REFERENCE_TAGS
            and attribute in {"href", "xlink:href"}
        )
        or (tag == "svg-resource" and attribute in {"href", "xlink:href"})
    )


def _requires_local_active_asset_allowlist(tag: str, attribute: str, target: Path) -> bool:
    """Keep every browser-loaded active local resource in the audited asset set."""
    return _is_automatic_reference(tag, attribute) and (
        tag in LOCAL_ACTIVE_ASSET_TAGS
        or target.suffix.casefold() in LOCAL_ACTIVE_ASSET_SUFFIXES
    )


def _resolve_local_reference(site_root: Path, page: Path, value: str) -> tuple[Path, str]:
    parts = urlsplit(value)
    relative = unquote(parts.path)
    if relative.startswith("/"):
        raise ValueError("root-relative URL is not portable under a project Pages path")

    target = page if not relative else page.parent / relative
    if not relative or relative.endswith("/"):
        target = target / "index.html" if relative else page
    target = target.resolve()
    try:
        target.relative_to(site_root.resolve())
    except ValueError as exc:
        raise ValueError("reference escapes site/") from exc
    return target, unquote(parts.fragment)


_SAFE_NUMERIC_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
}


def _safe_number(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_number(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_NUMERIC_OPERATORS:
        return _SAFE_NUMERIC_OPERATORS[type(node.op)](_safe_number(node.left), _safe_number(node.right))
    raise ValueError(f"unsupported numeric expression: {ast.dump(node, include_attributes=False)}")


def _resource_contract(path: Path) -> tuple[str, tuple[str, ...], dict[str, dict[str, object]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    default_intensity = ""
    model_policies: tuple[str, ...] = ()
    profiles: dict[str, dict[str, object]] = {}

    for statement in tree.body:
        target_name = ""
        value: ast.AST | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target_name = getattr(statement.targets[0], "id", "")
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target_name = getattr(statement.target, "id", "")
            value = statement.value

        if target_name == "DEFAULT_INTENSITY" and isinstance(value, ast.Constant):
            default_intensity = str(value.value)
        elif target_name == "MODEL_POLICIES" and isinstance(value, ast.Dict):
            model_policies = tuple(str(ast.literal_eval(key)) for key in value.keys if key is not None)
        elif target_name == "RESOURCE_PROFILES" and isinstance(value, ast.Dict):
            for key_node, call_node in zip(value.keys, value.values):
                if key_node is None or not isinstance(call_node, ast.Call):
                    continue
                name = str(ast.literal_eval(key_node))
                fields: dict[str, object] = {}
                for keyword in call_node.keywords:
                    if keyword.arg in {
                        "recall_per_turn",
                        "recall_budget_tokens",
                        "daily_enabled",
                        "weekly_enabled",
                        "provider_file_limit",
                        "provider_max_file_bytes",
                        "provider_scan_entries",
                        "mcp_idle_timeout_seconds",
                    }:
                        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, bool):
                            fields[keyword.arg] = keyword.value.value
                        else:
                            fields[keyword.arg] = _safe_number(keyword.value)
                profiles[name] = fields

    if not default_intensity or not model_policies or not profiles:
        raise ValueError("resource policy contract could not be extracted")
    return default_intensity, model_policies, profiles


def _audit_resource_profiles(repo_root: Path, site_root: Path, errors: list[str]) -> None:
    try:
        default_intensity, model_policies, profiles = _resource_contract(repo_root / "scripts/resource_policy.py")
    except (OSError, SyntaxError, ValueError) as exc:
        errors.append(f"scripts/resource_policy.py: cannot derive documentation contract: {exc}")
        return

    install = (site_root / "install/index.html").read_text(encoding="utf-8")
    architecture = (site_root / "architecture/index.html").read_text(encoding="utf-8")
    for name, profile in profiles.items():
        recall = (
            f"Up to {int(profile['recall_budget_tokens']):,} tokens"
            if profile["recall_per_turn"]
            else "Manual only"
        )
        cadence = (
            "Daily + weekly"
            if profile["daily_enabled"] and profile["weekly_enabled"]
            else "Weekly"
        )
        expected = (
            name,
            recall,
            cadence,
            f"{int(profile['provider_file_limit'])} / run",
            f"{int(profile['provider_max_file_bytes']) // 1024} KiB / {int(profile['provider_scan_entries']):,}",
        )
        for claim in expected:
            if claim not in install:
                errors.append(f"install/index.html: resource profile {name!r} is missing source-derived claim {claim!r}")

    if f'<tr class="recommended">\n                  <th scope="row">{default_intensity} ' not in install:
        errors.append(f"install/index.html: source default intensity {default_intensity!r} is not marked recommended")
    for policy in model_policies:
        if f"<strong>{policy}</strong>" not in install:
            errors.append(f"install/index.html: model policy {policy!r} is missing")

    idle_claim = " / ".join(f"{int(profile['mcp_idle_timeout_seconds']):,}" for profile in profiles.values())
    if f"{idle_claim} seconds" not in architecture:
        errors.append(f"architecture/index.html: idle lease sequence must match source: {idle_claim} seconds")


def _audit_claims(repo_root: Path, site_root: Path, errors: list[str]) -> None:
    metadata = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    source_version = str(project["version"])
    requires_python = str(project["requires-python"])
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    stable_match = re.search(
        r"Current (?:release line|stable release): `ai-dememory` "
        r"([0-9]+(?:\.[0-9]+){2})",
        readme,
    )
    if not stable_match:
        errors.append("README.md: current release line is not machine-readable")
        return
    stable_version = stable_match.group(1)
    errors.extend(_release_contract_errors(stable_version, source_version))
    pending_contract = _release_pending_contract(stable_version, source_version)
    stable_contract = STABLE_RELEASE_CONTRACTS.get(stable_version)
    if stable_contract is not None:
        for relative in STABLE_INSTALL_DOCS:
            text = (repo_root / relative).read_text(encoding="utf-8")
            errors.extend(
                _stable_command_errors(
                    text,
                    stable_version,
                    relative,
                    source_version=source_version,
                    required_executable_commands=STABLE_DOC_REQUIRED_COMMANDS.get(
                        relative, ()
                    ),
                    require_explicit_mcp_root=relative in EXPLICIT_ROOT_MCP_DOCS,
                )
            )
        for relative in PUBLIC_SOURCE_ROUTE_DOCS:
            text = (repo_root / relative).read_text(encoding="utf-8")
            errors.extend(
                _pending_source_execution_errors(
                    text,
                    stable_version,
                    source_version,
                    relative,
                    allow_explicit_maintainer_sections=True,
                )
            )
        errors.extend(
            audit_public_skill_guides(repo_root, stable_version, source_version)
        )
        for relative in MCP_CLIENT_SMOKE_GUIDES:
            text = (repo_root / relative).read_text(encoding="utf-8")
            errors.extend(_mcp_client_smoke_command_errors(text, relative))
    development_status = (repo_root / "docs" / "development-status.md").read_text(
        encoding="utf-8"
    )
    normalized_status = development_status.casefold()
    for prerelease_version, prerelease_contract in ACTIVE_PRERELEASE_CONTRACTS.items():
        for evidence in prerelease_contract["status_evidence"]:
            if evidence not in development_status:
                errors.append(
                    "docs/development-status.md: current prerelease "
                    f"{prerelease_version} is missing release evidence {evidence!r}"
                )
        if re.search(
            rf"\b{re.escape(prerelease_version)}\b.{{0,240}}\b(?:untagged|unpublished)\b",
            normalized_status,
            flags=re.DOTALL,
        ):
            errors.append(
                "docs/development-status.md: current prerelease "
                f"{prerelease_version} is still described as untagged or unpublished"
            )
    for prerelease_version, prerelease_contract in HISTORICAL_PRERELEASE_CONTRACTS.items():
        for evidence in prerelease_contract["status_evidence"]:
            if evidence not in development_status:
                errors.append(
                    "docs/development-status.md: historical prerelease "
                    f"{prerelease_version} is missing release evidence {evidence!r}"
                )
        marker = str(prerelease_contract["status_marker"])
        if marker not in normalized_status:
            errors.append(
                "docs/development-status.md: historical prerelease "
                f"{prerelease_version} must be explicitly labelled {marker!r}"
            )
    scope_markers = release_scope_markers(stable_version, source_version)
    for relative in RELEASE_SCOPE_DOCS:
        # Markdown prose may wrap a release sentence across physical lines.
        # Compare its rendered-word shape instead of making the public contract
        # depend on line width.
        scope_text = " ".join(
            (repo_root / relative).read_text(encoding="utf-8").lower().split()
        ).replace("`", "")
        for marker in scope_markers:
            if marker.casefold() not in scope_text:
                errors.append(f"{relative}: release capability scope is missing {marker!r}")

    install = (site_root / "install/index.html").read_text(encoding="utf-8")
    release_lens = site_release_lens(stable_version, source_version)
    install_expectations = [
        (f"Stable release: {stable_version}", "release line version"),
        (release_lens, "source version"),
        (f"Python {requires_python.removeprefix('>=')}+", "Python requirement"),
        ("pipx install --force ai-dememory", "stable upgrade command"),
        (
            "ai-dememory init ~/code/my-memory --wizard",
            "wizard-first vault command",
        ),
        (
            "ai-dememory --root ~/code/my-memory mcp-config --client codex",
            "optional legacy MCP client command",
        ),
        ("complete historical MCP surface", "admin compatibility warning"),
    ]
    # An active TestPyPI route is visible only while the checked-out source is
    # not the documented stable line. A future source candidate is a separate
    # status claim, never an implied package installation route.
    for prerelease_contract in ACTIVE_PRERELEASE_CONTRACTS.values():
        install_expectations.extend(
            [
                (prerelease_contract["install_marker"], "prerelease availability marker"),
                (prerelease_contract["package_command"], "exact prerelease install command"),
                (
                    "Use an isolated virtual environment for this TestPyPI evaluation",
                    "prerelease isolation guidance",
                ),
                (
                    "ai-dememory init ~/code/my-memory --wizard",
                    "prerelease wizard-first vault command",
                ),
            ]
        )
    if pending_contract is not None:
        install_expectations.extend(
            (marker, "release-pending source truth marker")
            for marker in pending_contract["scope_markers"]
        )
    source_is_unreleased_candidate = (
        source_version != stable_version
        and pending_contract is None
        and source_version not in ACTIVE_PRERELEASE_CONTRACTS
    )
    if source_is_unreleased_candidate:
        install_expectations.extend(
            [
                (
                    "not installable from a package index until it is tagged and published",
                    "unpublished candidate availability warning",
                ),
            ]
        )
    for expected, label in install_expectations:
        if expected not in install:
            errors.append(f"install/index.html: stale or missing {label}: {expected!r}")

    contract = STABLE_RELEASE_CONTRACTS.get(stable_version)
    if contract is None:
        errors.append(f"docs site guard: add an audited stable release contract for {stable_version}")
    else:
        release_blocks: dict[str, list[str]] = {}
        release_block_texts: dict[str, list[str]] = {}
        published_label = _published_release_label(stable_version, source_version)
        for page in site_root.rglob("*.html"):
            document = _parse_page(page)
            page_label = page.relative_to(site_root).as_posix()
            errors.extend(
                f"site/{page_label}: {violation}"
                for violation in document.release_block_violations
            )
            errors.extend(
                _stable_command_errors(
                    document.auditable_text,
                    stable_version,
                    f"site/{page_label}",
                    source_version=source_version,
                )
            )
            errors.extend(
                _untracked_site_command_errors(
                    document.untracked_auditable_text,
                    f"site/{page_label}",
                    allowed_package_commands=(
                        {"pipx install ai-dememory"}
                        if page_label in CONTEXTUAL_INSTALLER_PAGES
                        else set()
                    ),
                )
            )
            for release, parts in document.release_blocks.items():
                release_blocks.setdefault(release, []).extend(parts)
            for release, blocks in document.release_block_texts.items():
                release_block_texts.setdefault(release, []).extend(
                    "".join(block) for block in blocks
                )
            if pending_contract is not None and page_label in {"index.html", "install/index.html"}:
                page_text = " ".join(document.auditable_text.casefold().split())
                for marker in release_scope_markers(stable_version, source_version):
                    normalized_marker = " ".join(marker.casefold().split())
                    if normalized_marker not in page_text:
                        errors.append(
                            f"site/{page_label}: release-pending source truth marker is missing "
                            f"{marker!r}"
                        )
            page_published_blocks = [
                "".join(block)
                for block in document.release_block_texts.get(
                    published_label, []
                )
            ]
            page_published_text = "\n".join(page_published_blocks)
            required_page_commands = SITE_PAGE_REQUIRED_COMMANDS.get(page_label, ())
            if required_page_commands:
                errors.extend(
                    _stable_command_errors(
                        page_published_text,
                        stable_version,
                        f"site/{page_label}",
                        source_version=source_version,
                        required_executable_commands=required_page_commands,
                    )
                )
        known_release_labels = {
            published_label,
            *(
                f"source-{prerelease_version}"
                for prerelease_version in ACTIVE_PRERELEASE_CONTRACTS
            ),
        }
        for release in sorted(release_block_texts):
            if release not in known_release_labels:
                errors.append(
                    f"site: copyable command block uses an unknown release marker {release!r}"
                )
        published_text = "\n".join(release_blocks.get(published_label, []))
        published_commands = {
            command
            for block in release_block_texts.get(published_label, [])
            for command in _executable_command_lines(block)
        }
        if not published_text:
            errors.append(f"site: no command block is labelled {published_label!r}")
        for command in contract["required"]:
            if command not in published_commands:
                errors.append(f"site: published {stable_version} command block is missing {command!r}")
        for command in REQUIRED_COMMANDS:
            if command not in published_commands:
                errors.append(f"site: required first-run command is missing: {command!r}")
        for marker in contract["source_only"]:
            if marker in published_commands:
                errors.append(f"site: published {stable_version} command block contains source-only marker {marker!r}")
        for block in release_block_texts.get(published_label, []):
            literal_commands = tuple(
                line.strip() for line in block.splitlines() if line.strip()
            )
            unapproved_commands = tuple(
                command
                for command in literal_commands
                if command not in contract["copyable"]
            )
            if unapproved_commands:
                errors.append(
                    f"site: published {stable_version} command block contains an unapproved literal command: "
                    f"{unapproved_commands!r}"
                )
            errors.extend(_stable_command_errors(block, stable_version, "site published block"))

        # The one current, immutable TestPyPI prerelease owns a copyable
        # command block. An untagged source candidate cannot add another one.
        for prerelease_version, prerelease_contract in ACTIVE_PRERELEASE_CONTRACTS.items():
            prerelease_label = f"source-{prerelease_version}"
            prerelease_text = "\n".join(release_blocks.get(prerelease_label, []))
            prerelease_commands = {
                command
                for block in release_block_texts.get(prerelease_label, [])
                for command in _executable_command_lines(block)
            }
            if not prerelease_text:
                errors.append(
                    f"site: no command block is labelled active prerelease {prerelease_label!r}"
                )
            required_prerelease_commands = (
                prerelease_contract["package_command"],
                *ACTIVE_PRERELEASE_REQUIRED_COMMANDS,
            )
            for command in required_prerelease_commands:
                if command not in prerelease_commands:
                    errors.append(
                        f"site: active prerelease {prerelease_version} command block is missing {command!r}"
                    )
            for block in release_block_texts.get(prerelease_label, []):
                literal_commands = tuple(
                    line.strip() for line in block.splitlines() if line.strip()
                )
                if literal_commands != required_prerelease_commands:
                    errors.append(
                        f"site: active prerelease {prerelease_version} command block must contain only "
                        f"the approved prerelease install and wizard commands: {literal_commands!r}"
                    )
            for marker in ACTIVE_PRERELEASE_REQUIRED_COMMANDS:
                if marker not in prerelease_text:
                    errors.append(
                        f"site: active prerelease {prerelease_version} command blocks are missing {marker!r}"
                    )

    policy_path = repo_root / "SECURITY.md"
    policy_exists = policy_path.exists()
    pending_claim = "does not yet contain an approved <code>SECURITY.md</code> policy"
    security = (site_root / "security/index.html").read_text(encoding="utf-8")
    non_loopback_tls_marker = (
        "Any non-loopback bind requires an API key plus both "
        "<code>--tls-cert</code> and <code>--tls-key</code>"
    )
    if non_loopback_tls_marker not in security:
        errors.append(
            "security/index.html: non-loopback API guidance must require an API key "
            "and both --tls-cert and --tls-key"
        )
    if policy_exists and pending_claim in security:
        errors.append("security/index.html: reporting status is stale because SECURITY.md now exists")
    if policy_exists:
        policy = policy_path.read_text(encoding="utf-8")
        reporting_url = "https://github.com/GonzaloTorreras/ai-dememory/security/advisories/new"
        policy_url = "https://github.com/GonzaloTorreras/ai-dememory/blob/main/SECURITY.md"
        for label, marker in (
            ("SECURITY.md", reporting_url),
            ("security/index.html", reporting_url),
            ("security/index.html", policy_url),
        ):
            content = policy if label == "SECURITY.md" else security
            if marker not in content:
                errors.append(f"{label}: approved security reporting route is missing {marker!r}")
    if not policy_exists and pending_claim not in security:
        errors.append("security/index.html: must state that no approved SECURITY.md exists")

    _audit_resource_profiles(repo_root, site_root, errors)


def audit_site(repo_root: Path = REPO_ROOT, site_root: Path | None = None) -> list[str]:
    """Return deterministic validation errors for the static documentation site."""

    repo_root = repo_root.resolve()
    site_root = (site_root or repo_root / "site").resolve()
    errors: list[str] = []

    for relative in (*REQUIRED_PAGES, ".nojekyll", "README.md", "assets/site.css", "assets/site.js"):
        if not (site_root / relative).is_file():
            errors.append(f"site/{relative}: required file is missing")
    for relative in SOURCE_PATHS:
        if not (repo_root / relative).is_file():
            errors.append(f"{relative}: documentation source-map target is missing")
    if errors:
        return sorted(errors)

    pages = sorted(site_root.rglob("*.html"))
    parsed = {page.resolve(): _parse_page(page) for page in pages}

    for page, document in parsed.items():
        label = page.relative_to(site_root).as_posix()
        if document.lang != "en":
            errors.append(f"{label}: html lang must be 'en'")
        if not document.title:
            errors.append(f"{label}: title is missing")
        if not document.description:
            errors.append(f"{label}: meta description is missing")
        if "width=device-width" not in document.viewport:
            errors.append(f"{label}: responsive viewport is missing")
        if document.main_count != 1:
            errors.append(f"{label}: expected one main landmark, found {document.main_count}")
        if document.h1_count != 1:
            errors.append(f"{label}: expected one h1, found {document.h1_count}")
        if document.duplicate_ids:
            errors.append(f"{label}: duplicate ids: {sorted(document.duplicate_ids)}")
        if document.images_without_alt:
            errors.append(f"{label}: {document.images_without_alt} img element(s) lack alt")
        for data_label in document.data_labels:
            if data_label not in ALLOWED_CSS_DATA_LABELS:
                errors.append(
                    f"{label}: data-label renders through reviewed CSS and is not allowlisted: {data_label!r}"
                )
        if document.inline_script_count:
            errors.append(f"{label}: inline scripts are forbidden; use the audited local enhancement")
        if document.meta_refresh:
            errors.append(f"{label}: meta refresh is forbidden")
        if document.base_count:
            errors.append(f"{label}: base elements are forbidden because they change relative trust boundaries")

        inline_css = "\n".join((*document.inline_styles, *document.style_parts))
        if _contains_css_resource_reference(inline_css):
            errors.append(f"{label}: inline CSS imports/resources are forbidden")
        if _contains_css_comment_token(inline_css):
            errors.append(f"{label}: CSS comments are forbidden in the audited static site")
        if _contains_unapproved_css_generated_content(inline_css):
            errors.append(f"{label}: CSS generated content is not allowlisted")

        for tag, attribute, value in document.references:
            parts = urlsplit(value)
            if parts.scheme or parts.netloc:
                if _is_automatic_reference(tag, attribute):
                    errors.append(f"{label}: automatic external resource is forbidden: {value}")
                elif parts.scheme != "https" or parts.hostname not in ALLOWED_EXTERNAL_HOSTS:
                    errors.append(f"{label}: external link must use approved HTTPS host: {value}")
                continue
            try:
                target, fragment = _resolve_local_reference(site_root, page, value)
            except ValueError as exc:
                errors.append(f"{label}: invalid local reference {value!r}: {exc}")
                continue
            if not target.is_file():
                errors.append(f"{label}: broken local reference {value!r}")
                continue
            if _requires_local_active_asset_allowlist(tag, attribute, target):
                relative_target = target.relative_to(site_root).as_posix()
                if relative_target not in ALLOWED_LOCAL_ACTIVE_ASSETS:
                    errors.append(
                        f"{label}: local active asset is not allowlisted: {value}"
                    )
            if fragment:
                target_document = parsed.get(target.resolve())
                if target_document is None:
                    errors.append(f"{label}: fragment points to non-HTML target: {value!r}")
                elif fragment not in target_document.ids:
                    errors.append(f"{label}: missing fragment target {value!r}")

    css = (site_root / "assets/site.css").read_text(encoding="utf-8")
    if _contains_css_resource_reference(css):
        errors.append("assets/site.css: resource imports or references are forbidden")
    if _contains_css_comment_token(css):
        errors.append("assets/site.css: CSS comments are forbidden in the audited static site")
    if _contains_unapproved_css_generated_content(css):
        errors.append("assets/site.css: CSS generated content is not allowlisted")
    if "prefers-reduced-motion: reduce" not in css:
        errors.append("assets/site.css: reduced-motion treatment is missing")
    if "forced-colors: active" not in css:
        errors.append("assets/site.css: forced-colors treatment is missing")

    javascript = (site_root / "assets/site.js").read_bytes()
    actual_javascript_sha256 = hashlib.sha256(javascript).hexdigest()
    if actual_javascript_sha256 != SITE_JAVASCRIPT_SHA256:
        errors.append(
            "assets/site.js: content does not match the approved reviewed fingerprint; "
            "review the asset and update SITE_JAVASCRIPT_SHA256 deliberately"
        )
    if len(javascript) > JAVASCRIPT_BUDGET:
        errors.append(f"assets/site.js: exceeds {JAVASCRIPT_BUDGET}-byte budget")

    favicon = (site_root / "assets/favicon.svg").read_text(encoding="utf-8")
    if (
        SVG_ACTIVE_CONTENT_RE.search(favicon) is not None
        or _contains_css_resource_reference(favicon)
    ):
        errors.append("assets/favicon.svg: active SVG content or references are forbidden")

    home_assets = [
        site_root / "index.html",
        site_root / "assets/site.css",
        site_root / "assets/site.js",
    ]
    home_bytes = sum(path.stat().st_size for path in home_assets)
    if home_bytes > PRODUCTION_ASSET_BUDGET:
        errors.append(f"home production assets: {home_bytes} bytes exceeds {PRODUCTION_ASSET_BUDGET}")

    for extension in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif"):
        for image in site_root.rglob(extension):
            if image.stat().st_size > RASTER_BUDGET:
                errors.append(f"{image.relative_to(site_root).as_posix()}: exceeds raster budget")

    _audit_claims(repo_root, site_root, errors)
    return sorted(set(errors))


def main() -> int:
    errors = audit_site()
    if errors:
        print("Documentation site guard failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Documentation site guard passed: structure, links, release boundary, "
        "source-derived profiles, security status, and budgets are valid."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
