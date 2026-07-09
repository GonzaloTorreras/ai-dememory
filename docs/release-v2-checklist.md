# v2.0 Release Checklist

Use this checklist before marking the MCP memory toolchain as v2.0-ready.

## Repository State

- [ ] Branch is clean.
- [ ] `docs/pr-draft.md` is a reusable draft PR handoff runbook, not a
  hard-coded historical PR body.
- [ ] `docs/mcp-v2-gap-analysis.md` has been reviewed against the current MCP
  docs.
- [ ] `README.md MCP inventory` matches the server tool count and tool names.
- [ ] `docs/install.md`, `docs/distribution.md`,
  `docs/create-memory-repo.md`, `docs/import-capture.md`, `docs/git-lessons.md`, `docs/vector-migration.md`, `docs/scheduler.md`, `docs/hooks.md`, and
  `docs/codex-plugin.md` match the current package behavior.
- [ ] `docs/roadmap-status.md` matches the current v2 operational roadmap
  status command.
- [ ] `docs/scheduler-plugin-blueprint.md` documents host scheduler ownership,
  plugin artifact shape, MCP setup tools, and hook boundaries.
- [ ] `docs/review-workflows.md` and ADRs document review suppressions,
  conflict reports, and merge proposals.
- [ ] `docs/sleep-consolidation.md` documents safe sleep planning boundaries.
- [ ] `docs/adr/0005-hook-provider-config.md` documents hook config boundaries.
- [ ] `docs/adr/0006-managed-hook-instruction-blocks.md` documents managed
  instruction block behavior.
- [ ] `docs/adr/0007-import-capture-review-candidates.md` documents import
  and capture boundaries.
- [ ] `docs/adr/0008-git-lesson-capture.md` documents git lesson capture.
- [ ] `docs/adr/0009-measured-vector-search-gate.md` documents the vector gate.
- [ ] `docs/adr/0010-mcp-inventory-drift-check.md` documents MCP inventory
  drift checks.
- [ ] `docs/adr/0011-reusable-install-smoke-runner.md` documents reusable
  package and Docker install smoke.
- [ ] `docs/adr/0012-manual-trusted-publishing-guard.md` documents publish
  workflow safety checks.
- [ ] `docs/adr/0236-publish-plan.md` documents read-only manual publish
  planning.
- [ ] `docs/adr/0237-mcp-publish-plan.md` documents read-only MCP publish
  planning.
- [ ] `docs/adr/0238-mcp-publish-plan-smoke.md` documents package and Docker
  smoke coverage for MCP publish planning.
- [ ] `docs/adr/0239-release-evidence-publish-plan-commands.md` documents
  publish-plan commands in release evidence handoffs.
- [ ] `docs/adr/0240-publish-plan-workflow-url.md` documents offline workflow
  URL resolution for publish planning.
- [ ] `docs/adr/0241-plugin-server-only-tool-classification.md` documents the
  plugin enabled-tool and server-only MCP boundary.
- [ ] `docs/adr/0242-acceptance-plan-template-metadata.md` documents reviewer
  and PR URL metadata for manual acceptance plan/template commands.
- [ ] `docs/adr/0243-release-evidence-acceptance-metadata.md` documents
  reviewer and PR URL metadata propagation through release evidence.
- [ ] `docs/adr/0244-acceptance-command-safe-quoting.md` documents safer
  generated acceptance command argument quoting.
- [ ] `docs/adr/0013-v2-release-evidence-report.md` documents release evidence
  reporting.
- [ ] `docs/adr/0194-mcp-release-evidence-report.md` documents read-only MCP
  release evidence report rendering.
- [ ] `docs/adr/0195-maintenance-review-recommendation-summary.md` documents
  maintenance review recommendation queue summaries.
- [ ] `docs/adr/0196-review-recommendation-archive.md` documents CLI-only
  archival for reviewed recommendation artifacts.
- [ ] `docs/adr/0197-review-recommendation-archive-status.md` documents
  read-only archive status for reviewed recommendation artifacts.
- [ ] `docs/adr/0198-review-recommendation-archive-restore.md` documents
  CLI-only restore for one archived recommendation artifact.
- [ ] `docs/adr/0199-mcp-review-recommendation-archive-restore-preview.md`
  documents read-only MCP restore preview.
- [ ] `docs/adr/0200-mcp-review-recommendation-archive-status.md` documents
  read-only MCP archive status.
- [ ] `docs/adr/0201-review-recommendation-recursive-archive-partitions.md`
  documents optional recursive archive partition scans.
- [ ] `docs/adr/0202-review-recommendation-archive-status-pagination.md`
  documents archive status offset pagination.
- [ ] `docs/adr/0203-review-recommendation-archive-invalid-pagination.md`
  documents malformed archive artifact pagination.
- [ ] `docs/adr/0014-generated-mcp-client-config-smoke.md` documents generated
  MCP client config smoke.
- [ ] `docs/adr/0015-durable-provenance-audit.md` documents durable provenance
  auditing.
- [ ] `docs/adr/0016-manual-acceptance-evidence.md` documents manual
  acceptance evidence records.
- [ ] `docs/adr/0017-recall-fixture-promotion.md` documents reviewed recall
  miss promotion.
- [ ] `docs/adr/0018-expanded-install-smoke-v2-commands.md` documents expanded
  package install smoke coverage.
- [ ] `docs/adr/0019-ci-workflow-guard.md` documents CI workflow drift checks.
- [ ] `docs/adr/0020-generated-artifact-stage-guard.md` documents generated
  artifact staging checks.
- [ ] `docs/adr/0021-expanded-mcp-runtime-smoke.md` documents broad runtime
  MCP smoke coverage.
- [ ] `docs/adr/0022-local-rest-api-smoke.md` documents local REST API smoke
  coverage.
- [ ] `docs/adr/0023-pr-template-guard.md` documents pull request template
  validation.
- [ ] `docs/adr/0231-pr-draft-handoff-guard.md` documents draft PR handoff
  validation.
- [ ] `docs/adr/0232-roadmap-status.md` documents roadmap status reporting.
- [ ] `docs/adr/0233-mcp-roadmap-status.md` documents MCP roadmap status
  reporting.
- [ ] `docs/adr/0234-roadmap-status-smoke.md` documents package and Docker
  smoke coverage for roadmap status.
- [ ] `docs/adr/0024-manual-acceptance-checklist-guard.md` documents manual
  acceptance checklist validation.
- [ ] `docs/adr/0025-blocked-manual-acceptance-evidence.md` documents blocked
  manual acceptance evidence reporting.
- [ ] `docs/adr/0026-docker-maintenance-schedule-plan.md` documents Docker
  maintenance schedule planning.
- [ ] `docs/adr/0027-canonical-review-mode-names.md` documents canonical
  review mode names and legacy alias handling.
- [ ] `docs/adr/0028-cron-maintenance-export.md` documents cron maintenance
  export without automatic crontab writes.
- [ ] `docs/adr/0029-manual-acceptance-verify-gate.md` documents final manual
  acceptance verification.
- [ ] `docs/adr/0030-mcp-manual-acceptance-readiness.md` documents read-only
  MCP manual acceptance readiness tools.
- [ ] `docs/adr/0031-adr-quality-guard.md` documents executable ADR structure
  checks.
- [ ] `docs/adr/0032-release-checklist-guard.md` documents executable release
  checklist drift checks.
- [ ] `docs/adr/0033-release-evidence-readiness-summary.md` documents release
  evidence readiness summaries.
- [ ] `docs/adr/0034-recall-fixture-freshness-status.md` documents recall
  fixture freshness reporting.
- [ ] `docs/adr/0035-mcp-recall-fixture-status.md` documents MCP recall
  fixture freshness reporting.
- [ ] `docs/adr/0036-mcp-vector-readiness-status.md` documents MCP vector
  readiness reporting.
- [ ] `docs/adr/0037-mcp-durable-provenance-status.md` documents MCP durable
  provenance reporting.
- [ ] `docs/adr/0038-mcp-working-memory-tools.md` documents MCP generated
  working memory tools.
- [ ] `docs/adr/0039-codex-plugin-working-session-skill.md` documents the
  Codex plugin working-session skill.
- [ ] `docs/adr/0040-mcp-doctor-status.md` documents MCP doctor readiness
  checks.
- [ ] `docs/adr/0041-profile-aware-doctor.md` documents vault versus
  distribution doctor checks.
- [ ] `docs/adr/0042-doctor-profile-summary.md` documents doctor profile
  summary output.
- [ ] `docs/adr/0043-install-smoke-doctor-summary.md` documents installed and
  Docker doctor summary smoke coverage.
- [ ] `docs/adr/0044-docker-client-config-smoke.md` documents generated Docker
  MCP client config smoke coverage.
- [ ] `docs/adr/0045-recall-fixture-review-plan.md` documents the read-only
  weekly recall miss review plan.
- [ ] `docs/adr/0046-mcp-recall-review-plan.md` documents read-only MCP recall
  review planning.
- [ ] `docs/adr/0047-manual-acceptance-plan.md` documents read-only manual
  acceptance planning.
- [ ] `docs/adr/0048-mcp-manual-acceptance-plan.md` documents read-only MCP
  manual acceptance planning.
- [ ] `docs/adr/0049-release-evidence-acceptance-plan.md` documents embedding
  manual acceptance planning in release evidence.
- [ ] `docs/adr/0050-release-evidence-blockers.md` documents structured release
  blockers.
- [ ] `docs/adr/0051-mcp-release-evidence.md` documents read-only MCP release
  evidence.
- [ ] `docs/adr/0052-install-smoke-release-evidence.md` documents installed
  package release-evidence smoke coverage.
