"""Analysis Inspection Service
================================

Provides read-only inspection utilities for `AnalysisTask` entities including
listing with filters, detailed task metadata aggregation, and retrieval of
result summary JSON blobs for lazy-loaded UI panels.

Design Goals:
 - No side effects (pure read operations)
 - Uses standardized exceptions from `service_base`
 - Returns ORM objects for list views (templates already expect attribute access)
 - Derives helpful computed fields (durations, elapsed)
 - Safely handles malformed JSON stored in text columns
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json

from .service_base import NotFoundError, ValidationError
from ..models import AnalysisTask, AnalysisResult


def _ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware by adding UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class AnalysisInspectionService:
    """Read-only inspection utilities for analysis tasks."""

    # ------------- Listing -------------------------------------------------
    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        analysis_type: Optional[str] = None,
        model: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AnalysisTask]:
        """List tasks with lightweight filtering.

        Parameters accept raw enum values (e.g., 'pending', 'security').
        A small textual search is supported against task_id and task_name.
        """
        query = AnalysisTask.query
        if status:
            query = query.filter(AnalysisTask.status == status)
        if analysis_type:
            query = query.filter(AnalysisTask.analysis_type == analysis_type)
        if model:
            query = query.filter(AnalysisTask.target_model == model)
        if priority:
            query = query.filter(AnalysisTask.priority == priority)
        if search:
            like = f"%{search}%"
            query = query.filter(
                (AnalysisTask.task_id.ilike(like)) | (AnalysisTask.task_name.ilike(like))
            )
        return query.order_by(AnalysisTask.created_at.desc()).offset(offset).limit(limit).all()

    # ------------- Single Task --------------------------------------------
    def get_task(self, task_id: str) -> AnalysisTask:
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            raise NotFoundError(f"AnalysisTask not found: {task_id}")
        return task

    def get_task_detail(self, task_id: str) -> Dict[str, Any]:
        """Return enriched dictionary representation of a task."""
        task = self.get_task(task_id)
        data = task.to_dict()
        now = datetime.now(timezone.utc)
        
        # Derived durations - ensure all datetimes are timezone-aware
        if task.started_at and not task.completed_at:
            started_aware = _ensure_timezone_aware(task.started_at)
            data['elapsed_seconds'] = (now - started_aware).total_seconds()
        if task.started_at and task.completed_at:
            started_aware = _ensure_timezone_aware(task.started_at)
            completed_aware = _ensure_timezone_aware(task.completed_at)
            data['elapsed_seconds'] = (completed_aware - started_aware).total_seconds()
        if task.created_at:
            created_aware = _ensure_timezone_aware(task.created_at)
            data['age_seconds'] = (now - created_aware).total_seconds()
        # Provide simplified status flags
        status_val = data.get('status') or ''
        data['is_active'] = status_val in ('running', 'pending')
        data['is_finished'] = status_val in ('completed', 'failed', 'cancelled')
        data['has_error'] = bool(task.error_message)
        # Count attached results (if any)
        data['results_count'] = len(getattr(task, 'results', []) or [])
        return data

    # ------------- Results JSON -------------------------------------------
    def get_task_results_payload(self, task_id: str) -> Dict[str, Any]:
        """Return comprehensive structured JSON payload with ALL available metadata.

        Extracts maximum information from all analysis tools including:
        - Bandit: test_id, CWE mapping, confidence, line ranges, more_info URLs
        - PyLint: message-id, symbol, module, column info, end positions
        - ESLint: ruleId, messageId, severity levels, fixable status
        - MyPy: error codes, column ranges, note/suggestions
        - Tool metrics and configuration details
        """
        task = self.get_task(task_id)
        
        # Extract analysis results from task metadata
        metadata = task.get_metadata()
        analysis_data = metadata.get('analysis', {})
        
        # Build comprehensive summary from metadata
        summary = analysis_data.get('summary', {})
        
        # Extract severity breakdown
        severity = summary.get('severity_breakdown', {})
        
        # Extract detailed findings with ALL available information
        findings: List[Dict[str, Any]] = []
        total_issues = 0
        tool_metrics: Dict[str, Any] = {}
        
        if 'results' in analysis_data:
            results = analysis_data['results']
            
            # Process Python tool results with comprehensive metadata
            if 'python' in results:
                python_results = results['python']
                
                # Process Bandit issues - extract ALL fields
                if 'bandit' in python_results:
                    bandit_data = python_results['bandit']
                    tool_metrics['bandit'] = {
                        'status': bandit_data.get('status'),
                        'total_issues': bandit_data.get('total_issues', 0),
                        'metrics': bandit_data.get('metrics', {}),
                        'config_used': bandit_data.get('config_used', {})
                    }
                    
                    if 'issues' in bandit_data:
                        for issue in bandit_data['issues'][:50]:  # Increased limit
                            # Extract comprehensive Bandit metadata
                            finding = {
                                'tool': 'bandit',
                                'severity': issue.get('issue_severity', 'unknown').lower(),
                                'confidence': issue.get('issue_confidence', 'unknown').lower(),
                                'title': issue.get('issue_text', 'Security issue'),
                                'category': issue.get('test_name', 'security'),
                                'file_path': issue.get('filename', '').replace('/app/sources/', ''),
                                'line_number': issue.get('line_number'),
                                'line_range': issue.get('line_range', []),
                                'column_offset': issue.get('col_offset'),
                                'end_column_offset': issue.get('end_col_offset'),
                                'message': issue.get('issue_text', ''),
                                'test_id': issue.get('test_id'),
                                'test_name': issue.get('test_name'),
                                'code_snippet': issue.get('code', '').strip(),
                                'more_info_url': issue.get('more_info', ''),
                                # CWE mapping
                                'cwe_id': issue.get('issue_cwe', {}).get('id') if isinstance(issue.get('issue_cwe'), dict) else None,
                                'cwe_link': issue.get('issue_cwe', {}).get('link') if isinstance(issue.get('issue_cwe'), dict) else None,
                                # Raw data for advanced analysis
                                'raw_data': issue
                            }
                            findings.append(finding)
                
                # Process PyLint issues - extract ALL fields
                if 'pylint' in python_results:
                    pylint_data = python_results['pylint']
                    tool_metrics['pylint'] = {
                        'status': pylint_data.get('status'),
                        'total_issues': pylint_data.get('total_issues', 0),
                        'files_analyzed': pylint_data.get('files_analyzed', 0),
                        'config_used': pylint_data.get('config_used', {})
                    }
                    
                    if 'issues' in pylint_data:
                        for issue in pylint_data['issues'][:50]:  # Increased limit
                            # Extract comprehensive PyLint metadata
                            finding = {
                                'tool': 'pylint',
                                'severity': issue.get('type', 'unknown').lower(),
                                'title': issue.get('message', 'Code quality issue'),
                                'category': issue.get('symbol', 'code-quality'),
                                'file_path': issue.get('path', ''),
                                'line_number': issue.get('line'),
                                'column': issue.get('column'),
                                'end_line': issue.get('endLine'),
                                'end_column': issue.get('endColumn'),
                                'message': issue.get('message', ''),
                                'symbol': issue.get('symbol'),
                                'message_id': issue.get('message-id'),
                                'module': issue.get('module'),
                                'obj': issue.get('obj', ''),
                                # Raw data for advanced analysis
                                'raw_data': issue
                            }
                            findings.append(finding)
                
                # Process MyPy issues - extract ALL fields
                if 'mypy' in python_results:
                    mypy_data = python_results['mypy']
                    tool_metrics['mypy'] = {
                        'status': mypy_data.get('status'),
                        'total_issues': mypy_data.get('total_issues', 0),
                        'config_used': mypy_data.get('config_used', {})
                    }
                    
                    if 'issues' in mypy_data:
                        for issue in mypy_data['issues'][:50]:  # Increased limit
                            finding = {
                                'tool': 'mypy',
                                'severity': issue.get('severity', 'error').lower(),
                                'title': issue.get('message', 'Type checking issue'),
                                'category': issue.get('error_code', 'type-check'),
                                'file_path': issue.get('file', ''),
                                'line_number': issue.get('line'),
                                'column': issue.get('column'),
                                'end_line': issue.get('end_line'),
                                'end_column': issue.get('end_column'),
                                'message': issue.get('message', ''),
                                'error_code': issue.get('error_code'),
                                'note': issue.get('note', ''),
                                'suggestion': issue.get('suggestion', ''),
                                # Raw data for advanced analysis
                                'raw_data': issue
                            }
                            findings.append(finding)
            
            # Process JavaScript tool results with comprehensive metadata
            if 'javascript' in results:
                js_results = results['javascript']
                
                # Process ESLint issues - extract ALL fields
                if 'eslint' in js_results:
                    eslint_data = js_results['eslint']
                    tool_metrics['eslint'] = {
                        'status': eslint_data.get('status'),
                        'total_issues': eslint_data.get('total_issues', 0),
                        'config_used': eslint_data.get('config_used', {})
                    }
                    
                    if 'issues' in eslint_data:
                        for issue in eslint_data['issues'][:50]:  # Increased limit
                            # Extract comprehensive ESLint metadata
                            finding = {
                                'tool': 'eslint',
                                'severity': self._map_eslint_severity(issue.get('severity', 1)),
                                'title': issue.get('message', 'JavaScript issue'),
                                'category': issue.get('ruleId', 'javascript'),
                                'file_path': issue.get('filePath', ''),
                                'line_number': issue.get('line'),
                                'column': issue.get('column'),
                                'end_line': issue.get('endLine'),
                                'end_column': issue.get('endColumn'),
                                'message': issue.get('message', ''),
                                'rule_id': issue.get('ruleId'),
                                'message_id': issue.get('messageId'),
                                'node_type': issue.get('nodeType'),
                                'source': issue.get('source', ''),
                                'is_fixable': issue.get('fix') is not None,
                                'fix_range': issue.get('fix', {}).get('range', []) if issue.get('fix') else [],
                                'suggestions': issue.get('suggestions', []),
                                # Raw data for advanced analysis
                                'raw_data': issue
                            }
                            findings.append(finding)
            
            # Process CSS tool results
            if 'css' in results:
                css_results = results['css']
                if 'stylelint' in css_results:
                    stylelint_data = css_results['stylelint']
                    tool_metrics['stylelint'] = {
                        'status': stylelint_data.get('status'),
                        'total_issues': stylelint_data.get('total_issues', 0),
                        'config_used': stylelint_data.get('config_used', {})
                    }
                    
                    if 'issues' in stylelint_data:
                        for issue in stylelint_data['issues'][:50]:
                            finding = {
                                'tool': 'stylelint',
                                'severity': issue.get('severity', 'error').lower(),
                                'title': issue.get('text', 'CSS issue'),
                                'category': issue.get('rule', 'css'),
                                'file_path': issue.get('source', ''),
                                'line_number': issue.get('line'),
                                'column': issue.get('column'),
                                'message': issue.get('text', ''),
                                'rule': issue.get('rule'),
                                # Raw data for advanced analysis
                                'raw_data': issue
                            }
                            findings.append(finding)
        
        # Calculate total issues from summary or count findings
        total_issues = summary.get('total_issues_found', len(findings))
        
        # Enhanced payload with comprehensive metadata
        payload = {
            'task_id': task.task_id,
            'status': getattr(task.status, 'value', task.status),
            'analysis_type': getattr(task.analysis_type, 'value', task.analysis_type),
            'model_slug': analysis_data.get('model_slug'),
            'app_number': analysis_data.get('app_number'),
            'analysis_time': analysis_data.get('analysis_time'),
            'tools_used': analysis_data.get('tools_used', []),
            'configuration_applied': analysis_data.get('configuration_applied', False),
            'summary': summary,
            'severity_breakdown': severity,
            'tool_metrics': tool_metrics,
            'structure_analysis': results.get('structure', {}) if 'results' in analysis_data else {},
            'findings_preview': findings,
            'findings_total': total_issues,
            'findings_by_tool': self._group_findings_by_tool(findings),
            'findings_by_severity': self._group_findings_by_severity(findings),
            'metadata': {
                'extraction_version': '2.0',
                'comprehensive_parsing': True,
                'raw_data_included': True
            }
        }
        return payload

    def _map_eslint_severity(self, severity: int) -> str:
        """Map ESLint numeric severity to string."""
        return {1: 'warning', 2: 'error'}.get(severity, 'unknown')

    def _group_findings_by_tool(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group findings count by tool."""
        groups = {}
        for finding in findings:
            tool = finding.get('tool', 'unknown')
            groups[tool] = groups.get(tool, 0) + 1
        return groups

    def _group_findings_by_severity(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group findings count by severity."""
        groups = {}
        for finding in findings:
            severity = finding.get('severity', 'unknown')
            groups[severity] = groups.get(severity, 0) + 1
        return groups

    def get_task_results_json(self, task_id: str) -> str:
        """Return pretty JSON string for UI rendering."""
        try:
            payload = self.get_task_results_payload(task_id)
        except NotFoundError:
            raise
        try:
            return json.dumps(payload, indent=2, sort_keys=True)
        except Exception as e:  # pragma: no cover - defensive
            raise ValidationError(f"Failed to serialize results: {e}")

__all__ = ["AnalysisInspectionService"]
