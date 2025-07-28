# Frontend Development Prompt: Thesis Research App with HTMX & Missing.css

## Project Overview
Create a modern, responsive frontend for a Flask-based AI research application that analyzes thousands of generated applications across 30 AI models. The frontend should use HTMX for dynamic interactions and Missing.css for clean, minimal styling.

## Technical Requirements

### Core Technologies
- **CSS Framework**: Missing.css (https://missing.style/) - A minimal, nearly-classless CSS framework
- **JavaScript Library**: HTMX - For dynamic content loading and interactions without writing JavaScript
- **Template Engine**: Jinja2 (Flask templating)
- **Architecture**: Server-side rendered with HTMX partial updates
- **Optional Enhancement**: _hyperscript for complex client-side behaviors

### CSS Framework Integration
```html
<!-- Include Missing.css CDN -->
<link rel="stylesheet" href="https://unpkg.com/missing.css@1.1.3">
<!-- Optional: Prism theme for code highlighting -->
<link rel="stylesheet" href="https://unpkg.com/missing.css@1.1.3/prism">
```

### HTMX Integration
```html
<!-- Include HTMX -->
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
<!-- Optional: Include _hyperscript for advanced interactions -->
<script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
```

## Application Context

### Research Data Structure
The application manages:
- **30 AI Models** across 13 providers (Anthropic, OpenAI, DeepSeek, Google, Qwen, etc.)
- **30 Application Types** per model (login systems, chat apps, e-commerce, etc.)
- **900+ Generated Applications** total (30 models × 30 apps)
- **Docker Containers** for each application with unique port assignments
- **Security Analysis** results (bandit, safety, eslint, npm_audit)
- **Performance Testing** data and metrics
- **ZAP Security Scanning** results
- **Batch Processing** jobs and queues

### Implemented Routes Structure (from web_routes.py)

#### Main Routes
```python
# Dashboard and core pages
/ - Main dashboard with app grid
/app/<model>/<int:app_num> - Individual app details
/models - Models overview page
```

#### API Routes (HTMX endpoints)
```python
/api/status/<model>/<int:app_num> - Container status updates
/api/search - Live search endpoint
/api/advanced-search - Multi-filter search
/api/cache/stats - Cache statistics
/api/cache/clear - Clear cache action
/api/dashboard-stats - Dashboard statistics
/api/recent-activity - Activity feed
/api/header-stats - Navbar statistics
/api/sidebar-stats - Sidebar counters
/api/health-status - System health check
/api/system-health - Detailed health status
/api/notifications - User notifications
/api/settings - Get/save settings
```

#### Feature Routes
```python
# Docker management
/docker/ - Docker overview
/docker/<action>/<model>/<int:app_num> - Container actions (start/stop/restart)
/docker/logs/<model>/<int:app_num> - View container logs

# Analysis
/analysis/ - Analysis overview
/analysis/<type>/<model>/<int:app_num> - Analysis details
/analysis/<type>/<model>/<int:app_num>/run - Run analysis

# Performance
/performance/ - Performance overview
/performance/<model>/<int:app_num> - Performance test page
/performance/<model>/<int:app_num>/run - Run performance test

# ZAP Security
/zap/ - ZAP overview
/zap/<model>/<int:app_num> - ZAP scan page
/zap/<model>/<int:app_num>/scan - Start scan
/zap/<model>/<int:app_num>/status - Scan status

# OpenRouter
/openrouter/ - OpenRouter overview
/openrouter/<model>/<int:app_num> - Analysis page
/openrouter/<model>/<int:app_num>/analyze - Run analysis

# Batch Processing
/batch/ - Batch overview
/batch/create - Create batch job
/batch/job/<job_id> - Job status

# Generation
/generation/ - Generation overview
/generation/run/<timestamp> - Run details
```

## Frontend Requirements

### 1. Template Structure (Based on Actual Routes)

```
src/templates/
├── base.html                    # Base template with Missing.css
├── pages/                       # Full page templates
│   ├── dashboard.html          # Main dashboard (/)
│   ├── app_details.html        # App details page
│   ├── models_overview.html    # Models listing
│   ├── docker_overview.html    # Docker management
│   ├── analysis_overview.html  # Analysis tools
│   ├── analysis_details.html   # Analysis results
│   ├── performance_overview.html # Performance dashboard
│   ├── performance_test.html   # Performance test page
│   ├── zap_overview.html       # ZAP dashboard
│   ├── zap_scan.html          # ZAP scan page
│   ├── openrouter_overview.html # OpenRouter dashboard
│   ├── openrouter_analysis.html # OpenRouter analysis
│   ├── batch_overview.html     # Batch processing
│   ├── batch_create.html       # Create batch job
│   ├── generation_overview.html # Generation dashboard
│   ├── generation_run_details.html # Run details
│   ├── logs.html              # Container logs viewer
│   └── error.html             # Error page
└── partials/                    # HTMX partial templates
    ├── app_list.html           # App grid/list
    ├── app_tab_*.html          # App detail tabs
    ├── container_status.html   # Container status widget
    ├── container_logs.html     # Log viewer content
    ├── dashboard_stats.html    # Statistics cards
    ├── header_stats.html       # Navbar stats
    ├── sidebar_stats.html      # Sidebar counters
    ├── health_indicator.html   # Health status
    ├── system_health.html      # System health details
    ├── notifications_list.html # Notifications dropdown
    ├── settings_form.html      # Settings modal content
    ├── cache_info.html         # Cache statistics
    ├── recent_activity.html    # Activity feed
    ├── analysis_results.html   # Analysis results
    ├── analysis_error.html     # Analysis error state
    ├── performance_results.html # Performance results
    ├── zap_results.html        # ZAP scan results
    ├── zap_status.html         # ZAP scan progress
    ├── openrouter_results.html # OpenRouter results
    ├── batch_job_status.html   # Batch job progress
    ├── advanced_search_results.html # Search results
    ├── success_message.html    # Success notifications
    └── error_message.html      # Error notifications
```

### 2. Key UI Components

#### Main Dashboard (`pages/dashboard.html`)
```html
{% extends "base.html" %}

{% block content %}
<!-- Dashboard Header Stats -->
<div class="dashboard-header" 
     hx-get="/api/dashboard-stats" 
     hx-trigger="load, every 30s"
     hx-target="this">
    <div class="loading">Loading statistics...</div>
</div>

<!-- Search and Filters -->
<div class="search-section">
    <input type="search" 
           name="search"
           hx-get="/api/search" 
           hx-trigger="keyup changed delay:500ms"
           hx-target="#app-grid"
           placeholder="Search models or apps...">
    
    <select hx-get="/api/search" 
            hx-trigger="change"
            hx-target="#app-grid"
            name="model">
        <option value="">All Models</option>
        {% for model in unique_models %}
        <option value="{{ model }}">{{ model }}</option>
        {% endfor %}
    </select>
    
    <select hx-get="/api/search" 
            hx-trigger="change"
            hx-target="#app-grid"
            name="status">
        <option value="">All Statuses</option>
        <option value="running">Running</option>
        <option value="stopped">Stopped</option>
    </select>
</div>

<!-- App Grid -->
<div id="app-grid" class="app-grid">
    {% include "partials/app_list.html" %}
</div>

<!-- Load More -->
{% if has_more %}
<div hx-get="/?page={{ filters.page + 1 }}&component=apps-list" 
     hx-trigger="revealed"
     hx-target="#app-grid"
     hx-swap="beforeend">
    <div class="loading">Loading more...</div>
</div>
{% endif %}
{% endblock %}
```

#### App Details Page (`pages/app_details.html`)
```html
{% extends "base.html" %}

{% block content %}
<div class="app-details">
    <header>
        <h1>{{ model }} - App {{ app_num }}</h1>
        <div class="app-info">
            <span>{{ app.description }}</span>
        </div>
    </header>
    
    <!-- Container Status -->
    <div class="container-status-section"
         hx-get="/api/status/{{ model }}/{{ app_num }}"
         hx-trigger="load, every 5s"
         hx-target="this">
        {% include "partials/container_status.html" %}
    </div>
    
    <!-- Action Buttons -->
    <div class="actions">
        <button hx-post="/docker/start/{{ model }}/{{ app_num }}"
                hx-target=".container-status-section"
                class="btn-primary">Start</button>
        <button hx-post="/docker/stop/{{ model }}/{{ app_num }}"
                hx-target=".container-status-section"
                class="btn-danger">Stop</button>
        <button hx-get="/docker/logs/{{ model }}/{{ app_num }}"
                hx-target="#modal-container">View Logs</button>
    </div>
    
    <!-- Tabs -->
    <div class="tabs">
        <button hx-get="/app/{{ model }}/{{ app_num }}?tab=analysis"
                hx-target="#tab-content"
                class="tab active">Analysis</button>
        <button hx-get="/app/{{ model }}/{{ app_num }}?tab=performance"
                hx-target="#tab-content"
                class="tab">Performance</button>
        <button hx-get="/app/{{ model }}/{{ app_num }}?tab=security"
                hx-target="#tab-content"
                class="tab">Security</button>
    </div>
    
    <div id="tab-content">
        <!-- Tab content loaded here -->
    </div>
</div>
{% endblock %}
```

#### Container Status Partial (`partials/container_status.html`)
```html
<div class="container-status">
    <div class="status-card">
        <h4>Backend</h4>
        <span class="status-badge {{ 'running' if statuses.backend == 'running' else 'stopped' }}">
            {{ statuses.backend }}
        </span>
        <small>Port: {{ statuses.backend_port }}</small>
    </div>
    
    <div class="status-card">
        <h4>Frontend</h4>
        <span class="status-badge {{ 'running' if statuses.frontend == 'running' else 'stopped' }}">
            {{ statuses.frontend }}
        </span>
        <small>Port: {{ statuses.frontend_port }}</small>
    </div>
</div>

{% if success_message %}
<div class="alert success">{{ success_message }}</div>
{% endif %}
```

### 3. CSS Styling with Missing.css

```css
/* custom.css - Extends Missing.css */
:root {
    --app-primary: #2563eb;
    --app-success: #10b981;
    --app-warning: #f59e0b;
    --app-danger: #ef4444;
    --app-info: #3b82f6;
}

/* Dashboard Layout */
.dashboard-header {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}

.stat-card {
    background: white;
    padding: 1.5rem;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.stat-value {
    font-size: 2rem;
    font-weight: bold;
    color: var(--app-primary);
}

/* App Grid */
.app-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}

.app-card {
    background: white;
    border-radius: 0.5rem;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.app-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* Status Badges */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
}

.status-badge.running {
    background: rgba(16, 185, 129, 0.1);
    color: var(--app-success);
}

.status-badge.stopped {
    background: rgba(239, 68, 68, 0.1);
    color: var(--app-danger);
}

/* Container Status */
.container-status {
    display: flex;
    gap: 1rem;
    margin: 1rem 0;
}

.status-card {
    flex: 1;
    padding: 1rem;
    background: #f9fafb;
    border-radius: 0.5rem;
}

/* Tabs */
.tabs {
    display: flex;
    border-bottom: 2px solid #e5e7eb;
    margin: 2rem 0 1rem;
}

.tab {
    padding: 0.75rem 1.5rem;
    background: none;
    border: none;
    cursor: pointer;
    position: relative;
}

.tab.active::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--app-primary);
}

/* Search Section */
.search-section {
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
}

.search-section input[type="search"] {
    flex: 1;
}

/* Loading States */
.loading {
    text-align: center;
    padding: 2rem;
    color: #6b7280;
}

.htmx-request .loading {
    display: block;
}

.htmx-request.loading {
    opacity: 0.5;
}

/* Alerts */
.alert {
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 1rem 0;
}

.alert.success {
    background: #d1fae5;
    color: #065f46;
}

.alert.error {
    background: #fee2e2;
    color: #991b1b;
}
```

### 4. HTMX Patterns for Your Routes

#### Auto-refreshing Dashboard Stats
```html
<div hx-get="/api/dashboard-stats" 
     hx-trigger="load, every 30s"
     hx-swap="innerHTML">
    <!-- Stats loaded here -->
</div>
```

#### Live Search
```html
<input type="search" 
       hx-get="/api/search" 
       hx-trigger="keyup changed delay:500ms"
       hx-target="#app-grid"
       hx-include="[name='model'], [name='status']">
```

#### Container Actions
```html
<button hx-post="/docker/start/{{ model }}/{{ app_num }}"
        hx-target=".container-status-section"
        hx-confirm="Start containers for {{ model }}/app{{ app_num }}?">
    Start
</button>
```

#### Analysis Execution
```html
<form hx-post="/analysis/backend_security/{{ model }}/{{ app_num }}/run"
      hx-target="#analysis-results">
    <label>
        <input type="checkbox" name="use_all_tools" value="true">
        Use all available tools
    </label>
    <button type="submit">Run Analysis</button>
</form>
```

#### Batch Job Creation
```html
<form hx-post="/batch/create"
      hx-target="#batch-status">
    <select name="operation_type" required>
        <option value="security_analysis">Security Analysis</option>
        <option value="performance_test">Performance Test</option>
        <option value="zap_scan">ZAP Scan</option>
    </select>
    
    <fieldset>
        <legend>Select Models</legend>
        {% for model in models %}
        <label>
            <input type="checkbox" name="models" value="{{ model }}">
            {{ model }}
        </label>
        {% endfor %}
    </fieldset>
    
    <button type="submit">Create Batch Job</button>
</form>
```

### 5. Modal System
```html
<!-- Base template includes modal container -->
<div id="modal-container"></div>

<!-- Trigger modal -->
<button hx-get="/docker/logs/{{ model }}/{{ app_num }}"
        hx-target="#modal-container">
    View Logs
</button>

<!-- Modal content returned by server -->
<div class="modal-overlay" _="on click from outside .modal remove me">
    <div class="modal">
        <header>
            <h3>Container Logs</h3>
            <button _="on click remove closest .modal-overlay">×</button>
        </header>
        <div class="modal-body">
            <!-- Log content -->
        </div>
    </div>
</div>
```

### 6. Error Handling
```html
<!-- Global error handler in base template -->
<script>
document.body.addEventListener('htmx:responseError', function(evt) {
    const target = evt.detail.target;
    target.innerHTML = '<div class="alert error">Request failed. Please try again.</div>';
});
</script>
```

### 7. Navigation Structure
```html
<nav class="navbar">
    <a href="/" class="brand">Thesis Research App</a>
    
    <div class="nav-links">
        <a href="/">Dashboard</a>
        <a href="/models">Models</a>
        <a href="/docker/">Docker</a>
        <a href="/analysis/">Analysis</a>
        <a href="/batch/">Batch</a>
    </div>
    
    <div class="nav-stats" 
         hx-get="/api/header-stats" 
         hx-trigger="load, every 60s">
        <!-- Stats loaded here -->
    </div>
</nav>
```

## Development Guidelines

1. **Keep it Simple**: Use Missing.css defaults where possible
2. **HTMX First**: Prefer HTMX attributes over JavaScript
3. **Progressive Enhancement**: Ensure basic functionality works without JavaScript
4. **Consistent Patterns**: Use the same HTMX patterns throughout
5. **Server-Side Logic**: Keep business logic in Flask, not frontend
6. **Semantic HTML**: Use proper HTML5 elements
7. **Accessibility**: Include proper ARIA labels and keyboard navigation

This frontend implementation directly maps to your Flask routes and provides a clean, maintainable interface for your thesis research application.
