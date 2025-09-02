from app.paths import CODE_TEMPLATES_DIR, APP_TEMPLATES_DIR

REQUIRED_CODE = [
    'backend/app.py.template',
    'backend/Dockerfile.template',
    'backend/requirements.txt',
    'frontend/package.json.template',
    'frontend/vite.config.js.template',
    'frontend/Dockerfile.template',
    'frontend/index.html.template',
    'frontend/src/App.jsx.template',
    'frontend/src/App.css',
    'docker-compose.yml.template',
]

def test_no_nested_code_templates_duplication():
    dup = CODE_TEMPLATES_DIR / 'code_templates'
    assert not dup.exists(), f"Nested duplicate directory should not exist: {dup}"


def test_required_code_templates_present():
    missing = [p for p in REQUIRED_CODE if not (CODE_TEMPLATES_DIR / p).exists()]
    assert not missing, f"Missing required code template files: {missing}"


def test_app_templates_exist():
    assert APP_TEMPLATES_DIR.exists(), f"App templates dir missing: {APP_TEMPLATES_DIR}"
    # At least one backend & one frontend template file
    backend = list(APP_TEMPLATES_DIR.glob('*backend*'))
    frontend = list(APP_TEMPLATES_DIR.glob('*frontend*'))
    assert backend and frontend, "Expected both backend and frontend app template files"
