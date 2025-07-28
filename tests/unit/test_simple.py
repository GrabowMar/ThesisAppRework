"""
Simple test to validate basic configuration and imports.
"""
import pytest
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_basic_imports():
    """Test that we can import basic modules without errors."""
    try:
        from extensions import db
        from models import ModelCapability, PortConfiguration
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import basic modules: {e}")

def test_app_creation():
    """Test basic app creation."""
    try:
        from app import create_app
        app = create_app()
        assert app is not None
        assert app.config is not None
    except Exception as e:
        pytest.fail(f"Failed to create app: {e}")

def test_database_models():
    """Test that database models can be imported and created."""
    try:
        from app import create_app
        from extensions import db
        from models import ModelCapability, PortConfiguration, GeneratedApplication
        
        app = create_app()
        with app.app_context():
            # Just test that we can create the models
            model_cap = ModelCapability(
                model_id="test-model",
                canonical_slug="test_model",
                provider="test-provider", 
                model_name="Test Model",
                context_window=4000,
                input_price_per_token=0.001,
                output_price_per_token=0.002
            )
            assert model_cap.model_id == "test-model"
            
            port_config = PortConfiguration(
                backend_port=6000,
                frontend_port=9000
            )
            assert port_config.backend_port == 6000
            
    except Exception as e:
        pytest.fail(f"Failed to work with models: {e}")
