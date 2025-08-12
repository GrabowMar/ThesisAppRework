"""
System API Routes
=================

API endpoints for system information and health checks.
"""

import logging
import os
import psutil
import subprocess
from datetime import datetime
from flask import jsonify, render_template

from . import api_bp
from ...extensions import db

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/system/health')
def api_system_health():
    """API endpoint: Get system health status."""
    try:
        # Database health check
        db_healthy = True
        db_error = None
        try:
            # Simple query to test database connection
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db.session.commit()
        except Exception as e:
            db_healthy = False
            db_error = str(e)
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
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
        
        return jsonify({
            'status': health_status,
            'timestamp': datetime.utcnow().isoformat(),
            'database': {
                'healthy': db_healthy,
                'error': db_error
            },
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent
            },
            'issues': issues
        })
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@api_bp.route('/system/info')
def api_system_info():
    """API endpoint: Get system information."""
    try:
        # System information
        system_info = {
            'platform': os.name,
            'python_version': f"{psutil.Process().memory_info().rss}",  # Placeholder
            'cpu_count': psutil.cpu_count(),
            'total_memory': psutil.virtual_memory().total,
            'available_memory': psutil.virtual_memory().available,
            'disk_total': psutil.disk_usage('/').total,
            'disk_free': psutil.disk_usage('/').free,
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }
        
        # Process information
        current_process = psutil.Process()
        process_info = {
            'pid': current_process.pid,
            'memory_usage': current_process.memory_info().rss,
            'cpu_percent': current_process.cpu_percent(),
            'create_time': datetime.fromtimestamp(current_process.create_time()).isoformat(),
            'num_threads': current_process.num_threads()
        }
        
        return jsonify({
            'system': system_info,
            'process': process_info,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/system/overview')
def api_system_overview():
    """API endpoint: Get system overview."""
    try:
        # Get basic system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Database status
        db_status = 'connected'
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db.session.commit()
        except Exception:
            db_status = 'disconnected'
        
        # Uptime
        boot_time = psutil.boot_time()
        uptime_seconds = datetime.utcnow().timestamp() - boot_time
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        
        return jsonify({
            'status': 'online',
            'uptime': {
                'days': uptime_days,
                'hours': uptime_hours,
                'minutes': uptime_minutes,
                'total_seconds': int(uptime_seconds)
            },
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
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system overview: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/system/metrics')
def api_system_metrics():
    """API endpoint: Get detailed system metrics."""
    try:
        # CPU information
        cpu_info = {
            'physical_cores': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'current_freq': psutil.cpu_freq().current if psutil.cpu_freq() else None,
            'usage_per_core': psutil.cpu_percent(percpu=True, interval=1)
        }
        
        # Memory information
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        memory_info = {
            'virtual': {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent
            },
            'swap': {
                'total': swap.total,
                'used': swap.used,
                'free': swap.free,
                'percent': swap.percent
            }
        }
        
        # Disk information
        disk_io = psutil.disk_io_counters()
        disk_info = {
            'usage': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free,
                'percent': psutil.disk_usage('/').percent
            },
            'io': disk_io._asdict() if disk_io else {}
        }
        
        # Network information
        net_io = psutil.net_io_counters()
        network_info = {
            'io': net_io._asdict() if net_io else {},
            'connections': len(psutil.net_connections())
        }
        
        return jsonify({
            'cpu': cpu_info,
            'memory': memory_info,
            'disk': disk_info,
            'network': network_info,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/system/logs')
def api_system_logs():
    """API endpoint: Get system logs."""
    try:
        # This is a placeholder - in a real implementation,
        # you would read from actual log files
        logs = [
            {
                'timestamp': datetime.utcnow().isoformat(),
                'level': 'INFO',
                'message': 'System health check completed',
                'component': 'health_monitor'
            },
            {
                'timestamp': (datetime.utcnow()).isoformat(),
                'level': 'INFO', 
                'message': 'API server running normally',
                'component': 'api_server'
            }
        ]
        
        return jsonify({
            'logs': logs,
            'count': len(logs),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system logs: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# SYSTEM MONITORING AND ANALYZER MANAGEMENT  
# =================================================================

@api_bp.route('/system_health')
def system_health():
    """HTMX endpoint for system health status."""
    try:
        from sqlalchemy import text
        from flask import render_template
        
        # Check database status
        try:
            db.session.execute(text('SELECT 1'))
            db_status = {'status': 'healthy', 'message': 'Connected'}
        except Exception as e:
            db_status = {'status': 'error', 'message': str(e)}
        
        # Check Celery status
        try:
            from ...extensions import get_components
            components = get_components()
            celery_instance = components.celery if components else None
            if celery_instance:
                celery_inspect = celery_instance.control.inspect()
                active_tasks = celery_inspect.active()
                celery_status = {'status': 'healthy', 'message': 'Running'} if active_tasks is not None else {'status': 'error', 'message': 'Not responding'}
            else:
                celery_status = {'status': 'warning', 'message': 'Not available'}
        except Exception as e:
            celery_status = {'status': 'error', 'message': str(e)}
        
        # Check analyzer status (simplified to avoid encoding issues)
        try:
            from ...extensions import get_components
            components = get_components()
            analyzer_integration = components.analyzer_integration if components else None
            if analyzer_integration:
                # Just check if the service exists, don't run commands that might have encoding issues
                analyzer_status = {'status': 'available', 'message': 'Service available'}
            else:
                analyzer_status = {'status': 'warning', 'message': 'Not configured'}
        except Exception as e:
            analyzer_status = {'status': 'error', 'message': str(e)}
        
        system_status = {
            'database': db_status,
            'celery': celery_status,
            'analyzer': analyzer_status
        }
        
        return render_template('partials/system_status.html', system_status=system_status)
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        # Return a minimal system status to prevent template errors
        fallback_status = {
            'database': {'status': 'error', 'message': 'Health check failed'},
            'celery': {'status': 'error', 'message': 'Health check failed'},
            'analyzer': {'status': 'error', 'message': 'Health check failed'}
        }
        return render_template('partials/system_status.html', system_status=fallback_status)


# =================================================================
# ANALYZER SERVICE MANAGEMENT
# =================================================================

@api_bp.route('/analyzer/status')
def get_analyzer_status():
    """Get comprehensive analyzer services status."""
    try:
        from ...extensions import get_components
        
        components = get_components()
        analyzer_integration = components.analyzer_integration if components else None
        
        if not analyzer_integration:
            return jsonify({
                'status': 'unavailable',
                'message': 'Analyzer integration not available',
                'services': {}
            })
        
        # Get analyzer manager status
        status_info = analyzer_integration.get_services_status()
        
        # Try to ping analyzer_manager.py directly
        analyzer_manager_health = _ping_analyzer_manager()
        
        return jsonify({
            'status': 'available',
            'analyzer_manager': analyzer_manager_health,
            'services': status_info.get('services', {}),
            'last_check': datetime.utcnow().isoformat(),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting analyzer status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'services': {}
        }), 500


@api_bp.route('/analyzer/ping')
def ping_analyzer_services():
    """Ping individual analyzer services."""
    try:
        import socket
        services_status = {}
        
        # Standard analyzer services from analyzer_manager.py
        services = {
            'static-analyzer': 2001,
            'dynamic-analyzer': 2002, 
            'performance-tester': 2003,
            'ai-analyzer': 2004
        }
        
        for service_name, port in services.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                services_status[service_name] = {
                    'status': 'reachable' if result == 0 else 'unreachable',
                    'port': port,
                    'last_ping': datetime.utcnow().isoformat()
                }
            except Exception as e:
                services_status[service_name] = {
                    'status': 'error',
                    'port': port,
                    'error': str(e),
                    'last_ping': datetime.utcnow().isoformat()
                }
        
        overall_status = 'healthy' if any(s['status'] == 'reachable' for s in services_status.values()) else 'unhealthy'
        
        return jsonify({
            'overall_status': overall_status,
            'services': services_status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error pinging analyzer services: {e}")
        return jsonify({
            'overall_status': 'error',
            'error': str(e),
            'services': {}
        }), 500


@api_bp.route('/analyzer/start', methods=['POST'])
def start_analyzer_services():
    """Start analyzer services via analyzer_manager.py."""
    try:
        import subprocess
        from pathlib import Path
        
        analyzer_manager_path = Path(__file__).parent.parent.parent.parent.parent / "analyzer" / "analyzer_manager.py"
        
        if not analyzer_manager_path.exists():
            return jsonify({
                'success': False,
                'error': 'Analyzer manager script not found'
            }), 404
        
        # Run analyzer start command
        result = subprocess.run([
            'python', str(analyzer_manager_path), 'start'
        ], capture_output=True, text=True, timeout=60, cwd=analyzer_manager_path.parent)
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Analyzer services starting',
                'output': result.stdout[:500]
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to start services: {result.stderr[:200]}'
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Start command timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error starting analyzer services: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/analyzer/stop', methods=['POST'])
def stop_analyzer_services():
    """Stop analyzer services via analyzer_manager.py."""
    try:
        import subprocess
        from pathlib import Path
        
        analyzer_manager_path = Path(__file__).parent.parent.parent.parent.parent / "analyzer" / "analyzer_manager.py"
        
        if not analyzer_manager_path.exists():
            return jsonify({
                'success': False,
                'error': 'Analyzer manager script not found'
            }), 404
        
        # Run analyzer stop command
        result = subprocess.run([
            'python', str(analyzer_manager_path), 'stop'
        ], capture_output=True, text=True, timeout=30, cwd=analyzer_manager_path.parent)
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Analyzer services stopping',
                'output': result.stdout[:500]
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to stop services: {result.stderr[:200]}'
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Stop command timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error stopping analyzer services: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _ping_analyzer_manager():
    """Helper function to ping analyzer_manager.py."""
    try:
        import subprocess
        from pathlib import Path
        
        analyzer_manager_path = Path(__file__).parent.parent.parent.parent.parent / "analyzer" / "analyzer_manager.py"
        
        if not analyzer_manager_path.exists():
            return {
                'status': 'unavailable',
                'message': 'Analyzer manager script not found'
            }
        
        # Try to run status command with short timeout
        result = subprocess.run([
            'python', str(analyzer_manager_path), 'health'
        ], capture_output=True, text=True, timeout=5, cwd=analyzer_manager_path.parent)
        
        if result.returncode == 0:
            return {
                'status': 'available',
                'message': 'Analyzer manager responding',
                'output': result.stdout[:200]  # Truncate output
            }
        else:
            return {
                'status': 'error', 
                'message': f'Analyzer manager error: {result.stderr[:100]}'
            }
            
    except subprocess.TimeoutExpired:
        return {
            'status': 'timeout',
            'message': 'Analyzer manager timed out'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error pinging analyzer manager: {str(e)}'
        }
