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
        
        const hasEmbeddedData = options.toolData && typeof options.toolData === 'object';

        if (hasEmbeddedData) {
            this.currentToolData = options.toolData;
            if (this.shouldHydrateFromApi()) {
                await this.fetchToolDetails();
            } else {
                this.renderToolDetails();
            }
        } else {
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

    shouldHydrateFromApi() {
        const data = this.currentToolData;
        if (!data) {
            return true;
        }
        const arrays = ['issues', 'findings', 'vulnerabilities', 'results', 'problems'];
        const hasIssueArray = arrays.some(key => Array.isArray(data[key]) && data[key].length > 0);
        if (hasIssueArray) {
            return false;
        }
        const declaredCount = data.total_issues || data.issue_count || data.findings_count ||
                             data.vulnerabilities_count || data.results_count || 0;
        const hasSarif = Boolean(data.sarif || data.sarif_file);
        return declaredCount > 0 && hasSarif;
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
        
        // Status with proper parsing
        let status = data.status;
        if (!status) {
            if (data.executed === false) {
                status = 'skipped';
            } else if (data.executed) {
                status = 'success';
            } else {
                status = 'unknown';
            }
        }
        const statusHtml = this.getStatusBadge(status);
        document.getElementById('meta-status').innerHTML = statusHtml;
        
        // Execution time - handle various formats
        let execTime = data.execution_time || data.exec_time || data.elapsed_time || data.duration;
        if (execTime !== undefined && execTime !== null) {
            if (typeof execTime === 'number') {
                execTime = execTime < 1 ? `${(execTime * 1000).toFixed(0)}ms` : `${execTime.toFixed(2)}s`;
            }
        } else {
            execTime = '—';
        }
        document.getElementById('meta-exec-time').textContent = execTime;
        
        // Total issues - check multiple possible fields
        const totalIssues = data.total_issues || data.issue_count || data.findings_count ||
                           (data.issues && Array.isArray(data.issues) ? data.issues.length : 0) ||
                           (data.findings && Array.isArray(data.findings) ? data.findings.length : 0) || 0;
        document.getElementById('meta-total-issues').textContent = totalIssues;
        
        // Exit code - only show if meaningful
        const exitCodeContainer = document.getElementById('meta-exit-container');
        if (data.exit_code !== undefined && data.exit_code !== null) {
            const exitCode = data.exit_code;
            const exitCodeEl = document.getElementById('meta-exit-code');
            exitCodeEl.textContent = exitCode;
            exitCodeEl.className = exitCode === 0 ? 'text-success' : 'text-danger';
            exitCodeContainer.classList.remove('d-none');
        } else {
            exitCodeContainer.classList.add('d-none');
        }
        
        // Additional metadata - only show relevant items
        const additionalContainer = document.getElementById('meta-additional');
        additionalContainer.innerHTML = '';
        
        const fileCount = data.files_scanned || data.files_analyzed || data.file_count;
        const lineCount = data.lines_analyzed || data.lines_of_code || data.loc;
        const version = data.version || data.tool_version;
        
        if (fileCount) {
            this.addCompactMetadataItem(additionalContainer, 'Files', fileCount);
        }
        if (lineCount) {
            this.addCompactMetadataItem(additionalContainer, 'Lines', lineCount.toLocaleString());
        }
        if (version) {
            this.addCompactMetadataItem(additionalContainer, 'v' + version, null, true);
        }
    }
    
    addCompactMetadataItem(container, label, value, isVersionBadge = false) {
        const span = document.createElement('span');
        span.className = 'border-start ps-2 small';
        if (isVersionBadge) {
            span.innerHTML = `<span class="badge bg-secondary-lt">${this.escapeHtml(label)}</span>`;
        } else {
            span.innerHTML = `<strong class="text-muted">${this.escapeHtml(label)}:</strong> ${this.escapeHtml(value)}`;
        }
        container.appendChild(span);
    }
    
    renderSeveritySummary() {
        const data = this.currentToolData;
        const card = document.getElementById('severity-summary-card');
        const container = document.getElementById('severity-breakdown');
        
        // Get issues from various possible fields
        const issues = data.issues || data.findings || data.vulnerabilities || [];
        
        if (!Array.isArray(issues) || issues.length === 0) {
            card.classList.add('d-none');
            return;
        }
        
        // Count issues by severity with better parsing
        const severityCounts = {};
        issues.forEach(issue => {
            let severity = issue.issue_severity || issue.severity || issue.level || 
                          issue.priority || issue.risk || 'UNKNOWN';
            severity = String(severity).toUpperCase();
            
            // Normalize severity names
            if (severity.includes('CRIT')) severity = 'CRITICAL';
            else if (severity.includes('ERROR')) severity = 'HIGH';
            else if (severity.includes('WARN')) severity = 'MEDIUM';
            else if (severity.includes('NOTE') || severity.includes('MINOR')) severity = 'LOW';
            
            severityCounts[severity] = (severityCounts[severity] || 0) + 1;
        });
        
        if (Object.keys(severityCounts).length === 0) {
            card.classList.add('d-none');
            return;
        }
        
        // Render compact severity badges
        container.innerHTML = '';
        const severityOrder = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
        
        severityOrder.forEach(severity => {
            if (severityCounts[severity]) {
                const badgeClass = this.getSeverityBadgeClass(severity);
                const badge = document.createElement('span');
                badge.className = `badge ${badgeClass} me-1`;
                badge.textContent = `${severity}: ${severityCounts[severity]}`;
                container.appendChild(badge);
            }
        });
        
        card.classList.remove('d-none');
    }
    
    renderPerformanceMetrics() {
        const data = this.currentToolData;
        const card = document.getElementById('performance-metrics-card');
        const container = document.getElementById('performance-metrics');
        
        // Check if this is a performance tool - look for metrics in multiple places
        const metrics = data.metrics || data.performance || data.stats || {};
        const avgResponseTime = metrics.avg_response_time || metrics.response_time || 
                               data.avg_response_time || data.response_time;
        const throughput = metrics.requests_per_second || metrics.throughput || metrics.rps ||
                          data.requests_per_second || data.throughput || data.rps;
        const successRate = metrics.success_rate || data.success_rate;
        const totalRequests = metrics.total_requests || metrics.requests || 
                            data.requests || data.completed_requests;
        
        const hasMetrics = avgResponseTime || throughput || successRate !== undefined || totalRequests;
        
        if (!hasMetrics) {
            card.classList.add('d-none');
            return;
        }
        
        container.innerHTML = '';
        const items = [];
        
        if (avgResponseTime) {
            items.push(`<span class="border-start ps-2"><strong class="text-muted">Response:</strong> ${avgResponseTime.toFixed(1)}ms</span>`);
        }
        if (throughput) {
            items.push(`<span class="border-start ps-2"><strong class="text-muted">Throughput:</strong> ${throughput.toFixed(1)} req/s</span>`);
        }
        if (successRate !== undefined) {
            const rateClass = successRate >= 95 ? 'text-success' : (successRate >= 80 ? 'text-warning' : 'text-danger');
            items.push(`<span class="border-start ps-2"><strong class="text-muted">Success:</strong> <span class="${rateClass}">${successRate.toFixed(1)}%</span></span>`);
        }
        if (totalRequests) {
            const failed = metrics.failed_requests || data.failed_requests || 0;
            const failedText = failed > 0 ? ` <span class="text-danger">(${failed} failed)</span>` : '';
            items.push(`<span class="border-start ps-2"><strong class="text-muted">Requests:</strong> ${totalRequests}${failedText}</span>`);
        }
        
        container.innerHTML = items.join('');
        card.classList.remove('d-none');
    }
    
    renderIssuesTable() {
        const data = this.currentToolData;
        const tbody = document.getElementById('issues-table-body');
        const issuesCard = document.getElementById('issues-card');
        
        // Get issues from various possible fields
        const allIssues = data.issues || data.findings || data.vulnerabilities || 
                         data.results || data.problems || [];
        
        if (!Array.isArray(allIssues) || allIssues.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3 small">No issues found</td></tr>';
            document.getElementById('issues-count-badge').textContent = '0';
            this.updatePaginationInfo(0, 0, 0);
            document.getElementById('pagination-controls').innerHTML = '';
            return;
        }
        
        // Filter issues by severity
        let filteredIssues = allIssues;
        if (this.currentFilter) {
            filteredIssues = allIssues.filter(issue => {
                let severity = issue.issue_severity || issue.severity || issue.level || 
                              issue.priority || issue.risk || '';
                severity = String(severity).toUpperCase();
                
                // Normalize for comparison
                if (severity.includes('CRIT')) severity = 'CRITICAL';
                else if (severity.includes('ERROR')) severity = 'HIGH';
                else if (severity.includes('WARN')) severity = 'MEDIUM';
                else if (severity.includes('NOTE') || severity.includes('MINOR')) severity = 'LOW';
                
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
        tr.className = 'align-middle';
        
        // Severity - check multiple fields and normalize
        let severity = issue.issue_severity || issue.severity || issue.level || 
                      issue.priority || issue.risk || 'INFO';
        severity = String(severity).toUpperCase();
        
        // Normalize severity names
        if (severity.includes('CRIT')) severity = 'CRITICAL';
        else if (severity.includes('ERROR')) severity = 'HIGH';
        else if (severity.includes('WARN')) severity = 'MEDIUM';
        else if (severity.includes('NOTE') || severity.includes('MINOR')) severity = 'LOW';
        
        const severityBadge = `<span class="badge ${this.getSeverityBadgeClass(severity)} badge-sm">${severity}</span>`;
        
        // Rule/Type - check multiple fields
        const rule = issue.test_id || issue.rule_id || issue.check_id || issue.rule || 
                    issue.type || issue.code || issue.id || '—';
        const ruleShort = String(rule).length > 15 ? String(rule).substring(0, 12) + '...' : rule;
        
        // File path - check multiple fields and truncate intelligently
        const file = issue.filename || issue.file || issue.path || issue.location || 
                    issue.filepath || issue.file_path || '—';
        let fileDisplay = String(file);
        if (fileDisplay.length > 25) {
            const parts = fileDisplay.split('/');
            fileDisplay = parts.length > 1 ? '.../' + parts.slice(-2).join('/') : '...' + fileDisplay.slice(-22);
        }
        
        // Line number - check multiple fields
        const line = issue.line_number || issue.line || issue.start_line || 
                    issue.lineNumber || (issue.location && issue.location.line) || '—';
        
        // Description - check multiple fields and clean up
        let description = issue.issue_text || issue.message || issue.description || 
                         issue.text || issue.msg || issue.details || 'No description';
        description = String(description).replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim();
        if (description.length > 100) {
            description = description.substring(0, 97) + '...';
        }
        
        // CWE - check multiple fields
        const cwe = issue.issue_cwe || issue.cwe || issue.cwe_id || 
                   (issue.tags && issue.tags.find(t => String(t).startsWith('CWE'))) || '—';
        
        tr.innerHTML = `
            <td class="py-1">${severityBadge}</td>
            <td class="py-1"><code class="small" title="${this.escapeHtml(rule)}">${this.escapeHtml(ruleShort)}</code></td>
            <td class="py-1"><span class="small text-muted" title="${this.escapeHtml(file)}">${this.escapeHtml(fileDisplay)}</span></td>
            <td class="py-1 text-center small">${line}</td>
            <td class="py-1 small" title="${this.escapeHtml(description)}">${this.escapeHtml(description)}</td>
            <td class="py-1 text-center"><small class="text-muted">${cwe}</small></td>
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
