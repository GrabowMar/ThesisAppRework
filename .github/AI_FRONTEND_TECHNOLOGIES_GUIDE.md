# AI Frontend Technologies Guide for Flask Dashboards: HTMX, _hyperscript, and missing.css

This comprehensive guide provides AI models with detailed information about three powerful frontend technologies specifically for building dynamic Flask dashboards and admin interfaces. These technologies work together to create sophisticated, interactive web dashboards without heavy JavaScript frameworks.

## Table of Contents
1. [HTMX for Flask Dashboards](#htmx)
2. [_hyperscript for Dashboard Interactions](#_hyperscript)
3. [missing.css for Dashboard Styling](#missingcss)
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
<div class="stats-widget card" 
     hx-get="/api/dashboard/stats" 
     hx-trigger="load, every 30s"
     hx-swap="innerHTML">
    <div class="loading">Loading stats...</div>
</div>

<!-- Chart that updates based on date range -->
<div class="chart-container">
    <div class="chart-controls">
        <select name="timerange" 
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
    
    <div id="revenue-chart" 
         hx-get="/api/dashboard/chart/revenue?timerange=7d" 
         hx-trigger="load">
        Loading chart...
    </div>
</div>
```

#### Data Tables with Pagination and Sorting
```html
<!-- Dashboard data table -->
<div class="table-container">
    <!-- Table controls -->
    <div class="table-controls">
        <input type="search" 
               name="search" 
               placeholder="Search users..."
               hx-get="/api/dashboard/table/users" 
               hx-trigger="keyup changed delay:300ms" 
               hx-target="#users-table"
               hx-include="[name='sort'], [name='order']">
               
        <select name="per_page"
                hx-get="/api/dashboard/table/users" 
                hx-trigger="change" 
                hx-target="#users-table"
                hx-include="[name='search'], [name='sort'], [name='order']">
            <option value="10">10 per page</option>
            <option value="25">25 per page</option>
            <option value="50">50 per page</option>
        </select>
        
        <input type="hidden" name="sort" value="created_at">
        <input type="hidden" name="order" value="desc">
    </div>
    
    <!-- Table content -->
    <div id="users-table" 
         hx-get="/api/dashboard/table/users" 
         hx-trigger="load">
        Loading table...
    </div>
</div>
```

#### Inline Editing
```html
<!-- Inline editable user row -->
<tr id="user-{{ user.id }}">
    <td>
        <span class="editable-field" data-field="username">
            {{ user.username }}
        </span>
    </td>
    <td>
        <span class="editable-field" data-field="email">
            {{ user.email }}
        </span>
    </td>
    <td>
        <div class="status-badge {{ 'active' if user.is_active else 'inactive' }}"
             hx-post="/api/dashboard/users/{{ user.id }}/toggle-status"
             hx-target="this"
             hx-swap="outerHTML">
            {{ 'Active' if user.is_active else 'Inactive' }}
        </div>
    </td>
    <td>
        <button class="btn-edit" 
                hx-get="/api/dashboard/users/{{ user.id }}/edit"
                hx-target="#user-{{ user.id }}"
                hx-swap="outerHTML">
            Edit
        </button>
        <button class="btn-delete" 
                hx-delete="/api/dashboard/users/{{ user.id }}"
                hx-target="#user-{{ user.id }}"
                hx-swap="outerHTML"
                hx-confirm="Are you sure you want to delete this user?">
            Delete
        </button>
    </td>
</tr>
```

#### Dashboard Modals and Forms
```html
<!-- Add user button -->
<button class="btn-primary" 
        hx-get="/api/dashboard/users/new" 
        hx-target="#modal-container" 
        hx-swap="innerHTML">
    Add New User
</button>

<!-- Modal container -->
<div id="modal-container"></div>

<!-- Flask returns this modal form -->
<div class="modal-overlay">
    <div class="modal">
        <div class="modal-header">
            <h3>Add New User</h3>
            <button class="modal-close" 
                    onclick="document.getElementById('modal-container').innerHTML = ''">
                ×
            </button>
        </div>
        
        <form hx-post="/api/dashboard/users" 
              hx-target="#users-table" 
              hx-swap="afterbegin"
              hx-on::after-request="if(event.detail.successful) document.getElementById('modal-container').innerHTML = ''">
            
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" 
                       name="username" 
                       required
                       hx-get="/api/dashboard/validate/username"
                       hx-trigger="blur"
                       hx-target="#username-validation">
                <div id="username-validation"></div>
            </div>
            
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" name="email" required>
            </div>
            
            <div class="form-actions">
                <button type="submit" class="btn-primary">Create User</button>
                <button type="button" class="btn-secondary" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                    Cancel
                </button>
            </div>
        </form>
    </div>
</div>
```

#### Bulk Operations
```html
<!-- Bulk actions toolbar -->
<div class="bulk-actions" style="display: none;" id="bulk-actions">
    <span class="selected-count">0 selected</span>
    <button hx-post="/api/dashboard/users/bulk-activate" 
            hx-include="[name='selected_users']:checked"
            hx-target="#users-table"
            hx-swap="innerHTML">
        Activate Selected
    </button>
    <button hx-delete="/api/dashboard/users/bulk-delete" 
            hx-include="[name='selected_users']:checked"
            hx-target="#users-table"
            hx-swap="innerHTML"
            hx-confirm="Delete selected users?">
        Delete Selected
    </button>
</div>

<!-- Table with checkboxes -->
<table>
    <thead>
        <tr>
            <th>
                <input type="checkbox" id="select-all">
            </th>
            <th>Username</th>
            <th>Email</th>
            <th>Status</th>
        </tr>
    </thead>
    <tbody>
        {% for user in users %}
        <tr>
            <td>
                <input type="checkbox" 
                       name="selected_users" 
                       value="{{ user.id }}"
                       class="user-checkbox">
            </td>
            <td>{{ user.username }}</td>
            <td>{{ user.email }}</td>
            <td>{{ user.status }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

### Dashboard Filters and Search
```html
<!-- Advanced filter panel -->
<div class="filter-panel card">
    <h4>Filters</h4>
    <form hx-get="/api/dashboard/table/users" 
          hx-trigger="change, submit" 
          hx-target="#users-table"
          hx-swap="innerHTML">
        
        <div class="filter-group">
            <label>Status</label>
            <select name="status">
                <option value="">All</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
            </select>
        </div>
        
        <div class="filter-group">
            <label>Registration Date</label>
            <input type="date" name="date_from">
            <input type="date" name="date_to">
        </div>
        
        <div class="filter-group">
            <label>Role</label>
            <select name="role" multiple>
                {% for role in roles %}
                <option value="{{ role.id }}">{{ role.name }}</option>
                {% endfor %}
            </select>
        </div>
        
        <div class="filter-actions">
            <button type="submit" class="btn-primary">Apply Filters</button>
            <button type="button" 
                    hx-get="/api/dashboard/table/users" 
                    hx-target="#users-table"
                    onclick="this.closest('form').reset()">
                Clear Filters
            </button>
        </div>
    </form>
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

<button hx-get="/api/data" hx-target="#result">
    Get Data
    <span class="htmx-indicator">Loading...</span>
</button>

<div id="result">
    <div class="htmx-indicator">Loading...</div>
</div>
```

#### Form Handling
```html
<!-- Basic form submission -->
<form hx-post="/api/contact" hx-target="#response">
    <input name="name" required>
    <input name="email" type="email" required>
    <button type="submit">Submit</button>
</form>

<!-- Form with validation -->
<form hx-post="/api/validate" hx-target="#errors" 
      hx-trigger="submit" hx-swap="innerHTML">
    <input name="username" hx-get="/api/check-username" 
           hx-trigger="blur" hx-target="#username-error">
    <div id="username-error"></div>
    <button type="submit">Submit</button>
</form>
```

#### Infinite Scroll
```html
<div id="content">
    <!-- Initial content -->
</div>
<div hx-get="/api/more-content?page=2" 
     hx-trigger="revealed" 
     hx-swap="outerHTML"
     hx-target="this">
    <div class="htmx-indicator">Loading more...</div>
</div>
```

#### Live Search
```html
<input type="search" 
       name="search"
       hx-get="/api/search" 
       hx-trigger="keyup changed delay:300ms" 
       hx-target="#search-results"
       placeholder="Search...">
<div id="search-results"></div>
```

#### Modal Dialogs
```html
<!-- Trigger -->
<button hx-get="/modal/edit-user/123" 
        hx-target="#modal-container" 
        hx-trigger="click">
    Edit User
</button>

<!-- Modal container -->
<div id="modal-container"></div>

<!-- Server returns modal HTML -->
<div class="modal" id="edit-modal">
    <div class="modal-content">
        <form hx-put="/api/user/123" hx-target="#edit-modal" hx-swap="outerHTML">
            <!-- Form fields -->
            <button type="submit">Save</button>
            <button type="button" onclick="document.getElementById('edit-modal').remove()">Cancel</button>
        </form>
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
<nav class="sidebar" 
     _="init set :collapsed to false
       on toggle-sidebar
         if :collapsed
           remove .collapsed from me
           set :collapsed to false
         else
           add .collapsed to me
           set :collapsed to true
         end
         send sidebar-changed(collapsed: :collapsed) to #main-content">
    
    <div class="sidebar-header">
        <h2>Dashboard</h2>
        <button _="on click send toggle-sidebar to .sidebar">☰</button>
    </div>
    
    <ul class="nav-menu">
        <li><a href="/dashboard">Overview</a></li>
        <li><a href="/dashboard/users">Users</a></li>
        <li><a href="/dashboard/reports">Reports</a></li>
    </ul>
</nav>

<!-- Main content area that responds to sidebar changes -->
<main id="main-content" 
      _="on sidebar-changed(collapsed) 
         if collapsed
           add .sidebar-collapsed to me
         else
           remove .sidebar-collapsed from me
         end">
    <!-- Dashboard content -->
</main>
```

#### Dynamic Widget Management
```html
<!-- Widget container with drag-and-drop reordering -->
<div class="dashboard-widgets" 
     _="on widget-moved(from, to)
        fetch /api/dashboard/save-layout with 
          body: JSON.stringify({from: from, to: to})
          method: 'POST'
          headers: {'Content-Type': 'application/json'}">
    
    <!-- Individual widgets -->
    <div class="widget" data-widget-id="stats" 
         _="install Draggable
           on widget-refresh
             fetch /api/dashboard/widget/stats
             put the result into me
           end">
        <div class="widget-header">
            <h3>Statistics</h3>
            <div class="widget-controls">
                <button _="on click send widget-refresh to my closest .widget">↻</button>
                <button _="on click send widget-minimize to my closest .widget">_</button>
                <button _="on click send widget-close to my closest .widget">×</button>
            </div>
        </div>
        <div class="widget-content">
            <!-- Stats content -->
        </div>
    </div>
</div>

<!-- Draggable behavior for widgets -->
<script type="text/hyperscript">
  behavior Draggable
    on mousedown
      if event.target matches '.widget-header'
        set :dragging to true
        set :startX to event.clientX
        set :startY to event.clientY
        set :originalIndex to Array.from(my parentElement.children).indexOf(me)
        
        repeat until event mouseup from elsewhere
          wait for mousemove(clientX, clientY) from elsewhere
          set my *left to (my offsetLeft + clientX - :startX) + 'px'
          set my *top to (my offsetTop + clientY - :startY) + 'px'
          set :startX to clientX
          set :startY to clientY
          
          -- Check for drop zones
          get closest <.widget/> to {x: clientX, y: clientY}
          if it is not me and it exists
            set :dropTarget to it
          end
        end
        
        if :dropTarget exists
          set :newIndex to Array.from(my parentElement.children).indexOf(:dropTarget)
          send widget-moved(from: :originalIndex, to: :newIndex) to my parentElement
        end
        
        set :dragging to false
        set my *left to 'auto'
        set my *top to 'auto'
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
<div class="view-switcher" 
     _="on click from .view-btn
        send state-change(key: 'currentView', value: target.dataset.view) to #dashboard-state
        remove .active from .view-btn
        add .active to target">
    
    <button class="view-btn active" data-view="grid">Grid</button>
    <button class="view-btn" data-view="list">List</button>
    <button class="view-btn" data-view="table">Table</button>
</div>

<!-- Data container that responds to state changes -->
<div id="data-container" 
     _="on dashboard-state-changed(state)
        if state.currentView is 'grid'
          add .grid-view to me
          remove .list-view from me
          remove .table-view from me
        else if state.currentView is 'list'
          add .list-view to me
          remove .grid-view from me
          remove .table-view from me
        else if state.currentView is 'table'
          add .table-view to me
          remove .grid-view from me
          remove .list-view from me
        end">
    <!-- Data items -->
</div>
```

#### Advanced Table Interactions
```html
<!-- Smart table with selection and sorting -->
<table class="dashboard-table" 
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
    
    <thead>
        <tr>
            <th>
                <input type="checkbox" 
                       _="on change send select-all to my closest table">
            </th>
            <th _="on click 
                   send sort-column(column: 'name', direction: my @data-sort-direction or 'asc') to #data-container
                   set my @data-sort-direction to (my @data-sort-direction is 'asc' ? 'desc' : 'asc')">
                Name <span class="sort-indicator">↕</span>
            </th>
            <th _="on click 
                   send sort-column(column: 'email', direction: my @data-sort-direction or 'asc') to #data-container">
                Email <span class="sort-indicator">↕</span>
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
                <input type="checkbox" 
                       name="selected_users" 
                       value="{{ user.id }}">
            </td>
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
            <td>
                <button _="on click 
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
<div id="notifications" class="notification-container" 
     _="on show-notification(message, type, duration)
        make a <div.notification/> called notification
        add .{type} to notification
        put message into notification
        make a <button.notification-close/> called closeBtn
        put '×' into closeBtn
        put closeBtn into notification
        put notification at the end of me
        
        -- Auto-hide after duration
        if duration > 0
          wait {duration}ms
          remove notification
        end
       end
       
       on click from .notification-close
         remove the closest .notification
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
           send show-notification(message: 'Error creating user', type: 'error', duration: 5000) to #notifications
         end">
    <!-- Form fields -->
</form>
```

#### Dashboard Search and Filtering
```html
<!-- Advanced search component -->
<div class="search-component" 
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
    
    <div class="search-box">
        <input type="search" 
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
        
        <button type="button" 
                _="on click 
                  toggle .expanded on .search-component
                  if .search-component matches .expanded
                    focus() on input[name='search']
                  end">
            🔍
        </button>
    </div>
    
    <!-- Search suggestions dropdown -->
    <div id="search-suggestions" class="search-suggestions" style="display: none;">
        <!-- Populated by HTMX -->
    </div>
    
    <!-- Advanced filters (shown when expanded) -->
    <div class="advanced-filters" 
         _="on filter-change
           set filters to {}
           for input in <input, select/> in me
             if input.value is not empty
               set filters[input.name] to input.value
             end
           end
           send filters-changed(filters: filters) to body">
        
        <select name="category" 
                _="on change send filter-change to .advanced-filters">
            <option value="">All Categories</option>
            <option value="users">Users</option>
            <option value="orders">Orders</option>
        </select>
        
        <input type="date" 
               name="date_from" 
               _="on change send filter-change to .advanced-filters">
        
        <input type="date" 
               name="date_to" 
               _="on change send filter-change to .advanced-filters">
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
<div class="stats-widget" 
     _="on websocket-message(data)
        if data.type is 'stats-update'
          put data.stats.total_users into #total-users
          put data.stats.active_sessions into #active-sessions
        end">
    
    <div class="stat">
        <span class="stat-label">Total Users</span>
        <span id="total-users" class="stat-value">{{ stats.total_users }}</span>
    </div>
    
    <div class="stat">
        <span class="stat-label">Active Sessions</span>
        <span id="active-sessions" class="stat-value">{{ stats.active_sessions }}</span>
    </div>
</div>

<!-- Activity feed that updates in real-time -->
<div class="activity-feed" 
     _="on websocket-message(data)
        if data.type is 'activity'
          make a <div.activity-item/> called item
          put data.activity.message into item
          put item at the start of #activity-list
          
          -- Keep only last 50 items
          set items to <.activity-item/> in #activity-list
          if items.length > 50
            remove items[50]
          end
        end">
    
    <h3>Recent Activity</h3>
    <div id="activity-list">
        <!-- Activity items appear here -->
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
<button _="on click log 'Button clicked!'">Click Me</button>

<!-- Multiple events -->
<div _="on mouseenter add .hover
        on mouseleave remove .hover">Hover Me</div>

<!-- Event with conditions -->
<input _="on keyup[key is 'Enter'] call submitForm()">

<!-- Event with parameters -->
<button _="on mousedown(button) 
           if button is 1 add .middle-clicked">Middle Click</button>

<!-- Event delegation -->
<div _="on click from .delete-btn
        remove the closest .item">
  <div class="item">Item 1 <button class="delete-btn">Delete</button></div>
</div>
```

### DOM Manipulation

#### Finding Elements
```html
<!-- CSS selectors as literals -->
<button _="on click add .highlight to .target">Highlight targets</button>
<button _="on click remove #item-123">Remove item</button>
<button _="on click toggle .hidden on <div.sidebar/>">Toggle sidebar</button>

<!-- Positional selectors -->
<button _="on click add .selected to the first .item">Select first</button>
<button _="on click remove the last .item">Remove last</button>
<button _="on click highlight random in .items">Random highlight</button>

<!-- Relative selectors -->
<button _="on click add .active to the next .tab">Next tab</button>
<button _="on click remove the previous .item">Previous item</button>
<button _="on click toggle .expanded on the closest .section">Toggle section</button>
```

#### Content Manipulation
```html
<!-- Setting content -->
<button _="on click put 'Hello World!' into #output">Set content</button>
<button _="on click set #output's innerHTML to 'New content'">Set innerHTML</button>

<!-- Appending/prepending -->
<button _="on click put 'New item' at the end of #list">Append</button>
<button _="on click put 'First item' at the start of #list">Prepend</button>

<!-- Positioning content -->
<button _="on click put 'Before' before #target">Insert before</button>
<button _="on click put 'After' after #target">Insert after</button>
```

#### Attributes and Styles
```html
<!-- Working with attributes -->
<button _="on click set @disabled to 'disabled' on #submit-btn">Disable</button>
<button _="on click remove @disabled from #submit-btn">Enable</button>
<button _="on click toggle @disabled on #submit-btn">Toggle disable</button>

<!-- Working with styles -->
<div _="on click set my *color to 'red'">Change color</div>
<div _="on click set *width of #box to '200px'">Resize box</div>
<div _="on mouseenter transition my *opacity to 1 over 300ms">Fade in</div>
```

### Variables and Data

#### Variable Scopes
```html
<!-- Local variables -->
<button _="on click 
           set x to 10 
           log x">Local variable</button>

<!-- Element-scoped variables (prefix with :) -->
<button _="on click 
           increment :count 
           put :count into the next <output/>">
  Count: <output>0</output>
</button>

<!-- Global variables (prefix with $) -->
<button _="on click 
           set $globalCounter to ($globalCounter or 0) + 1
           log $globalCounter">Global counter</button>

<!-- Explicit scoping -->
<button _="on click
           set local myVar to 'local'
           set element myElementVar to 'element'
           set global myGlobalVar to 'global'">Set variables</button>
```

#### Special Variables
```html
<!-- Built-in variables -->
<button _="on click log me">Log current element</button>
<button _="on click log event">Log current event</button>
<button _="on click log target">Log event target</button>
<button _="on click log detail">Log event detail</button>
<div _="on customEvent(data) log data">Handle custom event with data</div>
```

### Control Flow

#### Conditionals
```html
<!-- Basic if/else -->
<button _="on click 
           if I match .selected
             remove .selected from me
           else
             add .selected to me
           end">Toggle selection</button>

<!-- Natural language comparisons -->
<input _="on input
          if my value is not empty
            remove .error from me
          else
            add .error to me
          end">

<!-- Unless modifier -->
<button _="on click 
           add .processing unless I match .disabled">Process</button>
```

#### Loops
```html
<!-- For loops -->
<button _="on click
           for item in [1, 2, 3, 4, 5]
             put item at the end of #list
           end">Add numbers</button>

<!-- While loops -->
<button _="on click
           set i to 0
           repeat while i < 5
             log i
             increment i
           end">Count to 5</button>

<!-- Repeat with times -->
<button _="on click
           repeat 3 times
             put 'Hello' at the end of #output
           end">Say hello 3 times</button>
```

### Async Operations

#### Waiting and Timing
```html
<!-- Wait for time -->
<button _="on click
           put 'Processing...' into me
           wait 2s
           put 'Done!' into me">Process</button>

<!-- Wait for events -->
<button _="on click
           put 'Click continue...' into #status
           wait for continue
           put 'Continued!' into #status">
  Start Process
</button>
<button _="on click send continue to the previous <button/>">Continue</button>

<!-- Wait with timeout -->
<button _="on click
           put 'Waiting...' into #status
           wait for continue or 5s
           if the result's type is 'continue'
             put 'Got continue!' into #status
           else
             put 'Timed out!' into #status
           end">Wait with timeout</button>
```

#### Fetch Requests
```html
<!-- Basic fetch -->
<button _="on click
           fetch /api/data
           put the result into #content">Get data</button>

<!-- Fetch with error handling -->
<button _="on click
           fetch /api/data
           if the response's ok
             put the result into #content
           else
             put 'Error loading data' into #error
           end">Get data safely</button>

<!-- Fetch with POST -->
<form _="on submit
         fetch /api/submit with body: new FormData(me)
         put the result into #response
         reset() me">
  <input name="username">
  <button type="submit">Submit</button>
</form>
```

### Event Handling and Communication

#### Sending Custom Events
```html
<!-- Send events to other elements -->
<button _="on click send refresh to #data-panel">Refresh data</button>

<!-- Send events with data -->
<button _="on click 
           send update(id: 123, status: 'active') to #status-panel">
  Update status
</button>

<!-- Send events to multiple targets -->
<button _="on click send refresh to .data-panel">Refresh all panels</button>
```

#### Event Queueing
```html
<!-- Default: queue last -->
<button _="on click 
           wait 1s 
           put 'Done' into #output">Default queuing</button>

<!-- Queue all events -->
<button _="on click queue all
           increment :count
           wait 1s
           put :count into #output">Queue all</button>

<!-- Process every event immediately -->
<button _="on every click
           increment :count
           put :count into #output">Process every click</button>

<!-- Queue first only -->
<button _="on click queue first
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
</script>

<!-- Install behavior -->
<div _="install Draggable" class="draggable-box">Drag me!</div>
```

#### Transitions and Animations
```html
<!-- CSS transitions -->
<div _="on click 
        transition my *width to '200px' over 500ms
        then transition my *height to '200px' over 500ms">
  Animate me
</div>

<!-- Class-based animations -->
<div _="on click 
        add .animate then settle
        wait 1s
        remove .animate then settle">
  Animate with classes
</div>

<!-- Toggle with events -->
<div _="on mouseenter toggle .highlighted until mouseleave">
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
</script>

<button _="on click
           call calculateTotal([{price: 10}, {price: 20}])
           put utils.formatCurrency(it) into #total">
  Calculate total
</button>
```

---

## missing.css for Dashboard Styling

### Overview
missing.css provides an excellent foundation for Flask dashboard styling by offering beautiful defaults for semantic HTML elements and a comprehensive set of dashboard-specific components.

### Dashboard Layout Foundations

#### Basic Dashboard Structure
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask Dashboard</title>
    <link rel="stylesheet" href="https://unpkg.com/missing.css@1.1.3">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
</head>
<body class="dashboard-layout">
    <!-- Dashboard header -->
    <header class="dashboard-header">
        <div class="container">
            <div class="navbar">
                <a href="/dashboard" class="brand">
                    <img src="/static/logo.png" alt="Logo">
                    Dashboard
                </a>
                
                <nav class="nav-menu">
                    <a href="/dashboard">Overview</a>
                    <a href="/dashboard/users">Users</a>
                    <a href="/dashboard/reports">Reports</a>
                    <a href="/dashboard/settings">Settings</a>
                </nav>
                
                <div class="user-menu">
                    <div class="dropdown">
                        <button class="user-avatar">
                            {{ current_user.username }}
                        </button>
                        <div class="dropdown-content">
                            <a href="/profile">Profile</a>
                            <a href="/logout">Logout</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </header>
    
    <!-- Dashboard main layout -->
    <div class="dashboard-container">
        <!-- Sidebar -->
        <aside class="dashboard-sidebar">
            <nav class="sidebar-nav">
                <div class="nav-group">
                    <h4>Main</h4>
                    <a href="/dashboard" class="nav-item active">
                        <span class="nav-icon">📊</span>
                        Overview
                    </a>
                    <a href="/dashboard/analytics" class="nav-item">
                        <span class="nav-icon">📈</span>
                        Analytics
                    </a>
                </div>
                
                <div class="nav-group">
                    <h4>Management</h4>
                    <a href="/dashboard/users" class="nav-item">
                        <span class="nav-icon">👥</span>
                        Users
                    </a>
                    <a href="/dashboard/orders" class="nav-item">
                        <span class="nav-icon">🛒</span>
                        Orders
                    </a>
                </div>
            </nav>
        </aside>
        
        <!-- Main content -->
        <main class="dashboard-main">
            <div class="dashboard-content">
                {% block content %}{% endblock %}
            </div>
        </main>
    </div>
</body>
</html>
```

#### Dashboard-Specific CSS Extensions
```css
/* Dashboard layout enhancements for missing.css */
:root {
    --dashboard-sidebar-width: 280px;
    --dashboard-header-height: 64px;
    --dashboard-border-color: #e5e7eb;
    --dashboard-background: #f9fafb;
    --dashboard-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* Dashboard Layout */
.dashboard-layout {
    margin: 0;
    background: var(--dashboard-background);
}

.dashboard-header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: var(--dashboard-header-height);
    background: white;
    border-bottom: 1px solid var(--dashboard-border-color);
    z-index: 100;
}

.dashboard-container {
    display: flex;
    margin-top: var(--dashboard-header-height);
    min-height: calc(100vh - var(--dashboard-header-height));
}

.dashboard-sidebar {
    width: var(--dashboard-sidebar-width);
    background: white;
    border-right: 1px solid var(--dashboard-border-color);
    padding: 1rem 0;
    position: fixed;
    height: calc(100vh - var(--dashboard-header-height));
    overflow-y: auto;
}

.dashboard-main {
    margin-left: var(--dashboard-sidebar-width);
    flex: 1;
    padding: 2rem;
}

/* Navigation */
.sidebar-nav .nav-group {
    margin-bottom: 2rem;
}

.sidebar-nav .nav-group h4 {
    color: #6b7280;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
    padding: 0 1rem;
}

.nav-item {
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    color: #4b5563;
    text-decoration: none;
    transition: all 0.2s;
    border-left: 3px solid transparent;
}

.nav-item:hover {
    background: #f3f4f6;
    color: #1f2937;
}

.nav-item.active {
    background: #eff6ff;
    color: #2563eb;
    border-left-color: #2563eb;
}

.nav-icon {
    margin-right: 0.75rem;
    font-size: 1.25rem;
}

/* User menu */
.user-menu .dropdown {
    position: relative;
}

.user-avatar {
    background: var(--primary-color);
    color: white;
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.dropdown-content {
    display: none;
    position: absolute;
    right: 0;
    top: 100%;
    background: white;
    min-width: 160px;
    box-shadow: var(--dashboard-card-shadow);
    border-radius: 0.5rem;
    border: 1px solid var(--dashboard-border-color);
    z-index: 1000;
}

.dropdown:hover .dropdown-content {
    display: block;
}

.dropdown-content a {
    display: block;
    padding: 0.75rem 1rem;
    color: #4b5563;
    text-decoration: none;
}

.dropdown-content a:hover {
    background: #f3f4f6;
}
```

### Dashboard Components

#### Stats Cards and Widgets
```html
<!-- Stats overview cards -->
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-icon">👥</div>
        <div class="stat-content">
            <div class="stat-value">1,234</div>
            <div class="stat-label">Total Users</div>
            <div class="stat-change positive">+12% from last month</div>
        </div>
    </div>
    
    <div class="stat-card">
        <div class="stat-icon">💰</div>
        <div class="stat-content">
            <div class="stat-value">$45,678</div>
            <div class="stat-label">Revenue</div>
            <div class="stat-change negative">-3% from last month</div>
        </div>
    </div>
    
    <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-content">
            <div class="stat-value">89.2%</div>
            <div class="stat-label">Conversion Rate</div>
            <div class="stat-change positive">+2.1% from last month</div>
        </div>
    </div>
    
    <div class="stat-card">
        <div class="stat-icon">⚡</div>
        <div class="stat-content">
            <div class="stat-value">324</div>
            <div class="stat-label">Active Sessions</div>
            <div class="stat-change neutral">No change</div>
        </div>
    </div>
</div>

<style>
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.stat-card {
    background: white;
    border-radius: 0.75rem;
    padding: 1.5rem;
    box-shadow: var(--dashboard-card-shadow);
    display: flex;
    align-items: center;
    gap: 1rem;
}

.stat-icon {
    font-size: 2.5rem;
    background: var(--primary-color);
    color: white;
    width: 60px;
    height: 60px;
    border-radius: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

.stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: #1f2937;
    line-height: 1;
}

.stat-label {
    color: #6b7280;
    font-size: 0.875rem;
    margin: 0.25rem 0;
}

.stat-change {
    font-size: 0.75rem;
    font-weight: 600;
}

.stat-change.positive { color: #059669; }
.stat-change.negative { color: #dc2626; }
.stat-change.neutral { color: #6b7280; }
</style>
```

#### Dashboard Data Tables
```html
<!-- Enhanced data table -->
<div class="table-widget card">
    <div class="table-header">
        <h3>Users</h3>
        <div class="table-actions">
            <button class="btn-secondary" 
                    hx-get="/api/dashboard/export/users" 
                    hx-trigger="click">
                Export
            </button>
            <button class="btn-primary" 
                    hx-get="/api/dashboard/users/new" 
                    hx-target="#modal-container">
                Add User
            </button>
        </div>
    </div>
    
    <div class="table-filters">
        <div class="filter-group">
            <input type="search" 
                   placeholder="Search users..." 
                   class="search-input"
                   hx-get="/api/dashboard/table/users" 
                   hx-trigger="keyup changed delay:300ms" 
                   hx-target="#users-table-body">
        </div>
        
        <div class="filter-group">
            <select class="filter-select" 
                    hx-get="/api/dashboard/table/users" 
                    hx-trigger="change" 
                    hx-target="#users-table-body">
                <option value="">All Status</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
            </select>
        </div>
    </div>
    
    <div class="table-container">
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th>
                        <input type="checkbox" class="select-all">
                    </th>
                    <th class="sortable" data-sort="name">
                        Name
                        <span class="sort-indicator">↕</span>
                    </th>
                    <th class="sortable" data-sort="email">
                        Email
                        <span class="sort-indicator">↕</span>
                    </th>
                    <th class="sortable" data-sort="created_at">
                        Created
                        <span class="sort-indicator">↕</span>
                    </th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="users-table-body">
                {% for user in users %}
                <tr data-row-id="{{ user.id }}">
                    <td>
                        <input type="checkbox" 
                               name="selected_users" 
                               value="{{ user.id }}">
                    </td>
                    <td>
                        <div class="user-info">
                            <div class="user-avatar">
                                {{ user.name[0].upper() }}
                            </div>
                            <div>
                                <div class="user-name">{{ user.name }}</div>
                                <div class="user-role">{{ user.role }}</div>
                            </div>
                        </div>
                    </td>
                    <td>{{ user.email }}</td>
                    <td>{{ user.created_at.strftime('%Y-%m-%d') }}</td>
                    <td>
                        <span class="status-badge {{ 'active' if user.is_active else 'inactive' }}">
                            {{ 'Active' if user.is_active else 'Inactive' }}
                        </span>
                    </td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn-icon" 
                                    hx-get="/api/dashboard/users/{{ user.id }}/edit"
                                    hx-target="#modal-container"
                                    title="Edit">
                                ✏️
                            </button>
                            <button class="btn-icon danger" 
                                    hx-delete="/api/dashboard/users/{{ user.id }}"
                                    hx-confirm="Delete this user?"
                                    hx-target="closest tr"
                                    hx-swap="outerHTML"
                                    title="Delete">
                                🗑️
                            </button>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <!-- Pagination -->
    <div class="table-pagination">
        <div class="pagination-info">
            Showing {{ pagination.start }} to {{ pagination.end }} of {{ pagination.total }} entries
        </div>
        
        <nav class="pagination">
            {% if pagination.has_prev %}
            <a href="#" class="page-link" 
               hx-get="/api/dashboard/table/users?page={{ pagination.prev_num }}"
               hx-target="#users-table-body">
                Previous
            </a>
            {% endif %}
            
            {% for page in pagination.iter_pages() %}
                {% if page %}
                    <a href="#" class="page-link {{ 'active' if page == pagination.page else '' }}"
                       hx-get="/api/dashboard/table/users?page={{ page }}"
                       hx-target="#users-table-body">
                        {{ page }}
                    </a>
                {% endif %}
            {% endfor %}
            
            {% if pagination.has_next %}
            <a href="#" class="page-link"
               hx-get="/api/dashboard/table/users?page={{ pagination.next_num }}"
               hx-target="#users-table-body">
                Next
            </a>
            {% endif %}
        </nav>
    </div>
</div>

<style>
.table-widget {
    background: white;
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: var(--dashboard-card-shadow);
}

.table-header {
    display: flex;
    justify-content: between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--dashboard-border-color);
}

.table-actions {
    display: flex;
    gap: 0.5rem;
}

.table-filters {
    display: flex;
    gap: 1rem;
    padding: 1rem 1.5rem;
    background: #f9fafb;
    border-bottom: 1px solid var(--dashboard-border-color);
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.search-input, .filter-select {
    padding: 0.5rem 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    font-size: 0.875rem;
}

.dashboard-table {
    width: 100%;
    border-collapse: collapse;
}

.dashboard-table th {
    background: #f9fafb;
    padding: 0.75rem 1rem;
    text-align: left;
    font-weight: 600;
    color: #374151;
    border-bottom: 1px solid var(--dashboard-border-color);
}

.dashboard-table td {
    padding: 1rem;
    border-bottom: 1px solid #f3f4f6;
}

.sortable {
    cursor: pointer;
    user-select: none;
}

.sortable:hover {
    background: #f3f4f6;
}

.sort-indicator {
    margin-left: 0.5rem;
    color: #9ca3af;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.user-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--primary-color);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
}

.user-name {
    font-weight: 500;
}

.user-role {
    font-size: 0.75rem;
    color: #6b7280;
}

.status-badge {
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
}

.status-badge.active {
    background: #d1fae5;
    color: #065f46;
}

.status-badge.inactive {
    background: #fee2e2;
    color: #991b1b;
}

.action-buttons {
    display: flex;
    gap: 0.5rem;
}

.btn-icon {
    padding: 0.5rem;
    border: none;
    background: #f3f4f6;
    border-radius: 0.375rem;
    cursor: pointer;
    transition: background 0.2s;
}

.btn-icon:hover {
    background: #e5e7eb;
}

.btn-icon.danger:hover {
    background: #fee2e2;
}

.table-pagination {
    display: flex;
    justify-content: between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-top: 1px solid var(--dashboard-border-color);
}

.pagination {
    display: flex;
    gap: 0.25rem;
}

.page-link {
    padding: 0.5rem 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    text-decoration: none;
    color: #374151;
    transition: all 0.2s;
}

.page-link:hover {
    background: #f3f4f6;
}

.page-link.active {
    background: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
}
</style>
```

#### Dashboard Forms and Modals
```html
<!-- Dashboard modal -->
<div class="modal-overlay">
    <div class="modal dashboard-modal">
        <div class="modal-header">
            <h3>Add New User</h3>
            <button class="modal-close" 
                    onclick="document.getElementById('modal-container').innerHTML = ''">
                ×
            </button>
        </div>
        
        <form class="dashboard-form" 
              hx-post="/api/dashboard/users" 
              hx-target="#users-table-body" 
              hx-swap="afterbegin">
            
            <div class="form-grid">
                <div class="form-group">
                    <label for="first_name">First Name</label>
                    <input type="text" 
                           id="first_name" 
                           name="first_name" 
                           required
                           class="form-control">
                </div>
                
                <div class="form-group">
                    <label for="last_name">Last Name</label>
                    <input type="text" 
                           id="last_name" 
                           name="last_name" 
                           required
                           class="form-control">
                </div>
            </div>
            
            <div class="form-group">
                <label for="email">Email Address</label>
                <input type="email" 
                       id="email" 
                       name="email" 
                       required
                       class="form-control"
                       hx-get="/api/dashboard/validate/email"
                       hx-trigger="blur"
                       hx-target="#email-validation">
                <div id="email-validation" class="field-validation"></div>
            </div>
            
            <div class="form-group">
                <label for="role">Role</label>
                <select id="role" name="role" class="form-control" required>
                    <option value="">Select a role</option>
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="moderator">Moderator</option>
                </select>
            </div>
            
            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" name="is_active" checked>
                    <span class="checkmark"></span>
                    Active User
                </label>
            </div>
            
            <div class="form-actions">
                <button type="submit" class="btn-primary">
                    Create User
                </button>
                <button type="button" 
                        class="btn-secondary" 
                        onclick="document.getElementById('modal-container').innerHTML = ''">
                    Cancel
                </button>
            </div>
        </form>
    </div>
</div>

<style>
.dashboard-modal {
    max-width: 600px;
    width: 90%;
}

.modal-header {
    display: flex;
    justify-content: between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--dashboard-border-color);
}

.modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #6b7280;
    padding: 0.25rem;
}

.dashboard-form {
    padding: 1.5rem;
}

.form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.form-group {
    margin-bottom: 1.5rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #374151;
}

.form-control {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    font-size: 0.875rem;
    transition: border-color 0.2s;
}

.form-control:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
}

.field-validation {
    margin-top: 0.25rem;
    font-size: 0.75rem;
}

.field-validation.error {
    color: #dc2626;
}

.field-validation.success {
    color: #059669;
}

.form-actions {
    display: flex;
    gap: 0.75rem;
    padding-top: 1rem;
    border-top: 1px solid var(--dashboard-border-color);
}
</style>
```

#### Dashboard Charts and Visualizations Container
```html
<!-- Chart widgets container -->
<div class="charts-grid">
    <div class="chart-widget card">
        <div class="chart-header">
            <h4>Revenue Trend</h4>
            <div class="chart-controls">
                <select class="chart-timeframe" 
                        hx-get="/api/dashboard/chart/revenue" 
                        hx-trigger="change" 
                        hx-target="#revenue-chart">
                    <option value="7d">Last 7 days</option>
                    <option value="30d">Last 30 days</option>
                    <option value="90d">Last 90 days</option>
                </select>
            </div>
        </div>
        <div id="revenue-chart" class="chart-container"
             hx-get="/api/dashboard/chart/revenue?timeframe=7d" 
             hx-trigger="load">
            <div class="chart-loading">Loading chart...</div>
        </div>
    </div>
    
    <div class="chart-widget card">
        <div class="chart-header">
            <h4>User Growth</h4>
        </div>
        <div id="user-growth-chart" class="chart-container"
             hx-get="/api/dashboard/chart/user-growth" 
             hx-trigger="load">
            <div class="chart-loading">Loading chart...</div>
        </div>
    </div>
</div>

<style>
.charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.chart-widget {
    background: white;
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: var(--dashboard-card-shadow);
}

.chart-header {
    display: flex;
    justify-content: between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--dashboard-border-color);
}

.chart-header h4 {
    margin: 0;
    color: #1f2937;
}

.chart-controls select {
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    font-size: 0.875rem;
}

.chart-container {
    padding: 1.5rem;
    min-height: 300px;
    position: relative;
}

.chart-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 300px;
    color: #6b7280;
}
</style>
```

### Installation
```html
<!-- CDN -->
<link rel="stylesheet" href="https://unpkg.com/missing.css@1.1.3">

<!-- With Prism theme for code highlighting -->
<link rel="stylesheet" href="https://unpkg.com/missing.css@1.1.3/prism">

<!-- NPM -->
<!-- npm install missing.css -->
```

### Default Styling
```html
<!-- Typography automatically styled -->
<h1>Main Heading</h1>
<h2>Section Heading</h2>
<p>Paragraphs get proper spacing and typography.</p>
<blockquote>Blockquotes are styled beautifully</blockquote>

<!-- Lists -->
<ul>
  <li>Unordered list item</li>
  <li>Another item</li>
</ul>

<ol>
  <li>Ordered list item</li>
  <li>Sequential item</li>
</ol>

<!-- Tables -->
<table>
  <thead>
    <tr>
      <th>Header 1</th>
      <th>Header 2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Cell 1</td>
      <td>Cell 2</td>
    </tr>
  </tbody>
</table>
```

### Forms
```html
<!-- Forms are automatically styled -->
<form>
  <label for="name">Name</label>
  <input type="text" id="name" name="name" required>
  
  <label for="email">Email</label>
  <input type="email" id="email" name="email">
  
  <label for="message">Message</label>
  <textarea id="message" name="message" rows="4"></textarea>
  
  <label>
    <input type="checkbox" name="subscribe">
    Subscribe to newsletter
  </label>
  
  <button type="submit">Submit</button>
  <button type="reset">Reset</button>
</form>

<!-- Form validation states -->
<input type="email" required aria-invalid="true"> <!-- Error state -->
<input type="text" aria-invalid="false"> <!-- Valid state -->
```

### Components and Utility Classes

#### Layout Utilities
```html
<!-- Container -->
<div class="container">
  <p>Centered content with max-width</p>
</div>

<!-- Grid system -->
<div class="grid">
  <div>Grid item 1</div>
  <div>Grid item 2</div>
  <div>Grid item 3</div>
</div>

<!-- Flexbox utilities -->
<div class="flex">
  <div>Flex item 1</div>
  <div>Flex item 2</div>
</div>

<div class="flex justify-between">
  <div>Left</div>
  <div>Right</div>
</div>
```

#### Navigation
```html
<!-- Navbar -->
<nav class="navbar">
  <a href="/" class="brand">Brand</a>
  <ul>
    <li><a href="/home">Home</a></li>
    <li><a href="/about">About</a></li>
    <li><a href="/contact">Contact</a></li>
  </ul>
</nav>

<!-- Breadcrumbs -->
<nav class="breadcrumb">
  <a href="/">Home</a>
  <a href="/category">Category</a>
  <span>Current Page</span>
</nav>
```

#### Cards and Panels
```html
<!-- Card component -->
<div class="card">
  <h3>Card Title</h3>
  <p>Card content goes here.</p>
  <div class="card-actions">
    <button>Action 1</button>
    <button>Action 2</button>
  </div>
</div>

<!-- Alert/notification -->
<div class="alert">
  <strong>Info:</strong> This is an informational message.
</div>

<div class="alert alert-warning">
  <strong>Warning:</strong> This needs attention.
</div>

<div class="alert alert-error">
  <strong>Error:</strong> Something went wrong.
</div>
```

#### Buttons
```html
<!-- Button variants -->
<button>Default Button</button>
<button class="primary">Primary Button</button>
<button class="secondary">Secondary Button</button>
<button class="danger">Danger Button</button>

<!-- Button sizes -->
<button class="small">Small</button>
<button>Default</button>
<button class="large">Large</button>

<!-- Button states -->
<button disabled>Disabled</button>
<button class="loading">Loading...</button>
```

#### Tables
```html
<!-- Enhanced table -->
<table class="striped">
  <thead>
    <tr>
      <th>Name</th>
      <th>Email</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>John Doe</td>
      <td>john@example.com</td>
      <td>
        <button class="small">Edit</button>
        <button class="small danger">Delete</button>
      </td>
    </tr>
  </tbody>
</table>
```

### Customization with CSS Variables
```css
:root {
  /* Colors */
  --primary-color: #007bff;
  --secondary-color: #6c757d;
  --success-color: #28a745;
  --warning-color: #ffc107;
  --danger-color: #dc3545;
  
  /* Typography */
  --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-size-base: 1rem;
  --line-height-base: 1.5;
  
  /* Spacing */
  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 3rem;
  
  /* Layout */
  --container-max-width: 1200px;
  --border-radius: 0.375rem;
  --border-width: 1px;
}

/* Custom theme example */
.dark-theme {
  --bg-color: #1a1a1a;
  --text-color: #ffffff;
  --border-color: #333333;
}
```

### Responsive Design
```html
<!-- missing.css includes responsive utilities -->
<div class="hidden-mobile">Hidden on mobile</div>
<div class="hidden-tablet">Hidden on tablet</div>
<div class="hidden-desktop">Hidden on desktop</div>

<!-- Responsive text alignment -->
<div class="text-center-mobile text-left-desktop">
  Responsive text alignment
</div>

<!-- Responsive spacing -->
<div class="margin-sm-mobile margin-lg-desktop">
  Responsive margins
</div>
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
        return f'<div class="alert error">Error: {str(e)}</div>', 400

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
    <link rel="stylesheet" href="https://unpkg.com/missing.css@1.1.3">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <style>
        /* Dashboard-specific styles */
        :root {
            --dashboard-sidebar-width: 280px;
            --dashboard-header-height: 64px;
            --dashboard-primary: #3b82f6;
            --dashboard-success: #10b981;
            --dashboard-warning: #f59e0b;
            --dashboard-danger: #ef4444;
        }
        
        .dashboard-layout {
            display: flex;
            min-height: 100vh;
        }
        
        .dashboard-sidebar {
            width: var(--dashboard-sidebar-width);
            background: white;
            border-right: 1px solid #e5e7eb;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }
        
        .dashboard-main {
            margin-left: var(--dashboard-sidebar-width);
            flex: 1;
            background: #f9fafb;
        }
        
        .dashboard-header {
            background: white;
            padding: 1rem 2rem;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: center;
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
        }
    </style>
</head>
<body class="dashboard-layout">
    <!-- Sidebar -->
    <aside class="dashboard-sidebar" 
           _="on mobile-menu-toggle 
              toggle .mobile-open on me">
        <div class="sidebar-content">
            <div class="sidebar-header">
                <h2>Dashboard</h2>
            </div>
            
            <nav class="sidebar-nav">
                <div class="nav-group">
                    <h4>Main</h4>
                    <a href="/dashboard" class="nav-item {{ 'active' if request.endpoint == 'dashboard' }}">
                        <span class="nav-icon">📊</span>
                        Overview
                    </a>
                    <a href="/dashboard/analytics" class="nav-item">
                        <span class="nav-icon">📈</span>
                        Analytics
                    </a>
                </div>
                
                <div class="nav-group">
                    <h4>Management</h4>
                    <a href="/dashboard/users" class="nav-item">
                        <span class="nav-icon">👥</span>
                        Users
                    </a>
                    <a href="/dashboard/orders" class="nav-item">
                        <span class="nav-icon">🛒</span>
                        Orders
                    </a>
                    <a href="/dashboard/reports" class="nav-item">
                        <span class="nav-icon">📋</span>
                        Reports
                    </a>
                </div>
                
                <div class="nav-group">
                    <h4>Settings</h4>
                    <a href="/dashboard/settings" class="nav-item">
                        <span class="nav-icon">⚙️</span>
                        Settings
                    </a>
                </div>
            </nav>
        </div>
    </aside>
    
    <!-- Main Content -->
    <main class="dashboard-main">
        <!-- Header -->
        <header class="dashboard-header">
            <div class="header-left">
                <button class="mobile-menu-btn" 
                        _="on click send mobile-menu-toggle to .dashboard-sidebar"
                        style="display: none;">
                    ☰
                </button>
                <h1>{% block page_title %}Dashboard{% endblock %}</h1>
            </div>
            
            <div class="header-right">
                <!-- Notifications -->
                <div class="notifications" 
                     _="on show-notification(message, type, duration)
                        make a <div.notification/> called notif
                        add .{type} to notif
                        put message into notif
                        put notif at the end of #notification-container
                        if duration > 0
                          wait {duration}ms
                          remove notif
                        end">
                    <button class="notification-btn">🔔</button>
                </div>
                
                <!-- User Menu -->
                <div class="user-menu dropdown">
                    <button class="user-avatar">
                        {{ current_user.username[0].upper() }}
                    </button>
                    <div class="dropdown-content">
                        <a href="/profile">Profile</a>
                        <a href="/settings">Settings</a>
                        <hr>
                        <a href="/logout">Logout</a>
                    </div>
                </div>
            </div>
        </header>
        
        <!-- Page Content -->
        <div class="dashboard-content">
            {% block content %}{% endblock %}
        </div>
    </main>
    
    <!-- Notification Container -->
    <div id="notification-container" class="notification-container"></div>
    
    <!-- Modal Container -->
    <div id="modal-container"></div>
    
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
          send show-notification(
            message: 'An error occurred. Please try again.', 
            type: 'error', 
            duration: 5000
          ) to .notifications
        end
        
        -- Success handler
        on htmx:afterRequest from body
          if detail.xhr.status >= 200 and detail.xhr.status < 300
            if detail.target.dataset.successMessage
              send show-notification(
                message: detail.target.dataset.successMessage, 
                type: 'success', 
                duration: 3000
              ) to .notifications
            end
          end
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
    <div class="loading">Loading dashboard stats...</div>
</div>

<!-- Charts Section -->
<div class="dashboard-section">
    <h2>Analytics</h2>
    <div class="charts-grid">
        <!-- User Growth Chart -->
        <div class="chart-widget card">
            <div class="chart-header">
                <h3>User Growth</h3>
                <select class="chart-timeframe" 
                        hx-get="/api/dashboard/chart/users-growth" 
                        hx-trigger="change" 
                        hx-target="#users-growth-chart">
                    <option value="7">Last 7 days</option>
                    <option value="30" selected>Last 30 days</option>
                    <option value="90">Last 90 days</option>
                </select>
            </div>
            <div id="users-growth-chart" 
                 hx-get="/api/dashboard/chart/users-growth?days=30" 
                 hx-trigger="load"
                 class="chart-container">
                Loading chart...
            </div>
        </div>
        
        <!-- Revenue Chart -->
        <div class="chart-widget card">
            <div class="chart-header">
                <h3>Revenue</h3>
            </div>
            <div id="revenue-chart" 
                 hx-get="/api/dashboard/chart/revenue" 
                 hx-trigger="load"
                 class="chart-container">
                Loading chart...
            </div>
        </div>
    </div>
</div>

<!-- Recent Activity -->
<div class="dashboard-section">
    <h2>Recent Activity</h2>
    <div class="activity-widget card">
        <div id="activity-feed" 
             hx-get="/api/dashboard/activity" 
             hx-trigger="load, every 60s">
            Loading activity...
        </div>
    </div>
</div>

<!-- Quick Actions -->
<div class="dashboard-section">
    <h2>Quick Actions</h2>
    <div class="quick-actions">
        <button class="action-card" 
                hx-get="/api/dashboard/users/new" 
                hx-target="#modal-container">
            <div class="action-icon">👤</div>
            <div class="action-text">Add User</div>
        </button>
        
        <button class="action-card" 
                hx-get="/api/dashboard/reports/generate" 
                hx-target="#modal-container">
            <div class="action-icon">📊</div>
            <div class="action-text">Generate Report</div>
        </button>
        
        <button class="action-card" 
                hx-get="/api/dashboard/settings/backup" 
                hx-target="#modal-container">
            <div class="action-icon">💾</div>
            <div class="action-text">Backup Data</div>
        </button>
    </div>
</div>

<style>
.dashboard-section {
    margin-bottom: 3rem;
}

.dashboard-section h2 {
    margin-bottom: 1.5rem;
    color: #1f2937;
}

.charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 1.5rem;
}

.chart-widget {
    background: white;
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
}

.chart-container {
    padding: 1.5rem;
    min-height: 300px;
}

.activity-widget {
    background: white;
    border-radius: 0.75rem;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.quick-actions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
}

.action-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
}

.action-card:hover {
    border-color: var(--dashboard-primary);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.action-icon {
    font-size: 2.5rem;
    margin-bottom: 1rem;
}

.action-text {
    font-weight: 500;
    color: #374151;
}
</style>
{% endblock %}
```

### HTMX + _hyperscript Integration for Dashboards
---

## Real-time Dashboard Updates

### WebSocket Integration with HTMX

Flask applications can use WebSockets for real-time dashboard updates. Here's how to integrate WebSocket connections with HTMX:

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

#### Real-time Dashboard Template
```html
<!-- Real-time Dashboard with WebSocket -->
<div class="realtime-dashboard" 
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
          put 'Connected (' + data.clients + ' clients)' into #connection-status
        end)
        
        -- Cleanup on page unload
        on beforeunload
          call :socket.disconnect()
        end
        
        -- Functions for updating UI
        def update-dashboard-stats(data)
          put data.active_users into #active-users-count
          put (data.system_load * 100).toFixed(1) + '%' into #system-load
          set #load-bar.style.width to (data.system_load * 100) + '%'
          
          -- Animate changes
          add .updated to #stats-container
          wait 300ms
          remove .updated from #stats-container
        end
        
        def update-activity-feed(activities)
          set feed to #activity-feed
          for activity in activities
            make a <div.activity-item/> called item
            set item.innerHTML to activity.html
            put item at the start of feed
          end
          
          -- Keep only latest 20 items
          set items to <.activity-item/> in feed
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
    <div class="dashboard-header">
        <h1>Real-time Dashboard</h1>
        <div class="connection-indicator">
            <span class="status-dot"></span>
            <span id="connection-status">Connecting...</span>
        </div>
    </div>
    
    <!-- Live Statistics -->
    <div id="stats-container" class="stats-grid">
        <div class="stat-card realtime">
            <div class="stat-icon">👥</div>
            <div class="stat-content">
                <div id="active-users-count" class="stat-value">--</div>
                <div class="stat-label">Active Users</div>
            </div>
        </div>
        
        <div class="stat-card realtime">
            <div class="stat-icon">⚡</div>
            <div class="stat-content">
                <div id="system-load" class="stat-value">--</div>
                <div class="stat-label">System Load</div>
                <div class="load-bar-container">
                    <div id="load-bar" class="load-bar"></div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Real-time Activity Feed -->
    <div class="activity-widget card">
        <h3>Live Activity</h3>
        <div id="activity-feed" class="activity-feed">
            <!-- Activities are inserted here dynamically -->
        </div>
    </div>
    
    <!-- Performance Chart -->
    <div class="chart-widget card">
        <h3>Performance Metrics</h3>
        <canvas id="performance-chart" width="400" height="200"></canvas>
    </div>
</div>

<!-- Chart.js for real-time charts -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.js"></script>

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
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.4,
            yAxisID: 'y'
        }, {
            label: 'Throughput (req/s)',
            data: [],
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
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
    padding: 2rem;
}

.dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
}

