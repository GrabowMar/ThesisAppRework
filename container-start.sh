#!/bin/bash
# =============================================================================
# Container Management Script for ThesisAppRework
# =============================================================================
# This script mirrors start.ps1 functionality for use inside Docker containers.
# Run via: docker exec -it thesisapprework-web-1 /app/start.sh [command]
#
# Usage:
#   /app/start.sh              # Interactive menu
#   /app/start.sh status       # Show status dashboard
#   /app/start.sh health       # Health check all services
#   /app/start.sh logs [N]     # Show last N lines of logs
#   /app/start.sh db           # Database info
#   /app/start.sh tasks        # Task status
#   /app/start.sh maintenance  # Run maintenance cleanup
#   /app/start.sh fix-tasks    # Fix stuck tasks
#   /app/start.sh password     # Reset admin password
#   /app/start.sh wipeout      # Full system reset (DANGER!)
#   /app/start.sh cleanup      # Clean logs and temp files
#   /app/start.sh help         # Show this help
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color
BOLD='\033[1m'
DIM='\033[2m'

# Icons
CHECK="✓"
CROSS="✗"
WARN="⚠"
INFO="ℹ"
ARROW="→"

# Service URLs
FLASK_URL="http://localhost:5000"
REDIS_HOST="redis"
REDIS_PORT=6379

ANALYZER_SERVICES=(
    "static-analyzer:2001"
    "dynamic-analyzer:2002"
    "performance-tester:2003"
    "ai-analyzer:2004"
)

# =============================================================================
# Utility Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC} ${BOLD}${WHITE}$1${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${WHITE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}${CHECK}${NC} $1"
}

print_error() {
    echo -e "${RED}${CROSS}${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}${WARN}${NC} $1"
}

print_info() {
    echo -e "${BLUE}${INFO}${NC} $1"
}

print_item() {
    echo -e "  ${DIM}${ARROW}${NC} $1"
}

