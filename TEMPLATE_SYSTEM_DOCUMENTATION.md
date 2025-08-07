# Template System Documentation

## Overview

This document provides comprehensive documentation of the template system used in the AI Model Testing Framework. The system uses Jinja2 templates with Bootstrap 5 styling and HTMX integration for real-time dynamic updates.

## Template Architecture

### Directory Structure

```
src/templates/
├── base.html                     # Base layout template
├── pages/                        # Full page templates
│   ├── dashboard.html           # Main dashboard
│   ├── unified_security_testing.html  # Testing interface
│   ├── app_details.html         # Application details
│   ├── app_overview.html        # Application overview
│   ├── models_overview.html     # Models listing
│   ├── statistics_overview.html # Statistics page
│   └── error.html              # Error page
└── partials/                    # HTMX partial templates
    ├── infrastructure_status.html     # Service health display
    ├── test_jobs_list.html           # Job listing table
    ├── job_progress.html             # Progress monitoring
    ├── job_results.html              # Results display
    ├── job_logs.html                 # Log viewer
    ├── new_test_modal.html           # Test creation form
    ├── test_statistics.html          # Statistics widgets
    ├── batch_jobs_list.html          # Batch job listing
    └── testing/                      # Testing-specific partials
        └── [additional partials]
```

## Core Templates

### 1. Base Template (`base.html`)

