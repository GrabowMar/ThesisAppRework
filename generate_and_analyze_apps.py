"""
Generate and Analyze Multiple Apps
Creates 3 new apps for Haiku and runs comprehensive analysis on each.
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import os
os.environ['TESTING'] = '1'

from app.factory import create_app
from app.models import db, ModelCapability
from app.services.service_locator import ServiceLocator
import asyncio

async def generate_app(model_slug: str, app_number: int):
    """Generate a new app for the given model."""
    print(f"\n{'='*80}")
    print(f"GENERATING APP {app_number} FOR {model_slug}")
    print('='*80)
    
    app = create_app()
    
    with app.app_context():
        generation_service = ServiceLocator.get_generation_service()
        
        # Check if app already exists
        app_dir = Path(f"generated/apps/{model_slug}/app{app_number}")
        if app_dir.exists():
            print(f"⚠️  App {app_number} already exists at {app_dir}")
            return True
        
        print(f"\n📝 Submitting generation request...")
        
        try:
            # Submit generation request
            result = await generation_service.submit_generation_request(
                model_slug=model_slug,
                app_number=app_number,
                template_type='standard',
                prompt_override=None,
                priority='normal'
            )
            
            if result and result.get('status') == 'success':
                task_id = result.get('task_id')
                print(f"✓ Generation submitted: {task_id}")
                
                # Wait for completion
                print(f"\n⏳ Waiting for generation to complete...")
                max_wait = 300  # 5 minutes
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    # Check if app directory was created
                    if app_dir.exists():
                        print(f"✓ App directory created: {app_dir}")
                        return True
                    
                    await asyncio.sleep(5)
                    print(".", end="", flush=True)
                
                print(f"\n⚠️  Timeout waiting for app generation")
                return False
            else:
                print(f"❌ Generation failed: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Error during generation: {e}")
            import traceback
            traceback.print_exc()
            return False


async def analyze_app(model_slug: str, app_number: int):
    """Run comprehensive analysis on an app."""
    print(f"\n{'='*80}")
    print(f"ANALYZING APP {app_number} FOR {model_slug}")
    print('='*80)
    
    # Import analyzer manager
    sys.path.insert(0, str(Path(__file__).parent / 'analyzer'))
    from analyzer_manager import AnalyzerManager
    
    try:
        manager = AnalyzerManager()
        
        # Check if app exists
        app_dir = Path(f"generated/apps/{model_slug}/app{app_number}")
        if not app_dir.exists():
            print(f"❌ App directory not found: {app_dir}")
            return False
        
        print(f"\n🔍 Starting comprehensive analysis...")
        print(f"   Model: {model_slug}")
        print(f"   App: {app_number}")
        
        # Run comprehensive analysis
        result = await manager.run_comprehensive_analysis(
            model_slug=model_slug,
            app_number=app_number
        )
        
        if result:
            print(f"\n✓ Analysis completed successfully!")
            
            # Show summary
            if 'summary' in result:
                summary = result['summary']
                print(f"\n📊 Analysis Summary:")
                print(f"   Total Findings: {summary.get('total_findings', 0)}")
                print(f"   Critical: {summary.get('critical_count', 0)}")
                print(f"   High: {summary.get('high_count', 0)}")
                print(f"   Medium: {summary.get('medium_count', 0)}")
                print(f"   Low: {summary.get('low_count', 0)}")
            
            return True
        else:
            print(f"❌ Analysis failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main workflow: generate 3 apps and analyze each."""
    print("\n" + "="*80)
    print("GENERATE AND ANALYZE MULTIPLE APPS")
    print("="*80)
    
    model_slug = "anthropic_claude-4.5-haiku-20251001"
    
    # Apps to generate (2, 3, 4)
    apps_to_create = [2, 3, 4]
    
    results = {
        'generated': [],
        'analyzed': [],
        'failed_generation': [],
        'failed_analysis': []
    }
    
    # Step 1: Generate all apps
    print("\n" + "="*80)
    print("STEP 1: GENERATE APPS")
    print("="*80)
    
    for app_num in apps_to_create:
        success = await generate_app(model_slug, app_num)
        if success:
            results['generated'].append(app_num)
        else:
            results['failed_generation'].append(app_num)
        
        # Small delay between generations
        await asyncio.sleep(2)
    
    # Step 2: Analyze all apps (including app1)
    print("\n" + "="*80)
    print("STEP 2: ANALYZE ALL APPS")
    print("="*80)
    
    all_apps = [1] + apps_to_create
    
    for app_num in all_apps:
        success = await analyze_app(model_slug, app_num)
        if success:
            results['analyzed'].append(app_num)
        else:
            results['failed_analysis'].append(app_num)
        
        # Small delay between analyses
        await asyncio.sleep(2)
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    print(f"\n✅ Generated Apps: {len(results['generated'])}")
    for app_num in results['generated']:
        print(f"   - App {app_num}")
    
    if results['failed_generation']:
        print(f"\n❌ Failed Generations: {len(results['failed_generation'])}")
        for app_num in results['failed_generation']:
            print(f"   - App {app_num}")
    
    print(f"\n✅ Analyzed Apps: {len(results['analyzed'])}")
    for app_num in results['analyzed']:
        print(f"   - App {app_num}")
    
    if results['failed_analysis']:
        print(f"\n❌ Failed Analyses: {len(results['failed_analysis'])}")
        for app_num in results['failed_analysis']:
            print(f"   - App {app_num}")
    
    print("\n" + "="*80)
    
    success = (len(results['failed_generation']) == 0 and 
               len(results['failed_analysis']) == 0)
    
    if success:
        print("✓ ALL OPERATIONS COMPLETED SUCCESSFULLY!")
    else:
        print("⚠️  SOME OPERATIONS FAILED - CHECK LOGS ABOVE")
    
    print("="*80)
    
    return success


if __name__ == '__main__':
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
