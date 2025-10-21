# Docker Quick Reference

## 🚀 Quick Start
```bash
# One-time setup
./docker-deploy.sh setup
# Edit .env and add your OPENROUTER_API_KEY

# Start everything
./docker-deploy.sh start

# Validate deployment
./validate-docker-deployment.sh
```

## 📦 Core Commands

### Service Management
```bash
docker compose up -d              # Start all services (detached)
docker compose down               # Stop all services
docker compose restart [service]  # Restart service
docker compose ps                 # Show service status
```

### Logs & Debugging
```bash
docker compose logs -f            # Follow all logs
docker compose logs -f web        # Follow web service logs
docker compose logs --tail=100    # Last 100 lines
```

### Database
```bash
docker compose exec web python src/init_db.py  # Initialize DB
```

## 🔗 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Web UI | http://localhost:5000 | Main application |
| Health | http://localhost:5000/health | Health check |
| Redis | redis://localhost:6379 | Cache & queue |
| Analyzer Gateway | ws://localhost:8765 | WebSocket gateway |
| Static Analyzer | http://localhost:2001 | Security analysis |
| Dynamic Analyzer | http://localhost:2002 | Dynamic testing |
| Performance Tester | http://localhost:2003 | Load testing |
| AI Analyzer | http://localhost:2004 | AI code review |

## 🔧 Troubleshooting

### Service won't start
```bash
docker compose logs [service]     # Check logs
docker compose ps                 # Check status
docker compose restart [service]  # Try restart
```

### Port already in use
```bash
# Find process using port 5000
netstat -tulpn | grep 5000        # Linux
lsof -i :5000                     # macOS
netstat -ano | findstr :5000      # Windows

# Stop conflicting service or change port in docker-compose.yml
```

### Database issues
```bash
# Reset database
docker compose down
rm -f src/data/thesis_app.db
docker compose up -d
docker compose exec web python src/init_db.py
```

### Permission errors
```bash
# Fix file permissions
sudo chown -R $USER:$USER generated/ results/ logs/ src/data/

# Or rebuild with correct UID
docker compose build --no-cache
```

## 📊 Monitoring

### Check service health
```bash
./validate-docker-deployment.sh
```

### View resource usage
```bash
docker stats                      # Real-time stats
docker compose ps --format json   # Detailed status
```

### Test specific endpoints
```bash
curl http://localhost:5000/health
curl http://localhost:2001/health
curl http://localhost:2002/health
```

## 🛠️ Development

### Hot reload (for development)
```yaml
# Add to docker-compose.override.yml
services:
  web:
    volumes:
      - ./src:/app/src
    environment:
      - FLASK_ENV=development
```

### Run commands in container
```bash
docker compose exec web bash      # Open shell
docker compose exec web python    # Python REPL
docker compose exec web pytest    # Run tests
```

### Scale workers
```bash
docker compose up -d --scale celery-worker=3
```

## 🔐 Security

### Generate secure secret key
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Add to .env as SECRET_KEY
```

### Update all images
```bash
docker compose pull
docker compose build --pull
docker compose up -d
```

## 🧹 Cleanup

### Remove stopped containers
```bash
docker compose down
```

### Remove everything including volumes
```bash
docker compose down -v
```

### Complete cleanup
```bash
./docker-deploy.sh clean
```

## 🎯 Helper Scripts

| Script | Purpose |
|--------|---------|
| `docker-deploy.sh` | Main deployment helper |
| `validate-docker-deployment.sh` | Validate running services |
| `docker-compose.yml` | Service definitions |
| `.env.example` | Configuration template |

## 📝 Configuration Files

- `.env` - Environment variables (copy from `.env.example`)
- `docker-compose.yml` - Service orchestration
- `Dockerfile` - Main app image
- `analyzer/Dockerfile` - Analyzer gateway image
- `.dockerignore` - Files excluded from build

## ⚡ Performance Tuning

### Adjust worker concurrency
```bash
# In .env
CELERY_WORKER_CONCURRENCY=4
```

### Adjust service resources
```yaml
# In docker-compose.yml under each service
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '1.0'
```

## 🆘 Emergency Recovery

### Complete reset
```bash
# Stop everything
docker compose down -v

# Clean all data
rm -rf generated/apps/* results/* logs/*

# Rebuild from scratch
docker compose build --no-cache
docker compose up -d

# Reinitialize
docker compose exec web python src/init_db.py
```

### Export logs for debugging
```bash
docker compose logs > debug.log 2>&1
# Attach debug.log to issue report
```

## 📚 Additional Resources

- Full documentation: `DOCKER_DEPLOYMENT.md`
- Changes summary: `DOCKER_COMPATIBILITY_CHANGES.md`
- Architecture: `docs/ARCHITECTURE.md`
- Development guide: `docs/DEVELOPMENT_GUIDE.md`

---

**Need Help?** Run `./docker-deploy.sh help` or check logs with `docker compose logs -f`
