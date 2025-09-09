"""
Models routes for the Flask application
=======================================

Model-related web routes that render Jinja templates.
"""

import os
from datetime import timedelta
from flask import Blueprint, request, flash, current_app, Response

from app.extensions import db, deep_merge_dicts, dicts_to_csv
from sqlalchemy import or_
from app.models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest,
    PortConfiguration, ExternalModelInfoCache
)
from app.utils.generated_apps import list_generated_apps  # noqa: F401 (may be used elsewhere)
from app.utils.template_paths import render_template_compat as render_template
from app.utils.helpers import get_app_directory
from app.utils.port_resolution import resolve_ports

# Import shared utilities
from ..shared_utils import openrouter_service, _project_root


class SimplePagination:
    """Simple pagination class to provide iter_pages() method for templates."""
    
    def __init__(self, page, per_page, total, items):
        self.page = page
        self.per_page = per_page
        self.total = total
        self.items = items
        self.pages = max(1, (total + per_page - 1) // per_page)
    
    @property
    def has_prev(self):
        return self.page > 1
    
    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None
    
    @property
    def has_next(self):
        return self.page < self.pages
    
    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None
    
    def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
        """Iterate over page numbers."""
        last = self.pages
        for num in range(1, last + 1):
            if num <= left_edge or \
               (self.page - left_current - 1 < num < self.page + right_current) or \
               num > last - right_edge:
                yield num


# Create blueprint
models_bp = Blueprint('models', __name__, url_prefix='/models')

# In-process lightweight enrichment cache (simple rate limiting / TTL)
_ENRICH_CACHE: dict[str, dict] = {}
_ENRICH_TTL_SECONDS = 300  # 5 minutes

def _enrich_model(model: ModelCapability):
    """Enrich a model with OpenRouter data using a tiny time-based cache.

    Avoids hammering external API repeatedly during rapid comparison / overview refreshes.
    """
    from time import time
    key = model.canonical_slug
    now = time()
    cached = _ENRICH_CACHE.get(key)
    if cached and (now - cached.get('_ts', 0)) < _ENRICH_TTL_SECONDS:
        return cached['data']
    data = openrouter_service.enrich_model_data(model)
    _ENRICH_CACHE[key] = {'_ts': now, 'data': data}
    return data

@models_bp.route('/')
def models_overview():
    """Static models overview page showing table of AI models with OpenRouter data."""
    try:
        # Basic stats for sidebar
        try:
            total_models = ModelCapability.query.count()
            unique_providers = db.session.query(ModelCapability.provider).distinct().count()
        except Exception:
            total_models = 0
            unique_providers = 0

        models_stats = {
            'total_models': total_models,
            'active_models': total_models,  # placeholder; refine if a flag exists
            'unique_providers': unique_providers,
            'avg_cost_per_1k': 0,
        }

        # Providers for filter dropdown (optional in template)
        try:
            providers = db.session.query(ModelCapability.provider.distinct()).all()
            available_providers = [
                {'id': p[0], 'name': p[0]}
                for p in providers if p and p[0]
            ]
        except Exception:
            available_providers = []

        return render_template(
            'pages/models/overview.html',
            models_stats=models_stats,
            available_providers=available_providers,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading models overview: {e}")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Models Overview Error',
            error_message=str(e)
        ), 500

@models_bp.route('/model/<model_slug>/details')
def model_details(model_slug):
    """Detailed view of a specific model with comprehensive OpenRouter data."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        enriched_data = openrouter_service.enrich_model_data(model)

        total_apps = GeneratedApplication.query.filter_by(model_slug=model_slug).count()
        analyses_count = (
            SecurityAnalysis.query.join(GeneratedApplication)
            .filter(GeneratedApplication.model_slug == model_slug)
            .count()
        )

        enriched_data.update({
            'total_apps': total_apps,
            'analyses_count': analyses_count,
        })

        disabled_env = os.getenv('DISABLED_ANALYSIS_MODELS', '')
        disabled_models = {m.strip() for m in disabled_env.split(',') if m.strip()}
        is_disabled = model_slug in disabled_models

        return render_template(
            'pages/models/model_details.html',
            model=enriched_data,
            model_slug=model_slug,
            analysis_disabled=is_disabled,
            disabled_models=disabled_models
        )

    except Exception as e:
        current_app.logger.error(f"Error loading model details for {model_slug}: {e}")
        flash(f"Error loading model details: {e}", "error")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=404,
            error_title='Model Not Found',
            error_message=f"Model '{model_slug}' not found"
        )

@models_bp.route('/model/<model_slug>/more-info')
def model_more_info(model_slug):
    """HTMX endpoint: external details (OpenRouter) for modal display."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()

        ttl_hours = int(request.args.get('ttl', 6))
        force_refresh = request.args.get('refresh') == '1'

        cached = None
        if not force_refresh:
            cached = ExternalModelInfoCache.query.filter_by(model_slug=model_slug).first()
            if cached and cached.is_expired():
                cached = None

        if cached is None or force_refresh:
            data = _enrich_model(model)

            try:
                entry = ExternalModelInfoCache.query.filter_by(model_slug=model_slug).first()
                if not entry:
                    entry = ExternalModelInfoCache()
                    entry.model_slug = model_slug
                    entry.set_data(data)
                    db.session.add(entry)
                else:
                    entry.set_data(data)
                # utc_now helper may live in app.utils.time or fall back to datetime.utcnow
                try:
                    from app.utils.time import utc_now  # type: ignore
                    entry.cache_expires_at = utc_now() + timedelta(hours=ttl_hours)
                except Exception:
                    from datetime import datetime, timezone
                    entry.cache_expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
                entry.source_notes = 'openrouter'
                db.session.commit()
            except Exception as e:
                current_app.logger.warning(f"Failed to persist external cache for {model_slug}: {e}")

            payload = data
        else:
            payload = cached.get_data()

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
            current_app.logger.warning(f"Failed to compute live counts for {model_slug}: {e}")

        return render_template(
            'partials/models/more_info_modal_body.html',
            model=payload,
            model_slug=model_slug
        )
    except Exception as e:
        current_app.logger.error(f"Error loading more info for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error: {str(e)}</div>'

def _render_applications_page():
    """Core implementation for applications overview (shared by legacy and new routes)."""
    try:
        # Build port map from database
        port_map = {}
        try:
            for pc in db.session.query(PortConfiguration).all():
                key = (pc.model, pc.app_num)
                port_map[key] = {
                    'backend': pc.backend_port,
                    'frontend': pc.frontend_port,
                }
        except Exception as e:
            current_app.logger.warning(f"Failed to load PortConfiguration from DB: {e}")

        # Get filter & table state parameters
        model_filter = request.args.get('model')
        provider_filter = request.args.get('provider')
        search_filter = request.args.get('search')
        status_filter = request.args.get('status')  # running|stopped|error|pending
        sort_field = request.args.get('sort', 'model')  # model|provider|running_desc etc.
        page = max(1, int(request.args.get('page', 1) or 1))
        per_page = min(100, max(5, int(request.args.get('per_page', 25) or 25)))

        # Get all models to create app grid
        models_query = ModelCapability.query

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

        # Apply simple sorting
        if sort_field == 'model':
            models_query = models_query.order_by(ModelCapability.model_name.asc())
        elif sort_field == 'model_desc':
            models_query = models_query.order_by(ModelCapability.model_name.desc())
        elif sort_field == 'provider':
            models_query = models_query.order_by(ModelCapability.provider.asc())
        elif sort_field == 'provider_desc':
            models_query = models_query.order_by(ModelCapability.provider.desc())
        else:
            models_query = models_query.order_by(ModelCapability.provider.asc(), ModelCapability.model_name.asc())

        models = models_query.all()

        # If no DB models, synthesize from filesystem directories so application
        # grid can still render existing generated apps.
        if not models:
            try:
                from app.utils.generated_apps import list_generated_models
                fs_slugs = list_generated_models()
                synthetic = []
                for slug in fs_slugs:
                    class _SyntheticModel:
                        canonical_slug = slug
                        model_name = slug
                        provider = slug.split('_')[0]
                        display_name = slug
                    synthetic.append(_SyntheticModel())
                if synthetic:
                    models = synthetic
            except Exception as _e:  # pragma: no cover
                current_app.logger.warning(f"Failed building synthetic models for applications page: {_e}")

        # Build application grid data
        application_grid = []
        total_apps = 0
        running_containers = 0
        stopped_containers = 0

        try:
            current_app.logger.debug(f"[apps-grid] models_count={len(models)} total_apps_db={GeneratedApplication.query.count()}")
        except Exception:
            pass
        filtered_models = []
        for model in models:
            db_apps = GeneratedApplication.query.filter_by(
                model_slug=model.canonical_slug
            ).all()
            db_apps_index = {a.app_number: a for a in db_apps}

            model_apps = []
            existing_count = 0
            for i in range(1, 31):  # Apps 1-30
                app = db_apps_index.get(i)
                ports = port_map.get((model.canonical_slug, i))
                # Filesystem fallback detection (only if no DB row)
                fs_exists = False
                if not app:
                    try:
                        fs_dir = get_app_directory(model.canonical_slug, i)
                        fs_exists = fs_dir.exists()
                    except Exception:
                        fs_exists = False
                exists_flag = bool(app) or fs_exists
                if exists_flag:
                    existing_count += 1
                app_data = {
                    'id': app.id if app else None,
                    'app_number': i,
                    'exists': exists_flag,
                    'status': app.container_status if app else ('filesystem' if fs_exists else 'not_created'),
                    'app_type': app.app_type if app else ('web_app' if fs_exists else 'unknown'),
                    'has_backend': app.has_backend if app else fs_exists,
                    'has_frontend': app.has_frontend if app else fs_exists,
                    'has_docker_compose': app.has_docker_compose if app else False,
                    'generation_status': app.generation_status if app else ('filesystem' if fs_exists else 'pending'),
                    'ports': ports
                }
                model_apps.append(app_data)

                if app:
                    total_apps += 1
                    if app.container_status == 'running':
                        running_containers += 1
                    else:
                        stopped_containers += 1
                elif fs_exists:
                    # Count filesystem-only apps as stopped (not running)
                    total_apps += 1
                    stopped_containers += 1

            # Optional status filtering: include model row only if any app matches
            if status_filter:
                status_match = any(a.get('status') and status_filter in a.get('status') for a in model_apps)
                if not status_match:
                    continue
            filtered_models.append(model)
            application_grid.append({
                'model': model,
                'apps': model_apps,
                'apps_count': existing_count
            })
            try:
                current_app.logger.debug(f"[apps-grid] model={getattr(model,'canonical_slug','?')} fs_apps={existing_count} total_apps_running={running_containers} total_apps={total_apps}")
            except Exception:
                pass

        # Get filter options
        providers = []
        try:
            providers = db.session.query(ModelCapability.provider.distinct()).all()
            providers = [p[0] for p in providers if p[0]]
        except Exception:
            providers = []
        if not providers and models:
            # derive from synthetic set
            providers = sorted({getattr(m, 'provider', 'local') for m in models if getattr(m, 'provider', None)})

        # Build additional context expected by template
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

        available_models = [
            {
                'slug': m.canonical_slug,
                'display_name': getattr(m, 'display_name', None) or m.model_name or m.canonical_slug
            }
            for m in filtered_models or models
        ]

        try:
            analyzed_count = db.session.query(SecurityAnalysis).count()
        except Exception:
            analyzed_count = 0

        stats = {
            'total_applications': total_apps,
            'running_applications': running_containers,
            'analyzed_applications': analyzed_count,
            'unique_models': len(filtered_models or models)
        }

        # Pagination (on model rows)
        total_models_count = len(application_grid)
        start = (page - 1) * per_page
        end = start + per_page
        paged_grid = application_grid[start:end]
        page_count = max(1, (total_models_count + per_page - 1) // per_page)

        # Create pagination object with iter_pages() method
        pagination = SimplePagination(page, per_page, total_models_count, paged_grid)

        # Unified context for applications overview. Ensures new base layout flags are present
        # even if older code paths forget to set them.
        context = {
            'application_grid': paged_grid,
            'total_apps': total_apps,
            'running_containers': running_containers,
            'stopped_containers': stopped_containers,
            'total_models': total_models_count,
            'providers': providers,
            'applications': applications_list,
            'total_count': total_apps,
            'available_models': available_models,
            'stats': stats,
            'applications_stats': stats,  # Template compatibility alias
            'current_filters': {
                'model': model_filter,
                'provider': provider_filter,
                'search': search_filter,
                'status': status_filter,
                'sort': sort_field,
                'page': page,
                'per_page': per_page,
                'page_count': page_count
            },
            'pagination': pagination,
            'active_page': 'applications',  # navbar highlight
            'has_right_sidebar': True       # required for correct two-column layout
        }
        try:
            current_app.logger.debug(f"[apps-grid] final_stats total_apps={total_apps} models={len(models)}")
        except Exception:
            pass
        return render_template('pages/applications/applications_main.html', **context)

    except Exception as e:
        current_app.logger.error(f"Error loading applications: {e}")
        flash(f"Error loading applications: {e}", "error")
        return render_template(
            'pages/errors/errors_main.html',
            application_grid=[], total_apps=0,
            running_containers=0, stopped_containers=0,
            current_filters={}, providers=[], error=str(e)
        )


@models_bp.route('/application/<model_slug>/<int:app_number>')
def application_detail(model_slug, app_number):
    """Detailed view of a specific application."""
    try:
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()

        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()

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

        app_path = get_app_directory(model_slug, app_number)
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
            from app.models import ZAPAnalysis, OpenRouterAnalysis
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

        # Resolve ports from database
        ports = None
        try:
            pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_number).first()
            if pc:
                ports = {'backend': pc.backend_port, 'frontend': pc.frontend_port}
        except Exception as e:
            current_app.logger.warning(f"Failed to query PortConfiguration for {model_slug}/app{app_number}: {e}")

        # Prompt templates for this app number
        prompts = {'backend': '', 'frontend': ''}
        template_files = {'backend_file': '', 'frontend_file': ''}
        tmpl_dir = _project_root() / 'misc' / 'app_templates'
        try:
            backend_md = sorted(tmpl_dir.glob(f'app_{app_number}_backend_*.md'))
            frontend_md = sorted(tmpl_dir.glob(f'app_{app_number}_frontend_*.md'))
            if backend_md:
                template_files['backend_file'] = backend_md[0].name
                prompts['backend'] = backend_md[0].read_text(encoding='utf-8', errors='ignore')
            if frontend_md:
                template_files['frontend_file'] = frontend_md[0].name
                prompts['frontend'] = frontend_md[0].read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            current_app.logger.warning(f"Failed to load prompts for app {app_number}: {e}")

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
            'pages/applications/detail.html',
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
            artifacts=artifacts,
            templates_dir=str(tmpl_dir),
            app_base_dir=str(app_path)
        )
    except Exception as e:
        current_app.logger.error(f"Error loading application details for {model_slug}/app{app_number}: {e}")
        flash(f"Error loading application details: {e}", "error")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=404,
            error_title='Application Not Found',
            error_message=f"Application '{model_slug}/app{app_number}' not found"
        )

