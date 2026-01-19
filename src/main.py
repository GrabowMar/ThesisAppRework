"""
Main Application Entry Point
===========================

Main entry point for the Thesis App with Celery integration
and analyzer orchestration capabilities.

This module serves as the primary entry point for the Flask web application.
It handles application initialization, configuration loading, and server startup.
The app supports both development and production modes with different execution
backends (threading vs Celery distributed tasks).

Key Features:
- Flask web application with SocketIO real-time features
- Celery distributed task processing for analysis workloads
- Containerized analyzer services integration
- Comprehensive logging and error handling
- UTF-8 encoding support for Windows compatibility

Environment Variables:
    FLASK_ENV: Application environment (development/production)
    PORT: Server port (default: 5000)
    HOST: Server host (default: 0.0.0.0)
    DEBUG: Enable debug mode (default: true in development)
    USE_CELERY_ANALYSIS: Use Celery for analysis tasks (default: false)
    LOG_LEVEL: Logging level configuration

The application provides REST APIs for health checks, task management,
and analyzer control, along with real-time WebSocket updates for analysis progress.
"""

import os
import sys
from pathlib import Path

# Configure centralized logging 
from app.utils.logging_config import setup_application_logging

logger = setup_application_logging()

# Clean up old logs at startup (optional - only runs if scripts/ exists)
try:
    scripts_dir = Path(__file__).parent.parent / "scripts"
    if scripts_dir.exists() and (scripts_dir / "log_cleanup.py").exists():
        sys.path.insert(0, str(scripts_dir))
        from log_cleanup import cleanup_logs_startup  # type: ignore[import-not-found]
        cleanup_logs_startup()
    # else: Skip silently in containerized environments where scripts/ isn't deployed
except Exception as e:
    # Non-critical: just log at debug level and continue
    logger.debug(f"Log cleanup at startup skipped: {e}")

def main():
    """Main application entry point.
    
    Initializes and starts the Flask application with the following steps:
    1. Sets up UTF-8 encoding for cross-platform compatibility
    2. Loads environment variables and configuration
    3. Creates Flask application instance
    4. Configures logging and startup banner
    5. Starts the web server (with or without SocketIO)
    6. Handles graceful shutdown on interrupt
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    
    # Add src directory to path (current directory)
    src_dir = Path(__file__).parent
    sys.path.insert(0, str(src_dir))
    
    # Ensure stdout/stderr are UTF-8 encoded to support Unicode banners on Windows
    try:
        # Use getattr to keep type-checkers happy even if the wrapper doesn't expose reconfigure
        _reconf_out = getattr(sys.stdout, "reconfigure", None)
        if callable(_reconf_out):
            _reconf_out(encoding="utf-8", errors="replace")
        _reconf_err = getattr(sys.stderr, "reconfigure", None)
        if callable(_reconf_err):
            _reconf_err(encoding="utf-8", errors="replace")
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    except Exception:
        # Non-fatal if we can't reconfigure; we'll use a safe banner fallback below
        pass
    
    # Import after path setup
    from app.factory import create_app
    
    # Get configuration from environment
    config_name = os.environ.get('FLASK_ENV', 'development')
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'true').lower() == 'true'
    
    logger.info(f"Starting Thesis App in {config_name} mode")
    logger.info(f"Server will run on {host}:{port}")
    
    # Create Flask application
    try:
        app = create_app(config_name)
        logger.info("Flask application created successfully")
    except Exception as e:
        logger.error(f"Failed to create Flask application: {e}")
        return 1
    
    # Determine execution mode for banner
    use_celery = os.environ.get('USE_CELERY_ANALYSIS', 'false').lower() == 'true'
    execution_mode = "Celery Distributed Task Queue" if use_celery else "ThreadPoolExecutor (8 workers)"

    # Print startup information with a Unicode banner; fall back to ASCII if needed
    try:
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           Thesis App - AI Model Analyzer                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Environment: {config_name:<20} │ Debug: {str(debug):<5}                       ║
║ Host: {host:<25} │ Port: {port:<10}                       ║
║                                                                              ║
║ Features:                                                                    ║
║  • {execution_mode:<58}                            ║
║  • Containerized Analyzer Services                                           ║
║  • Real-time Analysis Results                                                ║
║  • Batch Processing Capabilities                                             ║
║                                                                              ║
║ API Endpoints:                                                               ║
║  • GET  /api/health                - Application health check                ║
║  • GET  /api/tasks/status         - Active tasks status                     ║
║  • GET  /api/tasks/history        - Task execution history                  ║
║  • GET  /api/analyzer/status      - Analyzer services status                ║
║  • POST /api/analyzer/start       - Start analyzer services                 ║
║  • POST /api/analyzer/stop        - Stop analyzer services                  ║
║  • POST /api/analyzer/restart     - Restart analyzer services               ║
║                                                                              ║
║ Analyzer Services:                                                           ║
║  Auto-start: {str(app.config.get('ANALYZER_AUTO_START', False)):<5}                                                ║
║  Location: ../analyzer/analyzer_manager.py                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)
    except Exception:
        print(
            "Thesis App - AI Model Analyzer\n"
            f"Environment: {config_name} | Debug: {debug}\n"
            f"Host: {host} | Port: {port}\n"
            f"Features: {execution_mode}, Analyzer services, Real-time results, Batch processing\n"
            "Endpoints: /api/health, /api/tasks/status, /api/tasks/history, /api/analyzer/*\n"
            f"Analyzer Auto-start: {app.config.get('ANALYZER_AUTO_START', False)} | Location: ../analyzer/analyzer_manager.py\n"
        )
    
    # Start the application
    try:
        # Prefer SocketIO server if available to enable real-time features
        try:
            from app.extensions import SOCKETIO_AVAILABLE, socketio
        except Exception:
            SOCKETIO_AVAILABLE, socketio = False, None

        if SOCKETIO_AVAILABLE and socketio is not None:
            socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True, use_reloader=False)
        else:
            app.run(
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,
                threaded=True
            )
    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user")
        return 0
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())

