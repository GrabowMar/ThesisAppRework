import { createContext, useContext, useState, useEffect, useCallback } from 'react';

// LLM: Import auth service and toast
// import { authService } from '../services/auth';
// import toast from 'react-hot-toast';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // LLM: Implement auth state and functions
  // State: user, loading, isAuthenticated
  // Functions: login, register, logout
  // On mount: check token, fetch user with getMe()
  
  const value = {
    user: null,
    loading: false,
    isAuthenticated: false,
    isAdmin: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

export default useAuth;
