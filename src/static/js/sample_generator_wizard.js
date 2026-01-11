// Sample Generator Wizard JavaScript
// Handles wizard navigation, form validation, and generation management
// HTMX-safe: Uses window namespace and guards against duplicate initialization

(function() {
// ============================================================================
// HTMX Safety Guard - Prevent duplicate initialization
// ============================================================================

// If already loaded, just re-initialize without adding more listeners
if (window._sampleGeneratorWizardLoaded) {
  // Only re-init if we're on the sample generator page (check for unique element)
  if (document.getElementById('sample-generator-wizard')) {
    window.initSampleGeneratorWizard();
  }
  return;
}
window._sampleGeneratorWizardLoaded = true;

// ============================================================================
// State Management
// ============================================================================

let currentStep = 1;
let selectedScaffolding = null;
let selectedTemplates = [];
let selectedModels = [];
let selectedGenerationMode = 'guarded';  // Default to guarded mode
let rerunOnFailure = false;  // Default to false
let useAutoFix = false;  // Default to false
let maxRetries = 1;  // Default to 1 retry

// Cache for templates and models
let templatesCache = null;
let modelsCache = null;

// Execution guard to prevent concurrent generation runs
let isGenerating = false;

// ============================================================================
// Initialization
// ============================================================================

function initSampleGeneratorWizard() {
  // Only run if we're on the sample generator page (check for unique container)
  if (!document.getElementById('sample-generator-wizard')) return;
  
  console.log('[Wizard] Sample Generator Wizard initialized');
  
  // Reset State
  currentStep = 1;
  selectedScaffolding = null;
  selectedTemplates = [];
  selectedModels = [];
  selectedGenerationMode = 'guarded';
  rerunOnFailure = false;
  useAutoFix = false;
  maxRetries = 1;
  isGenerating = false;
  
  initializeWizard();
  loadInitialData();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSampleGeneratorWizard);
} else {
  initSampleGeneratorWizard();
}

document.body.addEventListener('htmx:afterSwap', function(evt) {
  // Re-initialize if sample generator wizard content was swapped in
  if (document.getElementById('sample-generator-wizard')) {
    initSampleGeneratorWizard();
  }
});

document.body.addEventListener('htmx:historyRestore', function(evt) {
  // Re-initialize if sample generator wizard content was restored from history
  if (document.getElementById('sample-generator-wizard')) {
    console.log('[Wizard] History restore detected, re-initializing...');
    initSampleGeneratorWizard();
  }
});

function initializeWizard() {
  updateWizardStep();
  updateNavigationButtons();
  initAdvancedOptionsCollapse();
  
  // Auto-select default scaffolding
  selectScaffolding('default');
}

async function loadInitialData() {
  try {
    // First, try to load from server-rendered embedded data (avoids auth issues with fetch)
    const pageDataEl = document.getElementById('page-data');
    if (pageDataEl) {
      try {
        const pageData = JSON.parse(pageDataEl.textContent);
        console.log('[Wizard] Found embedded page data:', pageData);
        
        if (pageData.templates && Array.isArray(pageData.templates)) {
          templatesCache = pageData.templates;
          console.log(`[Wizard] Loaded ${templatesCache.length} templates from embedded data`);
        }
        if (pageData.models && Array.isArray(pageData.models)) {
          modelsCache = pageData.models;
          console.log(`[Wizard] Loaded ${modelsCache.length} models from embedded data`);
        }
        
        // If we successfully loaded both from embedded data, we're done
        if (templatesCache && templatesCache.length > 0 && modelsCache && modelsCache.length > 0) {
          console.log('[Wizard] Successfully loaded initial data from server-rendered page');
          return;
        }
      } catch (parseError) {
        console.warn('[Wizard] Failed to parse embedded page data, falling back to API fetch:', parseError);
      }
    }
    
    // Fallback: Load via API fetch (requires credentials for authenticated endpoints)
    console.log('[Wizard] Loading initial data via API fetch (fallback)...');
    
    // Load templates
    if (!templatesCache || templatesCache.length === 0) {
      console.log('[Wizard] Loading templates from /api/gen/templates...');
      const templatesResponse = await fetch('/api/gen/templates', { credentials: 'include' });
      if (templatesResponse.ok) {
        const templatesData = await templatesResponse.json();
        console.log('[Wizard] Templates response:', templatesData);
        
        // Standardized API envelope: {success: true, data: [...], message: "..."}
        if (templatesData.success && Array.isArray(templatesData.data)) {
          templatesCache = templatesData.data;
          console.log(`[Wizard] Loaded ${templatesCache.length} templates`);
        } else {
          console.error('[Wizard] Invalid templates response format:', templatesData);
          templatesCache = [];
        }
      } else {
        console.error('[Wizard] Failed to load templates:', templatesResponse.status, templatesResponse.statusText);
        const errorText = await templatesResponse.text();
        console.error('[Wizard] Error response:', errorText);
        templatesCache = [];
      }
    }
    
    // Load models
    if (!modelsCache || modelsCache.length === 0) {
      console.log('[Wizard] Loading models from /api/models...');
      const modelsResponse = await fetch('/api/models', { credentials: 'include' });
      if (modelsResponse.ok) {
        const modelsData = await modelsResponse.json();
        console.log('[Wizard] Models response:', modelsData);
        
        // Handle standardized API envelope: {success: true, data: [...], message: "..."}
        if (modelsData.success && modelsData.data) {
          modelsCache = Array.isArray(modelsData.data) ? modelsData.data : [];
        } else if (Array.isArray(modelsData)) {
          modelsCache = modelsData;
        } else if (modelsData.models && Array.isArray(modelsData.models)) {
          modelsCache = modelsData.models;
        } else {
          console.warn('[Wizard] Unexpected models response format:', modelsData);
          modelsCache = [];
        }
        console.log(`[Wizard] Loaded ${modelsCache.length} models`);
      } else {
        console.error('[Wizard] Failed to load models:', modelsResponse.status, modelsResponse.statusText);
        const errorText = await modelsResponse.text();
        console.error('[Wizard] Error response:', errorText);
        modelsCache = [];
      }
    }
  } catch (error) {
    console.error('[Wizard] Error loading initial data:', error);
    templatesCache = templatesCache || [];
    modelsCache = modelsCache || [];
  }
}

// ============================================================================
// Wizard Navigation
// ============================================================================

function nextStep() {
  if (!validateCurrentStep()) {
    return;
  }
  
  if (currentStep < 3) {
    currentStep++;
    updateWizardStep();
    updateNavigationButtons();
    
    // Load data for the new step
    if (currentStep === 2) {
      loadTemplatesAndModels();
    }
  }
}

function previousStep() {
  if (currentStep > 1) {
    currentStep--;
    updateWizardStep();
    updateNavigationButtons();
  }
}

function goToStep(stepNumber) {
  if (stepNumber >= 1 && stepNumber <= 3) {
    // Validate all previous steps
    for (let i = 1; i < stepNumber; i++) {
      if (!isStepValid(i)) {
        showNotification(`Please complete step ${i} first`, 'warning');
        return;
      }
    }
    
    currentStep = stepNumber;
    updateWizardStep();
    updateNavigationButtons();
    
    if (currentStep === 2) {
      loadTemplatesAndModels();
    }
  }
}

function updateWizardStep() {
  // Update progress bar
  const progress = (currentStep / 3) * 100;
  const progressBar = document.getElementById('wizard-progress-bar');
  if (progressBar) {
    progressBar.style.width = `${progress}%`;
    progressBar.setAttribute('aria-valuenow', progress);
  }
  
  // Hide all panels (use active class like create.html)
  document.querySelectorAll('.wizard-panel').forEach(panel => {
    panel.classList.remove('active');
  });
  
  // Show current panel
  const currentPanel = document.querySelector(`[data-panel="${currentStep}"]`);
  if (currentPanel) {
    currentPanel.classList.add('active');
  }
  
  // Update step indicators (use active/completed classes like create.html)
  document.querySelectorAll('.step-item').forEach((step, index) => {
    const stepNum = index + 1;
    step.classList.remove('active', 'completed');
    if (stepNum < currentStep) {
      step.classList.add('completed');
    } else if (stepNum === currentStep) {
      step.classList.add('active');
    }
  });

  // Update help content visibility (use active class like create.html)
  document.querySelectorAll('.help-content').forEach(help => {
    help.classList.remove('active');
  });
  const currentHelp = document.querySelector(`[data-help="${currentStep}"]`);
  if (currentHelp) {
    currentHelp.classList.add('active');
  }
  
  // Update guide collapse indicator
  const guideCollapse = document.getElementById('guide-collapse');
  const guideIndicator = document.getElementById('guide-collapse-indicator');
  if (guideCollapse && guideIndicator) {
    guideCollapse.addEventListener('shown.bs.collapse', () => { guideIndicator.textContent = 'Hide'; });
    guideCollapse.addEventListener('hidden.bs.collapse', () => { guideIndicator.textContent = 'Show'; });
  }

  // Update step counter
  const stepCounter = document.getElementById('current-step');
  if (stepCounter) {
    stepCounter.textContent = currentStep;
  }
  
  // Update summary sidebar
  updateSidebar();
  
  // Scroll to top smoothly
  try {
    const activePanel = document.querySelector('.wizard-panel.active');
    if (activePanel) {
      activePanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } catch (e) {
    console.warn('Scroll into view failed:', e);
  }
}

function updateNavigationButtons() {
  console.log('[Wizard] updateNavigationButtons called, currentStep:', currentStep);
  
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const startBtn = document.getElementById('start-btn');
  
  if (!prevBtn || !nextBtn || !startBtn) {
    console.error('[Wizard] Navigation buttons not found!', {prevBtn, nextBtn, startBtn});
    return;
  }
  
  const show = (el) => { if (el) el.classList.remove('d-none'); };
  const hide = (el) => { if (el) el.classList.add('d-none'); };
  
  // Previous button availability - enable unless on first step
  if (prevBtn) {
    prevBtn.disabled = currentStep === 1;
    console.log('[Wizard] Previous button disabled:', currentStep === 1);
  }
  
  // Check if step is valid
  const stepValid = canProceedFromStep(currentStep);
  console.log('[Wizard] Navigation state:', {
    currentStep,
    stepValid,
    selectedScaffolding,
    selectedTemplatesCount: selectedTemplates.length,
    selectedModelsCount: selectedModels.length
  });
  
  if (currentStep === 3) {
    hide(nextBtn);
    show(startBtn);
    startBtn.disabled = !stepValid;
    
    // Setup click handler for start button (remove old listeners by cloning)
    const newStartBtn = startBtn.cloneNode(true);
    startBtn.parentNode.replaceChild(newStartBtn, startBtn);
    newStartBtn.addEventListener('click', () => {
      console.log('[Wizard] Start button clicked');
      startGeneration();
    });
    
    console.log('[Wizard] Step 3: Start button disabled:', !stepValid, 'Event listener attached');
  } else {
    show(nextBtn);
    hide(startBtn);
    nextBtn.disabled = !stepValid;
    
    // Update next button text based on validation state
    if (stepValid) {
      nextBtn.innerHTML = 'Next <i class="fas fa-chevron-right ms-1"></i>';
      nextBtn.classList.remove('btn-outline-primary');
      nextBtn.classList.add('btn-primary');
      console.log('[Wizard] Next button enabled');
    } else {
      nextBtn.innerHTML = 'Complete this step to continue';
      nextBtn.classList.remove('btn-primary');
      nextBtn.classList.add('btn-outline-primary');
      console.log('[Wizard] Next button disabled - step not valid');
    }
  }
}

// ============================================================================
// Validation
// ============================================================================

function validateCurrentStep() {
  return isStepValid(currentStep);
}

function isStepValid(step) {
  let valid = false;
  switch (step) {
    case 1:
      valid = selectedScaffolding !== null;
      console.log('[Wizard] Step 1 valid:', valid, 'Scaffolding:', selectedScaffolding);
      return valid;
    case 2:
      // Allow multiple models for batch generation
      valid = selectedTemplates.length > 0 && selectedModels.length > 0;
      console.log('[Wizard] Step 2 valid:', valid, 'Templates:', selectedTemplates.length, 'Models:', selectedModels.length);
      return valid;
    case 3:
      console.log('[Wizard] Step 3 always valid');
      return true; // Step 3 is always valid (results view)
    default:
      console.log('[Wizard] Invalid step:', step);
      return false;
  }
}

function canProceedFromStep(step) {
  return isStepValid(step);
}

// ============================================================================
// Step 1: Scaffolding Selection
// ============================================================================

function selectScaffolding(scaffoldingId) {
  selectedScaffolding = scaffoldingId;
  
  // Update hidden input
  const input = document.getElementById('input-scaffolding-id');
  if (input) {
    input.value = scaffoldingId;
  }
  
  // Update UI
  updateScaffoldingUI();
  updateNavigationButtons();
  updateSidebar();
  
  // Show preview
  showScaffoldingPreview();
}

function updateScaffoldingUI() {
  const cards = document.querySelectorAll('#scaffolding-selection-list .card');
  cards.forEach(card => {
    if (selectedScaffolding) {
      card.classList.add('border-primary');
    }
  });
}

function showScaffoldingPreview() {
  const preview = document.getElementById('scaffolding-preview');
  if (preview) {
    preview.classList.remove('d-none');
  }
}

// ============================================================================
// Generation Mode Selection
// ============================================================================

function selectGenerationMode(mode) {
  selectedGenerationMode = mode;
  
  // Update hidden input
  const input = document.getElementById('input-generation-mode');
  if (input) {
    input.value = mode;
  }
  
  // Update card selection UI
  const guardedCard = document.getElementById('mode-card-guarded');
  const unguardedCard = document.getElementById('mode-card-unguarded');
  const guardedBadge = document.getElementById('mode-selected-guarded');
  const unguardedBadge = document.getElementById('mode-selected-unguarded');
  const warningAlert = document.getElementById('unguarded-warning');
  
  if (mode === 'guarded') {
    guardedCard?.classList.add('selected');
    unguardedCard?.classList.remove('selected');
    guardedBadge?.classList.remove('d-none');
    unguardedBadge?.classList.add('d-none');
    if (warningAlert) warningAlert.style.display = 'none';
  } else {
    guardedCard?.classList.remove('selected');
    unguardedCard?.classList.add('selected');
    guardedBadge?.classList.add('d-none');
    unguardedBadge?.classList.remove('d-none');
    if (warningAlert) warningAlert.style.display = 'block';
  }
  
  // Update sidebar
  updateGenerationModeSidebar();
  updateNavigationButtons();
}

function updateGenerationModeSidebar() {
  const modeBadge = document.getElementById('sidebar-mode-badge');
  const modeDescription = document.getElementById('sidebar-mode-description');
  
  if (modeBadge) {
    if (selectedGenerationMode === 'guarded') {
      modeBadge.className = 'badge bg-success-lt';
      modeBadge.textContent = 'Guarded';
    } else {
      modeBadge.className = 'badge bg-warning-lt';
      modeBadge.textContent = 'Unguarded';
    }
  }
  
  if (modeDescription) {
    if (selectedGenerationMode === 'guarded') {
      modeDescription.textContent = 'Pre-defined architecture (4-query system)';
    } else {
      modeDescription.textContent = 'Model-driven architecture (research mode)';
    }
  }
}

// ============================================================================
// Advanced Options Management
// ============================================================================

function updateAdvancedOption(option, value) {
  console.log('[Wizard] Advanced option changed:', option, '=', value);
  
  switch (option) {
    case 'rerun-on-failure':
      rerunOnFailure = !!value;
      document.getElementById('input-rerun-on-failure').value = rerunOnFailure ? 'true' : 'false';
      // Show/hide max retries selector
      const maxRetriesContainer = document.getElementById('max-retries-container');
      if (maxRetriesContainer) {
        maxRetriesContainer.style.display = rerunOnFailure ? 'block' : 'none';
      }
      break;
    case 'use-auto-fix':
      useAutoFix = !!value;
      document.getElementById('input-use-auto-fix').value = useAutoFix ? 'true' : 'false';
      break;
    case 'max-retries':
      maxRetries = parseInt(value, 10) || 1;
      document.getElementById('input-max-retries').value = maxRetries;
      break;
  }
  
  console.log('[Wizard] Current advanced options:', { rerunOnFailure, useAutoFix, maxRetries });
}

function initAdvancedOptionsCollapse() {
  const advancedCollapse = document.getElementById('advanced-options-collapse');
  const advancedIndicator = document.getElementById('advanced-options-indicator');
  if (advancedCollapse && advancedIndicator) {
    advancedCollapse.addEventListener('shown.bs.collapse', () => { advancedIndicator.textContent = 'Hide'; });
    advancedCollapse.addEventListener('hidden.bs.collapse', () => { advancedIndicator.textContent = 'Show'; });
  }
}

// ============================================================================
// Step 2: Templates and Models Selection
// ============================================================================

async function loadTemplatesAndModels() {
  await loadTemplates();
  await loadModels();
}

async function loadTemplates() {
  const listContainer = document.getElementById('template-selection-list');
  if (!listContainer) return;
  
  // Check if templates are already in cache (loaded from embedded page data)
  if (templatesCache && templatesCache.length > 0) {
    console.log('[Wizard] Using cached templates from embedded data:', templatesCache.length);
    renderTemplatesTable(listContainer, templatesCache);
    return;
  }
  
  listContainer.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary"></div><p class="small text-muted mt-2">Loading templates...</p></div>';
  
  try {
    console.log('[Wizard] Fetching templates from /api/gen/templates...');
    const response = await fetch('/api/gen/templates', {
      credentials: 'include'  // Include session cookies for authentication
    });
    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Wizard] Template load error:', response.status, errorText);
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('[Wizard] Templates data received:', data);
    
    // Handle standardized API envelope
    let templates = [];
    if (data.success && data.data) {
      templates = Array.isArray(data.data) ? data.data : [];
    } else if (Array.isArray(data)) {
      templates = data;
    } else if (data.templates && Array.isArray(data.templates)) {
      templates = data.templates;
    }
    
    templatesCache = templates;
    console.log(`[Wizard] Parsed ${templates.length} templates`);
    
    renderTemplatesTable(listContainer, templates);
  } catch (error) {
    console.error('[Wizard] Error loading templates:', error);
    listContainer.innerHTML = `<div class="text-center text-danger p-4"><i class="fas fa-exclamation-triangle fa-2x mb-2"></i><p class="fw-bold">Error loading templates</p><p class="small">${error.message}</p><button class="btn btn-sm btn-outline-primary mt-2" onclick="loadTemplates()">Retry</button></div>`;
  }
}

// Helper function to render templates table (extracted for reuse)
function renderTemplatesTable(listContainer, templates) {
    
    listContainer.innerHTML = '';
    
    if (templates.length === 0) {
      listContainer.innerHTML = '<div class="empty py-5"><div class="empty-icon"><i class="fas fa-inbox fa-3x text-muted"></i></div><p class="empty-title h5">No templates available</p><p class="empty-subtitle text-muted">Templates should be in <code>misc/requirements/</code></p></div>';
      return;
    }
    
    // Map V2 requirements to wizard template format
    templates.forEach((template) => {
      // Ensure display_name is set for consistency
      template.display_name = template.name;
    });
    
    // Update cache with modified templates
    templatesCache = templates;
    console.log('[Wizard] Templates cache updated:', templatesCache.map(t => ({ slug: t.slug, name: t.name })));

    // Filter out any previously selected templates that no longer exist
    if (selectedTemplates.length) {
      const validSlugs = new Set(templates.map(t => t.slug));
      selectedTemplates = selectedTemplates.filter(slug => validSlugs.has(slug));
    }
    
    // Render as table
    const table = document.createElement('table');
    table.className = 'table table-sm table-vcenter table-hover card-table mb-0';
    table.id = 'templates-selection-table';
    table.innerHTML = `
      <thead>
        <tr>
          <th class="w-1"></th>
          <th class="text-nowrap">Template</th>
          <th>Description</th>
          <th class="text-nowrap">Category</th>
        </tr>
      </thead>
      <tbody id="template-selection-tbody"></tbody>
    `;
    listContainer.appendChild(table);
    
    const tbody = table.querySelector('tbody');
    templates.forEach(template => {
      const row = createTemplateTableRow(template);
      tbody.appendChild(row);
    });
    
    console.log('[Wizard] Templates UI updated with V2 requirements');
    console.log('[Wizard] Template items added to wizard list, ready for clicks');  
    updateSidebar();
    updateNavigationButtons();
}

function createTemplateTableRow(template) {
  const row = document.createElement('tr');
  row.className = 'template-item';
  row.style.cursor = 'pointer';
  
  const slug = template.slug || '';
  const name = template.name || template.display_name || template.title || `Template ${slug}`;
  const description = template.description || template.desc || '';
  const category = template.category || 'general';
  
  row.setAttribute('data-template-slug', slug);
  
  row.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const templateSlug = row.getAttribute('data-template-slug');
    if (templateSlug) {
      toggleTemplateSelection(templateSlug);
    }
  });
  
  const isSelected = selectedTemplates.includes(slug);
  if (isSelected) {
    row.classList.add('table-primary');
  }
  
  row.innerHTML = `
    <td>
      <input type="checkbox" class="form-check-input" data-template-slug="${escapeHtml(slug)}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation();">
    </td>
    <td class="fw-semibold text-nowrap">${escapeHtml(name)}</td>
    <td class="small text-muted">
      ${description ? escapeHtml(description.slice(0, 50)) + (description.length > 50 ? '...' : '') : '<span class="text-muted">—</span>'}
    </td>
    <td>
      <span class="badge bg-secondary-lt text-secondary">${escapeHtml(category)}</span>
    </td>
  `;
  
  return row;
}

