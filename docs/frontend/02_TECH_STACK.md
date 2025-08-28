# Frontend Tech Stack & Rationale

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Server Framework | Flask | Lightweight, already in use, good Jinja integration |
| Templates | Jinja2 | Powerful, familiar, supports macros and inheritance |
| Incremental Interactions | HTMX | Minimal JS, declarative attributes, server-first alignment |
| Styling Base | AdminLTE + Custom Theme | Provides baseline layout/components; curated overrides in `static/css/theme.css` |
| Iconography | Font Awesome (bundled via AdminLTE) | Consistency and availability |
| Live Updates | WebSockets (analyzer bridge) + HTMX polling fallback | Efficient real-time results distribution |
| Task Queue | Celery (server side) | Decouples long-running analysis from request cycle |
| Testing | pytest + Flask test client + HTML assertions | Fast feedback for routes & fragments |
| Accessibility Testing | axe-core CLI (future) | Automated a11y regression detection |
| Visual Regression (optional later) | Playwright or Loki snapshots | Catch unintended layout changes |

## Libraries We Avoid (Unless Approved)
- React/Vue/Angular (overkill for server-first pattern)
- Large CSS frameworks beyond AdminLTE (Bootstrap layers already present)
- jQuery usage in new code (AdminLTE may still ship it; do not rely on it directly)

## JavaScript Philosophy
1. Prefer zero custom JS first.
2. If dynamic client state needed, evaluate: HTMX swap? `hx-trigger`? SSE/WebSocket push? Only then minimal ES module or Alpine.js snippet.
3. All custom JS lives under `static/js/` with one file per feature group (e.g., `analysis-dashboard.js`). No global pollution; use IIFE or module scope.

## CSS & Theming
- Single custom bundle: `static/css/theme.css`.
- Use CSS custom properties for design tokens (colors, spacing, font sizes) at `:root`.
- Avoid deep descendant selectors; limit specificity.

## Version Tracking
List current versions (update when bumping):
- Flask: TBD (check `requirements.txt`)
- Jinja2: TBD
- HTMX: pinned via CDN snippet or local copy (document exact version)
- AdminLTE: version from `static/vendor/adminlte/` (inspect CSS header)

Update this file when upgrading dependencies; mention breaking changes & mitigation.
