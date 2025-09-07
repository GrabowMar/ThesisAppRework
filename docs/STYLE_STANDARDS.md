# Component Style Standards

**Standardized component styling patterns using the unified Font Awesome icon system and Tabler-inspired layout / spacing for consistent UI across the application.**

---

## Overview

This document outlines the standardized component styling patterns implemented across all templates to ensure consistency and maintainability. All styles follow the Tabler design system principles and are defined in `src/static/css/theme.css`.

---

## Button Standards

### Button Hierarchy & Sizing

```html
<!-- Primary Actions -->
<button class="btn btn-primary btn-sm">Primary Action</button>
<button class="btn btn-outline-primary btn-sm">Secondary Primary</button>

<!-- Contextual Actions -->
<button class="btn btn-success btn-sm">Success Action</button>
<button class="btn btn-outline-success btn-sm">Secondary Success</button>
<button class="btn btn-info btn-sm">Info Action</button>
<button class="btn btn-outline-info btn-sm">Secondary Info</button>
<button class="btn btn-secondary btn-sm">Neutral Action</button>
<button class="btn btn-outline-secondary btn-sm">Secondary Neutral</button>
<button class="btn btn-danger btn-sm">Destructive Action</button>
<button class="btn btn-outline-danger btn-sm">Secondary Destructive</button>
```

### Icon Usage

All buttons now use Font Awesome (solid style) icons. Inline SVGs have been removed project‑wide.

Sizing conventions are preserved via font size + existing spacing utilities:

```html
<!-- Small buttons (implicit ~14–16px icon) -->
<button class="btn btn-sm btn-primary">
  <i class="fas fa-plus me-1"></i>
  Add Item
</button>

<!-- Regular buttons (inherit parent line-height) -->
<button class="btn btn-primary">
  <i class="fas fa-plus me-1"></i>
  Add Item
</button>

<!-- Destructive -->
<button class="btn btn-sm btn-danger" title="Delete">
  <i class="fas fa-trash me-1"></i>
  Delete
</button>

<!-- Icon only (supply aria-label for accessibility) -->
<button class="btn btn-sm btn-outline-secondary" aria-label="Refresh" title="Refresh">
  <i class="fas fa-sync"></i>
</button>
```

Notes:
1. Retain the legacy `icon` class only when it influences layout in existing CSS; new code may omit it unless a rule depends on it.
2. Always keep text accessible: if using an icon-only button, add `aria-label`.
3. Prefer `fas` (solid) for consistency unless a clear semantic need exists for another style pack (not currently loaded by default).

### Button Layout Patterns

```html
<!-- Full-width buttons in sidebars -->
<div class="d-flex flex-column gap-2">
  <button class="btn btn-primary btn-sm w-100">Primary Action</button>
  <button class="btn btn-outline-secondary btn-sm w-100">Secondary Action</button>
</div>

<!-- Button groups -->
<div class="btn-list">
  <button class="btn btn-sm btn-outline-secondary">Action 1</button>
  <button class="btn btn-sm btn-outline-secondary">Action 2</button>
</div>
```

---

## Card Standards

### Card Structure

```html
<div class="card">
  <div class="card-header py-2">
    <strong>Card Title</strong>
  </div>
  <div class="card-body py-2">
    <!-- Card content -->
  </div>
</div>
```

### Card Variants

```html
<!-- Compact card for sidebars -->
<div class="card">
  <div class="card-header py-2">
    <strong>Stats</strong>
  </div>
  <div class="card-body p-2">
    <!-- Minimal padding content -->
  </div>
</div>

<!-- Standard card for main content -->
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Section Title</h3>
    <div class="card-actions">
      <button class="btn btn-sm btn-outline-secondary">Action</button>
    </div>
  </div>
  <div class="card-body">
    <!-- Standard padding content -->
  </div>
</div>
```

---

## Form Standards

### Form Groups

```html
<div class="mb-3">
  <label class="form-label small mb-1">Input Label</label>
  <input type="text" class="form-control form-control-sm" placeholder="Enter text...">
</div>
```

### Dropdown Forms

