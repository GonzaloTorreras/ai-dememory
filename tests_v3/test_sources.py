from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_dememory import sources
from ai_dememory.builtin_modules import sources as source_module


class ConversationSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def fixture(self, rows, name="conversation.jsonl"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(json.dumps(row) for row in rows) if path.suffix == ".jsonl" else json.dumps(rows)
        path.write_text(text, encoding="utf-8")
        return path

    def test_codex_user_text_and_mirrored_events_without_tools_or_assistant(self):
        rows = [
            {"type": "session_meta", "payload": {"cwd": "hidden"}},
            {"type": "event_msg", "payload": {"type": "user_message", "message": "Use Python"}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Use Python"}]}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Never import"}]}},
            {"type": "response_item", "payload": {"type": "function_call_output", "output": "Never import"}},
            {"type": "event_msg", "payload": {"type": "user_message", "message": "Use Python"}},
        ]
        self.fixture(rows)
        result = sources.preview_source(self.root, "conversation.jsonl", "codex")
        self.assertEqual(result["messages"], [{"role": "user", "content": "Use Python"}] * 2)
        self.assertEqual(result["counts"]["discarded_duplicate"], 1)
        self.assertEqual(result["counts"]["discarded_non_user"], 3)

    def test_claude_pi_and_generic_require_explicit_user_role(self):
        for format in ("claude", "pi", "generic"):
            rows = []
            for index, role in enumerate(("user", "assistant", "system", "tool")):
                message = {"role": role, "content": [{"type": "text", "text": role}, {"type": "tool_result", "content": "secret tool"}]}
                rows.append({"type": role, "message": message} if format == "claude" else
                            {"type": "message", "id": str(index), "parentId": str(index - 1) if index else None,
                             "message": message} if format == "pi" else message)
            name = f"{format}.jsonl"
            self.fixture(rows, name)
            result = sources.preview_source(self.root, name, format)
            self.assertEqual(result["messages"], [{"role": "user", "content": "user"}])

    def test_codex_titles_and_internal_sessions_are_not_filename_identity(self):
        sessions = self.root / "sessions"
        rows = [{"type":"session_meta","payload":{"id":"human-id","source":"vscode","cwd":"project-folder"}},
                {"type":"event_msg","payload":{"type":"user_message","message":"Human preference"}}]
        self.fixture(rows, "sessions/2026/09/07/rollout-human.jsonl")
        self.fixture([{"type":"session_meta","payload":{"id":"review-id","source":{"subagent":{"other":"guardian"}}}}], "sessions/2026/09/07/rollout-review.jsonl")
        self.fixture([{"id":"human-id","thread_name":"Readable conversation title"}], "session_index.jsonl")
        result = sources.list_sources(sessions,"codex")
        self.assertEqual(len(result["files"]),1)
        self.assertEqual(result["files"][0]["title"],"Readable conversation title")
        with self.assertRaisesRegex(ValueError,"Internal Codex"):
            sources.preview_source(sessions,"2026/09/07/rollout-review.jsonl","codex")

    def test_codex_native_events_exclude_scaffolding_and_nonadjacent_mirrors(self):
        rows = [{"type":"response_item","payload":{"type":"message","role":"user","content":"# AGENTS.md instructions bootstrap"}},
                {"type":"event_msg","payload":{"type":"user_message","message":"A real preference"}},
                {"type":"event_msg","payload":{"type":"token_count"}},
                {"type":"response_item","payload":{"type":"message","role":"user","content":"A real preference"}},
                {"type":"event_msg","payload":{"type":"user_message","message":"The following is the Codex agent history added since your last approval assessment."}}]
        self.fixture(rows)
        result=sources.preview_source(self.root,"conversation.jsonl","codex")
        self.assertEqual(result["messages"],[{"role":"user","content":"A real preference"}])

    def test_large_internal_metadata_cannot_bypass_source_exclusion(self):
        for size in (80_000,600_000):
            self.fixture([{"type":"session_meta","payload":{"base_instructions":"x"*size,"source":{"subagent":{"other":"guardian"}}}},
                          {"type":"event_msg","payload":{"type":"user_message","message":"Internal review data"}}])
            self.assertEqual(sources.list_sources(self.root,"codex")["files"],[])
            with self.assertRaises(ValueError): sources.preview_source(self.root,"conversation.jsonl","codex")

    def test_listing_selects_recent_files_beyond_first_hundred(self):
        for index in range(110):
            path=self.fixture([],f"file-{index:03}.jsonl")
            os.utime(path,(index+100,index+100))
        result=sources.list_sources(self.root,"generic")
        self.assertEqual(len(result["files"]),100)
        self.assertEqual(result["files"][0]["path"],"file-109.jsonl")
        self.assertTrue(result["truncated"])

    def test_generic_messages_export_and_same_text_distinct_turns(self):
        self.fixture({"messages": [{"role": "user", "content": "Repeated"}] * 2}, "export.json")
        result = sources.preview_source(self.root, "export.json", "generic")
        self.assertEqual(len(result["messages"]), 2)

    def test_latest_messages_and_character_budget_do_not_crop_content(self):
        self.fixture([{"role": "user", "content": f"Turn {index}"} for index in range(30)])
        result = sources.preview_source(self.root, "conversation.jsonl", "generic")
        self.assertEqual(result["messages"][0]["content"], "Turn 10")
        self.assertEqual(result["messages"][-1]["content"], "Turn 29")
        self.assertTrue(result["truncated"])
        self.assertEqual(result["counts"]["discarded_limit"], 10)
        self.fixture([{"role": "user", "content": "x" * 12_000}] * 3)
        result = sources.preview_source(self.root, "conversation.jsonl", "generic")
        self.assertEqual(result["counts"]["returned_characters"], 24_000)
        self.assertEqual(len(result["messages"]), 2)

    def test_sensitive_and_malformed_records_are_counted_without_exposure(self):
        canary = "ghp_" + "A" * 32
        path = self.fixture([{"role": "user", "content": canary}, {"role": "user", "content": "Keep this"}])
        with path.open("a", encoding="utf-8") as handle:
            handle.write('\n{"broken":\n')
        result = sources.preview_source(self.root, path.name, "generic")
        self.assertNotIn(canary, json.dumps(result))
        self.assertEqual(result["counts"]["discarded_sensitive"], 1)
        self.assertEqual(result["counts"]["malformed_records"], 1)
        self.assertEqual(result["messages"], [{"role": "user", "content": "Keep this"}])

    def test_listing_depth_count_suffix_and_size_limits(self):
        self.fixture([], "visible.json")
        self.fixture([], "one/two/three/four/allowed.json")
        self.fixture([], "one/two/three/four/five/excluded.json")
        (self.root / "secret.txt").write_text("not a supported source")
        (self.root / "large.json").write_bytes(b" " * (sources.MAX_FILE_BYTES + 1))
        result = sources.list_sources(self.root, "generic")
        self.assertEqual({item["path"] for item in result["files"]}, {"visible.json", "one/two/three/four/allowed.json"})
        self.assertTrue(result["truncated"])
        with patch.object(sources, "MAX_FILES", 1):
            result = sources.list_sources(self.root, "generic")
            self.assertEqual(len(result["files"]), 1)
            self.assertTrue(result["truncated"])

    def test_refuse_relative_root_traversal_missing_and_oversize_files(self):
        self.fixture([])
        with self.assertRaises(ValueError):
            sources.list_sources(Path("."), "generic")
        for relative in ("../outside.json", str(self.root / "conversation.jsonl"), "missing.json", "other.txt"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                sources.preview_source(self.root, relative, "generic")
        (self.root / "large.json").write_bytes(b" " * (sources.MAX_FILE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "2 MB"):
            sources.preview_source(self.root, "large.json", "generic")
        with self.assertRaisesRegex(ValueError, "format must"):
            sources.list_sources(self.root, "unsupported")

    def test_symlinks_are_never_read(self):
        outside = self.fixture([{"role": "user", "content": "Outside"}], "real.json")
        linked = self.root / "linked.json"
        try:
            linked.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symlinks unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "links or junctions"):
            sources.preview_source(self.root, "linked.json", "generic")
        self.assertNotIn("linked.json", [item["path"] for item in sources.list_sources(self.root, "generic")["files"]])

    def test_reads_leave_files_unchanged_and_module_is_foreground_only(self):
        path = self.fixture([{"role": "user", "content": "Keep"}])
        before = {item.name: item.read_bytes() for item in self.root.iterdir() if item.is_file()}
        sources.list_sources(self.root, "generic")
        sources.preview_source(self.root, path.name, "generic")
        after = {item.name: item.read_bytes() for item in self.root.iterdir() if item.is_file()}
        self.assertEqual(before, after)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(source_module.serve(None, []), 0)
        self.assertIn("Workbench", output.getvalue())
        self.assertFalse(source_module.get_manifest().resource_budget["persistent"])

    def test_pi_selects_only_latest_leaf_ancestors_and_rejects_broken_chain(self):
        def row(id, parent, text):
            return {"type": "message", "id": id, "parentId": parent, "message": {"role": "user", "content": text}}
        self.fixture([row("a", None, "Shared"), row("b", "a", "Discard branch"), row("c", "a", "Current branch")])
        result = sources.preview_source(self.root, "conversation.jsonl", "pi")
        self.assertEqual([message["content"] for message in result["messages"]], ["Shared", "Current branch"])
        self.fixture([row("a", "missing", "Broken")])
        with self.assertRaisesRegex(ValueError, "unresolved"):
            sources.preview_source(self.root, "conversation.jsonl", "pi")

    def test_dsh_only_human_source_and_highest_generation(self):
        rows = [{"type": "session", "version": 2}]
        for kind in ("user", "plugin", "goal"):
            rows.append({"type": "user/message", "data": {"role": "user", "source": {"kind": kind},
                                                          "content": [{"type": "text", "text": kind}]}})
        self.fixture(rows, "session.v1.jsonl")
        self.fixture(rows, "session.v2.jsonl")
        listed = sources.list_sources(self.root, "dsh")
        self.assertEqual([item["path"] for item in listed["files"]], ["session.v2.jsonl"])
        with self.assertRaisesRegex(ValueError, "latest DSH"):
            sources.preview_source(self.root, "session.v1.jsonl", "dsh")
        result = sources.preview_source(self.root, "session.v2.jsonl", "dsh")
        self.assertEqual(result["messages"], [{"role": "user", "content": "user"}])
        (self.root / "session.v3.jsonl.zstd").write_bytes(b"not-real-compressed")
        listed = sources.list_sources(self.root, "dsh")
        self.assertEqual(listed["files"], [])
        self.assertIn("compressed sessions are not supported", listed["notices"][0])

    def hermes_fixture(self):
        path = self.root / "state.db"
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, "
                           "timestamp REAL, active INTEGER DEFAULT 1, _compressed_summary INTEGER DEFAULT 0)")
        connection.executemany("INSERT INTO messages(session_id,role,content,timestamp,active,_compressed_summary) VALUES(?,?,?,?,?,?)", [
            ("session-a", "user", "Project A", 100, 1, 0),
            ("session-b", "user", "Project B", 1, 1, 0),
            ("session-b", "assistant", "Never import assistant", 2, 1, 0),
            ("session-b", "user", "Compressed summary", 3, 1, 1),
            ("session-b", "user", "Inactive", 4, 0, 0),
            ("session-b", "user", "\x00json:" + json.dumps([{"type": "text", "text": "User text"}, {"type": "tool_result", "content": "Never"}]), 5, 1, 0),
        ])
        connection.commit()
        connection.close()
        return path

    def test_native_hermes_snapshot_is_per_session_user_only_and_unchanged(self):
        path = self.hermes_fixture()
        before = path.read_bytes()
        listed = sources.list_sources(self.root, "hermes")
        self.assertEqual([item["session_id"] for item in listed["files"]], ["session-b", "session-a"])
        result = source_module.preview_source(self.root, "state.db", "hermes")
        self.assertEqual(result["session_id"], "session-b")
        self.assertEqual([message["content"] for message in result["messages"]], ["Project B", "User text"])
        selected = sources.preview_source(self.root, "state.db", "hermes", "session-a")
        self.assertEqual(selected["messages"], [{"role": "user", "content": "Project A"}])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual({item.name for item in self.root.iterdir()}, {"state.db"})
        self.assertIn("snapshot", result["notice"])

    def test_native_hermes_rejects_active_wal_and_unknown_schema(self):
        path = self.hermes_fixture()
        writer = sqlite3.connect(path)
        try:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("INSERT INTO messages(session_id,role,content,timestamp) VALUES('session-b','user','Live',6)")
            writer.commit()
            self.assertGreater(Path(str(path) + "-wal").stat().st_size, 0)
            with self.assertRaisesRegex(ValueError, "active WAL"):
                sources.preview_source(self.root, "state.db", "hermes")
            self.assertIn("active WAL", sources.list_sources(self.root, "hermes")["notices"][0])
        finally:
            writer.close()
        unknown = sqlite3.connect(self.root / "unknown.db")
        unknown.execute("CREATE TABLE other(value TEXT)")
        unknown.close()
        with self.assertRaisesRegex(ValueError, "supported Hermes"):
            sources.preview_source(self.root, "unknown.db", "hermes")
