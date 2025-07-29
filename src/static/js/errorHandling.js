/* HTMX and Hyperscript Error Handling */
/* Global error handling for the application */

// Enhanced error handling for HTMX requests
document.addEventListener('DOMContentLoaded', function() {
    
    // Global HTMX configuration
    htmx.config.timeout = 10000;
    htmx.config.defaultSwapStyle = 'innerHTML';
    htmx.config.historyCacheSize = 0;
    
    // Loading state management
    let loadingElements = new Set();
    
    // Show loading state
    function showLoading(element) {
        if (element && !loadingElements.has(element)) {
            loadingElements.add(element);
            element.classList.add('htmx-request');
            
            // Add spinner for buttons
            if (element.tagName === 'BUTTON') {
                const spinner = document.createElement('span');
                spinner.className = 'loading-spinner htmx-indicator';
                element.insertBefore(spinner, element.firstChild);
                element.disabled = true;
            }
        }
    }
    
    // Hide loading state
    function hideLoading(element) {
        if (element && loadingElements.has(element)) {
            loadingElements.delete(element);
            element.classList.remove('htmx-request');
            
            // Remove spinner from buttons
            if (element.tagName === 'BUTTON') {
                const spinner = element.querySelector('.htmx-indicator');
                if (spinner) {
                    spinner.remove();
                }
                element.disabled = false;
            }
        }
    }
    
    // HTMX event listeners
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        showLoading(evt.detail.elt);
    });
    
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        hideLoading(evt.detail.elt);
    });
    
    // Enhanced error handling
    document.body.addEventListener('htmx:responseError', function(evt) {
        const target = evt.detail.target;
        const status = evt.detail.xhr.status;
        const response = evt.detail.xhr.responseText;
        
        let errorMessage = getErrorMessage(status);
        let errorHtml = createErrorHtml(errorMessage, status, target);
        
        // Try to parse error response
        try {
            const errorData = JSON.parse(response);
            if (errorData.error) {
                errorMessage = errorData.error;
            }
            if (errorData.retry_after) {
                errorHtml = createRetryableErrorHtml(errorMessage, errorData.retry_after, target);
            }
        } catch (e) {
            // Use default error message
        }
        
        target.innerHTML = errorHtml;
        hideLoading(evt.detail.elt);
    });
    
    // Timeout handling
    document.body.addEventListener('htmx:timeout', function(evt) {
        const target = evt.detail.target;
        const errorHtml = createRetryableErrorHtml(
            'Request timed out. Please try again.',
            5,
            target
        );
        target.innerHTML = errorHtml;
        hideLoading(evt.detail.elt);
    });
    
    // Network error handling
    document.body.addEventListener('htmx:sendError', function(evt) {
        const target = evt.detail.target;
        const errorHtml = createRetryableErrorHtml(
            'Network error. Please check your connection.',
            10,
            target
        );
        target.innerHTML = errorHtml;
        hideLoading(evt.detail.elt);
    });
    
    // Success feedback
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        // Check for success messages and auto-dismiss
        const successAlerts = evt.detail.target.querySelectorAll('.alert-success');
        successAlerts.forEach(alert => {
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.style.opacity = '0';
                    setTimeout(() => alert.remove(), 300);
                }
            }, 3000);
        });
    });
    
    // Helper functions
    function getErrorMessage(status) {
        const errorMessages = {
            0: 'Network error. Please check your connection.',
            400: 'Invalid request. Please check your input.',
            401: 'Authentication required. Please refresh the page.',
            403: 'Access denied. You do not have permission.',
            404: 'Resource not found.',
            429: 'Too many requests. Please wait before trying again.',
            500: 'Server error. Please try again later.',
            502: 'Service unavailable. Please try again later.',
            503: 'Service temporarily unavailable.',
            504: 'Request timeout. Please try again.'
        };
        
        return errorMessages[status] || `Error ${status}. Please try again.`;
    }
    
    function createErrorHtml(message, status, target) {
        const alertClass = getAlertClass(status);
        return `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                <strong>Error:</strong> ${message}
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
    }
    
    function createRetryableErrorHtml(message, retryAfter, target) {
        const retryId = 'retry_' + Date.now();
        return `
            <div class="alert alert-warning alert-dismissible fade show" role="alert">
                <strong>Error:</strong> ${message}
                <button type="button" class="btn btn-sm btn-outline-primary ml-2" 
                        onclick="retryRequest(this)" 
                        data-retry-target="${target.id || ''}"
                        id="${retryId}">
                    <span class="htmx-indicator loading-spinner"></span>
                    Retry
                </button>
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
    }
    
    function getAlertClass(status) {
        if (status >= 400 && status < 500) {
            return 'alert-warning';
        } else if (status >= 500) {
            return 'alert-danger';
        }
        return 'alert-info';
    }
    
    // Global retry function
    window.retryRequest = function(button) {
        const targetId = button.dataset.retryTarget;
        let targetElement;
        
        if (targetId) {
            targetElement = document.getElementById(targetId);
        } else {
            targetElement = button.closest('[hx-get], [hx-post], [hx-put], [hx-delete]');
        }
        
        if (targetElement) {
            // Find the original HTMX element
            const htmxElement = targetElement.querySelector('[hx-get], [hx-post], [hx-put], [hx-delete]') || targetElement;
            
            if (htmxElement) {
                showLoading(button);
                htmx.trigger(htmxElement, 'click');
            }
        }
    };
    
    // Auto-dismiss alerts
    function autoDismissAlerts() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            if (!alert.dataset.autoDismissed) {
                alert.dataset.autoDismissed = 'true';
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.style.opacity = '0';
                        setTimeout(() => alert.remove(), 300);
                    }
                }, 5000);
            }
        });
    }
    
    // Run auto-dismiss on page load and after HTMX swaps
    autoDismissAlerts();
    document.body.addEventListener('htmx:afterSwap', autoDismissAlerts);
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(evt) {
        const dropdowns = document.querySelectorAll('.dropdown-menu.show');
        dropdowns.forEach(dropdown => {
            const toggle = dropdown.previousElementSibling;
            if (!dropdown.contains(evt.target) && !toggle.contains(evt.target)) {
                dropdown.classList.remove('show');
                toggle.setAttribute('aria-expanded', 'false');
            }
        });
    });
    
    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        document.addEventListener('htmx:afterSwap', function() {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        });
    }
    
    console.log('HTMX error handling initialized');
});
