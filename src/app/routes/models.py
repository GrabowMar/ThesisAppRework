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
from ..utils.helpers import deep_merge_dicts, dicts_to_csv
from datetime import timedelta
from pathlib import Path
from ..models import PortConfiguration  # type: ignore[attr-defined]
from ..services import application_service as app_service

# Set up logger
logger = logging.getLogger(__name__)

models_bp = Blueprint('models', __name__, url_prefix='/models')

# Initialize OpenRouter service
openrouter_service = OpenRouterService()

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


@models_bp.app_template_filter('abbreviate_number')
def abbreviate_number_filter(value):
    """Format large integers as human-readable abbreviations (e.g., 1.2K, 3.4M).

    Accepts int/float/str; returns the input unchanged if it can't be parsed as a number.
    """
    try:
        num = float(value or 0)
    except (ValueError, TypeError):
        return value

    sign = '-' if num < 0 else ''
    n = abs(num)
    for threshold, suffix in ((1_000_000_000_000, 'T'), (1_000_000_000, 'B'), (1_000_000, 'M'), (1_000, 'K')):
        if n >= threshold:
            val = n / threshold
            # Trim trailing .0
            s = f"{val:.1f}"
            if s.endswith('.0'):
                s = s[:-2]
            return f"{sign}{s}{suffix}"
    # For small numbers, keep as int if close to integer
    if n.is_integer():
        return f"{int(num)}"
    return f"{num:.2f}"

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
        available_providers = [
            {'id': prov, 'name': (prov or '').title()}
            for prov in providers
        ]
        
        total_models = len(models)
        free_models = sum(1 for m in models if m.is_free)
        paid_models = total_models - free_models
        
        # Calculate average cost (simplified)
        avg_cost = 0.001  # Default placeholder for now
        
        # Page context with models_stats structure expected by template
        models_stats = {
            'total_models': total_models,
            'active_models': total_models,  # For now, assume all are active
            'unique_providers': len(providers),
            'avg_cost_per_1k': avg_cost
        }
        
        context = {
            'models': enriched_models,
            'models_stats': models_stats,
            'providers': providers,
            'available_providers': available_providers,
            'total_models': total_models,
            'providers_count': len(providers),
            'free_models': free_models,
            'paid_models': paid_models,
            'page_title': 'AI Models Overview',
            'show_openrouter_data': bool(openrouter_service.api_key)
        }
        return render_template('views/models/overview.html', **context)
            
    except Exception as e:
        logger.error(f"Error loading models overview: {e}")
        flash(f"Error loading models: {e}", "error")
        # Use the proper error template structure
        return render_template(
            'partials/common/error.html',
            error=str(e),
            page_title='Models Overview Error'
        ), 500


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
    """HTMX endpoint: external details (OpenRouter) for modal display."""
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
                entry.source_notes = 'openrouter'
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

        return render_template(
            'partials/models/more_info_modal_body.html',
            model=payload,
            model_slug=model_slug
        )
    except Exception as e:
        logger.error(f"Error loading more info for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error: {str(e)}</div>'


@models_bp.route('/import')
def models_import_page():
    """Render a simple import page to upload JSON and call the API."""
    try:
        return render_template('views/models/import.html')
    except Exception as e:
        logger.error(f"Error rendering models import page: {e}")
        return render_template(
            'single_page.html',
            page_title='Models Import Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Import Page Error',
            error_message=str(e)
        ), 500


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
                'pricing_request': data.get('openrouter_pricing_request'),
                'pricing_image': data.get('openrouter_pricing_image'),
                'pricing_web_search': data.get('openrouter_pricing_web_search'),
                'pricing_internal_reasoning': data.get('openrouter_pricing_internal_reasoning'),
                'pricing_input_cache_read': data.get('openrouter_pricing_input_cache_read'),
                'pricing_input_cache_write': data.get('openrouter_pricing_input_cache_write'),
                'modality': data.get('architecture_modality'),
                'input_modalities': '|'.join(data.get('architecture_input_modalities') or []) if isinstance(data.get('architecture_input_modalities'), list) else data.get('architecture_input_modalities'),
                'output_modalities': '|'.join(data.get('architecture_output_modalities') or []) if isinstance(data.get('architecture_output_modalities'), list) else data.get('architecture_output_modalities'),
                'tokenizer': data.get('architecture_tokenizer'),
                'instruct_type': data.get('architecture_instruct_type'),
                'supported_parameters': '|'.join(data.get('openrouter_supported_parameters') or []) if isinstance(data.get('openrouter_supported_parameters'), list) else data.get('openrouter_supported_parameters'),
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
        # Build port map from database (PortConfiguration)
        port_map = {}
        try:
            for pc in db.session.query(PortConfiguration).all():
                key = (pc.model, pc.app_num)
                port_map[key] = {
                    'backend': pc.backend_port,
                    'frontend': pc.frontend_port,
                }
        except Exception as e:
            logger.warning(f"Failed to load PortConfiguration from DB: {e}")
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
                ports = port_map.get((model.canonical_slug, i))
                app_data = {
                    'id': app.id if app else None,
                    'app_number': i,
                    'exists': bool(app),
                    'status': app.container_status if app else 'not_created',
                    'app_type': app.app_type if app else 'unknown',
                    'has_backend': app.has_backend if app else False,
                    'has_frontend': app.has_frontend if app else False,
                    'has_docker_compose': app.has_docker_compose if app else False,
                    'generation_status': app.generation_status if app else 'pending',
                    'ports': ports
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

        # Build additional context expected by template
        # 1) Flatten applications list for simple counts and UI badges
        applications_list = []
        for entry in application_grid:
            for app in entry['apps']:
                if app.get('exists'):
                    applications_list.append({
                        'model_slug': entry['model'].canonical_slug,
                        'app_number': app.get('app_number'),
                        'status': app.get('status'),
                        'id': app.get('id')
                    })

        # 2) Available models for filter dropdown (slug + display name)
        available_models = [
            {
                'slug': m.canonical_slug,
                'display_name': getattr(m, 'display_name', None) or m.model_name or m.canonical_slug
            }
            for m in models
        ]

        # 3) Stats block for header cards
        try:
            analyzed_count = db.session.query(SecurityAnalysis).count()
        except Exception:
            analyzed_count = 0

        stats = {
            'total_applications': total_apps,
            'running_applications': running_containers,
            'analyzed_applications': analyzed_count,
            'unique_models': len(models)
        }

        context = {
            'application_grid': application_grid,
            'total_apps': total_apps,
            'running_containers': running_containers,
            'stopped_containers': stopped_containers,
            'total_models': len(models),
            'providers': providers,
            # New/normalized keys expected by the template
            'applications': applications_list,
            'total_count': total_apps,
            'available_models': available_models,
            'stats': stats,
            'current_filters': {
                'model': model_filter,
                'provider': provider_filter,
                'search': search_filter
            }
        }
        return render_template('views/applications/index.html', **context)
            
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
        
        app_path = Path('misc/models') / model_slug / f'app{app_number}'
        files_info = {
            'app_exists': app_path.exists(),
            'docker_compose': (app_path / 'docker-compose.yml').exists(),
            'backend_files': [],
            'frontend_files': [],
            'other_files': []
        }
        code_stats = {
            'total_files': 0,
            'total_loc': 0,
            'by_language': {}
        }
        artifacts = {
            'project_index': (app_path / 'PROJECT_INDEX.md') if app_path.exists() else None,
            'readme': (app_path / 'README.md') if app_path.exists() else None,
            'compose_path': (app_path / 'docker-compose.yml') if app_path.exists() else None,
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
                    # Basic LOC calculation
                    ext = item.suffix.lower()
                    lang_map = {
                        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
                        '.tsx': 'TypeScript', '.jsx': 'JavaScript', '.html': 'HTML',
                        '.css': 'CSS', '.md': 'Markdown', '.json': 'JSON', '.yml': 'YAML', '.yaml': 'YAML'
                    }
                    lang = lang_map.get(ext, 'Other')
                    try:
                        text = item.read_text(encoding='utf-8', errors='ignore')
                        loc = text.count('\n') + 1 if text else 0
                    except Exception:
                        loc = 0
                    code_stats['total_files'] += 1
                    code_stats['total_loc'] += loc
                    entry = code_stats['by_language'].setdefault(lang, {'files': 0, 'loc': 0})
                    entry['files'] += 1
                    entry['loc'] += loc
        
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

        # Resolve ports from database PortConfiguration
        ports = None
        try:
            pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_number).first()
            if pc:
                ports = {'backend': pc.backend_port, 'frontend': pc.frontend_port}
        except Exception as e:
            logger.warning(f"Failed to query PortConfiguration for {model_slug}/app{app_number}: {e}")

        # Prompt templates for this app number
        prompts = {'backend': '', 'frontend': ''}
        # Initialize with empty strings to satisfy static typing (later populated with filenames)
        template_files = {'backend_file': '', 'frontend_file': ''}
        try:
            tmpl_dir = Path('misc/app_templates')
            backend_md = sorted(tmpl_dir.glob(f'app_{app_number}_backend_*.md'))
            frontend_md = sorted(tmpl_dir.glob(f'app_{app_number}_frontend_*.md'))
            if backend_md:
                template_files['backend_file'] = backend_md[0].name
                prompts['backend'] = backend_md[0].read_text(encoding='utf-8', errors='ignore')
            if frontend_md:
                template_files['frontend_file'] = frontend_md[0].name
                prompts['frontend'] = frontend_md[0].read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"Failed to load prompts for app {app_number}: {e}")
        
        # Build 'application' object expected by the template
        # Map statuses to the simplified set used in UI
        def _map_status(app_obj) -> str:
            if not app_obj:
                return 'not_created'
            c = getattr(app_obj, 'container_status', None) or ''
            g = str(getattr(app_obj, 'generation_status', '') or '').lower()
            if c == 'running':
                return 'running'
            if g in {'completed', 'success', 'generated'}:
                return 'completed'
            if c == 'error' or g == 'failed':
                return 'failed'
            return 'pending'

        # Flatten analyses into a simple list for the template (optional)
        flat_analyses = []
        try:
            for a in analyses.get('security', []) or []:
                flat_analyses.append({
                    'id': getattr(a, 'id', None),
                    'analysis_type': 'security',
                    'status': getattr(a, 'status', 'completed') or 'completed',
                    'created_at': getattr(a, 'created_at', None),
                    'overall_score': getattr(a, 'overall_score', None)
                })
            for a in analyses.get('performance', []) or []:
                flat_analyses.append({
                    'id': getattr(a, 'id', None),
                    'analysis_type': 'performance',
                    'status': getattr(a, 'status', 'completed') or 'completed',
                    'created_at': getattr(a, 'created_at', None),
                    'overall_score': getattr(a, 'overall_score', None)
                })
            for a in analyses.get('zap', []) or []:
                flat_analyses.append({
                    'id': getattr(a, 'id', None),
                    'analysis_type': 'dynamic',
                    'status': getattr(a, 'status', 'completed') or 'completed',
                    'created_at': getattr(a, 'created_at', None),
                    'overall_score': getattr(a, 'overall_score', None)
                })
            for a in analyses.get('openrouter', []) or []:
                flat_analyses.append({
                    'id': getattr(a, 'id', None),
                    'analysis_type': 'openrouter',
                    'status': getattr(a, 'status', 'completed') or 'completed',
                    'created_at': getattr(a, 'created_at', None),
                    'overall_score': getattr(a, 'overall_score', None)
                })
        except Exception:
            flat_analyses = []

        application = {
            'id': getattr(app, 'id', None) if app else None,
            'model_slug': model_slug,
            'app_number': app_number,
            'status': _map_status(app),
            'created_at': getattr(app, 'created_at', None) if app else None,
            'backend_port': (ports or {}).get('backend') if isinstance(ports, dict) else None,
            'frontend_port': (ports or {}).get('frontend') if isinstance(ports, dict) else None,
            'is_running': (getattr(app, 'container_status', None) == 'running') if app else False,
            'last_started': None,
            'file_count': code_stats.get('total_files', 0),
            'total_size': None,
            'environment_variables': {},
            'analyses': flat_analyses,
            'generation_log': None,
            'versions': [],
        }

        return render_template(
            'views/applications/detail.html',
            application=application,
            app_data=app_data,
            files_info=files_info,
            analyses=analyses,
            stats=stats,
            model=model,
            ports=ports,
            code_stats=code_stats,
            prompts=prompts,
            template_files=template_files,
            artifacts=artifacts
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


def _collect_app_context(model_slug: str, app_number: int):
    """Internal helper to rebuild the detail context for section routes."""
    # Reuse logic from application_detail compactly
    app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
    model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
    app_data = {
        'model_slug': model_slug,
        'app_number': app_number,
        'exists_in_db': bool(app),
        'app_type': getattr(app, 'app_type', 'unknown') if app else 'unknown',
        'provider': getattr(app, 'provider', None) if app else None,
        'generation_status': getattr(app, 'generation_status', 'pending') if app else 'pending',
        'container_status': getattr(app, 'container_status', 'not_created') if app else 'not_created',
        'has_backend': getattr(app, 'has_backend', False) if app else False,
        'has_frontend': getattr(app, 'has_frontend', False) if app else False,
        'has_docker_compose': getattr(app, 'has_docker_compose', False) if app else False,
        'backend_framework': getattr(app, 'backend_framework', None) if app else None,
        'frontend_framework': getattr(app, 'frontend_framework', None) if app else None,
        'created_at': getattr(app, 'created_at', None) if app else None,
        'metadata': app.get_metadata() if app and hasattr(app, 'get_metadata') else {}
    }

    app_path = Path('misc/models') / model_slug / f'app{app_number}'
    ignore_dirs = {'.mypy_cache', '.pytest_cache', '__pycache__', 'node_modules', '.venv', '.git'}
    files_info = {'app_exists': app_path.exists(), 'docker_compose': (app_path / 'docker-compose.yml').exists(), 'backend_files': [], 'frontend_files': [], 'other_files': []}
    code_stats = {'total_files': 0, 'total_loc': 0, 'by_language': {}}
    artifacts = {
        'project_index': (app_path / 'PROJECT_INDEX.md') if app_path.exists() else None,
        'readme': (app_path / 'README.md') if app_path.exists() else None,
        'compose_path': (app_path / 'docker-compose.yml') if app_path.exists() else None,
    }
    if app_path.exists():
        for item in app_path.rglob('*'):
            # Skip ignored directories (cross-platform)
            try:
                parts = set(item.relative_to(app_path).parts)
            except Exception:
                parts = set()
            if any(p in ignore_dirs for p in parts):
                continue
            if item.is_file():
                rel_path = item.relative_to(app_path)
                file_info = {'name': item.name, 'path': str(rel_path), 'size': item.stat().st_size, 'modified': item.stat().st_mtime}
                lower = str(rel_path).lower()
                if 'backend' in lower:
                    files_info['backend_files'].append(file_info)
                elif 'frontend' in lower:
                    files_info['frontend_files'].append(file_info)
                else:
                    files_info['other_files'].append(file_info)
                # stats
                ext = item.suffix.lower()
                lang = {
                    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'TypeScript',
                    '.jsx': 'JavaScript', '.html': 'HTML', '.css': 'CSS', '.md': 'Markdown', '.json': 'JSON', '.yml': 'YAML', '.yaml': 'YAML'
                }.get(ext, 'Other')
                try:
                    text = item.read_text(encoding='utf-8', errors='ignore')
                    loc = text.count('\n') + 1 if text else 0
                except Exception:
                    loc = 0
                code_stats['total_files'] += 1
                code_stats['total_loc'] += loc
                entry = code_stats['by_language'].setdefault(lang, {'files': 0, 'loc': 0})
                entry['files'] += 1
                entry['loc'] += loc

    # analyses and stats
    analyses = {'security': [], 'performance': [], 'zap': [], 'openrouter': []}
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
        stats = {
            'total_security_analyses': len(analyses['security']),
            'total_performance_tests': len(analyses['performance']),
            'total_zap_analyses': len(analyses['zap']),
            'total_openrouter_analyses': len(analyses['openrouter'])
        }

    # ports
    ports = None
    try:
        pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_number).first()
        if pc:
            ports = {'backend': pc.backend_port, 'frontend': pc.frontend_port}
    except Exception as e:
        logger.warning(f"Failed to query PortConfiguration for {model_slug}/app{app_number}: {e}")

    # prompts + template files
    prompts = {'backend': '', 'frontend': ''}
    # Initialize with empty strings to satisfy static typing (later populated with filenames)
    template_files = {'backend_file': '', 'frontend_file': ''}
    try:
        tmpl_dir = Path('misc/app_templates')
        backend_md = sorted(tmpl_dir.glob(f'app_{app_number}_backend_*.md'))
        frontend_md = sorted(tmpl_dir.glob(f'app_{app_number}_frontend_*.md'))
        if backend_md:
            template_files['backend_file'] = backend_md[0].name
            prompts['backend'] = backend_md[0].read_text(encoding='utf-8', errors='ignore')
        if frontend_md:
            template_files['frontend_file'] = frontend_md[0].name
            prompts['frontend'] = frontend_md[0].read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Failed to load prompts for app {app_number}: {e}")

    return {
        'app_data': app_data,
        'model': model,
        'files_info': files_info,
        'code_stats': code_stats,
        'analyses': analyses,
        'stats': stats,
        'ports': ports,
        'prompts': prompts,
        'template_files': template_files,
        'artifacts': artifacts,
    }


@models_bp.route('/application/<model_slug>/<int:app_number>/section/<string:section>')
def application_detail_section(model_slug, app_number, section):
    """Data-on-demand partials for the application detail page."""
    try:
        ctx = _collect_app_context(model_slug, app_number)
        template_map = {
            'overview': 'partials/applications/sections/overview.html',
            'prompts': 'partials/applications/sections/prompts.html',
            'files': 'partials/applications/sections/files.html',
            'ports': 'partials/applications/sections/ports.html',
            'container': 'partials/applications/sections/container.html',
            'analyses': 'partials/applications/sections/analyses.html',
            'metadata': 'partials/applications/sections/metadata.html',
            'artifacts': 'partials/applications/sections/artifacts.html',
            'logs': 'partials/application_logs.html',
        }
        template = template_map.get(section)
        if not template:
            return f'<div class="alert alert-warning">Unknown section: {section}</div>', 404

        # For logs, reuse existing API template expected context
        if section == 'logs':
            fake_app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
            logs = [
                {'timestamp': '—', 'level': 'INFO', 'message': 'No logs available'}
            ]
            return render_template(template, app=fake_app, logs=logs)

        return render_template(template, **ctx)
    except Exception as e:
        logger.error(f"Error loading section {section} for {model_slug}/app{app_number}: {e}")
        return f'<div class="alert alert-danger">Error loading section: {str(e)}</div>', 500


@models_bp.route('/application/<model_slug>/<int:app_number>/export.csv')
def export_application_csv(model_slug, app_number):
    """Export a single application's file inventory and metadata as CSV."""
    try:
        # Load database app and ports
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        ports = {'backend': None, 'frontend': None}
        try:
            pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_number).first()
            if pc:
                ports = {'backend': pc.backend_port, 'frontend': pc.frontend_port}
        except Exception as e:
            logger.warning(f"PortConfiguration lookup failed for {model_slug}/app{app_number}: {e}")

        # Scan filesystem files under misc/models
        app_path = Path('misc/models') / model_slug / f'app{app_number}'
        rows = []
        def add_row(kind: str, info: dict):
            rows.append({
                'model_slug': model_slug,
                'app_number': app_number,
                'file_kind': kind,
                'path': info.get('path'),
                'size_bytes': info.get('size'),
                'modified_ts': info.get('modified'),
                'backend_port': ports['backend'],
                'frontend_port': ports['frontend'],
                'exists_in_db': bool(app),
                'has_backend': getattr(app, 'has_backend', False) if app else False,
                'has_frontend': getattr(app, 'has_frontend', False) if app else False,
                'generation_status': getattr(app, 'generation_status', 'pending') if app else 'pending',
                'container_status': getattr(app, 'container_status', 'not_created') if app else 'not_created',
            })

        if app_path.exists():
            # Mime scan replicate from application_detail
            for item in app_path.rglob('*'):
                if not item.is_file():
                    continue
                rel_path = item.relative_to(app_path)
                info = {
                    'path': str(rel_path),
                    'size': item.stat().st_size,
                    'modified': item.stat().st_mtime,
                }
                lower = str(rel_path).lower()
                if 'backend' in lower:
                    add_row('backend', info)
                elif 'frontend' in lower:
                    add_row('frontend', info)
                else:
                    add_row('other', info)

        csv_content = dicts_to_csv(rows, fieldnames=(list(rows[0].keys()) if rows else [
            'model_slug','app_number','file_kind','path','size_bytes','modified_ts','backend_port','frontend_port','exists_in_db','has_backend','has_frontend','generation_status','container_status'
        ]))
        filename = f"{model_slug}_app{app_number}_files.csv"
        return Response(csv_content, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})
    except Exception as e:
        logger.error(f"Error exporting application CSV for {model_slug}/app{app_number}: {e}")
    return Response('model_slug,app_number\n', mimetype='text/csv')


