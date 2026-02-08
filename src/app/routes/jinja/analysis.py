"""
Analysis routes for the Flask application
=======================================

Analysis-related web routes that render Jinja templates.
"""

import json
from datetime import datetime
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
from werkzeug.exceptions import HTTPException

from flask import render_template
from app.services.task_service import AnalysisTaskService
from app.services.unified_result_service import UnifiedResultService
from app.models import AnalysisTask, GeneratedApplication
from app.constants import AnalysisStatus
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, defer


# Helper class for descriptor objects
class DescriptorDict(dict):
    """Dictionary that allows attribute access and has display_timestamp method."""
    def __getattr__(self, key):
        return self.get(key)
    def display_timestamp(self):
        if self.get('modified_at'):
            dt = self['modified_at']
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
            if isinstance(dt, datetime):
                return dt.strftime('%Y-%m-%d %H:%M:%S')
        return 'N/A'


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

    try:
        # Base query with optimizations
        # 1. Eager load subtasks to prevent N+1 queries
        # 2. Defer large text fields to reduce memory/bandwidth
        query = AnalysisTask.query.options(
            joinedload(AnalysisTask.subtasks),  # type: ignore[arg-type]
            defer(AnalysisTask.result_summary),  # type: ignore[arg-type]
            defer(AnalysisTask.execution_context),  # type: ignore[arg-type]
            defer(AnalysisTask.task_metadata),  # type: ignore[arg-type]
            defer(AnalysisTask.error_message)  # type: ignore[arg-type]
        ).filter(
            or_(
                AnalysisTask.is_main_task == True,
                AnalysisTask.parent_task_id == None
            )
        )

        # Apply filters
        if model_filter:
            query = query.filter(AnalysisTask.target_model.ilike(f'%{model_filter}%'))
        if app_filter is not None:
            query = query.filter(AnalysisTask.target_app_number == app_filter)
        if status_filter:
            status_map = {
                'pending': AnalysisStatus.PENDING,
                'running': AnalysisStatus.RUNNING,
                'completed': AnalysisStatus.COMPLETED,
                'failed': AnalysisStatus.FAILED
            }
            if status_filter in status_map:
                query = query.filter(AnalysisTask.status == status_map[status_filter])  # type: ignore[arg-type]
        
        # Order by creation date
        query = query.order_by(AnalysisTask.created_at.desc())

        # Use database pagination
        pagination_obj = query.paginate(page=page, per_page=per_page, error_out=False)
        paginated_tasks = pagination_obj.items
        total_tasks = pagination_obj.total

    except Exception as exc:  # pragma: no cover
        current_app.logger.exception("Failed to query tasks: %s", exc)
        paginated_tasks = []
        total_tasks = 0
        pagination_obj = None

    def _select_result_descriptor(task: AnalysisTask) -> Optional[DescriptorDict]:
        """Create result descriptor from task DB columns (fast)."""
        if task.status in [AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS, AnalysisStatus.FAILED]:
            # Use proper fallback that preserves explicit zeros
            total_findings = task.issues_found if task.issues_found is not None else 0
            
            return DescriptorDict({
                'identifier': task.task_id,
                'task_id': task.task_id,
                'source': 'database',
                'task_name': task.task_name or task.task_id[:16],
                'model_slug': task.target_model,
                'app_number': task.target_app_number,
                'status': task.status.value if task.status else 'unknown',
                'total_findings': total_findings,
                'severity_breakdown': task.get_severity_breakdown(),
                'tools_executed': 0, 
                'tools_failed': 0,
                'tools_used': [],
                'modified_at': task.completed_at,
                'has_data': True
            })
        return None

    # Build unified list from paginated tasks
    unified_items = []

    for task in paginated_tasks:
        # Get subtasks data (already eager loaded)
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
                current_app.logger.warning(f"Failed to process subtasks for {task.task_id}: {exc}")

        selected_result = _select_result_descriptor(task)
        
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

    # Efficient counts - apply same filters to counts for consistency
    # Base query for counts (apply model and app filters to show filtered counts)
    def _build_count_query(statuses):
        q = AnalysisTask.query.filter(AnalysisTask.status.in_(statuses))  # type: ignore[union-attr]
        if model_filter:
            q = q.filter(AnalysisTask.target_model.ilike(f'%{model_filter}%'))
        if app_filter is not None:
            q = q.filter(AnalysisTask.target_app_number == app_filter)
        return q.count()
    
    active_count = _build_count_query([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])
    completed_count = _build_count_query([AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS])
    
    # Global counts (unfiltered) to show when filters are applied
    has_filters = bool(model_filter or app_filter is not None or status_filter)
    global_active = None
    global_completed = None
    if has_filters:
        global_active = AnalysisTask.query.filter(
            AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])  # type: ignore[union-attr]
        ).count()
        global_completed = AnalysisTask.query.filter(
            AnalysisTask.status.in_([AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS])  # type: ignore[union-attr]
        ).count()

    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_tasks,
        'total_completed': completed_count,
        'active_count': active_count,
        'global_active': global_active,
        'global_completed': global_completed,
        'has_filters': has_filters,
        'has_prev': pagination_obj.has_prev if pagination_obj else False,
        'has_next': pagination_obj.has_next if pagination_obj else False,
        'prev_num': pagination_obj.prev_num if pagination_obj else None,
        'next_num': pagination_obj.next_num if pagination_obj else None,
        'pages': pagination_obj.pages if pagination_obj else 1
    }

    html = render_template(
        'pages/analysis/partials/_tasks_table.html',
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
        selected_tools = form.getlist('selected_tools[]')
        tool_config_raw = form.get('tool_config')
        priority = (form.get('priority') or 'normal').strip()
        
        # Container management options (all opt-in, disabled by default)
        container_auto_start = form.get('container_auto_start') == 'on'
        container_build_if_missing = form.get('container_build_if_missing') == 'on'
        container_stop_after = form.get('container_stop_after') == 'on'

        try:
            current_app.logger.debug(
                "analysis_create POST: model=%s app=%s selected_tools=%s",
                model_slug,
                app_number_raw,
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

        # Validation: at least one tool must be selected
        if not selected_tools:
            errors.append('At least one tool must be selected')

        if errors:
            for message in errors:
                flash(message, 'danger')
            return render_template('pages/analysis/analysis_create.html'), 400

        missing_targets: List[str] = []
        for mslug, anum in selection_pairs:
            exists = GeneratedApplication.query.filter_by(model_slug=mslug, app_number=anum).first()
            if not exists:
                missing_targets.append(f"{mslug}/app{anum}")
        if missing_targets:
            for target in missing_targets:
                flash(f"Application not found: {target}", 'danger')
            return render_template('pages/analysis/analysis_create.html'), 404

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
                    # Always use unified analysis with subtasks for consistent UI display
                    options['unified_analysis'] = True

                    # Always create main task with subtasks (even for single-service)
                    # This ensures consistent subtask display in the UI
                    task = AnalysisTaskService.create_main_task_with_subtasks(
                        model_slug=mslug,
                        app_number=anum,
                        tools=tool_names,
                        priority=priority_value,
                        custom_options=options,
                        task_name=f"custom:{mslug}:{anum}"
                    )
                    # Count subtasks from tools_by_service
                    subtask_total += len(tools_by_service_map)
                    created.append(task)
                return created, subtask_total

            created_tasks: List[AnalysisTask] = []
            total_subtasks = 0

            # Process selected tools
            canonical_selection, invalid_entries = canonicalize_inputs(selected_tools)
            if invalid_entries:
                for message in invalid_entries:
                    flash(message, 'danger')
                return render_template('pages/analysis/analysis_create.html'), 400

            if not canonical_selection:
                flash('No valid tools selected after validation.', 'danger')
                return render_template('pages/analysis/analysis_create.html'), 400

            tool_ids, tool_names, tool_display_names, tools_by_service = build_tool_payload(canonical_selection)
            if not tools_by_service:
                flash('No valid tools selected after validation.', 'danger')
                return render_template('pages/analysis/analysis_create.html'), 400

            try:
                current_app.logger.debug(
                    "analysis_create selection: services=%s tool_names=%s",
                    list(tools_by_service.keys()),
                    tool_names,
                )
            except Exception:
                pass

            # Parse tool configuration if present
            tool_config = {}
            if tool_config_raw:
                try:
                    tool_config = json.loads(tool_config_raw)
                except Exception as e:
                    current_app.logger.warning(f"Failed to parse tool_config: {e}")

            base_options: Dict[str, Any] = {
                'selected_tools': tool_ids,
                'selected_tool_names': tool_names,
                'selected_tool_display_names': tool_display_names,
                'tools_by_service': tools_by_service,
                'source': 'wizard_custom',
                'analysis_type': 'custom',
                'tool_config': tool_config,
                # Container management options
                'container_management': {
                    'start_before_analysis': container_auto_start,
                    'build_if_missing': container_build_if_missing,
                    'stop_after_analysis': container_stop_after,
                },
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
                return render_template('pages/analysis/analysis_create.html'), 500

            success_message = f"Launched {len(created_tasks)} analysis task(s)"
            if total_subtasks:
                success_message += f" across {total_subtasks} analyzer service runs"
            flash(success_message + '.', 'success')

        except Exception as exc:  # pragma: no cover - defensive logging
            current_app.logger.exception('analysis_create failed inside processing block')
            flash(f'Error creating analysis task: {exc}', 'danger')
            return render_template('pages/analysis/analysis_create.html'), 500

        return redirect(url_for('analysis.analysis_list'))

    return render_template('pages/analysis/analysis_create.html')


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
    return render_template('pages/analysis/partials/_model_grid_select.html', models=page_models, selectable=selectable, page=page, page_size=page_size, total=total, has_next=has_next)


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
    return render_template('pages/analysis/partials/_applications_select.html', applications=apps, model_slug=model_slug)


def _get_result_service() -> UnifiedResultService:
    """Return a cached UnifiedResultService instance for the current app."""
    if not hasattr(current_app, '_unified_result_service'):
        current_app._unified_result_service = UnifiedResultService()  # type: ignore[attr-defined]
    return current_app._unified_result_service  # type: ignore[attr-defined]


@analysis_bp.route('/results/<string:result_id>')
def analysis_result_detail(result_id: str):
    """Render the detail page for a stored analysis result (file or database)."""
    service = _get_result_service()
    findings_limit: Optional[int] = None
    limit_param = (request.args.get('findings') or '').strip()
    if limit_param.isdigit():
        findings_limit = max(1, min(int(limit_param), 1000))

    # Load results using UnifiedResultService (handles DB, Cache, Filesystem and Hydration)
    try:
        results = service.load_analysis_results(result_id)
        if not results:
            # Try to find task to give better error
            task = AnalysisTask.query.filter_by(task_id=result_id).first()
            if task:
                if task.status in [AnalysisStatus.PENDING, AnalysisStatus.RUNNING]:
                    return render_template('pages/errors/errors_main.html', 
                        error_code=202, 
                        error_message=f"Analysis is still in progress ({task.status.value}). Please wait."), 202
                elif task.status == AnalysisStatus.FAILED and not task.result_summary:
                     return render_template('pages/errors/errors_main.html', 
                        error_code=500, 
                        error_message=f"Analysis failed: {task.error_message or 'Unknown error'}"), 500
            
            abort(404, description=f"Result {result_id} not found")
            
        payload = results.raw_data
    except HTTPException:
        raise  # Let abort() propagate without catching
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Failed to load analysis result %s: %s", result_id, exc)
        abort(500, description="Unable to load analysis result")

    # Extract findings and services from structured results
    findings = results.security.get('findings', [])[:findings_limit] if findings_limit else results.security.get('findings', [])
    services = results.tools
    summary_block = results.summary
    metadata_block = payload.get('metadata', {})
    
    # Transform service names and structure for template compatibility
    # Mapping: static-analyzer → static, dynamic-analyzer → dynamic, etc.
    SERVICE_NAME_MAP = {
        'static-analyzer': 'static',
        'dynamic-analyzer': 'dynamic',
        'performance-tester': 'performance',
        'ai-analyzer': 'ai'
    }
    
    def transform_services(raw_services: dict) -> dict:
        """Transform service data to template-expected format.
        
        Wraps everything in DescriptorDict for Jinja2 attribute access compatibility.
        
        Handles two formats:
        1. New format (v3.0+): service_data.analysis.results
        2. Legacy format: service_data.payload.results
        """
        transformed = {}
        for full_name, service_data in raw_services.items():
            short_name = SERVICE_NAME_MAP.get(full_name, full_name)
            if isinstance(service_data, dict):
                # CRITICAL FIX: Handle nested structure variations
                # Format 1: service_data.analysis.results (direct)
                # Format 2: service_data.payload.analysis.results (nested from Celery tasks)
                # Format 3: service_data.payload.results (legacy)
                analysis_data = service_data.get('analysis', {})
                if not analysis_data:
                    payload = service_data.get('payload', {})
                    # Check if payload has nested 'analysis' key (Celery task format)
                    if isinstance(payload, dict) and 'analysis' in payload:
                        analysis_data = payload.get('analysis', {})
                    else:
                        analysis_data = payload
                
                # AI analyzer has different structure: tools instead of results
                if full_name == 'ai-analyzer':
                    transformed[short_name] = DescriptorDict({
                        'status': service_data.get('status', 'unknown'),
                        'service': full_name,
                        'analysis': DescriptorDict({
                            'tools': analysis_data.get('tools', {}),
                            'summary': analysis_data.get('summary', {}),
                            'metadata': analysis_data.get('metadata', {}),
                            'results': analysis_data.get('results', {})  # Legacy fallback
                        })
                    })
                else:
                    # Static/Dynamic/Performance: results structure
                    transformed[short_name] = DescriptorDict({
                        'status': service_data.get('status', 'unknown'),
                        'service': full_name,
                        'analysis': DescriptorDict({
                            'results': analysis_data.get('results', {}),
                            'tools_used': analysis_data.get('tools_used', []),
                            'tools': analysis_data.get('results', {})  # Alias for compatibility
                        })
                    })
        return DescriptorDict(transformed)
    
    transformed_services = transform_services(services) if services else {}
    
    # Build descriptor for filesystem results
    descriptor = DescriptorDict({
        'identifier': result_id,
        'task_id': result_id,
        'source': 'filesystem',
        'model_slug': getattr(results, 'model_slug', 'unknown'),
        'app_number': getattr(results, 'app_number', 0),
        'task_name': result_id[:16],
        'status': results.status or 'unknown',
        'tools_used': list(services.keys()) if services else [],
        'total_findings': summary_block.get('total_findings', 0),
        'severity_breakdown': summary_block.get('severity_breakdown', {}),
        'tools_executed': len(services) if services else 0,
        'tools_failed': 0,
        'modified_at': getattr(results, 'modified_at', None),
    })
    
    # Wrap payload in expected structure for template compatibility
    wrapped_payload = DescriptorDict({
        'results': DescriptorDict({
            'services': transformed_services,
            'summary': summary_block
        }),
        'task': payload.get('task', {}),
        'metadata': metadata_block
    })

    # --- Enhancement: Timing data from AnalysisTask ---
    timing_info: Dict[str, Any] = {}
    task_obj = AnalysisTask.query.filter_by(task_id=result_id).first()
    if task_obj:
        timing_info = {
            'actual_duration': task_obj.actual_duration,
            'queue_time': task_obj.queue_time,
            'started_at': task_obj.started_at,
            'completed_at': task_obj.completed_at,
            'created_at': task_obj.created_at,
        }
        # Enrich descriptor with DB fields when available
        if task_obj.target_model:
            descriptor['model_slug'] = task_obj.target_model
        if task_obj.target_app_number:
            descriptor['app_number'] = task_obj.target_app_number
        if task_obj.task_name:
            descriptor['task_name'] = task_obj.task_name

    # --- Enhancement: Prev/Next task navigation (same model + app) ---
    prev_task_id: Optional[str] = None
    next_task_id: Optional[str] = None
    model_slug = descriptor.get('model_slug')
    app_number = descriptor.get('app_number')
    if task_obj and model_slug and app_number:
        prev_row = (
            AnalysisTask.query
            .filter(
                AnalysisTask.target_model == model_slug,
                AnalysisTask.target_app_number == app_number,
                AnalysisTask.is_main_task.is_(True),
                AnalysisTask.created_at < task_obj.created_at,
                AnalysisTask.status.in_([AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]),
            )
            .order_by(AnalysisTask.created_at.desc())
            .with_entities(AnalysisTask.task_id)
            .first()
        )
        next_row = (
            AnalysisTask.query
            .filter(
                AnalysisTask.target_model == model_slug,
                AnalysisTask.target_app_number == app_number,
                AnalysisTask.is_main_task.is_(True),
                AnalysisTask.created_at > task_obj.created_at,
                AnalysisTask.status.in_([AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]),
            )
            .order_by(AnalysisTask.created_at.asc())
            .with_entities(AnalysisTask.task_id)
            .first()
        )
        if prev_row:
            prev_task_id = prev_row[0]
        if next_row:
            next_task_id = next_row[0]

    from app.routes.jinja.detail_context import build_analysis_result_context
    context = build_analysis_result_context(
        result_id=result_id,
        descriptor=descriptor,
        payload=wrapped_payload,
        services=transformed_services,
        summary=summary_block,
        metadata=metadata_block,
        timing_info=timing_info,
        findings=findings,
        findings_limit=findings_limit,
        prev_task_id=prev_task_id,
        next_task_id=next_task_id,
    )

    return render_template(
        'pages/analysis/analysis_result_detail.html',
        **context,
    )


def _build_analysis_section_context(result_id: str) -> dict:
    """Build the full context needed to render any analysis section partial.

    Re-uses the same loading & transformation logic from the main route.
    """
    service = _get_result_service()
    results = service.load_analysis_results(result_id)
    if not results:
        abort(404, description=f"Result {result_id} not found")

    payload = results.raw_data
    findings = results.security.get('findings', [])
    services_raw = results.tools
    summary_block = results.summary
    metadata_block = payload.get('metadata', {})

    SERVICE_NAME_MAP = {
        'static-analyzer': 'static',
        'dynamic-analyzer': 'dynamic',
        'performance-tester': 'performance',
        'ai-analyzer': 'ai',
    }

    def transform_services(raw_services: dict) -> dict:
        transformed = {}
        for full_name, service_data in raw_services.items():
            short_name = SERVICE_NAME_MAP.get(full_name, full_name)
            if isinstance(service_data, dict):
                analysis_data = service_data.get('analysis', {})
                if not analysis_data:
                    p = service_data.get('payload', {})
                    if isinstance(p, dict) and 'analysis' in p:
                        analysis_data = p.get('analysis', {})
                    else:
                        analysis_data = p
                if full_name == 'ai-analyzer':
                    transformed[short_name] = DescriptorDict({
                        'status': service_data.get('status', 'unknown'),
                        'service': full_name,
                        'analysis': DescriptorDict({
                            'tools': analysis_data.get('tools', {}),
                            'summary': analysis_data.get('summary', {}),
                            'metadata': analysis_data.get('metadata', {}),
                            'results': analysis_data.get('results', {}),
                        }),
                    })
                else:
                    transformed[short_name] = DescriptorDict({
                        'status': service_data.get('status', 'unknown'),
                        'service': full_name,
                        'analysis': DescriptorDict({
                            'results': analysis_data.get('results', {}),
                            'tools_used': analysis_data.get('tools_used', []),
                            'tools': analysis_data.get('results', {}),
                        }),
                    })
        return DescriptorDict(transformed)

    transformed_services = transform_services(services_raw) if services_raw else {}

    descriptor = DescriptorDict({
        'identifier': result_id,
        'task_id': result_id,
        'source': 'filesystem',
        'model_slug': getattr(results, 'model_slug', 'unknown'),
        'app_number': getattr(results, 'app_number', 0),
        'task_name': result_id[:16],
        'status': results.status or 'unknown',
        'tools_used': list(services_raw.keys()) if services_raw else [],
        'total_findings': summary_block.get('total_findings', 0),
        'severity_breakdown': summary_block.get('severity_breakdown', {}),
        'tools_executed': len(services_raw) if services_raw else 0,
        'tools_failed': 0,
        'modified_at': getattr(results, 'modified_at', None),
    })

    wrapped_payload = DescriptorDict({
        'results': DescriptorDict({
            'services': transformed_services,
            'summary': summary_block,
        }),
        'task': payload.get('task', {}),
        'metadata': metadata_block,
    })

    timing_info: dict = {}
    task_obj = AnalysisTask.query.filter_by(task_id=result_id).first()
    if task_obj:
        timing_info = {
            'actual_duration': task_obj.actual_duration,
            'queue_time': task_obj.queue_time,
            'started_at': task_obj.started_at,
            'completed_at': task_obj.completed_at,
            'created_at': task_obj.created_at,
        }
        if task_obj.target_model:
            descriptor['model_slug'] = task_obj.target_model
        if task_obj.target_app_number:
            descriptor['app_number'] = task_obj.target_app_number
        if task_obj.task_name:
            descriptor['task_name'] = task_obj.task_name

    return {
        'descriptor': descriptor,
        'payload': wrapped_payload,
        'findings': findings,
        'services': transformed_services,
        'summary': summary_block,
        'metadata': metadata_block,
        'timing_info': timing_info,
        'task_info': {'task_id': result_id, 'status': results.status},
        'result_id': result_id,
    }


@analysis_bp.route('/results/<string:result_id>/section/<string:section>')
def analysis_result_section(result_id: str, section: str):
    """HTMX endpoint to render a single analysis section partial."""
    try:
        ctx = _build_analysis_section_context(result_id)
        section_templates = {
            'summary': 'pages/analysis/partials/_section_summary.html',
            'static': 'pages/analysis/partials/_section_static.html',
            'dynamic': 'pages/analysis/partials/_section_dynamic.html',
            'performance': 'pages/analysis/partials/_section_performance.html',
            'ai': 'pages/analysis/partials/_section_ai.html',
            'metadata': 'pages/analysis/partials/_section_metadata.html',
        }
        template = section_templates.get(section)
        if not template:
            return f'<div class="alert alert-warning">Unknown section: {section}</div>', 404
        return render_template(template, **ctx)
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error rendering analysis section %s for %s: %s", section, result_id, exc, exc_info=True)
        return f'<div class="alert alert-danger">Failed to load {section}: {exc}</div>', 500


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
    """Send the stored JSON file for download (from file or database)."""
    # First try database (check both COMPLETED and FAILED status)
    task = AnalysisTask.query.filter_by(task_id=result_id).first()
    if task and task.result_summary and task.status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]:
        try:
            payload = task.get_result_summary()
            if payload:
                response = make_response(json.dumps(payload, indent=2, default=str))
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                response.headers['Content-Disposition'] = f'attachment; filename="{result_id}.json"'
                response.headers['X-Analysis-Result'] = result_id
                response.headers['X-Result-Source'] = 'database'
                return response
        except Exception as exc:
            current_app.logger.warning(f"Failed to export database results for {result_id}: {exc}")
    
    # Fallback to filesystem
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


@analysis_bp.route('/api/tasks/stop-all', methods=['POST'])
def stop_all_tasks():
    """Stop all pending and running tasks.
    
    Returns JSON with count of cancelled tasks.
    """
    try:
        # Get all active tasks (pending or running)
        active_tasks = AnalysisTask.query.filter(
            AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])  # type: ignore[union-attr]
        ).all()
        
        cancelled_count = 0
        failed_count = 0
        
        for task in active_tasks:
            try:
                result = AnalysisTaskService.cancel_task(task.task_id)
                if result:
                    cancelled_count += 1
                    current_app.logger.info(f"Cancelled task {task.task_id}")
                else:
                    failed_count += 1
            except Exception as e:
                current_app.logger.warning(f"Failed to cancel task {task.task_id}: {e}")
                failed_count += 1
        
        return jsonify({
            'success': True,
            'cancelled': cancelled_count,
            'failed': failed_count,
            'total': len(active_tasks),
            'message': f"Cancelled {cancelled_count} task(s)"
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error stopping all tasks: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to stop tasks'
        }), 500


@analysis_bp.route('/tasks/<string:task_id>/export/sarif')
def export_task_sarif(task_id: str):
    """Export analysis results in SARIF 2.1.0 format.

    Attempts to load pre-generated SARIF document from file system.
    If multiple SARIF files exist, returns a ZIP archive.
    """
    import zipfile
    import io

    service = _get_result_service()
    sarif_files = service.get_sarif_files(task_id)
        
    if not sarif_files:
        abort(404, description=f"No SARIF files found for task {task_id}")

    current_app.logger.info(f"Found {len(sarif_files)} SARIF files for task {task_id}")

    # If single file, return it directly
    if len(sarif_files) == 1:
        return send_file(
            sarif_files[0],
            mimetype='application/json',
            as_attachment=True,
            download_name=sarif_files[0].name,
        )
        
    # If multiple files, zip them
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for sarif_file in sarif_files:
            zf.write(sarif_file, arcname=sarif_file.name)
            
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{task_id}_sarif.zip"
    )
