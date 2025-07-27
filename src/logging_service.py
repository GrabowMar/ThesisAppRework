"""
Logging Service Module
=====================

Centralized logging configuration and utilities for the Flask application.
Provides structured logging with request context, file rotation, and filtering.
"""

import logging
import logging.handlers
import os
import time
import uuid
from pathlib import Path
from flask import Flask, g, has_request_context, request

# Optional import for colored console output
try:
    import coloredlogs
    HAS_COLOREDLOGS = True
except ImportError:
    HAS_COLOREDLOGS = False


class ContextFilter(logging.Filter):
    """
    Add request context information to log records.
    Adds request ID and component name to log records for better traceability.
    """
    
    def filter(self, record):
        """
        Filter and enhance log record with context information.
        
        Args:
            record: Log record to filter
            
        Returns:
            True to allow the record to be processed
        """
        try:
            if has_request_context():
                record.request_id = getattr(g, 'request_id', '-')
            else:
                record.request_id = '-'
        except RuntimeError:
            record.request_id = '-'
        
        if '.' in record.name:
            record.component = record.name.split('.', 1)[0]
        else:
            record.component = record.name if record.name != 'root' else 'app'
        
        return True


class RequestFilter(logging.Filter):
    """
    Filter out noisy requests from werkzeug logs.
    Filters out common requests like health checks and static files to reduce log noise.
    """
    
    EXCLUDED_PATHS = {'/api/status', '/static/', '/favicon.ico'}
    
    def filter(self, record):
        """
        Filter werkzeug log records based on request path.
        
        Args:
            record: Log record to filter
            
        Returns:
            True to allow the record, False to filter it out
        """
        if record.name != 'werkzeug':
            return True
        
        try:
            if hasattr(record, 'args') and record.args:
                request_line = str(record.args[0])
                parts = request_line.split()
                if len(parts) >= 2:
                    path = parts[1]
                    if any(excluded in path for excluded in self.EXCLUDED_PATHS):
                        status_code = record.args[1] if len(record.args) > 1 else 200
                        return status_code >= 400
        except (IndexError, ValueError, TypeError):
            pass
        
        return True


def create_file_handler(filename: Path, level: int, format_str: str) -> logging.Handler:
    """Create a rotating file handler."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    
    handler = logging.handlers.RotatingFileHandler(
        filename=filename,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format_str, '%Y-%m-%d %H:%M:%S'))
    
    return handler


def setup_console_logging(logger: logging.Logger, level: int, debug_mode: bool):
    """Setup console logging with optional colors."""
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    if debug_mode and HAS_COLOREDLOGS:
        try:
            coloredlogs.install(
                level=level,
                logger=logger,
                fmt=format_str,
                datefmt='%Y-%m-%d %H:%M:%S',
                level_styles={
                    'debug': {'color': 'blue'},
                    'info': {'color': 'green'},
                    'warning': {'color': 'yellow'},
                    'error': {'color': 'red'},
                    'critical': {'color': 'red', 'bold': True}
                }
            )
            return
        except Exception:
            pass  # Fall back to standard console handler
    
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format_str, '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)


def initialize_logging(app: Flask):
    """Initialize logging for a Flask application."""
    log_level_name = app.config.get('LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO'))
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    log_dir = Path(app.config.get('LOG_DIR', 'logs'))
    
    context_filter = ContextFilter()
    request_filter = RequestFilter()
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    
    app_handler = create_file_handler(
        log_dir / 'app.log',
        log_level,
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(component)s.%(name)s: %(message)s"
    )
    app_handler.addFilter(context_filter)
    root_logger.addHandler(app_handler)
    
    error_handler = create_file_handler(
        log_dir / 'errors.log',
        logging.ERROR,
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(component)s.%(name)s.%(funcName)s:%(lineno)d - %(message)s"
    )
    error_handler.addFilter(context_filter)
    root_logger.addHandler(error_handler)
    
    setup_console_logging(root_logger, log_level, app.debug)
    
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()
    werkzeug_logger.setLevel(log_level)
    werkzeug_logger.propagate = False
    
    request_handler = create_file_handler(
        log_dir / 'requests.log',
        log_level,
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s"
    )
    request_handler.addFilter(context_filter)
    request_handler.addFilter(request_filter)
    werkzeug_logger.addHandler(request_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", 
        '%Y-%m-%d %H:%M:%S'
    ))
    console_handler.addFilter(context_filter)
    console_handler.addFilter(request_filter)
    werkzeug_logger.addHandler(console_handler)
    
    component_levels = {
        "docker": logging.INFO,
        "zap_scanner": logging.INFO,
        "performance": logging.INFO,
        "security": logging.INFO,
    }
    
    for component, level in component_levels.items():
        logging.getLogger(component).setLevel(level)
    
    setup_request_middleware(app)
    
    logging.info(f"Logging initialized. Level: {log_level_name}, Directory: {log_dir}")


def setup_request_middleware(app: Flask):
    """Setup request logging and ID generation."""
    QUIET_PATHS = {'/static/', '/api/status', '/favicon.ico'}
    
    @app.before_request
    def before_request():
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()
        g.is_quiet = any(quiet in request.path for quiet in QUIET_PATHS)
        if not g.is_quiet:
            logging.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
    
    @app.after_request
    def after_request(response):
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '-')
        start_time = getattr(g, 'start_time', time.time())
        duration = time.time() - start_time
        is_quiet = getattr(g, 'is_quiet', False)
        is_error = response.status_code >= 400
        is_slow = duration > 1.0
        if is_error or is_slow or not is_quiet:
            level = logging.WARNING if is_error else logging.INFO
            status_info = f"{response.status_code}"
            if is_slow:
                status_info += " [SLOW]"
            logging.log(level, f"Response: {request.method} {request.path} - "
                                 f"Status: {status_info} - Duration: {duration:.3f}s")
        return response
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        duration = time.time() - getattr(g, 'start_time', time.time())
        logging.exception(f"Unhandled exception: {request.method} {request.path} - "
                         f"Error: {e} - Duration: {duration:.3f}s")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from flask import jsonify
            status_code = getattr(e, 'code', 500)
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'An error occurred'
            }), status_code
        raise e


def create_logger_for_component(component_name: str) -> logging.Logger:
    """Create a logger for a specific component."""
    return logging.getLogger(component_name)