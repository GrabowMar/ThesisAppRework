"""
ZAP Scanner Module
=================

OWASP ZAP integration for web application security scanning.
Simplified version that works reliably.
"""

import json
import logging
import os
import re
import socket
import subprocess
import time
import shutil
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import requests
try:
    from zapv2 import ZAPv2
except ImportError:
    try:
        from zaproxy import ZAPv2
    except ImportError:
        # Create a mock ZAPv2 class if no ZAP library is available
        class ZAPv2:
            def __init__(self, *args, **kwargs):
                pass

# Import the simple analysis functions from core_services
try:
    from core_services import save_analysis_results, load_analysis_results, get_app_info
except ImportError:
    # Fallback implementations
    def save_analysis_results(*args, **kwargs):
        pass
    def load_analysis_results(*args, **kwargs):
        return None
    def get_app_info(*args, **kwargs):
        return None

# Import logging service from core_services module
try:
    from core_services import create_logger_for_component
except ImportError:
    import logging
    def create_logger_for_component(name):
        return logging.getLogger(name)

# Initialize logger
logger = create_logger_for_component('zap_scanner')


# Configuration Management
class ZAPConfig:
    """Centralized configuration for ZAP scanner."""
    DEFAULT_API_KEY = os.getenv('ZAP_API_KEY', '5tjkc409k4oaacd69qob5p6uri')
    DEFAULT_MAX_SCAN_DURATION = int(os.getenv('ZAP_MAX_SCAN_DURATION', '120'))
    DEFAULT_AJAX_TIMEOUT = int(os.getenv('ZAP_AJAX_TIMEOUT', '180'))
    DEFAULT_THREAD_COUNT = 8
    DEFAULT_MAX_CHILDREN = 30
    DEFAULT_HEAP_SIZE = '2G'  # Reduced from 6G to 2G for better compatibility
    DEFAULT_PORT_RANGE = (8090, 8099)
    CONNECTION_TIMEOUT = 60  # Added missing constant
    
    SOURCE_CODE_EXTENSIONS = [
        '.js', '.jsx', '.ts', '.tsx', '.php', '.py',
        '.java', '.html', '.css'
    ]


# Data Models (keep the same)
@dataclass
class CodeContext:
    snippet: str
    line_number: Optional[int] = None
    file_path: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    vulnerable_lines: List[int] = field(default_factory=list)
    highlight_positions: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class ZapVulnerability:
    url: str
    name: str
    alert: str
    risk: str
    confidence: str
    description: str
    solution: str
    reference: str
    evidence: Optional[str] = None
    cwe_id: Optional[str] = None
    parameter: Optional[str] = None
    attack: Optional[str] = None
    wascid: Optional[str] = None
    affected_code: Optional[CodeContext] = None
    source_file: Optional[str] = None


@dataclass
class ScanStatus:
    status: str = "Not Started"
    progress: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    spider_progress: int = 0
    passive_progress: int = 0
    active_progress: int = 0
    ajax_progress: int = 0
    phase: str = "Not Started"
    current_operation: str = ""
    urls_found: int = 0
    alerts_found: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    error_count: int = 0
    warning_count: int = 0


# Utility Functions
def log_operation(operation_name: str):
    """Decorator for logging operation start/end with consistent formatting."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"Starting {operation_name}...")
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"Completed {operation_name} in {elapsed:.2f} seconds")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"Failed {operation_name} after {elapsed:.2f} seconds: {str(e)}")
                raise
        return wrapper
    return decorator


class NetworkUtils:
    """Utility class for network operations."""
    
    @staticmethod
    def find_free_port(start_port: int, max_port: int) -> int:
        """Find a free port within the specified range."""
        logger.debug(f"Searching for free port between {start_port} and {max_port}...")
        for port in range(start_port, max_port + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(('127.0.0.1', port))
                    logger.info(f"Found free port: {port}")
                    return port
            except OSError:
                continue
        raise RuntimeError(f"No free ports found between {start_port} and {max_port}")
    
    @staticmethod
    def wait_for_service(host: str, port: int, timeout: int = 30) -> bool:
        """Wait for a service to become available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1.0)
                    result = sock.connect_ex((host, port))
                    if result == 0:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False


