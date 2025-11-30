# Frontend Scaffolding Context

## Technical Stack
- **React 18** with Vite
- **React Router DOM** - SPA routing
- **Tailwind CSS 3.4** - full utility classes available
- **Heroicons** - `@heroicons/react/24/outline` and `/24/solid`
- **react-hot-toast** - pre-configured, just import `toast`
- **Axios** - HTTP client

## ⚡ BUILT-IN AUTHENTICATION SYSTEM

The scaffolding includes a complete auth system. **Do NOT recreate auth** - use the hooks!

### Authentication Hook
```jsx
import { useAuth } from './components';

function MyComponent() {
  const { 
    user,              // Current user object or null
    isAuthenticated,   // Boolean - logged in?
    isAdmin,           // Boolean - is admin?
    loading,           // Boolean - checking auth status
    login,             // async (username, password) => {success, error}
    register,          // async (username, email, password) => {success, error}
    logout,            // async () => void
    updateProfile,     // async (data) => {success, error}
    requestPasswordReset, // async (email) => {success, resetToken}
    resetPassword,     // async (token, password) => {success, error}
    authApi            // Axios instance with auth headers
  } = useAuth();
  
  // Use authApi for authenticated requests
  const fetchData = async () => {
    const { data } = await authApi.get('/api/items');
  };
}
```

### Pre-built Routes (in main.jsx)
- `/login` - Login/Register page (redirects if already logged in)
- `/admin` - Admin panel (requires admin role)
- `/*` - Your app routes (App.jsx)

### Protected Route Components
```jsx
import { ProtectedRoute, PublicOnlyRoute } from './components';

// Require login
<Route path="/dashboard" element={
  <ProtectedRoute>
    <Dashboard />
  </ProtectedRoute>
} />

// Require admin
<Route path="/settings" element={
  <ProtectedRoute requireAdmin>
    <Settings />
  </ProtectedRoute>
} />

// Only for non-logged-in users
<Route path="/login" element={
  <PublicOnlyRoute>
    <LoginPage />
  </PublicOnlyRoute>
} />
```

### Layout Component (with Auth)
The `Layout` component automatically shows:
- User info + Logout button when logged in
- Admin link when user is admin
- Sign In button when not logged in

```jsx
import { Layout } from './components';

<Layout title="My App" subtitle="Description">
  {/* Your content */}
</Layout>
```

### User Object Shape
```javascript
{
  id: 1,
  username: "admin",
  email: "admin@example.com",  // Only in detailed requests
  is_admin: true,
  is_active: true,
  created_at: "2024-01-01T00:00:00",
  last_login: "2024-01-01T12:00:00"
}
```

### Default Admin Credentials
- **Username**: `admin`
- **Password**: `admin123`

## Architecture Rules (MUST FOLLOW)
1. `src/App.jsx` exports default functional component
2. API calls use relative paths (`/api/items`) - never hardcode localhost
3. Use `authApi` from `useAuth()` for authenticated requests
4. Use `toast.success()` / `toast.error()` for user feedback

## Available Utilities

### Helper Components
```jsx
import { 
  Layout,          // Main app shell with header/footer
  Card,            // Content card container
  PageHeader,      // Section header
  Spinner,         // Loading spinner
  EmptyState,      // Empty state display
  ErrorBoundary,   // Error boundary wrapper
  useAuth,         // Auth hook
  authApi,         // Authenticated axios instance
  ProtectedRoute,  // Route protection
  PublicOnlyRoute, // Non-auth route protection
  LoginPage,       // Pre-built login/register page
  AdminPanel       // Pre-built admin panel
} from './components';
```

### CSS Utility Classes (defined in App.css)
```
Buttons: btn-primary, btn-secondary, btn-danger, btn-success, btn-sm, btn-lg
Forms:   input, input-error, label, form-group
Alerts:  alert-error, alert-success, alert-warning, alert-info
Badges:  badge-primary, badge-success, badge-warning, badge-danger
Tables:  table (auto-styled th/td)
Icons:   icon-btn, icon-btn-primary, icon-btn-danger
Lists:   list-item, list-item-bordered
```

