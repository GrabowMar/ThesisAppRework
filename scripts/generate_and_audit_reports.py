#!/usr/bin/env python3
"""Generate all reports and audit their factuality.

Phases:
  1. Setup — Flask app context, discover model/template slugs from DB
  2. Generate — 10 model_analysis + 30 template_comparison + 1 tool_analysis + 1 generation_analytics
  3. Audit — universal + type-specific validators, cross-reference DB
  4. Output — console summary + scripts/audit_results.json

Usage:
    cd ThesisAppRework
    python3 scripts/generate_and_audit_reports.py
"""

import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Set up path so we can import from src/
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models import Report
from app.models.core import GeneratedApplication
from app.services.service_locator import ServiceLocator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEVERITY_KEYS = {"critical", "high", "medium", "low", "info"}
VALID_ANALYZER_CATEGORIES = {"static", "dynamic", "performance", "ai"}
FLOAT_TOLERANCE = 0.1  # tolerance for float comparisons

# Build set of known tool names from report_constants + ANALYZER_CATEGORIES
try:
    from app.services.reports.report_constants import KNOWN_TOOLS
    from app.services.report_service import ANALYZER_CATEGORIES
    ALL_KNOWN_TOOLS: set = set(KNOWN_TOOLS.keys())
    for cat_info in ANALYZER_CATEGORIES.values():
        ALL_KNOWN_TOOLS.update(cat_info["tools"].keys())
except ImportError:
    ALL_KNOWN_TOOLS = set()
    ANALYZER_CATEGORIES = {}


# ---------------------------------------------------------------------------
# Audit result helpers
# ---------------------------------------------------------------------------

class AuditCheck:
    """A single audit check result."""

    def __init__(self, name: str, status: str, detail: str = ""):
        self.name = name
        self.status = status  # PASS / WARN / FAIL
        self.detail = detail

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


class ReportAudit:
    """Audit results for a single report."""

    def __init__(self, report_id: str, report_type: str, title: str):
        self.report_id = report_id
        self.report_type = report_type
        self.title = title
        self.checks: List[AuditCheck] = []
        self.generation_time: float = 0.0
        self.generation_error: Optional[str] = None

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(AuditCheck(name, status, detail))

    def pass_(self, name: str, detail: str = "") -> None:
        self.add(name, "PASS", detail)

    def warn(self, name: str, detail: str = "") -> None:
        self.add(name, "WARN", detail)

    def fail(self, name: str, detail: str = "") -> None:
        self.add(name, "FAIL", detail)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARN")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "title": self.title,
            "generation_time": round(self.generation_time, 2),
            "generation_error": self.generation_error,
            "totals": {
                "pass": self.pass_count,
                "warn": self.warn_count,
                "fail": self.fail_count,
            },
            "checks": [c.to_dict() for c in self.checks],
        }


def close_enough(a: float, b: float, tol: float = FLOAT_TOLERANCE) -> bool:
    """Compare two floats with tolerance."""
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# Phase 1: Setup & Discovery
# ---------------------------------------------------------------------------

def discover_slugs() -> Tuple[List[str], List[str]]:
    """Discover all model_slugs and template_slugs from GeneratedApplication table."""
    model_rows = (
        db.session.query(GeneratedApplication.model_slug)
        .distinct()
        .order_by(GeneratedApplication.model_slug)
        .all()
    )
    template_rows = (
        db.session.query(GeneratedApplication.template_slug)
        .distinct()
        .order_by(GeneratedApplication.template_slug)
        .all()
    )
    model_slugs = [r[0] for r in model_rows if r[0]]
    template_slugs = [r[0] for r in template_rows if r[0]]
    return model_slugs, template_slugs


def print_baseline(model_slugs: List[str], template_slugs: List[str]) -> None:
    """Print baseline discovery stats."""
    total_apps = GeneratedApplication.query.count()
    print(f"  Total applications:  {total_apps}")
    print(f"  Distinct models:     {len(model_slugs)}")
    print(f"  Distinct templates:  {len(template_slugs)}")
    print(f"  Models:  {', '.join(model_slugs)}")
    print(f"  Expected reports:    {len(model_slugs)} + {len(template_slugs)} + 2 = {len(model_slugs) + len(template_slugs) + 2}")
    print()


# ---------------------------------------------------------------------------
# Phase 2: Generate reports
# ---------------------------------------------------------------------------

