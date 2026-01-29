# Remote Server Management Guide

This guide is for AI agents managing the ThesisApp deployment on the remote server.

## Connection Details
- **Host**: `145.239.65.130`
- **User**: `ubuntu`
- **Domain**: `ns3086089.ip-145-239-65.eu`
- **SSH Key**: `C:\Users\grabowmar\.ssh\id_ed25519_server`

## Application Stack
The app runs in Docker Compose with the following key services:
- **Caddy**: Reverse proxy handling HTTPS (80/443).
- **Web**: Flask application (internal port 5000).
- **Celery Worker**: Background task processor.
- **Redis**: Message broker for Celery.
- **Analyzers**: Static, Dynamic, Performance, and AI analyzers.

## Common Commands
All commands should be run from the `~/ThesisAppRework` directory on the server.

### Start/Restart Stack
```bash
./start.sh Docker --background
```

### Stop Services
```bash
./start.sh Stop
```

### View Logs
```bash
docker compose logs -f [service_name]
# or use start.sh
./start.sh Logs
```

### System Reset (Wipeout)
Deletes all generated data and resets the database.
```bash
./start.sh Wipeout
```
*Note: After a Wipeout, you MUST initialize the database and admin user.*

### Permission Fix
If you encounter `[Errno 13] Permission denied`, run:
```bash
sudo chmod -R 777 generated src/data
```

## Maintenance Procedures

### Updating Code
```bash
git pull
docker compose up -d --build
```
*Be careful with local conflicts (e.g., .env or temp scripts).*

### Admin Password Reset
Pipe the script via SSH:
```bash
cat reset_remote_password.py | ssh -i ... ubuntu@145.239.65.130 "cd ThesisAppRework && docker compose exec -T web python"
```
