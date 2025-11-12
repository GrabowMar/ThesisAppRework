"""
Test Report Generation

Tests various report types and formats.
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:5000"
API_URL = f"{BASE_URL}/api/reports"

def test_app_analysis_report():
    """Test App Analysis Report (single app)."""
    print("\n" + "="*60)
    print("TEST 1: App Analysis Report - PDF")
    print("="*60)
    
    payload = {
        "report_type": "app_analysis",
        "format": "pdf",
        "config": {
            "model_slug": "anthropic_claude-4.5-haiku-20251001",
            "app_number": 1,
            "include_findings": True,
            "include_metrics": True,
            "severity_filter": ["critical", "high", "medium", "low"]
        },
        "title": "App Analysis - Claude 4.5 Haiku - App 1",
        "description": "Complete analysis report for app 1"
    }
    
    print(f"Request: POST {API_URL}/generate")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(f"{API_URL}/generate", json=payload)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        report = response.json()['report']
        report_id = report['report_id']
        print(f"\n✓ Report created: {report_id}")
        print(f"  File: {report['file_path']}")
        print(f"  Size: {report['file_size']} bytes")
        print(f"  Status: {report['status']}")
        return report_id
    else:
        print(f"\n✗ Failed to create report")
        return None

def test_model_comparison_report():
    """Test Model Comparison Report (multiple models)."""
    print("\n" + "="*60)
    print("TEST 2: Model Comparison Report - HTML")
    print("="*60)
    
    payload = {
        "report_type": "model_comparison",
        "format": "html",
        "config": {
            "model_slugs": [
                "anthropic_claude-4.5-haiku-20251001",
                "amazon_nova-pro-v1"
            ],
            "app_numbers": [1],
            "metrics": [
                "code_quality",
                "security",
                "performance"
            ],
            "include_charts": True
        },
        "title": "Model Comparison: Claude vs Nova",
        "description": "Comparison of app 1 across models"
    }
    
    print(f"Request: POST {API_URL}/generate")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(f"{API_URL}/generate", json=payload)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        report = response.json()['report']
        report_id = report['report_id']
        print(f"\n✓ Report created: {report_id}")
        print(f"  File: {report['file_path']}")
        print(f"  Size: {report['file_size']} bytes")
        return report_id
    else:
        print(f"\n✗ Failed to create report")
        return None

def test_tool_effectiveness_report():
    """Test Tool Effectiveness Report."""
    print("\n" + "="*60)
    print("TEST 3: Tool Effectiveness Report - Excel")
    print("="*60)
    
    payload = {
        "report_type": "tool_effectiveness",
        "format": "excel",
        "config": {
            "tools": ["eslint", "bandit", "safety", "semgrep"],
            "model_slugs": ["anthropic_claude-4.5-haiku-20251001"],
            "app_numbers": [1],
            "metrics": [
                "findings_count",
                "execution_time",
                "severity_distribution"
            ]
        },
        "title": "Tool Effectiveness Analysis",
        "description": "Performance metrics for analysis tools"
    }
    
    print(f"Request: POST {API_URL}/generate")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(f"{API_URL}/generate", json=payload)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        report = response.json()['report']
        report_id = report['report_id']
        print(f"\n✓ Report created: {report_id}")
        print(f"  File: {report['file_path']}")
        print(f"  Size: {report['file_size']} bytes")
        return report_id
    else:
        print(f"\n✗ Failed to create report")
        return None

def test_executive_summary():
    """Test Executive Summary Report."""
    print("\n" + "="*60)
    print("TEST 4: Executive Summary - JSON")
    print("="*60)
    
    payload = {
        "report_type": "executive_summary",
        "format": "json",
        "config": {
            "period_days": 30,
            "include_trends": True,
            "include_recommendations": True,
            "model_slugs": ["anthropic_claude-4.5-haiku-20251001"]
        },
        "title": "Executive Summary - Last 30 Days",
        "description": "High-level overview of analysis activities"
    }
    
    print(f"Request: POST {API_URL}/generate")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(f"{API_URL}/generate", json=payload)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        report = response.json()['report']
        report_id = report['report_id']
        print(f"\n✓ Report created: {report_id}")
        print(f"  File: {report['file_path']}")
        print(f"  Size: {report['file_size']} bytes")
        return report_id
    else:
        print(f"\n✗ Failed to create report")
        return None

def test_list_reports():
    """Test listing reports."""
    print("\n" + "="*60)
    print("TEST 5: List Reports")
    print("="*60)
    
    response = requests.get(API_URL)
    print(f"Request: GET {API_URL}")
    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nTotal reports: {data['count']}")
        for report in data['reports']:
            print(f"\n  Report ID: {report['report_id']}")
            print(f"  Type: {report['report_type']}")
            print(f"  Format: {report['format']}")
            print(f"  Status: {report['status']}")
            print(f"  Title: {report['title']}")
            print(f"  Created: {report['created_at']}")
            print(f"  File: {report['file_path']}")
    else:
        print(f"✗ Failed to list reports: {response.json()}")

def test_download_report(report_id):
    """Test downloading a report."""
    if not report_id:
        print("\n⊘ Skipping download test - no report ID")
        return
        
    print("\n" + "="*60)
    print(f"TEST 6: Download Report {report_id}")
    print("="*60)
    
    response = requests.get(f"{API_URL}/download/{report_id}")
    print(f"Request: GET {API_URL}/download/{report_id}")
    print(f"Response Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    print(f"Content-Length: {len(response.content)} bytes")
    
    if response.status_code == 200:
        # Save to test output
        filename = f"test_report_{report_id}.{response.headers.get('Content-Type', '').split('/')[-1]}"
        output_path = Path(__file__).parent / "reports" / filename
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_bytes(response.content)
        print(f"\n✓ Report downloaded to: {output_path}")
    else:
        print(f"\n✗ Failed to download report")

def verify_report_files():
    """Verify that report files were created in the filesystem."""
    print("\n" + "="*60)
    print("TEST 7: Verify Report Files")
    print("="*60)
    
    reports_dir = Path(__file__).parent / "reports"
    if reports_dir.exists():
        files = list(reports_dir.iterdir())
        print(f"\nReports directory: {reports_dir}")
        print(f"Total files: {len(files)}")
        for file in files:
            print(f"  - {file.name} ({file.stat().st_size} bytes)")
    else:
        print("\n⊘ Reports directory not found")

def main():
    """Run all report tests."""
    print("\n" + "="*80)
    print(" "*20 + "REPORT GENERATION TEST SUITE")
    print("="*80)
    
    print("\nTesting report generation system with various report types and formats...")
    print(f"API Base URL: {BASE_URL}")
    
    # Test various report types
    report_ids = []
    
    # Test 1: App Analysis (PDF)
    report_id = test_app_analysis_report()
    if report_id:
        report_ids.append(report_id)
    time.sleep(1)
    
    # Test 2: Model Comparison (HTML)
    report_id = test_model_comparison_report()
    if report_id:
        report_ids.append(report_id)
    time.sleep(1)
    
    # Test 3: Tool Effectiveness (Excel)
    report_id = test_tool_effectiveness_report()
    if report_id:
        report_ids.append(report_id)
    time.sleep(1)
    
    # Test 4: Executive Summary (JSON)
    report_id = test_executive_summary()
    if report_id:
        report_ids.append(report_id)
    time.sleep(1)
    
    # Test 5: List all reports
    test_list_reports()
    
    # Test 6: Download one report
    if report_ids:
        test_download_report(report_ids[0])
    
    # Test 7: Verify files
    verify_report_files()
    
    # Summary
    print("\n" + "="*80)
    print(" "*25 + "TEST SUMMARY")
    print("="*80)
    print(f"Reports created: {len(report_ids)}")
    print(f"Report IDs: {', '.join(report_ids) if report_ids else 'None'}")
    print("\n✓ All tests completed!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
