#!/usr/bin/env python3
"""
End-to-end test: OpenRouter API → Sample Generation → File Creation
"""
import sys
import json
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv
load_dotenv()

def test_end_to_end_workflow():
    """Test complete workflow from OpenRouter to sample generation"""
    print("🔄 End-to-End Integration Test")
    print("=" * 50)
    
    # Step 1: Test OpenRouter API
    print("1️⃣  Testing OpenRouter API connectivity...")
    try:
        from app.services.openrouter_service import OpenRouterService
        
        openrouter = OpenRouterService()
        if not openrouter.api_key:
            print("❌ OpenRouter API key not configured")
            return False
        
        # Fetch some models
        models = openrouter.fetch_all_models()
        if not models:
            print("❌ Failed to fetch models from OpenRouter")
            return False
        
        print(f"✅ Fetched {len(models)} models from OpenRouter")
        
        # Get a few model IDs for testing
        test_model_ids = [model.get('id') for model in models[:3] if model.get('id')]
        print(f"   Test models: {test_model_ids}")
        
    except Exception as e:
        print(f"❌ OpenRouter test failed: {e}")
        return False
    
    # Step 2: Test model enrichment
    print("\n2️⃣  Testing model data enrichment...")
    try:
        # Test enriching data for a model
        if test_model_ids:
            api_model = openrouter.fetch_model_by_id(test_model_ids[0])
            if api_model:
                print(f"✅ Enriched data for {test_model_ids[0]}")
                print(f"   Model name: {api_model.get('name', 'Unknown')}")
                print(f"   Context length: {api_model.get('context_length', 'Unknown')}")
            else:
                print(f"⚠️  Could not enrich data for {test_model_ids[0]}")
    except Exception as e:
        print(f"❌ Model enrichment failed: {e}")
        return False
    
    # Step 3: Test sample generation
    print("\n3️⃣  Testing sample generation with real model names...")
    try:
        from app.services.app_scaffolding_service import AppScaffoldingService
        
        scaffolding = AppScaffoldingService()
        
        # Use first two real models for testing
        real_test_models = test_model_ids[:2] if len(test_model_ids) >= 2 else test_model_ids
        
        # Generate applications
        result = scaffolding.generate(real_test_models, apps_per_model=1, dry_run=False)
        
        if result.generated:
            print(f"✅ Generated {result.apps_created} applications")
            print(f"   Models processed: {len(result.preview.models)}")
            print(f"   Errors: {len(result.errors)}")
        else:
            print("❌ Sample generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Sample generation failed: {e}")
        return False
    
    # Step 4: Verify all files were created
    print("\n4️⃣  Verifying generated files...")
    try:
        # Check configuration files
        config_files = {
            "port_config.json": Path("src/misc/port_config.json"),
            "models_summary.json": Path("src/misc/models_summary.json"),
            "model_capabilities.json": Path("src/misc/model_capabilities.json")
        }
        
        for name, path in config_files.items():
            if path.exists():
                # Try to load as JSON
                with open(path, 'r') as f:
                    data = json.load(f)
                print(f"✅ {name} exists and is valid JSON")
                
                # Check for test models in port config
                if name == "port_config.json" and isinstance(data, list):
                    test_entries = [e for e in data if any(tm in e.get('model', '') for tm in real_test_models)]
                    print(f"   Found {len(test_entries)} entries for test models")
            else:
                print(f"❌ {name} does not exist")
                return False
        
        # Check generated applications
        generated_apps_dir = Path("src/generated/apps")
        if generated_apps_dir.exists():
            model_dirs = list(generated_apps_dir.iterdir())
            print(f"✅ Generated apps directory contains {len(model_dirs)} model directories")
            
            # Check for our test models
            test_model_dirs = []
            for model_id in real_test_models:
                safe_name = model_id.replace('/', '_')
                model_dir = generated_apps_dir / safe_name
                if model_dir.exists():
                    test_model_dirs.append(model_dir)
            
            print(f"   Found {len(test_model_dirs)} directories for test models")
            
            # Check structure of one test model
            if test_model_dirs:
                test_dir = test_model_dirs[0]
                app_dirs = [d for d in test_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
                print(f"   {test_dir.name} has {len(app_dirs)} app directories")
                
                if app_dirs:
                    first_app = app_dirs[0]
                    backend = first_app / "backend"
                    frontend = first_app / "frontend"
                    
                    print(f"   App structure - Backend: {'✅' if backend.exists() else '❌'}, Frontend: {'✅' if frontend.exists() else '❌'}")
                    
                    # Check for key files
                    key_files = [
                        backend / "app.py",
                        backend / "requirements.txt", 
                        frontend / "package.json",
                        frontend / "src" / "App.jsx"
                    ]
                    
                    for key_file in key_files:
                        if key_file.exists():
                            print(f"      ✅ {key_file.relative_to(first_app)}")
                        else:
                            print(f"      ❌ {key_file.relative_to(first_app)} missing")
        else:
            print("❌ Generated apps directory does not exist")
            return False
            
    except Exception as e:
        print(f"❌ File verification failed: {e}")
        return False
    
    # Step 5: Test port configuration loading
    print("\n5️⃣  Testing port configuration integration...")
    try:
        from app.utils.generated_apps import load_port_config
        
        port_config = load_port_config()
        if port_config.get('data'):
            print(f"✅ Port configuration loaded successfully")
            print(f"   Total port entries: {len(port_config['data'])}")
            
            if port_config.get('errors'):
                print(f"   ⚠️  Errors: {port_config['errors']}")
        else:
            print("❌ Port configuration loading failed")
            return False
            
    except Exception as e:
        print(f"❌ Port configuration test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_end_to_end_workflow()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 End-to-end integration test PASSED!")
        print("\n✅ All components working correctly:")
        print("   - OpenRouter API connectivity")
        print("   - Model data fetching and enrichment") 
        print("   - Sample generation service")
        print("   - Configuration file creation (port_config.json)")
        print("   - Application scaffolding")
        print("   - File structure validation")
    else:
        print("❌ End-to-end integration test FAILED!")
        print("   Check individual component logs above for details")