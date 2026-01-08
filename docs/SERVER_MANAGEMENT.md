# Server Management Guide

This document provides instructions for connecting to, modifying, and managing the production server for ThesisAppRework. Intended for developers and AI agents working with this codebase.

## Server Details

| Property | Value |
|----------|-------|
| **Provider** | OVH (Dedicated Server) |
| **IP Address** | `145.239.65.130` |
| **OS** | Ubuntu |
| **User** | `ubuntu` |
| **Application Path** | `/home/ubuntu/ThesisAppRework/` |
| **SSH Key (Windows)** | `C:\Users\grabowmar\.ssh\id_ed25519_server` |

## Connecting to the Server

### SSH Connection

**Windows (PowerShell):**
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130
```

**Linux/macOS:**
```bash
ssh -i ~/.ssh/id_ed25519_server ubuntu@145.239.65.130
```

### Running Remote Commands (One-Liner)

You can execute commands without entering an interactive session:

```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'your-command-here'
```

**Example - Check Docker containers:**
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'docker ps'
```

## Docker Architecture

The application runs via Docker Compose with these services:

| Service | Container Name | Purpose | Port |
|---------|----------------|---------|------|
| Web | `thesisapprework-web-1` | Flask application | 5000 |
| Celery | `thesisapprework-celery-worker-1` | Background task worker | - |
| Static Analyzer | `thesisapprework-static-analyzer-1` | Code analysis | 2001 |
| Dynamic Analyzer | `thesisapprework-dynamic-analyzer-1` | Runtime analysis | 2002 |
| Performance Tester | `thesisapprework-performance-tester-1` | Load testing | 2003 |
| AI Analyzer | `thesisapprework-ai-analyzer-1` | AI-powered analysis | 2004 |
| Redis | `thesisapprework-redis-1` | Task queue broker | 6379 |

## Common Docker Commands

### View Running Containers
```bash
docker ps
```

### View Container Logs
```bash
# All logs
docker logs thesisapprework-web-1

# Last 50 lines
docker logs thesisapprework-web-1 --tail 50

# Follow logs in real-time
docker logs thesisapprework-web-1 -f
```

### Execute Commands Inside Containers
```bash
docker exec thesisapprework-web-1 <command>

# Example: Run analyzer
docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py status

# Example: Interactive shell
docker exec -it thesisapprework-web-1 /bin/bash
```

### Restart Services
```bash
# Restart specific container
docker restart thesisapprework-ai-analyzer-1

# Restart all services via compose
cd /home/ubuntu/ThesisAppRework
docker compose restart
```

### View Service Health
```bash
docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py health
```

## Code Deployment Workflow

### Method 1: Direct File Edit (Quick Fixes)

For small changes, edit files directly on the server:

```bash
# SSH into server
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130

# Navigate to project
cd /home/ubuntu/ThesisAppRework

# Edit file
nano analyzer/services/ai-analyzer/main.py

# Rebuild and restart affected container
docker compose build ai-analyzer
docker compose up -d ai-analyzer
```

### Method 2: Git Pull (Recommended for Multiple Changes)

```bash
# SSH into server
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130

# Navigate to project
cd /home/ubuntu/ThesisAppRework

# Pull latest changes
git pull origin main

# Rebuild all containers (or specific ones)
docker compose build
docker compose up -d
```

### Method 3: Remote Commands (Agent/Automation)

Execute from local machine without interactive SSH:

```powershell
# Step 1: Make local changes and push to git
git add .
git commit -m "Fix: description"
git push origin main

# Step 2: Pull on server and rebuild
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'cd /home/ubuntu/ThesisAppRework && git pull && docker compose build && docker compose up -d'
```

### Rebuilding Specific Services

```bash
# Rebuild only the AI analyzer
docker compose build ai-analyzer
docker compose up -d ai-analyzer

# Rebuild web service
docker compose build web
docker compose up -d web

# Rebuild everything
docker compose build
docker compose up -d
```

## Analyzer Management

### Check Analyzer Status
```bash
docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py status
```

### Check Analyzer Health
```bash
docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py health
```

### Run Analysis (Testing)
```bash
# Run AI analysis on a specific app
docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py analyze <model_slug> <app_number> ai --tools <tool_name>

# Example:
docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py analyze google_gemini-2.5-flash 1 ai --tools requirements-scanner
```

### View Analyzer Logs
```bash
# AI Analyzer logs
docker logs thesisapprework-ai-analyzer-1 --tail 100

# Static Analyzer logs
docker logs thesisapprework-static-analyzer-1 --tail 100
```

