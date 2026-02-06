// Rankings page client logic
// ------------------------------------------------------------
// Responsibilities:
//  - Fetch filtered rankings from API
//  - Maintain client-side selection state (max 10 models)
//  - Render rankings table with benchmark data
//  - Handle weight adjustments for composite score
//  - Export functionality
// ------------------------------------------------------------

if (window.__RANKINGS_JS_LOADED__) {
  console.debug('rankings.js already loaded – skipping re-init');
} else {
  window.__RANKINGS_JS_LOADED__ = true;

  // State
  let rankingsData = [];
  let selectedRankings = new Set();
  let currentSort = { column: 'composite', direction: 'desc' };
  let searchTimeout;
  let currentPage = 1;
  let perPage = 25;
  let totalPages = 1;
  let rankingsPageBootstrapped = false;

  // Default weights (can be overridden by server)
  let weights = {
    humaneval_plus: 20,
    swe_bench_verified: 25,
    bigcodebench_hard: 20,
    livebench_coding: 15,
    mbpp_plus: 10,
    livecodebench: 10
  };

  // Initialize from server data if available
  function initFromServerData() {
    if (window.RANKINGS_INITIAL_DATA) {
      rankingsData = window.RANKINGS_INITIAL_DATA;
    }
    if (window.RANKINGS_SELECTED) {
      selectedRankings = new Set(window.RANKINGS_SELECTED);
    }
    if (window.RANKINGS_DEFAULT_WEIGHTS) {
      weights = { ...weights, ...window.RANKINGS_DEFAULT_WEIGHTS };
    }
  }

  // =========================================================================
  // Filter Parameter Building
  // =========================================================================

  function buildRankingFilterParams() {
    const p = new URLSearchParams();
    
    // Search term
    const searchEl = document.getElementById('ranking-search');
    const search = searchEl?.value?.trim();
    if (search) {
      p.append('search', search);
    }
    
    // Provider filter
    const providerEl = document.getElementById('provider-filter');
    const provider = providerEl?.value?.trim();
    if (provider) {
      p.append('provider', provider);
    }
    
    // Price filter
    const priceEl = document.getElementById('price-filter');
    const price = priceEl?.value?.trim();
    if (price) {
      p.append('max_price', price);
    }
    
    // Context filter
    const contextEl = document.getElementById('context-filter');
    const context = contextEl?.value?.trim();
    if (context) {
      p.append('min_context', context);
    }
    
    // Has benchmarks filter
    if (document.getElementById('filter-has-benchmarks')?.checked) {
      p.append('has_benchmarks', '1');
    }
    
    // Include free filter
    if (!document.getElementById('filter-include-free')?.checked) {
      p.append('exclude_free', '1');
    }
    
    return p;
  }

  // =========================================================================
  // API Calls
  // =========================================================================

  function showLoading(show) {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) spinner.style.display = show ? 'block' : 'none';
  }

  function loadRankingsPaginated() {
    showLoading(true);
    const params = buildRankingFilterParams();
    params.append('page', String(currentPage));
    params.append('per_page', String(perPage));
    
    // Add sort parameters
    params.append('sort_by', currentSort.column);
    params.append('sort_dir', currentSort.direction);
    
    const url = '/rankings/api/rankings?' + params.toString();
    console.log('[Rankings] Loading:', url);
    
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        console.log('[Rankings] API Response:', data);
        rankingsData = data.rankings || data.data || [];
        const pagination = data.pagination || {};
        totalPages = pagination.total_pages || 1;
        
        updateStatistics(data.statistics || {});
        renderRankingsTable(rankingsData);
        renderPagination(pagination);
        updateSelectionUI();
      })
      .catch(e => {
        console.error('[Rankings] Error loading:', e);
        showError('Failed to load rankings: ' + e.message);
      })
      .finally(() => {
        showLoading(false);
      });
  }

  function showError(message) {
    const tbody = document.getElementById('rankings-table-body');
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="13" class="text-center text-danger py-4">
            <i class="fa-solid fa-exclamation-triangle me-2"></i>${message}
          </td>
        </tr>
      `;
    }
  }

  // =========================================================================
  // Statistics Update
  // =========================================================================

  function updateStatistics(stats) {
    const totalEl = document.getElementById('total-models');
    if (totalEl) totalEl.textContent = stats.total || rankingsData.length || 0;
    
    const benchmarkedEl = document.getElementById('models-with-benchmarks');
    if (benchmarkedEl) benchmarkedEl.textContent = stats.with_benchmarks || rankingsData.length || 0;
    
    const providersEl = document.getElementById('unique-providers');
    if (providersEl) {
      const uniqueProviders = new Set(rankingsData.map(m => m.provider).filter(Boolean));
      providersEl.textContent = stats.unique_providers || uniqueProviders.size || 0;
    }
  }

  // =========================================================================
  // Table Rendering
  // =========================================================================

  function renderRankingsTable(models) {
    const tbody = document.getElementById('rankings-table-body');
    if (!tbody) return;
    
    if (!models || models.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="14" class="text-center text-muted py-4">
            <i class="fa-solid fa-search me-2"></i>No models found matching your filters.
          </td>
        </tr>
      `;
      return;
    }
    
    const html = models.map((model, index) => {
      const rank = (currentPage - 1) * perPage + index + 1;
      const isSelected = selectedRankings.has(model.model_id);
      const modelSlug = model.model_id?.replace('/', '_') || '';
      
      // MSS components (Chapter 4 methodology)
      const mss = model.mss_score ?? model.composite_score;
      const adoption = model.adoption_score ?? model.adoption;
      const benchmark = model.benchmark_score ?? model.benchmarks;
      const cost = model.cost_efficiency_score ?? model.cost_efficiency;
      const access = model.accessibility_score ?? model.accessibility;
      
      // Chapter 4 benchmark scores
      const bfcl = model.bfcl_score ?? model.bfcl;
      const webdev = model.webdev_arena_elo ?? model.webdev_elo;
      const livebench = model.livebench_coding ?? model.livebench;
      
      return `
        <tr data-model-id="${escapeHtml(model.model_id)}" 
            data-provider="${escapeHtml(model.provider || '')}"
            data-mss="${mss || 0}"
            class="${isSelected ? 'table-primary' : ''}">
          <td>
            <label class="form-check mb-0">
              <input type="checkbox" class="form-check-input ranking-checkbox" 
                     value="${escapeHtml(model.model_id)}"
                     ${isSelected ? 'checked' : ''}
                     ${!isSelected && selectedRankings.size >= 10 ? 'disabled' : ''}
                     onchange="toggleRankingSelection(this)">
            </label>
          </td>
          <td class="text-muted">${rank}</td>
          <td>
            <span class="fw-medium">${escapeHtml(model.model_name || model.name || '')}</span>
            <small class="text-muted d-block">${escapeHtml(model.provider || '')}</small>
          </td>
          <td class="fw-bold ${getMSSClass(mss)}">
            ${formatScore(mss)}
          </td>
          <td class="${getComponentClass(adoption)}">
            ${formatScore(adoption)}
          </td>
          <td class="${getComponentClass(benchmark)}">
            ${formatScore(benchmark)}
          </td>
          <td class="${getComponentClass(cost)}">
            ${formatScore(cost)}
          </td>
          <td class="${getComponentClass(access)}">
            ${formatScore(access)}
          </td>
          <td class="${getScoreClass(bfcl, 80, 60)}">
            ${formatScore(bfcl, '%')}
          </td>
          <td class="text-info">
            ${webdev ? webdev.toFixed(0) : '<span class="text-muted">—</span>'}
          </td>
          <td class="${getScoreClass(livebench, 60, 40)}">
            ${formatScore(livebench)}
          </td>
          <td>${formatContext(model.context_length)}</td>
          <td>${formatPrice(model.price_per_million_input)}</td>
          <td>
            <div class="btn-group btn-group-sm">
              <a href="/models/detail/${modelSlug}" class="btn btn-outline-secondary btn-sm" title="View model details">
                <i class="fa-solid fa-info-circle"></i>
              </a>
            </div>
          </td>
        </tr>
      `;
    }).join('');
    
    tbody.innerHTML = html;
    
    // Update sort indicators
    updateSortIndicators();
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // MSS-specific color coding (0-100 scale)
  function getMSSClass(value) {
    if (value === null || value === undefined) return 'text-muted';
    if (value >= 70) return 'text-success';
    if (value >= 50) return 'text-primary';
    if (value >= 30) return 'text-warning';
    return 'text-danger';
  }

  // Component score color coding (0-100 scale)
  function getComponentClass(value) {
    if (value === null || value === undefined) return 'text-muted';
    if (value >= 80) return 'text-success';
    if (value >= 60) return 'text-info';
    if (value >= 40) return 'text-warning';
    return 'text-muted';
  }

  function getScoreClass(value, highThreshold, medThreshold) {
    if (value === null || value === undefined) return 'text-muted';
    if (value >= highThreshold) return 'text-success';
    if (value >= medThreshold) return 'text-warning';
    return 'text-danger';
  }

  function formatScore(value, suffix = '') {
    if (value === null || value === undefined) return '<span class="text-muted">—</span>';
    return value.toFixed(1) + suffix;
  }

  function formatContext(value) {
    if (!value) return '—';
    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
    if (value >= 1000) return (value / 1000).toFixed(0) + 'K';
    return value.toLocaleString();
  }

  function formatPrice(value) {
    if (value === null || value === undefined) return '—';
    if (value === 0) return '<span class="badge bg-success">FREE</span>';
    return '$' + value.toFixed(2);
  }

  // =========================================================================
  // Pagination
  // =========================================================================

  function renderPagination(pagination) {
    const container = document.getElementById('rankings-pagination');
    const summary = document.getElementById('rankings-page-summary');
    
    if (!container) return;
    
    const total = pagination.total || 0;
    const page = pagination.page || currentPage;
    const pages = pagination.total_pages || totalPages;
    
    if (summary) {
      const start = (page - 1) * perPage + 1;
      const end = Math.min(page * perPage, total);
      summary.textContent = `Showing ${start}-${end} of ${total} models`;
    }
    
    if (pages <= 1) {
      container.innerHTML = '';
      return;
    }
    
    let html = '';
    
    // Previous button
    html += `<li class="page-item ${page === 1 ? 'disabled' : ''}">
      <a class="page-link" href="#" onclick="goToRankingsPage(${page - 1}); return false;">
        <i class="fa-solid fa-chevron-left"></i>
      </a>
    </li>`;
    
    // Page numbers
    const maxVisible = 5;
    let startPage = Math.max(1, page - Math.floor(maxVisible / 2));
    let endPage = Math.min(pages, startPage + maxVisible - 1);
    
    if (endPage - startPage < maxVisible - 1) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    if (startPage > 1) {
      html += `<li class="page-item"><a class="page-link" href="#" onclick="goToRankingsPage(1); return false;">1</a></li>`;
      if (startPage > 2) {
        html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
      }
    }
    
    for (let i = startPage; i <= endPage; i++) {
      html += `<li class="page-item ${i === page ? 'active' : ''}">
        <a class="page-link" href="#" onclick="goToRankingsPage(${i}); return false;">${i}</a>
      </li>`;
    }
    
    if (endPage < pages) {
      if (endPage < pages - 1) {
        html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
      }
      html += `<li class="page-item"><a class="page-link" href="#" onclick="goToRankingsPage(${pages}); return false;">${pages}</a></li>`;
    }
    
    // Next button
    html += `<li class="page-item ${page === pages ? 'disabled' : ''}">
      <a class="page-link" href="#" onclick="goToRankingsPage(${page + 1}); return false;">
        <i class="fa-solid fa-chevron-right"></i>
      </a>
    </li>`;
    
    container.innerHTML = html;
  }

  // =========================================================================
  // Selection Management
  // =========================================================================

  function toggleRankingSelection(checkbox) {
    const modelId = checkbox.value;
    
    if (checkbox.checked) {
      if (selectedRankings.size >= 10) {
        checkbox.checked = false;
        alert('Maximum 10 models can be selected for comparison.');
        return;
      }
      selectedRankings.add(modelId);
    } else {
      selectedRankings.delete(modelId);
    }
    
    updateSelectionUI();
    updateRowHighlight(modelId, checkbox.checked);
    updateCheckboxStates();
  }

  function updateRowHighlight(modelId, selected) {
    const row = document.querySelector(`tr[data-model-id="${modelId}"]`);
    if (row) {
      row.classList.toggle('table-primary', selected);
    }
  }

  function updateCheckboxStates() {
    const checkboxes = document.querySelectorAll('.ranking-checkbox');
    checkboxes.forEach(cb => {
      if (!cb.checked && selectedRankings.size >= 10) {
        cb.disabled = true;
      } else {
        cb.disabled = false;
      }
    });
  }

  function updateSelectionUI() {
    const count = selectedRankings.size;
    const summaryEl = document.getElementById('selectionSummary');
    const countEl = document.getElementById('selectedCount');
    const listEl = document.getElementById('selectedModelsList');
    const indicatorEl = document.getElementById('rankings-selection-indicator');
    const clearBtn = document.getElementById('clear-selection-btn');
    
    if (countEl) countEl.textContent = count;
    
    if (summaryEl) {
      summaryEl.style.display = count > 0 ? 'block' : 'none';
    }
    
    if (clearBtn) {
      clearBtn.style.display = count > 0 ? 'inline-block' : 'none';
    }
    
    if (indicatorEl) {
      indicatorEl.textContent = count > 0 ? `${count} selected` : '';
    }
    
    if (listEl) {
      const names = Array.from(selectedRankings).slice(0, 3);
      const suffix = selectedRankings.size > 3 ? '...' : '';
      listEl.textContent = names.join(', ') + suffix;
    }
    
    // Update select-all checkbox
    const selectAllEl = document.getElementById('select-all-rankings');
    if (selectAllEl) {
      const visibleCheckboxes = document.querySelectorAll('.ranking-checkbox');
      const checkedCount = document.querySelectorAll('.ranking-checkbox:checked').length;
      selectAllEl.checked = visibleCheckboxes.length > 0 && checkedCount === visibleCheckboxes.length;
      selectAllEl.indeterminate = checkedCount > 0 && checkedCount < visibleCheckboxes.length;
    }
  }

  function toggleSelectAllRankings() {
    const selectAllEl = document.getElementById('select-all-rankings');
    const checkboxes = document.querySelectorAll('.ranking-checkbox');
    
    if (selectAllEl.checked) {
      // Select visible (up to 10 total)
      checkboxes.forEach(cb => {
        if (selectedRankings.size < 10 && !cb.checked) {
          cb.checked = true;
          selectedRankings.add(cb.value);
          updateRowHighlight(cb.value, true);
        }
      });
    } else {
      // Deselect all visible
      checkboxes.forEach(cb => {
        if (cb.checked) {
          cb.checked = false;
          selectedRankings.delete(cb.value);
          updateRowHighlight(cb.value, false);
        }
      });
    }
    
    updateSelectionUI();
    updateCheckboxStates();
  }

  function clearRankingSelection() {
    selectedRankings.clear();
    document.querySelectorAll('.ranking-checkbox').forEach(cb => {
      cb.checked = false;
      updateRowHighlight(cb.value, false);
    });
    const selectAllEl = document.getElementById('select-all-rankings');
    if (selectAllEl) selectAllEl.checked = false;
    updateSelectionUI();
    updateCheckboxStates();
  }

  function selectTopModels(count) {
    clearRankingSelection();
    const checkboxes = Array.from(document.querySelectorAll('.ranking-checkbox')).slice(0, count);
    checkboxes.forEach(cb => {
      cb.checked = true;
      selectedRankings.add(cb.value);
      updateRowHighlight(cb.value, true);
    });
    updateSelectionUI();
    updateCheckboxStates();
  }

  // =========================================================================
  // Sorting
  // =========================================================================

  function sortRankings(column) {
    if (currentSort.column === column) {
      currentSort.direction = currentSort.direction === 'desc' ? 'asc' : 'desc';
    } else {
      currentSort.column = column;
      currentSort.direction = 'desc';
    }
    
    loadRankingsPaginated();
  }

  function updateSortIndicators() {
    document.querySelectorAll('#rankings-table thead th.sortable').forEach(th => {
      th.classList.remove('sort-asc', 'sort-desc', 'active');
      if (th.dataset.column === currentSort.column) {
        th.classList.add('active');
        th.classList.add(currentSort.direction === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }

  // Setup click handlers for sortable columns
  function setupSortHandlers() {
    document.querySelectorAll('#rankings-table thead th.sortable').forEach(th => {
      th.style.cursor = 'pointer';
      th.addEventListener('click', () => {
        sortRankings(th.dataset.column);
      });
    });
  }

  // =========================================================================
  // Filters
  // =========================================================================

  function applyRankingFilters() {
    currentPage = 1;
    loadRankingsPaginated();
  }

  function debounceRankingSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(applyRankingFilters, 300);
  }

  function clearRankingSearch() {
    const el = document.getElementById('ranking-search');
    if (el) el.value = '';
    applyRankingFilters();
  }

  function clearAllRankingFilters() {
    // Clear search
    const searchEl = document.getElementById('ranking-search');
    if (searchEl) searchEl.value = '';
    
    // Reset selects
    ['provider-filter', 'price-filter', 'context-filter'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    
    // Reset checkboxes to defaults
    const hasBenchmarksEl = document.getElementById('filter-has-benchmarks');
    if (hasBenchmarksEl) hasBenchmarksEl.checked = true;
    
    const includeFreeEl = document.getElementById('filter-include-free');
    if (includeFreeEl) includeFreeEl.checked = true;
    
    applyRankingFilters();
  }

  function toggleAdvancedFilters() {
    const panel = document.getElementById('advanced-filters-panel');
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'block';
  }

  // =========================================================================
  // Weight Management
  // =========================================================================

  function updateWeightDisplay(slider) {
    const val = document.getElementById(slider.id + '_val');
    if (val) {
      val.textContent = slider.value + '%';
    }
    updateWeightTotal();
  }

  function updateWeightTotal() {
    const sliders = document.querySelectorAll('.weight-input');
    let total = 0;
    sliders.forEach(s => {
      total += parseInt(s.value) || 0;
    });
    
    const totalEl = document.getElementById('weightTotal');
    if (totalEl) {
      totalEl.textContent = total + '%';
      totalEl.className = 'badge fs-5 ' + (total === 100 ? 'bg-success' : 'bg-danger');
    }
  }

  function resetWeights() {
    const defaults = window.RANKINGS_DEFAULT_WEIGHTS || {
      humaneval_plus: 20,
      swe_bench_verified: 25,
      bigcodebench_hard: 20,
      livebench_coding: 15,
      mbpp_plus: 10
    };
    
    const mapping = {
      'weight_humaneval': defaults.humaneval_plus,
      'weight_swebench': defaults.swe_bench_verified,
      'weight_bigcode': defaults.bigcodebench_hard,
      'weight_livebench': defaults.livebench_coding,
      'weight_mbpp': defaults.mbpp_plus
    };
    
    Object.entries(mapping).forEach(([id, value]) => {
      const slider = document.getElementById(id);
      if (slider) {
        slider.value = value;
        updateWeightDisplay(slider);
      }
    });
    
    updateWeightTotal();
  }

  function recalculateComposite() {
    const newWeights = {
      humaneval_plus: parseInt(document.getElementById('weight_humaneval')?.value) || 0,
      swe_bench_verified: parseInt(document.getElementById('weight_swebench')?.value) || 0,
      bigcodebench_hard: parseInt(document.getElementById('weight_bigcode')?.value) || 0,
      livebench_coding: parseInt(document.getElementById('weight_livebench')?.value) || 0,
      mbpp_plus: parseInt(document.getElementById('weight_mbpp')?.value) || 0
    };
    
    const total = Object.values(newWeights).reduce((a, b) => a + b, 0);
    if (total === 0) {
      alert('Please set at least one weight greater than 0.');
      return;
    }
    
    // Normalize weights
    Object.keys(newWeights).forEach(key => {
      newWeights[key] = newWeights[key] / total;
    });
    
    // Recalculate composite scores
    rankingsData.forEach(model => {
      let score = 0;
      let usedWeight = 0;
      
      const benchmarks = {
        humaneval_plus: model.humaneval_plus,
        swe_bench_verified: model.swe_bench_verified,
        bigcodebench_hard: model.bigcodebench_hard,
        livebench_coding: model.livebench_coding,
        mbpp_plus: model.mbpp_plus
      };
      
      Object.entries(benchmarks).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          score += value * newWeights[key];
          usedWeight += newWeights[key];
        }
      });
      
      model.composite_score = usedWeight > 0 ? score / usedWeight : null;
    });
    
    // Re-sort by composite
    rankingsData.sort((a, b) => {
      if (a.composite_score === null) return 1;
      if (b.composite_score === null) return -1;
      return b.composite_score - a.composite_score;
    });
    
    currentSort = { column: 'composite', direction: 'desc' };
    renderRankingsTable(rankingsData);
  }

  // =========================================================================
  // Export Functions
  // =========================================================================

  function exportRankingsCSV() {
    const headers = ['Rank', 'Model', 'Provider', 'Composite', 'HumanEval+', 'SWE-bench', 'BigCodeBench', 'LiveBench', 'MBPP+', 'LiveCodeBench', 'Context', 'Price (In)', 'Price (Out)'];
    const rows = rankingsData.map((m, i) => [
      i + 1,
      m.model_name || m.name || '',
      m.provider || '',
      m.composite_score?.toFixed(1) || '',
      m.humaneval_plus?.toFixed(1) || '',
      m.swe_bench_verified?.toFixed(1) || '',
      m.bigcodebench_hard?.toFixed(1) || '',
      m.livebench_coding?.toFixed(1) || '',
      m.mbpp_plus?.toFixed(1) || '',
      m.livecodebench?.toFixed(1) || '',
      m.context_length || '',
      m.price_per_million_input || '',
      m.price_per_million_output || ''
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rankings_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // =========================================================================
  // Actions
  // =========================================================================

  function saveSelectionForPipeline() {
    if (selectedRankings.size === 0) {
      alert('Please select at least one model.');
      return;
    }
    
    fetch('/rankings/api/select-models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_ids: Array.from(selectedRankings) })
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        alert(`Saved ${data.selected_count} models for pipeline use.`);
      } else {
        alert('Error: ' + (data.error || 'Unknown error'));
      }
    })
    .catch(e => {
      alert('Error saving selection: ' + e.message);
    });
  }

  function goToComparison() {
    if (selectedRankings.size < 2) {
      alert('Please select at least 2 models to compare.');
      return;
    }
    const ids = Array.from(selectedRankings).join(',');
    window.location.href = `/rankings/compare?models=${encodeURIComponent(ids)}`;
  }

  // =========================================================================
  // Navigation
  // =========================================================================

  function goToRankingsPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    loadRankingsPaginated();
  }

  function changePerPage(value) {
    const n = parseInt(value, 10);
    if (!isNaN(n) && n > 0) {
      perPage = n;
      currentPage = 1;
      loadRankingsPaginated();
    }
  }

  // =========================================================================
  // Bootstrap
  // =========================================================================

  function bootstrapRankingsPage() {
    if (!document.getElementById('rankings-table-body')) {
      return false;
    }
    
    if (rankingsPageBootstrapped) {
      return true;
    }
    
    initFromServerData();
    setupSortHandlers();
    loadRankingsPaginated();
    
    rankingsPageBootstrapped = true;
    return true;
  }

  // Initialize when DOM ready
  function whenReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  whenReady(() => {
    bootstrapRankingsPage();
  });

  // Re-bootstrap on HTMX navigation
  document.addEventListener('htmx:afterSwap', (event) => {
    if (event?.target?.querySelector?.('#rankings-table-body')) {
      rankingsPageBootstrapped = false;
      bootstrapRankingsPage();
    }
  });

  // Expose globals
  window.toggleRankingSelection = toggleRankingSelection;
  window.toggleSelectAllRankings = toggleSelectAllRankings;
  window.clearRankingSelection = clearRankingSelection;
  window.selectTopModels = selectTopModels;
  window.applyRankingFilters = applyRankingFilters;
  window.debounceRankingSearch = debounceRankingSearch;
  window.clearRankingSearch = clearRankingSearch;
  window.clearAllRankingFilters = clearAllRankingFilters;
  window.toggleAdvancedFilters = toggleAdvancedFilters;
  window.updateWeightDisplay = updateWeightDisplay;
  window.resetWeights = resetWeights;
  window.recalculateComposite = recalculateComposite;
  window.exportRankingsCSV = exportRankingsCSV;
  window.saveSelectionForPipeline = saveSelectionForPipeline;
  window.goToComparison = goToComparison;
  window.goToRankingsPage = goToRankingsPage;
  window.changePerPage = changePerPage;
  window.sortRankings = sortRankings;

} // End of SINGLE EXECUTION BLOCK
