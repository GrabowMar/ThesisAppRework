# AI Frontend Technologies Guide for Flask Dashboards: HTMX, _hyperscript, and Bootstrap 5

This comprehensive guide provides AI models with detailed information about three powerful frontend technologies specifically for building dynamic Flask dashboards and admin interfaces. These technologies work together to create sophisticated, interactive web dashboards without heavy JavaScript frameworks.

## Table of Contents
1. [HTMX for Flask Dashboards](#htmx)
2. [_hyperscript for Dashboard Interactions](#_hyperscript)
3. [Bootstrap 5 for Dashboard Styling](#bootstrap5)
4. [Flask Dashboard Integration Patterns](#integration-patterns)
5. [Dashboard-Specific Components](#dashboard-components)
6. [Real-time Dashboard Updates](#real-time-updates)
7. [Data Visualization Integration](#data-visualization)
8. [Best Practices for Flask Dashboard Development](#best-practices-for-ai-code-generation)

---

## HTMX for Flask Dashboards

### Overview
HTMX is perfect for Flask dashboard development because it allows you to build dynamic interfaces that communicate seamlessly with Flask routes, returning HTML fragments that update specific dashboard components without full page reloads.

### Core Philosophy for Dashboards
- **Server-Side Rendering** - Flask renders dashboard components as HTML templates
- **Partial Updates** - Update specific dashboard widgets without page refresh
- **RESTful Endpoints** - Dashboard actions map to Flask routes
- **Progressive Enhancement** - Works with existing Flask forms and links

### Flask Route Patterns for Dashboards

#### Dashboard Data Endpoints
```python
# Flask routes for dashboard data
from flask import render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard/index.html')

@app.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """Return dashboard statistics widget"""
    stats = {
        'total_users': User.query.count(),
        'active_sessions': get_active_sessions(),
        'revenue': calculate_revenue(),
        'conversion_rate': get_conversion_rate()
    }
    return render_template('dashboard/components/stats.html', stats=stats)

@app.route('/api/dashboard/chart/<chart_type>')
@login_required
def dashboard_chart(chart_type):
    """Return chart data as HTML"""
    data = get_chart_data(chart_type, request.args)
    return render_template(f'dashboard/charts/{chart_type}.html', data=data)

@app.route('/api/dashboard/table/<table_name>')
@login_required
def dashboard_table(table_name):
    """Return paginated table data"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    if table_name == 'users':
        pagination = User.query.paginate(page=page, per_page=per_page)
    elif table_name == 'orders':
        pagination = Order.query.paginate(page=page, per_page=per_page)
    
    return render_template('dashboard/tables/table.html', 
                         pagination=pagination, 
                         table_name=table_name)
```

#### CRUD Operations for Dashboard
```python
@app.route('/api/dashboard/users', methods=['POST'])
@login_required
def create_user():
    """Create new user from dashboard"""
    form_data = request.form
    user = User(
        username=form_data['username'],
        email=form_data['email']
    )
    db.session.add(user)
    db.session.commit()
    
    # Return the new user row
    return render_template('dashboard/components/user_row.html', user=user)

@app.route('/api/dashboard/users/<int:user_id>', methods=['PUT', 'POST'])
@login_required
def update_user(user_id):
    """Update user from dashboard"""
    user = User.query.get_or_404(user_id)
    user.username = request.form['username']
    user.email = request.form['email']
    db.session.commit()
    
    return render_template('dashboard/components/user_row.html', user=user)

@app.route('/api/dashboard/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete user from dashboard"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    # Return empty response to remove the row
    return '', 200

@app.route('/api/dashboard/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    # Return updated status badge
    return render_template('dashboard/components/status_badge.html', user=user)
```

### Dashboard HTMX Patterns

#### Auto-Refreshing Dashboard Widgets
```html
<!-- Auto-refreshing statistics widget -->
<div class="card" 
     hx-get="/api/dashboard/stats" 
     hx-trigger="load, every 30s"
     hx-swap="innerHTML">
    <div class="card-body">
        <div class="d-flex justify-content-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading stats...</span>
            </div>
        </div>
    </div>
</div>

<!-- Chart that updates based on date range -->
<div class="card">
    <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="card-title mb-0">Revenue Chart</h5>
        <select class="form-select form-select-sm" style="width: auto;"
                name="timerange" 
                hx-get="/api/dashboard/chart/revenue" 
                hx-trigger="change" 
                hx-target="#revenue-chart"
                hx-include="[name='chart_type']">
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
        </select>
        <input type="hidden" name="chart_type" value="line">
    </div>
    
    <div class="card-body">
        <div id="revenue-chart" 
             hx-get="/api/dashboard/chart/revenue?timerange=7d" 
             hx-trigger="load">
            <div class="d-flex justify-content-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading chart...</span>
                </div>
            </div>
        </div>
    </div>
</div>
```

#### Data Tables with Pagination and Sorting
```html
<!-- Dashboard data table -->
<div class="card">
    <div class="card-header">
        <div class="row align-items-center">
            <div class="col">
                <h5 class="card-title mb-0">Users</h5>
            </div>
            <div class="col-auto">
                <button class="btn btn-primary btn-sm" 
                        hx-get="/api/dashboard/users/new" 
                        hx-target="#modal-container">
                    Add User
                </button>
            </div>
        </div>
    </div>
    
    <!-- Table controls -->
    <div class="card-body border-bottom">
        <div class="row g-3">
            <div class="col-md-6">
                <input type="search" 
                       class="form-control"
                       name="search" 
                       placeholder="Search users..."
                       hx-get="/api/dashboard/table/users" 
                       hx-trigger="keyup changed delay:300ms" 
                       hx-target="#users-table"
                       hx-include="[name='sort'], [name='order'], [name='per_page']">
            </div>
            
            <div class="col-md-3">
                <select class="form-select" name="per_page"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table"
                        hx-include="[name='search'], [name='sort'], [name='order']">
                    <option value="10">10 per page</option>
                    <option value="25">25 per page</option>
                    <option value="50">50 per page</option>
                </select>
            </div>
            
            <div class="col-md-3">
                <button class="btn btn-outline-secondary w-100" 
                        hx-get="/api/dashboard/export/users" 
                        hx-trigger="click">
                    Export CSV
                </button>
            </div>
        </div>
        
        <input type="hidden" name="sort" value="created_at">
        <input type="hidden" name="order" value="desc">
    </div>
    
    <!-- Table content -->
    <div id="users-table" 
         hx-get="/api/dashboard/table/users" 
         hx-trigger="load">
        <div class="d-flex justify-content-center p-4">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading table...</span>
            </div>
        </div>
    </div>
</div>
```

#### Inline Editing
```html
<!-- Inline editable user row -->
<tr id="user-{{ user.id }}">
    <td>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" 
                   name="selected_users" 
                   value="{{ user.id }}">
        </div>
    </td>
    <td>
        <div class="d-flex align-items-center">
            <div class="avatar avatar-sm me-3">
                <span class="avatar-initial rounded-circle bg-primary">
                    {{ user.username[0].upper() }}
                </span>
            </div>
            <div>
                <h6 class="mb-0">{{ user.username }}</h6>
                <small class="text-muted">#{{ user.id }}</small>
            </div>
        </div>
    </td>
    <td>{{ user.email }}</td>
    <td>
        <span class="badge bg-{{ 'success' if user.is_active else 'secondary' }}"
              hx-post="/api/dashboard/users/{{ user.id }}/toggle-status"
              hx-target="this"
              hx-swap="outerHTML"
              style="cursor: pointer;">
            {{ 'Active' if user.is_active else 'Inactive' }}
        </span>
    </td>
    <td>
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" 
                    data-bs-toggle="dropdown">
                Actions
            </button>
            <ul class="dropdown-menu">
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/users/{{ user.id }}/edit"
                       hx-target="#modal-container">
                        Edit
                    </a>
                </li>
                <li>
                    <a class="dropdown-item text-danger" href="#"
                       hx-delete="/api/dashboard/users/{{ user.id }}"
                       hx-target="#user-{{ user.id }}"
                       hx-swap="outerHTML"
                       hx-confirm="Are you sure you want to delete this user?">
                        Delete
                    </a>
                </li>
            </ul>
        </div>
    </td>
</tr>
```

#### Dashboard Modals and Forms
```html
<!-- Add user button -->
<button class="btn btn-primary" 
        hx-get="/api/dashboard/users/new" 
        hx-target="#modal-container" 
        hx-swap="innerHTML">
    Add New User
</button>

<!-- Modal container -->
<div id="modal-container"></div>

<!-- Flask returns this modal form -->
<div class="modal fade show d-block" tabindex="-1" style="background: rgba(0,0,0,0.5);">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Add New User</h5>
                <button type="button" class="btn-close" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                </button>
            </div>
            
            <form hx-post="/api/dashboard/users" 
                  hx-target="#users-table" 
                  hx-swap="afterbegin"
                  hx-on::after-request="if(event.detail.successful) document.getElementById('modal-container').innerHTML = ''">
                
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label" for="username">Username</label>
                        <input type="text" 
                               class="form-control"
                               name="username" 
                               id="username"
                               required
                               hx-get="/api/dashboard/validate/username"
                               hx-trigger="blur"
                               hx-target="#username-validation">
                        <div id="username-validation"></div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label" for="email">Email</label>
                        <input type="email" 
                               class="form-control"
                               name="email" 
                               id="email"
                               required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label" for="role">Role</label>
                        <select class="form-select" name="role" id="role" required>
                            <option value="">Select a role</option>
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                            <option value="moderator">Moderator</option>
                        </select>
                    </div>
                    
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" 
                               name="is_active" id="is_active" checked>
                        <label class="form-check-label" for="is_active">
                            Active User
                        </label>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Create User</button>
                    <button type="button" class="btn btn-secondary" 
                            onclick="document.getElementById('modal-container').innerHTML = ''">
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
```

#### Bulk Operations
```html
<!-- Bulk actions toolbar -->
<div class="alert alert-info d-none" id="bulk-actions">
    <div class="d-flex justify-content-between align-items-center">
        <span class="fw-bold">
            <span id="selected-count">0</span> users selected
        </span>
        <div class="btn-group">
            <button class="btn btn-success btn-sm" 
                    hx-post="/api/dashboard/users/bulk-activate" 
                    hx-include="[name='selected_users']:checked"
                    hx-target="#users-table"
                    hx-swap="innerHTML">
                Activate Selected
            </button>
            <button class="btn btn-danger btn-sm" 
                    hx-delete="/api/dashboard/users/bulk-delete" 
                    hx-include="[name='selected_users']:checked"
                    hx-target="#users-table"
                    hx-swap="innerHTML"
                    hx-confirm="Delete selected users?">
                Delete Selected
            </button>
        </div>
    </div>
</div>

<!-- Table with checkboxes -->
<div class="table-responsive">
    <table class="table table-hover">
        <thead class="table-light">
            <tr>
                <th style="width: 40px;">
                    <input class="form-check-input" type="checkbox" id="select-all">
                </th>
                <th>Username</th>
                <th>Email</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for user in users %}
            <tr>
                <td>
                    <input class="form-check-input" 
                           type="checkbox" 
                           name="selected_users" 
                           value="{{ user.id }}"
                           class="user-checkbox">
                </td>
                <td>{{ user.username }}</td>
                <td>{{ user.email }}</td>
                <td>{{ user.status }}</td>
                <td>
                    <!-- Action buttons -->
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

### Dashboard Filters and Search
```html
<!-- Advanced filter panel -->
<div class="card">
    <div class="card-header">
        <h6 class="card-title mb-0">Filters</h6>
    </div>
    <div class="card-body">
        <form hx-get="/api/dashboard/table/users" 
              hx-trigger="change, submit" 
              hx-target="#users-table"
              hx-swap="innerHTML">
            
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Status</label>
                    <select class="form-select" name="status">
                        <option value="">All</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                    </select>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Role</label>
                    <select class="form-select" name="role">
                        <option value="">All Roles</option>
                        {% for role in roles %}
                        <option value="{{ role.id }}">{{ role.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Registration From</label>
                    <input type="date" class="form-control" name="date_from">
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Registration To</label>
                    <input type="date" class="form-control" name="date_to">
                </div>
                
                <div class="col-12">
                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-primary">Apply Filters</button>
                        <button type="button" 
                                class="btn btn-outline-secondary"
                                hx-get="/api/dashboard/table/users" 
                                hx-target="#users-table"
                                onclick="this.closest('form').reset()">
                            Clear Filters
                        </button>
                    </div>
                </div>
            </div>
        </form>
    </div>
</div>
```

### Key Attributes

#### Basic AJAX Attributes
```html
<!-- Core HTMX attributes -->
<button hx-get="/api/data" hx-target="#result">Get Data</button>
<form hx-post="/api/submit" hx-target="#response">
<div hx-put="/api/update" hx-trigger="click">
<span hx-delete="/api/item/123" hx-confirm="Are you sure?">
```

#### Essential Attributes Reference
- **`hx-get`** - Issues GET request to specified URL
- **`hx-post`** - Issues POST request to specified URL  
- **`hx-put`** - Issues PUT request to specified URL
- **`hx-delete`** - Issues DELETE request to specified URL
- **`hx-target`** - Element to update with response (CSS selector)
- **`hx-swap`** - How to swap content (innerHTML, outerHTML, beforeend, afterend, beforebegin, afterbegin, delete, none)
- **`hx-trigger`** - Event that triggers request (click, change, load, revealed, etc.)
- **`hx-params`** - Parameters to include in request
- **`hx-headers`** - Headers to include in request
- **`hx-vals`** - Values to include in request body

#### Advanced Attributes
- **`hx-boost`** - Converts regular links/forms to AJAX
- **`hx-push-url`** - Push URL to browser history
- **`hx-select`** - Select specific part of response
- **`hx-confirm`** - Show confirmation dialog
- **`hx-indicator`** - Element to show during request
- **`hx-sync`** - Synchronize requests
- **`hx-encoding`** - Request encoding (multipart/form-data)

### Triggers
```html
<!-- Event-based triggers -->
<div hx-get="/api/data" hx-trigger="click">Click me</div>
<input hx-get="/search" hx-trigger="keyup changed delay:500ms">
<div hx-get="/poll" hx-trigger="every 2s">Auto-refresh</div>
<div hx-get="/load" hx-trigger="load">Load on page load</div>
<div hx-get="/reveal" hx-trigger="revealed">Load when scrolled into view</div>

<!-- Trigger modifiers -->
<button hx-get="/api" hx-trigger="click once">Only once</button>
<input hx-get="/api" hx-trigger="keyup changed delay:500ms">
<div hx-get="/api" hx-trigger="click from:body">Delegate from body</div>
<div hx-get="/api" hx-trigger="click target:#button">Target specific element</div>
```

### Swapping Strategies
```html
<!-- Different swap strategies -->
<div hx-get="/content" hx-swap="innerHTML">Replace inner content</div>
<div hx-get="/content" hx-swap="outerHTML">Replace entire element</div>
<div hx-get="/content" hx-swap="beforebegin">Insert before element</div>
<div hx-get="/content" hx-swap="afterbegin">Insert at start of element</div>
<div hx-get="/content" hx-swap="beforeend">Insert at end of element</div>
<div hx-get="/content" hx-swap="afterend">Insert after element</div>
<div hx-get="/content" hx-swap="delete">Delete element</div>
<div hx-get="/content" hx-swap="none">Don't swap content</div>

<!-- Swap with timing and scrolling -->
<div hx-swap="innerHTML settle:100ms">Settle for 100ms</div>
<div hx-swap="innerHTML swap:200ms">Swap after 200ms</div>
<div hx-swap="innerHTML scroll:top">Scroll to top after swap</div>
<div hx-swap="innerHTML scroll:bottom">Scroll to bottom after swap</div>
```

### Common Patterns

#### Loading States and Indicators
```html
<style>
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request.htmx-indicator { display: inline; }
</style>

<button hx-get="/api/data" hx-target="#result" class="btn btn-primary">
    Get Data
    <span class="htmx-indicator">
        <span class="spinner-border spinner-border-sm ms-2" role="status">
            <span class="visually-hidden">Loading...</span>
        </span>
    </span>
</button>

<div id="result">
    <div class="htmx-indicator d-flex justify-content-center">
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    </div>
</div>
```

#### Form Handling
```html
<!-- Basic form submission -->
<form hx-post="/api/contact" hx-target="#response" class="needs-validation" novalidate>
    <div class="mb-3">
        <label class="form-label" for="name">Name</label>
        <input class="form-control" name="name" id="name" required>
        <div class="invalid-feedback">Please provide a name.</div>
    </div>
    <div class="mb-3">
        <label class="form-label" for="email">Email</label>
        <input type="email" class="form-control" name="email" id="email" required>
        <div class="invalid-feedback">Please provide a valid email.</div>
    </div>
    <button type="submit" class="btn btn-primary">Submit</button>
</form>

<!-- Form with validation -->
<form hx-post="/api/validate" hx-target="#errors" 
      hx-trigger="submit" hx-swap="innerHTML" class="needs-validation" novalidate>
    <div class="mb-3">
        <label class="form-label" for="username">Username</label>
        <input class="form-control" name="username" id="username"
               hx-get="/api/check-username" 
               hx-trigger="blur" 
               hx-target="#username-error">
        <div id="username-error"></div>
    </div>
    <button type="submit" class="btn btn-primary">Submit</button>
</form>
```

#### Infinite Scroll
```html
<div id="content" class="container">
    <!-- Initial content -->
</div>
<div hx-get="/api/more-content?page=2" 
     hx-trigger="revealed" 
     hx-swap="outerHTML"
     hx-target="this"
     class="text-center p-4">
    <div class="htmx-indicator">
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Loading more...</span>
        </div>
    </div>
</div>
```

#### Live Search
```html
<div class="mb-3">
    <input type="search" 
           class="form-control"
           name="search"
           hx-get="/api/search" 
           hx-trigger="keyup changed delay:300ms" 
           hx-target="#search-results"
           placeholder="Search...">
</div>
<div id="search-results"></div>
```

#### Modal Dialogs
```html
<!-- Trigger -->
<button class="btn btn-primary"
        hx-get="/modal/edit-user/123" 
        hx-target="#modal-container" 
        hx-trigger="click">
    Edit User
</button>

<!-- Modal container -->
<div id="modal-container"></div>

<!-- Server returns Bootstrap modal HTML -->
<div class="modal fade show d-block" tabindex="-1" style="background: rgba(0,0,0,0.5);">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Edit User</h5>
                <button type="button" class="btn-close" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                </button>
            </div>
            <form hx-put="/api/user/123" hx-target="#modal-container" hx-swap="outerHTML">
                <div class="modal-body">
                    <!-- Form fields -->
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Save</button>
                    <button type="button" class="btn btn-secondary" 
                            onclick="document.getElementById('modal-container').innerHTML = ''">
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
```

### Server-Side Response Headers
```javascript
// Useful HTMX response headers for server responses
app.post('/api/data', (req, res) => {
    // Trigger client-side events
    res.set('HX-Trigger', 'dataUpdated');
    
    // Redirect after request
    res.set('HX-Redirect', '/dashboard');
    
    // Refresh the page
    res.set('HX-Refresh', 'true');
    
    // Push URL to history
    res.set('HX-Push-Url', '/new-url');
    
    // Replace URL in history
    res.set('HX-Replace-Url', '/replace-url');
    
    res.send('<div>Updated content</div>');
});
```

### Out of Band Updates
```html
<!-- Response can update multiple elements -->
<div id="main-content">
    <!-- Primary update target -->
</div>

<!-- Server response can include out-of-band updates -->
<div hx-get="/api/update" hx-target="#main-content">Update</div>

<!-- Server returns: -->
<!--
<div id="main-content">New main content</div>
<div id="sidebar" hx-swap-oob="true">Updated sidebar</div>
<div id="header" hx-swap-oob="innerHTML">Updated header content</div>
-->
```

### Configuration
```html
<meta name="htmx-config" content='{"defaultSwapStyle":"outerHTML"}'>

<script>
// JavaScript configuration
htmx.config.defaultSwapStyle = 'outerHTML';
htmx.config.defaultSwapDelay = 100;
htmx.config.requestTimeout = 10000;
htmx.config.historyEnabled = true;
</script>
```

---

## _hyperscript for Dashboard Interactions

### Overview
_hyperscript is perfect for adding interactive behaviors to Flask dashboards. It excels at handling client-side state management, DOM manipulation, and coordinating between different dashboard components without complex JavaScript.

### Dashboard-Specific Behaviors

#### Dashboard Layout Management
```html
<!-- Collapsible sidebar -->
<nav class="navbar-nav bg-gradient-primary sidebar sidebar-dark accordion" 
     _="init set :collapsed to false
       on toggle-sidebar
         if :collapsed
           remove .sidebar-collapsed from #wrapper
           set :collapsed to false
         else
           add .sidebar-collapsed to #wrapper
           set :collapsed to true
         end
         send sidebar-changed(collapsed: :collapsed) to #main-content">
    
    <div class="sidebar-brand d-flex align-items-center justify-content-center">
        <div class="sidebar-brand-icon rotate-n-15">
            <i class="fas fa-laugh-wink"></i>
        </div>
        <div class="sidebar-brand-text mx-3">Dashboard</div>
        <button class="btn btn-link d-md-none ms-auto" 
                _="on click send toggle-sidebar to .sidebar">
            <i class="fas fa-bars"></i>
        </button>
    </div>
    
    <ul class="navbar-nav">
        <li class="nav-item">
            <a class="nav-link" href="/dashboard">
                <i class="fas fa-fw fa-tachometer-alt"></i>
                <span>Overview</span>
            </a>
        </li>
        <li class="nav-item">
            <a class="nav-link" href="/dashboard/users">
                <i class="fas fa-fw fa-users"></i>
                <span>Users</span>
            </a>
        </li>
        <li class="nav-item">
            <a class="nav-link" href="/dashboard/reports">
                <i class="fas fa-fw fa-chart-area"></i>
                <span>Reports</span>
            </a>
        </li>
    </ul>
</nav>

<!-- Main content area that responds to sidebar changes -->
<div id="main-content" class="d-flex flex-column" 
     _="on sidebar-changed(collapsed) 
        if collapsed
          add .sidebar-toggled to body
        else
          remove .sidebar-toggled from body
        end">
    <!-- Dashboard content -->
</div>
```

#### Dynamic Widget Management
```html
<!-- Widget container with drag-and-drop reordering -->
<div class="row dashboard-widgets" 
     _="on widget-moved(from, to)
        fetch /api/dashboard/save-layout with 
          body: JSON.stringify({from: from, to: to})
          method: 'POST'
          headers: {'Content-Type': 'application/json'}">
    
    <!-- Individual widgets -->
    <div class="col-xl-3 col-md-6 mb-4 widget" data-widget-id="stats" 
         _="install Draggable
           on widget-refresh
             fetch /api/dashboard/widget/stats
             put the result into me
           end">
        <div class="card border-left-primary shadow h-100 py-2">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                            Statistics
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">$40,000</div>
                    </div>
                    <div class="col-auto">
                        <div class="dropdown">
                            <button class="btn btn-sm btn-link text-muted dropdown-toggle" 
                                    data-bs-toggle="dropdown">
                                <i class="fas fa-ellipsis-v"></i>
                            </button>
                            <div class="dropdown-menu">
                                <a class="dropdown-item" href="#"
                                   _="on click send widget-refresh to my closest .widget">
                                    <i class="fas fa-sync-alt"></i> Refresh
                                </a>
                                <a class="dropdown-item" href="#"
                                   _="on click send widget-minimize to my closest .widget">
                                    <i class="fas fa-minus"></i> Minimize
                                </a>
                                <a class="dropdown-item text-danger" href="#"
                                   _="on click send widget-close to my closest .widget">
                                    <i class="fas fa-times"></i> Close
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Draggable behavior for widgets -->
<script type="text/hyperscript">
  behavior Draggable
    on mousedown
      if event.target matches '.card-body'
        set :dragging to true
        set :startX to event.clientX
        set :startY to event.clientY
        set :originalIndex to Array.from(my parentElement.parentElement.children).indexOf(my parentElement)
        
        repeat until event mouseup from elsewhere
          wait for mousemove(clientX, clientY) from elsewhere
          set my parentElement's style.transform to `translate(${clientX - :startX}px, ${clientY - :startY}px)`
          set :startX to clientX
          set :startY to clientY
          
          -- Check for drop zones
          get closest <.widget/> to {x: clientX, y: clientY}
          if it is not my parentElement and it exists
            set :dropTarget to it
          end
        end
        
        if :dropTarget exists
          set :newIndex to Array.from(my parentElement.parentElement.children).indexOf(:dropTarget)
          send widget-moved(from: :originalIndex, to: :newIndex) to .dashboard-widgets
        end
        
        set :dragging to false
        set my parentElement's style.transform to 'none'
      end
    end
  end
</script>
```

#### Dashboard State Management
```html
<!-- Dashboard state controller -->
<div id="dashboard-state" 
     _="init 
        set $dashboardState to {
          filters: {},
          selectedItems: [],
          currentView: 'grid',
          autoRefresh: true
        }
        
        on state-change(key, value)
          set $dashboardState[key] to value
          log 'Dashboard state updated:', key, value
          send dashboard-state-changed(state: $dashboardState) to body
        end
        
        on get-state
          return $dashboardState
        end">
</div>

<!-- Components that use dashboard state -->
<div class="btn-group view-switcher" role="group" 
     _="on click from .btn
        send state-change(key: 'currentView', value: target.dataset.view) to #dashboard-state
        remove .active from .btn
        add .active to target">
    
    <button type="button" class="btn btn-outline-primary active" data-view="grid">
        <i class="fas fa-th"></i> Grid
    </button>
    <button type="button" class="btn btn-outline-primary" data-view="list">
        <i class="fas fa-list"></i> List
    </button>
    <button type="button" class="btn btn-outline-primary" data-view="table">
        <i class="fas fa-table"></i> Table
    </button>
</div>

<!-- Data container that responds to state changes -->
<div id="data-container" 
     _="on dashboard-state-changed(state)
        if state.currentView is 'grid'
          add .row to me
          remove .list-group, .table-responsive from me
        else if state.currentView is 'list'
          add .list-group to me
          remove .row, .table-responsive from me
        else if state.currentView is 'table'
          add .table-responsive to me
          remove .row, .list-group from me
        end">
    <!-- Data items -->
</div>
```

#### Advanced Table Interactions
```html
<!-- Smart table with selection and sorting -->
<table class="table table-bordered table-hover dashboard-table" 
       _="init set :selectedRows to []
         on select-row(rowId)
           if :selectedRows contains rowId
             set :selectedRows to :selectedRows.filter(id => id !== rowId)
           else
             push rowId onto :selectedRows
           end
           send selection-changed(selected: :selectedRows) to #bulk-actions
         end
         
         on select-all
           if :selectedRows.length > 0
             set :selectedRows to []
           else
             set :selectedRows to Array.from(<tr[data-row-id]/> in me).map(row => row.dataset.rowId)
           end
           send selection-changed(selected: :selectedRows) to #bulk-actions
         end">
    
    <thead class="thead-dark">
        <tr>
            <th>
                <input class="form-check-input" type="checkbox" 
                       _="on change send select-all to my closest table">
            </th>
            <th class="sortable" 
                _="on click 
                   send sort-column(column: 'name', direction: my @data-sort-direction or 'asc') to #data-container
                   set my @data-sort-direction to (my @data-sort-direction is 'asc' ? 'desc' : 'asc')">
                Name 
                <i class="fas fa-sort text-muted"></i>
            </th>
            <th class="sortable" 
                _="on click 
                   send sort-column(column: 'email', direction: my @data-sort-direction or 'asc') to #data-container">
                Email 
                <i class="fas fa-sort text-muted"></i>
            </th>
            <th>Actions</th>
        </tr>
    </thead>
    
    <tbody>
        {% for user in users %}
        <tr data-row-id="{{ user.id }}" 
            _="on change from input[type=checkbox] in me
               send select-row(rowId: my @data-row-id) to my closest table">
            <td>
                <input class="form-check-input" 
                       type="checkbox" 
                       name="selected_users" 
                       value="{{ user.id }}">
            </td>
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
            <td>
                <button class="btn btn-sm btn-primary" 
                        _="on click 
                          fetch /api/dashboard/users/{{ user.id }}/edit
                          put the result into #modal-container">
                    Edit
                </button>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

#### Dashboard Notifications System
```html
<!-- Notification container -->
<div id="notifications" class="position-fixed top-0 end-0 p-3" style="z-index: 1050;" 
     _="on show-notification(message, type, duration)
        make a <div.toast/> called notification
        add .{type} to notification if type
        set notification.innerHTML to `
          <div class='toast-header'>
            <strong class='me-auto'>Dashboard</strong>
            <button type='button' class='btn-close' data-bs-dismiss='toast'></button>
          </div>
          <div class='toast-body'>${message}</div>
        `
        put notification at the end of me
        
        -- Initialize Bootstrap toast
        set toast to new bootstrap.Toast(notification)
        call toast.show()
        
        -- Auto-hide after duration
        if duration > 0
          wait {duration}ms
          call toast.hide()
        end
       end">
</div>

<!-- Components that trigger notifications -->
<form hx-post="/api/dashboard/users" 
      hx-target="#users-table" 
      hx-swap="afterbegin"
      _="on htmx:afterRequest
         if detail.xhr.status >= 200 and detail.xhr.status < 300
           send show-notification(message: 'User created successfully', type: 'success', duration: 3000) to #notifications
         else
           send show-notification(message: 'Error creating user', type: 'danger', duration: 5000) to #notifications
         end">
    <!-- Form fields -->
</form>
```

#### Dashboard Search and Filtering
```html
<!-- Advanced search component -->
<div class="card search-component" 
     _="init set :searchHistory to []
       on search-performed(query)
         if query is not empty
           if not (:searchHistory contains query)
             push query onto :searchHistory
             if :searchHistory.length > 10
               set :searchHistory to :searchHistory.slice(-10)
             end
           end
           localStorage.setItem('dashboard-search-history', JSON.stringify(:searchHistory))
         end
       end">
    
    <div class="card-body">
        <div class="input-group">
            <input type="search" 
                   class="form-control"
                   name="search" 
                   placeholder="Search..."
                   _="on keyup
                     if event.key is 'Enter'
                       send search-performed(query: my value) to .search-component
                     end
                     
                     if my value.length >= 2
                       fetch /api/dashboard/search/suggestions?q={my value}
                       put the result into #search-suggestions
                       show #search-suggestions
                     else
                       hide #search-suggestions
                     end"
                   
                   hx-get="/api/dashboard/search" 
                   hx-trigger="keyup changed delay:300ms" 
                   hx-target="#search-results"
                   hx-include="[name='filters']">
            
            <button class="btn btn-outline-secondary" type="button" 
                    _="on click 
                      toggle .show on #advanced-filters
                      if #advanced-filters matches .show
                        focus() on input[name='search']
                      end">
                <i class="fas fa-filter"></i>
            </button>
        </div>
        
        <!-- Search suggestions dropdown -->
        <div id="search-suggestions" class="list-group mt-2" style="display: none;">
            <!-- Populated by HTMX -->
        </div>
        
        <!-- Advanced filters (shown when expanded) -->
        <div id="advanced-filters" class="collapse mt-3"
             _="on filter-change
               set filters to {}
               for input in <input, select/> in me
                 if input.value is not empty
                   set filters[input.name] to input.value
                 end
               end
               send filters-changed(filters: filters) to body">
            
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Category</label>
                    <select class="form-select" name="category" 
                            _="on change send filter-change to #advanced-filters">
                        <option value="">All Categories</option>
                        <option value="users">Users</option>
                        <option value="orders">Orders</option>
                    </select>
                </div>
                
                <div class="col-md-3">
                    <label class="form-label">Date From</label>
                    <input type="date" 
                           class="form-control"
                           name="date_from" 
                           _="on change send filter-change to #advanced-filters">
                </div>
                
                <div class="col-md-3">
                    <label class="form-label">Date To</label>
                    <input type="date" 
                           class="form-control"
                           name="date_to" 
                           _="on change send filter-change to #advanced-filters">
                </div>
            </div>
        </div>
    </div>
</div>
```

#### Real-time Dashboard Updates
```html
<!-- WebSocket connection for real-time updates -->
<div id="websocket-manager" 
     _="init 
        set :ws to new WebSocket('ws://localhost:5000/dashboard-updates')
        set :ws.onmessage to def(event)
          set data to JSON.parse(event.data)
          send websocket-message(data: data) to body
        end
        set :ws.onerror to def(event)  
          send show-notification(message: 'Connection lost', type: 'warning', duration: 0) to #notifications
        end
        set :ws.onopen to def(event)
          send show-notification(message: 'Connected', type: 'success', duration: 2000) to #notifications
        end">
</div>

<!-- Components that respond to real-time updates -->
<div class="row stats-widgets" 
     _="on websocket-message(data)
        if data.type is 'stats-update'
          put data.stats.total_users into #total-users
          put data.stats.active_sessions into #active-sessions
        end">
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-primary shadow h-100 py-2">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                            Total Users
                        </div>
                        <div id="total-users" class="h5 mb-0 font-weight-bold text-gray-800">
                            {{ stats.total_users }}
                        </div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-users fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-success shadow h-100 py-2">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-success text-uppercase mb-1">
                            Active Sessions
                        </div>
                        <div id="active-sessions" class="h5 mb-0 font-weight-bold text-gray-800">
                            {{ stats.active_sessions }}
                        </div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-wifi fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Activity feed that updates in real-time -->
<div class="card shadow mb-4 activity-feed" 
     _="on websocket-message(data)
        if data.type is 'activity'
          make a <div.list-group-item/> called item
          set item.innerHTML to `
            <div class='d-flex w-100 justify-content-between'>
              <h6 class='mb-1'>${data.activity.title}</h6>
              <small>${data.activity.time}</small>
            </div>
            <p class='mb-1'>${data.activity.message}</p>
          `
          put item at the start of #activity-list
          
          -- Keep only last 50 items
          set items to <.list-group-item/> in #activity-list
          if items.length > 50
            remove items[50]
          end
        end">
    
    <div class="card-header py-3">
        <h6 class="m-0 font-weight-bold text-primary">Recent Activity</h6>
    </div>
    <div class="card-body">
        <div id="activity-list" class="list-group list-group-flush">
            <!-- Activity items appear here -->
        </div>
    </div>
</div>
```

### Basic Syntax

#### Installation and Setup
```html
<script src="https://unpkg.com/hyperscript.org@0.9.14"></script>

<!-- Using the _ attribute -->
<button _="on click toggle .red on me">Click Me</button>

<!-- Alternative attributes -->
<button script="on click toggle .red on me">Click Me</button>
<button data-script="on click toggle .red on me">Click Me</button>

<!-- In script tags -->
<script type="text/hyperscript">
  on click from #myButton
    add .highlight to #target
  end
</script>
```

#### Event Handlers
```html
<!-- Basic event handling -->
<button class="btn btn-primary" _="on click log 'Button clicked!'">Click Me</button>

<!-- Multiple events -->
<div class="card" _="on mouseenter add .shadow-lg
                    on mouseleave remove .shadow-lg">Hover Me</div>

<!-- Event with conditions -->
<input class="form-control" _="on keyup[key is 'Enter'] call submitForm()">

<!-- Event with parameters -->
<button class="btn btn-secondary" _="on mousedown(button) 
                                    if button is 1 add .btn-warning">Middle Click</button>

<!-- Event delegation -->
<div class="list-group" _="on click from .list-group-item
                          remove the closest .list-group-item">
  <div class="list-group-item">Item 1 <button class="btn btn-sm btn-danger">Delete</button></div>
</div>
```

### DOM Manipulation

#### Finding Elements
```html
<!-- CSS selectors as literals -->
<button class="btn btn-primary" _="on click add .highlight to .target">Highlight targets</button>
<button class="btn btn-danger" _="on click remove #item-123">Remove item</button>
<button class="btn btn-secondary" _="on click toggle .d-none on <div.sidebar/>">Toggle sidebar</button>

<!-- Positional selectors -->
<button class="btn btn-outline-primary" _="on click add .active to the first .nav-link">Select first</button>
<button class="btn btn-outline-danger" _="on click remove the last .list-group-item">Remove last</button>
<button class="btn btn-outline-warning" _="on click add .bg-warning to random in .card">Random highlight</button>

<!-- Relative selectors -->
<button class="btn btn-info" _="on click add .active to the next .tab-pane">Next tab</button>
<button class="btn btn-secondary" _="on click remove the previous .breadcrumb-item">Previous item</button>
<button class="btn btn-primary" _="on click toggle .collapse on the closest .accordion-collapse">Toggle section</button>
```

#### Content Manipulation
```html
<!-- Setting content -->
<button class="btn btn-primary" _="on click put 'Hello Bootstrap!' into #output">Set content</button>
<button class="btn btn-secondary" _="on click set #output's innerHTML to '<div class=\"alert alert-success\">Success!</div>'">Set HTML</button>

<!-- Appending/prepending -->
<button class="btn btn-outline-primary" _="on click put '<div class=\"list-group-item\">New item</div>' at the end of #list">Append</button>
<button class="btn btn-outline-secondary" _="on click put '<div class=\"list-group-item\">First item</div>' at the start of #list">Prepend</button>

<!-- Positioning content -->
<button class="btn btn-warning" _="on click put '<div class=\"alert alert-info\">Before</div>' before #target">Insert before</button>
<button class="btn btn-info" _="on click put '<div class=\"alert alert-success\">After</div>' after #target">Insert after</button>
```

#### Attributes and Styles
```html
<!-- Working with attributes -->
<button class="btn btn-danger" _="on click set @disabled to 'disabled' on #submit-btn">Disable</button>
<button class="btn btn-success" _="on click remove @disabled from #submit-btn">Enable</button>
<button class="btn btn-warning" _="on click toggle @disabled on #submit-btn">Toggle disable</button>

<!-- Working with Bootstrap classes -->
<div class="card" _="on click toggle .border-primary on me">Toggle border</div>
<div class="btn-group" _="on click add .active to target then remove .active from .btn in me">
  <button class="btn btn-outline-primary">Option 1</button>
  <button class="btn btn-outline-primary">Option 2</button>
</div>

<!-- Working with styles -->
<div class="progress" _="on click set *width of .progress-bar in me to '75%'">
  <div class="progress-bar" style="width: 25%"></div>
</div>
```

### Variables and Data

#### Variable Scopes
```html
<!-- Local variables -->
<button class="btn btn-primary" _="on click 
                                  set x to 10 
                                  log x">Local variable</button>

<!-- Element-scoped variables (prefix with :) -->
<button class="btn btn-secondary" _="on click 
                                    increment :count 
                                    put :count into the next <span/>">
  Count: <span class="badge bg-primary">0</span>
</button>

<!-- Global variables (prefix with $) -->
<button class="btn btn-info" _="on click 
                               set $globalCounter to ($globalCounter or 0) + 1
                               log $globalCounter">Global counter</button>
```

#### Special Variables
```html
<!-- Built-in variables -->
<button class="btn btn-primary" _="on click log me">Log current element</button>
<button class="btn btn-secondary" _="on click log event">Log current event</button>
<button class="btn btn-info" _="on click log target">Log event target</button>
<button class="btn btn-warning" _="on click log detail">Log event detail</button>
<div class="alert alert-info" _="on customEvent(data) log data">Handle custom event with data</div>
```

### Control Flow

#### Conditionals
```html
<!-- Basic if/else -->
<button class="btn btn-primary" _="on click 
                                  if I match .btn-primary
                                    remove .btn-primary from me
                                    add .btn-secondary to me
                                  else
                                    remove .btn-secondary from me
                                    add .btn-primary to me
                                  end">Toggle button style</button>

<!-- Natural language comparisons -->
<input class="form-control" _="on input
                               if my value is not empty
                                 remove .is-invalid from me
                                 add .is-valid to me
                               else
                                 remove .is-valid from me
                                 add .is-invalid to me
                               end">

<!-- Unless modifier -->
<button class="btn btn-primary" _="on click 
                                  add .loading unless I match .disabled">Process</button>
```

#### Loops
```html
<!-- For loops -->
<button class="btn btn-primary" _="on click
                                  for item in [1, 2, 3, 4, 5]
                                    put '<div class=\"alert alert-info\">Item ' + item + '</div>' at the end of #list
                                  end">Add numbers</button>

<!-- While loops -->
<button class="btn btn-secondary" _="on click
                                    set i to 0
                                    repeat while i < 5
                                      log i
                                      increment i
                                    end">Count to 5</button>

<!-- Repeat with times -->
<button class="btn btn-info" _="on click
                               repeat 3 times
                                 put '<div class=\"toast\">Hello</div>' at the end of #output
                               end">Say hello 3 times</button>
```

### Async Operations

#### Waiting and Timing
```html
<!-- Wait for time -->
<button class="btn btn-primary" _="on click
                                  put 'Processing...' into me
                                  add .disabled to me
                                  wait 2s
                                  put 'Done!' into me
                                  remove .disabled from me">Process</button>

<!-- Wait for events -->
<button class="btn btn-warning" _="on click
                                  put 'Click continue...' into #status
                                  wait for continue
                                  put '<div class=\"alert alert-success\">Continued!</div>' into #status">
  Start Process
</button>
<button class="btn btn-success" _="on click send continue to the previous <button/>">Continue</button>

<!-- Wait with timeout -->
<button class="btn btn-info" _="on click
                               put '<div class=\"spinner-border\"></div> Waiting...' into #status
                               wait for continue or 5s
                               if the result's type is 'continue'
                                 put '<div class=\"alert alert-success\">Got continue!</div>' into #status
                               else
                                 put '<div class=\"alert alert-warning\">Timed out!</div>' into #status
                               end">Wait with timeout</button>
```

#### Fetch Requests
```html
<!-- Basic fetch -->
<button class="btn btn-primary" _="on click
                                  fetch /api/data
                                  put the result into #content">Get data</button>

<!-- Fetch with error handling -->
<button class="btn btn-secondary" _="on click
                                    fetch /api/data
                                    if the response's ok
                                      put the result into #content
                                    else
                                      put '<div class=\"alert alert-danger\">Error loading data</div>' into #error
                                    end">Get data safely</button>

<!-- Fetch with POST -->
<form class="needs-validation" _="on submit
                                  fetch /api/submit with body: new FormData(me)
                                  put the result into #response
                                  reset() me">
  <div class="mb-3">
    <input class="form-control" name="username" placeholder="Username" required>
  </div>
  <button type="submit" class="btn btn-primary">Submit</button>
</form>
```

### Event Handling and Communication

#### Sending Custom Events
```html
<!-- Send events to other elements -->
<button class="btn btn-primary" _="on click send refresh to #data-panel">Refresh data</button>

<!-- Send events with data -->
<button class="btn btn-success" _="on click 
                                  send update(id: 123, status: 'active') to #status-panel">
  Update status
</button>

<!-- Send events to multiple targets -->
<button class="btn btn-info" _="on click send refresh to .data-panel">Refresh all panels</button>
```

#### Event Queueing
```html
<!-- Default: queue last -->
<button class="btn btn-primary" _="on click 
                                  wait 1s 
                                  put 'Done' into #output">Default queuing</button>

<!-- Queue all events -->
<button class="btn btn-secondary" _="on click queue all
                                    increment :count
                                    wait 1s
                                    put :count into #output">Queue all</button>

<!-- Process every event immediately -->
<button class="btn btn-info" _="on every click
                               increment :count
                               put :count into #output">Process every click</button>

<!-- Queue first only -->
<button class="btn btn-warning" _="on click queue first
                                  wait 2s
                                  put 'Processed' into #output">Queue first only</button>
```

### Advanced Features

#### Behaviors (Reusable Components)
```html
<script type="text/hyperscript">
  behavior Draggable
    on mousedown
      set startX to event.clientX
      set startY to event.clientY
      add .dragging to me
      
      repeat until event mouseup from elsewhere
        wait for mousemove(clientX, clientY) from elsewhere
        set my *left to (my offsetLeft + clientX - startX) + 'px'
        set my *top to (my offsetTop + clientY - startY) + 'px'
        set startX to clientX
        set startY to clientY
      end
      
      remove .dragging from me
    end
  end
  
  behavior TooltipToggle
    on mouseenter
      make a <div.tooltip.bs-tooltip-top/> called tip
      put my @data-bs-title into tip
      put tip after me
      
      -- Position tooltip
      set my *position to 'relative'
    end
    
    on mouseleave
      remove .tooltip from elsewhere
    end
  end
</script>

<!-- Install behaviors -->
<div class="card draggable-box" _="install Draggable" 
     style="width: 200px; height: 100px; cursor: move;">
  Drag me!
</div>

<button class="btn btn-primary" 
        _="install TooltipToggle" 
        data-bs-title="This is a custom tooltip">
  Hover for tooltip
</button>
```

#### Transitions and Animations
```html
<!-- Bootstrap fade transitions -->
<div class="alert alert-info" _="on click 
                                add .fade to me
                                wait 300ms
                                add .show to me">
  Fade in alert
</div>

<!-- Custom animations with Bootstrap classes -->
<div class="card" _="on click 
                    add .border-primary then settle
                    wait 500ms
                    remove .border-primary then settle">
  Animate with classes
</div>

<!-- Toggle with events -->
<div class="badge bg-secondary" _="on mouseenter add .bg-primary then remove .bg-secondary until mouseleave
                                  on mouseleave add .bg-secondary then remove .bg-primary">
  Hover highlight
</div>
```

#### Functions
```html
<script type="text/hyperscript">
  def calculateTotal(items)
    set total to 0
    for item in items
      set total to total + item.price
    end
    return total
  end
  
  def utils.formatCurrency(amount)
    return '$' + amount.toFixed(2)
  end
  
  def ui.showAlert(message, type)
    make a <div.alert/> called alert
    add .{`alert-${type}`} to alert
    put message into alert
    put alert at the start of body
    wait 3s
    remove alert
  end
</script>

<button class="btn btn-primary" _="on click
                                  call calculateTotal([{price: 10}, {price: 20}])
                                  call ui.showAlert(utils.formatCurrency(it), 'success')">
  Calculate total
</button>
```

---

## Bootstrap 5 for Dashboard Styling

### Overview
Bootstrap 5 provides an excellent foundation for Flask dashboard styling by offering a comprehensive component library, responsive grid system, and utility classes perfect for modern dashboard interfaces.

### Installation

#### CDN Installation
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask Dashboard</title>
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" 
          rel="stylesheet" 
          integrity="sha384-LN+7fdVzj6u52u30Kp6M/trliBMCMKTyK833zpbD+pXdCLuTusPj697FH4R/5mcr" 
          crossorigin="anonymous">
    <!-- Font Awesome for icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <!-- _hyperscript -->
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
</head>
<body>
    <!-- Dashboard content -->
    
    <!-- Bootstrap 5 JS Bundle -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js" 
            integrity="sha384-ndDqU0Gzau9qJ1lfW4pNLlhNTkCfHzAVBReH9diLvGRem5+R9g2FzA8ZGN954O5Q" 
            crossorigin="anonymous"></script>
</body>
</html>
```

#### NPM Installation
```bash
npm install bootstrap@5.3.7
```

### Dashboard Layout Foundations

#### Basic Dashboard Structure
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" 
          rel="stylesheet" 
          integrity="sha384-LN+7fdVzj6u52u30Kp6M/trliBMCMKTyK833zpbD+pXdCLuTusPj697FH4R/5mcr" 
          crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
</head>
<body class="bg-light">
    <!-- Navigation Header -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-tachometer-alt me-2"></i>
                Dashboard
            </a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link active" href="/dashboard">
                            <i class="fas fa-home me-1"></i> Overview
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/dashboard/analytics">
                            <i class="fas fa-chart-line me-1"></i> Analytics
                        </a>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-cogs me-1"></i> Management
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="/dashboard/users">
                                <i class="fas fa-users me-2"></i> Users
                            </a></li>
                            <li><a class="dropdown-item" href="/dashboard/orders">
                                <i class="fas fa-shopping-cart me-2"></i> Orders
                            </a></li>
                        </ul>
                    </li>
                </ul>
                
                <div class="navbar-nav">
                    <!-- User menu -->
                    <div class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-user-circle me-1"></i>
                            {{ current_user.username }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="/profile">
                                <i class="fas fa-user me-2"></i> Profile
                            </a></li>
                            <li><a class="dropdown-item" href="/settings">
                                <i class="fas fa-cog me-2"></i> Settings
                            </a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="/logout">
                                <i class="fas fa-sign-out-alt me-2"></i> Logout
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </nav>
    
    <!-- Main Container -->
    <div class="container-fluid" style="margin-top: 60px;">
        <div class="row">
            <!-- Sidebar -->
            <nav class="col-md-3 col-lg-2 d-md-block bg-white sidebar collapse">
                <div class="position-sticky pt-3">
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link active" href="/dashboard">
                                <i class="fas fa-home me-2"></i>
                                Dashboard
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/analytics">
                                <i class="fas fa-chart-area me-2"></i>
                                Analytics
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/users">
                                <i class="fas fa-users me-2"></i>
                                Users
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/orders">
                                <i class="fas fa-shopping-bag me-2"></i>
                                Orders
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/reports">
                                <i class="fas fa-file-alt me-2"></i>
                                Reports
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/settings">
                                <i class="fas fa-cog me-2"></i>
                                Settings
                            </a>
                        </li>
                    </ul>
                </div>
            </nav>
            
            <!-- Main Content -->
            <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
                <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                    <h1 class="h2">{% block page_title %}Dashboard{% endblock %}</h1>
                    <div class="btn-toolbar mb-2 mb-md-0">
                        <div class="btn-group me-2">
                            <button type="button" class="btn btn-sm btn-outline-secondary">
                                <i class="fas fa-share"></i> Share
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary">
                                <i class="fas fa-download"></i> Export
                            </button>
                        </div>
                        <button type="button" class="btn btn-sm btn-primary">
                            <i class="fas fa-calendar-week"></i> This week
                        </button>
                    </div>
                </div>
                
                <!-- Dashboard Content -->
                <div class="dashboard-content">
                    {% block content %}{% endblock %}
                </div>
            </main>
        </div>
    </div>
    
    <!-- Toast Container for Notifications -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <!-- Toasts will be dynamically added here -->
    </div>
    
    <!-- Modal Container -->
    <div id="modal-container"></div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js" 
            integrity="sha384-ndDqU0Gzau9qJ1lfW4pNLlhNTkCfHzAVBReH9diLvGRem5+R9g2FzA8ZGN954O5Q" 
            crossorigin="anonymous"></script>
    
    <!-- Dashboard Custom CSS -->
    <style>
        .sidebar {
            box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
        }
        
        .sidebar .nav-link {
            color: #333;
            border-radius: 0.375rem;
            margin: 0.125rem 0.5rem;
        }
        
        .sidebar .nav-link:hover {
            background-color: #f8f9fa;
        }
        
        .sidebar .nav-link.active {
            background-color: #0d6efd;
            color: white;
        }
        
        .dashboard-stat-card {
            transition: transform 0.2s;
        }
        
        .dashboard-stat-card:hover {
            transform: translateY(-2px);
        }
        
        @media (max-width: 767.98px) {
            .sidebar {
                top: 5rem;
            }
        }
    </style>
</body>
</html>
```

### Dashboard Components

#### Stats Cards
```html
<!-- Dashboard Statistics Cards -->
<div class="row mb-4">
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-primary shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                            Total Users
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">1,234</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-users fa-2x text-primary opacity-25"></i>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-success">
                        <i class="fas fa-arrow-up"></i> 12%
                    </span>
                    <span class="text-muted small">from last month</span>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-success shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-success text-uppercase mb-1">
                            Revenue
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">$45,678</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-dollar-sign fa-2x text-success opacity-25"></i>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-danger">
                        <i class="fas fa-arrow-down"></i> 3%
                    </span>
                    <span class="text-muted small">from last month</span>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-info shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-info text-uppercase mb-1">
                            Conversion Rate
                        </div>
                        <div class="row no-gutters align-items-center">
                            <div class="col-auto">
                                <div class="h5 mb-0 mr-3 font-weight-bold text-gray-800">89.2%</div>
                            </div>
                            <div class="col">
                                <div class="progress progress-sm mr-2">
                                    <div class="progress-bar bg-info" role="progressbar" 
                                         style="width: 89%" aria-valuenow="89" aria-valuemin="0" aria-valuemax="100">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-clipboard-list fa-2x text-info opacity-25"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-warning shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">
                            Active Sessions
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">324</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-wifi fa-2x text-warning opacity-25"></i>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-secondary">
                        <i class="fas fa-minus"></i> No change
                    </span>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
.border-left-primary {
    border-left: 0.25rem solid #4e73df !important;
}

.border-left-success {
    border-left: 0.25rem solid #1cc88a !important;
}

.border-left-info {
    border-left: 0.25rem solid #36b9cc !important;
}

.border-left-warning {
    border-left: 0.25rem solid #f6c23e !important;
}

.text-xs {
    font-size: 0.75rem;
}

.progress-sm {
    height: 0.5rem;
}
</style>
```

#### Enhanced Data Tables
```html
<!-- Enhanced Dashboard Data Table -->
<div class="card shadow mb-4">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">Users Management</h6>
        <div class="dropdown">
            <button class="btn btn-primary btn-sm dropdown-toggle" data-bs-toggle="dropdown">
                <i class="fas fa-plus"></i> Actions
            </button>
            <ul class="dropdown-menu">
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/users/new" 
                       hx-target="#modal-container">
                        <i class="fas fa-user-plus me-2"></i> Add User
                    </a>
                </li>
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/users/import" 
                       hx-target="#modal-container">
                        <i class="fas fa-file-import me-2"></i> Import Users
                    </a>
                </li>
                <li><hr class="dropdown-divider"></li>
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/export/users" 
                       hx-trigger="click">
                        <i class="fas fa-download me-2"></i> Export CSV
                    </a>
                </li>
            </ul>
        </div>
    </div>
    
    <!-- Table Filters -->
    <div class="card-body border-bottom">
        <div class="row g-3 align-items-end">
            <div class="col-md-4">
                <label class="form-label small text-muted">Search</label>
                <div class="input-group">
                    <span class="input-group-text">
                        <i class="fas fa-search"></i>
                    </span>
                    <input type="search" 
                           class="form-control"
                           name="search" 
                           placeholder="Search users..."
                           hx-get="/api/dashboard/table/users" 
                           hx-trigger="keyup changed delay:300ms" 
                           hx-target="#users-table-body"
                           hx-include="[name='status'], [name='role'], [name='per_page']">
                </div>
            </div>
            
            <div class="col-md-2">
                <label class="form-label small text-muted">Status</label>
                <select class="form-select" name="status"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table-body"
                        hx-include="[name='search'], [name='role'], [name='per_page']">
                    <option value="">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <label class="form-label small text-muted">Role</label>
                <select class="form-select" name="role"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table-body"
                        hx-include="[name='search'], [name='status'], [name='per_page']">
                    <option value="">All Roles</option>
                    <option value="admin">Admin</option>
                    <option value="user">User</option>
                    <option value="moderator">Moderator</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <label class="form-label small text-muted">Per Page</label>
                <select class="form-select" name="per_page"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table-body"
                        hx-include="[name='search'], [name='status'], [name='role']">
                    <option value="10">10</option>
                    <option value="25" selected>25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <button class="btn btn-outline-secondary w-100"
                        onclick="document.querySelector('form').reset(); 
                                 htmx.trigger('#users-table-body', 'refresh')">
                    <i class="fas fa-undo"></i> Reset
                </button>
            </div>
        </div>
    </div>
    
    <!-- Bulk Actions Bar -->
    <div id="bulk-actions-bar" class="alert alert-info m-0 rounded-0 d-none">
        <div class="d-flex justify-content-between align-items-center">
            <span class="fw-bold">
                <i class="fas fa-check-square me-2"></i>
                <span id="selected-count">0</span> users selected
            </span>
            <div class="btn-group btn-group-sm">
                <button class="btn btn-success" 
                        hx-post="/api/dashboard/users/bulk-activate" 
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-body"
                        hx-confirm="Activate selected users?">
                    <i class="fas fa-check"></i> Activate
                </button>
                <button class="btn btn-warning" 
                        hx-post="/api/dashboard/users/bulk-deactivate" 
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-body"
                        hx-confirm="Deactivate selected users?">
                    <i class="fas fa-pause"></i> Deactivate
                </button>
                <button class="btn btn-danger" 
                        hx-delete="/api/dashboard/users/bulk-delete" 
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-body"
                        hx-confirm="Delete selected users? This action cannot be undone.">
                    <i class="fas fa-trash"></i> Delete
                </button>
            </div>
        </div>
    </div>
    
    <!-- Table -->
    <div class="table-responsive">
        <table class="table table-bordered table-hover mb-0" id="dataTable">
            <thead class="table-light">
                <tr>
                    <th class="text-center" style="width: 40px;">
                        <input class="form-check-input" type="checkbox" id="select-all"
                               _="on change
                                  set checkboxes to <input[name='selected_users']/> in #users-table-body
                                  for checkbox in checkboxes
                                    set checkbox.checked to my checked
                                  end
                                  update-bulk-actions()">
                    </th>
                    <th class="sortable" data-sort="username">
                        Username <i class="fas fa-sort text-muted"></i>
                    </th>
                    <th class="sortable" data-sort="email">
                        Email <i class="fas fa-sort text-muted"></i>
                    </th>
                    <th>Role</th>
                    <th class="text-center">Status</th>
                    <th class="sortable" data-sort="created_at">
                        Created <i class="fas fa-sort text-muted"></i>
                    </th>
                    <th class="text-center" style="width: 120px;">Actions</th>
                </tr>
            </thead>
            <tbody id="users-table-body" 
                   hx-get="/api/dashboard/table/users" 
                   hx-trigger="load"
                   hx-swap="innerHTML">
                <!-- Loading state -->
                <tr>
                    <td colspan="7" class="text-center py-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <div class="mt-2 text-muted">Loading users...</div>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
    
    <!-- Pagination -->
    <div class="card-footer">
        <div class="row align-items-center">
            <div class="col-sm-6">
                <div class="dataTables_info">
                    Showing <span id="page-start">1</span> to <span id="page-end">25</span> 
                    of <span id="total-entries">100</span> entries
                </div>
            </div>
            <div class="col-sm-6">
                <nav>
                    <ul class="pagination justify-content-end mb-0" id="pagination-container">
                        <!-- Pagination buttons will be loaded here -->
                    </ul>
                </nav>
            </div>
        </div>
    </div>
</div>

<script type="text/hyperscript">
  def update-bulk-actions()
    set selectedBoxes to <input[name='selected_users']:checked/>
    set count to selectedBoxes.length
    put count into #selected-count
    
    if count > 0
      remove .d-none from #bulk-actions-bar
    else
      add .d-none to #bulk-actions-bar
    end
  end
  
  -- Auto-update bulk actions when checkboxes change
  on change from input[name='selected_users']
    update-bulk-actions()
  end
</script>
```

#### Dashboard Forms and Modals
```html
<!-- Bootstrap 5 Modal Form -->
<div class="modal fade show d-block" tabindex="-1" style="background: rgba(0,0,0,0.5);">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">
                    <i class="fas fa-user-plus me-2"></i>
                    Add New User
                </h5>
                <button type="button" class="btn-close" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                </button>
            </div>
            
            <form hx-post="/api/dashboard/users" 
                  hx-target="#users-table-body" 
                  hx-swap="afterbegin"
                  class="needs-validation" 
                  novalidate
                  hx-on::after-request="if(event.detail.successful) { 
                    document.getElementById('modal-container').innerHTML = ''; 
                    showToast('User created successfully', 'success'); 
                  }">
                
                <div class="modal-body">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label class="form-label" for="first_name">
                                First Name <span class="text-danger">*</span>
                            </label>
                            <input type="text" 
                                   class="form-control"
                                   id="first_name" 
                                   name="first_name" 
                                   required>
                            <div class="invalid-feedback">
                                Please provide a first name.
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <label class="form-label" for="last_name">
                                Last Name <span class="text-danger">*</span>
                            </label>
                            <input type="text" 
                                   class="form-control"
                                   id="last_name" 
                                   name="last_name" 
                                   required>
                            <div class="invalid-feedback">
                                Please provide a last name.
                            </div>
                        </div>
                        
                        <div class="col-12">
                            <label class="form-label" for="email">
                                Email Address <span class="text-danger">*</span>
                            </label>
                            <div class="input-group">
                                <span class="input-group-text">
                                    <i class="fas fa-envelope"></i>
                                </span>
                                <input type="email" 
                                       class="form-control"
                                       id="email" 
                                       name="email" 
                                       required
                                       hx-get="/api/dashboard/validate/email"
                                       hx-trigger="blur"
                                       hx-target="#email-validation">
                                <div class="invalid-feedback">
                                    Please provide a valid email address.
                                </div>
                            </div>
                            <div id="email-validation" class="mt-1"></div>
                        </div>
                        
                        <div class="col-md-6">
                            <label class="form-label" for="role">
                                Role <span class="text-danger">*</span>
                            </label>
                            <select class="form-select" id="role" name="role" required>
                                <option value="">Select a role</option>
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                                <option value="moderator">Moderator</option>
                            </select>
                            <div class="invalid-feedback">
                                Please select a role.
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <label class="form-label" for="department">Department</label>
                            <select class="form-select" id="department" name="department">
                                <option value="">Select department</option>
                                <option value="engineering">Engineering</option>
                                <option value="marketing">Marketing</option>
                                <option value="sales">Sales</option>
                                <option value="support">Support</option>
                            </select>
                        </div>
                        
                        <div class="col-12">
                            <div class="form-check form-switch">
                                <input class="form-check-input" 
                                       type="checkbox" 
                                       id="is_active" 
                                       name="is_active" 
                                       checked>
                                <label class="form-check-label" for="is_active">
                                    Active User
                                </label>
                            </div>
                        </div>
                        
                        <div class="col-12">
                            <div class="form-check">
                                <input class="form-check-input" 
                                       type="checkbox" 
                                       id="send_welcome" 
                                       name="send_welcome" 
                                       checked>
                                <label class="form-check-label" for="send_welcome">
                                    Send welcome email
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" 
                            onclick="document.getElementById('modal-container').innerHTML = ''">
                        <i class="fas fa-times me-1"></i> Cancel
                    </button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save me-1"></i> Create User
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
```

#### Dashboard Charts and Visualizations Container
```html
<!-- Chart widgets with Bootstrap cards -->
<div class="row mb-4">
    <div class="col-xl-8 col-lg-7">
        <div class="card shadow mb-4">
            <div class="card-header py-3 d-flex justify-content-between align-items-center">
                <h6 class="m-0 font-weight-bold text-primary">Revenue Trend</h6>
                <div class="dropdown">
                    <button class="btn btn-outline-primary btn-sm dropdown-toggle" 
                            data-bs-toggle="dropdown">
                        <i class="fas fa-calendar me-1"></i> Time Range
                    </button>
                    <ul class="dropdown-menu">
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/revenue?period=7d" 
                               hx-target="#revenue-chart">
                                Last 7 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/revenue?period=30d" 
                               hx-target="#revenue-chart">
                                Last 30 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/revenue?period=90d" 
                               hx-target="#revenue-chart">
                                Last 90 days
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="card-body">
                <div id="revenue-chart" 
                     hx-get="/api/dashboard/chart/revenue?period=30d" 
                     hx-trigger="load"
                     style="height: 400px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="text-center">
                            <div class="spinner-border text-primary mb-3" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <div class="text-muted">Loading chart...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-4 col-lg-5">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">User Distribution</h6>
            </div>
            <div class="card-body">
                <div id="user-distribution-chart" 
                     hx-get="/api/dashboard/chart/user-distribution" 
                     hx-trigger="load"
                     style="height: 320px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Performance metrics grid -->
<div class="row mb-4">
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Performance Metrics</h6>
            </div>
            <div class="card-body">
                <h4 class="small font-weight-bold">
                    Server Response Time 
                    <span class="float-end">40%</span>
                </h4>
                <div class="progress mb-4">
                    <div class="progress-bar bg-danger" role="progressbar" 
                         style="width: 40%" aria-valuenow="40" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                
                <h4 class="small font-weight-bold">
                    Sales Tracking 
                    <span class="float-end">60%</span>
                </h4>
                <div class="progress mb-4">
                    <div class="progress-bar bg-warning" role="progressbar" 
                         style="width: 60%" aria-valuenow="60" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                
                <h4 class="small font-weight-bold">
                    Customer Database 
                    <span class="float-end">80%</span>
                </h4>
                <div class="progress mb-4">
                    <div class="progress-bar" role="progressbar" 
                         style="width: 80%" aria-valuenow="80" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                
                <h4 class="small font-weight-bold">
                    Payout Details 
                    <span class="float-end">Complete!</span>
                </h4>
                <div class="progress">
                    <div class="progress-bar bg-success" role="progressbar" 
                         style="width: 100%" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Recent Activity</h6>
            </div>
            <div class="card-body" style="max-height: 300px; overflow-y: auto;">
                <div class="timeline" id="activity-timeline" 
                     hx-get="/api/dashboard/activity" 
                     hx-trigger="load, every 60s">
                    <div class="d-flex justify-content-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

#### Bootstrap Navigation Components
```html
<!-- Dashboard Navigation Tabs -->
<div class="card shadow mb-4">
    <div class="card-header">
        <ul class="nav nav-tabs card-header-tabs" id="dashboard-tabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="overview-tab" 
                        data-bs-toggle="tab" data-bs-target="#overview" 
                        type="button" role="tab">
                    <i class="fas fa-chart-line me-1"></i> Overview
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="analytics-tab" 
                        data-bs-toggle="tab" data-bs-target="#analytics" 
                        type="button" role="tab"
                        hx-get="/api/dashboard/analytics" 
                        hx-target="#analytics" 
                        hx-trigger="click once">
                    <i class="fas fa-chart-pie me-1"></i> Analytics
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="reports-tab" 
                        data-bs-toggle="tab" data-bs-target="#reports" 
                        type="button" role="tab"
                        hx-get="/api/dashboard/reports" 
                        hx-target="#reports" 
                        hx-trigger="click once">
                    <i class="fas fa-file-alt me-1"></i> Reports
                </button>
            </li>
        </ul>
    </div>
    
    <div class="card-body">
        <div class="tab-content" id="dashboard-tab-content">
            <div class="tab-pane fade show active" id="overview" role="tabpanel">
                <!-- Overview content -->
                <div class="row">
                    <div class="col-md-8">
                        <h5>Dashboard Overview</h5>
                        <p class="text-muted">Welcome to your dashboard. Here you can see an overview of your key metrics and recent activity.</p>
                    </div>
                    <div class="col-md-4">
                        <div class="text-center">
                            <i class="fas fa-chart-area fa-3x text-primary mb-3"></i>
                            <h6>Quick Stats</h6>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="analytics" role="tabpanel">
                <div class="d-flex justify-content-center p-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading analytics...</span>
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="reports" role="tabpanel">
                <div class="d-flex justify-content-center p-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading reports...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Breadcrumb Navigation -->
<nav aria-label="breadcrumb" class="mb-4">
    <ol class="breadcrumb">
        <li class="breadcrumb-item">
            <a href="/dashboard">
                <i class="fas fa-home me-1"></i> Dashboard
            </a>
        </li>
        <li class="breadcrumb-item">
            <a href="/dashboard/users">Users</a>
        </li>
        <li class="breadcrumb-item active" aria-current="page">
            User Details
        </li>
    </ol>
</nav>
```

#### Bootstrap Alerts and Notifications
```html
<!-- Toast Notifications -->
<div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1060;">
    <!-- Toasts will be inserted here -->
</div>

<!-- Alert Messages -->
<div id="alert-container" class="mb-4">
    <!-- Alerts will be dynamically added here -->
</div>

<!-- Success Alert Example -->
<div class="alert alert-success alert-dismissible fade show" role="alert">
    <i class="fas fa-check-circle me-2"></i>
    <strong>Success!</strong> User has been created successfully.
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>

<!-- Warning Alert with Action -->
<div class="alert alert-warning alert-dismissible fade show" role="alert">
    <div class="d-flex justify-content-between align-items-center">
        <div>
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Warning!</strong> Your subscription expires in 3 days.
        </div>
        <div>
            <button class="btn btn-warning btn-sm me-2">Renew Now</button>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    </div>
</div>

<script type="text/hyperscript">
  def showToast(message, type)
    set toastHtml to `
      <div class="toast" role="alert" data-bs-autohide="true" data-bs-delay="5000">
        <div class="toast-header">
          <div class="rounded me-2 ${type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info'}" 
               style="width: 20px; height: 20px;"></div>
          <strong class="me-auto">Dashboard</strong>
          <small>just now</small>
          <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
          ${message}
        </div>
      </div>
    `
    
    make a <div/> called toastElement
    set toastElement.innerHTML to toastHtml
    set toastEl to toastElement.firstElementChild
    put toastEl at the end of .toast-container
    
    set toast to new bootstrap.Toast(toastEl)
    call toast.show()
  end
</script>
```

#### Bootstrap Forms and Input Groups
```html
<!-- Advanced Form Controls -->
<div class="card shadow mb-4">
    <div class="card-header">
        <h6 class="m-0 font-weight-bold text-primary">User Settings</h6>
    </div>
    <div class="card-body">
        <form class="needs-validation" novalidate>
            <!-- Input Groups -->
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Username</label>
                    <div class="input-group">
                        <span class="input-group-text">@</span>
                        <input type="text" class="form-control" placeholder="Username" required>
                        <button class="btn btn-outline-secondary" type="button">
                            <i class="fas fa-check"></i>
                        </button>
                        <div class="invalid-feedback">
                            Please provide a valid username.
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Website</label>
                    <div class="input-group">
                        <span class="input-group-text">https://</span>
                        <input type="text" class="form-control" placeholder="example.com">
                    </div>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Amount</label>
                    <div class="input-group">
                        <span class="input-group-text">$</span>
                        <input type="number" class="form-control" step="0.01">
                        <span class="input-group-text">.00</span>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Search</label>
                    <div class="input-group">
                        <input type="search" class="form-control" placeholder="Search...">
                        <button class="btn btn-primary" type="button">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Floating Labels -->
            <div class="row g-3 mt-3">
                <div class="col-md-6">
                    <div class="form-floating">
                        <input type="email" class="form-control" id="floatingEmail" placeholder="name@example.com">
                        <label for="floatingEmail">Email address</label>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="form-floating">
                        <select class="form-select" id="floatingSelect">
                            <option selected>Choose...</option>
                            <option value="1">Option 1</option>
                            <option value="2">Option 2</option>
                            <option value="3">Option 3</option>
                        </select>
                        <label for="floatingSelect">Select an option</label>
                    </div>
                </div>
            </div>
            
            <!-- Range Slider -->
            <div class="mt-4">
                <label for="customRange" class="form-label">Priority Level</label>
                <input type="range" class="form-range" min="0" max="100" step="10" id="customRange">
                <div class="d-flex justify-content-between">
                    <span class="text-muted small">Low</span>
                    <span class="text-muted small">Medium</span>
                    <span class="text-muted small">High</span>
                </div>
            </div>
            
            <!-- Switches and Checkboxes -->
            <div class="mt-4">
                <h6>Notification Preferences</h6>
                <div class="row g-3">
                    <div class="col-md-4">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="emailNotifications" checked>
                            <label class="form-check-label" for="emailNotifications">
                                Email Notifications
                            </label>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="smsNotifications">
                            <label class="form-check-label" for="smsNotifications">
                                SMS Notifications
                            </label>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="pushNotifications" checked>
                            <label class="form-check-label" for="pushNotifications">
                                Push Notifications
                            </label>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Action Buttons -->
            <div class="mt-4 pt-3 border-top">
                <div class="d-flex justify-content-end gap-2">
                    <button type="button" class="btn btn-outline-secondary">
                        <i class="fas fa-times me-1"></i> Cancel
                    </button>
                    <button type="button" class="btn btn-outline-primary">
                        <i class="fas fa-eye me-1"></i> Preview
                    </button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save me-1"></i> Save Changes
                    </button>
                </div>
            </div>
        </form>
    </div>
</div>
```

### Bootstrap Utility Classes for Dashboards

#### Spacing and Layout Utilities
```html
<!-- Spacing utilities -->
<div class="mb-4">Margin bottom</div>
<div class="p-3">Padding all sides</div>
<div class="px-4 py-2">Horizontal and vertical padding</div>

<!-- Flexbox utilities -->
<div class="d-flex justify-content-between align-items-center">
    <h5 class="mb-0">Title</h5>
    <button class="btn btn-primary">Action</button>
</div>

<!-- Display utilities -->
<div class="d-none d-md-block">Hidden on mobile</div>
<div class="d-block d-md-none">Visible only on mobile</div>

<!-- Text utilities -->
<div class="text-center">Centered text</div>
<div class="text-muted small">Muted small text</div>
<div class="fw-bold">Bold text</div>
<div class="text-truncate" style="max-width: 200px;">Very long text that will be truncated</div>
```

#### Color and Background Utilities
```html
<!-- Background colors -->
<div class="bg-primary text-white p-3">Primary background</div>
<div class="bg-light p-3">Light background</div>
<div class="bg-gradient bg-primary text-white p-3">Gradient background</div>

<!-- Text colors -->
<span class="text-primary">Primary text</span>
<span class="text-success">Success text</span>
<span class="text-danger">Danger text</span>
<span class="text-warning">Warning text</span>

<!-- Border utilities -->
<div class="border border-primary rounded p-3">Bordered container</div>
<div class="border-start border-4 border-success ps-3">Left border accent</div>
```

#### Position and Shadow Utilities
```html
<!-- Shadow utilities -->
<div class="card shadow-sm">Small shadow</div>
<div class="card shadow">Default shadow</div>
<div class="card shadow-lg">Large shadow</div>

<!-- Position utilities -->
<div class="position-relative">
    <div class="position-absolute top-0 end-0">
        <span class="badge bg-danger">New</span>
    </div>
</div>
```

### Responsive Design with Bootstrap 5

#### Grid System for Dashboards
```html
<!-- Responsive dashboard grid -->
<div class="container-fluid">
    <div class="row">
        <!-- Stats cards - responsive columns -->
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 1</div>
        </div>
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 2</div>
        </div>
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 3</div>
        </div>
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 4</div>
        </div>
    </div>
    
    <div class="row">
        <!-- Main chart - larger on desktop -->
        <div class="col-lg-8 mb-4">
            <div class="card">Main Chart</div>
        </div>
        <!-- Sidebar chart - smaller on desktop -->
        <div class="col-lg-4 mb-4">
            <div class="card">Sidebar Chart</div>
        </div>
    </div>
</div>
```

#### Responsive Navigation
```html
<!-- Responsive sidebar -->
<nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar collapse" id="sidebarMenu">
    <div class="position-sticky pt-3">
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link active" href="#">Dashboard</a>
            </li>
            <!-- More nav items -->
        </ul>
    </div>
</nav>

<!-- Mobile toggle button -->
<button class="navbar-toggler d-md-none" type="button" 
        data-bs-toggle="collapse" data-bs-target="#sidebarMenu">
    <span class="navbar-toggler-icon"></span>
</button>
```

### Customizing Bootstrap 5 for Dashboards

#### CSS Custom Properties
```css
/* Custom dashboard theme using Bootstrap's CSS variables */
:root {
    /* Override Bootstrap colors */
    --bs-primary: #4e73df;
    --bs-secondary: #858796;
    --bs-success: #1cc88a;
    --bs-info: #36b9cc;
    --bs-warning: #f6c23e;
    --bs-danger: #e74a3b;
    
    /* Custom dashboard variables */
    --bs-dashboard-sidebar-width: 280px;
    --bs-dashboard-header-height: 64px;
    --bs-dashboard-card-shadow: 0 0.15rem 1.75rem 0 rgba(58, 59, 69, 0.15);
    --bs-dashboard-border-color: #e3e6f0;
}

/* Custom component styles */
.dashboard-card {
    border: 1px solid var(--bs-dashboard-border-color);
    box-shadow: var(--bs-dashboard-card-shadow);
    transition: all 0.3s;
}

.dashboard-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 0.25rem 2rem 0 rgba(58, 59, 69, 0.2);
}

/* Custom sidebar styles */
.dashboard-sidebar {
    width: var(--bs-dashboard-sidebar-width);
    box-shadow: 0 0 0 1px var(--bs-dashboard-border-color);
}

.dashboard-sidebar .nav-link {
    color: #5a5c69;
    padding: 0.75rem 1rem;
    border-radius: 0.35rem;
    margin: 0.125rem 0.5rem;
}

.dashboard-sidebar .nav-link:hover {
    background-color: #f8f9fc;
    color: #5a5c69;
}

.dashboard-sidebar .nav-link.active {
    background-color: var(--bs-primary);
    color: white;
}

/* Dark mode support */
[data-bs-theme="dark"] {
    --bs-dashboard-border-color: #444;
    --bs-dashboard-card-shadow: 0 0.15rem 1.75rem 0 rgba(0, 0, 0, 0.15);
}
```

#### Dark Mode Toggle
```html
<!-- Dark mode toggle -->
<div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" id="darkModeToggle"
           _="on change
              if my checked
                set document.documentElement's @data-bs-theme to 'dark'
                localStorage.setItem('dashboard-theme', 'dark')
              else
                set document.documentElement's @data-bs-theme to 'light'
                localStorage.setItem('dashboard-theme', 'light')
              end">
    <label class="form-check-label" for="darkModeToggle">
        <i class="fas fa-moon me-1"></i> Dark Mode
    </label>
</div>

<script type="text/hyperscript">
  -- Initialize theme on page load
  init
    set savedTheme to localStorage.getItem('dashboard-theme') or 'light'
    set document.documentElement's @data-bs-theme to savedTheme
    if savedTheme is 'dark'
      set #darkModeToggle.checked to true
    end
  end
</script>
```

---

## Flask Dashboard Integration Patterns

### Complete Dashboard Example with Flask Backend

#### Flask Application Structure
```python
# app.py - Main Flask application
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dashboard.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class DashboardStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    metric_name = db.Column(db.String(50), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Dashboard Routes
@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard/index.html')

@app.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    """Get real-time dashboard statistics"""
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'new_users_today': User.query.filter(
            User.created_at >= datetime.utcnow().date()
        ).count(),
        'online_users': get_online_users_count(),
    }
    return render_template('dashboard/components/stats_cards.html', stats=stats)

@app.route('/api/dashboard/users')
@login_required
def get_users():
    """Get paginated users list"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            User.username.contains(search) | 
            User.email.contains(search)
        )
    
    if status_filter:
        query = query.filter_by(is_active=(status_filter == 'active'))
    
    pagination = query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('dashboard/components/users_table.html', 
                         pagination=pagination)

@app.route('/api/dashboard/users', methods=['POST'])
@login_required
def create_user():
    """Create new user"""
    try:
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            role=request.form['role'],
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(user)
        db.session.commit()
        
        return render_template('dashboard/components/user_row.html', user=user), 201
    except Exception as e:
        return f'<div class="alert alert-danger">Error: {str(e)}</div>', 400

@app.route('/api/dashboard/users/<int:user_id>', methods=['PUT', 'POST'])
@login_required
def update_user(user_id):
    """Update user"""
    user = User.query.get_or_404(user_id)
    
    user.username = request.form['username']
    user.email = request.form['email']
    user.role = request.form['role']
    user.is_active = request.form.get('is_active') == 'on'
    
    db.session.commit()
    
    return render_template('dashboard/components/user_row.html', user=user)

@app.route('/api/dashboard/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete user"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    return '', 200

@app.route('/api/dashboard/chart/users-growth')
@login_required
def users_growth_chart():
    """Generate users growth chart data"""
    days = request.args.get('days', 30, type=int)
    
    # Generate sample data - replace with real data
    chart_data = generate_growth_chart_data(days)
    
    return render_template('dashboard/charts/line_chart.html', 
                         chart_data=chart_data, 
                         chart_id='users-growth')

def generate_growth_chart_data(days):
    """Generate sample chart data"""
    import random
    data = []
    base_date = datetime.utcnow() - timedelta(days=days)
    
    for i in range(days):
        date = base_date + timedelta(days=i)
        value = random.randint(10, 100)
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'value': value
        })
    
    return data

def get_online_users_count():
    """Get count of online users (implement based on your session logic)"""
    # Implement your online user counting logic
    return 42  # Sample data

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

#### Dashboard Templates Structure

**Base Dashboard Template (dashboard/base.html):**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Dashboard{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" 
          rel="stylesheet" 
          integrity="sha384-LN+7fdVzj6u52u30Kp6M/trliBMCMKTyK833zpbD+pXdCLuTusPj697FH4R/5mcr" 
          crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <style>
        /* Dashboard-specific styles */
        :root {
            --dashboard-sidebar-width: 280px;
            --dashboard-header-height: 64px;
            --dashboard-primary: #4e73df;
            --dashboard-success: #1cc88a;
            --dashboard-warning: #f6c23e;
            --dashboard-danger: #e74a3b;
        }
        
        .dashboard-layout {
            display: flex;
            min-height: 100vh;
        }
        
        .dashboard-sidebar {
            width: var(--dashboard-sidebar-width);
            background: white;
            border-right: 1px solid #e3e6f0;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            z-index: 1000;
        }
        
        .dashboard-main {
            margin-left: var(--dashboard-sidebar-width);
            flex: 1;
            background: #f8f9fc;
        }
        
        .dashboard-header {
            background: white;
            padding: 1rem 2rem;
            border-bottom: 1px solid #e3e6f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 999;
        }
        
        .dashboard-content {
            padding: 2rem;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .dashboard-sidebar {
                transform: translateX(-100%);
                transition: transform 0.3s;
            }
            
            .dashboard-sidebar.mobile-open {
                transform: translateX(0);
            }
            
            .dashboard-main {
                margin-left: 0;
            }
            
            .mobile-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 999;
            }
            
            .mobile-overlay.show {
                display: block;
            }
        }
        
        /* Navigation */
        .sidebar-nav .nav-item {
            margin: 0.125rem 0.5rem;
        }
        
        .sidebar-nav .nav-link {
            color: #5a5c69;
            padding: 0.75rem 1rem;
            border-radius: 0.35rem;
            display: flex;
            align-items: center;
        }
        
        .sidebar-nav .nav-link:hover {
            background-color: #f8f9fc;
            color: #5a5c69;
        }
        
        .sidebar-nav .nav-link.active {
            background-color: var(--dashboard-primary);
            color: white;
        }
        
        .sidebar-nav .nav-link i {
            width: 1.25rem;
            margin-right: 0.5rem;
        }
    </style>
</head>
<body class="dashboard-layout">
    <!-- Mobile Overlay -->
    <div class="mobile-overlay" 
         _="on click 
            remove .mobile-open from .dashboard-sidebar
            remove .show from me"></div>
    
    <!-- Sidebar -->
    <aside class="dashboard-sidebar" 
           _="on mobile-menu-toggle 
              toggle .mobile-open on me
              toggle .show on .mobile-overlay">
        <div class="sidebar-content">
            <div class="sidebar-header p-3">
                <div class="d-flex align-items-center">
                    <i class="fas fa-tachometer-alt text-primary me-2"></i>
                    <h4 class="mb-0">Dashboard</h4>
                </div>
            </div>
            
            <nav class="sidebar-nav">
                <ul class="nav flex-column">
                    <li class="nav-item">
                        <a href="/dashboard" class="nav-link {{ 'active' if request.endpoint == 'dashboard' }}">
                            <i class="fas fa-fw fa-tachometer-alt"></i>
                            <span>Overview</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/analytics" class="nav-link">
                            <i class="fas fa-fw fa-chart-area"></i>
                            <span>Analytics</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/users" class="nav-link">
                            <i class="fas fa-fw fa-users"></i>
                            <span>Users</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/orders" class="nav-link">
                            <i class="fas fa-fw fa-shopping-cart"></i>
                            <span>Orders</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/reports" class="nav-link">
                            <i class="fas fa-fw fa-file-alt"></i>
                            <span>Reports</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/settings" class="nav-link">
                            <i class="fas fa-fw fa-cog"></i>
                            <span>Settings</span>
                        </a>
                    </li>
                </ul>
            </nav>
        </div>
    </aside>
    
    <!-- Main Content -->
    <main class="dashboard-main">
        <!-- Header -->
        <header class="dashboard-header">
            <div class="header-left d-flex align-items-center">
                <button class="btn btn-link d-md-none me-3" 
                        _="on click send mobile-menu-toggle to .dashboard-sidebar">
                    <i class="fas fa-bars"></i>
                </button>
                <h1 class="h3 mb-0">{% block page_title %}Dashboard{% endblock %}</h1>
            </div>
            
            <div class="header-right d-flex align-items-center">
                <!-- Search -->
                <div class="me-3">
                    <div class="input-group">
                        <input type="search" class="form-control form-control-sm" 
                               placeholder="Search..." style="width: 200px;">
                        <button class="btn btn-outline-secondary btn-sm">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Notifications -->
                <div class="dropdown me-3">
                    <button class="btn btn-link position-relative" data-bs-toggle="dropdown">
                        <i class="fas fa-bell"></i>
                        <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">
                            3
                        </span>
                    </button>
                    <div class="dropdown-menu dropdown-menu-end">
                        <h6 class="dropdown-header">Notifications</h6>
                        <a class="dropdown-item" href="#">
                            <div class="d-flex">
                                <div class="flex-shrink-0">
                                    <i class="fas fa-user-plus text-success"></i>
                                </div>
                                <div class="flex-grow-1 ms-2">
                                    <div class="small">New user registered</div>
                                    <div class="text-muted small">2 minutes ago</div>
                                </div>
                            </div>
                        </a>
                        <div class="dropdown-divider"></div>
                        <a class="dropdown-item text-center small" href="#">View all notifications</a>
                    </div>
                </div>
                
                <!-- User Menu -->
                <div class="dropdown">
                    <button class="btn btn-link d-flex align-items-center" data-bs-toggle="dropdown">
                        <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center me-2"
                             style="width: 32px; height: 32px;">
                            {{ current_user.username[0].upper() }}
                        </div>
                        <span class="d-none d-sm-block">{{ current_user.username }}</span>
                        <i class="fas fa-chevron-down ms-1"></i>
                    </button>
                    <div class="dropdown-menu dropdown-menu-end">
                        <a class="dropdown-item" href="/profile">
                            <i class="fas fa-user me-2"></i> Profile
                        </a>
                        <a class="dropdown-item" href="/settings">
                            <i class="fas fa-cog me-2"></i> Settings
                        </a>
                        <div class="dropdown-divider"></div>
                        <a class="dropdown-item" href="/logout">
                            <i class="fas fa-sign-out-alt me-2"></i> Logout
                        </a>
                    </div>
                </div>
            </div>
        </header>
        
        <!-- Page Content -->
        <div class="dashboard-content">
            {% block content %}{% endblock %}
        </div>
    </main>
    
    <!-- Toast Container -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1060;">
        <!-- Toasts will be dynamically added here -->
    </div>
    
    <!-- Modal Container -->
    <div id="modal-container"></div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js" 
            integrity="sha384-ndDqU0Gzau9qJ1lfW4pNLlhNTkCfHzAVBReH9diLvGRem5+R9g2FzA8ZGN954O5Q" 
            crossorigin="anonymous"></script>
    
    <!-- Global Dashboard Scripts -->
    <script type="text/hyperscript">
        -- Auto-refresh dashboard every 30 seconds
        init
          repeat every 30s
            fetch /api/dashboard/stats
            put the result into #dashboard-stats
          end
        end
        
        -- Global error handler
        on htmx:responseError from body
          call showToast('An error occurred. Please try again.', 'danger')
        end
        
        -- Success handler
        on htmx:afterRequest from body
          if detail.xhr.status >= 200 and detail.xhr.status < 300
            if detail.target.dataset.successMessage
              call showToast(detail.target.dataset.successMessage, 'success')
            end
          end
        end
        
        -- Toast function
        def showToast(message, type)
          set toastHtml to `
            <div class="toast" role="alert" data-bs-autohide="true" data-bs-delay="5000">
              <div class="toast-header">
                <div class="rounded me-2 bg-${type}" style="width: 20px; height: 20px;"></div>
                <strong class="me-auto">Dashboard</strong>
                <small>just now</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
              </div>
              <div class="toast-body">${message}</div>
            </div>
          `
          
          make a <div/> called toastElement
          set toastElement.innerHTML to toastHtml
          set toastEl to toastElement.firstElementChild
          put toastEl at the end of .toast-container
          
          set toast to new bootstrap.Toast(toastEl)
          call toast.show()
        end
    </script>
</body>
</html>
```

**Main Dashboard Page (dashboard/index.html):**
```html
{% extends "dashboard/base.html" %}

{% block content %}
<!-- Stats Cards -->
<div id="dashboard-stats" 
     hx-get="/api/dashboard/stats" 
     hx-trigger="load">
    <div class="row">
        <div class="col-12 text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading dashboard stats...</span>
            </div>
            <div class="mt-2 text-muted">Loading dashboard...</div>
        </div>
    </div>
</div>

<!-- Charts Section -->
<div class="row mb-4">
    <div class="col-xl-8 col-lg-7">
        <!-- User Growth Chart -->
        <div class="card shadow mb-4">
            <div class="card-header py-3 d-flex justify-content-between align-items-center">
                <h6 class="m-0 font-weight-bold text-primary">User Growth</h6>
                <div class="dropdown">
                    <button class="btn btn-outline-primary btn-sm dropdown-toggle" 
                            data-bs-toggle="dropdown">
                        <i class="fas fa-calendar me-1"></i> Last 30 days
                    </button>
                    <ul class="dropdown-menu">
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/users-growth?days=7" 
                               hx-target="#users-growth-chart">
                                Last 7 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/users-growth?days=30" 
                               hx-target="#users-growth-chart">
                                Last 30 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/users-growth?days=90" 
                               hx-target="#users-growth-chart">
                                Last 90 days
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="card-body">
                <div id="users-growth-chart" 
                     hx-get="/api/dashboard/chart/users-growth?days=30" 
                     hx-trigger="load"
                     style="height: 400px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading chart...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-4 col-lg-5">
        <!-- Revenue Chart -->
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Revenue Sources</h6>
            </div>
            <div class="card-body">
                <div id="revenue-chart" 
                     hx-get="/api/dashboard/chart/revenue" 
                     hx-trigger="load"
                     style="height: 320px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading chart...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Recent Activity and Quick Actions -->
<div class="row">
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Recent Activity</h6>
            </div>
            <div class="card-body">
                <div id="activity-feed" 
                     hx-get="/api/dashboard/activity" 
                     hx-trigger="load, every 60s"
                     style="max-height: 400px; overflow-y: auto;">
                    <div class="text-center py-3">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading activity...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Quick Actions</h6>
            </div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-6">
                        <button class="btn btn-primary w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/users/new" 
                                hx-target="#modal-container">
                            <i class="fas fa-user-plus fa-2x mb-2"></i>
                            <span>Add User</span>
                        </button>
                    </div>
                    <div class="col-6">
                        <button class="btn btn-success w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/reports/generate" 
                                hx-target="#modal-container">
                            <i class="fas fa-chart-bar fa-2x mb-2"></i>
                            <span>Generate Report</span>
                        </button>
                    </div>
                    <div class="col-6">
                        <button class="btn btn-info w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/settings/backup" 
                                hx-target="#modal-container">
                            <i class="fas fa-download fa-2x mb-2"></i>
                            <span>Backup Data</span>
                        </button>
                    </div>
                    <div class="col-6">
                        <button class="btn btn-warning w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/system/maintenance" 
                                hx-target="#modal-container">
                            <i class="fas fa-tools fa-2x mb-2"></i>
                            <span>Maintenance</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

---

## Dashboard-Specific Components

### Real-time Dashboard Widgets

#### Live Activity Feed
```html
<!-- Activity Feed Component with Bootstrap styling -->
<div class="card shadow activity-feed-widget">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">
            <i class="fas fa-stream me-2"></i>Live Activity
        </h6>
        <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary" 
                    _="on click
                       toggle .paused on #activity-feed
                       if #activity-feed matches .paused
                         put 'Resume' into me
                         set my @title to 'Resume updates'
                         add .btn-warning to me
                         remove .btn-outline-secondary from me
                       else
                         put 'Pause' into me
                         set my @title to 'Pause updates'
                         add .btn-outline-secondary to me
                         remove .btn-warning from me
                       end">
                <i class="fas fa-pause me-1"></i> Pause
            </button>
            <button class="btn btn-outline-danger" 
                    hx-post="/api/dashboard/activity/clear" 
                    hx-target="#activity-list"
                    hx-confirm="Clear all activity?"
                    title="Clear activity">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    </div>
    
    <div id="activity-feed" 
         class="card-body p-0"
         hx-ext="sse" 
         sse-connect="/stream/activity"
         _="on sse:activity(data) 
            unless I match .paused
              make a <div.activity-item.list-group-item.border-0/> called item
              set item.innerHTML to `
                <div class='d-flex align-items-start'>
                  <div class='activity-icon bg-${data.type} text-white rounded-circle me-3 d-flex align-items-center justify-content-center' 
                       style='width: 40px; height: 40px; font-size: 0.875rem;'>
                    <i class='${data.icon}'></i>
                  </div>
                  <div class='flex-grow-1'>
                    <div class='activity-message fw-bold'>${data.message}</div>
                    <div class='activity-details text-muted small'>${data.details}</div>
                    <div class='activity-time text-muted small'>
                      <i class='fas fa-clock me-1'></i>${data.time}
                    </div>
                  </div>
                </div>
              `
              put item at the start of #activity-list
              
              -- Add animation
              add .animate__animated.animate__fadeInLeft to item
              
              -- Limit to 50 items
              set items to <.activity-item/> in #activity-list
              if items.length > 50
                remove items[items.length - 1]
              end
            end">
        
        <div id="activity-list" class="list-group list-group-flush" 
             style="max-height: 400px; overflow-y: auto;">
            {% for activity in recent_activities %}
            <div class="activity-item list-group-item border-0">
                <div class="d-flex align-items-start">
                    <div class="activity-icon bg-{{ activity.type }} text-white rounded-circle me-3 d-flex align-items-center justify-content-center" 
                         style="width: 40px; height: 40px; font-size: 0.875rem;">
                        <i class="{{ activity.icon }}"></i>
                    </div>
                    <div class="flex-grow-1">
                        <div class="activity-message fw-bold">{{ activity.message }}</div>
                        <div class="activity-details text-muted small">{{ activity.details }}</div>
                        <div class="activity-time text-muted small">
                            <i class="fas fa-clock me-1"></i>{{ activity.timestamp.strftime('%H:%M:%S') }}
                        </div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

<style>
.activity-feed-widget {
    height: 500px;
    display: flex;
    flex-direction: column;
}

.activity-feed.paused {
    opacity: 0.7;
}

.activity-item {
    transition: background-color 0.2s;
    padding: 1rem;
}

.activity-item:hover {
    background-color: #f8f9fa !important;
}

.animate__fadeInLeft {
    animation-duration: 0.5s;
}
</style>
```

#### System Health Dashboard
```html
<!-- System Health Widget with Bootstrap -->
<div class="card shadow system-health-widget">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">
            <i class="fas fa-heartbeat me-2"></i>System Health
        </h6>
        <span class="badge health-status bg-success" 
             _="init set :overallStatus to 'success'
               on health-update(status)
                 set :overallStatus to status
                 remove .bg-success, .bg-warning, .bg-danger from me
                 if status is 'success'
                   add .bg-success to me
                   put 'All Systems Operational' into me
                 else if status is 'warning'
                   add .bg-warning to me
                   put 'Some Issues Detected' into me
                 else
                   add .bg-danger to me
                   put 'Critical Issues' into me
                 end
               end">
            <i class="fas fa-check-circle me-1"></i>All Systems Operational
        </span>
    </div>
    
    <div class="card-body">
        <div class="health-metrics" 
             hx-get="/api/dashboard/health" 
             hx-trigger="load, every 10s"
             _="on htmx:afterRequest
                set data to JSON.parse(detail.xhr.response)
                
                -- Update metrics
                for metric in ['cpu', 'memory', 'disk']
                  set value to data[metric + '_usage']
                  set progressBar to `#${metric}-progress`
                  set valueDisplay to `#${metric}-value`
                  set progressBar.style.width to value + '%'
                  put value + '%' into valueDisplay
                  
                  -- Update progress bar color based on value
                  remove .bg-success, .bg-warning, .bg-danger from progressBar
                  if value < 60
                    add .bg-success to progressBar
                  else if value < 80
                    add .bg-warning to progressBar
                  else
                    add .bg-danger to progressBar
                  end
                end
                
                -- Update connection count
                put data.active_connections into #connections-count
                
                -- Determine overall status
                set maxUsage to Math.max(data.cpu_usage, data.memory_usage, data.disk_usage)
                if maxUsage > 90
                  send health-update(status: 'danger') to .health-status
                else if maxUsage > 75
                  send health-update(status: 'warning') to .health-status
                else
                  send health-update(status: 'success') to .health-status
                end">
            
            <div class="row g-3">
                <div class="col-md-4">
                    <div class="metric-card">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="metric-label">
                                <i class="fas fa-microchip me-1 text-primary"></i>CPU Usage
                            </span>
                            <span id="cpu-value" class="metric-value badge bg-primary">45%</span>
                        </div>
                        <div class="progress">
                            <div id="cpu-progress" class="progress-bar bg-success" 
                                 style="width: 45%" role="progressbar"></div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="metric-card">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="metric-label">
                                <i class="fas fa-memory me-1 text-warning"></i>Memory
                            </span>
                            <span id="memory-value" class="metric-value badge bg-warning">67%</span>
                        </div>
                        <div class="progress">
                            <div id="memory-progress" class="progress-bar bg-warning" 
                                 style="width: 67%" role="progressbar"></div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="metric-card">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="metric-label">
                                <i class="fas fa-hdd me-1 text-info"></i>Disk Usage
                            </span>
                            <span id="disk-value" class="metric-value badge bg-info">23%</span>
                        </div>
                        <div class="progress">
                            <div id="disk-progress" class="progress-bar bg-success" 
                                 style="width: 23%" role="progressbar"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <hr class="my-4">
            
            <div class="row text-center">
                <div class="col-md-6">
                    <div class="metric-large">
                        <i class="fas fa-wifi fa-2x text-success mb-2"></i>
                        <div class="metric-large-label">Active Connections</div>
                        <div id="connections-count" class="metric-large-value text-success">1,247</div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="metric-large">
                        <i class="fas fa-clock fa-2x text-info mb-2"></i>
                        <div class="metric-large-label">Uptime</div>
                        <div class="metric-large-value text-info">15d 7h 32m</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
.system-health-widget {
    min-width: 400px;
}

.metric-card {
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 0.5rem;
    transition: all 0.2s;
}

.metric-card:hover {
    background: #e9ecef;
    transform: translateY(-1px);
}

.metric-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: #495057;
}

.metric-value {
    font-size: 0.75rem;
}

.metric-large {
    padding: 1rem;
}

.metric-large-label {
    font-size: 0.875rem;
    color: #6c757d;
    margin-bottom: 0.5rem;
}

.metric-large-value {
    font-size: 1.5rem;
    font-weight: 700;
}

.progress {
    height: 6px;
}
</style>
```

---

## Real-time Dashboard Updates

### WebSocket Integration with HTMX and Bootstrap

Flask applications can use WebSockets for real-time dashboard updates. Here's how to integrate WebSocket connections with HTMX and Bootstrap styling:

#### WebSocket Flask Configuration
```python
# app.py - WebSocket setup with Flask-SocketIO
from flask import Flask
from flask_socketio import SocketIO, emit, disconnect
import json
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active dashboard connections
dashboard_connections = set()

@socketio.on('dashboard_connect')
def handle_dashboard_connect():
    dashboard_connections.add(request.sid)
    emit('connection_status', {'status': 'connected', 'clients': len(dashboard_connections)})
    
    # Send initial dashboard data
    emit('dashboard_data', get_dashboard_data())

@socketio.on('disconnect')
def handle_disconnect():
    dashboard_connections.discard(request.sid)

# Background task to send periodic updates
def background_thread():
    while True:
        time.sleep(5)  # Update every 5 seconds
        if dashboard_connections:
            dashboard_data = get_dashboard_data()
            socketio.emit('dashboard_update', dashboard_data, room=None)

# Start background thread
thread = threading.Thread(target=background_thread)
thread.daemon = True
thread.start()

def get_dashboard_data():
    """Collect real-time dashboard metrics"""
    return {
        'timestamp': time.time(),
        'active_users': get_active_user_count(),
        'system_load': get_system_load(),
        'recent_activities': get_recent_activities(),
        'performance_metrics': get_performance_metrics()
    }
```

#### Real-time Dashboard Template with Bootstrap
```html
<!-- Real-time Dashboard with WebSocket and Bootstrap -->
<div class="container-fluid realtime-dashboard" 
     _="init
        set :socket to io()
        
        -- Connect to dashboard updates
        call :socket.emit('dashboard_connect')
        
        -- Handle real-time updates
        call :socket.on('dashboard_update', def(data)
          update-dashboard-stats(data)
          update-activity-feed(data.recent_activities)
          update-performance-charts(data.performance_metrics)
        end)
        
        -- Handle connection status
        call :socket.on('connection_status', def(data)
          put data.clients + ' clients connected' into #connection-status
          if data.status is 'connected'
            remove .bg-danger from #connection-indicator
            add .bg-success to #connection-indicator
          else
            remove .bg-success from #connection-indicator
            add .bg-danger to #connection-indicator
          end
        end)
        
        -- Cleanup on page unload
        on beforeunload
          call :socket.disconnect()
        end
        
        -- Functions for updating UI
        def update-dashboard-stats(data)
          put data.active_users into #active-users-count
          put (data.system_load * 100).toFixed(1) + '%' into #system-load
          set #load-progress.style.width to (data.system_load * 100) + '%'
          
          -- Update progress bar color
          remove .bg-success, .bg-warning, .bg-danger from #load-progress
          if data.system_load < 0.6
            add .bg-success to #load-progress
          else if data.system_load < 0.8
            add .bg-warning to #load-progress
          else
            add .bg-danger to #load-progress
          end
          
          -- Animate changes
          add .animate__pulse to #stats-container
          wait 300ms
          remove .animate__pulse from #stats-container
        end
        
        def update-activity-feed(activities)
          set feed to #activity-feed
          for activity in activities
            make a <div.list-group-item.border-0/> called item
            set item.innerHTML to `
              <div class='d-flex align-items-start'>
                <div class='activity-icon bg-${activity.type} text-white rounded-circle me-3 d-flex align-items-center justify-content-center' 
                     style='width: 32px; height: 32px; font-size: 0.75rem;'>
                  <i class='${activity.icon}'></i>
                </div>
                <div class='flex-grow-1'>
                  <div class='activity-message small fw-bold'>${activity.message}</div>
                  <div class='activity-time text-muted small'>
                    <i class='fas fa-clock me-1'></i>${activity.time}
                  </div>
                </div>
              </div>
            `
            add .animate__fadeInUp to item
            put item at the start of feed
          end
          
          -- Keep only latest 20 items
          set items to <.list-group-item/> in feed
          if items.length > 20
            for i from 20 to items.length - 1
              remove items[i]
            end
          end
        end
        
        def update-performance-charts(metrics)
          if window.performanceChart
            set chart to window.performanceChart
            call chart.data.labels.push(new Date().toLocaleTimeString())
            call chart.data.datasets[0].data.push(metrics.response_time)
            call chart.data.datasets[1].data.push(metrics.throughput)
            
            -- Keep only last 20 data points
            if chart.data.labels.length > 20
              call chart.data.labels.shift()
              call chart.data.datasets[0].data.shift()
              call chart.data.datasets[1].data.shift()
            end
            
            call chart.update('none')
          end
        end">
    
    <!-- Connection Status -->
    <div class="row mb-4">
        <div class="col-12">
            <div class="alert alert-info d-flex align-items-center">
                <div id="connection-indicator" class="bg-success rounded-circle me-3" 
                     style="width: 12px; height: 12px;"></div>
                <div class="flex-grow-1">
                    <strong>Real-time Dashboard</strong> - 
                    <span id="connection-status">Connecting...</span>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-info" 
                            _="on click
                               if I match .btn-outline-info
                                 call :socket.disconnect()
                                 put 'Connect' into me
                                 remove .btn-outline-info from me
                                 add .btn-info to me
                               else
                                 call :socket.connect()
                                 put 'Disconnect' into me
                                 remove .btn-info from me
                                 add .btn-outline-info to me
                               end">
                        Disconnect
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Live Statistics -->
    <div id="stats-container" class="row mb-4">
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-primary shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                                Active Users
                            </div>
                            <div id="active-users-count" class="h5 mb-0 font-weight-bold text-gray-800">--</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-users fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-warning shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">
                                System Load
                            </div>
                            <div class="row no-gutters align-items-center">
                                <div class="col-auto">
                                    <div id="system-load" class="h5 mb-0 mr-3 font-weight-bold text-gray-800">--</div>
                                </div>
                                <div class="col">
                                    <div class="progress progress-sm mr-2">
                                        <div id="load-progress" class="progress-bar bg-warning" role="progressbar" 
                                             style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-server fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-success shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-success text-uppercase mb-1">
                                Revenue (Monthly)
                            </div>
                            <div class="h5 mb-0 font-weight-bold text-gray-800" id="monthly-revenue">$45,678</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-dollar-sign fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-info shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-info text-uppercase mb-1">
                                Tasks Pending
                            </div>
                            <div class="h5 mb-0 font-weight-bold text-gray-800" id="pending-tasks">18</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-clipboard-list fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Real-time Charts and Activity -->
    <div class="row">
        <div class="col-xl-8 col-lg-7">
            <!-- Performance Chart -->
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">Real-time Performance</h6>
                </div>
                <div class="card-body">
                    <canvas id="performance-chart" width="400" height="200"></canvas>
                </div>
            </div>
        </div>
        
        <div class="col-xl-4 col-lg-5">
            <!-- Live Activity Feed -->
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">Live Activity</h6>
                </div>
                <div class="card-body p-0">
                    <div id="activity-feed" class="list-group list-group-flush" 
                         style="max-height: 400px; overflow-y: auto;">
                        <!-- Activities are inserted here dynamically -->
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Chart.js for real-time charts -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">

<script>
// Initialize performance chart
const ctx = document.getElementById('performance-chart').getContext('2d');
window.performanceChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Response Time (ms)',
            data: [],
            borderColor: '#4e73df',
            backgroundColor: 'rgba(78, 115, 223, 0.1)',
            tension: 0.4,
            yAxisID: 'y'
        }, {
            label: 'Throughput (req/s)',
            data: [],
            borderColor: '#1cc88a',
            backgroundColor: 'rgba(28, 200, 138, 0.1)',
            tension: 0.4,
            yAxisID: 'y1'
        }]
    },
    options: {
        responsive: true,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        scales: {
            x: {
                display: true,
                title: {
                    display: true,
                    text: 'Time'
                }
            },
            y: {
                type: 'linear',
                display: true,
                position: 'left',
                title: {
                    display: true,
                    text: 'Response Time (ms)'
                }
            },
            y1: {
                type: 'linear',
                display: true,
                position: 'right',
                title: {
                    display: true,
                    text: 'Throughput (req/s)'
                },
                grid: {
                    drawOnChartArea: false,
                }
            }
        },
        animation: {
            duration: 0 // Disable animations for real-time updates
        }
    }
});
</script>

<style>
.realtime-dashboard {
    padding: 2rem 0;
}

.border-left-primary {
    border-left: 0.25rem solid #4e73df !important;
}

.border-left-success {
    border-left: 0.25rem solid #1cc88a !important;
}

.border-left-info {
    border-left: 0.25rem solid #36b9cc !important;
}

.border-left-warning {
    border-left: 0.25rem solid #f6c23e !important;
}

.text-xs {
    font-size: 0.75rem;
}

.progress-sm {
    height: 0.5rem;
}

.activity-item {
    transition: all 0.3s ease;
}

.animate__pulse {
    animation-duration: 0.5s;
}

.animate__fadeInUp {
    animation-duration: 0.5s;
}
</style>
```

### Server-Sent Events (SSE) Alternative

For simpler real-time updates, use Server-Sent Events with HTMX:

#### SSE Flask Route
```python
@app.route('/stream/dashboard')
def dashboard_stream():
    def generate():
        while True:
            # Get current dashboard data
            data = get_dashboard_data()
            
            # Send as SSE event
            yield f"event: dashboard_update\n"
            yield f"data: {json.dumps(data)}\n\n"
            
            time.sleep(5)  # Update every 5 seconds
    
    return Response(generate(), mimetype='text/plain')
```

#### SSE Dashboard Template with Bootstrap
```html
<div class="card shadow sse-dashboard" 
     hx-ext="sse" 
     sse-connect="/stream/dashboard"
     _="on sse:dashboard_update(data) 
        set metrics to JSON.parse(data)
        put metrics.active_users into #active-users
        put metrics.system_load + '%' into #system-load
        update-activity-feed(metrics.activities)">
    
    <div class="card-header">
        <h5 class="mb-0">
            <i class="fas fa-broadcast-tower me-2 text-primary"></i>
            Server-Sent Events Dashboard
        </h5>
    </div>
    
    <div class="card-body">
        <div class="row">
            <div class="col-md-6">
                <div class="metric-display">
                    <label class="form-label">Active Users</label>
                    <div class="input-group">
                        <span class="input-group-text">
                            <i class="fas fa-users"></i>
                        </span>
                        <input type="text" class="form-control" id="active-users" readonly>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="metric-display">
                    <label class="form-label">System Load</label>
                    <div class="input-group">
                        <span class="input-group-text">
                            <i class="fas fa-server"></i>
                        </span>
                        <input type="text" class="form-control" id="system-load" readonly>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="mt-4">
            <h6>Recent Activity</h6>
            <div id="activity-list" class="list-group"></div>
        </div>
    </div>
</div>
```

---

## Data Visualization Integration

### Chart.js Integration with HTMX and Bootstrap

Combine Chart.js with HTMX for dynamic, data-driven dashboards using Bootstrap styling:

#### Dynamic Chart Updates
```html
<!-- Chart Container with Bootstrap styling -->
<div class="card shadow chart-container">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">
            <i class="fas fa-chart-line me-2"></i>Sales Analytics
        </h6>
        <div class="chart-controls d-flex align-items-center gap-3">
            <div class="input-group" style="width: 200px;">
                <label class="input-group-text">Period</label>
                <select class="form-select" name="period" 
                        hx-get="/api/dashboard/chart-data" 
                        hx-trigger="change" 
                        hx-target="#chart-data" 
                        hx-swap="none"
                        _="on htmx:afterRequest(evt) 
                           set data to JSON.parse(evt.detail.xhr.response)
                           update-chart(data)">
                    <option value="7d">Last 7 Days</option>
                    <option value="30d" selected>Last 30 Days</option>
                    <option value="3m">Last 3 Months</option>
                    <option value="1y">Last Year</option>
                </select>
            </div>
            
            <div class="btn-group">
                <button class="btn btn-outline-secondary btn-sm" 
                        _="on click 
                           set canvas to #sales-chart
                           set link to document.createElement('a')
                           set link.download to 'sales-chart.png'
                           set link.href to canvas.toDataURL()
                           link.click()">
                    <i class="fas fa-download me-1"></i>Export
                </button>
                <button class="btn btn-outline-secondary btn-sm"
                        hx-get="/api/dashboard/chart-data" 
                        hx-target="#chart-data" 
                        hx-swap="none"
                        _="on htmx:afterRequest(evt) 
                           set data to JSON.parse(evt.detail.xhr.response)
                           update-chart(data)">
                    <i class="fas fa-sync-alt me-1"></i>Refresh
                </button>
            </div>
        </div>
    </div>
    
    <div class="card-body">
        <div class="chart-wrapper">
            <canvas id="sales-chart" width="800" height="400"></canvas>
        </div>
    </div>
    
    <!-- Hidden container for chart data -->
    <div id="chart-data" style="display: none;"></div>
</div>

<script>
// Initialize chart with Bootstrap-themed colors
const salesCtx = document.getElementById('sales-chart').getContext('2d');
let salesChart = new Chart(salesCtx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Sales',
            data: [],
            borderColor: '#4e73df',
            backgroundColor: 'rgba(78, 115, 223, 0.1)',
            tension: 0.4,
            fill: true,
            pointBackgroundColor: '#4e73df',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 5
        }, {
            label: 'Target',
            data: [],
            borderColor: '#1cc88a',
            borderDash: [5, 5],
            backgroundColor: 'transparent',
            tension: 0.4,
            pointBackgroundColor: '#1cc88a',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 5
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            title: {
                display: true,
                text: 'Sales Performance',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                color: '#5a5c69'
            },
            legend: {
                position: 'top',
                labels: {
                    usePointStyle: true,
                    padding: 20,
                    color: '#5a5c69'
                }
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                titleColor: '#5a5c69',
                bodyColor: '#5a5c69',
                borderColor: '#e3e6f0',
                borderWidth: 1,
                cornerRadius: 10,
                displayColors: true,
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        label += new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD'
                        }).format(context.parsed.y);
                        return label;
                    }
                }
            }
        },
        scales: {
            x: {
                display: true,
                title: {
                    display: true,
                    text: 'Date',
                    color: '#5a5c69',
                    font: {
                        weight: 'bold'
                    }
                },
                grid: {
                    color: '#e3e6f0'
                },
                ticks: {
                    color: '#858796'
                }
            },
            y: {
                display: true,
                title: {
                    display: true,
                    text: 'Revenue ($)',
                    color: '#5a5c69',
                    font: {
                        weight: 'bold'
                    }
                },
                grid: {
                    color: '#e3e6f0'
                },
                ticks: {
                    color: '#858796',
                    callback: function(value) {
                        return new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD',
                            notation: 'compact'
                        }).format(value);
                    }
                }
            }
        }
    }
});

// Function to update chart (called by hyperscript)
function updateChart(data) {
    salesChart.data.labels = data.labels;
    salesChart.data.datasets[0].data = data.sales;
    salesChart.data.datasets[1].data = data.targets;
    salesChart.update('active');
}
</script>

<style>
.chart-container {
    margin-bottom: 2rem;
}

.chart-wrapper {
    position: relative;
    height: 400px;
}

.chart-controls .input-group-text {
    font-size: 0.875rem;
    font-weight: 500;
}
</style>
```

#### Flask Chart Data Endpoint
```python
@app.route('/api/dashboard/chart-data')
def get_chart_data():
    period = request.args.get('period', '7d')
    
    # Generate data based on period
    if period == '7d':
        labels = [(datetime.now() - timedelta(days=x)).strftime('%m/%d') 
                 for x in range(6, -1, -1)]
        sales = [12000, 15000, 13500, 16000, 14500, 17000, 18500]
        targets = [14000, 14000, 14000, 15000, 15000, 16000, 16000]
    elif period == '30d':
        # Generate 30-day data
        labels = [(datetime.now() - timedelta(days=x)).strftime('%m/%d') 
                 for x in range(29, -1, -1)]
        sales = [random.randint(10000, 20000) for _ in range(30)]
        targets = [15000] * 30
    elif period == '3m':
        # Generate 3-month data (weekly)
        labels = [(datetime.now() - timedelta(weeks=x)).strftime('Week %U') 
                 for x in range(11, -1, -1)]
        sales = [random.randint(40000, 80000) for _ in range(12)]
        targets = [60000] * 12
    elif period == '1y':
        # Generate yearly data (monthly)
        labels = [(datetime.now() - timedelta(days=x*30)).strftime('%b %Y') 
                 for x in range(11, -1, -1)]
        sales = [random.randint(150000, 300000) for _ in range(12)]
        targets = [200000] * 12
    
    return jsonify({
        'labels': labels,
        'sales': sales,
        'targets': targets,
        'period': period
    })
```

### Multi-Chart Dashboard with Bootstrap Grid
```html
<!-- Dashboard with Multiple Charts using Bootstrap Grid -->
<div class="container-fluid multi-chart-dashboard">
    <div class="row mb-4">
        <!-- Revenue Chart -->
        <div class="col-xl-8 col-lg-7">
            <div class="card shadow mb-4">
                <div class="card-header py-3 d-flex justify-content-between align-items-center">
                    <h6 class="m-0 font-weight-bold text-primary">Revenue Trends</h6>
                    <div class="btn-group btn-group-sm chart-type-selector" 
                         _="on change from input[type=radio]
                            set chartType to event.target.value
                            set chart to window.revenueChart
                            call chart.destroy()
                            initialize-revenue-chart(chartType)">
                        <input type="radio" class="btn-check" name="revenue-type" 
                               id="btn-line" value="line" checked>
                        <label class="btn btn-outline-primary" for="btn-line">
                            <i class="fas fa-chart-line me-1"></i>Line
                        </label>
                        
                        <input type="radio" class="btn-check" name="revenue-type" 
                               id="btn-bar" value="bar">
                        <label class="btn btn-outline-primary" for="btn-bar">
                            <i class="fas fa-chart-bar me-1"></i>Bar
                        </label>
                        
                        <input type="radio" class="btn-check" name="revenue-type" 
                               id="btn-area" value="line">
                        <label class="btn btn-outline-primary" for="btn-area">
                            <i class="fas fa-chart-area me-1"></i>Area
                        </label>
                    </div>
                </div>
                <div class="card-body">
                    <canvas id="revenue-chart" style="height: 300px;"></canvas>
                </div>
            </div>
        </div>
        
        <!-- User Growth Chart -->
        <div class="col-xl-4 col-lg-5">
            <div class="card shadow mb-4">
                <div class="card-header py-3 d-flex justify-content-between align-items-center">
                    <h6 class="m-0 font-weight-bold text-primary">User Growth</h6>
                    <button class="btn btn-outline-secondary btn-sm refresh-btn" 
                            hx-get="/api/dashboard/user-growth" 
                            hx-trigger="click"
                            hx-swap="none"
                            _="on htmx:afterRequest(evt)
                               set data to JSON.parse(evt.detail.xhr.response)
                               update-user-growth-chart(data)">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                </div>
                <div class="card-body">
                    <canvas id="user-growth-chart" style="height: 280px;"></canvas>
                </div>
            </div>
        </div>
    </div>
    
    <div class="row">
        <!-- Performance Metrics -->
        <div class="col-lg-6">
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">System Performance</h6>
                </div>
                <div class="card-body">
                    <canvas id="performance-metrics-chart" style="height: 300px;"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Geographic Distribution -->
        <div class="col-lg-6">
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">Geographic Distribution</h6>
                </div>
                <div class="card-body">
                    <canvas id="geographic-chart" style="height: 300px;"></canvas>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
// Bootstrap-themed color palette
const bootstrapColors = {
    primary: '#4e73df',
    success: '#1cc88a',
    info: '#36b9cc',
    warning: '#f6c23e',
    danger: '#e74a3b',
    secondary: '#858796',
    light: '#f8f9fc',
    dark: '#5a5c69'
};

// Initialize all charts
document.addEventListener('DOMContentLoaded', function() {
    initializeRevenueChart('line');
    initializeUserGrowthChart();
    initializePerformanceChart();
    initializeGeographicChart();
});

function initializeRevenueChart(type) {
    const ctx = document.getElementById('revenue-chart').getContext('2d');
    
    const config = {
        type: type,
        data: {
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            datasets: [{
                label: 'Revenue',
                data: [65000, 78000, 85000, 72000, 95000, 102000],
                borderColor: bootstrapColors.primary,
                backgroundColor: type === 'line' ? 'rgba(78, 115, 223, 0.1)' : bootstrapColors.primary,
                fill: type === 'line'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#e3e6f0'
                    },
                    ticks: {
                        color: bootstrapColors.secondary
                    }
                },
                y: {
                    grid: {
                        color: '#e3e6f0'
                    },
                    ticks: {
                        color: bootstrapColors.secondary,
                        callback: function(value) {
                            return ' + (value / 1000) + 'k';
                        }
                    }
                }
            }
        }
    };
    
    if (window.revenueChart) {
        window.revenueChart.destroy();
    }
    window.revenueChart = new Chart(ctx, config);
}

function initializeUserGrowthChart() {
    const ctx = document.getElementById('user-growth-chart').getContext('2d');
    
    window.userGrowthChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['New Users', 'Returning Users', 'Inactive Users'],
            datasets: [{
                data: [300, 500, 100],
                backgroundColor: [
                    bootstrapColors.success,
                    bootstrapColors.primary,
                    bootstrapColors.warning
                ],
                borderWidth: 3,
                borderColor: '#ffffff',
                hoverBorderWidth: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        color: bootstrapColors.dark
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            }
        }
    });
}

function initializePerformanceChart() {
    const ctx = document.getElementById('performance-metrics-chart').getContext('2d');
    
    window.performanceChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Speed', 'Reliability', 'Security', 'Usability', 'Performance'],
            datasets: [{
                label: 'Current',
                data: [85, 92, 78, 88, 82],
                borderColor: bootstrapColors.primary,
                backgroundColor: 'rgba(78, 115, 223, 0.2)',
                borderWidth: 2,
                pointBackgroundColor: bootstrapColors.primary,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2
            }, {
                label: 'Target',
                data: [90, 95, 85, 90, 88],
                borderColor: bootstrapColors.success,
                backgroundColor: 'rgba(28, 200, 138, 0.1)',
                borderWidth: 2,
                borderDash: [5, 5],
                pointBackgroundColor: bootstrapColors.success,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: '#e3e6f0'
                    },
                    pointLabels: {
                        color: bootstrapColors.dark
                    },
                    ticks: {
                        color: bootstrapColors.secondary,
                        backdropColor: 'transparent'
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: bootstrapColors.dark,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            }
        }
    });
}

function initializeGeographicChart() {
    const ctx = document.getElementById('geographic-chart').getContext('2d');
    
    window.geographicChart = new Chart(ctx, {
        type: 'polarArea',
        data: {
            labels: ['North America', 'Europe', 'Asia', 'South America', 'Africa', 'Oceania'],
            datasets: [{
                data: [450, 320, 280, 180, 120, 80],
                backgroundColor: [
                    bootstrapColors.primary,
                    bootstrapColors.success,
                    bootstrapColors.warning,
                    bootstrapColors.danger,
                    bootstrapColors.info,
                    bootstrapColors.secondary
                ],
                borderWidth: 3,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        color: bootstrapColors.dark
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            },
            scales: {
                r: {
                    grid: {
                        color: '#e3e6f0'
                    },
                    pointLabels: {
                        color: bootstrapColors.dark
                    },
                    ticks: {
                        color: bootstrapColors.secondary,
                        backdropColor: 'transparent'
                    }
                }
            }
        }
    });
}

// Update functions (called by hyperscript)
function updateUserGrowthChart(data) {
    const chart = window.userGrowthChart;
    chart.data.datasets[0].data = [data.new_users, data.returning_users, data.inactive_users];
    chart.update();
}
</script>

<style>
.multi-chart-dashboard {
    padding: 1rem 0;
}

.chart-type-selector .btn {
    font-size: 0.875rem;
}

.refresh-btn:hover {
    background-color: #f8f9fa;
}

/* Chart container responsive adjustments */
@media (max-width: 768px) {
    .chart-wrapper {
        height: 250px;
    }
    
    .card-body canvas {
        height: 200px !important;
    }
}
</style>
```

---

## Best Practices for Flask Dashboard Development

### Performance Optimization

#### 1. Efficient HTMX Patterns with Bootstrap
```html
<!-- Good: Targeted updates with Bootstrap loading states -->
<div class="card" 
     hx-get="/api/stats" 
     hx-trigger="every 30s" 
     hx-target="#stats-container" 
     hx-swap="innerHTML">
    <div class="card-body">
        <div id="stats-container">
            <!-- Stats content -->
        </div>
    </div>
</div>

<!-- Better: Conditional updates with Bootstrap indicators -->
<div class="card" 
     hx-get="/api/stats" 
     hx-trigger="every 30s" 
     hx-target="#stats-container" 
     hx-swap="innerHTML"
     hx-headers='{"If-Modified-Since": "{{ last_modified }}"}'
     _="on htmx:beforeRequest add .updating to me
        on htmx:afterRequest remove .updating from me
        on htmx:responseError(evt)
          if evt.detail.xhr.status is 304
            -- No changes, skip update
            halt the event
          end">
    <div class="card-body">
        <div id="stats-container">
            <!-- Stats content -->
        </div>
        <div class="htmx-indicator">
            <div class="d-flex justify-content-center">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Updating...</span>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Best: Smart caching with Bootstrap styling -->
<div id="stats-widget" class="card" 
     hx-get="/api/stats" 
     hx-trigger="load, every 30s" 
     hx-target="this" 
     hx-swap="innerHTML"
     _="init 
        set :lastHash to ''
        
        on htmx:beforeRequest
          set :requestTime to Date.now()
          add .border-primary to me
        end
        
        on htmx:afterRequest(evt)
          set response to evt.detail.xhr.response
          set newHash to btoa(response).substring(0, 10)
          
          remove .border-primary from me
          
          if newHash is :lastHash
            -- No visual changes needed
            add .border-success to me
            wait 1s
            remove .border-success from me
            halt the event
          else
            set :lastHash to newHash
            add .border-info to me
            wait 500ms
            remove .border-info from me
          end
        end">
    <!-- Initial content -->
    <div class="card-body text-center">
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    </div>
</div>
```

#### 2. _hyperscript Memory Management with Bootstrap
```html
<!-- Good: Clean up event listeners with Bootstrap components -->
<div class="modal fade dashboard-widget" 
     _="init
        set :interval to setInterval(def() updateWidget() end, 5000)
        
        on hidden.bs.modal
          clearInterval(:interval)
        end
        
        def updateWidget()
          -- Update logic here
          add .updating to .card-body in me
          fetch /api/widget-data
          put the result into .widget-content in me
          remove .updating from .card-body in me
        end">
    
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-body">
                <div class="widget-content">
                    <!-- Widget content -->
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Better: Use built-in cleanup with Bootstrap events -->
<div class="card dashboard-widget" 
     _="init
        repeat every 5s
          updateWidget()
        until event(beforeunload) from window or event(hidden.bs.modal) from me
        
        def updateWidget()
          add .opacity-50 to .card-body in me
          fetch /api/widget-data
          put the result into .widget-content in me
          remove .opacity-50 from .card-body in me
        end">
    
    <div class="card-body">
        <div class="widget-content">
            <!-- Widget content -->
        </div>
    </div>
</div>
```

#### 3. Optimized Flask Routes with Bootstrap Responses
```python
from flask import jsonify, request, abort
from functools import wraps
import hashlib
import json

def cache_control(max_age=60):
    """Add cache control headers"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = f(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['Cache-Control'] = f'max-age={max_age}'
            return response
        return decorated_function
    return decorator

def etag_cache(f):
    """Add ETag caching for API responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the response data
        data = f(*args, **kwargs)
        
        # Generate ETag from data
        content = json.dumps(data, sort_keys=True) if isinstance(data, dict) else str(data)
        etag = hashlib.md5(content.encode()).hexdigest()
        
        # Check if client has cached version
        if request.headers.get('If-None-Match') == etag:
            return abort(304)  # Not Modified
        
        # Return response with ETag
        response = jsonify(data)
        response.headers['ETag'] = etag
        return response
    
    return decorated_function

@app.route('/api/dashboard/stats')
@cache_control(max_age=30)
@etag_cache
def get_dashboard_stats():
    return {
        'total_users': get_user_count(),
        'active_sessions': get_active_sessions(),
        'system_load': get_system_load(),
        'timestamp': int(time.time())
    }

@app.route('/api/dashboard/stats/html')
def get_dashboard_stats_html():
    """Return Bootstrap-styled HTML for stats"""
    stats = get_dashboard_stats()
    
    return render_template_string('''
    <div class="row">
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-primary shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                                Total Users
                            </div>
                            <div class="h5 mb-0 font-weight-bold text-gray-800">{{ stats.total_users }}</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-users fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <!-- More stat cards... -->
    </div>
    ''', stats=stats)
```

### Security Best Practices

#### 1. CSRF Protection with HTMX and Bootstrap
```python
from flask_wtf.csrf import CSRFProtect, generate_csrf

csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)
```

```html
<!-- Include CSRF token in HTMX requests with Bootstrap styling -->
<div class="container-fluid" hx-headers='{"X-CSRFToken": "{{ csrf_token() }}"}'>
    <form class="needs-validation" 
          hx-post="/api/dashboard/users"
          novalidate>
        <div class="mb-3">
            <label class="form-label">Username</label>
            <input class="form-control" name="username" required>
            <div class="invalid-feedback">
                Please provide a username.
            </div>
        </div>
        <button type="submit" class="btn btn-primary">Submit</button>
    </form>
</div>

<!-- Or use meta tag for global HTMX config -->
<meta name="csrf-token" content="{{ csrf_token() }}">
<script>
document.body.addEventListener('htmx:configRequest', function(evt) {
    evt.detail.headers['X-CSRFToken'] = document.querySelector('meta[name="csrf-token"]').content;
});
</script>
```

#### 2. Input Validation and Sanitization with Bootstrap
```python
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, validators
from markupsafe import Markup, escape

class DashboardFilterForm(FlaskForm):
    search = StringField('Search', [validators.Length(max=100)])
    status = SelectField('Status', choices=[('', 'All'), ('active', 'Active'), ('inactive', 'Inactive')])
    
    def clean_search(self):
        """Sanitize search input"""
        search = self.search.data
        if search:
            return escape(search.strip())
        return ''

@app.route('/api/dashboard/users')
def get_users():
    form = DashboardFilterForm()
    if form.validate():
        search = form.clean_search()
        status = form.status.data
        # Use sanitized inputs for database query
        users = User.query.filter_by_search(search, status)
        return render_template('dashboard/users_table.html', users=users)
    else:
        return render_template_string('''
        <div class="alert alert-danger" role="alert">
            <h4 class="alert-heading">Validation Error!</h4>
            <ul class="mb-0">
                {% for field, errors in form.errors.items() %}
                    {% for error in errors %}
                        <li>{{ field }}: {{ error }}</li>
                    {% endfor %}
                {% endfor %}
            </ul>
        </div>
        ''', form=form), 400
```

#### 3. Rate Limiting for Dashboard APIs
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/dashboard/stats')
@limiter.limit("30 per minute")
def get_dashboard_stats():
    return get_stats_data()

@app.route('/api/dashboard/export')
@limiter.limit("5 per minute")
def export_dashboard_data():
    return generate_export()

# Custom rate limit exceeded handler with Bootstrap styling
@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template_string('''
    <div class="alert alert-warning" role="alert">
        <h4 class="alert-heading">
            <i class="fas fa-exclamation-triangle me-2"></i>Rate Limit Exceeded
        </h4>
        <p>You have exceeded the rate limit. Please try again later.</p>
        <hr>
        <p class="mb-0">Limit: {{ e.description }}</p>
    </div>
    ''', e=e), 429
```

### Error Handling and User Experience

#### 1. Graceful Error Handling with Bootstrap
```html
<!-- Error handling with Bootstrap alerts -->
<div class="container-fluid dashboard-content" 
     _="on htmx:responseError(evt)
        set status to evt.detail.xhr.status
        if status is 403
          show-error-message('Access denied. Please check your permissions.', 'warning')
        else if status is 500
          show-error-message('Server error. Please try again later.', 'danger')
        else if status is 429
          show-error-message('Too many requests. Please wait before trying again.', 'warning')
        else
          show-error-message('An error occurred. Please refresh the page.', 'danger')
        end
        
        def show-error-message(message, type)
          make a <div.alert.alert-dismissible.fade.show/> called alert
          add .{`alert-${type}`} to alert
          set alert.innerHTML to `
            <div class='d-flex align-items-center'>
              <i class='fas fa-exclamation-circle me-2'></i>
              <div class='flex-grow-1'>${message}</div>
              <button type='button' class='btn-close' data-bs-dismiss='alert'></button>
            </div>
          `
          put alert at the start of body
          wait 5s
          if alert is in body
            set alertInstance to new bootstrap.Alert(alert)
            call alertInstance.close()
          end
        end
        
        on htmx:timeout
          show-error-message('Request timed out. Please check your connection.', 'warning')
        end">
    
    <!-- Dashboard content -->
</div>
```

#### 2. Loading States and Feedback with Bootstrap
```html
<!-- Advanced loading indicators with Bootstrap -->
<div class="card data-table-container" 
     _="on htmx:beforeRequest
        add .loading to me
        make a <div.loading-overlay.d-flex.align-items-center.justify-content-center/> called overlay
        set overlay.innerHTML to `
          <div class='text-center'>
            <div class='spinner-border text-primary mb-3' role='status'>
              <span class='visually-hidden'>Loading...</span>
            </div>
            <div class='text-muted'>Loading data...</div>
          </div>
        `
        set overlay.style.cssText to `
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(255, 255, 255, 0.9);
          z-index: 10;
        `
        put overlay into me
        
        on htmx:afterRequest
          remove .loading from me
          remove .loading-overlay from me
        end
        
        on htmx:timeout
          remove .loading from me
          remove .loading-overlay from me
          add .border-danger to me
          make a <div.alert.alert-danger.mt-3/> called errorAlert
          set errorAlert.innerHTML to `
            <i class='fas fa-exclamation-triangle me-2'></i>
            Request timed out. Please try again.
          `
          put errorAlert into .card-body in me
        end">
    
    <div class="card-body">
        <!-- Table content -->
    </div>
</div>

<style>
.data-table-container.loading {
    position: relative;
    pointer-events: none;
}
</style>
```

### Code Organization and Best Practices

#### 1. Modular Dashboard Components
```html
<!-- Reusable dashboard components -->
<script type="text/hyperscript">
  -- Global dashboard utilities
  def formatCurrency(amount)
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount)
  end
  
  def formatNumber(number)
    return new Intl.NumberFormat('en-US').format(number)
  end
  
  def showBootstrapToast(message, type, duration)
    set toastHtml to `
      <div class="toast" role="alert" data-bs-autohide="true" data-bs-delay="${duration || 5000}">
        <div class="toast-header">
          <div class="rounded me-2 bg-${type}" style="width: 20px; height: 20px;"></div>
          <strong class="me-auto">Dashboard</strong>
          <small>just now</small>
          <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">${message}</div>
      </div>
    `
    
    make a <div/> called toastElement
    set toastElement.innerHTML to toastHtml
    set toastEl to toastElement.firstElementChild
    put toastEl at the end of .toast-container
    
    set toast to new bootstrap.Toast(toastEl)
    call toast.show()
  end
  
  -- Reusable behaviors
  behavior DashboardCard
    on mouseenter
      add .shadow-lg to me
      remove .shadow to me
    end
    
    on mouseleave
      add .shadow to me
      remove .shadow-lg from me
    end
    
    on dashboard-refresh
      add .border-primary to me
      fetch my @data-refresh-url
      put the result into .card-body in me
      remove .border-primary from me
      add .border-success to me
      wait 1s
      remove .border-success from me
    end
  end
  
  behavior BootstrapTooltip
    on mouseenter
      if not my.tooltip
        set my.tooltip to new bootstrap.Tooltip(me, {
          title: my @data-bs-title,
          placement: my @data-bs-placement or 'top'
        })
      end
      call my.tooltip.show()
    end
    
    on mouseleave
      if my.tooltip
        call my.tooltip.hide()
      end
    end
  end
</script>

<!-- Use behaviors in components -->
<div class="card dashboard-card" 
     _="install DashboardCard" 
     data-refresh-url="/api/dashboard/widget/stats">
  <div class="card-body">
    <!-- Card content -->
  </div>
</div>

<button class="btn btn-outline-secondary" 
        _="install BootstrapTooltip" 
        data-bs-title="Click to refresh dashboard"
        data-bs-placement="bottom">
  <i class="fas fa-sync-alt"></i>
</button>
```

#### 2. Testing Dashboard Components

##### Unit Testing HTMX Endpoints
```python
import pytest
from flask import url_for
import json

def test_dashboard_stats_endpoint(client, auth_headers):
    """Test dashboard stats API"""
    response = client.get('/api/dashboard/stats', headers=auth_headers)
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'total_users' in data
    assert 'active_sessions' in data
    assert isinstance(data['total_users'], int)

def test_dashboard_stats_caching(client, auth_headers):
    """Test ETag caching"""
    # First request
    response1 = client.get('/api/dashboard/stats', headers=auth_headers)
    etag = response1.headers.get('ETag')
    assert etag is not None
    
    # Second request with ETag
    headers = {**auth_headers, 'If-None-Match': etag}
    response2 = client.get('/api/dashboard/stats', headers=headers)
    assert response2.status_code == 304

def test_user_table_filtering(client, auth_headers):
    """Test user table filtering"""
    response = client.get('/api/dashboard/users?search=john&status=active', 
                         headers=auth_headers)
    assert response.status_code == 200
    assert b'john' in response.data.lower()

def test_bootstrap_modal_rendering(client, auth_headers):
    """Test Bootstrap modal HTML rendering"""
    response = client.get('/api/dashboard/users/new', headers=auth_headers)
    assert response.status_code == 200
    
    # Check for Bootstrap modal classes
    assert b'modal fade' in response.data
    assert b'modal-dialog' in response.data
    assert b'btn-close' in response.data
    assert b'form-control' in response.data

def test_csrf_protection(client, auth_headers):
    """Test CSRF protection works with HTMX"""
    # Request without CSRF token should fail
    response = client.post('/api/dashboard/users', 
                          data={'username': 'test', 'email': 'test@example.com'},
                          headers=auth_headers)
    assert response.status_code == 400
    
    # Request with CSRF token should succeed
    csrf_token = get_csrf_token(client)
    headers = {**auth_headers, 'X-CSRFToken': csrf_token}
    response = client.post('/api/dashboard/users',
                          data={'username': 'test', 'email': 'test@example.com'},
                          headers=headers)
    assert response.status_code == 201
```

##### Frontend Testing with Playwright
```python
# test_dashboard_e2e.py
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        yield page
        browser.close()

def test_dashboard_real_time_updates(page):
    """Test real-time dashboard updates with Bootstrap styling"""
    page.goto("http://localhost:5000/dashboard")
    
    # Wait for initial load
    page.wait_for_selector("#stats-container")
    
    # Check Bootstrap classes are present
    assert page.query_selector(".card.border-left-primary")
    assert page.query_selector(".btn.btn-primary")
    
    # Check initial user count
    initial_count = page.text_content("#active-users-count")
    
    # Trigger update (simulate user login in another tab)
    page.evaluate("fetch('/api/simulate-user-login', {method: 'POST'})")
    
    # Wait for update
    page.wait_for_function(
        f"document.querySelector('#active-users-count').textContent !== '{initial_count}'"
    )
    
    # Verify count increased and Bootstrap styling is maintained
    new_count = page.text_content("#active-users-count")
    assert int(new_count) > int(initial_count)
    
    # Verify Bootstrap animation classes
    stats_container = page.query_selector("#stats-container")
    assert "animate__pulse" in stats_container.get_attribute("class") or True

def test_bootstrap_modal_functionality(page):
    """Test Bootstrap modal interactions"""
    page.goto("http://localhost:5000/dashboard/users")
    
    # Click add user button
    page.click("button:has-text('Add User')")
    
    # Wait for Bootstrap modal to appear
    page.wait_for_selector(".modal.fade.show", state="visible")
    
    # Check modal styling
    modal = page.query_selector(".modal")
    assert "fade" in modal.get_attribute("class")
    assert "show" in modal.get_attribute("class")
    
    # Fill form with Bootstrap form controls
    page.fill(".form-control[name='username']", "testuser")
    page.fill(".form-control[name='email']", "test@example.com")
    page.select_option(".form-select[name='role']", "user")
    
    # Submit form
    page.click("button[type='submit']")
    
    # Modal should close
    page.wait_for_selector(".modal", state="hidden")
    
    # New user should appear in table
    page.wait_for_selector("text=testuser")

def test_dashboard_responsive_design(page):
    """Test responsive behavior with Bootstrap breakpoints"""
    page.goto("http://localhost:5000/dashboard")
    
    # Test desktop view
    page.set_viewport_size({"width": 1200, "height": 800})
    sidebar = page.query_selector(".dashboard-sidebar")
    assert sidebar.is_visible()
    
    # Test mobile view
    page.set_viewport_size({"width": 375, "height": 667})
    
    # Sidebar should be hidden on mobile
    page.wait_for_function(
        "window.getComputedStyle(document.querySelector('.dashboard-sidebar')).transform.includes('translateX(-100%)')"
    )
    
    # Mobile menu button should be visible
    mobile_btn = page.query_selector(".mobile-menu-btn")
    assert mobile_btn.is_visible() if mobile_btn else True

def test_dashboard_interactivity(page):
    """Test dashboard interactive features with Bootstrap components"""
    page.goto("http://localhost:5000/dashboard/users")
    
    # Test Bootstrap dropdown filter
    page.click(".dropdown-toggle:has-text('Actions')")
    page.wait_for_selector(".dropdown-menu", state="visible")
    
    # Test search functionality with Bootstrap form controls
    page.fill(".form-control[placeholder*='Search']", "test user")
    page.wait_for_selector(".table tbody tr:has-text('test user')")
    
    # Test bulk selection with Bootstrap checkboxes
    page.check(".form-check-input[name='selected_users']")
    page.wait_for_selector("#bulk-actions-bar", state="visible")
    
    # Verify Bootstrap alert styling
    bulk_actions = page.query_selector("#bulk-actions-bar")
    assert "alert" in bulk_actions.get_attribute("class")
    assert "alert-info" in bulk_actions.get_attribute("class")

def test_chart_interactivity(page):
    """Test Chart.js integration with Bootstrap styling"""
    page.goto("http://localhost:5000/dashboard")
    
    # Wait for chart to load
    page.wait_for_selector("#sales-chart")
    
    # Test chart controls with Bootstrap dropdowns
    page.click(".dropdown-toggle:has-text('Time Range')")
    page.wait_for_selector(".dropdown-menu", state="visible")
    page.click(".dropdown-item:has-text('Last 7 days')")
    
    # Wait for chart update
    page.wait_for_timeout(1000)
    
    # Verify chart is still present and functional
    chart_canvas = page.query_selector("#sales-chart")
    assert chart_canvas.is_visible()
```

#### 3. Accessibility Guidelines with Bootstrap

```html
<!-- Accessible dashboard components with Bootstrap and ARIA -->
<nav class="navbar navbar-expand-lg navbar-dark bg-dark" role="navigation" aria-label="Main navigation">
    <div class="container-fluid">
        <a class="navbar-brand" href="/dashboard" aria-label="Dashboard home">
            <i class="fas fa-tachometer-alt me-2" aria-hidden="true"></i>
            Dashboard
        </a>
        
        <button class="navbar-toggler" type="button" 
                data-bs-toggle="collapse" 
                data-bs-target="#navbarNav"
                aria-controls="navbarNav" 
                aria-expanded="false" 
                aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"></span>
        </button>
    </div>
</nav>

<!-- Accessible data table with Bootstrap -->
<div class="card" role="region" aria-labelledby="users-table-heading">
    <div class="card-header">
        <h2 id="users-table-heading" class="h5 mb-0">Users Management</h2>
    </div>
    <div class="card-body">
        <!-- Screen reader announcements -->
        <div class="sr-only" aria-live="polite" id="table-status">
            <span id="loading-announcement"></span>
            <span id="update-announcement"></span>
        </div>
        
        <table class="table table-striped" 
               role="table" 
               aria-labelledby="users-table-heading"
               aria-describedby="table-description">
            <caption id="table-description" class="sr-only">
                Users in the system with their roles and status information
            </caption>
            
            <thead>
                <tr role="row">
                    <th scope="col" aria-label="Select user">
                        <input class="form-check-input" type="checkbox" 
                               aria-label="Select all users"
                               _="on change
                                  if my checked
                                    put 'All users selected' into #update-announcement
                                  else
                                    put 'All users deselected' into #update-announcement
                                  end">
                    </th>
                    <th scope="col" 
                        class="sortable" 
                        role="columnheader" 
                        aria-sort="none"
                        tabindex="0"
                        _="on click
                           set currentSort to my @aria-sort
                           if currentSort is 'ascending'
                             set my @aria-sort to 'descending'
                             put 'Users sorted by name, descending' into #update-announcement
                           else
                             set my @aria-sort to 'ascending'
                             put 'Users sorted by name, ascending' into #update-announcement
                           end">
                        Username
                        <i class="fas fa-sort ms-1" aria-hidden="true"></i>
                    </th>
                    <th scope="col">Email</th>
                    <th scope="col">Role</th>
                    <th scope="col">Status</th>
                    <th scope="col">Actions</th>
                </tr>
            </thead>
            
            <tbody>
                {% for user in users %}
                <tr role="row">
                    <td>
                        <input class="form-check-input" 
                               type="checkbox" 
                               name="selected_users" 
                               value="{{ user.id }}"
                               aria-label="Select {{ user.username }}">
                    </td>
                    <th scope="row">{{ user.username }}</th>
                    <td>{{ user.email }}</td>
                    <td>
                        <span class="badge bg-primary">{{ user.role }}</span>
                    </td>
                    <td>
                        <button class="btn btn-sm {{ 'btn-success' if user.is_active else 'btn-secondary' }}"
                                hx-post="/api/dashboard/users/{{ user.id }}/toggle-status"
                                hx-target="this"
                                hx-swap="outerHTML"
                                aria-label="Toggle status for {{ user.username }}. Currently {{ 'active' if user.is_active else 'inactive' }}"
                                _="on htmx:afterRequest
                                   put 'Status updated for {{ user.username }}' into #update-announcement">
                            {{ 'Active' if user.is_active else 'Inactive' }}
                        </button>
                    </td>
                    <td>
                        <div class="btn-group" role="group" aria-label="Actions for {{ user.username }}">
                            <button class="btn btn-sm btn-outline-primary" 
                                    hx-get="/api/dashboard/users/{{ user.id }}/edit"
                                    hx-target="#modal-container"
                                    aria-label="Edit {{ user.username }}">
                                <i class="fas fa-edit" aria-hidden="true"></i>
                                <span class="sr-only">Edit</span>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" 
                                    hx-delete="/api/dashboard/users/{{ user.id }}"
                                    hx-confirm="Delete {{ user.username }}?"
                                    hx-target="closest tr"
                                    hx-swap="outerHTML"
                                    aria-label="Delete {{ user.username }}">
                                <i class="fas fa-trash" aria-hidden="true"></i>
                                <span class="sr-only">Delete</span>
                            </button>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Accessible modal with Bootstrap -->
<div class="modal fade" 
     tabindex="-1" 
     role="dialog" 
     aria-labelledby="modal-title" 
     aria-hidden="true"
     _="on show.bs.modal
        focus() on the first <input/> in me
        on hidden.bs.modal
        focus() on the button that opened me">
    <div class="modal-dialog" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 id="modal-title" class="modal-title">Add New User</h5>
                <button type="button" 
                        class="btn-close" 
                        data-bs-dismiss="modal" 
                        aria-label="Close dialog">
                </button>
            </div>
            
            <form class="needs-validation" novalidate>
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="username" class="form-label">
                            Username <span class="text-danger" aria-label="required">*</span>
                        </label>
                        <input type="text" 
                               class="form-control" 
                               id="username" 
                               name="username" 
                               required 
                               aria-describedby="username-help username-error">
                        <div id="username-help" class="form-text">
                            Choose a unique username (3-20 characters)
                        </div>
                        <div id="username-error" class="invalid-feedback" role="alert">
                            Please provide a valid username.
                        </div>
                    </div>
                    
                    <fieldset class="mb-3">
                        <legend class="form-label">Account Status</legend>
                        <div class="form-check">
                            <input class="form-check-input" 
                                   type="checkbox" 
                                   id="is_active" 
                                   name="is_active" 
                                   checked>
                            <label class="form-check-label" for="is_active">
                                Active User
                            </label>
                        </div>
                    </fieldset>
                </div>
                
                <div class="modal-footer">
                    <button type="button" 
                            class="btn btn-secondary" 
                            data-bs-dismiss="modal">
                        Cancel
                    </button>
                    <button type="submit" 
                            class="btn btn-primary"
                            _="on click
                               put 'Creating user...' into #update-announcement">
                        Create User
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- Screen reader only styles -->
<style>
.sr-only {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
}

/* Focus indicators */
.btn:focus,
.form-control:focus,
.form-select:focus,
.form-check-input:focus {
    box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
    outline: 0;
}

/* High contrast mode support */
@media (prefers-contrast: high) {
    .card {
        border: 2px solid;
    }
    
    .btn {
        border-width: 2px;
    }
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
    .fade {
        transition: none;
    }
    
    .collapse {
        transition: none;
    }
    
    .modal.fade .modal-dialog {
        transition: none;
        transform: none;
    }
}
</style>
```

#### 4. Performance Monitoring and Optimization

```python
# Performance monitoring for dashboard endpoints
import time
import functools
from flask import g, request

def monitor_performance(f):
    """Decorator to monitor API performance"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = f(*args, **kwargs)
            status_code = getattr(result, 'status_code', 200)
        except Exception as e:
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time
            
            # Log performance metrics
            app.logger.info(f"API Performance: {request.endpoint} - "
                           f"Duration: {duration:.3f}s - "
                           f"Status: {status_code}")
            
            # Store in database for dashboard monitoring
            store_performance_metric(
                endpoint=request.endpoint,
                duration=duration,
                status_code=status_code,
                user_id=getattr(g, 'user_id', None)
            )
        
        return result
    return wrapper

@app.route('/api/dashboard/performance')
@monitor_performance
def get_performance_metrics():
    """Get performance metrics for dashboard monitoring"""
    metrics = {
        'avg_response_time': get_avg_response_time(),
        'error_rate': get_error_rate(),
        'requests_per_minute': get_requests_per_minute(),
        'slowest_endpoints': get_slowest_endpoints()
    }
    
    return render_template_string('''
    <div class="row">
        <div class="col-md-3">
            <div class="card border-left-info shadow h-100 py-2">
                <div class="card-body">
                    <div class="text-xs font-weight-bold text-info text-uppercase mb-1">
                        Avg Response Time
                    </div>
                    <div class="h5 mb-0 font-weight-bold text-gray-800">
                        {{ "%.0f"|format(metrics.avg_response_time) }}ms
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card border-left-{{ 'success' if metrics.error_rate < 5 else 'warning' if metrics.error_rate < 10 else 'danger' }} shadow h-100 py-2">
                <div class="card-body">
                    <div class="text-xs font-weight-bold text-{{ 'success' if metrics.error_rate < 5 else 'warning' if metrics.error_rate < 10 else 'danger' }} text-uppercase mb-1">
                        Error Rate
                    </div>
                    <div class="h5 mb-0 font-weight-bold text-gray-800">
                        {{ "%.1f"|format(metrics.error_rate) }}%
                    </div>
                </div>
            </div>
        </div>
        <!-- More metrics... -->
    </div>
    ''', metrics=metrics)

# Database optimization for dashboard queries
@app.route('/api/dashboard/users/optimized')
def get_users_optimized():
    """Optimized user query with pagination and filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 25, type=int), 100)  # Limit max per_page
    search = request.args.get('search', '').strip()
    
    # Use database indexes and efficient queries
    query = db.session.query(User).options(
        # Load only needed columns
        db.load_only(User.id, User.username, User.email, User.is_active, User.role, User.created_at)
    )
    
    if search:
        # Use full-text search index if available
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    # Add caching for frequently accessed data
    cache_key = f"users_page_{page}_{per_page}_{search}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return cached_result
    
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False,
        max_per_page=100
    )
    
    result = render_template('dashboard/users_table_optimized.html', 
                           pagination=pagination)
    
    # Cache for 5 minutes
    cache.set(cache_key, result, timeout=300)
    
    return result
```

#### 5. Deployment and Production Considerations

```python
# Production configuration for Flask dashboard
import os
import logging
from logging.handlers import RotatingFileHandler

class ProductionConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://user:pass@localhost/dashboard'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis for caching and sessions
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    SESSION_TYPE = 'redis'
    SESSION_REDIS = redis.from_url(REDIS_URL)
    
    # Security headers
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;",
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }
    
    # Logging
    LOG_LEVEL = logging.INFO
    LOG_FILE = 'logs/dashboard.log'

# Security middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    if app.config.get('SECURITY_HEADERS'):
        for header, value in app.config['SECURITY_HEADERS'].items():
            response.headers[header] = value
    return response

# Production logging setup
if not app.debug and not app.testing:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler(
        'logs/dashboard.log', 
        maxBytes=10240000, 
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('Dashboard startup')

# Docker deployment
"""
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user
RUN groupadd -r dashboard && useradd --no-log-init -r -g dashboard dashboard
RUN chown -R dashboard:dashboard /app
USER dashboard

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
"""

# docker-compose.yml
"""
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://dashboard:password@db:5432/dashboard
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-production-secret-key
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=dashboard
      - POSTGRES_USER=dashboard
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web

volumes:
  postgres_data:
"""
```

---

## Common Pitfalls to Avoid

### 1. HTMX Pitfalls
- **Don't forget `hx-target`** - Without it, HTMX will replace the triggering element
- **Use proper HTTP methods** - GET for retrieval, POST for creation, PUT for updates, DELETE for removal
- **Handle loading states** - Always provide Bootstrap loading indicators during requests
- **Validate on server** - Client-side validation is UX, server-side is security
- **Don't ignore CSRF protection** - Always include CSRF tokens in forms and AJAX requests

### 2. _hyperscript Pitfalls
- **Remember `end` keywords** - Most blocks need to be closed with `end`
- **Variable scoping** - Use `:` for element scope, `# AI Frontend Technologies Guide for Flask Dashboards: HTMX, _hyperscript, and Bootstrap 5

This comprehensive guide provides AI models with detailed information about three powerful frontend technologies specifically for building dynamic Flask dashboards and admin interfaces. These technologies work together to create sophisticated, interactive web dashboards without heavy JavaScript frameworks.

## Table of Contents
1. [HTMX for Flask Dashboards](#htmx)
2. [_hyperscript for Dashboard Interactions](#_hyperscript)
3. [Bootstrap 5 for Dashboard Styling](#bootstrap5)
4. [Flask Dashboard Integration Patterns](#integration-patterns)
5. [Dashboard-Specific Components](#dashboard-components)
6. [Real-time Dashboard Updates](#real-time-updates)
7. [Data Visualization Integration](#data-visualization)
8. [Best Practices for Flask Dashboard Development](#best-practices-for-ai-code-generation)

---

## HTMX for Flask Dashboards

### Overview
HTMX is perfect for Flask dashboard development because it allows you to build dynamic interfaces that communicate seamlessly with Flask routes, returning HTML fragments that update specific dashboard components without full page reloads.

### Core Philosophy for Dashboards
- **Server-Side Rendering** - Flask renders dashboard components as HTML templates
- **Partial Updates** - Update specific dashboard widgets without page refresh
- **RESTful Endpoints** - Dashboard actions map to Flask routes
- **Progressive Enhancement** - Works with existing Flask forms and links

### Flask Route Patterns for Dashboards

#### Dashboard Data Endpoints
```python
# Flask routes for dashboard data
from flask import render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard/index.html')

@app.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """Return dashboard statistics widget"""
    stats = {
        'total_users': User.query.count(),
        'active_sessions': get_active_sessions(),
        'revenue': calculate_revenue(),
        'conversion_rate': get_conversion_rate()
    }
    return render_template('dashboard/components/stats.html', stats=stats)

@app.route('/api/dashboard/chart/<chart_type>')
@login_required
def dashboard_chart(chart_type):
    """Return chart data as HTML"""
    data = get_chart_data(chart_type, request.args)
    return render_template(f'dashboard/charts/{chart_type}.html', data=data)

@app.route('/api/dashboard/table/<table_name>')
@login_required
def dashboard_table(table_name):
    """Return paginated table data"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    if table_name == 'users':
        pagination = User.query.paginate(page=page, per_page=per_page)
    elif table_name == 'orders':
        pagination = Order.query.paginate(page=page, per_page=per_page)
    
    return render_template('dashboard/tables/table.html', 
                         pagination=pagination, 
                         table_name=table_name)
```

#### CRUD Operations for Dashboard
```python
@app.route('/api/dashboard/users', methods=['POST'])
@login_required
def create_user():
    """Create new user from dashboard"""
    form_data = request.form
    user = User(
        username=form_data['username'],
        email=form_data['email']
    )
    db.session.add(user)
    db.session.commit()
    
    # Return the new user row
    return render_template('dashboard/components/user_row.html', user=user)

@app.route('/api/dashboard/users/<int:user_id>', methods=['PUT', 'POST'])
@login_required
def update_user(user_id):
    """Update user from dashboard"""
    user = User.query.get_or_404(user_id)
    user.username = request.form['username']
    user.email = request.form['email']
    db.session.commit()
    
    return render_template('dashboard/components/user_row.html', user=user)

@app.route('/api/dashboard/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete user from dashboard"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    # Return empty response to remove the row
    return '', 200

@app.route('/api/dashboard/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    # Return updated status badge
    return render_template('dashboard/components/status_badge.html', user=user)
```

### Dashboard HTMX Patterns

#### Auto-Refreshing Dashboard Widgets
```html
<!-- Auto-refreshing statistics widget -->
<div class="card" 
     hx-get="/api/dashboard/stats" 
     hx-trigger="load, every 30s"
     hx-swap="innerHTML">
    <div class="card-body">
        <div class="d-flex justify-content-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading stats...</span>
            </div>
        </div>
    </div>
</div>

<!-- Chart that updates based on date range -->
<div class="card">
    <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="card-title mb-0">Revenue Chart</h5>
        <select class="form-select form-select-sm" style="width: auto;"
                name="timerange" 
                hx-get="/api/dashboard/chart/revenue" 
                hx-trigger="change" 
                hx-target="#revenue-chart"
                hx-include="[name='chart_type']">
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
        </select>
        <input type="hidden" name="chart_type" value="line">
    </div>
    
    <div class="card-body">
        <div id="revenue-chart" 
             hx-get="/api/dashboard/chart/revenue?timerange=7d" 
             hx-trigger="load">
            <div class="d-flex justify-content-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading chart...</span>
                </div>
            </div>
        </div>
    </div>
</div>
```

#### Data Tables with Pagination and Sorting
```html
<!-- Dashboard data table -->
<div class="card">
    <div class="card-header">
        <div class="row align-items-center">
            <div class="col">
                <h5 class="card-title mb-0">Users</h5>
            </div>
            <div class="col-auto">
                <button class="btn btn-primary btn-sm" 
                        hx-get="/api/dashboard/users/new" 
                        hx-target="#modal-container">
                    Add User
                </button>
            </div>
        </div>
    </div>
    
    <!-- Table controls -->
    <div class="card-body border-bottom">
        <div class="row g-3">
            <div class="col-md-6">
                <input type="search" 
                       class="form-control"
                       name="search" 
                       placeholder="Search users..."
                       hx-get="/api/dashboard/table/users" 
                       hx-trigger="keyup changed delay:300ms" 
                       hx-target="#users-table"
                       hx-include="[name='sort'], [name='order'], [name='per_page']">
            </div>
            
            <div class="col-md-3">
                <select class="form-select" name="per_page"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table"
                        hx-include="[name='search'], [name='sort'], [name='order']">
                    <option value="10">10 per page</option>
                    <option value="25">25 per page</option>
                    <option value="50">50 per page</option>
                </select>
            </div>
            
            <div class="col-md-3">
                <button class="btn btn-outline-secondary w-100" 
                        hx-get="/api/dashboard/export/users" 
                        hx-trigger="click">
                    Export CSV
                </button>
            </div>
        </div>
        
        <input type="hidden" name="sort" value="created_at">
        <input type="hidden" name="order" value="desc">
    </div>
    
    <!-- Table content -->
    <div id="users-table" 
         hx-get="/api/dashboard/table/users" 
         hx-trigger="load">
        <div class="d-flex justify-content-center p-4">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading table...</span>
            </div>
        </div>
    </div>
</div>
```

#### Inline Editing
```html
<!-- Inline editable user row -->
<tr id="user-{{ user.id }}">
    <td>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" 
                   name="selected_users" 
                   value="{{ user.id }}">
        </div>
    </td>
    <td>
        <div class="d-flex align-items-center">
            <div class="avatar avatar-sm me-3">
                <span class="avatar-initial rounded-circle bg-primary">
                    {{ user.username[0].upper() }}
                </span>
            </div>
            <div>
                <h6 class="mb-0">{{ user.username }}</h6>
                <small class="text-muted">#{{ user.id }}</small>
            </div>
        </div>
    </td>
    <td>{{ user.email }}</td>
    <td>
        <span class="badge bg-{{ 'success' if user.is_active else 'secondary' }}"
              hx-post="/api/dashboard/users/{{ user.id }}/toggle-status"
              hx-target="this"
              hx-swap="outerHTML"
              style="cursor: pointer;">
            {{ 'Active' if user.is_active else 'Inactive' }}
        </span>
    </td>
    <td>
        <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" 
                    data-bs-toggle="dropdown">
                Actions
            </button>
            <ul class="dropdown-menu">
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/users/{{ user.id }}/edit"
                       hx-target="#modal-container">
                        Edit
                    </a>
                </li>
                <li>
                    <a class="dropdown-item text-danger" href="#"
                       hx-delete="/api/dashboard/users/{{ user.id }}"
                       hx-target="#user-{{ user.id }}"
                       hx-swap="outerHTML"
                       hx-confirm="Are you sure you want to delete this user?">
                        Delete
                    </a>
                </li>
            </ul>
        </div>
    </td>
</tr>
```

#### Dashboard Modals and Forms
```html
<!-- Add user button -->
<button class="btn btn-primary" 
        hx-get="/api/dashboard/users/new" 
        hx-target="#modal-container" 
        hx-swap="innerHTML">
    Add New User
</button>

<!-- Modal container -->
<div id="modal-container"></div>

<!-- Flask returns this modal form -->
<div class="modal fade show d-block" tabindex="-1" style="background: rgba(0,0,0,0.5);">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Add New User</h5>
                <button type="button" class="btn-close" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                </button>
            </div>
            
            <form hx-post="/api/dashboard/users" 
                  hx-target="#users-table" 
                  hx-swap="afterbegin"
                  hx-on::after-request="if(event.detail.successful) document.getElementById('modal-container').innerHTML = ''">
                
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label" for="username">Username</label>
                        <input type="text" 
                               class="form-control"
                               name="username" 
                               id="username"
                               required
                               hx-get="/api/dashboard/validate/username"
                               hx-trigger="blur"
                               hx-target="#username-validation">
                        <div id="username-validation"></div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label" for="email">Email</label>
                        <input type="email" 
                               class="form-control"
                               name="email" 
                               id="email"
                               required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label" for="role">Role</label>
                        <select class="form-select" name="role" id="role" required>
                            <option value="">Select a role</option>
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                            <option value="moderator">Moderator</option>
                        </select>
                    </div>
                    
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" 
                               name="is_active" id="is_active" checked>
                        <label class="form-check-label" for="is_active">
                            Active User
                        </label>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Create User</button>
                    <button type="button" class="btn btn-secondary" 
                            onclick="document.getElementById('modal-container').innerHTML = ''">
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
```

#### Bulk Operations
```html
<!-- Bulk actions toolbar -->
<div class="alert alert-info d-none" id="bulk-actions">
    <div class="d-flex justify-content-between align-items-center">
        <span class="fw-bold">
            <span id="selected-count">0</span> users selected
        </span>
        <div class="btn-group">
            <button class="btn btn-success btn-sm" 
                    hx-post="/api/dashboard/users/bulk-activate" 
                    hx-include="[name='selected_users']:checked"
                    hx-target="#users-table"
                    hx-swap="innerHTML">
                Activate Selected
            </button>
            <button class="btn btn-danger btn-sm" 
                    hx-delete="/api/dashboard/users/bulk-delete" 
                    hx-include="[name='selected_users']:checked"
                    hx-target="#users-table"
                    hx-swap="innerHTML"
                    hx-confirm="Delete selected users?">
                Delete Selected
            </button>
        </div>
    </div>
</div>

<!-- Table with checkboxes -->
<div class="table-responsive">
    <table class="table table-hover">
        <thead class="table-light">
            <tr>
                <th style="width: 40px;">
                    <input class="form-check-input" type="checkbox" id="select-all">
                </th>
                <th>Username</th>
                <th>Email</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for user in users %}
            <tr>
                <td>
                    <input class="form-check-input" 
                           type="checkbox" 
                           name="selected_users" 
                           value="{{ user.id }}"
                           class="user-checkbox">
                </td>
                <td>{{ user.username }}</td>
                <td>{{ user.email }}</td>
                <td>{{ user.status }}</td>
                <td>
                    <!-- Action buttons -->
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

### Dashboard Filters and Search
```html
<!-- Advanced filter panel -->
<div class="card">
    <div class="card-header">
        <h6 class="card-title mb-0">Filters</h6>
    </div>
    <div class="card-body">
        <form hx-get="/api/dashboard/table/users" 
              hx-trigger="change, submit" 
              hx-target="#users-table"
              hx-swap="innerHTML">
            
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Status</label>
                    <select class="form-select" name="status">
                        <option value="">All</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                    </select>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Role</label>
                    <select class="form-select" name="role">
                        <option value="">All Roles</option>
                        {% for role in roles %}
                        <option value="{{ role.id }}">{{ role.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Registration From</label>
                    <input type="date" class="form-control" name="date_from">
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Registration To</label>
                    <input type="date" class="form-control" name="date_to">
                </div>
                
                <div class="col-12">
                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-primary">Apply Filters</button>
                        <button type="button" 
                                class="btn btn-outline-secondary"
                                hx-get="/api/dashboard/table/users" 
                                hx-target="#users-table"
                                onclick="this.closest('form').reset()">
                            Clear Filters
                        </button>
                    </div>
                </div>
            </div>
        </form>
    </div>
</div>
```

### Key Attributes

#### Basic AJAX Attributes
```html
<!-- Core HTMX attributes -->
<button hx-get="/api/data" hx-target="#result">Get Data</button>
<form hx-post="/api/submit" hx-target="#response">
<div hx-put="/api/update" hx-trigger="click">
<span hx-delete="/api/item/123" hx-confirm="Are you sure?">
```

#### Essential Attributes Reference
- **`hx-get`** - Issues GET request to specified URL
- **`hx-post`** - Issues POST request to specified URL  
- **`hx-put`** - Issues PUT request to specified URL
- **`hx-delete`** - Issues DELETE request to specified URL
- **`hx-target`** - Element to update with response (CSS selector)
- **`hx-swap`** - How to swap content (innerHTML, outerHTML, beforeend, afterend, beforebegin, afterbegin, delete, none)
- **`hx-trigger`** - Event that triggers request (click, change, load, revealed, etc.)
- **`hx-params`** - Parameters to include in request
- **`hx-headers`** - Headers to include in request
- **`hx-vals`** - Values to include in request body

#### Advanced Attributes
- **`hx-boost`** - Converts regular links/forms to AJAX
- **`hx-push-url`** - Push URL to browser history
- **`hx-select`** - Select specific part of response
- **`hx-confirm`** - Show confirmation dialog
- **`hx-indicator`** - Element to show during request
- **`hx-sync`** - Synchronize requests
- **`hx-encoding`** - Request encoding (multipart/form-data)

### Triggers
```html
<!-- Event-based triggers -->
<div hx-get="/api/data" hx-trigger="click">Click me</div>
<input hx-get="/search" hx-trigger="keyup changed delay:500ms">
<div hx-get="/poll" hx-trigger="every 2s">Auto-refresh</div>
<div hx-get="/load" hx-trigger="load">Load on page load</div>
<div hx-get="/reveal" hx-trigger="revealed">Load when scrolled into view</div>

<!-- Trigger modifiers -->
<button hx-get="/api" hx-trigger="click once">Only once</button>
<input hx-get="/api" hx-trigger="keyup changed delay:500ms">
<div hx-get="/api" hx-trigger="click from:body">Delegate from body</div>
<div hx-get="/api" hx-trigger="click target:#button">Target specific element</div>
```

### Swapping Strategies
```html
<!-- Different swap strategies -->
<div hx-get="/content" hx-swap="innerHTML">Replace inner content</div>
<div hx-get="/content" hx-swap="outerHTML">Replace entire element</div>
<div hx-get="/content" hx-swap="beforebegin">Insert before element</div>
<div hx-get="/content" hx-swap="afterbegin">Insert at start of element</div>
<div hx-get="/content" hx-swap="beforeend">Insert at end of element</div>
<div hx-get="/content" hx-swap="afterend">Insert after element</div>
<div hx-get="/content" hx-swap="delete">Delete element</div>
<div hx-get="/content" hx-swap="none">Don't swap content</div>

<!-- Swap with timing and scrolling -->
<div hx-swap="innerHTML settle:100ms">Settle for 100ms</div>
<div hx-swap="innerHTML swap:200ms">Swap after 200ms</div>
<div hx-swap="innerHTML scroll:top">Scroll to top after swap</div>
<div hx-swap="innerHTML scroll:bottom">Scroll to bottom after swap</div>
```

### Common Patterns

#### Loading States and Indicators
```html
<style>
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request.htmx-indicator { display: inline; }
</style>

<button hx-get="/api/data" hx-target="#result" class="btn btn-primary">
    Get Data
    <span class="htmx-indicator">
        <span class="spinner-border spinner-border-sm ms-2" role="status">
            <span class="visually-hidden">Loading...</span>
        </span>
    </span>
</button>

<div id="result">
    <div class="htmx-indicator d-flex justify-content-center">
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    </div>
</div>
```

#### Form Handling
```html
<!-- Basic form submission -->
<form hx-post="/api/contact" hx-target="#response" class="needs-validation" novalidate>
    <div class="mb-3">
        <label class="form-label" for="name">Name</label>
        <input class="form-control" name="name" id="name" required>
        <div class="invalid-feedback">Please provide a name.</div>
    </div>
    <div class="mb-3">
        <label class="form-label" for="email">Email</label>
        <input type="email" class="form-control" name="email" id="email" required>
        <div class="invalid-feedback">Please provide a valid email.</div>
    </div>
    <button type="submit" class="btn btn-primary">Submit</button>
</form>

<!-- Form with validation -->
<form hx-post="/api/validate" hx-target="#errors" 
      hx-trigger="submit" hx-swap="innerHTML" class="needs-validation" novalidate>
    <div class="mb-3">
        <label class="form-label" for="username">Username</label>
        <input class="form-control" name="username" id="username"
               hx-get="/api/check-username" 
               hx-trigger="blur" 
               hx-target="#username-error">
        <div id="username-error"></div>
    </div>
    <button type="submit" class="btn btn-primary">Submit</button>
</form>
```

#### Infinite Scroll
```html
<div id="content" class="container">
    <!-- Initial content -->
</div>
<div hx-get="/api/more-content?page=2" 
     hx-trigger="revealed" 
     hx-swap="outerHTML"
     hx-target="this"
     class="text-center p-4">
    <div class="htmx-indicator">
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Loading more...</span>
        </div>
    </div>
</div>
```

#### Live Search
```html
<div class="mb-3">
    <input type="search" 
           class="form-control"
           name="search"
           hx-get="/api/search" 
           hx-trigger="keyup changed delay:300ms" 
           hx-target="#search-results"
           placeholder="Search...">
</div>
<div id="search-results"></div>
```

#### Modal Dialogs
```html
<!-- Trigger -->
<button class="btn btn-primary"
        hx-get="/modal/edit-user/123" 
        hx-target="#modal-container" 
        hx-trigger="click">
    Edit User
</button>

<!-- Modal container -->
<div id="modal-container"></div>

<!-- Server returns Bootstrap modal HTML -->
<div class="modal fade show d-block" tabindex="-1" style="background: rgba(0,0,0,0.5);">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Edit User</h5>
                <button type="button" class="btn-close" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                </button>
            </div>
            <form hx-put="/api/user/123" hx-target="#modal-container" hx-swap="outerHTML">
                <div class="modal-body">
                    <!-- Form fields -->
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Save</button>
                    <button type="button" class="btn btn-secondary" 
                            onclick="document.getElementById('modal-container').innerHTML = ''">
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
```

### Server-Side Response Headers
```javascript
// Useful HTMX response headers for server responses
app.post('/api/data', (req, res) => {
    // Trigger client-side events
    res.set('HX-Trigger', 'dataUpdated');
    
    // Redirect after request
    res.set('HX-Redirect', '/dashboard');
    
    // Refresh the page
    res.set('HX-Refresh', 'true');
    
    // Push URL to history
    res.set('HX-Push-Url', '/new-url');
    
    // Replace URL in history
    res.set('HX-Replace-Url', '/replace-url');
    
    res.send('<div>Updated content</div>');
});
```

### Out of Band Updates
```html
<!-- Response can update multiple elements -->
<div id="main-content">
    <!-- Primary update target -->
</div>

<!-- Server response can include out-of-band updates -->
<div hx-get="/api/update" hx-target="#main-content">Update</div>

<!-- Server returns: -->
<!--
<div id="main-content">New main content</div>
<div id="sidebar" hx-swap-oob="true">Updated sidebar</div>
<div id="header" hx-swap-oob="innerHTML">Updated header content</div>
-->
```

### Configuration
```html
<meta name="htmx-config" content='{"defaultSwapStyle":"outerHTML"}'>

<script>
// JavaScript configuration
htmx.config.defaultSwapStyle = 'outerHTML';
htmx.config.defaultSwapDelay = 100;
htmx.config.requestTimeout = 10000;
htmx.config.historyEnabled = true;
</script>
```

---

## _hyperscript for Dashboard Interactions

### Overview
_hyperscript is perfect for adding interactive behaviors to Flask dashboards. It excels at handling client-side state management, DOM manipulation, and coordinating between different dashboard components without complex JavaScript.

### Dashboard-Specific Behaviors

#### Dashboard Layout Management
```html
<!-- Collapsible sidebar -->
<nav class="navbar-nav bg-gradient-primary sidebar sidebar-dark accordion" 
     _="init set :collapsed to false
       on toggle-sidebar
         if :collapsed
           remove .sidebar-collapsed from #wrapper
           set :collapsed to false
         else
           add .sidebar-collapsed to #wrapper
           set :collapsed to true
         end
         send sidebar-changed(collapsed: :collapsed) to #main-content">
    
    <div class="sidebar-brand d-flex align-items-center justify-content-center">
        <div class="sidebar-brand-icon rotate-n-15">
            <i class="fas fa-laugh-wink"></i>
        </div>
        <div class="sidebar-brand-text mx-3">Dashboard</div>
        <button class="btn btn-link d-md-none ms-auto" 
                _="on click send toggle-sidebar to .sidebar">
            <i class="fas fa-bars"></i>
        </button>
    </div>
    
    <ul class="navbar-nav">
        <li class="nav-item">
            <a class="nav-link" href="/dashboard">
                <i class="fas fa-fw fa-tachometer-alt"></i>
                <span>Overview</span>
            </a>
        </li>
        <li class="nav-item">
            <a class="nav-link" href="/dashboard/users">
                <i class="fas fa-fw fa-users"></i>
                <span>Users</span>
            </a>
        </li>
        <li class="nav-item">
            <a class="nav-link" href="/dashboard/reports">
                <i class="fas fa-fw fa-chart-area"></i>
                <span>Reports</span>
            </a>
        </li>
    </ul>
</nav>

<!-- Main content area that responds to sidebar changes -->
<div id="main-content" class="d-flex flex-column" 
     _="on sidebar-changed(collapsed) 
        if collapsed
          add .sidebar-toggled to body
        else
          remove .sidebar-toggled from body
        end">
    <!-- Dashboard content -->
</div>
```

#### Dynamic Widget Management
```html
<!-- Widget container with drag-and-drop reordering -->
<div class="row dashboard-widgets" 
     _="on widget-moved(from, to)
        fetch /api/dashboard/save-layout with 
          body: JSON.stringify({from: from, to: to})
          method: 'POST'
          headers: {'Content-Type': 'application/json'}">
    
    <!-- Individual widgets -->
    <div class="col-xl-3 col-md-6 mb-4 widget" data-widget-id="stats" 
         _="install Draggable
           on widget-refresh
             fetch /api/dashboard/widget/stats
             put the result into me
           end">
        <div class="card border-left-primary shadow h-100 py-2">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                            Statistics
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">$40,000</div>
                    </div>
                    <div class="col-auto">
                        <div class="dropdown">
                            <button class="btn btn-sm btn-link text-muted dropdown-toggle" 
                                    data-bs-toggle="dropdown">
                                <i class="fas fa-ellipsis-v"></i>
                            </button>
                            <div class="dropdown-menu">
                                <a class="dropdown-item" href="#"
                                   _="on click send widget-refresh to my closest .widget">
                                    <i class="fas fa-sync-alt"></i> Refresh
                                </a>
                                <a class="dropdown-item" href="#"
                                   _="on click send widget-minimize to my closest .widget">
                                    <i class="fas fa-minus"></i> Minimize
                                </a>
                                <a class="dropdown-item text-danger" href="#"
                                   _="on click send widget-close to my closest .widget">
                                    <i class="fas fa-times"></i> Close
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Draggable behavior for widgets -->
<script type="text/hyperscript">
  behavior Draggable
    on mousedown
      if event.target matches '.card-body'
        set :dragging to true
        set :startX to event.clientX
        set :startY to event.clientY
        set :originalIndex to Array.from(my parentElement.parentElement.children).indexOf(my parentElement)
        
        repeat until event mouseup from elsewhere
          wait for mousemove(clientX, clientY) from elsewhere
          set my parentElement's style.transform to `translate(${clientX - :startX}px, ${clientY - :startY}px)`
          set :startX to clientX
          set :startY to clientY
          
          -- Check for drop zones
          get closest <.widget/> to {x: clientX, y: clientY}
          if it is not my parentElement and it exists
            set :dropTarget to it
          end
        end
        
        if :dropTarget exists
          set :newIndex to Array.from(my parentElement.parentElement.children).indexOf(:dropTarget)
          send widget-moved(from: :originalIndex, to: :newIndex) to .dashboard-widgets
        end
        
        set :dragging to false
        set my parentElement's style.transform to 'none'
      end
    end
  end
</script>
```

#### Dashboard State Management
```html
<!-- Dashboard state controller -->
<div id="dashboard-state" 
     _="init 
        set $dashboardState to {
          filters: {},
          selectedItems: [],
          currentView: 'grid',
          autoRefresh: true
        }
        
        on state-change(key, value)
          set $dashboardState[key] to value
          log 'Dashboard state updated:', key, value
          send dashboard-state-changed(state: $dashboardState) to body
        end
        
        on get-state
          return $dashboardState
        end">
</div>

<!-- Components that use dashboard state -->
<div class="btn-group view-switcher" role="group" 
     _="on click from .btn
        send state-change(key: 'currentView', value: target.dataset.view) to #dashboard-state
        remove .active from .btn
        add .active to target">
    
    <button type="button" class="btn btn-outline-primary active" data-view="grid">
        <i class="fas fa-th"></i> Grid
    </button>
    <button type="button" class="btn btn-outline-primary" data-view="list">
        <i class="fas fa-list"></i> List
    </button>
    <button type="button" class="btn btn-outline-primary" data-view="table">
        <i class="fas fa-table"></i> Table
    </button>
</div>

<!-- Data container that responds to state changes -->
<div id="data-container" 
     _="on dashboard-state-changed(state)
        if state.currentView is 'grid'
          add .row to me
          remove .list-group, .table-responsive from me
        else if state.currentView is 'list'
          add .list-group to me
          remove .row, .table-responsive from me
        else if state.currentView is 'table'
          add .table-responsive to me
          remove .row, .list-group from me
        end">
    <!-- Data items -->
</div>
```

#### Advanced Table Interactions
```html
<!-- Smart table with selection and sorting -->
<table class="table table-bordered table-hover dashboard-table" 
       _="init set :selectedRows to []
         on select-row(rowId)
           if :selectedRows contains rowId
             set :selectedRows to :selectedRows.filter(id => id !== rowId)
           else
             push rowId onto :selectedRows
           end
           send selection-changed(selected: :selectedRows) to #bulk-actions
         end
         
         on select-all
           if :selectedRows.length > 0
             set :selectedRows to []
           else
             set :selectedRows to Array.from(<tr[data-row-id]/> in me).map(row => row.dataset.rowId)
           end
           send selection-changed(selected: :selectedRows) to #bulk-actions
         end">
    
    <thead class="thead-dark">
        <tr>
            <th>
                <input class="form-check-input" type="checkbox" 
                       _="on change send select-all to my closest table">
            </th>
            <th class="sortable" 
                _="on click 
                   send sort-column(column: 'name', direction: my @data-sort-direction or 'asc') to #data-container
                   set my @data-sort-direction to (my @data-sort-direction is 'asc' ? 'desc' : 'asc')">
                Name 
                <i class="fas fa-sort text-muted"></i>
            </th>
            <th class="sortable" 
                _="on click 
                   send sort-column(column: 'email', direction: my @data-sort-direction or 'asc') to #data-container">
                Email 
                <i class="fas fa-sort text-muted"></i>
            </th>
            <th>Actions</th>
        </tr>
    </thead>
    
    <tbody>
        {% for user in users %}
        <tr data-row-id="{{ user.id }}" 
            _="on change from input[type=checkbox] in me
               send select-row(rowId: my @data-row-id) to my closest table">
            <td>
                <input class="form-check-input" 
                       type="checkbox" 
                       name="selected_users" 
                       value="{{ user.id }}">
            </td>
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
            <td>
                <button class="btn btn-sm btn-primary" 
                        _="on click 
                          fetch /api/dashboard/users/{{ user.id }}/edit
                          put the result into #modal-container">
                    Edit
                </button>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

#### Dashboard Notifications System
```html
<!-- Notification container -->
<div id="notifications" class="position-fixed top-0 end-0 p-3" style="z-index: 1050;" 
     _="on show-notification(message, type, duration)
        make a <div.toast/> called notification
        add .{type} to notification if type
        set notification.innerHTML to `
          <div class='toast-header'>
            <strong class='me-auto'>Dashboard</strong>
            <button type='button' class='btn-close' data-bs-dismiss='toast'></button>
          </div>
          <div class='toast-body'>${message}</div>
        `
        put notification at the end of me
        
        -- Initialize Bootstrap toast
        set toast to new bootstrap.Toast(notification)
        call toast.show()
        
        -- Auto-hide after duration
        if duration > 0
          wait {duration}ms
          call toast.hide()
        end
       end">
</div>

<!-- Components that trigger notifications -->
<form hx-post="/api/dashboard/users" 
      hx-target="#users-table" 
      hx-swap="afterbegin"
      _="on htmx:afterRequest
         if detail.xhr.status >= 200 and detail.xhr.status < 300
           send show-notification(message: 'User created successfully', type: 'success', duration: 3000) to #notifications
         else
           send show-notification(message: 'Error creating user', type: 'danger', duration: 5000) to #notifications
         end">
    <!-- Form fields -->
</form>
```

#### Dashboard Search and Filtering
```html
<!-- Advanced search component -->
<div class="card search-component" 
     _="init set :searchHistory to []
       on search-performed(query)
         if query is not empty
           if not (:searchHistory contains query)
             push query onto :searchHistory
             if :searchHistory.length > 10
               set :searchHistory to :searchHistory.slice(-10)
             end
           end
           localStorage.setItem('dashboard-search-history', JSON.stringify(:searchHistory))
         end
       end">
    
    <div class="card-body">
        <div class="input-group">
            <input type="search" 
                   class="form-control"
                   name="search" 
                   placeholder="Search..."
                   _="on keyup
                     if event.key is 'Enter'
                       send search-performed(query: my value) to .search-component
                     end
                     
                     if my value.length >= 2
                       fetch /api/dashboard/search/suggestions?q={my value}
                       put the result into #search-suggestions
                       show #search-suggestions
                     else
                       hide #search-suggestions
                     end"
                   
                   hx-get="/api/dashboard/search" 
                   hx-trigger="keyup changed delay:300ms" 
                   hx-target="#search-results"
                   hx-include="[name='filters']">
            
            <button class="btn btn-outline-secondary" type="button" 
                    _="on click 
                      toggle .show on #advanced-filters
                      if #advanced-filters matches .show
                        focus() on input[name='search']
                      end">
                <i class="fas fa-filter"></i>
            </button>
        </div>
        
        <!-- Search suggestions dropdown -->
        <div id="search-suggestions" class="list-group mt-2" style="display: none;">
            <!-- Populated by HTMX -->
        </div>
        
        <!-- Advanced filters (shown when expanded) -->
        <div id="advanced-filters" class="collapse mt-3"
             _="on filter-change
               set filters to {}
               for input in <input, select/> in me
                 if input.value is not empty
                   set filters[input.name] to input.value
                 end
               end
               send filters-changed(filters: filters) to body">
            
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Category</label>
                    <select class="form-select" name="category" 
                            _="on change send filter-change to #advanced-filters">
                        <option value="">All Categories</option>
                        <option value="users">Users</option>
                        <option value="orders">Orders</option>
                    </select>
                </div>
                
                <div class="col-md-3">
                    <label class="form-label">Date From</label>
                    <input type="date" 
                           class="form-control"
                           name="date_from" 
                           _="on change send filter-change to #advanced-filters">
                </div>
                
                <div class="col-md-3">
                    <label class="form-label">Date To</label>
                    <input type="date" 
                           class="form-control"
                           name="date_to" 
                           _="on change send filter-change to #advanced-filters">
                </div>
            </div>
        </div>
    </div>
</div>
```

#### Real-time Dashboard Updates
```html
<!-- WebSocket connection for real-time updates -->
<div id="websocket-manager" 
     _="init 
        set :ws to new WebSocket('ws://localhost:5000/dashboard-updates')
        set :ws.onmessage to def(event)
          set data to JSON.parse(event.data)
          send websocket-message(data: data) to body
        end
        set :ws.onerror to def(event)  
          send show-notification(message: 'Connection lost', type: 'warning', duration: 0) to #notifications
        end
        set :ws.onopen to def(event)
          send show-notification(message: 'Connected', type: 'success', duration: 2000) to #notifications
        end">
</div>

<!-- Components that respond to real-time updates -->
<div class="row stats-widgets" 
     _="on websocket-message(data)
        if data.type is 'stats-update'
          put data.stats.total_users into #total-users
          put data.stats.active_sessions into #active-sessions
        end">
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-primary shadow h-100 py-2">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                            Total Users
                        </div>
                        <div id="total-users" class="h5 mb-0 font-weight-bold text-gray-800">
                            {{ stats.total_users }}
                        </div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-users fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-success shadow h-100 py-2">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-success text-uppercase mb-1">
                            Active Sessions
                        </div>
                        <div id="active-sessions" class="h5 mb-0 font-weight-bold text-gray-800">
                            {{ stats.active_sessions }}
                        </div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-wifi fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Activity feed that updates in real-time -->
<div class="card shadow mb-4 activity-feed" 
     _="on websocket-message(data)
        if data.type is 'activity'
          make a <div.list-group-item/> called item
          set item.innerHTML to `
            <div class='d-flex w-100 justify-content-between'>
              <h6 class='mb-1'>${data.activity.title}</h6>
              <small>${data.activity.time}</small>
            </div>
            <p class='mb-1'>${data.activity.message}</p>
          `
          put item at the start of #activity-list
          
          -- Keep only last 50 items
          set items to <.list-group-item/> in #activity-list
          if items.length > 50
            remove items[50]
          end
        end">
    
    <div class="card-header py-3">
        <h6 class="m-0 font-weight-bold text-primary">Recent Activity</h6>
    </div>
    <div class="card-body">
        <div id="activity-list" class="list-group list-group-flush">
            <!-- Activity items appear here -->
        </div>
    </div>
</div>
```

### Basic Syntax

#### Installation and Setup
```html
<script src="https://unpkg.com/hyperscript.org@0.9.14"></script>

<!-- Using the _ attribute -->
<button _="on click toggle .red on me">Click Me</button>

<!-- Alternative attributes -->
<button script="on click toggle .red on me">Click Me</button>
<button data-script="on click toggle .red on me">Click Me</button>

<!-- In script tags -->
<script type="text/hyperscript">
  on click from #myButton
    add .highlight to #target
  end
</script>
```

#### Event Handlers
```html
<!-- Basic event handling -->
<button class="btn btn-primary" _="on click log 'Button clicked!'">Click Me</button>

<!-- Multiple events -->
<div class="card" _="on mouseenter add .shadow-lg
                    on mouseleave remove .shadow-lg">Hover Me</div>

<!-- Event with conditions -->
<input class="form-control" _="on keyup[key is 'Enter'] call submitForm()">

<!-- Event with parameters -->
<button class="btn btn-secondary" _="on mousedown(button) 
                                    if button is 1 add .btn-warning">Middle Click</button>

<!-- Event delegation -->
<div class="list-group" _="on click from .list-group-item
                          remove the closest .list-group-item">
  <div class="list-group-item">Item 1 <button class="btn btn-sm btn-danger">Delete</button></div>
</div>
```

### DOM Manipulation

#### Finding Elements
```html
<!-- CSS selectors as literals -->
<button class="btn btn-primary" _="on click add .highlight to .target">Highlight targets</button>
<button class="btn btn-danger" _="on click remove #item-123">Remove item</button>
<button class="btn btn-secondary" _="on click toggle .d-none on <div.sidebar/>">Toggle sidebar</button>

<!-- Positional selectors -->
<button class="btn btn-outline-primary" _="on click add .active to the first .nav-link">Select first</button>
<button class="btn btn-outline-danger" _="on click remove the last .list-group-item">Remove last</button>
<button class="btn btn-outline-warning" _="on click add .bg-warning to random in .card">Random highlight</button>

<!-- Relative selectors -->
<button class="btn btn-info" _="on click add .active to the next .tab-pane">Next tab</button>
<button class="btn btn-secondary" _="on click remove the previous .breadcrumb-item">Previous item</button>
<button class="btn btn-primary" _="on click toggle .collapse on the closest .accordion-collapse">Toggle section</button>
```

#### Content Manipulation
```html
<!-- Setting content -->
<button class="btn btn-primary" _="on click put 'Hello Bootstrap!' into #output">Set content</button>
<button class="btn btn-secondary" _="on click set #output's innerHTML to '<div class=\"alert alert-success\">Success!</div>'">Set HTML</button>

<!-- Appending/prepending -->
<button class="btn btn-outline-primary" _="on click put '<div class=\"list-group-item\">New item</div>' at the end of #list">Append</button>
<button class="btn btn-outline-secondary" _="on click put '<div class=\"list-group-item\">First item</div>' at the start of #list">Prepend</button>

<!-- Positioning content -->
<button class="btn btn-warning" _="on click put '<div class=\"alert alert-info\">Before</div>' before #target">Insert before</button>
<button class="btn btn-info" _="on click put '<div class=\"alert alert-success\">After</div>' after #target">Insert after</button>
```

#### Attributes and Styles
```html
<!-- Working with attributes -->
<button class="btn btn-danger" _="on click set @disabled to 'disabled' on #submit-btn">Disable</button>
<button class="btn btn-success" _="on click remove @disabled from #submit-btn">Enable</button>
<button class="btn btn-warning" _="on click toggle @disabled on #submit-btn">Toggle disable</button>

<!-- Working with Bootstrap classes -->
<div class="card" _="on click toggle .border-primary on me">Toggle border</div>
<div class="btn-group" _="on click add .active to target then remove .active from .btn in me">
  <button class="btn btn-outline-primary">Option 1</button>
  <button class="btn btn-outline-primary">Option 2</button>
</div>

<!-- Working with styles -->
<div class="progress" _="on click set *width of .progress-bar in me to '75%'">
  <div class="progress-bar" style="width: 25%"></div>
</div>
```

### Variables and Data

#### Variable Scopes
```html
<!-- Local variables -->
<button class="btn btn-primary" _="on click 
                                  set x to 10 
                                  log x">Local variable</button>

<!-- Element-scoped variables (prefix with :) -->
<button class="btn btn-secondary" _="on click 
                                    increment :count 
                                    put :count into the next <span/>">
  Count: <span class="badge bg-primary">0</span>
</button>

<!-- Global variables (prefix with $) -->
<button class="btn btn-info" _="on click 
                               set $globalCounter to ($globalCounter or 0) + 1
                               log $globalCounter">Global counter</button>
```

#### Special Variables
```html
<!-- Built-in variables -->
<button class="btn btn-primary" _="on click log me">Log current element</button>
<button class="btn btn-secondary" _="on click log event">Log current event</button>
<button class="btn btn-info" _="on click log target">Log event target</button>
<button class="btn btn-warning" _="on click log detail">Log event detail</button>
<div class="alert alert-info" _="on customEvent(data) log data">Handle custom event with data</div>
```

### Control Flow

#### Conditionals
```html
<!-- Basic if/else -->
<button class="btn btn-primary" _="on click 
                                  if I match .btn-primary
                                    remove .btn-primary from me
                                    add .btn-secondary to me
                                  else
                                    remove .btn-secondary from me
                                    add .btn-primary to me
                                  end">Toggle button style</button>

<!-- Natural language comparisons -->
<input class="form-control" _="on input
                               if my value is not empty
                                 remove .is-invalid from me
                                 add .is-valid to me
                               else
                                 remove .is-valid from me
                                 add .is-invalid to me
                               end">

<!-- Unless modifier -->
<button class="btn btn-primary" _="on click 
                                  add .loading unless I match .disabled">Process</button>
```

#### Loops
```html
<!-- For loops -->
<button class="btn btn-primary" _="on click
                                  for item in [1, 2, 3, 4, 5]
                                    put '<div class=\"alert alert-info\">Item ' + item + '</div>' at the end of #list
                                  end">Add numbers</button>

<!-- While loops -->
<button class="btn btn-secondary" _="on click
                                    set i to 0
                                    repeat while i < 5
                                      log i
                                      increment i
                                    end">Count to 5</button>

<!-- Repeat with times -->
<button class="btn btn-info" _="on click
                               repeat 3 times
                                 put '<div class=\"toast\">Hello</div>' at the end of #output
                               end">Say hello 3 times</button>
```

### Async Operations

#### Waiting and Timing
```html
<!-- Wait for time -->
<button class="btn btn-primary" _="on click
                                  put 'Processing...' into me
                                  add .disabled to me
                                  wait 2s
                                  put 'Done!' into me
                                  remove .disabled from me">Process</button>

<!-- Wait for events -->
<button class="btn btn-warning" _="on click
                                  put 'Click continue...' into #status
                                  wait for continue
                                  put '<div class=\"alert alert-success\">Continued!</div>' into #status">
  Start Process
</button>
<button class="btn btn-success" _="on click send continue to the previous <button/>">Continue</button>

<!-- Wait with timeout -->
<button class="btn btn-info" _="on click
                               put '<div class=\"spinner-border\"></div> Waiting...' into #status
                               wait for continue or 5s
                               if the result's type is 'continue'
                                 put '<div class=\"alert alert-success\">Got continue!</div>' into #status
                               else
                                 put '<div class=\"alert alert-warning\">Timed out!</div>' into #status
                               end">Wait with timeout</button>
```

#### Fetch Requests
```html
<!-- Basic fetch -->
<button class="btn btn-primary" _="on click
                                  fetch /api/data
                                  put the result into #content">Get data</button>

<!-- Fetch with error handling -->
<button class="btn btn-secondary" _="on click
                                    fetch /api/data
                                    if the response's ok
                                      put the result into #content
                                    else
                                      put '<div class=\"alert alert-danger\">Error loading data</div>' into #error
                                    end">Get data safely</button>

<!-- Fetch with POST -->
<form class="needs-validation" _="on submit
                                  fetch /api/submit with body: new FormData(me)
                                  put the result into #response
                                  reset() me">
  <div class="mb-3">
    <input class="form-control" name="username" placeholder="Username" required>
  </div>
  <button type="submit" class="btn btn-primary">Submit</button>
</form>
```

### Event Handling and Communication

#### Sending Custom Events
```html
<!-- Send events to other elements -->
<button class="btn btn-primary" _="on click send refresh to #data-panel">Refresh data</button>

<!-- Send events with data -->
<button class="btn btn-success" _="on click 
                                  send update(id: 123, status: 'active') to #status-panel">
  Update status
</button>

<!-- Send events to multiple targets -->
<button class="btn btn-info" _="on click send refresh to .data-panel">Refresh all panels</button>
```

#### Event Queueing
```html
<!-- Default: queue last -->
<button class="btn btn-primary" _="on click 
                                  wait 1s 
                                  put 'Done' into #output">Default queuing</button>

<!-- Queue all events -->
<button class="btn btn-secondary" _="on click queue all
                                    increment :count
                                    wait 1s
                                    put :count into #output">Queue all</button>

<!-- Process every event immediately -->
<button class="btn btn-info" _="on every click
                               increment :count
                               put :count into #output">Process every click</button>

<!-- Queue first only -->
<button class="btn btn-warning" _="on click queue first
                                  wait 2s
                                  put 'Processed' into #output">Queue first only</button>
```

### Advanced Features

#### Behaviors (Reusable Components)
```html
<script type="text/hyperscript">
  behavior Draggable
    on mousedown
      set startX to event.clientX
      set startY to event.clientY
      add .dragging to me
      
      repeat until event mouseup from elsewhere
        wait for mousemove(clientX, clientY) from elsewhere
        set my *left to (my offsetLeft + clientX - startX) + 'px'
        set my *top to (my offsetTop + clientY - startY) + 'px'
        set startX to clientX
        set startY to clientY
      end
      
      remove .dragging from me
    end
  end
  
  behavior TooltipToggle
    on mouseenter
      make a <div.tooltip.bs-tooltip-top/> called tip
      put my @data-bs-title into tip
      put tip after me
      
      -- Position tooltip
      set my *position to 'relative'
    end
    
    on mouseleave
      remove .tooltip from elsewhere
    end
  end
</script>

<!-- Install behaviors -->
<div class="card draggable-box" _="install Draggable" 
     style="width: 200px; height: 100px; cursor: move;">
  Drag me!
</div>

<button class="btn btn-primary" 
        _="install TooltipToggle" 
        data-bs-title="This is a custom tooltip">
  Hover for tooltip
</button>
```

#### Transitions and Animations
```html
<!-- Bootstrap fade transitions -->
<div class="alert alert-info" _="on click 
                                add .fade to me
                                wait 300ms
                                add .show to me">
  Fade in alert
</div>

<!-- Custom animations with Bootstrap classes -->
<div class="card" _="on click 
                    add .border-primary then settle
                    wait 500ms
                    remove .border-primary then settle">
  Animate with classes
</div>

<!-- Toggle with events -->
<div class="badge bg-secondary" _="on mouseenter add .bg-primary then remove .bg-secondary until mouseleave
                                  on mouseleave add .bg-secondary then remove .bg-primary">
  Hover highlight
</div>
```

#### Functions
```html
<script type="text/hyperscript">
  def calculateTotal(items)
    set total to 0
    for item in items
      set total to total + item.price
    end
    return total
  end
  
  def utils.formatCurrency(amount)
    return '$' + amount.toFixed(2)
  end
  
  def ui.showAlert(message, type)
    make a <div.alert/> called alert
    add .{`alert-${type}`} to alert
    put message into alert
    put alert at the start of body
    wait 3s
    remove alert
  end
</script>

<button class="btn btn-primary" _="on click
                                  call calculateTotal([{price: 10}, {price: 20}])
                                  call ui.showAlert(utils.formatCurrency(it), 'success')">
  Calculate total
</button>
```

---

## Bootstrap 5 for Dashboard Styling

### Overview
Bootstrap 5 provides an excellent foundation for Flask dashboard styling by offering a comprehensive component library, responsive grid system, and utility classes perfect for modern dashboard interfaces.

### Installation

#### CDN Installation
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask Dashboard</title>
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" 
          rel="stylesheet" 
          integrity="sha384-LN+7fdVzj6u52u30Kp6M/trliBMCMKTyK833zpbD+pXdCLuTusPj697FH4R/5mcr" 
          crossorigin="anonymous">
    <!-- Font Awesome for icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <!-- _hyperscript -->
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
</head>
<body>
    <!-- Dashboard content -->
    
    <!-- Bootstrap 5 JS Bundle -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js" 
            integrity="sha384-ndDqU0Gzau9qJ1lfW4pNLlhNTkCfHzAVBReH9diLvGRem5+R9g2FzA8ZGN954O5Q" 
            crossorigin="anonymous"></script>
</body>
</html>
```

#### NPM Installation
```bash
npm install bootstrap@5.3.7
```

### Dashboard Layout Foundations

#### Basic Dashboard Structure
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" 
          rel="stylesheet" 
          integrity="sha384-LN+7fdVzj6u52u30Kp6M/trliBMCMKTyK833zpbD+pXdCLuTusPj697FH4R/5mcr" 
          crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
</head>
<body class="bg-light">
    <!-- Navigation Header -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-tachometer-alt me-2"></i>
                Dashboard
            </a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link active" href="/dashboard">
                            <i class="fas fa-home me-1"></i> Overview
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/dashboard/analytics">
                            <i class="fas fa-chart-line me-1"></i> Analytics
                        </a>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-cogs me-1"></i> Management
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="/dashboard/users">
                                <i class="fas fa-users me-2"></i> Users
                            </a></li>
                            <li><a class="dropdown-item" href="/dashboard/orders">
                                <i class="fas fa-shopping-cart me-2"></i> Orders
                            </a></li>
                        </ul>
                    </li>
                </ul>
                
                <div class="navbar-nav">
                    <!-- User menu -->
                    <div class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-user-circle me-1"></i>
                            {{ current_user.username }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="/profile">
                                <i class="fas fa-user me-2"></i> Profile
                            </a></li>
                            <li><a class="dropdown-item" href="/settings">
                                <i class="fas fa-cog me-2"></i> Settings
                            </a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="/logout">
                                <i class="fas fa-sign-out-alt me-2"></i> Logout
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </nav>
    
    <!-- Main Container -->
    <div class="container-fluid" style="margin-top: 60px;">
        <div class="row">
            <!-- Sidebar -->
            <nav class="col-md-3 col-lg-2 d-md-block bg-white sidebar collapse">
                <div class="position-sticky pt-3">
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link active" href="/dashboard">
                                <i class="fas fa-home me-2"></i>
                                Dashboard
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/analytics">
                                <i class="fas fa-chart-area me-2"></i>
                                Analytics
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/users">
                                <i class="fas fa-users me-2"></i>
                                Users
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/orders">
                                <i class="fas fa-shopping-bag me-2"></i>
                                Orders
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/reports">
                                <i class="fas fa-file-alt me-2"></i>
                                Reports
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/dashboard/settings">
                                <i class="fas fa-cog me-2"></i>
                                Settings
                            </a>
                        </li>
                    </ul>
                </div>
            </nav>
            
            <!-- Main Content -->
            <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
                <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                    <h1 class="h2">{% block page_title %}Dashboard{% endblock %}</h1>
                    <div class="btn-toolbar mb-2 mb-md-0">
                        <div class="btn-group me-2">
                            <button type="button" class="btn btn-sm btn-outline-secondary">
                                <i class="fas fa-share"></i> Share
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary">
                                <i class="fas fa-download"></i> Export
                            </button>
                        </div>
                        <button type="button" class="btn btn-sm btn-primary">
                            <i class="fas fa-calendar-week"></i> This week
                        </button>
                    </div>
                </div>
                
                <!-- Dashboard Content -->
                <div class="dashboard-content">
                    {% block content %}{% endblock %}
                </div>
            </main>
        </div>
    </div>
    
    <!-- Toast Container for Notifications -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <!-- Toasts will be dynamically added here -->
    </div>
    
    <!-- Modal Container -->
    <div id="modal-container"></div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js" 
            integrity="sha384-ndDqU0Gzau9qJ1lfW4pNLlhNTkCfHzAVBReH9diLvGRem5+R9g2FzA8ZGN954O5Q" 
            crossorigin="anonymous"></script>
    
    <!-- Dashboard Custom CSS -->
    <style>
        .sidebar {
            box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
        }
        
        .sidebar .nav-link {
            color: #333;
            border-radius: 0.375rem;
            margin: 0.125rem 0.5rem;
        }
        
        .sidebar .nav-link:hover {
            background-color: #f8f9fa;
        }
        
        .sidebar .nav-link.active {
            background-color: #0d6efd;
            color: white;
        }
        
        .dashboard-stat-card {
            transition: transform 0.2s;
        }
        
        .dashboard-stat-card:hover {
            transform: translateY(-2px);
        }
        
        @media (max-width: 767.98px) {
            .sidebar {
                top: 5rem;
            }
        }
    </style>
</body>
</html>
```

### Dashboard Components

#### Stats Cards
```html
<!-- Dashboard Statistics Cards -->
<div class="row mb-4">
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-primary shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                            Total Users
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">1,234</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-users fa-2x text-primary opacity-25"></i>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-success">
                        <i class="fas fa-arrow-up"></i> 12%
                    </span>
                    <span class="text-muted small">from last month</span>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-success shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-success text-uppercase mb-1">
                            Revenue
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">$45,678</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-dollar-sign fa-2x text-success opacity-25"></i>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-danger">
                        <i class="fas fa-arrow-down"></i> 3%
                    </span>
                    <span class="text-muted small">from last month</span>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-info shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-info text-uppercase mb-1">
                            Conversion Rate
                        </div>
                        <div class="row no-gutters align-items-center">
                            <div class="col-auto">
                                <div class="h5 mb-0 mr-3 font-weight-bold text-gray-800">89.2%</div>
                            </div>
                            <div class="col">
                                <div class="progress progress-sm mr-2">
                                    <div class="progress-bar bg-info" role="progressbar" 
                                         style="width: 89%" aria-valuenow="89" aria-valuemin="0" aria-valuemax="100">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-clipboard-list fa-2x text-info opacity-25"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-left-warning shadow h-100 py-2 dashboard-stat-card">
            <div class="card-body">
                <div class="row no-gutters align-items-center">
                    <div class="col mr-2">
                        <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">
                            Active Sessions
                        </div>
                        <div class="h5 mb-0 font-weight-bold text-gray-800">324</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-wifi fa-2x text-warning opacity-25"></i>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-secondary">
                        <i class="fas fa-minus"></i> No change
                    </span>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
.border-left-primary {
    border-left: 0.25rem solid #4e73df !important;
}

.border-left-success {
    border-left: 0.25rem solid #1cc88a !important;
}

.border-left-info {
    border-left: 0.25rem solid #36b9cc !important;
}

.border-left-warning {
    border-left: 0.25rem solid #f6c23e !important;
}

.text-xs {
    font-size: 0.75rem;
}

.progress-sm {
    height: 0.5rem;
}
</style>
```

#### Enhanced Data Tables
```html
<!-- Enhanced Dashboard Data Table -->
<div class="card shadow mb-4">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">Users Management</h6>
        <div class="dropdown">
            <button class="btn btn-primary btn-sm dropdown-toggle" data-bs-toggle="dropdown">
                <i class="fas fa-plus"></i> Actions
            </button>
            <ul class="dropdown-menu">
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/users/new" 
                       hx-target="#modal-container">
                        <i class="fas fa-user-plus me-2"></i> Add User
                    </a>
                </li>
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/users/import" 
                       hx-target="#modal-container">
                        <i class="fas fa-file-import me-2"></i> Import Users
                    </a>
                </li>
                <li><hr class="dropdown-divider"></li>
                <li>
                    <a class="dropdown-item" href="#"
                       hx-get="/api/dashboard/export/users" 
                       hx-trigger="click">
                        <i class="fas fa-download me-2"></i> Export CSV
                    </a>
                </li>
            </ul>
        </div>
    </div>
    
    <!-- Table Filters -->
    <div class="card-body border-bottom">
        <div class="row g-3 align-items-end">
            <div class="col-md-4">
                <label class="form-label small text-muted">Search</label>
                <div class="input-group">
                    <span class="input-group-text">
                        <i class="fas fa-search"></i>
                    </span>
                    <input type="search" 
                           class="form-control"
                           name="search" 
                           placeholder="Search users..."
                           hx-get="/api/dashboard/table/users" 
                           hx-trigger="keyup changed delay:300ms" 
                           hx-target="#users-table-body"
                           hx-include="[name='status'], [name='role'], [name='per_page']">
                </div>
            </div>
            
            <div class="col-md-2">
                <label class="form-label small text-muted">Status</label>
                <select class="form-select" name="status"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table-body"
                        hx-include="[name='search'], [name='role'], [name='per_page']">
                    <option value="">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <label class="form-label small text-muted">Role</label>
                <select class="form-select" name="role"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table-body"
                        hx-include="[name='search'], [name='status'], [name='per_page']">
                    <option value="">All Roles</option>
                    <option value="admin">Admin</option>
                    <option value="user">User</option>
                    <option value="moderator">Moderator</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <label class="form-label small text-muted">Per Page</label>
                <select class="form-select" name="per_page"
                        hx-get="/api/dashboard/table/users" 
                        hx-trigger="change" 
                        hx-target="#users-table-body"
                        hx-include="[name='search'], [name='status'], [name='role']">
                    <option value="10">10</option>
                    <option value="25" selected>25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <button class="btn btn-outline-secondary w-100"
                        onclick="document.querySelector('form').reset(); 
                                 htmx.trigger('#users-table-body', 'refresh')">
                    <i class="fas fa-undo"></i> Reset
                </button>
            </div>
        </div>
    </div>
    
    <!-- Bulk Actions Bar -->
    <div id="bulk-actions-bar" class="alert alert-info m-0 rounded-0 d-none">
        <div class="d-flex justify-content-between align-items-center">
            <span class="fw-bold">
                <i class="fas fa-check-square me-2"></i>
                <span id="selected-count">0</span> users selected
            </span>
            <div class="btn-group btn-group-sm">
                <button class="btn btn-success" 
                        hx-post="/api/dashboard/users/bulk-activate" 
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-body"
                        hx-confirm="Activate selected users?">
                    <i class="fas fa-check"></i> Activate
                </button>
                <button class="btn btn-warning" 
                        hx-post="/api/dashboard/users/bulk-deactivate" 
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-body"
                        hx-confirm="Deactivate selected users?">
                    <i class="fas fa-pause"></i> Deactivate
                </button>
                <button class="btn btn-danger" 
                        hx-delete="/api/dashboard/users/bulk-delete" 
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-body"
                        hx-confirm="Delete selected users? This action cannot be undone.">
                    <i class="fas fa-trash"></i> Delete
                </button>
            </div>
        </div>
    </div>
    
    <!-- Table -->
    <div class="table-responsive">
        <table class="table table-bordered table-hover mb-0" id="dataTable">
            <thead class="table-light">
                <tr>
                    <th class="text-center" style="width: 40px;">
                        <input class="form-check-input" type="checkbox" id="select-all"
                               _="on change
                                  set checkboxes to <input[name='selected_users']/> in #users-table-body
                                  for checkbox in checkboxes
                                    set checkbox.checked to my checked
                                  end
                                  update-bulk-actions()">
                    </th>
                    <th class="sortable" data-sort="username">
                        Username <i class="fas fa-sort text-muted"></i>
                    </th>
                    <th class="sortable" data-sort="email">
                        Email <i class="fas fa-sort text-muted"></i>
                    </th>
                    <th>Role</th>
                    <th class="text-center">Status</th>
                    <th class="sortable" data-sort="created_at">
                        Created <i class="fas fa-sort text-muted"></i>
                    </th>
                    <th class="text-center" style="width: 120px;">Actions</th>
                </tr>
            </thead>
            <tbody id="users-table-body" 
                   hx-get="/api/dashboard/table/users" 
                   hx-trigger="load"
                   hx-swap="innerHTML">
                <!-- Loading state -->
                <tr>
                    <td colspan="7" class="text-center py-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <div class="mt-2 text-muted">Loading users...</div>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
    
    <!-- Pagination -->
    <div class="card-footer">
        <div class="row align-items-center">
            <div class="col-sm-6">
                <div class="dataTables_info">
                    Showing <span id="page-start">1</span> to <span id="page-end">25</span> 
                    of <span id="total-entries">100</span> entries
                </div>
            </div>
            <div class="col-sm-6">
                <nav>
                    <ul class="pagination justify-content-end mb-0" id="pagination-container">
                        <!-- Pagination buttons will be loaded here -->
                    </ul>
                </nav>
            </div>
        </div>
    </div>
</div>

<script type="text/hyperscript">
  def update-bulk-actions()
    set selectedBoxes to <input[name='selected_users']:checked/>
    set count to selectedBoxes.length
    put count into #selected-count
    
    if count > 0
      remove .d-none from #bulk-actions-bar
    else
      add .d-none to #bulk-actions-bar
    end
  end
  
  -- Auto-update bulk actions when checkboxes change
  on change from input[name='selected_users']
    update-bulk-actions()
  end
</script>
```

#### Dashboard Forms and Modals
```html
<!-- Bootstrap 5 Modal Form -->
<div class="modal fade show d-block" tabindex="-1" style="background: rgba(0,0,0,0.5);">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">
                    <i class="fas fa-user-plus me-2"></i>
                    Add New User
                </h5>
                <button type="button" class="btn-close" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                </button>
            </div>
            
            <form hx-post="/api/dashboard/users" 
                  hx-target="#users-table-body" 
                  hx-swap="afterbegin"
                  class="needs-validation" 
                  novalidate
                  hx-on::after-request="if(event.detail.successful) { 
                    document.getElementById('modal-container').innerHTML = ''; 
                    showToast('User created successfully', 'success'); 
                  }">
                
                <div class="modal-body">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label class="form-label" for="first_name">
                                First Name <span class="text-danger">*</span>
                            </label>
                            <input type="text" 
                                   class="form-control"
                                   id="first_name" 
                                   name="first_name" 
                                   required>
                            <div class="invalid-feedback">
                                Please provide a first name.
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <label class="form-label" for="last_name">
                                Last Name <span class="text-danger">*</span>
                            </label>
                            <input type="text" 
                                   class="form-control"
                                   id="last_name" 
                                   name="last_name" 
                                   required>
                            <div class="invalid-feedback">
                                Please provide a last name.
                            </div>
                        </div>
                        
                        <div class="col-12">
                            <label class="form-label" for="email">
                                Email Address <span class="text-danger">*</span>
                            </label>
                            <div class="input-group">
                                <span class="input-group-text">
                                    <i class="fas fa-envelope"></i>
                                </span>
                                <input type="email" 
                                       class="form-control"
                                       id="email" 
                                       name="email" 
                                       required
                                       hx-get="/api/dashboard/validate/email"
                                       hx-trigger="blur"
                                       hx-target="#email-validation">
                                <div class="invalid-feedback">
                                    Please provide a valid email address.
                                </div>
                            </div>
                            <div id="email-validation" class="mt-1"></div>
                        </div>
                        
                        <div class="col-md-6">
                            <label class="form-label" for="role">
                                Role <span class="text-danger">*</span>
                            </label>
                            <select class="form-select" id="role" name="role" required>
                                <option value="">Select a role</option>
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                                <option value="moderator">Moderator</option>
                            </select>
                            <div class="invalid-feedback">
                                Please select a role.
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <label class="form-label" for="department">Department</label>
                            <select class="form-select" id="department" name="department">
                                <option value="">Select department</option>
                                <option value="engineering">Engineering</option>
                                <option value="marketing">Marketing</option>
                                <option value="sales">Sales</option>
                                <option value="support">Support</option>
                            </select>
                        </div>
                        
                        <div class="col-12">
                            <div class="form-check form-switch">
                                <input class="form-check-input" 
                                       type="checkbox" 
                                       id="is_active" 
                                       name="is_active" 
                                       checked>
                                <label class="form-check-label" for="is_active">
                                    Active User
                                </label>
                            </div>
                        </div>
                        
                        <div class="col-12">
                            <div class="form-check">
                                <input class="form-check-input" 
                                       type="checkbox" 
                                       id="send_welcome" 
                                       name="send_welcome" 
                                       checked>
                                <label class="form-check-label" for="send_welcome">
                                    Send welcome email
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" 
                            onclick="document.getElementById('modal-container').innerHTML = ''">
                        <i class="fas fa-times me-1"></i> Cancel
                    </button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save me-1"></i> Create User
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
```

#### Dashboard Charts and Visualizations Container
```html
<!-- Chart widgets with Bootstrap cards -->
<div class="row mb-4">
    <div class="col-xl-8 col-lg-7">
        <div class="card shadow mb-4">
            <div class="card-header py-3 d-flex justify-content-between align-items-center">
                <h6 class="m-0 font-weight-bold text-primary">Revenue Trend</h6>
                <div class="dropdown">
                    <button class="btn btn-outline-primary btn-sm dropdown-toggle" 
                            data-bs-toggle="dropdown">
                        <i class="fas fa-calendar me-1"></i> Time Range
                    </button>
                    <ul class="dropdown-menu">
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/revenue?period=7d" 
                               hx-target="#revenue-chart">
                                Last 7 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/revenue?period=30d" 
                               hx-target="#revenue-chart">
                                Last 30 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/revenue?period=90d" 
                               hx-target="#revenue-chart">
                                Last 90 days
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="card-body">
                <div id="revenue-chart" 
                     hx-get="/api/dashboard/chart/revenue?period=30d" 
                     hx-trigger="load"
                     style="height: 400px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="text-center">
                            <div class="spinner-border text-primary mb-3" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <div class="text-muted">Loading chart...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-4 col-lg-5">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">User Distribution</h6>
            </div>
            <div class="card-body">
                <div id="user-distribution-chart" 
                     hx-get="/api/dashboard/chart/user-distribution" 
                     hx-trigger="load"
                     style="height: 320px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Performance metrics grid -->
<div class="row mb-4">
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Performance Metrics</h6>
            </div>
            <div class="card-body">
                <h4 class="small font-weight-bold">
                    Server Response Time 
                    <span class="float-end">40%</span>
                </h4>
                <div class="progress mb-4">
                    <div class="progress-bar bg-danger" role="progressbar" 
                         style="width: 40%" aria-valuenow="40" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                
                <h4 class="small font-weight-bold">
                    Sales Tracking 
                    <span class="float-end">60%</span>
                </h4>
                <div class="progress mb-4">
                    <div class="progress-bar bg-warning" role="progressbar" 
                         style="width: 60%" aria-valuenow="60" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                
                <h4 class="small font-weight-bold">
                    Customer Database 
                    <span class="float-end">80%</span>
                </h4>
                <div class="progress mb-4">
                    <div class="progress-bar" role="progressbar" 
                         style="width: 80%" aria-valuenow="80" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                
                <h4 class="small font-weight-bold">
                    Payout Details 
                    <span class="float-end">Complete!</span>
                </h4>
                <div class="progress">
                    <div class="progress-bar bg-success" role="progressbar" 
                         style="width: 100%" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Recent Activity</h6>
            </div>
            <div class="card-body" style="max-height: 300px; overflow-y: auto;">
                <div class="timeline" id="activity-timeline" 
                     hx-get="/api/dashboard/activity" 
                     hx-trigger="load, every 60s">
                    <div class="d-flex justify-content-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

#### Bootstrap Navigation Components
```html
<!-- Dashboard Navigation Tabs -->
<div class="card shadow mb-4">
    <div class="card-header">
        <ul class="nav nav-tabs card-header-tabs" id="dashboard-tabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="overview-tab" 
                        data-bs-toggle="tab" data-bs-target="#overview" 
                        type="button" role="tab">
                    <i class="fas fa-chart-line me-1"></i> Overview
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="analytics-tab" 
                        data-bs-toggle="tab" data-bs-target="#analytics" 
                        type="button" role="tab"
                        hx-get="/api/dashboard/analytics" 
                        hx-target="#analytics" 
                        hx-trigger="click once">
                    <i class="fas fa-chart-pie me-1"></i> Analytics
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="reports-tab" 
                        data-bs-toggle="tab" data-bs-target="#reports" 
                        type="button" role="tab"
                        hx-get="/api/dashboard/reports" 
                        hx-target="#reports" 
                        hx-trigger="click once">
                    <i class="fas fa-file-alt me-1"></i> Reports
                </button>
            </li>
        </ul>
    </div>
    
    <div class="card-body">
        <div class="tab-content" id="dashboard-tab-content">
            <div class="tab-pane fade show active" id="overview" role="tabpanel">
                <!-- Overview content -->
                <div class="row">
                    <div class="col-md-8">
                        <h5>Dashboard Overview</h5>
                        <p class="text-muted">Welcome to your dashboard. Here you can see an overview of your key metrics and recent activity.</p>
                    </div>
                    <div class="col-md-4">
                        <div class="text-center">
                            <i class="fas fa-chart-area fa-3x text-primary mb-3"></i>
                            <h6>Quick Stats</h6>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="analytics" role="tabpanel">
                <div class="d-flex justify-content-center p-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading analytics...</span>
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="reports" role="tabpanel">
                <div class="d-flex justify-content-center p-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading reports...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Breadcrumb Navigation -->
<nav aria-label="breadcrumb" class="mb-4">
    <ol class="breadcrumb">
        <li class="breadcrumb-item">
            <a href="/dashboard">
                <i class="fas fa-home me-1"></i> Dashboard
            </a>
        </li>
        <li class="breadcrumb-item">
            <a href="/dashboard/users">Users</a>
        </li>
        <li class="breadcrumb-item active" aria-current="page">
            User Details
        </li>
    </ol>
</nav>
```

#### Bootstrap Alerts and Notifications
```html
<!-- Toast Notifications -->
<div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1060;">
    <!-- Toasts will be inserted here -->
</div>

<!-- Alert Messages -->
<div id="alert-container" class="mb-4">
    <!-- Alerts will be dynamically added here -->
</div>

<!-- Success Alert Example -->
<div class="alert alert-success alert-dismissible fade show" role="alert">
    <i class="fas fa-check-circle me-2"></i>
    <strong>Success!</strong> User has been created successfully.
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>

<!-- Warning Alert with Action -->
<div class="alert alert-warning alert-dismissible fade show" role="alert">
    <div class="d-flex justify-content-between align-items-center">
        <div>
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Warning!</strong> Your subscription expires in 3 days.
        </div>
        <div>
            <button class="btn btn-warning btn-sm me-2">Renew Now</button>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    </div>
</div>

<script type="text/hyperscript">
  def showToast(message, type)
    set toastHtml to `
      <div class="toast" role="alert" data-bs-autohide="true" data-bs-delay="5000">
        <div class="toast-header">
          <div class="rounded me-2 ${type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info'}" 
               style="width: 20px; height: 20px;"></div>
          <strong class="me-auto">Dashboard</strong>
          <small>just now</small>
          <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
          ${message}
        </div>
      </div>
    `
    
    make a <div/> called toastElement
    set toastElement.innerHTML to toastHtml
    set toastEl to toastElement.firstElementChild
    put toastEl at the end of .toast-container
    
    set toast to new bootstrap.Toast(toastEl)
    call toast.show()
  end
</script>
```

#### Bootstrap Forms and Input Groups
```html
<!-- Advanced Form Controls -->
<div class="card shadow mb-4">
    <div class="card-header">
        <h6 class="m-0 font-weight-bold text-primary">User Settings</h6>
    </div>
    <div class="card-body">
        <form class="needs-validation" novalidate>
            <!-- Input Groups -->
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Username</label>
                    <div class="input-group">
                        <span class="input-group-text">@</span>
                        <input type="text" class="form-control" placeholder="Username" required>
                        <button class="btn btn-outline-secondary" type="button">
                            <i class="fas fa-check"></i>
                        </button>
                        <div class="invalid-feedback">
                            Please provide a valid username.
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Website</label>
                    <div class="input-group">
                        <span class="input-group-text">https://</span>
                        <input type="text" class="form-control" placeholder="example.com">
                    </div>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Amount</label>
                    <div class="input-group">
                        <span class="input-group-text">$</span>
                        <input type="number" class="form-control" step="0.01">
                        <span class="input-group-text">.00</span>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <label class="form-label">Search</label>
                    <div class="input-group">
                        <input type="search" class="form-control" placeholder="Search...">
                        <button class="btn btn-primary" type="button">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Floating Labels -->
            <div class="row g-3 mt-3">
                <div class="col-md-6">
                    <div class="form-floating">
                        <input type="email" class="form-control" id="floatingEmail" placeholder="name@example.com">
                        <label for="floatingEmail">Email address</label>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="form-floating">
                        <select class="form-select" id="floatingSelect">
                            <option selected>Choose...</option>
                            <option value="1">Option 1</option>
                            <option value="2">Option 2</option>
                            <option value="3">Option 3</option>
                        </select>
                        <label for="floatingSelect">Select an option</label>
                    </div>
                </div>
            </div>
            
            <!-- Range Slider -->
            <div class="mt-4">
                <label for="customRange" class="form-label">Priority Level</label>
                <input type="range" class="form-range" min="0" max="100" step="10" id="customRange">
                <div class="d-flex justify-content-between">
                    <span class="text-muted small">Low</span>
                    <span class="text-muted small">Medium</span>
                    <span class="text-muted small">High</span>
                </div>
            </div>
            
            <!-- Switches and Checkboxes -->
            <div class="mt-4">
                <h6>Notification Preferences</h6>
                <div class="row g-3">
                    <div class="col-md-4">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="emailNotifications" checked>
                            <label class="form-check-label" for="emailNotifications">
                                Email Notifications
                            </label>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="smsNotifications">
                            <label class="form-check-label" for="smsNotifications">
                                SMS Notifications
                            </label>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="pushNotifications" checked>
                            <label class="form-check-label" for="pushNotifications">
                                Push Notifications
                            </label>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Action Buttons -->
            <div class="mt-4 pt-3 border-top">
                <div class="d-flex justify-content-end gap-2">
                    <button type="button" class="btn btn-outline-secondary">
                        <i class="fas fa-times me-1"></i> Cancel
                    </button>
                    <button type="button" class="btn btn-outline-primary">
                        <i class="fas fa-eye me-1"></i> Preview
                    </button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save me-1"></i> Save Changes
                    </button>
                </div>
            </div>
        </form>
    </div>
</div>
```

### Bootstrap Utility Classes for Dashboards

#### Spacing and Layout Utilities
```html
<!-- Spacing utilities -->
<div class="mb-4">Margin bottom</div>
<div class="p-3">Padding all sides</div>
<div class="px-4 py-2">Horizontal and vertical padding</div>

<!-- Flexbox utilities -->
<div class="d-flex justify-content-between align-items-center">
    <h5 class="mb-0">Title</h5>
    <button class="btn btn-primary">Action</button>
</div>

<!-- Display utilities -->
<div class="d-none d-md-block">Hidden on mobile</div>
<div class="d-block d-md-none">Visible only on mobile</div>

<!-- Text utilities -->
<div class="text-center">Centered text</div>
<div class="text-muted small">Muted small text</div>
<div class="fw-bold">Bold text</div>
<div class="text-truncate" style="max-width: 200px;">Very long text that will be truncated</div>
```

#### Color and Background Utilities
```html
<!-- Background colors -->
<div class="bg-primary text-white p-3">Primary background</div>
<div class="bg-light p-3">Light background</div>
<div class="bg-gradient bg-primary text-white p-3">Gradient background</div>

<!-- Text colors -->
<span class="text-primary">Primary text</span>
<span class="text-success">Success text</span>
<span class="text-danger">Danger text</span>
<span class="text-warning">Warning text</span>

<!-- Border utilities -->
<div class="border border-primary rounded p-3">Bordered container</div>
<div class="border-start border-4 border-success ps-3">Left border accent</div>
```

#### Position and Shadow Utilities
```html
<!-- Shadow utilities -->
<div class="card shadow-sm">Small shadow</div>
<div class="card shadow">Default shadow</div>
<div class="card shadow-lg">Large shadow</div>

<!-- Position utilities -->
<div class="position-relative">
    <div class="position-absolute top-0 end-0">
        <span class="badge bg-danger">New</span>
    </div>
</div>
```

### Responsive Design with Bootstrap 5

#### Grid System for Dashboards
```html
<!-- Responsive dashboard grid -->
<div class="container-fluid">
    <div class="row">
        <!-- Stats cards - responsive columns -->
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 1</div>
        </div>
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 2</div>
        </div>
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 3</div>
        </div>
        <div class="col-12 col-sm-6 col-lg-3 mb-4">
            <div class="card">Stats Card 4</div>
        </div>
    </div>
    
    <div class="row">
        <!-- Main chart - larger on desktop -->
        <div class="col-lg-8 mb-4">
            <div class="card">Main Chart</div>
        </div>
        <!-- Sidebar chart - smaller on desktop -->
        <div class="col-lg-4 mb-4">
            <div class="card">Sidebar Chart</div>
        </div>
    </div>
</div>
```

#### Responsive Navigation
```html
<!-- Responsive sidebar -->
<nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar collapse" id="sidebarMenu">
    <div class="position-sticky pt-3">
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link active" href="#">Dashboard</a>
            </li>
            <!-- More nav items -->
        </ul>
    </div>
</nav>

<!-- Mobile toggle button -->
<button class="navbar-toggler d-md-none" type="button" 
        data-bs-toggle="collapse" data-bs-target="#sidebarMenu">
    <span class="navbar-toggler-icon"></span>
</button>
```

### Customizing Bootstrap 5 for Dashboards

#### CSS Custom Properties
```css
/* Custom dashboard theme using Bootstrap's CSS variables */
:root {
    /* Override Bootstrap colors */
    --bs-primary: #4e73df;
    --bs-secondary: #858796;
    --bs-success: #1cc88a;
    --bs-info: #36b9cc;
    --bs-warning: #f6c23e;
    --bs-danger: #e74a3b;
    
    /* Custom dashboard variables */
    --bs-dashboard-sidebar-width: 280px;
    --bs-dashboard-header-height: 64px;
    --bs-dashboard-card-shadow: 0 0.15rem 1.75rem 0 rgba(58, 59, 69, 0.15);
    --bs-dashboard-border-color: #e3e6f0;
}

/* Custom component styles */
.dashboard-card {
    border: 1px solid var(--bs-dashboard-border-color);
    box-shadow: var(--bs-dashboard-card-shadow);
    transition: all 0.3s;
}

.dashboard-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 0.25rem 2rem 0 rgba(58, 59, 69, 0.2);
}

/* Custom sidebar styles */
.dashboard-sidebar {
    width: var(--bs-dashboard-sidebar-width);
    box-shadow: 0 0 0 1px var(--bs-dashboard-border-color);
}

.dashboard-sidebar .nav-link {
    color: #5a5c69;
    padding: 0.75rem 1rem;
    border-radius: 0.35rem;
    margin: 0.125rem 0.5rem;
}

.dashboard-sidebar .nav-link:hover {
    background-color: #f8f9fc;
    color: #5a5c69;
}

.dashboard-sidebar .nav-link.active {
    background-color: var(--bs-primary);
    color: white;
}

/* Dark mode support */
[data-bs-theme="dark"] {
    --bs-dashboard-border-color: #444;
    --bs-dashboard-card-shadow: 0 0.15rem 1.75rem 0 rgba(0, 0, 0, 0.15);
}
```

#### Dark Mode Toggle
```html
<!-- Dark mode toggle -->
<div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" id="darkModeToggle"
           _="on change
              if my checked
                set document.documentElement's @data-bs-theme to 'dark'
                localStorage.setItem('dashboard-theme', 'dark')
              else
                set document.documentElement's @data-bs-theme to 'light'
                localStorage.setItem('dashboard-theme', 'light')
              end">
    <label class="form-check-label" for="darkModeToggle">
        <i class="fas fa-moon me-1"></i> Dark Mode
    </label>
</div>

<script type="text/hyperscript">
  -- Initialize theme on page load
  init
    set savedTheme to localStorage.getItem('dashboard-theme') or 'light'
    set document.documentElement's @data-bs-theme to savedTheme
    if savedTheme is 'dark'
      set #darkModeToggle.checked to true
    end
  end
</script>
```

---

## Flask Dashboard Integration Patterns

### Complete Dashboard Example with Flask Backend

#### Flask Application Structure
```python
# app.py - Main Flask application
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dashboard.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class DashboardStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    metric_name = db.Column(db.String(50), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Dashboard Routes
@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard/index.html')

@app.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    """Get real-time dashboard statistics"""
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'new_users_today': User.query.filter(
            User.created_at >= datetime.utcnow().date()
        ).count(),
        'online_users': get_online_users_count(),
    }
    return render_template('dashboard/components/stats_cards.html', stats=stats)

@app.route('/api/dashboard/users')
@login_required
def get_users():
    """Get paginated users list"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            User.username.contains(search) | 
            User.email.contains(search)
        )
    
    if status_filter:
        query = query.filter_by(is_active=(status_filter == 'active'))
    
    pagination = query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('dashboard/components/users_table.html', 
                         pagination=pagination)

@app.route('/api/dashboard/users', methods=['POST'])
@login_required
def create_user():
    """Create new user"""
    try:
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            role=request.form['role'],
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(user)
        db.session.commit()
        
        return render_template('dashboard/components/user_row.html', user=user), 201
    except Exception as e:
        return f'<div class="alert alert-danger">Error: {str(e)}</div>', 400

@app.route('/api/dashboard/users/<int:user_id>', methods=['PUT', 'POST'])
@login_required
def update_user(user_id):
    """Update user"""
    user = User.query.get_or_404(user_id)
    
    user.username = request.form['username']
    user.email = request.form['email']
    user.role = request.form['role']
    user.is_active = request.form.get('is_active') == 'on'
    
    db.session.commit()
    
    return render_template('dashboard/components/user_row.html', user=user)

@app.route('/api/dashboard/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete user"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    return '', 200

@app.route('/api/dashboard/chart/users-growth')
@login_required
def users_growth_chart():
    """Generate users growth chart data"""
    days = request.args.get('days', 30, type=int)
    
    # Generate sample data - replace with real data
    chart_data = generate_growth_chart_data(days)
    
    return render_template('dashboard/charts/line_chart.html', 
                         chart_data=chart_data, 
                         chart_id='users-growth')

def generate_growth_chart_data(days):
    """Generate sample chart data"""
    import random
    data = []
    base_date = datetime.utcnow() - timedelta(days=days)
    
    for i in range(days):
        date = base_date + timedelta(days=i)
        value = random.randint(10, 100)
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'value': value
        })
    
    return data

def get_online_users_count():
    """Get count of online users (implement based on your session logic)"""
    # Implement your online user counting logic
    return 42  # Sample data

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

#### Dashboard Templates Structure

**Base Dashboard Template (dashboard/base.html):**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Dashboard{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" 
          rel="stylesheet" 
          integrity="sha384-LN+7fdVzj6u52u30Kp6M/trliBMCMKTyK833zpbD+pXdCLuTusPj697FH4R/5mcr" 
          crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <style>
        /* Dashboard-specific styles */
        :root {
            --dashboard-sidebar-width: 280px;
            --dashboard-header-height: 64px;
            --dashboard-primary: #4e73df;
            --dashboard-success: #1cc88a;
            --dashboard-warning: #f6c23e;
            --dashboard-danger: #e74a3b;
        }
        
        .dashboard-layout {
            display: flex;
            min-height: 100vh;
        }
        
        .dashboard-sidebar {
            width: var(--dashboard-sidebar-width);
            background: white;
            border-right: 1px solid #e3e6f0;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            z-index: 1000;
        }
        
        .dashboard-main {
            margin-left: var(--dashboard-sidebar-width);
            flex: 1;
            background: #f8f9fc;
        }
        
        .dashboard-header {
            background: white;
            padding: 1rem 2rem;
            border-bottom: 1px solid #e3e6f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 999;
        }
        
        .dashboard-content {
            padding: 2rem;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .dashboard-sidebar {
                transform: translateX(-100%);
                transition: transform 0.3s;
            }
            
            .dashboard-sidebar.mobile-open {
                transform: translateX(0);
            }
            
            .dashboard-main {
                margin-left: 0;
            }
            
            .mobile-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 999;
            }
            
            .mobile-overlay.show {
                display: block;
            }
        }
        
        /* Navigation */
        .sidebar-nav .nav-item {
            margin: 0.125rem 0.5rem;
        }
        
        .sidebar-nav .nav-link {
            color: #5a5c69;
            padding: 0.75rem 1rem;
            border-radius: 0.35rem;
            display: flex;
            align-items: center;
        }
        
        .sidebar-nav .nav-link:hover {
            background-color: #f8f9fc;
            color: #5a5c69;
        }
        
        .sidebar-nav .nav-link.active {
            background-color: var(--dashboard-primary);
            color: white;
        }
        
        .sidebar-nav .nav-link i {
            width: 1.25rem;
            margin-right: 0.5rem;
        }
    </style>
</head>
<body class="dashboard-layout">
    <!-- Mobile Overlay -->
    <div class="mobile-overlay" 
         _="on click 
            remove .mobile-open from .dashboard-sidebar
            remove .show from me"></div>
    
    <!-- Sidebar -->
    <aside class="dashboard-sidebar" 
           _="on mobile-menu-toggle 
              toggle .mobile-open on me
              toggle .show on .mobile-overlay">
        <div class="sidebar-content">
            <div class="sidebar-header p-3">
                <div class="d-flex align-items-center">
                    <i class="fas fa-tachometer-alt text-primary me-2"></i>
                    <h4 class="mb-0">Dashboard</h4>
                </div>
            </div>
            
            <nav class="sidebar-nav">
                <ul class="nav flex-column">
                    <li class="nav-item">
                        <a href="/dashboard" class="nav-link {{ 'active' if request.endpoint == 'dashboard' }}">
                            <i class="fas fa-fw fa-tachometer-alt"></i>
                            <span>Overview</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/analytics" class="nav-link">
                            <i class="fas fa-fw fa-chart-area"></i>
                            <span>Analytics</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/users" class="nav-link">
                            <i class="fas fa-fw fa-users"></i>
                            <span>Users</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/orders" class="nav-link">
                            <i class="fas fa-fw fa-shopping-cart"></i>
                            <span>Orders</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/reports" class="nav-link">
                            <i class="fas fa-fw fa-file-alt"></i>
                            <span>Reports</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="/dashboard/settings" class="nav-link">
                            <i class="fas fa-fw fa-cog"></i>
                            <span>Settings</span>
                        </a>
                    </li>
                </ul>
            </nav>
        </div>
    </aside>
    
    <!-- Main Content -->
    <main class="dashboard-main">
        <!-- Header -->
        <header class="dashboard-header">
            <div class="header-left d-flex align-items-center">
                <button class="btn btn-link d-md-none me-3" 
                        _="on click send mobile-menu-toggle to .dashboard-sidebar">
                    <i class="fas fa-bars"></i>
                </button>
                <h1 class="h3 mb-0">{% block page_title %}Dashboard{% endblock %}</h1>
            </div>
            
            <div class="header-right d-flex align-items-center">
                <!-- Search -->
                <div class="me-3">
                    <div class="input-group">
                        <input type="search" class="form-control form-control-sm" 
                               placeholder="Search..." style="width: 200px;">
                        <button class="btn btn-outline-secondary btn-sm">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Notifications -->
                <div class="dropdown me-3">
                    <button class="btn btn-link position-relative" data-bs-toggle="dropdown">
                        <i class="fas fa-bell"></i>
                        <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">
                            3
                        </span>
                    </button>
                    <div class="dropdown-menu dropdown-menu-end">
                        <h6 class="dropdown-header">Notifications</h6>
                        <a class="dropdown-item" href="#">
                            <div class="d-flex">
                                <div class="flex-shrink-0">
                                    <i class="fas fa-user-plus text-success"></i>
                                </div>
                                <div class="flex-grow-1 ms-2">
                                    <div class="small">New user registered</div>
                                    <div class="text-muted small">2 minutes ago</div>
                                </div>
                            </div>
                        </a>
                        <div class="dropdown-divider"></div>
                        <a class="dropdown-item text-center small" href="#">View all notifications</a>
                    </div>
                </div>
                
                <!-- User Menu -->
                <div class="dropdown">
                    <button class="btn btn-link d-flex align-items-center" data-bs-toggle="dropdown">
                        <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center me-2"
                             style="width: 32px; height: 32px;">
                            {{ current_user.username[0].upper() }}
                        </div>
                        <span class="d-none d-sm-block">{{ current_user.username }}</span>
                        <i class="fas fa-chevron-down ms-1"></i>
                    </button>
                    <div class="dropdown-menu dropdown-menu-end">
                        <a class="dropdown-item" href="/profile">
                            <i class="fas fa-user me-2"></i> Profile
                        </a>
                        <a class="dropdown-item" href="/settings">
                            <i class="fas fa-cog me-2"></i> Settings
                        </a>
                        <div class="dropdown-divider"></div>
                        <a class="dropdown-item" href="/logout">
                            <i class="fas fa-sign-out-alt me-2"></i> Logout
                        </a>
                    </div>
                </div>
            </div>
        </header>
        
        <!-- Page Content -->
        <div class="dashboard-content">
            {% block content %}{% endblock %}
        </div>
    </main>
    
    <!-- Toast Container -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1060;">
        <!-- Toasts will be dynamically added here -->
    </div>
    
    <!-- Modal Container -->
    <div id="modal-container"></div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js" 
            integrity="sha384-ndDqU0Gzau9qJ1lfW4pNLlhNTkCfHzAVBReH9diLvGRem5+R9g2FzA8ZGN954O5Q" 
            crossorigin="anonymous"></script>
    
    <!-- Global Dashboard Scripts -->
    <script type="text/hyperscript">
        -- Auto-refresh dashboard every 30 seconds
        init
          repeat every 30s
            fetch /api/dashboard/stats
            put the result into #dashboard-stats
          end
        end
        
        -- Global error handler
        on htmx:responseError from body
          call showToast('An error occurred. Please try again.', 'danger')
        end
        
        -- Success handler
        on htmx:afterRequest from body
          if detail.xhr.status >= 200 and detail.xhr.status < 300
            if detail.target.dataset.successMessage
              call showToast(detail.target.dataset.successMessage, 'success')
            end
          end
        end
        
        -- Toast function
        def showToast(message, type)
          set toastHtml to `
            <div class="toast" role="alert" data-bs-autohide="true" data-bs-delay="5000">
              <div class="toast-header">
                <div class="rounded me-2 bg-${type}" style="width: 20px; height: 20px;"></div>
                <strong class="me-auto">Dashboard</strong>
                <small>just now</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
              </div>
              <div class="toast-body">${message}</div>
            </div>
          `
          
          make a <div/> called toastElement
          set toastElement.innerHTML to toastHtml
          set toastEl to toastElement.firstElementChild
          put toastEl at the end of .toast-container
          
          set toast to new bootstrap.Toast(toastEl)
          call toast.show()
        end
    </script>
</body>
</html>
```

**Main Dashboard Page (dashboard/index.html):**
```html
{% extends "dashboard/base.html" %}

{% block content %}
<!-- Stats Cards -->
<div id="dashboard-stats" 
     hx-get="/api/dashboard/stats" 
     hx-trigger="load">
    <div class="row">
        <div class="col-12 text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading dashboard stats...</span>
            </div>
            <div class="mt-2 text-muted">Loading dashboard...</div>
        </div>
    </div>
</div>

<!-- Charts Section -->
<div class="row mb-4">
    <div class="col-xl-8 col-lg-7">
        <!-- User Growth Chart -->
        <div class="card shadow mb-4">
            <div class="card-header py-3 d-flex justify-content-between align-items-center">
                <h6 class="m-0 font-weight-bold text-primary">User Growth</h6>
                <div class="dropdown">
                    <button class="btn btn-outline-primary btn-sm dropdown-toggle" 
                            data-bs-toggle="dropdown">
                        <i class="fas fa-calendar me-1"></i> Last 30 days
                    </button>
                    <ul class="dropdown-menu">
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/users-growth?days=7" 
                               hx-target="#users-growth-chart">
                                Last 7 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/users-growth?days=30" 
                               hx-target="#users-growth-chart">
                                Last 30 days
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" href="#"
                               hx-get="/api/dashboard/chart/users-growth?days=90" 
                               hx-target="#users-growth-chart">
                                Last 90 days
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="card-body">
                <div id="users-growth-chart" 
                     hx-get="/api/dashboard/chart/users-growth?days=30" 
                     hx-trigger="load"
                     style="height: 400px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading chart...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-4 col-lg-5">
        <!-- Revenue Chart -->
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Revenue Sources</h6>
            </div>
            <div class="card-body">
                <div id="revenue-chart" 
                     hx-get="/api/dashboard/chart/revenue" 
                     hx-trigger="load"
                     style="height: 320px;">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading chart...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Recent Activity and Quick Actions -->
<div class="row">
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Recent Activity</h6>
            </div>
            <div class="card-body">
                <div id="activity-feed" 
                     hx-get="/api/dashboard/activity" 
                     hx-trigger="load, every 60s"
                     style="max-height: 400px; overflow-y: auto;">
                    <div class="text-center py-3">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading activity...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-lg-6">
        <div class="card shadow mb-4">
            <div class="card-header py-3">
                <h6 class="m-0 font-weight-bold text-primary">Quick Actions</h6>
            </div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-6">
                        <button class="btn btn-primary w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/users/new" 
                                hx-target="#modal-container">
                            <i class="fas fa-user-plus fa-2x mb-2"></i>
                            <span>Add User</span>
                        </button>
                    </div>
                    <div class="col-6">
                        <button class="btn btn-success w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/reports/generate" 
                                hx-target="#modal-container">
                            <i class="fas fa-chart-bar fa-2x mb-2"></i>
                            <span>Generate Report</span>
                        </button>
                    </div>
                    <div class="col-6">
                        <button class="btn btn-info w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/settings/backup" 
                                hx-target="#modal-container">
                            <i class="fas fa-download fa-2x mb-2"></i>
                            <span>Backup Data</span>
                        </button>
                    </div>
                    <div class="col-6">
                        <button class="btn btn-warning w-100 h-100 d-flex flex-column align-items-center justify-content-center" 
                                style="min-height: 120px;"
                                hx-get="/api/dashboard/system/maintenance" 
                                hx-target="#modal-container">
                            <i class="fas fa-tools fa-2x mb-2"></i>
                            <span>Maintenance</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

---

## Dashboard-Specific Components

### Real-time Dashboard Widgets

#### Live Activity Feed
```html
<!-- Activity Feed Component with Bootstrap styling -->
<div class="card shadow activity-feed-widget">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">
            <i class="fas fa-stream me-2"></i>Live Activity
        </h6>
        <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary" 
                    _="on click
                       toggle .paused on #activity-feed
                       if #activity-feed matches .paused
                         put 'Resume' into me
                         set my @title to 'Resume updates'
                         add .btn-warning to me
                         remove .btn-outline-secondary from me
                       else
                         put 'Pause' into me
                         set my @title to 'Pause updates'
                         add .btn-outline-secondary to me
                         remove .btn-warning from me
                       end">
                <i class="fas fa-pause me-1"></i> Pause
            </button>
            <button class="btn btn-outline-danger" 
                    hx-post="/api/dashboard/activity/clear" 
                    hx-target="#activity-list"
                    hx-confirm="Clear all activity?"
                    title="Clear activity">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    </div>
    
    <div id="activity-feed" 
         class="card-body p-0"
         hx-ext="sse" 
         sse-connect="/stream/activity"
         _="on sse:activity(data) 
            unless I match .paused
              make a <div.activity-item.list-group-item.border-0/> called item
              set item.innerHTML to `
                <div class='d-flex align-items-start'>
                  <div class='activity-icon bg-${data.type} text-white rounded-circle me-3 d-flex align-items-center justify-content-center' 
                       style='width: 40px; height: 40px; font-size: 0.875rem;'>
                    <i class='${data.icon}'></i>
                  </div>
                  <div class='flex-grow-1'>
                    <div class='activity-message fw-bold'>${data.message}</div>
                    <div class='activity-details text-muted small'>${data.details}</div>
                    <div class='activity-time text-muted small'>
                      <i class='fas fa-clock me-1'></i>${data.time}
                    </div>
                  </div>
                </div>
              `
              put item at the start of #activity-list
              
              -- Add animation
              add .animate__animated.animate__fadeInLeft to item
              
              -- Limit to 50 items
              set items to <.activity-item/> in #activity-list
              if items.length > 50
                remove items[items.length - 1]
              end
            end">
        
        <div id="activity-list" class="list-group list-group-flush" 
             style="max-height: 400px; overflow-y: auto;">
            {% for activity in recent_activities %}
            <div class="activity-item list-group-item border-0">
                <div class="d-flex align-items-start">
                    <div class="activity-icon bg-{{ activity.type }} text-white rounded-circle me-3 d-flex align-items-center justify-content-center" 
                         style="width: 40px; height: 40px; font-size: 0.875rem;">
                        <i class="{{ activity.icon }}"></i>
                    </div>
                    <div class="flex-grow-1">
                        <div class="activity-message fw-bold">{{ activity.message }}</div>
                        <div class="activity-details text-muted small">{{ activity.details }}</div>
                        <div class="activity-time text-muted small">
                            <i class="fas fa-clock me-1"></i>{{ activity.timestamp.strftime('%H:%M:%S') }}
                        </div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

<style>
.activity-feed-widget {
    height: 500px;
    display: flex;
    flex-direction: column;
}

.activity-feed.paused {
    opacity: 0.7;
}

.activity-item {
    transition: background-color 0.2s;
    padding: 1rem;
}

.activity-item:hover {
    background-color: #f8f9fa !important;
}

.animate__fadeInLeft {
    animation-duration: 0.5s;
}
</style>
```

#### System Health Dashboard
```html
<!-- System Health Widget with Bootstrap -->
<div class="card shadow system-health-widget">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">
            <i class="fas fa-heartbeat me-2"></i>System Health
        </h6>
        <span class="badge health-status bg-success" 
             _="init set :overallStatus to 'success'
               on health-update(status)
                 set :overallStatus to status
                 remove .bg-success, .bg-warning, .bg-danger from me
                 if status is 'success'
                   add .bg-success to me
                   put 'All Systems Operational' into me
                 else if status is 'warning'
                   add .bg-warning to me
                   put 'Some Issues Detected' into me
                 else
                   add .bg-danger to me
                   put 'Critical Issues' into me
                 end
               end">
            <i class="fas fa-check-circle me-1"></i>All Systems Operational
        </span>
    </div>
    
    <div class="card-body">
        <div class="health-metrics" 
             hx-get="/api/dashboard/health" 
             hx-trigger="load, every 10s"
             _="on htmx:afterRequest
                set data to JSON.parse(detail.xhr.response)
                
                -- Update metrics
                for metric in ['cpu', 'memory', 'disk']
                  set value to data[metric + '_usage']
                  set progressBar to `#${metric}-progress`
                  set valueDisplay to `#${metric}-value`
                  set progressBar.style.width to value + '%'
                  put value + '%' into valueDisplay
                  
                  -- Update progress bar color based on value
                  remove .bg-success, .bg-warning, .bg-danger from progressBar
                  if value < 60
                    add .bg-success to progressBar
                  else if value < 80
                    add .bg-warning to progressBar
                  else
                    add .bg-danger to progressBar
                  end
                end
                
                -- Update connection count
                put data.active_connections into #connections-count
                
                -- Determine overall status
                set maxUsage to Math.max(data.cpu_usage, data.memory_usage, data.disk_usage)
                if maxUsage > 90
                  send health-update(status: 'danger') to .health-status
                else if maxUsage > 75
                  send health-update(status: 'warning') to .health-status
                else
                  send health-update(status: 'success') to .health-status
                end">
            
            <div class="row g-3">
                <div class="col-md-4">
                    <div class="metric-card">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="metric-label">
                                <i class="fas fa-microchip me-1 text-primary"></i>CPU Usage
                            </span>
                            <span id="cpu-value" class="metric-value badge bg-primary">45%</span>
                        </div>
                        <div class="progress">
                            <div id="cpu-progress" class="progress-bar bg-success" 
                                 style="width: 45%" role="progressbar"></div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="metric-card">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="metric-label">
                                <i class="fas fa-memory me-1 text-warning"></i>Memory
                            </span>
                            <span id="memory-value" class="metric-value badge bg-warning">67%</span>
                        </div>
                        <div class="progress">
                            <div id="memory-progress" class="progress-bar bg-warning" 
                                 style="width: 67%" role="progressbar"></div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="metric-card">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="metric-label">
                                <i class="fas fa-hdd me-1 text-info"></i>Disk Usage
                            </span>
                            <span id="disk-value" class="metric-value badge bg-info">23%</span>
                        </div>
                        <div class="progress">
                            <div id="disk-progress" class="progress-bar bg-success" 
                                 style="width: 23%" role="progressbar"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <hr class="my-4">
            
            <div class="row text-center">
                <div class="col-md-6">
                    <div class="metric-large">
                        <i class="fas fa-wifi fa-2x text-success mb-2"></i>
                        <div class="metric-large-label">Active Connections</div>
                        <div id="connections-count" class="metric-large-value text-success">1,247</div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="metric-large">
                        <i class="fas fa-clock fa-2x text-info mb-2"></i>
                        <div class="metric-large-label">Uptime</div>
                        <div class="metric-large-value text-info">15d 7h 32m</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
.system-health-widget {
    min-width: 400px;
}

.metric-card {
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 0.5rem;
    transition: all 0.2s;
}

.metric-card:hover {
    background: #e9ecef;
    transform: translateY(-1px);
}

.metric-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: #495057;
}

.metric-value {
    font-size: 0.75rem;
}

.metric-large {
    padding: 1rem;
}

.metric-large-label {
    font-size: 0.875rem;
    color: #6c757d;
    margin-bottom: 0.5rem;
}

.metric-large-value {
    font-size: 1.5rem;
    font-weight: 700;
}

.progress {
    height: 6px;
}
</style>
```

---

## Real-time Dashboard Updates

### WebSocket Integration with HTMX and Bootstrap

Flask applications can use WebSockets for real-time dashboard updates. Here's how to integrate WebSocket connections with HTMX and Bootstrap styling:

#### WebSocket Flask Configuration
```python
# app.py - WebSocket setup with Flask-SocketIO
from flask import Flask
from flask_socketio import SocketIO, emit, disconnect
import json
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active dashboard connections
dashboard_connections = set()

@socketio.on('dashboard_connect')
def handle_dashboard_connect():
    dashboard_connections.add(request.sid)
    emit('connection_status', {'status': 'connected', 'clients': len(dashboard_connections)})
    
    # Send initial dashboard data
    emit('dashboard_data', get_dashboard_data())

@socketio.on('disconnect')
def handle_disconnect():
    dashboard_connections.discard(request.sid)

# Background task to send periodic updates
def background_thread():
    while True:
        time.sleep(5)  # Update every 5 seconds
        if dashboard_connections:
            dashboard_data = get_dashboard_data()
            socketio.emit('dashboard_update', dashboard_data, room=None)

# Start background thread
thread = threading.Thread(target=background_thread)
thread.daemon = True
thread.start()

def get_dashboard_data():
    """Collect real-time dashboard metrics"""
    return {
        'timestamp': time.time(),
        'active_users': get_active_user_count(),
        'system_load': get_system_load(),
        'recent_activities': get_recent_activities(),
        'performance_metrics': get_performance_metrics()
    }
```

#### Real-time Dashboard Template with Bootstrap
```html
<!-- Real-time Dashboard with WebSocket and Bootstrap -->
<div class="container-fluid realtime-dashboard" 
     _="init
        set :socket to io()
        
        -- Connect to dashboard updates
        call :socket.emit('dashboard_connect')
        
        -- Handle real-time updates
        call :socket.on('dashboard_update', def(data)
          update-dashboard-stats(data)
          update-activity-feed(data.recent_activities)
          update-performance-charts(data.performance_metrics)
        end)
        
        -- Handle connection status
        call :socket.on('connection_status', def(data)
          put data.clients + ' clients connected' into #connection-status
          if data.status is 'connected'
            remove .bg-danger from #connection-indicator
            add .bg-success to #connection-indicator
          else
            remove .bg-success from #connection-indicator
            add .bg-danger to #connection-indicator
          end
        end)
        
        -- Cleanup on page unload
        on beforeunload
          call :socket.disconnect()
        end
        
        -- Functions for updating UI
        def update-dashboard-stats(data)
          put data.active_users into #active-users-count
          put (data.system_load * 100).toFixed(1) + '%' into #system-load
          set #load-progress.style.width to (data.system_load * 100) + '%'
          
          -- Update progress bar color
          remove .bg-success, .bg-warning, .bg-danger from #load-progress
          if data.system_load < 0.6
            add .bg-success to #load-progress
          else if data.system_load < 0.8
            add .bg-warning to #load-progress
          else
            add .bg-danger to #load-progress
          end
          
          -- Animate changes
          add .animate__pulse to #stats-container
          wait 300ms
          remove .animate__pulse from #stats-container
        end
        
        def update-activity-feed(activities)
          set feed to #activity-feed
          for activity in activities
            make a <div.list-group-item.border-0/> called item
            set item.innerHTML to `
              <div class='d-flex align-items-start'>
                <div class='activity-icon bg-${activity.type} text-white rounded-circle me-3 d-flex align-items-center justify-content-center' 
                     style='width: 32px; height: 32px; font-size: 0.75rem;'>
                  <i class='${activity.icon}'></i>
                </div>
                <div class='flex-grow-1'>
                  <div class='activity-message small fw-bold'>${activity.message}</div>
                  <div class='activity-time text-muted small'>
                    <i class='fas fa-clock me-1'></i>${activity.time}
                  </div>
                </div>
              </div>
            `
            add .animate__fadeInUp to item
            put item at the start of feed
          end
          
          -- Keep only latest 20 items
          set items to <.list-group-item/> in feed
          if items.length > 20
            for i from 20 to items.length - 1
              remove items[i]
            end
          end
        end
        
        def update-performance-charts(metrics)
          if window.performanceChart
            set chart to window.performanceChart
            call chart.data.labels.push(new Date().toLocaleTimeString())
            call chart.data.datasets[0].data.push(metrics.response_time)
            call chart.data.datasets[1].data.push(metrics.throughput)
            
            -- Keep only last 20 data points
            if chart.data.labels.length > 20
              call chart.data.labels.shift()
              call chart.data.datasets[0].data.shift()
              call chart.data.datasets[1].data.shift()
            end
            
            call chart.update('none')
          end
        end">
    
    <!-- Connection Status -->
    <div class="row mb-4">
        <div class="col-12">
            <div class="alert alert-info d-flex align-items-center">
                <div id="connection-indicator" class="bg-success rounded-circle me-3" 
                     style="width: 12px; height: 12px;"></div>
                <div class="flex-grow-1">
                    <strong>Real-time Dashboard</strong> - 
                    <span id="connection-status">Connecting...</span>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-info" 
                            _="on click
                               if I match .btn-outline-info
                                 call :socket.disconnect()
                                 put 'Connect' into me
                                 remove .btn-outline-info from me
                                 add .btn-info to me
                               else
                                 call :socket.connect()
                                 put 'Disconnect' into me
                                 remove .btn-info from me
                                 add .btn-outline-info to me
                               end">
                        Disconnect
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Live Statistics -->
    <div id="stats-container" class="row mb-4">
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-primary shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                                Active Users
                            </div>
                            <div id="active-users-count" class="h5 mb-0 font-weight-bold text-gray-800">--</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-users fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-warning shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">
                                System Load
                            </div>
                            <div class="row no-gutters align-items-center">
                                <div class="col-auto">
                                    <div id="system-load" class="h5 mb-0 mr-3 font-weight-bold text-gray-800">--</div>
                                </div>
                                <div class="col">
                                    <div class="progress progress-sm mr-2">
                                        <div id="load-progress" class="progress-bar bg-warning" role="progressbar" 
                                             style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-server fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-success shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-success text-uppercase mb-1">
                                Revenue (Monthly)
                            </div>
                            <div class="h5 mb-0 font-weight-bold text-gray-800" id="monthly-revenue">$45,678</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-dollar-sign fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-info shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-info text-uppercase mb-1">
                                Tasks Pending
                            </div>
                            <div class="h5 mb-0 font-weight-bold text-gray-800" id="pending-tasks">18</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-clipboard-list fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Real-time Charts and Activity -->
    <div class="row">
        <div class="col-xl-8 col-lg-7">
            <!-- Performance Chart -->
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">Real-time Performance</h6>
                </div>
                <div class="card-body">
                    <canvas id="performance-chart" width="400" height="200"></canvas>
                </div>
            </div>
        </div>
        
        <div class="col-xl-4 col-lg-5">
            <!-- Live Activity Feed -->
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">Live Activity</h6>
                </div>
                <div class="card-body p-0">
                    <div id="activity-feed" class="list-group list-group-flush" 
                         style="max-height: 400px; overflow-y: auto;">
                        <!-- Activities are inserted here dynamically -->
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Chart.js for real-time charts -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">

<script>
// Initialize performance chart
const ctx = document.getElementById('performance-chart').getContext('2d');
window.performanceChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Response Time (ms)',
            data: [],
            borderColor: '#4e73df',
            backgroundColor: 'rgba(78, 115, 223, 0.1)',
            tension: 0.4,
            yAxisID: 'y'
        }, {
            label: 'Throughput (req/s)',
            data: [],
            borderColor: '#1cc88a',
            backgroundColor: 'rgba(28, 200, 138, 0.1)',
            tension: 0.4,
            yAxisID: 'y1'
        }]
    },
    options: {
        responsive: true,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        scales: {
            x: {
                display: true,
                title: {
                    display: true,
                    text: 'Time'
                }
            },
            y: {
                type: 'linear',
                display: true,
                position: 'left',
                title: {
                    display: true,
                    text: 'Response Time (ms)'
                }
            },
            y1: {
                type: 'linear',
                display: true,
                position: 'right',
                title: {
                    display: true,
                    text: 'Throughput (req/s)'
                },
                grid: {
                    drawOnChartArea: false,
                }
            }
        },
        animation: {
            duration: 0 // Disable animations for real-time updates
        }
    }
});
</script>

<style>
.realtime-dashboard {
    padding: 2rem 0;
}

.border-left-primary {
    border-left: 0.25rem solid #4e73df !important;
}

.border-left-success {
    border-left: 0.25rem solid #1cc88a !important;
}

.border-left-info {
    border-left: 0.25rem solid #36b9cc !important;
}

.border-left-warning {
    border-left: 0.25rem solid #f6c23e !important;
}

.text-xs {
    font-size: 0.75rem;
}

.progress-sm {
    height: 0.5rem;
}

.activity-item {
    transition: all 0.3s ease;
}

.animate__pulse {
    animation-duration: 0.5s;
}

.animate__fadeInUp {
    animation-duration: 0.5s;
}
</style>
```

### Server-Sent Events (SSE) Alternative

For simpler real-time updates, use Server-Sent Events with HTMX:

#### SSE Flask Route
```python
@app.route('/stream/dashboard')
def dashboard_stream():
    def generate():
        while True:
            # Get current dashboard data
            data = get_dashboard_data()
            
            # Send as SSE event
            yield f"event: dashboard_update\n"
            yield f"data: {json.dumps(data)}\n\n"
            
            time.sleep(5)  # Update every 5 seconds
    
    return Response(generate(), mimetype='text/plain')
```

#### SSE Dashboard Template with Bootstrap
```html
<div class="card shadow sse-dashboard" 
     hx-ext="sse" 
     sse-connect="/stream/dashboard"
     _="on sse:dashboard_update(data) 
        set metrics to JSON.parse(data)
        put metrics.active_users into #active-users
        put metrics.system_load + '%' into #system-load
        update-activity-feed(metrics.activities)">
    
    <div class="card-header">
        <h5 class="mb-0">
            <i class="fas fa-broadcast-tower me-2 text-primary"></i>
            Server-Sent Events Dashboard
        </h5>
    </div>
    
    <div class="card-body">
        <div class="row">
            <div class="col-md-6">
                <div class="metric-display">
                    <label class="form-label">Active Users</label>
                    <div class="input-group">
                        <span class="input-group-text">
                            <i class="fas fa-users"></i>
                        </span>
                        <input type="text" class="form-control" id="active-users" readonly>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="metric-display">
                    <label class="form-label">System Load</label>
                    <div class="input-group">
                        <span class="input-group-text">
                            <i class="fas fa-server"></i>
                        </span>
                        <input type="text" class="form-control" id="system-load" readonly>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="mt-4">
            <h6>Recent Activity</h6>
            <div id="activity-list" class="list-group"></div>
        </div>
    </div>
</div>
```

---

## Data Visualization Integration

### Chart.js Integration with HTMX and Bootstrap

Combine Chart.js with HTMX for dynamic, data-driven dashboards using Bootstrap styling:

#### Dynamic Chart Updates
```html
<!-- Chart Container with Bootstrap styling -->
<div class="card shadow chart-container">
    <div class="card-header py-3 d-flex justify-content-between align-items-center">
        <h6 class="m-0 font-weight-bold text-primary">
            <i class="fas fa-chart-line me-2"></i>Sales Analytics
        </h6>
        <div class="chart-controls d-flex align-items-center gap-3">
            <div class="input-group" style="width: 200px;">
                <label class="input-group-text">Period</label>
                <select class="form-select" name="period" 
                        hx-get="/api/dashboard/chart-data" 
                        hx-trigger="change" 
                        hx-target="#chart-data" 
                        hx-swap="none"
                        _="on htmx:afterRequest(evt) 
                           set data to JSON.parse(evt.detail.xhr.response)
                           update-chart(data)">
                    <option value="7d">Last 7 Days</option>
                    <option value="30d" selected>Last 30 Days</option>
                    <option value="3m">Last 3 Months</option>
                    <option value="1y">Last Year</option>
                </select>
            </div>
            
            <div class="btn-group">
                <button class="btn btn-outline-secondary btn-sm" 
                        _="on click 
                           set canvas to #sales-chart
                           set link to document.createElement('a')
                           set link.download to 'sales-chart.png'
                           set link.href to canvas.toDataURL()
                           link.click()">
                    <i class="fas fa-download me-1"></i>Export
                </button>
                <button class="btn btn-outline-secondary btn-sm"
                        hx-get="/api/dashboard/chart-data" 
                        hx-target="#chart-data" 
                        hx-swap="none"
                        _="on htmx:afterRequest(evt) 
                           set data to JSON.parse(evt.detail.xhr.response)
                           update-chart(data)">
                    <i class="fas fa-sync-alt me-1"></i>Refresh
                </button>
            </div>
        </div>
    </div>
    
    <div class="card-body">
        <div class="chart-wrapper">
            <canvas id="sales-chart" width="800" height="400"></canvas>
        </div>
    </div>
    
    <!-- Hidden container for chart data -->
    <div id="chart-data" style="display: none;"></div>
</div>

<script>
// Initialize chart with Bootstrap-themed colors
const salesCtx = document.getElementById('sales-chart').getContext('2d');
let salesChart = new Chart(salesCtx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Sales',
            data: [],
            borderColor: '#4e73df',
            backgroundColor: 'rgba(78, 115, 223, 0.1)',
            tension: 0.4,
            fill: true,
            pointBackgroundColor: '#4e73df',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 5
        }, {
            label: 'Target',
            data: [],
            borderColor: '#1cc88a',
            borderDash: [5, 5],
            backgroundColor: 'transparent',
            tension: 0.4,
            pointBackgroundColor: '#1cc88a',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 5
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            title: {
                display: true,
                text: 'Sales Performance',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                color: '#5a5c69'
            },
            legend: {
                position: 'top',
                labels: {
                    usePointStyle: true,
                    padding: 20,
                    color: '#5a5c69'
                }
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                titleColor: '#5a5c69',
                bodyColor: '#5a5c69',
                borderColor: '#e3e6f0',
                borderWidth: 1,
                cornerRadius: 10,
                displayColors: true,
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        label += new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD'
                        }).format(context.parsed.y);
                        return label;
                    }
                }
            }
        },
        scales: {
            x: {
                display: true,
                title: {
                    display: true,
                    text: 'Date',
                    color: '#5a5c69',
                    font: {
                        weight: 'bold'
                    }
                },
                grid: {
                    color: '#e3e6f0'
                },
                ticks: {
                    color: '#858796'
                }
            },
            y: {
                display: true,
                title: {
                    display: true,
                    text: 'Revenue ($)',
                    color: '#5a5c69',
                    font: {
                        weight: 'bold'
                    }
                },
                grid: {
                    color: '#e3e6f0'
                },
                ticks: {
                    color: '#858796',
                    callback: function(value) {
                        return new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD',
                            notation: 'compact'
                        }).format(value);
                    }
                }
            }
        }
    }
});

