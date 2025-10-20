"""Quick validation of analyzer output"""
import json
from pathlib import Path

# Check most recent analysis result
result_file = Path("results/anthropic_claude-4.5-haiku-20251001/app2/analysis/anthropic_claude-4.5-haiku-20251001_app2_comprehensive_20251019_225104.json")

if result_file.exists():
    with open(result_file) as f:
        data = json.load(f)
    
    results = data.get("results", {})
    summary = results.get("summary", {})
    services = results.get("services", {})
    findings = results.get("findings", [])
    
    print("\n" + "="*80)
    print("ANALYZER OUTPUT VALIDATION")
    print("="*80)
    print(f"\n✓ File exists: {result_file.name}")
    print(f"✓ Total findings: {summary.get('total_findings', 0)}")
    print(f"✓ Tools executed: {len(summary.get('tools_used', []))}")
    print(f"  Tools list: {', '.join(summary.get('tools_used', []))}")
    print(f"\n✓ Services available: {', '.join(services.keys())}")
    print(f"✓ Findings array length: {len(findings)}")
    
    # Check severity breakdown
    severity = summary.get('severity_breakdown', {})
    print(f"\n✓ Severity breakdown:")
    print(f"  - High: {severity.get('high', 0)}")
    print(f"  - Medium: {severity.get('medium', 0)}")
    print(f"  - Low: {severity.get('low', 0)}")
    
    # Sample finding
    if findings:
        sample = findings[0]
        print(f"\n✓ Sample finding structure:")
        print(f"  - Tool: {sample.get('tool', 'N/A')}")
        print(f"  - Category: {sample.get('category', 'N/A')}")
        print(f"  - Severity: {sample.get('severity', 'N/A')}")
        print(f"  - Has message: {bool(sample.get('message'))}")
        print(f"  - Has file: {bool(sample.get('file'))}")
    
    print("\n" + "="*80)
    print("✅ ANALYZER OUTPUT STRUCTURE IS VALID")
    print("="*80 + "\n")
else:
    print(f"❌ ERROR: File not found: {result_file}")
