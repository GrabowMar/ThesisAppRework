// React Application - Single File Frontend
// LLM: Implement all components, auth, and API calls in this file

import React, { useState, useEffect, createContext, useContext } from 'react';
import { Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';

// =============================================================================
// API CLIENT
// =============================================================================

const baseURL = import.meta.env.VITE_BACKEND_URL
  ? `${import.meta.env.VITE_BACKEND_URL.replace(/\/$/, '')}/api`
  : '/api';

const api = axios.create({ baseURL, headers: { 'Content-Type': 'application/json' } });

// Add token to requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// LLM: Add API functions for your endpoints
// const getItems = () => api.get('/items');
// const createItem = (data) => api.post('/items', data);


// =============================================================================
// AUTH CONTEXT - LLM: Implement auth state management
// =============================================================================

const AuthContext = createContext(null);

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // LLM: Implement auth check on mount
  // LLM: Implement login, register, logout functions

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, isAdmin: user?.is_admin }}>
      {children}
    </AuthContext.Provider>
  );
}

const useAuth = () => useContext(AuthContext);


// =============================================================================
// LOGIN PAGE - LLM: Implement login/register form
// =============================================================================

function LoginPage() {
  // LLM: Implement login/register form with state
  // LLM: Handle form submission, call API, show toast on success/error

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Login</h1>
        {/* LLM: Implement login form */}
      </div>
    </div>
  );
}


// =============================================================================
// HOME PAGE - LLM: Public landing page with guest + logged-in summary
// =============================================================================

function HomePage() {
  const { user, isAuthenticated } = useAuth();

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Welcome</h1>
      {!isAuthenticated ? (
        <p className="text-gray-600">Guest view. Please log in to continue.</p>
      ) : (
        <p className="text-gray-600">Logged in as {user?.username}</p>
      )}
    </div>
  );
}


// =============================================================================
// USER PAGE - LLM: Implement main user interface
// =============================================================================

function UserPage() {
  // LLM: Implement user page with:
  // - Data fetching and display
  // - CRUD operations
  // - Loading/error states
  // - Logged-in user info panel (e.g., "Logged in as <username>")

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">User Dashboard</h1>
      {/* LLM: Implement user interface */}
    </div>
  );
}


// =============================================================================
// ADMIN PAGE - LLM: Implement admin dashboard
// =============================================================================

function AdminPage() {
  // LLM: Implement admin dashboard with:
  // - Stats cards
  // - User management
  // - Data tables

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Admin Dashboard</h1>
      {/* LLM: Implement admin interface */}
    </div>
  );
}


// =============================================================================
// NAVIGATION
// =============================================================================

function Navigation() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.href = '/login';
  };

  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-xl font-bold text-indigo-600">App</Link>
            <div className="flex gap-4">
              <Link to="/" className="text-gray-600 hover:text-gray-900">Home</Link>
              {isAuthenticated && (
                <Link to="/user" className="text-gray-600 hover:text-gray-900">My Dashboard</Link>
              )}
              {user?.is_admin && (
                <Link to="/admin" className="text-gray-600 hover:text-gray-900">Admin</Link>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4">
            {isAuthenticated ? (
              <>
                <span className="text-gray-600">{user?.username}</span>
                <button onClick={handleLogout} className="text-gray-600 hover:text-gray-900">Logout</button>
              </>
            ) : (
              <Link to="/login" className="text-indigo-600 hover:text-indigo-800">Login</Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}


// =============================================================================
// PROTECTED ROUTE
// =============================================================================

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (adminOnly && !user?.is_admin) return <Navigate to="/" replace />;
  return children;
}


// =============================================================================
// APP
// =============================================================================

function App() {
  return (
    <AuthProvider>
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/user" element={<ProtectedRoute><UserPage /></ProtectedRoute>} />
            <Route path="/admin" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  );
}

export default App;