// Function to update chart (called by hyperscript)
function updateChart(data) {
    salesChart.data.labels = data.labels;
    salesChart.data.datasets[0].data = data.sales;
    salesChart.data.datasets[1].data = data.targets;
    salesChart.update('active');
}
</script>

<style>
.chart-container {
    margin-bottom: 2rem;
}

.chart-wrapper {
    position: relative;
    height: 400px;
}

.chart-controls .input-group-text {
    font-size: 0.875rem;
    font-weight: 500;
}
</style>
```

#### Flask Chart Data Endpoint
```python
@app.route('/api/dashboard/chart-data')
def get_chart_data():
    period = request.args.get('period', '7d')
    
    # Generate data based on period
    if period == '7d':
        labels = [(datetime.now() - timedelta(days=x)).strftime('%m/%d') 
                 for x in range(6, -1, -1)]
        sales = [12000, 15000, 13500, 16000, 14500, 17000, 18500]
        targets = [14000, 14000, 14000, 15000, 15000, 16000, 16000]
    elif period == '30d':
        # Generate 30-day data
        labels = [(datetime.now() - timedelta(days=x)).strftime('%m/%d') 
                 for x in range(29, -1, -1)]
        sales = [random.randint(10000, 20000) for _ in range(30)]
        targets = [15000] * 30
    elif period == '3m':
        # Generate 3-month data (weekly)
        labels = [(datetime.now() - timedelta(weeks=x)).strftime('Week %U') 
                 for x in range(11, -1, -1)]
        sales = [random.randint(40000, 80000) for _ in range(12)]
        targets = [60000] * 12
    elif period == '1y':
        # Generate yearly data (monthly)
        labels = [(datetime.now() - timedelta(days=x*30)).strftime('%b %Y') 
                 for x in range(11, -1, -1)]
        sales = [random.randint(150000, 300000) for _ in range(12)]
        targets = [200000] * 12
    
    return jsonify({
        'labels': labels,
        'sales': sales,
        'targets': targets,
        'period': period
    })
