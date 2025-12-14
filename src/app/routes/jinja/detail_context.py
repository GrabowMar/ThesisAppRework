from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import abort, current_app
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    ExternalModelInfoCache,
    GeneratedApplication,
    ModelCapability,
    OpenRouterAnalysis,
    PerformanceTest,
    PortConfiguration,
    SecurityAnalysis,
    ZAPAnalysis,
)
from app.models.analysis_models import AnalysisTask
from app.routes.shared_utils import _project_root
from app.utils.helpers import deep_merge_dicts, get_app_directory
from app.utils.port_resolution import resolve_ports


class _SyntheticModel:
    def __init__(self, slug: str) -> None:
        self.canonical_slug = slug
        self.model_name = slug
        self.model_id = slug
        self.provider = (slug.split('_')[0] or 'local') if '_' in slug else (slug.split('-')[0] or 'local') if '-' in slug else 'local'
        self.display_name = slug
        self.context_window = None
        self.max_output_tokens = None
        self.cost_efficiency = None
        self.is_free = False
        self.installed = False
        self.input_price_per_token = None
        self.output_price_per_token = None
        self.supports_function_calling = False
        self.supports_vision = False
        self.supports_streaming = False
        self.supports_json_mode = False
        self.created_at = None
        self.updated_at = None

    def get_metadata(self) -> Dict[str, Any]:
        return {}

    def get_capabilities(self) -> Dict[str, Any]:
        return {}


def _slug_variants(slug: str) -> List[str]:
    if not slug:
        return []
    variants = {slug}
    variants.add(slug.replace('-', '_'))
    variants.add(slug.replace('_', '-'))
    variants.add(slug.replace(' ', '_'))
    variants.add(slug.replace(' ', '-'))
    variants = {v for v in variants if v}
    cleaned = set()
    for v in variants:
        cleaned.add(v.replace('__', '_').replace('--', '-'))
    return sorted(cleaned)


def _enum_to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return getattr(value, 'value', value)


def _format_datetime(dt: Any) -> str:
    if not dt:
        return '—'
    try:
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(dt)


def _resolve_model(model_slug: str, allow_synthetic: bool) -> ModelCapability | _SyntheticModel:
    model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
    if model:
        return model
    variants = _slug_variants(model_slug)
    if variants:
        model = ModelCapability.query.filter(ModelCapability.canonical_slug.in_(variants)).first()
        if model:
            return model
        model = ModelCapability.query.filter(ModelCapability.model_name.in_(variants)).first()
        if model:
            return model
    if allow_synthetic:
        return _SyntheticModel(model_slug)
    abort(404)


def _resolve_application(model: Any, model_slug: str, app_number: int) -> Optional[GeneratedApplication]:
    slugs = [model_slug]
    candidate = getattr(model, 'canonical_slug', None)
    if candidate:
        slugs.append(candidate)
    candidate = getattr(model, 'model_name', None)
    if candidate:
        slugs.append(candidate)
    seen = set()
    for slug in slugs:
        if not slug or slug in seen:
            continue
        seen.add(slug)
        app = GeneratedApplication.query.filter_by(model_slug=slug, app_number=app_number).first()
        if app:
            return app
    return None


def _model_to_dict(model: Any) -> Dict[str, Any]:
    return {
        'canonical_slug': getattr(model, 'canonical_slug', None),
        'model_name': getattr(model, 'model_name', None),
        'model_id': getattr(model, 'model_id', None),
        'provider': getattr(model, 'provider', None),
        'display_name': getattr(model, 'display_name', None) or getattr(model, 'model_name', None) or getattr(model, 'canonical_slug', None),
        'context_window': getattr(model, 'context_window', None),
        'max_output_tokens': getattr(model, 'max_output_tokens', None),
        'cost_efficiency': getattr(model, 'cost_efficiency', None),
        'is_free': getattr(model, 'is_free', False),
        'installed': getattr(model, 'installed', False),
        'input_price_per_token': getattr(model, 'input_price_per_token', None),
        'output_price_per_token': getattr(model, 'output_price_per_token', None),
        'supports_function_calling': getattr(model, 'supports_function_calling', False),
        'supports_vision': getattr(model, 'supports_vision', False),
        'supports_streaming': getattr(model, 'supports_streaming', False),
        'supports_json_mode': getattr(model, 'supports_json_mode', False),
        'created_at': getattr(model, 'created_at', None),
        'updated_at': getattr(model, 'updated_at', None),
        'apps_count': getattr(model, 'apps_count', None),
        'id': getattr(model, 'id', None),
    }


