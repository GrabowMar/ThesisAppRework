# Frontend Context

## Architecture (4-Query System)
```
frontend/src/
├── App.jsx           # Router + Navigation (DO NOT MODIFY)
├── main.jsx          # React entry (DO NOT MODIFY)
├── App.css           # Styles
├── pages/
│   ├── index.js      # Page exports (DO NOT MODIFY)
│   ├── UserPage.jsx  # Main user interface (Query 3)
│   └── AdminPage.jsx # Admin dashboard (Query 4)
├── services/
│   └── api.js        # API call functions (Query 3 & 4)
├── hooks/
│   └── useData.js    # Custom hooks (Query 3)
└── components/
    ├── index.js      # Pre-built exports
    ├── Spinner.jsx   # Loading indicator (pre-built)
    └── ErrorBoundary.jsx # Error boundary (pre-built)
```

## Stack
React 18, Axios, Tailwind CSS, react-hot-toast, @heroicons/react, react-router-dom

## Pre-built Components
```jsx
import { Spinner, ErrorBoundary } from '../components';
```

## Rules
1. User API calls to `/api/...`
2. Admin API calls to `/api/admin/...`
3. Use axios via `services/api.js`
4. Use toast for notifications
5. Handle loading + errors always

## Patterns (Pseudocode)

### API Service (services/api.js)
```jsx
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
});

// User API
export const getItems = () => api.get('/items');
export const createItem = (data) => api.post('/items', data);
export const updateItem = (id, data) => api.put(`/items/${id}`, data);
export const deleteItem = (id) => api.delete(`/items/${id}`);

// Admin API
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
import { getItems, createItem } from '../services/api';
import toast from 'react-hot-toast';

function UserPage() {
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
import { adminGetAllItems, adminToggleItem, adminBulkDelete, adminGetStats } from '../services/api';
import toast from 'react-hot-toast';

function AdminPage() {
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
      <h1 className="text-2xl font-bold mb-4">Admin Dashboard</h1>
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
