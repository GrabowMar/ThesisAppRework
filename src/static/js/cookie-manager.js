/**
 * Cookie & Data Storage Manager
 * Manages user consent for cookies and local storage usage
 *
 * Storage Categories:
 * - essential: Required for core functionality (always enabled)
 * - analytics: Performance monitoring and usage analytics
 * - functional: UI preferences and personalization
 * - ai: AI processing history and caching
 */

(function() {
  'use strict';

  const CONSENT_KEY = 'cookie_consent';
  const CONSENT_VERSION = '1.0';

  class CookieManager {
    constructor() {
      this.consent = this.loadConsent();
      this.initEventListeners();
      this.checkConsentStatus();
    }

    /**
     * Load consent from localStorage
     */
    loadConsent() {
      try {
        const stored = localStorage.getItem(CONSENT_KEY);
        if (stored) {
          const consent = JSON.parse(stored);
          // Check if consent is still valid (same version)
          if (consent.version === CONSENT_VERSION) {
            return consent;
          }
        }
      } catch (e) {
        console.warn('Failed to load cookie consent:', e);
      }
      return null;
    }

    /**
     * Save consent to localStorage
     */
    saveConsent(preferences) {
      const consent = {
        version: CONSENT_VERSION,
        timestamp: new Date().toISOString(),
        preferences: {
          essential: true, // Always true
          analytics: preferences.analytics || false,
          functional: preferences.functional || false,
          ai: preferences.ai || false
        }
      };

      try {
        localStorage.setItem(CONSENT_KEY, JSON.stringify(consent));
        this.consent = consent;
        this.applyConsent();
        this.hideBanner();
        this.showFloatButton();

        // Fire custom event
        document.dispatchEvent(new CustomEvent('cookieConsentUpdated', {
          detail: consent.preferences
        }));

        return true;
      } catch (e) {
        console.error('Failed to save cookie consent:', e);
        return false;
      }
    }

    /**
     * Check if user has given consent
     */
    hasConsent() {
      return this.consent !== null;
    }

    /**
     * Check if specific category is allowed
     */
    isAllowed(category) {
      if (category === 'essential') return true;
      if (!this.consent) return false;
      return this.consent.preferences[category] === true;
    }

    /**
     * Show or hide banner based on consent status
     */
    checkConsentStatus() {
      if (!this.hasConsent()) {
        this.showBanner();
      } else {
        this.showFloatButton();
        this.applyConsent();
      }
    }

    /**
     * Show cookie banner
     */
    showBanner() {
      const banner = document.getElementById('cookie-banner');
      if (banner) {
        // Small delay for animation
        setTimeout(() => {
          banner.classList.add('show');
        }, 500);
      }
    }

    /**
     * Hide cookie banner
     */
    hideBanner() {
      const banner = document.getElementById('cookie-banner');
      if (banner) {
        banner.classList.remove('show');
      }
    }

    /**
     * Show floating settings button - removed
     */
    showFloatButton() {
      // Floating button removed
    }

    /**
     * Open settings modal
     */
    openSettings() {
      const modal = document.getElementById('cookie-settings-modal');
      if (modal) {
        // Load current preferences
        if (this.consent) {
          const prefs = this.consent.preferences;
          document.getElementById('cookie-analytics').checked = prefs.analytics || false;
          document.getElementById('cookie-functional').checked = prefs.functional || false;
          document.getElementById('cookie-ai').checked = prefs.ai || false;
        }

        // Show modal using Bootstrap
        const bsModal = bootstrap.Modal.getInstance(modal) || new bootstrap.Modal(modal);
        bsModal.show();
      }
    }

    /**
     * Save settings from modal
     */
    saveSettings() {
      const preferences = {
        analytics: document.getElementById('cookie-analytics').checked,
        functional: document.getElementById('cookie-functional').checked,
        ai: document.getElementById('cookie-ai').checked
      };

      if (this.saveConsent(preferences)) {
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('cookie-settings-modal'));
        if (modal) {
          modal.hide();
        }

        // Show success message
        if (window.showToast) {
          window.showToast('Cookie preferences saved successfully', 'success');
        }
      }
    }

    /**
     * Accept all cookies
     */
    acceptAll() {
      this.saveConsent({
        analytics: true,
        functional: true,
        ai: true
      });

      if (window.showToast) {
        window.showToast('All cookies accepted', 'success');
      }
    }

    /**
     * Reject optional cookies (keep only essential)
     */
    rejectOptional() {
      this.saveConsent({
        analytics: false,
        functional: false,
        ai: false
      });

      if (window.showToast) {
        window.showToast('Optional cookies rejected', 'info');
      }
    }

    /**
     * Apply consent - clean up data for disabled categories
     */
    applyConsent() {
      if (!this.consent) return;

      const prefs = this.consent.preferences;

      // Clean up localStorage based on preferences
      if (!prefs.analytics) {
        this.clearAnalyticsData();
      }

      if (!prefs.functional) {
        this.clearFunctionalData();
      }

      if (!prefs.ai) {
        this.clearAIData();
      }
    }

    /**
     * Clear analytics data
     */
    clearAnalyticsData() {
      const analyticsKeys = ['page_views', 'feature_usage', 'performance_metrics'];
      analyticsKeys.forEach(key => {
        try {
          localStorage.removeItem(key);
        } catch (e) {}
      });
    }

    /**
     * Clear functional data
     */
    clearFunctionalData() {
      const functionalKeys = ['table_preferences', 'filter_settings', 'ui_state'];
      functionalKeys.forEach(key => {
        try {
          localStorage.removeItem(key);
        } catch (e) {}
      });
    }

    /**
     * Clear AI data
     */
    clearAIData() {
      const aiKeys = ['analysis_cache', 'model_preferences', 'prompt_history'];
      aiKeys.forEach(key => {
        try {
          localStorage.removeItem(key);
        } catch (e) {}
      });
    }

    /**
     * Initialize event listeners
     */
    initEventListeners() {
      // Wait for DOM to be ready
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => this.attachListeners());
      } else {
        this.attachListeners();
      }
    }

    /**
     * Attach event listeners to buttons
     */
    attachListeners() {
      // Accept all button
      const acceptBtn = document.getElementById('cookie-accept-all');
      if (acceptBtn) {
        acceptBtn.addEventListener('click', () => this.acceptAll());
      }

      // Reject optional button
      const rejectBtn = document.getElementById('cookie-reject-optional');
      if (rejectBtn) {
        rejectBtn.addEventListener('click', () => this.rejectOptional());
      }

      // Settings button in banner
      const settingsBtn = document.getElementById('cookie-settings-btn');
      if (settingsBtn) {
        settingsBtn.addEventListener('click', () => this.openSettings());
      }

      // Floating settings button removed

      // Save settings button in modal
      const saveBtn = document.getElementById('cookie-save-settings');
      if (saveBtn) {
        saveBtn.addEventListener('click', () => this.saveSettings());
      }
    }

    /**
     * Get current consent preferences
     */
    getPreferences() {
      if (!this.consent) {
        return {
          essential: true,
          analytics: false,
          functional: false,
          ai: false
        };
      }
      return this.consent.preferences;
    }
  }

  // Initialize cookie manager
  const cookieManager = new CookieManager();

  // Expose to window for global access
  window.cookieManager = cookieManager;

  // Helper function to check if storage is allowed
  window.canUseStorage = function(category) {
    return cookieManager.isAllowed(category);
  };

  // Safe localStorage wrapper
  window.safeLocalStorage = {
    setItem: function(key, value, category) {
      category = category || 'functional';
      if (cookieManager.isAllowed(category)) {
        try {
          localStorage.setItem(key, value);
          return true;
        } catch (e) {
          console.warn('localStorage.setItem failed:', e);
          return false;
        }
      }
      return false;
    },

    getItem: function(key, category) {
      category = category || 'functional';
      if (cookieManager.isAllowed(category)) {
        try {
          return localStorage.getItem(key);
        } catch (e) {
          console.warn('localStorage.getItem failed:', e);
          return null;
        }
      }
      return null;
    },

    removeItem: function(key) {
      try {
        localStorage.removeItem(key);
        return true;
      } catch (e) {
        console.warn('localStorage.removeItem failed:', e);
        return false;
      }
    }
  };

})();