- [ ] `docs/adr/0053-docker-smoke-release-evidence.md` documents Docker
  release-evidence smoke coverage.
- [ ] `docs/adr/0054-maintenance-lifecycle-artifacts.md` documents lifecycle
  score artifacts in scheduled maintenance.
- [ ] `docs/adr/0055-maintenance-artifact-status.md` documents generated
  artifact visibility in maintenance status.
- [ ] `docs/adr/0147-maintenance-review-due-summary.md` documents
  false-positive review due counts in maintenance status and reports.
- [ ] `docs/adr/0148-false-positive-due-only-filter.md` documents focused
  false-positive review filtering.
- [ ] `docs/adr/0149-stale-false-positive-suppression-audit.md` documents
  stale false-positive suppression audits.
- [ ] `docs/adr/0150-maintenance-stale-suppression-summary.md` documents stale
  suppression counts in maintenance status and reports.
- [ ] `docs/adr/0151-scheduler-review-due-summary.md` documents review due
  summaries in scheduler status.
- [ ] `docs/adr/0152-maintenance-conflict-review-summary.md` documents
  conflict review counts in maintenance status and reports.
- [ ] `docs/adr/0153-setup-health-summary.md` documents read-only setup health
  summaries.
- [ ] `docs/adr/0154-maintenance-profile-dry-run.md` documents maintenance
  profile dry-runs.
- [ ] `docs/adr/0155-setup-health-maintenance-preflight.md` documents
  maintenance preflight in setup health.
- [ ] `docs/adr/0179-setup-health-validation-status.md` documents validation
  status in setup health.
- [ ] `docs/adr/0180-setup-health-recall-review.md` documents recall review
  status in setup health.
- [ ] `docs/adr/0181-setup-health-context-config.md` documents context config
  status in setup health.
- [ ] `docs/adr/0182-setup-health-manual-acceptance.md` documents manual
  acceptance readiness in setup health.
- [ ] `docs/adr/0183-setup-health-vector-readiness.md` documents vector
  readiness in setup health.
- [ ] `docs/adr/0220-setup-health-generated-packet-archives.md` documents
  generated packet archive status in setup health.
- [ ] `docs/adr/0221-maintenance-generated-packet-archives.md` documents
  generated packet archive cleanup summaries in maintenance status and reports.
- [ ] `docs/adr/0056-install-smoke-maintenance-artifact-status.md` documents
  installed package smoke coverage for maintenance artifact status.
- [ ] `docs/adr/0057-docker-smoke-maintenance-artifact-status.md` documents
  Docker smoke coverage for maintenance artifact status.
- [ ] `docs/adr/0058-manual-acceptance-artifact-guidance.md` documents
  suggested evidence artifacts in manual acceptance plans.
- [ ] `docs/adr/0059-search-match-explanations.md` documents matched evidence
  fields in search explanations.
- [ ] `docs/adr/0060-working-status-summary.md` documents read-only working
  state status summaries.
- [ ] `docs/adr/0061-lifecycle-feedback-receipts.md` documents structured
  mark-seen feedback receipts.
- [ ] `docs/adr/0062-outcome-feedback-receipts.md` documents structured
  outcome feedback receipts.
- [ ] `docs/adr/0063-mcp-auto-context.md` documents MCP auto context query
  behavior.
- [ ] `docs/adr/0064-mcp-conflict-keep-resolution.md` documents reviewed MCP
  keep decisions for conflict review.
- [ ] `docs/adr/0065-mcp-false-positive-ignore-receipts.md` documents MCP
  false-positive ignore receipts.
- [ ] `docs/adr/0066-mcp-schedule-status.md` documents read-only MCP scheduler
  status.
- [ ] `docs/adr/0067-mcp-provider-status.md` documents read-only MCP provider
  import readiness.
- [ ] `docs/adr/0068-plugin-mcp-tool-surface-guard.md` documents the plugin MCP
  enabled-tool drift guard.
- [ ] `docs/adr/0069-plugin-mcp-config-smoke.md` documents checked-in plugin
  MCP config launch smoke.
- [ ] `docs/adr/0070-readme-mcp-inventory-guard.md` documents README MCP
  inventory drift checks.
- [ ] `docs/adr/0071-private-vault-setup-artifact-guard.md` documents private
  vault generated-artifact setup guards.
- [ ] `docs/adr/0072-vault-setup-ci-gate.md` documents vault setup CI and PR
  checklist coverage.
- [ ] `docs/adr/0073-vault-template-export-command.md` documents the CLI
  GitHub vault template export path.
- [ ] `docs/adr/0074-install-smoke-vault-template-export.md` documents
  installed package smoke coverage for vault template export.
- [ ] `docs/adr/0075-docker-smoke-vault-template-export.md` documents Docker
  smoke coverage for vault template export.
- [ ] `docs/adr/0076-publish-workflow-preflight.md` documents manual publish
  workflow preflight gates.
- [ ] `docs/adr/0077-package-build-smoke.md` documents temporary package build
  smoke coverage.
- [ ] `docs/adr/0105-package-build-stale-artifact-preflight.md` documents
  package-build stale generated artifact preflight.
- [ ] `docs/adr/0106-ci-post-smoke-artifact-guard.md` documents the final
  post-smoke CI package build artifact guard.
- [ ] `docs/adr/0107-ci-pr-gated-mcp-runtime-smoke.md` documents PR-gated MCP
  runtime smoke in CI.
- [ ] `docs/adr/0108-docker-vault-template-export-target.md` documents Docker
  vault-template export target validation.
- [ ] `docs/adr/0109-release-evidence-without-git.md` documents graceful
  release-evidence unavailability when `git` is missing.
- [ ] `docs/adr/0127-publish-workflow-smoke-gates.md` documents publish
  workflow install, package build, and Docker smoke gates.
- [ ] `docs/adr/0128-testpypi-acceptance-publish-preflight.md` documents
  TestPyPI manual acceptance evidence from publish workflow preflight.
- [ ] `docs/adr/0129-capture-miss-dry-run.md` documents read-only recall miss
  preview before writing inbox feedback.
- [ ] `docs/adr/0130-recall-miss-candidate-check.md` documents read-only
  recall miss rank checking before capture.
- [ ] `docs/adr/0131-mcp-recall-miss-candidate.md` documents read-only MCP
  recall miss rank checking before capture.
- [ ] `docs/adr/0132-recall-review-candidate-guidance.md` documents recall
  review plan guidance for candidate checks before capture.
- [ ] `docs/adr/0133-scheduler-plugin-blueprint.md` documents the scheduler
  and Codex plugin implementation contract.
- [ ] `docs/adr/0134-mcp-schedule-plan-cron-entries.md` documents reviewed
  cron export entries in MCP scheduler planning.
- [ ] `docs/adr/0229-cli-schedule-plan.md` documents structured CLI scheduler
  planning.
- [ ] `docs/adr/0135-setup-plan-cron-export-commands.md` documents reviewed
  cron export commands in first-run setup planning.
- [ ] `docs/adr/0136-maintenance-provider-readiness.md` documents provider
  import readiness in maintenance status.
- [ ] `docs/adr/0137-provider-import-dry-run.md` documents provider import
  dry-run preview before writing inbox candidates.
- [ ] `docs/adr/0138-provider-import-idempotency.md` documents stable
  provider import fingerprints and duplicate skips.
- [ ] `docs/adr/0139-mcp-git-lessons.md` documents MCP git lesson candidate
  capture.
- [ ] `docs/adr/0140-git-lesson-idempotency.md` documents stable git lesson
  fingerprints and duplicate skips.
- [ ] `docs/adr/0141-hook-event-idempotency.md` documents hook event
  fingerprints and duplicate skips.
- [ ] `docs/adr/0142-scheduler-input-validation.md` documents scheduler time
  and weekday validation.
- [ ] `docs/adr/0143-hook-json-fingerprints.md` documents canonical JSON hook
  payload fingerprints.
- [ ] `docs/adr/0170-hook-capture-review-report.md` documents frontmatter-only
  hook capture review reports.
- [ ] `docs/adr/0171-weekly-maintenance-hook-capture-report.md` documents
  weekly maintenance hook capture report generation.
- [ ] `docs/adr/0172-hook-capture-review-outcomes.md` documents hook capture
  review receipts and due-count closure.
- [ ] `docs/adr/0173-mcp-hook-capture-review.md` documents approval-gated MCP
  hook capture review receipts.
- [ ] `docs/adr/0174-hook-capture-review-filters.md` documents provider,
  event, and review-status filters for hook capture review queues.
- [ ] `docs/adr/0175-hook-capture-archive-reviewed.md` documents CLI-only
  archival for reviewed hook captures.
- [ ] `docs/adr/0176-hook-capture-date-window-filters.md` documents
  frontmatter-only date-window filters for hook capture review queues.
- [ ] `docs/adr/0144-mcp-schedule-validation-status.md` documents stable MCP
  scheduler validation fields.
- [ ] `docs/adr/0145-scheduler-environment-diagnostic.md` documents read-only
  scheduler command availability diagnostics.
- [ ] `docs/adr/0146-false-positive-review-due-status.md` documents
  false-positive suppression due-status fields.
- [ ] `docs/adr/0110-release-evidence-recall-freshness.md` documents recall
  fixture freshness in release evidence.
- [ ] `docs/adr/0111-release-evidence-recall-review-plan.md` documents the
  release-evidence recall review plan.
- [ ] `docs/adr/0184-release-evidence-vector-readiness.md` documents the
  release-evidence vector readiness gate.
- [ ] `docs/adr/0185-release-evidence-setup-health-summary.md` documents the
  release-evidence setup health summary.
