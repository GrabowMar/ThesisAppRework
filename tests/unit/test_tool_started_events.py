import uuid
import asyncio
from app.models import db, AnalysisTask, AnalyzerConfiguration
from app.constants import AnalysisType, JobPriority as Priority
from app.services.analyzer_integration import analysis_executor
from app.realtime.task_events import clear_events, get_recent_events


def test_tool_started_events_from_progress(app):
    with app.app_context():
        clear_events()
        cfg = AnalyzerConfiguration()
        cfg.name = "cfg-tool-start"
        cfg.analyzer_type = AnalysisType.SECURITY_BACKEND
        cfg.is_active = True
        cfg.config_data = '{}'
        db.session.add(cfg)
        db.session.commit()

        task = AnalysisTask()
        task.task_id = str(uuid.uuid4())
        task.analyzer_config_id = cfg.id
        task.analysis_type = AnalysisType.SECURITY_BACKEND
        task.priority = Priority.NORMAL
        task.target_model = "m"
        task.target_app_number = 1
        task.task_name = "Tool Start"
        db.session.add(task)
        db.session.commit()

        # Simulate stages that map to tools
        stages = [
            {"stage": "scanning_python", "percentage": 5, "message": "Scanning py"},
            {"stage": "scanning_js", "percentage": 25, "message": "Scanning js"},
            {"stage": "scanning_python", "percentage": 40, "message": "Still python"},  # duplicate should not emit repeated starts
        ]

        for payload in stages:
            asyncio.run(analysis_executor._handle_progress_message(payload, task))  # noqa: SLF001

    started_events = [e for e in get_recent_events() if e["event"] == "task.tool.started"]
    # Expect tools: bandit, pylint, mypy (from scanning_python once) and eslint, tsc from scanning_js
    tools = {e["data"]["tool"] for e in started_events}
    assert {"bandit", "pylint", "mypy", "eslint", "tsc"} <= tools
    # Ensure no duplicate bandit start events
    bandit_count = sum(1 for e in started_events if e["data"]["tool"] == "bandit")
    assert bandit_count == 1
