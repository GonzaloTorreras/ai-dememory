#!/usr/bin/env python3
"""Validate the dependency-free documentation site and its source contracts."""

from __future__ import annotations

import re
import sys
import tomllib
import ast
import operator
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "site"

REQUIRED_PAGES = (
    "index.html",
    "install/index.html",
    "architecture/index.html",
    "security/index.html",
    "404.html",
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
    "docs/schema.md",
    "docs/adr/0254-python-node-runtime-boundary.md",
    "docs/adr/0257-bounded-autonomy-and-resource-profiles.md",
    "scripts/resource_policy.py",
)

REQUIRED_COMMANDS = (
    "pipx install ai-dememory",
    "ai-dememory init ~/code/my-memory",
    "ai-dememory doctor",
    "ai-dememory setup wizard",
    "ai-dememory mcp-config --client codex",
    "ai-dememory mcp-client-smoke",
)

STABLE_RELEASE_CONTRACTS = {
    "2.0.0": {
        "required": (
            "pipx install ai-dememory",
            "ai-dememory init ~/code/my-memory",
            "ai-dememory doctor",
            "ai-dememory index",
            "ai-dememory setup plan --json",
            "ai-dememory setup health --json",
            "ai-dememory mcp-config --client codex",
            "ai-dememory mcp-client-smoke",
        ),
        "source_only": (
            "ai-dememory setup wizard",
            "--intensity",
            "--model-policy",
            "--idle-timeout-seconds",
        ),
    }
}

RELEASE_SCOPE_DOCS = (
    "README.md",
    "docs/install.md",
    "docs/local-mcp.md",
    "docs/mcp-client-config.md",
    "docs/codex-plugin.md",
    "docs/operations.md",
)

ALLOWED_EXTERNAL_HOSTS = {"github.com"}
PRODUCTION_ASSET_BUDGET = 250 * 1024
JAVASCRIPT_BUDGET = 8 * 1024
RASTER_BUDGET = 120 * 1024


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
        self._active_release = ""
        self._release_depth = 0

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if self._active_release:
            self._release_depth += 1
        elif values.get("data-release"):
            self._active_release = values["data-release"]
            self._release_depth = 1
            self.release_blocks.setdefault(self._active_release, [])
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

        for attribute in ("href", "src", "poster", "data"):
            value = values.get(attribute)
            if value:
                self.references.append((tag, attribute, value.strip()))
        if values.get("srcset"):
            for candidate in values["srcset"].split(","):
                resource = candidate.strip().split(maxsplit=1)[0]
                if resource:
                    self.references.append((tag, "srcset", resource))

        if tag == "img" and "alt" not in values:
            self.images_without_alt += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "style":
            self.in_style = False
        if self._active_release:
            self._release_depth -= 1
            if self._release_depth == 0:
                self._active_release = ""

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_style:
            self.style_parts.append(data)
        if self._active_release:
            self.release_blocks[self._active_release].append(data)


