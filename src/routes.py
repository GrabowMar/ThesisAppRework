"""
Flask Routes and Blueprints
===========================

Main route definitions for the Thesis Research App.
Includes routes for dashboard, analysis, performance testing, ZAP scanning, and generation content.
"""

import json
import os
import subprocess
import time
from enum import Enum
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, redirect, 
    render_template, request, url_for, make_response, session, jsonify, abort, Response
)

from logging_service import create_logger_for_component
from utils import (
    get_all_apps, get_app_container_statuses,
    get_app_directory, get_apps_for_model, get_container_names,
    handle_docker_action, verify_container_health, get_docker_manager, create_api_response,
    get_port_config, get_ai_models, get_app_config_by_model_and_number, get_app_info,
    load_json_results_for_template, get_available_analysis_results, get_latest_analysis_timestamp,
    get_dashboard_data_optimized, warm_container_cache_safe, get_cache_stats, clear_container_cache,
    get_model_stats, get_model_by_name, get_models_by_provider
)

# Import generation lookup service
try:
    from generation_lookup_service import GenerationLookupService
    generation_lookup_service = GenerationLookupService()
except Exception as e:
    logger = create_logger_for_component('routes')
    logger.error(f"Failed to initialize GenerationLookupService: {e}")
    generation_lookup_service = None

# Optional psutil import for system information
try:
    import psutil
except ImportError:
    psutil = None


class ScanState(Enum):
    """Enumeration of possible ZAP scan states."""
    NOT_RUN = "Not Run"
    STARTING = "Starting"
    SPIDERING = "Spidering"
    SCANNING = "Scanning"
    COMPLETE = "Complete"
    FAILED = "Failed"
    ERROR = "Error"
    STOPPED = "Stopped"


# Create blueprints
main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")
analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")
quality_bp = Blueprint("quality", __name__, url_prefix="/quality")
performance_bp = Blueprint("performance", __name__, url_prefix="/performance")
gpt4all_bp = Blueprint("gpt4all", __name__, url_prefix="/gpt4all")
zap_bp = Blueprint("zap", __name__, url_prefix="/zap")
generation_bp = Blueprint("generation", __name__, url_prefix="/generation")

# Initialize logger
logger = create_logger_for_component('routes')


def get_scan_manager():
    """
    Get scan manager from app context.
    
    Returns:
        ScanManager instance
    """
    if not hasattr(current_app, 'scan_manager'):
        from services import ScanManager
        current_app.scan_manager = ScanManager()
    return current_app.scan_manager


def filter_apps(apps, search=None, model=None, status=None):
    """Filter apps based on search criteria."""
    filtered = apps
    
    if search:
        search_lower = search.lower()
        filtered = [app for app in filtered if 
                   search_lower in app['model'].lower() or 
                   search_lower in str(app['app_num'])]
    
    if model:
        filtered = [app for app in filtered if app['model'] == model]
    
    if status:
        def get_app_status(app):
            if app.get('backend_status', {}).get('running') and app.get('frontend_status', {}).get('running'):
                return 'running'
            elif app.get('backend_status', {}).get('running') or app.get('frontend_status', {}).get('running'):
                return 'partial'
            else:
                return 'stopped'
        
        filtered = [app for app in filtered if get_app_status(app) == status]
    
    return filtered


# Main routes
@main_bp.route("/")
def index():
    """Main dashboard showing all apps and their statuses with optimized loading."""
    docker_manager = get_docker_manager()
    
    # Use optimized dashboard data loading
    dashboard_data = get_dashboard_data_optimized(docker_manager)
    apps = dashboard_data.get('apps', [])
    
    # Apply filters
    search = request.args.get('search')
    model_filter = request.args.get('model')
    status_filter = request.args.get('status')
    
    if search or model_filter or status_filter:
        apps = filter_apps(apps, search, model_filter, status_filter)
    
    autorefresh_enabled = request.cookies.get('autorefresh', 'false') == 'true'
    
    # Debug: Log app data structure and try URL generation
    logger = create_logger_for_component('routes.index')
    logger.info(f"Total apps: {len(apps)} (cache used: {dashboard_data.get('cache_used', False)})")
    
    if apps:
        first_app = apps[0]
        logger.debug(f"First app structure: {first_app}")
        logger.debug(f"First app model: {first_app.get('model')}")
        logger.debug(f"First app app_num: {first_app.get('app_num')}")
        
        # Test URL generation
        try:
            from flask import url_for
            test_url = url_for('analysis.analyze_app', model=first_app['model'], app_num=first_app['app_num'])
            logger.debug(f"Successfully generated URL: {test_url}")
        except Exception as e:
            logger.error(f"Failed to generate URL: {e}")
    
    # Enhance apps with analysis results availability
    for app in apps:
        try:
            available_analyses = get_available_analysis_results(app['model'], app['app_num'])
            app['available_analyses'] = available_analyses
            app['has_analysis_results'] = len(available_analyses) > 0
            app['latest_analysis_timestamp'] = get_latest_analysis_timestamp(app['model'], app['app_num'])
        except Exception as e:
            logger.warning(f"Error getting analysis results for {app['model']}/app{app['app_num']}: {e}")
            app['available_analyses'] = []
            app['has_analysis_results'] = False
            app['latest_analysis_timestamp'] = None
    
    return render_template("index.html", apps=apps, models=get_ai_models(), 
                         autorefresh_enabled=autorefresh_enabled,
                         cache_stats=get_cache_stats())


@main_bp.route("/status/<string:model>/<int:app_num>")
def check_app_status(model: str, app_num: int):
    """Get container status for a specific app."""
    docker_manager = get_docker_manager()
    statuses = get_app_container_statuses(model, app_num, docker_manager)
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(statuses)
    
    # For non-AJAX requests, show a simple status page
    return render_template("status.html", model=model, app_num=app_num, statuses=statuses)


@main_bp.route("/<action>/<string:model>/<int:app_num>", methods=["POST"])
def handle_docker_action_route(action: str, model: str, app_num: int):
    """Handle Docker actions (start, stop, restart, build, rebuild)."""
    success, message = handle_docker_action(action, model, app_num)
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return create_api_response(
            success=success,
            message=message,
            code=200 if success else 500
        )
    
    # For regular form submissions, use flash and redirect
    flash_message = message[:500] + "..." if len(message) > 500 else message
    flash(f"{'Success' if success else 'Error'}: {flash_message}", 
          "success" if success else "error")
    
    return redirect(request.referrer or url_for("main.index"))


