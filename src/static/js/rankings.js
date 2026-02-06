// Rankings page client logic
// ------------------------------------------------------------
// Responsibilities:
//  - Fetch filtered rankings from API
//  - Maintain client-side selection state (max 10 models)
//  - Render rankings table with all 9 Ch.4 benchmark columns
//  - Export functionality
// ------------------------------------------------------------

if (window.__RANKINGS_JS_LOADED__) {
  console.debug('rankings.js already loaded – skipping re-init');
} else {
  window.__RANKINGS_JS_LOADED__ = true;

  // State
  let rankingsData = [];
  let selectedRankings = new Set();
  let currentSort = { column: 'mss', direction: 'desc' };
  let searchTimeout;
  let currentPage = 1;
  let perPage = 25;
  let totalPages = 1;
  let rankingsPageBootstrapped = false;

  // Initialize from server data if available
  function initFromServerData() {
    if (window.RANKINGS_INITIAL_DATA) {
      rankingsData = window.RANKINGS_INITIAL_DATA;
    }
    if (window.RANKINGS_SELECTED) {
      selectedRankings = new Set(window.RANKINGS_SELECTED);
    }
  }

  // =========================================================================
  // Filter Parameter Building
  // =========================================================================

  function buildRankingFilterParams() {
    const p = new URLSearchParams();
    
    const searchEl = document.getElementById('ranking-search');
    const search = searchEl?.value?.trim();
    if (search) p.append('search', search);
    
    const providerEl = document.getElementById('provider-filter');
    const provider = providerEl?.value?.trim();
    if (provider) p.append('provider', provider);
    
    const priceEl = document.getElementById('price-filter');
    const price = priceEl?.value?.trim();
    if (price) p.append('max_price', price);
    
    const contextEl = document.getElementById('context-filter');
    const context = contextEl?.value?.trim();
    if (context) p.append('min_context', context);
    
    if (document.getElementById('filter-has-benchmarks')?.checked) {
      p.append('has_benchmarks', '1');
    }
    
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
    params.append('sort_by', currentSort.column);
    params.append('sort_dir', currentSort.direction);
    
    const url = '/rankings/api/rankings?' + params.toString();
    
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
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
          <td colspan="19" class="text-center text-danger py-4">
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
    if (benchmarkedEl) benchmarkedEl.textContent = stats.with_benchmarks || 0;
    
    const providersEl = document.getElementById('unique-providers');
    if (providersEl) providersEl.textContent = stats.unique_providers || 0;
  }

  // =========================================================================
  // Table Rendering — All 9 Ch.4 Benchmarks
  // =========================================================================

  function renderRankingsTable(models) {
    const tbody = document.getElementById('rankings-table-body');
    if (!tbody) return;
    
    if (!models || models.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="19" class="text-center text-muted py-4">
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
      
      // MSS & components (0-1 scale)
      const mss = model.mss_score;
      const adoption = model.adoption_score;
      const benchmark = model.benchmark_score;
      const cost = model.cost_efficiency_score;
      const access = model.accessibility_score;
      
      // Coding benchmarks
      const bfcl = model.bfcl_score;
      const webdev = model.webdev_elo;
      const lcb = model.livecodebench;
      const seal = model.seal_coding_score;
      const cac = model.canaicode_score;
      
      // Reasoning benchmarks
      const livebench = model.livebench_coding;
      const arc = model.arc_agi_score;
      const simp = model.simplebench_score;
      const gpqa = model.gpqa_score;
      
      return `
        <tr data-model-id="${esc(model.model_id)}" class="${isSelected ? 'table-primary' : ''}">
          <td>
            <label class="form-check mb-0">
              <input type="checkbox" class="form-check-input ranking-checkbox" 
                     value="${esc(model.model_id)}"
                     ${isSelected ? 'checked' : ''}
                     ${!isSelected && selectedRankings.size >= 10 ? 'disabled' : ''}
                     onchange="toggleRankingSelection(this)">
            </label>
          </td>
          <td class="text-muted">${rank}</td>
          <td>
            <span class="fw-medium">${esc(model.model_name || model.name || '')}</span>
            <small class="text-muted d-block">${esc(model.provider || '')}</small>
          </td>
          <td class="fw-bold ${mssClass(mss)}">${fmtPct(mss)}</td>
          <td class="border-start ${compClass(adoption)}">${fmtPct(adoption)}</td>
          <td class="${compClass(benchmark)}">${fmtPct(benchmark)}</td>
          <td class="${compClass(cost)}">${fmtPct(cost)}</td>
          <td class="${compClass(access)}">${fmtPct(access)}</td>
          <td class="border-start ${benchClass(bfcl, 80, 60)}">${fmtNum(bfcl, '%')}</td>
          <td class="${benchClass(webdev, 1300, 1100, true)}">${fmtElo(webdev)}</td>
          <td class="${benchClass(lcb, 50, 30)}">${fmtNum(lcb)}</td>
          <td class="${benchClass(seal, 80, 50)}">${fmtNum(seal)}</td>
          <td class="${benchClass(cac, 80, 50)}">${fmtNum(cac, '%')}</td>
          <td class="border-start ${benchClass(livebench, 60, 40)}">${fmtNum(livebench)}</td>
          <td class="${benchClass(arc, 50, 20)}">${fmtNum(arc, '%')}</td>
          <td class="${benchClass(simp, 50, 30)}">${fmtNum(simp, '%')}</td>
          <td class="${benchClass(gpqa, 60, 40)}">${fmtNum(gpqa, '%')}</td>
          <td class="border-start">${formatContext(model.context_length)}</td>
          <td>${formatPrice(model.price_per_million_input)}</td>
        </tr>
      `;
    }).join('');
    
    tbody.innerHTML = html;
    updateSortIndicators();
  }

  function esc(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // MSS is 0-1 scale
  function mssClass(v) {
    if (v == null) return 'text-muted';
    if (v >= 0.7) return 'text-success';
    if (v >= 0.5) return 'text-primary';
    if (v >= 0.3) return 'text-warning';
    return 'text-danger';
  }

  // MSS component scores are 0-1 scale
  function compClass(v) {
    if (v == null) return 'text-muted';
    if (v >= 0.8) return 'text-success';
    if (v >= 0.5) return 'text-info';
    if (v >= 0.3) return 'text-warning';
    return 'text-muted';
  }

  // Individual benchmark scores have varied scales
  function benchClass(v, high, med, isElo) {
    if (v == null) return 'text-muted';
    if (v >= high) return 'text-success';
    if (v >= med) return 'text-warning';
    return 'text-muted';
  }

  // Format 0-1 as percentage string "73.2%"
  function fmtPct(v) {
    if (v == null) return '<span class="text-muted">—</span>';
    return (v * 100).toFixed(1) + '%';
  }

  // Format a raw number with optional suffix
  function fmtNum(v, suffix) {
    if (v == null) return '<span class="text-muted">—</span>';
    return v.toFixed(1) + (suffix || '');
  }

  // Format Elo rating (integer)
  function fmtElo(v) {
    if (v == null) return '<span class="text-muted">—</span>';
    return v.toFixed(0);
  }

  function formatContext(value) {
    if (!value) return '—';
    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
    if (value >= 1000) return (value / 1000).toFixed(0) + 'K';
    return value.toLocaleString();
  }

  function formatPrice(value) {
    if (value == null) return '—';
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
    
    html += `<li class="page-item ${page === 1 ? 'disabled' : ''}">
      <a class="page-link" href="#" onclick="goToRankingsPage(${page - 1}); return false;">
        <i class="fa-solid fa-chevron-left"></i>
      </a>
    </li>`;
    
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
    if (row) row.classList.toggle('table-primary', selected);
  }

  function updateCheckboxStates() {
    const checkboxes = document.querySelectorAll('.ranking-checkbox');
    checkboxes.forEach(cb => {
      cb.disabled = !cb.checked && selectedRankings.size >= 10;
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
    if (summaryEl) summaryEl.style.display = count > 0 ? 'block' : 'none';
    if (clearBtn) clearBtn.style.display = count > 0 ? 'inline-block' : 'none';
    if (indicatorEl) indicatorEl.textContent = count > 0 ? `${count} selected` : '';
    
    if (listEl) {
      const names = Array.from(selectedRankings).slice(0, 3);
      const suffix = selectedRankings.size > 3 ? '...' : '';
      listEl.textContent = names.join(', ') + suffix;
    }
    
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
      checkboxes.forEach(cb => {
        if (selectedRankings.size < 10 && !cb.checked) {
          cb.checked = true;
          selectedRankings.add(cb.value);
          updateRowHighlight(cb.value, true);
        }
      });
    } else {
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
    const searchEl = document.getElementById('ranking-search');
    if (searchEl) searchEl.value = '';
    
    ['provider-filter', 'price-filter', 'context-filter'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    
    const hasBenchmarksEl = document.getElementById('filter-has-benchmarks');
    if (hasBenchmarksEl) hasBenchmarksEl.checked = true;
    
    const includeFreeEl = document.getElementById('filter-include-free');
    if (includeFreeEl) includeFreeEl.checked = true;
    
    applyRankingFilters();
  }

  // =========================================================================
  // Export Functions
  // =========================================================================

  function exportRankingsCSV() {
    const headers = [
      'Rank', 'Model', 'Provider', 'MSS', 'Adoption', 'Benchmark', 'Cost', 'Access',
      'BFCL', 'WebDev Elo', 'LiveCodeBench', 'SEAL', 'CanAiCode',
      'LiveBench', 'ARC-AGI', 'SimpleBench', 'GPQA',
      'Context', 'Price (In)', 'Price (Out)'
    ];
    const rows = rankingsData.map((m, i) => [
      i + 1,
      m.model_name || m.name || '',
      m.provider || '',
      m.mss_score != null ? (m.mss_score * 100).toFixed(1) : '',
      m.adoption_score != null ? (m.adoption_score * 100).toFixed(1) : '',
      m.benchmark_score != null ? (m.benchmark_score * 100).toFixed(1) : '',
      m.cost_efficiency_score != null ? (m.cost_efficiency_score * 100).toFixed(1) : '',
      m.accessibility_score != null ? (m.accessibility_score * 100).toFixed(1) : '',
      m.bfcl_score?.toFixed(1) || '',
      m.webdev_elo?.toFixed(0) || '',
      m.livecodebench?.toFixed(1) || '',
      m.seal_coding_score?.toFixed(1) || '',
      m.canaicode_score?.toFixed(1) || '',
      m.livebench_coding?.toFixed(1) || '',
      m.arc_agi_score?.toFixed(1) || '',
      m.simplebench_score?.toFixed(1) || '',
      m.gpqa_score?.toFixed(1) || '',
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
  window.exportRankingsCSV = exportRankingsCSV;
  window.saveSelectionForPipeline = saveSelectionForPipeline;
  window.goToComparison = goToComparison;
  window.goToRankingsPage = goToRankingsPage;
  window.changePerPage = changePerPage;
  window.sortRankings = sortRankings;

} // End of SINGLE EXECUTION BLOCK
