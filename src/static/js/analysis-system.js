/**
 * Analysis System Frontend Framework
 * ==================================
 * 
 * Comprehensive JavaScript framework for the reimplemented analysis system.
 * Handles all UI interactions, real-time updates, and API communications.
 */

class AnalysisSystemAPI {
    constructor() {
        this.baseURL = '/api/analysis';
        this.authHeaders = this.getAuthHeaders();
    }

    getAuthHeaders() {
        // Add authentication headers if needed
        const token = localStorage.getItem('auth_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...this.authHeaders,
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    }

    // Task Management
    async getTasks(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/tasks?${query}`);
    }

    async getTask(taskId) {
        return this.request(`/tasks/${taskId}`);
    }

    async createTask(taskData) {
        return this.request('/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
    }

    async cancelTask(taskId) {
        return this.request(`/tasks/${taskId}/cancel`, { method: 'POST' });
    }

    // Batch Management
    async getBatches(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/batches?${query}`);
    }

    async getBatch(batchId) {
        return this.request(`/batches/${batchId}`);
    }

    async createBatch(batchData) {
        return this.request('/batches', {
            method: 'POST',
            body: JSON.stringify(batchData)
        });
    }

    async startBatch(batchId) {
        return this.request(`/batches/${batchId}/start`, { method: 'POST' });
    }

    async cancelBatch(batchId) {
        return this.request(`/batches/${batchId}/cancel`, { method: 'POST' });
    }

    // System Status
    async getDashboardData() {
        return this.request('/dashboard-data');
    }

    async getSystemStatus() {
        return this.request('/system-status');
    }

    async getQueueStatus() {
        return this.request('/queue-status');
    }

    // Templates and Configuration
    async getBatchTemplates() {
        return this.request('/batch-templates');
    }

    async getConfigurations(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/configurations?${query}`);
    }

    async getAvailableModels() {
        return this.request('/available-models');
    }

    // Analytics
    async getTrends(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/analytics/trends?${query}`);
    }

    async getComparison(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/analytics/comparison?${query}`);
    }
}

class NotificationManager {
    constructor() {
        this.container = this.createContainer();
        this.notifications = new Map();
    }

    createContainer() {
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        return container;
    }

    show(message, type = 'info', duration = 5000) {
        const id = Date.now().toString();
        const notification = this.createNotification(id, message, type);
        
        this.container.appendChild(notification);
        this.notifications.set(id, notification);

        // Trigger animation
        setTimeout(() => notification.classList.add('show'), 100);

        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(id), duration);
        }

        return id;
    }

    createNotification(id, message, type) {
        const div = document.createElement('div');
        div.className = `toast align-items-center text-white bg-${this.getBootstrapClass(type)} border-0`;
        div.setAttribute('role', 'alert');
        div.setAttribute('data-id', id);
        
        div.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${this.getIcon(type)} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        onclick="analysisSystem.notifications.dismiss('${id}')"></button>
            </div>
        `;

        return div;
    }

    getBootstrapClass(type) {
        const classes = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'primary'
        };
        return classes[type] || 'primary';
    }

    getIcon(type) {
        const icons = {
            'success': 'check-circle',
            'error': 'exclamation-triangle',
            'warning': 'exclamation-circle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    dismiss(id) {
        const notification = this.notifications.get(id);
        if (notification) {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
                this.notifications.delete(id);
            }, 300);
        }
    }

    clear() {
        this.notifications.forEach((_, id) => this.dismiss(id));
    }
}

class RealTimeUpdater {
    constructor(api, notifications) {
        this.api = api;
        this.notifications = notifications;
        this.updateInterval = 30000; // 30 seconds
        this.intervals = new Map();
        this.subscribers = new Map();
    }

