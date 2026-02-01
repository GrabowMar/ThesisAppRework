#!/bin/bash

# ThesisApp Orchestrator - Linux/Ubuntu Version
# Replicates functionality of start.ps1

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT_DIR/src"
ANALYZER_DIR="$ROOT_DIR/analyzer"
LOGS_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"

# Default API Port
PORT=5000

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# Global State
PYTHON_CMD="python3"
BACKGROUND=false
NO_ANALYZER=false
NO_FOLLOW=false
CONCURRENT=false
MODE="Interactive"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

write_banner() {
    local text="$1"
    local color="${2:-$CYAN}"
    local width=80
    local line=$(printf "%${width}s" | tr " " "═")
    
    echo ""
    echo -e "${color}╔${line}╗${NC}"
    
    # Center text
    local text_len=${#text}
    local padding=$(( (width - text_len) / 2 ))
    local pad_str=$(printf "%${padding}s" "")
    local content="${pad_str} ${text} ${pad_str}"
    
    # Adjust for odd length
    if [ $(( (width - text_len) % 2 )) -ne 0 ]; then
        content="${content} "
    fi
    while [ ${#content} -lt $((width + 2)) ]; do
        content="${content} "
    done
    
    printf "${color}║%*s%s%*s║${NC}\n" $padding "" "$text" $((width - padding - text_len)) ""
    
    echo -e "${color}╚${line}╝${NC}"
    echo ""
}

write_status() {
    local message="$1"
    local type="${2:-Info}"
    
    local icon="ℹ️ "
    local color="$CYAN"
    
    case "$type" in
        "Success") icon="✅"; color="$GREEN" ;;
        "Warning") icon="⚠️ "; color="$YELLOW" ;;
        "Error")   icon="❌"; color="$RED" ;;
    esac
    
    echo -e "${color}${icon} ${message}${NC}"
}

initialize_environment() {
    write_status "Initializing environment..." "Info"
    
    mkdir -p "$LOGS_DIR"
    mkdir -p "$RUN_DIR"
    
    # Ensure all required project directories exist (to avoid Docker creating them as root)
    write_status "Ensuring project directories exist..." "Info"
    mkdir -p "$ROOT_DIR/results"
    mkdir -p "$ROOT_DIR/generated/apps"
    mkdir -p "$ROOT_DIR/generated/raw/responses"
    mkdir -p "$ROOT_DIR/generated/raw/payloads"
    mkdir -p "$ROOT_DIR/generated/metadata/indices"
    mkdir -p "$ROOT_DIR/src/data"

    # Set proper permissions for directories that the app needs to write to
    chmod -R 775 "$ROOT_DIR/results" 2>/dev/null || true
    chmod -R 775 "$ROOT_DIR/generated" 2>/dev/null || true
    chmod -R 775 "$ROOT_DIR/src/data" 2>/dev/null || true
    chmod -R 775 "$ROOT_DIR/logs" 2>/dev/null || true
    
    write_status "Ensuring shared Docker network exists..." "Info"
    if docker network ls --format "{{.Name}}" | grep -q "^thesis-apps-network$"; then
        write_status "  Shared network exists: thesis-apps-network" "Success"
    else
        if docker network create thesis-apps-network >/dev/null 2>&1; then
            write_status "  Created shared network: thesis-apps-network" "Success"
        else
            write_status "  Warning: Could not create shared network" "Warning"
        fi
    fi
    
    # Detect Docker GID for socket access (required for dynamic/performance analyzers)
    write_status "Detecting Docker GID..." "Info"
    if [ -S /var/run/docker.sock ]; then
        # Use stat to get the group ID of the docker socket
        export DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
        write_status "  Docker GID detected: $DOCKER_GID" "Success"

        # Verify socket is accessible
        if docker info >/dev/null 2>&1; then
            write_status "  Docker socket accessible" "Success"
        else
            write_status "  Warning: Docker socket not accessible (may need to restart)" "Warning"
        fi
    else
        # Fallback to group lookup
        DOCKER_GID=$(getent group docker | cut -d: -f3)
        if [ -n "$DOCKER_GID" ]; then
            export DOCKER_GID=$DOCKER_GID
            write_status "  Docker GID found via group lookup: $DOCKER_GID" "Success"
        else
            export DOCKER_GID=0
            write_status "  Warning: Could not detect Docker GID, defaulting to 0" "Warning"
        fi
    fi

    # Write DOCKER_GID to .env for docker-compose
    if ! grep -q "^DOCKER_GID=" "$ROOT_DIR/.env" 2>/dev/null; then
        echo "DOCKER_GID=$DOCKER_GID" >> "$ROOT_DIR/.env"
        write_status "  DOCKER_GID written to .env" "Success"
    else
        sed -i "s/^DOCKER_GID=.*/DOCKER_GID=$DOCKER_GID/" "$ROOT_DIR/.env"
        write_status "  DOCKER_GID updated in .env" "Success"
    fi
    
    # Export env vars
    export FLASK_ENV='development'
    export HOST='127.0.0.1'
    export PORT=$PORT
    export DEBUG='false'
    export PYTHONUTF8='1'
    export PYTHONIOENCODING='utf-8'
    
    write_status "Environment initialized" "Success"
}