@models_bp.route('/applications/generate', methods=['POST'])
def generate_application():
    """HTMX endpoint: Generate a new application record."""
    try:
        from app.services import application_service as app_service
        from flask import Response

        model_slug = (request.form.get('model_slug') or '').strip()
        app_number_raw = request.form.get('app_number')
        app_type = (request.form.get('app_type') or 'web_app').strip() or 'web_app'
        auto_start = request.form.get('auto_start') == 'on'

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

        created = app_service.create_application(payload)

        if auto_start and created.get('id'):
            try:
                app_service.start_application(created['id'])
            except Exception:  # pragma: no cover - non critical
                current_app.logger.warning("Failed to auto-start application", exc_info=True)

        detail_url = f"{request.url_root.rstrip('/')}/models/application/{model_slug}/{app_number}"
        resp = Response(
            '<div class="alert alert-success">'
            f'Successfully created application for <strong>{model_slug}</strong> '
            f'(<a href="{detail_url}" target="_blank">open details</a>).</div>'
        )
        resp.headers['HX-Trigger'] = 'refresh-grid'
        return resp
    except Exception as e:
        msg = str(e)
        if 'unique' in msg.lower() and 'model' in msg.lower():
            return (
                '<div class="alert alert-warning">An application for this model and number already exists.</div>',
                409,
            )
        current_app.logger.error(f"Error generating application: {e}")
        return (
            f'<div class="alert alert-danger">Error generating application: {str(e)}</div>',
            500,
        )

