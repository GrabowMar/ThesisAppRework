import pytest
from app.services.task_service import AnalysisTaskService

@pytest.mark.smoke
class TestTaskInspection:
    def test_tasks_inspection_page(self, client, app):
        resp = client.get('/analysis/tasks')
        assert resp.status_code == 200
        assert b'Analysis Tasks' in resp.data

    def test_tasks_inspection_fragment_empty(self, client):
        resp = client.get('/analysis/api/tasks/inspect/list', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        # Either no tasks or table header
        assert b'No tasks match filters' in resp.data or b'<table' in resp.data

    def test_task_detail_flow(self, client, app):
        # Create a task
        with app.app_context():
            t = AnalysisTaskService.create_task(model_slug='demo-model', app_number=1, analysis_type='security')
            task_id = t.task_id
        resp = client.get(f'/analysis/tasks/{task_id}')
        assert resp.status_code == 200
        assert task_id.encode() in resp.data
        # HTMX fragment
        frag = client.get(f'/analysis/api/tasks/{task_id}/detail', headers={'HX-Request': 'true'})
        assert frag.status_code == 200
        json_resp = client.get(f'/analysis/api/tasks/{task_id}/results.json')
        assert json_resp.status_code == 200
        assert b'"task_id"' in json_resp.data
