# Frontend Scaffolding Context

## Single File Structure
```
frontend/src/
├── main.jsx    # Entry point - DO NOT MODIFY
├── App.jsx     # ALL CODE GOES HERE - components, pages, auth
└── App.css     # Tailwind imports
```

## App.jsx Sections to Implement
1. **API CLIENT** - Add API functions for your endpoints
2. **AUTH CONTEXT** - Implement auth state, login/register/logout
3. **LOGIN PAGE** - Login/register form with validation
4. **USER PAGE** - Main user interface with CRUD
5. **ADMIN PAGE** - Admin dashboard with stats/tables

## Adding Dependencies
Add to package.json dependencies object:
```json
"recharts": "^2.12.0"
```

## Available Packages
react, react-dom, react-router-dom, axios, react-hot-toast, @heroicons/react, date-fns, clsx

## Toast Notifications
```jsx
import toast from 'react-hot-toast';
toast.success('Saved!');
toast.error('Error message');
```

## File Extensions
- React components: `.jsx`
- Must use default export for App
