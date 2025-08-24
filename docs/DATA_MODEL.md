# Data Model

> Navigation: [Overview](OVERVIEW.md) · [Architecture](ARCHITECTURE.md) · [Analysis Pipeline](ANALYSIS_PIPELINE.md) · [Request Flow](REQUEST_FLOW.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Dev Guide](DEVELOPMENT_GUIDE.md) · [Observability](OBSERVABILITY.md)

This document describes the persistent schema: relational tables, their key columns, relationships, indexing strategy, and JSON payload conventions.

## Modeling Principles

- Normalize core entities (models, applications, analyses) but allow flexible evolution through JSON blobs.
- Store large analyzer output verbatim (JSON) + compute lightweight summary metrics for dashboards.
- Use explicit status enums (`analysisstatus`) across analysis-related tables for uniform state transitions.
- Timestamp every record (created_at / updated_at, plus domain-specific started_at / completed_at) for auditing and trend analysis.

## Core Entities

### ModelCapability (`model_capabilities`)
Represents an AI model’s catalog entry and technical/business characteristics.
Key Columns:
- `model_id` (unique external ID)
- `canonical_slug` (stable slug, unique)
- `provider` (vendor / hosting provider)
- Capability Flags: `supports_function_calling`, `supports_vision`, `supports_streaming`, `supports_json_mode`
- Pricing: `input_price_per_token`, `output_price_per_token`
- Metrics: `cost_efficiency`, `safety_score`
- `installed` (boolean, denotes locally available/seeded model)
- JSON: `capabilities_json`, `metadata_json`
Indexes: model_id, canonical_slug, provider, installed (for filtering UI lists / dashboards).
Lifecycle: Seeded from `misc/model_capabilities.json` & `misc/models_summary.json`; enriched via `OpenRouterService`.

### GeneratedApplication (`generated_applications`)
Represents a concrete generated app variant for a model (identified by model slug + app_number).
Key Columns (representative subset – consult ORM for full set):
- Foreign keys: (implicit relationship to `ModelCapability` via slug / external join logic)
- `app_number` (sequence per model)
- `app_type` (normalized short string)
- Status: `generation_status` (enum reuse), `container_status`
- Frameworks: `backend_framework`, `frontend_framework`
- JSON blobs for code generation metadata (not all shown in migrations excerpt)
Indexes: Historically on `app_number`, `generation_status`, `container_status` (some removed in migration 19355bb85378 to optimize or relocate logic).
Lifecycle: Created when generating apps; used to resolve container names & ports.

### PortConfiguration (`port_configuration`)
Maps (model_slug, app_number) to reserved host ports (backend/front-end) ensuring stable routing.
Key Columns:
- `model_slug`, `app_number`
- `backend_port`, `frontend_port`
- Possibly `allocated_at` timestamp (confirm in ORM)
Lifecycle: Allocated on-demand via `PortService.allocate_ports`; released via `PortService.release_ports`.

## Analysis Tables

All analysis tables share structural patterns: status enum, counts/metrics, JSON results, started/completed timestamps.

### SecurityAnalysis (`security_analyses`)
Captures multi-tool static/dynamic security scan aggregates.
Key Columns (see migration 44361c0e780d additions):
- `analysis_name`, `description`
- Tool Config JSON blobs: `bandit_config_json`, `safety_config_json`, `pylint_config_json`, `eslint_config_json`, `npm_audit_config_json`, `snyk_config_json`, `zap_config_json`, `semgrep_config_json`
- Enable Flags: `zap_enabled`, `semgrep_enabled`
- Policy: `severity_threshold`, `max_issues_per_tool`, `timeout_minutes`
- Scope filters: `exclude_patterns`, `include_patterns`
- Execution metrics: `tools_run_count`, `tools_failed_count`
- `global_config_json` (aggregated resolved configuration)
- Standard status/timing columns.

### PerformanceTest (`performance_tests` or equivalent)*
Stores results of performance benchmarking runs.
Typical Columns:
- `application_id`
- `status`
- Metrics: latency percentiles (p50/p90/p95), throughput, error_rate (may be embedded in JSON if not promoted)
- `results_json`, `metadata_json`
- `started_at`, `completed_at`
*Confirm exact table name in ORM; adapt doc if different.*

