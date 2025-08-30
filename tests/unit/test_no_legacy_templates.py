import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repo root
TEMPLATES_DIR = ROOT / 'src' / 'templates'
ROUTES_DIR = ROOT / 'src' / 'app' / 'routes'

# Patterns that must not appear anymore
FORBIDDEN_TEMPLATE_PATTERNS = [
    r"\{\%\s*include\s*'partials/testing/",
    r"\{\%\s*include\s*\"partials/testing/",
    # Flat alias includes under analysis root (should use namespaced folders)
    r"\{\%\s*include\s*'partials/analysis/list_",
    r"\{\%\s*include\s*\"partials/analysis/list_",
    r"\{\%\s*include\s*'partials/analysis/preview_shell.html'",
    r"\{\%\s*include\s*\"partials/analysis/preview_shell.html\"",
    r"\{\%\s*include\s*'partials/analysis/create_shell.html'",
    r"\{\%\s*include\s*\"partials/analysis/create_shell.html\"",
    r"\{\%\s*include\s*'partials/analysis/active_tasks.html'",
    r"\{\%\s*include\s*\"partials/analysis/active_tasks.html\"",
]

FORBIDDEN_ROUTE_PATTERNS = [
    r"url_prefix=['\"]/testing['\"]",
    r"@api_bp\.route\('/testing",
    r"Blueprint\('testing'",
]


DEPRECATED_SENTINEL = "Deprecated legacy"


def _walk_files(root: Path, exts: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(exts):
                files.append(Path(dirpath) / name)
    return files


def test_no_legacy_template_includes():
    assert TEMPLATES_DIR.exists(), f"Templates dir not found: {TEMPLATES_DIR}"
    bad_hits: list[tuple[Path, str]] = []
    for file_path in _walk_files(TEMPLATES_DIR, ('.html', '.jinja', '.jinja2')):
        text = file_path.read_text(encoding='utf-8', errors='ignore')
        if DEPRECATED_SENTINEL in text:
            continue
        for pat in FORBIDDEN_TEMPLATE_PATTERNS:
            if re.search(pat, text):
                bad_hits.append((file_path.relative_to(ROOT), pat))
    assert not bad_hits, f"Found forbidden template includes: {bad_hits}"


def test_legacy_alias_templates_removed():
    """Ensure deprecated alias templates are physically removed."""
    root = TEMPLATES_DIR / 'partials' / 'analysis'
    forbidden_files = [
        'active_tasks.html',
        'list_combined.html',
        'list_dynamic.html',
        'list_performance.html',
        'list_security.html',
        'list_shell.html',
        'preview_shell.html',
        'create_shell.html',
    ]
    missing = []
    present = []
    for name in forbidden_files:
        path = root / name
        if path.exists():
            present.append(str(path.relative_to(ROOT)))
        else:
            missing.append(name)
    assert not present, f"Deprecated alias templates should be removed. Found: {present}"


def test_testing_templates_removed():
    """Ensure /testing templates are removed."""
    pages_testing = TEMPLATES_DIR / 'pages' / 'testing.html'
    testing_partials = TEMPLATES_DIR / 'partials' / 'testing'
    assert not pages_testing.exists(), f"Remove legacy page: {pages_testing}"
    assert not testing_partials.exists() or not any(testing_partials.iterdir()), "Remove legacy testing partials folder or empty it"


def test_no_legacy_testing_routes():
    assert ROUTES_DIR.exists(), f"Routes dir not found: {ROUTES_DIR}"
    bad_hits: list[tuple[Path, str]] = []
    for file_path in _walk_files(ROUTES_DIR, ('.py',)):
        text = file_path.read_text(encoding='utf-8', errors='ignore')
        if DEPRECATED_SENTINEL in text:
            continue
        for pat in FORBIDDEN_ROUTE_PATTERNS:
            if re.search(pat, text):
                bad_hits.append((file_path.relative_to(ROOT), pat))
    assert not bad_hits, f"Found forbidden testing route patterns: {bad_hits}"


def test_testing_route_modules_removed():
    """Ensure backend testing route modules are gone."""
    api_dir = ROUTES_DIR / 'api'
    forbidden = [
        ROUTES_DIR / 'testing.py',
        api_dir / 'testing.py',
        api_dir / 'testing_results.py',
        api_dir / 'testing_results_fixed.py',
        api_dir / 'testing_results_simple.py',
    ]
    present = [str(p.relative_to(ROOT)) for p in forbidden if p.exists()]
    assert not present, f"Remove deprecated testing route modules: {present}"
