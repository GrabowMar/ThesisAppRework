# Legacy Removals (August 2025)

This document summarizes codebase cleanup actions removing deprecated or
placeholder modules to reduce bloat and clarify active architecture.

## Removed Modules / Files

| Item | Type | Rationale | Replacement / Direction |
|------|------|-----------|--------------------------|
| `app/services/analyzer_service.py` | Service shim | Fully superseded by `analysis_engines.py` + `analysis_service` | Use engine registry (`get_engine`) or Celery tasks |
| `app/services/port_service.py` | Stub service | Incomplete dynamic allocation logic; opportunistic load handled elsewhere | Future focused port manager if needed |
| `app/services/websocket_integration_v2.py` | Deprecated shim | Consolidated WebSocket handling via `celery_websocket_service` | Continue using CeleryWebSocketService |
| `route_template_audit.md` (root) | One-off doc | Historical audit; no longer maintained | N/A |

## Retained (Deprecated) Shims

| Module | Status | Notes |
|--------|--------|-------|
| `app/services/container_service.py` | Deprecated | Kept to avoid import errors; raises `NotImplementedError` |
| `app/services/huggingface_service.py` | Deprecated | Prefer direct API utilities during batch ingest |

## Migration Notes

- Replace any former `AnalyzerService` usage with:
  ```python
  from app.services.analysis_engines import get_engine
  result = get_engine('security').run(model_slug, app_number)
  ```
- WebSocket broadcasts should route through `celery_websocket_service` helpers.
- Port configuration loading occurs lazily in `ServiceLocator` during app init; no direct PortService needed.

## Testing & Validation

After removal, the test suite was executed to ensure no residual imports
remained. Any failing imports should surface quickly under pytest; none
were observed in final run.

## Future Considerations

- If container orchestration matures, introduce a focused async orchestrator
  (separate process) rather than reviving the old monolithic service.
- Add a lightweight integration test ensuring deprecated shims continue to
  emit warnings until fully removed in a future major version.

---
Document generated as part of cleanup automation.
