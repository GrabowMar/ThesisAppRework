/**
 * Application Manager - Core Application Logic
 * Extracted from base.html to improve maintainability
 */

// Application namespace
const AppManager = {
    // Initialize the application
    init() {
        this.setupNavigation();
        this.loadStats();
        this.loadActivityFeed();
        this.setupHTMXHandlers();
        this.setupKeyboardShortcuts();
    },

    // Setup navigation active states
    setupNavigation() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.nav-link');
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            const href = link.getAttribute('href');
            
            if (href === currentPath || 
                (currentPath === '/' && link.dataset.page === 'dashboard') ||
                (currentPath.includes('/testing') && link.dataset.page === 'testing') ||
                (currentPath.includes('/models') && link.dataset.page === 'models')) {
                link.classList.add('active');
            }
        });
    },

    // Load sidebar statistics
    async loadStats() {
        try {
            const response = await fetch('/api/quick-stats');
            if (response.ok) {
                const data = await response.json();
                document.getElementById('stat-models').textContent = data.models || '0';
                document.getElementById('stat-apps').textContent = data.apps || '0';
                document.getElementById('stat-active').textContent = data.active || '0';
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    },

    // Load activity feed
    async loadActivityFeed() {
        try {
            const response = await fetch('/api/activity-feed');
            if (response.ok) {
                const html = await response.text();
                document.getElementById('activity-feed').innerHTML = html;
            }
        } catch (error) {
            console.error('Failed to load activity feed:', error);
        }
    },

    // Setup HTMX event handlers
    setupHTMXHandlers() {
        document.body.addEventListener('htmx:afterRequest', (event) => {
            if (event.detail.successful) {
                this.showToast('Operation completed successfully', 'success');
            }
        });

        document.body.addEventListener('htmx:responseError', (event) => {
            this.showToast('An error occurred. Please try again.', 'error');
            console.error('HTMX Error:', event.detail);
        });
    },

    // Setup keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+K - Focus search
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                const search = document.querySelector('input[type="search"], input[name="search"]');
                if (search) search.focus();
            }

            // Ctrl+R - Refresh data
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                this.refreshData();
            }

            // Escape - Close modals
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    },

    // Show toast notification
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        }[type];
        
        toast.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="margin-left: auto; background: none; border: none; cursor: pointer;">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    },

    // Refresh all data
    refreshData() {
        this.loadStats();
        this.loadActivityFeed();
        
        // Trigger HTMX refresh for any auto-updating elements
        document.querySelectorAll('[hx-trigger*="load"]').forEach(el => {
            htmx.trigger(el, 'load');
        });
        
        this.showToast('Data refreshed', 'success');
    },

    // Close all modals
    closeAllModals() {
        document.querySelectorAll('.modal.show').forEach(modal => {
            modal.classList.remove('show');
            modal.style.display = 'none';
        });
    },

    // Toggle sidebar (mobile)
    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        sidebar.classList.toggle('show');
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    AppManager.init();
});

// Auto-refresh stats every 30 seconds
setInterval(() => {
    AppManager.loadStats();
}, 30000);

// Export for global access
window.AppManager = AppManager;