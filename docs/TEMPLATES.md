# Templates and Partials Conventions

This project uses Flask + Jinja with a structured, namespaced template layout to keep things tidy and predictable at scale.

## Layout

- `src/templates/base.html` — global layout (navbar/sidebar/slots)
- `src/templates/single_page.html` — dynamic shell that renders a single `main_partial` inside `base.html`
- `src/templates/pages/` — top-level pages rendered directly by routes (compose partials)
- `src/templates/partials/` — reusable fragments grouped by feature area
  - `partials/common/` — shared UI blocks, error component, module wrapper macro
  - `partials/analysis/` — (DEPRECATED) legacy analysis fragments retained only as passthrough stubs or historical result templates. New development MUST use `pages/analysis/partials/`.
  - `pages/analysis/partials/` — authoritative analysis hub fragments (lists, stats, quick actions, active tasks, inspection views, task detail core)
    - `pages/analysis/partials/tasks_list.html` — recent tasks list
    - `pages/analysis/partials/stats_summary.html` — KPI summary cards
    - `pages/analysis/partials/quick_actions.html` — launch shortcuts
    - `pages/analysis/partials/active_tasks.html` — auto-refresh active tasks
    - `pages/analysis/partials/inspection_tasks_table.html` — task inspection table
    - `pages/analysis/partials/task_detail_core.html` — core metadata/results panel
    - Historical results partials (still under `partials/analysis/*_complete.html`) will migrate later.
  - `partials/applications/` — application detail and sections
  - `partials/apps_grid/` — grid components used on Applications and Models pages
  - `partials/models/` — model overview, details, and grids
  - `partials/dashboard/` — dashboard cards and HTMX fragments
  - `partials/batch/` — batch jobs UI

## Macros and Wrappers

- Use `partials/common/_module_wrapper.html` macro: `module_card(title, icon, body)` (import with `{% from 'partials/common/_module_wrapper.html' import module_card %}`) for consistent cards.
- Avoid ad-hoc card markup in partials; keep module padding/headers standardized via this macro.

- Row macros for legacy list tables live in `partials/analysis/list/_row_macros.html` (kept for compatibility). New hub tables may introduce updated macros colocated under `pages/analysis/partials/` as patterns stabilize.
  - `status_badge(status)`
  - `security_row(a)`, `dynamic_row(a)`, `performance_row(t)`
  Import with `{% from 'partials/analysis/list/_row_macros.html' import security_row, dynamic_row, performance_row %}`.

- Preview summary macros live in `partials/analysis/preview/_summary_macros.html` (legacy). They remain until preview cards are refactored into the unified hub.
  - `security_card(item)`, `dynamic_card(item)`
  Import with `{% from 'partials/analysis/preview/_summary_macros.html' import security_card, dynamic_card %}`.

- Combined list item macros live in `partials/analysis/list/_item_macros.html` (legacy). Prefer task inspection table patterns going forward.
  - `security_item_li(a)`, `dynamic_item_li(a)`, `performance_item_li(t)`
  Import with `{% from 'partials/analysis/list/_item_macros.html' import security_item_li, dynamic_item_li, performance_item_li %}`.

## Naming and Paths

- Prefer page-scoped namespaced paths. For example:
  - DO: `pages/analysis/partials/tasks_list.html`
  - AVOID: `partials/analysis/tasks_list.html` (deprecated passthrough) or any flat alias.
- Group related fragments in subfolders (e.g., `list/`, `create/`, `preview/`).
- Error fragments live under `partials/common/error.html`.

## Single Page Pattern

When a route renders a single composed screen, prefer:

```python
return render_template(
    'single_page.html',
    page_title='…',
    page_icon='…',
  main_partial='pages/analysis/partials/tasks_list.html',
    # other context
)
```

The `single_page.html` shell handles page header, actions, and includes `main_partial`.

## HTMX Fragments

- HTMX endpoints should return small, self-contained fragments from `pages/analysis/partials/**` (or other page-scoped namespaces). Legacy `partials/analysis/*` references remain as thin delegates only.
- Use specific inner fragments where possible (e.g., `_stats_cards_inner.html`) to minimize DOM churn.

## Duplicates and Aliases Policy

- Avoid duplicate alias files that mirror a canonical namespaced file.
- Migration (Sept 2025): analysis hub fragments relocated into `pages/analysis/partials/` so that page, layout, and fragments live together. Legacy `partials/analysis/*.html` files now:
  - Contain only a comment + include of the new canonical file, OR
  - Persist temporarily for historical result rendering (e.g. `*_complete.html`).
  They will be deleted once no external references remain.
  Canonical examples now:
    - `pages/analysis/partials/tasks_list.html`
    - `pages/analysis/partials/stats_summary.html`
    - `pages/analysis/partials/quick_actions.html`
    - `pages/analysis/partials/active_tasks.html`
    - `pages/analysis/partials/inspection_tasks_table.html`
    - `pages/analysis/partials/task_detail_core.html`
  Deprecated passthroughs (do not add new code):
    - `partials/analysis/tasks_list.html`
    - `partials/analysis/stats_summary.html`
    - etc.
  Historical: `partials/testing/start_result.html` was removed earlier; future create/start fragments will also be page-scoped when refactored.

