"""
App Report Generator

Generates cross-model comparison reports for a specific app.
Shows how different models performed on the same application.
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


class AppReportGenerator(BaseReportGenerator):
    """Generator for app-centric cross-model comparison reports."""
    
    def validate_config(self) -> None:
        """Validate configuration for app report."""
        app_number = self.config.get('app_number')
        if app_number is None:
            raise ValidationError("app_number is required for app analysis report")
    
    def get_template_name(self) -> str:
        """Get template name for app reports."""
        return 'partials/_app_comparison.html'
    
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect all analysis data for a specific app across all models.
        
        Hybrid approach:
        1. Query database for all completed tasks for this app number
        2. Load detailed findings from consolidated JSON files
        3. Compare models' performance on the same app
        """
        self.validate_config()
        
        app_number = self.config.get('app_number')
        date_range = self.config.get('date_range', {})
        filter_models = self.config.get('filter_models', [])  # Optional: limit to specific models
        
        logger.info(f"Collecting app comparison report data for app {app_number}")
        
        # Step 1: Query database for all completed tasks for this app (fast filtering)
        query = db.session.query(AnalysisTask).filter(
            AnalysisTask.target_app_number == app_number,
            AnalysisTask.status == 'completed'
        )
        
        # Apply date range filter if provided
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        # Apply model filter if provided
        if filter_models:
            query = query.filter(AnalysisTask.target_model.in_(filter_models))
        
        tasks = query.order_by(
            AnalysisTask.target_model,
            AnalysisTask.completed_at.desc()
        ).all()
        
        if not tasks:
            raise NotFoundError(f"No completed analyses found for app {app_number}")
        
        # Step 2: Load detailed results from filesystem (complete data)
        unified_service = ServiceLocator().get_unified_result_service()
        
        models_data = []
        all_findings = []
        all_tools = set()
        
        # Group tasks by model and get latest for each model
        models_map = {}
        for task in tasks:
            model_slug = task.target_model
            if model_slug not in models_map:
                models_map[model_slug] = []
            models_map[model_slug].append(task)
        
        for model_slug in sorted(models_map.keys()):
            model_tasks = models_map[model_slug]
            latest_task = model_tasks[0]  # Already sorted by completed_at desc
            
            # Load consolidated results
            result = unified_service.load_analysis_results(latest_task.task_id)
            
            if not result or not result.raw_data:
                logger.warning(f"No results found for task {latest_task.task_id}")
                continue
            
            raw_data = result.raw_data
            # Handle nested 'results' structure from analyzer_manager
            results_wrapper = raw_data.get('results', {})
            summary = raw_data.get('summary') or results_wrapper.get('summary', {})
            tools = raw_data.get('tools') or results_wrapper.get('tools', {})
            findings = raw_data.get('findings') or results_wrapper.get('findings', [])
            
            # Track all tools used across models
            all_tools.update(tools.keys())
            
            # Collect findings for overlap analysis
            all_findings.extend([
                {**f, 'model_slug': model_slug}
                for f in findings
            ])
            
            # Get app metadata for this model
            app = db.session.query(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug,
                GeneratedApplication.app_number == app_number
            ).first()
            
            models_data.append({
                'model_slug': model_slug,
                'task_id': latest_task.task_id,
                'completed_at': latest_task.completed_at.isoformat() if latest_task.completed_at else None,
                'duration_seconds': raw_data.get('metadata', {}).get('duration_seconds', 0),
                'app_name': f"{model_slug} / App {app_number}",  # Constructed, not from model
                'app_description': None,  # GeneratedApplication has no description field
                'findings_count': summary.get('total_findings', 0),
                'severity_counts': summary.get('findings_by_severity', {}),
                'tools': tools,
                'tools_successful': summary.get('tools_successful', 0),
                'tools_failed': summary.get('tools_failed', 0),
                'findings': findings,
                'all_tasks_count': len(model_tasks)
            })
        
        # Analyze findings overlap (findings found by multiple models)
        findings_by_signature = {}
        for finding in all_findings:
            # Create signature based on file, line, rule_id, and message
            signature = f"{finding.get('file', '')}:{finding.get('line', 0)}:{finding.get('rule_id', '')}:{finding.get('message', '')}"
            
            if signature not in findings_by_signature:
                findings_by_signature[signature] = {
                    'finding': finding,
                    'models': set()
                }
            findings_by_signature[signature]['models'].add(finding['model_slug'])
        
        # Categorize findings
        common_findings = []  # Found by multiple models
        unique_findings = []  # Found by single model
        
        for sig, data in findings_by_signature.items():
            finding_with_models = {
                **data['finding'],
                'found_by_models': list(data['models']),
                'found_by_count': len(data['models'])
            }
            
            if len(data['models']) > 1:
                common_findings.append(finding_with_models)
            else:
                unique_findings.append(finding_with_models)
        
        # Calculate comparative statistics
        best_model = None
        worst_model = None
        if models_data:
            sorted_by_findings = sorted(models_data, key=lambda x: x['findings_count'])
            best_model = sorted_by_findings[0]['model_slug']  # Fewest findings
            worst_model = sorted_by_findings[-1]['model_slug']  # Most findings
        
        # Tool consistency analysis
        tool_usage = {}
        for tool_name in all_tools:
            tool_usage[tool_name] = {
                'used_by_models': [],
                'success_rate_by_model': {}
            }
            
            for model_data in models_data:
                if tool_name in model_data['tools']:
                    tool_usage[tool_name]['used_by_models'].append(model_data['model_slug'])
                    tool_data = model_data['tools'][tool_name]
                    success = 1 if tool_data.get('status') == 'success' else 0
                    tool_usage[tool_name]['success_rate_by_model'][model_data['model_slug']] = success
        
        # Compile final data structure
        data = {
            'report_type': 'app_comparison',
            'app_number': app_number,
            'timestamp': utc_now().isoformat(),
            'date_range': date_range,
            'models': models_data,
            'models_count': len(models_data),
            'total_tasks': len(tasks),
            'comparison': {
                'best_performing_model': best_model,
                'worst_performing_model': worst_model,
                'common_findings': common_findings,
                'common_findings_count': len(common_findings),
                'unique_findings': unique_findings,
                'unique_findings_count': len(unique_findings),
                'tool_usage': tool_usage
            }
        }
        
        self.data = data
        return data
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary for app comparison report."""
        return {
            'app_number': data.get('app_number'),
            'models_compared': data.get('models_count', 0),
            'common_findings': data.get('comparison', {}).get('common_findings_count', 0),
            'best_model': data.get('comparison', {}).get('best_performing_model'),
            'generated_at': data.get('timestamp')
        }
