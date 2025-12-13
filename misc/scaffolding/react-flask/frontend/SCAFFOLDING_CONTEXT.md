# Frontend Context

## Stack
React 18, Axios, Tailwind CSS, react-hot-toast, @heroicons/react

## Pre-built
```jsx
import { Spinner, ErrorBoundary } from './components';
```

## Rules
1. API calls to `/api/...`
2. Use axios for HTTP
3. Use toast for notifications
4. Handle loading + errors

## Patterns (Pseudocode)

### State
```
items = [], loading = true, formData = {...}
```

### Fetch
```
on mount: GET → set items (handle {items:[]} or []) → loading false
on error → toast
```

### CRUD
```
create: POST → add to list → toast
update: PUT → update in list → toast  
delete: confirm → DELETE → remove → toast
```

## UI Structure
```
header, form, item list (with key=id), empty state
```

## Gotchas
- Response: `{items:[]}` or `[]`
- Errors: `err.response?.data?.error`
- Lists: `key={item.id}`
