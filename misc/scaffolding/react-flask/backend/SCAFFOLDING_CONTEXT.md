# Backend Scaffolding Context

## Single File Structure
```
backend/
├── app.py           # ALL CODE GOES HERE - models, routes, auth
├── requirements.txt # Add dependencies below marker
└── Dockerfile       # DO NOT MODIFY
```

## app.py Sections to Implement
1. **MODELS** - User model with password hashing, app-specific models
2. **AUTH HELPERS** - token_required/admin_required decorators, generate_token()
3. **AUTH ROUTES** - POST /api/auth/register, POST /api/auth/login, GET /api/auth/me
4. **USER ROUTES** - /api/* endpoints for user CRUD
5. **ADMIN ROUTES** - /api/admin/* endpoints for admin functions

## Adding Dependencies
Add to requirements.txt below the marker:
```
# LLM: ADD DEPENDENCIES BELOW
requests==2.31.0
```

## Response Patterns
```python
return jsonify(item.to_dict()), 200       # Single item
return jsonify({'items': [...]}), 200     # List  
return jsonify(item.to_dict()), 201       # Created
return jsonify({'error': 'msg'}), 400     # Error
```

## Database
SQLite at `sqlite:////app/data/app.db`
