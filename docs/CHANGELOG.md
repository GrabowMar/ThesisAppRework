# Changelog

All notable changes to the ThesisApp platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Advanced batch scheduling
- Multi-language support (Java, Go, Rust)
- Cloud deployment templates (AWS, Azure, GCP)
- Interactive result comparison
- Historical trend analysis

---

## [2.0.0] - 2025-10-14

### Major Changes
- **Documentation Overhaul**: Complete restructuring with mermaid diagrams and advanced markdown features
- **Consolidated Structure**: Reduced from 50+ files to organized feature/guide/reference structure

### Added
- Comprehensive getting started guide with troubleshooting
- Feature-focused documentation (Generation, Analysis, Containers, Ports)
- How-to guides for common tasks
- Technical reference documentation

### Changed
- Main README now serves as navigation hub
- Historical documents moved to archive/
- Improved markdown formatting with collapsible sections
- Enhanced diagrams and visual guides

---

## [1.9.0] - 2025-10

### Added - Multi-Tier Template System
- **Automatic Model Classification**: Models categorized as "standard" (30B+ params) or "lite" (<30B params)
- **Lite Templates**: 60 simplified templates for weaker models in `misc/app_templates_lite/`
- **Tier-Specific Generation**: Automatic template selection based on model capability
- **Improved Weak Model Support**: 17B parameter models now generate 400+ line functional apps (vs. 200 lines previously)

### Added - Application Status System
- **Intelligent Caching**: Database-backed container status with configurable TTL (default 300s)
- **Docker Sync**: Manual sync endpoint for instant status updates
- **Bulk Operations**: Refresh all application statuses efficiently
- **Status Types**: `running`, `stopped`, `not_created`, `no_compose`

### Added - Frontend Enhancements
- **Tabler Components**: Complete migration from custom CSS to pure Tabler.io components
- **Application Detail Redesign**: Tab-based navigation with HTMX lazy loading
- **Icon Standardization**: All icons use `fa-solid` prefix consistently
- **Mobile Responsive**: Improved mobile/tablet experience
- **Statistics Dashboard**: Enhanced filtering, batch operations, CSV export

### Changed - Template Enhancements
- **Procedural Guardrails**: All 60 templates enhanced with step-by-step workflows
  - Backend: 5-step workflow, 16-point validation, 300-500 line targets
  - Frontend: 8-step workflow, 20-point validation, 400-600 line targets
- **Code Templates Restructured**: From implementation-heavy (280/550 lines) to structural guidance (90/120 lines)
- **Creative Freedom**: Templates now provide patterns, not complete code
- **Backup Files Disabled**: `.bak` files no longer created by default

### Fixed
- **Slug Normalization**: Dots in version numbers (e.g., `3.5`) preserved instead of converted to underscores
- **Duplicate Applications**: Fixed regex patterns causing filesystem/database mismatches
- **Port Substitution**: Verified working, added documentation to templates
- **Template ID Parameter**: JavaScript now sends numeric IDs instead of names

---

## [1.8.0] - 2025-09

### Added - Port Allocation System
- **Automatic Port Management**: Database-backed unique port allocation per model/app combination
- **Port Ranges**: Backend (5001-5999), Frontend (8001-8999)
- **CLI Tool**: `scripts/port_manager.py` for managing port allocations
- **Conflict Prevention**: Unique constraints ensure no duplicate assignments
- **Template Substitution**: Automatic `{{backend_port}}` and `{{frontend_port}}` replacement

### Added - Unified Analysis Pipeline
- **Tool Registry**: Centralized registry for all 15 analysis tools
- **Four Analyzer Services**: 
  - static-analyzer (port 2001): Security, quality, static analysis
  - dynamic-analyzer (port 2002): Runtime behavior, OWASP ZAP
  - performance-tester (port 2003): Load testing, benchmarking
  - ai-analyzer (port 2004): AI-powered code review
