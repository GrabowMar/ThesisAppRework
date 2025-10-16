// Models page client logic
// ------------------------------------------------------------
// Responsibilities:
//  - Fetch full / filtered model lists
//  - Maintain client-side selection state
//  - Render models table
//  - Lazy‑load model detail modal content
//  - Basic filtering + statistics update
//
// Design notes:
//  - Keeps zero external dependencies beyond Fetch + (optional) Bootstrap modal
//  - All exported globals intentionally minimal so templates can call handlers
//  - If complexity grows: convert to small ES module & event delegation pattern
//  - Guarded so that if HTMX / dynamic navigation injects this script multiple
//    times we don't redeclare top-level let bindings (which causes errors)
// ------------------------------------------------------------

// models.js (post-trimming) – legacy bulk client table logic retained until fully replaced.
if (window.__MODELS_JS_LOADED__) {
  console.debug('models.js already loaded – skipping re‑init');
} else { // SINGLE EXECUTION BLOCK
  window.__MODELS_JS_LOADED__ = true;

/** @typedef {Object} EnrichedModel
 *  @property {string} slug
 *  @property {string} name
 *  @property {string} provider
 *  @property {number} input_price_per_1k
 *  @property {number} output_price_per_1k
 *  @property {number} context_length
 *  @property {Object|string|string[]} capabilities
 *  @property {string} [status]
 *  @property {number} [performance_score]
 */

  /** @type {string[]} */ let selectedModels = [];
  /** @type {EnrichedModel[]} */ let modelsData = [];
  // Placeholder for future sort state
  let currentSort = { field: null, direction: 'asc' };
  /** @type {number|undefined} */ let searchTimeout;
  // Pagination + source state
  let currentPage = 1;
  let perPage = 25;
  let totalPages = 1;
  let currentSource = 'db'; // 'db' | 'openrouter' | 'used'

  let modelsPageBootstrapped = false;
  let modelsPageSyncTriggered = false;

  function restoreUiStateFromStorage() {
    try {
      const st = JSON.parse(localStorage.getItem('models_ui_state') || '{}');
      if (st.perPage) perPage = st.perPage;
      if (st.source) currentSource = st.source;
      const perPageSelect = document.getElementById('models-per-page');
      if (perPageSelect) perPageSelect.value = String(perPage);
      updateSourceButtons();

      const savedSelection = JSON.parse(localStorage.getItem('models_selected') || '[]');
      if (Array.isArray(savedSelection)) {
        selectedModels = savedSelection;
        updateBatchSelectionCount();
      }
    } catch (e) {}
  }

  function bootstrapModelsPage() {
    if (!document.getElementById('models-table-body')) {
      return false;
    }

    const firstActivation = !modelsPageBootstrapped;
    restoreUiStateFromStorage();
    setupFilterHandlers();
    updateFilterSummaries();
    loadModelsPaginated();

    if (firstActivation && !modelsPageSyncTriggered) {
      modelsPageSyncTriggered = true;
      fetch('/api/models/sync', { method: 'POST' })
        .then(() => loadModelsPaginated())
        .catch(() => console.warn('Model sync failed, using cached data'));
    }

    modelsPageBootstrapped = true;
    return true;
  }

  function whenDocumentReady(fn) {
    if (document.readyState === 'loading') {
      const handler = () => {
        document.removeEventListener('DOMContentLoaded', handler);
        fn();
      };
      document.addEventListener('DOMContentLoaded', handler);
    } else {
      fn();
    }
  }

  function nodeContainsModelsTable(node) {
    if (!node) return false;
    if (node.id === 'models-table-body') return true;
    if (node.querySelector) {
      return Boolean(node.querySelector('#models-table-body'));
    }
    return false;
  }

  whenDocumentReady(() => {
    bootstrapModelsPage();
  });

  document.addEventListener('htmx:afterSwap', (event) => {
    if (nodeContainsModelsTable(event?.target)) {
      bootstrapModelsPage();
    }
  });

  document.addEventListener('htmx:load', (event) => {
    if (nodeContainsModelsTable(event?.detail?.elt)) {
      bootstrapModelsPage();
    }
  });

  // Handle pageshow (when using bfcache/back navigation) to force a refresh if stale > 60s
  window.addEventListener('pageshow', (ev) => {
    const isStale = ev?.persisted || (typeof performance !== 'undefined' && typeof performance.now === 'function' && performance.now() > 60000);
    if (isStale && document.getElementById('models-table-body')) {
      if (!bootstrapModelsPage()) {
        loadModelsPaginated();
      }
    }
  });

function getSelectValues(selectEl) {
  if (!selectEl) return [];
  return Array.from(selectEl.selectedOptions || [])
    .map(opt => opt.value)
    .filter(val => val !== undefined && val !== null && String(val).trim() !== '')
    .map(val => (typeof val === 'string' ? val.trim() : val));
}

function parseDataSelected(selectEl) {
  if (!selectEl || !selectEl.dataset || !selectEl.dataset.selected) return [];
  const raw = selectEl.dataset.selected;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.map(val => (typeof val === 'string' ? val.trim() : val)).filter(Boolean);
    }
    if (typeof parsed === 'string') {
      return parsed.split(',').map(val => val.trim()).filter(Boolean);
    }
  } catch (err) {
    return raw.split(',').map(val => val.trim()).filter(Boolean);
  }
  return [];
}

function storeSelectSelection(selectEl, values) {
  if (!selectEl || !selectEl.dataset) return;
  const sanitized = Array.isArray(values) ? values.filter(Boolean) : [];
  try {
    selectEl.dataset.selected = JSON.stringify(sanitized);
  } catch (err) {
    selectEl.dataset.selected = sanitized.join(',');
  }
  selectEl.dataset.selectionApplied = '1';
}

function syncSelectOptions(selectEl, options, placeholderText) {
  if (!selectEl || !Array.isArray(options)) return;

  const hasApplied = selectEl.dataset.selectionApplied === '1';
  const existingSelection = hasApplied ? getSelectValues(selectEl) : parseDataSelected(selectEl);
  const uniqueOptions = [...new Set(options.filter(Boolean))];
  const placeholder = placeholderText ?? null;

  selectEl.innerHTML = '';
  if (placeholder !== null) {
    const optAll = document.createElement('option');
    optAll.value = '';
    optAll.textContent = placeholder;
    selectEl.appendChild(optAll);
  }

  uniqueOptions.forEach(optionValue => {
    const optionEl = document.createElement('option');
    optionEl.value = optionValue;
    optionEl.textContent = optionValue.replace(/_/g, ' ');
    selectEl.appendChild(optionEl);
  });

  if (!selectEl.multiple) {
    const targetValue = existingSelection.length ? existingSelection[0] : '';
    selectEl.value = targetValue;
  } else {
    Array.from(selectEl.options).forEach(optionEl => {
      optionEl.selected = existingSelection.includes(optionEl.value);
    });
  }

  storeSelectSelection(selectEl, getSelectValues(selectEl));
}

