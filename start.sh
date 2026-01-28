#!/bin/bash
# =============================================================================
# ThesisApp Orchestrator - Linux Server Deployment Script
# =============================================================================
# Complete orchestration script for ThesisApp with:
# - Dependency-aware startup sequencing (Analyzers -> Flask)
# - Health monitoring and status dashboard
# - Docker Compose management
# - Database management and admin user creation
#
# Usage:
#   ./start.sh              # Interactive menu
#   ./start.sh start        # Start Docker production stack
#   ./start.sh stop         # Stop all services
#   ./start.sh status       # Show status dashboard
#   ./start.sh logs         # View logs
#   ./start.sh rebuild      # Rebuild containers
#   ./start.sh wipeout      # Reset to default state
#   ./start.sh help         # Show help
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
SRC_DIR="$ROOT_DIR/src"
ANALYZER_DIR="$ROOT_DIR/analyzer"
LOGS_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"

# Service configuration
FLASK_PORT="${PORT:-5000}"
FLASK_PID_FILE="$RUN_DIR/flask.pid"
FLASK_LOG_FILE="$LOGS_DIR/app.log"
ANALYZER_LOG_FILE="$LOGS_DIR/analyzer.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

# Icons
CHECK="[OK]"
CROSS="[X]"
WARN="[!]"
INFO="[i]"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

print_banner() {
    local text="$1"
    local color="${2:-$CYAN}"
    local width=70
    local line=$(printf '=%.0s' $(seq 1 $width))

    echo ""
    echo -e "${color}+${line}+${NC}"
    printf "${color}|${NC} %-$((width-2))s ${color}|${NC}\n" "$text"
    echo -e "${color}+${line}+${NC}"
    echo ""
}

print_status() {
    local message="$1"
    local type="${2:-Info}"

    case "$type" in
        Success) echo -e "${GREEN}${CHECK}${NC} $message" ;;
        Warning) echo -e "${YELLOW}${WARN}${NC} $message" ;;
        Error)   echo -e "${RED}${CROSS}${NC} $message" ;;
        *)       echo -e "${BLUE}${INFO}${NC} $message" ;;
    esac
}

print_section() {
    echo ""
    echo -e "${BLUE}$(printf '=%.0s' $(seq 1 70))${NC}"
    echo -e "${BOLD}${WHITE}  $1${NC}"
    echo -e "${BLUE}$(printf '=%.0s' $(seq 1 70))${NC}"
}

# =============================================================================
# INITIALIZATION
# =============================================================================

initialize_environment() {
    print_status "Initializing environment..." "Info"

    # Create required directories
    mkdir -p "$LOGS_DIR" "$RUN_DIR"

    # Ensure shared Docker network exists
    print_status "Ensuring shared Docker network exists..." "Info"
    if ! docker network ls --filter name=thesis-apps-network --format "{{.Name}}" | grep -q thesis-apps-network; then
        docker network create thesis-apps-network 2>/dev/null || true
        print_status "  Created shared network: thesis-apps-network" "Success"
    else
        print_status "  Shared network exists: thesis-apps-network" "Success"
    fi

    # Set environment variables
    export FLASK_ENV="${FLASK_ENV:-production}"
    export HOST="${HOST:-0.0.0.0}"
    export PORT="$FLASK_PORT"
    export PYTHONUNBUFFERED=1

    print_status "Environment initialized" "Success"
}

check_dependencies() {
    print_status "Checking dependencies..." "Info"
    local issues=0

    # Check Python
    if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
        PYTHON_CMD="$ROOT_DIR/.venv/bin/python"
        print_status "  Python: .venv virtual environment found" "Success"
    elif command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
        print_status "  Python: System Python3 found" "Warning"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
        print_status "  Python: System Python found" "Warning"
    else
        print_status "  Python not found" "Error"
        issues=$((issues + 1))
    fi

    # Check Docker
    if docker info &>/dev/null; then
        print_status "  Docker: Running" "Success"
    else
        print_status "  Docker is not running or not installed" "Error"
        issues=$((issues + 1))
    fi

    # Check docker compose
    if docker compose version &>/dev/null; then
        print_status "  Docker Compose: Available" "Success"
    else
        print_status "  Docker Compose not available" "Error"
        issues=$((issues + 1))
    fi

    # Check required directories
    if [ ! -d "$SRC_DIR" ]; then
        print_status "  Source directory not found: $SRC_DIR" "Error"
        issues=$((issues + 1))
    fi

    if [ $issues -gt 0 ]; then
        print_status "Dependency check failed with $issues issue(s)" "Error"
        return 1
    fi

    print_status "All dependencies satisfied" "Success"
    return 0
}

