/**
 * Main Dashboard JavaScript
 * Handles dashboard functionality including HTMX interactions, data updates, and UI management
 */

class SystemDashboard {
    constructor() {
        this.autoRefreshInterval = null;
        this.refreshRate = 30000; // 30 seconds
        this.analyzerServices = new Map();
        this.isInitialized = false;
        this.retryAttempts = 0;
        this.maxRetries = 3;
        
        this.init();
    }

    init() {
        if (this.isInitialized) return;
        
        console.log('Initializing System Dashboard...');
        
        // Setup HTMX event listeners
        this.setupHTMXEventListeners();
        
        // Initialize auto-refresh if enabled
        this.setupAutoRefresh();
        
        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
        
        // Initialize tooltips and popovers
        this.initializeBootstrapComponents();
        
        this.isInitialized = true;
        console.log('System Dashboard initialized successfully');
    }

    setupHTMXEventListeners() {
        // Handle HTMX request start
        document.body.addEventListener('htmx:beforeRequest', (evt) => {
            this.showLoadingIndicator(evt.detail.elt);
        });

        // Handle HTMX request completion
        document.body.addEventListener('htmx:afterRequest', (evt) => {
            this.hideLoadingIndicator(evt.detail.elt);
            
            if (evt.detail.successful) {
                this.handleSuccessfulRequest(evt);
            } else {
                this.handleFailedRequest(evt);
            }
        });

        // Handle HTMX content swap
        document.body.addEventListener('htmx:afterSwap', (evt) => {
            // Re-initialize Bootstrap components in new content
            this.initializeBootstrapComponents(evt.detail.elt);
            
            // Trigger custom events for analytics
            this.trackDashboardActivity(evt.detail.pathInfo.requestPath);
        });
    }