@models_bp.route('/application/<model_slug>/<int:app_number>/section/overview')
def application_section_overview(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'overview')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/prompts')
def application_section_prompts(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'prompts')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/files')
def application_section_files(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'files')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/ports')
def application_section_ports(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'ports')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/container')
def application_section_container(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'container')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/analyses')
def application_section_analyses(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'analyses')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/metadata')
def application_section_metadata(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'metadata')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/artifacts')
def application_section_artifacts(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'artifacts')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/logs')
def application_section_logs(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'logs')

def _render_application_section(model_slug: str, app_number: int, section: str):
    """Shared loader for application detail sections (partials)."""
    try:
        # Resolve model robustly
        def _cands(slug: str):
            base = {slug, slug.replace('-', '_'), slug.replace('_', '-'), slug.replace(' ', '_'), slug.replace(' ', '-')}
            also = set()
            for s in list(base):
                also.add(s.replace('__', '_'))
                also.add(s.replace('--', '-'))
            return {c for c in (base | also) if c}

        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            try:
                candidates = list(_cands(model_slug))
                model = ModelCapability.query.filter(ModelCapability.canonical_slug.in_(candidates)).first() or model
                model = ModelCapability.query.filter(ModelCapability.model_name.in_(candidates)).first() or model
            except Exception:
                pass
        if not model:
            class _SyntheticModel:
                canonical_slug = model_slug
                model_name = model_slug
                provider = (model_slug.split('_')[0] if '_' in model_slug else model_slug.split('-')[0]) or 'local'
                display_name = model_slug
                def get_metadata(self):
                    return {}
            model = _SyntheticModel()

        # Resolve application
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        if not app and getattr(model, 'canonical_slug', None) and model.canonical_slug != model_slug:
            app = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug, app_number=app_number).first()
        if not app and getattr(model, 'model_name', None):
            app = GeneratedApplication.query.filter_by(model_slug=model.model_name, app_number=app_number).first()

        # Build app_data
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
                'container_status': 'not_created',
                'provider': getattr(model, 'provider', 'local')
            }
        else:
            app_data = {
                'id': app.id,
                'model_slug': app.model_slug,
                'app_number': app.app_number,
                'exists_in_db': True,
                'app_type': app.app_type,
                'provider': app.provider or getattr(model, 'provider', None),
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

        # Files and stats
        app_path = get_app_directory(model_slug, app_number)
        files_info = {
            'app_exists': app_path.exists(),
            'docker_compose': (app_path / 'docker-compose.yml').exists(),
            'backend_files': [],
            'frontend_files': [],
            'other_files': []
        }
        code_stats = {'total_files': 0, 'total_loc': 0, 'by_language': {}}
        if app_path.exists():
            for item in app_path.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(app_path)
                    info = {
                        'name': item.name,
                        'path': str(rel_path),
                        'size': item.stat().st_size,
                        'modified': item.stat().st_mtime,
                    }
                    lower = str(rel_path).lower()
                    if 'backend' in lower:
                        files_info['backend_files'].append(info)
                    elif 'frontend' in lower:
                        files_info['frontend_files'].append(info)
                    else:
                        files_info['other_files'].append(info)
                    # LOC
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
                    entry = code_stats['by_language'].setdefault(lang, {'files': 0, 'loc': 0})
                    entry['files'] += 1
                    entry['loc'] += loc
                    code_stats['total_files'] += 1
                    code_stats['total_loc'] += loc

        # Ports
        try:
            pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_number).first()
            ports = {'backend': pc.backend_port, 'frontend': pc.frontend_port} if pc else None
        except Exception:
            ports = None

        # Prompts
        prompts = {'backend': '', 'frontend': ''}
        template_files = {'backend_file': '', 'frontend_file': ''}
        tmpl_dir = _project_root() / 'misc' / 'app_templates'
        try:
            backend_md = sorted(tmpl_dir.glob(f'app_{app_number}_backend_*.md'))
            frontend_md = sorted(tmpl_dir.glob(f'app_{app_number}_frontend_*.md'))
            if backend_md:
                template_files['backend_file'] = backend_md[0].name
                prompts['backend'] = backend_md[0].read_text(encoding='utf-8', errors='ignore')
            if frontend_md:
                template_files['frontend_file'] = frontend_md[0].name
                prompts['frontend'] = frontend_md[0].read_text(encoding='utf-8', errors='ignore')
        except Exception:
            pass

        # Analyses (lightweight list)
        analyses = {}
        if app:
            from app.models import ZAPAnalysis, OpenRouterAnalysis
            analyses = {
                'security': SecurityAnalysis.query.filter_by(application_id=app.id).order_by(SecurityAnalysis.created_at.desc()).all(),
                'performance': PerformanceTest.query.filter_by(application_id=app.id).order_by(PerformanceTest.created_at.desc()).all(),
                'zap': ZAPAnalysis.query.filter_by(application_id=app.id).order_by(ZAPAnalysis.created_at.desc()).all(),
                'openrouter': OpenRouterAnalysis.query.filter_by(application_id=app.id).order_by(OpenRouterAnalysis.created_at.desc()).all()
            }

        # Context
        ctx = {
            'application': {
                'id': getattr(app, 'id', None) if app else None,
                'model_slug': model_slug,
                'app_number': app_number,
                'status': getattr(app, 'container_status', None) or 'not_created',
                'created_at': getattr(app, 'created_at', None) if app else None,
                'backend_port': (ports or {}).get('backend') if isinstance(ports, dict) else None,
                'frontend_port': (ports or {}).get('frontend') if isinstance(ports, dict) else None,
                'is_running': (getattr(app, 'container_status', None) == 'running') if app else False,
                'last_started': None,
                'file_count': code_stats.get('total_files', 0),
                'total_size': None,
                'environment_variables': {},
                'analyses': [],
                'generation_log': None,
                'versions': [],
            },
            'app_data': app_data,
            'files_info': files_info,
            'analyses': analyses,
            'model': model,
            'ports': ports,
            'code_stats': code_stats,
            'prompts': prompts,
            'template_files': template_files,
            'artifacts': {
                'project_index': (app_path / 'PROJECT_INDEX.md') if app_path.exists() else None,
                'readme': (app_path / 'README.md') if app_path.exists() else None,
                'compose_path': (app_path / 'docker-compose.yml') if app_path.exists() else None,
            },
            'templates_dir': str(tmpl_dir),
            'app_base_dir': str(app_path),
        }

        template_map = {
            'overview': 'pages/applications/partials/overview.html',
            'prompts': 'pages/applications/partials/prompts.html',
            'files': 'pages/applications/partials/files.html',
            'ports': 'pages/applications/partials/ports.html',
            'container': 'pages/applications/partials/container.html',
            'analyses': 'pages/applications/partials/analyses.html',
            'metadata': 'pages/applications/partials/metadata.html',
            'artifacts': 'pages/applications/partials/artifacts.html',
            'logs': 'pages/applications/partials/logs.html'
        }
        tpl = template_map.get(section)
        if not tpl:
            return f'<div class="alert alert-warning">Unknown section: {section}</div>', 404
        return render_template(tpl, **ctx)
    except Exception as e:
        current_app.logger.error(f"Error rendering section {section} for {model_slug}/app{app_number}: {e}")
        return f'<div class="alert alert-danger">Failed to load {section}: {e}</div>', 500