function updateFilterOptions(filters) {
  if (!filters) return;

  const providerSelect = document.getElementById('provider-filter');
  if (providerSelect && Array.isArray(filters.providers)) {
    const placeholder = providerSelect.querySelector('option[value=""]')?.textContent || 'All';
    syncSelectOptions(providerSelect, filters.providers, placeholder);
  }

  const capabilitySelect = document.getElementById('capability-filter');
  if (capabilitySelect && Array.isArray(filters.capabilities)) {
    const placeholder = capabilitySelect.querySelector('option[value=""]')?.textContent || 'All';
    syncSelectOptions(capabilitySelect, filters.capabilities, placeholder);
  }

  updateFilterSummaries();
}

function onSelectFilterChange(event) {
  const target = event?.target;
  if (target) {
    storeSelectSelection(target, getSelectValues(target));
  }
  applyFilters();
}

function onPriceFilterChange() {
  applyFilters();
}

/** Debounced text search trigger */
function debounceSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(applyFilters, 300);
}
/** Clear search box and reapply filters */
function clearSearch() {
  const el = document.getElementById('model-search');
  if (el) el.value = '';
  applyFilters();
}
function persistUiState() {
  try { localStorage.setItem('models_ui_state', JSON.stringify({ perPage, source: currentSource })); } catch(e) {}
}
function setModelsSource(src) {
  if (!src || (src !== 'db' && src !== 'openrouter' && src !== 'used')) return;
  currentSource = src;
  currentPage = 1; // reset page
  updateSourceButtons();
  persistUiState();
  loadModelsPaginated();
}
function updateSourceButtons() {
  const dbBtn = document.getElementById('src-db');
  const usedBtn = document.getElementById('src-used');
  const orBtn = document.getElementById('src-openrouter');
  if (dbBtn && orBtn) {
    dbBtn.classList.toggle('active', currentSource === 'db');
    if (usedBtn) usedBtn.classList.toggle('active', currentSource === 'used');
    orBtn.classList.toggle('active', currentSource === 'openrouter');
  }
  const ind = document.getElementById('models-source-indicator');
  if (ind) {
    ind.textContent = currentSource === 'openrouter' ? 'OpenRouter catalog'
      : currentSource === 'used' ? 'Installed / used models'
      : 'All database models';
  }
}
function changePerPage(v) {
  const n = parseInt(v,10); if (!isNaN(n) && n>0) { perPage = n; currentPage = 1; persistUiState(); loadModelsPaginated(); }
}
/** Build current filter query params */
function buildFilterParams() {
  const p = new URLSearchParams();
  
  // Text search
  const q = document.getElementById('model-search')?.value.trim();
  if (q) p.append('search', q);
  
  // Basic filters
  const provider = document.getElementById('provider-filter')?.value;
  if (provider) p.append('provider', provider);
  
  const price = document.getElementById('price-filter')?.value;
  if (price) p.append('price', price);
  
  const context = document.getElementById('context-filter')?.value;
  if (context) p.append('context', context);
  
  // Checkbox filters
  if (document.getElementById('filter-has-apps')?.checked) {
    p.append('has_apps', '1');
  }
  if (document.getElementById('filter-installed-only')?.checked) {
    p.append('installed_only', '1');
  }
  if (document.getElementById('filter-free-models')?.checked) {
    p.append('free_models', '1');
  }
  
  // Feature support filters
  const featureFilters = document.querySelectorAll('.feature-filter:checked');
  featureFilters.forEach(cb => {
    p.append('features', cb.value);
  });
  
  // Modality filters
  const modalityFilters = document.querySelectorAll('.modality-filter:checked');
  modalityFilters.forEach(cb => {
    p.append('modalities', cb.value);
  });
  
  // Parameter support filters
  const paramFilters = document.querySelectorAll('.param-filter:checked');
  paramFilters.forEach(cb => {
    p.append('parameters', cb.value);
  });
  
  // Advanced filters
  const maxOutput = document.getElementById('max-output-filter')?.value;
  if (maxOutput) p.append('max_output', maxOutput);
  
  const tokenizer = document.getElementById('tokenizer-filter')?.value;
  if (tokenizer) p.append('tokenizer', tokenizer);
  
  const instructType = document.getElementById('instruct-type-filter')?.value;
  if (instructType) p.append('instruct_type', instructType);
  
  const costEfficiency = document.getElementById('cost-efficiency-filter')?.value;
  if (costEfficiency) p.append('cost_efficiency', costEfficiency);
  
  const safetyScore = document.getElementById('safety-score-filter')?.value;
  if (safetyScore) p.append('safety_score', safetyScore);
  
  return p;
}
function showLoading(s) {
  const sp = document.getElementById('loading-spinner');
  if (sp) sp.style.display = s ? 'block' : 'none';
}
/** Load complete model list (unfiltered) */
function loadModelsPaginated() {
  if (!window.fetch) return;
  showLoading(true);
  const params = buildFilterParams();
  params.append('page', String(currentPage));
  params.append('per_page', String(perPage));
  if (currentSource === 'used') {
    params.append('source', 'db');
    params.append('installed_only', '1');
  } else {
    params.append('source', currentSource);
  }
  
  const abortController = new AbortController();
  const timeoutId = setTimeout(() => abortController.abort(), 10000); // 10s timeout
  
  fetch('/api/models/paginated?' + params.toString(), {
    signal: abortController.signal
  })
    .then(r => {
      clearTimeout(timeoutId);
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
      return r.json();
    })
    .then(response => {
      // Unwrap standardized API envelope {success: true, data: {...}}
      const d = response.data || response;
      modelsData = d.models || [];
      updateStatistics(d.statistics || {});
      updateFilterOptions(d.filters || d.available_filters || null);
      totalPages = (d.pagination && d.pagination.total_pages) || 1;
      renderModelsTable(modelsData);
      renderPagination(d.pagination || {});
      
      // Re-setup handlers after table render
      setTimeout(() => setupFilterHandlers(), 100);
    })
    .catch(e => {
      if (e.name === 'AbortError') {
        console.warn('Request timed out');
      } else {
        console.error('Failed to load models:', e);
      }
    })
    .finally(() => {
      clearTimeout(timeoutId);
      showLoading(false);
    });
}
/** Fetch filtered models using current UI selections */
function applyFilters() { 
  currentPage = 1; 
  updateFilterSummaries();
  updateActiveFiltersCount();
  loadModelsPaginated(); 
}

