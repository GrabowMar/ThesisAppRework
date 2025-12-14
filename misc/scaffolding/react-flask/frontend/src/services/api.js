// API Service - Centralized API communication layer
// All API calls should go through this service
import axios from 'axios';

// Base axios instance with default config
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// ============================================================================
// USER API FUNCTIONS - Implement public API calls here
// ============================================================================
//
// Example API functions:
//
// export const getItems = () => api.get('/items');
// export const getItem = (id) => api.get(`/items/${id}`);
// export const createItem = (data) => api.post('/items', data);
// export const updateItem = (id, data) => api.put(`/items/${id}`, data);
// export const deleteItem = (id) => api.delete(`/items/${id}`);
//
// IMPLEMENT YOUR USER API FUNCTIONS BELOW:
// ============================================================================


// ============================================================================
// ADMIN API FUNCTIONS - Implement admin API calls here
// ============================================================================
//
// Example admin API functions:
//
// export const adminGetAllItems = () => api.get('/admin/items');
// export const adminToggleItem = (id) => api.post(`/admin/items/${id}/toggle`);
// export const adminBulkDelete = (ids) => api.post('/admin/items/bulk-delete', { ids });
// export const adminGetStats = () => api.get('/admin/stats');
//
// IMPLEMENT YOUR ADMIN API FUNCTIONS BELOW:
// ============================================================================


export default api;
