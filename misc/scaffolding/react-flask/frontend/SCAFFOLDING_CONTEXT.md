````markdown
# Frontend Context

## Architecture (4-Query System)
```
frontend/src/
├── App.jsx           # Router + Navigation (DO NOT MODIFY)
├── main.jsx          # React entry + AuthProvider (DO NOT MODIFY)
├── App.css           # Styles
├── pages/
│   ├── index.js      # Page exports (DO NOT MODIFY)
│   ├── LoginPage.jsx # Login/Register form (PRE-BUILT)
│   ├── UserPage.jsx  # Main user interface (Query 3)
│   └── AdminPage.jsx # Admin dashboard (Query 4)
├── services/
│   ├── api.js        # API call functions (Query 3 & 4)
│   └── auth.js       # Auth service (PRE-BUILT - DO NOT MODIFY)
├── hooks/
│   ├── useData.js    # Custom hooks (Query 3)
│   └── useAuth.js    # Auth hook (PRE-BUILT - DO NOT MODIFY)
└── components/
    ├── index.js      # Pre-built exports
    ├── Spinner.jsx   # Loading indicator (pre-built)
    └── ErrorBoundary.jsx # Error boundary (pre-built)
```

## Stack
React 18, Axios, Tailwind CSS, react-hot-toast, @heroicons/react, react-router-dom

## Authentication (PRE-BUILT)
The app includes a complete JWT-based auth system:

### useAuth Hook
```jsx
import { useAuth } from '../hooks/useAuth';

function MyComponent() {
  const { 
    user,           // Current user object or null
    isAuthenticated, // Boolean
    isAdmin,        // Boolean - true if user.is_admin
    loading,        // Boolean - true while checking auth
    login,          // async (username, password) => void
    logout,         // async () => void
    register,       // async ({username, password, email?}) => void
  } = useAuth();
  
  if (loading) return <Spinner />;
  
  return (
    <div>
      {isAuthenticated ? (
        <span>Hello, {user.username}</span>
      ) : (
        <Link to="/login">Login</Link>
      )}
    </div>
  );
}
```

### Auth Service (services/auth.js)
```jsx
import { authService } from '../services/auth';

// Token is auto-injected into all API requests via interceptor
// These are used internally by useAuth, but available if needed:
authService.getToken()      // Get stored JWT
authService.isAuthenticated() // Check if token exists
authService.clearToken()    // Remove token (logout)
```

### Routes & Protection
- `/login` - Login/Register page (public)
- `/` - User page (public)
- `/admin` - Admin page (requires admin, auto-redirects to login)

## Pre-built Components
```jsx
import { Spinner, ErrorBoundary } from '../components';
```

## Rules
1. User API calls to `/api/...`
2. Admin API calls to `/api/admin/...`
3. Auth API calls to `/api/auth/...` (handled by useAuth)
4. Use axios via `services/api.js` - auth token auto-injected
5. Use toast for notifications
6. Handle loading + errors always
7. Use `useAuth()` for auth state, not manual token handling

## Patterns (Pseudocode)

### API Service (services/api.js)
```jsx
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
});

// NOTE: Auth token is auto-injected by services/auth.js interceptor

// User API
export const getItems = () => api.get('/items');
export const createItem = (data) => api.post('/items', data);
export const updateItem = (id, data) => api.put(`/items/${id}`, data);
export const deleteItem = (id) => api.delete(`/items/${id}`);

// Admin API (requires admin token - auto-injected)
export const adminGetAllItems = () => api.get('/admin/items');
export const adminToggleItem = (id) => api.post(`/admin/items/${id}/toggle`);
export const adminBulkDelete = (ids) => api.post('/admin/items/bulk-delete', { ids });
export const adminGetStats = () => api.get('/admin/stats');

export default api;
```

### User Page (pages/UserPage.jsx)
```jsx
import React, { useState, useEffect } from 'react';
import { Spinner } from '../components';
import { useAuth } from '../hooks/useAuth';
import { getItems, createItem } from '../services/api';
import toast from 'react-hot-toast';

function UserPage() {
  const { user, isAuthenticated } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchItems();
  }, []);

  const fetchItems = async () => {
    try {
      const res = await getItems();
      setItems(res.data.items || res.data);
    } catch (err) {
      toast.error('Failed to load items');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Spinner />;
  
  return (
    <div className="container mx-auto p-4">
      {isAuthenticated && <p>Welcome, {user.username}!</p>}
      {/* User interface */}
    </div>
  );
}

export default UserPage;
```

### Admin Page (pages/AdminPage.jsx)
```jsx
import React, { useState, useEffect } from 'react';
import { Spinner } from '../components';
import { useAuth } from '../hooks/useAuth';
import { adminGetAllItems, adminToggleItem, adminBulkDelete, adminGetStats } from '../services/api';
import toast from 'react-hot-toast';

// Note: This page is protected by App.jsx ProtectedRoute
// Only admins can access - non-admins are auto-redirected

function AdminPage() {
  const { user, logout } = useAuth();
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchItems(), fetchStats()]);
  }, []);

  const handleToggle = async (id) => {
    await adminToggleItem(id);
    toast.success('Status updated');
    fetchItems();
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    await adminBulkDelete(selectedIds);
    toast.success(`Deleted ${selectedIds.length} items`);
    setSelectedIds([]);
    fetchItems();
  };

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <span>Logged in as {user?.username}</span>
      </div>
      {/* Stats cards, data table with checkboxes, bulk actions */}
    </div>
  );
}

export default AdminPage;
```

## Gotchas
- Response: `{items:[]}` or `[]` - handle both
- Errors: `err.response?.data?.error || err.message`
- Lists: always use `key={item.id}`
- Imports from services: use named exports
- Auth token auto-injected: don't manually set Authorization header
- 401 errors auto-clear token (via interceptor)
- Default admin credentials: admin / admin2025

````
