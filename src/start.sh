#!/usr/bin/env bash

# Thesis App Startup Script
# ========================
# 
# Comprehensive startup script for the Thesis App with Celery integration.
# This script handles starting the Flask app, Celery workers, and analyzer services.

set -e  # Exit on error

# Configuration
FLASK_APP="main.py"
CELERY_APP="app.tasks"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
WORKER_CONCURRENCY="${WORKER_CONCURRENCY:-4}"
BEAT_SCHEDULE="${BEAT_SCHEDULE:-30}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# Check if Redis is running
check_redis() {
    log "Checking Redis connection..."
    
    if command -v redis-cli >/dev/null 2>&1; then
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
            log "Redis is running and accessible"
            return 0
        else
            error "Redis is not accessible at $REDIS_HOST:$REDIS_PORT"
            return 1
        fi
    else
        warn "redis-cli not found, skipping Redis check"
        return 0
    fi
}

# Start Redis if not running
start_redis() {
    log "Starting Redis server..."
    
    if command -v redis-server >/dev/null 2>&1; then
        redis-server --daemonize yes --port "$REDIS_PORT" --bind "$REDIS_HOST"
        sleep 2
        
        if check_redis; then
            log "Redis started successfully"
        else
            error "Failed to start Redis"
            exit 1
        fi
    else
        error "Redis server not found. Please install Redis or use external Redis instance"
        exit 1
    fi
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    # Check Python
    if ! command -v python >/dev/null 2>&1; then
        error "Python not found"
        exit 1
    fi
    
    # Check pip packages
    if ! python -c "import flask, celery, redis, sqlalchemy" >/dev/null 2>&1; then
        error "Required Python packages not found. Run: pip install -r requirements.txt"
        exit 1
    fi
    
    log "Dependencies check passed"
}

# Initialize database
init_database() {
    log "Initializing database..."
    
    if [ -f "app/models.py" ]; then
        python -c "
from app.factory import create_cli_app
from app.models import init_db

app = create_cli_app()
with app.app_context():
    init_db()
    print('Database initialized successfully')
" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            log "Database initialization completed"
        else
            warn "Database initialization had issues, continuing..."
        fi
    else
        warn "Models file not found, skipping database initialization"
    fi
}

# Start Celery worker
start_celery_worker() {
    log "Starting Celery worker..."
    
    celery -A "$CELERY_APP" worker \
        --loglevel=info \
        --concurrency="$WORKER_CONCURRENCY" \
        --pidfile=celery_worker.pid \
        --logfile=celery_worker.log \
        --detach
    
    if [ $? -eq 0 ]; then
        log "Celery worker started successfully"
    else
        error "Failed to start Celery worker"
        exit 1
    fi
}

# Start Celery beat scheduler
start_celery_beat() {
    log "Starting Celery beat scheduler..."
    
    celery -A "$CELERY_APP" beat \
        --loglevel=info \
        --pidfile=celery_beat.pid \
        --logfile=celery_beat.log \
        --schedule=celerybeat-schedule \
        --detach
    
    if [ $? -eq 0 ]; then
        log "Celery beat started successfully"
    else
        error "Failed to start Celery beat"
        exit 1
    fi
}

# Start Flask application
start_flask_app() {
    log "Starting Flask application..."
    
    export FLASK_APP="$FLASK_APP"
    export FLASK_ENV="${FLASK_ENV:-development}"
    export ANALYZER_AUTO_START="${ANALYZER_AUTO_START:-false}"
    
    python "$FLASK_APP" &
    FLASK_PID=$!
    echo $FLASK_PID > flask_app.pid
    
    log "Flask application started with PID: $FLASK_PID"
}

# Start analyzer services
start_analyzer_services() {
    log "Starting analyzer services..."
    
    if [ -f "../analyzer/analyzer_manager.py" ]; then
        cd ../analyzer
        python analyzer_manager.py start >/dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            log "Analyzer services started successfully"
        else
            warn "Failed to start analyzer services automatically"
        fi
        cd - >/dev/null
    else
        warn "Analyzer manager not found, skipping analyzer services"
    fi
}

