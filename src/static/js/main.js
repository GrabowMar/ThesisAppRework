/**
 * Main Project JavaScript
 * Enhanced frontend functionality for AI Model Analysis Platform
 * Safe to load on all pages - features initialize only when needed
 */

class AppCore {
  constructor() {
    this.theme = localStorage.getItem('theme') || 'light';
    this.sidebarCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    this.init();
  }

  init() {
    this.initHTMX();
    this.initTheme();
    this.initSidebar();
    this.initTooltips();
    this.initKeyboardShortcuts();
    this.initScrollBehavior();
    this.initFormEnhancements();
    console.log('🚀 App initialized successfully');
  }

  // HTMX Configuration & Error Handling
  initHTMX() {
    if (!window.htmx) return;

    // Global HTMX configuration
    htmx.config.globalViewTransitions = true;
    htmx.config.scrollBehavior = 'smooth';

    // Enhanced error handling
    document.body.addEventListener('htmx:responseError', (evt) => {
      console.error('HTMX Response Error:', evt.detail);
      this.showToast('Network error occurred', 'error');
    });

    // Loading indicators
    document.body.addEventListener('htmx:beforeRequest', (evt) => {
      const target = evt.target;
      target.style.opacity = '0.7';
      target.style.pointerEvents = 'none';
    });

    document.body.addEventListener('htmx:afterRequest', (evt) => {
      const target = evt.target;
      target.style.opacity = '';
      target.style.pointerEvents = '';
    });

    // Auto-focus first input in swapped content
    document.body.addEventListener('htmx:afterSwap', () => {
      const firstInput = document.querySelector('input:not([type="hidden"]):not([readonly])');
      if (firstInput) firstInput.focus();
    });
  }

