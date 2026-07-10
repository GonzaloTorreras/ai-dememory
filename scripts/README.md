# Scripts

All scripts are dependency-light Python and should run from Windows/WSL with
Python 3.12+.

For a local command, install the checkout in editable mode:

```bash
python3 -m pip install -e .
ai-dememory validate
ai-dememory doctor
ai-dememory init ~/code/my-memory
ai-dememory mcp-config --client codex
ai-dememory mcp-client-smoke
ai-dememory verify-mcp
ai-dememory mcp-inventory --check-docs
ai-dememory install-smoke
ai-dememory publish-guard
ai-dememory ci-guard
ai-dememory artifact-guard
ai-dememory vault-setup-guard
ai-dememory pr-template-guard
ai-dememory pr-draft-guard
ai-dememory acceptance-guard
ai-dememory adr-guard
ai-dememory release-checklist-guard
ai-dememory release-evidence --json
ai-dememory roadmap status --json
ai-dememory acceptance status --json
ai-dememory acceptance verify --json
ai-dememory provenance --json
ai-dememory provenance --write-report --report-path reports/durable-provenance.md
ai-dememory release-check
ai-dememory mcp-smoke
ai-dememory api-smoke
ai-dememory eval-recall
ai-dememory recall-fixtures check-miss --query "missed query" --expected-id mem_example --json
ai-dememory capture-miss --query "missed query" --expected-id mem_example --reason "Expected memory was absent." --dry-run
ai-dememory recall-fixtures review-plan --write-report
ai-dememory recall-fixtures packet --write-report
ai-dememory recall-fixtures packet --limit 50 --pending-offset 50 --invalid-offset 50 --write-report
ai-dememory recall-fixtures promote-miss --help
ai-dememory recall-fixtures review-miss --help
ai-dememory search ai-dememory --limit 3
ai-dememory search ai-dememory --why
ai-dememory context ai-dememory --budget 2000
ai-dememory context --auto --budget 2000
ai-dememory graph --json
ai-dememory api --host 127.0.0.1 --port 8765
ai-dememory providers detect
ai-dememory capture markdown --path ./notes.md
ai-dememory learn --git --days 7 --repo .
ai-dememory learn --git --days 7 --repo . --write
ai-dememory vector status
ai-dememory maintenance status
ai-dememory maintenance run --profile daily --dry-run --json
ai-dememory maintenance run --profile daily --report-dir reports/maintenance
ai-dememory lifecycle scores --json
ai-dememory lifecycle report
ai-dememory lifecycle report --report-path reports/lifecycle.md
ai-dememory sleep plan
ai-dememory sleep --dry-run --json
ai-dememory sleep --propose --id sleep_... --json
ai-dememory sleep --apply-reviewed --id sleep_... --json
ai-dememory sleep plan --report-path reports/sleep-plan.md
ai-dememory sleep plan --json --json-report-path reports/sleep-plan.json
ai-dememory sleep apply-reviewed --all
ai-dememory working status --json
ai-dememory setup health --json
ai-dememory schedule plan --json
ai-dememory schedule setup --dry-run
ai-dememory hooks config --client codex
ai-dememory hooks config --client claude
ai-dememory hooks captures --json
ai-dememory hooks captures --created-from 2026-06-01 --created-to 2026-06-30 --json
ai-dememory hooks captures --write-report
ai-dememory hooks review --help
ai-dememory hooks archive --json
ai-dememory hooks install --client all --dry-run
ai-dememory review false-positives
ai-dememory review conflicts
ai-dememory review modes
ai-dememory review configure-mode --mode balanced --reviewer you
ai-dememory review plan --kind conflict
ai-dememory review recommendation --kind conflict --target-id conf_example --recommendation collect_evidence --rationale "Needs human review." --recommended-by "Local LLM" --json
ai-dememory review recommendations --json
ai-dememory review recommendation-outcome --id rec_example --status accepted --reviewer you --reason reviewed --json
ai-dememory review recommendation-outcomes --json
ai-dememory review recommendation-outcomes --limit 50 --offset 50 --invalid-offset 50 --json
ai-dememory conflict resolve --id conf_example --keep mem_example --recommendation-id rec_example --reviewer you
```

Run from the repository root:

