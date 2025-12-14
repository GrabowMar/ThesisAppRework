// Admin Page - Administrative interface (requires admin authentication)
// This component is protected by ProtectedRoute in App.jsx - only admins can access
import React, { useState, useEffect } from 'react';
import { Spinner, ErrorBoundary } from '../components';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';

// ============================================================================
// ADMIN DASHBOARD COMPONENT - Implement admin interface here
// ============================================================================
//
// This component renders for authenticated admin users only.
// The login gate is handled by ProtectedRoute in App.jsx using useAuth.
//
// Implement:
// - View all items (including inactive/deleted)
// - Toggle item states (active/inactive)
// - Bulk operations (delete multiple items)
// - Dashboard statistics
// - User management (if applicable)
//
// Example structure:
//
// function AdminDashboard() {
//   const { user, logout } = useAuth();
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
//         <div className="flex items-center gap-4">
//           <span className="text-gray-600">Welcome, {user?.username}</span>
//           <button onClick={logout} className="...">Logout</button>
//         </div>
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

function AdminPage() {
  const { user, logout } = useAuth();

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <p className="text-gray-600">Welcome back, {user?.username}</p>
        </div>
        <button 
          onClick={logout}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
        >
          Logout
        </button>
      </div>
      
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-gray-500 text-sm font-medium">Total Users</h3>
          <p className="text-3xl font-bold text-gray-900">-</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-gray-500 text-sm font-medium">Active Items</h3>
          <p className="text-3xl font-bold text-gray-900">-</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-gray-500 text-sm font-medium">Total Items</h3>
          <p className="text-3xl font-bold text-gray-900">-</p>
        </div>
      </div>

      {/* Admin Content Area */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Admin Panel</h2>
        <p className="text-gray-600">
          {/* TODO: LLM should implement admin interface here */}
          Implement your admin functionality here. This page is protected and only accessible to admin users.
        </p>
      </div>
    </div>
  );
}

export default AdminPage;
