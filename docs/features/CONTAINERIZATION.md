# Container-Ready Generated Applications

## Overview

All generated applications now include complete Docker containerization support, making them immediately deployable as isolated, sandboxed containers. This ensures:

- **Isolation**: Each app runs in its own container environment
- **Reproducibility**: Consistent behavior across different machines
- **Security**: Sandboxed execution with non-root users
- **Portability**: Easy deployment to any Docker-capable platform
- **Zero Configuration**: Works out of the box with sensible defaults

## Included Files

Every generated application includes:

### Docker Configuration
- **`backend/Dockerfile`**: Multi-stage Python container with security best practices
- **`backend/.dockerignore`**: Prevents unnecessary files from entering backend image
- **`frontend/Dockerfile`**: Multi-stage Node.js build + Nginx production server
- **`frontend/.dockerignore`**: Prevents unnecessary files from entering frontend image
- **`frontend/nginx.conf`**: Optimized Nginx configuration for React SPA
- **`docker-compose.yml`**: Orchestrates backend + frontend with health checks

### Configuration Files
- **`.env.example`**: Template for environment variables (copy to `.env`)
- **`README.md`**: Complete usage instructions and documentation

## Quick Start

### Run Any Generated App

```bash
cd generated/apps/<model-name>/app<N>

# Copy environment template
cp .env.example .env

# Start the application
docker-compose up --build
```

That's it! The app will be available at:
- Frontend: http://localhost:8000
- Backend API: http://localhost:5000

(Ports can be customized via `.env`)

## Architecture

### Multi-Stage Builds

Both frontend and backend use optimized multi-stage builds:

**Backend (Python/Flask)**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 5000
CMD ["python", "app.py"]
```

**Frontend (React/Vite + Nginx)**
```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Container Orchestration

Docker Compose manages both services with:
- **Health checks**: Automatic container health monitoring
- **Dependencies**: Frontend waits for backend to be healthy
- **Networks**: Isolated bridge network for inter-service communication
- **Volumes**: Persistent data storage for backend databases
- **Restart policies**: Automatic recovery from failures

### Security Features

1. **Non-root users**: Both containers run as unprivileged users
2. **Minimal base images**: Slim/Alpine variants reduce attack surface
3. **Layer caching**: Optimized Dockerfile ordering for faster rebuilds
4. **Health checks**: Automatic detection of unhealthy containers
5. **Network isolation**: Services communicate via internal Docker network
6. **Environment variables**: Sensitive data separated from code

## Environment Configuration

### Default Ports

```env
BACKEND_PORT=5000
FRONTEND_PORT=8000
```

### Available Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_NAME` | `app` | Container name prefix |
| `BACKEND_PORT` | `5000` | Backend service port |
| `FRONTEND_PORT` | `8000` | Frontend service port |
| `FLASK_ENV` | `production` | Flask environment mode |
| `CORS_ORIGINS` | `http://localhost:8000` | Allowed CORS origins |

### Port Conflicts

If default ports are in use:

```env
# .env
BACKEND_PORT=5001
FRONTEND_PORT=8001
```

Then rebuild:
```bash
docker-compose down
docker-compose up --build
```

## Development vs Production

### Development Mode

For active development, the docker-compose.yml includes volume mounts:

```yaml
volumes:
  - ./backend:/app  # Live code reloading
```

Enable Flask debug mode:
```env
FLASK_ENV=development
FLASK_DEBUG=1
```

### Production Mode

For production deployment:

1. Remove volume mounts from `docker-compose.yml`
2. Use production environment:
   ```env
   FLASK_ENV=production
   FLASK_DEBUG=0
   ```
3. Generate strong secrets:
   ```env
   SECRET_KEY=$(openssl rand -hex 32)
   ```
4. Configure proper CORS:
   ```env
   CORS_ORIGINS=https://yourdomain.com
   ```

## Operations

### Container Management