# Simplified ZAP Daemon Management
class ZAPDaemonManager:
    """Simplified ZAP daemon lifecycle management."""
    
    def __init__(self, base_path: Path, config: ZAPConfig):
        self.base_path = base_path
        self.config = config
        self.api_key = config.DEFAULT_API_KEY
        self.proxy_host = "127.0.0.1"
        self.proxy_port = None
        self.zap_log = self.base_path / "zap.log"
        self.daemon_process: Optional[subprocess.Popen] = None
        self.zap: Optional[ZAPv2] = None
        self._is_ready = False

    def _find_zap_installation(self) -> Path:
        """Find ZAP installation path."""
        zap_home = os.getenv("ZAP_HOME")
        possible_paths = [
            self.base_path / "ZAP_2.14.0",
            self.base_path / "ZAP_2.15.0",
            self.base_path,
            Path(zap_home) if zap_home else None,
            Path("C:/Program Files/OWASP/Zed Attack Proxy"),
            Path("C:/Program Files (x86)/OWASP/Zed Attack Proxy"),
            Path("C:/Program Files/ZAP/Zed Attack Proxy"),
            Path("/usr/share/zaproxy"),
            Path("/opt/zaproxy"),
            Path("/Applications/OWASP ZAP.app/Contents/Java"),
        ]
        
        for path in filter(None, possible_paths):
            if not path.exists():
                continue
                
            # Look for JAR files first
            jar_files = list(path.glob("zap*.jar"))
            if jar_files:
                logger.info(f"Found ZAP JAR at: {jar_files[0]}")
                return jar_files[0]
                
            # Look for executables
            for exe in ["zap.bat", "zap.sh", "zap.exe", "zap"]:
                exe_path = path / exe
                if exe_path.exists():
                    logger.info(f"Found ZAP executable at: {exe_path}")
                    return exe_path
        
        raise FileNotFoundError("ZAP installation not found. Please install ZAP and set ZAP_HOME environment variable.")

    def _get_simple_java_opts(self) -> List[str]:
        """Get simplified Java options for ZAP."""
        return [
            f'-Xmx{self.config.DEFAULT_HEAP_SIZE}',
            '-Djava.awt.headless=true',
        ]

    def _get_simple_zap_args(self) -> List[str]:
        """Get simplified ZAP command line arguments."""
        return [
            '-daemon',
            '-port', str(self.proxy_port),
            '-host', self.proxy_host,
            '-config', f'api.key={self.api_key}',
            '-config', 'api.addrs.addr.name=.*',
            '-config', 'api.addrs.addr.regex=true',
        ]

    @log_operation("ZAP daemon startup")
    def start_daemon(self) -> bool:
        """Start ZAP daemon with simplified approach."""
        try:
            # Clean up any existing processes first
            self._cleanup_existing_processes()
            
            # Find free port
            self.proxy_port = NetworkUtils.find_free_port(
                self.config.DEFAULT_PORT_RANGE[0],
                self.config.DEFAULT_PORT_RANGE[1]
            )
            
            # Create temp directory
            (self.base_path / "tmp").mkdir(parents=True, exist_ok=True)
            
            # Find ZAP
            zap_path = self._find_zap_installation()
            
            # Build command
            java_opts = self._get_simple_java_opts()
            zap_args = self._get_simple_zap_args()
            
            if zap_path.suffix == '.jar':
                cmd = ['java'] + java_opts + ['-jar', str(zap_path)] + zap_args
            else:
                cmd = [str(zap_path)] + zap_args
            
            logger.info(f"Starting ZAP daemon on port {self.proxy_port}")
            logger.debug(f"Command: {' '.join(cmd)}")
            
            # Start process
            with open(self.zap_log, 'w') as log_file:
                self.daemon_process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=str(self.base_path)
                )
            
            # Wait for ZAP to be ready
            logger.info("Waiting for ZAP to initialize...")
            if not NetworkUtils.wait_for_service(self.proxy_host, self.proxy_port, timeout=60):
                raise RuntimeError("ZAP failed to start within 60 seconds")
            
            # Additional stabilization time
            time.sleep(5)
            
            # Connect to API
            self._connect_to_api()
            
            self._is_ready = True
            logger.info(f"ZAP daemon started successfully on port {self.proxy_port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start ZAP daemon: {str(e)}")
            self._cleanup_existing_processes()
            return False

    def _connect_to_api(self):
        """Connect to ZAP API."""
        logger.info("Connecting to ZAP API...")
        
        self.zap = ZAPv2(
            apikey=self.api_key,
            proxies={
                'http': f'http://{self.proxy_host}:{self.proxy_port}',
                'https': f'http://{self.proxy_host}:{self.proxy_port}'
            }
        )
        
        # Test connection
        version = self.zap.core.version
        logger.info(f"Successfully connected to ZAP {version}")

    def _cleanup_existing_processes(self):
        """Clean up existing ZAP processes."""
        try:
            if self.daemon_process:
                logger.info("Terminating existing ZAP process...")
                self.daemon_process.terminate()
                try:
                    self.daemon_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.daemon_process.kill()
                    self.daemon_process.wait()
                self.daemon_process = None
            
            # Kill any orphaned ZAP processes
            if os.name == 'nt':
                subprocess.run(['taskkill', '/f', '/im', 'java.exe'], capture_output=True, check=False)
                subprocess.run(['taskkill', '/f', '/im', 'zap.exe'], capture_output=True, check=False)
            else:
                subprocess.run(['pkill', '-f', 'zap'], capture_output=True, check=False)
            
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Error during cleanup: {str(e)}")

    def cleanup(self):
        """Clean up ZAP daemon."""
        self._is_ready = False
        self._cleanup_existing_processes()
        self.zap = None

    def is_ready(self) -> bool:
        """Check if ZAP daemon is ready."""
        return self._is_ready and self.zap is not None


