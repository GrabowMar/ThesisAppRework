"""
Models Routes
============

Routes for managing AI models and their generated applications.
"""

import logging

from flask import Blueprint, render_template, request, flash, Response

from ..models import (
    ModelCapability, GeneratedApplication,
    SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis,
    ExternalModelInfoCache
)
from ..extensions import db
from ..services.openrouter_service import OpenRouterService
from ..services.huggingface_service import HuggingFaceService
from ..utils.helpers import deep_merge_dicts, dicts_to_csv
from datetime import timedelta

# Set up logger
logger = logging.getLogger(__name__)

models_bp = Blueprint('models', __name__, url_prefix='/models')

# Initialize OpenRouter service
openrouter_service = OpenRouterService()
hf_service = HuggingFaceService()

# Provider color mapping for templates
PROVIDER_COLORS = {
    'anthropic': '#D97706',
    'openai': '#14B8A6', 
    'google': '#3B82F6',
    'deepseek': '#9333EA',
    'mistralai': '#8B5CF6',
    'qwen': '#F43F5E',
    'minimax': '#7E22CE',
    'x-ai': '#B91C1C',
    'moonshotai': '#10B981',
    'nvidia': '#0D9488',
    'nousresearch': '#059669'
}

def get_provider_color(provider):
    """Get color for a provider."""
    return PROVIDER_COLORS.get(provider, '#666666')


@models_bp.app_template_global('get_provider_color')
def template_get_provider_color(provider):
    """Template global function for getting provider colors."""
    return get_provider_color(provider)


@models_bp.route('/')
def models_overview():
    """Static models overview page showing table of AI models with OpenRouter data."""
    try:
        # Get all models from database
        models = ModelCapability.query.order_by(
            ModelCapability.provider, 
            ModelCapability.model_name
        ).all()
        
        # Enrich models with OpenRouter data
        enriched_models = []
        for model in models:
            enriched_data = openrouter_service.enrich_model_data(model)
            # Add computed stats
            app_count = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug).count()
            enriched_data['apps_count'] = app_count
            enriched_models.append(enriched_data)
        
        # Get summary statistics
        providers = db.session.query(ModelCapability.provider.distinct()).all()
        providers = [p[0] for p in providers if p[0]]
        
        total_models = len(models)
        free_models = sum(1 for m in models if m.is_free)
        paid_models = total_models - free_models
        
        # Page context
        context = {
            'models': enriched_models,
            'total_models': total_models,
            'providers': providers,
            'providers_count': len(providers),
            'free_models': free_models,
            'paid_models': paid_models,
            'page_title': 'AI Models Overview',
            'show_openrouter_data': bool(openrouter_service.api_key)
        }
        return render_template('pages/models.html', **context)
            
    except Exception as e:
        logger.error(f"Error loading models overview: {e}")
        flash(f"Error loading models: {e}", "error")
        return render_template(
            'single_page.html',
            page_title='Models Overview Error',
            main_partial='partials/common/error.html',
            error=str(e),
            models=[], total_models=0, providers=[], providers_count=0
        )


@models_bp.route('/model/<model_slug>/details')
def model_details(model_slug):
    """Detailed view of a specific model with comprehensive OpenRouter data."""
    try:
        # Get model from database
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        
        # Enrich with OpenRouter data
        enriched_data = openrouter_service.enrich_model_data(model)
        
        # Get related statistics
        total_apps = GeneratedApplication.query.filter_by(model_slug=model_slug).count()
        analyses_count = (
            SecurityAnalysis.query.join(GeneratedApplication)
            .filter(GeneratedApplication.model_slug == model_slug)
            .count()
        )
        
        # Additional context
        enriched_data.update({
            'total_apps': total_apps,
            'analyses_count': analyses_count,
        })
        
        return render_template(
            'single_page.html',
            page_title=f"Model: {enriched_data.get('model_name', model_slug)}",
            page_icon='fas fa-robot',
            main_partial='partials/models/details.html',
            model=enriched_data
        )
        
    except Exception as e:
        logger.error(f"Error loading model details for {model_slug}: {e}")
        flash(f"Error loading model details: {e}", "error")
        return render_template(
            'single_page.html',
            page_title='Model Not Found',
            main_partial='partials/common/error.html',
            error_code=404,
            error_title='Model Not Found',
            error_message=f"Model '{model_slug}' not found"
        )


