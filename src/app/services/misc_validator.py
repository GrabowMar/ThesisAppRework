"""Misc input validator.

Checks requirements, templates, scaffolding, and prompt files used by generation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.paths import MISC_DIR


_ALLOWED_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
    "WS",
}


def _validate_requirements_data(data: Dict[str, Any], filename: str) -> List[str]:
    issues: List[str] = []
    slug = data.get("slug")
    if not slug:
        issues.append(f"requirements/{filename}: missing slug")
    elif slug != Path(filename).stem:
        issues.append(
            f"requirements/{filename}: slug '{slug}' != filename '{Path(filename).stem}'"
        )

    for field in [
        "name",
        "description",
        "backend_requirements",
        "frontend_requirements",
        "api_endpoints",
    ]:
        if field not in data:
            issues.append(f"requirements/{filename}: missing {field}")

    for list_field in ["backend_requirements", "frontend_requirements", "admin_requirements"]:
        values = data.get(list_field)
        if values is None:
            continue
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            issues.append(f"requirements/{filename}: {list_field} must be list[str]")

    for key in ["api_endpoints", "admin_api_endpoints", "control_endpoints"]:
        endpoints = data.get(key) or []
        if not isinstance(endpoints, list):
            issues.append(f"requirements/{filename}: {key} is not a list")
            continue

        seen: set[tuple[str, str]] = set()
        for idx, ep in enumerate(endpoints):
            if not isinstance(ep, dict):
                issues.append(f"requirements/{filename}: {key}[{idx}] not object")
                continue

            method = str(ep.get("method", "")).upper()
            path = str(ep.get("path", ""))
            if method and method not in _ALLOWED_METHODS:
                issues.append(
                    f"requirements/{filename}: {key}[{idx}] invalid method '{method}'"
                )
            if not path.startswith("/"):
                issues.append(
                    f"requirements/{filename}: {key}[{idx}] path missing leading '/'"
                )
            if key == "api_endpoints" and path and not path.startswith("/api"):
                issues.append(
                    f"requirements/{filename}: {key}[{idx}] path should start with /api"
                )
            if key == "admin_api_endpoints" and path and not path.startswith("/api/admin"):
                issues.append(
                    f"requirements/{filename}: {key}[{idx}] path should start with /api/admin"
                )
            if key == "control_endpoints" and path and not (
                path.startswith("/health") or path.startswith("/api/health") or path.startswith("/api/status")
            ):
                issues.append(
                    f"requirements/{filename}: {key}[{idx}] path should be /health or /api/health"
                )

            if method and path:
                signature = (method, path)
                if signature in seen:
                    issues.append(
                        f"requirements/{filename}: {key} duplicate {method} {path}"
                    )
                seen.add(signature)

    admin_reqs = data.get("admin_requirements") or []
    admin_eps = data.get("admin_api_endpoints") or []
    if admin_reqs and not admin_eps:
        issues.append(f"requirements/{filename}: admin_requirements present but admin_api_endpoints missing")
    if admin_eps and not admin_reqs:
        issues.append(f"requirements/{filename}: admin_api_endpoints present but admin_requirements missing")

    return issues


def validate_template_requirements(template_slug: str) -> Dict[str, Any]:
    """Validate a single template requirements file."""
    req_path = MISC_DIR / "requirements" / f"{template_slug}.json"
    if not req_path.exists():
        return {
            "ok": False,
            "issues": [f"requirements/{template_slug}.json: file not found"],
            "issue_count": 1,
        }

    try:
        data = json.loads(req_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "issues": [f"requirements/{req_path.name}: invalid JSON ({exc})"],
            "issue_count": 1,
        }

    issues = _validate_requirements_data(data, req_path.name)
    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "issue_count": len(issues),
    }


def validate_misc_inputs() -> Dict[str, Any]:
    """Validate misc inputs and return status details."""
    issues: List[str] = []

    # Requirements JSON
    req_dir = MISC_DIR / "requirements"
    for path in req_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"requirements/{path.name}: invalid JSON ({exc})")
            continue

        issues.extend(_validate_requirements_data(data, path.name))

    # Templates
    tpl_dir = MISC_DIR / "templates"
    expected = {
        "four-query": [
            "backend_user.md.jinja2",
            "backend_admin.md.jinja2",
            "frontend_user.md.jinja2",
            "frontend_admin.md.jinja2",
        ],
        "two-query": ["backend.md.jinja2", "frontend.md.jinja2"],
        "unguarded": ["backend.md.jinja2", "frontend.md.jinja2", "fullstack.md.jinja2"],
    }
    for folder, files in expected.items():
        folder_path = tpl_dir / folder
        if not folder_path.exists():
            issues.append(f"templates/{folder}: missing folder")
            continue
        for file_name in files:
            if not (folder_path / file_name).exists():
                issues.append(f"templates/{folder}/{file_name}: missing")

    # Scaffolding
    scaffold_dir = MISC_DIR / "scaffolding"
    for name in ["react-flask", "react-flask-unguarded"]:
        if not (scaffold_dir / name).exists():
            issues.append(f"scaffolding/{name}: missing")

    # System prompts
    prompt_dir = MISC_DIR / "prompts" / "system"
    for fname in [
        "backend_user.md",
        "backend_admin.md",
        "backend_unguarded.md",
        "frontend_user.md",
        "frontend_admin.md",
        "frontend_unguarded.md",
        "fullstack_unguarded.md",
    ]:
        if not (prompt_dir / fname).exists():
            issues.append(f"prompts/system/{fname}: missing")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "issue_count": len(issues),
    }
