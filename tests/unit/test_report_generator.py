"""
Unit Tests for Report Generators
================================

This module contains unit tests for the report generation services.

Tests cover:
- AppReportGenerator: Application-specific report generation and validation
- ModelReportGenerator: Model comparison report generation and validation
- Configuration validation for required parameters
- Template resolution and file handling
- Error handling for invalid configurations

These tests ensure that report generation works correctly for both individual
application analysis and model comparison scenarios.
"""
from app.services.reports.app_report_generator import AppReportGenerator
from app.services.reports.model_report_generator import ModelReportGenerator
from app.services.service_base import ValidationError

@pytest.fixture
def mock_reports_dir(tmp_path):
    return tmp_path


# =============================================================================
# AppReportGenerator Tests
# =============================================================================

def test_validate_config_missing_template_slug(mock_reports_dir):
    """Test validation fails when template_slug is missing."""
    generator = AppReportGenerator(config={}, reports_dir=mock_reports_dir)
    with pytest.raises(ValidationError, match="template_slug is required"):
        generator.validate_config()

def test_validate_config_success(mock_reports_dir):
    """Test validation succeeds with valid config."""
    generator = AppReportGenerator(config={'template_slug': 'crud_todo_list'}, reports_dir=mock_reports_dir)
    try:
        generator.validate_config()
    except ValidationError:
        pytest.fail("validate_config raised ValidationError unexpectedly")

def test_get_template_name(mock_reports_dir):
    """Test template name is correct."""
    generator = AppReportGenerator(config={'template_slug': 'crud_todo_list'}, reports_dir=mock_reports_dir)
    assert generator.get_template_name() == 'partials/_app_comparison.html'


# =============================================================================
# ModelReportGenerator Tests
# =============================================================================

def test_model_validate_config_missing_model_slug(mock_reports_dir):
    """Test validation fails when model_slug is missing."""
    generator = ModelReportGenerator(config={}, reports_dir=mock_reports_dir)
    with pytest.raises(ValidationError, match="model_slug is required"):
        generator.validate_config()

def test_model_validate_config_success(mock_reports_dir):
    """Test validation succeeds with valid config."""
    generator = ModelReportGenerator(config={'model_slug': 'openai_gpt-4o'}, reports_dir=mock_reports_dir)
    try:
        generator.validate_config()
    except ValidationError:
        pytest.fail("validate_config raised ValidationError unexpectedly")

def test_model_get_template_name(mock_reports_dir):
    """Test template name is correct."""
    generator = ModelReportGenerator(config={'model_slug': 'openai_gpt-4o'}, reports_dir=mock_reports_dir)
    assert generator.get_template_name() == 'partials/_model_analysis.html'


# =============================================================================
# Generation Metadata Helper Tests
# =============================================================================

