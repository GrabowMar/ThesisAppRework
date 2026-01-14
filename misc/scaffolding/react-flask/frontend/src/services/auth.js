import api from './api';

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

// LLM: Implement token storage
// export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
// export const getToken = () => localStorage.getItem(TOKEN_KEY);
// export const clearToken = () => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); };
// export const isAuthenticated = () => !!getToken();

// LLM: Implement auth API functions
// export const login = async (username, password) => { ... };
// export const register = async (data) => { ... };
// export const logout = async () => { ... };
// export const getMe = () => api.get('/auth/me');

// LLM: Add request interceptor to inject token
// api.interceptors.request.use(config => {
//   const token = getToken();
//   if (token) config.headers.Authorization = `Bearer ${token}`;
//   return config;
// });

// LLM: Add response interceptor to clear token on 401

export const authService = {
  // LLM: Export all auth functions
};

export default authService;
