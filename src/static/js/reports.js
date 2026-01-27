/**
 * Reports logic extracted from view_report.html
 * Handles report loading, rendering, and interactions.
 */

(function () {
    // Wait for DOM content to be loaded if not already
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReport);
    } else {
        initReport();
    }

    function initReport() {
        // Get report ID and type from data attributes
        const reportContainer = document.getElementById('report-detail-container'); // This ID needs to be added to the HTML
        // Fallback lookups if the container isn't found (for legacy support during refactor)
        if (!reportContainer && !window.REPORT_ID) return;

        const reportId = reportContainer ? reportContainer.dataset.reportId : window.REPORT_ID;
        const reportType = reportContainer ? reportContainer.dataset.reportType : window.REPORT_TYPE;

        const loadingState = document.getElementById('loading-state');
        const errorState = document.getElementById('error-state');
        const errorMessage = document.getElementById('error-message');
        const reportContent = document.getElementById('report-content');

        // Check if Chart.js is loaded
        if (typeof Chart === 'undefined') {
            console.error('Chart.js is not loaded');
        }

        let reportData = null;
        let severityChart = null;
        let toolsChart = null;

        // --- HELPER FUNCTIONS ---
        // Escape HTML
        function h(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        }

        // Format number with commas
        function formatNumber(n) {
            return (n || 0).toLocaleString();
        }

        // Format duration
        function formatDuration(seconds) {
            if (!seconds) return 'N/A';
            if (seconds < 60) return `${seconds.toFixed(1)}s`;
            const mins = Math.floor(seconds / 60);
            const secs = Math.round(seconds % 60);
            return `${mins}m ${secs}s`;
        }

        // Severity badge
        function severityBadge(sev) {
            const colors = {
                critical: 'bg-danger',
                high: 'bg-orange',
                medium: 'bg-yellow text-dark',
                low: 'bg-success',
                info: 'bg-info'
            };
            return `<span class="badge ${colors[sev?.toLowerCase()] || 'bg-secondary'}">${h(sev || 'Unknown')}</span>`;
        }

        // Task status badge with proper colors
        function statusBadge(status, taskStatus) {
            const statusMap = {
                'completed': { class: 'status-completed', icon: 'check', text: 'Completed' },
                'partial': { class: 'status-partial', icon: 'exclamation', text: 'Partial' },
                'partial_success': { class: 'status-partial', icon: 'exclamation', text: 'Partial' },
                'failed': { class: 'status-failed', icon: 'times', text: 'Failed' },
                'cancelled': { class: 'status-cancelled', icon: 'ban', text: 'Cancelled' },
                'running': { class: 'status-running', icon: 'spinner fa-spin', text: 'Running' },
                'pending': { class: 'status-pending', icon: 'clock', text: 'Pending' },
            };
            const s = statusMap[status?.toLowerCase()] || statusMap[taskStatus?.toLowerCase()] || { class: 'bg-secondary', icon: 'question', text: status || 'Unknown' };
            return `<span class="badge ${s.class}"><i class="fa-solid fa-${s.icon} me-1"></i>${s.text}</span>`;
        }

        // Display filter mode badge
        function displayFilterMode(filterMode) {
            const display = document.getElementById('filter-mode-display');
            if (!display) return;

            const modes = {
                'all': { text: 'All Analyzers', icon: 'fa-layer-group', color: 'primary' },
                'exclude_dynamic_perf': { text: 'Static & AI Only', icon: 'fa-shield-halved', color: 'info' },
                'only_dynamic_perf': { text: 'Dynamic & Performance Only', icon: 'fa-gauge-high', color: 'warning' }
            };

            const mode = modes[filterMode] || modes['all'];
            display.innerHTML = `
        <span class="badge bg-${mode.color}-lt">
          <i class="fa-solid ${mode.icon} me-1"></i>
          Filter Mode: ${mode.text}
        </span>
      `;
        }

        // Download JSON
        window.downloadJSON = function () {
            if (!reportData) return;
            const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `report_${reportId}.json`;
            a.click();
            URL.revokeObjectURL(url);
        };

        // --- PLACEHOLDERS FOR RENDER FUNCTIONS ---
        // Build LOC per-app table (helper for quantitative section)
        function buildLocPerAppTable(perAppData) {
            if (!perAppData) return '';
            // Handle both array and object formats
            let apps = Array.isArray(perAppData) ? perAppData : Object.values(perAppData);
            if (apps.length === 0) return '';
            let html = '<div class="mt-3">';
            html += '<h5 class="text-muted mb-2">Per-Application Breakdown</h5>';
            html += '<div class="table-responsive"><table class="table table-sm table-vcenter"><thead><tr>';
            html += '<th>App</th><th class="text-end">Backend LOC</th><th class="text-end">Frontend LOC</th>';
            html += '<th class="text-end">Total LOC</th><th class="text-end">Issues</th><th class="text-end">Issues/100 LOC</th>';
            html += '</tr></thead><tbody>';
            apps.forEach(app => {
                const colorClass = (app.issues_per_100_loc || 0) > 5 ? 'text-danger' : (app.issues_per_100_loc || 0) > 2 ? 'text-warning' : 'text-success';
                html += '<tr>';
                html += '<td><strong>App ' + (app.app_number || '?') + '</strong></td>';
                html += '<td class="text-end">' + formatNumber(app.backend_loc || 0) + '</td>';
                html += '<td class="text-end">' + formatNumber(app.frontend_loc || 0) + '</td>';
                html += '<td class="text-end">' + formatNumber(app.total_loc || 0) + '</td>';
                html += '<td class="text-end">' + formatNumber(app.issues_count || 0) + '</td>';
                html += '<td class="text-end ' + colorClass + '">' + (app.issues_per_100_loc || 0).toFixed(2) + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table></div></div>';
            return html;
        }

        // Build performance metrics card
        function buildPerformanceMetricsCard(perf) {
            if (!perf || Object.keys(perf).length === 0) return '';

            // Handle nested structure from backend
            const p95 = perf.p95_response_time || {};
            const p99 = perf.p99_response_time || {};
            const rps = perf.requests_per_second || {};
            const errorRate = perf.error_rate || {};

            let html = '<div class="card mb-3"><div class="card-header">';
            html += '<h3 class="card-title"><i class="fa-solid fa-gauge-high me-2"></i>Performance Metrics</h3></div>';
            html += '<div class="card-body">';

            // Top row: main summary metrics
            html += '<div class="row g-3 mb-3">';
            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0">' + formatNumber(perf.tests_count || perf.total_tests || 0) + '</div>';
            html += '<div class="text-muted small">Performance Tests</div></div></div>';

            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            const avgP95 = p95.mean || perf.avg_response_time_ms || 0;
            const p95Class = avgP95 <= 200 ? 'text-success' : avgP95 <= 500 ? 'text-warning' : 'text-danger';
            html += '<div class="h3 mb-0 ' + p95Class + '">' + avgP95.toFixed(0) + '</div>';
            html += '<div class="text-muted small">Mean P95 (ms)</div></div></div>';

            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            const avgRps = rps.mean || perf.avg_requests_per_sec || 0;
            html += '<div class="h3 mb-0">' + avgRps.toFixed(1) + '</div>';
            html += '<div class="text-muted small">Mean Requests/sec</div></div></div>';

            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            const avgErr = errorRate.mean || perf.avg_error_rate || 0;
            const errClass = avgErr <= 1 ? 'text-success' : avgErr <= 5 ? 'text-warning' : 'text-danger';
            html += '<div class="h3 mb-0 ' + errClass + '">' + (avgErr * 100).toFixed(2) + '%</div>';
            html += '<div class="text-muted small">Mean Error Rate</div></div></div>';
            html += '</div>';

            // Latency breakdown with min/median/max
            if (Object.keys(p95).length > 0 || Object.keys(p99).length > 0) {
                html += '<div class="row g-3 mb-3">';

                // P95 breakdown
                if (Object.keys(p95).length > 0) {
                    html += '<div class="col-md-6"><div class="border rounded p-2">';
                    html += '<h6 class="mb-2 text-muted"><i class="fa-solid fa-chart-line me-1"></i>P95 Response Time (ms)</h6>';
                    html += '<div class="d-flex justify-content-between small">';
                    html += '<span>Min: <strong>' + (p95.min || 0).toFixed(0) + '</strong></span>';
                    html += '<span>Median: <strong>' + (p95.median || 0).toFixed(0) + '</strong></span>';
                    html += '<span>Max: <strong class="text-danger">' + (p95.max || 0).toFixed(0) + '</strong></span>';
                    html += '</div></div></div>';
                }

                // P99 breakdown
                if (Object.keys(p99).length > 0) {
                    html += '<div class="col-md-6"><div class="border rounded p-2">';
                    html += '<h6 class="mb-2 text-muted"><i class="fa-solid fa-chart-line me-1"></i>P99 Response Time (ms)</h6>';
                    html += '<div class="d-flex justify-content-between small">';
                    html += '<span>Min: <strong>' + (p99.min || 0).toFixed(0) + '</strong></span>';
                    html += '<span>Median: <strong>' + (p99.median || 0).toFixed(0) + '</strong></span>';
                    html += '<span>Max: <strong class="text-danger">' + (p99.max || 0).toFixed(0) + '</strong></span>';
                    html += '</div></div></div>';
                }
                html += '</div>';
            }

            // Request totals
            if (perf.total_requests || perf.failed_requests) {
                html += '<div class="row g-2">';
                html += '<div class="col-6 col-md-4"><div class="text-center small">';
                html += '<span class="text-muted">Total Requests:</span> <strong>' + formatNumber(perf.total_requests || 0) + '</strong>';
                html += '</div></div>';
                html += '<div class="col-6 col-md-4"><div class="text-center small">';
                html += '<span class="text-muted">Failed:</span> <strong class="text-danger">' + formatNumber(perf.failed_requests || 0) + '</strong>';
                html += '</div></div>';
                if (rps.min !== undefined && rps.max !== undefined) {
                    html += '<div class="col-12 col-md-4"><div class="text-center small">';
                    html += '<span class="text-muted">RPS Range:</span> <strong>' + (rps.min || 0).toFixed(1) + ' - ' + (rps.max || 0).toFixed(1) + '</strong>';
                    html += '</div></div>';
                }
                html += '</div>';
            }

            html += '</div></div>';
            return html;
        }

        // Build security metrics card with enhanced breakdown
        function buildSecurityMetricsCard(sec) {
            if (!sec || Object.keys(sec).length === 0) return '';

            // Extract severity breakdown if available
            const severityBreakdown = sec.severity_breakdown || {};

            let html = '<div class="card"><div class="card-header">';
            html += '<h3 class="card-title"><i class="fa-solid fa-shield-halved me-2"></i>Security Analysis</h3></div>';
            html += '<div class="card-body">';

            // Main metrics row
            html += '<div class="row g-2 mb-3">';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            html += '<div class="h3 mb-0">' + formatNumber(sec.analyses_count || sec.total_analyses || 0) + '</div>';
            html += '<div class="text-muted small">Security Scans</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            html += '<div class="h3 mb-0">' + formatNumber(sec.total_issues || sec.total_vulnerabilities || 0) + '</div>';
            html += '<div class="text-muted small">Total Issues</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const toolSuccessRate = sec.tool_success_rate || 0;
            html += '<div class="h3 mb-0 ' + (toolSuccessRate >= 80 ? 'text-success' : 'text-warning') + '">' + toolSuccessRate.toFixed(0) + '%</div>';
            html += '<div class="text-muted small">Tool Success</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            html += '<div class="h3 mb-0">' + formatNumber(sec.tools_run_count || 0) + '</div>';
            html += '<div class="text-muted small">Tools Run</div></div></div>';
            html += '</div>';

            // Severity breakdown row
            html += '<div class="row g-2">';
            html += '<div class="col-3"><div class="text-center p-1 rounded" style="background-color: #f8d7da;">';
            html += '<div class="h4 mb-0 text-danger">' + formatNumber(severityBreakdown.critical || sec.critical_count || 0) + '</div>';
            html += '<div class="text-muted small">Critical</div></div></div>';
            html += '<div class="col-3"><div class="text-center p-1 rounded" style="background-color: #fff3cd;">';
            html += '<div class="h4 mb-0 text-warning">' + formatNumber(severityBreakdown.high || sec.high_count || 0) + '</div>';
            html += '<div class="text-muted small">High</div></div></div>';
            html += '<div class="col-3"><div class="text-center p-1 rounded" style="background-color: #d1e7dd;">';
            html += '<div class="h4 mb-0 text-info">' + formatNumber(severityBreakdown.medium || sec.medium_count || 0) + '</div>';
            html += '<div class="text-muted small">Medium</div></div></div>';
            html += '<div class="col-3"><div class="text-center p-1 rounded" style="background-color: #e2e3e5;">';
            html += '<div class="h4 mb-0 text-secondary">' + formatNumber(severityBreakdown.low || sec.low_count || 0) + '</div>';
            html += '<div class="text-muted small">Low</div></div></div>';
            html += '</div>';

            // Additional info row
            if (sec.avg_duration_per_analysis || sec.avg_issues_per_analysis) {
                html += '<div class="row g-2 mt-2">';
                html += '<div class="col-6"><div class="text-center">';
                html += '<div class="h5 mb-0">' + (sec.avg_duration_per_analysis || 0).toFixed(1) + 's</div>';
                html += '<div class="text-muted small">Avg Duration</div></div></div>';
                html += '<div class="col-6"><div class="text-center">';
                html += '<div class="h5 mb-0">' + (sec.avg_issues_per_analysis || 0).toFixed(1) + '</div>';
                html += '<div class="text-muted small">Avg Issues/Scan</div></div></div>';
                html += '</div>';
            }

            html += '</div></div>';
            return html;
        }

        // Build AI metrics card with enhanced quality scores
        function buildAiMetricsCard(ai) {
            if (!ai || Object.keys(ai).length === 0) return '';

            // Extract sub-scores if available (from backend ai_analysis metrics)
            const overallScore = ai.overall_score || {};
            const codeQuality = ai.code_quality_score || {};
            const securityScore = ai.security_score || {};
            const maintainabilityScore = ai.maintainability_score || {};
            const tokenUsage = ai.token_usage || {};

            let html = '<div class="card"><div class="card-header">';
            html += '<h3 class="card-title"><i class="fa-solid fa-robot me-2"></i>AI Analysis Quality Scores</h3></div>';
            html += '<div class="card-body">';

            // Main score metrics
            html += '<div class="row g-2 mb-3">';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            html += '<div class="h3 mb-0">' + formatNumber(ai.analyses_count || ai.total_analyses || 0) + '</div>';
            html += '<div class="text-muted small">AI Reviews</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const overallMean = overallScore.mean || ai.avg_compliance_score || 0;
            html += '<div class="h3 mb-0 ' + (overallMean >= 70 ? 'text-success' : overallMean >= 50 ? 'text-warning' : 'text-danger') + '">' + overallMean.toFixed(0) + '%</div>';
            html += '<div class="text-muted small">Overall Score</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const qualityMean = codeQuality.mean || ai.avg_quality_score || 0;
            html += '<div class="h3 mb-0">' + qualityMean.toFixed(0) + '</div>';
            html += '<div class="text-muted small">Code Quality</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const secMean = securityScore.mean || 0;
            html += '<div class="h3 mb-0">' + secMean.toFixed(0) + '</div>';
            html += '<div class="text-muted small">Security Score</div></div></div>';
            html += '</div>';

            // Additional metrics row
            html += '<div class="row g-2">';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const maintMean = maintainabilityScore.mean || 0;
            html += '<div class="h4 mb-0">' + maintMean.toFixed(0) + '</div>';
            html += '<div class="text-muted small">Maintainability</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const totalTokens = tokenUsage.total_tokens || ai.total_tokens_used || 0;
            html += '<div class="h4 mb-0">' + formatNumber(totalTokens) + '</div>';
            html += '<div class="text-muted small">Tokens Used</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const aiCost = ai.total_ai_analysis_cost_usd || 0;
            html += '<div class="h4 mb-0">$' + aiCost.toFixed(4) + '</div>';
            html += '<div class="text-muted small">AI Cost</div></div></div>';
            html += '<div class="col-6 col-md-3"><div class="text-center">';
            const scoreRange = overallScore.max && overallScore.min ? (overallScore.max - overallScore.min).toFixed(0) : '-';
            html += '<div class="h4 mb-0">' + scoreRange + '</div>';
            html += '<div class="text-muted small">Score Range</div></div></div>';
            html += '</div>';

            html += '</div></div>';
            return html;
        }

        // Build Docker/Container status card
        function buildDockerStatusCard(docker) {
            if (!docker || Object.keys(docker).length === 0) return '';
            const totalApps = docker.total_apps || 0;
            const running = docker.running || 0;
            const stopped = docker.stopped || 0;
            const errorCount = docker.error || 0;
            const neverBuilt = docker.never_built || 0;
            const buildSuccessRate = docker.build_success_rate || 0;
            const statusBreakdown = docker.status_breakdown || {};

            let html = '<div class="card mb-3"><div class="card-header">';
            html += '<h3 class="card-title"><i class="fa-brands fa-docker me-2"></i>Docker Container Status</h3></div>';
            html += '<div class="card-body">';

            // Main status indicators
            html += '<div class="row g-3 mb-3">';
            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0 text-success">' + formatNumber(running) + '</div>';
            html += '<div class="text-muted small">Running</div></div></div>';
            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0 text-secondary">' + formatNumber(stopped) + '</div>';
            html += '<div class="text-muted small">Stopped</div></div></div>';
            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0 text-danger">' + formatNumber(errorCount) + '</div>';
            html += '<div class="text-muted small">Error/Failed</div></div></div>';
            html += '<div class="col-md-3 col-6"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0 text-warning">' + formatNumber(neverBuilt) + '</div>';
            html += '<div class="text-muted small">Never Built</div></div></div>';
            html += '</div>';

            // Build success rate progress bar
            const rateClass = buildSuccessRate >= 80 ? 'bg-success' : buildSuccessRate >= 50 ? 'bg-warning' : 'bg-danger';
            html += '<div class="mb-3">';
            html += '<div class="d-flex justify-content-between mb-1">';
            html += '<span class="text-muted small">Build Success Rate</span>';
            html += '<span class="fw-bold">' + buildSuccessRate.toFixed(1) + '%</span>';
            html += '</div>';
            html += '<div class="progress" style="height: 10px;">';
            html += '<div class="progress-bar ' + rateClass + '" role="progressbar" style="width: ' + buildSuccessRate + '%" aria-valuenow="' + buildSuccessRate + '" aria-valuemin="0" aria-valuemax="100"></div>';
            html += '</div></div>';

            // Status breakdown table (if multiple statuses)
            const statusKeys = Object.keys(statusBreakdown);
            if (statusKeys.length > 0) {
                html += '<div class="table-responsive">';
                html += '<table class="table table-sm table-borderless mb-0">';
                html += '<tbody>';
                statusKeys.forEach(function (status) {
                    const count = statusBreakdown[status];
                    const pct = totalApps > 0 ? ((count / totalApps) * 100).toFixed(1) : 0;
                    const badgeClass = status === 'running' ? 'bg-success' :
                        status === 'stopped' ? 'bg-secondary' :
                            status === 'error' ? 'bg-danger' :
                                status === 'never_built' ? 'bg-warning' : 'bg-info';
                    html += '<tr><td><span class="badge ' + badgeClass + ' me-2">' + status.replace(/_/g, ' ') + '</span></td>';
                    html += '<td class="text-end">' + count + '</td>';
                    html += '<td class="text-end text-muted small">(' + pct + '%)</td></tr>';
                });
                html += '</tbody></table></div>';
            }

            html += '</div></div>';
            return html;
        }

        // Build generation summary card with fix breakdown
        function buildGenerationSummaryCard(gen) {
            if (!gen || Object.keys(gen).length === 0) return '';

            const fixCounts = gen.fix_counts || {};
            const successRate = gen.success_rate || 0;

            let html = '<div class="card"><div class="card-header">';
            html += '<h3 class="card-title"><i class="fa-solid fa-code-branch me-2"></i>Generation Summary</h3></div>';
            html += '<div class="card-body">';

            // Main metrics row
            html += '<div class="row g-2 mb-3">';
            html += '<div class="col-6 col-md-3"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0">' + formatNumber(gen.total_apps || 0) + '</div>';
            html += '<div class="text-muted small">Total Apps</div></div></div>';

            html += '<div class="col-6 col-md-3"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0 text-success">' + formatNumber(gen.successful_apps || 0) + '</div>';
            html += '<div class="text-muted small">Successful</div></div></div>';

            html += '<div class="col-6 col-md-3"><div class="text-center p-2 bg-light rounded">';
            html += '<div class="h3 mb-0 text-danger">' + formatNumber(gen.failed_apps || 0) + '</div>';
            html += '<div class="text-muted small">Failed</div></div></div>';

            html += '<div class="col-6 col-md-3"><div class="text-center p-2 bg-light rounded">';
            const rateClass = successRate >= 80 ? 'text-success' : successRate >= 50 ? 'text-warning' : 'text-danger';
            html += '<div class="h3 mb-0 ' + rateClass + '">' + successRate.toFixed(0) + '%</div>';
            html += '<div class="text-muted small">Success Rate</div></div></div>';
            html += '</div>';

            // Fix breakdown row (if any fixes applied)
            const totalFixes = fixCounts.total_fixes || 0;
            if (totalFixes > 0) {
                html += '<div class="border rounded p-2 mb-2">';
                html += '<h6 class="mb-2 text-muted"><i class="fa-solid fa-wrench me-1"></i>Fixes Applied: ' + formatNumber(totalFixes) + '</h6>';
                html += '<div class="row g-1 small">';

                if (fixCounts.retry_fixes > 0) {
                    html += '<div class="col-6 col-md-3"><span class="badge bg-info me-1">' + fixCounts.retry_fixes + '</span> Retry</div>';
                }
                if (fixCounts.automatic_fixes > 0) {
                    html += '<div class="col-6 col-md-3"><span class="badge bg-success me-1">' + fixCounts.automatic_fixes + '</span> Automatic</div>';
                }
                if (fixCounts.llm_fixes > 0) {
                    html += '<div class="col-6 col-md-3"><span class="badge bg-primary me-1">' + fixCounts.llm_fixes + '</span> LLM</div>';
                }
                if (fixCounts.manual_fixes > 0) {
                    html += '<div class="col-6 col-md-3"><span class="badge bg-secondary me-1">' + fixCounts.manual_fixes + '</span> Manual</div>';
                }

                html += '</div></div>';
            }

            // Additional stats
            html += '<div class="row g-2">';
            html += '<div class="col-6"><div class="text-center small">';
            html += '<span class="text-muted">Total Attempts:</span> <strong>' + formatNumber(gen.total_generation_attempts || 0) + '</strong>';
            html += '</div></div>';
            html += '<div class="col-6"><div class="text-center small">';
            html += '<span class="text-muted">Avg Attempts/App:</span> <strong>' + (gen.avg_attempts_per_app || 0).toFixed(1) + '</strong>';
            html += '</div></div>';
            html += '</div>';

            html += '</div></div>';
            return html;
        }

        // Render the report based on type
        function renderReport() {
            switch (reportType) {
                case 'model_analysis':
                    renderModelAnalysis();
                    break;
                case 'template_comparison':
                    renderTemplateComparison();
                    break;
                case 'tool_analysis':
                    renderToolAnalysis();
                    break;
                default:
                    renderGenericReport();
            }
        }

        // === Model Analysis Report (Comprehensive) ===
        function renderModelAnalysis() {
            const d = reportData;
            const summary = d.summary || {};
            const apps = d.apps || [];
            const tools = d.tool_summary || {};
            const findings = d.findings_breakdown || {};
            const genStats = d.generation_stats || {};
            const analysisStats = d.analysis_stats || {};
            const execMetrics = d.execution_metrics || {};
            const frameworks = d.framework_distribution || {};
            const modelInfo = d.model_info || {};
            // NEW: Quantitative metrics data
            const quantMetrics = d.quantitative_metrics || {};
            const locMetrics = d.loc_metrics || {};
            const perfMetrics = quantMetrics.performance || {};
            const aiMetrics = quantMetrics.ai_analysis || {};
            const secMetrics = quantMetrics.security || {};
            const dockerMetrics = quantMetrics.docker || {};
            const generationMetrics = quantMetrics.generation || {};

            let html = `
        <!-- Summary Metrics -->
        <div class="research-metrics">
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-layer-group"></i> Applications</div>
            <div class="research-metric-value">${formatNumber(summary.total_apps)}</div>
            <div class="research-metric-hint">${genStats.successful_generations || 0} successful</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-microscope"></i> Analyses</div>
            <div class="research-metric-value">${formatNumber(summary.total_analyses)}</div>
            <div class="research-metric-hint">${analysisStats.completed_analyses || 0} completed</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-bug"></i> Total Findings</div>
            <div class="research-metric-value">${formatNumber(summary.total_findings)}</div>
            <div class="research-metric-hint">Across all tools</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-chart-bar"></i> Avg Findings</div>
            <div class="research-metric-value">${(summary.avg_findings_per_app || 0).toFixed(1)}</div>
            <div class="research-metric-hint">Per application</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-clock"></i> Avg Duration</div>
            <div class="research-metric-value text-xs">${formatDuration(execMetrics.avg_duration_seconds)}</div>
            <div class="research-metric-hint">Per analysis</div>
            </div>
        </div>
        
        <!-- Model Info Section -->
        ${Object.keys(modelInfo).length > 0 ? `
        <div class="research-section">
            <div class="card">
            <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-robot me-2"></i>Model Information</h3>
            </div>
            <div class="card-body">
                <div class="datagrid">
                <div class="datagrid-item">
                    <div class="datagrid-title">Model Name</div>
                    <div class="datagrid-content">${h(modelInfo.model_name || d.model_slug)}</div>
                </div>
                <div class="datagrid-item">
                    <div class="datagrid-title">Provider</div>
                    <div class="datagrid-content">${h(modelInfo.provider || 'Unknown')}</div>
                </div>
                ${modelInfo.context_window ? `
                <div class="datagrid-item">
                    <div class="datagrid-title">Context Window</div>
                    <div class="datagrid-content">${formatNumber(modelInfo.context_window)} tokens</div>
                </div>` : ''}
                <div class="datagrid-item">
                    <div class="datagrid-title">Capabilities</div>
                    <div class="datagrid-content">
                    ${modelInfo.supports_vision ? '<span class="badge bg-purple-lt">Vision</span>' : ''}
                    ${modelInfo.supports_function_calling ? '<span class="badge bg-info-lt">Function Calling</span>' : ''}
                    ${modelInfo.is_free ? '<span class="badge bg-success-lt">Free</span>' : ''}
                    ${!modelInfo.supports_vision && !modelInfo.supports_function_calling && !modelInfo.is_free ? '<span class="text-muted">Standard</span>' : ''}
                    </div>
                </div>
                </div>
            </div>
            </div>
        </div>
        ` : ''}
        
        <!-- Severity Breakdown with Chart -->
        <div class="research-section">
            <div class="research-section-header">
            <h3 class="research-section-title"><i class="fa-solid fa-chart-pie"></i> Findings by Severity</h3>
            </div>
            <div class="research-data-grid cols-2">
            <div class="card">
                <div class="card-body">
                <div class="row align-items-center">
                    <div class="col-md-6">
                    <div class="chart-container">
                        <canvas id="severity-chart"></canvas>
                    </div>
                    </div>
                    <div class="col-md-6">
                    <div class="row g-3">
                        ${Object.entries(findings).map(([sev, count]) => `
                        <div class="col-6">
                            <div class="d-flex align-items-center">
                            <span class="badge bg-${sev === 'critical' ? 'danger' : sev === 'high' ? 'orange' : sev === 'medium' ? 'yellow text-dark' : sev === 'low' ? 'success' : 'info'} me-2" style="width: 12px; height: 12px; padding: 0;"></span>
                            <div>
                                <div class="h3 mb-0">${formatNumber(count)}</div>
                                <div class="text-muted small text-capitalize">${sev}</div>
                            </div>
                            </div>
                        </div>
                        `).join('')}
                    </div>
                    </div>
                </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-clock me-2"></i>Execution Metrics</h3>
                </div>
                <div class="card-body">
                <div class="mb-3">
                    <div class="d-flex justify-content-between mb-1">
                    <span class="text-muted">Total Duration</span>
                    <strong>${formatDuration(execMetrics.total_duration_seconds)}</strong>
                    </div>
                    <div class="d-flex justify-content-between mb-1">
                    <span class="text-muted">Avg Duration</span>
                    <strong>${formatDuration(execMetrics.avg_duration_seconds)}</strong>
                    </div>
                    <div class="d-flex justify-content-between mb-1">
                    <span class="text-muted">Total Queue Time</span>
                    <strong>${formatDuration(execMetrics.total_queue_time_seconds)}</strong>
                    </div>
                    <div class="d-flex justify-content-between">
                    <span class="text-muted">Total Retries</span>
                    <strong>${formatNumber(analysisStats.total_retries)}</strong>
                    </div>
                </div>
                </div>
            </div>
            </div>
        </div>
        
        <!-- Generation & Framework Stats -->
        <div class="research-section">
            <div class="research-data-grid cols-2">
            <div class="card">
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-hammer me-2"></i>Generation Statistics</h3>
                </div>
                <div class="card-body">
                <div class="row g-3">
                    <div class="col-6 col-md-4">
                    <div class="text-center">
                        <div class="h2 mb-0 text-success">${formatNumber(genStats.successful_generations)}</div>
                        <div class="text-muted small">Successful</div>
                    </div>
                    </div>
                    <div class="col-6 col-md-4">
                    <div class="text-center">
                        <div class="h2 mb-0 text-danger">${formatNumber(genStats.failed_generations)}</div>
                        <div class="text-muted small">Failed</div>
                    </div>
                    </div>
                    <div class="col-6 col-md-4">
                    <div class="text-center">
                        <div class="h2 mb-0 text-info">${formatNumber(genStats.apps_with_fixes)}</div>
                        <div class="text-muted small">With Fixes</div>
                    </div>
                    </div>
                    <div class="col-4">
                    <div class="text-center">
                        <div class="h4 mb-0">${formatNumber(genStats.total_scripted_fixes)}</div>
                        <div class="text-muted small">Script Fixes</div>
                    </div>
                    </div>
                    <div class="col-4">
                    <div class="text-center">
                        <div class="h4 mb-0">${formatNumber(genStats.total_llm_fixes)}</div>
                        <div class="text-muted small">LLM Fixes</div>
                    </div>
                    </div>
                    <div class="col-4">
                    <div class="text-center">
                        <div class="h4 mb-0">${formatNumber(genStats.total_manual_fixes)}</div>
                        <div class="text-muted small">Manual Fixes</div>
                    </div>
                    </div>
                </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-layer-group me-2"></i>Framework Distribution</h3>
                </div>
                <div class="card-body">
                <div class="row">
                    <div class="col-6">
                    <h5 class="text-muted mb-2">Backend</h5>
                    ${Object.entries(frameworks.backend || {}).length > 0 ?
                    Object.entries(frameworks.backend).map(([fw, count]) => `
                        <div class="d-flex justify-content-between mb-1">
                            <span>${h(fw)}</span>
                            <strong>${count}</strong>
                        </div>
                        `).join('') : '<span class="text-muted">No data</span>'}
                    </div>
                    <div class="col-6">
                    <h5 class="text-muted mb-2">Frontend</h5>
                    ${Object.entries(frameworks.frontend || {}).length > 0 ?
                    Object.entries(frameworks.frontend).map(([fw, count]) => `
                        <div class="d-flex justify-content-between mb-1">
                            <span>${h(fw)}</span>
                            <strong>${count}</strong>
                        </div>
                        `).join('') : '<span class="text-muted">No data</span>'}
                    </div>
                </div>
                </div>
            </div>
            </div>
        </div>
        
        <!-- Quantitative Metrics Section -->
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#quant-section">
            <h3 class="research-section-title"><i class="fa-solid fa-calculator"></i> Quantitative Metrics</h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse show" id="quant-section">
            <!-- Lines of Code & Issue Density -->
            <div class="card mb-3">
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-code me-2"></i>Lines of Code & Issue Density</h3>
                </div>
                <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-3 col-6">
                    <div class="text-center p-2 bg-light rounded">
                        <div class="h2 mb-0 text-primary">${formatNumber(locMetrics.total_loc || 0)}</div>
                        <div class="text-muted small">Total Lines of Code</div>
                    </div>
                    </div>
                    <div class="col-md-3 col-6">
                    <div class="text-center p-2 bg-light rounded">
                        <div class="h2 mb-0 text-info">${formatNumber(locMetrics.backend_loc || 0)}</div>
                        <div class="text-muted small">Backend LOC</div>
                    </div>
                    </div>
                    <div class="col-md-3 col-6">
                    <div class="text-center p-2 bg-light rounded">
                        <div class="h2 mb-0 text-purple">${formatNumber(locMetrics.frontend_loc || 0)}</div>
                        <div class="text-muted small">Frontend LOC</div>
                    </div>
                    </div>
                    <div class="col-md-3 col-6">
                    <div class="text-center p-2 bg-light rounded">
                        <div class="h2 mb-0 ${(locMetrics.issues_per_100_loc || 0) > 5 ? 'text-danger' : (locMetrics.issues_per_100_loc || 0) > 2 ? 'text-warning' : 'text-success'}">${(locMetrics.issues_per_100_loc || 0).toFixed(2)}</div>
                        <div class="text-muted small">Issues per 100 LOC</div>
                    </div>
                    </div>
                </div>
                ${buildLocPerAppTable(locMetrics.per_app || [])}
                </div>
            </div>
            
            <!-- Performance Metrics -->
            ${buildPerformanceMetricsCard(perfMetrics)}
            
            <!-- Docker/Container Status & Generation Summary -->
            <div class="research-data-grid cols-2">
                ${buildDockerStatusCard(dockerMetrics)}
                ${buildGenerationSummaryCard(generationMetrics)}
            </div>
            
            <!-- Security & AI Analysis Metrics -->
            <div class="research-data-grid cols-2">
                ${buildSecurityMetricsCard(secMetrics)}
                ${buildAiMetricsCard(aiMetrics)}
            </div>
            
            <!-- Generation Efficiency -->
            <div class="card mt-3">
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-chart-line me-2"></i>Generation Efficiency Summary</h3>
                </div>
                <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-2 col-4">
                    <div class="text-center">
                        <div class="h4 mb-0 text-success">${formatNumber(genStats.successful_generations || 0)}</div>
                        <div class="text-muted small">Successful</div>
                    </div>
                    </div>
                    <div class="col-md-2 col-4">
                    <div class="text-center">
                        <div class="h4 mb-0 text-danger">${formatNumber(genStats.failed_generations || 0)}</div>
                        <div class="text-muted small">Failed</div>
                    </div>
                    </div>
                    <div class="col-md-2 col-4">
                    <div class="text-center">
                        <div class="h4 mb-0">${((genStats.successful_generations || 0) / Math.max(1, (genStats.successful_generations || 0) + (genStats.failed_generations || 0)) * 100).toFixed(1)}%</div>
                        <div class="text-muted small">Success Rate</div>
                    </div>
                    </div>
                    <div class="col-md-2 col-4">
                    <div class="text-center">
                        <div class="h4 mb-0">${formatNumber(genStats.total_scripted_fixes + genStats.total_llm_fixes + genStats.total_manual_fixes || 0)}</div>
                        <div class="text-muted small">Total Fixes</div>
                    </div>
                    </div>
                    <div class="col-md-2 col-4">
                    <div class="text-center">
                        <div class="h4 mb-0">${(locMetrics.avg_loc_per_app || 0).toFixed(0)}</div>
                        <div class="text-muted small">Avg LOC/App</div>
                    </div>
                    </div>
                    <div class="col-md-2 col-4">
                    <div class="text-center">
                        <div class="h4 mb-0">${((summary.total_findings || 0) / Math.max(1, summary.total_apps || 1)).toFixed(1)}</div>
                        <div class="text-muted small">Avg Issues/App</div>
                    </div>
                    </div>
                </div>
                </div>
            </div>
            </div>
        </div>
        
        <!-- Applications Table (Expanded) -->
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#apps-section">
            <h3 class="research-section-title"><i class="fa-solid fa-folder"></i> Applications <span class="badge bg-secondary ms-2">${apps.length}</span></h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse show" id="apps-section">
            <div class="card">
                <div class="table-responsive">
                <table class="table table-vcenter card-table table-hover">
                    <thead>
                    <tr>
                        <th>App</th>
                        <th>Template</th>
                        <th>Frameworks</th>
                        <th>Status</th>
                        <th>Findings</th>
                        <th>Severity Breakdown</th>
                        <th>Duration</th>
                        <th>Fixes</th>
                    </tr>
                    </thead>
                    <tbody>
                    ${apps.map(app => `
                        <tr>
                        <td>
                            <strong>App ${app.app_number}</strong>
                            <div class="text-muted small">${h(app.task_id || '')}</div>
                        </td>
                        <td><span class="badge bg-blue-lt">${h(app.template_slug || 'N/A')}</span></td>
                        <td>
                            ${app.backend_framework ? `<span class="badge bg-purple-lt me-1">${h(app.backend_framework)}</span>` : ''}
                            ${app.frontend_framework ? `<span class="badge bg-cyan-lt">${h(app.frontend_framework)}</span>` : ''}
                            ${!app.backend_framework && !app.frontend_framework ? '<span class="text-muted">—</span>' : ''}
                        </td>
                        <td>${statusBadge(app.status, app.task_status)}</td>
                        <td><strong>${formatNumber(app.findings_count)}</strong></td>
                        <td>
                            <div class="d-flex gap-1 flex-wrap">
                            ${Object.entries(app.severity_breakdown || {}).filter(([s, c]) => c > 0).map(([s, c]) => `
                                <span class="badge bg-${s === 'critical' ? 'danger' : s === 'high' ? 'orange' : s === 'medium' ? 'yellow text-dark' : s === 'low' ? 'success' : 'info'}">${s}: ${c}</span>
                            `).join('') || '<span class="text-muted">No findings</span>'}
                            </div>
                        </td>
                        <td>${formatDuration(app.duration_seconds)}</td>
                        <td>
                            ${app.total_fixes > 0 ? `<span class="badge bg-info-lt">${app.total_fixes} fixes</span>` : '<span class="text-muted">—</span>'}
                        </td>
                        </tr>
                        ${app.subtasks && app.subtasks.length > 0 ? `
                        <tr class="bg-light">
                        <td colspan="8" class="py-2">
                            <div class="ms-4">
                            <small class="text-muted">Subtasks: </small>
                            ${app.subtasks.map(st => `
                                <span class="badge ${st.status === 'success' ? 'bg-success-lt' : st.status === 'error' ? 'bg-danger-lt' : 'bg-secondary-lt'} me-1">
                                ${h(st.service)} ${st.issues_found ? `(${st.issues_found})` : ''}
                                </span>
                            `).join('')}
                            </div>
                        </td>
                        </tr>
                        ` : ''}
                    `).join('')}
                    </tbody>
                </table>
                </div>
            </div>
            </div>
        </div>
        
        <!-- Tool Performance (Enhanced) -->
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#tools-section">
            <h3 class="research-section-title"><i class="fa-solid fa-wrench"></i> Tool Performance <span class="badge bg-secondary ms-2">${Object.keys(tools).length}</span></h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse show" id="tools-section">
            <div class="card">
                <div class="table-responsive">
                <table class="table table-vcenter card-table table-hover">
                    <thead>
                    <tr>
                        <th>Tool</th>
                        <th>Runs</th>
                        <th>Success Rate</th>
                        <th>Total Findings</th>
                        <th>Avg/Run</th>
                        <th>Avg Duration</th>
                        <th>Status</th>
                    </tr>
                    </thead>
                    <tbody>
                    ${Object.entries(tools).map(([name, tool]) => `
                        <tr>
                        <td><strong>${h(tool.display_name || name)}</strong></td>
                        <td>${formatNumber(tool.total_runs || tool.executions)}</td>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                            <div class="progress flex-grow-1" style="height: 6px; min-width: 60px;">
                                <div class="progress-bar ${(tool.success_rate || 0) >= 80 ? 'bg-success' : (tool.success_rate || 0) >= 50 ? 'bg-warning' : 'bg-danger'}" style="width: ${tool.success_rate || 0}%"></div>
                            </div>
                            <span class="small">${tool.success_rate ? tool.success_rate.toFixed(0) + '%' : 'N/A'}</span>
                            </div>
                        </td>
                        <td>${formatNumber(tool.total_findings)}</td>
                        <td>${(tool.findings_per_run || 0).toFixed(1)}</td>
                        <td>${formatDuration(tool.avg_duration)}</td>
                        <td>
                            <span class="tool-status-${tool.overall_status}">
                            <i class="fa-solid fa-${tool.overall_status === 'success' ? 'check-circle' : tool.overall_status === 'error' ? 'times-circle' : 'minus-circle'} me-1"></i>
                            ${tool.overall_status || 'unknown'}
                            </span>
                        </td>
                        </tr>
                    `).join('')}
                    </tbody>
                </table>
                </div>
            </div>
            </div>
        </div>
        
        <!-- Sample Findings (Collapsible) -->
        ${(d.findings || []).length > 0 ? `
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#findings-section">
            <h3 class="research-section-title"><i class="fa-solid fa-bug"></i> Sample Findings <span class="badge bg-secondary ms-2">${Math.min(50, d.findings.length)} of ${d.findings.length}</span></h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse" id="findings-section">
            <div class="card">
                <div class="card-body" style="max-height: 500px; overflow-y: auto;">
                ${d.findings.slice(0, 50).map(f => `
                    <div class="finding-item severity-${(f.severity || 'info').toLowerCase()} mb-2">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                        <strong>${h(f.message || f.title || 'Finding')}</strong>
                        ${f.tool ? `<span class="badge bg-secondary-lt ms-2">${h(f.tool)}</span>` : ''}
                        </div>
                        ${severityBadge(f.severity)}
                    </div>
                    <div class="text-muted small mt-1">
                        ${f.file ? `<i class="fa-solid fa-file me-1"></i>${h(f.file)}${f.line ? `:${f.line}` : ''}` : ''}
                        ${f.rule_id ? ` | Rule: ${h(f.rule_id)}` : ''}
                    </div>
                    </div>
                `).join('')}
                </div>
            </div>
            </div>
        </div>
        ` : ''}
        `;

            reportContent.innerHTML = html;

            // Initialize severity chart
            setTimeout(() => {
                const ctx = document.getElementById('severity-chart');
                if (ctx && Object.keys(findings).length > 0) {
                    const severityColors = {
                        critical: '#d63939',
                        high: '#f76707',
                        medium: '#f59f00',
                        low: '#2fb344',
                        info: '#0ea5e9'
                    };

                    severityChart = new Chart(ctx, {
                        type: 'doughnut',
                        data: {
                            labels: Object.keys(findings).map(s => s.charAt(0).toUpperCase() + s.slice(1)),
                            datasets: [{
                                data: Object.values(findings),
                                backgroundColor: Object.keys(findings).map(s => severityColors[s] || '#868e96'),
                                borderWidth: 0
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    display: false
                                }
                            },
                            cutout: '60%'
                        }
                    });
                }
            }, 100);
        }

        // === Template Comparison Report ===
        function renderTemplateComparison() {
            const d = reportData;
            const summary = d.summary || {};
            const models = d.models || [];
            const rankings = d.rankings || {};
            const comparison = d.comparison || {};
            const frameworks = d.framework_distribution || {};
            const findingsBreakdown = d.findings_breakdown || summary.severity_breakdown || {};

            // Calculate additional metrics
            const totalFindings = summary.total_findings || 0;
            const avgFindingsPerModel = models.length > 0 ? (totalFindings / models.length).toFixed(1) : 0;
            const bestScore = rankings.best_overall?.score?.toFixed(1) || 'N/A';
            const worstScore = rankings.worst_overall?.score?.toFixed(1) || 'N/A';
            const scoreSpread = (rankings.worst_overall?.score && rankings.best_overall?.score)
                ? (rankings.worst_overall.score - rankings.best_overall.score).toFixed(1)
                : 'N/A';

            let html = `
        <!-- Key Metrics Summary -->
        <div class="research-metrics">
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-robot"></i> Models Compared</div>
            <div class="research-metric-value tone-primary">${formatNumber(summary.models_compared || 0)}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-microscope"></i> Total Analyses</div>
            <div class="research-metric-value tone-info">${formatNumber(summary.total_analyses || 0)}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-bug"></i> Total Findings</div>
            <div class="research-metric-value tone-warning">${formatNumber(totalFindings)}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-chart-bar"></i> Avg per Model</div>
            <div class="research-metric-value">${avgFindingsPerModel}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-link"></i> Common Issues</div>
            <div class="research-metric-value tone-success">${formatNumber(summary.common_issues_count || 0)}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-clock"></i> Avg Duration</div>
            <div class="research-metric-value text-xs">${formatDuration(summary.avg_duration_seconds || 0)}</div>
            </div>
        </div>
        
        <!-- Severity Distribution Visual -->
        <div class="research-section">
            <div class="research-section-header">
            <h3 class="research-section-title"><i class="fa-solid fa-chart-bar"></i> Severity Distribution</h3>
            </div>
            <div class="research-data-grid cols-2">
            <div class="card">
                <div class="card-body">
                <div class="chart-container" id="severity-chart-container">
                    <canvas id="severityDistributionChart"></canvas>
                </div>
                <div class="row mt-4">
                    <div class="col">
                    <div class="d-flex align-items-center">
                        <span class="badge bg-danger me-2">&nbsp;</span>
                        <span>Critical: <strong>${formatNumber(findingsBreakdown.critical || 0)}</strong></span>
                    </div>
                    </div>
                    <div class="col">
                    <div class="d-flex align-items-center">
                        <span class="badge bg-orange me-2">&nbsp;</span>
                        <span>High: <strong>${formatNumber(findingsBreakdown.high || 0)}</strong></span>
                    </div>
                    </div>
                    <div class="col">
                    <div class="d-flex align-items-center">
                        <span class="badge bg-yellow me-2">&nbsp;</span>
                        <span>Medium: <strong>${formatNumber(findingsBreakdown.medium || 0)}</strong></span>
                    </div>
                    </div>
                    <div class="col">
                    <div class="d-flex align-items-center">
                        <span class="badge bg-success me-2">&nbsp;</span>
                        <span>Low: <strong>${formatNumber(findingsBreakdown.low || 0)}</strong></span>
                    </div>
                    </div>
                    <div class="col">
                    <div class="d-flex align-items-center">
                        <span class="badge bg-info me-2">&nbsp;</span>
                        <span>Info: <strong>${formatNumber(findingsBreakdown.info || 0)}</strong></span>
                    </div>
                    </div>
                </div>
                </div>
            </div>
            
            <div class="card h-100">
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-layer-group me-2"></i>Framework Distribution</h3>
                </div>
                <div class="card-body">
                <h5 class="text-muted mb-2">Backend Frameworks</h5>
                ${Object.entries(frameworks.backend || {}).length > 0 ?
                    Object.entries(frameworks.backend).map(([fw, count]) => `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-purple-lt">${h(fw)}</span>
                        <strong>${count} model${count > 1 ? 's' : ''}</strong>
                    </div>
                    `).join('') : '<span class="text-muted">No data available</span>'}
                
                <hr class="my-3">
                
                <h5 class="text-muted mb-2">Frontend Frameworks</h5>
                ${Object.entries(frameworks.frontend || {}).length > 0 ?
                    Object.entries(frameworks.frontend).map(([fw, count]) => `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-cyan-lt">${h(fw)}</span>
                        <strong>${count} model${count > 1 ? 's' : ''}</strong>
                    </div>
                    `).join('') : '<span class="text-muted">No data available</span>'}
                </div>
            </div>
            </div>
        </div>
        
        <!-- Rankings Section -->
        ${rankings.best_overall || rankings.worst_overall ? `
        <div class="research-section">
            <div class="research-data-grid cols-2">
            <div class="card border-success">
                <div class="card-status-top bg-success"></div>
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-trophy text-success me-2"></i>Best Performing Model</h3>
                </div>
                <div class="card-body">
                ${rankings.best_overall ? `
                    <div class="d-flex align-items-center mb-3">
                    <div class="avatar avatar-lg bg-success-lt me-3">
                        <i class="fa-solid fa-medal fa-lg text-success"></i>
                    </div>
                    <div>
                        <h2 class="mb-0">${h(rankings.best_overall.model_name || rankings.best_overall.model)}</h2>
                        <div class="text-muted">Lowest weighted score</div>
                    </div>
                    </div>
                    <div class="row text-center">
                    <div class="col-4">
                        <div class="h3 mb-0">${rankings.best_overall.score?.toFixed(1) || 'N/A'}</div>
                        <div class="text-muted small">Score</div>
                    </div>
                    <div class="col-4">
                        <div class="h3 mb-0">${formatNumber(rankings.best_overall.total_findings || 0)}</div>
                        <div class="text-muted small">Findings</div>
                    </div>
                    <div class="col-4">
                        <div class="h3 mb-0">#1</div>
                        <div class="text-muted small">Rank</div>
                    </div>
                    </div>
                ` : '<div class="text-muted">No data available</div>'}
                </div>
            </div>
            
            <div class="card border-danger">
                <div class="card-status-top bg-danger"></div>
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-triangle-exclamation text-danger me-2"></i>Needs Improvement</h3>
                </div>
                <div class="card-body">
                ${rankings.worst_overall ? `
                    <div class="d-flex align-items-center mb-3">
                    <div class="avatar avatar-lg bg-danger-lt me-3">
                        <i class="fa-solid fa-exclamation-circle fa-lg text-danger"></i>
                    </div>
                    <div>
                        <h2 class="mb-0">${h(rankings.worst_overall.model_name || rankings.worst_overall.model)}</h2>
                        <div class="text-muted">Highest weighted score</div>
                    </div>
                    </div>
                    <div class="row text-center">
                    <div class="col-4">
                        <div class="h3 mb-0">${rankings.worst_overall.score?.toFixed(1) || 'N/A'}</div>
                        <div class="text-muted small">Score</div>
                    </div>
                    <div class="col-4">
                        <div class="h3 mb-0">${formatNumber(rankings.worst_overall.total_findings || 0)}</div>
                        <div class="text-muted small">Findings</div>
                    </div>
                    <div class="col-4">
                        <div class="h3 mb-0">#${models.length || '?'}</div>
                        <div class="text-muted small">Rank</div>
                    </div>
                    </div>
                ` : '<div class="text-muted">No data available</div>'}
                </div>
            </div>
            </div>
        </div>
        ` : ''}
        
        <!-- Full Rankings Table -->
        ${rankings.all_ranked && rankings.all_ranked.length > 0 ? `
        <div class="research-section">
            <div class="research-section-header">
            <h3 class="research-section-title"><i class="fa-solid fa-ranking-star"></i> Complete Model Rankings</h3>
            <div class="text-muted small">Ranked by weighted severity score</div>
            </div>
            <div class="card">
            <div class="table-responsive">
                <table class="table table-vcenter card-table table-hover">
                <thead>
                    <tr>
                    <th style="width: 80px">Rank</th>
                    <th>Model</th>
                    <th class="text-center">Critical</th>
                    <th class="text-center">High</th>
                    <th class="text-center">Medium</th>
                    <th class="text-center">Low</th>
                    <th class="text-center">Total Findings</th>
                    <th class="text-center">Score</th>
                    <th style="width: 150px">Visual</th>
                    </tr>
                </thead>
                <tbody>
                    ${rankings.all_ranked.map((r, idx) => {
                        const m = models.find(m => m.model_slug === r.model) || {};
                        const sev = m.severity_breakdown || {};
                        const maxScore = rankings.worst_overall?.score || 1;
                        const scorePercent = maxScore > 0 ? ((r.score || 0) / maxScore * 100) : 0;
                        return `
                        <tr class="${idx === 0 ? 'table-success' : idx === rankings.all_ranked.length - 1 ? 'table-danger' : ''}">
                        <td>
                            <div class="d-flex align-items-center">
                            ${idx === 0 ? '<i class="fa-solid fa-crown text-warning me-2"></i>' : ''}
                            <span class="badge ${idx === 0 ? 'bg-success' : idx < 3 ? 'bg-primary' : 'bg-secondary'}">#${r.rank}</span>
                            </div>
                        </td>
                        <td>
                            <strong>${h(r.model_name || r.model)}</strong>
                        </td>
                        <td class="text-center severity-critical"><strong>${formatNumber(sev.critical || 0)}</strong></td>
                        <td class="text-center severity-high"><strong>${formatNumber(sev.high || 0)}</strong></td>
                        <td class="text-center severity-medium"><strong>${formatNumber(sev.medium || 0)}</strong></td>
                        <td class="text-center severity-low"><strong>${formatNumber(sev.low || 0)}</strong></td>
                        <td class="text-center"><strong>${formatNumber(r.total_findings || 0)}</strong></td>
                        <td class="text-center"><strong>${r.score?.toFixed(1) || 'N/A'}</strong></td>
                        <td>
                            <div class="progress" style="height: 8px;">
                            <div class="progress-bar ${idx === 0 ? 'bg-success' : scorePercent > 50 ? 'bg-danger' : 'bg-warning'}" style="width: ${scorePercent}%"></div>
                            </div>
                        </td>
                        </tr>
                    `;
                    }).join('')}
                </tbody>
                </table>
            </div>
            </div>
        </div>
        ` : ''}
        
        <!-- Per-Severity Best Models -->
        ${rankings.by_severity && Object.keys(rankings.by_severity).length > 0 ? `
        <div class="research-section">
            <div class="research-section-header">
            <h3 class="research-section-title"><i class="fa-solid fa-award"></i> Best Models by Severity Category</h3>
            </div>
            <div class="research-data-grid cols-4">
            ${Object.entries(rankings.by_severity).map(([sev, data]) => {
                        const sevColors = {
                            critical: { bg: 'danger', icon: 'skull-crossbones' },
                            high: { bg: 'orange', icon: 'exclamation-triangle' },
                            medium: { bg: 'yellow', icon: 'exclamation-circle' },
                            low: { bg: 'success', icon: 'info-circle' }
                        };
                        const c = sevColors[sev] || { bg: 'secondary', icon: 'question' };
                        return `
                <div class="card card-sm border-${c.bg}">
                    <div class="card-status-start bg-${c.bg}"></div>
                    <div class="card-body">
                    <div class="d-flex align-items-center mb-2">
                        <i class="fa-solid fa-${c.icon} text-${c.bg} me-2"></i>
                        <span class="text-uppercase text-muted small">Fewest ${sev}</span>
                    </div>
                    <h4 class="mb-1">${h(data?.model_name || data?.model || 'N/A')}</h4>
                    <div class="text-muted">${formatNumber(data?.count || 0)} findings</div>
                    </div>
                </div>
                `;
                    }).join('')}
            </div>
        </div>
        ` : ''}
        
        <!-- Common Issues Section -->
        ${comparison.common_issues && comparison.common_issues.length > 0 ? `
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#common-issues-section">
            <h3 class="research-section-title"><i class="fa-solid fa-link"></i> Common Issues <span class="badge bg-warning ms-2">${comparison.common_issues.length}</span></h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse show" id="common-issues-section">
            <div class="card">
                <div class="card-body">
                <p class="text-muted mb-3">These issues were found across multiple models, indicating common patterns or template-inherent problems.</p>
                <div class="list-group list-group-flush">
                    ${comparison.common_issues.slice(0, 20).map(issue => `
                    <div class="list-group-item finding-item severity-${(issue.severity || 'info').toLowerCase()}">
                        <div class="d-flex w-100 justify-content-between align-items-start">
                        <div>
                            ${severityBadge(issue.severity)}
                            <strong class="ms-2">${h(issue.rule_id || issue.tool || 'Unknown')}</strong>
                        </div>
                        <small class="text-muted">${h(issue.tool || '')}</small>
                        </div>
                        <p class="mb-1 mt-2">${h(issue.message || 'No description')}</p>
                        ${issue.file ? `<small class="text-muted"><i class="fa-solid fa-file-code me-1"></i>${h(issue.file)}${issue.line ? ':' + issue.line : ''}</small>` : ''}
                    </div>
                    `).join('')}
                </div>
                ${comparison.common_issues.length > 20 ? `<div class="text-muted mt-3">Showing 20 of ${comparison.common_issues.length} common issues</div>` : ''}
                </div>
            </div>
            </div>
        </div>
        ` : ''}
        
        <!-- Detailed Model Data -->
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#models-detail-section">
            <h3 class="research-section-title"><i class="fa-solid fa-robot"></i> Detailed Model Analysis <span class="badge bg-secondary ms-2">${models.length}</span></h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse show" id="models-detail-section">
            <div class="card">
                <div class="table-responsive">
                <table class="table table-vcenter card-table table-hover">
                    <thead>
                    <tr>
                        <th>Model</th>
                        <th>Task Status</th>
                        <th>Frameworks</th>
                        <th class="text-center">Critical</th>
                        <th class="text-center">High</th>
                        <th class="text-center">Medium</th>
                        <th class="text-center">Low</th>
                        <th class="text-center">Total</th>
                        <th class="text-center">Score</th>
                        <th>Duration</th>
                    </tr>
                    </thead>
                    <tbody>
                    ${models.map(m => {
                        const sev = m.severity_breakdown || {};
                        const isWinner = rankings.best_overall?.model === m.model_slug;
                        const isWorst = rankings.worst_overall?.model === m.model_slug;
                        return `
                        <tr class="${isWinner ? 'table-success' : isWorst ? 'table-danger' : ''}">
                            <td>
                            <div class="d-flex align-items-center">
                                ${isWinner ? '<i class="fa-solid fa-crown text-warning me-2"></i>' : ''}
                                <div>
                                <strong>${h(m.model_name || m.model_slug)}</strong>
                                ${isWinner ? '<span class="badge bg-success ms-2">Best</span>' : ''}
                                ${isWorst ? '<span class="badge bg-danger ms-2">Most Issues</span>' : ''}
                                <div class="text-muted small">App #${m.app_number || '?'}</div>
                                </div>
                            </div>
                            </td>
                            <td>${statusBadge(m.status, m.task_status)}</td>
                            <td>
                            ${m.backend_framework ? `<span class="badge bg-purple-lt me-1">${h(m.backend_framework)}</span>` : ''}
                            ${m.frontend_framework ? `<span class="badge bg-cyan-lt">${h(m.frontend_framework)}</span>` : ''}
                            ${!m.backend_framework && !m.frontend_framework ? '<span class="text-muted">—</span>' : ''}
                            </td>
                            <td class="text-center severity-critical"><strong>${formatNumber(sev.critical || 0)}</strong></td>
                            <td class="text-center severity-high"><strong>${formatNumber(sev.high || 0)}</strong></td>
                            <td class="text-center severity-medium"><strong>${formatNumber(sev.medium || 0)}</strong></td>
                            <td class="text-center severity-low"><strong>${formatNumber(sev.low || 0)}</strong></td>
                            <td class="text-center"><strong>${formatNumber(m.total_findings || m.findings_count || 0)}</strong></td>
                            <td class="text-center"><strong>${m.score?.toFixed(1) || 'N/A'}</strong></td>
                            <td>${formatDuration(m.duration_seconds)}</td>
                        </tr>
                        `;
                    }).join('')}
                    </tbody>
                </table>
                </div>
            </div>
            </div>
        </div>
        
        <!-- Research Notes -->
        <div class="research-section">
            <div class="card border-info">
            <div class="card-header bg-info-lt">
                <h3 class="card-title"><i class="fa-solid fa-lightbulb me-2"></i>Research Insights</h3>
            </div>
            <div class="card-body">
                <div class="row">
                <div class="col-md-6">
                    <h5>Key Findings</h5>
                    <ul class="mb-0">
                    <li><strong>Score Spread:</strong> ${scoreSpread} points between best and worst models</li>
                    <li><strong>Average Findings:</strong> ${avgFindingsPerModel} issues per model</li>
                    <li><strong>Common Issues:</strong> ${formatNumber(summary.common_issues_count || 0)} issues found across multiple models</li>
                    ${rankings.best_overall ? `<li><strong>Best Performer:</strong> ${h(rankings.best_overall.model_name || rankings.best_overall.model)} with ${formatNumber(rankings.best_overall.total_findings || 0)} total findings</li>` : ''}
                    </ul>
                </div>
                <div class="col-md-6">
                    <h5>Methodology</h5>
                    <ul class="mb-0">
                    <li><strong>Scoring Formula:</strong> Critical×100 + High×10 + Medium×3 + Low×1</li>
                    <li><strong>Lower scores indicate better code quality</strong></li>
                    <li>Analysis based on ${formatNumber(summary.total_analyses || 0)} task executions</li>
                    <li>Common issues identified by rule_id matching</li>
                    </ul>
                </div>
                </div>
            </div>
            </div>
        </div>
        `;

            reportContent.innerHTML = html;

            // Initialize severity chart
            setTimeout(() => {
                const ctx = document.getElementById('severityDistributionChart');
                if (ctx && typeof Chart !== 'undefined') {
                    new Chart(ctx, {
                        type: 'doughnut',
                        data: {
                            labels: ['Critical', 'High', 'Medium', 'Low', 'Info'],
                            datasets: [{
                                data: [
                                    findingsBreakdown.critical || 0,
                                    findingsBreakdown.high || 0,
                                    findingsBreakdown.medium || 0,
                                    findingsBreakdown.low || 0,
                                    findingsBreakdown.info || 0
                                ],
                                backgroundColor: ['#d63939', '#f76707', '#f59f00', '#2fb344', '#0ea5e9']
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'bottom' }
                            }
                        }
                    });
                }
            }, 100);
        }

        // === Tool Analysis Report ===
        function renderToolAnalysis() {
            const d = reportData;
            const summary = d.summary || {};
            const tools = d.tools || [];
            const categories = d.categories || {};
            const topPerformers = d.top_performers || {};
            const byModel = d.by_model || {};
            const filter = d.filter || {};
            const findingsBreakdown = d.findings_breakdown || summary.severity_breakdown || {};
            const findings = d.findings || [];

            // Calculate additional metrics
            const totalFindings = summary.total_findings || 0;
            const avgFindingsPerRun = tools.length > 0
                ? (tools.reduce((acc, t) => acc + (t.total_findings || 0), 0) / summary.total_runs).toFixed(2)
                : 0;
            const mostEffective = tools.length > 0
                ? tools.reduce((best, t) => (t.total_findings || 0) > (best.total_findings || 0) ? t : best, tools[0])
                : null;
            const mostReliable = tools.length > 0
                ? tools.reduce((best, t) => (t.success_rate || 0) > (best.success_rate || 0) ? t : best, tools[0])
                : null;

            // Calculate category stats
            const categoryStats = Object.entries(categories).map(([name, data]) => ({
                name,
                ...data,
                avgFindings: data.total_runs > 0 ? (data.total_findings / data.total_runs).toFixed(1) : 0
            }));

            let html = `
        <!-- Key Metrics Summary -->
        <div class="research-metrics">
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-wrench"></i> Tools Analyzed</div>
            <div class="research-metric-value tone-primary">${formatNumber(summary.tools_analyzed || 0)}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-play"></i> Total Executions</div>
            <div class="research-metric-value tone-info">${formatNumber(summary.total_runs || 0)}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-bug"></i> Total Findings</div>
            <div class="research-metric-value tone-warning">${formatNumber(totalFindings)}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-check-circle"></i> Avg Success Rate</div>
            <div class="research-metric-value ${(summary.avg_success_rate || 0) >= 90 ? 'tone-success' : (summary.avg_success_rate || 0) >= 70 ? 'tone-warning' : 'tone-danger'}">${summary.avg_success_rate ? summary.avg_success_rate.toFixed(0) + '%' : 'N/A'}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-chart-bar"></i> Findings/Run</div>
            <div class="research-metric-value">${avgFindingsPerRun}</div>
            </div>
            <div class="research-metric-card">
            <div class="research-metric-label"><i class="fa-solid fa-layer-group"></i> Categories</div>
            <div class="research-metric-value">${Object.keys(categories).length}</div>
            </div>
        </div>
        
        <!-- Severity Distribution -->
        <div class="research-section">
            <div class="research-section-header">
            <h3 class="research-section-title"><i class="fa-solid fa-chart-pie"></i> Findings by Severity</h3>
            </div>
            <div class="research-data-grid cols-2">
            <div class="card">
                <div class="card-body">
                <div class="chart-container" id="tool-severity-chart-container">
                    <canvas id="toolSeverityChart"></canvas>
                </div>
                <div class="row mt-4">
                    <div class="col">
                    <div class="d-flex align-items-center justify-content-center">
                        <span class="badge bg-danger me-2">&nbsp;</span>
                        <span>Critical: <strong>${formatNumber(findingsBreakdown.critical || 0)}</strong></span>
                    </div>
                    </div>
                    <div class="col">
                    <div class="d-flex align-items-center justify-content-center">
                        <span class="badge bg-orange me-2">&nbsp;</span>
                        <span>High: <strong>${formatNumber(findingsBreakdown.high || 0)}</strong></span>
                    </div>
                    </div>
                    <div class="col">
                    <div class="d-flex align-items-center justify-content-center">
                        <span class="badge bg-yellow me-2">&nbsp;</span>
                        <span>Medium: <strong>${formatNumber(findingsBreakdown.medium || 0)}</strong></span>
                    </div>
                    </div>
                    <div class="col">
                    <div class="d-flex align-items-center justify-content-center">
                        <span class="badge bg-success me-2">&nbsp;</span>
                        <span>Low: <strong>${formatNumber(findingsBreakdown.low || 0)}</strong></span>
                    </div>
                    </div>
                </div>
                </div>
            </div>
            
            <div class="card h-100">
                <div class="card-header">
                <h3 class="card-title"><i class="fa-solid fa-trophy me-2"></i>Top Performers</h3>
                </div>
                <div class="card-body">
                ${mostEffective ? `
                <div class="mb-4">
                    <div class="text-muted small text-uppercase mb-1">Most Findings Detected</div>
                    <div class="d-flex align-items-center">
                    <div class="avatar bg-warning-lt me-3">
                        <i class="fa-solid fa-bug text-warning"></i>
                    </div>
                    <div>
                        <h4 class="mb-0">${h(mostEffective.display_name || mostEffective.name)}</h4>
                        <div class="text-muted">${formatNumber(mostEffective.total_findings || 0)} findings</div>
                    </div>
                    </div>
                </div>
                ` : ''}
                ${mostReliable ? `
                <div class="mb-4">
                    <div class="text-muted small text-uppercase mb-1">Most Reliable</div>
                    <div class="d-flex align-items-center">
                    <div class="avatar bg-success-lt me-3">
                        <i class="fa-solid fa-check-circle text-success"></i>
                    </div>
                    <div>
                        <h4 class="mb-0">${h(mostReliable.display_name || mostReliable.name)}</h4>
                        <div class="text-muted">${mostReliable.success_rate?.toFixed(0) || 0}% success rate</div>
                    </div>
                    </div>
                </div>
                ` : ''}
                <div class="text-muted small text-uppercase mb-1">Tool Categories</div>
                <div class="d-flex flex-wrap gap-1">
                    ${Object.keys(categories).map(cat => `
                    <span class="badge bg-azure-lt">${h(cat)}</span>
                    `).join('')}
                </div>
                </div>
            </div>
            </div>
        </div>
        
        <!-- Category Breakdown -->
        ${Object.keys(categories).length > 0 ? `
        <div class="research-section">
            <div class="research-section-header">
            <h3 class="research-section-title"><i class="fa-solid fa-layer-group"></i> Analysis by Container/Category</h3>
            </div>
            <div class="research-data-grid cols-4">
            ${categoryStats.map(cat => {
                const catColors = {
                    'static-analyzer': { bg: 'purple', icon: 'code' },
                    'dynamic-analyzer': { bg: 'orange', icon: 'shield-halved' },
                    'performance-tester': { bg: 'cyan', icon: 'gauge-high' },
                    'ai-analyzer': { bg: 'pink', icon: 'brain' }
                };
                const c = catColors[cat.name] || { bg: 'secondary', icon: 'tools' };
                return `
                <div class="card border-${c.bg} h-100">
                    <div class="card-status-top bg-${c.bg}"></div>
                    <div class="card-body">
                    <div class="d-flex align-items-center mb-3">
                        <div class="avatar bg-${c.bg}-lt me-3">
                        <i class="fa-solid fa-${c.icon} text-${c.bg}"></i>
                        </div>
                        <h4 class="mb-0">${h(cat.name)}</h4>
                    </div>
                    <div class="row text-center">
                        <div class="col-4">
                        <div class="h4 mb-0">${formatNumber(cat.tools_count)}</div>
                        <div class="text-muted small">Tools</div>
                        </div>
                        <div class="col-4">
                        <div class="h4 mb-0">${formatNumber(cat.total_runs)}</div>
                        <div class="text-muted small">Runs</div>
                        </div>
                        <div class="col-4">
                        <div class="h4 mb-0">${formatNumber(cat.total_findings)}</div>
                        <div class="text-muted small">Findings</div>
                        </div>
                    </div>
                    <hr class="my-2">
                    <div class="text-muted small">
                        <strong>Avg per run:</strong> ${cat.avgFindings} findings
                    </div>
                    <div class="text-muted small mt-1">
                        <strong>Tools:</strong> ${(cat.tools || []).slice(0, 3).join(', ')}${(cat.tools || []).length > 3 ? '...' : ''}
                    </div>
                    </div>
                </div>
                `;
            }).join('')}
            </div>
        </div>
        ` : ''}
        
        <!-- Detailed Tool Performance Table -->
        <div class="research-section">
            <div class="research-section-header">
            <h3 class="research-section-title"><i class="fa-solid fa-table"></i> Detailed Tool Performance</h3>
            <div class="text-muted small">Sorted by execution count (most active first)</div>
            </div>
            <div class="card">
            <div class="table-responsive">
                <table class="table table-vcenter card-table table-hover">
                <thead>
                    <tr>
                    <th>Tool</th>
                    <th>Category</th>
                    <th class="text-center">Executions</th>
                    <th class="text-center">Success Rate</th>
                    <th class="text-center">Total Findings</th>
                    <th class="text-center">Avg/Run</th>
                    <th class="text-center">Avg Duration</th>
                    <th>Severity Breakdown</th>
                    </tr>
                </thead>
                <tbody>
                    ${tools.map((t, idx) => {
                const sevBreak = t.findings_by_severity || {};
                const isTop = idx < 3;
                return `
                        <tr>
                        <td>
                            <div class="d-flex align-items-center">
                            ${isTop ? '<i class="fa-solid fa-star text-warning me-2"></i>' : ''}
                            <div>
                                <strong>${h(t.display_name || t.name || t.tool_name)}</strong>
                                <div class="text-muted small">${h(t.tool_name || t.name)}</div>
                            </div>
                            </div>
                        </td>
                        <td><span class="badge bg-azure-lt">${h(t.container || t.service || 'unknown')}</span></td>
                        <td class="text-center"><strong>${formatNumber(t.total_runs || t.executions)}</strong></td>
                        <td class="text-center">
                            <div class="d-flex align-items-center justify-content-center gap-2">
                            <div class="progress flex-grow-1" style="height: 6px; max-width: 80px;">
                                <div class="progress-bar ${(t.success_rate || 0) >= 90 ? 'bg-success' : (t.success_rate || 0) >= 70 ? 'bg-warning' : 'bg-danger'}" style="width: ${t.success_rate || 0}%"></div>
                            </div>
                            <span class="small ${(t.success_rate || 0) >= 90 ? 'text-success' : (t.success_rate || 0) >= 70 ? 'text-warning' : 'text-danger'}">${t.success_rate ? t.success_rate.toFixed(0) + '%' : 'N/A'}</span>
                            </div>
                        </td>
                        <td class="text-center"><strong>${formatNumber(t.total_findings)}</strong></td>
                        <td class="text-center">${(t.avg_findings || t.findings_per_run || 0).toFixed(1)}</td>
                        <td class="text-center">${t.avg_duration ? t.avg_duration.toFixed(1) + 's' : 'N/A'}</td>
                        <td>
                            <div class="d-flex gap-1 flex-wrap">
                            ${(sevBreak.critical || 0) > 0 ? `<span class="badge bg-danger">${sevBreak.critical} crit</span>` : ''}
                            ${(sevBreak.high || 0) > 0 ? `<span class="badge bg-orange">${sevBreak.high} high</span>` : ''}
                            ${(sevBreak.medium || 0) > 0 ? `<span class="badge bg-yellow text-dark">${sevBreak.medium} med</span>` : ''}
                            ${(sevBreak.low || 0) > 0 ? `<span class="badge bg-success">${sevBreak.low} low</span>` : ''}
                            ${!sevBreak.critical && !sevBreak.high && !sevBreak.medium && !sevBreak.low ? '<span class="text-muted">—</span>' : ''}
                            </div>
                        </td>
                        </tr>
                    `;
            }).join('')}
                </tbody>
                </table>
            </div>
            </div>
        </div>
        
        <!-- Per-Model Tool Usage -->
        ${Object.keys(byModel).length > 0 ? `
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#by-model-section">
            <h3 class="research-section-title"><i class="fa-solid fa-robot"></i> Tool Usage by Model <span class="badge bg-secondary ms-2">${Object.keys(byModel).length} models</span></h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse" id="by-model-section">
            <div class="card">
                <div class="card-body">
                <div class="accordion" id="modelAccordion">
                    ${Object.entries(byModel).map(([model, modelTools], idx) => `
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                        <button class="accordion-button ${idx > 0 ? 'collapsed' : ''}" type="button" data-bs-toggle="collapse" data-bs-target="#model-${idx}">
                            <strong>${h(model.replace('_', ' / ').replace('-', ' ').substring(0, 50))}</strong>
                            <span class="badge bg-secondary ms-2">${Object.keys(modelTools).length} tools</span>
                        </button>
                        </h2>
                        <div id="model-${idx}" class="accordion-collapse collapse ${idx === 0 ? 'show' : ''}" data-bs-parent="#modelAccordion">
                        <div class="accordion-body">
                            <div class="table-responsive">
                            <table class="table table-sm table-borderless">
                                <thead>
                                <tr>
                                    <th>Tool</th>
                                    <th class="text-center">Executions</th>
                                    <th class="text-center">Successful</th>
                                    <th class="text-center">Findings</th>
                                </tr>
                                </thead>
                                <tbody>
                                ${Object.entries(modelTools).map(([toolName, toolData]) => `
                                    <tr>
                                    <td>${h(toolName)}</td>
                                    <td class="text-center">${formatNumber(toolData.executions)}</td>
                                    <td class="text-center">${formatNumber(toolData.successful)}</td>
                                    <td class="text-center">${formatNumber(toolData.findings)}</td>
                                    </tr>
                                `).join('')}
                                </tbody>
                            </table>
                            </div>
                        </div>
                        </div>
                    </div>
                    `).join('')}
                </div>
                </div>
            </div>
            </div>
        </div>
        ` : ''}
        
        <!-- Sample Findings -->
        ${findings.length > 0 ? `
        <div class="research-section">
            <div class="research-section-header section-collapse" data-bs-toggle="collapse" data-bs-target="#findings-section">
            <h3 class="research-section-title"><i class="fa-solid fa-list"></i> Sample Findings <span class="badge bg-secondary ms-2">${Math.min(findings.length, 25)} of ${findings.length}</span></h3>
            <div class="research-section-actions">
                <i class="fa-solid fa-chevron-down"></i>
            </div>
            </div>
            <div class="collapse" id="findings-section">
            <div class="card">
                <div class="card-body">
                <div class="list-group list-group-flush">
                    ${findings.slice(0, 25).map(f => `
                    <div class="list-group-item finding-item severity-${(f.severity || 'info').toLowerCase()}">
                        <div class="d-flex w-100 justify-content-between align-items-start">
                        <div>
                            ${severityBadge(f.severity)}
                            <span class="badge bg-azure-lt ms-2">${h(f.tool || 'unknown')}</span>
                            <strong class="ms-2">${h(f.rule_id || f.check_id || '')}</strong>
                        </div>
                        </div>
                        <p class="mb-1 mt-2">${h(f.message || f.description || 'No description')}</p>
                        ${f.file_path || f.file ? `<small class="text-muted"><i class="fa-solid fa-file-code me-1"></i>${h(f.file_path || f.file)}${f.line ? ':' + f.line : ''}</small>` : ''}
                    </div>
                    `).join('')}
                </div>
                </div>
            </div>
            </div>
        </div>
        ` : ''}
        
        <!-- Research Summary -->
        <div class="research-section">
            <div class="card border-success">
            <div class="card-header bg-success-lt">
                <h3 class="card-title"><i class="fa-solid fa-chart-line me-2"></i>Research Summary</h3>
            </div>
            <div class="card-body">
                <div class="row">
                <div class="col-md-6">
                    <h5>Tool Effectiveness Metrics</h5>
                    <ul class="mb-0">
                    <li><strong>Total Tools:</strong> ${formatNumber(summary.tools_analyzed || 0)} unique tools analyzed</li>
                    <li><strong>Total Executions:</strong> ${formatNumber(summary.total_runs || 0)} runs across all tools</li>
                    <li><strong>Average Success Rate:</strong> ${summary.avg_success_rate ? summary.avg_success_rate.toFixed(1) + '%' : 'N/A'}</li>
                    <li><strong>Findings per Run:</strong> ${avgFindingsPerRun} average</li>
                    ${mostEffective ? `<li><strong>Most Effective:</strong> ${h(mostEffective.display_name || mostEffective.name)} (${formatNumber(mostEffective.total_findings || 0)} findings)</li>` : ''}
                    </ul>
                </div>
                <div class="col-md-6">
                    <h5>Category Distribution</h5>
                    <ul class="mb-0">
                    ${categoryStats.map(cat => `
                        <li><strong>${h(cat.name)}:</strong> ${formatNumber(cat.tools_count)} tools, ${formatNumber(cat.total_findings)} findings</li>
                    `).join('')}
                    </ul>
                    ${filter.tool_name || filter.model ? `
                    <hr>
                    <h5>Active Filters</h5>
                    <ul class="mb-0">
                        ${filter.tool_name ? `<li>Tool: ${h(filter.tool_name)}</li>` : ''}
                        ${filter.model ? `<li>Model: ${h(filter.model)}</li>` : ''}
                    </ul>
                    ` : ''}
                </div>
                </div>
            </div>
            </div>
        </div>
        `;

            reportContent.innerHTML = html;

            // Initialize severity chart
            setTimeout(() => {
                const ctx = document.getElementById('toolSeverityChart');
                if (ctx && typeof Chart !== 'undefined') {
                    new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: ['Critical', 'High', 'Medium', 'Low', 'Info'],
                            datasets: [{
                                label: 'Findings',
                                data: [
                                    findingsBreakdown.critical || 0,
                                    findingsBreakdown.high || 0,
                                    findingsBreakdown.medium || 0,
                                    findingsBreakdown.low || 0,
                                    findingsBreakdown.info || 0
                                ],
                                backgroundColor: ['#d63939', '#f76707', '#f59f00', '#2fb344', '#0ea5e9']
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: { beginAtZero: true }
                            }
                        }
                    });
                }
            }, 100);
        }

        // === Generic Report ===
        function renderGenericReport() {
            reportContent.innerHTML = `
        <div class="card">
            <div class="card-header">
            <h3 class="card-title">Report Data</h3>
            </div>
            <div class="card-body">
            <pre class="mb-0"><code>${h(JSON.stringify(reportData, null, 2))}</code></pre>
            </div>
        </div>
        `;
        }

        // [RENDER_FUNCTIONS_HERE]

        // Fetch report data
        async function loadReport() {
            try {
                const response = await fetch(`/api/reports/${reportId}/data`);
                const result = await response.json();

                if (!result.success) {
                    throw new Error(result.error || 'Failed to load report');
                }

                reportData = result.data;

                // Display filter mode if present
                displayFilterMode(reportData.config?.filter_mode);

                if (loadingState) loadingState.classList.add('d-none');
                if (reportContent) reportContent.classList.remove('d-none');
                renderReport();

            } catch (e) {
                console.error('Failed to load report:', e);
                if (loadingState) loadingState.classList.add('d-none');
                if (errorMessage) errorMessage.textContent = e.message;
                if (errorState) errorState.classList.remove('d-none');
            }
        }

        // Start loading
        if (reportId) {
            loadReport();
        }
    }
})();
