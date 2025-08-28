/**
 * Application-Specific Features
 * Business logic and domain-specific functionality
 */

class ModelManager {
  constructor() {
    this.selectedModels = new Set();
    this.init();
  }

  init() {
    this.initModelSelection();
    this.initBulkActions();
    this.initFilters();
  }

  initModelSelection() {
    document.addEventListener('change', (e) => {
      if (e.target.matches('.model-checkbox')) {
        const modelSlug = e.target.value;
        if (e.target.checked) {
          this.selectedModels.add(modelSlug);
        } else {
          this.selectedModels.delete(modelSlug);
        }
        this.updateBulkActionsUI();
      }
    });

    // Select all functionality
    document.addEventListener('change', (e) => {
      if (e.target.matches('#select-all-models')) {
        const checkboxes = document.querySelectorAll('.model-checkbox');
        checkboxes.forEach(cb => {
          cb.checked = e.target.checked;
          if (e.target.checked) {
            this.selectedModels.add(cb.value);
          } else {
            this.selectedModels.delete(cb.value);
          }
        });
        this.updateBulkActionsUI();
      }
    });
  }

  initBulkActions() {
    document.addEventListener('click', (e) => {
      if (e.target.matches('[data-bulk-action]')) {
        e.preventDefault();
        const action = e.target.dataset.bulkAction;
        this.executeBulkAction(action);
      }
    });
  }

  updateBulkActionsUI() {
    const count = this.selectedModels.size;
    const bulkBar = document.querySelector('.bulk-actions-bar');
    const countDisplay = document.querySelector('.selected-count');

    if (bulkBar) {
      bulkBar.style.display = count > 0 ? 'flex' : 'none';
    }
    
    if (countDisplay) {
      countDisplay.textContent = `${count} model${count !== 1 ? 's' : ''} selected`;
    }
  }

  async executeBulkAction(action) {
    if (this.selectedModels.size === 0) {
      window.App.showToast('Please select models first', 'warning');
      return;
    }

    const models = Array.from(this.selectedModels);
    
    switch (action) {
      case 'analyze':
        await this.bulkAnalyze(models);
        break;
      case 'export':
        await this.bulkExport(models);
        break;
      case 'delete':
        if (confirm(`Delete ${models.length} selected models?`)) {
          await this.bulkDelete(models);
        }
        break;
      case 'compare':
        if (models.length > 1) {
          this.compareModels(models);
        } else {
          window.App.showToast('Select at least 2 models to compare', 'warning');
        }
        break;
    }
  }

  async bulkAnalyze(models) {
    window.App.showToast(`Starting analysis for ${models.length} models...`, 'info');
    
    try {
      const response = await window.appCore.fetchJSON('/api/models/bulk-analyze', {
        method: 'POST',
        body: JSON.stringify({ models })
      });
      
      if (response.success) {
        window.App.showToast('Bulk analysis started successfully', 'success');
        // Refresh the page or update UI
        setTimeout(() => location.reload(), 1000);
      }
    } catch (error) {
      window.App.showToast('Failed to start bulk analysis', 'error');
    }
  }

