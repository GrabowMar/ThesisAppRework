# State Management Strategy

We primarily manage state on the server. Client maintains minimal transient UI state only when unavoidable.

## Types of State
1. Persistent Domain State – models, applications, analysis results (DB backed)
2. Derived View State – aggregated metrics, filtered lists (recomputed per request)
3. Ephemeral Interaction State – loading indicators, expanded/collapsed rows (client only)
4. Streamed/Real-Time State – task progress updates (WebSocket or polling)

## Patterns
- Server GET returns canonical representation (HTML fragment or full page). Client never assumes stale correctness; uses `hx-refresh` patterns if needed.
- Long-running tasks: route enqueues Celery task -> returns placeholder partial with task id -> HTMX polls `/analysis/tasks/<id>` or WebSocket pushes replacement fragment.
- Form submissions: POST returns either (a) validation errors partial or (b) success state partial + event trigger (`HX-Trigger: batchCreated`).
- Bulk updates: prefer returning the updated list region rather than issuing multiple small swaps.

## HTMX Usage
- Always specify `hx-target` and `hx-swap` (e.g., `hx-swap="outerHTML"` for replacing a component boundary).
- Use `hx-vals` for sending small JSON (e.g., filter changes) instead of hidden inputs when not a full form.
- Avoid `hx-boost` for now to retain explicit control.

## WebSocket Integration
- WebSocket events update matching `data-component` elements via small JS dispatcher (future enhancement). Until then, fallback polling endpoints provide JSON that routes render into partials server-side.

## Caching
- Leverage HTTP caching headers for static assets (already handled). Do not micro-cache dynamic HTML unless performance testing shows necessity.

## Error Handling
- Partial load errors return error partial with retry link (HTMX automatically swaps failing target if status 200). Use `HX-Retarget` or wrapper intercept script for non-200 as needed.

## Focus Management
- After swapping a form region post-validation, focus first invalid control.
- After replacing a substantial content area, move focus to heading via `id` anchor (`tabindex="-1"`).

## State Anti-Patterns
- Storing mutable client state that could contradict server database.
- Embedding serialized large JSON blobs in `data-*` attributes; fetch via endpoint if needed.
- Creating hidden `div` caches of previous fragments.

## Testing State Behaviors
- Tests assert sequence: enqueue -> placeholder -> final data.
- Mock progress updates by patching service layer to deterministic stub.
