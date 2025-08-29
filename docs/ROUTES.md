# Routes Reference (src)

This document enumerates the Flask routes defined under `src/app/routes/` and `src/app/routes/api/`.

- UI blueprints serve HTML (often as HTMX partials) under dedicated prefixes.
- API endpoints live under the `/api` prefix (plus a separate `/api/websocket` blueprint) and return JSON unless noted as template/HTMX.
 - WebSocket HTTP fallback: `/ws/analysis` (426 Upgrade Required)
 - Polling behavior (HTMX): Preview cards refresh every ~15–20s; Active tasks refresh every ~10s via `/analysis/api/active-tasks`.
 - Rate limiting: High-frequency HTMX endpoints use a lightweight in-process limiter that returns 204 No Content with `Retry-After` hints when called too frequently. Clients can optionally honor the header to back off.

## UI Blueprints (server-rendered pages)

- main (prefix: /)
  - GET / — Dashboard page
  - GET /about — About page
  - GET /system-status — System status page
  - GET /test-platform — Redirects to Analysis Hub (/analysis/)
  - GET /models_overview — Redirects to models overview
  - JSON utilities (scoped under main, not API blueprint):
    - GET /api/stats — Dashboard stats
    - POST /api/data/initialize — Initialize DB from JSON
    - GET /api/data/status — Data initialization status
    - GET /api/system/health — System health summary
    - GET /api/dashboard/stats — Enhanced dashboard stats
    - POST /api/analyzer/start — Check/start analyzer services (advisory)

- docs (prefix: /docs)
  - GET /docs/ — Documentation index page
  - GET /docs/<path:filepath> — Display specific markdown documentation file
  - Supports all .md files in /docs/ and /docs/frontend/ directories
  - Renders markdown with syntax highlighting, tables, and code blocks
  - Security: Path traversal protection, only serves .md files from docs directory

- models (prefix: /models)
  - GET /models/ — Models overview page
  - GET /models/model/<model_slug>/details — Model details page
  - GET /models/applications — Applications overview page
  - GET /models/application/<model_slug>/<int:app_number> — Application detail page
  - GET /models/model_actions — Actions modal (generic)
  - GET /models/model_actions/<model_slug> — Actions modal (specific)
  - GET /models/model_apps/<model_slug> — Model applications list (HTMX)

- analysis (prefix: /analysis)
  - GET /analysis/ — Analysis hub page
  - GET /analysis/list — Analyses list page (combined)
  - GET /analysis/create — Create new analyses (security, dynamic)
  - GET /analysis/preview/<model_slug>/<int:app_number> — App-centric preview
  - HTMX partials
    - GET /analysis/api/stats — Stats cards
    - GET /analysis/api/trends — Trends card
    - GET /analysis/api/recent/security — Recent security list
    - GET /analysis/api/recent/performance — Recent performance list
    - GET /analysis/api/recent/combined — Combined recent activity
  - GET /analysis/api/list/combined — Combined list (security/dynamic/perf)
  - GET /analysis/api/list/security — Security analyses table
  - GET /analysis/api/list/dynamic — Dynamic (ZAP) analyses table
  - GET /analysis/api/list/performance — Performance tests table
  - GET /analysis/api/active-tasks — Active Celery tasks table
  - Actions
    - POST /analysis/security/start — Start security analysis
    - POST /analysis/performance/start — Start performance test
    - POST /analysis/dynamic/start — Start dynamic (ZAP-like) analysis
    - POST /analysis/batch/start — Start batch analysis
    - Aliases: POST /analysis/security/run, /analysis/performance/run, /analysis/dynamic/run
  - Forms (HTMX)
    - GET /analysis/security_test_form
    - GET /analysis/performance_test_form
    - GET /analysis/dynamic_test_form
  - Views
    - GET /analysis/get_model_apps — Apps select partial (HTMX)
    - GET /analysis/dynamic/<int:analysis_id> — Dynamic analysis results
    - GET /analysis/security/<int:analysis_id>/results/view — Security results
    - GET /analysis/security/<int:analysis_id>/results/complete — Security results (complete)