function createTemplateListItem(template) {
  const item = document.createElement('a');
  item.href = '#';
  item.className = 'list-group-item list-group-item-action';
  
  // Use slug-based identification
  const slug = template.slug || '';
  const name = template.name || template.display_name || template.title || `Template ${slug}`;
  const templateType = 'both'; // V2 requirements generate both backend and frontend
  const description = template.description || template.desc || '';
  const category = template.category || 'general';
  
  console.log('[Wizard] Creating template item:', { slug, name, category });
  
  // Store the slug as data attribute
  item.setAttribute('data-template-slug', slug);
  
  // Add click handler using addEventListener instead of onclick
  item.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    console.log('[Wizard] Template item clicked, slug:', slug);
    const templateSlug = item.getAttribute('data-template-slug');
    if (templateSlug) {
      toggleTemplateSelection(templateSlug);
    } else {
      console.error('[Wizard] No slug found for clicked template');
    }
  });
  
  // Check if selected
  const isSelected = selectedTemplates.includes(slug);
  if (isSelected) {
    item.classList.add('active');
  }
  
  // Determine template type badge
  let typeBadge = '<span class="badge bg-purple-lt"><i class="fas fa-code me-1"></i>Both</span>';
  if (templateType === 'backend' || templateType.toLowerCase().includes('backend')) {
    typeBadge = '<span class="badge bg-blue-lt"><i class="fas fa-server me-1"></i>Backend</span>';
  } else if (templateType === 'frontend' || templateType.toLowerCase().includes('frontend')) {
    typeBadge = '<span class="badge bg-green-lt"><i class="fas fa-window-maximize me-1"></i>Frontend</span>';
  }
  
  // Category badge
  const categoryBadge = `<span class="badge bg-secondary-lt">${escapeHtml(category)}</span>`;
  
  const descriptionHtml = description ? `<div class="text-muted small mt-1">${escapeHtml(description.slice(0, 100))}${description.length > 100 ? '...' : ''}</div>` : '';
  
  item.innerHTML = `
    <div class="d-flex align-items-center">
      <div class="flex-fill">
        <strong>${escapeHtml(name)}</strong>
        <div class="text-muted small">${typeBadge} ${categoryBadge}</div>
        ${descriptionHtml}
      </div>
      <div class="form-check">
        <input class="form-check-input" type="checkbox" data-template-slug="${slug}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation();">
      </div>
    </div>
  `;
  
  return item;
}

