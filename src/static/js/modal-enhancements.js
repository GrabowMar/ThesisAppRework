/**
 * Enhanced Security Test Modal JavaScript
 * Handles dynamic interactions for the comprehensive test creation modal
 */

// Debug function to test JavaScript loading
window.modalEnhancementsLoaded = true;
console.log('Modal enhancements JavaScript loaded successfully');

// Log all exported functions for debugging
window.addEventListener('load', function() {
    console.log('Available functions:', {
        loadAppDetails: typeof window.loadAppDetails,
        toggleTestOptions: typeof window.toggleTestOptions,
        handleTestResponse: typeof window.handleTestResponse,
        showTestDetails: typeof window.showTestDetails,
        showTestResults: typeof window.showTestResults,
        cancelTest: typeof window.cancelTest,
        restartTest: typeof window.restartTest,
        deleteTest: typeof window.deleteTest,
        showCreateTestModal: typeof window.showCreateTestModal
    });
});

// Simple notification system
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Handle test start (before request)
function handleTestStart(event) {
    const startBtn = document.getElementById('startTestBtn');
    const loadingSpinner = document.getElementById('test-loading');
    
    // Validate form first
    const form = document.getElementById('comprehensiveTestForm');
    const appSelect = document.getElementById('appSelect');
    
    if (!appSelect.value) {
        event.preventDefault();
        showNotification('Please select an application first.', 'error');
        return false;
    }
    
    // Check if at least one test type is selected
    const testTypes = form.querySelectorAll('input[name="test_types"]:checked');
    if (testTypes.length === 0) {
        event.preventDefault();
        showNotification('Please select at least one test type.', 'error');
        return false;
    }
    
    // Show loading state
    if (startBtn) {
        startBtn.disabled = true;
    }
    
    if (loadingSpinner) {
        loadingSpinner.classList.remove('d-none');
    }
    
    return true;
}

// Test response handling for HTMX
function handleTestResponse(event) {
    const startBtn = document.getElementById('startTestBtn');
    const loadingSpinner = document.getElementById('test-loading');
    
    if (startBtn) {
        startBtn.disabled = false;
    }
    
    if (loadingSpinner) {
        loadingSpinner.classList.add('d-none');
    }
    
    // Handle response based on status
    if (event.detail.xhr.status === 200) {
        // Success - close modal and show success message
        const modal = bootstrap.Modal.getInstance(document.getElementById('newTestModal'));
        if (modal) {
            modal.hide();
        }
        
        showNotification('Test launched successfully!', 'success');
    } else {
        // Error - show error message
        showNotification('Failed to launch test. Please try again.', 'error');
    }
}

// Application details management
function loadAppDetails(appId) {
    const selectElement = document.getElementById('appSelect');
    const detailsContainer = document.getElementById('selected-app-details');
    
    if (!appId) {
        detailsContainer.classList.add('d-none');
        return;
    }
    
    const option = selectElement.querySelector(`option[value="${appId}"]`);
    if (option) {
        // Extract data attributes
        const provider = option.dataset.provider || 'Unknown';
        const model = option.dataset.model || 'Unknown';
        const backendPort = option.dataset.backendPort || 'N/A';
        const frontendPort = option.dataset.frontendPort || 'N/A';
        
        // Update display elements
        document.getElementById('app-provider').textContent = provider.charAt(0).toUpperCase() + provider.slice(1);
        document.getElementById('app-model').textContent = model.split('_').pop() || model;
        document.getElementById('app-backend-port').textContent = backendPort;
        document.getElementById('app-frontend-port').textContent = frontendPort;
        
        // Show details with animation
        detailsContainer.classList.remove('d-none');
    }
}

// Test options toggle functionality
function toggleTestOptions(testType, isEnabled) {
    const optionsSection = document.getElementById(`${testType}-options`);
    
    if (!optionsSection) return;
    
    if (isEnabled) {
        optionsSection.classList.remove('d-none');
        
        // Auto-select some default tools for security tests
        if (testType === 'security') {
            const defaultTools = ['bandit', 'safety', 'pylint', 'eslint', 'retire', 'npm-audit'];
            defaultTools.forEach(tool => {
                const checkbox = document.getElementById(`tool-${tool}`);
                if (checkbox && !checkbox.checked) {
                    checkbox.checked = true;
                }
            });
        }
    } else {
        optionsSection.classList.add('d-none');
    }
}

