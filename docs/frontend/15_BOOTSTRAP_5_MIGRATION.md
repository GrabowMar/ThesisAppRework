# Bootstrap 5 Migration Guide

This document provides comprehensive guidance for migrating the ThesisApp frontend from AdminLTE to Bootstrap 5.

## Overview

The migration from AdminLTE to Bootstrap 5 is a key part of the frontend modernization effort. This migration:
- Removes jQuery dependencies
- Provides a modern, accessible CSS framework
- Simplifies the styling system
- Improves maintainability

## Migration Strategy

### Phase 1: Foundation (Stage 2)
- Update base layouts to use Bootstrap 5
- Replace AdminLTE CSS/JS with Bootstrap 5
- Convert core navigation components
- Update theme CSS variables

### Phase 2: Component Migration (Stages 3-7)
- Migrate components domain by domain
- Convert AdminLTE-specific classes to Bootstrap 5 equivalents
- Update JavaScript interactions to use vanilla JS or Bootstrap 5 components

### Phase 3: Cleanup (Stage 8)
- Remove AdminLTE dependencies
- Clean up unused CSS/JS
- Verify no jQuery dependencies remain

## Class Mapping Reference

### Layout & Structure
| AdminLTE | Bootstrap 5 | Notes |
|----------|-------------|-------|
| `content-wrapper` | `container-fluid` | Full-width container |
| `main-header` | `navbar navbar-expand-lg` | Top navigation |
| `main-sidebar` | `col-md-3 col-lg-2` | Sidebar column |
| `content-header` | `pb-3` | Content spacing |
| `content` | `col-md-9 col-lg-10` | Main content area |

### Components
| AdminLTE | Bootstrap 5 | Notes |
|----------|-------------|-------|
| `info-box` | `card` | Information display |
| `small-box` | `card text-center` | Compact info display |
| `box` | `card` | Generic container |
| `box-header` | `card-header` | Card header |
| `box-body` | `card-body` | Card content |
| `box-footer` | `card-footer` | Card footer |
| `btn` | `btn btn-primary` | Button styling |
| `label` | `badge` | Status indicators |

### Utilities
| AdminLTE | Bootstrap 5 | Notes |
|----------|-------------|-------|
| `pull-right` | `float-end` | Right alignment |
| `pull-left` | `float-start` | Left alignment |
| `text-center` | `text-center` | Text centering |
| `text-right` | `text-end` | Text right alignment |
| `hidden-xs` | `d-none d-sm-block` | Responsive visibility |
| `visible-xs` | `d-block d-sm-none` | Responsive visibility |

## Navigation Migration

### Top Navigation
```html
<!-- AdminLTE -->
<header class="main-header">
  <nav class="navbar navbar-static-top">
    <div class="navbar-custom-menu">
      <ul class="nav navbar-nav">
        <li><a href="#">Link</a></li>
      </ul>
    </div>
  </nav>
</header>

<!-- Bootstrap 5 -->
<nav class="navbar navbar-expand-lg navbar-light bg-light">
  <div class="container-fluid">
    <div class="navbar-nav ms-auto">
      <a class="nav-link" href="#">Link</a>
    </div>
  </div>
</nav>
```

### Sidebar
```html
<!-- AdminLTE -->
<aside class="main-sidebar">
  <section class="sidebar">
    <ul class="sidebar-menu">
      <li class="active"><a href="#"><i class="fa fa-dashboard"></i> Dashboard</a></li>
    </ul>
  </section>
</aside>

<!-- Bootstrap 5 -->
<aside class="col-md-3 col-lg-2 d-md-block bg-light sidebar">
  <div class="position-sticky pt-3">
    <ul class="nav flex-column">
      <li class="nav-item">
        <a class="nav-link active" href="#">
          <i class="bi bi-speedometer2"></i> Dashboard
        </a>
      </li>
    </ul>
  </div>
</aside>
```

## Form Migration

### Form Controls
```html
<!-- AdminLTE -->
<div class="form-group">
  <label>Label</label>
  <input type="text" class="form-control">
</div>

<!-- Bootstrap 5 -->
<div class="mb-3">
  <label class="form-label">Label</label>
  <input type="text" class="form-control">
</div>
```

### Form Validation
```html
<!-- AdminLTE -->
<div class="form-group has-error">
  <input type="text" class="form-control">
  <span class="help-block">Error message</span>
</div>

<!-- Bootstrap 5 -->
<div class="mb-3">
  <input type="text" class="form-control is-invalid">
  <div class="invalid-feedback">Error message</div>
</div>
```