function toggleTemplateSelection(slug) {
  console.log('[Wizard] Toggle template:', slug, 'Type:', typeof slug);
  console.log('[Wizard] Current selected templates length:', selectedTemplates.length);
  
  const index = selectedTemplates.indexOf(slug);
  if (index > -1) {
    selectedTemplates.splice(index, 1);
    console.log('[Wizard] Removed template:', slug, 'New count:', selectedTemplates.length);
  } else {
    selectedTemplates.push(slug);
    console.log('[Wizard] Added template:', slug, 'New count:', selectedTemplates.length);
  }
  
  console.log('[Wizard] Updated selected templates count:', selectedTemplates.length, 'First few:', selectedTemplates.slice(0, 3));
  
  // Only update UI elements, don't reload entire list
  updateTemplateSelectionUI();
  updateSidebar();
  updateNavigationButtons();
}

function updateTemplateSelectionUI() {
  // Re-render all items with updated selection state using table format
  if (templatesCache && templatesCache.length > 0) {
    const listContainer = document.getElementById('template-selection-list');
    if (listContainer) {
      listContainer.innerHTML = '';
      
      const table = document.createElement('table');
      table.className = 'table table-sm table-vcenter table-hover card-table mb-0';
      table.id = 'templates-selection-table';
      table.innerHTML = `
        <thead>
          <tr>
            <th class="w-1"></th>
            <th class="text-nowrap">Template</th>
            <th>Description</th>
            <th class="text-nowrap">Category</th>
          </tr>
        </thead>
        <tbody id="template-selection-tbody"></tbody>
      `;
      listContainer.appendChild(table);
      
      const tbody = table.querySelector('tbody');
      templatesCache.forEach(template => {
        const row = createTemplateTableRow(template);
        tbody.appendChild(row);
      });
    }
  }
}

function updateModelSelectionUI() {
  // Re-render all items with updated selection state using table format
  if (modelsCache && modelsCache.length > 0) {
    const listContainer = document.getElementById('model-selection-list');
    if (listContainer) {
      listContainer.innerHTML = '';
      
      // Group models by provider
      const modelsByProvider = {};
      modelsCache.forEach(model => {
        const provider = model.provider || 'Unknown';
        if (!modelsByProvider[provider]) {
          modelsByProvider[provider] = [];
        }
        modelsByProvider[provider].push(model);
      });
      
      const table = document.createElement('table');
      table.className = 'table table-sm table-vcenter table-hover card-table mb-0';
      table.id = 'models-selection-table';
      table.innerHTML = `
        <thead>
          <tr>
            <th class="w-1"></th>
            <th class="text-nowrap">Model</th>
            <th class="text-nowrap">Provider</th>
            <th>Pricing</th>
          </tr>
        </thead>
        <tbody id="model-selection-tbody"></tbody>
      `;
      listContainer.appendChild(table);
      
      const tbody = table.querySelector('tbody');
      
      Object.keys(modelsByProvider).sort().forEach(provider => {
        // Provider header row
        const headerRow = document.createElement('tr');
        headerRow.className = 'provider-header bg-light';
        headerRow.setAttribute('data-provider', provider);
        headerRow.innerHTML = `
          <td colspan="4" class="py-1 px-3 small fw-bold text-muted text-uppercase">
            <i class="fas fa-layer-group me-1"></i>${escapeHtml(provider)}
          </td>
        `;
        tbody.appendChild(headerRow);
        
        modelsByProvider[provider].forEach(model => {
          const row = createModelTableRow(model);
          tbody.appendChild(row);
        });
      });
    }
  }
}

function selectAllTemplates() {
  if (templatesCache) {
    console.log('[Wizard] Select all templates, cache:', templatesCache);
    // Extract slug from each template
    selectedTemplates = templatesCache.map(t => t.slug).filter(slug => slug);
    console.log('[Wizard] Selected all templates:', selectedTemplates);
    
    // Update UI without reloading
    updateTemplateSelectionUI();
    updateSidebar();
    updateNavigationButtons();
  }
}

function clearAllTemplates() {
  selectedTemplates = [];
  
  // Update UI without reloading
  updateTemplateSelectionUI();
  updateSidebar();
  updateNavigationButtons();
}