class TestGenerationMetadataHelpers:
    """Tests for generation metadata integration in report generators."""
    
    def test_model_generator_has_generation_metadata_method(self, mock_reports_dir):
        """Test that ModelReportGenerator has generation metadata helper."""
        generator = ModelReportGenerator(
            config={'model_slug': 'test-model'},
            reports_dir=mock_reports_dir
        )
        assert hasattr(generator, '_get_generation_metadata_for_model')
        assert callable(generator._get_generation_metadata_for_model)
    
    def test_app_generator_has_generation_comparison_method(self, mock_reports_dir):
        """Test that AppReportGenerator has generation comparison helper."""
        generator = AppReportGenerator(
            config={'template_slug': 'crud_todo_list'},
            reports_dir=mock_reports_dir
        )
        assert hasattr(generator, '_get_generation_comparison_for_template')
        assert callable(generator._get_generation_comparison_for_template)
    
    @patch('app.services.reports.model_report_generator.load_generation_records')
    def test_model_metadata_returns_dict_on_no_records(self, mock_load, mock_reports_dir):
        """Test that helper returns dict even when no records found."""
        mock_load.return_value = []
        
        generator = ModelReportGenerator(
            config={'model_slug': 'test-model'},
            reports_dir=mock_reports_dir
        )
        result = generator._get_generation_metadata_for_model('test-model')
        
        assert isinstance(result, dict)
        assert 'available' in result
        assert result.get('available') == False
    
    @patch('app.services.reports.app_report_generator.load_generation_records')
    def test_app_comparison_returns_dict_on_no_records(self, mock_load, mock_reports_dir):
        """Test that helper returns dict even when no records found."""
        mock_load.return_value = []
        
        generator = AppReportGenerator(
            config={'template_slug': 'crud_todo_list'},
            reports_dir=mock_reports_dir
        )
        result = generator._get_generation_comparison_for_template(
            'crud_todo_list', 
            ['model-a', 'model-b'],
            {'model-a': 1, 'model-b': 1}
        )
        
        assert isinstance(result, dict)
        assert 'available' in result
        assert result.get('available') == False
    
    @patch('app.services.reports.model_report_generator.load_generation_records')
    def test_model_metadata_aggregates_costs(self, mock_load, mock_reports_dir):
        """Test that model helper correctly aggregates generation costs."""
        # Create mock GenerationRecord-like objects
        class MockRecord:
            def __init__(self, model, app_num, cost, tokens, time_ms, lines, provider):
                self.model = model
                self.app_num = app_num  # Must match GenerationRecord field name
                self.estimated_cost = cost
                self.total_tokens = tokens
                self.prompt_tokens = int(tokens * 0.4)
                self.completion_tokens = int(tokens * 0.6)
                self.generation_time_ms = time_ms
                self.total_lines = lines  # Must match GenerationRecord field name
                self.provider_name = provider
                self.component = 'combined'
                self.success = True
        
        mock_load.return_value = [
            MockRecord('test-model', 1, 0.01, 1000, 5000, 100, 'OpenAI'),
            MockRecord('test-model', 1, 0.02, 2000, 8000, 200, 'OpenAI'),
            MockRecord('test-model', 2, 0.015, 1500, 6000, 150, 'OpenAI'),
        ]
        
        generator = ModelReportGenerator(
            config={'model_slug': 'test-model'},
            reports_dir=mock_reports_dir
        )
        result = generator._get_generation_metadata_for_model('test-model')
        
        assert result.get('available') == True
        assert result.get('total_generations') == 3
        assert abs(result.get('total_cost', 0) - 0.045) < 0.001  # 0.01 + 0.02 + 0.015
        assert result.get('total_tokens') == 4500  # 1000 + 2000 + 1500
    
    @patch('app.services.reports.app_report_generator.load_generation_records')
    def test_app_comparison_filters_by_template(self, mock_load, mock_reports_dir):
        """Test that app comparison only includes records for the specified models and app numbers."""
        class MockRecord:
            def __init__(self, model, app_num, cost, tokens, time_ms, lines, provider):
                self.model = model
                self.app_num = app_num  # Must match GenerationRecord field name
                self.estimated_cost = cost
                self.total_tokens = tokens
                self.prompt_tokens = int(tokens * 0.4)
                self.completion_tokens = int(tokens * 0.6)
                self.generation_time_ms = time_ms
                self.total_lines = lines  # Must match GenerationRecord field name
                self.provider_name = provider
                self.component = 'combined'
                self.success = True
        
        mock_load.return_value = [
            MockRecord('model-a', 1, 0.01, 1000, 5000, 100, 'OpenAI'),
            MockRecord('model-b', 2, 0.02, 2000, 8000, 200, 'Anthropic'),
            MockRecord('model-a', 3, 0.03, 3000, 10000, 300, 'OpenAI'),  # Different app
        ]
        
        generator = AppReportGenerator(
            config={'template_slug': 'crud_todo_list'},
            reports_dir=mock_reports_dir
        )
        # Simulate that model-a used app 1 and model-b used app 2 for the template
        result = generator._get_generation_comparison_for_template(
            'crud_todo_list',
            ['model-a', 'model-b'],
            {'model-a': 1, 'model-b': 2}
        )
        
        assert result.get('available') == True
        # Should have 2 models matching their respective app numbers
        models = result.get('models', [])
        assert len(models) == 2
        model_slugs = [m.get('model_slug') for m in models]
        assert 'model-a' in model_slugs
        assert 'model-b' in model_slugs
