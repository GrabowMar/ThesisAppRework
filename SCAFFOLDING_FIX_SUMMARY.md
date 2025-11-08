# Scaffolding Fix Summary

## Issue Identified
**Frontend API URL Configuration - CRITICAL BUG**

### Root Cause
Templates instructed AI models to use `const API_URL = 'http://backend:5000';` in React code, which:
- ❌ Works only for server-side rendering or backend-to-backend calls
- ❌ Fails in browser because `backend` hostname is not resolvable from client machines
- ❌ Causes "Failed to fetch" errors in all generated apps

### Why This Happened
The templates confused **Docker internal networking** (used by Nginx/Vite proxies to forward requests) with **client-side browser networking** (where React code actually runs).

## Architecture Explained

### Correct Request Flow
```
Browser → Frontend (http://localhost:8039)
    ↓
React App.jsx uses relative URL: fetch('/api/todos')
    ↓
Nginx/Vite Proxy intercepts /api/* requests
    ↓
Proxies to backend container: http://backend:5039
    ↓
Backend responds
```

### Incorrect Flow (Before Fix)
```
Browser → Frontend (http://localhost:8039)
    ↓
React App.jsx tries: fetch('http://backend:5000/api/todos')
    ↓
Browser cannot resolve 'backend' hostname
    ↓
ERR_NAME_NOT_RESOLVED or Failed to fetch
```

## Scaffolding Components Analysis

### ✅ CORRECT - No Changes Needed
1. **nginx.conf** - Proxies `/api/` to `http://backend:{{port}}`
2. **vite.config.js** - Proxies `/api` to `http://localhost:{{port}}`
3. **docker-compose.yml** - Correct network setup, backend service named `backend`
4. **Backend Dockerfile** - Healthchecks use `http://localhost:{{port}}/health`

### ❌ INCORRECT - Fixed
1. **frontend.md.jinja2** - Told models to use `http://backend:5000`
2. **frontend_compact.md.jinja2** - Told models to use `http://backend:5000`

## Files Fixed

### misc/templates/two-query/frontend.md.jinja2
**Before:**
```jinja
## Backend API
Backend runs at `http://backend:5000` (Docker container networking)

## Critical Constraints
**API URL:** Must use `const API_URL = 'http://backend:5000';` (Docker networking, NOT localhost)
```

**After:**
```jinja
## Backend API
Backend API is available at `/api/*` paths (proxied by Nginx/Vite to backend container)

## Critical Constraints
**API URL:** Must use `const API_URL = '';` (empty string for relative URLs, proxied to backend)
```

**Example Code Before:**
```jsx
const API_URL = 'http://backend:5000';
```

**Example Code After:**
```jsx
const API_URL = ''; // Empty string - use relative URLs (proxied to backend)
```

### misc/templates/two-query/frontend_compact.md.jinja2
**Before:**
```
- API_URL = 'http://backend:5000' (Docker, NOT localhost)
```

**After:**
```
- API_URL = '' (empty string for relative URLs, proxied to backend)
```

## Impact Assessment

### Before Fix
- ✅ All scaffolding infrastructure correct
- ✅ Nginx proxy configured correctly
- ✅ Vite proxy configured correctly
- ❌ **Generated React code used wrong API URL**
- Result: 0% functional apps (all fail to fetch data)

### After Fix
- ✅ All scaffolding infrastructure correct
- ✅ Nginx proxy configured correctly
- ✅ Vite proxy configured correctly
- ✅ **Generated React code will use relative URLs**
- Expected: Near 100% functional apps (models follow corrected templates)

## Deployment Modes Supported

### Development Mode (Vite Dev Server)
```bash
cd frontend
npm run dev
```
- Runs on `http://localhost:8039`
- Vite proxy forwards `/api/*` to `http://localhost:5039`
- React code uses relative URLs: `fetch('/api/todos')`
- ✅ Works with empty string API_URL

### Production Mode (Docker + Nginx)
```bash
docker-compose up
```
- Frontend runs on `http://localhost:8039` (Nginx)
- Backend runs on `http://localhost:5039` (Flask)
- Nginx proxy forwards `/api/*` to `http://backend:5039` (internal Docker network)
- React code uses relative URLs: `fetch('/api/todos')`
- ✅ Works with empty string API_URL

## Verification Needed

To confirm the fix works, need to:
1. ❌ Delete existing generated apps (they have the bug)
2. ❌ Regenerate apps with fixed templates
3. ❌ Test in browser - should successfully fetch data
4. ❌ Verify no "Failed to fetch" errors in console

## Related Files
- `misc/templates/two-query/frontend.md.jinja2` - ✅ FIXED
- `misc/templates/two-query/frontend_compact.md.jinja2` - ✅ FIXED
- `misc/scaffolding/react-flask/frontend/nginx.conf` - ✅ Already correct
- `misc/scaffolding/react-flask/frontend/vite.config.js` - ✅ Already correct
- `misc/scaffolding/react-flask/docker-compose.yml` - ✅ Already correct

## Conclusion

**This was a SCAFFOLDING FAULT, not a model fault.**

Both GPT-3.5 Turbo and Claude 4.5 Sonnet correctly followed the (incorrect) instructions in the templates. The fix is simple: use empty string for API_URL to enable relative URLs that work with the proxy infrastructure already in place.

**Expected Outcome:** After regeneration, all apps should work perfectly in both dev and production modes.
