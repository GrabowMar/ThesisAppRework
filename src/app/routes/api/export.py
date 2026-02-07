"""
Export API Routes
=================
Unified export service for all tables in the application.
Supports JSON and CSV formats with filtering.
"""

from flask import Blueprint, request, jsonify, make_response, current_app
from sqlalchemy import select, func
from datetime import datetime
import csv
import io

from app.models import ModelCapability, GeneratedApplication, AnalysisTask, db

export_bp = Blueprint('export', __name__, url_prefix='/api/export')


# Helper to safely get model fields
def safe_get_field(obj, field_name, default=None):
    """Safely get attribute from object"""
    return getattr(obj, field_name, default)


@export_bp.route('/models', methods=['GET'])
def export_models():
    """Export models table with optional filtering"""
    try:
        format_type = request.args.get('format', 'json').lower()
        
        # Build query with filters
        query = select(ModelCapability)
        
        # Apply filters
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
        
        # Execute query
        models = db.session.execute(query).scalars().all()
        
        # Prepare data
        data = []
        for model in models:
            data.append({
                'slug': model.canonical_slug,
                'model_id': model.model_id,
                'name': model.model_name,
                'provider': model.provider,
                'input_price': model.input_price_per_token,
                'output_price': model.output_price_per_token,
                'context_window': model.context_window,
                'installed': model.installed,
                'is_free': model.is_free,
                'created_at': model.created_at.isoformat() if model.created_at else None
            })
        
        # Return in requested format
        if format_type == 'csv':
            return _generate_csv_response(data, 'models')
        elif format_type == 'excel':
            return _generate_excel_response(data, 'models')
        else:
            return jsonify({
                'success': True,
                'data': data,
                'count': len(data),
                'exported_at': datetime.utcnow().isoformat()
            })
    
    except Exception as e:
        current_app.logger.error(f'Export models error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@export_bp.route('/applications', methods=['GET'])
def export_applications():
    """Export applications table with optional filtering"""
    try:
        format_type = request.args.get('format', 'json').lower()
        
        # Build query with filters
        query = select(GeneratedApplication)
        
        # Apply filters
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
        
        # Execute query
        applications = db.session.execute(query).scalars().all()
        
        # Prepare data
        data = []
        for app in applications:
            data.append({
                'model_slug': app.model_slug,
                'app_number': app.app_number,
                'app_type': safe_get_field(app, 'app_type', 'unknown'),
                'status': safe_get_field(app, 'container_status', 'unknown'),
                'created_at': app.created_at.isoformat() if app.created_at else None
            })
        
        # Return in requested format
        if format_type == 'csv':
            return _generate_csv_response(data, 'applications')
        elif format_type == 'excel':
            return _generate_excel_response(data, 'applications')
        else:
            return jsonify({
                'success': True,
                'data': data,
                'count': len(data),
                'exported_at': datetime.utcnow().isoformat()
            })
    
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