# Check if a service is reachable via HTTP
check_http_service() {
    local url=$1
    local timeout=${2:-5}
    if curl -s --connect-timeout $timeout --max-time $timeout "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check if a TCP port is open
check_tcp_port() {
    local host=$1
    local port=$2
    local timeout=${3:-2}
    if timeout $timeout bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# =============================================================================
# Status Dashboard
# =============================================================================

show_status() {
    print_header "ThesisAppRework - Status Dashboard"
    
    # Flask App Status
    print_section "Flask Application"
    if check_http_service "${FLASK_URL}/api/health" 3; then
        print_success "Flask app is ${GREEN}RUNNING${NC} on port 5000"
        
        # Get health details
        local health_response=$(curl -s --max-time 5 "${FLASK_URL}/api/health" 2>/dev/null || echo "{}")
        local status=$(echo "$health_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
        print_item "Health status: ${BOLD}$status${NC}"
    else
        print_error "Flask app is ${RED}NOT RESPONDING${NC}"
    fi
    
    # Redis Status
    print_section "Redis"
    if check_tcp_port "$REDIS_HOST" "$REDIS_PORT" 2; then
        print_success "Redis is ${GREEN}CONNECTED${NC} at ${REDIS_HOST}:${REDIS_PORT}"
    else
        print_error "Redis is ${RED}NOT REACHABLE${NC}"
    fi
    
    # Celery Status
    print_section "Celery Workers"
    if command -v celery &> /dev/null; then
        local celery_status=$(celery -A app.celery_worker inspect ping 2>/dev/null | head -5 || echo "No workers")
        if echo "$celery_status" | grep -q "pong"; then
            print_success "Celery workers are ${GREEN}ACTIVE${NC}"
        else
            print_warning "Celery workers status: ${YELLOW}Unknown${NC}"
        fi
    else
        print_item "Celery command not in path"
    fi
    
    # Analyzer Services
    print_section "Analyzer Services"
    for service in "${ANALYZER_SERVICES[@]}"; do
        local name="${service%%:*}"
        local port="${service##*:}"
        local health_url="http://${name}:${port}/health"
        
        if check_http_service "$health_url" 3; then
            print_success "${name} is ${GREEN}HEALTHY${NC} on port ${port}"
        else
            print_error "${name} is ${RED}NOT RESPONDING${NC} on port ${port}"
        fi
    done
    
    # Database Status
    print_section "Database"
    local db_path="/app/src/data/thesis_app.db"
    if [ -f "$db_path" ]; then
        local db_size=$(du -h "$db_path" 2>/dev/null | cut -f1 || echo "unknown")
        print_success "Database exists: ${BOLD}$db_size${NC}"
    else
        print_warning "Database file not found"
    fi
    
    # Disk Usage
    print_section "Disk Usage"
    local disk_usage=$(df -h /app 2>/dev/null | tail -1 | awk '{print $5 " used of " $2}' || echo "unknown")
    print_item "App volume: ${BOLD}$disk_usage${NC}"
    
    local generated_count=$(find /app/generated/apps -maxdepth 2 -type d 2>/dev/null | wc -l || echo "0")
    print_item "Generated apps: ${BOLD}$generated_count${NC} directories"
    
    local results_count=$(find /app/results -maxdepth 3 -name "*.json" 2>/dev/null | wc -l || echo "0")
    print_item "Result files: ${BOLD}$results_count${NC} JSON files"
    
    echo ""
}

# =============================================================================
# Health Check
# =============================================================================

show_health() {
    print_header "ThesisAppRework - Health Check"
    
    local all_healthy=true
    
    # Flask Health
    print_section "Core Services"
    
    echo -n "  Checking Flask API... "
    if check_http_service "${FLASK_URL}/api/health" 5; then
        echo -e "${GREEN}${CHECK} HEALTHY${NC}"
    else
        echo -e "${RED}${CROSS} UNHEALTHY${NC}"
        all_healthy=false
    fi
    
    echo -n "  Checking Redis... "
    if check_tcp_port "$REDIS_HOST" "$REDIS_PORT" 3; then
        echo -e "${GREEN}${CHECK} CONNECTED${NC}"
    else
        echo -e "${RED}${CROSS} DISCONNECTED${NC}"
        all_healthy=false
    fi
    
    # Analyzer Services Health
    print_section "Analyzer Services"
    
    for service in "${ANALYZER_SERVICES[@]}"; do
        local name="${service%%:*}"
        local port="${service##*:}"
        local health_url="http://${name}:${port}/health"
        
        echo -n "  Checking ${name}:${port}... "
        
        if check_http_service "$health_url" 5; then
            echo -e "${GREEN}${CHECK} HEALTHY${NC}"
        else
            echo -e "${RED}${CROSS} UNHEALTHY${NC}"
            all_healthy=false
        fi
    done
    
    # Summary
    print_section "Summary"
    if $all_healthy; then
        print_success "All services are ${GREEN}HEALTHY${NC}"
    else
        print_error "Some services are ${RED}UNHEALTHY${NC}"
    fi
    
    echo ""
}

# =============================================================================
# Logs Viewer
# =============================================================================

show_logs() {
    local lines=${1:-50}
    print_header "Application Logs (last $lines lines)"
    
    local log_file="/app/logs/app.log"
    if [ -f "$log_file" ]; then
        echo ""
        tail -n "$lines" "$log_file"
    else
        print_warning "Log file not found at $log_file"
    fi
    echo ""
}

follow_logs() {
    print_header "Following Application Logs (Ctrl+C to stop)"
    
    local log_file="/app/logs/app.log"
    if [ -f "$log_file" ]; then
        echo ""
        tail -f "$log_file"
    else
        print_warning "Log file not found at $log_file"
    fi
}

# =============================================================================
# Database Info
# =============================================================================

show_db_info() {
    print_header "Database Information"
    
    cd /app
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app/src')
sys.path.insert(0, '/app')

try:
    from app.factory import create_app
    from app.models import GeneratedApplication, AnalysisTask, User
    from app.constants import AnalysisStatus
    
    app = create_app()
    with app.app_context():
        # User stats
        users = User.query.count()
        print(f"\n  Users: {users}")
        
        # Application stats
        total_apps = GeneratedApplication.query.count()
        print(f"  Generated Applications: {total_apps}")
        
        # Task stats
        total_tasks = AnalysisTask.query.count()
        pending = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
        running = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).count()
        completed = AnalysisTask.query.filter_by(status=AnalysisStatus.COMPLETED).count()
        failed = AnalysisTask.query.filter_by(status=AnalysisStatus.FAILED).count()
        
        print(f"\n  Analysis Tasks:")
        print(f"    Total:     {total_tasks}")
        print(f"    Pending:   {pending}")
        print(f"    Running:   {running}")
        print(f"    Completed: {completed}")
        print(f"    Failed:    {failed}")
        
        # Recent tasks
        recent = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(5).all()
        if recent:
            print(f"\n  Recent Tasks:")
            for task in recent:
                status_str = task.status.value if task.status else 'unknown'
                print(f"    - {task.task_id}: {status_str} ({task.target_model})")
                
except Exception as e:
    print(f"  Error: {e}")
PYEOF
    echo ""
}

# =============================================================================
# Task Management
# =============================================================================

show_tasks() {
    print_header "Task Status Overview"
    
    cd /app
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app/src')
sys.path.insert(0, '/app')

try:
    from app.factory import create_app
    from app.models import AnalysisTask
    from app.constants import AnalysisStatus
    from datetime import datetime, timezone
    
    app = create_app()
    with app.app_context():
        # Status summary
        statuses = {}
        for status in AnalysisStatus:
            count = AnalysisTask.query.filter_by(status=status).count()
            if count > 0:
                statuses[status.value] = count
        
        print("\n  Task Status Summary:")
        for status, count in sorted(statuses.items()):
            icon = "✓" if status == "COMPLETED" else ("⏳" if status in ["PENDING", "RUNNING"] else "✗")
            print(f"    {icon} {status}: {count}")
        
        # Running tasks
        running = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
        if running:
            print(f"\n  Currently Running ({len(running)}):")
            for task in running[:10]:
                duration = ""
                if task.started_at:
                    started = task.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                    duration = f" ({int(elapsed)}s)"
                print(f"    → {task.task_id}{duration}")
        
        # Pending tasks
        pending = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).limit(10).all()
        if pending:
            print(f"\n  Pending Tasks (showing up to 10):")
            for task in pending:
                print(f"    → {task.task_id} ({task.target_model})")
        
        # Recent failures
        failed = AnalysisTask.query.filter_by(status=AnalysisStatus.FAILED).order_by(
            AnalysisTask.completed_at.desc()
        ).limit(5).all()
        if failed:
            print(f"\n  Recent Failures:")
            for task in failed:
                error = (task.error_message or "No error message")[:60]
                print(f"    ✗ {task.task_id}: {error}")
                
except Exception as e:
    print(f"  Error: {e}")
PYEOF
    echo ""
}

fix_tasks() {
    print_header "Fixing Stuck Tasks"
    
    cd /app
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app/src')
sys.path.insert(0, '/app')

try:
    from app.factory import create_app
    from app.models import AnalysisTask
    from app.constants import AnalysisStatus
    from app.extensions import db
    from datetime import datetime, timezone, timedelta
    
    app = create_app()
    with app.app_context():
        fixed_count = 0
        
        # Fix tasks stuck in RUNNING for > 2 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        stuck_running = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.RUNNING,
            AnalysisTask.started_at < cutoff
        ).all()
        
        for task in stuck_running:
            task.status = AnalysisStatus.FAILED
            task.error_message = "Task stuck in RUNNING state - marked as failed by maintenance"
            task.completed_at = datetime.now(timezone.utc)
            fixed_count += 1
            print(f"  ✗ Marked stuck task as FAILED: {task.task_id}")
        
        # Fix tasks stuck in PENDING for > 4 hours
        pending_cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
        stuck_pending = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.PENDING,
            AnalysisTask.created_at < pending_cutoff
        ).all()
        
        for task in stuck_pending:
            task.status = AnalysisStatus.CANCELLED
            task.error_message = "Task stuck in PENDING state - cancelled by maintenance"
            task.completed_at = datetime.now(timezone.utc)
            fixed_count += 1
            print(f"  ✗ Cancelled stuck task: {task.task_id}")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n  ✓ Fixed {fixed_count} stuck task(s)")
        else:
            print("\n  ✓ No stuck tasks found")
            
