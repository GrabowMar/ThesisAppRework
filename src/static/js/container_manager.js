/**
 * Container Management JavaScript Module
 * ==========================================
 * 
 * Handles Docker container lifecycle operations through the UI:
 * - Start/stop/restart containers
 * - Build images
 * - View logs and diagnostics
 * - Real-time status updates
 * - Port testing and management
 */

class ContainerManager {
    constructor(modelSlug, appNumber) {
        this.modelSlug = modelSlug;
        this.appNumber = appNumber;
        this.baseUrl = `/api/app/${modelSlug}/${appNumber}`;
        this.pollingInterval = null;
        this.statusCheckDelay = 2000; // 2 seconds
    }

    /**
     * Initialize the container manager
     */
    init() {
        this.bindEvents();
        this.startStatusPolling();
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Container control buttons
        document.getElementById('btn-container-start')?.addEventListener('click', () => this.start());
        document.getElementById('btn-container-stop')?.addEventListener('click', () => this.stop());
        document.getElementById('btn-container-restart')?.addEventListener('click', () => this.restart());
        document.getElementById('btn-container-build')?.addEventListener('click', () => this.build());
        document.getElementById('btn-container-rebuild')?.addEventListener('click', () => this.rebuild());
        
        // Diagnostics and logs
        document.getElementById('btn-diagnostics-refresh')?.addEventListener('click', () => this.refreshDiagnostics());
        document.getElementById('btn-logs-refresh')?.addEventListener('click', () => this.refreshLogs());
        document.getElementById('btn-logs-tail')?.addEventListener('click', () => this.tailLogs());
        document.getElementById('btn-logs-download')?.addEventListener('click', () => this.downloadLogs());
        
        // Port testing
        document.querySelectorAll('[data-action="test-port"]').forEach(btn => {
            btn.addEventListener('click', (e) => this.testPort(e.target.dataset.port));
        });
        document.getElementById('btn-test-all-ports')?.addEventListener('click', () => this.testAllPorts());
    }

    /**
     * Start containers
     */
    async start() {
        if (!window.containerLogsModal) {
            this.showToast('Logs modal not initialized', 'danger');
            return;
        }
        
        try {
            await window.containerLogsModal.startOperation(
                'Start Containers',
                `${this.baseUrl}/start`,
                {}
            );
            await this.refreshStatus();
        } catch (error) {
            console.error('Start error:', error);
        }
    }

    /**
     * Stop containers
     */
    async stop() {
        if (!confirm('Are you sure you want to stop all containers for this app?')) {
            return;
        }
        
        if (!window.containerLogsModal) {
            this.showToast('Logs modal not initialized', 'danger');
            return;
        }
        
        try {
            await window.containerLogsModal.startOperation(
                'Stop Containers',
                `${this.baseUrl}/stop`,
                {}
            );
            await this.refreshStatus();
        } catch (error) {
            console.error('Stop error:', error);
        }
    }

    /**
     * Restart containers
     */
    async restart() {
        if (!window.containerLogsModal) {
            this.showToast('Logs modal not initialized', 'danger');
            return;
        }
        
        try {
            await window.containerLogsModal.startOperation(
                'Restart Containers',
                `${this.baseUrl}/restart`,
                {}
            );
            await this.refreshStatus();
        } catch (error) {
            console.error('Restart error:', error);
        }
    }

    /**
     * Build containers (with cache)
     */
    async build() {
        if (!window.containerLogsModal) {
            this.showToast('Logs modal not initialized', 'danger');
            return;
        }
        
        try {
            await window.containerLogsModal.startOperation(
                'Build Containers',
                `${this.baseUrl}/build`,
                { no_cache: false, start_after: true }
            );
            await this.refreshStatus();
        } catch (error) {
            console.error('Build error:', error);
        }
    }

