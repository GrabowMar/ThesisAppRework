#!/usr/bin/env bash
# Docker Deployment Helper Script for ThesisApp
# Makes the application container-ready and validates configuration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    info "✓ Docker found: $(docker --version)"
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        error "Docker Compose V2 is not available. Please update Docker."
        exit 1
    fi
    info "✓ Docker Compose found: $(docker compose version)"
    
    # Check Docker is running
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
    info "✓ Docker daemon is running"
}

# Create necessary directories
create_directories() {
    info "Creating necessary directories..."
    
    mkdir -p generated/apps
    mkdir -p results
    mkdir -p logs
    mkdir -p src/data
    mkdir -p misc
    
    info "✓ Directories created"
}

# Setup environment file
setup_env() {
    if [ ! -f .env ]; then
        info "Creating .env file from template..."
        cp .env.example .env
        
        # Generate random secret key
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
        
        # Update .env with generated secret
        if [ "$(uname)" = "Darwin" ] || [ "$(uname)" = "Linux" ]; then
            sed -i.bak "s/change-me-to-a-random-secure-key/$SECRET_KEY/" .env && rm .env.bak
        fi
        
        warn "⚠ Please edit .env and add your OPENROUTER_API_KEY"
        info "✓ .env file created"
    else
        info "✓ .env file already exists"
    fi
}

# Validate configuration
validate_config() {
    info "Validating configuration..."
    
    if [ ! -f .env ]; then
        error ".env file not found. Run with --setup first."
        exit 1
    fi
    
    # Check for required variables
    if ! grep -q "OPENROUTER_API_KEY=.*[a-zA-Z0-9]" .env; then
        warn "⚠ OPENROUTER_API_KEY not set in .env (AI analysis will not work)"
    fi
    
    info "✓ Configuration validated"
}

# Build images
build_images() {
    info "Building Docker images..."
    docker compose build --pull
    info "✓ Images built successfully"
}

# Start services
start_services() {
    info "Starting services..."
    docker compose up -d
    info "✓ Services started"
    
    info "Waiting for services to be healthy..."
    sleep 5
    docker compose ps
}

# Stop services
stop_services() {
    info "Stopping services..."
    docker compose down
    info "✓ Services stopped"
}

# Show status
show_status() {
    info "Service status:"
    docker compose ps
    
    echo ""
    info "Service health:"
    docker compose ps --format json | python3 -m json.tool 2>/dev/null || docker compose ps
    
    echo ""
    info "Quick links:"
    echo "  Web UI:       http://localhost:5000"
    echo "  Health check: http://localhost:5000/health"
    echo "  Redis:        redis://localhost:6379"
}

# View logs
view_logs() {
    SERVICE=${1:-}
    if [ -z "$SERVICE" ]; then
        docker compose logs -f --tail=100
    else
        docker compose logs -f --tail=100 "$SERVICE"
    fi
}

# Initialize database
init_db() {
    info "Initializing database..."
    docker compose exec web python src/init_db.py
    info "✓ Database initialized"
}

# Run tests
run_tests() {
    info "Running tests in container..."
    docker compose exec web pytest -v
}

# Test Celery pipeline
test_celery() {
    info "Testing Celery and analyzer pipeline..."
    docker compose exec web python -c "
from app.tasks import celery
import sys
i = celery.control.inspect()
w = i.active()
if w:
    print('✓ Celery worker is active')
    print(f'  Active workers: {list(w.keys())}')
else:
    print('✗ No Celery workers responding')
    sys.exit(1)
"
}

# Clean up
cleanup() {
    warn "This will remove all containers, volumes, and generated data!"
    read -p "Are you sure? (yes/no): " -r
    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        info "Cleaning up..."
        docker compose down -v
        rm -rf generated/apps/* results/* logs/*
        info "✓ Cleanup complete"
    else
        info "Cleanup cancelled"
    fi
}

# Main script
case "${1:-help}" in
    setup)
        check_prerequisites
        create_directories
        setup_env
        info "✓ Setup complete. Edit .env and then run: $0 start"
        ;;
    
    validate)
        validate_config
        ;;
    
    build)
        check_prerequisites
        validate_config
        build_images
        ;;
    
    start)
        check_prerequisites
        validate_config
        build_images
        start_services
        echo ""
        show_status
        ;;
    
    stop)
        stop_services
        ;;
    
    restart)
        stop_services
        start_services
        show_status
        ;;
    
    status)
        show_status
        ;;
    
    logs)
        view_logs "$2"
        ;;
    
    init-db)
        init_db
        ;;
    
    test)
        run_tests
        ;;
    
    test-celery)
        test_celery
        ;;
    
    clean)
        cleanup
        ;;
    
    help|*)
        echo "ThesisApp Docker Deployment Helper"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  setup      - Initial setup (create dirs, .env file)"
        echo "  validate   - Validate configuration"
        echo "  build      - Build Docker images"
        echo "  start      - Build and start all services"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  status     - Show service status"
        echo "  logs       - View logs (optionally specify service name)"
        echo "  init-db    - Initialize database"
        echo "  test       - Run tests in container"
        echo "  test-celery - Test Celery worker and pipeline"
        echo "  clean      - Remove all containers and data (dangerous!)"
        echo "  help       - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 setup              # First time setup"
        echo "  $0 start              # Start all services"
        echo "  $0 logs web           # View web service logs"
        echo "  $0 status             # Check service health"
        ;;
esac
