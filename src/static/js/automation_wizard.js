/**
 * Automation Wizard - Pipeline State Machine & UI Controller
 * Manages the multi-step wizard for automated generation → analysis workflow
 */

// ============================================================================
// State Management
// ============================================================================

// Guard against duplicate declarations (can happen with browser caching/hot reload)
if (typeof window.AutomationWizard !== 'undefined') {
    console.warn('AutomationWizard already defined, skipping re-initialization');
} else {

window.AutomationWizard = {
    // Pipeline configuration state
    config: {
        generationMode: 'generate', // 'generate' or 'existing'
        templates: [],
        models: [],
        existingApps: [], // for existing apps mode
        generationOptions: {
            parallel: true,  // Default to parallel for efficiency
            maxConcurrentTasks: 2  // Default 2 concurrent (avoid rate limits)
        },
        analysisTools: [],
        analysisOptions: {
            parallel: true,  // Default to parallel for batch efficiency
            maxConcurrentTasks: 3,  // Default parallelism limit
            autoStartContainers: true,  // Auto-start containers by default
            stopAfterAnalysis: true  // Clean up containers after analysis
        },
        pipelineName: ''
    },
    
    // Runtime state
    state: {
        currentStep: 1,
        pipelineId: null,
        status: 'idle', // idle, running, paused, completed, failed, cancelled
        startTime: null,
        jobs: [],
        completedJobs: [],
        currentJob: null,
        pollInterval: null,
        elapsedInterval: null
    },
    
    // API endpoints
    endpoints: {
        startPipeline: '/automation/api/pipeline/start',
        pausePipeline: (id) => `/automation/api/pipeline/${id}/cancel`, // No pause - use cancel
        cancelPipeline: (id) => `/automation/api/pipeline/${id}/cancel`,
        getStatus: (id) => `/automation/api/pipeline/${id}/status`,
        getTools: '/automation/api/tools',
        fragmentStage: (stage) => `/automation/fragments/stage/${stage}`,
        fragmentStatus: '/automation/fragments/status'
    }
};

// ============================================================================
// Wizard Navigation
// ============================================================================

/**
 * Navigate to a specific step in the wizard
 */
function goToStep(step) {
    const wizard = AutomationWizard;
    const totalSteps = 4; // 3 config + 1 execution
    
    // Validate step bounds
    if (step < 1 || step > totalSteps) return;
    
    // Don't allow navigation during execution (step 5)
    if (wizard.state.status === 'running' && step < 5) {
        showNotification('Cannot navigate while pipeline is running', 'warning');
        return;
    }
    
    // Collect config when leaving a step (before moving)
    if (wizard.state.currentStep && wizard.state.currentStep !== step) {
        collectStepConfig(wizard.state.currentStep);
    }
    
    // Update state
    wizard.state.currentStep = step;
    
    // Update panels visibility using 'active' class (matching CSS)
    document.querySelectorAll('.wizard-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    const currentPanel = document.querySelector(`[data-panel="${step}"]`);
    if (currentPanel) {
        currentPanel.classList.add('active');
    }
    
    // Update sidebar stepper
    updateStepper(step);
    
    // Update navigation buttons
    updateNavigationButtons();
    
    // Update progress bar
    updateWizardProgress(step);
    
    // Special handling for review step
    if (step === 3) updateReviewSummary();
    
    // Special handling for analysis step - trigger HTMX tool loading
    if (step === 2) {
        // Trigger HTMX to load tools when Step 2 becomes visible
        // The intersect trigger doesn't work for display:none -> visible transitions
        setTimeout(() => {
            const toolContainers = ['static-tools-list', 'dynamic-tools-list', 'performance-tools-list', 'ai-tools-list'];
            toolContainers.forEach(id => {
                const el = document.getElementById(id);
                // Only trigger if still showing spinner (not yet loaded)
                if (el && el.querySelector('.spinner-border')) {
                    console.log('[AutomationWizard] Triggering HTMX load for:', id);
                    htmx.trigger(el, 'loadTools');
                }
            });
        }, 50); // Small delay to ensure panel is visible
    }
    
    // Special handling for execution step
    if (step === 4) {
        // Hide stepper, show metrics
        toggleExecutionMode(true);
    } else {
        toggleExecutionMode(false);
    }
}

/**
 * Move to next step
 */
function nextStep() {
    const wizard = window.AutomationWizard;
    const current = wizard.state.currentStep;
    
    // Collect config from current step BEFORE validating
    collectStepConfig(current);
    
    // Validate current step before proceeding
    if (!validateStep(current)) return;
    
    goToStep(current + 1);
}

/**
 * Move to previous step
 */
function previousStep() {
    const wizard = AutomationWizard;
    if (wizard.state.currentStep > 1) {
        goToStep(wizard.state.currentStep - 1);
    }
}

// Alias for backward compatibility
function prevStep() {
    previousStep();
}

/**
 * Update the stepper sidebar UI
 */
function updateStepper(activeStep) {
    document.querySelectorAll('.step-item').forEach(item => {
        const stepNum = parseInt(item.dataset.step, 10);
        item.classList.remove('active', 'completed');
        
        if (stepNum < activeStep) {
            item.classList.add('completed');
        } else if (stepNum === activeStep) {
            item.classList.add('active');
        }
    });
    
    // Update current step display
    const currentStepEl = document.getElementById('current-step');
    if (currentStepEl) {
        currentStepEl.textContent = activeStep;
    }
}

/**
 * Update navigation buttons based on current step
 */
function updateNavigationButtons() {
    const wizard = AutomationWizard;
    const step = wizard.state.currentStep;
    
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const startBtn = document.getElementById('start-btn');
    const startBtnLoading = document.getElementById('start-btn-loading');
    
    // Previous button - disabled on step 1
    if (prevBtn) {
        prevBtn.disabled = (step <= 1);
    }
    
    // Show/hide next vs start button based on step
    if (step < 3) {
        // Steps 1-2: show Next button
        if (nextBtn) nextBtn.classList.remove('d-none');
        if (startBtn) startBtn.classList.add('d-none');
        if (startBtnLoading) startBtnLoading.classList.add('d-none');
    } else if (step === 3) {
        // Step 3 (Review): show Start Pipeline button
        if (nextBtn) nextBtn.classList.add('d-none');
        if (startBtn) startBtn.classList.remove('d-none');
        if (startBtnLoading) startBtnLoading.classList.add('d-none');
    } else {
        // Step 4 (Execution): hide navigation
        if (nextBtn) nextBtn.classList.add('d-none');
        if (startBtn) startBtn.classList.add('d-none');
    }
}

/**
 * Update wizard progress bar
 */
function updateWizardProgress(step) {
    const totalConfigSteps = 3;
    const progress = Math.round((Math.min(step, totalConfigSteps) / totalConfigSteps) * 100);
    
    const progressBar = document.getElementById('automation-wizard-progress-bar');
    const progressPercentage = document.getElementById('progress-percentage');
    
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
    }
    if (progressPercentage) {
        progressPercentage.textContent = `${progress}%`;
    }
}

/**
 * Toggle between config mode and execution mode UI
 */
function toggleExecutionMode(executing) {
    const stepperEl = document.getElementById('wizard-stepper');
    const metricsEl = document.getElementById('status-metrics');
    
    if (stepperEl) stepperEl.classList.toggle('d-none', executing);
    if (metricsEl) metricsEl.classList.toggle('d-none', !executing);
}

// ============================================================================
// Step Validation & Config Collection
// ============================================================================

/**
 * Validate a specific step's configuration
 */
function validateStep(step) {
    const wizard = AutomationWizard;
    
    // Helper to highlight an element that needs attention
    const highlightElement = (selector, needsAttention) => {
        const el = document.querySelector(selector);
        if (el) {
            if (needsAttention) {
                el.classList.add('border-warning');
                // Remove highlight after 3 seconds
                setTimeout(() => el.classList.remove('border-warning'), 3000);
            } else {
                el.classList.remove('border-warning');
            }
        }
    };
    
    switch(step) {
        case 1: // Generation
            if (wizard.config.generationMode === 'existing') {
                // Existing apps mode - need at least one app selected
                if (!wizard.config.existingApps || wizard.config.existingApps.length === 0) {
                    showNotification('Please select at least one existing application', 'warning');
                    highlightElement('#existing-apps-section .card', true);
                    return false;
                }
            } else {
                // Generate new mode - need templates and models
                if (wizard.config.templates.length === 0) {
                    showNotification('Please select at least one template', 'warning');
                    highlightElement('#template-selection-list', true);
                    return false;
                }
                if (wizard.config.models.length === 0) {
                    showNotification('Please select at least one model', 'warning');
                    highlightElement('#model-selection-list', true);
                    return false;
                }
            }
            return true;
            
        case 2: // Analysis
            if (wizard.config.analysisTools.length === 0) {
                showNotification('Please select at least one analysis tool', 'warning');
                highlightElement('#tools-grid', true);
                return false;
            }
            return true;
            
        case 3: // Review
            return true;
            
        default:
            return true;
    }
}

/**
 * Collect configuration from a specific step
 */
function collectStepConfig(step) {
    const wizard = AutomationWizard;
    
    switch(step) {
        case 1: // Generation
            collectGenerationConfig();
            break;
            
        case 2: // Analysis
            collectAnalysisConfig();
            break;
            
        case 3: // Review
            wizard.config.pipelineName = document.getElementById('pipeline-name')?.value || '';
            break;
    }
}

/**
 * Collect generation step configuration
 */
function collectGenerationConfig() {
    const wizard = AutomationWizard;
    
    // Get generation mode
    const modeInput = document.querySelector('input[name="generation_mode"]:checked');
    if (modeInput) {
        wizard.config.generationMode = modeInput.value;
    }
    
    // Get selected templates
    wizard.config.templates = Array.from(
        document.querySelectorAll('input[name="template"]:checked')
    ).map(el => el.value);
    
    // Get selected models
    wizard.config.models = Array.from(
        document.querySelectorAll('input[name="model"]:checked')
    ).map(el => el.value);
    
    // Get existing apps (if in existing mode)
    wizard.config.existingApps = Array.from(
        document.querySelectorAll('input[name="existing_app"]:checked')
    ).map(el => el.value);
    
    // Get generation options (parallel execution settings)
    const genParallelEnabled = document.getElementById('generation-parallel')?.checked ?? true;
    const genMaxConcurrent = parseInt(document.getElementById('generation-max-concurrent')?.value || '2', 10);
    
    wizard.config.generationOptions = {
        parallel: genParallelEnabled,
        maxConcurrentTasks: genParallelEnabled ? Math.min(Math.max(genMaxConcurrent, 1), 4) : 1  // Clamp between 1-4
    };
    
    updateSelectionSummary();
}

/**
 * Collect analysis step configuration
 */
function collectAnalysisConfig() {
    const wizard = AutomationWizard;
    
    // Get selected tools
    wizard.config.analysisTools = Array.from(
        document.querySelectorAll('input[name="analysis_tool"]:checked')
    ).map(el => el.value);
    
    // Get analysis options
    const parallelEnabled = document.getElementById('analysis-parallel')?.checked ?? true;
    const maxConcurrent = parseInt(document.getElementById('analysis-max-concurrent')?.value || '3', 10);
    
    wizard.config.analysisOptions = {
        parallel: parallelEnabled,
        maxConcurrentTasks: parallelEnabled ? Math.min(Math.max(maxConcurrent, 1), 8) : 1,  // Clamp between 1-8
        autoStartContainers: document.getElementById('analysis-container-auto')?.checked ?? true,  // Default true for pipelines
        stopAfterAnalysis: document.getElementById('analysis-container-stop')?.checked ?? true  // Default cleanup
    };
}



// ============================================================================
// UI Updates
// ============================================================================

/**
 * Update the selection summary card (step 1)
 */
function updateSelectionSummary() {
    const wizard = AutomationWizard;
    const templates = wizard.config.templates.length;
    const models = wizard.config.models.length;
    const total = templates * models;
    
    // Update both old and new ID patterns for compatibility
    const templatesEls = [
        document.getElementById('selected-templates-count'),
        document.getElementById('selection-template-count'),
        document.getElementById('sidebar-template-count')
    ];
    const modelsEls = [
        document.getElementById('selected-models-count'),
        document.getElementById('selection-model-count'),
        document.getElementById('sidebar-model-count')
    ];
    const totalEls = [
        document.getElementById('total-jobs-count'),
        document.getElementById('selection-total-pairs'),
        document.getElementById('sidebar-job-count'),
        document.getElementById('sidebar-total-jobs')
    ];
    
    templatesEls.forEach(el => { if (el) el.textContent = templates; });
    modelsEls.forEach(el => { if (el) el.textContent = models; });
    totalEls.forEach(el => { if (el) el.textContent = total; });
    
    // Update estimated time
    const estTimeEls = [
        document.getElementById('selection-est-time'),
        document.getElementById('sidebar-est-duration')
    ];
    estTimeEls.forEach(el => {
        if (el) {
            if (total > 0) {
                const minutes = total * 2; // ~2 min per job
                const hours = Math.floor(minutes / 60);
                const mins = minutes % 60;
                el.textContent = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
            } else {
                el.textContent = '--';
            }
        }
    });
}

/**
 * Update a stage enabled/disabled badge in the sidebar
 */
function updateStageBadge(badgeId, enabled) {
    const badge = document.getElementById(badgeId);
    if (badge) {
        badge.textContent = enabled ? 'Enabled' : 'Disabled';
        badge.className = enabled ? 'badge bg-success-lt' : 'badge bg-secondary-lt';
    }
}

/**
 * Update the review summary (step 3)
 */
function updateReviewSummary() {
    const wizard = AutomationWizard;
    const config = wizard.config;
    
    // Helper function to safely set text content
    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };
    
    // Generation summary
    setText('summary-templates', config.templates.length);
    setText('summary-models', config.models.length);
    setText('summary-gen-jobs', config.templates.length * config.models.length);
    
    // Analysis summary
    setText('summary-tools-count', config.analysisTools.length || 'None selected');
    
    // Generation options - show parallelism details
    const genParallelMode = config.generationOptions?.parallel ?? true;
    const genMaxConcurrent = config.generationOptions?.maxConcurrentTasks || 2;
    const genOptionsText = genParallelMode ? `Parallel (max ${genMaxConcurrent})` : 'Sequential';
    setText('summary-gen-options', genOptionsText);
    
    // Analysis options - show parallelism details
    const parallelMode = config.analysisOptions.parallel;
    const maxConcurrent = config.analysisOptions.maxConcurrentTasks || 3;
    const optionsText = parallelMode ? `Parallel (max ${maxConcurrent})` : 'Sequential';
    setText('summary-analysis-options', optionsText);
    
    // Job queue preview
    updateJobQueuePreview();
    
    // Estimated time - adjust for parallelism (both generation and analysis)
    const totalJobs = config.templates.length * config.models.length;
    const genConcurrency = genParallelMode ? Math.min(genMaxConcurrent, totalJobs) : 1;
    const analysisConcurrency = parallelMode ? Math.min(maxConcurrent, totalJobs) : 1;
    const genMinutes = Math.ceil(totalJobs / genConcurrency) * 2;  // ~2 min per batch for generation
    const analysisMinutes = Math.ceil(totalJobs / analysisConcurrency) * 1;  // ~1 min per batch for analysis
    const estMinutes = genMinutes + analysisMinutes;
    setText('est-duration', formatDuration(estMinutes * 60));
    setText('total-operations', totalJobs * 2); // gen + analysis
    setText('total-jobs-badge', `${totalJobs} jobs`);
    
    // Combined parallelism mode display
    const combinedParallelism = genParallelMode || parallelMode ? 
        `Gen: ${genParallelMode ? genMaxConcurrent : 1}x / Analysis: ${parallelMode ? maxConcurrent : 1}x` :
        'Sequential';
    setText('parallelism-mode', combinedParallelism);
}