/** Toggle advanced filters panel visibility */
function toggleAdvancedFilters() {
  const panel = document.getElementById('advanced-filters-panel');
  if (!panel) return;
  const isVisible = panel.style.display !== 'none';
  panel.style.display = isVisible ? 'none' : 'block';
  
  // Animate the toggle button
  const btn = document.querySelector('button[onclick="toggleAdvancedFilters()"]');
  if (btn) {
    const icon = btn.querySelector('i.fa-filter');
    if (icon) {
      icon.classList.toggle('fa-filter');
      icon.classList.toggle('fa-filter-circle-xmark');
    }
  }
}

/** Clear all filters and reset to defaults */
function clearAllFilters() {
  // Clear text search
  const searchInput = document.getElementById('model-search');
  if (searchInput) searchInput.value = '';
  
  // Reset select filters
  const selects = ['provider-filter', 'price-filter', 'context-filter', 'max-output-filter', 'tokenizer-filter', 'instruct-type-filter', 'cost-efficiency-filter', 'safety-score-filter'];
  selects.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  
  // Uncheck all checkbox filters
  const checkboxes = document.querySelectorAll(
    '.feature-filter, .modality-filter, .param-filter, #filter-has-apps, #filter-installed-only, #filter-free-models'
  );
  checkboxes.forEach(cb => cb.checked = false);
  
  // Apply filters to refresh
  applyFilters();
}