async function loadModels() {
  const listContainer = document.getElementById('model-selection-list');
  if (!listContainer) return;

  listContainer.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary"></div><p class="small text-muted mt-2">Loading models...</p></div>';

  try {
    console.log('[Wizard] Loading models from catalog (paginated source)...');
    const models = await fetchAllModelsFromCatalog();

    modelsCache = models;
    console.log(`[Wizard] Parsed ${models.length} models`);

    // Remove any selected models that are no longer available
    selectedModels = selectedModels.filter(slug => modelsCache.some(model => getModelSlug(model) === slug));

    listContainer.innerHTML = '';

    if (models.length === 0) {
      listContainer.innerHTML = '<div class="empty py-5"><div class="empty-icon"><i class="fas fa-robot fa-3x text-muted"></i></div><p class="empty-title h5">No models available</p><p class="empty-subtitle text-muted">Check database for model capabilities</p></div>';
      return;
    }

    // Group models by provider for table rendering
    const modelsByProvider = {};
    models.forEach(model => {
      const provider = model.provider || 'Unknown';
      if (!modelsByProvider[provider]) {
        modelsByProvider[provider] = [];
      }
      modelsByProvider[provider].push(model);
    });

    // Render as table with provider groupings
    const table = document.createElement('table');
    table.className = 'table table-sm table-vcenter table-hover card-table mb-0';
    table.id = 'models-selection-table';
    table.innerHTML = `
      <thead>
        <tr>
          <th class="w-1"></th>
          <th class="text-nowrap">Model</th>
          <th class="text-nowrap">Provider</th>
          <th>Pricing</th>
        </tr>
      </thead>
      <tbody id="model-selection-tbody"></tbody>
    `;
    listContainer.appendChild(table);
    
    const tbody = table.querySelector('tbody');
    
    // Render models grouped by provider
    Object.keys(modelsByProvider).sort().forEach(provider => {
      // Provider header row
      const headerRow = document.createElement('tr');
      headerRow.className = 'provider-header bg-light';
      headerRow.setAttribute('data-provider', provider);
      headerRow.innerHTML = `
        <td colspan="4" class="py-1 px-3 small fw-bold text-muted text-uppercase">
          <i class="fas fa-layer-group me-1"></i>${escapeHtml(provider)}
        </td>
      `;
      tbody.appendChild(headerRow);
      
      // Model rows for this provider
      modelsByProvider[provider].forEach(model => {
        const row = createModelTableRow(model);
        tbody.appendChild(row);
      });
    });

    console.log('[Wizard] Models UI updated');
    updateSidebar();
    updateNavigationButtons();
  } catch (error) {
    console.error('[Wizard] Error loading models:', error);
    const message = escapeHtml(error.message || 'Unknown error');
    listContainer.innerHTML = `<div class="text-center text-danger p-4"><i class="fas fa-exclamation-triangle fa-2x mb-2"></i><p class="fw-bold">Error loading models</p><p class="small">${message}</p><button class="btn btn-sm btn-outline-primary mt-2" onclick="loadModels()">Retry</button></div>`;
  }
}

async function fetchAllModelsFromCatalog() {
  const perPage = 250;
  const aggregatedModels = [];
  const baseParams = new URLSearchParams({
    per_page: String(perPage),
    source: 'db'
  });

  const firstPage = await fetchModelsPage(baseParams, 1);
  aggregatedModels.push(...firstPage.models);

  const totalPages = firstPage.pagination?.total_pages || 1;
  if (totalPages > 1) {
    console.log(`[Wizard] Detected ${totalPages} model pages, loading remaining...`);
    const pagePromises = [];
    for (let page = 2; page <= totalPages; page++) {
      pagePromises.push(fetchModelsPage(baseParams, page));
    }
    const remainingPages = await Promise.all(pagePromises);
    remainingPages.forEach(result => {
      aggregatedModels.push(...result.models);
    });
  }

  const normalizedModels = aggregatedModels.map((raw, index) => {
    const clone = { ...raw };
    const candidateSlugs = [clone.slug, clone.canonical_slug, clone.model_id, clone.id, clone.model_name, clone.name];
    let slug = candidateSlugs.find(val => typeof val === 'string' && val.trim().length > 0);
    if (!slug) {
      slug = `model-${index + 1}`;
    }
    clone.slug = String(slug).trim();
    return clone;
  });

  const uniqueMap = new Map();
  normalizedModels.forEach(model => {
    const slug = getModelSlug(model);
    if (!slug) {
      return;
    }
    if (!uniqueMap.has(slug)) {
      uniqueMap.set(slug, model);
    }
  });

  const uniqueModels = Array.from(uniqueMap.values());
  uniqueModels.sort((a, b) => {
    const providerA = (a.provider || '').toLowerCase();
    const providerB = (b.provider || '').toLowerCase();
    const providerCompare = providerA.localeCompare(providerB);
    if (providerCompare !== 0) {
      return providerCompare;
    }
    const nameA = (a.model_name || a.name || '').toLowerCase();
    const nameB = (b.model_name || b.name || '').toLowerCase();
    return nameA.localeCompare(nameB);
  });

  return uniqueModels;
}

async function fetchModelsPage(baseParams, pageNumber) {
  const params = new URLSearchParams(baseParams);
  params.set('page', String(pageNumber));

  const response = await fetch(`/api/models/paginated?${params.toString()}`);
  if (!response.ok) {
    const errorText = await response.text();
    console.error('[Wizard] Model page load error:', response.status, errorText);
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const data = await response.json();
  if (data.success === false) {
    throw new Error(data.message || 'Failed to load models');
  }

  const { models, pagination } = extractModelsFromResponse(data);
  if (!Array.isArray(models)) {
    throw new Error('Invalid model payload received');
  }

  console.log(`[Wizard] Loaded page ${pageNumber} with ${models.length} models`);
  return { models, pagination };
}

function extractModelsFromResponse(data) {
  let payload = data;
  if (payload && payload.success && payload.data) {
    payload = payload.data;
  }

  if (payload && payload.data && payload.data.models) {
    payload = payload.data;
  }

  let models = [];
  if (Array.isArray(payload)) {
    models = payload;
  } else if (payload && Array.isArray(payload.models)) {
    models = payload.models;
  } else if (payload && Array.isArray(payload.items)) {
    models = payload.items;
  } else if (payload && Array.isArray(payload.results)) {
    models = payload.results;
  } else if (payload && payload.data && Array.isArray(payload.data)) {
    models = payload.data;
  }

  const pagination = payload && payload.pagination ? payload.pagination
    : payload && payload.data && payload.data.pagination ? payload.data.pagination
    : null;
  return { models, pagination };
}

function createModelTableRow(model) {
  const row = document.createElement('tr');
  row.className = 'model-item';
  row.style.cursor = 'pointer';
  
  let slug = getModelSlug(model);
  if (!slug) {
    slug = `model-${String(model.model_id || model.name || model.provider || 'unknown').replace(/\s+/g, '-').toLowerCase()}`;
  }
  model.slug = slug;
  const name = model.model_name || model.name || model.display_name || slug;
  const provider = model.provider || 'Unknown';
  
  const inputCost = normalizeModelCost(model);
  const outputCost = normalizeModelOutputCost(model);
  
  row.setAttribute('data-model-slug', slug);
  row.setAttribute('data-provider', provider);
  
  row.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const modelSlug = row.getAttribute('data-model-slug');
    if (modelSlug) {
      toggleModelSelection(modelSlug);
    }
  });
  
  const isSelected = selectedModels.includes(slug);
  if (isSelected) {
    row.classList.add('table-primary');
  }
  
  // Build pricing display
  let pricingHtml = '';
  if (inputCost !== null || outputCost !== null) {
    const parts = [];
    if (inputCost !== null) {
      parts.push(`<span class="badge bg-success-lt text-success me-1" title="Input cost per 1K tokens">In ${formatCost(inputCost)}</span>`);
    }
    if (outputCost !== null) {
      parts.push(`<span class="badge bg-warning-lt text-warning" title="Output cost per 1K tokens">Out ${formatCost(outputCost)}</span>`);
    }
    pricingHtml = parts.join('');
  } else {
    pricingHtml = '<span class="text-muted">—</span>';
  }
  
  row.innerHTML = `
    <td>
      <input type="checkbox" class="form-check-input" data-model-slug="${escapeHtml(slug)}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation();">
    </td>
    <td class="fw-semibold text-nowrap">${escapeHtml(name)}</td>
    <td><span class="badge bg-azure-lt text-azure">${escapeHtml(provider.toUpperCase())}</span></td>
    <td class="small">${pricingHtml}</td>
  `;
  
  return row;
}

function createModelListItem(model) {
  const item = document.createElement('a');
  item.href = '#';
  item.className = 'list-group-item list-group-item-action';

  let slug = getModelSlug(model);
  if (!slug) {
    slug = `model-${String(model.model_id || model.name || model.provider || 'unknown').replace(/\s+/g, '-').toLowerCase()}`;
  }
  model.slug = slug;
  const name = model.model_name || model.name || model.display_name || slug;
  const provider = model.provider || 'Unknown';
  const capabilities = Array.isArray(model.capabilities) ? model.capabilities : [];

  const inputCost = normalizeModelCost(model);
  const outputCost = normalizeModelOutputCost(model);

  item.setAttribute('data-model-slug', slug);

  item.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const modelSlug = item.getAttribute('data-model-slug');
    if (modelSlug) {
      toggleModelSelection(modelSlug);
    }
  });

  const isSelected = selectedModels.includes(slug);
  if (isSelected) {
    item.classList.add('active');
  }

  const providerBadge = `<span class="badge bg-azure-lt"><i class="fas fa-building me-1"></i>${escapeHtml(provider)}</span>`;

  const pricingBadges = [];
  if (inputCost !== null) {
    pricingBadges.push(`<span class="badge bg-success-lt" title="Input cost per 1K tokens">Input ${formatCost(inputCost)}</span>`);
  }
  if (outputCost !== null) {
    pricingBadges.push(`<span class="badge bg-warning-lt" title="Output cost per 1K tokens">Output ${formatCost(outputCost)}</span>`);
  }
  if (pricingBadges.length === 0) {
    pricingBadges.push('<span class="badge bg-secondary-lt">Pricing N/A</span>');
  }

  let capabilitiesHtml = '';
  if (capabilities.length > 0) {
    const displayCaps = capabilities.slice(0, 3).map(cap => `<span class="badge bg-secondary-lt">${escapeHtml(cap)}</span>`).join('');
    const extraCaps = capabilities.length > 3 ? `<span class="badge bg-secondary-lt">+${capabilities.length - 3}</span>` : '';
    capabilitiesHtml = `<div class="d-flex flex-wrap gap-1 mt-1 text-muted small">${displayCaps}${extraCaps}</div>`;
  }

  item.innerHTML = `
    <div class="d-flex align-items-center">
      <div class="flex-fill">
        <strong>${escapeHtml(name)}</strong>
        <div class="text-muted small d-flex flex-wrap align-items-center gap-1 mt-1">
          ${providerBadge}
          ${pricingBadges.join('')}
        </div>
        ${capabilitiesHtml}
        <div class="text-muted small mt-1"><code class="small">${escapeHtml(slug)}</code></div>
      </div>
      <div class="form-check">
        <input class="form-check-input" type="checkbox" data-model="${slug}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation();">
      </div>
    </div>
  `;

  return item;
}

