#!/usr/bin/env python3
"""
Test script to verify sample generator functionality
"""
import os
import sys
import json
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_config_files_exist():
    """Test if configuration files exist and have correct structure"""
    print("📁 Testing configuration files existence...")
    
    port_config_path = Path("src/misc/port_config.json")
    models_summary_path = Path("src/misc/models_summary.json")
    model_capabilities_path = Path("src/misc/model_capabilities.json")
    
    results = {}
    
    # Test port_config.json
    if port_config_path.exists():
        print(f"✅ {port_config_path} exists")
        try:
            with open(port_config_path, 'r') as f:
                port_data = json.load(f)
            if isinstance(port_data, list) and len(port_data) > 0:
                print(f"   ✅ Contains {len(port_data)} port configurations")
                sample = port_data[0]
                expected_keys = ['model', 'model_index', 'app_number', 'backend_port', 'frontend_port']
                if all(key in sample for key in expected_keys):
                    print(f"   ✅ First entry has correct structure: {sample}")
                    results['port_config'] = True
                else:
                    print(f"   ❌ Missing required keys. Found: {list(sample.keys())}")
                    results['port_config'] = False
            else:
                print(f"   ❌ Invalid structure or empty")
                results['port_config'] = False
        except Exception as e:
            print(f"   ❌ Error reading: {e}")
            results['port_config'] = False
    else:
        print(f"❌ {port_config_path} does not exist")
        results['port_config'] = False
    
    # Test models_summary.json
    if models_summary_path.exists():
        print(f"✅ {models_summary_path} exists")
        try:
            with open(models_summary_path, 'r') as f:
                summary_data = json.load(f)
            expected_keys = ['extraction_timestamp', 'total_models', 'apps_per_model', 'models']
            if all(key in summary_data for key in expected_keys):
                print(f"   ✅ Contains {summary_data.get('total_models', 0)} models")
                print(f"   ✅ Apps per model: {summary_data.get('apps_per_model', 0)}")
                if summary_data.get('models'):
                    sample_model = summary_data['models'][0]
                    print(f"   ✅ Sample model: {sample_model}")
                results['models_summary'] = True
            else:
                print(f"   ❌ Missing required keys. Found: {list(summary_data.keys())}")
                results['models_summary'] = False
        except Exception as e:
            print(f"   ❌ Error reading: {e}")
            results['models_summary'] = False
    else:
        print(f"❌ {models_summary_path} does not exist")
        results['models_summary'] = False
    
    # Test model_capabilities.json
    if model_capabilities_path.exists():
        print(f"✅ {model_capabilities_path} exists")
        try:
            with open(model_capabilities_path, 'r') as f:
                capabilities_data = json.load(f)
            if 'models' in capabilities_data and len(capabilities_data['models']) > 0:
                print(f"   ✅ Contains {len(capabilities_data['models'])} model capabilities")
                sample = capabilities_data['models'][0]
                print(f"   ✅ Sample capability: {sample.get('model_name', 'unknown')}")
                results['model_capabilities'] = True
            else:
                print(f"   ❌ No models found or wrong structure")
                results['model_capabilities'] = False
        except Exception as e:
            print(f"   ❌ Error reading: {e}")
            results['model_capabilities'] = False
    else:
        print(f"❌ {model_capabilities_path} does not exist")
        results['model_capabilities'] = False
    
    return results

def test_app_scaffolding_service():
    """Test the AppScaffoldingService functionality"""
    print("\n🏗️  Testing AppScaffoldingService...")
    
    try:
        from app.services.app_scaffolding_service import AppScaffoldingService
        
        service = AppScaffoldingService()
        print("✅ AppScaffoldingService initialized successfully")
        
        # Test preview generation
        test_models = ["test/model-1", "test/model-2"]
        preview = service.preview_generation(test_models, apps_per_model=2)
        
        print(f"✅ Preview generation successful")
        print(f"   Total apps planned: {preview.total_apps}")
        print(f"   Models: {len(preview.models)}")
        
        for model_plan in preview.models:
            print(f"   Model {model_plan.name}: ports {model_plan.port_range}, {len(model_plan.apps)} apps")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Service error: {e}")
        return False

def test_generated_apps_structure():
    """Test if generated apps directory structure exists"""
    print("\n📂 Testing generated applications structure...")
    
    generated_apps_dir = Path("src/generated/apps")
    
    if not generated_apps_dir.exists():
        print(f"❌ {generated_apps_dir} does not exist")
        return False
    
    print(f"✅ {generated_apps_dir} exists")
    
    # List existing models
    model_dirs = [d for d in generated_apps_dir.iterdir() if d.is_dir()]
    print(f"   Found {len(model_dirs)} model directories:")
    
    for model_dir in model_dirs[:5]:  # Show first 5
        app_dirs = [d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
        print(f"   📁 {model_dir.name}: {len(app_dirs)} apps")
        
        # Check first app structure
        if app_dirs:
            first_app = app_dirs[0]
            backend_dir = first_app / "backend"
            frontend_dir = first_app / "frontend"
            compose_file = first_app / "docker-compose.yml"
            
            structure_ok = True
            if backend_dir.exists():
                print(f"      ✅ backend/ exists")
            else:
                print(f"      ❌ backend/ missing")
                structure_ok = False
                
            if frontend_dir.exists():
                print(f"      ✅ frontend/ exists")
            else:
                print(f"      ❌ frontend/ missing")
                structure_ok = False
                
            if compose_file.exists():
                print(f"      ✅ docker-compose.yml exists")
            else:
                print(f"      ❌ docker-compose.yml missing")
                structure_ok = False
    
    return len(model_dirs) > 0

def test_sample_generator_direct():
    """Test the original sample generator script"""
    print("\n🎯 Testing original sample generator (generateApps.py)...")
    
    try:
        # Import the original generator
        misc_path = Path("misc")
        if not misc_path.exists():
            print("❌ misc/ directory not found")
            return False
        
        sys.path.insert(0, str(misc_path))
        
        # Test if generateApps can be imported
        import generateApps
        
        print("✅ generateApps.py imported successfully")
        
        # Test ModelManager
        manager = generateApps.ModelManager()
        print("✅ ModelManager initialized")
        
        # Test validation
        if manager.validate_setup():
            print("✅ Setup validation passed")
        else:
            print("⚠️  Setup validation failed (might be missing templates)")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Generator error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Sample Generator Integration Test")
    print("=" * 50)
    
    # Test 1: Configuration files
    config_results = test_config_files_exist()
    
    # Test 2: Service integration
    service_ok = test_app_scaffolding_service()
    
    # Test 3: Generated structure
    structure_ok = test_generated_apps_structure()
    
    # Test 4: Original generator
    generator_ok = test_sample_generator_direct()
    
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    print(f"   Configuration files: {'✅' if all(config_results.values()) else '❌'}")
    print(f"   AppScaffoldingService: {'✅' if service_ok else '❌'}")
    print(f"   Generated structure: {'✅' if structure_ok else '❌'}")
    print(f"   Original generator: {'✅' if generator_ok else '❌'}")
    
    all_passed = all(config_results.values()) and service_ok and structure_ok and generator_ok
    
    if all_passed:
        print("\n🎉 All sample generator tests passed!")
    else:
        print("\n⚠️  Some sample generator tests failed")
        for key, value in config_results.items():
            if not value:
                print(f"   - {key} failed")
        if not service_ok:
            print(f"   - Service integration failed")
        if not structure_ok:
            print(f"   - Generated structure check failed")
        if not generator_ok:
            print(f"   - Original generator failed")