@main_bp.route("/batch/<action>/<string:model>", methods=["POST"])
def batch_docker_action(action: str, model: str):
    """Execute batch Docker actions on all apps for a model."""
    # Handle special case for batch form submission
    if action == 'BATCH_ACTION':
        action = request.form.get('batch_action', '')
        if not action:
            flash("Please select a batch action", "error")
            return redirect(url_for("main.index"))
    
    valid_actions = ["start", "stop", "restart", "build", "rebuild", "health-check"]
    if action not in valid_actions:
        flash(f"Invalid action: {action}", "error")
        return redirect(url_for("main.index"))
    
    apps = get_apps_for_model(model)
    if not apps:
        flash(f"No apps found for model {model}", "error")
        return redirect(url_for("main.index"))
    
    results = []
    docker_manager = current_app.config.get("docker_manager")
    
    for app in apps:
        app_num = app["app_num"]
        
        try:
            if action == "health-check":
                if docker_manager:
                    healthy, message = verify_container_health(docker_manager, model, app_num)
                    results.append({"app_num": app_num, "success": healthy, "message": message})
                else:
                    results.append({"app_num": app_num, "success": False, "message": "Docker manager unavailable"})
            else:
                success, message = handle_docker_action(action, model, app_num)
                results.append({"app_num": app_num, "success": success, "message": message})
        except Exception as e:
            results.append({"app_num": app_num, "success": False, "message": f"Error: {str(e)}"})
    
    success_count = sum(1 for r in results if r["success"])
    
    flash(f"Batch {action} completed: {success_count}/{len(results)} successful", 
          "success" if success_count == len(results) else "warning")
    
    return redirect(url_for("main.index"))


@main_bp.route("/logs/<string:model>/<int:app_num>")
def view_logs(model: str, app_num: int):
    """View container logs for an app."""
    try:
        docker_manager = get_docker_manager()
        backend_name, frontend_name = get_container_names(model, app_num)
        
        logs_data = {
            "backend": docker_manager.get_container_logs(backend_name),
            "frontend": docker_manager.get_container_logs(frontend_name)
        }
        
        # Add a custom filter for log level filtering
        def filter_logs(log_text, level='all'):
            if level == 'all':
                return log_text
            
            lines = log_text.split('\n')
            filtered = [line for line in lines if level.upper() in line.upper()]
            return '\n'.join(filtered)
        
        # Register the filter
        current_app.jinja_env.filters['filter_logs'] = filter_logs
        
        return render_template("logs.html", logs=logs_data, model=model, app_num=app_num)
    except Exception as e:
        flash(f"Error retrieving logs: {e}", "error")
        return redirect(url_for("main.index"))


@main_bp.route("/docker-logs/<string:model>/<int:app_num>")
def view_docker_logs(model: str, app_num: int):
    """View Docker Compose logs for an app."""
    compose_logs = "Could not retrieve docker-compose logs."
    backend_logs = "Could not retrieve backend logs."
    frontend_logs = "Could not retrieve frontend logs."

    try:
        app_dir = get_app_directory(model, app_num)
        
        # Get docker-compose logs
        try:
            result = subprocess.run(
                ["docker-compose", "logs", "--no-color", "--tail", "200"],
                cwd=str(app_dir), capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0:
                compose_logs = result.stdout or "No logs output from docker-compose."
            else:
                compose_logs = f"Error (Code {result.returncode}): {result.stderr or result.stdout}"
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            compose_logs = f"Error fetching docker-compose logs: {e}"

        # Get container logs
        backend_name, frontend_name = get_container_names(model, app_num)
        docker_manager = get_docker_manager()
        backend_logs = docker_manager.get_container_logs(backend_name, tail=100)
        frontend_logs = docker_manager.get_container_logs(frontend_name, tail=100)

        return render_template("docker_logs.html", model=model, app_num=app_num,
                             compose_logs=compose_logs, backend_logs=backend_logs, 
                             frontend_logs=frontend_logs)
    except Exception as e:
        flash(f"Error retrieving Docker logs: {e}", "error")
        return redirect(url_for("main.index"))


# API routes
@api_bp.route("/log-client-error", methods=["POST"])
def log_client_error():
    """Log client-side errors to the server."""
    try:
        data = request.get_json() or {}
        error_message = data.get('message', 'Unknown client error')
        error_url = data.get('url', request.referrer or 'Unknown URL')
        error_line = data.get('line', 'Unknown')
        error_stack = data.get('stack', 'No stack trace')
        
        # Log the client error
        logger.error(f"Client Error - URL: {error_url}, Message: {error_message}, Line: {error_line}, Stack: {error_stack}")
        
        return create_api_response(
            success=True,
            message="Error logged successfully"
        )
    except Exception as e:
        logger.error(f"Error logging client error: {e}")
        return create_api_response(
            success=False,
            error=f"Failed to log client error: {str(e)}"
        ), 500


@api_bp.route("/toggle-autorefresh", methods=["POST"])
def toggle_autorefresh():
    """Toggle autorefresh setting."""
    current_setting = request.cookies.get('autorefresh', 'false')
    new_setting = 'false' if current_setting == 'true' else 'true'
    
    response = make_response(redirect(url_for("main.index")))
    response.set_cookie('autorefresh', new_setting, max_age=86400)  # 24 hours
    
    flash(f"Auto-refresh {'enabled' if new_setting == 'true' else 'disabled'}", "success")
    return response


@api_bp.route("/copy-to-clipboard", methods=["POST"])
def copy_to_clipboard():
    """Handle copy to clipboard (server-side fallback)."""
    content = request.form.get('content', '')
    
    # Store in session for retrieval
    session['clipboard_content'] = content
    
    # Create a download response as fallback
    response = make_response(content)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Content-Disposition'] = 'attachment; filename=logs.txt'
    
    return response


@api_bp.route("/system-info")
def system_info():
    """Get comprehensive system information."""
    try:
        logger.info("Gathering system information")
        
        docker_manager = current_app.config.get("docker_manager")
        
        if not docker_manager:
            return create_api_response(
                success=False,
                error="Docker manager not available",
                code=503
            )
        
        # Basic Docker info
        info = {
            "docker": {
                "available": docker_manager.is_docker_available(),
                "version": docker_manager.get_docker_version() or "Unknown",
                "compose_version": docker_manager.get_compose_version() or "Unknown"
            },
            "system": {}
        }
        
        # System metrics using psutil if available
        if psutil:
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                info["system"] = {
                    "cpu": {
                        "percent": cpu_percent,
                        "count": psutil.cpu_count()
                    },
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent,
                        "used": memory.used
                    },
                    "disk": {
                        "total": disk.total,
                        "used": disk.used,
                        "free": disk.free,
                        "percent": disk.percent
                    }
                }
                
                # Container metrics
                containers_info = []
                try:
                    # Get all running containers
                    containers = docker_manager.client.containers.list()
                    for container in containers[:20]:  # Limit to 20 containers
                        try:
                            stats = container.stats(stream=False)
                            
                            # Calculate CPU percentage
                            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
                            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                                          stats["precpu_stats"]["system_cpu_usage"]
                            cpu_percent = 0.0
                            if system_delta > 0.0:
                                cpu_percent = (cpu_delta / system_delta) * 100.0
                            
                            # Memory usage
                            mem_usage = stats["memory_stats"].get("usage", 0)
                            mem_limit = stats["memory_stats"].get("limit", 1)
                            mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
                            
                            containers_info.append({
                                "name": container.name,
                                "status": container.status,
                                "cpu_percent": round(cpu_percent, 2),
                                "memory": {
                                    "usage": mem_usage,
                                    "limit": mem_limit,
                                    "percent": round(mem_percent, 2)
                                }
                            })
                        except Exception as e:
                            logger.debug(f"Error getting stats for container {container.name}: {e}")
                            
                except Exception as e:
                    logger.error(f"Error getting container stats: {e}")
                
                info["containers"] = containers_info
                
            except Exception as e:
                logger.error(f"Error getting system metrics: {e}")
                info["system"]["error"] = str(e)
        else:
            info["system"]["error"] = "psutil not available"
        
        # Return as JSON for compatibility
        return jsonify(info)
        
    except Exception as e:
        logger.exception(f"System info error: {e}")
        return create_api_response(
            success=False,
            error=f"Failed to get system info: {str(e)}",
            code=500
        )


