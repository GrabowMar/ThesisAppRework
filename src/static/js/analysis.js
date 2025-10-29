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
    const wrapper = document.getElementById('main-tasks-table-wrapper');
    if (wrapper) {
      htmx.ajax('GET', `/analysis/api/tasks/list?${params.toString()}`, {
        target: '#main-tasks-table-wrapper',
        swap: 'innerHTML'
      });
    }
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
    const wrapper = document.getElementById('main-tasks-table-wrapper');
    if (wrapper) {
      htmx.ajax('GET', '/analysis/api/tasks/list', {
        target: '#main-tasks-table-wrapper',
        swap: 'innerHTML'
      });
    }
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

  // Toggle subtasks visibility for hierarchical task display
  window.toggleSubtasks = function(taskId) {
    const rows = document.querySelectorAll(`tr.subtask-row[data-parent="${taskId}"]`);
    const icon = document.getElementById(`icon-${taskId}`);
    
    if (!rows.length || !icon) return;
    
    rows.forEach(row => {
      const isHidden = row.style.display === 'none';
      row.style.display = isHidden ? 'table-row' : 'none';
    });
    
    // Toggle chevron direction
    icon.classList.toggle('fa-chevron-right');
    icon.classList.toggle('fa-chevron-down');
  };

})();
