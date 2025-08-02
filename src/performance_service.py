"""
Performance Analysis Module
==========================

Locust-based performance testing utilities for web applications.
Provides comprehensive performance testing with statistical analysis and reporting.
"""

import json
import os
import re
import subprocess
import importlib
import warnings
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable, TypedDict

# Optional dependencies with graceful fallbacks
try:
    import gevent
    GEVENT_AVAILABLE = True
except ImportError:
    GEVENT_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None

# Import logging service from core_services module
try:
    from core_services import get_logger
    def create_logger_for_component(name: str):
        return get_logger(name)
except ImportError:
    import logging
    def create_logger_for_component(name: str):
        return logging.getLogger(name)

# Import utility functions from core_services module
try:
    from core_services import get_models_base_dir
except ImportError:
    # Fallback implementations
    def get_models_base_dir() -> Path:
        """Fallback implementation for get_models_base_dir."""
        return Path.cwd() / "misc" / "models"

# Optional Locust imports with fallbacks
try:
    from locust import HttpUser, task, between, TaskSet
    from locust.stats import sort_stats, RequestStats
    from locust.env import Environment
    from locust.log import setup_logging
    from locust import events
    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    # Mock classes and functions
    class MockHttpUser:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockRequestStats:
        PERCENTILES_TO_REPORT = [50, 66, 75, 80, 90, 95, 98, 99, 99.9, 99.99, 100]
        def __init__(self, *args, **kwargs):
            self.entries = {}
    
    class MockEnvironment:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockEvents:
        class MockListener:
            def add_listener(self, func):
                return func
        test_start = MockListener()
        test_stop = MockListener()
    
    HttpUser = MockHttpUser
    task = lambda weight=1: lambda func: func
    between = lambda min_val, max_val: lambda: min_val
    TaskSet = MockHttpUser
    sort_stats = lambda entries: []
    RequestStats = MockRequestStats
    Environment = MockEnvironment
    setup_logging = lambda level, formatter: None
    events = MockEvents()

# Add save/load analysis results fallbacks
def save_analysis_results_to_database(model_name: str, app_num: int, analysis_type: str, results: Dict[str, Any]) -> bool:
    """Save performance analysis results to database instead of files."""
    try:
        from models import GeneratedApplication, PerformanceTest, AnalysisStatus
        from extensions import db
        from datetime import datetime
        
        # Find the application
        app = GeneratedApplication.query.filter_by(model_slug=model_name, app_number=app_num).first()
        if not app:
            logger.warning(f"GeneratedApplication not found for {model_name}/app{app_num}")
            return False
        
        # Create or update PerformanceTest record
        perf_test = PerformanceTest.query.filter_by(application_id=app.id, test_type=analysis_type).first()
        if not perf_test:
            perf_test = PerformanceTest()
            perf_test.application_id = app.id
            perf_test.test_type = analysis_type
            db.session.add(perf_test)
        
        # Extract key metrics from results
        perf_test.status = AnalysisStatus.COMPLETED
        perf_test.completed_at = datetime.utcnow()
        
        if not perf_test.started_at:
            perf_test.started_at = datetime.utcnow()
        
        # Extract performance metrics from results
        if isinstance(results, dict):
            stats = results.get('stats', {})
            if stats:
                perf_test.requests_per_second = stats.get('requests_per_second', 0.0)
                perf_test.average_response_time = stats.get('average_response_time', 0.0)
                perf_test.error_rate_percent = stats.get('error_rate_percent', 0.0)
                
            # Resource usage if available
            resource_usage = results.get('resource_usage', {})
            if resource_usage:
                perf_test.cpu_usage_percent = resource_usage.get('cpu_percent', 0.0)
                perf_test.memory_usage_mb = resource_usage.get('memory_mb', 0.0)
            
            # Duration if available
            perf_test.duration_seconds = results.get('duration_seconds', results.get('test_duration', 60))
            
            # Target users if available
            perf_test.target_users = results.get('target_users', results.get('users', 1))
        
        # Store full results
        perf_test.set_results(results)
        
        # Store metadata
        metadata = {
            'model': model_name,
            'app_num': app_num,
            'analysis_type': analysis_type,
            'timestamp': datetime.utcnow().isoformat()
        }
        perf_test.set_metadata(metadata)
        
        db.session.commit()
        logger.info(f"Saved performance analysis results to database for {model_name}/app{app_num}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save performance results to database: {e}")
        try:
            from extensions import db
            db.session.rollback()
        except:
            pass
        return False

def save_analysis_results(model_name: str, app_num: int, analysis_type: str, results: Dict[str, Any], 
                         subfolder: Optional[str] = None) -> Optional[Path]:
    """DEPRECATED: Use save_analysis_results_to_database instead. 
    This function now just calls the database version for compatibility."""
    logger.warning("save_analysis_results is deprecated. Results are now saved to database only.")
    
    # Call the database version
    success = save_analysis_results_to_database(model_name, app_num, analysis_type, results)
    
    # Return a dummy path for backward compatibility
    if success:
        return Path(f"database://{model_name}/app{app_num}/{analysis_type}")
    return None