# =============================================================================
# SERVICE MANAGEMENT
# =============================================================================

check_http_service() {
    local url="$1"
    local timeout="${2:-5}"
    curl -s --connect-timeout "$timeout" --max-time "$timeout" "$url" &>/dev/null
}

check_tcp_port() {
    local host="$1"
    local port="$2"
    local timeout="${3:-2}"
    timeout "$timeout" bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null
}

start_docker_stack() {
    print_banner "Starting ThesisApp Docker Production Stack"

    echo -e "${YELLOW}Docker production configuration:${NC}"
    echo "  - Flask app running in container (production mode)"
    echo "  - Celery + Redis for distributed task execution"
    echo "  - All analyzer microservices containerized"
    echo "  - Shared thesis-network for inter-container communication"
    echo ""

    local compose_file="$ROOT_DIR/docker-compose.yml"
    if [ ! -f "$compose_file" ]; then
        print_status "docker-compose.yml not found in project root" "Error"
        return 1
    fi

    print_status "Building and starting Docker production stack..." "Info"
    echo "  (This may take several minutes if images need to be rebuilt)"
    echo ""

    # Define services to start
    local services="web celery-worker redis analyzer-gateway static-analyzer dynamic-analyzer performance-tester ai-analyzer"

    cd "$ROOT_DIR"

    # Build and start services
    echo -e "${DIM}--- Docker Build Output ---${NC}"
    if docker compose up -d --build $services 2>&1 | tee -a "$LOGS_DIR/docker-compose.log"; then
        print_status "Docker containers starting..." "Success"
    else
        print_status "Failed to start Docker stack" "Error"
        return 1
    fi
    echo -e "${DIM}---------------------------${NC}"
    echo ""

    # Wait for services to be ready
    local max_wait=120
    local waited=0

    echo -n "  Waiting for services to be ready"
    while [ $waited -lt $max_wait ]; do
        sleep 2
        waited=$((waited + 2))
        echo -n "."

        if check_http_service "http://127.0.0.1:$FLASK_PORT/api/health"; then
            echo ""
            print_status "All services are ready! (${waited}s)" "Success"
            break
        fi
    done

    if [ $waited -ge $max_wait ]; then
        echo ""
        print_status "Timeout waiting for services (check docker compose logs)" "Warning"
    fi

    # Show container status
    echo ""
    echo -e "${CYAN}Container Status:${NC}"
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | while read line; do
        echo "  $line"
    done

    echo ""
    print_banner "ThesisApp Docker Stack Started" "$GREEN"
    echo -e "${CYAN}Application URL:${NC} http://127.0.0.1:$FLASK_PORT"
    echo -e "${DIM}Task Execution: Celery + Redis (distributed)${NC}"
    echo ""
    echo -e "${CYAN}Quick Commands:${NC}"
    echo "   ./start.sh status    - Check service status"
    echo "   docker compose logs -f  - View live container logs"
    echo "   ./start.sh stop      - Stop all services"
    echo ""

    # Mark Docker mode
    echo "docker-compose" > "$RUN_DIR/docker.mode"

    return 0
}

stop_docker_stack() {
    print_status "Stopping Docker production stack..." "Info"

    cd "$ROOT_DIR"
    docker compose down 2>&1 || true

    print_status "Docker stack stopped" "Success"

    # Clean up mode file
    rm -f "$RUN_DIR/docker.mode" 2>/dev/null || true
}

