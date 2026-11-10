"""Optional advisory tags. One foreground sweep, existing SQLite and budgets."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import closing

from .config import load_config, config_path
from .judgments import JudgmentEngine, _json_size, MAX_INPUT_CHARS, TOTAL_TIMEOUT_SECONDS
from .policy import reject_high_confidence_secrets
from .providers import ProviderEngine, ProviderError, BudgetExceeded, _database
from .quality import evidence_revision, recall_eligible
from .settings import load_settings, local_file
from .vault import _exclusive_write_lock, utc_now, VaultBusyError

RUBRIC = "memory-metadata-v1"


def configuration(settings):
    if "jev" not in load_config().enabled_modules:
        return None
    from .builtin_modules.jev import validate_config
    return validate_config(settings.get("module_settings", {}).get("jev", {}))


def config_key(settings, config):
    route = settings["judgment"]
    chain = [route["primary"], *route["fallback"]]
    enabled = load_config().enabled_modules
    profiles = [[name, {k:v for k,v in settings["providers"].get(name, {}).items()
                        if k not in ("input_cost_per_million", "output_cost_per_million")},
                 settings["providers"].get(name, {}).get("kind", "").removeprefix("plugin:") in enabled]
                for name in chain]
    semantic = {name: config[name] for name in ("languages", "purpose")}
    return hashlib.sha256(json.dumps([RUBRIC, semantic, profiles], sort_keys=True).encode()).hexdigest()


def database(vault):
    db = _database(vault)
    db.execute("""CREATE TABLE IF NOT EXISTS jev_skill_receipts (
        memory_id TEXT PRIMARY KEY, scope TEXT NOT NULL, revision TEXT NOT NULL,
        config_key TEXT NOT NULL, status TEXT NOT NULL, result TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("CREATE TABLE IF NOT EXISTS jev_skill_state (id INTEGER PRIMARY KEY CHECK(id=1), config_key TEXT NOT NULL)")
    return db


def record(vault, memory, key, result):
    with closing(database(vault)) as db, db:
        db.execute("INSERT OR REPLACE INTO jev_skill_receipts VALUES(?,?,?,?,?,?,?)",
                   (memory.memory_id, memory.scope, evidence_revision(memory.title, memory.content, memory.source),
                    key, result["status"], json.dumps(result), utc_now()))


def cached(vault, memory, key):
    path = local_file(vault, "runtime.sqlite")
    if not path.exists():
        return None
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=.1)) as db:
            row = db.execute("SELECT revision,config_key,status,result,scope FROM jev_skill_receipts WHERE memory_id=?",
                             (memory.memory_id,)).fetchone()
        revision = evidence_revision(memory.title, memory.content, memory.source)
        if row and row[:3] == (revision, key, "assessed") and row[4] == memory.scope and len(row[3]) <= 16_000:
            result = json.loads(row[3])
            if (isinstance(result, dict) and isinstance(result.get("result"), dict)
                    and result["result"].keys() <= {"language", "usefulness"}
                    and all(isinstance(value, dict) for value in result["result"].values())):
                return result
    except (ValueError, OSError, sqlite3.Error):
        pass
    return None


def assess(services, memory_id, scope, **kwargs):
    if "jev" not in load_config().enabled_modules:
        return {"status":"unassessed", "reason":"skills_disabled", "advisory_only":True, "result":{}}
    try:
        with _exclusive_write_lock(services.vault.root / ".jev-skills.lock"):
            return _assess(services, memory_id, scope, **kwargs)
    except VaultBusyError:
        return {"status":"unassessed", "reason":"busy", "advisory_only":True, "result":{}}


