# Research Detail Pages - Quick Reference

**One-page cheat sheet for implementing unified detail pages**

---

## 1. Template Boilerplate

```django
{# Your Detail Page - Research Dashboard #}
{% extends 'layouts/base.html' %}
{% from 'components/detail_macros.html' import 
   research_detail_header, 
   research_metric_grid, 
   research_section_nav, 
   research_scroll_spy_script %}

{% set active_page = 'your_section' %}
{% set page_title = view.title if view else 'Detail Page' %}

{% block content %}
<div class="research-detail-shell">
  {{ research_detail_header(view, metrics[:3], status_badge) }}
  {{ research_metric_grid(metrics) }}
  {{ research_section_nav(sections) }}
  
  <div class="research-content">
    {% for section in sections %}
      <section id="section-{{ section.id }}" 
               class="research-section" 
               data-research-section="{{ section.id }}"
               hx-get="{{ section.hx }}"
               hx-trigger="revealed once"
               hx-swap="innerHTML"
               hx-indicator=".research-section[data-research-section='{{ section.id }}']">
        
        <div class="research-section-header">
          <h2 class="research-section-title">
            <i class="{{ section.icon }}"></i>
            <span>{{ section.label }}</span>
          </h2>
        </div>
        
        <div class="research-skeleton">
          <div class="research-skeleton-line h-lg"></div>
          <div class="research-skeleton-line w-75"></div>
          <div class="research-skeleton-line w-50"></div>
        </div>
      </section>
    {% endfor %}
  </div>
</div>
{% endblock %}

{% block scripts %}
{{ research_scroll_spy_script() }}
<script>
// Your custom JS here
</script>
{% endblock %}
```

---

## 2. Context Builder Pattern

```python
def build_your_detail_context(...) -> Dict[str, Any]:
    # Build view structure
    view = {
        'pretitle': 'Your Section Detail',
        'icon': 'fas fa-your-icon',
        'title': 'Your Title',
        'subtitle': 'Your subtitle with inline info',
        'badges': [
            {'label': 'Status', 'variant': 'badge bg-success-lt', 'icon': 'fas fa-check'},
            {'label': 'Type', 'variant': 'badge bg-primary-lt'}
        ],
        'actions': [
            {
                'key': 'action1',
                'type': 'button',  # or 'link'
                'label': 'Do Something',
                'icon': 'fas fa-play',
                'onclick': 'doSomething()',  # or 'href': '/url'
                'classes': 'btn-primary',
                'visible': True
            }
        ]
    }
    
    # Build metrics
    metrics = [
        {
            'label': 'Metric Name',
            'value': '42',
            'hint': 'Optional hint text',
            'icon': 'fas fa-chart-line',
            'tone': 'success'  # success, warning, danger, info, primary, muted
        }
    ]
    
    # Build sections
    sections = [
        {
            'id': 'overview',
            'label': 'Overview',
            'icon': 'fas fa-home',
            'hx': f'/your-route/{id}/section/overview',
            'template': 'pages/your/partials/overview.html'
        }
    ]
    
    return {
        'view': view,
        'metrics': metrics,
        'sections': sections,
        # ... your additional context
    }
```

---

## 3. Section Partial Route

```python
@your_bp.route('/<int:id>/section/<section>')
def _render_section(id, section):
    context = build_your_detail_context(id)
    section_cfg = context.get('sections_map', {}).get(section)
    
    if not section_cfg:
        abort(404)
    
    return render_template(section_cfg['template'], **context)
```

---

## 4. Common Patterns

### Status Badge in Header
```python
# In context builder
metrics = [
    {
        'label': 'Status',
        'value': 'Running',
        'status_color': 'success'  # Used for header badge
    },
    # ... other metrics
]

# In template
{% set status_metric = metrics|selectattr('label', 'equalto', 'Status')|first %}
{% set status_badge = {
    'label': status_metric.value,
    'color': status_metric.status_color,
    'animated': status_metric.status_color == 'success'
} if status_metric else None %}

{{ research_detail_header(view, metrics[1:3], status_badge) }}
```

### Static Content Section (No Lazy Load)
```django
<section id="section-{{ section.id }}" 
         class="research-section" 
         data-research-section="{{ section.id }}">
  <div class="research-section-header">
    <h2 class="research-section-title">
      <i class="{{ section.icon }}"></i>
      <span>{{ section.label }}</span>
    </h2>
  </div>
  
  {% include 'your/partial.html' %}  {# No HTMX #}
</section>
```

### Empty State
```django
{% from 'components/detail_macros.html' import research_empty_state %}

{% if not items %}
  {{ research_empty_state(
    'fas fa-inbox', 
    'No Items Found',
    'There are no items to display.',
    {'type': 'button', 'label': 'Create Item', 'icon': 'fas fa-plus', 'onclick': 'createItem()', 'classes': 'btn-primary'}
  ) }}
{% endif %}
```

### Error Handling
```javascript
document.addEventListener('htmx:responseError', evt => {
  const section = evt.detail.elt;
  if (!section || !section.matches('[data-research-section]')) return;
  
  const sectionId = section.getAttribute('data-research-section');
  section.innerHTML = `
    <div class="research-empty-state">
      <div class="research-empty-icon">
        <i class="fas fa-exclamation-triangle"></i>
      </div>
      <div class="research-empty-title">Failed to load section</div>
      <div class="research-empty-action">
        <button class="btn btn-primary" 
                onclick="htmx.ajax('GET', '${section.getAttribute('hx-get')}', {target: '[data-research-section=\\'${sectionId}\\']', swap: 'innerHTML'})">
          <i class="fas fa-refresh me-1"></i>Retry
        </button>
      </div>
    </div>
  `;
});
```

