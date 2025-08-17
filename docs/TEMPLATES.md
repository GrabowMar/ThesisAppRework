# Templates and Partials Conventions

This project uses Flask + Jinja with a structured, namespaced template layout to keep things tidy and predictable at scale.

## Layout

- `src/templates/base.html` — global layout (navbar/sidebar/slots)
- `src/templates/single_page.html` — dynamic shell that renders a single `main_partial` inside `base.html`
- `src/templates/pages/` — top-level pages rendered directly by routes (compose partials)
- `src/templates/partials/` — reusable fragments grouped by feature area
  - `partials/common/` — shared UI blocks, error component, module wrapper macro
  - `partials/analysis/` — analysis hub, lists, detail pages, HTMX fragments
    - `partials/analysis/list/` — list views (security, dynamic, performance, combined, active_tasks)
    - `partials/analysis/create/` — forms and start results for creating analyses
    - `partials/analysis/preview/` — compact previews embedded in other pages
  - `partials/applications/` — application detail and sections
  - `partials/apps_grid/` — grid components used on Applications and Models pages
  - `partials/models/` — model overview, details, and grids
  - `partials/dashboard/` — dashboard cards and HTMX fragments
  - `partials/batch/` — batch jobs UI

## Macros and Wrappers

- Use `partials/common/_module_wrapper.html` macro: `module_card(title, icon, body)` (import with `{% from 'partials/common/_module_wrapper.html' import module_card %}`) for consistent cards.
- Avoid ad-hoc card markup in partials; keep module padding/headers standardized via this macro.

- Row macros for list tables live in `partials/analysis/list/_row_macros.html`:
  - `status_badge(status)`
  - `security_row(a)`, `dynamic_row(a)`, `performance_row(t)`
  Import with `{% from 'partials/analysis/list/_row_macros.html' import security_row, dynamic_row, performance_row %}`.

- Preview summary macros live in `partials/analysis/preview/_summary_macros.html`:
  - `security_card(item)`, `dynamic_card(item)`
  Import with `{% from 'partials/analysis/preview/_summary_macros.html' import security_card, dynamic_card %}`.

- Combined list item macros live in `partials/analysis/list/_item_macros.html`:
  - `security_item_li(a)`, `dynamic_item_li(a)`, `performance_item_li(t)`
  Import with `{% from 'partials/analysis/list/_item_macros.html' import security_item_li, dynamic_item_li, performance_item_li %}`.

## Naming and Paths

- Prefer namespaced paths over flat aliases. For example:
  - DO: `partials/analysis/list/security.html`
  - AVOID: `partials/analysis/list_security.html` (flat alias)
- Group related fragments in subfolders (e.g., `list/`, `create/`, `preview/`).
- Error fragments live under `partials/common/error.html`.

## Single Page Pattern

When a route renders a single composed screen, prefer:

```python
return render_template(
    'single_page.html',
    page_title='…',
    page_icon='…',
    main_partial='partials/analysis/list/shell.html',
    # other context
)
```

The `single_page.html` shell handles page header, actions, and includes `main_partial`.

## HTMX Fragments

- HTMX endpoints should return small, self-contained fragments from `partials/**`.
- Use specific inner fragments where possible (e.g., `_stats_cards_inner.html`) to minimize DOM churn.

## Duplicates and Aliases Policy

- Avoid duplicate alias files that mirror a canonical namespaced file.
- Removed duplicates in this cleanup (examples):
  - Flat alias templates under `partials/analysis/` have been removed. Use the namespaced versions only:
    - `partials/analysis/list/security.html`
    - `partials/analysis/list/dynamic.html`
    - `partials/analysis/list/performance.html`
    - `partials/analysis/list/combined.html`
    - `partials/analysis/list/shell.html`
    - `partials/analysis/preview/shell.html`
    - `partials/analysis/create/shell.html`
    - `partials/analysis/list/active_tasks.html`
  - `partials/testing/start_result.html` → use `partials/analysis/create/start_result.html`

New: Prefer macros for repeated UI patterns (badges, rows, summary cards) to avoid drift across templates.

## Live updates (HTMX polling)

- `partials/analysis/list/active_tasks.html` is wrapped with `hx-get` and `hx-trigger` to auto-refresh every ~10 seconds. It accepts both dict and list shapes for `active` and normalizes internally.
- `partials/analysis/preview/shell.html` wraps the security and dynamic summary cards with light polling (15–20s) to pick up recent results without a full page reload.

## Error Handling

- All error responses from HTMX and pages should render `partials/common/error.html` for consistency.

## When Adding New Partials

- Place them under the appropriate namespace folder.
- Import `module_card` and wrap content for consistent look and feel.
- If creating a list, add it under the relevant `list/` subfolder.
- Ensure all route `render_template` paths match the new file paths.

---

This document reflects the current structure after the partials cleanup. When in doubt, look for an existing example in the closest namespace and follow the same pattern.

## Changelog

- 2025-08-15: Removed flat alias duplicates under `partials/analysis` (`*_shell.html`, `list_*.html`, `active_tasks.html`) and removed the entire `partials/testing/` folder. Canonical names remain under `partials/analysis/list/`, `partials/analysis/preview/`, and `partials/analysis/create/`.
This document reflects the current structure after the partials cleanup. When in doubt, look for an existing example in the closest namespace and follow the same pattern.
