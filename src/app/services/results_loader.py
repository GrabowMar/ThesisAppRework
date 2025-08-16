"""
Results Loader Service
======================

Utility helpers to locate and load analyzer JSON result files produced by
the containerized analyzer services under analyzer/results/.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


ANALYSIS_TYPES = ["security", "performance", "static", "dynamic", "ai"]


def _project_root() -> Path:
    # src/app/services -> project root
    return Path(__file__).resolve().parents[3]


def _results_dir() -> Path:
    return _project_root() / "analyzer" / "results"


def _parse_timestamp_from_name(name: str) -> Optional[datetime]:
    # Example: anthropic_claude-3.7-sonnet_app1_security_20250816_163340.json
    try:
        parts = name.rsplit("_", 2)
        if len(parts) >= 2:
            datepart, timepart_with_ext = parts[-2], parts[-1]
            timepart = timepart_with_ext.split(".")[0]
            return datetime.strptime(f"{datepart}_{timepart}", "%Y%m%d_%H%M%S")
    except Exception:
        return None
    return None


def _match_file(model_slug: str, app_number: int, analysis_type: str, path: Path) -> bool:
    stem = path.stem
    return (
        f"{model_slug}_app{app_number}_" in stem and f"_{analysis_type}_" in stem
    )


def find_latest_for_type(model_slug: str, app_number: int, analysis_type: str) -> Optional[Dict[str, Any]]:
    """Find and load the latest JSON result for a given model/app/type."""
    try:
        results_dir = _results_dir()
        if not results_dir.exists():
            return None
        candidates: List[Tuple[datetime, Path]] = []
        for p in results_dir.glob("*.json"):
            if _match_file(model_slug, app_number, analysis_type, p):
                ts = _parse_timestamp_from_name(p.name) or datetime.min
                candidates.append((ts, p))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, latest = candidates[0]
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "file": str(latest),
            "timestamp": _parse_timestamp_from_name(latest.name),
            "type": analysis_type,
            "model_slug": model_slug,
            "app_number": app_number,
            "data": data,
        }
    except Exception as e:
        logger.warning(f"Failed to load result for {model_slug} app {app_number} {analysis_type}: {e}")
        return None


def find_latest_results(model_slug: str, app_number: int, types: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Return a dict of analysis_type -> loaded result object for latest files."""
    res: Dict[str, Dict[str, Any]] = {}
    for t in (types or ANALYSIS_TYPES):
        item = find_latest_for_type(model_slug, app_number, t)
        if item is not None:
            res[t] = item
    return res


def summarize_result(analysis_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a compact summary per analysis type for UI badges/cards."""
    try:
        data = payload.get("data") or {}
        if analysis_type == "security":
            # Expect tool-specific sections
            bandit = (data.get("bandit") or {}).get("results", [])
            safety = (data.get("safety") or {}).get("vulnerabilities", [])
            zap_alerts = 0
            zap = data.get("zap") or {}
            if isinstance(zap, dict) and zap.get("site"):
                try:
                    zap_alerts = len((zap["site"][0] or {}).get("alerts", []) or [])
                except Exception:
                    zap_alerts = 0
            return {
                "issues_total": len(bandit) + len(safety) + zap_alerts,
                "bandit": len(bandit),
                "safety": len(safety),
                "zap": zap_alerts,
            }
        if analysis_type == "performance":
            metrics = data.get("metrics") or {}
            return {
                "rps": metrics.get("requests_per_second"),
                "p95": metrics.get("latency_p95"),
                "failures": metrics.get("failures", 0),
            }
        if analysis_type == "static":
            semgrep = (data.get("semgrep") or {}).get("findings", [])
            eslint = 0
            es = data.get("eslint")
            if isinstance(es, list):
                eslint = sum(len(f.get("messages", [])) for f in es)
            pylint = len(data.get("pylint") or []) if isinstance(data.get("pylint"), list) else 0
            return {"issues_total": len(semgrep) + eslint + pylint, "semgrep": len(semgrep), "eslint": eslint, "pylint": pylint}
        if analysis_type == "dynamic":
            zap_alerts = 0
            zap = data.get("zap") or data
            if isinstance(zap, dict) and zap.get("site"):
                try:
                    zap_alerts = len((zap["site"][0] or {}).get("alerts", []) or [])
                except Exception:
                    zap_alerts = 0
            return {"alerts": zap_alerts}
        if analysis_type == "ai":
            insights = data.get("insights") or []
            return {"insights": len(insights)}
    except Exception:
        pass
    return {}
