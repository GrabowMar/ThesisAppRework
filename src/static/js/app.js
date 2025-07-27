/**
 * Application JavaScript
 * Minimal JavaScript for HTMX-based Thesis Research App
 * Version: 2.0.0
 */

// Global app namespace
window.ThesisApp = {
    // Configuration
    config: {
        refreshInterval: 30000, // 30 seconds
        debounceDelay: 300,
        maxRetries: 3
    },
    
    // State management
    state: {
        sidebarOpen: false,
        currentTab: null,
        activeRequests: new Set()
    },
    
    // Utility functions
    utils: {
        /**
         * Debounce function to limit rapid function calls
         */
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },
        
        /**
         * Generate unique ID
         */
        generateId: function() {
            return 'id-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        },
        
        /**
         * Format timestamp for display
         */
        formatTimestamp: function(timestamp) {
            if (!timestamp) return 'Never';
            const date = new Date(timestamp);
            return date.toLocaleString();
        },
        
        /**
         * Show toast notification
         */
        showToast: function(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.textContent = message;
            
            // Add to page
            let container = document.querySelector('.toast-container');
            if (!container) {
                container = document.createElement('div');
                container.className = 'toast-container';
                document.body.appendChild(container);
            }
            
            container.appendChild(toast);
            
            // Auto remove after 5 seconds
            setTimeout(() => {
                toast.remove();
            }, 5000);
        },
        
        /**
         * Copy text to clipboard
         */
        copyToClipboard: function(text) {
            navigator.clipboard.writeText(text).then(() => {
                this.showToast('Copied to clipboard', 'success');
            }).catch(() => {
                this.showToast('Failed to copy to clipboard', 'error');
            });
        }
    },
    
    // UI components
    ui: {
        /**
         * Toggle sidebar on mobile
         */
        toggleSidebar: function() {
            const sidebar = document.querySelector('.app-sidebar');
            const isOpen = sidebar.classList.contains('open');
            
            if (isOpen) {
                sidebar.classList.remove('open');
                ThesisApp.state.sidebarOpen = false;
            } else {
                sidebar.classList.add('open');
                ThesisApp.state.sidebarOpen = true;
            }
        },
        
        /**
         * Close sidebar when clicking outside
         */
        setupSidebarClickOutside: function() {
            document.addEventListener('click', (e) => {
                const sidebar = document.querySelector('.app-sidebar');
                const toggleBtn = document.querySelector('.sidebar-toggle');
                
                if (ThesisApp.state.sidebarOpen && 
                    !sidebar.contains(e.target) && 
                    !toggleBtn.contains(e.target)) {
                    this.toggleSidebar();
                }
            });
        },
        
        /**
         * Setup search functionality
         */
        setupSearch: function() {
            const searchInput = document.querySelector('#search-input');
            if (!searchInput) return;
            
            const debouncedSearch = ThesisApp.utils.debounce((query) => {
                // HTMX will handle the actual search
                console.log('Searching for:', query);
            }, ThesisApp.config.debounceDelay);
            
            searchInput.addEventListener('input', (e) => {
                debouncedSearch(e.target.value);
            });
        },
        
        /**
         * Setup copy buttons
         */
        setupCopyButtons: function() {
            document.addEventListener('click', (e) => {
                if (e.target.matches('[data-copy]') || e.target.closest('[data-copy]')) {
                    const btn = e.target.matches('[data-copy]') ? e.target : e.target.closest('[data-copy]');
                    const textToCopy = btn.getAttribute('data-copy');
                    ThesisApp.utils.copyToClipboard(textToCopy);
                }
            });
        },
        
        /**
         * Setup modal functionality
         */
        setupModals: function() {
            // Close modals on overlay click
            document.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) {
                    e.target.remove();
                }
            });
            
            // Close modals on escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    const modal = document.querySelector('.modal-overlay');
                    if (modal) modal.remove();
                }
            });
        },
        
        /**
         * Setup tab functionality
         */
        setupTabs: function() {
            document.addEventListener('click', (e) => {
                if (e.target.matches('.tabs-nav a') || e.target.closest('.tabs-nav a')) {
                    e.preventDefault();
                    const link = e.target.matches('.tabs-nav a') ? e.target : e.target.closest('.tabs-nav a');
                    
                    // Remove active class from all tabs
                    document.querySelectorAll('.tabs-nav a').forEach(tab => {
                        tab.classList.remove('active');
                    });
                    
                    // Add active class to clicked tab
                    link.classList.add('active');
                    
                    // Update state
                    ThesisApp.state.currentTab = link.getAttribute('href');
                }
            });
        }
    },
    
    // HTMX event handlers
    htmx: {
        /**
         * Setup HTMX event listeners
         */
        setup: function() {
            // Before request - show loading state
            document.body.addEventListener('htmx:beforeRequest', (e) => {
                const requestId = ThesisApp.utils.generateId();
                e.detail.requestConfig.headers['X-Request-ID'] = requestId;
                ThesisApp.state.activeRequests.add(requestId);
                
                // Add loading class to trigger element
                if (e.detail.elt) {
                    e.detail.elt.classList.add('htmx-loading');
                }
            });
            
            // After request - hide loading state
            document.body.addEventListener('htmx:afterRequest', (e) => {
                const requestId = e.detail.xhr.getResponseHeader('X-Request-ID');
                if (requestId) {
                    ThesisApp.state.activeRequests.delete(requestId);
                }
                
                // Remove loading class
                if (e.detail.elt) {
                    e.detail.elt.classList.remove('htmx-loading');
                }
            });
            
            // Handle errors
            document.body.addEventListener('htmx:responseError', (e) => {
                console.error('HTMX Error:', e.detail);
                ThesisApp.utils.showToast('Request failed. Please try again.', 'error');
            });
            
            // Handle successful responses
            document.body.addEventListener('htmx:afterSwap', (e) => {
                // Re-initialize components in the new content
                ThesisApp.ui.setupCopyButtons();
                
                // Announce to screen readers
                const announcement = e.detail.target.getAttribute('data-announce');
                if (announcement) {
                    ThesisApp.accessibility.announce(announcement);
                }
            });
            
            // Handle history navigation
            document.body.addEventListener('htmx:historyRestore', (e) => {
                console.log('History restored:', e.detail);
            });
        }
    },
    
    // Accessibility helpers
    accessibility: {
        /**
         * Announce content to screen readers
         */
        announce: function(message) {
            const announcer = document.querySelector('#sr-announcer') || this.createAnnouncer();
            announcer.textContent = message;
        },
        
        /**
         * Create screen reader announcer element
         */
        createAnnouncer: function() {
            const announcer = document.createElement('div');
            announcer.id = 'sr-announcer';
            announcer.setAttribute('aria-live', 'polite');
            announcer.setAttribute('aria-atomic', 'true');
            announcer.className = 'sr-only';
            announcer.style.cssText = `
                position: absolute !important;
                left: -10000px !important;
                width: 1px !important;
                height: 1px !important;
                overflow: hidden !important;
            `;
            document.body.appendChild(announcer);
            return announcer;
        },
        
        /**
         * Setup keyboard navigation
         */
        setupKeyboardNav: function() {
            // Focus trap for modals
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    const modal = document.querySelector('.modal-overlay');
                    if (modal) {
                        this.trapFocus(e, modal);
                    }
                }
            });
        },
        
        /**
         * Trap focus within an element
         */
        trapFocus: function(e, container) {
            const focusableElements = container.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            
            if (focusableElements.length === 0) return;
            
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];
            
            if (e.shiftKey) {
                if (document.activeElement === firstElement) {
                    lastElement.focus();
                    e.preventDefault();
                }
            } else {
                if (document.activeElement === lastElement) {
                    firstElement.focus();
                    e.preventDefault();
                }
            }
        }
    },
    
    // Performance monitoring
    performance: {
        /**
         * Monitor HTMX request performance
         */
        monitor: function() {
            let requestStart = null;
            
            document.body.addEventListener('htmx:beforeRequest', (e) => {
                requestStart = performance.now();
            });
            
            document.body.addEventListener('htmx:afterRequest', (e) => {
                if (requestStart) {
                    const duration = performance.now() - requestStart;
                    console.log(`HTMX request took ${duration.toFixed(2)}ms`);
                    
                    // Log slow requests
                    if (duration > 1000) {
                        console.warn(`Slow HTMX request: ${duration.toFixed(2)}ms`);
                    }
                }
            });
        }
    },
    
    // Initialization
    init: function() {
        console.log('Initializing Thesis Research App...');
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
            return;
        }
        
        // Initialize components
        this.ui.setupSidebarClickOutside();
        this.ui.setupSearch();
        this.ui.setupCopyButtons();
        this.ui.setupModals();
        this.ui.setupTabs();
        this.htmx.setup();
        this.accessibility.setupKeyboardNav();
        
        // Performance monitoring in development
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            this.performance.monitor();
        }
        
        console.log('Thesis Research App initialized successfully');
    }
};

// Auto-initialize when script loads
ThesisApp.init();

// Expose utility functions globally for template use
window.showToast = ThesisApp.utils.showToast;
window.copyToClipboard = ThesisApp.utils.copyToClipboard;
window.formatTimestamp = ThesisApp.utils.formatTimestamp;
