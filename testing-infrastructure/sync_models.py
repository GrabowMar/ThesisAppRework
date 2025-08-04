#!/usr/bin/env python3
"""
Model Synchronization Script
============================

This script helps maintain compatibility between the main application models
and the testing container models. It checks for mismatches and can update
the container models when needed.

Usage:
    python sync_models.py --check      # Check for compatibility issues
    python sync_models.py --update     # Update container models from main app
    python sync_models.py --validate   # Validate all models work together
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add paths for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))
sys.path.append(str(PROJECT_ROOT / "testing-infrastructure" / "containers" / "security-scanner" / "app"))

try:
    from src.models import AnalysisStatus, SeverityLevel as MainSeverityLevel
    from testing_infrastructure.containers.security_scanner.app.models import TestingStatus, SeverityLevel as ContainerSeverityLevel
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory.")
    sys.exit(1)


def check_enum_compatibility():
    """Check if enums are compatible between main app and containers."""
    issues = []
    
    # Check status enum compatibility
    main_statuses = {status.value for status in AnalysisStatus}
    container_statuses = {status.value for status in TestingStatus}
    
    # Main app statuses that containers don't support
    missing_in_container = main_statuses - container_statuses
    if missing_in_container:
        issues.append(f"Container missing statuses: {missing_in_container}")
    
    # Container statuses that main app doesn't support (these are OK)
    extra_in_container = container_statuses - main_statuses
    if extra_in_container:
        print(f"Info: Container has additional statuses: {extra_in_container}")
    
    # Check severity levels
    main_severities = {severity.value for severity in MainSeverityLevel}
    container_severities = {severity.value for severity in ContainerSeverityLevel}
    
    if main_severities != container_severities:
        issues.append(f"Severity level mismatch: Main={main_severities}, Container={container_severities}")
    
    return issues


def validate_result_structure():
    """Validate that container results can be properly converted to main app format."""
    try:
        # Import the models locally to test
        from models import SecurityTestResult, TestIssue, TestingStatus, SeverityLevel, create_main_app_compatible_result
        from datetime import datetime
        
        # Create a test result
        test_issue = TestIssue(
            tool="bandit",
            severity=SeverityLevel.HIGH,
            confidence="MEDIUM",
            file_path="test.py",
            line_number=42,
            message="Test security issue",
            description="This is a test security issue"
        )
        
        test_result = SecurityTestResult(
            test_id="test-123",
            status=TestingStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration=30.5,
            issues=[test_issue],
            tools_used=["bandit", "safety"]
        )
        
        # Test conversion to main app format
        main_app_data = create_main_app_compatible_result(test_result)
        
        # Validate required fields are present
        required_fields = [
            'status', 'started_at', 'completed_at', 'analysis_duration',
            'total_issues', 'critical_severity_count', 'high_severity_count',
            'medium_severity_count', 'low_severity_count', 'results_json'
        ]
        
        missing_fields = [field for field in required_fields if field not in main_app_data]
        if missing_fields:
            return f"Missing required fields in main app conversion: {missing_fields}"
        
        # Test JSON serialization
        json.dumps(main_app_data, default=str)
        
        return None  # No issues
        
    except Exception as e:
        return f"Validation failed: {e}"


def generate_compatibility_report():
    """Generate a full compatibility report."""
    print("=== Model Compatibility Report ===\n")
    
    # Check enum compatibility
    print("1. Enum Compatibility:")
    enum_issues = check_enum_compatibility()
    if enum_issues:
        for issue in enum_issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ All enums are compatible")
    
    print()
    
    # Check result structure
    print("2. Result Structure Validation:")
    structure_issue = validate_result_structure()
    if structure_issue:
        print(f"   ❌ {structure_issue}")
    else:
        print("   ✅ Result structures are compatible")
    
    print()
    
    # Check file synchronization
    print("3. File Synchronization:")
    shared_models_path = PROJECT_ROOT / "testing-infrastructure" / "containers" / "security-scanner" / "shared" / "api-contracts" / "testing_api_models.py"
    local_models_path = PROJECT_ROOT / "testing-infrastructure" / "containers" / "security-scanner" / "app" / "models.py"
    
    if shared_models_path.exists() and local_models_path.exists():
        print("   ⚠️  Both shared and local models exist - consider consolidating")
    elif local_models_path.exists():
        print("   ✅ Using local models (current approach)")
    else:
        print("   ❌ No models found")
    
    print()
    
    # Recommendations
    print("4. Recommendations:")
    if enum_issues or structure_issue:
        print("   🔧 Update container models to match main app")
        print("   🔧 Add automated tests for compatibility")
    else:
        print("   ✅ Models are compatible")
        print("   💡 Consider adding CI checks for model synchronization")
        print("   💡 Add version numbers to models for tracking changes")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Model synchronization and compatibility checker")
    parser.add_argument("--check", action="store_true", help="Check compatibility")
    parser.add_argument("--validate", action="store_true", help="Validate model structures")
    parser.add_argument("--report", action="store_true", help="Generate full compatibility report")
    
    args = parser.parse_args()
    
    if args.check:
        issues = check_enum_compatibility()
        if issues:
            print("Compatibility issues found:")
            for issue in issues:
                print(f"  - {issue}")
            sys.exit(1)
        else:
            print("✅ Models are compatible")
    
    elif args.validate:
        issue = validate_result_structure()
        if issue:
            print(f"❌ Validation failed: {issue}")
            sys.exit(1)
        else:
            print("✅ Validation passed")
    
    elif args.report:
        generate_compatibility_report()
    
    else:
        generate_compatibility_report()
