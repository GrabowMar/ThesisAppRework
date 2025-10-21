"""Dashboard routes for enhanced analysis visualization."""
from flask import Blueprint, render_template, jsonify, send_file, abort, flash, redirect, url_for, request
from flask_login import current_user
from datetime import datetime
import io
import csv

from app.services.service_locator import ServiceLocator

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/analysis/dashboard')

# Require authentication
@dashboard_bp.before_request
def require_authentication():
    """Require authentication for all dashboard endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access the dashboard.', 'info')
        return redirect(url_for('auth.login', next=request.url))


@dashboard_bp.route('/app/<model_slug>/<int:app_number>')
def app_dashboard(model_slug: str, app_number: int):
    """
    Enhanced dashboard view for a single app analysis.
    
    Shows:
    - Summary metrics
    - Filterable findings table
    - Tool execution details
    - CSV export option
    """
    inspection_service = ServiceLocator.get('analysis_inspection_service')
    if not inspection_service:
        abort(503, "Analysis inspection service not available")
    
    # Find the most recent analysis for this app (any type with results)
    from app.services.task_service import AnalysisTaskService
    tasks = AnalysisTaskService.list_tasks(model_slug=model_slug, limit=100)
    
    # Filter for this app - accept any analysis type that has results
    app_tasks = [
        t for t in tasks 
        if t.target_app_number == app_number 
        and t.status == 'completed'
    ]
    
    if not app_tasks:
        abort(404, f"No completed analysis found for {model_slug} app {app_number}")
    
    # Get the most recent task
    task = sorted(app_tasks, key=lambda t: t.created_at or datetime.min, reverse=True)[0]
    
    # Get full results payload
    try:
        payload = inspection_service.get_task_results_payload(task.task_id)
    except Exception as e:
        abort(500, f"Error loading results: {str(e)}")
    
    return render_template(
        'pages/analysis/dashboard/app_detail.html',
        task=task,
        model_slug=model_slug,
        app_number=app_number,
        payload=payload
    )


@dashboard_bp.route('/api/app/<model_slug>/<int:app_number>/export.csv')
def export_app_csv(model_slug: str, app_number: int):
    """Export app analysis results as CSV."""
    inspection_service = ServiceLocator.get('analysis_inspection_service')
    if not inspection_service:
        abort(503, "Analysis inspection service not available")
    
    # Find task
    from app.services.task_service import AnalysisTaskService
    tasks = AnalysisTaskService.list_tasks(model_slug=model_slug, limit=100)
    app_tasks = [
        t for t in tasks 
        if t.target_app_number == app_number 
        and t.status == 'completed'
    ]
    
    if not app_tasks:
        abort(404, "No analysis found")
    
    task = sorted(app_tasks, key=lambda t: t.created_at or datetime.min, reverse=True)[0]
    payload = inspection_service.get_task_results_payload(task.task_id)
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow([
        'Tool', 'Category', 'Severity', 'Type', 
        'File', 'Line', 'Message', 'Rule/Symbol', 'CWE'
    ])
    
    # Write findings
    findings = payload.get('results', {}).get('findings', [])
    for f in findings:
        writer.writerow([
            f.get('tool', ''),
            f.get('category', ''),
            f.get('severity', ''),
            f.get('type', ''),
            f.get('file', {}).get('path', ''),
            f.get('file', {}).get('line_start', ''),
            (f.get('message', {}).get('title') or f.get('message', {}).get('description', ''))[:100],
            f.get('rule_id') or f.get('symbol', ''),
            f.get('metadata', {}).get('cwe_id', '')
        ])
    
    # Create response
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{model_slug}_app{app_number}_findings.csv'
    )


@dashboard_bp.route('/model/<model_slug>')
def model_dashboard(model_slug: str):
    """Model comparison dashboard - coming in Phase 2."""
    return render_template(
        'pages/analysis/dashboard/model_comparison.html',
        model_slug=model_slug,
        phase='Phase 2 - Coming Soon'
    )


@dashboard_bp.route('/tools')
def tools_dashboard():
    """Tools overview dashboard - coming in Phase 3."""
    return render_template(
        'pages/analysis/dashboard/tools_overview.html',
        phase='Phase 3 - Coming Soon'
    )


@dashboard_bp.route('/compare')
def cross_model_comparison():
    """Cross-model comparison - coming in Phase 4."""
    return render_template(
        'pages/analysis/dashboard/cross_model.html',
        phase='Phase 4 - Coming Soon'
    )

