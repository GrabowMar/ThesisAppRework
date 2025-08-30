from app.services.batch_service import batch_service, BatchAnalysisService


class DummySocketIO:
    def __init__(self):
        self.events = []

    def emit(self, event, data, room=None):  # signature subset
        self.events.append({'event': event, 'data': data, 'room': room})


def _install_dummy_socketio(service: BatchAnalysisService) -> DummySocketIO:
    dummy = DummySocketIO()

    # Monkey patch the internal _emit to bypass import of extensions.socketio
    def _emit(event, payload):  # noqa: D401
        dummy.emit(event, payload)

    service._emit = _emit  # type: ignore
    return dummy


def test_event_sequence_normal_job(app):
    svc = batch_service
    dummy = _install_dummy_socketio(svc)

    # Create a job with no cache hits (unique options)
    job_id = svc.create_job(
        name="WS Normal",
        description="Normal path",
        analysis_types=["static"],  # maps to code_quality
        models=["anthropic_claude-3.7-sonnet"],
        app_range_str="1",
        options={"unique": "x"},
    )

    # Start job (queue stub auto-starts when enqueued; manually start if still pending)
    svc.start_job(job_id)

    # Simulate task completion
    svc.update_task_progress(job_id, task_completed=True)

    # Collect event names in order
    events = [e['event'] for e in dummy.events]

    # Expect at least created, queue_depth_update, started, task_progress, batch_completed (order may interleave depth update)
    assert 'batch_created' in events
    assert 'batch_started' in events
    assert 'task_progress' in events
    assert 'batch_completed' in events


def test_event_sequence_cache_only_job(app, monkeypatch):
    svc = batch_service
    dummy = _install_dummy_socketio(svc)

    # Pre-populate cache by storing result directly via cache service
    from app.services.batch_result_cache_service import batch_result_cache
    parts = ("code_quality", "anthropic_claude-3.7-sonnet", 1, {"depth": 1})
    batch_result_cache.store_result(parts, {"summary": "ok"}, ttl_seconds=30)

    svc.create_job(
        name="WS CacheOnly",
        description="All cached path",
        analysis_types=["static"],
        models=["anthropic_claude-3.7-sonnet"],
        app_range_str="1",
        options={"depth": 1},
    )

    # Cache-only jobs should emit created then completed (no started)
    events = [e['event'] for e in dummy.events]
    assert 'batch_created' in events
    assert 'batch_completed' in events
    # Should not have started event for cache-only immediate completion
    assert 'batch_started' not in events
