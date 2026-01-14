# Frontend Scaffolding Context

## Structure
```
frontend/src/
├── main.jsx          # Entry point - LLM adds providers
├── App.jsx           # LLM implements routing + layout
├── App.css           # Tailwind imports
├── pages/
│   ├── index.js      # Exports (don't modify)
│   ├── LoginPage.jsx # LLM implements auth form
│   ├── UserPage.jsx  # LLM implements user UI
│   └── AdminPage.jsx # LLM implements admin dashboard
├── services/
│   ├── api.js        # LLM adds API functions
│   └── auth.js       # LLM implements auth service
├── hooks/
│   ├── useAuth.jsx   # LLM implements auth context
│   └── useData.js    # LLM adds custom hooks
└── components/
    ├── index.js      # Exports
    ├── Spinner.jsx   # Ready to use
    └── ErrorBoundary.jsx # Ready to use
```

## What LLM Must Implement

### 1. Auth Service (services/auth.js)
```javascript
export const setToken = (token) => localStorage.setItem('auth_token', token);
export const getToken = () => localStorage.getItem('auth_token');
export const clearToken = () => localStorage.clear();
export const isAuthenticated = () => !!getToken();

export const login = async (username, password) => {
  const res = await api.post('/auth/login', { username, password });
  if (res.data.token) setToken(res.data.token);
  return res;
};

// Add interceptor to inject token into requests
api.interceptors.request.use(config => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
```

### 2. Auth Context (hooks/useAuth.jsx)
- State: `user`, `loading`, `isAuthenticated`
- Functions: `login(username, pw)`, `register(data)`, `logout()`
- On mount: check `isAuthenticated()`, fetch user with `getMe()`
- Expose: `isAdmin: user?.is_admin`

### 3. App Routing (App.jsx)
```jsx
<Routes>
  <Route path="/" element={<UserPage />} />
  <Route path="/login" element={<LoginPage />} />
  <Route path="/admin" element={<ProtectedRoute requireAdmin><AdminPage /></ProtectedRoute>} />
</Routes>
```

### 4. API Functions (services/api.js)
- User routes call `/api/*`
- Admin routes call `/api/admin/*`
- Auth routes call `/api/auth/*`

## Stack
React 18, axios, react-router-dom, react-hot-toast, Tailwind CSS

## Patterns
- Use `toast.success()` / `toast.error()` for notifications
- Handle `err.response?.data?.error || err.message` for errors
- Always show loading states with `<Spinner />`