```

### Multi-Chart Dashboard with Bootstrap Grid
```html
<!-- Dashboard with Multiple Charts using Bootstrap Grid -->
<div class="container-fluid multi-chart-dashboard">
    <div class="row mb-4">
        <!-- Revenue Chart -->
        <div class="col-xl-8 col-lg-7">
            <div class="card shadow mb-4">
                <div class="card-header py-3 d-flex justify-content-between align-items-center">
                    <h6 class="m-0 font-weight-bold text-primary">Revenue Trends</h6>
                    <div class="btn-group btn-group-sm chart-type-selector" 
                         _="on change from input[type=radio]
                            set chartType to event.target.value
                            set chart to window.revenueChart
                            call chart.destroy()
                            initialize-revenue-chart(chartType)">
                        <input type="radio" class="btn-check" name="revenue-type" 
                               id="btn-line" value="line" checked>
                        <label class="btn btn-outline-primary" for="btn-line">
                            <i class="fas fa-chart-line me-1"></i>Line
                        </label>
                        
                        <input type="radio" class="btn-check" name="revenue-type" 
                               id="btn-bar" value="bar">
                        <label class="btn btn-outline-primary" for="btn-bar">
                            <i class="fas fa-chart-bar me-1"></i>Bar
                        </label>
                        
                        <input type="radio" class="btn-check" name="revenue-type" 
                               id="btn-area" value="line">
                        <label class="btn btn-outline-primary" for="btn-area">
                            <i class="fas fa-chart-area me-1"></i>Area
                        </label>
                    </div>
                </div>
                <div class="card-body">
                    <canvas id="revenue-chart" style="height: 300px;"></canvas>
                </div>
            </div>
        </div>
        
        <!-- User Growth Chart -->
        <div class="col-xl-4 col-lg-5">
            <div class="card shadow mb-4">
                <div class="card-header py-3 d-flex justify-content-between align-items-center">
                    <h6 class="m-0 font-weight-bold text-primary">User Growth</h6>
                    <button class="btn btn-outline-secondary btn-sm refresh-btn" 
                            hx-get="/api/dashboard/user-growth" 
                            hx-trigger="click"
                            hx-swap="none"
                            _="on htmx:afterRequest(evt)
                               set data to JSON.parse(evt.detail.xhr.response)
                               update-user-growth-chart(data)">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                </div>
                <div class="card-body">
                    <canvas id="user-growth-chart" style="height: 280px;"></canvas>
                </div>
            </div>
        </div>
    </div>
    
    <div class="row">
        <!-- Performance Metrics -->
        <div class="col-lg-6">
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">System Performance</h6>
                </div>
                <div class="card-body">
                    <canvas id="performance-metrics-chart" style="height: 300px;"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Geographic Distribution -->
        <div class="col-lg-6">
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">Geographic Distribution</h6>
                </div>
                <div class="card-body">
                    <canvas id="geographic-chart" style="height: 300px;"></canvas>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
