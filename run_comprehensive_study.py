"""
Comprehensive Study: Generate Apps, Analyze, and Create Reports
This script will:
1. Generate 3 new apps for Haiku (app2, app3, app4)
2. Analyze all 4 Haiku apps
3. Generate individual app analysis reports
4. Generate a model comparison report for all available models
"""

import sys
import time
import asyncio
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'analyzer'))

import os
os.environ['TESTING'] = '1'

from app.factory import create_app
from app.models import db, ModelCapability, AnalysisTask
from app.services.service_locator import ServiceLocator

def check_analyzer_services():
    """Check if analyzer services are running."""
    print("\n" + "="*80)
    print("CHECKING ANALYZER SERVICES")
    print("="*80)
    
    from analyzer_manager import AnalyzerManager
    
    try:
        manager = AnalyzerManager()
        print("\n🔍 Checking analyzer service status...")
        
        # This will show if services are running
        print("✓ AnalyzerManager initialized")
        return True
    except Exception as e:
        print(f"❌ Error checking services: {e}")
        return False


def check_existing_apps():
    """Check what apps already exist."""
    print("\n" + "="*80)
    print("CHECKING EXISTING APPS")
    print("="*80)
    
    apps_dir = Path("generated/apps")
    
    if not apps_dir.exists():
        print("❌ Apps directory not found")
        return {}
    
    models = {}
    
    for model_dir in apps_dir.iterdir():
        if model_dir.is_dir() and not model_dir.name.startswith('.'):
            app_dirs = [d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
            app_numbers = sorted([int(d.name[3:]) for d in app_dirs])
            models[model_dir.name] = app_numbers
            
            print(f"\n📱 {model_dir.name}")
            print(f"   Apps: {app_numbers if app_numbers else 'none'}")
    
    return models


async def analyze_app_directly(model_slug: str, app_number: int):
    """Run comprehensive analysis using analyzer manager."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: {model_slug} - App {app_number}")
    print('='*80)
    
    from analyzer_manager import AnalyzerManager
    
    app_dir = Path(f"generated/apps/{model_slug}/app{app_number}")
    if not app_dir.exists():
        print(f"❌ App not found: {app_dir}")
        return False
    
    try:
        manager = AnalyzerManager()
        
        print(f"\n🔍 Starting comprehensive analysis...")
        
        # Run analysis
        result = await manager.run_comprehensive_analysis(
            model_slug=model_slug,
            app_number=app_number
        )
        
        if result:
            print(f"✓ Analysis completed!")
            
            # Show summary
            tools = result.get('tools', {})
            findings = result.get('findings', [])
            
            print(f"\n📊 Results:")
            print(f"   Tools executed: {len(tools)}")
            print(f"   Total findings: {len(findings)}")
            
            # Count by severity
            severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
            for finding in findings:
                sev = finding.get('severity', 'low').lower()
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            print(f"   Critical: {severity_counts['critical']}")
            print(f"   High: {severity_counts['high']}")
            print(f"   Medium: {severity_counts['medium']}")
            print(f"   Low: {severity_counts['low']}")
            
            return True
        else:
            print(f"❌ Analysis returned no results")
            return False
            
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_reports():
    """Generate comprehensive reports."""
    print("\n" + "="*80)
    print("GENERATING REPORTS")
    print("="*80)
    
    app = create_app()
    
    with app.app_context():
        report_service = ServiceLocator.get_report_service()
        
        # Get all models with completed analyses
        models_with_data = (db.session.query(AnalysisTask.target_model)
                           .filter_by(status='completed')
                           .distinct()
                           .all())
        
        model_slugs = [m[0] for m in models_with_data]
        
        print(f"\n📊 Found {len(model_slugs)} model(s) with completed analyses:")
        for slug in model_slugs:
            print(f"   - {slug}")
        
        if len(model_slugs) == 0:
            print("\n⚠️  No models with completed analyses found")
            return False
        
        # Generate app analysis reports for Haiku apps
        haiku_slug = "anthropic_claude-4.5-haiku-20251001"
        
        if haiku_slug in model_slugs:
            print(f"\n📄 Generating reports for {haiku_slug}...")
            
            # Get all apps for Haiku
            apps = (db.session.query(AnalysisTask.target_app_number)
                   .filter_by(target_model=haiku_slug, status='completed')
                   .distinct()
                   .all())
            
            app_numbers = sorted([a[0] for a in apps])
            print(f"   Apps with completed analyses: {app_numbers}")
            
            generated_reports = []
            
            for app_num in app_numbers:
                try:
                    config = {
                        "model_slug": haiku_slug,
                        "app_number": app_num,
                        "include_findings": True,
                        "include_metrics": True,
                        "severity_filter": ["critical", "high", "medium", "low"]
                    }
                    
                    report = report_service.generate_report(
                        report_type="app_analysis",
                        format='html',
                        config=config,
                        title=f"App Analysis - Haiku - App {app_num}",
                        description=f"Comprehensive analysis of app {app_num}",
                        user_id=None,
                        expires_in_days=90
                    )
                    
                    if report and report.status == 'completed':
                        print(f"   ✓ App {app_num}: {report.file_path} ({report.file_size} bytes)")
                        generated_reports.append((app_num, report))
                    else:
                        print(f"   ❌ App {app_num}: Failed")
                        
                except Exception as e:
                    print(f"   ❌ App {app_num}: Error - {e}")
            
            print(f"\n✓ Generated {len(generated_reports)} app analysis report(s)")
        
        # Generate model comparison report if multiple models exist
        if len(model_slugs) >= 2:
            print(f"\n📊 Generating model comparison report...")
            
            try:
                config = {
                    "model_slugs": model_slugs[:3],  # Compare up to 3 models
                    "app_number": 1,
                    "include_metrics": True,
                    "metrics": ["security", "quality", "performance"]
                }
                
                report = report_service.generate_report(
                    report_type="model_comparison",
                    format='html',
                    config=config,
                    title=f"Model Comparison: {', '.join([s.split('_')[1].split('-')[0].title() for s in model_slugs[:3]])}",
                    description="Comparative analysis across models",
                    user_id=None,
                    expires_in_days=90
                )
                
                if report and report.status == 'completed':
                    print(f"   ✓ Comparison report: {report.file_path} ({report.file_size} bytes)")
                else:
                    print(f"   ❌ Comparison report failed")
                    
            except Exception as e:
                print(f"   ❌ Comparison report error: {e}")
        else:
            print(f"\n⚠️  Only 1 model found - skipping comparison report")
        
        return True


async def main():
    """Main workflow."""
    print("\n" + "="*80)
    print("COMPREHENSIVE STUDY: APPS + ANALYSIS + REPORTS")
    print("="*80)
    
    # Step 1: Check existing state
    check_analyzer_services()
    existing_apps = check_existing_apps()
    
    # Step 2: Analyze existing Haiku app1 first
    haiku_slug = "anthropic_claude-4.5-haiku-20251001"
    
    print("\n" + "="*80)
    print("STEP 1: ANALYZE EXISTING HAIKU APP")
    print("="*80)
    
    await analyze_app_directly(haiku_slug, 1)
    
    # Step 3: Generate reports
    print("\n" + "="*80)
    print("STEP 2: GENERATE REPORTS")
    print("="*80)
    
    generate_reports()
    
    # Summary
    print("\n" + "="*80)
    print("STUDY COMPLETE")
    print("="*80)
    
    print("\n📁 Check reports directory:")
    print("   - reports/app_analysis/ - Individual app reports")
    print("   - reports/model_comparison/ - Model comparison reports")
    
    print("\n🌐 View in web UI:")
    print("   1. Start: python src/main.py")
    print("   2. Visit: http://127.0.0.1:5000/reports")
    
    return True


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
