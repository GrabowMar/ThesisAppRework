# Requirements Templates

This directory contains 30 **simple, single-feature application templates** for code generation. Each template represents a focused "glorified feature" rather than a complex system.

## Philosophy

Templates are intentionally minimal:
- **Backend**: ~4-5 requirements (model + endpoints + validation + behavior)
- **Frontend**: ~4-5 requirements (display + interaction + basic UX + states)
- **Admin**: optional but recommended for guarded 4-query (list-all, toggle, bulk ops, stats)
- **Single Purpose**: Each app does ONE thing well

Examples:
- **Todo List**: Add, complete, delete tasks
- **XML Validator**: Check if XML is well-formed  
- **URL Shortener**: Create and use short URLs
- **Flashcards**: Show question, flip to answer, next card

## Naming Convention

**Template files use semantic slug naming:** `{category}_{name}.json`

Examples:
- `crud_todo_list.json` - Basic CRUD operations
- `auth_user_management.json` - User authentication system
- `realtime_chat_application.json` - WebSocket-based chat

This naming makes templates discoverable and easier for LLMs to understand.

## File Format

Each requirements file follows this structure:

```json
{
  "slug": "category_name",
  "category": "Category Name",
  "name": "Display Name",
  "description": "Brief description",
  "backend_requirements": ["..."],
  "frontend_requirements": ["..."],
  "api_endpoints": [{...}],
  "control_endpoints": [{...}]  // optional
}
```

### Required Fields

- **slug**: Unique identifier matching filename (e.g., `crud_todo_list`)
- **category**: Category for grouping (CRUD, Authentication, Real-time, etc.)
- **name**: Human-readable display name
- **description**: Brief description of the application
- **backend_requirements**: Array of backend specifications
- **frontend_requirements**: Array of frontend specifications
- **api_endpoints**: Array of REST API endpoint definitions
- **control_endpoints**: Optional health/status endpoints for monitoring

### Endpoint Schema Notes

- **method**: One of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`, or `WS`.
- **path**: Must start with `/`. For HTTP APIs, prefer `/api/...` paths (the validator warns on non-`/api/` paths).
- **request/response**: Must be **object**, **array**, or **null**.
  - Use `null` for endpoints that do not return JSON (e.g., redirects, file downloads/streams).
  - For `multipart/form-data` uploads, use an object describing the content type and expected form fields.

## Available Templates (30 Simple Features)

**CRUD** (2): Todo List, Book List  
**Authentication** (1): User Login  
**Real-time** (1): Chat Room  
**API Integration** (2): Weather Display, URL Shortener  
**Data Visualization** (1): Sales Table  
**E-commerce** (1): Shopping Cart  
**File Processing** (1): Image Upload  
**Scheduling** (1): Event List  
**Social** (1): Blog Posts  
**Productivity** (1): Notes App  
**Workflow** (1): Task Board  
**Finance** (1): Expense Tracker  
**Utility** (1): Base64 Converter  
**Validation** (1): XML Checker  
**Monitoring** (1): Server Stats  
**Content** (1): Recipe List  
**Collaboration** (1): Simple Poll  
**Media** (1): Audio Player  
**Geolocation** (1): Store Locator  
**Inventory** (1): Stock Tracker  
**Healthcare** (1): Appointments  
**Gaming** (1): Leaderboard  
**Messaging** (1): Notifications  
**IoT** (1): Sensor Display  
**CRM** (1): Customer List  
**Learning** (1): Flashcards  
**Booking** (1): Reservations  
**Education** (1): Quiz App

## Usage

Templates are automatically loaded by the generation service. To use a template:

```python
# Via API
POST /api/gen/generate
{
  "model_slug": "openai_gpt-4",
  "app_num": 1,
  "template_slug": "crud_todo_list"
}
```

```bash
# Via CLI (if available)
python scripts/generate.py --model openai_gpt-4 --app 1 --template crud_todo_list
```

## Creating New Templates

Keep it **simple and focused**:

1. **One core feature only** - No complex multi-feature systems
2. **Minimal requirements** - 2 backend, 3 frontend items maximum  
3. **Clear outcome** - User knows exactly what the app does
4. **Self-contained** - Works standalone (except external APIs)

### Template Structure

```json
{
  "slug": "category_feature",
  "name": "Feature Name",
  "category": "Category",
  "description": "One-line what it does",
  "backend_requirements": [
    "REST API endpoints",
    "Storage schema"
  ],
  "frontend_requirements": [
    "Display component",
    "Input/interaction",
    "Basic UX"
  ],
  "api_endpoints": [...],
  "control_endpoints": [...]
}
```

## Technical Stack

- **Backend:** Flask + SQLAlchemy + SQLite (see scaffolding for exact versions)
- **Frontend:** React + Vite + Tailwind (available in scaffolding) + axios
- **Deployment:** Docker Compose with health checks
- **Port Allocation:** Deterministic based on model + app number

## Validation

The generation service validates:
- Template slug matches filename
- All required fields are present
- No duplicate slugs
- Valid JSON format
- Endpoint paths are properly formatted

Templates are cached in memory and support hot-reloading.
