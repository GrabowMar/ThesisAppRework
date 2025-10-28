"""
Analysis routes for the Flask application
=======================================

Analysis-related web routes that render Jinja templates.
"""

import json
from typing import List, Optional

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    request,
    send_file,
    url_for,
)
from flask_login import current_user

from app.utils.template_paths import render_template_compat as render_template
from app.services.task_service import AnalysisTaskService
from app.services.unified_result_service import UnifiedResultService
from app.models.analysis_models import AnalysisTask
from app.constants import AnalysisStatus
from app.extensions import db
from sqlalchemy import or_

# Create blueprint
analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')

# Require authentication for all analysis routes
@analysis_bp.before_request
def require_authentication():
    """Require authentication for all analysis endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access analysis features.', 'info')
        return redirect(url_for('auth.login', next=request.url))

@analysis_bp.errorhandler(400)
def bad_request(error):
    return render_template('pages/errors/errors_main.html', error_code=400, error_message=str(error)), 400

@analysis_bp.errorhandler(404)
def not_found(error):
    return render_template('pages/errors/errors_main.html', error_code=404, error_message=str(error)), 404

@analysis_bp.errorhandler(500)
def internal_error(error):
    return render_template('pages/errors/errors_main.html', error_code=500, error_message=str(error)), 500

@analysis_bp.route('/list')
def analysis_list():
    """Render minimal analysis page shell - actual content loaded via HTMX."""
    return render_template('pages/analysis/analysis_main.html')


@analysis_bp.route('/api/tasks/list')
def analysis_tasks_table():
    """HTMX endpoint: Return table content with unified tasks + results, with pagination."""
    service = UnifiedResultService()
    
    # Parse filters
    model_filter = (request.args.get('model') or '').strip() or None
    app_filter_raw = (request.args.get('app') or '').strip() or None
    status_filter = (request.args.get('status') or '').strip() or None
    
    app_filter = None
    if app_filter_raw and app_filter_raw.isdigit():
        app_filter = int(app_filter_raw)
    
    # Parse pagination
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(100, max(10, int(request.args.get('per_page', 25))))

    # Get ALL tasks from database (including completed ones to preserve hierarchy)
    try:
        # Only show main tasks or tasks without parents (filter out subtasks)
        all_tasks_query = AnalysisTask.query.filter(
            or_(
                AnalysisTask.is_main_task == True,
                AnalysisTask.parent_task_id == None
            )
        )
        
        if model_filter:
            all_tasks_query = all_tasks_query.filter(AnalysisTask.target_model.ilike(f'%{model_filter}%'))
        if app_filter is not None:
            all_tasks_query = all_tasks_query.filter(AnalysisTask.target_app_number == app_filter)
        if status_filter:
            # Map status filter to enum
            status_map = {
                'pending': AnalysisStatus.PENDING,
                'running': AnalysisStatus.RUNNING,
                'completed': AnalysisStatus.COMPLETED,
                'failed': AnalysisStatus.FAILED
            }
            if status_filter in status_map:
                all_tasks_query = all_tasks_query.filter(AnalysisTask.status == status_map[status_filter])
        
        all_tasks = all_tasks_query.order_by(AnalysisTask.created_at.desc()).all()
    except Exception as exc:  # pragma: no cover
        current_app.logger.exception("Failed to query tasks: %s", exc)
        all_tasks = []

    # Pagination for all tasks
    total_tasks = len(all_tasks)
    
    # Calculate pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated_tasks = all_tasks[start:end]

    # Preload available result files for tasks shown on this page
    result_lookup: dict[tuple[str, int], List[dict]] = {}
    if paginated_tasks:
        task_pairs = {(task.target_model, task.target_app_number) for task in paginated_tasks}
        for model_slug, app_number in task_pairs:
            try:
                result_files = service.list_result_files(model_slug=model_slug, app_number=app_number)
            except Exception as exc:  # pragma: no cover - defensive logging
                current_app.logger.warning(
                    "Failed to load results for %s app%s: %s", model_slug, app_number, exc
                )
                result_files = []
            if result_files:
                result_lookup[(model_slug, app_number)] = result_files

    def _select_result_file(
        task: AnalysisTask, result_files: List[dict]
    ) -> Optional[dict]:
        """Select the most relevant result file for a task."""
        if not result_files:
            return None

        # Find result file matching task_id
        for rf in result_files:
            if rf.get('task_id') == task.task_id:
                return rf
        
        # Fallback: return most recent
        return result_files[0] if result_files else None

    # Build unified list from paginated tasks
    unified_items = []

    # Add tasks with hierarchy preserved
    for task in paginated_tasks:
        # Get subtasks if this is a main task
        subtasks_data = []
        if task.is_main_task and task.subtasks:
            try:
                for subtask in task.subtasks:
                    subtasks_data.append({
                        'task_id': subtask.task_id,
                        'service_name': subtask.service_name or 'unknown',
                        'status': subtask.status.value.lower() if subtask.status else 'unknown',
                        'progress': subtask.progress_percentage or 0,
                        'task_name': subtask.task_name or subtask.task_id[:16]
                    })
            except Exception as exc:
                current_app.logger.warning(f"Failed to load subtasks for {task.task_id}: {exc}")
        
        result_files = result_lookup.get((task.target_model, task.target_app_number), [])
        selected_result = _select_result_file(task, result_files) if result_files else None

        unified_items.append({
            'type': 'task',
            'id': task.task_id,
            'model': task.target_model,
            'app': task.target_app_number,
            'analysis_type': task.analysis_type.value if task.analysis_type else 'N/A',
            'status': task.status.value.lower() if task.status else 'unknown',
            'priority': task.priority.value if task.priority else 'normal',
            'progress': task.progress_percentage or 0,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'task_name': task.task_name or task.task_id[:16],
            'is_main_task': task.is_main_task,
            'subtasks': subtasks_data,
            'obj': task,
            'result_descriptor': selected_result,
            'result_identifier': selected_result.get('task_id') if selected_result else None,
            'result_status': 'completed' if selected_result else None,
            'result_timestamp': selected_result.get('modified_at') if selected_result else None,
            'has_result': selected_result is not None,
        })
    
    # Pagination info
    total_pages = (total_tasks + per_page - 1) // per_page if total_tasks > 0 else 1
    has_prev = page > 1
    has_next = page < total_pages
    
    # Count by status for display
    active_count = len([t for t in all_tasks if t.status in [AnalysisStatus.PENDING, AnalysisStatus.RUNNING]])
    completed_count = len([t for t in all_tasks if t.status == AnalysisStatus.COMPLETED])
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_tasks,
        'total_completed': completed_count,
        'active_count': active_count,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': page - 1 if has_prev else None,
        'next_num': page + 1 if has_next else None,
        'pages': total_pages
    }
    
    html = render_template(
        'pages/analysis/partials/tasks_table.html',
        items=unified_items,
        pagination=pagination,
        model_filter=model_filter,
        app_filter=app_filter_raw,
        status_filter=status_filter
    )
    
    resp = make_response(html)
    resp.headers['X-Partial'] = 'analysis-tasks-table'
    return resp

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
                        # For custom selections spanning multiple services, create main task with subtasks
                        task = AnalysisTaskService.create_main_task_with_subtasks(
                            model_slug=mslug,
                            app_number=anum,
                            analysis_type='unified',
                            tools_by_service=tools_by_service,
                            priority=priority,
                            custom_options={
                                'selected_tools': ordered_ids,
                                'selected_tool_names': selected_tool_names,
                                'tools_by_service': tools_by_service,
                                'unified_analysis': True,
                                'source': 'wizard_custom'
                            },
                            task_name=f"custom:{mslug}:{anum}"
                        )
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
                                'unified_analysis': False,
                                'source': 'wizard_custom'
                            }
                        )
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
                        
                        # Create main task with subtasks
                        task = AnalysisTaskService.create_main_task_with_subtasks(
                            model_slug=mslug,
                            app_number=anum,
                            analysis_type=analysis_type,
                            tools_by_service=tools_by_service,
                            priority=priority,
                            custom_options={
                                'selected_tools': all_tool_ids,
                                'selected_tool_names': all_tool_names,
                                'source': 'wizard_profile_security',
                                'unified_analysis': True,
                                'tools_by_service': tools_by_service,
                            },
                            task_name=f"{analysis_profile}:{mslug}:{anum}"
                        )
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

def _get_result_service() -> UnifiedResultService:
    """Return a cached UnifiedResultService instance for the current app."""
    if not hasattr(current_app, '_unified_result_service'):
        current_app._unified_result_service = UnifiedResultService()  # type: ignore[attr-defined]
    return current_app._unified_result_service  # type: ignore[attr-defined]


@analysis_bp.route('/results/<string:result_id>')
def analysis_result_detail(result_id: str):
    """Render the detail page for a stored analysis result file."""
    service = _get_result_service()
    findings_limit: Optional[int] = None
    limit_param = (request.args.get('findings') or '').strip()
    if limit_param.isdigit():
        findings_limit = max(1, min(int(limit_param), 1000))

    try:
        results = service.load_analysis_results(result_id)
        if not results:
            abort(404, description=f"Result {result_id} not found")
        payload = results.raw_data
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Failed to load analysis result %s: %s", result_id, exc)
        abort(500, description="Unable to load analysis result")

    # Extract findings and services from structured results
    findings = results.security.get('findings', [])[:findings_limit] if findings_limit else results.security.get('findings', [])
    services = results.tools
    summary_block = results.summary
    task_info = {'task_id': result_id, 'status': results.status}
    metadata_block = {}

    return render_template(
        'pages/analysis/result_detail.html',
        descriptor={'identifier': result_id, 'task_id': result_id},
        payload=payload,
        findings=findings,
        services=services,
        summary=summary_block,
        task_info=task_info,
        metadata=metadata_block,
        findings_limit=findings_limit,
    )


@analysis_bp.route('/results/<string:result_id>.json')
def analysis_result_json(result_id: str):
    """Return the raw JSON payload for an analysis result."""
    service = _get_result_service()
    try:
        results = service.load_analysis_results(result_id)
        if not results:
            return jsonify({'error': 'result not found'}), 404
        payload = results.raw_data
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Failed to serialise analysis result %s: %s", result_id, exc)
        return jsonify({'error': 'unable to load result'}), 500

    response = make_response(json.dumps(payload, indent=2, default=str))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['X-Analysis-Result'] = result_id
    return response


@analysis_bp.route('/results/<string:result_id>/download')
def analysis_result_download(result_id: str):
    """Send the stored JSON file for download."""
    service = _get_result_service()
    path = service.find_path_by_identifier(result_id)
    if not path or not path.exists():
        abort(404, description=f"Result {result_id} not found")
    return send_file(
        path,
        mimetype='application/json',
        as_attachment=True,
        download_name=f"{result_id}.json",
    )


@analysis_bp.route('/tasks/<string:task_id>/export/sarif')
def export_task_sarif(task_id: str):
    """Export analysis results in SARIF 2.1.0 format.
    
    Attempts to load pre-generated SARIF document from file system.
    If not found, returns 404 with suggestion to check if analysis was SARIF-enabled.
    """
    from app.paths import RESULTS_DIR
    from pathlib import Path
    
    # Get task to extract model_slug and app_number
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if not task:
        abort(404, description=f"Task {task_id} not found")
    
    model_slug = task.target_model
    app_number = task.target_app_number
    
    if not model_slug or not app_number:
        abort(400, description="Task missing model_slug or app_number - cannot locate SARIF file")
    
    # Look for SARIF file: results/{model}/app{N}/analysis/{task_id}/consolidated.sarif.json
    sarif_path = RESULTS_DIR / model_slug / f"app{app_number}" / "analysis" / task_id / "consolidated.sarif.json"
    
    if not sarif_path.exists():
        abort(404, description=f"SARIF file not found for task {task_id}. Analysis may not have generated SARIF output.")
    
    current_app.logger.info(f"Serving SARIF export for task {task_id} from {sarif_path}")
    
    return send_file(
        sarif_path,
        mimetype='application/json',
        as_attachment=True,
        download_name=f"{task_id}.sarif.json",
    )