// Form validation and submission handling
function handleTestResponse(event) {
    const response = event.detail.xhr.response;
    const statusCode = event.detail.xhr.status;
    
    if (statusCode === 200) {
        // Success - close modal and show success message
        const modal = bootstrap.Modal.getInstance(document.getElementById('newTestModal'));
        if (modal) {
            modal.hide();
        }
        
        showNotification('Test started successfully!', 'success');
        
        // Refresh the test history or results
        if (typeof refreshTestHistory === 'function') {
            refreshTestHistory();
        }
    } else {
        // Error handling
        console.error('Test submission failed:', response);
        showNotification('Failed to start test. Please try again.', 'error');
    }
    
    // Re-enable the submit button
    const submitBtn = document.getElementById('startTestBtn');
    const loadingSpinner = document.getElementById('test-loading');
    
    if (submitBtn) {
        submitBtn.disabled = false;
    }
    
    if (loadingSpinner) {
        loadingSpinner.classList.add('d-none');
    }
}

// Form submission preparation
function prepareFormSubmission() {
    const form = document.getElementById('comprehensiveTestForm');
    const submitBtn = document.getElementById('startTestBtn');
    const loadingSpinner = document.getElementById('test-loading');
    
    if (submitBtn) {
        submitBtn.disabled = true;
    }
    
    if (loadingSpinner) {
        loadingSpinner.classList.remove('d-none');
    }
    
    // Validate form before submission
    if (!validateTestForm()) {
        if (submitBtn) {
            submitBtn.disabled = false;
        }
        if (loadingSpinner) {
            loadingSpinner.classList.add('d-none');
        }
        return false;
    }
    
    return true;
}

// Form validation
function validateTestForm() {
    const appSelect = document.getElementById('appSelect');
    const testTypes = document.querySelectorAll('input[name="test_types"]:checked');
    
    // Check if application is selected
    if (!appSelect.value) {
        showNotification('Please select an application to test.', 'warning');
        appSelect.focus();
        return false;
    }
    
    // Check if at least one test type is selected
    if (testTypes.length === 0) {
        showNotification('Please select at least one test type.', 'warning');
        return false;
    }
    
    // Validate security tools if security test is selected
    const securityTest = document.getElementById('securityAnalysis');
    if (securityTest && securityTest.checked) {
        const securityTools = document.querySelectorAll('input[name="security_tools"]:checked');
        if (securityTools.length === 0) {
            showNotification('Please select at least one security tool.', 'warning');
            return false;
        }
    }
    
    return true;
}