- [ ] `docs/adr/0222-release-evidence-maintenance-summary.md` documents the
  release-evidence maintenance summary.
- [ ] `docs/adr/0223-release-evidence-next-actions.md` documents top-level
  release evidence next actions.
- [ ] `docs/adr/0235-release-evidence-handoff-commands.md` documents
  structured release handoff command arrays.
- [ ] `docs/adr/0224-maintenance-artifact-freshness.md` documents generated
  artifact freshness in maintenance, setup health, and release evidence.
- [ ] `docs/adr/0112-recall-promotion-closes-source-miss.md` documents source
  miss closure and pass validation during recall fixture promotion.
- [ ] `docs/adr/0113-recall-miss-review-outcomes.md` documents rejected and
  dismissed recall miss review outcomes.
- [ ] `docs/adr/0114-recall-review-resolved-summary.md` documents bounded
  resolved recall miss summaries.
- [ ] `docs/adr/0115-recall-review-plan-report.md` documents generated recall
  review report artifacts.
- [ ] `docs/adr/0116-manual-acceptance-plan-report.md` documents generated
  manual acceptance planning artifacts.
- [ ] `docs/adr/0186-manual-acceptance-packet.md` documents generated manual
  acceptance review packets.
- [ ] `docs/adr/0192-mcp-manual-acceptance-packet.md` documents read-only MCP
  manual acceptance packet rendering.
- [ ] `docs/adr/0208-manual-acceptance-packet-pagination.md` documents manual
  acceptance packet pagination.
- [ ] `docs/adr/0209-manual-acceptance-packet-metadata.md` documents optional
  manual acceptance packet reviewer and PR URL metadata.
- [ ] `docs/adr/0211-manual-acceptance-packet-archive.md` documents
  timestamped manual acceptance packet archives.
- [ ] `docs/adr/0213-manual-acceptance-packet-archive-status.md` documents
  read-only manual acceptance packet archive status.
- [ ] `docs/adr/0215-mcp-manual-acceptance-packet-archive-status.md`
  documents read-only MCP manual acceptance packet archive status.
- [ ] `docs/adr/0187-recall-review-packet.md` documents generated recall
  review packets.
- [ ] `docs/adr/0193-mcp-recall-review-packet.md` documents read-only MCP
  recall review packet rendering.
- [ ] `docs/adr/0207-recall-review-packet-pagination.md` documents recall
  review packet pagination.
- [ ] `docs/adr/0210-recall-review-packet-metadata.md` documents optional
  recall review packet reviewer and PR URL metadata.
- [ ] `docs/adr/0212-recall-review-packet-archive.md` documents timestamped
  recall review packet archives.
- [ ] `docs/adr/0214-recall-review-packet-archive-status.md` documents
  read-only recall review packet archive status.
- [ ] `docs/adr/0216-mcp-recall-review-packet-archive-status.md` documents
  read-only MCP recall review packet archive status.
- [ ] `docs/adr/0218-generated-packet-archive-retention-plan.md` documents
  read-only generated packet archive retention plans.
- [ ] `docs/adr/0117-setup-plan-generated-reports.md` documents generated
  report commands in setup planning.
- [ ] `docs/adr/0217-setup-plan-generated-archive-status.md` documents
  generated archive status commands in setup planning.
- [ ] `docs/adr/0219-setup-plan-generated-archive-retention.md` documents
  generated archive retention commands in setup planning.
- [ ] `docs/adr/0118-release-evidence-report-path-guard.md` documents
  release-evidence report path validation and rendered secret scanning.
- [ ] `docs/adr/0119-vector-readiness-report-path-guard.md` documents vector
  readiness report path validation and rendered secret scanning.
- [ ] `docs/adr/0120-durable-provenance-report-path-guard.md` documents
  durable provenance report path validation and rendered secret scanning.
- [ ] `docs/adr/0121-lifecycle-report-path-guard.md` documents lifecycle
  report path validation and rendered secret scanning.
- [ ] `docs/adr/0122-sleep-plan-report-path-guard.md` documents sleep plan
  report path validation and rendered secret scanning.
- [ ] `docs/adr/0225-sleep-dry-run-propose-aliases.md` documents top-level
  sleep dry-run and propose aliases.
- [ ] `docs/adr/0226-sleep-apply-reviewed-alias.md` documents the top-level
  sleep apply-reviewed alias.
- [ ] `docs/adr/0227-weekly-maintenance-sleep-plan-report.md` documents weekly
  maintenance sleep plan report generation.
- [ ] `docs/adr/0230-schedule-plan-smoke.md` documents package and Docker
  schedule-plan smoke validation.
- [ ] `docs/adr/0123-consolidation-report-path-guard.md` documents
  consolidation report path validation and rendered secret scanning.
- [ ] `docs/adr/0124-review-report-path-guard.md` documents false-positive and
  conflict report path validation and rendered secret scanning.
- [ ] `docs/adr/0125-maintenance-report-dir-guard.md` documents maintenance
  report directory validation and rendered secret scanning.
- [ ] `docs/adr/0126-recall-review-report-secret-scan.md` documents rendered
  secret scanning for generated recall review reports.
- [ ] `docs/adr/0078-provider-setup-plan.md` documents read-only provider setup
  planning.
- [ ] `docs/adr/0228-provider-configure-dry-run.md` documents provider
  configure dry-run previews.
- [ ] `docs/adr/0079-local-setup-plan.md` documents read-only local first-run
  setup planning.
- [ ] `docs/adr/0080-manual-acceptance-template.md` documents read-only manual
  acceptance evidence templates.
- [ ] `docs/adr/0081-mcp-false-positive-unignore.md` documents MCP
  false-positive unignore receipts.
- [ ] `docs/adr/0082-mcp-review-mode-configuration.md` documents MCP
  review-mode configuration receipts.
- [ ] `docs/adr/0083-mcp-conflict-dismiss-receipts.md` documents MCP conflict
  dismiss receipts.
- [ ] `docs/adr/0084-mcp-conflict-merge-proposal-receipts.md` documents MCP
  conflict merge-proposal receipts.
- [ ] `docs/adr/0085-mcp-conflict-keep-reviewer-receipts.md` documents MCP
  conflict keep reviewer receipts.
- [ ] `docs/adr/0086-plugin-review-receipt-tools.md` documents plugin review
  receipt tool exposure.
- [ ] `docs/adr/0188-review-recommendation-artifacts.md` documents advisory
  review recommendation artifacts.
- [ ] `docs/adr/0189-review-recommendation-status.md` documents read-only
  advisory recommendation status.
- [ ] `docs/adr/0190-review-recommendation-outcome-links.md` documents linking
  accepted review outcomes back to advisory recommendations.
- [ ] `docs/adr/0191-review-recommendation-outcome-status.md` documents
  accepted/rejected recommendation artifact outcomes.
- [ ] `docs/adr/0204-review-recommendation-outcome-report.md` documents the
  generated recommendation outcome sign-off report.
- [ ] `docs/adr/0205-mcp-review-recommendation-outcome-report.md` documents
  read-only MCP rendering for the recommendation outcome sign-off report.
- [ ] `docs/adr/0206-review-recommendation-outcome-report-pagination.md`
  documents active recommendation outcome report pagination.
- [ ] `docs/adr/0087-mcp-client-enabled-tools-smoke.md` documents MCP client
  enabled-tool smoke verification.
- [ ] `docs/adr/0088-mcp-client-tools-list-pagination-smoke.md` documents MCP
  client tools-list pagination smoke.
- [ ] `docs/adr/0089-mcp-runtime-list-pagination-smoke.md` documents MCP
  runtime list pagination smoke.
- [ ] `docs/adr/0090-mcp-runtime-list-identity-smoke.md` documents MCP runtime
  list identity uniqueness smoke.
- [ ] `docs/adr/0091-mcp-client-single-session-pagination-smoke.md` documents
  single-session MCP client tools-list pagination smoke.
- [ ] `docs/adr/0092-mcp-client-initialized-notification-smoke.md` documents
  MCP client initialized-notification smoke.
- [ ] `docs/adr/0093-mcp-runtime-initialized-notification-smoke.md` documents
  MCP runtime initialized-notification smoke.
- [ ] `docs/adr/0094-mcp-client-response-id-smoke.md` documents MCP client
  response-id matching smoke.
- [ ] `docs/adr/0095-mcp-runtime-response-id-smoke.md` documents MCP runtime
  response-id matching smoke.
- [ ] `docs/adr/0096-install-smoke-initialized-notification.md` documents
  install smoke direct MCP initialized-notification coverage.
- [ ] `docs/adr/0097-install-smoke-response-id.md` documents install smoke
  direct MCP response-id matching.
- [ ] `docs/adr/0098-install-smoke-missing-response-diagnostics.md` documents
  install smoke missing response diagnostics.
- [ ] `docs/adr/0099-install-smoke-unexpected-response-id.md` documents
  install smoke unexpected response-id diagnostics.
- [ ] `docs/adr/0100-install-smoke-invalid-response-id.md` documents install
  smoke invalid response-id diagnostics.
- [ ] `docs/adr/0101-install-smoke-duplicate-response-id.md` documents install
  smoke duplicate response-id diagnostics.
- [ ] `docs/adr/0102-install-smoke-result-field-diagnostics.md` documents
  install smoke result-field diagnostics.
- [ ] `docs/adr/0103-install-smoke-result-type-diagnostics.md` documents
  install smoke result-type diagnostics.
- [ ] `docs/adr/0104-install-smoke-protocol-version-diagnostics.md` documents
  install smoke initialize protocol-version diagnostics.
- [ ] `AGENTS.md` and `CLAUDE.md` contain current ai-dememory managed hook
  instruction blocks.
