import os
import sys
from flask import Flask

# Ensure 'src' is on path (handles running pytest from project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from app.routes.response_utils import json_success, json_error, handle_exceptions  # noqa: E402


def make_app():
    app = Flask(__name__)

    @app.route('/ok')
    @handle_exceptions()
    def ok():
        return json_success({"value": 1}, message="Works")

    @app.route('/boom')
    @handle_exceptions()
    def boom():
        raise RuntimeError("Kaboom")

    return app


def test_json_success_structure():
    app = make_app()
    with app.test_client() as c:
        rv = c.get('/ok')
        assert rv.status_code == 200
        data = rv.get_json()
        assert data['ok'] is True
        assert data['data'] == {"value": 1}
        assert data['message'] == 'Works'
        assert data['error'] is None


def test_exception_decorator_returns_json_error():
    app = make_app()
    with app.test_client() as c:
        rv = c.get('/boom')
        assert rv.status_code == 500
        data = rv.get_json()
        assert data['ok'] is False
        assert data['error']['type'] == 'RuntimeError'
        assert 'Kaboom' in data['error']['details']['detail'] or 'Kaboom' in data['error']['details'].get('detail','')


def test_json_error_helper():
    app = Flask(__name__)
    with app.app_context():
        resp, status = json_error('Invalid', status=422, error_type='ValidationError')
        assert status == 422
        payload = resp.get_json()
        assert payload['ok'] is False
        assert payload['error']['type'] == 'ValidationError'
