"""
Reports routes (v2)
===================

Simplified web routes for reports module.
Reports are rendered client-side using JSON data from API.
"""
import logging
from flask import Blueprint, flash, redirect, url_for, request
from flask_login import current_user

from app.utils.template_paths import render_template_compat as render_template
from ...extensions import db
from ...models import Report

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


@reports_bp.before_request
def require_authentication():
    """Require authentication for all report endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access reports.', 'info')
        return redirect(url_for('auth.login', next=request.url))


@reports_bp.route('/')
def reports_index():
    """
    Main reports page.
    
    Lists existing reports and provides UI to create new ones.
    Actual report list is fetched via API for better interactivity.
    """
    # Get reports for initial render (can also be fetched via API)
    reports = db.session.query(Report).filter(
        Report.status.in_(['completed', 'failed', 'generating'])
    ).order_by(Report.created_at.desc()).limit(50).all()
    
    return render_template(
        'pages/reports/reports_main.html',
        reports=[r.to_dict() for r in reports]
    )


@reports_bp.route('/view/<report_id>')
def view_report(report_id: str):
    """
    View a specific report.
    
    Renders a shell page that fetches report data via API
    and renders it client-side with JavaScript.
    """
    report = Report.query.filter_by(report_id=report_id).first()
    
    if not report:
        flash('Report not found', 'error')
        return redirect(url_for('reports.reports_index'))
    
    if report.status == 'failed':
        flash(f'This report failed to generate: {report.error_message}', 'error')
        return redirect(url_for('reports.reports_index'))
    
    if report.status == 'generating':
        flash('This report is still being generated. Please wait...', 'info')
        return redirect(url_for('reports.reports_index'))
    
    return render_template(
        'pages/reports/view_report.html',
        report=report.to_dict(),
        report_id=report_id
    )


@reports_bp.route('/new')
def new_report_form():
    """
    Return the new report modal fragment for HTMX.
    
    Form data is populated via API call to /api/reports/options.
    """
    return render_template('pages/reports/partials/_new_report_modal.html')
