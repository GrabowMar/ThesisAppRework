// Authentication Service - Token management and auth API
import api from './api';

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const clearToken = () => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); };
export const isAuthenticated = () => !!getToken();
export const setUser = (user) => localStorage.setItem(USER_KEY, JSON.stringify(user));
export const getUser = () => { const u = localStorage.getItem(USER_KEY); return u ? JSON.parse(u) : null; };

export const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password });
  if (response.data.token) {
    setToken(response.data.token);
    setUser(response.data.user);
  }
  return response;
};

export const register = async (data) => {
  const response = await api.post('/auth/register', data);
  if (response.data.token) {
    setToken(response.data.token);
    setUser(response.data.user);
  }
  return response;
};

export const logout = async () => {
  try { await api.post('/auth/logout'); } finally { clearToken(); }
};

export const getMe = () => api.get('/auth/me');

// Auto-inject token into requests
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// Clear token on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) clearToken();
    return Promise.reject(error);
  }
);

export const authService = {
  login, register, logout, getMe,
  setToken, getToken, clearToken, isAuthenticated, setUser, getUser,
};

export default authService;