/** Count and display active filters */
function updateActiveFiltersCount() {
  let count = 0;
  
  // Count text search
  const searchVal = document.getElementById('model-search')?.value.trim();
  if (searchVal) count++;
  
  // Count select filters
  ['provider-filter', 'price-filter', 'context-filter', 'max-output-filter', 'tokenizer-filter', 'instruct-type-filter', 'cost-efficiency-filter', 'safety-score-filter'].forEach(id => {
    const el = document.getElementById(id);
    if (el && el.value) count++;
  });
  
  // Count checkbox filters
  const checkboxes = document.querySelectorAll(
    '.feature-filter:checked, .modality-filter:checked, .param-filter:checked, #filter-has-apps:checked, #filter-installed-only:checked, #filter-free-models:checked'
  );
  count += checkboxes.length;
  
  // Update badge
  const badge = document.getElementById('active-filters-count');
  if (badge) {
    if (count > 0) {
      badge.textContent = count;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }
}

/** Update KPI counters */
function updateStatistics(stats) {
  const tm = document.getElementById('total-models');
  if (tm) tm.textContent = stats.total_models || 0;
  const am = document.getElementById('active-models');
  if (am) am.textContent = stats.active_models || 0;
  const up = document.getElementById('unique-providers');
  if (up) up.textContent = stats.unique_providers || 0;
  const avg = document.querySelector('#avg-cost span');
  if (avg) avg.textContent = (stats.avg_cost_per_1k || 0).toFixed(4);
}
/** Normalize capabilities object into array of labels */
function toArrayCaps(v) {
  if (!v) return [];
  if (Array.isArray(v)) return v;
  if (typeof v === 'string') return [v];
  if (typeof v === 'object') {
    return Object.keys(v).filter(k => !!v[k]);
  }
  return [];
}
/** Render the main models table */
function renderModelsTable(models) {
  const tbody = document.getElementById('models-table-body');
  if (!tbody) return;
  if (!models.length) {
    tbody.innerHTML = '<tr><td colspan="12" class="text-center py-4 text-muted">No models found</td></tr>';
    return;
  }
  tbody.innerHTML = models.map(m => {
    const isFree = (+m.input_price_per_1k || 0) === 0 && (+m.output_price_per_1k || 0) === 0;
    const hasApps = m.has_applications || false;
    const isInstalled = m.installed || false;
    
    // Build badges - more compact
    const badges = [];
    if (isFree) badges.push('<span class="badge bg-success ms-2" title="Free"><i class="fas fa-gift"></i></span>');
    if (hasApps) badges.push('<span class="badge bg-info ms-1" title="Has Apps"><i class="fas fa-box"></i></span>');
    if (isInstalled) badges.push('<span class="badge bg-primary ms-1" title="Used"><i class="fas fa-check"></i></span>');
    
    // Modality - show all available input types from capabilities
    const caps_raw = m.capabilities_raw || {};
    const arch = caps_raw.architecture || {};
    const modality_str = arch.modality || '';
    const modalities = [];
    
    // Parse modality string (e.g., "text+image->text")
    if (modality_str.toLowerCase().includes('text')) {
      modalities.push('<span class="badge bg-azure text-white me-1" title="Text"><i class="fas fa-font"></i></span>');
    }
    if (modality_str.toLowerCase().includes('image') || m.supports_vision) {
      modalities.push('<span class="badge bg-info text-white me-1" title="Image/Vision"><i class="fas fa-eye"></i></span>');
    }
    if (modality_str.toLowerCase().includes('audio')) {
      modalities.push('<span class="badge bg-purple text-white me-1" title="Audio"><i class="fas fa-microphone"></i></span>');
    }
    if (modality_str.toLowerCase().includes('video')) {
      modalities.push('<span class="badge bg-pink text-white me-1" title="Video"><i class="fas fa-video"></i></span>');
    }
    
    const modalityHtml = modalities.length > 0 ? modalities.join('') : '<span class="badge bg-azure text-white"><i class="fas fa-font"></i></span>';
    
    // All available features - comprehensive display
    const features = [];
    if (m.supports_function_calling) features.push('<i class="fas fa-code text-primary fs-5" title="Function Calling"></i>');
    if (m.supports_vision) features.push('<i class="fas fa-eye text-info fs-5" title="Vision"></i>');
    if (m.supports_json_mode) features.push('<i class="fas fa-brackets-curly text-success fs-5" title="JSON Mode"></i>');
    if (m.supports_streaming) features.push('<i class="fas fa-stream text-warning fs-5" title="Streaming"></i>');
    
    const featuresHtml = features.length ? '<div class="d-flex gap-2 justify-content-center">' + features.join('') + '</div>' : '<span class="text-muted">—</span>';
    
    // Tokenizer type
    const tokenizer = arch.tokenizer || '';
    let tokenizerHtml = '<span class="text-muted small">—</span>';
    if (tokenizer) {
      const tokLower = tokenizer.toLowerCase();
      if (tokLower.includes('gpt') || tokLower.includes('claude')) {
        tokenizerHtml = '<span class="badge bg-primary-lt text-dark">GPT</span>';
      } else if (tokLower.includes('llama')) {
        tokenizerHtml = '<span class="badge bg-success-lt text-dark">Llama</span>';
      } else if (tokLower.includes('qwen')) {
        tokenizerHtml = '<span class="badge bg-warning-lt text-dark">Qwen</span>';
      } else if (tokLower.includes('mistral')) {
        tokenizerHtml = '<span class="badge bg-info-lt text-dark">Mistral</span>';
      } else {
        tokenizerHtml = `<span class="badge bg-secondary-lt text-dark" title="${tokenizer}">${tokenizer.substring(0, 6)}</span>`;
      }
    }
    
    // Instruction type - treat null/undefined as "base" model
    const instructType = arch.instruct_type;
    let instructHtml = '<span class="text-muted small">—</span>';
    if (instructType === null || instructType === undefined || instructType === '') {
      // No instruct_type means it's a base model (not instruction-tuned)
      instructHtml = '<span class="badge bg-secondary-lt text-dark">Base</span>';
    } else {
      const instLower = instructType.toLowerCase();
      if (instLower === 'none' || instLower === 'base') {
        instructHtml = '<span class="badge bg-secondary-lt text-dark">Base</span>';
      } else if (instLower.includes('chat')) {
        instructHtml = '<span class="badge bg-info-lt text-dark"><i class="fas fa-comments"></i></span>';
      } else if (instLower.includes('instruct')) {
        instructHtml = '<span class="badge bg-primary-lt text-dark"><i class="fas fa-terminal"></i></span>';
      } else {
        instructHtml = `<span class="badge bg-secondary-lt text-dark">${instructType.substring(0, 4)}</span>`;
      }
    }
    
    // Cost efficiency display
    const costEff = m.cost_efficiency || 0;
    let costEffHtml = '<span class="text-muted">—</span>';
    if (costEff > 0) {
      const effPercent = (costEff * 100).toFixed(0);
      let effColor = 'danger';
      let effIcon = 'fa-arrow-down';
      if (costEff >= 0.7) { effColor = 'success'; effIcon = 'fa-arrow-up'; }
      else if (costEff >= 0.4) { effColor = 'warning'; effIcon = 'fa-minus'; }
      costEffHtml = `<span class="badge bg-${effColor}-lt text-dark" title="Cost Efficiency: ${effPercent}%">
        <i class="fas ${effIcon}"></i> ${effPercent}%
      </span>`;
    }
    
    // Format prices per 1M tokens
    const inputPrice = ((m.input_price_per_1k || 0) * 1000).toFixed(2);
    const outputPrice = ((m.output_price_per_1k || 0) * 1000).toFixed(2);
    const priceHtml = isFree 
      ? '<span class="badge bg-success text-white fw-bold">Free</span>' 
      : `<div class="text-nowrap"><span class="text-dark fw-semibold">$${inputPrice}</span><span class="text-muted mx-1">/</span><span class="text-dark fw-semibold">$${outputPrice}</span></div>`;
    
    // Context and max output - use dark badges for visibility
    const contextHtml = m.context_length ? `<span class="badge bg-light text-dark fw-bold">${(m.context_length / 1000).toFixed(0)}K</span>` : '<span class="text-muted">—</span>';
    const maxOutputHtml = m.max_output_tokens ? `<span class="badge bg-light text-dark fw-bold">${(m.max_output_tokens / 1000).toFixed(0)}K</span>` : '<span class="text-muted">—</span>';
    
    // Provider with count badge - more compact
    const providerCount = m.provider_count || 0;
    const providerHtml = providerCount > 1 
      ? `<span class="badge bg-azure cursor-pointer text-white" onclick="showProviderDropdown('${m.slug}', this)" title="${providerCount} providers">
           ${m.provider || ''} <span class="badge badge-sm bg-white text-azure ms-1">${providerCount}</span>
         </span>`
      : `<span class="badge bg-azure text-white">${m.provider || ''}</span>`;
    
    // Variant count badge (if multiple pricing tiers exist) - more visible
    const variantCount = m.variant_count || 0;
    const variantBadge = variantCount > 1
      ? `<span class="badge bg-purple cursor-pointer text-white ms-1" onclick="showVariantDropdown('${m.slug}', this)" title="${variantCount} pricing tiers">
           <i class="fas fa-tags me-1"></i>${variantCount}
         </span>`
      : '';
    
    return `<tr>
      <td><input type="checkbox" class="form-check-input m-0" onchange="toggleModelSelection('${m.slug}')" aria-label="Select" ${selectedModels.includes(m.slug) ? 'checked' : ''}></td>
      <td>
        <div class="d-flex align-items-center">
          <strong>${m.name}</strong>
          ${badges.join('')}
          ${variantBadge}
        </div>
      </td>
      <td>${providerHtml}</td>
      <td class="text-center">${modalityHtml}</td>
      <td class="text-center">${tokenizerHtml}</td>
      <td class="text-center">${instructHtml}</td>
      <td class="text-end">${priceHtml}</td>
      <td class="text-center">${contextHtml}</td>
      <td class="text-center">${maxOutputHtml}</td>
      <td class="text-center">${costEffHtml}</td>
      <td class="text-center">${featuresHtml}</td>
      <td>
        <div class="btn-group btn-group-sm" role="group">
          <button class="btn btn-ghost-primary" onclick="viewModelDetails('${m.slug}')" title="View details">
            <i class="fas fa-eye"></i>
          </button>
          <button class="btn btn-ghost-info" onclick="openOnOpenRouter('${m.model_id || m.slug}')" title="View on OpenRouter">
            <i class="fas fa-external-link-alt"></i>
          </button>
        </div>
      </td>
    </tr>`;
  }).join('');
}
/** Toggle inclusion of a single model in bulk selection */
function toggleModelSelection(slug) {
  const i = selectedModels.indexOf(slug);
  if (i > -1) selectedModels.splice(i, 1); else selectedModels.push(slug);
  updateBatchSelectionCount();
  updateCompareButton();
  try { localStorage.setItem('models_selected', JSON.stringify(selectedModels)); } catch(e) {}
}

/** Update compare button state */
function updateCompareButton() {
  const btn = document.getElementById('compare-models-btn');
  if (btn) {
    btn.disabled = selectedModels.length < 2;
    if (selectedModels.length >= 2) {
      btn.classList.remove('btn-secondary');
      btn.classList.add('btn-primary');
    } else {
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-secondary');
    }
  }
}

/** Compare selected models */
function compareSelectedModels() {
  if (selectedModels.length < 2) {
    alert('Please select at least 2 models to compare');
    return;
  }
  if (selectedModels.length > 8) {
    alert('Maximum 8 models can be compared at once');
    return;
  }
  window.location.href = `/models/comparison?models=${selectedModels.join(',')}`;
}
/** Master checkbox: select / deselect all visible models */
function toggleSelectAll() {
  const master = document.getElementById('select-all-models');
  const checkboxes = [...document.querySelectorAll('#models-table-body input[type=checkbox]')];
  checkboxes.forEach(cb => {
    const match = cb.getAttribute('onchange').match(/'(.*)'/);
    const slug = match ? match[1] : null;
    if (!slug) return;
    cb.checked = master.checked;
    const idx = selectedModels.indexOf(slug);
    if (master.checked && idx === -1) selectedModels.push(slug);
    if (!master.checked && idx > -1) selectedModels.splice(idx, 1);
  });
  updateBatchSelectionCount();
  updateCompareButton();
  try { localStorage.setItem('models_selected', JSON.stringify(selectedModels)); } catch(e) {}
}
/** Navigate to model details page */
function viewModelDetails(slug) {
  window.location.href = `/models/${encodeURIComponent(slug)}`;
}
function refreshModels() { loadModelsPaginated(); }
function syncFromOpenRouter() {
  const btn = document.querySelector('button[onclick="syncFromOpenRouter()"]');
  if (!btn) return;
  
  // Store original state
  const originalHTML = btn.innerHTML;
  const originalDisabled = btn.disabled;
  
  // Set loading state
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i><span class="d-none d-md-inline">Syncing...</span>';
  
  fetch('/api/models/load-openrouter', { 
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  })
    .then(r => {
      if (!r.ok) {
        return r.json().then(err => { throw new Error(err.message || `HTTP ${r.status}`); });
      }
      return r.json();
    })
    .then(result => {
      // Show success message
      const message = `Successfully synced ${result.upserted || 0} models from OpenRouter`;
      
      // Create temporary success indicator
      btn.innerHTML = '<i class="fas fa-check text-success me-1"></i><span class="d-none d-md-inline">Synced!</span>';
      
      // Show a brief success notification (you can customize this)
      if (window.bootstrap && window.bootstrap.Toast) {
        // If Bootstrap toasts are available
        const toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center text-bg-success border-0';
        toastEl.setAttribute('role', 'alert');
        toastEl.innerHTML = `
          <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
          </div>
        `;
        document.body.appendChild(toastEl);
        const toast = new bootstrap.Toast(toastEl);
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
      } else {
        // Fallback to alert
        alert(message);
      }
      
      // Refresh the models table to show new data
      loadModelsPaginated();
      
      // Reset button after a delay
      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.disabled = originalDisabled;
      }, 2000);
    })
    .catch(err => {
      console.error('Failed to sync from OpenRouter:', err);
      
      // Show error state
      btn.innerHTML = '<i class="fas fa-exclamation-triangle text-danger me-1"></i><span class="d-none d-md-inline">Error</span>';
      
      // Show error message
      alert(`Failed to sync from OpenRouter: ${err.message || 'Unknown error'}`);
      
      // Reset button after a delay
      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.disabled = originalDisabled;
      }, 3000);
    });
}

