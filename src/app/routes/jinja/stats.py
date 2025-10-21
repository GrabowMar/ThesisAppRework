"""Statistics routes for the Flask application."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable

from flask import Blueprint, abort, render_template, send_file, url_for, flash, redirect, request
from flask_login import current_user

from app.models import (
    GeneratedApplication,
    OpenRouterAnalysis,
    PerformanceTest,
    SecurityAnalysis,
    ZAPAnalysis,
)
from app.services.generation_statistics import (
    build_generation_table_data,
    collect_file_system_metrics,
    summarize_generation_counts,
    SUMMARY_PATH,
    write_generation_summary,
)
from app.services.statistics_service import (
    get_analysis_statistics,
    get_analysis_summary,
    get_application_statistics,
    get_model_distribution,
    get_model_statistics,
    get_recent_statistics,
)

logger = logging.getLogger(__name__)

stats_bp = Blueprint("statistics", __name__, url_prefix="/statistics")


def _enum_value(value: Any) -> Any:
    if value is None:
        return None
    return getattr(value, "value", value)


def _dt_value(value: Any) -> Any:
    return value.isoformat() if value else None


def _json_preview(raw: Any, max_length: int = 160) -> str:
    if not raw:
        return ""
    if isinstance(raw, str):
        text = raw
        try:
            parsed = json.loads(raw)
            text = json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            text = raw
    else:
        text = json.dumps(raw, ensure_ascii=False)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - 3]}..."


def _collect_generated_apps(limit: int = 200) -> Iterable[Dict[str, Any]]:
    apps = (
        GeneratedApplication.query.order_by(GeneratedApplication.created_at.desc())
        .limit(limit)
        .all()
    )
    for app in apps:
        metadata = app.get_metadata() if hasattr(app, "get_metadata") else {}
        yield {
            "id": app.id,
            "model_slug": app.model_slug,
            "app_number": app.app_number,
            "app_type": app.app_type,
            "provider": app.provider,
            "generation_status": _enum_value(app.generation_status),
            "has_backend": app.has_backend,
            "has_frontend": app.has_frontend,
            "has_docker_compose": app.has_docker_compose,
            "backend_framework": app.backend_framework,
            "frontend_framework": app.frontend_framework,
            "container_status": app.container_status,
            "last_status_check": _dt_value(app.last_status_check),
            "created_at": _dt_value(app.created_at),
            "updated_at": _dt_value(app.updated_at),
            "metadata_preview": _json_preview(metadata),
        }


def _collect_security_analyses(limit: int = 200) -> Iterable[Dict[str, Any]]:
    analyses = (
        SecurityAnalysis.query.order_by(SecurityAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    for analysis in analyses:
        enabled_tools = [
            name
            for name, flag in [
                ("bandit", analysis.bandit_enabled),
                ("safety", analysis.safety_enabled),
                ("pylint", analysis.pylint_enabled),
                ("eslint", analysis.eslint_enabled),
                ("npm_audit", analysis.npm_audit_enabled),
                ("snyk", analysis.snyk_enabled),
                ("zap", analysis.zap_enabled),
                ("semgrep", analysis.semgrep_enabled),
            ]
            if flag
        ]
        yield {
            "id": analysis.id,
            "application_id": analysis.application_id,
            "status": _enum_value(analysis.status),
            "analysis_name": analysis.analysis_name,
            "severity_threshold": analysis.severity_threshold,
            "max_issues_per_tool": analysis.max_issues_per_tool,
            "timeout_minutes": analysis.timeout_minutes,
            "total_issues": analysis.total_issues,
            "critical": analysis.critical_severity_count,
            "high": analysis.high_severity_count,
            "medium": analysis.medium_severity_count,
            "low": analysis.low_severity_count,
            "tools_run_count": analysis.tools_run_count,
            "tools_failed_count": analysis.tools_failed_count,
            "analysis_duration": analysis.analysis_duration,
            "enabled_tools": enabled_tools,
            "created_at": _dt_value(analysis.created_at),
            "started_at": _dt_value(analysis.started_at),
            "completed_at": _dt_value(analysis.completed_at),
            "metadata_preview": _json_preview(analysis.metadata_json),
            "results_preview": _json_preview(analysis.results_json),
        }


def _collect_performance_tests(limit: int = 200) -> Iterable[Dict[str, Any]]:
    tests = (
        PerformanceTest.query.order_by(PerformanceTest.created_at.desc())
        .limit(limit)
        .all()
    )
    for test in tests:
        yield {
            "id": test.id,
            "application_id": test.application_id,
            "status": _enum_value(test.status),
            "test_type": test.test_type,
            "users": test.users,
            "spawn_rate": test.spawn_rate,
            "test_duration": test.test_duration,
            "requests_per_second": test.requests_per_second,
            "average_response_time": test.average_response_time,
            "p95_response_time": test.p95_response_time,
            "p99_response_time": test.p99_response_time,
            "error_rate": test.error_rate,
            "total_requests": test.total_requests,
            "failed_requests": test.failed_requests,
            "created_at": _dt_value(test.created_at),
            "started_at": _dt_value(test.started_at),
            "completed_at": _dt_value(test.completed_at),
            "metadata_preview": _json_preview(test.metadata_json),
            "results_preview": _json_preview(test.results_json),
        }


def _collect_zap_analyses(limit: int = 200) -> Iterable[Dict[str, Any]]:
    analyses = (
        ZAPAnalysis.query.order_by(ZAPAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    for analysis in analyses:
        yield {
            "id": analysis.id,
            "application_id": analysis.application_id,
            "status": _enum_value(analysis.status),
            "scan_type": analysis.scan_type,
            "target_url": analysis.target_url,
            "high_risk_alerts": analysis.high_risk_alerts,
            "medium_risk_alerts": analysis.medium_risk_alerts,
            "low_risk_alerts": analysis.low_risk_alerts,
            "informational_alerts": analysis.informational_alerts,
            "created_at": _dt_value(analysis.created_at),
            "started_at": _dt_value(analysis.started_at),
            "completed_at": _dt_value(analysis.completed_at),
            "metadata_preview": _json_preview(analysis.metadata_json),
            "report_preview": _json_preview(analysis.zap_report_json),
        }


def _collect_openrouter_analyses(limit: int = 200) -> Iterable[Dict[str, Any]]:
    analyses = (
        OpenRouterAnalysis.query.order_by(OpenRouterAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    for analysis in analyses:
        yield {
            "id": analysis.id,
            "application_id": analysis.application_id,
            "status": _enum_value(analysis.status),
            "analyzer_model": analysis.analyzer_model,
            "overall_score": analysis.overall_score,
            "code_quality_score": analysis.code_quality_score,
            "security_score": analysis.security_score,
            "maintainability_score": analysis.maintainability_score,
            "input_tokens": analysis.input_tokens,
            "output_tokens": analysis.output_tokens,
            "cost_usd": analysis.cost_usd,
            "created_at": _dt_value(analysis.created_at),
            "started_at": _dt_value(analysis.started_at),
            "completed_at": _dt_value(analysis.completed_at),
            "summary_preview": _json_preview(analysis.summary),
            "metadata_preview": _json_preview(analysis.metadata_json),
        }


@stats_bp.route("/")
def statistics_overview():
    generation_summary = summarize_generation_counts()
    generation_rows = build_generation_table_data()
    fs_metrics = collect_file_system_metrics()

    summary_path = None
    try:
        summary_path = write_generation_summary()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write generation summary file: %s", exc)

    context = {
        "page_title": "Statistics Dashboard",
        "page_icon": "fas fa-chart-line",
        "generation_summary": generation_summary,
        "generation_rows": generation_rows,
        "filesystem_metrics": fs_metrics,
        "generation_download_url": url_for("statistics.download_generation_data"),
        "application_stats": get_application_statistics(),
        "model_stats": get_model_statistics(),
        "analysis_stats": get_analysis_statistics(),
        "recent_stats": get_recent_statistics(),
        "model_distribution": get_model_distribution(),
        "analysis_summary": get_analysis_summary(),
        "generated_apps": list(_collect_generated_apps()),
        "security_analyses": list(_collect_security_analyses()),
        "performance_tests": list(_collect_performance_tests()),
        "zap_analyses": list(_collect_zap_analyses()),
        "openrouter_analyses": list(_collect_openrouter_analyses()),
        "generation_summary_path": str(summary_path) if summary_path else None,
    }
    return render_template("pages/statistics/statistics_main.html", **context)


@stats_bp.route("/generation-data.json")
def download_generation_data():
    try:
        summary_path = write_generation_summary()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unable to refresh generation summary before download: %s", exc)
        summary_path = SUMMARY_PATH if SUMMARY_PATH.exists() else None

    if not summary_path or not summary_path.exists():
        abort(404)

    return send_file(
        summary_path,
        mimetype="application/json",
        as_attachment=True,
        download_name="generation_stats_summary.json",
    )