- [ ] `LICENSE` and `pyproject.toml` both identify Apache-2.0.
- [ ] `.github/workflows/publish.yml` is manual-only and uses PyPI Trusted
  Publishing.
- [ ] `.github/workflows/publish.yml` preflight runs installed package smoke,
  package build smoke with `--check-clean`, and Docker local MCP smoke before
  building distributions.
- [ ] `.github/workflows/ci.yml` includes package install, recall quality, and
  Docker local MCP smoke coverage.
- [ ] `.github/workflows/ci.yml` runs `python scripts/ai_dememory.py
  vault-setup-guard`.
- [ ] `vault-template/` matches `ai_dememory_tool/templates/vault/`.
- [ ] `ai-dememory vault-template export ./ai-dememory-vault-template`
  exports the packaged vault template for a separate private GitHub template
  repository.
- [ ] `.agents/plugins/marketplace.json` exposes `plugins/ai-dememory/`.
- [ ] `plugins/ai-dememory/` includes plugin manifest, MCP config, hooks, and
  setup/recall/working-session/review/maintenance skills.
- [ ] `plugins/ai-dememory/.mcp.json` enabled tools match the documented
  review-first plugin MCP surface, including false-positive, conflict, and
  review-mode receipt tools.
- [ ] Every MCP tool is classified as either plugin-enabled or server-only, and
  `docs/codex-plugin.md` documents the server-only MCP tools.
- [ ] `python3 scripts/ai_dememory.py mcp-client-smoke --config plugins/ai-dememory/.mcp.json --command python3 --command-arg scripts/ai_dememory.py`
  verifies plugin `enabled_tools` against paginated `tools/list`.
- [ ] Plugin `enabled_tools` smoke follows cursors in one single stdio session
  for paginated `tools/list`.
- [ ] MCP client config smoke sends `notifications/initialized` before ping and
  tool listing.
- [ ] MCP client config smoke matches JSON-RPC responses by id and skips server
  notifications.
- [ ] `quality/recall-fixtures.json` contains representative recall fixtures.
- [ ] Private vault setup does not stage generated artifact directories.
- [ ] Draft PR exists from `codex/memory-mvp` to `main`.
- [ ] CI passes on the PR.
- [ ] No generated SQLite, report, cache, or distilled output is staged.

## Static Checks

- [ ] `python3 scripts/ai_dememory.py doctor`
- [ ] `python3 scripts/ai_dememory.py doctor --json --summary`
- [ ] `python3 scripts/ai_dememory.py verify-mcp`
- [ ] `python3 scripts/ai_dememory.py mcp-inventory --check-docs`
- [ ] `python3 scripts/ai_dememory.py ci-guard`
- [ ] `python3 scripts/ai_dememory.py artifact-guard`
- [ ] CI runs `python scripts/ai_dememory.py package-build-smoke --check-clean`
  after install, package build, and Docker smoke.
- [ ] `python3 scripts/ai_dememory.py vault-setup-guard`
- [ ] `python3 scripts/ai_dememory.py pr-template-guard`
- [ ] `python3 scripts/ai_dememory.py pr-draft-guard`
- [ ] `python3 scripts/ai_dememory.py acceptance-guard`
- [ ] `python3 scripts/ai_dememory.py adr-guard`
- [ ] `python3 scripts/ai_dememory.py release-checklist-guard`
- [ ] `python3 scripts/ai_dememory.py release-check`
- [ ] `python3 scripts/ai_dememory.py roadmap status --json`
- [ ] CI runs `python scripts/ai_dememory.py release-check --strict` on pull
  requests with `AI_DEMEMORY_PR_URL` set from the pull request URL.
- [ ] CI runs `python scripts/ai_dememory.py mcp-smoke` on pull requests with
  `AI_DEMEMORY_PR_URL` set from the pull request URL.
- [ ] `python3 scripts/ai_dememory.py api-smoke`
- [ ] `python3 scripts/ai_dememory.py acceptance template --item mcp-client-installed --json`
- [ ] `python3 scripts/ai_dememory.py validate`
- [ ] `python3 scripts/ai_dememory.py validate --json`
- [ ] `python3 scripts/ai_dememory.py secret-scan`
- [ ] `python3 scripts/ai_dememory.py eval-recall`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures status --json`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures check-miss --query
  "missed query" --expected-id mem_example --json` reports whether the expected
  memory is outside the accepted rank without writing recall feedback.
- [ ] `python3 scripts/ai_dememory.py capture-miss --query "missed query"
  --expected-id mem_example --reason "Expected memory was absent." --dry-run`
  renders a recall miss without writing `inbox/recall-feedback/`.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures review-plan --json`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures review-plan
  --write-report`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures packet --write-report`
  writes generated review guidance without promoting fixtures.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures packet --limit 50
  --pending-offset 50 --invalid-offset 50 --write-report` pages pending and
  malformed recall miss packet sections.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures packet --reviewer
  "Reviewer" --pr-url "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>"
  --write-report` renders packet handoff metadata without promoting fixtures.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures packet --archive --json`
  writes a timestamped generated packet copy under
  `reports/recall-review-packets/` without promoting fixtures.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures packet-archive-status
  --json` lists generated recall packet snapshots without promoting fixtures.
- [ ] `memory.recall_review_packet_archive_status` lists generated recall packet
  snapshots without writing files, fixtures, or miss outcomes.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures
  packet-archive-retention-plan --json` previews generated recall packet
  cleanup candidates without deleting files.
- [ ] `memory.recall_review_packet_archive_retention_plan` previews generated
  recall packet cleanup candidates without writing files, fixtures, deleting
  files, or closing miss outcomes.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures promote-miss` marks the
  source miss as `status: promoted`.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures promote-miss` validates
  that the fixture passes before committing it.
- [ ] `python3 scripts/ai_dememory.py recall-fixtures promote-miss --help`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures review-miss` marks a
  reviewed miss as `rejected` or `dismissed` without writing fixtures.
- [ ] `python3 scripts/ai_dememory.py lifecycle scores --json`
- [ ] `python3 scripts/ai_dememory.py lifecycle report`
- [ ] `python3 scripts/ai_dememory.py lifecycle report --report-path
  reports/lifecycle.md`
- [ ] `python3 scripts/ai_dememory.py mark-seen --id mem_preferences_20260614
  --query ai-dememory --json` returns `lifecycle_updated`
- [ ] `python3 scripts/ai_dememory.py outcome --last --good --json` returns
  `target_source`, `positive_outcomes`, and `lifecycle_updated`.
- [ ] Daily maintenance refreshes lifecycle score artifacts:
  `indexes/memory-lifecycle.json` and `reports/lifecycle.md`.
- [ ] `python3 scripts/ai_dememory.py sleep plan`
- [ ] `python3 scripts/ai_dememory.py sleep plan --report-path
  reports/sleep-plan.md`
- [ ] `python3 scripts/ai_dememory.py sleep plan --json --json-report-path
  reports/sleep-plan.json`
- [ ] `python3 scripts/ai_dememory.py sleep --dry-run --json`
- [ ] `python3 scripts/ai_dememory.py sleep --propose --id sleep_... --json`
- [ ] `python3 scripts/ai_dememory.py sleep --apply-reviewed --id sleep_...
  --json`
- [ ] `python3 scripts/ai_dememory.py working status --json`
- [ ] `python3 scripts/ai_dememory.py hooks config --client codex`
- [ ] `python3 scripts/ai_dememory.py hooks config --client claude`
- [ ] `python3 scripts/ai_dememory.py hooks captures --json`
- [ ] `python3 scripts/ai_dememory.py hooks captures --write-report`
- [ ] `python3 scripts/ai_dememory.py hooks archive --json`
- [ ] `python3 scripts/ai_dememory.py hooks install --client all --dry-run`
- [ ] `python3 scripts/ai_dememory.py setup plan --json`
- [ ] `python3 scripts/ai_dememory.py providers plan --json`
- [ ] `python3 scripts/ai_dememory.py install-smoke`
- [ ] Installed `ai-dememory roadmap status --json` validates `phase_count`,
  read-only side-effect flags, status counts, and stable phase numbers,
  including the expected missing-evidence exit from a plain vault.
- [ ] The install smoke direct MCP payload sends `notifications/initialized`
  before `ping`.
- [ ] The install smoke direct MCP validator matches JSON-RPC responses by id
  and skips server notifications.
- [ ] The install smoke direct MCP validator reports missing initialize and ping
  responses with explicit id-specific errors.
- [ ] The install smoke direct MCP validator rejects unexpected integer response
  ids.
- [ ] The install smoke direct MCP validator rejects non-integer response ids.
- [ ] The install smoke direct MCP validator rejects duplicate response ids.
- [ ] The install smoke direct MCP validator rejects responses missing result or
  error.
- [ ] The install smoke direct MCP validator rejects non-object initialize and
  ping results.
- [ ] The install smoke direct MCP validator reports missing and invalid
  initialize protocolVersion values.
- [ ] `python3 scripts/ai_dememory.py package-build-smoke`
- [ ] package-build-smoke refuses stale generated package build artifacts.
- [ ] `python3 scripts/ai_dememory.py publish-guard`
- [ ] `python3 scripts/ai_dememory.py publish-plan --repository testpypi --json`
- [ ] `python3 scripts/ai_dememory.py publish-plan --repository pypi --json`
  reminds maintainers to publish to TestPyPI first.
- [ ] `python3 scripts/ai_dememory.py release-evidence --json`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `manual_acceptance_plan`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `release_blockers`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `next_actions`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `recall_fixture_freshness`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `recall_fixture_review_plan`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `vector_readiness`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `setup_health_summary`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `maintenance_summary`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `artifact_freshness`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes recall
  review `candidate_check_command`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  recall review `resolved_count`
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` includes
  `handoff_commands` for release evidence, manual acceptance, recall review,
  strict release evidence, publish-plan, and publish guard handoff steps.
