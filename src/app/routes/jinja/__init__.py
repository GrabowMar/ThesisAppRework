"""
Jinja Routes Package
Handles all Jinja template-based routes and functionality.
"""

from .main import main_bp
from .models import models_bp
from .analysis import analysis_bp
from .stats import stats_bp
from .reports import reports_bp
from .docs import docs_bp
from .sample_generator import sample_generator_bp

__all__ = [
    'main_bp',
    'models_bp',
    'analysis_bp',
    'stats_bp',
    'reports_bp',
    'docs_bp',
    'sample_generator_bp'
]