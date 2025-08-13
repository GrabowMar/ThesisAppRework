/**
 * Enhanced Results Preview Management
 */

class EnhancedResultsManager {
    constructor() {
        this.currentView = 'table';
        this.currentPage = 1;
        this.pageSize = 25;
        this.filters = {
            model: '',
            analysisType: '',
            dateRange: 'all',
            status: '',
            search: ''
        };
        this.selectedResults = new Set();
        this.allResults = [];
        this.filteredResults = [];
        this.comparisonResults = [];
        
        this.init();
    }

    init() {
        this.loadResults();
        this.setupEventListeners();
        this.initializeCharts();
        this.updateCounters();
    }

    setupEventListeners() {
        // Real-time updates
        setInterval(() => {
            this.loadResults(false); // Load without UI reset
        }, 30000); // Update every 30 seconds
    }

    async loadResults(resetUI = true) {
        try {
            const response = await fetch('/api/testing/results/enhanced?' + new URLSearchParams({
                page: this.currentPage,
                page_size: this.pageSize,
                ...this.filters
            }));
            
            const data = await response.json();
            
            if (data.success) {
                this.allResults = data.results;
                this.filteredResults = data.results;
                
                if (resetUI) {
                    this.renderResults();
                    this.updateCounters();
                    this.updatePagination(data.pagination);
                }
                
                this.updateCharts();
            }
        } catch (error) {
            console.error('Error loading results:', error);
            this.showNotification('Failed to load results', 'error');
        }
    }

    applyFilters() {
        this.filters = {
            model: document.getElementById('modelFilter').value,
            analysisType: document.getElementById('analysisTypeFilter').value,
            dateRange: document.getElementById('dateFilter').value,
            status: document.getElementById('statusFilter').value,
            search: document.getElementById('searchFilter').value
        };
        
        this.pageSize = parseInt(document.getElementById('pageSizeFilter').value);
        this.currentPage = 1;
        
        this.loadResults();
    }

    switchView(viewType) {
        this.currentView = viewType;
        
        // Hide all view containers
        document.getElementById('tableViewContainer').style.display = 'none';
        document.getElementById('cardViewContainer').style.display = 'none';
        document.getElementById('chartViewContainer').style.display = 'none';
        
        // Show selected view
        document.getElementById(`${viewType}ViewContainer`).style.display = 'block';
        
        // Render content for new view
        if (viewType === 'table') {
            this.renderTableView();
        } else if (viewType === 'card') {
            this.renderCardView();
        } else if (viewType === 'chart') {
            this.renderChartView();
        }
    }

    renderResults() {
        this.renderTableView();
        this.renderCardView();
    }

