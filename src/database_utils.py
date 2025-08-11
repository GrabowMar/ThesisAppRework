"""
Database Management Utilities
=============================

Provides proper database session management, context managers, and error handling
to prevent connection leaks and improve database reliability.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Any, Optional
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DatabaseError

# Initialize logger
logger = logging.getLogger(__name__)

try:
    from extensions import db
except ImportError:
    try:
        from .extensions import db
    except ImportError:
        db = None
        logger.warning("Database not available for import")

class DatabaseManager:
    """Centralized database management with proper session handling."""
    
    @staticmethod
    @contextmanager
    def get_session() -> Generator[Any, None, None]:
        """
        Context manager for safe database sessions.
        
        Ensures proper session cleanup and error handling.
        """
        if not db:
            raise RuntimeError("Database not initialized")
        
        session = db.session
        try:
            yield session
            session.commit()
            logger.debug("Database session committed successfully")
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error: {e}")
            raise DatabaseError(f"Data integrity constraint violated: {str(e)}")
        except SQLAlchemyError as e:
            session.rollback() 
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database operation failed: {str(e)}")
        except Exception as e:
            session.rollback()
            logger.error(f"Unexpected error in database session: {e}")
            raise
        finally:
            session.close()
            logger.debug("Database session closed")
    
    @staticmethod
    def safe_execute(operation_func, *args, **kwargs) -> Optional[Any]:
        """
        Safely execute a database operation with proper error handling.
        
        Args:
            operation_func: Function that performs database operations
            *args, **kwargs: Arguments to pass to the operation function
            
        Returns:
            Result of the operation or None if failed
        """
        try:
            with DatabaseManager.get_session() as session:
                return operation_func(session, *args, **kwargs)
        except DatabaseError as e:
            logger.error(f"Database operation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in database operation: {e}")
            return None
    
    @staticmethod
    def safe_query(model_class, **filters) -> list:
        """
        Safely query the database with error handling.
        
        Args:
            model_class: SQLAlchemy model class
            **filters: Filter criteria
            
        Returns:
            List of results or empty list if failed
        """
        def query_operation(session, model_class, **filters):
            return session.query(model_class).filter_by(**filters).all()
        
        result = DatabaseManager.safe_execute(query_operation, model_class, **filters)
        return result if result is not None else []
    
    @staticmethod
    def safe_get(model_class, record_id: Any) -> Optional[Any]:
        """
        Safely get a single record by ID.
        
        Args:
            model_class: SQLAlchemy model class
            record_id: Primary key value
            
        Returns:
            Model instance or None if not found/failed
        """
        def get_operation(session, model_class, record_id):
            return session.query(model_class).get(record_id)
        
        return DatabaseManager.safe_execute(get_operation, model_class, record_id)
    
    @staticmethod
    def safe_create(model_instance) -> bool:
        """
        Safely create a new record.
        
        Args:
            model_instance: SQLAlchemy model instance to create
            
        Returns:
            True if successful, False otherwise
        """
        def create_operation(session, model_instance):
            session.add(model_instance)
            session.flush()  # Ensure the instance gets an ID
            return model_instance
        
        result = DatabaseManager.safe_execute(create_operation, model_instance)
        return result is not None
    
    @staticmethod
    def safe_update(model_instance, **updates) -> bool:
        """
        Safely update a record.
        
        Args:
            model_instance: SQLAlchemy model instance to update
            **updates: Fields to update
            
        Returns:
            True if successful, False otherwise
        """
        def update_operation(session, model_instance, **updates):
            for key, value in updates.items():
                if hasattr(model_instance, key):
                    setattr(model_instance, key, value)
            session.merge(model_instance)
            return model_instance
        
        result = DatabaseManager.safe_execute(update_operation, model_instance, **updates)
        return result is not None
    
    @staticmethod
    def safe_delete(model_instance) -> bool:
        """
        Safely delete a record.
        
        Args:
            model_instance: SQLAlchemy model instance to delete
            
        Returns:
            True if successful, False otherwise
        """
        def delete_operation(session, model_instance):
            session.delete(model_instance)
            return True
        
        result = DatabaseManager.safe_execute(delete_operation, model_instance)
        return result is not None

# Convenience functions for backward compatibility
get_session = DatabaseManager.get_session
safe_execute = DatabaseManager.safe_execute
safe_query = DatabaseManager.safe_query
safe_get = DatabaseManager.safe_get
safe_create = DatabaseManager.safe_create
safe_update = DatabaseManager.safe_update
safe_delete = DatabaseManager.safe_delete

# Database health check
def check_database_health() -> dict:
    """
    Check database connectivity and health.
    
    Returns:
        Dictionary with health status information
    """
    status = {
        'connected': False,
        'error': None,
        'details': {}
    }
    
    try:
        if not db:
            status['error'] = 'Database not initialized'
            return status
        
        # Test basic connectivity
        with DatabaseManager.get_session() as session:
            # Simple query to test connection
            result = session.execute('SELECT 1').scalar()
            if result == 1:
                status['connected'] = True
                status['details']['test_query'] = 'passed'
            else:
                status['error'] = 'Test query failed'
                
    except Exception as e:
        status['error'] = f'Database health check failed: {str(e)}'
        logger.error(f"Database health check error: {e}")
    
    return status

# Migration helpers
def ensure_tables_exist():
    """Ensure all database tables exist."""
    try:
        if db:
            db.create_all()
            logger.info("Database tables verified/created")
            return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False