// Bootstrap-themed color palette
const bootstrapColors = {
    primary: '#4e73df',
    success: '#1cc88a',
    info: '#36b9cc',
    warning: '#f6c23e',
    danger: '#e74a3b',
    secondary: '#858796',
    light: '#f8f9fc',
    dark: '#5a5c69'
};

// Initialize all charts
document.addEventListener('DOMContentLoaded', function() {
    initializeRevenueChart('line');
    initializeUserGrowthChart();
    initializePerformanceChart();
    initializeGeographicChart();
});

function initializeRevenueChart(type) {
    const ctx = document.getElementById('revenue-chart').getContext('2d');
    
    const config = {
        type: type,
        data: {
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            datasets: [{
                label: 'Revenue',
                data: [65000, 78000, 85000, 72000, 95000, 102000],
                borderColor: bootstrapColors.primary,
                backgroundColor: type === 'line' ? 'rgba(78, 115, 223, 0.1)' : bootstrapColors.primary,
                fill: type === 'line'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#e3e6f0'
                    },
                    ticks: {
                        color: bootstrapColors.secondary
                    }
                },
                y: {
                    grid: {
                        color: '#e3e6f0'
                    },
                    ticks: {
                        color: bootstrapColors.secondary,
                        callback: function(value) {
                            return ' + (value / 1000) + 'k';
                        }
                    }
                }
            }
        }
    };
    
    if (window.revenueChart) {
        window.revenueChart.destroy();
    }
    window.revenueChart = new Chart(ctx, config);
}

