"""
System status and monitoring API routes
========================================

Endpoints for system health, uptime, resource usage, and status indicators.
"""

import psutil
import subprocess
from flask import Blueprint, request, current_app
from datetime import datetime, timezone

from app.extensions import db
from .common import (
    api_success, api_error, get_system_status, get_uptime_info,
    get_database_health, get_active_tasks_count, render_status_indicator,
    render_tasks_indicator, render_uptime_indicator
)


system_bp = Blueprint('system_api', __name__)


@system_bp.route('/system/health')
def api_system_health():
    """Comprehensive system health status."""
    try:
        # Database health check
        db_healthy, db_error = get_database_health()

        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Check Docker status
        docker_status = {
            'available': False,
            'containers_running': 0,
            'error': None,
        }

        try:
            from app.services.docker_manager import DockerManager
            docker_service = DockerManager()
            client = getattr(docker_service, 'client', None)
            if client:
                containers = client.containers.list()
                docker_status['available'] = True
                docker_status['containers_running'] = len(containers)
        except Exception as e:
            docker_status['error'] = str(e)

        # Determine overall health
        health_status = 'healthy'
        issues = []

        if not db_healthy:
            health_status = 'unhealthy'
            issues.append(f'Database connection failed: {db_error}')

        if cpu_percent > 90:
            health_status = 'warning' if health_status == 'healthy' else health_status
            issues.append(f'High CPU usage: {cpu_percent}%')

        if memory.percent > 90:
            health_status = 'warning' if health_status == 'healthy' else health_status
            issues.append(f'High memory usage: {memory.percent}%')

        if disk.percent > 90:
            health_status = 'warning' if health_status == 'healthy' else health_status
            issues.append(f'High disk usage: {disk.percent}%')

        return api_success({
            'status': health_status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': {
                'healthy': db_healthy,
                'error': db_error
            },
            'docker': docker_status,
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent
            },
            'issues': issues
        })

    except Exception as e:
        current_app.logger.error(f"Error getting system health: {e}")
        return api_error("Failed to retrieve system health", status=500, details={'error': str(e)})


