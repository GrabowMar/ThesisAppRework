from app.factory import create_app


def create_test_client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_websocket_status_endpoint():
    client = create_test_client()
    resp = client.get('/api/websocket/status')
    assert resp.status_code in (200, 503)
    data = resp.get_json()
    assert isinstance(data, dict)


def test_websocket_analyses_endpoint():
    client = create_test_client()
    resp = client.get('/api/websocket/analyses')
    assert resp.status_code in (200, 503)


def test_websocket_test_endpoint():
    client = create_test_client()
    resp = client.post('/api/websocket/test', json={})
    # Should return 200 with a payload or 503 if service not available
    assert resp.status_code in (200, 503)


def test_websocket_start_and_cancel(monkeypatch):
    client = create_test_client()

    # If service not available, endpoints should 503 gracefully
    status = client.get('/api/websocket/status')
    if status.status_code == 503:
        return

    # Happy path: monkeypatch the websocket service inside the app components
    class DummyWS:
        def __init__(self):
            self.started = []
            self.cancelled = []
            self.events = []

        def get_status(self):
            return {'connected': True}

        def get_active_analyses(self):
            return []

        def start_analysis(self, data):
            self.started.append(data)
            return 'dummy-1'

        def cancel_analysis(self, aid):
            self.cancelled.append(aid)
            return True

        def get_event_log(self):
            return self.events

        def broadcast_message(self, event, data):
            self.events.append({'event': event, 'data': data})

    # Use app context to access components
    app = client.application
    with app.app_context():
        from app.extensions import get_components
        components = get_components()
        ws_service = components.websocket_service
        components.websocket_service = DummyWS()
        try:
            # Start
            resp = client.post('/api/websocket/analysis/start', json={
                'analysis_type': 'security', 'model_slug': 'm', 'app_number': 1
            })
            assert resp.status_code == 200
            aid = resp.get_json().get('analysis_id')
            assert aid == 'dummy-1'

            # Cancel
            resp = client.post(f'/api/websocket/analysis/{aid}/cancel')
            assert resp.status_code == 200

            # Broadcast
            resp = client.post('/api/websocket/broadcast', json={'event': 'hello', 'message': 'hi', 'data': {'x': 1}})
            assert resp.status_code == 200
        finally:
            components.websocket_service = ws_service
