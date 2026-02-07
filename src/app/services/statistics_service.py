"""Statistics Service Layer - Big Picture Dashboard
=====================================================

Provides aggregation logic for system-wide statistics and trends.
Designed to supplement the Reports module with high-level overview data.

Key Metrics:
- System health and analyzer status
- Overall analysis trends and completion rates  
- Finding severity distributions across all analyses
- Model and tool performance comparisons
- Recent activity timeline

Design Notes:
- Returns plain dictionaries (JSON-ready)
- Focuses on aggregate/summary data only (details in Reports)
- No Flask request context assumptions
- Optimized queries for dashboard performance
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy import func, desc

from ..extensions import db
from ..models import (
    GeneratedApplication,
    AnalysisTask,
)
from ..constants import AnalysisStatus
from ..paths import RESULTS_DIR, GENERATED_APPS_DIR

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System Overview - Key Performance Indicators
# ---------------------------------------------------------------------------

def get_system_overview() -> Dict[str, Any]:
    """Get high-level system KPIs for dashboard cards."""
    try:
        # Total apps generated
        total_apps = db.session.query(func.count(GeneratedApplication.id)).scalar() or 0
        
        # Unique models
        unique_models = db.session.query(
            func.count(func.distinct(GeneratedApplication.model_slug))
        ).scalar() or 0
        
        # Unique apps analyzed (distinct model+app combinations in tasks)
        # Use separate count to avoid SQLite concat issue
        unique_app_combos = db.session.query(
            AnalysisTask.target_model,
            AnalysisTask.target_app_number
        ).distinct().count()
        
        # Total analysis tasks
        total_tasks = db.session.query(func.count(AnalysisTask.id)).scalar() or 0
        
        # Completed tasks
        completed_count = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Failed tasks
        failed_count = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.status == AnalysisStatus.FAILED  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Running tasks
        running_count = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.status == AnalysisStatus.RUNNING  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Pending tasks
        pending_count = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.status == AnalysisStatus.PENDING  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Average duration (completed tasks last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        avg_duration = db.session.query(
            func.avg(AnalysisTask.actual_duration)
        ).filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED,  # type: ignore[arg-type]
            AnalysisTask.completed_at >= week_ago  # type: ignore[arg-type]
        ).scalar()
        
        # Success rate calculation
        total_finished = completed_count + failed_count
        success_rate = round((completed_count / total_finished * 100), 1) if total_finished > 0 else 0.0
        
        return {
            "total_apps": total_apps,
            "unique_apps": unique_app_combos,
            "unique_models": unique_models,
            "total_tasks": total_tasks,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "running_count": running_count,
            "pending_count": pending_count,
            "success_rate": success_rate,
            "avg_duration_seconds": round(float(avg_duration), 1) if avg_duration else 0.0,
        }
    except Exception as e:
        logger.error(f"Error getting system overview: {e}")
        return {
            "total_apps": 0,
            "unique_apps": 0,
            "unique_models": 0,
            "total_tasks": 0,
            "completed_count": 0,
            "failed_count": 0,
            "running_count": 0,
            "pending_count": 0,
            "success_rate": 0.0,
            "avg_duration_seconds": 0.0,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Severity Distribution - Aggregate Finding Severities
# ---------------------------------------------------------------------------

def get_severity_distribution() -> Dict[str, int]:
    """Get aggregate severity breakdown across all completed analyses.
    
    Uses DB severity_breakdown where available, falls back to
    consolidated.json summary.severity_breakdown for tasks without DB data.
    """
    try:
        severity_totals = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "total": 0,
        }
        
        # Get all completed tasks
        tasks = db.session.query(AnalysisTask).filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED,  # type: ignore[arg-type]
        ).all()
        
        tasks_with_db_severity = set()
        
        for task in tasks:
            breakdown = task.get_severity_breakdown()
            if breakdown:
                tasks_with_db_severity.add(task.task_id)
                for severity, count in breakdown.items():
                    key = severity.lower()
                    if key in severity_totals and key != "total":
                        severity_totals[key] += int(count) if count else 0
        
        # Filesystem fallback for tasks without DB severity data
        if len(tasks_with_db_severity) < len(tasks):
            _add_filesystem_severity(severity_totals, tasks_with_db_severity)
        
        severity_totals["total"] = sum(
            severity_totals[k] for k in ["critical", "high", "medium", "low", "info"]
        )
        
        return severity_totals
        
    except Exception as e:
        logger.error(f"Error getting severity distribution: {e}")
        return {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": 0}


def _add_filesystem_severity(
    severity_totals: Dict[str, int],
    already_counted: set,
) -> None:
    """Add severity counts from consolidated.json for tasks not in DB."""
    import json
    from pathlib import Path
    
    results_root = Path(RESULTS_DIR)
    if not results_root.exists():
        return
    
    for model_dir in results_root.iterdir():
        if not model_dir.is_dir():
            continue
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.startswith("app"):
                continue
            for task_dir in app_dir.iterdir():
                if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                    continue
                
                task_id = task_dir.name.replace("task_", "")
                if task_id in already_counted:
                    continue
                
                consolidated = task_dir / "consolidated.json"
                if not consolidated.exists():
                    continue
                
                try:
                    with open(consolidated, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    breakdown = (data.get("summary") or {}).get("severity_breakdown", {})
                    if breakdown:
                        for severity, count in breakdown.items():
                            key = severity.lower()
                            if key in severity_totals and key != "total":
                                severity_totals[key] += int(count) if count else 0
                except Exception:
                    continue


# ---------------------------------------------------------------------------
# Analysis Trends - Time-Series Data
# ---------------------------------------------------------------------------

def get_analysis_trends(days: int = 30) -> Dict[str, Any]:
    """Get analysis activity trends over specified period.
    
    Returns dict with:
    - dates: list of date labels
    - completed: list of completed counts per day
    - failed: list of failed counts per day
    """
    try:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)
        
        dates = []
        completed = []
        failed = []
        
        current = start_date
        while current <= end_date:
            day_start = datetime.combine(current, datetime.min.time()).replace(tzinfo=timezone.utc)
            day_end = datetime.combine(current, datetime.max.time()).replace(tzinfo=timezone.utc)
            
            # Completed count
            completed_count = db.session.query(func.count(AnalysisTask.id)).filter(
                AnalysisTask.completed_at >= day_start,  # type: ignore[arg-type]
                AnalysisTask.completed_at <= day_end,  # type: ignore[arg-type]
                AnalysisTask.status == AnalysisStatus.COMPLETED  # type: ignore[arg-type]
            ).scalar() or 0
            
            # Failed count
            failed_count = db.session.query(func.count(AnalysisTask.id)).filter(
                AnalysisTask.completed_at >= day_start,  # type: ignore[arg-type]
                AnalysisTask.completed_at <= day_end,  # type: ignore[arg-type]
                AnalysisTask.status == AnalysisStatus.FAILED  # type: ignore[arg-type]
            ).scalar() or 0
            
            dates.append(current.strftime("%m/%d"))
            completed.append(completed_count)
            failed.append(failed_count)
            
            current += timedelta(days=1)
        
        return {
            "dates": dates,
            "completed": completed,
            "failed": failed,
        }
        
    except Exception as e:
        logger.error(f"Error getting analysis trends: {e}")
        return {"dates": [], "completed": [], "failed": []}


# ---------------------------------------------------------------------------
# Model Performance Comparison
# ---------------------------------------------------------------------------

def get_model_comparison() -> List[Dict[str, Any]]:
    """Compare analysis results across different AI models.
    
    Returns list of dicts with:
    - model: model slug
    - app_count: number of apps
    - analysis_count: number of analyses
    - total_findings: total issues found
    - avg_findings: average findings per analysis
    """
    try:
        # Get all distinct models with apps
        models = db.session.query(
            GeneratedApplication.model_slug
        ).distinct().all()
        
        comparisons = []
        
        for (model_slug,) in models:
            if not model_slug:
                continue
                
            # Count apps for this model
            app_count = db.session.query(func.count(GeneratedApplication.id)).filter(
                GeneratedApplication.model_slug == model_slug
            ).scalar() or 0
            
            # Get analysis stats for this model
            model_tasks = db.session.query(AnalysisTask).filter(
                AnalysisTask.target_model == model_slug,
                AnalysisTask.status == AnalysisStatus.COMPLETED  # type: ignore[arg-type]
            ).all()
            
            analysis_count = len(model_tasks)
            total_findings = sum(t.issues_found or 0 for t in model_tasks)
            avg_findings = round(total_findings / analysis_count, 1) if analysis_count > 0 else None
            
            comparisons.append({
                "model": model_slug,
                "app_count": app_count,
                "analysis_count": analysis_count,
                "total_findings": total_findings,
                "avg_findings": avg_findings,
            })
        
        # Sort by analysis count (most active first)
        comparisons.sort(key=lambda x: x["analysis_count"], reverse=True)
        
        return comparisons
        
    except Exception as e:
        logger.error(f"Error getting model comparison: {e}")
        return []


# ---------------------------------------------------------------------------
# Recent Activity
# ---------------------------------------------------------------------------

def get_recent_activity(limit: int = 20) -> List[Dict[str, Any]]:
    """Get most recent analysis activities.
    
    Returns list of dicts with:
    - model: model slug
    - app: app number
    - status: task status
    - analysis_type: type of analysis
    - time_ago: human-readable time since
    """
    try:
        recent_tasks = db.session.query(AnalysisTask).order_by(
            desc(AnalysisTask.created_at)
        ).limit(limit).all()
        
        now = datetime.now(timezone.utc)
        activities = []
        
        for task in recent_tasks:
            # Calculate time ago
            if task.created_at:
                delta = now - task.created_at.replace(tzinfo=timezone.utc) if task.created_at.tzinfo is None else now - task.created_at
                if delta.days > 0:
                    time_ago = f"{delta.days}d ago"
                elif delta.seconds >= 3600:
                    time_ago = f"{delta.seconds // 3600}h ago"
                elif delta.seconds >= 60:
                    time_ago = f"{delta.seconds // 60}m ago"
                else:
                    time_ago = "just now"
            else:
                time_ago = "unknown"
            
            activities.append({
                "task_id": task.task_id,
                "model": task.target_model or "unknown",
                "app": task.target_app_number or 0,
                "status": task.status.value if task.status else "UNKNOWN",
                "analysis_type": task.task_name or "comprehensive",
                "time_ago": time_ago,
                "findings": task.issues_found or 0,
            })
        
        return activities
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return []


# ---------------------------------------------------------------------------

def get_analyzer_health() -> Dict[str, Any]:
    """Get analyzer health status snapshot with aggregate metrics.
    
    Returns dict with:
    - overall_status: 'healthy', 'degraded', or 'unhealthy'
    - services_up: count of healthy services
    - services_total: total services checked
    - analyzers: per-analyzer status dicts
    """
    try:
        from app.services.service_locator import ServiceLocator
        health_service = ServiceLocator.get_health_service()
        if not health_service:
            return {
                "overall_status": "unknown",
                "services_up": 0,
                "services_total": 4,
                "analyzers": {},
            }
        health = health_service.check_all()
        
        analyzer_keys = {
            "static_analyzer",
            "dynamic_analyzer",
            "performance_tester",
            "ai_analyzer",
        }
        analyzers = {
            key: value
            for key, value in health.items()
            if key in analyzer_keys
        }
        
        services_total = len(analyzer_keys)
        services_up = sum(
            1 for v in analyzers.values()
            if isinstance(v, dict) and v.get("status") == "healthy"
        )
        
        if services_up == services_total:
            overall_status = "healthy"
        elif services_up > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return {
            "overall_status": overall_status,
            "services_up": services_up,
            "services_total": services_total,
            "analyzers": analyzers,
        }
    except Exception as exc:
        logger.error(f"Error getting analyzer health: {exc}")
        return {
            "overall_status": "unknown",
            "services_up": 0,
            "services_total": 4,
            "analyzers": {},
        }

def get_tool_effectiveness() -> List[Dict[str, Any]]:
    """Get summary of tool effectiveness across all analyses.
    
    Reads tool data from service snapshot files (static.json, dynamic.json,
    performance.json) inside each task's services/ directory.
    
    Returns list of dicts with:
    - tool: tool name
    - run_count: number of runs
    - total_findings: total findings
    - avg_findings: average findings per run
    - success_rate: percentage successful runs
    """
    try:
        from pathlib import Path
        import json
        
        tool_stats: Dict[str, Dict[str, Any]] = {}
        
        results_root = Path(RESULTS_DIR)
        if not results_root.exists():
            return []
        
        for model_dir in results_root.iterdir():
            if not model_dir.is_dir():
                continue
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith("app"):
                    continue
                    
                for task_dir in app_dir.iterdir():
                    if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                        continue
                    
                    services_dir = task_dir / "services"
                    if not services_dir.is_dir():
                        continue
                    
                    for service_file in services_dir.glob("*.json"):
                        try:
                            with open(service_file, 'r', encoding='utf-8') as f:
                                svc_data = json.load(f)
                        except Exception:
                            continue
                        
                        _extract_tools_from_service(svc_data, service_file.stem, tool_stats)
        
        # Calculate averages and format as list
        result = []
        for tool_name, stats in tool_stats.items():
            stats["success_rate"] = round(
                stats["successful"] / stats["run_count"] * 100, 1
            ) if stats["run_count"] > 0 else 0.0
            
            stats["avg_findings"] = round(
                stats["total_findings"] / stats["run_count"], 1
            ) if stats["run_count"] > 0 else 0.0
            
            del stats["successful"]
            result.append(stats)
        
        result.sort(key=lambda x: x["run_count"], reverse=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting tool effectiveness: {e}")
        return []


def _extract_tools_from_service(
    svc_data: Dict[str, Any],
    service_name: str,
    tool_stats: Dict[str, Dict[str, Any]],
) -> None:
    """Extract tool-level stats from a service snapshot file.
    
    Handles the various nesting formats:
    - static.json: results.{lang}.{tool} or analysis.results.{lang}.{tool}
    - dynamic.json: results.analysis.tool_results.{tool} or results.analysis.tool_runs.{tool}
    - performance.json: results.analysis.tool_results.{tool}
    - ai.json: tools.{tool}
    """
    # Format 1: static analyzer — results.{lang}.{tool}
    results = svc_data.get("results", {})
    if isinstance(results, dict):
        # Check for analysis.results nesting
        analysis = svc_data.get("analysis", {})
        if isinstance(analysis, dict) and "results" in analysis:
            results = analysis["results"]
        
        # Static: results.{language}.{tool}
        for lang_key, lang_data in results.items():
            if isinstance(lang_data, dict):
                # Could be a language group (python, javascript) or nested analysis
                if lang_key == "analysis":
                    # dynamic/performance: results.analysis.tool_results.{tool}
                    tool_results = lang_data.get("tool_results", {})
                    if isinstance(tool_results, dict):
                        for tool_name, tool_data in tool_results.items():
                            if isinstance(tool_data, dict):
                                _record_tool(tool_name, tool_data, tool_stats)
                    # Also check tool_runs
                    tool_runs = lang_data.get("tool_runs", {})
                    if isinstance(tool_runs, dict):
                        for tool_name, tool_data in tool_runs.items():
                            if isinstance(tool_data, dict) and tool_name not in tool_results:
                                _record_tool(tool_name, tool_data, tool_stats)
                elif "tool" in lang_data or "status" in lang_data:
                    # Direct tool entry (e.g., results.bandit at top level)
                    _record_tool(lang_key, lang_data, tool_stats)
                else:
                    # Language group: results.python.bandit, results.javascript.eslint
                    for tool_name, tool_data in lang_data.items():
                        if isinstance(tool_data, dict):
                            _record_tool(tool_name, tool_data, tool_stats)
    
    # Format 2: ai analyzer — tools.{tool}
    tools = svc_data.get("tools", {})
    if isinstance(tools, dict):
        for tool_name, tool_data in tools.items():
            if isinstance(tool_data, dict):
                _record_tool(tool_name, tool_data, tool_stats)


def _record_tool(
    tool_name: str,
    tool_data: Dict[str, Any],
    tool_stats: Dict[str, Dict[str, Any]],
) -> None:
    """Record a single tool's execution data into the aggregate stats."""
    if tool_name not in tool_stats:
        tool_stats[tool_name] = {
            "tool": tool_name,
            "run_count": 0,
            "successful": 0,
            "total_findings": 0,
        }
    
    stats = tool_stats[tool_name]
    stats["run_count"] += 1
    
    status = str(tool_data.get("status", "")).lower()
    if status in ("success", "completed", "no_issues"):
        stats["successful"] += 1
    
    findings = (
        tool_data.get("total_issues", 0)
        or tool_data.get("issue_count", 0)
        or tool_data.get("issues_found", 0)
        or len(tool_data.get("issues", []))
    )
    stats["total_findings"] += int(findings) if findings else 0