// Notification system
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    
    notification.innerHTML = `
        <i class="fas fa-${getIconForType(type)} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

function getIconForType(type) {
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-triangle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Initialize modal when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add form submission handler
    const form = document.getElementById('comprehensiveTestForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!prepareFormSubmission()) {
                e.preventDefault();
                return false;
            }
        });
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl + Enter to submit form when modal is open
        if (e.ctrlKey && e.key === 'Enter') {
            const modal = document.getElementById('newTestModal');
            if (modal && modal.classList.contains('show')) {
                const submitBtn = document.getElementById('startTestBtn');
                if (submitBtn && !submitBtn.disabled) {
                    submitBtn.click();
                }
            }
        }
    });
});

// Reset modal when it's closed
document.addEventListener('hidden.bs.modal', function(e) {
    if (e.target.id === 'newTestModal') {
        // Reset form
        const form = document.getElementById('comprehensiveTestForm');
        if (form) {
            form.reset();
        }
        
        // Hide app details
        const detailsContainer = document.getElementById('selected-app-details');
        if (detailsContainer) {
            detailsContainer.classList.add('d-none');
        }
        
        // Hide all test options
        const optionsSections = document.querySelectorAll('.test-options-section');
        optionsSections.forEach(section => {
            section.classList.add('d-none');
        });
        
        // Show security options by default (since security is checked by default)
        const securityOptions = document.getElementById('security-options');
        if (securityOptions) {
            securityOptions.classList.remove('d-none');
        }
        
        // Re-enable submit button
        const submitBtn = document.getElementById('startTestBtn');
        if (submitBtn) {
            submitBtn.disabled = false;
        }
        
        // Hide loading spinner
        const loadingSpinner = document.getElementById('test-loading');
        if (loadingSpinner) {
            loadingSpinner.classList.add('d-none');
        }
    }
});

// Show test details modal or redirect to test details page
function showTestDetails(testId) {
    if (!testId) {
        console.error('Test ID is required for showTestDetails');
        showNotification('Invalid test ID', 'error');
        return;
    }
    
    console.log(`Showing details for test: ${testId}`);
    
    // Try to show details in a modal first
    showTestDetailsModal(testId);
}

// Show test details in a modal
function showTestDetailsModal(testId) {
    // Create modal HTML
    const modalHTML = `
        <div class="modal fade" id="testDetailsModal" tabindex="-1" aria-labelledby="testDetailsModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="testDetailsModalLabel">
                            <i class="fas fa-info-circle me-2"></i>Test Details
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="text-center">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">Loading test details...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if present
    const existingModal = document.getElementById('testDetailsModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('testDetailsModal'));
    modal.show();
    
    // Load test details via HTMX or fetch
    fetch(`/testing/api/test/${testId}/details`)
        .then(response => response.text())
        .then(html => {
            const modalBody = document.querySelector('#testDetailsModal .modal-body');
            if (modalBody) {
                modalBody.innerHTML = html;
            }
        })
        .catch(error => {
            console.error('Error loading test details:', error);
            const modalBody = document.querySelector('#testDetailsModal .modal-body');
            if (modalBody) {
                modalBody.innerHTML = `
                    <div class="alert alert-danger">
                        <h6>Error Loading Test Details</h6>
                        <p>Unable to load details for test ${testId}.</p>
                        <p class="mb-0"><small>Error: ${error.message}</small></p>
                    </div>
                `;
            }
        });
    
    // Clean up modal when hidden
    document.getElementById('testDetailsModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// Show test results
function showTestResults(testId) {
    if (!testId) {
        console.error('Test ID is required for showTestResults');
        showNotification('Invalid test ID', 'error');
        return;
    }
    
    console.log(`Showing results for test: ${testId}`);
    
    // Create modal HTML for results
    const modalHTML = `
        <div class="modal fade" id="testResultsModal" tabindex="-1" aria-labelledby="testResultsModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="testResultsModalLabel">
                            <i class="fas fa-chart-bar me-2"></i>Test Results
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="text-center">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">Loading test results...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if present
    const existingModal = document.getElementById('testResultsModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('testResultsModal'));
    modal.show();
    
    // Load test results
    fetch(`/testing/api/test/${testId}/results`)
        .then(response => response.text())
        .then(html => {
            const modalBody = document.querySelector('#testResultsModal .modal-body');
            if (modalBody) {
                modalBody.innerHTML = html;
            }
        })
        .catch(error => {
            console.error('Error loading test results:', error);
            const modalBody = document.querySelector('#testResultsModal .modal-body');
            if (modalBody) {
                modalBody.innerHTML = `
                    <div class="alert alert-danger">
                        <h6>Error Loading Test Results</h6>
                        <p>Unable to load results for test ${testId}.</p>
                        <p class="mb-0"><small>Error: ${error.message}</small></p>
                    </div>
                `;
            }
        });
    
    // Clean up modal when hidden
    document.getElementById('testResultsModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// Cancel test
function cancelTest(testId, buttonElement) {
    if (!testId) {
        console.error('Test ID is required for cancelTest');
        showNotification('Invalid test ID', 'error');
        return;
    }
    
    if (!confirm('Are you sure you want to cancel this test?')) {
        return;
    }
    
    console.log(`Cancelling test: ${testId}`);
    
    // Disable button during request
    if (buttonElement) {
        buttonElement.disabled = true;
        buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cancelling...';
    }
    
    fetch(`/testing/api/test/${testId}/cancel`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Test cancelled successfully', 'success');
            // Refresh the page or update the UI
            location.reload();
        } else {
            showNotification(data.error || 'Failed to cancel test', 'error');
        }
    })
    .catch(error => {
        console.error('Error cancelling test:', error);
        showNotification('Error cancelling test', 'error');
    })
    .finally(() => {
        if (buttonElement) {
            buttonElement.disabled = false;
            buttonElement.innerHTML = '<i class="fas fa-stop"></i> <span class="d-none d-xl-inline ml-1">Cancel</span>';
        }
    });
}

// Restart test
function restartTest(testId, buttonElement) {
    if (!testId) {
        console.error('Test ID is required for restartTest');
        showNotification('Invalid test ID', 'error');
        return;
    }
    
    if (!confirm('Are you sure you want to restart this test?')) {
        return;
    }
    
    console.log(`Restarting test: ${testId}`);
    
    // Disable button during request
    if (buttonElement) {
        buttonElement.disabled = true;
        buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restarting...';
    }
    
    fetch(`/testing/api/test/${testId}/restart`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Test restarted successfully', 'success');
            // Refresh the page or update the UI
            location.reload();
        } else {
            showNotification(data.error || 'Failed to restart test', 'error');
        }
    })
    .catch(error => {
        console.error('Error restarting test:', error);
        showNotification('Error restarting test', 'error');
    })
    .finally(() => {
        if (buttonElement) {
            buttonElement.disabled = false;
            buttonElement.innerHTML = '<i class="fas fa-redo"></i> <span class="d-none d-xl-inline ml-1">Restart</span>';
        }
    });
}

// Delete test
function deleteTest(testId, buttonElement) {
    if (!testId) {
        console.error('Test ID is required for deleteTest');
        showNotification('Invalid test ID', 'error');
        return;
    }
    
    if (!confirm('Are you sure you want to delete this test? This action cannot be undone.')) {
        return;
    }
    
    console.log(`Deleting test: ${testId}`);
    
    // Disable button during request
    if (buttonElement) {
        buttonElement.disabled = true;
        buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...';
    }
    
    fetch(`/testing/api/test/${testId}/delete`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Test deleted successfully', 'success');
            // Refresh the page or update the UI
            location.reload();
        } else {
            showNotification(data.error || 'Failed to delete test', 'error');
        }
    })
    .catch(error => {
        console.error('Error deleting test:', error);
        showNotification('Error deleting test', 'error');
    })
    .finally(() => {
        if (buttonElement) {
            buttonElement.disabled = false;
            buttonElement.innerHTML = '<i class="fas fa-trash"></i> <span class="d-none d-xl-inline ml-1">Delete</span>';
        }
    });
}

// Show create test modal
function showCreateTestModal() {
    console.log('Showing create test modal');
    
    // Try to find and show the new test modal
    const modal = document.getElementById('newTestModal');
    if (modal) {
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    } else {
        // If modal doesn't exist, load it via HTMX
        fetch('/testing/api/new-test-form')
            .then(response => response.text())
            .then(html => {
                // Create a temporary container
                const container = document.createElement('div');
                container.innerHTML = html;
                
                // Add to page
                document.body.appendChild(container);
                
                // Show the modal
                const newModal = container.querySelector('#newTestModal');
                if (newModal) {
                    const bootstrapModal = new bootstrap.Modal(newModal);
                    bootstrapModal.show();
                    
                    // Clean up when modal is hidden
                    newModal.addEventListener('hidden.bs.modal', function() {
                        container.remove();
                    });
                } else {
                    showNotification('Error loading test creation form', 'error');
                    container.remove();
                }
            })
            .catch(error => {
                console.error('Error loading create test modal:', error);
                showNotification('Error loading test creation form', 'error');
            });
    }
}

// Export functions for global access
window.loadAppDetails = loadAppDetails;
window.toggleTestOptions = toggleTestOptions;
window.handleTestResponse = handleTestResponse;
window.showTestDetails = showTestDetails;
window.showTestResults = showTestResults;
window.cancelTest = cancelTest;
window.restartTest = restartTest;
window.deleteTest = deleteTest;
window.showCreateTestModal = showCreateTestModal;
