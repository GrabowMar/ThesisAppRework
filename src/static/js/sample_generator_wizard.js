// Sample Generator Wizard JavaScript
// Handles wizard navigation, form validation, and generation management

// ============================================================================
// State Management
// ============================================================================

let currentStep = 1;
let selectedScaffolding = null;
let selectedTemplates = [];
let selectedModels = [];

// Cache for templates and models
let templatesCache = null;
let modelsCache = null;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  console.log('Sample Generator Wizard initialized');
  initializeWizard();
  loadInitialData();
});

function initializeWizard() {
  updateWizardStep();
  updateNavigationButtons();
  
  // Auto-select default scaffolding
  selectScaffolding('default');
}

async function loadInitialData() {
  try {
    // Load templates
        console.log('[Wizard] Loading templates from /api/gen/templates...');

    const templatesResponse = await fetch('/api/gen/templates');
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
    
    // Load models - use the actual working endpoint
    console.log('[Wizard] Loading models from /api/models...');
    const modelsResponse = await fetch('/api/models');
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
  } catch (error) {
    console.error('[Wizard] Error loading initial data:', error);
    templatesCache = [];
    modelsCache = [];
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
    console.log('[Wizard] Step 3: Start button disabled:', !stepValid);
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
// Step 2: Templates and Models Selection
// ============================================================================

async function loadTemplatesAndModels() {
  await loadTemplates();
  await loadModels();
}

async function loadTemplates() {
  const listContainer = document.getElementById('template-selection-list');
  if (!listContainer) return;
  
  listContainer.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary"></div><p class="small text-muted mt-2">Loading templates...</p></div>';
  
  try {
    console.log('[Wizard] Loading templates from /api/gen/templates...');
    const response = await fetch('/api/gen/templates');
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
    
    listContainer.innerHTML = '';
    
    if (templates.length === 0) {
      listContainer.innerHTML = '<div class="text-center text-muted p-4"><i class="fas fa-info-circle fa-2x mb-2 opacity-50"></i><p>No templates available</p><p class="small">Templates should be in <code>misc/app_templates/</code></p></div>';
      return;
    }
    
    // Map V2 requirements to wizard template format
    templates.forEach((template, index) => {
      // V2 uses string IDs, map to numeric app_num for wizard compatibility
      template.app_num = index + 1;
      template.display_name = template.name;
    });
    
    // Update cache with modified templates
    templatesCache = templates;
    console.log('[Wizard] Templates cache updated:', templatesCache.map(t => ({ id: t.id, app_num: t.app_num, name: t.name })));

    if (selectedTemplates.length) {
      const validAppNums = new Set(templates.map(t => t.app_num));
      selectedTemplates = selectedTemplates.filter(num => validAppNums.has(num));
    }
    
    // Render items
    templates.forEach(template => {
      const item = createTemplateListItem(template);
      listContainer.appendChild(item);
    });
  console.log('[Wizard] Templates UI updated with V2 requirements');
  console.log('[Wizard] Template items added to wizard list, ready for clicks');  
  updateSidebar();
  updateNavigationButtons();
  } catch (error) {
    console.error('[Wizard] Error loading templates:', error);
    listContainer.innerHTML = `<div class="text-center text-danger p-4"><i class="fas fa-exclamation-triangle fa-2x mb-2"></i><p class="fw-bold">Error loading templates</p><p class="small">${error.message}</p><button class="btn btn-sm btn-outline-primary mt-2" onclick="loadTemplates()">Retry</button></div>`;
  }
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
  // Re-render all items with updated selection state
  if (templatesCache && templatesCache.length > 0) {
    const listContainer = document.getElementById('template-selection-list');
    if (listContainer) {
      listContainer.innerHTML = '';
      templatesCache.forEach(template => {
        const item = createTemplateListItem(template);
        listContainer.appendChild(item);
      });
    }
  }
}

function updateModelSelectionUI() {
  // Re-render all items with updated selection state
  if (modelsCache && modelsCache.length > 0) {
    const listContainer = document.getElementById('model-selection-list');
    if (listContainer) {
      listContainer.innerHTML = '';
      modelsCache.forEach(model => {
        const item = createModelListItem(model);
        listContainer.appendChild(item);
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
      listContainer.innerHTML = '<div class="text-center text-muted p-4"><i class="fas fa-info-circle fa-2x mb-2 opacity-50"></i><p>No models available</p><p class="small">Check database for model capabilities</p></div>';
      return;
    }

    models.forEach(model => {
      const item = createModelListItem(model);
      listContainer.appendChild(item);
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
  if (!validateCurrentStep()) {
    showNotification('Please complete all previous steps', 'warning');
    return;
  }
  
  console.log('[Wizard] Starting batch generation');
  
  // Show loading state
  const startBtn = document.getElementById('start-btn');
  const loadingBtn = document.getElementById('start-btn-loading');
  if (startBtn) startBtn.classList.add('d-none');
  if (loadingBtn) loadingBtn.classList.remove('d-none');
  
  // Calculate total and prepare tracking
  const totalGenerations = selectedTemplates.length * selectedModels.length;
  const totalEl = document.getElementById('progress-total');
  const statusTotalEl = document.getElementById('status-total');
  if (totalEl) totalEl.textContent = totalGenerations;
  if (statusTotalEl) statusTotalEl.textContent = totalGenerations;
  
  const results = [];
  let completed = 0;
  let failed = 0;
  
  try {
    // Generate each combination
    for (const templateSlug of selectedTemplates) {
      for (const modelSlug of selectedModels) {
        console.log(`[Wizard] Generating: template ${templateSlug}, model ${modelSlug}`);
        
        try {
          // Get template type preference
          const templateTypeEl = document.getElementById('template-type-preference');
          const templateType = templateTypeEl ? templateTypeEl.value : 'auto';
          
          const response = await fetch('/api/gen/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              template_slug: templateSlug,
              model_slug: modelSlug,
              app_num: Date.now() % 10000,  // Use random app number
              generate_frontend: true,
              generate_backend: true,
              scaffold: true,
              template_type: templateType  // 'auto', 'full', or 'compact'
            })
          });
          
          const result = await response.json();
          
          if (response.ok && result.success) {
            completed++;
            results.push({
              success: true,
              template_slug: templateSlug,
              model: modelSlug,
              result_id: `${templateSlug}_${modelSlug.replace(/\//g, '_')}`,
              message: 'Generated successfully'
            });
          } else {
            failed++;
            results.push({
              success: false,
              template_slug: templateSlug,
              model: modelSlug,
              error: result.message || result.error || 'Generation failed'
            });
          }
        } catch (error) {
          failed++;
          results.push({
            success: false,
            template_slug: templateSlug,
            model: modelSlug,
            error: error.message
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
    // Restore button state
    if (startBtn) startBtn.classList.remove('d-none');
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
      const items = selectedTemplates.slice(0, 10).map(appNum => {
        const template = templatesCache?.find(t => t.app_num === appNum);
        const displayName = template?.display_name || `App ${appNum}`;
        return `<li class='d-flex align-items-center justify-content-between'>
          <span class='text-truncate me-2'>${escapeHtml(displayName)}</span>
          <button type='button' class='btn btn-link p-0 text-danger small' onclick="unselectTemplate(${appNum})" aria-label='Remove template'>&times;</button>
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

function unselectTemplate(appNum) {
  selectedTemplates = selectedTemplates.filter(num => num !== appNum);
  updateSidebar();
  updateNavigationButtons();
  
  // Update checkbox if visible
  const checkbox = document.querySelector(`input[data-template="${appNum}"]`);
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
  const term = searchTerm.toLowerCase();
  const items = document.querySelectorAll('#template-selection-list .list-group-item');
  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = text.includes(term) ? '' : 'none';
  });
}

function filterModels(searchTerm) {
  const term = searchTerm.toLowerCase();
  const items = document.querySelectorAll('#model-selection-list .list-group-item');
  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = text.includes(term) ? '' : 'none';
  });
}

// Export functions for global access
window.nextStep = nextStep;
window.previousStep = previousStep;
window.goToStep = goToStep;
window.selectScaffolding = selectScaffolding;
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
