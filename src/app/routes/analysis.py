"""
Analysis Routes
==============

Routes for managing analysis operations and results.
"""

import logging
import time
from functools import wraps

from flask import Blueprint, request, jsonify, render_template

from ..services.task_manager import TaskManager
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

    Uses (route, remote_addr) key in an in-memory dictionary. If calls arrive
    sooner than min_interval seconds, returns a 429 with a tiny partial that
    HTMX will swap in (but visually minimal) instead of hitting the DB again.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                from flask import request, make_response
                key = (fn.__name__, request.remote_addr or 'anon')
                now = time.time()
                last = _last_call_registry.get(key, 0)
                if now - last < min_interval:
                    # Too soon; short-circuit with 429
                    resp = make_response('<div class="d-none" data-rate="limited"></div>', 429)
                    resp.headers['Retry-After'] = str(int(min_interval))
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
def analysis_hub():
    """Starting page for analyses.

    Restores the classic pages/analysis.html as the primary entry point,
    with HTMX-driven sections for stats, trends and recent activity.
    """
    try:
        return render_template('pages/analysis.html')
    except Exception as e:  # pragma: no cover - defensive catch
        logger.error(f"Error loading analysis page: {e}")
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
def analyses_list_page():
    """Analyses list page (combined view with filters and tabs)."""
    try:
        return render_template(
            'single_page.html',
            page_title='Analyses',
            page_icon='fa-list',
            main_partial='partials/analysis/list/shell.html'
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Error loading analyses list page: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.get('/create')
def analyses_create_page():
    """Create new analyses page (unified forms for security and dynamic)."""
    try:
        return render_template(
            'single_page.html',
            page_title='Create Analysis',
            page_icon='fa-plus',
            main_partial='partials/analysis/create/shell.html'
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Error loading create analysis page: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.get('/create/security')
def analyses_create_security_page():
    """Create page focused on Security form only."""
    try:
        from ..models import ModelCapability
        models = ModelCapability.query.all()
        return render_template(
            'single_page.html',
            page_title='Create Security Analysis',
            page_icon='fa-shield-alt',
            main_partial='partials/analysis/create/security_test_form.html',
            models=models
        )
    except Exception as e:
        logger.error(f"Error loading security create page: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.get('/create/dynamic')
def analyses_create_dynamic_page():
    """Create page focused on Dynamic (ZAP) form only."""
    try:
        from ..models import ModelCapability
        models = ModelCapability.query.all()
        return render_template(
            'single_page.html',
            page_title='Create Dynamic Scan',
            page_icon='fa-bolt',
            main_partial='partials/analysis/create/dynamic_test_form.html',
            models=models
        )
    except Exception as e:
        logger.error(f"Error loading dynamic create page: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.get('/create/performance')
def analyses_create_performance_page():
    """Create page focused on Performance test form only."""
    try:
        from ..models import ModelCapability
        models = ModelCapability.query.all()
        return render_template(
            'single_page.html',
            page_title='Create Performance Test',
            page_icon='fa-tachometer-alt',
            main_partial='partials/analysis/create/performance_test_form.html',
            models=models
        )
    except Exception as e:
        logger.error(f"Error loading performance create page: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@analysis_bp.get('/create/batch')
def analyses_create_batch_page():
    """Create page focused on Batch analysis form only."""
    try:
        from ..models import ModelCapability
        models = ModelCapability.query.all()
        return render_template(
            'single_page.html',
            page_title='Create Batch Analysis',
            page_icon='fa-layer-group',
            main_partial='partials/analysis/create/batch_form.html',
            models=models
        )
    except Exception as e:
        logger.error(f"Error loading batch create page: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


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
    """HTMX endpoint for refreshing stats cards."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis
        stats = {
            'total_security': SecurityAnalysis.query.count(),
            'total_performance': PerformanceTest.query.count(),
            'total_zap': ZAPAnalysis.query.count(),
            'total_ai': OpenRouterAnalysis.query.count()
        }
        # Return inner fragment only; outer wrapper handles hx-* attributes
        return render_template('partials/analysis/_stats_cards_inner.html', stats=stats)
    except Exception as e:
        logger.error(f"HTMX stats error: {e}")
        return render_template('partials/common/error.html', error='Failed to load stats'), 500


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

        # Start performance test (returns task id)
        task_id = task_manager.start_performance_test(
            app.model_slug,
            app.app_number,
            test_config
        )

        if is_htmx:
            return render_template('partials/analysis/create/start_result.html',
                                   title='Performance test started',
                                   task_id=task_id,
                                   analysis_type='performance')

        return jsonify({
            'success': True,
            'task_id': task_id,
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

        # Validation
        if not analysis_types:
            # Decide response type based on HTMX
            if is_htmx:
                return render_template('partials/common/error.html', error='Select at least one analysis type'), 400
            return jsonify({'error': 'At least one analysis type required'}), 400

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

        analysis = ZAPAnalysis.query.get(analysis_id)
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


@analysis_bp.route('/security/<int:analysis_id>/results/view')
def security_analysis_results_view(analysis_id):
    """HTML view for security analysis results."""
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import SecurityAnalysis
        import json
        
        analysis = SecurityAnalysis.query.get(analysis_id)
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
        
        # Calculate scan duration
        scan_duration = 'N/A'
        if analysis.started_at and analysis.completed_at:
            duration = analysis.completed_at - analysis.started_at
            if duration.total_seconds() < 60:
                scan_duration = f"{int(duration.total_seconds())}s"
            else:
                scan_duration = f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"
        
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


@analysis_bp.get('/api/security/<int:analysis_id>/tools-status')
def htmx_security_tools_status(analysis_id: int):
    """HTMX endpoint to render current per-tool progress/status for a SecurityAnalysis.

    Returns a self-contained fragment that continues polling while the
    analysis is PENDING/RUNNING and stops polling when COMPLETED/FAILED
    by omitting hx attributes in the returned wrapper.
    """
    try:
        from ..models import SecurityAnalysis
        analysis = SecurityAnalysis.query.get(analysis_id)
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
        
        analysis = SecurityAnalysis.query.get(analysis_id)
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
# Combined recent activity endpoint (single poll instead of two)
# ============================================================================
@analysis_bp.get('/api/recent/combined')
@rate_limited(2.5)
def htmx_recent_combined():
    """Return a combined partial containing both recent security & performance.

    This reduces client polling overhead by consolidating two requests into one.
    """
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from sqlalchemy import desc
        security_items = SecurityAnalysis.query.order_by(desc(SecurityAnalysis.created_at)).limit(5).all()
        performance_items = PerformanceTest.query.order_by(desc(PerformanceTest.created_at)).limit(5).all()
        return render_template('partials/analysis/recent_combined.html',
                               recent_security=security_items,
                               recent_performance=performance_items)
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"HTMX recent combined error: {e}")
        return render_template('partials/common/error.html', error='Failed to load recent activity'), 500


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
