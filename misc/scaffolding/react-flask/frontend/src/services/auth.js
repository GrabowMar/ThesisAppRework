import api from './api';

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

// Token management
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const clearToken = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};
export const isAuthenticated = () => !!getToken();

// Auth API functions
export const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password });
  if (response.data.token) {
    setToken(response.data.token);
  }
  return response.data;
};

export const register = async (username, password, email = null) => {
  const response = await api.post('/auth/register', { username, password, email });
  if (response.data.token) {
    setToken(response.data.token);
  }
  return response.data;
};

export const getMe = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

export const logout = () => {
  clearToken();
};

// Request interceptor - add token to all requests
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authService = {
  login,
  register,
  logout,
  getMe,
  getToken,
  setToken,
  clearToken,
  isAuthenticated,
};

export default authService;