# ---------------------------------------------------------------------------
# Quick Stats for Sidebar/Widget
# ---------------------------------------------------------------------------

def get_quick_stats() -> Dict[str, Any]:
    """Get minimal stats for sidebar widgets.
    
    Returns dict with:
    - today_count: analyses today
    - week_count: analyses this week
    - pending_count: pending tasks
    - failed_24h: failed in last 24h
    - most_active_model: most analyzed model
    - last_analysis_ago: time since last analysis
    """
    try:
        now = datetime.now(timezone.utc)
        today_start = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        # Today's analyses
        today_count = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.created_at >= today_start
        ).scalar() or 0
        
        # This week
        week_count = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.created_at >= week_ago
        ).scalar() or 0
        
        # Pending tasks
        pending_count = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.status == AnalysisStatus.PENDING  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Failed in last 24h
        failed_24h = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.completed_at >= day_ago,  # type: ignore[arg-type]
            AnalysisTask.status == AnalysisStatus.FAILED  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Most active model (by task count)
        most_active_result = db.session.query(
            AnalysisTask.target_model,
            func.count(AnalysisTask.id).label('count')
        ).group_by(AnalysisTask.target_model).order_by(
            desc('count')
        ).first()
        most_active_model = most_active_result[0] if most_active_result else None
        
        # Last analysis time
        last_task = db.session.query(AnalysisTask).order_by(
            desc(AnalysisTask.completed_at)  # type: ignore[arg-type]
        ).first()
        
        if last_task and last_task.completed_at:
            delta = now - (last_task.completed_at.replace(tzinfo=timezone.utc) if last_task.completed_at.tzinfo is None else last_task.completed_at)
            if delta.days > 0:
                last_analysis_ago = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                last_analysis_ago = f"{delta.seconds // 3600}h ago"
            elif delta.seconds >= 60:
                last_analysis_ago = f"{delta.seconds // 60}m ago"
            else:
                last_analysis_ago = "just now"
        else:
            last_analysis_ago = None
        
        return {
            "today_count": today_count,
            "week_count": week_count,
            "pending_count": pending_count,
            "failed_24h": failed_24h,
            "most_active_model": most_active_model,
            "last_analysis_ago": last_analysis_ago,
        }
        
    except Exception as e:
        logger.error(f"Error getting quick stats: {e}")
        return {
            "today_count": 0,
            "week_count": 0,
            "pending_count": 0,
            "failed_24h": 0,
            "most_active_model": None,
            "last_analysis_ago": None,
        }


