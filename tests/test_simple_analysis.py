#!/usr/bin/env python3
"""
Simple test script to debug the analysis integration.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_analysis_integration():
    """Test the analysis integration with the analyzer services."""
    print("=" * 60)
    print("Testing Analysis Integration")
    print("=" * 60)
    
    # Test 1: Direct task execution without Flask app context
    print("1. Testing direct security analysis task...")
    try:
        from app.tasks import security_analysis_task
        
        print("   🔄 Running security analysis task...")
        result = security_analysis_task.run(
            'nousresearch_hermes-4-405b', 
            1, 
            tools=['bandit', 'safety', 'pylint']
        )
        
        print("   ✅ Analysis completed!")
        print(f"   📋 Status: {result.get('status', 'unknown')}")
        print(f"   📋 Model: {result.get('model_slug')}")
        print(f"   📋 App: {result.get('app_number')}")
        
        # Show the full result for debugging
        print(f"   🔍 Full result: {result}")
        
        if 'result' in result and isinstance(result['result'], dict):
            analysis_result = result['result']
            print(f"   📋 Analysis status: {analysis_result.get('status', 'unknown')}")
            
            # Show any error details
            if 'error' in analysis_result:
                print(f"   ❌ Error details: {analysis_result['error']}")
            
            if 'results' in analysis_result:
                results = analysis_result['results']
                if 'analysis' in results:
                    analysis_data = results['analysis']
                    if 'summary' in analysis_data:
                        summary = analysis_data['summary']
                        print(f"   📊 Total issues: {summary.get('total_issues_found', 0)}")
                        print(f"   📊 Tools run: {summary.get('tools_run_successfully', 0)}")
                
    except Exception as e:
        print(f"   ❌ Failed to run analysis: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_analysis_integration()
