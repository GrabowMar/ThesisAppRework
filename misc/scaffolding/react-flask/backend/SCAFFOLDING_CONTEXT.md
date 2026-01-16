# Backend Scaffolding Context

## Structure
```
backend/
├── app.py          # Entry point (minimal changes)
├── models.py       # LLM implements all models
├── services.py     # LLM implements business logic
└── routes/
    ├── __init__.py # Blueprint setup (don't modify)
    ├── auth.py     # LLM implements JWT auth
    ├── user.py     # LLM implements user API
    └── admin.py    # LLM implements admin API
```

### Blueprint Prefixes (IMPORTANT)
- `user_bp` already has `/api` prefix → route paths should NOT start with `/api`
- `admin_bp` already has `/api/admin` prefix → route paths should NOT start with `/api`

## What LLM Must Implement

### 1. User Model (models.py)
```python
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, pw):
        import bcrypt
        self.password_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    
    def check_password(self, pw):
        import bcrypt
        return bcrypt.checkpw(pw.encode(), self.password_hash.encode())
    
    def to_dict(self):
        return {'id': self.id, 'username': self.username, ...}
```

### 2. JWT Auth (routes/auth.py)
```python
import jwt

def generate_token(user_id):
    return jwt.encode({'user_id': user_id, 'exp': datetime.utcnow() + timedelta(hours=24)}, 
                      os.environ.get('SECRET_KEY', 'dev'), algorithm='HS256')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        payload = jwt.decode(token, os.environ.get('SECRET_KEY', 'dev'), algorithms=['HS256'])
        current_user = User.query.get(payload['user_id'])
        return f(current_user, *args, **kwargs)
    return decorated
```

### 3. API Patterns
- User routes: `/api/*` - public or @token_required
- Admin routes: `/api/admin/*` - always @admin_required
- All models need `to_dict()` method
- Use `db.session.add()` + `db.session.commit()`

## Environment
- DB: `sqlite:////app/data/app.db`
- Port: `FLASK_RUN_PORT` env var
- Secret: `SECRET_KEY` env var

## Dependencies & Healing
- You MAY add additional Python packages if needed.
- If you introduce new packages, include them in a `requirements` block.
- The Dependency Healer can reconcile missing packages, but you should still list any new ones you use.
