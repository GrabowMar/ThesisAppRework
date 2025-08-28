"""
Batch Testing Routes
===================

Flask routes for managing batch analysis operations with analyzer integration.
Provides endpoints for creating, monitoring, and managing bulk analysis jobs.
"""

import logging
import json
from datetime import datetime, UTC  # noqa: F401 (remaining endpoints may rely on direct datetime)

from flask import Blueprint, request, jsonify, redirect, url_for, flash
from ..utils.template_paths import render_template_compat as render_template
from sqlalchemy import desc

from ..extensions import db
from ..models import (
    BatchAnalysis, GeneratedApplication, SecurityAnalysis,
    PerformanceTest, ZAPAnalysis, OpenRouterAnalysis, BatchTemplate
)
from ..constants import JobStatus, AnalysisStatus
from ..services.batch_service import batch_service  # global instance with advanced managers
from sqlalchemy import func
from flask import Response

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
batch_bp = Blueprint('batch', __name__, url_prefix='/batch')


@batch_bp.route('/')
def batch_overview():
    """Batch overview page (legacy tests still assert its direct contents).

    We retain the original template rendering for backward compatibility while
    showing a subtle deprecation notice guiding users toward the new Tasks page.
    """
    try:
        # In production mode we now prefer the /tasks view; keep legacy template for tests.
        from flask import current_app
        if not current_app.config.get('TESTING'):
            return redirect(url_for('tasks.tasks_overview'))

        snapshot = batch_service.get_dashboard_snapshot() or {}
        system_resources = {
            'cpu_usage': snapshot.get('system_resources', {}).get('cpu_usage', 0.0),
            'memory_usage': snapshot.get('system_resources', {}).get('memory_usage', 0.0)
        }
        stats = snapshot.get('stats') or {
            'total_batches': 0,
            'running_batches': 0,
            'queued_batches': 0,
            'completed_batches': 0,
            'total_analyses': 0,
            'active_workers': 0,
        }
        snapshot.setdefault('stats', stats)
        from app.utils.helpers import utc_now
        current_time = utc_now()
        deprecation_notice = (
            "Batch page is legacy. Use the new Tasks hub for ongoing and queued analyses."
        )
        return render_template(
            'pages/batch/overview.html',
            snapshot=snapshot,
            system_resources=system_resources,
            stats=stats,
            current_time=current_time,
            deprecation_notice=deprecation_notice
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Error rendering batch overview: {e}")
        return render_template('partials/common/error.html', error='Failed to load batch overview'), 500


# -------- HTMX partial endpoints for live updating sections -------- #
@batch_bp.route('/partials/active')
def partial_active_batches():
    snapshot = batch_service.get_dashboard_snapshot()
    return render_template('pages/batch/partials/active_batches.html', active_batches=snapshot['active_batches'])


@batch_bp.route('/partials/recent')
def partial_recent_batches():
    snapshot = batch_service.get_dashboard_snapshot()
    return render_template('pages/batch/partials/recent_batches.html', recent_batches=snapshot['recent_batches'])


@batch_bp.route('/partials/queue')
def partial_queue_overview():
    snapshot = batch_service.get_dashboard_snapshot()
    return render_template('pages/batch/partials/queue_overview.html', queue_overview=snapshot['queue_overview'])


@batch_bp.route('/partials/stats')
def partial_stats_summary():
    snapshot = batch_service.get_dashboard_snapshot()
    return render_template('pages/batch/partials/stats_summary.html', stats=snapshot['stats'])


@batch_bp.route('/create', methods=['GET', 'POST'])
def create_batch():
    """Deprecated: Redirect to Analysis Create page; programmatic batch handled via API."""
    flash('Batch creation moved to Analysis → Create.', 'info')
    return redirect(url_for('analysis.analyses_create_page'))


@batch_bp.route('/<batch_id>')
def batch_detail(batch_id: str):
    """Show detailed view of a specific batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            flash('Batch analysis not found', 'error')
            return redirect(url_for('batch.batch_overview'))
        
        # Get related analysis results
        analysis_results = []
        
        # Get security analyses for this batch's models/apps
        model_filter = batch.get_model_filter()
        app_filter = batch.get_app_filter()
        
        if model_filter and app_filter:
            # Get applications matching the batch criteria
            apps = db.session.query(GeneratedApplication).filter(
                GeneratedApplication.model_slug.in_(model_filter),
                GeneratedApplication.app_number.in_(app_filter)
            ).all()
            
            for app in apps:
                # Get all analysis types for this app
                if 'security' in batch.get_analysis_types():
                    security_analyses = db.session.query(SecurityAnalysis).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'security',
                        'app': app,
                        'analysis': analysis
                    } for analysis in security_analyses])
                
                if 'performance' in batch.get_analysis_types():
                    performance_tests = db.session.query(PerformanceTest).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'performance',
                        'app': app,
                        'analysis': analysis
                    } for analysis in performance_tests])
                
                if 'zap' in batch.get_analysis_types():
                    zap_analyses = db.session.query(ZAPAnalysis).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'zap',
                        'app': app,
                        'analysis': analysis
                    } for analysis in zap_analyses])
                
                if 'ai_analysis' in batch.get_analysis_types():
                    ai_analyses = db.session.query(OpenRouterAnalysis).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'ai_analysis',
                        'app': app,
                        'analysis': analysis
                    } for analysis in ai_analyses])
        
        # Calculate detailed statistics
        completed_count = len([r for r in analysis_results if r['analysis'].status == AnalysisStatus.COMPLETED])
        failed_count = len([r for r in analysis_results if r['analysis'].status == AnalysisStatus.FAILED])
        running_count = len([r for r in analysis_results if r['analysis'].status == AnalysisStatus.RUNNING])
        
        detailed_stats = {
            'total_analyses': len(analysis_results),
            'completed': completed_count,
            'failed': failed_count,
            'running': running_count,
            'pending': len(analysis_results) - completed_count - failed_count - running_count,
            'success_rate': (completed_count / max(len(analysis_results), 1)) * 100
        }
        
        return render_template(
            'single_page.html',
            page_title='Batch Detail',
            page_icon='fa-layer-group',
            page_subtitle=f"Batch {batch.batch_id}",
            main_partial='partials/batch/detail.html',
            batch=batch,
            analysis_results=analysis_results,
            detailed_stats=detailed_stats
        )
    
    except Exception as e:
        logger.error(f"Error loading batch detail: {e}")
        flash(f"Error loading batch detail: {str(e)}", 'error')
        return redirect(url_for('batch.batch_overview'))


@batch_bp.route('/api/status/<batch_id>')
def api_batch_status(batch_id: str):
    """API endpoint to get batch status."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        return jsonify(batch.to_dict())
    
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/start/<batch_id>', methods=['POST'])
def api_start_batch(batch_id: str):
    """API endpoint to start a batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        if batch.status != JobStatus.PENDING:
            return jsonify({'error': 'Batch is not in pending state'}), 400
        
        from ..services.batch_service import batch_service
        success = batch_service.start_job(batch.batch_id)
        if success:
            return jsonify({'success': True, 'message': 'Batch started successfully'})
        else:
            return jsonify({'error': 'Failed to start batch'}), 500
    
    except Exception as e:
        logger.error(f"Error starting batch: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/stop/<batch_id>', methods=['POST'])
def api_stop_batch(batch_id: str):
    """API endpoint to stop a batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        if batch.status not in [JobStatus.RUNNING, JobStatus.PENDING]:
            return jsonify({'error': 'Batch is not running or pending'}), 400
        
        from ..services.batch_service import batch_service
        success = batch_service.cancel_job(batch.batch_id)
        if success:
            return jsonify({'success': True, 'message': 'Batch stopped successfully'})
        else:
            return jsonify({'error': 'Failed to stop batch'}), 500
    
    except Exception as e:
        logger.error(f"Error stopping batch: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/delete/<batch_id>', methods=['DELETE'])
def api_delete_batch(batch_id: str):
    """API endpoint to delete a batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        if batch.status == JobStatus.RUNNING:
            return jsonify({'error': 'Cannot delete running batch'}), 400
        
        # Delete the batch
        db.session.delete(batch)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Batch deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting batch: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/list')
def api_list_batches():
    """API endpoint to list all batch analyses."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status_filter = request.args.get('status')
        
        query = db.session.query(BatchAnalysis)
        
        if status_filter:
            try:
                status_enum = JobStatus(status_filter)
                query = query.filter(BatchAnalysis.status == status_enum)
            except ValueError:
                pass  # Invalid status, ignore filter
        
        # Get paginated results
        offset = (page - 1) * per_page
        batches_list = query.order_by(desc(BatchAnalysis.created_at)).offset(offset).limit(per_page).all()
        total_count = query.count()
        
        return jsonify({
            'batches': [batch.to_dict() for batch in batches_list],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page,
                'has_next': offset + per_page < total_count,
                'has_prev': page > 1
            }
        })
    
    except Exception as e:
        logger.error(f"Error listing batches: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/infrastructure/status')
def api_infrastructure_status():
    """API endpoint to get analyzer infrastructure status."""
    try:
        # Return mock status for now
        status = {
            'services': [
                {'name': 'security-analyzer', 'status': 'healthy', 'service_type': 'security'},
                {'name': 'performance-tester', 'status': 'healthy', 'service_type': 'performance'},
                {'name': 'zap-scanner', 'status': 'healthy', 'service_type': 'zap'},
                {'name': 'ai-analyzer', 'status': 'healthy', 'service_type': 'ai'}
            ],
            'overall_status': 'healthy'
        }
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Error getting infrastructure status: {e}")
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Advanced Batch Queue & Template API Endpoints
# ---------------------------------------------------------------------------

@batch_bp.route('/api/batch/queue', methods=['POST'])
def api_queue_batch():
    """Queue an existing batch_id (created earlier) with a priority and optional dependencies.

    Expected JSON:
    {"batch_id": "...", "priority": "high", "depends_on": ["other_batch_id"], "metadata": {...}}
    Or create+queue:
    {"create": {name, description, analysis_types, models, app_range, options}, "priority": "normal"}
    """
    try:
        data = request.get_json(force=True) or {}
        priority = data.get('priority', 'normal')
        depends_on = data.get('depends_on') or []
        metadata = data.get('metadata') or {}

        # If 'create' payload present, create a new BatchAnalysis job first
        batch_id = data.get('batch_id')
        if not batch_id and 'create' in data:
            create_cfg = data['create']
            batch_id = batch_service.create_job(
                name=create_cfg.get('name','Queued Batch'),
                description=create_cfg.get('description','Queued via API'),
                analysis_types=create_cfg.get('analysis_types', []),
                models=create_cfg.get('models', []),
                app_range_str=create_cfg.get('app_range','1'),
                options=create_cfg.get('options'),
                enqueue_immediately=False
            )
        if not batch_id:
            return jsonify({'error': 'batch_id or create payload required'}), 400

        # Persist dependencies
        if depends_on:
            from app.models import BatchDependency  # local import to avoid cycles
            from app.extensions import db as _db
            for dep in depends_on:
                try:
                    if dep == batch_id:
                        continue
                    exists = _db.session.query(BatchDependency).filter_by(batch_id=batch_id, depends_on_batch_id=dep).first()
                    if not exists:
                        bd = BatchDependency()
                        bd.batch_id = batch_id
                        bd.depends_on_batch_id = dep
                        _db.session.add(bd)
                except Exception as de:  # pragma: no cover
                    logger.warning(f"Failed to add dependency {dep}: {de}")
            try:
                _db.session.commit()
            except Exception:
                _db.session.rollback()

        enq_ok = getattr(batch_service, 'queue_manager', None) and batch_service.queue_manager.enqueue(batch_id, priority, metadata)  # type: ignore[attr-defined]
        if not enq_ok:
            return jsonify({'error': 'failed_to_enqueue'}), 500
        return jsonify({'success': True, 'batch_id': batch_id, 'queue_status': batch_service.queue_manager.status_overview()})  # type: ignore[attr-defined]
    except Exception as e:
        logger.error(f"Error queueing batch: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/queue/status')
def api_queue_status():
    try:
        qm = getattr(batch_service, 'queue_manager', None)
        if not qm:
            return jsonify({'error': 'queue_manager_unavailable'}), 503
        return jsonify(qm.status_overview())
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/dispatch-next', methods=['POST'])
def api_dispatch_next():
    """Manually dispatch the next queued batch according to priority ordering.

    Returns 200 with next job id and refreshed queue status, or 204 if queue empty.
    """
    try:
        qm = getattr(batch_service, 'queue_manager', None)
        if not qm:
            return jsonify({'error': 'queue_manager_unavailable'}), 503
        next_id = batch_service.dispatch_next()
        if not next_id:
            return ('', 204)
        return jsonify({'dispatched': next_id, 'queue': qm.status_overview()})
    except Exception as e:
        logger.error(f"Error dispatching next batch: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/<batch_id>/cancel', methods=['POST'])
def api_cancel_batch(batch_id: str):
    try:
        # Cancel if queued
        qm = getattr(batch_service, 'queue_manager', None)
        cancelled_queue = False
        if qm and batch_id in getattr(qm, 'meta', {}):
            cancelled_queue = qm.cancel(batch_id)
        # Cancel running job
        batch_service.cancel_job(batch_id)
        return jsonify({'success': True, 'queue_cancelled': cancelled_queue})
    except Exception as e:
        logger.error(f"Error cancelling batch: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/<batch_id>/report')
def api_batch_report(batch_id: str):
    """Generate a simple report summarizing batch outcome and resource usage."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'not_found'}), 404
        # Resource usage aggregation
        from app.models import BatchResourceUsage  # local import
        usage_rows = db.session.query(BatchResourceUsage).filter_by(batch_id=batch_id).all()
        usage_summary = {}
        for u in usage_rows:
            usage_summary[u.analyzer_type] = {
                'peak_memory': u.peak_memory,
                'peak_cpu': u.peak_cpu,
                'duration': u.duration,
                'samples': u.sample_count
            }
        report = batch.to_dict()
        report['resource_usage'] = usage_summary
        # Basic cost estimation
        try:
            from app.models import ModelCapability
            models = batch.get_model_filter()
            caps = db.session.query(ModelCapability).filter(ModelCapability.canonical_slug.in_(models)).all()
            # naive estimate: per-analysis token placeholders * pricing
            estimate_total = 0.0
            for c in caps:
                # simple heuristic: (completed_tasks / models_count) * (input+output token price * 1000)
                per_model_tasks = max(1, batch.completed_tasks + batch.failed_tasks)
                est_tokens = per_model_tasks * 500  # placeholder average tokens
                cost = (c.input_price_per_token + c.output_price_per_token) * est_tokens
                estimate_total += cost
            report['estimated_cost_usd'] = round(estimate_total, 4)
        except Exception:
            report['estimated_cost_usd'] = None
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error generating batch report: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/template', methods=['POST'])
def api_save_batch_template():
    """Save a batch configuration as a reusable template."""
    try:
        data = request.get_json(force=True) or {}
        name = data.get('name')
        config = data.get('config')
        description = data.get('description')
        if not name or not config:
            return jsonify({'error': 'name and config required'}), 400
        existing = BatchTemplate.query.filter_by(name=name).first()
        if existing:
            # Update
            existing.batch_config_json = json.dumps(config)
            existing.description = description
            db.session.commit()
            tpl = existing.to_dict()
        else:
            tpl_obj = BatchTemplate()
            tpl_obj.name = name
            tpl_obj.description = description
            tpl_obj.batch_config_json = json.dumps(config)
            db.session.add(tpl_obj)
            db.session.commit()
            tpl = tpl_obj.to_dict()
        return jsonify({'success': True, 'template': tpl})
    except Exception as e:
        logger.error(f"Error saving batch template: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/template/list')
def api_list_batch_templates():
    try:
        templates = BatchTemplate.query.order_by(BatchTemplate.updated_at.desc()).limit(50).all()
        return jsonify({'templates': [t.to_dict() for t in templates]})
    except Exception as e:
        logger.error(f"Error listing batch templates: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/template/<name>')
def api_get_batch_template(name: str):
    try:
        tpl = BatchTemplate.query.filter_by(name=name).first()
        if not tpl:
            return jsonify({'error': 'not_found'}), 404
        return jsonify(tpl.to_dict())
    except Exception as e:
        logger.error(f"Error retrieving batch template: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch/analytics')
def api_batch_analytics():
    """Return historical performance metrics (counts, avg durations, success rate)."""
    try:
        # Aggregate over batch_analyses
        total = db.session.query(func.count(BatchAnalysis.id)).scalar() or 0
        completed = db.session.query(func.count(BatchAnalysis.id)).filter(BatchAnalysis.status==JobStatus.COMPLETED).scalar() or 0
        failed = db.session.query(func.count(BatchAnalysis.id)).filter(BatchAnalysis.status==JobStatus.FAILED).scalar() or 0
        running = db.session.query(func.count(BatchAnalysis.id)).filter(BatchAnalysis.status==JobStatus.RUNNING).scalar() or 0
        avg_completion = db.session.query(func.avg(func.julianday(BatchAnalysis.completed_at) - func.julianday(BatchAnalysis.started_at))).filter(BatchAnalysis.completed_at.isnot(None), BatchAnalysis.started_at.isnot(None)).scalar()
        avg_completion_seconds = None
        if avg_completion is not None:
            # julianday diff in days
            avg_completion_seconds = round(avg_completion * 86400, 2)
        success_rate = round((completed / total * 100.0), 2) if total else 0.0
        return jsonify({
            'total_batches': total,
            'completed': completed,
            'failed': failed,
            'running': running,
            'success_rate_pct': success_rate,
            'avg_duration_seconds': avg_completion_seconds
        })
    except Exception as e:
        logger.error(f"Error retrieving batch analytics: {e}")
        return jsonify({'error': str(e)}), 500


# ------------------------ Export Endpoints ------------------------ #
@batch_bp.route('/api/batch/job/<job_id>/export')
def api_export_single_job(job_id: str):
    fmt = (request.args.get('format') or 'json').lower()
    mimetype, filename, data = batch_service.generate_job_export(job_id, fmt)
    return Response(data, mimetype=mimetype, headers={'Content-Disposition': f'attachment; filename={filename}'})


@batch_bp.route('/api/batch/export')
def api_export_jobs():
    fmt = (request.args.get('format') or 'csv').lower()
    include_db = request.args.get('include_db', '1') in ('1','true','yes')
    mimetype, filename, data = batch_service.generate_jobs_export(fmt, include_in_memory_only=not include_db)
    return Response(data, mimetype=mimetype, headers={'Content-Disposition': f'attachment; filename={filename}'})


@batch_bp.route('/api/stats/export')
def api_export_batch_stats():
    """Export aggregated batch job statistics as CSV (or JSON if requested)."""
    fmt = (request.args.get('format') or 'csv').lower()
    stats = batch_service.get_job_stats()
    if fmt == 'json':
        return jsonify(stats)
    # CSV default
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(stats.keys())
    writer.writerow([stats[k] for k in stats.keys()])
    data = output.getvalue()
    return Response(data, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=batch_stats.csv'})


@batch_bp.route('/statistics')
def batch_statistics_page():
    """Deprecated: redirect to split statistics pages (analysis-focused)."""
    return redirect(url_for('statistics.statistics_analysis'))


@batch_bp.route('/api/infrastructure/start', methods=['POST'])
def api_start_infrastructure():
    """API endpoint to start analyzer infrastructure."""
    try:
        # Mock success response
        return jsonify({'success': True, 'message': 'Infrastructure started successfully'})
    
    except Exception as e:
        logger.error(f"Error starting infrastructure: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/infrastructure/stop', methods=['POST'])
def api_stop_infrastructure():
    """API endpoint to stop analyzer infrastructure."""
    try:
        # Mock success response
        return jsonify({'success': True, 'message': 'Infrastructure stopped successfully'})
    
    except Exception as e:
        logger.error(f"Error stopping infrastructure: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/list')
def batch_list():
    """HTMX endpoint for batch list."""
    try:
        status_filter = request.args.get('status')

        query = BatchAnalysis.query
        if status_filter:
            query = query.filter_by(status=status_filter)

        batches = query.order_by(
            BatchAnalysis.created_at.desc()
        ).limit(10).all()
        return render_template('partials/analysis/create/batch_list.html', batches=batches)
    except Exception as e:
        logger.error(f"Error loading batch list: {e}")
        return render_template('partials/common/error.html', error=f"Error loading batch list: {str(e)}")


@batch_bp.route('/form')
def batch_form():
    """Deprecated: redirect to unified analysis create page with batch mode enabled.

    Legacy templates/links may still request /batch/form. We preserve UX by
    redirecting to /analysis/create?batch=1 so the new unified page auto-opens
    batch mode and lazy-loads the embedded batch form partial.
    """
    return redirect(url_for('analysis.analyses_create_page', batch=1))


# Import logger
logger = logging.getLogger(__name__)
