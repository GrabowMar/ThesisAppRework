# JavaScript Trimming & Progressive Enhancement

This document summarizes the ongoing effort to reduce bespoke frontend JavaScript in favor of:

- **HTMX** for declarative partial loading, polling, and swapping
- **Bootstrap 5** for layout, components, and transitions (no jQuery dependency)  
- **Font Awesome** for consistent iconography

## Feature Flags & Modes

| Flag / Attribute | Location | Purpose |
|------------------|----------|---------|
| `data-models-server-mode` | `#models-page` root | Skip heavy client models table (`models.js`) and rely on server-rendered/htmx fragments. |
| `data-simple-sample-gen` | `#sample-generator` root | Disable large `SampleGeneratorApp` class; use HTMX fragments instead. |
| `data-disable-live-tasks` | body or ancestor of `#tasks-live-table` | Disable websocket/polling live tasks dashboard. |

## Removed / Deprecated Globals

| Removed | Replacement |
|---------|-------------|
| `prefillAndShowGenerate(...)` | Hyperscript: `_="on click set #generateAppForm [name=model_slug].value to '{{ slug }}' then set #generateAppForm [name=app_number].value to '{{ num }}' then show #generateAppModal"` |
| `refreshModels()` (in server mode) | `hx-get` / form submissions; shim still exists but will go away. |

## Patterns

### 1. Polling / Status
Use HTMX `hx-get` + `hx-trigger="every 10s"` on a wrapper element. Example (Sample Generator status):
```html
<div hx-get="/sample-generator/fragments/status" hx-trigger="load, every 6s" hx-swap="outerHTML"></div>
```

### 2. Recent Lists / Tables
Table body driven by fragment returning `<tr>` rows. Initial placeholder row is replaced:
```html
<table hx-get="/sample-generator/fragments/recent" hx-trigger="load, every 15s" hx-target="this tbody" hx-swap="innerHTML"> ... </table>
```

### 3. Button Behaviors
Prefer hyperscript inline operations:
```html
<button _="on click toggle .collapsed on #sidebar">Toggle Sidebar</button>
```

### 4. Refresh Triggers
Broadcast custom events to a single `hx-trigger` listener (e.g. `refresh-apps-table`). Use:
```html
<button _="on click trigger refresh-apps-table">Refresh Apps</button>
```

## Migration Steps (In Progress)
1. Convert inline `onclick` handlers to hyperscript (search for `onclick=`).
2. Remove corresponding JS functions once no longer referenced.
3. Collapse large page-specific scripts behind feature flags (done for models & sample generator).
4. Introduce HTMX fragments for status + lists (done for Sample Generator status & recent results).
5. Final pass to delete unused code paths & shim logic (`models.js` server-mode section).

## Testing Checklist
- Load pages with JS disabled (basic content still visible?).
- Verify fragments swap without console errors.
- Confirm no global function 404s in templates after removals.

## Future Removals
- Full elimination of `models.js` table rendering once all filters/selection are server or HTMX-driven.
- Further decomposition of `sample_generator.js` (batch operations & scaffolding) into fragments.
- Potential replacement of tasks live dashboard via SSE + HTMX if websocket dependency decreases.

_Updated: 2025-09-16 (updated for Bootstrap 5 and Font Awesome migration)_