.connection-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: #6b7280;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.stat-card.realtime {
    transition: all 0.3s ease;
}

.stats-grid.updated .stat-card.realtime {
    transform: scale(1.02);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.load-bar-container {
    width: 100%;
    height: 4px;
    background: #e5e7eb;
    border-radius: 2px;
    margin-top: 0.5rem;
    overflow: hidden;
}

.load-bar {
    height: 100%;
    background: linear-gradient(90deg, #10b981, #f59e0b, #ef4444);
    border-radius: 2px;
    transition: width 0.5s ease;
    width: 0%;
}

.activity-feed {
    max-height: 300px;
    overflow-y: auto;
}

.activity-item {
    padding: 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    animation: slideIn 0.3s ease;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.chart-widget {
    margin-top: 2rem;
}

.chart-widget canvas {
    max-height: 300px;
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

#### SSE Dashboard Template
```html
<div class="sse-dashboard" 
     hx-ext="sse" 
     sse-connect="/stream/dashboard"
     _="on sse:dashboard_update(data) 
        set metrics to JSON.parse(data)
        put metrics.active_users into #active-users
        put metrics.system_load + '%' into #system-load
        update-activity-feed(metrics.activities)">
    
    <div class="metrics">
        <span id="active-users">--</span>
        <span id="system-load">--</span>
    </div>
    
    <div id="activity-list"></div>
</div>
```

---

## Data Visualization Integration

### Chart.js Integration with HTMX

Combine Chart.js with HTMX for dynamic, data-driven dashboards:

#### Dynamic Chart Updates
```html
<!-- Chart Container with Data Controls -->
<div class="chart-container card">
    <div class="chart-header">
        <h3>Sales Analytics</h3>
        <div class="chart-controls">
            <select name="period" 
                    hx-get="/api/dashboard/chart-data" 
                    hx-trigger="change" 
                    hx-target="#chart-data" 
                    hx-swap="none"
                    _="on htmx:afterRequest(evt) 
                       set data to JSON.parse(evt.detail.xhr.response)
                       update-chart(data)">
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="3m">Last 3 Months</option>
                <option value="1y">Last Year</option>
            </select>
            
            <button class="btn-secondary" 
                    hx-get="/api/dashboard/export-chart" 
                    hx-trigger="click"
                    _="on click 
                       set canvas to #sales-chart
                       set link to document.createElement('a')
                       set link.download to 'sales-chart.png'
                       set link.href to canvas.toDataURL()
                       link.click()">
                Export
            </button>
        </div>
    </div>
    
    <div class="chart-wrapper">
        <canvas id="sales-chart" width="800" height="400"></canvas>
    </div>
    
    <!-- Hidden container for chart data -->
    <div id="chart-data" style="display: none;"></div>
</div>

<script>
// Initialize chart
const salesCtx = document.getElementById('sales-chart').getContext('2d');
let salesChart = new Chart(salesCtx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Sales',
            data: [],
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.4,
            fill: true
        }, {
            label: 'Target',
            data: [],
            borderColor: '#10b981',
            borderDash: [5, 5],
            backgroundColor: 'transparent',
            tension: 0.4
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
                text: 'Sales Performance'
            },
            legend: {
                position: 'top',
            },
            tooltip: {
                mode: 'index',
                intersect: false,
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
                    text: 'Date'
                }
            },
            y: {
                display: true,
                title: {
                    display: true,
                    text: 'Revenue ($)'
                },
                ticks: {
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

.chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
}

.chart-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.chart-wrapper {
    padding: 1.5rem;
    height: 400px;
    position: relative;
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
    # ... handle other periods
    
    return jsonify({
        'labels': labels,
        'sales': sales,
        'targets': targets
    })
```

### Multi-Chart Dashboard
```html
<!-- Dashboard with Multiple Charts -->
<div class="multi-chart-dashboard">
    <div class="dashboard-grid">
        <!-- Revenue Chart -->
        <div class="chart-widget card">
            <div class="widget-header">
                <h3>Revenue Trends</h3>
                <div class="chart-type-selector" 
                     _="on change
                        set chartType to me.value
                        set chart to window.revenueChart
                        call chart.destroy()
                        initialize-revenue-chart(chartType)">
                    <label>
                        <input type="radio" name="revenue-type" value="line" checked>
                        Line
                    </label>
                    <label>
                        <input type="radio" name="revenue-type" value="bar">
                        Bar
                    </label>
                    <label>
                        <input type="radio" name="revenue-type" value="area">
                        Area
                    </label>
                </div>
            </div>
            <canvas id="revenue-chart"></canvas>
        </div>
        
        <!-- User Growth Chart -->
        <div class="chart-widget card">
            <div class="widget-header">
                <h3>User Growth</h3>
                <button class="refresh-btn" 
                        hx-get="/api/dashboard/user-growth" 
                        hx-trigger="click"
                        hx-swap="none"
                        _="on htmx:afterRequest(evt)
                           set data to JSON.parse(evt.detail.xhr.response)
                           update-user-growth-chart(data)">
                    🔄
                </button>
            </div>
            <canvas id="user-growth-chart"></canvas>
        </div>
        
        <!-- Performance Metrics -->
        <div class="chart-widget card">
            <div class="widget-header">
                <h3>System Performance</h3>
            </div>
            <canvas id="performance-metrics-chart"></canvas>
        </div>
        
        <!-- Geographic Distribution -->
        <div class="chart-widget card">
            <div class="widget-header">
                <h3>Geographic Distribution</h3>
            </div>
            <canvas id="geographic-chart"></canvas>
        </div>
    </div>
</div>

<script>
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
                borderColor: '#3b82f6',
                backgroundColor: type === 'area' ? 'rgba(59, 130, 246, 0.2)' : '#3b82f6',
                fill: type === 'area'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    };
    
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
                backgroundColor: ['#10b981', '#3b82f6', '#f59e0b'],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
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
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                borderWidth: 2
            }, {
                label: 'Target',
                data: [90, 95, 85, 90, 88],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                borderDash: [5, 5]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100
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
                    '#3b82f6',
                    '#10b981',
                    '#f59e0b',
                    '#ef4444',
                    '#8b5cf6',
                    '#06b6d4'
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right'
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
    padding: 2rem;
}

.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 2rem;
}

.chart-widget {
    min-height: 350px;
}

.widget-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #e5e7eb;
}

.widget-header h3 {
    margin: 0;
    color: #1f2937;
}

.chart-type-selector {
    display: flex;
    gap: 1rem;
}

.chart-type-selector label {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.875rem;
    cursor: pointer;
}

.refresh-btn {
    background: #f3f4f6;
    border: none;
    border-radius: 0.375rem;
    padding: 0.5rem;
    cursor: pointer;
    transition: background 0.2s;
}

.refresh-btn:hover {
    background: #e5e7eb;
}

.chart-widget canvas {
    padding: 1.5rem;
    height: 280px !important;
}
</style>
```

---

## Best Practices for Flask Dashboard Development

### Performance Optimization

#### 1. Efficient HTMX Patterns
```html
<!-- Good: Targeted updates -->
<div hx-get="/api/stats" 
     hx-trigger="every 30s" 
     hx-target="#stats-container" 
     hx-swap="innerHTML">
    <!-- Stats content -->
</div>

<!-- Better: Conditional updates -->
<div hx-get="/api/stats" 
     hx-trigger="every 30s" 
     hx-target="#stats-container" 
     hx-swap="innerHTML"
     hx-headers='{"If-Modified-Since": "{{ last_modified }}"}'
     _="on htmx:responseError(evt)
        if evt.detail.xhr.status is 304
          -- No changes, skip update
          halt the event
        end">
    <!-- Stats content -->
</div>

<!-- Best: Smart caching with conditional rendering -->
<div id="stats-widget" 
     hx-get="/api/stats" 
     hx-trigger="load, every 30s" 
     hx-target="this" 
     hx-swap="innerHTML"
     _="init 
        set :lastHash to ''
        
        on htmx:beforeRequest
          set :requestTime to Date.now()
        end
        
        on htmx:afterRequest(evt)
          set response to evt.detail.xhr.response
          set newHash to btoa(response).substring(0, 10)
          
          if newHash is :lastHash
            -- No visual changes needed
            halt the event
          else
            set :lastHash to newHash
          end
        end">
    <!-- Initial content -->
</div>
```

#### 2. _hyperscript Memory Management
```html
<!-- Good: Clean up event listeners -->
<div class="dashboard-widget" 
     _="init
        set :interval to setInterval(def() updateWidget() end, 5000)
        
        on beforeunload
          clearInterval(:interval)
        end
        
        def updateWidget()
          -- Update logic here
        end">
</div>

<!-- Better: Use built-in cleanup -->
<div class="dashboard-widget" 
     _="init
        repeat every 5s
          updateWidget()
        until event(beforeunload) from window
        
        def updateWidget()
          -- Update logic here
        end">
</div>
```

#### 3. Optimized Flask Routes
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
```

### Security Best Practices

#### 1. CSRF Protection with HTMX
```python
from flask_wtf.csrf import CSRFProtect, generate_csrf

csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)
```

```html
<!-- Include CSRF token in HTMX requests -->
<div hx-headers='{"X-CSRFToken": "{{ csrf_token() }}"}'>
    <form hx-post="/api/dashboard/users">
        <!-- Form content -->
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

#### 2. Input Validation and Sanitization
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
        return jsonify({'errors': form.errors}), 400
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
```

### Error Handling and User Experience

#### 1. Graceful Error Handling
```html
<!-- Error handling with user feedback -->
<div class="dashboard-content" 
     _="on htmx:responseError(evt)
        set status to evt.detail.xhr.status
        if status is 403
          show-error-message('Access denied. Please check your permissions.')
        else if status is 500
          show-error-message('Server error. Please try again later.')
        else if status is 429
          show-error-message('Too many requests. Please wait before trying again.')
        else
          show-error-message('An error occurred. Please refresh the page.')
        end
        
        def show-error-message(message)
          make a <div.alert.alert-error/> called alert
          put message into alert
          put alert at the start of body
          wait 5s
          remove alert
        end
        
        on htmx:timeout
          show-error-message('Request timed out. Please check your connection.')
        end">
    
    <!-- Dashboard content -->
</div>
```

#### 2. Loading States and Feedback
```html
<!-- Advanced loading indicators -->
<div class="data-table-container" 
     _="on htmx:beforeRequest
        add .loading to me
        make a <div.loading-overlay/> called overlay
        put '<div class=loading-spinner></div><p>Loading data...</p>' into overlay
        put overlay into me
        
        on htmx:afterRequest
          remove .loading from me
          remove .loading-overlay from me
        end
        
        on htmx:timeout
          remove .loading from me
          remove .loading-overlay from me
          add .error to me
        end">
    
    <!-- Table content -->
</div>

<style>
.loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.9);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 10;
}

.loading-spinner {
    width: 40px;
    height: 40px;
    border: 4px solid #e5e7eb;
    border-top: 4px solid #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
```

### Testing Dashboard Components

#### 1. Unit Testing HTMX Endpoints
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
```

#### 2. Frontend Testing with Playwright
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
    """Test real-time dashboard updates"""
    page.goto("http://localhost:5000/dashboard")
    
    # Wait for initial load
    page.wait_for_selector("#stats-container")
    
    # Check initial user count
    initial_count = page.text_content("#active-users-count")
    
    # Trigger update (simulate user login in another tab)
    page.evaluate("fetch('/api/simulate-user-login', {method: 'POST'})")
    
    # Wait for update
    page.wait_for_function(
        f"document.querySelector('#active-users-count').textContent !== '{initial_count}'"
    )
    
    # Verify count increased
    new_count = page.text_content("#active-users-count")
    assert int(new_count) > int(initial_count)

def test_dashboard_interactivity(page):
    """Test dashboard interactive features"""
    page.goto("http://localhost:5000/dashboard")
    
    # Test filter functionality
    page.fill("input[name='search']", "test user")
    page.wait_for_selector(".user-row:has-text('test user')")
    
    # Test bulk selection
    page.check("input[name='selected_users']")
    page.wait_for_selector("#bulk-actions", state="visible")
    
    # Test modal opening
    page.click("button:has-text('Add User')")
    page.wait_for_selector("#modal-container .modal", state="visible")
```

This comprehensive guide provides everything needed to build modern, interactive Flask dashboards using HTMX, _hyperscript, and missing.css. The combination of these technologies creates powerful, maintainable web applications with minimal JavaScript while providing excellent user experience and developer productivity.

**Users Table Component (dashboard/components/users_table.html):**
```html
<div class="table-container">
    <div class="table-header">
        <div class="table-title">
            <h3>Users ({{ pagination.total }})</h3>
        </div>
        
        <div class="table-actions">
            <!-- Bulk Actions -->
            <div id="bulk-actions" style="display: none;" 
                 _="on selection-changed(selected)
                    if selected.length > 0
                      show me
                      put selected.length + ' selected' into #selected-count
                    else
                      hide me
                    end">
                <span id="selected-count">0 selected</span>
                <button class="btn-secondary" 
                        hx-post="/api/dashboard/users/bulk-activate"
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-container"
                        data-success-message="Users activated successfully">
                    Activate
                </button>
                <button class="btn-danger" 
                        hx-delete="/api/dashboard/users/bulk-delete"
                        hx-include="[name='selected_users']:checked"
                        hx-target="#users-table-container"
                        hx-confirm="Delete selected users?"
                        data-success-message="Users deleted successfully">
                    Delete
                </button>
            </div>
            
            <button class="btn-primary" 
                    hx-get="/api/dashboard/users/new" 
                    hx-target="#modal-container">
                Add User
            </button>
        </div>
    </div>
    
    <!-- Filters -->
    <div class="table-filters card">
        <form hx-get="/api/dashboard/users" 
              hx-trigger="change, submit" 
              hx-target="#users-table-container">
            
            <div class="filter-group">
                <label>Search</label>
                <input type="search" 
                       name="search" 
                       placeholder="Search users..."
                       value="{{ request.args.get('search', '') }}"
                       hx-get="/api/dashboard/users" 
                       hx-trigger="keyup changed delay:300ms" 
                       hx-target="#users-table-container"
                       hx-include="[name='status'], [name='role']">
            </div>
            
            <div class="filter-group">
                <label>Status</label>
                <select name="status">
                    <option value="">All Status</option>
                    <option value="active" {{ 'selected' if request.args.get('status') == 'active' }}>Active</option>
                    <option value="inactive" {{ 'selected' if request.args.get('status') == 'inactive' }}>Inactive</option>
                </select>
            </div>
            
            <div class="filter-group">
                <label>Role</label>
                <select name="role">
                    <option value="">All Roles</option>
                    <option value="admin">Admin</option>
                    <option value="user">User</option>
                    <option value="moderator">Moderator</option>
                </select>
            </div>
            
            <div class="filter-actions">
                <button type="submit" class="btn-secondary">Apply</button>
                <button type="button" 
                        class="btn-outline"
                        hx-get="/api/dashboard/users" 
                        hx-target="#users-table-container"
                        _="on click 
                           reset() the closest form
                           trigger change">
                    Clear
                </button>
            </div>
        </form>
    </div>
    
    <!-- Table -->
    <div class="table-widget">
        <table class="dashboard-table" 
               _="init set :selectedRows to []
                 on select-row(rowId, checked)
                   if checked
                     push rowId onto :selectedRows
                   else
                     set :selectedRows to :selectedRows.filter(id => id != rowId)
                   end
                   send selection-changed(selected: :selectedRows) to #bulk-actions
                 end
                 
                 on select-all(checked)
                   set checkboxes to <input[name='selected_users']/> in me
                   for checkbox in checkboxes
                     set checkbox.checked to checked
                     set rowId to checkbox.value
                     if checked
                       push rowId onto :selectedRows unless :selectedRows contains rowId
                     else
                       set :selectedRows to :selectedRows.filter(id => id != rowId)
                     end
                   end
                   send selection-changed(selected: :selectedRows) to #bulk-actions
                 end">
            
            <thead>
                <tr>
                    <th style="width: 40px;">
                        <input type="checkbox" 
                               class="select-all-checkbox"
                               _="on change 
                                  send select-all(checked: my checked) to my closest table">
                    </th>
                    <th>User</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th style="width: 120px;">Actions</th>
                </tr>
            </thead>
            
            <tbody>
                {% for user in pagination.items %}
                <tr id="user-row-{{ user.id }}" data-user-id="{{ user.id }}">
                    <td>
                        <input type="checkbox" 
                               name="selected_users" 
                               value="{{ user.id }}"
                               _="on change 
                                  send select-row(rowId: my value, checked: my checked) to my closest table">
                    </td>
                    <td>
                        <div class="user-info">
                            <div class="user-avatar">{{ user.username[0].upper() }}</div>
                            <div>
                                <div class="user-name">{{ user.username }}</div>
                                <div class="user-id">#{{ user.id }}</div>
                            </div>
                        </div>
                    </td>
                    <td>{{ user.email }}</td>
                    <td>
                        <span class="role-badge role-{{ user.role }}">
                            {{ user.role.title() }}
                        </span>
                    </td>
                    <td>
                        <div class="status-toggle"
                             hx-post="/api/dashboard/users/{{ user.id }}/toggle-status"
                             hx-target="this"
                             hx-swap="outerHTML"
                             _="on click add .updating to me">
                            <span class="status-badge {{ 'active' if user.is_active else 'inactive' }}">
                                {{ 'Active' if user.is_active else 'Inactive' }}
                            </span>
                        </div>
                    </td>
                    <td>
                        <time datetime="{{ user.created_at.isoformat() }}">
                            {{ user.created_at.strftime('%Y-%m-%d') }}
                        </time>
                    </td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn-icon" 
                                    hx-get="/api/dashboard/users/{{ user.id }}/edit"
                                    hx-target="#modal-container"
                                    title="Edit user">
                                ✏️
                            </button>
                            <button class="btn-icon danger" 
                                    hx-delete="/api/dashboard/users/{{ user.id }}"
                                    hx-target="#user-row-{{ user.id }}"
                                    hx-swap="outerHTML"
                                    hx-confirm="Delete {{ user.username }}?"
                                    title="Delete user"
                                    data-success-message="User deleted successfully">
                                🗑️
                            </button>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <!-- Pagination -->
        {% if pagination.pages > 1 %}
        <div class="table-pagination">
            <div class="pagination-info">
                Showing {{ pagination.per_page * (pagination.page - 1) + 1 }} to 
                {{ pagination.per_page * pagination.page if pagination.page < pagination.pages else pagination.total }} 
                of {{ pagination.total }} entries
            </div>
            
            <nav class="pagination">
                {% if pagination.has_prev %}
                <a href="#" class="page-link" 
                   hx-get="/api/dashboard/users?page={{ pagination.prev_num }}"
                   hx-target="#users-table-container">
                    Previous
                </a>
                {% endif %}
                
                {% for page in pagination.iter_pages() %}
                    {% if page %}
                        <a href="#" class="page-link {{ 'active' if page == pagination.page else '' }}"
                           hx-get="/api/dashboard/users?page={{ page }}"
                           hx-target="#users-table-container">
                            {{ page }}
                        </a>
                    {% endif %}
                {% endfor %}
                
                {% if pagination.has_next %}
                <a href="#" class="page-link"
                   hx-get="/api/dashboard/users?page={{ pagination.next_num }}"
                   hx-target="#users-table-container">
                    Next
                </a>
                {% endif %}
            </nav>
        </div>
        {% endif %}
    </div>
</div>

<style>
.table-container {
    background: white;
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
}

.table-title h3 {
    margin: 0;
    color: #1f2937;
}

.table-filters {
    padding: 1rem 1.5rem;
    background: #f9fafb;
    border-bottom: 1px solid #e5e7eb;
}

.table-filters form {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr auto;
    gap: 1rem;
    align-items: end;
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.filter-group label {
    font-size: 0.75rem;
    font-weight: 500;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

.filter-actions {
    display: flex;
    gap: 0.5rem;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--dashboard-primary);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 0.875rem;
}

.user-name {
    font-weight: 500;
    color: #1f2937;
}

.user-id {
    font-size: 0.75rem;
    color: #9ca3af;
}

.role-badge {
    padding: 0.25rem 0.5rem;
    border-radius: 0.375rem;
    font-size: 0.75rem;
    font-weight: 500;
}

.role-admin {
    background: #fef3c7;
    color: #92400e;
}

.role-user {
    background: #e0e7ff;
    color: #3730a3;
}

.role-moderator {
    background: #d1fae5;
    color: #065f46;
}

.status-toggle {
    cursor: pointer;
    transition: opacity 0.2s;
}

.status-toggle.updating {
    opacity: 0.5;
    pointer-events: none;
}

.status-badge {
    padding: 0.25rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
}

.status-badge.active {
    background: #d1fae5;
    color: #065f46;
}

.status-badge.inactive {
    background: #fee2e2;
    color: #991b1b;
}

.action-buttons {
    display: flex;
    gap: 0.25rem;
}

.btn-icon {
    padding: 0.5rem;
    border: none;
    background: #f3f4f6;
    border-radius: 0.375rem;
    cursor: pointer;
    transition: background 0.2s;
    font-size: 0.875rem;
}

.btn-icon:hover {
    background: #e5e7eb;
}

.btn-icon.danger:hover {
    background: #fee2e2;
}

.table-pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-top: 1px solid #e5e7eb;
}

.pagination-info {
    font-size: 0.875rem;
    color: #6b7280;
}

.pagination {
    display: flex;
    gap: 0.25rem;
}

.page-link {
    padding: 0.5rem 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    text-decoration: none;
    color: #374151;
    transition: all 0.2s;
    font-size: 0.875rem;
}

.page-link:hover {
    background: #f3f4f6;
    border-color: #9ca3af;
}

.page-link.active {
    background: var(--dashboard-primary);
    color: white;
    border-color: var(--dashboard-primary);
}

#bulk-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.5rem 1rem;
    background: #eff6ff;
    border: 1px solid #dbeafe;
    border-radius: 0.375rem;
    margin-right: 1rem;
}

#selected-count {
    font-size: 0.875rem;
    color: #1e40af;
    font-weight: 500;
}
</style>
```

---

## Dashboard-Specific Components

### Real-time Dashboard Widgets

#### Live Activity Feed
```html
<!-- Activity Feed Component -->
<div class="activity-feed-widget card">
    <div class="widget-header">
        <h3>Live Activity</h3>
        <div class="widget-controls">
            <button class="control-btn" 
                    _="on click
                       toggle .paused on #activity-feed
                       if #activity-feed matches .paused
                         put '▶️' into me
                         set @title to 'Resume updates'
                       else
                         put '⏸️' into me
                         set @title to 'Pause updates'
                       end">
                ⏸️
            </button>
            <button class="control-btn" 
                    hx-get="/api/dashboard/activity/clear" 
                    hx-target="#activity-list"
                    hx-confirm="Clear all activity?"
                    title="Clear activity">
                🗑️
            </button>
        </div>
    </div>
    
    <div id="activity-feed" 
         class="activity-feed"
         hx-ext="sse" 
         sse-connect="/stream/activity"
         _="on sse:activity(data) 
            unless I match .paused
              make a <div.activity-item/> called item
              set item.innerHTML to data.html
              put item at the start of #activity-list
              
              -- Limit to 50 items
              set items to <.activity-item/> in #activity-list
              if items.length > 50
                remove items[items.length - 1]
              end
              
              -- Auto-scroll if at top
              if #activity-list.scrollTop < 50
                go to the top of #activity-list smoothly
              end
            end">
        
        <div id="activity-list" class="activity-list">
            {% for activity in recent_activities %}
            <div class="activity-item">
                <div class="activity-icon">{{ activity.icon }}</div>
                <div class="activity-content">
                    <div class="activity-message">{{ activity.message }}</div>
                    <div class="activity-time">{{ activity.timestamp.strftime('%H:%M:%S') }}</div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

