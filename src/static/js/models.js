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

  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('models-table-body')) {
      // Attempt to restore persisted UI state
      try {
        const st = JSON.parse(localStorage.getItem('models_ui_state')||'{}');
        if (st.perPage) perPage = st.perPage;
        if (st.source) currentSource = st.source;
        const sel = document.getElementById('models-per-page');
        if (sel) sel.value = String(perPage);
        updateSourceButtons();
      } catch(e) {}
      
      // Start loading models immediately without waiting for sync
      loadModelsPaginated();
      
      // Sync models in background (don't wait for it)
      fetch('/api/models/sync', { method: 'POST' })
        .then(() => {
          // Refresh the display after sync completes
          loadModelsPaginated();
        })
        .catch(() => {
          // If sync fails, we still have the initial load
          console.warn('Model sync failed, using cached data');
        });
      
      setupMultiselects();
    }
  });

  // Handle pageshow (when using bfcache/back navigation) to force a refresh if stale > 60s
  window.addEventListener('pageshow', (ev) => {
    if (ev.persisted || (performance && performance.now() > 60000)) {
      if (document.getElementById('models-table-body')) {
        loadModelsPaginated();
      }
    }
  });

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
  const q = document.getElementById('model-search')?.value.trim();
  if (q) p.append('search', q);
  document.querySelectorAll('.provider-option:checked').forEach(el => p.append('providers', el.value));
  document.querySelectorAll('.capability-option:checked').forEach(el => p.append('capabilities', el.value));
  const price = document.getElementById('price-filter')?.value;
  if (price) p.append('price', price);
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
  fetch('/api/models/paginated?' + params.toString())
    .then(r => r.json())
    .then(d => {
      modelsData = d.models || [];
      updateStatistics(d.statistics || {});
      totalPages = (d.pagination && d.pagination.total_pages) || 1;
      renderModelsTable(modelsData);
      renderPagination(d.pagination || {});
    })
    .catch(e => console.error(e))
    .finally(() => showLoading(false));
}
/** Fetch filtered models using current UI selections */
function applyFilters() { currentPage = 1; loadModelsPaginated(); }
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
    tbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-muted">No models found</td></tr>';
    return;
  }
  tbody.innerHTML = models.map(m => {
    const caps = toArrayCaps(m.capabilities);
    const isFree = (+m.input_price_per_1k || 0) === 0 && (+m.output_price_per_1k || 0) === 0;
    const hasApps = m.has_applications || false;
    const badgesHtml = [
      isFree ? '<span class="badge bg-success ms-1">free</span>' : '',
      hasApps ? '<span class="badge bg-info ms-1">used</span>' : ''
    ].filter(badge => badge).join('');
    
    return `<tr>
      <td><input type="checkbox" onchange="toggleModelSelection('${m.slug}')" ${selectedModels.includes(m.slug) ? 'checked' : ''}></td>
      <td><strong>${m.name}</strong> ${badgesHtml}</td>
      <td>${m.provider || ''}</td>
      <td>${caps.slice(0,2).map(c => `<span class='badge bg-info me-1'>${c}</span>`).join('')}${caps.length>2 ? `<span class='text-muted small'>+${caps.length-2}</span>`:''}</td>
      <td>$${m.input_price_per_1k} / $${m.output_price_per_1k}</td>
      <td>${m.context_length || ''}</td>
      <td><span class='badge bg-secondary'>${m.status || 'active'}</span></td>
      <td>${m.performance_score || ''}</td>
      <td><button class='btn btn-sm btn-outline-primary' onclick="viewModelDetails('${m.slug}')"><i class='fas fa-eye'></i></button></td>
    </tr>`;
  }).join('');
}
/** Toggle inclusion of a single model in bulk selection */
function toggleModelSelection(slug) {
  const i = selectedModels.indexOf(slug);
  if (i > -1) selectedModels.splice(i, 1); else selectedModels.push(slug);
  const el = document.getElementById('selected-models-count');
  if (el) el.textContent = selectedModels.length;
  try { localStorage.setItem('models_selected', JSON.stringify(selectedModels)); } catch(e) {}
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
  const el = document.getElementById('selected-models-count');
  if (el) el.textContent = selectedModels.length;
  try { localStorage.setItem('models_selected', JSON.stringify(selectedModels)); } catch(e) {}
}
/** Open modal with enriched model details (fetched on demand) */
function viewModelDetails(slug) {
  const target = document.getElementById('model-details-modal-content');
  if (!target) return;
  target.innerHTML = '<div class="p-3">Loading...</div>';
  // Include timestamp cache-buster to ensure latest details in case of recent sync
  const ts = Date.now();
  fetch(`/models/model/${encodeURIComponent(slug)}/more-info?ts=${ts}`)
    .then(r => r.text())
    .then(html => {
      target.innerHTML = html;
      if (window.bootstrap) {
        new bootstrap.Modal(document.getElementById('modelDetailsModal')).show();
      }
    })
    .catch(() => target.innerHTML = '<div class="alert alert-danger m-0">Failed to load.</div>');
}
function refreshModels() { loadModelsPaginated(); }
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
    .then(res => { alert(`Updated ${res.updated || 0} models.`); loadModels(); })
    .catch(() => alert('Tag installed failed'));
}
function setupMultiselects() {
  document.querySelectorAll('.provider-option').forEach(cb => cb.addEventListener('change', applyFilters));
  document.querySelectorAll('.capability-option').forEach(cb => cb.addEventListener('change', applyFilters));
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
}

// Expose functions if needed globally
  window.debounceSearch = debounceSearch;
  window.clearSearch = clearSearch;
  window.toggleModelSelection = toggleModelSelection;
  window.toggleSelectAll = toggleSelectAll;
  window.viewModelDetails = viewModelDetails;
  window.refreshModels = refreshModels;
  window.openComparison = openComparison;
  window.exportModelsData = exportModelsData;
  window.tagInstalledModels = tagInstalledModels;
  window.setModelsSource = setModelsSource;
  window.changePerPage = changePerPage;
  window.gotoModelsPage = gotoModelsPage;
  window.updateBatchSelectionCount = updateBatchSelectionCount;
}
