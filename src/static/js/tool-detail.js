/**
 * Tool Detail Modal - Dynamic loading and interaction for analysis tool details
 * Handles AJAX loading, pagination, filtering, and SARIF viewing
 */

class ToolDetailModal {
    constructor() {
        this.modal = null;
        this.bsModal = null; // Store Bootstrap modal instance
        this.currentToolData = null;
        this.currentPage = 1;
        this.itemsPerPage = 25;
        this.currentFilter = '';
        this.resultId = null;
        this.toolName = null;
        this.serviceType = null;
        
        this.init();
    }
    
    init() {
        // Get modal element
        this.modal = document.getElementById('toolDetailModal');
        if (!this.modal) {
            console.warn('Tool detail modal not found in DOM');
            return;
        }
        
        // Initialize Bootstrap modal instance once
        this.bsModal = new bootstrap.Modal(this.modal, {
            backdrop: true,
            keyboard: true,
            focus: true
        });
        
        // Attach event listeners
        this.attachEventListeners();
        
        // Handle URL hash navigation
        this.handleHashNavigation();
    }
    
    attachEventListeners() {
        // Severity filter
        const severityFilter = document.getElementById('severity-filter');
        if (severityFilter) {
            severityFilter.addEventListener('change', (e) => {
                this.currentFilter = e.target.value;
                this.currentPage = 1;
                this.renderIssuesTable();
            });
        }
        
        // Export button
        const exportBtn = document.getElementById('export-issues-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportToCSV());
        }
        
        // SARIF preview toggle
        const sarifToggle = document.getElementById('sarif-preview-toggle');
        if (sarifToggle) {
            sarifToggle.addEventListener('click', () => this.toggleSARIFPreview());
        }
        
        // Hash change for deep linking
        window.addEventListener('hashchange', () => this.handleHashNavigation());
    }
    
    /**
     * Open modal with tool data
     * @param {Object} options - { resultId, toolName, serviceType, toolData }
     */
    async openModal(options) {
        this.resultId = options.resultId;
        this.toolName = options.toolName;
        this.serviceType = options.serviceType;
        this.currentPage = 1;
        this.currentFilter = '';
        
        // Show loading state first
        this.showLoading();
        
        // Show modal using stored instance
        if (this.bsModal) {
            this.bsModal.show();
        }
        
        // Load tool data (either from embedded data or AJAX)
        if (options.toolData) {
            // Data already provided (embedded in page)
            this.currentToolData = options.toolData;
            this.renderToolDetails();
        } else {
            // Fetch from API
            await this.fetchToolDetails();
        }
        
        // Update URL hash for deep linking
        if (this.toolName) {
            window.location.hash = `tool-${this.toolName.toLowerCase()}`;
        }
    }
    
    showLoading() {
        document.getElementById('modal-loading').classList.remove('d-none');
        document.getElementById('modal-error').classList.add('d-none');
        document.getElementById('modal-content').classList.add('d-none');
    }
    
    showError(message) {
        document.getElementById('modal-loading').classList.add('d-none');
        document.getElementById('modal-error').classList.remove('d-none');
        document.getElementById('modal-error-message').textContent = message;
        document.getElementById('modal-content').classList.add('d-none');
    }
    
    showContent() {
        document.getElementById('modal-loading').classList.add('d-none');
        document.getElementById('modal-error').classList.add('d-none');
        document.getElementById('modal-content').classList.remove('d-none');
    }
    
