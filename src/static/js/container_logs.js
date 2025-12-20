/**
 * Container Logs Module
 * ======================
 * 
 * Handles real-time display of Docker operation logs in a modal window.
 * Provides visual feedback for build, start, stop, and other container operations.
 * 
 * Supports two modes:
 * 1. Legacy sync mode: Single POST request, waits for completion
 * 2. Async mode: Returns action_id immediately, polls/streams progress via WebSocket
 */

(function() {

class ContainerLogsModal {
    constructor() {
        this.modal = null;
        this.bootstrapModal = null;
        this.outputElement = null;
        this.statusElement = null;
        this.spinnerElement = null;
        this.progressBar = null;
        this.startTime = null;
        this.timerInterval = null;
        this.autoScroll = true;
        this.logs = [];
        this.operationInProgress = false;
        this.abortController = null;
        
        // Async action tracking
        this.currentActionId = null;
        this.actionPollingInterval = null;
        this.outputPollingInterval = null;
        this.lastOutputOffset = 0;
        this.useAsyncMode = true;  // Enable by default, fall back if needed
        
        // WebSocket for real-time updates (if SocketIO available)
        this.socket = null;
        
        this.init();
    }

    /**
     * Initialize the modal and bind events
     */
    init() {
        this.modal = document.getElementById('container-logs-modal');
        if (!this.modal) {
            console.error('Container logs modal not found in DOM');
            return;
        }

        this.bootstrapModal = new bootstrap.Modal(this.modal, {
            backdrop: 'static',
            keyboard: false
        });

        this.outputElement = document.getElementById('log-output');
        this.statusElement = document.getElementById('log-status-text');
        this.statusDetailElement = document.getElementById('log-status-detail');
        this.spinnerElement = document.getElementById('log-spinner');
        this.statusBanner = document.getElementById('log-status-banner');
        this.progressBar = document.getElementById('log-progress-bar');
        this.progressBarContainer = document.getElementById('log-progress-bar-container');
        this.elapsedTimeElement = document.getElementById('log-elapsed-time');
        this.lineCountElement = document.getElementById('log-line-count');
        this.closeButton = document.getElementById('log-close-btn');
        this.cancelButton = document.getElementById('log-cancel-btn');
        this.modalCloseButton = document.getElementById('log-modal-close');
        
        this.bindEvents();
        this.initWebSocket();
    }
    
    /**
     * Initialize WebSocket connection for real-time updates
     */
    initWebSocket() {
        // Check if SocketIO is available
        if (typeof io !== 'undefined') {
            try {
                this.socket = io();
                
                // Listen for container action events
                this.socket.on('container.progress', (data) => this.handleProgressEvent(data));
                this.socket.on('container.action_completed', (data) => this.handleCompletedEvent(data));
                this.socket.on('container.action_failed', (data) => this.handleFailedEvent(data));
                this.socket.on('container.action_cancelled', (data) => this.handleCancelledEvent(data));
                
                console.log('Container logs: WebSocket connected');
            } catch (e) {
                console.warn('Container logs: WebSocket initialization failed, using polling', e);
                this.socket = null;
            }
        }
    }
    
    /**
     * Handle real-time progress event from WebSocket
     */
    handleProgressEvent(data) {
        if (data.action_id !== this.currentActionId) return;
        
        // Update progress bar
        this.updateProgressBar(data.progress);
        
        // Update status
        if (data.step) {
            this.updateStatus(data.step, `${Math.round(data.progress)}% complete`, 'info');
        }
    }
    
    /**
     * Handle action completed event from WebSocket
     */
    handleCompletedEvent(data) {
        if (data.action_id !== this.currentActionId) return;
        
        this.stopPolling();
        this.updateProgressBar(100);
        this.updateStatus('Completed Successfully', `Duration: ${data.duration_seconds?.toFixed(1)}s`, 'success');
        this.appendLog('═══════════════════════════════════════════════', 'separator');
        this.appendLog('✅ Operation completed successfully!', 'success');
        this.finishOperation();
    }
    
    /**
     * Handle action failed event from WebSocket
     */
    handleFailedEvent(data) {
        if (data.action_id !== this.currentActionId) return;
        
        this.stopPolling();
        this.updateStatus('Failed', data.error || 'Operation failed', 'danger');
        this.appendLog('═══════════════════════════════════════════════', 'separator');
        this.appendLog(`❌ Operation failed: ${data.error || 'Unknown error'}`, 'error');
        this.finishOperation();
    }
    
    /**
     * Handle action cancelled event from WebSocket
     */
    handleCancelledEvent(data) {
        if (data.action_id !== this.currentActionId) return;
        
        this.stopPolling();
        this.updateStatus('Cancelled', data.reason || 'Operation was cancelled', 'warning');
        this.appendLog('═══════════════════════════════════════════════', 'separator');
        this.appendLog('⚠️ Operation cancelled', 'warning');
        this.finishOperation();
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Scroll toggle
        document.getElementById('log-scroll-toggle')?.addEventListener('click', () => {
            this.autoScroll = !this.autoScroll;
            const icon = document.querySelector('#log-scroll-toggle i');
            if (icon) {
                icon.className = this.autoScroll ? 'fas fa-arrow-down' : 'fas fa-pause';
            }
            if (this.autoScroll) {
                this.scrollToBottom();
            }
        });

        // Copy logs
        document.getElementById('log-copy')?.addEventListener('click', () => this.copyLogs());

        // Clear logs
        document.getElementById('log-clear')?.addEventListener('click', () => this.clearLogs());

        // Download logs
        document.getElementById('log-download')?.addEventListener('click', () => this.downloadLogs());

        // Cancel operation
        this.cancelButton?.addEventListener('click', () => this.cancelOperation());

        // Close modal
        this.closeButton?.addEventListener('click', () => this.close());
        
        // Prevent closing while operation is in progress
        this.modalCloseButton?.addEventListener('click', (e) => {
            if (this.operationInProgress) {
                e.preventDefault();
                e.stopPropagation();
                if (confirm('Operation is still in progress. Do you want to cancel it?')) {
                    this.cancelOperation();
                }
            }
        });
    }

    /**
     * Show the modal and start an operation
     * @param {string} operationName - Display name for the operation
     * @param {string} apiUrl - API endpoint URL
     * @param {object} payload - Request payload
     * @param {object} options - Additional options (useAsync: bool)
     */
    async startOperation(operationName, apiUrl, payload = {}, options = {}) {
        this.reset();
        this.operationInProgress = true;
        this.startTime = Date.now();
        
        // Determine if we should use async mode
        const useAsync = options.useAsync !== undefined ? options.useAsync : this.useAsyncMode;
        
        // Configure UI
        document.getElementById('log-operation-name').textContent = operationName;
        this.updateStatus('Starting...', `Initiating ${operationName.toLowerCase()}`);
        this.showProgressBar();
        this.closeButton.disabled = true;
        this.cancelButton.style.display = 'inline-block';
        this.modalCloseButton.disabled = true;
        
        // Show modal
        this.bootstrapModal.show();
        
        // Start timer
        this.startTimer();
        
        // Create abort controller for this operation
        this.abortController = new AbortController();
        
        try {
            if (useAsync) {
                // Try async mode first
                await this.executeOperationAsync(apiUrl, payload);
            } else {
                // Use legacy sync mode
                await this.executeOperation(apiUrl, payload);
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                this.appendLog('❌ Operation cancelled by user', 'error');
                this.updateStatus('Cancelled', 'Operation was cancelled', 'warning');
            } else {
                this.appendLog(`❌ Error: ${error.message}`, 'error');
                this.updateStatus('Failed', error.message, 'danger');
            }
            this.finishOperation();
        }
    }
    
    /**
     * Execute operation in async mode (returns immediately, tracks via action_id)
     */
    async executeOperationAsync(apiUrl, payload) {
        // Convert sync URL to async URL (e.g., /start -> /action/start)
        const asyncUrl = apiUrl.replace(/\/(start|stop|restart|build)$/, '/action/$1');
        
        this.appendLog(`🚀 Starting operation: ${asyncUrl}`, 'info');
        this.appendLog('═══════════════════════════════════════════════', 'separator');
        
        try {
            const response = await fetch(asyncUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: this.abortController.signal
            });
            
            const result = await response.json();
            
            if (!response.ok || !result.success) {
                // Check if it's a conflict (action already in progress)
                if (response.status === 409) {
                    this.appendLog(`⚠️ ${result.error || 'Action already in progress'}`, 'warning');
                    this.updateStatus('Action in Progress', result.error, 'warning');
                    this.finishOperation();
                    return;
                }
                throw new Error(result.error || `HTTP ${response.status}`);
            }
            
            // Store action ID and start tracking
            this.currentActionId = result.action_id;
            this.appendLog(`📋 Action ID: ${result.action_id}`, 'info');
            this.appendLog(`📦 Action Type: ${result.action?.action_type || 'unknown'}`, 'info');
            this.appendLog('─────────────────────────────────────────────', 'separator');
            
            // Start polling for status and output (WebSocket will also update)
            this.startPolling();
            
        } catch (error) {
            // If async endpoint doesn't exist, fall back to sync mode
            if (error.message.includes('404') || error.message.includes('Not Found')) {
                console.log('Async endpoint not found, falling back to sync mode');
                this.appendLog('📡 Using synchronous mode...', 'info');
                await this.executeOperation(apiUrl.replace('/action/', '/'), payload);
            } else {
                throw error;
            }
        }
    }
    
    /**
     * Start polling for action status and output
     */
    startPolling() {
        if (!this.currentActionId) return;
        
        // Poll status every 1 second
        this.actionPollingInterval = setInterval(() => this.pollActionStatus(), 1000);
        
        // Poll output every 500ms for near-real-time streaming
        this.outputPollingInterval = setInterval(() => this.pollActionOutput(), 500);
    }
    
    /**
     * Stop polling
     */
    stopPolling() {
        if (this.actionPollingInterval) {
            clearInterval(this.actionPollingInterval);
            this.actionPollingInterval = null;
        }
        if (this.outputPollingInterval) {
            clearInterval(this.outputPollingInterval);
            this.outputPollingInterval = null;
        }
    }
    
    /**
     * Poll action status
     */
    async pollActionStatus() {
        if (!this.currentActionId) return;
        
        try {
            const response = await fetch(`/api/container-actions/${this.currentActionId}`);
            if (!response.ok) return;
            
            const result = await response.json();
            if (!result.success || !result.action) return;
            
            const action = result.action;
            
            // Update progress
            this.updateProgressBar(action.progress_percentage);
            
            // Update status based on action status
            if (action.status === 'running') {
                this.updateStatus(
                    action.current_step || 'Running...',
                    `${Math.round(action.progress_percentage)}% complete`,
                    'info'
                );
            } else if (action.status === 'completed') {
                this.stopPolling();
                this.updateProgressBar(100);
                this.updateStatus('Completed Successfully', `Duration: ${action.duration_seconds?.toFixed(1)}s`, 'success');
                this.appendLog('═══════════════════════════════════════════════', 'separator');
                this.appendLog('✅ Operation completed successfully!', 'success');
                this.finishOperation();
            } else if (action.status === 'failed') {
                this.stopPolling();
                this.updateStatus('Failed', action.error_message || 'Operation failed', 'danger');
                this.appendLog('═══════════════════════════════════════════════', 'separator');
                this.appendLog(`❌ Operation failed: ${action.error_message || 'Unknown error'}`, 'error');
                this.finishOperation();
            } else if (action.status === 'cancelled') {
                this.stopPolling();
                this.updateStatus('Cancelled', 'Operation was cancelled', 'warning');
                this.appendLog('═══════════════════════════════════════════════', 'separator');
                this.appendLog('⚠️ Operation cancelled', 'warning');
                this.finishOperation();
            }
        } catch (error) {
            console.error('Error polling action status:', error);
        }
    }
    
    /**
     * Poll action output for streaming logs
     */
    async pollActionOutput() {
        if (!this.currentActionId) return;
        
        try {
            const response = await fetch(
                `/api/container-actions/${this.currentActionId}/output?offset=${this.lastOutputOffset}`
            );
            if (!response.ok) return;
            
            const result = await response.json();
            if (!result.success) return;
            
            // Append new output
            if (result.output && result.output.length > 0) {
                // Split by lines and append each
                const lines = result.output.split('\n');
                for (const line of lines) {
                    if (line.trim()) {
                        // Determine line type based on content
                        let type = 'output';
                        if (line.includes('error') || line.includes('Error') || line.includes('ERROR')) {
                            type = 'error';
                        } else if (line.includes('warning') || line.includes('Warning') || line.includes('WARN')) {
                            type = 'warning';
                        } else if (line.startsWith('#') || line.startsWith('Step ')) {
                            type = 'info';
                        }
                        this.appendLog(line, type);
                    }
                }
                this.lastOutputOffset = result.total_length;
            }
        } catch (error) {
            console.error('Error polling action output:', error);
        }
    }
    
    /**
     * Update progress bar
     */
    updateProgressBar(percentage) {
        if (this.progressBar) {
            this.progressBar.style.width = `${percentage}%`;
        }
    }
    
    /**
     * Show progress bar
     */
    showProgressBar() {
        if (this.progressBarContainer) {
            this.progressBarContainer.style.display = 'block';
        }
        this.updateProgressBar(0);
    }
    
    /**
     * Hide progress bar
     */
    hideProgressBar() {
        if (this.progressBarContainer) {
            this.progressBarContainer.style.display = 'none';
        }
    }
    
    /**
     * Finish operation and reset UI state
     */
    finishOperation() {
        this.operationInProgress = false;
        this.closeButton.disabled = false;
        this.cancelButton.style.display = 'none';
        this.modalCloseButton.disabled = false;
        this.stopTimer();
        this.stopPolling();
        this.currentActionId = null;
        this.lastOutputOffset = 0;
    }

    /**
     * Execute the operation with progress tracking
     */
    async executeOperation(apiUrl, payload) {
        this.appendLog(`🚀 Starting operation: ${apiUrl}`, 'info');
        this.appendLog('═══════════════════════════════════════════════', 'separator');

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
            signal: this.abortController.signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        const result = await response.json();

        // Parse and display the results
        this.displayResults(result);

        // Update final status
        if (result.success) {
            this.updateStatus('Completed Successfully', 'Operation finished without errors', 'success');
            this.appendLog('═══════════════════════════════════════════════', 'separator');
            this.appendLog('✅ Operation completed successfully!', 'success');
        } else {
            this.updateStatus('Failed', result.error || 'Operation failed', 'danger');
            this.appendLog('═══════════════════════════════════════════════', 'separator');
            this.appendLog(`❌ Operation failed: ${result.error || 'Unknown error'}`, 'error');
        }
    }

    /**
     * Display operation results
     */
    displayResults(result) {
        if (result.build) {
            this.appendLog('\n📦 Build Output:', 'section');
            this.appendLog('─────────────────────────────────────────────', 'separator');
            if (result.build.stdout) {
                this.appendLog(result.build.stdout, 'output');
            }
            if (result.build.stderr) {
                this.appendLog(result.build.stderr, 'error');
            }
            if (result.build.exit_code !== undefined) {
                this.appendLog(`Exit code: ${result.build.exit_code}`, 'info');
            }
        }

        if (result.up) {
            this.appendLog('\n🚀 Start Output:', 'section');
            this.appendLog('─────────────────────────────────────────────', 'separator');
            if (result.up.stdout) {
                this.appendLog(result.up.stdout, 'output');
            }
            if (result.up.stderr) {
                this.appendLog(result.up.stderr, 'error');
            }
            if (result.up.exit_code !== undefined) {
                this.appendLog(`Exit code: ${result.up.exit_code}`, 'info');
            }
        }

        // Handle other result types (start, stop, restart)
        if (result.stdout && !result.build && !result.up) {
            this.appendLog('\n📄 Command Output:', 'section');
            this.appendLog('─────────────────────────────────────────────', 'separator');
            this.appendLog(result.stdout, 'output');
        }

        if (result.stderr && !result.build && !result.up) {
            this.appendLog(result.stderr, 'error');
        }

        if (result.exit_code !== undefined && !result.build && !result.up) {
            this.appendLog(`\nExit code: ${result.exit_code}`, 'info');
        }

        // Display any status summary
        if (result.status_summary) {
            this.appendLog('\n📊 Status Summary:', 'section');
            this.appendLog('─────────────────────────────────────────────', 'separator');
            this.appendLog(JSON.stringify(result.status_summary, null, 2), 'info');
        }

        // Display preflight info
        if (result.preflight) {
            this.appendLog('\n🔍 Preflight Checks:', 'section');
            this.appendLog('─────────────────────────────────────────────', 'separator');
            this.appendLog(`Compose file exists: ${result.preflight.compose_file_exists ? '✓' : '✗'}`, 'info');
            this.appendLog(`Docker available: ${result.preflight.docker_available ? '✓' : '✗'}`, 'info');
        }
    }

    /**
     * Append log entry
     */
    appendLog(text, type = 'output') {
        if (!this.outputElement) return;

        const timestamp = new Date().toLocaleTimeString();
        let colorClass = '';
        let prefix = '';

        switch (type) {
            case 'error':
                colorClass = 'text-danger';
                break;
            case 'success':
                colorClass = 'text-success';
                break;
            case 'warning':
                colorClass = 'text-warning';
                break;
            case 'info':
                colorClass = 'text-info';
                break;
            case 'section':
                colorClass = 'text-primary fw-bold';
                prefix = '\n';
                break;
            case 'separator':
                colorClass = 'text-secondary';
                break;
            default:
                colorClass = 'text-white';
        }

        const line = document.createElement('div');
        line.className = colorClass;
        line.textContent = `${prefix}${text}`;
        
        this.outputElement.appendChild(line);
        this.logs.push({ timestamp, text, type });

        // Update line count
        this.lineCountElement.textContent = `${this.logs.length} lines`;

        // Auto-scroll to bottom
        if (this.autoScroll) {
            this.scrollToBottom();
        }
    }

    /**
     * Update status banner
     */
    updateStatus(statusText, detailText = '', severity = 'info') {
        if (this.statusElement) {
            this.statusElement.textContent = statusText;
        }
        if (this.statusDetailElement && detailText) {
            this.statusDetailElement.textContent = detailText;
        }
        
        // Dark-themed status colors (matches modal dark background)
        if (this.statusBanner) {
            const statusStyles = {
                info: { bg: 'rgba(32, 107, 196, 0.2)', border: 'rgba(32, 107, 196, 0.4)', spinner: 'text-info' },
                success: { bg: 'rgba(47, 179, 68, 0.2)', border: 'rgba(47, 179, 68, 0.4)', spinner: 'text-success' },
                danger: { bg: 'rgba(214, 57, 57, 0.2)', border: 'rgba(214, 57, 57, 0.4)', spinner: 'text-danger' },
                warning: { bg: 'rgba(247, 103, 7, 0.2)', border: 'rgba(247, 103, 7, 0.4)', spinner: 'text-warning' }
            };
            const style = statusStyles[severity] || statusStyles.info;
            
            this.statusBanner.className = 'rounded m-3 mb-0 p-3 d-flex align-items-center';
            this.statusBanner.style.background = style.bg;
            this.statusBanner.style.border = `1px solid ${style.border}`;
            
            // Update spinner color to match
            if (this.spinnerElement) {
                this.spinnerElement.className = `spinner-border spinner-border-sm me-3 ${style.spinner}`;
            }
        }

        // Update spinner visibility
        if (this.spinnerElement) {
            if (severity === 'info' && this.operationInProgress) {
                this.spinnerElement.style.display = 'inline-block';
            } else {
                this.spinnerElement.style.display = 'none';
            }
        }
    }

    /**
     * Start elapsed time timer
     */
    startTimer() {
        this.timerInterval = setInterval(() => {
            if (this.startTime && this.elapsedTimeElement) {
                const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                this.elapsedTimeElement.textContent = minutes > 0 
                    ? `${minutes}m ${seconds}s` 
                    : `${seconds}s`;
            }
        }, 1000);
    }

    /**
     * Stop timer
     */
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    /**
     * Scroll to bottom of log output
     */
    scrollToBottom() {
        if (this.outputElement) {
            this.outputElement.scrollTop = this.outputElement.scrollHeight;
        }
    }

    /**
     * Copy logs to clipboard
     */
    copyLogs() {
        const text = this.logs.map(l => l.text).join('\n');
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Logs copied to clipboard', 'success');
        }).catch(() => {
            this.showToast('Failed to copy logs', 'danger');
        });
    }

    /**
     * Clear logs
     */
    clearLogs() {
        if (this.operationInProgress) {
            this.showToast('Cannot clear logs while operation is running', 'warning');
            return;
        }
        this.logs = [];
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
        }
        this.lineCountElement.textContent = '0 lines';
    }

    /**
     * Download logs as file
     */
    downloadLogs() {
        const text = this.logs.map(l => `[${l.timestamp}] ${l.text}`).join('\n');
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `container-operation-${Date.now()}.log`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('Logs downloaded', 'success');
    }

    /**
     * Cancel current operation
     */
    async cancelOperation() {
        // If we have an action ID, cancel via API
        if (this.currentActionId) {
            try {
                const response = await fetch(`/api/container-actions/${this.currentActionId}/cancel`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reason: 'Cancelled by user' })
                });
                
                if (response.ok) {
                    this.appendLog('\n⚠️ Cancellation requested...', 'warning');
                } else {
                    // Action may have already completed
                    this.appendLog('\n⚠️ Could not cancel (action may have already finished)', 'warning');
                }
            } catch (error) {
                console.error('Error cancelling action:', error);
            }
        }
        
        // Also abort any pending fetch
        if (this.abortController) {
            this.abortController.abort();
        }
    }

    /**
     * Reset modal state
     */
    reset() {
        this.logs = [];
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
        }
        this.startTime = null;
        this.autoScroll = true;
        this.currentActionId = null;
        this.lastOutputOffset = 0;
        this.stopPolling();
        if (this.elapsedTimeElement) {
            this.elapsedTimeElement.textContent = '0s';
        }
        if (this.lineCountElement) {
            this.lineCountElement.textContent = '0 lines';
        }
        this.updateStatus('Initializing...', '', 'info');
        this.updateProgressBar(0);
    }

    /**
     * Close modal
     */
    close() {
        if (this.operationInProgress) {
            if (!confirm('Operation is still in progress. Are you sure you want to close?')) {
                return;
            }
            this.cancelOperation();
        }
        this.bootstrapModal.hide();
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container') || (() => {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
            return container;
        })();
        
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show`;
        toast.role = 'alert';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        toastContainer.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }
}

// Global instance
window.containerLogsModal = null;

// Initialize on DOM ready
function initContainerLogs() {
    window.containerLogsModal = new ContainerLogsModal();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initContainerLogs);
} else {
    initContainerLogs();
}

document.addEventListener('htmx:historyRestore', function(evt) {
    initContainerLogs();
});

})();
