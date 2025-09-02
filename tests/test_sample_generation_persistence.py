import asyncio
from app.services.sample_generation_service import get_sample_generation_service


def test_generation_persists_and_db_fallback(client, app):
    svc = get_sample_generation_service()
    # Ensure at least one template exists (create simple inline template if none)
    if not svc.list_templates():
        svc.upsert_templates([
            {
                "app_num": 1,
                "name": "simple",
                "content": "A tiny python service with one health endpoint.",
                "requirements": ["flask"]
            }
        ])
    # Trigger generation (mock path likely used)
    result_id, result = asyncio.run(svc.generate_async("simple", "minimax/minimax-12b-chat"))
    assert result_id
    # It should appear in in-memory list
    meta = svc.get_result(result_id, include_content=False)
    assert meta and meta["app_name"] == "simple"
    # Clear in-memory cache to force DB fallback
    svc._results.clear()  # type: ignore
    # Fetch again – should now come via DB
    meta2 = svc.get_result(result_id, include_content=True)
    assert meta2 is not None
    # Content may be None if generation failed; ensure persistence of metadata
    assert meta2["app_name"] == "simple"
    assert meta2["app_name"] == "simple"