def _parse_page(path: Path) -> DocumentParser:
    parser = DocumentParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def _is_automatic_reference(tag: str, attribute: str) -> bool:
    return attribute in {"src", "srcset", "poster", "data"} or (tag == "link" and attribute == "href")


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
    stable_match = re.search(r"Published stable release: `ai-dememory` ([0-9]+(?:\.[0-9]+){2})", readme)
    if not stable_match:
        errors.append("README.md: published stable version is not machine-readable")
        return
    stable_version = stable_match.group(1)
    for relative in RELEASE_SCOPE_DOCS:
        scope_text = (repo_root / relative).read_text(encoding="utf-8").lower()
        for marker in (f"stable {stable_version}", f"unreleased {source_version}"):
            if marker not in scope_text:
                errors.append(f"{relative}: release capability scope is missing {marker!r}")

    install = (site_root / "install/index.html").read_text(encoding="utf-8")
    for expected, label in (
        (f"Stable package: {stable_version}", "stable package version"),
        (f"Source line: {source_version}, unreleased", "source version"),
        (f"Python {requires_python.removeprefix('>=')}+", "Python requirement"),
    ):
        if expected not in install:
            errors.append(f"install/index.html: stale or missing {label}: {expected!r}")

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in site_root.rglob("*.html")
    )
    for command in REQUIRED_COMMANDS:
        if command not in combined:
            errors.append(f"site: required first-run command is missing: {command!r}")

    contract = STABLE_RELEASE_CONTRACTS.get(stable_version)
    if contract is None:
        errors.append(f"docs site guard: add an audited stable release contract for {stable_version}")
    else:
        release_blocks: dict[str, list[str]] = {}
        for page in site_root.rglob("*.html"):
            document = _parse_page(page)
            for release, parts in document.release_blocks.items():
                release_blocks.setdefault(release, []).extend(parts)
        stable_label = f"stable-{stable_version}"
        stable_text = "\n".join(release_blocks.get(stable_label, []))
        if not stable_text:
            errors.append(f"site: no command block is labelled {stable_label!r}")
        for command in contract["required"]:
            if command not in stable_text:
                errors.append(f"site: stable {stable_version} command block is missing {command!r}")
        for marker in contract["source_only"]:
            if marker in stable_text:
                errors.append(f"site: stable {stable_version} command block contains source-only marker {marker!r}")

        source_label = f"source-{source_version}"
        source_text = "\n".join(release_blocks.get(source_label, []))
        for marker in (
            "pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git",
            "ai-dememory setup wizard",
            "--intensity",
            "--model-policy",
        ):
            if marker not in source_text:
                errors.append(f"site: source {source_version} command blocks are missing {marker!r}")

    policy_exists = (repo_root / "SECURITY.md").exists()
    pending_claim = "does not yet contain an approved <code>SECURITY.md</code> policy"
    security = (site_root / "security/index.html").read_text(encoding="utf-8")
    if policy_exists and pending_claim in security:
        errors.append("security/index.html: reporting status is stale because SECURITY.md now exists")
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
        if document.inline_script_count:
            errors.append(f"{label}: inline scripts are forbidden; use the audited local enhancement")
        if document.meta_refresh:
            errors.append(f"{label}: meta refresh is forbidden")
        if document.base_count:
            errors.append(f"{label}: base elements are forbidden because they change relative trust boundaries")

        inline_css = "\n".join((*document.inline_styles, *document.style_parts))
        if re.search(r"@import|url\s*\(", inline_css, re.IGNORECASE):
            errors.append(f"{label}: inline CSS imports/resources are forbidden")

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
            if fragment:
                target_document = parsed.get(target.resolve())
                if target_document is None:
                    errors.append(f"{label}: fragment points to non-HTML target: {value!r}")
                elif fragment not in target_document.ids:
                    errors.append(f"{label}: missing fragment target {value!r}")

    css = (site_root / "assets/site.css").read_text(encoding="utf-8")
    if re.search(r"@import|url\s*\(\s*['\"]?(?:https?:)?//", css, re.IGNORECASE):
        errors.append("assets/site.css: external imports or resources are forbidden")
    if "prefers-reduced-motion: reduce" not in css:
        errors.append("assets/site.css: reduced-motion treatment is missing")
    if "forced-colors: active" not in css:
        errors.append("assets/site.css: forced-colors treatment is missing")

    javascript = (site_root / "assets/site.js").read_text(encoding="utf-8")
    for primitive in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon"):
        if primitive in javascript:
            errors.append(f"assets/site.js: network primitive is forbidden: {primitive}")
    if re.search(r"https?://|['\"]//", javascript, re.IGNORECASE):
        errors.append("assets/site.js: external URL literal is forbidden")
    if len(javascript.encode("utf-8")) > JAVASCRIPT_BUDGET:
        errors.append(f"assets/site.js: exceeds {JAVASCRIPT_BUDGET}-byte budget")

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
