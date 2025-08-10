// ===================================================================
// Modern Interactive Components for AI Research Platform
// ===================================================================

class PlatformUI {
    constructor() {
        this.init();
    }

    init() {
        this.setupGlobalSearch();
        this.setupKeyboardShortcuts();
        this.setupToastSystem();
        this.setupThemeManager();
        this.setupDataVisualization();
        this.setupModalEnhancements();
        console.log('✅ Platform UI initialized');
    }

    // ===================================================================
    // Global Search Enhancement
    // ===================================================================
    setupGlobalSearch() {
        const searchInput = document.getElementById('global-search');
        const searchResults = document.getElementById('search-results');
        
        if (!searchInput || !searchResults) return;

        let searchTimeout;
        
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();
            
            if (query.length < 2) {
                this.hideSearchResults();
                return;
            }
            
            searchTimeout = setTimeout(() => {
                this.performSearch(query);
            }, 300);
        });

        searchInput.addEventListener('focus', () => {
            if (searchInput.value.length >= 2) {
                this.showSearchResults();
            }
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                this.hideSearchResults();
            }
        });
    }

    performSearch(query) {
        const searchResults = document.getElementById('search-results');
        
        // Show loading state
        searchResults.innerHTML = `
            <div class="p-3 text-center">
                <div class="loading-spinner loading-spinner-sm me-2"></div>
                Searching...
            </div>
        `;
        this.showSearchResults();

        // Perform HTMX search
        htmx.ajax('POST', '/api/search', {
            values: { query: query },
            target: '#search-results',
            swap: 'innerHTML'
        });
    }

    showSearchResults() {
        const searchResults = document.getElementById('search-results');
        searchResults.classList.remove('d-none');
        searchResults.classList.add('search-dropdown-active');
    }

    hideSearchResults() {
        const searchResults = document.getElementById('search-results');
        searchResults.classList.add('d-none');
        searchResults.classList.remove('search-dropdown-active');
    }

    // ===================================================================
    // Keyboard Shortcuts
    // ===================================================================
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K for global search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('global-search')?.focus();
                return;
            }

            // Escape to close modals and search
            if (e.key === 'Escape') {
                this.hideSearchResults();
                // Close any open modals
                const activeModal = document.querySelector('.modal.show');
                if (activeModal) {
                    const modal = bootstrap.Modal.getInstance(activeModal);
                    modal?.hide();
                }
                return;
            }

            // Alt + 1-9 for quick navigation
            if (e.altKey && e.key >= '1' && e.key <= '9') {
                e.preventDefault();
                const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
                const index = parseInt(e.key) - 1;
                if (navLinks[index]) {
                    navLinks[index].click();
                }
                return;
            }
        });
    }

    // ===================================================================
    // Enhanced Toast System
    // ===================================================================
    setupToastSystem() {
        this.toastContainer = document.getElementById('toastContainer') || this.createToastContainer();
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }

    showToast(message, type = 'info', duration = 5000) {
        const toastId = 'toast-' + Date.now();
        const iconMap = {
            success: 'check-circle text-success',
            error: 'exclamation-triangle text-danger',
            warning: 'exclamation-circle text-warning',
            info: 'info-circle text-info'
        };

        const toastHtml = `
            <div class="toast toast-enter" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="fas fa-${iconMap[type]} me-2"></i>
                    <strong class="me-auto">AI Research Platform</strong>
                    <small class="text-muted">now</small>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;

        this.toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: duration });
        
        toast.show();

        // Remove element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });

        return toast;
    }

    // ===================================================================
    // Theme Management
    // ===================================================================
    setupThemeManager() {
        const themeToggle = document.getElementById('theme-toggle');
        const currentTheme = localStorage.getItem('theme') || 'light';
        
        this.setTheme(currentTheme);
        
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                const newTheme = document.body.classList.contains('dark-mode') ? 'light' : 'dark';
                this.setTheme(newTheme);
                localStorage.setItem('theme', newTheme);
            });
        }
    }

    setTheme(theme) {
        const body = document.body;
        const themeToggle = document.getElementById('theme-toggle');
        
        if (theme === 'dark') {
            body.classList.add('dark-mode');
            if (themeToggle) {
                themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
            }
        } else {
            body.classList.remove('dark-mode');
            if (themeToggle) {
                themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
            }
        }
    }

    // ===================================================================
    // Data Visualization Enhancement
    // ===================================================================
    setupDataVisualization() {
        // Initialize Chart.js defaults
        if (typeof Chart !== 'undefined') {
            Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
            Chart.defaults.color = '#6b7280';
            Chart.defaults.borderColor = '#e5e7eb';
            Chart.defaults.backgroundColor = 'rgba(8, 145, 240, 0.1)';
        }
    }

    createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === 'undefined') return null;

        const ctx = canvas.getContext('2d');
        
        // Default configuration
        const defaultConfig = {
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            padding: 20
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: '#f3f4f6'
                        }
                    },
                    x: {
                        grid: {
                            color: '#f3f4f6'
                        }
                    }
                }
            }
        };

        // Merge configurations
        const mergedConfig = this.mergeDeep(defaultConfig, config);
        
        return new Chart(ctx, mergedConfig);
    }

    // ===================================================================
    // Modal Enhancements
    // ===================================================================
    setupModalEnhancements() {
        // Add backdrop blur effect
        document.addEventListener('show.bs.modal', (e) => {
            document.body.style.backdropFilter = 'blur(4px)';
        });

        document.addEventListener('hidden.bs.modal', (e) => {
            document.body.style.backdropFilter = '';
        });

        // Auto-focus first input in modals
        document.addEventListener('shown.bs.modal', (e) => {
            const firstInput = e.target.querySelector('input, textarea, select');
            if (firstInput && !firstInput.hasAttribute('readonly')) {
                firstInput.focus();
            }
        });
    }

    // ===================================================================
    // Utility Functions
    // ===================================================================
    mergeDeep(target, source) {
        const isObject = (obj) => obj && typeof obj === 'object';
        
        if (!isObject(target) || !isObject(source)) {
            return source;
        }
        
        Object.keys(source).forEach(key => {
            const targetValue = target[key];
            const sourceValue = source[key];
            
            if (Array.isArray(targetValue) && Array.isArray(sourceValue)) {
                target[key] = targetValue.concat(sourceValue);
            } else if (isObject(targetValue) && isObject(sourceValue)) {
                target[key] = this.mergeDeep(Object.assign({}, targetValue), sourceValue);
            } else {
                target[key] = sourceValue;
            }
        });
        
        return target;
    }

    // ===================================================================
    // Public API Methods
    // ===================================================================
    showGlobalSearch() {
        document.getElementById('global-search')?.focus();
    }

    showKeyboardShortcuts() {
        const shortcuts = [
            { key: 'Ctrl/Cmd + K', description: 'Open global search' },
            { key: 'Escape', description: 'Close modals and search' },
            { key: 'Alt + 1-9', description: 'Quick navigation' }
        ];

        const shortcutsList = shortcuts.map(s => 
            `<div class="d-flex justify-content-between"><kbd>${s.key}</kbd><span>${s.description}</span></div>`
        ).join('');

        this.showToast(`
            <div class="fw-medium mb-2">Keyboard Shortcuts</div>
            <div class="small">${shortcutsList}</div>
        `, 'info', 8000);
    }

    refreshStats() {
        // Trigger refresh of all stat elements
        document.querySelectorAll('[hx-trigger*="every"]').forEach(element => {
            if (element.hasAttribute('hx-get')) {
                htmx.trigger(element, 'refresh');
            }
        });
    }
}

// ===================================================================
// Global Modal Functions (Enhanced)
// ===================================================================
function openSecurityTestModal() {
    const modal = new bootstrap.Modal(document.getElementById('securityTestModal'));
    modal.show();
}

function openPerformanceTestModal() {
    window.platformUI?.showToast('Performance test modal coming soon! 🚀', 'info');
}

function openBatchAnalysisModal() {
    window.platformUI?.showToast('Batch analysis modal coming soon! 📊', 'info');
}

function showContainerOverview() {
    window.platformUI?.showToast('Container overview coming soon! 🐳', 'info');
}

function showSystemStatus() {
    // This could open a detailed system status modal
    window.platformUI?.showToast('System status: All services operational ✅', 'success');
}

function exportData() {
    window.platformUI?.showToast('Data export functionality coming soon! 💾', 'info');
}

function showKeyboardShortcuts() {
    window.platformUI?.showKeyboardShortcuts();
}

function exportModelData(modelSlug) {
    window.platformUI?.showToast(`Exporting data for ${modelSlug}...`, 'info');
}

function openModelActions(modelSlug) {
    window.platformUI?.showToast(`Model actions for ${modelSlug}`, 'info');
}

// ===================================================================
// Enhanced HTMX Event Handlers
// ===================================================================
document.addEventListener('htmx:responseError', (e) => {
    console.error('HTMX Response Error:', e.detail);
    window.platformUI?.showToast('Network error occurred. Please try again.', 'error');
});

document.addEventListener('htmx:sendError', (e) => {
    console.error('HTMX Send Error:', e.detail);
    window.platformUI?.showToast('Connection error. Please check your network.', 'error');
});

document.addEventListener('htmx:timeout', (e) => {
    console.warn('HTMX Timeout:', e.detail);
    window.platformUI?.showToast('Request timed out. Please try again.', 'warning');
});

// ===================================================================
// Initialize Platform UI
// ===================================================================
document.addEventListener('DOMContentLoaded', () => {
    window.platformUI = new PlatformUI();
    
    // Show welcome message for new users
    if (localStorage.getItem('first_visit') !== 'false') {
        setTimeout(() => {
            window.platformUI.showToast(
                'Welcome to the AI Research Platform! Use Ctrl+K to search and explore. 🎉',
                'info',
                8000
            );
            localStorage.setItem('first_visit', 'false');
        }, 2000);
    }

    // Initialize tooltips and popovers
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));

    console.log('🚀 AI Research Platform loaded successfully');
});
