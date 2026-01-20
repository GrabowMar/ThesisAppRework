"""
Report Service (v2)
==================

Simplified report generation service that stores JSON data directly in the database.
No file generation - reports are rendered client-side from JSON data.

Report Types:
- model_analysis: All analyses for a single model across all apps
- template_comparison: Cross-model comparison for a single template  
- tool_analysis: Tool effectiveness metrics across analyses
"""

import json
import logging
import uuid
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Literal

from ..extensions import db
from ..models import (
    Report, AnalysisTask, GeneratedApplication, ModelCapability,
    PerformanceTest, SecurityAnalysis, OpenRouterAnalysis
)
from ..constants import AnalysisStatus
from ..utils.time import utc_now
from ..utils.slug_utils import normalize_model_slug, generate_slug_variants
from .unified_result_service import UnifiedResultService
from .service_locator import ServiceLocator
from .reports import _count_loc_from_files

logger = logging.getLogger(__name__)

ReportType = Literal['model_analysis', 'template_comparison', 'tool_analysis']


# =============================================================================
# ANALYZER CATEGORIES - Tool-to-Analyzer mapping for customized reports
# =============================================================================
# Maps tools to their analyzer type (static/dynamic/performance/ai)
# Includes type-specific metadata for enhanced reporting
ANALYZER_CATEGORIES = {
    # Static Analyzer Tools (Port 2001)
    'static': {
        'display_name': 'Static Analysis',
        'service': 'static-analyzer',
        'port': 2001,
        'description': 'Code quality and security analysis without execution',
        'metrics_focus': ['security_findings', 'code_quality', 'type_coverage', 'dependency_vulnerabilities'],
        'tools': {
            # Security tools
            'bandit': {'category': 'security', 'language': 'python', 'focus': 'security vulnerabilities'},
            'semgrep': {'category': 'security', 'language': 'multi', 'focus': 'pattern-based security'},
            'detect-secrets': {'category': 'security', 'language': 'multi', 'focus': 'credential detection'},
            # Quality tools
            'pylint': {'category': 'quality', 'language': 'python', 'focus': 'code quality'},
            'flake8': {'category': 'quality', 'language': 'python', 'focus': 'style checking'},
            'ruff': {'category': 'quality', 'language': 'python', 'focus': 'fast linting'},
            'vulture': {'category': 'quality', 'language': 'python', 'focus': 'dead code'},
            'eslint': {'category': 'quality', 'language': 'javascript', 'focus': 'JS/TS linting'},
            'jshint': {'category': 'quality', 'language': 'javascript', 'focus': 'JS quality'},
            'stylelint': {'category': 'quality', 'language': 'css', 'focus': 'CSS linting'},
            # Type checking
            'mypy': {'category': 'types', 'language': 'python', 'focus': 'static type checking'},
            # Dependency analysis
            'safety': {'category': 'dependencies', 'language': 'python', 'focus': 'CVE scanning'},
            'pip-audit': {'category': 'dependencies', 'language': 'python', 'focus': 'package audit'},
            'npm-audit': {'category': 'dependencies', 'language': 'javascript', 'focus': 'npm vulnerabilities'},
            # Complexity
            'radon': {'category': 'complexity', 'language': 'python', 'focus': 'cyclomatic complexity'},
        }
    },
    # Dynamic Analyzer Tools (Port 2002)
    'dynamic': {
        'display_name': 'Dynamic Analysis',
        'service': 'dynamic-analyzer',
        'port': 2002,
        'description': 'Runtime security scanning against running applications',
        'metrics_focus': ['runtime_vulnerabilities', 'zap_alerts', 'owasp_coverage', 'attack_surface'],
        'tools': {
            'zap': {'category': 'security', 'language': 'runtime', 'focus': 'web vulnerability scanning'},
            'owasp-zap': {'category': 'security', 'language': 'runtime', 'focus': 'OWASP ZAP scanner'},
            'nmap': {'category': 'security', 'language': 'runtime', 'focus': 'port scanning'},
            'curl': {'category': 'security', 'language': 'runtime', 'focus': 'endpoint probing'},
            'connectivity': {'category': 'health', 'language': 'runtime', 'focus': 'service availability'},
        }
    },
    # Performance Tester Tools (Port 2003)
    'performance': {
        'display_name': 'Performance Testing',
        'service': 'performance-tester',
        'port': 2003,
        'description': 'Load testing and performance benchmarking',
        'metrics_focus': ['requests_per_second', 'latency_percentiles', 'error_rate', 'throughput'],
        'tools': {
            'locust': {'category': 'performance', 'language': 'runtime', 'focus': 'distributed load testing'},
            'artillery': {'category': 'performance', 'language': 'runtime', 'focus': 'modern load testing'},
            'ab': {'category': 'performance', 'language': 'runtime', 'focus': 'Apache bench'},
            'aiohttp': {'category': 'performance', 'language': 'runtime', 'focus': 'async benchmarks'},
        }
    },
    # AI Analyzer Tools (Port 2004)
    'ai': {
        'display_name': 'AI Analysis',
        'service': 'ai-analyzer',
        'port': 2004,
        'description': 'LLM-based code analysis and requirements compliance',
        'metrics_focus': ['requirements_compliance', 'code_quality_score', 'api_conformance', 'best_practices'],
        'tools': {
            'ai-analyzer': {'category': 'ai', 'language': 'multi', 'focus': 'LLM code review'},
            'ai-review': {'category': 'ai', 'language': 'multi', 'focus': 'AI quality assessment'},
            'requirements-check': {'category': 'ai', 'language': 'multi', 'focus': 'requirements compliance'},
        }
    },
}

# Build reverse lookup: tool_name -> analyzer_type
TOOL_TO_ANALYZER = {}
for analyzer_type, analyzer_info in ANALYZER_CATEGORIES.items():
    for tool_name in analyzer_info['tools'].keys():
        TOOL_TO_ANALYZER[tool_name] = analyzer_type

# Tool category classification (for finer-grained grouping within analyzers)
TOOL_CATEGORIES = {
    'security': ['bandit', 'semgrep', 'detect-secrets', 'zap', 'owasp-zap', 'nmap', 'safety', 'pip-audit', 'npm-audit'],
    'quality': ['pylint', 'flake8', 'ruff', 'vulture', 'eslint', 'jshint', 'stylelint'],
    'types': ['mypy'],
    'complexity': ['radon'],
    'performance': ['locust', 'artillery', 'ab', 'aiohttp'],
    'ai': ['ai-analyzer', 'ai-review', 'requirements-check'],
    'health': ['connectivity', 'curl'],
}


