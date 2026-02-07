"""
Shared utility functions for report generators.

Consolidated extraction and calculation logic used by AppReportGenerator,
ToolReportGenerator, and ReportService. All functions are standalone (not methods)
and accept an optional ``filter_fn`` callback for service filtering.
"""
import re
import statistics
from typing import Dict, Any, List, Optional, Callable
from collections import Counter

from .report_constants import CWE_CATEGORIES


# ---------------------------------------------------------------------------
# Tool extraction
# ---------------------------------------------------------------------------

def extract_tools_from_services(
    services: Dict[str, Any],
    *,
    filter_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract a flat tool-results dict from nested analyzer service structures.

    Handles three common nesting patterns:
      1. ``service_data.tool_results.{tool}``
      2. ``service_data.analysis.tool_results.{tool}``
      3. ``service_data.results.{language}.{tool}`` (static-analyzer)

    Args:
        services: Mapping of service-name → service-data.
        filter_fn: Optional callback ``(services_dict) → filtered_dict`` to
                   include/exclude analyzer services (e.g. ``filter_services_data``).

    Returns:
        Flat dict mapping tool-name → tool-data.
    """
    if filter_fn is not None:
        services = filter_fn(services)

    flat_tools: Dict[str, Any] = {}

    if not isinstance(services, dict):
        return flat_tools

    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            continue

        # Try direct tool_results
        tool_results = service_data.get('tool_results', {})

        # Try nested in analysis
        if not tool_results and isinstance(service_data.get('analysis'), dict):
            tool_results = service_data['analysis'].get('tool_results', {})

        # Try nested in results -> language -> tool (static-analyzer)
        if not tool_results and isinstance(service_data.get('results'), dict):
            for _lang_key, lang_data in service_data['results'].items():
                if isinstance(lang_data, dict):
                    for tool_name, tool_data in lang_data.items():
                        if isinstance(tool_data, dict) and 'status' in tool_data:
                            flat_tools[tool_name] = tool_data

        # Add found tools
        if isinstance(tool_results, dict):
            for tool_name, tool_data in tool_results.items():
                if isinstance(tool_data, dict):
                    flat_tools[tool_name] = tool_data

    return flat_tools


# ---------------------------------------------------------------------------
# Findings extraction
# ---------------------------------------------------------------------------

def extract_findings_from_services(
    services: Dict[str, Any],
    *,
    filter_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    deduplicate: bool = True,
) -> List[Dict[str, Any]]:
    """Extract a flat list of findings from nested analyzer service structures.

    Handles three common locations:
      1. ``service_data.findings``
      2. ``service_data.analysis.findings``
      3. ``service_data.results.{lang}.{tool}.issues``

    Args:
        services: Mapping of service-name → service-data.
        filter_fn: Optional service-filter callback.
        deduplicate: If *True* (default), skip findings with duplicate
                     ``file:line:rule_id:message`` signatures.

    Returns:
        List of finding dicts, each annotated with ``service`` (and possibly
        ``tool``) keys.
    """
    if filter_fn is not None:
        services = filter_fn(services)

    all_findings: List[Dict[str, Any]] = []
    seen_signatures: set = set()

    if not isinstance(services, dict):
        return all_findings

    def _add(finding: Dict[str, Any]) -> None:
        if deduplicate:
            sig = (
                f"{finding.get('file', '')}:{finding.get('line', 0)}:"
                f"{finding.get('rule_id', '')}:{finding.get('message', '')[:50]}"
            )
            if sig in seen_signatures:
                return
            seen_signatures.add(sig)
        all_findings.append(finding)

    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            continue

        # Direct findings list
        if isinstance(service_data.get('findings'), list):
            for f in service_data['findings']:
                if isinstance(f, dict):
                    f['service'] = service_name
                    _add(f)

        # Nested in analysis
        if isinstance(service_data.get('analysis'), dict):
            analysis = service_data['analysis']
            if isinstance(analysis.get('findings'), list):
                for f in analysis['findings']:
                    if isinstance(f, dict):
                        f['service'] = service_name
                        _add(f)

        # Nested in results -> language -> tool -> issues
        if isinstance(service_data.get('results'), dict):
            for _lang_key, lang_data in service_data['results'].items():
                if isinstance(lang_data, dict):
                    for tool_name, tool_data in lang_data.items():
                        if isinstance(tool_data, dict):
                            issues = tool_data.get('issues', [])
                            if isinstance(issues, list):
                                for issue in issues:
                                    if isinstance(issue, dict):
                                        issue['tool'] = tool_name
                                        issue['service'] = service_name
                                        _add(issue)

    return all_findings


# ---------------------------------------------------------------------------
# Scientific metrics
# ---------------------------------------------------------------------------

def calculate_scientific_metrics(values: List[float]) -> Dict[str, float]:
    """Calculate scientific statistics for a list of numeric values.

    Returns a dict with: count, sum, mean, median, std_dev, variance,
    min, max, range, coefficient_of_variation.

    An empty or all-None input returns a zeroed-out dict.
    """
    clean_values = [float(v) for v in values if v is not None]

    if not clean_values:
        return {
            'count': 0,
            'sum': 0.0,
            'mean': 0.0,
            'median': 0.0,
            'std_dev': 0.0,
            'variance': 0.0,
            'min': 0.0,
            'max': 0.0,
            'range': 0.0,
            'coefficient_of_variation': 0.0,
        }

    n = len(clean_values)
    total = sum(clean_values)
    mean = total / n
    std_dev = statistics.stdev(clean_values) if n > 1 else 0.0
    variance = statistics.variance(clean_values) if n > 1 else 0.0
    median = statistics.median(clean_values)

    return {
        'count': n,
        'sum': round(total, 4),
        'mean': round(mean, 4),
        'median': round(median, 4),
        'std_dev': round(std_dev, 4),
        'variance': round(variance, 4),
        'min': round(min(clean_values), 4),
        'max': round(max(clean_values), 4),
        'range': round(max(clean_values) - min(clean_values), 4),
        'coefficient_of_variation': round((std_dev / mean) if mean > 0 else 0.0, 4),
    }


# ---------------------------------------------------------------------------
# CWE statistics
# ---------------------------------------------------------------------------

_CWE_PATTERN = re.compile(r'CWE-(\d+)', re.IGNORECASE)


def extract_cwe_statistics(
    findings: List[Dict[str, Any]],
    cwe_categories: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Extract and categorise CWE statistics from a findings list.

    Searches multiple fields (``cwe``, ``cwe_id``, ``rule_id``, ``message``,
    ``description``) for CWE identifiers using regex, supporting both
    string and integer CWE values.

    Args:
        findings: List of finding dicts.
        cwe_categories: Optional CWE-ID → name mapping; defaults to
                        ``report_constants.CWE_CATEGORIES``.

    Returns:
        Dict with ``total_cwe_findings``, ``unique_cwes``, ``cwe_counts``,
        ``by_category``, ``top_cwes``, ``top_5``.
    """
    if cwe_categories is None:
        cwe_categories = CWE_CATEGORIES

    cwe_counts: Counter = Counter()
    cwe_findings: Dict[str, List[Dict]] = {}
    findings_with_cwe = 0

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        cwe_ids: set = set()

        for field in ('cwe', 'cwe_id', 'rule_id', 'message', 'description'):
            value = finding.get(field)
            if isinstance(value, (int, float)):
                cwe_ids.add(f"CWE-{int(value)}")
            elif isinstance(value, str):
                for m in _CWE_PATTERN.finditer(value.upper()):
                    cwe_ids.add(f"CWE-{m.group(1)}")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        for m in _CWE_PATTERN.finditer(item.upper()):
                            cwe_ids.add(f"CWE-{m.group(1)}")

        if cwe_ids:
            findings_with_cwe += 1

        for cwe_id in cwe_ids:
            cwe_counts[cwe_id] += 1
            cwe_findings.setdefault(cwe_id, []).append(finding)

    # Build categorised output
    categorized: Dict[str, Dict[str, Any]] = {}
    for cwe_id, count in cwe_counts.most_common():
        category = cwe_categories.get(cwe_id, 'Other')
        if category not in categorized:
            categorized[category] = {'total': 0, 'cwes': {}}
        categorized[category]['total'] += count
        categorized[category]['cwes'][cwe_id] = count

    top_cwes = [
        {'cwe_id': cwe_id, 'count': count, 'name': cwe_categories.get(cwe_id, 'Unknown')}
        for cwe_id, count in cwe_counts.most_common(10)
    ]

    return {
        'total_cwe_findings': sum(cwe_counts.values()),
        'total_with_cwe': findings_with_cwe,
        'unique_cwes': len(cwe_counts),
        'cwe_counts': dict(cwe_counts.most_common()),
        'by_category': categorized,
        'top_cwes': top_cwes,
        'top_5': dict(cwe_counts.most_common(5)),
    }
