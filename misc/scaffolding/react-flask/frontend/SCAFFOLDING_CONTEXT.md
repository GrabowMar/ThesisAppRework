# Frontend Blueprint Reference

## CRITICAL RULES (READ FIRST)
1. **Use EXACT API paths from requirements** - Replace `/api/YOUR_RESOURCE` in examples with actual paths like `/api/todos`, `/api/books`, etc.
2. **Only these components exist**: `Spinner`, `ErrorBoundary` - create others inline if needed
3. **API response format**: List endpoints return `{items: [...], total: N}` - access via `response.data.items`
4. **Only implement what requirements ask for**: No routing/auth unless specified

## Stack
- React 18, Vite, Tailwind CSS, Axios, Heroicons, react-hot-toast

## Available Imports
```jsx
// These exist in ./components:
import { Spinner, ErrorBoundary } from './components';

// From node_modules:
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { PlusIcon, TrashIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline';
```

## Complete App Pattern
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { PlusIcon, TrashIcon, CheckIcon } from '@heroicons/react/24/outline';
import { Spinner } from './components';

function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newItem, setNewItem] = useState('');

  // Fetch data - REPLACE '/api/YOUR_RESOURCE' with actual path from requirements!
  useEffect(() => {
    axios.get('/api/YOUR_RESOURCE')  // e.g., '/api/todos'
      .then(res => setItems(res.data.items || []))
      .catch(() => toast.error('Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newItem.trim()) return;
    try {
      const { data } = await axios.post('/api/YOUR_RESOURCE', { /* fields */ });
      setItems([...items, data]);
      setNewItem('');
      toast.success('Created!');
    } catch {
      toast.error('Failed to create');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this item?')) return;
    try {
      await axios.delete(`/api/YOUR_RESOURCE/${id}`);
      setItems(items.filter(item => item.id !== id));
      toast.success('Deleted!');
    } catch {
      toast.error('Failed to delete');
    }
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <Spinner size="lg" />
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-blue-600 text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-2xl font-bold">App Title</h1>
          <p className="text-blue-100">Description</p>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 max-w-2xl">
        {/* Add Form */}
        <form onSubmit={handleSubmit} className="flex gap-2 mb-6">
          <input
            type="text"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            placeholder="New item..."
            className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
            <PlusIcon className="h-5 w-5" />
          </button>
        </form>

        {/* List */}
        {items.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p>No items yet. Add one above!</p>
          </div>
        ) : (
          <ul className="bg-white rounded-lg shadow divide-y">
            {items.map(item => (
              <li key={item.id} className="p-4 flex justify-between items-center">
                <span>{item.name}</span>
                <button onClick={() => handleDelete(item.id)} className="text-red-500 hover:text-red-700">
                  <TrashIcon className="h-5 w-5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-gray-500 text-sm">
        © 2024 App Name
      </footer>
    </div>
  );
}

export default App;
```

## Tailwind Quick Reference
- Layout: `flex`, `grid`, `justify-between`, `items-center`, `gap-{n}`
- Spacing: `p-{n}`, `m-{n}`, `py-{n}`, `px-{n}`
- Colors: `bg-blue-600`, `text-white`, `text-gray-500`
- Effects: `shadow`, `rounded-lg`, `hover:bg-blue-700`