def _assess(services, memory_id, scope, *, expected_revision=None, expected_config=None, automatic=False, engine=None):
    vault = services.vault
    engine = engine or JudgmentEngine(vault)
    settings = engine.settings
    config = configuration(settings)
    empty = lambda reason: {"status":"unassessed", "reason":reason, "advisory_only":True, "result":{}}
    if not config or not (config["language"] or config["usefulness"]):
        return empty("skills_disabled")
    memory = vault.get(memory_id)
    if not memory or memory.scope != scope or not recall_eligible(memory):
        return empty("memory_not_eligible")
    revision = evidence_revision(memory.title, memory.content, memory.source)
    if expected_revision is not None and expected_revision != revision:
        return empty("preview_stale")
    allowed = config["automatic_scopes"] if automatic and config["after_save"] else None
    if automatic and allowed is None:
        return empty("automatic_not_enabled")
    route, chain = engine._configuration(scope, allowed)
    if route is None:
        return empty("judgment_not_enabled")
    key = config_key(settings, config)
    if expected_config is not None and expected_config != key:
        return empty("preview_stale")
    old = cached(vault, memory, key)
    wanted = {name for name in ("language", "usefulness") if config[name]}
    previous = old["result"] if old else {}
    if wanted <= previous.keys():
        return {**old, "result":{name:previous[name] for name in wanted}, "cache":{"hit":True}}
    questions, schemas = {}, {}
    if config["language"] and "language" not in previous:
        choices = {**config["languages"], "mixed":"Substantial content in multiple languages.",
                   "other":"A language outside the configured list.", "undetermined":"Not enough language evidence."}
        questions["language"] = {"type":"choice", "instructions":"Identify the natural language of `content`. `title` is context only. If content has no natural language, choose undetermined regardless of title; identifiers and code are not language evidence.",
                                  "criteria":choices}
        schemas["language"] = tuple(choices)
    if config["usefulness"] and "usefulness" not in previous:
        questions["usefulness"] = {"type":"noul", "instructions":
            "Would this claim be useful in a scoped memory archive for agents working on `scope`? "
            "Judge retention value, not truth or authorization. `purpose` describes the user's intended use.",
            "criteria":{"true":"A reusable explicit fact, preference, tested lesson, or meaningful dated outcome with future context value.",
                        "false":"Greeting, one-time permission, generic filler, transient instruction, or ungrounded guess without reuse value."}}
        schemas["usefulness"] = None
    payload = {"model":"", "state":{"scope":scope, "title":memory.title, "content":memory.content,
                                        "purpose":config["purpose"]}, "questions":questions}
    if _json_size(payload) > MAX_INPUT_CHARS:
        return empty("input_too_large")
    try:
        reject_high_confidence_secrets(json.dumps(payload))
    except ValueError:
        return empty("sensitive_content")
    provider_engine = ProviderEngine(vault, settings, engine.transport, engine.credential_resolver)
    deadline, result = time.monotonic() + TOTAL_TIMEOUT_SECONDS, empty("provider_unavailable")
    for name in chain:
        try:
            answers, meta = engine._request_many(provider_engine, settings["providers"][name], name, payload, schemas, deadline)
            result = {"status":"assessed", "advisory_only":True, "writes_canonical_memory":False,
                      "rubric":RUBRIC, **meta, "cache":{"hit":False}, "result":{**previous, **answers}}
            break
        except BudgetExceeded:
            return empty("budget")
        except ProviderError as exc:
            result = empty(exc.reason)
    current = vault.get(memory_id)
    if (not current or not recall_eligible(current) or current.scope != scope
            or evidence_revision(current.title, current.content, current.source) != revision
            or configuration(load_settings(vault)) != config
            or config_key(load_settings(vault), config) != key):
        return empty("preview_stale")
    if result.get("reason") != "missing_credentials":
        record(vault, memory, key, result)
    return result


def arm(services, *, force=False):
    settings = load_settings(services.vault)
    config = configuration(settings)
    if config is None:
        return False
    if not config["after_save"]:
        if local_file(services.vault, "runtime.sqlite").exists():
            with closing(database(services.vault)) as db, db:
                db.execute("DELETE FROM jev_skill_state")
        return False
    key = config_key(settings, config)
    # Global module off/on can occur while this foreground process is stopped.
    # Re-arm conservatively on config edits; never backfill that interval.
    epoch = config_path().stat().st_mtime_ns
    auto_key = hashlib.sha256(json.dumps([key, config, epoch], sort_keys=True).encode()).hexdigest()
    with closing(database(services.vault)) as db:
        state = db.execute("SELECT config_key FROM jev_skill_state WHERE id=1").fetchone()
    if state and state[0] == auto_key and not force:
        return False
    # Baseline before acknowledging activation. No old corpus backfill or
    # timestamp watermark: same-second future IDs cannot be lost.
    with _exclusive_write_lock(services.vault.root / ".ai-dememory.write.lock"):
        memories = [services.vault.read_memory(p) for p in services.vault.iter_memory_paths()]
        with closing(database(services.vault)) as db, db:
            db.execute("DELETE FROM jev_skill_receipts WHERE status != 'assessed' OR config_key != ?", (key,))
            db.executemany("INSERT OR IGNORE INTO jev_skill_receipts VALUES(?,?,?,?,?,?,?)",
                           [(m.memory_id, m.scope, "", key, "baseline", "{}", utc_now()) for m in memories])
            db.execute("INSERT OR REPLACE INTO jev_skill_state VALUES(1,?)", (auto_key,))
    return True


def process_new(services, credential_resolver=None):
    settings = load_settings(services.vault)
    config = configuration(settings)
    armed = arm(services)
    if not config or not config["after_save"] or armed:
        return {"status":"idle"}
    with closing(database(services.vault)) as db:
        seen = {r[0] for r in db.execute("SELECT memory_id FROM jev_skill_receipts")}
    # ponytail: one bounded vault sweep/minute; use projected discovery only if
    # measured vault size makes scanning expensive. The canonical file cap applies.
    for path in services.vault.iter_memory_paths():
        memory = services.vault.read_memory(path)
        if memory.memory_id not in seen and memory.scope in config["automatic_scopes"] and recall_eligible(memory):
            result = assess(services, memory.memory_id, memory.scope, automatic=True,
                            engine=JudgmentEngine(services.vault, settings, credential_resolver=credential_resolver))
            if result["status"] == "unassessed" and result.get("reason") not in ("budget", "missing_credentials", "busy"):
                record(services.vault, memory, config_key(settings, config), result)
            return result
    return {"status":"idle"}


def recall_tags(vault, memory):
    settings = load_settings(vault)
    config = configuration(settings)
    if not config or not config["recall_tags"]:
        return {}
    result = cached(vault, memory, config_key(settings, config))
    selected = {name:value for name,value in result["result"].items() if config[name]} if result else {}
    return {"advisory_only":True, **selected} if selected else {}
