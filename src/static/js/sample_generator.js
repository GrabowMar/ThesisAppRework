(function() {
    // If the class is already defined, we don't need to do anything.
    // This prevents "Identifier has already been declared" errors with HTMX.
    if (window.SampleGeneratorApp) {
        return;
    }

    /**
     * Sample Generator Frontend JavaScript
     * Provides interactive functionality for the sample generator web interface
     */

    class SampleGeneratorApp {
        constructor() {
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
            
            // Initialize the application
            this.init();
        }

        /**
         * Initialize the application
         */
        init() {
            this.bindEvents();
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
            });

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

            // Scaffolding tab events
            this.bindScaffoldingEvents();

            // Global refresh
            document.getElementById('global-refresh-btn')?.addEventListener('click', () => {
                this.refreshAll();
            });
        }

        /**
         * Bind generation tab events
         */
        bindGenerationEvents() {
            if (this._generationEventsBound) return; // idempotent
            this._generationEventsBound = true;
            // Template selection change
            document.getElementById('template-select')?.addEventListener('change', (e) => {
                if (e.target.value) {
                    this.loadTemplateContent(e.target.value);
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

            // Generate button
            document.getElementById('generate-btn')?.addEventListener('click', () => {
                this.generateSample();
            });

            // Model selection change -> update enable/disable state
            document.getElementById('model-select')?.addEventListener('change', () => {
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
            if (this._resultsEventsBound) return; // idempotent
            this._resultsEventsBound = true;
            // Apply filters
            document.getElementById('apply-filters-btn')?.addEventListener('click', () => {
                this.applyResultsFilters();
            });

            // Refresh results
            document.getElementById('refresh-results-btn')?.addEventListener('click', () => {
                this.loadResults();
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
            document.getElementById('export-data-btn')?.addEventListener('click', () => {
                this.exportData();
            });

            document.getElementById('cleanup-orphaned-btn')?.addEventListener('click', () => {
                this.cleanupOrphaned();
            });

            document.getElementById('optimize-database-btn')?.addEventListener('click', () => {
                this.optimizeDatabase();
            });

            document.getElementById('validate-templates-btn')?.addEventListener('click', () => {
                this.validateTemplates();
            });

            // Advanced operations
            document.getElementById('execute-bulk-cleanup-btn')?.addEventListener('click', () => {
                this.executeBulkCleanup();
            });

            document.getElementById('download-export-btn')?.addEventListener('click', () => {
                this.downloadExport();
            });

            document.getElementById('upload-templates-btn')?.addEventListener('click', () => {
                this.uploadTemplates();
            });

            // Monitoring controls
            document.getElementById('auto-refresh-enabled')?.addEventListener('change', (e) => {
                this.toggleAutoRefresh(e.target.checked);
            });

            document.getElementById('force-refresh-btn')?.addEventListener('click', () => {
                this.forceRefresh();
            });

            document.getElementById('clear-cache-btn')?.addEventListener('click', () => {
                this.clearCache();
            });

            // Log controls
            document.getElementById('refresh-logs-btn')?.addEventListener('click', () => {
                this.loadSystemLogs();
            });

            document.getElementById('clear-logs-btn')?.addEventListener('click', () => {
                this.clearLogs();
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
        }

        /**
         * Load initial data when the application starts
         */
        async loadInitialData() {
            try {
                await Promise.all([
                    this.loadTemplates(),
                    this.loadModels(),
                    this.loadRecentGenerations()
                ]);
            } catch (error) {
                console.error('Failed to load initial data:', error);
                this.showError('Failed to load initial data');
            }
        }

        /**
         * Handle tab changes
         */
        onTabChanged(tabId) {
            switch (tabId) {
                case 'generation-tab':
                    break;
                case 'templates-tab':
                    this.loadTemplatesList();
                    break;
                case 'results-tab':
                    this.loadResults();
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
                this.templates = Array.isArray(rawTemplates) ? rawTemplates : [];
                this.updateTemplateSelect();
                this.updateBatchTemplates();
            } catch (error) {
                console.error('Failed to load templates:', error);
                this.showError('Failed to load templates');
            }
        }

        /**
         * Load models from API
         */
        async loadModels() {
            try {
                const response = await this.get('/models');
                let rawModels = response.data || response.models || [];
                this.models = Array.isArray(rawModels) ? rawModels.map(m => {
                    // Normalize simple list of strings to objects if backend returns just list
                    if (typeof m === 'string') {
                        return { name: m, provider: (m.split('/')[0] || 'unknown') };
                    }
                    return m;
                }) : [];
                this.updateModelSelect();
                this.updateBatchModels();
            } catch (error) {
                console.error('Failed to load models:', error);
                this.showError('Failed to load models');
            }
        }

        /**
         * Update template select dropdown
         */
        updateTemplateSelect() {
            const select = document.getElementById('template-select');
            if (!select) return;

            select.innerHTML = '<option value="">Select a template...</option>';
            this.templates.forEach(template => {
                const option = document.createElement('option');
                option.value = template.name;
                const badge = template.has_extra_prompt ? ' *' : '';
                option.textContent = `${template.name}${badge}`;
                if (template.has_extra_prompt) option.title = 'Has extra prompt context';
                select.appendChild(option);
            });
        }

        /**
         * Update model select dropdown
         */
        updateModelSelect() {
            const select = document.getElementById('model-select');
            if (!select) return;

            select.innerHTML = '<option value="">Select a model...</option>';
            this.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = `${model.name} (${model.provider || 'Unknown'})`;
                select.appendChild(option);
            });
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
            this.templates.forEach(template => {
                const col = document.createElement('div');
                col.className = 'col-md-6 mb-2';
                col.innerHTML = `
                    <div class="form-check">
                        <input class="form-check-input template-checkbox" type="checkbox" value="${template.name}" id="template-${template.name}">
                        <label class="form-check-label" for="template-${template.name}">
                            ${template.name} ${template.has_extra_prompt ? '<span class="badge bg-info ms-1">ctx</span>' : ''}
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
                const directory = 'src/misc/app_templates';
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
                            ${model.name}
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
         * Generate a sample
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

            try {
                this.showLoading('Generating sample...');
                
                const response = await this.post('/generate', {
                    template_name: templateName,
                    model_name: modelName,
                    max_concurrent: maxConcurrent,
                    request_timeout: timeout
                });

                this.hideLoading();
                
                if (response.success) {
                    this.showSuccess('Sample generated successfully!');
                    this.loadRecentGenerations();
                } else {
                    this.showError(response.error || 'Generation failed');
                }
            } catch (error) {
                this.hideLoading();
                this.showError('Failed to generate sample');
            }
        }

        /**
         * Load recent generations
         */
        async loadRecentGenerations() {
            try {
                const response = await this.get('/results', { limit: 10, order: 'desc' });
                this.updateRecentGenerationsTable(response.results || []);
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
                    <td>${result.id}</td>
                    <td>${result.template_name}</td>
                    <td>${result.model_name}</td>
                    <td>
                        <span class="badge ${result.success ? 'bg-success' : 'bg-danger'}">
                            ${result.success ? 'Success' : 'Failed'}
                        </span>
                    </td>
                    <td>${this.formatDuration(result.generation_time)}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="app.viewResult(${result.id})">
                            View
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        /**
         * Utility methods
         */
        formatDuration(seconds) {
            if (!seconds) return '-';
            if (seconds < 60) return `${seconds.toFixed(1)}s`;
            const minutes = Math.floor(seconds / 60);
            const secs = seconds % 60;
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

        /**
         * Update status dashboard
         */
        async updateStatus() {
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
            await this.loadInitialData();
            await this.updateStatus();
            this.showSuccess('Data refreshed');
        }

        // Placeholder methods for additional functionality
        // These would be implemented based on specific requirements

        loadTemplateContent(templateName) {
            console.log('Loading template content:', templateName);
        }

        showTemplateLoader() {
            console.log('Show template loader dialog');
        }

        showTemplateEditor() {
            console.log('Show template editor');
        }

        filterTemplates(searchTerm) {
            console.log('Filter templates:', searchTerm);
        }

        saveTemplate() {
            console.log('Save template');
        }

        deleteTemplate() {
            console.log('Delete template');
        }

        loadTemplatesList() {
            console.log('Load templates list');
        }

        applyResultsFilters() {
            console.log('Apply results filters');
        }

        loadResults() {
            console.log('Load results');
        }

        showCleanupDialog() {
            const modal = new bootstrap.Modal(document.getElementById('cleanup-modal'));
            modal.show();
        }

        executeCleanup() {
            console.log('Execute cleanup');
        }

        viewResult(resultId) {
            console.log('View result:', resultId);
        }

        copyResultContent() {
            console.log('Copy result content');
        }

        regenerateResult() {
            console.log('Regenerate result');
        }

        deleteResult() {
            console.log('Delete result');
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

        loadSystemStatus() {
            console.log('Load system status');
        }

        exportData() {
            console.log('Export data');
        }

        cleanupOrphaned() {
            console.log('Cleanup orphaned');
        }

        optimizeDatabase() {
            console.log('Optimize database');
        }

        validateTemplates() {
            console.log('Validate templates');
        }

        executeBulkCleanup() {
            console.log('Execute bulk cleanup');
        }

        downloadExport() {
            console.log('Download export');
        }

        uploadTemplates() {
            console.log('Upload templates');
        }

        toggleAutoRefresh(enabled) {
            console.log('Toggle auto refresh:', enabled);
            if (enabled) {
                const interval = parseInt(document.getElementById('monitor-interval')?.value) || 10;
                this.monitoringInterval = setInterval(() => {
                    this.updateStatus();
                }, interval * 1000);
            } else {
                if (this.monitoringInterval) {
                    clearInterval(this.monitoringInterval);
                    this.monitoringInterval = null;
                }
            }
        }

        forceRefresh() {
            this.refreshAll();
        }

        clearCache() {
            console.log('Clear cache');
        }

        loadSystemLogs() {
            console.log('Load system logs');
        }

        clearLogs() {
            console.log('Clear logs');
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
            const compose = !!document.getElementById('scaffold-compose-toggle')?.checked;
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
            const previewDiv = document.getElementById('scaffold-preview');
            const placeholder = document.getElementById('scaffold-preview-placeholder');
            const tableBody = document.getElementById('scaffold-models-table');
            if (!previewDiv || !tableBody) return;
            placeholder.style.display = 'none';
            previewDiv.style.display = 'block';
            tableBody.innerHTML = this._scaffoldPreview.models.map(m => {
                const sampleApps = (m.apps || []).slice(0,3).map(a => `#${a.number}:${a.backend}/${a.frontend}`).join(' ');
                return `
                <tr>
                  <td>${m.name}</td>
                  <td>${m.index}</td>
                  <td>${m.port_range[0]} - ${m.port_range[1]}</td>
                  <td class='small'>${sampleApps || '-'}</td>
                </tr>`;
            }).join('');
            document.getElementById('scaffold-total-apps').textContent = this._scaffoldPreview.total_apps;
            const summary = this._scaffoldPreview.config_summary;
            document.getElementById('scaffold-config-summary').textContent = `Apps/model: ${summary.apps_per_model}, Ports/app: ${summary.ports_per_app}`;
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
    // If an instance already exists, it means HTMX has swapped in new content.
    // We need to re-run init() to bind events to the new elements.
    if (window.sampleGeneratorAppInstance) {
        window.sampleGeneratorAppInstance.init();
    } else {
        window.sampleGeneratorAppInstance = new window.SampleGeneratorApp();
    }
}

// Handle both initial page load and HTMX content swaps
document.addEventListener('DOMContentLoaded', initializeSampleGeneratorApp);
document.body.addEventListener('htmx:load', initializeSampleGeneratorApp);