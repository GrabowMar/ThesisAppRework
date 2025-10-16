// Templates Manager JavaScript
// Handles template library, preview, and prompt display
// Wrapped in IIFE to avoid namespace collision with wizard

(function() {
  'use strict';
  
  let selectedTemplate = null;
  let templatesData = [];

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  console.log('[Templates] Initializing templates manager');
  
  // CRITICAL: Only initialize in templates tab, NEVER in wizard
  // Check 1: Must have templates-list (templates tab)
  // Check 2: Must NOT have template-selection-list (wizard)
  const hasTemplatesTab = document.getElementById('templates-list');
  const hasWizard = document.getElementById('template-selection-list');
  
  console.log('[Templates] Context check:', { hasTemplatesTab: !!hasTemplatesTab, hasWizard: !!hasWizard });
  
  if (hasTemplatesTab && !hasWizard) {
    console.log('[Templates] Initializing for templates tab');
    initTemplatesManager();
  } else {
    console.log('[Templates] Skipping init - wizard context or wrong page');
  }
});

function initTemplatesManager() {
  // Load templates when the tab is shown
  const templatesTab = document.querySelector('a[href="#templates"]');
  if (templatesTab) {
    templatesTab.addEventListener('shown.bs.tab', () => {
      console.log('[Templates] Tab shown, loading templates');
      loadTemplatesLibrary();
    });
  }
  
  // Set up button handlers
  setupTemplateHandlers();
}

// ============================================================================
// Template Loading
// ============================================================================

async function loadTemplatesLibrary() {
  const listContainer = document.getElementById('templates-list');
  if (!listContainer) {
    console.error('[Templates] List container not found');
    return;
  }
  
  listContainer.innerHTML = `
    <div class="text-center text-secondary py-5">
      <div class="spinner-border text-primary mb-2" role="status"></div>
      <div class="small">Loading templates...</div>
    </div>
  `;
  
  try {
    console.log('[Templates] Fetching from /api/gen/templates...');
    const response = await fetch('/api/gen/templates');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    console.log('[Templates] Response:', result);
    
    // Handle standardized API envelope
    if (result.success && result.data) {
      templatesData = Array.isArray(result.data) ? result.data : [];
    } else if (Array.isArray(result)) {
      templatesData = result;
    } else {
      throw new Error('Unexpected response format');
    }
    
    console.log(`[Templates] Loaded ${templatesData.length} templates`);
    
    // Update stats
    updateTemplateStats(templatesData.length, templatesData.length);
    
    // Render template list
    renderTemplateList(templatesData);
    
  } catch (error) {
    console.error('[Templates] Error loading templates:', error);
    listContainer.innerHTML = `
      <div class="text-center text-danger p-4">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-lg mb-2" width="48" height="48" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9v4" /><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z" /><path d="M12 16h.01" /></svg>
        <p class="fw-bold">Error loading templates</p>
        <p class="small text-muted">${escapeHtml(error.message)}</p>
        <button class="btn btn-sm btn-primary mt-2" onclick="loadTemplatesLibrary()">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4" /><path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4" /></svg>
          Retry
        </button>
      </div>
    `;
  }
}

function renderTemplateList(templates) {
  // CRITICAL: Only operate on templates-list (templates tab), never template-selection-list (wizard)
  const listContainer = document.getElementById('templates-list');
  if (!listContainer) {
    console.log('[Templates] templates-list not found, skipping render');
    return;
  }
  
  // Double-check we're not in wizard context
  if (document.getElementById('template-selection-list')) {
    console.log('[Templates] Wizard context detected, aborting templates_manager render');
    return;
  }
  
  if (templates.length === 0) {
    listContainer.innerHTML = `
      <div class="text-center text-muted p-4">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-lg mb-2 opacity-50" width="48" height="48" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M14 3v4a1 1 0 0 0 1 1h4" /><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z" /></svg>
        <p>No templates available</p>
        <p class="small">Templates should be in <code>misc/app_templates/</code></p>
      </div>
    `;
    return;
  }
  
  listContainer.innerHTML = '';
  
  templates.forEach((template, index) => {
    const item = createTemplateListItem(template, index);
    listContainer.appendChild(item);
  });
}

