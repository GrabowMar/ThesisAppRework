"""
Analysis Routes
==============

Routes for managing analysis operations and results.
"""

import logging
import time
from functools import wraps
import math

from flask import (
    Blueprint, request, jsonify, current_app,
    url_for, Response, redirect, flash
)
from ..utils.template_paths import render_template_compat as render_template

from ..services.task_manager import TaskManager
from ..services import results_loader
from ..models import GeneratedApplication
from ..constants import AnalysisStatus

# Set up logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')

# ---------------------------------------------------------------------------
# Lightweight in-process rate limiting (best-effort; not for multi-instance)
# ---------------------------------------------------------------------------
_last_call_registry = {}

def rate_limited(min_interval: float = 5.0):
    """Decorator to throttle high-frequency HTMX polling endpoints.

    Behavior:
    - Key = (function name, HX-Target or path, remote_addr) in-memory only.
    - If called again within min_interval, short-circuit with 204 (No Content)
      instead of 429, adding Retry-After seconds and X-RateLimit-Reason headers.
    - This makes throttling quiet in logs while still hinting clients to back off.

    Notes:
    - Best-effort only; not shared across processes or instances.
    - HTMX clients can optionally read Retry-After to adapt polling.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                from flask import request, make_response
                # Make the key more granular to reduce cross-tab collisions:
                # include HX-Target (element id) when available, otherwise the path.
                hx_target = request.headers.get('HX-Target') or request.path or ''
                key = (fn.__name__, hx_target, request.remote_addr or 'anon')
                now = time.time()
                last = _last_call_registry.get(key, 0)
                elapsed = now - last
                if elapsed < min_interval:
                    # Too soon; short-circuit with 204 (No Content) to avoid log noise
                    remaining = max(0.0, min_interval - elapsed)
                    resp = make_response('', 204)
                    # Provide a backoff hint; clients may optionally respect it
                    resp.headers['Retry-After'] = str(int(math.ceil(remaining)))
                    resp.headers['X-RateLimit-Reason'] = 'throttled'
                    resp.headers['Cache-Control'] = 'no-store'
                    return resp
                _last_call_registry[key] = now
            except Exception:  # pragma: no cover - safety net
                pass
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# Initialize services
task_manager = TaskManager()


@analysis_bp.route('/')
def analysis_dashboard():
    """Unified Analysis Hub - comprehensive overview merging analysis statistics, results, and batch operations.
    
    Features:
    - Combined statistics from analysis, batch, and results
    - Unified activity timeline across all operation types
    - System health monitoring and queue status
    - Batch operations summary integration
    - Results overview with trends
    - Real-time updates via HTMX endpoints
    """
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, ModelCapability
        from ..extensions import db
        from sqlalchemy import func
        from datetime import datetime, timedelta, timezone
        
        # Core analysis statistics
        stats = {
            'total_security': SecurityAnalysis.query.count(),
            'total_performance': PerformanceTest.query.count(),
            'total_dynamic': ZAPAnalysis.query.count(),
            'total_models': ModelCapability.query.count(),
        }
        
        # Weekly trends for statistics
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        trends = {
            'security_this_week': SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= week_ago).count(),
            'performance_this_week': PerformanceTest.query.filter(PerformanceTest.created_at >= week_ago).count(),
            'dynamic_this_week': ZAPAnalysis.query.filter(ZAPAnalysis.created_at >= week_ago).count(),
        }
        
        # Running analyses count
        stats['running_analyses'] = (
            SecurityAnalysis.query.filter_by(status='running').count() +
            PerformanceTest.query.filter_by(status='running').count() +
            ZAPAnalysis.query.filter_by(status='running').count()
        )
        
        # Recent combined activity (last 15 items across all types)
        recent_activity = []
        
        # Security analyses
        recent_security = SecurityAnalysis.query.order_by(SecurityAnalysis.created_at.desc()).limit(8).all()
        for analysis in recent_security:
            recent_activity.append({
                'type': 'security',
                'id': analysis.id,
                'model_slug': analysis.model_slug,
                'app_number': analysis.app_number,
                'status': analysis.status,
                'created_at': analysis.created_at,
                'description': f"Security analysis #{analysis.id}"
            })
        
        # Performance tests
        recent_performance = PerformanceTest.query.order_by(PerformanceTest.created_at.desc()).limit(8).all()
        for test in recent_performance:
            recent_activity.append({
                'type': 'performance',
                'id': test.id,
                'model_slug': test.model_slug,
                'app_number': test.app_number,
                'status': test.status,
                'created_at': test.created_at,
                'description': f"Performance test #{test.id}"
            })
        
        # Dynamic analyses
        recent_dynamic = ZAPAnalysis.query.order_by(ZAPAnalysis.created_at.desc()).limit(8).all()
        for analysis in recent_dynamic:
            recent_activity.append({
                'type': 'dynamic',
                'id': analysis.id,
                'model_slug': analysis.model_slug,
                'app_number': analysis.app_number,
                'status': analysis.status,
                'created_at': analysis.created_at,
                'description': f"Dynamic scan #{analysis.id}"
            })
        
        # Sort by date and limit to recent items
        recent_activity = sorted(recent_activity, key=lambda x: x['created_at'], reverse=True)[:15]
        
        # Mock batch statistics (in real implementation, these would come from batch service)
        batch_stats = {
            'total_batches': 0,
            'active_batches': 0,
            'running': 0,
            'queued': 0,
            'completed_today': 0,
            'recent_batches': []
        }
        
        # Mock system health data (in real implementation, these would come from system monitoring)
        system_resources = {
            'cpu_usage': 45.2,
            'memory_usage': 62.8,
            'active_workers': 3,
            'max_workers': 5
        }
        
        system_health = {
            'queue_length': stats['running_analyses']
        }
        
        # Results summary (count of completed analyses with results)
        results_summary = {
            'total_results': (
                SecurityAnalysis.query.filter_by(status='completed').count() +
                PerformanceTest.query.filter_by(status='completed').count() +
                ZAPAnalysis.query.filter_by(status='completed').count()
            )
        }
        
        return render_template(
            'single_page.html',
            page_title='Analysis Hub',
            page_icon='fa-tachometer-alt',
            main_partial='pages/analysis/dashboard.html',
            stats=stats,
            trends=trends,
            recent_activity=recent_activity,
            batch_stats=batch_stats,
            system_resources=system_resources,
            system_health=system_health,
            results_summary=results_summary
        )
        
    except Exception as e:
        logger.error(f"Error loading unified analysis dashboard: {e}")
        return render_template(
            'single_page.html',
            page_title='Error',
            main_partial='partials/common/error.html',
            error=str(e)
        ), 500


# ============================================================================
# New subpages: List, Create, Preview
# ============================================================================

@analysis_bp.get('/list')
def analysis_list():
    """Comprehensive Analysis List - all analyses with filtering and sorting.
    
    Features:
    - Tabbed view by analysis type
    - Filtering by model, status, date
    - Sorting options
    - Bulk actions
    """
    try:
        return render_template(
            'single_page.html',
            page_title='All Analyses',
            page_icon='fa-list',
            main_partial='pages/analysis/list.html'
        )
    except Exception as e:
        logger.error(f"Error loading analyses list page: {e}")
        return render_template(
            'single_page.html', 
            page_title='Error',
            main_partial='partials/common/error.html',
            error=str(e)
        ), 500


# Note: Create functionality removed - users create analyses directly from dashboard
# Legacy create routes removed for cleaner interface


@analysis_bp.get('/create/security')
def analyses_create_security_page():
    """Create page focused on Security form only (redirects to unified wizard)."""
    return redirect(url_for('analysis.analysis_create_wizard'))


@analysis_bp.get('/create/dynamic')
def analyses_create_dynamic_page():
    """Create page focused on Dynamic (ZAP) form only (redirects to unified wizard)."""
    return redirect(url_for('analysis.analysis_create_wizard'))


@analysis_bp.get('/create/performance')
def analyses_create_performance_page():
    """Create page focused on Performance test form only (redirects to unified wizard)."""
    return redirect(url_for('analysis.analysis_create_wizard'))


@analysis_bp.get('/create/batch')
def analyses_create_batch_page():
    """Create page focused on Batch analysis form only (redirects to unified wizard)."""
    return redirect(url_for('analysis.analysis_create_wizard'))


@analysis_bp.get('/create')
def analysis_create_wizard():
    """Multi-step analysis creation wizard (placeholder initial implementation).

    Provides a shell where the user can select model/app and desired analysis
    types (security, performance, dynamic, or comprehensive). Future enhancement
    will load partial forms via HTMX.
    """
    try:
        # Unified create experience now lives in pages/analysis/create.html
        return render_template(
            'single_page.html',
            page_title='Create Analysis',
            page_icon='fa-plus-circle',
            main_partial='pages/analysis/create.html'
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Error loading analysis create wizard: {e}")
        return render_template('single_page.html', page_title='Error', main_partial='partials/common/error.html', error=str(e)), 500

# Backward compatibility alias used by legacy redirects/tests
@analysis_bp.get('/create/page')
def analyses_create_page():  # pragma: no cover - legacy alias
    return redirect(url_for('analysis.analysis_create_wizard'))


@analysis_bp.get('/create/legacy')
def analysis_create_legacy():  # pragma: no cover - retained as alias; serves unified create now
    """Backward compatibility alias for any bookmarked "legacy" create URL.

    Requirement: User wants a single create experience everywhere (use create.html).
    Strategy: Keep the /analysis/create/legacy route (avoids 404 if referenced) but
    render the unified wizard template so there is exactly one creation UX.
    """
    try:
        return render_template(
            'single_page.html',
            page_title='Create Analysis',
            page_icon='fa-plus-circle',
            # Point directly at the canonical create page (NOT legacy partial anymore)
            main_partial='pages/analysis/create.html'
        )
    except Exception as e:
        logger.error(f"Error rendering create (legacy alias) form: {e}")
        return render_template('single_page.html', page_title='Error', main_partial='partials/common/error.html', error=str(e)), 500


@analysis_bp.post('/create')
def analysis_create():  # pragma: no cover - validated via tests
    """Unified creation endpoint (currently supports 'comprehensive').

    Deterministic test contract:
    - Always returns JSON (tests assert JSON fields even when COMPREHENSIVE_TEST_FORCE_RENDER is set)
    - Avoids ServiceLocator (tests monkeypatch module-level functions)
    - Provides IDs + redirect_url + success flag
    """
    try:
        from flask import current_app
        from ..models import GeneratedApplication
        # Direct import; tests monkeypatch functions on this module
        import app.services.analysis_service as analysis_service  # type: ignore

        # Accept JSON or form data
        data = request.get_json(silent=True) or request.form.to_dict()
        analysis_type = data.get('analysis_type') or 'security'
        model_slug = data.get('model_slug')
        app_number = data.get('app_number')

        if not model_slug or app_number is None:
            return jsonify({'success': False, 'message': 'model_slug and app_number required'}), 400
        try:
            app_number = int(app_number)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'app_number must be int'}), 400

        app_obj = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        if not app_obj:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        if analysis_type == 'comprehensive':
            security = analysis_service.create_comprehensive_security_analysis(app_obj.id)
            performance = analysis_service.create_performance_test({'application_id': app_obj.id})
            dynamic = analysis_service.create_dynamic_analysis({'application_id': app_obj.id})

            # Fire off tasks (best-effort; ignore failures individually)
            for starter, ident in [
                (analysis_service.start_security_analysis, security.get('id')),
                (analysis_service.start_performance_test, performance.get('id')),
                (analysis_service.start_dynamic_analysis, dynamic.get('id')),
            ]:
                try:
                    if ident is not None:
                        starter(ident)
                except Exception:  # noqa: BLE001
                    logger.exception('Failed to start analysis component')

            redirect_url = f"/analysis/results/{model_slug}/{app_number}"
            payload = {
                'success': True,
                'message': 'Comprehensive analysis started successfully!',
                'heading': 'Comprehensive Analysis Started',
                'redirect_url': redirect_url,
                'security_id': security.get('id'),
                'performance_id': performance.get('id'),
                'dynamic_id': dynamic.get('id'),
                'show_modal': True
            }

            # Unified contract: always JSON for comprehensive creation (tests rely on keys)
            return jsonify(payload)

        return jsonify({'success': False, 'message': f'Unsupported analysis_type {analysis_type}'}), 400
    except Exception as e:  # pragma: no cover
        logger.error(f"Error in analysis_create: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Trailing slash aliases (prevent automatic 308/302 redirects if tests or callers use a slash)
@analysis_bp.get('/create/')
def analysis_create_wizard_slash():  # pragma: no cover - simple alias
    return analysis_create_wizard()

@analysis_bp.post('/create/')
def analysis_create_slash():  # pragma: no cover - simple alias
    return analysis_create()


@analysis_bp.get('/preview/<model_slug>/<int:app_number>')
def analyses_preview_page(model_slug: str, app_number: int):
    """Preview results for a specific application across analysis types.

    Uses compact preview partials to show latest Security and Dynamic results.
    """
    try:
        from sqlalchemy import desc
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        if not app:
            return render_template('partials/common/error.html', error='Application not found'), 404

        from ..models import SecurityAnalysis, ZAPAnalysis
        latest_security = SecurityAnalysis.query.filter_by(application_id=app.id).order_by(desc(SecurityAnalysis.created_at)).first()
        latest_dynamic = ZAPAnalysis.query.filter_by(application_id=app.id).order_by(desc(ZAPAnalysis.created_at)).first()

        return render_template(
            'single_page.html',
            page_title='Analysis Preview',
            page_icon='fa-eye',
            page_subtitle=f"{model_slug} / app {app_number}",
            main_partial='partials/analysis/preview/shell.html',
            application=app,
            latest_security=latest_security,
            latest_dynamic=latest_dynamic
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Error loading analysis preview: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500

@analysis_bp.get('/api/stats')
def htmx_analysis_stats():
    """Enhanced HTMX endpoint for dashboard statistics with comprehensive metrics."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, ModelCapability
        from ..extensions import db
        from sqlalchemy import func
        from datetime import datetime, timedelta, timezone
        
        # Current totals
        stats = {
            'total_security': SecurityAnalysis.query.count(),
            'total_performance': PerformanceTest.query.count(),
            'total_dynamic': ZAPAnalysis.query.count(),
            'total_models': ModelCapability.query.count(),
        }
        
        # Weekly trends  
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        trends = {
            'security_this_week': SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= week_ago).count(),
            'performance_this_week': PerformanceTest.query.filter(PerformanceTest.created_at >= week_ago).count(),
            'dynamic_this_week': ZAPAnalysis.query.filter(ZAPAnalysis.created_at >= week_ago).count(),
        }
        
        # Status breakdown for security analyses
        status_counts = dict(
            db.session.query(SecurityAnalysis.status, func.count(SecurityAnalysis.id))
            .group_by(SecurityAnalysis.status).all()
        )
        stats.update({
            'security_completed': status_counts.get('completed', 0),
            'security_running': status_counts.get('running', 0), 
            'security_failed': status_counts.get('failed', 0),
            'security_pending': status_counts.get('pending', 0),
        })
        
        # Running analyses count across all types
        stats['running_analyses'] = (
            stats.get('security_running', 0) +
            PerformanceTest.query.filter_by(status='running').count() +
            ZAPAnalysis.query.filter_by(status='running').count()
        )
        
        return render_template('partials/analysis/hub_stats.html', stats=stats, trends=trends)
    except Exception as e:
        logger.error(f"HTMX dashboard stats error: {e}")
        return render_template('partials/common/error.html', error='Failed to load dashboard stats'), 500


