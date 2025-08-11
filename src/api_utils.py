"""
API Response Utilities
=====================

Standardized API response formatting for consistent client communication.
Includes error handling, status codes, and response structure.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union
from flask import jsonify, request, g

logger = logging.getLogger(__name__)

class APIResponse:
    """Standardized API response formatter."""
    
    @staticmethod
    def _get_request_context() -> Dict[str, Any]:
        """Get current request context information."""
        context = {}
        
        try:
            if request:
                context.update({
                    'method': request.method,
                    'endpoint': request.endpoint,
                    'remote_addr': request.remote_addr
                })
        except RuntimeError:
            # Outside request context
            pass
        
        try:
            if hasattr(g, 'request_id'):
                context['request_id'] = g.request_id
        except RuntimeError:
            pass
        
        return context
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", status_code: int = 200) -> tuple:
        """
        Create a successful API response.
        
        Args:
            data: Response data
            message: Success message
            status_code: HTTP status code
            
        Returns:
            Tuple of (response, status_code)
        """
        context = APIResponse._get_request_context()
        
        response_data = {
            'success': True,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
            'status_code': status_code
        }
        
        # Add request context if available
        if context:
            response_data['request_context'] = context
        
        logger.info(f"API Success Response: {message}", extra={
            'status_code': status_code,
            'endpoint': context.get('endpoint'),
            'request_id': context.get('request_id')
        })
        
        return jsonify(response_data), status_code
    
    @staticmethod
    def error(message: str, status_code: int = 400, details: Any = None, 
             error_code: str = None) -> tuple:
        """
        Create an error API response.
        
        Args:
            message: Error message
            status_code: HTTP status code
            details: Additional error details
            error_code: Application-specific error code
            
        Returns:
            Tuple of (response, status_code)
        """
        context = APIResponse._get_request_context()
        
        response_data = {
            'success': False,
            'error': message,
            'details': details,
            'error_code': error_code,
            'timestamp': datetime.utcnow().isoformat(),
            'status_code': status_code
        }
        
        # Add request context
        if context:
            response_data['request_context'] = context
        
        # Add retry information for retryable errors
        if status_code in [429, 500, 502, 503, 504]:
            response_data['retryable'] = True
            retry_delays = {429: 60, 500: 30, 502: 60, 503: 60, 504: 120}
            response_data['retry_after'] = retry_delays.get(status_code, 30)
        
        # Log error appropriately
        if status_code >= 500:
            logger.error(f"API Server Error: {message}", extra={
                'status_code': status_code,
                'endpoint': context.get('endpoint'),
                'request_id': context.get('request_id'),
                'details': details
            })
        elif status_code >= 400:
            logger.warning(f"API Client Error: {message}", extra={
                'status_code': status_code,
                'endpoint': context.get('endpoint'),
                'request_id': context.get('request_id')
            })
        
        response = jsonify(response_data)
        
        # Add retry header if applicable
        if 'retry_after' in response_data:
            response.headers['Retry-After'] = str(response_data['retry_after'])
        
        return response, status_code
    
    @staticmethod
    def validation_error(errors: Union[str, Dict, list], status_code: int = 400) -> tuple:
        """
        Create a validation error response.
        
        Args:
            errors: Validation errors (can be string, dict, or list)
            status_code: HTTP status code
            
        Returns:
            Tuple of (response, status_code)
        """
        return APIResponse.error(
            message="Validation failed",
            status_code=status_code,
            details=errors,
            error_code="VALIDATION_ERROR"
        )
    
    @staticmethod
    def not_found(resource: str = "Resource") -> tuple:
        """
        Create a 404 not found response.
        
        Args:
            resource: Name of the resource that was not found
            
        Returns:
            Tuple of (response, status_code)
        """
        return APIResponse.error(
            message=f"{resource} not found",
            status_code=404,
            error_code="NOT_FOUND"
        )
    
    @staticmethod
    def unauthorized(message: str = "Authentication required") -> tuple:
        """
        Create a 401 unauthorized response.
        
        Args:
            message: Unauthorized message
            
        Returns:
            Tuple of (response, status_code)
        """
        return APIResponse.error(
            message=message,
            status_code=401,
            error_code="UNAUTHORIZED"
        )
    
    @staticmethod
    def forbidden(message: str = "Access denied") -> tuple:
        """
        Create a 403 forbidden response.
        
        Args:
            message: Forbidden message
            
        Returns:
            Tuple of (response, status_code)
        """
        return APIResponse.error(
            message=message,
            status_code=403,
            error_code="FORBIDDEN"
        )
    
    @staticmethod
    def rate_limited(message: str = "Rate limit exceeded") -> tuple:
        """
        Create a 429 rate limited response.
        
        Args:
            message: Rate limit message
            
        Returns:
            Tuple of (response, status_code)
        """
        return APIResponse.error(
            message=message,
            status_code=429,
            error_code="RATE_LIMITED"
        )
    
    @staticmethod
    def server_error(message: str = "Internal server error") -> tuple:
        """
        Create a 500 server error response.
        
        Args:
            message: Server error message
            
        Returns:
            Tuple of (response, status_code)
        """
        return APIResponse.error(
            message=message,
            status_code=500,
            error_code="SERVER_ERROR"
        )

# Convenience functions for backward compatibility
def success_response(data=None, message="Success", status_code=200):
    """Backward compatible success response."""
    return APIResponse.success(data, message, status_code)

def error_response(message, status_code=400, details=None):
    """Backward compatible error response."""
    return APIResponse.error(message, status_code, details)

# Response decorators
def api_response_handler(f):
    """Decorator to automatically handle API responses."""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            
            # If function returns a tuple with status code, pass through
            if isinstance(result, tuple) and len(result) == 2:
                return result
            
            # If function returns data directly, wrap in success response
            return APIResponse.success(data=result)
            
        except ValueError as e:
            return APIResponse.validation_error(str(e))
        except KeyError as e:
            return APIResponse.not_found(f"Required field: {str(e)}")
        except Exception as e:
            logger.exception(f"Unhandled error in {f.__name__}")
            return APIResponse.server_error(f"Unexpected error: {str(e)}")
    
    return decorated_function