    /**
     * Rebuild containers (no cache)
     */
    async rebuild() {
        if (!confirm('Rebuild will clear Docker cache and may take several minutes. Continue?')) {
            return;
        }
        
        if (!window.containerLogsModal) {
            this.showToast('Logs modal not initialized', 'danger');
            return;
        }
        
        try {
            await window.containerLogsModal.startOperation(
                'Rebuild Containers (No Cache)',
                `${this.baseUrl}/build`,
                { no_cache: true, start_after: true }
            );
            await this.refreshStatus();
        } catch (error) {
            console.error('Rebuild error:', error);
        }
    }

    /**
     * Refresh container status
     */
    async refreshStatus() {
        try {
            const response = await fetch(`${this.baseUrl}/status`);
            const data = await response.json();
            
            if (data.success) {
                this.updateStatusUI(data.data);
            }
        } catch (error) {
            console.error('Error refreshing status:', error);
        }
    }

    /**
     * Refresh diagnostics panel
     */
    async refreshDiagnostics() {
        try {
            this.setButtonLoading('btn-diagnostics-refresh', true);
            
            const response = await fetch(`${this.baseUrl}/diagnostics`);
            const data = await response.json();
            
            if (data.success) {
                this.updateDiagnosticsUI(data.data);
                this.showToast('Diagnostics refreshed', 'success');
            } else {
                this.showToast('Failed to refresh diagnostics', 'warning');
            }
        } catch (error) {
            this.showToast(`Error: ${error.message}`, 'danger');
        } finally {
            this.setButtonLoading('btn-diagnostics-refresh', false);
        }
    }

    /**
     * Refresh logs
     */
    async refreshLogs() {
        try {
            this.setButtonLoading('btn-logs-refresh', true);
            
            const response = await fetch(`${this.baseUrl}/logs?lines=100`);
            const data = await response.json();
            
            if (data.success) {
                this.updateLogsUI(data.data.logs);
                this.showToast('Logs refreshed', 'success');
            } else {
                this.showToast('Failed to refresh logs', 'warning');
            }
        } catch (error) {
            this.showToast(`Error: ${error.message}`, 'danger');
        } finally {
            this.setButtonLoading('btn-logs-refresh', false);
        }
    }

    /**
     * Tail logs (live stream)
     */
    async tailLogs() {
        // TODO: Implement WebSocket log streaming
        this.showToast('Live log streaming coming soon!', 'info');
    }

