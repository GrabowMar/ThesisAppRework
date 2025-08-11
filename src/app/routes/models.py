"""
Models Routes
============

Routes for managing AI models and their generated applications.
"""

import logging

from flask import Blueprint, render_template, request, flash

from ..models import (
    ModelCapability, GeneratedApplication,
    SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis,
    BatchAnalysis, ContainerizedTest
)
from ..extensions import db

# Set up logger
logger = logging.getLogger(__name__)

models_bp = Blueprint('models', __name__)


@models_bp.route('/')
def models_overview():
    """Models overview page showing all available AI models."""
    try:
        # Get filter parameters
        provider_filter = request.args.get('provider')
        search_filter = request.args.get('search')
        sort_by = request.args.get('sortBy', 'name')
        view_mode = request.args.get('view_mode', 'grid')
        page = request.args.get('page', 1, type=int)
        per_page = 12  # Number of models per page
        
        # Build query
        query = ModelCapability.query
        
        if provider_filter:
            query = query.filter(ModelCapability.provider == provider_filter)
        
        if search_filter:
            query = query.filter(
                ModelCapability.model_name.contains(search_filter)
            )
        
        # Apply sorting
        if sort_by == 'provider':
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        elif sort_by == 'name':
            query = query.order_by(ModelCapability.model_name)
        elif sort_by == 'last_updated':
            query = query.order_by(ModelCapability.updated_at.desc())
        else:
            query = query.order_by(ModelCapability.model_name)
        
        # Paginate
        models_pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Add additional stats to models
        models_with_stats = []
        for model in models_pagination.items:
            app_count = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug).count()
            
            # Add computed fields
            model.apps_count = app_count
            model.analyses_count = 0  # This could be computed from related analyses
            model.success_rate = 85  # Placeholder - could be computed
            model.status = 'active'  # Placeholder
            model.capabilities = ['Chat', 'Code Generation', 'Analysis']  # Placeholder
            model.last_updated = model.updated_at
            model.model_slug = model.canonical_slug  # Add this for template compatibility
            models_with_stats.append(model)
        
        # Check if this is an HTMX request
        is_htmx = request.headers.get('HX-Request')
        
        if is_htmx:
            # Return just the partial content for HTMX
            if view_mode == 'list':
                return render_template(
                    'partials/models/models_list.html',
                    models=models_with_stats,
                    pagination=models_pagination
                )
            else:
                return render_template(
                    'partials/models/models_grid.html',
                    models=models_with_stats,
                    pagination=models_pagination
                )
        else:
            # Return full page for regular requests
            # Group by provider for initial load
            models_by_provider = {}
            for model in models_with_stats:
                if model.provider not in models_by_provider:
                    models_by_provider[model.provider] = []
                models_by_provider[model.provider].append(model)
            
            return render_template(
                'pages/models_overview.html',
                models_by_provider=models_by_provider,
                total_models=models_pagination.total,
                pagination=models_pagination
            )
            
    except Exception as e:
        logger.error(f"Error loading models: {e}")
        if request.headers.get('HX-Request'):
            return f'<div class="alert alert-danger">Error loading models: {str(e)}</div>'
        else:
            flash('Error loading models', 'error')
            return render_template('pages/error.html', 
                                 error_code=500,
                                 error_title='Models Error',
                                 error_message=str(e))


