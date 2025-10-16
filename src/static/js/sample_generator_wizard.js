// Sample Generator Wizard JavaScript
// Handles wizard navigation, form validation, and generation management

// ============================================================================
// State Management
// ============================================================================

let currentStep = 1;
let selectedScaffolding = null;
let selectedTemplates = [];
let selectedModels = [];
let generationBatchId = null;
let statusPollInterval = null;

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
      
      // Handle standardized API envelope: {success: true, data: [...], message: "..."}
      if (templatesData.success && templatesData.data) {
        templatesCache = Array.isArray(templatesData.data) ? templatesData.data : [];
      } else if (Array.isArray(templatesData)) {
        templatesCache = templatesData;
      } else if (templatesData.templates && Array.isArray(templatesData.templates)) {
        templatesCache = templatesData.templates;
      } else {
        console.warn('[Wizard] Unexpected templates response format:', templatesData);
        templatesCache = [];
      }
      console.log(`[Wizard] Loaded ${templatesCache.length} templates`);
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
  
  // Previous button availability
  prevBtn.disabled = currentStep === 1;
  
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
  updateGenerationMatrix();
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
      const item = createTemplateListItem(template);
      listContainer.appendChild(item);
    });
    console.log('[Wizard] Templates UI updated with V2 requirements');  
  } catch (error) {
    console.error('[Wizard] Error loading templates:', error);
    listContainer.innerHTML = `<div class="text-center text-danger p-4"><i class="fas fa-exclamation-triangle fa-2x mb-2"></i><p class="fw-bold">Error loading templates</p><p class="small">${error.message}</p><button class="btn btn-sm btn-outline-primary mt-2" onclick="loadTemplates()">Retry</button></div>`;
  }
}

function createTemplateListItem(template) {
  const item = document.createElement('a');
  item.href = '#';
  item.className = 'list-group-item list-group-item-action';
  
  // Safe property access with better fallbacks, ensure numeric app_num
  let appNum = template.app_num || template.number || 0;
  appNum = typeof appNum === 'string' ? parseInt(appNum, 10) : appNum;
  const name = template.display_name || template.name || template.title || `Template ${appNum}`;
  const templateType = 'both'; // V2 requirements generate both backend and frontend
  const description = template.description || template.desc || '';
  const requirementId = template.id || ''; // Store V2 requirement ID
  
  // Store the app_num and requirement_id as data attributes
  item.setAttribute('data-app-num', appNum);
  if (requirementId) {
    item.setAttribute('data-requirement-id', requirementId);
  }
  
  // Add click handler using addEventListener instead of onclick
  item.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const templateAppNum = parseInt(item.getAttribute('data-app-num'), 10);
    if (templateAppNum) {
      toggleTemplateSelection(templateAppNum);
    }
  });
  
  // Ensure consistent numeric comparison
  const isSelected = selectedTemplates.includes(appNum);
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
  
  const descriptionHtml = description ? `<div class="text-muted small mt-1">${escapeHtml(description.slice(0, 100))}${description.length > 100 ? '...' : ''}</div>` : '';
  
  item.innerHTML = `
    <div class="d-flex align-items-center">
      <div class="flex-fill">
        <strong>${escapeHtml(name)}</strong>
        <div class="text-muted small">${typeBadge} <span class="text-muted">App #${appNum}</span></div>
        ${descriptionHtml}
      </div>
      <div class="form-check">
        <input class="form-check-input" type="checkbox" ${isSelected ? 'checked' : ''}>
      </div>
    </div>
  `;
  
  return item;
}

