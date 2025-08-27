"""Tasks Routes
=================

Replaces legacy batch overview with a unified tasks monitoring page.
Shows active, queued, and recent analysis tasks across all analysis types.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint
from .analysis import render_template  # reuse compatibility shim import

from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')


@tasks_bp.route('/')
def tasks_overview():
    """Unified tasks overview (active + queue + recent history)."""
    try:
        # Active / running
        active_security = SecurityAnalysis.query.filter(SecurityAnalysis.status == 'running').all()
        active_performance = PerformanceTest.query.filter(PerformanceTest.status == 'running').all()
        active_dynamic = ZAPAnalysis.query.filter(ZAPAnalysis.status == 'running').all()

        active = [
            *[{ 'type': 'security', 'id': a.id, 'model_slug': a.model_slug, 'app_number': a.app_number, 'started_at': a.created_at } for a in active_security],
            *[{ 'type': 'performance', 'id': a.id, 'model_slug': a.model_slug, 'app_number': a.app_number, 'started_at': a.created_at } for a in active_performance],
            *[{ 'type': 'dynamic', 'id': a.id, 'model_slug': a.model_slug, 'app_number': a.app_number, 'started_at': a.created_at } for a in active_dynamic],
        ]

        # Queued (pending)
        queued_security = SecurityAnalysis.query.filter(SecurityAnalysis.status.in_(['pending','queued'])).all()
        queued_performance = PerformanceTest.query.filter(PerformanceTest.status.in_(['pending','queued'])).all()
        queued_dynamic = ZAPAnalysis.query.filter(ZAPAnalysis.status.in_(['pending','queued'])).all()
        queued = [
            *[{ 'type': 'security', 'id': a.id, 'model_slug': a.model_slug, 'app_number': a.app_number } for a in queued_security],
            *[{ 'type': 'performance', 'id': a.id, 'model_slug': a.model_slug, 'app_number': a.app_number } for a in queued_performance],
            *[{ 'type': 'dynamic', 'id': a.id, 'model_slug': a.model_slug, 'app_number': a.app_number } for a in queued_dynamic],
        ]

        # Recent (last 25, any status, within 30 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent_security = SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= cutoff).order_by(SecurityAnalysis.created_at.desc()).limit(25).all()
        recent_performance = PerformanceTest.query.filter(PerformanceTest.created_at >= cutoff).order_by(PerformanceTest.created_at.desc()).limit(25).all()
        recent_dynamic = ZAPAnalysis.query.filter(ZAPAnalysis.created_at >= cutoff).order_by(ZAPAnalysis.created_at.desc()).limit(25).all()
        recent = [
            *[{ 'type': 'security', 'id': a.id, 'status': a.status, 'model_slug': a.model_slug, 'app_number': a.app_number, 'created_at': a.created_at } for a in recent_security],
            *[{ 'type': 'performance', 'id': a.id, 'status': a.status, 'model_slug': a.model_slug, 'app_number': a.app_number, 'created_at': a.created_at } for a in recent_performance],
            *[{ 'type': 'dynamic', 'id': a.id, 'status': a.status, 'model_slug': a.model_slug, 'app_number': a.app_number, 'created_at': a.created_at } for a in recent_dynamic],
        ]
        recent.sort(key=lambda r: r['created_at'], reverse=True)
        recent = recent[:25]

        metrics = {
            'active_count': len(active),
            'queued_count': len(queued),
            'recent_24h': sum(1 for r in recent if (datetime.now(timezone.utc) - r['created_at']).total_seconds() < 86400),
            'completed_today': sum(1 for r in recent if r['status'] == 'completed' and (datetime.now(timezone.utc) - r['created_at']).total_seconds() < 86400),
        }

        return render_template(
            'single_page.html',
            page_title='Tasks Overview',
            page_icon='fa-tasks',
            main_partial='pages/tasks/overview.html',
            active=active,
            queued=queued,
            recent=recent,
            metrics=metrics
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Error loading tasks overview: {e}")
        return render_template('single_page.html', page_title='Error', main_partial='partials/common/error.html', error=str(e)), 500
