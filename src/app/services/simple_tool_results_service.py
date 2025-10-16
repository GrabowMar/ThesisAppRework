"""
Simple Tool Results Service
===========================

Service for storing and retrieving tool results from database for performance.
"""

import json
import logging
from typing import Dict, Any, Optional

from ..extensions import db
from ..models.simple_tool_results import ToolResult, ToolSummary

logger = logging.getLogger(__name__)


class SimpleToolResultsService:
    """Simple service for managing tool results in database."""
    
    # Invalid tools that should be filtered out
    INVALID_TOOLS = {
        'python', 'javascript', 'css',  # Generic language names
        'tool_runs', 'structure', 'port_scan',  # Non-analysis artifacts
    }
    
    @staticmethod
    def is_valid_tool(tool_name: str) -> bool:
        """Check if a tool name represents a valid analysis tool."""
        # Filter out invalid tools
        if tool_name in SimpleToolResultsService.INVALID_TOOLS:
            return False
        
        # Filter out URLs
        if tool_name.startswith(('http://', 'https://')):
            return False
        
        # Filter out other common non-tool patterns
        if tool_name in ('service:', 'ai-analyzer:'):
            return False
        
        return True
    
    # Tool metadata for display
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
        'nmap': {'name': 'Nmap', 'description': 'Network discovery and security auditing', 'icon': 'sitemap', 'category': 'dynamic'},
        'requirements-scanner': {'name': 'AI Requirements Scanner', 'description': 'AI-powered requirements compliance checker', 'icon': 'robot', 'category': 'quality'}
    }
    
    def store_tool_results_from_json(self, task_id: str, json_results: Dict[str, Any]) -> bool:
        """Store tool results from JSON analysis data."""
        try:
            results = json_results.get('results', {})
            tools_data = results.get('tools', {})
            raw_outputs = results.get('raw_outputs', {})
            summary_data = results.get('summary', {})
            
            if not tools_data:
                logger.info(f"No tools data found for task {task_id}")
                return True
            
            # Clear existing results
            self.clear_tool_results(task_id)
            
            tool_records = []
            category_counts = {'security': 0, 'quality': 0, 'performance': 0, 'dynamic': 0, 'other': 0}
            
            total_tools = 0
            executed_tools = 0
            successful_tools = 0
            failed_tools = 0
            not_available_tools = 0
            total_issues = 0
            
            tools_used = summary_data.get('tools_used', [])
            tools_failed = summary_data.get('tools_failed', [])
            
            for tool_name, tool_data in tools_data.items():
                # Skip invalid tools
                if not self.is_valid_tool(tool_name):
                    logger.debug(f"Skipping invalid tool: {tool_name}")
                    continue
                
                metadata = self.TOOL_METADATA.get(tool_name, {
                    'name': tool_name.replace('_', ' ').title(),
                    'description': f'{tool_name} analysis tool',
                    'icon': 'cog',
                    'category': 'other'
                })
                
                status = tool_data.get('status', 'unknown')
                executed = tool_data.get('executed', False)
                duration = tool_data.get('duration_seconds', 0.0)
                issues = tool_data.get('total_issues', 0)
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
                            issues = total_reqs  # Use total requirements as issues count
                            logger.info(f"AI Requirements Scanner: Found {total_reqs} total requirements for task {task_id}")
                
                # Fix status inconsistencies based on summary lists
                if tool_name in tools_failed:
                    # Tool is in failed list - check if it should be 'error' instead of 'not_available'
                    if status == 'not_available' and executed:
                        status = 'error'  # Was executed but failed
                        logger.debug(f"Fixed status for {tool_name}: not_available -> error (executed but failed)")
                elif tool_name in tools_used and status == 'not_available' and not executed:
                    # Tool is in used list but marked as not_available - this is likely wrong
                    # Keep the original status but log the inconsistency
                    logger.warning(f"Status inconsistency for {tool_name}: marked as used but not executed")
                
                # Check if has output
                raw_output = raw_outputs.get(tool_name, {})
                has_output = bool(raw_output.get('stdout') or raw_output.get('stderr'))
                
                # Create record
                tool_record = ToolResult(
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
                    total_issues=issues,
                    error_message=error_msg,
                    has_output=has_output,
                    in_summary_used=tool_name in tools_used,
                    in_summary_failed=tool_name in tools_failed
                )
                
                # Store raw data
                tool_record.set_raw_data({
                    'tool_data': tool_data,
                    'raw_output': raw_output
                })
                
                tool_records.append(tool_record)
                
                # Update counters
                category = metadata['category']
                category_counts[category] += 1
                total_tools += 1
                total_issues += issues
                
                if executed:
                    executed_tools += 1
                
                if status == 'success':
                    successful_tools += 1
                elif status == 'error':
                    failed_tools += 1
                elif status == 'not_available':
                    not_available_tools += 1
            
            # Create summary
            summary = ToolSummary(
                task_id=task_id,
                total_tools=total_tools,
                executed_tools=executed_tools,
                successful_tools=successful_tools,
                failed_tools=failed_tools,
                not_available_tools=not_available_tools,
                total_issues_found=total_issues
            )
            
            # Store tools data
            summary.set_tools_data({
                'tools_used': tools_used,
                'tools_failed': tools_failed,
                'category_counts': category_counts
            })
            
            # Save to database
            db.session.add_all(tool_records)
            db.session.add(summary)
            db.session.commit()
            
            logger.info(f"Stored {len(tool_records)} tool results for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing tool results for task {task_id}: {e}")
            db.session.rollback()
            return False
    
    def clear_tool_results(self, task_id: str) -> None:
        """Clear existing tool results for a task."""
        try:
            ToolResult.query.filter_by(task_id=task_id).delete()
            ToolSummary.query.filter_by(task_id=task_id).delete()
            db.session.commit()
        except Exception as e:
            logger.error(f"Error clearing tool results for task {task_id}: {e}")
            db.session.rollback()
    
    def get_tools_data_from_db(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get structured tool data from database."""
        try:
            # Check if we have data
            summary = ToolSummary.query.filter_by(task_id=task_id).first()
            if not summary:
                return None
            
            # Get all tool results
            tool_results = ToolResult.query.filter_by(task_id=task_id).all()
            
            # Build categories
            tool_categories = {
                'security': [],
                'quality': [],
                'performance': [],
                'dynamic': [],
                'other': []
            }
            
            tool_cards = []
            
            for tool in tool_results:
                # Add to category list
                category = getattr(tool, 'category', 'other') or 'other'
                tool_name = getattr(tool, 'tool_name', '')
                if category in tool_categories:
                    tool_categories[category].append(tool_name)
                else:
                    tool_categories['other'].append(tool_name)
                
                # Create card data
                status = getattr(tool, 'status', 'unknown') or 'unknown'
                duration = getattr(tool, 'duration_seconds', None)
                
                card_data = {
                    'tool_name': tool_name,
                    'display_name': getattr(tool, 'display_name', tool_name),
                    'description': getattr(tool, 'description', ''),
                    'icon': getattr(tool, 'icon', 'cog'),
                    'category': category.title(),
                    'status': status,
                    'status_class': self._get_status_class(status),
                    'status_icon': self._get_status_icon(status),
                    'badge_class': self._get_badge_class(status),
                    'executed': getattr(tool, 'executed', False) or False,
                    'duration': f"{duration:.2f}s" if duration else "—",
                    'total_issues': getattr(tool, 'total_issues', 0) or 0,
                    'exit_code': getattr(tool, 'exit_code', None),
                    'error_message': getattr(tool, 'error_message', None),
                    'has_output': getattr(tool, 'has_output', False) or False,
                    'in_summary_used': getattr(tool, 'in_summary_used', False) or False,
                    'in_summary_failed': getattr(tool, 'in_summary_failed', False) or False
                }
                tool_cards.append(card_data)
            
            # Sort tool cards
            tool_cards.sort(key=lambda x: (x['category'], 0 if x['status'] == 'success' else 1, x['display_name']))
            
            # Get summary data
            summary_data = summary.get_tools_data()
            
            return {
                'tool_categories': tool_categories,
                'tool_cards': tool_cards,
                'summary': {
                    'total_tools': getattr(summary, 'total_tools', 0) or 0,
                    'executed': getattr(summary, 'executed_tools', 0) or 0,
                    'successful': getattr(summary, 'successful_tools', 0) or 0,
                    'failed': getattr(summary, 'failed_tools', 0) or 0,
                    'not_available': getattr(summary, 'not_available_tools', 0) or 0,
                    'tools_used': summary_data.get('tools_used', []),
                    'tools_failed': summary_data.get('tools_failed', [])
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting tools data from DB for task {task_id}: {e}")
            return None
    
    def has_tool_results(self, task_id: str) -> bool:
        """Check if tool results exist in database."""
        try:
            return ToolSummary.query.filter_by(task_id=task_id).first() is not None
        except Exception:
            return False
    
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