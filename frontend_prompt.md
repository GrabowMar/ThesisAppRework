# Frontend Development Prompt: Thesis Research App with HTMX & Missing.css

## Project Overview
Create a modern, responsive frontend for a Flask-based AI research application that analyzes thousands of generated applications across 30 AI models. The frontend should use HTMX for dynamic interactions and Missing.css for clean, minimal styling.

## Technical Requirements

### Core Technologies
- **CSS Framework**: Missing.css (https://missing.style/) - A minimal, nearly-classless CSS framework
- **JavaScript Library**: HTMX - For dynamic content loading and interactions without writing JavaScript
- **Template Engine**: Jinja2 (Flask templating)
- **Architecture**: Server-side rendered with HTMX partial updates

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

### Backend Routes Structure
```python
# Main routes
/ - Dashboard
/app/<model>/<app_num> - Individual app details
/models - Models overview

# API routes (HTMX endpoints)
/api/status/<model>/<app_num> - Container status
/api/search - Search and filter
/api/cache/stats - Cache statistics

# Feature routes
/analysis/ - Security analysis
/performance/ - Performance testing
/zap/ - Security scanning
/batch/ - Batch processing
/generation/ - Content generation
/docker/ - Container management
```

## Frontend Requirements

### 1. Directory Structure
Create the following template organization:

```
src/templates/
├── base.html                    # Base template with Missing.css
├── components/                  # Reusable UI components
│   ├── navbar.html             # Navigation bar
│   ├── sidebar.html            # Sidebar navigation
│   ├── breadcrumbs.html        # Breadcrumb navigation
│   ├── app_card.html           # Application status card
│   ├── status_badge.html       # Status indicators
│   ├── modal.html              # Modal dialogs
│   ├── loading.html            # Loading indicators
│   └── search_bar.html         # Search component
├── layouts/                     # Page layouts
│   ├── main_layout.html        # Main application layout
│   └── analysis_layout.html    # Analysis-specific layout
├── pages/                       # Complete page templates
│   ├── dashboard.html          # Main dashboard
│   ├── app_details.html        # Individual app details
│   ├── models_overview.html    # Models listing
│   ├── analysis_overview.html  # Analysis dashboard
│   ├── performance_overview.html # Performance dashboard
│   ├── zap_overview.html       # ZAP scanning dashboard
│   ├── batch_overview.html     # Batch processing dashboard
│   └── generation_overview.html # Generation overview
├── partials/                    # HTMX partial templates
│   ├── dashboard_content.html  # Dashboard main content
│   ├── app_status.html         # App status partial
│   ├── search_results.html     # Search results
│   ├── analysis_results.html   # Analysis results
│   ├── docker_logs.html        # Container logs
│   ├── performance_metrics.html # Performance data
│   ├── zap_scan_progress.html  # ZAP scan progress
│   └── batch_job_status.html   # Batch job status
└── errors/                      # Error pages
    ├── 404.html
    └── 500.html
```

### 2. Static Assets Structure
```
src/static/
├── css/
│   ├── missing.min.css         # Missing.css framework (optional local copy)
│   └── custom.css              # Custom overrides and additions
├── js/
│   ├── htmx.min.js            # HTMX library (optional local copy)
│   └── app.js                 # Custom JavaScript (minimal)
└── img/
    └── logo.svg               # Application logo
```

### 3. Key UI Components Design

#### Dashboard Layout
- **Header**: Navigation with logo, search bar, and user actions
- **Sidebar**: Quick navigation to different sections (Analysis, Performance, ZAP, Batch)
- **Main Content**: Grid of application cards showing status, model, and quick actions
- **Status Bar**: Real-time statistics (running containers, active scans, etc.)

#### Application Cards
Display for each of the 900 applications:
- Model name and application type
- Container status (running/stopped/error)
- Last analysis date
- Quick action buttons (start/stop, analyze, view logs)
- Status indicators using Missing.css styling

#### Analysis Dashboard
- Filter controls for models and analysis types
- Results table with sortable columns
- Progress bars for running analyses
- Export options for results

### 4. HTMX Integration Patterns

#### Dynamic Content Loading
```html
<!-- Dashboard auto-refresh -->
<div hx-get="/api/dashboard-content" 
     hx-trigger="every 30s"
     hx-target="#dashboard-content">
</div>

<!-- Search with live results -->
<input type="search" 
       hx-get="/api/search" 
       hx-trigger="keyup changed delay:300ms"
       hx-target="#search-results">

<!-- Container actions -->
<button hx-post="/docker/start/model/1" 
        hx-target="#app-status"
        hx-swap="outerHTML">
    Start Container
</button>
```

#### Form Submissions
```html
<!-- Analysis form -->
<form hx-post="/analysis/security/model/1/run"
      hx-target="#analysis-results"
      hx-swap="innerHTML">
</form>

<!-- Batch job creation -->
<form hx-post="/batch/create"
      hx-target="#batch-status"
      hx-indicator="#loading">
</form>
```

### 5. Missing.css Usage Guidelines

#### Semantic HTML Structure
```html
<!-- Use semantic elements that Missing.css styles automatically -->
<main>
    <header>
        <nav>
            <a href="/">Dashboard</a>
            <a href="/analysis">Analysis</a>
            <a href="/performance">Performance</a>
        </nav>
    </header>
    
    <section>
        <h1>Application Dashboard</h1>
        <p>Monitor and analyze AI-generated applications</p>
    </section>
</main>
```

#### Utility Classes (when needed)
```html
<!-- Missing.css provides minimal utility classes -->
<div class="grid">           <!-- CSS Grid layout -->
<div class="flex">           <!-- Flexbox layout -->
<button class="primary">     <!-- Primary button style -->
<span class="badge">         <!-- Badge/tag styling -->
```

#### Custom CSS Variables
```css
/* Override Missing.css variables for customization */
:root {
    --accent-color: #007acc;        /* Primary brand color */
    --background-color: #ffffff;    /* Background */
    --text-color: #333333;         /* Text color */
    --border-radius: 4px;          /* Border radius */
    --spacing: 1rem;               /* Standard spacing */
}
```

### 6. Page-Specific Requirements

#### Dashboard (`/`)
- **Grid layout** of application cards (6-8 per row)
- **Real-time status updates** via HTMX polling
- **Search and filter** functionality
- **Quick stats** (total apps, running containers, recent analyses)
- **Recent activity** feed

#### App Details (`/app/<model>/<app_num>`)
- **Application metadata** (model, type, ports, creation date)
- **Container management** (start/stop/restart buttons)
- **Live logs** viewer with auto-scroll
- **Analysis results** tabs (security, performance, ZAP)
- **Port links** to access frontend/backend directly

#### Analysis Overview (`/analysis/`)
- **Analysis type tabs** (Security, Quality, Performance)
- **Filterable results table** with sorting
- **Batch analysis** creation form
- **Progress indicators** for running analyses
- **Export functionality** for results

#### Performance Dashboard (`/performance/`)
- **Performance metrics** charts and graphs
- **Load testing** configuration and execution
- **Response time** analysis
- **Resource usage** monitoring

### 7. Responsive Design

Missing.css provides automatic responsiveness, but ensure:
- **Mobile-first** approach
- **Grid layouts** that adapt to screen size
- **Navigation** that collapses on mobile
- **Touch-friendly** buttons and interactions

### 8. Accessibility Requirements

- **Semantic HTML** structure
- **ARIA labels** for dynamic content
- **Keyboard navigation** support
- **Screen reader** compatibility
- **Color contrast** compliance

### 9. Performance Considerations

- **Minimal JavaScript** (only HTMX)
- **Efficient HTMX** polling intervals
- **Lazy loading** for large data sets
- **Caching strategies** for static content
- **Optimized images** and assets

### 10. Integration Points

#### Service Helpers Integration
```python
# Templates have access to these via inject_template_vars()
{{ get_integration_service_cached() }}
{{ get_ai_models() }}
{{ get_all_apps() }}
{{ get_port_config() }}
```

#### Status Management
```python
# Use enums for consistent status display
{{ AnalysisStatus.RUNNING }}
{{ SeverityLevel.HIGH }}
{{ TaskStatus.COMPLETED }}
```

### 11. Error Handling

- **Graceful degradation** when HTMX fails
- **Error messages** in user-friendly language
- **Retry mechanisms** for failed requests
- **Loading states** for long operations

### 12. Testing Considerations

- **Cross-browser** compatibility
- **Mobile responsiveness** testing
- **HTMX functionality** validation
- **Accessibility** testing
- **Performance** benchmarking

## Implementation Notes

### Missing.css Benefits
- **Minimal footprint** (~8KB)
- **Nearly classless** - works with semantic HTML
- **Easy customization** via CSS variables
- **Good typography** out of the box
- **Responsive** by default

### HTMX Benefits
- **No complex JavaScript** framework needed
- **Server-side rendering** with dynamic updates
- **Progressive enhancement** approach
- **Small library size** (~10KB)
- **Works well** with Flask/Jinja2

### Development Workflow
1. Start with **semantic HTML** structure
2. Apply **Missing.css** for base styling
3. Add **HTMX attributes** for interactivity
4. Implement **Flask routes** returning partials
5. Test **responsiveness** and **accessibility**
6. Optimize **performance** and **loading**

This frontend should provide a clean, fast, and maintainable interface for managing and analyzing the thousands of AI-generated applications in your research project.
