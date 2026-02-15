"""
Reports routes (v2)
===================

Web routes for reports module.
Reports list uses HTMX partials; viewer renders server-side Jinja.
"""
import logging
from typing import Any, Dict, List

from flask import Blueprint, flash, redirect, url_for, request
from flask_login import current_user

from flask import render_template
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


def _load_report_options() -> Dict[str, Any]:
    """Load options for report creation (models, templates, tools)."""
    from ...models import ModelCapability, GeneratedApplication
    from ...engines.container_tool_registry import get_container_tool_registry
    from ...services.generation_v2 import get_generation_service
    from ...utils.slug_utils import normalize_model_slug

    # Models from generated apps
    app_model_slugs = db.session.query(
        GeneratedApplication.model_slug
    ).distinct().all()
    app_model_slugs = [row[0] for row in app_model_slugs if row[0]]

    models_data: List[Dict[str, str]] = []
    seen_slugs: set = set()
    for slug in app_model_slugs:
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        normalized = normalize_model_slug(slug)
        capability = ModelCapability.query.filter(
            (ModelCapability.canonical_slug == slug) |
            (ModelCapability.canonical_slug == normalized)
        ).first()
        if capability:
            models_data.append({
                'slug': slug,
                'name': capability.model_name or slug,
                'provider': capability.provider or (slug.split('_')[0] if '_' in slug else 'unknown')
            })
        else:
            parts = slug.split('_', 1)
            models_data.append({
                'slug': slug,
                'name': (parts[1] if len(parts) > 1 else slug).replace('-', ' ').title(),
                'provider': parts[0] if parts else 'unknown'
            })
    models_data.sort(key=lambda m: (m['provider'], m['name']))

    # Templates
    try:
        gen_service = get_generation_service()
        templates_catalog = gen_service.get_template_catalog()
        templates_data = [{
            'slug': t.get('slug'),
            'name': t.get('name'),
            'category': t.get('category', 'general')
        } for t in templates_catalog if t.get('slug') and t.get('name')]
        templates_data.sort(key=lambda t: (t['category'], t['name']))
    except Exception:
        templates_data = []

    # Tools
    try:
        tool_registry = get_container_tool_registry()
        all_tools = tool_registry.get_all_tools()
        tools_data = [{
            'name': tool.name,
            'display_name': tool.display_name,
            'container': tool.container.value if hasattr(tool.container, 'value') else str(tool.container),
            'available': tool.available
        } for tool in all_tools.values()]
        tools_data.sort(key=lambda t: (t['container'], t['display_name']))
    except Exception:
        tools_data = []

    return {
        'models': models_data,
        'templates': templates_data,
        'tools': tools_data,
    }


@reports_bp.route('/')
def reports_index():
    """Main reports page — HTMX loads the table partial."""
    return render_template('pages/reports/reports_main.html')