```html
<div class="mb-3">
  <label class="form-label small mb-1">Select Option</label>
  <div class="dropdown w-100">
    <button class="form-control form-control-sm d-flex justify-content-between align-items-center" data-bs-toggle="dropdown" type="button">
      <span>Select an option</span>
      <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="14" height="14" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
        <path d="M6 9l6 6l6 -6"/>
      </svg>
    </button>
    <div class="dropdown-menu w-100">
      <!-- Dropdown items -->
    </div>
  </div>
</div>
```

### Input Groups

```html
<div class="input-group input-group-sm">
  <input type="text" class="form-control" placeholder="Search...">
  <button class="btn btn-outline-secondary" type="button" title="Clear">
    <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="14" height="14" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
      <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
      <path d="M18 6l-12 12"/>
      <path d="M6 6l12 12"/>
    </svg>
  </button>
</div>
```

---

## Stats Components

### Mini Stats Pattern

```html
<div class="card mini-stats">
  <div class="card-header py-2"><strong>Stats</strong></div>
  <div class="card-body p-2">
    <ul class="list-unstyled mb-0 d-flex flex-wrap gap-2 small">
      <li class="d-flex align-items-center gap-1 stat-item">
        <span class="stat-icon bg-primary text-white">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="12" height="12" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
            <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
            <path d="M7 10l5 -6l5 6l-5 6l-5 -6z"/>
          </svg>
        </span>
        <span class="stat-value">42</span>
        <span class="text-muted stat-label">Items</span>
      </li>
    </ul>
  </div>
</div>
```

---

## Table Standards

### Basic Table

```html
<div class="table-responsive">
  <table class="table table-vcenter table-sm">
    <thead>
      <tr>
        <th>Name</th>
        <th>Status</th>
        <th class="w-1">Actions</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Item Name</td>
        <td>
          <span class="badge bg-success">Active</span>
        </td>
        <td>
          <button class="btn btn-sm btn-outline-secondary">Edit</button>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## Badge Standards

### Status Badges

```html
<!-- Status indicators -->
<span class="badge bg-success">Active</span>
<span class="badge bg-warning">Pending</span>
<span class="badge bg-danger">Error</span>
<span class="badge bg-secondary">Inactive</span>

<!-- Informational badges -->
<span class="badge bg-info">Info</span>
<span class="badge bg-primary">Primary</span>

<!-- Small badges -->
<span class="badge badge-sm bg-secondary">Small</span>
```

---

## Sidebar Layout Standards

### Right Sidebar Structure

```html
{% extends 'layouts/base.html' %}
{% set has_right_sidebar = true %}

{% block right_sidebar %}
<div class="d-flex flex-column gap-3">
  <!-- Title Card -->
  <div class="card">
    <div class="card-body pb-2">
      <div class="d-flex align-items-center mb-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon me-2" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <!-- Icon SVG -->
        </svg>
        <strong>Page Title</strong>
      </div>
      <div class="text-muted small">Page description</div>
    </div>
  </div>

  <!-- Stats Card -->
  <div class="card mini-stats">
    <div class="card-header py-2"><strong>Stats</strong></div>
    <div class="card-body p-2">
      <!-- Mini stats content -->
    </div>
  </div>

  <!-- Filters Card -->
  <div class="card">
    <div class="card-header py-2 d-flex align-items-center justify-content-between">
      <strong>Filters</strong>
      <button class="btn btn-sm btn-outline-secondary" title="Refresh">
        <!-- Refresh icon -->
      </button>
    </div>
    <div class="card-body py-2">
      <!-- Filter form content -->
    </div>
  </div>

  <!-- Actions Card -->
  <div class="card">
    <div class="card-header py-2"><strong>Actions</strong></div>
    <div class="card-body d-flex flex-column gap-2">
      <!-- Action buttons -->
    </div>
  </div>

  <!-- Legend Card -->
  <div class="card">
    <div class="card-header py-2"><strong>Legend</strong></div>
    <div class="card-body small py-2">
      <!-- Legend content -->
    </div>
  </div>
