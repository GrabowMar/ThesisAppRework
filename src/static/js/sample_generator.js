(function() {
    const ROOT = document.getElementById('sample-generator');
    // Simple (htmx) mode: if root div has data-simple-sample-gen we bypass heavy JS
    const SIMPLE_MODE = !!ROOT?.hasAttribute('data-simple-sample-gen');
    const STUB_MODE = ROOT?.dataset.sgStubbed === 'true';
    if (window.SampleGeneratorApp || SIMPLE_MODE) {
        if (SIMPLE_MODE && !window.__SG_SIMPLE_NOTICE) {
            window.__SG_SIMPLE_NOTICE = true;
            console.info('[SampleGenerator] Simple mode active – skipping full SampleGeneratorApp class load.');
        }
        return;
    }

    window.__SG_STUB_MODE = STUB_MODE;

    /**
     * Sample Generator Frontend JavaScript
     * Provides interactive functionality for the sample generator web interface
     */

    class SampleGeneratorApp {
        constructor() {
        this.root = document.getElementById('sample-generator');
        this.stubbedMode = !!window.__SG_STUB_MODE;
        // Backend blueprint defines url_prefix='/api/sample-gen'
        // (Earlier version used '/api/sample_generator' leading to 404s like /api/sample_generator/api/sample_generator/*)
        this.apiBase = '/api/sample-gen';
            this.currentPage = 1;
            this.resultsPerPage = 50;
            this.currentFilters = {};
            this.batchStatus = null;
            this.activeTaskInterval = null;
            this.monitoringInterval = null;
            this.templates = [];
            this.models = [];
            this.currentTemplate = null;
            this.currentTemplateContent = '';
            this.currentResultId = null;
            this.results = [];
            this.currentModel = null;
            this.selectedTemplateName = '';
            this.logEntries = []; // Store log entries for filtering
            // Deduplicate repeated identical error messages
            this._lastErrorMessage = null;
            this._lastErrorTs = 0;
            // Flags to ensure we don't double-bind events on HTMX swaps
            this._generationEventsBound = false;
            this._templateEventsBound = false;
            this._resultsEventsBound = false;
            this._batchEventsBound = false;
            this._managementEventsBound = false;
            this._scaffoldingEventsBound = false;
            this._modelSettingsEventsBound = false;
            
            // Initialize the application
            this.init();
        }

        /**
         * Initialize the application
         */
        init() {
            this.bindEvents();
            if (this.stubbedMode) {
                this.scaffoldFetchStatus();
                return;
            }
            this.loadInitialData();
            this.updateStatus();
        }

        /**
         * Bind event handlers to UI elements
         */
        bindEvents() {
            // Tab switching
            document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(tab => {
                tab.addEventListener('shown.bs.tab', (e) => {
                    this.onTabChanged(e.target.getAttribute('href').substring(1));
                });
                tab.addEventListener('hide.bs.tab', (e) => {
                    const leavingTabId = e.target.getAttribute('href').substring(1);
                    if (leavingTabId === 'results-tab') {
                        this.stopCurrentGenerationsPolling();
                    }
                });
            });

            if (!this.stubbedMode) {
                // Generation tab events
                this.bindGenerationEvents();
                
                // Templates tab events
                this.bindTemplateEvents();
                
                // Results tab events
                this.bindResultsEvents();
                
                // Batch tab events
                this.bindBatchEvents();
                
                // Management tab events
                this.bindManagementEvents();

                // Global refresh
                document.getElementById('global-refresh-btn')?.addEventListener('click', () => {
                    this.refreshAll();
                });
            } else {
                const refreshBtn = document.getElementById('global-refresh-btn');
                if (refreshBtn) {
                    refreshBtn.addEventListener('click', (event) => {
                        event.preventDefault();
                        this.showInfo('Sample generator controls are temporarily disabled.');
                    }, { once: true });
                }
            }

            // Scaffolding tab events
            this.bindScaffoldingEvents();
            this.bindModelSettingsEvents();
        }

        /**
         * Bind generation tab events
         */
        bindGenerationEvents() {
            if (this._generationEventsBound) return; // idempotent
            this._generationEventsBound = true;
            // Template selection change
            document.getElementById('template-select')?.addEventListener('change', (e) => {
                const value = e.target.value;
                this.selectedTemplateName = value || '';
                if (value) {
                    this.loadTemplateContent(value);
                }
                this.updateGenerateButtonState();
            });

            // Reload templates button
            document.getElementById('reload-templates-btn')?.addEventListener('click', () => {
                this.reloadTemplates();
            });

            // New SG Template button
            document.getElementById('new-sg-template-btn')?.addEventListener('click', () => {
                this.createNewAppTemplate();
            });

            // Replace files button
            document.getElementById('generate-btn')?.addEventListener('click', () => {
                this.generateSample();
            });

            // Model selection change -> update enable/disable state
            document.getElementById('model-select')?.addEventListener('change', () => {
                const value = document.getElementById('model-select')?.value || '';
                this.currentModel = value || null;
                this.updateGenerateButtonState();
            });

            // Initial state
            this.updateGenerateButtonState();

            // Refresh recent generations
            document.getElementById('refresh-recent-btn')?.addEventListener('click', () => {
                this.loadRecentGenerations();
            });
        }

        /**
         * Bind template tab events
         */
        bindTemplateEvents() {
            if (this._templateEventsBound) return; // idempotent
            this._templateEventsBound = true;
            // Load template button
            document.getElementById('load-template-btn')?.addEventListener('click', () => {
                this.showTemplateLoader();
            });

            // Create new template button
            document.getElementById('create-template-btn')?.addEventListener('click', () => {
                this.showTemplateEditor();
            });

            // Template search
            document.getElementById('template-search')?.addEventListener('input', (e) => {
                this.filterTemplates(e.target.value);
            });

            // Save template button in modal
            document.getElementById('save-template-btn')?.addEventListener('click', () => {
                this.saveTemplate();
            });

            // Delete template button in modal
            document.getElementById('delete-template-btn')?.addEventListener('click', () => {
                this.deleteTemplate();
            });
        }

        /**
         * Bind results tab events
         */
        bindResultsEvents() {
            if (this._resultsEventsBound) {
                console.log('[SampleGenerator] Results events already bound, skipping');
                return;
            }
            console.log('[SampleGenerator] Binding results tab events');
            this._resultsEventsBound = true;
            // Apply filters
            document.getElementById('apply-filters-btn')?.addEventListener('click', () => {
                console.log('[SampleGenerator] Apply filters clicked');
                this.applyResultsFilters();
            });

            // Refresh results
            document.getElementById('refresh-results-btn')?.addEventListener('click', () => {
                this.loadResults();
            });

            // Refresh current generations
            document.getElementById('refresh-current-gens-btn')?.addEventListener('click', () => {
                this.loadCurrentGenerations();
            });

            // Cleanup dialog
            document.getElementById('cleanup-dialog-btn')?.addEventListener('click', () => {
                this.showCleanupDialog();
            });

            // Execute cleanup
            document.getElementById('execute-cleanup-btn')?.addEventListener('click', () => {
                this.executeCleanup();
            });

            // Copy content button
            document.getElementById('copy-content-btn')?.addEventListener('click', () => {
                this.copyResultContent();
            });

            // Regenerate button
            document.getElementById('regenerate-btn')?.addEventListener('click', () => {
                this.regenerateResult();
            });

            // Delete result button
            document.getElementById('delete-result-btn')?.addEventListener('click', () => {
                this.deleteResult();
            });
        }

        /**
         * Bind batch tab events
         */
        bindBatchEvents() {
            if (this._batchEventsBound) return; // idempotent
            this._batchEventsBound = true;
            // Select all checkboxes
            document.getElementById('select-all-templates')?.addEventListener('change', (e) => {
                this.toggleAllTemplates(e.target.checked);
            });

            document.getElementById('select-all-models')?.addEventListener('change', (e) => {
                this.toggleAllModels(e.target.checked);
            });

            // Preview batch
            document.getElementById('preview-batch-btn')?.addEventListener('click', () => {
                this.previewBatch();
            });

            // Start batch
            document.getElementById('start-batch-btn')?.addEventListener('click', () => {
                this.startBatch();
            });

            // Confirm batch in modal
            document.getElementById('confirm-batch-btn')?.addEventListener('click', () => {
                this.confirmBatch();
            });

            // Batch control buttons
            document.getElementById('pause-batch-btn')?.addEventListener('click', () => {
                this.pauseBatch();
            });

            document.getElementById('cancel-batch-btn')?.addEventListener('click', () => {
                this.cancelBatch();
            });

            // Refresh tasks
            document.getElementById('refresh-tasks-btn')?.addEventListener('click', () => {
                this.loadActiveTasks();
            });
        }

        /**
         * Bind management tab events
         */
        bindManagementEvents() {
            if (this._managementEventsBound) return; // idempotent
            this._managementEventsBound = true;
            
            // System status refresh
            document.getElementById('refresh-system-status-btn')?.addEventListener('click', () => {
                this.loadSystemStatus();
            });

            // Quick actions
            document.getElementById('force-refresh-btn')?.addEventListener('click', () => {
                this.forceRefresh();
            });

            document.getElementById('reload-templates-management-btn')?.addEventListener('click', () => {
                this.loadTemplates().then(() => {
                    this.showSuccess('Templates reloaded successfully.');
                });
            });

            document.getElementById('view-generated-folder-btn')?.addEventListener('click', () => {
                this.showInfo('Generated apps are located in the <code>generated/apps/</code> folder in the project root.');
            });

            // Log controls
            document.getElementById('refresh-logs-btn')?.addEventListener('click', () => {
                this.loadSystemLogs();
            });

            document.getElementById('clear-logs-display-btn')?.addEventListener('click', () => {
                this.clearLogsDisplay();
            });

            // Log filter
            document.getElementById('log-filter')?.addEventListener('input', (e) => {
                this.filterLogs(e.target.value);
            });
        }

        /**
         * Bind scaffolding tab events
         */
        bindScaffoldingEvents() {
            if (this._scaffoldingEventsBound) return; // idempotent
            this._scaffoldingEventsBound = true;
            
            document.getElementById('scaffold-parse-btn')?.addEventListener('click', () => {
                this.scaffoldParseModels();
            });

            document.getElementById('scaffold-validate-templates-btn')?.addEventListener('click', () => {
                this.scaffoldValidateTemplates();
            });
            document.getElementById('scaffold-dryrun-btn')?.addEventListener('click', () => {
                this.scaffoldGenerate(true);
            });
            document.getElementById('scaffold-generate-btn')?.addEventListener('click', () => {
                this.scaffoldGenerate(false);
            });
            
            // Check for models selected from Models page and auto-populate
            this.checkScaffoldingModelSelection();
        }

        bindModelSettingsEvents() {
            if (this._modelSettingsEventsBound) return;
            this._modelSettingsEventsBound = true;
            const resetBtn = document.getElementById('sg-reset-model-settings');
            resetBtn?.addEventListener('click', (event) => {
                event.preventDefault();
                this.resetModelSettings();
            });
            const inputs = document.querySelectorAll('[data-sg-setting]');
            inputs.forEach(input => {
                input.addEventListener('change', () => this.updateModelSettingsSummary());
                input.addEventListener('input', () => this.updateModelSettingsSummary());
            });
            this.updateModelSettingsSummary();
        }

        /**
         * Load initial data when the application starts
         */
        async loadInitialData() {
            if (this.stubbedMode) return;
            try {
                await Promise.all([
                    this.loadTemplates(),
                    this.loadModels(),
                    this.loadRecentGenerations()
                ]);
                this.autoSelectDefaults();
            } catch (error) {
                console.error('Failed to load initial data:', error);
                this.showError('Failed to load initial data');
            }
        }

        /**
         * Handle tab changes
         */
        onTabChanged(tabId) {
            if (this.stubbedMode) {
                if (tabId === 'scaffolding' || tabId === 'scaffolding-tab') {
                    this.scaffoldFetchStatus();
                }
                return;
            }
            switch (tabId) {
                case 'generation-tab':
                    break;
                case 'templates-tab':
                    this.loadTemplatesList();
                    break;
                case 'results-tab':
                    this.loadResults();
                    this.loadCurrentGenerations();
                    this.startCurrentGenerationsPolling();
                    break;
                case 'batch-tab':
                    this.loadBatchData();
                    break;
                case 'management-tab':
                    this.loadSystemStatus();
                    break;
                case 'scaffolding-tab':
                    // lazy status fetch
                    this.scaffoldFetchStatus();
                    // Check for pre-selected model
                    this.checkScaffoldingModelSelection();
                    break;
            }
        }

        /**
         * API helper methods
         */
        async apiCall(endpoint, options = {}) {
            const ep = this._normalizeEndpoint(endpoint);
            const url = `${this.apiBase}${ep}`;
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            };

            try {
                const response = await fetch(url, { ...defaultOptions, ...options });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return await response.json();
                } else {
                    return await response.text();
                }
            } catch (error) {
                console.error(`API call failed: ${endpoint}`, error);
                throw error;
            }
        }

        async get(endpoint, params = {}) {
            const ep = this._normalizeEndpoint(endpoint);
            const url = new URL(`${this.apiBase}${ep}`, window.location.origin);
            Object.keys(params).forEach(key => {
                if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                    url.searchParams.append(key, params[key]);
                }
            });
            return this.apiCall(url.pathname + url.search);
        }

        async post(endpoint, data = {}) {
            return this.apiCall(endpoint, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        }

        async put(endpoint, data = {}) {
            return this.apiCall(endpoint, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        }

        async delete(endpoint) {
            return this.apiCall(endpoint, {
                method: 'DELETE'
            });
        }

        /**
         * Load templates from API
         */
        async loadTemplates() {
            try {
                const response = await this.get('/templates');
                // API returns { success, message, timestamp, data: [...] }
                // Older code expected response.templates. Normalize here.
                let rawTemplates = response.data || response.templates || [];
                // Ensure objects have a name property; backend uses 'name' already.
                this.templates = this._normalizeTemplateList(rawTemplates);
                this.updateTemplateSelect();
                this.updateBatchTemplates();
                this.loadTemplatesList();
                this.autoSelectDefaults();
            } catch (error) {
                console.error('Failed to load templates:', error);
                this.showError('Failed to load templates');
            }
        }

        /**
         * Load models from API
         */
        async loadModels(detail = true) {
            try {
                const response = await this.get(`/models${detail ? '?detail=1&mode=all' : ''}`);
                let rawModels = response.data || response.models || [];
                
                // Only use models from database - filter out any that don't have real data
                this.models = Array.isArray(rawModels) ? rawModels.filter(m => {
                    // Skip if it's just a string or doesn't have proper structure
                    if (typeof m === 'string') return false;
                    // Must have a name and should have been fetched from DB
                    return m.name && m.id; // id indicates it's from database
                }).map(m => {
                    return {
                        id: m.id,
                        name: m.name,
                        provider: m.provider || (m.name.split('/')[0] || 'unknown'),
                        is_free: !!m.is_free,
                        capabilities: m.capabilities || [],
                        installed: !!m.installed
                    };
                }) : [];
                
                this.updateModelSelect();
                this.updateBatchModels();
                this.populateModelFilters();
                this.autoSelectDefaults();
                this.updateGenerateButtonState();
            } catch (error) {
                console.error('Failed to load models:', error);
                this.showError('Failed to load models');
            }
        }

        autoSelectDefaults() {
            const templateSelect = document.getElementById('template-select');
            if (templateSelect && !templateSelect.value && templateSelect.options.length > 1) {
                templateSelect.selectedIndex = 1;
                templateSelect.dispatchEvent(new Event('change'));
            }

            const modelSelect = document.getElementById('model-select');
            if (modelSelect && !modelSelect.value && modelSelect.options.length > 1) {
                modelSelect.selectedIndex = 1;
                modelSelect.dispatchEvent(new Event('change'));
            }

            this.updateGenerateButtonState();
        }

        _normalizeTemplateList(rawTemplates) {
            if (!Array.isArray(rawTemplates)) return [];
            const normalized = rawTemplates.map((template) => this._normalizeTemplate(template));
            normalized.sort((a, b) => this._compareTemplates(a, b));
            return normalized;
        }

        _normalizeTemplate(templateInput) {
            const template = { ...templateInput };
            const rawAppNum = template.app_num ?? template.appNum;
            const parsedNum = typeof rawAppNum === 'number' ? rawAppNum : parseInt(rawAppNum, 10);
            template.app_num = Number.isFinite(parsedNum) ? parsedNum : null;
            const typeGuess = (template.template_type || template.type || '').toString().trim().toLowerCase();
            template.template_type = typeGuess || 'generic';
            if (!template.display_name) {
                template.display_name = this._buildTemplateDisplayName(template);
            }
            return template;
        }

        _compareTemplates(a, b) {
            const toNumber = (value) => {
                if (typeof value === 'number' && Number.isFinite(value)) return value;
                const parsed = parseInt(value, 10);
                return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
            };
            const typeRank = (template) => {
                const ranks = { backend: 0, frontend: 1 };
                const key = (template?.template_type || '').toString().toLowerCase();
                return ranks[key] ?? 2;
            };
            const nameA = (a.display_name || a.name || '').toString().toLowerCase();
            const nameB = (b.display_name || b.name || '').toString().toLowerCase();
            const numA = toNumber(a.app_num);
            const numB = toNumber(b.app_num);
            if (numA !== numB) return numA - numB;
            const rankDiff = typeRank(a) - typeRank(b);
            if (rankDiff !== 0) return rankDiff;
            return nameA.localeCompare(nameB);
        }

        _buildTemplateDisplayName(template) {
            const numberPart = Number.isFinite(template.app_num)
                ? `App ${template.app_num.toString().padStart(2, '0')}`
                : '';
            const typePart = template.template_type && template.template_type !== 'generic'
                ? template.template_type.charAt(0).toUpperCase() + template.template_type.slice(1)
                : '';
            const labelPart = this._deriveTemplateLabelFromName(template.name, template.template_type);
            const prefix = [numberPart, typePart].filter(Boolean).join(' ');
            if (prefix && labelPart) return `${prefix} – ${labelPart}`;
            if (prefix) return prefix;
            return labelPart || template.name;
        }

        _deriveTemplateLabelFromName(name, templateType) {
            if (!name) return '';
            let working = name;
            if (working.startsWith('app_')) {
                const segments = working.split('_');
                if (segments.length >= 4) {
                    working = segments.slice(3).join('_');
                } else if (segments.length >= 3) {
                    working = segments.slice(2).join('_');
                } else {
                    working = segments.slice(1).join('_');
                }
            }
            working = working.replace(/[_-]+/g, ' ');
            working = working.replace(/([a-z])([A-Z])/g, '$1 $2');
            working = working.replace(/\s+/g, ' ').trim();
            if (!working) {
                if (templateType && templateType !== 'generic') {
                    return templateType.charAt(0).toUpperCase() + templateType.slice(1);
                }
                return '';
            }
            const overrides = {
                iot: 'IoT',
                api: 'API',
                crm: 'CRM',
                erp: 'ERP',
                ui: 'UI',
                ux: 'UX',
            };
            return working.split(' ').map((part) => {
                const lower = part.toLowerCase();
                if (overrides[lower]) return overrides[lower];
                if (part.length <= 2) return part.toUpperCase();
                if (part === part.toUpperCase()) return part;
                return part.charAt(0).toUpperCase() + part.slice(1);
            }).join(' ');
        }

        /**
         * Update template select dropdown
         */
        updateTemplateSelect() {
            const select = document.getElementById('template-select');
            if (!select) return;

            const previous = select.value;
            select.innerHTML = '<option value="">Select a template...</option>';
            
            // Group templates by app_num to avoid duplicates (frontend/backend pairs)
            const templateGroups = new Map();
            this.templates.forEach(template => {
                if (Number.isFinite(template.app_num)) {
                    const key = template.app_num;
                    if (!templateGroups.has(key)) {
                        templateGroups.set(key, []);
                    }
                    templateGroups.get(key).push(template);
                } else {
                    // Handle templates without app_num (fallback for older templates)
                    templateGroups.set(template.name, [template]);
                }
            });
            
            // Sort groups by app_num
            const sortedGroups = Array.from(templateGroups.entries()).sort((a, b) => {
                if (typeof a[0] === 'number' && typeof b[0] === 'number') {
                    return a[0] - b[0];
                }
                return String(a[0]).localeCompare(String(b[0]));
            });
            
            sortedGroups.forEach(([key, templates]) => {
                const option = document.createElement('option');
                option.value = typeof key === 'number' ? key.toString() : key;
                
                // Use the display name from the first template, preferring backend over frontend
                let representativeTemplate = templates[0];
                const backendTemplate = templates.find(t => t.template_type && t.template_type.toLowerCase().includes('backend'));
                if (backendTemplate) {
                    representativeTemplate = backendTemplate;
                }
                
                const badge = templates.some(t => t.has_extra_prompt) ? ' *' : '';
                const label = representativeTemplate.display_name || representativeTemplate.name;
                
                // Show component info if we have both frontend and backend
                const hasBackend = templates.some(t => !t.template_type || t.template_type.toLowerCase().includes('backend') || t.template_type === 'generic');
                const hasFrontend = templates.some(t => t.template_type && t.template_type.toLowerCase().includes('frontend'));
                let componentInfo = '';
                if (hasBackend && hasFrontend) {
                    componentInfo = ' (Frontend + Backend)';
                } else if (hasBackend) {
                    componentInfo = ' (Backend only)';
                } else if (hasFrontend) {
                    componentInfo = ' (Frontend only)';
                }
                
                option.textContent = `${label}${componentInfo}${badge}`;
                
                if (typeof key === 'number') {
                    option.dataset.appNum = key;
                }
                if (templates.some(t => t.has_extra_prompt)) {
                    option.title = 'Has extra prompt context';
                }
                select.appendChild(option);
            });

            if (previous) {
                select.value = previous;
            }

            if (!select.value && this.currentTemplate) {
                const targetValue = Number.isFinite(this.currentTemplate.app_num) ? 
                    this.currentTemplate.app_num.toString() : this.currentTemplate.name;
                select.value = targetValue;
            }
        }

        /**
         * Update model select dropdown
         */
        updateModelSelect() {
            const select = document.getElementById('model-select');
            if (!select) return;

            const previous = select.value;
            select.innerHTML = '<option value="">Select a model...</option>';
            this.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                const freeBadge = model.is_free ? ' [FREE]' : '';
                option.textContent = `${model.name}${freeBadge} (${model.provider || 'Unknown'})`;
                if (model.is_free) option.classList.add('text-success');
                select.appendChild(option);
            });

            if (previous) {
                select.value = previous;
            }

            if (!select.value && this.currentModel) {
                select.value = this.currentModel;
            }
        }

        populateModelFilters() {
            const filter = document.getElementById('results-model-filter');
            if (!filter) return;
            const previous = filter.value;
            filter.innerHTML = '<option value="">All models</option>';
            this.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = model.name;
                filter.appendChild(option);
            });
            if (previous) {
                filter.value = previous;
            }
        }

        /**
         * Update batch template checkboxes
         */
        updateBatchTemplates() {
            const container = document.getElementById('templates-checkbox-list');
            if (!container) return;

            if (this.templates.length === 0) {
                container.innerHTML = '<div class="col-12 text-center text-muted py-3">No templates available</div>';
                return;
            }

            container.innerHTML = '';
            const templates = [...this.templates].sort((a, b) => this._compareTemplates(a, b));
            templates.forEach(template => {
                const col = document.createElement('div');
                col.className = 'col-md-6 mb-2';
                col.innerHTML = `
                    <div class="form-check">
                        <input class="form-check-input template-checkbox" type="checkbox" value="${template.name}" id="template-${template.name}">
                        <label class="form-check-label" for="template-${template.name}">
                            ${template.display_name || template.name} ${template.has_extra_prompt ? '<span class="badge bg-info ms-1">ctx</span>' : ''}
                        </label>
                    </div>
                `;
                container.appendChild(col);
            });

            // Add event listeners for selection counting
            container.querySelectorAll('.template-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', () => {
                    this.updateTemplateCount();
                    this.updateBatchPreview();
                });
            });
        }

        /** Reload templates from disk via backend directory loader */
        async reloadTemplates() {
            try {
                const directory = 'misc/app_templates';
                const res = await this.post('/templates/load-dir', { directory });
                console.log('Reload templates result', res);
                await this.loadTemplates();
                this.showSuccess('Templates reloaded');
            } catch (e) {
                console.error('Failed to reload templates', e);
                this.showError('Reload failed');
            }
        }

        /** Create a new app template persisted to misc/app_templates */
        async createNewAppTemplate() {
            try {
                const name = prompt('Enter new template base name (e.g. app_31_backend_custom)');
                if (!name) return;
                // Basic sanitization
                const safe = name.replace(/[^a-zA-Z0-9_\-]/g, '_');
                const filename = safe.endsWith('.md') ? safe : `${safe}.md`;
                const content = prompt('Enter initial template content (markdown). You can edit later.','New application template\n\nDescribe the application requirements here.');
                if (content == null) return;
                // Persist using TemplateStoreService (category 'app')
                const saveRes = await fetch(`/api/templates/app/${encodeURIComponent(filename)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content })
                });
                if (!saveRes.ok) throw new Error('Save failed');
                // Now reload sample generation registry to pick it up
                await this.reloadTemplates();
                // Pre-select new template if present
                const select = document.getElementById('template-select');
                if (select) {
                    select.value = safe;
                }
                this.showSuccess('Template created');
            } catch (e) {
                console.error('Failed to create template', e);
                this.showError('Create failed');
            }
        }

        /**
         * Update batch model checkboxes
         */
        updateBatchModels() {
            const container = document.getElementById('models-checkbox-list');
            if (!container) return;

            if (this.models.length === 0) {
                container.innerHTML = '<div class="col-12 text-center text-muted py-3">No models available</div>';
                return;
            }

            container.innerHTML = '';
            this.models.forEach(model => {
                const col = document.createElement('div');
                col.className = 'col-md-6 mb-2';
                col.innerHTML = `
                    <div class="form-check">
                        <input class="form-check-input model-checkbox" type="checkbox" value="${model.name}" id="model-${model.name}">
                        <label class="form-check-label" for="model-${model.name}">
                            ${model.name} ${model.is_free ? '<span class="badge bg-success ms-1">FREE</span>' : ''}
                        </label>
                    </div>
                `;
                container.appendChild(col);
            });

            // Add event listeners for selection counting
            container.querySelectorAll('.model-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', () => {
                    this.updateModelCount();
                    this.updateBatchPreview();
                });
            });
        }

        /**
         * Replace files using AI-generated code
         */
        async generateSample() {
            const templateName = document.getElementById('template-select')?.value;
            const modelName = document.getElementById('model-select')?.value;
            const maxConcurrent = parseInt(document.getElementById('max-concurrent')?.value) || 1;
            const timeout = parseInt(document.getElementById('request-timeout')?.value) || 300;

            if (!templateName || !modelName) {
                this.showError('Please select both template and model');
                return;
            }

            // Show confirmation dialog for file replacement
            if (!confirm('This will replace existing application files with AI-generated code. Backups will be created automatically. Continue?')) {
                return;
            }

            this.selectedTemplateName = templateName;
            this.currentModel = modelName;

            // Get the new replacement options
            const generateFrontend = document.getElementById('generate-frontend')?.checked ?? true;
            const generateBackend = document.getElementById('generate-backend')?.checked ?? true;
            const createBackup = document.getElementById('create-backup')?.checked ?? true;

            // Validate that at least one component is selected
            if (!generateFrontend && !generateBackend) {
                this.showError('Please select at least one component (Frontend or Backend)');
                return;
            }

            // Build confirmation message based on selected options
            const components = [];
            if (generateFrontend) components.push('frontend');
            if (generateBackend) components.push('backend');
            const backupMsg = createBackup ? 'Backups will be created automatically.' : 'No backups will be created.';
            
            if (!confirm(`This will replace existing ${components.join(' and ')} files with AI-generated code. ${backupMsg} Continue?`)) {
                return;
            }

            const modelOverrides = this.collectModelSettings();
            this.updateModelSettingsSummary(modelOverrides);

            try {
                this.showLoading(`Replacing ${components.join(' and ')} files with AI-generated code...`);
                
                const payload = {
                    template_id: templateName,
                    template: templateName,
                    template_name: templateName,
                    model: modelName,
                    model_name: modelName,
                    max_concurrent: maxConcurrent,
                    request_timeout: timeout,
                    create_backup: createBackup,
                    generate_frontend: generateFrontend,
                    generate_backend: generateBackend
                };

                Object.assign(payload, modelOverrides);

                const response = await this.post('/generate', payload);

                this.hideLoading();
                
                if (response.success) {
                    const backupNote = createBackup ? ' Backups were created for existing files.' : '';
                    this.showSuccess(`${components.join(' and ')} files replaced successfully!${backupNote}`);
                    this.loadRecentGenerations();
                } else {
                    this.showError(response.error || 'File replacement failed');
                }
            } catch (error) {
                this.hideLoading();
                this.showError('Failed to replace files');
            }
        }

        /**
         * Load recent generations
         */
        async loadRecentGenerations() {
            try {
                const response = await this.get('/results', { limit: 10 });
                const data = response.data || response.results || [];
                this.updateRecentGenerationsTable(Array.isArray(data) ? data : []);
            } catch (error) {
                console.error('Failed to load recent generations:', error);
            }
        }

        /**
         * Update recent generations table
         */
        updateRecentGenerationsTable(results) {
            const tbody = document.querySelector('#recent-generations-table tbody');
            if (!tbody) return;

            if (results.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No recent generations</td></tr>';
                return;
            }

            tbody.innerHTML = results.map(result => `
                <tr>
                    <td>${result.result_id || result.id || '—'}</td>
                    <td>${result.template_name || result.app_name || `App #${result.app_num ?? '—'}`}</td>
                    <td>${result.model || result.model_name || '—'}</td>
                    <td>
                        <span class="badge ${result.success ? 'bg-success' : 'bg-danger'}">
                            ${result.success ? 'Success' : 'Failed'}
                        </span>
                    </td>
                    <td>${this.formatDuration(result.duration ?? result.generation_time)}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="window.sampleGeneratorAppInstance.viewApplicationDetail('${result.model}', ${result.app_num || 1})">
                            View App
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        /**
         * Utility methods
         */
        formatDuration(seconds) {
            if (seconds === undefined || seconds === null) return '—';
            const value = Number(seconds);
            if (!Number.isFinite(value)) return '—';
            if (value < 60) return `${value.toFixed(1)}s`;
            const minutes = Math.floor(value / 60);
            const secs = value % 60;
            return `${minutes}m ${secs.toFixed(0)}s`;
        }

        formatFileSize(bytes) {
            if (!bytes) return '0 B';
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(1024));
            return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
        }

        formatTimestamp(timestamp) {
            return new Date(timestamp).toLocaleString();
        }

        escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        /**
         * UI feedback methods
         */
        showLoading(message = 'Loading...') {
            // Implementation depends on your loading indicator approach
            console.log('Loading:', message);
        }

        hideLoading() {
            console.log('Loading complete');
        }

        showError(message) {
            const now = Date.now();
            // Suppress duplicate errors fired within 1.5s
            if (message === this._lastErrorMessage && (now - this._lastErrorTs) < 1500) {
                return;
            }
            this._lastErrorMessage = message;
            this._lastErrorTs = now;
            let container = document.getElementById('sg-inline-error');
            if (!container) {
                container = document.createElement('div');
                container.id = 'sg-inline-error';
                container.className = 'alert alert-danger py-2 px-3 mb-2';
                // Insert near the top of the generation panel if present
                const parent = document.getElementById('generation-tab') || document.body;
                parent.prepend(container);
            }
            container.textContent = message;
            container.style.display = 'block';
            clearTimeout(this._hideErrorTimeout);
            this._hideErrorTimeout = setTimeout(() => {
                if (container) container.style.display = 'none';
            }, 4000);
        }

        showSuccess(message) {
            // You could use Bootstrap alerts, toast notifications, etc.
            console.log(`Success: ${message}`);
        }

        showInfo(message) {
            console.info(`Info: ${message}`);
        }

        /**
         * Update status dashboard
         */
        async updateStatus() {
            if (this.stubbedMode) return;
            try {
                const response = await this.get('/status');
                
                // Update status indicators
                // NOTE: Optional chaining cannot be used on the left-hand side of an assignment.
                // Use helper that checks element existence instead.
                this._setText('total-generations', response.total_results || 0);
                this._setText('active-tasks', response.active_tasks || 0);
                this._setText('available-templates', response.total_templates || 0);
                this._setText('connected-models', response.total_models || 0);
                
                // Update system status
                const statusEl = document.getElementById('system-status');
                if (statusEl) {
                    statusEl.className = `badge ${response.system_healthy ? 'bg-success' : 'bg-warning'}`;
                    statusEl.textContent = response.system_healthy ? 'Healthy' : 'Issues';
                }
            } catch (error) {
                console.error('Failed to update status:', error);
            }
        }

        /**
         * Refresh all data
         */
        async refreshAll() {
            if (this.stubbedMode) {
                this.showInfo('Sample generator controls are temporarily disabled.');
                return;
            }
            await this.loadInitialData();
            await this.updateStatus();
            this.showSuccess('Data refreshed');
        }

        // Placeholder methods for additional functionality
        // These would be implemented based on specific requirements

        async loadTemplateContent(templateName) {
            if (!templateName) return;
            const preview = document.getElementById('template-preview');
            const detailPreview = document.getElementById('template-detail-preview');
            if (preview) preview.textContent = 'Loading template...';
            if (detailPreview) detailPreview.textContent = 'Loading template...';

            const meta = this.templates.find(t => t.name === templateName || String(t.app_num) === String(templateName)) || null;
            let filename = templateName;
            if (!filename.endsWith('.md') && !filename.endsWith('.txt')) {
                filename = `${templateName}.md`;
            }

            try {
                const response = await fetch(`/api/sample-gen/templates/app/${encodeURIComponent(filename)}`);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const result = await response.json();
                
                // Handle both old format (direct content) and new format (data.content)
                const content = result.data?.content || result.content || '';
                const templateData = result.data || result;
                
                this.currentTemplate = meta ? { ...meta, filename } : { name: templateName, filename };
                this.currentTemplateContent = content;
                if (preview) preview.textContent = content || 'Template is empty.';
                if (detailPreview) detailPreview.textContent = content || 'Template is empty.';
                
                // Update template details with enhanced information
                const enhancedMeta = meta ? {
                    ...meta,
                    has_frontend: templateData.has_frontend,
                    has_backend: templateData.has_backend,
                    frontend_requirements: templateData.frontend_requirements || [],
                    backend_requirements: templateData.backend_requirements || []
                } : null;
                
                this.updateTemplateDetails(enhancedMeta, content);
            } catch (error) {
                console.error('Failed to load template content:', error);
                if (preview) preview.textContent = 'Unable to load template.';
                if (detailPreview) detailPreview.textContent = 'Unable to load template.';
                this.showError('Failed to load template content');
            }
        }

        showTemplateLoader() {
            if (!this.templates.length) {
                this.showInfo('No templates available.');
                return;
            }
            const select = document.getElementById('template-select');
            const name = select?.value || this.templates[0].name;
            this.openTemplateModal(name);
        }

        showTemplateEditor() {
            this.openTemplateModal(null);
        }

        openTemplateModal(templateName) {
            const modalEl = document.getElementById('template-modal');
            if (!modalEl) return;
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            const nameInput = document.getElementById('template-modal-name');
            const appInput = document.getElementById('template-modal-app');
            const contentArea = document.getElementById('template-modal-content');
            const pathInput = document.getElementById('template-modal-path');
            if (!nameInput || !appInput || !contentArea || !pathInput) return;

            if (templateName) {
                const meta = this.templates.find(t => t.name === templateName || String(t.app_num) === String(templateName)) || null;
                const appNum = meta?.app_num || 1;
                nameInput.value = meta?.name || templateName;
                appInput.value = appNum;
                pathInput.value = meta?.filename || '';
                this.loadTemplateContent(templateName).then(() => {
                    contentArea.value = this.currentTemplateContent || '';
                });
            } else {
                nameInput.value = '';
                appInput.value = this.templates.length + 1;
                contentArea.value = '';
                pathInput.value = '';
                this.currentTemplate = null;
                this.currentTemplateContent = '';
            }
            modal.show();
        }

        filterTemplates(searchTerm) {
            const tbody = document.getElementById('templates-table-body');
            if (!tbody) return;
            const term = (searchTerm || '').toLowerCase();
            tbody.querySelectorAll('tr[data-template-name]').forEach(row => {
                const name = row.dataset.templateName || '';
                const requirements = row.dataset.templateRequirements || '';
                const visible = !term || name.toLowerCase().includes(term) || requirements.toLowerCase().includes(term);
                row.style.display = visible ? '' : 'none';
            });
        }

        async saveTemplate() {
            const nameInput = document.getElementById('template-modal-name');
            const appInput = document.getElementById('template-modal-app');
            const contentArea = document.getElementById('template-modal-content');
            const pathInput = document.getElementById('template-modal-path');
            if (!nameInput || !appInput || !contentArea || !pathInput) return;

            const rawName = nameInput.value.trim();
            if (!rawName) {
                this.showError('Template name is required.');
                return;
            }
            const filename = rawName.endsWith('.md') || rawName.endsWith('.txt') ? rawName : `${rawName}.md`;
            const content = contentArea.value || '';

            try {
                const response = await fetch(`/api/templates/app/${encodeURIComponent(filename)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content })
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                this.showInfo('Template saved.');
                const modalEl = document.getElementById('template-modal');
                bootstrap.Modal.getOrCreateInstance(modalEl).hide();
                await this.reloadTemplates();
                const select = document.getElementById('template-select');
                if (select) select.value = rawName.replace(/\.md$/i, '');
                this.loadTemplateContent(rawName.replace(/\.md$/i, ''));
            } catch (error) {
                console.error('Failed to save template:', error);
                this.showError('Failed to save template');
            }
        }

        async deleteTemplate() {
            const nameInput = document.getElementById('template-modal-name');
            if (!nameInput) return;
            const rawName = nameInput.value.trim();
            if (!rawName) {
                this.showError('Select a template to delete.');
                return;
            }
            if (!confirm(`Delete template ${rawName}? This cannot be undone.`)) return;
            const filename = rawName.endsWith('.md') || rawName.endsWith('.txt') ? rawName : `${rawName}.md`;
            try {
                const response = await fetch(`/api/templates/app/${encodeURIComponent(filename)}`, {
                    method: 'DELETE'
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                this.showInfo('Template deleted.');
                bootstrap.Modal.getOrCreateInstance(document.getElementById('template-modal')).hide();
                await this.reloadTemplates();
                this.loadTemplatesList();
            } catch (error) {
                console.error('Failed to delete template:', error);
                this.showError('Failed to delete template');
            }
        }

        loadTemplatesList() {
            const tbody = document.getElementById('templates-table-body');
            const badge = document.getElementById('template-detail-badge');
            if (!tbody) return;

            if (!this.templates.length) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">No templates loaded.</td></tr>';
                if (badge) badge.textContent = 'No templates';
                return;
            }

            const templates = [...this.templates].sort((a, b) => this._compareTemplates(a, b));
            tbody.innerHTML = templates.map(template => {
                const ctxBadge = template.has_extra_prompt ? '<span class="badge bg-info ms-1">ctx</span>' : '';
                const complexity = template.complexity_score ? `${(template.complexity_score * 100).toFixed(0)}%` : 'n/a';
                const reqs = (template.requirements || []).join(', ');
                const displayLabel = template.display_name || template.name;
                const appNumber = Number.isFinite(template.app_num)
                    ? template.app_num.toString().padStart(2, '0')
                    : '—';
                return `
                    <tr data-template-name="${template.name}" data-template-requirements="${reqs}">
                        <td>
                            <button type="button" class="btn btn-link btn-sm p-0" data-template="${template.name}">
                                ${displayLabel}${ctxBadge}
                            </button>
                        </td>
                        <td>${appNumber}</td>
                        <td>${reqs || '<span class="text-muted">—</span>'}</td>
                        <td class="text-end">${complexity}</td>
                    </tr>`;
            }).join('');

            tbody.querySelectorAll('button[data-template]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const name = btn.getAttribute('data-template');
                    if (name) {
                        this.loadTemplateContent(name);
                        this.openTemplateModal(name);
                    }
                });
            });

            if (badge) {
                const selectEl = document.getElementById('template-select');
                const selectedName = selectEl?.value || this.selectedTemplateName || this.currentTemplate?.name || null;
                const current = selectedName ? templates.find(t => t.name === selectedName) : null;
                if (current) {
                    const typeLabel = current.template_type && current.template_type !== 'generic'
                        ? current.template_type.charAt(0).toUpperCase() + current.template_type.slice(1)
                        : 'Template';
                    const number = Number.isFinite(current.app_num)
                        ? current.app_num.toString().padStart(2, '0')
                        : '—';
                    badge.textContent = `${current.display_name || current.name} · ${typeLabel} · #${number}`;
                } else {
                    badge.textContent = `${templates.length} template${templates.length === 1 ? '' : 's'}`;
                }
            }
        }

        updateTemplateDetails(meta, content) {
            const nameEl = document.getElementById('template-detail-name');
            const reqEl = document.getElementById('template-detail-reqs');
            const extraEl = document.getElementById('template-detail-extra');
            if (nameEl) nameEl.textContent = meta?.display_name || meta?.name || this.currentTemplate?.display_name || this.currentTemplate?.name || '—';
            if (reqEl) {
                const reqs = meta?.requirements && meta.requirements.length ? meta.requirements.join(', ') : '—';
                reqEl.textContent = reqs;
            }
            if (extraEl) extraEl.textContent = meta?.has_extra_prompt ? 'Supplemental context available' : 'None';
            const badge = document.getElementById('template-detail-badge');
            if (badge) {
                if (meta) {
                    const number = Number.isFinite(meta.app_num) ? meta.app_num.toString().padStart(2, '0') : '—';
                    const kind = meta.template_type && meta.template_type !== 'generic'
                        ? meta.template_type.charAt(0).toUpperCase() + meta.template_type.slice(1)
                        : '';
                    const prefix = kind ? `App ${number} ${kind}` : `App ${number}`;
                    badge.textContent = meta.display_name || prefix;
                } else {
                    badge.textContent = 'Draft template';
                }
            }
            const preview = document.getElementById('template-detail-preview');
            if (preview) preview.textContent = content || 'Template is empty.';
        }


        applyResultsFilters() {
            console.log('[SampleGenerator] applyResultsFilters called');
            this.loadResults();
        }

        async loadResults() {
            console.log('[SampleGenerator] loadResults called');
            try {
                const modelFilter = document.getElementById('results-model-filter')?.value;
                const statusFilter = document.getElementById('results-status-filter')?.value;
                const limit = parseInt(document.getElementById('results-limit')?.value || '', 10) || this.resultsPerPage;
                const params = { limit };
                if (modelFilter) params.model = modelFilter;
                if (statusFilter === 'success') params.success = true;
                if (statusFilter === 'failed') params.success = false;
                console.log('[SampleGenerator] Loading results with params:', params);
                const response = await this.get('/results', params);
                console.log('[SampleGenerator] Results response:', response);
                const results = response.data || response.results || [];
                console.log('[SampleGenerator] Rendering', results.length, 'results');
                this.renderResultsTable(results);
            } catch (error) {
                console.error('Failed to load results:', error);
                this.showError('Failed to load results');
            }
        }

        async loadCurrentGenerations() {
            try {
                const response = await this.get('/status');
                const status = response.data || response.status || {};
                this.renderCurrentGenerations(status.active || []);
            } catch (error) {
                console.error('Failed to load current generations:', error);
                // Silently fail - just show empty state
                this.renderCurrentGenerations([]);
            }
        }

        renderCurrentGenerations(activeGens) {
            const container = document.getElementById('current-generations-list');
            const card = document.getElementById('current-generations-card');
            
            if (!container) return;

            // Hide card if no active generations
            if (!activeGens || activeGens.length === 0) {
                if (card) {
                    card.style.display = 'none';
                }
                container.innerHTML = `
                    <div class="list-group-item text-center text-muted">
                        <p class="mb-0">No active generations</p>
                    </div>
                `;
                return;
            }

            // Show card if there are active generations
            if (card) {
                card.style.display = 'block';
            }

            container.innerHTML = activeGens.map(gen => {
                const progress = gen.progress || 0;
                const statusText = gen.status || 'Processing...';
                const modelName = gen.model || '—';
                const templateName = gen.template || `App #${gen.app_num || '—'}`;
                
                return `
                    <div class="list-group-item">
                        <div class="row align-items-center">
                            <div class="col">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <div>
                                        <strong>${this.escapeHtml(modelName)}</strong> × 
                                        <span class="text-secondary">${this.escapeHtml(templateName)}</span>
                                    </div>
                                    <span class="badge bg-primary">${progress}%</span>
                                </div>
                                <div class="progress progress-sm mb-2">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         role="progressbar" 
                                         style="width: ${progress}%" 
                                         aria-valuenow="${progress}" 
                                         aria-valuemin="0" 
                                         aria-valuemax="100"></div>
                                </div>
                                <div class="small text-muted">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-inline me-1" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0" /><path d="M12 12l0 -3" /><path d="M12 12l2 2" /></svg>
                                    ${this.escapeHtml(statusText)}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        startCurrentGenerationsPolling() {
            // Clear any existing interval
            if (this._currentGensInterval) {
                clearInterval(this._currentGensInterval);
            }

            // Poll every 3 seconds
            this._currentGensInterval = setInterval(() => {
                this.loadCurrentGenerations();
            }, 3000);
        }

        stopCurrentGenerationsPolling() {
            if (this._currentGensInterval) {
                clearInterval(this._currentGensInterval);
                this._currentGensInterval = null;
            }
        }

        renderResultsTable(results) {
            const tbody = document.getElementById('results-table-body');
            if (!tbody) return;

            this.results = Array.isArray(results) ? results : [];

            if (!this.results.length) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No results found for the current filters.</td></tr>';
                return;
            }

            tbody.innerHTML = this.results.map((result) => {
                const resultId = result.result_id || result.id;
                const timestamp = result.timestamp ? this.formatTimestamp(result.timestamp) : '—';
                const appLabel = result.app_name || `App #${result.app_num ?? '—'}`;
                const duration = typeof result.duration === 'number' ? this.formatDuration(result.duration) : '—';
                const statusBadge = result.success ? 'bg-success' : 'bg-danger';
                const statusText = result.success ? 'Success' : 'Failed';
                const errorHint = result.error_message ? ` title="${result.error_message.replace(/"/g, '&quot;')}"` : '';
                const safeResultId = resultId ? resultId.replace(/"/g, '&quot;').replace(/'/g, '&#39;') : null;
                const actionsHtml = result.model && result.app_num
                    ? `<button class="btn btn-outline-primary" type="button" onclick="window.sampleGeneratorAppInstance.viewApplicationDetail('${result.model}', ${result.app_num})" aria-label="View application detail">
                            <i class="fas fa-eye"></i>
                       </button>`
                    : `<button class="btn btn-outline-secondary" type="button" disabled aria-disabled="true" title="Application details unavailable">
                            <i class="fas fa-eye"></i>
                       </button>`;
                return `
                    <tr>
                        <td>${resultId || '—'}</td>
                        <td>${timestamp}</td>
                        <td>${appLabel}</td>
                        <td>${result.model || '—'}</td>
                        <td><span class="badge ${statusBadge}"${errorHint}>${statusText}</span></td>
                        <td>${duration}</td>
                        <td class="text-end">
                            <div class="btn-group btn-group-sm" role="group">
                                ${actionsHtml}
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        showCleanupDialog() {
            const modalEl = document.getElementById('cleanup-modal');
            if (!modalEl) {
                this.showError('Cleanup dialog unavailable in this view.');
                return;
            }
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        async executeCleanup() {
            const ageInput = document.getElementById('cleanup-age');
            const dryRunInput = document.getElementById('cleanup-dryrun');
            const summary = document.getElementById('cleanup-summary');
            const modalEl = document.getElementById('cleanup-modal');
            const modal = modalEl ? bootstrap.Modal.getInstance(modalEl) : null;
            const maxAgeDays = parseInt(ageInput?.value || '30', 10);
            const dryRun = !!dryRunInput?.checked;
            try {
                const response = await this.post('/cleanup', { max_age_days: maxAgeDays, dry_run: dryRun });
                const data = response.data || response;
                if (summary) {
                    summary.textContent = dryRun
                        ? `Dry run: ${data.deleted_ids?.length ?? 0} results would be deleted.`
                        : `Deleted ${data.deleted_count ?? 0} results.`;
                }
                if (!dryRun && modal) modal.hide();
                this.loadResults();
                this.loadRecentGenerations();
            } catch (error) {
                console.error('Cleanup failed:', error);
                this.showError('Cleanup failed');
            }
        }

        async viewResult(resultId) {
            if (!resultId) return;
            this.currentResultId = resultId;
            const modalEl = document.getElementById('result-modal');
            const modal = modalEl ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;
            try {
                const response = await this.get(`/results/${resultId}?include_content=1`);
                const data = response.data || response.result || response;
                document.getElementById('result-modal-label').textContent = `Result ${resultId}`;
                document.getElementById('result-modal-status').textContent = data.success ? 'Success' : 'Failed';
                document.getElementById('result-modal-status').className = `badge ${data.success ? 'bg-success' : 'bg-danger'}`;
                document.getElementById('result-modal-meta').textContent = `${data.model || 'Unknown model'} · ${this.formatDuration(data.duration)} · App #${data.app_num}`;
                document.getElementById('result-modal-content').textContent = data.content || '[No content]';
                modal?.show();
            } catch (error) {
                console.error('Failed to load result:', error);
                this.showError('Failed to load result');
            }
        }

        async copyResultContent() {
            const content = document.getElementById('result-modal-content')?.textContent || '';
            try {
                await navigator.clipboard.writeText(content);
                this.showSuccess('Copied to clipboard');
            } catch (error) {
                console.error('Copy failed:', error);
                this.showError('Failed to copy content');
            }
        }

        viewApplicationDetail(model, app_num) {
            // Convert model name from 'x-ai/grok-code-fast-1' to 'x-ai_grok-code-fast-1' format
            const modelSlug = model.replace(/\//g, '_');
            const url = `/applications/${encodeURIComponent(modelSlug)}/${encodeURIComponent(app_num)}`;
            window.open(url, '_blank');
        }

        async regenerateResult() {
            if (!this.currentResultId) {
                this.showError('Open a result first');
                return;
            }
            try {
                const response = await this.post('/regenerate', { result_id: this.currentResultId });
                const data = response.data || response;
                this.showSuccess(`Regeneration started: ${data.result_id}`);
                this.loadResults();
                this.loadRecentGenerations();
            } catch (error) {
                console.error('Regeneration failed:', error);
                this.showError('Regeneration failed');
            }
        }

        async deleteResult() {
            if (!this.currentResultId) {
                this.showError('Open a result first');
                return;
            }
            if (!confirm(`Delete result ${this.currentResultId}?`)) return;
            try {
                await this.delete(`/results/${this.currentResultId}`);
                this.showSuccess('Result deleted');
                const modalEl = document.getElementById('result-modal');
                bootstrap.Modal.getInstance(modalEl)?.hide();
                this.loadResults();
                this.loadRecentGenerations();
            } catch (error) {
                console.error('Failed to delete result:', error);
                this.showError('Failed to delete result');
            }
        }

        toggleAllTemplates(checked) {
            document.querySelectorAll('.template-checkbox').forEach(cb => {
                cb.checked = checked;
            });
            this.updateTemplateCount();
            this.updateBatchPreview();
        }

        toggleAllModels(checked) {
            document.querySelectorAll('.model-checkbox').forEach(cb => {
                cb.checked = checked;
            });
            this.updateModelCount();
            this.updateBatchPreview();
        }

        updateTemplateCount() {
            const count = document.querySelectorAll('.template-checkbox:checked').length;
            document.getElementById('selected-templates-count').textContent = `${count} selected`;
        }

        updateModelCount() {
            const count = document.querySelectorAll('.model-checkbox:checked').length;
            document.getElementById('selected-models-count').textContent = `${count} selected`;
        }

        updateBatchPreview() {
            const templateCount = document.querySelectorAll('.template-checkbox:checked').length;
            const modelCount = document.querySelectorAll('.model-checkbox:checked').length;
            const totalTasks = templateCount * modelCount;
            
            document.getElementById('start-batch-btn').disabled = totalTasks === 0;
        }

        previewBatch() {
            console.log('Preview batch');
        }

        startBatch() {
            console.log('Start batch');
        }

        confirmBatch() {
            console.log('Confirm batch');
        }

        pauseBatch() {
            console.log('Pause batch');
        }

        cancelBatch() {
            console.log('Cancel batch');
        }

        loadBatchData() {
            console.log('Load batch data');
        }

        loadActiveTasks() {
            console.log('Load active tasks');
        }

        /**
         * Load system status and update management tab
         */
        async loadSystemStatus() {
            try {
                const response = await fetch('/api/sample-gen/status');
                if (!response.ok) throw new Error('Failed to fetch status');
                
                const status = await response.json();
                
                // Update status fields
                document.getElementById('in-flight-count').textContent = status.in_flight_count || 0;
                document.getElementById('available-slots').textContent = status.available_slots || 0;
                document.getElementById('max-concurrent').textContent = status.max_concurrent || 0;
                
                // Update timestamp
                const now = new Date().toLocaleString();
                document.getElementById('system-status-timestamp').innerHTML = 
                    `Last updated: <span class="fst-italic">${now}</span>`;
                
                // Update status badge
                const statusBadge = document.getElementById('system-status');
                if (statusBadge) {
                    if (status.in_flight_count > 0) {
                        statusBadge.className = 'badge bg-warning text-dark';
                        statusBadge.textContent = 'Processing';
                    } else {
                        statusBadge.className = 'badge bg-success';
                        statusBadge.textContent = 'Active';
                    }
                }
            } catch (err) {
                console.error('Failed to load system status:', err);
                const statusBadge = document.getElementById('system-status');
                if (statusBadge) {
                    statusBadge.className = 'badge bg-danger';
                    statusBadge.textContent = 'Error';
                }
            }
        }

        /**
         * Force refresh all data
         */
        forceRefresh() {
            if (this.stubbedMode) {
                this.showInfo('Refresh is unavailable while the sample generator is being reworked.');
                return;
            }
            this.showInfo('Refreshing all data...');
            Promise.all([
                this.loadTemplates(),
                this.loadModels(),
                this.updateStatus(),
                this.loadSystemStatus()
            ]).then(() => {
                this.showSuccess('All data refreshed successfully.');
            }).catch(err => {
                this.showError('Failed to refresh data: ' + err.message);
            });
        }

        /**
         * Clear logs display (not the actual log files)
         */
        clearLogsDisplay() {
            const logEl = document.getElementById('management-log');
            if (logEl) {
                logEl.textContent = 'Log display cleared. Click refresh to reload.';
                this.logEntries = [];
            }
            this.showInfo('Log display cleared.');
        }

        /**
         * Filter logs based on search term
         */
        filterLogs(searchTerm) {
            const logEl = document.getElementById('management-log');
            if (!logEl || !this.logEntries || this.logEntries.length === 0) return;

            const filtered = searchTerm 
                ? this.logEntries.filter(entry => 
                    entry.toLowerCase().includes(searchTerm.toLowerCase()))
                : this.logEntries;

            if (filtered.length === 0) {
                logEl.textContent = `No log entries matching "${searchTerm}".`;
            } else {
                logEl.textContent = filtered.join('\n');
            }
        }

        /**
         * Load system logs (from recent generations or activity)
         */
        async loadSystemLogs() {
            const logEl = document.getElementById('management-log');
            if (!logEl) return;

            try {
                // For now, show recent activity from the results
                const response = await fetch('/api/sample-gen/results?limit=20');
                if (!response.ok) throw new Error('Failed to fetch results');
                
                const data = await response.json();
                const logs = [];
                
                if (data.results && data.results.length > 0) {
                    data.results.forEach(result => {
                        const timestamp = result.timestamp || 'Unknown time';
                        const model = result.model || 'Unknown model';
                        const app = result.app_name || result.app_num || 'Unknown app';
                        const status = result.success ? '✓ SUCCESS' : '✗ FAILED';
                        const duration = result.duration ? `(${result.duration}s)` : '';
                        
                        logs.push(`[${timestamp}] ${status} ${duration} - ${model} → ${app}`);
                    });
                    
                    this.logEntries = logs;
                    logEl.textContent = logs.join('\n');
                } else {
                    logEl.textContent = 'No recent activity found.';
                    this.logEntries = [];
                }
            } catch (err) {
                console.error('Failed to load logs:', err);
                logEl.textContent = `Error loading logs: ${err.message}`;
                this.logEntries = [];
            }
        }

        // ---------------------------------------------------------------
        // Scaffolding methods
        // ---------------------------------------------------------------
        async scaffoldFetchStatus() {
            try {
                const res = await this.getScaffold('/status');
                this.scaffoldLog(`Scaffolding service ready (apps/model=${res.data.apps_per_model}).`);
            } catch (e) {
                this.scaffoldLog('Failed to reach scaffolding service');
            }
        }

        /**
         * Clear any stored model selections from localStorage
         */
        clearScaffoldingModelSelection() {
            localStorage.removeItem('selected_scaffolding_model');
            localStorage.removeItem('selected_scaffolding_models');
        }

        /**
         * Check if a model was selected from the models page and autofill the scaffolding input
         */
        checkScaffoldingModelSelection() {
            try {
                // Check for multiple models (new format)
                const selectedModelsJson = localStorage.getItem('selected_scaffolding_models');
                if (selectedModelsJson) {
                    const selectedModels = JSON.parse(selectedModelsJson);
                    if (Array.isArray(selectedModels) && selectedModels.length > 0) {
                        const input = document.getElementById('scaffold-models-input');
                        if (input) {
                            // Get current value
                            const currentValue = input.value.trim();
                            
                            // If empty, just set the models as comma-separated list
                            if (!currentValue) {
                                input.value = selectedModels.join(',');
                            } else {
                                // If there's existing content, append the models to the list
                                let existingModels = [];
                                if (currentValue.includes('models=')) {
                                    // Extract from URL
                                    const match = currentValue.match(/models=([^&]+)/);
                                    if (match) {
                                        existingModels = decodeURIComponent(match[1]).split(',').map(m => m.trim());
                                    }
                                } else {
                                    // Assume it's a comma-separated list
                                    existingModels = currentValue.split(',').map(m => m.trim());
                                }
                                
                                // Add the new models if they're not already in the list
                                selectedModels.forEach(model => {
                                    if (!existingModels.includes(model)) {
                                        existingModels.push(model);
                                    }
                                });
                                input.value = existingModels.join(',');
                            }
                            
                            // Highlight the input briefly to draw attention
                            input.classList.add('border-success', 'border-2');
                            setTimeout(() => {
                                input.classList.remove('border-success', 'border-2');
                            }, 2000);
                            
                            // Show a feedback message
                            const count = selectedModels.length;
                            this.scaffoldFeedback(`${count} model${count > 1 ? 's' : ''} added. Click "Parse Models" to continue.`, false);
                        }
                        
                        // Clear the localStorage item after using it
                        localStorage.removeItem('selected_scaffolding_models');
                        return;
                    }
                }
                
                // Fallback: check for single model (old format for backwards compatibility)
                const selectedModel = localStorage.getItem('selected_scaffolding_model');
                if (selectedModel) {
                    const input = document.getElementById('scaffold-models-input');
                    if (input) {
                        const currentValue = input.value.trim();
                        
                        if (!currentValue) {
                            input.value = selectedModel;
                        } else {
                            let existingModels = [];
                            if (currentValue.includes('models=')) {
                                const match = currentValue.match(/models=([^&]+)/);
                                if (match) {
                                    existingModels = decodeURIComponent(match[1]).split(',').map(m => m.trim());
                                }
                            } else {
                                existingModels = currentValue.split(',').map(m => m.trim());
                            }
                            
                            if (!existingModels.includes(selectedModel)) {
                                existingModels.push(selectedModel);
                                input.value = existingModels.join(',');
                            }
                        }
                        
                        input.classList.add('border-success', 'border-2');
                        setTimeout(() => {
                            input.classList.remove('border-success', 'border-2');
                        }, 2000);
                        
                        this.scaffoldFeedback(`Model "${selectedModel}" added. Click "Parse Models" to continue.`, false);
                    }
                    
                    localStorage.removeItem('selected_scaffolding_model');
                }
            } catch (e) {
                console.warn('Could not check scaffolding model selection:', e);
            }
        }

        async scaffoldParseModels() {
            const input = document.getElementById('scaffold-models-input')?.value || '';
            const apm = parseInt(document.getElementById('scaffold-apps-per-model')?.value) || undefined;
            if (!input.trim()) {
                this.scaffoldFeedback('Please enter a URL or model list.', true);
                return;
            }
            try {
                const res = await this.postScaffold('/models/parse', { input, apps_per_model: apm });
                if (!res.success) throw new Error(res.error || 'Parse failed');
                this._scaffoldModels = res.data.models;
                this._scaffoldPreview = res.data.preview;
                this.renderScaffoldPreview();
                this.scaffoldFeedback(`Parsed ${res.data.models.length} models.`);
            } catch (e) {
                console.error(e);
                this.scaffoldFeedback(e.message || 'Parse error', true);
            }
        }

        async scaffoldValidateTemplates() {
            try {
                const res = await this.getScaffold('/templates/validate');
                if (res.data.ok) {
                    this.scaffoldFeedback('All required templates present.');
                } else {
                    this.scaffoldFeedback(`Missing templates: ${res.data.missing.join(', ')}`, true);
                }
            } catch (e) {
                this.scaffoldFeedback('Template validation failed', true);
            }
        }

        async scaffoldGenerate(dryRun = true) {
            if (!this._scaffoldModels || this._scaffoldModels.length === 0) {
                this.scaffoldFeedback('Parse models first.', true);
                return;
            }
            const apm = parseInt(document.getElementById('scaffold-apps-per-model')?.value) || undefined;
            const compose = true; // always generate docker-compose.yml per app (toggle removed)
            try {
                const res = await this.postScaffold('/generate', { models: this._scaffoldModels, dry_run: dryRun, apps_per_model: apm, compose });
                if (!res.success) throw new Error(res.error || 'Generation failed');
                if (res.data.generated) {
                    this.scaffoldLog(`Generated model scaffolds. Paths: ${res.data.output_paths.join('; ')}`);
                } else {
                    this.scaffoldLog('Dry run complete. No files written.');
                }
                const meta = [];
                if (res.data.apps_created !== undefined) meta.push(`apps_created=${res.data.apps_created}`);
                if (res.data.missing_templates?.length) meta.push(`missing_templates=${res.data.missing_templates.length}`);
                if (res.data.errors?.length) meta.push(`errors=${res.data.errors.length}`);
                this._scaffoldLastResult = res.data;
                this.renderScaffoldMetadata();
                this.scaffoldFeedback(`Success: ${dryRun ? 'Dry run' : 'Generated'} ${res.data.total_apps} apps (${meta.join(', ')}).`);
            } catch (e) {
                this.scaffoldFeedback(e.message || 'Generation error', true);
            }
        }

        renderScaffoldPreview() {
            const tableBody = document.getElementById('scaffold-models-table');
            if (!tableBody) return;
            
            // Populate stats cards
            const totalModels = this._scaffoldPreview.models.length;
            const totalApps = this._scaffoldPreview.total_apps;
            const totalFolders = totalApps * 2; // frontend + backend per app
            const totalFiles = totalApps * 3; // approximate: docker-compose + 2 base files per app
            
            this._setText('scaffold-total-models', totalModels);
            this._setText('scaffold-total-apps', totalApps);
            this._setText('scaffold-total-folders', totalFolders);
            this._setText('scaffold-total-files', totalFiles);
            
            // Populate models table
            tableBody.innerHTML = this._scaffoldPreview.models.map(m => {
                const appsCount = m.apps ? m.apps.length : 0;
                const portRange = `${m.port_range[0]} - ${m.port_range[1]}`;
                const sizeEstimate = `~${appsCount * 2}MB`; // rough estimate
                return `
                <tr>
                  <td>${m.name}</td>
                  <td class="text-center">${appsCount}</td>
                  <td>${portRange}</td>
                  <td class="text-end">${sizeEstimate}</td>
                </tr>`;
            }).join('');
            
            // Update config summary
            const summary = this._scaffoldPreview.config_summary;
            this._setText('scaffold-config-summary', `Apps/model: ${summary.apps_per_model}, Ports/app: ${summary.ports_per_app}`);
            
            // Enable buttons
            document.getElementById('scaffold-dryrun-btn').disabled = false;
            document.getElementById('scaffold-generate-btn').disabled = false;
        }

        renderScaffoldMetadata() {
            const metaEl = document.getElementById('scaffold-metadata');
            if (!metaEl || !this._scaffoldLastResult) return;
            const r = this._scaffoldLastResult;
            const lines = [];
            if (r.missing_templates?.length) {
                lines.push(`<span class='text-warning'>Missing templates:</span> ${r.missing_templates.join(', ')}`);
            }
            if (r.errors?.length) {
                lines.push(`<span class='text-danger'>Errors:</span> ${r.errors.join('; ')}`);
            }
            if (!lines.length) {
                lines.push('<span class="text-success">No template issues or generation errors.</span>');
            }
            metaEl.innerHTML = lines.join('<br>');
        }

        scaffoldFeedback(message, isError = false) {
            const el = document.getElementById('scaffold-parse-feedback');
            if (el) {
                el.innerHTML = `<span class='${isError ? 'text-danger' : 'text-success'}'>${message}</span>`;
            }
            this.scaffoldLog(message);
        }

        scaffoldLog(message) {
            const logEl = document.getElementById('scaffold-log');
            if (logEl) {
                const ts = new Date().toLocaleTimeString();
                logEl.textContent += `\n[${ts}] ${message}`;
                logEl.scrollTop = logEl.scrollHeight;
            }
        }

        collectModelSettings() {
            const overrides = {};
            document.querySelectorAll('[data-sg-setting]').forEach((input) => {
                if (!(input instanceof HTMLInputElement)) return;
                const key = input.dataset.sgSetting;
                if (!key) return;
                const raw = input.value.trim();
                if (!raw) return;
                const type = input.dataset.sgType || 'float';
                let parsedValue;
                if (type === 'int') {
                    parsedValue = parseInt(raw, 10);
                } else {
                    parsedValue = parseFloat(raw);
                }
                if (!Number.isFinite(parsedValue)) {
                    return;
                }
                overrides[key] = parsedValue;
            });
            return overrides;
        }

        updateModelSettingsSummary(explicitOverrides) {
            const summaryEl = document.getElementById('sg-model-settings-active');
            if (!summaryEl) return;
            const overrides = explicitOverrides ?? this.collectModelSettings();
            const keys = Object.keys(overrides ?? {});
            if (!keys.length) {
                summaryEl.textContent = 'Defaults in use';
                summaryEl.classList.add('text-muted');
                return;
            }
            const summaryParts = keys.map((key) => `${key.replace(/_/g, ' ')}=${overrides[key]}`);
            summaryEl.textContent = `Overrides active: ${summaryParts.join(', ')}`;
            summaryEl.classList.remove('text-muted');
        }

        resetModelSettings() {
            document.querySelectorAll('[data-sg-setting]').forEach((input) => {
                if (input instanceof HTMLInputElement) {
                    input.value = '';
                }
            });
            this.updateModelSettingsSummary({});
        }

        async getScaffold(endpoint) { return this.apiCallScaffold('GET', endpoint); }
        async postScaffold(endpoint, data) { return this.apiCallScaffold('POST', endpoint, data); }
        async apiCallScaffold(method, endpoint, data) {
            const url = `/api/app-scaffold${endpoint}`;
            const options = { method, headers: { 'Content-Type': 'application/json' } };
            if (data) options.body = JSON.stringify(data);
            const res = await fetch(url, options);
            return res.json();
        }
    }

    // Expose the class to the global scope
    window.SampleGeneratorApp = SampleGeneratorApp;
})();

// Internal helper methods (attached via prototype to keep class body readable)
SampleGeneratorApp.prototype._setText = function(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
};

// Ensure endpoint begins with a single leading slash and is not already fully qualified.
SampleGeneratorApp.prototype._normalizeEndpoint = function(endpoint) {
    if (!endpoint) return '';
    // Strip any leading apiBase fragment accidentally passed in
    const cleaned = endpoint.replace(/^https?:\/\/[^/]+/,'')
                            .replace(this.apiBase, '')
                            .replace(/^\/+/, '/');
    return cleaned;
};

// Enable / disable Generate button based on selections
SampleGeneratorApp.prototype.updateGenerateButtonState = function() {
    const tmpl = document.getElementById('template-select')?.value;
    const model = document.getElementById('model-select')?.value;
    const btn = document.getElementById('generate-btn');
    if (btn) {
        btn.disabled = !(tmpl && model);
    }
};

function initializeSampleGeneratorApp() {
    const root = document.getElementById('sample-generator');
    if (!root) {
        console.warn('[SampleGenerator] Root element #sample-generator not found');
        return;
    }
    if (root?.hasAttribute('data-simple-sample-gen')) {
        console.log('[SampleGenerator] Simple mode - skipping JS initialization');
        return;
    }
    if (window.sampleGeneratorAppInstance) {
        console.log('[SampleGenerator] Re-initializing existing instance');
        window.sampleGeneratorAppInstance.init();
    } else {
        console.log('[SampleGenerator] Creating new instance');
        window.sampleGeneratorAppInstance = new window.SampleGeneratorApp();
    }
}

// Handle both initial page load and HTMX content swaps
document.addEventListener('DOMContentLoaded', initializeSampleGeneratorApp);
document.body.addEventListener('htmx:load', initializeSampleGeneratorApp);