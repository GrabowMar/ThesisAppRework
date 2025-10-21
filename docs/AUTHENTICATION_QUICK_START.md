# 🔐 Authentication System - Quick Deployment Guide

Your ThesisAppRework platform now has a **secure login system** protecting all routes!

## 🚀 Quick Start (5 minutes)

### 1. Install Dependencies
```powershell
pip install Flask-Login==0.6.3 bcrypt==4.1.2
```

### 2. Initialize Database
```powershell
cd src
python init_db.py
```

### 3. Create Admin User
```powershell
# Interactive mode (recommended)
python scripts/create_admin.py

# Or quick mode
python scripts/create_admin.py admin admin@example.com YourSecurePassword123
```

### 4. Set Secure SECRET_KEY (IMPORTANT!)
Generate a secure random key:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Update `.env`:
```env
SECRET_KEY=your-generated-secure-key-here
REGISTRATION_ENABLED=false
SESSION_COOKIE_SECURE=false  # Set to true when using HTTPS
```

### 5. Start Application
```powershell
# Local development
.\start.ps1

# Or Docker
docker compose up -d
```

### 6. Login
Visit `http://localhost:5000/` - you'll be redirected to login!

**Default Admin Credentials** (if you used quick mode above):
- Username: `admin`
- Password: `YourSecurePassword123`

---

## 🔒 Security Features

✅ **Bcrypt password hashing** - Secure password storage  
✅ **Session-based authentication** - Flask-Login integration  
✅ **Protected routes** - All pages require login  
✅ **Admin role support** - Role-based access control  
✅ **Configurable sessions** - Adjustable timeout and security  
✅ **Registration control** - Enable/disable self-registration  

---

## 📋 Environment Variables

| Variable | Description | Default | Production Value |
|----------|-------------|---------|------------------|
| `SECRET_KEY` | Flask session secret | `dev-secret-key...` | **Must be random!** |
| `REGISTRATION_ENABLED` | Allow new registrations | `false` | `false` recommended |
| `SESSION_COOKIE_SECURE` | Require HTTPS | `false` | `true` with HTTPS |
| `SESSION_LIFETIME` | Session timeout (seconds) | `86400` (24h) | Adjust as needed |

---

## 🐳 Docker Deployment

### Build and Start
```bash
docker compose build web celery-worker
docker compose up -d
```

### Create Admin Inside Container
```bash
docker compose exec web python scripts/create_admin.py
```

### Set Production Secret
Before deploying, update `.env` with a secure SECRET_KEY:
```bash
# Generate key
python -c "import secrets; print(secrets.token_hex(32))"

# Update .env
SECRET_KEY=<generated-key-here>
SESSION_COOKIE_SECURE=true  # if using HTTPS
```

Then rebuild:
```bash
docker compose up -d --force-recreate web celery-worker
```

---

## 👥 User Management

### Create Additional Users
```powershell
python scripts/create_admin.py username email@example.com password "Full Name"
```

### Enable Self-Registration
Set in `.env`:
```env
REGISTRATION_ENABLED=true
```

Users can then register at `/auth/register`

### Manage Users via Python
```python
from app.factory import create_app
from app.extensions import db
from app.models import User

app = create_app()
with app.app_context():
    # Make user admin
    user = User.query.filter_by(username='username').first()
    user.is_admin = True
    db.session.commit()
    
    # Deactivate user
    user.is_active = False
    db.session.commit()
    
    # Reset password
    user.set_password('new_password')
    db.session.commit()
```

---

## 🛡️ Security Best Practices

### For Production Deployment:

1. **SECRET_KEY**: Always use a random, unique value (not the default!)
2. **HTTPS**: Enable `SESSION_COOKIE_SECURE=true` when using HTTPS
3. **Registration**: Keep disabled (`REGISTRATION_ENABLED=false`) unless needed
4. **Passwords**: Enforce strong passwords (8+ characters minimum)
5. **Session Timeout**: Adjust `SESSION_LIFETIME` based on your security needs
6. **Firewall**: Restrict access to port 5000 (or use a reverse proxy)

---

## 🔧 Troubleshooting

### "Please log in to access this page" on every request
**Solution**: 
1. Verify `SECRET_KEY` is set and hasn't changed
2. Clear browser cookies
3. For development, ensure `SESSION_COOKIE_SECURE=false`

### Can't create admin - "User already exists"
**Solution**: Username/email already in use. Try different values or manage existing user.

### Session expires too quickly
**Solution**: Increase `SESSION_LIFETIME` in `.env` (value in seconds)

### Registration page returns 404
**Solution**: Set `REGISTRATION_ENABLED=true` in `.env` and restart

---

## 📚 Full Documentation

See `docs/AUTHENTICATION_DEPLOYMENT.md` for:
- Complete API documentation
- Database schema details
- Advanced configuration options
- Migration guide from non-authenticated setup
- Future enhancement roadmap

---

## 🎯 What's Protected

All routes require authentication except:
- `/auth/login` - Login page
- `/auth/logout` - Logout action  
- `/auth/register` - Registration (if enabled)
- `/health` - Health check endpoint

**Protected routes include:**
- Dashboard (`/`)
- Models overview
- Applications management
- Analysis tools
- All API endpoints

---

## ✅ Verification Checklist

Before deploying to production:

- [ ] Generated secure SECRET_KEY and updated `.env`
- [ ] Created at least one admin user
- [ ] Set `REGISTRATION_ENABLED` appropriately
- [ ] Configured `SESSION_COOKIE_SECURE` for HTTPS
- [ ] Tested login/logout functionality
- [ ] Verified all routes are protected
- [ ] Backed up database
- [ ] Set up reverse proxy (if using)
- [ ] Configured firewall rules

---

**Need Help?** Check `docs/AUTHENTICATION_DEPLOYMENT.md` for detailed documentation!