def load_analysis_results(model_name: str, app_num: int, analysis_type: str, 
                         subfolder: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fallback implementation for loading analysis results"""
    try:
        reports_dir = Path.cwd() / "reports" / model_name / f"app{app_num}"
        if subfolder:
            reports_dir = reports_dir / subfolder
        
        filename = f"{analysis_type}_results.json"
        filepath = reports_dir / filename
        
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return None

# Add get_app_info fallback
try:
    from core_services import get_app_info
except ImportError:
    def get_app_info(model: str, app_num: int) -> Dict[str, Any]:
        """Fallback implementation for get_app_info"""
        return {"status": "unknown", "port": 8000, "backend_port": 8000, "frontend_port": 3000}

# Initialize logger
logger = create_logger_for_component('performance')

# Sandboxed Locust imports to avoid monkey-patching issues
_locust_modules = {}
_locust_available = None

def _import_locust_safely():
    """
    Safely import Locust modules without affecting the main application.
    This prevents SSL monkey-patching issues that can cause RecursionError.
    """
    global _locust_modules, _locust_available
    
    if _locust_available is not None:
        return _locust_available
    
    try:
        # Suppress the monkey-patch warning since we're handling it properly
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            
            # Import Locust modules in a controlled way
            locust_main = importlib.import_module('locust')
            _locust_modules['HttpUser'] = locust_main.HttpUser
            _locust_modules['task'] = locust_main.task
            _locust_modules['events'] = locust_main.events
            _locust_modules['between'] = locust_main.between
            
            # Import environment and stats modules
            env_module = importlib.import_module('locust.env')
            _locust_modules['Environment'] = env_module.Environment
            
            stats_module = importlib.import_module('locust.stats')
            _locust_modules['StatsEntry'] = stats_module.StatsEntry
            _locust_modules['RequestStats'] = stats_module.RequestStats
            _locust_modules['sort_stats'] = stats_module.sort_stats
            
            runners_module = importlib.import_module('locust.runners')
            _locust_modules['Runner'] = runners_module.Runner
            
            _locust_available = True
            logger.info("Locust modules imported successfully in sandboxed mode")
            
    except ImportError as e:
        logger.error(f"Failed to import Locust modules: {e}")
        _locust_available = False
    except Exception as e:
        logger.error(f"Unexpected error importing Locust: {e}")
        _locust_available = False
    
    return _locust_available

def _get_locust_module(name: str):
    """Get a Locust module safely."""
    if not _import_locust_safely():
        raise ImportError(f"Locust not available: {name}")
    return _locust_modules.get(name)

# Initialize logger
logger = create_logger_for_component('performance')


@dataclass
class EndpointStats:
    name: str
    method: str
    num_requests: int = 0
    num_failures: int = 0
    median_response_time: float = 0
    avg_response_time: float = 0
    min_response_time: float = 0
    max_response_time: float = 0
    avg_content_length: float = 0
    current_rps: float = 0
    current_fail_per_sec: float = 0
    percentiles: Dict[str, float] = field(default_factory=dict)


@dataclass
class ErrorStats:
    error_type: str
    count: int
    endpoint: str
    method: str
    description: str = ""


class GraphInfo(TypedDict):
    name: str
    url: str


@dataclass
class PerformanceResult:
    total_requests: int
    total_failures: int
    avg_response_time: float
    median_response_time: float
    requests_per_sec: float
    start_time: str
    end_time: str
    duration: int
    endpoints: List[EndpointStats] = field(default_factory=list)
    errors: List[ErrorStats] = field(default_factory=list)
    percentile_95: float = 0
    percentile_99: float = 0
    user_count: int = 0
    spawn_rate: int = 0
    test_name: str = ""
    host: str = ""
    graph_urls: List[GraphInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['endpoints'] = [asdict(endpoint) for endpoint in self.endpoints]
        result['errors'] = [asdict(error) for error in self.errors]
        result['graph_urls'] = list(self.graph_urls)
        return result

    def save_json(self, file_path: Union[str, Path]) -> None:
        """
        Save the performance result as a JSON file.

        Args:
            file_path: Path to the output JSON file.
        """
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Performance results saved to {file_path}")


class UserGenerator:
    @staticmethod
    def create_http_user(host: str, endpoints: List[Dict[str, Any]]) -> type:
        """
        Dynamically create a Locust HttpUser class with tasks for each endpoint.

        Args:
            host: Target host URL.
            endpoints: List of endpoint configurations.

        Returns:
            A dynamically generated HttpUser subclass.
        """
        # Check if Locust is available
        if not _import_locust_safely():
            logger.warning("Locust not available, creating mock user class")
            # Return a mock class when Locust is not available
            class MockUser:
                def __init__(self):
                    self.host = host
                    self.wait_time = lambda: 2
            return MockUser
            
        # Get Locust classes safely
        try:
            HttpUser = _get_locust_module('HttpUser')
            task = _get_locust_module('task')
            between = _get_locust_module('between')
        except ImportError:
            logger.error("Failed to import Locust modules")
            class MockUser:
                def __init__(self):
                    self.host = host
                    self.wait_time = lambda: 2
            return MockUser
        
        class_attrs = {
            'host': host,
            'wait_time': between(1, 3) if between else lambda: 2
        }

        for i, endpoint in enumerate(endpoints):
            path = endpoint['path']
            method = endpoint.get('method', 'GET').lower()
            weight = endpoint.get('weight', 1)
            ep_name_part = re.sub(r"[^a-zA-Z0-9_]", "_", path.strip('/')).lower()
            if not ep_name_part:
                ep_name_part = "root"
            task_name = endpoint.get('name', f"task_{method}_{ep_name_part}_{i}")

            def create_task_fn(captured_path, captured_method, captured_endpoint_config):
                def task_fn(self):
                    kwargs = {}
                    for param in ['params', 'data', 'json', 'headers', 'files']:
                        if param in captured_endpoint_config:
                            kwargs[param] = captured_endpoint_config[param]

                    request_name = captured_endpoint_config.get('request_name', captured_path)
                    kwargs['name'] = request_name

                    if hasattr(self, 'client'):
                        request_method_func = getattr(self.client, captured_method, None)
                        if request_method_func:
                            with request_method_func(captured_path, catch_response=True, **kwargs) as response:
                                validators = captured_endpoint_config.get('validators')
                                if validators and callable(validators):
                                    try:
                                        validators(response)
                                    except Exception as val_err:
                                        response.failure(f"Validator failed: {val_err}")
                                elif not response.ok:
                                    response.failure(f"HTTP {response.status_code}")
                task_fn.__name__ = task_name
                task_fn.__doc__ = f"Task for {captured_method.upper()} {captured_path}"
                return task_fn

            task_fn_instance = create_task_fn(path, method, endpoint)
            if task:
                decorated_task = task(weight)(task_fn_instance)
            else:
                decorated_task = task_fn_instance
            class_attrs[task_name] = decorated_task

        try:
            DynamicUserClass = type('DynamicHttpUser', (HttpUser,), class_attrs)
        except (TypeError, NameError):
            # Fallback when HttpUser is None or not available
            class DynamicUserClass:
                def __init__(self):
                    for key, value in class_attrs.items():
                        setattr(self, key, value)
                        
        logger.debug(f"Created DynamicHttpUser class with tasks: {list(class_attrs.keys())}")
        return DynamicUserClass


class LocustPerformanceTester:
    def __init__(self, output_dir: Optional[Union[str, Path]] = None, static_url_path: str = "/static"):
        if output_dir is None:
            output_dir = Path("performance_reports")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.static_url_path = "/" + static_url_path.strip('/')
        logger.info(f"PerformanceTester initialized. Output dir: {self.output_dir}, Static URL path: {self.static_url_path}")
        self.current_test_dir: Optional[Path] = None
        self.environment = None
        self.runner = None

    def _save_consolidated_results(self,
                                   result: PerformanceResult,
                                   model: str,
                                   app_num: int) -> str:
        """
        Save performance results using the simple save function from utils.py.
        
        Args:
            result: The performance result to save
            model: Model name
            app_num: Application number
            
        Returns:
            Path to the saved results file
        """
        try:
            # Use the database save function instead of file-based saving
            success = save_analysis_results_to_database(
                model_name=model,
                app_num=app_num,
                analysis_type="performance",
                results=asdict(result)
            )
            if success:
                logger.info(f"Saved consolidated performance results for {model}/app{app_num} to database")
                return f"database://{model}/app{app_num}/performance"
            else:
                logger.error(f"Failed to save performance results for {model}/app{app_num} to database")
                return ""
        except Exception as e:
            logger.exception(f"Error saving consolidated results for {model}/app{app_num}: {e}")
            return ""

    def load_performance_results(self, model: str, app_num: int) -> Optional[PerformanceResult]:
        """
        Load performance test results for a specific model and app number.
        
        Args:
            model: Model name
            app_num: Application number
            
        Returns:
            PerformanceResult object or None if results not found
        """
        try:
            file_name = "performance_results.json"
            data = load_analysis_results(
                model_name=model,
                app_num=app_num,
                analysis_type="performance"
            )
            
            if not data:
                logger.warning(f"No performance results found for {model}/app{app_num}")
                return None
                
            # Convert dictionary back to PerformanceResult object
            result = PerformanceResult(
                total_requests=data.get('total_requests', 0),
                total_failures=data.get('total_failures', 0),
                avg_response_time=data.get('avg_response_time', 0.0),
                median_response_time=data.get('median_response_time', 0.0),
                requests_per_sec=data.get('requests_per_sec', 0.0),
                start_time=data.get('start_time', ''),
                end_time=data.get('end_time', ''),
                duration=data.get('duration', 0),
                user_count=data.get('user_count', 0),
                spawn_rate=data.get('spawn_rate', 0),
                test_name=data.get('test_name', ''),
                host=data.get('host', '')
            )
            
            # Load endpoints
            if 'endpoints' in data:
                result.endpoints = [
                    EndpointStats(**endpoint) for endpoint in data['endpoints']
                ]
            
            # Load errors
            if 'errors' in data:
                result.errors = [
                    ErrorStats(**error) for error in data['errors']
                ]
            
            # Load other fields
            result.percentile_95 = data.get('percentile_95', 0.0)
            result.percentile_99 = data.get('percentile_99', 0.0)
            result.graph_urls = data.get('graph_urls', [])
            
            logger.info(f"Successfully loaded performance results for {model}/app{app_num}")
            return result
        except Exception as e:
            logger.error(f"Error loading performance results for {model}/app{app_num}: {e}")
            return None

    def run_performance_test(self, model: str, app_num: int, force_rerun: bool = False) -> Dict[str, Any]:
        """
        Batch analysis compatible method to run performance test.
        This method provides a simplified interface for batch processing.
        """
        logger.info(f"run_performance_test called for model='{model}', app_num={app_num}")
        
        try:
            # Get app info to determine URL
            app_info = get_app_info(model, app_num)
            if not app_info:
                raise ValueError(f"Could not find app info for {model}/app{app_num}")
            
            # Determine target URL (prefer backend)
            port = app_info.get("backend_port") or app_info.get("frontend_port")
            if not port:
                raise ValueError(f"No port found for {model}/app{app_num}")
            
            host = f"http://localhost:{port}"
            
            # Create default endpoints (basic HTTP tests)
            endpoints = [
                {"path": "/", "method": "GET", "weight": 10},
                {"path": "/api/health", "method": "GET", "weight": 5}
            ]
            
            # Run a simple performance test (reduced load for batch processing)
            result = self.run_test_cli(
                test_name=f"Batch_Test_{model}_app{app_num}",
                host=host,
                endpoints=endpoints,
                user_count=5,  # Light load for batch processing
                spawn_rate=1,
                run_time="30s",  # Short duration
                headless=True,
                model=model,
                app_num=app_num,
                force_rerun=force_rerun
            )
            
            if result:
                # Save results
                self._save_consolidated_results(result, model, app_num)
                
                return {
                    "status": "success",
                    "summary": {
                        "total_requests": result.total_requests,
                        "total_failures": result.total_failures,
                        "avg_response_time": result.avg_response_time,
                        "requests_per_sec": result.requests_per_sec,
                        "duration": result.duration
                    },
                    "result": asdict(result)
                }
            else:
                return {
                    "status": "failed",
                    "summary": {"error": "Performance test returned no results"}
                }
                
        except Exception as e:
            logger.error(f"Error in run_performance_test for {model}/app{app_num}: {e}")
            return {
                "status": "error",
                "summary": {"error": str(e)}
            }
            
    def get_latest_test_result(self, model: str, app_num: int) -> Optional[PerformanceResult]:
        """
        Get the latest test result for a specific model and app number.
        
        Args:
            model: Model name
            app_num: Application number
            
        Returns:
            PerformanceResult object or None if not found
        """
        try:
            return self.load_performance_results(model, app_num)
        except Exception as e:
            logger.error(f"Error getting latest test result for {model}/app{app_num}: {e}")
            return None

    def _setup_test_directory(self, test_name: str) -> Path:
        safe_test_name = re.sub(r'[<>:"/\\|?*\s]+', '_', test_name)
        test_dir = self.output_dir / "performance_reports" / safe_test_name
        test_dir.mkdir(parents=True, exist_ok=True)
        self.current_test_dir = test_dir
        logger.info(f"Test artifacts directory set up at: {test_dir}")
        return test_dir

    def create_user_class(self, host: str, endpoints: List[Dict[str, Any]]) -> type:
        user_class = UserGenerator.create_http_user(host, endpoints)
        return user_class

    def run_test_cli(
        self,
        test_name: str,
        host: str,
        locustfile_path: Optional[str] = None,
        endpoints: Optional[List[Dict[str, Any]]] = None,
        user_count: int = 10,
        spawn_rate: int = 1,
        run_time: str = "30s",
        headless: bool = True,
        workers: int = 0,
        tags: Optional[List[str]] = None,
        html_report: bool = True,
        model: Optional[str] = None,
        app_num: Optional[int] = None,
        force_rerun: bool = False
    ) -> Optional[PerformanceResult]:
        """
        Run a Locust performance test using the CLI.
        
        Args:
            test_name: Name for the test
            host: Target host URL
            locustfile_path: Path to Locust file (optional)
            endpoints: List of endpoint configurations (used if no locustfile_path)
            user_count: Number of users to simulate
            spawn_rate: Rate at which to spawn users
            run_time: Test duration as string (e.g. "30s", "5m")
            headless: Whether to run in headless mode
            workers: Number of worker processes
            tags: Tags to filter tasks
            html_report: Whether to generate HTML report
            model: Optional model name for result organization
            app_num: Optional app number for result organization
            force_rerun: Whether to force rerun the test
            
        Returns:
            PerformanceResult object with test results or None if test fails
        """
        # Check for cached results if model and app_num are provided and not forcing rerun
        if model and app_num and not force_rerun:
            cached_result = self.load_performance_results(model, app_num)
            if cached_result:
                logger.info(f"Using cached performance results for {model}/app{app_num}")
                return cached_result

        # Generate full test name with timestamp if needed
        if not re.search(r'_\d{8}_\d{6}$', test_name):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            full_test_name = f"{test_name}_{timestamp}"
        else:
            full_test_name = test_name

        test_dir = self._setup_test_directory(full_test_name)
        csv_prefix = str(test_dir / "stats")

        temp_locustfile = None
        if not locustfile_path and endpoints:
            try:
                temp_locustfile = self._create_temp_locustfile(host, endpoints, test_dir)
                locustfile_path = temp_locustfile
            except Exception as temp_err:
                logger.error(f"Failed to create temporary locustfile: {temp_err}")
                return None
        elif not locustfile_path:
            logger.error("No locustfile or endpoints provided for CLI test.")
            return None

        try:
            cmd = ["locust", "-f", locustfile_path, "--host", host]
            if headless:
                cmd.extend(["--headless", "--users", str(user_count),
                            "--spawn_rate", str(spawn_rate), "--run-time", run_time])
            else:
                pass

            cmd.extend(["--csv", csv_prefix, "--csv-full-history"])

            if html_report:
                html_file_path = test_dir / f"{test_dir.name}_locust_report.html"
                cmd.extend(["--html", str(html_file_path)])

            if workers > 0:
                cmd.extend(["--master", "--expect-workers", str(workers)])

            if tags:
                cmd.extend(["--tags"] + tags)

            logger.info(f"Running Locust command: {' '.join(cmd)}")
            start_time = datetime.now()

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=False
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Locust process finished in {duration:.2f}s with exit code {process.returncode}")

            output_file = test_dir / "locust_output.txt"
            with open(output_file, "w", encoding='utf-8') as f:
                f.write("--- STDOUT ---\n")
                f.write(process.stdout if process.stdout else "[No stdout]")
                f.write("\n\n--- STDERR ---\n")
                f.write(process.stderr if process.stderr else "[No stderr]")
            logger.info(f"Locust output saved to {output_file}")

            if process.returncode != 0:
                logger.error(f"Locust test failed with exit code {process.returncode}.")
                return None

            stats_file = f"{csv_prefix}_stats.csv"
            failures_file = f"{csv_prefix}_failures.csv"
            history_file = f"{csv_prefix}_stats_history.csv"

            if not Path(stats_file).exists():
                logger.error(f"Locust completed but stats CSV not found: {stats_file}")
                return None

            result = self._parse_csv_results(
                stats_file=stats_file,
                failures_file=failures_file,
                start_time=start_time,
                end_time=end_time,
                user_count=user_count,
                spawn_rate=spawn_rate
            )
            if result is None:
                logger.error("Failed to parse CSV results.")
                return None

            result.test_name = full_test_name
            result.host = host

            graph_infos = self._generate_graphs_from_csv(history_file, test_dir)
            result.graph_urls = graph_infos

            # Save results using the simple save function if model and app_num are provided
            if model and app_num:
                self._save_consolidated_results(result, model, app_num)

            return result
        except FileNotFoundError as e:
            logger.error(f"Locust command not found or file path error: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unhandled error running Locust CLI test '{full_test_name}': {e}")
            return None
        finally:
            if temp_locustfile and os.path.exists(temp_locustfile):
                try:
                    os.unlink(temp_locustfile)
                    logger.debug(f"Deleted temporary locustfile: {temp_locustfile}")
                except Exception as e_unlink:
                    logger.warning(f"Failed to delete temporary file {temp_locustfile}: {e_unlink}")

    def _extract_stats_from_environment(
        self,
        stats,
        start_time: datetime,
        end_time: datetime,
        user_count: int,
        spawn_rate: int
    ) -> PerformanceResult:
        logger.info("Extracting stats directly from Locust environment...")
        
        # Get Locust classes safely
        try:
            sort_stats = _get_locust_module('sort_stats')
            RequestStats = _get_locust_module('RequestStats')
        except ImportError:
            logger.warning("Locust not available, using fallback stats extraction")
            return self._create_fallback_result(start_time, end_time, user_count, spawn_rate)
        
        endpoints: List[EndpointStats] = []
        errors: List[ErrorStats] = []

        try:
            sorted_entries = sort_stats(stats.entries)
            for entry in sorted_entries:
                if entry.name == "Aggregated":
                    continue

                percentiles_dict = {}
                try:
                    if hasattr(RequestStats, 'PERCENTILES_TO_REPORT'):
                        for p in RequestStats.PERCENTILES_TO_REPORT:
                            percentile_value = entry.get_response_time_percentile(p)
                            percentiles_dict[f"{p*100:.0f}"] = percentile_value if percentile_value is not None else 0.0
                except Exception as p_err:
                    logger.warning(f"Could not calculate percentiles for {entry.name}: {p_err}")

                ep_stats = EndpointStats(
                    name=entry.name,
                    method=entry.method or "N/A",
                    num_requests=entry.num_requests,
                    num_failures=entry.num_failures,
                    median_response_time=entry.median_response_time or 0.0,
                    avg_response_time=entry.avg_response_time or 0.0,
                    min_response_time=entry.min_response_time if entry.num_requests > 0 and entry.min_response_time is not None else 0.0,
                    max_response_time=entry.max_response_time or 0.0,
                    avg_content_length=entry.avg_content_length or 0.0,
                    current_rps=entry.current_rps or 0.0,
                    current_fail_per_sec=entry.current_fail_per_sec or 0.0,
                    percentiles=percentiles_dict
                )
                endpoints.append(ep_stats)

            for error_key, error_entry in stats.errors.items():
                err_stats = ErrorStats(
                    error_type=str(error_entry.error),
                    count=error_entry.occurrences,
                    endpoint=error_entry.name or "N/A",
                    method=error_entry.method or "N/A",
                    description=str(error_entry.error)
                )
                errors.append(err_stats)
        except Exception as e:
            logger.error(f"Error extracting stats: {e}")
            return self._create_fallback_result(start_time, end_time, user_count, spawn_rate)

        total_entry = stats.total
        duration_sec = max((end_time - start_time).total_seconds(), 0.1)

        total_p95 = 0.0
        total_p99 = 0.0
        try:
            total_p95 = total_entry.get_response_time_percentile(0.95) or 0.0
            total_p99 = total_entry.get_response_time_percentile(0.99) or 0.0
        except Exception as e:
            logger.warning(f"Could not calculate percentiles for total: {e}")

        result = PerformanceResult(
            total_requests=total_entry.num_requests,
            total_failures=total_entry.num_failures,
            avg_response_time=total_entry.avg_response_time or 0.0,
            median_response_time=total_entry.median_response_time or 0.0,
            requests_per_sec=(total_entry.num_requests / duration_sec),
            start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
            duration=int(duration_sec),
            endpoints=endpoints,
            errors=errors,
            percentile_95=total_p95,
            percentile_99=total_p99,
            user_count=user_count,
            spawn_rate=spawn_rate
        )
        logger.info(f"Stats extraction complete. Total Requests: {result.total_requests}, Failures: {result.total_failures}")
        return result

    def _create_fallback_result(self, start_time: datetime, end_time: datetime, user_count: int, spawn_rate: int) -> PerformanceResult:
        """Create a fallback result when Locust is not available."""
        duration_sec = max((end_time - start_time).total_seconds(), 0.1)
        return PerformanceResult(
            total_requests=0,
            total_failures=0,
            avg_response_time=0.0,
            median_response_time=0.0,
            requests_per_sec=0.0,
            start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
            duration=int(duration_sec),
            endpoints=[],
            errors=[],
            percentile_95=0.0,
            percentile_99=0.0,
            user_count=user_count,
            spawn_rate=spawn_rate
        )

    def run_test_library(
        self,
        test_name: str,
        host: str,
        user_class: Optional[type] = None,
        endpoints: Optional[List[Dict[str, Any]]] = None,
        user_count: int = 10,
        spawn_rate: int = 1,
        run_time: int = 30,
        generate_graphs: bool = True,
        on_start_callback: Optional[Callable[[Any], None]] = None,
        on_stop_callback: Optional[Callable[[Any], None]] = None,
        model: Optional[str] = None,
        app_num: Optional[int] = None,
        force_rerun: bool = False
    ) -> PerformanceResult:
        """
        Run a Locust performance test using the library API.
        
        Args:
            test_name: Name for the test
            host: Target host URL
            user_class: Optional user class for the test
            endpoints: List of endpoint configurations (required if user_class not provided)
            user_count: Number of users to simulate
            spawn_rate: Rate at which to spawn users
            run_time: Test duration in seconds
            generate_graphs: Whether to generate performance graphs
            on_start_callback: Optional callback when test starts
            on_stop_callback: Optional callback when test ends
            model: Optional model name for result organization
            app_num: Optional app number for result organization
            force_rerun: Whether to force rerun the test instead of using cached results
            
        Returns:
            PerformanceResult object with test results
        """
        # Check for cached results if model and app_num are provided and not forcing rerun
        if model and app_num and not force_rerun:
            cached_result = self.load_performance_results(model, app_num)
            if cached_result:
                logger.info(f"Using cached performance results for {model}/app{app_num}")
                return cached_result
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_test_name = f"{test_name}_{timestamp}"
        test_dir = self._setup_test_directory(full_test_name)

        if user_class is None and endpoints:
            user_class = self.create_user_class(host, endpoints)
        if user_class is None:
            raise ValueError("Either user_class or endpoints must be provided")

        # Check if Locust is available
        if not _import_locust_safely():
            logger.warning("Locust not available, creating fallback result")
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=run_time)
            result = self._create_fallback_result(start_time, end_time, user_count, spawn_rate)
            result.test_name = full_test_name
            result.host = host
            
            if model is not None and app_num is not None:
                self._save_consolidated_results(result, model, app_num)
            return result

        # Get Locust classes safely
        try:
            Environment = _get_locust_module('Environment')
            events = _get_locust_module('events')
        except ImportError:
            logger.error("Failed to import Locust modules for test execution")
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=run_time)
            result = self._create_fallback_result(start_time, end_time, user_count, spawn_rate)
            result.test_name = full_test_name
            result.host = host
            
            if model is not None and app_num is not None:
                self._save_consolidated_results(result, model, app_num)
            return result

        self.environment = None
        self.runner = None
        
        try:
            self.environment = Environment(user_classes=[user_class], host=host, catch_exceptions=True)
            self.environment.create_local_runner()
            if not self.environment.runner:
                raise RuntimeError("Failed to create Locust runner.")
            self.runner = self.environment.runner
            self.environment.custom_data = {}

            @events.test_start.add_listener
            def on_test_start(environment, **kwargs):
                environment.custom_data['start_time'] = datetime.now()
                logger.info(f"Test '{full_test_name}' starting at {environment.custom_data['start_time'].isoformat()} with {user_count} users at {spawn_rate} users/s on host {environment.host}")
                if on_start_callback:
                    try:
                        on_start_callback(environment)
                    except Exception as cb_err:
                        logger.error(f"Error in on_start_callback: {cb_err}", exc_info=True)

            @events.test_stop.add_listener
            def on_test_stop(environment, **kwargs):
                logger.info(f"Test '{full_test_name}' stopping...")
                if on_stop_callback:
                    try:
                        on_stop_callback(environment)
                    except Exception as cb_err:
                        logger.error(f"Error in on_stop_callback: {cb_err}", exc_info=True)

            self.runner.start(user_count, spawn_rate=spawn_rate)
            logger.info(f"Locust runner started. Waiting for {run_time} seconds...")

            stopper_greenlet = None
            try:
                if GEVENT_AVAILABLE:
                    import gevent
                    def stopper():
                        gevent.sleep(run_time)
                        logger.info(f"Run time ({run_time}s) elapsed. Stopping runner for test '{full_test_name}'...")
                        if self.runner:
                            self.runner.quit()
                            logger.info("Runner quit signal sent.")
                        else:
                            logger.warning("Stopper executed but runner was None.")
                    stopper_greenlet = gevent.spawn(stopper)
                    self.runner.greenlet.join()
                else:
                    # Fallback without gevent
                    import time
                    time.sleep(run_time)
                    if self.runner:
                        self.runner.quit()
                        
                logger.info("Runner greenlet joined (test run finished).")
            except KeyboardInterrupt:
                logger.warning("Test run interrupted by user (KeyboardInterrupt). Stopping runner...")
                if self.runner: self.runner.quit()
            except Exception as run_err:
                logger.exception(f"Error during runner execution or join for test '{full_test_name}': {run_err}")
                if self.runner: self.runner.quit()
                raise RuntimeError(f"Locust run failed: {run_err}") from run_err
            finally:
                if stopper_greenlet and GEVENT_AVAILABLE:
                    import gevent
                    if not stopper_greenlet.dead:
                        stopper_greenlet.kill(block=False)
                        logger.debug("Stopper greenlet killed.")

            end_time = datetime.now()
            logger.info(f"Test '{full_test_name}' finished execution at {end_time.isoformat()}")
            start_time = self.environment.custom_data.get('start_time')
            if start_time is None:
                logger.warning("Start time not found on environment.custom_data! Using approximate start based on end time and duration.")
                start_time = end_time - timedelta(seconds=run_time)
            else:
                logger.info(f"Actual test start time recorded: {start_time.isoformat()}")

            if not self.environment or not self.environment.stats:
                raise RuntimeError("Locust environment or stats object not available after test run.")

            result = self._extract_stats_from_environment(
                stats=self.environment.stats,
                start_time=start_time,
                end_time=end_time,
                user_count=user_count,
                spawn_rate=spawn_rate
            )
            result.test_name = full_test_name
            result.host = host

            if generate_graphs:
                try:
                    graph_infos = self._generate_graphs_from_history(self.environment.stats.history, test_dir)
                    result.graph_urls = graph_infos
                except Exception as graph_err:
                    logger.error(f"Failed to generate graphs for test '{full_test_name}': {graph_err}", exc_info=True)
                    result.graph_urls = []

            # Save results using the simple save function if model and app_num are provided
            if model is not None and app_num is not None:
                self._save_consolidated_results(result, model, app_num)

            return result
            
        except Exception as e:
            logger.error(f"Error in run_test_library: {e}")
            # Create fallback result
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=run_time)
            result = self._create_fallback_result(start_time, end_time, user_count, spawn_rate)
            result.test_name = full_test_name
            result.host = host
            
            if model is not None and app_num is not None:
                self._save_consolidated_results(result, model, app_num)
            return result
            
        finally:
            self.environment = None
            self.runner = None
            logger.debug("Environment and runner references cleared.")

    def _create_temp_locustfile(self, host: str, endpoints: List[Dict[str, Any]], test_dir: Path) -> str:
        """
        Create a temporary Locustfile for CLI-based tests.

        Args:
            host: Target host URL.
            endpoints: List of endpoint configurations.
            test_dir: Directory to place the temp file.

        Returns:
            Path to the created Locustfile.
        """
        content = f"""# Auto-generated Locustfile for {test_dir.name}
from locust import HttpUser, task, between
import json
class DynamicHttpUser(HttpUser):
    host = \"{host}\"
    wait_time = between(1, 3)
    print(f\"DynamicHttpUser targeting host: {{host}}\")
"""
        for i, endpoint in enumerate(endpoints):
            path = endpoint['path']
            method = endpoint.get('method', 'GET').lower()
            weight = endpoint.get('weight', 1)
            ep_name_part = re.sub(r"[^a-zA-Z0-9_]", "_", path.strip('/')).lower()
            if not ep_name_part:
                ep_name_part = "root"
            func_name = f"task_{method}_{ep_name_part}_{i}"
            request_name = endpoint.get('request_name', path)
            params_list = []
            params_list.append(f'name=\"{request_name}\"')
            params_list.append('catch_response=True')
            if 'params' in endpoint:
                params_list.append(f"params={json.dumps(endpoint['params'])}")
            if 'data' in endpoint:
                params_list.append(f"data={json.dumps(endpoint['data'])}")
            if 'json' in endpoint:
                params_list.append(f"json={json.dumps(endpoint['json'])}")
            if 'headers' in endpoint:
                params_list.append(f"headers={json.dumps(endpoint['headers'])}")
            param_str = ", ".join(params_list)
            task_code = f"""
    @task({weight})
    def {func_name}(self):
        with self.client.{method}(\"{path}\", {param_str}) as response:
            if not response.ok:
                response.failure(f\"HTTP {{response.status_code}}\")
"""
            content += task_code
        locustfile_path = test_dir / f"locustfile_{test_dir.name}.py"
        try:
            with open(locustfile_path, "w", encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Created temporary Locustfile for CLI run at {locustfile_path}")
            return str(locustfile_path)
        except Exception as e:
            logger.error(f"Failed to write temporary locustfile {locustfile_path}: {e}", exc_info=True)
            raise

    def _parse_csv_results(
        self,
        stats_file: str,
        failures_file: str,
        start_time: datetime,
        end_time: datetime,
        user_count: int,
        spawn_rate: int
    ) -> Optional[PerformanceResult]:
        """
        Parse Locust CSV output files to extract performance results.

        Args:
            stats_file: Path to the stats CSV.
            failures_file: Path to the failures CSV.
            start_time: Test start time.
            end_time: Test end time.
            user_count: Number of users.
            spawn_rate: User spawn rate.

        Returns:
            PerformanceResult or None if parsing fails.
        """
        total_requests, total_failures = 0, 0
        avg_response_time, median_response_time, requests_per_sec = 0.0, 0.0, 0.0
        percentile_95, percentile_99 = 0.0, 0.0
        endpoints: List[EndpointStats] = []
        errors: List[ErrorStats] = []
        try:
            stats_path = Path(stats_file)
            if stats_path.exists() and stats_path.stat().st_size > 0:
                if not PANDAS_AVAILABLE:
                    logger.warning("Pandas not available, cannot process CSV data")
                    return PerformanceResult(
                        total_requests=0, total_failures=0, avg_response_time=0.0,
                        median_response_time=0.0, requests_per_sec=0.0, 
                        start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"), 
                        duration=int((end_time - start_time).total_seconds()), 
                        percentile_95=0.0, percentile_99=0.0,
                        endpoints=[], errors=[]
                    )
                    
                import pandas as pd
                df = pd.read_csv(stats_path)
                for _, row in df.iterrows():
                    if row.get('Name') == 'Aggregated':
                        total_requests = int(row.get('Request Count', 0))
                        total_failures = int(row.get('Failure Count', 0))
                        avg_response_time = float(row.get('Average Response Time', 0.0))
                        median_response_time = float(row.get('Median Response Time', 0.0))
                        requests_per_sec = float(row.get('Requests/s', 0.0))
                        percentile_95 = float(row.get('95th Percentile', 0.0))
                        percentile_99 = float(row.get('99th Percentile', 0.0))
                    else:
                        ep = EndpointStats(
                            name=row.get('Name', ''),
                            method=row.get('Method', ''),
                            num_requests=int(row.get('Request Count', 0)),
                            num_failures=int(row.get('Failure Count', 0)),
                            median_response_time=float(row.get('Median Response Time', 0.0)),
                            avg_response_time=float(row.get('Average Response Time', 0.0)),
                            min_response_time=float(row.get('Min Response Time', 0.0)),
                            max_response_time=float(row.get('Max Response Time', 0.0)),
                            avg_content_length=float(row.get('Average Content Size', 0.0)),
                            current_rps=float(row.get('Requests/s', 0.0)),
                            current_fail_per_sec=0.0,
                            percentiles={
                                '95': float(row.get('95th Percentile', 0.0)),
                                '99': float(row.get('99th Percentile', 0.0))
                            }
                        )
                        endpoints.append(ep)
            else:
                logger.error(f"Stats CSV not found or empty: {stats_file}")
                return None
                
            failures_path = Path(failures_file)
            if failures_path.exists() and failures_path.stat().st_size > 0:
                if PANDAS_AVAILABLE:
                    import pandas as pd
                    df_fail = pd.read_csv(failures_path)
                    for _, row in df_fail.iterrows():
                        err = ErrorStats(
                            error_type=row.get('Error', ''),
                            count=int(row.get('Occurrences', 0)),
                            endpoint=row.get('Name', ''),
                            method=row.get('Method', ''),
                            description=row.get('Error', '')
                        )
                        errors.append(err)
                        
            duration = max((end_time - start_time).total_seconds(), 0.1)
            result = PerformanceResult(
                total_requests=total_requests,
                total_failures=total_failures,
                avg_response_time=avg_response_time,
                median_response_time=median_response_time,
                requests_per_sec=requests_per_sec,
                start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                duration=int(duration),
                endpoints=endpoints,
                errors=errors,
                percentile_95=percentile_95,
                percentile_99=percentile_99,
                user_count=user_count,
                spawn_rate=spawn_rate
            )
            return result
        except Exception as csv_err:
            if PANDAS_AVAILABLE:
                import pandas as pd
                if isinstance(csv_err, pd.errors.EmptyDataError):
                    logger.error(f"CSV file is empty: {csv_err}")
                else:
                    logger.error(f"Error parsing CSV results: {csv_err}")
            else:
                logger.error(f"Error parsing CSV results: {csv_err}")
            return None

    def _generate_graphs_from_history(self, history: List[Any], test_dir: Path) -> List[GraphInfo]:
        """
        Generate performance graphs from Locust stats history.

        Args:
            history: List of StatsEntry objects.
            test_dir: Directory to save graphs.

        Returns:
            List of GraphInfo dicts.
        """
        graph_infos: List[GraphInfo] = []
        if not history:
            logger.warning("No stats history provided for graph generation.")
            return graph_infos
        try:
            if not MATPLOTLIB_AVAILABLE:
                logger.warning("matplotlib not installed, skipping graph generation.")
                return graph_infos
                
            import matplotlib.pyplot as plt
            if NUMPY_AVAILABLE:
                import numpy as np
                
            times = [entry.timestamp for entry in history]
            rps = [entry.total_rps for entry in history]
            fig, ax = plt.subplots()
            ax.plot(times, rps, label='Requests per Second')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('RPS')
            ax.set_title('Requests per Second Over Time')
            ax.legend()
            graph_path = test_dir / "rps_over_time.png"
            fig.savefig(str(graph_path))  # Convert Path to string
            plt.close(fig)
            graph_infos.append(GraphInfo(name="RPS Over Time", url=str(graph_path)))
        except ImportError:
            logger.warning("matplotlib not installed, skipping graph generation.")
        except Exception as e:
            logger.error(f"Error generating graphs: {e}")
        return graph_infos

    def _generate_graphs_from_csv(self, history_csv_path: str, test_dir: Path) -> List[GraphInfo]:
        """
        Generate performance graphs from Locust history CSV.

        Args:
            history_csv_path: Path to the history CSV.
            test_dir: Directory to save graphs.

        Returns:
            List of GraphInfo dicts.
        """
        graph_infos: List[GraphInfo] = []
        history_file = Path(history_csv_path)
        if not history_file.exists() or history_file.stat().st_size == 0:
            logger.warning(f"History CSV not found or empty: {history_csv_path}")
            return []
        try:
            if not MATPLOTLIB_AVAILABLE or not PANDAS_AVAILABLE:
                logger.warning("matplotlib or pandas not installed; skipping graph generation.")
                return []
                
            import matplotlib.pyplot as plt
            import pandas as pd
            
            df = pd.read_csv(history_file)
            if 'Timestamp' not in df.columns or 'Requests/s' not in df.columns:
                logger.warning(f"History CSV missing required columns.")
                return []
            plt.figure(figsize=(10, 6))
            plt.plot(df['Timestamp'], df['Requests/s'], label='Requests/s')
            plt.xlabel('Timestamp')
            plt.ylabel('Requests/s')
            plt.title('Requests per Second Over Time')
            plt.legend()
            graph_path = test_dir / 'requests_per_sec.png'
            plt.savefig(str(graph_path))  # Convert Path to string
            plt.close()
            graph_infos.append({'name': 'Requests/s', 'url': str(graph_path)})
            return graph_infos
        except ImportError:
            logger.warning("matplotlib or pandas not installed; skipping graph generation.")
            return []
        except Exception as csv_err:
            if PANDAS_AVAILABLE:
                import pandas as pd
                if isinstance(csv_err, pd.errors.EmptyDataError):
                    logger.warning(f"History CSV is empty: {history_csv_path}")
                else:
                    logger.error(f"Error generating graphs from CSV: {csv_err}")
            else:
                logger.error(f"Error generating graphs from CSV: {csv_err}")
            return []

    def get_performance_summary(self, result: PerformanceResult) -> Dict[str, Any]:
        """
        Generate a summary of performance test results.
        
        Args:
            result: PerformanceResult object
            
        Returns:
            Dictionary with summary information
        """
        # Get models base directory from utils
        models_base_dir = get_models_base_dir()
        
        summary = {
            "total_requests": result.total_requests,
            "total_failures": result.total_failures,
            "failure_rate": round((result.total_failures / result.total_requests * 100) if result.total_requests else 0, 2),
            "avg_response_time": round(result.avg_response_time, 2),
            "median_response_time": round(result.median_response_time, 2),
            "percentile_95": round(result.percentile_95, 2),
            "percentile_99": round(result.percentile_99, 2),
            "requests_per_sec": round(result.requests_per_sec, 2),
            "user_count": result.user_count,
            "duration": result.duration,
            "test_name": result.test_name,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "results_path": str(models_base_dir),  # Add models base directory path
            "top_endpoints": [],
            "error_count": len(result.errors),
            "scan_time": datetime.now().isoformat()
        }
        
        # Add top 5 endpoints by request count
        sorted_endpoints = sorted(result.endpoints, key=lambda e: e.num_requests, reverse=True)
        summary["top_endpoints"] = [
            {
                "name": endpoint.name,
                "method": endpoint.method,
                "requests": endpoint.num_requests,
                "failures": endpoint.num_failures,
                "avg_response_time": round(endpoint.avg_response_time, 2)
            }
            for endpoint in sorted_endpoints[:5]
        ]
        
        # Add performance rating based on response time and failure rate
        if result.avg_response_time < 100 and summary["failure_rate"] < 1:
            summary["performance_rating"] = "Excellent"
        elif result.avg_response_time < 300 and summary["failure_rate"] < 5:
            summary["performance_rating"] = "Good"
        elif result.avg_response_time < 1000 and summary["failure_rate"] < 10:
            summary["performance_rating"] = "Fair"
        else:
            summary["performance_rating"] = "Poor"
            
        return summary