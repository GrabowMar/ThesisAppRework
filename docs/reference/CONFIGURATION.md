# Configuration Reference

> Complete environment and configuration reference

---

## Environment Variables

### Required Settings

```bash
# AI Model Access (REQUIRED)
OPENROUTER_API_KEY=sk-or-v1-...
# Get your key at: https://openrouter.ai/keys

# Flask Security (REQUIRED)
FLASK_SECRET_KEY=your-random-secret-key-here
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
```

### Optional Settings

```bash
# Flask Configuration
FLASK_ENV=development              # development | production
DEBUG=True                         # True | False

# Database
DATABASE_URL=sqlite:///app.db      # SQLite (dev)
# DATABASE_URL=postgresql://user:pass@localhost:5432/thesisapp  # PostgreSQL (prod)

# Redis
REDIS_URL=redis://localhost:6379/0

# Analyzer Services
ANALYZER_TIMEOUT=300               # Analysis timeout (seconds)
WEBSOCKET_GATEWAY_URL=ws://localhost:8765

# Generation Settings
GENERATION_TIMEOUT=600             # Generation timeout (seconds)
DISABLED_ANALYSIS_MODELS=model1,model2  # Skip analysis for these models

# Port Allocation
PORT_ALLOCATION_START_BACKEND=5001
PORT_ALLOCATION_START_FRONTEND=8001

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Configuration Files

### `.env` Template

```bash
# Copy this to .env and fill in your values

# ============================================
# Required Settings
# ============================================
OPENROUTER_API_KEY=
FLASK_SECRET_KEY=

# ============================================
# Flask
# ============================================
FLASK_ENV=development
DEBUG=True

# ============================================
# Database
# ============================================
DATABASE_URL=sqlite:///app.db

# ============================================
# Redis
# ============================================
REDIS_URL=redis://localhost:6379/0

# ============================================
# Analyzer
# ============================================
ANALYZER_TIMEOUT=300
WEBSOCKET_GATEWAY_URL=ws://localhost:8765

# ============================================
# Generation
# ============================================
GENERATION_TIMEOUT=600
```

---

## Port Configuration

### Service Ports

| Service | Default Port | Configurable | Description |
|---------|--------------|--------------|-------------|
| Flask App | 5000 | Yes | Web interface |
| Static Analyzer | 2001 | Via docker-compose | Security/quality analysis |
| Dynamic Analyzer | 2002 | Via docker-compose | Runtime testing |
| Performance Tester | 2003 | Via docker-compose | Load testing |
| AI Analyzer | 2004 | Via docker-compose | AI code review |
| WebSocket Gateway | 8765 | Via docker-compose | Real-time updates |
| Redis | 6379 | Via docker-compose | Cache/queue |
| PostgreSQL | 5432 | Via docker-compose | Database (prod) |

### Application Ports

Generated applications automatically receive unique ports:

- **Backend**: 5001, 5002, 5003, ... (configurable start)
- **Frontend**: 8001, 8002, 8003, ... (configurable start)

---

## Analyzer Configuration

### Docker Compose Override

Create `analyzer/docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  static-analyzer:
    environment:
      - CUSTOM_VAR=value
    ports:
      - "2001:2001"  # Change port if needed
  
  performance-tester:
    environment:
      - LOCUST_USERS=100
      - LOCUST_SPAWN_RATE=10
```

---

## Application Settings

### `src/app/config/settings.py`

```python
import os

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Celery
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # OpenRouter
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    
    # Analyzer
    ANALYZER_TIMEOUT = int(os.getenv('ANALYZER_TIMEOUT', 300))
    
class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')  # Must be PostgreSQL
```

---

## Last Updated

October 2025
