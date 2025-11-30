# Frontend Scaffolding Context

## Technical Stack
- **Framework**: React 18 (Vite)
- **Styling**: Tailwind CSS 3.4 (utility-first)
- **Icons**: Heroicons (`@heroicons/react`)
- **Notifications**: react-hot-toast (pre-configured)
- **HTTP Client**: Axios

## Pre-Built Components (USE THESE!)
```jsx
import { Layout, Card, Spinner, EmptyState } from './components';
import { CheckCircleIcon } from '@heroicons/react/24/outline';
```

| Component | Usage |
|-----------|-------|
| `<Layout title="" subtitle="" icon={<Icon />}>` | App shell with gradient header + footer |
| `<Card title="" actions={}>` | Content container with shadow |
| `<Spinner size="sm\|md\|lg" />` | Loading indicator |
| `<EmptyState title="" message="" action={} />` | Empty state display |

## Architecture Rules
1. `src/App.jsx` exports default functional component
2. API: Use relative paths (`/api/items`), never hardcode localhost
3. Define `const API_URL = '';` at top
4. Use `toast.success()` / `toast.error()` for feedback

## Quick Patterns

### Buttons with Interactions
```jsx
<button className="btn-primary hover:scale-105 transition-transform duration-200">
  <PlusIcon className="h-5 w-5 mr-2" /> Add
</button>
<button className="btn-danger btn-sm">Delete</button>
```

### Form Input
```jsx
<input 
  className="input focus:ring-2 focus:ring-blue-500 transition-all duration-200" 
  placeholder="Enter value..."
/>
```

### List Item with Actions
```jsx
<li className="flex items-center justify-between py-3 px-4 hover:bg-gray-50 rounded-lg transition-colors">
  <span>{item.name}</span>
  <div className="flex gap-2">
    <button className="p-2 text-blue-600 hover:bg-blue-50 rounded-full transition-colors">
      <PencilIcon className="h-4 w-4" />
    </button>
    <button className="p-2 text-red-600 hover:bg-red-50 rounded-full transition-colors">
      <TrashIcon className="h-4 w-4" />
    </button>
  </div>
</li>
```

### Stats/Badge
```jsx
<span className="badge-success">Active</span>
<span className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
  {count} items
</span>
```

### Toast with Promise
```jsx
toast.promise(axios.post('/api/items', data), {
  loading: 'Saving...',
  success: 'Created!',
  error: 'Failed'
});
```

## CSS Classes (from App.css)
- Buttons: `btn-primary`, `btn-secondary`, `btn-danger`, `btn-success`, `btn-sm`
- Forms: `input`, `input-error`, `label`, `form-group`
- Alerts: `alert-error`, `alert-success`, `alert-warning`, `alert-info`
- Badges: `badge-primary`, `badge-success`, `badge-danger`
- Tables: `table` (with styled th/td)

## Complete Example
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { PlusIcon, TrashIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { Layout, Card, Spinner, EmptyState } from './components';

const API_URL = '';

function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newItem, setNewItem] = useState('');

  useEffect(() => { fetchItems(); }, []);

  const fetchItems = async () => {
    try {
      const { data } = await axios.get(`${API_URL}/api/items`);
      setItems(data.items || data);
    } catch (err) {
      toast.error('Failed to load');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newItem.trim()) return;
    try {
      const { data } = await axios.post(`${API_URL}/api/items`, { name: newItem });
      setItems([data, ...items]);
      setNewItem('');
      toast.success('Added!');
    } catch (err) {
      toast.error('Failed to add');
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API_URL}/api/items/${id}`);
      setItems(items.filter(i => i.id !== id));
      toast.success('Deleted');
    } catch (err) {
      toast.error('Failed to delete');
    }
  };

  return (
    <Layout 
      title="My App" 
      subtitle="Manage your items"
      icon={<CheckCircleIcon className="h-10 w-10" />}
    >
      <Card title="Items" subtitle={`${items.length} total`}>
        <form onSubmit={handleAdd} className="flex gap-3 mb-6">
          <input
            className="input flex-1"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            placeholder="Add new item..."
          />
          <button type="submit" className="btn-primary hover:scale-105 transition-transform">
            <PlusIcon className="h-5 w-5" />
          </button>
        </form>

        {loading ? (
          <div className="flex justify-center py-12"><Spinner size="lg" /></div>
        ) : items.length === 0 ? (
          <EmptyState title="No items yet" message="Add your first item above" />
        ) : (
          <ul className="divide-y divide-gray-100">
            {items.map(item => (
              <li key={item.id} className="flex items-center justify-between py-3 hover:bg-gray-50 rounded-lg px-2 transition-colors">
                <span className="font-medium text-gray-900">{item.name}</span>
                <button 
                  onClick={() => handleDelete(item.id)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-full transition-colors"
                >
                  <TrashIcon className="h-5 w-5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Layout>
  );
}

export default App;
```
