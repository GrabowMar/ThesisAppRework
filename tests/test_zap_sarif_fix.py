"""Test ZAP SARIF parser fix for string confidence/risk values."""
import sys
from pathlib import Path

# Add analyzer services to path
analyzer_path = Path(__file__).parent.parent / "analyzer" / "services" / "dynamic-analyzer"
sys.path.insert(0, str(analyzer_path))

from sarif_parsers import ZAPSARIFParser


def test_zap_parser_with_string_confidence():
    """Test that ZAP parser handles string confidence values (from custom scans)."""
    # This mimics the output from main.py's custom ZAP-style scan
    output = {
        "alerts": [{
            "alert": "Security Issue",
            "risk": "high",
            "confidence": "medium",  # String value (not numeric)
            "description": "Test vulnerability",
            "url": "http://example.com",
            "solution": "Fix it",
            "reference": "http://ref.com",
            "param": "test_param",
            "attack": "test_attack",
            "evidence": "test_evidence"
        }]
    }
    
    # Should not raise ValueError
    sarif_run = ZAPSARIFParser.parse(output)
    
    assert sarif_run is not None
    assert "results" in sarif_run
    assert len(sarif_run["results"]) == 1
    result = sarif_run["results"][0]
    assert result["level"] == "error"  # high risk maps to error


def test_zap_parser_with_numeric_confidence():
    """Test that ZAP parser still handles numeric confidence values (native ZAP format)."""
    output = {
        "alerts": [{
            "alert": "Security Issue",
            "riskcode": 2,  # Numeric code for medium
            "confidence": 2,  # Numeric code for medium
            "riskdesc": "Medium (Medium)",
            "desc": "Test vulnerability",
            "uri": "http://example.com",
            "solution": "Fix it",
            "reference": "http://ref.com",
            "param": "test_param",
            "attack": "test_attack",
            "evidence": "test_evidence"
        }]
    }
    
    # Should not raise ValueError
    sarif_run = ZAPSARIFParser.parse(output)
    
    assert sarif_run is not None
    assert "results" in sarif_run
    assert len(sarif_run["results"]) == 1
    result = sarif_run["results"][0]
    assert result["level"] == "warning"  # medium risk maps to warning


def test_zap_parser_with_mixed_format():
    """Test that ZAP parser handles mixed string/numeric values."""
    output = {
        "alerts": [{
            "alert": "Issue 1",
            "risk": "low",  # String
            "confidence": "high",  # String
            "description": "Test 1",
            "url": "http://example.com"
        }, {
            "alert": "Issue 2",
            "riskcode": 3,  # Numeric
            "confidence": 1,  # Numeric
            "desc": "Test 2",
            "uri": "http://example.com"
        }]
    }
    
    # Should not raise ValueError
    sarif_run = ZAPSARIFParser.parse(output)
    
    assert sarif_run is not None
    assert "results" in sarif_run
    assert len(sarif_run["results"]) == 2


def test_zap_parser_with_numeric_string_confidence():
    """Test that ZAP parser handles numeric strings like '1', '2', '3'."""
    output = {
        "alerts": [{
            "alert": "Security Issue",
            "risk": "2",  # Numeric as string
            "confidence": "3",  # Numeric as string
            "description": "Test vulnerability",
            "url": "http://example.com"
        }]
    }
    
    # Should not raise ValueError and should convert to text
    sarif_run = ZAPSARIFParser.parse(output)
    
    assert sarif_run is not None
    assert "results" in sarif_run
    assert len(sarif_run["results"]) == 1


if __name__ == "__main__":
    test_zap_parser_with_string_confidence()
    print("✓ String confidence test passed")
    
    test_zap_parser_with_numeric_confidence()
    print("✓ Numeric confidence test passed")
    
    test_zap_parser_with_mixed_format()
    print("✓ Mixed format test passed")
    
    test_zap_parser_with_numeric_string_confidence()
    print("✓ Numeric string confidence test passed")
    
    print("\n✅ All ZAP SARIF parser tests passed!")