function rescanUsedModels() {
  const btn = document.querySelector('button[onclick="rescanUsedModels()"]');
  if (!btn) return;
  
  // Confirm action
  if (!confirm('This will reset all "used" flags and rescan the generated/apps folder. Continue?')) {
    return;
  }
  
  // Store original state
  const originalHTML = btn.innerHTML;
  const originalDisabled = btn.disabled;
  
  // Set loading state
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i><span class="d-none d-md-inline">Scanning...</span>';
  
  fetch('/api/models/rescan-used', { 
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  })
    .then(r => {
      if (!r.ok) {
        return r.json().then(err => { throw new Error(err.message || `HTTP ${r.status}`); });
      }
      return r.json();
    })
    .then(result => {
      const data = result.data || result;
      
      // Build detailed message
      let message = `Rescan complete:\n`;
      message += `• Reset: ${data.reset || 0} models\n`;
      message += `• Found: ${data.scanned || 0} model folders\n`;
      message += `• Marked as used: ${data.marked || 0} models\n`;
      
      if (data.apps_folder_empty) {
        message += `\n⚠️ The generated/apps folder is empty!`;
      }
      
      // Show success message
      btn.innerHTML = '<i class="fas fa-check text-success me-1"></i><span class="d-none d-md-inline">Rescanned!</span>';
      alert(message);
      
      // Refresh the models table to show updated data
      loadModelsPaginated();
      
      // Reset button after a delay
      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.disabled = originalDisabled;
      }, 2000);
    })
    .catch(err => {
      console.error('Failed to rescan used models:', err);
      
      // Show error state
      btn.innerHTML = '<i class="fas fa-exclamation-triangle text-danger me-1"></i><span class="d-none d-md-inline">Error</span>';
      
      // Show error message
      alert(`Failed to rescan used models: ${err.message || 'Unknown error'}`);
      
      // Reset button after a delay
      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.disabled = originalDisabled;
      }, 3000);
    });
}

function useSelectedForScaffolding() {
  // Get currently selected models
  if (!selectedModels || selectedModels.length === 0) {
    alert('Please select at least one model');
    return;
  }
  
  // Store in localStorage for cross-page access
  try {
    localStorage.setItem('selected_scaffolding_models', JSON.stringify(selectedModels));
  } catch (e) {
    console.warn('Could not store models in localStorage:', e);
  }
  
  // Navigate to sample generator page, scaffolding tab
  window.location.href = '/sample-generator#scaffolding-tab';
}