    async fetchToolDetails() {
        try {
            const url = `/api/analysis/results/${this.resultId}/tools/${this.toolName}?service=${this.serviceType}`;
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.currentToolData = data.data;
                this.renderToolDetails();
            } else {
                this.showError(data.message || 'Failed to load tool details');
            }
        } catch (error) {
            console.error('Error fetching tool details:', error);
            this.showError(`Failed to load tool details: ${error.message}`);
        }
    }
    
    renderToolDetails() {
        if (!this.currentToolData) {
            this.showError('No tool data available');
            return;
        }
        
        // Update modal title
        document.getElementById('modal-tool-name').textContent = 
            this.currentToolData.tool_name || this.toolName || 'Tool Details';
        document.getElementById('modal-tool-subtitle').textContent = 
            `${this.serviceType || 'Analysis'} • ${this.currentToolData.language || ''}`;
        
        // Render metadata
        this.renderMetadata();
        
        // Render severity summary (if applicable)
        this.renderSeveritySummary();
        
        // Render performance metrics (if applicable)
        this.renderPerformanceMetrics();
        
        // Render issues table
        this.renderIssuesTable();
        
        // Render SARIF section
        this.renderSARIFSection();
        
        // Render configuration
        this.renderConfiguration();
        
        this.showContent();
    }
    
    renderMetadata() {
        const data = this.currentToolData;
        
        // Status
        const statusHtml = this.getStatusBadge(data.status);
        document.getElementById('meta-status').innerHTML = statusHtml;
        
        // Execution time
        const execTime = data.execution_time || data.exec_time || '—';
        document.getElementById('meta-exec-time').textContent = 
            typeof execTime === 'number' ? `${execTime.toFixed(2)}s` : execTime;
        
        // Total issues
        const totalIssues = data.total_issues || data.issue_count || 
                           (data.issues ? data.issues.length : 0);
        document.getElementById('meta-total-issues').textContent = totalIssues;
        
        // Exit code
        const exitCode = data.exit_code !== undefined ? data.exit_code : '—';
        document.getElementById('meta-exit-code').textContent = exitCode;
        
        // Additional metadata
        const additionalContainer = document.getElementById('meta-additional');
        additionalContainer.innerHTML = '';
        
        // Add tool-specific metadata
        if (data.files_scanned) {
            this.addMetadataItem(additionalContainer, 'Files Scanned', data.files_scanned);
        }
        if (data.lines_analyzed) {
            this.addMetadataItem(additionalContainer, 'Lines Analyzed', data.lines_analyzed.toLocaleString());
        }
        if (data.version) {
            this.addMetadataItem(additionalContainer, 'Tool Version', data.version);
        }
    }
    
    addMetadataItem(container, label, value) {
        const col = document.createElement('div');
        col.className = 'col-md-3';
        col.innerHTML = `
            <div class="text-muted small text-uppercase mb-1">${label}</div>
            <div>${value}</div>
        `;
        container.appendChild(col);
    }
    
    renderSeveritySummary() {
        const data = this.currentToolData;
        const card = document.getElementById('severity-summary-card');
        const container = document.getElementById('severity-breakdown');
        
        if (!data.issues || data.issues.length === 0) {
            card.classList.add('d-none');
            return;
        }
        
        // Count issues by severity
        const severityCounts = {};
        data.issues.forEach(issue => {
            const severity = (issue.issue_severity || issue.severity || 'UNKNOWN').toUpperCase();
            severityCounts[severity] = (severityCounts[severity] || 0) + 1;
        });
        
        if (Object.keys(severityCounts).length === 0) {
            card.classList.add('d-none');
            return;
        }
        
        // Render severity breakdown
        container.innerHTML = '';
        const severityOrder = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
        
        severityOrder.forEach(severity => {
            if (severityCounts[severity]) {
                const col = document.createElement('div');
                col.className = 'col-md-2';
                const badgeClass = this.getSeverityBadgeClass(severity);
                col.innerHTML = `
                    <div class="text-muted small text-uppercase mb-1">${severity}</div>
                    <div class="h4 mb-0">
                        <span class="badge ${badgeClass} fs-5">${severityCounts[severity]}</span>
                    </div>
                `;
                container.appendChild(col);
            }
        });
        
        card.classList.remove('d-none');
    }
    
    renderPerformanceMetrics() {
        const data = this.currentToolData;
        const card = document.getElementById('performance-metrics-card');
        const container = document.getElementById('performance-metrics');
        
        // Check if this is a performance tool
        const hasMetrics = data.avg_response_time || data.requests_per_second || 
                          data.throughput || data.success_rate;
        
        if (!hasMetrics) {
            card.classList.add('d-none');
            return;
        }
        
        container.innerHTML = '';
        
        if (data.avg_response_time) {
            this.addMetadataItem(container, 'Avg Response Time', `${data.avg_response_time.toFixed(2)} ms`);
        }
        if (data.requests_per_second || data.throughput) {
            const rps = data.requests_per_second || data.throughput;
            this.addMetadataItem(container, 'Throughput', `${rps.toFixed(2)} req/s`);
        }
        if (data.success_rate !== undefined) {
            this.addMetadataItem(container, 'Success Rate', `${data.success_rate.toFixed(1)}%`);
        }
        if (data.requests || data.completed_requests) {
            const total = data.requests || data.completed_requests;
            const failed = data.failed_requests || 0;
            this.addMetadataItem(container, 'Total Requests', `${total} (${failed} failed)`);
        }
        
        card.classList.remove('d-none');
    }
    
    renderIssuesTable() {
        const data = this.currentToolData;
        const tbody = document.getElementById('issues-table-body');
        const issuesCard = document.getElementById('issues-card');
        
        if (!data.issues || data.issues.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No issues found</td></tr>';
            document.getElementById('issues-count-badge').textContent = '0';
            this.updatePaginationInfo(0, 0, 0);
            return;
        }
        
        // Filter issues
        let filteredIssues = data.issues;
        if (this.currentFilter) {
            filteredIssues = data.issues.filter(issue => {
                const severity = (issue.issue_severity || issue.severity || '').toUpperCase();
                return severity === this.currentFilter;
            });
        }
        
        // Update count badge
        document.getElementById('issues-count-badge').textContent = filteredIssues.length;
        
        // Paginate
        const start = (this.currentPage - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        const paginatedIssues = filteredIssues.slice(start, end);
        
        // Render rows
        tbody.innerHTML = '';
        paginatedIssues.forEach(issue => {
            const row = this.createIssueRow(issue);
            tbody.appendChild(row);
        });
        
        // Update pagination
        this.updatePaginationInfo(start + 1, Math.min(end, filteredIssues.length), filteredIssues.length);
        this.renderPaginationControls(filteredIssues.length);
    }
    
    createIssueRow(issue) {
        const tr = document.createElement('tr');
        
        // Severity
        const severity = (issue.issue_severity || issue.severity || 'INFO').toUpperCase();
        const severityBadge = `<span class="badge ${this.getSeverityBadgeClass(severity)}">${severity}</span>`;
        
        // Rule/Type
        const rule = issue.test_id || issue.rule_id || issue.type || '—';
        
        // File path (truncate if too long)
        const file = issue.filename || issue.file || issue.location || '—';
        const fileShort = file.length > 30 ? '...' + file.slice(-27) : file;
        
        // Line number
        const line = issue.line_number || issue.line || '—';
        
        // Description
        const description = issue.issue_text || issue.message || issue.description || 'No description';
        
        // CWE
        const cwe = issue.issue_cwe || issue.cwe || '—';
        
        tr.innerHTML = `
            <td>${severityBadge}</td>
            <td><code class="small">${this.escapeHtml(rule)}</code></td>
            <td><span class="small text-muted" title="${this.escapeHtml(file)}">${this.escapeHtml(fileShort)}</span></td>
            <td class="text-center">${line}</td>
            <td class="small">${this.escapeHtml(description)}</td>
            <td class="text-center"><small>${cwe}</small></td>
        `;
        
        return tr;
    }
    
    updatePaginationInfo(start, end, total) {
        document.getElementById('items-start').textContent = total > 0 ? start : 0;
        document.getElementById('items-end').textContent = end;
        document.getElementById('items-total').textContent = total;
    }
    
    renderPaginationControls(totalItems) {
        const totalPages = Math.ceil(totalItems / this.itemsPerPage);
        const container = document.getElementById('pagination-controls');
        container.innerHTML = '';
        
        if (totalPages <= 1) return;
        
        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${this.currentPage === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#" data-page="${this.currentPage - 1}">Previous</a>`;
        container.appendChild(prevLi);
        
        // Page numbers (show max 5 pages)
        const maxVisible = 5;
        let startPage = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);
        
        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === this.currentPage ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#" data-page="${i}">${i}</a>`;
            container.appendChild(li);
        }
        
        // Next button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${this.currentPage === totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#" data-page="${this.currentPage + 1}">Next</a>`;
        container.appendChild(nextLi);
        
        // Attach click handlers
        container.querySelectorAll('a.page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(e.target.dataset.page);
                if (page >= 1 && page <= totalPages) {
                    this.currentPage = page;
                    this.renderIssuesTable();
                }
            });
        });
    }
    
    renderSARIFSection() {
        const data = this.currentToolData;
        const card = document.getElementById('sarif-card');
        
        if (!data.sarif && !data.sarif_file) {
            card.classList.add('d-none');
            return;
        }
        
        const sarifPath = data.sarif_file || (data.sarif && data.sarif.sarif_file);
        if (!sarifPath) {
            card.classList.add('d-none');
            return;
        }
        
        document.getElementById('sarif-file-path').textContent = sarifPath;
        
        // Set download link
        const downloadBtn = document.getElementById('sarif-download-btn');
        downloadBtn.href = `/api/analysis/results/${this.resultId}/sarif/${encodeURIComponent(sarifPath)}`;
        
        card.classList.remove('d-none');
    }
    
    async toggleSARIFPreview() {
        const preview = document.getElementById('sarif-preview');
        const toggle = document.getElementById('sarif-preview-toggle');
        
        if (preview.classList.contains('d-none')) {
            // Load and show SARIF
            toggle.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading...';
            
            try {
                const sarifPath = document.getElementById('sarif-file-path').textContent;
                const response = await fetch(`/api/analysis/results/${this.resultId}/sarif/${encodeURIComponent(sarifPath)}`);
                
                if (response.ok) {
                    const sarifData = await response.json();
                    document.getElementById('sarif-preview-content').textContent = 
                        JSON.stringify(sarifData, null, 2);
                    preview.classList.remove('d-none');
                    toggle.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Hide Preview';
                } else {
                    throw new Error('Failed to load SARIF');
                }
            } catch (error) {
                alert('Failed to load SARIF preview: ' + error.message);
                toggle.innerHTML = '<i class="fa-solid fa-eye"></i> Show Preview';
            }
        } else {
            // Hide SARIF
            preview.classList.add('d-none');
            toggle.innerHTML = '<i class="fa-solid fa-eye"></i> Show Preview';
        }
    }
    
    renderConfiguration() {
        const data = this.currentToolData;
        const card = document.getElementById('config-card');
        
        if (!data.config && !data.command && !data.args) {
            card.classList.add('d-none');
            return;
        }
        
        let configText = '';
        
        if (data.command) {
            configText += `Command: ${data.command}\n`;
        }
        if (data.args) {
            configText += `Arguments: ${JSON.stringify(data.args, null, 2)}\n`;
        }
        if (data.config) {
            configText += `\nConfiguration:\n${JSON.stringify(data.config, null, 2)}`;
        }
        
        if (configText) {
            document.getElementById('config-content').textContent = configText;
            card.classList.remove('d-none');
        } else {
            card.classList.add('d-none');
        }
    }
    
    exportToCSV() {
        const data = this.currentToolData;
        if (!data.issues || data.issues.length === 0) {
            alert('No issues to export');
            return;
        }
        
        // Filter issues
        let issues = data.issues;
        if (this.currentFilter) {
            issues = issues.filter(issue => {
                const severity = (issue.issue_severity || issue.severity || '').toUpperCase();
                return severity === this.currentFilter;
            });
        }
        
        // Build CSV
        const headers = ['Severity', 'Rule/Type', 'File', 'Line', 'Description', 'CWE'];
        const rows = issues.map(issue => [
            (issue.issue_severity || issue.severity || 'INFO').toUpperCase(),
            issue.test_id || issue.rule_id || issue.type || '',
            issue.filename || issue.file || issue.location || '',
            issue.line_number || issue.line || '',
            (issue.issue_text || issue.message || issue.description || '').replace(/"/g, '""'),
            issue.issue_cwe || issue.cwe || ''
        ]);
        
        const csv = [
            headers.join(','),
            ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
        ].join('\n');
        
        // Download
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.toolName || 'tool'}-issues.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    handleHashNavigation() {
        const hash = window.location.hash;
        if (!hash || !hash.startsWith('#tool-')) return;
        
        const toolName = hash.replace('#tool-', '');
        
        // Find and click the corresponding tool detail button
        const toolBtn = document.querySelector(`[data-tool-name="${toolName}"]`);
        if (toolBtn) {
            toolBtn.click();
        }
    }
    
    // Helper methods
    getStatusBadge(status) {
        const statusLower = (status || 'unknown').toLowerCase();
        let badgeClass = 'bg-secondary-lt';
        let icon = 'fa-circle-dot';
        
        if (['success', 'ok', 'completed', 'no_issues'].includes(statusLower)) {
            badgeClass = 'bg-success-lt text-success';
            icon = 'fa-check';
        } else if (['failed', 'error'].includes(statusLower)) {
            badgeClass = 'bg-danger-lt text-danger';
            icon = 'fa-xmark';
        } else if (statusLower === 'skipped') {
            badgeClass = 'bg-secondary-lt';
            icon = 'fa-forward';
        }
        
        return `<span class="badge ${badgeClass}"><i class="fa-solid ${icon} me-1"></i>${status}</span>`;
    }
    
    getSeverityBadgeClass(severity) {
        const severityLower = (severity || '').toLowerCase();
        const classMap = {
            'critical': 'bg-danger text-white',
            'high': 'bg-danger-lt text-danger',
            'medium': 'bg-warning-lt text-warning',
            'low': 'bg-info-lt text-info',
            'info': 'bg-secondary-lt'
        };
        return classMap[severityLower] || 'bg-secondary-lt';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.toolDetailModal = new ToolDetailModal();
});
