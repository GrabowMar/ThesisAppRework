#!/usr/bin/env python3
"""
Test small sample generation to verify all files are created correctly
"""
import sys
import json
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv
load_dotenv()

def test_small_generation():
    """Test generating a small set of applications"""
    print("🧪 Testing small sample generation...")
    
    try:
        from app.services.app_scaffolding_service import AppScaffoldingService
        
        service = AppScaffoldingService()
        
        # Generate for 2 test models with 2 apps each
        test_models = ["test/sample-model-1", "test/sample-model-2"]
        
        print(f"🚀 Generating applications for {len(test_models)} models...")
        
        # First do a dry run
        dry_result = service.generate(test_models, dry_run=True, apps_per_model=2)
        print(f"✅ Dry run successful - would create {dry_result.preview.total_apps} apps")
        
        # Now do actual generation
        result = service.generate(test_models, dry_run=False, apps_per_model=2)
        
        if result.generated:
            print(f"✅ Generation successful!")
            print(f"   Apps created: {result.apps_created}")
            print(f"   Output paths: {len(result.output_paths)}")
            print(f"   Errors: {len(result.errors)}")
            
            if result.errors:
                for error in result.errors:
                    print(f"   ⚠️  {error}")
            
            # Check what was created
            for path in result.output_paths:
                if path.exists():
                    apps = [d for d in path.iterdir() if d.is_dir() and d.name.startswith('app')]
                    print(f"   📁 {path.name}: {len(apps)} apps created")
                    
                    # Check first app structure
                    if apps:
                        first_app = apps[0]
                        backend = first_app / "backend"
                        frontend = first_app / "frontend"
                        compose = first_app / "docker-compose.yml"
                        
                        print(f"      Backend: {'✅' if backend.exists() else '❌'}")
                        print(f"      Frontend: {'✅' if frontend.exists() else '❌'}")
                        print(f"      Docker Compose: {'✅' if compose.exists() else '❌'}")
            
            return True
        else:
            print(f"❌ Generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Generation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_updated_config_files():
    """Check if config files were updated with new models"""
    print("\n📁 Checking updated configuration files...")
    
    # Check port_config.json for test models
    port_config_path = Path("src/misc/port_config.json")
    if port_config_path.exists():
        with open(port_config_path, 'r') as f:
            port_data = json.load(f)
        
        test_entries = [entry for entry in port_data if 'test/' in entry.get('model', '')]
        print(f"✅ Found {len(test_entries)} test model entries in port_config.json")
        
        if test_entries:
            sample = test_entries[0]
            print(f"   Sample: {sample}")
    
    # Check that config files are still valid JSON
    config_files = [
        "src/misc/port_config.json",
        "src/misc/models_summary.json", 
        "src/misc/model_capabilities.json"
    ]
    
    for config_file in config_files:
        path = Path(config_file)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    json.load(f)
                print(f"✅ {config_file} is valid JSON")
            except json.JSONDecodeError as e:
                print(f"❌ {config_file} has JSON errors: {e}")
        else:
            print(f"❌ {config_file} does not exist")

if __name__ == "__main__":
    print("🧪 Small Sample Generation Test")
    print("=" * 40)
    
    # Test generation
    generation_ok = test_small_generation()
    
    # Check config files
    check_updated_config_files()
    
    print("\n" + "=" * 40)
    if generation_ok:
        print("🎉 Sample generation test passed!")
    else:
        print("⚠️  Sample generation test failed")