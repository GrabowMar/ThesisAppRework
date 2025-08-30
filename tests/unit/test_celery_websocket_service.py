from datetime import datetime, timezone

# Import the service
from app.services.celery_websocket_service import CeleryWebSocketService


class DummySocketIO:
    def __init__(self):
        self.events = []

    def emit(self, event, data, room=None):
        self.events.append({'event': event, 'data': data, 'room': room})


def test_get_status_and_event_log():
    sio = DummySocketIO()
    svc = CeleryWebSocketService(socketio=sio)

    status = svc.get_status()
    assert status['connected'] is True
    assert status['service'] == 'celery_websocket'

    # Initially empty log
    assert isinstance(svc.get_event_log(), list)


def test_start_analysis_missing_fields():
    sio = DummySocketIO()
    svc = CeleryWebSocketService(socketio=sio)

    # Missing model_slug/app_number should raise and return None
    analysis_id = svc.start_analysis({'analysis_type': 'security'})
    assert analysis_id is None
    assert any(e['event'] == 'analysis_error' for e in sio.events)


def test_start_analysis_dispatch(monkeypatch):
    sio = DummySocketIO()
    svc = CeleryWebSocketService(socketio=sio)

    class DummyAsyncRes:
        def __init__(self):
            self.id = 'task-123'

    # Patch delay methods for each task to avoid real Celery
    class DummyTask:
        def delay(self, *args, **kwargs):
            return DummyAsyncRes()

    monkeypatch.setattr('app.services.celery_websocket_service.security_analysis_task', DummyTask())
    monkeypatch.setattr('app.services.celery_websocket_service.performance_test_task', DummyTask())
    monkeypatch.setattr('app.services.celery_websocket_service.static_analysis_task', DummyTask())
    monkeypatch.setattr('app.services.celery_websocket_service.ai_analysis_task', DummyTask())

    # Security
    aid = svc.start_analysis({'analysis_type': 'security', 'model_slug': 'm', 'app_number': 1})
    assert aid == 'task-123'
    assert any(e['event'] == 'analysis_started' for e in sio.events)

    # Performance
    aid = svc.start_analysis({'analysis_type': 'performance', 'model_slug': 'm', 'app_number': 1})
    assert aid == 'task-123'

    # Static
    aid = svc.start_analysis({'analysis_type': 'static', 'model_slug': 'm', 'app_number': 1})
    assert aid == 'task-123'

    # AI
    aid = svc.start_analysis({'analysis_type': 'ai', 'model_slug': 'm', 'app_number': 1})
    assert aid == 'task-123'


def test_cancel_analysis(monkeypatch):
    sio = DummySocketIO()
    svc = CeleryWebSocketService(socketio=sio)

    # Add a fake active analysis
    svc.active_analyses['task-123'] = {
        'id': 'task-123', 'status': 'started', 'created_at': datetime.now(timezone.utc).isoformat()
    }

    class DummyControl:
        def revoke(self, *args, **kwargs):
            return True

    # Patch only the control object on the existing celery instance to avoid type issues
    svc.celery.control = DummyControl()

    assert svc.cancel_analysis('task-123') is True
    assert any(e['event'] == 'analysis_cancelled' for e in sio.events)


def test_broadcast_helpers():
    sio = DummySocketIO()
    svc = CeleryWebSocketService(socketio=sio)

    svc.broadcast_message('custom_event', {'x': 1})
    svc.send_to_analysis_room('abc', 'room_event', {'y': 2})

    events = [e['event'] for e in sio.events]
    assert 'custom_event' in events
    assert 'room_event' in events
