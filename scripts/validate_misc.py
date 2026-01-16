"""Validate misc inputs (requirements, templates, scaffolding, prompts).

Run:
  python scripts/validate_misc.py
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MISC_DIR = ROOT / "misc"
ALLOWED_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
    "WS",
}


def _check_requirements() -> list[str]:
    issues: list[str] = []
    req_dir = MISC_DIR / "requirements"
    for path in req_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"requirements/{path.name}: invalid JSON ({exc})")
            continue

        slug = data.get("slug")
        if not slug:
            issues.append(f"requirements/{path.name}: missing slug")
        elif slug != path.stem:
            issues.append(
                f"requirements/{path.name}: slug '{slug}' != filename '{path.stem}'"
            )

        for field in [
            "name",
            "description",
            "backend_requirements",
            "frontend_requirements",
            "api_endpoints",
        ]:
            if field not in data:
                issues.append(f"requirements/{path.name}: missing {field}")

        for list_field in ["backend_requirements", "frontend_requirements", "admin_requirements"]:
            values = data.get(list_field)
            if values is None:
                continue
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                issues.append(f"requirements/{path.name}: {list_field} must be list[str]")

        for key in ["api_endpoints", "admin_api_endpoints", "control_endpoints"]:
            endpoints = data.get(key) or []
            if not isinstance(endpoints, list):
                issues.append(f"requirements/{path.name}: {key} is not a list")
                continue
            seen: set[tuple[str, str]] = set()
            for idx, ep in enumerate(endpoints):
                if not isinstance(ep, dict):
                    issues.append(f"requirements/{path.name}: {key}[{idx}] not object")
                    continue
                method = str(ep.get("method", "")).upper()
                path_value = str(ep.get("path", ""))
                if method and method not in ALLOWED_METHODS:
                    issues.append(
                        f"requirements/{path.name}: {key}[{idx}] invalid method '{method}'"
                    )
                if "path" in ep and not path_value.startswith("/"):
                    issues.append(
                        f"requirements/{path.name}: {key}[{idx}] path missing leading '/'"
                    )
                if key == "api_endpoints" and path_value and not path_value.startswith("/api"):
                    issues.append(
                        f"requirements/{path.name}: {key}[{idx}] path should start with /api"
                    )
                if key == "admin_api_endpoints" and path_value and not path_value.startswith("/api/admin"):
                    issues.append(
                        f"requirements/{path.name}: {key}[{idx}] path should start with /api/admin"
                    )
                if key == "control_endpoints" and path_value and not (
                    path_value.startswith("/health")
                    or path_value.startswith("/api/health")
                    or path_value.startswith("/api/status")
                ):
                    issues.append(
                        f"requirements/{path.name}: {key}[{idx}] path should be /health or /api/health"
                    )

                if method and path_value:
                    signature = (method, path_value)
                    if signature in seen:
                        issues.append(
                            f"requirements/{path.name}: {key} duplicate {method} {path_value}"
                        )
                    seen.add(signature)

        admin_reqs = data.get("admin_requirements") or []
        admin_eps = data.get("admin_api_endpoints") or []
        if admin_reqs and not admin_eps:
            issues.append(
                f"requirements/{path.name}: admin_requirements present but admin_api_endpoints missing"
            )
        if admin_eps and not admin_reqs:
            issues.append(
                f"requirements/{path.name}: admin_api_endpoints present but admin_requirements missing"
            )

    return issues


def _check_templates() -> list[str]:
    issues: list[str] = []
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
    return issues


def _check_scaffolding() -> list[str]:
    issues: list[str] = []
    scaffold_dir = MISC_DIR / "scaffolding"
    for name in ["react-flask", "react-flask-unguarded"]:
        if not (scaffold_dir / name).exists():
            issues.append(f"scaffolding/{name}: missing")
    return issues


def _check_prompts() -> list[str]:
    issues: list[str] = []
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
    return issues


def main() -> int:
    issues: list[str] = []
    issues.extend(_check_requirements())
    issues.extend(_check_templates())
    issues.extend(_check_scaffolding())
    issues.extend(_check_prompts())

    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("No structural issues found in misc.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
