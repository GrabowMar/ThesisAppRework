"""
Flask Routes Package
===================

This package contains the refactored route modules that were previously
in the large web_routes.py file. The routes are now organized by functionality:

- main_routes.py: Dashboard and main application routes
- api_routes.py: RESTful API endpoints  
- docker_routes.py: Docker container management routes
- testing_routes.py: Security testing and analysis routes
- blueprint_registry.py: Blueprint registration and configuration

This refactoring maintains full frontend compatibility while improving
code organization and maintainability.
"""

# Re-export the main registration function for backward compatibility
from .blueprint_registry import register_blueprints

__all__ = ['register_blueprints']