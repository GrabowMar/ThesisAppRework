"""Result summary utilities.

Shared helpers for aggregating findings and severity counts across services.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, Mapping, Tuple

_DEFAULT_SEVERITY = "unknown"
_DEFAULT_TOOL = "unknown"


def _coerce_severity(value: Any, *, normalise: bool) -> str:
    if isinstance(value, str):
        text = value.strip()
    elif value is None:
        text = _DEFAULT_SEVERITY
    else:
        text = str(value)
    if not text:
        text = _DEFAULT_SEVERITY
    return text.lower() if normalise else text


def _coerce_tool(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
    elif value is None:
        text = _DEFAULT_TOOL
    else:
        text = str(value)
    return text or _DEFAULT_TOOL


def count_findings_by_severity(
    findings: Iterable[Mapping[str, Any]],
    *,
    normalise: bool = False,
) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for finding in findings:
        if not isinstance(finding, Mapping):
            continue
        severity = finding.get("severity", _DEFAULT_SEVERITY)
        counter[_coerce_severity(severity, normalise=normalise)] += 1
    return dict(counter)


def count_findings_by_tool(findings: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for finding in findings:
        if not isinstance(finding, Mapping):
            continue
        tool = finding.get("tool") or finding.get("tool_name") or _DEFAULT_TOOL
        counter[_coerce_tool(tool)] += 1
    return dict(counter)


def summarise_findings(
    findings: Iterable[Mapping[str, Any]],
    service_summaries: Iterable[Mapping[str, Any]],
    tool_results: Mapping[str, Mapping[str, Any]],
    *,
    normalise_severity: bool = False,
) -> Tuple[int, Dict[str, int], Dict[str, int]]:
    severity_counts = Counter(count_findings_by_severity(findings, normalise=normalise_severity))
    findings_by_tool = Counter(count_findings_by_tool(findings))
    total_findings = sum(severity_counts.values())

    if total_findings == 0:
        for summary in service_summaries:
            if not isinstance(summary, Mapping):
                continue
            total_value = summary.get("total_findings") or summary.get("total_issues")
            try:
                total_findings += int(total_value or 0)
            except (TypeError, ValueError):
                pass

            by_severity = summary.get("by_severity")
            if isinstance(by_severity, Mapping):
                for severity, count in by_severity.items():
                    try:
                        increment = int(count)
                    except (TypeError, ValueError):
                        continue
                    key = _coerce_severity(severity, normalise=normalise_severity)
                    severity_counts[key] += increment

            by_tool = summary.get("by_tool")
            if isinstance(by_tool, Mapping):
                for tool_name, count in by_tool.items():
                    try:
                        increment = int(count)
                    except (TypeError, ValueError):
                        continue
                    name = _coerce_tool(tool_name)
                    findings_by_tool[name] += increment

    if total_findings == 0:
        for meta in tool_results.values():
            if not isinstance(meta, Mapping):
                continue
            try:
                total_findings += int(meta.get("total_issues") or 0)
            except (TypeError, ValueError):
                continue

    return total_findings, dict(severity_counts), dict(findings_by_tool)


__all__ = [
    "count_findings_by_severity",
    "count_findings_by_tool",
    "summarise_findings",
]
