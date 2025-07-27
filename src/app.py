"""
Flask Application Main Module
============================

Main application factory and configuration for the Thesis Research App.
Provides security analysis, performance testing, and ZAP scanning capabilities.
"""

import atexit
import logging
import os  # Re-added for environment variable access
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Tuple, Type  # Removed List, Union

from dotenv import load_dotenv
from flask import Flask, Response, current_app, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from backend_security_analysis import BackendSecurityAnalyzer
from frontend_security_analysis import FrontendSecurityAnalyzer
from code_quality_analysis import BackendQualityAnalyzer, FrontendQualityAnalyzer
from openrouter_analyzer import OpenRouterAnalyzer
from logging_service import create_logger_for_component, initialize_logging
from routes import analysis_bp, api_bp, gpt4all_bp, main_bp, performance_bp, quality_bp, zap_bp
from generation_routes import generation_bp
from services import (
    DockerManager,
    PortManager,
    ScanManager,
    SystemHealthMonitor,
    create_scanner as create_zap_scanner,
    initialize_model_service,
    get_model_service,
)
from utils import (
    AppConfig,
    get_ai_models_from_config,
    load_port_config,
    stop_zap_scanners,
    cleanup_expired_cache,
)

# Load environment variables
load_dotenv()


@dataclass(frozen=True)
class AppDefaults:
    """Application default configuration values."""
    
    CLEANUP_INTERVAL: int = 300  # 5 minutes
    IDLE_SCAN_TIMEOUT: int = 3600  # 1 hour
    MAX_ZAP_SCANS: int = 10
    HOST: str = "127.0.0.1"
    PORT: int = 5000
    MAX_THREADS: int = 50
    REQUEST_TIMEOUT: int = 30


