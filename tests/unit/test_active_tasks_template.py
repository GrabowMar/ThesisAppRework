from flask import render_template_string


def _render_active_tasks(active):
    # Minimal Jinja render using the actual partial include path
    return render_template_string("""
        {% include 'partials/analysis/list/active_tasks.html' %}
    """, active=active)


def test_active_tasks_accepts_dict(app):
    with app.app_context():
        active = {
            'abc': {'id': 'abc', 'name': 'Job A', 'status': 'RUNNING', 'started_at': 'now'},
            'def': {'id': 'def', 'task_name': 'Job B', 'state': 'PENDING', 'start_time': 'now'},
        }
        html = _render_active_tasks(active)
        assert 'Job A' in html and 'Job B' in html


def test_active_tasks_accepts_list(app):
    with app.app_context():
        active = [
            {'id': 'ghi', 'name': 'Job C', 'status': 'RUNNING'},
            {'id': 'jkl', 'task_name': 'Job D', 'state': 'PENDING'},
        ]
        html = _render_active_tasks(active)
        assert 'Job C' in html and 'Job D' in html
