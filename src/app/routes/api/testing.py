"""
Testing dashboard API endpoints
"""

from datetime import datetime, timedelta
from flask import request, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models import SecurityAnalysis, GeneratedApplication
import logging

from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/testing/dashboard/stats')
def get_testing_dashboard_stats():
    """Get testing dashboard statistics."""
    try:
        # Get basic counts
        total_analyses = SecurityAnalysis.query.count()
        running_analyses = SecurityAnalysis.query.filter(SecurityAnalysis.status == 'running').count()
        completed_analyses = SecurityAnalysis.query.filter(SecurityAnalysis.status == 'completed').count()
        failed_analyses = SecurityAnalysis.query.filter(SecurityAnalysis.status == 'failed').count()
        
        # Get recent activity (last 24 hours)
        since_day = datetime.now() - timedelta(days=1)
        recent_analyses = SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= since_day).count()
        
        # Get average duration
        avg_duration = db.session.query(func.avg(SecurityAnalysis.analysis_duration)).scalar() or 0
        
        # Get success rate
        success_rate = (completed_analyses / total_analyses * 100) if total_analyses > 0 else 0
        
        stats = {
            'total_analyses': total_analyses,
            'running_analyses': running_analyses,
            'completed_analyses': completed_analyses,
            'failed_analyses': failed_analyses,
            'recent_analyses_24h': recent_analyses,
            'average_duration': round(avg_duration, 2),
            'success_rate': round(success_rate, 1),
            'system_status': 'operational',
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting testing dashboard stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/testing/analyzer/status')
def get_testing_analyzer_status():
    """Get analyzer service status."""
    try:
        # Since we're using mock services, return a simulated status
        status = {
            'services': {
                'security_analyzer': {
                    'status': 'running',
                    'version': '1.0.0',
                    'last_health_check': datetime.now().isoformat(),
                    'active_analyses': SecurityAnalysis.query.filter(SecurityAnalysis.status == 'running').count()
                },
                'performance_analyzer': {
                    'status': 'running',
                    'version': '1.0.0',
                    'last_health_check': datetime.now().isoformat(),
                    'active_analyses': 0
                },
                'static_analyzer': {
                    'status': 'running',
                    'version': '1.0.0',
                    'last_health_check': datetime.now().isoformat(),
                    'active_analyses': 0
                }
            },
            'overall_status': 'healthy',
            'mock_mode': True,
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting analyzer status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/testing/system/events')
def get_testing_system_events():
    """Get recent system events."""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        # Get recent analyses as system events
        recent_analyses = SecurityAnalysis.query.join(GeneratedApplication).order_by(
            SecurityAnalysis.created_at.desc()
        ).limit(limit).all()
        
        events = []
        for analysis in recent_analyses:
            app = analysis.application
            event = {
                'id': analysis.id,
                'timestamp': analysis.created_at.isoformat() if analysis.created_at else None,
                'type': 'analysis',
                'level': 'info',
                'message': f"Security analysis for {app.model_slug if app else 'unknown'} app {app.app_number if app else 0}",
                'status': analysis.status.value if analysis.status else 'unknown',
                'details': {
                    'analysis_type': 'security',
                    'model_slug': app.model_slug if app else 'unknown',
                    'app_number': app.app_number if app else 0
                }
            }
            events.append(event)
        
        return jsonify({
            'success': True,
            'events': events,
            'count': len(events)
        })
        
    except Exception as e:
        logger.error(f"Error getting system events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/testing/performance/metrics')
def get_testing_performance_metrics():
    """Get performance metrics for testing dashboard."""
    try:
        # Calculate performance metrics from security analyses
        analyses = SecurityAnalysis.query.all()
        
        if not analyses:
            return jsonify({
                'success': True,
                'metrics': {
                    'avg_analysis_time': 0,
                    'throughput_per_hour': 0,
                    'success_rate': 0,
                    'error_rate': 0,
                    'queue_length': 0,
                    'active_workers': 1
                }
            })
        
        # Calculate metrics
        durations = [a.analysis_duration for a in analyses if a.analysis_duration]
        avg_time = sum(durations) / len(durations) if durations else 0
        
        completed_count = len([a for a in analyses if a.status and a.status.value == 'completed'])
        failed_count = len([a for a in analyses if a.status and a.status.value == 'failed'])
        total_count = len(analyses)
        
        success_rate = (completed_count / total_count * 100) if total_count > 0 else 0
        error_rate = (failed_count / total_count * 100) if total_count > 0 else 0
        
        # Recent throughput (last 24 hours)
        since_day = datetime.now() - timedelta(days=1)
        recent_analyses = SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= since_day).count()
        
        metrics = {
            'avg_analysis_time': round(avg_time, 2),
            'throughput_per_hour': round(recent_analyses / 24, 2),
            'success_rate': round(success_rate, 1),
            'error_rate': round(error_rate, 1),
            'queue_length': SecurityAnalysis.query.filter(SecurityAnalysis.status == 'pending').count(),
            'active_workers': 1,
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'metrics': metrics
        })
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