@system_bp.route('/info')
def api_system_info():
    """System information."""
    try:
        system_info = {
            'platform': psutil.Process().memory_info().rss,  # This seems wrong in original, keeping for compatibility
            'cpu_count': psutil.cpu_count(),
            'total_memory': psutil.virtual_memory().total,
            'available_memory': psutil.virtual_memory().available,
            'disk_total': psutil.disk_usage('/').total,
            'disk_free': psutil.disk_usage('/').free,
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }

        current_process = psutil.Process()
        process_info = {
            'pid': current_process.pid,
            'memory_usage': current_process.memory_info().rss,
            'cpu_percent': current_process.cpu_percent(),
            'create_time': datetime.fromtimestamp(current_process.create_time()).isoformat(),
            'num_threads': current_process.num_threads()
        }

        return api_success({
            'system': system_info,
            'process': process_info,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting system info: {e}")
        return api_error("Failed to retrieve system info", details={"reason": str(e)})


@system_bp.route('/overview')
def api_system_overview():
    """System overview with uptime and resource usage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        db_status = 'connected'
        try:
            db.session.execute(db.text('SELECT 1'))
            db.session.commit()
        except Exception:
            db_status = 'disconnected'

        uptime_info = get_uptime_info()

        data = {
            'status': 'online',
            'uptime': uptime_info,
            'resources': {
                'cpu': {
                    'usage_percent': cpu_percent,
                    'cores': psutil.cpu_count()
                },
                'memory': {
                    'usage_percent': memory.percent,
                    'total_gb': round(memory.total / 1024**3, 2),
                    'available_gb': round(memory.available / 1024**3, 2)
                },
                'disk': {
                    'usage_percent': disk.percent,
                    'total_gb': round(disk.total / 1024**3, 2),
                    'free_gb': round(disk.free / 1024**3, 2)
                }
            },
            'services': {
                'database': db_status,
                'api': 'running'
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        return api_success(data)
    except Exception as e:
        current_app.logger.error(f"Error getting system overview: {e}")
        return api_error("Failed to retrieve system overview", details={"reason": str(e)})


@system_bp.route('/footer-status')
def api_system_footer_status():
    """System status for footer display."""
    try:
        status_info = get_system_status()
        
        # Return HTML fragment for HTMX requests
        if request.headers.get('HX-Request'):
            if 'header' in request.headers.get('HX-Target', '').lower() or 'header' in request.path:
                return f'<span class="{status_info["status_class"]} me-1"></span><small class="text-muted">OK</small>'
            else:
                return f'''
                <span class="{status_info["status_class"]} me-2"></span>
                <span class="text-secondary">System OK</span>
                '''

        return api_success(status_info)
    except Exception as e:
        current_app.logger.error(f"Error getting footer status: {e}")
        if request.headers.get('HX-Request'):
            return '<span class="status-indicator status-indicator-animated bg-red me-2"></span><span class="text-secondary">System Error</span>'
        return api_error("Failed to retrieve footer status", details={'error': str(e)})


@system_bp.route('/tasks/count')
def api_tasks_count():
    """Get active tasks count."""
    try:
        tasks_info = get_active_tasks_count()
        
        # Return HTML fragment for HTMX requests
        if request.headers.get('HX-Request'):
            if 'header' in request.headers.get('HX-Target', '').lower() or 'header' in request.path:
                return render_tasks_indicator(tasks_info)
            else:
                total = tasks_info['total_active']
                badge_class = 'bg-blue' if total > 0 else 'bg-secondary'
                return f'Tasks: <span class="badge {badge_class} ms-1">{total}</span>'

        return api_success({
            **tasks_info,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Error getting tasks count: {e}")
        if request.headers.get('HX-Request'):
            return 'Tasks: <span class="badge bg-red ms-1">!</span>'
        return api_error("Failed to retrieve tasks count", details={"total_active": 0})


@system_bp.route('/uptime')
def api_uptime():
    """Get system uptime."""
    try:
        uptime_info = get_uptime_info()
        
        # Return HTML fragment for HTMX requests
        if request.headers.get('HX-Request'):
            if 'header' in request.headers.get('HX-Target', '').lower() or 'header' in request.path:
                return render_uptime_indicator(uptime_info)
            else:
                return f'Uptime: {uptime_info["uptime_formatted"]}'

        return api_success({
            **uptime_info,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Error getting uptime: {e}")
        if request.headers.get('HX-Request'):
            return 'Uptime: --'
        return api_error("Failed to retrieve uptime", details={'uptime_formatted': '--'})


@system_bp.route('/header/summary')
def api_header_summary():
    """Header summary with status, tasks, and uptime for HTMX."""
    try:
        status_info = get_system_status()
        tasks_info = get_active_tasks_count()
        uptime_info = get_uptime_info()

        # Return HTML fragment for HTMX
        return f'''
        {render_status_indicator(status_info)}
        
        <a class="text-muted d-flex align-items-center me-3" href="/tasks" title="Active tasks">
          {render_tasks_indicator(tasks_info)}
        </a>

        <div class="text-muted me-3 d-flex align-items-center" title="Uptime">
          {render_uptime_indicator(uptime_info)}
        </div>
        '''

    except Exception as e:
        current_app.logger.error(f"Error getting header summary: {e}")
        # Return fallback HTML on error
        return '''
        <span class="d-flex align-items-center me-3" aria-live="polite">
          <span class="status-indicator-animated bg-red me-2" style="width:20px;height:20px;border-radius:50%;display:inline-block;" aria-hidden="true"></span>
          <small class="text-muted">Error</small>
        </span>
        <a class="text-muted d-flex align-items-center me-3" href="#" title="Active tasks">
          <small class="text-muted">!</small>
        </a>
        <div class="text-muted me-3 d-flex align-items-center" title="Uptime">
          <small class="text-muted">--</small>
        </div>
        '''


@system_bp.route('/analyzer/start', methods=['POST'])
def start_analyzer_services():
    """Start analyzer services via Docker"""
    try:
        result = subprocess.run(['docker', 'ps'],
                              capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return api_success({
                'message': 'Docker is available. Analyzer services can be started via the analyzer_manager.py script.',
                'note': 'Please run: cd analyzer && python analyzer_manager.py start'
            })
        else:
            return api_error('Docker not available', status=500)

    except subprocess.TimeoutExpired:
        return api_error('Docker command timed out', status=500)
    except FileNotFoundError:
        return api_error('Docker not found. Please install Docker.', status=500)
    except Exception as e:
        current_app.logger.error(f"Error starting analyzer services: {str(e)}")
        return api_error(str(e), status=500)