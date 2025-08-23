import pytest
from flask import render_template_string
from app.factory import create_app

@pytest.fixture(scope="module")
def app():
    app = create_app('test')
    app.config['TESTING'] = True
    with app.app_context():
        yield app


def test_include_comparison_matrix(app):
    # This include uses a legacy path that should remap via loader to pages/models/partials/comparison_matrix.html
    tpl = """{% include 'partials/models/comparison_matrix.html' %}"""
    html = render_template_string(tpl)
    assert 'comparison' in html.lower() or 'model' in html.lower()


def test_include_active_tasks(app):
    # Legacy include path should resolve via mapping to pages/analysis/partials/active_tasks.html
    tpl = """{% include 'partials/analysis/list/active_tasks.html' %}"""
    html = render_template_string(tpl, active_tasks=[])
    # Basic smoke assertion: template rendered (not empty) and did not raise TemplateNotFound
    assert html.strip() != ''
