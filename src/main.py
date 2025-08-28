"""
Main Application Entry Point
===========================

Main entry point for the Thesis App with Celery integration
and analyzer orchestration capabilities.
"""

import os
import sys
import logging
from pathlib import Path

# Configure centralized logging
from app.utils.logging_config import setup_application_logging

logger = setup_application_logging()

# Clean up old logs at startup
try:
    import sys
    from pathlib import Path
    scripts_dir = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from log_cleanup import cleanup_logs_startup
    cleanup_logs_startup()
except Exception as e:
    logger.warning(f"Log cleanup at startup failed: {e}")

def main():
    """Main application entry point."""
    
    # Add src directory to path (current directory)
    src_dir = Path(__file__).parent
    sys.path.insert(0, str(src_dir))
    
    # Import after path setup
    from app.factory import create_app
    
    # Get configuration from environment
    config_name = os.environ.get('FLASK_ENV', 'development')
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
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
    
    # Print startup information
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           Thesis App - AI Model Analyzer                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Environment: {config_name:<20} │ Debug: {str(debug):<5}                       ║
║ Host: {host:<25} │ Port: {port:<10}                       ║
║                                                                              ║
║ Features:                                                                    ║
║  • Celery Task Queue Integration                                             ║
║  • Containerized Analyzer Services                                           ║
║  • Real-time Analysis Results                                                ║
║  • Batch Processing Capabilities                                             ║
║                                                                              ║
║ API Endpoints:                                                               ║
║  • GET  /health                    - Application health check                ║
║  • GET  /api/tasks/status         - Active tasks status                     ║
║  • GET  /api/tasks/history        - Task execution history                  ║
║  • GET  /api/analyzer/status      - Analyzer services status                ║
║  • POST /api/analyzer/start       - Start analyzer services                 ║
║  • POST /api/analyzer/stop        - Stop analyzer services                  ║
║  • POST /api/analyzer/restart     - Restart analyzer services               ║
║                                                                              ║
║ Celery Workers:                                                              ║
║  To start Celery worker: celery -A app.tasks worker --loglevel=info         ║
║  To start Celery beat: celery -A app.tasks beat --loglevel=info             ║
║                                                                              ║
║ Analyzer Services:                                                           ║
║  Auto-start: {str(app.config.get('ANALYZER_AUTO_START', False)):<5}                                                ║
║  Location: ../analyzer/analyzer_manager.py                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Start the application
    try:
        # Prefer SocketIO server if available to enable real-time features
        try:
            from app.extensions import SOCKETIO_AVAILABLE, socketio
        except Exception:
            SOCKETIO_AVAILABLE, socketio = False, None

        if SOCKETIO_AVAILABLE and socketio is not None:
            socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
        else:
            app.run(
                host=host,
                port=port,
                debug=debug,
                threaded=True
            )
    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user")
        return 0
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
