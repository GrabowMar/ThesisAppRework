"""
Advanced routes for Apps Grid and Models Overview pages.
Handles HTMX requests, filtering, pagination, and dynamic content loading.
"""

from flask import Blueprint, render_template, request, jsonify, abort
from sqlalchemy import and_, or_, func, desc
import json
import os
from datetime import datetime
import docker.errors
import logging

from ..models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis, 
    PerformanceTest, ZAPAnalysis, PortConfiguration
)
from ..extensions import db

# Create blueprint
advanced = Blueprint('advanced', __name__, url_prefix='/advanced')
logger = logging.getLogger(__name__)

# Apps Grid Page Routes
@advanced.route('/apps')
def apps_grid():
    """Main apps grid page."""
    return render_template('pages/apps_grid.html')

@advanced.route('/models')
def models_overview():
    """Main models overview page."""
    return render_template('pages/models_overview.html')

# API Routes for Apps Grid
@advanced.route('/api/apps/grid')
def api_apps_grid():
    """Get applications grid data with filtering and pagination."""
    try:
        # Get filter parameters
        search = request.args.get('search', '').strip()
        model_filter = request.args.get('model', '')
        status_filter = request.args.get('status', '')
        type_filter = request.args.get('type', '')
        view_mode = request.args.get('view', 'grid')
        # Remove unused variables
        # page = int(request.args.get('page', 1))
        # per_page = int(request.args.get('per_page', 24))

        # Base query
        query = GeneratedApplication.query

        # Apply filters
        if search:
            search_terms = search.split()
            for term in search_terms:
                query = query.filter(
                    or_(
                        GeneratedApplication.model_slug.ilike(f'%{term}%'),
                        GeneratedApplication.provider.ilike(f'%{term}%'),
                        GeneratedApplication.app_type.ilike(f'%{term}%')
                    )
                )

        if model_filter:
            if model_filter in ['anthropic', 'openai', 'google', 'deepseek', 'mistralai']:
                query = query.filter(GeneratedApplication.provider == model_filter)
            else:
                query = query.filter(GeneratedApplication.model_slug.ilike(f'%{model_filter}%'))

        if status_filter:
            query = query.filter(GeneratedApplication.container_status == status_filter)

        if type_filter:
            query = query.filter(GeneratedApplication.app_type == type_filter)

        # Get results
        apps = query.order_by(
            GeneratedApplication.provider,
            GeneratedApplication.model_slug,
            GeneratedApplication.app_number
        ).all()

        # Enhance with container status and port information
        enhanced_apps = []
        for app in apps:
            app_data = {
                'id': f"{app.model_slug}_app{app.app_number}",
                'model_slug': app.model_slug,
                'provider': app.provider,
                'app_number': app.app_number,
                'app_type': app.app_type or 'Unknown',
                'container_status': get_container_status(app),
                'ports': get_app_ports(app),
                'stats': get_app_stats(app),
                'last_analyzed': get_last_analysis_time(app),
                'analysis_count': get_analysis_count(app),
                'created_at': app.created_at.isoformat() if app.created_at else None,
                'file_stats': get_file_stats(app)
            }
            enhanced_apps.append(app_data)

        # Render appropriate view
        if view_mode == 'list':
            return render_template('partials/apps_grid/apps_list.html', apps=enhanced_apps)
        elif view_mode == 'compact':
            return render_template('partials/apps_grid/apps_compact.html', apps=enhanced_apps)
        else:
            return render_template('partials/apps_grid/apps_grid.html', apps=enhanced_apps)

    except Exception as e:
        logger.error(f"Error in apps grid API: {str(e)}")
        return render_template('partials/common/error.html', 
                             error="Failed to load applications"), 500

