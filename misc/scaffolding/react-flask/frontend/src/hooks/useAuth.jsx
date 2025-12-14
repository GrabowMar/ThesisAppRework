// Authentication Hook and Context Provider
// Provides auth state management across the entire application
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/auth';
import toast from 'react-hot-toast';

// ============================================================================
// AUTH CONTEXT
// ============================================================================

const AuthContext = createContext(null);

/**
 * AuthProvider - Wrap your app with this to enable auth throughout
 * 
 * Usage in main.jsx or App.jsx:
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Check for existing session on mount
  useEffect(() => {
    const initAuth = async () => {
      if (authService.isAuthenticated()) {
        try {
          // Verify token is still valid by fetching user profile
          const response = await authService.getMe();
          setUser(response.data.user);
          setIsAuthenticated(true);
        } catch (error) {
          // Token invalid/expired - clear it
          authService.clearToken();
          setUser(null);
          setIsAuthenticated(false);
        }
      }
      setLoading(false);
    };
    
    initAuth();
  }, []);

  /**
   * Login with username and password
   */
  const login = useCallback(async (username, password) => {
    try {
      const response = await authService.login(username, password);
      setUser(response.data.user);
      setIsAuthenticated(true);
      toast.success('Login successful');
      return response;
    } catch (error) {
      const message = error.response?.data?.error || 'Login failed';
      toast.error(message);
      throw error;
    }
  }, []);

  /**
   * Register a new account
   */
  const register = useCallback(async (data) => {
    try {
      const response = await authService.register(data);
      setUser(response.data.user);
      setIsAuthenticated(true);
      toast.success('Registration successful');
      return response;
    } catch (error) {
      const message = error.response?.data?.error || 'Registration failed';
      toast.error(message);
      throw error;
    }
  }, []);

  /**
   * Logout the current user
   */
  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      toast.success('Logged out');
    }
  }, []);

  /**
   * Refresh user data from server
   */
  const refreshUser = useCallback(async () => {
    if (!authService.isAuthenticated()) return;
    
    try {
      const response = await authService.getMe();
      setUser(response.data.user);
    } catch (error) {
      // Token might have expired
      authService.clearToken();
      setUser(null);
      setIsAuthenticated(false);
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
    refreshUser,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * useAuth hook - Access auth state and functions from any component
 * 
 * Usage:
 *   const { user, isAuthenticated, login, logout } = useAuth();
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default useAuth;
