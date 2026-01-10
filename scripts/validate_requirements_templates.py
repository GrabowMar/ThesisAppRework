"""Validate requirement templates under misc/requirements.

This script is intentionally standalone (stdlib only) so it can be run
reliably from PowerShell/CI without interactive REPL issues.

It checks:
- JSON parses and top-level is an object
- Required keys and expected types
- slug normalization and filename/slug consistency (loader-critical)
- endpoint schema sanity (method/path/description + request/response types)
- basic LLM-readability heuristics (non-empty, consistent numbering)

Usage:
  python scripts/validate_requirements_templates.py
  python scripts/validate_requirements_templates.py --json
  python scripts/validate_requirements_templates.py --strict

Exit codes:
  0: no errors (warnings may exist)
  1: errors found (or warnings in --strict)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RE_METHOD = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|WS)$", re.IGNORECASE)
RE_NUMBERED_ITEM = re.compile(r"^\s*(\d+)\.(\s+|$)")


def _normalize_slug(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _normalize_filename_stem(path: Path) -> str:
    return _normalize_slug(path.stem)


@dataclass
class Issue:
    level: str  # 'error' | 'warning'
    code: str
    message: str


@dataclass
class FileReport:
    path: Path
    slug: Optional[str] = None
    normalized_slug: Optional[str] = None
    suggested_slug: Optional[str] = None
    errors: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)

    def add_error(self, code: str, message: str) -> None:
        self.errors.append(Issue(level="error", code=code, message=message))

    def add_warning(self, code: str, message: str) -> None:
        self.warnings.append(Issue(level="warning", code=code, message=message))


def _expect_type(report: FileReport, key: str, value: Any, expected: Tuple[type, ...]) -> bool:
    if not isinstance(value, expected):
        expected_names = ", ".join(t.__name__ for t in expected)
        report.add_error("type", f"Key '{key}' should be {expected_names}, got {type(value).__name__}")
        return False
    return True


def _validate_string_list(report: FileReport, key: str, value: Any, allow_empty: bool = False) -> None:
    if not _expect_type(report, key, value, (list,)):
        return
    if not value and not allow_empty:
        report.add_warning("empty", f"Key '{key}' is empty")
        return
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            report.add_error("type", f"Key '{key}' item {idx} should be string, got {type(item).__name__}")
            continue
        if not item.strip():
            report.add_warning("empty", f"Key '{key}' item {idx} is blank")


def _validate_endpoint_list(
    report: FileReport,
    key: str,
    endpoints: Any,
    expected_prefixes: Optional[List[str]],
    allow_empty: bool,
) -> None:
    if not _expect_type(report, key, endpoints, (list,)):
        return

    if not endpoints:
        if not allow_empty:
            report.add_warning("empty", f"Key '{key}' is empty")
        return

    for i, ep in enumerate(endpoints):
        if not isinstance(ep, dict):
            report.add_error("type", f"Key '{key}' item {i} should be object, got {type(ep).__name__}")
            continue

        method = ep.get("method")
        path = ep.get("path")
        desc = ep.get("description")

        if not isinstance(method, str) or not method.strip():
            report.add_error("endpoint", f"{key}[{i}].method missing or not a string")
        elif not RE_METHOD.match(method.strip()):
            report.add_warning("endpoint", f"{key}[{i}].method '{method}' is unusual")

        if not isinstance(path, str) or not path.strip():
            report.add_error("endpoint", f"{key}[{i}].path missing or not a string")
        else:
            if not path.startswith("/"):
                report.add_error("endpoint", f"{key}[{i}].path must start with '/', got '{path}'")
            if expected_prefixes and path.startswith("/"):
                if not any(path.startswith(pfx) for pfx in expected_prefixes):
                    report.add_warning(
                        "endpoint",
                        f"{key}[{i}].path '{path}' does not match expected prefixes {expected_prefixes}",
                    )

        if not isinstance(desc, str) or not desc.strip():
            report.add_warning("endpoint", f"{key}[{i}].description missing/blank")

        # request/response can be None or object; keep it simple for prompt rendering
        for rr_key in ("request", "response"):
            if rr_key not in ep:
                continue
            rr_val = ep.get(rr_key)
            if rr_val is None:
                continue
            if isinstance(rr_val, (dict, list)):
                continue
            report.add_warning(
                "endpoint",
                f"{key}[{i}].{rr_key} should be object/array/null (not {type(rr_val).__name__})",
            )


def _validate_numbering_consistency(report: FileReport, key: str, items: List[str]) -> None:
    numbered = 0
    for item in items:
        if RE_NUMBERED_ITEM.match(item):
            numbered += 1

    if not items:
        return

    # If at least half are numbered, encourage full numbering.
    if 0 < numbered < len(items) and numbered >= max(1, len(items) // 2):
        report.add_warning(
            "readability",
            f"Key '{key}' mixes numbered and unnumbered items; consider numbering all for LLM clarity",
        )


def validate_file(path: Path) -> FileReport:
    report = FileReport(path=path)
    filename_norm = _normalize_filename_stem(path)

    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception as e:
        report.add_error("io", f"Failed to read file: {e}")
        return report

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        report.add_error("json", f"Invalid JSON: {e}")
        return report

    if not isinstance(data, dict):
        report.add_error("type", f"Top-level JSON must be an object, got {type(data).__name__}")
        return report

    slug = data.get("slug")
    name = data.get("name")
    category = data.get("category")
    description = data.get("description")

    if isinstance(slug, str):
        report.slug = slug
        report.normalized_slug = _normalize_slug(slug)
        report.suggested_slug = filename_norm

        if report.normalized_slug != filename_norm:
            report.add_error(
                "slug_mismatch",
                f"Normalized slug '{report.normalized_slug}' does not match normalized filename '{filename_norm}'",
            )
    else:
        report.add_error("missing", "Missing required key 'slug' (string)")
        report.suggested_slug = filename_norm

    if not isinstance(name, str) or not name.strip():
        report.add_error("missing", "Missing required key 'name' (string)")
    if not isinstance(category, str) or not category.strip():
        report.add_warning("missing", "Missing/blank key 'category' (string)")
    if not isinstance(description, str) or not description.strip():
        report.add_warning("missing", "Missing/blank key 'description' (string)")

    # Requirements lists
    for list_key in ("backend_requirements", "frontend_requirements"):
        if list_key not in data:
            report.add_warning("missing", f"Missing key '{list_key}' (list of strings)")
            continue
        value = data.get(list_key)
        _validate_string_list(report, list_key, value)
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            _validate_numbering_consistency(report, list_key, value)

    # Admin requirements are optional but helpful
    if "admin_requirements" in data:
        _validate_string_list(report, "admin_requirements", data.get("admin_requirements"), allow_empty=True)

    # Endpoint lists
    if "api_endpoints" not in data:
        report.add_warning("missing", "Missing key 'api_endpoints' (list)")
    else:
        _validate_endpoint_list(
            report,
            "api_endpoints",
            data.get("api_endpoints"),
            expected_prefixes=["/api/"],
            allow_empty=False,
        )

    if "admin_api_endpoints" in data:
        _validate_endpoint_list(
            report,
            "admin_api_endpoints",
            data.get("admin_api_endpoints"),
            expected_prefixes=["/api/admin/"],
            allow_empty=True,
        )

    # Control endpoints are optional. If present, validate structure.
    if "control_endpoints" in data:
        _validate_endpoint_list(
            report,
            "control_endpoints",
            data.get("control_endpoints"),
            expected_prefixes=["/api/"],
            allow_empty=True,
        )

    # Extra sanity: endpoints should be dicts with stable keys; warn on unknown keys
    # (LLM readability: fewer surprise keys)
    allowed_endpoint_keys = {"method", "path", "description", "request", "response"}
    for ep_list_key in ("api_endpoints", "admin_api_endpoints", "control_endpoints"):
        eps = data.get(ep_list_key)
        if not isinstance(eps, list):
            continue
        for i, ep in enumerate(eps):
            if not isinstance(ep, dict):
                continue
            extra = sorted(k for k in ep.keys() if k not in allowed_endpoint_keys)
            if extra:
                report.add_warning(
                    "endpoint",
                    f"{ep_list_key}[{i}] has extra keys {extra}; keep schemas minimal for LLM clarity",
                )

    return report


def _render_text(reports: List[FileReport]) -> str:
    total_files = len(reports)
    total_errors = sum(len(r.errors) for r in reports)
    total_warnings = sum(len(r.warnings) for r in reports)

    lines: List[str] = []
    lines.append(f"Templates scanned: {total_files}")
    lines.append(f"Errors: {total_errors} | Warnings: {total_warnings}")
    lines.append("")

    # Per-file summary
    for r in sorted(reports, key=lambda x: x.path.name.lower()):
        if not r.errors and not r.warnings:
            continue
        lines.append(f"- {r.path.as_posix()}")
        if r.slug is not None:
            lines.append(f"  slug: {r.slug} (normalized={r.normalized_slug})")
        if r.suggested_slug:
            lines.append(f"  suggested_slug: {r.suggested_slug}")
        for issue in r.errors + r.warnings:
            lines.append(f"  [{issue.level}] {issue.code}: {issue.message}")
        lines.append("")

    if total_errors == 0 and total_warnings == 0:
        lines.append("All templates look good.")

    return "\n".join(lines)


def _render_json(reports: List[FileReport]) -> Dict[str, Any]:
    return {
        "templates_scanned": len(reports),
        "errors": sum(len(r.errors) for r in reports),
        "warnings": sum(len(r.warnings) for r in reports),
        "files": [
            {
                "path": r.path.as_posix(),
                "slug": r.slug,
                "normalized_slug": r.normalized_slug,
                "suggested_slug": r.suggested_slug,
                "errors": [{"code": i.code, "message": i.message} for i in r.errors],
                "warnings": [{"code": i.code, "message": i.message} for i in r.warnings],
            }
            for r in sorted(reports, key=lambda x: x.path.name.lower())
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (non-zero exit).",
    )
    args = parser.parse_args(argv)

    req_dir = Path(__file__).resolve().parents[1] / "misc" / "requirements"
    if not req_dir.exists():
        print(f"Requirements directory not found: {req_dir}", file=sys.stderr)
        return 1

    files = sorted(req_dir.glob("*.json"))
    reports = [validate_file(p) for p in files]

    if args.json:
        payload = _render_json(reports)
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(reports))

    total_errors = sum(len(r.errors) for r in reports)
    total_warnings = sum(len(r.warnings) for r in reports)

    if total_errors > 0:
        return 1
    if args.strict and total_warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
