"""Opt-in Windows one-shot consolidation. No resident worker or history reader."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from .config import config_dir, load_config
from .settings import local_file
from .vault import Vault, _atomic_write, _exclusive_write_lock


# All paths/XML arrive as JSON on stdin, never interpolated into shell source.
_TASK_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$p = [Console]::In.ReadToEnd() | ConvertFrom-Json
$s = New-Object -ComObject 'Schedule.Service'
$s.Connect()
$f = $s.GetFolder('\')
$task = $null
try { $task = $f.GetTask($p.name) }
catch { if ($_.Exception.HResult -ne -2147024894) { throw } }
$xml = if ($null -ne $task) { $task.Xml } else { $null }
if ($p.action -ne 'status') {
    if ($xml -cne $p.expected) { throw 'Task changed or is not owned by this installation' }
    if ($p.action -eq 'install') {
        $task = $f.RegisterTask($p.name, $p.xml, 6, $null, $null, 3, $null)
    } elseif ($p.action -eq 'remove') {
        if ($null -ne $task) { $f.DeleteTask($p.name, 0) }
        $task = $null
    } else { throw 'Unknown task action' }
}
@{ xml = $(if ($null -ne $task) { $task.Xml } else { $null });
   user = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value;
   enabled = $(if ($null -ne $task) { $task.Enabled } else { $false });
   state = $(if ($null -ne $task) { $task.State } else { 0 });
   last_result = $(if ($null -ne $task) { $task.LastTaskResult } else { $null });
   next_run = $(if ($null -ne $task) { $task.NextRunTime.ToString('o') } else { $null })
} | ConvertTo-Json -Compress
"""


