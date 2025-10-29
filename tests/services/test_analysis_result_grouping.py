import json
from pathlib import Path

import pytest

from app.services.analysis_result_loader import AnalysisResultAggregator
from app.services.result_file_service import ResultFileService


@pytest.fixture
def results_root(tmp_path: Path) -> Path:
    root = tmp_path / "results"
    root.mkdir()
    return root


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_grouped_task_listing_and_loading(results_root: Path) -> None:
    task_dir = results_root / "demo_model" / "app1" / "analysis" / "task_comprehensive"
    primary = task_dir / "demo_model_app1_task_comprehensive_20250101_000000.json"
    services_payload = {
        "metadata": {
            "model_slug": "demo_model",
            "app_number": 1,
            "analysis_type": "comprehensive",
            "timestamp": "2025-01-01T00:00:00+00:00",
        },
        "results": {
            "task": {
                "task_id": "comprehensive",
                "analysis_type": "comprehensive",
                "model_slug": "demo_model",
                "app_number": 1,
            },
            "summary": {
                "total_findings": 0,
                "services_executed": 1,
                "tools_used": [],
                "tools_executed": 0,
                "severity_breakdown": {"high": 0, "medium": 0, "low": 0},
                "status": "completed",
            },
            "services": {
                "static": {
                    "status": "success",
                    "analysis": {"tools_used": []},
                }
            },
            "findings": [],
        },
    }
    _write_json(primary, services_payload)

    snapshot = task_dir / "services" / "demo_model_app1_static.json"
    _write_json(
        snapshot,
        {
            "metadata": {
                "model_slug": "demo_model",
                "app_number": 1,
                "task_id": "comprehensive",
                "service_name": "static",
            },
            "results": services_payload["results"]["services"]["static"],
        },
    )

    service = ResultFileService(base_dir=results_root)
    descriptors = service.list_results()
    assert len(descriptors) == 1
    descriptor = descriptors[0]
    assert descriptor.model_slug == "demo_model"
    assert descriptor.app_number == 1
    # Ensure payload comes back with services populated
    _, payload = service.load_result_by_identifier(descriptor.identifier)
    assert payload["results"]["services"]["static"]["status"] == "success"


def test_rebuild_from_service_snapshots(results_root: Path) -> None:
    task_dir = results_root / "demo_model" / "app2" / "analysis" / "task_comprehensive"
    snapshot = task_dir / "services" / "demo_model_app2_dynamic.json"
    _write_json(
        snapshot,
        {
            "metadata": {
                "model_slug": "demo_model",
                "app_number": 2,
                "task_id": "comprehensive",
                "service_name": "dynamic",
            },
            "results": {
                "status": "success",
                "analysis": {"tools_used": ["curl"], "findings": []},
            },
        },
    )

    aggregator = AnalysisResultAggregator(results_root)
    payload = aggregator.build_payload_from_services(task_dir)
    assert payload is not None
    assert payload["metadata"]["analysis_type"] == "comprehensive"
    assert payload["results"]["services"]["dynamic"]["status"] == "success"
    assert payload["results"]["summary"]["services_executed"] == 1


def test_related_service_files_prefers_task_snapshots(results_root: Path) -> None:
    analysis_dir = results_root / "slug" / "app3" / "analysis"
    legacy = analysis_dir / "slug_app3_performance_20250101_000000.json"
    _write_json(
        legacy,
        {
            "metadata": {
                "model_slug": "slug",
                "app_number": 3,
                "analysis_type": "performance",
                "timestamp": "2025-01-01T00:00:00+00:00",
            },
            "results": {
                "services": {
                    "performance": {
                        "status": "success",
                        "analysis": {"tools_used": []},
                    }
                }
            },
        },
    )

    snapshot = analysis_dir / "task_comprehensive" / "services" / "slug_app3_performance.json"
    _write_json(
        snapshot,
        {
            "metadata": {
                "model_slug": "slug",
                "app_number": 3,
                "task_id": "comprehensive",
                "service_name": "performance",
            },
            "results": {
                "status": "success",
                "analysis": {"tools_used": ["locust"]},
            },
        },
    )

    service = ResultFileService(base_dir=results_root)
    related = service._find_related_service_files("slug", 3)
    assert "performance" in related
    assert related["performance"] == snapshot
