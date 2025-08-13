# Analysis & Statistics Refactor Plan

## Objectives
- Extract business logic from `routes/api/analysis.py` and `routes/api/statistics.py` into dedicated services
- Standardize JSON responses via `json_success` / `json_error` and `handle_exceptions`
- Reduce duplication of inline queries and aggregation logic
- Improve testability with isolated unit tests for service methods (mock Celery / background tasks)
- Preserve existing HTML/HTMX endpoints (phase 1) while refactoring JSON APIs

## Scope (Phase 1)
- Services: `analysis_service.py`, `statistics_service.py`
- Route refactor: only JSON API endpoints; leave template-rendering endpoints intact (may wrap later)
- Tests: `tests/test_analysis_service.py`, `tests/test_statistics_service.py`

## Models Involved
- `SecurityAnalysis` (id, application_id, status, tool enable flags, configs, counts, results_json, metadata_json, timestamps)
- `PerformanceTest` (id, application_id, status, test params, perf metrics, results_json)
- `ZAPAnalysis`, `OpenRouterAnalysis` (phase 2 for deeper integration; minimal read access Phase 1)
- Aggregations frequently join with `GeneratedApplication` / `ModelCapability`

## Identified Route Groups (analysis)
1. Listing & retrieval: list analyses, get single analysis
2. Creation / configuration: create security analysis, update configuration, create performance test
3. Execution: start security analysis, start comprehensive analysis, start performance test
4. Status / results: get analysis status, get results summary
5. Batch / composite: comprehensive analysis (multi-tool), potential batch operations (future)

## Identified Route Groups (statistics)
1. App-level stats (counts, recent activity)
2. Model-level stats (per model aggregations)
3. Analysis-level stats (counts, success/fail rates)
4. Recent activity & trends (time-window counts)
5. Distribution & rankings (model distribution, rankings, error analysis)
6. Export (JSON blob for offline use)
7. HTMX/template endpoints (defer; keep calling service read methods internally later)

## Service Responsibilities
### analysis_service
- list_security_analyses(application_id: Optional[int]) -> List[Dict]
- get_security_analysis(analysis_id: int) -> Dict
- create_security_analysis(application_id: int, payload: Dict) -> Dict
- update_security_analysis(analysis_id: int, payload: Dict) -> Dict
- start_security_analysis(analysis_id: int) -> Dict (enqueue task, update status)
- create_comprehensive_security_analysis(application_id: int, payload: Dict) -> Dict (pre-populated config)
- start_comprehensive_analysis(application_id: int) -> Dict (composite task orchestration)
- list_performance_tests(application_id: Optional[int]) -> List[Dict]
- get_performance_test(test_id: int) -> Dict
- create_performance_test(application_id: int, payload: Dict) -> Dict
- start_performance_test(test_id: int) -> Dict
- get_recent_activity(limit: int=5) -> Dict
- get_analysis_results(analysis_id: int) -> Dict (parse results)
- Error classes: `AnalysisNotFound`, `InvalidAnalysisState`, `TaskEnqueueError`

### statistics_service
- get_application_statistics() -> Dict
- get_model_statistics() -> Dict
- get_analysis_statistics() -> Dict
- get_recent_statistics() -> Dict
- get_model_distribution() -> Dict
- get_generation_trends(days: int=30) -> Dict
- get_analysis_summary() -> Dict
- export_statistics() -> Dict (aggregated snapshot)
- helper: _time_window_bounds(window: str) -> Tuple[datetime, datetime]
- Possibly caching layer (phase 2)

## Error Handling Strategy
- Define domain-specific exceptions; map to 404 / 400 / 500 via `handle_exceptions`
- Validation: use `require_fields` for minimal mandatory fields (application_id, test params)
- Return shapes always: { "success": bool, "data": {...}, "error": {...|None} }

## Route Refactor Mapping (examples)
- GET /api/analysis/security -> analysis_service.list_security_analyses
- POST /api/analysis/security -> analysis_service.create_security_analysis
- POST /api/analysis/security/<id>/start -> analysis_service.start_security_analysis
- POST /api/analysis/security/<id>/configure -> analysis_service.update_security_analysis
- POST /api/analysis/security/<id>/results -> analysis_service.get_analysis_results (or GET)
- POST /api/analysis/security/comprehensive -> analysis_service.create_comprehensive_security_analysis
- POST /api/analysis/security/comprehensive/start -> analysis_service.start_comprehensive_analysis
- GET /api/analysis/performance -> analysis_service.list_performance_tests
- POST /api/analysis/performance -> analysis_service.create_performance_test
- POST /api/analysis/performance/<id>/start -> analysis_service.start_performance_test

Statistics mapping similar: each existing JSON endpoint delegates to corresponding statistics_service method.

## Testing Plan
- Use in-memory SQLite; seed minimal GeneratedApplication + related analyses.
- Mock Celery task dispatch (patch run_security_analysis.delay etc.) to return stub object with id.
- analysis_service tests:
  * create + retrieve security analysis (default config applied)
  * start security analysis transitions status -> RUNNING
  * invalid start on already running raises InvalidAnalysisState
  * comprehensive creation populates all tool flags
  * performance test creation + start
- statistics_service tests:
  * application stats counts reflect created sample data
  * model statistics includes expected keys
  * analysis summary success/failure rates computed
  * generation trends length matches days param

## Phasing & Migration
1. Implement services & exceptions (no route changes yet) + tests.
2. Refactor analysis routes: replace inline logic with service calls; remove duplicated try/except.
3. Refactor statistics routes similarly.
4. Validate via existing test suite + new service tests.
5. (Optional) Introduce caching for expensive aggregations (model distribution, trends) with simple TTL.

## Assumptions
- Celery tasks accept analysis_id and handle status transitions; service only sets initial status + enqueues.
- BatchAnalysis & other specialized models handled in later phase; keep current behavior intact.
- HTML endpoints remain unchanged until services stabilized.

## Future Enhancements (Backlog)
- Pydantic schemas for request validation
- Pagination for listing endpoints
- Caching layer (Redis) for statistics
- OpenAPI spec generation
- WebSocket push for analysis status updates
- Consolidate similar counts across dashboard/statistics into shared queries

---
Prepared: Phase 1 blueprint ready for implementation.
