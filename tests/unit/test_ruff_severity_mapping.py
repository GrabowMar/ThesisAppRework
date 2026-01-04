"""
Unit tests for Ruff severity mapping.

Tests that whitespace rules (W291, W293) are correctly mapped to low severity
instead of being marked as high severity errors.
"""

import pytest
import sys
from pathlib import Path

# Add analyzer services to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'analyzer' / 'services' / 'static-analyzer'))

from sarif_parsers import RuffSARIFParser, remap_ruff_sarif_severity  # type: ignore[import-not-found]


def test_ruff_whitespace_rules_are_low_severity():
    """Test that whitespace rules (W291, W293, W292) map to low severity."""
    # W291: Trailing whitespace
    level, severity = RuffSARIFParser._get_ruff_severity('W291')
    assert level == 'note', f"W291 should be 'note', got '{level}'"
    assert severity == 'low', f"W291 should be 'low', got '{severity}'"
    
    # W293: Blank line contains whitespace
    level, severity = RuffSARIFParser._get_ruff_severity('W293')
    assert level == 'note', f"W293 should be 'note', got '{level}'"
    assert severity == 'low', f"W293 should be 'low', got '{severity}'"
    
    # W292: No newline at end of file
    level, severity = RuffSARIFParser._get_ruff_severity('W292')
    assert level == 'note', f"W292 should be 'note', got '{level}'"
    assert severity == 'low', f"W292 should be 'low', got '{severity}'"


def test_ruff_security_rules_are_high_severity():
    """Test that security rules (S104, S311) map to high severity."""
    # S104: Hardcoded bind all interfaces
    level, severity = RuffSARIFParser._get_ruff_severity('S104')
    assert level == 'error', f"S104 should be 'error', got '{level}'"
    assert severity == 'high', f"S104 should be 'high', got '{severity}'"
    
    # S311: Weak random
    level, severity = RuffSARIFParser._get_ruff_severity('S311')
    assert level == 'error', f"S311 should be 'error', got '{level}'"
    assert severity == 'high', f"S311 should be 'high', got '{severity}'"


def test_ruff_import_rules_are_medium_severity():
    """Test that import rules (I001, E401) map to medium severity."""
    # I001: Import block is unsorted
    level, severity = RuffSARIFParser._get_ruff_severity('I001')
    assert level == 'warning', f"I001 should be 'warning', got '{level}'"
    assert severity == 'medium', f"I001 should be 'medium', got '{severity}'"
    
    # E401: Multiple imports on one line
    level, severity = RuffSARIFParser._get_ruff_severity('E401')
    assert level == 'warning', f"E401 should be 'warning', got '{level}'"
    assert severity == 'medium', f"E401 should be 'medium', got '{severity}'"


def test_ruff_undefined_name_is_high_severity():
    """Test that F821 (undefined name) is high severity."""
    level, severity = RuffSARIFParser._get_ruff_severity('F821')
    assert level == 'error', f"F821 should be 'error', got '{level}'"
    assert severity == 'high', f"F821 should be 'high', got '{severity}'"


def test_remap_ruff_sarif_severity():
    """Test the SARIF remapping function with mock data."""
    # Mock SARIF data with W293 (whitespace) marked as error
    sarif_data = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "ruff",
                    "version": "0.14.10"
                }
            },
            "results": [
                {
                    "ruleId": "W293",
                    "level": "error",  # Incorrect - should be note
                    "message": {"text": "Blank line contains whitespace"},
                    "properties": {
                        "problem.severity": "error"
                    }
                },
                {
                    "ruleId": "S104",
                    "level": "error",  # Correct
                    "message": {"text": "Hardcoded bind all interfaces"},
                    "properties": {
                        "problem.severity": "error"
                    }
                }
            ]
        }]
    }
    
    # Apply remapping
    remapped = remap_ruff_sarif_severity(sarif_data)
    
    # Check W293 was downgraded
    w293_result = remapped['runs'][0]['results'][0]
    assert w293_result['level'] == 'note', "W293 should be downgraded to 'note'"
    assert w293_result['properties']['problem.severity'] == 'low', "W293 should have 'low' severity"
    
    # Check S104 stayed high
    s104_result = remapped['runs'][0]['results'][1]
    assert s104_result['level'] == 'error', "S104 should remain 'error'"
    assert s104_result['properties']['problem.severity'] == 'high', "S104 should have 'high' severity"


def test_remap_handles_non_ruff_tools():
    """Test that remapping skips non-Ruff tools."""
    # Mock SARIF data from a different tool
    sarif_data = {
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "bandit",
                    "version": "1.7.0"
                }
            },
            "results": [
                {
                    "ruleId": "B201",
                    "level": "error",
                    "message": {"text": "Flask debug"}
                }
            ]
        }]
    }
    
    # Apply remapping (should not modify)
    original = sarif_data.copy()
    remapped = remap_ruff_sarif_severity(sarif_data)
    
    # Check unchanged
    assert remapped['runs'][0]['results'][0]['level'] == 'error', "Bandit result should be unchanged"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
