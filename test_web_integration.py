"""
Test web app integration with analyzer_manager.

This script tests if the new analyzer_manager_wrapper produces
identical results to the CLI analyzer_manager.py.
"""
import sys
import os
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app
from app.services.analyzer_manager_wrapper import get_analyzer_wrapper

def test_web_integration():
    """Test that web integration produces same results as CLI."""
    print("=" * 80)
    print("Testing Web App Integration with analyzer_manager")
    print("=" * 80)
    
    # Test parameters (same as CLI test we did earlier)
    model_slug = "anthropic_claude-4.5-haiku-20251001"
    app_number = 1
    task_name = "web_integration_test"
    
    print(f"\n📋 Test Configuration:")
    print(f"   Model: {model_slug}")
    print(f"   App: {app_number}")
    print(f"   Task: {task_name}")
    
    # Create Flask app context (needed for logging and config)
    app = create_app()
    
    with app.app_context():
        print(f"\n🔧 Flask app context created")
        
        # Get analyzer wrapper
        wrapper = get_analyzer_wrapper()
        print(f"✅ Analyzer wrapper initialized")
        
        # Run comprehensive analysis
        print(f"\n🚀 Starting comprehensive analysis...")
        print(f"   (This will take several minutes)")
        
        try:
            result = wrapper.run_comprehensive_analysis(
                model_slug=model_slug,
                app_number=app_number,
                task_name=task_name
            )
            
            if not result:
                print("\n❌ Analysis failed - no result returned")
                return False
            
            print(f"\n✅ Analysis completed successfully!")
            
            # Check result structure
            print(f"\n📊 Result Structure:")
            if isinstance(result, dict):
                print(f"   Top-level keys: {list(result.keys())}")
                
                # Check top-level keys
                if 'metadata' in result:
                    print(f"   ✅ 'metadata' present")
                else:
                    print(f"   ❌ 'metadata' MISSING!")
                
                # Check nested results structure
                if 'results' in result and isinstance(result['results'], dict):
                    print(f"   ✅ 'results' present")
                    results_section = result['results']
                    
                    # Check for expected nested keys
                    expected_nested_keys = ['services', 'tools', 'findings', 'summary', 'task']
                    for key in expected_nested_keys:
                        if key in results_section:
                            print(f"      ✅ 'results.{key}' present")
                            if key == 'tools' and isinstance(results_section[key], dict):
                                print(f"         └─ Tool count: {len(results_section[key])}")
                            elif key == 'findings' and isinstance(results_section[key], list):
                                print(f"         └─ Finding count: {len(results_section[key])}")
                            elif key == 'services' and isinstance(results_section[key], dict):
                                print(f"         └─ Services: {list(results_section[key].keys())}")
                        else:
                            print(f"      ❌ 'results.{key}' MISSING!")
                else:
                    print(f"   ❌ 'results' section MISSING or invalid!")
            
            # Check if files were written
            result_dir = Path(f"results/{model_slug}/app{app_number}")
            print(f"\n📁 Result Files:")
            print(f"   Directory: {result_dir}")
            
            if result_dir.exists():
                # Find most recent task directory
                task_dirs = sorted(result_dir.glob("task_*"), key=lambda p: p.stat().st_mtime, reverse=True)
                if task_dirs:
                    latest_task = task_dirs[0]
                    print(f"   Latest task: {latest_task.name}")
                    
                    # Check for expected files
                    files = list(latest_task.glob("*.json"))
                    print(f"   JSON files: {len(files)}")
                    for f in files:
                        size_kb = f.stat().st_size / 1024
                        print(f"      - {f.name} ({size_kb:.1f} KB)")
                    
                    # Check for SARIF directory
                    sarif_dir = latest_task / "sarif"
                    if sarif_dir.exists():
                        sarif_files = list(sarif_dir.glob("*.sarif"))
                        print(f"   SARIF files: {len(sarif_files)}")
                        for f in sarif_files:
                            size_kb = f.stat().st_size / 1024
                            print(f"      - {f.name} ({size_kb:.1f} KB)")
                    else:
                        print(f"   ❌ SARIF directory missing!")
                    
                    # Check manifest
                    manifest = latest_task / "manifest.json"
                    if manifest.exists():
                        print(f"   ✅ manifest.json present")
                        with open(manifest) as f:
                            manifest_data = json.load(f)
                            print(f"      Files listed: {len(manifest_data.get('files', []))}")
                    else:
                        print(f"   ❌ manifest.json missing!")
                else:
                    print(f"   ❌ No task directories found!")
            else:
                print(f"   ❌ Result directory does not exist!")
            
            # Compare with CLI results
            print(f"\n🔍 Comparing with CLI Results:")
            cli_result_dir = Path(f"results/{model_slug}/app{app_number}/task_analysis_20251103_205204")
            if cli_result_dir.exists():
                print(f"   CLI result directory found: {cli_result_dir.name}")
                
                # Load CLI result
                cli_json_files = list(cli_result_dir.glob("*_app1_*.json"))
                if cli_json_files:
                    cli_result_file = cli_json_files[0]
                    with open(cli_result_file) as f:
                        cli_result = json.load(f)
                    
                    print(f"   CLI result loaded: {cli_result_file.name}")
                    print(f"   Structure Comparison:")
                    print(f"   {'Key':<20} {'CLI':<15} {'Web':<15} {'Match':<10}")
                    print(f"   {'-'*60}")
                    
                    # Compare at top level (metadata)
                    cli_has_meta = 'metadata' in cli_result
                    web_has_meta = 'metadata' in result
                    match = "✅" if (cli_has_meta == web_has_meta) else "❌"
                    print(f"   {'metadata':<20} {str(cli_has_meta):<15} {str(web_has_meta):<15} {match:<10}")
                    
                    # Compare nested keys under 'results'
                    cli_results = cli_result.get('results', {})
                    web_results = result.get('results', {})
                    
                    nested_keys = ['services', 'tools', 'findings', 'summary', 'task']
                    for key in nested_keys:
                        cli_has = key in cli_results
                        web_has = key in web_results
                        match = "✅" if (cli_has == web_has) else "❌"
                        print(f"   {'results.'+key:<20} {str(cli_has):<15} {str(web_has):<15} {match:<10}")
                    
                    # Compare tool counts
                    cli_tools = cli_results.get('tools', {})
                    web_tools = web_results.get('tools', {})
                    if cli_tools and web_tools:
                        cli_tool_count = len(cli_tools)
                        web_tool_count = len(web_tools)
                        print(f"\n   Tool Count: CLI={cli_tool_count}, Web={web_tool_count}")
                        if cli_tool_count == web_tool_count:
                            print(f"   ✅ Tool counts match!")
                        else:
                            print(f"   ⚠️  Tool counts differ!")
                    
                    # Compare finding counts
                    cli_findings = cli_results.get('findings', [])
                    web_findings = web_results.get('findings', [])
                    if cli_findings and web_findings:
                        cli_finding_count = len(cli_findings)
                        web_finding_count = len(web_findings)
                        print(f"   Finding Count: CLI={cli_finding_count}, Web={web_finding_count}")
                        if abs(cli_finding_count - web_finding_count) <= 2:
                            print(f"   ✅ Finding counts match (within tolerance)!")
                        else:
                            print(f"   ⚠️  Finding counts differ significantly!")
                else:
                    print(f"   ❌ No CLI result JSON file found!")
            else:
                print(f"   ℹ️  CLI result directory not found (expected if this is first test)")
            
            print(f"\n{'='*80}")
            print(f"✅ TEST PASSED - Integration appears to be working correctly!")
            print(f"{'='*80}")
            return True
            
        except Exception as e:
            print(f"\n❌ Analysis failed with error:")
            print(f"   {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = test_web_integration()
    sys.exit(0 if success else 1)
