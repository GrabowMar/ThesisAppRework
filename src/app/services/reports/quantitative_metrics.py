"""Quantitative metrics helpers.

This module centralizes DB-backed numeric metrics used in multiple report
generators (generation success, docker/container health, performance percentiles,
AI analysis scores, and security summary counts).

Keeping this logic in one place reduces drift between reports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ...extensions import db
from ...models import (
    GeneratedApplication,
    PerformanceTest,
    OpenRouterAnalysis,
    SecurityAnalysis,
)

logger = logging.getLogger(__name__)


def collect_quantitative_metrics(
    model_slug: str,
    filter_apps: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Collect quantitative metrics from database models for all apps of a model."""
    import statistics

    metrics: Dict[str, Any] = {
        'available': False,
        'performance': {},
        'ai_analysis': {},
        'security': {},
        'generation': {},
        'docker': {},
    }

    try:
        # Query GeneratedApplication for generation success metrics
        app_query = db.session.query(GeneratedApplication).filter(
            GeneratedApplication.model_slug == model_slug
        )
        if filter_apps:
            app_query = app_query.filter(GeneratedApplication.app_number.in_(filter_apps))

        apps = app_query.all()

        if not apps:
            return metrics

        # Generation success metrics
        total_apps = len(apps)
        successful_apps = sum(1 for a in apps if not a.is_generation_failed)
        failed_apps = sum(1 for a in apps if a.is_generation_failed)

        # Fix counts aggregation (handle missing attributes gracefully)
        retry_fixes = sum(getattr(a, 'retry_fixes', 0) or 0 for a in apps)
        automatic_fixes = sum(getattr(a, 'automatic_fixes', 0) or 0 for a in apps)
        llm_fixes = sum(getattr(a, 'llm_fixes', 0) or 0 for a in apps)
        manual_fixes = sum(getattr(a, 'manual_fixes', 0) or 0 for a in apps)
        total_fixes = retry_fixes + automatic_fixes + llm_fixes + manual_fixes

        # Generation attempts
        total_attempts = sum(getattr(a, 'generation_attempts', 1) or 1 for a in apps)

        metrics['generation'] = {
            'total_apps': total_apps,
            'successful_apps': successful_apps,
            'failed_apps': failed_apps,
            'success_rate': round(successful_apps / total_apps * 100, 2) if total_apps > 0 else 0,
            'total_generation_attempts': total_attempts,
            'avg_attempts_per_app': round(total_attempts / total_apps, 2) if total_apps > 0 else 0,
            'fix_counts': {
                'retry_fixes': retry_fixes,
                'automatic_fixes': automatic_fixes,
                'llm_fixes': llm_fixes,
                'manual_fixes': manual_fixes,
                'total_fixes': total_fixes,
            },
            'avg_fixes_per_app': round(total_fixes / total_apps, 2) if total_apps > 0 else 0,
        }

        # Docker/Container status aggregation
        container_status_counts: Dict[str, int] = {}
        for app in apps:
            status = app.container_status or 'unknown'
            # Normalize similar statuses
            if status in ('never_built', 'not_built'):
                status = 'never_built'
            elif status in ('failed', 'build_failed', 'error'):
                status = 'error'
            container_status_counts[status] = container_status_counts.get(status, 0) + 1

        # Calculate Docker health metrics
        running_count = container_status_counts.get('running', 0)
        stopped_count = container_status_counts.get('stopped', 0)
        error_count = container_status_counts.get('error', 0)
        never_built = container_status_counts.get('never_built', 0) + container_status_counts.get('unknown', 0)

        # Apps that have been successfully built (running or stopped)
        build_success_count = running_count + stopped_count
        build_success_rate = round(build_success_count / total_apps * 100, 2) if total_apps > 0 else 0

        metrics['docker'] = {
            'status_breakdown': container_status_counts,
            'running': running_count,
            'stopped': stopped_count,
            'error': error_count,
            'never_built': never_built,
            'build_success_count': build_success_count,
            'build_success_rate': build_success_rate,
            'total_apps': total_apps,
        }

        # Query PerformanceTest for performance metrics
        app_ids = [a.id for a in apps]
        perf_tests = db.session.query(PerformanceTest).filter(
            PerformanceTest.application_id.in_(app_ids)
        ).all()

        if perf_tests:
            p95_times = [p.p95_response_time for p in perf_tests if p.p95_response_time is not None]
            p99_times = [p.p99_response_time for p in perf_tests if p.p99_response_time is not None]
            rps_values = [p.requests_per_second for p in perf_tests if p.requests_per_second is not None]
            error_rates = [p.error_rate for p in perf_tests if p.error_rate is not None]
            total_requests = sum(p.total_requests or 0 for p in perf_tests)
            failed_requests = sum(p.failed_requests or 0 for p in perf_tests)

            metrics['performance'] = {
                'tests_count': len(perf_tests),
                'p95_response_time': {
                    'mean': round(statistics.mean(p95_times), 3) if p95_times else 0,
                    'min': round(min(p95_times), 3) if p95_times else 0,
                    'max': round(max(p95_times), 3) if p95_times else 0,
                    'median': round(statistics.median(p95_times), 3) if p95_times else 0,
                } if p95_times else {},
                'p99_response_time': {
                    'mean': round(statistics.mean(p99_times), 3) if p99_times else 0,
                    'min': round(min(p99_times), 3) if p99_times else 0,
                    'max': round(max(p99_times), 3) if p99_times else 0,
                    'median': round(statistics.median(p99_times), 3) if p99_times else 0,
                } if p99_times else {},
                'requests_per_second': {
                    'mean': round(statistics.mean(rps_values), 2) if rps_values else 0,
                    'min': round(min(rps_values), 2) if rps_values else 0,
                    'max': round(max(rps_values), 2) if rps_values else 0,
                } if rps_values else {},
                'error_rate': {
                    'mean': round(statistics.mean(error_rates), 4) if error_rates else 0,
                    'max': round(max(error_rates), 4) if error_rates else 0,
                } if error_rates else {},
                'total_requests': total_requests,
                'failed_requests': failed_requests,
            }

        # Query OpenRouterAnalysis for AI analysis scores
        ai_analyses = db.session.query(OpenRouterAnalysis).filter(
            OpenRouterAnalysis.application_id.in_(app_ids)
        ).all()

        if ai_analyses:
            overall_scores = [a.overall_score for a in ai_analyses if a.overall_score is not None]
            quality_scores = [a.code_quality_score for a in ai_analyses if a.code_quality_score is not None]
            security_scores = [a.security_score for a in ai_analyses if a.security_score is not None]
            maint_scores = [a.maintainability_score for a in ai_analyses if a.maintainability_score is not None]
            total_input_tokens = sum(a.input_tokens or 0 for a in ai_analyses)
            total_output_tokens = sum(a.output_tokens or 0 for a in ai_analyses)
            total_cost = sum(a.cost_usd or 0 for a in ai_analyses)

            metrics['ai_analysis'] = {
                'analyses_count': len(ai_analyses),
                'overall_score': {
                    'mean': round(statistics.mean(overall_scores), 2) if overall_scores else 0,
                    'min': round(min(overall_scores), 2) if overall_scores else 0,
                    'max': round(max(overall_scores), 2) if overall_scores else 0,
                    'std_dev': round(statistics.stdev(overall_scores), 2) if len(overall_scores) > 1 else 0,
                } if overall_scores else {},
                'code_quality_score': {
                    'mean': round(statistics.mean(quality_scores), 2) if quality_scores else 0,
                } if quality_scores else {},
                'security_score': {
                    'mean': round(statistics.mean(security_scores), 2) if security_scores else 0,
                } if security_scores else {},
                'maintainability_score': {
                    'mean': round(statistics.mean(maint_scores), 2) if maint_scores else 0,
                } if maint_scores else {},
                'token_usage': {
                    'total_input_tokens': total_input_tokens,
                    'total_output_tokens': total_output_tokens,
                    'total_tokens': total_input_tokens + total_output_tokens,
                },
                'total_ai_analysis_cost_usd': round(total_cost, 6),
            }

        # Query SecurityAnalysis for security metrics
        security_analyses = db.session.query(SecurityAnalysis).filter(
            SecurityAnalysis.application_id.in_(app_ids)
        ).all()

        if security_analyses:
            total_issues = sum(s.total_issues or 0 for s in security_analyses)
            critical_count = sum(s.critical_severity_count or 0 for s in security_analyses)
            high_count = sum(s.high_severity_count or 0 for s in security_analyses)
            medium_count = sum(s.medium_severity_count or 0 for s in security_analyses)
            low_count = sum(s.low_severity_count or 0 for s in security_analyses)
            tools_run = sum(s.tools_run_count or 0 for s in security_analyses)
            tools_failed = sum(s.tools_failed_count or 0 for s in security_analyses)
            total_duration = sum(s.analysis_duration or 0 for s in security_analyses)

            metrics['security'] = {
                'analyses_count': len(security_analyses),
                'total_issues': total_issues,
                'severity_breakdown': {
                    'critical': critical_count,
                    'high': high_count,
                    'medium': medium_count,
                    'low': low_count,
                },
                'tools_run_count': tools_run,
                'tools_failed_count': tools_failed,
                'tool_success_rate': round((tools_run - tools_failed) / tools_run * 100, 2) if tools_run > 0 else 0,
                'total_analysis_duration_seconds': round(total_duration, 2),
                'avg_duration_per_analysis': round(total_duration / len(security_analyses), 2) if security_analyses else 0,
                'avg_issues_per_analysis': round(total_issues / len(security_analyses), 2) if security_analyses else 0,
            }

        metrics['available'] = True

    except Exception as e:
        logger.warning(f"Failed to collect quantitative metrics for {model_slug}: {e}")
        metrics['error'] = str(e)

    return metrics