### ZAPAnalysis (`zap_analyses`)
Dynamic security scan (OWASP ZAP) results.
Key Columns (migration 19355bb85378):
- `application_id`
- Counts: `total_alerts`, `high_risk_count`, `medium_risk_count`, `low_risk_count`, `informational_count`
- `results_json`, `metadata_json`
- `analysis_duration`, timestamps
Indexes: `application_id`, `status` for retrieval & dashboards.

### OpenRouterAnalysis (`openrouter_analyses`)
Meta-analysis of app adherence to requirements, using AI evaluation.
Columns (migration 19355bb85378):
- `application_id`
- Requirements metrics: `total_requirements`, `met_requirements`, `unmet_requirements`
- Confidence counts: `high_confidence_count`, `medium_confidence_count`, `low_confidence_count`
- `analysis_duration`
- `results_json`, `metadata_json`
- Status, timestamps, indices on `application_id`, `status`.

### Additional / Planned Analyses
Static and AI analyses follow same pattern; verify table names (`static_analyses`, `ai_analyses`) if present; if not yet migrated they may be transient or consolidated.

## Supporting Tables

### BatchAnalysis / BatchJob
Tracks multi-analysis batch execution groups; likely fields: job id, name, description, target models/apps, counts of total/completed/failed, timestamps, status. Cleanup operates by age.

### AnalysisConfig / ConfigPreset
Persist stored analyzer configurations (security tool selection, thresholds). Fields typically: name, description, JSON config, created/updated timestamps.

## JSON Field Conventions

| Field Pattern | Purpose | Structure |
|---------------|---------|----------|
| `*_config_json` | Tool configuration snapshot | Dict serialized (tool-specific keys) |
| `results_json` | Primary raw analyzer output | Nested dict/array (tool outputs, findings, metrics) |
| `metadata_json` | Supplemental metadata (environment, versions) | Dict (contextual meta) |
| `global_config_json` | Resolved merged config (security) | Dict (derived effective config) |

Guidelines:
- Always serialize via `json.dumps` once; avoid double-encoding.
- Accessors in model/service should `json.loads` lazily to minimize repeated parsing.
- Maintain backward compatibility: if schema evolves, guard key access with `.get()`.

## Relationships (Conceptual)

```
ModelCapability 1 --- * GeneratedApplication 1 --- * (SecurityAnalysis | PerformanceTest | ZAPAnalysis | OpenRouterAnalysis)
											  \--- * PortConfiguration
```

Foreign keys explicitly defined at least from analyses to `generated_applications` (see migrations). Model link may be inferred through application.

## Status Lifecycle

Unified enum values: PENDING → RUNNING → (COMPLETED | FAILED | CANCELLED). Some tables track intermediate metrics updates while RUNNING.

## Indexing Strategy

- Lookups by `canonical_slug`, `provider` (model filter UIs).
- Per-application analysis retrieval: index `application_id` + `status`.
- Installed filter: index on `model_capabilities.installed`.
- Potential future composite: (`application_id`, `status`) already partially covered by separate indices; composite may improve selective queries if both always present.

## Data Initialization & Sync

`DataInitializationService` orchestrates:
1. Loading model capabilities summary & details from `misc/` JSON.
2. Loading generated applications metadata.
3. Loading/allocating port configuration (ensuring DB-first canonical source).
4. Marking installed models (setting `installed = true`).

## Retention & Cleanup

Cleanup services remove aged rows from analysis tables and batch jobs. Strategy:
- Age threshold (hours/days) parameter.
- Optionally archive JSON outside DB before deletion (future enhancement).

## Evolving the Schema

When adding a new analyzer:
1. Create new table with: id PK, FK to `generated_applications`, status enum, metrics columns, results_json, metadata_json, started/completed timestamps.
2. Add indices on (`application_id`), (`status`).
3. Provide accessor service methods returning parsed JSON and summary dicts.
4. Update this document & migrations.

## Open Questions / TODO

- Confirm presence & naming of performance tests table for doc alignment.
- Evaluate need for composite index on (`canonical_slug`, `provider`).
- Consider materialized aggregate table for dashboard counts to reduce heavy JSON scans.

---
_Last updated: 2025-08-24._ 