function toggleTemplateSelection(appNum) {
  console.log('[Wizard] Toggle template:', appNum, 'Type:', typeof appNum);
  console.log('[Wizard] Current selected templates length:', selectedTemplates.length);
  
  // Ensure appNum is a number for consistent comparison
  const numericAppNum = typeof appNum === 'string' ? parseInt(appNum, 10) : appNum;
  
  const index = selectedTemplates.indexOf(numericAppNum);
  if (index > -1) {
    selectedTemplates.splice(index, 1);
    console.log('[Wizard] Removed template:', numericAppNum, 'New count:', selectedTemplates.length);
  } else {
    selectedTemplates.push(numericAppNum);
    console.log('[Wizard] Added template:', numericAppNum, 'New count:', selectedTemplates.length);
  }
  
  console.log('[Wizard] Updated selected templates count:', selectedTemplates.length, 'First few:', selectedTemplates.slice(0, 3));
  
  // Only update UI elements, don't reload entire list
  updateTemplateSelectionUI();
  updateGenerationMatrix();
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
    // Extract app_num with multiple fallbacks and ensure it's a number
    selectedTemplates = templatesCache.map(t => {
      const appNum = t.app_num || t.id || t.number || 0;
      return typeof appNum === 'string' ? parseInt(appNum, 10) : appNum;
    }).filter(num => num > 0); // Remove any invalid entries
    console.log('[Wizard] Selected all templates:', selectedTemplates);
    loadTemplates();
    updateGenerationMatrix();
    updateSidebar();
    updateNavigationButtons();
  }
}

function clearAllTemplates() {
  selectedTemplates = [];
  loadTemplates();
  updateGenerationMatrix();
  updateSidebar();
  updateNavigationButtons();
}

async function loadModels() {
  const listContainer = document.getElementById('model-selection-list');
  if (!listContainer) return;
  
  listContainer.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary"></div><p class="small text-muted mt-2">Loading models...</p></div>';
  
  try {
    console.log('[Wizard] Loading models...');
    // Use the correct models endpoint
    const response = await fetch('/api/models');
    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Wizard] Model load error:', response.status, errorText);
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('[Wizard] Models data received:', data);
    
    // Handle standardized API envelope
    let models = [];
    if (data.success && data.data) {
      models = Array.isArray(data.data) ? data.data : [];
    } else if (Array.isArray(data)) {
      models = data;
    } else if (data.models && Array.isArray(data.models)) {
      models = data.models;
    }
    
    modelsCache = models;
    console.log(`[Wizard] Parsed ${models.length} models`);
    
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
  } catch (error) {
    console.error('[Wizard] Error loading models:', error);
    listContainer.innerHTML = `<div class="text-center text-danger p-4"><i class="fas fa-exclamation-triangle fa-2x mb-2"></i><p class="fw-bold">Error loading models</p><p class="small">${error.message}</p><button class="btn btn-sm btn-outline-primary mt-2" onclick="loadModels()">Retry</button></div>`;
  }
}

