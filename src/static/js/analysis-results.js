/**
 * Enhanced Analysis Results JavaScript API
 * ========================================
 * 
 * Provides improved API communication and error handling for analysis results.
 * Uses the new v2 API endpoints with structured data.
 */

class AnalysisResultsAPI {
    constructor(taskId, baseUrl = '/analysis/api/v2') {
        this.taskId = taskId;
        this.baseUrl = baseUrl;
        this.cache = new Map();
        this.listeners = new Map();
    }

    /**
     * Generic API call with error handling and loading states
     */
    async apiCall(endpoint, options = {}) {
        const url = `${this.baseUrl}/tasks/${this.taskId}/${endpoint}`;
        
        console.log(`[AnalysisAPI] Calling: ${url}`);
        
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            console.log(`[AnalysisAPI] Response for ${endpoint}: ${response.status}`);

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`[AnalysisAPI] Error response for ${endpoint}:`, errorText);
                
                let errorData;
                try {
                    errorData = JSON.parse(errorText);
                } catch (e) {
                    errorData = { error: errorText || 'Network error' };
                }
                
                throw new Error(errorData.error || `HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            console.log(`[AnalysisAPI] Success for ${endpoint}:`, data);
            return data;
        } catch (error) {
            console.error(`[AnalysisAPI] API call failed for ${endpoint}:`, error);
            this.notifyError(endpoint, error);
            throw error;
        }
    }

    /**
     * Get complete task results
     */
    async getResults() {
        if (this.cache.has('results')) {
            return this.cache.get('results');
        }

        const results = await this.apiCall('results');
        this.cache.set('results', results);
        return results;
    }

    /**
     * Get task summary for overview tab
     */
    async getSummary() {
        if (this.cache.has('summary')) {
            return this.cache.get('summary');
        }

        const summary = await this.apiCall('summary');
        this.cache.set('summary', summary);
        return summary;
    }

    /**
     * Get security data
     */
    async getSecurityData() {
        if (this.cache.has('security')) {
            return this.cache.get('security');
        }

        const securityData = await this.apiCall('security');
        this.cache.set('security', securityData);
        return securityData;
    }

    /**
     * Get performance data
     */
    async getPerformanceData() {
        if (this.cache.has('performance')) {
            return this.cache.get('performance');
        }

        const performanceData = await this.apiCall('performance');
        this.cache.set('performance', performanceData);
        return performanceData;
    }

    /**
     * Get code quality data
     */
    async getQualityData() {
        if (this.cache.has('quality')) {
            return this.cache.get('quality');
        }

        const qualityData = await this.apiCall('quality');
        this.cache.set('quality', qualityData);
        return qualityData;
    }

    /**
     * Get AI requirements data
     */
    async getRequirementsData() {
        if (this.cache.has('requirements')) {
            return this.cache.get('requirements');
        }

        const requirementsData = await this.apiCall('requirements');
        this.cache.set('requirements', requirementsData);
        return requirementsData;
    }

    /**
     * Get comprehensive tool execution data
     */
    async getToolsData() {
        if (this.cache.has('tools')) {
            return this.cache.get('tools');
        }

        const toolsData = await this.apiCall('tools');
        this.cache.set('tools', toolsData);
        return toolsData;
    }

    /**
     * Force refresh data from API
     */
    async refreshData() {
        this.cache.clear();
        return await this.apiCall('refresh', { method: 'POST' });
    }

    /**
     * Subscribe to data updates
     */
    addEventListener(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }

    /**
     * Notify listeners of errors
     */
    notifyError(endpoint, error) {
        const errorListeners = this.listeners.get('error') || [];
        errorListeners.forEach(callback => {
            try {
                callback({ endpoint, error, taskId: this.taskId });
            } catch (e) {
                console.error('Error in error listener:', e);
            }
        });
    }

    /**
     * Notify listeners of successful data loads
     */
    notifyDataLoaded(type, data) {
        const dataListeners = this.listeners.get('dataLoaded') || [];
        dataListeners.forEach(callback => {
            try {
                callback({ type, data, taskId: this.taskId });
            } catch (e) {
                console.error('Error in data loaded listener:', e);
            }
        });
    }
}

/**
 * Analysis Results Manager
 * Coordinates UI updates and data loading
 */
class AnalysisResultsManager {
    constructor(taskId) {
        this.taskId = taskId;
        this.api = new AnalysisResultsAPI(taskId);
        this.loadingStates = new Map();
        this.errorStates = new Map();
        
        // Set up global error handling
        this.api.addEventListener('error', this.handleError.bind(this));
        this.api.addEventListener('dataLoaded', this.handleDataLoaded.bind(this));
    }

    /**
     * Initialize the manager and load overview data
     */
    async initialize() {
        try {
            await this.loadOverview();
        } catch (error) {
            console.error('Failed to initialize analysis results:', error);
            this.showGlobalError('Failed to load analysis results. Please try refreshing the page.');
        }
    }

    /**
     * Load overview tab data
     */
    async loadOverview() {
        this.setLoading('overview', true);
        
        try {
            const summary = await this.api.getSummary();
            this.renderOverview(summary);
            this.setLoading('overview', false);
        } catch (error) {
            this.setError('overview', 'Failed to load overview data');
            this.setLoading('overview', false);
        }
    }

    /**
     * Load security tab data
     */
    async loadSecurity() {
        this.setLoading('security', true);
        
        try {
            const securityData = await this.api.getSecurityData();
            this.renderSecurity(securityData);
            this.setLoading('security', false);
        } catch (error) {
            this.setError('security', 'Failed to load security data');
            this.setLoading('security', false);
        }
    }

    /**
     * Load performance tab data
     */
    async loadPerformance() {
        this.setLoading('performance', true);
        
        try {
            const performanceData = await this.api.getPerformanceData();
            this.renderPerformance(performanceData);
            this.setLoading('performance', false);
        } catch (error) {
            this.setError('performance', 'Failed to load performance data');
            this.setLoading('performance', false);
        }
    }

    /**
     * Load quality tab data
     */
    async loadQuality() {
        this.setLoading('quality', true);
        
        try {
            const qualityData = await this.api.getQualityData();
            this.renderQuality(qualityData);
            this.setLoading('quality', false);
        } catch (error) {
            this.setError('quality', 'Failed to load quality data');
            this.setLoading('quality', false);
        }
    }

    /**
     * Load requirements tab data
     */
    async loadRequirements() {
        this.setLoading('requirements', true);
        
        try {
            const requirementsData = await this.api.getRequirementsData();
            this.renderRequirements(requirementsData);
            this.setLoading('requirements', false);
        } catch (error) {
            this.setError('requirements', 'Failed to load requirements data');
            this.setLoading('requirements', false);
        }
    }

    /**
     * Load tools tab data
     */
    async loadTools() {
        this.setLoading('tools', true);
        
        try {
            const toolsData = await this.api.getToolsData();
            this.renderTools(toolsData);
            this.setLoading('tools', false);
        } catch (error) {
            this.setError('tools', 'Failed to load tools data');
            this.setLoading('tools', false);
        }
    }

    /**
     * Set loading state for a tab
     */
    setLoading(tab, isLoading) {
        this.loadingStates.set(tab, isLoading);
        
        const tabElement = document.querySelector(`[data-tab="${tab}"]`);
        if (tabElement) {
            if (isLoading) {
                tabElement.classList.add('loading');
                this.showSpinner(tab);
            } else {
                tabElement.classList.remove('loading');
                this.hideSpinner(tab);
            }
        }
    }

    /**
     * Set error state for a tab
     */
    setError(tab, errorMessage) {
        this.errorStates.set(tab, errorMessage);
        this.showError(tab, errorMessage);
    }

    /**
     * Clear error state for a tab
     */
    clearError(tab) {
        this.errorStates.delete(tab);
        this.hideError(tab);
    }

    /**
     * Show loading spinner
     */
    showSpinner(tab) {
        const container = document.getElementById(`${tab}-content`) || 
                         document.querySelector(`[data-tab-content="${tab}"]`);
        
        if (container) {
            container.innerHTML = `
                <div class="d-flex justify-content-center align-items-center p-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading ${tab} data...</span>
                    </div>
                    <span class="ms-3">Loading ${tab} data...</span>
                </div>
            `;
        }
    }

    /**
     * Hide loading spinner
     */
    hideSpinner(tab) {
        // Spinner will be replaced by actual content in render methods
    }

    /**
     * Show error message
     */
    showError(tab, message) {
        const container = document.getElementById(`${tab}-content`) || 
                         document.querySelector(`[data-tab-content="${tab}"]`);
        
        if (container) {
            container.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <div class="d-flex align-items-center">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <div>
                            <strong>Error loading ${tab} data</strong>
                            <div class="small mt-1">${message}</div>
                        </div>
                        <button class="btn btn-sm btn-outline-danger ms-auto" onclick="analysisResults.retry('${tab}')">
                            <i class="fas fa-redo me-1"></i>Retry
                        </button>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Hide error message
     */
    hideError(tab) {
        const container = document.getElementById(`${tab}-content`) || 
                         document.querySelector(`[data-tab-content="${tab}"]`);
        
        if (container) {
            const alertElement = container.querySelector('.alert-danger');
            if (alertElement) {
                alertElement.remove();
            }
        }
    }

    /**
     * Show global error
     */
    showGlobalError(message) {
        const errorContainer = document.getElementById('global-error') || 
                              document.createElement('div');
        
        errorContainer.id = 'global-error';
        errorContainer.className = 'alert alert-danger alert-dismissible fade show';
        errorContainer.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div class="flex-grow-1">
                    <strong>Analysis Results Error</strong>
                    <div class="small mt-1">${message}</div>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // Insert at top of main content area
        const mainContent = document.querySelector('.main-content') || 
                           document.querySelector('.container-fluid') ||
                           document.body;
        
        mainContent.insertBefore(errorContainer, mainContent.firstChild);
    }

    /**
     * Retry loading data for a specific tab
     */
    async retry(tab) {
        this.clearError(tab);
        
        switch (tab) {
            case 'overview':
                await this.loadOverview();
                break;
            case 'security':
                await this.loadSecurity();
                break;
            case 'performance':
                await this.loadPerformance();
                break;
            case 'quality':
                await this.loadQuality();
                break;
            case 'requirements':
                await this.loadRequirements();
                break;
            case 'tools':
                await this.loadTools();
                break;
            default:
                console.error('Unknown tab for retry:', tab);
        }
    }

    /**
     * Handle API errors
     */
    handleError(event) {
        console.error('API Error:', event);
        
        // Could implement more sophisticated error handling here
        // such as showing user-friendly messages, retry logic, etc.
    }

    /**
     * Handle successful data loads
     */
    handleDataLoaded(event) {
        console.log('Data loaded:', event);
        // Could implement success notifications or analytics here
    }

    /**
     * Render methods for each tab
     */
    renderOverview(summary) {
        const container = document.getElementById('overview-content');
        if (!container) return;

        const html = this.createOverviewHTML(summary);
        container.innerHTML = html;
    }

    renderSecurity(securityData) {
        const container = document.getElementById('security-content');
        if (!container) return;

        const html = this.createSecurityHTML(securityData);
        container.innerHTML = html;
    }

    renderPerformance(performanceData) {
        const container = document.getElementById('performance-content');
        if (!container) return;

        const html = this.createPerformanceHTML(performanceData);
        container.innerHTML = html;
    }

    renderQuality(qualityData) {
        const container = document.getElementById('quality-content');
        if (!container) return;

        const html = this.createQualityHTML(qualityData);
        container.innerHTML = html;
    }

    renderRequirements(requirementsData) {
        const container = document.getElementById('requirements-content');
        if (!container) return;

        const html = this.createRequirementsHTML(requirementsData);
        container.innerHTML = html;
    }

    renderTools(toolsData) {
        const container = document.getElementById('tools-content');
        if (!container) return;

        const html = this.createToolsHTML(toolsData);
        container.innerHTML = html;
    }

    /**
     * HTML creation methods
     */
    createOverviewHTML(summary) {
        return `
            <!-- Task Summary -->
            <div class="row g-3 mb-4">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-info">${summary.total_findings || 0}</div>
                            <div class="text-muted small">Total Issues</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-success">${summary.tools_executed?.length || 0}</div>
                            <div class="text-muted small">Tools Run</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-primary">${summary.duration ? Math.round(summary.duration) + 's' : '-'}</div>
                            <div class="text-muted small">Duration</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 ${this.getStatusColor(summary.status)}">${this.getStatusIcon(summary.status)} ${summary.status || 'Unknown'}</div>
                            <div class="text-muted small">Status</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Summary Cards -->
            <div class="row g-3 mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6 class="card-title mb-0"><i class="fas fa-shield-halved text-danger me-2"></i>Security Summary</h6>
                        </div>
                        <div class="card-body">
                            <div class="row g-2">
                                <div class="col-6">
                                    <div class="text-center">
                                        <div class="h4 mb-0 text-danger">${summary.security?.critical_issues || 0}</div>
                                        <div class="small text-muted">Critical</div>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="text-center">
                                        <div class="h4 mb-0 text-warning">${summary.security?.high_issues || 0}</div>
                                        <div class="small text-muted">High</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6 class="card-title mb-0"><i class="fas fa-code text-info me-2"></i>Code Quality Summary</h6>
                        </div>
                        <div class="card-body">
                            <div class="row g-2">
                                <div class="col-6">
                                    <div class="text-center">
                                        <div class="h4 mb-0 text-danger">${summary.quality?.errors || 0}</div>
                                        <div class="small text-muted">Errors</div>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="text-center">
                                        <div class="h4 mb-0 text-warning">${summary.quality?.warnings || 0}</div>
                                        <div class="small text-muted">Warnings</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tools Executed -->
            <div class="card">
                <div class="card-header">
                    <h6 class="card-title mb-0">Tools Executed</h6>
                </div>
                <div class="card-body">
                    ${this.createToolBadgesHTML(summary.tools_executed || [])}
                </div>
            </div>
        `;
    }

    createSecurityHTML(securityData) {
        return `
            <!-- Security Summary Cards -->
            <div class="row g-3 mb-4">
                <div class="col-md-2">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-danger">${securityData.summary?.critical || 0}</div>
                            <div class="text-muted small">Critical</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-warning">${securityData.summary?.high || 0}</div>
                            <div class="text-muted small">High</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-info">${securityData.summary?.medium || 0}</div>
                            <div class="text-muted small">Medium</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-success">${securityData.summary?.low || 0}</div>
                            <div class="text-muted small">Low</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body py-3">
                            <div class="d-flex align-items-center">
                                <div>
                                    <div class="text-muted small">Security Tools Run</div>
                                    <div class="h6 mb-0">${securityData.tools_run?.join(', ') || 'None'}</div>
                                </div>
                                <div class="ms-auto">
                                    <i class="fas fa-tools text-muted"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Security Findings -->
            <div class="card">
                <div class="card-header">
                    <strong>Security Findings</strong>
                    <span class="badge bg-danger-lt ms-2">${securityData.summary?.total || 0}</span>
                </div>
                <div class="card-body p-0">
                    ${this.createSecurityFindingsHTML(securityData.findings || [])}
                </div>
            </div>

            <!-- Security Recommendations -->
            ${securityData.recommendations?.length ? this.createSecurityRecommendationsHTML(securityData.recommendations) : ''}
        `;
    }

    createPerformanceHTML(performanceData) {
        const metrics = performanceData.metrics || {};
        return `
            <!-- Performance Metrics -->
            <div class="row g-3 mb-4">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0">${metrics.response_time?.value || '-'}</div>
                            <div class="text-muted small">Avg Response Time (ms)</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0">${metrics.requests_per_sec?.value || '-'}</div>
                            <div class="text-muted small">Requests/sec</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0">${metrics.failed_requests?.value || '-'}</div>
                            <div class="text-muted small">Failed Requests</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0">${metrics.max_concurrent?.value || '-'}</div>
                            <div class="text-muted small">Max Concurrent</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Performance Tools -->
            <div class="card">
                <div class="card-header">
                    <strong>Performance Analysis Tools</strong>
                </div>
                <div class="card-body">
                    ${this.createPerformanceToolsHTML(performanceData.tools || {})}
                </div>
            </div>

            <!-- Performance Recommendations -->
            ${performanceData.recommendations?.length ? this.createPerformanceRecommendationsHTML(performanceData.recommendations) : ''}
        `;
    }

    createQualityHTML(qualityData) {
        const summary = qualityData.summary || {};
        return `
            <!-- Quality Summary Cards -->
            <div class="row g-3 mb-4">
                <div class="col-md-2">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-danger">${summary.errors || 0}</div>
                            <div class="text-muted small">Errors</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-warning">${summary.warnings || 0}</div>
                            <div class="text-muted small">Warnings</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-info">${summary.info || 0}</div>
                            <div class="text-muted small">Info</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-secondary">${summary.type_errors || 0}</div>
                            <div class="text-muted small">Type Errors</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body py-3">
                            <div class="h3 mb-0 text-muted">${summary.dead_code || 0}</div>
                            <div class="text-muted small">Dead Code</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quality Tools Status -->
            <div class="card mb-4">
                <div class="card-header">
                    <strong>Quality Tools Execution Status</strong>
                </div>
                <div class="card-body">
                    ${this.createQualityToolsHTML(qualityData.tools || {})}
                </div>
            </div>

            <!-- Quality Issues -->
            <div class="card">
                <div class="card-header">
                    <strong>Code Quality Issues</strong>
                    <span class="badge bg-info-lt ms-2">${qualityData.issues?.length || 0}</span>
                </div>
                <div class="card-body p-0">
                    ${this.createQualityIssuesHTML(qualityData.issues || [])}
                </div>
            </div>
        `;
    }

    createRequirementsHTML(requirementsData) {
        const summary = requirementsData.summary || {};
        return `
            <!-- Requirements Summary -->
            <div class="row g-3 mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <strong>Requirements Compliance Summary</strong>
                        </div>
                        <div class="card-body">
                            <div class="row g-2 text-center">
                                <div class="col-3">
                                    <div class="h4 mb-0 text-success">${summary.met || 0}</div>
                                    <div class="small text-muted">Met</div>
                                </div>
                                <div class="col-3">
                                    <div class="h4 mb-0 text-danger">${summary.not_met || 0}</div>
                                    <div class="small text-muted">Not Met</div>
                                </div>
                                <div class="col-3">
                                    <div class="h4 mb-0 text-warning">${summary.partial || 0}</div>
                                    <div class="small text-muted">Partial</div>
                                </div>
                                <div class="col-3">
                                    <div class="h4 mb-0 text-primary">${Math.round(summary.compliance_percentage || 0)}%</div>
                                    <div class="small text-muted">Compliance</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <strong>Analysis Details</strong>
                        </div>
                        <div class="card-body">
                            <div class="small">
                                <div><strong>Status:</strong> ${requirementsData.analysis_details?.status || 'Unknown'}</div>
                                <div><strong>Target Model:</strong> ${requirementsData.analysis_details?.target_model || 'N/A'}</div>
                                <div><strong>Total Requirements:</strong> ${summary.total_requirements || 0}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Detailed Requirements Analysis -->
            <div class="card">
                <div class="card-header">
                    <strong>Detailed Requirements Analysis</strong>
                </div>
                <div class="card-body">
                    ${requirementsData.requirements?.length ? this.createRequirementsDetailsHTML(requirementsData.requirements) : '<div class="text-center p-4 text-muted">No detailed requirements analysis available.</div>'}
                </div>
            </div>
        `;
    }

    createToolsHTML(toolsData) {
        const { tool_cards = [], summary = {}, tool_categories = {} } = toolsData;
        
        return `
            <!-- Tools Summary -->
            <div class="row g-3 mb-4">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <strong>Tool Execution Summary</strong>
                        </div>
                        <div class="card-body">
                            <div class="row g-2 text-center">
                                <div class="col-md-2 col-6">
                                    <div class="h4 mb-0 text-primary">${summary.total_tools || 0}</div>
                                    <div class="small text-muted">Total</div>
                                </div>
                                <div class="col-md-2 col-6">
                                    <div class="h4 mb-0 text-info">${summary.executed || 0}</div>
                                    <div class="small text-muted">Executed</div>
                                </div>
                                <div class="col-md-2 col-6">
                                    <div class="h4 mb-0 text-success">${summary.successful || 0}</div>
                                    <div class="small text-muted">Successful</div>
                                </div>
                                <div class="col-md-2 col-6">
                                    <div class="h4 mb-0 text-danger">${summary.failed || 0}</div>
                                    <div class="small text-muted">Failed</div>
                                </div>
                                <div class="col-md-2 col-6">
                                    <div class="h4 mb-0 text-secondary">${summary.not_available || 0}</div>
                                    <div class="small text-muted">Not Available</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <strong>Categories</strong>
                        </div>
                        <div class="card-body">
                            <div class="small">
                                <div><i class="fas fa-shield-alt text-danger me-1"></i> Security: ${tool_categories.security?.length || 0}</div>
                                <div><i class="fas fa-code text-info me-1"></i> Quality: ${tool_categories.quality?.length || 0}</div>
                                <div><i class="fas fa-tachometer-alt text-warning me-1"></i> Performance: ${tool_categories.performance?.length || 0}</div>
                                <div><i class="fas fa-network-wired text-success me-1"></i> Dynamic: ${tool_categories.dynamic?.length || 0}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tool Category Tabs -->
            <div class="card">
                <div class="card-header">
                    <ul class="nav nav-tabs card-header-tabs" role="tablist">
                        <li class="nav-item">
                            <a class="nav-link active" data-bs-toggle="tab" href="#tools-all" role="tab">All Tools</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" data-bs-toggle="tab" href="#tools-security" role="tab">Security</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" data-bs-toggle="tab" href="#tools-quality" role="tab">Quality</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" data-bs-toggle="tab" href="#tools-performance" role="tab">Performance</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" data-bs-toggle="tab" href="#tools-dynamic" role="tab">Dynamic</a>
                        </li>
                    </ul>
                </div>
                <div class="card-body">
                    <div class="tab-content">
                        <div class="tab-pane active" id="tools-all" role="tabpanel">
                            ${this.createToolCardsHTML(tool_cards)}
                        </div>
                        <div class="tab-pane" id="tools-security" role="tabpanel">
                            ${this.createToolCardsHTML(tool_cards.filter(card => card.category === 'Security'))}
                        </div>
                        <div class="tab-pane" id="tools-quality" role="tabpanel">
                            ${this.createToolCardsHTML(tool_cards.filter(card => card.category === 'Quality'))}
                        </div>
                        <div class="tab-pane" id="tools-performance" role="tabpanel">
                            ${this.createToolCardsHTML(tool_cards.filter(card => card.category === 'Performance'))}
                        </div>
                        <div class="tab-pane" id="tools-dynamic" role="tabpanel">
                            ${this.createToolCardsHTML(tool_cards.filter(card => card.category === 'Dynamic'))}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // Helper methods for creating specific HTML sections
    createToolBadgesHTML(tools) {
        if (!tools.length) return '<div class="text-muted">No tools executed</div>';
        return tools.map(tool => `<span class="badge bg-primary me-2 mb-2">${tool}</span>`).join('');
    }

    createToolCardsHTML(toolCards) {
        if (!toolCards.length) {
            return '<div class="text-center p-4 text-muted">No tools in this category</div>';
        }

        return `
            <div class="row g-3">
                ${toolCards.map(card => `
                    <div class="col-lg-4 col-md-6">
                        <div class="card card-sm h-100 tool-card" data-tool="${card.tool_name}">
                            <div class="card-status-top bg-${card.status_class}"></div>
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-2">
                                    <div class="me-3">
                                        <div class="avatar bg-${card.status_class}-lt">
                                            <i class="fas fa-${card.icon}"></i>
                                        </div>
                                    </div>
                                    <div class="flex-fill">
                                        <div class="fw-bold">${card.display_name}</div>
                                        <div class="small text-muted">${card.description}</div>
                                    </div>
                                    <div class="ms-2">
                                        <span class="badge ${card.badge_class} badge-sm">
                                            <i class="fas fa-${card.status_icon} me-1"></i>${card.status}
                                        </span>
                                    </div>
                                </div>
                                
                                <div class="row g-2 small">
                                    <div class="col-6">
                                        <div class="text-muted">Duration:</div>
                                        <div class="fw-medium">${card.duration}</div>
                                    </div>
                                    <div class="col-6">
                                        <div class="text-muted">Issues Found:</div>
                                        <div class="fw-medium ${card.total_issues > 0 ? 'text-warning' : ''}">${card.total_issues}</div>
                                    </div>
                                    ${card.exit_code !== null && card.exit_code !== undefined ? `
                                        <div class="col-6">
                                            <div class="text-muted">Exit Code:</div>
                                            <div class="fw-medium ${card.exit_code === 0 ? 'text-success' : 'text-danger'}">${card.exit_code}</div>
                                        </div>
                                    ` : ''}
                                    <div class="col-6">
                                        <div class="text-muted">Executed:</div>
                                        <div class="fw-medium">
                                            <i class="fas fa-${card.executed ? 'check text-success' : 'times text-danger'} me-1"></i>
                                            ${card.executed ? 'Yes' : 'No'}
                                        </div>
                                    </div>
                                </div>
                                
                                ${card.error_message ? `
                                    <div class="mt-2">
                                        <div class="alert alert-danger alert-sm mb-0">
                                            <i class="fas fa-exclamation-triangle me-1"></i>
                                            <strong>Error:</strong> ${card.error_message}
                                        </div>
                                    </div>
                                ` : ''}
                                
                                ${card.has_output ? `
                                    <div class="mt-2">
                                        <button class="btn btn-outline-secondary btn-sm btn-sm" onclick="showToolOutput('${card.tool_name}')">
                                            <i class="fas fa-file-alt me-1"></i>View Output
                                        </button>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    createSecurityFindingsHTML(findings) {
        if (!findings.length) {
            return '<div class="text-center p-4 text-success"><i class="fas fa-check-circle me-2"></i>No security issues found!</div>';
        }
        
        let html = '<div class="table-responsive"><table class="table table-sm table-striped mb-0">';
        html += '<thead><tr><th>Severity</th><th>Tool</th><th>Issue</th><th>File</th><th>Line</th></tr></thead><tbody>';
        
        findings.slice(0, 10).forEach(finding => { // Limit to first 10
            const severityClass = this.getSeverityClass(finding.severity);
            html += `
                <tr>
                    <td><span class="badge ${severityClass}">${finding.severity}</span></td>
                    <td><span class="badge bg-dark">${finding.tool}</span></td>
                    <td class="text-truncate" style="max-width: 300px;" title="${finding.description || finding.title}">${finding.title || finding.description}</td>
                    <td class="text-truncate" style="max-width: 200px;" title="${finding.file_path || ''}">${this.getFileName(finding.file_path)}</td>
                    <td>${finding.line_start || '-'}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        
        if (findings.length > 10) {
            html += `<div class="p-2 text-center text-muted small">Showing 10 of ${findings.length} findings</div>`;
        }
        
        return html;
    }

    createSecurityRecommendationsHTML(recommendations) {
        if (!recommendations.length) return '';
        
        let html = '<div class="card mt-4"><div class="card-header"><strong>Security Recommendations</strong></div><div class="card-body"><div class="row g-3">';
        
        recommendations.forEach(rec => {
            const alertClass = rec.severity === 'danger' ? 'alert-danger' : 
                              rec.severity === 'warning' ? 'alert-warning' : 
                              rec.severity === 'success' ? 'alert-success' : 'alert-info';
            
            html += `
                <div class="col-md-6">
                    <div class="alert ${alertClass} py-2">
                        <h6 class="alert-heading">${rec.title}</h6>
                        <p class="mb-1">${rec.message}</p>
                        <small class="text-muted">${rec.source}</small>
                    </div>
                </div>
            `;
        });
        
        html += '</div></div></div>';
        return html;
    }

    createPerformanceToolsHTML(tools) {
        if (!Object.keys(tools).length) return '<div class="text-muted">No performance tools executed</div>';
        
        let html = '<div class="row g-3">';
        Object.entries(tools).forEach(([toolName, toolData]) => {
            const statusClass = toolData.status === 'success' ? 'text-success' : 
                               toolData.status === 'error' ? 'text-danger' : 'text-muted';
            
            html += `
                <div class="col-md-4">
                    <div class="card card-sm">
                        <div class="card-body text-center">
                            <div class="h6 mb-2">${toolName}</div>
                            <div class="${statusClass}">${toolData.status}</div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        return html;
    }

    createPerformanceRecommendationsHTML(recommendations) {
        if (!recommendations.length) return '';
        
        let html = '<div class="card mt-4"><div class="card-header"><strong>Performance Recommendations</strong></div><div class="card-body"><div class="row g-3">';
        
        recommendations.forEach(rec => {
            html += `
                <div class="col-md-6">
                    <div class="alert alert-info py-2">
                        <h6 class="alert-heading">
                            ${rec.icon ? `<i class="${rec.icon} me-1"></i>` : ''}
                            ${rec.title}
                        </h6>
                        <p class="mb-0">${rec.message}</p>
                    </div>
                </div>
            `;
        });
        
        html += '</div></div></div>';
        return html;
    }

    createQualityToolsHTML(tools) {
        if (!Object.keys(tools).length) return '<div class="text-muted">No quality tools executed</div>';
        
        let html = '<div class="row g-3">';
        Object.entries(tools).forEach(([toolName, toolData]) => {
            const statusIcon = toolData.status === 'success' ? 'fas fa-check' : 
                              toolData.status === 'error' ? 'fas fa-times' : 'fas fa-question';
            const statusClass = toolData.status === 'success' ? 'text-success' : 
                               toolData.status === 'error' ? 'text-danger' : 'text-muted';
            
            html += `
                <div class="col-md-2">
                    <div class="text-center">
                        <div class="${statusClass} mb-1">
                            <i class="${statusIcon}"></i>
                        </div>
                        <div class="small fw-semibold">${toolName}</div>
                        <div class="small text-muted">${toolData.issues || 0} issues</div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        return html;
    }

    createQualityIssuesHTML(issues) {
        if (!issues.length) {
            return '<div class="text-center p-4 text-success"><i class="fas fa-check-circle me-2"></i>No quality issues found!</div>';
        }
        
        let html = '<div class="table-responsive"><table class="table table-sm table-striped mb-0">';
        html += '<thead><tr><th>Severity</th><th>Tool</th><th>Type</th><th>Message</th><th>File</th><th>Line</th></tr></thead><tbody>';
        
        issues.slice(0, 15).forEach(issue => { // Limit to first 15
            const severityClass = this.getSeverityClass(issue.severity);
            html += `
                <tr>
                    <td><span class="badge ${severityClass}">${issue.severity}</span></td>
                    <td><span class="badge bg-secondary">${issue.tool}</span></td>
                    <td>${issue.issue_type}</td>
                    <td class="text-truncate" style="max-width: 300px;" title="${issue.message}">${issue.message}</td>
                    <td class="text-truncate" style="max-width: 200px;" title="${issue.file_path || ''}">${this.getFileName(issue.file_path)}</td>
                    <td>${issue.line_number || '-'}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        
        if (issues.length > 15) {
            html += `<div class="p-2 text-center text-muted small">Showing 15 of ${issues.length} issues</div>`;
        }
        
        return html;
    }

    createRequirementsDetailsHTML(requirements) {
        if (!requirements.length) return '<div class="text-muted">No requirements data available</div>';
        
        let html = '<div class="accordion" id="requirementsAccordion">';
        
        requirements.slice(0, 10).forEach((req, index) => { // Limit to first 10
            const statusClass = req.status === 'met' ? 'text-success' : 
                               req.status === 'not_met' ? 'text-danger' : 
                               req.status === 'partial' ? 'text-warning' : 'text-muted';
            
            html += `
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#req${index}">
                            <span class="${statusClass} me-2">
                                <i class="fas ${req.status === 'met' ? 'fa-check' : req.status === 'not_met' ? 'fa-times' : 'fa-minus'}"></i>
                            </span>
                            ${req.requirement.substring(0, 100)}${req.requirement.length > 100 ? '...' : ''}
                        </button>
                    </h2>
                    <div id="req${index}" class="accordion-collapse collapse">
                        <div class="accordion-body">
                            <div><strong>Status:</strong> <span class="${statusClass}">${req.status}</span></div>
                            <div><strong>Confidence:</strong> ${Math.round(req.confidence * 100)}%</div>
                            <div><strong>Explanation:</strong> ${req.explanation}</div>
                            ${req.evidence?.length ? `<div><strong>Evidence:</strong><ul>${req.evidence.map(e => `<li>${e}</li>`).join('')}</ul></div>` : ''}
                            ${req.suggestions?.length ? `<div><strong>Suggestions:</strong><ul>${req.suggestions.map(s => `<li>${s}</li>`).join('')}</ul></div>` : ''}
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        
        if (requirements.length > 10) {
            html += `<div class="p-2 text-center text-muted small">Showing 10 of ${requirements.length} requirements</div>`;
        }
        
        return html;
    }

    // Utility methods
    getSeverityClass(severity) {
        const sev = severity?.toLowerCase();
        if (sev === 'critical') return 'bg-danger';
        if (sev === 'high') return 'bg-warning';
        if (sev === 'medium') return 'bg-info';
        if (sev === 'low') return 'bg-success';
        if (sev === 'error') return 'bg-danger';
        if (sev === 'warning') return 'bg-warning';
        return 'bg-secondary';
    }

    getStatusColor(status) {
        const st = status?.toLowerCase();
        if (st === 'completed' || st === 'success') return 'text-success';
        if (st === 'failed' || st === 'error') return 'text-danger';
        if (st === 'running') return 'text-warning';
        if (st === 'pending') return 'text-muted';
        return 'text-secondary';
    }

    getStatusIcon(status) {
        const st = status?.toLowerCase();
        if (st === 'completed' || st === 'success') return '<i class="fas fa-check"></i>';
        if (st === 'failed' || st === 'error') return '<i class="fas fa-times"></i>';
        if (st === 'running') return '<i class="fas fa-spinner fa-spin"></i>';
        if (st === 'pending') return '<i class="fas fa-clock"></i>';
        return '<i class="fas fa-question"></i>';
    }

    getFileName(filePath) {
        if (!filePath) return 'Unknown';
        return filePath.split('/').pop() || filePath;
    }
}

// Global instance (will be initialized when page loads)
let analysisResults = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('[AnalysisResults] DOM loaded, initializing...');
    
    // Get task ID from page (this would be set in the template)
    const taskIdElement = document.querySelector('[data-task-id]');
    console.log('[AnalysisResults] Task ID element:', taskIdElement);
    
    if (taskIdElement) {
        const taskId = taskIdElement.getAttribute('data-task-id');
        console.log('[AnalysisResults] Found task ID:', taskId);
        
        analysisResults = new AnalysisResultsManager(taskId);
        console.log('[AnalysisResults] Manager created, initializing...');
        analysisResults.initialize();
    } else {
        console.error('[AnalysisResults] No element with data-task-id attribute found!');
        console.log('[AnalysisResults] Looking for elements with data attributes:', 
                   document.querySelectorAll('[data-task-id], #task-data'));
    }
});