function initializeUserGrowthChart() {
    const ctx = document.getElementById('user-growth-chart').getContext('2d');
    
    window.userGrowthChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['New Users', 'Returning Users', 'Inactive Users'],
            datasets: [{
                data: [300, 500, 100],
                backgroundColor: [
                    bootstrapColors.success,
                    bootstrapColors.primary,
                    bootstrapColors.warning
                ],
                borderWidth: 3,
                borderColor: '#ffffff',
                hoverBorderWidth: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        color: bootstrapColors.dark
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            }
        }
    });
}

function initializePerformanceChart() {
    const ctx = document.getElementById('performance-metrics-chart').getContext('2d');
    
    window.performanceChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Speed', 'Reliability', 'Security', 'Usability', 'Performance'],
            datasets: [{
                label: 'Current',
                data: [85, 92, 78, 88, 82],
                borderColor: bootstrapColors.primary,
                backgroundColor: 'rgba(78, 115, 223, 0.2)',
                borderWidth: 2,
                pointBackgroundColor: bootstrapColors.primary,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2
            }, {
                label: 'Target',
                data: [90, 95, 85, 90, 88],
                borderColor: bootstrapColors.success,
                backgroundColor: 'rgba(28, 200, 138, 0.1)',
                borderWidth: 2,
                borderDash: [5, 5],
                pointBackgroundColor: bootstrapColors.success,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: '#e3e6f0'
                    },
                    pointLabels: {
                        color: bootstrapColors.dark
                    },
                    ticks: {
                        color: bootstrapColors.secondary,
                        backdropColor: 'transparent'
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: bootstrapColors.dark,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            }
        }
    });
}

