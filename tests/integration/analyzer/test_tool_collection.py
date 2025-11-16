"""
Integration tests for tool collection and metadata filtering.

Verifies that:
1. Metadata fields (tool_status, file_counts, etc.) are not treated as tools
2. Actual tools show correct execution status (not "Skipped")
3. Tools map appears in consolidated results
4. Case-insensitive metadata filtering works
"""

import json
import pytest
from pathlib import Path


@pytest.mark.integration
@pytest.mark.analyzer
def test_tool_collection_filters_metadata():
    """Verify metadata fields are excluded from tools map."""
    # Load a real result file from the fixtures
    result_file = Path(__file__).parent.parent.parent.parent / 'results' / \
                  'anthropic_claude-4.5-haiku-20251001' / 'app1' / 'task_bbf179816bd9' / \
                  'anthropic_claude-4.5-haiku-20251001_app1_task_bbf179816bd9_20251116_090534.json'
    
    if not result_file.exists():
        pytest.skip(f"Test result file not found: {result_file}")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Verify tools map exists
    assert 'results' in data, "Missing results section"
    assert 'tools' in data['results'], "Missing tools map in results"
    
    tools = data['results']['tools']
    
    # Metadata keys that should NOT appear as tools
    metadata_keys = {
        'tool_status', '_metadata', 'status', 'file_counts', 'security_files',
        'total_files', 'message', 'error', 'analysis_time', 'model_slug',
        'app_number', 'tools_used', 'configuration_applied', 'results',
        '_project_metadata'
    }
    
    # Check no metadata keys appear in tools (case-insensitive)
    tool_names_lower = {name.lower() for name in tools.keys()}
    found_metadata = tool_names_lower & metadata_keys
    
    assert not found_metadata, \
        f"Metadata keys found in tools map: {found_metadata}. Tools: {list(tools.keys())}"


@pytest.mark.integration
@pytest.mark.analyzer
def test_executed_tools_show_correct_status():
    """Verify tools that executed show success/no_issues, not Skipped."""
    result_file = Path(__file__).parent.parent.parent.parent / 'results' / \
                  'anthropic_claude-4.5-haiku-20251001' / 'app1' / 'task_bbf179816bd9' / \
                  'anthropic_claude-4.5-haiku-20251001_app1_task_bbf179816bd9_20251116_090534.json'
    
    if not result_file.exists():
        pytest.skip(f"Test result file not found: {result_file}")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tools = data.get('results', {}).get('tools', {})
    
    # Expected tools from the user's screenshot
    expected_tools = ['bandit', 'pylint', 'semgrep', 'mypy', 'safety', 'vulture', 'ruff', 'eslint']
    
    for tool_name in expected_tools:
        if tool_name in tools:
            tool_data = tools[tool_name]
            status = tool_data.get('status', '').lower()
            executed = tool_data.get('executed', False)
            
            # If executed is True, status should not be skipped
            if executed:
                assert status not in ('skipped', 'not_available'), \
                    f"Tool '{tool_name}' shows executed=True but status='{status}'"
                assert status in ('success', 'completed', 'no_issues', 'error'), \
                    f"Tool '{tool_name}' has unexpected status: '{status}'"


@pytest.mark.integration
@pytest.mark.analyzer
def test_tools_have_required_fields():
    """Verify all tools in the map have required fields."""
    result_file = Path(__file__).parent.parent.parent.parent / 'results' / \
                  'anthropic_claude-4.5-haiku-20251001' / 'app1' / 'task_bbf179816bd9' / \
                  'anthropic_claude-4.5-haiku-20251001_app1_task_bbf179816bd9_20251116_090534.json'
    
    if not result_file.exists():
        pytest.skip(f"Test result file not found: {result_file}")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tools = data.get('results', {}).get('tools', {})
    
    required_fields = {'status', 'executed', 'total_issues'}
    
    for tool_name, tool_data in tools.items():
        assert isinstance(tool_data, dict), f"Tool '{tool_name}' is not a dict"
        
        missing_fields = required_fields - set(tool_data.keys())
        assert not missing_fields, \
            f"Tool '{tool_name}' missing required fields: {missing_fields}"


@pytest.mark.integration
@pytest.mark.analyzer
def test_service_metadata_remains_in_services():
    """Verify service-level metadata stays in services section, not promoted to tools."""
    result_file = Path(__file__).parent.parent.parent.parent / 'results' / \
                  'anthropic_claude-4.5-haiku-20251001' / 'app1' / 'task_bbf179816bd9' / \
                  'anthropic_claude-4.5-haiku-20251001_app1_task_bbf179816bd9_20251116_090534.json'
    
    if not result_file.exists():
        pytest.skip(f"Test result file not found: {result_file}")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check that _metadata and _project_metadata are in services, not tools
    services = data.get('results', {}).get('services', {})
    tools = data.get('results', {}).get('tools', {})
    
    # Verify _metadata is NOT in tools
    assert '_metadata' not in tools, "_metadata should not appear in tools map"
    assert '_project_metadata' not in tools, "_project_metadata should not appear in tools map"
    
    # Verify it exists in services (if static analyzer ran)
    static_service = services.get('static-analyzer', {})
    if static_service:
        analysis = static_service.get('analysis', {})
        results = analysis.get('results', {})
        python_results = results.get('python', {})
        
        # _metadata should be in Python results, not promoted to tools
        if '_metadata' in python_results:
            assert isinstance(python_results['_metadata'], dict), \
                "_metadata should be a dict in service results"


@pytest.mark.unit
def test_metadata_keys_list_is_comprehensive():
    """Verify METADATA_KEYS constant covers all known metadata fields."""
    # This test ensures we don't forget to add new metadata fields to the filter list
    from analyzer.analyzer_manager import AnalyzerManager
    
    # Read the source to extract METADATA_KEYS
    import inspect
    source = inspect.getsource(AnalyzerManager._collect_normalized_tools)
    
    # Verify METADATA_KEYS is defined
    assert 'METADATA_KEYS' in source, "METADATA_KEYS not found in _collect_normalized_tools"
    
    # Known metadata fields that should be in the set
    expected_metadata = [
        'tool_status', '_metadata', 'status', 'file_counts', 'security_files',
        'total_files', '_project_metadata'
    ]
    
    for field in expected_metadata:
        assert field in source, f"Expected metadata field '{field}' not in METADATA_KEYS"
