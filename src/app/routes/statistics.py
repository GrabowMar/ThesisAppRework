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
        last_7_days = now - timedelta(days=7)
        
        # Get basic model statistics
        total_models = db.session.query(ModelCapability).count()
        total_applications = db.session.query(GeneratedApplication).count()
        
        # Get provider distribution
        provider_stats = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()
        
        # Get advanced model statistics
        model_stats = _get_comprehensive_model_stats()
        
        # Get generation statistics with enhanced metrics
        generation_stats = {
            'total_models': total_models,
            'total_applications': total_applications,
            'total_calls': total_applications,  # Assuming 1 call per app
            'success_rate': _calculate_success_rate(),
            'avg_generation_time': _calculate_avg_generation_time(),
            'successful_calls': _count_successful_generations(),
            'recent_generations_7d': _count_recent_generations(last_7_days),
            'recent_generations_30d': _count_recent_generations(last_30_days),
            'avg_apps_per_model': total_applications / max(total_models, 1),
            'total_providers': len(provider_stats)
        }
        
        # Get comprehensive analysis statistics
        security_analyses = db.session.query(SecurityAnalysis).count()
        performance_tests = db.session.query(PerformanceTest).count()
        zap_analyses = db.session.query(ZAPAnalysis).count()
        ai_analyses = db.session.query(OpenRouterAnalysis).count()
        
        analysis_stats = {
            'total_security_analyses': security_analyses,
            'total_performance_tests': performance_tests,
            'total_zap_analyses': zap_analyses,
            'total_ai_analyses': ai_analyses,
            'total_analyses': security_analyses + performance_tests + zap_analyses + ai_analyses,
            'avg_security_issues': _get_avg_security_issues(),
            'avg_performance_score': _get_avg_performance_score(),
            'critical_vulnerabilities': _get_critical_vulnerabilities_count(),
            'high_performance_apps': _get_high_performance_apps_count()
        }
        
        # Get batch job statistics
        batch_stats = _get_batch_statistics()
        
        # Get recent activity (last 15 applications for more data)
        recent_activity = db.session.query(GeneratedApplication).order_by(
            desc(GeneratedApplication.created_at)
        ).limit(15).all()
        
        # Get top performing models with enhanced metrics
        top_models = _get_top_performing_models()
        
        # Get daily statistics for the last 30 days
        daily_stats = _get_daily_statistics(last_30_days)
        
        # Get error analysis with more detail
        error_analysis = _get_error_analysis()
        
        # Get capability distribution
        capability_stats = _get_capability_distribution()
        
        # Get cost analysis
        cost_analysis = _get_cost_analysis()
        
        # Get framework distribution
        framework_stats = _get_framework_distribution()
        
        # Get analysis trends
        analysis_trends = _get_analysis_trends()
        
        # Load external data from misc folder
        external_data = _load_external_statistics()
        
        return render_template('pages/statistics_overview.html',
                             stats=generation_stats,
                             analysis_stats=analysis_stats,
                             batch_stats=batch_stats,
                             provider_stats=dict(provider_stats),
                             recent_activity=recent_activity,
                             top_models=top_models,
                             daily_stats=daily_stats,
                             error_analysis=error_analysis,
                             model_stats=model_stats,
                             capability_stats=capability_stats,
                             cost_analysis=cost_analysis,
                             framework_stats=framework_stats,
                             analysis_trends=analysis_trends,
                             external_data=external_data)
    
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
    """API endpoint for generation trend statistics with external data."""
    try:
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get database data
        daily_counts = db.session.query(
            func.date(GeneratedApplication.created_at).label('date'),
            func.count(GeneratedApplication.id).label('count')
        ).filter(
            GeneratedApplication.created_at >= start_date
        ).group_by(
            func.date(GeneratedApplication.created_at)
        ).order_by('date').all()
        
        daily_analyses = db.session.query(
            func.date(SecurityAnalysis.created_at).label('date'),
            func.count(SecurityAnalysis.id).label('security_count')
        ).filter(
            SecurityAnalysis.created_at >= start_date
        ).group_by(
            func.date(SecurityAnalysis.created_at)
        ).order_by('date').all()
        
        # Load external data from misc folder
        external_data = _load_external_generation_data()
        
        # Combine database data
        trend_data = {}
        for date, count in daily_counts:
            trend_data[str(date)] = {'generations': count, 'analyses': 0}
        
        for date, count in daily_analyses:
            if str(date) in trend_data:
                trend_data[str(date)]['analyses'] = count
            else:
                trend_data[str(date)] = {'generations': 0, 'analyses': count}
        
        # If no recent data, provide sample data based on external files
        if not trend_data and external_data:
            # Generate sample daily data for the requested period
            for i in range(days):
                sample_date = (datetime.utcnow() - timedelta(days=days-i)).date()
                sample_generations = max(0, int(external_data.get('total_apps', 750) / days) + 
                                      (i % 7) * 2 - 1)  # Vary by day
                sample_analyses = max(0, sample_generations // 3 + (i % 5))
                trend_data[str(sample_date)] = {
                    'generations': sample_generations,
                    'analyses': sample_analyses
                }
        
        return jsonify(trend_data)
    
    except Exception as e:
        logger.error(f"Error getting generation trends: {e}")
        return jsonify({'error': str(e)}), 500


def _load_external_generation_data() -> Dict[str, Any]:
    """Load generation data from misc folder files."""
    try:
        import json
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent.parent
        misc_path = project_root / "misc"
        
        external_data = {}
        
        # Load models summary
        models_summary_path = misc_path / "models_summary.json"
        if models_summary_path.exists():
            with open(models_summary_path, 'r') as f:
                summary_data = json.load(f)
                external_data.update({
                    'total_models': summary_data.get('total_models', 0),
                    'apps_per_model': summary_data.get('apps_per_model', 0),
                    'total_apps': summary_data.get('total_models', 0) * summary_data.get('apps_per_model', 0),
                    'extraction_date': summary_data.get('extraction_timestamp', '')
                })
        
        # Count actual generated apps in models folder
        models_path = misc_path / "models"
        if models_path.exists():
            actual_apps = 0
            model_count = 0
            for model_dir in models_path.iterdir():
                if model_dir.is_dir() and not model_dir.name.startswith('_'):
                    model_count += 1
                    for app_dir in model_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            actual_apps += 1
            
            external_data.update({
                'actual_models': model_count,
                'actual_apps': actual_apps
            })
        
        # Load conversation metadata if available
        conversations_path = misc_path / "generated_conversations"
        if conversations_path.exists():
            conversation_files = list(conversations_path.glob("*.json"))
            external_data['conversation_files'] = len(conversation_files)
        
        return external_data
    except Exception as e:
        logger.error(f"Error loading external generation data: {e}")
        return {}


@stats_bp.route('/api/external/statistics')
def api_external_statistics():
    """API endpoint for external generation statistics from misc folder."""
    try:
        import json
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent.parent
        misc_path = project_root / "misc"
        
        result = {
            'models_summary': {},
            'generation_stats': {},
            'filesystem_stats': {},
            'conversation_stats': {}
        }
        
        # Load models summary
        models_summary_path = misc_path / "models_summary.json"
        if models_summary_path.exists():
            with open(models_summary_path, 'r') as f:
                summary_data = json.load(f)
                result['models_summary'] = {
                    'total_models': summary_data.get('total_models', 0),
                    'apps_per_model': summary_data.get('apps_per_model', 0),
                    'extraction_timestamp': summary_data.get('extraction_timestamp', ''),
                    'providers': list(set(model.get('provider', 'unknown') 
                                        for model in summary_data.get('models', [])))
                }
        
        # Count filesystem stats
        models_path = misc_path / "models"
        if models_path.exists():
            actual_models = 0
            actual_apps = 0
            provider_breakdown = {}
            
            for model_dir in models_path.iterdir():
                if model_dir.is_dir() and not model_dir.name.startswith('_'):
                    actual_models += 1
                    provider = model_dir.name.split('_')[0] if '_' in model_dir.name else 'unknown'
                    provider_breakdown[provider] = provider_breakdown.get(provider, 0) + 1
                    
                    # Count apps in this model
                    model_apps = 0
                    for app_dir in model_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            model_apps += 1
                            actual_apps += 1
                    
            result['filesystem_stats'] = {
                'actual_models': actual_models,
                'actual_apps': actual_apps,
                'avg_apps_per_model': round(actual_apps / actual_models, 2) if actual_models > 0 else 0,
                'provider_breakdown': provider_breakdown
            }
        
        # Conversation files stats
        conversations_path = misc_path / "generated_conversations"
        if conversations_path.exists():
            conversation_files = list(conversations_path.glob("*.json"))
            result['conversation_stats'] = {
                'total_conversation_files': len(conversation_files),
                'conversation_folders': len([d for d in conversations_path.iterdir() if d.is_dir()])
            }
        
        # Calculate generation efficiency
        if result['models_summary'] and result['filesystem_stats']:
            expected_apps = (result['models_summary'].get('total_models', 0) * 
                           result['models_summary'].get('apps_per_model', 0))
            actual_apps = result['filesystem_stats'].get('actual_apps', 0)
            
            result['generation_stats'] = {
                'expected_total_apps': expected_apps,
                'actual_total_apps': actual_apps,
                'completion_rate': round((actual_apps / expected_apps) * 100, 2) if expected_apps > 0 else 0,
                'missing_apps': max(0, expected_apps - actual_apps)
            }
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error getting external statistics: {e}")
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


def _get_comprehensive_model_stats() -> Dict[str, Any]:
    """Get comprehensive model statistics."""
    try:
        # Model capability breakdown
        function_calling_models = db.session.query(ModelCapability).filter(
            ModelCapability.supports_function_calling.is_(True)
        ).count()
        
        vision_models = db.session.query(ModelCapability).filter(
            ModelCapability.supports_vision.is_(True)
        ).count()
        
        streaming_models = db.session.query(ModelCapability).filter(
            ModelCapability.supports_streaming.is_(True)
        ).count()
        
        json_mode_models = db.session.query(ModelCapability).filter(
            ModelCapability.supports_json_mode.is_(True)
        ).count()
        
        free_models = db.session.query(ModelCapability).filter(
            ModelCapability.is_free.is_(True)
        ).count()
        
        # Context window statistics
        avg_context_window = db.session.query(
            func.avg(ModelCapability.context_window)
        ).scalar() or 0
        
        max_context_window = db.session.query(
            func.max(ModelCapability.context_window)
        ).scalar() or 0
        
        return {
            'function_calling_models': function_calling_models,
            'vision_models': vision_models,
            'streaming_models': streaming_models,
            'json_mode_models': json_mode_models,
            'free_models': free_models,
            'avg_context_window': int(avg_context_window),
            'max_context_window': int(max_context_window)
        }
    except Exception as e:
        logger.error(f"Error getting comprehensive model stats: {e}")
        return {
            'function_calling_models': 0, 'vision_models': 0, 'streaming_models': 0,
            'json_mode_models': 0, 'free_models': 0, 'avg_context_window': 0, 'max_context_window': 0
        }


def _count_recent_generations(start_date: datetime) -> int:
    """Count generations since start_date."""
    try:
        return db.session.query(GeneratedApplication).filter(
            GeneratedApplication.created_at >= start_date
        ).count()
    except Exception:
        return 0


def _get_avg_security_issues() -> float:
    """Get average security issues per analysis."""
    try:
        avg_issues = db.session.query(
            func.avg(SecurityAnalysis.total_issues)
        ).filter(
            SecurityAnalysis.total_issues.isnot(None)
        ).scalar()
        return float(avg_issues) if avg_issues else 0.0
    except Exception:
        return 0.0


def _get_avg_performance_score() -> float:
    """Get average performance score."""
    try:
        avg_rps = db.session.query(
            func.avg(PerformanceTest.requests_per_second)
        ).filter(
            PerformanceTest.requests_per_second.isnot(None)
        ).scalar()
        return float(avg_rps) if avg_rps else 0.0
    except Exception:
        return 0.0


def _get_critical_vulnerabilities_count() -> int:
    """Get total critical vulnerabilities found."""
    try:
        critical_count = db.session.query(
            func.sum(SecurityAnalysis.critical_severity_count)
        ).scalar()
        return int(critical_count) if critical_count else 0
    except Exception:
        return 0


def _get_high_performance_apps_count() -> int:
    """Get count of high-performance applications (>100 RPS)."""
    try:
        return db.session.query(PerformanceTest).filter(
            PerformanceTest.requests_per_second > 100
        ).count()
    except Exception:
        return 0


def _get_capability_distribution() -> Dict[str, Any]:
    """Get distribution of model capabilities."""
    try:
        total_models = db.session.query(ModelCapability).count()
        if total_models == 0:
            return {
                'function_calling': 0,
                'vision': 0,
                'streaming': 0,
                'json_mode': 0,
                'function_calling_percentage': 0,
                'vision_percentage': 0,
                'streaming_percentage': 0,
                'json_mode_percentage': 0
            }
        
        # Get counts for each capability
        function_calling = db.session.query(ModelCapability).filter(
            ModelCapability.supports_function_calling.is_(True)
        ).count()
        
        vision = db.session.query(ModelCapability).filter(
            ModelCapability.supports_vision.is_(True)
        ).count()
        
        streaming = db.session.query(ModelCapability).filter(
            ModelCapability.supports_streaming.is_(True)
        ).count()
        
        json_mode = db.session.query(ModelCapability).filter(
            ModelCapability.supports_json_mode.is_(True)
        ).count()
        
        # Build result dictionary with percentages
        result = {
            'function_calling': function_calling,
            'vision': vision,
            'streaming': streaming,
            'json_mode': json_mode,
            'function_calling_percentage': round((function_calling / total_models) * 100, 2),
            'vision_percentage': round((vision / total_models) * 100, 2),
            'streaming_percentage': round((streaming / total_models) * 100, 2),
            'json_mode_percentage': round((json_mode / total_models) * 100, 2)
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting capability distribution: {e}")
        return {
            'function_calling': 0,
            'vision': 0,
            'streaming': 0,
            'json_mode': 0,
            'function_calling_percentage': 0,
            'vision_percentage': 0,
            'streaming_percentage': 0,
            'json_mode_percentage': 0
        }


def _get_cost_analysis() -> Dict[str, Any]:
    """Get cost analysis data."""
    try:
        # Cost ranges
        free_models = db.session.query(ModelCapability).filter(
            ModelCapability.is_free.is_(True)
        ).count()
        
        low_cost = db.session.query(ModelCapability).filter(
            ModelCapability.input_price_per_token <= 0.001,
            ModelCapability.is_free.is_(False)
        ).count()
        
        medium_cost = db.session.query(ModelCapability).filter(
            ModelCapability.input_price_per_token.between(0.001, 0.01)
        ).count()
        
        high_cost = db.session.query(ModelCapability).filter(
            ModelCapability.input_price_per_token > 0.01
        ).count()
        
        # Average costs
        avg_input_cost = db.session.query(
            func.avg(ModelCapability.input_price_per_token)
        ).filter(
            ModelCapability.input_price_per_token.isnot(None),
            ModelCapability.is_free.is_(False)
        ).scalar()
        
        avg_output_cost = db.session.query(
            func.avg(ModelCapability.output_price_per_token)
        ).filter(
            ModelCapability.output_price_per_token.isnot(None),
            ModelCapability.is_free.is_(False)
        ).scalar()
        
        return {
            'free_models': free_models,
            'low_cost_models': low_cost,
            'medium_cost_models': medium_cost,
            'high_cost_models': high_cost,
            'avg_input_cost': float(avg_input_cost) if avg_input_cost else 0.0,
            'avg_output_cost': float(avg_output_cost) if avg_output_cost else 0.0
        }
    except Exception as e:
        logger.error(f"Error getting cost analysis: {e}")
        return {
            'free_models': 0, 'low_cost_models': 0, 'medium_cost_models': 0,
            'high_cost_models': 0, 'avg_input_cost': 0.0, 'avg_output_cost': 0.0
        }


def _get_framework_distribution() -> Dict[str, Any]:
    """Get framework distribution from generated applications."""
    try:
        # Backend frameworks
        backend_frameworks = db.session.query(
            GeneratedApplication.backend_framework,
            func.count(GeneratedApplication.id).label('count')
        ).filter(
            GeneratedApplication.backend_framework.isnot(None)
        ).group_by(GeneratedApplication.backend_framework).all()
        
        # Frontend frameworks
        frontend_frameworks = db.session.query(
            GeneratedApplication.frontend_framework,
            func.count(GeneratedApplication.id).label('count')
        ).filter(
            GeneratedApplication.frontend_framework.isnot(None)
        ).group_by(GeneratedApplication.frontend_framework).all()
        
        return {
            'backend_frameworks': dict(backend_frameworks),
            'frontend_frameworks': dict(frontend_frameworks)
        }
    except Exception as e:
        logger.error(f"Error getting framework distribution: {e}")
        return {'backend_frameworks': {}, 'frontend_frameworks': {}}


def _get_analysis_trends() -> Dict[str, Any]:
    """Get analysis trends over time."""
    try:
        last_30_days = datetime.utcnow() - timedelta(days=30)
        
        # Weekly trend
        weekly_security = db.session.query(
            func.count(SecurityAnalysis.id)
        ).filter(
            SecurityAnalysis.created_at >= datetime.utcnow() - timedelta(days=7)
        ).scalar() or 0
        
        weekly_performance = db.session.query(
            func.count(PerformanceTest.id)
        ).filter(
            PerformanceTest.created_at >= datetime.utcnow() - timedelta(days=7)
        ).scalar() or 0
        
        # Monthly trend
        monthly_security = db.session.query(
            func.count(SecurityAnalysis.id)
        ).filter(
            SecurityAnalysis.created_at >= last_30_days
        ).scalar() or 0
        
        monthly_performance = db.session.query(
            func.count(PerformanceTest.id)
        ).filter(
            PerformanceTest.created_at >= last_30_days
        ).scalar() or 0
        
        return {
            'weekly_security_analyses': weekly_security,
            'weekly_performance_tests': weekly_performance,
            'monthly_security_analyses': monthly_security,
            'monthly_performance_tests': monthly_performance
        }
    except Exception as e:
        logger.error(f"Error getting analysis trends: {e}")
        return {
            'weekly_security_analyses': 0, 'weekly_performance_tests': 0,
            'monthly_security_analyses': 0, 'monthly_performance_tests': 0
        }


def _get_provider_distribution() -> Dict[str, int]:
    """Get distribution of providers from models."""
    try:
        # Get from database if available
        provider_counts = {}
        models = db.session.query(ModelCapability.provider).distinct().all()
        
        for (provider,) in models:
            if provider:
                count = db.session.query(ModelCapability).filter(
                    ModelCapability.provider == provider
                ).count()
                provider_counts[provider] = count
        
        # If no database data, use external data
        if not provider_counts:
            external_data = _load_external_statistics()
            if external_data.get('filesystem_stats', {}).get('provider_breakdown'):
                provider_counts = external_data['filesystem_stats']['provider_breakdown']
        
        return provider_counts
    except Exception as e:
        logger.error(f"Error getting provider distribution: {e}")
        return {}


def _load_external_statistics() -> Dict[str, Any]:
    """Load statistics from external JSON files in misc folder."""
    try:
        import json
        from pathlib import Path
        
        # Get the project root
        project_root = Path(__file__).parent.parent.parent.parent
        misc_path = project_root / "misc"
        
        external_data = {}
        
        # Load model capabilities summary
        model_capabilities_path = misc_path / "model_capabilities.json"
        if model_capabilities_path.exists():
            with open(model_capabilities_path, 'r') as f:
                capabilities_data = json.load(f)
                external_data['model_capabilities'] = capabilities_data.get('capabilities_summary', {})
        
        # Load models summary
        models_summary_path = misc_path / "models_summary.json"
        if models_summary_path.exists():
            with open(models_summary_path, 'r') as f:
                summary_data = json.load(f)
                external_data['models_summary'] = {
                    'total_models': summary_data.get('total_models', 0),
                    'apps_per_model': summary_data.get('apps_per_model', 0),
                    'extraction_timestamp': summary_data.get('extraction_timestamp', '')
                }
        
        # Count generated applications in misc/models folder
        models_path = misc_path / "models"
        if models_path.exists():
            generated_apps_count = 0
            model_folders = 0
            for model_dir in models_path.iterdir():
                if model_dir.is_dir() and not model_dir.name.startswith('_'):
                    model_folders += 1
                    for app_dir in model_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            generated_apps_count += 1
            
            external_data['filesystem_stats'] = {
                'model_folders': model_folders,
                'generated_apps': generated_apps_count
            }
        
        return external_data
    except Exception as e:
        logger.error(f"Error loading external statistics: {e}")
        return {}