def generate_all_reports(
    report_service: Any,
    model_slugs: List[str],
    template_slugs: List[str],
) -> List[Tuple[Report, float, Optional[str]]]:
    """Generate all reports, returning list of (report, elapsed_seconds, error_or_None)."""
    results: List[Tuple[Report, float, Optional[str]]] = []

    def _gen(report_type: str, config: Dict[str, Any], label: str) -> None:
        print(f"  Generating [{report_type}] {label} ... ", end="", flush=True)
        t0 = time.time()
        try:
            report = report_service.generate_report(
                report_type=report_type,
                config=config,
                expires_in_days=365,
            )
            elapsed = time.time() - t0
            if report.status == "completed":
                print(f"OK ({elapsed:.1f}s)")
                results.append((report, elapsed, None))
            else:
                err = report.error_message or "unknown error"
                print(f"FAILED: {err} ({elapsed:.1f}s)")
                results.append((report, elapsed, err))
        except Exception as e:
            elapsed = time.time() - t0
            print(f"EXCEPTION: {e} ({elapsed:.1f}s)")
            results.append((None, elapsed, str(e)))  # type: ignore[arg-type]

    # 1) model_analysis — one per model
    for slug in model_slugs:
        _gen("model_analysis", {"model_slug": slug}, slug)

    # 2) template_comparison — one per template
    for slug in template_slugs:
        _gen("template_comparison", {"template_slug": slug}, slug)

    # 3) tool_analysis — global
    _gen("tool_analysis", {}, "all tools")

    # 4) generation_analytics — global with large lookback
    _gen("generation_analytics", {"days_back": 365}, "generation analytics")

    return results


# ---------------------------------------------------------------------------
# Phase 3: Audit — universal validators
# ---------------------------------------------------------------------------

def audit_universal(data: Dict[str, Any], audit: ReportAudit, expected_type: str) -> None:
    """Run universal validation checks applicable to all report types."""

    # report_type matches
    actual_type = data.get("report_type")
    if actual_type == expected_type:
        audit.pass_("report_type", f"matches: {expected_type}")
    elif actual_type is None:
        # generation_analytics doesn't always have report_type key
        if expected_type == "generation_analytics":
            audit.warn("report_type", "key missing (generation_analytics may omit it)")
        else:
            audit.fail("report_type", f"missing, expected {expected_type}")
    else:
        audit.fail("report_type", f"mismatch: got {actual_type}, expected {expected_type}")

    # generated_at is valid ISO datetime
    gen_at = data.get("generated_at")
    if gen_at:
        try:
            datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
            audit.pass_("generated_at", gen_at)
        except (ValueError, AttributeError):
            audit.fail("generated_at", f"invalid datetime: {gen_at}")
    else:
        # generation_analytics may not have generated_at
        if expected_type == "generation_analytics":
            audit.pass_("generated_at", "not required for generation_analytics")
        else:
            audit.warn("generated_at", "missing")

    # Severity keys present in summary.severity_breakdown (if summary exists)
    summary = data.get("summary", {})
    sev_breakdown = summary.get("severity_breakdown", {})
    if sev_breakdown:
        missing_sev = SEVERITY_KEYS - set(sev_breakdown.keys())
        if not missing_sev:
            audit.pass_("severity_keys", "all present")
        else:
            audit.fail("severity_keys", f"missing: {missing_sev}")

        # All severity values are non-negative integers
        bad_values = []
        for key in SEVERITY_KEYS:
            val = sev_breakdown.get(key)
            if val is not None:
                if not isinstance(val, int) or val < 0:
                    bad_values.append(f"{key}={val}")
        if bad_values:
            audit.fail("severity_values", f"bad values: {', '.join(bad_values)}")
        else:
            audit.pass_("severity_values", "all non-negative integers")

    # Percentage fields in [0, 100]
    _check_percentage_fields(data, audit)


def _check_percentage_fields(data: Any, audit: ReportAudit, path: str = "") -> None:
    """Recursively check that keys ending in _rate or _percent are in [0, 100]."""
    bad = []
    _collect_bad_percentages(data, bad, path)
    if bad:
        # Only report first 10
        detail = "; ".join(bad[:10])
        if len(bad) > 10:
            detail += f" ... and {len(bad) - 10} more"
        audit.warn("percentage_bounds", detail)
    else:
        audit.pass_("percentage_bounds", "all in [0, 100] or not present")


