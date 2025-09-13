"""Unit tests for progress event tool gating.

Verifies that when only a subset of tools is selected (e.g., Bandit),
the progress handler emits tool.started events only for those tools
and not for unselected ones like Pylint or MyPy.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List


class _DummyTask:
    def __init__(self, selected_tools: List[str]):
        self.task_id = "task-123"
        self._meta = {"selected_tools": selected_tools}
        self.progress_percentage = 0.0
        self.logs = ""

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._meta)

    def update_progress(self, pct: float, message: str) -> None:
        self.progress_percentage = pct


def test_progress_emits_only_selected_bandit(monkeypatch):
    # Import locally to avoid module import side-effects at collection time
    from app.services.analyzer_integration import AnalysisExecutor, ConnectionManager

    # Prepare executor (connection manager won't be used by this test)
    executor = AnalysisExecutor(ConnectionManager())

    # Create dummy task that selected only bandit
    task = _DummyTask(selected_tools=["bandit"])  # names, not IDs

    # Capture emitted events
    emitted: List[Dict[str, Any]] = []

    def _emit_task_event(event_type: str, payload: Dict[str, Any]) -> None:
        emitted.append({"type": event_type, **(payload or {})})

    # Patch emit_task_event used inside _handle_progress_message
    monkeypatch.setattr("app.realtime.task_events.emit_task_event", _emit_task_event, raising=False)

    # Simulate a progress update for python analysis stage which maps to bandit/pylint/mypy
    data = {
        "type": "progress",
        "stage": "python_analysis",
        "percentage": 42,
        "message": "Analyzing Python source",
    }

    asyncio.get_event_loop().run_until_complete(
        executor._handle_progress_message(data, task, None)
    )

    # Assert only a bandit tool.started event was emitted
    started = [e for e in emitted if e.get("type") == "task.tool.started"]
    assert any(e.get("tool") == "bandit" for e in started), "Expected bandit to be started"
    assert not any(e.get("tool") == "pylint" for e in started), "Pylint should not be started when unselected"
    assert not any(e.get("tool") == "mypy" for e in started), "MyPy should not be started when unselected"
