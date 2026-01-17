import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { login as authLogin, register as authRegister, logout as authLogout, getMe, isAuthenticated } from '../services/auth';
import toast from 'react-hot-toast';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      if (isAuthenticated()) {
        try {
          const userData = await getMe();
          setUser(userData);
        } catch (error) {
          console.error('Auth check failed:', error);
          setUser(null);
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  const login = useCallback(async (username, password) => {
    try {
      const data = await authLogin(username, password);
      setUser(data.user);
      toast.success('Welcome back!');
      return data;
    } catch (error) {
      const message = error.response?.data?.error || 'Login failed';
      toast.error(message);
      throw error;
    }
  }, []);

  const register = useCallback(async (username, password, email = null) => {
    try {
      const data = await authRegister(username, password, email);
      setUser(data.user);
      toast.success('Account created!');
      return data;
    } catch (error) {
      const message = error.response?.data?.error || 'Registration failed';
      toast.error(message);
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    authLogout();
    setUser(null);
    toast.success('Logged out');
  }, []);

  const value = {
    user,
    loading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin || false,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

export default useAuth;
