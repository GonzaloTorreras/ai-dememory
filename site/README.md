# ai DeMemory Static Documentation Site

This directory is the dependency-free source artifact for the public
documentation experience described in
`docs/documentation-site-plan.md`. It is not a private vault and it never reads
vault data at build time or in the browser.

## Status And Boundary

- Content/static artifact: implemented here.
- Hosting: not enabled and no public deployment has been claimed.
- Pull-request validation: read-only and isolated from every Pages permission.
- GitHub Pages delivery: a separate manual exact-main workflow exists, but it
  cannot run until the reviewed change is on `main`, Pages is explicitly
  enabled, and an exact SHA dispatch is authorized.
- Product runtime: unchanged; Python remains authoritative.
- Documentation runtime: none. Any static file server can serve this directory.
- JavaScript: optional enhancement only. Navigation and content work without it.

## Accepted Visual Contract

Reference:
`docs/design-concepts/documentation-site-desktop.png`.

The concept is a composition reference, not a source of product facts. The site
uses reviewed repository documentation for all commands and architecture claims.

### Design tokens

| Role | Token | Value |
| --- | --- | --- |
| Page | `--paper` | `#ffffff` |
| Main ink | `--ink` | `#15171c` |
| Muted ink | `--muted` | `#5d6470` |
| Rule | `--line` | `#d9dee8` |
| Primary action | `--blue` | `#1746e8` |
| Primary hover | `--blue-dark` | `#0d2fae` |
| Review/safety | `--green` | `#178a57` |
| Quiet blue surface | `--blue-soft` | `#f4f7ff` |
| Quiet green surface | `--green-soft` | `#f2fbf6` |

The background is true white. The site does not use gradients, glass effects,
decorative pills, marketing metrics, external fonts, or card-grid filler.

### Typography

- Display and section headings: Georgia, Cambria, Times New Roman, serif.
- UI, body, controls, diagrams, and code: system sans/monospace stacks.
- Body text: 17 px desktop, 16 px compact screens, 1.65 line height.
- Control text is explicitly sized and never relies on browser defaults.

### Layout

- Maximum content width: 1180 px.
- First viewport: compact header, two-column hero, and a visible hint of the
  next section on common laptop heights.
- Sections use open bands and thin rules instead of nested cards.
- Desktop diagrams read left-to-right.
- At 760 px and below, every flow becomes a top-to-bottom sequence.
- At 320 px, no horizontal page scroll is allowed; code blocks may scroll
  internally.

## Allowed Above-The-Fold Copy

- Brand: `ai DeMemory`
- Navigation: `How it works`, `Architecture`, `Install`, `Security`,
  `GitHub`
- Heading: `Local memory for your AI agents`
- Supporting copy: `Markdown is the source of truth. The index makes recall
  fast. You decide what becomes durable.`
- Primary action: `Start in five minutes`
- Secondary action: `See the architecture`

No eyebrow, badge, metric, testimonial, or additional hero control is allowed.

## Embedded Visualization Inventory

All layers are UML-like explanatory diagrams, not measured charts. The primary
specialist route is software-architecture visualization; accessibility and
browser testing are supporting passes. No diagram depends on D3, Canvas, WebGL,
animation, hover, or generated raster text.

| Visual layer | Story job | Encoding and layout | Mobile/fallback | Accessibility and QA |
| --- | --- | --- | --- | --- |
| Local memory layers | Explain one local bridge between private Markdown, a rebuildable index, and AI clients. | C4-like context view with direct relationship labels and blue/green semantic roles. | Vertical stack plus adjacent prose. | Informative SVG has title/description; prose repeats every node and boundary. |
| Reviewed lifecycle | Show that review precedes durable storage. | Four-step activity flow; review is green and structurally boxed, not color-only. | Ordered vertical list. | Native ordered list is the canonical reading path; icons are decorative. |
| Three-place separation | Prevent repository/tool/vault collapse. | Three explicit locations separated by inequality markers. | Three stacked sections retaining the same order. | Visible `not the same place` text and no reliance on arrows. |
| Technical request flow | Trace one memory-bearing recall request. | C4/component flow: client -> delivery -> policy -> service -> Markdown/FTS -> provenance response. | Numbered sequence; SVG-like connector treatment removed. | Text outline names nodes, protocol, revalidation, and response fields. |
| Resource envelopes | Compare unreleased 2.1 bounded policy presets without claiming measured cost or stable availability. | Directly labelled comparison table; balanced is recommended through border and text. | Rows become stacked definition blocks. | Header associations, captions, explicit `recommended` text, and a visible release boundary. |
| Process lifecycle | Explain why abandoned MCP descendants terminate. | State/activity flow from client start to EOF/idle/deadline and process-tree exit. | Vertical state path. | Text fallback lists all exit triggers and host/package ownership boundary. |

Fresh-pass status: local specialist pass using the software-architecture,
accessibility, and visualization-testing guidance. A fresh independent repository
review remains required before PR readiness.

## Source Map

| Site surface | Authoritative repository sources |
| --- | --- |
| Home mental model | `docs/architecture.md`, `README.md` |
| Installation | `docs/install.md`, `pyproject.toml` |
| Stable/source capability boundary | `README.md`, `docs/install.md`, audited `v2.0.0` tag behavior |
| Intensity/model policy | `docs/adr/0257-bounded-autonomy-and-resource-profiles.md`, `scripts/resource_policy.py` |
| MCP setup | `docs/local-mcp.md`, `docs/mcp-tool-profiles.md` |
| Python/Node boundary | `docs/adr/0254-python-node-runtime-boundary.md` |
| Process ownership | `docs/operations.md`, lifecycle tests |
| Security model and reporting | `SECURITY.md`, `AGENTS.md`, `docs/architecture.md`, `docs/operations.md`, `docs/local-api.md` |
| Pages delivery boundary | `docs/adr/0259-manual-github-pages-deployment.md`, `.github/workflows/pages-validate.yml`, `.github/workflows/pages.yml`, `scripts/ci_guard.py`, `scripts/pages_artifact_guard.py` |

The structural guard verifies that every listed source exists, keeps stable
2.0.0 command blocks free of 2.1-only features, derives profile numbers and
idle leases from `scripts/resource_policy.py`, and keeps the approved
`SECURITY.md` plus private-reporting route aligned with the security page.

## Local Preview

From the repository root:

```powershell
py -3 -m http.server 4173 --directory site
```

Open `http://127.0.0.1:4173/`.

The server is local preview tooling only. The committed site performs no network
requests until a reader intentionally follows an external link.

## Validation

```bash
python scripts/docs_site_guard.py
python scripts/pages_artifact_guard.py
python -m unittest tests.test_docs_site
python -m unittest tests.test_pages_delivery
```

Rendered QA additionally covers 320, 375, 768, 864, and 1440 px, keyboard
navigation, focus visibility, reduced motion, console warnings/errors, internal
links, command-copy enhancement, and zero automatic external requests.
