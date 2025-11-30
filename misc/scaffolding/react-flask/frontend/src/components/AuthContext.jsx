import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';

const API_URL = '';

// Create axios instance with interceptors
const authApi = axios.create({ baseURL: API_URL });

// Request interceptor to add token
authApi.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
authApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${API_URL}/api/auth/refresh`, {}, {
            headers: { Authorization: `Bearer ${refreshToken}` }
          });
          
          localStorage.setItem('access_token', data.access_token);
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
          return authApi(originalRequest);
        } catch (refreshError) {
          // Refresh failed, logout user
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      }
    }
    
    return Promise.reject(error);
  }
);

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Check authentication status on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const { data } = await authApi.get('/api/auth/me');
          setUser(data.user);
          setIsAuthenticated(true);
        } catch (error) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  const login = useCallback(async (username, password) => {
    try {
      const { data } = await axios.post(`${API_URL}/api/auth/login`, {
        username,
        password
      });
      
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      setUser(data.user);
      setIsAuthenticated(true);
      toast.success(`Welcome back, ${data.user.username}!`);
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.error || 'Login failed';
      toast.error(message);
      return { success: false, error: message };
    }
  }, []);

  const register = useCallback(async (username, email, password) => {
    try {
      const { data } = await axios.post(`${API_URL}/api/auth/register`, {
        username,
        email,
        password
      });
      
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      setUser(data.user);
      setIsAuthenticated(true);
      toast.success('Account created successfully!');
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.error || 'Registration failed';
      toast.error(message);
      return { success: false, error: message };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.post('/api/auth/logout');
    } catch (error) {
      // Ignore logout errors
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    setIsAuthenticated(false);
    toast.success('Logged out successfully');
  }, []);

  const updateProfile = useCallback(async (profileData) => {
    try {
      const { data } = await authApi.put('/api/auth/me', profileData);
      setUser(data.user);
      toast.success(data.message || 'Profile updated');
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.error || 'Update failed';
      toast.error(message);
      return { success: false, error: message };
    }
  }, []);

  const requestPasswordReset = useCallback(async (email) => {
    try {
      const { data } = await axios.post(`${API_URL}/api/auth/request-reset`, { email });
      toast.success(data.message);
      // For demo, return the token (remove in production)
      return { success: true, resetToken: data.reset_token };
    } catch (error) {
      const message = error.response?.data?.error || 'Request failed';
      toast.error(message);
      return { success: false, error: message };
    }
  }, []);

  const resetPassword = useCallback(async (token, password) => {
    try {
      const { data } = await axios.post(`${API_URL}/api/auth/reset-password`, {
        token,
        password
      });
      toast.success(data.message);
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.error || 'Reset failed';
      toast.error(message);
      return { success: false, error: message };
    }
  }, []);

  const value = {
    user,
    loading,
    isAuthenticated,
    isAdmin: user?.is_admin || false,
    login,
    register,
    logout,
    updateProfile,
    requestPasswordReset,
    resetPassword,
    authApi // Export the authenticated axios instance
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export { authApi };
export default AuthContext;
