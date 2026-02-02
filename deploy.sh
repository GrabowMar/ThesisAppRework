#!/bin/bash
# ThesisAppRework Quick Deploy Script
# Usage: ./deploy.sh [--reset]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[-]${NC} $1"; exit 1; }

# Full reset if requested
if [[ "$1" == "--reset" ]]; then
    warn "Full reset requested..."
    docker compose down -v 2>/dev/null || true
    docker system prune -af --volumes 2>/dev/null || true
    rm -rf generated/* results/* logs/* instance/* src/data/*
    log "Reset complete"
fi

# Check prerequisites
command -v docker >/dev/null 2>&1 || error "Docker not found"
command -v docker compose >/dev/null 2>&1 || error "Docker Compose not found"

# Setup .env if not exists
if [[ ! -f .env ]]; then
    log "Creating .env from template..."
    cp .env.example .env
    warn "Edit .env to add your OPENROUTER_API_KEY"
fi

# Detect and set Docker GID
DOCKER_GID=$(stat -c '%g' /var/run/docker.sock 2>/dev/null || echo "0")
if ! grep -q "DOCKER_GID=" .env 2>/dev/null; then
    log "Setting DOCKER_GID=$DOCKER_GID"
    echo "DOCKER_GID=$DOCKER_GID" >> .env
else
    sed -i "s/^DOCKER_GID=.*/DOCKER_GID=$DOCKER_GID/" .env
fi

# Create directories
log "Creating directories..."
mkdir -p generated/apps generated/raw/responses generated/metadata results logs instance src/data
chmod -R 777 generated results logs instance src/data

# Create Docker network
log "Ensuring Docker network exists..."
docker network create thesis-apps-network 2>/dev/null || true

# Deploy
log "Deploying containers..."
docker compose up -d --build

# Wait for health
log "Waiting for services to be healthy..."
sleep 30

# Check status
log "Checking service status..."
docker compose ps

# Create admin user
log "Ensuring admin user exists..."
docker compose exec -T web python -c "
from app.factory import create_app
from app.models.user import User
from app.extensions import db
app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@local.dev')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Admin created: admin / admin123')
    else:
        print('Admin user exists')
" 2>/dev/null || warn "Could not create admin user - try manually"

log "Deployment complete!"
echo ""
echo "Access the app at: http://localhost"
echo "Default credentials: admin / admin123"
