#!/usr/bin/env python3
"""
Database Initialization Script
==============================

This script initializes the database and loads initial data for the Thesis App.

The script performs the following operations:
1. Creates all database tables based on SQLAlchemy models
2. Loads model capabilities from JSON files
3. Loads application templates and configurations
4. Loads port configurations for Docker containers
5. Verifies data integrity and reports statistics

Usage:
    python src/init_db.py

Environment Variables:
    DATABASE_URL: Database connection string (defaults to SQLite in data/ directory)
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)

The script will exit with code 1 if any critical errors occur during initialization.
"""

import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Initialize database and load data.
    
    This function performs the complete database initialization process:
    - Creates Flask application context
    - Initializes database tables
    - Loads all data from JSON files
    - Performs verification and cleanup
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info("Starting database initialization...")
        
        # Import Flask app components
        from app.factory import create_app
        from app.extensions import init_db
        from app.services.data_initialization import DataInitializationService
        from app.models import ModelCapability
        
        # Create Flask app
        logger.info("Creating Flask application...")
        app = create_app()
        
        with app.app_context():
            logger.info("Database URI: %s", app.config['SQLALCHEMY_DATABASE_URI'])
            
            # Initialize database tables
            logger.info("Creating database tables...")
            init_db()
            logger.info("Database tables created successfully!")
            
            # Initialize all data from JSON files
            logger.info("Loading all data from JSON files...")
            service = DataInitializationService()
            result = service.initialize_all_data()
            
            if result['success']:
                logger.info("✅ Data loading completed successfully!")
                total_models = result['models_loaded'] + result.get('openrouter_models_loaded', 0)
                logger.info("   Models loaded: %d (from file: %d, from OpenRouter: %d)", 
                           total_models, result['models_loaded'], result.get('openrouter_models_loaded', 0))
                logger.info("   Applications loaded: %d", result['applications_loaded'])
                logger.info("   Ports loaded: %d", result['ports_loaded'])
                if result['errors']:
                    logger.warning("   Warnings: %s", result['errors'])
            else:
                logger.error("❌ Data loading had errors: %s", result['errors'])
                sys.exit(1)
            
            # Verify the data
            total_models = ModelCapability.query.count()
            logger.info("✅ Database initialization complete! Total models: %d", total_models)
            
    except Exception as e:
        logger.error("❌ Database initialization failed: %s", e)
        sys.exit(1)

if __name__ == '__main__':
    main()
