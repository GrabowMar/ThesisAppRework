# Container Quick Reference

## 🚀 Quick Commands

### Start an App
```bash
cd generated/apps/<model>/<app>
docker-compose up --build
```

### Common Operations
```bash
# Start detached
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild
docker-compose up --build --force-recreate

# Check status
docker-compose ps
```

## 📦 What's Included

Every generated app has:
- ✅ `backend/Dockerfile` - Python/Flask container
- ✅ `frontend/Dockerfile` - React/Vite + Nginx container  
- ✅ `docker-compose.yml` - Orchestration
- ✅ `.env.example` - Configuration template
- ✅ `README.md` - Full documentation

## 🔧 Configuration

### Change Ports
```bash
# Edit .env
BACKEND_PORT=5001
FRONTEND_PORT=8001

# Restart
docker-compose down && docker-compose up
```

### Development Mode
```env
FLASK_ENV=development
FLASK_DEBUG=1
```

### Production Mode
```env
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=<generate-strong-secret>
```

## 🐛 Troubleshooting

### Port Conflict
```bash
# Check what's using port
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # Linux/macOS

# Change port in .env
BACKEND_PORT=5001
```

### Container Won't Start
```bash
# Check logs
docker-compose logs backend

# Check health
docker inspect <container> | grep Health

# Rebuild from scratch
docker-compose down -v
docker-compose up --build --force-recreate
```

### Health Check Failing
```bash
# Test backend health
curl http://localhost:5000/health

# Test frontend health  
curl http://localhost:8000/health

# Check inside container
docker-compose exec backend curl localhost:5000/health
```

## 📊 Monitoring

```bash
# Resource usage
docker stats

# Container details
docker-compose exec backend env
docker-compose exec backend ps aux

# Network inspection
docker network inspect <app>_app-network
```

## 🔐 Security Features

- ✅ Non-root users in containers
- ✅ Minimal base images (Alpine/Slim)
- ✅ Health checks enabled
- ✅ Network isolation
- ✅ Volume-based data persistence
- ✅ Environment-based secrets

## 🔄 Backfill Old Apps

```bash
# Preview changes
python scripts/backfill_docker_files.py --dry-run

# Apply to all apps
python scripts/backfill_docker_files.py

# Specific model
python scripts/backfill_docker_files.py --model openai_gpt-4

# Force overwrite
python scripts/backfill_docker_files.py --force
```

## 📚 Full Documentation

See [docs/features/CONTAINERIZATION.md](../features/CONTAINERIZATION.md) for complete documentation.

---

**Default URLs:**
- Frontend: http://localhost:8000
- Backend: http://localhost:5000
