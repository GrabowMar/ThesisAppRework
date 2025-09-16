# Frontend Documentation

This folder contains the consolidated frontend architecture and development documentation for the Flask/Jinja/HTMX/Bootstrap 5 based UI.

## Documentation Structure

- **FRONTEND_ARCHITECTURE.md** – Complete frontend architecture guide covering technology stack, component hierarchy, HTMX patterns, Bootstrap 5 implementation, accessibility standards, and performance guidelines
- **FRONTEND_DEVELOPMENT.md** – Practical development guide with workflow, component creation patterns, testing strategies, and troubleshooting

## Key Technologies

- **Server Framework**: Flask with Jinja2 templating
- **CSS Framework**: Bootstrap 5 (no jQuery dependency)
- **Progressive Enhancement**: HTMX for dynamic updates
- **Icons**: Font Awesome (solid style) - NO inline SVG
- **JavaScript**: Vanilla ES modules only when needed

## Template Organization

```
templates/
├── layouts/              # Page skeletons (base.html, dashboard.html, etc.)
├── pages/{domain}/       # Complete domain-specific pages
├── ui/elements/          # Reusable UI components
└── partials/{domain}/    # HTMX fragment endpoints
```

## Migration Status

✅ **Completed**: Documentation consolidation, Bootstrap 5 foundation
🔄 **In Progress**: Component migration from AdminLTE to Bootstrap 5
📋 **Planned**: Legacy cleanup and AdminLTE removal

## Quick Start

1. Read [FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md) for architectural overview
2. Follow [FRONTEND_DEVELOPMENT.md](FRONTEND_DEVELOPMENT.md) for development workflow
3. Use Bootstrap 5 utilities and components
4. Test accessibility and responsive behavior
5. Update component documentation as needed

For questions or clarifications, refer to the consolidated documentation files or create an issue.
