"""Finding analytics module.

Queries AnalysisResult directly from the database (bypassing the 50-finding
cap per app) to produce rich analytics: CWE distribution, category breakdown,
confidence×severity matrix, impact/remediation stats, and file hotspots.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from ...models import AnalysisResult
from .report_utils import extract_cwe_statistics

logger = logging.getLogger(__name__)


def collect_finding_analytics(task_ids: List[str]) -> Dict[str, Any]:
    """Build rich finding analytics from DB-level AnalysisResult rows.

    Args:
        task_ids: List of task IDs whose findings should be aggregated.

    Returns:
        Dict with keys: cwe_distribution, category_distribution,
        confidence_severity_matrix, impact_remediation, file_hotspots,
        tool_versions.
    """
    if not task_ids:
        return _empty_analytics()

    try:
        results = (
            AnalysisResult.query
            .filter(AnalysisResult.task_id.in_(task_ids))
            .all()
        )
    except Exception as e:
        logger.warning(f"Failed to query AnalysisResult for finding analytics: {e}")
        return _empty_analytics()

    if not results:
        return _empty_analytics()

    # ------------------------------------------------------------------
    # 1. CWE Distribution - reuse existing extract_cwe_statistics()
    # ------------------------------------------------------------------
    findings_for_cwe = []
    for r in results:
        finding = {
            'rule_id': r.rule_id or '',
            'description': r.description or '',
            'message': r.title or '',
        }
        # Include sarif_metadata CWE info if present
        if r.sarif_metadata:
            try:
                meta = json.loads(r.sarif_metadata)
                if 'cwe' in meta:
                    finding['cwe'] = meta['cwe']
                if 'cwe_id' in meta:
                    finding['cwe_id'] = meta['cwe_id']
            except (json.JSONDecodeError, TypeError):
                pass
        findings_for_cwe.append(finding)

    cwe_distribution = extract_cwe_statistics(findings_for_cwe)

    # ------------------------------------------------------------------
    # 2. Category Distribution
    # ------------------------------------------------------------------
    category_counts: Counter = Counter()
    rule_counts: Counter = Counter()
    for r in results:
        cat = r.category or 'uncategorized'
        category_counts[cat] += 1
        if r.rule_id:
            rule_counts[r.rule_id] += 1

    category_distribution = {
        'counts': dict(category_counts.most_common()),
        'total': sum(category_counts.values()),
        'top_rules': [
            {'rule_id': rid, 'count': cnt}
            for rid, cnt in rule_counts.most_common(15)
        ],
    }

    # ------------------------------------------------------------------
    # 3. Confidence × Severity Matrix
    # ------------------------------------------------------------------
    conf_levels = ('high', 'medium', 'low')
    sev_levels = ('critical', 'high', 'medium', 'low', 'info')
    matrix: Dict[str, Dict[str, int]] = {
        c: {s: 0 for s in sev_levels} for c in conf_levels
    }
    unknown_conf = {s: 0 for s in sev_levels}

    for r in results:
        sev = r.severity.value.lower() if r.severity else 'info'
        if sev not in sev_levels:
            sev = 'info'
        conf = (r.confidence or '').lower()
        if conf in conf_levels:
            matrix[conf][sev] += 1
        else:
            unknown_conf[sev] += 1

    confidence_severity_matrix = {
        'matrix': matrix,
        'unknown_confidence': unknown_conf,
        'severity_levels': list(sev_levels),
        'confidence_levels': list(conf_levels),
    }

    # ------------------------------------------------------------------
    # 4. Impact & Remediation
    # ------------------------------------------------------------------
    impact_scores = [r.impact_score for r in results if r.impact_score is not None]
    business_impacts: Counter = Counter()
    remediation_efforts: Counter = Counter()
    quick_wins = 0

    for r in results:
        if r.business_impact:
            business_impacts[r.business_impact.lower()] += 1
        if r.remediation_effort:
            remediation_efforts[r.remediation_effort.lower()] += 1
        # Quick win: high/critical severity + low remediation effort
        if r.remediation_effort and r.remediation_effort.lower() == 'low':
            sev = r.severity.value.lower() if r.severity else ''
            if sev in ('high', 'critical'):
                quick_wins += 1

    # Impact score distribution buckets
    impact_buckets = {'0-2': 0, '2-4': 0, '4-6': 0, '6-8': 0, '8-10': 0}
    for score in impact_scores:
        if score < 2:
            impact_buckets['0-2'] += 1
        elif score < 4:
            impact_buckets['2-4'] += 1
        elif score < 6:
            impact_buckets['4-6'] += 1
        elif score < 8:
            impact_buckets['6-8'] += 1
        else:
            impact_buckets['8-10'] += 1

    impact_remediation = {
        'impact_score': {
            'mean': round(sum(impact_scores) / len(impact_scores), 2) if impact_scores else None,
            'count': len(impact_scores),
            'distribution': impact_buckets,
        },
        'business_impact': dict(business_impacts.most_common()),
        'remediation_effort': dict(remediation_efforts.most_common()),
        'quick_wins': quick_wins,
        'has_data': bool(impact_scores or business_impacts or remediation_efforts),
    }

    # ------------------------------------------------------------------
    # 5. File Hotspots (top 15 files by finding count)
    # ------------------------------------------------------------------
    file_counter: Counter = Counter()
    file_severity: Dict[str, Dict[str, int]] = {}

    for r in results:
        fp = r.file_path
        if not fp:
            continue
        file_counter[fp] += 1
        if fp not in file_severity:
            file_severity[fp] = {s: 0 for s in sev_levels}
        sev = r.severity.value.lower() if r.severity else 'info'
        if sev in sev_levels:
            file_severity[fp][sev] += 1

    file_hotspots = [
        {
            'file': fp,
            'count': cnt,
            'severity': file_severity.get(fp, {}),
        }
        for fp, cnt in file_counter.most_common(15)
    ]

    # ------------------------------------------------------------------
    # 6. Tool Versions
    # ------------------------------------------------------------------
    tool_versions: Dict[str, Optional[str]] = {}
    for r in results:
        if r.tool_name and r.tool_name not in tool_versions:
            tool_versions[r.tool_name] = r.tool_version

    return {
        'cwe_distribution': cwe_distribution,
        'category_distribution': category_distribution,
        'confidence_severity_matrix': confidence_severity_matrix,
        'impact_remediation': impact_remediation,
        'file_hotspots': file_hotspots,
        'tool_versions': tool_versions,
        'total_results_analyzed': len(results),
    }


def _empty_analytics() -> Dict[str, Any]:
    """Return an empty analytics dict for when there is no data."""
    return {
        'cwe_distribution': {
            'total_cwe_findings': 0,
            'total_with_cwe': 0,
            'unique_cwes': 0,
            'cwe_counts': {},
            'by_category': {},
            'top_cwes': [],
            'top_5': {},
        },
        'category_distribution': {
            'counts': {},
            'total': 0,
            'top_rules': [],
        },
        'confidence_severity_matrix': {
            'matrix': {c: {s: 0 for s in ('critical', 'high', 'medium', 'low', 'info')}
                       for c in ('high', 'medium', 'low')},
            'unknown_confidence': {s: 0 for s in ('critical', 'high', 'medium', 'low', 'info')},
            'severity_levels': ['critical', 'high', 'medium', 'low', 'info'],
            'confidence_levels': ['high', 'medium', 'low'],
        },
        'impact_remediation': {
            'impact_score': {'mean': None, 'count': 0, 'distribution': {}},
            'business_impact': {},
            'remediation_effort': {},
            'quick_wins': 0,
            'has_data': False,
        },
        'file_hotspots': [],
        'tool_versions': {},
        'total_results_analyzed': 0,
    }