@reports_bp.route('/api/list')
def reports_table():
    """HTMX endpoint: render the reports table partial with filters."""
    report_type = request.args.get('report_type', '').strip() or None
    status = request.args.get('status', '').strip() or None
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(100, max(10, int(request.args.get('per_page', 25))))

    query = Report.query
    if report_type:
        query = query.filter(Report.report_type == report_type)
    if status:
        query = query.filter(Report.status == status)

    total = query.count()
    reports = (
        query.order_by(Report.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Counts by status
    count_completed = Report.query.filter(Report.status == 'completed').count()
    count_generating = Report.query.filter(Report.status == 'generating').count()
    count_failed = Report.query.filter(Report.status == 'failed').count()

    return render_template(
        'pages/reports/partials/_reports_table.html',
        reports=reports,
        total=total,
        count_completed=count_completed,
        count_generating=count_generating,
        count_failed=count_failed,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
        filter_type=report_type or '',
        filter_status=status or '',
    )


@reports_bp.route('/create')
def reports_create():
    """Full-page report creation wizard."""
    options = _load_report_options()
    return render_template(
        'pages/reports/reports_create.html',
        models=options['models'],
        templates=options['templates'],
        tools=options['tools'],
    )


@reports_bp.route('/view/<report_id>')
def view_report(report_id: str):
    """View a specific report — server-rendered with accordion sections."""
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

    report_data = report.get_report_data() or {}
    report_dict = report.to_dict()

    # Pre-compute "most common issues" from findings list
    common_issues: List[Dict[str, Any]] = []
    findings = report_data.get('findings', [])
    if findings:
        from collections import Counter
        issue_groups: Dict[str, Dict[str, Any]] = {}
        for f in findings:
            msg = f.get('message', f.get('title', ''))
            if not msg:
                continue
            key = msg[:120]
            if key not in issue_groups:
                issue_groups[key] = {
                    'message': msg,
                    'count': 0,
                    'severity': f.get('severity', 'info'),
                    'tool': f.get('tool', ''),
                    'apps': set(),
                }
            issue_groups[key]['count'] += 1
            app_num = f.get('app_number')
            if app_num:
                issue_groups[key]['apps'].add(app_num)
        common_issues = sorted(
            issue_groups.values(), key=lambda x: x['count'], reverse=True
        )[:30]
        for ci in common_issues:
            ci['app_count'] = len(ci['apps'])
            ci.pop('apps', None)

    # Count findings by tool
    tool_finding_counts: Dict[str, int] = {}
    for f in findings:
        tool = f.get('tool', 'unknown')
        tool_finding_counts[tool] = tool_finding_counts.get(tool, 0) + 1

    # For model_analysis: get total apps in DB for this model
    total_model_apps = None
    if report.report_type == 'model_analysis':
        model_slug = report_data.get('model_slug')
        if model_slug:
            from ...models import GeneratedApplication
            total_model_apps = GeneratedApplication.query.filter_by(
                model_slug=model_slug
            ).count()

    # Prev/next navigation (same report_type)
    prev_report = (
        Report.query
        .filter(
            Report.report_type == report.report_type,
            Report.status == 'completed',
            Report.created_at < report.created_at,
        )
        .order_by(Report.created_at.desc())
        .with_entities(Report.report_id)
        .first()
    )
    next_report = (
        Report.query
        .filter(
            Report.report_type == report.report_type,
            Report.status == 'completed',
            Report.created_at > report.created_at,
        )
        .order_by(Report.created_at.asc())
        .with_entities(Report.report_id)
        .first()
    )

    # Route tool_analysis reports to dedicated template
    if report.report_type == 'tool_analysis':
        overall_stats = report_data.get('summary', {})
        overall_stats.setdefault('total_executions', report_data.get('total_executions', 0))
        overall_stats.setdefault('total_successful', overall_stats.get('total_successful', 0))
        overall_stats.setdefault('overall_success_rate', overall_stats.get('avg_success_rate', 0))
        overall_stats.setdefault('total_findings', overall_stats.get('total_findings', 0))

        filters = report_data.get('filter', {})
        tools_list = report_data.get('tools', [])
        tools_count = report_data.get('tools_count', len(tools_list) if isinstance(tools_list, list) else 0)

        # Build insights from top_performers
        top = report_data.get('top_performers', {})
        insights = {
            'most_findings_tool': top['by_findings'][0].get('tool_name', top['by_findings'][0].get('name')) if top.get('by_findings') else None,
            'best_success_rate_tool': top['by_success_rate'][0].get('tool_name', top['by_success_rate'][0].get('name')) if top.get('by_success_rate') else None,
            'worst_success_rate_tool': top['by_success_rate'][-1].get('tool_name', top['by_success_rate'][-1].get('name')) if top.get('by_success_rate') else None,
            'fastest_tool': top['fastest'][0].get('tool_name', top['fastest'][0].get('name')) if top.get('fastest') else None,
            'slowest_tool': top['slowest'][0].get('tool_name', top['slowest'][0].get('name')) if top.get('slowest') else None,
        }

        return render_template(
            'pages/reports/partials/_tool_analysis.html',
            report_id=report_id,
            timestamp=report_data.get('generated_at', ''),
            filters=filters,
            tools_count=tools_count,
            tasks_analyzed=report_data.get('total_executions', 0),
            overall_stats=overall_stats,
            tools=tools_list if isinstance(tools_list, list) else list(tools_list.values()),
            insights=insights,
            analyzer_categories=report_data.get('analyzer_categories', {}),
            prev_report_id=prev_report[0] if prev_report else None,
            next_report_id=next_report[0] if next_report else None,
        )

    return render_template(
        'pages/reports/view_report.html',
        report=report_dict,
        report_id=report_id,
        report_data=report_data,
        common_issues=common_issues,
        tool_finding_counts=tool_finding_counts,
        total_model_apps=total_model_apps,
        prev_report_id=prev_report[0] if prev_report else None,
        next_report_id=next_report[0] if next_report else None,
    )


@reports_bp.route('/new')
def new_report_form():
    """Return the new report modal fragment for HTMX (deprecated — use /reports/create)."""
    return render_template('pages/reports/partials/_new_report_modal.html')