---

## 5. CSS Classes Quick Reference

### Layout
- `.research-detail-shell` - Root container
- `.research-content` - Section wrapper

### Header
- `.research-header` - Header container
- `.research-header-icon` - Icon avatar
- `.research-header-identity` - Title block
- `.research-header-pretitle` - Small label
- `.research-header-title` - Main heading
- `.research-header-subtitle` - Secondary info
- `.research-header-actions` - Button group

### Metrics
- `.research-metrics` - Grid container
- `.research-metric-card` - Individual card
- `.research-metric-label` - Metric name
- `.research-metric-value` - Metric value
- `.research-metric-value.tone-{color}` - Colored value
- `.research-metric-hint` - Small text

### Navigation
- `.research-section-nav-wrapper` - Sticky container
- `.research-section-nav` - Nav list
- `.research-section-link` - Nav item
- `.research-section-link.is-active` - Active state

### Sections
- `.research-section` - Section container
- `.research-section-header` - Section title bar
- `.research-section-title` - Section heading
- `.research-section.is-loading` - Loading state

### Loaders
- `.research-skeleton` - Skeleton container
- `.research-skeleton-line` - Line loader
- `.research-skeleton-line.h-lg` - Large line
- `.research-skeleton-line.w-{25|50|75}` - Width

### Empty States
- `.research-empty-state` - Container
- `.research-empty-icon` - Icon circle
- `.research-empty-title` - Title
- `.research-empty-message` - Description
- `.research-empty-action` - Button wrapper

---

## 6. Tone Colors

Use on `.research-metric-value.tone-{color}`:

- `success` - Green (positive metrics)
- `warning` - Yellow (caution metrics)
- `danger` - Red (error/critical metrics)
- `info` - Blue (informational metrics)
- `primary` - Brand color (emphasis)
- `muted` - Gray (neutral metrics)

---

## 7. Icon Recommendations

| Section Type | Icon |
|--------------|------|
| Overview | `fas fa-home` |
| Files | `fas fa-folder` |
| Code | `fas fa-code` |
| Container | `fas fa-box` |
| Ports | `fas fa-network-wired` |
| Logs | `fas fa-file-lines` |
| Metrics | `fas fa-chart-line` |
| Security | `fas fa-shield-halved` |
| Performance | `fas fa-gauge-high` |
| AI/ML | `fas fa-robot` |
| Settings | `fas fa-gear` |
| Metadata | `fas fa-info-circle` |
| Analysis | `fas fa-microscope` |

---

## 8. Responsive Breakpoints

```
Mobile:   < 768px  → 1 column metrics
Tablet:   768-1199px → 4 column metrics
Desktop:  ≥ 1200px → 6 column metrics
```

Actions hide text label on mobile (<992px), show on desktop.

---

## 9. Common Mistakes ❌

**DON'T:**
- ❌ Use `hx-trigger="load once"` (use `revealed once`)
- ❌ Exceed 8 metrics (visual clutter)
- ❌ Use generic section IDs (`section1`, `tab2`)
- ❌ Skip skeleton loaders
- ❌ Omit `aria-label` on icon-only buttons
- ❌ Forget to call `research_scroll_spy_script()`

**DO:**
- ✅ Use `hx-trigger="revealed once"`
- ✅ Limit to 6 metrics per page
- ✅ Use semantic IDs (`overview`, `files`)
- ✅ Show skeleton during loading
- ✅ Add `aria-label` for accessibility
- ✅ Include scroll spy in scripts block

---

## 10. Testing Checklist

- [ ] Skeleton loaders visible on initial load
- [ ] Sections lazy-load on scroll (check Network tab)
- [ ] Scroll spy highlights active section
- [ ] Click nav link → smooth scroll to section
- [ ] Resize to mobile → header stacks, 1-column metrics
- [ ] Toggle dark theme → page adapts
- [ ] Run Lighthouse → 90+ accessibility score
- [ ] Tab through buttons → focus visible
- [ ] Network error → retry button appears

---

## 11. Performance Tips

1. **Lazy load below-fold sections** with `revealed once`
2. **Cache section partials** on server side
3. **Limit metrics to 6** for optimal density
4. **Use semantic IDs** for better caching
5. **Compress responses** with gzip
6. **Enable HTTP/2** for parallel section loads

---

## 12. Accessibility Checklist

- [ ] `<h1>` for page title (in header)
- [ ] `<h2>` for section titles
- [ ] `aria-label` on icon-only buttons
- [ ] `aria-labelledby` on sections
- [ ] `aria-hidden="true"` on decorative icons
- [ ] `aria-live="polite"` on skeletons
- [ ] Color contrast ≥ 4.5:1 for body text
- [ ] Keyboard navigation works (Tab, Enter, Space)

---

## 13. Need Help?

- **Full Guide:** `docs/frontend/DETAIL_PAGES_DESIGN_SYSTEM.md`
- **Visual Comparison:** `docs/frontend/DETAIL_PAGES_VISUAL_COMPARISON.md`
- **Testing:** `docs/frontend/DETAIL_PAGES_TESTING_CHECKLIST.md`
- **CSS:** `src/static/css/detail-pages.css`
- **Macros:** `src/templates/components/detail_macros.html`
- **Examples:**
  - Applications: `src/templates/pages/applications/detail.html`
  - Models: `src/templates/pages/models/model_details.html`
  - Analysis: `src/templates/pages/analysis/result_detail.html`

---

**Last Updated:** January 23, 2025  
**Version:** 1.0.0
