"""
Flask Application Package
========================

This module contains the application package for the Thesis App.
Uses the factory pattern implemented in factory.py for proper application creation.
"""

# For backward compatibility, expose the factory function
from app.factory import create_app

__all__ = ['create_app']
