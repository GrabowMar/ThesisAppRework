"""
Flask Extensions Configuration

This module initializes Flask extensions used throughout the application.
Extensions are created here and then initialized in the app factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

def init_extensions(app):
    """Initialize Flask extensions with the app instance."""
    db.init_app(app)
    migrate.init_app(app, db)