function createTemplateListItem(template, index) {
  const item = document.createElement('a');
  item.href = '#';
  item.className = 'list-group-item list-group-item-action';
  
  const templateId = template.id || `template-${index + 1}`;
  const name = template.name || template.title || `Template ${index + 1}`;
  const description = template.description || '';
  const category = template.category || 'general';
  
  // Check if this template is selected
  if (selectedTemplate && selectedTemplate.id === templateId) {
    item.classList.add('active');
  }
  
  // Category badge color
  const categoryColors = {
    'frontend': 'bg-green-lt',
    'backend': 'bg-blue-lt',
    'fullstack': 'bg-purple-lt',
    'general': 'bg-secondary-lt'
  };
  const categoryColor = categoryColors[category.toLowerCase()] || 'bg-secondary-lt';
  
  item.innerHTML = `
    <div class="d-flex justify-content-between align-items-start">
      <div class="flex-fill">
        <div class="fw-bold mb-1">${escapeHtml(name)}</div>
        <div class="text-muted small mb-2">${escapeHtml(description).substring(0, 100)}${description.length > 100 ? '...' : ''}</div>
        <div>
          <span class="badge ${categoryColor}">${escapeHtml(category)}</span>
        </div>
      </div>
      <div class="ms-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon text-muted" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M9 6l6 6l-6 6" /></svg>
      </div>
    </div>
  `;
  
  // Click handler - only for templates tab, not wizard
  item.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    console.log('[Templates] Template item clicked (templates tab)');
    selectTemplate(template);
  });
  
  return item;
}

// ============================================================================
// Template Selection and Display
// ============================================================================

async function selectTemplate(template) {
  console.log('[Templates] Selected template:', template);
  selectedTemplate = template;
  
  // Update UI to show selected state
  document.querySelectorAll('#templates-list .list-group-item').forEach(item => {
    item.classList.remove('active');
  });
  event.currentTarget?.classList.add('active');
  
  // Show the detail content
  const emptyState = document.getElementById('template-empty-state');
  const detailContent = document.getElementById('template-detail-content');
  
  if (emptyState) emptyState.classList.add('d-none');
  if (detailContent) detailContent.classList.remove('d-none');
  
  // Update badge
  const badge = document.getElementById('template-detail-badge');
  if (badge) {
    badge.textContent = 'Selected';
    badge.className = 'badge bg-success-lt';
  }
  
  // Enable action buttons
  document.getElementById('edit-template-btn')?.removeAttribute('disabled');
  document.getElementById('duplicate-template-btn')?.removeAttribute('disabled');
  document.getElementById('delete-template-btn')?.removeAttribute('disabled');
  
  // Display template details
  displayTemplateDetails(template);
  
  // Load and display full prompt
  await loadTemplatePrompt(template);
}

