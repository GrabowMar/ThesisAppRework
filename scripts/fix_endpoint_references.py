"""Utility to scan templates for incorrect Flask endpoint references and auto-fix them.

Focus:
    - Detect url_for('api.<endpoint>') calls where <endpoint> does not exist.
    - Heuristic fix when an extra "api_" prefix was added (e.g. api.api_system_status -> api.system_status).

Process:
    1. Parse api blueprint route function names from src/app/routes/ (functions decorated with @api_bp.route).
    2. Scan template files for occurrences of url_for('api.<name>').
    3. Build list of unknown endpoint names.
    4. Apply heuristic fixes:
         - If name starts with 'api_' and stripped version exists -> replace with stripped version.
         - If name WITHOUT 'api_' prefix missing but prefixed version exists -> replace with prefixed version.
         - Specific typo fix: 'api_system_status' -> 'system_status' if available.
    5. Write changes in-place and create one .bak backup per modified template file.

Run:
    python scripts/fix_endpoint_references.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, Set

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
ROUTES_DIR = SRC_DIR / "app" / "routes"
TEMPLATES_DIR = SRC_DIR / "templates"

API_BLUEPRINT_NAME = "api_bp"
URL_FOR_PATTERN = re.compile(r"url_for\(['\"]api\.([a-zA-Z0-9_]+)['\"]")

def collect_api_endpoints() -> Set[str]:
    endpoints: Set[str] = set()
    if not ROUTES_DIR.exists():
        return endpoints
    for py_file in ROUTES_DIR.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for deco in node.decorator_list:
                    if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
                        if (
                            isinstance(deco.func.value, ast.Name)
                            and deco.func.value.id == API_BLUEPRINT_NAME
                            and deco.func.attr == "route"
                        ):
                            endpoints.add(node.name)
    return endpoints

def determine_fix(name: str, existing: Set[str]) -> str | None:
    # Already valid
    if name in existing:
        return None
    # Heuristic 1: leading api_ erroneously added
    if name.startswith("api_"):
        stripped = name[len("api_"):]
        if stripped in existing:
            return stripped
    # Heuristic 2: missing api_ prefix but prefixed exists
    prefixed = f"api_{name}"
    if prefixed in existing:
        return prefixed
    # Heuristic 3: common system_status mismatch
    if name == "api_system_status" and "system_status" in existing:
        return "system_status"
    return None

def apply_fixes(content: str, fixes: Dict[str, str]) -> str:
    for bad, good in fixes.items():
        content = content.replace(f"url_for('api.{bad}'", f"url_for('api.{good}'")
        content = content.replace(f'url_for("api.{bad}"', f'url_for("api.{good}"')
    return content

def main() -> int:
    endpoints = collect_api_endpoints()
    if not endpoints:
        print("No API endpoints discovered. Aborting.")
        return 1
    print(f"Discovered {len(endpoints)} endpoints under api blueprint.")

    total_fixes = 0
    modified_files = 0

    for template in TEMPLATES_DIR.rglob("*.html"):
        try:
            content = template.read_text(encoding="utf-8")
        except Exception:
            continue
        names = URL_FOR_PATTERN.findall(content)
        if not names:
            continue
        planned: Dict[str, str] = {}
        for name in names:
            fix = determine_fix(name, endpoints)
            if fix and fix != name:
                planned[name] = fix
        if planned:
            backup = template.with_suffix(template.suffix + ".bak")
            if not backup.exists():
                backup.write_text(content, encoding="utf-8")
            new_content = apply_fixes(content, planned)
            template.write_text(new_content, encoding="utf-8")
            modified_files += 1
            total_fixes += len(planned)
            for bad, good in planned.items():
                rel = template.relative_to(ROOT)
                print(f"Fixed {rel}: {bad} -> {good}")

    print(f"\nSummary: {total_fixes} fix(es) applied in {modified_files} file(s).")
    return 0

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