- batch (prefix: /batch) [LEGACY]
  - GET /batch/ — Legacy batch dashboard (renders only in TESTING mode; redirects to /tasks otherwise)
  - GET|POST /batch/create — Legacy create (redirects to unified analysis create wizard)
  - GET /batch/<batch_id> — Batch detail page (still supported)
  - HTMX partials (active, recent, queue, stats) still served for legacy tests
  - JSON utilities retained for backward compatibility
  - NOTE: Prefer the new Tasks hub (/tasks/) for active & queued work

- tasks (prefix: /tasks)
  - GET /tasks/ — Unified tasks & operations overview (supersedes legacy /batch)
  - Planned: future granular task APIs (queue management, filtering)

- statistics (prefix: /statistics)
  - GET /statistics/ — Unified statistics overview (legacy aggregate)
  - GET /statistics/generation — Generation-focused metrics (apps/models produced)
  - GET /statistics/analysis — Analysis-focused metrics (security/performance/dynamic)

  

- advanced (prefix: /advanced)
  - GET /advanced/apps — Apps grid page shell
  - GET /advanced/models — Models overview page shell
  - Apps grid APIs (template/HTMX responses)
    - GET /advanced/api/apps/grid — Grid/list/compact views
    - GET /advanced/api/apps/<app_id>/details — App details partial
    - GET /advanced/api/apps/<app_id>/urls — App URLs (JSON)
    - POST /advanced/api/containers/bulk-action — Bulk start/stop/restart (JSON)
    - POST /advanced/api/analysis/configuration — Analysis config partial
    - POST /advanced/api/analysis/start — Start analyses for selected apps (JSON)
  - Models overview helpers (small HTML/JSON endpoints)
    - GET /advanced/api/models/stats/active — Active models count (HTML span)
    - GET /advanced/api/models/stats/performance — Avg performance (HTML span)
    - GET /advanced/api/models/stats/last-updated — Last update (text)
    - GET /advanced/api/models/display — Models listing partial(s)
    - GET /advanced/api/models/<int:model_id>/details — Model details partial

- websocket fallbacks (registered globally)
  - GET /ws/analysis — Placeholder WS endpoint (426 upgrade required)
  - GET /socket.io/ — Socket.IO fallback JSON

## API Blueprints (JSON-first)

All paths below are prefixed with `/api` unless otherwise noted.

- core
  - GET /api/ — API overview
  - GET /api/health — API health

- models
  - GET /api/models — Models list (enveloped)
  - GET /api/models/<model_slug>/apps — Apps for a model
  - GET /api/models/list — Raw models list
  - GET /api/models/stats/total — Model count
  - GET /api/models/stats/providers — Provider counts
  - GET /api/models/providers — Unique providers
  - Container/status helpers
    - GET /api/model/<model_slug>/container-status
    - GET /api/model/<model_slug>/running-count
    - GET /api/app/<model_slug>/<int:app_num>/status
    - GET /api/app/<model_slug>/<int:app_num>/logs
  - Aggregates
    - GET /api/models/stats/performance
    - GET /api/models/stats/last-updated

- applications
  - GET /api/applications — Paginated apps
  - POST /api/applications — Create app
  - GET /api/applications/<int:app_id> — App detail (enveloped)
  - PUT /api/applications/<int:app_id> — Update app
  - DELETE /api/applications/<int:app_id> — Delete app
  - GET /api/applications/types — Known types
  - GET /api/applications/<int:app_id>/code — App code/metadata
  - PATCH /api/applications/<int:app_id>/status — Update status
  - Views (template/HTMX)
    - GET /api/apps/grid — Grid/list partials
    - GET /api/applications/<int:app_id>/details — Details modal
    - GET /api/applications/<int:app_id>/logs — Logs modal
    - GET /api/logs/application/<int:app_id> — Logs partial
  - Container controls
    - POST /api/applications/<int:app_id>/start
    - POST /api/applications/<int:app_id>/stop
    - POST /api/applications/<int:app_id>/restart
    - POST /api/app/<model_slug>/<int:app_num>/start
    - POST /api/app/<model_slug>/<int:app_num>/stop
    - POST /api/app/<model_slug>/<int:app_num>/restart
    - POST /api/model/<model_slug>/containers/start
    - POST /api/model/<model_slug>/containers/stop