function displayTemplateDetails(template) {
  // Template name and metadata
  const nameEl = document.getElementById('template-detail-name');
  const pathEl = document.getElementById('template-detail-path');
  const appNumEl = document.getElementById('template-detail-app-num');
  const contextEl = document.getElementById('template-detail-context');
  
  if (nameEl) nameEl.textContent = template.name || 'Unnamed Template';
  if (pathEl) pathEl.textContent = template.path || 'misc/app_templates/';
  if (appNumEl) appNumEl.textContent = template.id || '—';
  if (contextEl) contextEl.textContent = template.category || 'general';
  
  // Badge updates
  const appBadge = document.getElementById('template-detail-app-badge');
  if (appBadge) {
    appBadge.textContent = `Template #${template.id || '?'}`;
  }
  
  const contextBadge = document.getElementById('template-detail-context-badge');
  if (contextBadge) {
    contextBadge.textContent = template.category || 'General';
  }
  
  // Complexity indicator
  const complexity = template.complexity || 'medium';
  const complexityPercent = complexity === 'simple' ? 33 : complexity === 'medium' ? 66 : 100;
  const complexityBar = document.querySelector('#template-detail-complexity .progress-bar');
  if (complexityBar) {
    complexityBar.style.width = `${complexityPercent}%`;
  }
  
  // Requirements
  const reqsEl = document.getElementById('template-detail-reqs');
  if (reqsEl) {
    if (template.features && template.features.length > 0) {
      reqsEl.innerHTML = `<ul class="mb-0">${template.features.map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul>`;
    } else {
      reqsEl.textContent = 'No requirements specified';
    }
  }
  
  // Extra prompt
  const extraEl = document.getElementById('template-detail-extra');
  if (extraEl) {
    if (template.extra_prompt) {
      extraEl.textContent = template.extra_prompt;
    } else {
      extraEl.textContent = 'No extra prompt';
    }
  }
  
  // Size (placeholder)
  const sizeEl = document.getElementById('template-detail-size');
  if (sizeEl) {
    sizeEl.textContent = '—';
  }
}

async function loadTemplatePrompt(template) {
  const previewEl = document.getElementById('template-detail-preview');
  const promptPreviewEl = document.getElementById('template-prompt-preview');
  
  if (!previewEl || !promptPreviewEl) {
    console.error('[Templates] Preview elements not found');
    return;
  }
  
  // Show loading state
  previewEl.textContent = 'Loading template content...';
  promptPreviewEl.textContent = 'Loading prompt...';
  
  try {
    // For now, display the template metadata as the content
    // In a full implementation, you'd fetch the actual .md file content
    const templateContent = JSON.stringify(template, null, 2);
    previewEl.textContent = templateContent;
    
    // Build the prompt that would be sent to the AI
    const systemPrompt = buildSystemPrompt(template);
    const userPrompt = buildUserPrompt(template);
    const fullPrompt = `=== SYSTEM PROMPT ===\n${systemPrompt}\n\n=== USER PROMPT ===\n${userPrompt}`;
    
    promptPreviewEl.textContent = fullPrompt;
    
  } catch (error) {
    console.error('[Templates] Error loading template content:', error);
    previewEl.textContent = `Error loading template: ${error.message}`;
    promptPreviewEl.textContent = `Error loading prompt: ${error.message}`;
  }
}

function buildSystemPrompt(template) {
  // This should match the actual system prompt used in generation
  return `You are an expert full-stack developer. Generate clean, production-ready code based on the requirements.

Guidelines:
- Write modern, idiomatic code
- Follow best practices and conventions
- Include proper error handling
- Add helpful comments where needed
- Use the specified tech stack
- Make the code maintainable and scalable

Tech Stack: ${JSON.stringify(template.tech_stack || {})}
Category: ${template.category || 'general'}
Complexity: ${template.complexity || 'medium'}`;
}

function buildUserPrompt(template) {
  // Build the user prompt that includes requirements
  let prompt = `Create a ${template.category || 'web'} application with the following requirements:\n\n`;
  
  if (template.description) {
    prompt += `Description: ${template.description}\n\n`;
  }
  
  if (template.features && template.features.length > 0) {
    prompt += `Features:\n`;
    template.features.forEach(feature => {
      prompt += `- ${feature}\n`;
    });
    prompt += '\n';
  }
  
  if (template.tech_stack) {
    prompt += `Tech Stack:\n`;
    if (template.tech_stack.frontend) {
      prompt += `- Frontend: ${template.tech_stack.frontend}\n`;
    }
    if (template.tech_stack.backend) {
      prompt += `- Backend: ${template.tech_stack.backend}\n`;
    }
    if (template.tech_stack.database) {
      prompt += `- Database: ${template.tech_stack.database}\n`;
    }
    prompt += '\n';
  }
  
  if (template.extra_prompt) {
    prompt += `Additional Instructions:\n${template.extra_prompt}\n\n`;
  }
  
  prompt += `Please provide complete, working code for this application.`;
  
  return prompt;
}

