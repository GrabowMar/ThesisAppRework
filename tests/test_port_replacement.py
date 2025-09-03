import os
import asyncio
import pytest
from app.services.sample_generation_service import get_sample_generation_service, Template

@pytest.fixture
def svc():
    os.environ['OPENROUTER_API_KEY'] = ''  # force mock path
    service = get_sample_generation_service()
    # isolate state
    service.template_registry.templates.clear()
    service.port_allocator.reset()
    service._results.clear()
    return service

def add_template(service, content: str):
    t = Template(app_num=1, name="port_app", content=content, requirements=["Flask"])
    service.template_registry.templates.append(t)
    return t

MOCK_TEMPLATE = """
Simple flask app
""".strip()

# We simulate a generation response that would include a flask app with default port 5000.
# The service mock generation already produces such a block; we just invoke generate.

def test_port_replacement_flask_run(svc):
    add_template(svc, MOCK_TEMPLATE)
    result_id, result = asyncio.run(svc.generate_async("1", "mock/test-model"))
    assert result.success
    assert result.extracted_blocks, "Expected at least one extracted code block"
    backend_ports = {b.backend_port for b in result.extracted_blocks if b.backend_port}
    assert backend_ports, "Backend port should be assigned"
    # Ensure port literal '5000' was replaced in at least one block when code contains app.run(...5000...)
    replaced_detected = False
    for b in result.extracted_blocks:
        if b.port_replacements.get('5000') == str(b.backend_port):
            assert f"port={b.backend_port}" in b.code or str(b.backend_port) in b.code
            replaced_detected = True
    # Mock generation always includes a 5000 so replacement should occur
    assert replaced_detected, "Expected port 5000 to be replaced with allocated backend port"
