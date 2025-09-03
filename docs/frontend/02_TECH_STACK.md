# Frontend Tech Stack & Rationale

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Server Framework | Flask | Lightweight, already in use, good Jinja integration |
| Templates | Jinja2 | Powerful, familiar, supports macros and inheritance |
| Incremental Interactions | HTMX | Minimal JS, declarative attributes, server-first alignment |
| Styling Base | Bootstrap 5 + Custom Theme | Modern, accessible CSS framework; custom overrides in `static/css/theme.css` |
| Iconography | Bootstrap Icons or Font Awesome | Consistency and availability; Bootstrap Icons preferred for Bootstrap 5 integration |
| Live Updates | WebSockets (analyzer bridge) + HTMX polling fallback | Efficient real-time results distribution |
| Task Queue | Celery (server side) | Decouples long-running analysis from request cycle |
| Testing | pytest + Flask test client + HTML assertions | Fast feedback for routes & fragments |
| Accessibility Testing | axe-core CLI (future) | Automated a11y regression detection |
| Visual Regression (optional later) | Playwright or Loki snapshots | Catch unintended layout changes |

## Libraries We Avoid (Unless Approved)
- React/Vue/Angular (overkill for server-first pattern)
- Large CSS frameworks beyond Bootstrap 5 (no additional CSS layers)
- jQuery usage in new code (Bootstrap 5 is jQuery-free; use vanilla JS or Bootstrap's built-in components)

## JavaScript Philosophy
1. Prefer zero custom JS first.
2. If dynamic client state needed, evaluate: HTMX swap? `hx-trigger`? SSE/WebSocket push? Only then minimal ES module or Alpine.js snippet.
3. All custom JS lives under `static/js/` with one file per feature group (e.g., `analysis-dashboard.js`). No global pollution; use IIFE or module scope.
4. Use Bootstrap 5's built-in JavaScript components when possible (modals, dropdowns, tooltips, etc.).

## CSS & Theming
- Single custom bundle: `static/css/theme.css`.
- Use CSS custom properties for design tokens (colors, spacing, font sizes) at `:root`.
- Leverage Bootstrap 5 utility classes extensively; avoid deep descendant selectors; limit specificity.
- Custom components should extend Bootstrap 5 patterns rather than override them.

## Version Tracking
List current versions (update when bumping):
- Flask: TBD (check `requirements.txt`)
- Jinja2: TBD
- HTMX: pinned via CDN snippet or local copy (document exact version)
- Bootstrap: 5.x.x (latest stable, document exact version)
- Bootstrap Icons: latest (if using)

Update this file when upgrading dependencies; mention breaking changes & mitigation.

## Migration Notes
- AdminLTE → Bootstrap 5: Replace AdminLTE-specific classes with Bootstrap 5 equivalents
- jQuery → Vanilla JS: Use Bootstrap 5's built-in JavaScript or write vanilla JS for custom interactions
- Icon classes: Migrate from Font Awesome to Bootstrap Icons for consistency