/**
 * Update the job queue preview table
 */
function updateJobQueuePreview() {
    const wizard = AutomationWizard;
    const config = wizard.config;
    const tbody = document.getElementById('job-queue-preview');
    
    if (!tbody) return;
    
    let html = '';
    let jobNum = 0;
    
    config.templates.forEach(template => {
        config.models.forEach(model => {
            jobNum++;
            const templateName = template.replace(/_/g, ' ').replace('.json', '');
            const modelName = model.split('/').pop().replace(/_/g, ' ');
            const toolsCount = config.analysisTools.length || 0;
            
            html += `
                <tr>
                    <td>${jobNum}</td>
                    <td><span class="badge bg-azure-lt text-azure">${templateName}</span></td>
                    <td>${modelName}</td>
                    <td><span class="badge bg-green-lt text-green">${toolsCount} tools</span></td>
                    <td class="text-end text-muted">~3 min</td>
                </tr>
            `;
        });
    });
    
    if (html === '') {
        html = `
            <tr>
                <td colspan="5" class="text-center text-muted py-3">
                    <i class="fas fa-info-circle me-2"></i>
                    Select templates and models to preview job queue
                </td>
            </tr>
        `;
    }
    
    tbody.innerHTML = html;
}

// ============================================================================
// Pipeline Execution
// ============================================================================

