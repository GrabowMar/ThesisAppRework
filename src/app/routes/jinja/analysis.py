"""
Analysis routes for the Flask application
=======================================

Analysis-related web routes that render Jinja templates.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple

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
from app.models import AnalysisTask, GeneratedApplication, AnalysisResult
from app.constants import AnalysisStatus
from app.extensions import db
from sqlalchemy import or_, func

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
            'analysis_type': task.analysis_type or 'N/A',
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
    """Render and process the Analysis Creation Wizard."""
    if request.method == 'POST':
        form = request.form
        model_slug = (form.get('model_slug') or '').strip()
        app_number_raw = form.get('app_number') or ''
        analysis_mode = (form.get('analysis_mode') or '').strip()
        analysis_profile = (form.get('analysis_profile') or '').strip()
        selected_tools = form.getlist('selected_tools[]')
        priority = (form.get('priority') or 'normal').strip()

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

        def _parse_selection(model_value: str, app_value: str) -> List[Tuple[str, int]]:
            pairs: List[Tuple[str, int]] = []
            m_list = [m.strip() for m in (model_value or '').split(',') if m.strip()]
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

            app_numbers: List[int] = []
            for raw in [x.strip() for x in (app_value or '').split(',') if x.strip()]:
                try:
                    app_numbers.append(int(raw))
                except Exception:
                    continue

            if not m_list and model_value:
                m_list = [model_value]

            for m in m_list or []:
                for anum in app_numbers or []:
                    pairs.append((m, anum))

            if not pairs and model_value and app_value:
                try:
                    pairs.append((model_value, int(app_value)))
                except Exception:
                    pass
            return pairs

        selection_pairs = _parse_selection(model_slug, app_number_raw)

        errors: List[str] = []
        if not selection_pairs:
            if not model_slug:
                errors.append('Model is required')
            errors.append('Valid application number required')

        if analysis_mode == 'profile':
            if not analysis_profile:
                errors.append('Analysis profile is required when using profile mode')
        elif analysis_mode == 'custom':
            if not selected_tools:
                errors.append('At least one tool must be selected for custom analysis')
        else:
            errors.append('Analysis mode (profile or custom) is required')

        if errors:
            for message in errors:
                flash(message, 'danger')
            return render_template('pages/analysis/create.html'), 400

        missing_targets: List[str] = []
        for mslug, anum in selection_pairs:
            exists = GeneratedApplication.query.filter_by(model_slug=mslug, app_number=anum).first()
            if not exists:
                missing_targets.append(f"{mslug}/app{anum}")
        if missing_targets:
            for target in missing_targets:
                flash(f"Application not found: {target}", 'danger')
            return render_template('pages/analysis/create.html'), 404

        try:
            from app.engines.container_tool_registry import get_container_tool_registry

            registry = get_container_tool_registry()
            registry_tools = registry.get_all_tools()

            tool_sequence = list(registry_tools.items())
            tool_name_to_id: Dict[str, int] = {name: idx + 1 for idx, (name, _) in enumerate(tool_sequence)}
            tool_id_to_name: Dict[str, str] = {str(idx + 1): name for idx, (name, _) in enumerate(tool_sequence)}
            tool_lower_to_name: Dict[str, str] = {name.lower(): name for name, _ in tool_sequence}

            def canonicalize_inputs(raw_values: List[str]) -> Tuple[List[str], List[str]]:
                canonical: List[str] = []
                errors_local: List[str] = []
                seen: Set[str] = set()
                for raw in raw_values:
                    raw_s = str(raw).strip()
                    if not raw_s:
                        continue
                    candidate = tool_id_to_name.get(raw_s) if raw_s.isdigit() else None
                    if candidate is None:
                        candidate = tool_lower_to_name.get(raw_s.lower())
                    if candidate is None:
                        errors_local.append(f"Unknown tool: {raw_s}")
                        continue
                    tool_obj = registry_tools.get(candidate)
                    if not tool_obj or not tool_obj.available:
                        errors_local.append(f"Tool unavailable: {raw_s}")
                        continue
                    if candidate not in seen:
                        seen.add(candidate)
                        canonical.append(candidate)
                return canonical, errors_local

            def build_tool_payload(canonical_names: List[str]) -> Tuple[List[int], List[str], List[str], Dict[str, List[int]]]:
                ids: List[int] = []
                names: List[str] = []
                display_names: List[str] = []
                grouped: Dict[str, List[int]] = {}
                for name in canonical_names:
                    tool_obj = registry_tools.get(name)
                    if not tool_obj or not tool_obj.available:
                        continue
                    canonical_name = tool_obj.name
                    names.append(canonical_name)
                    display_names.append(tool_obj.display_name or canonical_name)
                    tool_id = tool_name_to_id.get(name)
                    if tool_id is None:
                        continue
                    ids.append(tool_id)
                    service = tool_obj.container.value if tool_obj.container else 'unknown'
                    grouped.setdefault(service, []).append(tool_id)
                return ids, names, display_names, grouped

            def enqueue_for_targets(
                targets: List[Tuple[str, int]],
                tool_names: List[str],
                tool_ids: List[int],
                tools_by_service_map: Dict[str, List[int]],
                priority_value: str,
                base_options: Dict[str, Any],
            ) -> Tuple[List[AnalysisTask], int]:
                created: List[AnalysisTask] = []
                subtask_total = 0
                for mslug, anum in targets:
                    options = dict(base_options)
                    options['selected_tools'] = list(tool_ids)
                    options['selected_tool_names'] = list(tool_names)
                    options['tools_by_service'] = {svc: list(ids) for svc, ids in tools_by_service_map.items()}
                    use_subtasks = len(options['tools_by_service']) > 1
                    options['unified_analysis'] = use_subtasks

                    if use_subtasks:
                        # Service determines grouping internally from tool names
                        task = AnalysisTaskService.create_main_task_with_subtasks(
                            model_slug=mslug,
                            app_number=anum,
                            tools=tool_names,
                            priority=priority_value,
                            custom_options=options,
                        )
                        # Service returns number of subtasks implicitly
                        subtask_total += use_subtasks  # Count will be updated by service
                    else:
                        task = AnalysisTaskService.create_task(
                            model_slug=mslug,
                            app_number=anum,
                            tools=tool_names,
                            priority=priority_value,
                            custom_options=options,
                        )
                    created.append(task)
                return created, subtask_total

            created_tasks: List[AnalysisTask] = []
            total_subtasks = 0

            if analysis_mode == 'custom':
                canonical_selection, invalid_entries = canonicalize_inputs(selected_tools)
                if invalid_entries:
                    for message in invalid_entries:
                        flash(message, 'danger')
                    return render_template('pages/analysis/create.html'), 400

                if not canonical_selection:
                    flash('No valid tools selected after validation.', 'danger')
                    return render_template('pages/analysis/create.html'), 400

                tool_ids, tool_names, tool_display_names, tools_by_service = build_tool_payload(canonical_selection)
                if not tools_by_service:
                    flash('No valid tools selected after validation.', 'danger')
                    return render_template('pages/analysis/create.html'), 400

                try:
                    current_app.logger.debug(
                        "analysis_create custom selection: services=%s tool_names=%s",
                        list(tools_by_service.keys()),
                        tool_names,
                    )
                except Exception:
                    pass

                base_options: Dict[str, Any] = {
                    'selected_tools': tool_ids,
                    'selected_tool_names': tool_names,
                    'selected_tool_display_names': tool_display_names,
                    'tools_by_service': tools_by_service,
                    'source': 'wizard_custom',
                    'analysis_type': 'custom',
                }

                new_tasks, subtask_count = enqueue_for_targets(
                    selection_pairs,
                    tool_names,
                    tool_ids,
                    tools_by_service,
                    priority,
                    base_options,
                )
                created_tasks.extend(new_tasks)
                total_subtasks += subtask_count

            else:
                profile_key = analysis_profile.lower()
                canonical_profile: List[str] = []
                for name, tool in registry_tools.items():
                    if not tool.available:
                        continue
                    tags_lower = {tag.lower() for tag in tool.tags}
                    if profile_key in ('comprehensive', 'unified') or profile_key in tags_lower:
                        canonical_profile.append(name)

                if not canonical_profile:
                    flash(f"Unknown or empty analysis profile: {analysis_profile}", 'danger')
                    return render_template('pages/analysis/create.html'), 400

                tool_ids, tool_names, tool_display_names, tools_by_service = build_tool_payload(canonical_profile)
                if not tool_names:
                    flash(f"No available tools for profile {analysis_profile}", 'danger')
                    return render_template('pages/analysis/create.html'), 400

                base_options: Dict[str, Any] = {
                    'selected_tools': tool_ids,
                    'selected_tool_names': tool_names,
                    'selected_tool_display_names': tool_display_names,
                    'tools_by_service': tools_by_service,
                    'source': f'wizard_profile_{profile_key}',
                    'analysis_type': profile_key,
                    'selected_profile': profile_key,
                }

                new_tasks, subtask_count = enqueue_for_targets(
                    selection_pairs,
                    tool_names,
                    tool_ids,
                    tools_by_service,
                    priority,
                    base_options,
                )
                created_tasks.extend(new_tasks)
                total_subtasks += subtask_count

            if not created_tasks:
                flash('No analysis tasks were created.', 'warning')
                return render_template('pages/analysis/create.html'), 500

            success_message = f"Launched {len(created_tasks)} analysis task(s)"
            if total_subtasks:
                success_message += f" across {total_subtasks} analyzer service runs"
            flash(success_message + '.', 'success')

        except Exception as exc:  # pragma: no cover - defensive logging
            current_app.logger.exception('analysis_create failed inside processing block')
            flash(f'Error creating analysis task: {exc}', 'danger')
            return render_template('pages/analysis/create.html'), 500

        return redirect(url_for('analysis.analysis_list'))

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
    if tool in ('ai-requirements', 'requirements-analyzer'):
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
            tools=[tool],
            priority='normal',
            custom_options={
                'selected_tools': [tool_id],
                'selected_tool_names': [tool],
                'tools_by_service': tools_by_service,
                'selected_tool_display_names': [tool],
                'analysis_type': 'ai',
                'unified_analysis': False,
                'source': 'quick_ai_endpoint'
            }
        )
        try:
            meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            meta.update({
                'selected_tools': [tool_id],
                'selected_tool_names': [tool],
                'selected_tool_display_names': [tool],
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


@analysis_bp.route('/tasks/<string:task_id>')
def analysis_task_detail(task_id: str):
    """Render the detail page for an analysis task with database-backed results."""
    # Load task from database
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if not task:
        abort(404, description=f"Task {task_id} not found")
    
    # Query all findings for this task
    findings_query = AnalysisResult.query.filter_by(task_id=task_id)
    
    # Support optional findings limit parameter
    findings_limit: Optional[int] = None
    limit_param = (request.args.get('findings') or '').strip()
    if limit_param.isdigit():
        findings_limit = max(1, min(int(limit_param), 1000))
        findings_query = findings_query.limit(findings_limit)
    
    # Get all findings
    findings = findings_query.all()
    
    # Group results by tool name
    results_by_tool = {}
    for finding in findings:
        tool_name = finding.tool_name or 'unknown'
        if tool_name not in results_by_tool:
            results_by_tool[tool_name] = []
        results_by_tool[tool_name].append(finding)
    
    # Calculate severity breakdown using SQLAlchemy
    severity_counts = db.session.query(
        AnalysisResult.severity,
        func.count(AnalysisResult.id).label('count')
    ).filter_by(task_id=task_id).group_by(AnalysisResult.severity).all()
    
    # Build summary dict
    summary = {
        'total_findings': len(findings),
        'severity_breakdown': {str(sev): count for sev, count in severity_counts},
        'tools_used': list(results_by_tool.keys()),
        'tools_count': len(results_by_tool)
    }
    
    # Add zero counts for missing severities
    from app.constants import SeverityLevel
    for severity in SeverityLevel:
        if severity.value not in summary['severity_breakdown']:
            summary['severity_breakdown'][severity.value] = 0
    
    return render_template(
        'pages/analysis/task_detail.html',
        task=task,
        findings=findings,
        results_by_tool=results_by_tool,
        summary=summary,
        findings_limit=findings_limit,
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