# Stop all services
stop_services() {
    log "Stopping all services..."
    
    # Stop Flask app
    if [ -f "flask_app.pid" ]; then
        FLASK_PID=$(cat flask_app.pid)
        if kill -0 "$FLASK_PID" 2>/dev/null; then
            kill "$FLASK_PID"
            log "Flask application stopped"
        fi
        rm -f flask_app.pid
    fi
    
    # Stop Celery worker
    if [ -f "celery_worker.pid" ]; then
        celery -A "$CELERY_APP" control shutdown
        rm -f celery_worker.pid
        log "Celery worker stopped"
    fi
    
    # Stop Celery beat
    if [ -f "celery_beat.pid" ]; then
        BEAT_PID=$(cat celery_beat.pid)
        if kill -0 "$BEAT_PID" 2>/dev/null; then
            kill "$BEAT_PID"
            log "Celery beat stopped"
        fi
        rm -f celery_beat.pid celerybeat-schedule
    fi
    
    # Stop analyzer services
    if [ -f "../analyzer/analyzer_manager.py" ]; then
        cd ../analyzer
        python analyzer_manager.py stop >/dev/null 2>&1
        cd - >/dev/null
        log "Analyzer services stopped"
    fi
}

# Check status of services
check_status() {
    log "Checking service status..."
    
    # Flask app
    if [ -f "flask_app.pid" ]; then
        FLASK_PID=$(cat flask_app.pid)
        if kill -0 "$FLASK_PID" 2>/dev/null; then
            info "Flask app: RUNNING (PID: $FLASK_PID)"
        else
            warn "Flask app: STOPPED (stale PID file)"
        fi
    else
        warn "Flask app: STOPPED"
    fi
    
    # Celery worker
    if [ -f "celery_worker.pid" ]; then
        info "Celery worker: RUNNING"
    else
        warn "Celery worker: STOPPED"
    fi
    
    # Celery beat
    if [ -f "celery_beat.pid" ]; then
        BEAT_PID=$(cat celery_beat.pid)
        if kill -0 "$BEAT_PID" 2>/dev/null; then
            info "Celery beat: RUNNING (PID: $BEAT_PID)"
        else
            warn "Celery beat: STOPPED (stale PID file)"
        fi
    else
        warn "Celery beat: STOPPED"
    fi
    
    # Redis
    if check_redis; then
        info "Redis: RUNNING"
    else
        warn "Redis: NOT ACCESSIBLE"
    fi
}

# Main function
main() {
    case "${1:-start}" in
        start)
            log "Starting Thesis App with Celery integration..."
            
            check_dependencies
            
            # Check/start Redis
            if ! check_redis; then
                start_redis
            fi
            
            init_database
            start_celery_worker
            start_celery_beat
            start_analyzer_services
            start_flask_app
            
            log "All services started successfully!"
            log "Flask app available at: http://127.0.0.1:5000"
            log "Use 'bash $0 stop' to stop all services"
            log "Use 'bash $0 status' to check service status"
            ;;
        
        stop)
            stop_services
            log "All services stopped"
            ;;
        
        restart)
            stop_services
            sleep 2
            main start
            ;;
        
        status)
            check_status
            ;;
        
        worker-only)
            log "Starting Celery worker only..."
            check_dependencies
            if ! check_redis; then
                start_redis
            fi
            start_celery_worker
            log "Celery worker started"
            ;;
        
        beat-only)
            log "Starting Celery beat only..."
            check_dependencies
            if ! check_redis; then
                start_redis
            fi
            start_celery_beat
            log "Celery beat started"
            ;;
        
        flask-only)
            log "Starting Flask app only..."
            check_dependencies
            init_database
            start_flask_app
            log "Flask app started"
            ;;
        
        *)
            echo "Usage: $0 {start|stop|restart|status|worker-only|beat-only|flask-only}"
            echo ""
            echo "Commands:"
            echo "  start       - Start all services (default)"
            echo "  stop        - Stop all services"
            echo "  restart     - Restart all services"
            echo "  status      - Check service status"
            echo "  worker-only - Start only Celery worker"
            echo "  beat-only   - Start only Celery beat"
            echo "  flask-only  - Start only Flask app"
            exit 1
            ;;
    esac
}

# Handle script interruption
trap 'stop_services; exit 130' INT TERM

# Run main function
main "$@"
