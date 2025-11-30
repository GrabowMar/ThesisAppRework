import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { Spinner } from './Spinner';

/**
 * ProtectedRoute - Wrapper for routes that require authentication
 * Usage: <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
 */
export function ProtectedRoute({ children, requireAdmin = false }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    // Redirect to login, saving the attempted URL
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireAdmin && !isAdmin) {
    // Redirect non-admins away from admin routes
    return <Navigate to="/" replace />;
  }

  return children;
}

/**
 * PublicOnlyRoute - Wrapper for routes that should only be accessible when NOT logged in
 * Usage: <Route path="/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />
 */
export function PublicOnlyRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isAuthenticated) {
    // Redirect authenticated users to home or where they came from
    const from = location.state?.from?.pathname || '/';
    return <Navigate to={from} replace />;
  }

  return children;
}

export default ProtectedRoute;
