import os
import pytest
from app.services.sample_generation_service import get_sample_generation_service, Template

@pytest.fixture
def svc():
    # Ensure no real API key so mock path is used
    os.environ['OPENROUTER_API_KEY'] = ''
    service = get_sample_generation_service()
    # Reset internal registries for isolation
    service.template_registry.templates.clear()
    service.port_allocator.reset()
    service._results.clear()
    return service


def _add_template(service, app_num=1, name="mini_api"):
    t = Template(app_num=app_num, name=name, content="Return a hello world endpoint", requirements=["Flask"])
    service.template_registry.templates.append(t)
    return t


def test_single_generation_minimax_mock(svc):
    _add_template(svc, app_num=1, name="mini_api")
    # Use a minimax style model slug to ensure provider parsing & capability detection
    model = "minimax/minimax-12b-chat:free"
    import asyncio
    result_id, result = asyncio.run(svc.generate_async("1", model))

    assert result.success
    assert result.extracted_blocks, "Should extract at least one code block"
    block = result.extracted_blocks[0]
    assert block.backend_port is not None
    # Ensure saving happened
    structure = svc.project_structure()
    # model name sanitized replaces '/' with '_'
    assert any('app1' in apps for apps in structure.values())


def test_batch_generation_two_apps_minimax(svc):
    _add_template(svc, app_num=1, name="mini_api_one")
    _add_template(svc, app_num=2, name="mini_api_two")

    model = "minimax/minimax-12b-chat"
    # Run batch with parallel=1 to simplify
    import asyncio
    res = asyncio.run(svc.generate_batch_async(["1", "2"], [model], parallel_workers=1))
    assert 'results' in res
    assert len(res['results']) == 2
    assert all(r['success'] for r in res['results'])
    # Ports for app1 and app2 should differ
    ports = {b['backend_port'] for r in res['results'] for b in r['extracted_blocks'] if b['backend_port'] is not None}
    assert len(ports) >= 2, "Distinct ports expected for different apps"


def test_project_structure_reflects_minimax_results(svc):
    _add_template(svc, app_num=1, name="mini_port_check")
    import asyncio
    asyncio.run(svc.generate_async("1", "minimax/minimax-12b-chat"))
    structure = svc.project_structure()
    # Should contain a folder for minimax model sanitized
    found = False
    for model_folder, apps in structure.items():
        if model_folder.startswith('minimax_minimax-12b-chat'):
            assert 'app1' in apps
            found = True
    assert found, f"Structure missing minimax model folder: {structure}"