```bash
# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Check container status
docker-compose ps

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Health Monitoring

Both services include health checks:

```bash
# Check health status
docker inspect <container-name> | grep -A 10 Health

# Manual health check
curl http://localhost:5000/health  # Backend
curl http://localhost:8000/health  # Frontend
```

### Debugging

```bash
# Execute commands in running container
docker-compose exec backend bash
docker-compose exec frontend sh

# View container resource usage
docker stats

# Inspect container details
docker-compose exec backend env
```

## Backfilling Existing Apps

For apps generated before this feature was added:

```bash
# Dry run to see what would be added
python scripts/backfill_docker_files.py --dry-run

# Add Docker files to all apps
python scripts/backfill_docker_files.py

# Add to specific model
python scripts/backfill_docker_files.py --model openai_gpt-4

# Add to specific app
python scripts/backfill_docker_files.py --model openai_gpt-4 --app-num 1

# Force overwrite existing files (use with caution!)
python scripts/backfill_docker_files.py --force
```

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker-compose logs backend
docker-compose logs frontend
```

**Common issues:**
- Port already in use → Change `BACKEND_PORT`/`FRONTEND_PORT` in `.env`
- Missing dependencies → Verify `requirements.txt` or `package.json`
- Database errors → Check volume mounts and permissions

### Health Check Failing

**Backend health check:**
```bash
docker-compose exec backend curl http://localhost:5000/health
```

If missing `/health` endpoint, add to Flask app:
```python
@app.route('/health')
def health():
    return {'status': 'healthy'}, 200
```

**Frontend health check:**
```bash
docker-compose exec frontend wget --spider http://localhost/
```

### Build Failures

**Clear Docker cache:**
```bash
docker-compose build --no-cache
docker system prune -af
```

**Check Dockerfile syntax:**
```bash
docker build -t test-backend ./backend
docker build -t test-frontend ./frontend
```

### Network Issues

**Verify network:**
```bash
docker network ls
docker network inspect <project>_app-network
```

**Test inter-service connectivity:**
```bash
docker-compose exec frontend ping backend
docker-compose exec backend ping frontend
```

## Best Practices

### Development

1. **Use volume mounts** for live code reloading
2. **Enable debug mode** for detailed error messages
3. **Use `.env` file** for local configuration
4. **Check logs frequently** with `docker-compose logs -f`

### Production

1. **Remove volume mounts** to prevent code changes
2. **Use environment variables** instead of `.env` files
3. **Set proper secrets** for production keys
4. **Enable HTTPS** with reverse proxy (Nginx/Caddy)
5. **Monitor logs** with centralized logging (ELK, Splunk)
6. **Set resource limits** in docker-compose.yml:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '0.5'
         memory: 512M
   ```

### Security

1. **Never commit `.env`** to version control
2. **Rotate secrets regularly** in production
3. **Use minimal base images** (alpine, slim)
4. **Run as non-root users** (already configured)
5. **Scan images** for vulnerabilities:
   ```bash
   docker scan <image-name>
   ```
6. **Update dependencies** regularly:
   ```bash
   pip install --upgrade -r requirements.txt
   npm update
   ```

## Integration with Analysis

The analyzer services can now:
- Build and run containerized apps automatically
- Perform security scans on Docker images
- Test app functionality in isolated environments
- Verify container health and resource usage

See `docs/features/ANALYSIS.md` for details on analyzing containerized applications.

## Future Enhancements

Planned improvements:
- [ ] Kubernetes deployment manifests
- [ ] Docker Swarm configurations
- [ ] CI/CD pipeline templates (GitHub Actions, GitLab CI)
- [ ] Monitoring stack (Prometheus, Grafana)
- [ ] Auto-scaling configurations
- [ ] Multi-architecture builds (ARM64, AMD64)

## References

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/)
- [Flask Deployment Options](https://flask.palletsprojects.com/en/latest/deploying/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)

---

**Note**: This containerization is automatic for all new generated applications. Existing apps can be backfilled using the provided script.
