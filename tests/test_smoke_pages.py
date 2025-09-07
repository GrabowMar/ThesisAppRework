"""Simple smoke tests for key page endpoints after header removal refactor.

Ensures critical pages render (HTTP 200) instead of 500 due to stale template
macro references or missing templates.
"""
from http import HTTPStatus

def test_sample_generator_page(client):
    resp = client.get('/sample-generator/')
    assert resp.status_code == HTTPStatus.OK, resp.text[:200]
    # Basic content sanity (title heading now plain h2)
    assert b'Sample Generator' in resp.data


def test_reports_page(client):
    resp = client.get('/reports/')
    # After route fix this should render index_main.html
    assert resp.status_code == HTTPStatus.OK, resp.text[:200]
    # Loose keyword expected on reports landing (adapt if template changes)
    assert b'Reports' in resp.data or b'files' in resp.data.lower()