except Exception as e:
    print(f"  Error: {e}")
PYEOF
    echo ""
}

# =============================================================================
# Maintenance
# =============================================================================

run_maintenance() {
    print_header "Running Maintenance Cleanup"
    
    cd /app
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app/src')
sys.path.insert(0, '/app')

try:
    from app.factory import create_app
    from app.services.maintenance_service import get_maintenance_service
    
    app = create_app()
    with app.app_context():
        maintenance = get_maintenance_service()
        if maintenance:
            print("\n  Running maintenance tasks...")
            maintenance._run_maintenance()
            print("\n  ✓ Maintenance completed")
        else:
            print("\n  ⚠ Maintenance service not available")
            
except Exception as e:
    print(f"\n  Error: {e}")
PYEOF
    echo ""
}

# =============================================================================
# Password Reset
# =============================================================================

reset_password() {
    print_header "Admin Password Reset"
    
    cd /app
    python3 << 'PYEOF'
import sys
import secrets
import string
sys.path.insert(0, '/app/src')
sys.path.insert(0, '/app')

try:
    from app.factory import create_app
    from app.models import User
    from app.extensions import db
    
    # Generate secure password
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if admin:
            admin.set_password(new_password)
            db.session.commit()
            print(f"\n  ✓ Admin password has been reset")
            print(f"")
            print(f"  New Admin Credentials")
            print(f"  ─────────────────────")
            print(f"  Username: admin")
            print(f"  Password: {new_password}")
            print(f"")
            print(f"  ⚠ Save this password - it won't be shown again!")
        else:
            # Create admin user if doesn't exist
            admin = User(
                username='admin',
                email='admin@localhost'
            )
            admin.set_password(new_password)
            admin.is_admin = True
            db.session.add(admin)
            db.session.commit()
            print(f"\n  ✓ Admin user created")
            print(f"")
            print(f"  New Admin Credentials")
            print(f"  ─────────────────────")
            print(f"  Username: admin")
            print(f"  Password: {new_password}")
            print(f"")
            print(f"  ⚠ Save this password - it won't be shown again!")
            
except Exception as e:
    print(f"\n  Error: {e}")
PYEOF
    echo ""
}

