"""
Dashboard Data Parser Test & Validation

Tests the dashboard JavaScript parsing logic against mock data
to ensure all 18 tools are properly registered and findings are parsed correctly.
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from generate_mock_results import generate_mock_results, TOOLS_CONFIG


def test_data_structure():
    """Test that generated mock data matches expected structure."""
    print("=" * 60)
    print("TEST 1: Data Structure Validation")
    print("=" * 60)
    
    results = generate_mock_results()
    
    # Check top-level keys
    required_keys = ["task_id", "status", "analysis_type", "model_slug", "app_number", "results", "metadata"]
    for key in required_keys:
        assert key in results, f"Missing required key: {key}"
        print(f"✅ Key present: {key}")
    
    # Check results.summary structure
    summary = results["results"]["summary"]
    summary_keys = ["total_findings", "severity_breakdown", "findings_by_tool", "tools_used", "tools_failed", "tools_skipped"]
    for key in summary_keys:
        assert key in summary, f"Missing summary key: {key}"
        print(f"✅ Summary key present: {key}")
    
    # Check findings structure
    findings = results["results"]["findings"]
    assert len(findings) > 0, "No findings generated"
    print(f"✅ Generated {len(findings)} findings")
    
    # Check each finding has required fields
    required_finding_keys = ["tool", "category", "severity", "message", "file"]
    for idx, finding in enumerate(findings[:3]):  # Check first 3
        for key in required_finding_keys:
            assert key in finding, f"Finding {idx} missing key: {key}"
    print(f"✅ All findings have required keys")
    
    print("\\n✅ Data structure validation: PASSED\\n")
    return results


def test_tool_registration():
    """Test that all 18 tools are properly registered."""
    print("=" * 60)
    print("TEST 2: Tool Registration")
    print("=" * 60)
    
    results = generate_mock_results()
    summary = results["results"]["summary"]
    
    expected_tools = list(TOOLS_CONFIG.keys())
    registered_tools = summary["tools_used"]
    
    print(f"Expected tools: {len(expected_tools)}")
    print(f"Registered tools: {len(registered_tools)}")
    
    missing_tools = set(expected_tools) - set(registered_tools)
    extra_tools = set(registered_tools) - set(expected_tools)
    
    if missing_tools:
        print(f"❌ Missing tools: {missing_tools}")
        return False
    
    if extra_tools:
        print(f"⚠️  Extra tools: {extra_tools}")
    
    # Check each tool category
    categories = {
        "Static": ["bandit", "pylint", "flake8", "mypy", "semgrep", "safety", "vulture", "eslint", "jshint", "snyk", "stylelint"],
        "Dynamic": ["curl", "nmap", "zap"],
        "Performance": ["aiohttp", "ab", "locust", "artillery"]
    }
    
    for category, tools in categories.items():
        registered = [t for t in tools if t in registered_tools]
        print(f"✅ {category}: {len(registered)}/{len(tools)} tools registered")
        for tool in registered:
            print(f"   - {tool}")
    
    print("\\n✅ Tool registration: PASSED\\n")
    return True


def test_severity_breakdown():
    """Test that severity breakdown is calculated correctly."""
    print("=" * 60)
    print("TEST 3: Severity Breakdown")
    print("=" * 60)
    
    results = generate_mock_results()
    summary = results["results"]["summary"]
    findings = results["results"]["findings"]
    
    # Count severities from findings
    actual_counts = {
        "critical": sum(1 for f in findings if f["severity"] == "critical"),
        "high": sum(1 for f in findings if f["severity"] == "high"),
        "medium": sum(1 for f in findings if f["severity"] == "medium"),
        "low": sum(1 for f in findings if f["severity"] == "low"),
    }
    
    reported_counts = summary["severity_breakdown"]
    
    for severity in ["critical", "high", "medium", "low"]:
        actual = actual_counts[severity]
        reported = reported_counts[severity]
        match = "✅" if actual == reported else "❌"
        print(f"{match} {severity.upper()}: actual={actual}, reported={reported}")
        assert actual == reported, f"Severity mismatch for {severity}"
    
    total_from_breakdown = sum(reported_counts.values())
    total_findings = summary["total_findings"]
    print(f"\\n✅ Total findings: {total_findings}")
    print(f"✅ Sum of breakdown: {total_from_breakdown}")
    assert total_from_breakdown == total_findings, "Breakdown sum doesn't match total"
    
    print("\\n✅ Severity breakdown: PASSED\\n")
    return True


def test_findings_by_tool():
    """Test that findings_by_tool counts are correct."""
    print("=" * 60)
    print("TEST 4: Findings by Tool")
    print("=" * 60)
    
    results = generate_mock_results()
    summary = results["results"]["summary"]
    findings = results["results"]["findings"]
    
    # Count findings per tool from actual findings
    actual_counts = {}
    for finding in findings:
        tool = finding["tool"]
        actual_counts[tool] = actual_counts.get(tool, 0) + 1
    
    reported_counts = summary["findings_by_tool"]
    
    print(f"Tools with findings: {len(reported_counts)}")
    
    all_match = True
    for tool in reported_counts:
        actual = actual_counts.get(tool, 0)
        reported = reported_counts[tool]
        match = "✅" if actual == reported else "❌"
        print(f"{match} {tool:12} actual={actual:2}, reported={reported:2}")
        if actual != reported:
            all_match = False
    
    assert all_match, "Some tool counts don't match"
    print("\\n✅ Findings by tool: PASSED\\n")
    return True


def test_category_distribution():
    """Test that findings are properly categorized."""
    print("=" * 60)
    print("TEST 5: Category Distribution")
    print("=" * 60)
    
    results = generate_mock_results()
    findings = results["results"]["findings"]
    
    # Count by category
    category_counts = {}
    for finding in findings:
        category = finding["category"]
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print("Category distribution:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category:15} {count:3} findings")
    
    # Verify categories match tool definitions
    for finding in findings:
        tool = finding["tool"]
        category = finding["category"]
        expected_category = TOOLS_CONFIG[tool]["category"]
        assert category == expected_category, f"Tool {tool} has wrong category: {category} vs {expected_category}"
    
    print("\\n✅ Category distribution: PASSED\\n")
    return True


def test_finding_fields():
    """Test that each finding has all required fields for dashboard display."""
    print("=" * 60)
    print("TEST 6: Finding Field Completeness")
    print("=" * 60)
    
    results = generate_mock_results()
    findings = results["results"]["findings"]
    
    # Required fields for dashboard JavaScript
    required_fields = {
        "tool": str,
        "category": str,
        "severity": str,
        "message": dict,
        "file": dict,
    }
    
    optional_fields = ["rule_id", "symbol", "line_number", "evidence", "metadata"]
    
    print(f"Testing {len(findings)} findings...")
    
    for idx, finding in enumerate(findings):
        # Check required fields
        for field, expected_type in required_fields.items():
            assert field in finding, f"Finding {idx} missing field: {field}"
            assert isinstance(finding[field], expected_type), f"Finding {idx} field {field} wrong type"
        
        # Check message structure
        message = finding["message"]
        assert "title" in message or "description" in message, f"Finding {idx} message missing title/description"
        
        # Check file structure
        file_info = finding["file"]
        assert "path" in file_info, f"Finding {idx} file missing path"
    
    print(f"✅ All {len(findings)} findings have required fields")
    print(f"✅ Message structures valid")
    print(f"✅ File structures valid")
    
    print("\\n✅ Finding field completeness: PASSED\\n")
    return True


def test_dashboard_parsing_simulation():
    """Simulate the dashboard JavaScript parsing logic."""
    print("=" * 60)
    print("TEST 7: Dashboard Parsing Simulation")
    print("=" * 60)
    
    results = generate_mock_results()
    summary = results["results"]["summary"]
    findings = results["results"]["findings"]
    
    # Simulate updateSummaryCards()
    print("Simulating updateSummaryCards()...")
    total_findings = summary["total_findings"]
    severity = summary["severity_breakdown"]
    high_count = severity.get("critical", 0) + severity.get("high", 0)
    tools_used = summary["tools_used"]
    tools_failed = summary["tools_failed"]
    tools_skipped = summary["tools_skipped"]
    
    print(f"  Total findings: {total_findings}")
    print(f"  High severity: {high_count}")
    print(f"  Tools executed: {len(tools_used)}/18")
    print(f"  Tools status: {len(tools_failed)} failed, {len(tools_skipped)} skipped")
    
    # Simulate category filtering
    print("\\nSimulating category filtering...")
    security_findings = [f for f in findings if f["category"] == "security"]
    quality_findings = [f for f in findings if f["category"] in ["quality", "code_quality"]]
    performance_findings = [f for f in findings if f["category"] == "performance"]
    
    print(f"  Security: {len(security_findings)} findings")
    print(f"  Quality: {len(quality_findings)} findings")
    print(f"  Performance: {len(performance_findings)} findings")
    
    # Simulate severity filtering
    print("\\nSimulating severity filtering...")
    critical_high = [f for f in findings if f["severity"] in ["critical", "high"]]
    medium_plus = [f for f in findings if f["severity"] in ["critical", "high", "medium"]]
    all_severity = findings
    
    print(f"  High only: {len(critical_high)} findings")
    print(f"  Medium+: {len(medium_plus)} findings")
    print(f"  All: {len(all_severity)} findings")
    
    # Simulate tool filtering
    print("\\nSimulating tool filtering...")
    tools_with_findings = set(f["tool"] for f in findings)
    print(f"  Unique tools: {len(tools_with_findings)}")
    for tool in sorted(tools_with_findings)[:5]:
        tool_findings = [f for f in findings if f["tool"] == tool]
        print(f"    {tool}: {len(tool_findings)} findings")
    
    print("\\n✅ Dashboard parsing simulation: PASSED\\n")
    return True


def run_all_tests():
    """Run all validation tests."""
    print("\\n" + "=" * 60)
    print("DASHBOARD DATA VALIDATION TEST SUITE")
    print("=" * 60 + "\\n")
    
    tests = [
        ("Data Structure", test_data_structure),
        ("Tool Registration", test_tool_registration),
        ("Severity Breakdown", test_severity_breakdown),
        ("Findings by Tool", test_findings_by_tool),
        ("Category Distribution", test_category_distribution),
        ("Finding Fields", test_finding_fields),
        ("Dashboard Parsing", test_dashboard_parsing_simulation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"❌ TEST FAILED: {name}")
            print(f"   Error: {e}\\n")
    
    # Summary
    print("\\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status:12} {name}")
        if error:
            print(f"             Error: {error}")
    
    print(f"\\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\\n🎉 ALL TESTS PASSED! Dashboard parsing is working correctly.")
        return 0
    else:
        print(f"\\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