    subscribe(type, callback, interval = this.updateInterval) {
        const id = `${type}_${Date.now()}`;
        
        if (!this.subscribers.has(type)) {
            this.subscribers.set(type, new Map());
        }
        
        this.subscribers.get(type).set(id, callback);
        
        // Start interval if first subscriber for this type
        if (this.subscribers.get(type).size === 1) {
            this.startUpdates(type, interval);
        }
        
        return id;
    }

    unsubscribe(type, id) {
        if (this.subscribers.has(type)) {
            this.subscribers.get(type).delete(id);
            
            // Stop interval if no more subscribers
            if (this.subscribers.get(type).size === 0) {
                this.stopUpdates(type);
            }
        }
    }

    startUpdates(type, interval) {
        const updateFunction = this.getUpdateFunction(type);
        if (updateFunction) {
            const intervalId = setInterval(async () => {
                try {
                    const data = await updateFunction();
                    this.notifySubscribers(type, data);
                } catch (error) {
                    console.error(`Real-time update error for ${type}:`, error);
                }
            }, interval);
            
            this.intervals.set(type, intervalId);
        }
    }

    stopUpdates(type) {
        const intervalId = this.intervals.get(type);
        if (intervalId) {
            clearInterval(intervalId);
            this.intervals.delete(type);
        }
    }

    getUpdateFunction(type) {
        const functions = {
            'dashboard': () => this.api.getDashboardData(),
            'tasks': () => this.api.getTasks({ limit: 20 }),
            'batches': () => this.api.getBatches({ limit: 10 }),
            'system': () => this.api.getSystemStatus(),
            'queue': () => this.api.getQueueStatus()
        };
        return functions[type];
    }