New: Prefer macros for repeated UI patterns (badges, rows, summary cards) to avoid drift across templates.

## Live updates (HTMX polling)

- `pages/analysis/partials/active_tasks.html` auto-refreshes every ~10 seconds via `hx-get` and `hx-trigger` (accepts dict or list for `active`).
- `pages/analysis/partials/tasks_list.html` may be periodically reloaded for rolling visibility.
- `partials/analysis/preview/shell.html` (legacy) wraps the security and dynamic summary cards with light polling (15–20s); will migrate or be retired.
 - Rate limiter behavior: HTMX endpoints may return `204 No Content` with a `Retry-After` header when called too frequently. This is expected and helps avoid noisy `429` logs. Clients can choose to respect `Retry-After` to dynamically back off.

## Error Handling

- All error responses from HTMX and pages should render `partials/common/error.html` for consistency.

## When Adding New Partials

- Place them under the appropriate namespace folder.
- Import `module_card` and wrap content for consistent look and feel.
- If creating a list, add it under the relevant `list/` subfolder.
- Ensure all route `render_template` paths match the new file paths.

---

This document reflects the current structure after the partials cleanup and Sept 2025 migration to page-scoped analysis partials. When in doubt, look for an existing example in the closest namespace and follow the same pattern.

## Legacy Path Compatibility Loader (August 2025)

After the large-scale restructure that introduced `pages/` and deeper namespacing,
many routes and Jinja `{% include %}` statements still referenced legacy paths
(`views/...`, `partials/...`). To prevent mass edits and regressions, a two-layer
compatibility system was added:

1. `RESTRUCTURE_MAPPING.json` captures old → new file path mappings (auto-generated by the restructure script).
2. `app/utils/template_paths.py` provides:
  - `render_template_compat` — drop-in replacement for `flask.render_template` that remaps legacy names.
  - A Jinja loader wrapper (`_LegacyMappingLoader`) attached in `create_app()` via `attach_legacy_mapping_loader(app)` so that `{% include %}` / `{% extends %}` also benefit.

### Adding a New Mapping

1. Edit `src/templates/RESTRUCTURE_MAPPING.json` and add the entry under `changed_files`.
2. (Optional) Add a heuristic inside `remap_template` if the change follows a broad pattern (e.g. `views/` → `pages/`).
3. Run tests; no route changes are required.

### Removing Legacy Shim Files

Shim files (thin includes pointing to a new canonical path) can be safely deleted once
no code or tests still reference the legacy name and a mapping entry exists.

### Debugging Tips

* If you see `TemplateNotFound: legacy/path.html`, verify the mapping entry or heuristic.
* Ensure tests create the app through `create_app` so the loader wrapper is installed.
* Add temporary logging in `remap_template` for stubborn cases.

### Rationale

This approach allows incremental adoption, minimizes noisy diffs, and preserves historical
path references important for research reproducibility. It also safeguards external
scripts or extensions that may reference pre-restructure template names.

## Changelog

- 2025-08-15: Removed flat alias duplicates under `partials/analysis` (`*_shell.html`, `list_*.html`, `active_tasks.html`) and removed the entire `partials/testing/` folder. Canonical names remain under `partials/analysis/list/`, `partials/analysis/preview/`, and `partials/analysis/create/`.
- 2025-08-27: Eliminated legacy standalone create form (`pages/analysis/legacy_create.html`). All create routes and legacy aliases (`/analysis/create/legacy`, `/analysis/create/page`, trailing slash variants) now point to the unified wizard template `pages/analysis/create.html` rendered inside `single_page.html`. The POST endpoint `/analysis/create` always returns a deterministic JSON payload for comprehensive analysis launches (`success, message, heading, redirect_url, security_id, performance_id, dynamic_id, show_modal`). Any bookmarked legacy URLs remain functional but no longer have a separate template.
- 2025-09-07: Migrated analysis hub fragments to `pages/analysis/partials/` and converted key legacy partials into passthrough delegates (`tasks_list`, `stats_summary`, `quick_actions`, `active_tasks`, `inspection_tasks_table`, `task_detail_core`). New development must not add files under `partials/analysis/`.
This document reflects the current structure after the partials cleanup. When in doubt, look for an existing example in the closest namespace and follow the same pattern.
