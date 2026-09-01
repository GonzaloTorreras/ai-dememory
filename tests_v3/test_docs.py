from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE = (
    ROOT / "README.md",
    ROOT / "README-PYPI.md",
    ROOT / "DEVELOPMENT.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "modules.md",
    ROOT / "docs" / "roadmap.md",
    ROOT / "docs" / "development-status.md",
)


class ActiveDocumentationTests(unittest.TestCase):
    def test_relative_links_exist(self) -> None:
        pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        missing: list[str] = []
        for document in ACTIVE:
            text = document.read_text(encoding="utf-8")
            for target in pattern.findall(text):
                if target.startswith(("http://", "https://", "#")):
                    continue
                relative = target.split("#", 1)[0]
                if relative and not (document.parent / relative).resolve().exists():
                    missing.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [])

    def test_active_user_docs_do_not_teach_v2_commands(self) -> None:
        forbidden = (
            "scripts/ai_dememory.py",
            "scripts\\ai_dememory.py",
            "--root <vault",
            "setup wizard",
            "mcp-config",
            "74 mcp",
        )
        offenders: list[str] = []
        for document in ACTIVE:
            text = document.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                if phrase in text:
                    offenders.append(f"{document.relative_to(ROOT)}: {phrase}")
        self.assertEqual(offenders, [])

    def test_active_workflows_do_not_execute_v2_runtime(self) -> None:
        forbidden = (
            "python scripts/",
            "python3 scripts/",
            "compileall -q scripts",
            "mcp/server",
            "unittest discover -s tests -t .",
        )
        offenders: list[str] = []
        for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            for phrase in forbidden:
                if phrase in text:
                    offenders.append(f"{workflow.name}: {phrase}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
