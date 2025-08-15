"""
Simple Testing Results API - Works with actual model structure
"""

import json
from datetime import datetime, timedelta
from flask import request, jsonify, send_file
from sqlalchemy import func, desc
from app.extensions import db
from app.models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis, GeneratedApplication
import logging

from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/testing/results/enhanced')
def get_enhanced_results():
    """Get enhanced testing results with filtering and pagination."""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 25, type=int)
        analysis_type_filter = request.args.get('analysisType', '')
        date_filter = request.args.get('dateRange', 'all')
        status_filter = request.args.get('status', '')
        
        # For now, let's just return security analyses with their applications
        query = db.session.query(SecurityAnalysis).join(GeneratedApplication)
        
        # Apply status filter
        if status_filter:
            query = query.filter(SecurityAnalysis.status == status_filter)
        
        # Apply date filter
        if date_filter != 'all':
            date_cutoff = datetime.now()
            if date_filter == 'today':
                date_cutoff = date_cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_filter == 'week':
                date_cutoff = date_cutoff - timedelta(days=7)
            elif date_filter == 'month':
                date_cutoff = date_cutoff - timedelta(days=30)
            
            query = query.filter(SecurityAnalysis.created_at >= date_cutoff)
        
        # Order by created date descending
        query = query.order_by(desc(SecurityAnalysis.created_at))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        results = query.offset((page - 1) * page_size).limit(page_size).all()
        
        # Format results
        formatted_results = []
        for result in results:
            app = result.application  # This should work with the foreign key relationship
            
            formatted_result = {
                'id': result.id,
                'model_slug': app.model_slug if app else 'unknown',
                'app_number': app.app_number if app else 0,
                'analysis_type': 'security',
                'status': result.status.value if result.status else 'unknown',
                'score': getattr(result, 'overall_score', None) or 0,
                'duration': result.analysis_duration,
                'started_at': result.started_at.isoformat() if result.started_at else None,
                'completed_at': result.completed_at.isoformat() if result.completed_at else None,
                'task_id': getattr(result, 'task_id', None)
            }
            
            # Add basic results summary
            formatted_result['summary'] = {
                'total_findings': result.total_issues or 0,
                'high_severity': result.high_severity_count or 0,
                'medium_severity': result.medium_severity_count or 0,
                'low_severity': result.low_severity_count or 0
            }
            
            formatted_results.append(formatted_result)
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        
        return jsonify({
            'success': True,
            'results': formatted_results,
            'pagination': {
                'current_page': page,
                'per_page': page_size,
                'total': total_count,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting enhanced results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/testing/results/<int:result_id>/detail')
def get_result_detail(result_id):
    """Get detailed information for a specific result."""
    try:
        # Try to find the result in security analysis first
        result = SecurityAnalysis.query.get(result_id)
        analysis_type = 'security'
        
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404
        
        app = result.application
        
        # Format detailed result
        detailed_result = {
            'id': result.id,
            'model_slug': app.model_slug if app else 'unknown',
            'app_number': app.app_number if app else 0,
            'analysis_type': analysis_type,
            'status': result.status.value if result.status else 'unknown',
            'score': getattr(result, 'overall_score', None) or 0,
            'duration': result.analysis_duration,
            'started_at': result.created_at.isoformat() if result.created_at else None,
            'completed_at': result.completed_at.isoformat() if result.completed_at else None,
            'task_id': getattr(result, 'task_id', None),
            'config': result.get_global_config(),
            'results': result.get_results(),
            'version': 'N/A',
            'service': f'{analysis_type}_analyzer',
            'files_analyzed': 'N/A'
        }
        
        return jsonify({
            'success': True,
            'result': detailed_result
        })
        
    except Exception as e:
        logger.error(f"Error getting result detail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/testing/results/statistics')
def get_results_statistics():
    """Get overall testing statistics."""
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


# Simple endpoints for other functionality
@api_bp.route('/testing/results/<int:result_id>/download')
def download_result(result_id):
    """Download a specific result as JSON file."""
    try:
        result = SecurityAnalysis.query.get(result_id)
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404
        
        app = result.application
        
        result_data = {
            'id': result.id,
            'model_slug': app.model_slug if app else 'unknown',
            'app_number': app.app_number if app else 0,
            'analysis_type': 'security',
            'status': result.status.value if result.status else 'unknown',
            'results': result.get_results()
        }
        
        # Create temporary file
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(result_data, f, indent=2)
            temp_filename = f.name
        
        filename = f"analysis_result_security_{app.model_slug if app else 'unknown'}_app{app.app_number if app else 0}.json"
        
        return send_file(
            temp_filename,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error downloading result: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/testing/results/export')
def export_multiple_results():
    """Export multiple results as a ZIP file."""
    return jsonify({'success': False, 'error': 'Export functionality not implemented yet'}), 501


@api_bp.route('/testing/results/comparison')
def get_results_comparison():
    """Get comparison data for multiple results."""
    return jsonify({'success': False, 'error': 'Comparison functionality not implemented yet'}), 501


"""
Deprecated legacy

This module previously exposed /api/testing/results (simple) endpoints.
It is intentionally left empty. Deprecated legacy
"""

# No routes here.
