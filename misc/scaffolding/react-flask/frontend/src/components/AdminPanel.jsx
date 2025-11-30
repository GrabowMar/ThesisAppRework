import React, { useState, useEffect } from 'react';
import { useAuth } from './AuthContext';
import { Spinner } from './Spinner';
import toast from 'react-hot-toast';
import {
  UsersIcon,
  MagnifyingGlassIcon,
  PencilSquareIcon,
  TrashIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  CheckCircleIcon,
  XCircleIcon,
  ChartBarIcon,
  UserPlusIcon,
  ArrowPathIcon,
  ChevronLeftIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';

/**
 * AdminPanel - User management panel for administrators
 * Features: List users, search, toggle admin/active status, delete users, stats
 */
export function AdminPanel() {
  const { authApi, user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [editingUser, setEditingUser] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);

  const fetchUsers = async () => {
    try {
      const { data } = await authApi.get('/api/admin/users', {
        params: { page, search, per_page: 10 }
      });
      setUsers(data.users);
      setTotalPages(data.pages);
    } catch (error) {
      toast.error('Failed to load users');
    }
  };

  const fetchStats = async () => {
    try {
      const { data } = await authApi.get('/api/admin/stats');
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats');
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchUsers(), fetchStats()]);
      setLoading(false);
    };
    loadData();
  }, [page]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      if (page === 1) fetchUsers();
      else setPage(1);
    }, 300);
    return () => clearTimeout(debounce);
  }, [search]);

  const handleToggleAdmin = async (userId, isAdmin) => {
    try {
      await authApi.put(`/api/admin/users/${userId}`, { is_admin: !isAdmin });
      toast.success(`Admin status ${!isAdmin ? 'granted' : 'revoked'}`);
      fetchUsers();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to update user');
    }
  };

  const handleToggleActive = async (userId, isActive) => {
    try {
      await authApi.put(`/api/admin/users/${userId}`, { is_active: !isActive });
      toast.success(`User ${!isActive ? 'activated' : 'deactivated'}`);
      fetchUsers();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to update user');
    }
  };

  const handleDeleteUser = async (userId) => {
    try {
      await authApi.delete(`/api/admin/users/${userId}`);
      toast.success('User deleted');
      setShowDeleteConfirm(null);
      fetchUsers();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to delete user');
    }
  };

  const handleUpdateUser = async (e) => {
    e.preventDefault();
    try {
      await authApi.put(`/api/admin/users/${editingUser.id}`, {
        email: editingUser.email,
        password: editingUser.newPassword || undefined
      });
      toast.success('User updated');
      setEditingUser(null);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to update user');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard
            label="Total Users"
            value={stats.total_users}
            icon={<UsersIcon className="w-6 h-6" />}
            color="blue"
          />
          <StatCard
            label="Active Users"
            value={stats.active_users}
            icon={<CheckCircleIcon className="w-6 h-6" />}
            color="green"
          />
          <StatCard
            label="Admins"
            value={stats.admin_users}
            icon={<ShieldCheckIcon className="w-6 h-6" />}
            color="purple"
          />
          <StatCard
            label="New (7 days)"
            value={stats.new_users_7d}
            icon={<UserPlusIcon className="w-6 h-6" />}
            color="amber"
          />
          <StatCard
            label="Active Today"
            value={stats.recent_logins_24h}
            icon={<ChartBarIcon className="w-6 h-6" />}
            color="indigo"
          />
        </div>
      )}

      {/* User Management Card */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <UsersIcon className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900">User Management</h2>
                <p className="text-sm text-gray-500">Manage user accounts and permissions</p>
              </div>
            </div>
            
            {/* Search */}
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search users..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-full sm:w-64"
              />
            </div>
          </div>
        </div>

        {/* User Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Login</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-medium">
                        {user.username.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{user.username}</p>
                        <p className="text-sm text-gray-500">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => handleToggleActive(user.id, user.is_active)}
                      disabled={user.id === currentUser?.id}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        user.is_active
                          ? 'bg-green-100 text-green-700 hover:bg-green-200'
                          : 'bg-red-100 text-red-700 hover:bg-red-200'
                      } ${user.id === currentUser?.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      {user.is_active ? (
                        <>
                          <CheckCircleIcon className="w-4 h-4" />
                          Active
                        </>
                      ) : (
                        <>
                          <XCircleIcon className="w-4 h-4" />
                          Inactive
                        </>
                      )}
                    </button>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => handleToggleAdmin(user.id, user.is_admin)}
                      disabled={user.id === currentUser?.id}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        user.is_admin
                          ? 'bg-purple-100 text-purple-700 hover:bg-purple-200'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      } ${user.id === currentUser?.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      {user.is_admin ? (
                        <>
                          <ShieldCheckIcon className="w-4 h-4" />
                          Admin
                        </>
                      ) : (
                        <>
                          <ShieldExclamationIcon className="w-4 h-4" />
                          User
                        </>
                      )}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {user.last_login
                      ? new Date(user.last_login).toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setEditingUser({ ...user, newPassword: '' })}
                        className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="Edit user"
                      >
                        <PencilSquareIcon className="w-5 h-5" />
                      </button>
                      {user.id !== currentUser?.id && (
                        <button
                          onClick={() => setShowDeleteConfirm(user)}
                          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Delete user"
                        >
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Page {page} of {totalPages}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeftIcon className="w-5 h-5" />
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRightIcon className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Edit User Modal */}
      {editingUser && (
        <Modal onClose={() => setEditingUser(null)}>
          <form onSubmit={handleUpdateUser} className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">
              Edit User: {editingUser.username}
            </h3>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={editingUser.email}
                onChange={(e) => setEditingUser({ ...editingUser, email: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                New Password (leave blank to keep current)
              </label>
              <input
                type="password"
                value={editingUser.newPassword}
                onChange={(e) => setEditingUser({ ...editingUser, newPassword: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
              />
            </div>
            
            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={() => setEditingUser(null)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Save Changes
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <Modal onClose={() => setShowDeleteConfirm(null)}>
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <TrashIcon className="w-6 h-6 text-red-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete User</h3>
            <p className="text-gray-500 mb-6">
              Are you sure you want to delete <strong>{showDeleteConfirm.username}</strong>? This action cannot be undone.
            </p>
            <div className="flex justify-center gap-3">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteUser(showDeleteConfirm.id)}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// Stat Card Component
function StatCard({ label, value, icon, color }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    amber: 'bg-amber-50 text-amber-600',
    indigo: 'bg-indigo-50 text-indigo-600'
  };

  return (
    <div className="bg-white rounded-xl shadow p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${colors[color]}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

// Modal Component
function Modal({ children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/50" onClick={onClose} />
        <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
          {children}
        </div>
      </div>
    </div>
  );
}

export default AdminPanel;
