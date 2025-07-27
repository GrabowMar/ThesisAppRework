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
import gevent
import pandas as pd
import importlib
import warnings
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable, TypedDict

from logging_service import create_logger_for_component
from utils import save_analysis_results, load_analysis_results, get_models_base_dir

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


@dataclass
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
        # Get Locust classes safely
        HttpUser = _get_locust_module('HttpUser')
        task = _get_locust_module('task')
        between = _get_locust_module('between')
        
        class_attrs = {
            'host': host,
            'wait_time': between(1, 3)
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

                    request_method_func = getattr(self.client, captured_method)
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
            decorated_task = task(weight)(task_fn_instance)
            class_attrs[task_name] = decorated_task

        DynamicUserClass = type('DynamicHttpUser', (HttpUser,), class_attrs)
        logger.debug(f"Created DynamicHttpUser class with tasks: {list(class_attrs.keys())}")
        return DynamicUserClass


class LocustPerformanceTester:
    def __init__(self, output_dir: Union[str, Path], static_url_path: str = "/static"):
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
            # Use the simple save_analysis_results function from utils.py
            file_name = "performance_results.json"
            results_path = save_analysis_results(
                model=model,
                app_num=app_num,
                results=result,
                filename=file_name
            )
            logger.info(f"Saved consolidated performance results for {model}/app{app_num}")
            return str(results_path)
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
                model=model,
                app_num=app_num,
                filename=file_name
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

    def run_performance_test(self, model: str, app_num: int) -> Dict[str, Any]:
        """
        Batch analysis compatible method to run performance test.
        This method provides a simplified interface for batch processing.
        """
        logger.info(f"run_performance_test called for model='{model}', app_num={app_num}")
        
        try:
            # Get app info to determine URL
            from utils import get_app_info
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
            result = self.run_test_library(
                host=host,
                user_count=5,  # Light load for batch processing
                spawn_rate=1,
                test_duration_seconds=30,  # Short duration
                endpoints=endpoints,
                test_name=f"Batch_Test_{model}_app{app_num}"
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
            
    def get_latest_test_result(self, model: str, port: int) -> Optional[PerformanceResult]:
        """
        Get the latest test result for a specific model and port.
        
        Args:
            model: Model name
            port: Application port
            
        Returns:
            PerformanceResult object or None if not found
        """
        try:
            # Determine app_num from port
            from utils import get_app_info
            app_info = get_app_info(port)
            if not app_info or 'app_num' not in app_info:
                logger.warning(f"Could not determine app_num from port {port}")
                return None
                
            app_num = app_info['app_num']
            return self.load_performance_results(model, app_num)
        except Exception as e:
            logger.error(f"Error getting latest test result for {model}/port{port}: {e}")
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
        sort_stats = _get_locust_module('sort_stats')
        RequestStats = _get_locust_module('RequestStats')
        
        endpoints: List[EndpointStats] = []
        errors: List[ErrorStats] = []

        sorted_entries = sort_stats(stats.entries)
        for entry in sorted_entries:
            if entry.name == "Aggregated":
                continue

            percentiles_dict = {}
            try:
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

        total_entry = stats.total
        duration_sec = max((end_time - start_time).total_seconds(), 0.1)

        total_p95 = total_entry.get_response_time_percentile(0.95) or 0.0
        total_p99 = total_entry.get_response_time_percentile(0.99) or 0.0

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

        # Get Locust classes safely
        Environment = _get_locust_module('Environment')
        events = _get_locust_module('events')

        self.environment = None
        self.runner = None
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
            logger.info("Runner greenlet joined (test run finished).")
        except KeyboardInterrupt:
            logger.warning("Test run interrupted by user (KeyboardInterrupt). Stopping runner...")
            if self.runner: self.runner.quit()
        except Exception as run_err:
            logger.exception(f"Error during runner execution or join for test '{full_test_name}': {run_err}")
            if self.runner: self.runner.quit()
            raise RuntimeError(f"Locust run failed: {run_err}") from run_err
        finally:
            if stopper_greenlet and not stopper_greenlet.dead:
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

        self.environment = None
        self.runner = None
        logger.debug("Environment and runner references cleared.")
        logger.info(f"Returning results for test {full_test_name}")
        return result

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
        except pd.errors.EmptyDataError as e:
            logger.error(f"CSV file is empty: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing CSV results: {e}")
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
            import matplotlib.pyplot as plt
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
            fig.savefig(graph_path)
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
            import matplotlib.pyplot as plt
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
            plt.savefig(graph_path)
            plt.close()
            graph_infos.append({'name': 'Requests/s', 'url': str(graph_path)})
            return graph_infos
        except ImportError:
            logger.warning("matplotlib not installed; skipping graph generation.")
            return []
        except pd.errors.EmptyDataError:
            logger.warning(f"History CSV is empty: {history_csv_path}")
            return []
        except Exception as e:
            logger.error(f"Error generating graphs from CSV: {e}")
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