@analysis_bp.get('/api/list/combined')
@rate_limited(2.0)
def htmx_list_combined():
    """HTMX: Combined analyses list (security + dynamic + performance)."""
    try:
        from ..services import analysis_service as svc
        security = svc.list_security_analyses(limit=50)
        dynamic = svc.list_dynamic_analyses(limit=50)
        performance = svc.list_performance_tests(limit=50)
        return render_template('partials/analysis/list/combined.html',
                               security=security, dynamic=dynamic, performance=performance)
    except Exception as e:
        logger.error(f"HTMX combined list error: {e}")
        return render_template('partials/common/error.html', error='Failed to load analyses list'), 500


@analysis_bp.get('/api/list/security')
@rate_limited(2.0)
def htmx_list_security():
    try:
        from ..services import analysis_service as svc
        items = svc.list_security_analyses(limit=100)
        # Enrich with model/app info for UI
        from ..models import GeneratedApplication
        for it in items:
            try:
                # Use modern Session.get to avoid deprecated Query.get
                from app.extensions import get_session
                with get_session() as _s:
                    app = _s.get(GeneratedApplication, it.get('application_id'))
                if app:
                    it['model_slug'] = app.model_slug
                    it['app_number'] = app.app_number
            except Exception:
                pass
        return render_template('partials/analysis/list/security.html', items=items)
    except Exception as e:
        logger.error(f"HTMX security list error: {e}")
        return render_template('partials/common/error.html', error='Failed to load security analyses'), 500


@analysis_bp.get('/api/list/dynamic')
@rate_limited(2.0)
def htmx_list_dynamic():
    try:
        from ..services import analysis_service as svc
        items = svc.list_dynamic_analyses(limit=100)
        from ..models import GeneratedApplication
        for it in items:
            try:
                from app.extensions import get_session
                with get_session() as _s:
                    app = _s.get(GeneratedApplication, it.get('application_id'))
                if app:
                    it['model_slug'] = app.model_slug
                    it['app_number'] = app.app_number
            except Exception:
                pass
        return render_template('partials/analysis/list/dynamic.html', items=items)
    except Exception as e:
        logger.error(f"HTMX dynamic list error: {e}")
        return render_template('partials/common/error.html', error='Failed to load dynamic analyses'), 500


@analysis_bp.get('/api/list/performance')
@rate_limited(2.0)
def htmx_list_performance():
    try:
        from ..services import analysis_service as svc
        items = svc.list_performance_tests(limit=100)
        from ..models import GeneratedApplication
        for it in items:
            try:
                from app.extensions import get_session
                with get_session() as _s:
                    app = _s.get(GeneratedApplication, it.get('application_id'))
                if app:
                    it['model_slug'] = app.model_slug
                    it['app_number'] = app.app_number
            except Exception:
                pass
        return render_template('partials/analysis/list/performance.html', items=items)
    except Exception as e:
        logger.error(f"HTMX performance list error: {e}")
        return render_template('partials/common/error.html', error='Failed to load performance tests'), 500


@analysis_bp.get('/api/active-tasks')
@rate_limited(2.0)
def htmx_active_tasks():
    """HTMX: Show currently active Celery tasks tracked by TaskManager."""
    try:
        active = task_manager.get_active_tasks()
        return render_template('partials/analysis/list/active_tasks.html', active=active)
    except Exception as e:
        logger.error(f"HTMX active tasks error: {e}")
        return render_template('partials/common/error.html', error='Failed to load active tasks'), 500


