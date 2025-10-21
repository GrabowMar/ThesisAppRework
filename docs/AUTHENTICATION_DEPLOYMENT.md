# Authentication System - Deployment Guide

## Overview

The application now includes a complete Flask-Login based authentication system to protect your deployment from unauthorized access.

## Features

- **User Authentication**: Secure login/logout with Flask-Login
- **Password Hashing**: Bcrypt-based password storage
- **Session Management**: Configurable session lifetime and security
- **Admin Support**: Role-based access with admin flag
- **Protected Routes**: All main routes require authentication

## Quick Start

### 1. Install Dependencies

```bash
pip install Flask-Login==0.6.3 bcrypt==4.1.2
```

### 2. Update Database

Run the database initialization to create the users table:

```bash
cd src
python init_db.py
```

### 3. Create Admin User

Use the provided script to create an admin user:

```bash
# Interactive mode (recommended)
python scripts/create_admin.py

# Or command-line mode
python scripts/create_admin.py admin admin@example.com SecurePassword123
```

### 4. Configure Environment Variables

Update your `.env` file with security settings:

```env
# Authentication & Security
SECRET_KEY=your-very-secure-random-secret-key-here
REGISTRATION_ENABLED=false
SESSION_COOKIE_SECURE=true  # Set to true in production with HTTPS
SESSION_LIFETIME=86400  # 24 hours in seconds
```

**IMPORTANT**: Generate a secure random SECRET_KEY for production:

```python
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Start the Application

```bash
# Using PowerShell (Windows)
.\start.ps1

# Or Docker Compose
docker compose up -d
```

### 6. Login

Navigate to `http://localhost:5000/` and you'll be redirected to the login page.

## Configuration Options

### Environment Variables

| Variable | Description | Default | Production |
|----------|-------------|---------|------------|
| `SECRET_KEY` | Flask secret key for sessions | `dev-secret-key...` | **Must change!** |
| `REGISTRATION_ENABLED` | Allow new user registration | `false` | `false` recommended |
| `SESSION_COOKIE_SECURE` | Require HTTPS for cookies | `false` | `true` (with HTTPS) |
| `SESSION_LIFETIME` | Session timeout in seconds | `86400` (24h) | Adjust as needed |

### Security Best Practices

1. **SECRET_KEY**: Always use a random, unique secret key in production
2. **HTTPS**: Enable `SESSION_COOKIE_SECURE=true` when using HTTPS
3. **Registration**: Keep `REGISTRATION_ENABLED=false` unless you need public signup
4. **Passwords**: Enforce strong passwords (8+ characters minimum)
5. **Session Timeout**: Adjust based on your security requirements

## User Management

### Creating Users Manually

Use the admin creation script:

```bash
# Create regular user
python scripts/create_admin.py username email@example.com password "Full Name"

# Create admin user (script creates admins by default)
python scripts/create_admin.py
```

### Enabling Self-Registration

If you want to allow users to register themselves:

1. Set `REGISTRATION_ENABLED=true` in `.env`
2. Restart the application
3. Users can register at `/auth/register`

**Note**: All self-registered users are non-admin by default.

### Managing Existing Users

Use Python shell to manage users:

```python
from app.factory import create_app
from app.extensions import db
from app.models import User

app = create_app()
with app.app_context():
    # Deactivate a user
    user = User.query.filter_by(username='username').first()
    user.is_active = False
    db.session.commit()
    
    # Make user admin
    user = User.query.filter_by(username='username').first()
    user.is_admin = True
    db.session.commit()
    
    # Change password
    user = User.query.filter_by(username='username').first()
    user.set_password('new_password')
    db.session.commit()
```

## Protected Routes

All routes are now protected by default except:
- `/auth/login` - Login page
- `/auth/logout` - Logout action
- `/auth/register` - Registration (if enabled)
- `/health` - Health check endpoint

Users must be logged in to access:
- Dashboard (`/`)
- Models overview
- Applications
- Analysis tools
- All API endpoints

## Database Schema

### Users Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `username` | String(80) | Unique username |
| `email` | String(120) | Unique email |
| `password_hash` | String(255) | Bcrypt hashed password |
| `full_name` | String(120) | Optional full name |
| `is_active` | Boolean | Account active status |
| `is_admin` | Boolean | Admin privileges flag |
| `created_at` | DateTime | Account creation timestamp |
| `last_login` | DateTime | Last login timestamp |

## Docker Deployment

The authentication system works seamlessly with Docker:

1. Ensure `.env` is configured with production settings
2. Build and start containers:

```bash
docker compose build
docker compose up -d
```

3. Create admin user inside the container:

```bash
docker compose exec web python /app/scripts/create_admin.py
```

Or mount a script to create users automatically on first run.

## Troubleshooting

### "Please log in to access this page" on every request

**Cause**: SECRET_KEY changed or session cookies not being saved

**Solution**:
1. Check SECRET_KEY is set and consistent
2. Clear browser cookies
3. For development, ensure `SESSION_COOKIE_SECURE=false`

### Cannot create admin user - "User already exists"

**Solution**: User with that username/email already exists. Try:
- Different username/email
- Or manage the existing user via Python shell

### Registration page not accessible

**Cause**: Registration is disabled

**Solution**: Set `REGISTRATION_ENABLED=true` in `.env` and restart

### Session expires too quickly

**Solution**: Increase `SESSION_LIFETIME` in `.env` (value in seconds)

## API Authentication

For API endpoints, you have two options:

### Option 1: Session-Based (Current)

API requests must include session cookies from browser login.

### Option 2: Token-Based (Future Enhancement)

Consider adding JWT tokens or API keys for programmatic access.

## Migration from Non-Authenticated Setup

If upgrading from a version without authentication:

1. **Backup your database**:
   ```bash
   cp src/data/thesis_app.db src/data/thesis_app.db.backup
   ```

2. **Install new dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run migrations** (if using Flask-Migrate):
   ```bash
   cd src
   flask db upgrade
   ```
   
   Or reinitialize the database:
   ```bash
   python init_db.py
   ```

4. **Create admin user**:
   ```bash
   python scripts/create_admin.py
   ```

5. **Test login** before deploying to production

## Future Enhancements

Potential improvements for the authentication system:

- [ ] Email verification for new users
- [ ] Password reset functionality
- [ ] Two-factor authentication (2FA)
- [ ] API token authentication
- [ ] Audit logging for login attempts
- [ ] Role-based permissions (beyond admin/user)
- [ ] OAuth integration (GitHub, Google, etc.)
- [ ] Session management dashboard
- [ ] Account lockout after failed attempts

## Support

For issues or questions about the authentication system:

1. Check this documentation
2. Review error logs in `logs/` directory
3. Verify environment variables are set correctly
4. Ensure database is properly initialized
