#!/usr/bin/env bash
#
# ThesisApp Orchestrator - Modern service management for Flask + Analyzers
# Bash version for Ubuntu Server
#
# Complete orchestration script for ThesisApp with:
# - Dependency-aware startup sequencing (Analyzers → Flask)
# - Real-time health monitoring with auto-refresh
# - Live log aggregation with color-coded output
# - Interactive mode selection and graceful shutdown
# - Developer mode with configurable analyzer stack
#
# Usage:
#   ./start.sh                     # Interactive mode with menu
#   ./start.sh start               # Start full stack
#   ./start.sh dev                 # Developer mode
#   ./start.sh dev --no-analyzer   # Dev mode without analyzers
#   ./start.sh stop                # Stop all services
#   ./start.sh status              # Check service status
#   ./start.sh logs                # View aggregated logs
#   ./start.sh --help              # Show help
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SRC_DIR="$SCRIPT_DIR/src"
readonly ANALYZER_DIR="$SCRIPT_DIR/analyzer"
readonly LOGS_DIR="$SCRIPT_DIR/logs"
readonly RUN_DIR="$SCRIPT_DIR/run"

# Flask configuration
readonly FLASK_PID_FILE="$RUN_DIR/flask.pid"
readonly FLASK_LOG_FILE="$LOGS_DIR/app.log"
readonly FLASK_STARTUP_TIME=10

# Analyzer configuration
readonly ANALYZER_PID_FILE="$RUN_DIR/analyzer.pid"
readonly ANALYZER_LOG_FILE="$LOGS_DIR/analyzer.log"
readonly ANALYZER_SERVICES=("static-analyzer" "dynamic-analyzer" "performance-tester" "ai-analyzer")
readonly ANALYZER_PORTS=(2001 2002 2003 2004)
readonly ANALYZER_STARTUP_TIME=15

# Default options
FLASK_PORT=5000
NO_ANALYZER=false
NO_FOLLOW=false
BACKGROUND=false
DEBUG_MODE=false

# Python command (will be detected)
PYTHON_CMD=""

# ============================================================================
# ANSI COLOR CODES
# ============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[0;37m'
readonly GRAY='\033[0;90m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Status icons (Unicode)
readonly ICON_SUCCESS="✅"
readonly ICON_ERROR="❌"
readonly ICON_WARNING="⚠️ "
readonly ICON_INFO="ℹ️ "
readonly ICON_RUNNING="🟢"
readonly ICON_STOPPED="🔴"
readonly ICON_DEGRADED="🟡"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

