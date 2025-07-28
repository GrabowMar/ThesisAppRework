/**
 * Thesis Research App - JavaScript
 * HTMX-powered interactions and utilities
 */

// ==========================================
// INITIALIZATION
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Thesis Research App initialized');
    
    // Initialize components
    initializeDropdowns();
    initializeToasts();
    initializeModals();
    initializeSearch();
    
    // Set up periodic updates
    setupPeriodicUpdates();
    
    // Initialize keyboard shortcuts
    initializeKeyboardShortcuts();
});

// ==========================================
// DROPDOWN FUNCTIONALITY
// ==========================================

function initializeDropdowns() {
    document.addEventListener('click', function(e) {
        // Close all dropdowns when clicking outside
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown.active').forEach(dropdown => {
                dropdown.classList.remove('active');
            });
        }
        
        // Toggle dropdown when clicking trigger
        const dropdownToggle = e.target.closest('[data-dropdown-toggle], [data-dropdown]');
        if (dropdownToggle) {
            e.preventDefault();
            const dropdown = dropdownToggle.closest('.dropdown');
            const isActive = dropdown.classList.contains('active');
            
            // Close all other dropdowns
            document.querySelectorAll('.dropdown.active').forEach(d => {
                if (d !== dropdown) d.classList.remove('active');
            });
            
            // Toggle current dropdown
            dropdown.classList.toggle('active', !isActive);
        }
    });
}

// ==========================================
// TOAST NOTIFICATIONS
// ==========================================

function initializeToasts() {
    // Create toast container if it doesn't exist
    if (!document.getElementById('toast-container')) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
}

