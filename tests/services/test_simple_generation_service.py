"""Tests for the deprecated simple generation shim.

The real implementation now lives in :mod:`app.services.generation`. These
tests exist purely to verify the shim preserves backwards compatibility while
nudging callers onto the new service.
"""

from __future__ import annotations

import warnings

import pytest


@pytest.fixture
def app():
    from app.factory import create_app

    return create_app('testing')


def test_shim_emits_deprecation_warning(app):
    with app.app_context():
        from app.services.generation import get_generation_service
        from app.services.simple_generation_service import get_simple_generation_service

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always', DeprecationWarning)
            shim_service = get_simple_generation_service()

        assert captured, "Expected deprecation warning from shim"
        assert captured[0].category is DeprecationWarning
        assert shim_service is get_generation_service()


def test_shim_multiple_calls_share_singleton(app):
    with app.app_context():
        from app.services.simple_generation_service import get_simple_generation_service

        first = get_simple_generation_service()
        second = get_simple_generation_service()

        assert first is second
