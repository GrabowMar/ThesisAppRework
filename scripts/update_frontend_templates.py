"""Update Frontend Templates with Best Practices
==============================================

Apply research-based improvements to frontend templates.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.paths import MISC_DIR


def update_frontend_step1():
    """Update frontend step 1 with few-shot example."""
    template_path = MISC_DIR / 'templates' / 'minimal' / 'frontend_step1_structure.md.jinja2'
    
    content = '''# Task: Build React UI for {{ name }}

{{ description }}

## Let's Think Step by Step

**Systematic Approach:**
1. Understand the API endpoints
2. Plan the component structure (all in one file!)
3. Design the state management
4. Implement the UI with React hooks

## API Endpoints Available

{% for endpoint in endpoints %}
- **{{ endpoint.method }} {{ endpoint.path }}** - {{ endpoint.description }}
{% endfor %}

## User Requirements

Create UI that allows users to:
{% for verify in verification %}
- {{ verify }}
{% endfor %}

## Technical Stack

- React 18 with hooks (useState, useEffect)
- Axios for API calls
- Vite build system
- CSS for styling

## EXAMPLE: Professional React Component

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({ name: '', description: '' });

  const fetchItems = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/items');
      setItems(response.data);
      setError('');
    } catch (err) {
      setError('Failed to load items');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post('/api/items', formData);
      setFormData({ name: '', description: '' });
      fetchItems();
    } catch (err) {
      setError('Failed to create item');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Item Manager</h1>
      </header>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="container">
        <form onSubmit={handleSubmit} className="form">
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({...formData, name: e.target.value})}
            placeholder="Name"
            required
          />
          <textarea
            value={formData.description}
            onChange={(e) => setFormData({...formData, description: e.target.value})}
            placeholder="Description"
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Adding...' : 'Add Item'}
          </button>
        </form>

        <div className="items-list">
          {items.map(item => (
            <div key={item.id} className="item-card">
              <h3>{item.name}</h3>
              <p>{item.description}</p>
              <span className="timestamp">{new Date(item.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;
```

```css
.app {
  min-height: 100vh;
  background: #f5f5f5;
}

.app-header {
  background: #2c3e50;
  color: white;
  padding: 1.5rem;
  text-align: center;
}

.container {
  max-width: 800px;
  margin: 2rem auto;
  padding: 0 1rem;
}

.form {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 2rem;
}

.form input, .form textarea {
  width: 100%;
  padding: 0.75rem;
  margin-bottom: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.form button {
  width: 100%;
  padding: 0.75rem;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}

.form button:hover {
  background: #2980b9;
}

.form button:disabled {
  background: #95a5a6;
  cursor: not-allowed;
}

.alert {
  padding: 1rem;
  margin: 1rem;
  border-radius: 4px;
}

.alert-error {
  background: #e74c3c;
  color: white;
}

.items-list {
  display: grid;
  gap: 1rem;
}

.item-card {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.item-card h3 {
  margin: 0 0 0.5rem 0;
  color: #2c3e50;
}

.item-card p {
  color: #7f8c8d;
  margin: 0 0 0.5rem 0;
}

.timestamp {
  font-size: 0.875rem;
  color: #95a5a6;
}
```

## Your Task

**Follow the example to build your React app.**

### Critical Requirements:

1. **Single File Implementation**
   - ALL code in App.jsx (NO separate components!)
   - ALL styles in App.css
   - NO external component imports

2. **React Patterns**
   - Use useState for state
   - Use useEffect for data fetching
   - Handle loading states
   - Handle error states

3. **API Integration**
   - Use relative paths (`/api/items`)
   - Use axios for HTTP
   - Handle errors gracefully

4. **Styling**
   - Responsive design
   - Modern look
   - Use unicode symbols for icons: ✓ ✗ ⟳ 🗑️ ➕

## Deliverables

1. **src/App.jsx** (200-300 lines)
2. **src/App.css** (150-200 lines)

**DO NOT** generate:
- package.json (provided by build system)
- index.html (provided by build system)
- main.jsx (provided by build system)

## Checklist

- ✓ All functionality in App.jsx only
- ✓ Professional styling in App.css
- ✓ Loading states
- ✓ Error handling
- ✓ Responsive design
- ✗ NO separate component files
- ✗ NO external imports (except React, axios)
'''
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated {template_path.name}")


def update_frontend_step2():
    """Update frontend step 2 template."""
    template_path = MISC_DIR / 'templates' / 'minimal' / 'frontend_step2_enhance.md.jinja2'
    
    content = '''# Task: Enhance {{ name }} UI

Add advanced features to create a professional application.

## Enhancement Goals

1. **Advanced Features**
   - Add filtering by multiple criteria
   - Add sorting (ascending/descending)
   - Add search functionality
   - Add pagination or "load more"

2. **Better UX**
   - Add form validation with real-time feedback
   - Add confirmation dialogs (inline, no external components!)
   - Add success messages
   - Add keyboard shortcuts

3. **Professional Styling**
   - Smooth transitions and animations
   - Hover effects
   - Focus states
   - Better spacing and typography
   - Dark/light color scheme

4. **Performance**
   - Debounce search inputs (implement inline)
   - Cache API responses
   - Optimistic UI updates

## CRITICAL: Everything in App.jsx

- Implement modals/toasts as inline JSX in App component
- Implement debounce function inline in App.jsx
- Use unicode symbols: ✓ ✗ ⟳ 🗑️ ➕ ⬆️ ⬇️ 🔍 ⚙️

Example inline modal:
```jsx
{showModal && (
  <div className="modal-overlay" onClick={() => setShowModal(false)}>
    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
      <h2>Confirm Delete</h2>
      <p>Are you sure?</p>
      <button onClick={handleDelete}>Yes</button>
      <button onClick={() => setShowModal(false)}>No</button>
    </div>
  </div>
)}
```

## Target

**Expand to 400-500 lines in App.jsx and 250-300 lines in App.css**

Make it feature-rich and professional!
'''
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated {template_path.name}")


def update_frontend_step3():
    """Update frontend step 3 template."""
    template_path = MISC_DIR / 'templates' / 'minimal' / 'frontend_step3_polish.md.jinja2'
    
    content = '''# Task: Polish {{ name }} UI

Add final production features.

## Final Features

1. **Complete Accessibility**
   - ARIA labels on all elements
   - Full keyboard navigation
   - Focus indicators
   - Semantic HTML

2. **Advanced Performance**
   - React.memo for optimization
   - Debouncing (inline implementation)
   - Request caching

3. **User Feedback**
   - Loading indicators everywhere
   - Empty states with messages
   - Helpful error messages
   - Success confirmations

4. **Additional Features**
   - Keyboard shortcuts guide
   - Data persistence (localStorage)
   - Auto-retry failed requests
   - Optimistic updates

5. **Professional Polish**
   - Remove console.logs
   - Remove TODOs
   - Consistent code style
   - Smooth animations

## Target

**Final deliverable: 600-800 lines minimum**
- App.jsx: 500-600 lines
- App.css: 300-400 lines

Make this enterprise-grade and fully featured!

## Remember

- Still ALL in App.jsx only
- NO separate component files
- NO external libraries except React and axios
'''
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated {template_path.name}")


def main():
    """Run all frontend updates."""
    print("Updating Frontend Templates")
    print("=" * 60)
    
    update_frontend_step1()
    update_frontend_step2()
    update_frontend_step3()
    
    print("\n" + "=" * 60)
    print("✓ All frontend templates updated!")


if __name__ == "__main__":
    main()