def _safe_json_loads(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            return json.loads(candidate)
        except Exception:
            current_app.logger.debug("Failed to parse JSON payload (len=%s)", len(candidate))
            return None
    return None


def _format_metric_value(value: Any) -> str:
    if value is None:
        return '—'
    if isinstance(value, float):
        formatted = f"{value:,.2f}"
        return formatted.rstrip('0').rstrip('.')
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _analysis_type_metadata(key: str) -> Tuple[str, str]:
    mapping = {
        'security': ('security', 'Security Analysis'),
        'performance': ('performance', 'Performance Test'),
        'zap': ('zap', 'ZAP Scan'),
        'openrouter': ('openrouter', 'AI Review'),
    }
    return mapping.get(key, (key, key.replace('_', ' ').title()))


def _analysis_sort_key(entry: Dict[str, Any]) -> float:
    def _timestamp(candidate: Any) -> Optional[float]:
        if candidate is None:
            return None
        if hasattr(candidate, 'timestamp'):
            try:
                return float(candidate.timestamp())
            except Exception:
                return None
        if isinstance(candidate, (int, float)):
            return float(candidate)
        if isinstance(candidate, str):
            try:
                dt = datetime.fromisoformat(candidate)
                return float(dt.timestamp())
            except Exception:
                return None
        return None

    for field in ('created_at', 'started_at', 'completed_at'):
        ts = _timestamp(entry.get(field))
        if ts is not None:
            return ts
    fallback = entry.get('id')
    if isinstance(fallback, (int, float)):
        return float(fallback)
    return 0.0


def _normalize_analysis_record(record: Any, analysis_key: str) -> Dict[str, Any]:
    payload = _safe_json_loads(getattr(record, 'results_json', None))
    if payload is None and analysis_key == 'zap':
        payload = _safe_json_loads(getattr(record, 'zap_report_json', None))
    if isinstance(payload, list):
        payload = {'items': payload}
    if not isinstance(payload, dict):
        payload = {}

    raw: Dict[str, Any] = dict(payload)
    metrics_source = raw.get('metrics')
    metrics: Dict[str, Any] = {}
    if isinstance(metrics_source, dict):
        metrics = {str(k): metrics_source[k] for k in metrics_source}

    def _add_metric(label: str, value: Any) -> None:
        if label not in metrics and value is not None:
            metrics[label] = _format_metric_value(value)

    if analysis_key == 'security':
        _add_metric('Total Issues', getattr(record, 'total_issues', None))
        _add_metric('Critical Alerts', getattr(record, 'critical_severity_count', None))
        _add_metric('High Alerts', getattr(record, 'high_severity_count', None))
        _add_metric('Medium Alerts', getattr(record, 'medium_severity_count', None))
        _add_metric('Low Alerts', getattr(record, 'low_severity_count', None))
    elif analysis_key == 'performance':
        _add_metric('Requests/sec', getattr(record, 'requests_per_second', None))
        _add_metric('Avg Response (ms)', getattr(record, 'average_response_time', None))
        _add_metric('p95 Response (ms)', getattr(record, 'p95_response_time', None))
        _add_metric('Error Rate (%)', getattr(record, 'error_rate', None))
        _add_metric('Total Requests', getattr(record, 'total_requests', None))
        _add_metric('Failed Requests', getattr(record, 'failed_requests', None))
    elif analysis_key == 'zap':
        _add_metric('High Alerts', getattr(record, 'high_risk_alerts', None))
        _add_metric('Medium Alerts', getattr(record, 'medium_risk_alerts', None))
        _add_metric('Low Alerts', getattr(record, 'low_risk_alerts', None))
        _add_metric('Info Alerts', getattr(record, 'informational_alerts', None))
    elif analysis_key == 'openrouter':
        summary_text = getattr(record, 'summary', None)
        if summary_text and 'summary' not in raw:
            raw['summary'] = summary_text
        findings = _safe_json_loads(getattr(record, 'findings_json', None))
        if findings and 'issues' not in raw:
            raw['issues'] = findings
        recommendations = _safe_json_loads(getattr(record, 'recommendations_json', None))
        if recommendations and 'recommendations' not in raw:
            raw['recommendations'] = recommendations
        overall_score = getattr(record, 'overall_score', None)
        if overall_score is not None and 'overall_score' not in raw:
            raw['overall_score'] = overall_score
        _add_metric('Code Quality Score', getattr(record, 'code_quality_score', None))
        _add_metric('Security Score', getattr(record, 'security_score', None))
        _add_metric('Maintainability Score', getattr(record, 'maintainability_score', None))
        _add_metric('Input Tokens', getattr(record, 'input_tokens', None))
        _add_metric('Output Tokens', getattr(record, 'output_tokens', None))
        _add_metric('Cost (USD)', getattr(record, 'cost_usd', None))

    if metrics:
        raw['metrics'] = metrics

    error_message = getattr(record, 'error_message', None)
    if not error_message:
        err_candidate = raw.get('error') if isinstance(raw, dict) else None
        if err_candidate:
            error_message = str(err_candidate)

    status_str = _enum_to_str(getattr(record, 'status', None)) or 'unknown'
    analysis_type, analysis_label = _analysis_type_metadata(analysis_key)

    return {
        'id': getattr(record, 'id', None),
        'analysis_type': analysis_type,
        'analysis_label': analysis_label,
        'status': status_str,
        'started_at': getattr(record, 'started_at', None),
        'completed_at': getattr(record, 'completed_at', None),
        'created_at': getattr(record, 'created_at', None),
        'results_json': raw,
        'error_message': error_message,
        'raw_type': analysis_key,
    }


def _collect_app_files(app_path: Path) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    files_info = {
        'app_exists': app_path.exists(),
        'docker_compose': (app_path / 'docker-compose.yml').exists(),
        'backend_files': [],
        'frontend_files': [],
        'other_files': [],
    }
    code_stats: Dict[str, Any] = {'total_files': 0, 'total_loc': 0, 'by_language': {}}
    file_stats: Dict[str, Any] = {'total_files': 0, 'total_size': 0, 'code_files': 0, 'config_files': 0, 'by_extension': {}}
    scanned_files: List[Dict[str, Any]] = []
    if not app_path.exists():
        return files_info, code_stats, scanned_files, file_stats
    lang_map = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'TypeScript', '.jsx': 'JavaScript',
        '.html': 'HTML', '.css': 'CSS', '.md': 'Markdown', '.json': 'JSON', '.yml': 'YAML', '.yaml': 'YAML'
    }
    code_exts = {'.py', '.js', '.ts', '.tsx', '.jsx'}
    config_exts = {'.json', '.yml', '.yaml', '.toml', '.cfg', '.ini'}
    try:
        for item in app_path.rglob('*'):
            if not item.is_file():
                continue
            rel_path = item.relative_to(app_path)
            try:
                size = item.stat().st_size
            except Exception:
                size = 0
            info = {
                'name': item.name,
                'path': str(rel_path),
                'size': size,
                'is_directory': False,
            }
            scanned_files.append(info)
            lower_path = str(rel_path).lower()
            if 'backend' in lower_path:
                files_info['backend_files'].append(info)
            elif 'frontend' in lower_path:
                files_info['frontend_files'].append(info)
            else:
                files_info['other_files'].append(info)
            ext = item.suffix.lower()
            lang = lang_map.get(ext, 'Other')
            try:
                text = item.read_text(encoding='utf-8', errors='ignore')
                loc = text.count('\n') + 1 if text else 0
            except Exception:
                loc = 0
            code_stats['total_files'] += 1
            code_stats['total_loc'] += loc
            entry = code_stats['by_language'].setdefault(lang, {'files': 0, 'loc': 0})
            entry['files'] += 1
            entry['loc'] += loc
            file_stats['total_files'] += 1
            file_stats['total_size'] += size
            if ext in code_exts:
                file_stats['code_files'] += 1
            if ext in config_exts:
                file_stats['config_files'] += 1
            ext_entry = file_stats['by_extension'].setdefault(ext or '', {'count': 0, 'size': 0})
            ext_entry['count'] += 1
            ext_entry['size'] += size
    except Exception as err:
        current_app.logger.warning("File scan failed for %s: %s", app_path, err)
    scanned_files.sort(key=lambda f: f['path'])
    total_size = file_stats['total_size'] or 0
    for ext, entry in file_stats['by_extension'].items():
        entry['percentage'] = round((entry['size'] / total_size) * 100.0, 2) if total_size else 0.0
    return files_info, code_stats, scanned_files, file_stats


def _collect_artifacts(app_path: Path) -> Dict[str, Optional[Path]]:
    exists = app_path.exists()
    return {
        'project_index': (app_path / 'PROJECT_INDEX.md') if exists and (app_path / 'PROJECT_INDEX.md').exists() else None,
        'readme': (app_path / 'README.md') if exists and (app_path / 'README.md').exists() else None,
        'compose_path': (app_path / 'docker-compose.yml') if exists and (app_path / 'docker-compose.yml').exists() else None,
    }


