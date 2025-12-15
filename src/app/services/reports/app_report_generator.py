"""
Template Comparison Report Generator

Generates cross-model comparison reports for apps using the same template.
Shows how different models performed when implementing the same requirements.
Includes generation metadata (cost, tokens, time) for full context.
"""
import logging
from typing import Dict, Any, List
from pathlib import Path

from .base_generator import BaseReportGenerator
from ...extensions import db
from ...models import AnalysisTask, GeneratedApplication
from ...constants import AnalysisStatus
from ...services.service_locator import ServiceLocator
from ...services.service_base import ValidationError, NotFoundError
from ...utils.time import utc_now
from ..generation_statistics import load_generation_records

logger = logging.getLogger(__name__)


class AppReportGenerator(BaseReportGenerator):
    """Generator for template-centric cross-model comparison reports."""
    
    def validate_config(self) -> None:
        """Validate configuration for template comparison report."""
        template_slug = self.config.get('template_slug')
        if not template_slug:
            raise ValidationError("template_slug is required for template comparison report")
    
    def get_template_name(self) -> str:
        """Get template name for template comparison reports."""
        return 'partials/_app_comparison.html'
    
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect all analysis data for apps using a specific template across all models.
        
        Template-based approach:
        1. Query database for all GeneratedApplications with matching template_slug
        2. Find completed analysis tasks for those apps
        3. Load detailed findings from consolidated JSON files
        4. Compare models' performance on the same template requirements
        """
        self.validate_config()
        
        template_slug = self.config.get('template_slug')
        date_range = self.config.get('date_range', {})
        filter_models = self.config.get('filter_models', [])  # Optional: limit to specific models
        
        # Support single model_slug config (from pipeline) - convert to filter_models list
        single_model = self.config.get('model_slug')
        if single_model and not filter_models:
            filter_models = [single_model]
        
        logger.info(f"Collecting template comparison report data for template '{template_slug}'" + 
                    (f" (filtered to models: {filter_models})" if filter_models else ""))
        
        # Step 1: Find all apps that used this template
        apps_query = db.session.query(GeneratedApplication).filter(
            GeneratedApplication.template_slug == template_slug
        )
        
        # Apply model filter if provided
        if filter_models:
            apps_query = apps_query.filter(GeneratedApplication.model_slug.in_(filter_models))
        
        apps = apps_query.all()
        
        if not apps:
            logger.warning(f"No apps found using template '{template_slug}'")
            return self._empty_report_data(template_slug, date_range)
        
        # Build a map of (model_slug, app_number) for the apps using this template
        app_identifiers = [(app.model_slug, app.app_number) for app in apps]
        
        # Step 2: Query analysis tasks for these specific apps
        # We need to find tasks where (target_model, target_app_number) matches our apps
        # Only include COMPLETED or PARTIAL_SUCCESS - don't pollute report with failed analyses
        query = db.session.query(AnalysisTask).filter(
            AnalysisTask.status.in_([
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS
            ])
        )
        
        # Apply date range filter if provided
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        # Filter to only tasks for apps using this template
        # Use OR conditions for each (model, app_number) pair
        from sqlalchemy import or_, and_
        app_conditions = [
            and_(
                AnalysisTask.target_model == model_slug,
                AnalysisTask.target_app_number == app_number
            )
            for model_slug, app_number in app_identifiers
        ]
        
        if app_conditions:
            query = query.filter(or_(*app_conditions))
        
        tasks = query.order_by(
            AnalysisTask.target_model,
            AnalysisTask.completed_at.desc()
        ).all()
        
        # Return empty report if no successful analyses exist
        if not tasks:
            logger.warning(f"No successful analyses found for template '{template_slug}' - cannot generate comparison report")
            return self._empty_report_data(template_slug, date_range)
        
        # Step 3: Load detailed results from filesystem (complete data)
        unified_service = ServiceLocator().get_unified_result_service()
        
        models_data = []
        all_findings = []
        all_tools = set()
        
        # Build a lookup for app info by (model_slug, app_number)
        apps_lookup = {(app.model_slug, app.app_number): app for app in apps}
        
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
            
            # Get the app info for this task
            app_info = apps_lookup.get((latest_task.target_model, latest_task.target_app_number))
            
            # Load consolidated results for completed/partial success tasks
            result = unified_service.load_analysis_results(latest_task.task_id)
            
            if not result or not result.raw_data:
                logger.warning(f"No results found for task {latest_task.task_id}, skipping model")
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
            
            # Use app_info from our lookup (already retrieved above)
            
            # Extract tool success/failure counts - handle both integer and list formats
            tools_successful = summary.get('tools_successful', 0)
            tools_failed = summary.get('tools_failed', 0)
            
            # Convert to integers if they're lists (some formats store tool names instead of counts)
            if isinstance(tools_successful, list):
                tools_successful = len(tools_successful)
            if isinstance(tools_failed, list):
                tools_failed = len(tools_failed)
            
            # Ensure we have integers
            tools_successful = int(tools_successful) if tools_successful else 0
            tools_failed = int(tools_failed) if tools_failed else 0
            
            # Also ensure findings_count is an integer
            findings_count = summary.get('total_findings', 0)
            if isinstance(findings_count, list):
                findings_count = len(findings_count)
            findings_count = int(findings_count) if findings_count else 0
            
            # Handle duration_seconds safely
            duration_seconds = raw_data.get('metadata', {}).get('duration_seconds', 0)
            if duration_seconds is None:
                duration_seconds = 0.0
            
            # Get app number from app_info
            app_number = app_info.app_number if app_info else latest_task.target_app_number
            
            models_data.append({
                'model_slug': model_slug,
                'task_id': latest_task.task_id,
                'app_number': app_number,
                'template_slug': template_slug,
                'completed_at': latest_task.completed_at.isoformat() if latest_task.completed_at else None,
                'duration_seconds': float(duration_seconds),
                'app_name': f"{model_slug} / {template_slug}",
                'app_description': None,  # GeneratedApplication has no description field
                'findings_count': findings_count,
                'severity_counts': summary.get('findings_by_severity', {}),
                'tools': tools,
                'tools_successful': tools_successful,
                'tools_failed': tools_failed,
                'findings': findings,
                'all_tasks_count': len(model_tasks),
                'analysis_status': 'completed',
                'error_message': None,
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
        
        # Load generation metadata for cost/token comparison across models
        # Collect all app numbers used by this template for generation stats
        app_numbers_by_model = {m['model_slug']: m.get('app_number') for m in models_data}
        generation_comparison = self._get_generation_comparison_for_template(
            template_slug, 
            [m['model_slug'] for m in models_data],
            app_numbers_by_model
        )
        
        # All models in models_data are from successful analyses now
        successful_analyses = len(models_data)
        
        # Compile final data structure
        data = {
            'report_type': 'template_comparison',
            'template_slug': template_slug,
            'timestamp': utc_now().isoformat(),
            'date_range': date_range,
            'models': models_data,
            'models_count': len(models_data),
            'total_tasks': len(tasks),
            'successful_analyses': successful_analyses,
            'failed_analyses': 0,  # We no longer include failed analyses
            'comparison': {
                'best_performing_model': best_model,
                'worst_performing_model': worst_model,
                'common_findings': common_findings,
                'common_findings_count': len(common_findings),
                'unique_findings': unique_findings,
                'unique_findings_count': len(unique_findings),
                'tool_usage': tool_usage
            },
            'generation_comparison': generation_comparison
        }
        
        # Add tool categories from registry for template rendering
        data = self.add_tool_context(data)
        
        self.data = data
        return data
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary for template comparison report."""
        return {
            'template_slug': data.get('template_slug'),
            'models_compared': data.get('models_count', 0),
            'common_findings': data.get('comparison', {}).get('common_findings_count', 0),
            'best_model': data.get('comparison', {}).get('best_performing_model'),
            'generated_at': data.get('timestamp')
        }
    
    def _empty_report_data(self, template_slug: str, date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Return empty report structure when no apps found for template."""
        return {
            'report_type': 'template_comparison',
            'template_slug': template_slug,
            'timestamp': utc_now().isoformat(),
            'date_range': date_range,
            'models': [],
            'models_count': 0,
            'total_tasks': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'comparison': {
                'best_performing_model': None,
                'worst_performing_model': None,
                'common_findings': [],
                'common_findings_count': 0,
                'unique_findings': [],
                'unique_findings_count': 0,
                'tool_usage': {}
            },
            'generation_comparison': {'available': False, 'message': 'No apps found for this template'}
        }
    
    def _get_generation_comparison_for_template(
        self, 
        template_slug: str, 
        model_slugs: List[str],
        app_numbers_by_model: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Load generation metadata for comparing models on a specific template.
        
        Returns per-model generation stats (cost, tokens, time, lines).
        """
        try:
            records = load_generation_records(include_files=True, include_db=True, include_applications=True)
            
            # Filter to models in our list and their corresponding app numbers
            app_records = []
            for r in records:
                if r.model in model_slugs:
                    expected_app_num = app_numbers_by_model.get(r.model)
                    if expected_app_num is not None and r.app_num == expected_app_num:
                        app_records.append(r)
            
            if not app_records:
                return {'available': False, 'message': 'No generation metadata found'}
            
            # Group by model
            models_generation = {}
            
            for rec in app_records:
                model = rec.model
                if model not in models_generation:
                    models_generation[model] = {
                        'model_slug': model,
                        'components': [],
                        'total_cost': 0.0,
                        'total_tokens': 0,
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'generation_time_ms': 0,
                        'total_lines': 0,
                        'provider': None
                    }
                
                data = models_generation[model]
                
                if rec.component:
                    data['components'].append(rec.component)
                
                if rec.estimated_cost:
                    data['total_cost'] += rec.estimated_cost
                if rec.total_tokens:
                    data['total_tokens'] += rec.total_tokens
                if rec.prompt_tokens:
                    data['prompt_tokens'] += rec.prompt_tokens
                if rec.completion_tokens:
                    data['completion_tokens'] += rec.completion_tokens
                if rec.generation_time_ms:
                    data['generation_time_ms'] += rec.generation_time_ms
                if rec.total_lines:
                    data['total_lines'] += rec.total_lines
                if rec.provider_name:
                    data['provider'] = rec.provider_name
            
            # Find cheapest and most expensive
            models_list = list(models_generation.values())
            models_with_cost = [m for m in models_list if m['total_cost'] > 0]
            
            cheapest_model = None
            most_expensive_model = None
            if models_with_cost:
                sorted_by_cost = sorted(models_with_cost, key=lambda x: x['total_cost'])
                cheapest_model = sorted_by_cost[0]['model_slug']
                most_expensive_model = sorted_by_cost[-1]['model_slug']
            
            # Calculate totals
            total_cost = sum(m['total_cost'] for m in models_list)
            total_tokens = sum(m['total_tokens'] for m in models_list)
            total_lines = sum(m['total_lines'] for m in models_list)
            
            return {
                'available': True,
                'models': models_list,
                'cheapest_model': cheapest_model,
                'most_expensive_model': most_expensive_model,
                'total_cost': round(total_cost, 6),
                'total_tokens': total_tokens,
                'total_lines': total_lines,
                'avg_cost_per_model': round(total_cost / len(models_list), 6) if models_list else 0
            }
        except Exception as e:
            logger.warning(f"Failed to load generation comparison for template {template_slug}: {e}")
            return {'available': False, 'error': str(e)}