<style>
.activity-feed-widget {
    height: 400px;
    display: flex;
    flex-direction: column;
}

.widget-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #e5e7eb;
}

.widget-controls {
    display: flex;
    gap: 0.5rem;
}

.control-btn {
    padding: 0.25rem 0.5rem;
    border: none;
    background: #f3f4f6;
    border-radius: 0.375rem;
    cursor: pointer;
    font-size: 0.875rem;
}

.activity-feed {
    flex: 1;
    overflow: hidden;
}

.activity-feed.paused {
    opacity: 0.7;
}

.activity-list {
    height: 100%;
    overflow-y: auto;
    padding: 0.5rem;
}

.activity-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem;
    border-radius: 0.5rem;
    transition: background 0.2s;
    margin-bottom: 0.5rem;
}

.activity-item:hover {
    background: #f9fafb;
}

.activity-icon {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    background: var(--dashboard-primary);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.875rem;
}

.activity-message {
    font-size: 0.875rem;
    color: #374151;
    line-height: 1.4;
}

.activity-time {
    font-size: 0.75rem;
    color: #9ca3af;
    margin-top: 0.25rem;
}
</style>
```

#### System Health Dashboard
```html
<!-- System Health Widget -->
<div class="system-health-widget card">
    <div class="widget-header">
        <h3>System Health</h3>
        <div class="health-status" 
             _="init set :overallStatus to 'good'
               on health-update(status)
                 set :overallStatus to status
                 remove .good, .warning, .critical from me
                 add .{status} to me
                 if status is 'good'
                   put '🟢 All Systems Operational' into me
                 else if status is 'warning'
                   put '🟡 Some Issues Detected' into me
                 else
                   put '🔴 Critical Issues' into me
                 end
               end">
            🟢 All Systems Operational
        </div>
    </div>
    
    <div class="health-metrics" 
         hx-get="/api/dashboard/health" 
         hx-trigger="load, every 10s"
         _="on htmx:afterRequest
            set data to JSON.parse(detail.xhr.response)
            
            -- Update CPU usage
            set cpuValue to data.cpu_usage
            set #cpu-progress.style.width to cpuValue + '%'
            put cpuValue + '%' into #cpu-value
            
            -- Update Memory usage
            set memValue to data.memory_usage
            set #memory-progress.style.width to memValue + '%'
            put memValue + '%' into #memory-value
            
            -- Update Disk usage
            set diskValue to data.disk_usage
            set #disk-progress.style.width to diskValue + '%'
            put diskValue + '%' into #disk-value
            
            -- Determine overall status
            set maxUsage to Math.max(cpuValue, memValue, diskValue)
            if maxUsage > 90
              send health-update(status: 'critical') to .health-status
            else if maxUsage > 75
              send health-update(status: 'warning') to .health-status
            else
              send health-update(status: 'good') to .health-status
            end">
        
        <div class="metric">
            <div class="metric-label">CPU Usage</div>
            <div class="metric-bar">
                <div id="cpu-progress" class="metric-progress" style="width: 45%"></div>
            </div>
            <div id="cpu-value" class="metric-value">45%</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Memory Usage</div>
            <div class="metric-bar">
                <div id="memory-progress" class="metric-progress" style="width: 67%"></div>
            </div>
            <div id="memory-value" class="metric-value">67%</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Disk Usage</div>
            <div class="metric-bar">
                <div id="disk-progress" class="metric-progress" style="width: 23%"></div>
            </div>
            <div id="disk-value" class="metric-value">23%</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Active Connections</div>
            <div id="connections-count" class="metric-large-value">1,247</div>
        </div>
    </div>
