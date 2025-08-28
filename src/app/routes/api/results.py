"""
Results API endpoints for enhanced results management
"""

from datetime import datetime, timedelta
from flask import request, jsonify
from sqlalchemy import func, desc
from app.extensions import db
from app.models import SecurityAnalysis, GeneratedApplication
import logging

from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/results')
def get_api_results():
    """Get results with filtering and pagination."""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        size = request.args.get('size', 25, type=int)
        sort = request.args.get('sort', 'timestamp:desc')
        status = request.args.get('status', '')
        model = request.args.get('model', '')
        date_range = request.args.get('dateRange', '')
        search = request.args.get('search', '')
        
        # Start with security analyses
        query = db.session.query(SecurityAnalysis).join(GeneratedApplication)
        
        # Apply filters
        if status:
            query = query.filter(SecurityAnalysis.status == status)
        
        if model:
            query = query.filter(GeneratedApplication.model_slug.ilike(f'%{model}%'))
        
        if search:
            query = query.filter(GeneratedApplication.model_slug.ilike(f'%{search}%'))
        
        # Apply date range filter
        if date_range:
            date_cutoff = datetime.now()
            if date_range == 'today':
                date_cutoff = date_cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_range == 'week':
                date_cutoff = date_cutoff - timedelta(days=7)
            elif date_range == 'month':
                date_cutoff = date_cutoff - timedelta(days=30)
            
            query = query.filter(SecurityAnalysis.created_at >= date_cutoff)
        
        # Apply sorting
        if sort == 'timestamp:desc':
            query = query.order_by(desc(SecurityAnalysis.created_at))
        elif sort == 'timestamp:asc':
            query = query.order_by(SecurityAnalysis.created_at)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        results = query.offset((page - 1) * size).limit(size).all()
        
        # Format results
        formatted_results = []
        for result in results:
            app = result.application
            
            formatted_result = {
                'id': result.id,
                'model_slug': app.model_slug if app else 'unknown',
                'app_number': app.app_number if app else 0,
                'analysis_type': 'security',
                'status': result.status.value if result.status else 'unknown',
                'score': getattr(result, 'overall_score', None) or 0,
                'duration': result.analysis_duration,
                'timestamp': result.created_at.isoformat() if result.created_at else None,
                'started_at': result.started_at.isoformat() if result.started_at else None,
                'completed_at': result.completed_at.isoformat() if result.completed_at else None,
                'task_id': getattr(result, 'task_id', None),
                'summary': {
                    'total_findings': result.total_issues or 0,
                    'high_severity': result.high_severity_count or 0,
                    'medium_severity': result.medium_severity_count or 0,
                    'low_severity': result.low_severity_count or 0
                }
            }
            
            formatted_results.append(formatted_result)
        
        # Calculate pagination info
        total_pages = (total_count + size - 1) // size
        
        return jsonify({
            'success': True,
            'results': formatted_results,
            'pagination': {
                'current_page': page,
                'per_page': size,
                'total': total_count,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/results/running')
def get_api_running_results():
    """Get currently running analysis results."""
    try:
        # Get running security analyses
        running_analyses = SecurityAnalysis.query.filter(
            SecurityAnalysis.status == 'running'
        ).join(GeneratedApplication).all()
        
        results = []
        for analysis in running_analyses:
            app = analysis.application
            results.append({
                'id': analysis.id,
                'model_slug': app.model_slug if app else 'unknown',
                'app_number': app.app_number if app else 0,
                'analysis_type': 'security',
                'status': 'running',
                'started_at': analysis.started_at.isoformat() if analysis.started_at else None,
                'task_id': getattr(analysis, 'task_id', None),
                'progress': getattr(analysis, 'progress_percentage', 0)
            })
        
        return jsonify({
            'success': True,
            'running_analyses': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Error getting running results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/results/statistics')
def get_api_results_statistics():
    """Get overall results statistics."""
    try:
        # Get counts by status for security analyses
        security_stats = db.session.query(
            SecurityAnalysis.status,
            func.count(SecurityAnalysis.id)
        ).group_by(SecurityAnalysis.status).all()
        
        # Calculate average duration
        avg_security_duration = db.session.query(func.avg(SecurityAnalysis.analysis_duration)).scalar() or 0
        
        # Get recent activity (last 7 days)
        since_week = datetime.now() - timedelta(days=7)
        recent_security = SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= since_week).count()
        
        statistics = {
            'by_type': {
                'security': {
                    'total': sum(count for status, count in security_stats),
                    'by_status': {status.value if status else 'unknown': count for status, count in security_stats},
                    'avg_duration': round(avg_security_duration, 2),
                    'recent_week': recent_security
                }
            },
            'overall': {
                'total_tests': sum(count for status, count in security_stats),
                'recent_week_total': recent_security,
                'overall_avg_duration': round(avg_security_duration, 2)
            }
        }
        
        return jsonify({
            'success': True,
            'statistics': statistics
        })
        
    except Exception as e:
        logger.error(f"Error getting results statistics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/results/cards')
def get_api_results_cards():
    """Get results in card format for dashboard."""
    try:
        # Get query parameters
        limit = request.args.get('limit', 6, type=int)
        type_filter = request.args.get('type', '')
        
        # Get recent analyses
        query = db.session.query(SecurityAnalysis).join(GeneratedApplication)
        
        if type_filter:
            # For now only security type is supported
            pass
        
        results = query.order_by(desc(SecurityAnalysis.created_at)).limit(limit).all()
        
        cards = []
        for result in results:
            app = result.application
            cards.append({
                'id': result.id,
                'title': f'{app.model_slug if app else "unknown"} - App {app.app_number if app else 0}',
                'type': 'security',
                'status': result.status.value if result.status else 'unknown',
                'timestamp': result.created_at.isoformat() if result.created_at else None,
                'score': getattr(result, 'overall_score', None) or 0,
                'summary': {
                    'total_findings': result.total_issues or 0,
                    'high_severity': result.high_severity_count or 0
                }
            })
        
        return jsonify({
            'success': True,
            'cards': cards
        })
        
    except Exception as e:
        logger.error(f"Error getting results cards: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/results/timeline')
def get_api_results_timeline():
    """Get results timeline data."""
    try:
        # Get analyses from last 30 days
        since_month = datetime.now() - timedelta(days=30)
        
        analyses = SecurityAnalysis.query.filter(
            SecurityAnalysis.created_at >= since_month
        ).join(GeneratedApplication).order_by(SecurityAnalysis.created_at).all()
        
        timeline_data = []
        for analysis in analyses:
            app = analysis.application
            timeline_data.append({
                'date': analysis.created_at.strftime('%Y-%m-%d') if analysis.created_at else None,
                'time': analysis.created_at.strftime('%H:%M') if analysis.created_at else None,
                'model': app.model_slug if app else 'unknown',
                'app_number': app.app_number if app else 0,
                'type': 'security',
                'status': analysis.status.value if analysis.status else 'unknown',
                'score': getattr(analysis, 'overall_score', None) or 0
            })
        
        return jsonify({
            'success': True,
            'timeline': timeline_data
        })
        
    except Exception as e:
        logger.error(f"Error getting results timeline: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/results/<int:result_id>')
def get_api_result_detail(result_id):
    """Get detailed information for a specific result."""
    try:
        # Try to find the result in security analysis
        from app.extensions import get_session
        with get_session() as _s:
            result = _s.get(SecurityAnalysis, result_id)
        
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404
        
        app = result.application
        
        # Format detailed result
        detailed_result = {
            'id': result.id,
            'model_slug': app.model_slug if app else 'unknown',
            'app_number': app.app_number if app else 0,
            'analysis_type': 'security',
            'status': result.status.value if result.status else 'unknown',
            'score': getattr(result, 'overall_score', None) or 0,
            'duration': result.analysis_duration,
            'started_at': result.created_at.isoformat() if result.created_at else None,
            'completed_at': result.completed_at.isoformat() if result.completed_at else None,
            'task_id': getattr(result, 'task_id', None),
            'config': result.get_global_config(),
            'results': result.get_results(),
            'version': 'N/A',
            'service': 'security_analyzer',
            'files_analyzed': 'N/A'
        }
        
        return jsonify({
            'success': True,
            'result': detailed_result
        })
        
    except Exception as e:
        logger.error(f"Error getting result detail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/results/<int:result_id>/export')
def export_api_result(result_id):
    """Export a specific result."""
    try:
        from app.extensions import get_session
        with get_session() as _s:
            result = _s.get(SecurityAnalysis, result_id)
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404
        
        app = result.application
        
        export_data = {
            'id': result.id,
            'model_slug': app.model_slug if app else 'unknown',
            'app_number': app.app_number if app else 0,
            'analysis_type': 'security',
            'status': result.status.value if result.status else 'unknown',
            'results': result.get_results(),
            'exported_at': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': export_data
        })
        
    except Exception as e:
        logger.error(f"Error exporting result: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
