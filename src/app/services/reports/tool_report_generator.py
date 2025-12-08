"""
Tool Report Generator

Generates tool effectiveness reports showing performance across all analyses.
Global analysis with optional filtering by model/app.
"""
import logging
from typing import Dict, Any, List
from pathlib import Path
from collections import defaultdict

from .base_generator import BaseReportGenerator
from ...extensions import db
from ...models import AnalysisTask
from ...constants import AnalysisStatus
from ...services.service_locator import ServiceLocator
from ...services.service_base import ValidationError, NotFoundError
from ...utils.time import utc_now

logger = logging.getLogger(__name__)


class ToolReportGenerator(BaseReportGenerator):
    """Generator for tool-centric performance reports."""
    
    def validate_config(self) -> None:
        """Validate configuration for tool report."""
        # Tool name is optional - if not provided, analyze all tools
        pass
    
    def get_template_name(self) -> str:
        """Get template name for tool reports."""
        return 'partials/_tool_analysis.html'
    
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect tool performance data across all analyses.
        
        Global but filterable:
        - Analyze all tools by default
        - Filter by specific tool name if provided
        - Filter by model if provided
        - Filter by app if provided
        - Filter by date range if provided
        
        Hybrid approach:
        1. Query database for all completed tasks (with filters)
        2. Load detailed tool data from consolidated JSON files
        3. Aggregate tool statistics globally
        """
        tool_name = self.config.get('tool_name')  # Optional
        filter_model = self.config.get('filter_model')  # Optional (single model)
        filter_models = self.config.get('filter_models', [])  # Optional (list of models from pipeline)
        filter_app = self.config.get('filter_app')  # Optional (single app)
        filter_apps = self.config.get('filter_apps', [])  # Optional (list of apps from pipeline)
        date_range = self.config.get('date_range', {})
        
        logger.info(f"Collecting tool report data (tool={tool_name}, model={filter_model or filter_models}, app={filter_app or filter_apps})")
        
        # Step 1: Query database for terminal tasks (fast filtering)
        query = db.session.query(AnalysisTask).filter(
            AnalysisTask.status.in_([
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS
            ])
        )
        
        # Apply filters
        if filter_model:
            query = query.filter(AnalysisTask.target_model == filter_model)
        elif filter_models:
            query = query.filter(AnalysisTask.target_model.in_(filter_models))
        
        if filter_app is not None:
            query = query.filter(AnalysisTask.target_app_number == filter_app)
        elif filter_apps:
            query = query.filter(AnalysisTask.target_app_number.in_(filter_apps))
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        tasks = query.order_by(AnalysisTask.completed_at.desc()).all()
        
        if not tasks:
            logger.warning("No completed analyses found with the specified filters")
            tasks = []  # Continue with empty list
        
        # Step 2: Load detailed tool data from filesystem
        unified_service = ServiceLocator().get_unified_result_service()
        
        # Global tool statistics
        tools_data = defaultdict(lambda: {
            'tool_name': '',
            'total_executions': 0,
            'successful': 0,
            'failed': 0,
            'total_findings': 0,
            'findings_by_severity': {
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'info': 0
            },
            'total_duration': 0.0,
            'executions_by_model': defaultdict(int),
            'success_by_model': defaultdict(int),
            'findings_by_model': defaultdict(int),
            'execution_timeline': []  # For trend analysis
        })
        
        processed_tasks = 0
        
        for task in tasks:
            # Load consolidated results
            result = unified_service.load_analysis_results(task.task_id)
            
            if not result or not result.raw_data:
                logger.warning(f"No results found for task {task.task_id}")
                continue
            
            raw_data = result.raw_data
            # Handle nested 'results' structure from analyzer_manager
            results_wrapper = raw_data.get('results', {})
            tools = raw_data.get('tools') or results_wrapper.get('tools', {})
            findings = raw_data.get('findings') or results_wrapper.get('findings', [])
            
            # Process each tool in this task
            for tool, tool_data in tools.items():
                # Skip if filtering by specific tool and this isn't it
                if tool_name and tool != tool_name:
                    continue
                
                stats = tools_data[tool]
                stats['tool_name'] = tool
                
                # Execution statistics
                stats['total_executions'] += 1
                stats['executions_by_model'][task.target_model] += 1
                
                if tool_data.get('executed'):
                    if tool_data.get('status') == 'success':
                        stats['successful'] += 1
                        stats['success_by_model'][task.target_model] += 1
                    else:
                        stats['failed'] += 1
                
                # Duration - ensure we handle None values
                duration = tool_data.get('duration_seconds')
                stats['total_duration'] += float(duration) if duration is not None else 0.0
                
                # Timeline entry for trend analysis
                stats['execution_timeline'].append({
                    'date': task.completed_at.isoformat() if task.completed_at else None,
                    'model': task.target_model,
                    'app': task.target_app_number,
                    'success': tool_data.get('status') == 'success',
                    'findings': tool_data.get('total_issues', 0) or 0,
                    'duration': float(duration) if duration is not None else 0.0
                })
            
            # Count findings by tool
            for finding in findings:
                finding_tool = finding.get('tool')
                
                # Skip if filtering by specific tool and this isn't it
                if tool_name and finding_tool != tool_name:
                    continue
                
                if finding_tool:
                    stats = tools_data[finding_tool]
                    stats['total_findings'] += 1
                    stats['findings_by_model'][task.target_model] += 1
                    
                    # Track severity
                    severity = finding.get('severity', 'info').lower()
                    if severity in stats['findings_by_severity']:
                        stats['findings_by_severity'][severity] += 1
            
            processed_tasks += 1
        
        # Convert defaultdicts to regular dicts and calculate rates
        tools_list = []
        for tool_name_key, stats in tools_data.items():
            # Convert nested defaultdicts
            stats['executions_by_model'] = dict(stats['executions_by_model'])
            stats['success_by_model'] = dict(stats['success_by_model'])
            stats['findings_by_model'] = dict(stats['findings_by_model'])
            
            # Calculate rates
            total_exec = stats['total_executions']
            stats['success_rate'] = (stats['successful'] / total_exec * 100) if total_exec > 0 else 0
            stats['failure_rate'] = (stats['failed'] / total_exec * 100) if total_exec > 0 else 0
            stats['average_duration'] = (stats['total_duration'] / stats['successful']) if stats['successful'] > 0 else 0
            stats['average_findings_per_execution'] = (stats['total_findings'] / stats['successful']) if stats['successful'] > 0 else 0
            
            # Sort timeline by date
            stats['execution_timeline'].sort(key=lambda x: x['date'] or '', reverse=True)
            
            tools_list.append(stats)
        
        # Sort tools by total executions (most used first)
        tools_list.sort(key=lambda x: x['total_executions'], reverse=True)
        
        # Calculate overall statistics
        total_executions = sum(t['total_executions'] for t in tools_list)
        total_successful = sum(t['successful'] for t in tools_list)
        total_findings = sum(t['total_findings'] for t in tools_list)
        
        # Identify best/worst performers
        best_success_rate_tool = None
        worst_success_rate_tool = None
        fastest_tool = None
        slowest_tool = None
        most_findings_tool = None
        
        if tools_list:
            sorted_by_success = sorted([t for t in tools_list if t['total_executions'] > 0], 
                                      key=lambda x: x['success_rate'], reverse=True)
            if sorted_by_success:
                best_success_rate_tool = sorted_by_success[0]['tool_name']
                worst_success_rate_tool = sorted_by_success[-1]['tool_name']
            
            sorted_by_duration = sorted([t for t in tools_list if t['successful'] > 0],
                                       key=lambda x: x['average_duration'])
            if sorted_by_duration:
                fastest_tool = sorted_by_duration[0]['tool_name']
                slowest_tool = sorted_by_duration[-1]['tool_name']
            
            sorted_by_findings = sorted(tools_list, key=lambda x: x['total_findings'], reverse=True)
            most_findings_tool = sorted_by_findings[0]['tool_name']
        
        # Compile final data structure
        data = {
            'report_type': 'tool_analysis',
            'timestamp': utc_now().isoformat(),
            'filters': {
                'tool_name': tool_name,
                'filter_model': filter_model,
                'filter_app': filter_app,
                'date_range': date_range
            },
            'tools': tools_list,
            'tools_count': len(tools_list),
            'tasks_analyzed': processed_tasks,
            'overall_stats': {
                'total_executions': total_executions,
                'total_successful': total_successful,
                'total_findings': total_findings,
                'overall_success_rate': (total_successful / total_executions * 100) if total_executions > 0 else 0
            },
            'insights': {
                'best_success_rate_tool': best_success_rate_tool,
                'worst_success_rate_tool': worst_success_rate_tool,
                'fastest_tool': fastest_tool,
                'slowest_tool': slowest_tool,
                'most_findings_tool': most_findings_tool
            }
        }
        
        self.data = data
        return data
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary for tool report."""
        return {
            'tools_analyzed': data.get('tools_count', 0),
            'tasks_analyzed': data.get('tasks_analyzed', 0),
            'total_findings': data.get('overall_stats', {}).get('total_findings', 0),
            'overall_success_rate': round(data.get('overall_stats', {}).get('overall_success_rate', 0), 1),
            'best_tool': data.get('insights', {}).get('best_success_rate_tool'),
            'generated_at': data.get('timestamp')
        }