def _collect_bad_percentages(data: Any, bad: List[str], path: str) -> None:
    """Recursively collect percentage fields outside [0, 100]."""
    if isinstance(data, dict):
        for key, val in data.items():
            full_key = f"{path}.{key}" if path else key
            if (key.endswith("_rate") or key.endswith("_percent")) and isinstance(val, (int, float)):
                if val < -FLOAT_TOLERANCE or val > 100 + FLOAT_TOLERANCE:
                    bad.append(f"{full_key}={val}")
            _collect_bad_percentages(val, bad, full_key)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _collect_bad_percentages(item, bad, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# Phase 3: Audit — model_analysis validators
# ---------------------------------------------------------------------------

def audit_model_analysis(data: Dict[str, Any], audit: ReportAudit, config: Dict[str, Any]) -> None:
    """Validate model_analysis report data."""
    expected_slug = config.get("model_slug", "")

    # model_slug in data matches requested
    actual_slug = data.get("model_slug", "")
    if actual_slug == expected_slug:
        audit.pass_("model_slug_match", expected_slug)
    else:
        audit.fail("model_slug_match", f"got {actual_slug}, expected {expected_slug}")

    apps = data.get("apps", [])
    apps_count = data.get("apps_count", 0)

    # apps_count == len(apps)
    if apps_count == len(apps):
        audit.pass_("apps_count", f"{apps_count}")
    else:
        audit.fail("apps_count", f"apps_count={apps_count}, len(apps)={len(apps)}")

    # All apps[].model_slug match
    mismatched = [a.get("app_number") for a in apps if a.get("model_slug") != expected_slug]
    if not mismatched:
        audit.pass_("apps_model_slug", "all match")
    else:
        audit.fail("apps_model_slug", f"mismatched app_numbers: {mismatched[:10]}")

    # summary.total_findings == sum of apps[].findings_count
    summary = data.get("summary", {})
    total_findings = summary.get("total_findings", 0)
    sum_findings = sum(a.get("findings_count", 0) for a in apps)
    if total_findings == sum_findings:
        audit.pass_("total_findings_sum", f"{total_findings}")
    else:
        audit.fail("total_findings_sum", f"summary.total_findings={total_findings}, sum(findings_count)={sum_findings}")

    # Each app: findings_count >= len(findings) (list capped at 50)
    bad_caps = []
    for a in apps:
        fc = a.get("findings_count", 0)
        fl = len(a.get("findings", []))
        if fc < fl:
            bad_caps.append(f"app{a.get('app_number')}: count={fc} < len={fl}")
    if bad_caps:
        audit.fail("findings_cap", "; ".join(bad_caps[:5]))
    else:
        audit.pass_("findings_cap", "all findings_count >= len(findings)")

    # Severity breakdown sums
    sev_breakdown = summary.get("severity_breakdown", {})
    sev_sum = sum(sev_breakdown.get(k, 0) for k in SEVERITY_KEYS)
    # severity_breakdown sum should >= total_findings (severity counts come from DB, findings_count also from DB)
    # They should be consistent
    unclassified = summary.get("unclassified_findings", 0) or 0
    if sev_sum >= total_findings or close_enough(sev_sum, total_findings, 1):
        audit.pass_("severity_sum", f"sev_sum={sev_sum}, total_findings={total_findings}")
    elif sev_sum + unclassified == total_findings:
        audit.pass_("severity_sum", f"sev_sum={sev_sum} + unclassified={unclassified} == total_findings={total_findings}")
    else:
        audit.warn("severity_sum", f"sev_sum={sev_sum} < total_findings={total_findings} (unclassified={unclassified})")

    # Scientific metrics: mean between min/max, stddev >= 0
    sci = data.get("scientific_metrics", {})
    _audit_scientific_metrics(sci, audit)

    # LOC metrics: total_loc consistency
    loc = data.get("loc_metrics", {})
    if loc:
        total_loc = loc.get("total_loc", 0)
        component_sum = (
            loc.get("python_loc", 0)
            + loc.get("javascript_loc", 0)
            + loc.get("jsx_loc", 0)
            + loc.get("css_loc", 0)
            + loc.get("other_loc", 0)
        )
        if total_loc > 0 and component_sum > 0:
            if close_enough(total_loc, component_sum, 2):
                audit.pass_("loc_total", f"total={total_loc}, components={component_sum}")
            else:
                audit.warn("loc_total", f"total={total_loc} != components_sum={component_sum}")
        else:
            audit.pass_("loc_total", f"total_loc={total_loc} (components may be 0)")

    # Tools in tools_statistics are known
    tools_stats = data.get("tools_statistics", {})
    if tools_stats and ALL_KNOWN_TOOLS:
        unknown = set(tools_stats.keys()) - ALL_KNOWN_TOOLS
        if unknown:
            audit.warn("known_tools", f"unknown tools: {unknown}")
        else:
            audit.pass_("known_tools", f"all {len(tools_stats)} tools known")

    # Quantitative metrics structure
    qm = data.get("quantitative_metrics", {})
    if qm:
        _audit_quantitative_metrics(qm, audit)

    # Scatter data entries
    scatter = data.get("scatter_data", [])
    if scatter:
        bad_scatter = []
        for entry in scatter:
            if entry.get("loc", 0) < 0:
                bad_scatter.append(f"app{entry.get('app_number')}: loc<0")
            if entry.get("findings", 0) < 0:
                bad_scatter.append(f"app{entry.get('app_number')}: findings<0")
        if bad_scatter:
            audit.fail("scatter_data", "; ".join(bad_scatter[:5]))
        else:
            audit.pass_("scatter_data", f"{len(scatter)} entries valid")

    # Cross-ref: app count vs DB
    from app.utils.slug_utils import generate_slug_variants
    slug_variants = generate_slug_variants(expected_slug)
    db_app_count = GeneratedApplication.query.filter(
        GeneratedApplication.model_slug.in_(slug_variants)
    ).count()
    if apps_count <= db_app_count:
        audit.pass_("xref_app_count", f"report={apps_count}, db={db_app_count}")
    else:
        audit.warn("xref_app_count", f"report={apps_count} > db={db_app_count}")

    # Cross-ref: task count
    from app.models.analysis_models import AnalysisTask
    from app.constants import AnalysisStatus
    db_task_count = AnalysisTask.query.filter(
        AnalysisTask.target_model.in_(slug_variants),
        AnalysisTask.status.in_([
            AnalysisStatus.COMPLETED,
            AnalysisStatus.PARTIAL_SUCCESS,
            AnalysisStatus.FAILED,
            AnalysisStatus.CANCELLED,
        ]),
        db.or_(
            AnalysisTask.is_main_task.is_(True),
            AnalysisTask.parent_task_id.is_(None),
        ),
    ).count()
    report_tasks = data.get("total_tasks", 0)
    if report_tasks == db_task_count:
        audit.pass_("xref_task_count", f"{report_tasks}")
    else:
        audit.warn("xref_task_count", f"report={report_tasks}, db={db_task_count}")


def _audit_scientific_metrics(sci: Dict[str, Any], audit: ReportAudit) -> None:
    """Validate scientific_metrics sub-object."""
    if not sci:
        audit.pass_("scientific_metrics", "empty (no data)")
        return

    bad = []
    for metric_name, metric_data in sci.items():
        if not isinstance(metric_data, dict):
            continue
        mean = metric_data.get("mean")
        mn = metric_data.get("min")
        mx = metric_data.get("max")
        sd = metric_data.get("stddev")
        median = metric_data.get("median")

        if mean is not None and mn is not None and mx is not None:
            if not (mn - FLOAT_TOLERANCE <= mean <= mx + FLOAT_TOLERANCE):
                bad.append(f"{metric_name}: mean={mean} outside [{mn}, {mx}]")
        if sd is not None and sd < -FLOAT_TOLERANCE:
            bad.append(f"{metric_name}: stddev={sd} < 0")
        if median is not None and mn is not None and mx is not None:
            if not (mn - FLOAT_TOLERANCE <= median <= mx + FLOAT_TOLERANCE):
                bad.append(f"{metric_name}: median={median} outside [{mn}, {mx}]")

    if bad:
        audit.fail("scientific_metrics", "; ".join(bad[:5]))
    else:
        audit.pass_("scientific_metrics", f"{len(sci)} metrics valid")


def _audit_quantitative_metrics(qm: Dict[str, Any], audit: ReportAudit) -> None:
    """Validate quantitative_metrics structure."""
    expected_sections = ["generation", "docker", "performance", "ai_analysis", "security"]
    present = [s for s in expected_sections if s in qm]
    audit.pass_("qm_structure", f"sections present: {present}")

    for section in present:
        sec_data = qm[section]
        if isinstance(sec_data, dict) and sec_data.get("available"):
            audit.pass_(f"qm_{section}", "available=True, data present")
        elif isinstance(sec_data, dict) and not sec_data.get("available"):
            audit.pass_(f"qm_{section}", "available=False (no data)")
        else:
            audit.warn(f"qm_{section}", f"unexpected structure: {type(sec_data)}")


# ---------------------------------------------------------------------------
# Phase 3: Audit — template_comparison validators
# ---------------------------------------------------------------------------

def audit_template_comparison(data: Dict[str, Any], audit: ReportAudit, config: Dict[str, Any]) -> None:
    """Validate template_comparison report data."""
    expected_slug = config.get("template_slug", "")

    # template_slug matches
    actual_slug = data.get("template_slug", "")
    if actual_slug == expected_slug:
        audit.pass_("template_slug_match", expected_slug)
    else:
        audit.fail("template_slug_match", f"got {actual_slug}, expected {expected_slug}")

    models = data.get("models", [])
    models_count = data.get("models_count", 0)

    # models_count == len(models)
    if models_count == len(models):
        audit.pass_("models_count", f"{models_count}")
    else:
        audit.fail("models_count", f"models_count={models_count}, len(models)={len(models)}")

    # summary.total_findings == sum of models[].findings_count
    summary = data.get("summary", {})
    total_findings = summary.get("total_findings", 0)
    sum_findings = sum(m.get("findings_count", 0) for m in models)
    if total_findings == sum_findings:
        audit.pass_("total_findings_sum", f"{total_findings}")
    else:
        audit.fail("total_findings_sum", f"summary={total_findings}, sum={sum_findings}")

    # Rankings: ranks sequential if present
    rankings = data.get("rankings", {})
    if rankings:
        ranked_list = rankings.get("by_score", rankings.get("overall", []))
        if isinstance(ranked_list, list) and ranked_list:
            ranks = [r.get("rank") for r in ranked_list if isinstance(r, dict) and "rank" in r]
            if ranks:
                expected_ranks = list(range(1, len(ranks) + 1))
                if ranks == expected_ranks:
                    audit.pass_("rankings_sequential", f"1..{len(ranks)}")
                else:
                    audit.warn("rankings_sequential", f"ranks={ranks}, expected={expected_ranks}")
            else:
                audit.pass_("rankings_sequential", "no ranked entries with rank field")
        else:
            audit.pass_("rankings_sequential", "no ranked list found")
    else:
        audit.pass_("rankings", "no rankings section")

    # Code density: issues_per_100_loc consistency
    code_density = data.get("code_density", {})
    if isinstance(code_density, dict):
        per_model = code_density.get("per_model", code_density.get("models", {}))
        if isinstance(per_model, dict):
            bad_density = []
            for slug, cd in per_model.items():
                if not isinstance(cd, dict):
                    continue
                loc = cd.get("total_loc", 0) or cd.get("loc", 0)
                findings = cd.get("findings_count", 0) or cd.get("findings", 0) or cd.get("total_findings", 0)
                reported_density = cd.get("issues_per_100_loc", None)
                if loc > 0 and reported_density is not None:
                    expected_density = (findings / loc) * 100
                    if not close_enough(reported_density, expected_density, 0.5):
                        bad_density.append(f"{slug}: reported={reported_density}, expected={expected_density:.2f}")
            if bad_density:
                audit.warn("code_density", "; ".join(bad_density[:5]))
            else:
                audit.pass_("code_density", "consistent")
        else:
            audit.pass_("code_density", "no per_model data")
    else:
        audit.pass_("code_density", "no code_density section")

    # Radar chart: all values 0-100, exactly 5 axes
    radar = data.get("radar_chart_data", {})
    if radar and isinstance(radar, dict):
        axes = radar.get("axes", [])
        datasets = radar.get("datasets", [])
        if len(axes) != 5:
            audit.fail("radar_axes", f"expected 5 axes, got {len(axes)}")
        else:
            audit.pass_("radar_axes", f"{axes}")

        bad_radar = []
        for ds in datasets:
            values = ds.get("values", [])
            slug = ds.get("model_slug", "?")
            if len(values) != 5:
                bad_radar.append(f"{slug}: {len(values)} values (expected 5)")
            for v in values:
                if isinstance(v, (int, float)) and (v < -FLOAT_TOLERANCE or v > 100 + FLOAT_TOLERANCE):
                    bad_radar.append(f"{slug}: value {v} outside [0,100]")
        if bad_radar:
            audit.fail("radar_values", "; ".join(bad_radar[:5]))
        else:
            audit.pass_("radar_values", f"{len(datasets)} datasets valid")
    else:
        audit.pass_("radar_chart", "no radar_chart_data")

    # Cross-ref: model count vs DB
    db_model_count = (
        db.session.query(GeneratedApplication.model_slug)
        .filter(GeneratedApplication.template_slug == expected_slug)
        .distinct()
        .count()
    )
    if models_count <= db_model_count:
        audit.pass_("xref_model_count", f"report={models_count}, db_distinct={db_model_count}")
    else:
        audit.warn("xref_model_count", f"report={models_count} > db={db_model_count}")


# ---------------------------------------------------------------------------
# Phase 3: Audit — tool_analysis validators
# ---------------------------------------------------------------------------

def audit_tool_analysis(data: Dict[str, Any], audit: ReportAudit) -> None:
    """Validate tool_analysis report data."""
    tools = data.get("tools", [])
    tools_count = data.get("tools_count", 0)

    # tools_count == len(tools)
    if tools_count == len(tools):
        audit.pass_("tools_count", f"{tools_count}")
    else:
        audit.fail("tools_count", f"tools_count={tools_count}, len(tools)={len(tools)}")

    # Per-tool: executions >= successful + failed + skipped
    # Some tool runs may have statuses like 'error', 'unknown', 'timeout' that
    # are not counted in successful/failed/skipped, so we check >=
    bad_exec = []
    for t in tools:
        name = t.get("tool_name", "?")
        executions = t.get("executions", 0)
        successful = t.get("successful", 0)
        failed = t.get("failed", 0)
        skipped = t.get("skipped", 0)
        accounted = successful + failed + skipped
        if accounted > executions:
            bad_exec.append(f"{name}: s+f+sk={accounted} > exec={executions}")
    if bad_exec:
        audit.fail("tool_exec_sum", "; ".join(bad_exec[:5]))
    else:
        audit.pass_("tool_exec_sum", f"all {len(tools)} tools: accounted <= executions")

    # Per-tool: success_rate
    bad_rate = []
    for t in tools:
        name = t.get("tool_name", "?")
        executions = t.get("executions", 0)
        successful = t.get("successful", 0)
        reported_rate = t.get("success_rate", 0)
        expected_rate = (successful / executions * 100) if executions > 0 else 0
        if not close_enough(reported_rate, expected_rate, 0.2):
            bad_rate.append(f"{name}: reported={reported_rate}, expected={expected_rate:.1f}")
    if bad_rate:
        audit.fail("tool_success_rate", "; ".join(bad_rate[:5]))
    else:
        audit.pass_("tool_success_rate", "all rates consistent")

    # Summary totals
    summary = data.get("summary", {})
    total_runs = summary.get("total_runs", 0)
    sum_exec = sum(t.get("executions", 0) for t in tools)
    if total_runs == sum_exec:
        audit.pass_("summary_total_runs", f"{total_runs}")
    else:
        audit.fail("summary_total_runs", f"summary={total_runs}, sum={sum_exec}")

    total_findings = summary.get("total_findings", 0)
    sum_findings = sum(t.get("total_findings", 0) for t in tools)
    if total_findings == sum_findings:
        audit.pass_("summary_total_findings", f"{total_findings}")
    else:
        audit.fail("summary_total_findings", f"summary={total_findings}, sum={sum_findings}")

    # Severity heatmap
    heatmap = data.get("severity_heatmap_data", {})
    if heatmap and isinstance(heatmap, dict):
        hm_tools = heatmap.get("tools", [])
        hm_matrix = heatmap.get("matrix", [])
        hm_sevs = heatmap.get("severities", [])

        # Dimensions match
        if len(hm_tools) == len(tools):
            audit.pass_("heatmap_rows", f"{len(hm_tools)} rows")
        else:
            audit.fail("heatmap_rows", f"heatmap tools={len(hm_tools)}, actual tools={len(tools)}")

        if len(hm_matrix) == len(hm_tools):
            audit.pass_("heatmap_matrix_rows", "matrix rows match tools")
        else:
            audit.fail("heatmap_matrix_rows", f"matrix rows={len(hm_matrix)}, tools={len(hm_tools)}")

        # Each row has 5 columns
        bad_cols = [i for i, row in enumerate(hm_matrix) if len(row) != 5]
        if bad_cols:
            audit.fail("heatmap_cols", f"rows with != 5 cols: {bad_cols[:5]}")
        else:
            audit.pass_("heatmap_cols", "all rows have 5 columns")

        # Heatmap row sums vs tool total_findings
        bad_hm_sums = []
        for i, (row, t) in enumerate(zip(hm_matrix, tools)):
            row_sum = sum(row)
            tool_findings = t.get("total_findings", 0)
            # Heatmap uses findings_by_severity which is counted from issues list,
            # while total_findings comes from total_issues counter.
            # They may differ if some findings lack severity.
            if row_sum > tool_findings + 1:
                bad_hm_sums.append(
                    f"{t.get('tool_name', '?')}: heatmap_sum={row_sum}, total_findings={tool_findings}"
                )
        if bad_hm_sums:
            audit.warn("heatmap_sums", "; ".join(bad_hm_sums[:5]))
        else:
            audit.pass_("heatmap_sums", "row sums consistent with tool findings")

    # Analyzer categories valid
    analyzer_cats = data.get("analyzer_categories", {})
    if analyzer_cats:
        bad_cats = set(analyzer_cats.keys()) - VALID_ANALYZER_CATEGORIES
        if bad_cats:
            audit.warn("analyzer_categories", f"unexpected: {bad_cats}")
        else:
            audit.pass_("analyzer_categories", f"categories: {list(analyzer_cats.keys())}")


# ---------------------------------------------------------------------------
# Phase 3: Audit — generation_analytics validators
# ---------------------------------------------------------------------------

def audit_generation_analytics(data: Dict[str, Any], audit: ReportAudit) -> None:
    """Validate generation_analytics report data."""
    # Check for no_data case
    if data.get("status") == "no_data":
        audit.warn("no_data", data.get("message", "no data"))
        return

    summary = data.get("summary", {})
    total_apps = summary.get("total_apps", 0)
    successful = summary.get("successful", 0)
    failed = summary.get("failed", 0)

    # total == successful + failed
    if total_apps == successful + failed:
        audit.pass_("total_sum", f"total={total_apps}, success={successful}, failed={failed}")
    else:
        audit.fail("total_sum", f"total={total_apps} != success({successful}) + failed({failed})")

    # success_rate
    reported_rate = summary.get("success_rate", 0)
    expected_rate = round((successful / total_apps) * 100, 1) if total_apps > 0 else 0
    if close_enough(reported_rate, expected_rate, 0.2):
        audit.pass_("success_rate", f"{reported_rate}%")
    else:
        audit.fail("success_rate", f"reported={reported_rate}, expected={expected_rate}")

    # Per-model consistency
    by_model = data.get("by_model", [])
    bad_model = []
    model_total_sum = 0
    for entry in by_model:
        name = entry.get("model", "?")
        m_total = entry.get("total", 0)
        m_success = entry.get("success", 0)
        m_failed = entry.get("failed", 0)
        model_total_sum += m_total
        if m_total != m_success + m_failed:
            bad_model.append(f"{name}: total={m_total} != s+f={m_success + m_failed}")
        m_rate = entry.get("success_rate", 0)
        exp_rate = round((m_success / m_total) * 100, 1) if m_total > 0 else 0
        if not close_enough(m_rate, exp_rate, 0.2):
            bad_model.append(f"{name}: rate={m_rate}, expected={exp_rate}")
    if bad_model:
        audit.fail("per_model", "; ".join(bad_model[:5]))
    else:
        audit.pass_("per_model", f"{len(by_model)} models consistent")

    # Sum of all model totals == summary.total_apps
    if model_total_sum == total_apps:
        audit.pass_("model_total_sum", f"{model_total_sum}")
    else:
        audit.fail("model_total_sum", f"sum_models={model_total_sum}, total_apps={total_apps}")

    # Per-template consistency
    by_template = data.get("by_template", [])
    bad_tmpl = []
    template_total_sum = 0
    for entry in by_template:
        name = entry.get("template", "?")
        t_total = entry.get("total", 0)
        t_success = entry.get("success", 0)
        t_failed = entry.get("failed", 0)
        template_total_sum += t_total
        if t_total != t_success + t_failed:
            bad_tmpl.append(f"{name}: total={t_total} != s+f={t_success + t_failed}")
        t_rate = entry.get("success_rate", 0)
        exp_rate = round((t_success / t_total) * 100, 1) if t_total > 0 else 0
        if not close_enough(t_rate, exp_rate, 0.2):
            bad_tmpl.append(f"{name}: rate={t_rate}, expected={exp_rate}")
    if bad_tmpl:
        audit.fail("per_template", "; ".join(bad_tmpl[:5]))
    else:
        audit.pass_("per_template", f"{len(by_template)} templates consistent")

    # Template total sum == total_apps
    if template_total_sum == total_apps:
        audit.pass_("template_total_sum", f"{template_total_sum}")
    else:
        audit.fail("template_total_sum", f"sum_templates={template_total_sum}, total_apps={total_apps}")

    # Model-template matrix dimensions
    matrix_data = data.get("model_template_matrix", {})
    if matrix_data and isinstance(matrix_data, dict):
        m_models = matrix_data.get("models", [])
        m_templates = matrix_data.get("templates", [])
        m_matrix = matrix_data.get("matrix", [])

        if len(m_matrix) == len(m_models):
            audit.pass_("matrix_rows", f"{len(m_models)} models")
        else:
            audit.fail("matrix_rows", f"matrix rows={len(m_matrix)}, models={len(m_models)}")

        bad_cols = [i for i, row in enumerate(m_matrix) if len(row) != len(m_templates)]
        if bad_cols:
            audit.fail("matrix_cols", f"rows with wrong col count: {bad_cols[:5]}")
        else:
            audit.pass_("matrix_cols", f"{len(m_templates)} templates per row")

        # Matrix cell totals sum to total_apps
        cell_sum = 0
        for row in m_matrix:
            for cell in row:
                if isinstance(cell, dict):
                    cell_sum += cell.get("total", 0)
                elif isinstance(cell, (int, float)):
                    cell_sum += int(cell)
        if cell_sum == total_apps:
            audit.pass_("matrix_sum", f"{cell_sum}")
        else:
            audit.fail("matrix_sum", f"cell_sum={cell_sum}, total_apps={total_apps}")
    else:
        audit.pass_("matrix", "no model_template_matrix")

    # Attempts distribution sums to total_apps
    attempts = data.get("attempts_distribution", [])
    if attempts:
        attempts_sum = sum(entry.get("count", 0) for entry in attempts)
        if attempts_sum == total_apps:
            audit.pass_("attempts_sum", f"{attempts_sum}")
        else:
            audit.fail("attempts_sum", f"attempts_sum={attempts_sum}, total_apps={total_apps}")

    # Fix counts are non-negative
    fix_stats = data.get("fix_effectiveness", {})
    if fix_stats:
        bad_fix = [f"{k}={v}" for k, v in fix_stats.items() if isinstance(v, (int, float)) and v < 0]
        if bad_fix:
            audit.fail("fix_counts", f"negative: {', '.join(bad_fix)}")
        else:
            audit.pass_("fix_counts", "all non-negative")


# ---------------------------------------------------------------------------
# Phase 3: Main audit orchestrator
# ---------------------------------------------------------------------------

def audit_report(report: Report) -> ReportAudit:
    """Run all applicable audit checks on a single report."""
    data = report.get_report_data()
    config = report.get_config()
    audit = ReportAudit(report.report_id, report.report_type, report.title or "")

    if not data:
        audit.fail("data_present", "report_data is None or empty")
        return audit

    if not isinstance(data, dict):
        audit.fail("data_type", f"expected dict, got {type(data).__name__}")
        return audit

    audit.pass_("data_present", f"{len(json.dumps(data, default=str)):,} bytes")

    # Universal checks
    audit_universal(data, audit, report.report_type)

    # Type-specific checks
    if report.report_type == "model_analysis":
        audit_model_analysis(data, audit, config)
    elif report.report_type == "template_comparison":
        audit_template_comparison(data, audit, config)
    elif report.report_type == "tool_analysis":
        audit_tool_analysis(data, audit)
    elif report.report_type == "generation_analytics":
        audit_generation_analytics(data, audit)
    else:
        audit.warn("unknown_type", f"no specific validator for {report.report_type}")

    return audit


# ---------------------------------------------------------------------------
# Phase 4: Output
# ---------------------------------------------------------------------------

def print_audit_summary(audits: List[ReportAudit]) -> None:
    """Print structured audit report to console."""
    total_pass = sum(a.pass_count for a in audits)
    total_warn = sum(a.warn_count for a in audits)
    total_fail = sum(a.fail_count for a in audits)
    total_checks = total_pass + total_warn + total_fail

    print(f"\n{'=' * 80}")
    print(f"AUDIT SUMMARY")
    print(f"{'=' * 80}")
    print(f"Reports audited: {len(audits)}")
    print(f"Total checks:    {total_checks}")
    print(f"  PASS: {total_pass}")
    print(f"  WARN: {total_warn}")
    print(f"  FAIL: {total_fail}")
    print()

    # Group by report type
    by_type: Dict[str, List[ReportAudit]] = {}
    for a in audits:
        by_type.setdefault(a.report_type, []).append(a)

    for rtype, type_audits in sorted(by_type.items()):
        type_pass = sum(a.pass_count for a in type_audits)
        type_warn = sum(a.warn_count for a in type_audits)
        type_fail = sum(a.fail_count for a in type_audits)
        print(f"\n--- {rtype} ({len(type_audits)} reports) ---")
        print(f"    PASS={type_pass}  WARN={type_warn}  FAIL={type_fail}")

        for a in type_audits:
            status_icon = "OK" if a.fail_count == 0 else "FAIL"
            warn_note = f" ({a.warn_count}W)" if a.warn_count > 0 else ""
            gen_note = ""
            if a.generation_error:
                gen_note = f" [GEN ERROR: {a.generation_error[:60]}]"
            print(f"    [{status_icon}]{warn_note} {a.title}{gen_note}")

            # Print failures
            for c in a.checks:
                if c.status == "FAIL":
                    print(f"      FAIL: {c.name}: {c.detail}")

    # Print all warnings at the end
    all_warns = []
    for a in audits:
        for c in a.checks:
            if c.status == "WARN":
                all_warns.append((a.title, c.name, c.detail))

    if all_warns:
        print(f"\n--- ALL WARNINGS ({len(all_warns)}) ---")
        for title, name, detail in all_warns[:30]:
            print(f"  [{title[:40]}] {name}: {detail}")
        if len(all_warns) > 30:
            print(f"  ... and {len(all_warns) - 30} more warnings")

    print(f"\n{'=' * 80}")
    if total_fail == 0:
        print("RESULT: ALL CHECKS PASSED (no failures)")
    else:
        print(f"RESULT: {total_fail} FAILURE(S) DETECTED")
    print(f"{'=' * 80}\n")


def save_audit_json(audits: List[ReportAudit], path: Path) -> None:
    """Save machine-readable audit results to JSON file."""
    output = {
        "generated_at": datetime.now().isoformat(),
        "reports_audited": len(audits),
        "totals": {
            "pass": sum(a.pass_count for a in audits),
            "warn": sum(a.warn_count for a in audits),
            "fail": sum(a.fail_count for a in audits),
        },
        "reports": [a.to_dict() for a in audits],
    }
    path.write_text(json.dumps(output, indent=2, default=str))
    print(f"Audit results saved to: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 80)
    print("GENERATE ALL REPORTS AND AUDIT FACTUALITY")
    print("=" * 80)

    # Phase 1: Setup
    print("\n[Phase 1] Setup & Discovery")
    app = create_app("development")

    with app.app_context():
        report_service = ServiceLocator.get_report_service()
        if not report_service:
            print("ERROR: ReportService not available")
            return 1

        model_slugs, template_slugs = discover_slugs()
        print_baseline(model_slugs, template_slugs)

        existing_count = Report.query.count()
        print(f"  Existing reports in DB: {existing_count}")

        # Phase 2: Generate
        expected_count = len(model_slugs) + len(template_slugs) + 2
        print(f"\n[Phase 2] Generating {expected_count} reports")
        print("-" * 60)
        t_start = time.time()
        gen_results = generate_all_reports(report_service, model_slugs, template_slugs)
        t_gen = time.time() - t_start

        succeeded = sum(1 for r, _, e in gen_results if r and e is None)
        failed_gen = sum(1 for r, _, e in gen_results if e is not None)
        print(f"\nGeneration complete: {succeeded} succeeded, {failed_gen} failed in {t_gen:.1f}s")

        # Phase 3: Audit
        print(f"\n[Phase 3] Auditing {succeeded} completed reports")
        print("-" * 60)
        audits: List[ReportAudit] = []

        for report_obj, elapsed, gen_error in gen_results:
            if report_obj is None:
                # Create a placeholder audit for failed generation
                placeholder = ReportAudit("N/A", "unknown", "GENERATION FAILED")
                placeholder.generation_error = gen_error
                placeholder.generation_time = elapsed
                placeholder.fail("generation", gen_error or "report not created")
                audits.append(placeholder)
                continue

            audit = audit_report(report_obj)
            audit.generation_time = elapsed
            if gen_error:
                audit.generation_error = gen_error
            audits.append(audit)
            print(f"  Audited [{report_obj.report_type}] {report_obj.title}: "
                  f"P={audit.pass_count} W={audit.warn_count} F={audit.fail_count}")

        # Phase 4: Output
        print_audit_summary(audits)

        # Save JSON
        json_path = Path(__file__).resolve().parent / "audit_results.json"
        save_audit_json(audits, json_path)

        # Final verification: report count
        final_count = Report.query.filter(Report.status == "completed").count()
        print(f"\nFinal report count (completed): {final_count}")
        total_in_db = Report.query.count()
        print(f"Total reports in DB: {total_in_db}")

        total_fail = sum(a.fail_count for a in audits)
        return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