    setupAutoRefresh() {
        const autoRefreshCheckbox = document.getElementById('auto-refresh-toggle');
        if (autoRefreshCheckbox) {
            autoRefreshCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
            
            // Start auto-refresh if checkbox is checked on page load
            if (autoRefreshCheckbox.checked) {
                this.startAutoRefresh();
            }
        }
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + R: Refresh all panels
            if ((e.ctrlKey || e.metaKey) && e.key === 'r' && e.shiftKey) {
                e.preventDefault();
                this.refreshAllPanels();
            }
            
            // Ctrl/Cmd + D: Toggle auto-refresh
            if ((e.ctrlKey || e.metaKey) && e.key === 'd' && e.shiftKey) {
                e.preventDefault();
                this.toggleAutoRefresh();
            }
        });
    }

    initializeBootstrapComponents(container = document) {
        // Initialize tooltips
        const tooltipTriggerList = container.querySelectorAll('[data-bs-toggle="tooltip"]');
        const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => 
            new bootstrap.Tooltip(tooltipTriggerEl));

        // Initialize popovers
        const popoverTriggerList = container.querySelectorAll('[data-bs-toggle="popover"]');
        const popoverList = [...popoverTriggerList].map(popoverTriggerEl => 
            new bootstrap.Popover(popoverTriggerEl));

        // Initialize dropdowns
        const dropdownElementList = container.querySelectorAll('.dropdown-toggle');
        const dropdownList = [...dropdownElementList].map(dropdownToggleEl => 
            new bootstrap.Dropdown(dropdownToggleEl));
    }

    // Panel Management Methods
    refreshAnalyzerStatus() {
        console.log('Refreshing analyzer status...');
        htmx.trigger('#analyzer-services-panel', 'refresh');
    }

    refreshDockerStatus() {
        console.log('Refreshing Docker status...');
        htmx.trigger('#docker-status-panel', 'refresh');
    }

    refreshSystemHealth() {
        console.log('Refreshing system health...');
        htmx.trigger('#system-health-panel', 'refresh');
    }

    refreshActivity() {
        console.log('Refreshing recent activity...');
        htmx.trigger('#recent-activity-panel', 'refresh');
    }

    refreshAllPanels() {
        console.log('Refreshing all dashboard panels...');
        this.refreshAnalyzerStatus();
        this.refreshDockerStatus();
        this.refreshSystemHealth();
        this.refreshActivity();
        
        this.showNotification('All panels refreshed', 'success');
    }

    // Auto-refresh Methods
    startAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        
        this.autoRefreshInterval = setInterval(() => {
            this.refreshAllPanels();
        }, this.refreshRate);
        
        console.log(`Auto-refresh started with ${this.refreshRate/1000}s interval`);
        this.showNotification('Auto-refresh enabled', 'info');
    }

    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
        
        console.log('Auto-refresh stopped');
        this.showNotification('Auto-refresh disabled', 'info');
    }

    toggleAutoRefresh() {
        const checkbox = document.getElementById('auto-refresh-toggle');
        if (checkbox) {
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event('change'));
        }
    }

    // Loading States
    showLoadingIndicator(element) {
        const indicator = element.querySelector('.htmx-indicator');
        if (indicator) {
            indicator.style.display = 'block';
        } else {
            element.classList.add('htmx-request');
        }
    }

    hideLoadingIndicator(element) {
        const indicator = element.querySelector('.htmx-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        } else {
            element.classList.remove('htmx-request');
        }
    }

    // Error Handling
    handleSuccessfulRequest(evt) {
        this.retryAttempts = 0;
        
        // Update last refresh timestamp
        const timestamp = new Date().toLocaleTimeString();
        const statusElements = document.querySelectorAll('.last-updated');
        statusElements.forEach(el => {
            el.textContent = `Last updated: ${timestamp}`;
        });
    }

    handleFailedRequest(evt) {
        this.retryAttempts++;
        
        if (this.retryAttempts < this.maxRetries) {
            console.warn(`Request failed, retrying (${this.retryAttempts}/${this.maxRetries})...`);
            setTimeout(() => {
                htmx.trigger(evt.detail.elt, 'retry');
            }, 2000 * this.retryAttempts);
        } else {
            console.error('Request failed after maximum retries');
            this.showNotification('Failed to update dashboard data', 'error');
            this.retryAttempts = 0;
        }
    }

    // Utility Methods
    runSystemDiagnostics() {
        console.log('Running system diagnostics...');
        
        // Show loading state
        const button = event.target;
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Running...';
        button.disabled = true;
        
        // Simulate diagnostics
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
            this.showNotification('System diagnostics completed', 'success');
        }, 3000);
    }

    showNotification(message, type = 'info') {
        // Create toast notification
        const toastContainer = document.getElementById('toast-container') || this.createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${this.getIconForType(type)} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove toast after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
        return container;
    }

    getIconForType(type) {
        const icons = {
            'success': 'check-circle',
            'error': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    trackDashboardActivity(path) {
        // Analytics tracking for dashboard interactions
        console.log(`Dashboard activity: ${path}`);
        
        // You can integrate with analytics services here
        if (window.gtag) {
            gtag('event', 'dashboard_interaction', {
                'event_category': 'Dashboard',
                'event_label': path
            });
        }
    }

    // Public API methods for external use
    setRefreshRate(rate) {
        this.refreshRate = rate * 1000; // Convert to milliseconds
        if (this.autoRefreshInterval) {
            this.stopAutoRefresh();
            this.startAutoRefresh();
        }
    }

    getSystemStatus() {
        return {
            autoRefreshEnabled: !!this.autoRefreshInterval,
            refreshRate: this.refreshRate / 1000,
            retryAttempts: this.retryAttempts,
            isInitialized: this.isInitialized
        };
    }
}

// Apps Grid JavaScript
class AppsGridManager {
    constructor() {
        this.selectedApps = new Set();
        this.bulkActionsVisible = false;
        this.currentView = 'grid';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupBulkActions();
    }

    setupEventListeners() {
        // App selection handling
        document.addEventListener('change', (e) => {
            if (e.target.matches('.app-select-checkbox')) {
                this.handleAppSelection(e.target);
            }
        });

        // Bulk actions
        document.addEventListener('click', (e) => {
            if (e.target.matches('.bulk-action-btn')) {
                this.handleBulkAction(e.target.dataset.action);
            }
        });

        // View mode switching
        document.addEventListener('click', (e) => {
            if (e.target.matches('.view-mode-btn')) {
                this.switchViewMode(e.target.dataset.view);
            }
        });
    }

    handleAppSelection(checkbox) {
        const appId = checkbox.value;
        
        if (checkbox.checked) {
            this.selectedApps.add(appId);
        } else {
            this.selectedApps.delete(appId);
        }
        
        this.updateBulkActionsVisibility();
        this.updateSelectionCounter();
    }

    updateBulkActionsVisibility() {
        const bulkActionsBar = document.getElementById('bulk-actions');
        const shouldShow = this.selectedApps.size > 0;
        
        if (shouldShow && !this.bulkActionsVisible) {
            bulkActionsBar.classList.remove('d-none');
            this.bulkActionsVisible = true;
        } else if (!shouldShow && this.bulkActionsVisible) {
            bulkActionsBar.classList.add('d-none');
            this.bulkActionsVisible = false;
        }
    }

    updateSelectionCounter() {
        const counter = document.getElementById('selection-count');
        if (counter) {
            counter.textContent = this.selectedApps.size;
        }
    }

    handleBulkAction(action) {
        if (this.selectedApps.size === 0) {
            dashboard.showNotification('No applications selected', 'warning');
            return;
        }

        const appIds = Array.from(this.selectedApps);
        
        // Send HTMX request for bulk action
        htmx.ajax('POST', '/advanced/api/containers/bulk-action', {
            values: {
                action: action,
                app_ids: appIds
            },
            target: '#bulk-action-results',
            swap: 'innerHTML'
        });
    }

    switchViewMode(mode) {
        this.currentView = mode;
        
        // Update active button
        document.querySelectorAll('.view-mode-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-view="${mode}"]`).classList.add('active');
        
        // Trigger HTMX request to get new view
        const container = document.getElementById('apps-container');
        const currentParams = new URLSearchParams(window.location.search);
        currentParams.set('view', mode);
        
        htmx.ajax('GET', `/advanced/api/apps/grid?${currentParams.toString()}`, {
            target: container,
            swap: 'innerHTML'
        });
    }

    clearSelection() {
        this.selectedApps.clear();
        document.querySelectorAll('.app-select-checkbox').forEach(cb => {
            cb.checked = false;
        });
        this.updateBulkActionsVisibility();
        this.updateSelectionCounter();
    }

    selectAll() {
        document.querySelectorAll('.app-select-checkbox').forEach(cb => {
            cb.checked = true;
            this.selectedApps.add(cb.value);
        });
        this.updateBulkActionsVisibility();
        this.updateSelectionCounter();
    }
}

// Models Overview JavaScript
class ModelsManager {
    constructor() {
        this.currentSort = 'name';
        this.currentFilters = {};
        this.init();
    }

    init() {
        this.setupFilterHandlers();
        this.setupSortHandlers();
    }

    setupFilterHandlers() {
        document.addEventListener('change', (e) => {
            if (e.target.matches('.filter-input')) {
                this.handleFilterChange(e.target);
            }
        });
    }

    setupSortHandlers() {
        document.addEventListener('click', (e) => {
            if (e.target.matches('.sort-btn')) {
                this.handleSortChange(e.target.dataset.sort);
            }
        });
    }

    handleFilterChange(input) {
        const filterType = input.name;
        const value = input.value;
        
        if (value) {
            this.currentFilters[filterType] = value;
        } else {
            delete this.currentFilters[filterType];
        }
        
        this.applyFilters();
    }

    handleSortChange(sortBy) {
        this.currentSort = sortBy;
        this.applyFilters();
    }

    applyFilters() {
        const params = new URLSearchParams(this.currentFilters);
        params.set('sort', this.currentSort);
        
        htmx.ajax('GET', `/advanced/api/models/display?${params.toString()}`, {
            target: '#models-container',
            swap: 'innerHTML'
        });
    }

    clearFilters() {
        this.currentFilters = {};
        document.querySelectorAll('.filter-input').forEach(input => {
            input.value = '';
        });
        this.applyFilters();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    window.dashboard = new SystemDashboard();
    
    // Initialize apps grid if on apps page
    if (document.getElementById('apps-container')) {
        window.appsGrid = new AppsGridManager();
    }
    
    // Initialize models manager if on models page
    if (document.getElementById('models-container')) {
        window.modelsManager = new ModelsManager();
    }
    
    console.log('All dashboard components initialized');
});

// Utility functions for global use
window.clearAllFilters = function() {
    // Clear apps filters
    if (window.appsGrid) {
        window.appsGrid.clearSelection();
    }
    
    // Clear models filters
    if (window.modelsManager) {
        window.modelsManager.clearFilters();
    }
    
    // Clear form inputs
    document.querySelectorAll('.filter-input, .search-input').forEach(input => {
        input.value = '';
    });
    
    dashboard.showNotification('All filters cleared', 'info');
};

window.refreshDashboard = function() {
    if (window.dashboard) {
        window.dashboard.refreshAllPanels();
    }
};