@advanced.route('/api/apps/<app_id>/details')
def api_app_details(app_id):
    """Get detailed information about a specific application."""
    try:
        # Parse app_id (format: model_slug_appN)
        parts = app_id.rsplit('_app', 1)
        if len(parts) != 2:
            abort(400, "Invalid app ID format")
        
        model_slug = parts[0]
        app_number = int(parts[1])

        # Get application
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()

        if not app:
            abort(404, "Application not found")

        # Get comprehensive details
        details = {
            'app': app,
            'container_status': get_container_status(app),
            'ports': get_app_ports(app),
            'logs': [],  # get_container_logs(app),
            'file_structure': {},  # get_file_structure(app),
            'analyses': [],  # get_app_analyses(app),
            'performance_tests': [],  # get_app_performance_tests(app),
            'docker_info': {}  # get_docker_info(app)
        }

        return render_template('partials/apps_grid/app_details.html', **details)

    except Exception as e:
        logger.error(f"Error getting app details for {app_id}: {str(e)}")
        return render_template('partials/common/error.html', 
                             error="Failed to load application details"), 500

@advanced.route('/api/apps/<app_id>/urls')
def api_app_urls(app_id):
    """Get application URLs if containers are running."""
    try:
        parts = app_id.rsplit('_app', 1)
        if len(parts) != 2:
            return jsonify({'error': 'Invalid app ID format'}), 400
        
        model_slug = parts[0]
        app_number = int(parts[1])

        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()

        if not app:
            return jsonify({'error': 'Application not found'}), 404

        ports = get_app_ports(app)
        status = get_container_status(app)

        if status == 'running':
            return jsonify({
                'frontend_url': f"http://localhost:{ports.get('frontend')}" if ports.get('frontend') else None,
                'backend_url': f"http://localhost:{ports.get('backend')}" if ports.get('backend') else None,
                'status': 'running'
            })
        else:
            return jsonify({
                'frontend_url': None,
                'backend_url': None,
                'status': status
            })

    except Exception as e:
        logger.error(f"Error getting app URLs for {app_id}: {str(e)}")
        return jsonify({'error': 'Failed to get application URLs'}), 500

@advanced.route('/api/containers/bulk-action', methods=['POST'])
def api_bulk_container_action():
    """Execute bulk container actions (start, stop, restart)."""
    try:
        data = request.get_json()
        action = data.get('action')
        app_ids = data.get('app_ids', [])

        if action not in ['start', 'stop', 'restart']:
            return jsonify({'error': 'Invalid action'}), 400

        if not app_ids:
            return jsonify({'error': 'No applications selected'}), 400

        results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        docker_client = docker.from_env()

        for app_id in app_ids:
            try:
                # Parse app_id
                parts = app_id.rsplit('_app', 1)
                if len(parts) != 2:
                    results['errors'].append(f"Invalid app ID: {app_id}")
                    results['failed'] += 1
                    continue

                model_slug = parts[0]
                app_number = int(parts[1])

                # Execute action
                if execute_container_action(docker_client, model_slug, app_number, action):
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to {action} {app_id}")

            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error with {app_id}: {str(e)}")

        return jsonify({
            'success': True,
            **results
        })

    except Exception as e:
        logger.error(f"Error in bulk container action: {str(e)}")
        return jsonify({'error': 'Bulk action failed'}), 500

@advanced.route('/api/analysis/configuration', methods=['POST'])
def api_analysis_configuration():
    """Get analysis configuration form for selected applications."""
    try:
        data = request.get_json()
        app_ids = data.get('app_ids', [])

        if not app_ids:
            return render_template('partials/common/error.html', 
                                 error="No applications selected"), 400

        # Get application details for configuration
        apps = []
        for app_id in app_ids:
            parts = app_id.rsplit('_app', 1)
            if len(parts) == 2:
                model_slug = parts[0]
                app_number = int(parts[1])
                app = GeneratedApplication.query.filter_by(
                    model_slug=model_slug,
                    app_number=app_number
                ).first()
                if app:
                    apps.append(app)

        return render_template('partials/apps_grid/analysis_config.html', 
                             apps=apps, app_ids=app_ids)

    except Exception as e:
        logger.error(f"Error loading analysis configuration: {str(e)}")
        return render_template('partials/common/error.html', 
                             error="Failed to load analysis configuration"), 500

