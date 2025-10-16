# Prompt Template for Backend Generation

{scaffolding_info}

---

## Application Specification

**Application Name:** {app_name}

**Description:** {app_description}

---

## Backend Requirements

{backend_requirements}

---

## Implementation Guidelines

### Database Models
- Use SQLAlchemy ORM with proper model definitions
- Include timestamps (created_at, updated_at) where appropriate
- Add proper relationships and constraints
- Initialize database with `db.create_all()` in app context

### API Endpoints
- Follow RESTful conventions (GET, POST, PUT, DELETE)
- Use proper HTTP status codes (200, 201, 400, 404, 500)
- Return JSON responses with consistent structure
- Add input validation and error handling

### Error Handling
- Catch and handle exceptions gracefully
- Return meaningful error messages
- Log errors for debugging

### Code Quality
- Add docstrings to functions and classes
- Use type hints where appropriate
- Follow PEP 8 style guidelines
- Keep functions focused and modular

---

## Important Constraints

✅ **DO:**
- Generate complete, working Flask application code
- Include all routes, models, and business logic
- Add proper CORS configuration
- Use SQLAlchemy for database operations
- Include error handling and validation
- Add logging for debugging

❌ **DO NOT:**
- Generate Dockerfile, requirements.txt, or other infrastructure
- Include `if __name__ == '__main__'` block (already in scaffolding)
- Regenerate Flask app initialization (already done)
- Create separate files (generate single code block)

---

## Output Format

Generate ONLY the Python code in a single code block:

```python
# Your complete Flask application code here
# This will be merged with the scaffolding
```
