# Naming Conventions

## Files & Directories
- Directories: lowercase, hyphen-free domain names (`analysis`, `models`).
- Templates: `kebab-case.html` for pages & partials.
- Private implementation partials (not to be included externally) may start with underscore: `_task-row.html`.
- Macro files: descriptive, under `utils/macros/` (e.g., `ui.html`).

## Jinja
- Macro names: snake_case (`render_status_badge`).
- Block names: semantic (`content`, `title`, `scripts`).
- Context variables passed to templates: snake_case.

## CSS Classes
- Use AdminLTE / Bootstrap utility classes where possible.
- Custom structural classes: `c-<component>` prefix (e.g., `c-task-row`).
- Modifier classes: `is-*` or `has-*` (e.g., `is-failed`, `has-warning`).
- Avoid deep nesting > 3 levels.

## IDs & Data Attributes
- IDs only for unique anchors or JS/HTMX targets: `id="task-list"`.
- Data attributes for state / instrumentation: `data-component="task-row"`, `data-testid="task-row"`.
- Avoid mixing naming styles: prefer kebab-case for attribute values.

## HTMX Targets
- Use container id or `data-hx-target` wrappers: `<div id="analysis-progress" data-component="analysis-progress">`.
- Name swap regions after content, not action: `id="batch-summary"` not `id="update-batch"`.

## JavaScript Modules (If Added)
- `analysis-dashboard.js` (domain + feature).
- Export a single `init()` or auto-invoke on DOMContentLoaded inside module scope.

## Design Tokens (CSS Custom Properties)
- Prefix with `--app-` (e.g., `--app-color-accent`).
- Group by domain where helpful: `--app-spacing-sm`, `--app-font-size-base`.

## Git Branches
- Migration stage: `frontend/<domain>-migration` (e.g., `frontend/analysis-migration`).
- Component extraction: `frontend/extract-<component>`.

## Tests
- Test files for templates: `test_<domain>_templates.py` or appended to existing domain test module.

## Commit Messages
Use conventional syntax: `feat(frontend:analysis): migrate dashboard templates`.
