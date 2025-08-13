# Routes & Service Architecture

## Overview
The routing layer has been refactored to enforce clear separation of concerns:

| Layer | Responsibility | Artifacts |
|-------|----------------|-----------|
| Service (`app/services/*.py`) | Business logic, database access, validation | `application_service.py` |
| Routes (`app/routes/api/*.py`) | HTTP/transport, request parsing, response shaping | `applications.py`, `core.py`, etc. |
| Utilities (`app/routes/response_utils.py`) | Consistent JSON envelopes, pagination, exception decorator | `json_success`, `json_error`, `handle_exceptions` |

## Patterns Implemented
### 1. Standard JSON Envelope
All API JSON responses follow:
```json
{
  "success": true,
  "message": "Human readable message",
  "data": { ... optional/varies ... },
  "error": { "type": "...", "detail": "..." },
  "pagination": { ... when applicable ... }
}
```
Helper functions prevent drift:
- `json_success(data=None, message="", **extra)`
- `json_error(detail, status=400, error_type="ValidationError", **extra)`

### 2. Exception Handling Decorator
`@handle_exceptions(logger_override=logger)` wraps route functions, converting uncaught exceptions into a standardized 500 envelope while logging.

### 3. Service Layer
Business logic extracted to `application_service.py` providing:
- Pure functions returning serializable dicts
- Centralized validation & field whitelisting
- Custom exceptions: `ValidationError`, `NotFoundError`
- Model-wide operations (start/stop all containers) for horizontal actions

### 4. Pagination Abstraction
`build_pagination_envelope(query, page, per_page)` returns `(items, meta)`; route serializes items while the helper supplies metadata.

### 5. Incremental Migration Strategy
Legacy endpoints retained (HTML partials for HTMX) without forcing JSON envelope where HTML fragments are intentional (e.g. `apps_grid`, logs modals). Migration boundary is explicit: HTML routes remain view-focused; JSON API endpoints standardized.

## Before vs After (Example)
Before (excerpt):
```python
@app.route('/applications/<int:id>')
def get_app(id):
    try:
        app = GeneratedApplication.query.get(id)
        if not app:
            return jsonify({'error': 'not found'}), 404
        return jsonify(app.to_dict())
    except Exception as e:
        current_app.logger.error(e)
        return jsonify({'error': str(e)}), 500
```
After:
```python
@api_bp.route('/applications/<int:app_id>')
@handle_exceptions(logger_override=logger)
def api_get_application(app_id):
    try:
        return json_success(app_service.get_application(app_id))
    except app_service.NotFoundError:
        return json_error('Application not found', status=404, error_type='NotFound')
```

## Testing Strategy
- Unit tests for response utilities (`test_response_utils.py`)
- Service layer tests in isolation without blueprint registration (`test_application_service.py`)
- Future: integration tests exercising route/service boundary & error mapping.

## SQLAlchemy Modernization
Replaced deprecated `Query.get()` with `db.session.get(Model, id)` eliminating legacy warnings.

## Extension to Other Domains
Next candidates: analysis, statistics, batch processing.
Planned steps:
1. Inventory endpoints & identify duplication (try/except + direct DB access).
2. Create `analysis_service.py`, `statistics_service.py` mirroring existing pattern.
3. Apply JSON envelope + decorator to routes; preserve HTML partials.
4. Add domain-specific tests (happy path + error cases).

## Guidelines for Adding New Endpoints
1. Add business logic to appropriate service module (return plain dicts / lists).
2. Raise `ValidationError` / `NotFoundError` as needed; do not return Flask responses inside services.
3. In route:
   - Parse & validate request minimalistically.
   - Call service.
   - Wrap result with `json_success`.
   - Catch service exceptions and map with `json_error`.
4. Use `@handle_exceptions` for unexpected errors.
5. Add / update tests (service first, then integration).

## Open Improvements (Backlog)
- Introduce Pydantic schemas (request/response) for stronger typing.
- Add OpenAPI (generate spec from decorators or dataclasses).
- Introduce repository abstraction to isolate SQLAlchemy specifics.
- Implement caching for frequently accessed lists (models/applications).
- Standardize HTML fragment responses or add parallel JSON endpoints.

## Quick Reference
| Concern | Location | Tooling |
|---------|----------|---------|
| JSON envelope | `routes/response_utils.py` | `json_success`, `json_error` |
| Error mapping | Decorator + service exceptions | `handle_exceptions` |
| Business logic | `services/*_service.py` | Pure functions |
| Pagination | `build_pagination_envelope` | Query slicing |

---
_Last updated: 2025-08-13_
