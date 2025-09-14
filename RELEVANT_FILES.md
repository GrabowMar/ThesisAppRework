Core analysis surface (kept)
---------------------------

- src/app/services/analysis_engines.py — engine wrappers (security, dynamic, static, performance)
- src/app/services/analyzer_integration.py — bridge to analyzer_manager.py and containers
- src/app/services/task_service.py — AnalysisTask/BatchAnalysis CRUD (batch table retained; heavy batch orchestration removed)
- src/app/routes/jinja/analysis.py — analysis routes (create/list/detail)
- src/templates/pages/analysis/** — Analysis UI (batch UI pending further simplification)
- analyzer/analyzer_manager.py — CLI to start/stop/analyze; service invocations
- analyzer/services/** — service processes (static-analyzer, dynamic-analyzer, performance-tester, ai-analyzer)
- analyzer/shared/** — protocol/client base for services

Removed or neutralized (legacy/out-of-scope)
-------------------------------------------

- analyzer/test_gateway.py — now skipped at collection; legacy gateway test depended on removed paths
- src/app/services/batch_service.py — removed (superseded by task_service.BatchAnalysisService)
- src/app/services/batch_scheduler.py — removed
- src/app/services/batch_result_cache_service.py — removed
- src/app/services/websocket_integration.py — removed (use celery_websocket_service or mock)
- src/app/services/analyzer_service.py — removed (use analysis_service and engines)
- src/app/services/container_service.py — removed
- src/app/services/huggingface_service.py — removed
- src/app/services/analysis_orchestrator.py — removed (legacy)
- src/app/services/analysis_config_models.py — removed (unused)
- src/app/services/analyzer_config_service.py — removed (unused)
- src/app/services/analyzer_config.py — removed (unused)
- src/app/services/results_loader.py — removed (unused)
- src/app/services/results_service.py — removed (unused)

Kept (active)
-------------

- src/app/services/celery_websocket_service.py — production websocket bridge
- src/app/services/mock_websocket_service.py — simple fallback used by factory during tests/dev

Notes
-----

- BatchAnalysis DB model stays for lightweight grouping via task_service.BatchAnalysisService. Full batch orchestration code was pruned for clarity.
- Future: If keeping only single-app runs, trim batch UI blocks in templates/pages/analysis/create.html and related routes.