    renderTableView() {
        const tbody = document.getElementById('resultsTableBody');
        tbody.innerHTML = '';
        
        this.filteredResults.forEach(result => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <input type="checkbox" value="${result.id}" onchange="toggleResultSelection(${result.id})">
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        <img src="${this.getModelIcon(result.model_slug)}" class="me-2" width="20" height="20">
                        <span>${this.formatModelName(result.model_slug)}</span>
                    </div>
                </td>
                <td><span class="badge bg-secondary">${result.app_number}</span></td>
                <td>
                    <span class="badge ${this.getAnalysisTypeBadgeClass(result.analysis_type)}">
                        ${this.formatAnalysisType(result.analysis_type)}
                    </span>
                </td>
                <td>${this.renderStatusBadge(result.status)}</td>
                <td>${this.renderScoreBadge(result.score)}</td>
                <td>${this.formatDuration(result.duration)}</td>
                <td>
                    <small class="text-muted">${this.formatRelativeTime(result.started_at)}</small>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary btn-sm" onclick="viewResultDetail(${result.id})" title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-outline-success btn-sm" onclick="downloadResult(${result.id})" title="Download">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="btn btn-outline-info btn-sm" onclick="addToComparison(${result.id})" title="Compare">
                            <i class="fas fa-balance-scale"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    renderCardView() {
        const container = document.getElementById('resultsCardsContainer');
        container.innerHTML = '';
        
        this.filteredResults.forEach(result => {
            const col = document.createElement('div');
            col.className = 'col-md-6 col-lg-4 mb-3';
            
            col.innerHTML = `
                <div class="card h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <img src="${this.getModelIcon(result.model_slug)}" class="me-2" width="24" height="24">
                            <strong>${this.formatModelName(result.model_slug)}</strong>
                        </div>
                        <span class="badge bg-secondary">App ${result.app_number}</span>
                    </div>
                    <div class="card-body">
                        <div class="mb-2">
                            <span class="badge ${this.getAnalysisTypeBadgeClass(result.analysis_type)}">
                                ${this.formatAnalysisType(result.analysis_type)}
                            </span>
                            ${this.renderStatusBadge(result.status)}
                        </div>
                        <div class="mb-3">
                            <div class="d-flex justify-content-between">
                                <span>Score:</span>
                                ${this.renderScoreBadge(result.score)}
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>Duration:</span>
                                <span>${this.formatDuration(result.duration)}</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>Started:</span>
                                <small class="text-muted">${this.formatRelativeTime(result.started_at)}</small>
                            </div>
                        </div>
                    </div>
                    <div class="card-footer">
                        <div class="d-grid gap-2 d-md-flex justify-content-md-center">
                            <button class="btn btn-primary btn-sm" onclick="viewResultDetail(${result.id})">
                                <i class="fas fa-eye me-1"></i>View
                            </button>
                            <button class="btn btn-success btn-sm" onclick="downloadResult(${result.id})">
                                <i class="fas fa-download me-1"></i>Download
                            </button>
                            <button class="btn btn-info btn-sm" onclick="addToComparison(${result.id})">
                                <i class="fas fa-plus me-1"></i>Compare
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            container.appendChild(col);
        });
    }

    renderChartView() {
        // Update charts with current data
        this.updateCharts();
    }

    initializeCharts() {
        // Initialize Chart.js charts
        this.statusChart = new Chart(document.getElementById('statusChart'), {
            type: 'doughnut',
            data: {
                labels: ['Success', 'Running', 'Failed'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#28a745', '#ffc107', '#dc3545']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Test Status Distribution'
                    }
                }
            }
        });

        this.scoreChart = new Chart(document.getElementById('scoreChart'), {
            type: 'bar',
            data: {
                labels: ['0-20', '21-40', '41-60', '61-80', '81-100'],
                datasets: [{
                    label: 'Score Distribution',
                    data: [0, 0, 0, 0, 0],
                    backgroundColor: '#007bff'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Score Distribution'
                    }
                }
            }
        });

        this.timelineChart = new Chart(document.getElementById('timelineChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Tests Over Time',
                    data: [],
                    borderColor: '#007bff',
                    fill: false
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Testing Activity Timeline'
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day'
                        }
                    }
                }
            }
        });
    }

    updateCharts() {
        if (!this.filteredResults.length) return;

        // Update status chart
        const statusCounts = this.getStatusCounts();
        this.statusChart.data.datasets[0].data = [
            statusCounts.success,
            statusCounts.running,
            statusCounts.failed
        ];
        this.statusChart.update();

        // Update score chart
        const scoreBuckets = this.getScoreBuckets();
        this.scoreChart.data.datasets[0].data = scoreBuckets;
        this.scoreChart.update();

        // Update timeline chart
        const timelineData = this.getTimelineData();
        this.timelineChart.data.labels = timelineData.labels;
        this.timelineChart.data.datasets[0].data = timelineData.data;
        this.timelineChart.update();
    }

    getStatusCounts() {
        return this.filteredResults.reduce((counts, result) => {
            counts[result.status] = (counts[result.status] || 0) + 1;
            return counts;
        }, { success: 0, running: 0, failed: 0 });
    }

    getScoreBuckets() {
        const buckets = [0, 0, 0, 0, 0];
        this.filteredResults.forEach(result => {
            if (result.score !== null) {
                const bucketIndex = Math.min(Math.floor(result.score / 20), 4);
                buckets[bucketIndex]++;
            }
        });
        return buckets;
    }

    getTimelineData() {
        const grouped = {};
        this.filteredResults.forEach(result => {
            const date = new Date(result.started_at).toDateString();
            grouped[date] = (grouped[date] || 0) + 1;
        });
        
        return {
            labels: Object.keys(grouped).sort(),
            data: Object.keys(grouped).sort().map(date => grouped[date])
        };
    }

    updateCounters() {
        if (!this.filteredResults.length) return;

        const counts = this.getStatusCounts();
        
        document.getElementById('totalTestsCount').textContent = this.filteredResults.length;
        document.getElementById('completedTestsCount').textContent = counts.success || 0;
        document.getElementById('runningTestsCount').textContent = counts.running || 0;
        document.getElementById('failedTestsCount').textContent = counts.failed || 0;
    }

    updatePagination(pagination) {
        const container = document.getElementById('resultsPagination');
        container.innerHTML = '';

        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${pagination.current_page === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#" onclick="changePage(${pagination.current_page - 1})">Previous</a>`;
        container.appendChild(prevLi);

        // Page numbers
        for (let i = Math.max(1, pagination.current_page - 2); 
             i <= Math.min(pagination.total_pages, pagination.current_page + 2); 
             i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === pagination.current_page ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#" onclick="changePage(${i})">${i}</a>`;
            container.appendChild(li);
        }

        // Next button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${pagination.current_page === pagination.total_pages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#" onclick="changePage(${pagination.current_page + 1})">Next</a>`;
        container.appendChild(nextLi);

        // Update results info
        const start = (pagination.current_page - 1) * pagination.per_page + 1;
        const end = Math.min(start + pagination.per_page - 1, pagination.total);
        document.getElementById('resultsInfo').textContent = 
            `Showing ${start}-${end} of ${pagination.total} results`;
    }

    // Helper methods for formatting
    getModelIcon(modelSlug) {
        const icons = {
            'anthropic_claude': '/static/images/claude-icon.png',
            'openai_gpt': '/static/images/openai-icon.png',
            'google_gemini': '/static/images/gemini-icon.png',
            'meta_llama': '/static/images/llama-icon.png'
        };
        
        const prefix = modelSlug.split('_')[0] + '_' + modelSlug.split('_')[1].split('-')[0];
        return icons[prefix] || '/static/images/default-model-icon.png';
    }

    formatModelName(modelSlug) {
        return modelSlug.replace(/_/g, ' ').replace(/-/g, ' ').split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }

    getAnalysisTypeBadgeClass(type) {
        const classes = {
            'security': 'bg-danger',
            'performance': 'bg-warning',
            'ai_analysis': 'bg-info',
            'static_analysis': 'bg-success'
        };
        return classes[type] || 'bg-secondary';
    }

    formatAnalysisType(type) {
        return type.replace(/_/g, ' ').split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }

    renderStatusBadge(status) {
        const badges = {
            'success': '<span class="badge bg-success">Completed</span>',
            'running': '<span class="badge bg-warning">Running</span>',
            'failed': '<span class="badge bg-danger">Failed</span>',
            'pending': '<span class="badge bg-secondary">Pending</span>'
        };
        return badges[status] || '<span class="badge bg-light">Unknown</span>';
    }

    renderScoreBadge(score) {
        if (score === null || score === undefined) {
            return '<span class="badge bg-light">N/A</span>';
        }
        
        let badgeClass = 'bg-secondary';
        if (score >= 80) badgeClass = 'bg-success';
        else if (score >= 60) badgeClass = 'bg-info';
        else if (score >= 40) badgeClass = 'bg-warning';
        else badgeClass = 'bg-danger';
        
        return `<span class="badge ${badgeClass}">${score}%</span>`;
    }

    formatDuration(duration) {
        if (!duration) return 'N/A';
        
        const seconds = Math.floor(duration);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }

    formatRelativeTime(timestamp) {
        const now = new Date();
        const date = new Date(timestamp);
        const diffMs = now - date;
        const diffHours = diffMs / (1000 * 60 * 60);
        const diffDays = diffHours / 24;
        
        if (diffHours < 1) {
            const diffMinutes = Math.floor(diffMs / (1000 * 60));
            return `${diffMinutes}m ago`;
        } else if (diffHours < 24) {
            return `${Math.floor(diffHours)}h ago`;
        } else if (diffDays < 7) {
            return `${Math.floor(diffDays)}d ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    async viewResultDetail(resultId) {
        try {
            const response = await fetch(`/api/testing/results/${resultId}/detail`);
            const data = await response.json();
            
            if (data.success) {
                this.populateDetailModal(data.result);
                const modal = new bootstrap.Modal(document.getElementById('resultDetailModal'));
                modal.show();
            }
        } catch (error) {
            this.showNotification('Failed to load result details', 'error');
        }
    }

    populateDetailModal(result) {
        // Populate summary
        document.getElementById('resultSummaryContent').innerHTML = this.generateSummaryHTML(result);
        
        // Populate details
        document.getElementById('resultDetailsContent').innerHTML = this.generateDetailsHTML(result);
        
        // Populate raw data
        document.getElementById('resultRawContent').innerHTML = `<pre><code>${JSON.stringify(result, null, 2)}</code></pre>`;
        
        // Populate configuration
        document.getElementById('resultConfigContent').innerHTML = this.generateConfigHTML(result.config);
        
        // Populate metadata
        document.getElementById('resultMetadata').innerHTML = this.generateMetadataHTML(result);
    }

    generateSummaryHTML(result) {
        return `
            <div class="row">
                <div class="col-md-6">
                    <h6>Test Overview</h6>
                    <table class="table table-sm">
                        <tr><td>Model:</td><td>${this.formatModelName(result.model_slug)}</td></tr>
                        <tr><td>Application:</td><td>#${result.app_number}</td></tr>
                        <tr><td>Analysis Type:</td><td>${this.formatAnalysisType(result.analysis_type)}</td></tr>
                        <tr><td>Status:</td><td>${this.renderStatusBadge(result.status)}</td></tr>
                        <tr><td>Score:</td><td>${this.renderScoreBadge(result.score)}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Performance Metrics</h6>
                    <table class="table table-sm">
                        <tr><td>Duration:</td><td>${this.formatDuration(result.duration)}</td></tr>
                        <tr><td>Started:</td><td>${new Date(result.started_at).toLocaleString()}</td></tr>
                        <tr><td>Completed:</td><td>${result.completed_at ? new Date(result.completed_at).toLocaleString() : 'N/A'}</td></tr>
                        <tr><td>Files Analyzed:</td><td>${result.files_analyzed || 'N/A'}</td></tr>
                    </table>
                </div>
            </div>
        `;
    }

    generateDetailsHTML(result) {
        // Generate detailed analysis results based on type
        return `<div class="alert alert-info">Detailed analysis results will be displayed here based on the analysis type.</div>`;
    }

    generateConfigHTML(config) {
        return `<pre><code>${JSON.stringify(config, null, 2)}</code></pre>`;
    }

    generateMetadataHTML(result) {
        return `
            <table class="table table-sm">
                <tr><td>ID:</td><td>${result.id}</td></tr>
                <tr><td>Version:</td><td>${result.version || 'N/A'}</td></tr>
                <tr><td>Service:</td><td>${result.service || 'N/A'}</td></tr>
                <tr><td>Task ID:</td><td>${result.task_id || 'N/A'}</td></tr>
            </table>
        `;
    }

    showNotification(message, type = 'info') {
        // Create notification (similar to config manager)
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    async loadComparisonData() {
        try {
            const ids = Array.from(this.comparisonResults);
            const response = await fetch('/api/testing/results/comparison?' + ids.map(id => `ids=${id}`).join('&'));
            const data = await response.json();
            
            if (data.success) {
                this.renderComparisonView(data.results, data.insights);
            } else {
                this.showNotification('Failed to load comparison data', 'error');
            }
        } catch (error) {
            console.error('Error loading comparison data:', error);
            this.showNotification('Failed to load comparison data', 'error');
        }
    }

    renderComparisonView(results, insights) {
        const container = document.getElementById('comparisonContent');
        
        // Create comparison dashboard
        container.innerHTML = `
            <div class="row mb-4">
                <div class="col-12">
                    <h5>Comparing ${results.length} Results</h5>
                    <div class="d-flex flex-wrap gap-2 mb-3">
                        ${results.map(result => `
                            <span class="badge bg-primary fs-6">
                                ${this.formatModelName(result.model_slug)} App ${result.app_number} 
                                (${this.formatAnalysisType(result.analysis_type)})
                            </span>
                        `).join('')}
                    </div>
                </div>
            </div>
            
            <!-- Comparison Charts -->
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6>Score Comparison</h6>
                        </div>
                        <div class="card-body">
                            <canvas id="comparisonScoreChart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6>Performance Comparison</h6>
                        </div>
                        <div class="card-body">
                            <canvas id="comparisonDurationChart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Detailed Comparison Table -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h6>Detailed Comparison</h6>
                        </div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Metric</th>
                                            ${results.map((result, index) => 
                                                `<th>Result ${index + 1}</th>`
                                            ).join('')}
                                            <th>Best</th>
                                            <th>Variance</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${this.generateComparisonRows(results)}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Statistical Analysis -->
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6>Statistical Summary</h6>
                        </div>
                        <div class="card-body">
                            ${this.generateStatisticalSummary(results, insights)}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6>Key Insights</h6>
                        </div>
                        <div class="card-body">
                            ${this.generateKeyInsights(results, insights)}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Export Options -->
            <div class="row">
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex gap-2">
                                <button class="btn btn-primary" onclick="exportComparisonReport()">
                                    <i class="fas fa-file-pdf me-1"></i>Export PDF Report
                                </button>
                                <button class="btn btn-success" onclick="exportComparisonData()">
                                    <i class="fas fa-file-excel me-1"></i>Export Excel Data
                                </button>
                                <button class="btn btn-info" onclick="shareComparison()">
                                    <i class="fas fa-share me-1"></i>Share Comparison
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Initialize comparison charts
        this.initializeComparisonCharts(results);
    }

    generateComparisonRows(results) {
        const metrics = [
            { key: 'score', label: 'Score (%)', format: (val) => val !== null ? `${val}%` : 'N/A' },
            { key: 'duration', label: 'Duration', format: (val) => this.formatDuration(val) },
            { key: 'status', label: 'Status', format: (val) => val },
            { key: 'analysis_type', label: 'Analysis Type', format: (val) => this.formatAnalysisType(val) },
            { key: 'model_slug', label: 'Model', format: (val) => this.formatModelName(val) }
        ];
        
        return metrics.map(metric => {
            const values = results.map(result => result[metric.key]);
            const numericValues = values.filter(v => typeof v === 'number' && !isNaN(v));
            
            let bestValue = 'N/A';
            let variance = 'N/A';
            
            if (numericValues.length > 0) {
                if (metric.key === 'score') {
                    bestValue = `${Math.max(...numericValues)}%`;
                } else if (metric.key === 'duration') {
                    bestValue = this.formatDuration(Math.min(...numericValues));
                }
                
                if (numericValues.length > 1) {
                    const mean = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
                    const squaredDiffs = numericValues.map(value => Math.pow(value - mean, 2));
                    const variance_calc = Math.sqrt(squaredDiffs.reduce((a, b) => a + b, 0) / numericValues.length);
                    variance = variance_calc.toFixed(2);
                }
            }
            
            return `
                <tr>
                    <td><strong>${metric.label}</strong></td>
                    ${values.map(value => `<td>${metric.format(value)}</td>`).join('')}
                    <td><span class="badge bg-success">${bestValue}</span></td>
                    <td>${variance}</td>
                </tr>
            `;
        }).join('');
    }

    generateStatisticalSummary(results, insights) {
        const scoreStats = this.calculateStats(insights.score_comparison);
        const durationStats = this.calculateStats(insights.duration_comparison);
        
        return `
            <div class="row">
                <div class="col-12 mb-3">
                    <h6>Score Statistics</h6>
                    <table class="table table-sm">
                        <tr><td>Average:</td><td>${scoreStats.mean.toFixed(1)}%</td></tr>
                        <tr><td>Median:</td><td>${scoreStats.median.toFixed(1)}%</td></tr>
                        <tr><td>Range:</td><td>${scoreStats.min.toFixed(1)}% - ${scoreStats.max.toFixed(1)}%</td></tr>
                        <tr><td>Std Dev:</td><td>${scoreStats.stdDev.toFixed(1)}</td></tr>
                    </table>
                </div>
                <div class="col-12">
                    <h6>Duration Statistics</h6>
                    <table class="table table-sm">
                        <tr><td>Average:</td><td>${this.formatDuration(durationStats.mean)}</td></tr>
                        <tr><td>Median:</td><td>${this.formatDuration(durationStats.median)}</td></tr>
                        <tr><td>Range:</td><td>${this.formatDuration(durationStats.min)} - ${this.formatDuration(durationStats.max)}</td></tr>
                    </table>
                </div>
            </div>
        `;
    }

    generateKeyInsights(results, insights) {
        const insights_list = [];
        
        // Score insights
        if (insights.score_comparison.length > 0) {
            const maxScore = Math.max(...insights.score_comparison);
            const minScore = Math.min(...insights.score_comparison);
            const scoreDiff = maxScore - minScore;
            
            if (scoreDiff > 20) {
                insights_list.push(`<li class="text-warning">High score variance (${scoreDiff.toFixed(1)}%) indicates significant quality differences</li>`);
            } else if (scoreDiff < 5) {
                insights_list.push(`<li class="text-success">Low score variance (${scoreDiff.toFixed(1)}%) indicates consistent quality</li>`);
            }
        }
        
        // Duration insights
        if (insights.duration_comparison.length > 0) {
            const maxDuration = Math.max(...insights.duration_comparison);
            const minDuration = Math.min(...insights.duration_comparison);
            const ratio = maxDuration / minDuration;
            
            if (ratio > 3) {
                insights_list.push(`<li class="text-info">Performance varies significantly (${ratio.toFixed(1)}x difference)</li>`);
            } else if (ratio < 1.5) {
                insights_list.push(`<li class="text-success">Consistent performance across results</li>`);
            }
        }
        
        // Model insights
        if (insights.model_comparison.length > 1) {
            insights_list.push(`<li class="text-info">Comparing ${insights.model_comparison.length} different models</li>`);
        }
        
        // Analysis type insights
        if (insights.analysis_types.length > 1) {
            insights_list.push(`<li class="text-info">Multi-dimensional analysis across ${insights.analysis_types.length} types</li>`);
        }
        
        if (insights_list.length === 0) {
            insights_list.push(`<li class="text-muted">No significant patterns detected in this comparison</li>`);
        }
        
        return `<ul class="list-unstyled">${insights_list.join('')}</ul>`;
    }

    calculateStats(values) {
        if (values.length === 0) return { mean: 0, median: 0, min: 0, max: 0, stdDev: 0 };
        
        const sorted = [...values].sort((a, b) => a - b);
        const mean = values.reduce((a, b) => a + b, 0) / values.length;
        const median = sorted[Math.floor(sorted.length / 2)];
        const min = sorted[0];
        const max = sorted[sorted.length - 1];
        
        const squaredDiffs = values.map(value => Math.pow(value - mean, 2));
        const stdDev = Math.sqrt(squaredDiffs.reduce((a, b) => a + b, 0) / values.length);
        
        return { mean, median, min, max, stdDev };
    }

    initializeComparisonCharts(results) {
        // Score comparison chart
        const scoreChart = new Chart(document.getElementById('comparisonScoreChart'), {
            type: 'bar',
            data: {
                labels: results.map((result, index) => `Result ${index + 1}`),
                datasets: [{
                    label: 'Score (%)',
                    data: results.map(result => result.score || 0),
                    backgroundColor: results.map((result, index) => {
                        const colors = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6f42c1'];
                        return colors[index % colors.length];
                    })
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });

        // Duration comparison chart
        const durationChart = new Chart(document.getElementById('comparisonDurationChart'), {
            type: 'line',
            data: {
                labels: results.map((result, index) => `Result ${index + 1}`),
                datasets: [{
                    label: 'Duration (seconds)',
                    data: results.map(result => result.duration || 0),
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// Global functions for template usage
function refreshResults() {
    if (window.resultsManager) {
        window.resultsManager.loadResults();
    }
}

function applyFilters() {
    if (window.resultsManager) {
        window.resultsManager.applyFilters();
    }
}

function switchView(viewType) {
    if (window.resultsManager) {
        window.resultsManager.switchView(viewType);
    }
}

function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('input[type="checkbox"][value]');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll.checked;
        if (selectAll.checked) {
            window.resultsManager?.selectedResults.add(parseInt(checkbox.value));
        } else {
            window.resultsManager?.selectedResults.delete(parseInt(checkbox.value));
        }
    });
}

function toggleResultSelection(resultId) {
    if (window.resultsManager) {
        if (window.resultsManager.selectedResults.has(resultId)) {
            window.resultsManager.selectedResults.delete(resultId);
        } else {
            window.resultsManager.selectedResults.add(resultId);
        }
    }
}

function changePage(page) {
    if (window.resultsManager) {
        window.resultsManager.currentPage = page;
        window.resultsManager.loadResults();
    }
}

function viewResultDetail(resultId) {
    if (window.resultsManager) {
        window.resultsManager.viewResultDetail(resultId);
    }
}

function downloadResult(resultId) {
    window.open(`/api/testing/results/${resultId}/download`, '_blank');
}

function addToComparison(resultId) {
    if (window.resultsManager) {
        window.resultsManager.comparisonResults.push(resultId);
        window.resultsManager.showNotification('Added to comparison', 'success');
    }
}

function exportAllResults() {
    if (window.resultsManager) {
        const selectedIds = Array.from(window.resultsManager.selectedResults);
        if (selectedIds.length === 0) {
            window.resultsManager.showNotification('Please select results to export', 'warning');
            return;
        }
        
        const url = '/api/testing/results/export?' + selectedIds.map(id => `ids=${id}`).join('&');
        window.open(url, '_blank');
    }
}

function showComparisonView() {
    if (window.resultsManager) {
        if (window.resultsManager.comparisonResults.length === 0) {
            window.resultsManager.showNotification('Please add results to comparison first', 'warning');
            return;
        }
        
        // Load comparison data and show modal
        window.resultsManager.loadComparisonData();
        const modal = new bootstrap.Modal(document.getElementById('comparisonModal'));
        modal.show();
    }
}

function exportComparisonReport() {
    if (window.resultsManager) {
        const ids = Array.from(window.resultsManager.comparisonResults);
        if (ids.length === 0) {
            window.resultsManager.showNotification('No results in comparison', 'warning');
            return;
        }
        
        // TODO: Implement PDF export functionality
        window.resultsManager.showNotification('PDF export functionality coming soon', 'info');
    }
}

function exportComparisonData() {
    if (window.resultsManager) {
        const ids = Array.from(window.resultsManager.comparisonResults);
        if (ids.length === 0) {
            window.resultsManager.showNotification('No results in comparison', 'warning');
            return;
        }
        
        const url = '/api/testing/results/export?' + ids.map(id => `ids=${id}`).join('&');
        window.open(url, '_blank');
    }
}

function shareComparison() {
    if (window.resultsManager) {
        const ids = Array.from(window.resultsManager.comparisonResults);
        if (ids.length === 0) {
            window.resultsManager.showNotification('No results in comparison', 'warning');
            return;
        }
        
        // Create shareable URL
        const baseUrl = window.location.origin + window.location.pathname;
        const shareUrl = `${baseUrl}?compare=${ids.join(',')}`;
        
        // Copy to clipboard
        navigator.clipboard.writeText(shareUrl).then(() => {
            window.resultsManager.showNotification('Comparison URL copied to clipboard', 'success');
        }).catch(() => {
            window.resultsManager.showNotification('Failed to copy URL to clipboard', 'error');
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('resultsTable')) {
        window.resultsManager = new EnhancedResultsManager();
    }
});