- [ ] `handoff_commands` separates read-only `payload_*` flags from
  `command_side_effects`, with generated report commands marked
  `writes_files=true` and publish-plan commands marked as local read-only
  inspection plus non-publishing.
- [ ] `handoff_commands.commands.publish_plan_testpypi` and
  `handoff_commands.commands.publish_plan_pypi` include `--pr-url` placeholders
  or the current PR URL.
- [ ] `handoff_commands.commands.acceptance_plan` and
  `handoff_commands.commands.acceptance_template` include `--reviewer` and
  `--pr-url` placeholders or the current metadata.
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` reports stale
  recall fixture provenance, and adds a `recall_fixture_review` blocker only
  when current eval is unavailable or failing, or when pending/invalid recall
  miss files exist.
- [ ] `python3 scripts/ai_dememory.py release-evidence --json` reports a
  `vector_readiness_review` blocker when measured recall failures make a vector
  experiment eligible for review.
- [ ] `python3 scripts/ai_dememory.py release-evidence --strict`
- [ ] `python3 scripts/ai_dememory.py release-evidence --write-report --report-path
  reports/v2-release-evidence.md`
- [ ] `python3 scripts/ai_dememory.py release-evidence --reviewer "Reviewer"
  --pr-url "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" --json`
  pre-fills embedded manual acceptance plan and handoff commands without
  recording evidence.
- [ ] `python3 scripts/ai_dememory.py acceptance status --json`
- [ ] `python3 scripts/ai_dememory.py acceptance plan --json`
- [ ] `python3 scripts/ai_dememory.py acceptance plan --reviewer "Reviewer"
  --pr-url "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" --json`
  pre-fills record commands without recording evidence.
- [ ] `python3 scripts/ai_dememory.py acceptance plan --write-report`
- [ ] `python3 scripts/ai_dememory.py acceptance template --item
  mcp-client-installed --reviewer "Reviewer" --pr-url
  "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" --json` pre-fills the
  reviewed-by and PR artifact fields without recording evidence.
- [ ] `python3 scripts/ai_dememory.py acceptance packet --write-report`
- [ ] `python3 scripts/ai_dememory.py acceptance packet --limit 50 --offset
  50 --write-report` pages incomplete manual acceptance packet items.
- [ ] `python3 scripts/ai_dememory.py acceptance packet --reviewer "Reviewer"
  --pr-url "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>"
  --write-report` renders packet handoff metadata without recording evidence.
- [ ] `python3 scripts/ai_dememory.py acceptance packet --archive --json`
  writes a timestamped generated packet copy under
  `reports/manual-acceptance-packets/` without recording evidence.
- [ ] `python3 scripts/ai_dememory.py acceptance packet-archive-status --json`
  lists generated packet snapshots without recording evidence.
- [ ] `memory.acceptance_packet_archive_status` lists generated packet
  snapshots without writing files or recording evidence.
- [ ] `python3 scripts/ai_dememory.py acceptance
  packet-archive-retention-plan --json` previews generated packet cleanup
  candidates without deleting files.
- [ ] `memory.acceptance_packet_archive_retention_plan` previews generated
  packet cleanup candidates without writing files, deleting files, or recording
  evidence.
- [ ] `python3 scripts/ai_dememory.py acceptance plan --json` includes
  `suggested_artifacts`
- [ ] `python3 scripts/ai_dememory.py acceptance verify --json`
- [ ] `python3 scripts/ai_dememory.py mcp-client-smoke --command python3 --command-arg scripts/ai_dememory.py`
- [ ] `python3 scripts/ai_dememory.py mcp-client-smoke --config plugins/ai-dememory/.mcp.json --command python3 --command-arg scripts/ai_dememory.py`
- [ ] `python3 scripts/ai_dememory.py provenance --json`
- [ ] `python3 scripts/ai_dememory.py provenance --write-report --report-path
  reports/durable-provenance.md`
- [ ] `python3 scripts/ai_dememory.py capture text --stdin --title "Smoke capture"`
- [ ] `python3 scripts/ai_dememory.py learn --git --days 7 --repo . --dry-run`
- [ ] `python3 scripts/ai_dememory.py vector status`
- [ ] `python3 scripts/ai_dememory.py vector status --write-report --report-path
  reports/vector-readiness.md`
- [ ] `python3 scripts/ai_dememory.py review false-positives`
- [ ] `python3 scripts/ai_dememory.py review false-positives --report-path
  reports/false-positives.md`
- [ ] `python3 scripts/ai_dememory.py review false-positives --due-only`
  writes a focused report with only due suppressions.
- [ ] `python3 scripts/ai_dememory.py review stale-false-positives` reports
  ignored false-positive ids whose current scanner finding disappeared.
- [ ] `python3 scripts/ai_dememory.py review conflicts`
- [ ] `python3 scripts/ai_dememory.py review conflicts --report-path
  reports/conflicts.md`
- [ ] `python3 scripts/ai_dememory.py review modes`
- [ ] `python3 scripts/ai_dememory.py review plan --kind conflict`
- [ ] `python3 scripts/ai_dememory.py review recommendation --kind conflict`
  writes advisory recommendation artifacts without applying review decisions.
- [ ] `python3 scripts/ai_dememory.py review recommendations --json` lists
  advisory recommendation artifacts without writing files.
- [ ] `python3 scripts/ai_dememory.py review recommendation-outcome --id
  rec_example --status accepted --reviewer you --reason reviewed --json`
  records accepted/rejected recommendation status without applying outcomes.
- [ ] `python3 scripts/ai_dememory.py review recommendation-outcomes --json`
  writes a generated outcome report without applying review decisions.
- [ ] `python3 scripts/ai_dememory.py review recommendation-outcomes --limit
  50 --offset 50 --invalid-offset 50 --json` pages reviewed recommendation
  outcomes and malformed active artifacts without applying review decisions.
- [ ] `python3 scripts/ai_dememory.py review recommendations-archive --json`
  previews accepted/rejected recommendation archival without moving files.
- [ ] `python3 scripts/ai_dememory.py review recommendations-archive --apply
  --json` moves only reviewed recommendation artifacts to
  `archive/review-recommendations/`.
- [ ] `python3 scripts/ai_dememory.py review recommendations-archive-status
  --json` lists archived recommendation artifacts without moving files.
- [ ] `python3 scripts/ai_dememory.py review recommendations-archive-status
  --limit 50 --invalid-offset 50 --json` pages malformed archived
  recommendation artifacts without moving files.
- [ ] `python3 scripts/ai_dememory.py review recommendations-archive-restore
  --id rec_example --json` previews restoring one archived recommendation
  artifact without moving files or applying decisions.
- [ ] `python3 scripts/ai_dememory.py conflict resolve --id conf_example --keep
  mem_example --recommendation-id rec_example --reviewer you` validates
  recommendation links before writing review state.
- [ ] `python3 -m compileall -q scripts mcp/server ai_dememory_tool`
- [ ] `python3 -m unittest discover -s tests`

## Package Install Smoke

- [ ] Build/install the package in a fresh virtual environment.
- [ ] `ai-dememory install-smoke` passes from the distribution checkout.
  It covers provenance, acceptance status, recall fixture promotion, generated
  MCP config, read-only setup planning, doctor profile summary, CLI auto
  context from generated working memory, scheduler plan payload validation,
  maintenance artifact status, vault template export,
  MCP release-evidence unavailability in a fresh vault, checked-in plugin MCP
  config launch, and MCP `initialize`/`notifications/initialized`/`ping` while
  matching JSON-RPC responses by id, reporting missing responses explicitly, and
  rejecting unexpected, non-integer, duplicate, result-less, and non-object
  result responses, with explicit initialize protocolVersion diagnostics.
- [ ] `ai-dememory install-smoke` removes generated package build metadata it
  creates without deleting paths that already existed before the smoke.
- [ ] `ai-dememory init <temp-vault>` writes the vault template.
- [ ] `ai-dememory vault-template export <temp-template-repo>` writes the
  packaged vault template, including hidden config files.
- [ ] `ai-dememory package-build-smoke` builds wheel and source distribution
  into temporary storage and runs `twine check` without leaving `dist/`
  artifacts in the repository.
- [ ] `ai-dememory package-build-smoke` fails fast when stale `build/`,
  `dist/`, or `ai_dememory.egg-info/` paths already exist in the checkout.
- [ ] From that vault, `ai-dememory doctor` succeeds with only an initial
  missing-index warning.
- [ ] From that vault, `ai-dememory validate`, `ai-dememory secret-scan`, and
  `ai-dememory index` succeed.
- [ ] `ai-dememory mcp-config --client codex` emits a config with
  `AI_DEMEMORY_ROOT` pointing at the vault.
- [ ] `ai-dememory setup plan --json` returns first-run setup commands without
  writing files, installing hooks, installing schedules, reading provider files,
  or writing import candidates.
- [ ] `python3 scripts/ai_dememory.py setup health --json` returns setup
  health without running commands or writing files.
- [ ] `python3 scripts/ai_dememory.py setup health --json` includes
  `validation_status`.
- [ ] `python3 scripts/ai_dememory.py setup health --json` includes
  `context_config`.
- [ ] `python3 scripts/ai_dememory.py setup health --json` includes
  `manual_acceptance`.
- [ ] `python3 scripts/ai_dememory.py setup health --json` includes
  `vector_readiness`.
- [ ] `python3 scripts/ai_dememory.py setup health --json` includes
  `recall_review`.
- [ ] `python3 scripts/ai_dememory.py setup health --json` includes
  `generated_packet_archives`.
- [ ] `python3 scripts/ai_dememory.py setup health --json` includes
  maintenance preflight commands and artifact targets without reading provider
  files.
- [ ] `ai-dememory setup plan --json` includes `generated_reports` commands
  for recall review, recall review packet, manual acceptance, manual acceptance
  packet, hook capture review, and release evidence handoffs.
- [ ] `ai-dememory setup plan --json` includes `generated_archive_status`
  commands for recall and manual acceptance packet archive inspection.
- [ ] `ai-dememory setup plan --json` includes `generated_archive_retention`
  commands for recall and manual acceptance packet archive retention previews.
- [ ] `ai-dememory setup plan --json` includes installed and Docker
  `schedule plan --json` command arrays without writing scheduler state.
- [ ] `ai-dememory setup plan --json` includes installed and Docker
  `schedule cron` command arrays without writing scheduler state.
- [ ] Installed `ai-dememory mcp --stdio` accepts
  `initialize`/`notifications/initialized`/`ping` with response-id matching.
- [ ] Installed `ai-dememory mcp-client-smoke` launches generated installed
  CLI config, sends `notifications/initialized`, and responds to `initialize`
  and `ping`.
- [ ] Installed `ai-dememory mcp-client-smoke --config
  plugins/ai-dememory/.mcp.json --command <installed-ai-dememory>` launches
  the checked-in plugin config, sends `notifications/initialized`, and responds
  to `initialize` and `ping`.
- [ ] Installed `ai-dememory mcp --call memory.release_evidence --args "{}"`
  returns `available=false` from a fresh vault and explains that release
  evidence requires a distribution checkout.
- [ ] Installed `ai-dememory mcp --call memory.publish_plan --args "{}"`
  returns TestPyPI dispatch inputs, preflight commands, and false publish
  side-effect flags from a fresh vault.
- [ ] `ai-dememory mcp-config --mode docker --client codex` emits a Docker
  stdio command with the vault bind-mounted at `/memory`.
- [ ] `ai-dememory hooks config --client codex` emits Codex hook commands
  pointing at the vault.
- [ ] `ai-dememory hooks config --client claude` emits Claude Code hook
  commands pointing at the vault.
- [ ] `ai-dememory hooks install --client all --dry-run` previews managed
  `AGENTS.md` and `CLAUDE.md` instruction blocks without writing files.
- [ ] `ai-dememory hooks captures --json` reports frontmatter-only hook
  capture counts without reading raw payload bodies.
- [ ] `ai-dememory hooks captures --provider <provider> --event <event>
  --review-status pending --json` filters hook capture summaries without
  reading raw payload bodies.
- [ ] `ai-dememory hooks captures --created-from <date> --created-to <date>
  --json` filters hook capture summaries by frontmatter dates.
- [ ] `ai-dememory hooks captures --write-report` writes a path-bounded,
  secret-scanned Markdown review report under the vault.
- [ ] `ai-dememory hooks review --path <capture> --status dismissed
  --reviewed-by <name> --reason <reason>` records reviewed hook capture
  metadata under `inbox/session-events/` and returns
  `canonical_memory_updated=false`.
- [ ] `ai-dememory hooks archive --json` previews moving resolved hook
  captures to `archive/session-events/` without writing files.
- [ ] `ai-dememory hooks archive --apply --min-reviewed-days <days> --json`
  moves only resolved hook captures under `archive/session-events/`.
- [ ] `memory.hook_capture_review` returns a structured receipt with reviewer
  metadata, records only under `inbox/session-events/`, and returns
  `canonical_memory_updated=false`.
- [ ] MCP `memory.hook_status` supports `capture_provider`, `capture_event`,
  and `capture_review_status` filters while remaining read-only.
- [ ] MCP `memory.hook_status` supports `capture_created_from`,
  `capture_created_to`, `capture_review_after_from`, and
  `capture_review_after_to` while remaining read-only.
- [ ] Repeated hook captures with the same provider, event, and payload
  fingerprint reuse the existing inbox file.
- [ ] Equivalent JSON hook payloads with different formatting or key order reuse
  the existing inbox file.
- [ ] `ai-dememory providers detect` runs without mutating provider folders.
- [ ] `ai-dememory providers plan --json` returns reviewable configure/import
  commands without reading provider files or writing import candidates.
- [ ] `ai-dememory providers configure codex --path <path> --dry-run --json`
  previews normalized provider config without writing `.ai-dememory.toml`,
  reading provider files, or writing import candidates.
- [ ] MCP `memory.providers_status` reports configured provider import
  readiness without reading provider files or writing import candidates.
- [ ] MCP `memory.providers_plan` reports provider setup commands without
  configuring providers, reading provider files, or writing import candidates,
  and includes `configure_dry_run_command` for reviewed folder selection.
- [ ] `ai-dememory capture markdown --path <file>` writes only to
  `inbox/imports/markdown/`.
- [ ] `ai-dememory learn --git --repo <repo> --dry-run` previews git lesson
  candidates without writing canonical memory.
- [ ] Repeated git lesson capture skips candidates with the same stable
  fingerprint instead of writing duplicate inbox files.
- [ ] `ai-dememory vector status` reports `not_justified` until measured
  recall failures pass the configured gate.
- [ ] `ai-dememory schedule plan --json` returns platform scheduler commands,
  cron entries, and side-effect flags without writing scheduler state.
- [ ] Installed `ai-dememory schedule plan --json` validates scheduler
  commands, cron entries, and side-effect flags in package install smoke.
- [ ] `ai-dememory schedule plan --json --mode docker --image
  ai-dememory:local` previews Docker maintenance commands without writing
  scheduler state.
- [ ] `ai-dememory schedule setup --dry-run` does not write scheduler state.
- [ ] `ai-dememory schedule setup --dry-run --mode docker --image
  ai-dememory:local` previews Docker maintenance without writing scheduler
  state.
- [ ] `ai-dememory schedule cron --json` exports cron lines without writing
  scheduler state.
- [ ] Scheduler times use 24-hour `HH:MM`, weekly days are explicit
  `SUN`-`SAT`, and invalid values are rejected instead of coerced.
- [ ] `ai-dememory maintenance status` reports schedule/provider state.
- [ ] `ai-dememory maintenance status` reports provider import readiness
  without reading provider files or writing import candidates.
- [ ] `ai-dememory maintenance status` reports false-positive review due
  counts without exposing redacted finding lines.
- [ ] `ai-dememory import-chats codex --dry-run --json` previews provider
  import candidates without writing inbox files.
- [ ] Repeated provider imports skip candidates with the same stable fingerprint
  instead of writing duplicate inbox files.
- [ ] `ai-dememory maintenance run --profile daily --dry-run --json` previews
  enabled provider imports and generated artifacts without writing files or
  import candidates.
- [ ] `ai-dememory maintenance run --profile weekly --dry-run --json`
  previews `reports/sleep-plan.md` with
  `would_write_sleep_plan_report=true` and `reports/hook-captures.md` with
  `would_write_hook_capture_report=true` without writing files.
- [ ] `ai-dememory maintenance run --profile daily --report-dir
  reports/maintenance` writes maintenance reports inside the memory root.
- [ ] `ai-dememory maintenance run --profile weekly` writes
  `reports/sleep-plan.md` and `reports/hook-captures.md`, and includes sleep
  plan and hook capture review paths/counts in the generated maintenance report.
- [ ] Installed `ai-dememory maintenance status` reports generated artifact
  state for index, graph, weights, lifecycle scores, lifecycle report, and hook
  capture and sleep plan reports.
- [ ] Installed `ai-dememory maintenance status` reports `artifact_freshness`
  without writing files.
- [ ] Installed `ai-dememory maintenance status` reports generated packet
  archive cleanup counts without deleting archives.
- [ ] Installed and Docker `ai-dememory maintenance status` validate
  `review_due.due_findings`, `review_due.stale_suppressions`, and
  `review_due.canonical_memory_updated`, plus
  `conflict_review.active_conflicts`, and
  `review_recommendations.pending_count`.
- [ ] `ai-dememory api-smoke` verifies loopback API behavior and network bind
  refusal.

## Docker Local MCP Smoke

- [ ] `docker build -t ai-dememory:local .`
- [ ] `ai-dememory install-smoke --skip-package --docker --image ai-dememory:local`
- [ ] Docker smoke verifies `doctor --json --summary` reports the `vault`
  profile.
- [ ] Docker smoke verifies generated Docker MCP client config launches and
  responds to `initialize` and `ping`.
- [ ] Docker smoke verifies `memory.release_evidence` returns
  `available=false` from the mounted vault and explains that release evidence
  requires a distribution checkout.
- [ ] Docker smoke verifies `memory.publish_plan` returns TestPyPI dispatch
  inputs, preflight commands, and false publish side-effect flags from the
  mounted vault.
- [ ] Docker smoke verifies `maintenance status` returns generated artifact
  state for index, graph, weights, lifecycle scores, lifecycle report, and
  review recommendation counts plus `artifact_freshness`.
- [ ] Docker smoke verifies `schedule plan --json` returns `root=/memory`,
  scheduler commands, cron entries, and false side-effect flags.
- [ ] Docker smoke verifies `roadmap status --json` returns 11 phases,
  matching status counts, stable phase numbers, and false side-effect flags
  from the mounted vault, allowing the expected missing-evidence exit from a
  plain vault.
- [ ] Docker smoke verifies `vault-template export` writes the packaged vault
  template, including hidden config files, from the image.
- [ ] `docker run --rm -v <temp-vault>:/memory ai-dememory:local init /memory`
- [ ] `docker run --rm -v <temp-template-repo>:/template ai-dememory:local vault-template export /template --force --json`
- [ ] `docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local doctor`
- [ ] `docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local index`
- [ ] `docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local maintenance status`
- [ ] `docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local schedule plan --json`
- [ ] `docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local roadmap status --json`
- [ ] `docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local mcp --call memory.release_evidence --args "{}"`
- [ ] `docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local mcp --call memory.publish_plan --args "{}"`
- [ ] Piped MCP `ping` succeeds through `docker run --rm -i ... ai-dememory:local`.

## Publishing

- [ ] TestPyPI trusted publisher is configured for
  `.github/workflows/publish.yml` and environment `testpypi`.
- [ ] PyPI trusted publisher is configured for `.github/workflows/publish.yml`
  and environment `pypi`.
- [ ] `ai-dememory publish-guard` confirms the workflow is manual-only,
  confirmation-gated, and token-free.
- [ ] Publish workflow preflight runs `publish-guard`, `artifact-guard`,
  `validate`, `secret-scan`, `verify-mcp`, `release-check`, installed package
  smoke, package build smoke with `--check-clean`, and Docker local MCP smoke
  before building distributions.
- [ ] First publish attempt targets `testpypi`, with workflow input
  `confirm=publish`.
- [ ] PyPI publish is run only after TestPyPI install verification.

## Generated Artifacts

- [ ] `python3 scripts/ai_dememory.py index`
- [ ] `python3 scripts/ai_dememory.py search ai-dememory --limit 3`
- [ ] `python3 scripts/ai_dememory.py search ai-dememory --why`
- [ ] `python3 scripts/ai_dememory.py search ai-dememory --why` reports
  `matched_terms` and `matched_fields`
- [ ] `python3 scripts/ai_dememory.py context ai-dememory --budget 2000`
- [ ] `python3 scripts/ai_dememory.py context --auto --budget 2000` returns
  `query_source: working_memory` when generated working memory exists.
- [ ] `python3 scripts/ai_dememory.py eval-recall`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures status --strict --max-age-days 14`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures review-plan`
- [ ] `python3 scripts/ai_dememory.py recall-fixtures packet --write-report`
- [ ] `python3 scripts/ai_dememory.py vector status --write-report`
- [ ] `python3 scripts/ai_dememory.py providers detect`
- [ ] `python3 scripts/ai_dememory.py setup plan --json`
- [ ] `python3 scripts/ai_dememory.py setup health --json`
- [ ] `python3 scripts/ai_dememory.py providers plan --json`
- [ ] `python3 scripts/ai_dememory.py providers configure codex --path
  "$HOME/.codex" --dry-run --json`
- [ ] `python3 scripts/ai_dememory.py maintenance status`
- [ ] `python3 scripts/ai_dememory.py maintenance run --profile daily --dry-run --json`
- [ ] Maintenance status reports generated artifact state for index, graph,
  weights, lifecycle scores, and lifecycle report.
- [ ] Maintenance status reports `artifact_freshness` with missing/stale counts
  and `writes_files=false`.
- [ ] Maintenance status reports generated packet archive cleanup counts with
  `deletes_files=false`.
- [ ] `python3 scripts/ai_dememory.py schedule plan --json`
- [ ] `python3 scripts/ai_dememory.py schedule plan --json --mode docker
  --image ai-dememory:local`
- [ ] `python3 scripts/ai_dememory.py schedule setup --dry-run`
- [ ] `python3 scripts/ai_dememory.py schedule setup --dry-run --mode docker
  --image ai-dememory:local`
- [ ] `python3 scripts/ai_dememory.py schedule cron --json`
- [ ] Package install smoke runs `ai-dememory schedule doctor --json`.
- [ ] `python3 scripts/ai_dememory.py schedule doctor --json` reports
  scheduler, Docker, and optional crontab command availability without running
  those commands.
- [ ] MCP `memory.schedule_status` returns configured scheduler settings and
  status commands plus review due summaries without executing platform
  scheduler commands.
- [ ] MCP `memory.schedule_status` output schema includes `valid` and
  `validation_errors`.
- [ ] `python3 scripts/ai_dememory.py export-context`
- [ ] `python3 scripts/ai_dememory.py consolidate --dry-run`
- [ ] `python3 scripts/ai_dememory.py consolidate --dry-run --report-path
  reports/consolidation-dry-run.md`
- [ ] `python3 scripts/ai_dememory.py release-evidence --write-report`
- [ ] `python3 scripts/ai_dememory.py release-evidence --strict` fails until
  automated evidence is clean and all manual acceptance is complete.
- [ ] `python3 scripts/ai_dememory.py publish-plan --json` reports workflow
  dispatch inputs, publish preflight commands, release blockers, and false
  publish side-effect flags.
- [ ] `python3 scripts/ai_dememory.py publish-plan --json` resolves
  `workflow_url` from project metadata or the local GitHub remote when
  available and otherwise returns the documented placeholder.
- [ ] `python3 scripts/ai_dememory.py acceptance status --json`
- [ ] `python3 scripts/ai_dememory.py acceptance plan --json`
- [ ] `python3 scripts/ai_dememory.py acceptance plan --write-report`
- [ ] `python3 scripts/ai_dememory.py acceptance packet --write-report`
- [ ] `python3 scripts/ai_dememory.py acceptance verify --json` fails until all
  manual acceptance items have reviewed passing evidence.

## MCP Runtime Smoke

Run only after the PR exists, preserving the requested workflow order.

- [ ] Set `AI_DEMEMORY_PR_URL` to the draft PR URL.
- [ ] `python3 scripts/ai_dememory.py mcp-smoke`
- [ ] `python3 scripts/ai_dememory.py mcp-client-smoke --command python3 --command-arg scripts/ai_dememory.py`
- [ ] `python3 scripts/ai_dememory.py mcp-client-smoke --config plugins/ai-dememory/.mcp.json --command python3 --command-arg scripts/ai_dememory.py`
- [ ] Initialize over stdio with protocol `2025-11-25`.
- [ ] PR-gated runtime smoke sends `notifications/initialized` before `ping`.
- [ ] PR-gated runtime smoke matches JSON-RPC responses by id and skips server
  notifications.
- [ ] `ping` returns an empty result.
- [ ] Paginated `tools/list` returns search, read, proposal, graph, recall-miss,
  doctor, maintenance, import, capture, provider, schedule, and hook config tools.
- [ ] Paginated `resources/list` returns public/internal memory resources.
- [ ] Paginated `prompts/list` returns the three memory prompts.
- [ ] Paginated runtime list smoke rejects duplicate tool names, resource URIs,
  and prompt names.
- [ ] `tools/call memory.search` returns structured content.
- [ ] `tools/call memory.context` returns token-budgeted structured context.
- [ ] `memory.context` accepts `auto: true` and returns
  `query_source: working_memory` when generated working memory exists.
- [ ] `memory.doctor` returns local readiness checks without writing files.
- [ ] `resources/read` refuses private/sensitive memory by default.
- [ ] `memory.write_proposal` writes only to `inbox/llm-captures/`.
- [ ] `memory.secret_scan` rejects out-of-repo paths.
- [ ] `memory.graph` returns public/internal graph nodes and excludes sensitive memories by default.
- [ ] `memory.capture_miss` writes only to `inbox/recall-feedback/`.
- [ ] `memory.recall_miss_candidate` checks expected memory rank without
  writing recall feedback, fixtures, reports, indexes, or canonical memory.
- [ ] `memory.recall_fixture_status` reports recall fixture freshness without
  writing fixture files.
- [ ] `memory.recall_review_plan` reports pending recall misses without writing
  fixture files.
- [ ] `memory.recall_review_plan` reports bounded `recent_resolved_misses`
  without reopening resolved misses as pending.
- [ ] `memory.recall_review_packet` renders weekly recall review guidance
  without writing reports, fixture files, or miss outcomes.
- [ ] `memory.recall_review_packet` supports `pending_offset`,
  `pending_next_offset`, `invalid_offset`, and `invalid_next_offset` for paged
  review packets.
- [ ] `memory.recall_review_packet` supports optional `reviewer` and `pr_url`
  handoff metadata without writing reports, fixtures, or miss outcomes.
- [ ] `memory.recall_miss_review` records reviewed rejected or dismissed miss
  outcomes without writing fixture files or canonical memory.
- [ ] `memory.vector_status` reports vector readiness without creating
  embeddings or vector indexes.
- [ ] `memory.provenance_status` reports durable provenance issues without
  writing reports.
- [ ] `memory.working_current` reads generated current task state without
  writing files.
- [ ] `memory.working_status` reports current state, recent-session presence,
  and handoff summaries without writing files.
- [ ] `memory.working_snapshot` and `memory.working_handoff` write only under
  `working/`.
- [ ] `memory.maintenance_status` returns recent reports, generated artifacts,
  and configured providers.
- [ ] `memory.maintenance_status` returns provider import readiness without
  reading provider files or writing import candidates.
- [ ] `memory.maintenance_status` returns false-positive review due counts with
  stale suppression counts and `canonical_memory_updated=false`.
- [ ] `memory.maintenance_status` returns conflict review counts with
  `canonical_memory_updated=false`.
- [ ] `memory.maintenance_status` returns review recommendation counts with
  `applies_review_decisions=false` and `canonical_memory_updated=false`.
- [ ] `memory.maintenance_status` returns generated packet archive cleanup
  counts with `deletes_files=false`.
- [ ] `memory.maintenance_run` accepts `dry_run=true` and previews enabled
  provider imports and generated artifacts without writing files or import
  candidates.
- [ ] `memory.capture_import` writes only to `inbox/imports/<kind>/` and
  rejects out-of-vault paths.
- [ ] `memory.git_lessons` defaults to `dry_run=true` and writes only to
  `inbox/git-lessons/` when `dry_run=false`.
- [ ] `memory.import_chats` accepts `dry_run=true` and returns `would_write`
  without writing provider import candidates.
- [ ] `memory.providers_status` reports provider import readiness without
  reading provider files or writing import candidates.
- [ ] `memory.providers_plan` reports provider setup commands without
  configuring providers, reading provider files, or writing import candidates,
  and includes `configure_dry_run_command`.
- [ ] `memory.setup_plan` reports first-run setup commands without writing
  files, installing hooks, installing schedules, reading provider files, or
  writing import candidates.
- [ ] `memory.setup_plan` includes `generated_reports` commands for review and
  release handoff artifacts, including recall review packets.
- [ ] `memory.setup_plan` includes `generated_archive_status` commands for
  generated packet archive inspection.
- [ ] `memory.setup_plan` includes `generated_archive_retention` commands for
  generated packet archive retention previews.
- [ ] `memory.setup_plan` includes installed and Docker `schedule cron` command
  arrays without writing scheduler state.
- [ ] `memory.setup_plan` includes installed and Docker `schedule doctor --json`
  command arrays without writing scheduler state.
- [ ] `memory.setup_health` returns scheduler environment/status, provider
  readiness, generated packet archive status, artifact, lock, false-positive
  review, stale suppression, conflict review, and review recommendation
  summaries without running commands or writing files.
- [ ] `memory.setup_health` includes maintenance preflight commands and artifact
  targets without reading provider files.
- [ ] `memory.schedule_plan` returns scheduler commands without installing them.
- [ ] `memory.schedule_plan` returns reviewed `cron_entries` with
  `mutates_system=false`.
- [ ] `memory.schedule_status` returns configured scheduler settings and status
  commands plus review due summaries without querying or mutating the OS
  scheduler.
- [ ] Invalid scheduler config reports validation errors and no platform status
  commands.
- [ ] MCP runtime smoke covers invalid scheduler config with `valid=false`,
  validation errors, and no platform status commands.
- [ ] `memory.schedule_environment` reports scheduler, Docker, and optional
  crontab command availability with `runs_commands=false`.
- [ ] `memory.acceptance_status`, `memory.acceptance_verify`,
  `memory.acceptance_plan`, `memory.acceptance_template`, and
  `memory.acceptance_packet` report manual acceptance readiness, next actions,
  single-item evidence templates, and the full review packet without recording
  evidence or writing reports.
- [ ] `memory.acceptance_plan` and `memory.acceptance_template` support optional
  `reviewer` and `pr_url` metadata in generated record commands without
  recording evidence or writing reports.
- [ ] `memory.acceptance_packet` supports `offset`, `next_offset`, and
  `has_more` for paged incomplete review items.
- [ ] `memory.acceptance_packet` supports optional `reviewer` and `pr_url`
  handoff metadata without recording evidence or writing reports.
- [ ] `memory.acceptance_packet_archive_retention_plan` previews generated
  packet cleanup candidates with `deletes_files=false`.
- [ ] `memory.maintenance_status` reports `artifact_freshness` with
  `writes_files=false`.
- [ ] `memory.release_evidence` reports read-only release evidence in the
  distribution checkout and returns unavailable in plain vault roots.
- [ ] `memory.release_evidence_report` renders release evidence Markdown in the
  distribution checkout without writing reports or recording evidence, and
  returns unavailable in plain vault roots.
- [ ] `memory.release_evidence` and `memory.release_evidence_report` accept
  optional `reviewer` and `pr_url` metadata for embedded acceptance handoff
  commands without recording evidence or writing reports.
- [ ] `memory.publish_plan` reports TestPyPI/PyPI workflow dispatch inputs,
  preflight commands, release blockers, and false publish side-effect flags
  without writing files, running commands, or uploading packages.
- [ ] `memory.roadmap_status` reports v2 roadmap phase status without writing
  files or mutating canonical memory.
- [ ] `memory.hook_events` and `memory.hook_config` return hook metadata and
  config fragments without installing hooks.
- [ ] `memory.mark_seen` returns a structured receipt with
  `selected_memory_id` and `lifecycle_updated`.
- [ ] `memory.outcome` returns a structured receipt with `target_source`,
  outcome counters, and `lifecycle_updated`.
- [ ] `memory.lifecycle_scores` returns generated scoring data.
- [ ] `memory.sleep_plan` returns safe consolidation candidates.
- [ ] `memory.sleep_apply_reviewed` writes only to `inbox/sleep-consolidation/`.
- [ ] `memory.review_false_positives` returns deterministic review ids.
- [ ] `memory.review_false_positives` returns `review_due` and
  `review_after_status` for suppressions with review-after dates.
- [ ] `memory.review_false_positives` accepts `due_only=true` and returns
  `returned_count` for the filtered view.
- [ ] `memory.review_stale_false_positives` returns stale ignored
  false-positive suppressions without mutating review state.
- [ ] `memory.false_positive_ignore` returns a structured receipt with
  reviewer, review dates, due-status fields, and
  `canonical_memory_updated=false`.
- [ ] `memory.false_positive_unignore` returns a structured receipt with
  reviewer, review date, ignored state, due-status fields, and
  `canonical_memory_updated=false`.
- [ ] `memory.review_conflicts` returns duplicate/conflict candidates.
- [ ] `memory.conflict_dismiss` returns a structured receipt with reviewer,
  review date, dismissed state, and `canonical_memory_updated=false`.
- [ ] `memory.conflict_keep` returns a structured receipt with reviewer, review
  date, keep decision, and `canonical_memory_updated=false`.
- [ ] `memory.conflict_merge_proposal` writes only to
  `inbox/conflict-resolution/` and returns a structured receipt with
  `canonical_memory_updated=false`.
- [ ] `memory.review_modes` and `memory.review_plan` return active policy guidance.
- [ ] `memory.review_configure_mode` persists the active review mode and returns
  policy flags with `canonical_memory_updated=false`.
- [ ] `memory.review_recommendation` writes only to
  `inbox/review-recommendations/` and returns
  `applies_review_decision=false`.
- [ ] `memory.review_recommendations` lists advisory recommendation artifacts
  and returns `writes_files=false`.
- [ ] `memory.review_recommendation_archive_status` lists archived
  accepted/rejected recommendation artifacts with `writes_files=false`.
- [ ] `memory.review_recommendation_archive_status` supports `limit` and
  `offset` with `has_more` and `next_offset` for large archives.
- [ ] `memory.review_recommendation_archive_status` supports `invalid_offset`
  with `invalid_has_more` and `invalid_next_offset` for malformed archive
  artifacts.
- [ ] `memory.review_recommendation_archive_status` and
  `memory.review_recommendation_archive_restore_preview` support
  `recursive=true` for partitioned archive directories.
- [ ] `memory.review_recommendation_archive_restore_preview` previews one
  archived recommendation restore with `dry_run=true` and `writes_files=false`.
- [ ] `memory.review_recommendation_outcome_report` renders reviewed
  recommendation outcome Markdown with `writes_files=false`.
- [ ] `memory.review_recommendation_outcome_report` supports `offset`,
  `next_offset`, `invalid_offset`, and `invalid_next_offset` for paged active
  recommendation outcome packets.
- [ ] `memory.review_recommendation_outcome` records accepted/rejected status
  with `outcome_writes_canonical_memory=false`.
- [ ] `memory.conflict_keep` and `memory.false_positive_ignore` return linked
  recommendation metadata when `recommendation_id` is supplied.
- [ ] `ai-dememory api-smoke` confirms local health/search/graph endpoints and
  `0.0.0.0` refusal without `AI_DEMEMORY_API_KEY` or explicit override.

## Security Review

- [ ] Fake OpenAI, GitHub, Google, AWS, Stripe, Slack, JWT, database URL, private
  key, service account, cookie, and `.env` samples are detected and redacted.
- [ ] Scanner output never prints secret values.
- [ ] MCP resource output excludes `private`, `sensitive`, and
  `secret-prohibited` memories by default.
- [ ] Durable memories require `reviewed: true`.
- [ ] `ai-dememory provenance` reports no missing `reviewed_by` or
  `reviewed_at` metadata for durable memories.

## Manual Acceptance

- [ ] `obsidian-vault`: Export the generated vault template and inspect Obsidian-compatible templates; open it in Obsidian when a GUI reviewer is available.
- [ ] `mcp-client-installed`: Use one real MCP client with installed CLI config.
- [ ] `mcp-client-docker`: Use one real MCP client with Docker config if Docker is supported.
- [ ] `proposal-capture`: Capture one non-secret proposal and review its inbox file.
- [ ] `provider-import`: Import one non-secret provider fixture and review its inbox file.
- [ ] `git-lesson`: Capture one git lesson candidate and review its inbox file.
- [ ] `daily-maintenance`: Run one daily maintenance pass and inspect index, graph, weights, and report artifacts.
- [ ] `review-reports`: Generate false-positive and conflict reports, then review one intentional case or the empty-report evidence.
- [ ] `testpypi-publish`: Publish to TestPyPI only after package and Docker smoke pass in CI and publish workflow preflight.
- [ ] Promote or reject the proposal manually; do not auto-modify durable
  memory.
- [ ] Record reviewed manual proof with `ai-dememory acceptance record --item
  <item-id>` for each completed manual acceptance item.
- [ ] `ai-dememory acceptance verify` exits zero after all manual acceptance
  items have reviewed passing evidence.
