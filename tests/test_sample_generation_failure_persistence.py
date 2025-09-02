import asyncio
from app.services.sample_generation_service import get_sample_generation_service, CodeGenerator, GenerationResult

async def failing_generate(self, template, model, temperature=None, max_tokens=None):  # type: ignore
    return GenerationResult(
        app_num=template.app_num,
        app_name=template.name,
        model=model,
        content="",  # no content
        requirements=template.requirements or [],
        success=False,
        error_message="Simulated failure",
        attempts=2,
        duration=0.05,
    )


def test_failed_generation_persisted(monkeypatch, client, app):
    svc = get_sample_generation_service()
    if not svc.list_templates():
        svc.upsert_templates([
            {"app_num": 3, "name": "failcase", "content": "Will fail", "requirements": []}
        ])
    monkeypatch.setattr(CodeGenerator, "generate", failing_generate)
    rid, res = asyncio.run(svc.generate_async("failcase", "openrouter/test-model"))
    assert rid and not res.success and res.error_message
    svc._results.clear()  # force db fallback
    meta = svc.get_result(rid, include_content=True)
    assert meta and meta.get("success") is False and meta.get("error_message") == "Simulated failure"
    # content should be absent or empty
    assert not meta.get("content")
