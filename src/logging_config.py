"""
Advanced Logging Configuration
==============================

Comprehensive logging setup for the Thesis Research App with multiple handlers,
filters, and performance monitoring capabilities.
"""

import logging
import logging.handlers
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from flask import Flask, g, has_request_context
import uuid


class PerformanceFilter(logging.Filter):
    """Filter to add performance metrics to log records."""
    
    def filter(self, record):
        # Add performance context if available
        if has_request_context():
            record.request_id = getattr(g, 'request_id', '-')
            record.duration_ms = getattr(g, 'duration_ms', 0)
        else:
            record.request_id = '-'
            record.duration_ms = 0
        
        # Add component name from logger name
        record.component = record.name.split('.')[0] if '.' in record.name else record.name
        return True


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from logs."""
    
    SENSITIVE_PATTERNS = [
        'password', 'token', 'secret', 'key', 'auth'
    ]
    
    def filter(self, record):
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            # Simple check for sensitive patterns
            if any(pattern.lower() in message.lower() for pattern in self.SENSITIVE_PATTERNS):
                # Replace with placeholder
                for pattern in self.SENSITIVE_PATTERNS:
                    if pattern.lower() in message.lower():
                        record.msg = message.replace(pattern, '***REDACTED***')
                        break
        return True


class LoggingConfig:
    """Advanced logging configuration for the application."""
    
    @staticmethod
    def setup_comprehensive_logging(app: Flask) -> None:
        """Setup comprehensive logging with multiple handlers and filters."""
        
        # Get configuration
        log_dir = Path(app.config.get('LOG_DIR', 'logs'))
        log_level = app.config.get('LOG_LEVEL', 'INFO')
        debug_mode = app.config.get('DEBUG', False)
        
        # Ensure log directory exists
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert log level string to logging constant
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] [%(request_id)s] %(component)s.%(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        performance_formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] [%(request_id)s] [%(duration_ms).2fms] %(component)s.%(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        json_formatter = JsonFormatter()
        
        # Create filters
        performance_filter = PerformanceFilter()
        sensitive_filter = SensitiveDataFilter()
        
        # Create handlers
        handlers = LoggingConfig._create_handlers(log_dir, numeric_level, detailed_formatter, 
                                                performance_formatter, json_formatter)
        
        # Apply filters to handlers
        for handler in handlers:
            handler.addFilter(performance_filter)
            handler.addFilter(sensitive_filter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(numeric_level)
        
        for handler in handlers:
            root_logger.addHandler(handler)
        
        # Setup request middleware
        LoggingConfig._setup_request_middleware(app)
        
        # Setup error handlers
        LoggingConfig._setup_error_handlers(app)
        
        # Configure third-party loggers
        LoggingConfig._configure_third_party_loggers(numeric_level)
        
        logging.info("Comprehensive logging system initialized")
        logging.info(f"Log level: {log_level}, Directory: {log_dir}")
    
    @staticmethod
    def _create_handlers(log_dir: Path, level: int, detailed_formatter, 
                        performance_formatter, json_formatter) -> list:
        """Create all logging handlers."""
        handlers = []
        
        # Main application log (rotating)
        app_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / 'app.log',
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=10,
            encoding='utf-8'
        )
        app_handler.setLevel(level)
        app_handler.setFormatter(detailed_formatter)
        handlers.append(app_handler)
        
        # Error-only log
        error_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / 'errors.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        handlers.append(error_handler)
        
        # Performance log
        perf_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / 'performance.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(performance_formatter)
        perf_handler.addFilter(PerformanceLogFilter())
        handlers.append(perf_handler)
        
        # JSON structured log for analytics
        json_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / 'structured.log',
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(json_formatter)
        handlers.append(json_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(component)s: %(message)s',
            datefmt='%H:%M:%S'
        ))
        handlers.append(console_handler)
        
        return handlers
    
    @staticmethod
    def _setup_request_middleware(app: Flask) -> None:
        """Setup request logging middleware with performance tracking."""
        
        @app.before_request
        def before_request():
            g.request_id = str(uuid.uuid4())[:8]
            g.start_time = time.time()
            g.request_start = time.time()
            
            # Log request start (excluding static files)
            if not request.path.startswith('/static/'):
                logging.info(f"Request started: {request.method} {request.path}")
        
        @app.after_request
        def after_request(response):
            # Calculate duration
            duration = time.time() - getattr(g, 'start_time', time.time())
            g.duration_ms = duration * 1000
            
            # Add request ID to response headers
            response.headers['X-Request-ID'] = getattr(g, 'request_id', '-')
            
            # Log request completion
            if response.status_code >= 400:
                logging.warning(f"Request failed: {request.method} {request.path} - "
                              f"Status: {response.status_code} - Duration: {duration:.3f}s")
            elif duration > 1.0:  # Log slow requests
                logging.warning(f"Slow request: {request.method} {request.path} - "
                              f"Duration: {duration:.3f}s")
            elif not request.path.startswith('/static/'):
                logging.info(f"Request completed: {request.method} {request.path} - "
                           f"Status: {response.status_code} - Duration: {duration:.3f}s")
            
            return response
    
    @staticmethod
    def _setup_error_handlers(app: Flask) -> None:
        """Setup error handlers with logging."""
        
        @app.errorhandler(Exception)
        def handle_exception(e):
            # Log the exception
            logging.error(f"Unhandled exception: {e}", exc_info=True)
            
            # Return appropriate response
            if hasattr(e, 'code'):
                return str(e), e.code
            return "Internal Server Error", 500
    
    @staticmethod
    def _configure_third_party_loggers(level: int) -> None:
        """Configure third-party library loggers."""
        
        # Werkzeug (Flask's HTTP server)
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.WARNING)  # Reduce verbosity
        
        # SQLAlchemy
        sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
        sqlalchemy_logger.setLevel(logging.WARNING)
        
        # Docker library
        docker_logger = logging.getLogger('docker')
        docker_logger.setLevel(logging.WARNING)
        
        # Requests library
        requests_logger = logging.getLogger('requests.packages.urllib3')
        requests_logger.setLevel(logging.WARNING)


class PerformanceLogFilter(logging.Filter):
    """Filter for performance-specific logging."""
    
    def filter(self, record):
        # Only log records related to performance
        performance_keywords = ['duration', 'time', 'performance', 'slow', 'completed']
        message = record.getMessage().lower()
        return any(keyword in message for keyword in performance_keywords)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        import json
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'component': getattr(record, 'component', record.name),
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-'),
            'duration_ms': getattr(record, 'duration_ms', 0),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


# Example usage function
def setup_logging_for_app(app: Flask) -> None:
    """Convenience function to setup logging for the application."""
    LoggingConfig.setup_comprehensive_logging(app)
