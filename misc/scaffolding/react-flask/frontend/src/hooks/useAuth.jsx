// Authentication Hook and Context Provider
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/auth';
import toast from 'react-hot-toast';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const initAuth = async () => {
      if (authService.isAuthenticated()) {
        try {
          const response = await authService.getMe();
          setUser(response.data.user);
          setIsAuthenticated(true);
        } catch (error) {
          authService.clearToken();
          setUser(null);
          setIsAuthenticated(false);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = useCallback(async (username, password) => {
    try {
      const response = await authService.login(username, password);
      setUser(response.data.user);
      setIsAuthenticated(true);
      toast.success('Login successful');
      return response;
    } catch (error) {
      toast.error(error.response?.data?.error || 'Login failed');
      throw error;
    }
  }, []);

  const register = useCallback(async (data) => {
    try {
      const response = await authService.register(data);
      setUser(response.data.user);
      setIsAuthenticated(true);
      toast.success('Registration successful');
      return response;
    } catch (error) {
      toast.error(error.response?.data?.error || 'Registration failed');
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try { await authService.logout(); } finally {
      setUser(null);
      setIsAuthenticated(false);
      toast.success('Logged out');
    }
  }, []);

  const value = {
    user, loading, isAuthenticated,
    isAdmin: user?.is_admin || false,
    login, register, logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}

export default useAuth;