/**
 * Launch the automation pipeline
 */
async function launchPipeline() {
    const wizard = AutomationWizard;
    
    // Final validation
    if (!validateStep(1) || !validateStep(2)) {
        showNotification('Please complete all required configuration', 'error');
        return;
    }
    
    // Collect final config
    collectStepConfig(3);
    
    // Prepare payload - wrapped in 'config' with nested structure matching backend expectation
    const payload = {
        config: {
            generation: {
                mode: wizard.config.generationMode || 'generate',
                models: wizard.config.models,
                templates: wizard.config.templates,
                existingApps: wizard.config.existingApps || [],
                options: wizard.config.generationOptions || { parallel: true, maxConcurrentTasks: 2 }
            },
            analysis: {
                enabled: true,
                tools: wizard.config.analysisTools,
                options: wizard.config.analysisOptions
            }
        },
        name: wizard.config.pipelineName
    };
    
    try {
        // Disable launch button
        const launchBtn = document.getElementById('launch-pipeline-btn');
        if (launchBtn) {
            launchBtn.disabled = true;
            launchBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Starting...';
        }
        
        // Call API to start pipeline
        const response = await fetch(wizard.endpoints.startPipeline, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to start pipeline');
        }
        
        // Update state
        wizard.state.pipelineId = data.pipeline_id;
        wizard.state.status = 'running';
        wizard.state.startTime = Date.now();
        wizard.state.jobs = data.jobs || [];
        
        addActivityLog('Pipeline started', 'info');
        showNotification('Pipeline started successfully', 'success');
        
        // Redirect to automation page with pipeline ID to open progress modal
        // This ensures the past executions list is refreshed with the new pipeline
        const baseUrl = window.location.pathname;
        window.location.href = `${baseUrl}?pipeline=${data.pipeline_id}&show_progress=1`;
        
    } catch (error) {
        console.error('Failed to start pipeline:', error);
        showNotification(error.message, 'error');
        
        // Re-enable launch button
        const launchBtn = document.getElementById('launch-pipeline-btn');
        if (launchBtn) {
            launchBtn.disabled = false;
            launchBtn.innerHTML = '<i class="fas fa-rocket me-2"></i>Launch Pipeline';
        }
    }
}

/**
 * Pause the running pipeline
 */
async function pausePipeline() {
    const wizard = AutomationWizard;
    
    if (!wizard.state.pipelineId) return;
    
    try {
        const response = await fetch(wizard.endpoints.pausePipeline(wizard.state.pipelineId), {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            wizard.state.status = 'paused';
            updateExecutionUI();
            addActivityLog('Pipeline paused', 'warning');
            showNotification('Pipeline paused', 'warning');
        } else {
            throw new Error(data.error || 'Failed to pause pipeline');
        }
    } catch (error) {
        console.error('Failed to pause pipeline:', error);
        showNotification(error.message, 'error');
    }
}

/**
 * Cancel the running pipeline
 */
async function cancelPipeline() {
    const wizard = AutomationWizard;
    
    if (!wizard.state.pipelineId) return;
    
    if (!confirm('Are you sure you want to cancel the pipeline? This cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(wizard.endpoints.cancelPipeline(wizard.state.pipelineId), {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            wizard.state.status = 'cancelled';
            stopStatusPolling();
            stopElapsedTimer();
            updateExecutionUI();
            addActivityLog('Pipeline cancelled by user', 'danger');
            showNotification('Pipeline cancelled', 'warning');
        } else {
            throw new Error(data.error || 'Failed to cancel pipeline');
        }
    } catch (error) {
        console.error('Failed to cancel pipeline:', error);
        showNotification(error.message, 'error');
    }
}

// ============================================================================
// Status Polling & Updates
// ============================================================================

/**
 * Start polling for pipeline status
 */
function startStatusPolling() {
    const wizard = AutomationWizard;
    
    // Clear existing interval
    if (wizard.state.pollInterval) {
        clearInterval(wizard.state.pollInterval);
    }
    
    // Poll every 2 seconds
    wizard.state.pollInterval = setInterval(pollPipelineStatus, 2000);
    
    // Also poll immediately
    pollPipelineStatus();
}

/**
 * Stop status polling
 */
function stopStatusPolling() {
    const wizard = AutomationWizard;
    
    if (wizard.state.pollInterval) {
        clearInterval(wizard.state.pollInterval);
        wizard.state.pollInterval = null;
    }
}

/**
 * Poll the server for pipeline status
 */
async function pollPipelineStatus() {
    const wizard = AutomationWizard;
    
    if (!wizard.state.pipelineId) return;
    
    try {
        const response = await fetch(
            wizard.endpoints.getStatus(wizard.state.pipelineId),
            {
                credentials: 'include',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }
        );
        
        if (!response.ok) {
            throw new Error('Failed to fetch status');
        }
        
        const result = await response.json();
        
        if (!result.success || !result.data) {
            throw new Error(result.error || 'Invalid response');
        }
        
        const data = result.data;
        
        // Update state from database-backed pipeline
        wizard.state.status = data.status;
        wizard.state.currentJob = data.current_job || null;
        wizard.state.completedJobs = []; // Will be built from progress
        
        // Update UI with progress from each stage
        updateStageProgress('generation', data.progress?.generation);
        updateStageProgress('analysis', data.progress?.analysis);
        
        // Update overall progress
        updateOverallProgress(data.overall_progress || 0);
        
        // Update current stage indicator
        updateCurrentStage(data.stage);
        
        // Update execution UI
        updateExecutionUI();
        
        // Check for completion
        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
            stopStatusPolling();
            stopElapsedTimer();
            onPipelineComplete(data);
        }
        
    } catch (error) {
        console.error('Status poll error:', error);
        // Don't stop polling on error, might be temporary
    }
}

/**
 * Update progress display for a specific stage
 */
function updateStageProgress(stageName, progress) {
    if (!progress) return;
    
    const total = progress.total || 0;
    const completed = progress.completed || 0;
    const failed = progress.failed || 0;
    const done = completed + failed;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    
    // Update count badge
    const countEl = document.getElementById(`stage-count-${stageName}`);
    if (countEl) {
        countEl.textContent = `${done}/${total}`;
    }
    
    // Update progress bar
    const progressEl = document.getElementById(`stage-progress-${stageName}`);
    if (progressEl) {
        progressEl.style.width = `${pct}%`;
    }
    
    // Update status text
    const statusEl = document.getElementById(`stage-status-${stageName}`);
    if (statusEl) {
        if (progress.status === 'skipped') {
            statusEl.textContent = 'Skipped';
        } else if (progress.status === 'completed') {
            statusEl.textContent = failed > 0 ? `Done (${failed} failed)` : 'Completed';
        } else if (progress.status === 'running') {
            statusEl.textContent = 'Running...';
        } else {
            statusEl.textContent = 'Pending';
        }
    }
    
    // Update card styling based on status
    const cardEl = document.getElementById(`stage-card-${stageName}`);
    if (cardEl) {
        cardEl.classList.remove('border-primary', 'border-success', 'border-danger');
        if (progress.status === 'running') {
            cardEl.classList.add('border-primary');
        } else if (progress.status === 'completed') {
            cardEl.classList.add(failed > 0 ? 'border-warning' : 'border-success');
        }
    }
    
    // Update icon
    const iconEl = document.getElementById(`stage-icon-${stageName}`);
    if (iconEl) {
        const icon = iconEl.querySelector('i');
        if (icon) {
            icon.classList.remove('fa-spin');
            if (progress.status === 'running') {
                icon.classList.add('fa-spin');
            }
        }
    }
    
    // Add to activity log for new completions
    if (progress.status === 'completed' && done === total && total > 0) {
        addActivityLog(`${stageName.charAt(0).toUpperCase() + stageName.slice(1)} stage completed (${completed} success, ${failed} failed)`, 
                       failed > 0 ? 'warning' : 'success');
    }
}

/**
 * Update overall progress bar
 */
function updateOverallProgress(pct) {
    // Cap progress at 100% to prevent display issues
    const cappedPct = Math.min(pct, 100);
    
    const progressBar = document.getElementById('overall-progress-bar');
    const progressText = document.getElementById('overall-progress-text');
    
    if (progressBar) {
        progressBar.style.width = `${cappedPct}%`;
        progressBar.setAttribute('aria-valuenow', cappedPct);
    }
    if (progressText) {
        progressText.textContent = `${Math.round(cappedPct)}%`;
    }
}

/**
 * Update current stage indicator
 */
function updateCurrentStage(stage) {
    // Update metrics panel
    const stageText = document.getElementById('metrics-current-stage');
    if (stageText) {
        const stageNames = {
            'generation': 'Generation',
            'analysis': 'Analysis',
            'done': 'Complete'
        };
        stageText.textContent = stageNames[stage] || stage;
    }
}

