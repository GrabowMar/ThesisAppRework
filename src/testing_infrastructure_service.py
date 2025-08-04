"""
Testing Infrastructure Integration Service
==========================================

Integrates the containerized testing infrastructure with the main Flask application.
Provides API for managing security analysis, performance testing, and ZAP scans.
"""

import asyncio
import json
import logging
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Add testing infrastructure to path
testing_infra_path = Path(__file__).parent.parent / "testing-infrastructure"
sys.path.append(str(testing_infra_path / "shared" / "api-contracts"))

try:
    from testing_api_client import SyncTestingAPIClient
    from testing_api_models import (
        SecurityTestRequest, PerformanceTestRequest, ZapTestRequest, AIAnalysisRequest,
        TestingStatus, TestType, SeverityLevel, BatchTestRequest, TestRequest
    )
except ImportError:
    # Mock classes if testing infrastructure is not available
    class SyncTestingAPIClient:
        def __init__(self, *args, **kwargs):
            pass
        def health_check(self):
            return {}
        def run_security_analysis(self, *args, **kwargs):
            return None
        def run_performance_test(self, *args, **kwargs):
            return None
        def run_zap_scan(self, *args, **kwargs):
            return None
        def get_test_status(self, *args, **kwargs):
            return {}
        def get_test_results(self, *args, **kwargs):
            return {}
        def cancel_test(self, *args, **kwargs):
            return True
    
    class SecurityTestRequest:
        def __init__(self, model=None, app_num=None, tools=None, *args, **kwargs):
            self.model = model
            self.app_num = app_num
            self.tools = tools or []
        
        def to_dict(self):
            return {
                'model': self.model,
                'app_num': self.app_num,
                'tools': self.tools
            }
    
    class PerformanceTestRequest:
        def __init__(self, model=None, app_num=None, target_url=None, users=None, *args, **kwargs):
            self.model = model
            self.app_num = app_num
            self.target_url = target_url
            self.users = users
        
        def to_dict(self):
            return {
                'model': self.model,
                'app_num': self.app_num,
                'target_url': self.target_url,
                'users': self.users
            }
    
    class ZapTestRequest:
        def __init__(self, model=None, app_num=None, target_url=None, scan_type=None, *args, **kwargs):
            self.model = model
            self.app_num = app_num
            self.target_url = target_url
            self.scan_type = scan_type
        
        def to_dict(self):
            return {
                'model': self.model,
                'app_num': self.app_num,
                'target_url': self.target_url,
                'scan_type': self.scan_type
            }
    
    class AIAnalysisRequest:
        def __init__(self, *args, **kwargs):
            pass
    
    class BatchTestRequest:
        def __init__(self, *args, **kwargs):
            pass
    
    class TestRequest:
        def __init__(self, *args, **kwargs):
            pass
    
    class TestingStatus:
        PENDING = 'pending'
        RUNNING = 'running'
        COMPLETED = 'completed'
        FAILED = 'failed'
        CANCELLED = 'cancelled'
    
    class TestType:
        SECURITY_BACKEND = 'security_backend'
        SECURITY_FRONTEND = 'security_frontend'
        PERFORMANCE = 'performance'
        SECURITY_ZAP = 'security_zap'
    
    class SeverityLevel:
        LOW = 'low'
        MEDIUM = 'medium'
        HIGH = 'high'
        CRITICAL = 'critical'

logger = logging.getLogger(__name__)


