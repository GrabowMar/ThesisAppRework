# Frontend Documentation

## Overview

This directory contains comprehensive documentation for the ThesisAppRework frontend, including design systems, component libraries, and development guides.

---

## Research Detail Pages Design System

**Unified, data-dense layout for model, application, and analysis detail pages.**

### Quick Links

- 📖 **[Design System Guide](DETAIL_PAGES_DESIGN_SYSTEM.md)** - Complete component specifications, usage examples, API reference
- 🎨 **[Visual Comparison](DETAIL_PAGES_VISUAL_COMPARISON.md)** - Before/after layouts, responsive behavior, visual improvements
- ✅ **[Testing Checklist](DETAIL_PAGES_TESTING_CHECKLIST.md)** - Comprehensive test scenarios and sign-off procedures
- 📝 **[Quick Reference](DETAIL_PAGES_QUICK_REFERENCE.md)** - One-page cheat sheet for developers
- 📋 **[Implementation Summary](DETAIL_PAGES_REDESIGN_SUMMARY.md)** - What was implemented, metrics, next steps

### Key Features

- **Compact Header Bar** - Icon, title, inline metrics, and all actions in single row
- **Dense Metric Grid** - 4-6 metrics per row (responsive: 6 desktop, 4 tablet, 1 mobile)
- **Sticky Scroll Spy Navigation** - Horizontal nav with automatic highlighting
- **Lazy-Loaded Sections** - Intersection Observer with `hx-trigger="revealed once"`
- **Skeleton Loaders** - Shimmer wave animations during loading
- **Unified Macros** - Reusable Jinja2 components for consistency
- **WCAG 2.1 AA Compliant** - Full accessibility support
- **Dark Theme Support** - Automatic theme adaptation

### Getting Started

1. **Read the Quick Reference** - Start with [DETAIL_PAGES_QUICK_REFERENCE.md](DETAIL_PAGES_QUICK_REFERENCE.md) for template boilerplate
2. **Review Examples** - Check existing implementations:
   - `src/templates/pages/applications/detail.html`
   - `src/templates/pages/models/model_details.html`
   - `src/templates/pages/analysis/result_detail.html`
3. **Import Macros** - Add to your template:
   ```django
   {% from 'components/detail_macros.html' import 
      research_detail_header, 
      research_metric_grid, 
      research_section_nav %}
   ```
4. **Build Context** - Create view model in `detail_context.py`:
   ```python
   def build_your_detail_context(...) -> Dict[str, Any]:
       return {
           'view': {...},      # Header, badges, actions
           'metrics': [...],   # Dense metric grid
           'sections': [...]   # Lazy-loaded sections
       }
   ```
5. **Test Thoroughly** - Use [DETAIL_PAGES_TESTING_CHECKLIST.md](DETAIL_PAGES_TESTING_CHECKLIST.md)

### Architecture

```
src/
├── static/css/
│   └── detail-pages.css              # 600+ lines, 11 components
├── templates/
│   ├── components/
│   │   └── detail_macros.html        # 9 reusable macros
│   └── pages/
│       ├── applications/detail.html  # Unified implementation
│       ├── models/model_details.html # Unified implementation
│       └── analysis/result_detail.html # Unified implementation
└── app/routes/jinja/
    └── detail_context.py             # View model builders
```

### Browser Support

| Browser | Version | Support |
|---------|---------|---------|
| Chrome/Edge | 90+ | ✅ Full |
| Firefox | 88+ | ✅ Full |
| Safari | 14+ | ✅ Full* |
| Mobile Safari | 14+ | ✅ Full* |
| Samsung Internet | 15+ | ✅ Full |

*Scrollbar styling uses graceful fallback in Safari

### Performance Metrics

- **First Paint:** <500ms (skeleton visible)
- **Section Load:** <200ms per section
- **Lazy Load Savings:** ~40% bandwidth on initial load
- **CSS Size:** ~12KB uncompressed (~3KB gzipped)

---

## Other Frontend Documentation

*(Add other frontend docs here as they are created)*

---

## Contributing

When adding new detail pages:

1. Follow the unified design system
2. Use macros from `components/detail_macros.html`
3. Implement scroll spy with `research_scroll_spy_script()`
4. Test against [DETAIL_PAGES_TESTING_CHECKLIST.md](DETAIL_PAGES_TESTING_CHECKLIST.md)
5. Update documentation if adding new patterns

---

## Questions?

- **Design System Issues:** Review [DETAIL_PAGES_DESIGN_SYSTEM.md](DETAIL_PAGES_DESIGN_SYSTEM.md) troubleshooting section
- **Implementation Help:** Check [DETAIL_PAGES_QUICK_REFERENCE.md](DETAIL_PAGES_QUICK_REFERENCE.md) patterns
- **Visual Questions:** See [DETAIL_PAGES_VISUAL_COMPARISON.md](DETAIL_PAGES_VISUAL_COMPARISON.md) for layouts

---

**Last Updated:** January 23, 2025  
**Maintained By:** Frontend Team

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