@models_bp.route('/application/<model_slug>/<int:app_number>/file')
def application_file_preview(model_slug, app_number):
    """Preview a file from the generated application directory (safe, size-limited)."""
    try:
        rel_path = request.args.get('path')
        if not rel_path:
            return '<div class="alert alert-warning">Missing path</div>', 400

        base = Path('misc/models') / model_slug / f'app{app_number}'
        # Normalize and ensure the target is inside base
        target = (base / rel_path).resolve()
        if not str(target).startswith(str(base.resolve())):
            return '<div class="alert alert-danger">Invalid path</div>', 400
        if not target.exists() or not target.is_file():
            return '<div class="alert alert-warning">File not found</div>', 404

        # Read with size cap
        size = target.stat().st_size
        max_bytes = 200 * 1024  # 200 KB
        truncated = False
        content = ''
        try:
            if size <= max_bytes:
                content = target.read_text(encoding='utf-8', errors='replace')
            else:
                with target.open('rb') as f:
                    data = f.read(max_bytes)
                content = data.decode('utf-8', errors='replace')
                truncated = True
        except Exception as e:
            content = f"<binary or unreadable content: {e}>"

        return render_template(
            'partials/applications/file_preview.html',
            file={
                'rel_path': str(Path(rel_path)),
                'abs_path': str(target),
                'size': size,
            },
            content=content,
            truncated=truncated
        )
    except Exception as e:
        logger.error(f"Error previewing file for {model_slug}/app{app_number}: {e}")
        return f'<div class="alert alert-danger">Error: {str(e)}</div>', 500


