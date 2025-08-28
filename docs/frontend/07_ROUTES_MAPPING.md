# Routes → Templates Mapping

This document tracks current (legacy) and target template paths per route group. Update as domains migrate.

## Legend
- Legacy Path: what route currently renders (may pass through compatibility wrapper)
- Target Path: canonical new template path
- Status: Pending | Migrated | Consolidated

## Main (`main_bp`)
| Route | Legacy Path | Target Path | Status |
|-------|-------------|-------------|--------|
| `/` | `views/dashboard/index.html` | `pages/analysis/dashboard.html` or dedicated `pages/dashboard/overview.html` (decide) | Pending |
| `/about` | `views/about.html` | `pages/about/about.html` | Pending |
| `/system-status` | `views/system/status.html` | `pages/system/status.html` | Pending |
| `/spa/dashboard` | `spa/dashboard_content.html` | `pages/analysis/partials/dashboard_content.html` or `ui/elements/dashboard/...` | Pending |
| `/spa/analysis` | `spa/analysis_content.html` | `pages/analysis/spa/analysis_content.html` | Pending |

## Analysis (`/analysis`)
| Route | Legacy | Target | Status |
|-------|--------|--------|--------|
| `/analysis/dashboard` | `pages/analysis/dashboard.html` | same (already OK) | Migrated |
| `/analysis/list` | `pages/analysis/hub.html` | `pages/analysis/hub.html` | Migrated |
| `/analysis/` | `pages/analysis/hub.html` | same | Migrated |
| (partials) | `pages/analysis/partials/*.html` | same (normalize naming) | In Progress |

## Models
(Mapping needs extraction from `models.py`; fill as migrating.)

| Route (Examples) | Legacy | Target | Status |
|------------------|--------|--------|--------|
| `/models/` | likely `views/models/overview.html` (verify) | `pages/models/overview.html` | Pending |
| `/model/<slug>/details` | legacy partial chain | `pages/models/detail.html` + partials | Pending |
| `/model/<slug>/more-info` | legacy | `pages/models/more-info.html` (if kept) | Pending |
| `/import` | legacy | `pages/models/import.html` | Pending |

## Applications
| Route | Legacy | Target | Status |
|-------|--------|--------|--------|
| `/applications` | `views/applications/index.html` | `pages/applications/index.html` | Pending |
| `/application/<slug>/<num>` | legacy detail chain | `pages/applications/detail.html` + extracted partials | Pending |
| File/section exports | n/a (responses) | (no template) | - |

## Reports
| `/reports/` | `pages/reports/index.html` | same | Pending |

## Statistics
| `/statistics/` | TBD | `pages/statistics/overview.html` | Pending |
| `/statistics/generation` | TBD | `pages/statistics/generation.html` | Pending |
| `/statistics/analysis` | TBD | `pages/statistics/analysis.html` | Pending |
| `/statistics/charts` | TBD | `pages/statistics/charts.html` | Pending |

## System
| `/system/status` | see main | `pages/system/status.html` | Pending |
| `/system/logs` | legacy | `pages/system/logs.html` | Pending |
| `/system/settings` | legacy | `pages/system/settings.html` | Pending |

## Tasks
| `/tasks/` | TBD | `pages/tasks/overview.html` | Pending |

## Migration Tracking
Update this table as PRs land. Once a route is Migrated, remove reliance on compatibility shim for that blueprint file.

## Notes
- Some "legacy" names inferred; verify by searching route handlers before migrating.
- If target template needs splitting (e.g., detail view with tabs), create a parent + partials folder.

## Procedure for Updating
1. Migrate template & update route render call.
2. Mark status Migrated.
3. If consolidating duplicates, list them under Consolidations subsection below.

## Consolidations
List prior duplicate templates removed & their replacements.

| Removed | Replaced By | Date | PR |
|---------|-------------|------|----|
| (example) `partials/dashboard/_dashboard_stats_inner.html` | `ui/elements/dashboard/stats-cards.html` | YYYY-MM-DD | #NN |