- **WebSocket Gateway** (port 8765): Real-time progress updates
- **Raw Outputs**: Tool-specific execution details embedded in results

### Changed
- **Analyzer Architecture**: Migrated from enum-based to registry-based tool management
- **Result Format**: Enhanced with `raw_outputs` section containing per-tool details
- **Docker Orchestration**: All analyzers managed via single `docker-compose.yml`

---

## [1.7.0] - 2025-08

### Added - Sample Generation Improvements
- **Enhanced Code Templates**: 
  - Backend: 90-line structural templates with Flask patterns
  - Frontend: 120-line templates with React/Vite patterns
  - Docker: Production-ready Dockerfile templates with health checks
- **Unified Generation Interface**: Combined individual/batch generation workflows
- **Template Preview**: Live preview of template content before generation
- **Batch Configuration**: JSON-based batch generation with parallel execution

### Changed
- **Scaffolding Process**: Improved file copying and directory structure
- **Template Substitution**: More robust port and variable replacement
- **Error Handling**: Better validation and error messages during generation

### Fixed
- **Missing Scaffold Files**: All necessary files now copied during scaffolding
- **Template Adherence**: AI models now better follow template structure
- **Generation Reliability**: Reduced incomplete or malformed outputs

---

## [1.6.0] - 2025-07

### Added - Database & Cleanup
- **Database Schema Optimization**: Removed 9 unused models
  - Removed: BatchQueue, BatchDependency, BatchSchedule, BatchResourceUsage, BatchTemplate
  - Removed: TestResults, EventLog, RequirementMatchCache
  - Tables dropped from database
- **Folder Cleanup**: Removed 14 empty folders
  - Generated folders: failures, large_content, logs, markdown, stats, summaries, tmp
  - Misc folders: .history, generated_conversations, profiles, requirements
- **Cleanup Scripts**: `scripts/drop_unused_tables.py` for safe table removal

### Added - Table Standardization
- **Consistent Icons**: All tables use `fa-solid` prefix
- **Uniform Labels**: Standardized filter labels with colons
- **Action Button Consistency**: Standardized icons across Applications, Analysis, Models tables

---

## [1.5.0] - 2025-06

### Added - Configuration Management
- **Environment Variables**: Centralized `.env` configuration
- **Settings Module**: `src/app/config/settings.py` for application settings
- **Config Manager**: `src/app/config/config_manager.py` for analyzer settings
- **Service Locator**: Dependency injection via `src/app/services/service_locator.py`

### Added - Task Management
- **Celery Integration**: Asynchronous task processing
- **Task Execution Service**: Lightweight in-process task advancement
- **WebSocket Bridge**: Real-time progress updates (Celery-backed or mock)
- **Task Monitoring**: Web UI for viewing active/completed tasks

---

## [1.4.0] - 2025-05

### Added - Frontend Architecture
- **Bootstrap 5**: Modern responsive framework (no jQuery)
- **HTMX**: Declarative partial loading and polling
- **Font Awesome**: Consistent iconography throughout
- **Progressive Enhancement**: JavaScript trimming in favor of server-side rendering

### Changed
- **JavaScript Reduction**: Removed heavy client-side models table
- **Feature Flags**: `data-models-server-mode`, `data-simple-sample-gen`, `data-disable-live-tasks`
- **Mobile Experience**: Improved sidebar, hamburger menu, touch interactions

---

## [1.3.0] - 2025-04

### Added - Analysis Features
- **Security Tools**: Bandit, Safety, Semgrep, OWASP ZAP
- **Performance Tools**: Locust, Apache Bench, custom load testers
- **Quality Tools**: Pylint, Flake8, ESLint, Radon
- **AI Review**: OpenRouter integration for code review

### Changed
- **Analysis Pipeline**: Unified orchestration across all tools
- **Result Format**: Standardized JSON schema for all analyzers
- **Progress Tracking**: Real-time WebSocket updates

