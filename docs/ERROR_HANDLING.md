# Error Handling

This application implements centralized error handling with both HTML and JSON responses.

## Features
- Centralized registration in `app.errors.handlers.register_error_handlers`
- Automatic request ID (`g.request_id`) added to every request for correlation
- Content negotiation:
  - `application/json` Accept header, `X-Requested-With: XMLHttpRequest`, or `/api/` path => JSON
  - Otherwise renders `templates/pages/errors/errors_main.html`
- Friendly titles, subtitles, and icons for common HTTP status codes (400, 401, 403, 404, 405, 409, 415, 429, 500, 503)
- Debug mode displays stack trace and exception type (never shown in production)
- Optional `/trigger-error` route in debug mode to quickly preview the 500 page

## JSON Error Schema
```json
{
  "status": "error",
  "status_code": 404,
  "message": "The requested resource could not be found.",
  "error": "Page Not Found",
  "error_id": "<request id>",
  "timestamp": "2025-09-02T12:00:00.000000+00:00",
  "path": "/api/some/missing"
}
```

`debug` details (stack trace) are only included when `FLASK_DEBUG` / `DEBUG` is true or `SHOW_ERROR_DETAILS` config flag is set.

## Template Context
The error template receives:
- `error_code`, `error_title`, `error_icon`, `error_subtitle`, `error_message`
- `request_id` (for correlation)
- `debug` and `debug_info` (conditionally)
- `python_version` if configured

## Extending
To customize or add new codes, modify `ERROR_META` in `app/errors/handlers.py`.

## Rationale
Previously only minimal JSON handlers for 404/500 existed. This richer system improves operator UX, debugging, and API consistency while preserving existing tests (no tests asserted the old minimal payload).