@models_bp.route('/applications')
def applications():
    """Applications overview page."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filter parameters
        model_filter = request.args.get('model')
        provider_filter = request.args.get('provider')
        status_filter = request.args.get('status')
        search_filter = request.args.get('search')
        
        # Build query
        query = GeneratedApplication.query
        
        if model_filter:
            query = query.filter(GeneratedApplication.model_slug.contains(model_filter))
        
        if provider_filter:
            query = query.filter(GeneratedApplication.provider == provider_filter)
        
        if status_filter:
            query = query.filter(GeneratedApplication.container_status == status_filter)
            
        if search_filter:
            query = query.filter(
                db.or_(
                    GeneratedApplication.model_slug.contains(search_filter),
                    GeneratedApplication.provider.contains(search_filter),
                    GeneratedApplication.app_type.contains(search_filter)
                )
            )
        
        # Paginate results
        applications_pagination = query.order_by(
            GeneratedApplication.created_at.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Get filter options
        providers = db.session.query(GeneratedApplication.provider.distinct()).filter(
            GeneratedApplication.provider.isnot(None)
        ).all()
        providers = [p[0] for p in providers if p[0]]
        
        models = db.session.query(GeneratedApplication.model_slug.distinct()).filter(
            GeneratedApplication.model_slug.isnot(None)
        ).all()
        models = [m[0] for m in models if m[0]]
        
        # Enhanced app data with statistics
        enhanced_apps = []
        for app in applications_pagination.items:
            # Get security analysis count
            security_count = SecurityAnalysis.query.filter_by(application_id=app.id).count()
            
            # Get performance test count
            performance_count = PerformanceTest.query.filter_by(application_id=app.id).count()
            
            # Get ZAP analysis count
            zap_count = ZAPAnalysis.query.filter_by(application_id=app.id).count()
            
            # Get OpenRouter analysis count
            openrouter_count = OpenRouterAnalysis.query.filter_by(application_id=app.id).count()
            
            # Add computed fields
            app.security_analyses_count = security_count
            app.performance_tests_count = performance_count
            app.zap_analyses_count = zap_count
            app.openrouter_analyses_count = openrouter_count
            app.total_analyses = security_count + performance_count + zap_count + openrouter_count
            
            # Status badge class
            status_class = {
                'running': 'success',
                'stopped': 'secondary', 
                'error': 'danger',
                'pending': 'warning'
            }.get(app.container_status, 'secondary')
            app.status_class = status_class
            
            # Description from metadata
            metadata = app.get_metadata()
            app.description = metadata.get('description', f'{app.app_type} application using {app.model_slug}')
            
            enhanced_apps.append(app)
        
        # Check if this is an HTMX request
        if request.headers.get('HX-Request'):
            return render_template(
                'partials/applications_content.html',
                applications=enhanced_apps,
                pagination=applications_pagination
            )
        
        return render_template(
            'pages/applications.html',
            applications=enhanced_apps,
            pagination=applications_pagination,
            providers=providers,
            available_models=models,
            current_filters={
                'model': model_filter,
                'provider': provider_filter,
                'status': status_filter,
                'search': search_filter
            }
        )
    except Exception as e:
        logger.error(f"Error loading applications: {e}")
        if request.headers.get('HX-Request'):
            return f'<div class="alert alert-danger">Error loading applications: {str(e)}</div>'
        else:
            flash('Error loading applications', 'error')
            return render_template('pages/error.html', 
                                 error_code=500,
                                 error_title='Applications Error',
                                 error_message=str(e))


@models_bp.route('/application/<int:app_id>')
def application_detail(app_id):
    """Application detail page."""
    try:
        app = GeneratedApplication.query.get_or_404(app_id)
        
        # Get related analyses
        security_analyses = SecurityAnalysis.query.filter_by(
            application_id=app_id
        ).order_by(SecurityAnalysis.created_at.desc()).all()
        
        performance_tests = PerformanceTest.query.filter_by(
            application_id=app_id
        ).order_by(PerformanceTest.created_at.desc()).all()
        
        zap_analyses = ZAPAnalysis.query.filter_by(
            application_id=app_id
        ).order_by(ZAPAnalysis.created_at.desc()).all()
        
        openrouter_analyses = OpenRouterAnalysis.query.filter_by(
            application_id=app_id
        ).order_by(OpenRouterAnalysis.created_at.desc()).all()
        
        # Calculate statistics
        stats = {
            'total_security_analyses': len(security_analyses),
            'total_performance_tests': len(performance_tests),
            'total_zap_analyses': len(zap_analyses),
            'total_ai_analyses': len(openrouter_analyses),
            'security_issues': sum(a.total_issues or 0 for a in security_analyses),
            'avg_response_time': (
                sum(t.average_response_time or 0 for t in performance_tests) / len(performance_tests) 
                if performance_tests else 0
            ),
            'avg_rps': (
                sum(t.requests_per_second or 0 for t in performance_tests) / len(performance_tests) 
                if performance_tests else 0
            )
        }
        
        return render_template(
            'pages/application_detail.html',
            app=app,
            security_analyses=security_analyses,
            performance_tests=performance_tests,
            zap_analyses=zap_analyses,
            openrouter_analyses=openrouter_analyses,
            stats=stats
        )
    except Exception as e:
        logger.error(f"Error loading application {app_id}: {e}")
        flash('Error loading application', 'error')
        return render_template('pages/error.html', 
                             error_code=500,
                             error_title='Application Error',
                             error_message=str(e))


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
            'pages/model_apps.html',
            model=model,
            apps=apps
        )
    except Exception as e:
        logger.error(f"Error loading model apps for {model_slug}: {e}")
        flash(f'Error loading applications: {str(e)}', 'error')
        return render_template('pages/error.html', 
                             error_code=500,
                             error_title='Model Applications Error',
                             error_message=str(e))