</div>

<style>
.system-health-widget {
    min-width: 300px;
}

.health-status {
    font-size: 0.875rem;
    font-weight: 500;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    transition: all 0.3s;
}

.health-status.good {
    background: #d1fae5;
    color: #065f46;
}

.health-status.warning {
    background: #fef3c7;
    color: #92400e;
}

.health-status.critical {
    background: #fee2e2;
    color: #991b1b;
}

.health-metrics {
    padding: 1.5rem;
}

.metric {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
}

.metric:last-child {
    margin-bottom: 0;
}

.metric-label {
    min-width: 100px;
    font-size: 0.875rem;
    color: #6b7280;
}

.metric-bar {
    flex: 1;
    height: 8px;
    background: #f3f4f6;
    border-radius: 4px;
    overflow: hidden;
    position: relative;
}

.metric-progress {
    height: 100%;
    background: linear-gradient(90deg, #10b981, #059669);
    border-radius: 4px;
    transition: width 0.3s ease;
}

.metric-value {
    min-width: 50px;
    text-align: right;
    font-size: 0.875rem;
    font-weight: 500;
    color: #374151;
}

.metric-large-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--dashboard-primary);
    margin-left: auto;
}
</style>
```

### Advanced Dashboard Features

#### Dashboard Customization Panel
```html
<!-- Dashboard Customization -->
<div class="dashboard-customizer" 
     _="init 
        set :isOpen to false
        set :layout to localStorage.getItem('dashboard-layout') or 'default'
        set :theme to localStorage.getItem('dashboard-theme') or 'light'
        apply-theme(:theme)
        
        def apply-theme(theme)
          remove .light, .dark from body
          add .{theme} to body
          localStorage.setItem('dashboard-theme', theme)
        end
        
        on toggle-customizer
          if :isOpen
            remove .open from me
            set :isOpen to false
          else
            add .open to me
            set :isOpen to true
          end
        end">
    
    <!-- Customizer Toggle -->
    <button class="customizer-toggle" 
            _="on click send toggle-customizer to .dashboard-customizer">
        ⚙️
    </button>
    
    <!-- Customizer Panel -->
    <div class="customizer-panel">
        <div class="customizer-header">
            <h3>Customize Dashboard</h3>
            <button class="customizer-close" 
                    _="on click send toggle-customizer to .dashboard-customizer">
                ×
            </button>
        </div>
        
        <div class="customizer-content">
            <!-- Theme Selection -->
            <div class="customizer-section">
                <h4>Theme</h4>
                <div class="theme-options">
                    <label class="theme-option">
                        <input type="radio" 
                               name="theme" 
                               value="light" 
                               checked
                               _="on change 
                                  set :theme to my value
                                  apply-theme(my value)">
                        <div class="theme-preview light-preview">
                            <div class="preview-header"></div>
                            <div class="preview-sidebar"></div>
                            <div class="preview-content"></div>
                        </div>
                        <span>Light</span>
                    </label>
                    
                    <label class="theme-option">
                        <input type="radio" 
                               name="theme" 
                               value="dark"
                               _="on change 
                                  set :theme to my value
                                  apply-theme(my value)">
                        <div class="theme-preview dark-preview">
                            <div class="preview-header"></div>
                            <div class="preview-sidebar"></div>
                            <div class="preview-content"></div>
                        </div>
                        <span>Dark</span>
                    </label>
                </div>
            </div>
            
            <!-- Layout Options -->
            <div class="customizer-section">
                <h4>Layout</h4>
                <div class="layout-options">
                    <label class="layout-option">
                        <input type="radio" 
                               name="layout" 
                               value="default" 
                               checked
                               _="on change save-layout-preference(my value)">
                        <span>Default</span>
                    </label>
                    <label class="layout-option">
                        <input type="radio" 
                               name="layout" 
                               value="compact"
                               _="on change save-layout-preference(my value)">
                        <span>Compact</span>
                    </label>
                    <label class="layout-option">
                        <input type="radio" 
                               name="layout" 
                               value="wide"
                               _="on change save-layout-preference(my value)">
                        <span>Wide</span>
                    </label>
                </div>
            </div>
            
            <!-- Widget Visibility -->
            <div class="customizer-section">
                <h4>Widgets</h4>
                <div class="widget-toggles">
                    <label class="widget-toggle">
                        <input type="checkbox" 
                               checked 
                               data-widget="stats"
                               _="on change 
                                  if my checked
                                    show #stats-widget
                                  else
                                    hide #stats-widget
                                  end
                                  save-widget-visibility()">
                        <span>Statistics</span>
                    </label>
                    
                    <label class="widget-toggle">
                        <input type="checkbox" 
                               checked 
                               data-widget="charts"
                               _="on change 
                                  if my checked
                                    show #charts-section
                                  else
                                    hide #charts-section
                                  end
                                  save-widget-visibility()">
                        <span>Charts</span>
                    </label>
                    
                    <label class="widget-toggle">
                        <input type="checkbox" 
                               checked 
                               data-widget="activity"
                               _="on change 
                                  if my checked
                                    show #activity-widget
                                  else
                                    hide #activity-widget
                                  end
                                  save-widget-visibility()">
                        <span>Activity Feed</span>
                    </label>
                </div>
            </div>
            
            <!-- Export/Import Settings -->
            <div class="customizer-section">
                <h4>Settings</h4>
                <div class="settings-actions">
                    <button class="btn-secondary" 
                            _="on click export-settings()">
                        Export Settings
                    </button>
                    <button class="btn-secondary" 
                            _="on click trigger change on #import-file">
                        Import Settings
                    </button>
                    <input type="file" 
                           id="import-file" 
                           accept=".json" 
                           style="display: none;"
                           _="on change import-settings(me.files[0])">
                </div>
            </div>
        </div>
    </div>
