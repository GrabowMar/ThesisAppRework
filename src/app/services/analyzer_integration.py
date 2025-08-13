"""
Analyzer Integration Service
===========================

Bridges the task manager with the analyzer_manager.py to provide
seamless integration between Celery tasks and containerized analyzers.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class AnalyzerIntegration:
    """
    Integration layer between task manager and analyzer infrastructure.
    """
    
    def __init__(self):
        self.analyzer_manager_path = self._get_analyzer_manager_path()
        self.services_status = {}
        self.last_health_check = None
        
    def _get_analyzer_manager_path(self) -> Path:
        """Get the path to analyzer_manager.py."""
        # Navigate from src2/app/services to analyzer/
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent.parent
        analyzer_path = project_root / 'analyzer' / 'analyzer_manager.py'
        
        if not analyzer_path.exists():
            logger.warning(f"Analyzer manager not found at {analyzer_path}")
        
        return analyzer_path
    
    def run_analyzer_command(self, command: List[str], timeout: int = 300) -> Dict[str, Any]:
        """
        Run a command through analyzer_manager.py.
        
        Args:
            command: Command arguments to pass to analyzer_manager.py
            timeout: Command timeout in seconds
            
        Returns:
            Command result
        """
        
        try:
            if not self.analyzer_manager_path.exists():
                raise FileNotFoundError(f"Analyzer manager not found at {self.analyzer_manager_path}")
            
            # Construct full command
            full_command = [sys.executable, str(self.analyzer_manager_path)] + command
            
            logger.info(f"Running analyzer command: {' '.join(command)}")
            
            # Run command with proper encoding handling for Windows
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.analyzer_manager_path.parent,
                encoding='utf-8',
                errors='replace'  # Replace problematic characters instead of failing
            )
            
            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': command,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Analyzer command timed out: {' '.join(command)}")
            return {
                'success': False,
                'error': 'Command timed out',
                'command': command,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to run analyzer command: {e}")
            return {
                'success': False,
                'error': str(e),
                'command': command,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def start_analyzer_services(self) -> bool:
        """
        Start all analyzer services.
        
        Returns:
            True if services started successfully
        """
        
        try:
            result = self.run_analyzer_command(['start'])
            
            if result['success']:
                logger.info("Analyzer services started successfully")
                self._update_services_status()
                return True
            else:
                logger.error(f"Failed to start analyzer services: {result.get('stderr', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting analyzer services: {e}")
            return False
    
    def stop_analyzer_services(self) -> bool:
        """
        Stop all analyzer services.
        
        Returns:
            True if services stopped successfully
        """
        
        try:
            result = self.run_analyzer_command(['stop'])
            
            if result['success']:
                logger.info("Analyzer services stopped successfully")
                self._update_services_status()
                return True
            else:
                logger.error(f"Failed to stop analyzer services: {result.get('stderr', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping analyzer services: {e}")
            return False
    
    def restart_analyzer_services(self) -> bool:
        """
        Restart all analyzer services.
        
        Returns:
            True if services restarted successfully
        """
        
        try:
            # Stop first
            stop_result = self.run_analyzer_command(['stop'])
            if not stop_result['success']:
                logger.warning("Stop command failed, continuing with start")
            
            # Then start
            start_result = self.run_analyzer_command(['start'])
            
            if start_result['success']:
                logger.info("Analyzer services restarted successfully")
                self._update_services_status()
                return True
            else:
                logger.error(f"Failed to restart analyzer services: {start_result.get('stderr', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting analyzer services: {e}")
            return False
    
    def get_services_status(self) -> Dict[str, Any]:
        """
        Get status of all analyzer services.
        
        Returns:
            Services status information
        """
        
        try:
            # Check if analyzer manager exists
            if not self.analyzer_manager_path.exists():
                return {
                    'error': 'Analyzer manager not found',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # Try to get real status from analyzer manager
            try:
                result = self.run_analyzer_command(['health'], timeout=10)
                
                if result.get('returncode') == 0:
                    # Parse health output to extract service status
                    output = result.get('stdout', '')
                    
                    # Look for service health in output
                    services_status = {}
                    lines = output.split('\n')
                    
                    for line in lines:
                        if '✅' in line and ':' in line:
                            # Extract service name and status from lines like "✅ static-analyzer: healthy"
                            parts = line.split(':')
                            if len(parts) >= 2:
                                service_name = parts[0].replace('✅', '').replace('❌', '').strip()
                                status = parts[1].strip()
                                services_status[service_name] = {'status': status}
                    
                    if services_status:
                        status_info = {
                            'services': services_status,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'health_check_mode': 'real'
                        }
                        self.services_status = status_info
                        self.last_health_check = datetime.now(timezone.utc)
                        return status_info
                
                # Fallback to simplified status if parsing failed
                logger.warning("Failed to parse analyzer health output, using simplified status")
                
            except Exception as e:
                logger.warning(f"Failed to get real analyzer status: {e}, using simplified status")
            
            # Simplified fallback status
            status_info = {
                'services': {
                    'analyzer_manager': {'status': 'available'},
                    'docker_services': {'status': 'unknown'}
                },
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'health_check_mode': 'simplified'
            }
            self.services_status = status_info
            self.last_health_check = datetime.now(timezone.utc)
            return status_info
                
        except Exception as e:
            logger.error(f"Error getting services status: {e}")
            return {'error': str(e)}
    
    def run_security_analysis(self, model_slug: str, app_number: int, 
                            tools: Optional[List[str]] = None, 
                            options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run security analysis through analyzer infrastructure.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: Security tools to run
            options: Additional options
            
        Returns:
            Analysis results
        """
        
        try:
            # Construct command
            command = ['analyze', '--type', 'security', '--model', model_slug, '--app', str(app_number)]
            
            if tools:
                command.extend(['--tools'] + tools)
            
            if options:
                # Add options as JSON
                command.extend(['--options', json.dumps(options)])
            
            # Run analysis
            result = self.run_analyzer_command(command, timeout=options.get('timeout', 600) if options else 600)
            
            if result['success']:
                # Parse results from stdout
                try:
                    analysis_results = json.loads(result['stdout'])
                    return analysis_results
                except json.JSONDecodeError:
                    # If JSON parsing fails, return raw output
                    return {
                        'status': 'completed',
                        'raw_output': result['stdout'],
                        'command': command
                    }
            else:
                return {
                    'status': 'failed',
                    'error': result.get('stderr', 'Unknown error'),
                    'command': command
                }
                
        except Exception as e:
            logger.error(f"Error running security analysis: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def run_performance_test(self, model_slug: str, app_number: int,
                           test_config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run performance test through analyzer infrastructure.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            test_config: Performance test configuration
            
        Returns:
            Test results
        """
        
        try:
            # Construct command
            command = ['analyze', '--type', 'performance', '--model', model_slug, '--app', str(app_number)]
            
            if test_config:
                command.extend(['--config', json.dumps(test_config)])
            
            # Run test
            result = self.run_analyzer_command(command, timeout=test_config.get('timeout', 900) if test_config else 900)
            
            if result['success']:
                try:
                    test_results = json.loads(result['stdout'])
                    return test_results
                except json.JSONDecodeError:
                    return {
                        'status': 'completed',
                        'raw_output': result['stdout'],
                        'command': command
                    }
            else:
                return {
                    'status': 'failed',
                    'error': result.get('stderr', 'Unknown error'),
                    'command': command
                }
                
        except Exception as e:
            logger.error(f"Error running performance test: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def run_static_analysis(self, model_slug: str, app_number: int,
                          tools: Optional[List[str]] = None,
                          options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run static analysis through analyzer infrastructure.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: Static analysis tools to run
            options: Additional options
            
        Returns:
            Analysis results
        """
        
        try:
            # Construct command
            command = ['analyze', '--type', 'static', '--model', model_slug, '--app', str(app_number)]
            
            if tools:
                command.extend(['--tools'] + tools)
            
            if options:
                command.extend(['--options', json.dumps(options)])
            
            # Run analysis
            result = self.run_analyzer_command(command, timeout=options.get('timeout', 300) if options else 300)
            
            if result['success']:
                try:
                    analysis_results = json.loads(result['stdout'])
                    return analysis_results
                except json.JSONDecodeError:
                    return {
                        'status': 'completed',
                        'raw_output': result['stdout'],
                        'command': command
                    }
            else:
                return {
                    'status': 'failed',
                    'error': result.get('stderr', 'Unknown error'),
                    'command': command
                }
                
        except Exception as e:
            logger.error(f"Error running static analysis: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def run_ai_analysis(self, model_slug: str, app_number: int,
                       analysis_types: Optional[List[str]] = None,
                       options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run AI-powered analysis through analyzer infrastructure.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            analysis_types: Types of AI analysis to perform
            options: Additional options
            
        Returns:
            Analysis results
        """
        
        try:
            # Construct command
            command = ['analyze', '--type', 'ai', '--model', model_slug, '--app', str(app_number)]
            
            if analysis_types:
                command.extend(['--analysis-types'] + analysis_types)
            
            if options:
                command.extend(['--options', json.dumps(options)])
            
            # Run analysis
            result = self.run_analyzer_command(command, timeout=options.get('timeout', 1200) if options else 1200)
            
            if result['success']:
                try:
                    analysis_results = json.loads(result['stdout'])
                    return analysis_results
                except json.JSONDecodeError:
                    return {
                        'status': 'completed',
                        'raw_output': result['stdout'],
                        'command': command
                    }
            else:
                return {
                    'status': 'failed',
                    'error': result.get('stderr', 'Unknown error'),
                    'command': command
                }
                
        except Exception as e:
            logger.error(f"Error running AI analysis: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _parse_status_output(self, status_output: str) -> Dict[str, Any]:
        """
        Parse status output from analyzer_manager.py.
        
        Args:
            status_output: Raw status output
            
        Returns:
            Parsed status information
        """
        
        try:
            # Try to parse as JSON first
            status_data = json.loads(status_output)
            return status_data
        except json.JSONDecodeError:
            # If not JSON, parse line by line
            lines = status_output.strip().split('\n')
            services = {}
            
            for line in lines:
                if 'Service:' in line and 'Status:' in line:
                    parts = line.split()
                    service_name = None
                    status = None
                    
                    for i, part in enumerate(parts):
                        if part == 'Service:' and i + 1 < len(parts):
                            service_name = parts[i + 1]
                        if part == 'Status:' and i + 1 < len(parts):
                            status = parts[i + 1]
                    
                    if service_name and status:
                        services[service_name] = {'status': status}
            
            return {
                'services': services,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'raw_output': status_output
            }
    
    def _update_services_status(self):
        """Update cached services status."""
        try:
            self.get_services_status()
        except Exception as e:
            logger.error(f"Failed to update services status: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of analyzer infrastructure.
        
        Returns:
            Health check results
        """
        
        try:
            # Check if analyzer_manager.py exists
            if not self.analyzer_manager_path.exists():
                return {
                    'status': 'critical',
                    'message': 'Analyzer manager not found',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # Get services status (simplified version)
            status_info = self.get_services_status()
            
            if 'error' in status_info:
                return {
                    'status': 'degraded',
                    'message': 'Failed to get services status',
                    'details': status_info,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # For simplified status, just return that the manager is available
            return {
                'status': 'available',
                'message': 'Analyzer manager is available',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# Global analyzer integration instance
_analyzer_integration = None

def get_analyzer_integration() -> AnalyzerIntegration:
    """Get the global analyzer integration instance."""
    global _analyzer_integration
    if _analyzer_integration is None:
        _analyzer_integration = AnalyzerIntegration()
    return _analyzer_integration