### Tailwind - Full Freedom
Use any Tailwind classes. Common patterns:
- Colors: `bg-{color}-{shade}`, `text-{color}-{shade}` (e.g., `bg-emerald-500`, `text-rose-600`)
- Gradients: `bg-gradient-to-r from-{color} to-{color}`
- Spacing: `p-{n}`, `m-{n}`, `gap-{n}`, `space-y-{n}`
- Layout: `flex`, `grid`, `grid-cols-{n}`, `justify-between`, `items-center`
- Responsive: `sm:`, `md:`, `lg:`, `xl:` prefixes
- Effects: `shadow-{sm|md|lg|xl}`, `rounded-{sm|md|lg|xl|full}`
- Transitions: `transition-all`, `duration-{ms}`, `hover:`, `focus:`

### Icons (ONLY use these exact names from @heroicons/react)
```jsx
import { IconName } from '@heroicons/react/24/outline'; // or /24/solid
```

**Common Icons (verified, use these exact names):**
- Navigation: `HomeIcon`, `ArrowLeftIcon`, `ArrowRightIcon`, `ChevronDownIcon`, `ChevronUpIcon`, `Bars3Icon`, `XMarkIcon`
- Actions: `PlusIcon`, `MinusIcon`, `TrashIcon`, `PencilIcon`, `PencilSquareIcon`, `CheckIcon`, `XMarkIcon`
- User/Auth: `UserIcon`, `UserCircleIcon`, `UserPlusIcon`, `ArrowRightOnRectangleIcon` (logout), `ArrowLeftOnRectangleIcon` (login), `LockClosedIcon`, `LockOpenIcon`, `KeyIcon`, `ShieldCheckIcon`
- Communication: `EnvelopeIcon`, `ChatBubbleLeftIcon`, `BellIcon`, `PhoneIcon`
- Data: `MagnifyingGlassIcon`, `FunnelIcon`, `AdjustmentsHorizontalIcon`, `DocumentIcon`, `FolderIcon`, `ClipboardIcon`
- Status: `CheckCircleIcon`, `ExclamationCircleIcon`, `ExclamationTriangleIcon`, `InformationCircleIcon`, `QuestionMarkCircleIcon`
- Media: `PhotoIcon`, `PlayIcon`, `PauseIcon`, `MusicalNoteIcon`, `FilmIcon`
- Commerce: `ShoppingCartIcon`, `CreditCardIcon`, `CurrencyDollarIcon`, `TagIcon`, `GiftIcon`
- UI: `EyeIcon`, `EyeSlashIcon`, `HeartIcon`, `StarIcon`, `BookmarkIcon`, `ShareIcon`, `LinkIcon`
- Misc: `CalendarIcon`, `ClockIcon`, `MapPinIcon`, `GlobeAltIcon`, `CloudIcon`, `SunIcon`, `MoonIcon`, `Cog6ToothIcon`

**⚠️ DO NOT invent icon names** - If unsure, use a generic icon like `Squares2X2Icon` or skip the icon.

### Toast Notifications
```jsx
import toast from 'react-hot-toast';

toast.success('Saved!');
toast.error('Failed to save');
toast.promise(asyncOperation, {
  loading: 'Saving...',
  success: 'Done!',
  error: 'Error'
});
```

## Code Pattern (with Auth)
```jsx
import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { PlusIcon } from '@heroicons/react/24/outline';
import { Layout, Card, Spinner, useAuth } from './components';

function App() {
  const { user, isAuthenticated, authApi } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { 
    if (isAuthenticated) fetchItems(); 
  }, [isAuthenticated]);

  const fetchItems = async () => {
    try {
      // Use authApi for authenticated requests
      const { data } = await authApi.get('/api/items');
      setItems(data.items || data);
    } catch (err) {
      toast.error('Failed to load');
    } finally {
      setLoading(false);
    }
  };

  const createItem = async (name) => {
    try {
      const { data } = await authApi.post('/api/items', { name });
      setItems([data, ...items]);
      toast.success('Created!');
    } catch (err) {
      toast.error('Failed to create');
    }
  };

  // Use Layout component for consistent header with auth UI
  return (
    <Layout title="My App" subtitle="Description">
      {!isAuthenticated ? (
        <Card>
          <p className="text-center text-gray-500">Please sign in to continue</p>
        </Card>
      ) : loading ? (
        <Spinner size="lg" />
      ) : (
        <Card title="Items">
          {/* Your content here */}
        </Card>
      )}
    </Layout>
  );
}

export default App;
```

## Design Freedom
- Choose your own color scheme (not limited to blue)
- Create your own content structure within the Layout
- Use cards, grids, lists - whatever fits the app
- Add animations, gradients, shadows as you see fit
- Make it visually appropriate for the app's purpose
- Auth UI (header buttons) is handled automatically by Layout