# ---------------------------------------------------------------------------
# Filesystem Metrics
# ---------------------------------------------------------------------------

def get_filesystem_metrics() -> Dict[str, Any]:
    """Get metrics about results storage.
    
    Returns dict with:
    - total_result_files: number of result files
    - total_size_mb: total storage in MB
    - apps_with_results: count of apps that have results
    - model_count: number of models with results
    """
    try:
        from pathlib import Path
        
        results_root = Path(RESULTS_DIR)
        
        if not results_root.exists():
            return {
                "total_result_files": 0,
                "total_size_mb": 0.0,
                "apps_with_results": 0,
                "model_count": 0,
            }
        
        total_files = 0
        total_size = 0
        model_dirs = set()
        app_dirs = set()
        
        for model_dir in results_root.iterdir():
            if not model_dir.is_dir():
                continue
            model_dirs.add(model_dir.name)
            
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith("app"):
                    continue
                app_dirs.add(f"{model_dir.name}/{app_dir.name}")
                
                for f in app_dir.rglob("*"):
                    if f.is_file():
                        total_files += 1
                        total_size += f.stat().st_size
        
        return {
            "total_result_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "apps_with_results": len(app_dirs),
            "model_count": len(model_dirs),
        }
        
    except Exception as e:
        logger.error(f"Error getting filesystem metrics: {e}")
        return {
            "total_result_files": 0,
            "total_size_mb": 0.0,
            "apps_with_results": 0,
            "model_count": 0,
        }