```bash
python3 scripts/ai_dememory.py validate
python3 scripts/ai_dememory.py validate --json
python3 scripts/ai_dememory.py doctor
python3 scripts/ai_dememory.py mcp-client-smoke --command python3 --command-arg scripts/ai_dememory.py
python3 scripts/ai_dememory.py verify-mcp
python3 scripts/ai_dememory.py mcp-inventory --check-docs
python3 scripts/ai_dememory.py install-smoke
python3 scripts/ai_dememory.py publish-guard
python3 scripts/ai_dememory.py ci-guard
python3 scripts/ai_dememory.py artifact-guard
python3 scripts/ai_dememory.py vault-setup-guard
python3 scripts/ai_dememory.py pr-template-guard
python3 scripts/ai_dememory.py pr-draft-guard
python3 scripts/ai_dememory.py acceptance-guard
python3 scripts/ai_dememory.py adr-guard
python3 scripts/ai_dememory.py release-checklist-guard
python3 scripts/ai_dememory.py release-evidence --json
python3 scripts/ai_dememory.py roadmap status --json
python3 scripts/ai_dememory.py acceptance status --json
python3 scripts/ai_dememory.py acceptance verify --json
python3 scripts/ai_dememory.py provenance --json
python3 scripts/ai_dememory.py provenance --write-report --report-path reports/durable-provenance.md
python3 scripts/ai_dememory.py release-check
python3 scripts/ai_dememory.py mcp-smoke
python3 scripts/ai_dememory.py api-smoke
python3 scripts/ai_dememory.py secret-scan
python3 scripts/ai_dememory.py index
python3 scripts/ai_dememory.py search codex
python3 scripts/ai_dememory.py search codex --why
python3 scripts/ai_dememory.py context codex --budget 2000
python3 scripts/ai_dememory.py graph --json
python3 scripts/ai_dememory.py providers detect
python3 scripts/ai_dememory.py providers configure codex --path "$HOME/.codex" --dry-run --json
python3 scripts/ai_dememory.py capture text --stdin --title "Session lesson"
python3 scripts/ai_dememory.py learn --git --days 7 --repo .
python3 scripts/ai_dememory.py learn --git --days 7 --repo . --write
python3 scripts/ai_dememory.py vector status
python3 scripts/ai_dememory.py maintenance status
python3 scripts/ai_dememory.py maintenance run --profile daily --dry-run --json
python3 scripts/ai_dememory.py maintenance run --profile daily --report-dir reports/maintenance
python3 scripts/ai_dememory.py maintenance run --profile weekly --dry-run --json
python3 scripts/ai_dememory.py maintenance run --profile weekly
python3 scripts/ai_dememory.py lifecycle scores --json
python3 scripts/ai_dememory.py lifecycle report
python3 scripts/ai_dememory.py lifecycle report --report-path reports/lifecycle.md
python3 scripts/ai_dememory.py sleep plan
python3 scripts/ai_dememory.py sleep --dry-run --json
python3 scripts/ai_dememory.py sleep --propose --id sleep_... --json
python3 scripts/ai_dememory.py sleep --apply-reviewed --id sleep_... --json
python3 scripts/ai_dememory.py sleep plan --report-path reports/sleep-plan.md
python3 scripts/ai_dememory.py sleep plan --json --json-report-path reports/sleep-plan.json
python3 scripts/ai_dememory.py working status --json
python3 scripts/ai_dememory.py sleep apply-reviewed --all
python3 scripts/ai_dememory.py setup health --json
python3 scripts/ai_dememory.py schedule plan --json
python3 scripts/ai_dememory.py schedule plan --json --mode docker --image ai-dememory:local
python3 scripts/ai_dememory.py schedule setup --dry-run
python3 scripts/ai_dememory.py schedule setup --dry-run --mode docker --image ai-dememory:local
python3 scripts/ai_dememory.py schedule cron --json
python3 scripts/ai_dememory.py schedule doctor --json
python3 scripts/ai_dememory.py hooks events
python3 scripts/ai_dememory.py hooks config --client claude
python3 scripts/ai_dememory.py hooks list
python3 scripts/ai_dememory.py hooks captures --json
python3 scripts/ai_dememory.py hooks captures --created-from 2026-06-01 --created-to 2026-06-30 --json
python3 scripts/ai_dememory.py hooks captures --write-report
python3 scripts/ai_dememory.py hooks review --help
python3 scripts/ai_dememory.py hooks archive --json
python3 scripts/ai_dememory.py hooks install --client all --dry-run
python3 scripts/ai_dememory.py eval-recall
python3 scripts/ai_dememory.py recall-fixtures check-miss --query "missed query" --expected-id mem_example --json
python3 scripts/ai_dememory.py capture-miss --query "missed query" --expected-id mem_example --reason "Expected memory was absent." --dry-run
python3 scripts/ai_dememory.py recall-fixtures review-plan --write-report
python3 scripts/ai_dememory.py recall-fixtures packet --write-report
python3 scripts/ai_dememory.py recall-fixtures packet --limit 50 --pending-offset 50 --invalid-offset 50 --write-report
python3 scripts/ai_dememory.py recall-fixtures promote-miss --help
python3 scripts/ai_dememory.py recall-fixtures review-miss --help
python3 scripts/ai_dememory.py export-context
python3 scripts/ai_dememory.py consolidate --dry-run
python3 scripts/ai_dememory.py consolidate --dry-run --report-path reports/consolidation-dry-run.md
python3 scripts/ai_dememory.py review false-positives
python3 scripts/ai_dememory.py review false-positives --report-path reports/false-positives.md
python3 scripts/ai_dememory.py review false-positives --due-only
python3 scripts/ai_dememory.py review stale-false-positives
python3 scripts/ai_dememory.py review conflicts
python3 scripts/ai_dememory.py review conflicts --report-path reports/conflicts.md
python3 scripts/ai_dememory.py review modes
python3 scripts/ai_dememory.py review plan --kind conflict
python3 scripts/ai_dememory.py review recommendation --kind conflict --target-id conf_example --recommendation collect_evidence --rationale "Needs human review." --recommended-by "Local LLM" --json
python3 scripts/ai_dememory.py review recommendations --json
python3 scripts/ai_dememory.py review recommendation-outcome --id rec_example --status accepted --reviewer you --reason reviewed --json
python3 scripts/ai_dememory.py review recommendation-outcomes --json
python3 scripts/ai_dememory.py review recommendation-outcomes --limit 50 --offset 50 --invalid-offset 50 --json
python3 scripts/ai_dememory.py conflict resolve --id conf_example --keep mem_example --recommendation-id rec_example --reviewer you
python3 scripts/ai_dememory.py api --host 127.0.0.1 --port 8765
python3 scripts/ai_dememory.py mcp --stdio
```