class TestingInfrastructureService:
    """Service for managing containerized testing infrastructure."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = SyncTestingAPIClient(base_url)
        self.active_tests = {}  # Track running tests
        self.test_results = {}  # Cache results
        self._lock = threading.RLock()
        
        # Available security tools with their configurations
        self.security_tools = {
            'bandit': {
                'name': 'Bandit',
                'description': 'Python security linter',
                'category': 'backend',
                'severity_levels': ['HIGH', 'MEDIUM', 'LOW'],
                'confidence_levels': ['HIGH', 'MEDIUM', 'LOW'],
                'options': {
                    'skip_tests': 'Comma-separated list of test IDs to skip (e.g., B101,B102)',
                    'exclude_paths': 'Paths to exclude from scan',
                    'format': 'Output format (json, txt, csv, xml)',
                    'severity_level': 'Minimum severity to report',
                    'confidence_level': 'Minimum confidence to report'
                }
            },
            'safety': {
                'name': 'Safety',
                'description': 'Python dependency vulnerability scanner',
                'category': 'backend',
                'scan_types': ['dependencies', 'requirements', 'pipenv', 'poetry'],
                'options': {
                    'apply_fixes': 'Automatically apply security updates',
                    'detailed_output': 'Enable verbose scan report',
                    'ignore_ids': 'Comma-separated list of vulnerability IDs to ignore',
                    'policy_file': 'Path to custom policy file',
                    'timeout': 'Request timeout in seconds (default: 30)'
                }
            },
            'pylint': {
                'name': 'Pylint',
                'description': 'Python code quality analyzer',
                'category': 'backend',
                'message_types': ['error', 'warning', 'refactor', 'convention'],
                'options': {
                    'disable_checks': 'Comma-separated list of checks to disable',
                    'enable_checks': 'Comma-separated list of checks to enable',
                    'output_format': 'Output format (text, json, colorized)',
                    'score_threshold': 'Minimum score threshold'
                }
            },
            'semgrep': {
                'name': 'Semgrep',
                'description': 'Static analysis with custom rules',
                'category': 'backend',
                'config_types': ['auto', 'security', 'python', 'owasp-top-10'],
                'options': {
                    'config': 'Configuration preset (auto, security, python)',
                    'max_memory': 'Maximum memory in MB per file scan',
                    'max_target_bytes': 'Maximum file size to scan',
                    'timeout': 'Maximum time per file in seconds',
                    'exclude_files': 'File patterns to exclude',
                    'severity': 'Minimum severity level (ERROR, WARNING, INFO)'
                }
            },
            'eslint': {
                'name': 'ESLint',
                'description': 'JavaScript/TypeScript linter',
                'category': 'frontend',
                'config_presets': ['recommended', 'security', 'react', 'typescript'],
                'options': {
                    'config_file': 'Path to ESLint configuration file',
                    'fix_issues': 'Automatically fix fixable issues',
                    'max_warnings': 'Maximum number of warnings allowed',
                    'env': 'Environment settings (browser, node, es6)',
                    'parser': 'Parser to use (default, typescript)',
                    'rules': 'Custom rules configuration'
                }
            },
            'retire': {
                'name': 'Retire.js',
                'description': 'JavaScript dependency vulnerability scanner',
                'category': 'frontend',
                'scan_targets': ['package.json', 'bower.json', 'node_modules', 'js_files'],
                'options': {
                    'severity': 'Minimum severity level (high, medium, low)',
                    'ignore_file': 'Path to ignore file',
                    'output_format': 'Output format (json, text)',
                    'include_dev': 'Include development dependencies'
                }
            },
            'npm-audit': {
                'name': 'NPM Audit',
                'description': 'Node.js package vulnerability scanner',
                'category': 'frontend',
                'audit_levels': ['critical', 'high', 'moderate', 'low'],
                'options': {
                    'audit_level': 'Minimum severity to report',
                    'production': 'Only scan production dependencies',
                    'dev': 'Include development dependencies',
                    'fix': 'Automatically fix vulnerabilities',
                    'force': 'Force package updates'
                }
            }
        }
        
        # ZAP scan types and options
        self.zap_scan_types = {
            'spider': {
                'name': 'Spider Scan',
                'description': 'Crawl the application to discover URLs',
                'options': {
                    'max_depth': 'Maximum crawl depth',
                    'max_children': 'Maximum child URLs per page',
                    'recurse': 'Enable recursive crawling',
                    'context_name': 'ZAP context name',
                    'user_agent': 'Custom user agent string'
                }
            },
            'active': {
                'name': 'Active Scan',
                'description': 'Perform active vulnerability scanning',
                'options': {
                    'policy': 'Scan policy to use',
                    'recurse': 'Scan recursively',
                    'in_scope_only': 'Only scan URLs in scope',
                    'max_rule_duration': 'Maximum time per rule in minutes',
                    'strength': 'Attack strength (Low, Medium, High, Insane)'
                }
            },
            'passive': {
                'name': 'Passive Scan',
                'description': 'Analyze traffic for vulnerabilities',
                'options': {
                    'enable_tags': 'Enable specific scan rule tags',
                    'disable_tags': 'Disable specific scan rule tags',
                    'max_alerts': 'Maximum number of alerts',
                    'context_name': 'ZAP context name'
                }
            },
            'baseline': {
                'name': 'Baseline Scan',
                'description': 'Quick security baseline assessment',
                'options': {
                    'duration': 'Scan duration in minutes',
                    'max_time': 'Maximum scan time',
                    'level': 'Scan level (Pass, Warn, Fail, Off)',
                    'context_file': 'Path to context file'
                }
            }
        }
        
        logger.info("Testing Infrastructure Service initialized")
    
    def get_service_health(self) -> Dict[str, Any]:
        """Check health status of all testing services."""
        try:
            health_status = self.client.health_check()
            
            # Add additional service information
            service_info = {
                'testing_infrastructure': {
                    'status': 'available' if health_status else 'unavailable',
                    'services': health_status,
                    'base_url': self.base_url,
                    'active_tests': len(self.active_tests)
                },
                'security_tools': {
                    'available': list(self.security_tools.keys()),
                    'backend_tools': [k for k, v in self.security_tools.items() if v['category'] == 'backend'],
                    'frontend_tools': [k for k, v in self.security_tools.items() if v['category'] == 'frontend']
                },
                'zap_scans': {
                    'available_types': list(self.zap_scan_types.keys()),
                    'scan_types': {k: v['name'] for k, v in self.zap_scan_types.items()}
                }
            }
            
            return service_info
            
        except Exception as e:
            logger.error(f"Error checking service health: {e}")
            return {
                'testing_infrastructure': {
                    'status': 'error',
                    'error': str(e),
                    'services': {},
                    'active_tests': len(self.active_tests)
                }
            }
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Get information about available security tools."""
        return {
            'security_tools': self.security_tools,
            'zap_scan_types': self.zap_scan_types,
            'categories': {
                'backend': [k for k, v in self.security_tools.items() if v['category'] == 'backend'],
                'frontend': [k for k, v in self.security_tools.items() if v['category'] == 'frontend']
            }
        }
    
    def create_security_analysis_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new security analysis job."""
        try:
            job_id = str(uuid.uuid4())
            
            # Extract configuration
            model = job_config.get('model')
            app_num = job_config.get('app_num')
            tools = job_config.get('tools', [])
            tool_options = job_config.get('tool_options', {})
            
            if not model or not app_num:
                return {'success': False, 'error': 'Model and app number are required'}
            
            # Create test request
            test_request = SecurityTestRequest(
                model=model,
                app_num=int(app_num),
                test_type=TestType.SECURITY_BACKEND,
                tools=tools,
                scan_depth=job_config.get('scan_depth', 'standard'),
                include_dependencies=job_config.get('include_dependencies', True),
                options=tool_options
            )
            
            # Store job info
            with self._lock:
                self.active_tests[job_id] = {
                    'job_id': job_id,
                    'model': model,
                    'app_num': app_num,
                    'tools': tools,
                    'status': TestingStatus.PENDING,
                    'created_at': datetime.utcnow(),
                    'request': test_request
                }
            
            # Submit test asynchronously
            threading.Thread(
                target=self._run_security_analysis,
                args=(job_id, test_request),
                daemon=True
            ).start()
            
            logger.info(f"Created security analysis job {job_id} for {model}/app{app_num}")
            
            return {
                'success': True,
                'job_id': job_id,
                'message': f'Security analysis job created for {model}/app{app_num}'
            }
            
        except Exception as e:
            logger.error(f"Error creating security analysis job: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_zap_scan_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new ZAP security scan job."""
        try:
            job_id = str(uuid.uuid4())
            
            # Extract configuration
            model = job_config.get('model')
            app_num = job_config.get('app_num')
            target_url = job_config.get('target_url')
            scan_type = job_config.get('scan_type', 'spider')
            scan_options = job_config.get('scan_options', {})
            
            if not all([model, app_num, target_url]):
                return {'success': False, 'error': 'Model, app number, and target URL are required'}
            
            # Create ZAP test request
            test_request = ZapTestRequest(
                model=model,
                app_num=int(app_num) if app_num is not None else 0,
                test_type=TestType.SECURITY_ZAP,
                target_url=target_url,
                scan_type=scan_type,
                options=scan_options
            )
            
            # Store job info
            with self._lock:
                self.active_tests[job_id] = {
                    'job_id': job_id,
                    'model': model,
                    'app_num': app_num,
                    'target_url': target_url,
                    'scan_type': scan_type,
                    'status': TestingStatus.PENDING,
                    'created_at': datetime.utcnow(),
                    'request': test_request
                }
            
            # Submit test asynchronously
            threading.Thread(
                target=self._run_zap_scan,
                args=(job_id, test_request),
                daemon=True
            ).start()
            
            logger.info(f"Created ZAP scan job {job_id} for {model}/app{app_num} - {target_url}")
            
            return {
                'success': True,
                'job_id': job_id,
                'message': f'ZAP {scan_type} scan created for {model}/app{app_num}'
            }
            
        except Exception as e:
            logger.error(f"Error creating ZAP scan job: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_performance_test_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new performance test job."""
        try:
            job_id = str(uuid.uuid4())
            
            # Extract configuration
            model = job_config.get('model')
            app_num = job_config.get('app_num')
            target_url = job_config.get('target_url')
            users = job_config.get('users', 10)
            spawn_rate = job_config.get('spawn_rate', 2)
            duration = job_config.get('duration', 60)
            
            if not all([model, app_num, target_url]):
                return {'success': False, 'error': 'Model, app number, and target URL are required'}
            
            # Create performance test request
            test_request = PerformanceTestRequest(
                model=model,
                app_num=int(app_num) if app_num is not None else 0,
                test_type=TestType.PERFORMANCE,
                target_url=target_url,
                users=int(users) if users is not None else 1,
                spawn_rate=int(spawn_rate) if spawn_rate is not None else 1,
                duration=int(duration) if duration is not None else 60
            )
            
            # Store job info
            with self._lock:
                self.active_tests[job_id] = {
                    'job_id': job_id,
                    'model': model,
                    'app_num': app_num,
                    'target_url': target_url,
                    'users': users,
                    'duration': duration,
                    'status': TestingStatus.PENDING,
                    'created_at': datetime.utcnow(),
                    'request': test_request
                }
            
            # Submit test asynchronously
            threading.Thread(
                target=self._run_performance_test,
                args=(job_id, test_request),
                daemon=True
            ).start()
            
            logger.info(f"Created performance test job {job_id} for {model}/app{app_num} - {target_url}")
            
            return {
                'success': True,
                'job_id': job_id,
                'message': f'Performance test created for {model}/app{app_num} with {users} users'
            }
            
        except Exception as e:
            logger.error(f"Error creating performance test job: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a testing job."""
        try:
            with self._lock:
                if job_id not in self.active_tests:
                    return {'success': False, 'error': 'Job not found'}
                
                job = self.active_tests[job_id].copy()
            
            # Serialize request object if it exists
            if 'request' in job and hasattr(job['request'], 'to_dict'):
                job['request'] = job['request'].to_dict()
            
            # Add runtime information
            if job['status'] == TestingStatus.RUNNING:
                try:
                    now = datetime.utcnow()
                    created_at = job['created_at']
                    
                    # Handle timezone mismatches
                    if created_at.tzinfo is not None and now.tzinfo is None:
                        # created_at is timezone-aware, now is naive
                        now = now.replace(tzinfo=created_at.tzinfo)
                    elif created_at.tzinfo is None and now.tzinfo is not None:
                        # created_at is naive, now is timezone-aware
                        created_at = created_at.replace(tzinfo=now.tzinfo)
                    
                    runtime = (now - created_at).total_seconds()
                    job['runtime_seconds'] = runtime
                except Exception as e:
                    logger.warning(f"Could not calculate runtime for job {job_id}: {e}")
                    job['runtime_seconds'] = 0
            
            return {'success': True, 'job': job}
            
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """Get the result of a completed testing job."""
        try:
            with self._lock:
                if job_id not in self.test_results:
                    return {'success': False, 'error': 'Job result not found'}
                
                result = self.test_results[job_id].copy()
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            logger.error(f"Error getting job result for {job_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_all_jobs(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all testing jobs with optional status filtering."""
        try:
            with self._lock:
                jobs = []
                
                # Add active tests
                for job in self.active_tests.values():
                    if not status_filter or job['status'] == status_filter:
                        job_copy = job.copy()
                        # Serialize request object if it exists
                        if 'request' in job_copy and hasattr(job_copy['request'], 'to_dict'):
                            job_copy['request'] = job_copy['request'].to_dict()
                        jobs.append(job_copy)
                
                # Add completed tests with results
                for job_id, result in self.test_results.items():
                    if job_id not in self.active_tests:  # Only completed jobs
                        job_info = {
                            'job_id': job_id,
                            'status': result.get('status', TestingStatus.COMPLETED),
                            'completed_at': result.get('completed_at'),
                            'total_issues': len(result.get('issues', [])),
                            'tools_used': result.get('tools_used', [])
                        }
                        if not status_filter or job_info['status'] == status_filter:
                            jobs.append(job_info)
                
                # Sort by creation/completion time
                jobs.sort(key=lambda x: x.get('created_at') or x.get('completed_at') or datetime.min, reverse=True)
                
                return jobs
                
        except Exception as e:
            logger.error(f"Error getting all jobs: {e}")
            return []
    
    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running testing job."""
        try:
            with self._lock:
                if job_id not in self.active_tests:
                    return {'success': False, 'error': 'Job not found'}
                
                job = self.active_tests[job_id]
                if job['status'] not in [TestingStatus.PENDING, TestingStatus.RUNNING]:
                    return {'success': False, 'error': 'Job cannot be cancelled'}
                
                # Try to cancel via API
                try:
                    test_type = job['request'].test_type
                    cancelled = self.client.cancel_test(job_id, test_type)
                    if cancelled:
                        job['status'] = TestingStatus.CANCELLED
                        job['cancelled_at'] = datetime.utcnow()
                        
                        logger.info(f"Cancelled testing job {job_id}")
                        return {'success': True, 'message': 'Job cancelled successfully'}
                    else:
                        return {'success': False, 'error': 'Failed to cancel job via API'}
                        
                except Exception as api_error:
                    # Fallback: mark as cancelled locally
                    job['status'] = TestingStatus.CANCELLED
                    job['cancelled_at'] = datetime.utcnow()
                    
                    logger.warning(f"Marked job {job_id} as cancelled locally due to API error: {api_error}")
                    return {'success': True, 'message': 'Job marked as cancelled (API unavailable)'}
                
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _run_security_analysis(self, job_id: str, request: SecurityTestRequest):
        """Run security analysis in background thread."""
        try:
            with self._lock:
                if job_id in self.active_tests:
                    self.active_tests[job_id]['status'] = TestingStatus.RUNNING
                    self.active_tests[job_id]['started_at'] = datetime.utcnow()
            
            # Run the actual security analysis
            result = self.client.run_security_analysis(
                request.model,
                request.app_num,
                request.tools
            )
            
            if result:
                with self._lock:
                    self.active_tests[job_id]['status'] = TestingStatus.COMPLETED
                    self.active_tests[job_id]['completed_at'] = datetime.utcnow()
                    self.test_results[job_id] = result.to_dict() if hasattr(result, 'to_dict') else result
                
                logger.info(f"Security analysis job {job_id} completed successfully")
            else:
                with self._lock:
                    self.active_tests[job_id]['status'] = TestingStatus.FAILED
                    self.active_tests[job_id]['error'] = 'Analysis failed'
                
                logger.error(f"Security analysis job {job_id} failed")
                
        except Exception as e:
            with self._lock:
                if job_id in self.active_tests:
                    self.active_tests[job_id]['status'] = TestingStatus.FAILED
                    self.active_tests[job_id]['error'] = str(e)
            
            logger.error(f"Error running security analysis job {job_id}: {e}")
    
    def _run_zap_scan(self, job_id: str, request: ZapTestRequest):
        """Run ZAP scan in background thread."""
        try:
            with self._lock:
                if job_id in self.active_tests:
                    self.active_tests[job_id]['status'] = TestingStatus.RUNNING
                    self.active_tests[job_id]['started_at'] = datetime.utcnow()
            
            # Run the actual ZAP scan
            result = self.client.run_zap_scan(
                request.model,
                request.app_num,
                request.target_url,
                request.scan_type
            )
            
            if result:
                with self._lock:
                    self.active_tests[job_id]['status'] = TestingStatus.COMPLETED
                    self.active_tests[job_id]['completed_at'] = datetime.utcnow()
                    self.test_results[job_id] = result.to_dict() if hasattr(result, 'to_dict') else result
                
                logger.info(f"ZAP scan job {job_id} completed successfully")
            else:
                with self._lock:
                    self.active_tests[job_id]['status'] = TestingStatus.FAILED
                    self.active_tests[job_id]['error'] = 'ZAP scan failed'
                
                logger.error(f"ZAP scan job {job_id} failed")
                
        except Exception as e:
            with self._lock:
                if job_id in self.active_tests:
                    self.active_tests[job_id]['status'] = TestingStatus.FAILED
                    self.active_tests[job_id]['error'] = str(e)
            
            logger.error(f"Error running ZAP scan job {job_id}: {e}")
    
    def _run_performance_test(self, job_id: str, request: PerformanceTestRequest):
        """Run performance test in background thread."""
        try:
            with self._lock:
                if job_id in self.active_tests:
                    self.active_tests[job_id]['status'] = TestingStatus.RUNNING
                    self.active_tests[job_id]['started_at'] = datetime.utcnow()
            
            # Run the actual performance test
            result = self.client.run_performance_test(
                request.model,
                request.app_num,
                request.target_url,
                request.users
            )
            
            if result:
                with self._lock:
                    self.active_tests[job_id]['status'] = TestingStatus.COMPLETED
                    self.active_tests[job_id]['completed_at'] = datetime.utcnow()
                    self.test_results[job_id] = result.to_dict() if hasattr(result, 'to_dict') else result
                
                logger.info(f"Performance test job {job_id} completed successfully")
            else:
                with self._lock:
                    self.active_tests[job_id]['status'] = TestingStatus.FAILED
                    self.active_tests[job_id]['error'] = 'Performance test failed'
                
                logger.error(f"Performance test job {job_id} failed")
                
        except Exception as e:
            with self._lock:
                if job_id in self.active_tests:
                    self.active_tests[job_id]['status'] = TestingStatus.FAILED
                    self.active_tests[job_id]['error'] = str(e)
            
            logger.error(f"Error running performance test job {job_id}: {e}")


# Global service instance
_testing_service = None
_service_lock = threading.Lock()


def get_testing_infrastructure_service() -> TestingInfrastructureService:
    """Get the global testing infrastructure service instance."""
    global _testing_service
    
    if _testing_service is None:
        with _service_lock:
            if _testing_service is None:
                _testing_service = TestingInfrastructureService()
    
    return _testing_service


def initialize_testing_infrastructure_service(base_url: str = "http://localhost:8000") -> TestingInfrastructureService:
    """Initialize the testing infrastructure service with custom configuration."""
    global _testing_service
    
    with _service_lock:
        _testing_service = TestingInfrastructureService(base_url)
    
    return _testing_service
