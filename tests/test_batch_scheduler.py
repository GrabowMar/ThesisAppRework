from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pytest
from flask import Flask

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from app.extensions import db  # type: ignore  # noqa: E402
from app.models import BatchSchedule, BatchAnalysis  # type: ignore  # noqa: E402
from app.services.batch_scheduler import batch_scheduler_service  # type: ignore  # noqa: E402
from app.services.batch_service import batch_service  # type: ignore  # noqa: E402


@pytest.fixture()
def app_ctx():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def test_interval_schedule_creates_batch(app_ctx: Flask):
    # interval schedule every 1 second
    sched = BatchSchedule()
    sched.cron_expression = 'interval:1s'
    sched.batch_config_json = '{"name":"SJob","analysis_types":["security"],"models":["m1"],"app_range":"1"}'
    db.session.add(sched)
    db.session.commit()
    executed = batch_scheduler_service.run_once(now=datetime.now(timezone.utc))
    assert executed == 1
    # A BatchAnalysis row should now exist (created by batch_service.create_job)
    assert db.session.query(BatchAnalysis).count() == 1
    # next_run should be populated in schedule
    db.session.refresh(sched)
    assert sched.next_run is not None


def test_cron_schedule_parsing(app_ctx: Flask):
    # Use a cron expression for every minute; set next_run None so it's due immediately
    sched = BatchSchedule()
    sched.cron_expression = '* * * * *'
    sched.batch_config_json = '{"name":"CJob","analysis_types":["security"],"models":["m1"],"app_range":"1"}'
    db.session.add(sched)
    db.session.commit()
    executed = batch_scheduler_service.run_once(now=datetime.now(timezone.utc))
    assert executed == 1
    db.session.refresh(sched)
    assert sched.last_run is not None
    assert sched.next_run is not None
    # Should have created a job and started it
    assert any(j for j in batch_service.jobs.values() if j.name.startswith('CJob'))
