import uuid
from app.models import db, AnalysisTask, AnalyzerConfiguration
from app.constants import AnalysisType, JobPriority as Priority
from app.services.analyzer_integration import analysis_executor
from app.realtime.task_events import clear_events, get_recent_events


def test_tool_completion_events_emitted(app):
    with app.app_context():
        clear_events()
        cfg = AnalyzerConfiguration()
        cfg.name = "cfg-tool-events"
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
        task.target_model = "modelX"
        task.target_app_number = 1
        task.task_name = "Tool Events"
        db.session.add(task)
        db.session.commit()

        findings = [
            {"tool_name": "bandit", "title": "Issue A", "severity": "low"},
            {"tool_name": "bandit", "title": "Issue B", "severity": "medium"},
            {"tool_name": "pylint", "title": "Lint A", "severity": "low"},
        ]

        import asyncio
        asyncio.run(analysis_executor._store_findings(task, findings))  # noqa: SLF001
        db.session.commit()

    events = [e for e in get_recent_events() if e["event"] == "task.tool.completed"]
    # Expect one event per tool
    tool_map = {e["data"]["tool"]: e["data"] for e in events}
    assert tool_map["bandit"]["findings_count"] == 2
    assert tool_map["pylint"]["findings_count"] == 1
    assert all(d["total_findings_for_task"] == 3 for d in tool_map.values())
    # Severity breakdown present for bandit (low + medium)
    bb = tool_map["bandit"].get("severity_breakdown")
    assert bb and bb.get("low") == 1 and bb.get("medium") == 1
