"""Batch scheduling service.

Responsible for evaluating `BatchSchedule` rows and enqueuing new batch jobs
based on their stored configuration. Supports both traditional 5-field cron
expressions (via `croniter`) and simple interval expressions of the form:

    interval:5m   -> every 5 minutes
    interval:30s  -> every 30 seconds
    interval:2h   -> every 2 hours

Design goals:
 - Stateless aside from DB persistence in `BatchSchedule`
 - Pure functions for time calculations to simplify unit testing
 - No background thread auto-start during tests (explicit `.run_once()`)
 - Defensive: any single schedule error is logged and does not abort loop

The scheduler does not perform advanced dependency/resource gating yet; it
delegates to the (currently minimal) `batch_service` for job creation and
immediate start/queue stub dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, Iterable

try:  # pragma: no cover - import guard
    from croniter import croniter  # type: ignore
except Exception:  # pragma: no cover
    croniter = None  # type: ignore

from flask import has_app_context  # type: ignore
from ..extensions import get_session, db  # type: ignore
from ..models import BatchSchedule  # type: ignore
from .batch_service import batch_service  # type: ignore  # circular safe (import at runtime)

logger = logging.getLogger(__name__)


@dataclass
class ScheduleComputation:
    expression: str
    now: datetime
    next_run: Optional[datetime]
    error: Optional[str] = None


def _parse_interval(expr: str) -> Optional[timedelta]:
    """Parse interval expressions like `interval:5m` / `interval:30s` / `interval:2h`.

    Returns a timedelta or None if format invalid.
    """
    if not expr.startswith("interval:"):
        return None
    body = expr.split(":", 1)[1].strip()
    if not body:
        return None
    # number + unit
    num = ''
    unit = ''
    for ch in body:
        if ch.isdigit():
            num += ch
        else:
            unit += ch
    if not num or not unit:
        return None
    try:
        value = int(num)
    except ValueError:
        return None
    unit = unit.lower()
    if unit in ('s', 'sec', 'secs', 'second', 'seconds'):
        return timedelta(seconds=value)
    if unit in ('m', 'min', 'mins', 'minute', 'minutes'):
        return timedelta(minutes=value)
    if unit in ('h', 'hr', 'hrs', 'hour', 'hours'):
        return timedelta(hours=value)
    if unit in ('d', 'day', 'days'):
        return timedelta(days=value)
    return None


def compute_next_run(expression: str, from_time: datetime) -> ScheduleComputation:
    """Compute next run time for a schedule expression.

    Supports either cron (5-field) or interval expressions. If croniter is not
    available, cron expressions produce an error. Interval parsing does not
    require croniter.
    """
    expr = expression.strip()
    now = from_time
    # Interval syntax
    interval_td = _parse_interval(expr)
    if interval_td:
        return ScheduleComputation(expr, now, now + interval_td)
    # Cron syntax
    if croniter is None:
        return ScheduleComputation(expr, now, None, error="croniter_not_installed")
    try:
        itr = croniter(expr, now)
        nxt = itr.get_next(datetime)
        return ScheduleComputation(expr, now, nxt)
    except Exception as e:  # pragma: no cover - malformed cron
        return ScheduleComputation(expr, now, None, error=str(e))


class BatchSchedulerService:
    """Service that processes due `BatchSchedule` rows.

    Usage (manual / tests):
        scheduler = BatchSchedulerService()
        scheduler.run_once()  # evaluates now

    In production a future enhancement may launch a background thread invoking
    `run_forever()` with sleep intervals; for now we keep explicit control.
    """

    def __init__(self, evaluation_limit: int = 100):
        self.evaluation_limit = evaluation_limit
        self.logger = logger

    def _due_schedules(self, now: datetime) -> Iterable[BatchSchedule]:  # pragma: no cover - simple generator
        with get_session() as session:
            qry = (session.query(BatchSchedule)
                   .filter(BatchSchedule.enabled.is_(True))
                   .order_by(BatchSchedule.next_run.asc().nullsfirst())
                   .limit(self.evaluation_limit))
            for sched in qry:
                # If next_run is None, treat as immediately due to seed next_run
                if sched.next_run is None or (sched.next_run <= now):
                    yield sched

    def run_once(self, now: Optional[datetime] = None) -> int:
        """Evaluate schedules due at `now` (UTC) and enqueue new batches.

        Returns number of schedules executed.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        executed = 0
        # Use existing app context session if present (important for tests with sqlite:///:memory:)
        if has_app_context():
            session = db.session
            rows = (session.query(BatchSchedule)
                    .filter(BatchSchedule.enabled.is_(True))
                    .limit(self.evaluation_limit)
                    .all())
            for sched in rows:
                if sched.next_run and sched.next_run > now:
                    continue
                comp = compute_next_run(sched.cron_expression, now)
                if comp.error:
                    self.logger.warning("Schedule %s parse error %s", sched.id, comp.error)
                    sched.next_run = now + timedelta(minutes=5)
                    continue
                cfg = sched.get_batch_config()
                try:
                    name = cfg.get('name') or f"sched_{sched.id}_{int(now.timestamp())}"
                    description = cfg.get('description', f"Scheduled run {sched.id}")
                    analysis_types = cfg.get('analysis_types', [])
                    models = cfg.get('models', [])
                    app_range = cfg.get('app_range', '1')
                    options = cfg.get('options') or {}
                    batch_id = batch_service.create_job(name, description, analysis_types, models, app_range, options)
                    batch_service.queue_manager.enqueue(batch_id, priority=cfg.get('priority', 'normal'))
                    executed += 1
                    sched.last_run = now
                    sched.next_run = comp.next_run
                except Exception as e:  # pragma: no cover
                    self.logger.exception("Failed executing schedule %s: %s", sched.id, e)
                    sched.next_run = now + timedelta(minutes=1)
            session.commit()
        else:
            with get_session() as session:
                rows = (session.query(BatchSchedule)
                        .filter(BatchSchedule.enabled.is_(True))
                        .limit(self.evaluation_limit)
                        .all())
                for sched in rows:
                    if sched.next_run and sched.next_run > now:
                        continue
                    comp = compute_next_run(sched.cron_expression, now)
                    if comp.error:
                        self.logger.warning("Schedule %s parse error %s", sched.id, comp.error)
                        sched.next_run = now + timedelta(minutes=5)
                        session.add(sched)
                        continue
                    cfg = sched.get_batch_config()
                    try:
                        name = cfg.get('name') or f"sched_{sched.id}_{int(now.timestamp())}"
                        description = cfg.get('description', f"Scheduled run {sched.id}")
                        analysis_types = cfg.get('analysis_types', [])
                        models = cfg.get('models', [])
                        app_range = cfg.get('app_range', '1')
                        options = cfg.get('options') or {}
                        batch_id = batch_service.create_job(name, description, analysis_types, models, app_range, options)
                        batch_service.queue_manager.enqueue(batch_id, priority=cfg.get('priority', 'normal'))
                        executed += 1
                        sched.last_run = now
                        sched.next_run = comp.next_run
                        session.add(sched)
                    except Exception as e:  # pragma: no cover
                        self.logger.exception("Failed executing schedule %s: %s", sched.id, e)
                        sched.next_run = now + timedelta(minutes=1)
                        session.add(sched)
                session.commit()
        return executed

    # Placeholder for future background loop (not started automatically)
    def run_forever(self, interval_seconds: int = 30):  # pragma: no cover - not used in tests
        import time
        while True:
            try:
                self.run_once()
            except Exception:  # noqa: E722
                self.logger.exception("Scheduler iteration failed")
            time.sleep(interval_seconds)


# Singleton (lazy used by batch_service if present)
batch_scheduler_service = BatchSchedulerService()

__all__ = [
    'BatchSchedulerService',
    'batch_scheduler_service',
    'compute_next_run',
    'ScheduleComputation',
]
