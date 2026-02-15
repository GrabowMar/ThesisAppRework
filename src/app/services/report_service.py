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
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Literal

from ..extensions import db
from ..models import (
    Report, AnalysisTask, AnalysisResult, GeneratedApplication, ModelCapability,
    PerformanceTest, SecurityAnalysis, OpenRouterAnalysis
)
from ..constants import AnalysisStatus, ReportFilterMode
from ..utils.time import utc_now
from ..utils.slug_utils import normalize_model_slug, generate_slug_variants
from .unified_result_service import UnifiedResultService
from .service_locator import ServiceLocator
from .reports import count_loc_from_generated_files, collect_finding_analytics

logger = logging.getLogger(__name__)

ReportType = Literal[
    'model_analysis',
    'template_comparison',
    'tool_analysis',
    'generation_analytics',
    'comprehensive'
]


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
            'requirements-scanner': {'category': 'ai', 'language': 'multi', 'focus': 'requirements compliance'},
            'curl-endpoint-tester': {'category': 'ai', 'language': 'runtime', 'focus': 'endpoint verification'},
            'code-quality-analyzer': {'category': 'ai', 'language': 'multi', 'focus': 'code quality analysis'},
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
    'ai': ['ai-analyzer', 'ai-review', 'requirements-check', 'requirements-scanner', 'curl-endpoint-tester', 'code-quality-analyzer'],
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
        expires_in_days: int = 30,
        filter_mode: ReportFilterMode = ReportFilterMode.ALL_ANALYZERS
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
            filter_mode: Analyzer filter mode (all/exclude_dynamic_perf/only_dynamic_perf)
            
        Returns:
            Report model instance with data populated
        """
        # Validate config
        self._validate_config(report_type, config)
        
        # Add filter_mode to config for generators
        config['filter_mode'] = filter_mode.value if isinstance(filter_mode, ReportFilterMode) else filter_mode
        
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
            elif report_type == 'comprehensive':
                data = self._generate_comprehensive_report(config, report)

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
            elif report.report_type == 'generation_analytics':
                new_data = self._generate_generation_analytics(config, report)
            elif report.report_type == 'comprehensive':
                new_data = self._generate_comprehensive_report(config, report)
            else:
                logger.error(f"Unknown report type: {report.report_type}")
                raise ValueError(f"Unknown report type: {report.report_type}")
            
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
        # Only include main tasks (not subtasks) for report grouping
        query = AnalysisTask.query.filter(
            AnalysisTask.target_model.in_(slug_variants),
            AnalysisTask.status.in_([  # type: ignore[union-attr]
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS,
                AnalysisStatus.FAILED,
                AnalysisStatus.CANCELLED
            ]),
            db.or_(
                AnalysisTask.is_main_task.is_(True),
                AnalysisTask.parent_task_id.is_(None)
            )
        )
        
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])  # type: ignore[operator]
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])  # type: ignore[operator]
        
        max_app_number = config.get('max_app_number')
        if max_app_number:
            query = query.filter(AnalysisTask.target_app_number <= max_app_number)
        
        tasks = query.order_by(
            AnalysisTask.target_app_number,
            AnalysisTask.completed_at.desc()  # type: ignore[union-attr]
        ).all()
        
        report.update_progress(20)
        db.session.commit()
        
        # Group by app and get best task per app
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
            # Pick best task: prefer one with most issues_found (indicates complete analysis)
            best_task = max(app_tasks, key=lambda t: (t.issues_found or 0, t.completed_at or t.created_at))
            
            app_entry = self._process_task_for_report(best_task, model_slug, app_number)
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
        # IMPORTANT: Use per-app severity_counts (from DB/full results), NOT from
        # the truncated all_findings list (which is capped at 50 findings per app).
        aggregated_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for app_entry in apps_data:
            app_sev = app_entry.get('severity_counts', {})
            for sev_key in aggregated_severity:
                aggregated_severity[sev_key] += app_sev.get(sev_key, 0)
        severity_counts = aggregated_severity

        # Correct total findings from per-app findings_count (not truncated findings list)
        correct_total_findings = sum(a.get('findings_count', 0) for a in apps_data)

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
        loc_metrics = count_loc_from_generated_files(model_slug, app_numbers)
        
        # Calculate issues_per_100_loc if we have LOC data
        # Use correct_total_findings (from findings_count), NOT len(all_findings) which is truncated
        total_loc = loc_metrics.get('total_loc', 0)
        if total_loc > 0:
            loc_metrics['issues_per_100_loc'] = round((correct_total_findings / total_loc) * 100, 4)
        else:
            loc_metrics['issues_per_100_loc'] = None

        # Add issues_count and issues_per_100_loc to each per_app entry
        # Use findings_count (correct total), NOT len(findings) which is capped at 50 per app
        findings_per_app = {}
        for app_entry in apps_data:
            app_num = app_entry.get('app_number')
            if app_num is not None:
                findings_per_app[app_num] = app_entry.get('findings_count', 0)
        
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

        # Collect finding analytics from DB (bypasses 50-finding cap)
        task_ids_for_analytics = [t.task_id for t in tasks]
        finding_analytics = collect_finding_analytics(task_ids_for_analytics)

        # Build per-app LOC list for scatter chart (LOC vs findings)
        scatter_data = []
        for app_entry in apps_data:
            app_num = app_entry.get('app_number')
            per_app = loc_metrics.get('per_app', {}).get(app_num, {})
            app_loc = per_app.get('total_loc', 0)
            if app_loc > 0:
                scatter_data.append({
                    'app_number': app_num,
                    'loc': app_loc,
                    'findings': app_entry.get('findings_count', 0),
                })

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
                'total_findings': correct_total_findings,
                'severity_breakdown': severity_counts,
                # Some tools do not provide a standardized severity mapping.
                'unclassified_findings': max(0, correct_total_findings - sum(severity_counts.values())),
                'avg_findings_per_app': correct_total_findings / len(apps_data) if apps_data else 0,
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
            # NEW: Deep finding analytics from DB (CWE, categories, confidence, file hotspots)
            'finding_analytics': finding_analytics,
            # NEW: Scatter chart data (LOC vs findings per app)
            'scatter_data': scatter_data,
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
        apps_total = len(apps)

        # This report is defined as *cross-model* comparison for a template.
        # Some templates can have multiple runs per model (e.g., reproducibility replications).
        # To keep the report semantically correct (one row per model), select the lowest
        # app_number per model and record how many extra runs were excluded.
        selected_by_model: Dict[str, GeneratedApplication] = {}
        replications_excluded = 0
        for app in apps:
            slug = app.model_slug or 'unknown'
            cur = selected_by_model.get(slug)
            if cur is None:
                selected_by_model[slug] = app
                continue
            # Keep the earliest app_number as the representative for cross-model comparison.
            if (app.app_number or 1_000_000) < (cur.app_number or 1_000_000):
                selected_by_model[slug] = app
                replications_excluded += 1
            else:
                replications_excluded += 1

        apps = list(selected_by_model.values())
        
        report.update_progress(15)
        db.session.commit()
        
        # Get latest completed analysis for each app
        models_data = []
        all_findings = []
        total_analyses = 0
        
        # Collect per-model comprehensive metrics
        per_model_metrics = {}
        
        for app in apps:
            # Get best completed main task for this app (prefer most complete results)
            candidate_tasks = AnalysisTask.query.filter(
                AnalysisTask.target_model == app.model_slug,
                AnalysisTask.target_app_number == app.app_number,
                AnalysisTask.status.in_([  # type: ignore[union-attr]
                    AnalysisStatus.COMPLETED,
                    AnalysisStatus.PARTIAL_SUCCESS,
                    AnalysisStatus.FAILED
                ]),
                db.or_(
                    AnalysisTask.is_main_task.is_(True),
                    AnalysisTask.parent_task_id.is_(None)
                )
            ).all()
            
            # Pick task with most issues_found (indicates complete analysis)
            task = max(candidate_tasks, key=lambda t: (t.issues_found or 0, t.completed_at or t.created_at)) if candidate_tasks else None
            
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
        # Use per-model severity_counts (correct), NOT truncated all_findings
        aggregated_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for model_entry in models_data:
            model_sev = model_entry.get('severity_counts', {})
            for sev_key in aggregated_severity:
                aggregated_severity[sev_key] += model_sev.get(sev_key, 0)
        severity_counts = aggregated_severity
        correct_total_findings = sum(m.get('findings_count', 0) for m in models_data)

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

        # NEW: Per-model finding analytics for cross-model CWE comparison
        cross_model_analytics = {}
        for m in models_data:
            m_slug = m.get('model_slug')
            m_task_id = m.get('task_id')
            if m_slug and m_task_id:
                cross_model_analytics[m_slug] = collect_finding_analytics([m_task_id])

        # NEW: Radar chart data - normalize 5 axes to 0-100 scale
        radar_chart_data = self._build_radar_chart_data(models_data, apps)

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
            'apps_found': apps_total,
            'replications_excluded': replications_excluded,
            
            # Summary statistics
            'summary': {
                'template_slug': template_slug,
                'template_name': template_metadata.get('name', template_slug),
                'template_category': template_metadata.get('category', 'Unknown'),
                'template_complexity': template_metadata.get('complexity_tier', 'unknown'),
                'template_complexity_score': template_metadata.get('complexity_score', 0),
                'models_compared': len(models_data),
                'total_analyses': total_analyses,
                'total_findings': correct_total_findings,
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

            # NEW: Per-model finding analytics for cross-model CWE comparison
            'cross_model_analytics': cross_model_analytics,

            # NEW: Radar chart data (5 quality axes, 0-100 scale per model)
            'radar_chart_data': radar_chart_data,

            # Sample findings
            'findings': all_findings[:500]
        }

    @staticmethod
    def _extract_score(source: Any, key: str) -> float:
        """Extract a numeric score from either flat value or {'mean': x} dict."""
        val = source.get(key) if isinstance(source, dict) else None
        if val is None:
            return 0.0
        if isinstance(val, dict):
            return float(val.get('mean', 0) or 0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    def _build_radar_chart_data(
        self,
        models_data: List[Dict[str, Any]],
        apps: List[GeneratedApplication],
    ) -> Dict[str, Any]:
        """Build radar chart data normalizing 5 axes to 0-100 per model.

        Handles both flat scores (from _get_per_model_metrics) and nested
        dicts like ``{'mean': x}`` (from collect_quantitative_metrics).
        """
        axes = ['Security Score', 'Code Quality', 'Performance', 'Maintainability', 'Issue Density']
        datasets = []

        for m in models_data:
            slug = m.get('model_slug', '')
            qm = m.get('quantitative_metrics', {})
            ai = qm.get('ai_analysis', {})
            has_ai = ai.get('available', False) if isinstance(ai, dict) else False

            # Security score (from AI analysis, 0-10 → 0-100)
            security = min(100, self._extract_score(ai, 'security_score') * 10) if has_ai else 0

            # Code quality score (from AI analysis, 0-10 → 0-100)
            quality = min(100, self._extract_score(ai, 'code_quality_score') * 10) if has_ai else 0

            # Performance (invert error rate: lower error = better, cap at 100)
            perf = qm.get('performance', {})
            has_perf = perf.get('available', False) if isinstance(perf, dict) else False
            if has_perf:
                error_rate = self._extract_score(perf, 'error_rate') if isinstance(perf, dict) else 0
                # error_rate may be 0-1 (fraction) or 0-100 (percent) depending on source
                if isinstance(error_rate, (int, float)) and error_rate > 1:
                    error_rate = error_rate / 100  # normalize to fraction
                performance = max(0, 100 - error_rate * 100)
            else:
                performance = 0  # no data → 0, not 100

            # Maintainability (from AI analysis, 0-10 → 0-100)
            maintainability = min(100, self._extract_score(ai, 'maintainability_score') * 10) if has_ai else 0

            # Issue density (invert: fewer issues per LOC = better)
            loc_info = qm.get('loc', {})
            total_loc = loc_info.get('total_loc', 0) if isinstance(loc_info, dict) and loc_info.get('available') else 0
            findings_count = m.get('findings_count', 0) or m.get('total_findings', 0)
            if total_loc > 0:
                density = findings_count / total_loc * 100  # issues per 100 LOC
                issue_density_score = max(0, 100 - density * 10)  # 10 issues/100LOC = 0 score
            else:
                issue_density_score = 50  # neutral when no LOC data

            datasets.append({
                'model_slug': slug,
                'model_name': m.get('model_name', slug),
                'values': [
                    round(security, 1),
                    round(quality, 1),
                    round(performance, 1),
                    round(maintainability, 1),
                    round(issue_density_score, 1),
                ],
            })

        return {
            'axes': axes,
            'datasets': datasets,
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
            loc_data = count_loc_from_generated_files(app.model_slug, [app.app_number])
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
        
        # Query completed main tasks only (subtask results are included in main task's consolidated result)
        query = AnalysisTask.query.filter(
            AnalysisTask.status.in_([  # type: ignore[union-attr]
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS
            ]),
            db.or_(
                AnalysisTask.is_main_task.is_(True),
                AnalysisTask.parent_task_id.is_(None)
            )
        )
        
        if filter_model:
            query = query.filter(AnalysisTask.target_model == filter_model)
        if filter_app:
            query = query.filter(AnalysisTask.target_app_number == filter_app)
        
        max_app_number = config.get('max_app_number')
        if max_app_number:
            query = query.filter(AnalysisTask.target_app_number <= max_app_number)
        
        tasks = query.order_by(AnalysisTask.completed_at.desc()).all()  # type: ignore[union-attr]
        
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
        
        # Track deployment reachability per model
        deploy_tracking: Dict[str, Dict[str, int]] = {}  # model -> {reachable, total}
        
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
            
            # Track deployment reachability from dynamic-analyzer
            if model_slug not in deploy_tracking:
                deploy_tracking[model_slug] = {'reachable': 0, 'total': 0}
            deploy_tracking[model_slug]['total'] += 1
            dyn_svc = (result.tools or {}).get('dynamic-analyzer', {})
            if isinstance(dyn_svc, dict):
                dyn_payload = dyn_svc.get('payload', dyn_svc)
                dyn_analysis = dyn_payload.get('analysis', {}) if isinstance(dyn_payload, dict) else {}
                dyn_summary = dyn_analysis.get('summary', {}) if isinstance(dyn_analysis, dict) else {}
                if isinstance(dyn_summary, dict) and dyn_summary.get('reachable_urls', 0) > 0:
                    deploy_tracking[model_slug]['reachable'] += 1
            
            # Get LOC for this app (cached by app_key)
            app_loc = 0
            if app:
                loc_data = count_loc_from_generated_files(model_slug, [task.target_app_number])
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
                # Service entries have 'analysis', 'tool_results', or multiple result keys
                # Direct tools have 'status' and simple result data
                is_service = (
                    'analysis' in item_data or
                    'tool_results' in item_data or
                    'tools_used' in item_data or
                    ('tools' in item_data and isinstance(item_data.get('tools'), dict))
                )
                
                is_direct_tool = (
                    not is_service and
                    'status' in item_data and 
                    ('tool_name' in item_data or 'results' in item_data or 'metadata' in item_data)
                )
                
                if is_direct_tool:
                    # item_data IS the tool data itself (AI analyzer format)
                    tool_results = {item_name: self._normalize_tool_data(item_data, tool_name=item_name)}
                    service_name = 'ai-analyzer'  # Infer service from direct tool structure
                else:
                    # item_data is a service containing tools (possibly without 'analysis' wrapper)
                    # If no 'analysis' key, try treating the item_data itself as the analysis
                    if 'analysis' not in item_data and ('results' in item_data or 'tool_results' in item_data or 'tools' in item_data):
                        wrapped = {'analysis': item_data}
                        tool_results = self._extract_tools_from_service(wrapped)
                    else:
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
                    
                    # Count findings by severity - prefer severity_breakdown over iterating issues
                    sev_bd = t_data.get('severity_breakdown', {})
                    if isinstance(sev_bd, dict) and sev_bd:
                        # Use pre-computed severity breakdown (most reliable)
                        for sev_key, sev_count in sev_bd.items():
                            sev_lower = sev_key.lower()
                            if sev_lower in agg['findings_by_severity'] and isinstance(sev_count, (int, float)):
                                agg['findings_by_severity'][sev_lower] += int(sev_count)
                    else:
                        # Fallback: count from issues list
                        issues_list = t_data.get('issues', [])
                        if isinstance(issues_list, list) and isinstance(findings_count, int) and findings_count >= 0:
                            issues_list = issues_list[:findings_count]

                        for finding in issues_list if isinstance(issues_list, list) else []:
                            sev = 'info'
                            if isinstance(finding, dict):
                                sev = str(finding.get('severity', 'info')).lower()
                            if sev in agg['findings_by_severity']:
                                agg['findings_by_severity'][sev] += 1
                            all_findings.append({**finding, 'tool': t_name} if isinstance(finding, dict) else {'tool': t_name})
                    
                    # Store performance/AI metrics if present
                    if 'metrics' in t_data:
                        if 'metrics' not in agg:
                            agg['metrics'] = []
                        agg['metrics'].append(t_data['metrics'])
                    if 'tool_type' in t_data:
                        agg['tool_type'] = t_data['tool_type']
                    
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
                    
                    # Enrich per-model data with tool-specific metrics
                    metrics = t_data.get('metrics', {})
                    if metrics and isinstance(metrics, dict):
                        if 'metrics_list' not in tbm:
                            tbm['metrics_list'] = []
                        tbm['metrics_list'].append(metrics)
                    
                    # Capture endpoint test data for curl-endpoint-tester
                    ep_metrics = t_data.get('endpoint_metrics', {})
                    if ep_metrics and isinstance(ep_metrics, dict):
                        if 'endpoint_data' not in tbm:
                            tbm['endpoint_data'] = {'total': 0, 'passed': 0, 'failed': 0}
                        tbm['endpoint_data']['total'] += ep_metrics.get('endpoints_total', 0)
                        tbm['endpoint_data']['passed'] += ep_metrics.get('endpoints_passed', 0)
                        tbm['endpoint_data']['failed'] += ep_metrics.get('endpoints_failed', 0)
                    
                    # Capture per-app severity breakdown (for ZAP per-model)
                    sev_bd_data = t_data.get('severity_breakdown', {})
                    if sev_bd_data and isinstance(sev_bd_data, dict):
                        if 'severity' not in tbm:
                            tbm['severity'] = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
                        for sk, sv in sev_bd_data.items():
                            sk_lower = sk.lower()
                            if sk_lower in tbm['severity'] and isinstance(sv, (int, float)):
                                tbm['severity'][sk_lower] += int(sv)
                    
                    # Store tool_type
                    if 'tool_type' in t_data:
                        tbm['tool_type'] = t_data['tool_type']
                    
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
        
        # Aggregate per-model rich metrics from collected lists
        for model_slug, model_tools in tools_by_model.items():
            for t_name, tbm in model_tools.items():
                ml = tbm.pop('metrics_list', [])
                if not ml:
                    continue
                tool_type = tbm.get('tool_type', '')
                if tool_type == 'performance':
                    rps = [m.get('requests_per_second') for m in ml if m.get('requests_per_second') is not None]
                    rt = [m.get('avg_response_time') for m in ml if m.get('avg_response_time') is not None]
                    errs = [m.get('failed_requests', 0) or 0 for m in ml]
                    p95 = [m.get('p95_response_time') for m in ml if m.get('p95_response_time') is not None]
                    tbm['perf'] = {
                        'avg_rps': round(sum(rps) / len(rps), 2) if rps else 0,
                        'avg_rt': round(sum(rt) / len(rt), 2) if rt else 0,
                        'total_errors': sum(int(e) for e in errs if e),
                        'p95_rt': round(sum(p95) / len(p95), 2) if p95 else 0,
                        'samples': len(ml),
                    }
                elif tool_type == 'ai':
                    compliance = [m.get('compliance_percentage') for m in ml if m.get('compliance_percentage') is not None]
                    scores = [m.get('aggregate_score') for m in ml if m.get('aggregate_score') is not None]
                    grades = [m.get('quality_grade') for m in ml if m.get('quality_grade')]
                    reqs_met = [m.get('requirements_met', 0) or 0 for m in ml]
                    reqs_total = [m.get('total_requirements', 0) or 0 for m in ml]
                    metrics_passed = [m.get('metrics_passed', 0) or 0 for m in ml]
                    metrics_total = [m.get('total_metrics', 0) or 0 for m in ml]
                    grade_dist: Dict[str, int] = {}
                    for g in grades:
                        grade_dist[g] = grade_dist.get(g, 0) + 1
                    tbm['ai'] = {
                        'avg_compliance': round(sum(compliance) / len(compliance), 1) if compliance else 0,
                        'avg_score': round(sum(scores) / len(scores), 1) if scores else 0,
                        'grade_dist': grade_dist,
                        'avg_reqs_met': round(sum(reqs_met) / len(reqs_met), 1) if reqs_met else 0,
                        'avg_reqs_total': round(sum(reqs_total) / len(reqs_total), 1) if reqs_total else 0,
                        'avg_metrics_passed': round(sum(metrics_passed) / len(metrics_passed), 1) if metrics_passed else 0,
                        'avg_metrics_total': round(sum(metrics_total) / len(metrics_total), 1) if metrics_total else 0,
                        'samples': len(ml),
                    }
                # Compute endpoint pass rate
                ep = tbm.get('endpoint_data')
                if ep and ep.get('total', 0) > 0:
                    ep['pass_rate'] = round(ep['passed'] / ep['total'] * 100, 1)
        
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
            
            # Aggregate performance/AI metrics if present
            tool_type = agg.get('tool_type', 'static')
            metrics_list = agg.get('metrics', [])
            if tool_type == 'performance' and metrics_list:
                rps_vals = [m.get('requests_per_second') for m in metrics_list
                            if m.get('requests_per_second') is not None]
                rt_vals = [m.get('avg_response_time') for m in metrics_list
                           if m.get('avg_response_time') is not None]
                err_vals = [m.get('failed_requests', 0) for m in metrics_list
                            if m.get('failed_requests') is not None]
                agg['performance_metrics'] = {
                    'avg_rps': round(sum(rps_vals) / len(rps_vals), 2) if rps_vals else 0,
                    'avg_response_time': round(sum(rt_vals) / len(rt_vals), 2) if rt_vals else 0,
                    'total_errors': sum(e for e in err_vals if e),
                    'samples': len(metrics_list),
                }
            elif tool_type == 'ai' and metrics_list:
                scores = [m.get('aggregate_score') or m.get('compliance_percentage')
                          for m in metrics_list
                          if m.get('aggregate_score') is not None or m.get('compliance_percentage') is not None]
                grades = [m.get('quality_grade') for m in metrics_list
                          if m.get('quality_grade')]
                agg['ai_metrics'] = {
                    'avg_score': round(sum(s for s in scores if s) / len(scores), 2) if scores else 0,
                    'grades': grades,
                    'samples': len(metrics_list),
                }
            
            # Remove raw metrics list from output
            agg.pop('metrics', None)
            
            # Add display-friendly fields
            agg['display_name'] = t_name.replace('_', ' ').title()
            agg['name'] = t_name
            agg['total_runs'] = agg['executions']
            agg['avg_findings'] = agg['findings_per_run']
            agg['container'] = agg['service']
            
            # Template-compatible aliases
            agg['average_duration'] = agg['avg_duration']
            agg['average_findings_per_execution'] = agg['findings_per_run']
            agg['total_executions'] = agg['executions']
            
            # Build per-model breakdown from tools_by_model
            exec_by_model: Dict[str, int] = {}
            findings_by_model: Dict[str, int] = {}
            success_by_model: Dict[str, int] = {}
            for m_slug in sorted(models_seen):
                tbm_data = tools_by_model.get(m_slug, {}).get(t_name)
                if tbm_data:
                    exec_by_model[m_slug] = tbm_data.get('executions', 0)
                    findings_by_model[m_slug] = tbm_data.get('findings', 0)
                    success_by_model[m_slug] = tbm_data.get('successful', 0)
            agg['executions_by_model'] = exec_by_model
            agg['findings_by_model'] = findings_by_model
            agg['success_by_model'] = success_by_model
            
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
            
            # NEW: Severity heatmap data — tools (rows) × severities (cols) → count
            'severity_heatmap_data': {
                'tools': [t['tool_name'] for t in tools_list],
                'severities': ['critical', 'high', 'medium', 'low', 'info'],
                'matrix': [
                    [t['findings_by_severity'].get(s, 0) for s in ['critical', 'high', 'medium', 'low', 'info']]
                    for t in tools_list
                ],
            },

            # NEW: Per-tool category/confidence breakdown from DB
            'tool_finding_analytics': self._build_tool_finding_analytics(tools_list, tasks),

            # Sample findings
            'findings': all_findings[:500],

            # Deployment reachability per model
            'deploy_tracking': deploy_tracking,
        }

    def _build_tool_finding_analytics(
        self,
        tools_list: List[Dict[str, Any]],
        tasks: List[AnalysisTask],
    ) -> Dict[str, Any]:
        """Query AnalysisResult grouped by tool_name for category/confidence breakdown."""
        task_ids = [t.task_id for t in tasks]
        if not task_ids:
            return {}

        try:
            rows = (
                db.session.query(
                    AnalysisResult.tool_name,
                    AnalysisResult.category,
                    AnalysisResult.confidence,
                    db.func.count(AnalysisResult.id),
                )
                .filter(AnalysisResult.task_id.in_(task_ids))
                .group_by(AnalysisResult.tool_name, AnalysisResult.category, AnalysisResult.confidence)
                .all()
            )
        except Exception as e:
            logger.warning(f"Failed to build tool finding analytics: {e}")
            return {}

        per_tool: Dict[str, Dict[str, Any]] = {}
        for tool_name, category, confidence, count in rows:
            if tool_name not in per_tool:
                per_tool[tool_name] = {'categories': {}, 'confidence': {}}
            cat = category or 'uncategorized'
            per_tool[tool_name]['categories'][cat] = per_tool[tool_name]['categories'].get(cat, 0) + count
            conf = (confidence or 'unknown').lower()
            per_tool[tool_name]['confidence'][conf] = per_tool[tool_name]['confidence'].get(conf, 0) + count

        return per_tool

    # ==========================================================================
    # GENERATION ANALYTICS
    # ==========================================================================

    def _generate_generation_analytics(self, config: Dict[str, Any], report: 'Report') -> Dict[str, Any]:
        """Generate analytics about app generation success/failure patterns.

        Provides insights into:
        - Success rates by model and template
        - Common failure stages and error patterns
        - Fix effectiveness (automatic, LLM, manual)
        - Generation attempt statistics
        """
        from datetime import timedelta

        report.update_progress(10)
        db.session.commit()

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
            query = query.filter(GeneratedApplication.template_slug == template_filter)
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
        
        report.update_progress(30)
        db.session.commit()

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
            tmpl = app.template_slug or 'unknown'
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
                'template': app.template_slug,
                'failure_stage': app.failure_stage,
                'error_message': (app.error_message[:200] + '...') if app.error_message and len(app.error_message) > 200 else app.error_message,
                'attempts': app.generation_attempts,
                'timestamp': app.last_error_at.isoformat() if app.last_error_at else None
            })
        
        report.update_progress(70)
        db.session.commit()

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

        # NEW: Model × Template success matrix (for heatmap)
        model_template_matrix = self._build_model_template_matrix(apps)

        # NEW: Timing distribution per model
        timing_distribution = {}
        for app in apps:
            slug = app.model_slug or 'unknown'
            if slug not in timing_distribution:
                timing_distribution[slug] = []
            # Use generation duration if available
            duration = getattr(app, 'generation_duration', None)
            if duration is not None:
                timing_distribution[slug].append(round(duration, 2))

        return {
            'report_type': 'generation_analytics',
            'generated_at': utc_now().isoformat(),
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
            ],
            # NEW: Model × Template success heatmap
            'model_template_matrix': model_template_matrix,
            # NEW: Timing distribution per model
            'timing_distribution': timing_distribution,
        }

    def _build_model_template_matrix(
        self, apps: List[GeneratedApplication]
    ) -> Dict[str, Any]:
        """Build model × template → success/failed/total matrix."""
        models_set: set = set()
        templates_set: set = set()
        cells: Dict[str, Dict[str, Dict[str, int]]] = {}

        for app in apps:
            m = app.model_slug or 'unknown'
            t = app.template_slug or 'unknown'
            models_set.add(m)
            templates_set.add(t)
            key = f"{m}|{t}"
            if key not in cells:
                cells[key] = {'success': 0, 'failed': 0, 'total': 0}
            cells[key]['total'] += 1
            if app.is_generation_failed:
                cells[key]['failed'] += 1
            else:
                cells[key]['success'] += 1

        models = sorted(models_set)
        templates = sorted(templates_set)

        # Build matrix: list of lists  [model_idx][template_idx] = {success, failed, total}
        matrix = []
        for m in models:
            row = []
            for t in templates:
                row.append(cells.get(f"{m}|{t}", {'success': 0, 'failed': 0, 'total': 0}))
            matrix.append(row)

        return {
            'models': models,
            'templates': templates,
            'matrix': matrix,
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

    def _generate_comprehensive_report(self, config: Dict[str, Any], report: Report) -> Dict[str, Any]:
        """Generate a platform-wide report by composing all existing report generators."""
        report.update_progress(10)
        db.session.commit()

        filter_mode = config.get('filter_mode', 'all')
        max_app_number = config.get('max_app_number', 20)

        app_query = db.session.query(
            GeneratedApplication.model_slug,
            GeneratedApplication.template_slug
        )
        if max_app_number:
            app_query = app_query.filter(
                GeneratedApplication.app_number <= max_app_number
            )
        app_pairs = app_query.all()
        total_apps = len(app_pairs)

        models_set: set[str] = set()
        templates_set: set[str] = set()
        template_models: Dict[str, set[str]] = {}
        for model_slug, template_slug in app_pairs:
            if model_slug:
                models_set.add(model_slug)
            if template_slug:
                templates_set.add(template_slug)
                if template_slug not in template_models:
                    template_models[template_slug] = set()
                if model_slug:
                    template_models[template_slug].add(model_slug)

        model_slugs = sorted(models_set)
        template_slugs = sorted(templates_set)
        comparable_templates = [
            template_slug
            for template_slug in template_slugs
            if len(template_models.get(template_slug, set())) >= 2
        ]

        class _NoOpReport:
            def update_progress(self, _percent: int) -> None:
                return None

        sub_report = _NoOpReport()

        model_reports: Dict[str, Dict[str, Any]] = {}
        template_reports: Dict[str, Dict[str, Any]] = {}
        tool_report: Dict[str, Any] = {}
        generation_report: Dict[str, Any] = {}
        subreport_errors: Dict[str, Dict[str, str]] = {
            'model_reports': {},
            'template_reports': {},
            'tool_report': {},
            'generation_report': {},
        }

        for model_slug in model_slugs:
            try:
                model_reports[model_slug] = self._generate_model_report(
                    {'model_slug': model_slug, 'filter_mode': filter_mode,
                     'max_app_number': max_app_number},
                    sub_report,  # type: ignore[arg-type]
                )
            except Exception as exc:
                logger.warning("Comprehensive model report failed for %s: %s", model_slug, exc, exc_info=True)
                subreport_errors['model_reports'][model_slug] = str(exc)

        report.update_progress(40)
        db.session.commit()

        for template_slug in comparable_templates:
            try:
                template_reports[template_slug] = self._generate_template_comparison(
                    {'template_slug': template_slug, 'filter_mode': filter_mode},
                    sub_report,  # type: ignore[arg-type]
                )
            except Exception as exc:
                logger.warning(
                    "Comprehensive template comparison failed for %s: %s",
                    template_slug,
                    exc,
                    exc_info=True
                )
                subreport_errors['template_reports'][template_slug] = str(exc)

        report.update_progress(60)
        db.session.commit()

        try:
            tool_report = self._generate_tool_report(
                {'filter_mode': filter_mode, 'max_app_number': max_app_number},
                sub_report,  # type: ignore[arg-type]
            )
        except Exception as exc:
            logger.warning("Comprehensive tool report failed: %s", exc, exc_info=True)
            subreport_errors['tool_report']['error'] = str(exc)

        report.update_progress(75)
        db.session.commit()

        try:
            generation_report = self._generate_generation_analytics(
                {'days_back': None, 'filter_mode': filter_mode,
                 'max_app_number': max_app_number},
                sub_report,  # type: ignore[arg-type]
            )
        except Exception as exc:
            logger.warning("Comprehensive generation report failed: %s", exc, exc_info=True)
            subreport_errors['generation_report']['error'] = str(exc)

        report.update_progress(85)
        db.session.commit()

        findings_breakdown = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        total_findings = 0
        for model_data in model_reports.values():
            model_summary = model_data.get('summary', {})
            total_findings += model_summary.get('total_findings', 0) or 0
            sev = model_data.get('findings_breakdown') or model_summary.get('severity_breakdown', {})
            for key in findings_breakdown:
                findings_breakdown[key] += sev.get(key, 0) or 0

        model_rankings = self._build_comprehensive_rankings(model_reports, tool_report)

        # Compute thesis-level analytics (per-tool per-model, heatmap, TOPSIS, etc.)
        thesis_analytics = self._compute_thesis_analytics(model_reports, tool_report)

        report.update_progress(95)
        db.session.commit()

        models_with_findings = len(model_reports)
        return {
            'report_type': 'comprehensive',
            'generated_at': utc_now().isoformat(),
            'summary': {
                'total_models': len(model_slugs),
                'total_templates': len(template_slugs),
                'total_apps': total_apps,
                'total_findings': total_findings,
                'templates_compared': len(template_reports),
            },
            'findings_breakdown': findings_breakdown,
            'model_reports': model_reports,
            'template_reports': template_reports,
            'tool_report': tool_report,
            'generation_report': generation_report,
            'model_rankings': model_rankings,
            'thesis_analytics': thesis_analytics,
            'platform_metrics': {
                'avg_findings_per_model': (
                    total_findings / models_with_findings if models_with_findings else 0
                ),
                'avg_findings_per_app': (total_findings / total_apps if total_apps else 0),
            },
            'subreport_errors': subreport_errors,
        }

    def _build_comprehensive_rankings(
        self,
        model_reports: Dict[str, Dict[str, Any]],
        tool_report: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Build model leaderboard for comprehensive reports."""
        deploy_tracking = (tool_report or {}).get('deploy_tracking', {})
        rankings: List[Dict[str, Any]] = []

        for model_slug, model_data in model_reports.items():
            summary = model_data.get('summary', {})
            severity = model_data.get('findings_breakdown') or summary.get('severity_breakdown', {})
            critical = severity.get('critical', 0) or 0
            high = severity.get('high', 0) or 0
            medium = severity.get('medium', 0) or 0
            low = severity.get('low', 0) or 0
            info = severity.get('info', 0) or 0
            total_findings = summary.get('total_findings', 0) or 0
            apps_count = model_data.get('apps_count', summary.get('total_apps', 0))
            dt = deploy_tracking.get(model_slug, {})
            deploy_rate = (dt.get('reachable', 0) / dt['total'] * 100) if dt.get('total', 0) > 0 else 0

            severity_score = (critical * 100) + (high * 10) + (medium * 3) + low
            rankings.append({
                'model_slug': model_slug,
                'apps_count': apps_count,
                'total_findings': total_findings,
                'critical': critical,
                'high': high,
                'medium': medium,
                'low': low,
                'info': info,
                'severity_score': severity_score,
                'deploy_rate': round(deploy_rate, 1),
            })

        rankings.sort(key=lambda row: (row['severity_score'], row['total_findings'], row['model_slug']))
        for idx, row in enumerate(rankings, start=1):
            row['rank'] = idx

        return rankings
    
    # ==========================================================================
    # THESIS ANALYTICS — Per-tool per-model data for comprehensive report tables
    # ==========================================================================

    # Model pricing data for TOPSIS/WSM computations
    _MODEL_PARAMS: Dict[str, Dict[str, float]] = {
        'openai_gpt-4o-mini': {'ctx_k': 128, 'max_out_k': 16, 'in_price': 0.15, 'out_price': 0.60},
        'openai_gpt-5.2-codex-20260114': {'ctx_k': 400, 'max_out_k': 128, 'in_price': 1.75, 'out_price': 14.00},
        'google_gemini-3-pro-preview-20251117': {'ctx_k': 1048, 'max_out_k': 65, 'in_price': 2.00, 'out_price': 12.00},
        'deepseek_deepseek-r1-0528': {'ctx_k': 163, 'max_out_k': 65, 'in_price': 0.40, 'out_price': 1.75},
        'qwen_qwen3-coder-plus': {'ctx_k': 128, 'max_out_k': 65, 'in_price': 1.00, 'out_price': 5.00},
        'z-ai_glm-4.7-20251222': {'ctx_k': 202, 'max_out_k': 65, 'in_price': 0.40, 'out_price': 1.50},
        'mistralai_mistral-small-3.1-24b-instruct-2503': {'ctx_k': 131, 'max_out_k': 131, 'in_price': 0.03, 'out_price': 0.11},
        'google_gemini-3-flash-preview-20251217': {'ctx_k': 1048, 'max_out_k': 65, 'in_price': 0.50, 'out_price': 3.00},
        'meta-llama_llama-3.1-405b-instruct': {'ctx_k': 10, 'max_out_k': 0, 'in_price': 4.00, 'out_price': 4.00},
        'anthropic_claude-4.5-sonnet-20250929': {'ctx_k': 1000, 'max_out_k': 64, 'in_price': 3.00, 'out_price': 15.00},
    }

    _SHORT_NAMES: Dict[str, str] = {
        'openai_gpt-4o-mini': 'GPT-4o Mini',
        'openai_gpt-5.2-codex-20260114': 'GPT-5.2 Codex',
        'google_gemini-3-pro-preview-20251117': 'Gemini 3 Pro',
        'deepseek_deepseek-r1-0528': 'DeepSeek R1',
        'qwen_qwen3-coder-plus': 'Qwen3 Coder+',
        'z-ai_glm-4.7-20251222': 'GLM-4.7',
        'mistralai_mistral-small-3.1-24b-instruct-2503': 'Mistral Small 3.1',
        'google_gemini-3-flash-preview-20251217': 'Gemini 3 Flash',
        'meta-llama_llama-3.1-405b-instruct': 'Llama 3.1 405B',
        'anthropic_claude-4.5-sonnet-20250929': 'Claude 4.5 Sonnet',
    }

    def _compute_thesis_analytics(
        self,
        model_reports: Dict[str, Dict[str, Any]],
        tool_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute thesis-level analytics for the comprehensive report.

        Produces per-tool per-model breakdowns, code composition, severity tables,
        heatmap matrix, TOPSIS/WSM rankings, and Spearman correlations — all from
        the already-generated model_reports and tool_report data.

        Returns:
            Dict with keys: code_composition, severity_by_model, service_completion,
            static_tools, dynamic_tools, performance_tools, ai_tools,
            heatmap, topsis, wsm, correlations
        """
        import math

        model_slugs = sorted(model_reports.keys())
        tools_by_model = tool_report.get('by_model', {})
        tools_list = tool_report.get('tools', [])
        deploy_tracking = tool_report.get('deploy_tracking', {})
        tools_by_name: Dict[str, Dict[str, Any]] = {
            t['tool_name']: t for t in tools_list
        }

        # ── Code Composition per model ───────────────────────────────────────
        code_composition: List[Dict[str, Any]] = []
        for slug in model_slugs:
            mr = model_reports[slug]
            loc = mr.get('loc_metrics', {})
            apps_count = mr.get('apps_count', 0)
            total_loc = loc.get('total_loc', 0)
            python_loc = loc.get('backend_loc', 0)
            js_loc = loc.get('frontend_loc', 0)
            total_findings = mr.get('summary', {}).get('total_findings', 0) or 0
            loc_per_app = total_loc / apps_count if apps_count else 0
            i_100_loc = (total_findings / total_loc * 100) if total_loc > 0 else 0
            dt = deploy_tracking.get(slug, {})
            deploy_rate = (dt.get('reachable', 0) / dt['total'] * 100) if dt.get('total', 0) > 0 else 0

            code_composition.append({
                'model_slug': slug,
                'short_name': self._SHORT_NAMES.get(slug, slug),
                'apps': apps_count,
                'total_loc': total_loc,
                'python_loc': python_loc,
                'js_loc': js_loc,
                'loc_per_app': round(loc_per_app),
                'i_100_loc': round(i_100_loc, 2),
                'deploy_rate': round(deploy_rate, 1),
                'deploy_reachable': dt.get('reachable', 0),
                'deploy_total': dt.get('total', 0),
            })
        code_composition.sort(key=lambda r: r['loc_per_app'], reverse=True)

        # ── Severity by Model ────────────────────────────────────────────────
        severity_by_model: List[Dict[str, Any]] = []
        for slug in model_slugs:
            mr = model_reports[slug]
            sev = mr.get('findings_breakdown', {})
            total_f = mr.get('summary', {}).get('total_findings', 0) or 0
            loc = mr.get('loc_metrics', {})
            total_loc = loc.get('total_loc', 0)
            apps_count = mr.get('apps_count', 0)
            d_kloc = (total_f / total_loc * 1000) if total_loc > 0 else 0
            avg_per_app = total_f / apps_count if apps_count > 0 else 0

            severity_by_model.append({
                'model_slug': slug,
                'short_name': self._SHORT_NAMES.get(slug, slug),
                'apps': apps_count,
                'total': total_f,
                'critical': sev.get('critical', 0),
                'high': sev.get('high', 0),
                'medium': sev.get('medium', 0),
                'low': sev.get('low', 0),
                'info': sev.get('info', 0),
                'd_kloc': round(d_kloc, 2),
                'avg_per_app': round(avg_per_app, 1),
            })
        severity_by_model.sort(key=lambda r: r['d_kloc'], reverse=True)

        # ── Service Completion per model ─────────────────────────────────────
        service_completion: List[Dict[str, Any]] = []
        # Derive from tool_report by_model: count tools from each service
        _svc_tools: Dict[str, set] = {}
        for t in tools_list:
            svc = t.get('service', '')
            if svc not in _svc_tools:
                _svc_tools[svc] = set()
            _svc_tools[svc].add(t['tool_name'])

        for slug in model_slugs:
            mr = model_reports[slug]
            apps_count = mr.get('apps_count', 0)
            model_tools = tools_by_model.get(slug, {})

            # Count apps that had at least one tool from each service type
            svc_counts: Dict[str, int] = {}
            for svc_type in ['static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer']:
                svc_tool_set = _svc_tools.get(svc_type, set())
                if svc_tool_set:
                    count = max(
                        (model_tools.get(tn, {}).get('executions', 0) for tn in svc_tool_set),
                        default=0
                    )
                    svc_counts[svc_type] = count
                else:
                    svc_counts[svc_type] = 0

            service_completion.append({
                'model_slug': slug,
                'short_name': self._SHORT_NAMES.get(slug, slug),
                'apps': apps_count,
                'static': svc_counts.get('static-analyzer', 0),
                'dynamic': svc_counts.get('dynamic-analyzer', 0),
                'performance': svc_counts.get('performance-tester', 0),
                'ai': svc_counts.get('ai-analyzer', 0),
            })

        # ── Per-tool per-model data grouped by tool type ─────────────────────
        _STATIC_TOOLS = [
            'bandit', 'semgrep', 'pylint', 'ruff', 'mypy', 'vulture', 'radon',
            'safety', 'pip-audit', 'detect-secrets', 'eslint', 'npm-audit',
            'stylelint',
        ]
        _DYNAMIC_TOOLS = ['zap', 'owasp-zap', 'nmap', 'curl', 'curl-endpoint-tester',
                          'connectivity', 'port-scan']
        _PERF_TOOLS = ['ab', 'locust', 'artillery', 'aiohttp']
        _AI_TOOLS = ['requirements-scanner', 'code-quality-analyzer']

        # Tool category mapping for customised table rendering
        _TOOL_CATEGORIES: Dict[str, str] = {
            'bandit': 'security', 'semgrep': 'security', 'detect-secrets': 'security',
            'safety': 'dependency', 'pip-audit': 'dependency', 'npm-audit': 'dependency',
            'pylint': 'quality', 'ruff': 'quality', 'eslint': 'quality',
            'mypy': 'quality', 'stylelint': 'quality', 'html-validator': 'quality',
            'vulture': 'quality',
            'radon': 'complexity',
        }

        def _per_model_findings(tool_name: str) -> List[Dict[str, Any]]:
            """Build per-model breakdown for a findings-based tool."""
            rows = []
            tool_agg = tools_by_name.get(tool_name, {})
            total_loc_tracked = tool_agg.get('total_loc_analyzed', 0)
            for slug in model_slugs:
                mt = tools_by_model.get(slug, {}).get(tool_name, {})
                runs = mt.get('executions', 0)
                ok = mt.get('successful', 0)
                findings = mt.get('findings', 0)
                loc = model_reports[slug].get('loc_metrics', {}).get('total_loc', 0)
                avg_run = findings / ok if ok > 0 else 0
                f_kloc = (findings / loc * 1000) if loc > 0 else 0
                sev = mt.get('severity', {})
                rows.append({
                    'model_slug': slug,
                    'short_name': self._SHORT_NAMES.get(slug, slug),
                    'runs': runs, 'ok': ok, 'findings': findings,
                    'avg_per_run': round(avg_run, 2),
                    'f_kloc': round(f_kloc, 2),
                    'high': sev.get('high', 0),
                    'medium': sev.get('medium', 0),
                    'low': sev.get('low', 0),
                    'info': sev.get('info', 0),
                })
            return rows

        # Static tools
        static_tools_data: Dict[str, Dict[str, Any]] = {}
        for tn in _STATIC_TOOLS:
            if tn not in tools_by_name:
                continue
            agg = tools_by_name[tn]
            static_tools_data[tn] = {
                'tool_name': tn,
                'display_name': agg.get('display_name', tn),
                'total_findings': agg.get('total_findings', 0),
                'total_runs': agg.get('executions', 0),
                'severity': agg.get('findings_by_severity', {}),
                'category': _TOOL_CATEGORIES.get(tn, 'quality'),
                'per_model': _per_model_findings(tn),
            }

        # Dynamic tools — each gets custom per-model data
        # Dynamic tools — per-model findings + endpoint/severity detail
        dynamic_tools_data: Dict[str, Dict[str, Any]] = {}
        for tn in _DYNAMIC_TOOLS:
            if tn not in tools_by_name:
                continue
            agg = tools_by_name[tn]
            if not agg.get('total_findings', 0):
                continue
            per_model = _per_model_findings(tn)
            # Enrich curl-endpoint-tester and zap with per-model detail
            for row in per_model:
                slug = row['model_slug']
                mt = tools_by_model.get(slug, {}).get(tn, {})
                if tn == 'curl-endpoint-tester':
                    ep = mt.get('endpoint_data', {})
                    ep_total = ep.get('total', 0)
                    ep_passed = ep.get('passed', 0)
                    ep_failed = ep.get('failed', 0)
                    row['endpoints'] = ep_total
                    row['ep_passed'] = ep_passed
                    row['ep_failed'] = ep_failed
                    row['ep_pass_rate'] = round(ep_passed / ep_total * 100, 1) if ep_total > 0 else 0
                if tn == 'zap':
                    sev = mt.get('severity', {})
                    row['high'] = sev.get('high', 0)
                    row['medium'] = sev.get('medium', 0)
                    row['low'] = sev.get('low', 0)
                    row['info'] = sev.get('info', 0)
            dynamic_tools_data[tn] = {
                'tool_name': tn,
                'display_name': agg.get('display_name', tn),
                'total_findings': agg.get('total_findings', 0),
                'total_runs': agg.get('executions', 0),
                'severity': agg.get('findings_by_severity', {}),
                'per_model': per_model,
            }

        # Performance tools — per-model RPS/RT metrics
        perf_tools_data: Dict[str, Dict[str, Any]] = {}
        for tn in _PERF_TOOLS:
            if tn not in tools_by_name:
                continue
            agg = tools_by_name[tn]
            pm = agg.get('performance_metrics', {})
            per_model_rows: List[Dict[str, Any]] = []
            for slug in model_slugs:
                mt = tools_by_model.get(slug, {}).get(tn, {})
                runs = mt.get('executions', 0)
                perf = mt.get('perf', {})
                per_model_rows.append({
                    'model_slug': slug,
                    'short_name': self._SHORT_NAMES.get(slug, slug),
                    'runs': runs,
                    'ok': mt.get('successful', 0),
                    'avg_rps': perf.get('avg_rps', 0),
                    'avg_rt': perf.get('avg_rt', 0),
                    'errors': perf.get('total_errors', 0),
                    'p95_rt': perf.get('p95_rt', 0),
                })
            perf_tools_data[tn] = {
                'tool_name': tn,
                'display_name': agg.get('display_name', tn),
                'total_runs': agg.get('executions', 0),
                'performance_metrics': pm,
                'per_model': per_model_rows,
            }

        # AI tools — per-model scores/compliance/grades
        ai_tools_data: Dict[str, Dict[str, Any]] = {}
        for tn in _AI_TOOLS:
            if tn not in tools_by_name:
                continue
            agg = tools_by_name[tn]
            am = agg.get('ai_metrics', {})
            per_model_rows = []
            for slug in model_slugs:
                mt = tools_by_model.get(slug, {}).get(tn, {})
                ai = mt.get('ai', {})
                row: Dict[str, Any] = {
                    'model_slug': slug,
                    'short_name': self._SHORT_NAMES.get(slug, slug),
                    'runs': mt.get('executions', 0),
                    'ok': mt.get('successful', 0),
                }
                if ai:
                    row['avg_compliance'] = ai.get('avg_compliance', 0)
                    row['avg_score'] = ai.get('avg_score', 0)
                    row['grade_dist'] = ai.get('grade_dist', {})
                    row['reqs_met'] = ai.get('avg_reqs_met', 0)
                    row['reqs_total'] = ai.get('avg_reqs_total', 0)
                    row['metrics_passed'] = ai.get('avg_metrics_passed', 0)
                    row['metrics_total'] = ai.get('avg_metrics_total', 0)
                per_model_rows.append(row)
            ai_tools_data[tn] = {
                'tool_name': tn,
                'display_name': agg.get('display_name', tn),
                'total_runs': agg.get('executions', 0),
                'ai_metrics': am,
                'per_model': per_model_rows,
            }

        # ── Heatmap — tool × model findings matrix ──────────────────────────
        # Only include tools with nonzero findings
        heatmap_tools = [
            tn for tn in (_STATIC_TOOLS + _DYNAMIC_TOOLS)
            if tools_by_name.get(tn, {}).get('total_findings', 0) > 0
        ]
        heatmap_models = model_slugs
        heatmap_matrix: List[Dict[str, Any]] = []
        for tn in heatmap_tools:
            row: Dict[str, Any] = {'tool': tn}
            for slug in heatmap_models:
                row[slug] = tools_by_model.get(slug, {}).get(tn, {}).get('findings', 0)
            heatmap_matrix.append(row)

        heatmap = {
            'tools': heatmap_tools,
            'models': heatmap_models,
            'model_names': {s: self._SHORT_NAMES.get(s, s) for s in heatmap_models},
            'matrix': heatmap_matrix,
        }

        # ── TOPSIS ──────────────────────────────────────────────────────────
        # Build per-model compliance & quality scores from AI tools
        model_compliance: Dict[str, float] = {}
        model_quality: Dict[str, float] = {}
        model_deploy: Dict[str, float] = {}
        for slug in model_slugs:
            rs_data = tools_by_model.get(slug, {}).get('requirements-scanner', {}).get('ai', {})
            cqa_data = tools_by_model.get(slug, {}).get('code-quality-analyzer', {}).get('ai', {})
            model_compliance[slug] = rs_data.get('avg_compliance', 0)
            model_quality[slug] = cqa_data.get('avg_score', 0)
            dt = deploy_tracking.get(slug, {})
            model_deploy[slug] = (dt.get('reachable', 0) / dt['total'] * 100) if dt.get('total', 0) > 0 else 0

        topsis_rows = []
        for slug in model_slugs:
            mr = model_reports[slug]
            loc_m = mr.get('loc_metrics', {})
            total_loc = loc_m.get('total_loc', 0)
            apps_count = mr.get('apps_count', 0)
            loc_app = total_loc / apps_count if apps_count > 0 else 0
            total_f = mr.get('summary', {}).get('total_findings', 0) or 0
            d_kloc = (total_f / total_loc * 1000) if total_loc > 0 else 0
            out_price = self._MODEL_PARAMS.get(slug, {}).get('out_price', 0)
            compliance = model_compliance.get(slug, 0)
            quality = model_quality.get(slug, 0)
            deploy_rate = model_deploy.get(slug, 0)
            topsis_rows.append({
                'model_slug': slug,
                'short_name': self._SHORT_NAMES.get(slug, slug),
                'deploy_rate': deploy_rate,
                'compliance': compliance, 'loc_app': loc_app,
                'quality': quality, 'dkloc': d_kloc, 'out_price': out_price,
            })

        criteria = ['deploy_rate', 'compliance', 'quality', 'loc_app', 'dkloc', 'out_price']
        weights = [0.25, 0.25, 0.15, 0.10, 0.15, 0.10]
        is_benefit = [True, True, True, True, False, False]

        # Vector normalization
        norms = {}
        for c in criteria:
            ss = math.sqrt(sum(r[c] ** 2 for r in topsis_rows))
            norms[c] = ss if ss > 0 else 1
        normalized = [{c: r[c] / norms[c] for c in criteria} for r in topsis_rows]
        weighted = [{c: nr[c] * weights[i] for i, c in enumerate(criteria)} for nr in normalized]

        ideal = {}
        anti_ideal = {}
        for i, c in enumerate(criteria):
            vals = [wr[c] for wr in weighted]
            if is_benefit[i]:
                ideal[c], anti_ideal[c] = max(vals), min(vals)
            else:
                ideal[c], anti_ideal[c] = min(vals), max(vals)

        topsis_scores = []
        for wr in weighted:
            d_plus = math.sqrt(sum((wr[c] - ideal[c]) ** 2 for c in criteria))
            d_minus = math.sqrt(sum((wr[c] - anti_ideal[c]) ** 2 for c in criteria))
            topsis_scores.append(d_minus / (d_plus + d_minus) if (d_plus + d_minus) > 0 else 0)

        topsis_combined = sorted(
            zip(topsis_rows, topsis_scores), key=lambda x: x[1], reverse=True
        )
        topsis = [
            {**row, 'score': round(score, 4), 'rank': rank}
            for rank, (row, score) in enumerate(topsis_combined, 1)
        ]

        # ── WSM ─────────────────────────────────────────────────────────────
        wsm_criteria = ['deploy_rate', 'compliance', 'quality', 'dkloc']
        wsm_weights = [0.30, 0.30, 0.20, 0.20]
        wsm_is_benefit = [True, True, True, False]

        mins = {c: min(r[c] for r in topsis_rows) for c in wsm_criteria}
        maxs = {c: max(r[c] for r in topsis_rows) for c in wsm_criteria}

        wsm_scored = []
        for r in topsis_rows:
            score = 0.0
            for i, c in enumerate(wsm_criteria):
                rng = maxs[c] - mins[c]
                if rng == 0:
                    norm = 1.0
                elif wsm_is_benefit[i]:
                    norm = (r[c] - mins[c]) / rng
                else:
                    norm = (maxs[c] - r[c]) / rng
                score += norm * wsm_weights[i]
            wsm_scored.append((r, score))

        wsm_combined = sorted(wsm_scored, key=lambda x: x[1], reverse=True)
        wsm = [
            {**row, 'score': round(score, 4), 'rank': rank}
            for rank, (row, score) in enumerate(wsm_combined, 1)
        ]

        # ── Spearman correlations ────────────────────────────────────────────
        def _rank(vals: List[float]) -> List[float]:
            indexed = sorted(enumerate(vals), key=lambda x: x[1])
            ranks = [0.0] * len(vals)
            i = 0
            while i < len(indexed):
                j = i
                while j < len(indexed) - 1 and indexed[j + 1][1] == indexed[j][1]:
                    j += 1
                avg_r = sum(range(i + 1, j + 2)) / (j - i + 1)
                for k in range(i, j + 1):
                    ranks[indexed[k][0]] = avg_r
                i = j + 1
            return ranks

        def _spearman(x: List[float], y: List[float]) -> float:
            n = len(x)
            if n < 3:
                return 0.0
            rx, ry = _rank(x), _rank(y)
            d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
            return 1 - (6 * d2) / (n * (n ** 2 - 1))

        total_locs = [r['loc_app'] * (model_reports[r['model_slug']].get('apps_count', 0))
                      for r in topsis_rows]
        loc_apps = [r['loc_app'] for r in topsis_rows]
        dklocs_v = [r['dkloc'] for r in topsis_rows]
        compliance_v = [r['compliance'] for r in topsis_rows]
        quality_v = [r['quality'] for r in topsis_rows]
        deploy_v = [r['deploy_rate'] for r in topsis_rows]
        ctx_ks = [self._MODEL_PARAMS.get(r['model_slug'], {}).get('ctx_k', 0) for r in topsis_rows]
        max_outs = [self._MODEL_PARAMS.get(r['model_slug'], {}).get('max_out_k', 0) for r in topsis_rows]
        out_prices_v = [r['out_price'] for r in topsis_rows]

        params_list = [
            ('Context (k)', ctx_ks),
            ('Max Out (k)', max_outs),
            ('Out $/Mtok', out_prices_v),
        ]
        outcomes_list = [
            ('Deploy%', deploy_v),
            ('Total LOC', total_locs),
            ('LOC/App', loc_apps),
            ('D/kLOC', dklocs_v),
            ('Compl.%', compliance_v),
            ('Quality', quality_v),
        ]

        correlations: List[Dict[str, Any]] = []
        for pname, pvals in params_list:
            row_data: Dict[str, Any] = {'parameter': pname}
            for oname, ovals in outcomes_list:
                row_data[oname] = round(_spearman(pvals, ovals), 2)
            correlations.append(row_data)
        correlation_outcomes = [o[0] for o in outcomes_list]

        return {
            'code_composition': code_composition,
            'severity_by_model': severity_by_model,
            'service_completion': service_completion,
            'static_tools': static_tools_data,
            'dynamic_tools': dynamic_tools_data,
            'performance_tools': perf_tools_data,
            'ai_tools': ai_tools_data,
            'heatmap': heatmap,
            'topsis': topsis,
            'wsm': wsm,
            'correlations': correlations,
            'correlation_outcomes': correlation_outcomes,
            'model_names': {s: self._SHORT_NAMES.get(s, s) for s in model_slugs},
        }

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
        elif report_type == 'comprehensive':
            pass  # All fields optional
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
        elif report_type == 'comprehensive':
            return "Comprehensive Platform Report"
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
            
            # Extract tools - merge top-level 'tools' with services tools
            tools = raw.get('tools') or results_wrapper.get('tools') or {}
            
            # Filter out metadata/config entries that aren't real tools
            _NON_TOOL_KEYS = {'_metadata', 'config_used', 'metadata'}
            tools = {k: v for k, v in tools.items() 
                     if k not in _NON_TOOL_KEYS and not k.startswith('_')}
            
            # Extract additional tools from services (e.g. ai-analyzer)
            service_tools = self._extract_tools_from_services(raw.get('services', {}))
            
            # Merge service tools into main tools dict (prefer service tools if duplicate)
            if service_tools:
                tools.update(service_tools)
            
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
        4. Resolved service file: results.analysis.results.{language}.{tool}
        """
        tools = {}
        
        analysis = service_data.get('analysis', {})
        if not isinstance(analysis, dict) or not analysis:
            # Fallback: resolved service files have results.analysis structure
            inner_results = service_data.get('results', {})
            if isinstance(inner_results, dict) and 'analysis' in inner_results:
                analysis = inner_results.get('analysis', {})
            if not isinstance(analysis, dict):
                analysis = {}
        
        # 1. AI Analyzer structure: analysis.tools.{tool_name}
        ai_tools = analysis.get('tools', {})
        if isinstance(ai_tools, dict):
            for tool_name, tool_data in ai_tools.items():
                if isinstance(tool_data, dict) and 'status' in tool_data:
                    tools[tool_name] = self._normalize_tool_data(tool_data, tool_name=tool_name)
        
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
                            if tool_name.startswith('_'):
                                continue
                            if isinstance(tool_data, dict) and ('status' in tool_data or 'executed' in tool_data):
                                if tool_name not in tools:
                                    tools[tool_name] = self._normalize_tool_data(tool_data, tool_name=tool_name)
                    elif 'status' in value or 'executed' in value:
                        # Direct tool entry
                        tools[key] = self._normalize_tool_data(value, tool_name=key)
        
        # 3. Performance analyzer: results keyed by URL, each URL has per-tool data
        # Extract per-tool metrics from URL-keyed results
        if isinstance(results, dict):
            for url_key, url_data in results.items():
                if url_key == 'tool_runs' or not isinstance(url_data, dict):
                    continue
                # Check if this looks like URL-keyed performance data
                perf_tool_names = {'ab', 'locust', 'artillery', 'aiohttp'}
                if any(t in url_data for t in perf_tool_names):
                    for pt_name in perf_tool_names:
                        pt_data = url_data.get(pt_name, {})
                        if isinstance(pt_data, dict) and pt_data:
                            normalized = self._normalize_tool_data(pt_data, tool_name=pt_name)
                            if pt_name in tools:
                                # Merge metrics from multiple URLs
                                existing = tools[pt_name]
                                existing['executions'] = existing.get('executions', 0) + 1
                                if 'metrics' in normalized and 'metrics' in existing:
                                    # Keep first set of metrics; downstream aggregation handles cross-app
                                    pass
                            else:
                                tools[pt_name] = normalized
        
        # 4. Direct tool_results structure (dynamic/perf analyzers)
        tool_results = analysis.get('tool_results', {}) or service_data.get('tool_results', {})
        if isinstance(tool_results, dict):
            for tool_name, tool_data in tool_results.items():
                if isinstance(tool_data, dict) and tool_name not in tools:
                    tools[tool_name] = self._normalize_tool_data(tool_data, tool_name=tool_name)
        
        # 5. Enrich ZAP tool with severity from zap_security_scan list
        if isinstance(results, dict):
            zap_scan = results.get('zap_security_scan', [])
            if isinstance(zap_scan, list) and zap_scan and 'zap' in tools:
                sev_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
                for scan_entry in zap_scan:
                    if not isinstance(scan_entry, dict):
                        continue
                    abr = scan_entry.get('alerts_by_risk', {})
                    if isinstance(abr, dict):
                        for risk_level, alerts in abr.items():
                            if isinstance(alerts, list):
                                key = risk_level.lower()
                                if key == 'informational':
                                    key = 'info'
                                if key in sev_counts:
                                    sev_counts[key] += len(alerts)
                if any(v > 0 for v in sev_counts.values()):
                    tools['zap']['severity_breakdown'] = sev_counts
                    tools['zap']['total_issues'] = sum(sev_counts.values())
        
        return tools
    
    def _normalize_tool_data(self, tool_data: Dict[str, Any],
                             tool_name: str = '') -> Dict[str, Any]:
        """Normalize tool data to consistent format with tool-aware extraction.
        
        Handles different data schemas:
        - Standard: issues list with severity per item
        - Vulnerability tools (safety, pip-audit): vulnerabilities list
        - npm-audit: vulnerabilities dict keyed by package name
        - Output-only tools (semgrep, ruff, eslint): output string + issue_count
        - Performance tools (ab, locust, artillery, aiohttp): metrics not findings
        - AI tools (requirements-scanner, code-quality-analyzer): scores/compliance
        """
        status = tool_data.get('status', 'unknown')
        if status in ('success', 'completed', 'no_issues'):
            status = 'success'
        elif tool_data.get('executed') is False:
            status = 'skipped'
        
        # Base normalized data
        normalized: Dict[str, Any] = {
            'status': status,
            'total_issues': tool_data.get('total_issues') or tool_data.get('issue_count', 0),
            'duration_seconds': tool_data.get('duration_seconds', 0) or 0,
            'issues': [],
            'executed': tool_data.get('executed', True),
            'severity_breakdown': {},
        }
        
        # Use severity_breakdown if available (most reliable for static tools)
        sev_bd = tool_data.get('severity_breakdown', {})
        if isinstance(sev_bd, dict) and sev_bd:
            normalized['severity_breakdown'] = {
                k.lower(): v for k, v in sev_bd.items() if isinstance(v, (int, float))
            }
        
        # Extract issues from the correct field based on tool type
        issues = tool_data.get('issues', [])
        vulns = tool_data.get('vulnerabilities')
        
        if isinstance(issues, list) and issues:
            normalized['issues'] = issues
        elif isinstance(vulns, list) and vulns:
            # safety, pip-audit: vulnerabilities is a list
            normalized['issues'] = vulns
            if not normalized['total_issues']:
                normalized['total_issues'] = len(vulns)
        elif isinstance(vulns, dict) and vulns:
            # npm-audit: vulnerabilities is a dict keyed by package name
            normalized['issues'] = list(vulns.values())
            if not normalized['total_issues']:
                normalized['total_issues'] = len(vulns)
        
        # Performance tool metrics
        perf_tools = {'ab', 'locust', 'artillery', 'aiohttp'}
        if tool_name in perf_tools:
            normalized['tool_type'] = 'performance'
            normalized['metrics'] = {
                'requests_per_second': tool_data.get('requests_per_second'),
                'avg_response_time': tool_data.get('avg_response_time'),
                'failed_requests': tool_data.get('failed_requests',
                                                  tool_data.get('failures',
                                                               tool_data.get('errors', 0))),
                'completed_requests': tool_data.get('completed_requests',
                                                     tool_data.get('requests', 0)),
                'p95_response_time': tool_data.get('p95_response_time'),
            }
        
        # AI tool metrics
        ai_tools = {'requirements-scanner', 'code-quality-analyzer'}
        if tool_name in ai_tools:
            normalized['tool_type'] = 'ai'
            results = tool_data.get('results', {})
            summary = results.get('summary', {}) if isinstance(results, dict) else {}
            if isinstance(summary, dict) and summary:
                normalized['metrics'] = {
                    'compliance_percentage': summary.get('compliance_percentage'),
                    'aggregate_score': summary.get('aggregate_score'),
                    'quality_grade': summary.get('quality_grade'),
                    'requirements_met': summary.get('requirements_met'),
                    'total_requirements': summary.get('total_requirements'),
                    'metrics_passed': summary.get('metrics_passed'),
                    'total_metrics': summary.get('total_metrics'),
                }
        
        # Curl-endpoint-tester: extract endpoint test pass/fail data
        if tool_name == 'curl-endpoint-tester':
            normalized['tool_type'] = 'dynamic'
            et = tool_data.get('endpoint_tests', {})
            if isinstance(et, dict) and et:
                normalized['endpoint_metrics'] = {
                    'endpoints_total': et.get('total', 0),
                    'endpoints_passed': et.get('passed', 0),
                    'endpoints_failed': et.get('failed', 0),
                }
        
        return normalized
    
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
        elif report_type == 'comprehensive':
            return {
                'total_models': summary.get('total_models', 0),
                'total_templates': summary.get('total_templates', 0),
                'total_apps': summary.get('total_apps', 0),
                'total_findings': summary.get('total_findings', 0),
                'templates_compared': summary.get('templates_compared', 0),
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
