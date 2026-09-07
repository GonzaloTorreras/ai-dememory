"""Opt-in, foreground source schedules. Reuse bounded readers and job receipts."""

import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

from .modules import load_enabled_module
from .settings import local_file
from .vault import _atomic_write, validate_scope


class SourceJobs:
    def __init__(self, vault, jobs):
        self.vault, self.jobs = vault, jobs

    def load(self):
        path = local_file(self.vault, "source-jobs.json")
        if not path.exists():
            return {"rules": []}
        if path.stat().st_size > 1_000_000:
            raise ValueError("Source schedule file exceeds its limit")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("rules"), list) or len(data["rules"]) > 16:
            raise ValueError("Invalid source schedules")
        return data

    def _write(self, data):
        encoded = json.dumps(data, indent=2)
        if len(encoded.encode()) > 1_000_000:
            raise ValueError("Source schedules exceed the local state limit")
        _atomic_write(local_file(self.vault, "source-jobs.json"), encoded)

    def public(self):
        return [{k:v for k,v in rule.items() if k != "seen"} for rule in self.load()["rules"]]

    def save(self, data):
        load_enabled_module("sources")
        from .sources import FORMATS, _root
        root = str(_root(Path(data.get("root", ""))))
        format = data.get("format")
        scope = data.get("scope")
        validate_scope(scope)
        if format not in FORMATS or type(data.get("enabled")) is not bool:
            raise ValueError("Choose a harness and whether scheduled extraction is enabled")
        hours = data.get("interval_hours")
        if type(hours) is not int or not 1 <= hours <= 8760:
            raise ValueError("Choose an interval of 1 to 8760 hours")
        if data["enabled"] and data.get("confirmed") is not True:
            raise ValueError("Confirm automatic transfer to the configured extraction route")
        stored = self.load()
        if len(stored["rules"]) >= 16:
            raise ValueError("At most 16 source schedules; remove an unused one first")
        rule = {"id":uuid4().hex, "root":root, "format":format, "scope":scope,
                "interval_hours":hours, "enabled":data["enabled"], "next_run":time.time()+hours*3600,
                "last_result":"Not run", "seen":{}}
        stored["rules"].append(rule)
        self._write(stored)
        return {"saved":rule["id"]}

    def change(self, id, action):
        stored = self.load()
        rule = next((rule for rule in stored["rules"] if rule["id"] == id), None)
        if rule is None:
            raise ValueError("Source schedule not found")
        if action == "delete":
            stored["rules"].remove(rule)
        elif action == "pause":
            rule["enabled"] = False
        elif action == "resume":
            load_enabled_module("sources")
            rule["enabled"] = True
            rule["next_run"] = time.time()+rule["interval_hours"]*3600
        else:
            raise ValueError("Unsupported schedule action")
        self._write(stored)
        return {"updated":True}

    def run(self, id=None):
        reader = load_enabled_module("sources")
        stored = self.load()
        now = time.time()
        rule = next((r for r in stored["rules"] if r["id"] == id), None) if id else next(
            (r for r in stored["rules"] if r["enabled"] and r["next_run"] <= now), None)
        if rule is None:
            return {"skipped":True}
        # Persist deadline before work so a failed provider cannot spin on every tick.
        rule["next_run"] = now + rule["interval_hours"] * 3600
        self._write(stored)
        result = {"processed":0, "learned":0, "skipped":0}
        try:
            listing = reader.list_sources(Path(rule["root"]), rule["format"])
            for file in listing["files"]:
                identity = hashlib.sha256((file["path"] + ":" + str(file.get("session_id", ""))).encode()).hexdigest()
                stamp = str(file.get("latest_message_id", file["modified_at"])) + ":" + str(file["bytes"])
                previous = rule["seen"].get(identity, {})
                if previous.get("file") == stamp:
                    continue
                try:
                    preview = reader.preview_source(Path(rule["root"]), file["path"], rule["format"], file.get("session_id"))
                except (ValueError, OSError):
                    result["skipped"] += 1
                    continue
                window = hashlib.sha256(json.dumps(preview["messages"],ensure_ascii=False).encode()).hexdigest()
                if previous.get("window") == window:
                    rule["seen"][identity] = {"file":stamp,"window":window}
                    continue
                event = hashlib.sha256((rule["id"]+identity+window).encode()).hexdigest()
                if preview["messages"]:
                    extracted = self.jobs.extract(preview["messages"], rule["scope"],
                                                  route_key="skill:source-"+rule["format"], event_id="source-job-"+event)
                    result["learned"] = len(extracted.get("learned", []))
                rule["seen"][identity] = {"file":stamp,"window":window}
                rule["seen"] = dict(list(rule["seen"].items())[-128:])
                result["processed"] = 1
                break  # One conversation window per run, using normal provider budgets.
            rule["seen"] = dict(list(rule["seen"].items())[-128:])
            rule["last_result"] = f"{result['processed']} conversation window; {result['learned']} memories; {result['skipped']} unreadable"
        except (ValueError, OSError) as exc:
            rule["last_result"] = "Failed; check source access, route and provider budget"
            result = {"failed":True}
        rule["last_run"] = now
        self._write(stored)
        return result
