"""Validate TaskExecutionService tool resolution respects explicit selections.

Ensures that when a task metadata contains selected_tools=['bandit'],
the engine is invoked with exactly ['bandit'] and not augmented with
other defaults like pylint/mypy/eslint/stylelint.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List


class _DummyTask:
    def __init__(self, analysis_type: str, model_slug: str, app_number: int, selected_tools: List[str] | None):
        self.analysis_type = analysis_type
        self.target_model = model_slug
        self.target_app_number = app_number
        self.progress_percentage = 0.0
        self.task_id = "test_task_id"
        self._meta: Dict[str, Any] = {}
        if selected_tools is not None:
            # Store selected_tools in custom_options, matching route behavior
            self._meta["custom_options"] = {"selected_tools": selected_tools}
        # fields that may be updated during execution
        self.started_at = None
        self.completed_at = None
        self.status = None
        # Add missing attributes to match AnalysisTask interface
        self.id = 1
        self.description = "Test task"
        self.target_path = "/test/path"

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._meta)

    def set_metadata(self, md: Dict[str, Any]) -> None:
        self._meta = dict(md or {})
    
    def start_execution(self, worker: str | None = None) -> None:
        """Mock method to match AnalysisTask interface."""
        pass
    
    def complete_execution(self, success: bool = True, error_message: str | None = None) -> None:
        """Mock method to match AnalysisTask interface."""
        pass


def test_task_execution_passes_only_selected_tools(monkeypatch, app):
    from app.services.task_execution_service import TaskExecutionService

    with app.app_context():
        # Capture tools passed to engine.run
        seen_tools: List[str] | None = None

        class _FakeEngine:
            engine_name = "security"

            def run(self, model_slug: str, app_number: int, **kwargs):  # noqa: D401
                nonlocal seen_tools
                seen_tools = list(kwargs.get("tools") or [])
                # Return object with attributes accessed by service
                return SimpleNamespace(status="success", payload={"analysis": {"summary": {}}}, error=None)

        # Patch get_engine to return our fake
        monkeypatch.setattr("app.services.analysis_engines.get_engine", lambda name: _FakeEngine())

        # Create a dummy task with explicit selection
        task = _DummyTask("security", "x-ai_grok-code-fast-1", 1, selected_tools=["bandit"])

        svc = TaskExecutionService()
        result = svc._execute_real_analysis(task)

        # Sanity
        assert result.get("status") == "success"
        assert seen_tools is not None
        assert seen_tools == ["bandit"], f"Expected only ['bandit'], got {seen_tools}"