class AnalyzerProtocol(Protocol):
    """Protocol for analyzer classes."""
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the analyzer."""
        ...


class AppError(Exception):
    """Base exception for application errors."""
    
    def __init__(self, message: str, code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class InitializationError(AppError):
    """Exception raised during application initialization."""
    pass


class ServiceManager:
    """Manages application services and their lifecycle."""
    
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.logger = create_logger_for_component('service_manager')
        self._services: Dict[str, Any] = {}
        self._cleanup_lock = threading.RLock()
        
        # Ensure app.extensions exists
        if not hasattr(app, 'extensions'):
            app.extensions = {}
    
    def register_service(self, name: str, service: Any) -> None:
        """Register a service with the manager."""
        with self._cleanup_lock:
            self._services[name] = service
            # Store in both places for consistency
            setattr(self.app, name, service)
            self.app.extensions[name] = service
            self.logger.info(f"Registered service: {name}")
    
    def get_service(self, name: str) -> Optional[Any]:
        """Get a registered service."""
        return self._services.get(name)
    
    def cleanup_services(self) -> None:
        """Clean up all registered services."""
        with self._cleanup_lock:
            for name, service in self._services.items():
                try:
                    if hasattr(service, 'cleanup'):
                        service.cleanup()
                    self.logger.info(f"Cleaned up service: {name}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up service {name}: {e}")


class HostPortValidator:
    """Validates host and port configuration."""
    
    @staticmethod
    def validate(host: Optional[str], port: Optional[int]) -> Tuple[str, int]:
        """
        Validate and return host and port configuration.
        
        Args:
            host: Host address to validate
            port: Port number to validate
            
        Returns:
            Tuple of validated host and port
            
        Raises:
            ValueError: If validation fails
        """
        defaults = AppDefaults()
        
        # Validate host
        if not host or not isinstance(host, str) or not host.strip():
            validated_host = defaults.HOST
        else:
            validated_host = host.strip()
        
        # Validate port
        if port is None or not isinstance(port, int) or not (1 <= port <= 65535):
            validated_port = defaults.PORT
        else:
            validated_port = port
            
        return validated_host, validated_port


class ErrorResponseGenerator:
    """Generates appropriate error responses for different request types."""
    
    @staticmethod
    def generate(error_code: int, error_name: str, error_message: str) -> Tuple[Any, int]:
        """
        Generate an appropriate error response based on request type.
        
        Args:
            error_code: HTTP error code
            error_name: Error name/type
            error_message: Error description
            
        Returns:
            Tuple of response and status code
        """
        if request.path.startswith('/api/'):
            response = jsonify({
                'error': {
                    'code': error_code,
                    'name': error_name,
                    'message': error_message,
                    'timestamp': time.time()
                }
            })
        else:
            try:
                debug_mode = current_app.config.get("DEBUG", False)
            except RuntimeError:
                debug_mode = False
            response = render_template(
                'error.html',
                error_code=error_code,
                error_name=error_name,
                error_message=error_message,
                debug=debug_mode
            )
        return response, error_code


class ScanCleanupManager:
    """Manages cleanup of old ZAP scans."""
    
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.logger = create_logger_for_component('cleanup.scans')
        self._cleanup_lock = threading.RLock()
        self._running = True
        self.defaults = AppDefaults()
    
    def start_cleanup_thread(self) -> None:
        """Start the background cleanup thread."""
        cleanup_thread = threading.Thread(
            target=self._cleanup_task,
            daemon=True,
            name="ScanCleanup"
        )
        cleanup_thread.start()
        self.logger.info("Scan cleanup thread started")
    
    def stop(self) -> None:
        """Stop the cleanup manager."""
        self._running = False
    
    def _cleanup_task(self) -> None:
        """Periodically clean up old ZAP scans."""
        while self._running:
            try:
                time.sleep(self.defaults.CLEANUP_INTERVAL)
                self._perform_cleanup()
            except Exception as e:
                self.logger.error(f"Error in scan cleanup: {e}")
    
    def _perform_cleanup(self) -> None:
        """Perform the actual cleanup operation."""
        with self._cleanup_lock:
            if not hasattr(self.app, 'config') or 'ZAP_SCANS' not in self.app.config:
                return
            
            scans = self.app.config['ZAP_SCANS']
            current_time = time.time()
            
            # Remove idle scans
            self._remove_idle_scans(scans, current_time)
            
            # Limit total scans
            self._limit_total_scans(scans)
    
    def _remove_idle_scans(self, scans: Dict[str, Any], current_time: float) -> None:
        """Remove scans that have been idle too long."""
        to_remove = [
            scan_id for scan_id, scan_data in scans.items()
            if current_time - scan_data.get('last_update', 0) > self.defaults.IDLE_SCAN_TIMEOUT
        ]
        
        for scan_id in to_remove:
            self.logger.info(f"Removing idle scan: {scan_id}")
            scans.pop(scan_id, None)
    
    def _limit_total_scans(self, scans: Dict[str, Any]) -> None:
        """Limit the total number of scans to prevent memory issues."""
        if len(scans) <= self.defaults.MAX_ZAP_SCANS:
            return
        
        oldest_scans = sorted(
            scans.items(),
            key=lambda x: x[1].get('last_update', 0)
        )
        
        excess_count = len(scans) - self.defaults.MAX_ZAP_SCANS
        for scan_id, _ in oldest_scans[:excess_count]:
            self.logger.info(f"Removing excess scan: {scan_id}")
            scans.pop(scan_id, None)


class AnalyzerInitializer:
    """Handles initialization of various analyzers."""
    
    def __init__(self, app: Flask, service_manager: ServiceManager) -> None:
        self.app = app
        self.service_manager = service_manager
        self.logger = create_logger_for_component('init.analyzers')
    
    def initialize_all(self, project_root_path: Path, app_base_dir: Path) -> None:
        """
        Initialize all analyzers used by the application.
        
        Args:
            project_root_path: Path to the project root directory
            app_base_dir: Path to the application base directory
        """
        models_dir = project_root_path / "models"
        
        # Initialize security analyzers
        self._initialize_security_analyzers(models_dir)
        self._initialize_quality_analyzers(models_dir)
        
        # Initialize OpenRouter analyzer
        self._initialize_openrouter_analyzer(project_root_path)
        
        # Initialize performance tester
        self._initialize_performance_tester(app_base_dir)
        
        # Initialize GPT4All analyzer
        self._initialize_gpt4all_analyzer()
        
        # Initialize ZAP scanner
        self._initialize_zap_scanner(app_base_dir)
        
        self.logger.info("All analyzers initialized")
    
    def _initialize_analyzer(
        self,
        analyzer_class: Type[AnalyzerProtocol],
        service_name: str,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Initialize a single analyzer."""
        try:
            self.logger.info(f"Initializing {analyzer_class.__name__}")
            analyzer = analyzer_class(*args, **kwargs)
            self.service_manager.register_service(service_name, analyzer)
            self.logger.info(f"{analyzer_class.__name__} initialized successfully")
        except Exception as e:
            self.logger.exception(f"Failed to initialize {analyzer_class.__name__}: {e}")
            self.service_manager.register_service(service_name, None)
    
    def _initialize_security_analyzers(self, models_dir: Path) -> None:
        """Initialize security analyzers."""
        self._initialize_analyzer(
            BackendSecurityAnalyzer,
            'backend_security_analyzer',
            models_dir
        )
        self._initialize_analyzer(
            FrontendSecurityAnalyzer,
            'frontend_security_analyzer',
            models_dir
        )
    
    def _initialize_quality_analyzers(self, models_dir: Path) -> None:
        """Initialize code quality analyzers."""
        self._initialize_analyzer(
            BackendQualityAnalyzer,
            'backend_quality_analyzer',
            models_dir
        )
        self._initialize_analyzer(
            FrontendQualityAnalyzer,
            'frontend_quality_analyzer',
            models_dir
        )
    
    def _initialize_openrouter_analyzer(self, project_root_path: Path) -> None:
        """Initialize OpenRouter analyzer."""
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        if not openrouter_api_key:
            self.logger.warning("OPENROUTER_API_KEY not found in environment")
        self._initialize_analyzer(
            OpenRouterAnalyzer,
            'openrouter_analyzer',
            str(project_root_path)
        )
    
    def _initialize_performance_tester(self, app_base_dir: Path) -> None:
        """Initialize performance tester with lazy loading to avoid monkey-patching issues."""
        performance_report_dir = app_base_dir / "performance_reports"
        performance_report_dir.mkdir(exist_ok=True)
        
        # Import the performance tester class only when needed
        try:
            from performance_analysis import LocustPerformanceTester
            self._initialize_analyzer(
                LocustPerformanceTester,
                'performance_tester',
                performance_report_dir
            )
            
            # Also register with the alias expected by batch analysis
            performance_tester = self.service_manager.get_service('performance_tester')
            if performance_tester:
                self.service_manager.register_service('performance_analyzer', performance_tester)
        except Exception as init_error:
            error_message = f"Performance testing unavailable: {init_error}"
            self.logger.warning(f"Performance tester initialization failed: {init_error}")
            
            # Create a placeholder that will show appropriate error messages
            class PlaceholderPerformanceTester:
                def __init__(self, *args, **kwargs):
                    self.available = False
                    self.error_message = error_message
                
                def run_test_library(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def run_test_cli(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def run_performance_test(self, model, app_num):
                    """Batch analysis compatible method"""
                    raise RuntimeError(self.error_message)
            
            self.service_manager.register_service('performance_tester', PlaceholderPerformanceTester())
            
            # Also register the placeholder with the alias expected by batch analysis
            placeholder = self.service_manager.get_service('performance_tester')
            if placeholder:
                self.service_manager.register_service('performance_analyzer', placeholder)
    
    def _initialize_gpt4all_analyzer(self) -> None:
        """Initialize GPT4All analyzer for batch processing."""
        try:
            from gpt4all_analyzer import create_gpt4all_analyzer
            analyzer = create_gpt4all_analyzer()
            
            # Register with the name expected by batch analysis
            self.service_manager.register_service('gpt4all_analyzer', analyzer)
            self.logger.info("GPT4All analyzer initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"GPT4All analyzer initialization failed: {e}")
            error_msg = f"GPT4All analyzer unavailable: {e}"
            
            # Create a placeholder
            class PlaceholderGPT4AllAnalyzer:
                def __init__(self):
                    self.available = False
                    self.error_message = error_msg
                
                def analyze_app(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def is_available(self):
                    return False
            
            self.service_manager.register_service('gpt4all_analyzer', PlaceholderGPT4AllAnalyzer())
    
    def _initialize_zap_scanner(self, app_base_dir: Path) -> None:
        """Initialize ZAP scanner with better error handling and logging."""
        try:
            self.logger.info("[ZAP INIT] Starting ZAP scanner initialization")
            self.logger.info(f"[ZAP INIT] App base directory: {app_base_dir}")
            
            # Create ZAP scanner with enhanced logging
            zap_scanner = create_zap_scanner(app_base_dir)
            
            if zap_scanner:
                self.logger.info("[ZAP INIT] ZAP scanner instance created successfully")
                self.service_manager.register_service('zap_scanner', zap_scanner)
                self.app.config["ZAP_SCANS"] = {}
                
                # Log scanner status
                if hasattr(zap_scanner, 'is_ready'):
                    ready = zap_scanner.is_ready()
                    self.logger.info(f"[ZAP INIT] Scanner ready status: {ready}")
                else:
                    self.logger.warning("[ZAP INIT] Scanner does not have is_ready method")
                    
                self.logger.info("[ZAP INIT] ZAP scanner initialization complete")
            else:
                self.logger.error("[ZAP INIT] create_zap_scanner returned None")
                
                # Create placeholder ZAP scanner for batch analysis compatibility
                class PlaceholderZAPScanner:
                    def __init__(self):
                        self.available = False
                        self.error_message = "ZAP scanner not available - zapv2 module not installed"
                    
                    def start_scan(self, *args, **kwargs):
                        raise RuntimeError(self.error_message)
                    
                    def scan_app(self, model, app_num):
                        """Batch analysis compatible method"""
                        raise RuntimeError(self.error_message)
                    
                    def is_ready(self):
                        return False
                
                self.service_manager.register_service('zap_scanner', PlaceholderZAPScanner())
                self.app.config["ZAP_SCANS"] = {}
                
        except Exception as zap_init_error:
            self.logger.exception(f"[ZAP INIT ERROR] Failed to initialize ZAP scanner: {zap_init_error}")
            
            # Create placeholder ZAP scanner for batch analysis compatibility
            class ZAPErrorPlaceholder:
                def __init__(self, error_msg):
                    self.available = False
                    self.error_message = f"ZAP scanner initialization failed: {error_msg}"
                
                def start_scan(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def scan_app(self, model, app_num):
                    """Batch analysis compatible method"""
                    raise RuntimeError(self.error_message)
                
                def is_ready(self):
                    return False
            
            self.service_manager.register_service('zap_scanner', ZAPErrorPlaceholder(str(zap_init_error)))
            self.app.config["ZAP_SCANS"] = {}


class ServiceInitializer:
    """Handles initialization of application services."""
    
    def __init__(self, app: Flask, service_manager: ServiceManager) -> None:
        self.app = app
        self.service_manager = service_manager
        self.logger = create_logger_for_component('init.services')
    
    def initialize_all(self) -> None:
        """Initialize all services used by the application."""
        self._initialize_docker_manager()
        self._initialize_scan_manager()
        self._initialize_port_manager()
        self._initialize_health_monitor()
    
    def _initialize_docker_manager(self) -> None:
        """Initialize Docker Manager."""
        try:
            docker_manager = DockerManager()
            self.service_manager.register_service('docker_manager', docker_manager)
            self.app.config["docker_manager"] = docker_manager
            self.logger.info("DockerManager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize DockerManager: {e}")
            self.service_manager.register_service('docker_manager', None)
            self.app.config["docker_manager"] = None
    
    def _initialize_scan_manager(self) -> None:
        """Initialize Scan Manager."""
        try:
            scan_manager = ScanManager()
            self.service_manager.register_service('scan_manager', scan_manager)
            self.logger.info("ScanManager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize ScanManager: {e}")
            self.service_manager.register_service('scan_manager', None)
    
    def _initialize_port_manager(self) -> None:
        """Initialize Port Manager."""
        try:
            port_config = self.app.config.get('PORT_CONFIG', [])
            port_manager = PortManager(port_config)
            self.service_manager.register_service('port_manager', port_manager)
            self.logger.info(f"PortManager initialized with {len(port_config)} configurations")
        except Exception as e:
            self.logger.error(f"Failed to initialize PortManager: {e}")
            self.service_manager.register_service('port_manager', None)
    
    def _initialize_health_monitor(self) -> None:
        """Initialize System Health Monitor."""
        try:
            health_monitor = SystemHealthMonitor()
            self.service_manager.register_service('health_monitor', health_monitor)
            self.logger.info("SystemHealthMonitor initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize SystemHealthMonitor: {e}")
            self.service_manager.register_service('health_monitor', None)


class ErrorHandlerRegistry:
    """Registers error handlers for the Flask application."""
    
    @staticmethod
    def register_all(app: Flask) -> None:
        """Register all error handlers for the application."""
        app.register_error_handler(HTTPException, ErrorHandlerRegistry._handle_http_exception)
        app.register_error_handler(BadRequest, ErrorHandlerRegistry._handle_bad_request)
        app.register_error_handler(Exception, ErrorHandlerRegistry._handle_generic_exception)
    
    @staticmethod
    def _handle_http_exception(e: HTTPException) -> Tuple[Response, int]:
        """Handle HTTP exceptions."""
        return ErrorResponseGenerator.generate(
            e.code or 500,
            e.name,
            e.description or "An error occurred"
        )
    
    @staticmethod
    def _handle_bad_request(e: BadRequest) -> Tuple[Response, int]:
        """Handle bad request exceptions."""
        return ErrorResponseGenerator.generate(
            400,
            "Bad Request",
            e.description or "The request could not be understood by the server."
        )
    
    @staticmethod
    def _handle_generic_exception(e: Exception) -> Tuple[Response, int]:
        """Handle generic exceptions."""
        logger = create_logger_for_component('error_handler')
        logger.exception(f"Unhandled exception: {e}")
        
        if current_app.config.get("DEBUG"):
            error_message = f"{type(e).__name__}: {str(e)}"
        else:
            error_message = "An internal server error occurred."
        
        return ErrorResponseGenerator.generate(500, "Internal Server Error", error_message)


class ContextProcessorRegistry:
    """Registers context processors for template rendering."""
    
    @staticmethod
    def register_all(app: Flask) -> None:
        """Register template context processors."""
        @app.context_processor
        def inject_global_context() -> Dict[str, Any]:
            from utils import get_apps_for_model, load_json_results_for_template
            return {
                'port_config': app.config.get('PORT_CONFIG', []),
                'ai_models': app.config.get('AI_MODELS', []),
                'HAS_BATCH_ANALYSIS': app.config.get('HAS_BATCH_ANALYSIS', False),
                'get_apps_for_model': get_apps_for_model,
                'load_json_results': load_json_results_for_template
            }


class ConfigurationLoader:
    """Loads and validates application configuration."""
    
    def __init__(self, app_base_dir: Path) -> None:
        self.app_base_dir = app_base_dir
        self.logger = create_logger_for_component('config_loader')
    
    def load_configuration(self, app: Flask) -> None:
        """Load all configuration for the application."""
        # Load basic configuration
        config = AppConfig.from_env()
        app.config.from_object(config)
        app.config['APP_CONFIG'] = config
        
        # Load port configuration
        self._load_port_configuration(app)
        
        # Load batch analysis configuration
        self._load_batch_analysis_configuration(app)
        
        # Configure JSON handling
        app.config['JSON_SORT_KEYS'] = False
    
    def _load_port_configuration(self, app: Flask) -> None:
        """Load port configuration and initialize model integration service."""
        self.logger.info("Loading port configuration")
        # Use project root path (parent of app_base_dir) since JSON files are there
        project_root = self.app_base_dir.parent
        port_config = load_port_config(project_root)
        app.config['PORT_CONFIG'] = port_config
        
        # Initialize the enhanced model integration service
        self.logger.info(f"Initializing model integration service with path: {project_root}")
        model_service = initialize_model_service(project_root)
        app.config['MODEL_SERVICE'] = model_service
        
        # Maintain backward compatibility with AI_MODELS
        app.config['AI_MODELS'] = get_ai_models_from_config(port_config)
        
        # Add enhanced model data
        all_models = model_service.get_all_models()
        app.config['ENHANCED_MODELS'] = all_models
        app.config['MODEL_STATS'] = model_service.get_summary_stats()
        
        self.logger.info(f"Loaded {len(port_config)} port configurations")
        self.logger.info(f"Integrated {len(all_models)} enhanced models with full capabilities")
    
    def _load_batch_analysis_configuration(self, app: Flask) -> None:
        """Load batch analysis configuration."""
        try:
            from batch_analysis_module import init_batch_analysis
            app.config['HAS_BATCH_ANALYSIS'] = True
            init_batch_analysis(app)
            self.logger.info("Batch analysis module loaded successfully")
        except ImportError as e:
            self.logger.warning(f"Batch analysis module not available: {e}")
            app.config['HAS_BATCH_ANALYSIS'] = False


class CacheCleanupManager:
    """Manager for periodic cache cleanup."""
    
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.cleanup_interval = 300  # 5 minutes
        self.cleanup_thread = None
        self.shutdown_event = threading.Event()
        self.logger = create_logger_for_component('cache_cleanup')
    
    def start_cleanup_thread(self) -> None:
        """Start the cache cleanup thread."""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                daemon=True,
                name="CacheCleanup"
            )
            self.cleanup_thread.start()
            self.logger.info("Cache cleanup thread started")
    
    def stop_cleanup_thread(self) -> None:
        """Stop the cache cleanup thread."""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.shutdown_event.set()
            self.cleanup_thread.join(timeout=5)
            self.logger.info("Cache cleanup thread stopped")
    
    def _cleanup_worker(self) -> None:
        """Background worker for cache cleanup."""
        while not self.shutdown_event.is_set():
            try:
                # Wait for either shutdown event or cleanup interval
                if self.shutdown_event.wait(self.cleanup_interval):
                    break  # Shutdown event was set
                
                # Perform cleanup without Flask context
                try:
                    cleanup_expired_cache()
                    self.logger.debug("Performed periodic cache cleanup")
                except Exception as cleanup_error:
                    self.logger.warning(f"Cache cleanup failed: {cleanup_error}")
                    
            except Exception as e:
                self.logger.error(f"Error in cache cleanup worker: {e}")
                # Continue running despite errors
                time.sleep(60)  # Wait 1 minute before retrying
    
    def cleanup(self) -> None:
        """Cleanup method called on application shutdown."""
        self.stop_cleanup_thread()


class FlaskApplicationFactory:
    """Factory for creating and configuring Flask applications."""
    
    def __init__(self) -> None:
        self.logger = None
        self.service_manager = None
        self.cleanup_manager = None
        self.cache_cleanup_manager = None
    
    def create_app(self) -> Flask:
        """
        Create and configure the Flask application.
        
        Returns:
            Configured Flask application instance
            
        Raises:
            InitializationError: If application initialization fails
        """
        try:
            # Initialize paths
            app_base_dir = Path(__file__).parent.resolve()
            project_root_path = app_base_dir.parent.resolve()
            
            # Create Flask app
            app = self._create_flask_instance(app_base_dir)
            
            # Initialize logging
            initialize_logging(app)
            self.logger = create_logger_for_component('app_startup')
            
            # Configure application
            self._configure_application(app, app_base_dir, project_root_path)
            
            self.logger.info("Application initialization complete")
            return app
            
        except Exception as e:
            if self.logger:
                self.logger.exception(f"Failed to create application: {e}")
            raise InitializationError(f"Application initialization failed: {e}")
    
    def _create_flask_instance(self, app_base_dir: Path) -> Flask:
        """Create the basic Flask instance."""
        return Flask(
            __name__,
            template_folder=str(app_base_dir / "templates"),
            static_folder=str(app_base_dir / "static")
        )
    
    def _configure_application(
        self,
        app: Flask,
        app_base_dir: Path,
        project_root_path: Path
    ) -> None:
        """Configure the Flask application with all necessary components."""
        # Load configuration
        config_loader = ConfigurationLoader(app_base_dir)
        config_loader.load_configuration(app)
        
        # Configure proxy handling
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1, x_proto=1, x_host=1, x_prefix=1
        )
        
        # Initialize service and cleanup managers (but don't use context manager)
        self.service_manager = ServiceManager(app)
        self.cleanup_manager = ScanCleanupManager(app)
        self.cache_cleanup_manager = CacheCleanupManager(app)
        
        # Store managers in app extensions for consistent access
        app.extensions['service_manager'] = self.service_manager
        app.extensions['cleanup_manager'] = self.cleanup_manager
        app.extensions['cache_cleanup_manager'] = self.cache_cleanup_manager
        
        # Initialize services
        service_initializer = ServiceInitializer(app, self.service_manager)
        service_initializer.initialize_all()
        
        # Initialize analyzers
        analyzer_initializer = AnalyzerInitializer(app, self.service_manager)
        analyzer_initializer.initialize_all(project_root_path, app_base_dir)
        
        # Start cleanup thread
        self.cleanup_manager.start_cleanup_thread()
        
        # Start cache cleanup thread
        self.cache_cleanup_manager.start_cleanup_thread()
        
        # Register blueprints
        self._register_blueprints(app)
        
        # Register error handlers and context processors
        ErrorHandlerRegistry.register_all(app)
        ContextProcessorRegistry.register_all(app)
        
        # Register cleanup handlers
        self._register_cleanup_handlers(app)
    
    def _register_blueprints(self, app: Flask) -> None:
        """Register all application blueprints."""
        if self.logger:
            self.logger.info("Registering blueprints")
        blueprints = [main_bp, api_bp, analysis_bp, performance_bp, quality_bp, gpt4all_bp, zap_bp, generation_bp]
        for blueprint in blueprints:
            app.register_blueprint(blueprint)
            if self.logger:
                self.logger.debug(f"Registered blueprint: {blueprint.name}")
    
    def _register_cleanup_handlers(self, app: Flask) -> None:
        """Register cleanup handlers for application shutdown."""
        def cleanup():
            logger = create_logger_for_component('cleanup')
            logger.info("Starting application cleanup")
            
            # Stop ZAP scanners
            try:
                stop_zap_scanners(app)
            except Exception as e:
                logger.error(f"Error stopping ZAP scanners: {e}")
            
            # Safely access extensions
            extensions = getattr(app, 'extensions', {})
            
            # Stop cleanup manager
            if 'cleanup_manager' in extensions:
                try:
                    extensions['cleanup_manager'].stop()
                except Exception as e:
                    logger.error(f"Error stopping cleanup manager: {e}")
            
            # Stop cache cleanup manager
            if 'cache_cleanup_manager' in extensions:
                try:
                    extensions['cache_cleanup_manager'].cleanup()
                except Exception as e:
                    logger.error(f"Error stopping cache cleanup manager: {e}")
            
            # Cleanup services
            if 'service_manager' in extensions:
                try:
                    extensions['service_manager'].cleanup_services()
                except Exception as e:
                    logger.error(f"Error cleaning up services: {e}")
            
            logger.info("Application cleanup complete")
        
        atexit.register(cleanup)


def create_app() -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Configured Flask application instance
    """
    factory = FlaskApplicationFactory()
    return factory.create_app()


def main() -> None:
    """Main entry point for the application."""
    # Initialize logger outside try block for better error handling
    logger = create_logger_for_component('main')
    
    try:
        app = create_app()
        config = app.config.get('APP_CONFIG')
        host, port = HostPortValidator.validate(
            config.HOST if config else None,
            config.PORT if config else None
        )
        logger.info(f"Starting Flask application on {host}:{port}")
        
        # Log ZAP scanner status before starting - use consistent access method
        extensions = getattr(app, 'extensions', {})
        zap_scanner = extensions.get('zap_scanner')
        if zap_scanner:
            logger.info(f"[MAIN] ZAP scanner available: {zap_scanner is not None}")
            if hasattr(zap_scanner, 'is_ready'):
                logger.info(f"[MAIN] ZAP scanner ready: {zap_scanner.is_ready()}")
        else:
            logger.warning("[MAIN] ZAP scanner not found in app.extensions")
        
        # Security: Only enable debug if FLASK_DEBUG env var is set to '1'
        debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
        
        # More flexible host binding - warn but don't override without explicit override flag
        if host == '0.0.0.0' and not os.environ.get('ALLOW_ALL_INTERFACES', '').lower() == 'true':
            logger.warning(
                "Binding to all interfaces (0.0.0.0). "
                "Set ALLOW_ALL_INTERFACES=true to suppress this warning."
            )
        
        app.run(
            host=host,
            port=port,
            debug=debug_mode,
            use_reloader=False,
            threaded=True
        )
        
    except Exception as e:
        logger.exception(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Entry point for running the Flask application
    main()