function openComparison() {
  // Load from current in-memory selection (fallback to localStorage)
  if (!selectedModels.length) {
    try { const stored = JSON.parse(localStorage.getItem('models_selected')||'[]'); if(Array.isArray(stored)) selectedModels = stored; } catch(e) {}
  }
  const unique = [...new Set(selectedModels)];
  const param = unique.slice(0,20).join(','); // cap to avoid huge URLs
  try { localStorage.setItem('models_selected', JSON.stringify(unique)); } catch(e) {}
  const url = '/models/comparison' + (param? ('?models='+encodeURIComponent(param)):'');
  window.location.href = url;
}
function exportModelsData() { window.open('/api/models/export?format=json', '_blank'); }
/** Mark locally installed models (server heuristic) */
function tagInstalledModels() {
  fetch('/api/models/mark-installed', { method: 'POST' })
    .then(r => r.json())
    .then(res => { alert(`Updated ${res.updated || 0} models.`); loadModelsPaginated(); })
    .catch(() => alert('Tag installed failed'));
}
function setupFilterHandlers() {
  const providerSelect = document.getElementById('provider-filter');
  if (providerSelect) {
    providerSelect.removeEventListener('change', onSelectFilterChange);
    providerSelect.addEventListener('change', onSelectFilterChange);
  }

  const capabilitySelect = document.getElementById('capability-filter');
  if (capabilitySelect) {
    capabilitySelect.removeEventListener('change', onSelectFilterChange);
    capabilitySelect.addEventListener('change', onSelectFilterChange);
  }

  const priceFilter = document.getElementById('price-filter');
  if (priceFilter) {
    priceFilter.removeEventListener('change', onPriceFilterChange);
    priceFilter.addEventListener('change', onPriceFilterChange);
  }

  const searchInput = document.getElementById('model-search');
  if (searchInput) {
    searchInput.removeEventListener('input', debounceSearch);
    searchInput.addEventListener('input', debounceSearch);
  }
}

function updateFilterSummaries() {
  const providerSelect = document.getElementById('provider-filter');
  const providerLabel = document.getElementById('provider-filter-label');
  if (providerSelect && providerLabel) {
    const selectedOption = providerSelect.value && providerSelect.selectedOptions.length
      ? providerSelect.selectedOptions[0].textContent
      : null;
    providerLabel.textContent = selectedOption ? `Provider: ${selectedOption}` : 'Providers';
  }

  const capabilitySelect = document.getElementById('capability-filter');
  const capabilityLabel = document.getElementById('capability-filter-label');
  if (capabilitySelect && capabilityLabel) {
    const selectedCap = capabilitySelect.value && capabilitySelect.selectedOptions.length
      ? capabilitySelect.selectedOptions[0].textContent
      : null;
    capabilityLabel.textContent = selectedCap ? `Capability: ${selectedCap}` : 'Capabilities';
  }
}
function renderPagination(p) {
  const ul = document.getElementById('models-pagination');
  const summary = document.getElementById('models-page-summary');
  if (!ul) return;
  const page = p.current_page || 1;
  const pages = p.total_pages || 1;
  currentPage = page; totalPages = pages;
  if (summary) {
    const total = p.total_items || modelsData.length;
    const start = (page-1)* (p.per_page||perPage) + 1;
    const end = Math.min(start + (p.per_page||perPage) -1, total);
    summary.textContent = `Showing ${start}-${end} of ${total}`;
  }
  const mk = (label, targetPage, disabled=false, active=false) => `<li class="page-item ${disabled?'disabled':''} ${active?'active':''}"><a class="page-link" href="#" onclick="return gotoModelsPage(${targetPage})">${label}</a></li>`;
  let html = '';
  html += mk('&laquo;', page-1, page<=1);
  // show limited window
  const windowSize = 5;
  let startP = Math.max(1, page - Math.floor(windowSize/2));
  let endP = startP + windowSize - 1;
  if (endP > pages) { endP = pages; startP = Math.max(1, endP - windowSize +1); }
  for (let i=startP;i<=endP;i++) html += mk(String(i), i, false, i===page);
  html += mk('&raquo;', page+1, page>=pages);
  ul.innerHTML = html;
}
function gotoModelsPage(p) {
  if (p<1 || p> totalPages) return false;
  currentPage = p;
  loadModelsPaginated();
  return false;
}
function updateBatchSelectionCount() {
  const el = document.getElementById('selected-models-count');
  if (el) el.textContent = selectedModels.length;
  const indicator = document.getElementById('models-selection-indicator');
  if (indicator) {
    if (selectedModels.length > 0) {
      indicator.textContent = `${selectedModels.length} selected`;
      indicator.className = 'text-primary small fw-bold';
    } else {
      indicator.textContent = '';
      indicator.className = 'text-muted small';
    }
  }
}

// Batch operation functions
function batchExportJSON() {
  if (!selectedModels.length) {
    alert('No models selected');
    return;
  }
  const params = new URLSearchParams();
  selectedModels.forEach(slug => params.append('models', slug));
  params.append('format', 'json');
  window.open('/api/models/export?' + params.toString(), '_blank');
}

function batchExportCSV() {
  if (!selectedModels.length) {
    alert('No models selected');
    return;
  }
  const params = new URLSearchParams();
  selectedModels.forEach(slug => params.append('models', slug));
  params.append('format', 'csv');
  window.open('/api/models/export?' + params.toString(), '_blank');
}

function batchExportComparison() {
  if (!selectedModels.length) {
    alert('No models selected');
    return;
  }
  openComparison();
}

function batchMarkInstalled() {
  if (!selectedModels.length) {
    alert('No models selected');
    return;
  }
  
  if (!confirm(`Mark ${selectedModels.length} models as installed?`)) {
    return;
  }
  
  const resultDiv = document.getElementById('batch-operation-result');
  if (resultDiv) resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>Processing...';
  
  fetch('/api/models/batch-mark-installed', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ models: selectedModels })
  })
  .then(r => r.json())
  .then(res => {
    if (resultDiv) {
      if (res.success) {
        resultDiv.innerHTML = `<div class="alert alert-success mb-0">✓ Updated ${res.updated || 0} models</div>`;
        loadModelsPaginated();
      } else {
        resultDiv.innerHTML = `<div class="alert alert-danger mb-0">✗ ${res.error || 'Operation failed'}</div>`;
      }
    }
  })
  .catch(err => {
    if (resultDiv) resultDiv.innerHTML = `<div class="alert alert-danger mb-0">✗ ${err.message || 'Network error'}</div>`;
  });
}

