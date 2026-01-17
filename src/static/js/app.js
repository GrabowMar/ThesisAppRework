// Lean application JS for ThesisAppRework
// Goal: minimise bespoke JS now that htmx + hyperscript + Tabler/Bootstrap handle
// most dynamic behaviour. Keep public API surface for templates while internally
// delegating to simple, small helpers. (Safe to remove more after template audit.)

window.ThesisApp = window.ThesisApp || {};

// ============================================================================
// Page Initialization Utilities - Handle HTMX Navigation
// ============================================================================
// Use these helpers to ensure page scripts run on both initial load AND
// after HTMX navigation (hx-boost). Scripts using only DOMContentLoaded will
// NOT run after HTMX swaps content.
// ============================================================================

/**
 * Register a page initialization function that runs on:
 * - Initial page load (DOMContentLoaded)
 * - HTMX navigation (thesis:pageInit event)
 * - Browser back/forward (htmx:historyRestore)
 * 
 * @param {Function} initFn - Initialization function to call
 * @param {Object} options - Optional configuration
 * @param {string} options.pageId - Only run if page contains element with this ID
 * @param {string} options.selector - Only run if page contains elements matching this selector
 * 
 * @example
 * // Always run on any page
 * ThesisApp.onPageReady(function() {
 *   console.log('Page loaded or navigated');
 * });
 * 
 * @example
 * // Only run on pages with #analysis-wizard element
 * ThesisApp.onPageReady(initAnalysisWizard, { pageId: 'analysis-wizard' });
 * 
 * @example
 * // Only run on pages with .models-table
 * ThesisApp.onPageReady(initModelsTable, { selector: '.models-table' });
 */
ThesisApp.onPageReady = function(initFn, options) {
  options = options || {};
  
  function shouldRun() {
    if (options.pageId && !document.getElementById(options.pageId)) return false;
    if (options.selector && !document.querySelector(options.selector)) return false;
    return true;
  }
  
  function safeRun() {
    if (shouldRun()) {
      try {
        initFn();
      } catch (e) {
        console.error('[ThesisApp] Page init error:', e);
      }
    }
  }
  
  // Run on initial load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', safeRun);
  } else {
    safeRun();
  }
  
  // Run on HTMX navigation
  document.addEventListener('thesis:pageInit', safeRun);
};

/**
 * One-time initialization that only runs once per page visit.
 * Useful for event listeners that shouldn't be added multiple times.
 * 
 * @param {string} key - Unique identifier for this initialization
 * @param {Function} initFn - Initialization function
 */
ThesisApp.initOnce = function(key, initFn) {
  var initKey = '_thesis_init_' + key;
  if (window[initKey]) return;
  window[initKey] = true;
  
  try {
    initFn();
  } catch (e) {
    console.error('[ThesisApp] initOnce error for ' + key + ':', e);
    window[initKey] = false;
  }
};

/**
 * Reset one-time initialization flags (called on HTMX navigation)
 * This allows initOnce to run again on new pages
 */
ThesisApp.resetInitFlags = function() {
  Object.keys(window).forEach(function(key) {
    if (key.startsWith('_thesis_init_')) {
      delete window[key];
    }
  });
};

// Reset init flags on navigation so page-specific inits can run again
document.addEventListener('thesis:pageInit', function() {
  ThesisApp.resetInitFlags();
});

// ============================================================================

// ============================================================================
// HTMX Modal Utilities - Proper Bootstrap Modal Management
// ============================================================================
// Use these helpers for HTMX-loaded modals to ensure proper backdrop cleanup.
// DO NOT manually create/manage backdrops - Bootstrap handles this automatically.
// ============================================================================

/**
 * Initialize an HTMX-loaded modal with proper Bootstrap cleanup.
 * This ensures the modal backdrop is removed on ANY close method:
 * - Clicking the X button
 * - Clicking outside the modal (backdrop)
 * - Pressing Escape key
 * - Programmatic close via bsModal.hide()
 *
 * @param {string|HTMLElement} modalOrId - Modal element or its ID
 * @param {Object} options - Bootstrap Modal options (optional)
 * @returns {bootstrap.Modal} Bootstrap Modal instance
 *
 * @example
 * // In your HTMX-loaded modal template script:
 * const bsModal = ThesisApp.initHtmxModal('my-modal-id');
 * // Modal is automatically shown and will clean up on close
 *
 * @example
 * // With custom options:
 * const bsModal = ThesisApp.initHtmxModal(document.getElementById('my-modal'), {
 *   keyboard: false,  // Disable Escape key close
 *   backdrop: 'static'  // Don't close on backdrop click
 * });
 */
