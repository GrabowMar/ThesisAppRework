import axios from 'axios';

const rawBaseUrl = import.meta.env.VITE_BACKEND_URL;
const normalizedBase = rawBaseUrl ? rawBaseUrl.replace(/\/$/, '') : '';
const baseURL = normalizedBase ? `${normalizedBase}/api` : '/api';

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});

// LLM: Add user API functions
// export const getItems = () => api.get('/items');
// export const createItem = (data) => api.post('/items', data);
// export const updateItem = (id, data) => api.put(`/items/${id}`, data);
// export const deleteItem = (id) => api.delete(`/items/${id}`);

// LLM: Add admin API functions (use /admin prefix)
// export const adminGetStats = () => api.get('/admin/stats');
// export const adminGetItems = () => api.get('/admin/items');
// export const adminToggleItem = (id) => api.post(`/admin/items/${id}/toggle`);

export default api;