function batchUpdateStatus() {
  if (!selectedModels.length) {
    alert('No models selected');
    return;
  }
  
  const newStatus = prompt('Enter new status for selected models:', 'active');
  if (!newStatus) return;
  
  const resultDiv = document.getElementById('batch-operation-result');
  if (resultDiv) resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>Updating status...';
  
  fetch('/api/models/batch-update-status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ models: selectedModels, status: newStatus })
  })
  .then(r => r.json())
  .then(res => {
    if (resultDiv) {
      if (res.success) {
        resultDiv.innerHTML = `<div class="alert alert-success mb-0">✓ Updated ${res.updated || 0} models to '${newStatus}'</div>`;
        loadModelsPaginated();
      } else {
        resultDiv.innerHTML = `<div class="alert alert-danger mb-0">✗ ${res.error || 'Update failed'}</div>`;
      }
    }
  })
  .catch(err => {
    if (resultDiv) resultDiv.innerHTML = `<div class="alert alert-danger mb-0">✗ ${err.message || 'Network error'}</div>`;
  });
}

/**
 * Show provider dropdown modal with list of providers for a model
 */
function showProviderDropdown(slug, element) {
  // Prevent event bubbling
  if (event) event.stopPropagation();
  
  // Show loading state
  const providerModal = document.createElement('div');
  providerModal.id = 'provider-modal';
  providerModal.className = 'modal modal-blur fade show';
  providerModal.style.display = 'block';
  providerModal.innerHTML = `
    <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Model Providers</h5>
          <button type="button" class="btn-close" onclick="closeProviderModal()"></button>
        </div>
        <div class="modal-body">
          <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Loading providers...</span>
            </div>
            <p class="text-muted mt-2">Fetching provider information...</p>
          </div>
        </div>
      </div>
    </div>
  `;
  
  // Add modal backdrop
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop fade show';
  backdrop.id = 'provider-modal-backdrop';
  
  document.body.appendChild(backdrop);
  document.body.appendChild(providerModal);
  document.body.classList.add('modal-open');
  
  // Fetch provider data
  fetch(`/api/models/${slug}/providers`)
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        throw new Error(data.error);
      }
      
      const providers = data.providers || [];
      if (providers.length === 0) {
        providerModal.querySelector('.modal-body').innerHTML = `
          <div class="alert alert-info mb-0">
            <i class="fas fa-info-circle me-2"></i>
            No provider information available for this model.
          </div>
        `;
        return;
      }
      
      // Build provider table
      const tableHtml = `
        <div class="mb-3">
          <h6 class="fw-bold">${data.model_name}</h6>
          <p class="text-muted small mb-0">${data.model_id}</p>
        </div>
        <div class="table-responsive">
          <table class="table table-vcenter card-table table-sm">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Region</th>
                <th>Latency</th>
                <th>Throughput</th>
                <th class="text-end">Context</th>
                <th class="text-end">Max Output</th>
                <th class="text-end">Input Price</th>
                <th class="text-end">Output Price</th>
              </tr>
            </thead>
            <tbody>
              ${providers.map(p => `
                <tr>
                  <td>
                    <span class="badge bg-azure-lt">${p.name || 'Unknown'}</span>
                    ${p.uptime ? `<span class="badge badge-outline text-green ms-1" title="Uptime">${(p.uptime * 100).toFixed(1)}%</span>` : ''}
                  </td>
                  <td><span class="text-muted">${p.region || '—'}</span></td>
                  <td><span class="text-muted">${p.latency ? `${p.latency.toFixed(2)}s` : '—'}</span></td>
                  <td><span class="text-muted">${p.throughput ? `${p.throughput.toFixed(1)} tps` : '—'}</span></td>
                  <td class="text-end">${p.context_length ? `<span class="badge badge-outline">${(p.context_length / 1000).toFixed(0)}K</span>` : '—'}</td>
                  <td class="text-end">${p.max_completion_tokens ? `<span class="badge badge-outline">${(p.max_completion_tokens / 1000).toFixed(0)}K</span>` : '—'}</td>
                  <td class="text-end">${p.input_price ? `<span class="text-muted small">$${(p.input_price * 1000000).toFixed(2)}</span>` : '—'}</td>
                  <td class="text-end">${p.output_price ? `<span class="text-muted small">$${(p.output_price * 1000000).toFixed(2)}</span>` : '—'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        <div class="alert alert-info mt-3 mb-0">
          <i class="fas fa-info-circle me-2"></i>
          OpenRouter automatically routes requests to the best available provider based on latency, throughput, and pricing.
        </div>
      `;
      
      providerModal.querySelector('.modal-body').innerHTML = tableHtml;
    })
    .catch(err => {
      providerModal.querySelector('.modal-body').innerHTML = `
        <div class="alert alert-danger mb-0">
          <i class="fas fa-exclamation-triangle me-2"></i>
          Error loading providers: ${err.message}
        </div>
      `;
    });
}

/**
 * Close provider modal
 */
function closeProviderModal() {
  const modal = document.getElementById('provider-modal');
  const backdrop = document.getElementById('provider-modal-backdrop');
  if (modal) modal.remove();
  if (backdrop) backdrop.remove();
  document.body.classList.remove('modal-open');
}

/**
 * Show variant dropdown modal with list of pricing tiers for a model
 */
function showVariantDropdown(slug, element) {
  // Prevent event bubbling
  if (event) event.stopPropagation();
  
  // Show loading state
  const variantModal = document.createElement('div');
  variantModal.id = 'variant-modal';
  variantModal.className = 'modal modal-blur fade show';
  variantModal.style.display = 'block';
  variantModal.innerHTML = `
    <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Pricing Tiers</h5>
          <button type="button" class="btn-close" onclick="closeVariantModal()"></button>
        </div>
        <div class="modal-body">
          <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Loading variants...</span>
            </div>
            <p class="text-muted mt-2">Fetching pricing information...</p>
          </div>
        </div>
      </div>
    </div>
  `;
  
  // Add modal backdrop
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop fade show';
  backdrop.id = 'variant-modal-backdrop';
  
  document.body.appendChild(backdrop);
  document.body.appendChild(variantModal);
  document.body.classList.add('modal-open');
  
  // Fetch variant data
  fetch(`/api/models/${slug}/variants`)
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        throw new Error(data.error);
      }
      
      const variants = data.variants || [];
      if (variants.length === 0) {
        variantModal.querySelector('.modal-body').innerHTML = `
          <div class="alert alert-info mb-0">
            <i class="fas fa-info-circle me-2"></i>
            No variant information available for this model.
          </div>
        `;
        return;
      }
      
      // Build variant table
      const tableHtml = `
        <div class="mb-3">
          <h6 class="fw-bold">Available Pricing Tiers</h6>
          <p class="text-muted small mb-0">Base Model: ${data.base_model_id || 'N/A'}</p>
        </div>
        <div class="table-responsive">
          <table class="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Tier</th>
                <th class="text-end">Input (per 1M)</th>
                <th class="text-end">Output (per 1M)</th>
                <th class="text-end">Context</th>
                <th class="text-end">Max Output</th>
              </tr>
            </thead>
            <tbody>
              ${variants.map(v => `
                <tr>
                  <td>
                    <div>
                      <strong>${v.name}</strong>
                      ${v.is_free ? '<span class="badge bg-success-lt ms-2">Free</span>' : ''}
                    </div>
                    <div class="text-muted small">${v.model_id}</div>
                  </td>
                  <td>
                    ${v.variant_suffix ? `<span class="badge bg-purple-lt">${v.variant_suffix}</span>` : '<span class="text-muted">Standard</span>'}
                  </td>
                  <td class="text-end">
                    ${v.is_free ? '<span class="text-success fw-bold">Free</span>' : `<span class="text-muted">$${v.input_price_per_1m.toFixed(2)}</span>`}
                  </td>
                  <td class="text-end">
                    ${v.is_free ? '<span class="text-success fw-bold">Free</span>' : `<span class="text-muted">$${v.output_price_per_1m.toFixed(2)}</span>`}
                  </td>
                  <td class="text-end">
                    ${v.context_window ? `<span class="badge badge-outline">${(v.context_window / 1000).toFixed(0)}K</span>` : '—'}
                  </td>
                  <td class="text-end">
                    ${v.max_output_tokens ? `<span class="badge badge-outline">${(v.max_output_tokens / 1000).toFixed(0)}K</span>` : '—'}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        <div class="alert alert-info mt-3 mb-0">
          <i class="fas fa-info-circle me-2"></i>
          Some models offer multiple pricing tiers with different features, rate limits, or quality levels.
        </div>
      `;
      
      variantModal.querySelector('.modal-body').innerHTML = tableHtml;
    })
    .catch(err => {
      variantModal.querySelector('.modal-body').innerHTML = `
        <div class="alert alert-danger mb-0">
          <i class="fas fa-exclamation-triangle me-2"></i>
          Error loading variants: ${err.message}
        </div>
      `;
    });
}

