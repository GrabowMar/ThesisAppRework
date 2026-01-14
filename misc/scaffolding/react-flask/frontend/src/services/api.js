import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
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
