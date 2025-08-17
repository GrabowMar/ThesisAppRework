#!/usr/bin/env python3
"""
Database Initialization Script
==============================

Run this script to initialize the database and load initial data.
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
    """Initialize database and load data."""
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
            
            # Check if we already have data
            existing_models = ModelCapability.query.count()
            if existing_models > 0:
                logger.info("Database already has %d models. Skipping data load.", existing_models)
                return
            
            # Load model capabilities
            logger.info("Loading model capabilities from JSON files...")
            service = DataInitializationService()
            result = service.load_model_capabilities()
            
            logger.info("Model capabilities loaded: %s", result)
            
            # Verify the data
            total_models = ModelCapability.query.count()
            logger.info("✅ Database initialization complete! Total models: %d", total_models)
            
    except Exception as e:
        logger.error("❌ Database initialization failed: %s", e)
        sys.exit(1)

if __name__ == '__main__':
    main()
