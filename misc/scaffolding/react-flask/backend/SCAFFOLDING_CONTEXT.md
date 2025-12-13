# Backend Context

## Environment
- DB: `sqlite:////app/data/app.db` (4 slashes)
- Uploads: `/app/data/uploads`
- Port: env `FLASK_RUN_PORT` or 5000

## Stack
Flask 3.0, Flask-CORS, SQLAlchemy, gunicorn, bcrypt, PyJWT, werkzeug

## Rules
1. Keep `/api/health` → `{"status": "healthy"}`
2. All routes under `/api/`
3. Define models FIRST, then `with app.app_context(): db.create_all()`
4. Return JSON always
5. Use `host='0.0.0.0'` in `app.run()` for Docker

## Patterns (Pseudocode)

### Model
```
Model: id (pk), fields..., timestamps
to_dict() → dict with all fields (datetime → isoformat)
```

### DB Init (MUST be after models)
```
with app.app_context():
    db.create_all()
```

### Routes
```
GET /api/things → list all
GET /api/things/:id → get one or 404
POST /api/things → validate, create, return 201
PUT /api/things/:id → update, return item
DELETE /api/things/:id → delete, return success
```

### Main
```
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_RUN_PORT', 5000)))
```

### Errors
```
ValueError → 400
Exception → rollback + 500
```

## Gotchas
- Flask 3.0: NO `@app.before_first_request` (use app_context instead)
- `get_or_404()` auto-returns 404
- Rollback on errors
- Boolean params: `== 'true'`
- Import `os` when using `os.environ`
