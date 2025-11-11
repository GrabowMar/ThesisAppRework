#!/usr/bin/env python3
"""
Create Admin User Script
=========================

Creates the database and a default admin user.
Used during wipeout operations to reset the system.
"""

import sys
import logging
from pathlib import Path

# Add src directory to Python path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Default admin credentials
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "ia5aeQE2wR87J8w"
DEFAULT_ADMIN_EMAIL = "admin@thesis.local"


def main():
    """Initialize database and create admin user."""
    try:
        logger.info("Starting database and admin user creation...")
        
        # Import Flask app components
        from app.factory import create_app
        from app.extensions import init_db
        from app.models import User
        from app.services.data_initialization import DataInitializationService
        
        # Create Flask app
        logger.info("Creating Flask application...")
        app = create_app()
        
        with app.app_context():
            logger.info("Database URI: %s", app.config['SQLALCHEMY_DATABASE_URI'])
            
            # Initialize database tables
            logger.info("Creating database tables...")
            init_db()
            logger.info("✅ Database tables created successfully!")
            
            # Check if admin user already exists
            admin_user = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
            
            if admin_user:
                logger.info("Admin user already exists, updating credentials...")
                admin_user.set_password(DEFAULT_ADMIN_PASSWORD)
                admin_user.email = DEFAULT_ADMIN_EMAIL
                admin_user.is_admin = True
                admin_user.is_active = True
            else:
                logger.info("Creating admin user...")
                admin_user = User(
                    username=DEFAULT_ADMIN_USERNAME,
                    email=DEFAULT_ADMIN_EMAIL,
                    full_name="System Administrator"
                )
                admin_user.set_password(DEFAULT_ADMIN_PASSWORD)
                admin_user.is_admin = True
                admin_user.is_active = True
                from app.extensions import db
                db.session.add(admin_user)
            
            # Commit the admin user
            from app.extensions import db
            db.session.commit()
            logger.info("✅ Admin user created/updated successfully!")
            logger.info("   Username: %s", DEFAULT_ADMIN_USERNAME)
            logger.info("   Email: %s", DEFAULT_ADMIN_EMAIL)
            
            # Initialize data from JSON files
            logger.info("Loading data from JSON files...")
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
                # Don't fail the script if data loading has issues
            
            logger.info("✅ System initialization complete!")
            
    except Exception as e:
        logger.error("❌ Initialization failed: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
