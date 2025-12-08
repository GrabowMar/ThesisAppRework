"""
Reports routes for the Flask application
=======================================

Reports-related web routes that render Jinja templates.
"""

from flask import Blueprint, send_file, flash, redirect, url_for, request, jsonify
from flask_login import current_user
from markupsafe import Markup

from app.utils.template_paths import render_template_compat as render_template
from app.paths import REPORTS_DIR
from ...services.service_locator import ServiceLocator
from ...services.tool_registry_service import get_tool_registry_service
from ...extensions import db
from ...models import Report, ModelCapability, GeneratedApplication, AnalysisTask

# Import shared utilities
from ..shared_utils import _gather_file_reports, _get_recent_analyses

# Create blueprint
reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# Require authentication
@reports_bp.before_request
def require_authentication():
    """Require authentication for all report endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access reports.', 'info')
        return redirect(url_for('auth.login', next=request.url))

@reports_bp.route('/')
def reports_index():
    """Show reports list with generated reports from database."""
    # Get generated reports from database
    reports = db.session.query(Report).order_by(Report.created_at.desc()).limit(50).all()
    
    # Template renders the reports list
    return render_template(
        'pages/reports/reports_main.html',
        reports=reports
    )

@reports_bp.route('/new')
def new_report():
    """Show report generation form (modal fragment for HTMX)."""
    # Get models that have generated applications
    models_with_apps = db.session.query(ModelCapability).join(
        GeneratedApplication,
        ModelCapability.canonical_slug == GeneratedApplication.model_slug
    ).distinct().order_by(ModelCapability.provider, ModelCapability.model_name).all()
    
    # Get available apps for selection (grouped by model)
    apps = db.session.query(GeneratedApplication).order_by(
        GeneratedApplication.model_slug, 
        GeneratedApplication.app_number
    ).all()
    
    # Build a map of model_slug -> [app_numbers] for easy lookup in template
    apps_by_model = {}
    for app in apps:
        if app.model_slug not in apps_by_model:
            apps_by_model[app.model_slug] = []
        apps_by_model[app.model_slug].append(app.app_number)
    
    # Convert models to dicts for JSON serialization in template
    models_data = []
    for model in models_with_apps:
        models_data.append({
            'id': model.model_id,
            'model_id': model.model_id,
            'canonical_slug': model.canonical_slug,
            'model_slug': model.canonical_slug,
            'slug': model.canonical_slug,
            'model_name': model.model_name,
            'display_name': model.model_name,
            'provider': model.provider
        })
    
    # Get available tools from the registry
    tool_registry = get_tool_registry_service()
    all_tools = tool_registry.get_all_tools()
    tools_data = [
        {
            'name': tool.name,
            'display_name': tool.display_name,
            'container': tool.container.value if hasattr(tool.container, 'value') else str(tool.container),
            'tags': list(tool.tags) if tool.tags else [],
            'available': tool.available
        }
        for tool in all_tools.values()
    ]
    # Sort by container then display name
    tools_data.sort(key=lambda t: (t['container'], t['display_name']))
    
    # Get available templates from generation service
    from ...services.generation import get_generation_service
    gen_service = get_generation_service()
    templates_catalog = gen_service.get_template_catalog()
    
    # Simplify template data for the modal
    templates_data = [
        {
            'slug': t.get('slug'),
            'name': t.get('name'),
            'category': t.get('category', 'general')
        }
        for t in templates_catalog
        if t.get('slug') and t.get('name')
    ]
    # Sort by category then name
    templates_data.sort(key=lambda t: (t['category'], t['name']))
    
    # Return modal fragment for HTMX
    return render_template(
        'pages/reports/partials/_new_report_modal.html',
        models=models_data,
        apps_by_model=apps_by_model,
        tools=tools_data,
        templates=templates_data
    )

@reports_bp.route('/view/<report_id>')
def view_report(report_id: str):
    """View a generated report."""
    service_locator = ServiceLocator()
    report_service = service_locator.get_report_service()
    
    report = report_service.get_report(report_id)
    
    if not report:
        flash('Report not found', 'error')
        return redirect(url_for('reports.reports_index'))
    
    # If HTML report, render directly; otherwise show details and download link
    if report.format == 'html' and report.status == 'completed':
        # Load report data
        file_path = report_service.reports_dir / report.file_path
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            # Serve the HTML content - mark as safe since it's generated by our system
            return Markup(html_content)
    
    # For other formats, show report details
    return render_template(
        'pages/reports/view_report.html',
        report=report
    )

@reports_bp.route('/download/<path:fname>')
def download_report(fname: str):
    """Download generated report files (legacy file-based reports)."""
    target = REPORTS_DIR / fname
    if not target.exists() or not target.is_file():
        from flask import abort
        abort(404)
    if target.resolve().parent != REPORTS_DIR.resolve():
        from flask import abort
        abort(400)
    return send_file(target, as_attachment=True, download_name=target.name)