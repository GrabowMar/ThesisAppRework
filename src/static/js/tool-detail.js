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
        this.currentToolName = null;
        this.currentFilter = 'all';
        this.currentSearch = '';
        this.currentPage = 1;
        this.pageSize = 25;
        this.expandedIssueId = null;
        
        if (this.modalElement) {
            this.bsModal = bootstrap.Modal.getInstance(this.modalElement) || new bootstrap.Modal(this.modalElement);
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

        // Listener for issue row clicks (accordion expand/collapse)
        this.modalElement.addEventListener('click', (e) => {
            const row = e.target.closest('.issue-row');
            if (row) {
                e.preventDefault();
                const issueId = row.dataset.issueId;
                this.toggleIssueDetail(issueId, row);
            }
        });

        // Pagination clicks
        this.modalElement.addEventListener('click', (e) => {
            const pageBtn = e.target.closest('.page-link[data-page]');
            if (pageBtn) {
                e.preventDefault();
                const page = parseInt(pageBtn.dataset.page, 10);
                if (page && page !== this.currentPage) {
                    this.currentPage = page;
                    this.renderIssuesTable(this.currentToolData.issues);
                }
            }
        });

        // Filter listeners
        const severityFilter = document.getElementById('severity-filter');
        if (severityFilter) {
            severityFilter.addEventListener('change', (e) => {
                this.currentFilter = e.target.value;
                this.currentPage = 1;
                this.expandedIssueId = null;
                this.renderIssuesTable(this.currentToolData.issues);
            });
        }

        const searchInput = document.getElementById('issue-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.currentSearch = e.target.value.toLowerCase();
                this.currentPage = 1;
                this.expandedIssueId = null;
                this.renderIssuesTable(this.currentToolData.issues);
            });
        }

        // Raw output copy/download buttons
        const copyRawBtn = document.getElementById('copy-raw-btn');
        if (copyRawBtn) {
            copyRawBtn.addEventListener('click', () => this.copyRawOutput());
        }

        const downloadRawBtn = document.getElementById('download-raw-btn');
        if (downloadRawBtn) {
            downloadRawBtn.addEventListener('click', () => this.downloadRawOutput());
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

        this.currentToolName = toolName;

        // Get the correct parser
        this.currentParser = window.AnalysisParserFactory.getParser(serviceType, window.ANALYSIS_DATA);
        
        // Get normalized data for the specific tool
        this.currentToolData = this.currentParser.getToolData(toolName);

        if (!this.currentToolData) {
            console.error(`No data found for tool: ${toolName}`);
            return;
        }

        // Check if we need to fetch detailed data from API
        if (this.currentToolData.issues.length === 0 && 
            this.currentToolData.summary.total_issues > 0) {
            
            try {
                this.renderLoadingState();
                this.bsModal.show();

                const resultId = window.ANALYSIS_DATA.task_id;
                const response = await fetch(`/api/analysis/results/${resultId}/tools/${toolName}?service=${serviceType}`, {
                    credentials: 'same-origin'
                });
                
                if (!response.ok) {
                    console.error(`API call failed: ${response.status} ${response.statusText}`);
                    const errorBody = await response.text();
                    console.error('Error body:', errorBody);
                }
                
                if (response.ok) {
                    const result = await response.json();
                    const detailedData = result.data || result;

                    if (detailedData) {
                        this.currentToolData.raw = { ...this.currentToolData.raw, ...detailedData };
                    }

                    if (detailedData.issues && detailedData.issues.length > 0) {
                        this.currentToolData.issues = detailedData.issues.map((issue, idx) => ({
                            id: `fetched-${toolName}-${idx}`,
                            tool: toolName,
                            severity: (issue.severity || issue.issue_severity || issue.level || 'info').toLowerCase(),
                            message: issue.message || issue.issue_text || issue.description || 'No description',
                            file: issue.file || issue.path || issue.filename || issue.location?.file || 'unknown',
                            line: issue.line || issue.line_number || issue.location?.line || 0,
                            raw: issue
                        }));
                        this.currentToolData.summary.total_issues = this.currentToolData.issues.length;
                    } else if (detailedData.sarif_content) {
                        const sarifIssues = window.AnalysisParserFactory.SarifParser.parse(detailedData.sarif_content);
                        this.currentToolData.issues = sarifIssues;
                        this.currentToolData.summary.total_issues = sarifIssues.length;
                    } else if (detailedData.sarif) {
                        const sarifIssues = window.AnalysisParserFactory.SarifParser.parse(detailedData.sarif);
                        this.currentToolData.issues = sarifIssues;
                        this.currentToolData.summary.total_issues = sarifIssues.length;
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
        document.getElementById('severity-summary-divider').classList.add('d-none');
        document.getElementById('raw-output-content').textContent = 'Loading...';
    }


    renderModalContent() {
        const data = this.currentToolData;
        const summary = data.summary;

        // 1. Header
        document.getElementById('modal-tool-name').textContent = summary.name;
        document.getElementById('modal-tool-subtitle').textContent = `${summary.status} • ${summary.total_issues} issues`;

        // 2. Metadata
        const statusEl = document.getElementById('meta-status');
        statusEl.textContent = summary.status;
        const isSuccess = summary.status === 'success' || summary.status === 'completed';
        statusEl.className = `badge ${isSuccess ? 'bg-success-lt text-success' : 'bg-secondary-lt text-secondary'}`;
        document.getElementById('meta-total-issues').textContent = summary.total_issues;
        document.getElementById('meta-exec-time').textContent = summary.execution_time ? `${(summary.execution_time).toFixed(2)}s` : '—';

        // 3. Metrics / Summary Cards
        this.renderMetrics(data.metrics);
        this.renderSeveritySummary(data.issues);

        // 4. Issues Table
        this.currentPage = 1;
        this.expandedIssueId = null;
        this.renderIssuesTable(data.issues);

        // 5. Raw Output Tab
        this.renderRawOutput(data.raw);

        // 6. Footer count
        this.updateFooterCount(data.summary.total_issues);
        
        // Switch to issues tab
        const issuesTab = document.getElementById('issues-tab');
        if (issuesTab) {
            const tab = new bootstrap.Tab(issuesTab);
            tab.show();
        }
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
                <div class="border rounded-2 p-2 text-center bg-body">
                    <div class="small text-muted text-uppercase fw-bold" style="font-size: 0.7rem;">${m.name}</div>
                    <div class="fs-4 fw-bold text-primary">${m.value}</div>
                </div>
            </div>
        `).join('');
    }

    renderSeveritySummary(issues) {
        const container = document.getElementById('severity-badges');
        const wrapper = document.getElementById('severity-summary-container');
        const divider = document.getElementById('severity-summary-divider');

        if (!issues || issues.length === 0) {
            wrapper.classList.add('d-none');
            divider.classList.add('d-none');
            return;
        }

        wrapper.classList.remove('d-none');
        divider.classList.remove('d-none');
        
        const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
        issues.forEach(i => {
            const sev = (i.severity || 'info').toLowerCase();
            if (counts[sev] !== undefined) counts[sev]++;
            else counts.info++;
        });

        container.innerHTML = Object.entries(counts)
            .filter(([_, count]) => count > 0)
            .map(([sev, count]) => {
                const cls = this.getSeverityBadgeClass(sev);
                return `<span class="badge ${cls}">${sev.toUpperCase()}: ${count}</span>`;
            }).join('');
    }

    renderIssuesTable(issues) {
        const tbody = document.getElementById('issues-table-body');
        const noIssuesMsg = document.getElementById('no-issues-message');
        const tableCard = document.getElementById('issues-table').closest('.card');
        
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

        // Update filter count
        const filterCountEl = document.getElementById('filter-count');
        if (filtered.length !== issues.length) {
            filterCountEl.textContent = `Showing ${filtered.length} of ${issues.length}`;
        } else {
            filterCountEl.textContent = filtered.length > 0 ? `${filtered.length} total` : '';
        }

        if (filtered.length === 0) {
            tableCard.classList.add('d-none');
            noIssuesMsg.classList.remove('d-none');
            noIssuesMsg.querySelector('.empty-title').textContent = issues.length > 0 ? 'No matching issues found.' : 'No issues found.';
            document.getElementById('issues-pagination').classList.add('d-none');
            return;
        }

        tableCard.classList.remove('d-none');
        noIssuesMsg.classList.add('d-none');

        // Pagination
        const totalPages = Math.ceil(filtered.length / this.pageSize);
        if (this.currentPage > totalPages) this.currentPage = totalPages;
        const startIdx = (this.currentPage - 1) * this.pageSize;
        const endIdx = Math.min(startIdx + this.pageSize, filtered.length);
        const pageItems = filtered.slice(startIdx, endIdx);

        // Render rows
        let html = '';
        for (const issue of pageItems) {
            const isExpanded = this.expandedIssueId === issue.id;
            const badgeCls = this.getSeverityBadgeClass(issue.severity);
            html += `
            <tr class="issue-row${isExpanded ? ' expanded' : ''}" data-issue-id="${issue.id}">
                <td><span class="badge ${badgeCls}">${this.escapeHtml(issue.severity)}</span></td>
                <td><div class="text-truncate" style="max-width: 450px;" title="${this.escapeHtml(issue.message)}">${this.escapeHtml(issue.message)}</div></td>
                <td><small class="text-muted font-monospace">${this.escapeHtml(this.formatLocation(issue))}</small></td>
                <td class="text-center"><i class="fa-solid fa-chevron-down chevron-icon"></i></td>
            </tr>`;
            if (isExpanded) {
                html += this.buildDetailRow(issue);
            }
        }
        tbody.innerHTML = html;

        // Pagination controls
        this.renderPagination(filtered.length, totalPages);

        // Update footer
        this.updateFooterCount(issues.length, filtered.length);
    }

    renderPagination(totalFiltered, totalPages) {
        const paginationContainer = document.getElementById('issues-pagination');
        const paginationInfo = document.getElementById('pagination-info');
        const paginationControls = document.getElementById('pagination-controls');

        if (totalPages <= 1) {
            paginationContainer.classList.add('d-none');
            return;
        }

        paginationContainer.classList.remove('d-none');
        const startIdx = (this.currentPage - 1) * this.pageSize + 1;
        const endIdx = Math.min(this.currentPage * this.pageSize, totalFiltered);
        paginationInfo.textContent = `Showing ${startIdx}–${endIdx} of ${totalFiltered} findings`;

        let controlsHtml = '';
        // Previous button
        if (this.currentPage > 1) {
            controlsHtml += `<li class="page-item"><button class="page-link" data-page="${this.currentPage - 1}" type="button">Previous</button></li>`;
        }
        // Page numbers with ellipsis
        for (let p = 1; p <= totalPages; p++) {
            if (p === this.currentPage) {
                controlsHtml += `<li class="page-item active"><span class="page-link">${p}</span></li>`;
            } else if (p === 1 || p === totalPages || (p >= this.currentPage - 2 && p <= this.currentPage + 2)) {
                controlsHtml += `<li class="page-item"><button class="page-link" data-page="${p}" type="button">${p}</button></li>`;
            } else if (p === this.currentPage - 3 || p === this.currentPage + 3) {
                controlsHtml += `<li class="page-item disabled"><span class="page-link">…</span></li>`;
            }
        }
        // Next button
        if (this.currentPage < totalPages) {
            controlsHtml += `<li class="page-item"><button class="page-link" data-page="${this.currentPage + 1}" type="button">Next</button></li>`;
        }
        paginationControls.innerHTML = controlsHtml;
    }

    toggleIssueDetail(issueId, rowElement) {
        if (this.expandedIssueId === issueId) {
            // Collapse
            this.expandedIssueId = null;
            rowElement.classList.remove('expanded');
            const detailRow = rowElement.nextElementSibling;
            if (detailRow && detailRow.classList.contains('issue-detail-row')) {
                detailRow.remove();
            }
        } else {
            // Collapse previous
            const prevExpanded = this.modalElement.querySelector('.issue-row.expanded');
            if (prevExpanded) {
                prevExpanded.classList.remove('expanded');
                const prevDetail = prevExpanded.nextElementSibling;
                if (prevDetail && prevDetail.classList.contains('issue-detail-row')) {
                    prevDetail.remove();
                }
            }
            // Expand new
            this.expandedIssueId = issueId;
            rowElement.classList.add('expanded');

            const issue = this.currentToolData.issues.find(i => i.id === issueId);
            if (!issue) return;

            const detailHtml = this.buildDetailRow(issue);
            rowElement.insertAdjacentHTML('afterend', detailHtml);
        }
    }

    buildDetailRow(issue) {
        let detail = null;

        // Try to get detail from parser first, then build from raw
        if (this.currentParser && typeof this.currentParser.getDetail === 'function') {
            detail = this.currentParser.getDetail(issue.id);
        }
        if (!detail) {
            detail = {
                title: issue.message,
                severity: issue.severity,
                description: issue.raw?.description || issue.raw?.issue_text || issue.message,
                location: this.formatLocation(issue),
                code: issue.raw?.code || issue.raw?.context || null,
                remediation: issue.raw?.remediation || issue.raw?.solution || issue.raw?.fix || null,
                evidence: issue.raw || issue
            };
        }

        const badgeCls = this.getSeverityBadgeClass(detail.severity);

        let contentHtml = `
        <div class="issue-detail-content">
            <div class="d-flex align-items-center gap-2 mb-2">
                <span class="badge ${badgeCls}">${this.escapeHtml(detail.severity)}</span>
                <span class="text-muted font-monospace small">${this.escapeHtml(detail.location || '')}</span>
            </div>
            <div class="mb-2">
                <div class="fw-bold small text-uppercase text-muted mb-1">Description</div>
                <p class="mb-0 small">${this.escapeHtml(detail.description)}</p>
            </div>`;

        if (detail.code) {
            const codeText = typeof detail.code === 'string' ? detail.code : JSON.stringify(detail.code, null, 2);
            contentHtml += `
            <div class="mb-2">
                <div class="fw-bold small text-uppercase text-muted mb-1">Code / Context</div>
                <pre class="bg-dark text-light p-2 rounded-2 small mb-0"><code>${this.escapeHtml(codeText)}</code></pre>
            </div>`;
        }

        if (detail.remediation) {
            contentHtml += `
            <div class="mb-2">
                <div class="fw-bold small text-uppercase text-muted text-success mb-1">Remediation</div>
                <div class="alert alert-success bg-success-lt border-success py-1 px-2 mb-0 small">${this.escapeHtml(detail.remediation)}</div>
            </div>`;
        }

        // Raw evidence as collapsible
        const evidenceId = `evidence-${issue.id.replace(/[^a-zA-Z0-9-]/g, '_')}`;
        contentHtml += `
            <div>
                <button class="btn btn-sm btn-ghost-secondary px-0" type="button" data-bs-toggle="collapse" data-bs-target="#${evidenceId}">
                    <i class="fa-solid fa-code me-1"></i>Raw Evidence
                </button>
                <div class="collapse mt-1" id="${evidenceId}">
                    <pre class="small mb-0 overflow-auto bg-dark text-light p-2 rounded-2" style="max-height: 200px;"><code>${this.escapeHtml(JSON.stringify(detail.evidence, null, 2))}</code></pre>
                </div>
            </div>
        </div>`;

        return `<tr class="issue-detail-row"><td colspan="4">${contentHtml}</td></tr>`;
    }

    formatLocation(issue) {
        const file = issue.file || issue.url || '';
        const line = issue.line || '';
        if (!file && !line) return '—';
        // Shorten long file paths to last 2 segments
        let shortFile = file;
        const parts = file.replace(/^file:\/\//, '').split('/');
        if (parts.length > 2) {
            shortFile = '…/' + parts.slice(-2).join('/');
        }
        return line ? `${shortFile}:${line}` : shortFile;
    }

    renderRawOutput(rawData) {
        const container = document.getElementById('raw-output-content');
        if (!container) return;

        if (!rawData || Object.keys(rawData).length === 0) {
            container.innerHTML = '<span class="text-muted">// No raw data available for this tool</span>';
            return;
        }

        try {
            const jsonString = JSON.stringify(rawData, null, 2);
            container.innerHTML = this.highlightJson(jsonString);
        } catch (e) {
            container.textContent = `// Error formatting raw data: ${e.message}`;
        }
    }

    highlightJson(jsonStr) {
        return jsonStr.replace(
            /("(?:\\.|[^"\\])*")\s*:/g,
            '<span class="json-key">$1</span>:'
        ).replace(
            /:\s*("(?:\\.|[^"\\])*")/g,
            ': <span class="json-string">$1</span>'
        ).replace(
            /:\s*(\d+(?:\.\d+)?)/g,
            ': <span class="json-number">$1</span>'
        ).replace(
            /:\s*(true|false)/g,
            ': <span class="json-boolean">$1</span>'
        ).replace(
            /:\s*(null)/g,
            ': <span class="json-null">$1</span>'
        );
    }

    updateFooterCount(total, filtered) {
        const el = document.getElementById('modal-footer-count');
        if (!el) return;
        if (filtered !== undefined && filtered !== total) {
            el.textContent = `${filtered} of ${total} findings shown`;
        } else {
            el.textContent = `${total} total findings`;
        }
    }

    copyRawOutput() {
        const rawContent = document.getElementById('raw-output-content');
        if (!rawContent) return;

        navigator.clipboard.writeText(rawContent.textContent).then(() => {
            const btn = document.getElementById('copy-raw-btn');
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-check me-1"></i> Copied!';
            btn.classList.add('btn-success');
            btn.classList.remove('btn-ghost-primary');
            
            setTimeout(() => {
                btn.innerHTML = originalHtml;
                btn.classList.remove('btn-success');
                btn.classList.add('btn-ghost-primary');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    }

    downloadRawOutput() {
        if (!this.currentToolData || !this.currentToolData.raw) return;

        const jsonString = JSON.stringify(this.currentToolData.raw, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.currentToolName || 'tool'}_raw_output.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    resetModal() {
        this.currentParser = null;
        this.currentToolData = null;
        this.currentToolName = null;
        this.currentFilter = 'all';
        this.currentSearch = '';
        this.currentPage = 1;
        this.expandedIssueId = null;
        
        document.getElementById('issues-table-body').innerHTML = '';
        document.getElementById('issue-search').value = '';
        document.getElementById('severity-filter').value = 'all';
        document.getElementById('raw-output-content').textContent = '';
        document.getElementById('modal-footer-count').textContent = '';
        document.getElementById('filter-count').textContent = '';
        document.getElementById('issues-pagination').classList.add('d-none');
    }

    getSeverityBadgeClass(severity) {
        const map = {
            critical: 'bg-danger-lt text-danger',
            high: 'bg-danger-lt text-danger',
            medium: 'bg-warning-lt text-warning',
            low: 'bg-info-lt text-info',
            info: 'bg-secondary-lt text-secondary',
            success: 'bg-success-lt text-success'
        };
        return map[severity?.toLowerCase()] || 'bg-secondary-lt text-secondary';
    }

    escapeHtml(text) {
        if (!text) return '';
        return String(text)
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
