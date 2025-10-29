"""
Main Application Entry Point
===========================

Main entry point for the Thesis App with Celery integration
and analyzer orchestration capabilities.
"""

import os
import sys
from pathlib import Path

# Configure centralized logging 
from app.utils.logging_config import setup_application_logging

logger = setup_application_logging()

# Clean up old logs at startup
try:
    scripts_dir = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from log_cleanup import cleanup_logs_startup  # type: ignore[import-not-found]
    cleanup_logs_startup()
except Exception as e:
    logger.warning(f"Log cleanup at startup failed: {e}")

def main():
    """Main application entry point."""
    
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
    # Run generated content migration (best-effort)
    try:
        from app.services.generation_migration import run_generated_migration
        mig_report = run_generated_migration(delete_source=False)
        if not mig_report.get('skipped'):
            logger.info("Generated content migration run: moved_files=%s", mig_report.get('moved_files'))
    except Exception as mig_err:  # noqa: BLE001
        logger.warning(f"Generated content migration skipped due to error: {mig_err}")
    
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
║  • ThreadPoolExecutor Task Execution (4 workers)                             ║
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
            "Features: ThreadPoolExecutor (4 workers), Analyzer services, Real-time results, Batch processing\n"
            "Endpoints: /health, /api/tasks/status, /api/tasks/history, /api/analyzer/*\n"
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
                use_reloader=False
            )
    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user")
        return 0
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())

# reload

