#!/usr/bin/env python3
"""
Test script for Analyzer Configuration Service
==============================================

Tests the enhanced analyzer configuration service to ensure it properly:
1. Detects models from database and misc folder
2. Detects apps from database and misc folder  
3. Can validate model/app combinations
4. Can sync database from misc folder
5. Can generate analysis plans
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.factory import create_app
from app.services.analyzer_config_service import AnalyzerConfigService
from app.models import ModelCapability, GeneratedApplication

def test_analyzer_config_service():
    """Test the analyzer configuration service."""
    app = create_app()
    
    with app.app_context():
        print("Testing Analyzer Configuration Service")
        print("=" * 50)
        
        # Initialize service
        config_service = AnalyzerConfigService()
        
        # Test 1: Get available models
        print("\n1. Testing get_available_models()...")
        models = config_service.get_available_models()
        print(f"Found {len(models)} models")
        
        for model in models[:5]:  # Show first 5
            print(f"  - {model['slug']} ({model['provider']}) [{model['source']}]")
        
        if len(models) > 5:
            print(f"  ... and {len(models) - 5} more")
        
        # Test 2: Get available apps
        print("\n2. Testing get_available_apps()...")
        apps = config_service.get_available_apps()
        print(f"Found {len(apps)} total apps")
        
        # Group by model
        apps_by_model = {}
        for app in apps:
            model = app['model_slug']
            if model not in apps_by_model:
                apps_by_model[model] = []
            apps_by_model[model].append(app)
        
        print(f"Apps distributed across {len(apps_by_model)} models")
        for model, model_apps in list(apps_by_model.items())[:3]:  # Show first 3 models
            print(f"  - {model}: {len(model_apps)} apps")
            for app in model_apps[:3]:  # Show first 3 apps
                print(f"    * app{app['app_number']} ({app['app_type']}) [{app['source']}]")
        
        # Test 3: Test model-specific apps
        if models:
            test_model = models[0]['slug']
            print(f"\n3. Testing get_available_apps('{test_model}')...")
            model_apps = config_service.get_available_apps(test_model)
            print(f"Found {len(model_apps)} apps for {test_model}")
            
            for app in model_apps[:5]:  # Show first 5
                path = config_service.get_app_directory_path(app['model_slug'], app['app_number'])
                print(f"  - app{app['app_number']}: {app['app_type']} - {path}")
        
        # Test 4: Sync database from misc folder
        print("\n4. Testing sync_database_from_misc_folder()...")
        try:
            synced = config_service.sync_database_from_misc_folder()
            print(f"Synced {synced['models']} models and {synced['apps']} apps")
        except Exception as e:
            print(f"Sync failed: {e}")
        
        # Test 5: Get scannable targets
        print("\n5. Testing get_scannable_targets()...")
        targets = config_service.get_scannable_targets()
        print(f"Found scannable targets for {len(targets)} models")
        
        total_targets = sum(len(model_targets) for model_targets in targets.values())
        print(f"Total scannable targets: {total_targets}")
        
        # Show sample targets
        for model, model_targets in list(targets.items())[:2]:  # Show first 2 models
            print(f"  - {model}: {len(model_targets)} targets")
            for target in model_targets[:3]:  # Show first 3 targets
                frameworks = []
                if target['backend_framework']:
                    frameworks.append(f"BE:{target['backend_framework']}")
                if target['frontend_framework']:
                    frameworks.append(f"FE:{target['frontend_framework']}")
                fw_str = " (" + ", ".join(frameworks) + ")" if frameworks else ""
                print(f"    * app{target['app_number']}: {target['app_type']}{fw_str}")
        
        # Test 6: Generate analysis plan
        print("\n6. Testing generate_analysis_plan()...")
        if models:
            test_model = models[0]['slug']
            plan = config_service.generate_analysis_plan(model_slug=test_model)
            
            print(f"Analysis plan for {test_model}:")
            print(f"  - Target count: {plan['target_count']}")
            print(f"  - Estimated duration: {plan['estimated_duration']} seconds")
            print(f"  - Analysis types: {', '.join(plan['analysis_types'])}")
            print(f"  - Warnings: {len(plan['warnings'])}")
            
            if plan['warnings']:
                for warning in plan['warnings'][:3]:  # Show first 3 warnings
                    print(f"    ! {warning}")
        
        # Test 7: Database stats
        print("\n7. Database statistics...")
        db_models = ModelCapability.query.count()
        db_apps = GeneratedApplication.query.count()
        print(f"  - Models in database: {db_models}")
        print(f"  - Apps in database: {db_apps}")
        
        # Test 8: Validation
        print("\n8. Testing validation...")
        if models and apps:
            test_app = apps[0]
            is_valid = config_service.validate_model_app_combination(
                test_app['model_slug'], 
                test_app['app_number']
            )
            print(f"  - {test_app['model_slug']}/app{test_app['app_number']}: {'Valid' if is_valid else 'Invalid'}")
            
            # Test invalid combination
            is_invalid = config_service.validate_model_app_combination("nonexistent_model", 999)
            print(f"  - nonexistent_model/app999: {'Valid' if is_invalid else 'Invalid (expected)'}")
        
        print("\n" + "=" * 50)
        print("Analyzer Configuration Service Test Complete!")


if __name__ == "__main__":
    test_analyzer_config_service()