@models_bp.route('/application/<model_slug>/<int:app_number>/file')
def application_file_preview(model_slug, app_number):
    """HTMX endpoint to preview a file inside an application directory."""
    rel_path = request.args.get('path', '').strip()
    if not rel_path:
        return '<div class="text-muted">No file specified.</div>'
    try:
        app_dir = get_app_directory(model_slug, app_number)
        if not app_dir.exists():
            return '<div class="text-danger">Application directory not found.</div>'
        # prevent path traversal
        candidate = (app_dir / rel_path).resolve()
        if not str(candidate).startswith(str(app_dir.resolve())):
            return '<div class="text-danger">Invalid path.</div>', 400
        if not candidate.exists() or not candidate.is_file():
            return '<div class="text-warning">File not found.</div>', 404
        try:
            content = candidate.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return '<div class="text-danger">Unable to read file.</div>', 500
        from markupsafe import escape
        escaped = escape(content)
        return f'<div class="file-preview"><h6 class="small text-muted mb-2">{rel_path}</h6><pre class="small bg-body-tertiary p-2 rounded" style="max-height:480px; overflow:auto; white-space: pre-wrap">{escaped}</pre></div>'
    except Exception as e:
        current_app.logger.error(f"Error previewing file {model_slug}/app{app_number}:{rel_path}: {e}")
        return f'<div class="text-danger">Error: {e}</div>', 500

