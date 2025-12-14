// Main App Component - Router and Layout Configuration
// Routes are pre-configured; implement page components in ./pages/
import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { UserPage, AdminPage } from './pages';

// ============================================================================
// NAVIGATION COMPONENT - Customize navigation here
// ============================================================================
function Navigation() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith('/admin');
  
  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="text-xl font-bold text-gray-800">
            {/* App name */}
            App
          </Link>
          <div className="flex space-x-4">
            <Link
              to="/"
              className={`px-3 py-2 rounded-md ${
                !isAdmin ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              Home
            </Link>
            <Link
              to="/admin"
              className={`px-3 py-2 rounded-md ${
                isAdmin ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              Admin
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}

// ============================================================================
// MAIN APP - Routes are pre-configured
// ============================================================================
function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <main>
        <Routes>
          <Route path="/" element={<UserPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
