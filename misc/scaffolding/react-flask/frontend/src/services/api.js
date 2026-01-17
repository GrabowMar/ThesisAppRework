import axios from 'axios';

// API base URL - works in Docker and local development
const rawBaseUrl = import.meta.env.VITE_BACKEND_URL;
const normalizedBase = rawBaseUrl ? rawBaseUrl.replace(/\/$/, '') : '';
const baseURL = normalizedBase ? `${normalizedBase}/api` : '/api';

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});

// LLM: ADD USER API FUNCTIONS BELOW
// Pattern: export const getItems = () => api.get('/items');
// Pattern: export const createItem = (data) => api.post('/items', data);
// Pattern: export const updateItem = (id, data) => api.put(`/items/${id}`, data);
// Pattern: export const deleteItem = (id) => api.delete(`/items/${id}`);


// LLM: ADD ADMIN API FUNCTIONS BELOW (use /admin prefix)
// Pattern: export const adminGetStats = () => api.get('/admin/stats');
// Pattern: export const adminGetUsers = () => api.get('/admin/users');
// Pattern: export const adminToggleUser = (id) => api.post(`/admin/users/${id}/toggle`);


export default api;
