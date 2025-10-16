"""
Results Management Service
=========================

High-level service that combines API fetching, caching, and data transformation
to provide a unified interface for analysis results.
"""
# type: ignore

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timezone, timedelta

from .results_api_service import ResultsAPIService, AnalysisResults
from ..models.results_cache import AnalysisResultsCache
from ..extensions import db
# from .service_base import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class ResultsManagementService:
    """
    Service for managing analysis results with caching and API integration.
    
    This service provides:
    - Cached results for better performance
    - Automatic API fallback when cache is stale/missing
    - Structured data for different analysis tabs
    - Error handling and logging
    """
    
    def __init__(self, api_base_url: str = "http://127.0.0.1:5000"):
        """Initialize the results management service."""
        self.api_service = ResultsAPIService(base_url=api_base_url)
        self.cache_ttl = timedelta(hours=1)  # Cache expires after 1 hour
    
    def get_task_results(self, task_id: str, force_refresh: bool = False) -> Optional[AnalysisResults]:
        """
        Get results for a task, using cache when available.
        
        Args:
            task_id: The task ID to fetch results for
            force_refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            AnalysisResults object or None if not found
        """
        try:
            # Check cache first unless force refresh is requested
            if not force_refresh:
                cached_results = self._get_cached_results(task_id)
                if cached_results and not self._is_cache_stale(cached_results):
                    logger.debug(f"Returning cached results for task {task_id}")
                    return self._convert_cache_to_results(cached_results)
            
            # Fetch from API
            logger.info(f"Fetching fresh results from API for task {task_id}")
            api_results = self.api_service.get_task_results(task_id)
            
            if api_results:
                # Update cache
                self._update_cache(api_results)
                return api_results
            else:
                # If API fails but we have cached data, return it even if stale
                cached_results = self._get_cached_results(task_id)
                if cached_results:
                    logger.warning(f"API failed for task {task_id}, returning stale cached data")
                    setattr(cached_results, 'is_stale', True)
                    db.session.commit()
                    return self._convert_cache_to_results(cached_results)
                
                logger.error(f"No results found for task {task_id} in API or cache")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching results for task {task_id}: {e}")
            
            # Try to return cached data as fallback
            try:
                cached_results = self._get_cached_results(task_id)
                if cached_results:
                    logger.warning(f"Exception occurred, returning cached data for task {task_id}")
                    return self._convert_cache_to_results(cached_results)
            except Exception:
                pass
            
            return None
    
    def get_security_data(self, task_id: str) -> Dict[str, Any]:
        """Get security-specific data for a task."""
        results = self.get_task_results(task_id)
        if results and results.security:
            return results.security
        return self._empty_security_data()
    
    def get_performance_data(self, task_id: str) -> Dict[str, Any]:
        """Get performance-specific data for a task."""
        results = self.get_task_results(task_id)
        if results and results.performance:
            return results.performance
        return self._empty_performance_data()
    
    def get_quality_data(self, task_id: str) -> Dict[str, Any]:
        """Get code quality-specific data for a task."""
        results = self.get_task_results(task_id)
        if results and results.quality:
            return results.quality
        return self._empty_quality_data()
    
    def get_requirements_data(self, task_id: str) -> Dict[str, Any]:
        """Get AI requirements-specific data for a task."""
        results = self.get_task_results(task_id)
        if results and results.requirements:
            return results.requirements
        return self._empty_requirements_data()
    
    def get_tools_data(self, task_id: str) -> Dict[str, Any]:
        """Get comprehensive tool execution data for card display (DB-first approach)."""
        try:
            # Try database first for performance
            db_results = self._get_tools_data_from_db(task_id)
            if db_results:
                logger.debug(f"Loaded tools data from database for task {task_id}")
                return db_results
            
            logger.info(f"No database results found, fetching from API for task {task_id}")
            
            # Fallback to API (original implementation)
            raw_results = self.api_service._fetch_raw_results(task_id)
            if not raw_results:
                return self._empty_tools_data()
            
            results = raw_results.get('results', {})
            tools_data = results.get('tools', {})
            raw_outputs = results.get('raw_outputs', {})
            summary = results.get('summary', {})
            
            # Store in database for next time (async/background)
            self._store_tools_data_in_background(task_id, raw_results)
            
            # Process tools into categories
            tool_categories = self._categorize_tools(tools_data)
            tool_cards = self._create_tool_cards(tools_data, raw_outputs, summary)
            
            return {
                'tool_categories': tool_categories,
                'tool_cards': tool_cards,
                'summary': {
                    'total_tools': len(tools_data),
                    'executed': sum(1 for tool in tools_data.values() if tool.get('executed', False)),
                    'successful': sum(1 for tool in tools_data.values() if tool.get('status') == 'success'),
                    'failed': sum(1 for tool in tools_data.values() if tool.get('status') == 'error'),
                    'not_available': sum(1 for tool in tools_data.values() if tool.get('status') == 'not_available'),
                    'tools_used': summary.get('tools_used', []),
                    'tools_failed': summary.get('tools_failed', [])
                }
            }
        except Exception as e:
            logger.error(f"Error getting tools data for task {task_id}: {e}")
            return self._empty_tools_data()
    
    def get_task_summary(self, task_id: str) -> Dict[str, Any]:
        """Get a summary of task results for the overview tab."""
        results = self.get_task_results(task_id)
        if not results:
            return self._empty_summary_data()
        
        # Calculate aggregated metrics
        security_summary = results.security.get('summary', {})
        quality_summary = results.quality.get('summary', {})
        performance_metrics = results.performance.get('metrics', {})
        requirements_summary = results.requirements.get('summary', {})
        
        return {
            'task_id': results.task_id,
            'status': results.status,
            'analysis_type': results.analysis_type,
            'model_slug': results.model_slug,
            'app_number': results.app_number,
            'timestamp': results.timestamp,
            'duration': results.duration,
            'total_findings': results.total_findings,
            'tools_executed': results.tools_executed,
            'tools_failed': results.tools_failed,
            'security': {
                'total_issues': security_summary.get('total', 0),
                'critical_issues': security_summary.get('critical', 0),
                'high_issues': security_summary.get('high', 0),
                'tools_run': len(results.security.get('tools_run', []))
            },
            'performance': {
                'avg_response_time': performance_metrics.get('response_time', {}).get('value'),
                'requests_per_sec': performance_metrics.get('requests_per_sec', {}).get('value'),
                'status': 'unknown'  # Will be calculated from metrics
            },
            'quality': {
                'total_issues': (quality_summary.get('errors', 0) + 
                               quality_summary.get('warnings', 0) + 
                               quality_summary.get('info', 0)),
                'errors': quality_summary.get('errors', 0),
                'warnings': quality_summary.get('warnings', 0),
                'type_errors': quality_summary.get('type_errors', 0)
            },
            'requirements': {
                'compliance_percentage': requirements_summary.get('compliance_percentage', 0),
                'total_requirements': requirements_summary.get('total_requirements', 0),
                'met': requirements_summary.get('met', 0),
                'not_met': requirements_summary.get('not_met', 0)
            }
        }
    
    def invalidate_cache(self, task_id: str) -> bool:
        """Invalidate cached results for a task."""
        try:
            cached = AnalysisResultsCache.query.filter_by(task_id=task_id).first()
            if cached:
                cached.is_stale = True
                db.session.commit()
                logger.info(f"Invalidated cache for task {task_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error invalidating cache for task {task_id}: {e}")
            return False
    
    def clear_stale_cache(self, older_than_hours: int = 24) -> int:
        """Clear cache entries older than specified hours."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
            count = AnalysisResultsCache.query.filter(
                AnalysisResultsCache.updated_at < cutoff
            ).count()
            
            AnalysisResultsCache.query.filter(
                AnalysisResultsCache.updated_at < cutoff
            ).delete()
            
            db.session.commit()
            logger.info(f"Cleared {count} stale cache entries older than {older_than_hours} hours")
            return count
            
        except Exception as e:
            logger.error(f"Error clearing stale cache: {e}")
            db.session.rollback()
            return 0
    
    def _get_cached_results(self, task_id: str) -> Optional[AnalysisResultsCache]:
        """Get cached results for a task."""
        return AnalysisResultsCache.query.filter_by(task_id=task_id).first()
    
    def _is_cache_stale(self, cached: AnalysisResultsCache) -> bool:
        """Check if cached results are stale."""
        # Use getattr to bypass SQLAlchemy typing issues
        is_stale = getattr(cached, 'is_stale', True)
        if is_stale:
            return True
        
        updated_at = getattr(cached, 'updated_at', None)
        if updated_at:
            # Ensure both datetimes are timezone-aware for comparison
            now = datetime.now(timezone.utc)
            if updated_at.tzinfo is None:
                # Make the cached timestamp timezone-aware (assume UTC)
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            
            age = now - updated_at
            return age > self.cache_ttl
        
        return True  # Assume stale if no timestamp
    
    def _update_cache(self, results: AnalysisResults) -> None:
        """Update cache with new results."""
        try:
            # Check if cache entry exists
            cached = AnalysisResultsCache.query.filter_by(task_id=results.task_id).first()
            
            if cached:
                # Update existing entry
                cached.status = results.status
                cached.analysis_type = results.analysis_type
                cached.model_slug = results.model_slug
                cached.app_number = results.app_number
                cached.analysis_timestamp = results.timestamp
                cached.duration_seconds = results.duration
                cached.total_findings = results.total_findings
                cached.tools_executed_count = len(results.tools_executed)
                cached.tools_failed_count = len(results.tools_failed)
                cached.security_data = results.security
                cached.performance_data = results.performance
                cached.quality_data = results.quality
                cached.requirements_data = results.requirements
                cached.last_api_fetch = datetime.now(timezone.utc)
                cached.is_stale = False
                cached.set_raw_data(results.raw_data)
                cached.updated_at = datetime.now(timezone.utc)
            else:
                # Create new entry
                cached = AnalysisResultsCache.from_analysis_results(results)
                db.session.add(cached)
            
            db.session.commit()
            logger.debug(f"Updated cache for task {results.task_id}")
            
        except Exception as e:
            logger.error(f"Error updating cache for task {results.task_id}: {e}")
            db.session.rollback()
    
    def _convert_cache_to_results(self, cached: AnalysisResultsCache) -> AnalysisResults:
        """Convert cached entry to AnalysisResults object."""
        # Use getattr to safely extract values and bypass SQLAlchemy typing
        task_id = getattr(cached, 'task_id', '')
        status = getattr(cached, 'status', 'unknown')
        analysis_type = getattr(cached, 'analysis_type', 'unknown')
        model_slug = getattr(cached, 'model_slug', '')
        app_number = getattr(cached, 'app_number', 0)
        timestamp = getattr(cached, 'analysis_timestamp') or datetime.now(timezone.utc)
        total_findings = getattr(cached, 'total_findings', 0)
        duration = getattr(cached, 'duration_seconds')
        
        # Extract JSON data with safe defaults
        security_data = getattr(cached, 'security_data') or {}
        performance_data = getattr(cached, 'performance_data') or {}
        quality_data = getattr(cached, 'quality_data') or {}
        requirements_data = getattr(cached, 'requirements_data') or {}
        
        return AnalysisResults(
            task_id=task_id,
            status=status,
            analysis_type=analysis_type,
            model_slug=model_slug,
            app_number=app_number,
            timestamp=timestamp,
            total_findings=total_findings,
            duration=duration,
            tools_executed=self._extract_tools_list(security_data, quality_data),
            tools_failed=[],  # Not stored in cache currently
            security=security_data,
            performance=performance_data,
            quality=quality_data,
            requirements=requirements_data,
            raw_data=cached.get_raw_data() or {}
        )
    
    def _extract_tools_list(self, security_data: Optional[Dict], quality_data: Optional[Dict]) -> List[str]:
        """Extract list of executed tools from cached data."""
        tools = []
        
        if security_data and 'tools_run' in security_data:
            tools.extend(security_data['tools_run'])
        
        if quality_data and 'tools' in quality_data:
            executed_tools = [
                tool for tool, info in quality_data['tools'].items()
                if info.get('status') == 'success'
            ]
            tools.extend(executed_tools)
        
        return list(set(tools))  # Remove duplicates
    
    def _empty_security_data(self) -> Dict[str, Any]:
        """Return empty security data structure."""
        return {
            'findings': [],
            'summary': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'total': 0},
            'tools_run': [],
            'recommendations': []
        }
    
    def _empty_performance_data(self) -> Dict[str, Any]:
        """Return empty performance data structure."""
        return {
            'metrics': {
                'response_time': {'value': None, 'unit': 'ms', 'status': 'unknown'},
                'requests_per_sec': {'value': None, 'unit': 'req/s', 'status': 'unknown'},
                'failed_requests': {'value': None, 'unit': '%', 'status': 'unknown'},
                'max_concurrent': {'value': None, 'unit': 'users', 'status': 'unknown'}
            },
            'tools': {},
            'recommendations': []
        }
    
    def _empty_quality_data(self) -> Dict[str, Any]:
        """Return empty quality data structure."""
        return {
            'summary': {'errors': 0, 'warnings': 0, 'info': 0, 'type_errors': 0, 'dead_code': 0},
            'tools': {},
            'issues': [],
            'insights': {'import_issues': [], 'type_safety': []}
        }
    
    def _empty_requirements_data(self) -> Dict[str, Any]:
        """Return empty requirements data structure."""
        return {
            'summary': {
                'total_requirements': 0, 'met': 0, 'not_met': 0, 'partial': 0,
                'compliance_percentage': 0.0
            },
            'analysis_details': {
                'status': 'unknown', 'target_model': '', 'analysis_time': None,
                'configuration': None
            },
            'requirements': [],
            'insights': {'security_features': [], 'authentication': []}
        }
    
    def _empty_summary_data(self) -> Dict[str, Any]:
        """Return empty summary data structure."""
        return {
            'task_id': '',
            'status': 'unknown',
            'analysis_type': 'unknown',
            'model_slug': '',
            'app_number': 0,
            'timestamp': datetime.now(timezone.utc),
            'duration': None,
            'total_findings': 0,
            'tools_executed': [],
            'tools_failed': [],
            'security': {'total_issues': 0, 'critical_issues': 0, 'high_issues': 0, 'tools_run': 0},
            'performance': {'avg_response_time': None, 'requests_per_sec': None, 'status': 'unknown'},
            'quality': {'total_issues': 0, 'errors': 0, 'warnings': 0, 'type_errors': 0},
            'requirements': {'compliance_percentage': 0, 'total_requirements': 0, 'met': 0, 'not_met': 0}
        }
    
    def _empty_tools_data(self) -> Dict[str, Any]:
        """Return empty tools data structure."""
        return {
            'tool_categories': {
                'security': [],
                'quality': [],
                'performance': [],
                'dynamic': [],
                'other': []
            },
            'tool_cards': [],
            'summary': {
                'total_tools': 0,
                'executed': 0,
                'successful': 0,
                'failed': 0,
                'not_available': 0,
                'tools_used': [],
                'tools_failed': []
            }
        }
    
    def _categorize_tools(self, tools_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Categorize tools by their type/purpose."""
        categories = {
            'security': ['bandit', 'safety', 'semgrep', 'zap'],
            'quality': ['pylint', 'eslint', 'jshint', 'mypy', 'vulture'],
            'performance': ['ab', 'locust', 'aiohttp'],
            'dynamic': ['curl', 'nmap', 'zap'],
            'other': []
        }
        
        # Categorize actual tools
        result = {cat: [] for cat in categories.keys()}
        
        for tool_name in tools_data.keys():
            categorized = False
            for category, tool_list in categories.items():
                if tool_name in tool_list:
                    result[category].append(tool_name)
                    categorized = True
                    break
            
            if not categorized:
                result['other'].append(tool_name)
        
        return result
    
    def _is_invalid_tool(self, tool_name: str) -> bool:
        """Check if a tool name represents a valid analysis tool."""
        # Invalid tools that should be filtered out
        invalid_tools = {
            'python', 'javascript', 'css',  # Generic language names
            'tool_runs', 'structure', 'port_scan',  # Non-analysis artifacts
        }
        
        # Filter out invalid tools
        if tool_name in invalid_tools:
            return True
        
        # Filter out URLs
        if tool_name.startswith(('http://', 'https://')):
            return True
        
        # Filter out other common non-tool patterns
        if tool_name in ('service:', 'ai-analyzer:'):
            return True
        
        return False
    
    def _create_tool_cards(self, tools_data: Dict[str, Any], raw_outputs: Dict[str, Any], summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create tool card data for frontend display."""
        cards = []
        
        # Define tool metadata
        tool_metadata = {
            'bandit': {'name': 'Bandit', 'description': 'Python security linter', 'icon': 'shield-alt', 'category': 'Security'},
            'safety': {'name': 'Safety', 'description': 'Python dependency vulnerability checker', 'icon': 'shield-check', 'category': 'Security'},
            'semgrep': {'name': 'Semgrep', 'description': 'Static analysis for security bugs', 'icon': 'search', 'category': 'Security'},
            'zap': {'name': 'OWASP ZAP', 'description': 'Web application security scanner', 'icon': 'spider', 'category': 'Security'},
            'pylint': {'name': 'Pylint', 'description': 'Python code quality checker', 'icon': 'code', 'category': 'Quality'},
            'eslint': {'name': 'ESLint', 'description': 'JavaScript linter', 'icon': 'js-square', 'category': 'Quality'},
            'jshint': {'name': 'JSHint', 'description': 'JavaScript code quality tool', 'icon': 'js-square', 'category': 'Quality'},
            'mypy': {'name': 'MyPy', 'description': 'Python static type checker', 'icon': 'check-circle', 'category': 'Quality'},
            'vulture': {'name': 'Vulture', 'description': 'Dead code finder for Python', 'icon': 'trash', 'category': 'Quality'},
            'ab': {'name': 'Apache Bench', 'description': 'HTTP server benchmarking tool', 'icon': 'tachometer-alt', 'category': 'Performance'},
            'locust': {'name': 'Locust', 'description': 'Load testing tool', 'icon': 'bug', 'category': 'Performance'},
            'aiohttp': {'name': 'aiohttp', 'description': 'Async HTTP client/server', 'icon': 'network-wired', 'category': 'Performance'},
            'curl': {'name': 'cURL', 'description': 'HTTP client tool', 'icon': 'download', 'category': 'Dynamic'},
            'nmap': {'name': 'Nmap', 'description': 'Network discovery and security auditing', 'icon': 'sitemap', 'category': 'Dynamic'},
            'requirements-scanner': {'name': 'AI Requirements Scanner', 'description': 'AI-powered requirements compliance checker', 'icon': 'robot', 'category': 'Quality'}
        }
        
        for tool_name, tool_data in tools_data.items():
            # Skip invalid tools (same logic as SimpleToolResultsService)
            if self._is_invalid_tool(tool_name):
                continue
            
            # Get metadata or create default
            metadata = tool_metadata.get(tool_name, {
                'name': tool_name.replace('_', ' ').title(),
                'description': f'{tool_name} analysis tool',
                'icon': 'cog',
                'category': 'Other'
            })
            
            # Determine status and styling
            status = tool_data.get('status', 'unknown')
            executed = tool_data.get('executed', False)
            
            if status == 'success':
                status_class = 'success'
                status_icon = 'check-circle'
                badge_class = 'bg-success'
            elif status == 'error':
                status_class = 'danger'
                status_icon = 'exclamation-triangle'
                badge_class = 'bg-danger'
            elif status == 'not_available' or not executed:
                status_class = 'secondary'
                status_icon = 'minus-circle'
                badge_class = 'bg-secondary'
            else:
                status_class = 'warning'
                status_icon = 'question-circle'
                badge_class = 'bg-warning'
            
            # Calculate metrics
            duration = tool_data.get('duration_seconds', 0)
            total_issues = tool_data.get('total_issues', 0)
            exit_code = tool_data.get('exit_code')
            error_msg = tool_data.get('error')
            
            # Special parsing for AI requirements scanner
            if tool_name == 'requirements-scanner' and executed and status == 'success':
                # Parse the raw output to get actual requirements count
                raw_output_data = raw_outputs.get(tool_name, {})
                if 'raw_output' in raw_output_data:
                    raw_text = raw_output_data['raw_output']
                    # Look for "Total Requirements: X" pattern
                    import re
                    match = re.search(r'Total Requirements:\s*(\d+)', raw_text)
                    if match:
                        total_reqs = int(match.group(1))
                        total_issues = total_reqs  # Use total requirements as issues count
                        logger.debug(f"AI Requirements Scanner: Found {total_reqs} total requirements")
            
            card_data = {
                'tool_name': tool_name,
                'display_name': metadata['name'],
                'description': metadata['description'],
                'icon': metadata['icon'],
                'category': metadata['category'],
                'status': status,
                'status_class': status_class,
                'status_icon': status_icon,
                'badge_class': badge_class,
                'executed': executed,
                'duration': f"{duration:.2f}s" if duration else "—",
                'total_issues': total_issues,
                'exit_code': exit_code,
                'error_message': error_msg,
                'has_output': bool(raw_outputs.get(tool_name, {}).get('stdout') or raw_outputs.get(tool_name, {}).get('stderr')),
                'in_summary_used': tool_name in summary.get('tools_used', []),
                'in_summary_failed': tool_name in summary.get('tools_failed', [])
            }
            
            cards.append(card_data)
        
        # Sort by category, then by status (successful first), then by name
        cards.sort(key=lambda x: (x['category'], 0 if x['status'] == 'success' else 1, x['display_name']))
        
        return cards
    
    def _get_tools_data_from_db(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get tools data from database."""
        try:
            from .simple_tool_results_service import SimpleToolResultsService
            service = SimpleToolResultsService()
            return service.get_tools_data_from_db(task_id)
        except Exception as e:
            logger.error(f"Error loading tools data from database for task {task_id}: {e}")
            return None
    
    def _store_tools_data_in_background(self, task_id: str, raw_results: Dict[str, Any]) -> None:
        """Store tools data in database for future fast access."""
        try:
            from .simple_tool_results_service import SimpleToolResultsService
            service = SimpleToolResultsService()
            success = service.store_tool_results_from_json(task_id, raw_results)
            if success:
                logger.info(f"Successfully stored tools data in database for task {task_id}")
            else:
                logger.warning(f"Failed to store tools data in database for task {task_id}")
        except Exception as e:
            logger.error(f"Error storing tools data in database for task {task_id}: {e}")
    
    def invalidate_tools_cache(self, task_id: str) -> bool:
        """Invalidate tools data cache for a task."""
        try:
            from .simple_tool_results_service import SimpleToolResultsService
            service = SimpleToolResultsService()
            service.clear_tool_results(task_id)
            return True
        except Exception as e:
            logger.error(f"Error invalidating tools cache for task {task_id}: {e}")
            return False