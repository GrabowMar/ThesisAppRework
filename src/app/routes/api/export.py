"""
Export API Routes
=================
Unified export service for all tables in the application.
Full JSON exports with all database fields and nested relations.
"""

from flask import Blueprint, request, jsonify, make_response, current_app
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, defer
from datetime import datetime
import csv
import io
import json
import enum

from app.models import (
    ModelCapability, GeneratedApplication, AnalysisTask,
    ModelBenchmarkCache, db
)

export_bp = Blueprint('export', __name__, url_prefix='/api/export')


def _serialize_model(obj, skip_columns: set[str] | None = None) -> dict:
    """Generic SQLAlchemy model to dict converter.

    Always iterates over table columns to handle deferred columns safely.
    Handles enums (.value), datetimes (.isoformat()), and JSON text columns.
    """
    skip = skip_columns or set()
    result = {}
    for col in obj.__class__.__table__.columns:
        if col.name in skip:
            continue
        val = getattr(obj, col.name, None)
        if val is None:
            result[col.name] = None
        elif isinstance(val, enum.Enum):
            result[col.name] = val.value
        elif isinstance(val, datetime):
            result[col.name] = val.isoformat()
        elif isinstance(val, str) and col.name.endswith('_json'):
            try:
                result[col.name] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                result[col.name] = val
        else:
            result[col.name] = val
    return result


