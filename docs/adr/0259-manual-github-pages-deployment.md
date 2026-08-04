# ADR 0259: Manual Exact-Main GitHub Pages Deployment

## Status

Accepted by the Codex Operational Owner under standing owner-delegated
repository authority on 2026-08-03.

## Context

The dependency-free documentation artifact under `site/` is ready for public
hosting, but GitHub Pages introduces a new write-capable workflow, OIDC token,
deployment environment, and public origin. A workflow that both validates pull
requests and owns `pages: write` would let untrusted or merely unmerged YAML
describe its own privileged execution path. A push trigger would also turn a
routine documentation merge into an ambient production deployment.

The Pages uploader dereferences links while building its tar artifact. Uploading
the directory without an exact manifest check could therefore include an
untracked file, a link target, a gitlink, or generated material that was never
reviewed as part of the commit.

## Decision

Use two independent workflows:

- `.github/workflows/pages-validate.yml` runs only for relevant pull requests,
  has only `contents: read`, and cannot upload, deploy, request OIDC, or enter a
  GitHub environment;
- `.github/workflows/pages.yml` runs only through `workflow_dispatch` from the
  trusted default branch. It requires an exact 40-character `approved_sha`, a
  `deploy-pages@<approved_sha>` confirmation, equality with the event SHA, and a
  live GitHub API readback proving that the same SHA is still current `main`;
- validation and deployment use separate jobs. The preparation job has only
  `contents: read`; after the `github-pages` environment gate, the deployment
  job uses `contents: read`, `pages: write`, and `id-token: write` to repeat the
  live-main check and then invoke the pinned `deploy-pages` action. Its guard
  permits no other shell or action;
- every third-party action is pinned to a full commit SHA, checkout never
  persists credentials, deployments serialize without cancelling an active
  run, and no repository secret is read;
- `scripts/pages_artifact_guard.py` runs immediately before upload. It requires
  a clean `site/`, stage-zero Git entries with regular-file mode `100644`, an
  exact tracked-file/directory set, and no symlink, junction, gitlink, hard link,
  modified file, untracked file, assume-unchanged flag, or skip-worktree flag.
  Every file is rehashed with the Git blob format and compared to the object ID
  in the approved commit; Git's path-aware canonical hash permits only declared
  checkout normalization such as Windows line endings;
- the artifact name is fixed to `github-pages`, retention is one day, and hidden
  tracked files are included so `.nojekyll` reaches the public artifact; and
- `configure-pages` is not used. Repository Pages enablement, environment
  protection, the first dispatch, and public-origin QA remain separate explicit
  operations after this workflow change is reviewed and merged.

## Consequences

Opening or merging the workflow PR cannot deploy the site. A deployment is
bound to an explicit current-main tuple and the trusted workflow already stored
on the default branch. Pull-request code still runs on a hosted runner, but it
has no deployment token, environment, artifact upload, repository secret, or
write permission.

The extra validator and manifest check add a small amount of CI time. They use
the existing Python authority and do not add Node, a site build, package runtime
dependencies, analytics, or vault access. GitHub's JavaScript actions remain
presentation/delivery infrastructure rather than product authority.

## Limitations

- GitHub Pages must be enabled with GitHub Actions as its source before the
  first dispatch, and the `github-pages` environment must be inspected after
  GitHub creates or updates it.
- The one-day artifact is not a durable rollback store. Rollback is a reviewed
  revert or fix-forward on `main` followed by a new exact-main dispatch.
- A compromised pinned GitHub-owned action or hosted runner remains part of the
  delivery threat model. SHA pins, minimal permissions, a closed artifact, and
  environment controls reduce but cannot eliminate that platform risk.
- Public-origin 404 behavior, canonical metadata, sitemap, and social preview
  cannot be finalized until the real project Pages URL exists.

## Future Risks

A later change could combine PR execution with Pages permissions, add a push or
workflow-chain trigger, stop checking live `main`, upload a wider tree, mutate
the artifact after its guard, introduce another action in the deploy job, or
mistake Pages OIDC for package-publishing authority. The workflow, artifact,
publisher-inventory, and supply-chain guards must continue to fail those changes
closed.

## Dependencies

- `SECURITY.md` defines workflow, artifact, environment, and publication
  boundaries.
- `docs/documentation-site-plan.md` defines D3 entry and exit evidence.
- `scripts/ci_guard.py` locks workflow triggers, permissions, pins, commands,
  artifact identity, and deploy-job shape.
- `scripts/docs_site_guard.py` validates public content and claims.
- `scripts/pages_artifact_guard.py` validates the exact uploaded tree.

## Rollback

For bad content, revert or fix-forward the documentation on protected `main`
and dispatch the corrected exact SHA. To withdraw hosting, disable Pages and the
deployment environment. Removing the workflows alone does not retract an
already published site and must not be described as a deployment rollback.
