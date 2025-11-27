/**
 * Tool Detail Controller
 * Orchestrates the interaction between the UI and the Analysis Parsers.
 * Replaces the old monolithic ToolDetailModal.
 */

(function() {

class ToolDetailController {
    constructor() {
        this.modalElement = document.getElementById('toolDetailModal');
        this.bsModal = null;
        this.currentParser = null;
        this.currentToolData = null;
        this.currentFilter = 'all';
        this.currentSearch = '';
        
        if (this.modalElement) {
            this.bsModal = new bootstrap.Modal(this.modalElement);
            this.initEventListeners();
        } else {
            console.warn('Tool Detail Modal element not found.');
        }
    }

    initEventListeners() {
        // Global listener for "View Details" buttons
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.tool-detail-btn');
            if (btn) {
                e.preventDefault();
                const toolName = btn.dataset.toolName;
                const serviceType = btn.dataset.serviceType;
                this.openToolModal(serviceType, toolName);
            }
        });

        // Listener for "View Issue" buttons inside the modal table
        this.modalElement.addEventListener('click', (e) => {
            const btn = e.target.closest('.view-issue-btn');
            if (btn) {
                e.preventDefault();
                const issueId = btn.dataset.issueId;
                this.showIssueDetail(issueId);
            }
        });

        // Back button
        const backBtn = document.getElementById('back-to-list-btn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                document.getElementById('detail-view').classList.add('d-none');
                document.getElementById('issues-section').classList.remove('d-none');
            });
        }

        // Filter listeners
        const severityFilter = document.getElementById('severity-filter');
        if (severityFilter) {
            severityFilter.addEventListener('change', (e) => {
                this.currentFilter = e.target.value;
                this.renderIssuesTable(this.currentToolData.issues);
            });
        }

        const searchInput = document.getElementById('issue-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.currentSearch = e.target.value.toLowerCase();
                this.renderIssuesTable(this.currentToolData.issues);
            });
        }

        // Reset modal on close
        this.modalElement.addEventListener('hidden.bs.modal', () => {
            this.resetModal();
        });
    }

    async openToolModal(serviceType, toolName) {
        if (!window.ANALYSIS_DATA) {
            console.error('Analysis data not loaded.');
            return;
        }

        // Get the correct parser
        this.currentParser = window.AnalysisParserFactory.getParser(serviceType, window.ANALYSIS_DATA);
        
        // Get normalized data for the specific tool
        this.currentToolData = this.currentParser.getToolData(toolName);

        if (!this.currentToolData) {
            console.error(`No data found for tool: ${toolName}`);
            return;
        }

        // Check if we need to fetch SARIF data
        // Condition: No issues parsed, but total_issues > 0, and we have a SARIF file reference
        if (this.currentToolData.issues.length === 0 && 
            this.currentToolData.summary.total_issues > 0 && 
            this.currentToolData.sarif_file) {
            
            try {
                this.renderLoadingState();
                this.bsModal.show();

                const resultId = window.ANALYSIS_DATA.task_id;
                // Fetch detailed tool data which should include hydrated issues or SARIF content
                const response = await fetch(`/api/analysis/results/${resultId}/tools/${toolName}?service=${serviceType}`);
                
                if (response.ok) {
                    const result = await response.json();
                    const detailedData = result.data || result;

                    if (detailedData.issues && detailedData.issues.length > 0) {
                        // If backend hydrated the issues, use them
                        // Normalize them to match the format expected by renderIssuesTable
                        this.currentToolData.issues = detailedData.issues.map((issue, idx) => ({
                            id: `fetched-${toolName}-${idx}`,
                            tool: toolName,
                            severity: (issue.severity || issue.issue_severity || issue.level || 'info').toLowerCase(),
                            message: issue.message || issue.issue_text || 'No description',
                            file: issue.file || issue.path || issue.filename || issue.location?.file || 'unknown',
                            line: issue.line || issue.line_number || issue.location?.line || 0,
                            raw: issue
                        }));
                    } else if (detailedData.sarif_content) {
                        // If backend returned SARIF content
                        const sarifIssues = window.AnalysisParserFactory.SarifParser.parse(detailedData.sarif_content);
                        this.currentToolData.issues = sarifIssues;
                    } else if (detailedData.sarif_file) {
                        // If we just got the file path again, maybe we can fetch the file directly?
                        // This depends on if there is a route to serve raw result files.
                        // Let's try to fetch the SARIF file content if we can construct a URL.
                        // Assuming /api/analysis/results/{id}/artifacts/{path} exists?
                        // For now, we'll leave it as is if we can't get content.
                        console.warn('Received SARIF file path but no content. Backend hydration needed.');
                    }
                }
            } catch (e) {
                console.error('Error fetching detailed tool data:', e);
            }
        }

        this.renderModalContent();
        if (!this.bsModal._isShown) this.bsModal.show();
    }

    renderLoadingState() {
        document.getElementById('modal-tool-name').textContent = 'Loading...';
        document.getElementById('modal-tool-subtitle').textContent = 'Fetching detailed results...';
        document.getElementById('issues-table-body').innerHTML = '<tr><td colspan="4" class="text-center p-4"><div class="spinner-border text-primary" role="status"></div></td></tr>';
        document.getElementById('metrics-section').classList.add('d-none');
        document.getElementById('severity-summary-container').classList.add('d-none');
    }


    renderModalContent() {
        const data = this.currentToolData;
        const summary = data.summary;

        // 1. Header
        document.getElementById('modal-tool-name').textContent = summary.name;
        document.getElementById('modal-tool-subtitle').textContent = `${summary.status} • ${summary.total_issues} issues`;

        // 2. Metadata
        document.getElementById('meta-status').textContent = summary.status;
        document.getElementById('meta-status').className = `badge bg-${summary.status === 'success' || summary.status === 'completed' ? 'success' : 'secondary'}-lt`;
        document.getElementById('meta-total-issues').textContent = summary.total_issues;
        document.getElementById('meta-exec-time').textContent = summary.execution_time ? `${(summary.execution_time).toFixed(2)}s` : '—';

        // 3. Metrics / Summary Cards
        this.renderMetrics(data.metrics);
        this.renderSeveritySummary(data.issues);

        // 4. Issues Table
        this.renderIssuesTable(data.issues);

        // 5. Reset Views
        document.getElementById('detail-view').classList.add('d-none');
        document.getElementById('issues-section').classList.remove('d-none');
    }

    renderMetrics(metrics) {
        const container = document.getElementById('metrics-container');
        const section = document.getElementById('metrics-section');
        
        if (!metrics || metrics.length === 0) {
            section.classList.add('d-none');
            return;
        }

        section.classList.remove('d-none');
        container.innerHTML = metrics.map(m => `
            <div class="col-md-3 col-6">
                <div class="border rounded p-2 text-center bg-white">
                    <div class="small text-muted text-uppercase fw-bold" style="font-size: 0.7rem;">${m.name}</div>
                    <div class="fs-4 fw-bold text-primary">${m.value}</div>
                </div>
            </div>
        `).join('');
    }

    renderSeveritySummary(issues) {
        const container = document.getElementById('severity-badges');
        const wrapper = document.getElementById('severity-summary-container');

        if (!issues || issues.length === 0) {
            wrapper.classList.add('d-none');
            return;
        }

        wrapper.classList.remove('d-none');
        
        const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
        issues.forEach(i => {
            const sev = (i.severity || 'info').toLowerCase();
            if (counts[sev] !== undefined) counts[sev]++;
            else counts.info++;
        });

        container.innerHTML = Object.entries(counts)
            .filter(([_, count]) => count > 0)
            .map(([sev, count]) => `
                <span class="badge bg-${this.getSeverityColor(sev)} me-1">
                    ${sev.toUpperCase()}: ${count}
                </span>
            `).join('');
    }

    renderIssuesTable(issues) {
        const tbody = document.getElementById('issues-table-body');
        const noIssuesMsg = document.getElementById('no-issues-message');
        const table = document.getElementById('issues-table');
        
        // Filter issues
        let filtered = issues;
        if (this.currentFilter !== 'all') {
            filtered = filtered.filter(i => (i.severity || 'info').toLowerCase() === this.currentFilter);
        }
        if (this.currentSearch) {
            filtered = filtered.filter(i => 
                (i.message || '').toLowerCase().includes(this.currentSearch) ||
                (i.file || '').toLowerCase().includes(this.currentSearch)
            );
        }

        if (filtered.length === 0) {
            table.classList.add('d-none');
            noIssuesMsg.classList.remove('d-none');
            noIssuesMsg.querySelector('p').textContent = issues.length > 0 ? 'No matching issues found.' : 'No issues found.';
            return;
        }

        table.classList.remove('d-none');
        noIssuesMsg.classList.add('d-none');

        tbody.innerHTML = filtered.map(issue => `
            <tr>
                <td><span class="badge bg-${this.getSeverityColor(issue.severity)}">${issue.severity}</span></td>
                <td><div class="text-truncate" style="max-width: 400px;" title="${this.escapeHtml(issue.message)}">${this.escapeHtml(issue.message)}</div></td>
                <td><small class="text-muted text-truncate d-block" style="max-width: 200px;" title="${this.escapeHtml(issue.file || issue.url)}">${this.escapeHtml(issue.file || issue.url || '-')}:${issue.line || ''}</small></td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-primary view-issue-btn" data-issue-id="${issue.id}">
                        View
                    </button>
                </td>
            </tr>
        `).join('');
    }

    showIssueDetail(issueId) {
        // Try to find it in currentToolData first (for fetched issues)
        const issue = this.currentToolData.issues.find(i => i.id === issueId);
        
        let detail = null;
        if (issue) {
            // Construct detail from the normalized issue we created
            detail = {
                title: issue.message,
                subtitle: `${issue.tool} (Fetched)`,
                severity: issue.severity,
                description: issue.raw.description || issue.message,
                location: `${issue.file}:${issue.line}`,
                code: issue.raw.code || issue.raw.context || null,
                remediation: issue.raw.remediation || issue.raw.solution || null,
                evidence: issue.raw
            };
        } else {
            // Fallback to parser (for pre-loaded issues)
            detail = this.currentParser.getDetail(issueId);
        }

        if (!detail) return;

        // Populate Detail View
        document.getElementById('detail-title').textContent = detail.title;
        document.getElementById('detail-severity').textContent = detail.severity;
        document.getElementById('detail-severity').className = `badge bg-${this.getSeverityColor(detail.severity)}`;
        document.getElementById('detail-location').textContent = detail.location;
        document.getElementById('detail-description').textContent = detail.description;

        // Code Block
        const codeBlock = document.getElementById('detail-code');
        const codeSection = document.getElementById('detail-code-section');
        if (detail.code) {
            codeBlock.textContent = typeof detail.code === 'string' ? detail.code : JSON.stringify(detail.code, null, 2);
            codeSection.classList.remove('d-none');
        } else {
            codeSection.classList.add('d-none');
        }

        // Remediation
        const remediationDiv = document.getElementById('detail-remediation');
        const remediationSection = document.getElementById('detail-remediation-section');
        if (detail.remediation) {
            remediationDiv.textContent = detail.remediation;
            remediationSection.classList.remove('d-none');
        } else {
            remediationSection.classList.add('d-none');
        }

        // Evidence / Raw Data
        const evidenceBlock = document.getElementById('detail-evidence');
        evidenceBlock.textContent = JSON.stringify(detail.evidence, null, 2);

        // Switch Views
        document.getElementById('issues-section').classList.add('d-none');
        document.getElementById('detail-view').classList.remove('d-none');
    }

    resetModal() {
        this.currentParser = null;
        this.currentToolData = null;
        this.currentFilter = 'all';
        this.currentSearch = '';
        
        document.getElementById('issues-table-body').innerHTML = '';
        document.getElementById('issue-search').value = '';
        document.getElementById('severity-filter').value = 'all';
        
        document.getElementById('detail-view').classList.add('d-none');
        document.getElementById('issues-section').classList.remove('d-none');
    }

    getSeverityColor(severity) {
        const map = {
            critical: 'danger',
            high: 'danger',
            medium: 'warning',
            low: 'info',
            info: 'secondary',
            success: 'success'
        };
        return map[severity?.toLowerCase()] || 'secondary';
    }

    escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Initialize
function initToolDetail() {
    window.toolDetailController = new ToolDetailController();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initToolDetail);
} else {
    initToolDetail();
}

document.addEventListener('htmx:historyRestore', function(evt) {
    initToolDetail();
});

})();