@export_bp.route('/models', methods=['GET'])
def export_models():
    """Export models table with all fields and nested benchmarks."""
    try:
        # Build query with filters
        query = select(ModelCapability)

        if provider := request.args.get('provider'):
            query = query.where(ModelCapability.provider == provider)

        if search := request.args.get('search'):
            search_term = f'%{search}%'
            query = query.where(
                (ModelCapability.model_name.ilike(search_term)) |
                (ModelCapability.model_id.ilike(search_term)) |
                (ModelCapability.canonical_slug.ilike(search_term))
            )

        if installed := request.args.get('installed'):
            query = query.where(ModelCapability.installed == (installed.lower() == 'true'))

        models = db.session.execute(query).scalars().all()

        # Pre-fetch all benchmarks in one query, keyed by model_id
        model_ids = [m.model_id for m in models]
        benchmarks_map: dict[str, dict] = {}
        if model_ids:
            benchmarks = db.session.execute(
                select(ModelBenchmarkCache).where(
                    ModelBenchmarkCache.model_id.in_(model_ids)
                )
            ).scalars().all()
            for b in benchmarks:
                benchmarks_map[b.model_id] = _serialize_model(b)

        data = []
        for model in models:
            row = _serialize_model(model)
            row['benchmarks'] = benchmarks_map.get(model.model_id)
            data.append(row)

        resp = make_response(json.dumps({
            'success': True,
            'data': data,
            'count': len(data),
            'exported_at': datetime.utcnow().isoformat()
        }, default=str, indent=2))
        resp.headers['Content-Type'] = 'application/json'
        resp.headers['Content-Disposition'] = (
            f'attachment; filename=models_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        return resp

    except Exception as e:
        current_app.logger.error(f'Export models error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@export_bp.route('/applications', methods=['GET'])
def export_applications():
    """Export applications table with all fields and nested analysis data."""
    try:
        # Build query with eager loading of relationships
        query = (
            select(GeneratedApplication)
            .options(
                selectinload(GeneratedApplication.security_analyses),
                selectinload(GeneratedApplication.performance_tests),
                selectinload(GeneratedApplication.zap_analyses),
                selectinload(GeneratedApplication.openrouter_analyses),
            )
        )

        if model_slug := request.args.get('model'):
            query = query.where(GeneratedApplication.model_slug == model_slug)

        if status := request.args.get('status'):
            query = query.where(GeneratedApplication.container_status == status)  # type: ignore[arg-type]

        if app_type := request.args.get('type'):
            query = query.where(GeneratedApplication.app_type == app_type)

        if search := request.args.get('search'):
            search_term = f'%{search}%'
            query = query.where(
                (GeneratedApplication.model_slug.ilike(search_term)) |
                (GeneratedApplication.app_type.ilike(search_term))
            )

        applications = db.session.execute(query).scalars().all()

        # Pre-fetch all analysis tasks with results in batch
        tasks_map: dict[tuple[str, int], list[dict]] = {}

        if applications:
            # Use OR conditions instead of tuple IN (SQLite compatible)
            # Defer result_summary (can be ~1GB total) to keep export fast;
            # full task data available via /api/export/analysis
            target_models = {app.model_slug for app in applications}
            task_query = (
                select(AnalysisTask)
                .options(
                    selectinload(AnalysisTask.results),
                    defer(AnalysisTask.result_summary),
                )
                .where(AnalysisTask.target_model.in_(list(target_models)))
            )
            tasks = db.session.execute(task_query).scalars().all()
            # Filter to only matching (model, app_number) pairs
            app_keys = {(app.model_slug, app.app_number) for app in applications}
            # Skip result_summary (deferred) to avoid N+1 lazy loads
            task_skip = {'result_summary'}
            for task in tasks:
                key = (task.target_model, task.target_app_number)
                if key in app_keys:
                    task_dict = _serialize_model(task, skip_columns=task_skip)
                    task_dict['results'] = [_serialize_model(r) for r in task.results]
                    tasks_map.setdefault(key, []).append(task_dict)

        data = []
        for app in applications:
            row = _serialize_model(app)
            row['security_analyses'] = [_serialize_model(sa) for sa in app.security_analyses]
            row['performance_tests'] = [_serialize_model(pt) for pt in app.performance_tests]
            row['zap_analyses'] = [_serialize_model(za) for za in app.zap_analyses]
            row['openrouter_analyses'] = [_serialize_model(oa) for oa in app.openrouter_analyses]
            row['analysis_tasks'] = tasks_map.get((app.model_slug, app.app_number), [])
            data.append(row)

        resp = make_response(json.dumps({
            'success': True,
            'data': data,
            'count': len(data),
            'exported_at': datetime.utcnow().isoformat()
        }, default=str, indent=2))
        resp.headers['Content-Type'] = 'application/json'
        resp.headers['Content-Disposition'] = (
            f'attachment; filename=applications_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        return resp

    except Exception as e:
        current_app.logger.error(f'Export applications error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@export_bp.route('/analysis', methods=['GET'])
def export_analysis():
    """Export analysis tasks with optional filtering"""
    try:
        format_type = request.args.get('format', 'json').lower()

        # Build query with filters
        query = select(AnalysisTask)

        # Apply filters (simplified - task model fields may vary)
        if task_id := request.args.get('task_id'):
            query = query.where(AnalysisTask.task_id == task_id)

        # Execute query
        tasks = db.session.execute(query).scalars().all()

        # Prepare data
        data = []
        for task in tasks:
            data.append({
                'task_id': task.task_id,
                'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None
            })

        # Return in requested format
        if format_type == 'csv':
            return _generate_csv_response(data, 'analysis')
        elif format_type == 'excel':
            return _generate_excel_response(data, 'analysis')
        else:
            return jsonify({
                'success': True,
                'data': data,
                'count': len(data),
                'exported_at': datetime.utcnow().isoformat()
            })

    except Exception as e:
        current_app.logger.error(f'Export analysis error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@export_bp.route('/statistics', methods=['GET'])
def export_statistics():
    """Export aggregated statistics"""
    try:
        format_type = request.args.get('format', 'json').lower()
        stat_type = request.args.get('stat_type', 'summary')

        data = []

        if stat_type == 'summary':
            # Overall summary statistics
            total_models = db.session.execute(select(func.count(ModelCapability.id))).scalar()
            total_apps = db.session.execute(select(func.count(GeneratedApplication.id))).scalar()
            total_tasks = db.session.execute(select(func.count(AnalysisTask.id))).scalar()

            data = [{
                'metric': 'Total Models',
                'value': total_models or 0,
                'category': 'models'
            }, {
                'metric': 'Total Applications',
                'value': total_apps or 0,
                'category': 'applications'
            }, {
                'metric': 'Total Analysis Tasks',
                'value': total_tasks or 0,
                'category': 'analysis'
            }]

        elif stat_type == 'models_by_provider':
            # Models grouped by provider
            result = db.session.execute(
                select(ModelCapability.provider, func.count(ModelCapability.id).label('count'))
                .group_by(ModelCapability.provider)
            ).all()

            data = [{'provider': r.provider, 'count': r.count} for r in result]

        elif stat_type == 'apps_by_model':
            # Applications grouped by model
            result = db.session.execute(
                select(GeneratedApplication.model_slug, func.count(GeneratedApplication.id).label('count'))
                .group_by(GeneratedApplication.model_slug)
            ).all()

            data = [{'model': r.model_slug, 'count': r.count} for r in result]

        # Return in requested format
        if format_type == 'csv':
            return _generate_csv_response(data, f'statistics_{stat_type}')
        elif format_type == 'excel':
            return _generate_excel_response(data, f'statistics_{stat_type}')
        else:
            return jsonify({
                'success': True,
                'data': data,
                'count': len(data),
                'stat_type': stat_type,
                'exported_at': datetime.utcnow().isoformat()
            })

    except Exception as e:
        current_app.logger.error(f'Export statistics error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# Helper Functions
# ========================================

def _generate_csv_response(data, filename):
    """Generate CSV response from data"""
    if not data:
        return jsonify({'success': False, 'error': 'No data to export'}), 400

    # Create CSV in memory
    si = io.StringIO()
    writer = csv.DictWriter(si, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)

    # Create response
    output = si.getvalue()
    si.close()

    response = make_response(output)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

    return response


def _generate_excel_response(data, filename):
    """Generate Excel response from data - Currently falls back to CSV"""
    # Excel export requires additional dependencies (openpyxl, pandas)
    # For now, fallback to CSV
    current_app.logger.info('Excel export requested, falling back to CSV')
    return _generate_csv_response(data, filename)
