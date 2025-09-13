"""Minimal tests for ToolRegistryService custom analysis and execution plan."""
from __future__ import annotations

from typing import List

from app.services.tool_registry_service import ToolRegistryService
from app.models.tool_registry import CustomAnalysisRequest
from app.models import GeneratedApplication
from app.extensions import db


def _make_tool_via_service(svc: ToolRegistryService, name: str, service: str, category: str = "security", compat: List[str] | None = None, duration: int | None = None) -> int:
    created = svc.create_tool({
        'name': name,
        'display_name': name.title(),
        'description': f'Tool {name}',
        'category': category,
        'compatibility': compat or ['python'],
        'service_name': service,
        'command': f'{name} --run',
        'is_enabled': True,
        'estimated_duration': duration or 0,
    })
    return int(created['id'])


def test_create_custom_analysis_custom_mode_happy(app, db_session):
    # Ensure a GeneratedApplication exists
    app_rec = GeneratedApplication()
    setattr(app_rec, 'model_slug', 'test-model')
    setattr(app_rec, 'app_number', 1)
    setattr(app_rec, 'app_type', 'web')
    setattr(app_rec, 'provider', 'openrouter')
    db.session.add(app_rec)

    svc = ToolRegistryService()
    # Two tools via service
    t1_id = _make_tool_via_service(svc, 'talpha', service='static-analyzer', duration=60)
    t2_id = _make_tool_via_service(svc, 'tbeta', service='dynamic-analyzer', duration=90)
    db.session.commit()

    result = svc.create_custom_analysis(
        model_slug="test-model",
        app_number=1,
        analysis_mode="custom",
        tool_ids=[t1_id, t2_id],
        priority="normal",
    )

    assert isinstance(result, dict)
    assert result.get("id") is not None
    assert result.get("request_name")
    assert result.get("custom_tools") is not None
    assert len(result["custom_tools"]) == 2

    # Check DB row
    req = CustomAnalysisRequest.query.get(result["id"])  # type: ignore[arg-type]
    assert req is not None
    assert isinstance(req.custom_tools, list)


def test_execution_plan_grouped_by_service(app, db_session):
    # Ensure app
    app_rec = GeneratedApplication()
    setattr(app_rec, 'model_slug', 'test-model')
    setattr(app_rec, 'app_number', 1)
    setattr(app_rec, 'app_type', 'web')
    setattr(app_rec, 'provider', 'openrouter')
    db.session.add(app_rec)

    svc = ToolRegistryService()
    t1_id = _make_tool_via_service(svc, 'talpha2', service='static-analyzer', duration=30)
    t2_id = _make_tool_via_service(svc, 'tbeta2', service='dynamic-analyzer', duration=45)
    db.session.commit()

    result = svc.create_custom_analysis(
        model_slug="test-model",
        app_number=1,
        analysis_mode="custom",
        tool_ids=[t1_id, t2_id],
    )

    plan = svc.get_analysis_execution_plan(result["id"])  # type: ignore[index]
    services = plan.get("services", {})

    assert set(services.keys()) == {"static-analyzer", "dynamic-analyzer"}
    assert services["static-analyzer"]["estimated_duration"] >= 30
    assert services["dynamic-analyzer"]["estimated_duration"] >= 45
