// Admin Page - Administrative interface with login protection
// This component provides admin-only functionality behind a simple login gate
import React, { useState, useEffect } from 'react';
import { Spinner, ErrorBoundary } from '../components';
import toast from 'react-hot-toast';

// ============================================================================
// ADMIN LOGIN GATE - Simple password protection for admin area
// ============================================================================
// 
// This is a rudimentary client-side login gate. The LLM should:
// 1. Keep this login gate structure (modify password/logic as needed)
// 2. Implement the AdminDashboard component below
// 3. Optionally add server-side validation for sensitive operations
//
// Note: This is basic protection. For production apps, implement proper
// authentication with JWT tokens, sessions, or OAuth.

function AdminLoginGate({ onLogin }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  // ========================================================================
  // IMPLEMENT: Customize admin password validation logic here
  // The LLM should modify this to match the application's auth requirements
  // ========================================================================
  const handleSubmit = (e) => {
    e.preventDefault();
    // TODO: LLM should implement proper password validation
    // For now, accept any non-empty password (LLM will customize)
    if (password.trim()) {
      onLogin(password);
    } else {
      setError('Please enter the admin password');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md w-96">
        <h2 className="text-2xl font-bold mb-6 text-center">Admin Access</h2>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2">
              Admin Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter admin password"
            />
          </div>
          {error && (
            <p className="text-red-500 text-sm mb-4">{error}</p>
          )}
          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Access Admin Panel
          </button>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// ADMIN DASHBOARD COMPONENT - Implement admin interface here
// ============================================================================
//
// This component renders AFTER successful login. Implement:
// - View all items (including inactive/deleted)
// - Toggle item states (active/inactive)
// - Bulk operations (delete multiple items)
// - Dashboard statistics
// - User management (if applicable)
//
// Example structure:
//
// function AdminDashboard({ onLogout }) {
//   const [items, setItems] = useState([]);
//   const [stats, setStats] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [selectedIds, setSelectedIds] = useState([]);
//
//   useEffect(() => {
//     Promise.all([fetchAllItems(), fetchStats()]);
//   }, []);
//
//   const handleToggle = async (id) => {
//     try {
//       await adminToggleItem(id);
//       toast.success('Item status updated');
//       fetchAllItems();
//     } catch (err) {
//       toast.error('Failed to update item');
//     }
//   };
//
//   return (
//     <div className="container mx-auto p-4">
//       <div className="flex justify-between items-center mb-4">
//         <h1 className="text-2xl font-bold">Admin Dashboard</h1>
//         <button onClick={onLogout} className="...">Logout</button>
//       </div>
//       
//       {/* Stats Cards */}
//       <div className="grid grid-cols-3 gap-4 mb-6">
//         <div className="bg-white p-4 rounded shadow">
//           <h3 className="text-gray-500">Total Items</h3>
//           <p className="text-2xl font-bold">{stats?.total_items}</p>
//         </div>
//       </div>
//       
//       {/* Admin Table with bulk actions */}
//     </div>
//   );
// }
//
// IMPLEMENT YOUR ADMIN DASHBOARD BELOW:
// ============================================================================

function AdminDashboard({ onLogout }) {
  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <button 
          onClick={onLogout}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
        >
          Logout
        </button>
      </div>
      {/* TODO: LLM should implement admin interface here */}
    </div>
  );
}

// ============================================================================
// MAIN ADMIN PAGE - Wraps dashboard with login gate
// ============================================================================

function AdminPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Check for existing session on mount
  useEffect(() => {
    const adminSession = sessionStorage.getItem('adminAuthenticated');
    if (adminSession === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = (password) => {
    // Store session (LLM should enhance with proper validation)
    sessionStorage.setItem('adminAuthenticated', 'true');
    setIsAuthenticated(true);
    toast.success('Admin access granted');
  };

  const handleLogout = () => {
    sessionStorage.removeItem('adminAuthenticated');
    setIsAuthenticated(false);
    toast.success('Logged out');
  };

  if (!isAuthenticated) {
    return <AdminLoginGate onLogin={handleLogin} />;
  }

  return <AdminDashboard onLogout={handleLogout} />;
}

export default AdminPage;