# Simplified Code Analyzer
class CodeAnalyzer:
    """Simplified code analysis."""
    
    def __init__(self, config: ZAPConfig):
        self.config = config
        self.source_root_dir = None

    def set_source_code_root(self, root_dir: str):
        """Set the root directory for source code."""
        if os.path.isdir(root_dir):
            self.source_root_dir = root_dir
            logger.info(f"Source code root directory set to: {root_dir}")

    def get_affected_code(self, alert: Dict[str, Any], zap: ZAPv2) -> Optional[CodeContext]:
        """Extract affected code context from alert - simplified version."""
        evidence = alert.get('evidence', '')
        if not evidence:
            return None
            
        # Just return the evidence as context for now
        return CodeContext(
            snippet=evidence,
            line_number=None,
            file_path=None,
            highlight_positions=[(0, len(evidence))]
        )


# Simplified Report Generator
class ReportGenerator:
    """Simplified report generation."""
    
    @log_operation("Report generation")
    def generate_affected_code_report(self, vulnerabilities: List[ZapVulnerability], output_file: str = None) -> str:
        """Generate simple vulnerability report."""
        report = ["# Security Vulnerability Report\n"]
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Group by risk
        by_risk = {"High": [], "Medium": [], "Low": [], "Informational": []}
        for vuln in vulnerabilities:
            risk = "Informational" if vuln.risk == "Info" else vuln.risk
            if risk in by_risk:
                by_risk[risk].append(vuln)
        
        # Summary
        report.append("## Summary\n")
        for risk, vulns in by_risk.items():
            if vulns:
                report.append(f"- **{risk}**: {len(vulns)} vulnerabilities\n")
        
        # Details
        for risk in ["High", "Medium", "Low", "Informational"]:
            vulns = by_risk[risk]
            if not vulns:
                continue
                
            report.append(f"\n## {risk} Risk Vulnerabilities\n")
            for i, vuln in enumerate(vulns, 1):
                report.append(f"### {i}. {vuln.name}\n")
                report.append(f"- **URL**: {vuln.url}\n")
                report.append(f"- **Confidence**: {vuln.confidence}\n")
                if vuln.parameter:
                    report.append(f"- **Parameter**: {vuln.parameter}\n")
                report.append(f"- **Description**: {vuln.description}\n")
                report.append(f"- **Solution**: {vuln.solution}\n")
                if vuln.evidence:
                    report.append(f"\n#### Evidence\n```\n{vuln.evidence}\n```\n")
                report.append("\n---\n")
        
        content = '\n'.join(report)
        
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Report saved to: {output_file}")
        
        return content


