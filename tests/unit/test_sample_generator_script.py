"""Tests for scripts/run_sample_generations.py

Tests the fallback model creation and validation logic.
"""
import sys
from pathlib import Path

import pytest

# Add src and scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from app.factory import create_app
from app.models import ModelCapability
from app.extensions import db
from run_sample_generations import ensure_model_exists, MODEL_SLUG


@pytest.fixture
def app():
    """Create test Flask app with in-memory database."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_ensure_model_exists_creates_fallback_when_empty(app, monkeypatch):
    """Test that ensure_model_exists creates a fallback model when database is empty."""
    
    # Set OPENROUTER_API_KEY for the test
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test_key')
    
    with app.app_context():
        # Verify no models exist
        assert ModelCapability.query.count() == 0
        
        # Call the function
        success, model_slug = ensure_model_exists(app)
        
        # Verify a model was created
        assert success is True
        assert model_slug == "anthropic_claude-3-5-haiku"
        assert ModelCapability.query.count() == 1
        
        # Verify model properties
        model = ModelCapability.query.first()
        assert model.canonical_slug == "anthropic_claude-3-5-haiku"
        assert model.model_id == "anthropic/claude-3.5-haiku"
        assert model.provider == "anthropic"
        assert model.installed is True


def test_ensure_model_exists_uses_existing_model(app, monkeypatch):
    """Test that ensure_model_exists uses an existing model if available."""
    with app.app_context():
        # Create a model
        model = ModelCapability(
            model_id="test/model",
            canonical_slug="test_model",
            provider="test",
            model_name="test-model",
            installed=True,
        )
        db.session.add(model)
        db.session.commit()
        
        # Verify one model exists
        assert ModelCapability.query.count() == 1
        
        # Call the function
        success, model_slug = ensure_model_exists(app)
        
        # Should use the existing model
        assert success is True
        assert model_slug == "test_model"
        assert ModelCapability.query.count() == 1  # No new models created


def test_ensure_model_exists_fails_without_api_key(app, monkeypatch):
    """Test that ensure_model_exists fails gracefully when API key is missing."""
    # Ensure OPENROUTER_API_KEY is not set
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    
    with app.app_context():
        # Verify no models exist
        assert ModelCapability.query.count() == 0
        
        # Call the function - should fail
        success, model_slug = ensure_model_exists(app)
        
        # Should fail gracefully
        assert success is False
        assert model_slug == ""
        assert ModelCapability.query.count() == 0  # No models created


def test_ensure_model_exists_prefers_primary_model(app):
    """Test that ensure_model_exists prefers the primary model when multiple exist."""
    with app.app_context():
        # Create fallback model
        fallback = ModelCapability(
            model_id="google/gemini",
            canonical_slug="google_gemini",
            provider="google",
            model_name="gemini",
            installed=True,
        )
        db.session.add(fallback)
        
        # Create primary model
        primary = ModelCapability(
            model_id="anthropic/claude-3.5-haiku",
            canonical_slug=MODEL_SLUG,
            provider="anthropic",
            model_name="claude-3.5-haiku",
            installed=True,
        )
        db.session.add(primary)
        db.session.commit()
        
        # Call the function
        success, model_slug = ensure_model_exists(app)
        
        # Should prefer the primary model
        assert success is True
        assert model_slug == MODEL_SLUG
