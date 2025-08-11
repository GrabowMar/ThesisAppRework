"""
Routes Package
=============

Modular Flask blueprints for the application.
"""

from .main import main_bp
from .models import models_bp  
from .analysis import analysis_bp
from .api import api_bp
from .batch import batch_bp
from .statistics import stats_bp
from .advanced import advanced
from .testing import testing_bp
from .errors import register_error_handlers

__all__ = [
    'main_bp',
    'models_bp', 
    'analysis_bp',
    'api_bp',
    'batch_bp',
    'stats_bp',
    'advanced',
    'testing_bp',
    'register_error_handlers'
]

def register_blueprints(app):
    """Register all blueprints with the Flask application."""
    
    # Core routes
    app.register_blueprint(main_bp)
    app.register_blueprint(models_bp, url_prefix='/models')
    app.register_blueprint(analysis_bp, url_prefix='/analysis')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Feature routes
    app.register_blueprint(batch_bp, url_prefix='/batch')
    app.register_blueprint(stats_bp, url_prefix='/statistics')
    app.register_blueprint(testing_bp, url_prefix='/testing')
    app.register_blueprint(advanced)
    
    # Register error handlers
    register_error_handlers(app)