function createModelListItem(model) {
  const item = document.createElement('a');
  item.href = '#';
  item.className = 'list-group-item list-group-item-action';
  
  // Safe property access with better fallbacks, ensure string slug
  let slug = model.canonical_slug || model.slug || model.id || model.model_id || 'unknown';
  slug = String(slug);
  const name = model.model_name || model.name || model.display_name || slug;
  const provider = model.provider || 'Unknown';
  const capabilities = model.capabilities || [];
  
  // Store the slug as a data attribute for easier access
  item.setAttribute('data-model-slug', slug);
  
  // Add click handler using addEventListener instead of onclick
  item.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const modelSlug = item.getAttribute('data-model-slug');
    if (modelSlug) {
      toggleModelSelection(modelSlug);
    }
  });
  
  // Ensure consistent string comparison
  const isSelected = selectedModels.includes(slug);
  if (isSelected) {
    item.classList.add('active');
  }
  
  const providerBadge = `<span class="badge bg-azure-lt"><i class="fas fa-building me-1"></i>${escapeHtml(provider)}</span>`;
  
  // Show capabilities if available
  let capabilitiesBadges = '';
  if (Array.isArray(capabilities) && capabilities.length > 0) {
    capabilitiesBadges = capabilities.slice(0, 3).map(cap => 
      `<span class="badge bg-secondary-lt ms-1">${escapeHtml(cap)}</span>`
    ).join('');
    if (capabilities.length > 3) {
      capabilitiesBadges += `<span class="badge bg-secondary-lt ms-1">+${capabilities.length - 3}</span>`;
    }
  }
  
  item.innerHTML = `
    <div class="d-flex align-items-center">
      <div class="flex-fill">
        <strong>${escapeHtml(name)}</strong>
        <div class="text-muted small">
          ${providerBadge}
          ${capabilitiesBadges}
        </div>
        <div class="text-muted small"><code class="small">${escapeHtml(slug)}</code></div>
      </div>
      <div class="form-check">
        <input class="form-check-input" type="checkbox" ${isSelected ? 'checked' : ''}>
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
  updateGenerationMatrix();
  updateSidebar();
  updateNavigationButtons();
}

function selectAllModels() {
  if (modelsCache) {
    console.log('[Wizard] Select all models, cache:', modelsCache);
    // Extract slug with multiple fallbacks and ensure it's a string
    selectedModels = modelsCache.map(m => {
      const slug = m.canonical_slug || m.slug || m.id || m.model_id || 'unknown';
      return String(slug);
    }).filter(slug => slug !== 'unknown'); // Remove any invalid entries
    console.log('[Wizard] Selected all models:', selectedModels);
    loadModels();
    updateGenerationMatrix();
    updateSidebar();
    updateNavigationButtons();
  }
}

function clearAllModels() {
  selectedModels = [];
  loadModels();
  updateGenerationMatrix();
  updateSidebar();
  updateNavigationButtons();
}

function updateGenerationMatrix() {
  const countEl = document.getElementById('matrix-count');
  const templatesEl = document.getElementById('matrix-templates');
  const modelsEl = document.getElementById('matrix-models');
  const previewEl = document.getElementById('generation-matrix-preview');
  
  const totalGenerations = selectedTemplates.length * selectedModels.length;
  console.log('[Wizard] updateGenerationMatrix:', {
    templates: selectedTemplates.length,
    models: selectedModels.length,
    total: totalGenerations,
    countEl: !!countEl,
    templatesEl: !!templatesEl,
    modelsEl: !!modelsEl,
    previewEl: !!previewEl
  });
  
  if (countEl) countEl.textContent = totalGenerations;
  if (templatesEl) templatesEl.textContent = selectedTemplates.length;
  if (modelsEl) modelsEl.textContent = selectedModels.length;
  
  if (previewEl && totalGenerations > 0 && totalGenerations <= 100) {
    // Show matrix table for reasonable sizes
    let html = '<table class="table table-sm table-bordered"><thead><tr><th>Template</th>';
    selectedModels.forEach(modelSlug => {
      const model = modelsCache?.find(m => m.slug === modelSlug);
      html += `<th class="text-center" style="writing-mode: vertical-rl; transform: rotate(180deg);">${model?.name || modelSlug}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    selectedTemplates.forEach(appNum => {
      const template = templatesCache?.find(t => t.app_num === appNum);
      html += `<tr><td>${template?.display_name || `App ${appNum}`}</td>`;
      selectedModels.forEach(() => {
        html += '<td class="text-center"><span class="badge bg-blue-lt">✓</span></td>';
      });
      html += '</tr>';
    });
    
    html += '</tbody></table>';
    previewEl.innerHTML = html;
  } else if (previewEl && totalGenerations > 100) {
    previewEl.innerHTML = '<div class="alert alert-warning">Matrix too large to display (>100 generations)</div>';
  } else if (previewEl) {
    previewEl.innerHTML = '';
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
  
  const payload = {
    template_ids: selectedTemplates,
    models: selectedModels,
    parallel_workers: 3
  };
  
  console.log('[Wizard] Starting batch generation:', payload);
  
  // Show loading state
  const startBtn = document.getElementById('start-btn');
  const loadingBtn = document.getElementById('start-btn-loading');
  if (startBtn) startBtn.classList.add('d-none');
  if (loadingBtn) loadingBtn.classList.remove('d-none');
  
  // Show progress immediately
  const totalGenerations = selectedTemplates.length * selectedModels.length;
  const totalEl = document.getElementById('progress-total');
  const statusTotalEl = document.getElementById('status-total');
  if (totalEl) totalEl.textContent = totalGenerations;
  if (statusTotalEl) statusTotalEl.textContent = totalGenerations;
  
  try {
    const response = await fetch('/api/sample-gen/generate/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const result = await response.json();
    console.log('[Wizard] Generation response:', result);
    
    if (!response.ok || !result.success) {
      throw new Error(result.message || result.error || 'Generation request failed');
    }
    
    // Batch generation completes synchronously - results are in response.data
    const batchResults = result.data;
    console.log('[Wizard] Batch results:', batchResults);
    
    showNotification('Generation completed!', 'success');
    
    // Display results immediately
    if (batchResults && typeof batchResults === 'object') {
      displayBatchResults(batchResults);
    } else {
      showNotification('Generation completed but no results returned', 'warning');
    }
  } catch (error) {
    console.error('Error starting generation:', error);
    showNotification('Failed to start generation: ' + error.message, 'danger');
  } finally {
    // Restore button state
    if (startBtn) startBtn.classList.remove('d-none');
    if (loadingBtn) loadingBtn.classList.add('d-none');
  }
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
        templateId: genResult.template_id || genResult.app_num
      });
      
      const statusBadge = success
        ? '<span class="badge bg-success"><i class="fas fa-check me-1"></i>Success</span>'
        : '<span class="badge bg-danger"><i class="fas fa-times me-1"></i>Failed</span>';
      
      const templateId = genResult.template_id || genResult.app_num || genResult.result_id?.split('_')[0];
      const modelSlug = genResult.model || 'Unknown';
      const templateName = templatesCache?.find(t => t.app_num == templateId)?.display_name || `Template ${templateId}`;
      const modelName = modelsCache?.find(m => m.canonical_slug === modelSlug)?.name || modelSlug;
      
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