@analysis_bp.get('/tasks')
def tasks_page():
    """Tasks management page with Active + History panels."""
    try:
        return render_template(
            'single_page.html',
            page_title='Tasks',
            page_icon='fa-tasks',
            main_partial='partials/tasks/shell.html'
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Error loading tasks page: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.get('/api/list/task-history')
@rate_limited(2.5)
def htmx_task_history():
    """HTMX: Load recent task history from TaskManager."""
    try:
        history = task_manager.get_task_history(limit=100)
        return render_template('partials/analysis/list/task_history.html', history=history)
    except Exception as e:
        logger.error(f"HTMX task history error: {e}")
        return render_template('partials/common/error.html', error='Failed to load task history'), 500


@analysis_bp.get('/api/completed-tasks')
@rate_limited(3.0)
def htmx_completed_tasks():
    """HTMX: Render completed tasks with quick links to result details."""
    try:
        history = task_manager.get_task_history(limit=100)
        return render_template('partials/analysis/list/completed_tasks.html', history=history)
    except Exception as e:
        logger.error(f"HTMX completed tasks error: {e}")
        return render_template('partials/common/error.html', error='Failed to load completed tasks'), 500

@analysis_bp.get('/api/trends')
def htmx_analysis_trends():
    """HTMX endpoint for refreshing trends card."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from datetime import datetime, timedelta, timezone
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        trends = {
            'security_this_week': SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= week_ago).count(),
            'performance_this_week': PerformanceTest.query.filter(PerformanceTest.created_at >= week_ago).count()
        }
        return render_template('partials/analysis/trends.html', trends=trends)
    except Exception as e:
        logger.error(f"HTMX trends error: {e}")
        return render_template('partials/common/error.html', error='Failed to load trends'), 500

@analysis_bp.get('/api/recent/security')
@rate_limited(2.5)
def htmx_recent_security():
    """HTMX endpoint for recent security analyses list."""
    try:
        from ..models import SecurityAnalysis
        from sqlalchemy import desc
        recent_security = SecurityAnalysis.query.order_by(desc(SecurityAnalysis.created_at)).limit(5).all()
        return render_template('partials/analysis/recent_security.html', recent_security=recent_security)
    except Exception as e:
        logger.error(f"HTMX recent security error: {e}")
        return render_template('partials/common/error.html', error='Failed to load security list'), 500

@analysis_bp.get('/api/recent/performance')
@rate_limited(2.5)
def htmx_recent_performance():
    """HTMX endpoint for recent performance tests list."""
    try:
        from ..models import PerformanceTest
        from sqlalchemy import desc
        recent_performance = PerformanceTest.query.order_by(desc(PerformanceTest.created_at)).limit(5).all()
        return render_template('partials/analysis/recent_performance.html', recent_performance=recent_performance)
    except Exception as e:
        logger.error(f"HTMX recent performance error: {e}")
        return render_template('partials/common/error.html', error='Failed to load performance list'), 500


@analysis_bp.route('/security/start', methods=['POST'])
def start_security_analysis():
    """Start security analysis using service-layer to persist config and results."""
    try:
        # Accept both JSON and form-encoded data
        payload = request.get_json(silent=True) or request.form.to_dict()

        # Resolve application
        app_id = payload.get('app_id')
        if not app_id:
            # Support model_slug + app_number in form submissions
            model_slug = payload.get('model_slug')
            app_number = payload.get('app_number')
            if not model_slug or not app_number:
                return jsonify({'error': 'Application ID or (model_slug + app_number) required'}), 400
            try:
                app_number = int(app_number)
            except (TypeError, ValueError):
                return jsonify({'error': 'app_number must be an integer'}), 400
            app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
            if not app:
                return jsonify({'error': 'Application not found for given model/app'}), 404
            app_id = app.id
        else:
            try:
                app_id = int(app_id)
            except (TypeError, ValueError):
                return jsonify({'error': 'app_id must be an integer'}), 400

        # Build create payload with flags
        create_payload = {
            'application_id': app_id,
            'analysis_name': payload.get('analysis_name') or 'Security Analysis',
            'description': payload.get('description')
        }
        # Flags
        for flag in ['bandit_enabled','safety_enabled','pylint_enabled','eslint_enabled','npm_audit_enabled','snyk_enabled','zap_enabled','semgrep_enabled']:
            if flag in payload:
                # Treat any truthy string as True for form posts
                val = payload.get(flag)
                create_payload[flag] = (str(val).lower() in ['1','true','on','yes'])

        # Create analysis record
        from ..services import analysis_service as svc
        created = svc.create_security_analysis(create_payload)

        # Optional: apply advanced configs via update
        update_payload = {'analysis_id': created['id']}
        # Pattern lists if present (comma-separated)
        if payload.get('include_patterns'):
            update_payload['include_patterns'] = [p.strip() for p in str(payload['include_patterns']).split(',') if p.strip()]
        if payload.get('exclude_patterns'):
            update_payload['exclude_patterns'] = [p.strip() for p in str(payload['exclude_patterns']).split(',') if p.strip()]
        # Timeout and thresholds
        for f in ['severity_threshold','max_issues_per_tool','timeout_minutes']:
            if f in payload:
                update_payload[f] = payload[f]
        # Tool configs as JSON strings
        import json
        for cfg_key in ['bandit_config','safety_config','eslint_config','pylint_config','zap_config','global_config']:
            if cfg_key in payload and payload[cfg_key]:
                try:
                    update_payload[cfg_key] = json.loads(payload[cfg_key]) if isinstance(payload[cfg_key], str) else payload[cfg_key]
                except json.JSONDecodeError:
                    pass  # ignore invalid JSON silently for now
        # Persist updates if any
        if len(update_payload) > 1:
            svc.update_security_analysis(created['id'], update_payload)

        # Start analysis via Celery-backed path that persists results
        started = svc.start_security_analysis(created['id'])

        # Return a small HTMX-friendly partial by default
        return render_template('partials/analysis/create/start_result.html',
                               title='Security analysis started',
                               task_id=started.get('task_id'),
                               analysis_id=created['id'],
                               analysis_type='security')

    except Exception as e:
        logger.error(f"Error starting security analysis: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.route('/performance/start', methods=['POST'])
def start_performance_test():
    """Start performance test for an application."""
    try:
        is_htmx = request.headers.get('HX-Request') == 'true'
        data = request.get_json(silent=True)

        # Accept form submissions as well
        if data is None:
            form = request.form
            model_slug = form.get('model_slug')
            app_number = form.get('app_number')
            try:
                app_number = int(app_number) if app_number not in (None, '') else None
            except ValueError:
                app_number = None
            if not (model_slug and app_number):
                return (render_template('partials/common/error.html', error='Model and app number required'), 400) if is_htmx \
                       else (jsonify({'error': 'Model and app number required'}), 400)
            app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
            if not app:
                return (render_template('partials/common/error.html', error='Application not found'), 404) if is_htmx \
                       else (jsonify({'error': 'Application not found'}), 404)

            # Test configuration from form
            def _to_int(val, default):
                try:
                    return int(val)
                except Exception:
                    return default
            def _to_float(val, default):
                try:
                    return float(val)
                except Exception:
                    return default

            test_config = {
                'test_type': form.get('test_type', 'load'),
                'users': _to_int(form.get('users', 10), 10),
                'spawn_rate': _to_float(form.get('spawn_rate', 1.0), 1.0),
                'duration': _to_int(form.get('duration', 60), 60)
            }
            # Create PerformanceTest record via service for integrity
            from ..services import analysis_service as svc
            created = svc.create_performance_test({
                'application_id': app.id,
                'test_type': test_config['test_type'],
                'users': test_config['users'],
                'spawn_rate': test_config['spawn_rate'],
                'test_duration': test_config['duration']
            })
            _ = svc.start_performance_test(created['id'])
        else:
            app_id = data.get('app_id')
            if not app_id:
                return jsonify({'error': 'Application ID required'}), 400
            app = GeneratedApplication.query.get_or_404(app_id)
            test_config = {
                'test_type': data.get('test_type', 'load'),
                'users': data.get('users', 10),
                'spawn_rate': data.get('spawn_rate', 1.0),
                'duration': data.get('duration', 60)
            }
            # Create PerformanceTest record via service for integrity
            from ..services import analysis_service as svc
            created = svc.create_performance_test({
                'application_id': app.id,
                'test_type': test_config['test_type'],
                'users': test_config['users'],
                'spawn_rate': test_config['spawn_rate'],
                'test_duration': test_config['duration']
            })
            _ = svc.start_performance_test(created['id'])

        # Optionally also enqueue background execution tracking via TaskManager
        try:
            task_id = task_manager.start_performance_test(
                app.model_slug,
                app.app_number,
                test_config
            )
        except Exception:
            task_id = None

        if is_htmx:
            return render_template('partials/analysis/create/start_result.html',
                                   title='Performance test started',
                                   task_id=task_id,
                                   analysis_id=created['id'],
                                   analysis_type='performance')

        return jsonify({
            'success': True,
            'task_id': task_id,
            'analysis_id': created['id'],
            'message': 'Performance test started'
        })

    except Exception as e:
        logger.error(f"Error starting performance test: {e}")
        return (render_template('partials/common/error.html', error=str(e)), 500) if request.headers.get('HX-Request') == 'true' \
               else (jsonify({'error': str(e)}), 500)


@analysis_bp.route('/dynamic/start', methods=['POST'])
def start_dynamic_analysis():
    """Start dynamic (ZAP-like) analysis through service layer (DB-backed)."""
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()

        # Resolve application
        app_id = payload.get('app_id')
        if not app_id:
            model_slug = payload.get('model_slug')
            app_number = payload.get('app_number')
            if not model_slug or not app_number:
                return render_template('partials/common/error.html', error='model_slug and app_number are required'), 400
            try:
                app_number = int(app_number)
            except (TypeError, ValueError):
                return render_template('partials/common/error.html', error='app_number must be an integer'), 400
            app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
            if not app:
                return render_template('partials/common/error.html', error='Application not found for given model/app'), 404
            app_id = app.id
        else:
            try:
                app_id = int(app_id)
            except (TypeError, ValueError):
                return render_template('partials/common/error.html', error='app_id must be an integer'), 400

        # Build create payload
        # If target_url omitted, leave empty; analyzer task may infer from port mapping
        create_payload = {
            'application_id': app_id,
            'target_url': payload.get('target_url', '') or '' ,
            'scan_type': payload.get('scan_type', 'baseline')
        }
        # Optional include/exclude path lists: accept comma-separated strings or arrays
        if payload.get('include_paths'):
            val = payload.get('include_paths')
            if isinstance(val, str):
                create_payload['include_paths'] = [p.strip() for p in val.split(',') if p.strip()]
            elif isinstance(val, list):
                create_payload['include_paths'] = val
        if payload.get('exclude_paths'):
            val = payload.get('exclude_paths')
            if isinstance(val, str):
                create_payload['exclude_paths'] = [p.strip() for p in val.split(',') if p.strip()]
            elif isinstance(val, list):
                create_payload['exclude_paths'] = val
        # Timeout in minutes
        if 'timeout' in payload and payload.get('timeout') not in (None, ''):
            try:
                create_payload['timeout_minutes'] = int(str(payload.get('timeout')).strip())
            except Exception:
                # Ignore invalid timeout formats silently for now
                pass

        # Persist analysis and start
        from ..services import analysis_service as svc
        created = svc.create_dynamic_analysis(create_payload)
        started = svc.start_dynamic_analysis(created['id'])

        return render_template('partials/analysis/create/start_result.html',
                               title='Dynamic analysis started',
                               task_id=started.get('task_id'),
                               analysis_id=created['id'],
                               analysis_type='dynamic')

    except Exception as e:
        logger.error(f"Error starting dynamic analysis: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.route('/batch/start', methods=['POST'])
def start_batch_analysis():
    """Start batch analysis job."""
    try:
        # Support both JSON and form-encoded submissions (HTMX)
        is_htmx = request.headers.get('HX-Request') == 'true'
        payload_json = request.get_json(silent=True)

        if payload_json is not None:
            models = payload_json.get('models') or payload_json.get('model_filter') or []
            apps = payload_json.get('apps') or payload_json.get('app_filter') or []
            analysis_types = payload_json.get('analysis_types', [])
            priority = payload_json.get('priority', 'normal')
            options = payload_json.get('options', {}) or {}
            # Normalize nested options if passed flat
            if 'security_tools' in payload_json and isinstance(payload_json.get('security_tools'), list):
                options['security_tools'] = payload_json.get('security_tools')
            if 'static_tools' in payload_json and isinstance(payload_json.get('static_tools'), list):
                options['static_tools'] = payload_json.get('static_tools')
            # Performance config
            perf = options.get('performance_config', {}) or {}
            for k_json, k_opt in [('perf_users','users'),('perf_spawn_rate','spawn_rate'),('perf_duration','duration'),('perf_type','test_type')]:
                if k_json in payload_json:
                    perf[k_opt] = payload_json.get(k_json)
            if perf:
                options['performance_config'] = perf
            # Dynamic options
            dyn = options.get('dynamic_options', {}) or {}
            if 'dynamic_scan_type' in payload_json:
                dyn['scan_type'] = payload_json.get('dynamic_scan_type')
            if 'dynamic_target_url' in payload_json:
                dyn['target_url'] = payload_json.get('dynamic_target_url')
            if dyn:
                options['dynamic_options'] = dyn
            # AI
            if 'ai_types' in payload_json and isinstance(payload_json.get('ai_types'), list):
                options['ai_types'] = payload_json.get('ai_types')
        else:
            # Form data path
            form = request.form
            # Multi-selects and checkboxes
            models = form.getlist('models') or form.getlist('model_filter')
            analysis_types = form.getlist('analysis_types') or form.getlist('analysis_types[]')
            priority = form.get('priority', 'normal')

            # Apps: from CSV or range inputs
            apps = []
            # CSV list
            csv_apps = form.get('app_numbers', '')
            if csv_apps:
                for part in csv_apps.split(','):
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        apps.append(int(part))
                    except ValueError:
                        pass
            # Range inputs
            start_s = form.get('app_range_start', '').strip()
            end_s = form.get('app_range_end', '').strip()
            if start_s and end_s:
                try:
                    start_i, end_i = int(start_s), int(end_s)
                    if start_i <= end_i:
                        apps.extend(list(range(start_i, end_i + 1)))
                except ValueError:
                    pass

            # Options (best-effort parsing)
            options = {}
            if form.get('continue_on_error'):
                options['continue_on_error'] = str(form.get('continue_on_error')).lower() in ['1','true','on','yes']
            if form.get('parallelism'):
                try:
                    options['parallelism'] = int(str(form.get('parallelism') or ''))
                except ValueError:
                    pass
            if form.get('timeout_minutes'):
                try:
                    options['timeout_minutes'] = int(str(form.get('timeout_minutes') or ''))
                except ValueError:
                    pass
            options['priority'] = priority

            # Type-specific options
            # Security tools (multi checkbox named security_tools)
            sec_tools = form.getlist('security_tools')
            if sec_tools:
                options['security_tools'] = sec_tools
            # Optional severity threshold
            if form.get('security_severity'):
                options.setdefault('security_options', {})['severity_threshold'] = form.get('security_severity')
            # Static tools
            static_tools = form.getlist('static_tools')
            if static_tools:
                options['static_tools'] = static_tools
            # Performance config
            perf_cfg = {}
            if form.get('perf_users'):
                try:
                    perf_cfg['users'] = int(str(form.get('perf_users') or ''))
                except Exception:
                    pass
            if form.get('perf_spawn_rate'):
                try:
                    perf_cfg['spawn_rate'] = float(str(form.get('perf_spawn_rate') or ''))
                except Exception:
                    pass
            if form.get('perf_duration'):
                try:
                    perf_cfg['duration'] = int(str(form.get('perf_duration') or ''))
                except Exception:
                    pass
            if form.get('perf_type'):
                perf_cfg['test_type'] = form.get('perf_type')
            if perf_cfg:
                options['performance_config'] = perf_cfg
            # Dynamic options
            dyn_opts = {}
            if form.get('dynamic_scan_type'):
                dyn_opts['scan_type'] = form.get('dynamic_scan_type')
            if form.get('dynamic_target_url'):
                dyn_opts['target_url'] = form.get('dynamic_target_url')
            if dyn_opts:
                options['dynamic_options'] = dyn_opts
            # AI types
            ai_types = form.getlist('ai_types')
            if ai_types:
                options['ai_types'] = ai_types

        # --- Normalize & validate inputs ---
        # Sanitize models: drop blanks/whitespace and de-duplicate
        try:
            models = [str(m).strip() for m in (models or []) if str(m).strip()]
            # Sort for determinism
            models = sorted(set(models))
        except Exception:
            models = []

        # Validation
        if not analysis_types:
            # Decide response type based on HTMX
            if is_htmx:
                return render_template('partials/common/error.html', error='Select at least one analysis type'), 400
            return jsonify({'error': 'At least one analysis type required'}), 400

        # Require at least one model. Apps alone are ambiguous for source path resolution.
        if not models:
            msg = 'Select at least one model to run analyses.'
            if is_htmx:
                return render_template('partials/common/error.html', error=msg), 400
            return jsonify({'error': msg}), 400

        # If apps empty but models provided, include all apps for those models
        if (not apps) and models:
            try:
                from ..models import GeneratedApplication as GA
                q = GA.query.filter(GA.model_slug.in_(models)).with_entities(GA.app_number).distinct()
                apps = sorted({row.app_number for row in q})
            except Exception as ie:
                logger.warning(f"Could not auto-expand apps for models {models}: {ie}")
                apps = []

        # Ensure types
        try:
            apps = [int(a) for a in apps]
        except Exception:
            # If apps contain non-ints, ignore invalid values
            cleaned = []
            for a in apps:
                try:
                    cleaned.append(int(a))
                except Exception:
                    continue
            apps = cleaned

        # Start batch analysis (returns task id)
        task_id = task_manager.start_batch_analysis(
            models=models or [],
            apps=apps or [],
            analysis_types=analysis_types,
            options=options or {}
        )

        if is_htmx:
            # HTMX-friendly partial response
            return render_template('partials/analysis/create/start_result.html',
                                   title='Batch analysis started',
                                   task_id=task_id,
                                   analysis_type='batch')

        # JSON fallback
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Batch analysis started'
        })
        
    except Exception as e:
        logger.error(f"Error starting batch analysis: {e}")
        # Prefer HTML error for HTMX
        if request.headers.get('HX-Request') == 'true':
            return render_template('partials/common/error.html', error=str(e)), 500
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/security_test_form')
def security_test_form():
    """HTMX endpoint for security test form."""
    from ..models import ModelCapability
    
    try:
        models = ModelCapability.query.all()
        return render_template('partials/analysis/create/security_test_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading security test form: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading security test form: {str(e)}")


@analysis_bp.route('/performance_test_form')
def performance_test_form():
    """HTMX endpoint for performance test form."""
    from ..models import ModelCapability
    try:
        models = ModelCapability.query.all()
        return render_template('partials/analysis/create/performance_test_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading performance test form: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading performance test form: {str(e)}")


@analysis_bp.route('/dynamic_test_form')
def dynamic_test_form():
    """HTMX endpoint for dynamic (ZAP) test form."""
    from ..models import ModelCapability
    try:
        models = ModelCapability.query.all()
        return render_template('partials/analysis/create/dynamic_test_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading dynamic test form: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading dynamic test form: {str(e)}")


@analysis_bp.route('/batch_test_form')
def batch_test_form():
    """HTMX endpoint for batch analysis form (Create page)."""
    try:
        from ..models import ModelCapability
        models = ModelCapability.query.all()
        return render_template('partials/analysis/create/batch_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading batch test form: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading batch test form: {str(e)}"), 500


@analysis_bp.route('/security/run', methods=['POST'])
def run_security_test():
    """Run security test (alias for start_security_analysis)."""
    return start_security_analysis()


@analysis_bp.route('/performance/run', methods=['POST'])
def run_performance_test():
    """Run performance test (alias for start_performance_test)."""
    return start_performance_test()


@analysis_bp.route('/dynamic/run', methods=['POST'])
def run_dynamic_test():
    """Run dynamic test (alias for start_dynamic_analysis)."""
    return start_dynamic_analysis()


@analysis_bp.route('/get_model_apps')
def get_model_apps():
    """HTMX endpoint to get applications for a model."""
    from ..models import GeneratedApplication
    from flask import request
    
    model_slug = request.args.get('model_slug')
    select_id = request.args.get('select_id')
    apps = []
    
    if model_slug:
        try:
            apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        except Exception as e:
            logger.error(f"Error getting apps for model {model_slug}: {e}")
    
    return render_template('partials/common/model_apps_select.html', 
                         apps=apps, 
                         model_slug=model_slug,
                         select_id=select_id)


@analysis_bp.route('/dynamic/<int:analysis_id>')
def dynamic_analysis_results_view(analysis_id: int):
    """HTML view for dynamic (ZAP) analysis results."""
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import ZAPAnalysis

        from app.extensions import get_session
        with get_session() as _s:
            analysis = _s.get(ZAPAnalysis, analysis_id)
        if not analysis:
            flash('Dynamic analysis not found', 'error')
            return redirect(url_for('analysis.analysis_hub'))

        zap_report = analysis.get_zap_report() if hasattr(analysis, 'get_zap_report') else {}
        metadata = analysis.get_metadata() if hasattr(analysis, 'get_metadata') else {}

        # Derive basic stats if not already populated
        high = analysis.high_risk_alerts or 0
        medium = analysis.medium_risk_alerts or 0
        low = analysis.low_risk_alerts or 0
        info = analysis.informational_alerts or 0

        # Fallback: compute counts from report if needed
        try:
            if (high + medium + low + info) == 0 and zap_report and 'site' in zap_report and zap_report['site']:
                alerts = zap_report['site'][0].get('alerts', [])
                for alert in alerts:
                    risk_code = int(alert.get('riskcode', 0))
                    if risk_code == 3:
                        high += 1
                    elif risk_code == 2:
                        medium += 1
                    elif risk_code == 1:
                        low += 1
                    else:
                        info += 1
        except Exception:  # pragma: no cover - defensive
            pass

        return render_template(
            'single_page.html',
            page_title='Dynamic Security Analysis',
            page_icon='fa-bolt',
            page_subtitle=f"ZAP Scan #{analysis.id}",
            main_partial='partials/analysis/dynamic_complete.html',
            analysis=analysis,
            zap_report=zap_report,
            metadata=metadata,
            counts={
                'high': high,
                'medium': medium,
                'low': low,
                'info': info,
            }
        )
    except Exception as e:
        logger.error(f"Error rendering dynamic analysis results for {analysis_id}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading dynamic analysis results: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))

@analysis_bp.route('/security/<int:analysis_id>')
def security_analysis_short_redirect(analysis_id: int):
    """Short URL to view security results; redirects to the canonical results view."""
    try:
        from flask import redirect, url_for
        return redirect(url_for('analysis.security_analysis_results_view', analysis_id=analysis_id))
    except Exception:
        # Fallback to hub if url_for fails for any reason
        from flask import redirect, url_for
        return redirect(url_for('analysis.analysis_hub'))


@analysis_bp.route('/security/<int:analysis_id>/results/view')
def security_analysis_results_view(analysis_id):
    """HTML view for security analysis results."""
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import SecurityAnalysis
        import json
        
        from app.extensions import get_session
        with get_session() as _s:
            analysis = _s.get(SecurityAnalysis, analysis_id)
        if not analysis:
            flash('Security analysis not found', 'error')
            return redirect(url_for('analysis.analysis_hub'))
        
        # Initialize results data
        bandit_results = None
        safety_results = None
        zap_results = None
        pylint_results = None
        eslint_results = None
        
        # Parse individual tool results from results_json
        if hasattr(analysis, 'results_json') and analysis.results_json:
            try:
                all_results = json.loads(analysis.results_json)
                bandit_results = all_results.get('bandit')
                safety_results = all_results.get('safety')
                zap_results = all_results.get('zap')
                pylint_results = all_results.get('pylint')
                eslint_results = all_results.get('eslint')
            except json.JSONDecodeError:
                # If parsing fails, set all to None
                pass
        
        # Get tool configurations
        bandit_config = analysis.get_bandit_config() if hasattr(analysis, 'get_bandit_config') else {}
        safety_config = analysis.get_safety_config() if hasattr(analysis, 'get_safety_config') else {}
        eslint_config = analysis.get_eslint_config() if hasattr(analysis, 'get_eslint_config') else {}
        pylint_config = analysis.get_pylint_config() if hasattr(analysis, 'get_pylint_config') else {}
        zap_config = analysis.get_zap_config() if hasattr(analysis, 'get_zap_config') else {}
        
        # Get analysis metadata
        analysis_metadata = analysis.get_metadata() if hasattr(analysis, 'get_metadata') else {}

        # Calculate summary metrics
        total_vulnerabilities = 0
        critical_high_count = 0
        tools_executed = 0
        
        # Count Bandit vulnerabilities
        if bandit_results and 'results' in bandit_results:
            bandit_count = len(bandit_results['results'])
            total_vulnerabilities += bandit_count
            tools_executed += 1
            # Count high/critical severity in Bandit
            for result in bandit_results['results']:
                if result.get('issue_severity', '').lower() in ['high', 'critical']:
                    critical_high_count += 1
        
        # Count Safety vulnerabilities
        if safety_results and 'vulnerabilities' in safety_results:
            safety_count = len(safety_results['vulnerabilities'])
            total_vulnerabilities += safety_count
            tools_executed += 1
            # Safety vulnerabilities are typically high severity by nature
            critical_high_count += safety_count
        
        # Count OWASP ZAP vulnerabilities
        if zap_results and 'site' in zap_results and zap_results['site']:
            if 'alerts' in zap_results['site'][0]:
                zap_count = len(zap_results['site'][0]['alerts'])
                total_vulnerabilities += zap_count
                tools_executed += 1
                # Count high risk alerts (riskcode 2-3)
                for alert in zap_results['site'][0]['alerts']:
                    if alert.get('riskcode', 0) >= 2:
                        critical_high_count += 1
        
        # Count Pylint issues
        if pylint_results:
            pylint_count = len(pylint_results)
            total_vulnerabilities += pylint_count
            tools_executed += 1
            # Count errors as high severity
            for result in pylint_results:
                if result.get('type', '') == 'error':
                    critical_high_count += 1
        
        # Count ESLint issues
        if eslint_results:
            eslint_count = 0
            for file_result in eslint_results:
                if 'messages' in file_result:
                    eslint_count += len(file_result['messages'])
                    # Count severity 2 (errors) as high severity
                    for message in file_result['messages']:
                        if message.get('severity', 0) == 2:
                            critical_high_count += 1
            total_vulnerabilities += eslint_count
            tools_executed += 1
        
        # Calculate scan duration (handle naive vs aware datetimes safely)
        scan_duration = 'N/A'
        if analysis.started_at and analysis.completed_at:
            try:
                from datetime import timezone as _tz
                sa = analysis.started_at
                ca = analysis.completed_at
                if sa.tzinfo is None:
                    sa = sa.replace(tzinfo=_tz.utc)
                else:
                    sa = sa.astimezone(_tz.utc)
                if ca.tzinfo is None:
                    ca = ca.replace(tzinfo=_tz.utc)
                else:
                    ca = ca.astimezone(_tz.utc)
                duration = ca - sa
                total = int(duration.total_seconds())
                if total < 60:
                    scan_duration = f"{total}s"
                else:
                    scan_duration = f"{total // 60}m {total % 60}s"
            except Exception:
                scan_duration = 'N/A'
        
        # Prepare severity distribution for charts
        severity_distribution = {
            'Critical': 0,
            'High': 0,
            'Medium': 0,
            'Low': 0,
            'Info': 0
        }
        
        tool_distribution = {
            'Bandit': len(bandit_results['results']) if bandit_results and 'results' in bandit_results else 0,
            'Safety': len(safety_results['vulnerabilities']) if safety_results and 'vulnerabilities' in safety_results else 0,
            'OWASP ZAP': len(zap_results['site'][0]['alerts']) if zap_results and 'site' in zap_results and zap_results['site'] and 'alerts' in zap_results['site'][0] else 0,
            'Pylint': len(pylint_results) if pylint_results else 0,
            'ESLint': sum(len(f.get('messages', [])) for f in eslint_results) if eslint_results else 0
        }
        
        # Count severity levels for Bandit
        if bandit_results and 'results' in bandit_results:
            for result in bandit_results['results']:
                severity = result.get('issue_severity', '').title()
                if severity in severity_distribution:
                    severity_distribution[severity] += 1
        
        # Count severity levels for ZAP
        if zap_results and 'site' in zap_results and zap_results['site']:
            if 'alerts' in zap_results['site'][0]:
                for alert in zap_results['site'][0]['alerts']:
                    risk_code = alert.get('riskcode', 0)
                    if risk_code == 3:
                        severity_distribution['High'] += 1
                    elif risk_code == 2:
                        severity_distribution['Medium'] += 1
                    elif risk_code == 1:
                        severity_distribution['Low'] += 1
                    else:
                        severity_distribution['Info'] += 1
        
        return render_template(
            'single_page.html',
            page_title='Security Analysis Complete',
            page_icon='fa-shield-alt',
            page_subtitle=f"Analysis #{analysis.id}",
            main_partial='partials/analysis/security_complete.html',
            analysis=analysis,
            bandit_results=bandit_results,
            safety_results=safety_results,
            zap_results=zap_results,
            pylint_results=pylint_results,
            eslint_results=eslint_results,
            bandit_config=bandit_config,
            safety_config=safety_config,
            eslint_config=eslint_config,
            pylint_config=pylint_config,
            zap_config=zap_config,
            analysis_metadata=analysis_metadata,
            total_vulnerabilities=total_vulnerabilities,
            critical_high_count=critical_high_count,
            tools_executed=tools_executed,
            scan_duration=scan_duration,
            severity_distribution=severity_distribution,
            tool_distribution=tool_distribution
        )
        
    except Exception as e:
        logger.error(f"Error rendering security analysis results for {analysis_id}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading results: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))


@analysis_bp.route('/performance/<int:analysis_id>')
def performance_test_results_view(analysis_id: int):
    """HTML view for performance test results."""
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import PerformanceTest

        from app.extensions import get_session
        with get_session() as _s:
            test = _s.get(PerformanceTest, analysis_id)
        if not test:
            flash('Performance test not found', 'error')
            return redirect(url_for('analysis.analysis_hub'))

        results = test.get_results() if hasattr(test, 'get_results') else {}
        metadata = test.get_metadata() if hasattr(test, 'get_metadata') else {}

        return render_template(
            'single_page.html',
            page_title='Performance Test Results',
            page_icon='fa-tachometer-alt',
            page_subtitle=f"Test #{test.id}",
            main_partial='partials/analysis/performance_complete.html',
            test=test,
            results=results,
            metadata=metadata
        )
    except Exception as e:
        logger.error(f"Error rendering performance test results for {analysis_id}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading performance results: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))


@analysis_bp.route('/security/<int:analysis_id>/export')
def export_security_analysis(analysis_id: int):
    """Export security analysis results as JSON."""
    try:
        from flask import jsonify
        from ..models import SecurityAnalysis
        from app.extensions import get_session
        with get_session() as _s:
            analysis = _s.get(SecurityAnalysis, analysis_id)
        if not analysis:
            return jsonify({'success': False, 'error': 'Security analysis not found'}), 404
        return jsonify({
            'success': True,
            'id': analysis.id,
            'application_id': analysis.application_id,
            'status': analysis.status,
            'results': analysis.get_results(),
            'metadata': analysis.get_metadata(),
        })
    except Exception as e:
        logger.error(f"Error exporting security analysis {analysis_id}: {e}")
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500


@analysis_bp.route('/performance/<int:analysis_id>/export')
def export_performance_test(analysis_id: int):
    """Export performance test results as JSON."""
    try:
        from flask import jsonify
        from ..models import PerformanceTest
        from app.extensions import get_session
        with get_session() as _s:
            test = _s.get(PerformanceTest, analysis_id)
        if not test:
            return jsonify({'success': False, 'error': 'Performance test not found'}), 404
        return jsonify({
            'success': True,
            'id': test.id,
            'application_id': test.application_id,
            'status': test.status,
            'results': test.get_results(),
            'metadata': test.get_metadata(),
        })
    except Exception as e:
        logger.error(f"Error exporting performance test {analysis_id}: {e}")
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500


@analysis_bp.get('/api/security/<int:analysis_id>/tools-status')
def htmx_security_tools_status(analysis_id: int):
    """HTMX endpoint to render current per-tool progress/status for a SecurityAnalysis.

    Returns a self-contained fragment that continues polling while the
    analysis is PENDING/RUNNING and stops polling when COMPLETED/FAILED
    by omitting hx attributes in the returned wrapper.
    """
    try:
        from ..models import SecurityAnalysis
        from app.extensions import get_session
        with get_session() as _s:
            analysis = _s.get(SecurityAnalysis, analysis_id)
        if not analysis:
            return render_template('partials/common/error.html', error='Security analysis not found'), 404

        # Parse results JSON for per-tool presence
        all_results = {}
        try:
            all_results = analysis.get_results() or {}
        except Exception:
            all_results = {}

        # Build tool status list
        def _tool(name: str, enabled: bool, key: str):
            present = key in all_results and all_results.get(key) is not None
            if not enabled:
                status = 'disabled'
            elif analysis.status == AnalysisStatus.FAILED:
                status = 'failed'
            elif present:
                status = 'completed'
            elif analysis.status in (AnalysisStatus.RUNNING, AnalysisStatus.PENDING):
                status = 'running'
            else:
                status = 'pending'

            # Compute simple counts when present
            count = None
            try:
                if present:
                    res = all_results.get(key) or {}
                    if key == 'bandit':
                        count = len(res.get('results', []) or [])
                    elif key == 'safety':
                        count = len(res.get('vulnerabilities', []) or [])
                    elif key == 'eslint':
                        count = sum(len(f.get('messages', [])) for f in (res or [])) if isinstance(res, list) else 0
                    elif key == 'pylint':
                        count = len(res or []) if isinstance(res, list) else 0
                    elif key == 'zap':
                        if isinstance(res, dict) and res.get('site'):
                            count = len((res['site'][0] or {}).get('alerts', []) or [])
            except Exception:
                count = None

            return {
                'name': name,
                'key': key,
                'enabled': enabled,
                'status': status,
                'count': count
            }

        tools = [
            _tool('Bandit', getattr(analysis, 'bandit_enabled', False), 'bandit'),
            _tool('Safety', getattr(analysis, 'safety_enabled', False), 'safety'),
            _tool('PyLint', getattr(analysis, 'pylint_enabled', False), 'pylint'),
            _tool('ESLint', getattr(analysis, 'eslint_enabled', False), 'eslint'),
            _tool('npm audit', getattr(analysis, 'npm_audit_enabled', False), 'npm_audit'),
            _tool('Snyk', getattr(analysis, 'snyk_enabled', False), 'snyk'),
            _tool('Semgrep', getattr(analysis, 'semgrep_enabled', False), 'semgrep'),
            _tool('ZAP', getattr(analysis, 'zap_enabled', False), 'zap'),
        ]

        return render_template('partials/analysis/security_tools_status.html',
                               analysis=analysis,
                               tools=tools)
    except Exception as e:
        logger.error(f"HTMX security tools status error: {e}")
        return render_template('partials/common/error.html', error='Failed to load tools status'), 500


@analysis_bp.route('/security/<int:analysis_id>/results/complete')
def security_analysis_complete_view(analysis_id):
    """Complete HTML view for security analysis with all configurations and metadata."""
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import SecurityAnalysis
        import json
        
        from app.extensions import get_session
        with get_session() as _s:
            analysis = _s.get(SecurityAnalysis, analysis_id)
        if not analysis:
            flash('Security analysis not found', 'error')
            return redirect(url_for('analysis.analysis_hub'))
        
        # Initialize results data
        bandit_results = None
        safety_results = None
        zap_results = None
        pylint_results = None
        eslint_results = None
        
        # Parse individual tool results from results_json
        if hasattr(analysis, 'results_json') and analysis.results_json:
            try:
                all_results = json.loads(analysis.results_json)
                bandit_results = all_results.get('bandit')
                safety_results = all_results.get('safety')
                zap_results = all_results.get('zap')
                pylint_results = all_results.get('pylint')
                eslint_results = all_results.get('eslint')
            except json.JSONDecodeError:
                # If parsing fails, set all to None
                pass
        
        # Get tool configurations - these are the detailed configs
        bandit_config = analysis.get_bandit_config() if hasattr(analysis, 'get_bandit_config') else {}
        safety_config = analysis.get_safety_config() if hasattr(analysis, 'get_safety_config') else {}
        eslint_config = analysis.get_eslint_config() if hasattr(analysis, 'get_eslint_config') else {}
        pylint_config = analysis.get_pylint_config() if hasattr(analysis, 'get_pylint_config') else {}
        zap_config = analysis.get_zap_config() if hasattr(analysis, 'get_zap_config') else {}
        
        # Get analysis metadata
        analysis_metadata = analysis.get_metadata() if hasattr(analysis, 'get_metadata') else {}

        return render_template(
            'single_page.html',
            page_title='Security Analysis (Complete View)',
            page_icon='fa-search',
            page_subtitle=f"Analysis #{analysis.id}",
            main_partial='partials/analysis/security_complete.html',
            analysis=analysis,
            bandit_results=bandit_results,
            safety_results=safety_results,
            zap_results=zap_results,
            pylint_results=pylint_results,
            eslint_results=eslint_results,
            bandit_config=bandit_config,
            safety_config=safety_config,
            eslint_config=eslint_config,
            pylint_config=pylint_config,
            zap_config=zap_config,
            analysis_metadata=analysis_metadata
        )
        
    except Exception as e:
        logger.error(f"Error rendering complete security analysis for {analysis_id}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading complete analysis: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))


# ============================================================================
# Unified Analysis Hub HTMX Endpoints
# ============================================================================

@analysis_bp.get('/api/activity/combined')
@rate_limited(3.0)
def htmx_unified_activity():
    """HTMX endpoint for unified activity timeline across all analysis types."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis
        from datetime import datetime, timezone
        
        # Gather recent activity from all analysis types
        recent_activity = []
        
        # Security analyses
        recent_security = SecurityAnalysis.query.order_by(SecurityAnalysis.created_at.desc()).limit(8).all()
        for analysis in recent_security:
            recent_activity.append({
                'type': 'security',
                'id': analysis.id,
                'model_slug': analysis.model_slug,
                'app_number': analysis.app_number,
                'status': analysis.status,
                'created_at': analysis.created_at,
                'description': f"Security analysis #{analysis.id}"
            })
        
        # Performance tests
        recent_performance = PerformanceTest.query.order_by(PerformanceTest.created_at.desc()).limit(8).all()
        for test in recent_performance:
            recent_activity.append({
                'type': 'performance',
                'id': test.id,
                'model_slug': test.model_slug,
                'app_number': test.app_number,
                'status': test.status,
                'created_at': test.created_at,
                'description': f"Performance test #{test.id}"
            })
        
        # Dynamic analyses
        recent_dynamic = ZAPAnalysis.query.order_by(ZAPAnalysis.created_at.desc()).limit(8).all()
        for analysis in recent_dynamic:
            recent_activity.append({
                'type': 'dynamic',
                'id': analysis.id,
                'model_slug': analysis.model_slug,
                'app_number': analysis.app_number,
                'status': analysis.status,
                'created_at': analysis.created_at,
                'description': f"Dynamic scan #{analysis.id}"
            })
        
        # Sort by date and limit
        recent_activity = sorted(recent_activity, key=lambda x: x['created_at'], reverse=True)[:15]
        
        return render_template('partials/analysis/unified_activity.html', recent_activity=recent_activity)
    except Exception as e:
        logger.error(f"HTMX unified activity error: {e}")
        return render_template('partials/common/error.html', error='Failed to load activity timeline'), 500


@analysis_bp.get('/api/results/summary')
@rate_limited(5.0)
def htmx_results_summary():
    """HTMX endpoint for results overview summary."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis
        from sqlalchemy import func
        from datetime import datetime, timedelta, timezone
        
        # Get completed analyses with results
        completed_security = SecurityAnalysis.query.filter_by(status='completed').count()
        completed_performance = PerformanceTest.query.filter_by(status='completed').count()  
        completed_dynamic = ZAPAnalysis.query.filter_by(status='completed').count()
        
        # Recent completions (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_completions = (
            SecurityAnalysis.query.filter(
                SecurityAnalysis.status == 'completed',
                SecurityAnalysis.completed_at >= week_ago
            ).count() +
            PerformanceTest.query.filter(
                PerformanceTest.status == 'completed', 
                PerformanceTest.completed_at >= week_ago
            ).count() +
            ZAPAnalysis.query.filter(
                ZAPAnalysis.status == 'completed',
                ZAPAnalysis.completed_at >= week_ago
            ).count()
        )
        
        # Latest completed analyses for preview
        latest_results = []
        
        # Get latest from each type
        latest_security = SecurityAnalysis.query.filter_by(status='completed').order_by(SecurityAnalysis.completed_at.desc()).first()
        if latest_security:
            latest_results.append({
                'type': 'security',
                'id': latest_security.id,
                'model_slug': latest_security.model_slug,
                'app_number': latest_security.app_number,
                'completed_at': latest_security.completed_at,
                'title': f'Security Analysis #{latest_security.id}'
            })
            
        latest_performance = PerformanceTest.query.filter_by(status='completed').order_by(PerformanceTest.completed_at.desc()).first()
        if latest_performance:
            latest_results.append({
                'type': 'performance',
                'id': latest_performance.id,
                'model_slug': latest_performance.model_slug,
                'app_number': latest_performance.app_number,
                'completed_at': latest_performance.completed_at,
                'title': f'Performance Test #{latest_performance.id}'
            })
            
        latest_dynamic = ZAPAnalysis.query.filter_by(status='completed').order_by(ZAPAnalysis.completed_at.desc()).first()
        if latest_dynamic:
            latest_results.append({
                'type': 'dynamic',
                'id': latest_dynamic.id,
                'model_slug': latest_dynamic.model_slug,
                'app_number': latest_dynamic.app_number,
                'completed_at': latest_dynamic.completed_at,
                'title': f'Dynamic Scan #{latest_dynamic.id}'
            })
        
        # Sort by completion date
        latest_results = sorted(latest_results, key=lambda x: x['completed_at'], reverse=True)
        
        summary = {
            'total_completed': completed_security + completed_performance + completed_dynamic,
            'completed_security': completed_security,
            'completed_performance': completed_performance,
            'completed_dynamic': completed_dynamic,
            'recent_completions': recent_completions,
            'latest_results': latest_results[:5]
        }
        
        return render_template('partials/analysis/results_summary.html', summary=summary)
    except Exception as e:
        logger.error(f"HTMX results summary error: {e}")
        return render_template('partials/common/error.html', error='Failed to load results summary'), 500


@analysis_bp.get('/api/system/health')
@rate_limited(3.0)
def htmx_system_health():
    """HTMX endpoint for system health monitoring."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis
        import psutil
        
        # Get system resource usage
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
        except Exception:
            # Fallback values if psutil not available
            cpu_usage = 45.2
            memory_usage = 62.8
        
        # Running analyses count
        running_analyses = (
            SecurityAnalysis.query.filter_by(status='running').count() +
            PerformanceTest.query.filter_by(status='running').count() +
            ZAPAnalysis.query.filter_by(status='running').count()
        )
        
        # Pending analyses count  
        pending_analyses = (
            SecurityAnalysis.query.filter_by(status='pending').count() +
            PerformanceTest.query.filter_by(status='pending').count() +
            ZAPAnalysis.query.filter_by(status='pending').count()
        )
        
        health_data = {
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'active_workers': min(running_analyses, 5),  # Mock max workers
            'max_workers': 5,
            'queue_length': pending_analyses,
            'running_tasks': running_analyses
        }
        
        return render_template('partials/analysis/system_health.html', health=health_data)
    except Exception as e:
        logger.error(f"HTMX system health error: {e}")
        return render_template('partials/common/error.html', error='Failed to load system health'), 500


@analysis_bp.get('/api/batch/summary')  
@rate_limited(4.0)
def htmx_batch_summary():
    """HTMX endpoint for batch operations summary."""
    try:
        from datetime import datetime, timezone
        
        # Mock batch statistics (in real implementation would query batch operations table)
        batch_summary = {
            'total_batches': 12,
            'running': 2,
            'queued': 1,
            'completed_today': 5,
            'recent_batches': [
                {
                    'id': 1,
                    'status': 'running',
                    'created_at': datetime.now(timezone.utc),
                    'progress': 65
                },
                {
                    'id': 2, 
                    'status': 'completed',
                    'created_at': datetime.now(timezone.utc),
                    'progress': 100
                },
                {
                    'id': 3,
                    'status': 'queued', 
                    'created_at': datetime.now(timezone.utc),
                    'progress': 0
                }
            ]
        }
        
        return render_template('partials/analysis/batch_summary.html', batch_stats=batch_summary)
    except Exception as e:
        logger.error(f"HTMX batch summary error: {e}")
        return render_template('partials/common/error.html', error='Failed to load batch summary'), 500


# New: table rows endpoint used by the Research Hub table
@analysis_bp.get('/api/recent/table')
@rate_limited(2.5)
def htmx_recent_table():
    """Return only the <tr> rows for the combined recent analyses table.

    Enables safe initial render with HTMX and lightweight periodic refreshes.
    """
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from sqlalchemy import desc
        security_items = SecurityAnalysis.query.order_by(desc(SecurityAnalysis.created_at)).limit(50).all()
        performance_items = PerformanceTest.query.order_by(desc(PerformanceTest.created_at)).limit(50).all()
        return render_template('partials/analysis/recent_table_rows.html',
                               recent_security=security_items,
                               recent_performance=performance_items)
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"HTMX recent table error: {e}")
        return render_template('partials/common/error.html', error='Failed to load recent table'), 500


