import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ai_dememory.modules import enable_module, disable_module
from ai_dememory.source_history import read_window
from ai_dememory.source_jobs import SourceJobs
from ai_dememory.sources import list_sources
from ai_dememory.vault import Vault


def user(text):
    return {"type": "event_msg", "payload": {"type": "user_message", "message": text}}


class SourceHistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.sources = self.root / "sessions"; self.sources.mkdir()
        env = patch.dict(os.environ, AI_DEMEMORY_CONFIG_DIR=str(self.root / "config"))
        env.start(); self.addCleanup(env.stop)
        enable_module("sources")
        self.vault = Vault.create(self.root / "vault")
        self.jobs = Mock(); self.jobs.extract.return_value = {"learned": [{}]}
        self.manager = SourceJobs(self.vault, self.jobs)
        self.payload = {"root": str(self.sources), "format": "codex", "mode": "history",
                        "scope": "project:test", "interval_hours": 1, "enabled": False}

    def fixture(self, rows, name="a.jsonl"):
        path = self.sources / name
        metadata = {"type": "session_meta", "payload": {"id": name, "source": "vscode"}}
        path.write_text("".join(json.dumps(row) + "\n" for row in [metadata, *rows]), encoding="utf-8")
        return path

    def append(self, path, rows):
        with path.open("a", encoding="utf-8") as stream:
            stream.write("".join(json.dumps(row) + "\n" for row in rows))

    def test_all_messages_in_order_and_mirrors_never_reenter(self):
        rows = []
        for i in range(45):
            rows.extend([user(f"Preference {i}"), {"type": "response_item", "payload": {
                "type": "message", "role": "user", "content": f"Preference {i}"}}])
        self.fixture(rows)
        cursor = None; found = []
        for count in (20, 20, 5):
            window = read_window(self.sources, "a.jsonl", cursor)
            self.assertEqual(len(window["messages"]), count)
            found.extend(m["content"] for m in window["messages"])
            cursor = window["cursor"]
        self.assertEqual(found, [f"Preference {i}" for i in range(45)])
        self.assertEqual(window["bytes_remaining"], 0)

    def test_character_boundary_sensitive_and_oversize_discards(self):
        secret = "-----BEGIN PRIVATE KEY-----\nsynthetic-canary\n-----END PRIVATE KEY-----"
        self.fixture([user("a" * 13000), user("b" * 13000), user(secret), user("x" * 24001), user("Final")])
        first = read_window(self.sources, "a.jsonl")
        self.assertEqual(len(first["messages"]), 1)
        second = read_window(self.sources, "a.jsonl", first["cursor"])
        self.assertEqual([m["content"] for m in second["messages"]], ["b" * 13000, "Final"])
        self.assertEqual(second["counts"]["sensitive"], 1)
        self.assertEqual(second["counts"]["oversize"], 1)

    def test_partial_line_waits_and_assistant_only_windows_advance(self):
        path = self.fixture([user("First")])
        with path.open("a") as stream: stream.write(json.dumps(user("Second")))
        first = read_window(self.sources, "a.jsonl")
        self.assertTrue(first["waiting_for_newline"])
        self.assertEqual(len(first["messages"]), 1)
        with path.open("a") as stream: stream.write("\n")
        second = read_window(self.sources, "a.jsonl", first["cursor"])
        self.assertEqual(second["messages"], [{"role": "user", "content": "Second"}])
        self.append(path, [{"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": "reply"}}])
        third = read_window(self.sources, "a.jsonl", second["cursor"])
        self.assertEqual(third["messages"], [])
        self.assertGreater(third["cursor"]["offset"], second["cursor"]["offset"])

    def test_byte_limit_retains_next_complete_record(self):
        self.fixture([{"type": "tool", "padding": "x" * 600000}] * 4 + [user("At end")])
        first = read_window(self.sources, "a.jsonl")
        self.assertEqual(first["messages"], [])
        self.assertLessEqual(first["cursor"]["offset"], 2000000)
        second = read_window(self.sources, "a.jsonl", first["cursor"])
        self.assertEqual(second["messages"], [{"role": "user", "content": "At end"}])

    def test_truncation_replacement_and_internal_sessions_are_refused(self):
        path = self.fixture([user("A sufficiently long initial statement")])
        window = read_window(self.sources, "a.jsonl")
        self.fixture([])
        with self.assertRaisesRegex(ValueError, "truncated"):
            read_window(self.sources, "a.jsonl", window["cursor"])
        path.unlink(); self.fixture([user("replacement" * 20)])
        # Distinct metadata is detected even on filesystems that reuse an inode.
        text = path.read_text().replace('"id": "a.jsonl"', '"id": "new-id"')
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, "replaced"):
            read_window(self.sources, "a.jsonl", window["cursor"])
        path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "internal", "source": {"subagent": "review"}}}) + "\n")
        with self.assertRaisesRegex(ValueError, "human"):
            read_window(self.sources, "a.jsonl")

    def test_failure_retry_is_stable_even_after_append_and_restart(self):
        path = self.fixture([user("First")])
        id = self.manager.save(self.payload)["saved"]
        self.jobs.extract.side_effect = ValueError("synthetic provider failure")
        self.assertTrue(self.manager.run(id)["failed"])
        before = self.jobs.extract.call_args
        self.append(path, [user("Later")])
        self.jobs.extract.side_effect = None
        manager = SourceJobs(self.vault, self.jobs)
        self.assertEqual(manager.run(id)["processed"], 1)
        self.assertEqual(self.jobs.extract.call_args, before)
        self.assertEqual(manager.run(id)["processed"], 1)
        self.assertEqual(self.jobs.extract.call_args.args[0], [{"role": "user", "content": "Later"}])
        self.assertNotEqual(self.jobs.extract.call_args.kwargs["event_id"], before.kwargs["event_id"])

    def test_identical_windows_have_distinct_occurrences_and_assistant_no_calls(self):
        path = self.fixture([user("Same") for _ in range(40)])
        id = self.manager.save(self.payload)["saved"]
        self.manager.run(id); self.manager.run(id)
        ids = [call.kwargs["event_id"] for call in self.jobs.extract.call_args_list]
        self.assertEqual(len(set(ids)), 2)
        self.manager.run(id)  # Finish discovery pass.
        self.append(path, [{"type": "tool", "data": "ignored"}])
        self.manager.run(id)
        self.assertEqual(self.jobs.extract.call_count, 2)
        state = self.manager.public()[0]
        self.assertEqual(state["progress"]["messages"], 40)
        self.assertNotIn("scan_after", state)
        self.manager.change(id, "delete")
        self.assertEqual(self.manager.public(), [])

    def test_busy_first_conversation_yields_to_other_files(self):
        path = self.fixture([user(f'First {i}') for i in range(45)])
        self.fixture([user('Second conversation')], 'b.jsonl')
        id = self.manager.save(self.payload)['saved']
        self.manager.run(id)
        self.append(path, [user(f'Appended {i}') for i in range(25)])
        self.manager.run(id)
        self.assertEqual(self.jobs.extract.call_args.args[0], [{'role': 'user', 'content': 'Second conversation'}])
        self.manager.run(id)
        self.assertEqual(self.jobs.extract.call_args.args[0][0]['content'], 'First 20')

    def test_pagination_visits_more_than_100_files_and_cursors_do_not_evict(self):
        for i in range(131): self.fixture([user(f"Preference {i}")], f"file-{i:03}.jsonl")
        page = list_sources(self.sources, "codex", after="")
        self.assertEqual(len(page["files"]), 100)
        second = list_sources(self.sources, "codex", after=page["files"][-1]["path"])
        self.assertEqual(len(second["files"]), 31)
        id = self.manager.save(self.payload)["saved"]
        for _ in range(135): self.manager.run(id)
        self.assertEqual(self.jobs.extract.call_count, 131)
        self.assertEqual(self.manager.public()[0]["progress"]["tracked_conversations"], 131)

    def test_bad_file_does_not_starve_next_and_mode_is_opt_in(self):
        (self.sources / "a.jsonl").write_text('{}\n')
        self.fixture([user("Good")], "b.jsonl")
        with self.assertRaises(ValueError): self.manager.save({**self.payload, "format": "generic"})
        id = self.manager.save(self.payload)["saved"]
        result = self.manager.run(id)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["learned"], 1)
        disable_module("sources")
        with self.assertRaises(ValueError): self.manager.run(id)


if __name__ == "__main__":
    unittest.main()
