/**
 * Container Logs Module
 * ======================
 * 
 * Handles real-time display of Docker operation logs in a modal window.
 * Provides visual feedback for build, start, stop, and other container operations.
 */

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
     */
    async startOperation(operationName, apiUrl, payload = {}) {
        this.reset();
        this.operationInProgress = true;
        this.startTime = Date.now();
        
        // Configure UI
        document.getElementById('log-operation-name').textContent = operationName;
        this.updateStatus('Starting...', `Initiating ${operationName.toLowerCase()}`);
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
            // Make the API call with streaming
            await this.executeOperation(apiUrl, payload);
        } catch (error) {
            if (error.name === 'AbortError') {
                this.appendLog('❌ Operation cancelled by user', 'error');
                this.updateStatus('Cancelled', 'Operation was cancelled', 'warning');
            } else {
                this.appendLog(`❌ Error: ${error.message}`, 'error');
                this.updateStatus('Failed', error.message, 'danger');
            }
        } finally {
            this.operationInProgress = false;
            this.closeButton.disabled = false;
            this.cancelButton.style.display = 'none';
            this.modalCloseButton.disabled = false;
            this.stopTimer();
        }
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
        if (this.statusBanner) {
            this.statusBanner.className = `alert alert-${severity} m-3 mb-0`;
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
    cancelOperation() {
        if (this.abortController) {
            this.abortController.abort();
            this.appendLog('\n⚠️ Cancellation requested...', 'warning');
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
        if (this.elapsedTimeElement) {
            this.elapsedTimeElement.textContent = '0s';
        }
        if (this.lineCountElement) {
            this.lineCountElement.textContent = '0 lines';
        }
        this.updateStatus('Initializing...', '', 'info');
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
document.addEventListener('DOMContentLoaded', () => {
    window.containerLogsModal = new ContainerLogsModal();
});