function showToast(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
        </div>
        <button class="toast-close" onclick="removeToast(this.parentElement)">×</button>
    `;
    
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => removeToast(toast), duration);
    }
    
    return toast;
}

function removeToast(toast) {
    toast.classList.add('hiding');
    setTimeout(() => {
        if (toast.parentElement) {
            toast.parentElement.removeChild(toast);
        }
    }, 300);
}

// ==========================================
// MODAL FUNCTIONALITY
// ==========================================

function initializeModals() {
    // Close modal when clicking backdrop
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-backdrop')) {
            closeModal();
        }
    });
    
    // Close modal with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
}

function openModal(content) {
    const container = document.getElementById('modal-container');
    container.innerHTML = `
        <div class="modal-backdrop">
            <div class="modal-content">
                ${content}
            </div>
        </div>
    `;
    container.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    const container = document.getElementById('modal-container');
    container.innerHTML = '';
    container.style.display = 'none';
    document.body.style.overflow = '';
}

// ==========================================
// SEARCH FUNCTIONALITY
// ==========================================

function initializeSearch() {
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        // Add search shortcuts
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                this.value = '';
                this.blur();
                htmx.trigger('#app-list', 'load');
            }
        });
        
        // Focus search with Ctrl+K or Cmd+K
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        });
    }
}

// ==========================================
// PERIODIC UPDATES
// ==========================================

function setupPeriodicUpdates() {
    // Update container statuses every 30 seconds
    setInterval(() => {
        const statusElements = document.querySelectorAll('[hx-trigger*="every"]');
        statusElements.forEach(element => {
            if (element.offsetParent !== null) { // Only if visible
                htmx.trigger(element, 'load');
            }
        });
    }, 30000);
    
    // Update dashboard stats every 2 minutes
    setInterval(() => {
        const dashboardStats = document.getElementById('stats-container');
        if (dashboardStats) {
            htmx.trigger(dashboardStats.parentElement, 'load');
        }
    }, 120000);
}

// ==========================================
// KEYBOARD SHORTCUTS
// ==========================================

function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Only handle shortcuts when not in input fields
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        const shortcuts = {
            // Navigation
            'd': () => window.location.href = '/dashboard',
            'a': () => window.location.href = '/analysis',
            'p': () => window.location.href = '/performance',
            's': () => window.location.href = '/zap',
            'b': () => window.location.href = '/batch',
            
            // Actions
            'r': () => window.location.reload(),
            'h': () => toggleSidebar(),
            '?': () => showKeyboardShortcuts()
        };
        
        if (shortcuts[e.key.toLowerCase()]) {
            e.preventDefault();
            shortcuts[e.key.toLowerCase()]();
        }
    });
}

function toggleSidebar() {
    const sidebar = document.querySelector('.app-sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

function showKeyboardShortcuts() {
    const shortcuts = `
        <div class="keyboard-shortcuts">
            <h3>🔧 Keyboard Shortcuts</h3>
            <div class="shortcuts-grid">
                <div class="shortcut-group">
                    <h4>Navigation</h4>
                    <div class="shortcut-item"><kbd>D</kbd> Dashboard</div>
                    <div class="shortcut-item"><kbd>A</kbd> Analysis</div>
                    <div class="shortcut-item"><kbd>P</kbd> Performance</div>
                    <div class="shortcut-item"><kbd>S</kbd> Security</div>
                    <div class="shortcut-item"><kbd>B</kbd> Batch</div>
                </div>
                <div class="shortcut-group">
                    <h4>Search & Actions</h4>
                    <div class="shortcut-item"><kbd>Ctrl+K</kbd> Search</div>
                    <div class="shortcut-item"><kbd>R</kbd> Refresh</div>
                    <div class="shortcut-item"><kbd>H</kbd> Toggle Sidebar</div>
                    <div class="shortcut-item"><kbd>Esc</kbd> Close Modal</div>
                    <div class="shortcut-item"><kbd>?</kbd> Show Shortcuts</div>
                </div>
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal()">Close</button>
            </div>
        </div>
    `;
    openModal(shortcuts);
}

// ==========================================
// HTMX EVENT HANDLERS
// ==========================================

// Global HTMX configuration
document.addEventListener('htmx:configRequest', function(evt) {
    // Add CSRF token to all requests
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (csrfToken) {
        evt.detail.headers['X-CSRFToken'] = csrfToken.getAttribute('content');
    }
});

// Handle successful responses
document.addEventListener('htmx:afterSwap', function(evt) {
    // Re-initialize components in new content
    initializeDropdowns();
    
    // Show success message for certain operations
    const target = evt.detail.target;
    if (target.hasAttribute('data-success-message')) {
        showToast(target.getAttribute('data-success-message'), 'success');
    }
    
    // Auto-focus first input in new content
    const firstInput = target.querySelector('input:not([type="hidden"]), textarea, select');
    if (firstInput && target.hasAttribute('data-auto-focus')) {
        setTimeout(() => firstInput.focus(), 100);
    }
});

// Handle errors
document.addEventListener('htmx:responseError', function(evt) {
    console.error('HTMX Request failed:', evt.detail);
    showToast('Request failed. Please try again.', 'error');
});

document.addEventListener('htmx:sendError', function(evt) {
    console.error('HTMX Send error:', evt.detail);
    showToast('Network error. Please check your connection.', 'error');
});

// Handle timeout
document.addEventListener('htmx:timeout', function(evt) {
    console.warn('HTMX Request timeout:', evt.detail);
    showToast('Request timed out. Please try again.', 'warning');
});

// Handle loading states
document.addEventListener('htmx:beforeRequest', function(evt) {
    const trigger = evt.detail.elt;
    if (trigger.hasAttribute('data-loading-text')) {
        trigger.setAttribute('data-original-text', trigger.textContent);
        trigger.textContent = trigger.getAttribute('data-loading-text');
        trigger.disabled = true;
    }
});

document.addEventListener('htmx:afterRequest', function(evt) {
    const trigger = evt.detail.elt;
    if (trigger.hasAttribute('data-original-text')) {
        trigger.textContent = trigger.getAttribute('data-original-text');
        trigger.disabled = false;
        trigger.removeAttribute('data-original-text');
    }
});

// ==========================================
// UTILITY FUNCTIONS
// ==========================================

function formatDateTime(timestamp) {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDuration(seconds) {
    if (!seconds || seconds < 0) return 'N/A';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copied to clipboard', 'success', 2000);
        }).catch(() => {
            fallbackCopyToClipboard(text);
        });
    } else {
        fallbackCopyToClipboard(text);
    }
}

function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showToast('Copied to clipboard', 'success', 2000);
    } catch (err) {
        showToast('Failed to copy to clipboard', 'error');
    }
    
    document.body.removeChild(textArea);
}

// ==========================================
// EXPORT FUNCTIONS FOR GLOBAL USE
// ==========================================

window.ThesisApp = {
    showToast,
    removeToast,
    openModal,
    closeModal,
    toggleSidebar,
    showKeyboardShortcuts,
    formatDateTime,
    formatDuration,
    copyToClipboard
};

// Log successful initialization
console.log('✅ Thesis Research App JavaScript loaded successfully');