stop_all_services() {
    print_banner "Stopping ThesisApp Services"

    # Check if we're in Docker mode
    if [ -f "$RUN_DIR/docker.mode" ]; then
        stop_docker_stack
    fi

    # Stop any local Flask process
    if [ -f "$FLASK_PID_FILE" ]; then
        local pid=$(cat "$FLASK_PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            print_status "Stopping Flask (PID: $pid)..." "Info"
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$FLASK_PID_FILE"
    fi

    # Stop Celery worker and Redis containers if running standalone
    cd "$ROOT_DIR"
    docker compose stop celery-worker redis 2>/dev/null || true

    print_status "All services stopped" "Success"
}

# =============================================================================
# STATUS & HEALTH
# =============================================================================

show_status_dashboard() {
    print_banner "ThesisApp Status Dashboard"

    print_section "Core Services"

    # Flask Health
    echo -n "  Checking Flask API... "
    if check_http_service "http://127.0.0.1:$FLASK_PORT/api/health" 5; then
        echo -e "${GREEN}${CHECK} HEALTHY${NC}"
    else
        echo -e "${RED}${CROSS} UNHEALTHY${NC}"
    fi

    # Redis
    echo -n "  Checking Redis... "
    if docker compose ps redis 2>/dev/null | grep -q "running"; then
        echo -e "${GREEN}${CHECK} RUNNING${NC}"
    else
        echo -e "${RED}${CROSS} NOT RUNNING${NC}"
    fi

    # Celery Worker
    echo -n "  Checking Celery Worker... "
    if docker compose ps celery-worker 2>/dev/null | grep -q "running"; then
        echo -e "${GREEN}${CHECK} RUNNING${NC}"
    else
        echo -e "${RED}${CROSS} NOT RUNNING${NC}"
    fi

    print_section "Analyzer Services"

    local analyzer_services=("static-analyzer:2001" "dynamic-analyzer:2002" "performance-tester:2003" "ai-analyzer:2004")

    for service in "${analyzer_services[@]}"; do
        local name="${service%%:*}"
        local port="${service##*:}"

        echo -n "  Checking $name:$port... "
        if check_http_service "http://localhost:$port/health" 3; then
            echo -e "${GREEN}${CHECK} HEALTHY${NC}"
        else
            echo -e "${RED}${CROSS} UNHEALTHY${NC}"
        fi
    done

    print_section "Container Status"
    cd "$ROOT_DIR"
    docker compose ps 2>/dev/null || echo "  Docker Compose not running"

    echo ""
    echo -e "${DIM}Last check: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""
}

# =============================================================================
# LOGS
# =============================================================================

show_logs() {
    local lines="${1:-100}"
    print_banner "Application Logs (last $lines lines)"

    cd "$ROOT_DIR"
    docker compose logs --tail="$lines" 2>/dev/null || echo "No logs available"
}

follow_logs() {
    print_banner "Following Application Logs (Ctrl+C to stop)"

    cd "$ROOT_DIR"
    docker compose logs -f 2>/dev/null || echo "No logs available"
}

# =============================================================================
# REBUILD
# =============================================================================

rebuild_containers() {
    print_banner "Rebuilding Docker Stack"

    cd "$ROOT_DIR"

    print_status "Stopping and removing existing containers..." "Info"
    docker compose down 2>&1 || true

    # Enable BuildKit for faster builds
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1

    print_status "Building with BuildKit optimization..." "Info"
    echo "  - Shared base image caching enabled"
    echo "  - Multi-stage builds with layer reuse"
    echo ""

    docker compose build --parallel

    if [ $? -eq 0 ]; then
        echo ""
        print_banner "Rebuild Complete" "$GREEN"

        echo -e "${YELLOW}Would you like to start all services now? (y/N): ${NC}"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            start_docker_stack
        else
            print_status "Services not started - use './start.sh start' to launch" "Info"
        fi
    else
        print_status "Rebuild failed" "Error"
        return 1
    fi
}

clean_rebuild() {
    print_banner "Clean Rebuild - Complete Cache Wipe" "$YELLOW"

    echo -e "${YELLOW}This will:${NC}"
    echo "  - Remove all Docker images and volumes"
    echo "  - Clear BuildKit cache"
    echo "  - Force complete rebuild from scratch"
    echo ""
    echo -e "${YELLOW}Type 'CLEAN' to confirm (or anything else to cancel): ${NC}"
    read -r confirmation

    if [ "$confirmation" != "CLEAN" ]; then
        print_status "Clean rebuild cancelled" "Warning"
        return 0
    fi

    cd "$ROOT_DIR"

    print_status "Performing deep clean..." "Info"
    docker compose down --rmi all --volumes 2>&1 || true

    print_status "Clearing BuildKit cache..." "Info"
    docker builder prune --all --force 2>&1 || true

    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1

    print_status "Building from scratch..." "Warning"
    docker compose build --no-cache --parallel

    if [ $? -eq 0 ]; then
        print_banner "Clean Rebuild Complete" "$GREEN"

        echo -e "${YELLOW}Would you like to start all services now? (y/N): ${NC}"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            start_docker_stack
        fi
    else
        print_status "Clean rebuild failed" "Error"
        return 1
    fi
}

# =============================================================================
# CLEANUP & WIPEOUT
# =============================================================================

cleanup() {
    print_banner "Cleaning ThesisApp"

    print_status "Removing PID files..." "Info"
    rm -f "$RUN_DIR"/*.pid 2>/dev/null || true

    print_status "Rotating logs..." "Info"
    for log in "$LOGS_DIR"/*.log; do
        if [ -f "$log" ]; then
            mv "$log" "${log}.old" 2>/dev/null || true
        fi
    done

    print_status "Cleanup completed" "Success"
}

wipeout() {
    print_banner "WIPEOUT - Reset to Default State" "$RED"

    echo -e "${YELLOW}This will:${NC}"
    echo "  - Stop all running services"
    echo "  - Delete the database (src/data/)"
    echo "  - Remove all generated apps (generated/)"
    echo "  - Remove all analysis results (results/)"
    echo "  - Remove all reports (reports/)"
    echo "  - Remove Docker containers, images, and volumes"
    echo "  - Create fresh admin user"
    echo ""
    echo -e "${RED}THIS CANNOT BE UNDONE!${NC}"
    echo ""
    echo -e "${YELLOW}Type 'YES' to confirm: ${NC}"
    read -r confirmation

    if [ "$confirmation" != "YES" ]; then
        print_status "Wipeout cancelled" "Info"
        return 0
    fi

    print_status "Starting wipeout procedure..." "Warning"

    # 1. Stop all services
    print_status "Stopping all services..." "Info"
    stop_all_services
    sleep 2

    # 2. Remove Docker resources
    print_status "Removing Docker resources..." "Info"
    cd "$ROOT_DIR"
    docker compose down --rmi local --volumes --remove-orphans 2>&1 || true

    # 3. Remove database
    local db_dir="$SRC_DIR/data"
    if [ -d "$db_dir" ]; then
        print_status "Removing database..." "Info"
        rm -rf "$db_dir"
        print_status "  Database removed" "Success"
    fi

    # 4. Remove generated apps
    local generated_dir="$ROOT_DIR/generated"
    if [ -d "$generated_dir" ]; then
        print_status "Removing generated apps..." "Info"
        find "$generated_dir" -mindepth 1 -maxdepth 1 ! -name ".migration_done" -exec rm -rf {} \; 2>/dev/null || true
        print_status "  Generated apps removed" "Success"
    fi

    # 5. Remove results
    local results_dir="$ROOT_DIR/results"
    if [ -d "$results_dir" ]; then
        print_status "Removing analysis results..." "Info"
        rm -rf "$results_dir"
        mkdir -p "$results_dir"
        print_status "  Results removed" "Success"
    fi

    # 6. Remove reports
    local reports_dir="$ROOT_DIR/reports"
    if [ -d "$reports_dir" ]; then
        print_status "Removing reports..." "Info"
        rm -rf "$reports_dir"
        mkdir -p "$reports_dir"
        print_status "  Reports removed" "Success"
    fi

    # 7. Remove logs
    print_status "Removing all logs..." "Info"
    rm -f "$LOGS_DIR"/*.log "$LOGS_DIR"/*.old 2>/dev/null || true
    print_status "  Logs removed" "Success"

    # 8. Remove PID files
    print_status "Removing PID files..." "Info"
    rm -f "$RUN_DIR"/*.pid "$RUN_DIR"/*.mode 2>/dev/null || true

    # 9. Initialize fresh database
    print_status "Initializing fresh database..." "Info"
    local init_db_script="$SRC_DIR/init_db.py"
    if [ -f "$init_db_script" ]; then
        $PYTHON_CMD "$init_db_script" 2>&1 || true
        print_status "  Database initialized" "Success"
    fi

    # 10. Create admin user with random password
    print_status "Creating admin user..." "Info"
    local new_password=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9!@#$%^&*' | fold -w 16 | head -n 1)

    cat > /tmp/create_admin.py << PYEOF
import sys
from pathlib import Path
sys.path.insert(0, str(Path("$SRC_DIR")))

from app.factory import create_app
from app.models import User
from app.extensions import db

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@thesis.local',
            full_name='System Administrator'
        )
        admin.set_password('$new_password')
        admin.is_admin = True
        admin.is_active = True
        db.session.add(admin)
        db.session.commit()
        print('CREATED')
    else:
        admin.set_password('$new_password')
        db.session.commit()
        print('SUCCESS')
PYEOF

    local output=$($PYTHON_CMD /tmp/create_admin.py 2>&1)
    rm -f /tmp/create_admin.py

    if [[ "$output" == *"SUCCESS"* ]] || [[ "$output" == *"CREATED"* ]]; then
        print_status "  Admin user created successfully" "Success"
    else
        print_status "  Warning: Could not create admin user" "Warning"
    fi

    print_banner "Wipeout Complete - System Reset" "$GREEN"

    # Auto-restart
    print_status "Restarting application..." "Info"
    sleep 1

    if start_docker_stack; then
        echo ""
        print_banner "Application Restarted" "$GREEN"
    else
        print_status "Application restart failed - try './start.sh start' manually" "Warning"
    fi

    # Display credentials
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}  NEW ADMIN CREDENTIALS${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo -e "  Username: ${GREEN}admin${NC}"
    echo -e "  Password: ${GREEN}$new_password${NC}"
    echo -e "  Email:    ${GREEN}admin@thesis.local${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo ""
    echo -e "${YELLOW}IMPORTANT: Save this password now! It will not be shown again.${NC}"
    echo ""

    return 0
}

# =============================================================================
# PASSWORD RESET
# =============================================================================

reset_password() {
    print_banner "Reset Admin Password"

    echo "This will reset the admin user password to a new random value."
    echo ""
    echo -e "${YELLOW}Continue? (y/N): ${NC}"
    read -r response

    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_status "Password reset cancelled" "Info"
        return 0
    fi

    local new_password=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9!@#$%^&*' | fold -w 16 | head -n 1)

    print_status "Resetting admin password..." "Info"

    # Check if Docker mode
    if [ -f "$RUN_DIR/docker.mode" ]; then
        print_status "Detected Docker environment - executing inside container..." "Info"

        cd "$ROOT_DIR"
        local container_id=$(docker compose ps -q web 2>/dev/null | head -1)

        if [ -z "$container_id" ]; then
            print_status "Could not find running 'web' container. Ensure the stack is running." "Error"
            return 1
        fi

        cat > /tmp/reset_password.py << PYEOF
import sys
sys.path.insert(0, '/app/src')

from app.factory import create_app
from app.models import User
from app.extensions import db

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@thesis.local',
            full_name='System Administrator'
        )
        admin.set_password('$new_password')
        admin.is_admin = True
        admin.is_active = True
        db.session.add(admin)
        db.session.commit()
        print('CREATED')
    else:
        admin.set_password('$new_password')
        db.session.commit()
        print('SUCCESS')
PYEOF

        docker cp /tmp/reset_password.py "$container_id:/tmp/reset_password.py"
        local output=$(docker exec "$container_id" python /tmp/reset_password.py 2>&1)
        docker exec "$container_id" rm /tmp/reset_password.py 2>/dev/null || true
        rm -f /tmp/reset_password.py
    else
        # Local execution
        cat > /tmp/reset_password.py << PYEOF
import sys
from pathlib import Path
sys.path.insert(0, str(Path("$SRC_DIR")))

from app.factory import create_app
from app.models import User
from app.extensions import db

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@thesis.local',
            full_name='System Administrator'
        )
        admin.set_password('$new_password')
        admin.is_admin = True
        admin.is_active = True
        db.session.add(admin)
        db.session.commit()
        print('CREATED')
    else:
        admin.set_password('$new_password')
        db.session.commit()
        print('SUCCESS')
PYEOF
        local output=$($PYTHON_CMD /tmp/reset_password.py 2>&1)
        rm -f /tmp/reset_password.py
    fi

    if [[ "$output" == *"SUCCESS"* ]] || [[ "$output" == *"CREATED"* ]]; then
        print_banner "Password Reset Successfully" "$GREEN"
        echo ""
        echo -e "${CYAN}New Admin Credentials:${NC}"
        echo -e "  Username: ${GREEN}admin${NC}"
        echo -e "  Password: ${GREEN}$new_password${NC}"
        echo ""
        echo -e "${YELLOW}IMPORTANT: Save this password now! It will not be shown again.${NC}"
        echo ""
    else
        print_status "Failed to reset password" "Error"
        echo "Output: $output"
    fi
}

# =============================================================================
# MAINTENANCE
# =============================================================================

run_maintenance() {
    print_banner "Manual Maintenance Cleanup" "$YELLOW"

    echo "This will run the maintenance service to clean up:"
    echo "  - Orphan app records (apps missing from filesystem for >7 days)"
    echo "  - Orphan tasks (tasks targeting non-existent apps)"
    echo "  - Stuck tasks (RUNNING for >2 hours, PENDING for >4 hours)"
    echo "  - Old completed/failed tasks (>30 days old)"
    echo ""
    echo "Press Enter to continue or Ctrl+C to cancel..."
    read -r

    print_status "Running maintenance cleanup..." "Info"

    cat > /tmp/maintenance.py << 'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, '/app/src')

from app.factory import create_app
from app.services.maintenance_service import get_maintenance_service

app = create_app()

with app.app_context():
    service = get_maintenance_service()
    if service is None:
        print("ERROR: Maintenance service not initialized")
        sys.exit(1)

    print("\n=== Running Manual Maintenance Cleanup ===\n")
    service._run_maintenance()

    print("\n=== Maintenance Statistics ===")
    stats = service.stats
    print(f"Total runs: {stats['runs']}")
    print(f"Orphan apps cleaned: {stats['orphan_apps_cleaned']}")
    print(f"Orphan tasks cleaned: {stats['orphan_tasks_cleaned']}")
    print(f"Stuck tasks cleaned: {stats['stuck_tasks_cleaned']}")
    print(f"Old tasks cleaned: {stats['old_tasks_cleaned']}")
    print(f"Errors: {stats['errors']}")
    print()
PYEOF

    if [ -f "$RUN_DIR/docker.mode" ]; then
        cd "$ROOT_DIR"
        local container_id=$(docker compose ps -q web 2>/dev/null | head -1)
        if [ -n "$container_id" ]; then
            docker cp /tmp/maintenance.py "$container_id:/tmp/maintenance.py"
            docker exec "$container_id" python /tmp/maintenance.py
            docker exec "$container_id" rm /tmp/maintenance.py 2>/dev/null || true
        fi
    else
        $PYTHON_CMD /tmp/maintenance.py
    fi

    rm -f /tmp/maintenance.py
    print_status "Maintenance cleanup completed" "Success"
}

# =============================================================================
# HELP
# =============================================================================

show_help() {
    print_banner "ThesisApp Orchestrator - Help"

    echo -e "${CYAN}USAGE:${NC}"
    echo "  ./start.sh [COMMAND] [OPTIONS]"
    echo ""
    echo -e "${CYAN}COMMANDS:${NC}"
    echo "  (none)        Interactive menu (default)"
    echo "  start         Start Docker production stack"
    echo "  stop          Stop all services gracefully"
    echo "  status        Show service status dashboard"
    echo "  logs [N]      Show last N lines of logs (default: 100)"
    echo "  logs-follow   Follow logs in real-time"
    echo "  rebuild       Rebuild containers (with cache)"
    echo "  clean-rebuild Force rebuild from scratch (no cache)"
    echo "  cleanup       Clean logs and PID files"
    echo "  wipeout       Reset to default state (removes all data)"
    echo "  password      Reset admin password"
    echo "  maintenance   Run maintenance cleanup"
    echo "  help          Show this help message"
    echo ""
    echo -e "${CYAN}EXAMPLES:${NC}"
    echo "  ./start.sh"
    echo "    -> Interactive menu"
    echo ""
    echo "  ./start.sh start"
    echo "    -> Start full Docker production stack"
    echo ""
    echo "  ./start.sh logs 200"
    echo "    -> Show last 200 lines of logs"
    echo ""
    echo "  ./start.sh wipeout"
    echo "    -> Reset system to default state"
    echo ""
    echo -e "${CYAN}SERVICE URLS:${NC}"
    echo "  Flask App:           http://127.0.0.1:$FLASK_PORT"
    echo "  Static Analyzer:     ws://localhost:2001"
    echo "  Dynamic Analyzer:    ws://localhost:2002"
    echo "  Performance Tester:  ws://localhost:2003"
    echo "  AI Analyzer:         ws://localhost:2004"
    echo ""
}

# =============================================================================
# INTERACTIVE MENU
# =============================================================================

show_interactive_menu() {
    while true; do
        clear
        print_banner "ThesisApp Orchestrator"

        echo "Select an option:"
        echo ""
        echo "  [S] Start         - Start Docker production stack"
        echo "  [X] Stop          - Stop all services"
        echo "  [T] Status        - Show service status"
        echo "  [L] Logs          - View logs (last 100 lines)"
        echo "  [F] Follow Logs   - Follow logs in real-time"
        echo "  [R] Rebuild       - Rebuild containers (with cache)"
        echo "  [C] Clean Rebuild - Force rebuild (no cache)"
        echo "  [K] Cleanup       - Clean logs and PID files"
        echo "  [W] Wipeout       - Reset to default state"
        echo "  [P] Password      - Reset admin password"
        echo "  [M] Maintenance   - Run maintenance cleanup"
        echo "  [H] Help          - Show help"
        echo "  [Q] Quit          - Exit"
        echo ""
        echo -n "Enter choice: "
        read -r choice

        case "${choice^^}" in
            S)
                start_docker_stack
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            X)
                stop_all_services
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            T)
                show_status_dashboard
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            L)
                show_logs 100
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            F)
                follow_logs
                ;;
            R)
                rebuild_containers
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            C)
                clean_rebuild
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            K)
                cleanup
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            W)
                wipeout
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            P)
                reset_password
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            M)
                run_maintenance
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            H)
                show_help
                echo ""
                echo "Press Enter to return to menu..."
                read -r
                ;;
            Q)
                echo ""
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                sleep 1
                ;;
        esac
    done
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    # Initialize
    initialize_environment

    if ! check_dependencies; then
        exit 1
    fi

    # Parse command
    local command="${1:-menu}"
    shift 2>/dev/null || true

    case "$command" in
        start)
            start_docker_stack
            ;;
        stop)
            stop_all_services
            ;;
        status)
            show_status_dashboard
            ;;
        logs)
            show_logs "${1:-100}"
            ;;
        logs-follow|follow)
            follow_logs
            ;;
        rebuild)
            rebuild_containers
            ;;
        clean-rebuild)
            clean_rebuild
            ;;
        cleanup|clean)
            cleanup
            ;;
        wipeout)
            wipeout
            ;;
        password)
            reset_password
            ;;
        maintenance)
            run_maintenance
            ;;
        help|--help|-h)
            show_help
            ;;
        menu|"")
            show_interactive_menu
            ;;
        *)
            echo -e "${RED}Unknown command: $command${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