# ---------------------------------------------------------------------------
# Code Generation Stats — Lines of code per model
# ---------------------------------------------------------------------------

def get_code_generation_stats() -> List[Dict[str, Any]]:
    """Get lines-of-code and file counts per model from generated apps.
    
    Scans the generated/apps/ directory tree counting source files.
    
    Returns list of dicts sorted by total_lines descending:
    - model: model slug
    - total_lines: total lines of source code
    - total_files: number of source files
    - avg_lines_per_app: average lines per app
    - app_count: number of app directories
    """
    try:
        from pathlib import Path
        
        CODE_SUFFIXES = {'.py', '.js', '.jsx', '.ts', '.tsx', '.css', '.html'}
        gen_root = Path(GENERATED_APPS_DIR)
        if not gen_root.exists():
            return []
        
        stats = []
        for model_dir in gen_root.iterdir():
            if not model_dir.is_dir():
                continue
            total_lines = 0
            total_files = 0
            app_count = 0
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith("app"):
                    continue
                app_count += 1
                for f in app_dir.rglob("*"):
                    if f.is_file() and f.suffix in CODE_SUFFIXES:
                        try:
                            total_lines += sum(1 for _ in open(f, 'r', encoding='utf-8', errors='ignore'))
                            total_files += 1
                        except Exception:
                            pass
            
            if app_count > 0:
                stats.append({
                    "model": model_dir.name,
                    "total_lines": total_lines,
                    "total_files": total_files,
                    "avg_lines_per_app": round(total_lines / app_count),
                    "app_count": app_count,
                })
        
        stats.sort(key=lambda x: x["total_lines"], reverse=True)
        return stats
    except Exception as e:
        logger.error(f"Error getting code generation stats: {e}")
        return []