---

## [1.2.0] - 2025-03

### Added - Model Management
- **Model Registry**: 50+ models from OpenAI, Anthropic, Google, Meta
- **Capability Tracking**: Model parameters, context length, pricing
- **Model Classification**: Automatic tier assignment based on capabilities
- **Model Gating**: Disable analysis for specific models via config

### Added - Application Management
- **Lifecycle Control**: Start, stop, restart generated applications
- **Status Monitoring**: Real-time container health checks
- **Port Management**: Automatic port allocation and tracking
- **File Explorer**: Browse generated application files

---

## [1.1.0] - 2025-02

### Added - Core Features
- **Flask Application**: Web interface and REST API
- **Database Models**: SQLAlchemy models for apps, tasks, results
- **Template System**: 60 application templates (30 backend, 30 frontend)
- **Docker Integration**: Container orchestration for generated apps

### Changed
- **Project Structure**: Organized into app/, templates/, static/, analyzer/
- **Database**: SQLite for development, PostgreSQL support for production

---

## [1.0.0] - 2025-01

### Initial Release
- Basic AI application generation
- Simple analysis pipeline
- Flask web interface
- SQLite database
- Docker support

---

## Migration Guides

### Migrating from 1.x to 2.0

#### Documentation
- Old docs archived in `docs/archive/`
- Update bookmarks to new structure:
  - `OVERVIEW.md` → `README.md`
  - `DEVELOPMENT_GUIDE.md` → `GETTING_STARTED.md`
  - Feature docs → `features/`
  - Guides → `guides/`

#### No Code Changes Required
- All existing functionality preserved
- No breaking API changes
- Database schema unchanged

### Migrating to Multi-Tier Templates (1.9.0)

#### If You Have Custom Templates
1. Decide if template should have a lite version
2. Create lite version in `misc/app_templates_lite/`
3. Follow lite template patterns (procedural, step-by-step)

#### If You Modified Generation Code
- Check `get_model_capability_tier()` function
- Update tier classification if needed
- Test with both standard and lite models

### Migrating to Port Allocation System (1.8.0)

#### Existing Applications
```bash
# Ports auto-allocated on first use
# No manual migration needed

# To verify ports
python scripts/port_manager.py list

# To fix conflicts (if any)
python scripts/port_manager.py check <model>
```

#### Custom Generation Code
```python
# Old way (hardcoded)
backend_port = 5001
frontend_port = 8001

# New way (automatic)
from src.app.services.port_allocation_service import PortAllocationService
ports = PortAllocationService.get_or_allocate_ports(model, app_num)
backend_port = ports["backend"]
frontend_port = ports["frontend"]
```

### Database Cleanup (1.6.0)

If upgrading from pre-1.6.0:

```bash
# Run cleanup script
cd src
python ../scripts/drop_unused_tables.py

# Or manual SQL
sqlite3 app.db <<EOF
DROP TABLE IF EXISTS batch_queues;
DROP TABLE IF EXISTS batch_dependencies;
DROP TABLE IF EXISTS batch_schedules;
DROP TABLE IF EXISTS batch_resource_usage;
DROP TABLE IF EXISTS batch_templates;
DROP TABLE IF EXISTS test_results;
DROP TABLE IF EXISTS event_logs;
DROP TABLE IF EXISTS requirement_matches_cache;
EOF
```

---

## Deprecation Notices

### Deprecated in 2.0.0
- **Old Documentation Structure**: Will be removed in 3.0.0
  - Use new organized structure in `docs/`
  - Old files available in `docs/archive/`

### Removed in 2.0.0
- None (all features preserved)

### Deprecated in 1.9.0
- **Single Template System**: Use multi-tier templates instead
  - Old templates still work but weak models perform better with lite templates

---

## Contributors

- Development Team
- Community Contributors
- Documentation Team

---

**Format**: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
**Versioning**: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