</div>

<script type="text/hyperscript">
  def save-layout-preference(layout)
    localStorage.setItem('dashboard-layout', layout)
    remove .default, .compact, .wide from #dashboard-container
    add .{layout} to #dashboard-container
  end
  
  def save-widget-visibility()
    set widgets to {}
    for checkbox in <input[data-widget]/> in .widget-toggles
      set widgets[checkbox.dataset.widget] to checkbox.checked
    end
    localStorage.setItem('dashboard-widgets', JSON.stringify(widgets))
  end
  
  def export-settings()
    set settings to {
      theme: localStorage.getItem('dashboard-theme'),
      layout: localStorage.getItem('dashboard-layout'),
      widgets: JSON.parse(localStorage.getItem('dashboard-widgets') or '{}')
    }
    set blob to new Blob([JSON.stringify(settings, null, 2)], {type: 'application/json'})
    set url to URL.createObjectURL(blob)
    set link to document.createElement('a')
    set link.href to url
    set link.download to 'dashboard-settings.json'
    link.click()
    URL.revokeObjectURL(url)
  end
  
  def import-settings(file)
    if file
      set reader to new FileReader()
      set reader.onload to def(e)
        try
          set settings to JSON.parse(e.target.result)
          if settings.theme
            localStorage.setItem('dashboard-theme', settings.theme)
          end
          if settings.layout
            localStorage.setItem('dashboard-layout', settings.layout)
          end
          if settings.widgets
            localStorage.setItem('dashboard-widgets', JSON.stringify(settings.widgets))
          end
          location.reload()
        catch e
          alert('Error importing settings: ' + e.message)
        end
      end
      reader.readAsText(file)
    end
  end
