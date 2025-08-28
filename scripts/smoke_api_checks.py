"""Run simple in-process smoke checks against app routes using the Flask test client."""
import sys
from pathlib import Path

# Ensure src is on sys.path
repo_root = Path(__file__).resolve().parent.parent
src_path = str(repo_root / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from app.factory import create_app

app = create_app()
with app.test_client() as c:
    resp = c.get('/api/models/all')
    print('GET /api/models/all', resp.status_code, (resp.get_json() or {}).get('statistics', {}))

    resp2 = c.post('/api/models/load-openrouter')
    print('POST /api/models/load-openrouter', resp2.status_code, resp2.get_json())