# ---------------------------------------------------------------------------
# Top Findings — Most common issues from SARIF files
# ---------------------------------------------------------------------------

def get_top_findings(limit: int = 10) -> List[Dict[str, Any]]:
    """Get most frequently occurring findings across all analyses.
    
    Reads SARIF files to aggregate rule/issue occurrences.
    
    Returns list of dicts:
    - rule_id: the rule identifier
    - tool: tool that reported it
    - level: severity level (error, warning, note)
    - count: number of occurrences
    """
    try:
        import json
        from pathlib import Path
        from collections import Counter
        
        results_root = Path(RESULTS_DIR)
        if not results_root.exists():
            return []
        
        rule_counter: Counter = Counter()
        rule_meta: Dict[str, Dict[str, str]] = {}
        
        for sarif_file in results_root.rglob("sarif/*.sarif.json"):
            try:
                with open(sarif_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for run in data.get("runs", []):
                    tool_name = (run.get("tool", {}).get("driver", {}).get("name", "unknown"))
                    for result in run.get("results", []):
                        rule_id = result.get("ruleId", "unknown")
                        level = result.get("level", "note")
                        key = f"{tool_name}|{rule_id}"
                        rule_counter[key] += 1
                        if key not in rule_meta:
                            rule_meta[key] = {"tool": tool_name, "level": level}
            except Exception:
                continue
        
        top = []
        for key, count in rule_counter.most_common(limit):
            meta = rule_meta.get(key, {})
            _, rule_id = key.split("|", 1)
            top.append({
                "rule_id": rule_id,
                "tool": meta.get("tool", "unknown"),
                "level": meta.get("level", "note"),
                "count": count,
            })
        
        return top
    except Exception as e:
        logger.error(f"Error getting top findings: {e}")
        return []


# ---------------------------------------------------------------------------
# Model Leaderboard — Ranked by key metrics
# ---------------------------------------------------------------------------

def get_model_leaderboard() -> Dict[str, Any]:
    """Get model rankings across several dimensions.
    
    Returns dict with:
    - most_lines: model with most generated code
    - fewest_issues: model with fewest analysis issues
    - most_issues: model with most issues
    - fastest_analysis: model whose analyses completed fastest on average
    - slowest_analysis: model whose analyses took longest on average
    - best_success_rate: model with highest analysis success rate
    """
    try:
        # Issues & duration per model
        model_tasks = db.session.query(
            AnalysisTask.target_model,
            func.sum(AnalysisTask.issues_found).label("total_issues"),
            func.count(AnalysisTask.id).label("task_count"),
            func.avg(AnalysisTask.actual_duration).label("avg_duration"),
        ).filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED,  # type: ignore[arg-type]
            AnalysisTask.target_model.isnot(None),
        ).group_by(AnalysisTask.target_model).all()
        
        # Success rates
        all_tasks = db.session.query(
            AnalysisTask.target_model,
            AnalysisTask.status,
            func.count(AnalysisTask.id).label("cnt"),
        ).filter(
            AnalysisTask.target_model.isnot(None),
            AnalysisTask.status.in_([AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]),  # type: ignore[union-attr]
        ).group_by(AnalysisTask.target_model, AnalysisTask.status).all()
        
        completed_by_model: Dict[str, int] = {}
        total_by_model: Dict[str, int] = {}
        for model, status, cnt in all_tasks:
            total_by_model[model] = total_by_model.get(model, 0) + cnt
            if status == AnalysisStatus.COMPLETED:
                completed_by_model[model] = completed_by_model.get(model, 0) + cnt
        
        success_rates = {
            m: round(completed_by_model.get(m, 0) / t * 100, 1) if t > 0 else 0
            for m, t in total_by_model.items()
        }
        
        # Code line counts
        code_stats = get_code_generation_stats()
        
        leaderboard: Dict[str, Any] = {}
        
        # Most lines
        if code_stats:
            top = code_stats[0]
            leaderboard["most_lines"] = {"model": top["model"], "value": f"{top['total_lines']:,} lines"}
            bottom = code_stats[-1]
            leaderboard["fewest_lines"] = {"model": bottom["model"], "value": f"{bottom['total_lines']:,} lines"}
        
        if model_tasks:
            # Fewest / most issues
            sorted_by_issues = sorted(model_tasks, key=lambda x: (x.total_issues or 0))
            fewest = sorted_by_issues[0]
            most = sorted_by_issues[-1]
            leaderboard["fewest_issues"] = {"model": fewest.target_model, "value": str(fewest.total_issues or 0)}
            leaderboard["most_issues"] = {"model": most.target_model, "value": str(most.total_issues or 0)}
            
            # Fastest / slowest analysis
            with_duration = [t for t in model_tasks if t.avg_duration is not None]
            if with_duration:
                sorted_by_dur = sorted(with_duration, key=lambda x: x.avg_duration)
                fastest = sorted_by_dur[0]
                slowest = sorted_by_dur[-1]
                leaderboard["fastest_analysis"] = {
                    "model": fastest.target_model,
                    "value": f"{fastest.avg_duration:.0f}s avg",
                }
                leaderboard["slowest_analysis"] = {
                    "model": slowest.target_model,
                    "value": f"{slowest.avg_duration:.0f}s avg",
                }
        
        # Best success rate
        if success_rates:
            best_model = max(success_rates, key=success_rates.get)  # type: ignore[arg-type]
            leaderboard["best_success_rate"] = {
                "model": best_model,
                "value": f"{success_rates[best_model]}%",
            }
        
        return leaderboard
    except Exception as e:
        logger.error(f"Error getting model leaderboard: {e}")
        return {}


# ---------------------------------------------------------------------------
# Legacy/Backward Compatibility Aliases
# ---------------------------------------------------------------------------
# These functions provide backward compatibility with the dashboard API
# that expects the old statistics_service interface

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    'get_system_overview',
    'get_severity_distribution',
    'get_analysis_trends',
    'get_model_comparison',
    'get_recent_activity',
    'get_analyzer_health',
    'get_tool_effectiveness',
    'get_quick_stats',
    'get_filesystem_metrics',
    'get_code_generation_stats',
    'get_top_findings',
    'get_model_leaderboard',
]