@models_bp.route('/application/<model_slug>/<int:app_number>/logs/modal')
def application_logs_modal(model_slug, app_number):
    """Return a modal containing recent log lines for the app (backend & frontend)."""
    try:
        logs_dir = _project_root() / 'generated' / 'apps' / '_logs'
        # fallback per model directory
        model_logs_dir = logs_dir / model_slug
        collected = []
        def _tail(path, limit=200):
            try:
                if path.exists():
                    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()[-limit:]
                    collected.append((path.name, lines))
            except Exception:
                pass
        # Try generic aggregated logs first
        _tail(logs_dir / f'{model_slug}_app{app_number}_backend.log')
        _tail(logs_dir / f'{model_slug}_app{app_number}_frontend.log')
        # Per-model subdir
        _tail(model_logs_dir / f'app{app_number}_backend.log')
        _tail(model_logs_dir / f'app{app_number}_frontend.log')
        if not collected:
            return ('<div id="logsModal" class="modal fade" tabindex="-1">'
                    '<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content">'
                    '<div class="modal-header"><h5 class="modal-title">Logs</h5>'
                    '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>'
                    '<div class="modal-body"><div class="alert alert-warning mb-0">No logs found for this application.</div></div>'
                    '</div></div></div>')
        body_parts = []
        for name, lines in collected:
            escaped = '\n'.join(lines).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            body_parts.append(f'<h6 class="mt-3">{name}</h6><pre class="small bg-body-tertiary p-2 rounded" style="max-height:260px; overflow:auto">{escaped}</pre>')
        body_html = ''.join(body_parts)
        return ('<div id="logsModal" class="modal fade" tabindex="-1">'
                '<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content">'
                f'<div class="modal-header"><h5 class="modal-title">Logs - {model_slug} app{app_number}</h5>'
                '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>'
                f'<div class="modal-body">{body_html}</div>'
                '</div></div></div>')
    except Exception as e:
        current_app.logger.error(f"Error loading logs modal for {model_slug}/app{app_number}: {e}")
        return ('<div id="logsModal" class="modal fade" tabindex="-1">'
                '<div class="modal-dialog"><div class="modal-content">'
                '<div class="modal-header"><h5 class="modal-title">Logs</h5>'
                '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>'
                f'<div class="modal-body"><div class="alert alert-danger">Error loading logs: {e}</div></div>'
                '</div></div></div>'), 500