**Purpose**: Provides the foundational layout for all pages  
**Framework**: Bootstrap 5 + HTMX integration

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Thesis Research App{% endblock %}</title>
    
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js"></script>
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/custom.css') }}">
    
    {% block head %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-flask"></i> Thesis Research App
            </a>
            <!-- Navigation items -->
        </div>
    </nav>
    
    <!-- Main Content -->
    <div class="container-fluid mt-4">
        {% block content %}{% endblock %}
    </div>
    
    <!-- Footer -->
    <footer class="bg-light mt-5 py-3">
        <div class="container text-center">
            <small class="text-muted">AI Model Testing Framework - Research Tool</small>
        </div>
    </footer>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Custom JavaScript -->
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
    
    {% block scripts %}{% endblock %}
</body>
</html>
```

**Key Features:**
- Responsive Bootstrap 5 layout
- HTMX script integration
- Navigation with active page highlighting
- Block system for extensibility
- Font Awesome icons support

### 2. Dashboard Template (`pages/dashboard.html`)

**Purpose**: Main application dashboard with overview widgets  
**Route**: `/`

```html
{% extends "base.html" %}

{% block title %}Dashboard - Thesis Research App{% endblock %}

{% block content %}
<div class="row">
    <!-- Infrastructure Status Card -->
    <div class="col-lg-6 mb-4">
        <div class="card h-100">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">
                    <i class="fas fa-server"></i> Infrastructure Status
                </h5>
                <div class="spinner-border spinner-border-sm d-none" id="infrastructure-loading"></div>
            </div>
            <div class="card-body" 
                 hx-get="/testing/api/infrastructure-status"
                 hx-trigger="every 5s"
                 hx-target="this"
                 hx-indicator="#infrastructure-loading">
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Test Statistics Card -->
    <div class="col-lg-6 mb-4">
        <div class="card h-100">
            <div class="card-header">
                <h5 class="mb-0">
                    <i class="fas fa-chart-bar"></i> Test Statistics
                </h5>
            </div>
            <div class="card-body"
                 hx-get="/testing/api/stats"
                 hx-trigger="load, every 10s"
                 hx-target="this">
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Recent Jobs Section -->
<div class="row">
    <div class="col-12">
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">
                    <i class="fas fa-tasks"></i> Recent Test Jobs
                </h5>
                <a href="/testing/" class="btn btn-primary btn-sm">
                    <i class="fas fa-plus"></i> New Test
                </a>
            </div>
            <div class="card-body"
                 hx-get="/testing/api/jobs"
                 hx-trigger="load, every 15s"
                 hx-target="this">
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**Key Features:**
- Real-time infrastructure monitoring
- Auto-refreshing statistics
- Recent jobs overview
- Quick action buttons

### 3. Testing Interface (`pages/unified_security_testing.html`)

**Purpose**: Main testing interface with job management  
**Route**: `/testing/`

```html
{% extends "base.html" %}

{% block title %}Security Testing - Thesis Research App{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1>
        <i class="fas fa-shield-alt"></i> Security Testing Interface
    </h1>
    <button class="btn btn-success" 
            hx-get="/testing/api/new-test-form"
            hx-target="#modal-content"
            data-bs-toggle="modal"
            data-bs-target="#testModal">
        <i class="fas fa-plus"></i> Create New Test
    </button>
</div>

<!-- Infrastructure Status Section -->
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">
                    <i class="fas fa-server"></i> Infrastructure Status
                </h5>
            </div>
            <div class="card-body" id="infrastructure-status"
                 hx-get="/testing/api/infrastructure-status"
                 hx-trigger="every 3s"
                 hx-target="this">
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Checking services...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Test Jobs Section -->
<div class="row">
    <div class="col-12">
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">
                    <i class="fas fa-tasks"></i> Test Jobs
                </h5>
                <div class="btn-group" role="group">
                    <button type="button" class="btn btn-outline-secondary btn-sm"
                            hx-get="/testing/api/jobs"
                            hx-target="#jobs-container">
                        <i class="fas fa-sync"></i> Refresh
                    </button>
                </div>
            </div>
            <div class="card-body p-0">
                <div id="jobs-container"
                     hx-get="/testing/api/jobs"
                     hx-trigger="load, every 5s"
                     hx-target="this">
                    <div class="text-center p-4">
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">Loading jobs...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Test Creation Modal -->
<div class="modal fade" id="testModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content" id="modal-content">
            <!-- Modal content loaded via HTMX -->
        </div>
    </div>
</div>

<!-- Job Progress Modal -->
<div class="modal fade" id="progressModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content" id="progress-modal-content">
            <!-- Progress content loaded via HTMX -->
        </div>
    </div>
</div>

<!-- Job Results Modal -->
<div class="modal fade" id="resultsModal" tabindex="-1">
    <div class="modal-dialog modal-xl">
        <div class="modal-content" id="results-modal-content">
            <!-- Results content loaded via HTMX -->
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
// Auto-refresh job list when modals close
document.addEventListener('hidden.bs.modal', function() {
    htmx.trigger('#jobs-container', 'refresh');
});

// Handle HTMX errors
document.addEventListener('htmx:responseError', function(event) {
    console.error('HTMX Error:', event.detail);
    // Show error notification
});
</script>
{% endblock %}
```

## HTMX Partial Templates

### 1. Infrastructure Status (`partials/infrastructure_status.html`)

**Purpose**: Display real-time infrastructure service status  
**Usage**: Auto-refreshed component in dashboard and testing interface

```html
<div class="row g-3">
    {% for service_name, service_info in services.items() %}
    <div class="col-md-6 col-lg-4">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-body text-center">
                <div class="mb-2">
                    {% if service_info.status == 'healthy' %}
                        <i class="fas fa-check-circle text-success fa-2x"></i>
                    {% elif service_info.status == 'unhealthy' %}
                        <i class="fas fa-times-circle text-danger fa-2x"></i>
                    {% else %}
                        <i class="fas fa-question-circle text-warning fa-2x"></i>
                    {% endif %}
                </div>
                <h6 class="card-title">{{ service_name.title().replace('-', ' ') }}</h6>
                <p class="card-text small text-muted mb-2">
                    {% if service_info.status == 'healthy' %}
                        <span class="badge bg-success">Online</span>
                    {% elif service_info.status == 'unhealthy' %}
                        <span class="badge bg-danger">Offline</span>
                    {% else %}
                        <span class="badge bg-warning">Unknown</span>
                    {% endif %}
                </p>
                {% if service_info.response_time %}
                <p class="card-text small text-muted mb-0">
                    Response: {{ service_info.response_time }}
                </p>
                {% endif %}
            </div>
        </div>
    </div>
    {% endfor %}
</div>

<!-- Overall Status Summary -->
<div class="row mt-3">
    <div class="col-12">
        <div class="alert alert-{{ 'success' if overall_status == 'healthy' else 'warning' if overall_status == 'partial' else 'danger' }} mb-0">
            <div class="d-flex align-items-center">
                <i class="fas fa-server me-2"></i>
                <strong>Infrastructure Status: </strong>
                {{ healthy_services }}/{{ total_services }} services operational
                <small class="ms-auto">Last check: {{ check_duration }}</small>
            </div>
        </div>
    </div>
</div>
```

### 2. Test Jobs List (`partials/test_jobs_list.html`)

**Purpose**: Display test jobs with action buttons  
**Usage**: Main jobs listing with management controls

```html
{% if jobs %}
<div class="table-responsive">
    <table class="table table-hover">
        <thead class="table-dark">
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Model</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Created</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for job in jobs %}
            <tr>
                <td>
                    <span class="badge bg-secondary">#{{ job.id }}</span>
                </td>
                <td>
                    <strong>{{ job.name or 'Unnamed Job' }}</strong>
                    {% if job.description %}
                    <br><small class="text-muted">{{ job.description[:50] }}...</small>
                    {% endif %}
                </td>
                <td>
                    {% if job.model_name %}
                    <span class="badge bg-info">{{ job.model_name }}</span>
                    {% else %}
                    <span class="text-muted">Multiple</span>
                    {% endif %}
                </td>
                <td>
                    {% set status_class = {
                        'pending': 'warning',
                        'running': 'primary',
                        'completed': 'success',
                        'failed': 'danger',
                        'cancelled': 'secondary'
                    } %}
                    <span class="badge bg-{{ status_class.get(job.status, 'secondary') }}">
                        {{ job.status.title() }}
                    </span>
                </td>
                <td>
                    <div class="progress" style="height: 20px;">
                        <div class="progress-bar" 
                             role="progressbar" 
                             style="width: {{ job.progress }}%"
                             aria-valuenow="{{ job.progress }}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                            {{ job.progress }}%
                        </div>
                    </div>
                </td>
                <td>
                    <small class="text-muted">
                        {{ job.created_at.strftime('%Y-%m-%d %H:%M') if job.created_at else 'Unknown' }}
                    </small>
                </td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        {% if job.status == 'pending' %}
                        <button class="btn btn-success btn-sm"
                                hx-post="/testing/api/job/{{ job.id }}/start"
                                hx-target="#job-{{ job.id }}-actions"
                                hx-indicator="#job-{{ job.id }}-loading">
                            <i class="fas fa-play"></i>
                        </button>
                        {% elif job.status == 'running' %}
                        <button class="btn btn-warning btn-sm"
                                hx-get="/testing/api/job/{{ job.id }}/progress"
                                hx-target="#progress-modal-content"
                                data-bs-toggle="modal"
                                data-bs-target="#progressModal">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-danger btn-sm"
                                hx-post="/testing/api/job/{{ job.id }}/stop"
                                hx-target="#job-{{ job.id }}-actions"
                                hx-confirm="Are you sure you want to stop this job?">
                            <i class="fas fa-stop"></i>
                        </button>
                        {% elif job.status == 'completed' %}
                        <button class="btn btn-info btn-sm"
                                hx-get="/testing/api/job/{{ job.id }}/results"
                                hx-target="#results-modal-content"
                                data-bs-toggle="modal"
                                data-bs-target="#resultsModal">
                            <i class="fas fa-chart-line"></i>
                        </button>
                        {% endif %}
                        
                        <button class="btn btn-secondary btn-sm"
                                hx-get="/testing/api/job/{{ job.id }}/logs"
                                hx-target="#results-modal-content"
                                data-bs-toggle="modal"
                                data-bs-target="#resultsModal">
                            <i class="fas fa-file-alt"></i>
                        </button>
                        
                        <div id="job-{{ job.id }}-loading" class="spinner-border spinner-border-sm d-none"></div>
                        <div id="job-{{ job.id }}-actions"></div>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% else %}
<div class="text-center py-5">
    <i class="fas fa-tasks fa-3x text-muted mb-3"></i>
    <h5 class="text-muted">No test jobs found</h5>
    <p class="text-muted">Create your first test to get started.</p>
    <button class="btn btn-primary"
            hx-get="/testing/api/new-test-form"
            hx-target="#modal-content"
            data-bs-toggle="modal"
            data-bs-target="#testModal">
        <i class="fas fa-plus"></i> Create Test Job
    </button>
</div>
{% endif %}
```

### 3. Job Progress (`partials/job_progress.html`)

**Purpose**: Real-time progress monitoring for running jobs  
**Usage**: Modal content for progress tracking

```html
<div class="modal-header">
    <h5 class="modal-title">
        <i class="fas fa-tasks"></i> Job Progress: {{ job.name or 'Job #' + job.id|string }}
    </h5>
    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
</div>

<div class="modal-body">
    <!-- Overall Progress -->
    <div class="mb-4">
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0">Overall Progress</h6>
            <span class="badge bg-{{ 'primary' if job.status == 'running' else 'success' if job.status == 'completed' else 'danger' }}">
                {{ job.status.title() }}
            </span>
        </div>
        <div class="progress mb-2" style="height: 25px;">
            <div class="progress-bar progress-bar-striped {{ 'progress-bar-animated' if job.status == 'running' else '' }}"
                 role="progressbar"
                 style="width: {{ job.progress }}%"
                 aria-valuenow="{{ job.progress }}"
                 aria-valuemin="0"
                 aria-valuemax="100">
                {{ job.progress }}%
            </div>
        </div>
        {% if job.estimated_duration and job.status == 'running' %}
        <small class="text-muted">
            <i class="fas fa-clock"></i> 
            Estimated time remaining: {{ job.estimated_duration }} minutes
        </small>
        {% endif %}
    </div>

    <!-- Task Breakdown -->
    {% if job.tasks %}
    <div class="mb-4">
        <h6>Task Breakdown</h6>
        <div class="list-group">
            {% for task in job.tasks %}
            <div class="list-group-item">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">{{ task.name }}</h6>
                    <small class="text-muted">
                        {% if task.status == 'completed' %}
                        <i class="fas fa-check text-success"></i>
                        {% elif task.status == 'running' %}
                        <i class="fas fa-spinner fa-spin text-primary"></i>
                        {% elif task.status == 'failed' %}
                        <i class="fas fa-times text-danger"></i>
                        {% else %}
                        <i class="fas fa-clock text-muted"></i>
                        {% endif %}
                        {{ task.status.title() }}
                    </small>
                </div>
                {% if task.progress > 0 %}
                <div class="progress mt-2" style="height: 15px;">
                    <div class="progress-bar" 
                         style="width: {{ task.progress }}%">
                        {{ task.progress }}%
                    </div>
                </div>
                {% endif %}
                {% if task.error_message %}
                <p class="mb-1 text-danger">
                    <small><i class="fas fa-exclamation-triangle"></i> {{ task.error_message }}</small>
                </p>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <!-- Live Logs (if available) -->
    {% if job.has_logs %}
    <div class="mb-3">
        <h6>Recent Activity</h6>
        <div class="bg-dark text-light p-3 rounded" style="height: 200px; overflow-y: auto; font-family: monospace; font-size: 0.875rem;">
            <div hx-get="/testing/api/job/{{ job.id }}/logs?tail=20"
                 hx-trigger="load, every 2s"
                 hx-target="this">
                Loading logs...
            </div>
        </div>
    </div>
    {% endif %}
</div>

<div class="modal-footer">
    {% if job.status == 'running' %}
    <button type="button" class="btn btn-danger"
            hx-post="/testing/api/job/{{ job.id }}/stop"
            hx-confirm="Are you sure you want to stop this job?"
            hx-target="#job-actions">
        <i class="fas fa-stop"></i> Stop Job
    </button>
    {% endif %}
    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
    <div id="job-actions"></div>
</div>

<!-- Auto-refresh if job is running -->
{% if job.status == 'running' %}
<script>
setTimeout(function() {
    htmx.trigger(document.querySelector('#progress-modal-content'), 'refresh');
}, 3000);
</script>
{% endif %}
```

### 4. Job Results (`partials/job_results.html`)

**Purpose**: Display detailed test results with metrics  
**Usage**: Modal content for completed job results

```html
<div class="modal-header">
    <h5 class="modal-title">
        <i class="fas fa-chart-line"></i> Test Results: {{ job.name or 'Job #' + job.id|string }}
    </h5>
    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
</div>

<div class="modal-body">
    <!-- Results Summary -->
    <div class="row mb-4">
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card bg-primary text-white text-center">
                <div class="card-body">
                    <h3>{{ job.total_tests or 0 }}</h3>
                    <small>Total Tests</small>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card bg-success text-white text-center">
                <div class="card-body">
                    <h3>{{ job.completed_tests or 0 }}</h3>
                    <small>Completed</small>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card bg-danger text-white text-center">
                <div class="card-body">
                    <h3>{{ job.failed_tests or 0 }}</h3>
                    <small>Failed</small>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card bg-info text-white text-center">
                <div class="card-body">
                    <h3>{{ job.execution_duration|round(2) if job.execution_duration else 'N/A' }}</h3>
                    <small>Duration (min)</small>
                </div>
            </div>
        </div>
    </div>

    <!-- Detailed Results -->
    {% if job.results %}
    <div class="accordion" id="resultsAccordion">
        {% for test_type, test_results in job.results.items() %}
        <div class="accordion-item">
            <h2 class="accordion-header" id="heading{{ loop.index }}">
                <button class="accordion-button {{ 'collapsed' if not loop.first else '' }}" 
                        type="button" 
                        data-bs-toggle="collapse" 
                        data-bs-target="#collapse{{ loop.index }}">
                    <i class="fas fa-{{ 'shield-alt' if test_type == 'security' else 'tachometer-alt' if test_type == 'performance' else 'bug' }}"></i>
                    &nbsp;{{ test_type.title() }} Results
                    {% if test_results.summary %}
                    <span class="badge bg-secondary ms-2">
                        {{ test_results.summary.get('issues_found', 0) }} issues
                    </span>
                    {% endif %}
                </button>
            </h2>
            <div id="collapse{{ loop.index }}" 
                 class="accordion-collapse collapse {{ 'show' if loop.first else '' }}"
                 data-bs-parent="#resultsAccordion">
                <div class="accordion-body">
                    {% if test_type == 'security' %}
                        {% include 'partials/security_results.html' %}
                    {% elif test_type == 'performance' %}
                        {% include 'partials/performance_results.html' %}
                    {% endif %}
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-4">
        <i class="fas fa-chart-line fa-3x text-muted mb-3"></i>
        <h5 class="text-muted">No results available</h5>
        <p class="text-muted">This job hasn't produced any results yet.</p>
    </div>
    {% endif %}

    <!-- Download Artifacts -->
    {% if job.artifacts %}
    <div class="mt-4">
        <h6>Download Reports</h6>
        <div class="list-group">
            {% for artifact in job.artifacts %}
            <a href="{{ artifact.download_url }}" 
               class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                <div>
                    <i class="fas fa-file-{{ 'code' if artifact.type == 'json' else 'alt' }}"></i>
                    {{ artifact.name }}
                    <small class="text-muted d-block">{{ artifact.type }}</small>
                </div>
                <span class="badge bg-primary rounded-pill">
                    {{ (artifact.size / 1024)|round(1) }} KB
                </span>
            </a>
            {% endfor %}
        </div>
    </div>
    {% endif %}
</div>

<div class="modal-footer">
    {% if job.artifacts %}
    <button type="button" class="btn btn-primary"
            hx-get="/testing/api/job/{{ job.id }}/export?format=csv"
            hx-target="_blank">
        <i class="fas fa-download"></i> Export CSV
    </button>
    {% endif %}
    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
</div>
```

### 5. New Test Modal (`partials/new_test_modal.html`)

**Purpose**: Form for creating new test jobs  
**Usage**: Modal content for test creation

```html
<div class="modal-header">
    <h5 class="modal-title">
        <i class="fas fa-plus"></i> Create New Test Job
    </h5>
    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
</div>

<form hx-post="/testing/api/create-test" 
      hx-target="#test-creation-result"
      hx-indicator="#test-creation-loading">
    <div class="modal-body">
        <!-- Job Configuration -->
        <div class="mb-3">
            <label for="jobName" class="form-label">Job Name</label>
            <input type="text" 
                   class="form-control" 
                   id="jobName" 
                   name="name" 
                   placeholder="e.g., Security Analysis - Claude 3.7"
                   required>
        </div>

        <div class="mb-3">
            <label for="jobDescription" class="form-label">Description (Optional)</label>
            <textarea class="form-control" 
                      id="jobDescription" 
                      name="description" 
                      rows="2"
                      placeholder="Brief description of the test purpose"></textarea>
        </div>

        <!-- Model Selection -->
        <div class="mb-3">
            <label for="modelSelect" class="form-label">AI Model</label>
            <select class="form-select" 
                    id="modelSelect" 
                    name="model" 
                    required
                    hx-get="/testing/api/app-details"
                    hx-target="#app-selection"
                    hx-trigger="change">
                <option value="">Select a model...</option>
                {% for model in models %}
                <option value="{{ model.slug }}">
                    {{ model.display_name }} ({{ model.provider }})
                </option>
                {% endfor %}
            </select>
        </div>

        <!-- App Selection -->
        <div id="app-selection" class="mb-3">
            <label class="form-label">Application Number</label>
            <select class="form-select" name="app_number" disabled>
                <option value="">Select a model first...</option>
            </select>
        </div>

        <!-- Test Types -->
        <div class="mb-3">
            <label class="form-label">Test Types</label>
            <div class="form-check">
                <input class="form-check-input" 
                       type="checkbox" 
                       id="securityTest" 
                       name="test_types" 
                       value="security" 
                       checked>
                <label class="form-check-label" for="securityTest">
                    <i class="fas fa-shield-alt"></i> Security Analysis
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" 
                       type="checkbox" 
                       id="performanceTest" 
                       name="test_types" 
                       value="performance">
                <label class="form-check-label" for="performanceTest">
                    <i class="fas fa-tachometer-alt"></i> Performance Testing
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" 
                       type="checkbox" 
                       id="zapTest" 
                       name="test_types" 
                       value="zap">
                <label class="form-check-label" for="zapTest">
                    <i class="fas fa-bug"></i> ZAP Security Scan
                </label>
            </div>
        </div>

        <!-- Security Tools -->
        <div id="security-tools" class="mb-3">
            <label class="form-label">Security Tools</label>
            <div class="row">
                <div class="col-md-6">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="bandit" name="tools.security" value="bandit" checked>
                        <label class="form-check-label" for="bandit">Bandit (Python)</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="safety" name="tools.security" value="safety" checked>
                        <label class="form-check-label" for="safety">Safety (Dependencies)</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="pylint" name="tools.security" value="pylint">
                        <label class="form-check-label" for="pylint">PyLint (Code Quality)</label>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="eslint" name="tools.security" value="eslint">
                        <label class="form-check-label" for="eslint">ESLint (JavaScript)</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="npm-audit" name="tools.security" value="npm-audit">
                        <label class="form-check-label" for="npm-audit">npm audit</label>
                    </div>
                </div>
            </div>
        </div>

        <!-- Advanced Configuration -->
        <div class="accordion" id="advancedConfig">
            <div class="accordion-item">
                <h2 class="accordion-header">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAdvanced">
                        Advanced Configuration
                    </button>
                </h2>
                <div id="collapseAdvanced" class="accordion-collapse collapse" data-bs-parent="#advancedConfig">
                    <div class="accordion-body">
                        <div class="mb-3">
                            <label for="priority" class="form-label">Priority</label>
                            <select class="form-select" name="priority">
                                <option value="normal" selected>Normal</option>
                                <option value="high">High</option>
                                <option value="low">Low</option>
                            </select>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="notifyCompletion" name="notify_on_completion">
                            <label class="form-check-label" for="notifyCompletion">
                                Notify on completion
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Result Container -->
        <div id="test-creation-result" class="mt-3"></div>
    </div>

    <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="submit" class="btn btn-primary">
            <span id="test-creation-loading" class="spinner-border spinner-border-sm d-none me-2"></span>
            <i class="fas fa-play"></i> Create & Start Test
        </button>
    </div>
</form>

<script>
// Show/hide tool sections based on test type selection
document.addEventListener('change', function(event) {
    if (event.target.name === 'test_types') {
        const securityTools = document.getElementById('security-tools');
        const securityChecked = document.getElementById('securityTest').checked;
        securityTools.style.display = securityChecked ? 'block' : 'none';
    }
});
</script>
```

## Template Patterns and Best Practices

### 1. HTMX Integration Patterns

#### Auto-Refresh Components
```html
<!-- Component that refreshes every 5 seconds -->
<div hx-get="/api/status" 
     hx-trigger="every 5s" 
     hx-target="this">
    Initial content...
</div>
```

#### Modal Loading
```html
<!-- Button that loads modal content -->
<button hx-get="/api/modal-content"
        hx-target="#modal-content"
        data-bs-toggle="modal"
        data-bs-target="#myModal">
    Open Modal
</button>
```

#### Form Submission with Feedback
```html
<form hx-post="/api/submit"
      hx-target="#result"
      hx-indicator="#loading">
    <!-- Form fields -->
    <button type="submit">
        <span id="loading" class="spinner-border spinner-border-sm d-none"></span>
        Submit
    </button>
</form>
<div id="result"></div>
```

### 2. Bootstrap Components

#### Status Badges
```html
{% set status_class = {
    'pending': 'warning',
    'running': 'primary', 
    'completed': 'success',
    'failed': 'danger'
} %}
<span class="badge bg-{{ status_class.get(status, 'secondary') }}">
    {{ status.title() }}
</span>
```

#### Progress Bars
```html
<div class="progress">
    <div class="progress-bar {{ 'progress-bar-animated progress-bar-striped' if animated else '' }}"
         role="progressbar"
         style="width: {{ progress }}%">
        {{ progress }}%
    </div>
</div>
```

#### Cards with Actions
```html
<div class="card">
    <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0">Card Title</h5>
        <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-primary">Action</button>
        </div>
    </div>
    <div class="card-body">
        Card content...
    </div>
</div>
```

### 3. Error Handling Templates

#### Generic Error Template (`partials/error_message.html`)
```html
<div class="alert alert-{{ error_type or 'danger' }} alert-dismissible fade show">
    <i class="fas fa-exclamation-triangle"></i>
    <strong>{{ error_title or 'Error' }}:</strong> {{ error_message }}
    {% if error_details %}
    <hr>
    <small>{{ error_details }}</small>
    {% endif %}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
```

#### Loading States
```html
<!-- Loading placeholder -->
<div class="text-center p-4">
    <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
    </div>
    <p class="mt-2 text-muted">{{ loading_message or 'Loading...' }}</p>
</div>
```

### 4. Responsive Design Patterns

#### Mobile-First Tables
```html
<div class="table-responsive">
    <table class="table table-hover">
        <thead class="d-none d-md-table-header-group">
            <!-- Desktop headers -->
        </thead>
        <tbody>
            {% for item in items %}
            <tr class="d-block d-md-table-row">
                <td class="d-block d-md-table-cell">
                    <!-- Mobile: stacked layout -->
                    <div class="d-md-none">
                        <strong>{{ item.title }}</strong><br>
                        <small class="text-muted">{{ item.subtitle }}</small>
                    </div>
                    <!-- Desktop: normal cell -->
                    <span class="d-none d-md-inline">{{ item.title }}</span>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

#### Responsive Cards
```html
<div class="row g-3">
    {% for item in items %}
    <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
        <div class="card h-100">
            <!-- Card content -->
        </div>
    </div>
    {% endfor %}
</div>
```

## Custom CSS and JavaScript

### Custom Styles (`src/static/css/custom.css`)
```css
/* Custom status indicators */
.status-healthy { color: #28a745; }
.status-unhealthy { color: #dc3545; }
.status-unknown { color: #ffc107; }

/* Progress bar animations */
.progress-bar-pulse {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}

/* HTMX loading states */
.htmx-indicator {
    opacity: 0;
    transition: opacity 200ms ease-in;
}
.htmx-request .htmx-indicator {
    opacity: 1;
}
.htmx-request.htmx-indicator {
    opacity: 1;
}

/* Modal improvements */
.modal-xl {
    max-width: 95%;
}

/* Table hover effects */
.table-hover tbody tr:hover {
    background-color: rgba(0, 123, 255, 0.05);
}
```

### JavaScript Utilities (`src/static/js/app.js`)
```javascript
// HTMX event handlers
document.addEventListener('htmx:responseError', function(event) {
    console.error('HTMX Error:', event.detail);
    showNotification('Request failed. Please try again.', 'error');
});

document.addEventListener('htmx:timeout', function(event) {
    showNotification('Request timed out. Please check your connection.', 'warning');
});

// Notification system
function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    document.querySelector('.toast-container').appendChild(toast);
    new bootstrap.Toast(toast).show();
}

// Auto-refresh controls
function toggleAutoRefresh(element) {
    const isEnabled = element.dataset.autoRefresh === 'true';
    element.dataset.autoRefresh = !isEnabled;
    element.textContent = isEnabled ? 'Enable Auto-refresh' : 'Disable Auto-refresh';
    
    if (!isEnabled) {
        element.setAttribute('hx-trigger', 'every 5s');
    } else {
        element.removeAttribute('hx-trigger');
    }
    htmx.process(element);
}
```

This template system provides a comprehensive, responsive, and interactive user interface for the AI Model Testing Framework with proper separation between structure, styling, and behavior.
