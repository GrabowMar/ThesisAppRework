"""Analysis results & reports routes."""
from pathlib import Path
from datetime import datetime
from flask import Blueprint, send_file, abort
from ..utils.template_paths import render_template_compat as render_template
from ..constants import Paths
from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis
from ..extensions import get_session

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def _gather_file_reports(limit: int | None = None):
    """Get generated file reports for download."""
    reports_dir = Paths.REPORTS_DIR
    if not reports_dir.exists():
        return []
    files = []
    for p in sorted(reports_dir.glob('*'), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        stat = p.stat()
        files.append({
            'name': p.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'ext': p.suffix.lower().lstrip('.'),
        })
        if limit and len(files) >= limit:
            break
    return files


def _get_recent_analyses(limit: int = 20):
    """Get recent completed analyses across all types."""
    analyses = []
    
    with get_session() as session:
        # Get recent security analyses
        security_analyses = session.query(SecurityAnalysis).filter(
            SecurityAnalysis.status.in_(['completed', 'failed'])
        ).order_by(SecurityAnalysis.created_at.desc()).limit(limit).all()
        
        for analysis in security_analyses:
            analyses.append({
                'id': analysis.id,
                'type': 'security',
                'model_slug': analysis.application.model_slug if analysis.application else 'Unknown',
                'app_number': analysis.application.app_number if analysis.application else 0,
                'status': analysis.status,
                'created_at': analysis.created_at,
                'completed_at': analysis.completed_at,
                'has_results': bool(analysis.results_json),
                'results_summary': _get_security_summary(analysis) if analysis.status == 'completed' else None
            })
        
        # Get recent performance tests
        performance_tests = session.query(PerformanceTest).filter(
            PerformanceTest.status.in_(['completed', 'failed'])
        ).order_by(PerformanceTest.created_at.desc()).limit(limit).all()
        
        for test in performance_tests:
            analyses.append({
                'id': test.id,
                'type': 'performance',
                'model_slug': test.application.model_slug if test.application else 'Unknown',
                'app_number': test.application.app_number if test.application else 0,
                'status': test.status,
                'created_at': test.created_at,
                'completed_at': test.completed_at,
                'has_results': bool(test.results_json),
                'results_summary': _get_performance_summary(test) if test.status == 'completed' else None
            })
        
        # Get recent ZAP analyses
        zap_analyses = session.query(ZAPAnalysis).filter(
            ZAPAnalysis.status.in_(['completed', 'failed'])
        ).order_by(ZAPAnalysis.created_at.desc()).limit(limit).all()
        
        for zap in zap_analyses:
            analyses.append({
                'id': zap.id,
                'type': 'zap',
                'model_slug': zap.application.model_slug if zap.application else 'Unknown',
                'app_number': zap.application.app_number if zap.application else 0,
                'status': zap.status,
                'created_at': zap.created_at,
                'completed_at': zap.completed_at,
                'has_results': bool(zap.zap_report_json),
                'results_summary': _get_zap_summary(zap) if zap.status == 'completed' else None
            })
        
        # Get recent AI analyses
        ai_analyses = session.query(OpenRouterAnalysis).filter(
            OpenRouterAnalysis.status.in_(['completed', 'failed'])
        ).order_by(OpenRouterAnalysis.created_at.desc()).limit(limit).all()
        
        for ai in ai_analyses:
            analyses.append({
                'id': ai.id,
                'type': 'ai',
                'model_slug': ai.application.model_slug if ai.application else 'Unknown',
                'app_number': ai.application.app_number if ai.application else 0,
                'status': ai.status,
                'created_at': ai.created_at,
                'completed_at': ai.completed_at,
                'has_results': bool(getattr(ai, 'results_json', None)),
                'results_summary': None  # TODO: Add AI results summary
            })
    
    # Sort all analyses by creation date
    analyses.sort(key=lambda x: x['created_at'], reverse=True)
    return analyses[:limit]


def _get_security_summary(analysis: SecurityAnalysis):
    """Get summary info for security analysis."""
    try:
        results = analysis.get_results()
        if not results:
            return None
        
        total_issues = 0
        high_critical = 0
        
        # Count Bandit issues
        if 'bandit' in results and 'results' in results['bandit']:
            bandit_issues = len(results['bandit']['results'])
            total_issues += bandit_issues
            for issue in results['bandit']['results']:
                if issue.get('issue_severity', '').lower() in ['high', 'critical']:
                    high_critical += 1
        
        # Count Safety issues  
        if 'safety' in results and 'vulnerabilities' in results['safety']:
            safety_issues = len(results['safety']['vulnerabilities'])
            total_issues += safety_issues
            high_critical += safety_issues  # Safety issues are typically high severity
        
        # Count ZAP issues
        if 'zap' in results and 'site' in results['zap'] and results['zap']['site']:
            if 'alerts' in results['zap']['site'][0]:
                zap_issues = len(results['zap']['site'][0]['alerts'])
                total_issues += zap_issues
                for alert in results['zap']['site'][0]['alerts']:
                    if alert.get('riskcode', 0) >= 2:  # Medium and above
                        high_critical += 1
        
        return {
            'total_issues': total_issues,
            'high_critical': high_critical,
            'tools_used': len([k for k in ['bandit', 'safety', 'zap', 'pylint', 'eslint'] if k in results])
        }
    except Exception:
        return None


def _get_performance_summary(test: PerformanceTest):
    """Get summary info for performance test."""
    try:
        results = test.get_results()
        if not results:
            return None
        
        # Extract key metrics
        avg_response = None
        throughput = None
        error_rate = None
        
        # Look for common performance metrics in results
        if 'locust' in results:
            locust_data = results['locust']
            if 'stats' in locust_data:
                stats = locust_data['stats']
                if stats:
                    avg_response = stats[0].get('avg_response_time')
                    throughput = stats[0].get('current_rps')
                    total_reqs = stats[0].get('num_requests', 1)
                    failures = stats[0].get('num_failures', 0)
                    error_rate = (failures / total_reqs * 100) if total_reqs > 0 else 0
        
        return {
            'avg_response_time': avg_response,
            'throughput': throughput, 
            'error_rate': error_rate
        }
    except Exception:
        return None


def _get_zap_summary(zap: ZAPAnalysis):
    """Get summary info for ZAP analysis."""
    try:
        # ZAPAnalysis uses different field names
        if hasattr(zap, 'get_zap_report'):
            results = zap.get_zap_report()
        else:
            # Fallback to direct access
            import json
            results = json.loads(zap.zap_report_json) if zap.zap_report_json else None
        
        if not results or 'site' not in results or not results['site']:
            return None
        
        alerts = results['site'][0].get('alerts', [])
        high_risk = len([a for a in alerts if a.get('riskcode', 0) >= 2])
        
        return {
            'total_alerts': len(alerts),
            'high_risk_alerts': high_risk
        }
    except Exception:
        return None


@reports_bp.route('/')
def reports_index():
    """Show analysis results dashboard."""
    analyses = _get_recent_analyses()
    files = _gather_file_reports(10)  # Limit file reports to last 10
    
    return render_template(
        'pages/reports/index.html', 
        analyses=analyses,
        files=files
    )


@reports_bp.route('/download/<path:fname>')
def download_report(fname: str):
    """Download generated report files."""
    target = Paths.REPORTS_DIR / fname
    if not target.exists() or not target.is_file():
        abort(404)
    # Basic path traversal guard
    if target.resolve().parent != Paths.REPORTS_DIR.resolve():
        abort(400)
    return send_file(target, as_attachment=True, download_name=target.name)
