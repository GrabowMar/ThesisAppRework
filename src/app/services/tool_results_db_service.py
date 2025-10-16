"""
Tool Results Database Service
============================

Service for converting JSON analysis results to database records
and managing tool execution data for performance optimization.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..extensions import db
from ..models.tool_results import ToolExecutionResult, ToolExecutionSummary
from ..models.analysis_models import AnalysisTask
from ..utils.time import utc_now

logger = logging.getLogger(__name__)


class ToolResultsDBService:
    """Service for managing tool results in the database."""
    
    # Tool metadata for categorization and display
    TOOL_METADATA = {
        'bandit': {'name': 'Bandit', 'description': 'Python security linter', 'icon': 'shield-alt', 'category': 'security'},
        'safety': {'name': 'Safety', 'description': 'Python dependency vulnerability checker', 'icon': 'shield-check', 'category': 'security'},
        'semgrep': {'name': 'Semgrep', 'description': 'Static analysis for security bugs', 'icon': 'search', 'category': 'security'},
        'zap': {'name': 'OWASP ZAP', 'description': 'Web application security scanner', 'icon': 'spider', 'category': 'security'},
        'pylint': {'name': 'Pylint', 'description': 'Python code quality checker', 'icon': 'code', 'category': 'quality'},
        'eslint': {'name': 'ESLint', 'description': 'JavaScript linter', 'icon': 'js-square', 'category': 'quality'},
        'jshint': {'name': 'JSHint', 'description': 'JavaScript code quality tool', 'icon': 'js-square', 'category': 'quality'},
        'mypy': {'name': 'MyPy', 'description': 'Python static type checker', 'icon': 'check-circle', 'category': 'quality'},
        'vulture': {'name': 'Vulture', 'description': 'Dead code finder for Python', 'icon': 'trash', 'category': 'quality'},
        'ab': {'name': 'Apache Bench', 'description': 'HTTP server benchmarking tool', 'icon': 'tachometer-alt', 'category': 'performance'},
        'locust': {'name': 'Locust', 'description': 'Load testing tool', 'icon': 'bug', 'category': 'performance'},
        'aiohttp': {'name': 'aiohttp', 'description': 'Async HTTP client/server', 'icon': 'network-wired', 'category': 'performance'},
        'curl': {'name': 'cURL', 'description': 'HTTP client tool', 'icon': 'download', 'category': 'dynamic'},
        'nmap': {'name': 'Nmap', 'description': 'Network discovery and security auditing', 'icon': 'sitemap', 'category': 'dynamic'}
    }
    
    def store_tool_results_from_json(self, task_id: str, json_results: Dict[str, Any]) -> bool:
        """
        Convert JSON analysis results to database records.
        
        Args:
            task_id: The analysis task ID
            json_results: Raw JSON results from analysis
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract tool results from JSON
            results = json_results.get('results', {})
            tools_data = results.get('tools', {})
            raw_outputs = results.get('raw_outputs', {})
            summary_data = results.get('summary', {})
            
            if not tools_data:
                logger.warning(f"No tools data found for task {task_id}")
                return True  # Not an error, just no tools
            
            # Clear existing results for this task
            self.clear_tool_results(task_id)
            
            # Process each tool
            tool_results = []
            category_counts = {'security': 0, 'quality': 0, 'performance': 0, 'dynamic': 0, 'other': 0}
            summary_stats = {
                'total_tools': 0,
                'executed_tools': 0,
                'successful_tools': 0,
                'failed_tools': 0,
                'not_available_tools': 0,
                'total_execution_time': 0.0,
                'total_issues_found': 0
            }
            
            tools_used = summary_data.get('tools_used', [])
            tools_failed = summary_data.get('tools_failed', [])
            
            for tool_name, tool_data in tools_data.items():
                # Get tool metadata
                metadata = self.TOOL_METADATA.get(tool_name, {
                    'name': tool_name.replace('_', ' ').title(),
                    'description': f'{tool_name} analysis tool',
                    'icon': 'cog',
                    'category': 'other'
                })
                
                # Determine status
                status = tool_data.get('status', 'unknown')
                executed = tool_data.get('executed', False)
                duration = tool_data.get('duration_seconds', 0.0)
                total_issues = tool_data.get('total_issues', 0)
                exit_code = tool_data.get('exit_code')
                error_msg = tool_data.get('error')
                
                # Get output information
                raw_output = raw_outputs.get(tool_name, {})
                stdout = raw_output.get('stdout', '')
                stderr = raw_output.get('stderr', '')
                has_output = bool(stdout or stderr)
                
                # Create database record
                tool_result = ToolExecutionResult(  # type: ignore[call-arg]
                    task_id=task_id,
                    tool_name=tool_name,
                    display_name=metadata['name'],
                    description=metadata['description'],
                    category=metadata['category'],
                    icon=metadata['icon'],
                    status=status,
                    executed=executed,
                    duration_seconds=duration,
                    exit_code=exit_code,
                    total_issues=total_issues,
                    error_message=error_msg,
                    has_output=has_output,
                    output_size=len(stdout) + len(stderr),
                    stdout_preview=stdout[:500] if stdout else None,
                    stderr_preview=stderr[:500] if stderr else None,
                    in_summary_used=tool_name in tools_used,
                    in_summary_failed=tool_name in tools_failed
                )
                
                # Set additional metadata
                if tool_data:
                    tool_result.set_metadata({
                        'raw_output': raw_output,
                        'command_line': tool_data.get('command_line', ''),
                        'tool_version': tool_data.get('tool_version')
                    })
                
                tool_results.append(tool_result)
                
                # Update counters
                category = metadata['category']
                category_counts[category] += 1
                summary_stats['total_tools'] += 1
                
                if executed:
                    summary_stats['executed_tools'] += 1
                    if duration:
                        summary_stats['total_execution_time'] += duration
                
                if status == 'success':
                    summary_stats['successful_tools'] += 1
                elif status == 'error':
                    summary_stats['failed_tools'] += 1
                elif status == 'not_available':
                    summary_stats['not_available_tools'] += 1
                
                summary_stats['total_issues_found'] += total_issues
            
            # Create summary record
            summary = ToolExecutionSummary(  # type: ignore[call-arg]
                task_id=task_id,
                total_tools=summary_stats['total_tools'],
                executed_tools=summary_stats['executed_tools'],
                successful_tools=summary_stats['successful_tools'],
                failed_tools=summary_stats['failed_tools'],
                not_available_tools=summary_stats['not_available_tools'],
                security_tools=category_counts['security'],
                quality_tools=category_counts['quality'],
                performance_tools=category_counts['performance'],
                dynamic_tools=category_counts['dynamic'],
                other_tools=category_counts['other'],
                total_execution_time=summary_stats['total_execution_time'],
                total_issues_found=summary_stats['total_issues_found']
            )
            
            # Calculate average execution time
            summary.calculate_metrics()
            
            # Set tool lists
            summary.set_tools_used(tools_used)
            summary.set_tools_failed(tools_failed)
            summary.set_tools_skipped([])
            
            # Save to database
            db.session.add_all(tool_results)
            db.session.add(summary)
            db.session.commit()
            
            logger.info(f"Stored {len(tool_results)} tool results for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing tool results for task {task_id}: {e}")
            db.session.rollback()
            return False
    
    def clear_tool_results(self, task_id: str) -> None:
        """Clear existing tool results for a task."""
        try:
            ToolExecutionResult.query.filter_by(task_id=task_id).delete()
            ToolExecutionSummary.query.filter_by(task_id=task_id).delete()
            db.session.commit()
        except Exception as e:
            logger.error(f"Error clearing tool results for task {task_id}: {e}")
            db.session.rollback()
    
    def get_tools_data_from_db(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tool data from database for fast loading.
        
        Args:
            task_id: The analysis task ID
            
        Returns:
            Structured tool data or None if not found
        """
        try:
            # Get summary
            summary = ToolExecutionSummary.query.filter_by(task_id=task_id).first()
            if not summary:
                return None
            
            # Get tool results
            tool_results = ToolExecutionResult.query.filter_by(task_id=task_id).all()
            
            # Group tools by category
            tool_categories = {
                'security': [],
                'quality': [],
                'performance': [],
                'dynamic': [],
                'other': []
            }
            
            tool_cards = []
            for tool in tool_results:
                # Add to category
                category = tool.category or 'other'
                if category in tool_categories:
                    tool_categories[category].append(tool.tool_name)
                else:
                    tool_categories['other'].append(tool.tool_name)
                
                # Create card data - use simpler attribute access
                card_data = {
                    'tool_name': tool.tool_name,
                    'display_name': tool.display_name,
                    'description': tool.description or '',
                    'icon': tool.icon or 'cog',
                    'category': (tool.category or 'other').title(),
                    'status': tool.status or 'unknown',
                    'status_class': self._get_status_class(tool.status),
                    'status_icon': self._get_status_icon(tool.status),
                    'badge_class': self._get_badge_class(tool.status),
                    'executed': tool.executed or False,
                    'duration': f"{tool.duration_seconds:.2f}s" if tool.duration_seconds else "—",
                    'total_issues': tool.total_issues or 0,
                    'exit_code': tool.exit_code,
                    'error_message': tool.error_message,
                    'has_output': tool.has_output or False,
                    'in_summary_used': tool.in_summary_used or False,
                    'in_summary_failed': tool.in_summary_failed or False
                }
                tool_cards.append(card_data)
            
            # Sort cards by category, then status, then name
            tool_cards.sort(key=lambda x: (
                x['category'], 
                0 if x['status'] == 'success' else 1, 
                x['display_name']
            ))
            
            return {
                'tool_categories': tool_categories,
                'tool_cards': tool_cards,
                'summary': {
                    'total_tools': summary.total_tools,
                    'executed': summary.executed_tools,
                    'successful': summary.successful_tools,
                    'failed': summary.failed_tools,
                    'not_available': summary.not_available_tools,
                    'tools_used': summary.get_tools_used(),
                    'tools_failed': summary.get_tools_failed()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting tools data from DB for task {task_id}: {e}")
            return None
    
    def _get_status_class(self, status: str) -> str:
        """Get Bootstrap CSS class for status."""
        mapping = {
            'success': 'success',
            'error': 'danger',
            'not_available': 'secondary',
            'unknown': 'warning'
        }
        return mapping.get(status, 'secondary')
    
    def _get_status_icon(self, status: str) -> str:
        """Get FontAwesome icon for status."""
        mapping = {
            'success': 'check-circle',
            'error': 'exclamation-triangle',
            'not_available': 'minus-circle',
            'unknown': 'question-circle'
        }
        return mapping.get(status, 'question-circle')
    
    def _get_badge_class(self, status: str) -> str:
        """Get Bootstrap badge class for status."""
        mapping = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'not_available': 'bg-secondary',
            'unknown': 'bg-warning'
        }
        return mapping.get(status, 'bg-secondary')
    
    def has_tool_results(self, task_id: str) -> bool:
        """Check if tool results exist in database for a task."""
        try:
            return ToolExecutionSummary.query.filter_by(task_id=task_id).first() is not None
        except Exception as e:
            logger.error(f"Error checking tool results for task {task_id}: {e}")
            return False