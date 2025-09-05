import time

from app.services.task_service import task_service
from app.constants import AnalysisType
from app.models import AnalyzerConfiguration


def test_task_events_emitted(app):
    """Creating tasks and running executor should produce realtime events."""
    from app.realtime.task_events import get_recent_events, clear_events
    clear_events()
    with app.app_context():
        # Ensure analyzer config exists
        if not AnalyzerConfiguration.query.first():
            from app.extensions import db
            cfg = AnalyzerConfiguration()
            cfg.name = "Cfg"
            cfg.analyzer_type = list(AnalysisType)[0]
            cfg.config_data = "{}"
            db.session.add(cfg)
            db.session.commit()

        task = task_service.create_task(
            model_slug="modelZ",
            app_number=1,
            analysis_type=list(AnalysisType)[0].value,
        )
        # task.created event present
        created_events = [e for e in get_recent_events() if e["event"] == "task.created" and e["data"]["task_id"] == task.task_id]
        assert created_events, "Expected task.created event"

        # Advance deterministically
        from app.services.task_execution_service import task_execution_service
        deadline = time.time() + 3
        while time.time() < deadline:
            task_execution_service.process_once(limit=5)
            done_events = [e for e in get_recent_events() if e["event"] == "task.completed" and e["data"]["task_id"] == task.task_id]
            if done_events:
                break
            time.sleep(0.05)

        done_events = [e for e in get_recent_events() if e["event"] == "task.completed" and e["data"]["task_id"] == task.task_id]
        assert done_events, "Expected task.completed event"
        assert done_events[-1]["data"]["progress_percentage"] == 100.0