  async bulkExport(models) {
    try {
      const response = await fetch('/api/models/bulk-export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models })
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `models-export-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        window.App.showToast('Models exported successfully', 'success');
      }
    } catch (error) {
      window.App.showToast('Export failed', 'error');
    }
  }

  compareModels(models) {
    const url = `/models/compare?models=${models.join(',')}`;
    window.open(url, '_blank');
  }

  initFilters() {
    const filterForm = document.querySelector('#model-filters');
    if (!filterForm) return;

    // Live filtering
    filterForm.addEventListener('input', window.appCore.debounce((e) => {
      this.applyFilters();
    }, 300));

    filterForm.addEventListener('change', () => {
      this.applyFilters();
    });

    // Clear filters
    document.addEventListener('click', (e) => {
      if (e.target.matches('[data-clear-filters]')) {
        e.preventDefault();
        this.clearFilters();
      }
    });
  }

  applyFilters() {
    const formData = new FormData(document.querySelector('#model-filters'));
    const filters = Object.fromEntries(formData.entries());
    
    // Apply filters via HTMX if available, otherwise use client-side filtering
    if (window.htmx) {
      htmx.ajax('GET', '/models', {
        target: '#models-container',
        values: filters
      });
    } else {
      this.clientSideFilter(filters);
    }
  }

  clientSideFilter(filters) {
    const rows = document.querySelectorAll('[data-model-row]');
    
    rows.forEach(row => {
      let show = true;
      
      // Provider filter
      if (filters.provider && filters.provider !== 'all') {
        const provider = row.dataset.provider;
        if (provider !== filters.provider) show = false;
      }
      
      // Capability filter
      if (filters.capability && filters.capability !== 'all') {
        const capabilities = row.dataset.capabilities?.split(',') || [];
        if (!capabilities.includes(filters.capability)) show = false;
      }
      
      // Search filter
      if (filters.search) {
        const text = row.textContent.toLowerCase();
        if (!text.includes(filters.search.toLowerCase())) show = false;
      }
      
      row.style.display = show ? '' : 'none';
    });
    
    this.updateFilterStats();
  }

  updateFilterStats() {
    const total = document.querySelectorAll('[data-model-row]').length;
    const visible = document.querySelectorAll('[data-model-row]:not([style*="display: none"])').length;
    
    const statsElement = document.querySelector('.filter-stats');
    if (statsElement) {
      statsElement.textContent = `Showing ${visible} of ${total} models`;
    }
  }

  clearFilters() {
    const form = document.querySelector('#model-filters');
    if (form) {
      form.reset();
      this.applyFilters();
    }
  }
}

class AnalysisManager {
  constructor() {
    this.runningAnalyses = new Map();
    this.init();
  }

  init() {
    this.initAnalysisControls();
    this.initProgressTracking();
    this.initResultsView();
  }

  initAnalysisControls() {
    document.addEventListener('click', (e) => {
      if (e.target.matches('[data-start-analysis]')) {
        e.preventDefault();
        const config = JSON.parse(e.target.dataset.startAnalysis);
        this.startAnalysis(config);
      }

      if (e.target.matches('[data-stop-analysis]')) {
        e.preventDefault();
        const analysisId = e.target.dataset.stopAnalysis;
        this.stopAnalysis(analysisId);
      }
    });
  }

  async startAnalysis(config) {
    try {
      const response = await window.appCore.fetchJSON('/api/analysis/start', {
        method: 'POST',
        body: JSON.stringify(config)
      });

      if (response.success) {
        this.runningAnalyses.set(response.analysisId, {
          ...config,
          startTime: Date.now(),
          status: 'running'
        });

        window.App.showToast('Analysis started successfully', 'success');
        this.trackProgress(response.analysisId);
      }
    } catch (error) {
      window.App.showToast('Failed to start analysis', 'error');
    }
  }

  async stopAnalysis(analysisId) {
    try {
      await window.appCore.fetchJSON(`/api/analysis/${analysisId}/stop`, {
        method: 'POST'
      });

      this.runningAnalyses.delete(analysisId);
      window.App.showToast('Analysis stopped', 'info');
    } catch (error) {
      window.App.showToast('Failed to stop analysis', 'error');
    }
  }

  trackProgress(analysisId) {
    const progressElement = document.querySelector(`[data-analysis-progress="${analysisId}"]`);
    if (!progressElement) return;

    const tracker = new window.Components.ProgressTracker(progressElement);
    
    const checkProgress = async () => {
      try {
        const response = await window.appCore.fetchJSON(`/api/analysis/${analysisId}/progress`);
        
        tracker.setProgress(response.progress);
        
        if (response.status === 'completed') {
          tracker.setStatus('success', 'Completed');
          this.runningAnalyses.delete(analysisId);
          this.loadResults(analysisId);
        } else if (response.status === 'failed') {
          tracker.setStatus('error', 'Failed');
          this.runningAnalyses.delete(analysisId);
        } else {
          setTimeout(checkProgress, 2000); // Check every 2 seconds
        }
      } catch (error) {
        console.error('Progress tracking error:', error);
        setTimeout(checkProgress, 5000); // Retry after 5 seconds
      }
    };

    checkProgress();
  }

  initProgressTracking() {
    // Resume tracking for any running analyses on page load
    document.querySelectorAll('[data-analysis-progress]').forEach(element => {
      const analysisId = element.dataset.analysisProgress;
      if (element.dataset.status === 'running') {
        this.trackProgress(analysisId);
      }
    });
  }

  async loadResults(analysisId) {
    const resultsContainer = document.querySelector(`[data-analysis-results="${analysisId}"]`);
    if (!resultsContainer) return;

    try {
      const response = await window.appCore.fetchJSON(`/api/analysis/${analysisId}/results`);
      this.displayResults(resultsContainer, response.results);
    } catch (error) {
      resultsContainer.innerHTML = '<div class="alert alert-danger">Failed to load results</div>';
    }
  }

  displayResults(container, results) {
    // Create a tabbed interface for different result types
    const tabs = ['security', 'performance', 'quality'];
    
    let tabsHtml = '<ul class="nav nav-tabs" role="tablist">';
    tabs.forEach((tab, index) => {
      if (results[tab]) {
        tabsHtml += `
          <li class="nav-item">
            <a class="nav-link ${index === 0 ? 'active' : ''}" 
               data-bs-toggle="tab" href="#${tab}-results" role="tab">
              ${tab.charAt(0).toUpperCase() + tab.slice(1)}
            </a>
          </li>
        `;
      }
    });
    tabsHtml += '</ul>';

    let contentHtml = '<div class="tab-content mt-3">';
    tabs.forEach((tab, index) => {
      if (results[tab]) {
        contentHtml += `
          <div class="tab-pane fade ${index === 0 ? 'show active' : ''}" 
               id="${tab}-results" role="tabpanel">
            <div data-code-viewer='{"language": "json"}'>${JSON.stringify(results[tab], null, 2)}</div>
          </div>
        `;
      }
    });
    contentHtml += '</div>';

    container.innerHTML = tabsHtml + contentHtml;

    // Initialize code viewers for the results
    container.querySelectorAll('[data-code-viewer]').forEach(element => {
      new window.Components.CodeViewer(element, JSON.parse(element.dataset.codeViewer));
    });
  }

  initResultsView() {
    // Export results functionality
    document.addEventListener('click', (e) => {
      if (e.target.matches('[data-export-results]')) {
        e.preventDefault();
        const analysisId = e.target.dataset.exportResults;
        this.exportResults(analysisId);
      }
    });
  }

  async exportResults(analysisId) {
    try {
      const response = await fetch(`/api/analysis/${analysisId}/export`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `analysis-${analysisId}-results.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      window.App.showToast('Export failed', 'error');
    }
  }
}

// Initialize managers when DOM is ready (defensive)
document.addEventListener('DOMContentLoaded', () => {
  // Only initialize if relevant elements exist
  if (document.querySelector('[data-model-row], .model-checkbox')) {
    if (typeof window.modelManager === 'undefined') {
      window.modelManager = new ModelManager();
    }
  }

  if (document.querySelector('[data-start-analysis], [data-analysis-progress]')) {
    if (typeof window.analysisManager === 'undefined') {
      window.analysisManager = new AnalysisManager();
    }
  }
});

// Export for manual initialization (defensive)
if (typeof window.AppFeatures === 'undefined') {
  window.AppFeatures = {
    ModelManager,
    AnalysisManager
  };
}