# ============================================================================
# Results detail: expanded preview sourced from analyzer/results artifacts
# ============================================================================

@analysis_bp.get('/results/<model_slug>/<int:app_number>')
def analysis_results_detail(model_slug: str, app_number: int):
    """Rich results view combining latest artifacts for the given app."""
    try:
        latest = results_loader.find_latest_results(model_slug, app_number)
        summaries = {k: results_loader.summarize_result(k, v) for k, v in latest.items()}
        return render_template(
            'pages/analysis_result.html',
            model_slug=model_slug,
            app_number=app_number,
            latest=latest,
            summaries=summaries
        )
    except Exception as e:
        logger.error(f"Error rendering results detail for {model_slug} app {app_number}: {e}")
        return render_template('partials/common/error.html', error='Failed to render results detail'), 500


@analysis_bp.get('/results/<model_slug>/<int:app_number>/export')
def analysis_results_export(model_slug: str, app_number: int):
    """Export merged latest results across types as JSON."""
    try:
        latest = results_loader.find_latest_results(model_slug, app_number)
        return jsonify({k: v.get('data') for k, v in latest.items()})
    except Exception as e:
        logger.error(f"Export error for {model_slug} app {app_number}: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Server-Sent Events (SSE) stream for gateway activity feed
# ============================================================================
@analysis_bp.get('/events/stream')
def sse_events_stream():
    """SSE endpoint that bridges WebSocket gateway events to the browser.

    This endpoint connects to the gateway as a subscriber and forwards progress
    updates as text/event-stream. Optional query params:
      - correlation_id: filter to a specific analysis
    """
    import asyncio
    import json
    import threading
    import queue
    import websockets
    import uuid
    from datetime import datetime, timezone

    correlation_id = request.args.get('correlation_id')

    event_queue: "queue.Queue[str]" = queue.Queue(maxsize=1000)
    stop_flag = '__STOP__'

    async def ws_subscriber():
        uri = 'ws://localhost:8765'
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10, close_timeout=5) as ws:
                # Subscribe with replay using raw protocol dict to avoid tight coupling
                sub = {
                    'type': 'status_request',
                    'id': str(uuid.uuid4()),
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'data': {'subscribe': 'events', 'replay': True}
                }
                await ws.send(json.dumps(sub))
                while True:
                    raw = await ws.recv()
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue
                    # Basic filter by correlation_id when provided
                    cid = data.get('correlation_id') or ((data.get('data') or {}).get('correlation_id') if isinstance(data.get('data'), dict) else None)
                    if correlation_id and cid and str(cid) != str(correlation_id):
                        continue
                    evt = f"data: {json.dumps(data)}\n\n"
                    try:
                        event_queue.put_nowait(evt)
                    except queue.Full:
                        # Drop oldest to keep UI responsive
                        try:
                            _ = event_queue.get_nowait()
                        except Exception:
                            pass
                        try:
                            event_queue.put_nowait(evt)
                        except Exception:
                            pass
        except Exception as e:  # pragma: no cover - network errors
            try:
                event_queue.put_nowait(f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n")
            except Exception:
                pass
        finally:
            try:
                event_queue.put_nowait(stop_flag)  # signal generator to finish
            except Exception:
                pass

    # Run the websocket subscriber in a thread with its own loop
    def start_async_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ws_subscriber())

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_async_loop, args=(loop,), daemon=True)
    t.start()

    def gen():
        yield 'event: open\ndata: {"status":"listening"}\n\n'
        while True:
            item = event_queue.get()
            if item == stop_flag:
                break
            yield item

    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'text/event-stream',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
    }
    return Response(gen(), headers=headers)


