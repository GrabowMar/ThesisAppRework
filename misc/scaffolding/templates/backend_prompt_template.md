# Prompt Template for Backend Generation

{scaffolding_info}

---

## Application Specification

**Application Name:** {app_name}

**Description:** {app_description}

---

## Backend Requirements

**IMPORTANT:** You MUST implement ALL of the following requirements completely. This task is critical to the success of the project.

{backend_requirements}

---

## Implementation Guidelines

**Think step by step** as you implement each requirement:

### Database Models
1. Use SQLAlchemy ORM with proper model definitions
2. Include timestamps (created_at, updated_at) where appropriate
3. Add proper relationships and constraints
4. Initialize database with `db.create_all()` in app context

### API Endpoints
1. Follow RESTful conventions (GET, POST, PUT, DELETE)
2. Use proper HTTP status codes (200, 201, 400, 404, 500)
3. Return JSON responses with consistent structure
4. Add input validation and error handling

### Error Handling
1. Catch and handle exceptions gracefully
2. Return meaningful error messages
3. Log errors for debugging

### Code Quality
1. Add docstrings to functions and classes
2. Use type hints where appropriate
3. Follow PEP 8 style guidelines
4. Keep functions focused and modular

---

## Important Constraints

✅ **DO:**
1. Generate complete, working Flask application code
2. Include all routes, models, and business logic
3. Add proper CORS configuration
4. Use SQLAlchemy for database operations
5. Include error handling and validation
6. Add logging for debugging
7. Implement every requirement listed above without exception

❌ **DO NOT:**
1. Generate Dockerfile, requirements.txt, or other infrastructure
2. Include `if __name__ == '__main__'` block (already in scaffolding)
3. Regenerate Flask app initialization (already done)
4. Create separate files (generate single code block)
5. Skip any requirements or use placeholder comments like TODO or FIXME

---

## Output Format

Generate ONLY the Python code in a single code block:

```python
# Your complete Flask application code here
# This will be merged with the scaffolding
```