@advanced.route('/api/analysis/start', methods=['POST'])
def api_start_analysis():
    """Start analysis for selected applications."""
    try:
        data = request.get_json()
        app_ids = data.get('app_ids', [])
        analysis_types = data.get('analysis_types', [])
        
        if not app_ids or not analysis_types:
            return jsonify({'error': 'Missing app IDs or analysis types'}), 400

        # Start analysis for each app
        started_count = 0
        for app_id in app_ids:
            parts = app_id.rsplit('_app', 1)
            if len(parts) == 2:
                model_slug = parts[0]
                app_number = int(parts[1])
                
                for analysis_type in analysis_types:
                    if start_app_analysis(model_slug, app_number, analysis_type):
                        started_count += 1

        return jsonify({
            'success': True,
            'app_count': len(app_ids),
            'analyses_started': started_count
        })

    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}")
        return jsonify({'error': 'Failed to start analysis'}), 500

# API Routes for Models Overview
@advanced.route('/api/models/stats/active')
def api_models_stats_active():
    """Get number of active models."""
    try:
        # For now, assume all models are active. This could be enhanced with a status field
        count = ModelCapability.query.count()
        return f"<span class='counter' data-target='{count}'>{count}</span>"
    except Exception as e:
        logger.error(f"Error getting active models count: {str(e)}")
        return "Error"

@advanced.route('/api/models/stats/performance')
def api_models_stats_performance():
    """Get average performance score."""
    try:
        avg_score = db.session.query(func.avg(ModelCapability.cost_efficiency)).scalar()
        if avg_score:
            return f"<span class='counter' data-target='{avg_score:.1f}'>{avg_score:.1f}</span>"
        return "N/A"
    except Exception as e:
        logger.error(f"Error getting performance average: {str(e)}")
        return "Error"

@advanced.route('/api/models/stats/last-updated')
def api_models_stats_last_updated():
    """Get time since last model update."""
    try:
        latest = db.session.query(func.max(ModelCapability.updated_at)).scalar()
        if latest:
            delta = datetime.utcnow() - latest
            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h ago"
            else:
                return f"{delta.seconds // 60}m ago"
        return "Never"
    except Exception as e:
        logger.error(f"Error getting last update time: {str(e)}")
        return "Error"

@advanced.route('/api/models/display')
def api_models_display():
    """Get models display with filtering and pagination."""
    try:
        # Get filter parameters
        search = request.args.get('search', '').strip()
        provider = request.args.get('provider', '')
        capabilities = request.args.getlist('capabilities')
        cost = request.args.get('cost', '')
        sort_by = request.args.get('sort', 'name')
        group_by = request.args.get('groupBy', '')
        view_mode = request.args.get('viewMode', 'cards')
        page_size = request.args.get('pageSize', '24')
        page = int(request.args.get('page', 1))

        # Base query
        query = ModelCapability.query

        # Apply filters
        if search:
            search_terms = search.split()
            for term in search_terms:
                query = query.filter(
                    or_(
                        ModelCapability.model_name.ilike(f'%{term}%'),
                        ModelCapability.provider.ilike(f'%{term}%'),
                        ModelCapability.capabilities_json.ilike(f'%{term}%')
                    )
                )

        if provider:
            query = query.filter(ModelCapability.provider == provider)

        if capabilities:
            for capability in capabilities:
                query = query.filter(ModelCapability.capabilities_json.ilike(f'%{capability}%'))

        if cost:
            if cost == 'free':
                query = query.filter(
                    and_(
                        ModelCapability.input_price_per_token == 0,
                        ModelCapability.output_price_per_token == 0
                    )
                )
            elif cost == 'low':
                query = query.filter(
                    or_(
                        ModelCapability.input_price_per_token <= 0.01,
                        ModelCapability.output_price_per_token <= 0.01
                    )
                )
            elif cost == 'medium':
                query = query.filter(
                    and_(
                        ModelCapability.input_price_per_token > 0.01,
                        ModelCapability.input_price_per_token <= 0.1
                    )
                )
            elif cost == 'high':
                query = query.filter(ModelCapability.input_price_per_token > 0.1)

        # Apply sorting
        if sort_by == 'name':
            query = query.order_by(ModelCapability.model_name)
        elif sort_by == 'provider':
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        elif sort_by == 'created_at':
            query = query.order_by(desc(ModelCapability.created_at))
        elif sort_by == 'performance':
            query = query.order_by(desc(ModelCapability.cost_efficiency))
        elif sort_by == 'cost':
            query = query.order_by(ModelCapability.input_price_per_token)

        # Get results
        if page_size == 'all':
            models = query.all()
            total = len(models)
        else:
            page_size = int(page_size)
            pagination = query.paginate(
                page=page, per_page=page_size, error_out=False
            )
            models = pagination.items
            total = pagination.total

        # Group models if requested
        if group_by:
            grouped_models = group_models_by(models, group_by)
            template = f'partials/models/models_{view_mode}_grouped.html'
            return render_template(template, 
                                 grouped_models=grouped_models, 
                                 total=total)
        else:
            template = f'partials/models/models_{view_mode}.html'
            return render_template(template, 
                                 models=models, 
                                 total=total,
                                 page=page,
                                 page_size=page_size if page_size != 'all' else len(models))

    except Exception as e:
        logger.error(f"Error in models display API: {str(e)}")
        return render_template('partials/common/error.html', 
                             error="Failed to load models"), 500

