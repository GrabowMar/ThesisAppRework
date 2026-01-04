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
    ModelCapability, 
    AnalysisTask,
)
from ..constants import AnalysisStatus
from ..paths import RESULTS_DIR

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
    """Get aggregate severity breakdown across all completed analyses."""
    try:
        severity_totals = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "total": 0,
        }
        
        # Get all completed tasks with severity data
        tasks = db.session.query(AnalysisTask).filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED,  # type: ignore[arg-type]
            AnalysisTask.severity_breakdown.isnot(None)  # type: ignore[union-attr]
        ).all()
        
        for task in tasks:
            breakdown = task.get_severity_breakdown()
            if breakdown:
                for severity, count in breakdown.items():
                    key = severity.lower()
                    if key in severity_totals and key != "total":
                        severity_totals[key] += int(count) if count else 0
        
        # Calculate total
        severity_totals["total"] = sum(
            severity_totals[k] for k in ["critical", "high", "medium", "low", "info"]
        )
        
        return severity_totals
        
    except Exception as e:
        logger.error(f"Error getting severity distribution: {e}")
        return {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": 0}


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
    - avg_score: average score (if available)
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
            
            # Calculate average score (placeholder - could be based on severity weights)
            avg_score = None
            if analysis_count > 0 and total_findings >= 0:
                # Simple score: fewer findings = higher score
                findings_per_analysis = total_findings / analysis_count
                avg_score = max(0, 100 - (findings_per_analysis * 2))  # Rough scoring
            
            comparisons.append({
                "model": model_slug,
                "app_count": app_count,
                "analysis_count": analysis_count,
                "total_findings": total_findings,
                "avg_score": round(avg_score, 1) if avg_score is not None else None,
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
# Analyzer Health Status
# ---------------------------------------------------------------------------

def get_analyzer_health() -> Dict[str, Any]:
    """Get analyzer service health indicators.
    
    Returns dict with:
    - overall_status: healthy/degraded/critical
    - services_up: count of healthy services
    - services_total: total service count
    - queue_depth: pending task count
    """
    try:
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        
        # Recent task performance
        recent_completed = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.completed_at >= one_hour_ago,  # type: ignore[arg-type]
            AnalysisTask.status == AnalysisStatus.COMPLETED  # type: ignore[arg-type]
        ).scalar() or 0
        
        recent_failed = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.completed_at >= one_hour_ago,  # type: ignore[arg-type]
            AnalysisTask.status == AnalysisStatus.FAILED  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Stuck tasks (running for more than 1 hour)
        stuck_tasks = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.status == AnalysisStatus.RUNNING,  # type: ignore[arg-type]
            AnalysisTask.started_at < one_hour_ago  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Queue depth (pending tasks)
        queue_depth = db.session.query(func.count(AnalysisTask.id)).filter(
            AnalysisTask.status == AnalysisStatus.PENDING  # type: ignore[arg-type]
        ).scalar() or 0
        
        # Determine health status
        overall_status = "healthy"
        services_total = 4  # static, dynamic, performance, ai analyzers
        services_up = 4  # Assume healthy unless we detect issues
        
        if stuck_tasks > 0:
            overall_status = "degraded"
            services_up = 3
        
        if queue_depth > 10:
            overall_status = "degraded"
        
        if recent_failed > recent_completed and recent_completed + recent_failed > 0:
            overall_status = "critical"
            services_up = 2
        
        return {
            "overall_status": overall_status,
            "services_up": services_up,
            "services_total": services_total,
            "queue_depth": queue_depth,
            "stuck_tasks": stuck_tasks,
            "recent_completed": recent_completed,
            "recent_failed": recent_failed,
        }
        
    except Exception as e:
        logger.error(f"Error getting analyzer health: {e}")
        return {
            "overall_status": "unknown",
            "services_up": 0,
            "services_total": 4,
            "queue_depth": 0,
        }


# ---------------------------------------------------------------------------
# Tool Effectiveness Summary
# ---------------------------------------------------------------------------

def get_tool_effectiveness() -> List[Dict[str, Any]]:
    """Get summary of tool effectiveness across all analyses.
    
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
        
        # Scan results directory for tool data
        results_root = Path(RESULTS_DIR)
        if not results_root.exists():
            return []
        
        for model_dir in results_root.iterdir():
            if not model_dir.is_dir():
                continue
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith("app"):
                    continue
                    
                # Check task directories
                for task_dir in app_dir.iterdir():
                    if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                        continue
                    
                    # Find main result JSON
                    json_files = [f for f in task_dir.glob("*.json") if f.name != "manifest.json"]
                    if not json_files:
                        continue
                    
                    try:
                        with open(json_files[0], 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # Extract tool data from services
                        tools_flat = data.get('tools', {})
                        
                        # Process flat tools structure first
                        for tool_name, tool_data in tools_flat.items():
                            if not isinstance(tool_data, dict):
                                continue
                            
                            if tool_name not in tool_stats:
                                tool_stats[tool_name] = {
                                    "tool": tool_name,
                                    "run_count": 0,
                                    "successful": 0,
                                    "total_findings": 0,
                                }
                            
                            stats = tool_stats[tool_name]
                            stats["run_count"] += 1
                            
                            status = tool_data.get("status", "").lower()
                            if status in ("success", "completed", "no_issues"):
                                stats["successful"] += 1
                            
                            findings = tool_data.get("total_issues", 0) or tool_data.get("issues_found", 0) or len(tool_data.get("issues", []))
                            stats["total_findings"] += findings
                                
                    except Exception:
                        continue
        
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
        
        # Sort by run count
        result.sort(key=lambda x: x["run_count"], reverse=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting tool effectiveness: {e}")
        return []


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
# Legacy/Backward Compatibility Aliases
# ---------------------------------------------------------------------------
# These functions provide backward compatibility with the dashboard API
# that expects the old statistics_service interface

def get_application_statistics() -> Dict[str, Any]:
    """Legacy: Get application statistics (maps to system_overview)."""
    overview = get_system_overview()
    return {
        "total": overview.get("total_apps", 0),
        "by_model": {},  # Simplified
        "recent_count": overview.get("total_tasks", 0),
    }

def get_model_statistics() -> Dict[str, Any]:
    """Legacy: Get model statistics (maps to model_comparison)."""
    models = get_model_comparison()
    return {
        "total": len(models),
        "models": models,
    }

def get_analysis_statistics() -> Dict[str, Any]:
    """Legacy: Get analysis statistics."""
    overview = get_system_overview()
    severity = get_severity_distribution()
    return {
        "total_tasks": overview.get("total_tasks", 0),
        "completed": overview.get("completed_count", 0),
        "failed": overview.get("failed_count", 0),
        "success_rate": overview.get("success_rate", 0.0),
        "total_findings": severity.get("total", 0),
    }

def get_recent_statistics() -> Dict[str, Any]:
    """Legacy: Get recent statistics."""
    quick = get_quick_stats()
    return {
        "today": quick.get("today_count", 0),
        "week": quick.get("week_count", 0),
    }

def get_model_distribution() -> Dict[str, Any]:
    """Legacy: Get model distribution."""
    models = get_model_comparison()
    return {
        "labels": [m.get("model", "") for m in models[:10]],
        "values": [m.get("analysis_count", 0) for m in models[:10]],
    }

def get_generation_trends() -> Dict[str, Any]:
    """Legacy: Get generation trends."""
    trends = get_analysis_trends(days=14)
    return trends

def get_analysis_summary() -> Dict[str, Any]:
    """Legacy: Get analysis summary."""
    severity = get_severity_distribution()
    return {
        "severity": severity,
        "total": severity.get("total", 0),
    }

def export_statistics() -> Dict[str, Any]:
    """Legacy: Export all statistics as a single dict."""
    return {
        "overview": get_system_overview(),
        "severity": get_severity_distribution(),
        "health": get_analyzer_health(),
        "models": get_model_comparison(),
        "tools": get_tool_effectiveness(),
        "quick_stats": get_quick_stats(),
        "filesystem": get_filesystem_metrics(),
    }

def get_generation_statistics_by_models(model_slugs: List[str]) -> Dict[str, Any]:
    """Legacy: Get generation statistics filtered by model slugs."""
    all_models = get_model_comparison()
    filtered = [m for m in all_models if m.get("model") in model_slugs]
    return {
        "models": filtered,
        "total_apps": sum(m.get("app_count", 0) for m in filtered),
        "total_analyses": sum(m.get("analysis_count", 0) for m in filtered),
    }


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # New API
    'get_system_overview',
    'get_severity_distribution',
    'get_analysis_trends',
    'get_model_comparison',
    'get_recent_activity',
    'get_analyzer_health',
    'get_tool_effectiveness',
    'get_quick_stats',
    'get_filesystem_metrics',
    # Legacy API (backward compatibility)
    'get_application_statistics',
    'get_model_statistics',
    'get_analysis_statistics',
    'get_recent_statistics',
    'get_model_distribution',
    'get_generation_trends',
    'get_analysis_summary',
    'export_statistics',
    'get_generation_statistics_by_models',
]
