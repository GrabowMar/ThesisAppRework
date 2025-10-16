"""
Analysis routes for the Flask application
=======================================

Analysis-related web routes that render Jinja templates.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, request, redirect, url_for, flash, jsonify, make_response, abort

from app.models import AnalysisTask
from app.utils.template_paths import render_template_compat as render_template
from app.services.task_service import AnalysisTaskService
from app.services.service_locator import ServiceLocator
from app.services import analysis_result_store
# (Removed ValidationError, NotFoundError imports after refactor of custom mode logic)

# Create blueprint
analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')


def _render_task_tab(template_name: str, task_id: str):
    """Helper to hydrate tab templates with database task and inspection payload."""
    try:
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
    except Exception as exc:  # pragma: no cover - defensive safety net
        return f'<div class="alert alert-danger">Error loading task: {exc}</div>'

    if not task:
        return '<div class="alert alert-danger">Task not found</div>'

    insp = ServiceLocator.get('analysis_inspection_service')
    payload: Dict[str, Any] = {}
    data_error: Optional[str] = None

    if not insp:
        data_error = 'Inspection service unavailable'
    else:
        try:
            payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - payload retrieval can legitimately fail while task exists
            data_error = str(exc)

    return render_template(
        template_name,
        task=task,
        task_id=task_id,
        payload=payload,
        data_error=data_error,
    )

@analysis_bp.errorhandler(400)
def bad_request(error):
    return render_template('pages/errors/errors_main.html', error_code=400, error_message=str(error)), 400

@analysis_bp.errorhandler(404)
def not_found(error):
    return render_template('pages/errors/errors_main.html', error_code=404, error_message=str(error)), 404

@analysis_bp.errorhandler(500)
def internal_error(error):
    return render_template('pages/errors/errors_main.html', error_code=500, error_message=str(error)), 500

@analysis_bp.route('/dashboard')
def analysis_dashboard():
    """Render the analysis dashboard page."""
    dashboard_data = {
        'active_tasks': 0,
        'completed_tasks': 0,
        'failed_tasks': 0,
        'total_analyses': 0,
        'recent_activity': [],
        'system_health': {'status': 'healthy'},
        'queue_status': {'pending': 0, 'running': 0}
    }

    try:
        active_tasks = AnalysisTask.query.filter_by(status='running').count()
        completed_tasks = AnalysisTask.query.filter_by(status='completed').count()
        failed_tasks = AnalysisTask.query.filter_by(status='failed').count()
        total_analyses = AnalysisTask.query.count()

        dashboard_data.update({
            'active_tasks': active_tasks,
            'completed_tasks': completed_tasks,
            'failed_tasks': failed_tasks,
            'total_analyses': total_analyses
        })
    except Exception as e:
        current_app.logger.warning(f"Could not load dashboard data: {e}")

    return render_template('pages/analysis/dashboard_main.html', dashboard_data=dashboard_data)

@analysis_bp.route('/list')
def analysis_list():
    """Render analysis hub/list page with recent tasks.

    Full page render for non-HTMX; fragments are handled by /api/* endpoints.
    """
    # Simplified page: server-render initial recent tasks so page is not empty before HTMX filtering
    try:
        tasks = AnalysisTaskService.get_recent_tasks(limit=25)
    except Exception as e:  # pragma: no cover
        current_app.logger.warning(f"Could not load initial tasks: {e}")
        tasks = []
    return render_template('pages/analysis/analysis_main.html', tasks=tasks)

@analysis_bp.route('/')
def analysis_index():
    """Alias of /analysis/list during migration with shared data."""
    return analysis_list()

@analysis_bp.route('/create', methods=['GET', 'POST'])
def analysis_create():
    """Render and process the Analysis Creation Wizard.

    POST expects form fields: 
    - model_slug, app_number (required)
    - analysis_mode (profile/custom)
    - analysis_profile (for profile mode)
    - selected_tools[] (for custom mode)
    - priority (optional)
    
    Creates a CustomAnalysisRequest or AnalysisTask based on mode,
    then redirects to /analysis/list.
    """
    if request.method == 'POST':
        form = request.form
        model_slug = (form.get('model_slug') or '').strip()
        app_number_raw = form.get('app_number') or ''
        analysis_mode = (form.get('analysis_mode') or '').strip()
        analysis_profile = (form.get('analysis_profile') or '').strip()
        # Selected tools may arrive as legacy numeric IDs OR (new) tool names
        selected_tools = form.getlist('selected_tools[]')
        priority = (form.get('priority') or 'normal').strip()

        # Debug logging to trace actual POST payload (safe, no secrets)
        try:
            current_app.logger.debug(
                "analysis_create POST: model=%s app=%s mode=%s profile=%s selected_tools=%s",
                model_slug,
                app_number_raw,
                analysis_mode,
                analysis_profile,
                selected_tools,
            )
        except Exception:
            pass

        # Helper: parse potential batch inputs coming from the wizard
        def _parse_selection(model_value: str, app_value: str) -> list[tuple[str, int]]:
            """Return list of (model_slug, app_number) pairs.

            Supports formats:
            - Single: model_slug='gpt', app_number='7'
            - Batch apps with explicit model: app_number='gpt:7,claude:3'
            - Batch models + single/nums (fallback): model_slug='gpt,claude', app_number='7,8'
            In the last case, we pair each model with each app number (cartesian product).
            """
            pairs: list[tuple[str, int]] = []
            m_list = [m.strip() for m in (model_value or '').split(',') if m.strip()]
            # First, prefer explicit model:app entries in app_value
            explicit_parts = [p.strip() for p in (app_value or '').split(',') if p.strip()]
            has_explicit = any(':' in p for p in explicit_parts)
            if has_explicit:
                for part in explicit_parts:
                    try:
                        mslug, anum = part.split(':', 1)
                        anum_i = int(str(anum).strip())
                        mslug = mslug.strip()
                        if mslug:
                            pairs.append((mslug, anum_i))
                    except Exception:
                        continue
                return pairs
            # Otherwise, parse app numbers and pair with provided model(s)
            a_list: list[int] = []
            for a in [x.strip() for x in (app_value or '').split(',') if x.strip()]:
                try:
                    a_list.append(int(a))
                except Exception:
                    continue
            # If no model list provided, keep single model as list if present
            if not m_list and model_value:
                m_list = [model_value]
            # If both present and multiple, build cartesian product; if one side empty, result empty
            for m in m_list or []:
                for a in a_list or []:
                    pairs.append((m, a))
            # Fallback: single/single if above produced nothing and values look scalar
            if not pairs and model_value and app_value:
                try:
                    pairs.append((model_value, int(app_value)))
                except Exception:
                    pass
            return pairs

        # Compute selection pairs (supports batch)
        selection_pairs = _parse_selection(model_slug, app_number_raw)

        errors = []
        if not selection_pairs:
            # Preserve original error messages for single-case UX
            if not model_slug:
                errors.append('Model is required')
            errors.append('Valid application number required')
        
        # Validate analysis configuration
        if analysis_mode == 'profile':
            if not analysis_profile:
                errors.append('Analysis profile is required when using profile mode')
        elif analysis_mode == 'custom':
            if not selected_tools:
                errors.append('At least one tool must be selected for custom analysis')
        else:
            errors.append('Analysis mode (profile or custom) is required')

        if errors:
            for e in errors:
                flash(e, 'danger')
            # Re-render wizard template; JS handles state restoration.
            return render_template('pages/analysis/create.html'), 400

        try:
            if analysis_mode == 'custom':
                # ------------------------------------------------------------------
                # CUSTOM MODE: Accept tool *names* (preferred) or legacy numeric IDs
                # ------------------------------------------------------------------
                try:
                    from app.engines.container_tool_registry import get_container_tool_registry
                    registry = get_container_tool_registry()
                    registry_tools = registry.get_all_tools()  # Ordered mapping
                except Exception as e:
                    current_app.logger.exception("Failed to load container tool registry")
                    flash('Tool registry unavailable. Please retry shortly.', 'danger')
                    return render_template('pages/analysis/create.html'), 500

                # Build lookup tables
                id_to_name: dict[int, str] = {}
                name_to_id: dict[str, int] = {}
                name_to_record: dict[str, dict] = {}
                for idx, (t_name, t_obj) in enumerate(registry_tools.items()):
                    tid = idx + 1  # Legacy numeric ID
                    id_to_name[tid] = t_name
                    name_to_id[t_name.lower()] = tid
                    name_to_record[t_name.lower()] = {
                        'id': tid,
                        'name': t_obj.name,
                        'display_name': t_obj.display_name,
                        'container': t_obj.container.value,
                        'service_name': t_obj.container.value,
                        'is_enabled': t_obj.available,
                        'available': t_obj.available,
                        'tags': list(t_obj.tags),
                    }

                # Normalize submitted list -> list[int] (legacy ids) & list[str] (names)
                normalized_tool_ids: list[int] = []
                invalid: list[str] = []
                for raw in selected_tools:
                    raw_s = str(raw).strip()
                    if not raw_s:
                        continue
                    if raw_s.isdigit():  # legacy ID
                        tid = int(raw_s)
                        tname = id_to_name.get(tid)
                        if not tname:
                            invalid.append(f"Unknown tool id: {tid}")
                            continue
                        normalized_tool_ids.append(tid)
                    else:
                        rec = name_to_record.get(raw_s.lower())
                        if not rec:
                            invalid.append(f"Unknown tool name: {raw_s}")
                            continue
                        normalized_tool_ids.append(rec['id'])

                # Deduplicate while preserving order
                seen_ids = set()
                ordered_ids: list[int] = []
                for tid in normalized_tool_ids:
                    if tid not in seen_ids:
                        seen_ids.add(tid)
                        ordered_ids.append(tid)

                if invalid:
                    for msg in invalid:
                        flash(msg, 'danger')
                    return render_template('pages/analysis/create.html'), 400

                # Group by service (container)
                tools_by_service: dict[str, list[int]] = {}
                selected_tool_names: list[str] = []
                for tid in ordered_ids:
                    tname = id_to_name.get(tid)
                    if not tname:
                        continue
                    rec = name_to_record.get(tname.lower())
                    if not rec or not rec.get('is_enabled'):
                        continue
                    svc = rec['service_name']
                    tools_by_service.setdefault(svc, []).append(tid)
                    selected_tool_names.append(tname)

                if not tools_by_service:
                    flash('No valid tools selected after validation.', 'danger')
                    return render_template('pages/analysis/create.html'), 400

                multiple_services = len(tools_by_service) > 1

                # Debug visibility for AI-only or single-service selections
                try:
                    current_app.logger.debug(
                        "analysis_create custom selection: services=%s selected_tool_names=%s multiple_services=%s engine_preview=%s",
                        list(tools_by_service.keys()),
                        selected_tool_names,
                        multiple_services,
                        ('ai' if (len(tools_by_service)==1 and 'ai-analyzer' in tools_by_service) else 'security')
                    )
                except Exception:
                    pass

                # Map container service -> engine name
                service_to_engine = {
                    'static-analyzer': 'security',
                    'dynamic-analyzer': 'dynamic',
                    'performance-tester': 'performance',
                    'ai-analyzer': 'ai',
                }

                from app.extensions import db as _db  # lazy import
                created_tasks = []
                for mslug, anum in selection_pairs:
                    if multiple_services:
                        engine_name = 'security'  # coordinating primary (unified orchestrator will fan out)
                    else:
                        only_service = next(iter(tools_by_service.keys()))
                        engine_name = service_to_engine.get(only_service, 'security')
                    task = AnalysisTaskService.create_task(
                        model_slug=mslug,
                        app_number=anum,
                        analysis_type=engine_name,
                        priority=priority,
                        custom_options={
                            'selected_tools': ordered_ids,
                            'selected_tool_names': selected_tool_names,
                            'tools_by_service': tools_by_service,
                            'unified_analysis': multiple_services,
                            'source': 'wizard_custom'
                        }
                    )
                    try:
                        meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
                        meta.update({
                            'selected_tools': ordered_ids,
                            'selected_tool_names': selected_tool_names,
                            'tools_by_service': tools_by_service,
                            'unified_analysis': multiple_services,
                        })
                        task.set_metadata(meta)
                        _db.session.commit()
                    except Exception:
                        pass
                    created_tasks.append(task)

                flash(f"Created {len(created_tasks)} task(s) with {len(ordered_ids)} selected tool(s)", 'success')
                
            else:
                # Profile mode - ENHANCED to support unified analysis across all tools
                analysis_type_mapping = {
                    'security': 'security',
                    'performance': 'performance',
                    'quality': 'dynamic',  # Map quality to dynamic for now
                }
                
                analysis_type = analysis_type_mapping.get(analysis_profile, analysis_profile)
                
                # FORCE unified analysis for security profile to run ALL tools
                use_unified_analysis = (analysis_profile == 'security')
                
                # Create a task for each selected pair
                created = []
                for mslug, anum in selection_pairs:
                    if use_unified_analysis:
                        # Security profile should run ALL 15 tools across all containers
                        from app.engines.container_tool_registry import get_container_tool_registry
                        registry = get_container_tool_registry()
                        all_tools = registry.get_all_tools()
                        
                        # Get ALL tool IDs and names
                        all_tool_ids = list(range(1, len(all_tools) + 1))
                        all_tool_names = list(all_tools.keys())
                        
                        # Group tools by service
                        tools_by_service = {}
                        for idx, (tool_name, tool) in enumerate(all_tools.items()):
                            service = tool.container.value
                            tool_id = idx + 1
                            tools_by_service.setdefault(service, []).append(tool_id)
                        
                        task = AnalysisTaskService.create_task(
                            model_slug=mslug,
                            app_number=anum,
                            analysis_type=analysis_type,
                            priority=priority,
                            custom_options={
                                'selected_tools': all_tool_ids,
                                'selected_tool_names': all_tool_names,
                                'source': 'wizard_profile_security',
                                'unified_analysis': True,
                                'tools_by_service': tools_by_service,
                            }
                        )
                        
                        # Set metadata for unified analysis
                        try:
                            meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
                            meta.update({
                                'selected_tools': all_tool_ids,
                                'selected_tool_names': all_tool_names,
                                'tools_by_service': tools_by_service,
                                'unified_analysis': True
                            })
                            task.set_metadata(meta)
                            from app.extensions import db as _db
                            _db.session.commit()
                        except Exception:
                            pass
                    else:
                        # Other profiles use regular single-engine analysis
                        task = AnalysisTaskService.create_task(
                            model_slug=mslug,
                            app_number=anum,
                            analysis_type=analysis_type,
                            priority=priority
                        )
                    created.append(task)
                if len(created) == 1:
                    flash(f'Created {analysis_profile} analysis task {created[0].task_id}', 'success')
                else:
                    flash(f'Created {len(created)} {analysis_profile} analysis tasks', 'success')
            
        except Exception as e:
            current_app.logger.exception('analysis_create failed inside processing block')
            flash(f'Error creating analysis task: {e}', 'danger')
            return render_template('pages/analysis/create.html'), 500

        return redirect(url_for('analysis.analysis_list'))
    # GET request: render wizard
    return render_template('pages/analysis/create.html')
            
@analysis_bp.route('/quick/ai')
def analysis_quick_ai():
    """Create a single AI-only analysis task (debug helper).

    Query params:
      model (required)
      app (required int)
      tool (optional alias; defaults to requirements-scanner)
    """
    from app.services.task_service import AnalysisTaskService
    model = (request.args.get('model') or '').strip()
    app_raw = (request.args.get('app') or '').strip()
    tool = (request.args.get('tool') or 'requirements-scanner').strip().lower()
    if not model or not app_raw.isdigit():
        return make_response(jsonify({'error': 'model and numeric app required'}), 400)
    app_number = int(app_raw)
    # Map aliases
    if tool in ('ai-requirements','requirements-analyzer'):
        tool = 'requirements-scanner'
    # Build minimal metadata matching custom mode shape
    try:
        from app.engines.container_tool_registry import get_container_tool_registry
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        # Determine tool id for requested tool
        tool_id = None
        for idx, name in enumerate(all_tools.keys()):
            if name == tool:
                tool_id = idx + 1
                break
        if not tool_id:
            return make_response(jsonify({'error': f'unknown_tool:{tool}'}), 400)
        tools_by_service = {'ai-analyzer': [tool_id]}
        task = AnalysisTaskService.create_task(
            model_slug=model,
            app_number=app_number,
            analysis_type='ai',
            priority='normal',
            custom_options={
                'selected_tools': [tool_id],
                'selected_tool_names': [tool],
                'tools_by_service': tools_by_service,
                'unified_analysis': False,
                'source': 'quick_ai_endpoint'
            }
        )
        try:
            meta = task.get_metadata() if hasattr(task,'get_metadata') else {}
            meta.update({
                'selected_tools': [tool_id],
                'selected_tool_names': [tool],
                'tools_by_service': tools_by_service,
                'unified_analysis': False
            })
            task.set_metadata(meta)
            from app.extensions import db as _db
            _db.session.commit()
        except Exception:
            pass
        current_app.logger.info(f"quick_ai: created task {task.task_id} for {model} app {app_number} tool={tool}")
        return jsonify({'status': 'created', 'task_id': task.task_id})
    except Exception as e:
        current_app.logger.exception('quick_ai failed')
        return make_response(jsonify({'error': str(e)}), 500)


# ---------------------------------------------------------------------------
# HTMX/fragment endpoints expected by legacy tests
# ---------------------------------------------------------------------------

# Model grid fragment for wizard (HTMX)
@analysis_bp.route('/api/models/grid')
def htmx_model_grid_fragment():
    """Return model grid fragment for wizard selection (HTMX)."""
    from app.services.model_service import ModelService
    # Acquire service instance (reuse if app has one cached)
    svc: ModelService
    if not hasattr(current_app, 'model_service'):
        current_app.model_service = ModelService(current_app)  # type: ignore[attr-defined]
    svc = current_app.model_service  # type: ignore[attr-defined]
    # Filtering params
    provider = request.args.get('provider')
    capability = request.args.get('capability')
    price = request.args.get('price')
    selectable = request.args.get('selectable', 'false').lower() == 'true'
    page = int(request.args.get('page', 1) or 1)
    page_size = min(int(request.args.get('page_size', 12) or 12), 60)
    # Use only used models (models with applications)
    models = svc.get_used_models(provider=provider)
    # Apply additional filters
    if capability:
        models = [m for m in models if capability in getattr(m, 'capabilities', [])]
    if price:
        def price_bucket(m):
            p = getattr(m, 'input_price_per_token', 0.0)
            if p < 0.01:
                return 'low'
            if p < 0.05:
                return 'medium'
            return 'high'
        models = [m for m in models if price_bucket(m) == price]
    total = len(models)
    start = (page - 1) * page_size
    end = start + page_size
    page_models = models[start:end]
    has_next = end < total
    return render_template('pages/analysis/partials/model_grid_select.html', models=page_models, selectable=selectable, page=page, page_size=page_size, total=total, has_next=has_next)

@analysis_bp.route('/api/models/providers')
def htmx_model_providers():
    """Return list of providers that have models with applications (HTMX)."""
    from app.services.model_service import ModelService
    svc: ModelService
    if not hasattr(current_app, 'model_service'):
        current_app.model_service = ModelService(current_app)  # type: ignore[attr-defined]
    svc = current_app.model_service  # type: ignore[attr-defined]
    
    providers = svc.get_used_providers()
    
    # Return as simple HTML options
    html = '<option value="">All Providers</option>'
    for provider in providers:
        html += f'<option value="{provider}">{provider.title()}</option>'
    
    return html

# Applications list fragment for wizard (HTMX)
@analysis_bp.route('/api/models/<model_slug>/applications')
def htmx_model_applications_fragment(model_slug):
    """Return applications list fragment for selected model (HTMX)."""
    from app.services.model_service import ModelService
    if not hasattr(current_app, 'model_service'):
        current_app.model_service = ModelService(current_app)  # type: ignore[attr-defined]
    svc = current_app.model_service  # type: ignore[attr-defined]
    apps = svc.get_model_apps(model_slug)
    return render_template('pages/analysis/partials/applications_select.html', applications=apps, model_slug=model_slug)

@analysis_bp.route('/api/tasks/recent')
def htmx_recent_tasks_fragment():
    """Return recent tasks fragment (HTMX)."""
    tasks = AnalysisTaskService.get_recent_tasks(limit=25)
    return render_template('pages/analysis/partials/tasks_list.html', tasks=tasks)

@analysis_bp.route('/api/stats')
def htmx_stats_fragment():
    """Return stats summary fragment (HTMX)."""
    try:
        tasks = AnalysisTaskService.get_recent_tasks(limit=25)
        stats = _build_stats_snapshot(tasks)
    except Exception as e:  # pragma: no cover
        current_app.logger.warning(f"Could not build stats: {e}")
        stats = None
    return render_template('pages/analysis/partials/stats_summary.html', stats=stats)

@analysis_bp.route('/api/quick-actions')
def htmx_quick_actions_fragment():
    """Return quick actions fragment (HTMX)."""
    return render_template('pages/analysis/partials/quick_actions.html')

@analysis_bp.route('/api/list/combined')
def htmx_analysis_list_combined():
    """Return a minimal fragment or status code for combined analyses list.

    Tests only assert the status code is one of (200, 204, 429). We return 200
    with a tiny placeholder table so future enhancement can expand it.
    """
    if request.headers.get('HX-Request'):
        return '<div class="analysis-combined-list"><!-- empty placeholder --></div>'
    return '<div>HTMX only endpoint</div>'

@analysis_bp.route('/api/active-tasks')
def htmx_active_tasks():
    """Return active tasks fragment (HTMX). Future: real-time active list."""
    return render_template('pages/analysis/partials/active_tasks.html')

# ---------------------------------------------------------------------------
# New: Task inspection list & detail views
# ---------------------------------------------------------------------------

@analysis_bp.route('/tasks')
def tasks_inspection_index():
    """Legacy inspection route now unified with main analysis list.

    Retained so old bookmarks/tests keep working. Renders the same unified
    task management page and shows a small legacy notice banner.
    """
    # Prefer recent tasks for fast initial paint; fall back gracefully.
    try:
        tasks = AnalysisTaskService.get_recent_tasks(limit=25)
    except Exception as e:  # pragma: no cover
        current_app.logger.warning(f"Could not load initial tasks (legacy route): {e}")
        tasks = []
    return render_template('pages/analysis/analysis_main.html', tasks=tasks, show_legacy_notice=True)

@analysis_bp.route('/tasks/<task_id>')
def task_detail_page(task_id: str):
    """Full page detail for a single analysis task."""
    try:
        # Get basic task info first
        from app.models import AnalysisTask
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            abort(404, description=f"Task {task_id} not found")
        
        # Use the new modern template with sidebar
        return render_template('pages/analysis/task_detail_main.html', task=task, task_id=task_id)
        
    except Exception as e:
        current_app.logger.error(f"Task detail page error for {task_id}: {e}")
        abort(500, description="Internal server error")

@analysis_bp.route('/api/tasks/inspect/list')
def htmx_tasks_inspection_list():
    """HTMX fragment: filtered task list (table rows).

    Falls back to simple recent task listing if the dedicated inspection
    service is unavailable (e.g., during initialization) so the UI does not
    appear empty.
    """
    insp = ServiceLocator.get('analysis_inspection_service')
    # Extract filters (shared between inspection and fallback path)
    kwargs = {
        'status': request.args.get('status') or None,
        'analysis_type': request.args.get('analysis_type') or None,
        'model': request.args.get('model') or None,
        'priority': request.args.get('priority') or None,
        'search': request.args.get('search') or None,
    }
    limit = int(request.args.get('limit', 25))
    tasks = []
    if insp:
        try:
            tasks = insp.list_tasks(limit=limit, **kwargs)  # type: ignore[arg-type]
        except Exception as e:  # pragma: no cover
            current_app.logger.warning(f"Task list filter failed (insp): {e}")
            tasks = []
    # Fallback if insp missing OR returned nothing and filters not applied
    if (not insp) and not tasks:
        try:
            tasks = AnalysisTaskService.get_recent_tasks(limit=limit)
        except Exception as e:  # pragma: no cover
            current_app.logger.warning(f"Fallback recent tasks failed: {e}")
            tasks = []
    return render_template('pages/analysis/partials/inspection_tasks_table.html', tasks=tasks)

@analysis_bp.route('/api/tasks/<task_id>/cancel', methods=['POST'])
def cancel_single_task(task_id: str):
    """Cancel a single running/pending task."""
    try:
        task = AnalysisTaskService.cancel_task(task_id)
        if not task:
            return '<div class="text-danger small">Task not found</div>', 404
        return '<div class="alert alert-info py-2 mb-2 small">Task cancelled successfully</div>'
    except ValueError as e:
        return f'<div class="text-warning small">{e}</div>', 400
    except Exception as e:
        current_app.logger.error(f"Error cancelling task {task_id}: {e}")
        return f'<div class="text-danger small">Error cancelling task: {e}</div>', 500

@analysis_bp.route('/api/tasks/batch/delete', methods=['POST'])
def batch_delete_tasks():
    """Batch delete (remove) analysis tasks.

    Accepts either form-encoded `task_ids` (repeatable) or JSON body with
    {"task_ids": ["task_123", ...]}. Running/pending tasks are skipped for
    safety. Returns a lightweight HTML snippet indicating result which the
    client can display, and triggers caller to refresh task list.
    """
    from app.extensions import db
    # Parse IDs
    task_ids = []
    if request.is_json:
        try:
            payload = request.get_json(silent=True) or {}
            task_ids = list(payload.get('task_ids') or [])
        except Exception:
            task_ids = []
    if not task_ids:
        # Accept both task_ids and task_ids[] naming
        task_ids = request.form.getlist('task_ids') or request.form.getlist('task_ids[]')
    task_ids = [tid for tid in (task_ids or []) if isinstance(tid, str) and tid.strip()]
    if not task_ids:
        return '<div class="text-danger small">No task ids provided</div>', 400
    deleted = 0
    skipped = 0
    from app.constants import AnalysisStatus
    for tid in task_ids[:200]:  # hard safety cap
        try:
            task = AnalysisTaskService.get_task(tid)
            if not task:
                skipped += 1
                continue
            # Skip active tasks (do not delete running/pending)
            if task.status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
                skipped += 1
                continue
            removed = AnalysisTaskService.delete_task(tid, allow_batch=True, commit=False)
            if removed:
                deleted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    try:
        if deleted:
            db.session.commit()
        else:
            db.session.rollback()
    except Exception:
        pass
    return f'<div class="alert alert-info py-2 mb-2 small">Removed {deleted} task(s); skipped {skipped}.</div>'

## Removed legacy /api/tasks/table endpoint (complex pagination table) during simplification.
## Reason: Replaced by existing stable inspection list (/api/tasks/inspect/list) to reduce maintenance surface.

@analysis_bp.route('/api/tasks/<task_id>/detail')
def htmx_task_detail_fragment(task_id: str):
    """HTMX fragment: core detail panel (metadata)."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="text-danger">Inspection service unavailable</div>'
    try:
        detail = insp.get_task_detail(task_id)  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        return f'<div class="text-danger">Error: {e}</div>'
    return render_template('pages/analysis/partials/task_detail_core.html', task=detail)

@analysis_bp.route('/api/tasks/<task_id>/results.json')
def task_results_json(task_id: str):
    """Return authoritative consolidated JSON for a task.

    Payloads are sourced from the relational store via AnalysisInspectionService.
    """
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return ('{"error":"service unavailable"}', 503, {'Content-Type': 'application/json'})
    try:
        json_payload = insp.get_task_results_json(task_id)  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        return (f'{{"error":"{e}"}}', 404, {'Content-Type': 'application/json'})
    return (json_payload, 200, {'Content-Type': 'application/json; charset=utf-8'})

@analysis_bp.route('/api/tasks/<task_id>/results/minimal')
def task_results_minimal_json(task_id: str):
    """Return a minimal summary-only JSON payload for large analyses.

    Excludes heavy arrays and verbose raw outputs. Intended for quick
    programmatic consumption and bandwidth-sensitive UI calls.

    Schema (keys retained):
      {
        "task_id", "status", "analysis_type", "model_slug", "app_number",
        "findings_total", "findings_by_severity", "findings_by_tool",
        "tools_used", "configuration_applied", "summary", "metadata": {"extraction_version"}
      }
    "raw_outputs" is replaced with an object containing only per-analyzer tool names & issue counts.
    "findings_preview" truncated to first 5 (or omitted if empty).
    "_source": "minimal" marker added for clarity.
    """
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return ('{"error":"service unavailable"}', 503, {'Content-Type': 'application/json'})
    try:
        full = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        return (f'{{"error":"{e}"}}', 404, {'Content-Type': 'application/json'})

    # Build minimal structure
    minimal = {
        'task_id': full.get('task_id'),
        'status': full.get('status'),
        'analysis_type': full.get('analysis_type'),
        'model_slug': full.get('model_slug'),
        'app_number': full.get('app_number'),
        'findings_total': full.get('findings_total'),
        'findings_by_severity': full.get('findings_by_severity'),
        'findings_by_tool': full.get('findings_by_tool'),
        'tools_used': full.get('tools_used'),
        'configuration_applied': full.get('configuration_applied'),
        'summary': full.get('summary'),
        'metadata': {
            'extraction_version': (full.get('metadata') or {}).get('extraction_version'),
            'schema_variant': 'minimal-v1'
        },
        '_source': 'minimal'
    }

    # Optional very small preview (first 5 findings)
    preview = full.get('findings_preview') or []
    if preview:
        minimal['findings_preview'] = preview[:5]

    # Compact raw output summary: { analyzer: { tool: issue_count } }
    raw = full.get('raw_outputs') or {}
    compact_raw = {}
    if isinstance(raw, dict):
        for analyzer_name, block in raw.items():
            tools_block = (block or {}).get('tools') or {}
            if isinstance(tools_block, dict):
                compact_raw[analyzer_name] = {
                    t: (td.get('total_issues') if isinstance(td, dict) else None)
                    for t, td in tools_block.items()
                }
    minimal['raw_outputs'] = compact_raw

    try:
        return (json.dumps(minimal, indent=2, sort_keys=True), 200, {'Content-Type': 'application/json; charset=utf-8'})
    except Exception as e:  # pragma: no cover
        return (f'{{"error":"serialization failed: {e}"}}', 500, {'Content-Type': 'application/json'})


@analysis_bp.route('/api/tasks/<task_id>/generate-json', methods=['POST'])
def task_generate_json(task_id: str):
    """Persist the latest analysis payload to the relational analysis store."""
    task = AnalysisTaskService.get_task(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return jsonify({'error': 'Inspection service unavailable'}), 503

    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Failed to assemble results payload for %s: %s", task_id, exc)
        return jsonify({'error': f'Unable to build analysis payload: {exc}'}), 500

    if not payload:
        return jsonify({'error': 'No results available for this task yet'}), 400

    if not isinstance(payload, dict):
        return jsonify({'error': 'Unable to build structured payload for this task'}), 400

    persisted = False
    try:
        persisted = analysis_result_store.persist_analysis_payload_by_task_id(task_id, payload)
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Failed to persist analysis payload for %s: %s", task_id, exc)
        return jsonify({'error': f'Failed to persist analysis payload: {exc}'}), 500

    if not persisted:
        return jsonify({'error': 'Analysis task no longer exists'}), 404

    response_payload = {
        'status': 'ok',
        'message': 'Analysis payload stored in database.',
        'task_id': task_id,
        'model_slug': payload.get('model_slug'),
        'app_number': payload.get('app_number'),
        'analysis_type': payload.get('analysis_type'),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }

    current_app.logger.info(
        "Persisted analysis payload for task %s (model=%s app=%s)",
        task_id,
        payload.get('model_slug'),
        payload.get('app_number'),
    )

    return jsonify(response_payload)

@analysis_bp.route('/api/tasks/<task_id>/results/summary')
def task_results_summary_fragment(task_id: str):
    """HTMX fragment: structured results summary (tools, severities, findings table).

    Keeps preview lightweight (first 50 findings already enforced in service layer).
    Future analyzers (performance, quality, license) can extend via template blocks.
    """
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="text-danger small">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger small">Error loading results: {e}</div>'
    # Limit findings to 50 for display safety (service may already do this)
    findings = (payload.get('findings_preview') or [])[:50]
    return render_template('pages/analysis/partials/task_results_summary.html', task_id=task_id, payload=payload, findings=findings)

@analysis_bp.route('/api/tasks/<task_id>/results/tools')
def task_tool_details_fragment(task_id: str):
    """HTMX fragment: detailed tool execution information and output logs.
    
    Shows what tools actually did during analysis, including files analyzed,
    rules checked, execution time, and raw output - even when findings count is 0.
    """
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="text-danger small">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger small">Error loading tool details: {e}</div>'
    
    # Extract tool metrics and execution details
    tool_metrics = payload.get('tool_metrics', {})
    
    return render_template('pages/analysis/partials/task_tool_details.html', 
                         task_id=task_id, 
                         payload=payload, 
                         tool_metrics=tool_metrics)

# Modern tab endpoints for new task detail interface

@analysis_bp.route('/api/tasks/<task_id>/tabs/overview')
def task_tab_overview(task_id: str):
    """HTMX fragment: Overview tab with summary dashboard and key metrics."""
    return _render_task_tab('pages/analysis/partials/tab_overview.html', task_id)

@analysis_bp.route('/api/tasks/<task_id>/tabs/security')
def task_tab_security(task_id: str):
    """HTMX fragment: Security tools tab (Bandit, Semgrep, ZAP, etc.)."""
    return _render_task_tab('pages/analysis/partials/tab_security.html', task_id)

@analysis_bp.route('/api/tasks/<task_id>/tabs/quality')
def task_tab_quality(task_id: str):
    """HTMX fragment: Code quality tools tab (ESLint, Pylint, Mypy, Vulture)."""
    return _render_task_tab('pages/analysis/partials/tab_quality.html', task_id)

@analysis_bp.route('/api/tasks/<task_id>/tabs/dependencies')
def task_tab_dependencies(task_id: str):
    """HTMX fragment: Dependencies tab (Safety, Snyk, package analysis)."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_enhanced_task_payload(task_id)  # type: ignore[attr-defined]
        deps_tools = insp.get_dependency_tools_report(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/tabs/dependencies.html', 
                             task_id=task_id, payload=payload, deps_tools=deps_tools)
    except Exception as e:
        return f'<div class="alert alert-danger">Error loading dependencies tab: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/tabs/findings')
def task_tab_findings(task_id: str):
    """HTMX fragment: Unified findings tab with all issues from all tools."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_enhanced_task_payload(task_id)  # type: ignore[attr-defined]
        unified_findings = insp.get_unified_findings(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/tabs/findings.html', 
                             task_id=task_id, payload=payload, findings=unified_findings)
    except Exception as e:
        return f'<div class="alert alert-danger">Error loading findings tab: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/tabs/explorer')
def task_tab_explorer(task_id: str):
    """HTMX fragment: Raw data explorer tab with tool outputs and JSON data."""
    return _render_task_tab('pages/analysis/partials/tab_explorer.html', task_id)


@analysis_bp.route('/api/tasks/<task_id>/tabs/performance')
def task_tab_performance(task_id: str):
    """HTMX fragment: Performance testing tab with Apache Bench, Locust, aiohttp results."""
    return _render_task_tab('pages/analysis/partials/tab_performance.html', task_id)


@analysis_bp.route('/api/tasks/<task_id>/tabs/requirements')
def task_tab_requirements(task_id: str):
    """HTMX fragment: AI requirements analysis tab with functional requirement compliance."""
    return _render_task_tab('pages/analysis/partials/tab_requirements.html', task_id)


@analysis_bp.route('/api/tasks/<task_id>/export/sarif')
def task_export_sarif(task_id: str):
    """Export task results in SARIF format for integration with other tools."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return jsonify({'error': 'Inspection service unavailable'}), 500
    try:
        sarif_data = insp.export_to_sarif(task_id)  # type: ignore[attr-defined]
        response = make_response(json.dumps(sarif_data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename="{task_id}.sarif"'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analysis_bp.route('/api/tasks/<task_id>/refresh')
def task_refresh(task_id: str):
    """Refresh task data and return updated content."""
    try:
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            return '<div class="alert alert-danger">Task not found</div>'
        
        # Force refresh of cached data
        insp = ServiceLocator.get('analysis_inspection_service')
        if insp and hasattr(insp, 'clear_cache'):
            insp.clear_cache(task_id)  # type: ignore[attr-defined]
            
        return render_template('pages/analysis/task_detail_main.html', task=task, task_id=task_id)
    except Exception as e:
        return f'<div class="alert alert-danger">Error refreshing task: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/refresh-content')
def task_refresh_content(task_id: str):
    """Refresh only the executive summary content without changing the page layout."""
    try:
        # Force refresh of cached data
        insp = ServiceLocator.get('analysis_inspection_service')
        if insp and hasattr(insp, 'clear_cache'):
            insp.clear_cache(task_id)  # type: ignore[attr-defined]
            
        # Return just the summary dashboard content
        payload = insp.get_task_results_payload(task_id) if insp else {}  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/summary_dashboard.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:
        return f'<div class="alert alert-danger">Error refreshing content: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/debug-payload')
def task_debug_payload(task_id: str):
    """Debug endpoint to show the raw payload data."""
    try:
        insp = ServiceLocator.get('analysis_inspection_service')
        if not insp:
            return '<div class="alert alert-danger">Inspection service unavailable</div>'
        
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        
        # Return formatted JSON for debugging
        import json
        return f'<pre>{json.dumps(payload, indent=2, default=str)}</pre>'
    except Exception as e:
        return f'<div class="alert alert-danger">Error loading debug payload: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/summary-dashboard')
def task_summary_dashboard(task_id: str):
    """HTMX fragment: executive summary dashboard with key metrics and charts."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/summary_dashboard.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger">Error loading summary: {e}</div>'

# Modern task detail tab routes (simple URLs for easy navigation)
@analysis_bp.route('/tasks/<task_id>/overview')
def task_overview_simple(task_id: str):
    """Simple URL for overview tab."""
    return task_overview_tab(task_id)

@analysis_bp.route('/tasks/<task_id>/security')
def task_security_simple(task_id: str):
    """Simple URL for security tab."""
    return task_security_tools_tab(task_id)

@analysis_bp.route('/tasks/<task_id>/quality')
def task_quality_simple(task_id: str):
    """Simple URL for quality tab."""
    return task_quality_tools_tab(task_id)

@analysis_bp.route('/tasks/<task_id>/dependencies')
def task_dependencies_simple(task_id: str):
    """Simple URL for dependencies tab."""
    return task_dependency_tools_tab(task_id)

@analysis_bp.route('/tasks/<task_id>/findings')
def task_findings_simple(task_id: str):
    """Simple URL for findings tab."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/all_findings_tab.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:
        return f'<div class="alert alert-danger">Error loading findings: {e}</div>'

@analysis_bp.route('/tasks/<task_id>/explorer')
def task_explorer_simple(task_id: str):
    """Simple URL for code explorer tab."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/code_explorer_tab.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:
        return f'<div class="alert alert-danger">Error loading explorer: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/overview')
def task_overview_tab(task_id: str):
    """HTMX fragment: overview tab with general analysis information."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/overview_tab.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger">Error loading overview: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/security-tools')
def task_security_tools_tab(task_id: str):
    """HTMX fragment: security tools analysis with detailed reports."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/security_tools_tab.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger">Error loading security tools: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/quality-tools')
def task_quality_tools_tab(task_id: str):
    """HTMX fragment: code quality tools analysis."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/quality_tools_tab.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger">Error loading quality tools: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/dependency-tools')
def task_dependency_tools_tab(task_id: str):
    """HTMX fragment: dependency analysis tools."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return '<div class="alert alert-danger">Inspection service unavailable</div>'
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        return render_template('pages/analysis/partials/dependency_tools_tab.html', 
                             task_id=task_id, payload=payload)
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger">Error loading dependency tools: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/all-findings')
def task_all_findings_tab(task_id: str):
    """HTMX fragment: unified view of all findings across tools."""
    try:
        insp = ServiceLocator.get_analysis_inspection_service()
        if not insp:
            return '<div class="alert alert-danger">Inspection service unavailable</div>'
        
        analysis = insp.get_task(task_id)  # type: ignore[attr-defined]
        
        # Get comprehensive findings data
        payload = insp.get_comprehensive_findings(analysis)  # type: ignore[attr-defined]
        
        return render_template('pages/analysis/partials/all_findings_tab.html', 
                             analysis=analysis, payload=payload)
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger">Error loading findings: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/code-explorer')
def task_code_explorer_tab(task_id: str):
    """HTMX fragment: interactive code explorer with syntax highlighting."""
    try:
        insp = ServiceLocator.get_analysis_inspection_service()
        if not insp:
            return '<div class="alert alert-danger">Inspection service unavailable</div>'
        
        analysis = insp.get_task(task_id)  # type: ignore[attr-defined]
        
        # Get code exploration data
        payload = insp.get_code_exploration_data(analysis)  # type: ignore[attr-defined]
        
        return render_template('pages/analysis/partials/code_explorer_tab.html', 
                             analysis=analysis, payload=payload)
    except Exception as e:  # pragma: no cover
        return f'<div class="alert alert-danger">Error loading code explorer: {e}</div>'

@analysis_bp.route('/api/tasks/<task_id>/export/sarif')
def export_task_sarif(task_id: str):
    """Export analysis results in SARIF format."""
    insp = ServiceLocator.get('analysis_inspection_service')
    if not insp:
        return jsonify({'error': 'Inspection service unavailable'}), 500
    try:
        payload = insp.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        sarif_data = _convert_to_sarif(payload)
        
        response = make_response(json.dumps(sarif_data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename="task_{task_id}_analysis.sarif"'
        return response
    except Exception as e:  # pragma: no cover
        return jsonify({'error': f'SARIF export failed: {e}'}), 500

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_stats_snapshot(tasks):
    """Derive stats summary dict from a list of task ORM objects."""
    try:
        return {
            'total_tasks': AnalysisTask.query.count(),
            'active_tasks': len([t for t in tasks if getattr(t.status, 'value', t.status) in ('running', 'pending')]),
            'completed_tasks': len([t for t in tasks if getattr(t.status, 'value', t.status) == 'completed']),
            'failed_tasks': len([t for t in tasks if getattr(t.status, 'value', t.status) == 'failed'])
        }
    except Exception:  # pragma: no cover - defensive
        return {
            'total_tasks': 0,
            'active_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0
        }

def _convert_to_sarif(payload: dict) -> dict:
    """Convert analysis payload to SARIF 2.1.0 format."""
    from datetime import datetime
    
    # SARIF 2.1.0 structure
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "ThesisApp Security Analysis",
                    "version": "1.0.0",
                    "informationUri": "https://github.com/ThesisApp",
                    "rules": []
                }
            },
            "invocation": {
                "executionSuccessful": payload.get('status') == 'completed',
                "startTimeUtc": datetime.now().isoformat() + 'Z'
            },
            "results": []
        }]
    }
    
    # Convert findings to SARIF results
    findings = payload.get('findings_preview', [])
    rules = set()
    
    for finding in findings:
        rule_id = f"{finding.get('tool', 'unknown')}.{finding.get('category', 'general')}"
        rules.add(rule_id)
        
        result = {
            "ruleId": rule_id,
            "message": {
                "text": finding.get('message', finding.get('title', 'No description'))
            },
            "level": _map_severity_to_sarif(finding.get('severity', 'info')),
            "locations": []
        }
        
        # Add location if available
        if finding.get('file_path'):
            location = {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": finding['file_path']
                    }
                }
            }
            
            if finding.get('line_number'):
                location['physicalLocation']['region'] = {
                    "startLine": finding['line_number']
                }
                if finding.get('column'):
                    location['physicalLocation']['region']['startColumn'] = finding['column']
            
            result['locations'].append(location)
        
        sarif['runs'][0]['results'].append(result)
    
    # Add rules definitions
    for rule_id in rules:
        tool_name, category = rule_id.split('.', 1) if '.' in rule_id else (rule_id, 'general')
        sarif['runs'][0]['tool']['driver']['rules'].append({
            "id": rule_id,
            "name": category.title().replace('-', ' '),
            "shortDescription": {
                "text": f"{tool_name.title()} {category.replace('-', ' ')} check"
            },
            "helpUri": f"https://docs.thesisapp.com/rules/{tool_name}/{category}"
        })
    
    return sarif

def _map_severity_to_sarif(severity: str) -> str:
    """Map internal severity levels to SARIF levels."""
    severity = severity.lower()
    if severity in ['critical', 'high', 'error']:
        return 'error'
    elif severity in ['medium', 'warning']:
        return 'warning'
    elif severity in ['low', 'info']:
        return 'info'
    else:
        return 'note'