@advanced.route('/api/models/<int:model_id>/details')
def api_model_details(model_id):
    """Get detailed information about a specific model."""
    try:
        model = ModelCapability.query.get_or_404(model_id)
        
        # Get related applications
        apps = GeneratedApplication.query.filter_by(
            model_slug=model.model_slug
        ).all()

        # Get analysis statistics
        analysis_stats = get_model_analysis_stats(model)

        details = {
            'model': model,
            'applications': apps,
            'analysis_stats': analysis_stats,
            'capabilities_parsed': parse_capabilities(model.capabilities),
            'provider_info': get_provider_info(model.provider)
        }

        return render_template('partials/model_details.html', **details)

    except Exception as e:
        logger.error(f"Error getting model details for {model_id}: {str(e)}")
        return render_template('partials/error.html', 
                             error="Failed to load model details"), 500

# Helper Functions
def get_container_status(app):
    """Get current container status for an application."""
    try:
        import docker
        docker_client = docker.from_env()
        container_name = f"{app.model_slug}_app{app.app_number}"
        
        containers = docker_client.containers.list(
            all=True, 
            filters={'name': container_name}
        )
        
        if containers:
            container = containers[0]
            return container.status
        else:
            return 'stopped'
            
    except Exception as e:
        logger.warning(f"Error getting container status: {str(e)}")
        return 'unknown'

def get_app_ports(app):
    """Get port configuration for an application."""
    try:
        port_config = PortConfiguration.query.filter_by(
            model_name=app.model_slug,
            app_number=app.app_number
        ).first()

        if port_config:
            return {
                'frontend': port_config.frontend_port,
                'backend': port_config.backend_port
            }
        else:
            # Fallback to reading from misc/port_config.json
            return get_ports_from_config(app.model_slug, app.app_number)
            
    except Exception as e:
        logger.warning(f"Error getting app ports: {str(e)}")
        return {'frontend': None, 'backend': None}

