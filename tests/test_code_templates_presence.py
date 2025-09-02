from app.paths import CODE_TEMPLATES_DIR
import re

REQUIRED = [
    'backend/app.py.template',
    'backend/requirements.txt',
    'backend/Dockerfile.template',
    'frontend/package.json.template',
    'frontend/vite.config.js.template',
    'frontend/src/App.jsx.template',
    'frontend/src/App.css',
    'frontend/index.html.template',
    'frontend/Dockerfile.template',
    'docker-compose.yml.template',
]

PLACEHOLDER_KEYS = [
    'model_name', 'model_name_lower', 'backend_port', 'frontend_port', 'model_prefix', 'port'
]

DOUBLE_BRACE_PATTERN = re.compile(r'{{\s*([a-zA-Z0-9_]+)\s*}}')


def test_template_files_exist_and_use_double_braces():
    base = CODE_TEMPLATES_DIR
    assert base.exists(), f"Templates base directory missing: {base}"

    missing = [rel for rel in REQUIRED if not (base / rel).exists()]
    assert not missing, f"Missing template files: {missing}"

    # Spot check at least one occurrence of a known placeholder per file that previously had single braces
    files_to_check = [
        'backend/app.py.template',
        'backend/Dockerfile.template',
        'frontend/package.json.template',
        'frontend/index.html.template',
        'frontend/Dockerfile.template',
        'frontend/src/App.jsx.template',
        'docker-compose.yml.template',
    ]
    found_any = False
    for rel in files_to_check:
        content = (base / rel).read_text(encoding='utf-8', errors='ignore')
        matches = DOUBLE_BRACE_PATTERN.findall(content)
        if any(m in PLACEHOLDER_KEYS for m in matches):
            found_any = True
        else:
            raise AssertionError(f"File {rel} does not contain any expected double-brace placeholders; found: {matches}")

    assert found_any, "Expected to find at least one placeholder across checked files"