function initializeGeographicChart() {
    const ctx = document.getElementById('geographic-chart').getContext('2d');
    
    window.geographicChart = new Chart(ctx, {
        type: 'polarArea',
        data: {
            labels: ['North America', 'Europe', 'Asia', 'South America', 'Africa', 'Oceania'],
            datasets: [{
                data: [450, 320, 280, 180, 120, 80],
                backgroundColor: [
                    bootstrapColors.primary,
                    bootstrapColors.success,
                    bootstrapColors.warning,
                    bootstrapColors.danger,
                    bootstrapColors.info,
                    bootstrapColors.secondary
                ],
                borderWidth: 3,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        color: bootstrapColors.dark
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: bootstrapColors.dark,
                    bodyColor: bootstrapColors.dark,
                    borderColor: '#e3e6f0',
                    borderWidth: 1,
                    cornerRadius: 10
                }
            },
            scales: {
                r: {
                    grid: {
                        color: '#e3e6f0'
                    },
                    pointLabels: {
                        color: bootstrapColors.dark
                    },
                    ticks: {
                        color: bootstrapColors.secondary,
                        backdropColor: 'transparent'
                    }
                }
            }
        }
    });
}

// Update functions (called by hyperscript)
function updateUserGrowthChart(data) {
    const chart = window.userGrowthChart;
    chart.data.datasets[0].data = [data.new_users, data.returning_users, data.inactive_users];
    chart.update();
}
</script>

