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
        ├── App.jsx         # Main component → model implements
        ├── App.css         # Tailwind imports
        └── components/     # Utilities: Spinner, ErrorBoundary
```

## What's Provided (Fixed)
- Docker containers for backend/frontend
- SQLite database at `/app/data/app.db`
- CORS, Nginx proxy, health check endpoint
- Tailwind CSS, Axios, react-hot-toast, heroicons pre-configured

## What Model Generates
- Database models and API routes (in `app.py` or separate files)
- React UI (in `App.jsx` or additional components)
- All business logic per requirements

## Ports
- `BACKEND_PORT`: Flask API (default 5000)
- `FRONTEND_PORT`: React app (default 8000)
