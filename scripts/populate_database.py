#!/usr/bin/env python3
"""
Database Population Script
==========================

Populates the database with data from JSON files in misc/ directory.
Run this script to sync JSON file data into the SQLite database.
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

def populate_database():
    """Main function to populate database from JSON files."""
    
    try:
        # Import Flask app components
        from app.factory import create_app
        from app.services.model_service import ModelService
        
        # Create Flask app
        logger.info("Creating Flask application...")
        app = create_app()
        
        with app.app_context():
            logger.info("Starting database population...")
            
            # Initialize model service
            model_service = ModelService(app)
            
            # Populate database from files
            results = model_service.populate_database_from_files()
            
            logger.info("Database population completed!")
            logger.info(f"Results: {results}")
            
            # Print summary
            print("\n" + "=" * 60)
            print("DATABASE POPULATION SUMMARY")
            print("=" * 60)
            print(f"Models created/updated:      {results['models']}")
            print(f"Port configs created:        {results['ports']}")
            print(f"Applications discovered:     {results['apps']}")
            print("=" * 60)
            
            if sum(results.values()) > 0:
                print("✅ Database population successful!")
                return True
            else:
                print("ℹ️  No new data to populate (database already up to date)")
                return True
                
    except Exception as e:
        logger.error(f"Error during database population: {e}")
        print(f"\n❌ Database population failed: {e}")
        return False

def verify_population():
    """Verify that data was populated correctly."""
    
    try:
        from app.factory import create_app
        from app.models import ModelCapability, PortConfiguration, GeneratedApplication
        
        app = create_app()
        
        with app.app_context():
            # Count records
            model_count = ModelCapability.query.count()
            port_count = PortConfiguration.query.count()
            app_count = GeneratedApplication.query.count()
            
            print("\n" + "=" * 60)
            print("DATABASE VERIFICATION")
            print("=" * 60)
            print(f"Total models in database:     {model_count}")
            print(f"Total port configs:           {port_count}")
            print(f"Total applications:           {app_count}")
            
            if model_count > 0:
                # Show sample models by provider
                from sqlalchemy import func
                providers = ModelCapability.query.with_entities(
                    ModelCapability.provider, 
                    func.count(ModelCapability.id).label('count')
                ).group_by(ModelCapability.provider).all()
                
                print("\nModels by provider:")
                for provider, count in providers:
                    print(f"  {provider}: {count} models")
            
            print("=" * 60)
            return model_count > 0
            
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        print(f"\n❌ Database verification failed: {e}")
        return False

def main():
    """Main entry point."""
    
    print("🔄 Starting database population from JSON files...")
    
    # Step 1: Populate database
    success = populate_database()
    
    if not success:
        return 1
    
    # Step 2: Verify population  
    verified = verify_population()
    
    if verified:
        print("\n🎉 Database population and verification completed successfully!")
        print("\nThe application will now read data from the database instead of JSON files.")
        return 0
    else:
        print("\n⚠️  Database verification failed - check logs for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())