</div>
{% endblock %}
```

---

## Icon Standards (Font Awesome)

### Unified Icon Policy

Inline SVGs have been removed. Font Awesome (currently the solid style set) is the single approved icon source. Do not reintroduce raw `<svg>` icons unless a compelling gap exists and it is documented.

### Sizing Guidance

- Small buttons / compact UI: rely on default inline size (approx 14–16px rendered) with `btn-sm`
- Regular buttons: same `<i>` element; sizing handled by font context
- Headers / section titles: wrap icon in a flex container and optionally apply `fs-4` or utility sizing class
- Stat / mini indicators: apply `small` or custom `.stat-icon` styling

### Common Icon Patterns

```html
<!-- Refresh -->
<i class="fas fa-sync"></i>

<!-- Add / Plus -->
<i class="fas fa-plus"></i>

<!-- Delete / Remove -->
<i class="fas fa-trash"></i>

<!-- Close / Cancel -->
<i class="fas fa-times"></i>

<!-- Play / Start -->
<i class="fas fa-play"></i>

<!-- Pause -->
<i class="fas fa-pause"></i>

<!-- Warning / Alert -->
<i class="fas fa-triangle-exclamation text-warning"></i>

<!-- Success / Confirmation -->
<i class="fas fa-check-circle text-success"></i>
```

### Accessibility

Where an icon is the only content in an interactive element:

```html
<button class="btn btn-sm btn-outline-secondary" aria-label="Refresh results">
  <i class="fas fa-sync"></i>
</button>
```

Screen readers will announce the `aria-label`. Avoid adding visually hidden text unless a more complex description is needed.

---

## Spacing Standards

### Consistent Spacing Classes

- **Gap between cards**: `gap-3` (1rem)
- **Button gaps**: `gap-2` (0.5rem)  
- **Form groups**: `mb-3` (1rem)
- **Compact forms**: `mb-2` (0.5rem)
- **Card padding**: `py-2` (0.5rem top/bottom), `p-2` (0.5rem all sides)

### Layout Classes

```html
<!-- Flex layouts -->
<div class="d-flex flex-column gap-3">  <!-- Vertical stack with gaps -->
<div class="d-flex align-items-center gap-2">  <!-- Horizontal align with gaps -->
<div class="d-flex justify-content-between align-items-center">  <!-- Space between -->

<!-- Grid layouts -->
<div class="d-grid gap-2">  <!-- Grid with gaps -->
<div class="row g-3">  <!-- Bootstrap grid with gutters -->
```

---

## CSS Custom Properties

### Theme Variables

The following CSS custom properties are available for consistent theming:

```css
:root {
  --tblr-primary: #206bc4;
  --tblr-success: #2fb344;
  --tblr-info: #4299e1;
  --tblr-warning: #f76707;
  --tblr-danger: #d63384;
  --tblr-secondary: #6c757d;
  --tblr-border-color: #e1e5e8;
  --tblr-bg-surface: #f8f9fa;
  --tblr-body-color: #212529;
  --tblr-body-color-secondary: #6c757d;
}
```

---

## Implementation Guidelines

### When Creating New Components

1. **Follow established patterns**: Reuse existing card/button/form structures
2. **Use consistent sizing**: `btn-sm`, `form-control-sm`, `py-2`, etc.
3. **Use Font Awesome icons**: `<i class="fas fa-...">` only (no inline SVG)
4. **Apply semantic classes**: Contextual text/background utilities as appropriate
5. **Maintain spacing**: Standard gap + margin utility classes

### When Updating Existing Components

1. **Check for consistency**: Ensure similar elements use same styling
2. **Modernize icons**: Replace any legacy inline SVG that reappears with Font Awesome
3. **Standardize sizing**: Apply consistent button and form sizing
4. **Verify spacing**: Use standardized gap and padding classes
5. **Remove dead `icon` classes** cautiously only after confirming no CSS dependency

### CSS Organization

All component styles are organized in `src/static/css/theme.css` under the "Standardized Component Styles" section. This includes:

- Button standardization
- Card standardization  
- Form standardization
- Stats/badge standardization
- Table standardization
- Dropdown standardization
- Alert standardization

---

This documentation ensures consistent styling across the entire application and provides clear guidelines for future development.