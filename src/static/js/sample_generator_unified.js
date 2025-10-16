/**
 * Sample Generator - Unified Generation Interface
 * Handles both individual and batch generation in a single, streamlined UI
 */

(function() {
    'use strict';

    // Prevent double initialization
    if (window.SampleGeneratorUnified) {
        return;
    }

    class SampleGeneratorUnified {
        constructor() {
            this.apiBase = '/api/sample-gen';
            this.templates = [];
            this.models = [];
            this.selectedTemplates = new Set();
            this.selectedModels = new Set();
            this.activeGenerations = new Map();
            this.recentGenerations = [];
            
            // UI mode tracking
            this.templateMode = 'single'; // single, multiple, all
            this.modelMode = 'single';    // single, multiple, all
            
            // Polling
            this.statusPollInterval = null;
            
            this.init();
        }

        init() {
            console.log('[SampleGeneratorUnified] Initializing unified generation interface');
            this.bindEvents();
            this.loadInitialData();
            this.startStatusPolling();
        }

        bindEvents() {
            // Template mode switches
            document.querySelectorAll('input[name="gen-template-mode"]').forEach(radio => {
                radio.addEventListener('change', (e) => this.onTemplateModeChange(e.target.value));
            });

            // Model mode switches
            document.querySelectorAll('input[name="gen-model-mode"]').forEach(radio => {
                radio.addEventListener('change', (e) => this.onModelModeChange(e.target.value));
            });

            // Template selection
            const templateSelect = document.getElementById('gen-template-select');
            if (templateSelect) {
                templateSelect.addEventListener('change', (e) => this.onSingleTemplateSelect(e.target.value));
            }

            // Model selection
            const modelSelect = document.getElementById('gen-model-select');
            if (modelSelect) {
                modelSelect.addEventListener('change', (e) => this.onSingleModelSelect(e.target.value));
            }

            // Toggle all buttons
            const toggleTemplatesBtn = document.getElementById('gen-toggle-all-templates');
            if (toggleTemplatesBtn) {
                toggleTemplatesBtn.addEventListener('click', () => this.toggleAllTemplates());
            }

            const toggleModelsBtn = document.getElementById('gen-toggle-all-models');
            if (toggleModelsBtn) {
                toggleModelsBtn.addEventListener('click', () => this.toggleAllModels());
            }

            // Reload buttons
            const reloadTemplatesBtn = document.getElementById('gen-reload-templates-btn');
            if (reloadTemplatesBtn) {
                reloadTemplatesBtn.addEventListener('click', () => this.loadTemplates());
            }

            const refreshModelsBtn = document.getElementById('gen-refresh-models-btn');
            if (refreshModelsBtn) {
                refreshModelsBtn.addEventListener('click', () => this.loadModels());
            }

            // Action buttons
            const previewBtn = document.getElementById('gen-preview-btn');
            if (previewBtn) {
                previewBtn.addEventListener('click', () => this.previewGeneration());
            }

            const startBtn = document.getElementById('gen-start-btn');
            if (startBtn) {
                startBtn.addEventListener('click', () => this.startGeneration());
            }

            // Refresh buttons
            const refreshActiveBtn = document.getElementById('gen-refresh-active-btn');
            if (refreshActiveBtn) {
                refreshActiveBtn.addEventListener('click', () => this.updateActiveGenerations());
            }

            const viewAllResultsBtn = document.getElementById('gen-view-all-results-btn');
            if (viewAllResultsBtn) {
                viewAllResultsBtn.addEventListener('click', () => this.navigateToResults());
            }

            // Scope checkboxes - trigger summary update
            ['gen-scope-frontend', 'gen-scope-backend', 'gen-scope-tests'].forEach(id => {
                const elem = document.getElementById(id);
                if (elem) {
                    elem.addEventListener('change', () => this.updateSummary());
                }
            });

            // Advanced settings - trigger summary update
            const workersInput = document.getElementById('gen-workers');
            if (workersInput) {
                workersInput.addEventListener('change', () => this.updateSummary());
            }
        }

        // ========================================================================
        // Data Loading
        // ========================================================================

        async loadInitialData() {
            try {
                await Promise.all([
                    this.loadTemplates(),
                    this.loadModels(),
                    this.loadRecentGenerations()
                ]);
            } catch (error) {
                console.error('[SampleGeneratorUnified] Failed to load initial data:', error);
                this.showError('Failed to load initial data');
            }
        }

        async loadTemplates() {
            try {
                const response = await this.apiGet('/templates');
                const templates = response.data || response.templates || [];
                
                this.templates = templates.map(t => ({
                    app_num: t.app_num,
                    name: t.name || `App ${t.app_num}`,
                    display_name: t.display_name || t.name || `App ${t.app_num}`,
                    template_type: t.template_type || 'generic',
                    content: t.content || ''
                }));
                
                console.log(`[SampleGeneratorUnified] Loaded ${this.templates.length} templates`);
                this.renderTemplateSelectors();
                this.updateSummary();
            } catch (error) {
                console.error('[SampleGeneratorUnified] Failed to load templates:', error);
                this.showError('Failed to load templates');
            }
        }

        async loadModels() {
            try {
                // Only fetch scaffolded models (mode=scaffolded)
                const response = await this.apiGet('/models', { mode: 'scaffolded' });
                const models = response.data || response.models || [];
                
                this.models = models.map(m => {
                    if (typeof m === 'string') {
                        return { name: m, display_name: m };
                    }
                    return {
                        name: m.name || m.canonical_slug || m,
                        display_name: m.display_name || m.name || m.canonical_slug || m,
                        provider: m.provider || '',
                        is_free: m.is_free || false
                    };
                });
                
                console.log(`[SampleGeneratorUnified] Loaded ${this.models.length} scaffolded models`);
                this.renderModelSelectors();
                this.updateSummary();
            } catch (error) {
                console.error('[SampleGeneratorUnified] Failed to load models:', error);
                this.showError('Failed to load scaffolded models');
            }
        }

        async loadRecentGenerations() {
            try {
                // This would hit an endpoint like /results?limit=20&sort=desc
                // For now, stub with empty array
                this.recentGenerations = [];
                this.renderRecentGenerations();
            } catch (error) {
                console.error('[SampleGeneratorUnified] Failed to load recent generations:', error);
            }
        }

        // ========================================================================
        // UI Rendering
        // ========================================================================

        renderTemplateSelectors() {
            // Single template selector (dropdown)
            const select = document.getElementById('gen-template-select');
            if (select) {
                select.innerHTML = '<option value="">Select a template...</option>';
                this.templates.forEach(t => {
                    const option = document.createElement('option');
                    option.value = t.app_num;
                    option.textContent = t.display_name;
                    select.appendChild(option);
                });
            }

            // Multiple template selector (checkboxes)
            const checkboxList = document.getElementById('gen-template-checkbox-list');
            if (checkboxList) {
                checkboxList.innerHTML = '';
                this.templates.forEach(t => {
                    const item = document.createElement('label');
                    item.className = 'list-group-item';
                    item.innerHTML = `
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" value="${t.app_num}" data-template-checkbox>
                            <span class="form-check-label">${this.escapeHtml(t.display_name)}</span>
                        </div>
                    `;
                    const checkbox = item.querySelector('input');
                    checkbox.addEventListener('change', () => this.onTemplateCheckboxChange());
                    checkboxList.appendChild(item);
                });
            }
        }

        renderModelSelectors() {
            // Single model selector (dropdown)
            const select = document.getElementById('gen-model-select');
            if (select) {
                select.innerHTML = '<option value="">Select a model...</option>';
                this.models.forEach(m => {
                    const option = document.createElement('option');
                    option.value = m.name;
                    option.textContent = m.display_name;
                    select.appendChild(option);
                });
            }

            // Multiple model selector (checkboxes)
            const checkboxList = document.getElementById('gen-model-checkbox-list');
            if (checkboxList) {
                checkboxList.innerHTML = '';
                this.models.forEach(m => {
                    const item = document.createElement('label');
                    item.className = 'list-group-item';
                    item.innerHTML = `
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" value="${m.name}" data-model-checkbox>
                            <span class="form-check-label">${this.escapeHtml(m.display_name)}</span>
                        </div>
                    `;
                    const checkbox = item.querySelector('input');
                    checkbox.addEventListener('change', () => this.onModelCheckboxChange());
                    checkboxList.appendChild(item);
                });
            }
        }

        renderRecentGenerations() {
            const tbody = document.getElementById('gen-recent-table');
            if (!tbody) return;

            if (this.recentGenerations.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="text-center text-muted py-4">
                            No recent generations found
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = this.recentGenerations.map(gen => `
                <tr>
                    <td>${this.formatTimestamp(gen.timestamp)}</td>
                    <td>${this.escapeHtml(gen.template_name || '—')}</td>
                    <td>${this.escapeHtml(gen.model_name || '—')}</td>
                    <td>${this.renderStatusBadge(gen.status)}</td>
                    <td>${this.formatDuration(gen.duration)}</td>
                    <td>
                        <button class="btn btn-sm btn-ghost-secondary" onclick="viewGeneration('${gen.id}')">
                            View
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        // ========================================================================
        // Mode Changes
        // ========================================================================

        onTemplateModeChange(mode) {
            this.templateMode = mode;
            
            const singleSelector = document.getElementById('gen-single-template-selector');
            const multipleSelector = document.getElementById('gen-multiple-template-selector');
            
            if (mode === 'single') {
                singleSelector?.classList.remove('d-none');
                multipleSelector?.classList.add('d-none');
                this.selectedTemplates.clear();
                const select = document.getElementById('gen-template-select');
                if (select && select.value) {
                    this.selectedTemplates.add(parseInt(select.value));
                }
            } else {
                singleSelector?.classList.add('d-none');
                multipleSelector?.classList.remove('d-none');
                
                if (mode === 'all') {
                    // Select all templates
                    this.selectedTemplates.clear();
                    this.templates.forEach(t => this.selectedTemplates.add(t.app_num));
                    // Check all checkboxes
                    document.querySelectorAll('[data-template-checkbox]').forEach(cb => {
                        cb.checked = true;
                    });
                }
            }
            
            this.updateTemplatePreview();
            this.updateTemplateCount();
            this.updateSummary();
        }

        onModelModeChange(mode) {
            this.modelMode = mode;
            
            const singleSelector = document.getElementById('gen-single-model-selector');
            const multipleSelector = document.getElementById('gen-multiple-model-selector');
            
            if (mode === 'single') {
                singleSelector?.classList.remove('d-none');
                multipleSelector?.classList.add('d-none');
                this.selectedModels.clear();
                const select = document.getElementById('gen-model-select');
                if (select && select.value) {
                    this.selectedModels.add(select.value);
                }
            } else {
                singleSelector?.classList.add('d-none');
                multipleSelector?.classList.remove('d-none');
                
                if (mode === 'all') {
                    // Select all models
                    this.selectedModels.clear();
                    this.models.forEach(m => this.selectedModels.add(m.name));
                    // Check all checkboxes
                    document.querySelectorAll('[data-model-checkbox]').forEach(cb => {
                        cb.checked = true;
                    });
                }
            }
            
            this.updateModelCount();
            this.updateSummary();
        }

        // ========================================================================
        // Selection Handlers
        // ========================================================================

        onSingleTemplateSelect(appNum) {
            this.selectedTemplates.clear();
            if (appNum) {
                this.selectedTemplates.add(parseInt(appNum));
                this.loadTemplatePreview(parseInt(appNum));
            } else {
                this.clearTemplatePreview();
            }
            this.updateSummary();
        }

        onSingleModelSelect(modelName) {
            this.selectedModels.clear();
            if (modelName) {
                this.selectedModels.add(modelName);
            }
            this.updateSummary();
        }

        onTemplateCheckboxChange() {
            this.selectedTemplates.clear();
            document.querySelectorAll('[data-template-checkbox]:checked').forEach(cb => {
                this.selectedTemplates.add(parseInt(cb.value));
            });
            this.updateTemplateCount();
            this.updateTemplatePreview();
            this.updateSummary();
        }

        onModelCheckboxChange() {
            this.selectedModels.clear();
            document.querySelectorAll('[data-model-checkbox]:checked').forEach(cb => {
                this.selectedModels.add(cb.value);
            });
            this.updateModelCount();
            this.updateSummary();
        }

        toggleAllTemplates() {
            const checkboxes = document.querySelectorAll('[data-template-checkbox]');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            
            checkboxes.forEach(cb => {
                cb.checked = !allChecked;
            });
            
            this.onTemplateCheckboxChange();
        }

        toggleAllModels() {
            const checkboxes = document.querySelectorAll('[data-model-checkbox]');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            
            checkboxes.forEach(cb => {
                cb.checked = !allChecked;
            });
            
            this.onModelCheckboxChange();
        }

        // ========================================================================
        // Template Preview
        // ========================================================================

        async loadTemplatePreview(appNum) {
            const previewDiv = document.getElementById('gen-template-preview');
            if (!previewDiv) return;

            try {
                previewDiv.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>Loading preview...';
                
                const response = await this.apiGet(`/templates/app/${appNum}.md`);
                const content = response.data?.content || response.content || 'No content available';
                
                previewDiv.innerHTML = `<pre class="mb-0">${this.escapeHtml(content.substring(0, 500))}${content.length > 500 ? '...' : ''}</pre>`;
            } catch (error) {
                console.error('[SampleGeneratorUnified] Failed to load template preview:', error);
                previewDiv.innerHTML = '<div class="text-danger">Failed to load preview</div>';
            }
        }

        updateTemplatePreview() {
            if (this.templateMode === 'single') {
                // Preview already loaded by onSingleTemplateSelect
                return;
            }
            
            const previewDiv = document.getElementById('gen-template-preview');
            if (!previewDiv) return;
            
            if (this.selectedTemplates.size === 0) {
                this.clearTemplatePreview();
            } else if (this.selectedTemplates.size === 1) {
                const appNum = Array.from(this.selectedTemplates)[0];
                this.loadTemplatePreview(appNum);
            } else {
                previewDiv.innerHTML = `<div class="text-secondary">${this.selectedTemplates.size} templates selected</div>`;
            }
        }

        clearTemplatePreview() {
            const previewDiv = document.getElementById('gen-template-preview');
            if (!previewDiv) return;
            
            previewDiv.innerHTML = `
                <div class="empty">
                    <p class="empty-title">No template selected</p>
                    <p class="empty-subtitle">Select a template to preview its content</p>
                </div>
            `;
        }

        updateTemplateCount() {
            const countSpan = document.getElementById('gen-templates-selected-count');
            if (countSpan) {
                countSpan.textContent = this.selectedTemplates.size;
            }
        }

        updateModelCount() {
            const countSpan = document.getElementById('gen-models-selected-count');
            if (countSpan) {
                countSpan.textContent = this.selectedModels.size;
            }
        }

        // ========================================================================
        // Summary & Validation
        // ========================================================================

        updateSummary() {
            const templatesCount = this.selectedTemplates.size;
            const modelsCount = this.selectedModels.size;
            const totalJobs = templatesCount * modelsCount;
            
            // Update summary display
            this.setElementText('gen-summary-templates', templatesCount || '—');
            this.setElementText('gen-summary-models', modelsCount || '—');
            this.setElementText('gen-summary-jobs', totalJobs || '—');
            
            // Estimate time (rough: 30s per job base + concurrency factor)
            if (totalJobs > 0) {
                const workers = parseInt(document.getElementById('gen-workers')?.value || 3);
                const timePerJob = 30; // seconds
                const estimatedSeconds = Math.ceil(totalJobs / workers) * timePerJob;
                this.setElementText('gen-summary-time', this.formatDuration(estimatedSeconds));
            } else {
                this.setElementText('gen-summary-time', '—');
            }
            
            // Enable/disable action buttons
            const canGenerate = templatesCount > 0 && modelsCount > 0;
            const previewBtn = document.getElementById('gen-preview-btn');
            const startBtn = document.getElementById('gen-start-btn');
            
            if (previewBtn) {
                previewBtn.disabled = !canGenerate;
            }
            if (startBtn) {
                startBtn.disabled = !canGenerate;
            }
        }

        // ========================================================================
        // Generation Actions
        // ========================================================================

        async previewGeneration() {
            const plan = this.buildGenerationPlan();
            
            // Show preview modal or inline message
            const message = `
                <div class="mb-3"><strong>Generation Preview</strong></div>
                <ul>
                    <li>Templates: ${plan.templates.length}</li>
                    <li>Models: ${plan.models.length}</li>
                    <li>Total Jobs: ${plan.jobs.length}</li>
                    <li>Estimated Time: ${this.formatDuration(plan.estimatedTime)}</li>
                </ul>
                <div class="alert alert-warning">
                    This will generate ${plan.jobs.length} application(s) and may overwrite existing files.
                </div>
            `;
            
            this.showInfo(message);
        }

        async startGeneration() {
            const plan = this.buildGenerationPlan();
            
            if (!confirm(`Start generation of ${plan.jobs.length} application(s)?`)) {
                return;
            }
            
            try {
                // Collect generation options
                const options = {
                    generate_frontend: document.getElementById('gen-scope-frontend')?.checked || false,
                    generate_backend: document.getElementById('gen-scope-backend')?.checked || false,
                    tests: document.getElementById('gen-scope-tests')?.checked || false,
                    workers: parseInt(document.getElementById('gen-workers')?.value || 3),
                    timeout: parseInt(document.getElementById('gen-timeout')?.value || 300),
                    create_backup: document.getElementById('gen-create-backup')?.checked || false
                };
                
                // If single job, use /generate; if multiple, use /generate/batch
                if (plan.jobs.length === 1) {
                    const job = plan.jobs[0];
                    // Use template_id (app_num) not template name
                    const templateId = plan.template_ids[0];
                    const response = await this.apiPost('/generate', {
                        template_id: String(templateId),
                        model: job.model,
                        ...options
                    });
                    
                    if (response.success) {
                        this.showSuccess('Generation started successfully');
                        this.loadRecentGenerations();
                    } else {
                        this.showError(response.message || 'Generation failed');
                    }
                } else {
                    // For batch generation, send template_ids and models as separate arrays
                    const response = await this.apiPost('/generate/batch', {
                        template_ids: plan.template_ids,
                        models: plan.models,
                        parallel_workers: options.workers,
                        ...options
                    });
                    
                    if (response.success) {
                        this.showSuccess(`Batch generation started: ${plan.jobs.length} jobs`);
                        this.loadRecentGenerations();
                    } else {
                        this.showError(response.message || 'Batch generation failed');
                    }
                }
                
                // Start polling for status updates
                this.startStatusPolling();
                
            } catch (error) {
                console.error('[SampleGeneratorUnified] Generation failed:', error);
                this.showError('Generation failed: ' + error.message);
            }
        }

        buildGenerationPlan() {
            const template_ids = Array.from(this.selectedTemplates);
            
            const templates = template_ids.map(appNum => {
                const template = this.templates.find(t => t.app_num === appNum);
                return template ? template.name : `app_${appNum}`;
            });
            
            const models = Array.from(this.selectedModels);
            
            const jobs = [];
            templates.forEach(template => {
                models.forEach(model => {
                    jobs.push({ template, model });
                });
            });
            
            const workers = parseInt(document.getElementById('gen-workers')?.value || 3);
            const timePerJob = 30; // seconds
            const estimatedTime = Math.ceil(jobs.length / workers) * timePerJob;
            
            return {
                template_ids,  // Array of app_num integers for the API
                templates,
                models,
                jobs,
                estimatedTime
            };
        }

        // ========================================================================
        // Status Polling
        // ========================================================================

        startStatusPolling() {
            if (this.statusPollInterval) {
                clearInterval(this.statusPollInterval);
            }
            
            this.updateActiveGenerations();
            this.statusPollInterval = setInterval(() => {
                this.updateActiveGenerations();
            }, 5000); // Poll every 5 seconds
        }

        stopStatusPolling() {
            if (this.statusPollInterval) {
                clearInterval(this.statusPollInterval);
                this.statusPollInterval = null;
            }
        }

        async updateActiveGenerations() {
            try {
                const response = await this.apiGet('/status');
                const status = response.data || response.status || {};
                
                // Update active generations list
                const activeList = document.getElementById('gen-active-list');
                if (!activeList) return;
                
                if (!status.active || status.active.length === 0) {
                    activeList.innerHTML = `
                        <div class="list-group-item text-center text-muted">
                            <p class="mb-0">No active generations</p>
                        </div>
                    `;
                    this.stopStatusPolling();
                    return;
                }
                
                activeList.innerHTML = status.active.map(gen => this.renderActiveGeneration(gen)).join('');
                
            } catch (error) {
                console.error('[SampleGeneratorUnified] Failed to update active generations:', error);
            }
        }

        renderActiveGeneration(gen) {
            const progress = gen.progress || 0;
            return `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <strong>${this.escapeHtml(gen.model || '—')}</strong> × 
                            <span class="text-secondary">${this.escapeHtml(gen.template || '—')}</span>
                        </div>
                        <span class="badge bg-primary">${progress}%</span>
                    </div>
                    <div class="progress progress-sm">
                        <div class="progress-bar" role="progressbar" style="width: ${progress}%" 
                             aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    ${gen.status ? `<div class="small text-muted mt-1">${this.escapeHtml(gen.status)}</div>` : ''}
                </div>
            `;
        }

        // ========================================================================
        // Navigation
        // ========================================================================

        navigateToResults() {
            const resultsTab = document.querySelector('[data-bs-target="#results"]');
            if (resultsTab) {
                const tab = new bootstrap.Tab(resultsTab);
                tab.show();
            }
        }

        // ========================================================================
        // API Helpers
        // ========================================================================

        async apiGet(endpoint, params = {}) {
            const url = new URL(this.apiBase + endpoint, window.location.origin);
            Object.keys(params).forEach(key => {
                if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                    url.searchParams.append(key, params[key]);
                }
            });
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        }

        async apiPost(endpoint, data = {}) {
            try {
                const url = this.apiBase + endpoint;
                console.log('[API] POST', url, data);
                
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout
                
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(data),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                console.log('[API] Response status:', response.status, response.statusText);
                
                if (!response.ok) {
                    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                    try {
                        const errorData = await response.json();
                        if (errorData.message || errorData.error) {
                            errorMessage = errorData.message || errorData.error;
                        }
                    } catch (e) {
                        // Failed to parse error response, use default message
                    }
                    throw new Error(errorMessage);
                }
                
                const result = await response.json();
                console.log('[API] Response data:', result);
                return result;
                
            } catch (error) {
                if (error.name === 'AbortError') {
                    console.error('[API] Request timeout after 2 minutes');
                    throw new Error('Request timeout - generation is taking too long');
                }
                console.error('[API] Request failed:', error);
                throw error;
            }
        }

        // ========================================================================
        // UI Helpers
        // ========================================================================

        setElementText(id, text) {
            const elem = document.getElementById(id);
            if (elem) {
                elem.textContent = text;
            }
        }

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        formatTimestamp(timestamp) {
            if (!timestamp) return '—';
            try {
                const date = new Date(timestamp);
                return date.toLocaleString();
            } catch {
                return timestamp;
            }
        }

        formatDuration(seconds) {
            if (!seconds || seconds === 0) return '—';
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            
            const parts = [];
            if (hours > 0) parts.push(`${hours}h`);
            if (minutes > 0) parts.push(`${minutes}m`);
            if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
            
            return parts.join(' ');
        }

        renderStatusBadge(status) {
            const statusMap = {
                'success': 'bg-success',
                'completed': 'bg-success',
                'failed': 'bg-danger',
                'error': 'bg-danger',
                'running': 'bg-primary',
                'pending': 'bg-secondary',
                'queued': 'bg-secondary'
            };
            
            const badgeClass = statusMap[status?.toLowerCase()] || 'bg-secondary';
            return `<span class="badge ${badgeClass}">${this.escapeHtml(status || 'Unknown')}</span>`;
        }

        showSuccess(message) {
            this.showNotification(message, 'success');
        }

        showError(message) {
            this.showNotification(message, 'danger');
        }

        showInfo(message) {
            this.showNotification(message, 'info');
        }

        showNotification(message, type = 'info') {
            // Simple alert for now - can be replaced with toast/modal
            console.log(`[${type.toUpperCase()}] ${message}`);
            
            // Try to use Tabler toast if available, else use native alert
            if (window.tabler && window.tabler.toast) {
                window.tabler.toast.show({
                    message: message,
                    type: type
                });
            } else {
                // Fallback to simple alert
                if (type === 'danger' || type === 'error') {
                    alert('Error: ' + message);
                } else if (type === 'info') {
                    // Create temporary toast-like element
                    const toast = document.createElement('div');
                    toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
                    toast.style.zIndex = '9999';
                    toast.innerHTML = message;
                    document.body.appendChild(toast);
                    setTimeout(() => toast.remove(), 5000);
                }
            }
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.SampleGeneratorUnified = new SampleGeneratorUnified();
        });
    } else {
        window.SampleGeneratorUnified = new SampleGeneratorUnified();
    }

    // Also initialize on HTMX afterSwap if tab is swapped in
    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail.target.id === 'generation' || event.detail.target.id === 'generation-tab') {
            if (!window.SampleGeneratorUnified) {
                window.SampleGeneratorUnified = new SampleGeneratorUnified();
            }
        }
    });

})();