def _collect_app_prompts(app_number: int, model_slug: str = None) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], str]:
    """
    Collect FULL prompts and responses from generated/raw/{payloads,responses}/{model_slug}/app{number}/*.json files
    Falls back to misc/app_templates for legacy support
    Returns: (prompts, responses, template_files, source_dir)
    """
    prompts = {'backend': '', 'frontend': ''}
    responses = {'backend': '', 'frontend': ''}
    template_files = {'backend_file': '', 'frontend_file': ''}
    
    # Try new location first: generated/raw/payloads/{model_slug}/app{number}/
    if model_slug:
        payloads_dir = _project_root() / 'generated' / 'raw' / 'payloads' / model_slug / f'app{app_number}'
        responses_dir = _project_root() / 'generated' / 'raw' / 'responses' / model_slug / f'app{app_number}'
        current_app.logger.info(f"Looking for prompts in: {payloads_dir}, exists: {payloads_dir.exists()}")
        
        if payloads_dir.exists():
            try:
                import json
                backend_files = sorted(payloads_dir.glob(f'*_app{app_number}_backend_*_payload.json'))
                frontend_files = sorted(payloads_dir.glob(f'*_app{app_number}_frontend_*_payload.json'))
                current_app.logger.info(f"Found backend files: {len(backend_files)}, frontend files: {len(frontend_files)}")
                
                if backend_files:
                    template_files['backend_file'] = backend_files[0].name
                    with open(backend_files[0], 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Build complete payload representation
                        payload = data.get('payload', {})
                        parts = []
                        parts.append(f"=== REQUEST METADATA ===")
                        parts.append(f"Timestamp: {data.get('timestamp', 'N/A')}")
                        parts.append(f"Run ID: {data.get('run_id', 'N/A')}")
                        parts.append(f"Model: {payload.get('model', 'N/A')}")
                        parts.append(f"Temperature: {payload.get('temperature', 'N/A')}")
                        parts.append(f"Max Tokens: {payload.get('max_tokens', 'N/A')}")
                        provider = payload.get('provider', {})
                        if provider:
                            parts.append(f"Provider Settings: allow_fallbacks={provider.get('allow_fallbacks')}, data_collection={provider.get('data_collection')}")
                        parts.append("")
                        # Add all messages
                        messages = payload.get('messages', [])
                        for msg in messages:
                            role = msg.get('role', 'unknown').upper()
                            content = msg.get('content', '')
                            parts.append(f"=== {role} ===")
                            parts.append(content)
                            parts.append("")
                        prompts['backend'] = '\n'.join(parts)
                        current_app.logger.info(f"Loaded backend prompt, length: {len(prompts['backend'])}")
                
                if frontend_files:
                    template_files['frontend_file'] = frontend_files[0].name
                    with open(frontend_files[0], 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        payload = data.get('payload', {})
                        parts = []
                        parts.append(f"=== REQUEST METADATA ===")
                        parts.append(f"Timestamp: {data.get('timestamp', 'N/A')}")
                        parts.append(f"Run ID: {data.get('run_id', 'N/A')}")
                        parts.append(f"Model: {payload.get('model', 'N/A')}")
                        parts.append(f"Temperature: {payload.get('temperature', 'N/A')}")
                        parts.append(f"Max Tokens: {payload.get('max_tokens', 'N/A')}")
                        provider = payload.get('provider', {})
                        if provider:
                            parts.append(f"Provider Settings: allow_fallbacks={provider.get('allow_fallbacks')}, data_collection={provider.get('data_collection')}")
                        parts.append("")
                        messages = payload.get('messages', [])
                        for msg in messages:
                            role = msg.get('role', 'unknown').upper()
                            content = msg.get('content', '')
                            parts.append(f"=== {role} ===")
                            parts.append(content)
                            parts.append("")
                        prompts['frontend'] = '\n'.join(parts)
                        current_app.logger.info(f"Loaded frontend prompt, length: {len(prompts['frontend'])}")
                
            except Exception as err:
                current_app.logger.warning("Failed to load prompts from raw payloads for %s/app%s: %s", model_slug, app_number, err)
        
        # Load responses with full metadata
        if responses_dir.exists():
            try:
                import json
                backend_resp_files = sorted(responses_dir.glob(f'*_app{app_number}_backend_*_response.json'))
                frontend_resp_files = sorted(responses_dir.glob(f'*_app{app_number}_frontend_*_response.json'))
                
                if backend_resp_files:
                    with open(backend_resp_files[0], 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        resp = data.get('response', {})
                        parts = []
                        parts.append(f"=== RESPONSE METADATA ===")
                        parts.append(f"Timestamp: {data.get('timestamp', 'N/A')}")
                        parts.append(f"Run ID: {data.get('run_id', 'N/A')}")
                        parts.append(f"Response ID: {resp.get('id', 'N/A')}")
                        parts.append(f"Model: {resp.get('model', 'N/A')}")
                        parts.append(f"Provider: {resp.get('provider', 'N/A')}")
                        # Usage stats
                        usage = resp.get('usage', {})
                        if usage:
                            parts.append(f"")
                            parts.append(f"=== USAGE ===")
                            parts.append(f"Prompt Tokens: {usage.get('prompt_tokens', 'N/A')}")
                            parts.append(f"Completion Tokens: {usage.get('completion_tokens', 'N/A')}")
                            parts.append(f"Total Tokens: {usage.get('total_tokens', 'N/A')}")
                            parts.append(f"Cost: ${usage.get('cost', 'N/A')}")
                        # Choice info
                        choices = resp.get('choices', [])
                        if choices:
                            choice = choices[0]
                            parts.append(f"")
                            parts.append(f"=== COMPLETION ===")
                            parts.append(f"Finish Reason: {choice.get('finish_reason', 'N/A')}")
                            parts.append(f"")
                            parts.append(f"=== ASSISTANT ===")
                            content = choice.get('message', {}).get('content', '')
                            parts.append(content)
                        responses['backend'] = '\n'.join(parts)
                        current_app.logger.info(f"Loaded backend response, length: {len(responses['backend'])}")
                
                if frontend_resp_files:
                    with open(frontend_resp_files[0], 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        resp = data.get('response', {})
                        parts = []
                        parts.append(f"=== RESPONSE METADATA ===")
                        parts.append(f"Timestamp: {data.get('timestamp', 'N/A')}")
                        parts.append(f"Run ID: {data.get('run_id', 'N/A')}")
                        parts.append(f"Response ID: {resp.get('id', 'N/A')}")
                        parts.append(f"Model: {resp.get('model', 'N/A')}")
                        parts.append(f"Provider: {resp.get('provider', 'N/A')}")
                        usage = resp.get('usage', {})
                        if usage:
                            parts.append(f"")
                            parts.append(f"=== USAGE ===")
                            parts.append(f"Prompt Tokens: {usage.get('prompt_tokens', 'N/A')}")
                            parts.append(f"Completion Tokens: {usage.get('completion_tokens', 'N/A')}")
                            parts.append(f"Total Tokens: {usage.get('total_tokens', 'N/A')}")
                            parts.append(f"Cost: ${usage.get('cost', 'N/A')}")
                        choices = resp.get('choices', [])
                        if choices:
                            choice = choices[0]
                            parts.append(f"")
                            parts.append(f"=== COMPLETION ===")
                            parts.append(f"Finish Reason: {choice.get('finish_reason', 'N/A')}")
                            parts.append(f"")
                            parts.append(f"=== ASSISTANT ===")
                            content = choice.get('message', {}).get('content', '')
                            parts.append(content)
                        responses['frontend'] = '\n'.join(parts)
                        current_app.logger.info(f"Loaded frontend response, length: {len(responses['frontend'])}")
                
            except Exception as err:
                current_app.logger.warning("Failed to load responses for %s/app%s: %s", model_slug, app_number, err)
        
        if prompts['backend'] or prompts['frontend']:
            current_app.logger.info(f"Returning prompts from raw payloads")
            return prompts, responses, template_files, str(payloads_dir)
    
    # Fallback to legacy location: misc/app_templates
    tmpl_dir = _project_root() / 'misc' / 'app_templates'
    if tmpl_dir.exists():
        try:
            backend_md = sorted(tmpl_dir.glob(f'app_{app_number}_backend_*.md'))
            frontend_md = sorted(tmpl_dir.glob(f'app_{app_number}_frontend_*.md'))
            if backend_md:
                template_files['backend_file'] = backend_md[0].name
                prompts['backend'] = backend_md[0].read_text(encoding='utf-8', errors='ignore')
            if frontend_md:
                template_files['frontend_file'] = frontend_md[0].name
                prompts['frontend'] = frontend_md[0].read_text(encoding='utf-8', errors='ignore')
        except Exception as err:
            current_app.logger.warning("Failed to load prompts from templates for app %s: %s", app_number, err)
    
    return prompts, responses, template_files, str(tmpl_dir)


def _collect_ports(model_slug: str, app_number: int, app: Optional[GeneratedApplication]) -> Tuple[Optional[Dict[str, int]], List[Dict[str, Any]]]:
    ports_dict: Optional[Dict[str, int]] = None
    try:
        pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_number).first()
        if pc:
            ports_dict = {'backend': pc.backend_port, 'frontend': pc.frontend_port}
    except Exception as err:
        current_app.logger.warning("PortConfiguration lookup failed for %s/%s: %s", model_slug, app_number, err)
    if not ports_dict and app:
        try:
            candidate = app.get_ports() or {}
            if isinstance(candidate, dict):
                temp_ports: Dict[str, int] = {}
                for key in ('backend', 'frontend'):
                    value = candidate.get(key)
                    if isinstance(value, int):
                        temp_ports[key] = value
                if temp_ports:
                    ports_dict = temp_ports
        except Exception as err:
            current_app.logger.debug("Application get_ports failed for %s/%s: %s", model_slug, app_number, err)
    if not ports_dict:
        try:
            resolved = resolve_ports(model_slug, app_number, include_attempts=False)
            if resolved:
                temp_ports: Dict[str, int] = {}
                for key in ('backend', 'frontend'):
                    value = resolved.get(key)
                    if isinstance(value, int):
                        temp_ports[key] = value
                if temp_ports:
                    ports_dict = temp_ports
        except Exception as err:
            current_app.logger.debug("Port resolution failed for %s/%s: %s", model_slug, app_number, err)
    port_entries: List[Dict[str, Any]] = []
    seen: set[int] = set()
    running = bool(app and (getattr(app, 'container_status', '') or '').lower() == 'running')
    
    # Also check actual Docker container status if available
    if not running and app:
        try:
            from app.services.service_locator import ServiceLocator
            docker_manager = ServiceLocator.get('docker_manager')
            if docker_manager:
                container_name = f"{model_slug}-app{app_number}"
                status = docker_manager.get_container_status(container_name)
                running = status and status.get('State', {}).get('Running', False)
                current_app.logger.info(f"Docker direct check for {container_name}: running={running}")
        except Exception as err:
            current_app.logger.debug(f"Failed to check Docker status directly: {err}")
    
    if ports_dict:
        for role, value in ports_dict.items():
            if not isinstance(value, int) or value in seen:
                continue
            seen.add(value)
            port_entries.append({
                'role': role,
                'container_port': value,
                'host_port': value,
                'protocol': 'tcp',
                'accessible': running,  # Used by template
                'is_accessible': running,  # Legacy compatibility
                'description': f"{role.replace('_', ' ').title()} service",
                'is_exposed': True,
            })
    port_entries.sort(key=lambda entry: entry['host_port'])
    return ports_dict if ports_dict else None, port_entries


def _collect_app_analyses(app: Optional[GeneratedApplication]) -> Tuple[Dict[str, List[Any]], Dict[str, int], List[Dict[str, Any]]]:
    analyses: Dict[str, List[Any]] = {'security': [], 'performance': [], 'zap': [], 'openrouter': []}
    stats = {
        'total_security_analyses': 0,
        'total_performance_tests': 0,
        'total_zap_analyses': 0,
        'total_openrouter_analyses': 0,
    }
    entries: List[Dict[str, Any]] = []
    if not app:
        return analyses, stats, entries
    analyses['security'] = SecurityAnalysis.query.filter_by(application_id=app.id).order_by(SecurityAnalysis.created_at.desc()).all()
    analyses['performance'] = PerformanceTest.query.filter_by(application_id=app.id).order_by(PerformanceTest.created_at.desc()).all()
    analyses['zap'] = ZAPAnalysis.query.filter_by(application_id=app.id).order_by(ZAPAnalysis.created_at.desc()).all()
    analyses['openrouter'] = OpenRouterAnalysis.query.filter_by(application_id=app.id).order_by(OpenRouterAnalysis.created_at.desc()).all()
    stats['total_security_analyses'] = len(analyses['security'])
    stats['total_performance_tests'] = len(analyses['performance'])
    stats['total_zap_analyses'] = len(analyses['zap'])
    stats['total_openrouter_analyses'] = len(analyses['openrouter'])
    for key, records in analyses.items():
        for record in records:
            entries.append(_normalize_analysis_record(record, key))
    entries.sort(key=_analysis_sort_key, reverse=True)
    return analyses, stats, entries


def _collect_analysis_tasks(model_slug: str, app_number: int) -> List[AnalysisTask]:
    """Collect AnalysisTask records from the database for this application.
    
    Returns a list of AnalysisTask objects ordered by created_at descending.
    """
    try:
        # Query for tasks matching this model and app number
        tasks = AnalysisTask.query.filter_by(
            target_model=model_slug,
            target_app_number=app_number
        ).order_by(AnalysisTask.created_at.desc()).all()
        
        # Also check for slug variants if no results
        if not tasks:
            variants = _slug_variants(model_slug)
            for variant in variants:
                if variant != model_slug:
                    tasks = AnalysisTask.query.filter_by(
                        target_model=variant,
                        target_app_number=app_number
                    ).order_by(AnalysisTask.created_at.desc()).all()
                    if tasks:
                        break
        
        return tasks
    except Exception as err:
        current_app.logger.warning("Failed to collect analysis tasks for %s/app%s: %s", model_slug, app_number, err)
        return []


def _derive_status(container_status: Optional[str], generation_status: Optional[str], exists: bool) -> str:
    container = (container_status or '').lower()
    generation = (generation_status or '').lower()
    if container == 'running':
        return 'running'
    if container in {'error', 'failed'} or generation in {'error', 'failed'}:
        return 'failed'
    if generation in {'completed', 'success', 'generated'}:
        return 'completed'
    if not exists:
        return 'not_created'
    return 'pending'


def _build_application_badges(app_data: Dict[str, Any], model_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    badges: List[Dict[str, Any]] = []
    app_type = app_data.get('app_type')
    if app_type and app_type != 'unknown':
        badges.append({'label': app_type.replace('_', ' ').title(), 'variant': 'badge bg-info-lt', 'icon': 'fas fa-layer-group'})
    provider = app_data.get('provider') or model_dict.get('provider') or 'local'
    badges.append({'label': provider, 'variant': 'badge bg-primary-lt', 'icon': 'fas fa-robot'})
    created_at = app_data.get('created_at')
    if created_at:
        try:
            badges.append({'label': f"Created {created_at.strftime('%Y-%m-%d')}", 'variant': 'badge bg-secondary-lt', 'icon': 'fas fa-clock'})
        except Exception:
            badges.append({'label': f"Created {created_at}", 'variant': 'badge bg-secondary-lt', 'icon': 'fas fa-clock'})
    frameworks = [f for f in (app_data.get('backend_framework'), app_data.get('frontend_framework')) if f]
    if frameworks:
        badges.append({'label': ' / '.join(frameworks), 'variant': 'badge bg-success-lt', 'icon': 'fas fa-cubes'})
    return badges


def _build_application_actions(app_data: Dict[str, Any], ports: List[Dict[str, Any]], model_slug: str, app_number: int) -> List[Dict[str, Any]]:
    export_url = f"/applications/{model_slug}/{app_number}/export.csv"
    running = (app_data.get('container_status') or '').lower() == 'running'
    exists = bool(app_data.get('exists_in_db'))
    accessible = bool(running and ports)
    primary_port = ports[0]['host_port'] if accessible else None
    actions = [
        {
            'key': 'start',
            'type': 'button',
            'label': 'Start',
            'icon': 'fas fa-play',
            'classes': 'btn-success btn-sm',
            'onclick': 'startApplication()',
            'visible': exists and not running,
        },
        {
            'key': 'stop',
            'type': 'button',
            'label': 'Stop',
            'icon': 'fas fa-stop',
            'classes': 'btn-danger btn-sm',
            'onclick': 'stopApplication()',
            'visible': running,
        },
        {
            'key': 'restart',
            'type': 'button',
            'label': 'Restart',
            'icon': 'fas fa-rotate',
            'classes': 'btn-warning btn-sm',
            'onclick': 'restartApplication()',
            'visible': exists,
        },
        {
            'key': 'build',
            'type': 'button',
            'label': 'Rebuild',
            'icon': 'fas fa-hammer',
            'classes': 'btn-primary btn-sm',
            'onclick': 'buildApplication()',
            'visible': exists,
        },
        {
            'key': 'open',
            'type': 'link',
            'label': 'Open App',
            'icon': 'fas fa-external-link-alt',
            'classes': 'btn-ghost-success btn-sm',
            'href': f"http://localhost:{primary_port}" if primary_port else '',
            'target': '_blank',
            'visible': accessible and primary_port is not None,
        },
        {
            'key': 'back',
            'type': 'link',
            'label': 'Back',
            'icon': 'fas fa-arrow-left',
            'classes': 'btn-ghost-secondary btn-sm',
            'href': '/applications',
            'visible': True,
        },
        {
            'key': 'export',
            'type': 'link',
            'label': 'Export',
            'icon': 'fas fa-download',
            'classes': 'btn-ghost-secondary btn-sm',
            'href': export_url,
            'visible': exists,
        },
    ]
    return actions


def _build_application_metrics(app_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    status = str(app_data.get('status') or '').lower()
    status_class = {
        'running': 'text-success',
        'completed': 'text-primary',
        'failed': 'text-danger',
        'pending': 'text-warning',
        'not_created': 'text-muted',
    }.get(status, 'text-muted')
    metrics = [
        {
            'label': 'Container',
            'value': app_data.get('container_status_display') or 'Unknown',
            'hint': 'Current lifecycle state',
            'tone': status_class,
        },
        {
            'label': 'Ports',
            'value': app_data.get('ports_count', 0),
            'hint': 'Published endpoints',
            'tone': 'text-success' if app_data.get('ports_count') else 'text-muted',
        },
        {
            'label': 'Created',
            'value': _format_datetime(app_data.get('created_at')),
            'hint': 'Generation timestamp',
            'tone': 'text-info',
        },
        {
            'label': 'Last Updated',
            'value': _format_datetime(app_data.get('updated_at')),
            'hint': 'Metadata refresh',
            'tone': 'text-muted',
        },
    ]
    return metrics


def _collect_app_logs(model_slug: str, app_number: int, tail: int = 100) -> Tuple[str, Dict[str, int]]:
    """Collect container logs for the application.
    
    Returns:
        Tuple of (log_content, log_stats)
    """
    from app.services.service_locator import ServiceLocator
    
    try:
        docker_mgr = ServiceLocator.get('docker_manager')
        if not docker_mgr:
            current_app.logger.warning(f"Docker manager not available for logs collection")
            return '', {'error_count': 0, 'warning_count': 0, 'info_count': 0, 'total_lines': 0}
        
        # Try to get backend logs first, then frontend as fallback
        logs = ''
        try:
            backend_logs = docker_mgr.get_container_logs(model_slug, app_number, 'backend', tail=tail)
            current_app.logger.debug(f"Backend logs result: {backend_logs[:100] if backend_logs else 'None'}")
            # Filter out error messages - we only want actual logs
            if backend_logs and not any(err in backend_logs for err in ['not found', 'unavailable', 'Error getting']):
                logs += f"=== Backend Logs ===\n{backend_logs}\n\n"
            else:
                current_app.logger.debug(f"Backend logs contained error or empty: {backend_logs[:200] if backend_logs else 'Empty'}")
        except Exception as e:
            current_app.logger.debug(f"Could not fetch backend logs: {e}")
        
        try:
            frontend_logs = docker_mgr.get_container_logs(model_slug, app_number, 'frontend', tail=tail)
            current_app.logger.debug(f"Frontend logs result: {frontend_logs[:100] if frontend_logs else 'None'}")
            # Filter out error messages - we only want actual logs
            if frontend_logs and not any(err in frontend_logs for err in ['not found', 'unavailable', 'Error getting']):
                logs += f"=== Frontend Logs ===\n{frontend_logs}\n"
            else:
                current_app.logger.debug(f"Frontend logs contained error or empty: {frontend_logs[:200] if frontend_logs else 'Empty'}")
        except Exception as e:
            current_app.logger.debug(f"Could not fetch frontend logs: {e}")
        
        current_app.logger.info(f"Total logs collected for {model_slug}/app{app_number}: {len(logs)} chars")
        
        # Calculate statistics
        lines = [line for line in logs.split('\n') if line.strip()]
        stats = {
            'error_count': sum(1 for line in lines if 'ERROR' in line.upper() or 'error' in line),
            'warning_count': sum(1 for line in lines if 'WARN' in line.upper() or 'warning' in line),
            'info_count': sum(1 for line in lines if 'INFO' in line.upper()),
            'total_lines': len(lines),
        }
        
        return logs, stats
        
    except Exception as e:
        current_app.logger.error(f"Error collecting logs for {model_slug}/app{app_number}: {e}")
        return '', {'error_count': 0, 'warning_count': 0, 'info_count': 0, 'total_lines': 0}


def _build_application_sections(model_slug: str, app_number: int) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    base = [
        ('overview', 'Overview', 'fas fa-info-circle', 'pages/applications/partials/_overview.html'),
        ('prompts', 'Prompts', 'fas fa-terminal', 'pages/applications/partials/_prompts.html'),
        ('files', 'Files', 'fas fa-folder-open', 'pages/applications/partials/_files.html'),
        ('ports', 'Ports', 'fas fa-network-wired', 'pages/applications/partials/_ports.html'),
        ('container', 'Container', 'fab fa-docker', 'pages/applications/partials/_container.html'),
        ('analyses', 'Analyses', 'fas fa-flask', 'pages/applications/partials/_analyses.html'),
        ('metadata', 'Metadata', 'fas fa-database', 'pages/applications/partials/_metadata.html'),
        ('artifacts', 'Artifacts', 'fas fa-book', 'pages/applications/partials/_artifacts.html'),
        ('logs', 'Logs', 'fas fa-file-lines', 'pages/applications/partials/_logs.html'),
    ]
    sections: List[Dict[str, Any]] = []
    sections_map: Dict[str, Dict[str, Any]] = {}
    for identifier, label, icon, template in base:
        section = {
            'id': identifier,
            'label': label,
            'icon': icon,
            'template': template,
            'hx': f"/applications/{model_slug}/{app_number}/section/{identifier}",
            'dom_id': f"section-{identifier}",
            'placeholder_rows': 3,
        }
        sections.append(section)
        sections_map[identifier] = section
    return sections, sections_map


def build_application_detail_context(model_slug: str, app_number: int, allow_synthetic: bool = False) -> Dict[str, Any]:
    model = _resolve_model(model_slug, allow_synthetic)
    app = _resolve_application(model, model_slug, app_number)
    resolved_slug = getattr(app, 'model_slug', None) or getattr(model, 'canonical_slug', None) or model_slug
    model_dict = _model_to_dict(model)
    app_data: Dict[str, Any] = {
        'id': getattr(app, 'id', None),
        'model_slug': resolved_slug,
        'app_number': app_number,
        'exists_in_db': bool(app),
        'app_type': getattr(app, 'app_type', None) or ('unknown' if not app else getattr(app, 'app_type', None)),
        'provider': getattr(app, 'provider', None) or model_dict.get('provider') or 'local',
        'generation_status': _enum_to_str(getattr(app, 'generation_status', None)),
        'container_status': getattr(app, 'container_status', None),
        'has_backend': getattr(app, 'has_backend', False),
        'has_frontend': getattr(app, 'has_frontend', False),
        'has_docker_compose': getattr(app, 'has_docker_compose', False),
        'backend_framework': getattr(app, 'backend_framework', None),
        'frontend_framework': getattr(app, 'frontend_framework', None),
        'created_at': getattr(app, 'created_at', None),
        'updated_at': getattr(app, 'updated_at', None),
        'metadata': app.get_metadata() if app and hasattr(app, 'get_metadata') else {},
        'last_status_check': getattr(app, 'last_status_check', None),
        # Fixes applied tracking
        'retry_fixes': getattr(app, 'retry_fixes', 0) or 0,
        'automatic_fixes': getattr(app, 'automatic_fixes', 0) or 0,
        'llm_fixes': getattr(app, 'llm_fixes', 0) or 0,
        'manual_fixes': getattr(app, 'manual_fixes', 0) or 0,
    }
    app_data['app_type'] = app_data['app_type'] or 'unknown'
    app_data['container_status_display'] = (app_data.get('container_status') or 'unknown').replace('_', ' ').title()
    app_data['status'] = _derive_status(app_data.get('container_status'), app_data.get('generation_status'), app_data['exists_in_db'])
    app_data['status_display'] = app_data['status'].replace('_', ' ').title()
    
    # Check for unhealthy container status (status is 'failed' from _derive_status or explicit error states)
    container_status_raw = (app_data.get('container_status') or '').lower()
    app_data['is_container_unhealthy'] = (
        app_data['status'] == 'failed' or 
        container_status_raw in ('error', 'failed', 'exited', 'dead', 'unhealthy')
    )

    app_path = get_app_directory(resolved_slug, app_number)
    files_info, code_stats, files, file_stats = _collect_app_files(app_path)
    artifacts = _collect_artifacts(app_path)
    ports_raw, ports = _collect_ports(resolved_slug, app_number, app)
    app_data['ports'] = ports
    app_data['ports_count'] = len(ports)
    prompts, responses, template_files, templates_dir = _collect_app_prompts(app_number, resolved_slug)
    analyses, stats, analysis_entries = _collect_app_analyses(app)
    analysis_tasks = _collect_analysis_tasks(resolved_slug, app_number)
    logs, log_stats = _collect_app_logs(resolved_slug, app_number)
    slug_candidates = {resolved_slug}
    canonical = getattr(model, 'canonical_slug', None)
    if canonical:
        slug_candidates.add(canonical)
    model_name = getattr(model, 'model_name', None)
    if model_name:
        slug_candidates.add(model_name)
    model_apps_count = GeneratedApplication.query.filter(GeneratedApplication.model_slug.in_(list(slug_candidates))).count()
    model_dict['apps_count'] = model_apps_count
    badges = _build_application_badges(app_data, model_dict)
    actions = _build_application_actions(app_data, ports, resolved_slug, app_number)
    metrics = _build_application_metrics(app_data)
    sections, sections_map = _build_application_sections(resolved_slug, app_number)

    def _port_value(role: str) -> Optional[int]:
        for entry in ports:
            if entry.get('role') == role:
                return entry.get('host_port')
        return None

    application_view = {
        'id': app_data.get('id'),
        'model_slug': resolved_slug,
        'app_number': app_number,
        'status': app_data.get('status'),
        'created_at': app_data.get('created_at'),
        'backend_port': _port_value('backend'),
        'frontend_port': _port_value('frontend'),
        'is_running': app_data.get('status') == 'running',
        'last_started': None,
        'file_count': code_stats.get('total_files', 0),
        'total_size': file_stats.get('total_size', 0),
        'environment_variables': {},
        'analyses': analysis_entries,
        'generation_log': None,
        'versions': [],
    }

    view = {
        'pretitle': 'Application Detail',
        'icon': 'fas fa-cube',
        'title': f"Application #{app_number}",
        'subtitle': f'<a href="/models/{resolved_slug}" class="text-reset">{model_dict.get("display_name") or resolved_slug}</a> · {resolved_slug}',
        'badges': badges,
        'actions': actions,
    }

    return {
        'view': view,
        'metrics': metrics,
        'sections': sections,
        'app_data': app_data,
        'application': application_view,
        'model': model_dict,
        'model_record': model,
        'files_info': files_info,
        'code_stats': code_stats,
        'files': files,
        'file_stats': file_stats,
        'analyses': analyses,
        'analysis_entries': analysis_entries,
        'analysis_tasks': analysis_tasks,
        'stats': stats,
        'ports': ports,
        'raw_ports': ports_raw,
        'prompts': prompts,
        'responses': responses,
        'template_files': template_files,
        'artifacts': artifacts,
        'templates_dir': templates_dir,
        'app_base_dir': str(app_path),
        'sections_map': sections_map,
        'active_page': 'applications',
        'logs': logs,
        'log_stats': log_stats,
    }


def _build_model_badges(model_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    badges: List[Dict[str, Any]] = []
    if model_dict.get('model_id'):
        badges.append({'label': model_dict['model_id'], 'variant': 'badge bg-primary-lt', 'icon': 'fas fa-id-card'})
    if model_dict.get('id'):
        badges.append({'label': f"#{model_dict['id']}", 'variant': 'badge bg-secondary-lt', 'icon': 'fas fa-database'})
    slug = model_dict.get('canonical_slug')
    if slug and slug != model_dict.get('model_id'):
        badges.append({'label': slug, 'variant': 'badge bg-info-lt', 'icon': 'fas fa-link'})
    if model_dict.get('is_free'):
        badges.append({'label': 'Free Tier', 'variant': 'badge bg-success-lt', 'icon': 'fas fa-gift'})
    if model_dict.get('installed'):
        badges.append({'label': 'Installed', 'variant': 'badge bg-azure-lt', 'icon': 'fas fa-check-circle'})
    return badges


def _build_model_actions(model_slug: str) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'generate',
            'type': 'button',
            'label': 'Generate App',
            'icon': 'fas fa-plus',
            'classes': 'btn-primary btn-sm',
            'onclick': 'generateApplication()',
            'visible': True,
        },
        {
            'key': 'compare',
            'type': 'button',
            'label': 'Compare',
            'icon': 'fas fa-balance-scale',
            'classes': 'btn-ghost-primary btn-sm',
            'onclick': 'openModelComparison()',
            'visible': True,
        },
        {
            'key': 'refresh',
            'type': 'button',
            'label': 'Refresh Data',
            'icon': 'fas fa-sync',
            'classes': 'btn-ghost-secondary btn-sm',
            'onclick': 'refreshModelData()',
            'visible': True,
            'title': 'Reload model data from OpenRouter API',
        },
        {
            'key': 'export',
            'type': 'link',
            'label': 'Export JSON',
            'icon': 'fas fa-download',
            'classes': 'btn-ghost-secondary btn-sm',
            'href': f"/models/{model_slug}/export.json",
            'visible': True,
        },
    ]


def _build_model_metrics(model_dict: Dict[str, Any], enriched_data: Dict[str, Any], stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    context_value = model_dict.get('context_window') or enriched_data.get('openrouter_context_length')
    if context_value:
        try:
            context_display = f"{int(context_value):,}"
        except Exception:
            try:
                context_display = f"{float(context_value):,.0f}"
            except Exception:
                context_display = str(context_value)
    else:
        context_display = '—'
    cost_eff = model_dict.get('cost_efficiency')
    if cost_eff:
        try:
            cost_display = f"{float(cost_eff):.2f}"
        except Exception:
            cost_display = str(cost_eff)
    else:
        cost_display = '—'
    metrics = [
        {
            'label': 'Applications',
            'value': stats.get('applications', 0),
            'hint': 'Generated with this model',
            'tone': 'text-primary',
        },
        {
            'label': 'Context Window',
            'value': context_display,
            'hint': 'Tokens per request',
            'tone': 'text-success',
        },
        {
            'label': 'Cost Efficiency',
            'value': cost_display,
            'hint': 'Higher is better',
            'tone': 'text-info',
        },
        {
            'label': 'Last Updated',
            'value': _format_datetime(model_dict.get('updated_at')),
            'hint': 'Catalog sync timestamp',
            'tone': 'text-muted',
        },
    ]
    return metrics



def _calculate_average_model_stats() -> Dict[str, Any]:
    """Calculate average statistics across all models for comparison."""
    try:
        from sqlalchemy import func
        
        # Query for averages
        avg_data = db.session.query(
            func.avg(ModelCapability.input_price_per_token).label('avg_prompt_price'),
            func.avg(ModelCapability.output_price_per_token).label('avg_completion_price'),
            func.avg(ModelCapability.context_window).label('avg_context_length'),
            func.avg(ModelCapability.cost_efficiency).label('avg_cost_efficiency'),
        ).filter(
            ModelCapability.input_price_per_token.isnot(None),
            ModelCapability.input_price_per_token > 0
        ).first()
        
        if not avg_data:
            return {
                'avg_prompt_price': 0,
                'avg_completion_price': 0,
                'avg_context_length': 0,
                'avg_cost_efficiency': 0,
            }
        
        return {
            'avg_prompt_price': float(avg_data[0] or 0) * 1000,  # Convert to per 1K tokens
            'avg_completion_price': float(avg_data[1] or 0) * 1000,
            'avg_context_length': int(avg_data[2] or 0),
            'avg_cost_efficiency': float(avg_data[3] or 0),
        }
    except Exception as e:
        current_app.logger.error(f"Error calculating average model stats: {e}")
        return {
            'avg_prompt_price': 0,
            'avg_completion_price': 0,
            'avg_context_length': 0,
            'avg_cost_efficiency': 0,
        }


def _build_model_sections(model_slug: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    base = [
        ('overview', 'Overview', 'fas fa-info-circle', 'pages/models/partials/_model_overview.html'),
        ('capabilities', 'Capabilities', 'fas fa-cogs', 'pages/models/partials/_model_capabilities.html'),
        ('provider', 'Provider & Performance', 'fas fa-server', 'pages/models/partials/_provider_performance.html'),
        ('pricing', 'Pricing', 'fas fa-dollar-sign', 'pages/models/partials/_pricing_info.html'),
        ('applications', 'Applications', 'fas fa-cube', 'pages/models/partials/_model_applications.html'),
        ('usage', 'Usage Analytics', 'fas fa-chart-line', 'pages/models/partials/_usage_analytics.html'),
        ('metadata', 'Metadata', 'fas fa-database', 'pages/models/partials/_model_metadata.html'),
    ]
    sections: List[Dict[str, Any]] = []
    sections_map: Dict[str, Dict[str, Any]] = {}
    for identifier, label, icon, template in base:
        section = {
            'id': identifier,
            'label': label,
            'icon': icon,
            'template': template,
            'hx': f"/models/detail/{model_slug}/section/{identifier}",
            'dom_id': f"section-{identifier}",
            'placeholder_rows': 3,
        }
        sections.append(section)
        sections_map[identifier] = section
    return sections, sections_map


def build_model_detail_context(
    model_slug: str,
    enrich_model: Optional[Callable[[ModelCapability], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
    if not model:
        variants = _slug_variants(model_slug)
        if variants:
            model = ModelCapability.query.filter(or_(ModelCapability.canonical_slug.in_(variants), ModelCapability.model_name.in_(variants))).first()
    if not model:
        abort(404)
    enriched_data: Dict[str, Any] = {}
    if enrich_model:
        enriched_data = enrich_model(model) or {}
    cached_info = ExternalModelInfoCache.query.filter_by(model_slug=model.canonical_slug).first()
    cache_timestamp = None
    if cached_info:
        try:
            enriched_data = deep_merge_dicts(enriched_data, cached_info.get_data())
            cache_timestamp = cached_info.updated_at
        except Exception:
            pass
    applications = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug).order_by(GeneratedApplication.created_at.desc()).all()
    app_count = len(applications)
    recent_apps = applications[:5]
    
    # Calculate version counts per app_number
    from sqlalchemy import func
    app_version_counts = {}
    version_count_query = db.session.query(
        GeneratedApplication.app_number,
        func.count(GeneratedApplication.id).label('version_count')
    ).filter_by(
        model_slug=model.canonical_slug
    ).group_by(
        GeneratedApplication.app_number
    ).all()
    
    for app_num, count in version_count_query:
        app_version_counts[app_num] = count
    
    security_count = db.session.query(SecurityAnalysis).join(GeneratedApplication).filter(GeneratedApplication.model_slug == model.canonical_slug).count()
    performance_count = db.session.query(PerformanceTest).join(GeneratedApplication).filter(GeneratedApplication.model_slug == model.canonical_slug).count()
    
    # Calculate usage analytics
    running_apps = sum(1 for app in applications if getattr(app, 'container_status', None) == 'running')
    avg_analysis_quality = None
    if security_count > 0 or performance_count > 0:
        # Calculate analysis quality based on severity (lower is better)
        security_analyses = db.session.query(SecurityAnalysis).join(GeneratedApplication).filter(
            GeneratedApplication.model_slug == model.canonical_slug,
            SecurityAnalysis.status == 'COMPLETED'
        ).all()
        performance_tests = db.session.query(PerformanceTest).join(GeneratedApplication).filter(
            GeneratedApplication.model_slug == model.canonical_slug,
            PerformanceTest.status == 'COMPLETED'
        ).all()
        
        # Calculate quality score: fewer critical/high issues = better quality
        quality_scores = []
        for s in security_analyses:
            if s.total_issues is not None and s.total_issues > 0:
                # Penalize critical and high severity issues more
                penalty = (s.critical_severity_count or 0) * 10 + (s.high_severity_count or 0) * 5 + (s.medium_severity_count or 0) * 2
                quality_scores.append(max(0, 100 - penalty))
        
        for p in performance_tests:
            if p.error_rate is not None:
                # Convert error rate to quality score (0% error = 100, 100% error = 0)
                quality_scores.append(max(0, 100 - (p.error_rate * 100)))
        
        if quality_scores:
            avg_analysis_quality = sum(quality_scores) / len(quality_scores)
    
    model_dict = _model_to_dict(model)
    model_dict['apps_count'] = app_count
    model_dict['capabilities'] = enriched_data.get('capabilities', {})
    model_dict['metadata'] = enriched_data
    model_dict['cache_timestamp'] = cache_timestamp
    
    # Calculate average model stats for comparison
    avg_stats = _calculate_average_model_stats()
    
    stats = {
        'applications': app_count,
        'running_apps': running_apps,
        'security_tests': security_count,
        'performance_tests': performance_count,
        'avg_analysis_quality': avg_analysis_quality,
        'avg_prompt_price': avg_stats.get('avg_prompt_price', 0),
        'avg_completion_price': avg_stats.get('avg_completion_price', 0),
        'avg_context_length': avg_stats.get('avg_context_length', 0),
        'avg_cost_efficiency': avg_stats.get('avg_cost_efficiency', 0),
        'cache_timestamp': cache_timestamp,
    }
    badges = _build_model_badges(model_dict)
    actions = _build_model_actions(model_slug)
    metrics = _build_model_metrics(model_dict, enriched_data, stats)
    sections, sections_map = _build_model_sections(model_slug)
    view = {
        'pretitle': 'Model Detail',
        'icon': 'fas fa-robot',
        'title': model_dict.get('display_name') or model_dict.get('model_name') or model_slug,
        'subtitle': f"{model_dict.get('provider') or 'local'} · {app_count} applications",
        'badges': badges,
        'actions': actions,
    }
    return {
        'view': view,
        'metrics': metrics,
        'sections': sections,
        'model': model_dict,
        'model_record': model,
        'model_slug': model_slug,
        'enriched_data': enriched_data,
        'applications': applications,
        'app_version_counts': app_version_counts,
        'recent_apps': recent_apps,
        'stats': stats,
        'sections_map': sections_map,
        'active_page': 'models',
    }
