from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from ai_dememory.harness import project_files
from ai_dememory.integration_install import install_user
from ai_dememory.scheduled import _task_xml
from ai_dememory.vault import Vault


class InterpreterPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        base = self.root / "base" / "python"
        base.parent.mkdir()
        base.touch()
        self.python = self.root / "venv with spaces" / "bin" / "python"
        self.python.parent.mkdir(parents=True)
        try:
            self.python.symlink_to(base)
        except OSError as exc:
            self.skipTest(f"file symlinks are unavailable: {exc}")
        self.enterContext(patch("sys.executable", str(self.python)))
        self.enterContext(patch.dict(os.environ, {
            "AI_DEMEMORY_CONFIG_DIR": str(self.root / "config"),
            "CODEX_HOME": str(self.root / "codex"),
        }))
        self.vault = Vault.create(self.root / "vault")

    def assert_hook_interpreter(self, text):
        for groups in json.loads(text)["hooks"].values():
            command = groups[0]["hooks"][0]["command"]
            if os.name == "nt":
                self.assertTrue(command.startswith(subprocess.list2cmdline([str(self.python)]) + " -m "))
            else:
                self.assertEqual(shlex.split(command)[0], str(self.python))

    def test_global_codex_mcp_and_hooks_keep_symlink_interpreter(self):
        install_user(self.vault)
        home = self.root / "codex"
        server = tomllib.loads((home / "config.toml").read_text())["mcp_servers"]["dememory_v3"]
        self.assertEqual(server["command"], str(self.python))
        self.assert_hook_interpreter((home / "hooks.json").read_text())

    def test_project_codex_and_claude_keep_symlink_interpreter(self):
        for client in ("codex", "claude"):
            with self.subTest(client=client):
                files = project_files(self.vault, self.root / client, client, "project:test")
                server_text, hooks_text = files.values()
                if client == "codex":
                    server = tomllib.loads(server_text)["mcp_servers"]["dememory_v3"]
                else:
                    server = json.loads(server_text)["mcpServers"]["dememory_v3"]
                self.assertEqual(server["command"], str(self.python))
                self.assert_hook_interpreter(hooks_text)

    def test_scheduled_command_uses_pythonw_beside_symlink_interpreter(self):
        pythonw = self.python.with_name("pythonw.exe")
        pythonw.touch()
        self.python.resolve().with_name("pythonw.exe").touch()
        task = ET.fromstring(_task_xml(self.vault, "test-user"))
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        self.assertEqual(task.find("t:Actions/t:Exec/t:Command", ns).text, str(pythonw))
