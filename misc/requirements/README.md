# Requirements Templates

This directory contains application requirement templates in standardized JSON format. Each template defines the specifications for generating a complete full-stack application (React frontend + Flask backend).

## File Format

Each requirements file follows this structure:

```json
{
  "id": <integer>,
  "name": "<string>",
  "description": "<string>",
  "backend_requirements": [<array of strings>],
  "frontend_requirements": [<array of strings>],
  "api_endpoints": [<array of endpoint objects>],
  "control_endpoints": [<array of control endpoint objects>]
}
```

### Naming Convention

**IMPORTANT**: All template files MUST use numeric naming: `{id}.json`
- ✅ Correct: `1.json`, `2.json`, `3.json`, `4.json`
- ❌ Incorrect: `todo_app.json`, `base64_converter.json` (legacy, no longer supported)

This convention ensures consistency across the generation service, Docker containers, and analyzer services.

### Fields

- **id**: Unique numeric identifier (must match filename: `{id}.json`)
- **name**: Display name of the application template
- **description**: Brief description of what the application does
- **backend_requirements**: Array of backend specifications including:
  - SQLAlchemy model definitions
  - API endpoint implementations
  - Database initialization logic
  - Validation rules
  - HTTP status codes and error handling
- **frontend_requirements**: Array of frontend specifications including:
  - UI components and layouts
  - API integration with axios
  - Loading states and error handling
  - Bootstrap 5 styling requirements
  - Responsive design and accessibility
- **api_endpoints**: Array of endpoint specifications with:
  - `method`: HTTP method (GET, POST, PUT, DELETE)
  - `path`: Endpoint path
  - `description`: What the endpoint does
  - `request`: Request body schema (optional)
  - `response`: Response body schema
  - `query_params`: Query parameter schema (optional)
- **control_endpoints**: Array of health/status endpoints for monitoring

## Available Templates

1. **Simple Todo List** (`1.json`)
   - Basic CRUD operations for todos
   - Filter by completion status
   - SQLite database with Todo model

2. **Authors and Books Manager** (`2.json`)
   - Complex one-to-many relationship between Authors and Books
   - Nested JSON serialization
   - Cascade delete operations

3. **Base64 Encoder/Decoder** (`3.json`)
   - Text encoding/decoding operations
   - Conversion history tracking
   - UTF-8 character support

4. **XSD Validator** (`4.json`)
   - XML validation against XSD schemas
   - File upload and preview
   - Validation history with revalidation support
   - lxml library integration

## Usage

Templates are automatically loaded by the generation service. To use a template:

```bash
python scripts/ai_client.py --token <token> generate --model <model> --app-num <num> --template-id <id>
```

Example:
```bash
python scripts/ai_client.py --token "..." generate --model "openai_gpt-4" --app-num 1 --template-id 2
```

## Creating New Templates

To create a new template:

1. Create a new JSON file with the next available ID: `{next_id}.json` (numeric only!)
2. Follow the structure defined above
3. Ensure the `id` field matches the filename (e.g., `5.json` must have `"id": 5`)
4. Include comprehensive `backend_requirements` and `frontend_requirements`
5. Define all `api_endpoints` with complete request/response schemas
6. Add at least one `control_endpoint` for health checking

### Best Practices

- **Backend Requirements**:
  - Always start with "Implement SQLAlchemy model for X"
  - Specify all model fields with types
  - Define relationships explicitly (one-to-many, many-to-many)
  - Include "Initialize database with db.create_all() in setup_app() function"
  - Specify HTTP status codes for all endpoints
  - Include validation requirements

- **Frontend Requirements**:
  - Specify UI components clearly
  - Always include "Use axios to call backend API at http://backend:5000"
  - Include "Show loading states during all API operations"
  - Include "Display error messages when API calls fail"
  - Specify "Use Bootstrap 5 for styling"
  - Include accessibility requirements

- **API Endpoints**:
  - Document all request and response fields
  - Mark required vs optional fields
  - Include data types in parentheses: "string (required)"
  - Provide example response structure

## Technical Details

- All generated apps use **Flask 3.0.0** backend with **SQLAlchemy 2.0.25**
- Frontend uses **React 18.2.0** with **Vite 5.0.0** and **Bootstrap 5.3.2**
- Database: SQLite (development), configurable for production
- Docker Compose orchestration with health checks
- Port allocation: Deterministic based on model hash + app number

## Validation

The generation service validates:
- Template file exists and is valid JSON
- Required fields are present
- ID matches filename
- All endpoint paths are properly formatted
- No duplicate IDs

Templates are cached in memory and reloaded on service restart.
