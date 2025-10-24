import json
from pathlib import Path

import pytest

from app.services.result_file_service import ResultFileService


@pytest.fixture()
def result_base_dir(tmp_path: Path) -> Path:
    base = tmp_path / "results"
    analysis_dir = base / "demo_model" / "app1" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    def _write(name: str, service: str, total_findings: int) -> None:
        payload = {
            "metadata": {
                "model_slug": "demo/model",
                "app_number": 1,
                "analysis_type": "unified",
                "timestamp": "2025-01-01T10:10:10Z",
            },
            "results": {
                "summary": {
                    "total_findings": total_findings,
                    "tools_executed": 1,
                    "tools_used": [f"{service}-tool"],
                    "severity_breakdown": {"high": total_findings, "medium": 0, "low": 0},
                    "status": "completed",
                },
                "services": {
                    service: {
                        "service": f"{service}-analyzer",
                        "status": "success",
                    }
                },
                "findings": [{"service": service, "message": f"issue-{service}"}],
                "tools": {f"{service}-tool": {"status": "success"}},
                "raw_outputs": {service: {"status": "success"}},
            },
        }
        path = analysis_dir / name
        path.write_text(json.dumps(payload), encoding="utf-8")

    _write("demo_model_app1_static_20250101_101010.json", "static", 3)
    _write("demo_model_app1_dynamic_20250101_101015.json", "dynamic", 5)
    _write("demo_model_app1_performance_20250101_101020.json", "performance", 7)
    _write("demo_model_app1_ai_20250101_101025.json", "ai", 11)
    return base


def test_load_result_merges_related_services(result_base_dir: Path) -> None:
    service = ResultFileService(base_dir=result_base_dir)

    descriptor, payload = service.load_result_by_identifier("demo_model_app1_static_20250101_101010")

    services = payload["results"]["services"]
    assert sorted(services.keys()) == ["ai", "dynamic", "performance", "static"]

    summary = payload["results"]["summary"]
    assert summary["services_executed"] == 4
    assert summary["total_findings"] == 3 + 5 + 7 + 11
    assert "ai-tool" in summary["tools_used"]

    assert descriptor.total_findings == 3 + 5 + 7 + 11
    assert descriptor.tools_executed == 4
    assert descriptor.severity_breakdown.get("high") == 3 + 5 + 7 + 11
*** End File