## Troubleshooting

### Container Won't Start

1. Check logs for errors:
   ```bash
   docker logs <container_name> --tail 50
   ```

2. Check if port is in use:
   ```bash
   netstat -tuln | grep <port>
   ```

3. Force rebuild:
   ```bash
   docker compose build <service>
   docker compose up -d <service>
   ```

### "Split-Brain" Deployment (Network Isolation)

**Symptom:** Web container can't reach analyzers, but analyzers seem running. `python analyzer/analyzer_manager.py health` fails with `error` or `unreachable`.

**Cause:** You may have accidentally started the analyzers from the `analyzer/` subdirectory instead of the root. This creates a separate Docker network (`analyzer_analyzer-network`) that the web app (`thesisapprework_thesis-network`) cannot reach.

**Fix:**
```bash
# 1. Stop the isolated stack
cd /home/ubuntu/ThesisAppRework/analyzer
docker compose down

# 2. Start the unified stack (root directory)
cd /home/ubuntu/ThesisAppRework
docker compose up -d
```

### Analysis Failing

1. Check service health:
   ```bash
   docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py health
   ```

2. Check specific analyzer logs:
   ```bash
   docker logs thesisapprework-ai-analyzer-1 --tail 200
   ```

3. Test WebSocket connectivity:
   ```bash
   curl -v http://localhost:2004/  # AI analyzer
   curl -v http://localhost:2001/  # Static analyzer
   ```

### Database Issues

The SQLite database is located at:
```
/home/ubuntu/ThesisAppRework/src/data/thesis_app.db
```

To backup:
```bash
cp /home/ubuntu/ThesisAppRework/src/data/thesis_app.db /home/ubuntu/backup_$(date +%Y%m%d).db
```

### Out of Disk Space

Check disk usage:
```bash
df -h
docker system df
```

Clean up Docker:
```bash
docker system prune -a  # WARNING: Removes all unused images
```

## Environment Variables

Key environment variables are set in `docker-compose.yml`:

| Variable | Purpose |
|----------|---------|
| `IN_DOCKER=true` | Signals containers they're running in Docker |
| `OPENROUTER_API_KEY` | API key for OpenRouter AI models |
| `SECRET_KEY` | Flask secret key |
| `DATABASE_URL` | Database connection string |

To update environment variables:
1. Edit `docker-compose.yml`
2. Restart affected containers: `docker compose up -d`

## File Locations

| Path | Description |
|------|-------------|
| `/home/ubuntu/ThesisAppRework/` | Project root |
| `analyzer/` | Analyzer manager and services |
| `analyzer/services/ai-analyzer/` | AI analyzer microservice |
| `analyzer/services/static-analyzer/` | Static analysis microservice |
| `src/` | Flask application source |
| `src/data/thesis_app.db` | SQLite database |
| `generated/apps/` | Generated applications |
| `results/` | Analysis results |
| `logs/` | Application logs |

## Useful One-Liners for AI Agents

### Quick Health Check
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py health'
```

### View Recent Logs
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'docker logs thesisapprework-web-1 --tail 50'
```

### Run Test Analysis
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py analyze google_gemini-2.5-flash 1 ai --tools requirements-scanner 2>&1 | tail -50'
```

### Restart All Services
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'cd /home/ubuntu/ThesisAppRework && docker compose restart'
```

### Pull Latest Code and Rebuild
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'cd /home/ubuntu/ThesisAppRework && git pull && docker compose build && docker compose up -d'
```

### Check Container Resource Usage
```powershell
ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130 'docker stats --no-stream'
```

## Security Notes

1. **SSH Key**: The SSH key must be kept secure and never committed to the repository
2. **API Keys**: Environment variables containing API keys are stored in `docker-compose.yml` (not in git)
3. **Firewall**: Only necessary ports are exposed (5000 for web, internal ports for services)

## Quick Reference Card

| Task | Command |
|------|---------|
| Connect to server | `ssh -i C:\Users\grabowmar\.ssh\id_ed25519_server ubuntu@145.239.65.130` |
| View containers | `docker ps` |
| View logs | `docker logs <container> --tail 50` |
| Restart container | `docker restart <container>` |
| Rebuild & restart | `docker compose build <service> && docker compose up -d <service>` |
| Health check | `docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py health` |
| Run analysis | `docker exec thesisapprework-web-1 python analyzer/analyzer_manager.py analyze <model> <app> <type>` |
| Pull & deploy | `git pull && docker compose build && docker compose up -d` |

---

*Last Updated: January 7, 2026*
