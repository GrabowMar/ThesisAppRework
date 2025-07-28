/**
 * Enhanced Error Handling Utilities for React Components and HTMX
 * Provides consistent error messaging and retry mechanisms
 */

// Enhanced error handling for React components
export const ErrorHandler = {
  // Parse and format error responses
  parseError: (error, defaultMessage = "Request failed. Please try again.") => {
    // Network error (no response)
    if (!error.response) {
      return {
        type: 'network',
        message: 'Network error. Please check your connection.',
        retryable: true,
        details: error.message
      };
    }

    const status = error.response?.status;
    const data = error.response?.data;

    // Status-specific error messages
    switch (status) {
      case 400:
        return {
          type: 'validation',
          message: data?.message || 'Invalid request. Please check your input.',
          retryable: false,
          errors: data?.errors || {},
          details: `Bad Request (${status})`
        };

      case 401:
        return {
          type: 'auth',
          message: 'Authentication required. Please log in again.',
          retryable: false,
          details: `Unauthorized (${status})`
        };

      case 403:
        return {
          type: 'permission',
          message: 'Access denied. You don\'t have permission for this action.',
          retryable: false,
          details: `Forbidden (${status})`
        };

      case 404:
        return {
          type: 'notfound',
          message: 'Resource not found.',
          retryable: false,
          details: `Not Found (${status})`
        };

      case 429:
        return {
          type: 'ratelimit',
          message: 'Too many requests. Please wait and try again.',
          retryable: true,
          retryAfter: error.response.headers['retry-after'] || 30,
          details: `Rate Limited (${status})`
        };

      case 500:
        return {
          type: 'server',
          message: 'Server error. Please try again in a moment.',
          retryable: true,
          details: `Internal Server Error (${status})`
        };

      case 502:
      case 503:
      case 504:
        return {
          type: 'service',
          message: 'Service temporarily unavailable. Please try again.',
          retryable: true,
          retryAfter: 10,
          details: `Service Unavailable (${status})`
        };

      default:
        return {
          type: 'unknown',
          message: data?.message || defaultMessage,
          retryable: status >= 500,
          details: `HTTP ${status}`
        };
    }
  },

  // Create retry function with exponential backoff
  createRetryHandler: (originalFunction, maxRetries = 3, baseDelay = 1000) => {
    return async (...args) => {
      let lastError;
      
      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          return await originalFunction(...args);
        } catch (error) {
          lastError = error;
          const parsedError = ErrorHandler.parseError(error);
          
          // Don't retry if error is not retryable
          if (!parsedError.retryable || attempt === maxRetries) {
            throw error;
          }

          // Calculate delay with exponential backoff
          const delay = parsedError.retryAfter 
            ? parsedError.retryAfter * 1000 
            : baseDelay * Math.pow(2, attempt);

          // Show retry notification
          ErrorHandler.showRetryNotification(attempt + 1, delay / 1000);
          
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
      
      throw lastError;
    };
  },

  // Show toast notification for retry attempts
  showRetryNotification: (attempt, delay) => {
    const toast = document.createElement('div');
    toast.className = 'toast info show';
    toast.innerHTML = `
      <div>
        <strong>Retry Attempt ${attempt}</strong><br>
        Retrying in ${delay} seconds...
      </div>
    `;

    const container = document.querySelector('.toast-container') || (() => {
      const newContainer = document.createElement('div');
      newContainer.className = 'toast-container';
      document.body.appendChild(newContainer);
      return newContainer;
    })();

    container.appendChild(toast);

    // Remove toast after delay + 1 second
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, (delay + 1) * 1000);
  },

  // Enhanced React hook for API calls with error handling
  useApiCall: (apiFunction) => {
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState(null);
    const [data, setData] = React.useState(null);

    const execute = React.useCallback(async (...args) => {
      setLoading(true);
      setError(null);

      try {
        const result = await apiFunction(...args);
        setData(result);
        return result;
      } catch (err) {
        const parsedError = ErrorHandler.parseError(err);
        setError(parsedError);
        throw parsedError;
      } finally {
        setLoading(false);
      }
    }, [apiFunction]);

    const retry = React.useCallback(() => {
      if (error && error.retryable) {
        execute();
      }
    }, [error, execute]);

    return { loading, error, data, execute, retry };
  }
};

// Enhanced form handling utilities
export const FormHandler = {
  // Create enhanced form submit handler
  createSubmitHandler: (apiCall, options = {}) => {
    const {
      onSuccess = () => {},
      onError = () => {},
      validateForm = () => true,
      clearErrors = () => {},
      setLoading = () => {},
      setErrors = () => {}
    } = options;

    return async (e) => {
      e.preventDefault();
      
      // Clear previous errors
      clearErrors();
      setErrors({});
      
      // Validate form
      const validation = validateForm(e.target);
      if (!validation.valid) {
        setErrors(validation.errors);
        return;
      }

      setLoading(true);

      try {
        const result = await apiCall(e);
        onSuccess(result);
      } catch (error) {
        const parsedError = ErrorHandler.parseError(error);
        
        // Set field-specific errors if available
        if (parsedError.errors) {
          setErrors(parsedError.errors);
        } else {
          // Set general error
          setErrors({ general: parsedError.message });
        }
        
        onError(parsedError);
      } finally {
        setLoading(false);
      }
    };
  },

  // Validate common form fields
  validateField: (name, value, rules = {}) => {
    const errors = [];

    if (rules.required && !value.trim()) {
      errors.push(`${name} is required`);
    }

    if (rules.email && value && !/\S+@\S+\.\S+/.test(value)) {
      errors.push('Please enter a valid email address');
    }

    if (rules.minLength && value.length < rules.minLength) {
      errors.push(`${name} must be at least ${rules.minLength} characters`);
    }

    if (rules.password && value && value.length < 8) {
      errors.push('Password must be at least 8 characters');
    }

    return errors;
  }
};

// HTMX Error Handling Extensions
export const HTMXErrorHandler = {
  // Initialize enhanced HTMX error handling
  init: () => {
    // Network status indicator
    const createNetworkIndicator = () => {
      const indicator = document.createElement('div');
      indicator.className = 'network-status';
      indicator.id = 'network-status';
      document.body.appendChild(indicator);
      return indicator;
    };

    const networkIndicator = createNetworkIndicator();

    // Enhanced error handler for HTMX requests
    document.body.addEventListener('htmx:responseError', (e) => {
      const status = e.detail.xhr.status;
      const errorData = ErrorHandler.parseError({ response: { status, data: {} } });
      
      // Show network indicator for service errors
      if (errorData.type === 'service' || errorData.type === 'network') {
        networkIndicator.textContent = errorData.message;
        networkIndicator.className = `network-status ${errorData.type} show`;
        setTimeout(() => networkIndicator.classList.remove('show'), 5000);
      }
    });

    // Network monitoring
    window.addEventListener('online', () => {
      networkIndicator.textContent = 'Connection restored';
      networkIndicator.className = 'network-status online show';
      setTimeout(() => networkIndicator.classList.remove('show'), 3000);
    });

    window.addEventListener('offline', () => {
      networkIndicator.textContent = 'Connection lost';
      networkIndicator.className = 'network-status offline show';
    });
  }
};

// Initialize on page load
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    HTMXErrorHandler.init();
  });
}
