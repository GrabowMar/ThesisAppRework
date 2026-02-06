/**
 * Unified Container Manager
 * =========================
 * 
 * A unified container management system that works across all pages:
 * - Individual container operations (start, stop, restart, build)
 * - Bulk/batch operations with progress tracking
 * - Real-time progress display via modal
 * - Support for both single-app (detail page) and multi-app (table) contexts
 * 
 * This module consolidates container_manager.js, container_logs.js, and 
 * the inline scripts from _overview_content.html into a single, cohesive system.
 */

(function () {
    'use strict';

    // ============================================================================
    // UnifiedContainerManager - Main orchestrator
    // ============================================================================

    class UnifiedContainerManager {
        constructor() {
            this.modal = null;
            this.progressModal = null;
            this.currentOperation = null;
            this.batchQueue = [];
            this.batchInProgress = false;
            this.pollingIntervals = new Map();
            this.socket = null;

            // Configuration
            this.config = {
                pollInterval: 1000,           // Status poll interval (ms)
                outputPollInterval: 500,      // Output stream poll interval (ms)
                toastDuration: 4000,          // Toast notification duration (ms)
                progressModalDelay: 200,      // Delay before showing progress modal (ms)
            };

            this.init();
        }

        // ------------------------------------------------------------------------
        // Initialization
        // ------------------------------------------------------------------------

        init() {
            this.initProgressModal();
            this.initBatchModal();
            this.initWebSocket();
            this.bindGlobalEvents();
        }

        initProgressModal() {
            // Look for the standard container logs modal
            this.modal = document.getElementById('container-logs-modal');
            if (!this.modal) {
                console.warn('UnifiedContainerManager: container-logs-modal not found');
            }
        }

        initBatchModal() {
            this.batchModal = document.getElementById('batchProgressModal');
            // Will be created dynamically if not found when needed
        }

        initWebSocket() {
            if (typeof io !== 'undefined') {
                try {
                    this.socket = io();
                    this.socket.on('container.progress', (data) => this.handleWSProgress(data));
                    this.socket.on('container.action_completed', (data) => this.handleWSComplete(data));
                    this.socket.on('container.action_failed', (data) => this.handleWSFailed(data));
                    console.log('UnifiedContainerManager: WebSocket connected');
                } catch (e) {
                    console.warn('UnifiedContainerManager: WebSocket init failed, using polling', e);
                }
            }
        }

        bindGlobalEvents() {
            // Handle modal close events
            document.addEventListener('hidden.bs.modal', (e) => {
                if (e.target.id === 'container-logs-modal') {
                    this.onProgressModalClosed();
                }
                if (e.target.id === 'batchProgressModal') {
                    this.onBatchModalClosed();
                }
            });
        }

        // ------------------------------------------------------------------------
        // Single Container Operations
        // ------------------------------------------------------------------------

        /**
         * Perform a container action on a single app
         * @param {string} modelSlug - Model slug
         * @param {number} appNumber - App number
         * @param {string} action - Action type (start, stop, restart, build)
         * @param {object} options - Additional options (no_cache, start_after, showModal)
         * @returns {Promise<object>} - Result of the operation
         */
        async performAction(modelSlug, appNumber, action, options = {}) {
            const appLabel = this.formatAppLabel(modelSlug, appNumber);
            const showModal = options.showModal !== false; // Default to true

            // Update table row status immediately
            this.updateTableRowStatus(modelSlug, appNumber, 'pending', `${action}ing...`);

            // Use containerLogsModal if available (provides better output streaming)
            if (showModal && window.containerLogsModal) {
                try {
                    const baseUrl = `/api/app/${modelSlug}/${appNumber}`;
                    const payload = {
                        no_cache: options.no_cache || false,
                        start_after: options.start_after || false
                    };

                    // Start operation with the logs modal (handles async polling internally)
                    await window.containerLogsModal.startOperation(
                        `${action.charAt(0).toUpperCase() + action.slice(1)} - ${appLabel}`,
                        `${baseUrl}/${action}`,
                        payload
                    );

                    // Trigger table refresh after operation
                    setTimeout(() => this.triggerTableRefresh(), 1000);
                    return { success: true };

                } catch (error) {
                    this.showToast(`${appLabel}: ${error.message}`, 'danger');
                    this.updateTableRowStatus(modelSlug, appNumber, 'error', 'Error');
                    return { success: false, error: error.message };
                }
            }

            // Fallback: Direct API call without modal (for batch operations or when modal unavailable)
            try {
                const response = await fetch(`/api/app/${modelSlug}/${appNumber}/action/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        no_cache: options.no_cache || false,
                        start_after: options.start_after || false
                    })
                });

                const data = await response.json();

                if (response.status === 409) {
                    this.showToast(`${appLabel}: Another operation is in progress`, 'info');
                    return { success: false, error: 'Operation in progress' };
                }

                if (!response.ok || !data.success) {
                    throw new Error(data.error || `HTTP ${response.status}`);
                }

                // Track the action
                const actionId = data.action_id;
                this.currentOperation = {
                    actionId,
                    modelSlug,
                    appNumber,
                    action,
                    startTime: Date.now()
                };

                // Start polling for status (background tracking)
                this.startActionPolling(actionId, modelSlug, appNumber, action);

                return { success: true, actionId };

            } catch (error) {
                this.showToast(`${appLabel}: ${error.message}`, 'danger');
                this.updateTableRowStatus(modelSlug, appNumber, 'error', 'Error');
                return { success: false, error: error.message };
            }
        }

        /**
         * Start polling for action status and output
         */
        startActionPolling(actionId, modelSlug, appNumber, action) {
            // Clear any existing polling for this action
            this.stopActionPolling(actionId);

            let outputOffset = 0;

            // Status polling
            const statusInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/container-actions/${actionId}`);
                    if (!response.ok) return;

                    const data = await response.json();
                    if (!data.success || !data.action) return;

                    const actionData = data.action;

                    // Update progress modal if visible
                    this.updateProgressModal(actionData);

                    // Update table row
                    this.updateTableRowStatus(
                        modelSlug,
                        appNumber,
                        actionData.status,
                        actionData.current_step || `${action}ing...`
                    );

                    // Check for completion
                    if (['completed', 'failed', 'cancelled'].includes(actionData.status)) {
                        this.stopActionPolling(actionId);
                        this.handleActionComplete(actionData, modelSlug, appNumber);
                    }

                } catch (error) {
                    console.debug('Status poll failed:', error);
                }
            }, this.config.pollInterval);

            // Output polling (for modal)
            const outputInterval = setInterval(async () => {
                if (!this.isProgressModalVisible()) return;

                try {
                    const response = await fetch(`/api/container-actions/${actionId}/output?offset=${outputOffset}`);
                    if (!response.ok) return;

                    const data = await response.json();
                    if (!data.success) return;

                    if (data.output && data.output.length > 0) {
                        this.appendModalOutput(data.output);
                        outputOffset = data.total_length || (outputOffset + data.output.length);
                    }
                } catch (error) {
                    console.debug('Output poll failed:', error);
                }
            }, this.config.outputPollInterval);

            this.pollingIntervals.set(actionId, { statusInterval, outputInterval });
        }

        stopActionPolling(actionId) {
            const intervals = this.pollingIntervals.get(actionId);
            if (intervals) {
                clearInterval(intervals.statusInterval);
                clearInterval(intervals.outputInterval);
                this.pollingIntervals.delete(actionId);
            }
        }

        handleActionComplete(actionData, modelSlug, appNumber) {
            const appLabel = this.formatAppLabel(modelSlug, appNumber);
            const action = actionData.action_type;

            if (actionData.status === 'completed') {
                this.showToast(`${appLabel}: ${action} completed`, 'success');
                // Determine final status based on action
                const finalStatus = (action === 'stop') ? 'stopped' : 'running';
                this.updateTableRowStatus(modelSlug, appNumber, finalStatus);
            } else if (actionData.status === 'failed') {
                const errorMsg = actionData.error_message || `${action} failed`;
                this.showToast(`${appLabel}: ${errorMsg}`, 'danger', 6000);
                this.updateTableRowStatus(modelSlug, appNumber, 'error', 'Failed');
            } else if (actionData.status === 'cancelled') {
                this.showToast(`${appLabel}: ${action} cancelled`, 'warning');
            }

            // Trigger table refresh after a short delay
            setTimeout(() => this.triggerTableRefresh(), 1000);

            // Update modal final state
            this.finalizeProgressModal(actionData);
        }

        // ------------------------------------------------------------------------
        // Batch Operations
        // ------------------------------------------------------------------------

        /**
         * Perform a batch operation on multiple apps
         * @param {Array<{modelSlug: string, appNumber: number}>} apps - List of apps
         * @param {string} action - Action type
         * @param {object} options - Additional options
         * @returns {Promise<object>} - Batch results
         */
        async performBatchAction(apps, action, options = {}) {
            if (this.batchInProgress) {
                this.showToast('A batch operation is already in progress', 'warning');
                return { success: false, error: 'Batch in progress' };
            }

            if (!apps.length) {
                this.showToast('No applications selected', 'warning');
                return { success: false, error: 'No apps selected' };
            }

            this.batchInProgress = true;
            this.batchQueue = [...apps];

            const results = {
                total: apps.length,
                completed: 0,
                failed: 0,
                cancelled: false,
                details: []
            };

            // Show batch progress modal
            this.showBatchProgressModal(action, apps.length);

            // Process sequentially
            for (let i = 0; i < apps.length; i++) {
                if (results.cancelled) break;

                const app = apps[i];
                const appLabel = this.formatAppLabel(app.modelSlug, app.appNumber);

                // Update progress
                this.updateBatchProgress(i, apps.length, `${action}: ${appLabel}`);
                this.addBatchLogEntry(`<i class="fa-solid fa-spinner fa-spin me-1"></i>${appLabel}...`, 'text-muted', i);

                try {
                    const result = await this.performSingleBatchAction(app.modelSlug, app.appNumber, action, options);

                    if (result.success) {
                        results.completed++;
                        this.updateBatchLogEntry(i, `<i class="fa-solid fa-check text-success me-1"></i>${appLabel}`, 'text-success');
                    } else {
                        results.failed++;
                        const errMsg = result.error ? `: ${result.error.substring(0, 30)}` : '';
                        this.updateBatchLogEntry(i, `<i class="fa-solid fa-times text-danger me-1"></i>${appLabel}${errMsg}`, 'text-danger');
                    }

                    results.details.push({ app, success: result.success, error: result.error });

                } catch (error) {
                    results.failed++;
                    this.updateBatchLogEntry(i, `<i class="fa-solid fa-times text-danger me-1"></i>${appLabel}: ${error.message}`, 'text-danger');
                    results.details.push({ app, success: false, error: error.message });
                }

                // Small delay between operations
                await this.sleep(100);
            }

            this.batchInProgress = false;
            this.finalizeBatchProgress(results, action);

            // Trigger table refresh
            setTimeout(() => this.triggerTableRefresh(), 500);

            return results;
        }

        async performSingleBatchAction(modelSlug, appNumber, action, options) {
            // For batch operations, use sync endpoint to keep it simple
            const apiAction = action === 'rebuild' ? 'build' : action;
            const body = action === 'build' || action === 'rebuild'
                ? { no_cache: action === 'rebuild', start_after: true }
                : {};

            const response = await fetch(`/api/app/${modelSlug}/${appNumber}/${apiAction}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const data = await response.json().catch(() => ({}));
            return {
                success: response.ok && data.success !== false,
                error: data.error
            };
        }

        cancelBatch() {
            if (this.batchInProgress) {
                // Find the current batch results and mark as cancelled
                // This will be checked in the batch loop
                this.batchQueue = [];
                this.showToast('Cancelling batch operation...', 'info');
            }
        }

        // ------------------------------------------------------------------------
        // Progress Modal Management
        // ------------------------------------------------------------------------

        showProgressModal(action, modelSlug, appNumber, actionId) {
            if (!this.modal) return;

            // Reset modal state
            const outputEl = document.getElementById('log-output');
            if (outputEl) outputEl.innerHTML = '';

            const operationName = document.getElementById('log-operation-name');
            if (operationName) {
                operationName.textContent = `${action.charAt(0).toUpperCase() + action.slice(1)} - ${modelSlug} App ${appNumber}`;
            }

            // Update status
            this.updateModalStatus('Starting...', `Initiating ${action}`, 'info');
            this.updateModalProgress(0);

            // Show modal elements
            const progressContainer = document.getElementById('log-progress-bar-container');
            if (progressContainer) progressContainer.style.display = 'block';

            const cancelBtn = document.getElementById('log-cancel-btn');
            if (cancelBtn) {
                cancelBtn.style.display = 'inline-block';
                cancelBtn.onclick = () => this.cancelCurrentAction(actionId);
            }

            const closeBtn = document.getElementById('log-close-btn');
            if (closeBtn) closeBtn.disabled = true;

            // Start timer
            this.startModalTimer();

            // Show modal
            const bsModal = new bootstrap.Modal(this.modal);
            bsModal.show();
        }

        updateProgressModal(actionData) {
            if (!this.isProgressModalVisible()) return;

            // Update progress bar
            this.updateModalProgress(actionData.progress_percentage || 0);

            // Update status
            if (actionData.status === 'running') {
                this.updateModalStatus(
                    actionData.current_step || 'Running...',
                    `${Math.round(actionData.progress_percentage || 0)}% complete`,
                    'info'
                );
            }
        }

        finalizeProgressModal(actionData) {
            if (!this.isProgressModalVisible()) return;

            this.stopModalTimer();

            const cancelBtn = document.getElementById('log-cancel-btn');
            if (cancelBtn) cancelBtn.style.display = 'none';

            const closeBtn = document.getElementById('log-close-btn');
            if (closeBtn) closeBtn.disabled = false;

            if (actionData.status === 'completed') {
                this.updateModalProgress(100);
                this.updateModalStatus('Completed Successfully', `Duration: ${actionData.duration_seconds?.toFixed(1)}s`, 'success');
                this.appendModalOutput('\n═══════════════════════════════════════════════\n✅ Operation completed successfully!', 'success');
            } else if (actionData.status === 'failed') {
                this.updateModalStatus('Failed', actionData.error_message || 'Operation failed', 'danger');
                this.appendModalOutput(`\n═══════════════════════════════════════════════\n❌ Operation failed: ${actionData.error_message || 'Unknown error'}`, 'error');
            } else if (actionData.status === 'cancelled') {
                this.updateModalStatus('Cancelled', 'Operation was cancelled', 'warning');
                this.appendModalOutput('\n═══════════════════════════════════════════════\n⚠️ Operation cancelled', 'warning');
            }
        }

        updateModalStatus(status, detail, severity) {
            const statusText = document.getElementById('log-status-text');
            const statusDetail = document.getElementById('log-status-detail');
            const statusBanner = document.getElementById('log-status-banner');
            const spinner = document.getElementById('log-spinner');

            // Dark-themed status colors
            const statusStyles = {
                info: { bg: 'rgba(32, 107, 196, 0.2)', border: 'rgba(32, 107, 196, 0.4)', text: 'text-info' },
                success: { bg: 'rgba(47, 179, 68, 0.2)', border: 'rgba(47, 179, 68, 0.4)', text: 'text-success' },
                danger: { bg: 'rgba(214, 57, 57, 0.2)', border: 'rgba(214, 57, 57, 0.4)', text: 'text-danger' },
                warning: { bg: 'rgba(247, 103, 7, 0.2)', border: 'rgba(247, 103, 7, 0.4)', text: 'text-warning' }
            };
            const style = statusStyles[severity] || statusStyles.info;

            if (statusText) statusText.textContent = status;
            if (statusDetail) statusDetail.textContent = detail || '';
            if (statusBanner) {
                statusBanner.className = 'rounded m-3 mb-0 p-3 d-flex align-items-center';
                statusBanner.style.background = style.bg;
                statusBanner.style.border = `1px solid ${style.border}`;
            }
            if (spinner) {
                spinner.style.display = severity === 'info' ? 'inline-block' : 'none';
                spinner.className = `spinner-border spinner-border-sm me-3 ${style.text}`;
            }
        }

        updateModalProgress(percentage) {
            const progressBar = document.getElementById('log-progress-bar');
            if (progressBar) {
                progressBar.style.width = `${percentage}%`;
            }
        }

        appendModalOutput(text, type = 'output') {
            const outputEl = document.getElementById('log-output');
            if (!outputEl) return;

            const colorClass = {
                error: 'text-danger',
                success: 'text-success',
                warning: 'text-warning',
                info: 'text-info',
                output: 'text-white'
            }[type] || 'text-white';

            const lines = text.split('\n');
            for (const line of lines) {
                if (line) {
                    const div = document.createElement('div');
                    div.className = colorClass;
                    div.textContent = line;
                    outputEl.appendChild(div);
                }
            }

            // Auto-scroll
            outputEl.parentElement.scrollTop = outputEl.parentElement.scrollHeight;

            // Update line count
            const lineCount = document.getElementById('log-line-count');
            if (lineCount) {
                lineCount.textContent = `${outputEl.children.length} lines`;
            }
        }

        isProgressModalVisible() {
            return this.modal && this.modal.classList.contains('show');
        }

        onProgressModalClosed() {
            this.stopModalTimer();
            // Don't stop polling - let it continue in background
        }

        startModalTimer() {
            this.modalStartTime = Date.now();
            this.modalTimerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - this.modalStartTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                const elapsedEl = document.getElementById('log-elapsed-time');
                if (elapsedEl) {
                    elapsedEl.textContent = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
                }
            }, 1000);
        }

        stopModalTimer() {
            if (this.modalTimerInterval) {
                clearInterval(this.modalTimerInterval);
                this.modalTimerInterval = null;
            }
        }

        async cancelCurrentAction(actionId) {
            try {
                await fetch(`/api/container-actions/${actionId}/cancel`, { method: 'POST' });
                this.showToast('Cancellation requested...', 'info');
            } catch (error) {
                console.error('Failed to cancel action:', error);
            }
        }

        // ------------------------------------------------------------------------
        // Batch Progress Modal Management
        // ------------------------------------------------------------------------

        showBatchProgressModal(action, totalApps) {
            // Use the existing batch modal or create one
            const modal = document.getElementById('batchApplicationsModal');
            if (!modal) return;

            // Switch to progress view
            const buttonsEl = document.getElementById('batchOperationsButtons');
            const progressEl = document.getElementById('batchOperationsProgress');
            const resultEl = document.getElementById('batchOperationResult');
            const cancelBtn = document.getElementById('batchCancelBtn');
            const closeBtn = document.getElementById('batchCloseBtn');

            if (buttonsEl) buttonsEl.style.display = 'none';
            if (progressEl) progressEl.style.display = 'block';
            if (resultEl) resultEl.innerHTML = '';
            if (cancelBtn) {
                cancelBtn.style.display = 'inline-block';
                cancelBtn.onclick = () => this.cancelBatch();
            }
            if (closeBtn) closeBtn.disabled = true;

            // Reset progress
            this.updateBatchProgress(0, totalApps, `Starting ${action}...`);

            const logEl = document.getElementById('batchProgressLog');
            if (logEl) logEl.innerHTML = '';
        }

        updateBatchProgress(current, total, label) {
            const percent = total > 0 ? Math.round(((current + 1) / total) * 100) : 0;

            const labelEl = document.getElementById('batchProgressLabel');
            const countEl = document.getElementById('batchProgressCount');
            const barEl = document.getElementById('batchProgressBar');

            if (labelEl) labelEl.textContent = label;
            if (countEl) countEl.textContent = `${current + 1}/${total}`;
            if (barEl) barEl.style.width = `${percent}%`;
        }

        addBatchLogEntry(html, className, index) {
            const log = document.getElementById('batchProgressLog');
            if (!log) return;

            const entry = document.createElement('div');
            entry.className = className || '';
            entry.innerHTML = html;
            entry.dataset.index = index;
            log.appendChild(entry);
            log.scrollTop = log.scrollHeight;
        }

        updateBatchLogEntry(index, html, className) {
            const log = document.getElementById('batchProgressLog');
            if (!log) return;

            const entry = log.querySelector(`[data-index="${index}"]`);
            if (entry) {
                entry.className = className || '';
                entry.innerHTML = html;
            }
        }

        finalizeBatchProgress(results, action) {
            const cancelBtn = document.getElementById('batchCancelBtn');
            const closeBtn = document.getElementById('batchCloseBtn');
            const resultEl = document.getElementById('batchOperationResult');

            if (cancelBtn) cancelBtn.style.display = 'none';
            if (closeBtn) closeBtn.disabled = false;

            let alertClass = 'success';
            let icon = 'check-circle';
            let message = `${action} completed: ${results.completed} successful`;

            if (results.failed > 0) {
                alertClass = 'warning';
                icon = 'exclamation-triangle';
                message += `, ${results.failed} failed`;
            }
            if (results.cancelled) {
                alertClass = 'secondary';
                icon = 'ban';
                message = `${action} cancelled: ${results.completed} completed, ${results.total - results.completed} remaining`;
            }

            if (resultEl) {
                resultEl.innerHTML = `
                <div class="alert alert-${alertClass} py-2 mb-0 mt-2 d-flex align-items-center gap-2">
                    <i class="fa-solid fa-${icon}"></i>
                    <span>${message}</span>
                    <button class="btn btn-sm btn-link ms-auto p-0" onclick="window.unifiedContainerManager.resetBatchUI()">
                        <i class="fa-solid fa-redo"></i> New
                    </button>
                </div>
            `;
            }
        }

        resetBatchUI() {
            const buttonsEl = document.getElementById('batchOperationsButtons');
            const progressEl = document.getElementById('batchOperationsProgress');
            const resultEl = document.getElementById('batchOperationResult');
            const cancelBtn = document.getElementById('batchCancelBtn');
            const closeBtn = document.getElementById('batchCloseBtn');

            if (buttonsEl) buttonsEl.style.display = 'block';
            if (progressEl) progressEl.style.display = 'none';
            if (resultEl) resultEl.innerHTML = '';
            if (cancelBtn) cancelBtn.style.display = 'none';
            if (closeBtn) closeBtn.disabled = false;
        }

        onBatchModalClosed() {
            this.resetBatchUI();
        }

        // ------------------------------------------------------------------------
        // Table Row Status Updates
        // ------------------------------------------------------------------------

        updateTableRowStatus(modelSlug, appNumber, status, step = null) {
            const row = document.querySelector(`tr[data-model="${modelSlug}"][data-app="${appNumber}"]`);
            if (!row) return;

            const statusBadge = row.querySelector('[data-role="status-badge"]');
            if (!statusBadge) return;

            const statusConfig = {
                running: { class: 'badge bg-success-lt text-success', icon: 'fa-play', text: 'Running' },
                stopped: { class: 'badge bg-secondary-lt text-secondary', icon: 'fa-stop', text: 'Stopped' },
                pending: { class: 'badge bg-info-lt text-info', icon: 'fa-spinner fa-spin', text: step || 'Processing...' },
                error: { class: 'badge bg-danger-lt text-danger', icon: 'fa-exclamation-circle', text: 'Error' },
                failed: { class: 'badge bg-orange text-white', icon: 'fa-exclamation-triangle', text: 'Build Failed' },
                completed: { class: 'badge bg-success-lt text-success', icon: 'fa-check', text: 'Completed' }
            };

            const config = statusConfig[status] || statusConfig.pending;
            statusBadge.className = config.class;
            statusBadge.innerHTML = `<i class="fa-solid ${config.icon} fa-xs me-1"></i>${step || config.text}`;

            // Update actions visibility
            const runningGroup = row.querySelector('.actions-group-running');
            const stoppedGroup = row.querySelector('.actions-group-stopped');

            if (runningGroup && stoppedGroup) {
                const isRunning = status === 'running';
                runningGroup.style.display = isRunning ? 'contents' : 'none';
                stoppedGroup.style.display = isRunning ? 'none' : 'contents';
            }
        }

        // ------------------------------------------------------------------------
        // WebSocket Handlers
        // ------------------------------------------------------------------------

        handleWSProgress(data) {
            if (!this.currentOperation || data.action_id !== this.currentOperation.actionId) return;

            this.updateModalProgress(data.progress);
            if (data.step) {
                this.updateModalStatus(data.step, `${Math.round(data.progress)}% complete`, 'info');
            }
        }

        handleWSComplete(data) {
            if (!this.currentOperation || data.action_id !== this.currentOperation.actionId) return;

            this.stopActionPolling(data.action_id);
            this.handleActionComplete({
                ...data,
                status: 'completed',
                action_type: this.currentOperation.action
            }, this.currentOperation.modelSlug, this.currentOperation.appNumber);
        }

        handleWSFailed(data) {
            if (!this.currentOperation || data.action_id !== this.currentOperation.actionId) return;

            this.stopActionPolling(data.action_id);
            this.handleActionComplete({
                ...data,
                status: 'failed',
                action_type: this.currentOperation.action,
                error_message: data.error
            }, this.currentOperation.modelSlug, this.currentOperation.appNumber);
        }

        // ------------------------------------------------------------------------
        // Utility Functions
        // ------------------------------------------------------------------------

        formatAppLabel(modelSlug, appNumber) {
            const modelName = modelSlug.split('_').pop();
            return `${modelName} #${appNumber}`;
        }

        showToast(message, type = 'info', duration = null) {
            const container = this.getToastContainer();

            const iconMap = {
                success: '<i class="fa-solid fa-check-circle text-success me-2"></i>',
                danger: '<i class="fa-solid fa-exclamation-circle text-danger me-2"></i>',
                warning: '<i class="fa-solid fa-exclamation-triangle text-warning me-2"></i>',
                info: '<i class="fa-solid fa-info-circle text-info me-2"></i>'
            };

            const bgMap = {
                success: 'bg-success-lt',
                danger: 'bg-danger-lt',
                warning: 'bg-warning-lt',
                info: 'bg-info-lt'
            };

            const toast = document.createElement('div');
            toast.className = `card shadow-sm mb-2 ${bgMap[type] || 'bg-white'}`;
            toast.style.cssText = 'font-size: 0.85rem; animation: slideInRight 0.2s ease-out;';
            toast.innerHTML = `
            <div class="card-body p-2 d-flex align-items-center">
                ${iconMap[type] || iconMap.info}
                <span class="flex-grow-1">${this.escapeHtml(message)}</span>
                <button class="btn btn-sm p-0 border-0 ms-2" onclick="this.closest('.card').remove()" title="Dismiss">
                    <i class="fa-solid fa-times text-muted"></i>
                </button>
            </div>
        `;

            container.appendChild(toast);

            setTimeout(() => {
                toast.style.animation = 'slideOutRight 0.2s ease-in';
                setTimeout(() => toast.remove(), 200);
            }, duration || this.config.toastDuration);
        }

        getToastContainer() {
            let container = document.getElementById('unified-toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'unified-toast-container';
                container.className = 'position-fixed bottom-0 end-0 p-3';
                container.style.cssText = 'z-index: 1100; max-width: 320px;';
                document.body.appendChild(container);

                // Add animations
                const style = document.createElement('style');
                style.textContent = `
                @keyframes slideInRight {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOutRight {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
                document.head.appendChild(style);
            }
            return container;
        }

        triggerTableRefresh() {
            if (typeof htmx !== 'undefined') {
                htmx.trigger('body', 'refresh-applications-table');
            }
            if (typeof window.refreshApplications === 'function') {
                window.refreshApplications();
            }
        }

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        sleep(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
    }

    // ============================================================================
    // Global Instance and Helper Functions
    // ============================================================================

    // Create global instance
    window.unifiedContainerManager = null;

    function initUnifiedContainerManager() {
        if (!window.unifiedContainerManager) {
            window.unifiedContainerManager = new UnifiedContainerManager();
        }
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initUnifiedContainerManager);
    } else {
        initUnifiedContainerManager();
    }

    // Re-initialize on HTMX page navigation
    document.addEventListener('htmx:historyRestore', initUnifiedContainerManager);

    // ============================================================================
    // Global API Functions (for onclick handlers)
    // ============================================================================

    /**
     * Start a container action from anywhere (table, buttons, etc.)
     * This is the main entry point for all container operations
     */
    window.startContainerAction = function (modelSlug, appNumber, action, options = {}) {
        if (!window.unifiedContainerManager) {
            initUnifiedContainerManager();
        }
        return window.unifiedContainerManager.performAction(modelSlug, appNumber, action, options);
    };

    /**
     * Perform a batch operation on selected apps
     * @param {string} action - Action to perform
     */
    window.batchOperation = function (action) {
        const selected = window.getSelectedApplications ? window.getSelectedApplications() : [];
        if (!selected.length) {
            window.unifiedContainerManager?.showToast('Please select at least one application', 'warning');
            return;
        }

        // Parse selected values (format: "modelSlug-appNumber")
        const apps = selected.map(val => {
            const lastDash = val.lastIndexOf('-');
            return {
                modelSlug: val.substring(0, lastDash),
                appNumber: parseInt(val.substring(lastDash + 1), 10)
            };
        });

        if (!window.unifiedContainerManager) {
            initUnifiedContainerManager();
        }

        return window.unifiedContainerManager.performBatchAction(apps, action);
    };

    /**
     * Get list of selected application checkboxes
     */
    window.getSelectedApplications = function () {
        return Array.from(document.querySelectorAll('.app-checkbox:checked')).map(cb => cb.value);
    };

    /**
     * Update batch selection count display
     */
    window.updateBatchSelectionCount = function () {
        const count = window.getSelectedApplications().length;
        const element = document.getElementById('selected-applications-count');
        if (element) element.textContent = count;
    };

    /**
     * Confirm and perform batch delete
     */
    window.confirmBatchDelete = function () {
        const count = window.getSelectedApplications().length;
        if (confirm(`Are you sure you want to delete ${count} application(s)? This cannot be undone.`)) {
            window.batchOperation('delete');
        }
    };

    /**
     * Cancel ongoing batch operation
     */
    window.cancelBatchOperation = function () {
        if (window.unifiedContainerManager) {
            window.unifiedContainerManager.cancelBatch();
        }
    };

    /**
     * Reset batch modal UI
     */
    window.resetBatchUI = function () {
        if (window.unifiedContainerManager) {
            window.unifiedContainerManager.resetBatchUI();
        }
    };

})();
