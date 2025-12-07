/**
 * Automation Wizard - Pipeline State Machine & UI Controller
 * Manages the multi-step wizard for automated generation → analysis → reports workflow
 */

// ============================================================================
// State Management
// ============================================================================

const AutomationWizard = {
    // Pipeline configuration state
    config: {
        generationMode: 'generate', // 'generate' or 'existing'
        templates: [],
        models: [],
        existingApps: [], // for existing apps mode
        analysisProfile: 'comprehensive',
        analysisTools: [],
        analysisOptions: {
            waitForCompletion: true,
            parallel: false,
            autoStartContainers: false
        },
        reportFormats: ['html'],
        reportScope: 'individual',
        reportSections: ['summary', 'security', 'quality', 'performance', 'ai'],
        reportOptions: {
            autoOpen: true,
            includeCode: false,
            includeSarif: false
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
        startPipeline: '/automation/api/start',
        pausePipeline: '/automation/api/pause',
        cancelPipeline: '/automation/api/cancel',
        getStatus: (id) => `/automation/api/status/${id}`,
        getTools: '/automation/api/tools',
        fragmentStage: (stage) => `/automation/fragment/stage/${stage}`,
        fragmentStatus: '/automation/fragment/status'
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
    const totalSteps = 5; // 4 config + 1 execution
    
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
    if (step === 4) updateReviewSummary();
    
    // Special handling for execution step
    if (step === 5) {
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
    const wizard = AutomationWizard;
    const current = wizard.state.currentStep;
    
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
    if (step < 4) {
        // Steps 1-3: show Next button
        if (nextBtn) nextBtn.classList.remove('d-none');
        if (startBtn) startBtn.classList.add('d-none');
        if (startBtnLoading) startBtnLoading.classList.add('d-none');
    } else if (step === 4) {
        // Step 4 (Review): show Start Pipeline button
        if (nextBtn) nextBtn.classList.add('d-none');
        if (startBtn) startBtn.classList.remove('d-none');
        if (startBtnLoading) startBtnLoading.classList.add('d-none');
    } else {
        // Step 5 (Execution): hide navigation
        if (nextBtn) nextBtn.classList.add('d-none');
        if (startBtn) startBtn.classList.add('d-none');
    }
}

/**
 * Update wizard progress bar
 */
function updateWizardProgress(step) {
    const totalConfigSteps = 4;
    const progress = Math.round((Math.min(step, totalConfigSteps) / totalConfigSteps) * 100);
    
    const progressBar = document.getElementById('wizard-progress-bar');
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
            if (wizard.config.analysisProfile === 'custom' && 
                wizard.config.analysisTools.length === 0) {
                showNotification('Please select at least one analysis tool', 'warning');
                highlightElement('#custom-tools-section', true);
                return false;
            }
            return true;
            
        case 3: // Reports
            if (wizard.config.reportFormats.length === 0) {
                showNotification('Please select at least one report format', 'warning');
                return false;
            }
            return true;
            
        case 4: // Review
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
            
        case 3: // Reports
            collectReportsConfig();
            break;
            
        case 4: // Review
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
    
    updateSelectionSummary();
}

/**
 * Collect analysis step configuration
 */
function collectAnalysisConfig() {
    const wizard = AutomationWizard;
    
    // Get analysis profile
    wizard.config.analysisProfile = document.querySelector(
        'input[name="analysis_profile"]:checked'
    )?.value || 'comprehensive';
    
    // Get custom tools if applicable
    if (wizard.config.analysisProfile === 'custom') {
        wizard.config.analysisTools = Array.from(
            document.querySelectorAll('input[name="analysis_tool"]:checked')
        ).map(el => el.value);
    }
    
    // Get analysis options
    wizard.config.analysisOptions = {
        waitForCompletion: document.getElementById('analysis-wait-complete')?.checked ?? true,
        parallel: document.getElementById('analysis-parallel')?.checked ?? false,
        autoStartContainers: document.getElementById('analysis-container-auto')?.checked ?? false
    };
}

/**
 * Collect reports step configuration
 */
function collectReportsConfig() {
    const wizard = AutomationWizard;
    
    // Get report formats
    wizard.config.reportFormats = Array.from(
        document.querySelectorAll('input[name="report_format"]:checked')
    ).map(el => el.value);
    
    // Get report scope
    wizard.config.reportScope = document.querySelector(
        'input[name="report_scope"]:checked'
    )?.value || 'individual';
    
    // Get report sections
    wizard.config.reportSections = Array.from(
        document.querySelectorAll('input[name="section"]:checked')
    ).map(el => el.value);
    
    // Get report options
    wizard.config.reportOptions = {
        autoOpen: document.getElementById('report-auto-open')?.checked ?? true,
        includeCode: document.getElementById('report-include-code')?.checked ?? false,
        includeSarif: document.getElementById('report-include-sarif')?.checked ?? false
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
 * Update the review summary (step 4)
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
    setText('summary-analysis-profile', 
        config.analysisProfile.charAt(0).toUpperCase() + config.analysisProfile.slice(1));
    setText('summary-tools-count', 
        config.analysisProfile === 'custom' ? config.analysisTools.length : 'All');
    setText('summary-analysis-options', 
        config.analysisOptions.parallel ? 'Parallel' : 'Sequential');
    
    // Reports summary
    setText('summary-report-formats', config.reportFormats.join(', ').toUpperCase());
    setText('summary-report-scope', 
        config.reportScope.charAt(0).toUpperCase() + config.reportScope.slice(1));
    setText('summary-report-sections', config.reportSections.length);
    
    // Job queue preview
    updateJobQueuePreview();
    
    // Estimated time
    const totalJobs = config.templates.length * config.models.length;
    const estMinutes = totalJobs * 5; // Rough estimate: 5 min per job (gen + analysis + report)
    setText('est-duration', formatDuration(estMinutes * 60));
    setText('total-operations', totalJobs * 3); // gen + analysis + report
    setText('total-jobs-badge', `${totalJobs} jobs`);
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
            
            html += `
                <tr>
                    <td>${jobNum}</td>
                    <td><span class="badge bg-azure-lt text-azure">${templateName}</span></td>
                    <td>${modelName}</td>
                    <td><span class="badge bg-green-lt text-green">${config.analysisProfile}</span></td>
                    <td><span class="badge bg-orange-lt text-orange">${config.reportFormats.join(', ')}</span></td>
                    <td class="text-end text-muted">~5 min</td>
                </tr>
            `;
        });
    });
    
    if (html === '') {
        html = `
            <tr>
                <td colspan="6" class="text-center text-muted py-3">
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
    if (!validateStep(1) || !validateStep(2) || !validateStep(3)) {
        showNotification('Please complete all required configuration', 'error');
        return;
    }
    
    // Collect final config
    collectStepConfig(4);
    
    // Prepare payload
    const payload = {
        templates: wizard.config.templates,
        models: wizard.config.models,
        analysis: {
            profile: wizard.config.analysisProfile,
            tools: wizard.config.analysisProfile === 'custom' ? wizard.config.analysisTools : [],
            options: wizard.config.analysisOptions
        },
        reports: {
            formats: wizard.config.reportFormats,
            scope: wizard.config.reportScope,
            sections: wizard.config.reportSections,
            options: wizard.config.reportOptions
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
        
        // Navigate to execution panel
        goToStep(5);
        
        // Start polling for status
        startStatusPolling();
        
        // Start elapsed time counter
        startElapsedTimer();
        
        addActivityLog('Pipeline started', 'info');
        showNotification('Pipeline started successfully', 'success');
        
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
        const response = await fetch(wizard.endpoints.pausePipeline, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ pipeline_id: wizard.state.pipelineId })
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
        const response = await fetch(wizard.endpoints.cancelPipeline, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ pipeline_id: wizard.state.pipelineId })
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
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }
        );
        
        if (!response.ok) {
            throw new Error('Failed to fetch status');
        }
        
        const data = await response.json();
        
        // Update state
        wizard.state.status = data.status;
        wizard.state.currentJob = data.current_job;
        wizard.state.completedJobs = data.completed_jobs || [];
        
        // Update UI
        updateExecutionUI();
        updateMetricsPanel(data);
        
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
            'running': 'bg-primary',
            'paused': 'bg-warning',
            'completed': 'bg-success',
            'failed': 'bg-danger',
            'cancelled': 'bg-secondary'
        };
        statusBadge.className = `badge ${statusColors[wizard.state.status] || 'bg-secondary'}`;
        statusBadge.textContent = wizard.state.status.charAt(0).toUpperCase() + wizard.state.status.slice(1);
    }
    
    // Update overall progress
    const totalJobs = wizard.config.templates.length * wizard.config.models.length * 3; // gen + analysis + report
    const completedCount = wizard.state.completedJobs.length;
    const progress = totalJobs > 0 ? Math.round((completedCount / totalJobs) * 100) : 0;
    
    const progressBar = document.getElementById('overall-progress-bar');
    const progressText = document.getElementById('overall-progress-text');
    
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
    }
    if (progressText) {
        progressText.textContent = `${progress}%`;
    }
    
    // Update current job details
    updateCurrentJobDetails();
    
    // Update completed jobs table
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
    
    // Success rate
    const successRateEl = document.getElementById('metrics-success-rate');
    if (successRateEl && data.success_rate !== undefined) {
        successRateEl.textContent = `${Math.round(data.success_rate)}%`;
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

/**
 * Load available analysis tools
 */
async function loadAnalysisTools() {
    const wizard = AutomationWizard;
    
    try {
        const response = await fetch(wizard.endpoints.getTools);
        const data = await response.json();
        
        if (data.tools) {
            renderToolLists(data.tools);
        }
    } catch (error) {
        console.error('Failed to load tools:', error);
    }
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

/**
 * Select all report sections
 */
function selectAllSections() {
    document.querySelectorAll('input[name="section"]').forEach(el => {
        el.checked = true;
    });
}

/**
 * Select minimal report sections
 */
function selectMinimalSections() {
    document.querySelectorAll('input[name="section"]').forEach(el => {
        el.checked = ['summary', 'security'].includes(el.value);
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
        'analysis': 'fa-search-plus',
        'reports': 'fa-file-alt'
    };
    return icons[stage] || 'fa-cog';
}

/**
 * Get color class for pipeline stage
 */
function getStageColor(stage) {
    const colors = {
        'generation': 'bg-azure-lt text-azure',
        'analysis': 'bg-green-lt text-green',
        'reports': 'bg-orange-lt text-orange'
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
        templates: [],
        models: [],
        analysisProfile: 'comprehensive',
        analysisTools: [],
        analysisOptions: {
            waitForCompletion: true,
            parallel: false,
            autoStartContainers: false
        },
        reportFormats: ['html'],
        reportScope: 'individual',
        reportSections: ['summary', 'security', 'quality', 'performance', 'ai'],
        reportOptions: {
            autoOpen: true,
            includeCode: false,
            includeSarif: false
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
document.addEventListener('DOMContentLoaded', function() {
    // Initialize at step 1
    goToStep(1);
    
    // Load analysis tools
    loadAnalysisTools();
    
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
        
        // Analysis profile toggle
        if (e.target.matches('input[name="analysis_profile"]')) {
            const customSection = document.getElementById('custom-tools-section');
            if (customSection) {
                customSection.style.display = e.target.value === 'custom' ? 'block' : 'none';
            }
        }
        
        // Stage enable/disable toggles
        if (e.target.matches('#enable-generation')) {
            updateStageBadge('gen-status-badge', e.target.checked);
        }
        if (e.target.matches('#enable-analysis')) {
            updateStageBadge('analysis-status-badge', e.target.checked);
        }
        if (e.target.matches('#enable-reports')) {
            updateStageBadge('reports-status-badge', e.target.checked);
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
        // Save settings button
        if (e.target.matches('#save-settings-btn, #save-settings-btn *')) {
            e.preventDefault();
            showSaveSettingsModal();
        }
        // Save settings confirm
        if (e.target.matches('#save-settings-confirm, #save-settings-confirm *')) {
            e.preventDefault();
            saveCurrentSettings();
        }
        // Load settings item
        if (e.target.matches('.load-settings-item, .load-settings-item *')) {
            e.preventDefault();
            const item = e.target.closest('.load-settings-item');
            if (item && item.dataset.settingsId) {
                loadPipelineSettings(item.dataset.settingsId);
            }
        }
        // Manage settings link
        if (e.target.matches('#manage-settings-link, #manage-settings-link *')) {
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
 * Filter templates by search query
 */
function filterTemplates(query) {
    const items = document.querySelectorAll('.template-item');
    const lowerQuery = query.toLowerCase();
    items.forEach(item => {
        const slug = (item.dataset.slug || '').toLowerCase();
        const text = item.textContent.toLowerCase();
        const visible = slug.includes(lowerQuery) || text.includes(lowerQuery);
        item.style.display = visible ? '' : 'none';
    });
}

/**
 * Filter models by search query
 */
function filterModels(query) {
    const items = document.querySelectorAll('.model-item');
    const headers = document.querySelectorAll('.provider-header');
    const lowerQuery = query.toLowerCase();
    
    // Track visible providers
    const visibleProviders = new Set();
    
    items.forEach(item => {
        const slug = (item.dataset.slug || '').toLowerCase();
        const text = item.textContent.toLowerCase();
        const isVisible = slug.includes(lowerQuery) || text.includes(lowerQuery);
        item.style.display = isVisible ? '' : 'none';
        if (isVisible && item.dataset.provider) {
            visibleProviders.add(item.dataset.provider);
        }
    });
    
    // Show/hide provider headers
    headers.forEach(header => {
        header.style.display = visibleProviders.has(header.dataset.provider) ? '' : 'none';
    });
}

/**
 * Filter existing apps by search query
 */
function filterExistingApps(query) {
    const items = document.querySelectorAll('.existing-app-item');
    const lowerQuery = query.toLowerCase();
    items.forEach(item => {
        const model = (item.dataset.model || '').toLowerCase();
        const text = item.textContent.toLowerCase();
        item.style.display = (model.includes(lowerQuery) || text.includes(lowerQuery)) ? '' : 'none';
    });
}

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
 * Show the manage settings modal
 */
function showManageSettingsModal() {
    // Load settings list first
    fetch('/automation/api/settings')
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
    
    // Gather current config
    const config = {
        mode: document.querySelector('input[name="generation_mode"]:checked')?.value || 'generate',
        templates: Array.from(document.querySelectorAll('input[name="template"]:checked')).map(cb => cb.value),
        models: Array.from(document.querySelectorAll('input[name="model"]:checked')).map(cb => cb.value),
        existingApps: Array.from(document.querySelectorAll('input[name="existing_app"]:checked')).map(cb => cb.value),
    };
    
    fetch('/automation/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, config, is_default: isDefault }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('saveSettingsModal'));
                if (modal) modal.hide();
                showNotification('Settings saved successfully', 'success');
                // Refresh the dropdown
                setTimeout(() => location.reload(), 500);
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
    fetch(`/automation/api/settings/${settingsId}`)
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
    
    // Update summaries
    collectGenerationConfig();
    updateExistingAppsSummary();
}

/**
 * Set a settings preset as default
 */
function setDefaultSettings(settingsId) {
    fetch(`/automation/api/settings/${settingsId}/default`, { method: 'POST' })
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
    
    fetch(`/automation/api/settings/${settingsId}`, { method: 'DELETE' })
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
window.selectAllSections = selectAllSections;
window.selectMinimalSections = selectMinimalSections;
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
