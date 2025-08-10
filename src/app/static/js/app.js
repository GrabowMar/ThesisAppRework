// Custom JavaScript for ThesisApp

// HTMX configuration
document.addEventListener('DOMContentLoaded', function() {
    // Configure HTMX
    htmx.config.defaultSwapStyle = 'outerHTML';
    htmx.config.defaultSwapDelay = 0;
    htmx.config.defaultSettleDelay = 100;
    
    // Global HTMX event listeners
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        // Show loading indicators
        const btn = evt.detail.elt;
        if (btn.tagName === 'BUTTON') {
            btn.disabled = true;
            const spinner = btn.querySelector('.loading-spinner');
            if (spinner) {
                spinner.style.display = 'inline-block';
            }
        }
    });
    
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        // Hide loading indicators
        const btn = evt.detail.elt;
        if (btn.tagName === 'BUTTON') {
            btn.disabled = false;
            const spinner = btn.querySelector('.loading-spinner');
            if (spinner) {
                spinner.style.display = 'none';
            }
        }
    });
    
    document.body.addEventListener('htmx:responseError', function(evt) {
        // Handle errors
        console.error('HTMX Error:', evt.detail);
        showErrorMessage('Request failed. Please try again.');
    });
});

// Utility functions
function showErrorMessage(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function showSuccessMessage(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Copy to clipboard function
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showSuccessMessage('Copied to clipboard!');
    }).catch(function(err) {
        console.error('Failed to copy: ', err);
        showErrorMessage('Failed to copy to clipboard');
    });
}

// Format numbers
function formatNumber(num) {
    return new Intl.NumberFormat().format(num);
}

// Format file sizes
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Auto-refresh functionality
function startAutoRefresh(selector, interval = 30000) {
    setInterval(() => {
        const element = document.querySelector(selector);
        if (element && element.hasAttribute('hx-get')) {
            htmx.trigger(element, 'refresh');
        }
    }, interval);
}

// Form validation helpers
function validateForm(formElement) {
    const inputs = formElement.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}