    notifySubscribers(type, data) {
        if (this.subscribers.has(type)) {
            this.subscribers.get(type).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Subscriber callback error for ${type}:`, error);
                }
            });
        }
    }

    destroy() {
        this.intervals.forEach((intervalId) => clearInterval(intervalId));
        this.intervals.clear();
        this.subscribers.clear();
    }
}

class AnalysisFormManager {
    constructor(api, notifications) {
        this.api = api;
        this.notifications = notifications;
        this.forms = new Map();
    }

    registerForm(formElement, config = {}) {
        const formId = formElement.id || `form_${Date.now()}`;
        
        const formConfig = {
            validation: config.validation || {},
            submitHandler: config.submitHandler || this.defaultSubmitHandler.bind(this),
            successCallback: config.successCallback || this.defaultSuccessCallback.bind(this),
            errorCallback: config.errorCallback || this.defaultErrorCallback.bind(this),
            ...config
        };

        this.forms.set(formId, {
            element: formElement,
            config: formConfig
        });

        this.setupForm(formElement, formConfig);
        return formId;
    }

    setupForm(formElement, config) {
        formElement.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(formElement);
            const data = Object.fromEntries(formData.entries());
            
            // Validate
            const validation = this.validateForm(data, config.validation);
            if (!validation.isValid) {
                this.showValidationErrors(formElement, validation.errors);
                return;
            }

            // Clear previous errors
            this.clearValidationErrors(formElement);

            try {
                // Show loading
                this.setFormLoading(formElement, true);
                
                // Submit
                const result = await config.submitHandler(data);
                config.successCallback(result, formElement);
                
            } catch (error) {
                config.errorCallback(error, formElement);
            } finally {
                this.setFormLoading(formElement, false);
            }
        });
    }

    validateForm(data, rules) {
        const errors = {};
        let isValid = true;

        Object.entries(rules).forEach(([field, fieldRules]) => {
            const value = data[field];
            const fieldErrors = [];

            if (fieldRules.required && (!value || value.trim() === '')) {
                fieldErrors.push('This field is required');
                isValid = false;
            }

            if (value && fieldRules.minLength && value.length < fieldRules.minLength) {
                fieldErrors.push(`Minimum length is ${fieldRules.minLength}`);
                isValid = false;
            }

            if (value && fieldRules.maxLength && value.length > fieldRules.maxLength) {
                fieldErrors.push(`Maximum length is ${fieldRules.maxLength}`);
                isValid = false;
            }

            if (value && fieldRules.pattern && !fieldRules.pattern.test(value)) {
                fieldErrors.push(fieldRules.patternMessage || 'Invalid format');
                isValid = false;
            }

            if (fieldRules.custom) {
                const customResult = fieldRules.custom(value, data);
                if (customResult !== true) {
                    fieldErrors.push(customResult);
                    isValid = false;
                }
            }

            if (fieldErrors.length > 0) {
                errors[field] = fieldErrors;
            }
        });

        return { isValid, errors };
    }

    showValidationErrors(formElement, errors) {
        Object.entries(errors).forEach(([field, fieldErrors]) => {
            const fieldElement = formElement.querySelector(`[name="${field}"]`);
            if (fieldElement) {
                fieldElement.classList.add('is-invalid');
                
                let feedback = fieldElement.parentElement.querySelector('.invalid-feedback');
                if (!feedback) {
                    feedback = document.createElement('div');
                    feedback.className = 'invalid-feedback';
                    fieldElement.parentElement.appendChild(feedback);
                }
                
                feedback.textContent = fieldErrors[0];
            }
        });
    }

    clearValidationErrors(formElement) {
        formElement.querySelectorAll('.is-invalid').forEach(el => {
            el.classList.remove('is-invalid');
        });
        
        formElement.querySelectorAll('.invalid-feedback').forEach(el => {
            el.remove();
        });
    }

    setFormLoading(formElement, loading) {
        const submitButton = formElement.querySelector('[type="submit"]');
        if (submitButton) {
            submitButton.disabled = loading;
            
            if (loading) {
                submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Processing...';
            } else {
                // Restore original text
                const originalText = submitButton.dataset.originalText || 'Submit';
                submitButton.innerHTML = originalText;
            }
        }
    }

    async defaultSubmitHandler(data) {
        // Override in specific implementations
        throw new Error('Submit handler not implemented');
    }

    defaultSuccessCallback(result, formElement) {
        this.notifications.show('Operation completed successfully', 'success');
        formElement.reset();
    }

    defaultErrorCallback(error, formElement) {
        this.notifications.show(`Error: ${error.message}`, 'error');
    }
}

class AnalysisChartManager {
    constructor() {
        this.charts = new Map();
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    }
                },
                x: {
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    }
                }
            }
        };
    }

    createChart(canvasElement, config) {
        const chartId = canvasElement.id || `chart_${Date.now()}`;
        
        // Destroy existing chart if any
        if (this.charts.has(chartId)) {
            this.charts.get(chartId).destroy();
        }

        const chartConfig = {
            ...config,
            options: {
                ...this.defaultOptions,
                ...config.options
            }
        };

        const chart = new Chart(canvasElement, chartConfig);
        this.charts.set(chartId, chart);
        
        return chart;
    }

    updateChart(chartId, newData) {
        const chart = this.charts.get(chartId);
        if (chart) {
            chart.data = newData;
            chart.update('none');
        }
    }

    destroyChart(chartId) {
        const chart = this.charts.get(chartId);
        if (chart) {
            chart.destroy();
            this.charts.delete(chartId);
        }
    }

    destroyAll() {
        this.charts.forEach(chart => chart.destroy());
        this.charts.clear();
    }
}

class AnalysisSystem {
    constructor() {
        this.api = new AnalysisSystemAPI();
        this.notifications = new NotificationManager();
        this.realTime = new RealTimeUpdater(this.api, this.notifications);
        this.forms = new AnalysisFormManager(this.api, this.notifications);
        this.charts = new AnalysisChartManager();
        
        this.init();
    }

    init() {
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.onDOMReady());
        } else {
            this.onDOMReady();
        }
    }

    onDOMReady() {
        this.setupGlobalEventListeners();
        this.initializePage();
    }

    setupGlobalEventListeners() {
        // Handle errors globally
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
        });

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
        });

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    initializePage() {
        const pageName = this.getCurrentPageName();
        
        switch (pageName) {
            case 'dashboard':
                this.initializeDashboard();
                break;
            case 'task-manager':
                this.initializeTaskManager();
                break;
            case 'batch-manager':
                this.initializeBatchManager();
                break;
            case 'results-preview':
                this.initializeResultsPreview();
                break;
            default:
                console.log(`No specific initialization for page: ${pageName}`);
        }
    }

    getCurrentPageName() {
        const path = window.location.pathname;
        const body = document.body;
        
        // Check for page identifier in body class or data attribute
        if (body.classList.contains('analysis-dashboard')) return 'dashboard';
        if (body.classList.contains('task-manager')) return 'task-manager';
        if (body.classList.contains('batch-manager')) return 'batch-manager';
        if (body.classList.contains('results-preview')) return 'results-preview';
        
        // Fallback to path analysis
        if (path.includes('dashboard')) return 'dashboard';
        if (path.includes('tasks')) return 'task-manager';
        if (path.includes('batch')) return 'batch-manager';
        if (path.includes('results')) return 'results-preview';
        
        return 'unknown';
    }

    initializeDashboard() {
        console.log('Initializing dashboard...');
        
        // Subscribe to real-time updates
        this.realTime.subscribe('dashboard', (data) => {
            this.updateDashboardData(data);
        });

        // Initialize charts
        this.initializeDashboardCharts();
    }

    initializeTaskManager() {
        console.log('Initializing task manager...');
        
        // Subscribe to task updates
        this.realTime.subscribe('tasks', (data) => {
            this.updateTasksList(data.tasks);
            this.updateTaskStats(data.stats);
        });

        // Setup task forms
        const createTaskForm = document.getElementById('create-task-form');
        if (createTaskForm) {
            this.forms.registerForm(createTaskForm, {
                validation: {
                    model_slug: { required: true },
                    app_number: { required: true, pattern: /^\d+$/ },
                    analysis_type: { required: true }
                },
                submitHandler: async (data) => {
                    return await this.api.createTask(data);
                },
                successCallback: (result) => {
                    this.notifications.show('Task created successfully', 'success');
                    this.refreshTasksList();
                }
            });
        }
    }

    initializeBatchManager() {
        console.log('Initializing batch manager...');
        
        // Subscribe to batch updates
        this.realTime.subscribe('batches', (data) => {
            this.updateBatchesList(data.batches);
        });

        // Setup batch creation wizard
        this.initializeBatchWizard();
    }

    initializeResultsPreview() {
        console.log('Initializing results preview...');
        
        // Setup result filters
        this.setupResultFilters();
        
        // Initialize export functionality
        this.setupResultExport();
    }

    // Utility methods
    formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleString();
    }

    formatDuration(seconds) {
        if (!seconds) return 'N/A';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    }

    formatFileSize(bytes) {
        if (!bytes) return 'N/A';
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    async refreshData() {
        try {
            // Refresh current page data
            const pageName = this.getCurrentPageName();
            
            switch (pageName) {
                case 'dashboard':
                    await this.refreshDashboard();
                    break;
                case 'task-manager':
                    await this.refreshTasksList();
                    break;
                case 'batch-manager':
                    await this.refreshBatchesList();
                    break;
            }
            
            this.notifications.show('Data refreshed', 'info', 2000);
        } catch (error) {
            this.notifications.show('Failed to refresh data', 'error');
        }
    }

    cleanup() {
        this.realTime.destroy();
        this.charts.destroyAll();
    }
}

// Global instance
const analysisSystem = new AnalysisSystem();

// Export for use in other scripts
window.analysisSystem = analysisSystem;

// Utility functions for backward compatibility
window.AnalysisAPI = AnalysisSystemAPI;
window.NotificationManager = NotificationManager;
window.AnalysisCharts = AnalysisChartManager;