# ============================================================================
# Lightweight preview endpoints for embedding in Application detail page
# ============================================================================

@analysis_bp.get('/security/<int:analysis_id>/preview')
def security_analysis_preview(analysis_id: int):
    """TODO stub: compact preview for a SecurityAnalysis (to be implemented).

    This endpoint will render a concise, inline preview of a specific
    security analysis suitable for embedding in application pages.
    """
    # TODO: Implement compact preview rendering once Analysis Hub UX is finalized.
    return render_template('partials/common/todo_stub.html',
                           title='Security Analysis Preview',
                           message='Inline preview is coming soon. Open the full results instead.',
                           action_url=f"/analysis/security/{analysis_id}/results/view",
                           action_label='Open full results'), 200


@analysis_bp.get('/dynamic/<int:analysis_id>/preview')
def dynamic_analysis_preview(analysis_id: int):
    """TODO stub: compact preview for a Dynamic (ZAP) analysis (to be implemented)."""
    # TODO: Implement compact preview rendering once Analysis Hub UX is finalized.
    return render_template('partials/common/todo_stub.html',
                           title='Dynamic Analysis Preview',
                           message='Inline preview is coming soon. Open the full results instead.',
                           action_url=f"/analysis/dynamic/{analysis_id}",
                           action_label='Open full results'), 200


