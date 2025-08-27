import time

from app.services.batch_service import batch_service
from app.services.batch_result_cache_service import batch_result_cache


def test_batch_job_cache_hit_and_cache_only(app):
    """First job populates cache (simulated by marking tasks complete); second identical job should be cache_only.

    We create a job with a small matrix (1 analysis type * 1 model * 1 app) so total_tasks == 1.
    After creating the first job we manually insert a cached result (simulating post-analysis storage).
    The second creation should detect the cached result and mark cache_only / completed immediately.
    """
    analysis_types = ["static"]  # maps to code_quality
    models = ["anthropic_claude-3.7-sonnet"]
    app_range = "1"
    options = {"depth": 1}

    # Ensure clean cache
    batch_result_cache.clear()

    # Simulate first run result insertion directly into cache (bypassing actual execution)
    parts = ("code_quality", models[0], 1, options)
    batch_result_cache.store_result(parts, {"summary": "ok"}, ttl_seconds=60)

    # Now create the job which should find the cached entry and finish immediately
    job_id = batch_service.create_job(
        name="Cached Static Analysis",
        description="Testing cache-only flow",
        analysis_types=analysis_types,
        models=models,
        app_range_str=app_range,
        options=options,
    )

    status = batch_service.get_job_status(job_id)
    assert status is not None
    assert status["cache_only"] is True, "Job should be marked cache_only when all tasks cached"
    assert status["status"] == "completed"
    assert status["total_tasks"] == 1
    assert status["cached_tasks"] == 1
    assert status["cache_hit"] is True


def test_partial_cache_hit(app):
    """When only some tasks are cached, job should not be cache_only but cache_hit True."""
    batch_result_cache.clear()

    analysis_types = ["static", "security"]  # two different types
    models = ["anthropic_claude-3.7-sonnet"]
    app_range = "1"
    options = {"depth": 1}

    # Pre-cache only one of the two analysis types
    parts = ("code_quality", models[0], 1, options)  # static maps to code_quality
    batch_result_cache.store_result(parts, {"summary": "ok"}, ttl_seconds=60)

    job_id = batch_service.create_job(
        name="Partial Cache",
        description="One cached, one new",
        analysis_types=analysis_types,
        models=models,
        app_range_str=app_range,
        options=options,
    )
    status = batch_service.get_job_status(job_id)
    assert status is not None
    assert status["cache_only"] is False
    assert status["cache_hit"] is True
    assert status["cached_tasks"] == 1
    assert status["total_tasks"] == 2


def test_cache_expiration(app):
    """Expired cache entries should not produce cache_only outcome."""
    batch_result_cache.clear()

    analysis_types = ["static"]
    models = ["anthropic_claude-3.7-sonnet"]
    app_range = "1"
    options = {"depth": 1}

    # Insert with very short TTL
    parts = ("code_quality", models[0], 1, options)
    batch_result_cache.store_result(parts, {"summary": "temp"}, ttl_seconds=1)
    time.sleep(1.2)

    job_id = batch_service.create_job(
        name="Expired Cache",
        description="Should not be cache_only after expiry",
        analysis_types=analysis_types,
        models=models,
        app_range_str=app_range,
        options=options,
    )
    status = batch_service.get_job_status(job_id)
    assert status is not None
    assert status["cache_only"] is False
    assert status["cached_tasks"] == 0
    assert status["cache_hit"] is False
