#!/usr/bin/env python3
"""
Apply SARIF Fields Migration
============================

Adds SARIF 2.1.0 support columns to AnalysisResult table.
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Apply SARIF migration to database."""
    try:
        logger.info("Starting SARIF migration...")
        
        # Add src directory to path
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        
        # Import Flask app components
        from app.factory import create_app
        from app.extensions import db
        
        # Create Flask app
        logger.info("Creating Flask application...")
        app = create_app()
        
        with app.app_context():
            logger.info("Database URI: %s", app.config['SQLALCHEMY_DATABASE_URI'])
            
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('analysis_results')]
            
            if 'sarif_level' in columns:
                logger.info("✅ SARIF columns already exist - no migration needed")
                return
            
            logger.info("Adding SARIF columns to analysis_results table...")
            
            # For SQLite, use batch operations
            with db.engine.begin() as connection:
                if db.engine.name == 'sqlite':
                    # SQLite doesn't support ALTER TABLE ADD COLUMN with batching well
                    # Use direct ALTER statements
                    connection.execute(db.text(
                        "ALTER TABLE analysis_results ADD COLUMN sarif_level VARCHAR(20)"
                    ))
                    connection.execute(db.text(
                        "ALTER TABLE analysis_results ADD COLUMN sarif_rule_id VARCHAR(100)"
                    ))
                    connection.execute(db.text(
                        "ALTER TABLE analysis_results ADD COLUMN sarif_metadata TEXT"
                    ))
                else:
                    # PostgreSQL/MySQL support multiple columns in one statement
                    connection.execute(db.text(
                        """
                        ALTER TABLE analysis_results 
                        ADD COLUMN sarif_level VARCHAR(20),
                        ADD COLUMN sarif_rule_id VARCHAR(100),
                        ADD COLUMN sarif_metadata TEXT
                        """
                    ))
            
            logger.info("✅ SARIF migration completed successfully!")
            logger.info("   Added columns: sarif_level, sarif_rule_id, sarif_metadata")
            
    except Exception as e:
        logger.error("❌ SARIF migration failed: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
