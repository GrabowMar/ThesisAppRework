"""
Statistics Routes
=================

Flask routes for displaying comprehensive statistics from AI model generation
and analysis operations. Provides insights into model performance, success rates,
and analysis results.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from flask import Blueprint, request, render_template, jsonify
from sqlalchemy import func, desc

from ..extensions import db
from ..models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis,
    PerformanceTest, ZAPAnalysis, OpenRouterAnalysis, BatchAnalysis
)
from ..constants import AnalysisStatus, JobStatus

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
stats_bp = Blueprint('statistics', __name__, url_prefix='/statistics')


@stats_bp.route('/')
def statistics_overview():
    """Main statistics dashboard."""
    try:
        # Calculate time ranges
        now = datetime.utcnow()
        last_30_days = now - timedelta(days=30)
        
        # Get basic model statistics
        total_models = db.session.query(ModelCapability).count()
        total_applications = db.session.query(GeneratedApplication).count()
        
        # Get provider distribution
        provider_stats = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()
        
        # Get generation statistics
        generation_stats = {
            'total_models': total_models,
            'total_applications': total_applications,
            'total_calls': total_applications,  # Assuming 1 call per app
            'success_rate': _calculate_success_rate(),
            'avg_generation_time': _calculate_avg_generation_time(),
            'successful_calls': _count_successful_generations()
        }
        
        # Get analysis statistics
        security_analyses = db.session.query(SecurityAnalysis).count()
        performance_tests = db.session.query(PerformanceTest).count()
        zap_analyses = db.session.query(ZAPAnalysis).count()
        ai_analyses = db.session.query(OpenRouterAnalysis).count()
        
        analysis_stats = {
            'total_security_analyses': security_analyses,
            'total_performance_tests': performance_tests,
            'total_zap_analyses': zap_analyses,
            'total_ai_analyses': ai_analyses,
            'total_analyses': security_analyses + performance_tests + zap_analyses + ai_analyses
        }
        
        # Get batch job statistics
        batch_stats = _get_batch_statistics()
        
        # Get recent activity (last 10 applications)
        recent_activity = db.session.query(GeneratedApplication).order_by(
            desc(GeneratedApplication.created_at)
        ).limit(10).all()
        
        # Get top performing models
        top_models = _get_top_performing_models()
        
        # Get daily statistics for the last 30 days
        daily_stats = _get_daily_statistics(last_30_days)
        
        # Get error analysis
        error_analysis = _get_error_analysis()
        
        return render_template('pages/statistics_overview.html',
                             stats=generation_stats,
                             analysis_stats=analysis_stats,
                             batch_stats=batch_stats,
                             provider_stats=dict(provider_stats),
                             recent_activity=recent_activity,
                             top_models=top_models,
                             daily_stats=daily_stats,
                             error_analysis=error_analysis)
    
    except Exception as e:
        logger.error(f"Error loading statistics overview: {e}")
        return render_template('pages/error.html', error=str(e))


@stats_bp.route('/api/models/distribution')
def api_models_distribution():
    """API endpoint for model distribution statistics."""
    try:
        # Provider distribution
        provider_dist = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()
        
        # Capability distribution
        capability_stats = {
            'function_calling': db.session.query(ModelCapability).filter(
                ModelCapability.supports_function_calling
            ).count(),
            'vision': db.session.query(ModelCapability).filter(
                ModelCapability.supports_vision
            ).count(),
            'streaming': db.session.query(ModelCapability).filter(
                ModelCapability.supports_streaming
            ).count(),
            'json_mode': db.session.query(ModelCapability).filter(
                ModelCapability.supports_json_mode
            ).count()
        }
        
        # Cost distribution
        cost_ranges = {
            'free': db.session.query(ModelCapability).filter(
                ModelCapability.is_free
            ).count(),
            'low_cost': db.session.query(ModelCapability).filter(
                ModelCapability.input_price_per_token <= 0.001
            ).count(),
            'medium_cost': db.session.query(ModelCapability).filter(
                ModelCapability.input_price_per_token.between(0.001, 0.01)
            ).count(),
            'high_cost': db.session.query(ModelCapability).filter(
                ModelCapability.input_price_per_token > 0.01
            ).count()
        }
        
        return jsonify({
            'provider_distribution': dict(provider_dist),
            'capability_distribution': capability_stats,
            'cost_distribution': cost_ranges
        })
    
    except Exception as e:
        logger.error(f"Error getting model distribution: {e}")
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/generation/trends')
def api_generation_trends():
    """API endpoint for generation trend statistics."""
    try:
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get daily generation counts
        daily_counts = db.session.query(
            func.date(GeneratedApplication.created_at).label('date'),
            func.count(GeneratedApplication.id).label('count')
        ).filter(
            GeneratedApplication.created_at >= start_date
        ).group_by(
            func.date(GeneratedApplication.created_at)
        ).order_by('date').all()
        
        # Get daily analysis counts
        daily_analyses = db.session.query(
            func.date(SecurityAnalysis.created_at).label('date'),
            func.count(SecurityAnalysis.id).label('security_count')
        ).filter(
            SecurityAnalysis.created_at >= start_date
        ).group_by(
            func.date(SecurityAnalysis.created_at)
        ).order_by('date').all()
        
        # Combine data
        trend_data = {}
        for date, count in daily_counts:
            trend_data[str(date)] = {'generations': count, 'analyses': 0}
        
        for date, count in daily_analyses:
            if str(date) in trend_data:
                trend_data[str(date)]['analyses'] = count
            else:
                trend_data[str(date)] = {'generations': 0, 'analyses': count}
        
        return jsonify(trend_data)
    
    except Exception as e:
        logger.error(f"Error getting generation trends: {e}")
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/analysis/summary')
def api_analysis_summary():
    """API endpoint for analysis summary statistics."""
    try:
        # Security analysis summary
        security_summary = db.session.query(
            func.avg(SecurityAnalysis.total_issues).label('avg_issues'),
            func.sum(SecurityAnalysis.critical_severity_count).label('total_critical'),
            func.sum(SecurityAnalysis.high_severity_count).label('total_high'),
            func.sum(SecurityAnalysis.medium_severity_count).label('total_medium'),
            func.sum(SecurityAnalysis.low_severity_count).label('total_low')
        ).filter(
            SecurityAnalysis.status == AnalysisStatus.COMPLETED
        ).first()
        
        # Performance test summary
        performance_summary = db.session.query(
            func.avg(PerformanceTest.requests_per_second).label('avg_rps'),
            func.avg(PerformanceTest.average_response_time).label('avg_response_time'),
            func.avg(PerformanceTest.error_rate).label('avg_error_rate')
        ).filter(
            PerformanceTest.status == AnalysisStatus.COMPLETED
        ).first()
        
        # ZAP analysis summary
        zap_summary = db.session.query(
            func.avg(ZAPAnalysis.high_risk_alerts).label('avg_high_risk'),
            func.avg(ZAPAnalysis.medium_risk_alerts).label('avg_medium_risk'),
            func.avg(ZAPAnalysis.low_risk_alerts).label('avg_low_risk')
        ).filter(
            ZAPAnalysis.status == AnalysisStatus.COMPLETED
        ).first()
        
        # AI analysis summary
        ai_summary = db.session.query(
            func.avg(OpenRouterAnalysis.overall_score).label('avg_overall_score'),
            func.avg(OpenRouterAnalysis.security_score).label('avg_security_score'),
            func.avg(OpenRouterAnalysis.code_quality_score).label('avg_quality_score'),
            func.sum(OpenRouterAnalysis.cost_usd).label('total_cost')
        ).filter(
            OpenRouterAnalysis.status == AnalysisStatus.COMPLETED
        ).first()
        
        return jsonify({
            'security': {
                'avg_issues': float(getattr(security_summary, 'avg_issues', 0) or 0),
                'total_critical': int(getattr(security_summary, 'total_critical', 0) or 0),
                'total_high': int(getattr(security_summary, 'total_high', 0) or 0),
                'total_medium': int(getattr(security_summary, 'total_medium', 0) or 0),
                'total_low': int(getattr(security_summary, 'total_low', 0) or 0)
            },
            'performance': {
                'avg_rps': float(getattr(performance_summary, 'avg_rps', 0) or 0),
                'avg_response_time': float(getattr(performance_summary, 'avg_response_time', 0) or 0),
                'avg_error_rate': float(getattr(performance_summary, 'avg_error_rate', 0) or 0)
            },
            'zap': {
                'avg_high_risk': float(getattr(zap_summary, 'avg_high_risk', 0) or 0),
                'avg_medium_risk': float(getattr(zap_summary, 'avg_medium_risk', 0) or 0),
                'avg_low_risk': float(getattr(zap_summary, 'avg_low_risk', 0) or 0)
            },
            'ai_analysis': {
                'avg_overall_score': float(getattr(ai_summary, 'avg_overall_score', 0) or 0),
                'avg_security_score': float(getattr(ai_summary, 'avg_security_score', 0) or 0),
                'avg_quality_score': float(getattr(ai_summary, 'avg_quality_score', 0) or 0),
                'total_cost': float(getattr(ai_summary, 'total_cost', 0) or 0)
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting analysis summary: {e}")
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/export')
def api_export_statistics():
    """API endpoint to export statistics data."""
    try:
        format_type = request.args.get('format', 'json')
        time_range = request.args.get('time_range', '30d')
        
        # Calculate date range
        if time_range == '7d':
            start_date = datetime.utcnow() - timedelta(days=7)
        elif time_range == '30d':
            start_date = datetime.utcnow() - timedelta(days=30)
        elif time_range == '90d':
            start_date = datetime.utcnow() - timedelta(days=90)
        else:
            start_date = datetime.utcnow() - timedelta(days=30)
        
        # Gather export data
        export_data = {
            'metadata': {
                'exported_at': datetime.utcnow().isoformat(),
                'time_range': time_range,
                'start_date': start_date.isoformat()
            },
            'models': _get_model_export_data(),
            'applications': _get_application_export_data(start_date),
            'analyses': _get_analysis_export_data(start_date),
            'batches': _get_batch_export_data(start_date)
        }
        
        if format_type == 'xlsx':
            # For now, return JSON even for XLSX requests
            # TODO: Implement actual XLSX export
            return jsonify(export_data)
        else:
            return jsonify(export_data)
    
    except Exception as e:
        logger.error(f"Error exporting statistics: {e}")
        return jsonify({'error': str(e)}), 500


def _calculate_success_rate() -> float:
    """Calculate overall generation success rate."""
    try:
        total = db.session.query(GeneratedApplication).count()
        if total == 0:
            return 0.0
        
        successful = db.session.query(GeneratedApplication).filter(
            GeneratedApplication.generation_status == AnalysisStatus.COMPLETED
        ).count()
        
        return (successful / total) * 100
    except Exception:
        return 0.0


def _calculate_avg_generation_time() -> str:
    """Calculate average generation time."""
    try:
        # Mock calculation - in real implementation, this would be based on actual timing data
        return "2.5m"
    except Exception:
        return "N/A"


def _count_successful_generations() -> int:
    """Count successful generations."""
    try:
        return db.session.query(GeneratedApplication).filter(
            GeneratedApplication.generation_status == AnalysisStatus.COMPLETED
        ).count()
    except Exception:
        return 0


def _get_batch_statistics() -> Dict[str, Any]:
    """Get batch job statistics."""
    try:
        total_batches = db.session.query(BatchAnalysis).count()
        completed_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status == JobStatus.COMPLETED
        ).count()
        failed_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status == JobStatus.FAILED
        ).count()
        
        return {
            'total_batches': total_batches,
            'completed_batches': completed_batches,
            'failed_batches': failed_batches,
            'success_rate': (completed_batches / max(total_batches, 1)) * 100
        }
    except Exception:
        return {'total_batches': 0, 'completed_batches': 0, 'failed_batches': 0, 'success_rate': 0}


def _get_top_performing_models() -> List[Dict[str, Any]]:
    """Get top performing models by generation count."""
    try:
        top_models = db.session.query(
            GeneratedApplication.model_slug,
            func.count(GeneratedApplication.id).label('app_count')
        ).group_by(
            GeneratedApplication.model_slug
        ).order_by(
            desc('app_count')
        ).limit(10).all()
        
        return [
            {
                'model_slug': model.model_slug,
                'app_count': model.app_count,
                'success_rate': 85.0  # Mock success rate for now
            }
            for model in top_models
        ]
    except Exception as e:
        logger.error(f"Error getting top models: {e}")
        return []


def _get_daily_statistics(start_date: datetime) -> List[Dict[str, Any]]:
    """Get daily statistics for charts."""
    try:
        daily_data = []
        current_date = start_date.date()
        end_date = datetime.utcnow().date()
        
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())
            
            # Count generations for this day
            generations = db.session.query(GeneratedApplication).filter(
                GeneratedApplication.created_at.between(day_start, day_end)
            ).count()
            
            # Count analyses for this day
            analyses = db.session.query(SecurityAnalysis).filter(
                SecurityAnalysis.created_at.between(day_start, day_end)
            ).count()
            
            daily_data.append({
                'date': current_date.isoformat(),
                'generations': generations,
                'analyses': analyses
            })
            
            current_date += timedelta(days=1)
        
        return daily_data
    except Exception as e:
        logger.error(f"Error getting daily statistics: {e}")
        return []


def _get_error_analysis() -> Dict[str, Any]:
    """Get error analysis data."""
    try:
        # Count failed generations
        failed_generations = db.session.query(GeneratedApplication).filter(
            GeneratedApplication.generation_status == AnalysisStatus.FAILED
        ).count()
        
        # Count failed analyses
        failed_security = db.session.query(SecurityAnalysis).filter(
            SecurityAnalysis.status == AnalysisStatus.FAILED
        ).count()
        
        failed_performance = db.session.query(PerformanceTest).filter(
            PerformanceTest.status == AnalysisStatus.FAILED
        ).count()
        
        return {
            'failed_generations': failed_generations,
            'failed_security_analyses': failed_security,
            'failed_performance_tests': failed_performance,
            'total_failures': failed_generations + failed_security + failed_performance
        }
    except Exception as e:
        logger.error(f"Error getting error analysis: {e}")
        return {'failed_generations': 0, 'failed_security_analyses': 0, 'failed_performance_tests': 0, 'total_failures': 0}


def _get_model_export_data() -> List[Dict[str, Any]]:
    """Get model data for export."""
    try:
        models = db.session.query(ModelCapability).all()
        return [model.to_dict() for model in models]
    except Exception:
        return []


def _get_application_export_data(start_date: datetime) -> List[Dict[str, Any]]:
    """Get application data for export."""
    try:
        apps = db.session.query(GeneratedApplication).filter(
            GeneratedApplication.created_at >= start_date
        ).all()
        return [app.to_dict() for app in apps]
    except Exception:
        return []


def _get_analysis_export_data(start_date: datetime) -> Dict[str, List[Dict[str, Any]]]:
    """Get analysis data for export."""
    try:
        security = db.session.query(SecurityAnalysis).filter(
            SecurityAnalysis.created_at >= start_date
        ).all()
        
        performance = db.session.query(PerformanceTest).filter(
            PerformanceTest.created_at >= start_date
        ).all()
        
        return {
            'security': [analysis.to_dict() for analysis in security],
            'performance': [test.to_dict() for test in performance]
        }
    except Exception:
        return {'security': [], 'performance': []}


def _get_batch_export_data(start_date: datetime) -> List[Dict[str, Any]]:
    """Get batch job data for export."""
    try:
        batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.created_at >= start_date
        ).all()
        return [batch.to_dict() for batch in batches]
    except Exception:
        return []