Direct script entry points remain available:

```bash
python3 scripts/validate_memory.py
python3 scripts/validate_memory.py --json
python3 scripts/secret_scan.py
python3 scripts/setup_plan.py health --json
python3 scripts/mcp_inventory.py --check-docs
python3 scripts/install_smoke.py --skip-package --docker
python3 scripts/publish_guard.py
python3 scripts/roadmap_status.py status --json
python3 scripts/ci_guard.py
python3 scripts/artifact_guard.py
python3 scripts/pr_template_guard.py
python3 scripts/pr_draft_guard.py
python3 scripts/acceptance_guard.py
python3 scripts/release_evidence.py --json
python3 scripts/manual_acceptance.py status --json
python3 scripts/durable_provenance.py --json
python3 scripts/durable_provenance.py --write-report --report-path reports/durable-provenance.md
python3 scripts/mcp_client_smoke.py --command python3 --command-arg scripts/ai_dememory.py
python3 scripts/api_smoke.py
python3 scripts/index_memory.py
python3 scripts/search_memory.py codex
python3 scripts/context_memory.py codex --budget 2000
python3 scripts/graph_memory.py --json
python3 scripts/http_api.py --host 127.0.0.1 --port 8765
python3 scripts/provider_import.py detect
python3 scripts/setup_plan.py plan --json
python3 scripts/provider_import.py capture markdown --path ./notes.md
python3 scripts/git_lessons.py --git --days 7 --repo .
python3 scripts/git_lessons.py --git --days 7 --repo . --write
python3 scripts/vector_gate.py status
python3 scripts/maintenance.py status
python3 scripts/maintenance.py run --profile daily --report-dir reports/maintenance
python3 scripts/lifecycle.py report --report-path reports/lifecycle.md
python3 scripts/schedule_memory.py setup --dry-run
python3 scripts/hook_event.py config --client codex
python3 scripts/eval_recall.py
python3 scripts/recall_fixtures.py promote-miss --help
python3 scripts/recall_fixtures.py review-plan --write-report
python3 scripts/recall_fixtures.py review-miss --help
python3 scripts/capture_miss.py --query "missed query" --expected-id mem_example --reason "Expected memory was absent." --dry-run
python3 scripts/capture_miss.py --query "missed query" --expected-id mem_example --reason "Expected memory was absent."
python3 scripts/export_context.py
python3 scripts/consolidate_memory.py --dry-run
python3 scripts/consolidate_memory.py --dry-run --report-path reports/consolidation-dry-run.md
python3 scripts/sleep_consolidation.py plan
python3 scripts/sleep_consolidation.py plan --report-path reports/sleep-plan.md
python3 scripts/review_memory.py review false-positives
python3 scripts/review_memory.py review false-positives --report-path reports/false-positives.md
python3 scripts/review_memory.py review stale-false-positives
python3 scripts/review_memory.py review conflicts
python3 scripts/review_memory.py review conflicts --report-path reports/conflicts.md
python3 scripts/review_memory.py review modes
python3 scripts/review_memory.py review plan --kind conflict
```

## Tooling

- `ai_dememory.py`: unified local command dispatcher.
- `doctor.py`: local readiness checks for repo, SQLite FTS5, schema, secret
  scan, index, and MCP definitions.