## Card Migration

### Info Box
```html
<!-- AdminLTE -->
<div class="info-box">
  <span class="info-box-icon bg-blue"><i class="fa fa-envelope"></i></span>
  <div class="info-box-content">
    <span class="info-box-text">Messages</span>
    <span class="info-box-number">1,410</span>
  </div>
</div>

<!-- Bootstrap 5 -->
<div class="card">
  <div class="card-body d-flex align-items-center">
    <div class="bg-primary text-white rounded p-3 me-3">
      <i class="bi bi-envelope"></i>
    </div>
    <div>
      <div class="text-muted small">Messages</div>
      <div class="h4 mb-0">1,410</div>
    </div>
  </div>
</div>
```

## JavaScript Migration

### Modal Handling
```html
<!-- AdminLTE (jQuery) -->
<button onclick="$('#myModal').modal('show')">Open Modal</button>

<!-- Bootstrap 5 (Vanilla JS) -->
<button data-bs-toggle="modal" data-bs-target="#myModal">Open Modal</button>
```

### Dropdown Handling
```html
<!-- AdminLTE (jQuery) -->
<div class="dropdown">
  <button class="btn dropdown-toggle" data-toggle="dropdown">Dropdown</button>
  <ul class="dropdown-menu">
    <li><a href="#">Item</a></li>
  </ul>
</div>

<!-- Bootstrap 5 (Built-in) -->
<div class="dropdown">
  <button class="btn dropdown-toggle" data-bs-toggle="dropdown">Dropdown</button>
  <ul class="dropdown-menu">
    <li><a class="dropdown-item" href="#">Item</a></li>
  </ul>
</div>
```

## Icon Migration

### Font Awesome to Bootstrap Icons
| Font Awesome | Bootstrap Icons | Notes |
|--------------|-----------------|-------|
| `fa fa-dashboard` | `bi bi-speedometer2` | Dashboard icon |
| `fa fa-cog` | `bi bi-gear` | Settings icon |
| `fa fa-user` | `bi bi-person` | User icon |
| `fa fa-home` | `bi bi-house` | Home icon |
| `fa fa-search` | `bi bi-search` | Search icon |

### Icon Usage
```html
<!-- Font Awesome -->
<i class="fa fa-dashboard"></i>

<!-- Bootstrap Icons -->
<i class="bi bi-speedometer2"></i>
```

## Testing Checklist

### Visual Testing
- [ ] Navigation renders correctly on all breakpoints
- [ ] Forms display properly with validation states
- [ ] Cards and components maintain visual hierarchy
- [ ] Colors and spacing are consistent
- [ ] Responsive behavior works as expected

### Functional Testing
- [ ] All interactive components work without jQuery
- [ ] Bootstrap 5 JavaScript components function properly
- [ ] HTMX interactions continue to work
- [ ] No console errors related to missing dependencies

### Accessibility Testing
- [ ] Keyboard navigation works properly
- [ ] Screen reader compatibility maintained
- [ ] Color contrast meets WCAG AA standards
- [ ] ARIA attributes are properly implemented

## Common Pitfalls

### 1. Missing Bootstrap 5 JavaScript
Ensure Bootstrap 5 JavaScript is included for interactive components:
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

### 2. Incorrect Data Attributes
Bootstrap 5 uses `data-bs-*` attributes instead of `data-*`:
```html
<!-- Wrong -->
<button data-toggle="modal" data-target="#myModal">

<!-- Correct -->
<button data-bs-toggle="modal" data-bs-target="#myModal">
```

### 3. Missing CSS Classes
Some AdminLTE utilities don't have direct Bootstrap 5 equivalents:
```html
<!-- AdminLTE -->
<div class="pull-right">

<!-- Bootstrap 5 -->
<div class="float-end">
```

## Rollback Plan

If critical issues arise during migration:
1. Keep AdminLTE CSS/JS available as fallback
2. Use feature flags to toggle between AdminLTE and Bootstrap 5
3. Maintain AdminLTE compatibility layer for critical components
4. Document specific issues for targeted fixes

## Resources

- [Bootstrap 5 Documentation](https://getbootstrap.com/docs/5.3/)
- [Bootstrap Icons](https://icons.getbootstrap.com/)
- [Migration Guide from Bootstrap 4](https://getbootstrap.com/docs/5.3/migration/)
- [Bootstrap 5 Examples](https://getbootstrap.com/docs/5.3/examples/)
