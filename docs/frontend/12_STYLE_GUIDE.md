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
  --app-color-accent: #4f46e5;
  --app-color-accent-hover: #4338ca;
  --app-color-danger: #dc2626;
  --app-color-success: #16a34a;
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

## Layout Spacing
- Use utility classes (e.g., `mb-3`) or custom spacing variables in new CSS utility classes.
- Do not embed raw pixel values repeatedly.

## Typography
- Use heading tags for hierarchy, not styling. Adjust font sizes via CSS if appearance differs.

## Color Usage
| Purpose | Token |
|---------|-------|
| Primary Action | `--app-color-accent` |
| Destructive | `--app-color-danger` |
| Success | `--app-color-success` |

## Status Badges
Map analysis/task statuses to semantic classes (document in macro). Example: `status-running -> badge bg-info`.

## Dark Mode (Future)
Provide alternative token value set in `[data-theme="dark"] :root { ... }`.

## Print Styles
Add minimal overrides within `print.html` layout or `@media print` block in theme; hide navigation, ensure monochrome readability.

## Icon Usage
Use Font Awesome with `<i class="fa fa-icon" aria-hidden="true"></i>` and pair with screen-reader text if sole content.

## Motion & Transitions
Keep transitions under 150ms; no parallax or large animations.

## Example Component Block
```
<!-- component:stats-cards -->
<div class="c-stats-cards">
  <div class="c-stats-cards__item is-ok" data-testid="stat-item">
    <span class="c-stats-cards__value">{{ stats.total_models }}</span>
    <span class="c-stats-cards__label">Models</span>
  </div>
</div>
```
