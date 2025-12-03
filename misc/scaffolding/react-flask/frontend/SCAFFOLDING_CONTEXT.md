```markdown
# Frontend Blueprint Reference

## CRITICAL RULES (READ FIRST)
1. **Use EXACT API paths from requirements** - Replace `/api/YOUR_RESOURCE` with actual paths like `/api/todos`, `/api/books`
2. **Only these components exist**: `Spinner`, `ErrorBoundary` - create others inline if needed
3. **API response format**: List endpoints return `{items: [...], total: N}` - access via `response.data.items`
4. **Write production-ready code**: Include form validation, loading states, error handling, and good UX

## Stack
- React 18, Vite, Tailwind CSS, Axios, Heroicons, react-hot-toast

## Available Imports
```jsx
// These exist in ./components:
import { Spinner, ErrorBoundary } from './components';

// From node_modules:
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { 
  PlusIcon, TrashIcon, CheckIcon, XMarkIcon,
  PencilIcon, MagnifyingGlassIcon, ExclamationCircleIcon,
  ArrowPathIcon, ChevronUpIcon, ChevronDownIcon
} from '@heroicons/react/24/outline';
```

## Complete App Pattern
```jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { PlusIcon, TrashIcon, CheckIcon, PencilIcon, XMarkIcon, MagnifyingGlassIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { Spinner } from './components';

// Constants
const API_BASE = '/api/YOUR_RESOURCE';  // <- REPLACE with actual path from requirements!

function App() {
  // State management
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({ title: '' });
  const [formErrors, setFormErrors] = useState({});
  const [editingId, setEditingId] = useState(null);
  
  // Search/filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOrder, setSortOrder] = useState('desc');

  // Fetch data with error handling
  const fetchItems = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const { data } = await axios.get(API_BASE, {
        params: { sort: 'created_at', order: sortOrder }
      });
      setItems(data.items || []);
    } catch (err) {
      const message = err.response?.data?.error || 'Failed to load items';
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [sortOrder]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Form validation
  const validateForm = () => {
    const errors = {};
    if (!formData.title?.trim()) {
      errors.title = 'Title is required';
    } else if (formData.title.length > 200) {
      errors.title = 'Title must be 200 characters or less';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Handle input changes
  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    // Clear error when user starts typing
    if (formErrors[name]) {
      setFormErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  // Create new item
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    
    try {
      setSubmitting(true);
      const { data } = await axios.post(API_BASE, {
        title: formData.title.trim(),
        // Add other fields from requirements
      });
      setItems(prev => [data, ...prev]);
      setFormData({ title: '' });
      toast.success('Created successfully!');
    } catch (err) {
      const message = err.response?.data?.error || 'Failed to create';
      toast.error(message);
      if (err.response?.data?.field) {
        setFormErrors({ [err.response.data.field]: message });
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Update existing item
  const handleUpdate = async (id, updates) => {
    try {
      const { data } = await axios.put(`${API_BASE}/${id}`, updates);
      setItems(prev => prev.map(item => item.id === id ? data : item));
      setEditingId(null);
      toast.success('Updated successfully!');
    } catch (err) {
      const message = err.response?.data?.error || 'Failed to update';
      toast.error(message);
    }
  };

  // Toggle completion (for items with completed field)
  const handleToggleComplete = async (item) => {
    try {
      const { data } = await axios.put(`${API_BASE}/${item.id}`, {
        completed: !item.completed
      });
      setItems(prev => prev.map(i => i.id === item.id ? data : i));
    } catch (err) {
      toast.error('Failed to update');
    }
  };

  // Delete with confirmation
  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this item?')) return;
    
    try {
      await axios.delete(`${API_BASE}/${id}`);
      setItems(prev => prev.filter(item => item.id !== id));
      toast.success('Deleted successfully!');
    } catch (err) {
      const message = err.response?.data?.error || 'Failed to delete';
      toast.error(message);
    }
  };

  // Filtered and sorted items
  const filteredItems = useMemo(() => {
    if (!searchTerm.trim()) return items;
    const term = searchTerm.toLowerCase();
    return items.filter(item => 
      item.title?.toLowerCase().includes(term) ||
      item.description?.toLowerCase().includes(term)
    );
  }, [items, searchTerm]);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Spinner size="lg" />
          <p className="mt-4 text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && items.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button
            onClick={fetchItems}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 mx-auto"
          >
            <ArrowPathIcon className="h-5 w-5" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-blue-600 text-white py-6 shadow-lg">
        <div className="container mx-auto px-4">
          <h1 className="text-2xl font-bold">App Title</h1>
          <p className="text-blue-100 mt-1">Manage your items efficiently</p>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 max-w-3xl">
        {/* Add Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Add New Item</h2>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleInputChange}
                placeholder="Enter title..."
                className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition ${
                  formErrors.title ? 'border-red-500' : 'border-gray-300'
                }`}
                disabled={submitting}
              />
              {formErrors.title && (
                <p className="mt-1 text-sm text-red-500">{formErrors.title}</p>
              )}
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition"
            >
              {submitting ? (
                <Spinner size="sm" />
              ) : (
                <>
                  <PlusIcon className="h-5 w-5" />
                  <span>Add</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Search and Sort Controls */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search items..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            />
          </div>
          <button
            onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
          >
            {sortOrder === 'desc' ? 'Newest First' : 'Oldest First'}
          </button>
          <button
            onClick={fetchItems}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            title="Refresh"
          >
            <ArrowPathIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Item Count */}
        <div className="mb-4 text-sm text-gray-500">
          {filteredItems.length} of {items.length} items
          {searchTerm && ` matching "${searchTerm}"`}
        </div>

        {/* Items List */}
        {filteredItems.length === 0 ? (
          <div className="bg-white rounded-lg shadow-md p-12 text-center">
            <div className="text-gray-400 mb-4">
              <svg className="h-16 w-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <p className="text-gray-500 text-lg">
              {searchTerm ? 'No items match your search' : 'No items yet'}
            </p>
            <p className="text-gray-400 mt-2">
              {searchTerm ? 'Try a different search term' : 'Add your first item above!'}
            </p>
          </div>
        ) : (
          <ul className="bg-white rounded-lg shadow-md divide-y divide-gray-200">
            {filteredItems.map(item => (
              <li key={item.id} className="p-4 hover:bg-gray-50 transition">
                <div className="flex items-center justify-between gap-4">
                  {/* Item checkbox for completion toggle */}
                  <button
                    onClick={() => handleToggleComplete(item)}
                    className={`flex-shrink-0 h-6 w-6 rounded-full border-2 flex items-center justify-center transition ${
                      item.completed 
                        ? 'bg-green-500 border-green-500 text-white' 
                        : 'border-gray-300 hover:border-green-500'
                    }`}
                  >
                    {item.completed && <CheckIcon className="h-4 w-4" />}
                  </button>
                  
                  {/* Item content */}
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium truncate ${item.completed ? 'line-through text-gray-400' : 'text-gray-900'}`}>
                      {item.title}
                    </p>
                    {item.description && (
                      <p className="text-sm text-gray-500 truncate">{item.description}</p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      Created: {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  
                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setEditingId(editingId === item.id ? null : item.id)}
                      className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
                      title="Edit"
                    >
                      <PencilIcon className="h-5 w-5" />
                    </button>
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                      title="Delete"
                    >
                      <TrashIcon className="h-5 w-5" />
                    </button>
                  </div>
                </div>
                
                {/* Inline edit form */}
                {editingId === item.id && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <EditForm 
                      item={item} 
                      onSave={(updates) => handleUpdate(item.id, updates)}
                      onCancel={() => setEditingId(null)}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>

      {/* Footer */}
      <footer className="text-center py-6 text-gray-500 text-sm border-t border-gray-200 mt-8">
        <p>© {new Date().getFullYear()} App Name. All rights reserved.</p>
      </footer>
    </div>
  );
}

// Inline edit form component
function EditForm({ item, onSave, onCancel }) {
  const [title, setTitle] = useState(item.title || '');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    await onSave({ title: title.trim() });
    setSaving(false);
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        autoFocus
      />
      <button
        type="submit"
        disabled={saving || !title.trim()}
        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400"
      >
        {saving ? <Spinner size="sm" /> : <CheckIcon className="h-5 w-5" />}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
      >
        <XMarkIcon className="h-5 w-5" />
      </button>
    </form>
  );
}

export default App;
```

## Tailwind Quick Reference
- **Layout**: `flex`, `grid`, `justify-between`, `items-center`, `gap-{n}`, `min-w-0` (for truncate)
- **Spacing**: `p-{n}`, `m-{n}`, `py-{n}`, `px-{n}`, `space-y-{n}`
- **Colors**: `bg-blue-600`, `text-white`, `text-gray-500`, `hover:bg-blue-700`
- **Effects**: `shadow-md`, `rounded-lg`, `hover:shadow-lg`, `transition`
- **States**: `disabled:bg-gray-400`, `disabled:cursor-not-allowed`, `focus:ring-2`
- **Typography**: `font-bold`, `text-lg`, `truncate`, `line-through`

## Quality Checklist
- [ ] Loading spinner while fetching data
- [ ] Error state with retry button
- [ ] Form validation with error messages
- [ ] Submit button shows loading state
- [ ] Delete confirmation dialog
- [ ] Empty state with helpful message
- [ ] Toast notifications for actions
- [ ] Search/filter functionality
- [ ] Keyboard accessible (forms work with Enter)
```
