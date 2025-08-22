"""Tests for DISABLED_ANALYSIS_MODELS gating in Celery tasks.

These tests exercise the early-return skip logic without requiring a running
Celery worker. We import the task functions directly and call their .run()
implementation (Celery wraps .run inside Task.__call__). We monkeypatch the
environment before reloading the module to ensure the disabled set is built
with the desired model slug.
"""
from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType

import pytest

TARGET_MODEL = "test_model_a"


def _reload_tasks_with_env(disabled: str) -> ModuleType:
    os.environ["DISABLED_ANALYSIS_MODELS"] = disabled
    if "app.tasks" in sys.modules:
        del sys.modules["app.tasks"]
    import app.tasks  # type: ignore  # noqa: F401
    return importlib.import_module("app.tasks")


@pytest.mark.parametrize("task_name, kwargs", [
    ("security_analysis_task", {"model_slug": TARGET_MODEL, "app_number": 1, "tools": None, "options": None}),
    ("performance_test_task", {"model_slug": TARGET_MODEL, "app_number": 2, "test_config": None}),
    ("static_analysis_task", {"model_slug": TARGET_MODEL, "app_number": 3, "tools": None, "options": None}),
    ("dynamic_analysis_task", {"model_slug": TARGET_MODEL, "app_number": 4, "options": None}),
])
def test_tasks_skip_when_model_disabled(task_name: str, kwargs):
    tasks_mod = _reload_tasks_with_env(TARGET_MODEL)
    task_fn = getattr(tasks_mod, task_name)
    # Call underlying run implementation by accessing .run attribute if bound Task
    run_callable = getattr(task_fn, "run", task_fn)
    result = run_callable(**kwargs)
    assert result["status"] == "skipped"
    assert result["reason"] == "model_disabled"
    assert result["model_slug"] == TARGET_MODEL


@pytest.mark.parametrize("task_name, kwargs", [
    ("security_analysis_task", {"model_slug": TARGET_MODEL, "app_number": 1, "tools": None, "options": None}),
    ("performance_test_task", {"model_slug": TARGET_MODEL, "app_number": 2, "test_config": None}),
])
def test_tasks_execute_normally_when_not_disabled(task_name: str, kwargs, monkeypatch):
    tasks_mod = _reload_tasks_with_env("")  # empty disabled list
    # Monkeypatch _run_engine to return a deterministic minimal result
    def fake_run_engine(engine_name, model_slug, app_number, **k):  # noqa: ANN001
        return {"status": "completed", "summary": {}}
    monkeypatch.setattr(tasks_mod, "_run_engine", fake_run_engine)
    task_fn = getattr(tasks_mod, task_name)
    run_callable = getattr(task_fn, "run", task_fn)
    result = run_callable(**kwargs)
    assert result["status"] == "completed"
    assert result["model_slug"] == TARGET_MODEL
