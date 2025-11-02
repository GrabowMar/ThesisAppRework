import datetime

from app.tasks import _seconds_between


def test_seconds_between_handles_naive_and_aware():
    naive_start = datetime.datetime(2024, 1, 1, 12, 0, 0)
    aware_end = datetime.datetime(2024, 1, 1, 12, 0, 5, tzinfo=datetime.timezone.utc)

    duration = _seconds_between(aware_end, naive_start)

    assert duration == 5.0


def test_seconds_between_returns_none_when_missing_values():
    aware = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    assert _seconds_between(None, aware) is None
    assert _seconds_between(aware, None) is None