@models_bp.route('/model_actions/<model_slug>')
@models_bp.route('/model_actions')
def model_actions(model_slug=None):
    """HTMX endpoint for model actions modal content."""
    try:
        if model_slug:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()

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
            # Bulk operations modal (legacy path expected 'partials/bulk_operations.html')
            # Updated to new canonical location under pages/applications/partials
            return render_template('pages/applications/partials/bulk_operations.html')

    except Exception as e:
        current_app.logger.error(f"Error loading model actions for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error loading model actions: {str(e)}</div>'

@models_bp.route('/application/<model_slug>/<int:app_number>/diagnostics/ports')
def application_ports_diagnostics(model_slug, app_number):
    """Lightweight preformatted diagnostics for port resolution attempts."""
    try:
        result = resolve_ports(model_slug, app_number, include_attempts=True)
        if not result:
            return '<pre class="small">{\n  "found": false\n}</pre>'
        import html as _html
        backend = result.get('backend')
        frontend = result.get('frontend')
        source = _html.escape(str(result.get('source')))
        attempts = result.get('attempts', [])
        esc_attempts = ',\n    '.join([_html.escape(a) for a in attempts])
        body = (
            '{\n'
            f'  "found": true,\n'
            f'  "backend": {backend},\n'
            f'  "frontend": {frontend},\n'
            f'  "source": "{source}",\n'
            f'  "attempts": [\n    {esc_attempts}\n  ]\n'
            '}'
        )
        return f'<pre class="small">{body}</pre>'
    except Exception as e:
        return f'<div class="alert alert-danger small">Diagnostics error: {e}</div>', 500

@models_bp.route('/model_apps/<model_slug>')
def model_apps(model_slug):
    """View applications for a specific model."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()

        return render_template(
            # Removed legacy 'pages/applications/index.html' reference (deprecated layout)
            model=model,
            apps=apps,
            page_title=f"{model.display_name} Applications"
        )
    except Exception as e:
        current_app.logger.error(f"Error loading model apps for {model_slug}: {e}")
        flash(f'Error loading applications: {str(e)}', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Model Applications Error',
            error_message=str(e),
            python_version='3.11'
        )

@models_bp.route('/import')
def models_import_page():
    """Render a simple import page to upload JSON and call the API."""
    try:
        return render_template('pages/models/import.html')
    except Exception as e:
        current_app.logger.error(f"Error rendering models import page: {e}")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Import Page Error',
            error_message=str(e)
        ), 500

@models_bp.route('/export/models.csv')
def export_models_csv():
    """Export models overview to CSV with selected fields."""
    try:
        models = ModelCapability.query.order_by(
            ModelCapability.provider, ModelCapability.model_name
        ).all()
        rows = []
        for m in models:
            data = _enrich_model(m)
            cached = ExternalModelInfoCache.query.filter_by(model_slug=m.canonical_slug).first()
            if cached:
                try:
                    data = deep_merge_dicts(data, cached.get_data())
                except Exception:  # pragma: no cover
                    pass
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

        csv_content = dicts_to_csv(rows)
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=models_export.csv'}
        )
    except Exception as e:  # pragma: no cover - export failures rare
        current_app.logger.error(f"Error exporting models CSV: {e}")
        return Response('provider,model_name,slug\n', mimetype='text/csv')

@models_bp.route('/filter')
def models_filter():
    """HTMX endpoint: Return filtered models grid for dynamic updates."""
    try:
        # Get filter parameters
        search = request.args.get('search', '').strip()
        provider = request.args.get('provider', '').strip()
        capabilities = request.args.get('capabilities', '').strip()
        pricing = request.args.get('pricing', '').strip()
        sort = request.args.get('sort', 'name')

        # Base query
        query = ModelCapability.query

        # Apply filters
        if provider:
            query = query.filter(ModelCapability.provider.ilike(f'%{provider}%'))

        if search:
            query = query.filter(
                or_(
                    ModelCapability.model_name.ilike(f'%{search}%'),
                    ModelCapability.provider.ilike(f'%{search}%'),
                    ModelCapability.canonical_slug.ilike(f'%{search}%')
                )
            )

        if pricing:
            if pricing == 'free':
                query = query.filter(ModelCapability.is_free)
            elif pricing == 'paid':
                query = query.filter(~ModelCapability.is_free)

        # Apply sorting
        if sort == 'provider':
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        elif sort == 'cost':
            # Sort by pricing (this is approximate since pricing comes from OpenRouter)
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        else:  # name
            query = query.order_by(ModelCapability.model_name)

        models = query.all()

        # Enrich models with OpenRouter data and filter by capabilities
        enriched_models = []
        for model in models:
            enriched_data = _enrich_model(model)
            app_count = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug).count()
            enriched_data['apps_count'] = app_count

            # Filter by capabilities if specified
            if capabilities:
                model_caps = enriched_data.get('capabilities', {})
                cap_supported = False

                if capabilities == 'text' and model_caps.get('text'):
                    cap_supported = True
                elif capabilities == 'vision' and (model_caps.get('vision') or model_caps.get('images')):
                    cap_supported = True
                elif capabilities == 'multimodal' and model_caps.get('multimodal'):
                    cap_supported = True
                elif capabilities == 'function_calling' and model_caps.get('function_calling'):
                    cap_supported = True
                elif capabilities == 'streaming' and model_caps.get('streaming'):
                    cap_supported = True

                if not cap_supported:
                    continue

            enriched_models.append(enriched_data)

        # Return just the models grid
        return render_template('pages/models/partials/models-grid.html', models=enriched_models)

    except Exception as e:
        current_app.logger.error(f"Error filtering models: {e}")
        return f'<div class="alert alert-danger">Error filtering models: {str(e)}</div>', 500

@models_bp.route('/comparison')
def models_comparison():
    """Render comparison page with optional selected models list."""
    try:
        raw = request.args.get('models', '')
        slugs = [s.strip() for s in raw.split(',') if s.strip()][:6]  # limit to 6 for layout
        selected_models = []
        comparison_rows = []
        capability_union: set[str] = set()
        pricing = []
        if slugs:
            for slug in slugs:
                m = ModelCapability.query.filter_by(canonical_slug=slug).first()
                if not m:
                    continue
                data = _enrich_model(m)
                caps = data.get('capabilities') or {}
                # normalize capability keys
                if isinstance(caps, dict):
                    for k, v in caps.items():
                        if v:
                            capability_union.add(k)
                # Normalize price fields to float (original sources may be strings like '0.0012')
                def _to_float(v):
                    try:
                        if v is None or v == '':
                            return 0.0
                        return float(v)
                    except Exception:
                        return 0.0
                selected_models.append({
                    'slug': slug,
                    'name': data.get('name') or m.model_name,
                    'provider': data.get('provider') or m.provider,
                    'context_length': data.get('openrouter_context_length') or m.context_window,
                    'input_price': _to_float(data.get('openrouter_prompt_price') or data.get('input_price_per_1k')),
                    'output_price': _to_float(data.get('openrouter_completion_price') or data.get('output_price_per_1k')),
                    'performance_score': data.get('performance_score'),
                    'capabilities': caps,
                })
            # Pricing delta baseline (first model)
            if selected_models:
                base = selected_models[0]
                b_in = float(base.get('input_price') or 0) or 0.0
                b_out = float(base.get('output_price') or 0) or 0.0
                for sm in selected_models:
                    in_p = float(sm.get('input_price') or 0) or 0.0
                    out_p = float(sm.get('output_price') or 0) or 0.0
                    pricing.append({
                        'slug': sm['slug'],
                        'name': sm['name'],
                        'input_price': in_p,
                        'output_price': out_p,
                        'input_delta': (in_p - b_in) if b_in else None,
                        'output_delta': (out_p - b_out) if b_out else None,
                    })
            # Capability matrix
            capability_list = sorted(capability_union)
            for cap in capability_list:
                row = {'capability': cap, 'support': []}
                for sm in selected_models:
                    caps = sm.get('capabilities') or {}
                    val = False
                    if isinstance(caps, dict):
                        val = bool(caps.get(cap))
                    elif isinstance(caps, list):
                        val = cap in caps
                    row['support'].append(val)
                comparison_rows.append(row)
        return render_template(
            'pages/models/comparison.html',
            models=selected_models,
            pricing=pricing,
            capability_rows=comparison_rows,
            selected_models=slugs,
        )
    except Exception as e:
        current_app.logger.error(f"Error building comparison page: {e}")
        flash('Error building comparison', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Comparison Error',
            error_message=str(e)
        ), 500