# MASTER FRONTEND REWRITE PROMPT

Use this prompt (updated continually) when asking an AI assistant to generate or refactor frontend code.

## Mission
Rebuild the Flask + Jinja + HTMX based UI for ThesisApp into a clean, modular, testable, accessible system using plain Bootstrap 5. Remove legacy path cruft, consolidate duplicate partials, and enforce consistent patterns for incremental HTMX-driven interactivity without drifting into a SPA rewrite.

## Non-Negotiable Principles (see 01_CORE_PRINCIPLES.md for depth)
1. Server-first rendering. HTMX augments; JS sprinkles only.
2. Idempotent, cache-friendly GET views; POST modifies state and returns partial fragments where possible.
3. All business logic stays in Python services accessed via ServiceLocator; templates never embed complex logic beyond simple conditionals/loops.
4. Progressive enhancement: the page must remain usable (core flows) with JS disabled.
5. Accessibility & semantics come before visual flair.
6. No inline styles; no inline JS except minimal `hx-*` attributes.
7. Deterministic template paths under `templates/` with domain-based grouping: `layouts/`, `pages/<domain>/`, `ui/elements/<category>/`.
8. Reuse partials before creating new ones; every new partial registered in component taxonomy doc.
9. Consistent naming: kebab-case for file names (`analysis-dashboard.html` only if leaf page), snake_case for Jinja macro names, BEM-like class composition optional but must not collide with Bootstrap 5 utility classes.
10. Observability hooks (data attributes or comments) for key dynamic regions.

## Scope Guardrails
- Do NOT introduce frontend build step (no webpack/Vite) unless explicitly approved; stick to plain ES modules only if/when needed.
- Avoid large JS frameworks; Alpine.js allowed only for localized state if HTMX insufficient.
- Use plain Bootstrap 5 CSS/JS via CDN or local copy; custom overrides in `static/css/theme.css`.
- No jQuery dependencies; use vanilla JavaScript or Bootstrap 5's built-in JavaScript components.

## Template Layer Strategy
- Layouts provide `<head>`, navigation shell, and block definitions: `base.html`, `dashboard.html`, `full-width.html`, `single-page.html`, `modal.html`, `print.html`.
- Pages extend a layout and render domain content. Smaller dynamic zones must be extracted into `ui/elements/` partials or macros.
- Cross-domain primitives (cards, tables, status badges, progress rows) become macro functions in `utils/macros/` or partials under `ui/elements/common/`.

## HTMX & Interaction Rules
- Every interactive control uses explicit `hx-target` + `hx-swap` (never rely on defaults) and must degrade gracefully.
- Use `data-loading-indicator="spinner-sm"` or similar attribute; central JS (if added) will toggle spinners.
- Polling (hx-trigger="load, every 5s") only for lightweight status; escalate to WebSocket push for heavier updates (already supported server-side).
- For long-running tasks display optimistic placeholder while Celery task enqueued; partial updates are streamed as they complete.

## Routing Cohesion
- Map each blueprint domain (analysis, models, applications, reports, statistics, system, tasks) to `pages/<domain>/...`.
- Remove legacy `views/` and `partials/` references; rely on `render_template_compat` only during transition. Each migrated route must switch to direct `flask.render_template` with new path.

## Migration Workflow
1. Inventory & classify existing templates (see 04_COMPONENT_TAXONOMY.md).
2. Pick a domain (e.g., `analysis`), create a staging branch `frontend/analysis-migration`.
3. Move & normalize templates, update routes to new paths, add tests to confirm HTTP 200 + expected fragments.
4. Remove obsolete duplicates; update mapping JSON if needed.
5. Run shared lint & a11y checks; update docs.
6. Merge; proceed to next domain.

## Testing Requirements
- Each page route: one snapshot-ish test checking canonical blocks render (assert presence of a key heading / region marker comment).
- Each interactive partial: test an HTMX request returns only the expected fragment root element.
- Macro-level logic (e.g., status badge selection) tested with small Jinja rendering test harness.

## Performance Budgets
- Initial dashboard HTML < 120KB uncompressed.
- Per incremental HTMX fragment response < 40KB typical.
- Critical CSS in Bootstrap 5 + theme only; avoid per-page inline style blocks.

## Accessibility
- Heading hierarchy enforced: no skipped levels within a content region.
- Every interactive element has discernible text; icon-only controls get `aria-label`.
- Color contrast meets WCAG AA; dynamic status changes announce via aria-live regions when significant.

## Deliverables per Domain Migration
- Cleaned templates placed in canonical directories.
- Updated routes use direct paths (no compatibility wrapper for migrated files).
- Added/updated taxonomy entries.
- Tests passing.
- Docs updated (`08_ITERATIVE_MIGRATION_PLAN.md` progress section).

## When Generating Code, The AI Must
- Read and respect existing macros & utilities; prefer expanding them rather than new inline logic.
- Provide only modified/new files; avoid restating unchanged content.
- Include reasoning for structural decisions if deviating from these rules.

## Known Legacy Issues to Eliminate
- Mixed naming (`_partial.html` vs no prefix) → normalize to descriptive names without leading underscores except for private partials not directly routed.
- Deep nested partial chains causing context confusion.
- Duplicate card widgets across dashboard & analysis hub.
- AdminLTE-specific classes and dependencies → migrate to Bootstrap 5 equivalents.

## Success Definition
A maintainable, documented, test-covered template system where adding a new analysis visualization requires touching no more than: one route method, one partial, optional macro/styles, and a doc update.

---
(Keep this file concise; link out for details.)
