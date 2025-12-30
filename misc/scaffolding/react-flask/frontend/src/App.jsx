// Main App - Router and Layout
import React from 'react';
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { UserPage, AdminPage, LoginPage } from './pages';
import { useAuth } from './hooks/useAuth';

function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  
  const isAdminRoute = location.pathname.startsWith('/admin');
  if (location.pathname === '/login') return null;
  
  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="text-xl font-bold text-gray-800">App</Link>
          <div className="flex items-center space-x-4">
            <Link to="/" className={`px-3 py-2 rounded-md ${!isAdminRoute ? 'bg-blue-100 text-blue-700' : 'text-gray-600'}`}>
              Home
            </Link>
            {isAdmin && (
              <Link to="/admin" className={`px-3 py-2 rounded-md ${isAdminRoute ? 'bg-blue-100 text-blue-700' : 'text-gray-600'}`}>
                Admin
              </Link>
            )}
            {isAuthenticated ? (
              <div className="flex items-center space-x-3">
                <span className="text-sm text-gray-600">
                  {user?.username}
                  {isAdmin && <span className="ml-1 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">Admin</span>}
                </span>
                <button onClick={() => { logout(); navigate('/'); }} className="px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-md">
                  Logout
                </button>
              </div>
            ) : (
              <Link to="/login" className="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">Login</Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

function ProtectedRoute({ children, requireAdmin = false }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  
  React.useEffect(() => {
    if (!loading) {
      if (!isAuthenticated) navigate('/login', { state: { from: location }, replace: true });
      else if (requireAdmin && !isAdmin) navigate('/', { replace: true });
    }
  }, [isAuthenticated, isAdmin, loading, navigate, location, requireAdmin]);
  
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div></div>;
  if (!isAuthenticated || (requireAdmin && !isAdmin)) return null;
  return children;
}

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <main>
        <Routes>
          <Route path="/" element={<UserPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/admin" element={<ProtectedRoute requireAdmin><AdminPage /></ProtectedRoute>} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
