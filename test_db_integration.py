#!/usr/bin/env python3
"""
Database Integration Test
========================

Tests that the application is correctly reading from database instead of JSON files.
"""

import sys
import logging
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_database_integration():
    """Test that all services are reading from database correctly."""
    
    results = {'passed': 0, 'failed': 0, 'details': []}
    
    try:
        # Import Flask app components
        from app.factory import create_app
        from app.services.service_locator import ServiceLocator
        from app.models import ModelCapability, PortConfiguration, GeneratedApplication
        
        # Create Flask app
        logger.info("Creating Flask application...")
        app = create_app()
        
        with app.app_context():
            
            # Test 1: Check database has data
            logger.info("Testing database data availability...")
            model_count = ModelCapability.query.count()
            port_count = PortConfiguration.query.count()
            app_count = GeneratedApplication.query.count()
            
            if model_count > 0:
                results['passed'] += 1
                results['details'].append(f"✅ Database contains {model_count} models")
            else:
                results['failed'] += 1
                results['details'].append("❌ Database contains no models")
            
            if port_count > 0:
                results['passed'] += 1
                results['details'].append(f"✅ Database contains {port_count} port configurations")
            else:
                results['failed'] += 1
                results['details'].append("❌ Database contains no port configurations")
            
            if app_count > 0:
                results['passed'] += 1
                results['details'].append(f"✅ Database contains {app_count} applications")
            else:
                results['failed'] += 1
                results['details'].append("❌ Database contains no applications")
            
            # Test 2: Check service locator
            logger.info("Testing service locator...")
            model_service = ServiceLocator.get_model_service()
            
            if model_service:
                results['passed'] += 1
                results['details'].append("✅ Model service accessible via service locator")
                
                # Test service methods
                try:
                    all_models = model_service.get_all_models()
                    if len(all_models) > 0:
                        results['passed'] += 1
                        results['details'].append(f"✅ Model service returns {len(all_models)} models")
                    else:
                        results['failed'] += 1
                        results['details'].append("❌ Model service returns no models")
                        
                    providers = model_service.get_providers()
                    if len(providers) > 0:
                        results['passed'] += 1
                        results['details'].append(f"✅ Model service returns {len(providers)} providers: {providers}")
                    else:
                        results['failed'] += 1
                        results['details'].append("❌ Model service returns no providers")
                        
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append(f"❌ Model service methods failed: {e}")
            else:
                results['failed'] += 1
                results['details'].append("❌ Model service not accessible via service locator")
            
            # Test 3: Test specific model lookup
            logger.info("Testing specific model operations...")
            try:
                # Try to get a specific model
                first_model = ModelCapability.query.first()
                if first_model:
                    model_by_slug = model_service.get_model_by_slug(first_model.canonical_slug)
                    if model_by_slug:
                        results['passed'] += 1
                        results['details'].append(f"✅ Successfully retrieved model: {first_model.canonical_slug}")
                    else:
                        results['failed'] += 1
                        results['details'].append(f"❌ Failed to retrieve model by slug: {first_model.canonical_slug}")
                        
                    # Test model apps
                    model_apps = model_service.get_model_apps(first_model.canonical_slug)
                    results['passed'] += 1
                    results['details'].append(f"✅ Model {first_model.canonical_slug} has {len(model_apps)} applications")
                    
                    # Test port configuration
                    if len(model_apps) > 0:
                        first_app = model_apps[0]
                        port_config = model_service.get_app_ports(first_app.model_slug, first_app.app_number)
                        if port_config:
                            results['passed'] += 1
                            results['details'].append(f"✅ Port config found: frontend={port_config.frontend_port}, backend={port_config.backend_port}")
                        else:
                            results['failed'] += 1
                            results['details'].append(f"❌ No port config found for {first_app.model_slug}/app{first_app.app_number}")
                else:
                    results['failed'] += 1
                    results['details'].append("❌ No models found in database")
                    
            except Exception as e:
                results['failed'] += 1
                results['details'].append(f"❌ Model operations failed: {e}")
            
            # Test 4: Test model summary generation 
            logger.info("Testing model summary generation...")
            try:
                model_summary = model_service.get_model_summary()
                if model_summary and 'models' in model_summary:
                    results['passed'] += 1
                    results['details'].append(f"✅ Generated model summary with {len(model_summary['models'])} models")
                else:
                    results['failed'] += 1
                    results['details'].append("❌ Failed to generate model summary")
            except Exception as e:
                results['failed'] += 1
                results['details'].append(f"❌ Model summary generation failed: {e}")
            
    except Exception as e:
        logger.error(f"Error during database integration test: {e}")
        results['failed'] += 1
        results['details'].append(f"❌ Critical error: {e}")
    
    return results

def main():
    """Main entry point."""
    
    print("🔍 Testing database integration...")
    print("=" * 80)
    
    results = test_database_integration()
    
    print("\nTEST RESULTS:")
    print("=" * 80)
    
    for detail in results['details']:
        print(detail)
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: {results['passed']} passed, {results['failed']} failed")
    
    if results['failed'] == 0:
        print("🎉 All database integration tests passed!")
        print("The application is successfully reading from the database.")
        return 0
    else:
        print(f"⚠️  {results['failed']} tests failed - check details above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
