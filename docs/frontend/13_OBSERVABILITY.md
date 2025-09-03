# Observability in the Frontend

## Goals
Provide enough signals to debug rendering issues, track fragment performance, and trace user-triggered analysis flows end-to-end.

## Techniques
- `data-component` attributes on root of each reusable component.
- Structured HTML comments for key regions: `<!-- region:analysis-progress -->`.
- Server logs include request id & HX flag (extend logging middleware) – correlate with Celery task ids.
- Optional timing: record start/end of Jinja render for HTMX requests, log as `FRAGMENT_RENDER name=analysis-progress ms=34`.

## Event Tracing
- When enqueuing an analysis, emit log: `ANALYSIS_ENQUEUE model=... app=... type=... task_id=...`.
- When fragment updates with progress, include `task_id` & status.

## Error Surface
- Error partial includes `data-error-code` attribute; consider capturing last 5 frontend errors to a ring buffer (future JS module).

## Metrics (Future)
- Count fragment hits per route.
- Average render time per component.

## Debug Mode Helpers
- Toggle query param `?debug=components` to display overlay bounding boxes (future enhancement) via conditional CSS.

## Logging Consistency
Every log line starts with domain tag: `[frontend]` or `[fragment]` for clarity.
