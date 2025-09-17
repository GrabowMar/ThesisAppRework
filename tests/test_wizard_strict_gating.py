import pytest
from unittest.mock import patch


def _get_bandit_tool_id():
    from app.services.service_locator import ServiceLocator
    svc = ServiceLocator.get_tool_registry_service()
    assert svc is not None
    # Ensure builtin tools are initialized and fetch by name
    bandit = None
    try:
        bandit = svc.get_tool_by_name('bandit')  # type: ignore[attr-defined]
    except Exception:
        bandit = None
    if not bandit:
        # Fall back to scanning all tools (numeric IDs only)
        tools = svc.get_all_tools(enabled_only=True)  # type: ignore[attr-defined]
        for t in tools:
            if str(t.get('name')).lower() == 'bandit' and isinstance(t.get('id'), int):
                bandit = t
                break
    assert bandit and isinstance(bandit.get('id'), int), 'Bandit tool with numeric id must exist'
    return int(bandit['id'])


@pytest.mark.api
@pytest.mark.db
def test_wizard_rejects_unavailable_tool_strict(client, db_session):
    # Create required application entity
    from tests.conftest import create_test_generated_application
    create_test_generated_application(db_session, model_slug='test-model', app_number=1)

    bandit_id = _get_bandit_tool_id()

    # Patch analyzer availability to report no tools available in static-analyzer
    with patch('app.services.analyzer_integration.get_available_toolsets', return_value={'static-analyzer': []}):
        resp = client.post(
            '/analysis/create',
            data={
                'model_slug': 'test-model',
                'app_number': '1',
                'analysis_mode': 'custom',
                'selected_tools[]': [str(bandit_id)],
                'priority': 'normal',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400
        # Optional: page should render and mention unavailable
        assert b'unavailable' in resp.data or b'could not create' in resp.data.lower()


@pytest.mark.api
@pytest.mark.db
def test_wizard_accepts_available_tool_creates_task(client, db_session):
    from tests.conftest import create_test_generated_application
    create_test_generated_application(db_session, model_slug='test-model', app_number=1)

    bandit_id = _get_bandit_tool_id()

    # Report bandit as available on static-analyzer
    with patch('app.services.analyzer_integration.get_available_toolsets', return_value={'static-analyzer': ['bandit']}):
        resp = client.post(
            '/analysis/create',
            data={
                'model_slug': 'test-model',
                'app_number': '1',
                'analysis_mode': 'custom',
                'selected_tools[]': [str(bandit_id)],
                'priority': 'normal',
            },
            follow_redirects=False,
        )
        # Should redirect to analysis list on success
        assert resp.status_code in (302, 303)
        assert '/analysis/list' in resp.headers.get('Location', '')

        # Task should be created
        from app.models import AnalysisTask
        count = AnalysisTask.query.count()
        assert count >= 1
