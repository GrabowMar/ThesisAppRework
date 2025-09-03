# Component Taxonomy

Authoritative index of reusable UI building blocks. Update when adding/modifying components.

## Categories
- common – Generic, cross-domain elements (alerts, badges, empty states)
- dashboard – Widgets specific to dashboard/overview pages
- forms – Input controls & compound form fragments
- navigation – Menus, sidebars, breadcrumbs
- misc – Spinners, placeholders, helpers

## Table (Initial Seed – expand iteratively)
| Name | Path | Category | Type | Purpose | Key Context / Params |
|------|------|----------|------|---------|----------------------|
| error | ui/elements/common/error.html | common | partial | Display error message block | error (str), page_title? |
| alert | ui/elements/common/alert.html | common | partial | Generic alert by type | type (success/info/warning/error), message |
| badge | ui/elements/common/badge.html | common | macro (ui.html) | Status badge with color | status, label_override |
| stats-cards | ui/elements/dashboard/stats-cards.html | dashboard | partial | Grid of summary metric cards | stats dict |
| recent-activity | ui/elements/dashboard/recent-activity.html | dashboard | partial | Recent models/apps/tasks list | items list |
| model-select | ui/elements/forms/model-select.html | forms | partial | Dropdown/select list of models | models list, selected |
| app-select | ui/elements/forms/app-select.html | forms | partial | Dropdown of applications for chosen model | apps list, selected |
| batch-form | ui/elements/forms/batch-form.html | forms | partial | Create/edit batch configuration | config dict |
| sidebar | ui/elements/navigation/sidebar.html | navigation | partial | Left navigation menu | active section |
| topnav | ui/elements/navigation/topnav.html | navigation | partial | Top navigation bar | user/session |
| loading-spinner | ui/elements/misc/loading-spinner.html | misc | partial | Loading indicator placeholder | size (sm/md/lg) |

## Bootstrap 5 Component Mapping
| Bootstrap Component | Usage | Customization |
|-------------------|-------|---------------|
| `card` | Content containers, info boxes | Extend with custom classes, avoid overriding core styles |
| `navbar` | Top navigation, sidebars | Use Bootstrap's responsive classes, customize colors via CSS variables |
| `table` | Data display | Leverage `table-striped`, `table-hover`, `table-responsive` |
| `form-control` | Input styling | Use Bootstrap's validation states, extend with custom validation |
| `btn` | Action buttons | Use semantic variants (`btn-primary`, `btn-danger`) |
| `badge` | Status indicators | Use semantic colors (`bg-primary`, `bg-success`) |
| `alert` | Status messages | Use semantic variants, extend with custom dismiss logic |
| `modal` | Dialogs, overlays | Use Bootstrap's built-in JavaScript, extend with HTMX integration |

## Conventions
- Macro library: define logic-heavy components as Jinja macros inside `utils/macros/ui.html`.
- Keep partial names noun-first ("stats-cards" not "cards-stats").
- Prefer Bootstrap 5 utility classes over custom CSS when possible.
- Use semantic Bootstrap classes (`text-primary`, `bg-success`) for consistent theming.

## Registration Checklist For New Component
1. Determine category (create subfolder if justified).
2. Add row to table above.
3. Add docstring comment at top of file describing purpose & required context keys.
4. If macro: list parameters & defaults in the macro signature.
5. Reference component in commit message.
6. Document any Bootstrap 5 component usage in the mapping table above.

## Deprecation
Mark deprecated components with a comment header `DEPRECATED: use <new-path>` and remove after two migration cycles.

## Migration Notes
- AdminLTE components should be replaced with Bootstrap 5 equivalents
- jQuery-dependent components should be rewritten using vanilla JavaScript or Bootstrap 5's built-in JavaScript
- Font Awesome icons should be migrated to Bootstrap Icons where possible
