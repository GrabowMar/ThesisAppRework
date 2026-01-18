# React-Flask Scaffolding

Lightweight scaffolding for React + Flask apps. Provides Docker infrastructure and minimal boilerplate.
**Model generates all application logic** based on requirements.

## Structure

```
react-flask/
├── docker-compose.yml      # Container orchestration
├── .env.example            # Environment template
├── backend/
│   ├── Dockerfile          # Python container
│   ├── app.py              # Flask skeleton → model implements
│   ├── requirements.txt    # Python dependencies
│   └── SCAFFOLDING_CONTEXT.md  # Quick reference for common patterns
└── frontend/
    ├── Dockerfile          # Node container (builds with Vite)
    ├── nginx.conf          # Static serving
    ├── package.json        # Node dependencies
    ├── vite.config.js      # Build config
    ├── tailwind.config.js  # Styling config
    ├── index.html          # Entry HTML
    ├── SCAFFOLDING_CONTEXT.md  # Quick reference for common patterns
    └── src/
        ├── main.jsx        # React entry
        ├── App.jsx         # COMPLETE application (all code in one file)
        ├── App.css         # Tailwind imports
        └── components/     # Utilities: Spinner, ErrorBoundary
```

## What's Provided (Fixed)
- Docker containers for backend/frontend
- SQLite database at `/app/data/app.db`
- CORS, Nginx proxy, health check endpoint (/api/health)
- Tailwind CSS, Axios, react-hot-toast, heroicons pre-configured

## What Model Generates
- Backend: ONE complete `app.py` file with all models, routes, and business logic
- Frontend: ONE complete `App.jsx` file with all components, auth, routing, and pages
- App.jsx contains HomePage serving both public (read-only) and logged-in (full CRUD) users via conditional rendering

## Ports
- `BACKEND_PORT`: Flask API (default 5000)
- `FRONTEND_PORT`: React app (default 8000)