# ============================================================================
# Universal Analysis Detail Route
# ============================================================================

@analysis_bp.route('/<int:analysis_id>')
def analysis_detail(analysis_id: int):
    """Universal analysis detail view that works for any analysis type."""
    # from flask import flash
    from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis
    from ..extensions import get_session
    
    # Helper class to make dict data accessible via dot notation
    class DotDict:
        def __init__(self, data):
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        setattr(self, key, DotDict(value))
                    elif isinstance(value, list):
                        setattr(self, key, [DotDict(item) if isinstance(item, dict) else item for item in value])
                    else:
                        setattr(self, key, value)
            else:
                # Handle non-dict data
                pass
        
        def __getattr__(self, name):
            # Return None for missing attributes instead of raising AttributeError
            return None
        
        def get(self, key, default=None):
            return getattr(self, key, default)
    
    try:
        analysis = None
        analysis_type = None
        
        # Try to find the analysis in each table
        with get_session() as session:
            # Check SecurityAnalysis
            security = session.get(SecurityAnalysis, analysis_id)
            if security:
                analysis = security
                analysis_type = 'security'
            
            # Check PerformanceTest
            if not analysis:
                performance = session.get(PerformanceTest, analysis_id)
                if performance:
                    analysis = performance
                    analysis_type = 'performance'
            
            # Check ZAPAnalysis
            if not analysis:
                zap = session.get(ZAPAnalysis, analysis_id)
                if zap:
                    analysis = zap
                    analysis_type = 'dynamic'
            
            # Check OpenRouterAnalysis
            if not analysis:
                ai = session.get(OpenRouterAnalysis, analysis_id)
                if ai:
                    analysis = ai
                    analysis_type = 'ai'
        
        if not analysis:
            flash(f'Analysis #{analysis_id} not found', 'error')
            return redirect(url_for('reports.reports_index'))
        
        # Prepare data for the comprehensive detail template
        template_data = {
            'analysis': analysis,
            'analysis_type': analysis_type,
            'analysis_type_icons': {
                'security': 'shield-alt',
                'performance': 'tachometer-alt', 
                'dynamic': 'bug',
                'ai': 'robot'
            },
            'analysis_type_colors': {
                'security': 'danger',
                'performance': 'info',
                'dynamic': 'warning', 
                'ai': 'primary'
            }
        }
        
        # Add parsed results if available and make them accessible via dot notation
        results_data = None
        if hasattr(analysis, 'get_results'):
            results_data = analysis.get_results()
        elif hasattr(analysis, 'get_zap_report') and analysis_type == 'dynamic':
            results_data = analysis.get_zap_report()
        
        if results_data:
            # Attach results to analysis object for template access
            analysis.results = DotDict(results_data)
        
        return render_template('pages/analysis/detail.html', **template_data)
        
    except Exception as e:
        logger.error(f"Error rendering analysis detail for #{analysis_id}: {e}")
        flash(f'Error loading analysis details: {str(e)}', 'error')
        return redirect(url_for('reports.reports_index'))


