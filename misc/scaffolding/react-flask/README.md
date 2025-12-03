# React-Flask Scaffolding Blueprint

Minimal blueprint providing Docker infrastructure for React + Flask applications.
**Model implements all application logic** based on requirements.

## Structure

```
react-flask/
├── docker-compose.yml      # Container orchestration
├── .env.example            # Environment template
├── backend/
│   ├── Dockerfile          # Python container config
│   ├── app.py              # Flask skeleton (model adds models/routes)
│   ├── requirements.txt    # Python dependencies
│   └── SCAFFOLDING_CONTEXT.md  # Backend patterns reference
└── frontend/
    ├── Dockerfile          # Node container config
    ├── nginx.conf          # Production static serving
    ├── package.json        # Node dependencies
    ├── vite.config.js      # Vite build config
    ├── tailwind.config.js  # Tailwind config
    ├── index.html          # HTML entry
    ├── SCAFFOLDING_CONTEXT.md  # Frontend patterns reference
    └── src/
        ├── main.jsx        # React entry (minimal)
        ├── App.jsx         # App component (model implements)
        ├── App.css         # Tailwind imports
        └── components/     # Minimal utilities only
            ├── Spinner.jsx
            └── ErrorBoundary.jsx
```

## What This Provides

### Infrastructure (Fixed)
- Docker containers for backend/frontend
- SQLite database at `/app/data/app.db`
- CORS configured between services
- Nginx reverse proxy for production
- Health check endpoint at `/api/health`

### Available Stack (Model Uses As Needed)
- **Backend**: Flask, SQLAlchemy, Flask-JWT-Extended, bcrypt
- **Frontend**: React 18, React Router, Tailwind CSS, Axios, Heroicons, react-hot-toast

## What Model Implements

Based on application requirements:
- Database models in `backend/app.py`
- API routes in `backend/app.py`
- React components in `frontend/src/App.jsx`
- Authentication (if requirements specify it)
- All business logic and UI

## Usage

Model receives this scaffolding + requirements JSON, then:
1. Adds models to `backend/app.py` MODELS section
2. Adds routes to `backend/app.py` ROUTES section  
3. Implements UI in `frontend/src/App.jsx`
4. Uses patterns from `SCAFFOLDING_CONTEXT.md` as reference

## Ports

Configured via `.env`:
- `BACKEND_PORT`: Flask API (default 5000)
- `FRONTEND_PORT`: React app (default 8000)
