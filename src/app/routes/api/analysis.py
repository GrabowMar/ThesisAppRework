"""
Analysis API module for managing code analysis operations.
Handles security analysis, performance testing, and analysis summaries.
All tool operations are now delegated to the container-based tool registry.
"""

from flask import Blueprint, jsonify, request, current_app
from app.routes.api.common import api_error
from app.engines.container_tool_registry import get_container_tool_registry
from app.paths import RESULTS_DIR, PROJECT_ROOT
import logging
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Create analysis blueprint
analysis_bp = Blueprint('api_analysis', __name__)


def _normalize_task_folder_name(result_id: str) -> str:
    """Ensure task folders always start with 'task_' prefix."""
    if not result_id:
        return 'task_unknown'
    return result_id if result_id.startswith('task_') else f'task_{result_id}'


def _extract_model_app_from_result(result_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort extraction of model slug and app number from result payload."""
    model_slug = None
    app_number = None

    metadata = result_data.get('metadata') or {}
    model_slug = metadata.get('model_slug') or metadata.get('model')
    app_number = metadata.get('app_number') or metadata.get('app')

    if not model_slug or not app_number:
        summary = result_data.get('summary') or {}
        model_slug = model_slug or summary.get('model_slug')
        app_number = app_number or summary.get('app_number')

    if not model_slug or not app_number:
        static_analysis = (result_data.get('results') or {}).get('static', {}).get('analysis', {})
        model_slug = model_slug or static_analysis.get('model_slug') or static_analysis.get('target_model')
        app_number = app_number or static_analysis.get('app_number') or static_analysis.get('target_app_number')

    return model_slug, app_number


def _resolve_task_directory(result_data: Dict[str, Any], result_id: str) -> Optional[Path]:
    """Resolve the filesystem path for a task's result directory."""
    model_slug, app_number = _extract_model_app_from_result(result_data)
    task_folder = _normalize_task_folder_name(str(result_id))

    if model_slug and app_number:
        safe_slug = str(model_slug).replace('/', '_')
        return RESULTS_DIR / safe_slug / f'app{app_number}' / task_folder

    results_path = result_data.get('results_path')
    if isinstance(results_path, str) and results_path:
        candidate = Path(results_path)
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        return candidate

    return None


def _extract_issues_from_sarif(sarif_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize SARIF run data into the issue format expected by the UI."""
    extracted_issues = []
    if not isinstance(sarif_data, dict):
        return extracted_issues

    level_map = {
        'error': 'HIGH',
        'warning': 'MEDIUM',
        'note': 'LOW',
        'none': 'INFO'
    }

    for run in sarif_data.get('runs', []):
        rules_index = {}
        driver = (run.get('tool') or {}).get('driver') or {}
        for rule in driver.get('rules', []) or []:
            if isinstance(rule, dict) and rule.get('id'):
                rules_index[rule['id']] = rule

        for result_item in run.get('results', []) or []:
            if not isinstance(result_item, dict):
                continue

            rule_id = result_item.get('ruleId') or result_item.get('rule', {}).get('id')
            message = (result_item.get('message') or {}).get('text') or ''
            level = (result_item.get('level') or 'warning').lower()
            severity = level_map.get(level, 'MEDIUM')

            issue: Dict[str, Any] = {
                'rule': rule_id,
                'rule_id': rule_id,
                'level': level,
                'severity': severity,
                'issue_severity': (result_item.get('properties', {}).get('issue_severity') or severity).upper(),
                'message': message,
                'tool': driver.get('name') or 'SARIF tool'
            }

            locations = result_item.get('locations') or []
            if locations:
                physical_loc = (locations[0] or {}).get('physicalLocation') or {}
                artifact_loc = physical_loc.get('artifactLocation') or {}
                region = physical_loc.get('region') or {}

                uri = artifact_loc.get('uri') or ''
                issue['file'] = uri.replace('file://', '')
                issue['line'] = region.get('startLine')
                issue['column'] = region.get('startColumn')

            properties = result_item.get('properties') or {}
            if 'issue_confidence' in properties:
                issue['confidence'] = properties['issue_confidence']
            if 'issue_severity' in properties:
                issue['issue_severity'] = properties['issue_severity'].upper()
            if 'cwe' in properties:
                issue['cwe'] = properties['cwe']

            if rule_id and rule_id in rules_index:
                rule_meta = rules_index[rule_id]
                if rule_meta.get('helpUri'):
                    issue['help_url'] = rule_meta['helpUri']
                if rule_meta.get('name'):
                    issue['rule_name'] = rule_meta['name']

            extracted_issues.append(issue)

    return extracted_issues


def _normalize_issue_severity(value: Optional[str], default: str = 'MEDIUM') -> str:
    """Normalize severity/risk labels coming from various services."""
    if not value:
        return default

    normalized = str(value).strip().upper()
    mapping = {
        'CRIT': 'CRITICAL',
        'CRITICAL': 'CRITICAL',
        'HIGH': 'HIGH',
        'WARN': 'MEDIUM',
        'WARNING': 'MEDIUM',
        'MEDIUM': 'MEDIUM',
        'LOW': 'LOW',
        'INFO': 'INFO',
        'INFORMATIONAL': 'INFO',
        'NOTE': 'LOW',
        'MINOR': 'LOW',
        'ERROR': 'HIGH'
    }

    for key, mapped in mapping.items():
        if normalized == key or key in normalized:
            return mapped

    return default


def _extract_zap_security_issues(zap_results: Any) -> List[Dict[str, Any]]:
    """Flatten ZAP alert payloads into the standard issue shape."""
    issues: List[Dict[str, Any]] = []
    if not isinstance(zap_results, list):
        return issues

    for scan in zap_results:
        if not isinstance(scan, dict):
            continue

        base_url = scan.get('url')
        scan_type = scan.get('scan_type') or scan.get('type')
        alerts_by_risk = scan.get('alerts_by_risk') or {}

        for risk_bucket, alerts in alerts_by_risk.items():
            if not isinstance(alerts, list):
                continue

            for alert in alerts:
                if not isinstance(alert, dict):
                    continue

                severity = _normalize_issue_severity(alert.get('risk') or risk_bucket)
                issue = {
                    'issue_severity': severity,
                    'severity': severity,
                    'risk': alert.get('risk') or risk_bucket,
                    'name': alert.get('name') or alert.get('alert') or 'ZAP Alert',
                    'message': alert.get('description') or alert.get('name'),
                    'description': alert.get('description'),
                    'solution': alert.get('solution'),
                    'reference': alert.get('reference'),
                    'url': alert.get('url') or base_url,
                    'param': alert.get('param') or alert.get('parameter'),
                    'evidence': alert.get('evidence'),
                    'confidence': alert.get('confidence'),
                    'plugin_id': alert.get('pluginId'),
                    'alert_id': alert.get('id'),
                    'alert_ref': alert.get('alertRef'),
                    'tags': alert.get('tags'),
                    'tool': 'zap',
                    'category': 'zap_security_scan',
                    'scan_type': scan_type,
                    'target_url': base_url,
                }

                cwe_id = alert.get('cweid') or alert.get('cwe')
                if cwe_id and str(cwe_id) not in ('-1', '0'):
                    issue['cwe'] = f"CWE-{cwe_id}" if not str(cwe_id).startswith('CWE-') else str(cwe_id)

                other_notes = alert.get('other')
                if other_notes:
                    issue['notes'] = other_notes

                issues.append(issue)

    return issues


def _extract_vulnerability_scan_issues(vulnerability_results: Any) -> List[Dict[str, Any]]:
    """Derive issues from vulnerability scan summaries emitted by the dynamic analyzer."""
    issues: List[Dict[str, Any]] = []
    if not isinstance(vulnerability_results, list):
        return issues

    for scan in vulnerability_results:
        if not isinstance(scan, dict):
            continue

        target_url = scan.get('url')
        for vuln in scan.get('vulnerabilities') or []:
            if not isinstance(vuln, dict):
                continue

            severity = _normalize_issue_severity(vuln.get('severity') or 'LOW')
            issue = {
                'issue_severity': severity,
                'severity': severity,
                'vulnerability_type': vuln.get('type'),
                'message': vuln.get('description') or vuln.get('type') or 'Potential vulnerability',
                'description': vuln.get('description'),
                'url': target_url,
                'paths': vuln.get('paths'),
                'tool': 'vulnerability_scan',
                'category': 'vulnerability_scan',
            }
            issues.append(issue)

    return issues


def _extract_connectivity_issues(connectivity_results: Any) -> List[Dict[str, Any]]:
    """Create issue entries for missing security headers detected during connectivity checks."""
    issues: List[Dict[str, Any]] = []
    if not isinstance(connectivity_results, list):
        return issues

    for entry in connectivity_results:
        analysis = entry.get('analysis') if isinstance(entry, dict) else None
        if not isinstance(analysis, dict):
            continue

        headers = analysis.get('security_headers') or {}
        if not isinstance(headers, dict):
            continue

        missing_headers = [name for name, present in headers.items() if not present]
        if not missing_headers:
            continue

        severity = 'LOW'
        issues.append({
            'issue_severity': severity,
            'severity': severity,
            'message': 'Missing security headers',
            'description': f"The following headers are not configured: {', '.join(sorted(missing_headers))}",
            'url': analysis.get('url'),
            'status_code': analysis.get('status_code'),
            'security_score': analysis.get('security_score'),
            'tool': 'curl',
            'category': 'connectivity',
        })

    return issues


def _extract_port_scan_issues(port_scan_result: Any) -> List[Dict[str, Any]]:
    """Represent open ports discovered by nmap as informational issues."""
    issues: List[Dict[str, Any]] = []
    if not isinstance(port_scan_result, dict):
        return issues

    host = port_scan_result.get('host')
    for port in port_scan_result.get('open_ports') or []:
        issue = {
            'issue_severity': 'INFO',
            'severity': 'INFO',
            'message': f'Port {port} is open',
            'description': 'The port responded during scanning and should be verified if exposure is intentional.',
            'host': host,
            'tool': 'nmap',
            'category': 'port_scan',
            'port': port,
        }
        issues.append(issue)

    return issues


def _derive_tool_issues_from_service(service_type: Optional[str], tool_name: str, analysis_block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Attempt to build issue arrays for tools that don't emit SARIF/issue payloads."""
    if not service_type or not isinstance(analysis_block, dict):
        return []

    results = analysis_block.get('results') or {}
    tool_key = tool_name.lower()

    if service_type == 'dynamic':
        if tool_key == 'zap':
            return _extract_zap_security_issues(results.get('zap_security_scan'))
        if tool_key in ('curl', 'connectivity'):
            return _extract_connectivity_issues(results.get('connectivity'))
        if tool_key in ('nmap', 'portscan', 'port-scan'):
            return _extract_port_scan_issues(results.get('port_scan'))
        if tool_key in ('vulnerability_scan', 'vulnscan', 'dirsearch'):
            return _extract_vulnerability_scan_issues(results.get('vulnerability_scan'))

    # Future services (performance, ai) can be added here as needed
    return []


def _resolve_tools_from_names(tool_names, all_tools):
    """Helper to resolve tool names to IDs and group by service.
    
    Returns:
        tuple: (tool_ids, tool_names, tools_by_service) or (None, None, None) if no valid tools
    """
    tool_ids = []
    valid_tool_names = []
    tools_by_service = {}
    
    # Build lookup: name (case-insensitive) -> tool object
    tools_lookup = {t.name.lower(): t for t in all_tools.values()}
    name_to_idx = {t.name.lower(): idx + 1 for idx, t in enumerate(all_tools.values())}
    
    for tool_name in tool_names:
        tool_name_lower = tool_name.lower()
        tool_obj = tools_lookup.get(tool_name_lower)
        
        if tool_obj and tool_obj.available:
            tool_id = name_to_idx.get(tool_name_lower)
            if tool_id:
                tool_ids.append(tool_id)
                valid_tool_names.append(tool_obj.name)
                service = tool_obj.container.value
                tools_by_service.setdefault(service, []).append(tool_id)
        else:
            logger.warning(f"Tool '{tool_name}' not found or unavailable")
    
    if not tools_by_service:
        return None, None, None
    
    return tool_ids, valid_tool_names, tools_by_service

@analysis_bp.route('/tool-registry/custom-analysis', methods=['POST'])
def create_custom_analysis():
    """Create a custom analysis request using container tools."""
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['model_slug', 'app_number']
        for field in required_fields:
            if field not in data:
                return api_error(f"Missing required field: {field}", 400)
        
        # Create custom analysis configuration
        result = {
            'analysis_id': f"custom_{data['app_number']}_{data['model_slug']}",
            'app_number': data['app_number'],
            'model_slug': data['model_slug'],
            'tools': data.get('tools', []),
            'containers': data.get('containers', ['static-analyzer']),
            'created_at': __import__('time').time()
        }
        
        return jsonify({
            'success': True,
            'data': result,
            'message': 'Custom analysis created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating custom analysis: {str(e)}")
        return api_error(f"Failed to create custom analysis: {str(e)}", 500)

@analysis_bp.route('/tool-registry/execution-plan/<int:analysis_id>')
def get_execution_plan(analysis_id):
    """Get execution plan for a custom analysis."""
    try:
        # Basic execution plan based on container tools
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        plan = {
            'analysis_id': analysis_id,
            'steps': [],
            'estimated_duration': 0
        }
        
        # Create steps for each container
        for container in ['static-analyzer', 'dynamic-analyzer', 'performance-tester']:
            tools = [tool for tool in all_tools.values() if tool.container.value == container]
            if tools:
                plan['steps'].append({
                    'step': len(plan['steps']) + 1,
                    'container': container,
                    'tools': [tool.name for tool in tools if tool.available],
                    'estimated_duration': 60  # seconds
                })
                plan['estimated_duration'] += 60
        
        return jsonify({
            'success': True,
            'data': plan,
            'message': 'Execution plan retrieved successfully'
        })
    except Exception as e:
        logger.error(f"Error fetching execution plan: {str(e)}")
        return api_error(f"Failed to fetch execution plan: {str(e)}", 500)


@analysis_bp.route('/run', methods=['POST'])
def run_analysis():
    """
    Run analysis on an application.
    
    Endpoint: POST /api/analysis/run
    
    Request body:
    {
        "model_slug": "openai_codex-mini",
        "app_number": 1,
        "analysis_type": "security",  # security, performance, dynamic, ai, unified
        "tools": ["bandit", "safety"],  # Optional: specific tools to run
        "priority": "normal"  # Optional: normal, high, low
    }
    
    Returns:
    {
        "success": true,
        "task_id": "abc123...",
        "message": "Analysis task created",
        "data": {
            "task_id": "abc123...",
            "model_slug": "openai_codex-mini",
            "app_number": 1,
            "analysis_type": "security",
            "status": "pending",
            "created_at": "2025-10-27T10:00:00"
        }
    }
    """
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        model_slug = data.get('model_slug', '').strip()
        app_number = data.get('app_number')
        analysis_type = data.get('analysis_type', 'security').strip()
        tools = data.get('tools', [])
        priority = data.get('priority', 'normal').strip()
        
        if not model_slug:
            return api_error("Missing required field: model_slug", 400)
        if not app_number:
            return api_error("Missing required field: app_number", 400)
        
        try:
            app_number = int(app_number)
        except (ValueError, TypeError):
            return api_error("app_number must be an integer", 400)
        
        # Verify application exists
        from app.models import GeneratedApplication
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if not app:
            return api_error(f"Application not found: {model_slug}/app{app_number}", 404)
        
        # Import task service
        from app.services.task_service import AnalysisTaskService
        from app.engines.container_tool_registry import get_container_tool_registry
        
        # Get tool registry
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        # Determine which tools to run
        if not tools:
            # No tools specified - use analysis_type to determine tools
            if analysis_type in ['unified', 'comprehensive']:
                tools = [t.name for t in all_tools.values() if t.available]
            else:
                # Map analysis_type to default tools
                default_tools_map = {
                    'security': ['bandit', 'safety', 'eslint'],
                    'performance': ['locust'],
                    'dynamic': ['zap'],
                    'ai': ['ai-analyzer']
                }
                tools = default_tools_map.get(analysis_type, ['bandit', 'safety'])
        
        # Resolve tool names to IDs and group by service
        tool_ids, tool_names, tools_by_service = _resolve_tools_from_names(tools, all_tools)
        
        if not tools_by_service:
            return api_error("No valid tools found", 400)
        
        # Build custom options for task
        custom_options = {
            'selected_tools': tool_ids,
            'selected_tool_names': tool_names,
            'tools_by_service': tools_by_service,
            'source': 'api'
        }
        
        # Create task - use multi-service if multiple containers involved
        if len(tools_by_service) > 1:
            custom_options['unified_analysis'] = True
            task = AnalysisTaskService.create_main_task_with_subtasks(
                model_slug=model_slug,
                app_number=app_number,
                tools=tool_names,
                priority=priority,
                custom_options=custom_options,
                task_name=f"api:{model_slug}:{app_number}"
            )
        else:
            custom_options['unified_analysis'] = False
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                tools=tool_names,
                priority=priority,
                custom_options=custom_options
            )
        
        # Return task information
        return jsonify({
            'success': True,
            'task_id': task.task_id,
            'message': 'Analysis task created successfully',
            'data': {
                'task_id': task.task_id,
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_type': task.analysis_type,
                'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'tools_count': len(tools) if tools else 'all',
                'priority': priority
            }
        }), 201
        
    except Exception as e:
        logger.exception(f"Error running analysis: {str(e)}")
        return api_error(f"Failed to run analysis: {str(e)}", 500)


@analysis_bp.route('/results/<result_id>/tools/<tool_name>', methods=['GET'])
def get_tool_details(result_id: str, tool_name: str):
    """
    Get detailed information for a specific tool from an analysis result.
    
    Endpoint: GET /api/analysis/results/<result_id>/tools/<tool_name>?service=<service_type>
    
    Query parameters:
        - service: Service type (static, dynamic, performance, ai) - optional
        - page: Page number for pagination (default: 1)
        - per_page: Items per page (default: 25)
        - severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
    
    Returns:
    {
        "success": true,
        "data": {
            "tool_name": "bandit",
            "language": "python",
            "status": "success",
            "executed": true,
            "execution_time": 2.3,
            "total_issues": 5,
            "issues": [...],
            "sarif_file": "sarif/static_python_bandit.sarif.json",
            ...
        }
    }
    """
    try:
        from app.services.unified_result_service import UnifiedResultService
        
        # Get query parameters
        service_type = request.args.get('service', '').lower()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))
        severity_filter = request.args.get('severity', '').upper()
        
        # Load result data
        result_service = UnifiedResultService()
        result = result_service.load_analysis_results(result_id)
        
        if not result:
            return api_error(f"Result not found: {result_id}", 404)
        
        result_data = result.raw_data
        
        # Extract tool data from result
        tool_data = None
        detected_service = None
        matched_analysis_block: Optional[Dict[str, Any]] = None
        
        # Try to find tool in services
        services = result_data.get('results', {}).get('services', {})
        
        # Search through all services if not specified
        search_services = [service_type] if service_type else ['static', 'dynamic', 'performance', 'ai']
        
        for svc in search_services:
            if svc not in services:
                continue
            
            svc_data = services[svc]
            analysis = svc_data.get('analysis', {})
            
            # Check different result structures
            if svc == 'static':
                # Static has language-based grouping
                results = analysis.get('results', {})
                for lang, lang_tools in results.items():
                    if isinstance(lang_tools, dict) and tool_name.lower() in [k.lower() for k in lang_tools.keys()]:
                        # Find exact match (case-insensitive)
                        for k, v in lang_tools.items():
                            if k.lower() == tool_name.lower():
                                tool_data = v.copy()
                                tool_data['language'] = lang
                                detected_service = svc
                                matched_analysis_block = analysis
                                break
                    if tool_data:
                        break
            else:
                # Dynamic, performance, AI have flat tool_results
                tool_results = analysis.get('tool_results', analysis.get('results', {}))
                if isinstance(tool_results, dict):
                    for k, v in tool_results.items():
                        if k.lower() == tool_name.lower():
                            tool_data = v.copy()
                            detected_service = svc
                            matched_analysis_block = analysis
                            break
            
            if tool_data:
                break
        
        if not tool_data:
            return api_error(f"Tool '{tool_name}' not found in result", 404)
        
        # Add tool name to response
        tool_data['tool_name'] = tool_name
        tool_data['service_type'] = detected_service

        if (not tool_data.get('issues')) and matched_analysis_block:
            derived_issues = _derive_tool_issues_from_service(
                detected_service,
                tool_name,
                matched_analysis_block
            )
            if derived_issues:
                tool_data['issues'] = derived_issues
                tool_data['total_issues'] = len(derived_issues)
        
        # If tool has SARIF data but empty issues array, derive issues from SARIF payload
        if (not tool_data.get('issues') or len(tool_data.get('issues', [])) == 0) and tool_data.get('sarif'):
            sarif_ref = tool_data.get('sarif')
            sarif_data = None
            sarif_file = None

            if isinstance(sarif_ref, dict):
                if sarif_ref.get('runs'):
                    sarif_data = sarif_ref
                else:
                    sarif_file = sarif_ref.get('sarif_file') or sarif_ref.get('path') or sarif_ref.get('file')
            elif isinstance(sarif_ref, str):
                sarif_file = sarif_ref

            if not sarif_data and sarif_file:
                try:
                    task_dir = _resolve_task_directory(result_data, result_id)
                    if task_dir:
                        task_root = task_dir.resolve()
                        sarif_path_obj = Path(sarif_file)
                        sarif_full_path = sarif_path_obj if sarif_path_obj.is_absolute() else (task_root / sarif_path_obj).resolve()

                        try:
                            sarif_full_path.relative_to(task_root)
                        except ValueError:
                            raise ValueError('SARIF path escapes task directory')

                        if sarif_full_path.exists():
                            with open(sarif_full_path, 'r', encoding='utf-8') as f:
                                sarif_data = json.load(f)
                        else:
                            logger.warning(f"SARIF file missing for {tool_name}: {sarif_full_path}")
                except Exception as e:
                    logger.warning(f"Failed to load SARIF file for {tool_name}: {e}")

            if sarif_data:
                extracted_issues = _extract_issues_from_sarif(sarif_data)
                tool_data['issues'] = extracted_issues
                tool_data['total_issues'] = len(extracted_issues)
                logger.info(f"Loaded {len(extracted_issues)} issues from SARIF data for {tool_name}")
        
        # Filter issues by severity if requested
        if severity_filter and 'issues' in tool_data and tool_data['issues']:
            original_issues = tool_data['issues']
            filtered_issues = [
                issue for issue in original_issues
                if (issue.get('issue_severity') or issue.get('severity', '')).upper() == severity_filter
            ]
            tool_data['issues'] = filtered_issues
            tool_data['filtered_count'] = len(filtered_issues)
            tool_data['original_count'] = len(original_issues)
        
        # Apply pagination to issues
        if 'issues' in tool_data and tool_data['issues']:
            total_issues = len(tool_data['issues'])
            start = (page - 1) * per_page
            end = start + per_page
            
            tool_data['pagination'] = {
                'page': page,
                'per_page': per_page,
                'total': total_issues,
                'pages': (total_issues + per_page - 1) // per_page,
                'has_prev': page > 1,
                'has_next': end < total_issues
            }
            
            # Slice issues for current page
            tool_data['issues'] = tool_data['issues'][start:end]
        
        return jsonify({
            'success': True,
            'data': tool_data
        })
        
    except Exception as e:
        logger.exception(f"Error fetching tool details: {str(e)}")
        return api_error(f"Failed to fetch tool details: {str(e)}", 500)


@analysis_bp.route('/results/<result_id>/sarif/<path:sarif_path>', methods=['GET'])
def get_sarif_file(result_id: str, sarif_path: str):
    """
    Get SARIF file content from an analysis result.
    
    Endpoint: GET /api/analysis/results/<result_id>/sarif/<sarif_path>
    
    Returns: SARIF JSON file or 404 if not found
    """
    try:
        import os
        from pathlib import Path
        
        # Construct full path to SARIF file
        # SARIF files are stored in results/{model}/app{N}/task_{id}/sarif/
        # We need to resolve the actual filesystem path
        
        # Extract model slug and app number from result_id or metadata
        from app.services.unified_result_service import UnifiedResultService
        result_service = UnifiedResultService()
        result = result_service.load_analysis_results(result_id)
        
        if not result:
            return api_error(f"Result not found: {result_id}", 404)
        
        result_data = result.raw_data
        task_dir = _resolve_task_directory(result_data, result_id)
        if not task_dir:
            return api_error("Invalid result metadata", 400)

        task_root = task_dir.resolve()
        sarif_full_path = (task_root / sarif_path).resolve()

        try:
            sarif_full_path.relative_to(task_root)
        except ValueError:
            return api_error("Invalid SARIF path", 400)

        if not sarif_full_path.exists():
            return api_error(f"SARIF file not found: {sarif_path}", 404)
        
        # Read and return SARIF file
        with open(sarif_full_path, 'r', encoding='utf-8') as f:
            sarif_data = json.load(f)
        
        return jsonify(sarif_data)
        
    except Exception as e:
        logger.exception(f"Error fetching SARIF file: {str(e)}")
        return api_error(f"Failed to fetch SARIF file: {str(e)}", 500)

