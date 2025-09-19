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
from pathlib import Path

from .service_base import NotFoundError, ValidationError
from ..models import AnalysisTask


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
            query = query.filter(AnalysisTask.status == status)  # type: ignore[arg-type]
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
        # Prefer a derived status if analyzer indicated success but DB status lags
        try:
            payload = self.get_task_results_payload(task.task_id)
            if isinstance(payload, dict) and payload.get('derived_status'):
                data['derived_status'] = payload.get('derived_status')
        except Exception:
            # Non-fatal if results not yet present or any parsing error occurs
            pass
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
        metadata = task.get_metadata() or {}
        # Support both legacy shape (metadata['analysis']) and new orchestrator shape (metadata at top-level)
        if 'analysis' in metadata:
            analysis_data = metadata.get('analysis', {})
            summary = analysis_data.get('summary', {})
            results = analysis_data.get('results', {})
        else:
            # Orchestrator payload lives at the top level with 'summary', 'findings', 'tool_results'
            analysis_data = metadata
            summary = metadata.get('summary', {})
            # Prefer tool_results; some producers use 'results'
            results = metadata.get('tool_results') or metadata.get('results') or {}

        # Best-effort fallback: if results look empty, try to load the latest persisted analyzer result file
        model_slug = (analysis_data.get('model_slug') or task.target_model)
        app_number = (analysis_data.get('app_number') or task.target_app_number)
        if (not results or (isinstance(results, dict) and not results.keys())) and model_slug and app_number:
            try:
                loaded = self._load_latest_analyzer_results(str(model_slug), int(app_number))
                if loaded:
                    # Common analyzer file shapes:
                    # A) { 'analysis': {..., 'results': {...}, 'summary': {...} } }
                    # B) { 'results': { 'analysis': {..., 'results': {...}}, 'summary': {...} } }
                    # C) { 'results': {...}, 'summary': {...} }

                    # Shape A: top-level 'analysis'
                    if 'analysis' in loaded and isinstance(loaded['analysis'], dict):
                        analysis_block = loaded['analysis']
                        results = analysis_block.get('results', results)
                        summary = (analysis_block.get('summary') or summary) or summary
                        if 'analysis_time' in analysis_block and 'analysis_time' not in analysis_data:
                            analysis_data['analysis_time'] = analysis_block.get('analysis_time')
                        if not analysis_data.get('tools_used') and isinstance(analysis_block.get('tools_used'), list):
                            analysis_data['tools_used'] = list(analysis_block.get('tools_used', []))

                    # Shape B: nested under loaded['results']
                    elif 'results' in loaded and isinstance(loaded['results'], dict):
                        outer_results = loaded['results']
                        # Try nested analysis/results
                        if 'analysis' in outer_results and isinstance(outer_results['analysis'], dict):
                            analysis_block = outer_results['analysis']
                            # Tool outputs live here
                            results = analysis_block.get('results', results)
                            # Prefer summary from outer or analysis block
                            if not summary:
                                summary = outer_results.get('summary') or analysis_block.get('summary') or {}
                            # Carry over helpful fields
                            if 'analysis_time' in analysis_block and 'analysis_time' not in analysis_data:
                                analysis_data['analysis_time'] = analysis_block.get('analysis_time')
                            if not analysis_data.get('tools_used') and isinstance(analysis_block.get('tools_used'), list):
                                analysis_data['tools_used'] = list(analysis_block.get('tools_used', []))
                            if 'configuration_applied' in analysis_block and 'configuration_applied' not in analysis_data:
                                analysis_data['configuration_applied'] = analysis_block.get('configuration_applied')
                        else:
                            # Shape C or partial: tool outputs may already be here
                            results = outer_results or results
                            if not summary:
                                summary = loaded.get('summary', {})
            except Exception:
                pass
        
        # If analyzer file signaled top-level error, reflect it in summary and status
        try:
            if isinstance(loaded, dict) and isinstance(loaded.get('results'), dict):
                top = loaded['results']
                if str(top.get('status', '')).lower() in ('error', 'failed'):
                    # Mark summary to include error and prefer failed status
                    summary = summary or {}
                    if 'error' in top and 'error' not in summary:
                        summary['error'] = top.get('error')
                    # Force derived_status to failed to avoid misleading completed
                    derived_status = 'failed'
        except Exception:
            pass

        # Extract severity breakdown
        severity = summary.get('severity_breakdown', {})
        
        # Extract detailed findings with ALL available information
        findings: List[Dict[str, Any]] = []
        total_issues = 0
        tool_metrics: Dict[str, Any] = {}
        
        if results:
            
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
                        'files_analyzed': mypy_data.get('files_analyzed', 0),
                        'summary': mypy_data.get('summary', {}),
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
                
                # Process Semgrep issues - extract ALL fields
                if 'semgrep' in python_results:
                    semgrep_data = python_results['semgrep']
                    tool_metrics['semgrep'] = {
                        'status': semgrep_data.get('status'),
                        'total_issues': semgrep_data.get('total_issues', 0),
                        'severity_breakdown': semgrep_data.get('severity_breakdown', {}),
                        'paths_scanned': semgrep_data.get('paths_scanned', {}),
                        'errors': semgrep_data.get('errors', []),
                        'config_used': semgrep_data.get('config_used', {})
                    }
                    
                    if 'results' in semgrep_data:
                        for issue in semgrep_data['results'][:50]:
                            finding = {
                                'tool': 'semgrep',
                                'severity': issue.get('extra', {}).get('severity', 'INFO').lower(),
                                'title': issue.get('extra', {}).get('message', 'Security pattern detected'),
                                'category': issue.get('check_id', 'security'),
                                'file_path': issue.get('path', ''),
                                'line_number': issue.get('start', {}).get('line'),
                                'column': issue.get('start', {}).get('col'),
                                'end_line': issue.get('end', {}).get('line'),
                                'end_column': issue.get('end', {}).get('col'),
                                'message': issue.get('extra', {}).get('message', ''),
                                'check_id': issue.get('check_id'),
                                'metadata': issue.get('extra', {}).get('metadata', {}),
                                'references': issue.get('extra', {}).get('references', []),
                                'raw_data': issue
                            }
                            findings.append(finding)
                
                # Process Safety vulnerabilities - extract ALL fields
                if 'safety' in python_results:
                    safety_data = python_results['safety']
                    tool_metrics['safety'] = {
                        'status': safety_data.get('status'),
                        'total_issues': safety_data.get('total_issues', 0),
                        'vulnerabilities': len(safety_data.get('vulnerabilities', [])),
                        'ignored_vulnerabilities': len(safety_data.get('ignored_vulnerabilities', [])),
                        'metadata': safety_data.get('metadata', {}),
                        'config_used': safety_data.get('config_used', {})
                    }
                    
                    if 'vulnerabilities' in safety_data:
                        for vuln in safety_data['vulnerabilities'][:50]:
                            finding = {
                                'tool': 'safety',
                                'severity': 'high',  # Safety vulnerabilities are generally high severity
                                'title': vuln.get('advisory', 'Security vulnerability'),
                                'category': 'dependency-vulnerability',
                                'package_name': vuln.get('package_name'),
                                'installed_version': vuln.get('installed_version'),
                                'affected_versions': vuln.get('affected_versions'),
                                'analyzed_version': vuln.get('analyzed_version'),
                                'message': vuln.get('advisory', ''),
                                'vulnerability_id': vuln.get('vulnerability_id'),
                                'cve': vuln.get('cve'),
                                'cwe': vuln.get('cwe'),
                                'more_info_url': vuln.get('more_info_url', ''),
                                'raw_data': vuln
                            }
                            findings.append(finding)
                
                # Process Vulture dead code findings - extract ALL fields
                if 'vulture' in python_results:
                    vulture_data = python_results['vulture']
                    tool_metrics['vulture'] = {
                        'status': vulture_data.get('status'),
                        'total_issues': vulture_data.get('total_issues', 0),
                        'config_used': vulture_data.get('config_used', {})
                    }
                    
                    if 'results' in vulture_data:
                        for issue in vulture_data['results'][:50]:
                            finding = {
                                'tool': 'vulture',
                                'severity': 'low',  # Dead code is typically low severity
                                'title': issue.get('message', 'Dead code detected'),
                                'category': 'dead-code',
                                'file_path': issue.get('filename', ''),
                                'line_number': issue.get('line'),
                                'message': issue.get('message', ''),
                                'confidence': issue.get('confidence', 80),
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
                
                # Process JSHint issues - extract ALL fields
                if 'jshint' in js_results:
                    jshint_data = js_results['jshint']
                    tool_metrics['jshint'] = {
                        'status': jshint_data.get('status'),
                        'total_issues': jshint_data.get('total_issues', 0),
                        'config_used': jshint_data.get('config_used', {})
                    }
                    
                    if 'results' in jshint_data:
                        for file_result in jshint_data['results']:
                            for issue in file_result.get('messages', [])[:50]:
                                finding = {
                                    'tool': 'jshint',
                                    'severity': 'warning',  # JSHint issues are typically warnings
                                    'title': issue.get('message', 'JavaScript code quality issue'),
                                    'category': issue.get('code', 'javascript'),
                                    'file_path': file_result.get('filePath', ''),
                                    'line_number': issue.get('line'),
                                    'column': issue.get('column'),
                                    'message': issue.get('message', ''),
                                    'code': issue.get('code'),
                                    'evidence': issue.get('evidence', ''),
                                    'raw_data': issue
                                }
                                findings.append(finding)
                
                # Process Snyk issues - extract ALL fields  
                if 'snyk' in js_results:
                    snyk_data = js_results['snyk']
                    tool_metrics['snyk'] = {
                        'status': snyk_data.get('status'),
                        'total_issues': snyk_data.get('total_issues', 0),
                        'config_used': snyk_data.get('config_used', {})
                    }
                    
                    if 'results' in snyk_data:
                        for issue in snyk_data['results'][:50]:
                            finding = {
                                'tool': 'snyk',
                                'severity': issue.get('severity', 'medium').lower(),
                                'title': issue.get('title', 'Security vulnerability'),
                                'category': 'security-vulnerability',
                                'file_path': issue.get('packageName', ''),
                                'message': issue.get('title', ''),
                                'package_name': issue.get('packageName'),
                                'version': issue.get('version'),
                                'cve': issue.get('identifiers', {}).get('CVE', []),
                                'cwe': issue.get('identifiers', {}).get('CWE', []),
                                'references': issue.get('references', []),
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

        # If unified raw tool JSON blocks exist, attempt standardized parsing augmentation.
        try:
            from .analysis_result_parser import (
                parse_bandit_results,
                parse_pylint_messages,
                merge_findings,
            )
            # Only enrich if we have top-level tool raw blocks and haven't already parsed them.
            # Bandit: if 'bandit' block exists but we have zero bandit findings identified above.
            if results and 'security' in results:
                security_block = results['security']
                bandit_block = security_block.get('bandit') if isinstance(security_block, dict) else None
                if isinstance(bandit_block, dict):
                    existing_bandit = any(f.get('tool') == 'bandit' for f in findings)
                    if not existing_bandit:
                        findings = merge_findings(findings, parse_bandit_results(bandit_block))

            if results and 'python' in results:
                python_block = results['python']
                pylint_block = python_block.get('pylint') if isinstance(python_block, dict) else None
                if isinstance(pylint_block, dict) and 'issues' in pylint_block:
                    existing_pylint = any(f.get('tool') == 'pylint' for f in findings)
                    if not existing_pylint:
                        findings = merge_findings(findings, parse_pylint_messages(pylint_block.get('issues', [])))
        except Exception:  # pragma: no cover - enrichment is best effort
            pass
        
        # Calculate total issues from summary or count findings
        total_issues = summary.get('total_issues_found', len(findings))
        
        # Enhanced payload with comprehensive metadata
        # Derive a friendlier status hint from analyzer summary if DB task status is misleading
        derived_status = None
        try:
            deriv = summary.get('analysis_status') if isinstance(summary, dict) else None
            if deriv in ('completed', 'success'):
                derived_status = deriv
            elif findings:
                derived_status = 'completed'
        except Exception:
            pass

        # Derive tools_used if still empty by inspecting executed tool blocks
        tools_skipped: list[str] = []
        try:
            if (not analysis_data.get('tools_used')) and isinstance(results, dict):
                used = []
                
                # Check for orchestrator-style results first
                if 'tools_requested' in results and 'tool_results' in results:
                    # New orchestrator format
                    tools_requested = results.get('tools_requested', [])
                    tool_results = results.get('tool_results', {})
                    
                    for tool_name in tools_requested:
                        tool_result = tool_results.get(tool_name, {})
                        status = tool_result.get('status', '')
                        if status and not status.startswith('❌') and 'not available' not in status.lower():
                            used.append(tool_name)
                        else:
                            tools_skipped.append(tool_name)
                else:
                    # Legacy format inspection
                    for lang_key, lang_block in results.items():
                        if not isinstance(lang_block, dict):
                            continue
                        for tool_name, tool_block in lang_block.items():
                            if not isinstance(tool_block, dict):
                                continue
                            # Consider executed tools or those with a non-skipped status
                            executed = tool_block.get('executed') is True
                            status_val = str(tool_block.get('status', '')).lower()
                            if executed or (status_val and status_val not in ('skipped', 'not_run', 'noop')):
                                used.append(tool_name)
                            if (not executed) or status_val in ('skipped', 'not_run', 'noop', 'no_files'):
                                tools_skipped.append(tool_name)
                
                if used:
                    # Deduplicate and store
                    analysis_data['tools_used'] = sorted(set(used))
        except Exception:
            pass

        # Decide effective status: prefer analyzer-derived
        effective_status = derived_status or getattr(task.status, 'value', task.status)
        db_status = getattr(task.status, 'value', task.status)

        payload = {
            'task_id': task.task_id,
            'status': effective_status,
            'db_status': db_status,
            'analysis_type': getattr(task.analysis_type, 'value', task.analysis_type),
            'model_slug': analysis_data.get('model_slug', model_slug),
            'app_number': analysis_data.get('app_number', app_number),
            'analysis_time': analysis_data.get('analysis_time'),
            'tools_used': analysis_data.get('tools_used') or (summary.get('tools_used') if isinstance(summary, dict) else []) or [],
            'tools_skipped': sorted(set(tools_skipped)) if tools_skipped else [],
            'configuration_applied': analysis_data.get('configuration_applied', False),
            'summary': summary,
            'severity_breakdown': severity,
            'tool_metrics': tool_metrics,
            'structure_analysis': results.get('structure', {}) if results else {},
            'findings_preview': findings,
            'findings_total': total_issues,
            'findings_by_tool': self._group_findings_by_tool(findings),
            'findings_by_severity': self._group_findings_by_severity(findings),
            'metadata': {
                'extraction_version': '2.0',
                'comprehensive_parsing': True,
                'raw_data_included': True,
                'analysis_duration': analysis_data.get('analysis_duration') or (results.get('analysis_duration') if results else None)
            },
            'derived_status': derived_status
        }
        return payload

    def _load_latest_analyzer_results(self, model_slug: str, app_number: int) -> Optional[Dict[str, Any]]:
        """Load the most recent analyzer result JSON for a given model/app.

        Searches results/<model_slug>/appN/*-analyzer/*.json and returns parsed JSON.
        """
        try:
            base = Path.cwd() / 'results' / model_slug / f'app{app_number}'
            if not base.exists():
                return None
            # Prefer static-analyzer first, but allow any analyzer folder
            candidates = []
            for sub in ('static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer'):
                p = base / sub
                if p.exists():
                    candidates.extend(sorted(p.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True))
            # Fallback to any JSON under app folder
            if not candidates:
                candidates = sorted(base.glob('**/*.json'), key=lambda x: x.stat().st_mtime, reverse=True)
            if not candidates:
                return None
            latest = candidates[0]
            with latest.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

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
