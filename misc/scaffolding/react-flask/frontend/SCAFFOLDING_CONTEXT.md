# Frontend Blueprint Reference

## Stack
- **React 18** with Vite
- **React Router DOM** for routing
- **Tailwind CSS 3.4** for styling
- **Heroicons** (`@heroicons/react/24/outline`, `/24/solid`)
- **react-hot-toast** for notifications
- **Axios** for HTTP

## Architecture Rules
1. `src/App.jsx` exports default component
2. API calls use relative paths (`/api/items`)
3. Use `toast.success()`/`toast.error()` for feedback

## Available Utilities
```jsx
import { Spinner, ErrorBoundary } from './components';
import toast from 'react-hot-toast';
import axios from 'axios';
```

## Patterns

### Data Fetching
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';

function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('/api/items')
      .then(res => setItems(res.data))
      .catch(() => toast.error('Failed to load'))
      .finally(() => setLoading(false));
  }, []);
  
  if (loading) return <Spinner />;
  return <div>{/* render items */}</div>;
}
```

### Form Handling
```jsx
const [form, setForm] = useState({ name: '' });

const handleSubmit = async (e) => {
  e.preventDefault();
  try {
    const { data } = await axios.post('/api/items', form);
    setItems([...items, data]);
    setForm({ name: '' });
    toast.success('Created!');
  } catch {
    toast.error('Failed');
  }
};
```

### Routing (if multiple pages needed)
```jsx
import { Routes, Route, Link, useNavigate, useParams } from 'react-router-dom';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/items/:id" element={<ItemDetail />} />
    </Routes>
  );
}
```

### Auth (if requirements need it)
```jsx
const [token, setToken] = useState(localStorage.getItem('token'));

const login = async (username, password) => {
  const { data } = await axios.post('/api/auth/login', { username, password });
  localStorage.setItem('token', data.token);
  setToken(data.token);
};

// Add token to requests
axios.defaults.headers.common['Authorization'] = token ? `Bearer ${token}` : '';
```

## Tailwind Shortcuts
- Layout: `flex`, `grid`, `grid-cols-{n}`, `gap-{n}`, `justify-between`, `items-center`
- Spacing: `p-{n}`, `m-{n}`, `space-y-{n}`
- Colors: `bg-{color}-{shade}`, `text-{color}-{shade}`
- Effects: `shadow`, `rounded-lg`, `hover:`, `transition`
- Responsive: `sm:`, `md:`, `lg:`

## Common Icons
```jsx
import { PlusIcon, TrashIcon, PencilIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline';
```
