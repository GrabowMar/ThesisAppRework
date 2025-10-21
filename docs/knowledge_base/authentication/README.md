# Authentication

## Quick Start

All routes are protected by default. Users must log in to access any functionality.

### Setup (5 minutes)

```bash
# 1. Install dependencies
pip install Flask-Login bcrypt

# 2. Initialize database
cd src && python init_db.py

# 3. Create admin user
python scripts/create_admin.py

# 4. Set secure key in .env
SECRET_KEY=<generate-random-64-char-string>

# 5. Start app
docker compose up -d
```

### Login
Visit `http://localhost:5000/` → Auto-redirects to clean login page

## Architecture

**Flask-Login** manages sessions with bcrypt password hashing. Every blueprint has `@before_request` checks:
- **Web routes**: Redirect unauthenticated users to login page
- **API routes**: Return 401 JSON for unauthenticated requests
- **Exceptions**: `/auth/login`, `/auth/logout`, `/health` endpoints only

## API Token Authentication

For programmatic access (AI models, scripts):

```bash
# Generate token (web UI: User Menu → API Access)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:5000/api/models
```

## User Management

```python
# Create users
python scripts/create_admin.py username email password

# Manage via Python
from app.models import User
user = User.query.filter_by(username='name').first()
user.is_admin = True  # Make admin
user.set_password('newpass')  # Change password
db.session.commit()
```

## Environment Variables

| Variable | Default | Production |
|----------|---------|------------|
| `SECRET_KEY` | dev key | **Must change!** |
| `REGISTRATION_ENABLED` | `false` | `false` |
| `SESSION_COOKIE_SECURE` | `false` | `true` (HTTPS) |
| `SESSION_LIFETIME` | `86400` (24h) | Adjust as needed |

## Security Checklist

- [ ] Generate random SECRET_KEY (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Create admin user
- [ ] Disable registration (`REGISTRATION_ENABLED=false`)
- [ ] Enable secure cookies for HTTPS (`SESSION_COOKIE_SECURE=true`)
- [ ] Test login/logout
- [ ] Set up HTTPS with reverse proxy
