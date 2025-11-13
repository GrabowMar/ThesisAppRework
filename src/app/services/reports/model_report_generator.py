"""
Model Report Generator

Generates comprehensive reports showing all analyses for a specific model across all apps.
Shows model performance, consistency, and patterns.
"""
import logging
from typing import Dict, Any, List
from pathlib import Path

from .base_generator import BaseReportGenerator
from ...extensions import db
from ...models import AnalysisTask, GeneratedApplication
from ...services.service_locator import ServiceLocator
from ...services.service_base import ValidationError, NotFoundError
from ...utils.time import utc_now

logger = logging.getLogger(__name__)


class ModelReportGenerator(BaseReportGenerator):
    """Generator for model-centric analysis reports."""
    
    def validate_config(self) -> None:
        """Validate configuration for model report."""
        model_slug = self.config.get('model_slug')
        if not model_slug:
            raise ValidationError("model_slug is required for model analysis report")
    
    def get_template_name(self) -> str:
        """Get template name for model reports."""
        return 'model_analysis.html'
    
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect all analysis data for a specific model.
        
        Hybrid approach:
        1. Query database for all completed tasks for this model
        2. Load detailed findings from consolidated JSON files
        3. Aggregate statistics across all apps
        """
        self.validate_config()
        
        model_slug = self.config.get('model_slug')
        date_range = self.config.get('date_range', {})
        
        logger.info(f"Collecting model report data for {model_slug}")
        
        # Step 1: Query database for all completed tasks (fast filtering)
        query = db.session.query(AnalysisTask).filter(
            AnalysisTask.target_model == model_slug,
            AnalysisTask.status == 'completed'
        )
        
        # Apply date range filter if provided
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        tasks = query.order_by(
            AnalysisTask.target_app_number,
            AnalysisTask.completed_at.desc()
        ).all()
        
        if not tasks:
            raise NotFoundError(f"No completed analyses found for model {model_slug}")
        
        # Step 2: Load detailed results from filesystem (complete data)
        unified_service = ServiceLocator().get_unified_result_service()
        
        apps_data = []
        total_findings = 0
        total_critical = 0
        total_high = 0
        total_medium = 0
        total_low = 0
        tools_stats = {}
        
        # Group tasks by app number and get latest for each app
        apps_map = {}
        for task in tasks:
            app_num = task.target_app_number
            if app_num not in apps_map:
                apps_map[app_num] = []
            apps_map[app_num].append(task)
        
        for app_number in sorted(apps_map.keys()):
            app_tasks = apps_map[app_number]
            latest_task = app_tasks[0]  # Already sorted by completed_at desc
            
            # Load consolidated results
            result = unified_service.load_analysis_results(latest_task.task_id)
            
            if not result or not result.raw_data:
                logger.warning(f"No results found for task {latest_task.task_id}")
                continue
            
            raw_data = result.raw_data
            summary = raw_data.get('summary', {})
            
            # Aggregate statistics
            findings_count = summary.get('total_findings', 0)
            total_findings += findings_count
            
            severity_counts = summary.get('findings_by_severity', {})
            total_critical += severity_counts.get('critical', 0)
            total_high += severity_counts.get('high', 0)
            total_medium += severity_counts.get('medium', 0)
            total_low += severity_counts.get('low', 0)
            
            # Aggregate tool statistics
            tools = raw_data.get('tools', {})
            for tool_name, tool_data in tools.items():
                if tool_name not in tools_stats:
                    tools_stats[tool_name] = {
                        'total_executions': 0,
                        'successful': 0,
                        'failed': 0,
                        'total_findings': 0,
                        'total_duration': 0.0
                    }
                
                stats = tools_stats[tool_name]
                stats['total_executions'] += 1
                
                if tool_data.get('status') == 'success':
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                
                stats['total_findings'] += tool_data.get('total_issues', 0)
                stats['total_duration'] += tool_data.get('duration_seconds', 0.0)
            
            # Get app metadata
            app = db.session.query(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug,
                GeneratedApplication.app_number == app_number
            ).first()
            
            apps_data.append({
                'app_number': app_number,
                'task_id': latest_task.task_id,
                'task_status': latest_task.status,
                'completed_at': latest_task.completed_at.isoformat() if latest_task.completed_at else None,
                'duration_seconds': raw_data.get('metadata', {}).get('duration_seconds', 0),
                'app_name': f"{model_slug} / App {app_number}",  # Constructed from slug and number
                'app_type': app.app_type if app else None,
                'findings_count': findings_count,
                'severity_counts': severity_counts,
                'tools': tools,
                'findings': raw_data.get('findings', []),
                'summary': summary,
                'all_tasks_count': len(app_tasks)  # Historical task count
            })
        
        # Calculate tool success rates
        for tool_name, stats in tools_stats.items():
            total = stats['total_executions']
            stats['success_rate'] = (stats['successful'] / total * 100) if total > 0 else 0
            stats['average_duration'] = (stats['total_duration'] / stats['successful']) if stats['successful'] > 0 else 0
        
        # Compile final data structure
        data = {
            'report_type': 'model_analysis',
            'model_slug': model_slug,
            'timestamp': utc_now().isoformat(),
            'date_range': date_range,
            'apps': apps_data,
            'apps_count': len(apps_data),
            'total_tasks': len(tasks),
            'aggregated_stats': {
                'total_findings': total_findings,
                'findings_by_severity': {
                    'critical': total_critical,
                    'high': total_high,
                    'medium': total_medium,
                    'low': total_low
                },
                'average_findings_per_app': total_findings / len(apps_data) if apps_data else 0
            },
            'tools_statistics': tools_stats
        }
        
        self.data = data
        return data
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary for model report."""
        return {
            'model_slug': data.get('model_slug'),
            'apps_analyzed': data.get('apps_count', 0),
            'total_findings': data.get('aggregated_stats', {}).get('total_findings', 0),
            'critical_findings': data.get('aggregated_stats', {}).get('findings_by_severity', {}).get('critical', 0),
            'generated_at': data.get('timestamp')
        }
