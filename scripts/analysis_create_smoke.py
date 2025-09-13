"""Smoke test for /analysis/create route.

Starts a Flask app in-process and simulates the Analysis Creation Wizard
submission in custom mode. Verifies that the POST does not return 500 and
preferably redirects to the analysis list.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    # Ensure src on path
    repo_root = Path(__file__).resolve().parent.parent
    src_path = str(repo_root / 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Be strict about using celery websocket in case any WS status is invoked
    os.environ.setdefault('WEBSOCKET_STRICT_CELERY', 'true')
    os.environ.setdefault('WEBSOCKET_SERVICE', 'celery')

    from app.factory import create_app
    from app.models import GeneratedApplication
    from app.services.model_service import ModelService
    from app.services.tool_registry_service import ToolRegistryService

    app = create_app('test')

    model_slug = 'x-ai_grok-code-fast-1'
    app_number = 1

    with app.app_context():
        # Ensure a GeneratedApplication exists for our target
        exists = GeneratedApplication.query.filter_by(
            model_slug=model_slug, app_number=app_number
        ).first()
        if not exists:
            ms = ModelService(app)
            ms.populate_database_from_files()

        # Initialize tool registry and get two enabled tools
        trs = ToolRegistryService()
        tools = trs.get_all_tools(enabled_only=True)
        if len(tools) < 1:
            print('No tools available from Tool Registry; cannot perform custom analysis POST')
            return 2
        tool_ids = [t['id'] for t in tools[:2]]

        # Use Flask test client to simulate form submission
        client = app.test_client()
        # Initial GET should be 200
        get_resp = client.get('/analysis/create')
        print('GET /analysis/create:', get_resp.status_code)

        data = {
            'model_slug': model_slug,
            'app_number': str(app_number),
            'analysis_mode': 'custom',
            'priority': 'normal',
        }
        # Multiple selected_tools[] entries
        for tid in tool_ids:
            data.setdefault('selected_tools[]', [])
            data['selected_tools[]'].append(str(tid))

        post_resp = client.post('/analysis/create', data=data, follow_redirects=False)
        print('POST /analysis/create:', post_resp.status_code)

        # Accept 302 redirect as success; 200 is also acceptable if page re-renders without server error
        if post_resp.status_code >= 500:
            try:
                print('Body (truncated):', post_resp.get_data(as_text=True)[:400])
            except Exception:
                pass
            return 1

        # Optionally verify Location header for redirect
        if post_resp.status_code in (301, 302, 303, 307, 308):
            loc = post_resp.headers.get('Location', '')
            print('Redirect Location:', loc)

        print('Analysis create smoke OK')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
