# Frontend Facelift Prompt

**Usage**: Paste this prompt + attach target folder to request UI updates.

---

## Context

I need you to facelift the attached template(s). Follow these conventions:

### Stack
- **Framework**: Tabler UI 1.0.0-beta19 + Bootstrap 5
- **Icons**: Font Awesome 6.5 (`fa-solid fa-*`) + Tabler Icons (`ti ti-*`)
- **Templating**: Jinja2 (`{% %}`, `{{ }}`)
- **Interactivity**: HTMX 1.9 + Hyperscript 0.9
- **Theme**: Light/dark via `[data-bs-theme]`

### Layout Structure
```html
{% extends "layouts/base.html" %}
{% set active_page = 'page-name' %}
{% set page_title = 'Title' %}
{% set page_icon = 'fa-solid fa-icon' %}

{% block title %}Page Title{% endblock %}

{% block content %}
<!-- Main content here -->
{% endblock %}

{% block scripts %}
<!-- Page-specific JS -->
{% endblock %}
```

### Page Header Pattern
```html
<div class="page-header mb-4">
  <div class="row align-items-center">
    <div class="col-auto">
      <span class="page-icon bg-primary-lt text-primary rounded-3 p-2">
        <i class="fa-solid fa-icon fa-lg"></i>
      </span>
    </div>
    <div class="col">
      <h1 class="page-title mb-1">{{ page_title }}</h1>
      <p class="text-muted mb-0">Subtitle text</p>
    </div>
    <div class="col-auto ms-auto">
      <div class="btn-list">
        <a href="#" class="btn btn-primary">
          <i class="fa-solid fa-plus me-2"></i>Action
        </a>
      </div>
    </div>
  </div>
</div>
```

### Card Pattern (Compact)
```html
<div class="card card-table-compact">
  <div class="card-header d-flex flex-wrap align-items-center gap-3">
    <h3 class="card-title d-flex align-items-center gap-2 mb-0">
      <i class="fa-solid fa-icon"></i>
      <span>Card Title</span>
    </h3>
    <div class="card-actions ms-auto">
      <div class="btn-list">
        <button class="btn btn-sm btn-ghost-primary btn-icon" title="Refresh">
          <i class="fa-solid fa-sync"></i>
        </button>
      </div>
    </div>
  </div>
  <div class="card-body">
    <!-- Content -->
  </div>
</div>
```

### HTMX Data Loading
```html
<div id="data-region"
     hx-get="/api/endpoint"
     hx-trigger="load, every 30s, refresh"
     hx-target="this"
     hx-swap="innerHTML">
  <div class="text-center text-muted py-4">
    <div class="spinner-border spinner-border-sm me-2"></div>
    Loading…
  </div>
</div>
```

### Table Pattern
```html
<div class="table-responsive">
  <table class="table table-vcenter table-hover card-table">
    <thead>
      <tr>
        <th class="w-1">Status</th>
        <th>Name</th>
        <th class="w-1">Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr>
        <td><span class="badge bg-{{ item.status_color }}">{{ item.status }}</span></td>
        <td>{{ item.name }}</td>
        <td>
          <div class="btn-list flex-nowrap">
            <a href="#" class="btn btn-sm btn-ghost-primary btn-icon" title="View">
              <i class="fa-solid fa-eye"></i>
            </a>
          </div>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

### Status Badges
```html
<span class="badge bg-success">Completed</span>
<span class="badge bg-warning text-dark">Pending</span>
<span class="badge bg-danger">Failed</span>
<span class="badge bg-info">Running</span>
<span class="badge bg-secondary">Draft</span>
```

### Buttons
```html
<!-- Primary action -->
<a class="btn btn-primary"><i class="fa-solid fa-plus me-2"></i>Create</a>

<!-- Secondary -->
<button class="btn btn-outline-secondary">Cancel</button>

<!-- Ghost (icon only) -->
<button class="btn btn-sm btn-ghost-primary btn-icon" title="Tooltip">
  <i class="fa-solid fa-icon"></i>
</button>

<!-- Danger action -->
<button class="btn btn-sm btn-ghost-danger btn-icon" title="Delete">
  <i class="fa-solid fa-trash"></i>
</button>
```

### Empty State
```html
<div class="empty py-5">
  <div class="empty-icon">
    <i class="fa-solid fa-inbox fa-3x text-muted"></i>
  </div>
  <p class="empty-title h5">No items found</p>
  <p class="empty-subtitle text-muted">
    Description of empty state or next steps.
  </p>
  <div class="empty-action">
    <a href="#" class="btn btn-primary">
      <i class="fa-solid fa-plus me-2"></i>Create First Item
    </a>
  </div>
</div>
```

### Metric/Stat Card
```html
<div class="card card-sm">
  <div class="card-body">
    <div class="d-flex align-items-center">
      <div class="subheader text-muted text-uppercase small">Metric Name</div>
      <div class="ms-auto">
        <span class="text-success d-flex align-items-center">
          <i class="fa-solid fa-arrow-up fa-xs me-1"></i>+5%
        </span>
      </div>
    </div>
    <div class="h1 mb-0">1,234</div>
  </div>
</div>
```

### Grid Layout
```html
<!-- Summary cards row -->
<div class="row row-cards g-2 mb-3">
  <div class="col-6 col-lg-3"><!-- Card --></div>
  <div class="col-6 col-lg-3"><!-- Card --></div>
</div>

<!-- Main content grid -->
<div class="row row-cards g-2">
  <div class="col-lg-8"><!-- Main content --></div>
  <div class="col-lg-4"><!-- Sidebar --></div>
</div>
```

### Modal Pattern
```html
<div class="modal fade" id="example-modal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Modal Title</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <!-- Content -->
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-primary">Confirm</button>
      </div>
    </div>
  </div>
</div>
```

### Hyperscript Refresh
```html
<button _="on click send refresh to #data-region">Refresh</button>
```

---

## Rules

1. **Extend base**: Always `{% extends "layouts/base.html" %}`
2. **Set vars**: `active_page`, `page_title`, `page_icon` at top
3. **Compact classes**: Use `card-table-compact` for data cards
4. **Icons**: Font Awesome solid (`fa-solid fa-*`)
5. **Spacing**: `mb-3/4`, `gap-2/3`, `g-2` for gutters
6. **HTMX**: Prefer `hx-get` over JS fetch for data loading
7. **Loading states**: Always show spinner placeholder
8. **Responsive**: Use `col-6 col-lg-3` patterns, hide with `d-none d-lg-block`
9. **Dark mode**: No hardcoded colors; use Bootstrap vars
10. **Accessibility**: `aria-label`, `title`, `role` attributes

---

## Do NOT

- Add inline styles (use existing CSS classes)
- Create new CSS files
- Use jQuery
- Hardcode colors (use `bg-*`, `text-*` utilities)
- Use deprecated Bootstrap 4 classes
- Create standalone pages without base layout

---

## Apply To

Facelift the attached template(s) following these patterns. Keep structure clean, use existing components, ensure dark mode compatibility.
