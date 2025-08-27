from __future__ import annotations

import os
import sys
import pytest
from flask import Flask

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from app.extensions import db  # type: ignore  # noqa: E402
from app.models import BatchAnalysis  # type: ignore  # noqa: E402
from app.routes.batch import batch_bp  # type: ignore  # noqa: E402


@pytest.fixture()
def app_ctx():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_ENABLED=False,
    )
    db.init_app(app)
    app.register_blueprint(batch_bp)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def test_queue_create_and_status(app_ctx: Flask):
    client = app_ctx.test_client()
    payload = {
        'create': {
            'name': 'Test Batch',
            'description': 'Via test',
            'analysis_types': ['security'],
            'models': ['m1'],
            'app_range': '1',
            'options': {}
        },
        'priority': 'high'
    }
    rv = client.post('/batch/api/batch/queue', json=payload)
    assert rv.status_code == 200, rv.get_data(as_text=True)
    data = rv.get_json()
    assert data['success'] is True
    batch_id = data['batch_id']
    # Queue status
    q = client.get('/batch/api/batch/queue/status')
    assert q.status_code == 200
    qd = q.get_json()
    assert 'depths' in qd
    # Cancel
    cancel = client.post(f'/batch/api/batch/{batch_id}/cancel')
    assert cancel.status_code == 200


def test_template_save_list_get(app_ctx: Flask):
    client = app_ctx.test_client()
    cfg = {'analysis_types': ['security','performance'], 'models': ['m1','m2'], 'app_range': '1-2'}
    rv = client.post('/batch/api/batch/template', json={'name': 'base', 'config': cfg, 'description': 'desc'})
    assert rv.status_code == 200
    tpl = rv.get_json()['template']
    assert tpl['name'] == 'base'
    # list
    lst = client.get('/batch/api/batch/template/list')
    assert lst.status_code == 200
    assert any(t['name'] == 'base' for t in lst.get_json()['templates'])
    # get
    single = client.get('/batch/api/batch/template/base')
    assert single.status_code == 200
    assert single.get_json()['name'] == 'base'


def test_analytics_and_report_paths(app_ctx: Flask):
    client = app_ctx.test_client()
    # Create bare batch directly
    b = BatchAnalysis()
    b.batch_id = 'b1'
    b.total_tasks = 10
    db.session.add(b)
    db.session.commit()
    # analytics
    a = client.get('/batch/api/batch/analytics')
    assert a.status_code == 200
    # report (should 404 until batch exists with metrics but we created one -> should 200)
    r = client.get('/batch/api/batch/b1/report')
    # It will list found batch; resource usage empty
    assert r.status_code == 200
    rep = r.get_json()
    assert rep['batch_id'] == 'b1'