function toggleModelSelection(slug) {
  console.log('[Wizard] Toggle model:', slug, 'Type:', typeof slug);
  console.log('[Wizard] Current selected models length:', selectedModels.length);
  
  // Ensure slug is a string
  const stringSlug = String(slug);
  
  const index = selectedModels.indexOf(stringSlug);
  if (index > -1) {
    selectedModels.splice(index, 1);
    console.log('[Wizard] Removed model:', stringSlug, 'New count:', selectedModels.length);
  } else {
    selectedModels.push(stringSlug);
    console.log('[Wizard] Added model:', stringSlug, 'New count:', selectedModels.length);
  }
  
  console.log('[Wizard] Updated selected models count:', selectedModels.length, 'First few:', selectedModels.slice(0, 3));
  
  // Only update UI elements, don't reload entire list
  updateModelSelectionUI();
  updateSidebar();
  updateNavigationButtons();
}

function selectAllModels() {
  if (modelsCache) {
    console.log('[Wizard] Select all models, cache:', modelsCache);
    selectedModels = modelsCache
      .map(getModelSlug)
      .filter(slug => Boolean(slug));
    selectedModels = Array.from(new Set(selectedModels));
    console.log('[Wizard] Selected all models:', selectedModels);
    loadModels();
    updateNavigationButtons();
  }
}

function clearAllModels() {
  selectedModels = [];
  loadModels();
  updateNavigationButtons();
}

function updateGenerationSummary() {
  const templateCount = selectedTemplates.length;
  const modelCount = selectedModels.length;
  const totalPairs = templateCount * modelCount;

  console.log('[Wizard] updateGenerationSummary:', { templateCount, modelCount, totalPairs });

  setTextContent('selection-template-count', templateCount);
  setTextContent('selection-model-count', modelCount);
  setTextContent('selection-total-pairs', totalPairs);
  setTextContent('summary-total-generations', totalPairs);
  setTextContent('status-total', totalPairs);
  setTextContent('status-templates', templateCount);
  setTextContent('status-models', modelCount);
  setTextContent('sidebar-total-pairs', totalPairs);

  const progressTotalEl = document.getElementById('progress-total');
  if (progressTotalEl) {
    progressTotalEl.textContent = totalPairs;
  }

  const selectedModelObjects = modelsCache
    ? selectedModels
        .map(slug => modelsCache.find(model => getModelSlug(model) === slug))
        .filter(Boolean)
    : [];

  const costValues = selectedModelObjects
    .map(normalizeModelCost)
    .filter(value => value !== null);

  const avgCost = costValues.length
    ? costValues.reduce((sum, value) => sum + value, 0) / costValues.length
    : null;
  const minCost = costValues.length ? Math.min(...costValues) : null;
  const maxCost = costValues.length ? Math.max(...costValues) : null;

  const avgCostText = avgCost !== null ? formatCost(avgCost) : '–';
  setTextContent('selection-average-cost', avgCostText);
  setTextContent('sidebar-average-cost', avgCostText);

  const costRangeText = formatCostRange(minCost, maxCost);
  setTextContent('status-cost', costRangeText);

  const hasModelsSelected = modelCount > 0;
  const costNote = document.getElementById('selection-cost-note');
  if (costNote) {
    if (costValues.length) {
      costNote.textContent = `Estimated input price per 1K tokens across selected models: ${costRangeText}. Actual spend depends on prompt size and output tokens.`;
    } else if (hasModelsSelected) {
      costNote.textContent = 'Pricing data is unavailable for the selected models.';
    } else {
      costNote.textContent = 'Select at least one model to see estimated pricing.';
    }
  }

  const sidebarCostNote = document.getElementById('sidebar-cost-note');
  if (sidebarCostNote) {
    if (costValues.length) {
      sidebarCostNote.textContent = 'Pricing shown per 1K input tokens. Output tokens may add extra cost.';
    } else if (hasModelsSelected) {
      sidebarCostNote.textContent = 'Pricing data missing for these models; review pricing in the Models overview.';
    } else {
      sidebarCostNote.textContent = 'Select models to estimate cost.';
    }
  }
}

// ============================================================================
// Step 3: Generation and Status
// ============================================================================

async function startGeneration() {
  // Guard: Prevent concurrent executions
  if (isGenerating) {
    console.warn('[Wizard] Generation already in progress, ignoring duplicate call');
    return;
  }
  
  if (!validateCurrentStep()) {
    showNotification('Please complete all previous steps', 'warning');
    return;
  }
  
  // CRITICAL: Validate at least one model selected
  if (selectedModels.length === 0) {
    showNotification('Please select at least one model', 'error');
    return;
  }
  
  // CRITICAL: Validate at least one template selected
  if (selectedTemplates.length === 0) {
    showNotification('Please select at least one template', 'error');
    return;
  }
  
  // CRITICAL: Log exactly what will be generated to prevent surprises
  console.log('[Wizard] GENERATION VALIDATION:');
  console.log('  - Templates to generate:', selectedTemplates);
  console.log('  - Models to use:', selectedModels);
  console.log('  - Total apps to create:', selectedTemplates.length * selectedModels.length);
  
  // Set flag immediately to block concurrent calls
  isGenerating = true;
  
  console.log('[Wizard] Starting batch generation');
  
  // Show loading state and disable button immediately
  const startBtn = document.getElementById('start-btn');
  const loadingBtn = document.getElementById('start-btn-loading');
  if (startBtn) {
    startBtn.disabled = true;
    startBtn.classList.add('d-none');
  }
  if (loadingBtn) loadingBtn.classList.remove('d-none');
  
  try {
    // Calculate total and prepare tracking
    const totalGenerations = selectedTemplates.length * selectedModels.length;
    const totalEl = document.getElementById('progress-total');
    const statusTotalEl = document.getElementById('status-total');
    if (totalEl) totalEl.textContent = totalGenerations;
    if (statusTotalEl) statusTotalEl.textContent = totalGenerations;
    
    const results = [];
    let completed = 0;
    let failed = 0;
    
    // Generate unique batch ID ONCE for this entire batch generation
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const randomSuffix = Math.random().toString(36).substring(2, 10);
    const batchId = `batch_${timestamp}_${randomSuffix}`;
    console.log(`[Wizard] Batch ID: ${batchId}`);
    
    // CRITICAL: Freeze selections to prevent mid-generation changes
    const templatesToGenerate = [...selectedTemplates];
    const modelsToUse = [...selectedModels];
    const generationMode = selectedGenerationMode;  // Freeze generation mode too
    
    // Freeze advanced options
    const frozenRerunOnFailure = rerunOnFailure;
    const frozenUseAutoFix = useAutoFix;
    const frozenMaxRetries = maxRetries;
    
    console.log(`[Wizard] LOCKED GENERATION PLAN:`);
    console.log(`  - Batch ID: ${batchId}`);
    console.log(`  - Models: ${modelsToUse.join(', ')}`);
    console.log(`  - Templates: ${templatesToGenerate.join(', ')}`);
    console.log(`  - Generation Mode: ${generationMode}`);
    console.log(`  - Rerun on Failure: ${frozenRerunOnFailure} (max ${frozenMaxRetries} retries)`);
    console.log(`  - Use Auto-Fix: ${frozenUseAutoFix}`);
    console.log(`  - Total apps: ${totalGenerations}`);
    
    for (const modelSlug of modelsToUse) {
      for (const templateSlug of templatesToGenerate) {
        console.log(`[Wizard] Generating: template ${templateSlug}, model ${modelSlug}`);
        
        // Retry loop with configurable max attempts
        const maxAttempts = frozenRerunOnFailure ? (frozenMaxRetries + 1) : 1;
        let attemptNumber = 0;
        let lastError = null;
        let generationSucceeded = false;
        
        while (attemptNumber < maxAttempts && !generationSucceeded) {
          attemptNumber++;
          if (attemptNumber > 1) {
            console.log(`[Wizard] Retry attempt ${attemptNumber}/${maxAttempts} for ${templateSlug} + ${modelSlug}`);
          }
          
          try {
            // No need to pre-fetch app number - generation service handles atomic reservation
            const response = await fetch('/api/gen/generate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                template_slug: templateSlug,
                model_slug: modelSlug,
                app_num: null,  // Auto-allocate in generation service
                generate_frontend: true,
                generate_backend: true,
                scaffold: true,
                batch_id: batchId,  // Track batch operations together
                version: 1,  // New generation, version 1
                generation_mode: generationMode,  // Include generation mode
                use_auto_fix: frozenUseAutoFix  // Include auto-fix option
              })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
              generationSucceeded = true;
              completed++;
              results.push({
                success: true,
                template_slug: templateSlug,
                model: modelSlug,
                result_id: `${templateSlug}_${modelSlug.replace(/\//g, '_')}`,
                message: attemptNumber > 1 ? `Generated successfully (attempt ${attemptNumber})` : 'Generated successfully',
                batch_id: batchId,
                attempts: attemptNumber,
                // Capture healing and stub file data from API response
                healing: result.data?.healing || null,
                stub_files_created: result.data?.stub_files_created || []
              });
            } else {
              lastError = result.message || result.error || 'Generation failed';
              // Continue to next attempt if retries enabled
            }
          } catch (error) {
            lastError = error.message;
            // Continue to next attempt if retries enabled
          }
        }
        
        // If all attempts failed, record the failure
        if (!generationSucceeded) {
          failed++;
          results.push({
            success: false,
            template_slug: templateSlug,
            model: modelSlug,
            error: frozenRerunOnFailure 
              ? `Failed after ${attemptNumber} attempt(s): ${lastError}`
              : lastError,
            attempts: attemptNumber,
            // Capture any partial healing data from failed attempts
            healing: null,
            stub_files_created: []
          });
        }
          
        // Update progress
        const progressCompleted = completed + failed;
        const progressPercent = (progressCompleted / totalGenerations) * 100;
        updateProgress(progressPercent, progressCompleted, totalGenerations, completed, failed);
      }
    }
    
    showNotification(`Generation completed: ${completed} succeeded, ${failed} failed`, completed === totalGenerations ? 'success' : 'warning');
    
    // Display results
    displayBatchResults({
      results: results,
      batch_id: batchId,  // Include batch ID in results
      progress: {
        completed_tasks: completed,
        failed_tasks: failed,
        total_tasks: totalGenerations
      }
    });
  } catch (error) {
    console.error('Error during generation:', error);
    showNotification('Generation failed: ' + error.message, 'danger');
  } finally {
    // Reset execution flag
    isGenerating = false;
    
    // Restore button state
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.classList.remove('d-none');
    }
    if (loadingBtn) loadingBtn.classList.add('d-none');
  }
}

