/**
 * Frontend Configuration
 * Centralized configuration for frontend behavior and settings
 */

window.AppConfig = {
  // API Configuration
  api: {
    baseURL: '/api',
    timeout: 30000,
    retryAttempts: 3,
    retryDelay: 1000
  },

  // WebSocket Configuration
  websocket: {
    url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`,
    reconnectDelay: 1000,
    maxReconnectDelay: 30000,
    maxReconnectAttempts: 10
  },

  // UI Settings
  ui: {
    theme: 'auto', // 'light', 'dark', 'auto'
    sidebarCollapsed: false,
    tablePageSize: 25,
    animationDuration: 300,
    toastTimeout: 5000,
    debounceDelay: 300,
    throttleDelay: 100
  },

  // Feature Flags
  features: {
    darkMode: true,
    keyboardShortcuts: true,
    autoSave: true,
    realTimeUpdates: true,
    bulkOperations: true,
    exportFeatures: true,
    searchSuggestions: true,
    progressTracking: true
  },

  // Analysis Settings
  analysis: {
    autoRefreshInterval: 5000, // 5 seconds
    maxRetries: 5,
    timeoutMinutes: 30,
    supportedTypes: ['security', 'performance', 'dynamic', 'ai_powered'],
    batchSize: 10
  },

  // Table Configuration
  tables: {
    defaultPageSize: 25,
    pageSizeOptions: [10, 25, 50, 100],
    stickyHeaders: true,
    striped: true,
    sortable: true,
    filterable: true
  },

  // Form Configuration
  forms: {
    autoSave: true,
    autoSaveDelay: 2000,
    validateOnBlur: true,
    showInlineErrors: true
  },

  // Performance Settings
  performance: {
    lazyLoadThreshold: 100,
    virtualScrollThreshold: 1000,
    imageOptimization: true,
    cacheTimeout: 300000 // 5 minutes
  },

  // Keyboard Shortcuts
  shortcuts: {
    search: ['ctrl+k', 'cmd+k'],
    sidebar: ['ctrl+b', 'cmd+b'],
    theme: ['ctrl+shift+t', 'cmd+shift+t'],
    save: ['ctrl+s', 'cmd+s'],
    refresh: ['f5'],
    help: ['?']
  },

  // Export Settings
  export: {
    formats: ['json', 'csv', 'pdf'],
    compression: true,
    includeMetadata: true
  },

  // Error Handling
  errors: {
    showToasts: true,
    logToConsole: true,
    reportToServer: false,
    retryFailedRequests: true
  },

  // Development Settings
  development: {
    debug: false,
    verbose: false,
    showPerformanceMetrics: false,
    mockData: false
  }
};

// Environment-specific overrides
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  AppConfig.development.debug = true;
  AppConfig.development.verbose = true;
  AppConfig.development.showPerformanceMetrics = true;
}

// User preference overrides from localStorage (defensive if Utils.Storage not yet defined)
let savedSettings = {};
try {
  if (window.Utils && Utils.Storage && typeof Utils.Storage.get === 'function') {
    savedSettings = Utils.Storage.get('appSettings', {}) || {};
  } else {
    // Fallback to direct localStorage usage
    const raw = localStorage.getItem('appSettings');
    if (raw) {
      try { savedSettings = JSON.parse(raw) || {}; } catch(e) { /* ignore parse errors */ }
    }
  }
} catch(e) { /* swallow */ }
if (savedSettings.theme) {
  AppConfig.ui.theme = savedSettings.theme;
}
if (savedSettings.sidebarCollapsed !== undefined) {
  AppConfig.ui.sidebarCollapsed = savedSettings.sidebarCollapsed;
}
if (savedSettings.tablePageSize) {
  AppConfig.ui.tablePageSize = savedSettings.tablePageSize;
}

// Save settings helper
window.AppConfig.save = function() {
  Utils.Storage.set('appSettings', {
    theme: this.ui.theme,
    sidebarCollapsed: this.ui.sidebarCollapsed,
    tablePageSize: this.ui.tablePageSize
  });
};

// Configuration validation
window.AppConfig.validate = function() {
  const errors = [];

  // Validate required URLs
  if (!this.api.baseURL) {
    errors.push('API base URL is required');
  }

  // Validate timeout values
  if (this.api.timeout < 1000) {
    errors.push('API timeout must be at least 1000ms');
  }

  // Validate page sizes
  if (this.ui.tablePageSize < 5 || this.ui.tablePageSize > 200) {
    errors.push('Table page size must be between 5 and 200');
  }

  if (errors.length > 0) {
    console.error('Configuration validation errors:', errors);
    return false;
  }

  return true;
};

// Feature detection and capability checking
window.AppConfig.capabilities = {
  webSockets: typeof WebSocket !== 'undefined',
  localStorage: typeof Storage !== 'undefined',
  fetch: typeof fetch !== 'undefined',
  intersectionObserver: typeof IntersectionObserver !== 'undefined',
  resizeObserver: typeof ResizeObserver !== 'undefined',
  mutationObserver: typeof MutationObserver !== 'undefined',
  serviceWorker: 'serviceWorker' in navigator,
  pushNotifications: 'PushManager' in window,
  clipboard: navigator.clipboard !== undefined,
  geolocation: 'geolocation' in navigator
};

// Browser-specific adjustments
const userAgent = navigator.userAgent.toLowerCase();
if (userAgent.includes('safari') && !userAgent.includes('chrome')) {
  // Safari-specific adjustments
  AppConfig.ui.animationDuration = 200; // Shorter animations for Safari
}

if (userAgent.includes('firefox')) {
  // Firefox-specific adjustments
  AppConfig.performance.virtualScrollThreshold = 500; // Lower threshold for Firefox
}

// Mobile device detection and adjustments
const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
if (isMobile) {
  AppConfig.ui.tablePageSize = 10; // Smaller page size for mobile
  AppConfig.ui.sidebarCollapsed = true; // Start with collapsed sidebar
  AppConfig.ui.animationDuration = 200; // Faster animations
  AppConfig.performance.lazyLoadThreshold = 50; // Earlier lazy loading
}

// Validate configuration on load
if (!AppConfig.validate()) {
  console.warn('Configuration validation failed, using defaults');
}

// Expose configuration change event
AppConfig.onChange = function(callback) {
  document.addEventListener('configChange', callback);
};

AppConfig.trigger = function(property, oldValue, newValue) {
  document.dispatchEvent(new CustomEvent('configChange', {
    detail: { property, oldValue, newValue }
  }));
};

console.log('⚙️ Configuration loaded successfully');