@analysis_bp.route('/results/<model_slug>/<int:app_number>')
def unified_results_view(model_slug: str, app_number: int):
    """
    Unified results view showing all analysis types for a specific model/app combination.
    This replaces the separate security, performance, and dynamic analysis result pages.
    """
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis
        import json

        from app.extensions import get_session
        with get_session() as _s:
            # Get the most recent analysis results for each type
            security_analysis = _s.query(SecurityAnalysis).filter_by(
                model_slug=model_slug, app_number=app_number
            ).order_by(SecurityAnalysis.created_at.desc()).first()

            performance_test = _s.query(PerformanceTest).filter_by(
                model_slug=model_slug, app_number=app_number
            ).order_by(PerformanceTest.created_at.desc()).first()

            dynamic_analysis = _s.query(ZAPAnalysis).filter_by(
                model_slug=model_slug, app_number=app_number
            ).order_by(ZAPAnalysis.created_at.desc()).first()

        # If no analyses found, redirect to hub
        if not any([security_analysis, performance_test, dynamic_analysis]):
            flash(f'No analysis results found for {model_slug} app {app_number}', 'warning')
            return redirect(url_for('analysis.analysis_hub'))

        # Prepare security data
        security_data = {}
        if security_analysis:
            security_data = {
                'analysis': security_analysis,
                'total_vulnerabilities': 0,
                'critical_high_count': 0,
                'tools_executed': 0,
                'results': {}
            }
            
            # Parse security results JSON
            if hasattr(security_analysis, 'results_json') and security_analysis.results_json:
                try:
                    all_results = json.loads(security_analysis.results_json)
                    security_data['results'] = {
                        'bandit': all_results.get('bandit'),
                        'safety': all_results.get('safety'),
                        'zap': all_results.get('zap'),
                        'pylint': all_results.get('pylint'),
                        'eslint': all_results.get('eslint')
                    }
                    
                    # Calculate summary metrics
                    total_vulns = 0
                    critical_high = 0
                    tools = 0
                    
                    # Count results from each tool
                    if security_data['results']['bandit'] and 'results' in security_data['results']['bandit']:
                        bandit_count = len(security_data['results']['bandit']['results'])
                        total_vulns += bandit_count
                        tools += 1
                        for result in security_data['results']['bandit']['results']:
                            if result.get('issue_severity', '').lower() in ['high', 'critical']:
                                critical_high += 1
                    
                    if security_data['results']['safety'] and 'vulnerabilities' in security_data['results']['safety']:
                        safety_count = len(security_data['results']['safety']['vulnerabilities'])
                        total_vulns += safety_count
                        critical_high += safety_count  # Safety vulns are typically high
                        tools += 1
                    
                    if security_data['results']['zap'] and 'site' in security_data['results']['zap']:
                        if security_data['results']['zap']['site'] and 'alerts' in security_data['results']['zap']['site'][0]:
                            zap_alerts = security_data['results']['zap']['site'][0]['alerts']
                            total_vulns += len(zap_alerts)
                            tools += 1
                            for alert in zap_alerts:
                                if alert.get('riskcode', 0) >= 2:
                                    critical_high += 1
                    
                    if security_data['results']['pylint']:
                        total_vulns += len(security_data['results']['pylint'])
                        tools += 1
                        for result in security_data['results']['pylint']:
                            if result.get('type', '') == 'error':
                                critical_high += 1
                    
                    if security_data['results']['eslint']:
                        eslint_count = 0
                        for file_result in security_data['results']['eslint']:
                            if 'messages' in file_result:
                                file_count = len(file_result['messages'])
                                eslint_count += file_count
                                for msg in file_result['messages']:
                                    if msg.get('severity', 0) == 2:
                                        critical_high += 1
                        total_vulns += eslint_count
                        if eslint_count > 0:
                            tools += 1
                    
                    security_data.update({
                        'total_vulnerabilities': total_vulns,
                        'critical_high_count': critical_high,
                        'tools_executed': tools
                    })
                    
                except json.JSONDecodeError:
                    pass

        # Prepare performance data
        performance_data = {}
        if performance_test:
            performance_data = {
                'test': performance_test,
                'results': performance_test.get_results() if hasattr(performance_test, 'get_results') else {},
                'metadata': performance_test.get_metadata() if hasattr(performance_test, 'get_metadata') else {}
            }

        # Prepare dynamic analysis data
        dynamic_data = {}
        if dynamic_analysis:
            dynamic_data = {
                'analysis': dynamic_analysis,
                'zap_report': dynamic_analysis.get_zap_report() if hasattr(dynamic_analysis, 'get_zap_report') else {},
                'metadata': dynamic_analysis.get_metadata() if hasattr(dynamic_analysis, 'get_metadata') else {},
                'counts': {
                    'high': dynamic_analysis.high_risk_alerts or 0,
                    'medium': dynamic_analysis.medium_risk_alerts or 0,
                    'low': dynamic_analysis.low_risk_alerts or 0,
                    'info': dynamic_analysis.informational_alerts or 0
                }
            }
            
            # Fallback: calculate counts from report if needed
            if sum(dynamic_data['counts'].values()) == 0:
                if dynamic_data['zap_report'] and 'site' in dynamic_data['zap_report']:
                    if dynamic_data['zap_report']['site'] and 'alerts' in dynamic_data['zap_report']['site'][0]:
                        alerts = dynamic_data['zap_report']['site'][0]['alerts']
                        counts = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
                        for alert in alerts:
                            risk_code = int(alert.get('riskcode', 0))
                            if risk_code == 3:
                                counts['high'] += 1
                            elif risk_code == 2:
                                counts['medium'] += 1
                            elif risk_code == 1:
                                counts['low'] += 1
                            else:
                                counts['info'] += 1
                        dynamic_data['counts'] = counts

        return render_template(
            'single_page.html',
            page_title=f'Analysis Results: {model_slug} App {app_number}',
            page_icon='fa-chart-bar',
            page_subtitle='Comprehensive Security, Performance & Dynamic Analysis',
            main_partial='pages/analysis/partials/unified_results.html',
            model_slug=model_slug,
            app_number=app_number,
            security_data=security_data,
            performance_data=performance_data,
            dynamic_data=dynamic_data
        )
        
    except Exception as e:
        logger.error(f"Error loading unified results for {model_slug} app {app_number}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading analysis results: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))