# Analysis routes
@analysis_bp.route("/<string:model>/<int:app_num>")
def analyze_app(model: str, app_num: int):
    """Security analysis page for a specific app."""
    try:
        # Get app configuration
        app_config = get_app_config_by_model_and_number(model, app_num)
        if not app_config:
            flash(f"App {model}/{app_num} not found", "error")
            return redirect(url_for("main.index"))
        
        # Load existing JSON results
        json_results = load_json_results_for_template(model, app_num)
        available_analyses = get_available_analysis_results(model, app_num)
        latest_timestamp = get_latest_analysis_timestamp(model, app_num)
        
        # Check if analyzers are available
        backend_analyzer = getattr(current_app, 'backend_security_analyzer', None)
        frontend_analyzer = getattr(current_app, 'frontend_security_analyzer', None)
        
        # Prepare summary from JSON results
        summary = {'total_issues': 0, 'files_affected': 0, 'files_analyzed': 0, 'severity_counts': {'high': 0, 'medium': 0, 'low': 0}, 'tool_counts': {}}
        issues = []
        
        # Process backend security results
        if 'backend_security' in json_results:
            backend_data = json_results['backend_security']
            if 'issues' in backend_data:
                issues.extend(backend_data['issues'])
                for issue in backend_data['issues']:
                    if issue.get('severity', '').lower() in summary['severity_counts']:
                        summary['severity_counts'][issue['severity'].lower()] += 1
                    summary['total_issues'] += 1
        
        # Process frontend security results
        if 'frontend_security' in json_results:
            frontend_data = json_results['frontend_security']
            if 'issues' in frontend_data:
                issues.extend(frontend_data['issues'])
                for issue in frontend_data['issues']:
                    if issue.get('severity', '').lower() in summary['severity_counts']:
                        summary['severity_counts'][issue['severity'].lower()] += 1
                    summary['total_issues'] += 1
        
        return render_template("analysis.html", 
                             model=model, 
                             app_num=app_num, 
                             app_config=app_config,
                             backend_analyzer_available=backend_analyzer is not None,
                             frontend_analyzer_available=frontend_analyzer is not None,
                             summary=summary,
                             issues=issues,
                             json_results=json_results,
                             available_analyses=available_analyses,
                             latest_timestamp=latest_timestamp)
    except Exception as e:
        logger.error(f"Error loading analysis page: {e}")
        flash(f"Error loading analysis page: {e}", "error")
        return redirect(url_for("main.index"))


@analysis_bp.route("/<string:model>/<int:app_num>/run", methods=["POST"])
def run_analysis(model: str, app_num: int):
    """Run security analysis on a specific app."""
    try:
        analysis_type = request.form.get('analysis_type', 'both')
        use_all_tools = request.form.get('use_all_tools') == 'on'
        force_rerun = request.form.get('force_rerun') == 'on'
        
        results = {}
        
        if analysis_type in ['backend', 'both']:
            backend_analyzer = getattr(current_app, 'backend_security_analyzer', None)
            if backend_analyzer:
                try:
                    issues, tool_status, tool_outputs = backend_analyzer.run_security_analysis(
                        model, app_num, use_all_tools=use_all_tools, force_rerun=force_rerun
                    )
                    results['backend'] = {
                        'issues': issues,
                        'tool_status': tool_status,
                        'tool_outputs': tool_outputs
                    }
                except Exception as e:
                    logger.error(f"Backend analysis failed: {e}")
                    results['backend'] = {'error': str(e)}
        
        if analysis_type in ['frontend', 'both']:
            frontend_analyzer = getattr(current_app, 'frontend_security_analyzer', None)
            if frontend_analyzer:
                try:
                    issues, tool_status, tool_outputs = frontend_analyzer.run_security_analysis(
                        model, app_num, use_all_tools=use_all_tools, force_rerun=force_rerun
                    )
                    results['frontend'] = {
                        'issues': issues,
                        'tool_status': tool_status,
                        'tool_outputs': tool_outputs
                    }
                except Exception as e:
                    logger.error(f"Frontend analysis failed: {e}")
                    results['frontend'] = {'error': str(e)}
        
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify(results)
        else:
            # For form submissions, redirect back with flash message
            if any('error' in result for result in results.values()):
                flash("Analysis completed with some errors. Check the results below.", "warning")
            else:
                flash("Analysis completed successfully!", "success")
            
            return render_template("analysis_results.html", 
                                 model=model, 
                                 app_num=app_num, 
                                 results=results)
                                 
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        flash(f"Error running analysis: {e}", "error")
        return redirect(url_for("analysis.analyze_app", model=model, app_num=app_num))