def get_ports_from_config(model_slug, app_number):
    """Get ports from misc/port_config.json as fallback."""
    try:
        config_path = os.path.join('misc', 'port_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            key = f"{model_slug}_{app_number}"
            if key in config:
                return config[key]
                
        return {'frontend': None, 'backend': None}
        
    except Exception as e:
        logger.warning(f"Error reading port config: {str(e)}")
        return {'frontend': None, 'backend': None}

def get_app_stats(app):
    """Get application statistics."""
    try:
        stats = {
            'security_analyses': SecurityAnalysis.query.filter_by(
                model_slug=app.model_slug,
                app_number=app.app_number
            ).count(),
            'performance_tests': PerformanceTest.query.filter_by(
                model_slug=app.model_slug,
                app_number=app.app_number
            ).count(),
            'zap_scans': ZAPAnalysis.query.filter_by(
                model_slug=app.model_slug,
                app_number=app.app_number
            ).count(),
            'last_test': get_last_test_date(app)
        }
        return stats
        
    except Exception as e:
        logger.warning(f"Error getting app stats: {str(e)}")
        return {}

def get_last_analysis_time(app):
    """Get the most recent analysis time for an application."""
    try:
        latest_security = db.session.query(func.max(SecurityAnalysis.created_at)).filter_by(
            model_slug=app.model_slug,
            app_number=app.app_number
        ).scalar()
        
        latest_performance = db.session.query(func.max(PerformanceTest.created_at)).filter_by(
            model_slug=app.model_slug,
            app_number=app.app_number
        ).scalar()
        
        latest_zap = db.session.query(func.max(ZAPAnalysis.created_at)).filter_by(
            model_slug=app.model_slug,
            app_number=app.app_number
        ).scalar()

        times = [t for t in [latest_security, latest_performance, latest_zap] if t]
        
        if times:
            return max(times)
        return None
        
    except Exception as e:
        logger.warning(f"Error getting last analysis time: {str(e)}")
        return None

def get_analysis_count(app):
    """Get total analysis count for an application."""
    try:
        security_count = SecurityAnalysis.query.filter_by(
            model_slug=app.model_slug,
            app_number=app.app_number
        ).count()
        
        performance_count = PerformanceTest.query.filter_by(
            model_slug=app.model_slug,
            app_number=app.app_number
        ).count()
        
        zap_count = ZAPAnalysis.query.filter_by(
            model_slug=app.model_slug,
            app_number=app.app_number
        ).count()

        return security_count + performance_count + zap_count
        
    except Exception as e:
        logger.warning(f"Error getting analysis count: {str(e)}")
        return 0

def get_file_stats(app):
    """Get file statistics for an application."""
    try:
        app_path = os.path.join('misc', 'models', app.model_slug, f'app{app.app_number}')
        
        if not os.path.exists(app_path):
            return {'files': 0, 'size': 0}
            
        file_count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(app_path):
            file_count += len(files)
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                except OSError:
                    continue
                    
        return {
            'files': file_count,
            'size': total_size,
            'size_mb': round(total_size / (1024 * 1024), 2)
        }
        
    except Exception as e:
        logger.warning(f"Error getting file stats: {str(e)}")
        return {'files': 0, 'size': 0, 'size_mb': 0}

def execute_container_action(docker_client, model_slug, app_number, action):
    """Execute a container action (start, stop, restart)."""
    try:
        container_name = f"{model_slug}_app{app_number}"
        
        if action == 'start':
            # First check if container exists
            try:
                container = docker_client.containers.get(container_name)
                if container.status != 'running':
                    container.start()
                return True
            except docker.errors.NotFound:
                # Container doesn't exist, need to build it
                return build_and_start_container(docker_client, model_slug, app_number)
                
        elif action == 'stop':
            try:
                container = docker_client.containers.get(container_name)
                if container.status == 'running':
                    container.stop()
                return True
            except docker.errors.NotFound:
                return True  # Already stopped/doesn't exist
                
        elif action == 'restart':
            try:
                container = docker_client.containers.get(container_name)
                container.restart()
                return True
            except docker.errors.NotFound:
                # Build and start if doesn't exist
                return build_and_start_container(docker_client, model_slug, app_number)
                
        return False
        
    except Exception as e:
        logger.error(f"Error executing container action {action}: {str(e)}")
        return False

def build_and_start_container(docker_client, model_slug, app_number):
    """Build and start a container for an application."""
    try:
        app_path = os.path.join('misc', 'models', model_slug, f'app{app_number}')
        
        if not os.path.exists(app_path):
            logger.error(f"Application path does not exist: {app_path}")
            return False
            
        # Check for docker-compose.yml
        compose_file = os.path.join(app_path, 'docker-compose.yml')
        if os.path.exists(compose_file):
            # Use docker-compose
            import subprocess
            result = subprocess.run(
                ['docker-compose', 'up', '-d'],
                cwd=app_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        else:
            logger.warning(f"No docker-compose.yml found in {app_path}")
            return False
            
    except Exception as e:
        logger.error(f"Error building and starting container: {str(e)}")
        return False

def start_app_analysis(model_slug, app_number, analysis_type):
    """Start analysis for an application."""
    try:
        # This would integrate with your analyzer services
        # For now, just log the request
        logger.info(f"Starting {analysis_type} analysis for {model_slug} app {app_number}")
        
        # Here you would:
        # 1. Check if containers are running
        # 2. Start appropriate analyzer service
        # 3. Create analysis record in database
        # 4. Return analysis ID
        
        return True
        
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}")
        return False

def group_models_by(models, group_by):
    """Group models by specified criteria."""
    groups = {}
    
    for model in models:
        if group_by == 'provider':
            key = model.provider
        elif group_by == 'capabilities':
            # Group by primary capability
            caps = parse_capabilities(model.capabilities)
            key = caps[0] if caps else 'Other'
        elif group_by == 'cost_tier':
            if model.cost_per_input_token == 0:
                key = 'Free'
            elif model.cost_per_input_token <= 0.01:
                key = 'Low Cost'
            elif model.cost_per_input_token <= 0.1:
                key = 'Medium Cost'
            else:
                key = 'High Cost'
        elif group_by == 'performance_tier':
            if model.performance_score >= 8:
                key = 'High Performance'
            elif model.performance_score >= 6:
                key = 'Medium Performance'
            else:
                key = 'Low Performance'
        else:
            key = 'Other'
            
        if key not in groups:
            groups[key] = []
        groups[key].append(model)
    
    return groups

def parse_capabilities(capabilities_str):
    """Parse capabilities string into list."""
    try:
        if isinstance(capabilities_str, str):
            # Try to parse as JSON first
            try:
                caps = json.loads(capabilities_str)
                if isinstance(caps, list):
                    return caps
                elif isinstance(caps, dict):
                    return [k for k, v in caps.items() if v]
            except json.JSONDecodeError:
                # Fall back to comma-separated parsing
                return [cap.strip() for cap in capabilities_str.split(',') if cap.strip()]
        return []
    except Exception as e:
        logger.warning(f"Error parsing capabilities: {str(e)}")
        return []

def get_provider_info(provider):
    """Get additional provider information."""
    provider_info = {
        'anthropic': {
            'full_name': 'Anthropic',
            'website': 'https://anthropic.com',
            'description': 'AI safety focused company'
        },
        'openai': {
            'full_name': 'OpenAI',
            'website': 'https://openai.com',
            'description': 'AI research and deployment company'
        },
        'google': {
            'full_name': 'Google',
            'website': 'https://ai.google',
            'description': 'Google AI and DeepMind'
        },
        'deepseek': {
            'full_name': 'DeepSeek',
            'website': 'https://deepseek.com',
            'description': 'AI research company'
        },
        'mistralai': {
            'full_name': 'Mistral AI',
            'website': 'https://mistral.ai',
            'description': 'Open-source AI company'
        }
    }
    
    return provider_info.get(provider, {
        'full_name': provider.title(),
        'website': '',
        'description': ''
    })

def get_model_analysis_stats(model):
    """Get analysis statistics for a model across all its applications."""
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model.model_slug).all()
        
        total_security = 0
        total_performance = 0
        total_zap = 0
        
        for app in apps:
            total_security += SecurityAnalysis.query.filter_by(
                model_slug=app.model_slug,
                app_number=app.app_number
            ).count()
            
            total_performance += PerformanceTest.query.filter_by(
                model_slug=app.model_slug,
                app_number=app.app_number
            ).count()
            
            total_zap += ZAPAnalysis.query.filter_by(
                model_slug=app.model_slug,
                app_number=app.app_number
            ).count()
        
        return {
            'security_analyses': total_security,
            'performance_tests': total_performance,
            'zap_scans': total_zap,
            'total_apps': len(apps)
        }
        
    except Exception as e:
        logger.warning(f"Error getting model analysis stats: {str(e)}")
        return {}

def get_last_test_date(app):
    """Get the last test date for an application."""
    try:
        latest = get_last_analysis_time(app)
        if latest:
            delta = datetime.utcnow() - latest
            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h ago"
            else:
                return f"{delta.seconds // 60}m ago"
        return "Never"
    except Exception as e:
        logger.warning(f"Error getting last test date: {str(e)}")
        return "Unknown"
