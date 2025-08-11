# Route Organization Documentation

## Blueprint Structure

The application is now organized into well-defined blueprints with clear separation of concerns:

### 1. MAIN BLUEPRINT (`/`)
**Purpose**: Core application pages and basic functionality
- `/` - Main dashboard
- `/about` - About page
- `/testing` - Testing console overview
- `/models_overview` - Basic models overview (legacy)
- `/api/stats` - Basic dashboard statistics

### 2. MODELS BLUEPRINT (`/models`)
**Purpose**: Model management and visualization
- `/models/` - Models overview page
- `/models/applications` - Generated applications listing
- `/models/application/<id>` - Individual application details
- `/models/model_actions[/<slug>]` - Model configuration actions
- `/models/model_apps/<slug>` - Applications for specific model

### 3. ANALYSIS BLUEPRINT (`/analysis`)
**Purpose**: Analysis operations and testing forms
- `/analysis/security_test_form` - Security testing form
- `/analysis/performance_test_form` - Performance testing form
- `/analysis/get_model_apps` - HTMX endpoint for model apps dropdown
- `/analysis/security/start` - Start security analysis
- `/analysis/security/run` - Run security test (alias)
- `/analysis/performance/start` - Start performance analysis
- `/analysis/performance/run` - Run performance test (alias)
- `/analysis/batch/start` - Start batch analysis

### 4. API BLUEPRINT (`/api`)
**Purpose**: REST API endpoints and HTMX data providers
- **Dashboard APIs**: `/api/dashboard/*` - Dashboard widgets data
- **Statistics APIs**: `/api/stats_*` - Various statistics endpoints
- **System APIs**: `/api/system_*` - System health and status
- **Tasks APIs**: `/api/tasks/*` - Task management
- **Analysis APIs**: `/api/analysis/*` - Analysis operations
- **Models APIs**: `/api/models/*` - Model data endpoints
- **Testing APIs**: `/api/testing/*` - Testing status and data

### 5. BATCH BLUEPRINT (`/batch`)
**Purpose**: Batch analysis operations
- `/batch/` - Batch overview dashboard
- `/batch/create` - Create new batch (GET/POST)
- `/batch/<id>` - Batch details
- `/batch/list` - HTMX batch list partial
- `/batch/form` - HTMX batch form partial
- `/batch/api/*` - Batch management APIs

### 6. STATISTICS BLUEPRINT (`/statistics`)
**Purpose**: Comprehensive statistics and reporting
- `/statistics/` - Statistics overview dashboard
- `/statistics/api/models/distribution` - Model distribution data
- `/statistics/api/generation/trends` - Generation trends
- `/statistics/api/analysis/summary` - Analysis summary
- `/statistics/api/export` - Export statistics

### 7. ADVANCED BLUEPRINT (`/advanced`)
**Purpose**: Advanced features and detailed views
- `/advanced/apps` - Advanced apps grid view
- `/advanced/models` - Advanced models view
- `/advanced/api/apps/*` - Advanced app APIs
- `/advanced/api/models/*` - Advanced model APIs
- `/advanced/api/analysis/*` - Advanced analysis operations

## Template Organization

### Pages Templates (`/templates/pages/`)
Full page templates that extend `base.html`:
- `dashboard.html` - Main dashboard
- `models_overview.html` - Models overview
- `batch_testing.html` - Batch testing
- `statistics_overview.html` - Statistics
- `testing.html` - Testing console
- `apps_grid.html` - Apps grid view

### Partials Templates (`/templates/partials/`)
Organized by functionality:

#### `/partials/apps_grid/`
- `apps_grid.html` - Apps grid display
- `apps_list.html` - Apps list view
- `apps_compact.html` - Compact apps view
- `app_details.html` - Individual app details
- `analysis_config.html` - Analysis configuration

#### `/partials/models/`
- `models_cards.html` - Card view of models
- `models_table.html` - Table view of models
- `models_list.html` - List view of models
- `models_grid.html` - Grid view of models
- `models_cards_grouped.html` - Grouped card view
- `models_table_grouped.html` - Grouped table view

#### `/partials/testing/`
- `analysis_results.html` - Analysis results display
- `batch_list.html` - Batch analysis list
- `batch_form.html` - Batch creation form
- `security_test_form.html` - Security testing form
- `performance_test_form.html` - Performance testing form

#### `/partials/common/`
- `active_tasks.html` - Active tasks widget
- `activity_timeline.html` - Activity timeline
- `sidebar_stats.html` - Sidebar statistics
- `error.html` - Error display template
- `container_status.html` - Container status widget
- `model_apps_select.html` - Model apps dropdown

#### `/partials/dashboard/`
- `analyzer_services.html` - Analyzer services status
- `docker_status.html` - Docker status display
- Other dashboard-specific widgets

## Key Improvements

### 1. ✅ Removed HTML from Routes
- All inline HTML strings replaced with proper templates
- Clean separation between logic and presentation
- Better error handling with templates

### 2. ✅ Fixed Duplicate Routes
- Removed duplicate routes from factory.py
- Consolidated similar functionality
- Clear ownership of endpoints

### 3. ✅ Improved Blueprint Organization
- Logical grouping by functionality
- Consistent URL prefixes
- Clear separation of concerns

### 4. ✅ HTMX/API Standardization
- Consistent HTMX endpoint patterns
- Proper partial template rendering
- RESTful API design

### 5. ✅ Template Structure
- Organized partials by feature area
- Reusable components
- Consistent naming conventions

## Route Testing Status

All routes have been tested and are working correctly:
- ✅ All main pages load successfully
- ✅ All HTMX endpoints function properly
- ✅ No duplicate route conflicts
- ✅ Template references updated correctly
- ✅ Error handling uses templates

## Development Guidelines

### Adding New Routes
1. Choose appropriate blueprint based on functionality
2. Use consistent URL patterns
3. Return templates, not HTML strings
4. Follow RESTful conventions for APIs
5. Document in this file

### Template Usage
1. Use partials for HTMX responses
2. Use pages for full page loads
3. Organize by feature area
4. Include error templates for exception handling

### HTMX Patterns
1. Use `hx-get` for data loading
2. Use `hx-post` for form submissions
3. Target specific containers
4. Return appropriate partial templates