ThesisApp.initHtmxModal = function(modalOrId, options) {
  const modal = typeof modalOrId === 'string'
    ? document.getElementById(modalOrId)
    : modalOrId;
  
  if (!modal) {
    console.error('[ThesisApp] initHtmxModal: Modal not found:', modalOrId);
    return null;
  }
  
  // Remove any existing style="display:block" that might interfere
  modal.style.removeProperty('display');
  
  // Initialize Bootstrap Modal with options
  const defaultOptions = { focus: true };
  const bsModal = new bootstrap.Modal(modal, { ...defaultOptions, ...options });
  
  // Show the modal
  bsModal.show();
  
  // Single cleanup handler for ALL close methods (backdrop click, Escape, buttons)
  modal.addEventListener('hidden.bs.modal', function cleanupModal() {
    bsModal.dispose();
    modal.remove();
    // Also clean up any orphan backdrops (defensive, shouldn't be needed)
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
  }, { once: true });
  
  return bsModal;
};

/**
 * Close and cleanup a dynamically created modal.
 * Use this for programmatic close when you have the Bootstrap Modal instance.
 *
 * @param {bootstrap.Modal} bsModal - Bootstrap Modal instance
 */
ThesisApp.closeModal = function(bsModal) {
  if (bsModal && typeof bsModal.hide === 'function') {
    bsModal.hide();
    // hidden.bs.modal event will handle cleanup
  }
};

/**
 * Emergency cleanup for orphan modal backdrops.
 * Call this if a modal was improperly closed and left a backdrop behind.
 * Should rarely be needed if using initHtmxModal() properly.
 */
ThesisApp.cleanupOrphanBackdrops = function() {
  document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
  document.body.classList.remove('modal-open');
  document.body.style.removeProperty('overflow');
  document.body.style.removeProperty('padding-right');
};

// ============================================================================

// Chart helper kept as a light progressive enhancement; returns null if missing
ThesisApp.initDashboardChart = function(ctx){
  if(!ctx || !window.Chart) return null;
  try { return new Chart(ctx, { type:'line', data:{labels:[],datasets:[]}, options:{responsive:true,maintainAspectRatio:false}}); }
  catch(e){ console.warn('Chart init failed', e); return null; }
};

// 4. Progress meter helper shared across dashboard tables
(function(){
  function clampProgress(val){
    var num = parseFloat(val);
    if(!isFinite(num)) return 0;
    return Math.min(100, Math.max(0, num));
  }

  function setAriaAttributes(el, value){
    el.setAttribute('role', 'progressbar');
    el.setAttribute('aria-valuemin', '0');
    el.setAttribute('aria-valuemax', '100');
    el.setAttribute('aria-valuenow', value.toFixed ? value.toFixed(0) : value);
  }

  function updateProgressBars(root){
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('.progress[data-progress]').forEach(function(progressEl){
      var value = clampProgress(progressEl.getAttribute('data-progress'));
      var bar = progressEl.querySelector('.progress-bar');
      if(bar){
        bar.style.width = value + '%';
        bar.setAttribute('aria-valuenow', value.toFixed(0));
        bar.setAttribute('aria-valuemin', '0');
        bar.setAttribute('aria-valuemax', '100');
        bar.textContent = value >= 45 ? value.toFixed(0) + '%' : '';
      }
      setAriaAttributes(progressEl, value);
    });
  }

  ThesisApp.refreshProgressBars = updateProgressBars;

  function onReady(fn){
    if(document.readyState === 'loading'){
      document.addEventListener('DOMContentLoaded', function handler(){
        document.removeEventListener('DOMContentLoaded', handler);
        fn();
      });
    } else {
      fn();
    }
  }

  onReady(function(){ updateProgressBars(document); });

  document.addEventListener('htmx:afterSwap', function(evt){
    if(evt && evt.target){ updateProgressBars(evt.target); }
  });
  document.addEventListener('htmx:afterSettle', function(evt){
    if(evt && evt.target){ updateProgressBars(evt.target); }
  });
  document.addEventListener('htmx:historyRestore', function(evt){
    updateProgressBars(document);
  });
  document.addEventListener('thesis:refresh-progress', function(evt){
    updateProgressBars(evt && evt.detail && evt.detail.root ? evt.detail.root : document);
  });
})();