write_banner() {
    local text="$1"
    local color="${2:-$CYAN}"
    local width=80
    local text_len=${#text}
    local padding=$(( (width - text_len - 4) / 2 ))
    local line=""
    
    for ((i=0; i<width; i++)); do
        line+="═"
    done
    
    local spaces=""
    for ((i=0; i<padding; i++)); do
        spaces+=" "
    done
    
    echo ""
    echo -e "${color}╔${line}╗${NC}"
    echo -e "${color}║${spaces} ${text} ${spaces}║${NC}"
    echo -e "${color}╚${line}╝${NC}"
    echo ""
}

log_info() {
    echo -e "${ICON_INFO} ${CYAN}$1${NC}"
}

log_success() {
    echo -e "${ICON_SUCCESS} ${GREEN}$1${NC}"
}

log_warning() {
    echo -e "${ICON_WARNING}${YELLOW}$1${NC}"
}

log_error() {
    echo -e "${ICON_ERROR} ${RED}$1${NC}"
}

# ============================================================================
# ENVIRONMENT INITIALIZATION
# ============================================================================

initialize_environment() {
    log_info "Initializing environment..."
    
    # Create required directories
    for dir in "$LOGS_DIR" "$RUN_DIR"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_info "  Created directory: $dir"
        fi
    done
    
    # Set environment variables
    export FLASK_ENV="development"
    export HOST="127.0.0.1"
    export PORT="$FLASK_PORT"
    export DEBUG="false"
    export PYTHONUTF8="1"
    export PYTHONIOENCODING="utf-8"
    export DOCKER_BUILDKIT="1"
    export COMPOSE_DOCKER_CLI_BUILD="1"
    
    log_success "Environment initialized"
}

# ============================================================================
# DEPENDENCY CHECKS
# ============================================================================

find_python() {
    # Priority: venv python > python3 > python
    local venv_python="$SCRIPT_DIR/.venv/bin/python"
    
    if [[ -x "$venv_python" ]]; then
        PYTHON_CMD="$venv_python"
        log_success "  Python: .venv virtual environment found"
        return 0
    elif command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
        log_warning "  Python: System python3 found (consider using venv)"
        return 0
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
        log_warning "  Python: System python found (consider using venv)"
        return 0
    else
        return 1
    fi
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    local issues=()
    
    # Check Python
    if ! find_python; then
        issues+=("Python not found (neither .venv nor system)")
    fi
    
    # Check Docker
    if command -v docker &>/dev/null; then
        if docker info &>/dev/null; then
            log_success "  Docker: Running"
        else
            # Check if user is in docker group
            if groups | grep -q docker; then
                issues+=("Docker daemon not running")
            else
                log_warning "  Docker: User not in docker group (may need sudo)"
                issues+=("Docker requires root/sudo or user in docker group")
            fi
        fi
    else
        issues+=("Docker not found")
    fi
    
    # Check required directories
    if [[ ! -d "$SRC_DIR" ]]; then
        issues+=("Source directory not found: $SRC_DIR")
    fi
    if [[ ! -d "$ANALYZER_DIR" ]]; then
        issues+=("Analyzer directory not found: $ANALYZER_DIR")
    fi
    
    if [[ ${#issues[@]} -gt 0 ]]; then
        log_error "Dependency check failed:"
        for issue in "${issues[@]}"; do
            echo -e "  ${RED}• $issue${NC}"
        done
        return 1
    fi
    
    log_success "All dependencies satisfied"
    return 0
}

# ============================================================================
# SERVICE MANAGEMENT - ANALYZERS
# ============================================================================

start_analyzer_services() {
    if [[ "$NO_ANALYZER" == "true" ]]; then
        log_warning "Skipping analyzer services (--no-analyzer flag)"
        return 0
    fi
    
    log_info "Starting analyzer microservices..."
    
    pushd "$ANALYZER_DIR" > /dev/null
    
    # Start all analyzer services
    if ! docker-compose up -d >> "$ANALYZER_LOG_FILE" 2>&1; then
        log_error "  Failed to start analyzer containers"
        popd > /dev/null
        return 1
    fi
    
    # Wait for services to be ready
    local max_wait=$ANALYZER_STARTUP_TIME
    local waited=0
    
    echo -ne "  ${CYAN}Waiting for services${NC}"
    while [[ $waited -lt $max_wait ]]; do
        local running
        running=$(docker-compose ps --services --filter status=running 2>/dev/null | wc -l)
        
        if [[ $running -ge 4 ]]; then
            echo ""
            log_success "  All analyzer services started ($running/4)"
            popd > /dev/null
            return 0
        fi
        
        echo -n "."
        sleep 1
        ((waited++))
    done
    
    echo ""
    log_warning "  Some analyzer services may not have started"
    popd > /dev/null
    return 0
}

stop_analyzer_services() {
    log_info "Stopping analyzer services..."
    
    pushd "$ANALYZER_DIR" > /dev/null
    docker-compose stop >> "$ANALYZER_LOG_FILE" 2>&1 || true
    popd > /dev/null
    
    if [[ -f "$ANALYZER_PID_FILE" ]]; then
        rm -f "$ANALYZER_PID_FILE"
    fi
    
    log_success "  Analyzers stopped"
}

# ============================================================================
# SERVICE MANAGEMENT - FLASK
# ============================================================================

start_flask_app() {
    log_info "Starting Flask application..."
    
    # Check if already running
    if [[ -f "$FLASK_PID_FILE" ]]; then
        local existing_pid
        existing_pid=$(cat "$FLASK_PID_FILE")
        if kill -0 "$existing_pid" 2>/dev/null; then
            log_warning "  Flask already running (PID: $existing_pid)"
            return 0
        fi
    fi
    
    if [[ "$BACKGROUND" == "true" ]]; then
        # Background mode
        nohup "$PYTHON_CMD" "$SRC_DIR/main.py" >> "$FLASK_LOG_FILE" 2>&1 &
        local flask_pid=$!
        echo "$flask_pid" > "$FLASK_PID_FILE"
        
        log_success "  Flask started in background (PID: $flask_pid)"
        echo -e "    ${GRAY}URL: http://127.0.0.1:$FLASK_PORT${NC}"
    else
        # Foreground mode (for dev)
        log_info "  Starting Flask in foreground (Ctrl+C to stop)..."
        echo -e "    ${GRAY}URL: http://127.0.0.1:$FLASK_PORT${NC}"
        echo ""
        
        # Run in foreground - this will block
        "$PYTHON_CMD" "$SRC_DIR/main.py"
    fi
    
    return 0
}

stop_flask_app() {
    log_info "Stopping Flask application..."
    
    if [[ -f "$FLASK_PID_FILE" ]]; then
        local pid
        pid=$(cat "$FLASK_PID_FILE")
        
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            
            # Wait for process to exit (max 5 seconds)
            local waited=0
            while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 5 ]]; do
                sleep 1
                ((waited++))
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        
        rm -f "$FLASK_PID_FILE"
        log_success "  Flask stopped"
    else
        log_info "  Flask not running (no PID file)"
    fi
}

# ============================================================================
# SERVICE MANAGEMENT - COMBINED
# ============================================================================

stop_all_services() {
    write_banner "Stopping ThesisApp Services"
    
    # Stop in reverse dependency order
    stop_flask_app
    stop_analyzer_services
    
    log_success "All services stopped"
}

start_full_stack() {
    write_banner "Starting ThesisApp Full Stack"
    
    # Dependency-aware startup sequence
    
    # 1. Analyzer services (optional but recommended)
    if ! start_analyzer_services; then
        log_warning "Analyzer services failed, but continuing..."
    fi
    
    # 2. Flask app
    BACKGROUND=true
    if ! start_flask_app; then
        log_error "Failed to start Flask application"
        return 1
    fi
    
    # Wait for Flask to be fully ready
    echo -e "\n${YELLOW}⏳ Waiting for Flask to be ready...${NC}"
    local max_wait=10
    local waited=0
    
    while [[ $waited -lt $max_wait ]]; do
        if check_flask_health_quiet; then
            echo ""
            break
        fi
        echo -n "."
        sleep 1
        ((waited++))
    done
    
    echo ""
    write_banner "ThesisApp Started Successfully" "$GREEN"
    echo -e "${CYAN}🌐 Application URL: ${WHITE}http://127.0.0.1:$FLASK_PORT${NC}"
    echo -e "${GRAY}⚡ Task Execution: Background ThreadPoolExecutor${NC}"
    echo ""
    echo -e "${CYAN}💡 Quick Commands:${NC}"
    echo -e "   ${GRAY}./start.sh status    - Check service status${NC}"
    echo -e "   ${GRAY}./start.sh logs      - View aggregated logs${NC}"
    echo -e "   ${GRAY}./start.sh stop      - Stop all services${NC}"
    echo ""
    
    return 0
}

start_dev_mode() {
    write_banner "Starting ThesisApp (Developer Mode)"
    
    echo -e "${YELLOW}Developer mode configuration:${NC}"
    echo -e "  ${GRAY}• Flask with ThreadPoolExecutor (4 workers)${NC}"
    echo -e "  ${GRAY}• Debug enabled${NC}"
    echo -e "  ${GRAY}• Analyzer services: $(if [[ "$NO_ANALYZER" == "true" ]]; then echo 'Disabled'; else echo 'Enabled'; fi)${NC}"
    echo ""
    
    export DEBUG="true"
    export FLASK_ENV="development"
    
    # Start analyzers if not disabled
    if [[ "$NO_ANALYZER" != "true" ]]; then
        start_analyzer_services || true
    fi
    
    # Start Flask in foreground (dev mode is interactive)
    BACKGROUND=false
    start_flask_app
}

# ============================================================================
# HEALTH CHECKS
# ============================================================================

check_flask_health_quiet() {
    if [[ ! -f "$FLASK_PID_FILE" ]]; then
        return 1
    fi
    
    local pid
    pid=$(cat "$FLASK_PID_FILE")
    if ! kill -0 "$pid" 2>/dev/null; then
        return 1
    fi
    
    # Check HTTP health endpoint
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:$FLASK_PORT/health" 2>/dev/null) || true
    [[ "$response" == "200" ]]
}

check_analyzer_health_quiet() {
    pushd "$ANALYZER_DIR" > /dev/null
    local running
    running=$(docker-compose ps --services --filter status=running 2>/dev/null | wc -l) || running=0
    popd > /dev/null
    [[ $running -ge 4 ]]
}

show_status_dashboard() {
    local continuous="${1:-false}"
    
    while true; do
        if [[ "$continuous" == "true" ]]; then
            clear
        fi
        
        write_banner "ThesisApp Status Dashboard"
        
        echo -e "${CYAN}Services Status:${NC}"
        echo -e "${GRAY}────────────────────────────────────────────────────────────────────────────────${NC}"
        
        # Analyzers status
        echo -ne "  "
        if check_analyzer_health_quiet; then
            echo -e "${ICON_RUNNING} ${GREEN}Analyzers: Running${NC}"
            pushd "$ANALYZER_DIR" > /dev/null
            local services
            services=$(docker-compose ps --services --filter status=running 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
            popd > /dev/null
            echo -e "     ${GRAY}Services: $services${NC}"
            echo -e "     ${GRAY}Ports: 2001-2004${NC}"
        else
            if [[ "$NO_ANALYZER" == "true" ]]; then
                echo -e "${ICON_STOPPED} ${GRAY}Analyzers: Disabled (--no-analyzer)${NC}"
            else
                echo -e "${ICON_STOPPED} ${RED}Analyzers: Stopped${NC}"
            fi
        fi
        
        # Flask status
        echo -ne "  "
        if check_flask_health_quiet; then
            local flask_pid
            flask_pid=$(cat "$FLASK_PID_FILE" 2>/dev/null || echo "unknown")
            echo -e "${ICON_RUNNING} ${GREEN}Flask: Running${NC}"
            echo -e "     ${GRAY}URL: http://127.0.0.1:$FLASK_PORT${NC}"
            echo -e "     ${GRAY}PID: $flask_pid${NC}"
        else
            echo -e "${ICON_STOPPED} ${RED}Flask: Stopped${NC}"
        fi
        
        echo -e "${GRAY}────────────────────────────────────────────────────────────────────────────────${NC}"
        echo -e "${GRAY}Last check: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
        
        if [[ "$continuous" == "true" ]]; then
            echo -e "\n${GRAY}Refreshing in 5 seconds... (Ctrl+C to exit)${NC}"
            sleep 5
        else
            break
        fi
    done
}

# ============================================================================
# LOG MANAGEMENT
# ============================================================================

show_logs() {
    if [[ "$NO_FOLLOW" == "true" ]]; then
        show_log_snapshot
    else
        show_live_logs
    fi
}

show_log_snapshot() {
    echo -e "\n${CYAN}📜 Log Snapshot (last 50 lines per service):${NC}\n"
    
    # Flask logs
    echo -e "${CYAN}━━━ Flask ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [[ -f "$FLASK_LOG_FILE" ]]; then
        tail -n 50 "$FLASK_LOG_FILE"
    else
        echo -e "${GRAY}(No log file found)${NC}"
    fi
    echo ""
    
    # Analyzer logs
    echo -e "${GREEN}━━━ Analyzers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [[ -f "$ANALYZER_LOG_FILE" ]]; then
        tail -n 50 "$ANALYZER_LOG_FILE"
    else
        echo -e "${GRAY}(No log file found)${NC}"
    fi
    echo ""
}

show_live_logs() {
    echo -e "\n${CYAN}📜 Starting live log aggregation (Ctrl+C to stop)...${NC}"
    echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    # Check if multitail is available for better log viewing
    if command -v multitail &>/dev/null; then
        multitail -ci green "$FLASK_LOG_FILE" -ci blue "$ANALYZER_LOG_FILE"
    else
        # Simple approach: tail both with prefixes using named pipes
        local flask_exists=false
        local analyzer_exists=false
        
        [[ -f "$FLASK_LOG_FILE" ]] && flask_exists=true
        [[ -f "$ANALYZER_LOG_FILE" ]] && analyzer_exists=true
        
        if [[ "$flask_exists" == "true" && "$analyzer_exists" == "true" ]]; then
            # Tail both files
            tail -f "$FLASK_LOG_FILE" 2>/dev/null | sed "s/^/[Flask] /" &
            local flask_tail_pid=$!
            tail -f "$ANALYZER_LOG_FILE" 2>/dev/null | sed "s/^/[Analyzer] /" &
            local analyzer_tail_pid=$!
            
            # Wait for interrupt
            trap "kill $flask_tail_pid $analyzer_tail_pid 2>/dev/null; exit 0" INT TERM
            wait
        elif [[ "$flask_exists" == "true" ]]; then
            tail -f "$FLASK_LOG_FILE"
        elif [[ "$analyzer_exists" == "true" ]]; then
            tail -f "$ANALYZER_LOG_FILE"
        else
            echo -e "${YELLOW}No log files found. Start services first.${NC}"
        fi
    fi
}

# ============================================================================
# REBUILD OPERATIONS
# ============================================================================

invoke_rebuild() {
    write_banner "Rebuilding Analyzer Containers"
    
    log_info "Stopping existing containers..."
    pushd "$ANALYZER_DIR" > /dev/null
    docker-compose down 2>/dev/null || true
    
    log_info "Rebuilding with cache (fast rebuild)..."
    echo -e "${GRAY}This uses BuildKit cache mounts for faster rebuilds.${NC}"
    echo -e "${GRAY}Use 'cleanrebuild' for a complete no-cache rebuild.${NC}\n"
    
    if docker-compose build --parallel; then
        log_success "Rebuild completed successfully"
        
        echo -e "\n${YELLOW}Starting rebuilt containers...${NC}"
        docker-compose up -d
        
        log_success "Containers started"
    else
        log_error "Rebuild failed"
        popd > /dev/null
        return 1
    fi
    
    popd > /dev/null
    return 0
}

invoke_clean_rebuild() {
    write_banner "⚠️  Clean Rebuild - Complete Cache Wipe" "$YELLOW"
    
    echo -e "${YELLOW}This will:${NC}"
    echo -e "  ${YELLOW}• Remove all Docker images and volumes${NC}"
    echo -e "  ${YELLOW}• Clear BuildKit cache${NC}"
    echo -e "  ${YELLOW}• Force complete rebuild from scratch${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Use this only if experiencing build issues!${NC}"
    echo -e "    ${GRAY}Normal rebuilds are much faster with caching.${NC}"
    echo ""
    echo -ne "${YELLOW}Type 'CLEAN' to confirm (or anything else to cancel): ${NC}"
    read -r confirmation
    
    if [[ "$confirmation" != "CLEAN" ]]; then
        log_info "Clean rebuild cancelled"
        return 0
    fi
    
    pushd "$ANALYZER_DIR" > /dev/null
    
    log_info "Removing containers, images, and volumes..."
    docker-compose down --rmi all --volumes 2>/dev/null || true
    
    log_info "Pruning BuildKit cache..."
    docker builder prune -f 2>/dev/null || true
    
    log_info "Rebuilding from scratch (this may take 12-18 minutes)..."
    if docker-compose build --no-cache --parallel; then
        log_success "Clean rebuild completed"
        
        echo -e "\n${YELLOW}Starting rebuilt containers...${NC}"
        docker-compose up -d
        
        log_success "Containers started"
    else
        log_error "Clean rebuild failed"
        popd > /dev/null
        return 1
    fi
    
    popd > /dev/null
    return 0
}

# ============================================================================
# CLEANUP OPERATIONS
# ============================================================================

invoke_cleanup() {
    write_banner "Cleaning ThesisApp"
    
    # Check if services are running
    local any_running=false
    if check_flask_health_quiet || check_analyzer_health_quiet; then
        any_running=true
    fi
    
    if [[ "$any_running" == "true" ]]; then
        echo -e "${YELLOW}Some services are still running.${NC}"
        echo -ne "${YELLOW}Stop them before cleanup? (Y/N): ${NC}"
        read -r response
        
        if [[ "$response" =~ ^[Yy]$ ]]; then
            stop_all_services
        else
            log_warning "Skipping cleanup of running services"
        fi
    fi
    
    log_info "Removing PID files..."
    rm -f "$RUN_DIR"/*.pid 2>/dev/null || true
    
    log_info "Rotating logs..."
    local rotated=0
    local skipped=0
    
    for logfile in "$LOGS_DIR"/*.log; do
        [[ -f "$logfile" ]] || continue
        
        # Check if file is being used
        if lsof "$logfile" &>/dev/null; then
            ((skipped++))
            continue
        fi
        
        mv "$logfile" "${logfile}.old" 2>/dev/null || true
        ((rotated++))
    done
    
    [[ $rotated -gt 0 ]] && log_success "  Rotated $rotated log files"
    [[ $skipped -gt 0 ]] && log_warning "  Skipped $skipped log files (in use)"
    
    log_success "Cleanup completed"
}

invoke_maintenance() {
    write_banner "🔧 Manual Maintenance Cleanup" "$YELLOW"
    
    echo -e "${CYAN}This will run the maintenance service to clean up:${NC}"
    echo -e "  ${WHITE}• Orphan app records (apps missing from filesystem for >7 days)${NC}"
    echo -e "  ${WHITE}• Orphan tasks (tasks targeting non-existent apps)${NC}"
    echo -e "  ${WHITE}• Stuck tasks (RUNNING for >2 hours, PENDING for >4 hours)${NC}"
    echo -e "  ${WHITE}• Old completed/failed tasks (>30 days old)${NC}"
    echo ""
    echo -e "${YELLOW}NOTE: Apps missing for <7 days will be marked but NOT deleted.${NC}"
    echo -e "${YELLOW}      This gives you time to restore backup/recover files.${NC}"
    echo ""
    echo -ne "${GRAY}Press Enter to continue or Ctrl+C to cancel...${NC}"
    read -r
    
    log_info "Running maintenance cleanup..."
    
    local maintenance_script='
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.factory import create_app
from app.services.maintenance_service import get_maintenance_service

app = create_app()

with app.app_context():
    service = get_maintenance_service()
    if service is None:
        print("ERROR: MaintenanceService not available")
        sys.exit(1)
    
    print("\n=== Running Manual Maintenance Cleanup ===\n")
    service._run_maintenance()
    
    print("\n=== Maintenance Statistics ===")
    stats = service.stats
    print(f"Total runs: {stats[\"runs\"]}")
    print(f"Orphan apps cleaned: {stats[\"orphan_apps_cleaned\"]}")
    print(f"Orphan tasks cleaned: {stats[\"orphan_tasks_cleaned\"]}")
    print(f"Stuck tasks cleaned: {stats[\"stuck_tasks_cleaned\"]}")
    print(f"Old tasks cleaned: {stats[\"old_tasks_cleaned\"]}")
    print(f"Errors: {stats[\"errors\"]}")
    print()
'
    
    local temp_script="$SCRIPT_DIR/temp_maintenance.py"
    echo "$maintenance_script" > "$temp_script"
    
    "$PYTHON_CMD" "$temp_script" || true
    
    rm -f "$temp_script"
    
    echo ""
    echo -e "${GRAY}View detailed logs at: $FLASK_LOG_FILE${NC}"
    echo ""
    
    return 0
}

invoke_wipeout() {
    write_banner "⚠️  WIPEOUT - Reset to Default State" "$RED"
    
    echo -e "${YELLOW}This will:${NC}"
    echo -e "  ${YELLOW}• Stop all running services${NC}"
    echo -e "  ${YELLOW}• Delete the database (src/data/)${NC}"
    echo -e "  ${YELLOW}• Remove all generated apps (generated/)${NC}"
    echo -e "  ${YELLOW}• Remove all analysis results (results/)${NC}"
    echo -e "  ${YELLOW}• Remove all reports (reports/)${NC}"
    echo -e "  ${YELLOW}• Create fresh admin user${NC}"
    echo ""
    echo -e "${RED}⚠️  THIS CANNOT BE UNDONE! ⚠️${NC}"
    echo ""
    echo -ne "${YELLOW}Type 'WIPEOUT' to confirm (or anything else to cancel): ${NC}"
    read -r confirmation
    
    if [[ "$confirmation" != "WIPEOUT" ]]; then
        log_info "Wipeout cancelled"
        return 0
    fi
    
    echo ""
    log_warning "Starting wipeout procedure..."
    
    # 1. Stop all services
    log_info "Stopping all services..."
    stop_all_services
    sleep 2
    
    # 2. Remove database
    local db_dir="$SRC_DIR/data"
    if [[ -d "$db_dir" ]]; then
        log_info "Removing database..."
        rm -rf "$db_dir"
        log_success "  Database removed"
    fi
    
    # 3. Remove generated apps
    local generated_dir="$SCRIPT_DIR/generated"
    if [[ -d "$generated_dir" ]]; then
        log_info "Removing generated apps..."
        rm -rf "$generated_dir"
        mkdir -p "$generated_dir"
        log_success "  Generated apps removed"
    fi
    
    # 4. Remove results
    local results_dir="$SCRIPT_DIR/results"
    if [[ -d "$results_dir" ]]; then
        log_info "Removing results..."
        rm -rf "$results_dir"
        mkdir -p "$results_dir"
        log_success "  Results removed"
    fi
    
    # 5. Remove reports
    local reports_dir="$SCRIPT_DIR/reports"
    if [[ -d "$reports_dir" ]]; then
        log_info "Removing reports..."
        rm -rf "$reports_dir"
        mkdir -p "$reports_dir"
        log_success "  Reports removed"
    fi
    
    # 6. Remove logs
    log_info "Removing logs..."
    rm -f "$LOGS_DIR"/*.log "$LOGS_DIR"/*.log.old 2>/dev/null || true
    
    # 7. Remove PID files
    log_info "Removing PID files..."
    rm -f "$RUN_DIR"/*.pid 2>/dev/null || true
    
    # 8. Recreate database and admin user
    log_info "Initializing fresh database..."
    local create_admin_script="$SCRIPT_DIR/scripts/create_admin.py"
    
    if [[ -f "$create_admin_script" ]]; then
        "$PYTHON_CMD" "$create_admin_script" || true
    else
        log_warning "  create_admin.py not found, skipping admin creation"
    fi
    
    echo ""
    write_banner "✅ Wipeout Complete - System Reset" "$GREEN"
    echo -e "${CYAN}Default credentials:${NC}"
    echo -e "  ${WHITE}Username: admin${NC}"
    echo -e "  ${WHITE}Password: ia5aeQE2wR87J8w${NC}"
    echo -e "  ${WHITE}Email: admin@thesis.local${NC}"
    echo ""
    log_info "You can now start the application with './start.sh start'"
    
    return 0
}

invoke_reset_password() {
    write_banner "Reset Admin Password"
    
    echo ""
    echo -e "${YELLOW}This will reset the admin user password to a new random value.${NC}"
    echo -e "${YELLOW}The new password will be displayed on screen.${NC}"
    echo ""
    echo -ne "${YELLOW}Continue? (Y/N): ${NC}"
    read -r response
    
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Password reset cancelled"
        return 0
    fi
    
    # Generate random password (16 characters)
    local new_password
    new_password=$(tr -dc 'a-zA-Z0-9!@#$%^&*' < /dev/urandom | head -c 16)
    
    # Create Python script to reset password
    local reset_script="
import sys
from pathlib import Path

# Add src directory to path
SCRIPT_DIR = Path('$SCRIPT_DIR')
SRC_DIR = SCRIPT_DIR / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.models import User
from app.extensions import db

def main():
    app = create_app()
    
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if admin:
            admin.set_password('$new_password')
            db.session.commit()
            print('Password reset successfully!')
            print()
            print('New credentials:')
            print('  Username: admin')
            print('  Password: $new_password')
        else:
            print('ERROR: Admin user not found')
            sys.exit(1)

if __name__ == '__main__':
    main()
"
    
    local temp_script="$SCRIPT_DIR/temp_reset_password.py"
    echo "$reset_script" > "$temp_script"
    
    "$PYTHON_CMD" "$temp_script" || {
        log_error "Error resetting password"
        rm -f "$temp_script"
        return 1
    }
    
    rm -f "$temp_script"
    return 0
}

invoke_reload() {
    write_banner "🔄 Reloading ThesisApp" "$YELLOW"
    
    log_info "Quick reload for live code changes..."
    echo -e "  ${GRAY}This will stop and restart all services${NC}"
    echo ""
    
    # Stop all services
    log_info "Stopping services..."
    stop_all_services
    
    # Brief pause to ensure clean shutdown
    sleep 2
    
    # Start services again
    log_info "Restarting services..."
    BACKGROUND=true
    
    if start_full_stack; then
        write_banner "🔄 Reload Complete" "$GREEN"
        echo -e "${CYAN}Services restarted with latest code changes.${NC}"
        echo ""
        return 0
    else
        log_error "Reload failed"
        return 1
    fi
}

# ============================================================================
# HELP
# ============================================================================

show_help() {
    write_banner "ThesisApp Orchestrator - Help"
    
    echo -e "${CYAN}USAGE:${NC}"
    echo -e "  ${WHITE}./start.sh [MODE] [OPTIONS]${NC}\n"
    
    echo -e "${CYAN}MODES:${NC}"
    echo -e "  ${WHITE}interactive   ${NC}Launch interactive menu (default)"
    echo -e "  ${WHITE}start         ${NC}Start full stack (Flask + Analyzers)"
    echo -e "  ${WHITE}dev           ${NC}Developer mode (Flask with debug enabled)"
    echo -e "  ${WHITE}reload        ${NC}Quick reload - stop and restart all services"
    echo -e "  ${WHITE}stop          ${NC}Stop all services gracefully"
    echo -e "  ${WHITE}status        ${NC}Show service status (one-time check)"
    echo -e "  ${WHITE}health        ${NC}Continuous health monitoring (auto-refresh)"
    echo -e "  ${WHITE}logs          ${NC}View aggregated logs from all services"
    echo -e "  ${WHITE}rebuild       ${NC}Rebuild containers (fast, with cache)"
    echo -e "  ${WHITE}cleanrebuild  ${NC}⚠️  Force rebuild from scratch (no cache)"
    echo -e "  ${WHITE}maintenance   ${NC}Run manual database cleanup"
    echo -e "  ${WHITE}clean         ${NC}Clean logs and PID files"
    echo -e "  ${WHITE}wipeout       ${NC}⚠️  Reset to default state (removes all data)"
    echo -e "  ${WHITE}password      ${NC}Reset admin password to random value"
    echo -e "  ${WHITE}help          ${NC}Show this help message\n"
    
    echo -e "${CYAN}OPTIONS:${NC}"
    echo -e "  ${WHITE}--no-analyzer ${NC}Skip analyzer microservices (faster startup)"
    echo -e "  ${WHITE}--no-follow   ${NC}Disable auto-follow for logs (show snapshot only)"
    echo -e "  ${WHITE}--background  ${NC}Run services in background"
    echo -e "  ${WHITE}--port <n>    ${NC}Flask application port (default: 5000)"
    echo -e "  ${WHITE}--help, -h    ${NC}Show this help message\n"
    
    echo -e "${CYAN}STARTUP SEQUENCE:${NC}"
    echo -e "  ${GRAY}1. Analyzers   (Optional - 4 microservices on ports 2001-2004)${NC}"
    echo -e "  ${GRAY}2. Flask       (Required - web app on port 5000)${NC}\n"
    
    echo -e "${CYAN}EXAMPLES:${NC}"
    echo -e "  ${YELLOW}./start.sh${NC}"
    echo -e "    ${GRAY}→ Interactive menu for easy navigation${NC}\n"
    
    echo -e "  ${YELLOW}./start.sh start --background${NC}"
    echo -e "    ${GRAY}→ Start full stack in background${NC}\n"
    
    echo -e "  ${YELLOW}./start.sh dev --no-analyzer${NC}"
    echo -e "    ${GRAY}→ Quick dev mode without analyzer containers${NC}\n"
    
    echo -e "  ${YELLOW}./start.sh reload${NC}"
    echo -e "    ${GRAY}→ Quick reload for live code changes${NC}\n"
    
    echo -e "  ${YELLOW}./start.sh logs${NC}"
    echo -e "    ${GRAY}→ View live logs with auto-follow${NC}\n"
    
    echo -e "  ${YELLOW}./start.sh logs --no-follow${NC}"
    echo -e "    ${GRAY}→ View log snapshot (last 50 lines per service)${NC}\n"
    
    echo -e "${CYAN}SERVICE URLS:${NC}"
    echo -e "  ${GRAY}Flask App:           http://127.0.0.1:5000${NC}"
    echo -e "  ${GRAY}Static Analyzer:     ws://localhost:2001${NC}"
    echo -e "  ${GRAY}Dynamic Analyzer:    ws://localhost:2002${NC}"
    echo -e "  ${GRAY}Performance Tester:  ws://localhost:2003${NC}"
    echo -e "  ${GRAY}AI Analyzer:         ws://localhost:2004${NC}"
    echo -e "  ${GRAY}WebSocket Gateway:   ws://localhost:8765${NC}\n"
    
    echo -e "${CYAN}LOG FILES:${NC}"
    echo -e "  ${GRAY}Flask:     $FLASK_LOG_FILE${NC}"
    echo -e "  ${GRAY}Analyzers: $ANALYZER_LOG_FILE${NC}\n"
    
    echo -e "${CYAN}DEPENDENCIES:${NC}"
    echo -e "  ${GRAY}• Python 3.8+ (virtual environment preferred: .venv)${NC}"
    echo -e "  ${GRAY}• Docker (user must be in docker group or use sudo)${NC}"
    echo -e "  ${GRAY}• Bash 4.0+${NC}"
    echo ""
}

# ============================================================================
# INTERACTIVE MENU
# ============================================================================

show_interactive_menu() {
    while true; do
        clear
        write_banner "ThesisApp Orchestrator"
        
        echo -e "${CYAN}Select an option:${NC}"
        echo ""
        echo -e "  ${WHITE}[S]${NC} Start        - Start full stack (Flask + Analyzers)"
        echo -e "  ${WHITE}[D]${NC} Dev          - Developer mode (Flask, debug on)"
        echo -e "  ${WHITE}[O]${NC} Reload       - 🔄 Quick reload (Stop → Start)"
        echo -e "  ${WHITE}[R]${NC} Rebuild      - Rebuild containers (fast, with cache)"
        echo -e "  ${WHITE}[F]${NC} CleanRebuild - ⚠️  Force rebuild (no cache, slow)"
        echo -e "  ${WHITE}[L]${NC} Logs         - View aggregated logs"
        echo -e "  ${WHITE}[M]${NC} Monitor      - Live status monitoring"
        echo -e "  ${WHITE}[H]${NC} Health       - Check service health"
        echo -e "  ${WHITE}[X]${NC} Stop         - Stop all services"
        echo -e "  ${WHITE}[C]${NC} Clean        - Clean logs and PID files"
        echo -e "  ${WHITE}[W]${NC} Wipeout      - ⚠️  Reset to default state"
        echo -e "  ${WHITE}[P]${NC} Password     - Reset admin password"
        echo -e "  ${WHITE}[T]${NC} Maintenance  - Run database cleanup"
        echo -e "  ${WHITE}[?]${NC} Help         - Show detailed help"
        echo -e "  ${WHITE}[Q]${NC} Quit         - Exit"
        echo ""
        
        echo -ne "Enter choice: "
        read -r choice
        
        case "${choice^^}" in
            S)
                BACKGROUND=true
                start_full_stack
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            D)
                start_dev_mode
                ;;
            O)
                invoke_reload
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            R)
                invoke_rebuild
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            F)
                invoke_clean_rebuild
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            L)
                show_logs
                ;;
            M)
                show_status_dashboard true
                ;;
            H)
                show_status_dashboard false
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            X)
                stop_all_services
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            C)
                invoke_cleanup
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            W)
                invoke_wipeout
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            P)
                invoke_reset_password
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            T)
                invoke_maintenance
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            "?")
                show_help
                echo -ne "\n${GRAY}Press Enter to continue...${NC}"
                read -r
                ;;
            Q)
                log_info "Goodbye!"
                exit 0
                ;;
            *)
                log_warning "Invalid choice: $choice"
                sleep 1
                ;;
        esac
    done
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

parse_arguments() {
    local mode="interactive"
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --no-analyzer)
                NO_ANALYZER=true
                shift
                ;;
            --no-follow)
                NO_FOLLOW=true
                shift
                ;;
            --background)
                BACKGROUND=true
                shift
                ;;
            --port)
                FLASK_PORT="$2"
                shift 2
                ;;
            --help|-h)
                mode="help"
                shift
                ;;
            interactive|start|dev|stop|status|health|logs|rebuild|cleanrebuild|clean|wipeout|password|maintenance|reload|help)
                mode="$1"
                shift
                ;;
            *)
                log_error "Unknown argument: $1"
                echo "Use './start.sh --help' for usage information."
                exit 1
                ;;
        esac
    done
    
    echo "$mode"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    # Parse arguments
    local mode
    mode=$(parse_arguments "$@")
    
    # Initialize environment
    initialize_environment
    
    # Check dependencies (except for help)
    if [[ "$mode" != "help" ]]; then
        if ! check_dependencies; then
            exit 1
        fi
    fi
    
    # Execute based on mode
    case "$mode" in
        interactive)
            show_interactive_menu
            ;;
        start)
            BACKGROUND=true
            start_full_stack
            ;;
        dev)
            start_dev_mode
            ;;
        stop)
            stop_all_services
            ;;
        status)
            show_status_dashboard false
            ;;
        health)
            show_status_dashboard true
            ;;
        logs)
            show_logs
            ;;
        rebuild)
            invoke_rebuild
            ;;
        cleanrebuild)
            invoke_clean_rebuild
            ;;
        clean)
            invoke_cleanup
            ;;
        wipeout)
            invoke_wipeout
            ;;
        password)
            invoke_reset_password
            ;;
        maintenance)
            invoke_maintenance
            ;;
        reload)
            invoke_reload
            ;;
        help)
            show_help
            ;;
        *)
            log_error "Unknown mode: $mode"
            show_help
            exit 1
            ;;
    esac
}

# Run main with all arguments
main "$@"