@models_bp.route('/applications/generate', methods=['POST'])
def generate_application():
    """HTMX endpoint: Generate a new application record for a given model/app number.

    Accepts form-encoded fields:
      - model_slug (required)
      - app_number (required, int)
      - app_type (optional; defaults to 'web_app')
      - generation_prompt (optional; ignored for now)
      - auto_start (optional; 'on' -> attempt to mark running)

    Returns a small HTML alert snippet suitable for hx-target swap.
    """
    try:
        model_slug = (request.form.get('model_slug') or '').strip()
        app_number_raw = request.form.get('app_number')
        app_type = (request.form.get('app_type') or 'web_app').strip() or 'web_app'
        auto_start = request.form.get('auto_start') == 'on'
        # generation_prompt and auto_analyze not used in this minimal handler

        if not model_slug or not app_number_raw:
            return (
                '<div class="alert alert-danger">Model and app number are required.</div>',
                400,
            )
        try:
            app_number = int(app_number_raw)
        except Exception:
            return (
                '<div class="alert alert-danger">Invalid app number.</div>',
                400,
            )

        # Look up provider from the selected model
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return (
                f'<div class="alert alert-danger">Unknown model: {model_slug}</div>',
                404,
            )

        payload = {
            'model_slug': model_slug,
            'app_number': app_number,
            'app_type': app_type,
            'provider': model.provider,
        }

        # Create application via service
        created = app_service.create_application(payload)

        # Optionally mark as running (best-effort; no docker integration here)
        if auto_start and created.get('id'):
            try:
                app_service.start_application(created['id'])
            except Exception:
                pass

        detail_url = f"{request.url_root.rstrip('/')}/models/application/{model_slug}/{app_number}"
        # Return success alert and trigger a lightweight grid refresh for the Applications page
        resp = Response(
            '<div class="alert alert-success">'
            f'Successfully created application for <strong>{model_slug}</strong> '
            f'(<a href="{detail_url}" target="_blank">open details</a>).</div>'
        )
        resp.headers['HX-Trigger'] = 'refresh-grid'
        return resp
    except app_service.ValidationError as ve:
        return (f'<div class="alert alert-danger">{str(ve)}</div>', 400)
    except Exception as e:  # noqa: BLE001
        # Handle common unique constraint errors gracefully
        msg = str(e)
        if 'unique' in msg.lower() and 'model' in msg.lower():
            return (
                '<div class="alert alert-warning">An application for this model and number already exists.</div>',
                409,
            )
        logger.error(f"Error generating application: {e}")
        return (
            f'<div class="alert alert-danger">Error generating application: {str(e)}</div>',
            500,
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
            main_partial='partials/overview.html',  # reuse existing apps overview partial
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