/**
 * Close variant modal
 */
function closeVariantModal() {
  const modal = document.getElementById('variant-modal');
  const backdrop = document.getElementById('variant-modal-backdrop');
  if (modal) modal.remove();
  if (backdrop) backdrop.remove();
  document.body.classList.remove('modal-open');
}

/**
 * Open model page on OpenRouter in new tab
 */
function openOnOpenRouter(modelId) {
  // Convert slug format to OpenRouter model ID if needed
  let openrouterModelId = modelId;
  
  // If it's a slug format (with underscores), convert to forward slash
  if (modelId && modelId.includes('_') && !modelId.includes('/')) {
    openrouterModelId = modelId.replace('_', '/');
  }
  
  // OpenRouter model URL format
  const url = `https://openrouter.ai/models/${encodeURIComponent(openrouterModelId)}`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

function batchDelete() {
  if (!selectedModels.length) {
    alert('No models selected');
    return;
  }
  
  if (!confirm(`Delete ${selectedModels.length} models? This action cannot be undone.`)) {
    return;
  }
  
  const resultDiv = document.getElementById('batch-operation-result');
  if (resultDiv) resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>Deleting models...';
  
  fetch('/api/models/batch-delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ models: selectedModels })
  })
  .then(r => r.json())
  .then(res => {
    if (resultDiv) {
      if (res.success) {
        resultDiv.innerHTML = `<div class="alert alert-success mb-0">✓ Deleted ${res.deleted || 0} models</div>`;
        selectedModels = []; // Clear selection
        updateBatchSelectionCount();
        loadModelsPaginated();
      } else {
        resultDiv.innerHTML = `<div class="alert alert-danger mb-0">✗ ${res.error || 'Delete failed'}</div>`;
      }
    }
  })
  .catch(err => {
    if (resultDiv) resultDiv.innerHTML = `<div class="alert alert-danger mb-0">✗ ${err.message || 'Network error'}</div>`;
  });
}

// Expose functions if needed globally
  window.debounceSearch = debounceSearch;
  window.clearSearch = clearSearch;
  window.toggleModelSelection = toggleModelSelection;
  window.toggleSelectAll = toggleSelectAll;
  window.viewModelDetails = viewModelDetails;
  window.refreshModels = refreshModels;
  window.syncFromOpenRouter = syncFromOpenRouter;
  window.openComparison = openComparison;
  window.exportModelsData = exportModelsData;
  window.tagInstalledModels = tagInstalledModels;
  window.setModelsSource = setModelsSource;
  window.changePerPage = changePerPage;
  window.showProviderDropdown = showProviderDropdown;
  window.closeProviderModal = closeProviderModal;
  window.showVariantDropdown = showVariantDropdown;
  window.closeVariantModal = closeVariantModal;
  window.openOnOpenRouter = openOnOpenRouter;
  window.compareSelectedModels = compareSelectedModels;
  window.gotoModelsPage = gotoModelsPage;
  window.updateBatchSelectionCount = updateBatchSelectionCount;
  window.setupFilterHandlers = setupFilterHandlers;
  window.updateFilterSummaries = updateFilterSummaries;
  window.batchExportJSON = batchExportJSON;
  window.batchExportCSV = batchExportCSV;
  window.batchExportComparison = batchExportComparison;
  window.batchMarkInstalled = batchMarkInstalled;
  window.batchUpdateStatus = batchUpdateStatus;
  window.batchDelete = batchDelete;
  window.setupFilterHandlers = setupFilterHandlers;
  window.updateFilterSummaries = updateFilterSummaries;
}
