# Observability & Operations

> Navigation: [Overview](OVERVIEW.md) · [Architecture](ARCHITECTURE.md) · [Request Flow](REQUEST_FLOW.md) · [Analysis Pipeline](ANALYSIS_PIPELINE.md) · [Data Model](DATA_MODEL.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Dev Guide](DEVELOPMENT_GUIDE.md)

How to inspect health, performance, and correctness of the platform during development and future production hardening.

## 1. Logging

| File | Purpose |
|------|---------|
| `logs/app.log` | General Flask & service logs |
| `logs/errors.log` | Filtered error-level (if configured) |
| `logs/requests.log` | Access / request diagnostics (middleware) |
| `logs/celery_worker.log` | Celery worker execution & task lifecycle |
| `logs/analyzer-build.log` | Analyzer container build output |

Recommendations (future): adopt structured logging (JSON lines) for machine parsing and correlation IDs per request/task.

## 2. Health & Status Endpoints
| Endpoint | Description | Notes |
|----------|-------------|-------|
| `/health` | Basic liveness (Flask) | Fast, no DB query |
| `/system/health` | Extended (DB check, maybe Redis) | Add timings future |
| `/analyzer/status` | Analyzer containers summary | Source: gateway / service calls |

## 3. Task Visibility
Store task status & timestamps in DB. Progress polling endpoint queries structured fields:
- `status`: queued, running, complete, failed
- `progress_percent` (optional)
- `last_error` (nullable)
- `result_json` (large payload, parsed lazily)

Future: Introduce secondary index on `(status, updated_at)` for fast dashboard rollups.

## 4. Analyzer Container Diagnostics
Use CLI:
```
python analyzer/analyzer_manager.py status
python analyzer/analyzer_manager.py logs static-analyzer
```
Key fields: running state, port binding, last start time.

## 5. Metrics (Planned)
Potential categories:
| Metric | Type | Description |
|--------|------|-------------|
| analyses_started_total | Counter | Number of analysis tasks queued |
| analyses_failed_total | Counter | Failures segmented by type |
| analysis_duration_seconds | Histogram | Wall-clock time per analysis |
| websocket_reconnects_total | Counter | Bridge reliability indicator |
| active_tasks | Gauge | Currently running tasks |

Implementation path: small `/metrics` endpoint (Prometheus exposition) or statsd client in Celery signals.

## 6. Tracing (Future)
Introduce OpenTelemetry:
- Instrument Flask requests (trace ID → response header).
- Instrument Celery tasks (parent span from request if correlation provided).
- Wrap WebSocket send/receive events for latency insight.

## 7. Alerting Suggestions (Future Production)
| Condition | Alert |
|-----------|-------|
| High failure ratio (>20% in 5 min) | Pager / Slack notification |
| Analyzer container restart loop | Ops channel message |
| Task queue latency > threshold | Scale workers or investigate bottleneck |
| No analyses completed in X mins | Heartbeat failure |

## 8. Debugging Playbook
| Symptom | Step 1 | Step 2 | Step 3 |
|---------|-------|--------|--------|
| Task stuck queued | Check `logs/celery_worker.log` | Confirm Redis broker | Restart worker via script |
| No progress updates | Inspect analyzer gateway logs | Check WebSocket connectivity | Retry task with debug flag |
| Container build failure | View `analyzer-build.log` | Rebuild specific service | Clear build cache & rebuild |
| Missing ports | Verify DB `port_configuration` rows | Fallback JSON file | Re-run population script |
| Corrupted result JSON | Validate stored blob | Re-run analysis | Add schema validator |

## 9. Performance Profiling
Short-term: manual timing logs around heavy service calls.
Future: integrate `pyinstrument` or `cProfile` triggered by env flag for slow requests.

## 10. Data Integrity Checks (Future)
Scheduled task to:
- Detect orphaned task records (no result after timeout).
- Purge obsolete large JSON (older than retention window with archived snapshot).
- Verify analyzer container list vs DB configuration.

## 11. Retention & Cleanup
Scripts:
- `scripts/cleanup_analyzer_outputs.py` for disk hygiene.
- (Future) `scripts/purge_old_results.py` with retention policy config.

## 12. Observability Roadmap
1. Structured logging (JSON) + correlation IDs.
2. Metrics endpoint exporting counters/histograms.
3. Distributed tracing across request → task → analyzer.
4. Log-based anomaly detection (error rate spikes).
5. UI dashboard summarizing recent analysis durations & failure histogram.

---
_Last updated: 2025-08-24._ 
