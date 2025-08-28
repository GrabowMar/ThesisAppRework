/**
 * API Client and Backend Communication
 * Centralized API handling with error management and loading states
 */

class APIClient {
  constructor(baseURL = '') {
    this.baseURL = baseURL;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    };
    this.requestInterceptors = [];
    this.responseInterceptors = [];
  }

  // Request interceptors for auth, logging, etc.
  addRequestInterceptor(interceptor) {
    this.requestInterceptors.push(interceptor);
  }

  addResponseInterceptor(interceptor) {
    this.responseInterceptors.push(interceptor);
  }

  async request(url, options = {}) {
    const config = {
      method: 'GET',
      headers: { ...this.defaultHeaders, ...options.headers },
      ...options
    };

    // Apply request interceptors
    for (const interceptor of this.requestInterceptors) {
      await interceptor(config);
    }

    const fullURL = url.startsWith('http') ? url : `${this.baseURL}${url}`;

    try {
      const response = await fetch(fullURL, config);
      
      // Apply response interceptors
      for (const interceptor of this.responseInterceptors) {
        await interceptor(response);
      }

      if (!response.ok) {
        throw new APIError(response.statusText, response.status, response);
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      
      return await response.text();
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network Error', 0, null, error);
    }
  }

  // Convenience methods
  get(url, options = {}) {
    return this.request(url, { ...options, method: 'GET' });
  }

  post(url, data, options = {}) {
    return this.request(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  put(url, data, options = {}) {
    return this.request(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  delete(url, options = {}) {
    return this.request(url, { ...options, method: 'DELETE' });
  }

  // File upload helper
  uploadFile(url, file, onProgress = null) {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);

      const xhr = new XMLHttpRequest();
      
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            onProgress(percentComplete);
          }
        });
      }

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch {
            resolve(xhr.responseText);
          }
        } else {
          reject(new APIError(xhr.statusText, xhr.status));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new APIError('Upload failed', 0));
      });

      xhr.open('POST', url.startsWith('http') ? url : `${this.baseURL}${url}`);
      xhr.send(formData);
    });
  }
}

class APIError extends Error {
  constructor(message, status, response = null, originalError = null) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.response = response;
    this.originalError = originalError;
  }
}

// Application-specific API endpoints
class AppAPI extends APIClient {
  constructor() {
    super('/api');
    
    // Add default interceptors
    this.addRequestInterceptor(this.addCSRFToken);
    this.addResponseInterceptor(this.handleCommonErrors);
  }

  async addCSRFToken(config) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken;
    }
  }

  async handleCommonErrors(response) {
    if (response.status === 401) {
      window.location.href = '/login';
    } else if (response.status === 403) {
      window.App?.showToast('Access denied', 'error');
    } else if (response.status >= 500) {
      window.App?.showToast('Server error occurred', 'error');
    }
  }

  // Model management endpoints
  async getModels(filters = {}) {
    const params = new URLSearchParams(filters);
    return this.get(`/models?${params}`);
  }

  async getModel(slug) {
    return this.get(`/models/${encodeURIComponent(slug)}`);
  }

  async updateModel(slug, data) {
    return this.put(`/models/${encodeURIComponent(slug)}`, data);
  }

  async deleteModel(slug) {
    return this.delete(`/models/${encodeURIComponent(slug)}`);
  }

  // Application endpoints
  async getApplications(modelSlug, filters = {}) {
    const params = new URLSearchParams(filters);
    return this.get(`/models/${encodeURIComponent(modelSlug)}/applications?${params}`);
  }

  async getApplication(modelSlug, appNumber) {
    return this.get(`/models/${encodeURIComponent(modelSlug)}/applications/${appNumber}`);
  }

  async deleteApplication(modelSlug, appNumber) {
    return this.delete(`/models/${encodeURIComponent(modelSlug)}/applications/${appNumber}`);
  }

  // Analysis endpoints
  async startAnalysis(modelSlug, appNumber, analysisType, options = {}) {
    return this.post('/analysis/start', {
      model_slug: modelSlug,
      app_number: appNumber,
      analysis_type: analysisType,
      ...options
    });
  }

  async getAnalysisStatus(taskId) {
    return this.get(`/analysis/status/${taskId}`);
  }

  async getAnalysisResults(modelSlug, appNumber, analysisType) {
    return this.get(`/analysis/results/${encodeURIComponent(modelSlug)}/${appNumber}/${analysisType}`);
  }

  async cancelAnalysis(taskId) {
    return this.post(`/analysis/cancel/${taskId}`);
  }

  // Batch operations
  async startBatchAnalysis(config) {
    return this.post('/batch/start', config);
  }

  async getBatchStatus(batchId) {
    return this.get(`/batch/status/${batchId}`);
  }

  async cancelBatch(batchId) {
    return this.post(`/batch/cancel/${batchId}`);
  }

  // Export endpoints
  async exportResults(modelSlug, appNumber, format = 'json') {
    return this.get(`/export/${encodeURIComponent(modelSlug)}/${appNumber}/${format}`);
  }

  async exportBulk(selection, format = 'json') {
    return this.post('/export/bulk', { selection, format });
  }

  // Statistics endpoints
  async getStats(timeframe = '7d') {
    return this.get(`/stats?timeframe=${timeframe}`);
  }

  async getModelStats(modelSlug, timeframe = '7d') {
    return this.get(`/stats/models/${encodeURIComponent(modelSlug)}?timeframe=${timeframe}`);
  }

  // Search endpoints
  async search(query, filters = {}) {
    return this.post('/search', { query, ...filters });
  }

  async getSearchSuggestions(query) {
    return this.get(`/search/suggestions?q=${encodeURIComponent(query)}`);
  }
}

// WebSocket manager for real-time updates
class WebSocketManager {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 30000;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.listeners = {};
    this.isReconnecting = false;
  }

  connect() {
    try {
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.isReconnecting = false;
        this.emit('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.emit('message', data);
          if (data.type) {
            this.emit(data.type, data);
          }
        } catch (error) {
          console.error('WebSocket message parse error:', error);
        }
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        this.emit('disconnected', event);
        this.handleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.emit('error', error);
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.handleReconnect();
    }
  }

  handleReconnect() {
    if (this.isReconnecting || this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    this.isReconnecting = true;
    
    setTimeout(() => {
      console.log(`Reconnecting WebSocket (attempt ${this.reconnectAttempts + 1})`);
      this.reconnectAttempts++;
      this.connect();
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    }, this.reconnectDelay);
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket not connected, message not sent:', data);
    }
  }

  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }

  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => callback(data));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Create global instances (defensive)
if (typeof window.API === 'undefined') {
  window.API = new AppAPI();
}
if (typeof window.WebSocketManager === 'undefined') {
  window.WebSocketManager = WebSocketManager;
}

// Helper function for async operations with loading states
window.withLoading = async function(element, asyncFn) {
  const originalText = element.textContent;
  const originalDisabled = element.disabled;
  
  element.disabled = true;
  element.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Loading...';
  
  try {
    return await asyncFn();
  } catch (error) {
    console.error('Operation failed:', error);
    window.App?.showToast('Operation failed: ' + error.message, 'error');
    throw error;
  } finally {
    element.textContent = originalText;
    element.disabled = originalDisabled;
  }
};

console.log('📡 API client loaded successfully');