- analysis
  - Security
    - GET /api/analysis/security — List
    - POST /api/analysis/security — Create
    - POST /api/analysis/security/<int:app_id> — Create for app
    - POST /api/analysis/security/start — Create+start comprehensive
    - POST /api/analysis/security/configure — Update config
    - GET /api/analysis/security/<int:analysis_id>/results — Results
  - Performance
    - GET /api/analysis/performance — List
    - POST /api/analysis/performance — Create
    - POST /api/analysis/performance/<int:app_id> — Create for app
  - Dynamic (ZAP-like)
    - GET /api/analysis/dynamic — List
    - POST /api/analysis/dynamic — Create
    - POST /api/analysis/dynamic/start — Start
    - GET /api/analysis/dynamic/<int:analysis_id>/results — Results
  - Batches & containerized
    - GET /api/analysis/batch — List batches
    - GET /api/analysis/containerized — List containerized tests
  - Batch creation & control
    - POST /api/batch — Create batch
    - GET /api/batch/<batch_id>/status — Batch status
    - POST /api/analysis/start/<int:app_id> — Start comprehensive analysis (BG service)
    - GET /api/analysis/configure/<int:app_id> — Config modal (template)
    - HTMX: GET /api/batch/active — Active batches partial
    - POST /api/batch/create — Create batch (BG service)
    - POST /api/batch/<batch_id>/start — Start batch (BG service)

- statistics
  - GET /api/stats/apps — App stats
  - GET /api/stats/models — Model stats
  - GET /api/stats/analysis — Analysis stats
  - GET /api/stats/recent — Recent stats
  - GET /api/models/distribution — Distribution
  - GET /api/generation/trends — Trends
  - GET /api/analysis/summary — Summary
  - GET /api/export — Export snapshot
  - HTMX helpers:
    - GET /api/stats_total_models
    - GET /api/stats_models_trend
    - GET /api/stats_total_apps
    - GET /api/stats_security_tests
    - GET /api/stats_performance_tests
    - GET /api/stats_container_status
    - GET /api/stats_completed_analyses
    - GET /api/stats_analysis_trend
    - GET /api/stats_system_health
    - GET /api/stats_uptime
    - GET /api/stats_running_containers
  - Template renderers:
    - GET /api/statistics/test-results
    - GET /api/statistics/model-rankings
    - GET /api/statistics/error-analysis

- dashboard
  - GET /api/dashboard/overview — Overview counters
  - GET /api/dashboard/activity — Recent activity
  - GET /api/dashboard/charts — Chart datasets
  - GET /api/dashboard/health — Health summary
  - HTMX/template:
    - GET /api/dashboard/activity-timeline — Timeline partial
    - GET /api/sidebar_stats — Sidebar stats partial
    - GET /api/recent_activity — Recent activity partial
    - GET /api/recent_activity_detailed — Detailed activity partial
    - GET /api/models_overview_summary — Models overview summary
    - GET /api/performance_chart_data — Performance chart partial
    - GET /api/security_distribution_data — Security distribution partial
    - GET /api/dashboard/recent-models — Recent models partial
    - GET /api/realtime/dashboard — Realtime dashboard partial
    - GET /api/dashboard/docker-status — Docker status partial

- results
  - GET /api/results — Paginated results
  - GET /api/results/running — Running analyses
  - GET /api/results/statistics — Result stats
  - GET /api/results/cards — Card summaries
  - GET /api/results/timeline — Timeline data
  - GET /api/results/<int:result_id> — Result detail
  - GET /api/results/<int:result_id>/export — Export single result

  

- websocket API (separate blueprint; prefix: /api/websocket)
  - GET /api/websocket/status — WebSocket service status
  - GET /api/websocket/analyses — Active analyses
  - POST /api/websocket/analysis/start — Start analysis
  - POST /api/websocket/analysis/<analysis_id>/cancel — Cancel analysis
  - GET /api/websocket/events — Event log (mock)
  - POST /api/websocket/broadcast — Broadcast message
  - POST /api/websocket/test — Start a test analysis

## Notes

- Many endpoints labeled “HTMX” return HTML partials and are intended for dynamic page updates without full reloads.
- Some endpoints under UI blueprints intentionally use `/api/...` paths but are not part of the main API blueprint; they produce JSON or small HTML fragments for those pages.
- Security-sensitive and long-running operations are dispatched to Celery tasks via services; consult `src/app/tasks.py` and service layer for orchestration details.