function startStatusPolling() {
  if (statusPollInterval) {
    clearInterval(statusPollInterval);
  }
  
  statusPollInterval = setInterval(async () => {
    await updateGenerationStatus();
  }, 2000); // Poll every 2 seconds
}

function stopStatusPolling() {
  if (statusPollInterval) {
    clearInterval(statusPollInterval);
    statusPollInterval = null;
  }
}

async function updateGenerationStatus() {
  if (!generationBatchId) return;
  
  try {
    const response = await fetch(`/api/sample-gen/batch/${generationBatchId}/status`);
    if (!response.ok) return;
    
    const status = await response.json();
    
    // Update progress
    const progressEl = document.getElementById('overall-progress-bar');
    const percentEl = document.getElementById('progress-percentage');
    const completedEl = document.getElementById('progress-completed');
    const totalEl = document.getElementById('progress-total');
    
    if (progressEl && status.progress_percent !== undefined) {
      progressEl.style.width = `${status.progress_percent}%`;
    }
    if (percentEl) percentEl.textContent = `${Math.round(status.progress_percent || 0)}%`;
    if (completedEl) completedEl.textContent = status.completed_tasks || 0;
    if (totalEl) totalEl.textContent = status.total_tasks || 0;
    
    // Update status cards
    document.getElementById('status-in-progress').textContent = 
      (status.total_tasks - status.completed_tasks - status.failed_tasks) || 0;
    document.getElementById('status-completed').textContent = status.completed_tasks || 0;
    document.getElementById('status-failed').textContent = status.failed_tasks || 0;
    
    // Update results table
    if (status.task_results) {
      updateResultsTable(status.task_results);
    }
    
    // Stop polling if complete
    if (status.is_complete || status.status === 'completed') {
      stopStatusPolling();
      showNotification('Generation completed', 'success');
      document.getElementById('download-all-btn').disabled = false;
    }
  } catch (error) {
    console.error('Error fetching generation status:', error);
  }
}