# Main ZAP Scanner Class - Simplified
class ZAPScanner:
    """Simplified ZAP scanner."""
    
    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.config = ZAPConfig()
        self.daemon_manager = ZAPDaemonManager(self.base_path, self.config)
        self.code_analyzer = CodeAnalyzer(self.config)
        self.report_generator = ReportGenerator()
        self._scans: Dict[str, Dict] = {}
        
        # Scan settings
        self.max_children = 10  # Reduced for stability
        self.scan_recursively = True
        self.max_scan_duration_minutes = self.config.DEFAULT_MAX_SCAN_DURATION
        self.thread_per_host = 2  # Reduced for stability
        
        logger.info(f"ZAPScanner initialized with base path: {self.base_path}")

    @property
    def zap(self) -> Optional[ZAPv2]:
        """Get ZAP API client."""
        return self.daemon_manager.zap

    def is_ready(self) -> bool:
        """Check if scanner is ready."""
        return self.daemon_manager.is_ready()

    def is_available(self) -> bool:
        """Check if ZAP scanner is available for use."""
        try:
            # Check if zapv2 module is available
            import zapv2
            
            # Check if ZAP daemon can be started or is already running
            if self.daemon_manager.is_ready():
                return True
                
            # Try to start daemon to test availability
            return self.daemon_manager.start_daemon()
        except ImportError:
            logger.warning("ZAP scanner not available: zapv2 module not found")
            return False
        except Exception as e:
            logger.warning(f"ZAP scanner not available: {e}")
            return False

    def set_source_code_root(self, root_dir: str):
        """Set the root directory for source code."""
        self.code_analyzer.set_source_code_root(root_dir)

    def _get_target_url(self, model: str, app_num: int) -> str:
        """Get the correct app URL using get_app_info, preferring backend_port if available."""
        logger.info(f"Getting target URL for model='{model}', app_num={app_num}")
        
        app_info = get_app_info(model, app_num)
        if app_info:
            logger.info(f"Found app_info: {app_info}")
            # Prefer backend_port if present, else frontend_port
            port = app_info.get("backend_port") or app_info.get("frontend_port")
            if port:
                target_url = f"http://localhost:{port}"
                logger.info(f"Using port {port}, target URL: {target_url}")
                return target_url
                
        logger.error(f"No app_info found for model='{model}', app_num={app_num}")
        raise ValueError(f"Could not determine app port for model={model}, app_num={app_num}")

    @log_operation("ZAP Scan")
    def start_scan(self, model: str, app_num: int, quick_scan: bool = False) -> bool:
        """Start a simplified ZAP scan."""
        scan_key = f"{model}-{app_num}"
        scan_status = ScanStatus(start_time=datetime.now().isoformat())
        
        logger.info(f"Starting ZAP scan for model='{model}', app_num={app_num}, quick_scan={quick_scan}")
        
        # Calculate target URL using shared utility
        try:
            target_url = self._get_target_url(model, app_num)
            logger.info(f"Target URL calculated: {target_url}")
        except Exception as e:
            logger.error(f"Failed to determine target URL for {model}/app{app_num}: {e}")
            scan_status.status = f"Failed: {e}"
            return False
        
        # Set source code root
        try:
            # Try to import from main module first
            try:
                from core_services import get_models_base_dir
            except ImportError:
                # Fallback to default path
                from pathlib import Path
                def get_models_base_dir():
                    return Path.cwd() / "misc" / "models"
                    
            models_base_dir = get_models_base_dir()
            app_path = models_base_dir / f"{model}/app{app_num}"
            if app_path.exists():
                self.set_source_code_root(str(app_path))
        except Exception as e:
            logger.warning(f"Could not set source code root: {e}")
        
        # Initialize scan data
        self._scans[scan_key] = {
            "status": scan_status,
            "target_url": target_url,
            "start_time": datetime.now().isoformat()
        }
        
        logger.info(f"Starting scan {scan_key} for {target_url}")
        
        try:
            scan_status.status = "Running"
            
            # Ensure daemon is started
            if not self.daemon_manager.is_ready():
                logger.info("Starting ZAP daemon...")
                if not self.daemon_manager.start_daemon():
                    raise RuntimeError("Failed to start ZAP daemon")
            
            # Run scan
            vulnerabilities, summary = self._execute_simplified_scan(target_url, scan_status)
            
            # Save results
            self.save_scan_results(model, app_num, vulnerabilities, summary)
            
            # Update status
            scan_status.status = "Complete"
            scan_status.progress = 100
            scan_status.end_time = datetime.now().isoformat()
            
            logger.info(f"Scan {scan_key} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Scan failed: {str(e)}")
            scan_status.status = f"Failed: {str(e)}"
            scan_status.end_time = datetime.now().isoformat()
            return False
        finally:
            # Always cleanup after scan
            self.daemon_manager.cleanup()

    def _execute_simplified_scan(self, target_url: str, scan_status: ScanStatus) -> Tuple[List[ZapVulnerability], Dict]:
        """Execute simplified scan process."""
        scan_start_time = datetime.now()
        
        try:
            # Access target
            logger.info(f"Accessing target URL: {target_url}")
            scan_status.phase = "Initial Access"
            self.zap.core.access_url(target_url, followredirects=True)
            time.sleep(2)
            
            # Spider scan
            logger.info("Starting spider scan...")
            scan_status.phase = "Spider Scanning"
            spider_id = self.zap.spider.scan(url=target_url, maxchildren=self.max_children)
            
            # Monitor spider
            while int(self.zap.spider.status(spider_id)) < 100:
                progress = int(self.zap.spider.status(spider_id))
                scan_status.spider_progress = progress
                scan_status.progress = progress // 3  # Spider is 1/3 of total
                logger.info(f"Spider progress: {progress}%")
                time.sleep(2)
            
            # Wait for passive scan
            logger.info("Waiting for passive scan...")
            scan_status.phase = "Passive Scanning"
            time.sleep(5)
            
            while int(self.zap.pscan.records_to_scan) > 0:
                remaining = int(self.zap.pscan.records_to_scan)
                logger.info(f"Passive scan - {remaining} records remaining")
                scan_status.passive_progress = 100 - min(remaining, 100)
                scan_status.progress = 33 + (scan_status.passive_progress // 3)
                time.sleep(2)
            
            # Active scan
            logger.info("Starting active scan...")
            scan_status.phase = "Active Scanning"
            scan_id = self.zap.ascan.scan(url=target_url, recurse=True)
            
            # Monitor active scan
            while int(self.zap.ascan.status(scan_id)) < 100:
                progress = int(self.zap.ascan.status(scan_id))
                scan_status.active_progress = progress
                scan_status.progress = 66 + (progress // 3)
                logger.info(f"Active scan progress: {progress}%")
                time.sleep(5)
            
            # Get results
            logger.info("Retrieving results...")
            scan_status.phase = "Processing Results"
            alerts = self.zap.core.alerts(baseurl=target_url)
            
            # Process alerts
            vulnerabilities = []
            for alert in alerts:
                vuln = ZapVulnerability(
                    url=alert.get('url', ''),
                    name=alert.get('name', ''),
                    alert=alert.get('alert', ''),
                    risk=alert.get('risk', ''),
                    confidence=alert.get('confidence', ''),
                    description=alert.get('description', ''),
                    solution=alert.get('solution', ''),
                    reference=alert.get('reference', ''),
                    evidence=alert.get('evidence'),
                    cwe_id=alert.get('cweid'),
                    parameter=alert.get('param'),
                    attack=alert.get('attack'),
                    wascid=alert.get('wascid')
                )
                vulnerabilities.append(vuln)
                
                # Update counts
                if vuln.risk == "High":
                    scan_status.high_count += 1
                elif vuln.risk == "Medium":
                    scan_status.medium_count += 1
                elif vuln.risk == "Low":
                    scan_status.low_count += 1
                else:
                    scan_status.info_count += 1
            
            # Create summary
            end_time = datetime.now()
            duration = int((end_time - scan_start_time).total_seconds())
            
            summary = {
                "status": "success",
                "start_time": scan_start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "total_alerts": len(vulnerabilities),
                "high": scan_status.high_count,
                "medium": scan_status.medium_count,
                "low": scan_status.low_count,
                "info": scan_status.info_count
            }
            
            return vulnerabilities, summary
            
        except Exception as e:
            logger.error(f"Scan error: {str(e)}")
            return [], {"status": "failed", "error": str(e)}

    def get_scan_status(self, model: str, app_num: int) -> Optional[ScanStatus]:
        """Get current scan status."""
        scan_key = f"{model}-{app_num}"
        scan_info = self._scans.get(scan_key)
        return scan_info["status"] if scan_info else None

    def stop_scan(self, model: str = None, app_num: int = None) -> bool:
        """Stop a running scan."""
        try:
            if self.zap:
                self.zap.spider.stop_all_scans()
                self.zap.ascan.stop_all_scans()
            
            if model and app_num:
                scan_key = f"{model}-{app_num}"
                if scan_key in self._scans:
                    self._scans[scan_key]["status"].status = "Stopped"
            
            return True
        except Exception as e:
            logger.error(f"Error stopping scan: {e}")
            return False

    def save_scan_results(self, model: str, app_num: int, vulnerabilities: List[ZapVulnerability], 
                         summary: Dict[str, Any]):
        """Save scan results."""
        try:
            # Convert to dict for JSON
            results = {
                "alerts": [asdict(v) for v in vulnerabilities],
                "summary": summary,
                "scan_time": datetime.now().isoformat()
            }
            
            # Log detailed information about what's being saved
            logger.info(f"Saving ZAP scan results for model='{model}', app_num={app_num}")
            logger.info(f"Number of vulnerabilities: {len(vulnerabilities)}")
            logger.info(f"Summary: {summary}")
            
            # Save using utils
            save_analysis_results(
                model=model,
                app_num=app_num,
                results=results,
                filename="zap_results.json"
            )
            
            # Generate report
            report_path = f"zap_reports/{model}/app{app_num}/zap_code_report.md"
            self.report_generator.generate_affected_code_report(vulnerabilities, report_path)
            
            logger.info(f"Successfully saved scan results for {model}/app{app_num}")
            
        except Exception as e:
            logger.error(f"Error saving scan results for {model}/app{app_num}: {e}")
            raise

    def run_zap_scan(self, model: str, app_num: int, scan_type: str = "spider") -> dict:
        """
        Run ZAP scan compatible with web routes interface.
        This method provides the interface expected by web_routes.py.
        """
        logger.info(f"run_zap_scan called for model='{model}', app_num={app_num}, scan_type='{scan_type}'")
        
        try:
            # Use the existing scan_app method
            result = self.scan_app(model, app_num)
            
            # Transform result to match expected web interface format
            if result.get("status") == "success":
                return {
                    'success': True,
                    'data': {
                        'vulnerabilities': result.get("issues", []),
                        'scan_type': scan_type,
                        'scan_time': result.get("scan_time"),
                        'summary': result.get("summary", {})
                    }
                }
            else:
                return {
                    'success': False,
                    'error': result.get("summary", {}).get("error", "ZAP scan failed"),
                    'scan_type': scan_type
                }
                
        except Exception as e:
            logger.error(f"Error in run_zap_scan for {model}/app{app_num}: {e}")
            return {
                'success': False,
                'error': str(e),
                'scan_type': scan_type
            }

    def scan_app(self, model: str, app_num: int) -> Dict[str, Any]:
        """
        Batch analysis compatible method to scan an app.
        This method bridges the batch analysis interface with the existing start_scan method.
        """
        logger.info(f"scan_app called for model='{model}', app_num={app_num}")
        
        try:
            # Start the scan
            success = self.start_scan(model, app_num)
            
            if success:
                # Try to load the saved results
                try:
                    results = load_analysis_results(model, app_num, "zap_results.json")
                    if results:
                        return {
                            "status": "success",
                            "issues": results.get("alerts", []),
                            "summary": results.get("summary", {}),
                            "scan_time": results.get("scan_time", datetime.now().isoformat())
                        }
                except Exception as e:
                    logger.warning(f"Could not load saved results: {e}")
                
                # Return basic success response if results loading failed
                return {
                    "status": "success",
                    "issues": [],
                    "summary": {"message": "Scan completed but results could not be loaded"},
                    "scan_time": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "failed",
                    "issues": [],
                    "summary": {"error": "Scan failed to complete"},
                    "scan_time": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error in scan_app for {model}/app{app_num}: {e}")
            return {
                "status": "error", 
                "issues": [],
                "summary": {"error": str(e)},
                "scan_time": datetime.now().isoformat()
            }


# Factory function
def create_scanner(base_path: Path) -> ZAPScanner:
    """Factory function to create and initialize a ZAP scanner."""
    logger.info("Creating ZAP scanner instance...")
    return ZAPScanner(base_path)