    /**
     * Download logs as file
     */
    async downloadLogs() {
        try {
            const response = await fetch(`${this.baseUrl}/logs?lines=1000`);
            const data = await response.json();
            
            if (data.success && data.data.logs) {
                const blob = new Blob([data.data.logs], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${this.modelSlug}_app${this.appNumber}_logs.txt`;
                a.click();
                URL.revokeObjectURL(url);
                
                this.showToast('Logs downloaded', 'success');
            } else {
                this.showToast('No logs available', 'warning');
            }
        } catch (error) {
            this.showToast(`Error downloading logs: ${error.message}`, 'danger');
        }
    }

    /**
     * Test specific port
     */
    async testPort(port) {
        try {
            const response = await fetch(`${this.baseUrl}/test-port/${port}`);
            const data = await response.json();
            
            if (data.accessible) {
                this.showToast(`Port ${port} is accessible ✓`, 'success');
            } else {
                this.showToast(`Port ${port} is not reachable`, 'warning');
            }
            
            return data.accessible;
        } catch (error) {
            this.showToast(`Error testing port ${port}: ${error.message}`, 'danger');
            return false;
        }
    }

    /**
     * Test all ports
     */
    async testAllPorts() {
        const portElements = document.querySelectorAll('[data-port]');
        const ports = Array.from(portElements).map(el => el.dataset.port);
        
        if (ports.length === 0) {
            this.showToast('No ports to test', 'info');
            return;
        }
        
        this.setButtonLoading('btn-test-all-ports', true);
        this.showToast(`Testing ${ports.length} ports...`, 'info');
        
        const results = await Promise.all(
            ports.map(port => this.testPort(port))
        );
        
        const accessible = results.filter(r => r).length;
        
        if (accessible === ports.length) {
            this.showToast(`All ${ports.length} ports accessible ✓`, 'success');
        } else {
            this.showToast(`${accessible}/${ports.length} ports accessible`, 'warning');
        }
        
        this.setButtonLoading('btn-test-all-ports', false);
    }

    /**
     * Update status UI
     */
    updateStatusUI(statusData) {
        // Update status badge
        const statusBadge = document.getElementById('container-status-badge');
        if (statusBadge && statusData.status) {
            const status = statusData.status.toLowerCase();
            const colorMap = {
                'running': 'success',
                'stopped': 'secondary',
                'building': 'warning',
                'error': 'danger'
            };
            const color = colorMap[status] || 'secondary';
            statusBadge.className = `badge bg-${color}`;
            statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        }
        
        // Update button states based on status
        const isRunning = statusData.status?.toLowerCase() === 'running';
        const startBtn = document.getElementById('btn-container-start');
        const stopBtn = document.getElementById('btn-container-stop');
        
        if (startBtn) startBtn.disabled = isRunning;
        if (stopBtn) stopBtn.disabled = !isRunning;
    }

    /**
     * Update diagnostics UI
     */
    updateDiagnosticsUI(diagnostics) {
        const panel = document.getElementById('diagnostics-panel');
        if (!panel) return;
        
        let html = '<div class="list-group list-group-flush">';
        
        if (diagnostics.compose_file_exists) {
            html += '<div class="list-group-item"><span class="text-success">✓</span> docker-compose.yml found</div>';
        } else {
            html += '<div class="list-group-item"><span class="text-danger">✗</span> docker-compose.yml missing</div>';
        }
        
        if (diagnostics.docker_available) {
            html += '<div class="list-group-item"><span class="text-success">✓</span> Docker daemon available</div>';
        } else {
            html += '<div class="list-group-item"><span class="text-danger">✗</span> Docker daemon unavailable</div>';
        }
        
        if (diagnostics.status_summary) {
            const summary = diagnostics.status_summary;
            html += `<div class="list-group-item">Containers: ${summary.running || 0} running, ${summary.stopped || 0} stopped</div>`;
        }
        
        html += '</div>';
        panel.innerHTML = html;
    }

    /**
     * Update logs UI
     */
    updateLogsUI(logs) {
        const logsPanel = document.getElementById('logs-panel');
        if (!logsPanel) return;
        
        if (logs && logs.length > 0) {
            logsPanel.innerHTML = `<pre class="bg-dark text-white p-3 rounded" style="max-height: 400px; overflow: auto;">${this.escapeHtml(logs)}</pre>`;
        } else {
            logsPanel.innerHTML = '<div class="alert alert-info">No logs available</div>';
        }
    }

    /**
     * Start status polling
     */
    startStatusPolling() {
        // Initial status check
        this.refreshStatus();
        
        // Poll every 5 seconds
        this.pollingInterval = setInterval(() => {
            this.refreshStatus();
        }, 5000);
    }

    /**
     * Stop status polling
     */
    stopStatusPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    /**
     * Set button loading state
     */
    setButtonLoading(buttonId, loading) {
        const button = document.getElementById(buttonId);
        if (!button) return;
        
        if (loading) {
            button.dataset.originalHtml = button.innerHTML;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading...';
            button.disabled = true;
        } else {
            button.innerHTML = button.dataset.originalHtml || button.innerHTML;
            button.disabled = false;
        }
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
            ${this.escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        toastContainer.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Cleanup on destroy
     */
    destroy() {
        this.stopStatusPolling();
    }
}

// Auto-initialize if container management section exists
document.addEventListener('DOMContentLoaded', () => {
    const containerSection = document.getElementById('container-management-section');
    if (containerSection) {
        const modelSlug = containerSection.dataset.modelSlug;
        const appNumber = parseInt(containerSection.dataset.appNumber);
        
        if (modelSlug && appNumber) {
            window.containerManager = new ContainerManager(modelSlug, appNumber);
            window.containerManager.init();
        }
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.containerManager) {
        window.containerManager.destroy();
    }
});
