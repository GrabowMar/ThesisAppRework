"""Analysis Hub Route & Fragment Tests.

Ensures the reworked Analysis Hub page and HTMX fragment endpoints
return expected status codes and basic HTML scaffolding. Focuses on:
 - Full page /analysis/list
 - Recent tasks fragment
 - Stats fragment
 - Quick actions fragment
 - Active tasks placeholder

These are smoke-level tests (not deep ORM assertions) to guard
template path regressions.
"""

import pytest


@pytest.mark.smoke
class TestAnalysisHubPage:
    def test_analysis_hub_page(self, client):
        resp = client.get('/analysis/list')
        assert resp.status_code == 200
        # Should include page title marker
        assert b'Analysis Hub' in resp.data

    def test_recent_tasks_fragment(self, client):
        resp = client.get('/analysis/api/tasks/recent', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        # Table header or empty message
        assert b'ID' in resp.data or b'No analysis tasks yet' in resp.data

    def test_stats_fragment(self, client):
        resp = client.get('/analysis/api/stats', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        # Expect one of the labels
        assert b'Total Tasks' in resp.data

    def test_quick_actions_fragment(self, client):
        resp = client.get('/analysis/api/quick-actions', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'Create New Analysis' in resp.data

    def test_active_tasks_fragment(self, client):
        resp = client.get('/analysis/api/active-tasks', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'No active tasks' in resp.data