  // Theme Management
  initTheme() {
    this.applyTheme(this.theme);
    
    // Theme toggle handler
    document.addEventListener('click', (e) => {
      if (e.target.matches('[data-theme-toggle]')) {
        e.preventDefault();
        this.toggleTheme();
      }
    });

    // Auto theme detection
    if (this.theme === 'auto') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      mediaQuery.addEventListener('change', () => this.applyTheme('auto'));
    }
  }

  toggleTheme() {
    const themes = ['light', 'dark', 'auto'];
    const currentIndex = themes.indexOf(this.theme);
    this.theme = themes[(currentIndex + 1) % themes.length];
    this.applyTheme(this.theme);
    localStorage.setItem('theme', this.theme);
    this.showToast(`Theme switched to ${this.theme}`, 'success');
  }

  applyTheme(theme) {
    const root = document.documentElement;
    const effectiveTheme = theme === 'auto' 
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme;
    
    root.setAttribute('data-theme', theme);
    root.setAttribute('data-bs-theme', effectiveTheme);
  }

  // Sidebar Management
  initSidebar() {
    if (this.sidebarCollapsed) {
      document.body.classList.add('sidebar-collapsed');
    }

    // Sidebar toggle handler
    document.addEventListener('click', (e) => {
      if (e.target.matches('[data-sidebar-toggle]') || e.target.closest('[data-sidebar-toggle]')) {
        e.preventDefault();
        this.toggleSidebar();
      }
    });

    // Auto-collapse on mobile
    this.handleSidebarResponsive();
    window.addEventListener('resize', () => this.handleSidebarResponsive());
  }

  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
    document.body.classList.toggle('sidebar-collapsed', this.sidebarCollapsed);
    localStorage.setItem('sidebar-collapsed', this.sidebarCollapsed);
    
    // Dispatch custom event for components that need to react
    document.dispatchEvent(new CustomEvent('sidebar:toggle', { 
      detail: { collapsed: this.sidebarCollapsed } 
    }));
  }

  handleSidebarResponsive() {
    const isMobile = window.innerWidth < 992;
    if (isMobile) {
      document.body.classList.add('sidebar-collapsed');
    } else if (!this.sidebarCollapsed) {
      document.body.classList.remove('sidebar-collapsed');
    }
  }

  // Tooltip Initialization
  initTooltips() {
    if (typeof bootstrap !== 'undefined') {
      // Initialize Bootstrap tooltips
      const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
      tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

      // Auto-tooltips for truncated text
      document.querySelectorAll('[data-auto-tooltip]').forEach(el => {
        if (el.scrollWidth > el.clientWidth) {
          el.setAttribute('data-bs-toggle', 'tooltip');
          el.setAttribute('title', el.textContent.trim());
          new bootstrap.Tooltip(el);
        }
      });
    }
  }

  // Keyboard Shortcuts
  initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Ctrl/Cmd + K: Focus search
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('input[type="search"], input[placeholder*="search" i]');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }

      // Ctrl/Cmd + B: Toggle sidebar
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault();
        this.toggleSidebar();
      }

      // Ctrl/Cmd + Shift + T: Toggle theme
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'T') {
        e.preventDefault();
        this.toggleTheme();
      }

      // Escape: Close modals, dropdowns, etc.
      if (e.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal && typeof bootstrap !== 'undefined') {
          bootstrap.Modal.getInstance(openModal)?.hide();
        }
      }
    });
  }

  // Smooth Scroll Behavior
  initScrollBehavior() {
    // Scroll to top functionality
    const scrollTopBtn = document.querySelector('[data-scroll-top]');
    if (scrollTopBtn) {
      window.addEventListener('scroll', () => {
        scrollTopBtn.style.opacity = window.scrollY > 300 ? '1' : '0';
      });

      scrollTopBtn.addEventListener('click', (e) => {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }

    // Smooth anchor scrolling
    document.addEventListener('click', (e) => {
      const anchor = e.target.closest('a[href^="#"]');
      if (anchor && anchor.getAttribute('href') !== '#') {
        const target = document.querySelector(anchor.getAttribute('href'));
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  }

  // Form Enhancements
  initFormEnhancements() {
    // Auto-save form data
    document.addEventListener('input', (e) => {
      if (e.target.matches('[data-auto-save]')) {
        const key = `form-${e.target.name || e.target.id}`;
        localStorage.setItem(key, e.target.value);
      }
    });

    // Restore saved form data
    document.querySelectorAll('[data-auto-save]').forEach(input => {
      const key = `form-${input.name || input.id}`;
      const saved = localStorage.getItem(key);
      if (saved && !input.value) {
        input.value = saved;
      }
    });

    // Form validation feedback
    document.addEventListener('invalid', (e) => {
      e.target.classList.add('is-invalid');
    }, true);

    document.addEventListener('input', (e) => {
      if (e.target.classList.contains('is-invalid') && e.target.checkValidity()) {
        e.target.classList.remove('is-invalid');
        e.target.classList.add('is-valid');
      }
    });
  }

  // Utility Methods
  showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    `;

    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container position-fixed top-0 end-0 p-3';
      document.body.appendChild(container);
    }

    container.appendChild(toast);

    if (typeof bootstrap !== 'undefined') {
      const bsToast = new bootstrap.Toast(toast, { delay: duration });
      bsToast.show();
      toast.addEventListener('hidden.bs.toast', () => toast.remove());
    } else {
      setTimeout(() => toast.remove(), duration);
    }
  }

  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // API Helpers
  async fetchJSON(url, options = {}) {
    try {
      const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Fetch error:', error);
      this.showToast('Network request failed', 'error');
      throw error;
    }
  }
}

// Global utilities
window.App = {
  // Expose common utilities globally
  showToast: (message, type, duration) => window.appCore?.showToast(message, type, duration),
  toggleTheme: () => window.appCore?.toggleTheme(),
  toggleSidebar: () => window.appCore?.toggleSidebar(),
  
  // Common UI patterns
  confirmAction: (message) => confirm(message),
  
  // Copy to clipboard helper
  copyToClipboard: async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      window.App.showToast('Copied to clipboard!', 'success');
      return true;
    } catch (err) {
      console.error('Copy failed:', err);
      return false;
    }
  },

  // Format utilities
  formatBytes: (bytes, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
  },

  formatNumber: (num) => new Intl.NumberFormat().format(num)
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.appCore = new AppCore();
  });
} else {
  window.appCore = new AppCore();
}
