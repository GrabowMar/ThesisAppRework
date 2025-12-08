#!/usr/bin/env python
"""
Quick test for report generation via API.
Tests that reports are saved to database and accessible.
"""

import requests
import json

API_BASE = "http://localhost:5000"
TOKEN = "a_S4ACkLNzuy2U4enBDinjWsDf423gnOQjcADKON_3e5TT8VxSCsVBSTG-zZbz-Z"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def list_reports():
    """List all reports via API."""
    r = requests.get(f"{API_BASE}/api/reports", headers=headers)
    return r.json()

def generate_report(model_slug, title):
    """Generate a model analysis report."""
    payload = {
        "report_type": "model_analysis",
        "format": "html",
        "config": {"model_slug": model_slug},
        "title": title,
        "expires_in_days": 30
    }
    r = requests.post(f"{API_BASE}/api/reports/generate", headers=headers, json=payload)
    return r.json()

def main():
    print("=== Testing Report Generation ===\n")
    
    # List existing reports
    print("1. Current reports in database:")
    data = list_reports()
    for rpt in data.get("reports", []):
        status_icon = "✓" if rpt["status"] == "completed" else "✗"
        print(f"   {status_icon} {rpt['report_id']}: {rpt['title']} ({rpt['status']})")
    print(f"   Total: {data.get('count', 0)} reports\n")
    
    # Generate a new test report
    print("2. Generating new test report...")
    result = generate_report("google_gemma-3-4b-it", "API Test Report")
    if result.get("success"):
        report = result["report"]
        print(f"   ✓ Report generated: {report['report_id']}")
        print(f"   Status: {report['status']}")
        print(f"   File size: {report.get('file_size', 'N/A')} bytes")
        print(f"   View at: {API_BASE}/reports/view/{report['report_id']}")
    else:
        print(f"   ✗ Failed: {result.get('error')}")
    
    # Verify it's in the list now
    print("\n3. Verifying report appears in list:")
    data = list_reports()
    print(f"   Total reports now: {data.get('count', 0)}")
    
    # Show URL to view reports
    print(f"\n4. View all reports at: {API_BASE}/reports/")
    print("   (requires login or session authentication)")

if __name__ == "__main__":
    main()
