"""
Test the enhanced CLI analysis system with database integration.
This script tests the full analysis workflow and database saving.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask import Flask
from extensions import db
from models import SecurityAnalysis, GeneratedApplication, AnalysisStatus
from security_analysis_service import UnifiedCLIAnalyzer

def create_test_app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    
    # Use absolute path to database
    db_path = Path(__file__).parent / "src" / "data" / "thesis_app.db"
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    return app

def test_cli_analysis():
    """Test CLI analysis with database integration."""
    print("🧪 Testing CLI Analysis System with Database Integration")
    print("=" * 60)
    
    # Create Flask app and context
    app = create_test_app()
    
    with app.app_context():
        # Initialize analyzer
        analyzer = UnifiedCLIAnalyzer(Path.cwd())
        
        # Test model and app
        test_model = "anthropic_claude-3.7-sonnet"
        test_app_num = 1
        
        print(f"📋 Test Target: {test_model}/app{test_app_num}")
        
        # Check if GeneratedApplication exists
        gen_app = GeneratedApplication.query.filter_by(
            model_slug=test_model, 
            app_number=test_app_num
        ).first()
        
        if not gen_app:
            print(f"⚠️ GeneratedApplication not found. Creating placeholder...")
            gen_app = GeneratedApplication(
                model_slug=test_model,
                app_number=test_app_num,
                app_type="Test Application",
                provider="test",
                generation_status="generated"
            )
            db.session.add(gen_app)
            db.session.commit()
            print(f"✅ Created GeneratedApplication with ID: {gen_app.id}")
        else:
            print(f"✅ Found existing GeneratedApplication with ID: {gen_app.id}")
        
        # Check available tools
        print("\n🔧 Available Tools:")
        available_tools = analyzer.get_available_tools()
        total_tools = 0
        for category, tools in available_tools.items():
            print(f"   {category}: {len(tools)} tools - {tools}")
            total_tools += len(tools)
        print(f"   📊 Total: {total_tools} tools across 4 categories")
        
        # Run full analysis with all tools
        print(f"\n🚀 Running Full CLI Analysis (use_all_tools=True)...")
        
        results = analyzer.run_full_analysis(
            model=test_model,
            app_num=test_app_num,
            use_all_tools=True,
            save_to_db=True,
            force_rerun=True
        )
        
        # Display results summary
        print("\n📊 Analysis Results:")
        total_issues = 0
        for category, data in results.items():
            if category == "metadata":
                continue
            if isinstance(data, dict) and "issues" in data:
                issues_count = len(data["issues"])
                total_issues += issues_count
                tool_status = data.get("tool_status", {})
                print(f"   {category}: {issues_count} issues")
                for tool_name, status in tool_status.items():
                    print(f"      {tool_name}: {status}")
        
        print(f"   🎯 Total Issues: {total_issues}")
        
        # Check database record
        print(f"\n💾 Database Verification:")
        analysis = SecurityAnalysis.query.filter_by(application_id=gen_app.id).first()
        
        if analysis:
            print(f"   ✅ SecurityAnalysis record found")
            print(f"   📊 Status: {analysis.status.value}")
            print(f"   📈 Total Issues: {analysis.total_issues}")
            print(f"   🔴 Critical: {analysis.critical_severity_count}")
            print(f"   🟠 High: {analysis.high_severity_count}")
            print(f"   🟡 Medium: {analysis.medium_severity_count}")
            print(f"   🟢 Low: {analysis.low_severity_count}")
            
            # Check tool configuration
            enabled_tools = analysis.get_enabled_tools()
            print(f"   🔧 Enabled Tools: {sum(enabled_tools.values())}/{len(enabled_tools)}")
            for tool, enabled in enabled_tools.items():
                status = "✅" if enabled else "❌"
                print(f"      {status} {tool}")
                
            # Check results data
            results_data = analysis.get_results()
            if results_data:
                print(f"   📄 Results Data: Available ({len(str(results_data))} chars)")
            else:
                print(f"   📄 Results Data: Not available")
        else:
            print(f"   ❌ No SecurityAnalysis record found")
        
        print(f"\n✅ CLI Analysis Test Complete!")
        
        return results, analysis

if __name__ == "__main__":
    try:
        results, analysis = test_cli_analysis()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
