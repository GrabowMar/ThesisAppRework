#!/usr/bin/env python3
"""
Quick test script to verify real ZAP integration in dynamic analyzer.
"""
import asyncio
import sys
from analyzer.analyzer_manager import AnalyzerManager

async def test_zap():
    """Run a ZAP scan via the dynamic analyzer."""
    manager = AnalyzerManager()
    
    print("Testing real ZAP integration...")
    print("=" * 60)
    
    # Run dynamic analysis which uses real ZAP
    print("\n[*] Running dynamic analysis with real OWASP ZAP...")
    print("[!] Note: This requires the app to be running on its configured ports")
    result = await manager.run_dynamic_analysis(
        model_slug="openai_gpt-4.1-2025-04-14",
        app_number=3,
        target_urls=["http://example.com"],  # Use a simple test URL
        tools=["zap"]  # Only ZAP
    )
    
    print(f"\n[+] Analysis completed!")
    print(f"Status: {result.get('status')}")
    print(f"Type: {result.get('type')}")
    print(f"\nFull result keys: {list(result.keys())}")
    
    # Debug: print the full result structure
    import json
    print(f"\nFull result:")
    print(json.dumps(result, indent=2, default=str)[:2000])
    
    # Dynamic analyzer returns result directly with 'analysis' key
    if 'analysis' in result:
        analysis = result['analysis']
        print(f"\n[*] Dynamic Analysis (ZAP) Results:")
        print(f"  Status: {analysis.get('status')}")
        print(f"  Services: {list(analysis.get('services', {}).keys())}")
        
        # Check if ZAP ran
        services = analysis.get('services', {})
        if 'dynamic' in services:
            dynamic = services['dynamic']
            tools = dynamic.get('tools', {})
            
            if 'zap' in tools:
                zap_result = tools['zap']
                print(f"\n  [>] ZAP Scanner Results:")
                print(f"    Status: {zap_result.get('status')}")
                print(f"    Version: {zap_result.get('version', 'N/A')}")
                print(f"    Finding Count: {zap_result.get('finding_count', 0)}")
                
                # Show sample findings
                findings = zap_result.get('findings', [])
                if findings:
                    print(f"\n    Sample vulnerabilities (first 5):")
                    for i, finding in enumerate(findings[:5], 1):
                        print(f"    {i}. [{finding.get('risk', 'N/A')}] {finding.get('alert', 'N/A')}")
                        print(f"       URL: {finding.get('url', 'N/A')}")
                        print(f"       Description: {finding.get('description', 'N/A')[:80]}...")
                else:
                    print(f"\n    [+] No vulnerabilities found!")
                
                # Check if SARIF was generated
                if 'sarif' in zap_result:
                    print(f"\n    [*] SARIF Report: Available")
                    sarif = zap_result.get('sarif', {})
                    print(f"       Version: {sarif.get('version', 'N/A')}")
                    runs = sarif.get('runs', [])
                    if runs:
                        results = runs[0].get('results', [])
                        print(f"       SARIF Results: {len(results)}")
            else:
                print("  [!] ZAP tool not found in results")
        else:
            print("  [!] No dynamic service in results")
    else:
        print("\n[!] No 'analysis' key in result")
        print(f"Result keys: {list(result.keys())}")
    
    return result

if __name__ == '__main__':
    try:
        result = asyncio.run(test_zap())
        sys.exit(0)
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
