# Dashboard & UI

## Overview

The platform provides multiple dashboard views for managing AI models, applications, and analysis tasks.

## Dashboard Types

### Main Dashboard (`/`)
- System statistics (models, apps, analyses)
- Recent activity feed
- Quick action buttons
- Resource usage graphs

### SPA Dashboard (`/spa/dashboard`)
- Single-page application version
- Real-time updates via WebSocket
- Interactive charts
- Responsive design

### Analysis Dashboard (`/analysis/dashboard`)
- Task management interface
- Live progress tracking
- Result visualization
- Filter and search tools

## Key Features

### Tabbed Interface
- **Overview**: System stats and metrics
- **Models**: Available AI models and capabilities
- **Applications**: Generated app management
- **Tasks**: Analysis job monitoring

### Real-Time Updates
- WebSocket connection for live progress
- Auto-refresh for task status
- Live log streaming
- Event notifications

### Container Management
- Start/stop/restart containers from UI
- View logs in modal dialogs
- Build images on demand
- Health status indicators

## Technology Stack

- **Frontend**: Bootstrap 5 + HTMX
- **Real-time**: WebSocket via `websocket_gateway.py`
- **Icons**: Font Awesome
- **Charts**: Chart.js (for analytics)

## Customization

Templates located in:
- `src/templates/pages/dashboard/` - Dashboard pages
- `src/templates/pages/spa/` - Single-page app views
- `src/templates/components/` - Reusable UI components