function updateResultsTable(results) {
  const tbody = document.getElementById('results-table-body');
  if (!tbody || !results.length) return;
  
  tbody.innerHTML = '';
  results.forEach(result => {
    const row = document.createElement('tr');
    
    const statusBadge = result.success ? 
      '<span class="badge bg-success">Success</span>' :
      '<span class="badge bg-danger">Failed</span>';
    
    const duration = result.duration ? `${result.duration.toFixed(2)}s` : '-';
    const timestamp = result.timestamp ? new Date(result.timestamp).toLocaleString() : '-';
    
    row.innerHTML = `
      <td>${result.template || '-'}</td>
      <td>${result.model || '-'}</td>
      <td>${statusBadge}</td>
      <td>${duration}</td>
      <td>${timestamp}</td>
      <td>
        <div class="btn-list">
          <button type="button" class="btn btn-sm btn-ghost-primary" onclick="viewResult('${result.id}')">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><circle cx="12" cy="12" r="2" /><path d="M22 12c-2.667 4.667 -6 7 -10 7s-7.333 -2.333 -10 -7c2.667 -4.667 6 -7 10 -7s7.333 2.333 10 7" /></svg>
          </button>
          <button type="button" class="btn btn-sm btn-ghost-primary" onclick="downloadResult('${result.id}')">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2" /><polyline points="7 11 12 16 17 11" /><line x1="12" y1="4" x2="12" y2="16" /></svg>
          </button>
        </div>
      </td>
    `;
    
    tbody.appendChild(row);
  });
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
        const model = modelsCache?.find(m => m.slug === slug);
        const displayName = model?.name || slug;
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
  
  // Update generation matrix
  const totalGenerations = selectedTemplates.length * selectedModels.length;
  const matrixCount = document.getElementById('matrix-count');
  const matrixTemplates = document.getElementById('matrix-templates');
  const matrixModels = document.getElementById('matrix-models');
  
  if (matrixCount) {
    matrixCount.textContent = totalGenerations;
  } else {
    console.warn('[Wizard] matrix-count element not found');
  }
  
  if (matrixTemplates) {
    matrixTemplates.textContent = selectedTemplates.length;
  } else {
    console.warn('[Wizard] matrix-templates element not found');
  }
  
  if (matrixModels) {
    matrixModels.textContent = selectedModels.length;
  } else {
    console.warn('[Wizard] matrix-models element not found');
  }
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

async function downloadAllResults() {
  if (!generationBatchId) return;
  
  try {
    const response = await fetch(`/api/sample-gen/batch/${generationBatchId}/download`);
    if (!response.ok) throw new Error('Download failed');
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `generation-${generationBatchId}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    
    showNotification('Download started', 'success');
  } catch (error) {
    console.error('Error downloading results:', error);
    showNotification('Download failed: ' + error.message, 'danger');
  }
}

function viewResult(resultId) {
  window.open(`/api/sample-gen/result/${resultId}`, '_blank');
}

function downloadResult(resultId) {
  window.location.href = `/api/sample-gen/result/${resultId}/download`;
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
window.downloadAllResults = downloadAllResults;
window.viewResult = viewResult;
window.downloadResult = downloadResult;
window.refreshScaffoldings = refreshScaffoldings;
window.viewScaffoldingDetails = viewScaffoldingDetails;
window.refreshTemplates = refreshTemplates;
window.searchTemplates = searchTemplates;
window.createTemplate = createTemplate;
window.viewTemplate = viewTemplate;
window.editTemplate = editTemplate;
window.deleteTemplate = deleteTemplate;
window.saveTemplate = saveTemplate;
