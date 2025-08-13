"""
Error Handlers
=============

Global error handlers for the application.
"""

from flask import render_template


def register_error_handlers(app):
    """Register error handlers with the Flask app."""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template(
            'single_page.html',
            page_title='Not Found',
            main_partial='partials/common/error.html',
            error="Page not found"
        ), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template(
            'single_page.html',
            page_title='Server Error',
            main_partial='partials/common/error.html',
            error="Internal server error"
        ), 500
    
    @app.errorhandler(503)
    def service_unavailable_error(error):
        return render_template(
            'single_page.html',
            page_title='Service Unavailable',
            main_partial='partials/common/error.html',
            error="Service temporarily unavailable"
        ), 503
