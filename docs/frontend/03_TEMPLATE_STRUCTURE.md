# Target Template Structure

```
templates/
  layouts/
    base.html
    dashboard.html
    full-width.html
    modal.html
    single-page.html
    print.html
  pages/
    analysis/
      dashboard.html
      hub.html
      results.html
      task_manager.html
      partials/
        analysis-progress.html
        task_history.html
        ...
    models/
      overview.html
      detail.html
      comparison.html
      partials/
    applications/
      index.html
      detail.html
      files.html
      partials/
    reports/
      index.html
    statistics/
      overview.html
      analysis.html
      generation.html
      charts.html
      partials/
    system/
      status.html
      logs.html
      settings.html
      partials/
    tasks/
      overview.html
    about/
      about.html
  ui/
    elements/
      common/
        alert.html
        badge.html
        empty-state.html
        error.html
        pagination.html
      dashboard/
        stats-cards.html
        recent-activity.html
      forms/
        model-select.html
        app-select.html
        batch-form.html
      navigation/
        sidebar.html
        topnav.html
      misc/
        loading-spinner.html
  utils/
    macros/
      ui.html
```

## Layout Responsibilities
- `base.html`: global head, body root, block definitions for meta, styles, scripts, main content.
- `dashboard.html`: extends base, injects dashboard-specific regions.
- `single-page.html`: shell for SPA-like section; contains placeholder `#spa-content`.
- `modal.html`: stripped layout for printable / modal dialogs (if needed server-side rendered).

## Partial Naming Conventions
- Reusable: plain descriptive name (`stats-cards.html`).
- Private/implementation detail: prefix underscore (`_task-row.html`) if not included directly outside module.

## Jinja Blocks (Standard Set)
- `title` – page title
- `meta` – extra meta tags
- `styles` – page-level styles (should be rare)
- `content` – main body
- `scripts` – page-specific scripts (HTMX triggers or module imports)

## Includes & Macros
Prefer macros for repeated logic variations (e.g., status badge selecting class). Use includes for structural composition. A macro that outputs raw HTML must document expected context keys.

## Component Discovery
Every new partial or macro must be appended to `04_COMPONENT_TAXONOMY.md` with: name, path, category, purpose, parameters (if macro), and ownership.

## Legacy Mapping
During transition `render_template_compat` handles old paths. For migrated templates:
- Replace `from ..utils.template_paths import render_template_compat as render_template` with `from flask import render_template`.
- Remove any obsolete partial duplicates after verifying no legacy route references remain.