check_dependencies() {
    write_status "Checking dependencies..." "Info"
    local issues=()
    
    # Check Python
    local venv_python="$ROOT_DIR/.venv/bin/python"
    if [ -f "$venv_python" ]; then
        write_status "  Python: .venv virtual environment found" "Success"
        PYTHON_CMD="$venv_python"
    elif command -v python3 &> /dev/null; then
        write_status "  Python: System Python found" "Warning"
        PYTHON_CMD="python3"
    else
        issues+=("Python not found")
    fi
    
    # Check Docker
    if docker info >/dev/null 2>&1; then
        write_status "  Docker: Running" "Success"
    else
        issues+=("Docker is not running or not installed")
    fi
    
    if [ ${#issues[@]} -gt 0 ]; then
        write_status "Dependency check failed:" "Error"
        for issue in "${issues[@]}"; do
            echo -e "  • $issue"
        done
        return 1
    fi
    
    write_status "All dependencies satisfied" "Success"
    return 0
}

# ============================================================================
# SERVICE FUNCTIONS
# ============================================================================

start_redis() {
    write_status "Starting Redis container..." "Info"
    
    if docker ps --filter "name=^thesisapprework-redis-1$" --format "{{.Names}}" | grep -q "redis"; then
        write_status "  ✓ Redis already running" "Success"
        return 0
    fi
    
    cd "$ROOT_DIR"
    if ! docker compose up -d redis; then
        write_status "  ✗ Failed to start Redis" "Error"
        return 1
    fi
    
    # Wait for Redis
    echo -n -e "  ⏳ Waiting for Redis health check"
    local max_wait=30
    local waited=0
    
    while [ $waited -lt $max_wait ]; do
        sleep 1
        waited=$((waited+1))
        echo -n -e "${YELLOW}.${NC}"
        
        if "$PYTHON_CMD" -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1); exit(0) if s.connect_ex(('127.0.0.1', 6379)) == 0 else exit(1)" 2>/dev/null; then
            echo ""
            write_status "  ✓ Redis started and healthy (${waited}s)" "Success"
            return 0
        fi
    done
    
    echo ""
    write_status "  ✗ Redis health check timeout" "Error"
    return 1
}

start_celery() {
    write_status "Starting Celery worker..." "Info"
    
    if docker ps --filter "name=^thesisapprework-celery-worker-1$" --format "{{.Names}}" | grep -q "celery-worker"; then
        write_status "  ✓ Celery worker already running" "Success"
        return 0
    fi
    
    cd "$ROOT_DIR"
    if ! docker compose up -d celery-worker; then
        write_status "  ✗ Failed to start Celery worker" "Error"
        return 1
    fi
    
    # Wait for Celery
    echo -n -e "  ⏳ Waiting for Celery worker"
    local max_wait=60
    local waited=0
    
    while [ $waited -lt $max_wait ]; do
        sleep 2
        waited=$((waited+2))
        echo -n -e "${YELLOW}.${NC}"
        
        local health=$(docker inspect --format='{{.State.Health.Status}}' thesisapprework-celery-worker-1 2>/dev/null || echo "unknown")
        if [ "$health" == "healthy" ]; then
            echo ""
            write_status "  ✓ Celery worker healthy (${waited}s)" "Success"
            return 0
        fi
    done
    
    echo ""
    write_status "  ⚠ Celery worker timeout (will fallback to ThreadPool)" "Warning"
    return 0 # Not fatal
}

start_analyzers() {
    if [ "$NO_ANALYZER" = true ]; then
        write_status "Skipping analyzer services" "Warning"
        return 0
    fi
    
    write_status "Starting analyzer services..." "Info"
    
    local services=("analyzer-gateway" "static-analyzer" "dynamic-analyzer" "performance-tester" "ai-analyzer" "redis")
    local expected_count=6
    local mode_label="Standard"
    
    if [ "$CONCURRENT" = true ]; then
        write_status "Enable CONCURRENT mode..." "Info"
        services+=("static-analyzer-2" "static-analyzer-3" "dynamic-analyzer-2" "performance-tester-2" "ai-analyzer-2")
        expected_count=11
        mode_label="Concurrent"
        
        export STATIC_ANALYZER_URLS="ws://localhost:2001,ws://localhost:2051,ws://localhost:2052"
        export DYNAMIC_ANALYZER_URLS="ws://localhost:2002,ws://localhost:2053"
        export PERF_TESTER_URLS="ws://localhost:2003,ws://localhost:2054"
        export AI_ANALYZER_URLS="ws://localhost:2004,ws://localhost:2055"
    fi
    
    # Ensure clean state for analyzers
    cd "$ROOT_DIR"
    
    # Start
    if ! docker compose up -d "${services[@]}" >> "$LOGS_DIR/analyzer.log" 2>&1; then
        write_status "  Failed to start analyzer services" "Error"
        return 1
    fi
    
    write_status "  Analyzer services started" "Success"
    
    # Save mode info
    echo "{\"mode\": \"$mode_label\"}" > "$RUN_DIR/analyzer.pid"
    
    return 0
}

start_flask() {
    write_status "Starting Flask application..." "Info"
    local pid_file="$RUN_DIR/flask.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null; then
            write_status "  Flask already running (PID: $pid)" "Success"
            return 0
        fi
        rm "$pid_file"
    fi
    
    cd "$SRC_DIR"
    
    if [ "$BACKGROUND" = true ]; then
        nohup "$PYTHON_CMD" main.py > "$LOGS_DIR/app.log" 2> "$LOGS_DIR/flask_stderr.log" &
        echo $! > "$pid_file"
        write_status "  Flask started in background (PID: $(cat $pid_file))" "Success"
    else
        write_status "  Flask starting in foreground..." "Success"
        echo -e "${GRAY}    URL: http://127.0.0.1:$PORT${NC}"
        "$PYTHON_CMD" main.py
    fi
    
    return 0
}

stop_all_services() {
    write_banner "Stopping ThesisApp Services"
    
    # Check for docker mode
    if [ -f "$RUN_DIR/docker.mode" ]; then
        write_status "Stopping Docker stack..." "Info"
        cd "$ROOT_DIR"
        docker compose down >/dev/null 2>&1
        rm -f "$RUN_DIR/docker.mode"
        write_status "Docker stack stopped" "Success"
        return 0
    fi
    
    # Stop Flask
    if [ -f "$RUN_DIR/flask.pid" ]; then
        local pid=$(cat "$RUN_DIR/flask.pid")
        write_status "Stopping Flask (PID: $pid)..." "Info"
        kill $pid 2>/dev/null || true
        rm "$RUN_DIR/flask.pid"
        write_status "  Flask stopped" "Success"
    else
        # Fallback: kill by pattern
        pkill -f "python.*main.py" && write_status "  Flask stopped (killed by pattern)" "Success" || true
    fi
    
    # Stop Analyzers (Containers)
    write_status "Stopping Analyzer containers..." "Info"
    cd "$ROOT_DIR"
    docker compose stop analyzer-gateway static-analyzer dynamic-analyzer performance-tester ai-analyzer static-analyzer-2 static-analyzer-3 dynamic-analyzer-2 performance-tester-2 ai-analyzer-2 2>/dev/null || true
    rm -f "$RUN_DIR/analyzer.pid"
    
    # Stop Redis/Celery
    docker compose stop redis celery-worker 2>/dev/null || true
    
    write_status "All services stopped" "Success"
}

start_local_stack() {
    write_banner "Starting Local Stack"
    
    start_redis || return 1
    start_celery
    start_analyzers
    start_flask
}

start_docker_stack() {
    write_banner "Starting Docker Production Stack"

    cd "$ROOT_DIR"

    local services=("nginx" "web" "celery-worker" "redis" "analyzer-gateway" "static-analyzer" "dynamic-analyzer" "performance-tester" "ai-analyzer")
    if [ "$CONCURRENT" = true ]; then
         services+=("static-analyzer-2" "static-analyzer-3" "dynamic-analyzer-2" "performance-tester-2" "ai-analyzer-2")
    fi

    write_status "Building and starting stack..." "Info"
    docker compose up -d --build "${services[@]}"

    echo "docker-compose" > "$RUN_DIR/docker.mode"

    write_status "Docker stack started" "Success"
    write_status "Waiting for services to be healthy..." "Info"
    sleep 5

    # Check celery-worker health
    local max_wait=60
    local waited=0
    echo -n -e "  ⏳ Waiting for celery-worker to be healthy"
    while [ $waited -lt $max_wait ]; do
        local health=$(docker inspect --format='{{.State.Health.Status}}' thesisapprework-celery-worker-1 2>/dev/null || echo "unknown")
        if [ "$health" == "healthy" ]; then
            echo ""
            write_status "  ✓ Celery worker healthy with Docker access" "Success"
            break
        fi
        echo -n -e "${YELLOW}.${NC}"
        sleep 2
        waited=$((waited + 2))
    done

    if [ $waited -ge $max_wait ]; then
        echo ""
        write_status "  ⚠ Celery worker may not be fully healthy - check logs if issues occur" "Warning"
    fi

    echo -e "${CYAN}URL: http://127.0.0.1:80 (HTTP) or https://127.0.0.1:443 (HTTPS)${NC}"
}

start_dev_mode() {
    write_banner "Starting Dev Mode"
    export DEBUG='true'
    export FLASK_ENV='development'
    
    if [ "$NO_ANALYZER" = false ]; then
        start_analyzers
    fi
    
    start_flask
}

invoke_cleanup() {
    write_banner "Cleaning ThesisApp"
    rm -f "$RUN_DIR"/*.pid
    rm -f "$LOGS_DIR"/*.log
    rm -f "$LOGS_DIR"/*.old
    write_status "Cleanup completed" "Success"
}

invoke_logs() {
    local opts=""
    if [ "$NO_FOLLOW" = false ]; then
        opts="-f"
    else
        opts="--tail=50"
    fi
    
    tail $opts "$LOGS_DIR"/*.log 2>/dev/null
}

invoke_reload() {
    write_banner "🔄 Reloading ThesisApp" "Yellow"
    write_status "Stopping services..." "Info"
    stop_all_services
    sleep 2
    
    # Kill any orphans
    pkill -f "$SRC_DIR" 2>/dev/null || true
    rm -f "$RUN_DIR/flask.pid"
    
    write_status "Restarting services..." "Info"
    BACKGROUND=true
    start_docker_stack
}

invoke_wipeout() {
    write_banner "⚠️  WIPEOUT" "Red"
    write_status "Stopping services..." "Info"
    stop_all_services
    
    write_status "Removing Docker resources..." "Info"
    cd "$ROOT_DIR"
    docker compose down --rmi local --volumes --remove-orphans >/dev/null 2>&1
    
    write_status "Removing database..." "Info"
    rm -rf "$SRC_DIR/data"
    mkdir -p "$SRC_DIR/data"
    chmod 777 "$SRC_DIR/data"
    
    write_status "Removing generated apps..." "Info"
    rm -rf "$ROOT_DIR/generated"
    mkdir -p "$ROOT_DIR/generated/apps"
    mkdir -p "$ROOT_DIR/generated/raw/responses"
    mkdir -p "$ROOT_DIR/generated/raw/payloads"
    mkdir -p "$ROOT_DIR/generated/metadata/indices"
    touch "$ROOT_DIR/generated/.gitkeep"
    
    write_status "Removing results/reports..." "Info"
    rm -rf "$ROOT_DIR/results" "$ROOT_DIR/reports"
    mkdir -p "$ROOT_DIR/results" "$ROOT_DIR/reports"
    
    invoke_cleanup
    
    write_status "Initializing fresh database..." "Info"
    if ! ANALYZER_ENABLED=false "$PYTHON_CMD" "$SRC_DIR/init_db.py" >/dev/null 2>&1; then
        write_status "  Local python init failed, trying via Docker..." "Warning"
        if ! docker compose run --rm -e ANALYZER_ENABLED=false web python src/init_db.py; then
            write_status "  ✗ Failed to initialize database" "Error"
            return 1
        fi
    fi

    # Create Admin User
    write_status "Creating admin user..." "Info"
    local new_password=$(tr -dc 'A-Za-z0-9!@#$%^&*' < /dev/urandom | head -c 16)
    local temp_script_name="temp_create_admin.py"
    local temp_script_host="$ROOT_DIR/$temp_script_name"
    
    cat <<EOF > "$temp_script_host"
import sys, os
sys.path.insert(0, '/app/src')
sys.path.insert(0, '$SRC_DIR')
from app.factory import create_app
from app.models import User
from app.extensions import db
app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first() or User(username='admin', email='admin@thesis.local', full_name='System Administrator')
    admin.set_password('$new_password')
    admin.is_admin = True
    admin.is_active = True
    db.session.add(admin)
    db.session.commit()
    print('ADMIN_CREATED')
EOF

    if ! ANALYZER_ENABLED=false "$PYTHON_CMD" "$temp_script_host" >/dev/null 2>&1; then
        write_status "  Local admin creation failed, trying via Docker..." "Warning"
        docker compose run --rm -e ANALYZER_ENABLED=false -v "$temp_script_host:/app/$temp_script_name" web python "/app/$temp_script_name" >/dev/null 2>&1
    fi
    rm -f "$temp_script_host"
    
    write_status "Admin user initialized" "Success"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  NEW ADMIN CREDENTIALS${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  Username: ${GREEN}admin${NC}"
    echo -e "  Password: ${GREEN}$new_password${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⚠️  Save this password now!${NC}"
    
    write_status "Wipeout complete" "Success"
}

invoke_nuke() {
    write_banner "🔥 NUKE" "Red"
    invoke_wipeout
    initialize_environment
    
    write_status "Rebuilding..." "Info"
    cd "$ROOT_DIR"
    docker compose build --no-cache --parallel
    
    if [ "$BACKGROUND" = false ]; then
        read -p "Start services now? (y/n): " choice
        if [[ "$choice" =~ ^[Yy]$ ]]; then
            start_docker_stack
        fi
    else
        start_docker_stack
    fi
}

show_status_dashboard() {
    local loop="$1"
    
    while true; do
        clear
        write_banner "ThesisApp Status Dashboard"
        
        # Check Flask
        if [ -f "$RUN_DIR/flask.pid" ] && ps -p $(cat "$RUN_DIR/flask.pid") > /dev/null; then
             echo -e "Flask:      ${GREEN}Running${NC} (PID: $(cat "$RUN_DIR/flask.pid"))"
             echo -e "     URL: http://127.0.0.1:$PORT"
        else
             echo -e "Flask:      ${RED}Stopped${NC}"
        fi
        
        # Check Docker Services
        if [ -f "$RUN_DIR/docker.mode" ]; then
             echo -e "Mode:       ${CYAN}Docker Production${NC}"
             cd "$ROOT_DIR"
             docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
        else
             # Check Analyzers
             local running_analyzers=$(docker ps --filter "name=analyzer" --format "{{.Names}}" | wc -l)
             if [ "$running_analyzers" -gt 0 ]; then
                 echo -e "Analyzers:  ${GREEN}Running${NC} ($running_analyzers services)"
             else
                 echo -e "Analyzers:  ${RED}Stopped${NC}"
             fi
        fi
        
        echo -e "--------------------------------------------------------------------------------"
        echo -e "Last check: $(date)"
        
        if [ "$loop" != "true" ]; then break; fi
        echo -e "\n${YELLOW}Refreshing in 5s... (Ctrl+C to stop)${NC}"
        sleep 5
    done
}

show_help() {
    write_banner "Help"
    echo "Usage: ./start.sh [MODE] [OPTIONS]"
    echo ""
    echo "Modes:"
    echo "  Start       Start Docker stack"
    echo "  Local       Start local stack (Flask + Containers)"
    echo "  Dev         Dev mode"
    echo "  Reload      Quick reload (Stop → Start)"
    echo "  Stop        Stop services"
    echo "  Logs        Show logs"
    echo "  Monitor     Live status dashboard"
    echo "  Clean       Clean temporary files"
    echo "  Wipeout     Reset system"
    echo "  Nuke        Wipeout + Rebuild"
    echo ""
    echo "Options:"
    echo "  -b, --background   Run in background"
    echo "  --no-analyzer      Skip analyzers"
    echo "  --concurrent       Horizontal scaling mode"
    echo "  --port <p>         Set Flask port"
    echo "  --no-follow        Don't follow logs"
}

show_menu() {
    while true; do
        clear
        write_banner "ThesisApp Orchestrator (Linux)"
        echo -e "${CYAN}Select an option:${NC}"
        echo ""
        echo "  [s] Start        - Start Docker stack"
        echo "  [k] Local        - Start Local stack"
        echo "  [d] Dev          - Start Dev mode"
        echo "  [o] Reload       - Quick reload"
        echo "  [x] Stop         - Stop all services"
        echo "  [l] Logs         - View logs"
        echo "  [m] Monitor      - Live status monitoring"
        echo "  [r] Rebuild      - Rebuild containers"
        echo "  [f] CleanRebuild - Force rebuild"
        echo "  [c] Clean        - Cleanup"
        echo "  [w] Wipeout      - Reset system"
        echo "  [n] Nuke         - Wipeout + Rebuild"
        echo "  [p] Password     - Reset admin password"
        echo "  [q] Quit         - Exit"
        echo ""
        read -p "Enter choice: " choice
        
        case "$choice" in
            s|S) BACKGROUND=true; start_docker_stack; read -p "Press Enter...";;
            k|K) BACKGROUND=true; start_local_stack; read -p "Press Enter...";;
            d|D) start_dev_mode; read -p "Press Enter...";;
            o|O) invoke_reload; read -p "Press Enter...";;
            x|X) stop_all_services; read -p "Press Enter...";;
            l|L) invoke_logs; read -p "Press Enter...";;
            m|M) show_status_dashboard "true";;
            r|R) cd "$ROOT_DIR"; docker compose build --parallel; read -p "Press Enter...";;
            f|F) cd "$ROOT_DIR"; docker builder prune -f; docker compose build --no-cache --parallel; read -p "Press Enter...";;
            c|C) invoke_cleanup; read -p "Press Enter...";;
            w|W) invoke_wipeout; read -p "Press Enter...";;
            n|N) invoke_nuke; read -p "Press Enter...";;
            p|P) "$PYTHON_CMD" "$SRC_DIR/scripts/reset_password.py" 2>/dev/null || echo "Use Wipeout for full reset"; read -p "Press Enter...";;
            q|Q) exit 0 ;;
            *) echo "Invalid choice" ;;
        esac
    done
}

# ============================================================================
# MAIN
# ============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -b|--background)
            BACKGROUND=true
            shift
            ;;
        --no-analyzer)
            NO_ANALYZER=true
            shift
            ;;
        --no-follow)
            NO_FOLLOW=true
            shift
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -v|--verbose)
            # Ignored
            shift
            ;;
        --concurrent)
            CONCURRENT=true
            shift
            ;;
        Start|Docker|Local|Dev|Stop|Logs|Clean|Wipeout|Nuke|Help|Interactive|Rebuild|CleanRebuild|Password|Maintenance|Reload|Status|Health)
            MODE="$1"
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Initialize
initialize_environment
check_dependencies || exit 1

case "$MODE" in
    Interactive)
        show_menu
        ;;
    Start|Docker)
        start_docker_stack
        ;;
    Local)
        start_local_stack
        ;;
    Dev)
        start_dev_mode
        ;;
    Reload)
        invoke_reload
        ;;
    Stop)
        stop_all_services
        ;;
    Logs)
        invoke_logs
        ;;
    Status)
        show_status_dashboard "false"
        ;;
    Health)
        show_status_dashboard "true"
        ;;
    Clean)
        invoke_cleanup
        ;;
    Rebuild)
        cd "$ROOT_DIR"
        write_status "Rebuilding Docker stack..." "Info"
        docker compose build --parallel
        write_status "Rebuild complete" "Success"
        ;;
    CleanRebuild)
        cd "$ROOT_DIR"
        write_status "Clean Rebuilding Docker stack..." "Info"
        docker builder prune -f >/dev/null 2>&1
        docker compose build --no-cache --parallel
        write_status "Clean Rebuild complete" "Success"
        ;;
    Password)
        write_status "Resetting Admin Password..." "Info"
        "$PYTHON_CMD" "$SRC_DIR/scripts/reset_password.py" 2>/dev/null || \
        write_status "Use 'Wipeout' to reset password completely or check documentation." "Warning"
        ;;
    Maintenance)
        write_status "Running Maintenance..." "Info"
        "$PYTHON_CMD" "$SRC_DIR/scripts/maintenance.py" 2>/dev/null || \
        write_status "Maintenance script not found." "Warning"
        ;;
    Wipeout)
        invoke_wipeout
        ;;
    Nuke)
        invoke_nuke
        ;;
    *)
        show_help
        exit 1
        ;;
esac