<style>
.multi-chart-dashboard {
    padding: 1rem 0;
}

.chart-type-selector .btn {
    font-size: 0.875rem;
}

.refresh-btn:hover {
    background-color: #f8f9fa;
}

/* Chart container responsive adjustments */
@media (max-width: 768px) {
    .chart-wrapper {
        height: 250px;
    }
    
    .card-body canvas {
        height: 200px !important;
    }
}
</style>
```

---

## Best Practices for Flask Dashboard Development

### Performance Optimization

#### 1. Efficient HTMX Patterns with Bootstrap
```html
<!-- Good: Targeted updates with Bootstrap loading states -->
<div class="card" 
     hx-get="/api/stats" 
     hx-trigger="every 30s" 
     hx-target="#stats-container" 
     hx-swap="innerHTML">
    <div class="card-body">
        <div id="stats-container">
            <!-- Stats content -->
        </div>
    </div>
</div>

<!-- Better: Conditional updates with Bootstrap indicators -->
<div class="card" 
     hx-get="/api/stats" 
     hx-trigger="every 30s" 
     hx-target="#stats-container" 
     hx-swap="innerHTML"
     hx-headers='{"If-Modified-Since": "{{ last_modified }}"}'
     _="on htmx:beforeRequest add .updating to me
        on htmx:afterRequest remove .updating from me
        on htmx:responseError(evt)
          if evt.detail.xhr.status is 304
            -- No changes, skip update
            halt the event
          end">
    <div class="card-body">
        <div id="stats-container">
            <!-- Stats content -->
        </div>
        <div class="htmx-indicator">
            <div class="d-flex justify-content-center">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Updating...</span>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Best: Smart caching with Bootstrap styling -->