/**
 * Start elapsed time counter
 */
function startElapsedTimer() {
    const wizard = AutomationWizard;
    
    if (wizard.state.elapsedInterval) {
        clearInterval(wizard.state.elapsedInterval);
    }
    
    wizard.state.elapsedInterval = setInterval(updateElapsedTime, 1000);
}

/**
 * Stop elapsed time counter
 */
/**
 * Check for an active pipeline and restore it on page load
 */
async function checkAndRestoreActivePipeline() {
    const wizard = AutomationWizard;
    
    try {
        const response = await fetch('/automation/api/pipelines/active', {
            credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (!response.ok) {
            return; // No active pipeline or error
        }
        
        const result = await response.json();
        
        if (!result.success || !result.data) {
            return; // No active pipeline
        }
        
        const pipeline = result.data;
        
        // Restore pipeline state
        wizard.state.pipelineId = pipeline.id;
        wizard.state.status = pipeline.status;
        wizard.state.startTime = pipeline.started_at ? new Date(pipeline.started_at).getTime() : Date.now();
        
        // Update hidden form fields
        document.getElementById('pipeline-id').value = pipeline.id;
        document.getElementById('pipeline-status').value = pipeline.status;
        
        // Restore config if available
        if (pipeline.config) {
            wizard.config = {
                ...wizard.config,
                models: pipeline.config.models || [],
                templates: pipeline.config.templates || [],
                analysisTools: pipeline.config.analysis_tools || [],
                enableGeneration: pipeline.config.stages?.generation ?? true,
                enableAnalysis: pipeline.config.stages?.analysis ?? true
            };
        }
        
        // Navigate to execution panel
        goToStep(4);
        
        // Update UI with current status
        updateExecutionUI();
        
        // Update progress from pipeline data
        if (pipeline.progress) {
            updateStageProgress('generation', pipeline.progress.generation);
            updateStageProgress('analysis', pipeline.progress.analysis);
            updateOverallProgress(pipeline.overall_progress || 0);
            updateCurrentStage(pipeline.stage);
        }
        
        // Start polling if pipeline is still running
        if (['running', 'pending'].includes(pipeline.status)) {
            startStatusPolling();
            startElapsedTimer();
            addActivityLog('Reconnected to active pipeline', 'info');
        } else {
            // Show completion state
            onPipelineComplete(pipeline);
        }
        
        console.log('Restored active pipeline:', pipeline.id);
        
    } catch (error) {
        console.error('Error checking for active pipeline:', error);
    }
}

function stopElapsedTimer() {
    const wizard = AutomationWizard;
    
    if (wizard.state.elapsedInterval) {
        clearInterval(wizard.state.elapsedInterval);
        wizard.state.elapsedInterval = null;
    }
}

/**
 * Update elapsed time display
 */
function updateElapsedTime() {
    const wizard = AutomationWizard;
    
    if (!wizard.state.startTime) return;
    
    const elapsed = Math.floor((Date.now() - wizard.state.startTime) / 1000);
    const formatted = formatDuration(elapsed);
    
    const elapsedEl = document.getElementById('exec-elapsed-time');
    const metricsEl = document.getElementById('metrics-elapsed');
    
    if (elapsedEl) elapsedEl.textContent = formatted;
    if (metricsEl) metricsEl.textContent = formatted;
}

// ============================================================================
// Execution UI Updates
// ============================================================================

/**
 * Update the execution panel UI
 */
function updateExecutionUI() {
    const wizard = AutomationWizard;
    
    // Update status badge
    const statusBadge = document.getElementById('exec-status-badge');
    if (statusBadge) {
        const statusColors = {
            'pending': 'bg-secondary',
            'running': 'bg-primary',
            'paused': 'bg-warning',
            'completed': 'bg-success',
            'failed': 'bg-danger',
            'cancelled': 'bg-secondary'
        };
        statusBadge.className = `badge ${statusColors[wizard.state.status] || 'bg-secondary'}`;
        statusBadge.textContent = wizard.state.status.charAt(0).toUpperCase() + wizard.state.status.slice(1);
    }
    
    // Note: Overall progress is now updated by updateOverallProgress() called from pollPipelineStatus()
    // Stage progress is updated by updateStageProgress() called from pollPipelineStatus()
    
    // Update current job details
    updateCurrentJobDetails();
    
    // Update completed jobs table (legacy - may need to convert to activity log)
    updateCompletedJobsTable();
    
    // Update control buttons
    updateControlButtons();
}

/**
 * Update current job details panel
 */
function updateCurrentJobDetails() {
    const wizard = AutomationWizard;
    const container = document.getElementById('current-job-details');
    
    if (!container) return;
    
    const job = wizard.state.currentJob;
    
    if (!job) {
        container.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-hourglass-start fa-2x mb-2"></i>
                <div>Waiting for next job...</div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="d-flex align-items-start">
            <div class="me-3">
                <span class="avatar bg-primary">
                    <i class="fas ${getStageIcon(job.stage)}"></i>
                </span>
            </div>
            <div class="flex-fill">
                <div class="fw-semibold">${job.name || 'Processing...'}</div>
                <div class="text-muted small">${job.stage || '-'}</div>
                <div class="mt-2">
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-primary" style="width: ${job.progress || 0}%"></div>
                    </div>
                    <div class="text-muted small mt-1">${job.message || ''}</div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Update completed jobs table
 */
function updateCompletedJobsTable() {
    const wizard = AutomationWizard;
    const tbody = document.getElementById('completed-jobs-table');
    const countEl = document.getElementById('completed-jobs-count');
    
    if (!tbody) return;
    
    const jobs = wizard.state.completedJobs;
    
    if (countEl) countEl.textContent = jobs.length;
    
    if (jobs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted py-3">
                    <i class="fas fa-inbox me-2"></i>No completed jobs yet
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    jobs.forEach((job, index) => {
        const statusClass = job.status === 'success' ? 'bg-success' : 
                           job.status === 'failed' ? 'bg-danger' : 'bg-warning';
        
        html += `
            <tr>
                <td>${index + 1}</td>
                <td><span class="badge ${getStageColor(job.stage)}">${job.stage}</span></td>
                <td>${job.target || '-'}</td>
                <td><span class="badge ${statusClass}">${job.status}</span></td>
                <td>${formatDuration(job.duration || 0)}</td>
                <td class="text-end">
                    ${job.result_url ? `<a href="${job.result_url}" class="btn btn-ghost-primary btn-sm">View</a>` : ''}
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

/**
 * Update control buttons based on status
 */
function updateControlButtons() {
    const wizard = AutomationWizard;
    const status = wizard.state.status;
    
    const pauseBtn = document.getElementById('pause-pipeline-btn');
    const cancelBtn = document.getElementById('cancel-pipeline-btn');
    const completionActions = document.getElementById('completion-actions');
    const quickActionsPanel = document.getElementById('quick-actions-panel');
    const finalResultsPanel = document.getElementById('final-results-panel');
    
    const isRunning = status === 'running';
    const isComplete = ['completed', 'failed', 'cancelled'].includes(status);
    
    if (pauseBtn) {
        pauseBtn.disabled = !isRunning;
        pauseBtn.innerHTML = status === 'paused' ? 
            '<i class="fas fa-play me-1"></i>Resume' : 
            '<i class="fas fa-pause me-1"></i>Pause';
    }
    
    if (cancelBtn) cancelBtn.disabled = isComplete;
    if (completionActions) completionActions.style.display = isComplete ? 'block' : 'none';
    if (quickActionsPanel) quickActionsPanel.style.display = isComplete ? 'none' : 'block';
    if (finalResultsPanel) finalResultsPanel.style.display = isComplete ? 'block' : 'none';
}

/**
 * Update metrics sidebar panel
 */
function updateMetricsPanel(data) {
    const wizard = AutomationWizard;
    
    // Status
    const statusText = document.getElementById('metrics-status-text');
    if (statusText) {
        statusText.textContent = wizard.state.status.charAt(0).toUpperCase() + wizard.state.status.slice(1);
    }
    
    // Update status badge and header styling
    const statusBadge = document.getElementById('metrics-status-badge');
    const statusIcon = document.getElementById('metrics-status-icon');
    const statusHeader = document.getElementById('pipeline-status-header');
    const statusDot = document.getElementById('status-dot');
    const currentStageRow = document.getElementById('current-stage-row');
    
    if (statusBadge && statusIcon) {
        const statusConfig = {
            'ready': { badge: 'bg-primary-lt text-primary', icon: 'fa-play', dot: 'bg-primary', label: 'Idle' },
            'running': { badge: 'bg-success-lt text-success', icon: 'fa-spinner fa-spin', dot: 'bg-success', label: 'Running' },
            'paused': { badge: 'bg-warning-lt text-warning', icon: 'fa-pause', dot: 'bg-warning', label: 'Paused' },
            'completed': { badge: 'bg-success', icon: 'fa-check', dot: 'bg-success', label: 'Done' },
            'failed': { badge: 'bg-danger-lt text-danger', icon: 'fa-times', dot: 'bg-danger', label: 'Failed' },
            'cancelled': { badge: 'bg-secondary-lt text-secondary', icon: 'fa-ban', dot: 'bg-secondary', label: 'Cancelled' }
        };
        const config = statusConfig[wizard.state.status] || statusConfig['ready'];
        statusBadge.className = `badge ${config.badge}`;
        statusIcon.className = `fas ${config.icon} fa-xs me-1`;
        statusBadge.innerHTML = `<i class="fas ${config.icon} fa-xs me-1" id="metrics-status-icon"></i>${config.label}`;
        if (statusDot) statusDot.className = `status-dot status-dot-animated ${config.dot}`;
        if (statusHeader) {
            statusHeader.className = `pipeline-status-header px-3 py-2 border-bottom status-${wizard.state.status}`;
        }
    }
    
    // Show/hide current stage row when running
    if (currentStageRow) {
        currentStageRow.style.display = wizard.state.status === 'running' ? 'block' : 'none';
    }
    
    // Current stage
    const stageText = document.getElementById('metrics-current-stage');
    if (stageText && data.current_stage) {
        stageText.textContent = data.current_stage;
    }
    
    // Completed count
    const completedEl = document.getElementById('metrics-completed');
    const totalEl = document.getElementById('metrics-total');
    if (completedEl) completedEl.textContent = data.completed_count || 0;
    if (totalEl) totalEl.textContent = data.total_count || 0;
    
    // Update progress bar
    const progressBar = document.getElementById('metrics-progress-bar');
    if (progressBar && data.total_count > 0) {
        const pct = Math.round((data.completed_count / data.total_count) * 100);
        progressBar.style.width = `${pct}%`;
        progressBar.setAttribute('aria-valuenow', pct);
    }
    
    // Success rate (using the new element ID)
    const successRateEl = document.getElementById('metrics-success-rate-value');
    if (successRateEl && data.success_rate !== undefined) {
        const rate = Math.round(data.success_rate);
        successRateEl.textContent = `${rate}%`;
        // Color coding
        if (rate >= 80) successRateEl.className = 'h4 mb-0 text-success';
        else if (rate >= 50) successRateEl.className = 'h4 mb-0 text-warning';
        else successRateEl.className = 'h4 mb-0 text-danger';
    }
    
    // Failures
    const failuresEl = document.getElementById('metrics-failures');
    if (failuresEl) failuresEl.textContent = data.failed_count || 0;
    
    // ETA
    const etaEl = document.getElementById('metrics-eta');
    if (etaEl && data.estimated_remaining) {
        etaEl.textContent = formatDuration(data.estimated_remaining);
    }
}

/**
 * Handle pipeline completion
 */
function onPipelineComplete(data) {
    const wizard = AutomationWizard;
    
    addActivityLog(`Pipeline ${data.status}`, data.status === 'completed' ? 'success' : 'danger');
    
    // Update final summary
    const summaryEl = document.getElementById('final-summary');
    if (summaryEl) {
        const completed = data.completed_count || 0;
        const failed = data.failed_count || 0;
        summaryEl.textContent = `${completed} completed, ${failed} failed`;
    }
    
    // Show notification
    if (data.status === 'completed') {
        showNotification('Pipeline completed successfully!', 'success');
    } else if (data.status === 'failed') {
        showNotification('Pipeline failed. Check logs for details.', 'error');
    }
    
    updateExecutionUI();
}

// ============================================================================
// Activity Log
// ============================================================================

/**
 * Add entry to activity log
 */
function addActivityLog(message, type = 'info') {
    const log = document.getElementById('activity-log');
    if (!log) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const typeColors = {
        'info': 'text-info',
        'success': 'text-success',
        'warning': 'text-warning',
        'danger': 'text-danger',
        'error': 'text-danger'
    };
    
    const entry = document.createElement('div');
    entry.className = `px-2 py-1 border-bottom ${typeColors[type] || ''}`;
    entry.innerHTML = `<span class="text-muted">[${timestamp}]</span> ${message}`;
    
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

/**
 * Clear activity log
 */
function clearActivityLog() {
    const log = document.getElementById('activity-log');
    if (log) {
        log.innerHTML = '<div class="p-2 text-muted">Log cleared</div>';
    }
}

// ============================================================================
// Tool Selection Helpers
// ============================================================================

// Simple cache for tools data (survives step navigation but not page refresh)
const toolsCache = {
    data: null,
    timestamp: null,
    maxAge: 5 * 60 * 1000, // 5 minutes
    
    isValid() {
        return this.data && this.timestamp && (Date.now() - this.timestamp < this.maxAge);
    },
    
    set(data) {
        this.data = data;
        this.timestamp = Date.now();
    },
    
    get() {
        return this.isValid() ? this.data : null;
    },
    
    clear() {
        this.data = null;
        this.timestamp = null;
    }
};

/**
 * Load available analysis tools (fallback/programmatic use)
 * Note: Primary loading is now done via HTMX with hx-trigger="intersect once"
 */
async function loadAnalysisTools() {
    const wizard = window.AutomationWizard;
    
    // Check cache first
    const cached = toolsCache.get();
    if (cached) {
        console.log('[AutomationWizard] Using cached tools data');
        renderToolLists(cached);
        return;
    }
    
    try {
        console.log('[AutomationWizard] Loading analysis tools from:', wizard.endpoints.getTools);
        const response = await fetch(wizard.endpoints.getTools, {
            credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (!response.ok) {
            console.error('[AutomationWizard] Failed to load tools:', response.status, response.statusText);
            renderToolsError('Failed to load analysis tools');
            return;
        }
        
        const data = await response.json();
        console.log('[AutomationWizard] Tools loaded:', data);
        
        if (data.success === false) {
            console.error('[AutomationWizard] Tools API error:', data.error);
            renderToolsError(data.error || 'Error loading tools');
            return;
        }
        
        if (data.tools) {
            // Cache the tools data
            toolsCache.set(data.tools);
            renderToolLists(data.tools);
        } else {
            console.warn('[AutomationWizard] No tools in response');
            renderToolsError('No analysis tools available');
        }
    } catch (error) {
        console.error('[AutomationWizard] Failed to load tools:', error);
        renderToolsError('Network error loading tools');
    }
}

/**
 * Render error state in tool lists
 */
function renderToolsError(message) {
    const categories = ['static-tools-list', 'dynamic-tools-list', 'performance-tools-list', 'ai-tools-list'];
    categories.forEach(elementId => {
        const container = document.getElementById(elementId);
        if (container) {
            container.innerHTML = `<div class="p-2 text-danger small"><i class="fas fa-exclamation-triangle me-1"></i>${message}</div>`;
        }
    });
}

/**
 * Render tool lists in custom tools section
 */
function renderToolLists(tools) {
    const categories = {
        'static': 'static-tools-list',
        'dynamic': 'dynamic-tools-list',
        'performance': 'performance-tools-list',
        'ai': 'ai-tools-list'
    };
    
    Object.entries(categories).forEach(([category, elementId]) => {
        const container = document.getElementById(elementId);
        if (!container) return;
        
        // tools is an object keyed by category, e.g., tools.static, tools.dynamic
        const categoryTools = tools[category] || [];
        
        if (categoryTools.length === 0) {
            container.innerHTML = '<div class="p-2 text-muted small">No tools available</div>';
            return;
        }
        
        let html = '<div class="list-group list-group-flush">';
        categoryTools.forEach(tool => {
            html += `
                <label class="list-group-item">
                    <input class="form-check-input me-2" type="checkbox" 
                           name="analysis_tool" value="${tool.name}"
                           ${tool.available ? '' : 'disabled'}>
                    <span class="fw-medium">${tool.display_name || tool.name}</span>
                    ${!tool.available ? '<span class="badge bg-secondary ms-2">unavailable</span>' : ''}
                    <span class="text-muted small d-block">${tool.description || ''}</span>
                </label>
            `;
        });
        html += '</div>';
        
        container.innerHTML = html;
    });
}

/**
 * Select all analysis tools
 */
function selectAllTools() {
    document.querySelectorAll('input[name="analysis_tool"]').forEach(el => {
        el.checked = true;
    });
}

/**
 * Clear all analysis tools
 */
function clearAllTools() {
    document.querySelectorAll('input[name="analysis_tool"]').forEach(el => {
        el.checked = false;
    });
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format duration in seconds to human readable
 */
function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}m ${secs}s`;
    }
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
}

/**
 * Get icon for pipeline stage
 */
function getStageIcon(stage) {
    const icons = {
        'generation': 'fa-code',
        'analysis': 'fa-search-plus'
    };
    return icons[stage] || 'fa-cog';
}

/**
 * Get color class for pipeline stage
 */
function getStageColor(stage) {
    const colors = {
        'generation': 'bg-azure-lt text-azure',
        'analysis': 'bg-green-lt text-green'
    };
    return colors[stage] || 'bg-secondary';
}

// Track last notification to prevent spam
let lastNotification = { message: '', time: 0 };

/**
 * Show notification toast with debouncing to prevent spam
 */
function showNotification(message, type = 'info') {
    // Debounce: skip duplicate notifications within 2 seconds
    const now = Date.now();
    if (message === lastNotification.message && (now - lastNotification.time) < 2000) {
        return;
    }
    lastNotification = { message, time: now };
    
    // Use existing notification system if available
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
        return;
    }
    
    // Fallback to alert
    if (type === 'error') {
        console.error(message);
    } else {
        console.log(`[${type}] ${message}`);
    }
}

/**
 * Reset wizard to initial state
 */
function resetWizard() {
    const wizard = AutomationWizard;
    
    // Reset config
    wizard.config = {
        generationMode: 'generate',
        templates: [],
        models: [],
        existingApps: [],
        analysisTools: [],
        analysisOptions: {
            parallel: true,  // Default to parallel for batch efficiency
            maxConcurrentTasks: 3,  // Default parallelism limit
            autoStartContainers: true,  // Auto-start containers by default
            stopAfterAnalysis: true  // Clean up containers after analysis
        },
        pipelineName: ''
    };
    
    // Reset state
    wizard.state = {
        currentStep: 1,
        pipelineId: null,
        status: 'idle',
        startTime: null,
        jobs: [],
        completedJobs: [],
        currentJob: null,
        pollInterval: null,
        elapsedInterval: null
    };
    
    // Reset UI
    document.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach(el => {
        el.checked = el.defaultChecked;
    });
    
    goToStep(1);
}

// ============================================================================
// Event Handlers & Initialization
// ============================================================================

/**
 * Initialize wizard on page load
 */
document.addEventListener('DOMContentLoaded', async function() {
    // Check for active pipeline first (await to avoid race condition)
    await checkAndRestoreActivePipeline();
    
    // Initialize at step 1 (if no active pipeline was restored)
    if (!AutomationWizard.state.pipelineId) {
        goToStep(1);
    }
    
    // Note: Analysis tools are now loaded via HTMX with hx-trigger="intersect once"
    // This ensures tools load when Step 2 becomes visible, fixing the initial load issue.
    // The loadAnalysisTools() function is kept as a fallback for programmatic refresh.
    
    // Setup event listeners for selection changes (using event delegation for dynamic content)
    document.addEventListener('change', function(e) {
        // Template/model checkboxes
        if (e.target.matches('input[name="template"], input[name="model"]')) {
            collectGenerationConfig();
        }
        
        // Generation mode toggle
        if (e.target.matches('input[name="generation_mode"]')) {
            toggleGenerationMode(e.target.value);
        }
        
        // Existing apps checkboxes
        if (e.target.matches('input[name="existing_app"]')) {
            updateExistingAppsSummary();
        }
        
        // Stage enable/disable toggles
        if (e.target.matches('#enable-generation')) {
            updateStageBadge('gen-status-badge', e.target.checked);
        }
        if (e.target.matches('#enable-analysis')) {
            updateStageBadge('analysis-status-badge', e.target.checked);
        }
    });
    
    // Setup click handlers for select/clear buttons (using event delegation)
    document.addEventListener('click', function(e) {
        // Select all templates
        if (e.target.matches('#select-all-templates, #select-all-templates *')) {
            e.preventDefault();
            selectAllTemplates();
        }
        // Clear all templates
        if (e.target.matches('#clear-all-templates, #clear-all-templates *')) {
            e.preventDefault();
            clearAllTemplates();
        }
        // Select all models
        if (e.target.matches('#select-all-models, #select-all-models *')) {
            e.preventDefault();
            selectAllModels();
        }
        // Clear all models
        if (e.target.matches('#clear-all-models, #clear-all-models *')) {
            e.preventDefault();
            clearAllModels();
        }
        // Select all existing apps
        if (e.target.matches('#select-all-existing-apps, #select-all-existing-apps *')) {
            e.preventDefault();
            selectAllExistingApps();
        }
        // Clear all existing apps
        if (e.target.matches('#clear-all-existing-apps, #clear-all-existing-apps *')) {
            e.preventDefault();
            clearAllExistingApps();
        }
        // Save settings button (both old and sidebar)
        if (e.target.matches('#save-settings-btn, #save-settings-btn *, #save-settings-btn-sidebar, #save-settings-btn-sidebar *')) {
            e.preventDefault();
            showSaveSettingsModal();
        }
        // Load settings button (sidebar - opens modal)
        if (e.target.matches('#load-settings-btn-sidebar, #load-settings-btn-sidebar *')) {
            e.preventDefault();
            showLoadSettingsModal();
        }
        // Save settings confirm
        if (e.target.matches('#save-settings-confirm, #save-settings-confirm *')) {
            e.preventDefault();
            saveCurrentSettings();
        }
        // Load settings item (legacy dropdown - still works if present)
        if (e.target.matches('.load-settings-item, .load-settings-item *')) {
            e.preventDefault();
            const item = e.target.closest('.load-settings-item');
            if (item && item.dataset.settingsId) {
                loadPipelineSettings(item.dataset.settingsId);
            }
        }
        // Manage settings link (both old and sidebar)
        if (e.target.matches('#manage-settings-link, #manage-settings-link *, #manage-settings-link-sidebar, #manage-settings-link-sidebar *')) {
            e.preventDefault();
            showManageSettingsModal();
        }
    });
    
    // Setup search input handlers
    document.addEventListener('input', function(e) {
        if (e.target.matches('#template-search')) {
            filterTemplates(e.target.value);
        }
        if (e.target.matches('#model-search')) {
            filterModels(e.target.value);
        }
        if (e.target.matches('#existing-apps-search')) {
            filterExistingApps(e.target.value);
        }
        if (e.target.matches('#filter-model')) {
            filterExistingAppsByModel(e.target.value);
        }
        if (e.target.matches('#filter-status')) {
            filterExistingAppsByStatus(e.target.value);
        }
    });
    
    console.log('Automation Wizard initialized');
});

// ============================================================================
// Generation Stage Helper Functions
// ============================================================================

/**
 * Toggle between Generate New and Use Existing Apps modes
 */
function toggleGenerationMode(mode) {
    const generateSection = document.getElementById('generate-new-section');
    const existingSection = document.getElementById('existing-apps-section');
    
    if (mode === 'generate') {
        if (generateSection) generateSection.classList.remove('d-none');
        if (existingSection) existingSection.classList.add('d-none');
        AutomationWizard.config.generationMode = 'generate';
    } else {
        if (generateSection) generateSection.classList.add('d-none');
        if (existingSection) existingSection.classList.remove('d-none');
        AutomationWizard.config.generationMode = 'existing';
    }
}

/**
 * Update existing apps selection summary
 */
function updateExistingAppsSummary() {
    const count = document.querySelectorAll('input[name="existing_app"]:checked').length;
    const countEl = document.getElementById('existing-apps-count');
    if (countEl) countEl.textContent = count;
    
    // Store in config
    AutomationWizard.config.existingApps = Array.from(
        document.querySelectorAll('input[name="existing_app"]:checked')
    ).map(el => el.value);
}

/**
 * Filter templates by search query (works with table rows)
 */
function filterTemplates(query) {
    const items = document.querySelectorAll('.template-item');
    const lowerQuery = (query || '').toLowerCase().trim();
    
    items.forEach(item => {
        const slug = (item.dataset.slug || '').toLowerCase();
        const text = item.textContent.toLowerCase();
        const visible = !lowerQuery || slug.includes(lowerQuery) || text.includes(lowerQuery);
        item.style.display = visible ? '' : 'none';
    });
}
// Expose globally for inline handlers
window.filterTemplates = filterTemplates;

/**
 * Filter models by search query (works with table rows)
 */
function filterModels(query) {
    const items = document.querySelectorAll('.model-item');
    const headers = document.querySelectorAll('.provider-header');
    const lowerQuery = (query || '').toLowerCase().trim();
    
    // Track visible providers
    const visibleProviders = new Set();
    
    items.forEach(item => {
        const slug = (item.dataset.slug || '').toLowerCase();
        const text = item.textContent.toLowerCase();
        const isVisible = !lowerQuery || slug.includes(lowerQuery) || text.includes(lowerQuery);
        item.style.display = isVisible ? '' : 'none';
        if (isVisible && item.dataset.provider) {
            visibleProviders.add(item.dataset.provider);
        }
    });
    
    // Show/hide provider headers based on visible models
    headers.forEach(header => {
        const provider = header.dataset.provider;
        header.style.display = (!lowerQuery || visibleProviders.has(provider)) ? '' : 'none';
    });
}
// Expose globally for inline handlers
window.filterModels = filterModels;

/**
 * Toggle template checkbox when clicking the row
 */
function toggleTemplateCheckbox(row) {
    const checkbox = row.querySelector('input[type="checkbox"]');
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
        collectGenerationConfig();
    }
}
// Expose globally for inline handlers
window.toggleTemplateCheckbox = toggleTemplateCheckbox;

/**
 * Toggle model checkbox when clicking the row
 */
function toggleModelCheckbox(row) {
    const checkbox = row.querySelector('input[type="checkbox"]');
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
        collectGenerationConfig();
    }
}
// Expose globally for inline handlers
window.toggleModelCheckbox = toggleModelCheckbox;

/**
 * Filter existing apps by search query
 */
function filterExistingApps(query) {
    const items = document.querySelectorAll('.existing-app-item');
    const lowerQuery = (query || '').toLowerCase().trim();
    items.forEach(item => {
        const model = (item.dataset.model || '').toLowerCase();
        const text = item.textContent.toLowerCase();
        item.style.display = (!lowerQuery || model.includes(lowerQuery) || text.includes(lowerQuery)) ? '' : 'none';
    });
}
// Expose globally for inline handlers
window.filterExistingApps = filterExistingApps;

/**
 * Filter existing apps by model
 */
function filterExistingAppsByModel(model) {
    const items = document.querySelectorAll('.existing-app-item');
    items.forEach(item => {
        if (!model || item.dataset.model === model) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}
// Expose globally for inline handlers
window.filterExistingAppsByModel = filterExistingAppsByModel;

/**
 * Filter existing apps by status
 */
function filterExistingAppsByStatus(status) {
    const items = document.querySelectorAll('.existing-app-item');
    items.forEach(item => {
        if (!status || item.dataset.status === status) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}
// Expose globally for inline handlers
window.filterExistingAppsByStatus = filterExistingAppsByStatus;

/**
 * Toggle existing app checkbox when clicking the row
 */
function toggleExistingAppCheckbox(row) {
    const checkbox = row.querySelector('input[type="checkbox"]');
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
        updateExistingAppsSummary();
    }
}
// Expose globally for inline handlers
window.toggleExistingAppCheckbox = toggleExistingAppCheckbox;

/**
 * Select all visible templates
 */
function selectAllTemplates() {
    document.querySelectorAll('input[name="template"]').forEach(cb => {
        const item = cb.closest('.template-item');
        if (!item || item.style.display !== 'none') {
            cb.checked = true;
        }
    });
    collectGenerationConfig();
}

/**
 * Clear all template selections
 */
function clearAllTemplates() {
    document.querySelectorAll('input[name="template"]').forEach(cb => cb.checked = false);
    collectGenerationConfig();
}

/**
 * Select all visible models
 */
function selectAllModels() {
    document.querySelectorAll('input[name="model"]').forEach(cb => {
        const item = cb.closest('.model-item');
        if (!item || item.style.display !== 'none') {
            cb.checked = true;
        }
    });
    collectGenerationConfig();
}

/**
 * Clear all model selections
 */
function clearAllModels() {
    document.querySelectorAll('input[name="model"]').forEach(cb => cb.checked = false);
    collectGenerationConfig();
}

/**
 * Select all visible existing apps
 */
function selectAllExistingApps() {
    document.querySelectorAll('input[name="existing_app"]').forEach(cb => {
        const item = cb.closest('.existing-app-item');
        if (!item || item.style.display !== 'none') {
            cb.checked = true;
        }
    });
    updateExistingAppsSummary();
}

/**
 * Clear all existing app selections
 */
function clearAllExistingApps() {
    document.querySelectorAll('input[name="existing_app"]').forEach(cb => cb.checked = false);
    updateExistingAppsSummary();
}

// ============================================================================
// Settings Management Functions
// ============================================================================

/**
 * Show the save settings modal
 */
function showSaveSettingsModal() {
    const modal = new bootstrap.Modal(document.getElementById('saveSettingsModal'));
    modal.show();
}

/**
 * Show the load settings modal with all saved settings
 */
function showLoadSettingsModal() {
    const list = document.getElementById('load-settings-list');
    if (list) {
        list.innerHTML = `
            <div class="text-center py-4 text-muted">
                <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                Loading saved settings...
            </div>
        `;
    }
    
    const modal = new bootstrap.Modal(document.getElementById('loadSettingsModal'));
    modal.show();
    
    // Load settings list
    fetch('/automation/api/settings', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderLoadSettingsList(data.data);
            } else {
                if (list) {
                    list.innerHTML = '<div class="text-center py-4 text-danger">Error loading settings</div>';
                }
            }
        })
        .catch(err => {
            console.error('Error loading settings:', err);
            if (list) {
                list.innerHTML = '<div class="text-center py-4 text-danger">Error loading settings</div>';
            }
        });
}

/**
 * Render the load settings list with full preview
 */
function renderLoadSettingsList(settings) {
    const list = document.getElementById('load-settings-list');
    if (!list) return;
    
    if (!settings || settings.length === 0) {
        list.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="fas fa-bookmark fa-2x mb-3 opacity-50"></i>
                <p class="mb-1">No saved settings</p>
                <p class="small">Save your current pipeline configuration to reuse it later.</p>
            </div>
        `;
        return;
    }
    
    list.innerHTML = settings.map(s => {
        const config = s.config || {};
        const templatesCount = (config.templates || []).length;
        const modelsCount = (config.models || []).length;
        const existingAppsCount = (config.existingApps || []).length;
        const toolsCount = (config.analysisTools || []).length;
        const mode = config.mode || 'generate';
        
        return `
            <div class="list-group-item list-group-item-action load-settings-modal-item" 
                 data-settings-id="${s.id}" 
                 role="button">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <h6 class="mb-0">${escapeHtml(s.name)}</h6>
                        ${s.description ? `<small class="text-muted">${escapeHtml(s.description)}</small>` : ''}
                    </div>
                    <div class="d-flex gap-1">
                        ${s.is_default ? '<span class="badge bg-primary">Default</span>' : ''}
                    </div>
                </div>
                <div class="row g-2 small">
                    <div class="col-6 col-md-3">
                        <div class="text-muted">Mode</div>
                        <div class="fw-medium">
                            <i class="fas ${mode === 'existing' ? 'fa-folder-open' : 'fa-magic'} me-1 text-primary"></i>
                            ${mode === 'existing' ? 'Existing' : 'Generate'}
                        </div>
                    </div>
                    ${mode === 'generate' ? `
                    <div class="col-6 col-md-3">
                        <div class="text-muted">Templates</div>
                        <div class="fw-medium">${templatesCount}</div>
                    </div>
                    <div class="col-6 col-md-3">
                        <div class="text-muted">Models</div>
                        <div class="fw-medium">${modelsCount}</div>
                    </div>
                    ` : `
                    <div class="col-6 col-md-3">
                        <div class="text-muted">Existing Apps</div>
                        <div class="fw-medium">${existingAppsCount}</div>
                    </div>
                    <div class="col-6 col-md-3"></div>
                    `}
                    <div class="col-6 col-md-3">
                        <div class="text-muted">Analysis Tools</div>
                        <div class="fw-medium">${toolsCount}</div>
                    </div>
                </div>
                <div class="mt-2 small">
                    ${mode === 'generate' ? `<span class="text-muted">${templatesCount * modelsCount} jobs</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    // Add click handlers
    list.querySelectorAll('.load-settings-modal-item').forEach(item => {
        item.addEventListener('click', () => {
            const settingsId = item.dataset.settingsId;
            loadPipelineSettingsAndClose(settingsId);
        });
    });
}

/**
 * Load pipeline settings and close the modal
 */
function loadPipelineSettingsAndClose(settingsId) {
    fetch(`/automation/api/settings/${settingsId}`, { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.data) {
                applySettings(data.data.config);
                
                // Close the modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('loadSettingsModal'));
                if (modal) modal.hide();
                
                showNotification(`Settings "${data.data.name}" loaded`, 'success');
            } else {
                showNotification('Error loading settings', 'error');
            }
        })
        .catch(err => {
            console.error('Error loading settings:', err);
            showNotification('Error loading settings', 'error');
        });
}

/**
 * Show the manage settings modal
 */
function showManageSettingsModal() {
    // Load settings list first
    fetch('/automation/api/settings', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderManageSettingsList(data.data);
                const modal = new bootstrap.Modal(document.getElementById('manageSettingsModal'));
                modal.show();
            }
        })
        .catch(err => console.error('Error loading settings:', err));
}

/**
 * Render the manage settings list
 */
function renderManageSettingsList(settings) {
    const list = document.getElementById('manage-settings-list');
    if (!list) return;
    
    if (!settings || settings.length === 0) {
        list.innerHTML = '<div class="text-muted text-center py-3">No saved settings</div>';
        return;
    }
    
    list.innerHTML = settings.map(s => `
        <div class="list-group-item d-flex justify-content-between align-items-center">
            <div>
                <div class="fw-medium">${escapeHtml(s.name)}</div>
                ${s.description ? `<div class="text-muted small">${escapeHtml(s.description)}</div>` : ''}
            </div>
            <div class="btn-group btn-group-sm">
                ${!s.is_default ? `<button class="btn btn-ghost-primary" onclick="setDefaultSettings(${s.id})"><i class="fas fa-star"></i></button>` : '<span class="badge bg-primary-lt me-2">Default</span>'}
                <button class="btn btn-ghost-danger" onclick="deleteSettings(${s.id})"><i class="fas fa-trash"></i></button>
            </div>
        </div>
    `).join('');
}

/**
 * Helper to escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Save current settings
 */
function saveCurrentSettings() {
    const name = document.getElementById('settings-name')?.value.trim();
    if (!name) {
        showNotification('Please enter a name for the settings', 'warning');
        return;
    }
    
    const description = document.getElementById('settings-description')?.value.trim() || '';
    const isDefault = document.getElementById('settings-default')?.checked || false;
    
    // Gather COMPLETE current config from AutomationWizard
    // First ensure we collect from all steps
    collectGenerationConfig();
    collectAnalysisConfig();
    
    const wizard = AutomationWizard;
    const config = {
        // Step 1 - Generation
        mode: wizard.config.generationMode || 'generate',
        templates: wizard.config.templates || [],
        models: wizard.config.models || [],
        existingApps: wizard.config.existingApps || [],
        
        // Step 2 - Analysis
        analysisTools: wizard.config.analysisTools || [],
        analysisOptions: wizard.config.analysisOptions || {
            parallel: true,
            maxConcurrentTasks: 3,
            autoStartContainers: true,
            stopAfterAnalysis: true
        }
    };
    
    fetch('/automation/api/settings', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, config, is_default: isDefault }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('saveSettingsModal'));
                if (modal) modal.hide();
                // Clear the form
                document.getElementById('settings-name').value = '';
                document.getElementById('settings-description').value = '';
                document.getElementById('settings-default').checked = false;
                showNotification('Settings saved successfully', 'success');
            } else {
                showNotification('Error saving settings: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => {
            console.error('Error saving settings:', err);
            showNotification('Error saving settings', 'error');
        });
}

/**
 * Load pipeline settings by ID
 */
function loadPipelineSettings(settingsId) {
    fetch(`/automation/api/settings/${settingsId}`, { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.data) {
                applySettings(data.data.config);
                showNotification('Settings loaded', 'success');
            }
        })
        .catch(err => console.error('Error loading settings:', err));
}

/**
 * Apply settings configuration to the UI
 */
function applySettings(config) {
    const wizard = AutomationWizard;
    
    // === Step 1: Generation Settings ===
    
    // Set mode
    if (config.mode === 'existing') {
        const existingRadio = document.getElementById('mode-existing');
        if (existingRadio) existingRadio.checked = true;
        toggleGenerationMode('existing');
    } else {
        const generateRadio = document.getElementById('mode-generate');
        if (generateRadio) generateRadio.checked = true;
        toggleGenerationMode('generate');
    }
    
    // Set templates
    document.querySelectorAll('input[name="template"]').forEach(cb => {
        cb.checked = config.templates && config.templates.includes(cb.value);
    });
    
    // Set models
    document.querySelectorAll('input[name="model"]').forEach(cb => {
        cb.checked = config.models && config.models.includes(cb.value);
    });
    
    // Set existing apps
    document.querySelectorAll('input[name="existing_app"]').forEach(cb => {
        cb.checked = config.existingApps && config.existingApps.includes(cb.value);
    });
    
    // Update wizard config for generation
    wizard.config.generationMode = config.mode || 'generate';
    wizard.config.templates = config.templates || [];
    wizard.config.models = config.models || [];
    wizard.config.existingApps = config.existingApps || [];
    
    // === Step 2: Analysis Settings ===
    
    // Set analysis tools
    if (config.analysisTools) {
        document.querySelectorAll('input[name="analysis_tool"]').forEach(cb => {
            cb.checked = config.analysisTools.includes(cb.value);
        });
        wizard.config.analysisTools = config.analysisTools;
    }
    
    // Set analysis options
    if (config.analysisOptions) {
        const opts = config.analysisOptions;
        const parallel = document.getElementById('analysis-parallel');
        const maxConcurrent = document.getElementById('analysis-max-concurrent');
        const autoStart = document.getElementById('analysis-container-auto');
        const stopAfter = document.getElementById('analysis-container-stop');
        
        if (parallel) parallel.checked = opts.parallel ?? true;
        if (maxConcurrent) maxConcurrent.value = opts.maxConcurrentTasks ?? 3;
        if (autoStart) autoStart.checked = opts.autoStartContainers ?? true;
        if (stopAfter) stopAfter.checked = opts.stopAfterAnalysis ?? true;
        
        wizard.config.analysisOptions = opts;
    }
    
    // === Update UI summaries ===
    updateSelectionSummary();
    updateExistingAppsSummary();
    
    // Update sidebar analysis summary
    const analysisSummaryEl = document.getElementById('sidebar-analysis-summary');
    if (analysisSummaryEl && config.analysisTools) {
        const toolsCount = config.analysisTools.length || 0;
        analysisSummaryEl.innerHTML = `Tools: <strong>${toolsCount} selected</strong>`;
    }
}

/**
 * Set a settings preset as default
 */
function setDefaultSettings(settingsId) {
    fetch(`/automation/api/settings/${settingsId}/default`, { method: 'POST', credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Default settings updated', 'success');
                setTimeout(() => location.reload(), 500);
            }
        })
        .catch(err => console.error('Error setting default:', err));
}

/**
 * Delete a settings preset
 */
function deleteSettings(settingsId) {
    if (!confirm('Are you sure you want to delete this settings preset?')) return;
    
    fetch(`/automation/api/settings/${settingsId}`, { method: 'DELETE', credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Settings deleted', 'success');
                setTimeout(() => location.reload(), 500);
            }
        })
        .catch(err => console.error('Error deleting settings:', err));
}

// ============================================================================
// Global Function Aliases (for onclick handlers in HTML)
// ============================================================================

// Alias for startPipeline (used in HTML onclick)
function startPipeline() {
    launchPipeline();
}

// Make functions available globally for HTML onclick handlers
window.goToStep = goToStep;
window.nextStep = nextStep;
window.previousStep = previousStep;
window.prevStep = prevStep;
window.startPipeline = startPipeline;
window.launchPipeline = launchPipeline;
window.pausePipeline = pausePipeline;
window.cancelPipeline = cancelPipeline;
window.resetWizard = resetWizard;
window.selectAllTools = selectAllTools;
window.clearAllTools = clearAllTools;
window.clearActivityLog = clearActivityLog;
window.selectAllTemplates = selectAllTemplates;
window.clearAllTemplates = clearAllTemplates;
window.selectAllModels = selectAllModels;
window.clearAllModels = clearAllModels;
window.selectAllExistingApps = selectAllExistingApps;
window.clearAllExistingApps = clearAllExistingApps;
window.toggleGenerationMode = toggleGenerationMode;
window.filterTemplates = filterTemplates;
window.filterModels = filterModels;
window.filterExistingApps = filterExistingApps;
window.setDefaultSettings = setDefaultSettings;
window.deleteSettings = deleteSettings;
window.showSaveSettingsModal = showSaveSettingsModal;
window.showLoadSettingsModal = showLoadSettingsModal;
window.showManageSettingsModal = showManageSettingsModal;
window.loadPipelineSettingsAndClose = loadPipelineSettingsAndClose;

} // End of AutomationWizard guard block

// Alias for backward compatibility (scripts that use AutomationWizard directly)
const AutomationWizard = window.AutomationWizard;