# Performance routes
@performance_bp.route("/<string:model>/<int:port>")
def performance_test(model: str, port: int):
    """Performance testing page for a specific app."""
    try:
        # Get performance tester
        performance_tester = getattr(current_app, 'performance_tester', None)
        
        # Calculate app_num from port (reverse of port calculation)
        app_num = ((port - 5501) // 10) + 1
        
        # Load existing JSON results
        json_results = load_json_results_for_template(model, app_num, 'performance')
        available_analyses = get_available_analysis_results(model, app_num)
        latest_timestamp = get_latest_analysis_timestamp(model, app_num)
        
        # Process performance results if available
        performance_data = None
        if 'performance' in json_results:
            performance_data = json_results['performance']
        
        return render_template("performance.html", 
                             model=model, 
                             port=port,
                             app_num=app_num,
                             performance_tester_available=performance_tester is not None,
                             json_results=json_results,
                             performance_data=performance_data,
                             available_analyses=available_analyses,
                             latest_timestamp=latest_timestamp)
    except Exception as e:
        logger.error(f"Error loading performance test page: {e}")
        flash(f"Error loading performance test page: {e}", "error")
        return redirect(url_for("main.index"))


@performance_bp.route("/<string:model>/<int:port>", methods=["POST"])
def run_performance_test(model: str, port: int):
    """Run performance test for a specific app."""
    try:
        # Get performance tester
        performance_tester = getattr(current_app, 'performance_tester', None)
        if not performance_tester:
            return create_api_response(
                success=False,
                error="Performance tester not available"
            ), 500

        # Parse request data
        data = request.get_json()
        if not data:
            return create_api_response(
                success=False,
                error="No JSON data provided"
            ), 400

        # Extract test parameters
        num_users = data.get('num_users', 10)
        duration = data.get('duration', 30)
        spawn_rate = data.get('spawn_rate', 1)
        endpoints = data.get('endpoints', [{"path": "/", "method": "GET", "weight": 1}])

        # Validate parameters
        if not isinstance(num_users, int) or num_users < 1:
            return create_api_response(
                success=False,
                error="num_users must be a positive integer"
            ), 400
            
        if not isinstance(duration, int) or duration < 5:
            return create_api_response(
                success=False,
                error="duration must be at least 5 seconds"
            ), 400
            
        if not isinstance(spawn_rate, int) or spawn_rate < 1:
            return create_api_response(
                success=False,
                error="spawn_rate must be a positive integer"
            ), 400

        # Determine app_num from port configuration
        port_config = get_port_config()
        app_num = None
        for model_name, model_ports in port_config.items():
            if model_name == model:
                for app_port_info in model_ports:
                    if app_port_info.get('frontend_port') == port:
                        app_num = app_port_info.get('app_num')
                        break
                break
        
        if app_num is None:
            logger.warning(f"Could not determine app_num from port {port} for model {model}")
            app_num = 1  # Default fallback

        # Build target host URL
        host = f"http://localhost:{port}"

        # Run the performance test
        logger.info(f"Starting performance test for {model} on port {port}")
        logger.info(f"Test parameters: users={num_users}, duration={duration}s, spawn_rate={spawn_rate}")
        logger.info(f"Endpoints: {endpoints}")

        # Use the library method for better control and error handling
        result = performance_tester.run_test_library(
            test_name=f"performance_test_{model}_app{app_num}",
            host=host,
            endpoints=endpoints,
            user_count=num_users,
            spawn_rate=spawn_rate,
            run_time=duration,
            model=model,
            app_num=app_num,
            force_rerun=True  # Always run fresh test from UI
        )

        if result:
            # Convert result to dict for JSON response
            result_dict = result.to_dict()
            logger.info(f"Performance test completed successfully for {model}/port{port}")
            
            return create_api_response(
                success=True,
                data=result_dict,
                message="Performance test completed successfully"
            )
        else:
            logger.error(f"Performance test failed for {model}/port{port}")
            return create_api_response(
                success=False,
                error="Performance test failed to run"
            ), 500

    except Exception as e:
        logger.exception(f"Error running performance test for {model}/port{port}: {e}")
        return create_api_response(
            success=False,
            error=f"Performance test error: {str(e)}"
        ), 500


# ZAP routes
@zap_bp.route("/<string:model>/<int:app_num>", methods=["GET", "POST"])
def zap_scan(model: str, app_num: int):
    """ZAP scan page for a specific app."""
    try:
        # Get app configuration and info
        app_config = get_app_config_by_model_and_number(model, app_num)
        if not app_config:
            flash(f"App {model}/{app_num} not found", "error")
            return redirect(url_for("main.index"))
        
        # Get dynamic app info (including actual ports)
        app_info = get_app_info(model, app_num)
        
        # Check if ZAP scanner is available
        zap_scanner = getattr(current_app, 'zap_scanner', None)
        
        # Initialize summary with default structure
        summary = {
            'total_vulnerabilities': 0,
            'vulnerabilities_with_code': 0,
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0,
            'info_severity': 0,
            'scan_duration': 0,
            'timestamp': None,
            'status': 'not_started',
            'target_url': '',
            'scan_mode': '',
            'error': None
        }
        
        alerts = []
        
        # Try to load existing ZAP results from centralized reports
        json_results = load_json_results_for_template(model, app_num, 'zap_scan')
        available_analyses = get_available_analysis_results(model, app_num)
        latest_timestamp = get_latest_analysis_timestamp(model, app_num)
        
        logger.info(f"Loading ZAP results for model='{model}', app_num={app_num}")
        logger.info(f"Available analyses: {available_analyses}")
        logger.info(f"JSON results keys: {list(json_results.keys())}")
        logger.info(f"App info: {app_info}")
        
        # Process ZAP results if available
        if 'zap_scan' in json_results:
            zap_data = json_results['zap_scan']
            logger.info(f"Found ZAP scan data with keys: {list(zap_data.keys())}")
            
            # Check metadata to verify it's for the correct model/app
            if '_metadata' in zap_data:
                metadata = zap_data['_metadata']
                logger.info(f"ZAP scan metadata: {metadata}")
                expected_model = metadata.get('model')
                expected_app_num = metadata.get('app_num')
                
                if expected_model != model or expected_app_num != app_num:
                    logger.warning(f"ZAP scan data mismatch! Expected {model}/app{app_num}, got {expected_model}/app{expected_app_num}")
                else:
                    logger.info(f"ZAP scan data matches expected model/app: {model}/app{app_num}")
            
            logger.debug(f"ZAP data keys: {list(zap_data.keys())}")
            
            # Update summary from JSON results
            if 'summary' in zap_data:
                summary.update(zap_data['summary'])
                logger.debug(f"Updated summary from JSON: {summary}")
                
                # Handle different summary field naming conventions
                zap_summary = zap_data['summary']
                
                # Map old field names to new ones for backward compatibility
                if 'high' in zap_summary:
                    summary['high_severity'] = zap_summary['high']
                if 'medium' in zap_summary:
                    summary['medium_severity'] = zap_summary['medium']
                if 'low' in zap_summary:
                    summary['low_severity'] = zap_summary['low']
                if 'info' in zap_summary:
                    summary['info_severity'] = zap_summary['info']
                
                # Handle total_alerts vs total_vulnerabilities
                if 'total_alerts' in zap_summary and 'total_vulnerabilities' not in zap_summary:
                    summary['total_vulnerabilities'] = zap_summary['total_alerts']
            
            # Load alerts from JSON results
            if 'alerts' in zap_data:
                alerts = zap_data['alerts']
                logger.debug(f"Loaded {len(alerts)} alerts from JSON")
                
                # Count vulnerabilities with code
                if alerts:
                    summary['vulnerabilities_with_code'] = sum(
                        1 for alert in alerts 
                        if alert.get('code_context') or alert.get('sourceid') or alert.get('affected_code')
                    )
                    
                    # Calculate severity counts if not already set in summary
                    if 'high_severity' not in summary or summary['high_severity'] == 0:
                        summary['high_severity'] = 0
                        summary['medium_severity'] = 0
                        summary['low_severity'] = 0
                        summary['info_severity'] = 0
                        
                        for alert in alerts:
                            risk_level = alert.get('risk', '').lower()
                            if risk_level == 'high':
                                summary['high_severity'] += 1
                            elif risk_level == 'medium':
                                summary['medium_severity'] += 1
                            elif risk_level == 'low':
                                summary['low_severity'] += 1
                            elif risk_level == 'informational' or risk_level == 'info':
                                summary['info_severity'] += 1
                        
                        if 'total_vulnerabilities' not in summary:
                            summary['total_vulnerabilities'] = len(alerts)
                        
                        logger.debug(f"Calculated summary from alerts: {summary}")
        
        logger.info(f"ZAP scan page loaded - Model: {model}, App: {app_num}, Alerts: {len(alerts)}, Summary: {summary}")
        
        return render_template("zap_scan.html", 
                            model=model, 
                            app_num=app_num,
                            app_config=app_config,
                            app_info=app_info,
                            summary=summary,
                            alerts=alerts,
                            json_results=json_results,
                            available_analyses=available_analyses,
                            latest_timestamp=latest_timestamp,
                            zap_scanner_available=zap_scanner is not None)
                            
    except Exception as e:
        logger.error(f"Error loading ZAP scan page: {e}")
        
        # Create minimal summary for error case
        error_summary = {
            'total_vulnerabilities': 0,
            'vulnerabilities_with_code': 0,
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0,
            'info_severity': 0,
            'scan_duration': 0,
            'timestamp': None,
            'status': 'error',
            'target_url': '',
            'scan_mode': '',
            'error': str(e)
        }
        
        flash(f"Error loading ZAP scan page: {e}", "error")
        
        # Try to render with error summary rather than redirecting
        try:
            app_config = get_app_config_by_model_and_number(model, app_num)
            return render_template("zap_scan.html", 
                                 model=model, 
                                 app_num=app_num,
                                 app_config=app_config or {},
                                 summary=error_summary,
                                 alerts=[],
                                 zap_scanner_available=False)
        except Exception as e:
            # If all else fails, redirect
            logger.error(f"Error in ZAP scan route: {e}")
            return redirect(url_for("main.index"))


@zap_bp.route("/scan/<string:model>/<int:app_num>", methods=["POST"])
def start_zap_scan(model: str, app_num: int):
    """Start a ZAP scan for a specific app."""
    try:
        # Get ZAP scanner from app context
        zap_scanner = getattr(current_app, 'zap_scanner', None)
        if not zap_scanner:
            logger.error("ZAP scanner not available in app context")
            return jsonify({
                "status": "error",
                "message": "ZAP scanner not available"
            }), 503
        
        # Check if scanner is ready
        logger.info(f"Checking if ZAP scanner is ready for {model}/app{app_num}")
        
        # First, check if the daemon startup thread is still running
        if hasattr(zap_scanner, '_daemon_startup_thread') and zap_scanner._daemon_startup_thread.is_alive():
            logger.info("ZAP daemon is still initializing in background thread, waiting up to 30 seconds...")
            # Wait for the thread to complete for up to 30 seconds
            zap_scanner._daemon_startup_thread.join(timeout=30)
        
        # Now check if the scanner is ready
        try:
            scanner_ready = zap_scanner.is_ready() if hasattr(zap_scanner, 'is_ready') else False
        except Exception as e:
            logger.error(f"Error checking scanner readiness: {e}")
            scanner_ready = False
            
        if not scanner_ready:
            # Try to manually start the daemon if it's not ready
            logger.warning("ZAP scanner not ready, attempting to start daemon...")
            try:
                # Check if the daemon process exists but is not responding
                if zap_scanner.daemon_manager.daemon_process and zap_scanner.daemon_manager.daemon_process.poll() is None:
                    logger.info("ZAP daemon process exists but not ready, waiting longer...")
                    # Wait a bit longer - the process exists but may still be initializing
                    time.sleep(5)
                    if hasattr(zap_scanner, 'is_ready') and zap_scanner.is_ready():
                        logger.info("ZAP scanner is now ready after additional wait")
                    else:
                        # Force restart the daemon
                        logger.warning("ZAP daemon not responding after wait, restarting...")
                        zap_scanner.daemon_manager.cleanup()
                        time.sleep(2)
                
                # Try to start the daemon
                logger.info("Starting ZAP daemon...")
                success = zap_scanner.daemon_manager.start_daemon()
                if success:
                    logger.info("ZAP daemon started successfully")
                    # Wait for the daemon to fully initialize
                    time.sleep(5)
                else:
                    logger.error("Failed to start ZAP daemon")
                    return jsonify({
                        "status": "error", 
                        "message": "ZAP scanner daemon failed to start. Please try again in a few minutes."
                    }), 503
            except Exception as e:
                logger.error(f"Error starting ZAP daemon: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"ZAP scanner daemon error: {str(e)}"
                }), 503
            
            # Check again if the daemon is ready after start attempt
            scanner_ready_after_start = (
                hasattr(zap_scanner, 'is_ready') and zap_scanner.is_ready()
            ) if zap_scanner else False
            
            if not scanner_ready_after_start:
                logger.error("ZAP scanner still not ready after daemon start attempt")
                
                # Check daemon process status for better diagnostics
                process_status = "No process"
                if hasattr(zap_scanner.daemon_manager, 'daemon_process') and zap_scanner.daemon_manager.daemon_process:
                    exit_code = zap_scanner.daemon_manager.daemon_process.poll()
                    if exit_code is None:
                        process_status = "Running but not ready"
                    else:
                        process_status = f"Exited with code {exit_code}"
                
                return jsonify({
                    "status": "error", 
                    "message": f"ZAP scanner is starting up but not ready yet. Process status: {process_status}. Please try again in a moment."
                }), 503
        
        # Get scan options from request
        data = request.get_json() or {}
        quick_scan = data.get('quick_scan', False)
        
        logger.info(f"Starting ZAP scan for {model}/app{app_num}, quick_scan={quick_scan}")
        
        # Start the scan
        success = zap_scanner.start_scan(model, app_num, quick_scan)
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Scan started successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to start scan"
            }), 500
            
    except Exception as e:
        logger.error(f"Error starting ZAP scan: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@zap_bp.route("/scan/<string:model>/<int:app_num>/stop", methods=["POST"])
def stop_zap_scan(model: str, app_num: int):
    """Stop a ZAP scan for a specific app."""
    try:
        # Get ZAP scanner from app context
        zap_scanner = getattr(current_app, 'zap_scanner', None)
        if not zap_scanner:
            return jsonify({
                "status": "error",
                "message": "ZAP scanner not available"
            }), 503
        
        logger.info(f"Stopping ZAP scan for {model}/app{app_num}")
        
        # Stop the scan
        success = zap_scanner.stop_scan(model, app_num)
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Scan stopped successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to stop scan"
            }), 500
            
    except Exception as e:
        logger.error(f"Error stopping ZAP scan: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@zap_bp.route("/scan/<string:model>/<int:app_num>/status", methods=["GET"])
def get_zap_scan_status(model: str, app_num: int):
    """Get the status of a ZAP scan for a specific app."""
    try:
        # Get ZAP scanner from app context
        zap_scanner = getattr(current_app, 'zap_scanner', None)
        if not zap_scanner:
            return jsonify({
                "status": "error",
                "message": "ZAP scanner not available"
            }), 503
        
        # Get scan status
        scan_status = zap_scanner.get_scan_status(model, app_num)
        
        if scan_status:
            return jsonify({
                "status": "success",
                "scan_status": scan_status.status,
                "progress": scan_status.progress,
                "high_count": scan_status.high_count,
                "medium_count": scan_status.medium_count,
                "low_count": scan_status.low_count,
                "info_count": scan_status.info_count,
                "spider_progress": scan_status.spider_progress,
                "passive_progress": scan_status.passive_progress,
                "active_progress": scan_status.active_progress,
                "ajax_progress": scan_status.ajax_progress,
                "phase": scan_status.phase,
                "current_operation": scan_status.current_operation,
                "urls_found": scan_status.urls_found,
                "alerts_found": scan_status.alerts_found,
                "start_time": scan_status.start_time,
                "duration_seconds": scan_status.duration_seconds
            })
        else:
            return jsonify({
                "status": "success",
                "scan_status": "Not Started",
                "progress": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "info_count": 0,
                "spider_progress": 0,
                "passive_progress": 0,
                "active_progress": 0,
                "ajax_progress": 0,
                "phase": "Not Started",
                "current_operation": "",
                "urls_found": 0,
                "alerts_found": 0,
                "start_time": None,
                "duration_seconds": None
            })
            
    except Exception as e:
        logger.error(f"Error getting ZAP scan status: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@zap_bp.route("/scan/<string:model>/<int:app_num>/progress", methods=["GET"])
def get_zap_scan_progress(model: str, app_num: int):
    """Get detailed progress of a ZAP scan for a specific app."""
    try:
        # Get ZAP scanner from app context
        zap_scanner = getattr(current_app, 'zap_scanner', None)
        if not zap_scanner:
            return jsonify({
                "status": "error",
                "message": "ZAP scanner not available"
            }), 503
        
        # Get scan status with detailed progress
        scan_status = zap_scanner.get_scan_status(model, app_num)
        
        if scan_status:
            # Convert ScanStatus to dict with all fields
            progress_data = {
                "status": scan_status.status,
                "progress": scan_status.progress,
                "high_count": scan_status.high_count,
                "medium_count": scan_status.medium_count,
                "low_count": scan_status.low_count,
                "info_count": scan_status.info_count,
                "spider_progress": scan_status.spider_progress,
                "passive_progress": scan_status.passive_progress,
                "active_progress": scan_status.active_progress,
                "ajax_progress": scan_status.ajax_progress,
                "start_time": scan_status.start_time,
                "end_time": scan_status.end_time,
                "duration_seconds": scan_status.duration_seconds,
                "phase": scan_status.phase,
                "urls_found": scan_status.urls_found,
                "alerts_found": scan_status.alerts_found,
                "current_operation": scan_status.current_operation,
                "error_count": scan_status.error_count,
                "warning_count": scan_status.warning_count
            }
            
            return jsonify(progress_data)
        else:
            # Return default progress data when no scan is running
            return jsonify({
                "status": "Not Started",
                "progress": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "info_count": 0,
                "spider_progress": 0,
                "passive_progress": 0,
                "active_progress": 0,
                "ajax_progress": 0,
                "start_time": None,
                "end_time": None,
                "duration_seconds": None,
                "phase": "Not Started",
                "urls_found": 0,
                "alerts_found": 0,
                "current_operation": "",
                "error_count": 0,
                "warning_count": 0
            })
            
    except Exception as e:
        logger.error(f"Error getting ZAP scan progress: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "progress": 0
        }), 500


# GPT4All/Requirements routes
@gpt4all_bp.route("/<string:model>/<int:app_num>", methods=["GET", "POST"])
def gpt4all_analysis(model: str, app_num: int):
    """Requirements analysis page for a specific app."""
    try:
        # Get app configuration
        app_config = get_app_config_by_model_and_number(model, app_num)
        if not app_config:
            flash(f"App {model}/{app_num} not found", "error")
            return redirect(url_for("main.index"))
        
        # Check if OpenRouter analyzer is available
        openrouter_analyzer = getattr(current_app, 'openrouter_analyzer', None)
        print(f"[DEBUG] routes.py - openrouter_analyzer: {openrouter_analyzer}")
        print(f"[DEBUG] routes.py - openrouter_analyzer type: {type(openrouter_analyzer)}")
        if openrouter_analyzer:
            print(f"[DEBUG] routes.py - calling is_api_available()...")
            api_available = openrouter_analyzer.is_api_available()
            print(f"[DEBUG] routes.py - is_api_available result: {api_available}")
        else:
            print(f"[DEBUG] routes.py - openrouter_analyzer is None")
        
        # Load existing JSON results
        json_results = load_json_results_for_template(model, app_num, 'gpt4all')
        available_analyses = get_available_analysis_results(model, app_num)
        latest_timestamp = get_latest_analysis_timestamp(model, app_num)
        
        # Process GPT4All results if available
        existing_results = None
        if 'gpt4all' in json_results:
            existing_results = json_results['gpt4all']
        
        # Get requirements for display
        requirements = []
        template_name = f"App {app_num}"
        available_models = []
        if openrouter_analyzer:
            try:
                requirements, template_name = openrouter_analyzer.get_requirements_for_app(app_num)
                available_models = openrouter_analyzer.get_available_models()
            except Exception as e:
                logger.error(f"Error getting requirements: {e}")
                requirements = ["Error loading requirements"]
        
        # Handle POST request for analysis
        if request.method == 'POST':
            try:
                # Get analysis parameters
                check_requirements = request.form.get('check_requirements') == 'true'
                openrouter_model = request.form.get('openrouter_model', 'mistralai/mistral-small-3.2-24b-instruct:free')
                
                if check_requirements and openrouter_analyzer:
                    # Run requirements analysis
                    results = openrouter_analyzer.check_requirements(model, app_num, selected_model=openrouter_model)
                    
                    return render_template("requirements.html", 
                                         model=model, 
                                         app_num=app_num, 
                                         app_config=app_config,
                                         requirements=requirements,
                                         template_name=template_name,
                                         available_models=available_models,
                                         results=results,
                                         selected_model=openrouter_model,
                                         json_results=json_results,
                                         available_analyses=available_analyses,
                                         latest_timestamp=latest_timestamp,
                                         openrouter_analyzer_available=True)
                else:
                    flash("Requirements analysis not available", "error")
                    
            except Exception as e:
                logger.error(f"Error running requirements analysis: {e}")
                return render_template("requirements.html", 
                                     model=model, 
                                     app_num=app_num, 
                                     app_config=app_config,
                                     requirements=requirements,
                                     template_name=template_name,
                                     available_models=available_models,
                                     error=str(e),
                                     json_results=json_results,
                                     available_analyses=available_analyses,
                                     latest_timestamp=latest_timestamp,
                                     openrouter_analyzer_available=openrouter_analyzer is not None)
        
        # GET request - show the analysis page
        return render_template("requirements.html", 
                             model=model, 
                             app_num=app_num, 
                             app_config=app_config,
                             requirements=requirements,
                             template_name=template_name,
                             available_models=available_models,
                             json_results=json_results,
                             available_analyses=available_analyses,
                             latest_timestamp=latest_timestamp,
                             openrouter_analyzer_available=openrouter_analyzer is not None)
                             
    except Exception as e:
        logger.error(f"Error loading requirements analysis page: {e}")
        flash(f"Error loading requirements analysis page: {e}", "error")
        return redirect(url_for("main.index"))


@gpt4all_bp.route("/models", methods=["GET"])
def get_models():
    """Get available OpenRouter models."""
    try:
        openrouter_analyzer = getattr(current_app, 'openrouter_analyzer', None)
        if not openrouter_analyzer:
            return jsonify({
                "status": "error",
                "message": "OpenRouter analyzer not available"
            }), 503
        
        models = openrouter_analyzer.get_available_models()
        return jsonify({
            "status": "success",
            "models": models
        })
        
    except Exception as e:
        logger.error(f"Error getting OpenRouter models: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@gpt4all_bp.route("/server-status", methods=["GET"])
def server_status():
    """Check OpenRouter server status."""
    try:
        openrouter_analyzer = getattr(current_app, 'openrouter_analyzer', None)
        if not openrouter_analyzer:
            return jsonify({
                "available": False,
                "message": "OpenRouter analyzer not available"
            })
        
        status = openrouter_analyzer.check_server_status()
        return jsonify({
            "available": status,
            "message": "OpenRouter API is available" if status else "OpenRouter API is not available"
        })
        
    except Exception as e:
        logger.error(f"Error checking OpenRouter server status: {e}")
        return jsonify({
            "available": False,
            "message": str(e)
        })


# Cache management API endpoints
@api_bp.route("/cache/stats")
def cache_stats():
    """Get cache statistics."""
    try:
        stats = get_cache_stats()
        return create_api_response(success=True, data=stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return create_api_response(success=False, error=str(e), code=500)


@api_bp.route("/cache/clear", methods=["POST"])
def clear_cache():
    """Clear container cache."""
    try:
        model = request.json.get('model') if request.json else None
        app_num = request.json.get('app_num') if request.json else None
        
        clear_container_cache(model, app_num)
        
        if model and app_num:
            message = f"Cache cleared for {model}/app{app_num}"
        else:
            message = "All cache cleared"
            
        return create_api_response(success=True, message=message)
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return create_api_response(success=False, error=str(e), code=500)


@api_bp.route("/cache/warm", methods=["POST"])
def warm_cache():
    """Warm up the container cache."""
    try:
        docker_manager = get_docker_manager()
        
        # Get current apps from request context
        all_apps = get_all_apps()
        
        # Use the safe cache warming method
        success = warm_container_cache_safe(all_apps, docker_manager)
        
        if success:
            return create_api_response(success=True, message="Cache warming initiated")
        else:
            return create_api_response(success=False, message="Failed to warm cache")
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        return create_api_response(success=False, error=str(e), code=500)


# Quality Analysis routes
@quality_bp.route("/<string:model>/<int:app_num>")
def analyze_quality(model: str, app_num: int):
    """Code quality analysis page for a specific app."""
    try:
        # Get app configuration
        app_config = get_app_config_by_model_and_number(model, app_num)
        if not app_config:
            flash(f"App {model}/{app_num} not found", "error")
            return redirect(url_for("main.index"))
        
        # Load existing JSON results
        json_results = load_json_results_for_template(model, app_num, analysis_type="quality")
        available_analyses = get_available_analysis_results(model, app_num)
        latest_timestamp = get_latest_analysis_timestamp(model, app_num)
        
        # Filter for quality-specific results
        quality_results = {}
        if json_results:
            if 'backend_quality' in json_results:
                quality_results['backend_quality'] = json_results['backend_quality']
            if 'frontend_quality' in json_results:
                quality_results['frontend_quality'] = json_results['frontend_quality']
        
        # Check if analyzers are available
        backend_analyzer = getattr(current_app, 'backend_quality_analyzer', None)
        frontend_analyzer = getattr(current_app, 'frontend_quality_analyzer', None)
        
        return render_template("quality_analysis.html", 
                             model=model, 
                             app_num=app_num, 
                             app_config=app_config,
                             backend_analyzer_available=backend_analyzer is not None,
                             frontend_analyzer_available=frontend_analyzer is not None,
                             json_results=quality_results,
                             available_analyses=available_analyses,
                             latest_timestamp=latest_timestamp)
    except Exception as e:
        logger.error(f"Error loading quality analysis page: {e}")
        flash(f"Error loading quality analysis page: {e}", "error")
        return redirect(url_for("main.index"))


@quality_bp.route("/<string:model>/<int:app_num>/run", methods=["POST"])
def run_quality_analysis(model: str, app_num: int):
    """Run code quality analysis on a specific app."""
    try:
        analysis_type = request.form.get('analysis_type', 'both')
        use_all_tools = request.form.get('use_all_tools') == 'on'
        force_rerun = request.form.get('force_rerun') == 'on'
        
        results = {}
        
        if analysis_type in ['backend', 'both']:
            backend_analyzer = getattr(current_app, 'backend_quality_analyzer', None)
            if backend_analyzer:
                try:
                    issues, tool_status, tool_outputs = backend_analyzer.run_quality_analysis(
                        model, app_num, use_all_tools=use_all_tools, force_rerun=force_rerun
                    )
                    results['backend'] = {
                        'issues': issues,
                        'tool_status': tool_status,
                        'tool_outputs': tool_outputs
                    }
                except Exception as e:
                    logger.error(f"Backend quality analysis failed: {e}")
                    results['backend'] = {'error': str(e)}
        
        if analysis_type in ['frontend', 'both']:
            frontend_analyzer = getattr(current_app, 'frontend_quality_analyzer', None)
            if frontend_analyzer:
                try:
                    issues, tool_status, tool_outputs = frontend_analyzer.run_quality_analysis(
                        model, app_num, use_all_tools=use_all_tools, force_rerun=force_rerun
                    )
                    results['frontend'] = {
                        'issues': issues,
                        'tool_status': tool_status,
                        'tool_outputs': tool_outputs
                    }
                except Exception as e:
                    logger.error(f"Frontend quality analysis failed: {e}")
                    results['frontend'] = {'error': str(e)}
        
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify(results)
        else:
            # For form submissions, redirect back with flash message
            if any('error' in result for result in results.values()):
                flash("Quality analysis completed with some errors. Check the results below.", "warning")
            else:
                flash("Quality analysis completed successfully!", "success")
            
            return render_template("quality_analysis_results.html", 
                                 model=model, 
                                 app_num=app_num, 
                                 results=results)
                                 
    except Exception as e:
        logger.error(f"Error running quality analysis: {e}")
        flash(f"Error running quality analysis: {e}", "error")
        return redirect(url_for("quality.analyze_quality", model=model, app_num=app_num))


# Generation Content routes
@generation_bp.route('/')
def generation_index():
    """Main generation content page showing all generation runs."""
    try:
        if not generation_lookup_service:
            return render_template('generation/error.html', 
                                 error="Generation lookup service not available")
        
        # Get list of generation runs
        runs = generation_lookup_service.list_generation_runs()
        
        return render_template('generation/index.html', 
                             generation_runs=runs,
                             total_runs=len(runs))
    
    except Exception as e:
        logger.error(f"Error in generation index: {e}")
        return render_template('generation/error.html', 
                             error=f"Failed to load generation runs: {e}")


@generation_bp.route('/run/<timestamp>')
def generation_view_run(timestamp: str):
    """View details of a specific generation run."""
    try:
        if not generation_lookup_service:
            abort(503, "Generation lookup service not available")
        
        # Get generation details
        details = generation_lookup_service.get_generation_details(timestamp)
        if not details:
            abort(404, "Generation run not found")
        
        # Get performance summary
        performance = generation_lookup_service.get_model_performance_summary(timestamp)
        
        return render_template('generation/run_details.html',
                             timestamp=timestamp,
                             details=details,
                             performance=performance)
    
    except Exception as e:
        logger.error(f"Error viewing generation run {timestamp}: {e}")
        abort(500, f"Error loading generation run: {e}")


@generation_bp.route('/model/<timestamp>/<path:model>/<int:app_num>')
def generation_view_model_app(timestamp: str, model: str, app_num: int):
    """View details of a specific model-app combination from generation."""
    try:
        if not generation_lookup_service:
            abort(503, "Generation lookup service not available")
        
        # Get model app details
        details = generation_lookup_service.get_model_app_details(timestamp, model, app_num)
        if not details:
            abort(404, "Model-app combination not found")
        
        return render_template('generation/model_app_details.html',
                             timestamp=timestamp,
                             model=model,
                             app_num=app_num,
                             details=details)
    
    except Exception as e:
        logger.error(f"Error viewing model app {model}/{app_num}: {e}")
        abort(500, f"Error loading model app details: {e}")


@generation_bp.route('/file/<path:file_path>')
def generation_view_file(file_path: str):
    """View content of a generated file."""
    try:
        if not generation_lookup_service:
            abort(503, "Generation lookup service not available")
        
        # Get file content
        content = generation_lookup_service.get_file_content(file_path)
        if content is None:
            abort(404, "File not found")
        
        # Determine if it's a markdown file
        is_markdown = file_path.endswith('.md')
        
        # Get file extension for syntax highlighting
        file_ext = Path(file_path).suffix.lower()
        
        return render_template('generation/file_viewer.html',
                             file_path=file_path,
                             content=content,
                             is_markdown=is_markdown,
                             file_extension=file_ext)
    
    except Exception as e:
        logger.error(f"Error viewing file {file_path}: {e}")
        abort(500, f"Error loading file: {e}")


@generation_bp.route('/api/runs')
def generation_api_list_runs():
    """API endpoint to list generation runs."""
    try:
        if not generation_lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        runs = generation_lookup_service.list_generation_runs()
        return jsonify({
            "runs": [
                {
                    "timestamp": run.timestamp,
                    "filename": run.filename,
                    "models_count": run.models_count,
                    "apps_count": run.apps_count,
                    "total_successful": run.total_successful,
                    "total_failed": run.total_failed,
                    "generation_time": run.generation_time,
                    "fastest_model": run.fastest_model,
                    "slowest_model": run.slowest_model
                }
                for run in runs
            ]
        })
    
    except Exception as e:
        logger.error(f"Error in API list runs: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/run/<timestamp>')
def generation_api_get_run(timestamp: str):
    """API endpoint to get generation run details."""
    try:
        if not generation_lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        details = generation_lookup_service.get_generation_details(timestamp)
        if not details:
            return jsonify({"error": "Run not found"}), 404
        
        return jsonify(details)
    
    except Exception as e:
        logger.error(f"Error in API get run: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/search')
def generation_api_search():
    """API endpoint to search generations."""
    try:
        if not generation_lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        # Get query parameters
        model_filter = request.args.get('model')
        app_filter = request.args.get('app', type=int)
        success_only = request.args.get('success_only', 'false').lower() == 'true'
        
        results = generation_lookup_service.search_generations(
            model_filter=model_filter,
            app_filter=app_filter,
            success_only=success_only
        )
        
        return jsonify({
            "results": [
                {
                    "timestamp": timestamp,
                    "model": model,
                    "app_num": app_num,
                    "success": success
                }
                for timestamp, model, app_num, success in results
            ]
        })
    
    except Exception as e:
        logger.error(f"Error in API search: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/file/<path:file_path>')
def generation_api_get_file(file_path: str):
    """API endpoint to get file content."""
    try:
        if not generation_lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        content = generation_lookup_service.get_file_content(file_path)
        if content is None:
            return jsonify({"error": "File not found"}), 404
        
        return Response(content, mimetype='text/plain')
    
    except Exception as e:
        logger.error(f"Error in API get file: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/stats')
def generation_api_get_stats():
    """API endpoint to get overall generation statistics."""
    try:
        if not generation_lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        runs = generation_lookup_service.list_generation_runs()
        
        # Calculate overall statistics
        total_runs = len(runs)
        total_models = sum(run.models_count for run in runs)
        total_apps = sum(run.apps_count for run in runs)
        total_successful = sum(run.total_successful for run in runs)
        total_failed = sum(run.total_failed for run in runs)
        
        avg_generation_time = sum(run.generation_time for run in runs) / max(total_runs, 1)
        
        return jsonify({
            "total_runs": total_runs,
            "total_models": total_models,
            "total_apps": total_apps,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "success_rate": total_successful / max(total_successful + total_failed, 1) * 100,
            "avg_generation_time": avg_generation_time,
            "latest_run": runs[0].timestamp if runs else None
        })
    
    except Exception as e:
        logger.error(f"Error in API get stats: {e}")
        return jsonify({"error": str(e)}), 500


# Error handlers for generation blueprint
@generation_bp.errorhandler(404)
def generation_not_found(error):
    """Handle 404 errors in generation routes."""
    return render_template('generation/error.html', 
                         error="The requested resource was not found"), 404


@generation_bp.errorhandler(500)
def generation_internal_error(error):
    """Handle 500 errors in generation routes."""
    return render_template('generation/error.html', 
                         error="An internal server error occurred"), 500


@generation_bp.errorhandler(503)
def generation_service_unavailable(error):
    """Handle 503 errors in generation routes."""
    return render_template('generation/error.html', 
                         error="Generation lookup service is currently unavailable"), 503