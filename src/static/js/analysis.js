// Analysis tasks management - HTMX-driven filters and pagination
(function() {
  'use strict';
  
  // Local scope timeout variable for debouncing
  let filterTimeout;

  function debounceAnalysisFilters() {
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(applyAnalysisFilters, 300);
  }

  function applyAnalysisFilters(extra = {}) {
    const params = new URLSearchParams();
    
    // Get filter values
    const modelFilter = document.getElementById('analysis-model-filter')?.value;
    const appFilter = document.getElementById('analysis-app-filter')?.value;
    const statusFilter = document.getElementById('analysis-status-filter')?.value;
    const perPageSelect = document.getElementById('analysis-per-page');
    const perPageValue = extra.per_page || perPageSelect?.value;
    
    // Build params
    if (modelFilter) params.set('model', modelFilter);
    if (appFilter) params.set('app', appFilter);
    if (statusFilter) params.set('status', statusFilter);
    if (perPageValue) params.set('per_page', perPageValue);
    if (extra.page) params.set('page', extra.page);

    // Trigger HTMX reload with filters
    htmx.ajax('GET', `/analysis/api/tasks/list?${params.toString()}`, {
      target: '#main-tasks-table-wrapper',
      swap: 'innerHTML'
    });
  }

  function refreshAnalysisTasks() {
    // Preserve current filters when refreshing
    applyAnalysisFilters();
  }

  function clearAnalysisFilters() {
    // Clear all filter inputs
    const modelInput = document.getElementById('analysis-model-filter');
    const appInput = document.getElementById('analysis-app-filter');
    const statusSelect = document.getElementById('analysis-status-filter');
    
    if (modelInput) modelInput.value = '';
    if (appInput) appInput.value = '';
    if (statusSelect) statusSelect.value = '';
    
    // Reload without filters
    htmx.ajax('GET', '/analysis/api/tasks/list', {
      target: '#main-tasks-table-wrapper',
      swap: 'innerHTML'
    });
  }

  function changeAnalysisPage(page) {
    applyAnalysisFilters({ page });
  }

  function changeAnalysisPerPage(perPage) {
    applyAnalysisFilters({ per_page: perPage, page: 1 });
  }

  // Export functions to global scope for template event handlers
  window.debounceAnalysisFilters = debounceAnalysisFilters;
  window.applyAnalysisFilters = applyAnalysisFilters;
  window.refreshAnalysisTasks = refreshAnalysisTasks;
  window.clearAnalysisFilters = clearAnalysisFilters;
  window.changeAnalysisPage = changeAnalysisPage;
  window.changeAnalysisPerPage = changeAnalysisPerPage;

  // Auto-refresh active tasks every 10 seconds when page is visible
  let refreshInterval;
  
  function startAutoRefresh() {
    if (refreshInterval) return; // Already running
    
    refreshInterval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        // Check if there are active tasks
        const activeTasks = document.querySelectorAll('[data-type="task"]');
        if (activeTasks.length > 0) {
          // Silently refresh to update progress
          refreshAnalysisTasks();
        }
      }
    }, 10000); // 10 seconds
  }

  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
    }
  }

  // Start auto-refresh on page load
  document.addEventListener('DOMContentLoaded', startAutoRefresh);

  // Stop auto-refresh when navigating away
  window.addEventListener('beforeunload', stopAutoRefresh);

  // Restart auto-refresh after HTMX swaps
  document.body.addEventListener('htmx:afterSwap', (evt) => {
    if (evt.target?.id === 'main-tasks-table-wrapper') {
      startAutoRefresh();
    }
  });

  // Handle visibility changes to pause/resume auto-refresh
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
  });

})();
