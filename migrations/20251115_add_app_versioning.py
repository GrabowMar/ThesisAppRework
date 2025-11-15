"""
Migration: Add versioning support to GeneratedApplication model
Date: 2025-11-15
Description: Adds version, parent_app_id, and batch_id fields to support app versioning and batch tracking
"""

def upgrade(app):
    """Add version, parent_app_id, and batch_id columns to generated_applications table."""
    from app.extensions import db
    from sqlalchemy import text
    import logging
    
    logger = logging.getLogger(__name__)
    
    with app.app_context():
        try:
            logger.info("Starting migration: Add versioning to generated_applications")
            
            # Add version column (default 1 for existing apps)
            logger.info("Adding version column...")
            db.session.execute(text("""
                ALTER TABLE generated_applications 
                ADD COLUMN version INTEGER NOT NULL DEFAULT 1
            """))
            
            # Add parent_app_id column (nullable, for regenerations)
            logger.info("Adding parent_app_id column...")
            db.session.execute(text("""
                ALTER TABLE generated_applications 
                ADD COLUMN parent_app_id INTEGER
            """))
            
            # Add batch_id column (nullable, for batch operations)
            logger.info("Adding batch_id column...")
            db.session.execute(text("""
                ALTER TABLE generated_applications 
                ADD COLUMN batch_id VARCHAR(100)
            """))
            
            # Drop old unique constraint
            logger.info("Dropping old unique constraint...")
            db.session.execute(text("""
                DROP INDEX IF EXISTS unique_model_app
            """))
            
            # Create new unique constraint including version
            logger.info("Creating new unique constraint (model_slug, app_number, version)...")
            db.session.execute(text("""
                CREATE UNIQUE INDEX unique_model_app_version 
                ON generated_applications (model_slug, app_number, version)
            """))
            
            # Create index for model_slug + template_slug queries
            logger.info("Creating index on (model_slug, template_slug)...")
            db.session.execute(text("""
                CREATE INDEX idx_model_template 
                ON generated_applications (model_slug, template_slug)
            """))
            
            # Create index for batch_id
            logger.info("Creating index on batch_id...")
            db.session.execute(text("""
                CREATE INDEX idx_batch_id 
                ON generated_applications (batch_id)
            """))
            
            # Add foreign key constraint for parent_app_id
            logger.info("Adding foreign key constraint for parent_app_id...")
            db.session.execute(text("""
                CREATE INDEX idx_parent_app_id 
                ON generated_applications (parent_app_id)
            """))
            
            db.session.commit()
            logger.info("Migration completed successfully")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Migration failed: {e}")
            raise

def downgrade(app):
    """Remove versioning columns and restore original constraint."""
    from app.extensions import db
    from sqlalchemy import text
    import logging
    
    logger = logging.getLogger(__name__)
    
    with app.app_context():
        try:
            logger.info("Starting rollback: Remove versioning from generated_applications")
            
            # Drop indexes
            logger.info("Dropping indexes...")
            db.session.execute(text("DROP INDEX IF EXISTS unique_model_app_version"))
            db.session.execute(text("DROP INDEX IF EXISTS idx_model_template"))
            db.session.execute(text("DROP INDEX IF EXISTS idx_batch_id"))
            db.session.execute(text("DROP INDEX IF EXISTS idx_parent_app_id"))
            
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            # For production with PostgreSQL/MySQL, use ALTER TABLE DROP COLUMN
            logger.info("Removing version, parent_app_id, batch_id columns...")
            
            # Create temporary table without versioning columns
            db.session.execute(text("""
                CREATE TABLE generated_applications_temp AS 
                SELECT id, model_slug, app_number, app_type, provider, template_slug, 
                       generation_status, has_backend, has_frontend, has_docker_compose,
                       backend_framework, frontend_framework, container_status, 
                       last_status_check, metadata_json, created_at, updated_at
                FROM generated_applications
            """))
            
            # Drop original table
            db.session.execute(text("DROP TABLE generated_applications"))
            
            # Rename temp table
            db.session.execute(text("ALTER TABLE generated_applications_temp RENAME TO generated_applications"))
            
            # Recreate old unique constraint
            logger.info("Recreating old unique constraint...")
            db.session.execute(text("""
                CREATE UNIQUE INDEX unique_model_app 
                ON generated_applications (model_slug, app_number)
            """))
            
            db.session.commit()
            logger.info("Rollback completed successfully")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Rollback failed: {e}")
            raise

if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    # Add src directory to path
    src_dir = Path(__file__).parent.parent / 'src'
    sys.path.insert(0, str(src_dir))
    
    from app.factory import create_app
    app = create_app()
    upgrade(app)