function updateProgress(percent, completed, total, succeeded, failed) {
  const progressEl = document.getElementById('overall-progress-bar');
  const percentEl = document.getElementById('progress-percentage');
  const progressCompletedEl = document.getElementById('progress-completed');
  const statusCompletedEl = document.getElementById('status-completed');
  const statusFailedEl = document.getElementById('status-failed');
  const statusInProgressEl = document.getElementById('status-in-progress');
  
  if (progressEl) {
    progressEl.style.width = `${percent}%`;
    if (percent >= 100) {
      progressEl.classList.remove('progress-bar-animated');
    }
  }
  if (percentEl) percentEl.textContent = `${Math.round(percent)}%`;
  if (progressCompletedEl) progressCompletedEl.textContent = completed;
  if (statusCompletedEl) statusCompletedEl.textContent = succeeded;
  if (statusFailedEl) statusFailedEl.textContent = failed;
  if (statusInProgressEl) statusInProgressEl.textContent = Math.max(0, total - completed);
}

function displayBatchResults(batchResults) {
  console.log('[Wizard] Displaying batch results:', batchResults);
  
  // Extract data from response structure
  const results = batchResults.results || [];
  const progress = batchResults.progress || {};
  
  console.log('[Wizard] Results array:', results);
  console.log('[Wizard] Progress data:', progress);
  
  if (!results || results.length === 0) {
    console.error('[Wizard] No results in batch response!');
    showNotification('No results returned from generation', 'warning');
    return;
  }
  
  // Update status cards
  const totalGenerations = selectedTemplates.length * selectedModels.length;
  const completedCount = progress.completed_tasks || 0;
  const failedCount = progress.failed_tasks || 0;
  
  console.log('[Wizard] Status update:', { totalGenerations, completedCount, failedCount });
  
  const completedEl = document.getElementById('status-completed');
  const failedEl = document.getElementById('status-failed');
  const inProgressEl = document.getElementById('status-in-progress');
  const totalEl = document.getElementById('status-total');
  
  if (completedEl) completedEl.textContent = completedCount;
  if (failedEl) failedEl.textContent = failedCount;
  if (inProgressEl) inProgressEl.textContent = 0; // All done
  if (totalEl) totalEl.textContent = totalGenerations;
  
  // Update progress bar
  const progressEl = document.getElementById('overall-progress-bar');
  const percentEl = document.getElementById('progress-percentage');
  const progressCompletedEl = document.getElementById('progress-completed');
  const progressTotalEl = document.getElementById('progress-total');
  
  if (progressEl) {
    progressEl.style.width = '100%';
    progressEl.classList.remove('progress-bar-animated');
  }
  if (percentEl) percentEl.textContent = '100%';
  if (progressCompletedEl) progressCompletedEl.textContent = totalGenerations;
  if (progressTotalEl) progressTotalEl.textContent = totalGenerations;
  
  // Build results table
  const resultsTableBody = document.getElementById('generation-results-body');
  const emptyState = document.getElementById('generation-empty-state');
  
  if (resultsTableBody && results.length > 0) {
    resultsTableBody.innerHTML = '';
    
    results.forEach((genResult, index) => {
      console.log(`[Wizard] Processing result ${index + 1}:`, genResult);
      
      const row = document.createElement('tr');
      
      // Check success field explicitly - backend always sets this correctly
      // A result can have result_id but still be unsuccessful (API error, extraction failure, etc.)
      const success = genResult.success === true;
      const hasError = !!genResult.error || !!genResult.error_message;
      
      console.log(`[Wizard] Result ${index + 1} status:`, { 
        success: genResult.success,
        hasError,
        resultId: genResult.result_id,
        model: genResult.model,
        templateSlug: genResult.template_slug
      });
      
      const statusBadge = success
        ? '<span class="badge bg-success"><i class="fas fa-check me-1"></i>Success</span>'
        : '<span class="badge bg-danger"><i class="fas fa-times me-1"></i>Failed</span>';
      
  const templateSlug = genResult.template_slug || genResult.result_id?.split('_')[0];
  const modelSlug = genResult.model || 'Unknown';
  const templateName = templatesCache?.find(t => t.slug === templateSlug)?.name || `Template ${templateSlug}`;
  const matchedModel = modelsCache?.find(m => getModelSlug(m) === modelSlug);
  const modelName = matchedModel?.model_name || matchedModel?.name || modelSlug;
      
      const errorMsg = genResult.error || '';
      const message = errorMsg || genResult.message || (success ? 'Generated successfully' : 'Check logs for details');
      
      row.innerHTML = `
        <td class="text-muted">${index + 1}</td>
        <td><strong>${escapeHtml(templateName)}</strong></td>
        <td><code class="small">${escapeHtml(modelSlug)}</code></td>
        <td>${statusBadge}</td>
        <td class="text-muted small" style="max-width: 400px; word-wrap: break-word;">${escapeHtml(message)}</td>
      `;
      
      resultsTableBody.appendChild(row);
    });
    
    if (emptyState) emptyState.classList.add('d-none');
  } else if (emptyState) {
    emptyState.classList.remove('d-none');
  }
  
  // =========================================================================
  // Populate Healing Results and Stub Files UI Sections
  // =========================================================================
  
  // Aggregate healing data from all results
  const allHealing = results
    .filter(r => r.healing && typeof r.healing === 'object')
    .map(r => ({ model: r.model, healing: r.healing }));
  
  // Aggregate stub files from all results
  const allStubFiles = results.flatMap(r => {
    if (Array.isArray(r.stub_files_created) && r.stub_files_created.length > 0) {
      return r.stub_files_created.map(sf => ({
        ...sf,
        model: r.model
      }));
    }
    return [];
  });
  
  // Update Healing Results Section
  const healingSection = document.getElementById('healing-results-section');
  const healingList = document.getElementById('healing-results-list');
  const healingBadge = document.getElementById('healing-count-badge');
  
  if (healingSection && healingList && healingBadge) {
    if (allHealing.length > 0) {
      // Count total fixes applied
      let totalFixes = 0;
      healingList.innerHTML = '';
      
      allHealing.forEach(item => {
        const h = item.healing;
        const fixes = [];
        
        // Extract meaningful healing information
        if (h.dependencies_added && h.dependencies_added.length > 0) {
          fixes.push(`Dependencies added: ${h.dependencies_added.join(', ')}`);
          totalFixes += h.dependencies_added.length;
        }
        if (h.imports_fixed && h.imports_fixed.length > 0) {
          fixes.push(`Imports fixed: ${h.imports_fixed.length}`);
          totalFixes += h.imports_fixed.length;
        }
        if (h.syntax_errors_fixed && h.syntax_errors_fixed.length > 0) {
          fixes.push(`Syntax errors fixed: ${h.syntax_errors_fixed.length}`);
          totalFixes += h.syntax_errors_fixed.length;
        }
        if (h.files_healed && h.files_healed.length > 0) {
          fixes.push(`Files healed: ${h.files_healed.join(', ')}`);
          totalFixes += h.files_healed.length;
        }
        if (h.jsx_extensions_added > 0) {
          fixes.push(`JSX extensions added: ${h.jsx_extensions_added}`);
          totalFixes += h.jsx_extensions_added;
        }
        if (h.missing_exports_stubbed > 0) {
          fixes.push(`Missing exports stubbed: ${h.missing_exports_stubbed}`);
          totalFixes += h.missing_exports_stubbed;
        }
        
        // If no specific fixes but healing object exists, show generic message
        if (fixes.length === 0 && Object.keys(h).length > 0) {
          fixes.push('Auto-fix applied (see logs for details)');
          totalFixes += 1;
        }
        
        if (fixes.length > 0) {
          const li = document.createElement('li');
          li.className = 'mb-2';
          li.innerHTML = `
            <strong><code class="small">${escapeHtml(item.model)}</code></strong>:
            <ul class="mb-0 mt-1">
              ${fixes.map(f => `<li class="small text-muted">${escapeHtml(f)}</li>`).join('')}
            </ul>
          `;
          healingList.appendChild(li);
        }
      });
      
      healingBadge.textContent = `${totalFixes} fix${totalFixes !== 1 ? 'es' : ''}`;
      healingSection.style.display = 'block';
    } else {
      healingSection.style.display = 'none';
    }
  }
  
  // Update Stub Files Section
  const stubSection = document.getElementById('stub-files-section');
  const stubList = document.getElementById('stub-files-list');
  const stubBadge = document.getElementById('stub-files-count-badge');
  
  if (stubSection && stubList && stubBadge) {
    if (allStubFiles.length > 0) {
      stubList.innerHTML = '';
      
      allStubFiles.forEach(sf => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><code class="small">${escapeHtml(sf.path || sf.file || 'Unknown')}</code></td>
          <td class="text-muted small">${escapeHtml(sf.reason || 'Missing dependency')}</td>
        `;
        stubList.appendChild(tr);
      });
      
      stubBadge.textContent = `${allStubFiles.length} file${allStubFiles.length !== 1 ? 's' : ''}`;
      stubSection.style.display = 'block';
    } else {
      stubSection.style.display = 'none';
    }
  }
  
  // Show summary notification
  const successCount = results.filter(r => {
    const hasResultId = !!r.result_id;
    const hasError = !!r.error;
    return hasResultId && !hasError;
  }).length;
  
  if (failedCount > 0) {
    showNotification(`Completed ${successCount}/${totalGenerations} generations (${failedCount} failed)`, 'warning');
  } else {
    showNotification(`All ${successCount} generations completed successfully!`, 'success');
  }
}

// ============================================================================
// Sidebar Updates
// ============================================================================

function updateSidebar() {
  // Update scaffolding display
  const scaffoldingBadge = document.getElementById('sidebar-scaffolding-badge');
  const scaffoldingName = document.getElementById('sidebar-scaffolding-name');
  if (scaffoldingBadge && scaffoldingName) {
    if (selectedScaffolding) {
      scaffoldingBadge.textContent = 'Selected';
      scaffoldingBadge.className = 'badge bg-success-lt';
      scaffoldingName.textContent = 'Default Full-Stack';
    } else {
      scaffoldingBadge.textContent = 'None';
      scaffoldingBadge.className = 'badge bg-secondary-lt';
      scaffoldingName.textContent = '-';
    }
  }
  
  // Update templates list
  const templateCount = document.getElementById('sidebar-template-count');
  const templateList = document.getElementById('sidebar-template-list');
  const clearTemplatesBtn = document.getElementById('clear-templates-btn');
  
  if (templateCount) {
    templateCount.textContent = selectedTemplates.length;
  }
  
  if (templateList) {
    if (selectedTemplates.length === 0) {
      templateList.innerHTML = '<li class="text-muted">No templates selected</li>';
    } else {
      const items = selectedTemplates.slice(0, 10).map(slug => {
        const template = templatesCache?.find(t => t.slug === slug);
        const displayName = template?.name || template?.display_name || slug;
        return `<li class='d-flex align-items-center justify-content-between'>
          <span class='text-truncate me-2'>${escapeHtml(displayName)}</span>
          <button type='button' class='btn btn-link p-0 text-danger small' onclick="unselectTemplate('${escapeHtml(slug)}')" aria-label='Remove template'>&times;</button>
        </li>`;
      }).join('');
      const more = selectedTemplates.length > 10 ? `<li class='text-muted small'>+${selectedTemplates.length - 10} more...</li>` : '';
      templateList.innerHTML = items + more;
    }
  }
  
  if (clearTemplatesBtn) {
    clearTemplatesBtn.classList.toggle('d-none', selectedTemplates.length === 0);
  }
  
  // Update models list
  const modelCount = document.getElementById('sidebar-model-count');
  const modelList = document.getElementById('sidebar-model-list');
  const clearModelsBtn = document.getElementById('clear-models-btn');
  
  if (modelCount) {
    modelCount.textContent = selectedModels.length;
  }
  
  if (modelList) {
    if (selectedModels.length === 0) {
      modelList.innerHTML = '<li class="text-muted">No models selected</li>';
    } else {
      const items = selectedModels.slice(0, 10).map(slug => {
        const model = modelsCache?.find(m => getModelSlug(m) === slug);
        const displayName = model?.model_name || model?.name || slug;
        return `<li class='d-flex align-items-center justify-content-between'>
          <span class='text-truncate me-2'>${escapeHtml(displayName)}</span>
          <button type='button' class='btn btn-link p-0 text-danger small' onclick="unselectModel('${slug}')" aria-label='Remove model'>&times;</button>
        </li>`;
      }).join('');
      const more = selectedModels.length > 10 ? `<li class='text-muted small'>+${selectedModels.length - 10} more...</li>` : '';
      modelList.innerHTML = items + more;
    }
  }
  
  if (clearModelsBtn) {
    clearModelsBtn.classList.toggle('d-none', selectedModels.length === 0);
  }
  
  // Sync summary card values
  updateGenerationSummary();
}

// ============================================================================
// Utility Functions
// ============================================================================

function showNotification(message, type = 'info') {
  // Create toast notification
  const toast = document.createElement('div');
  toast.className = `alert alert-${type} alert-dismissible position-fixed top-0 end-0 m-3`;
  toast.style.zIndex = '9999';
  toast.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  
  document.body.appendChild(toast);
  
  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    toast.remove();
  }, 5000);
}

// ============================================================================
// Management Functions (for other tabs)
// ============================================================================

function refreshScaffoldings() {
  showNotification('Scaffoldings refreshed', 'info');
}

function viewScaffoldingDetails(scaffoldingId) {
  console.log('View scaffolding:', scaffoldingId);
}

function refreshTemplates() {
  loadTemplates();
  showNotification('Templates refreshed', 'info');
}

function searchTemplates() {
  // Implement template search
  const searchTerm = document.getElementById('template-search')?.value.toLowerCase();
  // Filter and re-render template list
}

function createTemplate() {
  // Open modal for creating new template
  const modal = new bootstrap.Modal(document.getElementById('template-modal'));
  modal.show();
}

function viewTemplate(templateId) {
  console.log('View template:', templateId);
}

function editTemplate(templateId) {
  console.log('Edit template:', templateId);
}

function deleteTemplate(templateId) {
  if (confirm('Are you sure you want to delete this template?')) {
    console.log('Delete template:', templateId);
  }
}

function saveTemplate() {
  showNotification('Template saved successfully', 'success');
}

// ============================================================================
// Utility Functions
// ============================================================================

function setTextContent(id, value) {
  const el = document.getElementById(id);
  if (!el) {
    return;
  }
  if (value === undefined || value === null) {
    el.textContent = '–';
  } else {
    el.textContent = value;
  }
}

function getModelSlug(model) {
  if (!model) {
    return '';
  }
  const candidates = [model.slug, model.canonical_slug, model.model_id, model.id, model.model_name, model.name];
  const slug = candidates.find(val => typeof val === 'string' && val.trim().length > 0);
  return slug ? String(slug).trim() : '';
}

function normalizeModelCost(model) {
  if (!model) {
    return null;
  }
  if (typeof model.input_price_per_1k === 'number') {
    return Number(model.input_price_per_1k);
  }
  if (typeof model.input_price_per_token === 'number') {
    return Number(model.input_price_per_token) * 1000;
  }
  const pricing = model.pricing || (model.openrouter && model.openrouter.pricing) || null;
  const extracted = extractPricingValue(pricing, ['input', 'prompt', 'input_cost', 'prompt_cost', 'input_price_per_1k', 'prompt_price_per_1k']);
  return typeof extracted === 'number' ? extracted : null;
}

function normalizeModelOutputCost(model) {
  if (!model) {
    return null;
  }
  if (typeof model.output_price_per_1k === 'number') {
    return Number(model.output_price_per_1k);
  }
  if (typeof model.output_price_per_token === 'number') {
    return Number(model.output_price_per_token) * 1000;
  }
  const pricing = model.pricing || (model.openrouter && model.openrouter.pricing) || null;
  const extracted = extractPricingValue(pricing, ['output', 'completion', 'output_cost', 'completion_cost', 'output_price_per_1k', 'completion_price_per_1k']);
  return typeof extracted === 'number' ? extracted : null;
}

function extractPricingValue(pricing, keys) {
  if (!pricing || typeof pricing !== 'object') {
    return null;
  }
  for (const key of keys) {
    const raw = pricing[key];
    if (raw === undefined || raw === null) {
      continue;
    }
    const numeric = Number(raw);
    if (!Number.isNaN(numeric)) {
      return numeric;
    }
  }
  const usdPricing = pricing.usd;
  if (usdPricing && typeof usdPricing === 'object') {
    for (const key of keys) {
      const raw = usdPricing[key];
      if (raw === undefined || raw === null) {
        continue;
      }
      const numeric = Number(raw);
      if (!Number.isNaN(numeric)) {
        return numeric;
      }
    }
  }
  return null;
}

function formatCost(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '–';
  }
  if (value === 0) {
    return 'free';
  }
  const absVal = Math.abs(value);
  let decimals = 2;
  if (absVal < 10) decimals = 3;
  if (absVal < 1) decimals = 4;
  if (absVal < 0.1) decimals = 5;
  if (absVal < 0.01) decimals = 6;
  const fixed = value.toFixed(decimals);
  const trimmed = fixed.replace(/(\.\d*?[1-9])0+$/, '$1').replace(/\.0+$/, '');
  return `$${trimmed}`;
}

function formatCostRange(min, max) {
  if (min === null || min === undefined || max === null || max === undefined) {
    return '–';
  }
  if (min === max) {
    return formatCost(min);
  }
  return `${formatCost(min)} – ${formatCost(max)}`;
}

function escapeHtml(text) {
  if (text === null || text === undefined) {
    return '';
  }
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  const str = String(text);
  return str.replace(/[&<>"']/g, function(m) { return map[m]; });
}

function unselectTemplate(slug) {
  selectedTemplates = selectedTemplates.filter(s => s !== slug);
  updateSidebar();
  updateNavigationButtons();
  updateTemplateSelectionUI();
  
  // Update checkbox if visible
  const checkbox = document.querySelector(`input[data-template-slug="${slug}"]`);
  if (checkbox) {
    checkbox.checked = false;
  }
}

function unselectModel(slug) {
  selectedModels = selectedModels.filter(s => s !== slug);
  updateSidebar();
  updateNavigationButtons();
  
  // Update checkbox if visible
  const checkbox = document.querySelector(`input[data-model="${slug}"]`);
  if (checkbox) {
    checkbox.checked = false;
  }
}

function filterTemplates(searchTerm) {
  const term = (searchTerm || '').toLowerCase().trim();
  const items = document.querySelectorAll('#template-selection-list .template-item');
  
  items.forEach(item => {
    const slug = (item.getAttribute('data-template-slug') || '').toLowerCase();
    const text = item.textContent.toLowerCase();
    const visible = !term || slug.includes(term) || text.includes(term);
    item.style.display = visible ? '' : 'none';
  });
}

function filterModels(searchTerm) {
  const term = (searchTerm || '').toLowerCase().trim();
  const items = document.querySelectorAll('#model-selection-list .model-item');
  const headers = document.querySelectorAll('#model-selection-list .provider-header');
  
  // Track visible providers
  const visibleProviders = new Set();
  
  items.forEach(item => {
    const slug = (item.getAttribute('data-model-slug') || '').toLowerCase();
    const text = item.textContent.toLowerCase();
    const provider = item.getAttribute('data-provider');
    const visible = !term || slug.includes(term) || text.includes(term);
    item.style.display = visible ? '' : 'none';
    if (visible && provider) {
      visibleProviders.add(provider);
    }
  });
  
  // Show/hide provider headers based on visible models
  headers.forEach(header => {
    const provider = header.getAttribute('data-provider');
    header.style.display = (!term || visibleProviders.has(provider)) ? '' : 'none';
  });
}

// ============================================================================
// Past Generations Table Functions
// ============================================================================

async function loadPastGenerations(limit = null) {
  const tbody = document.getElementById('past-generations-tbody');
  const countEl = document.getElementById('past-generations-count');
  
  if (!tbody) return;
  
  // Get limit from dropdown if not provided
  if (!limit) {
    const limitSelect = document.getElementById('past-generations-per-page');
    limit = limitSelect ? limitSelect.value : 10;
  }
  
  // Show loading state
  tbody.innerHTML = `
    <tr>
      <td colspan="7" class="text-center py-4">
        <div class="spinner-border text-primary" role="status"></div>
        <p class="small text-muted mt-2 mb-0">Loading past generations...</p>
      </td>
    </tr>
  `;
  
  try {
    const response = await fetch(`/sample-generator/api/proxy/recent?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    const recent = data.data || [];
    
    // Update count
    if (countEl) {
      countEl.textContent = recent.length;
    }
    
    if (recent.length === 0) {
      tbody.innerHTML = `
        <tr id="past-generations-empty">
          <td colspan="7" class="text-center py-5">
            <div class="empty py-4">
              <div class="empty-icon">
                <i class="fas fa-history fa-3x text-muted"></i>
              </div>
              <p class="empty-title h5">No past generations</p>
              <p class="empty-subtitle text-muted">Generated applications will appear here</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }
    
    // Render rows
    tbody.innerHTML = recent.map(r => {
      const timestamp = formatTimestamp(r.timestamp);
      const appName = r.app_name || `App #${r.app_num || '?'}`;
      const model = r.model || '—';
      const duration = r.duration ? `${r.duration.toFixed(1)}s` : '—';
      const errorMessage = r.error_message || '';
      const resultId = r.result_id || `${r.model}_app${r.app_num}`;
      
      // Determine status badge based on status field
      let statusBadge;
      const status = r.status || (r.success ? 'completed' : 'pending');
      switch (status) {
        case 'completed':
          statusBadge = '<span class="badge bg-success-lt text-success"><i class="fas fa-check me-1"></i>Success</span>';
          break;
        case 'failed':
          statusBadge = '<span class="badge bg-danger-lt text-danger"><i class="fas fa-times me-1"></i>Failed</span>';
          break;
        case 'running':
          statusBadge = '<span class="badge bg-info-lt text-info"><i class="fas fa-spinner fa-spin me-1"></i>Running</span>';
          break;
        default:
          statusBadge = '<span class="badge bg-warning-lt text-warning"><i class="fas fa-clock me-1"></i>Pending</span>';
      }
      
      // Render error message cell
      const errorCell = errorMessage 
        ? `<span class="text-truncate d-inline-block" style="max-width: 240px;" title="${escapeHtml(errorMessage)}">${escapeHtml(errorMessage)}</span>`
        : '<span class="text-muted">—</span>';
      
      return `
        <tr>
          <td class="text-muted small text-nowrap">${escapeHtml(timestamp)}</td>
          <td><strong>${escapeHtml(appName)}</strong></td>
          <td><span class="badge bg-azure-lt text-azure">${escapeHtml(model)}</span></td>
          <td class="text-center">${statusBadge}</td>
          <td class="text-muted small" style="max-width: 250px;">${errorCell}</td>
          <td class="text-end text-muted small">${escapeHtml(duration)}</td>
          <td>
            <div class="btn-group btn-group-sm" role="group">
              <button type="button" class="btn btn-ghost-primary btn-icon"
                      onclick="viewGenerationResult('${escapeHtml(resultId)}')"
                      title="View details">
                <i class="fas fa-eye"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
    
  } catch (error) {
    console.error('[Wizard] Error loading past generations:', error);
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center py-4 text-danger">
          <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
          <p class="fw-bold mb-1">Error loading past generations</p>
          <p class="small mb-2">${escapeHtml(error.message)}</p>
          <button class="btn btn-sm btn-outline-primary" onclick="loadPastGenerations()">
            <i class="fas fa-sync me-1"></i>Retry
          </button>
        </td>
      </tr>
    `;
  }
}

function viewGenerationResult(resultId) {
  if (!resultId) {
    showNotification('No result ID available', 'warning');
    return;
  }
  
  console.log('[Wizard] View generation result:', resultId);
  
  // Parse the result ID to extract model slug and app number
  // Format is typically: {model_slug}_app{app_num} e.g., "anthropic_claude-3-5-haiku-20241022_app1"
  const appMatch = resultId.match(/^(.+)_app(\d+)$/);
  
  if (appMatch) {
    const modelSlug = appMatch[1];
    const appNum = appMatch[2];
    
    // Navigate to the application detail page
    window.location.href = `/applications/${encodeURIComponent(modelSlug)}/${appNum}`;
  } else {
    // Fallback: try to use the whole resultId as model slug with app 1
    // or show the applications page with a search filter
    showNotification(`Navigating to applications with result: ${resultId}`, 'info');
    window.location.href = `/applications?search=${encodeURIComponent(resultId)}`;
  }
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  
  // If it's already a string, return as is
  if (typeof ts === 'string') {
    // Try to parse and format
    try {
      const date = new Date(ts);
      if (!isNaN(date.getTime())) {
        return date.toLocaleString('en-US', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false
        });
      }
    } catch (e) {
      // Return original string if parsing fails
    }
    return ts;
  }
  
  // If it's a Date object
  if (ts instanceof Date) {
    return ts.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  }
  
  return '—';
}

// Export functions for global access
window.nextStep = nextStep;
window.previousStep = previousStep;
window.goToStep = goToStep;
window.selectScaffolding = selectScaffolding;
window.selectGenerationMode = selectGenerationMode;
window.updateAdvancedOption = updateAdvancedOption;
window.toggleTemplateSelection = toggleTemplateSelection;
window.selectAllTemplates = selectAllTemplates;
window.clearAllTemplates = clearAllTemplates;
window.toggleModelSelection = toggleModelSelection;
window.selectAllModels = selectAllModels;
window.clearAllModels = clearAllModels;
window.unselectTemplate = unselectTemplate;
window.unselectModel = unselectModel;
window.filterTemplates = filterTemplates;
window.filterModels = filterModels;
window.startGeneration = startGeneration;
window.refreshScaffoldings = refreshScaffoldings;
window.viewScaffoldingDetails = viewScaffoldingDetails;
window.refreshTemplates = refreshTemplates;
window.searchTemplates = searchTemplates;
window.createTemplate = createTemplate;
window.viewTemplate = viewTemplate;
window.editTemplate = editTemplate;
window.deleteTemplate = deleteTemplate;
window.saveTemplate = saveTemplate;
window.initSampleGeneratorWizard = initSampleGeneratorWizard;
window.loadPastGenerations = loadPastGenerations;
window.viewGenerationResult = viewGenerationResult;
})();