- `verify_mcp_contract.py`: static MCP capability, tool schema, annotation, and
  prompt definition checks.
- `mcp_inventory.py`: reports MCP protocol/tool/prompt/resource inventory and
  checks documentation for stale tool counts.
- `install_smoke.py`: installs the package in a fresh virtual environment,
  checks v2 CLI surfaces, promotes a synthetic recall miss fixture, and
  optionally verifies the local Docker MCP image.
- `publish_guard.py`: validates the AI-operated tag release, green-CI tagger,
  OIDC, exact-artifact smoke, attestation and confirmation-gated, token-free
  recovery contracts.
- `ci_guard.py`: validates that CI keeps required v2 verification gates.
- `artifact_guard.py`: fails when generated indexes, reports, context exports,
  build outputs, or caches are staged.
- `pr_template_guard.py`: validates that the PR template lists current v2
  validation gates.
- `pr_draft_guard.py`: validates that the draft PR handoff runbook is reusable
  and not pinned to an old pull request.
- `acceptance_guard.py`: validates that manual acceptance checklist items match
  the canonical acceptance registry.
- `release_checklist_guard.py`: validates that the release checklist lists
  current v2 release gates.
- `release_evidence.py`: summarizes automated v2 gates and completed, blocked,
  and remaining manual acceptance evidence.
- `roadmap_status.py`: reports read-only implementation status for the v2
  operational roadmap phases.
- `manual_acceptance.py`: records reviewed manual release acceptance evidence
  and verifies final manual acceptance completion.
- `durable_provenance.py`: audits durable memories for reviewed provenance
  and writes guarded generated reports.
- `release_check.py`: non-runtime v2 release readiness gates.
- `mcp_client_smoke.py`: launches generated MCP client config and verifies
  `initialize`/`ping`.
- `mcp_runtime_smoke.py`: PR-gated MCP stdio runtime smoke checks.
- `api_smoke.py`: starts the local REST API on loopback and verifies health,
  search, graph, proposal, reindex, API-key, and non-loopback safety behavior.
- `validate_memory.py`: validates canonical Markdown memory frontmatter.
- `secret_scan.py`: detects forbidden secret-like material and redacts output.
- `index_memory.py`: parses Markdown and rebuilds `indexes/memory.sqlite`.
- `search_memory.py`: queries SQLite FTS with tags, aliases, recency, confidence,
  pin/type boosts, and stale/archive/disputed penalties.
- `context_memory.py`: assembles token-budgeted session context from ranked
  memory results and working state.
- `working_memory.py`: writes current working snapshots and handoffs.
- `lifecycle.py`: records retrieval and good/bad usefulness outcomes, computes
  generated lifecycle scores, and writes guarded lifecycle reports.
- `graph_memory.py`: builds a generated memory/tag/project/type relationship
  graph.
- `http_api.py`: serves a dependency-free local REST API for health, search,
  graph, proposal writes, and reindexing.
- `provider_import.py`: imports configured LLM provider chat/session files and
  explicit Markdown/text/conversation captures into `inbox/imports/` for review.
- `setup_plan.py`: emits read-only first-run setup command arrays for vault,
  MCP, provider, hook, scheduler, maintenance, acceptance planning, and
  generated review packets.
- `git_lessons.py`: captures review-first project lesson candidates from recent
  git history into `inbox/git-lessons/`.
- `vector_gate.py`: evaluates whether recall fixtures justify a future vector
  search experiment without generating embeddings.
- `maintenance.py`: runs daily/weekly index, graph, weights, recall, cleanup,
  review-due summaries, and guarded maintenance report profiles.
- `schedule_memory.py`: installs, previews, or removes opt-in OS schedules.
- `hook_event.py`: captures small provider hook event metadata into
  `inbox/session-events/` and generates Codex/Claude hook config fragments.
- `eval_recall.py`: evaluates ranked search against curated recall fixtures.
- `recall_fixtures.py`: promotes reviewed recall misses into curated fixtures.
- `capture_miss.py`: previews or writes recall miss proposals under
  `inbox/recall-feedback/`.
- `export_context.py`: writes generated LLM context bundles under `distilled/`.
- `consolidate_memory.py`: writes guarded dry-run review reports under
  `reports/`.
- `sleep_consolidation.py`: plans safe sleep consolidation, writes guarded
  generated reports, and writes review packets under
  `inbox/sleep-consolidation/`.
- `review_memory.py`: writes guarded false-positive, conflict, and
  recommendation outcome reports, records reviewed suppressions, creates
  conflict merge proposals, emits mode-specific review plans, lists advisory
  review recommendations, and records accepted/rejected recommendation artifact
  outcomes.

Generated artifacts are disposable. Markdown under `memories/` remains canonical.
