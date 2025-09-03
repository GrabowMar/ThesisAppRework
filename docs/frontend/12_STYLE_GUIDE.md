# Style Guide

## Design Tokens (Proposed)
Define in `:root` within `static/css/theme.css`:
```
:root {
  --app-font-family-base: system-ui, Arial, sans-serif;
  --app-color-bg: #ffffff;
  --app-color-surface: #f8f9fa;
  --app-color-border: #e2e5e9;
  --app-color-text: #212529;
  --app-color-accent: #0d6efd;  /* Bootstrap 5 primary */
  --app-color-accent-hover: #0b5ed7;
  --app-color-danger: #dc3545;  /* Bootstrap 5 danger */
  --app-color-success: #198754;  /* Bootstrap 5 success */
  --app-spacing-xs: .25rem;
  --app-spacing-sm: .5rem;
  --app-spacing-md: 1rem;
  --app-spacing-lg: 1.5rem;
  --app-radius-sm: 4px;
  --app-radius-md: 6px;
  --app-shadow-sm: 0 1px 2px rgba(0,0,0,.05);
}
```

## Component Styling Pattern
- Each component partial may have an optional SCSS-like comment block documenting classes & modifier states.
- Avoid increasing specificity; single class selectors preferred.
- Leverage Bootstrap 5 utility classes extensively before creating custom CSS.

## Layout Spacing
- Use Bootstrap 5 utility classes (e.g., `mb-3`, `p-4`, `gap-3`) for consistent spacing.
- Custom spacing variables in new CSS utility classes only when Bootstrap utilities insufficient.
- Do not embed raw pixel values repeatedly.

## Typography
- Use heading tags for hierarchy, not styling. Adjust font sizes via CSS if appearance differs.
- Leverage Bootstrap 5 text utilities (`text-muted`, `text-center`, `fw-bold`, etc.).

## Color Usage
| Purpose | Token | Bootstrap Class |
|---------|-------|-----------------|
| Primary Action | `--app-color-accent` | `btn-primary`, `text-primary` |
| Destructive | `--app-color-danger` | `btn-danger`, `text-danger` |
| Success | `--app-color-success` | `btn-success`, `text-success` |
| Secondary | `--app-color-surface` | `btn-secondary`, `text-secondary` |

## Status Badges
Map analysis/task statuses to Bootstrap 5 semantic classes:
- `status-running` → `badge bg-primary`
- `status-completed` → `badge bg-success`
- `status-failed` → `badge bg-danger`
- `status-pending` → `badge bg-warning`

## Dark Mode (Future)
Provide alternative token value set in `[data-bs-theme="dark"] :root { ... }` using Bootstrap 5's built-in dark mode support.

## Print Styles
Add minimal overrides within `print.html` layout or `@media print` block in theme; hide navigation, ensure monochrome readability.

## Icon Usage
Use Bootstrap Icons with `<i class="bi bi-icon-name" aria-hidden="true"></i>` and pair with screen-reader text if sole content.
Fallback to Font Awesome if needed: `<i class="fa fa-icon" aria-hidden="true"></i>`.

## Motion & Transitions
Keep transitions under 150ms; no parallax or large animations.
Use Bootstrap 5's built-in transition classes when possible.

## Bootstrap 5 Component Usage
- Cards: Use `card`, `card-header`, `card-body`, `card-footer` structure
- Tables: Use `table`, `table-striped`, `table-hover` for enhanced tables
- Forms: Use `form-control`, `form-label`, `form-text` for consistent form styling
- Buttons: Use `btn`, `btn-primary`, `btn-outline-primary` variants
- Alerts: Use `alert`, `alert-primary`, `alert-success` for status messages

## Example Component Block
```
<!-- component:stats-cards -->
<div class="c-stats-cards row g-3">
  <div class="c-stats-cards__item col-md-4" data-testid="stat-item">
    <div class="card h-100">
      <div class="card-body text-center">
        <span class="c-stats-cards__value display-6 text-primary">{{ stats.total_models }}</span>
        <span class="c-stats-cards__label text-muted">{{ stats.label }}</span>
      </div>
    </div>
  </div>
</div>
```

## Migration from AdminLTE
When converting existing components:
- `adminlte-*` classes → Bootstrap 5 equivalents
- `content-wrapper` → `container-fluid` or `container`
- `main-header` → `navbar navbar-expand-lg navbar-light bg-light`
- `sidebar` → `col-md-3` or `col-lg-2` with custom styling
- `info-box` → `card` with custom styling
- `small-box` → `card text-center` with background utilities
