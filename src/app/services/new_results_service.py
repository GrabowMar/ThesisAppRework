"""
Results Preview and Management Service
=====================================

Comprehensive system for managing, previewing, and analyzing analysis results.
Supports multiple result formats, filtering, aggregation, and export functionality.
"""

import logging
import json
import csv
import io
import zipfile
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import base64

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func, text

from ..extensions import db
from ..models import (
    AnalysisTask, BatchAnalysis, AnalysisResult, AnalyzerConfiguration,
    AnalysisStatus, AnalysisType, Priority, BatchStatus
)


logger = logging.getLogger(__name__)


class ResultFormat(Enum):
    """Supported result export formats."""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    XML = "xml"


class SeverityLevel(Enum):
    """Severity levels for findings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResultSummary:
    """Summary statistics for analysis results."""
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_findings: int
    findings_by_severity: Dict[str, int]
    findings_by_type: Dict[str, int]
    average_score: float
    execution_time_total: int
    models_analyzed: List[str]
    analysis_types_used: List[str]


@dataclass
class FilterCriteria:
    """Criteria for filtering analysis results."""
    status: Optional[List[str]] = None
    analysis_type: Optional[List[str]] = None
    model_slug: Optional[List[str]] = None
    severity: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    has_findings: Optional[bool] = None
    batch_id: Optional[int] = None


class ResultsQueryService:
    """Service for querying and filtering analysis results."""
    
    @staticmethod
    def get_task_results(
        task_id: str,
        include_detailed_results: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get comprehensive results for a specific task."""
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            return None
        
        result = task.to_dict()
        
        if include_detailed_results:
            # Get detailed results
            detailed_results = AnalysisResult.query.filter_by(task_id=task.id).all()
            result['detailed_results'] = [r.to_dict() for r in detailed_results]
            
            # Calculate additional metrics
            if detailed_results:
                result['findings_summary'] = ResultsQueryService._calculate_findings_summary(detailed_results)
        
        return result
    
    @staticmethod
    def get_batch_results(
        batch_id: str,
        include_task_details: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get comprehensive results for a batch."""
        batch = BatchAnalysis.query.filter_by(batch_id=batch_id).first()
        if not batch:
            return None
        
        result = batch.to_dict()
        
        # Get task summaries
        tasks = batch.tasks
        result['task_summaries'] = []
        
        for task in tasks:
            task_summary = {
                'task_id': task.task_id,
                'analysis_type': task.analysis_type,
                'model_slug': task.model_slug,
                'app_number': task.app_number,
                'status': task.status,
                'progress_percentage': task.progress_percentage,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'error_message': task.error_message
            }
            
            if include_task_details:
                task_summary['results'] = task.get_results()
                task_summary['config'] = task.get_config()
            
            result['task_summaries'].append(task_summary)
        
        # Calculate batch-level statistics
        result['batch_statistics'] = ResultsQueryService._calculate_batch_statistics(tasks)
        
        return result
    
    @staticmethod
    def list_results(
        filters: FilterCriteria,
        limit: int = 100,
        offset: int = 0,
        order_by: str = 'created_at',
        order_desc: bool = True
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List analysis results with filtering and pagination."""
        query = AnalysisTask.query
        
        # Apply filters
        if filters.status:
            query = query.filter(AnalysisTask.status.in_(filters.status))
        
        if filters.analysis_type:
            query = query.filter(AnalysisTask.analysis_type.in_(filters.analysis_type))
        
        if filters.model_slug:
            query = query.filter(AnalysisTask.model_slug.in_(filters.model_slug))
        
        if filters.date_from:
            query = query.filter(AnalysisTask.created_at >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(AnalysisTask.created_at <= filters.date_to)
        
        if filters.batch_id:
            query = query.filter(AnalysisTask.batch_id == filters.batch_id)
        
        # Apply score filters (requires JSON operations)
        if filters.score_min is not None or filters.score_max is not None:
            # This would use JSON operations on the results_json field
            # Implementation depends on database (PostgreSQL, MySQL, etc.)
            pass
        
        # Count total before pagination
        total_count = query.count()
        
        # Apply ordering
        if hasattr(AnalysisTask, order_by):
            order_col = getattr(AnalysisTask, order_by)
            if order_desc:
                query = query.order_by(desc(order_col))
            else:
                query = query.order_by(asc(order_col))
        
        # Apply pagination
        tasks = query.offset(offset).limit(limit).all()
        
        # Convert to dictionaries
        results = []
        for task in tasks:
            task_dict = task.to_dict()
            # Add summary information
            task_dict['findings_count'] = AnalysisResult.query.filter_by(task_id=task.id).count()
            results.append(task_dict)
        
        return results, total_count
    
    @staticmethod
    def search_results(
        search_term: str,
        search_fields: List[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search results by text content."""
        if search_fields is None:
            search_fields = ['title', 'description', 'file_path', 'recommendation']
        
        # Build search query
        search_conditions = []
        for field in search_fields:
            if hasattr(AnalysisResult, field):
                column = getattr(AnalysisResult, field)
                search_conditions.append(column.ilike(f'%{search_term}%'))
        
        if not search_conditions:
            return []
        
        # Execute search
        results = AnalysisResult.query.filter(
            or_(*search_conditions)
        ).limit(limit).all()
        
        # Group by task and return
        task_results = {}
        for result in results:
            task_id = result.task_id
            if task_id not in task_results:
                task = AnalysisTask.query.get(task_id)
                if task:
                    task_results[task_id] = {
                        'task': task.to_dict(),
                        'matching_results': []
                    }
            
            if task_id in task_results:
                task_results[task_id]['matching_results'].append(result.to_dict())
        
        return list(task_results.values())
    
    @staticmethod
    def _calculate_findings_summary(results: List[AnalysisResult]) -> Dict[str, Any]:
        """Calculate summary statistics for findings."""
        if not results:
            return {}
        
        severity_counts = {}
        category_counts = {}
        total_score = 0
        score_count = 0
        
        for result in results:
            # Count by severity
            if result.severity:
                severity_counts[result.severity] = severity_counts.get(result.severity, 0) + 1
            
            # Count by category
            if result.category:
                category_counts[result.category] = category_counts.get(result.category, 0) + 1
            
            # Calculate average score
            if result.score is not None:
                total_score += result.score
                score_count += 1
        
        average_score = total_score / score_count if score_count > 0 else None
        
        return {
            'total_findings': len(results),
            'severity_counts': severity_counts,
            'category_counts': category_counts,
            'average_score': round(average_score, 2) if average_score else None,
            'has_high_severity': any(r.severity in ['high', 'critical'] for r in results),
            'unique_files': len(set(r.file_path for r in results if r.file_path))
        }
    
    @staticmethod
    def _calculate_batch_statistics(tasks: List[AnalysisTask]) -> Dict[str, Any]:
        """Calculate statistics for a batch of tasks."""
        if not tasks:
            return {}
        
        # Status counts
        status_counts = {}
        for task in tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
        
        # Type counts
        type_counts = {}
        for task in tasks:
            type_counts[task.analysis_type] = type_counts.get(task.analysis_type, 0) + 1
        
        # Model counts
        model_counts = {}
        for task in tasks:
            model_counts[task.model_slug] = model_counts.get(task.model_slug, 0) + 1
        
        # Timing statistics
        completed_tasks = [t for t in tasks if t.status == AnalysisStatus.COMPLETED.value and t.actual_duration]
        
        if completed_tasks:
            durations = [t.actual_duration for t in completed_tasks]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            total_duration = sum(durations)
        else:
            avg_duration = min_duration = max_duration = total_duration = 0
        
        return {
            'total_tasks': len(tasks),
            'status_counts': status_counts,
            'type_counts': type_counts,
            'model_counts': model_counts,
            'timing_stats': {
                'average_duration': round(avg_duration, 1) if avg_duration else 0,
                'min_duration': min_duration,
                'max_duration': max_duration,
                'total_duration': total_duration,
                'completed_tasks_count': len(completed_tasks)
            },
            'unique_models': len(model_counts),
            'unique_types': len(type_counts),
            'success_rate': (
                status_counts.get(AnalysisStatus.COMPLETED.value, 0) / len(tasks) * 100
                if tasks else 0
            )
        }


class ResultsAggregationService:
    """Service for aggregating and summarizing results across multiple analyses."""
    
    @staticmethod
    def get_dashboard_summary(
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get high-level dashboard summary."""
        if not date_from:
            date_from = datetime.now(timezone.utc) - timedelta(days=30)
        if not date_to:
            date_to = datetime.now(timezone.utc)
        
        # Query tasks in date range
        tasks = AnalysisTask.query.filter(
            and_(
                AnalysisTask.created_at >= date_from,
                AnalysisTask.created_at <= date_to
            )
        ).all()
        
        # Query batches in date range
        batches = BatchAnalysis.query.filter(
            and_(
                BatchAnalysis.created_at >= date_from,
                BatchAnalysis.created_at <= date_to
            )
        ).all()
        
        # Calculate summary
        task_summary = ResultsQueryService._calculate_batch_statistics(tasks)
        
        # Recent activity
        recent_tasks = AnalysisTask.query.order_by(
            AnalysisTask.created_at.desc()
        ).limit(10).all()
        
        recent_batches = BatchAnalysis.query.order_by(
            BatchAnalysis.created_at.desc()
        ).limit(5).all()
        
        return {
            'date_range': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'task_summary': task_summary,
            'batch_summary': {
                'total_batches': len(batches),
                'active_batches': len([b for b in batches if b.is_running]),
                'completed_batches': len([b for b in batches if b.status == BatchStatus.COMPLETED.value])
            },
            'recent_activity': {
                'recent_tasks': [t.to_dict() for t in recent_tasks],
                'recent_batches': [b.to_dict() for b in recent_batches]
            },
            'system_health': {
                'total_analyzers': 5,  # Mock data
                'healthy_analyzers': 5,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
        }
    
    @staticmethod
    def get_trend_analysis(
        metric: str = 'task_count',
        period: str = 'daily',
        days: int = 30
    ) -> Dict[str, Any]:
        """Get trend analysis for specified metric and period."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Generate date range
        if period == 'daily':
            date_points = [start_date + timedelta(days=i) for i in range(days + 1)]
        elif period == 'weekly':
            weeks = days // 7
            date_points = [start_date + timedelta(weeks=i) for i in range(weeks + 1)]
        else:  # hourly
            hours = min(days * 24, 168)  # Limit to 1 week for hourly
            date_points = [start_date + timedelta(hours=i) for i in range(hours + 1)]
        
        # Calculate metric for each point
        trend_data = []
        for date_point in date_points:
            if period == 'daily':
                next_date = date_point + timedelta(days=1)
            elif period == 'weekly':
                next_date = date_point + timedelta(weeks=1)
            else:
                next_date = date_point + timedelta(hours=1)
            
            # Query data for this period
            tasks_in_period = AnalysisTask.query.filter(
                and_(
                    AnalysisTask.created_at >= date_point,
                    AnalysisTask.created_at < next_date
                )
            ).all()
            
            # Calculate metric
            if metric == 'task_count':
                value = len(tasks_in_period)
            elif metric == 'success_rate':
                completed = len([t for t in tasks_in_period if t.status == AnalysisStatus.COMPLETED.value])
                value = (completed / len(tasks_in_period) * 100) if tasks_in_period else 0
            elif metric == 'avg_duration':
                completed = [t for t in tasks_in_period if t.actual_duration]
                value = (sum(t.actual_duration for t in completed) / len(completed)) if completed else 0
            else:
                value = 0
            
            trend_data.append({
                'date': date_point.isoformat(),
                'value': round(value, 2)
            })
        
        return {
            'metric': metric,
            'period': period,
            'days': days,
            'data': trend_data,
            'summary': {
                'total_points': len(trend_data),
                'avg_value': round(sum(p['value'] for p in trend_data) / len(trend_data), 2) if trend_data else 0,
                'max_value': max(p['value'] for p in trend_data) if trend_data else 0,
                'min_value': min(p['value'] for p in trend_data) if trend_data else 0
            }
        }
    
    @staticmethod
    def get_comparison_analysis(
        comparison_type: str = 'model_performance',
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get comparative analysis across different dimensions."""
        if comparison_type == 'model_performance':
            return ResultsAggregationService._compare_model_performance(limit)
        elif comparison_type == 'analysis_type_efficiency':
            return ResultsAggregationService._compare_analysis_types(limit)
        elif comparison_type == 'batch_performance':
            return ResultsAggregationService._compare_batch_performance(limit)
        else:
            return {'error': f'Unknown comparison type: {comparison_type}'}
    
    @staticmethod
    def _compare_model_performance(limit: int) -> Dict[str, Any]:
        """Compare performance across different models."""
        # Group tasks by model
        model_stats = {}
        
        tasks = AnalysisTask.query.limit(1000).all()  # Limit for performance
        
        for task in tasks:
            model = task.model_slug
            if model not in model_stats:
                model_stats[model] = {
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'failed_tasks': 0,
                    'total_duration': 0,
                    'total_findings': 0
                }
            
            stats = model_stats[model]
            stats['total_tasks'] += 1
            
            if task.status == AnalysisStatus.COMPLETED.value:
                stats['completed_tasks'] += 1
                if task.actual_duration:
                    stats['total_duration'] += task.actual_duration
                
                # Count findings (would need to query AnalysisResult)
                findings_count = AnalysisResult.query.filter_by(task_id=task.id).count()
                stats['total_findings'] += findings_count
            elif task.status == AnalysisStatus.FAILED.value:
                stats['failed_tasks'] += 1
        
        # Calculate derived metrics
        comparison_data = []
        for model, stats in model_stats.items():
            if stats['total_tasks'] > 0:
                success_rate = stats['completed_tasks'] / stats['total_tasks'] * 100
                avg_duration = stats['total_duration'] / stats['completed_tasks'] if stats['completed_tasks'] > 0 else 0
                avg_findings = stats['total_findings'] / stats['completed_tasks'] if stats['completed_tasks'] > 0 else 0
                
                comparison_data.append({
                    'model': model,
                    'total_tasks': stats['total_tasks'],
                    'success_rate': round(success_rate, 1),
                    'avg_duration': round(avg_duration, 1),
                    'avg_findings': round(avg_findings, 1),
                    'total_findings': stats['total_findings']
                })
        
        # Sort by success rate (descending)
        comparison_data.sort(key=lambda x: x['success_rate'], reverse=True)
        
        return {
            'comparison_type': 'model_performance',
            'data': comparison_data[:limit],
            'summary': {
                'total_models': len(comparison_data),
                'best_model': comparison_data[0]['model'] if comparison_data else None,
                'avg_success_rate': round(sum(d['success_rate'] for d in comparison_data) / len(comparison_data), 1) if comparison_data else 0
            }
        }
    
    @staticmethod
    def _compare_analysis_types(limit: int) -> Dict[str, Any]:
        """Compare efficiency across analysis types."""
        type_stats = {}
        
        tasks = AnalysisTask.query.limit(1000).all()
        
        for task in tasks:
            analysis_type = task.analysis_type
            if analysis_type not in type_stats:
                type_stats[analysis_type] = {
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'total_duration': 0,
                    'total_findings': 0
                }
            
            stats = type_stats[analysis_type]
            stats['total_tasks'] += 1
            
            if task.status == AnalysisStatus.COMPLETED.value:
                stats['completed_tasks'] += 1
                if task.actual_duration:
                    stats['total_duration'] += task.actual_duration
                
                findings_count = AnalysisResult.query.filter_by(task_id=task.id).count()
                stats['total_findings'] += findings_count
        
        # Calculate metrics
        comparison_data = []
        for analysis_type, stats in type_stats.items():
            if stats['total_tasks'] > 0:
                avg_duration = stats['total_duration'] / stats['completed_tasks'] if stats['completed_tasks'] > 0 else 0
                findings_per_minute = (stats['total_findings'] / (stats['total_duration'] / 60)) if stats['total_duration'] > 0 else 0
                
                comparison_data.append({
                    'analysis_type': analysis_type,
                    'total_tasks': stats['total_tasks'],
                    'avg_duration': round(avg_duration, 1),
                    'total_findings': stats['total_findings'],
                    'findings_per_minute': round(findings_per_minute, 2)
                })
        
        # Sort by efficiency (findings per minute)
        comparison_data.sort(key=lambda x: x['findings_per_minute'], reverse=True)
        
        return {
            'comparison_type': 'analysis_type_efficiency',
            'data': comparison_data[:limit],
            'summary': {
                'most_efficient_type': comparison_data[0]['analysis_type'] if comparison_data else None,
                'avg_findings_per_minute': round(sum(d['findings_per_minute'] for d in comparison_data) / len(comparison_data), 2) if comparison_data else 0
            }
        }
    
    @staticmethod
    def _compare_batch_performance(limit: int) -> Dict[str, Any]:
        """Compare performance across batch analyses."""
        batches = BatchAnalysis.query.order_by(BatchAnalysis.created_at.desc()).limit(limit).all()
        
        comparison_data = []
        for batch in batches:
            batch_dict = batch.to_dict()
            batch_dict['efficiency_score'] = (
                batch.progress_percentage * (batch.completed_tasks / max(batch.total_tasks, 1))
            )
            comparison_data.append(batch_dict)
        
        # Sort by efficiency score
        comparison_data.sort(key=lambda x: x['efficiency_score'], reverse=True)
        
        return {
            'comparison_type': 'batch_performance',
            'data': comparison_data,
            'summary': {
                'total_batches': len(comparison_data),
                'most_efficient_batch': comparison_data[0]['name'] if comparison_data else None,
                'avg_efficiency': round(sum(d['efficiency_score'] for d in comparison_data) / len(comparison_data), 1) if comparison_data else 0
            }
        }


class ResultsExportService:
    """Service for exporting analysis results in various formats."""
    
    @staticmethod
    def export_task_results(
        task_id: str,
        format: ResultFormat = ResultFormat.JSON,
        include_detailed: bool = True
    ) -> Tuple[bytes, str, str]:
        """Export results for a single task."""
        task_results = ResultsQueryService.get_task_results(task_id, include_detailed)
        if not task_results:
            raise ValueError(f"Task not found: {task_id}")
        
        filename = f"analysis_results_{task_id}"
        
        if format == ResultFormat.JSON:
            content = json.dumps(task_results, indent=2, default=str).encode('utf-8')
            mimetype = 'application/json'
            filename += '.json'
        elif format == ResultFormat.CSV:
            content = ResultsExportService._export_csv([task_results])
            mimetype = 'text/csv'
            filename += '.csv'
        elif format == ResultFormat.HTML:
            content = ResultsExportService._export_html(task_results, 'Task Results').encode('utf-8')
            mimetype = 'text/html'
            filename += '.html'
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        return content, filename, mimetype
    
    @staticmethod
    def export_batch_results(
        batch_id: str,
        format: ResultFormat = ResultFormat.JSON,
        include_task_details: bool = False
    ) -> Tuple[bytes, str, str]:
        """Export results for an entire batch."""
        batch_results = ResultsQueryService.get_batch_results(batch_id, include_task_details)
        if not batch_results:
            raise ValueError(f"Batch not found: {batch_id}")
        
        filename = f"batch_results_{batch_id}"
        
        if format == ResultFormat.JSON:
            content = json.dumps(batch_results, indent=2, default=str).encode('utf-8')
            mimetype = 'application/json'
            filename += '.json'
        elif format == ResultFormat.CSV:
            # Export task summaries as CSV
            content = ResultsExportService._export_batch_csv(batch_results)
            mimetype = 'text/csv'
            filename += '.csv'
        elif format == ResultFormat.HTML:
            content = ResultsExportService._export_html(batch_results, 'Batch Results').encode('utf-8')
            mimetype = 'text/html'
            filename += '.html'
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        return content, filename, mimetype
    
    @staticmethod
    def export_multiple_results(
        task_ids: List[str],
        format: ResultFormat = ResultFormat.JSON
    ) -> Tuple[bytes, str, str]:
        """Export results for multiple tasks as a ZIP archive."""
        if not task_ids:
            raise ValueError("No task IDs provided")
        
        # Create ZIP archive in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for task_id in task_ids:
                try:
                    content, filename, _ = ResultsExportService.export_task_results(
                        task_id, format, include_detailed=True
                    )
                    zip_file.writestr(filename, content)
                except Exception as e:
                    logger.error(f"Failed to export task {task_id}: {e}")
                    # Add error file
                    error_content = f"Error exporting task {task_id}: {str(e)}"
                    zip_file.writestr(f"ERROR_{task_id}.txt", error_content.encode('utf-8'))
        
        zip_buffer.seek(0)
        content = zip_buffer.getvalue()
        filename = f"analysis_results_{len(task_ids)}_tasks.zip"
        mimetype = 'application/zip'
        
        return content, filename, mimetype
    
    @staticmethod
    def _export_csv(task_results_list: List[Dict[str, Any]]) -> bytes:
        """Export task results to CSV format."""
        csv_buffer = io.StringIO()
        
        # Define CSV columns
        columns = [
            'task_id', 'analysis_type', 'model_slug', 'app_number', 'status',
            'progress_percentage', 'created_at', 'started_at', 'completed_at',
            'actual_duration', 'error_message'
        ]
        
        writer = csv.DictWriter(csv_buffer, fieldnames=columns)
        writer.writeheader()
        
        for task_results in task_results_list:
            row = {col: task_results.get(col, '') for col in columns}
            writer.writerow(row)
        
        return csv_buffer.getvalue().encode('utf-8')
    
    @staticmethod
    def _export_batch_csv(batch_results: Dict[str, Any]) -> bytes:
        """Export batch task summaries to CSV format."""
        csv_buffer = io.StringIO()
        
        columns = [
            'task_id', 'analysis_type', 'model_slug', 'app_number', 'status',
            'progress_percentage', 'created_at', 'completed_at', 'error_message'
        ]
        
        writer = csv.DictWriter(csv_buffer, fieldnames=columns)
        writer.writeheader()
        
        for task_summary in batch_results.get('task_summaries', []):
            row = {col: task_summary.get(col, '') for col in columns}
            writer.writerow(row)
        
        return csv_buffer.getvalue().encode('utf-8')
    
    @staticmethod
    def _export_html(results: Dict[str, Any], title: str) -> str:
        """Export results to HTML format."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; }}
                .task {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .status-completed {{ border-left: 5px solid #28a745; }}
                .status-failed {{ border-left: 5px solid #dc3545; }}
                .status-running {{ border-left: 5px solid #007bff; }}
                .finding {{ background-color: #f8f9fa; margin: 5px 0; padding: 10px; border-radius: 3px; }}
                .severity-critical {{ border-left: 3px solid #dc3545; }}
                .severity-high {{ border-left: 3px solid #fd7e14; }}
                .severity-medium {{ border-left: 3px solid #ffc107; }}
                .severity-low {{ border-left: 3px solid #28a745; }}
                pre {{ background-color: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{title}</h1>
                <p>Generated on: {datetime.now(timezone.utc).isoformat()}</p>
            </div>
            
            <div class="section">
                <h2>Summary</h2>
                <pre>{json.dumps(results, indent=2, default=str)}</pre>
            </div>
        </body>
        </html>
        """
        return html


# Initialize service instances
results_query_service = ResultsQueryService()
results_aggregation_service = ResultsAggregationService()
results_export_service = ResultsExportService()



