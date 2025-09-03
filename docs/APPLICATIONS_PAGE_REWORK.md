# Applications Page Rework

This document summarizes the rework of the Applications page to bring back legacy functionality while aligning with the new frontend structure.

## Goals
- Restore legacy feature richness (grouping by model, per-app lifecycle controls, model-wide actions, generation modal)
- Adopt new layout conventions (cards, page header blocks, container-xl, partial inclusion)
- Enable HTMX-driven partial refreshes instead of full page reloads
- Externalize inline JavaScript into a dedicated static asset

## Implemented
- New template path: `templates/pages/applications/index.html` (replaces legacy `views/applications/index.html` usage)
- Grid partial: `templates/pages/applications/partials/applications_grid.html` with collapsible cards per model and action buttons per application
- Model-wide start/stop buttons using new API endpoints:
  - `POST /api/models/<model_slug>/containers/start`
  - `POST /api/models/<model_slug>/containers/stop`
- Added HX-Trigger headers (`refresh-grid`) to lifecycle endpoints so UI auto-refreshes
- Extracted inline JS to `static/js/applications.js` (prefill modal + grid refresh triggers)
- Generate Application modal posts via HTMX (`/models/applications/generate`) and triggers refresh

## Notes / Limitations
- Model-wide start/stop currently flip DB `container_status` only (no Docker orchestration yet). Future: integrate `DockerManager` for real container lifecycle.
- Bulk multi-select actions, advanced analysis triggers, list/timeline view modes, and container log/inspect modals are not yet reintroduced.
- UI references only existing application-level start/stop operations; restart/build not surfaced in grid yet.

## Next Possible Enhancements
1. Bulk selection bar + batch operations (start/stop/restart/delete/export/analyze)
2. Introduce list & timeline view modes (HTMX swap of partial)
3. Add per-app restart/build buttons (map to future orchestration endpoints)
4. Container diagnostics (logs/inspect) integrating `DockerManager.get_container_logs`
5. Replace DB-only status flips with real docker-compose orchestration service
6. Toast/notification component for success/error instead of relying on simple indicator
7. Polling or SSE for live status updates (remove manual refresh)

## HTMX Triggers
- `refresh-grid` emitted via HX-Trigger header on lifecycle endpoints and generation form responses. Hidden `#grid-refresher` div listens and swaps grid content.

## Testing
- Smoke tested via existing pytest task to ensure route imports / template rendering do not introduce syntax errors.

---
Last updated: {{ '%Y-%m-%d' | datetime | default('2025-09-03') }}