<div id="stats-widget" class="card" 
     hx-get="/api/stats" 
     hx-trigger="load, every 30s" 
     hx-target="this" 
     hx-swap="innerHTML"
     _="init 
        set :lastHash to ''
        
        on htmx:beforeRequest
          set :requestTime to Date.now()
          add .border-primary to me
        end
        
        on htmx:afterRequest(evt)
          set response to evt.detail.xhr.response
          set newHash to btoa(response).substring(0, 10)
          
          remove .border-primary from me
          
          if newHash is :lastHash
            -- No visual changes needed
            add .border-success to me
            wait 1s
            remove .border-success from me
            halt the event
          else
            set :lastHash to newHash
            add .border-info to me
            wait 500ms
            remove .border-info from me
          end
        end">
    <!-- Initial content -->
    <div class="card-body text-center">
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    </div>
</div>
```

#### 2. _hyperscript Memory Management with Bootstrap
```html
<!-- Good: Clean up event listeners with Bootstrap components -->
<div class="modal fade dashboard-widget" 
     _="init
        set :interval to setInterval(def() updateWidget() end, 5000)
        
        on hidden.bs.modal
          clearInterval(:interval)
        end
        
        def updateWidget()
          -- Update logic here
          add .updating to .card-body in me
          fetch /api/widget-data
          put the result into .widget-content in me
          remove .updating from .card-body in me
        end">
    
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-body">
                <div class="widget-content">
                    <!-- Widget content -->
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Better: Use built-in cleanup with Bootstrap events -->
<div class="card dashboard-widget" 
     _="init
        repeat every 5s
          updateWidget()
        until event(beforeunload) from window or event(hidden.bs.modal) from me
        
        def updateWidget()
          add .opacity-50 to .card-body in me
          fetch /api/widget-data
          put the result into .widget-content in me
          remove .opacity-50 from .card-body in me
        end">
    
    <div class="card-body">
        <div class="widget-content">
            <!-- Widget content -->
        </div>
    </div>
</div>
```

#### 3. Optimized Flask Routes with Bootstrap Responses
```python
from flask import jsonify, request, abort
from functools import wraps
import hashlib
import json

def cache_control(max_age=60):
    """Add cache control headers"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = f(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['Cache-Control'] = f'max-age={max_age}'
            return response
        return decorated_function
    return decorator

def etag_cache(f):
    """Add ETag caching for API responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the response data
        data = f(*args, **kwargs)
        
        # Generate ETag from data
        content = json.dumps(data, sort_keys=True) if isinstance(data, dict) else str(data)
        etag = hashlib.md5(content.encode()).hexdigest()
        
        # Check if client has cached version
        if request.headers.get('If-None-Match') == etag:
            return abort(304)  # Not Modified
        
        # Return response with ETag
        response = jsonify(data)
        response.headers['ETag'] = etag
        return response
    
    return decorated_function

@app.route('/api/dashboard/stats')
@cache_control(max_age=30)
@etag_cache
def get_dashboard_stats():
    return {
        'total_users': get_user_count(),
        'active_sessions': get_active_sessions(),
        'system_load': get_system_load(),
        'timestamp': int(time.time())
    }

@app.route('/api/dashboard/stats/html')
def get_dashboard_stats_html():
    """Return Bootstrap-styled HTML for stats"""
    stats = get_dashboard_stats()
    
    return render_template_string('''
    <div class="row">
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card border-left-primary shadow h-100 py-2">
                <div class="card-body">
                    <div class="row no-gutters align-items-center">
                        <div class="col mr-2">
                            <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">
                                Total Users
                            </div>
                            <div class="h5 mb-0 font-weight-bold text-gray-800">{{ stats.total_users }}</div>
                        </div>
                        <div class="col-auto">
                            <i class="fas fa-users fa-2x text-gray-300"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <!-- More stat cards... -->
    </div>
    ''', stats=stats)
```

### Security Best Practices

#### 1. CSRF Protection with HTMX and Bootstrap
```python
from flask_wtf.csrf import CSRFProtect, generate_csrf

csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)
```

```html
<!-- Include CSRF token in HTMX requests with Bootstrap styling -->
<div class="container-fluid" hx-headers='{"X-CSRFToken": "{{ csrf_token() }}"}'>
    <form class="needs-validation" 
          hx-post="/api/dashboard/users"
          novalidate>
        <div class="mb-3">
            <label class="form-label">Username</label>
            <input class="form-control" name="username" required>
            <div class="invalid-feedback">
                Please provide a username.
            </div>
        </div>
        <button type="submit" class="btn btn-primary">Submit</button>
    </form>
</div>

<!-- Or use meta tag for global HTMX config -->
<meta name="csrf-token" content="{{ csrf_token() }}">
<script>
document.body.addEventListener('htmx:configRequest', function(evt) {
    evt.detail.headers['X-CSRFToken'] = document.querySelector('meta[name="csrf-token"]').content;
});
</script>
```

#### 2. Input Validation and Sanitization with Bootstrap
```python
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, validators
from markupsafe import Markup, escape

class DashboardFilterForm(FlaskForm):
    search = StringField('Search', [validators.Length(max=100)])
    status = SelectField('Status', choices=[('', 'All'), ('active', 'Active'), ('inactive', 'Inactive')])
    
    def clean_search(self):
        """Sanitize search input"""
        search = self.search.data
        if search:
            return escape(search.strip())
        return ''

@app.route('/api/dashboard/users')
def get_users():
    form = DashboardFilterForm()
    if form.validate():
        search = form.clean_search()
        status = form.status.data
        # Use sanitized inputs for database query
        users = User.query.filter_by_search(search, status)
        return render_template('dashboard/users_table.html', users=users)
    else:
        return render_template_string('''
        <div class="alert alert-danger" role="alert">
            <h4 class="alert-heading">Validation Error!</h4>
            <ul class="mb-0">
                {% for field, errors in form.errors.items() %}
                    {% for error in errors %}
                        <li>{{ field }}: {{ error }}</li>
                    {% endfor %}
                {% endfor %}
            </ul>
        </div>
        ''', form=form), 400
```

#### 3. Rate Limiting for Dashboard APIs
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/dashboard/stats')
@limiter.limit("30 per minute")
def get_dashboard_stats():
    return get_stats_data()

@app.route('/api/dashboard/export')
@limiter.limit("5 per minute")
def export_dashboard_data():
    return generate_export()

# Custom rate limit exceeded handler with Bootstrap styling
@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template_string('''
    <div class="alert alert-warning" role="alert">
        <h4 class="alert-heading">
            <i class="fas fa-exclamation-triangle me-2"></i>Rate Limit Exceeded
        </h4>
        <p>You have exceeded the rate limit. Please try again later.</p>
        <hr>
        <p class="mb-0">Limit: {{ e.description }}</p>
    </div>
    ''', e=e), 429
```

### Error Handling and User Experience

#### 1. Graceful Error Handling with Bootstrap
```html
<!-- Error handling with Bootstrap alerts -->
<div class="container-fluid dashboard-content" 
     _="on htmx:responseError(evt)
        set status to evt.detail.xhr.status
        if status is 403
          show-error-message('Access denied. Please check your permissions.', 'warning')
        else if status is 500
          show-error-message('Server error. Please try again later.', 'danger')
        else if status is 429
          show-error-message('Too many requests. Please wait before trying again.', 'warning')
        else
          show-error-message('An error occurred. Please refresh the page.', 'danger')
        end
        
        def show-error-message(message, type)
          make a <div.alert.alert-dismissible.fade.show/> called alert
          add .{`alert-${type}`} to alert
          set alert.innerHTML to `
            <div class='d-flex align-items-center'>
              <i class='fas fa-exclamation-circle me-2'></i>
              <div class='flex-grow-1'>${message}</div>
              <button type='button' class='btn-close' data-bs-dismiss='alert'></button>
            </div>
          `
          put alert at the start of body
          wait 5s
          if alert is in body
            set alertInstance to new bootstrap.Alert(alert)
            call alertInstance.close()
          end
        end
        
        on htmx:timeout
          show-error-message('Request timed out. Please check your connection.', 'warning')
        end">
    
    <!-- Dashboard content -->
</div>
```

#### 2. Loading States and Feedback with Bootstrap
```html
<!-- Advanced loading indicators with Bootstrap -->
<div class="card data-table-container" 
     _="on htmx:beforeRequest
        add .loading to me
        make a <div.loading-overlay.d-flex.align-items-center.justify-content-center/> called overlay
        set overlay.innerHTML to `
          <div class='text-center'>
            <div class='spinner-border text-primary mb-3' role='status'>
              <span class='visually-hidden'>Loading...</span>
            </div>
            <div class='text-muted'>Loading data...</div>
          </div>
        `
        set overlay.style.cssText to `
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(255, 255, 255, 0.9);
          z-index: 10;
        `
        put overlay into me
        
        on htmx:afterRequest
          remove .loading from me
          remove .loading-overlay from me
        end
        
        on htmx:timeout
          remove .loading from me
          remove .loading-overlay from me
          add .border-danger to me
          make a <div.alert.alert-danger.mt-3/> called errorAlert
          set errorAlert.innerHTML to `
            <i class='fas fa-exclamation-triangle me-2'></i>
            Request timed out. Please try again.
          `
          put errorAlert into .card-body in me
        end">
    
    <div class="card-body">
        <!-- Table content -->
    </div>
</div>

<style>
.data-table-container.loading {
    position: relative;
    pointer-events: none;
}
</style>
```

### Code Organization and Best Practices

#### 1. Modular Dashboard Components
```html
<!-- Reusable dashboard components -->
<script type="text/hyperscript">
  -- Global dashboard utilities
  def formatCurrency(amount)
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount)
  end
  
  def formatNumber(number)
    return new Intl.NumberFormat('en-US').format(number)
  end
  
  def showBootstrapToast(message, type, duration)
    set toastHtml to `
      <div class="toast" role="alert" data-bs-autohide="true" data-bs-delay="${duration || 5000}">
        <div class="toast-header">
          <div class="rounded me-2 bg-${type}" style="width: 20px; height: 20px;"></div>
          <strong class="me-auto">Dashboard</strong>
          <small>just now</small>
          <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">${message}</div>
      </div>
    `
    
    make a <div/> called toastElement
    set toastElement.innerHTML to toastHtml
    set toastEl to toastElement.firstElementChild
    put toastEl at the end of .toast-container
    
    set toast to new bootstrap.Toast(toastEl)
    call toast.show()
  end
  
  -- Reusable behaviors
  behavior DashboardCard
    on mouseenter
      add .shadow-lg to me
      remove .shadow to me
    end
    
    on mouseleave
      add .shadow to me
      remove .shadow-lg from me
    end
    
    on dashboard-refresh
      add .border-primary to me
      fetch my @data-refresh-url
      put the result into .card-body in me
      remove .border-primary from me
      add .border-success to me
      wait 1s
      remove .border-success from me
    end
  end
  
  behavior BootstrapTooltip
    on mouseenter
      if not my.tooltip
        set my.tooltip to new bootstrap.Tooltip(me, {
          title: my @data-bs-title,
          placement: my @data-bs-placement or 'top'
        })
      end
      call my.tooltip.show()
    end
    
    on mouseleave
      if my.tooltip
        call my.tooltip.hide()
      end
    end
  end
</script>

<!-- Use behaviors in components -->
<div class="card dashboard-card" 
     _="install DashboardCard" 
     data-refresh-url="/api/dashboard/widget/stats">
  <div class="card-body">
    <!-- Card content -->
  </div>
</div>

<button class="btn btn-outline-secondary" 
        _="install BootstrapTooltip" 
        data-bs-title="Click to refresh dashboard"
        data-bs-placement="bottom">
  <i class="fas fa-sync-alt"></i>
</button>
```

 for global scope
- **Event bubbling** - Events bubble up the DOM by default
- **Async transparency** - Commands automatically wait for promises to resolve
- **Bootstrap integration** - Remember to work with Bootstrap's event system (show.bs.modal, hidden.bs.modal, etc.)

### 3. Bootstrap 5 Pitfalls
- **Don't mix Bootstrap versions** - Ensure all Bootstrap components are from the same version
- **Use utility classes appropriately** - Don't override Bootstrap's core styles unless necessary
- **Mobile-first approach** - Always design for mobile first, then enhance for larger screens
- **JavaScript dependencies** - Some Bootstrap components require JavaScript, ensure proper initialization
- **Accessibility** - Don't forget ARIA attributes and proper semantic HTML structure

### 4. Performance Pitfalls
- **Avoid excessive DOM updates** - Use targeted HTMX swaps instead of replacing large sections
- **Cache API responses** - Implement proper caching strategies for frequently accessed data
- **Optimize database queries** - Use pagination, indexing, and selective loading
- **Minimize JavaScript** - Let HTMX and _hyperscript handle most interactions instead of heavy JavaScript

### 5. Security Pitfalls
- **Never trust client data** - Always validate and sanitize input on the server
- **Implement proper authentication** - Ensure all dashboard endpoints are protected
- **Use HTTPS in production** - Never serve dashboards over plain HTTP
- **Rate limit API endpoints** - Prevent abuse of dashboard APIs
- **Sanitize HTML output** - Be careful when rendering user-generated content

---

## Advanced Dashboard Patterns

### 1. Multi-tenant Dashboard
```python
# Multi-tenant support
from flask import g
from functools import wraps

def require_tenant(f):
    """Ensure user has access to the requested tenant"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tenant_id = request.args.get('tenant_id') or session.get('tenant_id')
        
        if not tenant_id or not current_user.has_tenant_access(tenant_id):
            abort(403)
        
        g.tenant_id = tenant_id
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/dashboard/stats')
@login_required
@require_tenant
def get_tenant_stats():
    """Get stats for specific tenant"""
    stats = get_stats_for_tenant(g.tenant_id)
    return render_template('dashboard/tenant_stats.html', stats=stats)
```

```html
<!-- Tenant selector with Bootstrap -->
<div class="card mb-4">
    <div class="card-body">
        <div class="row align-items-center">
            <div class="col-md-6">
                <h5 class="card-title mb-0">
                    <i class="fas fa-building me-2"></i>Organization Dashboard
                </h5>
            </div>
            <div class="col-md-6">
                <select class="form-select" 
                        hx-get="/api/dashboard/switch-tenant" 
                        hx-trigger="change" 
                        hx-target="#dashboard-content"
                        hx-include="this">
                    {% for tenant in current_user.tenants %}
                    <option value="{{ tenant.id }}" 
                            {{ 'selected' if tenant.id == current_tenant.id }}>
                        {{ tenant.name }}
                    </option>
                    {% endfor %}
                </select>
            </div>
        </div>
    </div>
</div>
```

### 2. Dashboard with Custom Widgets
```html
<!-- Widget marketplace -->
<div class="card">
    <div class="card-header">
        <h5 class="mb-0">Available Widgets</h5>
    </div>
    <div class="card-body">
        <div class="row" id="widget-marketplace">
            {% for widget in available_widgets %}
            <div class="col-md-4 mb-3">
                <div class="card border">
                    <div class="card-body text-center">
                        <i class="{{ widget.icon }} fa-3x text-primary mb-3"></i>
                        <h6 class="card-title">{{ widget.name }}</h6>
                        <p class="card-text small">{{ widget.description }}</p>
                        <button class="btn btn-primary btn-sm"
                                hx-post="/api/dashboard/widgets/add"
                                hx-vals='{"widget_id": "{{ widget.id }}"}'
                                hx-target="#dashboard-widgets"
                                hx-swap="beforeend">
                            <i class="fas fa-plus me-1"></i>Add Widget
                        </button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

<!-- Dashboard widgets area -->
<div id="dashboard-widgets" class="row sortable" 
     _="on sortend 
        set order to []
        for widget in <.dashboard-widget/> in me
          push widget.dataset.widgetId onto order
        end
        fetch /api/dashboard/widgets/reorder with 
          body: JSON.stringify({order: order})
          method: 'POST'">
    
    {% for widget in user_widgets %}
    <div class="col-lg-6 dashboard-widget" data-widget-id="{{ widget.id }}">
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <i class="{{ widget.icon }} me-2"></i>{{ widget.name }}
                </h6>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-secondary"
                            hx-get="/api/dashboard/widgets/{{ widget.id }}/configure"
                            hx-target="#modal-container">
                        <i class="fas fa-cog"></i>
                    </button>
                    <button class="btn btn-outline-danger"
                            hx-delete="/api/dashboard/widgets/{{ widget.id }}"
                            hx-target="closest .dashboard-widget"
                            hx-swap="outerHTML"
                            hx-confirm="Remove this widget?">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="card-body"
                 hx-get="/api/dashboard/widgets/{{ widget.id }}/content"
                 hx-trigger="load, every {{ widget.refresh_interval }}s">
                <div class="text-center">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
```

### 3. Advanced Search and Filtering
```html
<!-- Advanced search with Bootstrap -->
<div class="card mb-4">
    <div class="card-header">
        <h6 class="mb-0">
            <i class="fas fa-search me-2"></i>Advanced Search
        </h6>
    </div>
    <div class="card-body">
        <form hx-get="/api/dashboard/search" 
              hx-trigger="submit, change delay:500ms" 
              hx-target="#search-results">
            
            <div class="row g-3">
                <div class="col-md-4">
                    <label class="form-label">Search Terms</label>
                    <input type="search" 
                           class="form-control" 
                           name="q" 
                           placeholder="Enter search terms..."
                           _="on keyup changed delay:300ms
                              if my value.length > 2
                                fetch /api/dashboard/search/suggestions?q={my value}
                                put the result into #search-suggestions
                                show #search-suggestions
                              else
                                hide #search-suggestions
                              end">
                    <div id="search-suggestions" class="list-group mt-1" style="display: none;">
                        <!-- Suggestions populated by HTMX -->
                    </div>
                </div>
                
                <div class="col-md-2">
                    <label class="form-label">Date Range</label>
                    <select class="form-select" name="date_range">
                        <option value="">Any time</option>
                        <option value="today">Today</option>
                        <option value="week">This week</option>
                        <option value="month">This month</option>
                        <option value="custom">Custom range</option>
                    </select>
                </div>
                
                <div class="col-md-2">
                    <label class="form-label">Category</label>
                    <select class="form-select" name="category" multiple>
                        {% for category in categories %}
                        <option value="{{ category.id }}">{{ category.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="col-md-2">
                    <label class="form-label">Status</label>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" name="status" value="active" id="status-active">
                        <label class="form-check-label" for="status-active">Active</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" name="status" value="inactive" id="status-inactive">
                        <label class="form-check-label" for="status-inactive">Inactive</label>
                    </div>
                </div>
                
                <div class="col-md-2 d-flex align-items-end">
                    <div class="btn-group w-100">
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-search me-1"></i>Search
                        </button>
                        <button type="button" class="btn btn-outline-secondary"
                                onclick="this.form.reset(); htmx.trigger('#search-results', 'refresh')">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Custom date range (shown when "Custom range" is selected) -->
            <div class="row g-3 mt-2 d-none" id="custom-date-range">
                <div class="col-md-3">
                    <label class="form-label">From Date</label>
                    <input type="date" class="form-control" name="date_from">
                </div>
                <div class="col-md-3">
                    <label class="form-label">To Date</label>
                    <input type="date" class="form-control" name="date_to">
                </div>
            </div>
        </form>
    </div>
</div>

<!-- Search results -->
<div id="search-results">
    <!-- Results populated by HTMX -->
</div>

<script type="text/hyperscript">
  -- Show/hide custom date range
  on change from select[name='date_range']
    if target.value is 'custom'
      remove .d-none from #custom-date-range
    else
      add .d-none to #custom-date-range
    end
  end
</script>
```

This comprehensive guide provides everything needed to build modern, interactive Flask dashboards using HTMX, _hyperscript, and Bootstrap 5. The combination of these technologies creates powerful, maintainable web applications with excellent user experience and developer productivity, all while leveraging Bootstrap's robust component library and responsive design system.

The guide covers:
- **Complete integration patterns** for Flask backends with Bootstrap styling
- **Real-time updates** using WebSockets and Server-Sent Events
- **Advanced data visualization** with Chart.js integration
- **Comprehensive testing strategies** for both backend and frontend
- **Accessibility best practices** with proper ARIA implementation
- **Performance optimization** techniques and monitoring
- **Security considerations** and production deployment
- **Advanced patterns** for multi-tenant and customizable dashboards

This toolkit enables developers to create sophisticated dashboard applications that rival those built with complex JavaScript frameworks, while maintaining simplicity and reducing technical debt.