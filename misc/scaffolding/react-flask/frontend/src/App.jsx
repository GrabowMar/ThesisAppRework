// Main App Component - Router and Layout Configuration
// Routes are pre-configured; implement page components in ./pages/
import React from 'react';
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { UserPage, AdminPage, LoginPage } from './pages';
import { useAuth } from './hooks/useAuth';

// ============================================================================
// NAVIGATION COMPONENT - Includes auth-aware navigation
// ============================================================================
function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  
  const isAdminRoute = location.pathname.startsWith('/admin');
  const isLoginRoute = location.pathname === '/login';
  
  const handleLogout = async () => {
    await logout();
    navigate('/');
  };
  
  // Don't show nav on login page
  if (isLoginRoute) return null;
  
  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="text-xl font-bold text-gray-800">
            {/* App name */}
            App
          </Link>
          <div className="flex items-center space-x-4">
            <Link
              to="/"
              className={`px-3 py-2 rounded-md ${
                !isAdminRoute && !isLoginRoute ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              Home
            </Link>
            
            {/* Admin link - only show if user is admin */}
            {isAdmin && (
              <Link
                to="/admin"
                className={`px-3 py-2 rounded-md ${
                  isAdminRoute ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                Admin
              </Link>
            )}
            
            {/* Auth buttons */}
            {isAuthenticated ? (
              <div className="flex items-center space-x-3">
                <span className="text-sm text-gray-600">
                  {user?.username}
                  {isAdmin && <span className="ml-1 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">Admin</span>}
                </span>
                <button
                  onClick={handleLogout}
                  className="px-3 py-2 text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded-md"
                >
                  Logout
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Login
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

// ============================================================================
// PROTECTED ROUTE WRAPPER - Requires authentication
// ============================================================================
function ProtectedRoute({ children, requireAdmin = false }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  
  React.useEffect(() => {
    if (!loading) {
      if (!isAuthenticated) {
        // Redirect to login, save the attempted URL
        navigate('/login', { state: { from: location }, replace: true });
      } else if (requireAdmin && !isAdmin) {
        // Redirect non-admins to home
        navigate('/', { replace: true });
      }
    }
  }, [isAuthenticated, isAdmin, loading, navigate, location, requireAdmin]);
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }
  
  if (!isAuthenticated || (requireAdmin && !isAdmin)) {
    return null;
  }
  
  return children;
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
          <Route path="/login" element={<LoginPage />} />
          <Route 
            path="/admin" 
            element={
              <ProtectedRoute requireAdmin>
                <AdminPage />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </main>
    </div>
  );
}

export default App;
