# V2 Prompt System - Before & After Comparison

## BEFORE (Generic, No Requirements)

### Backend System Prompt:
```
You are an expert Flask developer. Generate ONLY the application code.
DO NOT generate Dockerfile, requirements.txt, or other infrastructure.
Generate clean, working Flask API code.
```

### Backend User Prompt:
```
Generate Python code for a Flask backend API.

IMPORTANT: 
- Generate ONLY the application-specific code
- DO NOT generate Dockerfile, requirements.txt, or other infrastructure
- Focus on routes, models, business logic
- Keep it simple and working

Generate the Flask API code:
```

**Problem**: Vague, no context, no specific requirements!

---

## AFTER (Requirements-Driven, Detailed)

### Backend System Prompt:
```
You are an expert Flask developer specializing in production-ready REST APIs.

Your task is to generate ONLY the Flask application code based on the given requirements.

RULES:
- Generate ONLY application code (routes, models, business logic)
- DO NOT generate infrastructure files (Dockerfile, requirements.txt, docker-compose.yml, etc)
- Use Flask best practices and proper project structure
- Use SQLAlchemy for database models when needed
- Include CORS configuration for frontend integration
- Implement ALL specified backend requirements completely
- Add proper error handling, validation, and logging
- Use appropriate HTTP status codes and response formats
- Generate complete, working code - no placeholders or TODOs

Return ONLY the Python code wrapped in ```python code blocks.
```

### Backend User Prompt (for Todo App):
```
Generate Python Flask backend code for: Simple Todo List

Description: A basic todo list application to manage tasks

BACKEND REQUIREMENTS:
- Create new todo item with title and optional description
- Retrieve all todo items
- Update todo item (title, description, completed status)
- Delete todo item by ID
- Mark todo as completed or uncompleted
- Store todos in SQLite database with timestamps
- Filter todos by completion status (all, active, completed)

IMPORTANT CONSTRAINTS:
- Generate ONLY the application code (routes, models, business logic)
- DO NOT generate Dockerfile, requirements.txt, or infrastructure files
- Use Flask best practices with proper error handling
- Use SQLAlchemy for database models where needed
- Include CORS configuration for frontend integration
- Add proper logging and validation
- Keep code clean, well-commented, and production-ready

Generate the complete Flask backend code:
```

**Benefits**: 
✅ Clear application name and description
✅ Specific, actionable requirements list
✅ Better context for the model
✅ More likely to get complete, correct code

---

## How It Works

1. **Requirements Files**: JSON files in `misc/requirements/` define what each app needs
   - `todo_app.json` - Todo list requirements
   - `base64_converter.json` - Base64 encoder/decoder requirements
   - `xsd_verifier.json` - XML validator requirements

2. **Template ID Mapping**: Each template ID maps to a requirements file
   ```python
   template_map = {
       1: 'todo_app.json',
       2: 'base64_converter.json',
       3: 'xsd_verifier.json'
   }
   ```

3. **Dynamic Prompt Building**: Requirements are loaded and formatted into the prompt
   - App name and description
   - Bulleted list of backend/frontend requirements
   - Clear constraints and guidelines

4. **Result**: Models generate code that actually implements all requirements!
