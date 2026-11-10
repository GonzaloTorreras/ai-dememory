"""Small public synthetic pilot. No vault memories enter its request."""
import hashlib
import json
import time

from .jev_skills import configuration, config_key
from .judgments import JudgmentEngine, _json_size, MAX_INPUT_CHARS, TOTAL_TIMEOUT_SECONDS
from .providers import ProviderEngine, ProviderError, BudgetExceeded

DATASET = "jev-metadata-pilot-v1"
# Frozen labels are evaluation data only, never model input.
CASES = (
    ("Storage rule", "Keep Markdown canonical and rebuild the SQLite index when needed.", "en", True),
    ("Preferencia", "Prefiero copias cifradas fuera del equipo y comprobar su restauración.", "es", True),
    ("Project rule", "Keep tasks small; conserva los identificadores exactos de cada proyecto.", "mixed", True),
    ("Restore lesson", "On 2026-11-09, a clean restore recovered the records but missed attachments; verify both in future restore tests.", "en", True),
    ("Greeting", "Thanks, please continue with this one command now.", "en", False),
    ("Saludo", "Hola, adelante y sigue con lo de ahora.", "es", False),
    ("Greeting", "Merci beaucoup, continuez.", "fr", False),
    ("Fragment", "ZX-42 / 9901 / A8", "undetermined", False),
)


def preview(vault):
    engine = JudgmentEngine(vault)
    config = configuration(engine.settings)
    if not config:
        raise ValueError("Enable the optional Jev module first")
    return {"dataset":DATASET, "config_key":config_key(engine.settings, config),
            "cases":[{"title":t,"content":c,"expected_language":lang,"expected_useful":useful}
                     for t,c,lang,useful in CASES], "canonical_writes":False,
            "note":"Synthetic diagnostic only; no real memory or project purpose is sent. Shared budgets apply."}


def run(vault, expected_config, *, engine=None):
    engine = engine or JudgmentEngine(vault)
    config = configuration(engine.settings)
    if not config or config_key(engine.settings, config) != expected_config:
        raise ValueError("Evaluation settings changed. Preview again.")
    route, chain = engine._configuration("project:synthetic-evaluation", ["project:synthetic-evaluation"])
    if route is None:
        raise ValueError("Choose and save a judgment provider first")
    choices = {**config["languages"], "mixed":"Multiple natural languages.",
               "other":"Outside the configured languages.", "undetermined":"Insufficient natural-language evidence."}
    questions, schemas = {}, {}
    for i, _case in enumerate(CASES):
        ql, qu = f"language_{i}", f"useful_{i}"
        questions[ql] = {"type":"choice", "instructions":f"Identify the natural language of `cases[{i}].content`. The title is context only. Choose undetermined for content without natural language; ignore identifiers and code.", "criteria":choices}
        questions[qu] = {"type":"noul", "instructions":f"Is `cases[{i}]` useful in a project memory archive for future agent tasks? Judge retention value, not truth.",
                         "criteria":{"true":"Reusable fact, preference, lesson or meaningful dated outcome.",
                                     "false":"Greeting, one-time permission, transient instruction or generic filler."}}
        schemas[ql], schemas[qu] = tuple(choices), None
    payload = {"model":"", "state":{"cases":[{"title":t,"content":c} for t,c,_l,_u in CASES]}, "questions":questions}
    if _json_size(payload) > MAX_INPUT_CHARS:
        raise ValueError("Too many language labels for this small pilot; use a shorter language list.")
    cache_key = hashlib.sha256((DATASET + expected_config + json.dumps(payload)).encode()).hexdigest()
    previous = engine._cached(cache_key)
    if previous:
        return {**previous,"cached":True}
    provider_engine = ProviderEngine(vault, engine.settings, engine.transport, engine.credential_resolver)
    start = time.monotonic()
    last_reason = "provider_unavailable"
    for name in chain:
        try:
            answers, meta = engine._request_many(provider_engine, engine.settings["providers"][name], name, payload,
                                                 schemas, start + TOTAL_TIMEOUT_SECONDS)
            break
        except BudgetExceeded:
            return {"status":"unassessed","reason":"budget"}
        except ProviderError as exc:
            last_reason = exc.reason
    else:
        return {"status":"unassessed","reason":last_reason}
    rows = []
    for i, (_t,_c,language,useful) in enumerate(CASES):
        expected = language if language in choices else "other"
        predicted = answers[f"language_{i}"]["verdict"]
        probability = answers[f"useful_{i}"]["probability"]
        rows.append({"case":i,"language":predicted,"expected_language":expected,
                     "expected_useful":useful,"useful_probability":probability,"keep_at_0_5":probability >= .5})
    result = {"status":"assessed","dataset":DATASET,"cached":False, **meta,
              "duration_ms":round((time.monotonic()-start)*1000), "cases":rows,
              "baseline":{"policy":"keep_all", "usefulness_correct":4, "usefulness_cases":8},
              "measured":{"language_correct":sum(r["language"]==r["expected_language"] for r in rows),
                          "usefulness_correct":sum(r["keep_at_0_5"]==r["expected_useful"] for r in rows),
                          "useful_rejected":sum(r["expected_useful"] and not r["keep_at_0_5"] for r in rows),
                          "noise_kept":sum(not r["expected_useful"] and r["keep_at_0_5"] for r in rows)},
              "note":"Eight synthetic cases do not establish production efficacy or calibrated thresholds. No ranking/admission change."}
    engine._cache(cache_key, result)
    return result
