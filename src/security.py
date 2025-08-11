"""
Security Infrastructure for Flask Application
=============================================

This module provides comprehensive security features including:
- CSRF protection
- Input validation and sanitization  
- Rate limiting
- Security headers
- Error handling decorators
"""

import logging
import traceback
from functools import wraps
from typing import Any, Dict, Optional, Union

from flask import Flask, request, jsonify, current_app, g
from markupsafe import escape
from marshmallow import Schema, fields, ValidationError

# Initialize logger
logger = logging.getLogger(__name__)

# ===========================
# CSRF PROTECTION
# ===========================

class CSRFProtection:
    """CSRF protection service using Flask-WTF."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self._csrf = None
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """Initialize CSRF protection with the Flask app."""
        try:
            from flask_wtf.csrf import CSRFProtect
            self._csrf = CSRFProtect(app)
            
            # Add CSRF token to template context
            @app.context_processor
            def inject_csrf_token():
                try:
                    from flask_wtf.csrf import generate_csrf
                    return dict(csrf_token=generate_csrf)
                except Exception as e:
                    logger.error(f"Failed to generate CSRF token: {e}")
                    return dict(csrf_token="")
            
            logger.info("CSRF protection initialized")
            
        except ImportError:
            logger.warning("Flask-WTF not available, CSRF protection disabled")
        except Exception as e:
            logger.error(f"Failed to initialize CSRF protection: {e}")

# ===========================
# INPUT VALIDATION
# ===========================

class InputValidator:
    """Input validation and sanitization service."""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        if not isinstance(value, str):
            return ""
        
        # Remove null bytes and trim
        sanitized = value.replace('\x00', '').strip()
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # HTML escape
        return escape(sanitized)
    
    @staticmethod
    def validate_model_slug(slug: str) -> str:
        """Validate and sanitize model slug."""
        if not slug or not isinstance(slug, str):
            raise ValidationError("Model slug is required")
        
        sanitized = InputValidator.sanitize_string(slug, 100)
        
        # Additional validation for model slugs
        if not sanitized or len(sanitized) < 1:
            raise ValidationError("Model slug cannot be empty")
        
        # Check for valid characters (alphanumeric, hyphens, underscores)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', sanitized):
            raise ValidationError("Model slug contains invalid characters")
        
        return sanitized
    
    @staticmethod
    def validate_app_number(app_num: Union[str, int]) -> int:
        """Validate app number."""
        try:
            num = int(app_num)
            if not (1 <= num <= 30):
                raise ValidationError("App number must be between 1 and 30")
            return num
        except (ValueError, TypeError):
            raise ValidationError("Invalid app number")

# Validation schemas
class ModelRequestSchema(Schema):
    """Schema for model-related requests."""
    model_slug = fields.Str(required=True, validate=lambda x: len(x) <= 100)

class AppRequestSchema(Schema):
    """Schema for app-related requests."""
    model_slug = fields.Str(required=True, validate=lambda x: len(x) <= 100)
    app_number = fields.Int(required=True, validate=lambda x: 1 <= x <= 30)

# ===========================
# RATE LIMITING
# ===========================

class RateLimiter:
    """Rate limiting service using Flask-Limiter."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self._limiter = None
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """Initialize rate limiting with the Flask app."""
        try:
            from flask_limiter import Limiter
            from flask_limiter.util import get_remote_address
            
            self._limiter = Limiter(
                app,
                key_func=get_remote_address,
                default_limits=["200 per day", "50 per hour"],
                storage_uri="memory://"  # Use in-memory storage for simplicity
            )
            
            logger.info("Rate limiting initialized")
            
        except ImportError:
            logger.warning("Flask-Limiter not available, rate limiting disabled")
        except Exception as e:
            logger.error(f"Failed to initialize rate limiting: {e}")
    
    def limit(self, limit_string: str):
        """Decorator for applying rate limits to routes."""
        if self._limiter:
            return self._limiter.limit(limit_string)
        else:
            # Return a no-op decorator if limiter is not available
            def decorator(f):
                return f
            return decorator

# ===========================
# SECURITY HEADERS
# ===========================

def add_security_headers(app: Flask) -> None:
    """Add security headers to all responses."""
    
    @app.after_request
    def security_headers(response):
        """Add security headers to responses."""
        # Basic security headers
        security_headers = {
            'X-Frame-Options': 'DENY',
            'X-Content-Type-Options': 'nosniff',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'X-Permitted-Cross-Domain-Policies': 'none'
        }
        
        # Add HSTS in production
        if not app.debug:
            security_headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'"
        )
        security_headers['Content-Security-Policy'] = csp
        
        # Apply headers
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    logger.info("Security headers middleware installed")

# ===========================
# ERROR HANDLING
# ===========================

def handle_errors(f):
    """Decorator for consistent error handling across routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return jsonify({
                'success': False,
                'error': 'Invalid input',
                'details': str(e),
                'timestamp': None
            }), 400
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Internal server error',
                'timestamp': None
            }), 500
    return decorated_function

def handle_database_errors(f):
    """Decorator for database-specific error handling."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Check if it's a database error
            if 'sqlalchemy' in str(type(e)).lower():
                logger.error(f"Database error in {f.__name__}: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': 'Database error',
                    'timestamp': None
                }), 500
            else:
                # Re-raise non-database errors
                raise
    return decorated_function

# ===========================
# SECURITY UTILITIES
# ===========================

def is_safe_url(target: str) -> bool:
    """Check if a URL is safe for redirects."""
    if not target:
        return False
    
    # Simple check for relative URLs or same-origin URLs
    return target.startswith('/') or target.startswith(request.host_url)

def log_security_event(event_type: str, details: Dict[str, Any]) -> None:
    """Log security-related events."""
    logger.warning(f"Security event: {event_type}", extra={
        'event_type': event_type,
        'details': details,
        'remote_addr': request.remote_addr if request else None,
        'user_agent': request.headers.get('User-Agent') if request else None
    })

# ===========================
# INITIALIZATION
# ===========================

def init_security(app: Flask) -> None:
    """Initialize all security features for the Flask app."""
    
    # Initialize CSRF protection
    csrf = CSRFProtection(app)
    
    # Initialize rate limiting
    rate_limiter = RateLimiter(app)
    
    # Add security headers
    add_security_headers(app)
    
    # Store security services in app config for access
    app.config['csrf_protection'] = csrf
    app.config['rate_limiter'] = rate_limiter
    
    logger.info("All security features initialized")
    
    return {
        'csrf': csrf,
        'rate_limiter': rate_limiter
    }