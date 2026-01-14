#!/bin/bash
#
# ThesisApp Clean Wipe and Redeploy Script
# =========================================
# 
# This script completely wipes all data and redeploys the application.
# Run directly on the server: sudo ./wipe_and_redeploy.sh
#
# Options:
#   --confirm    Skip confirmation prompt
#   --no-rebuild Skip container rebuild (just restart)
#

set -e

APP_PATH="/opt/thesisapp"
APP_USER="thesisapp"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info() { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
SKIP_CONFIRM=false
NO_REBUILD=false

for arg in "$@"; do
    case $arg in
        --confirm)
            SKIP_CONFIRM=true
            shift
            ;;
        --no-rebuild)
            NO_REBUILD=true
            shift
            ;;
    esac
done

echo ""
echo "========================================"
echo "  ThesisApp Clean Wipe & Redeploy"
echo "========================================"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    error "Please run as root or with sudo"
    exit 1
fi

# Check if app directory exists
if [ ! -d "$APP_PATH" ]; then
    error "Application directory not found: $APP_PATH"
    exit 1
fi

cd "$APP_PATH"

# Confirmation
if [ "$SKIP_CONFIRM" = false ]; then
    echo ""
    warn "This will COMPLETELY WIPE all data!"
    echo ""
    echo "  - All generated applications"
    echo "  - All analysis results"
    echo "  - All database records"
    echo "  - All logs"
    echo ""
    read -p "Type 'WIPE' to confirm: " confirmation
    if [ "$confirmation" != "WIPE" ]; then
        info "Operation cancelled"
        exit 0
    fi
fi

echo ""
info "Starting clean wipe and redeploy..."
START_TIME=$(date +%s)

# Step 1: Stop containers
info "Stopping containers..."
sudo -u $APP_USER docker compose down -v 2>/dev/null || docker compose down -v 2>/dev/null || true
success "Containers stopped"

# Step 2: Pull latest code
info "Pulling latest code from main branch..."
sudo -u $APP_USER git fetch origin main
sudo -u $APP_USER git reset --hard origin/main
success "Code updated to latest main"

# Step 3: Wipe data directories
info "Wiping data directories..."

# Generated apps
rm -rf "$APP_PATH/generated/apps/"*
mkdir -p "$APP_PATH/generated/apps"

# Raw payloads and responses
rm -rf "$APP_PATH/generated/raw/payloads/"*
rm -rf "$APP_PATH/generated/raw/responses/"*
mkdir -p "$APP_PATH/generated/raw/payloads"
mkdir -p "$APP_PATH/generated/raw/responses"

# Metadata
rm -rf "$APP_PATH/generated/metadata/indices/runs/"*
mkdir -p "$APP_PATH/generated/metadata/indices/runs"

# Results
rm -rf "$APP_PATH/results/"*
mkdir -p "$APP_PATH/results"

# Logs
rm -f "$APP_PATH/logs/"*.log
mkdir -p "$APP_PATH/logs"

# Database
rm -f "$APP_PATH/src/data/thesis_app.db"
rm -f "$APP_PATH/instance/"*.db

# Fix ownership
chown -R $APP_USER:$APP_USER "$APP_PATH/generated"
chown -R $APP_USER:$APP_USER "$APP_PATH/results"
chown -R $APP_USER:$APP_USER "$APP_PATH/logs"
chown -R $APP_USER:$APP_USER "$APP_PATH/src/data" 2>/dev/null || true
chown -R $APP_USER:$APP_USER "$APP_PATH/instance" 2>/dev/null || true

success "Data directories wiped"

# Step 4: Prune Docker
info "Pruning Docker resources..."
docker system prune -f
success "Docker cleaned"

# Step 5: Rebuild containers
if [ "$NO_REBUILD" = false ]; then
    info "Rebuilding containers (this may take a few minutes)..."
    sudo -u $APP_USER docker compose build --no-cache --parallel
    success "Containers rebuilt"
else
    info "Skipping rebuild (--no-rebuild flag set)"
fi

# Step 6: Start containers
info "Starting containers..."
sudo -u $APP_USER docker compose up -d
success "Containers started"

# Step 7: Wait for startup
info "Waiting for services to initialize..."
sleep 15

# Step 8: Health check
info "Checking health..."
for i in {1..5}; do
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        success "Health check passed"
        break
    fi
    if [ $i -eq 5 ]; then
        warn "Health check not responding yet (services may still be starting)"
    else
        sleep 5
    fi
done

# Show status
echo ""
info "Container Status:"
sudo -u $APP_USER docker compose ps

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "========================================"
success "Clean wipe and redeploy complete!"
echo "  Time elapsed: ${ELAPSED}s"
echo "  Server: https://$(hostname -f)"
echo "========================================"
echo ""
