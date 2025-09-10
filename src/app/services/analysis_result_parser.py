"""Unified analysis tool result parsing utilities.

Provides normalization helpers to turn raw tool JSON fragments (bandit, pylint,
etc.) into the canonical finding dictionaries used by the UI / API.

Contract (output finding dict keys):
  tool: str              # tool name e.g. "bandit"
  severity: str          # normalized severity: error|warning|medium|low|info|unknown
  title: str             # short human readable summary
  category: str          # rule/test/category identifier
  file_path: str         # relative file path inside generated app sources
  line_number: int|None
  column: int|None
  end_line: int|None
  end_column: int|None
  message: str           # descriptive message
  raw_data: dict         # original tool record for advanced / drill‑down

Low level mapping rules intentionally kept pure (no DB / Flask context) so they
can be unit tested in isolation.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

SEVERITY_MAP_GENERIC = {
    # bandit maps mixed case values; pylint numeric -> handled separately
    'HIGH': 'error',
    'MEDIUM': 'medium',
    'LOW': 'low',
    'ERROR': 'error',
    'WARN': 'warning',
    'WARNING': 'warning',
    'INFO': 'info'
}


def _normalize_severity(value: Any) -> str:
    if value is None:
        return 'unknown'
    if isinstance(value, (int, float)):
        # Pylint numeric: 0 (convention/info) -> info, 1 warning, 2 error, 3 fatal (treat as error)
        mapping = {0: 'info', 1: 'warning', 2: 'error', 3: 'error'}
        return mapping.get(int(value), 'unknown')
    upper = str(value).strip().upper()
    return SEVERITY_MAP_GENERIC.get(upper, upper.lower() if upper else 'unknown')


def parse_bandit_results(bandit_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse bandit JSON structure into canonical findings list.

    bandit_json expected structure (subset):
      {
        "results": [ { "filename": str, "issue_severity": str, ... } ],
        "metrics": { ... }
      }
    """
    findings: List[Dict[str, Any]] = []
    for issue in bandit_json.get('results', [])[:200]:  # safeguard limit
        findings.append({
            'tool': 'bandit',
            'severity': _normalize_severity(issue.get('issue_severity')),
            'title': issue.get('issue_text', '')[:200].strip(),
            'category': issue.get('test_name') or issue.get('test_id') or 'bandit',
            'file_path': issue.get('filename', ''),
            'line_number': issue.get('line_number'),
            'column': None,
            'end_line': None,
            'end_column': None,
            'message': issue.get('issue_text', '').strip(),
            'cwe': (issue.get('issue_cwe') or {}).get('id'),
            'confidence': issue.get('issue_confidence'),
            'more_info': issue.get('more_info'),
            'raw_data': issue,
        })
    return findings


def parse_pylint_messages(pylint_issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse iterable of pylint issue dicts.

    Expected keys (subset): 'type', 'message', 'symbol', 'path', 'line', 'column',
    plus any extras (kept in raw_data).
    """
    results: List[Dict[str, Any]] = []
    for issue in list(pylint_issues)[:400]:  # guard large lists
        severity = issue.get('type') or issue.get('message-id')
        results.append({
            'tool': 'pylint',
            'severity': _normalize_severity(severity),
            'title': issue.get('message', '')[:160].strip(),
            'category': issue.get('symbol') or issue.get('message-id') or 'pylint',
            'file_path': issue.get('path') or issue.get('file_path') or issue.get('filename', ''),
            'line_number': issue.get('line') or issue.get('line_number'),
            'column': issue.get('column'),
            'end_line': issue.get('endLine') or issue.get('end_line'),
            'end_column': issue.get('endColumn') or issue.get('end_column'),
            'message': issue.get('message', '').strip(),
            'message_id': issue.get('message-id') or issue.get('message_id'),
            'raw_data': issue,
        })
    return results


def merge_findings(*lists: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for seq in lists:
        if not seq:
            continue
        merged.extend(seq)
    return merged


__all__ = [
    'parse_bandit_results',
    'parse_pylint_messages',
    'merge_findings'
]
