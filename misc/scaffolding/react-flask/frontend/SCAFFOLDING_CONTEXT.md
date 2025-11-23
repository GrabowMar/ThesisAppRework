# Frontend Scaffolding Context

## Technical Stack
- **Framework**: React 18 (Vite)
- **Styling**: Bootstrap 5 (loaded globally)
- **HTTP Client**: Axios
- **Routing**: Single Page Application (SPA)

## Architecture Constraints
1. **Entry Point**: `src/App.jsx` MUST export a default functional component.
2. **API Communication**:
   - Use relative paths for ALL API requests (e.g., `/api/items`).
   - **NEVER** hardcode `localhost` or ports (e.g., `http://localhost:5000`).
   - Nginx handles the proxying to the backend.
   - Define `const API_URL = '';` at the top of the file.
3. **State Management**: Use React Hooks (`useState`, `useEffect`).
4. **UI Components**: Use Bootstrap 5 classes (e.g., `card`, `btn`, `alert`).

## Code Pattern
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = ''; // Relative path for Nginx proxy

function App() {
  const [data, setData] = useState([]);

  useEffect(() => {
    axios.get(`${API_URL}/api/items`)
      .then(res => setData(res.data))
      .catch(err => console.error(err));
  }, []);

  return (
    <div className="container">
      <h1>App</h1>
    </div>
  );
}

export default App;
```