// ============================================================================
// Event Handlers
// ============================================================================

function setupTemplateHandlers() {
  // Reload button
  const reloadBtn = document.getElementById('reload-templates-library-btn');
  if (reloadBtn) {
    reloadBtn.addEventListener('click', () => {
      console.log('[Templates] Reload button clicked');
      loadTemplatesLibrary();
    });
  }
  
  // Search input
  const searchInput = document.getElementById('template-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      filterTemplates(e.target.value);
    });
  }
  
  // Context filter
  const contextFilter = document.getElementById('template-context-filter');
  if (contextFilter) {
    contextFilter.addEventListener('change', (e) => {
      filterByContext(e.target.value);
    });
  }
  
  // Copy buttons
  const copyTemplateBtn = document.getElementById('template-preview-copy-btn');
  if (copyTemplateBtn) {
    copyTemplateBtn.addEventListener('click', () => {
      copyToClipboard('template-detail-preview', 'Template content');
    });
  }
  
  const copyPromptBtn = document.getElementById('prompt-preview-copy-btn');
  if (copyPromptBtn) {
    copyPromptBtn.addEventListener('click', () => {
      copyToClipboard('template-prompt-preview', 'Prompt');
    });
  }
}

function filterTemplates(searchTerm) {
  const term = searchTerm.toLowerCase().trim();
  
  if (!term) {
    // Show all templates
    renderTemplateList(templatesData);
    updateTemplateStats(templatesData.length, templatesData.length);
    return;
  }
  
  const filtered = templatesData.filter(t => {
    const name = (t.name || '').toLowerCase();
    const desc = (t.description || '').toLowerCase();
    const category = (t.category || '').toLowerCase();
    return name.includes(term) || desc.includes(term) || category.includes(term);
  });
  
  renderTemplateList(filtered);
  updateTemplateStats(templatesData.length, filtered.length);
}

function filterByContext(context) {
  if (!context) {
    renderTemplateList(templatesData);
    updateTemplateStats(templatesData.length, templatesData.length);
    return;
  }
  
  const filtered = templatesData.filter(t => 
    (t.category || '').toLowerCase() === context.toLowerCase()
  );
  
  renderTemplateList(filtered);
  updateTemplateStats(templatesData.length, filtered.length);
}

function updateTemplateStats(total, filtered) {
  const totalEl = document.getElementById('total-templates-count');
  const filteredEl = document.getElementById('filtered-templates-count');
  
  if (totalEl) totalEl.textContent = total;
  if (filteredEl) filteredEl.textContent = filtered;
}

async function copyToClipboard(elementId, label) {
  const element = document.getElementById(elementId);
  if (!element) return;
  
  const text = element.textContent;
  
  try {
    await navigator.clipboard.writeText(text);
    showNotification(`${label} copied to clipboard`, 'success');
  } catch (error) {
    console.error('[Templates] Copy failed:', error);
    showNotification('Failed to copy to clipboard', 'danger');
  }
}

// ============================================================================
// Utility Functions
// ============================================================================

function showNotification(message, type = 'info') {
  // Use the global notification system if available
  if (window.showNotification) {
    window.showNotification(message, type);
    return;
  }
  
  // Fallback: create toast notification
  const toast = document.createElement('div');
  toast.className = `alert alert-${type} alert-dismissible position-fixed top-0 end-0 m-3`;
  toast.style.zIndex = '9999';
  toast.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 5000);
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

// Export functions for global access (if needed from outside)
window.loadTemplatesLibrary = loadTemplatesLibrary;
window.selectTemplate = selectTemplate;

})(); // End of IIFE - templates_manager scope
