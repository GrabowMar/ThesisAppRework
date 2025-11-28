import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.services.reports.app_report_generator import AppReportGenerator
from app.services.service_base import ValidationError

@pytest.fixture
def mock_reports_dir(tmp_path):
    return tmp_path

def test_validate_config_missing_app_number(mock_reports_dir):
    """Test validation fails when app_number is missing."""
    generator = AppReportGenerator(config={}, reports_dir=mock_reports_dir)
    with pytest.raises(ValidationError, match="app_number is required"):
        generator.validate_config()

def test_validate_config_success(mock_reports_dir):
    """Test validation succeeds with valid config."""
    generator = AppReportGenerator(config={'app_number': 1}, reports_dir=mock_reports_dir)
    try:
        generator.validate_config()
    except ValidationError:
        pytest.fail("validate_config raised ValidationError unexpectedly")

def test_get_template_name(mock_reports_dir):
    """Test template name is correct."""
    generator = AppReportGenerator(config={'app_number': 1}, reports_dir=mock_reports_dir)
    assert generator.get_template_name() == 'partials/_app_comparison.html'
