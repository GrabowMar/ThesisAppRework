// Authentication Service - Token management and auth API calls
// Handles login, register, logout, and JWT token storage
import api from './api';

// ============================================================================
// TOKEN MANAGEMENT
// ============================================================================

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

/**
 * Store the authentication token in localStorage
 */
export const setToken = (token) => {
  localStorage.setItem(TOKEN_KEY, token);
};

/**
 * Get the stored authentication token
 */
export const getToken = () => {
  return localStorage.getItem(TOKEN_KEY);
};

/**
 * Remove the authentication token
 */
export const clearToken = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

/**
 * Check if user is authenticated (has valid token)
 */
export const isAuthenticated = () => {
  return !!getToken();
};

/**
 * Store user data in localStorage
 */
export const setUser = (user) => {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

/**
 * Get stored user data
 */
export const getUser = () => {
  const user = localStorage.getItem(USER_KEY);
  return user ? JSON.parse(user) : null;
};

// ============================================================================
// AUTH API FUNCTIONS
// ============================================================================

/**
 * Login with username and password
 * @param {string} username 
 * @param {string} password 
 * @returns {Promise} Response with token and user data
 */
export const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password });
  if (response.data.token) {
    setToken(response.data.token);
    setUser(response.data.user);
  }
  return response;
};

/**
 * Register a new user account
 * @param {Object} data - { username, password, email? }
 * @returns {Promise} Response with token and user data
 */
export const register = async (data) => {
  const response = await api.post('/auth/register', data);
  if (response.data.token) {
    setToken(response.data.token);
    setUser(response.data.user);
  }
  return response;
};

/**
 * Logout the current user
 * @returns {Promise}
 */
export const logout = async () => {
  try {
    await api.post('/auth/logout');
  } finally {
    clearToken();
  }
};

/**
 * Get current user's profile
 * @returns {Promise} Response with user data
 */
export const getMe = () => api.get('/auth/me');

/**
 * Change the current user's password
 * @param {string} currentPassword 
 * @param {string} newPassword 
 * @returns {Promise}
 */
export const changePassword = (currentPassword, newPassword) => 
  api.post('/auth/change-password', { 
    current_password: currentPassword, 
    new_password: newPassword 
  });

// ============================================================================
// AXIOS INTERCEPTOR - Auto-inject token into requests
// ============================================================================

// Add request interceptor to inject auth token
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

// Add response interceptor to handle 401 errors (token expired/invalid)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear auth state
      // Note: Don't auto-redirect here, let components handle it
      clearToken();
    }
    return Promise.reject(error);
  }
);

// Export all auth functions as a service object
export const authService = {
  login,
  register,
  logout,
  getMe,
  changePassword,
  setToken,
  getToken,
  clearToken,
  isAuthenticated,
  setUser,
  getUser,
};

export default authService;