@models_bp.route('/model/<model_slug>/more-info')
def model_more_info(model_slug):
    """HTMX endpoint: external details (OpenRouter+HuggingFace) for modal display."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()

        # Cache settings and refresh flag
        ttl_hours = int(request.args.get('ttl', 6))
        force_refresh = request.args.get('refresh') == '1'

        cached = None
        if not force_refresh:
            cached = ExternalModelInfoCache.query.filter_by(model_slug=model_slug).first()
            if cached and cached.is_expired():
                cached = None

        if cached is None or force_refresh:
            data = openrouter_service.enrich_model_data(model)
            # Merge HF enrichment (best-effort)
            try:
                hf_data = hf_service.enrich_model_data(model.provider, model.model_name)
                if hf_data:
                    data = deep_merge_dicts(data, hf_data)
            except Exception as e:
                logger.warning(f"HF enrich failed for {model_slug}: {e}")

            # Upsert cache
            try:
                entry = ExternalModelInfoCache.query.filter_by(model_slug=model_slug).first()
                if not entry:
                    entry = ExternalModelInfoCache()
                    entry.model_slug = model_slug
                    entry.set_data(data)
                    db.session.add(entry)
                else:
                    entry.set_data(data)
                # set expiry
                from ..models import utc_now
                entry.cache_expires_at = utc_now() + timedelta(hours=ttl_hours)
                entry.source_notes = 'openrouter+hf'
                db.session.commit()
            except Exception as e:
                logger.warning(f"Failed to persist external cache for {model_slug}: {e}")

            payload = data
        else:
            payload = cached.get_data()

        # Inject live counts (do not persist to cache)
        try:
            app_count = GeneratedApplication.query.filter_by(model_slug=model_slug).count()
            sec_count = (
                SecurityAnalysis.query.join(GeneratedApplication)
                .filter(GeneratedApplication.model_slug == model_slug)
                .count()
            )
            payload['apps_count'] = app_count
            payload['analyses_count'] = sec_count
        except Exception as e:
            logger.warning(f"Failed to compute live counts for {model_slug}: {e}")

        return render_template('partials/models/more_info_modal_body.html', model=payload, model_slug=model_slug)
    except Exception as e:
        logger.error(f"Error loading more info for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error: {str(e)}</div>'


@models_bp.route('/export/models.csv')
def export_models_csv():
    """Export models overview to CSV with selected fields including OpenRouter/HF when available."""
    try:
        rows = []
        models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
        for m in models:
            data = openrouter_service.enrich_model_data(m)
            # best-effort merge cached external info
            cached = ExternalModelInfoCache.query.filter_by(model_slug=m.canonical_slug).first()
            if cached:
                data = deep_merge_dicts(data, cached.get_data())
            rows.append({
                'provider': m.provider,
                'model_name': m.model_name,
                'slug': m.canonical_slug,
                'context_window': data.get('openrouter_context_length') or m.context_window,
                'prompt_price': data.get('openrouter_prompt_price'),
                'completion_price': data.get('openrouter_completion_price'),
                'modality': data.get('architecture_modality'),
                'hf_repo': data.get('hf_repo_id'),
                'hf_likes': data.get('hf_likes'),
                'hf_downloads': data.get('hf_downloads'),
                'is_free': m.is_free,
            })

        csv_content = dicts_to_csv(rows, fieldnames=(list(rows[0].keys()) if rows else ['provider','model_name','slug']))
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=models_export.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting models CSV: {e}")
        return Response('provider,model_name,slug\n', mimetype='text/csv')


@models_bp.route('/applications')
def applications():
    """Applications overview page with grid layout and container management."""
    try:
        # Get filter parameters
        model_filter = request.args.get('model')
        provider_filter = request.args.get('provider')
        search_filter = request.args.get('search')
        
        # Get all models to create app grid
        models_query = ModelCapability.query.order_by(
            ModelCapability.provider, 
            ModelCapability.model_name
        )
        
        # Apply filters
        if provider_filter:
            models_query = models_query.filter(ModelCapability.provider == provider_filter)
        
        if model_filter:
            models_query = models_query.filter(
                ModelCapability.canonical_slug.contains(model_filter) |
                ModelCapability.model_name.contains(model_filter)
            )
            
        if search_filter:
            models_query = models_query.filter(
                ModelCapability.model_name.contains(search_filter) |
                ModelCapability.provider.contains(search_filter)
            )
        
        models = models_query.all()
        
        # Build application grid data
        application_grid = []
        total_apps = 0
        running_containers = 0
        stopped_containers = 0
        
        for model in models:
            # Get apps for this model
            apps = GeneratedApplication.query.filter_by(
                model_slug=model.canonical_slug
            ).all()
            
            model_apps = []
            for i in range(1, 31):  # Apps 1-30
                app = next((a for a in apps if a.app_number == i), None)
                app_data = {
                    'app_number': i,
                    'exists': bool(app),
                    'status': app.container_status if app else 'not_created',
                    'app_type': app.app_type if app else 'unknown',
                    'has_backend': app.has_backend if app else False,
                    'has_frontend': app.has_frontend if app else False,
                    'has_docker_compose': app.has_docker_compose if app else False,
                    'generation_status': app.generation_status if app else 'pending'
                }
                model_apps.append(app_data)
                
                if app:
                    total_apps += 1
                    if app.container_status == 'running':
                        running_containers += 1
                    else:
                        stopped_containers += 1
            
            application_grid.append({
                'model': model,
                'apps': model_apps,
                'apps_count': len([a for a in model_apps if a['exists']])
            })
        
        # Get filter options
        providers = db.session.query(ModelCapability.provider.distinct()).all()
        providers = [p[0] for p in providers if p[0]]
        
        context = {
            'application_grid': application_grid,
            'total_apps': total_apps,
            'running_containers': running_containers,
            'stopped_containers': stopped_containers,
            'total_models': len(models),
            'providers': providers,
            'current_filters': {
                'model': model_filter,
                'provider': provider_filter,
                'search': search_filter
            }
        }
        return render_template('pages/applications.html', **context)
            
    except Exception as e:
        logger.error(f"Error loading applications: {e}")
        flash(f"Error loading applications: {e}", "error")
        return render_template(
            'single_page.html',
            page_title='Applications Error',
            main_partial='partials/common/error.html',
            application_grid=[], total_apps=0,
            running_containers=0, stopped_containers=0,
            current_filters={}, providers=[], error=str(e)
        )


@models_bp.route('/application/<model_slug>/<int:app_number>')
def application_detail(model_slug, app_number):
    """Detailed view of a specific application with files, generation info, and container management."""
    try:
        # Get the application
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug, 
            app_number=app_number
        ).first()
        
        # Get the model
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        
        # If app doesn't exist in database, create a placeholder
        if not app:
            app_data = {
                'model_slug': model_slug,
                'app_number': app_number,
                'exists_in_db': False,
                'status': 'not_created',
                'app_type': 'unknown',
                'has_backend': False,
                'has_frontend': False,
                'has_docker_compose': False,
                'generation_status': 'pending',
                'container_status': 'not_created'
            }
        else:
            app_data = {
                'id': app.id,
                'model_slug': app.model_slug,
                'app_number': app.app_number,
                'exists_in_db': True,
                'app_type': app.app_type,
                'provider': app.provider,
                'generation_status': app.generation_status,
                'container_status': app.container_status,
                'has_backend': app.has_backend,
                'has_frontend': app.has_frontend,
                'has_docker_compose': app.has_docker_compose,
                'backend_framework': app.backend_framework,
                'frontend_framework': app.frontend_framework,
                'created_at': app.created_at,
                'metadata': app.get_metadata() if hasattr(app, 'get_metadata') else {}
            }
        
        # Remove unused import
        from pathlib import Path
        
        app_path = Path('misc/models') / model_slug / f'app{app_number}'
        files_info = {
            'app_exists': app_path.exists(),
            'docker_compose': (app_path / 'docker-compose.yml').exists(),
            'backend_files': [],
            'frontend_files': [],
            'other_files': []
        }
        
        if app_path.exists():
            # Scan for files
            for item in app_path.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(app_path)
                    file_info = {
                        'name': item.name,
                        'path': str(rel_path),
                        'size': item.stat().st_size,
                        'modified': item.stat().st_mtime
                    }
                    
                    if 'backend' in str(rel_path).lower():
                        files_info['backend_files'].append(file_info)
                    elif 'frontend' in str(rel_path).lower():
                        files_info['frontend_files'].append(file_info)
                    else:
                        files_info['other_files'].append(file_info)
        
        # Get analysis history if app exists in DB
        analyses = {}
        stats = {
            'total_security_analyses': 0,
            'total_performance_tests': 0,
            'total_zap_analyses': 0,
            'total_openrouter_analyses': 0
        }
        
        if app:
            analyses = {
                'security': SecurityAnalysis.query.filter_by(application_id=app.id).order_by(SecurityAnalysis.created_at.desc()).all(),
                'performance': PerformanceTest.query.filter_by(application_id=app.id).order_by(PerformanceTest.created_at.desc()).all(),
                'zap': ZAPAnalysis.query.filter_by(application_id=app.id).order_by(ZAPAnalysis.created_at.desc()).all(),
                'openrouter': OpenRouterAnalysis.query.filter_by(application_id=app.id).order_by(OpenRouterAnalysis.created_at.desc()).all()
            }
            
            # Calculate statistics
            stats = {
                'total_security_analyses': len(analyses['security']),
                'total_performance_tests': len(analyses['performance']),
                'total_zap_analyses': len(analyses['zap']),
                'total_openrouter_analyses': len(analyses['openrouter'])
            }
        
        return render_template(
            'single_page.html',
            page_title=f"Application {app_number}",
            page_icon='fas fa-cube',
            main_partial='partials/applications/detail.html',
            app_data=app_data,
            files_info=files_info,
            analyses=analyses,
            stats=stats,
            model=model
        )
        
    except Exception as e:
        logger.error(f"Error loading application details for {model_slug}/app{app_number}: {e}")
        flash(f"Error loading application details: {e}", "error")
        return render_template(
            'single_page.html',
            page_title='Application Not Found',
            main_partial='partials/common/error.html',
            error_code=404,
            error_title='Application Not Found',
            error_message=f"Application '{model_slug}/app{app_number}' not found"
        )


@models_bp.route('/model_actions/<model_slug>')
@models_bp.route('/model_actions')  # Support both with and without model_slug
def model_actions(model_slug=None):
    """HTMX endpoint for model actions modal content."""
    try:
        if model_slug:
            # Specific model actions
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
            
            # Get related statistics
            app_count = GeneratedApplication.query.filter_by(model_slug=model_slug).count()
            security_count = db.session.query(SecurityAnalysis).join(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug
            ).count()
            performance_count = db.session.query(PerformanceTest).join(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug
            ).count()
            
            return render_template(
                'partials/model_actions.html',
                model=model,
                stats={
                    'applications': app_count,
                    'security_tests': security_count,
                    'performance_tests': performance_count
                }
            )
        else:
            # Bulk operations view
            return render_template('partials/bulk_operations.html')
            
    except Exception as e:
        logger.error(f"Error loading model actions for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error loading model actions: {str(e)}</div>'


@models_bp.route('/model_apps/<model_slug>')
def model_apps(model_slug):
    """View applications for a specific model."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        
        return render_template(
            'single_page.html',
            page_title=f"{model.display_name} Applications",
            page_icon='fa-cubes',
            page_subtitle=f"All generated apps for {model.display_name}",
            main_partial='partials/applications/overview.html',  # reuse existing apps overview partial
            model=model,
            apps=apps
        )
    except Exception as e:
        logger.error(f"Error loading model apps for {model_slug}: {e}")
        flash(f'Error loading applications: {str(e)}', 'error')
        return render_template(
            'single_page.html',
            page_title='Error',
            page_icon='fa-triangle-exclamation',
            page_subtitle='Model Applications Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Model Applications Error',
            error_message=str(e),
            python_version='3.11'
        )



