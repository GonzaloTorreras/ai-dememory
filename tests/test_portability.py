from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from memorylib import contained_relative_path, repo_relative_path, safe_write_text  # noqa: E402
from hook_event import (  # noqa: E402
    archive_reviewed_hook_captures,
    capture_hook_event,
    hook_capture_summary,
    review_hook_capture,
)
from review_memory import (  # noqa: E402
    archive_review_recommendations,
    capture_review_recommendation,
    record_review_recommendation_outcome,
    review_recommendations,
)
from working_memory import reject_working_path_symlink_components  # noqa: E402


class PathPortabilityTests(unittest.TestCase):
    def test_relative_path_normalizes_root_and_candidate_consistently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "inbox" / "candidate.md"
            candidate.parent.mkdir()
            candidate.write_text("candidate\n", encoding="utf-8")

            self.assertEqual(contained_relative_path(candidate, root), Path("inbox/candidate.md"))
            self.assertEqual(repo_relative_path(candidate, root), "inbox/candidate.md")

    def test_root_alias_does_not_mix_logical_and_resolved_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = base / "actual"
            actual.mkdir()
            alias = base / "alias"
            try:
                os.symlink(actual, alias, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            candidate = alias / "review" / "item.md"
            candidate.parent.mkdir()
            candidate.write_text("item\n", encoding="utf-8")

            self.assertNotEqual(candidate.absolute(), candidate.resolve())
            self.assertEqual(contained_relative_path(candidate, alias), Path("review/item.md"))

    def test_safe_write_anchors_root_alias_to_one_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first = base / "first"
            second = base / "second"
            first.mkdir()
            second.mkdir()
            alias = base / "alias"
            try:
                os.symlink(first, alias, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            original_resolve = Path.resolve
            swapped = False

            def resolve_then_retarget(path: Path, *args: object, **kwargs: object) -> Path:
                nonlocal swapped
                resolved = original_resolve(path, *args, **kwargs)
                if not swapped and Path(os.path.abspath(path)) == Path(os.path.abspath(alias)):
                    alias.unlink()
                    os.symlink(second, alias, target_is_directory=True)
                    swapped = True
                return resolved

            with patch.object(Path, "resolve", resolve_then_retarget):
                written = safe_write_text(
                    alias / "capture.md",
                    "anchored\n",
                    root=alias,
                    overwrite=False,
                )

            self.assertTrue(swapped)
            self.assertEqual(written, first / "capture.md")
            self.assertEqual((first / "capture.md").read_text(encoding="utf-8"), "anchored\n")
            self.assertFalse((second / "capture.md").exists())

    def test_safe_write_root_alias_still_rejects_descendant_link_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = base / "actual"
            outside = base / "outside"
            actual.mkdir()
            outside.mkdir()
            alias = base / "alias"
            linked_child = actual / "linked-child"
            try:
                os.symlink(actual, alias, target_is_directory=True)
                os.symlink(outside, linked_child, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                safe_write_text(
                    alias / "linked-child" / "escape.md",
                    "blocked\n",
                    root=alias,
                    overwrite=False,
                )

            self.assertEqual(list(outside.iterdir()), [])

    def test_resolved_containment_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "vault"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "working"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaises(ValueError):
                contained_relative_path(link / "current.json", root)
            with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
                reject_working_path_symlink_components(root, link / "current.json", "working path")

    def test_symlink_component_inside_root_remains_visible_to_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actual = root / "actual"
            actual.mkdir()
            link = root / "working"
            try:
                os.symlink(actual, link, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            self.assertEqual(contained_relative_path(link / "current.json", root), Path("working/current.json"))
            with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
                reject_working_path_symlink_components(root, link / "current.json", "working path")

    def test_alias_root_hook_and_review_workflows_keep_valid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = base / "actual"
            actual.mkdir()
            alias = base / "alias"
            try:
                os.symlink(actual, alias, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            capture = capture_hook_event(alias, "UserPromptSubmit", '{"prompt":"review project memory"}')
            self.assertIsNotNone(capture)
            summary = hook_capture_summary(alias)
            self.assertEqual(summary["total_count"], 1)
            self.assertEqual(summary["malformed_count"], 0)
            review_hook_capture(alias, repo_relative_path(capture, alias), "dismissed", "Unit Test", "Reviewed.")
            hook_archive = archive_reviewed_hook_captures(alias, apply=False)
            self.assertEqual(len(hook_archive.candidates), 1)

            recommendation = capture_review_recommendation(
                alias,
                "inbox",
                "candidate-1",
                "collect_evidence",
                "Confirm current evidence.",
                "Unit Test",
            )
            review_state = review_recommendations(alias)
            self.assertEqual(review_state["pending_count"], 1)
            self.assertEqual(review_state["invalid_count"], 0)
            record_review_recommendation_outcome(
                alias, recommendation.id, "accepted", "Unit Test", "Evidence confirmed."
            )
            recommendation_archive = archive_review_recommendations(alias, apply=False)
            self.assertEqual(len(recommendation_archive.candidates), 1)


class PackageNamespaceTests(unittest.TestCase):
    def test_source_checkout_exposes_namespaced_mcp_module(self) -> None:
        from ai_dememory_tool.mcp_server import memory_mcp

        self.assertEqual(memory_mcp.__name__, "ai_dememory_tool.mcp_server.memory_mcp")


if __name__ == "__main__":
    unittest.main()
