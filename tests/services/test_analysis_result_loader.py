
import json
from pathlib import Path

from app.services.analysis_result_loader import AnalysisResultAggregator


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_iter_unified_files_skips_universal_and_service_snapshots(tmp_path):
    base = tmp_path / "results"
    task_dir = base / "demo_model" / "app1" / "analysis" / "task-main"
    task_dir.mkdir(parents=True, exist_ok=True)

    unified = task_dir / "demo_model_app1_task-main_20240101_120000.json"
    _write(unified, {})
    # Universal schema output should be ignored
    _write(task_dir / "demo_model_app1_task-main_universal.json", {})
    # Service snapshot should be ignored
    _write(task_dir / "services" / "demo_model_app1_static.json", {})

    aggregator = AnalysisResultAggregator(base)
    files = list(aggregator.iter_unified_files())
    assert len(files) == 1
    assert files[0].path == unified
    assert files[0].task_id == "main"
    assert files[0].app_number == 1


def test_iter_unified_files_applies_filters(tmp_path):
    base = tmp_path / "results"
    # Task A
    task_a = base / "demo_model" / "app1" / "analysis" / "task-a"
    _write(task_a / "demo_model_app1_task-a_20240101_120000.json", {})
    # Task B for different model/app
    task_b = base / "other_model" / "app2" / "analysis" / "task-b"
    _write(task_b / "other_model_app2_task-b_20240101_120000.json", {})

    aggregator = AnalysisResultAggregator(base)
    filtered = list(aggregator.iter_unified_files(model_slug="demo/model", app_number=1))
    assert len(filtered) == 1
    assert filtered[0].path.parent == task_a