# =============================================================================
# Wipeout (Full Reset)
# =============================================================================

invoke_wipeout() {
    print_header "SYSTEM WIPEOUT"
    
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ${BOLD}WARNING: THIS WILL DELETE ALL DATA!${NC}${RED}                            ║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║  This operation will:                                            ║${NC}"
    echo -e "${RED}║  • Delete the database (thesis_app.db)                           ║${NC}"
    echo -e "${RED}║  • Remove all generated applications                             ║${NC}"
    echo -e "${RED}║  • Delete all analysis results                                   ║${NC}"
    echo -e "${RED}║  • Clear all reports                                             ║${NC}"
    echo -e "${RED}║  • Reinitialize database with fresh schema                       ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    read -p "Type 'YES I UNDERSTAND' to proceed: " confirmation
    
    if [ "$confirmation" != "YES I UNDERSTAND" ]; then
        print_info "Wipeout cancelled"
        return
    fi
    
    echo ""
    print_warning "Starting wipeout in 3 seconds... (Ctrl+C to cancel)"
    sleep 3
    
    echo ""
    print_info "Stopping background services..."
    
    # Remove database
    print_info "Removing database..."
    rm -f /app/src/data/thesis_app.db 2>/dev/null || true
    rm -f /app/src/data/*.db-journal 2>/dev/null || true
    
    # Clear generated apps
    print_info "Clearing generated applications..."
    rm -rf /app/generated/apps/* 2>/dev/null || true
    
    # Clear results
    print_info "Clearing analysis results..."
    rm -rf /app/results/* 2>/dev/null || true
    
    # Clear reports
    print_info "Clearing reports..."
    rm -rf /app/reports/* 2>/dev/null || true
    
    # Clear logs
    print_info "Clearing logs..."
    rm -f /app/logs/*.log 2>/dev/null || true
    
    # Reinitialize database
    print_info "Reinitializing database..."
    cd /app
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app/src')
sys.path.insert(0, '/app')

try:
    from app.factory import create_app
    from app.extensions import db
    from app.models import User
    import secrets
    import string
    
    app = create_app()
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create default admin user
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(16))
        
        admin = User(
            username='admin',
            email='admin@localhost'
        )
        admin.set_password(password)
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()
        
        print(f"\n  ✓ Database reinitialized")
        print(f"")
        print(f"  New Admin Credentials")
        print(f"  ─────────────────────")
        print(f"  Username: admin")
        print(f"  Password: {password}")
        print(f"")
        print(f"  ⚠ Save this password!")
        
except Exception as e:
    print(f"\n  Error reinitializing database: {e}")
PYEOF
    
    echo ""
    print_success "Wipeout completed!"
    print_warning "Container restart recommended: docker restart thesisapprework-web-1"
    echo ""
}

# =============================================================================
# Cleanup
# =============================================================================

invoke_cleanup() {
    print_header "System Cleanup"
    
    local freed_space=0
    
    # Rotate logs
    print_section "Log Rotation"
    local log_dir="/app/logs"
    if [ -d "$log_dir" ]; then
        local log_count=$(find "$log_dir" -name "*.log" -size +10M 2>/dev/null | wc -l)
        if [ "$log_count" -gt 0 ]; then
            find "$log_dir" -name "*.log" -size +10M -exec sh -c 'mv "$1" "$1.old" && : > "$1"' _ {} \;
            print_success "Rotated $log_count large log file(s)"
        else
            print_info "No large log files to rotate"
        fi
        
        # Remove old rotated logs
        local old_count=$(find "$log_dir" -name "*.old" -mtime +7 2>/dev/null | wc -l)
        if [ "$old_count" -gt 0 ]; then
            find "$log_dir" -name "*.old" -mtime +7 -delete
            print_success "Removed $old_count old rotated log(s)"
        fi
    fi
    
    # Clean Python cache
    print_section "Python Cache"
    local pycache_count=$(find /app -type d -name "__pycache__" 2>/dev/null | wc -l)
    if [ "$pycache_count" -gt 0 ]; then
        find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        print_success "Cleaned $pycache_count __pycache__ directories"
    else
        print_info "No __pycache__ directories found"
    fi
    
    # Clean .pyc files
    local pyc_count=$(find /app -name "*.pyc" 2>/dev/null | wc -l)
    if [ "$pyc_count" -gt 0 ]; then
        find /app -name "*.pyc" -delete 2>/dev/null || true
        print_success "Removed $pyc_count .pyc files"
    fi
    
    # Clean temp files
    print_section "Temporary Files"
    rm -rf /tmp/thesis_* 2>/dev/null || true
    rm -rf /app/tmp/* 2>/dev/null || true
    print_success "Cleaned temporary directories"
    
    # Show disk usage after cleanup
    print_section "Disk Usage After Cleanup"
    local disk_usage=$(df -h /app 2>/dev/null | tail -1 | awk '{print $5 " used of " $2 " (available: " $4 ")"}')
    print_info "App volume: $disk_usage"
    
    echo ""
}

# =============================================================================
# Help
# =============================================================================

show_help() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC} ${BOLD}${WHITE}ThesisAppRework Container Management Script${NC}                      ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo -e "  ${GREEN}/app/start.sh${NC} [command] [options]"
    echo ""
    echo -e "${BOLD}Commands:${NC}"
    echo ""
    echo -e "  ${CYAN}Information:${NC}"
    echo -e "    ${GREEN}status${NC}          Show comprehensive status dashboard"
    echo -e "    ${GREEN}health${NC}          Check health of all services"
    echo -e "    ${GREEN}logs${NC} [N]        Show last N lines of application log (default: 50)"
    echo -e "    ${GREEN}logs-follow${NC}     Follow application logs in real-time"
    echo -e "    ${GREEN}db${NC}              Show database statistics"
    echo ""
    echo -e "  ${CYAN}Task Management:${NC}"
    echo -e "    ${GREEN}tasks${NC}           Show task status overview"
    echo -e "    ${GREEN}fix-tasks${NC}       Fix stuck tasks (RUNNING>2h, PENDING>4h)"
    echo ""
    echo -e "  ${CYAN}Maintenance:${NC}"
    echo -e "    ${GREEN}maintenance${NC}     Run maintenance cleanup service"
    echo -e "    ${GREEN}cleanup${NC}         Clean logs, cache, and temp files"
    echo ""
    echo -e "  ${CYAN}Administration:${NC}"
    echo -e "    ${GREEN}password${NC}        Reset admin password"
    echo -e "    ${GREEN}wipeout${NC}         ${RED}[DANGER]${NC} Full system reset - deletes all data"
    echo ""
    echo -e "  ${CYAN}Interactive:${NC}"
    echo -e "    ${GREEN}menu${NC}            Show interactive menu"
    echo -e "    ${GREEN}help${NC}            Show this help message"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  ${DIM}# Check system health${NC}"
    echo -e "  docker exec -it thesisapprework-web-1 /app/start.sh health"
    echo ""
    echo -e "  ${DIM}# View last 100 log lines${NC}"
    echo -e "  docker exec -it thesisapprework-web-1 /app/start.sh logs 100"
    echo ""
    echo -e "  ${DIM}# Interactive mode${NC}"
    echo -e "  docker exec -it thesisapprework-web-1 /app/start.sh"
    echo ""
}

# =============================================================================
# Interactive Menu
# =============================================================================

show_interactive_menu() {
    while true; do
        clear
        echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║${NC}        ${BOLD}${WHITE}ThesisAppRework - Container Management${NC}                   ${CYAN}║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "  ${BOLD}Information${NC}"
        echo -e "    ${GREEN}1)${NC} Status Dashboard"
        echo -e "    ${GREEN}2)${NC} Health Check"
        echo -e "    ${GREEN}3)${NC} View Logs"
        echo -e "    ${GREEN}4)${NC} Follow Logs (live)"
        echo -e "    ${GREEN}5)${NC} Database Info"
        echo ""
        echo -e "  ${BOLD}Task Management${NC}"
        echo -e "    ${GREEN}6)${NC} Task Status"
        echo -e "    ${GREEN}7)${NC} Fix Stuck Tasks"
        echo ""
        echo -e "  ${BOLD}Maintenance${NC}"
        echo -e "    ${GREEN}8)${NC} Run Maintenance"
        echo -e "    ${GREEN}9)${NC} Cleanup (logs/cache)"
        echo ""
        echo -e "  ${BOLD}Administration${NC}"
        echo -e "    ${YELLOW}p)${NC} Reset Admin Password"
        echo -e "    ${RED}w)${NC} Wipeout (DANGER!)"
        echo ""
        echo -e "    ${DIM}h)${NC} Help"
        echo -e "    ${DIM}q)${NC} Quit"
        echo ""
        echo -n "  Select option: "
        
        read -r choice
        
        case $choice in
            1) show_status; read -p "Press Enter to continue..." ;;
            2) show_health; read -p "Press Enter to continue..." ;;
            3) show_logs 50; read -p "Press Enter to continue..." ;;
            4) follow_logs ;;
            5) show_db_info; read -p "Press Enter to continue..." ;;
            6) show_tasks; read -p "Press Enter to continue..." ;;
            7) fix_tasks; read -p "Press Enter to continue..." ;;
            8) run_maintenance; read -p "Press Enter to continue..." ;;
            9) invoke_cleanup; read -p "Press Enter to continue..." ;;
            p|P) reset_password; read -p "Press Enter to continue..." ;;
            w|W) invoke_wipeout; read -p "Press Enter to continue..." ;;
            h|H) show_help; read -p "Press Enter to continue..." ;;
            q|Q) echo ""; exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}"; sleep 1 ;;
        esac
    done
}

# =============================================================================
# Main Entry Point
# =============================================================================

case "${1:-menu}" in
    status)
        show_status
        ;;
    health)
        show_health
        ;;
    logs)
        show_logs "${2:-50}"
        ;;
    logs-follow|follow)
        follow_logs
        ;;
    db|database)
        show_db_info
        ;;
    tasks)
        show_tasks
        ;;
    fix-tasks|fix)
        fix_tasks
        ;;
    maintenance|maint)
        run_maintenance
        ;;
    cleanup|clean)
        invoke_cleanup
        ;;
    password|passwd)
        reset_password
        ;;
    wipeout|reset)
        invoke_wipeout
        ;;
    help|--help|-h)
        show_help
        ;;
    menu|"")
        show_interactive_menu
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