def _task_call(action, name, expected=None, xml=None):
    if os.name != "nt":
        raise ValueError("Automatic task installation is Windows-only; use --run-due with your scheduler")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run(
        [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _TASK_SCRIPT],
        input=json.dumps({"action": action, "name": name, "expected": expected, "xml": xml}),
        text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise ValueError("Windows task operation failed. Check Task Scheduler access and unchanged task ownership; no password or administrator access is requested.")
    return json.loads(result.stdout.lstrip("\ufeff"))


def _receipt(vault):
    path = local_file(vault, "windows-task.json")
    if not path.exists():
        return {}
    if path.stat().st_size > 32_000:
        raise ValueError("Task receipt exceeds size limit")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data and data.get("schema_version") != 1:
        raise ValueError("Unsupported task receipt")
    return data


def receipt_status(vault):
    """Cheap receipt-only UI state, not an OS health check or process probe."""
    receipt = _receipt(vault)
    return {"installed_receipt": bool(receipt), "name": receipt.get("name"),
            "verified_live": False, "check_every_minutes": 60,
            "max_run_minutes": 5, "requires_user_logged_in": True}


def _task_xml(vault, user):
    python = Path(sys.executable).resolve().with_name("pythonw.exe")
    if not python.is_file():
        raise ValueError("This Python installation needs pythonw.exe for a windowless scheduled task")
    root = ET.Element("Task", version="1.2", xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task")
    def child(parent, tag, value=None, **attributes):
        item = ET.SubElement(parent, tag, attributes)
        item.text = value
        return item
    registration = child(root, "RegistrationInfo")
    child(registration, "Description", "ai DeMemory V3: check the saved consolidation schedule and exit. No history ingestion.")
    trigger = child(child(root, "Triggers"), "TimeTrigger")
    repetition = child(trigger, "Repetition")
    child(repetition, "Interval", "PT1H")
    child(trigger, "StartBoundary", (datetime.now().astimezone() + timedelta(minutes=1)).replace(microsecond=0).isoformat())
    child(trigger, "Enabled", "true")
    principal = child(child(root, "Principals"), "Principal", id="CurrentUser")
    child(principal, "UserId", user)
    child(principal, "LogonType", "InteractiveToken")
    child(principal, "RunLevel", "LeastPrivilege")
    settings = child(root, "Settings")
    for key, value in (("MultipleInstancesPolicy", "IgnoreNew"),
                       ("DisallowStartIfOnBatteries", "false"), ("StopIfGoingOnBatteries", "false"),
                       ("StartWhenAvailable", "true"), ("Enabled", "true"),
                       ("WakeToRun", "false"), ("ExecutionTimeLimit", "PT5M")):
        child(settings, key, value)
    action = child(child(root, "Actions", Context="CurrentUser"), "Exec")
    child(action, "Command", str(python))
    child(action, "Arguments", subprocess.list2cmdline([
        "-m", "ai_dememory.scheduled", "--vault", str(vault.root), "--config-dir", str(config_dir())]))
    child(action, "WorkingDirectory", str(python.parent))
    return ET.tostring(root, encoding="unicode")


def manage_task(vault, action):
    if action not in {"install", "remove", "status"}:
        raise ValueError("Unknown task action")
    with _exclusive_write_lock(local_file(vault, ".task-install.lock")):
        receipt = _receipt(vault)
        identity = str(config_dir()) + "\n" + str(vault.root)
        name = "ai-DeMemory-V3-" + hashlib.sha256(identity.encode()).hexdigest()[:12]
        if receipt and (receipt.get("name") != name or receipt.get("config_dir") != str(config_dir())):
            raise ValueError("Task receipt belongs to a different installation")
        actual = _task_call("status", name)
        if action == "status":
            return {**receipt_status(vault), "verified_live": True, "exists": bool(actual["xml"]),
                    "owned": bool(receipt) and actual["xml"] == receipt.get("xml"),
                    **{key: actual[key] for key in ("enabled", "state", "last_result", "next_run")}}
        if actual["xml"] is not None and actual["xml"] != receipt.get("xml"):
            raise ValueError("Task was changed or is not owned; inspect it in Windows Task Scheduler before retrying")
        if action == "remove" and not receipt:
            return {"installed": False, "changed": False}
        desired = _task_xml(vault, actual["user"]) if action == "install" else None
        # Preserve a matching trigger on repeat install; refresh moved runtimes.
        if action == "install" and actual["xml"]:
            ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
            old_action = ET.fromstring(actual["xml"]).find("t:Actions", ns)
            new_action = ET.fromstring(desired).find("t:Actions", ns)
            def action_fields(action):
                return (action.get("Context"), *(action.findtext("t:Exec/t:" + field, namespaces=ns)
                         for field in ("Command", "Arguments", "WorkingDirectory")))
            if action_fields(old_action) == action_fields(new_action):
                return {"installed": True, "changed": False, "name": name}
        changed = _task_call(action, name, actual["xml"], desired)
        try:
            data = {"schema_version": 1, "name": name, "config_dir": str(config_dir()),
                    "xml": changed["xml"]} if action == "install" else {}
            _atomic_write(local_file(vault, "windows-task.json"), json.dumps(data, indent=2) + "\n")
        except Exception:
            # Restore only if the task still exactly matches this operation.
            _task_call("install" if actual["xml"] else "remove", name, changed["xml"], actual["xml"])
            raise
        return {"installed": action == "install", "changed": True, "name": name}


def run_due(vault):
    if "workbench" not in load_config().enabled_modules:
        return {"skipped": "workbench_disabled"}
    from .core import CoreServices
    from .jobs import LearningJobs
    result = LearningJobs(CoreServices(vault)).run_due()
    return result or {"skipped": "not_due_or_busy"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--config-dir", required=True)
    args = parser.parse_args(argv)
    os.environ["AI_DEMEMORY_CONFIG_DIR"] = args.config_dir
    try:
        result = run_due(Vault.open(Path(args.vault)))
        return 1 if result.get("error") else 0
    except Exception:
        # Task Scheduler records the exit code. Never send private exceptions to logs.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