class ReportService:
    """
    Simplified report generation service.
    
    All report data is stored as JSON in the database - no file I/O.
    Reports are rendered client-side using JavaScript.
    """
    
    def __init__(self):
        """Initialize the report service."""
        self._unified_service: Optional[UnifiedResultService] = None
    
    @property
    def unified_service(self) -> UnifiedResultService:
        """Lazy-load unified result service."""
        if self._unified_service is None:
            try:
                service = ServiceLocator().get_unified_result_service()
                if service is not None:
                    self._unified_service = service  # type: ignore[assignment]
                else:
                    self._unified_service = UnifiedResultService()
            except Exception:
                self._unified_service = UnifiedResultService()
        assert self._unified_service is not None
        return self._unified_service
    
    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def generate_report(
        self,
        report_type: ReportType,
        config: Dict[str, Any],
        title: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
        expires_in_days: int = 30
    ) -> Report:
        """
        Generate a report and store data in database.
        
        Args:
            report_type: Type of report to generate
            config: Report-specific configuration
            title: Optional custom title
            description: Optional description
            user_id: ID of user creating report
            expires_in_days: Days until report expires
            
        Returns:
            Report model instance with data populated
        """
        # Validate config
        self._validate_config(report_type, config)
        
        # Generate unique ID
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        
        # Create report record
        report = Report(
            report_id=report_id,
            report_type=report_type,
            title=title or self._generate_title(report_type, config),
            description=description,
            format='json',  # Always JSON now
            status='generating',
            created_by=user_id,
            progress_percent=0
        )
        report.set_config(config)
        
        if expires_in_days:
            report.expires_at = utc_now() + timedelta(days=expires_in_days)
        
        db.session.add(report)
        db.session.commit()
        
        try:
            # Generate report data based on type
            logger.info(f"Generating {report_type} report {report_id}")
            
            if report_type == 'model_analysis':
                data = self._generate_model_report(config, report)
            elif report_type == 'template_comparison':
                data = self._generate_template_comparison(config, report)
            elif report_type == 'tool_analysis':
                data = self._generate_tool_report(config, report)
            elif report_type == 'generation_analytics':
                data = self._generate_generation_analytics(config, report)

            # Store the generated data in the database
            report.set_report_data(data)

            report.status = 'completed'
            report.completed_at = utc_now()
            report.progress_percent = 100
            
            db.session.commit()
            logger.info(f"Report {report_id} generated successfully")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate report {report_id}: {e}", exc_info=True)
            report.status = 'failed'
            report.error_message = str(e)
            report.completed_at = utc_now()
            db.session.commit()
            raise
    
    def get_report(self, report_id: str) -> Optional[Report]:
        """Get report by ID."""
        return Report.query.filter_by(report_id=report_id).first()
    
    def get_report_data(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report data as dictionary."""
        report = self.get_report(report_id)
        if report and report.status == 'completed':
            return report.get_report_data()
        return None
    
    def list_reports(
        self,
        report_type: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Report]:
        """List reports with optional filtering."""
        query = Report.query
        
        if report_type:
            query = query.filter(Report.report_type == report_type)
        if status:
            query = query.filter(Report.status == status)  # type: ignore[arg-type]
        if user_id:
            query = query.filter(Report.created_by == user_id)
        
        return query.order_by(Report.created_at.desc()).limit(limit).offset(offset).all()
    
    def delete_report(self, report_id: str) -> bool:
        """Delete a report."""
        report = self.get_report(report_id)
        if not report:
            return False
        
        db.session.delete(report)
        db.session.commit()
        logger.info(f"Deleted report {report_id}")
        return True
    
    def regenerate_report(self, report_id: str) -> Optional[Report]:
        """
        Regenerate an existing report with fresh data.
        
        This re-runs the report generation logic using the original config,
        then updates the stored report_data. Useful when underlying analysis
        data has changed.
        
        Args:
            report_id: The report ID to regenerate
            
        Returns:
            Updated Report object or None if not found
        """
        report = self.get_report(report_id)
        if not report:
            return None
        
        # Parse config if stored as string
        config = report.config
        if isinstance(config, str):
            import json
            config = json.loads(config)
        
        logger.info(f"Regenerating report {report_id} (type={report.report_type})")
        
        try:
            # Generate fresh report data using appropriate generator
            if report.report_type == 'model_analysis':
                new_data = self._generate_model_report(config, report)
            elif report.report_type == 'template_comparison':
                new_data = self._generate_template_comparison(config, report)
            elif report.report_type == 'tool_analysis':
                new_data = self._generate_tool_report(config, report)
            else:
                logger.error(f"Unknown report type: {report.report_type}")
                return None
            
            # Update report with new data
            import json
            report.report_data = json.dumps(new_data) if not isinstance(new_data, str) else new_data
            report.completed_at = utc_now()
            report.status = 'completed'
            db.session.commit()
            
            logger.info(f"Successfully regenerated report {report_id}")
            return report
            
        except Exception as e:
            logger.error(f"Error regenerating report {report_id}: {e}", exc_info=True)
            report.status = 'failed'
            report.error_message = str(e)
            db.session.commit()
            return None
    
    def cleanup_expired_reports(self) -> int:
        """Delete expired reports. Returns count deleted."""
        now = utc_now()
        expired = Report.query.filter(
            Report.expires_at.isnot(None),
            Report.expires_at < now
        ).all()
        
        count = 0
        for report in expired:
            try:
                db.session.delete(report)
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete expired report {report.report_id}: {e}")
        
        db.session.commit()
        logger.info(f"Cleaned up {count} expired reports")
        return count
    
    # ==========================================================================
    # REPORT GENERATORS
    # ==========================================================================
    
    def _generate_model_report(self, config: Dict[str, Any], report: Report) -> Dict[str, Any]:
        """
        Generate model analysis report.
        
        Shows all analyses for a single model across all apps.
        """
        model_slug = config['model_slug']
        date_range = config.get('date_range', {})
        
        # Normalize and generate slug variants for matching
        normalized_slug = normalize_model_slug(model_slug)
        slug_variants = generate_slug_variants(model_slug)
        
        logger.info(f"Generating model report for {model_slug} (normalized: {normalized_slug}, variants: {slug_variants})")
        
        # Query completed tasks for this model using slug variants
        query = AnalysisTask.query.filter(
            AnalysisTask.target_model.in_(slug_variants),
            AnalysisTask.status.in_([  # type: ignore[union-attr]
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS,
                AnalysisStatus.FAILED,
                AnalysisStatus.CANCELLED
            ])
        )
        
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])  # type: ignore[operator]
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])  # type: ignore[operator]
        
        tasks = query.order_by(
            AnalysisTask.target_app_number,
            AnalysisTask.completed_at.desc()  # type: ignore[union-attr]
        ).all()
        
        report.update_progress(20)
        db.session.commit()
        
        # Group by app and get latest task per app
        apps_map: Dict[int, List[AnalysisTask]] = {}
        for task in tasks:
            app_num = task.target_app_number
            if app_num not in apps_map:
                apps_map[app_num] = []
            apps_map[app_num].append(task)
        
        # Process each app
        apps_data = []
        all_findings = []
        tools_stats: Dict[str, Dict[str, Any]] = {}
        
        for app_number in sorted(apps_map.keys()):
            app_tasks = apps_map[app_number]
            latest_task = app_tasks[0]
            
            app_entry = self._process_task_for_report(latest_task, model_slug, app_number)
            apps_data.append(app_entry)
            
            # Aggregate findings
            if app_entry.get('findings'):
                all_findings.extend(app_entry['findings'])
            
            # Aggregate tool stats
            for tool_name, tool_data in app_entry.get('tools', {}).items():
                if tool_name not in tools_stats:
                    tools_stats[tool_name] = {
                        'executions': 0,
                        'successful': 0,
                        'failed': 0,
                        'total_findings': 0,
                        'total_duration': 0.0
                    }
                
                stats = tools_stats[tool_name]
                stats['executions'] += 1
                
                status = tool_data.get('status', 'unknown')
                if status in ('success', 'completed', 'no_issues'):
                    stats['successful'] += 1
                elif status == 'failed':
                    stats['failed'] += 1
                
                stats['total_findings'] += tool_data.get('total_issues', 0) or 0
                stats['total_duration'] += tool_data.get('duration_seconds', 0) or 0
        
        report.update_progress(80)
        db.session.commit()
        
        # Calculate aggregated statistics
        severity_counts = self._count_severities(all_findings)
        scientific_metrics = self._calculate_metrics(apps_data)
        
        # Finalize tool stats with display-friendly fields
        for tool_name, stats in tools_stats.items():
            total = stats['executions']
            stats['success_rate'] = (stats['successful'] / total * 100) if total > 0 else 0
            stats['avg_duration'] = (stats['total_duration'] / stats['successful']) if stats['successful'] > 0 else 0
            stats['findings_per_run'] = (stats['total_findings'] / stats['successful']) if stats['successful'] > 0 else 0
            # Add display-friendly fields for template
            stats['display_name'] = tool_name.replace('_', ' ').title()
            stats['total_runs'] = stats['executions']
            stats['overall_status'] = 'success' if stats['success_rate'] >= 50 else 'error'
        
        # Get model capability info if available (using correct attribute names)
        model_info = {}
        try:
            capability = ModelCapability.query.filter(
                (ModelCapability.canonical_slug == model_slug) |
                (ModelCapability.canonical_slug == normalized_slug)
            ).first()
            if capability:
                model_info = {
                    'model_name': capability.model_name,
                    'provider': capability.provider,
                    'context_window': capability.context_window,
                    'max_output_tokens': capability.max_output_tokens,
                    'supports_function_calling': capability.supports_function_calling,
                    'supports_vision': capability.supports_vision,
                    'supports_streaming': capability.supports_streaming,
                    'supports_json_mode': capability.supports_json_mode,
                    'is_free': capability.is_free,
                    'input_price_per_token': capability.input_price_per_token,
                    'output_price_per_token': capability.output_price_per_token,
                }
        except Exception as e:
            logger.warning(f"Could not fetch model capability: {e}")
        
        # Calculate aggregate execution metrics
        total_duration = sum(a.get('duration_seconds', 0) or 0 for a in apps_data)
        total_queue_time = sum(a.get('queue_time_seconds', 0) or 0 for a in apps_data)
        avg_duration = total_duration / len(apps_data) if apps_data else 0
        
        # Calculate generation statistics (using correct field names from _process_task_for_report)
        generation_stats = {
            'total_apps': len(apps_data),
            'successful_generations': sum(1 for a in apps_data if a.get('generation_status') in ('completed', 'COMPLETED')),
            'failed_generations': sum(1 for a in apps_data if a.get('generation_failed')),
            'total_scripted_fixes': sum(a.get('automatic_fixes', 0) or 0 for a in apps_data),
            'total_llm_fixes': sum(a.get('llm_fixes', 0) or 0 for a in apps_data),
            'total_manual_fixes': sum(a.get('manual_fixes', 0) or 0 for a in apps_data),
            'apps_with_fixes': sum(1 for a in apps_data if a.get('total_fixes', 0) > 0),
        }
        
        # Calculate analysis statistics
        analysis_stats = {
            'completed_analyses': sum(1 for a in apps_data if a.get('task_status') == 'completed'),
            'partial_analyses': sum(1 for a in apps_data if a.get('task_status') == 'partial_success'),
            'failed_analyses': sum(1 for a in apps_data if a.get('task_status') in ('failed', 'cancelled')),
            'total_retries': sum(a.get('retry_count', 0) or 0 for a in apps_data),
        }
        
        # Framework distribution
        backend_frameworks = {}
        frontend_frameworks = {}
        for a in apps_data:
            bf = a.get('backend_framework')
            ff = a.get('frontend_framework')
            if bf:
                backend_frameworks[bf] = backend_frameworks.get(bf, 0) + 1
            if ff:
                frontend_frameworks[ff] = frontend_frameworks.get(ff, 0) + 1
        
        # Calculate LOC metrics using the shared helper
        app_numbers = sorted(apps_map.keys())
        loc_metrics = _count_loc_from_files(model_slug, app_numbers)
        
        # Calculate issues_per_100_loc if we have LOC data
        total_loc = loc_metrics.get('total_loc', 0)
        if total_loc > 0:
            loc_metrics['issues_per_100_loc'] = round((len(all_findings) / total_loc) * 100, 4)
        else:
            loc_metrics['issues_per_100_loc'] = None
        
        # Add issues_count and issues_per_100_loc to each per_app entry
        # Build a map of app_number -> findings count from apps_data
        findings_per_app = {}
        for app_entry in apps_data:
            app_num = app_entry.get('app_number')
            if app_num is not None:
                findings_per_app[app_num] = len(app_entry.get('findings', []))
        
        # Enrich per_app entries with issues data
        for app_num, per_app_data in loc_metrics.get('per_app', {}).items():
            issues_count = findings_per_app.get(app_num, 0)
            per_app_data['issues_count'] = issues_count
            app_loc = per_app_data.get('total_loc', 0)
            if app_loc > 0:
                per_app_data['issues_per_100_loc'] = round((issues_count / app_loc) * 100, 2)
            else:
                per_app_data['issues_per_100_loc'] = 0.0
        
        # Collect quantitative metrics from database models
        quantitative_metrics = self._get_quantitative_metrics(model_slug, app_numbers)
        
        return {
            'report_type': 'model_analysis',
            'model_slug': model_slug,
            'model_info': model_info,
            'generated_at': utc_now().isoformat(),
            'date_range': date_range,
            'apps': apps_data,
            'apps_count': len(apps_data),
            'total_tasks': len(tasks),
            # Summary with all fields the template expects
            'summary': {
                'total_apps': len(apps_data),
                'total_analyses': len(tasks),
                'total_findings': len(all_findings),
                'severity_breakdown': severity_counts,
                'avg_findings_per_app': len(all_findings) / len(apps_data) if apps_data else 0,
                # Extended metrics
                'avg_duration_seconds': avg_duration,
                'total_duration_seconds': total_duration,
                'total_queue_time_seconds': total_queue_time,
            },
            # Duplicate severity data for template compatibility
            'findings_breakdown': severity_counts,
            'scientific_metrics': scientific_metrics,
            # Provide both field names for compatibility
            'tools_statistics': tools_stats,
            'tool_summary': tools_stats,
            'findings': all_findings[:500],
            # Extended data sections
            'generation_stats': generation_stats,
            'analysis_stats': analysis_stats,
            'execution_metrics': {
                'total_duration_seconds': total_duration,
                'avg_duration_seconds': avg_duration,
                'total_queue_time_seconds': total_queue_time,
                'avg_queue_time_seconds': total_queue_time / len(apps_data) if apps_data else 0,
            },
            'framework_distribution': {
                'backend': backend_frameworks,
                'frontend': frontend_frameworks,
            },
            'loc_metrics': loc_metrics,
            # NEW: Quantitative metrics from DB models (docker, generation, performance, ai, security)
            'quantitative_metrics': quantitative_metrics,
        }
    
    def _get_quantitative_metrics(
        self,
        model_slug: str,
        filter_apps: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Collect quantitative metrics from database models for all apps of this model.
        
        Queries PerformanceTest, OpenRouterAnalysis, SecurityAnalysis, and GeneratedApplication
        to extract numeric metrics for scientific analysis.
        
        Args:
            model_slug: Model identifier
            filter_apps: Optional list of app numbers to filter
            
        Returns:
            Dict with performance, AI analysis, security, docker, and generation success metrics
        """
        # Local import avoids report package import-time cycles.
        from .reports.quantitative_metrics import collect_quantitative_metrics

        return collect_quantitative_metrics(model_slug=model_slug, filter_apps=filter_apps)
    
    def _get_template_metadata(self, template_slug: str) -> Dict[str, Any]:
        """
        Load template metadata from the requirements JSON file.
        
        Returns comprehensive template info including requirements counts,
        API endpoints, complexity metrics, etc.
        """
        import os
        
        # Construct path to template file
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        template_path = os.path.join(base_path, 'misc', 'requirements', f'{template_slug}.json')
        
        metadata = {
            'slug': template_slug,
            'name': template_slug.replace('_', ' ').title(),
            'category': 'Unknown',
            'description': 'No description available',
            'available': False,
            'backend_requirements_count': 0,
            'frontend_requirements_count': 0,
            'admin_requirements_count': 0,
            'total_requirements_count': 0,
            'api_endpoints_count': 0,
            'admin_api_endpoints_count': 0,
            'total_endpoints_count': 0,
            'has_data_model': False,
            'data_model_fields_count': 0,
            'complexity_score': 0,
            'complexity_tier': 'unknown',
            'backend_requirements': [],
            'frontend_requirements': [],
            'admin_requirements': [],
            'api_endpoints': [],
            'admin_api_endpoints': [],
            'data_model': None,
        }
        
        try:
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                
                metadata['available'] = True
                metadata['name'] = template_data.get('name', metadata['name'])
                metadata['category'] = template_data.get('category', 'Unknown')
                metadata['description'] = template_data.get('description', metadata['description'])
                
                # Requirements counts
                backend_reqs = template_data.get('backend_requirements', [])
                frontend_reqs = template_data.get('frontend_requirements', [])
                admin_reqs = template_data.get('admin_requirements', [])
                
                metadata['backend_requirements'] = backend_reqs
                metadata['frontend_requirements'] = frontend_reqs
                metadata['admin_requirements'] = admin_reqs
                metadata['backend_requirements_count'] = len(backend_reqs)
                metadata['frontend_requirements_count'] = len(frontend_reqs)
                metadata['admin_requirements_count'] = len(admin_reqs)
                metadata['total_requirements_count'] = len(backend_reqs) + len(frontend_reqs) + len(admin_reqs)
                
                # API endpoints
                api_endpoints = template_data.get('api_endpoints', [])
                admin_api_endpoints = template_data.get('admin_api_endpoints', [])
                
                metadata['api_endpoints'] = api_endpoints
                metadata['admin_api_endpoints'] = admin_api_endpoints
                metadata['api_endpoints_count'] = len(api_endpoints)
                metadata['admin_api_endpoints_count'] = len(admin_api_endpoints)
                metadata['total_endpoints_count'] = len(api_endpoints) + len(admin_api_endpoints)
                
                # Data model info
                data_model = template_data.get('data_model')
                if data_model:
                    metadata['has_data_model'] = True
                    metadata['data_model'] = data_model
                    metadata['data_model_name'] = data_model.get('name', 'Unknown')
                    fields = data_model.get('fields', {})
                    metadata['data_model_fields_count'] = len(fields) if isinstance(fields, dict) else 0
                
                # Calculate complexity score (weighted combination)
                # Higher score = more complex template
                complexity = (
                    metadata['total_requirements_count'] * 3 +  # Requirements weighted 3x
                    metadata['total_endpoints_count'] * 2 +     # Endpoints weighted 2x
                    metadata['data_model_fields_count'] * 1     # Fields weighted 1x
                )
                metadata['complexity_score'] = complexity
                
                # Assign complexity tier
                if complexity <= 15:
                    metadata['complexity_tier'] = 'simple'
                elif complexity <= 30:
                    metadata['complexity_tier'] = 'moderate'
                elif complexity <= 50:
                    metadata['complexity_tier'] = 'complex'
                else:
                    metadata['complexity_tier'] = 'very_complex'
                
        except Exception as e:
            logger.warning(f"Failed to load template metadata for {template_slug}: {e}")
            metadata['error'] = str(e)
        
        return metadata
    
    def _generate_template_comparison(self, config: Dict[str, Any], report: Report) -> Dict[str, Any]:
        """
        Generate template comparison report.
        
        Compares how different models implemented the same template with
        comprehensive metrics including LOC, Docker status, generation stats,
        performance data, AI scores, and security analysis.
        """
        template_slug = config['template_slug']
        filter_models = config.get('filter_models', [])
        
        # Load template metadata first
        template_metadata = self._get_template_metadata(template_slug)
        
        # Find all apps with this template
        apps_query = GeneratedApplication.query.filter(
            GeneratedApplication.template_slug == template_slug
        )
        
        if filter_models:
            apps_query = apps_query.filter(
                GeneratedApplication.model_slug.in_(filter_models)
            )
        
        apps = apps_query.all()
        
        report.update_progress(15)
        db.session.commit()
        
        # Get latest completed analysis for each app
        models_data = []
        all_findings = []
        total_analyses = 0
        
        # Collect per-model comprehensive metrics
        per_model_metrics = {}
        
        for app in apps:
            # Get latest completed task for this app
            task = AnalysisTask.query.filter(
                AnalysisTask.target_model == app.model_slug,
                AnalysisTask.target_app_number == app.app_number,
                AnalysisTask.status.in_([  # type: ignore[union-attr]
                    AnalysisStatus.COMPLETED,
                    AnalysisStatus.PARTIAL_SUCCESS,
                    AnalysisStatus.FAILED
                ])
            ).order_by(AnalysisTask.completed_at.desc()).first()  # type: ignore[union-attr]
            
            if task:
                entry = self._process_task_for_report(task, app.model_slug, app.app_number)
                entry['template_slug'] = template_slug
                # Add model display name
                entry['model_name'] = app.model_slug.replace('_', ' / ').replace('-', ' ').title()
                # Calculate total findings for this model
                entry['total_findings'] = entry.get('findings_count', 0)
                models_data.append(entry)
                
                if entry.get('findings'):
                    all_findings.extend(entry['findings'])
                
                # Count all analyses for this app
                total_analyses += AnalysisTask.query.filter(
                    AnalysisTask.target_model == app.model_slug,
                    AnalysisTask.target_app_number == app.app_number,
                    AnalysisTask.status.in_([AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS])  # type: ignore[union-attr]
                ).count()
            
            # Collect comprehensive metrics for this model
            model_slug = app.model_slug
            if model_slug not in per_model_metrics:
                per_model_metrics[model_slug] = self._get_per_model_metrics(app)
        
        report.update_progress(50)
        db.session.commit()
        
        # Calculate comparison metrics
        severity_counts = self._count_severities(all_findings)
        
        # Find common vs unique issues
        common_issues, unique_issues = self._identify_common_issues(models_data)
        
        # Calculate rankings
        rankings = self._calculate_rankings(models_data)
        
        # Calculate execution metrics
        total_duration = sum(m.get('duration_seconds', 0) or 0 for m in models_data)
        avg_duration = total_duration / len(models_data) if models_data else 0
        
        # Framework distribution
        backend_frameworks = {}
        frontend_frameworks = {}
        for m in models_data:
            bf = m.get('backend_framework')
            ff = m.get('frontend_framework')
            if bf:
                backend_frameworks[bf] = backend_frameworks.get(bf, 0) + 1
            if ff:
                frontend_frameworks[ff] = frontend_frameworks.get(ff, 0) + 1
        
        report.update_progress(70)
        db.session.commit()
        
        # Merge per_model_metrics into models_data for unified view
        for m in models_data:
            model_slug = m.get('model_slug')
            if model_slug and model_slug in per_model_metrics:
                m['quantitative_metrics'] = per_model_metrics[model_slug]
        
        # Calculate LOC-based code density metrics
        code_density = self._calculate_code_density(models_data)
        
        # Calculate generation success metrics
        generation_stats = self._calculate_generation_stats(apps)
        
        # Calculate aggregate performance metrics
        performance_comparison = self._calculate_performance_comparison(apps)
        
        # Calculate aggregate AI scores
        ai_comparison = self._calculate_ai_comparison(apps)
        
        report.update_progress(85)
        db.session.commit()
        
        return {
            'report_type': 'template_comparison',
            'template_slug': template_slug,
            'generated_at': utc_now().isoformat(),
            
            # Template metadata
            'template_metadata': template_metadata,
            
            # Models data with embedded quantitative metrics
            'models': models_data,
            'models_count': len(models_data),
            
            # Summary statistics
            'summary': {
                'template_slug': template_slug,
                'template_name': template_metadata.get('name', template_slug),
                'template_category': template_metadata.get('category', 'Unknown'),
                'template_complexity': template_metadata.get('complexity_tier', 'unknown'),
                'template_complexity_score': template_metadata.get('complexity_score', 0),
                'models_compared': len(models_data),
                'total_analyses': total_analyses,
                'total_findings': len(all_findings),
                'severity_breakdown': severity_counts,
                'common_issues_count': len(common_issues),
                'unique_issues_count': sum(len(v) for v in unique_issues.values()) if isinstance(unique_issues, dict) else len(unique_issues),
                'avg_duration_seconds': avg_duration,
                'total_requirements': template_metadata.get('total_requirements_count', 0),
                'total_endpoints': template_metadata.get('total_endpoints_count', 0),
            },
            
            # Severity breakdown
            'findings_breakdown': severity_counts,
            
            # Rankings
            'rankings': rankings,
            
            # Issue comparison
            'comparison': {
                'common_issues': common_issues[:50],
                'unique_by_model': unique_issues
            },
            
            # Framework distribution
            'framework_distribution': {
                'backend': backend_frameworks,
                'frontend': frontend_frameworks,
            },
            
            # Code density analysis (issues per LOC)
            'code_density': code_density,
            
            # Generation success metrics
            'generation_stats': generation_stats,
            
            # Performance comparison
            'performance_comparison': performance_comparison,
            
            # AI analysis comparison
            'ai_comparison': ai_comparison,
            
            # Sample findings
            'findings': all_findings[:500]
        }
    
    def _get_per_model_metrics(self, app: GeneratedApplication) -> Dict[str, Any]:
        """Get comprehensive metrics for a single model/app."""
        metrics = {
            'available': True,
            'docker': {'available': False},
            'generation': {'available': False},
            'performance': {'available': False},
            'ai_analysis': {'available': False},
            'security': {'available': False},
        }
        
        try:
            # Docker/Container metrics
            metrics['docker'] = {
                'available': True,
                'container_status': app.container_status or 'unknown',
                'is_running': app.container_status == 'running' if app.container_status else False,
            }
            
            # Generation metrics
            metrics['generation'] = {
                'available': True,
                'is_failed': app.is_generation_failed or False,
                'failure_stage': app.failure_stage if app.is_generation_failed else None,
                'automatic_fixes': app.automatic_fixes or 0,
                'llm_fixes': app.llm_fixes or 0,
                'manual_fixes': app.manual_fixes or 0,
                'total_fixes': (app.automatic_fixes or 0) + (app.llm_fixes or 0) + (app.manual_fixes or 0),
                'generation_mode': app.generation_mode or 'unknown',
            }
            
            # LOC metrics
            loc_data = _count_loc_from_files(app.model_slug, [app.app_number])
            if loc_data.get('total_loc', 0) > 0:
                metrics['loc'] = {
                    'available': True,
                    'total_loc': loc_data.get('total_loc', 0),
                    'python_loc': loc_data.get('python_loc', 0),
                    'javascript_loc': loc_data.get('javascript_loc', 0),
                    'jsx_loc': loc_data.get('jsx_loc', 0),
                    'css_loc': loc_data.get('css_loc', 0),
                    'other_loc': loc_data.get('other_loc', 0),
                }
            else:
                metrics['loc'] = {'available': False}
            
            # Performance test metrics
            perf_test = PerformanceTest.query.filter_by(application_id=app.id).order_by(
                PerformanceTest.created_at.desc()
            ).first()
            
            if perf_test:
                metrics['performance'] = {
                    'available': True,
                    'avg_response_time_ms': perf_test.average_response_time,
                    'requests_per_second': perf_test.requests_per_second,
                    'error_rate_percent': perf_test.error_rate,
                    'p95_response_time_ms': perf_test.p95_response_time,
                    'test_date': perf_test.created_at.isoformat() if perf_test.created_at else None,
                }
            
            # AI analysis metrics
            ai_analysis = OpenRouterAnalysis.query.filter_by(application_id=app.id).order_by(
                OpenRouterAnalysis.created_at.desc()
            ).first()
            
            if ai_analysis:
                metrics['ai_analysis'] = {
                    'available': True,
                    'overall_score': ai_analysis.overall_score,
                    'code_quality_score': ai_analysis.code_quality_score,
                    'security_score': ai_analysis.security_score,
                    'maintainability_score': ai_analysis.maintainability_score,
                    'analysis_date': ai_analysis.created_at.isoformat() if ai_analysis.created_at else None,
                }
            
            # Security analysis metrics
            sec_analysis = SecurityAnalysis.query.filter_by(application_id=app.id).order_by(
                SecurityAnalysis.created_at.desc()
            ).first()
            
            if sec_analysis:
                metrics['security'] = {
                    'available': True,
                    'total_issues': sec_analysis.total_issues,
                    'critical_count': sec_analysis.critical_severity_count,
                    'high_count': sec_analysis.high_severity_count,
                    'medium_count': sec_analysis.medium_severity_count,
                    'low_count': sec_analysis.low_severity_count,
                    'analysis_date': sec_analysis.created_at.isoformat() if sec_analysis.created_at else None,
                }
                
        except Exception as e:
            logger.warning(f"Failed to get metrics for {app.model_slug} app {app.app_number}: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def _calculate_code_density(self, models_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate issues per LOC metrics for each model."""
        density_data = {
            'by_model': [],
            'overall': {
                'total_loc': 0,
                'total_findings': 0,
                'avg_issues_per_100_loc': 0,
            },
            'best_density': None,
            'worst_density': None,
        }
        
        total_loc = 0
        total_findings = 0
        
        for m in models_data:
            model_slug = m.get('model_slug')
            qm = m.get('quantitative_metrics', {})
            loc_data = qm.get('loc', {})
            loc = loc_data.get('total_loc', 0) if loc_data.get('available') else 0
            findings = m.get('findings_count', 0) or m.get('total_findings', 0)
            
            issues_per_100_loc = (findings / loc * 100) if loc > 0 else 0
            
            density_entry = {
                'model_slug': model_slug,
                'model_name': m.get('model_name', model_slug),
                'total_loc': loc,
                'total_findings': findings,
                'issues_per_100_loc': round(issues_per_100_loc, 2),
            }
            density_data['by_model'].append(density_entry)
            
            total_loc += loc
            total_findings += findings
        
        density_data['overall']['total_loc'] = total_loc
        density_data['overall']['total_findings'] = total_findings
        density_data['overall']['avg_issues_per_100_loc'] = round(
            (total_findings / total_loc * 100) if total_loc > 0 else 0, 2
        )
        
        # Find best and worst code density
        valid_densities = [d for d in density_data['by_model'] if d['total_loc'] > 0]
        if valid_densities:
            sorted_density = sorted(valid_densities, key=lambda x: x['issues_per_100_loc'])
            density_data['best_density'] = sorted_density[0]
            density_data['worst_density'] = sorted_density[-1]
        
        return density_data
    
    def _calculate_generation_stats(self, apps: List[GeneratedApplication]) -> Dict[str, Any]:
        """Calculate aggregate generation statistics across all models."""
        stats = {
            'total_apps': len(apps),
            'successful_generations': 0,
            'failed_generations': 0,
            'success_rate': 0,
            'total_automatic_fixes': 0,
            'total_llm_fixes': 0,
            'total_manual_fixes': 0,
            'avg_fixes_per_app': 0,
            'by_generation_mode': {},
            'by_failure_stage': {},
        }
        
        for app in apps:
            if app.is_generation_failed:
                stats['failed_generations'] += 1
                stage = app.failure_stage or 'unknown'
                stats['by_failure_stage'][stage] = stats['by_failure_stage'].get(stage, 0) + 1
            else:
                stats['successful_generations'] += 1
            
            stats['total_automatic_fixes'] += app.automatic_fixes or 0
            stats['total_llm_fixes'] += app.llm_fixes or 0
            stats['total_manual_fixes'] += app.manual_fixes or 0
            
            mode = app.generation_mode or 'unknown'
            stats['by_generation_mode'][mode] = stats['by_generation_mode'].get(mode, 0) + 1
        
        if stats['total_apps'] > 0:
            stats['success_rate'] = round(
                stats['successful_generations'] / stats['total_apps'] * 100, 1
            )
            total_fixes = stats['total_automatic_fixes'] + stats['total_llm_fixes'] + stats['total_manual_fixes']
            stats['avg_fixes_per_app'] = round(total_fixes / stats['total_apps'], 2)
        
        return stats
    
    def _calculate_performance_comparison(self, apps: List[GeneratedApplication]) -> Dict[str, Any]:
        """Calculate performance comparison across models."""
        comparison = {
            'available': False,
            'models_with_data': 0,
            'by_model': [],
            'best_response_time': None,
            'best_throughput': None,
            'worst_response_time': None,
            'avg_response_time_ms': 0,
            'avg_rps': 0,
        }
        
        response_times = []
        rps_values = []
        
        for app in apps:
            perf = PerformanceTest.query.filter_by(application_id=app.id).order_by(
                PerformanceTest.created_at.desc()
            ).first()
            
            if perf:
                entry = {
                    'model_slug': app.model_slug,
                    'model_name': app.model_slug.replace('_', ' / ').replace('-', ' ').title(),
                    'avg_response_time_ms': perf.average_response_time,
                    'requests_per_second': perf.requests_per_second,
                    'error_rate_percent': perf.error_rate,
                    'p95_response_time_ms': perf.p95_response_time,
                }
                comparison['by_model'].append(entry)
                
                if perf.average_response_time:
                    response_times.append((entry, perf.average_response_time))
                if perf.requests_per_second:
                    rps_values.append((entry, perf.requests_per_second))
        
        comparison['models_with_data'] = len(comparison['by_model'])
        
        if comparison['models_with_data'] > 0:
            comparison['available'] = True
            
            # Calculate averages
            if response_times:
                comparison['avg_response_time_ms'] = round(
                    sum(rt for _, rt in response_times) / len(response_times), 2
                )
                # Best = lowest response time
                sorted_rt = sorted(response_times, key=lambda x: x[1])
                comparison['best_response_time'] = sorted_rt[0][0]
                comparison['worst_response_time'] = sorted_rt[-1][0]
            
            if rps_values:
                comparison['avg_rps'] = round(
                    sum(rps for _, rps in rps_values) / len(rps_values), 2
                )
                # Best = highest RPS
                sorted_rps = sorted(rps_values, key=lambda x: x[1], reverse=True)
                comparison['best_throughput'] = sorted_rps[0][0]
        
        return comparison
    
    def _calculate_ai_comparison(self, apps: List[GeneratedApplication]) -> Dict[str, Any]:
        """Calculate AI analysis score comparison across models."""
        comparison = {
            'available': False,
            'models_with_data': 0,
            'by_model': [],
            'best_overall': None,
            'best_security': None,
            'best_code_quality': None,
            'avg_scores': {
                'overall': 0,
                'code_quality': 0,
                'security': 0,
                'requirements_compliance': 0,
            },
        }
        
        overall_scores = []
        security_scores = []
        quality_scores = []
        
        for app in apps:
            ai = OpenRouterAnalysis.query.filter_by(application_id=app.id).order_by(
                OpenRouterAnalysis.created_at.desc()
            ).first()
            
            if ai:
                entry = {
                    'model_slug': app.model_slug,
                    'model_name': app.model_slug.replace('_', ' / ').replace('-', ' ').title(),
                    'overall_score': ai.overall_score,
                    'code_quality_score': ai.code_quality_score,
                    'security_score': ai.security_score,
                    'maintainability_score': ai.maintainability_score,
                }
                comparison['by_model'].append(entry)
                
                if ai.overall_score:
                    overall_scores.append((entry, ai.overall_score))
                if ai.security_score:
                    security_scores.append((entry, ai.security_score))
                if ai.code_quality_score:
                    quality_scores.append((entry, ai.code_quality_score))
        
        comparison['models_with_data'] = len(comparison['by_model'])
        
        if comparison['models_with_data'] > 0:
            comparison['available'] = True
            
            # Calculate averages
            if overall_scores:
                comparison['avg_scores']['overall'] = round(
                    sum(s for _, s in overall_scores) / len(overall_scores), 2
                )
                sorted_overall = sorted(overall_scores, key=lambda x: x[1], reverse=True)
                comparison['best_overall'] = sorted_overall[0][0]
            
            if security_scores:
                comparison['avg_scores']['security'] = round(
                    sum(s for _, s in security_scores) / len(security_scores), 2
                )
                sorted_security = sorted(security_scores, key=lambda x: x[1], reverse=True)
                comparison['best_security'] = sorted_security[0][0]
            
            if quality_scores:
                comparison['avg_scores']['code_quality'] = round(
                    sum(s for _, s in quality_scores) / len(quality_scores), 2
                )
                sorted_quality = sorted(quality_scores, key=lambda x: x[1], reverse=True)
                comparison['best_code_quality'] = sorted_quality[0][0]
        
        return comparison
    
    def _calculate_rankings(self, models_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate rankings for template comparison."""
        if not models_data:
            return {}
        
        # Score based on weighted severity (lower is better)
        def calculate_score(m):
            sev = m.get('severity_breakdown') or m.get('severity_counts') or {}
            return (
                (sev.get('critical', 0) or 0) * 100 +
                (sev.get('high', 0) or 0) * 10 +
                (sev.get('medium', 0) or 0) * 3 +
                (sev.get('low', 0) or 0) * 1 +
                (sev.get('info', 0) or 0) * 0.1
            )
        
        # Add score to each model
        for m in models_data:
            m['score'] = calculate_score(m)
        
        # Sort by score (lower is better)
        sorted_models = sorted(models_data, key=lambda x: x.get('score', float('inf')))
        
        best = sorted_models[0] if sorted_models else None
        worst = sorted_models[-1] if sorted_models else None
        
        # Find best by each severity
        by_severity = {}
        for sev in ['critical', 'high', 'medium', 'low']:
            sorted_by_sev = sorted(
                models_data,
                key=lambda x: (x.get('severity_breakdown') or {}).get(sev, 0) or (x.get('severity_counts') or {}).get(sev, 0)
            )
            if sorted_by_sev:
                by_severity[sev] = {
                    'model': sorted_by_sev[0].get('model_slug'),
                    'model_name': sorted_by_sev[0].get('model_name', sorted_by_sev[0].get('model_slug')),
                    'count': (sorted_by_sev[0].get('severity_breakdown') or {}).get(sev, 0) or (sorted_by_sev[0].get('severity_counts') or {}).get(sev, 0)
                }
        
        return {
            'best_overall': {
                'model': best.get('model_slug') if best else None,
                'model_name': best.get('model_name', best.get('model_slug')) if best else None,
                'score': best.get('score') if best else None,
                'total_findings': best.get('total_findings', 0) if best else 0,
            } if best else None,
            'worst_overall': {
                'model': worst.get('model_slug') if worst else None,
                'model_name': worst.get('model_name', worst.get('model_slug')) if worst else None,
                'score': worst.get('score') if worst else None,
                'total_findings': worst.get('total_findings', 0) if worst else 0,
            } if worst else None,
            'by_severity': by_severity,
            'all_ranked': [
                {
                    'rank': i + 1,
                    'model': m.get('model_slug'),
                    'model_name': m.get('model_name', m.get('model_slug')),
                    'score': m.get('score'),
                    'total_findings': m.get('total_findings', 0),
                }
                for i, m in enumerate(sorted_models)
            ]
        }
    
    def _generate_tool_report(self, config: Dict[str, Any], report: Report) -> Dict[str, Any]:
        """
        Generate tool analysis report with comprehensive metrics.
        
        Shows tool effectiveness across all analyses, including:
        - Execution statistics (runs, success rate, duration)
        - Findings distribution (severity, by model, by template)
        - LOC metrics (code analyzed per tool)
        - Effectiveness scores (severity-weighted findings)
        - Template and model coverage
        """
        tool_name = config.get('tool_name')  # Optional - None means all tools
        filter_model = config.get('filter_model')
        filter_app = config.get('filter_app')
        
        # Query completed tasks
        query = AnalysisTask.query.filter(
            AnalysisTask.status.in_([  # type: ignore[union-attr]
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS
            ])
        )
        
        if filter_model:
            query = query.filter(AnalysisTask.target_model == filter_model)
        if filter_app:
            query = query.filter(AnalysisTask.target_app_number == filter_app)
        
        tasks = query.order_by(AnalysisTask.completed_at.desc()).limit(300).all()  # type: ignore[union-attr]
        
        report.update_progress(15)
        db.session.commit()
        
        # Collect tool data across all tasks
        tools_aggregate: Dict[str, Dict[str, Any]] = {}
        tools_by_model: Dict[str, Dict[str, Dict[str, Any]]] = {}
        tools_by_template: Dict[str, Dict[str, Dict[str, Any]]] = {}
        all_findings = []
        
        # Track unique models and templates seen
        models_seen = set()
        templates_seen = set()
        
        # Track LOC per tool (approximate by app)
        tool_loc_tracking: Dict[str, Dict[str, int]] = {}  # tool -> app_key -> loc
        
        for task in tasks:
            result = self.unified_service.load_analysis_results(task.task_id)
            if not result:
                continue
            
            # Get app info for template tracking
            app = GeneratedApplication.query.filter_by(
                model_slug=task.target_model,
                app_number=task.target_app_number
            ).first()
            
            template_slug = app.template_slug if app else 'unknown'
            model_slug = task.target_model
            app_key = f"{model_slug}_{task.target_app_number}"
            
            models_seen.add(model_slug)
            if template_slug:
                templates_seen.add(template_slug)
            
            # Get LOC for this app (cached by app_key)
            app_loc = 0
            if app:
                loc_data = _count_loc_from_files(model_slug, [task.target_app_number])
                app_loc = loc_data.get('total_loc', 0)
            
            # Extract tool data from services OR direct tools
            # result.tools can be:
            # 1. Services dict: {'static-analyzer': {analysis: {...}}, ...}
            # 2. Direct tools dict (AI analyzer): {'code-quality-analyzer': {status: 'success', ...}}
            services = result.tools or {}
            for item_name, item_data in services.items():
                if not isinstance(item_data, dict):
                    continue
                
                # Detect if this is a direct tool entry (AI analyzer) or a service entry
                # Direct tools have 'status' and optionally 'tool_name' at top level, no 'analysis' key
                is_direct_tool = (
                    'status' in item_data and 
                    'analysis' not in item_data and
                    ('tool_name' in item_data or 'results' in item_data or 'metadata' in item_data)
                )
                
                if is_direct_tool:
                    # item_data IS the tool data itself (AI analyzer format)
                    tool_results = {item_name: self._normalize_tool_data(item_data)}
                    service_name = 'ai-analyzer'  # Infer service from direct tool structure
                else:
                    # item_data is a service containing tools
                    tool_results = self._extract_tools_from_service(item_data)
                    service_name = item_name
                
                for t_name, t_data in tool_results.items():
                    # Skip if filtering to specific tool
                    if tool_name and t_name != tool_name:
                        continue
                    
                    # Initialize aggregate entry
                    if t_name not in tools_aggregate:
                        tools_aggregate[t_name] = {
                            'tool_name': t_name,
                            'service': service_name,
                            'executions': 0,
                            'successful': 0,
                            'failed': 0,
                            'skipped': 0,
                            'total_findings': 0,
                            'total_duration': 0.0,
                            'min_duration': float('inf'),
                            'max_duration': 0.0,
                            'findings_by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0},
                            'models_analyzed': set(),
                            'templates_analyzed': set(),
                            'durations': [],
                        }
                        tool_loc_tracking[t_name] = {}
                    
                    agg = tools_aggregate[t_name]
                    agg['executions'] += 1
                    
                    status = t_data.get('status', 'unknown')
                    if status in ('success', 'completed', 'no_issues'):
                        agg['successful'] += 1
                    elif status == 'failed':
                        agg['failed'] += 1
                    elif status == 'skipped':
                        agg['skipped'] += 1
                    
                    findings_count = t_data.get('total_issues', 0)
                    agg['total_findings'] += findings_count
                    
                    duration = t_data.get('duration_seconds', 0) or 0
                    if duration > 0:
                        agg['total_duration'] += duration
                        agg['min_duration'] = min(agg['min_duration'], duration)
                        agg['max_duration'] = max(agg['max_duration'], duration)
                        agg['durations'].append(duration)
                    
                    # Track models and templates per tool
                    agg['models_analyzed'].add(model_slug)
                    if template_slug:
                        agg['templates_analyzed'].add(template_slug)
                    
                    # Track LOC analyzed by this tool (unique per app)
                    if app_key not in tool_loc_tracking[t_name] and app_loc > 0:
                        tool_loc_tracking[t_name][app_key] = app_loc
                    
                    # Count findings by severity
                    for finding in t_data.get('issues', []):
                        sev = finding.get('severity', 'info').lower()
                        if sev in agg['findings_by_severity']:
                            agg['findings_by_severity'][sev] += 1
                        all_findings.append({**finding, 'tool': t_name})
                    
                    # Track by model
                    if model_slug not in tools_by_model:
                        tools_by_model[model_slug] = {}
                    if t_name not in tools_by_model[model_slug]:
                        tools_by_model[model_slug][t_name] = {
                            'executions': 0, 'successful': 0, 'findings': 0, 'duration': 0.0
                        }
                    
                    tbm = tools_by_model[model_slug][t_name]
                    tbm['executions'] += 1
                    if status in ('success', 'completed', 'no_issues'):
                        tbm['successful'] += 1
                    tbm['findings'] += findings_count
                    tbm['duration'] += duration
                    
                    # Track by template
                    if template_slug:
                        if template_slug not in tools_by_template:
                            tools_by_template[template_slug] = {}
                        if t_name not in tools_by_template[template_slug]:
                            tools_by_template[template_slug][t_name] = {
                                'executions': 0, 'successful': 0, 'findings': 0
                            }
                        
                        tbt = tools_by_template[template_slug][t_name]
                        tbt['executions'] += 1
                        if status in ('success', 'completed', 'no_issues'):
                            tbt['successful'] += 1
                        tbt['findings'] += findings_count
        
        report.update_progress(60)
        db.session.commit()
        
        # Finalize aggregates
        tools_list = []
        for t_name, agg in tools_aggregate.items():
            total = agg['executions']
            successful = agg['successful']
            
            # Basic rates
            agg['success_rate'] = round((successful / total * 100), 1) if total > 0 else 0
            agg['failure_rate'] = round((agg['failed'] / total * 100), 1) if total > 0 else 0
            agg['skip_rate'] = round((agg['skipped'] / total * 100), 1) if total > 0 else 0
            
            # Duration metrics
            agg['avg_duration'] = round((agg['total_duration'] / successful), 2) if successful > 0 else 0
            if agg['min_duration'] == float('inf'):
                agg['min_duration'] = 0
            agg['min_duration'] = round(agg['min_duration'], 2)
            agg['max_duration'] = round(agg['max_duration'], 2)
            
            # Calculate median duration
            durations = sorted(agg['durations'])
            if durations:
                mid = len(durations) // 2
                if len(durations) % 2 == 0:
                    agg['median_duration'] = round((durations[mid - 1] + durations[mid]) / 2, 2)
                else:
                    agg['median_duration'] = round(durations[mid], 2)
            else:
                agg['median_duration'] = 0
            del agg['durations']  # Remove raw durations from output
            
            # Findings metrics
            agg['findings_per_run'] = round((agg['total_findings'] / successful), 2) if successful > 0 else 0
            
            # LOC metrics
            tool_loc = sum(tool_loc_tracking.get(t_name, {}).values())
            agg['total_loc_analyzed'] = tool_loc
            agg['findings_per_1000_loc'] = round((agg['total_findings'] / tool_loc * 1000), 2) if tool_loc > 0 else 0
            agg['unique_apps_analyzed'] = len(tool_loc_tracking.get(t_name, {}))
            
            # Convert sets to counts and lists
            agg['models_count'] = len(agg['models_analyzed'])
            agg['templates_count'] = len(agg['templates_analyzed'])
            agg['models_list'] = sorted(list(agg['models_analyzed']))
            agg['templates_list'] = sorted(list(agg['templates_analyzed']))
            del agg['models_analyzed']
            del agg['templates_analyzed']
            
            # Calculate effectiveness score (severity-weighted findings per run)
            sev = agg['findings_by_severity']
            weighted_findings = (
                sev['critical'] * 10 +
                sev['high'] * 5 +
                sev['medium'] * 2 +
                sev['low'] * 1 +
                sev['info'] * 0.1
            )
            agg['effectiveness_score'] = round(weighted_findings / successful, 2) if successful > 0 else 0
            
            # Add display-friendly fields
            agg['display_name'] = t_name.replace('_', ' ').title()
            agg['name'] = t_name
            agg['total_runs'] = agg['executions']
            agg['avg_findings'] = agg['findings_per_run']
            agg['container'] = agg['service']
            
            tools_list.append(agg)
        
        # Sort by execution count
        tools_list.sort(key=lambda x: x['executions'], reverse=True)
        
        severity_counts = self._count_severities(all_findings)
        
        report.update_progress(80)
        db.session.commit()
        
        # Calculate aggregate stats
        total_runs = sum(t['executions'] for t in tools_list)
        total_successful = sum(t['successful'] for t in tools_list)
        total_findings_all = sum(t['total_findings'] for t in tools_list)
        avg_success = round(sum(t['success_rate'] for t in tools_list) / len(tools_list), 1) if tools_list else 0
        
        # Group by service/container
        categories = {}
        for t in tools_list:
            svc = t.get('service', 'unknown')
            if svc not in categories:
                categories[svc] = {
                    'tools_count': 0,
                    'total_findings': 0,
                    'total_runs': 0,
                    'avg_success_rate': 0,
                    'tools': [],
                    'success_rates': []
                }
            categories[svc]['tools_count'] += 1
            categories[svc]['total_findings'] += t['total_findings']
            categories[svc]['total_runs'] += t['executions']
            categories[svc]['tools'].append(t['tool_name'])
            categories[svc]['success_rates'].append(t['success_rate'])
        
        # Calculate avg success rate per category
        for cat_data in categories.values():
            rates = cat_data.pop('success_rates')
            cat_data['avg_success_rate'] = round(sum(rates) / len(rates), 1) if rates else 0
        
        # Find top performers
        top_by_findings = sorted(tools_list, key=lambda x: x['total_findings'], reverse=True)[:5]
        top_by_success = sorted(tools_list, key=lambda x: x['success_rate'], reverse=True)[:5]
        top_by_effectiveness = sorted(tools_list, key=lambda x: x['effectiveness_score'], reverse=True)[:5]
        fastest_tools = sorted([t for t in tools_list if t['avg_duration'] > 0], key=lambda x: x['avg_duration'])[:5]
        slowest_tools = sorted([t for t in tools_list if t['avg_duration'] > 0], key=lambda x: x['avg_duration'], reverse=True)[:5]
        
        # Model coverage statistics
        model_coverage = {
            'total_models': len(models_seen),
            'models_list': sorted(list(models_seen)),
            'tools_per_model': {
                model: {
                    'tools_count': len(tools_by_model.get(model, {})),
                    'total_findings': sum(td.get('findings', 0) for td in tools_by_model.get(model, {}).values())
                }
                for model in models_seen
            }
        }
        
        # Template coverage statistics
        template_coverage = {
            'total_templates': len(templates_seen),
            'templates_list': sorted(list(templates_seen)),
            'tools_per_template': {
                tmpl: {
                    'tools_count': len(tools_by_template.get(tmpl, {})),
                    'total_findings': sum(td.get('findings', 0) for td in tools_by_template.get(tmpl, {}).values())
                }
                for tmpl in templates_seen
            }
        }
        
        # Calculate overall LOC metrics
        total_unique_loc = sum(
            sum(app_locs.values())
            for app_locs in tool_loc_tracking.values()
        )
        
        # Execution timeline metrics
        execution_timeline = {
            'total_duration_seconds': sum(t['total_duration'] for t in tools_list),
            'avg_duration_per_tool': round(
                sum(t['avg_duration'] for t in tools_list) / len(tools_list), 2
            ) if tools_list else 0,
            'fastest_tool': {
                'name': fastest_tools[0]['tool_name'],
                'avg_duration': fastest_tools[0]['avg_duration']
            } if fastest_tools else None,
            'slowest_tool': {
                'name': slowest_tools[0]['tool_name'],
                'avg_duration': slowest_tools[0]['avg_duration']
            } if slowest_tools else None,
        }
        
        # =====================================================================
        # ANALYZER CATEGORIES - Group tools by analyzer type with type-specific metrics
        # =====================================================================
        analyzer_categories = {}
        for analyzer_type, analyzer_info in ANALYZER_CATEGORIES.items():
            # Get tools belonging to this analyzer
            analyzer_tool_names = set(analyzer_info['tools'].keys())
            analyzer_tools = [t for t in tools_list if t['tool_name'] in analyzer_tool_names]
            
            if not analyzer_tools:
                continue
            
            # Aggregate statistics for this analyzer type
            cat_executions = sum(t['executions'] for t in analyzer_tools)
            cat_successful = sum(t['successful'] for t in analyzer_tools)
            cat_findings = sum(t['total_findings'] for t in analyzer_tools)
            cat_failed = sum(t['failed'] for t in analyzer_tools)
            cat_duration = sum(t['total_duration'] for t in analyzer_tools)
            
            # Severity breakdown for this analyzer
            cat_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
            for t in analyzer_tools:
                for sev, count in t['findings_by_severity'].items():
                    if sev in cat_severity:
                        cat_severity[sev] += count
            
            # Calculate severity score (weighted)
            severity_score = (
                cat_severity['critical'] * 10 +
                cat_severity['high'] * 5 +
                cat_severity['medium'] * 2 +
                cat_severity['low'] * 1 +
                cat_severity['info'] * 0.1
            )
            
            # Build tool details for this analyzer
            tool_details = []
            for t in sorted(analyzer_tools, key=lambda x: x['total_findings'], reverse=True):
                tool_meta = analyzer_info['tools'].get(t['tool_name'], {})
                tool_details.append({
                    'name': t['tool_name'],
                    'display_name': t.get('display_name', t['tool_name']),
                    'category': tool_meta.get('category', 'other'),
                    'language': tool_meta.get('language', 'unknown'),
                    'focus': tool_meta.get('focus', ''),
                    'executions': t['executions'],
                    'successful': t['successful'],
                    'success_rate': t['success_rate'],
                    'total_findings': t['total_findings'],
                    'findings_per_run': t['findings_per_run'],
                    'avg_duration': t['avg_duration'],
                    'effectiveness_score': t['effectiveness_score'],
                    'findings_by_severity': t['findings_by_severity'],
                })
            
            # Build analyzer category data
            analyzer_categories[analyzer_type] = {
                'display_name': analyzer_info['display_name'],
                'service': analyzer_info['service'],
                'port': analyzer_info['port'],
                'description': analyzer_info['description'],
                'metrics_focus': analyzer_info['metrics_focus'],
                
                # Summary statistics
                'summary': {
                    'tools_count': len(analyzer_tools),
                    'total_executions': cat_executions,
                    'total_successful': cat_successful,
                    'total_failed': cat_failed,
                    'total_findings': cat_findings,
                    'total_duration': round(cat_duration, 2),
                    'success_rate': round(cat_successful / cat_executions * 100, 1) if cat_executions > 0 else 0,
                    'avg_findings_per_run': round(cat_findings / cat_successful, 2) if cat_successful > 0 else 0,
                    'avg_duration': round(cat_duration / cat_successful, 2) if cat_successful > 0 else 0,
                },
                
                # Severity breakdown
                'severity_breakdown': cat_severity,
                'severity_score': round(severity_score, 1),
                
                # Tool details
                'tools': tool_details,
                'tool_names': [t['name'] for t in tool_details],
                
                # Top tools in this analyzer
                'top_by_findings': tool_details[:3] if len(tool_details) >= 3 else tool_details,
                'top_by_effectiveness': sorted(tool_details, key=lambda x: x['effectiveness_score'], reverse=True)[:3],
            }
        
        # Add analyzer-type-specific metrics where applicable
        # Static analyzer: severity distribution insights
        if 'static' in analyzer_categories:
            static_cat = analyzer_categories['static']
            static_sev = static_cat['severity_breakdown']
            total_static_findings = static_cat['summary']['total_findings']
            static_cat['type_specific'] = {
                'security_findings_ratio': round(
                    (static_sev['critical'] + static_sev['high'] + static_sev['medium']) / total_static_findings * 100, 1
                ) if total_static_findings > 0 else 0,
                'critical_high_count': static_sev['critical'] + static_sev['high'],
                'quality_coverage': [t['name'] for t in static_cat['tools'] if ANALYZER_CATEGORIES['static']['tools'].get(t['name'], {}).get('category') == 'quality'],
                'security_coverage': [t['name'] for t in static_cat['tools'] if ANALYZER_CATEGORIES['static']['tools'].get(t['name'], {}).get('category') == 'security'],
            }
        
        # Dynamic analyzer: runtime security insights
        if 'dynamic' in analyzer_categories:
            dynamic_cat = analyzer_categories['dynamic']
            dynamic_cat['type_specific'] = {
                'runtime_vulnerabilities': dynamic_cat['summary']['total_findings'],
                'owasp_tool_present': any(t['name'] in ('zap', 'owasp-zap') for t in dynamic_cat['tools']),
                'port_scan_present': any(t['name'] == 'nmap' for t in dynamic_cat['tools']),
                'requires_running_app': True,
            }
        
        # Performance tester: performance-specific insights
        if 'performance' in analyzer_categories:
            perf_cat = analyzer_categories['performance']
            perf_cat['type_specific'] = {
                'tools_with_load_testing': [t['name'] for t in perf_cat['tools'] if t['name'] in ('locust', 'artillery', 'ab')],
                'tools_with_async_testing': [t['name'] for t in perf_cat['tools'] if t['name'] == 'aiohttp'],
                'requires_running_app': True,
                'measures': ['requests_per_second', 'latency_percentiles', 'error_rate', 'throughput'],
            }
        
        # AI analyzer: AI-specific insights  
        if 'ai' in analyzer_categories:
            ai_cat = analyzer_categories['ai']
            ai_cat['type_specific'] = {
                'llm_based_analysis': True,
                'analyzes': ['requirements_compliance', 'code_quality', 'best_practices', 'security_patterns'],
                'requires_api_key': True,
            }
        
        # Calculate analyzer summary stats
        analyzer_summary = {
            'total_analyzer_types': len(analyzer_categories),
            'analyzer_types_present': list(analyzer_categories.keys()),
            'findings_by_analyzer': {
                atype: analyzer_categories[atype]['summary']['total_findings']
                for atype in analyzer_categories
            },
            'executions_by_analyzer': {
                atype: analyzer_categories[atype]['summary']['total_executions']
                for atype in analyzer_categories
            },
            'success_rates_by_analyzer': {
                atype: analyzer_categories[atype]['summary']['success_rate']
                for atype in analyzer_categories
            },
        }

        return {
            'report_type': 'tool_analysis',
            'generated_at': utc_now().isoformat(),
            'filter': {
                'tool_name': tool_name,
                'model': filter_model,
                'app': filter_app
            },
            
            # Tool data
            'tools': tools_list,
            'tools_count': len(tools_list),
            'total_executions': total_runs,
            
            # Summary statistics
            'summary': {
                'tools_analyzed': len(tools_list),
                'total_runs': total_runs,
                'total_successful': total_successful,
                'total_failed': sum(t['failed'] for t in tools_list),
                'total_findings': total_findings_all,
                'avg_success_rate': avg_success,
                'severity_breakdown': severity_counts,
                'models_covered': len(models_seen),
                'templates_covered': len(templates_seen),
                'total_loc_analyzed': total_unique_loc,
                'findings_per_1000_loc': round(
                    (total_findings_all / total_unique_loc * 1000), 2
                ) if total_unique_loc > 0 else 0
            },
            
            # Severity breakdown
            'findings_breakdown': severity_counts,
            
            # =====================================================================
            # NEW: ANALYZER CATEGORIES - Customized by analyzer type
            # =====================================================================
            'analyzer_categories': analyzer_categories,
            'analyzer_summary': analyzer_summary,
            
            # Categories (by service/container) - legacy grouping
            'categories': categories,
            
            # Cross-reference by model
            'by_model': tools_by_model,
            
            # Cross-reference by template
            'by_template': tools_by_template,
            
            # Model coverage
            'model_coverage': model_coverage,
            
            # Template coverage
            'template_coverage': template_coverage,
            
            # Execution timing
            'execution_timeline': execution_timeline,
            
            # Top performers
            'top_performers': {
                'by_findings': [
                    {'name': t['tool_name'], 'findings': t['total_findings'], 'runs': t['executions']}
                    for t in top_by_findings
                ],
                'by_success_rate': [
                    {'name': t['tool_name'], 'success_rate': t['success_rate'], 'runs': t['executions']}
                    for t in top_by_success
                ],
                'by_effectiveness': [
                    {'name': t['tool_name'], 'effectiveness_score': t['effectiveness_score'], 'runs': t['executions']}
                    for t in top_by_effectiveness
                ],
                'fastest': [
                    {'name': t['tool_name'], 'avg_duration': t['avg_duration'], 'runs': t['executions']}
                    for t in fastest_tools
                ],
                'slowest': [
                    {'name': t['tool_name'], 'avg_duration': t['avg_duration'], 'runs': t['executions']}
                    for t in slowest_tools
                ]
            },
            
            # Sample findings
            'findings': all_findings[:500]
        }
    
    # ==========================================================================
    # GENERATION ANALYTICS
    # ==========================================================================
    
    def _generate_generation_analytics(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate analytics about app generation success/failure patterns.
        
        Provides insights into:
        - Success rates by model and template
        - Common failure stages and error patterns
        - Fix effectiveness (automatic, LLM, manual)
        - Generation attempt statistics
        """
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # Get filter parameters
        model_filter = config.get('model_slug')
        template_filter = config.get('template_slug')
        days_back = config.get('days_back', 30)
        
        # Base query
        query = GeneratedApplication.query
        
        # Apply filters
        if model_filter:
            query = query.filter(GeneratedApplication.model_slug == model_filter)
        if template_filter:
            query = query.filter(GeneratedApplication.template_name == template_filter)
        if days_back:
            cutoff = datetime.utcnow() - timedelta(days=days_back)
            query = query.filter(GeneratedApplication.created_at >= cutoff)
        
        # Get all matching apps
        apps = query.all()
        
        if not apps:
            return {
                'status': 'no_data',
                'message': 'No generated applications found matching criteria',
                'filters': {
                    'model_slug': model_filter,
                    'template_slug': template_filter,
                    'days_back': days_back
                }
            }
        
        # Aggregate statistics
        total_apps = len(apps)
        successful_apps = [a for a in apps if not a.is_generation_failed]
        failed_apps = [a for a in apps if a.is_generation_failed]
        
        # Model breakdown
        models_stats = {}
        for app in apps:
            slug = app.model_slug or 'unknown'
            if slug not in models_stats:
                models_stats[slug] = {'total': 0, 'success': 0, 'failed': 0, 'attempts_sum': 0}
            models_stats[slug]['total'] += 1
            models_stats[slug]['attempts_sum'] += app.generation_attempts or 1
            if app.is_generation_failed:
                models_stats[slug]['failed'] += 1
            else:
                models_stats[slug]['success'] += 1
        
        # Calculate success rates per model
        for slug, stats in models_stats.items():
            stats['success_rate'] = round((stats['success'] / stats['total']) * 100, 1) if stats['total'] > 0 else 0
            stats['avg_attempts'] = round(stats['attempts_sum'] / stats['total'], 2) if stats['total'] > 0 else 0
        
        # Template breakdown
        templates_stats = {}
        for app in apps:
            tmpl = app.template_name or 'unknown'
            if tmpl not in templates_stats:
                templates_stats[tmpl] = {'total': 0, 'success': 0, 'failed': 0}
            templates_stats[tmpl]['total'] += 1
            if app.is_generation_failed:
                templates_stats[tmpl]['failed'] += 1
            else:
                templates_stats[tmpl]['success'] += 1
        
        for tmpl, stats in templates_stats.items():
            stats['success_rate'] = round((stats['success'] / stats['total']) * 100, 1) if stats['total'] > 0 else 0
        
        # Failure stage analysis
        failure_stages = {}
        error_patterns = {}
        for app in failed_apps:
            stage = app.failure_stage or 'unknown'
            failure_stages[stage] = failure_stages.get(stage, 0) + 1
            
            # Extract error pattern
            if app.error_message:
                pattern = self._extract_error_pattern(app.error_message)
                error_patterns[pattern] = error_patterns.get(pattern, 0) + 1
        
        # Fix effectiveness
        fix_stats = {
            'automatic_fixes': sum(1 for a in apps if a.automatic_fixes and a.automatic_fixes > 0),
            'llm_fixes': sum(1 for a in apps if a.llm_fixes and a.llm_fixes > 0),
            'manual_fixes': sum(1 for a in apps if a.manual_fixes and a.manual_fixes > 0),
            'retry_fixes': sum(1 for a in apps if a.retry_fixes and a.retry_fixes > 0),
            'total_automatic_fixes': sum(a.automatic_fixes or 0 for a in apps),
            'total_llm_fixes': sum(a.llm_fixes or 0 for a in apps),
            'total_manual_fixes': sum(a.manual_fixes or 0 for a in apps),
            'total_retry_fixes': sum(a.retry_fixes or 0 for a in apps)
        }
        
        # Generation attempts distribution
        attempts_distribution = {}
        for app in apps:
            attempts = app.generation_attempts or 1
            attempts_distribution[attempts] = attempts_distribution.get(attempts, 0) + 1
        
        # Recent failures (last 10)
        recent_failures = []
        for app in sorted(failed_apps, key=lambda a: a.last_error_at or a.created_at or datetime.min, reverse=True)[:10]:
            recent_failures.append({
                'model_slug': app.model_slug,
                'app_number': app.app_number,
                'template': app.template_name,
                'failure_stage': app.failure_stage,
                'error_message': (app.error_message[:200] + '...') if app.error_message and len(app.error_message) > 200 else app.error_message,
                'attempts': app.generation_attempts,
                'timestamp': app.last_error_at.isoformat() if app.last_error_at else None
            })
        
        # Sort models and templates by success rate
        sorted_models = sorted(
            [{'model': k, **v} for k, v in models_stats.items()],
            key=lambda x: x['success_rate'],
            reverse=True
        )
        sorted_templates = sorted(
            [{'template': k, **v} for k, v in templates_stats.items()],
            key=lambda x: x['success_rate'],
            reverse=True
        )
        
        # Sort error patterns by frequency
        sorted_errors = sorted(
            [{'pattern': k, 'count': v} for k, v in error_patterns.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:20]  # Top 20 error patterns
        
        return {
            'summary': {
                'total_apps': total_apps,
                'successful': len(successful_apps),
                'failed': len(failed_apps),
                'success_rate': round((len(successful_apps) / total_apps) * 100, 1) if total_apps > 0 else 0,
                'models_analyzed': len(models_stats),
                'templates_analyzed': len(templates_stats)
            },
            'filters_applied': {
                'model_slug': model_filter,
                'template_slug': template_filter,
                'days_back': days_back
            },
            'by_model': sorted_models,
            'by_template': sorted_templates,
            'failure_analysis': {
                'by_stage': [
                    {'stage': k, 'count': v} 
                    for k, v in sorted(failure_stages.items(), key=lambda x: x[1], reverse=True)
                ],
                'error_patterns': sorted_errors,
                'recent_failures': recent_failures
            },
            'fix_effectiveness': fix_stats,
            'attempts_distribution': [
                {'attempts': k, 'count': v}
                for k, v in sorted(attempts_distribution.items())
            ]
        }
    
    def _extract_error_pattern(self, error_message: str) -> str:
        """Extract a normalized error pattern for grouping similar errors."""
        if not error_message:
            return 'unknown'
        
        # Normalize: lowercase, truncate, remove variable parts
        pattern = error_message.lower()[:100]
        
        # Remove common variable parts (file paths, line numbers, etc.)
        import re
        pattern = re.sub(r'line \d+', 'line N', pattern)
        pattern = re.sub(r'column \d+', 'column N', pattern)
        pattern = re.sub(r'/[\w/.-]+', '/PATH', pattern)
        pattern = re.sub(r"'[\w_]+'", "'VAR'", pattern)
        pattern = re.sub(r'"[\w_]+"', '"VAR"', pattern)
        
        return pattern.strip()
    
    # ==========================================================================
    # HELPERS
    # ==========================================================================
    
    def _validate_config(self, report_type: str, config: Dict[str, Any]) -> None:
        """Validate config for report type."""
        if report_type == 'model_analysis':
            if not config.get('model_slug'):
                raise ValueError("model_slug is required for model_analysis")
        elif report_type == 'template_comparison':
            if not config.get('template_slug'):
                raise ValueError("template_slug is required for template_comparison")
        elif report_type == 'tool_analysis':
            pass  # All fields optional
        elif report_type == 'generation_analytics':
            pass  # All fields optional - model_slug, template_slug, days_back
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    
    def _generate_title(self, report_type: str, config: Dict[str, Any]) -> str:
        """Generate default title."""
        if report_type == 'model_analysis':
            return f"Model Analysis: {config.get('model_slug', 'Unknown')}"
        elif report_type == 'template_comparison':
            return f"Template Comparison: {config.get('template_slug', 'Unknown')}"
        elif report_type == 'tool_analysis':
            tool = config.get('tool_name', 'All Tools')
            return f"Tool Analysis: {tool}"
        elif report_type == 'generation_analytics':
            model = config.get('model_slug')
            template = config.get('template_slug')
            if model and template:
                return f"Generation Analytics: {model} / {template}"
            elif model:
                return f"Generation Analytics: {model}"
            elif template:
                return f"Generation Analytics: Template {template}"
            return "Generation Analytics: All Models & Templates"
        return "Analysis Report"
    
    def _process_task_for_report(
        self,
        task: AnalysisTask,
        model_slug: str,
        app_number: int
    ) -> Dict[str, Any]:
        """Process a single task into report entry format with comprehensive data."""
        # Get app metadata first - needed for all cases
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        # Try alternate slug if not found
        if not app:
            for variant in generate_slug_variants(model_slug):
                app = GeneratedApplication.query.filter_by(
                    model_slug=variant,
                    app_number=app_number
                ).first()
                if app:
                    break
        
        # Calculate duration from task timestamps
        duration = task.actual_duration or 0.0
        if not duration and task.completed_at and task.started_at:
            duration = (task.completed_at - task.started_at).total_seconds()
        
        # Calculate queue time
        queue_time = task.queue_time or 0.0
        if not queue_time and task.started_at and task.created_at:
            queue_time = (task.started_at - task.created_at).total_seconds()
        
        # Map task status to display status
        status_map = {
            AnalysisStatus.COMPLETED: 'completed',
            AnalysisStatus.PARTIAL_SUCCESS: 'partial',
            AnalysisStatus.FAILED: 'failed',
            AnalysisStatus.CANCELLED: 'cancelled',
            AnalysisStatus.RUNNING: 'running',
            AnalysisStatus.PENDING: 'pending'
        }
        display_status = status_map.get(task.status, str(task.status.value) if task.status else 'unknown')
        
        # Determine has_analysis based on task status, not result availability
        has_analysis = task.status in (
            AnalysisStatus.COMPLETED, 
            AnalysisStatus.PARTIAL_SUCCESS
        )
        
        # Build base entry with all task/app data from DB
        base_entry = {
            'app_number': app_number,
            'model_slug': model_slug,
            'task_id': task.task_id,
            'status': display_status,
            'task_status': task.status.value if task.status else 'unknown',  # Raw status for JS
            'has_analysis': has_analysis,
            'error_message': task.error_message,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'duration_seconds': duration,
            'queue_time_seconds': queue_time,
            'retry_count': task.retry_count or 0,
            # App metadata
            'app_type': app.app_type if app else None,
            'template_slug': app.template_slug if app else None,
            'provider': app.provider if app else None,
            'backend_framework': app.backend_framework if app else None,
            'frontend_framework': app.frontend_framework if app else None,
            'generation_status': app.generation_status.value if app and app.generation_status else None,
            'generation_mode': app.generation_mode.value if app and hasattr(app, 'generation_mode') and app.generation_mode else None,
            'container_status': app.container_status if app else None,
            # Generation fix counters (correct attribute names from model)
            'generation_failed': app.is_generation_failed if app else False,
            'failure_stage': app.failure_stage if app else None,
            'generation_attempts': getattr(app, 'generation_attempts', 1) if app else 1,
            'retry_fixes': getattr(app, 'retry_fixes', 0) if app else 0,
            'automatic_fixes': getattr(app, 'automatic_fixes', 0) if app else 0,
            'llm_fixes': getattr(app, 'llm_fixes', 0) if app else 0,
            'manual_fixes': getattr(app, 'manual_fixes', 0) if app else 0,
        }
        
        # Get severity from DB as fallback (always available)
        db_severity = task.get_severity_breakdown() or {}
        db_issues_count = task.issues_found or 0
        
        # Try to load full results for detailed findings
        result = self.unified_service.load_analysis_results(task.task_id)
        
        # Initialize with DB fallback values
        severity_counts = db_severity or {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        findings_count = db_issues_count
        findings = []
        tools = {}
        subtasks_data = []
        
        if result and result.raw_data:
            # Have full results - extract detailed data
            raw = result.raw_data
            results_wrapper = raw.get('results', {})
            summary = raw.get('summary') or results_wrapper.get('summary') or {}
            
            # Extract findings
            findings = raw.get('findings') or results_wrapper.get('findings') or []
            
            # Get severity counts from results, fallback to DB, or compute from findings
            result_severity = summary.get('severity_breakdown') or summary.get('findings_by_severity')
            if result_severity:
                severity_counts = result_severity
            elif findings:
                severity_counts = self._count_severities(findings)
            elif db_severity:
                severity_counts = db_severity
            
            # Update findings count
            if findings:
                findings_count = len(findings)
            elif db_issues_count:
                findings_count = db_issues_count
            
            # Extract tools
            tools = raw.get('tools') or results_wrapper.get('tools') or {}
            if not tools:
                tools = self._extract_tools_from_services(raw.get('services', {}))
            
            # Extract services for subtask breakdown
            services = raw.get('services', {})
            for svc_name, svc_data in services.items():
                if isinstance(svc_data, dict):
                    subtasks_data.append({
                        'service': svc_name,
                        'status': svc_data.get('status', 'unknown'),
                        'tools_count': len(svc_data.get('analysis', {}).get('results', {})) if isinstance(svc_data.get('analysis'), dict) else 0,
                        'duration': svc_data.get('metadata', {}).get('duration_seconds') if isinstance(svc_data.get('metadata'), dict) else None
                    })
        else:
            # No result file - use DB data as-is
            # Try to get result_summary from task for tool data
            task_summary = task.get_result_summary()
            if task_summary:
                # Extract what we can from DB result_summary
                if 'tools' in task_summary:
                    tools = task_summary['tools']
                if 'findings' in task_summary:
                    findings = task_summary['findings'][:50]  # Limit
                    findings_count = len(task_summary.get('findings', []))
                if 'summary' in task_summary:
                    sum_data = task_summary['summary']
                    if 'severity_breakdown' in sum_data:
                        severity_counts = sum_data['severity_breakdown']
        
        # Ensure severity_counts has all required keys
        for key in ['critical', 'high', 'medium', 'low', 'info']:
            if key not in severity_counts:
                severity_counts[key] = 0
        
        # Get subtask info from DB if we have a main task
        if task.is_main_task:
            db_subtasks = task.get_all_subtasks()
            for st in db_subtasks:
                if not any(s['service'] == st.service_name for s in subtasks_data):
                    subtasks_data.append({
                        'service': st.service_name,
                        'status': st.status.value if st.status else 'unknown',
                        'task_id': st.task_id,
                        'issues_found': st.issues_found or 0,
                        'duration': st.actual_duration
                    })
        
        # Merge all data
        base_entry.update({
            'findings_count': findings_count,
            'severity_counts': severity_counts,
            'severity_breakdown': severity_counts,  # Alias for template
            'tools': tools,
            'findings': findings[:50],  # Limit per app
            'subtasks': subtasks_data,
            'has_subtasks': len(subtasks_data) > 0,
            # Calculated metrics (using correct attribute names from model)
            'total_fixes': (
                (getattr(app, 'automatic_fixes', 0) or 0) +
                (getattr(app, 'llm_fixes', 0) or 0) +
                (getattr(app, 'manual_fixes', 0) or 0)
            ) if app else 0
        })
        
        return base_entry
    
    def _extract_tools_from_services(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Extract flat tool map from nested services structure."""
        tools = {}
        
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            tool_results = self._extract_tools_from_service(service_data)
            for tool_name, tool_data in tool_results.items():
                tool_data['service'] = service_name
                tools[tool_name] = tool_data
        
        return tools
    
    def _extract_tools_from_service(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tool results from a single service.
        
        Handles multiple result structures:
        1. Static analyzer: analysis.results.{language}.{tool}
        2. AI analyzer: analysis.tools.{tool}
        3. Dynamic/Perf: analysis.results.{tool} or tool_results.{tool}
        """
        tools = {}
        
        analysis = service_data.get('analysis', {})
        if not isinstance(analysis, dict):
            return tools
        
        # 1. AI Analyzer structure: analysis.tools.{tool_name}
        ai_tools = analysis.get('tools', {})
        if isinstance(ai_tools, dict):
            for tool_name, tool_data in ai_tools.items():
                if isinstance(tool_data, dict) and 'status' in tool_data:
                    tools[tool_name] = self._normalize_tool_data(tool_data)
        
        # 2. Static analyzer structure: analysis.results.{language}.{tool}
        results = analysis.get('results', {})
        if isinstance(results, dict):
            for key, value in results.items():
                if isinstance(value, dict):
                    # Check if it's a language wrapper (has tool children)
                    has_tool_children = any(
                        isinstance(v, dict) and ('status' in v or 'executed' in v)
                        for v in value.values()
                        if isinstance(v, dict) and not str(v).startswith('_')
                    )
                    
                    if has_tool_children:
                        # Language wrapper - extract tools
                        for tool_name, tool_data in value.items():
                            if isinstance(tool_data, dict) and ('status' in tool_data or 'executed' in tool_data):
                                tools[tool_name] = self._normalize_tool_data(tool_data)
                    elif 'status' in value or 'executed' in value:
                        # Direct tool entry
                        tools[key] = self._normalize_tool_data(value)
        
        # 3. Direct tool_results structure (dynamic/perf analyzers)
        tool_results = analysis.get('tool_results', {}) or service_data.get('tool_results', {})
        if isinstance(tool_results, dict):
            for tool_name, tool_data in tool_results.items():
                if isinstance(tool_data, dict) and tool_name not in tools:
                    tools[tool_name] = self._normalize_tool_data(tool_data)
        
        return tools
    
    def _normalize_tool_data(self, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize tool data to consistent format."""
        status = tool_data.get('status', 'unknown')
        if status in ('success', 'completed', 'no_issues'):
            status = 'success'
        elif tool_data.get('executed') == False:
            status = 'skipped'
        
        return {
            'status': status,
            'total_issues': tool_data.get('total_issues') or tool_data.get('issue_count', 0),
            'duration_seconds': tool_data.get('duration_seconds', 0) or 0,
            'issues': tool_data.get('issues', []),
            'executed': tool_data.get('executed', True)
        }
    
    def _count_severities(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count findings by severity."""
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for f in findings:
            sev = str(f.get('severity', 'info')).lower()
            if sev in counts:
                counts[sev] += 1
        return counts
    
    def _calculate_metrics(self, apps_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistical metrics for apps."""
        if not apps_data:
            return {}
        
        findings_counts = [a.get('findings_count', 0) for a in apps_data]
        durations = [a.get('duration_seconds', 0) for a in apps_data if a.get('duration_seconds', 0) > 0]
        
        metrics = {
            'findings_distribution': {
                'mean': statistics.mean(findings_counts) if findings_counts else 0,
                'median': statistics.median(findings_counts) if findings_counts else 0,
                'min': min(findings_counts) if findings_counts else 0,
                'max': max(findings_counts) if findings_counts else 0,
                'total': sum(findings_counts)
            }
        }
        
        if len(findings_counts) > 1:
            metrics['findings_distribution']['std_dev'] = statistics.stdev(findings_counts)
        
        if durations:
            metrics['duration_statistics'] = {
                'mean': statistics.mean(durations),
                'median': statistics.median(durations),
                'total': sum(durations)
            }
        
        return metrics
    
    def _identify_common_issues(self, models_data: List[Dict[str, Any]]) -> tuple:
        """Identify issues common across models vs unique to specific models."""
        # Group findings by message/rule
        issue_occurrences: Dict[str, List[str]] = {}
        
        for model in models_data:
            model_slug = model.get('model_slug', 'unknown')
            for finding in model.get('findings', []):
                key = f"{finding.get('tool', '')}:{finding.get('message', '')[:100]}"
                if key not in issue_occurrences:
                    issue_occurrences[key] = []
                if model_slug not in issue_occurrences[key]:
                    issue_occurrences[key].append(model_slug)
        
        # Categorize as common (>50% of models) or unique
        threshold = len(models_data) / 2
        common = []
        unique: Dict[str, List[Dict[str, Any]]] = {}
        
        for key, models in issue_occurrences.items():
            parts = key.split(':', 1)
            issue_info = {'tool': parts[0], 'message': parts[1] if len(parts) > 1 else '', 'models': models}
            
            if len(models) >= threshold:
                common.append(issue_info)
            else:
                for model in models:
                    if model not in unique:
                        unique[model] = []
                    unique[model].append(issue_info)
        
        return common, unique
    
    def _extract_summary(self, report_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract quick summary for list display."""
        summary = data.get('summary', {})
        
        if report_type == 'model_analysis':
            return {
                'model_slug': data.get('model_slug'),
                'apps_count': data.get('apps_count', 0),
                'total_findings': summary.get('total_findings', 0),
                'critical': summary.get('severity_breakdown', {}).get('critical', 0)
            }
        elif report_type == 'template_comparison':
            return {
                'template_slug': data.get('template_slug'),
                'models_count': data.get('models_count', 0),
                'total_findings': summary.get('total_findings', 0),
                'common_issues': summary.get('common_issues_count', 0)
            }
        elif report_type == 'tool_analysis':
            return {
                'tools_count': data.get('tools_count', 0),
                'total_executions': data.get('total_executions', 0),
                'total_findings': summary.get('total_findings', 0)
            }
        elif report_type == 'generation_analytics':
            return {
                'total_apps': summary.get('total_apps', 0),
                'successful': summary.get('successful', 0),
                'failed': summary.get('failed', 0),
                'success_rate': summary.get('success_rate', 0),
                'models_analyzed': summary.get('models_analyzed', 0),
                'templates_analyzed': summary.get('templates_analyzed', 0)
            }
        
        return summary


# Singleton accessor
_report_service: Optional[ReportService] = None


def get_report_service() -> ReportService:
    """Get singleton ReportService instance."""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
