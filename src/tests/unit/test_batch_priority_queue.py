"""Priority queue & stats tests for batch service."""
from app.services.batch_service import batch_service, BatchAnalysisService

class DummySocketIO:
    def __init__(self):
        self.events = []
    def emit(self, event, data, room=None):
        self.events.append({'event': event, 'data': data, 'room': room})

def _install_dummy_socketio(service: BatchAnalysisService) -> DummySocketIO:
    dummy = DummySocketIO()
    def _emit(event, payload):
        dummy.emit(event, payload)
    service._emit = _emit  # type: ignore
    return dummy

def test_priority_dispatch_order(app):
    svc = batch_service
    dummy = _install_dummy_socketio(svc)
    # Ensure clean slate (jobs + queues)
    svc._reset_for_test()
    # Create three jobs with defer_start so they remain queued
    high = svc.create_job('High', 'high prio', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {'priority': 'high', 'defer_start': True, 'uniq':'h'})
    normal = svc.create_job('Normal', 'normal prio', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {'priority': 'normal', 'defer_start': True, 'uniq':'n'})
    low = svc.create_job('Low', 'low prio', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {'priority': 'low', 'defer_start': True, 'uniq':'l'})

    # Dispatch sequence should be high -> normal -> low
    first = svc.dispatch_next()
    second = svc.dispatch_next()
    third = svc.dispatch_next()
    assert [first, second, third] == [high, normal, low]

    # Verify started events correspond to those job IDs in order
    started_ids = [e['data']['batch_id'] for e in dummy.events if e['event'] == 'batch_started']
    assert started_ids == [high, normal, low]


def test_queue_depth_events_on_enqueue_and_dequeue(app):
    svc = batch_service
    dummy = _install_dummy_socketio(svc)
    svc._reset_for_test()

    svc.create_job('A', 'job A', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {'priority': 'low', 'defer_start': True, 'uniq':'a'})
    svc.create_job('B', 'job B', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {'priority': 'low', 'defer_start': True, 'uniq':'b'})

    # Expect at least two queue_depth_update events from enqueue
    enqueue_depths = [e['data']['total'] for e in dummy.events if e['event'] == 'queue_depth_update']
    assert max(enqueue_depths) >= 2

    svc.dispatch_next()  # start first
    svc.dispatch_next()  # start second

    # After dispatching both, queue total should reach 0 in some event
    totals = [e['data']['total'] for e in dummy.events if e['event'] == 'queue_depth_update']
    assert 0 in totals


def test_cancel_pending_job_removes_from_queue(app):
    svc = batch_service
    dummy = _install_dummy_socketio(svc)
    svc._reset_for_test()

    job_id = svc.create_job('Cancellable', 'will cancel', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {'priority': 'normal', 'defer_start': True, 'uniq':'c'})
    # Cancel before dispatch
    assert svc.cancel_job(job_id) is True
    status = svc.get_job_status(job_id)
    assert status and status['status'] == 'cancelled'

    # Ensure no started event for this job
    started_ids = [e['data']['batch_id'] for e in dummy.events if e['event'] == 'batch_started']
    assert job_id not in started_ids


def test_job_stats_cache_and_failure_rates(app):
    svc = batch_service
    _install_dummy_socketio(svc)
    svc._reset_for_test()

    # Create one cache-only job by pre-populating cache
    from app.services.batch_result_cache_service import batch_result_cache
    cache_parts = ("code_quality", "anthropic_claude-3.7-sonnet", 1, {"pre": 1})
    batch_result_cache.store_result(cache_parts, {"ok": True}, ttl_seconds=60)
    cached_id = svc.create_job('Cached', 'all cached', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {"pre": 1})

    # Create a normal job and simulate failure of its single task
    fail_id = svc.create_job('WillFail', 'simulate failure', ['static'], ['anthropic_claude-3.7-sonnet'], '1', {"uniq": "fail"})
    svc.start_job(fail_id)
    svc.update_task_progress(fail_id, task_failed=True)

    stats = svc.get_job_stats()
    # Two jobs total
    assert stats['total'] >= 2
    # At least one cache hit
    assert stats['cache_hit_rate'] > 0
    # Failure rate should be > 0 due to failed job
    assert stats['failure_rate'] > 0

    # Sanity: cached job status is completed
    cached_status = svc.get_job_status(cached_id)
    assert cached_status and cached_status['status'] == 'completed'