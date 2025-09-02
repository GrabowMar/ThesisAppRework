import asyncio
from app.services.sample_generation_service import get_sample_generation_service, CodeGenerator, GenerationResult

MULTI_BLOCK_CONTENT = """```python\n# backend file\nprint('hello')\n```\n```text\nflask\n```\n```javascript\n// frontend file\nconsole.log('hi');\n```"""

async def stub_generate(self, template, model, temperature=None, max_tokens=None):  # type: ignore
    return GenerationResult(
        app_num=template.app_num,
        app_name=template.name,
        model=model,
        content=MULTI_BLOCK_CONTENT,
        requirements=template.requirements or ["flask"],
        success=True,
        attempts=1,
        duration=0.01,
    )


def test_openrouter_stub_generation_persists(client, app, monkeypatch):
    svc = get_sample_generation_service()
    if not svc.list_templates():
        svc.upsert_templates([
            {"app_num": 2, "name": "stub", "content": "Create backend+frontend", "requirements": ["flask", "javascript"]}
        ])
    monkeypatch.setattr(CodeGenerator, "generate", stub_generate)
    rid, res = asyncio.run(svc.generate_async("stub", "openrouter/test-model"))
    assert rid and res.success
    assert len(res.extracted_blocks) >= 2
    # Force DB fallback
    svc._results.clear()  # type: ignore
    fetched = svc.get_result(rid, include_content=True)
    assert fetched is not None
    assert fetched.get("requirements")
    assert any(b.get("language") == "python" for b in fetched.get("extracted_blocks", []))