</script>

<style>
.dashboard-customizer {
    position: fixed;
    top: 50%;
    right: -320px;
    transform: translateY(-50%);
    z-index: 1000;
    transition: right 0.3s ease;
}

.dashboard-customizer.open {
    right: 0;
}

.customizer-toggle {
    position: absolute;
    left: -50px;
    top: 50%;
    transform: translateY(-50%);
    width: 50px;
    height: 50px;
    background: var(--dashboard-primary);
    color: white;
    border: none;
    border-radius: 0.5rem 0 0 0.5rem;
    cursor: pointer;
    font-size: 1.25rem;
    transition: background 0.2s;
}

.customizer-toggle:hover {
    background: #2563eb;
}

.customizer-panel {
    width: 320px;
    height: 80vh;
    background: white;
    border-radius: 0.75rem 0 0 0.75rem;
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
    display: flex;
    flex-direction: column;
}

.customizer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
}

.customizer-header h3 {
    margin: 0;
    color: #1f2937;
}

.customizer-close {
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: #6b7280;
    padding: 0.25rem;
}

.customizer-content {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
}

.customizer-section {
    margin-bottom: 2rem;
}

.customizer-section h4 {
    margin: 0 0 1rem 0;
    color: #374151;
    font-size: 0.875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.theme-options {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.theme-option {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
}

.theme-option input[type="radio"] {
    display: none;
}

.theme-preview {
    width: 80px;
    height: 60px;
    border: 2px solid #e5e7eb;
    border-radius: 0.375rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}

.theme-option input:checked + .theme-preview {
    border-color: var(--dashboard-primary);
}

.light-preview { background: #ffffff; }
.dark-preview { background: #1f2937; }

.preview-header {
    height: 12px;
    background: #f3f4f6;
}

.dark-preview .preview-header {
    background: #374151;
}

.preview-sidebar {
    position: absolute;
    left: 0;
    top: 12px;
    width: 20px;
    height: 48px;
    background: #e5e7eb;
}

.dark-preview .preview-sidebar {
    background: #4b5563;
}

.preview-content {
    position: absolute;
    left: 20px;
    top: 12px;
    right: 0;
    height: 48px;
    background: #f9fafb;
}

.dark-preview .preview-content {
    background: #111827;
}

.layout-options, .widget-toggles {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.layout-option, .widget-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
}

.settings-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

/* Dark theme styles */
body.dark {
    --dashboard-background: #111827;
    background: var(--dashboard-background);
    color: #f9fafb;
}

body.dark .dashboard-sidebar,
body.dark .dashboard-header,
body.dark .card,
body.dark .customizer-panel {
    background: #1f2937;
    border-color: #374151;
}

body.dark .customizer-panel {
    color: #f9fafb;
}
</style>
```

### Advanced Modal Example
```html
<!-- Modal trigger with HTMX -->
<button hx-get="/modal/user-form" 
        hx-target="body" 
        hx-swap="beforeend"
        class="primary">
    Add User
</button>

<!-- Server returns this modal HTML -->
<div class="modal-overlay" 
     _="on click from outside the .modal 
        remove me
        on keyup[key is 'Escape'] from elsewhere 
        remove me">
    
    <div class="modal card">
        <h2>Add User</h2>
        
        <form hx-post="/api/users" 
              hx-target="#user-list" 
              hx-swap="beforeend"
              _="on htmx:afterRequest 
                 if detail.xhr.status is 201
                   remove the closest .modal-overlay
                 end">
            
            <label for="name">Name</label>
            <input name="name" required 
                   _="on input 
                     if my value's length >= 2
                       remove .error from me
                     else
                       add .error to me
                     end">
            
            <label for="email">Email</label>
            <input name="email" type="email" required>
            
            <div class="form-actions">
                <button type="submit">Save User</button>
                <button type="button" 
                        _="on click remove the closest .modal-overlay">
                    Cancel
                </button>
            </div>
        </form>
    </div>
</div>
```

### Live Search with Debouncing
```html
<div class="container">
    <h2>Live Search</h2>
    
    <!-- Search input -->
    <input type="search" 
           name="q"
           hx-get="/api/search" 
           hx-trigger="keyup changed delay:300ms" 
           hx-target="#search-results"
           hx-indicator="#search-loading"
           placeholder="Search users..."
           _="on focus add .searching to #search-container
             on blur remove .searching from #search-container">
    
    <!-- Loading indicator -->
    <div id="search-loading" class="htmx-indicator">
        Searching...
    </div>
    
    <!-- Results container -->
    <div id="search-results" class="grid">
        <!-- Results appear here -->
    </div>
</div>

<style>
.searching {
    border-color: var(--primary-color);
}
</style>
```

### Real-time Updates
```html
<!-- Server-Sent Events with HTMX -->
<div hx-ext="sse" 
     sse-connect="/api/events"
     sse-swap="notification">
    
    <!-- Notifications appear here -->
    <div id="notifications" 
         _="on sse:notification
           add .show to the event's target
           wait 3s
           remove .show from the event's target">
    </div>
</div>

<!-- Chat interface -->
<div class="chat-container">
    <div id="messages" 
         hx-ext="sse" 
         sse-connect="/api/chat"
         sse-swap="message"
         _="on sse:message 
           if detail.user is not me
             play notification sound
           end
           go to the bottom of me smoothly">
    </div>
    
    <form hx-post="/api/chat/send" 
          hx-target="#messages" 
          hx-swap="beforeend"
          _="on htmx:afterRequest reset() me">
        <input name="message" placeholder="Type message..." required>
        <button type="submit">Send</button>
    </form>
</div>
```

---

## Best Practices for AI Code Generation

### 1. HTML Structure Guidelines
```html
<!-- Always use semantic HTML first -->
<article>
    <header>
        <h1>Article Title</h1>
        <time datetime="2024-01-01">January 1, 2024</time>
    </header>
    
    <main>
        <p>Article content...</p>
    </main>
    
    <footer>
        <button hx-post="/api/like" 
                hx-target="#like-count"
                _="on click add .liked to me">
            Like (<span id="like-count">0</span>)
        </button>
    </footer>
</article>
```

### 2. Progressive Enhancement Pattern
```html
<!-- Start with working HTML/CSS -->
<form action="/api/contact" method="post">
    <input name="email" type="email" required>
    <button type="submit">Subscribe</button>
</form>

<!-- Enhance with HTMX -->
<form action="/api/contact" method="post"
      hx-post="/api/contact"
      hx-target="#result"
      hx-swap="innerHTML">
    <input name="email" type="email" required>
    <button type="submit">Subscribe</button>
</form>

<!-- Add hyperscript for client-side enhancements -->
<form action="/api/contact" method="post"
      hx-post="/api/contact"
      hx-target="#result"
      hx-swap="innerHTML"
      _="on htmx:afterRequest 
         if detail.xhr.status is 200
           reset() me
           put 'Thanks for subscribing!' into #result
         end">
    <input name="email" type="email" required 
           _="on input 
             if my validity.valid 
               remove .error from me 
             else 
               add .error to me 
             end">
    <button type="submit">Subscribe</button>
</form>
```

### 3. Error Handling Patterns
```html
<!-- Server error handling -->
<div hx-get="/api/data"
     hx-target="#content"
     hx-on::htmx:responseError="put 'Failed to load data' into #error"
     hx-on::htmx:timeout="put 'Request timed out' into #error">
    Load Data
</div>

<!-- Client-side validation -->
<form _="on submit
         set isValid to true
         for input in <input[required]/> in me
           if input.value is ''
             add .error to input
             set isValid to false
           end
         end
         if not isValid halt the event
         end">
    
    <input name="name" required>
    <button type="submit">Submit</button>
</form>
```

### 4. State Management
```html
<!-- Use element-scoped variables for component state -->
<div class="counter" 
     _="init set :count to 0
       on increment 
         increment :count 
         put :count into .count-display in me
       on decrement 
         decrement :count 
         put :count into .count-display in me">
    
    <button _="on click send increment to my parentElement">+</button>
    <span class="count-display">0</span>
    <button _="on click send decrement to my parentElement">-</button>
</div>
```

### 5. Performance Considerations
```html
<!-- Use appropriate swap strategies -->
<div hx-get="/api/large-list"
     hx-swap="outerHTML settle:100ms"
     hx-indicator="#loading">
    
<!-- Implement infinite scroll efficiently -->
<div hx-get="/api/more?page=2"
     hx-trigger="revealed"
     hx-swap="outerHTML"
     hx-select="#more-content">
    <div id="more-content">Load more...</div>
</div>

<!-- Debounce user input -->
<input hx-get="/api/search"
       hx-trigger="keyup changed delay:500ms"
       hx-target="#results">
```

### 6. Accessibility Guidelines
```html
<!-- Proper ARIA labels and roles -->
<button hx-get="/api/data"
        hx-target="#results"
        aria-describedby="loading-status"
        _="on htmx:beforeRequest 
           set @aria-busy to 'true'
           on htmx:afterRequest 
           set @aria-busy to 'false'">
    Load Data
</button>

<div id="loading-status" aria-live="polite">
    <span class="htmx-indicator">Loading...</span>
</div>

<!-- Keyboard navigation -->
<div class="modal"
     _="on keyup[key is 'Escape'] remove me
       init focus() the first <input/> in me">
    <form>
        <input name="field1" required>
        <button type="submit">Save</button>
        <button type="button" 
               _="on click remove the closest .modal">Cancel</button>
    </form>
</div>
```

### 7. Code Organization
```html
<!-- Separate concerns clearly -->
<script type="text/hyperscript">
  -- Global functions
  def formatCurrency(amount)
    return '$' + amount.toFixed(2)
  end
  
  -- Reusable behaviors
  behavior Tooltip
    on mouseenter
      make a <div.tooltip/> 
      put @data-tooltip into it
      put it after me
    end
    
    on mouseleave
      remove .tooltip from elsewhere
    end
  end
</script>

<!-- Use behaviors for reusable components -->
<span data-tooltip="This is helpful info" 
      _="install Tooltip">Hover me</span>
```

### 8. Testing Considerations
```html
<!-- Add data attributes for testing -->
<button hx-post="/api/submit"
        data-testid="submit-button"
        _="on click 
           add .submitting to me
           on htmx:afterRequest 
           remove .submitting from me">
    Submit
</button>

<!-- Make state observable -->
<div id="app-state" 
     _="on stateChange(newState)
       set @data-state to newState
       log 'State changed to:', newState">
</div>
```

---

## Common Pitfalls to Avoid

### 1. HTMX Pitfalls
- **Don't forget `hx-target`** - Without it, HTMX will replace the triggering element
- **Use proper HTTP methods** - GET for retrieval, POST for creation, PUT for updates, DELETE for removal
- **Handle loading states** - Always provide feedback during requests
- **Validate on server** - Client-side validation is UX, server-side is security

### 2. _hyperscript Pitfalls
- **Remember `end` keywords** - Most blocks need to be closed with `end`
- **Variable scoping** - Use `:` for element scope, `$` for global scope
- **Event bubbling** - Events bubble up the DOM by default
- **Async transparency** - Commands automatically wait for promises to resolve

### 3. missing.css Pitfalls
- **Don't fight the defaults** - Work with the semantic styling, don't override extensively
- **Use CSS variables** - Customize through variables rather than overriding selectors
- **Progressive enhancement** - Start classless, add classes for specific needs
- **Mobile-first** - The framework is responsive by default

---

This guide provides comprehensive information for AI models to generate effective, modern web applications using HTMX, _hyperscript, and missing.css. These technologies work together to create powerful, accessible, and maintainable web applications with minimal JavaScript complexity.
