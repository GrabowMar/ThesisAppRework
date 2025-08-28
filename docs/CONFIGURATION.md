# Configuration Guide

This document lists runtime configuration flags and environment variables relevant to analysis behavior.

## Analysis Task Gating

Set `DISABLED_ANALYSIS_MODELS` to a comma-separated list of model slugs to globally skip ALL analysis engine tasks (security, static, dynamic, performance) for those models.

Example (PowerShell):
```powershell
$env:DISABLED_ANALYSIS_MODELS = "anthropic_claude-3.7-sonnet,openai_gpt-4o"
```
Then restart the Flask app / Celery worker processes. Any subsequent task invocation for a disabled model returns a payload:
```json
{
  "model_slug": "anthropic_claude-3.7-sonnet",
  "app_number": 1,
  "analysis_type": "security",
  "status": "skipped",
  "reason": "model_disabled",
  "timestamp": "2025-08-22T12:34:56.789Z"
}
```
No analyzer containers or engines are invoked; database records (if any) remain pending until manually started after re‑enabling.

## WebSocket Test Route Model Preference

The previous hard-coded preference for `anthropic_claude-3.7-sonnet` was removed. You can optionally specify a preferred ordering for auto-selection when calling `/api/websocket/test` without a `model_slug` by setting `WEBSOCKET_MODEL_PREFERENCE` (Flask config – list or comma string). If not set, the server picks the first available model with an `app1` directory.

Disabled models (via `DISABLED_ANALYSIS_MODELS`) are short-circuited in the WebSocket test route and return `status=skipped`.

## Recommended Usage Pattern
1. Add noisy or experimental models to `DISABLED_ANALYSIS_MODELS` during refactors.
2. Run tests / develop without churn from background “sanity” analyses.
3. Remove the model slug from the list once ready to resume analyses.

## Related Future Enhancements (Proposed)
- Per-analysis-type disable envs: `DISABLED_SECURITY_MODELS`, `DISABLED_PERFORMANCE_MODELS`, etc.
- Admin UI toggle persisting to a config table instead of environment variable.
- Audit log when a disabled model task attempt is skipped (lightweight logging hook).

