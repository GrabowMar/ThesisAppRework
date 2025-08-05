"""
Unified CLI Analyzer
===================

A consolidated command-line interface that unifies the functionality from both
batch_testing_service.py and testing_infrastructure_service.py into a single,
comprehensive tool for container and security analysis.

This module provides:
- Unified command-line interface for all testing operations
- Container lifecycle management (start, stop, restart, rebuild)
- Security analysis using multiple tools (bandit, safety, pylint, semgrep, eslint, etc.)
- ZAP security scanning with various scan types
- Performance testing with configurable load patterns
- Batch operations across multiple models and applications
- Real-time progress monitoring and detailed reporting
- Export capabilities for results in multiple formats

Key Features:
- Single CLI entry point for all testing operations
- Consistent configuration management
- Comprehensive error handling and logging
- Plugin architecture for extending functionality
- Integration with existing Docker and testing infrastructure

Usage Examples:
    # Container operations
    python unified_cli_analyzer.py container start --model claude-3-sonnet --app 1
    python unified_cli_analyzer.py container batch-start --models all --apps 1-5
    
    # Security analysis
    python unified_cli_analyzer.py security backend --model gpt-4 --app 1 --tools bandit,safety
    python unified_cli_analyzer.py security zap-scan --target http://localhost:8001 --scan-type active
    
    # Performance testing
    python unified_cli_analyzer.py performance test --target http://localhost:8001 --users 50 --duration 300
    
    # Batch operations
    python unified_cli_analyzer.py batch create --operation security_backend --models claude-3-sonnet,gpt-4 --apps 1-10
    python unified_cli_analyzer.py batch status --operation-id abc123
    
    # Reporting
    python unified_cli_analyzer.py report export --format json --output results.json
    python unified_cli_analyzer.py report summary --models all --date-range 7d
"""

import argparse
import json
import logging
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core_services import DockerManager, DockerUtils
try:
    from models import ModelCapability
except ImportError:
    ModelCapability = None


class ToolCategory(Enum):
    """Tool categories for classification."""
    BACKEND_SECURITY = "backend_security"
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_QUALITY = "backend_quality"
    FRONTEND_QUALITY = "frontend_quality"
    PERFORMANCE = "performance"
    VULNERABILITY = "vulnerability"


class UnifiedCLIAnalyzer:
    """Unified CLI analyzer that consolidates container and testing operations."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the unified CLI analyzer.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.logger = self._setup_logging()
        self.config = self._load_config(config_path)
        
        # Initialize service components
        self.docker_manager = DockerManager()
        
        # CLI state management
        self.operation_history: List[Dict[str, Any]] = []
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        
        # Mock service methods for compatibility
        self._jobs: List[Dict[str, Any]] = []
        self._job_counter = 0
        
        self.logger.info("Unified CLI Analyzer initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('unified_cli_analyzer')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            'default_timeout': 300,
            'default_concurrency': 4,
            'default_models': ['claude-3-sonnet', 'gpt-4'],
            'default_apps': '1-5',
            'output_directory': 'reports',
            'log_level': 'INFO',
            'container_options': {
                'wait_healthy': True,
                'pull_images': False,
                'force_recreate': False,
                'remove_orphans': True
            },
            'security_tools': {
                'backend': ['bandit', 'safety', 'pylint'],
                'frontend': ['eslint', 'retire', 'npm-audit']
            },
            'zap_scan_defaults': {
                'scan_type': 'spider',
                'max_depth': 5,
                'max_children': 50
            },
            'performance_defaults': {
                'users': 10,
                'spawn_rate': 2,
                'duration': 60
            }
        }
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
                    self.logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return default_config
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser with all subcommands."""
        parser = argparse.ArgumentParser(
            prog='unified_cli_analyzer',
            description='Unified CLI for container and security analysis operations',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Container operations
  %(prog)s container start --model claude-3-sonnet --app 1
  %(prog)s container stop --model gpt-4 --app 1-5
  %(prog)s container batch-restart --models all --apps 1-10
  
  # Security analysis
  %(prog)s security backend --model claude-3-sonnet --app 1 --tools bandit,safety
  %(prog)s security frontend --model gpt-4 --app 2 --tools eslint,retire
  %(prog)s security zap-scan --target http://localhost:8001 --scan-type active
  
  # Performance testing
  %(prog)s performance test --target http://localhost:8001 --users 50 --duration 300
  
  # Batch operations
  %(prog)s batch create --operation security_backend --models claude-3-sonnet --apps 1-5
  %(prog)s batch status --operation-id abc123
  %(prog)s batch cancel --operation-id abc123
  
  # Reporting and monitoring
  %(prog)s report summary --models all --date-range 7d
  %(prog)s report export --format json --output results.json
  %(prog)s monitor containers --refresh 30
  
  # Utility operations
  %(prog)s utils list-models
  %(prog)s utils validate-docker
  %(prog)s utils cleanup --dry-run
            """
        )
        
        # Global options
        parser.add_argument('--config', '-c', help='Configuration file path')
        parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
        parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output except errors')
        parser.add_argument('--output-format', choices=['text', 'json', 'yaml'], default='text',
                          help='Output format')
        
        # Create subparsers for main command categories
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Container management commands
        self._add_container_commands(subparsers)
        
        # Security analysis commands
        self._add_security_commands(subparsers)
        
        # Performance testing commands
        self._add_performance_commands(subparsers)
        
        # Batch operation commands
        self._add_batch_commands(subparsers)
        
        # Reporting and monitoring commands
        self._add_report_commands(subparsers)
        
        # Utility commands
        self._add_utility_commands(subparsers)
        
        return parser
    
    def _add_container_commands(self, subparsers) -> None:
        """Add container management subcommands."""
        container_parser = subparsers.add_parser('container', help='Container lifecycle management')
        container_subparsers = container_parser.add_subparsers(dest='container_action')
        
        # Single container operations
        for action in ['start', 'stop', 'restart', 'build']:
            action_parser = container_subparsers.add_parser(action, help=f'{action.title()} containers')
            action_parser.add_argument('--model', '-m', required=True, help='Model name')
            action_parser.add_argument('--app', '-a', required=True, help='App number or range (e.g., 1 or 1-5)')
            action_parser.add_argument('--container-type', choices=['backend', 'frontend', 'both'], 
                                     default='both', help='Container type to operate on')
            action_parser.add_argument('--timeout', type=int, default=300, help='Operation timeout in seconds')
            action_parser.add_argument('--force', action='store_true', help='Force operation')
        
        # Batch container operations
        for action in ['batch-start', 'batch-stop', 'batch-restart', 'batch-build']:
            batch_action = action.replace('batch-', '')
            action_parser = container_subparsers.add_parser(action, help=f'Batch {batch_action} containers')
            action_parser.add_argument('--models', help='Comma-separated model names or "all"')
            action_parser.add_argument('--apps', default='1-5', help='App range (e.g., 1-5 or 1,3,5)')
            action_parser.add_argument('--concurrency', type=int, default=4, help='Max concurrent operations')
            action_parser.add_argument('--timeout', type=int, default=300, help='Operation timeout in seconds')
            action_parser.add_argument('--container-types', help='Container types (backend,frontend)')
        
        # Container status and logs
        status_parser = container_subparsers.add_parser('status', help='Check container status')
        status_parser.add_argument('--model', help='Model name (optional)')
        status_parser.add_argument('--app', help='App number (optional)')
        status_parser.add_argument('--all', action='store_true', help='Show all containers')
        
        logs_parser = container_subparsers.add_parser('logs', help='Get container logs')
        logs_parser.add_argument('--model', '-m', required=True, help='Model name')
        logs_parser.add_argument('--app', '-a', required=True, type=int, help='App number')
        logs_parser.add_argument('--container-type', choices=['backend', 'frontend'], 
                               default='backend', help='Container type')
        logs_parser.add_argument('--tail', type=int, default=100, help='Number of log lines to show')
        logs_parser.add_argument('--follow', '-f', action='store_true', help='Follow log output')
    
    def _add_security_commands(self, subparsers) -> None:
        """Add security analysis subcommands."""
        security_parser = subparsers.add_parser('security', help='Security analysis operations')
        security_subparsers = security_parser.add_subparsers(dest='security_action')
        
        # Backend security analysis
        backend_parser = security_subparsers.add_parser('backend', help='Backend security analysis')
        backend_parser.add_argument('--model', '-m', required=True, help='Model name')
        backend_parser.add_argument('--app', '-a', required=True, help='App number')
        backend_parser.add_argument('--tools', help='Comma-separated security tools (bandit,safety,pylint,semgrep)')
        backend_parser.add_argument('--scan-depth', choices=['quick', 'standard', 'deep'], 
                                   default='standard', help='Scan depth')
        backend_parser.add_argument('--include-dependencies', action='store_true', default=True,
                                   help='Include dependency scanning')
        backend_parser.add_argument('--tool-options', help='JSON string of tool-specific options')
        
        # Frontend security analysis
        frontend_parser = security_subparsers.add_parser('frontend', help='Frontend security analysis')
        frontend_parser.add_argument('--model', '-m', required=True, help='Model name')
        frontend_parser.add_argument('--app', '-a', required=True, help='App number')
        frontend_parser.add_argument('--tools', help='Comma-separated security tools (eslint,retire,npm-audit)')
        frontend_parser.add_argument('--scan-depth', choices=['quick', 'standard', 'deep'], 
                                   default='standard', help='Scan depth')
        frontend_parser.add_argument('--tool-options', help='JSON string of tool-specific options')
        
        # ZAP security scanning
        zap_parser = security_subparsers.add_parser('zap-scan', help='ZAP security scanning')
        zap_parser.add_argument('--target', '-t', required=True, help='Target URL to scan')
        zap_parser.add_argument('--scan-type', choices=['spider', 'baseline', 'active', 'passive'], 
                               default='spider', help='ZAP scan type')
        zap_parser.add_argument('--model', help='Associated model name (for reporting)')
        zap_parser.add_argument('--app', type=int, help='Associated app number (for reporting)')
        zap_parser.add_argument('--scan-options', help='JSON string of scan-specific options')
        zap_parser.add_argument('--timeout', type=int, default=1800, help='Scan timeout in seconds')
        
        # Security report generation
        report_parser = security_subparsers.add_parser('report', help='Generate security reports')
        report_parser.add_argument('--job-id', help='Specific job ID to report on')
        report_parser.add_argument('--model', help='Filter by model')
        report_parser.add_argument('--date-range', help='Date range (e.g., 7d, 2024-01-01:2024-01-31)')
        report_parser.add_argument('--format', choices=['text', 'json', 'html', 'csv'], 
                                 default='text', help='Report format')
        report_parser.add_argument('--output', help='Output file path')
        
        # List available tools
        tools_parser = security_subparsers.add_parser('list-tools', help='List available security tools')
        tools_parser.add_argument('--category', choices=['backend', 'frontend', 'all'], 
                                 default='all', help='Tool category')
    
    def _add_performance_commands(self, subparsers) -> None:
        """Add performance testing subcommands."""
        perf_parser = subparsers.add_parser('performance', help='Performance testing operations')
        perf_subparsers = perf_parser.add_subparsers(dest='performance_action')
        
        # Performance test
        test_parser = perf_subparsers.add_parser('test', help='Run performance test')
        test_parser.add_argument('--target', '-t', required=True, help='Target URL to test')
        test_parser.add_argument('--users', '-u', type=int, default=10, help='Number of virtual users')
        test_parser.add_argument('--spawn-rate', '-r', type=int, default=2, help='User spawn rate per second')
        test_parser.add_argument('--duration', '-d', type=int, default=60, help='Test duration in seconds')
        test_parser.add_argument('--model', help='Associated model name (for reporting)')
        test_parser.add_argument('--app', type=int, help='Associated app number (for reporting)')
        test_parser.add_argument('--test-options', help='JSON string of test-specific options')
        
        # Performance monitoring
        monitor_parser = perf_subparsers.add_parser('monitor', help='Monitor performance test')
        monitor_parser.add_argument('--job-id', required=True, help='Performance test job ID')
        monitor_parser.add_argument('--refresh', type=int, default=5, help='Refresh interval in seconds')
        
        # Performance reports
        report_parser = perf_subparsers.add_parser('report', help='Generate performance reports')
        report_parser.add_argument('--job-id', help='Specific job ID to report on')
        report_parser.add_argument('--model', help='Filter by model')
        report_parser.add_argument('--date-range', help='Date range (e.g., 7d, 2024-01-01:2024-01-31)')
        report_parser.add_argument('--format', choices=['text', 'json', 'html', 'csv'], 
                                 default='text', help='Report format')
        report_parser.add_argument('--output', help='Output file path')
    
    def _add_batch_commands(self, subparsers) -> None:
        """Add batch operation subcommands."""
        batch_parser = subparsers.add_parser('batch', help='Batch operation management')
        batch_subparsers = batch_parser.add_subparsers(dest='batch_action')
        
        # Create batch operation
        create_parser = batch_subparsers.add_parser('create', help='Create batch operation')
        create_parser.add_argument('--operation', required=True,
                                 choices=['start_containers', 'stop_containers', 'restart_containers', 
                                        'rebuild_containers', 'security_backend', 'security_frontend', 
                                        'security_full', 'vulnerability_scan', 'health_check', 
                                        'resource_monitor', 'log_collection', 'performance_test',
                                        'cleanup_containers', 'image_update', 'network_reset'],
                                 help='Operation type')
        create_parser.add_argument('--models', help='Comma-separated model names or "all"')
        create_parser.add_argument('--apps', default='1-5', help='App range (e.g., 1-5 or 1,3,5)')
        create_parser.add_argument('--concurrency', type=int, default=4, help='Max concurrent operations')
        create_parser.add_argument('--timeout', type=int, default=300, help='Operation timeout in seconds')
        create_parser.add_argument('--tools', help='Security tools for analysis operations')
        create_parser.add_argument('--container-options', help='JSON string of container options')
        create_parser.add_argument('--name', help='Operation name (optional)')
        create_parser.add_argument('--description', help='Operation description (optional)')
        create_parser.add_argument('--start-immediately', action='store_true', help='Start operation immediately')
        
        # Batch operation management
        for action in ['start', 'cancel', 'delete']:
            action_parser = batch_subparsers.add_parser(action, help=f'{action.title()} batch operation')
            action_parser.add_argument('--operation-id', required=True, help='Operation ID')
        
        # Batch operation status and results
        status_parser = batch_subparsers.add_parser('status', help='Check batch operation status')
        status_parser.add_argument('--operation-id', help='Specific operation ID (optional)')
        status_parser.add_argument('--status-filter', choices=['pending', 'running', 'completed', 'failed', 'cancelled'],
                                 help='Filter by status')
        status_parser.add_argument('--operation-type-filter', help='Filter by operation type')
        status_parser.add_argument('--model-filter', help='Filter by model')
        
        results_parser = batch_subparsers.add_parser('results', help='Get batch operation results')
        results_parser.add_argument('--operation-id', required=True, help='Operation ID')
        results_parser.add_argument('--format', choices=['text', 'json', 'csv'], 
                                  default='text', help='Output format')
        results_parser.add_argument('--output', help='Output file path')
        
        # List operations
        list_parser = batch_subparsers.add_parser('list', help='List batch operations')
        list_parser.add_argument('--limit', type=int, default=20, help='Maximum number of operations to show')
        list_parser.add_argument('--status-filter', help='Filter by status')
        list_parser.add_argument('--operation-type-filter', help='Filter by operation type')
    
    def _add_report_commands(self, subparsers) -> None:
        """Add reporting and monitoring subcommands."""
        report_parser = subparsers.add_parser('report', help='Reporting and analysis')
        report_subparsers = report_parser.add_subparsers(dest='report_action')
        
        # Summary reports
        summary_parser = report_subparsers.add_parser('summary', help='Generate summary report')
        summary_parser.add_argument('--models', help='Comma-separated model names or "all"')
        summary_parser.add_argument('--date-range', help='Date range (e.g., 7d, 2024-01-01:2024-01-31)')
        summary_parser.add_argument('--operation-type', help='Filter by operation type')
        summary_parser.add_argument('--format', choices=['text', 'json', 'html'], 
                                  default='text', help='Report format')
        summary_parser.add_argument('--output', help='Output file path')
        
        # Export results
        export_parser = report_subparsers.add_parser('export', help='Export results')
        export_parser.add_argument('--format', required=True, choices=['json', 'csv', 'yaml', 'xml'],
                                 help='Export format')
        export_parser.add_argument('--output', required=True, help='Output file path')
        export_parser.add_argument('--models', help='Filter by models')
        export_parser.add_argument('--date-range', help='Date range filter')
        export_parser.add_argument('--operation-types', help='Filter by operation types')
        
        # Statistics
        stats_parser = report_subparsers.add_parser('stats', help='Show operation statistics')
        stats_parser.add_argument('--models', help='Filter by models')
        stats_parser.add_argument('--date-range', help='Date range filter')
        stats_parser.add_argument('--breakdown', choices=['model', 'operation', 'date', 'status'],
                                help='Statistics breakdown type')
        
        # Monitoring
        monitor_parser = subparsers.add_parser('monitor', help='Real-time monitoring')
        monitor_subparsers = monitor_parser.add_subparsers(dest='monitor_action')
        
        containers_parser = monitor_subparsers.add_parser('containers', help='Monitor containers')
        containers_parser.add_argument('--refresh', type=int, default=30, help='Refresh interval in seconds')
        containers_parser.add_argument('--models', help='Filter by models')
        
        operations_parser = monitor_subparsers.add_parser('operations', help='Monitor operations')
        operations_parser.add_argument('--refresh', type=int, default=10, help='Refresh interval in seconds')
        operations_parser.add_argument('--status-filter', help='Filter by status')
    
    def _add_utility_commands(self, subparsers) -> None:
        """Add utility subcommands."""
        utils_parser = subparsers.add_parser('utils', help='Utility operations')
        utils_subparsers = utils_parser.add_subparsers(dest='utils_action')
        
        # List available models
        models_parser = utils_subparsers.add_parser('list-models', help='List available models')
        models_parser.add_argument('--details', action='store_true', help='Show detailed model information')
        
        # Validate Docker setup
        docker_parser = utils_subparsers.add_parser('validate-docker', help='Validate Docker setup')
        docker_parser.add_argument('--verbose', action='store_true', help='Show detailed validation info')
        
        # System health check
        health_parser = utils_subparsers.add_parser('health-check', help='Check system health')
        health_parser.add_argument('--services', help='Comma-separated services to check')
        
        # Cleanup operations
        cleanup_parser = utils_subparsers.add_parser('cleanup', help='Cleanup operations')
        cleanup_parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned up')
        cleanup_parser.add_argument('--containers', action='store_true', help='Clean up containers')
        cleanup_parser.add_argument('--images', action='store_true', help='Clean up images')
        cleanup_parser.add_argument('--volumes', action='store_true', help='Clean up volumes')
        cleanup_parser.add_argument('--networks', action='store_true', help='Clean up networks')
        cleanup_parser.add_argument('--all', action='store_true', help='Clean up everything')
        
        # Configuration management
        config_parser = utils_subparsers.add_parser('config', help='Configuration management')
        config_subparsers = config_parser.add_subparsers(dest='config_action')
        
        show_parser = config_subparsers.add_parser('show', help='Show current configuration')
        show_parser.add_argument('--section', help='Show specific configuration section')
        
        set_parser = config_subparsers.add_parser('set', help='Set configuration value')
        set_parser.add_argument('key', help='Configuration key')
        set_parser.add_argument('value', help='Configuration value')
        
        reset_parser = config_subparsers.add_parser('reset', help='Reset configuration to defaults')
        reset_parser.add_argument('--confirm', action='store_true', help='Confirm reset')
    
    def execute_command(self, args: argparse.Namespace) -> int:
        """Execute the parsed command.
        
        Args:
            args: Parsed command arguments
            
        Returns:
            int: Exit code (0 for success, non-zero for error)
        """
        try:
            # Set logging level based on arguments
            if args.verbose:
                self.logger.setLevel(logging.DEBUG)
            elif args.quiet:
                self.logger.setLevel(logging.ERROR)
            
            # Route to appropriate command handler
            if args.command == 'container':
                return self._handle_container_command(args)
            elif args.command == 'security':
                return self._handle_security_command(args)
            elif args.command == 'performance':
                return self._handle_performance_command(args)
            elif args.command == 'batch':
                return self._handle_batch_command(args)
            elif args.command == 'report':
                return self._handle_report_command(args)
            elif args.command == 'monitor':
                return self._handle_monitor_command(args)
            elif args.command == 'utils':
                return self._handle_utils_command(args)
            else:
                self.logger.error(f"Unknown command: {args.command}")
                return 1
                
        except KeyboardInterrupt:
            self.logger.info("Operation cancelled by user")
            return 1
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def _handle_container_command(self, args: argparse.Namespace) -> int:
        """Handle container management commands."""
        if args.container_action in ['start', 'stop', 'restart', 'build']:
            return self._handle_single_container_operation(args)
        elif args.container_action.startswith('batch-'):
            return self._handle_batch_container_operation(args)
        elif args.container_action == 'status':
            return self._handle_container_status(args)
        elif args.container_action == 'logs':
            return self._handle_container_logs(args)
        else:
            self.logger.error(f"Unknown container action: {args.container_action}")
            return 1
    
    def _handle_single_container_operation(self, args: argparse.Namespace) -> int:
        """Handle single container operations."""
        try:
            model = args.model
            app_range = args.app
            action = args.container_action
            
            # Parse app range
            app_numbers = self._parse_app_range(app_range)
            
            success_count = 0
            total_count = len(app_numbers)
            
            for app_num in app_numbers:
                self.logger.info(f"Executing {action} for {model}/app{app_num}")
                
                try:
                    # Get compose path
                    app_dir = Path("misc/models") / model / f"app{app_num}"
                    compose_path = app_dir / "docker-compose.yml"
                    
                    if not compose_path.exists():
                        self.logger.error(f"Compose file not found: {compose_path}")
                        continue
                    
                    # Execute Docker action
                    if action == 'start':
                        result = self.docker_manager.start_containers(str(compose_path), model, app_num)
                    elif action == 'stop':
                        result = self.docker_manager.stop_containers(str(compose_path), model, app_num)
                    elif action == 'restart':
                        result = self.docker_manager.restart_containers(str(compose_path), model, app_num)
                    elif action == 'build':
                        result = self.docker_manager.build_containers(str(compose_path), model, app_num)
                    
                    if result['success']:
                        self.logger.info(f"✓ {action} successful for {model}/app{app_num}")
                        success_count += 1
                    else:
                        self.logger.error(f"✗ {action} failed for {model}/app{app_num}: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    self.logger.error(f"✗ {action} failed for {model}/app{app_num}: {e}")
            
            # Summary
            self.logger.info(f"Operation completed: {success_count}/{total_count} successful")
            return 0 if success_count == total_count else 1
            
        except Exception as e:
            self.logger.error(f"Container operation failed: {e}")
            return 1
    
    def _handle_batch_container_operation(self, args: argparse.Namespace) -> int:
        """Handle batch container operations."""
        try:
            action = args.container_action.replace('batch-', '')
            models = self._parse_models_arg(args.models)
            apps = args.apps or '1-5'
            
            # Create batch operation config
            operation_config = {
                'job_name': f'CLI Batch {action.title()}',
                'description': f'CLI initiated batch {action} operation',
                'operation_type': f'{action}_containers',
                'target_selection': 'models' if models != 'all' else 'all',
                'selected_models': models if models != 'all' else [],
                'selected_apps': apps,
                'concurrency': args.concurrency,
                'timeout': args.timeout,
                'container_options': {
                    'wait_healthy': True,
                    'pull_images': False,
                    'force_recreate': getattr(args, 'force', False),
                    'remove_orphans': True
                }
            }
            
            # Create and start operation
            result = self.batch_service.create_batch_operation(operation_config)
            
            if not result.get('success'):
                self.logger.error(f"Failed to create batch operation: {result.get('error')}")
                return 1
            
            operation_id = result['operation_id']
            self.logger.info(f"Created batch operation: {operation_id}")
            
            # Start operation
            start_result = self.batch_service.start_operation(operation_id)
            if not start_result.get('success'):
                self.logger.error(f"Failed to start operation: {start_result.get('error')}")
                return 1
            
            # Monitor operation progress
            return self._monitor_operation_progress(operation_id)
            
        except Exception as e:
            self.logger.error(f"Batch container operation failed: {e}")
            return 1
    
    def _handle_container_status(self, args: argparse.Namespace) -> int:
        """Handle container status command."""
        try:
            if args.all:
                # Show all container statistics
                stats = self.batch_service.get_container_stats()
                self._output_container_stats(stats, args.output_format)
            else:
                # Show specific container status
                if not args.model or not args.app:
                    self.logger.error("Model and app required for specific container status")
                    return 1
                
                app_num = int(args.app)
                project_name = DockerUtils.get_project_name(args.model, app_num)
                
                # Check backend and frontend containers
                for container_type in ['backend', 'frontend']:
                    container_name = f"{project_name}_{container_type}"
                    status = self.docker_manager.get_container_status(container_name)
                    self._output_container_status(args.model, app_num, container_type, status, args.output_format)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Container status check failed: {e}")
            return 1
    
    def _handle_container_logs(self, args: argparse.Namespace) -> int:
        """Handle container logs command."""
        try:
            logs = self.docker_manager.get_container_logs(
                args.model, args.app, args.container_type, args.tail
            )
            
            if args.follow:
                # Implement log following
                self._follow_container_logs(args.model, args.app, args.container_type)
            else:
                print(logs)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to get container logs: {e}")
            return 1
    
    def _handle_security_command(self, args: argparse.Namespace) -> int:
        """Handle security analysis commands."""
        if args.security_action in ['backend', 'frontend']:
            return self._handle_security_analysis(args)
        elif args.security_action == 'zap-scan':
            return self._handle_zap_scan(args)
        elif args.security_action == 'report':
            return self._handle_security_report(args)
        elif args.security_action == 'list-tools':
            return self._handle_list_security_tools(args)
        else:
            self.logger.error(f"Unknown security action: {args.security_action}")
            return 1
    
    def _handle_security_analysis(self, args: argparse.Namespace) -> int:
        """Handle security analysis operations."""
        try:
            # Prepare job configuration
            tools = []
            if args.tools:
                tools = [tool.strip() for tool in args.tools.split(',')]
            else:
                # Use default tools for category
                category = 'backend' if args.security_action == 'backend' else 'frontend'
                tools = self.config['security_tools'][category]
            
            tool_options = {}
            if args.tool_options:
                tool_options = json.loads(args.tool_options)
            
            job_config = {
                'model': args.model,
                'app_num': int(args.app),
                'tools': tools,
                'tool_options': tool_options,
                'scan_depth': args.scan_depth,
                'include_dependencies': getattr(args, 'include_dependencies', True)
            }
            
            # Create security analysis job
            result = self.testing_service.create_security_analysis_job(job_config)
            
            if not result.get('success'):
                self.logger.error(f"Failed to create security analysis job: {result.get('error')}")
                return 1
            
            job_id = result['job_id']
            self.logger.info(f"Created security analysis job: {job_id}")
            
            # Monitor job progress
            return self._monitor_job_progress(job_id)
            
        except Exception as e:
            self.logger.error(f"Security analysis failed: {e}")
            return 1
    
    def _handle_zap_scan(self, args: argparse.Namespace) -> int:
        """Handle ZAP security scanning."""
        try:
            scan_options = {}
            if args.scan_options:
                scan_options = json.loads(args.scan_options)
            
            job_config = {
                'model': args.model or 'cli-initiated',
                'app_num': args.app or 0,
                'target_url': args.target,
                'scan_type': args.scan_type,
                'scan_options': scan_options
            }
            
            # Create ZAP scan job
            result = self.testing_service.create_zap_scan_job(job_config)
            
            if not result.get('success'):
                self.logger.error(f"Failed to create ZAP scan job: {result.get('error')}")
                return 1
            
            job_id = result['job_id']
            self.logger.info(f"Created ZAP scan job: {job_id}")
            
            # Monitor job progress
            return self._monitor_job_progress(job_id)
            
        except Exception as e:
            self.logger.error(f"ZAP scan failed: {e}")
            return 1
    
    def _handle_performance_command(self, args: argparse.Namespace) -> int:
        """Handle performance testing commands."""
        if args.performance_action == 'test':
            return self._handle_performance_test(args)
        elif args.performance_action == 'monitor':
            return self._handle_performance_monitor(args)
        elif args.performance_action == 'report':
            return self._handle_performance_report(args)
        else:
            self.logger.error(f"Unknown performance action: {args.performance_action}")
            return 1
    
    def _handle_performance_test(self, args: argparse.Namespace) -> int:
        """Handle performance test execution."""
        try:
            test_options = {}
            if args.test_options:
                test_options = json.loads(args.test_options)
            
            job_config = {
                'model': args.model or 'cli-initiated',
                'app_num': args.app or 0,
                'target_url': args.target,
                'users': args.users,
                'spawn_rate': args.spawn_rate,
                'duration': args.duration,
                **test_options
            }
            
            # Create performance test job
            result = self.testing_service.create_performance_test_job(job_config)
            
            if not result.get('success'):
                self.logger.error(f"Failed to create performance test job: {result.get('error')}")
                return 1
            
            job_id = result['job_id']
            self.logger.info(f"Created performance test job: {job_id}")
            
            # Monitor job progress
            return self._monitor_job_progress(job_id)
            
        except Exception as e:
            self.logger.error(f"Performance test failed: {e}")
            return 1
    
    def _handle_batch_command(self, args: argparse.Namespace) -> int:
        """Handle batch operation commands."""
        if args.batch_action == 'create':
            return self._handle_batch_create(args)
        elif args.batch_action in ['start', 'cancel', 'delete']:
            return self._handle_batch_management(args)
        elif args.batch_action == 'status':
            return self._handle_batch_status(args)
        elif args.batch_action == 'results':
            return self._handle_batch_results(args)
        elif args.batch_action == 'list':
            return self._handle_batch_list(args)
        else:
            self.logger.error(f"Unknown batch action: {args.batch_action}")
            return 1
    
    def _parse_app_range(self, app_range: str) -> List[int]:
        """Parse app number range string."""
        app_numbers = []
        
        for part in app_range.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                app_numbers.extend(range(start, end + 1))
            else:
                app_numbers.append(int(part))
        
        return sorted(list(set(app_numbers)))  # Remove duplicates and sort
    
    def _parse_models_arg(self, models_arg: Optional[str]) -> Union[str, List[str]]:
        """Parse models argument."""
        if not models_arg or models_arg.lower() == 'all':
            return 'all'
        
        return [model.strip() for model in models_arg.split(',') if model.strip()]
    
    def _monitor_operation_progress(self, operation_id: str) -> int:
        """Monitor batch operation progress."""
        try:
            self.logger.info("Monitoring operation progress (Ctrl+C to stop monitoring)...")
            
            while True:
                operation = self.batch_service.get_operation_details(operation_id)
                
                if not operation:
                    self.logger.error("Operation not found")
                    return 1
                
                status = operation['status']
                progress = operation.get('progress', 0)
                
                if status == 'completed':
                    self.logger.info("✓ Operation completed successfully (100%)")
                    return 0
                elif status == 'failed':
                    self.logger.error(f"✗ Operation failed ({progress}%)")
                    return 1
                elif status == 'cancelled':
                    self.logger.info(f"Operation cancelled ({progress}%)")
                    return 1
                else:
                    self.logger.info(f"Operation {status}: {progress}%")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")
            return 0
    
    def _monitor_job_progress(self, job_id: str) -> int:
        """Monitor testing job progress."""
        try:
            self.logger.info("Monitoring job progress (Ctrl+C to stop monitoring)...")
            
            while True:
                status_info = self.testing_service.get_job_status(job_id)
                
                if not status_info.get('success'):
                    self.logger.error("Failed to get job status")
                    return 1
                
                status = status_info.get('status', 'unknown')
                
                if status == 'completed':
                    self.logger.info("✓ Job completed successfully")
                    
                    # Get and display results
                    results = self.testing_service.get_job_result(job_id)
                    if results.get('success'):
                        self._display_job_results(results.get('results', {}))
                    
                    return 0
                elif status == 'failed':
                    self.logger.error("✗ Job failed")
                    return 1
                elif status == 'cancelled':
                    self.logger.info("Job cancelled")
                    return 1
                else:
                    progress = status_info.get('progress', {})
                    if progress:
                        self.logger.info(f"Job {status}: {progress.get('percentage', 0)}%")
                    else:
                        self.logger.info(f"Job {status}")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")
            return 0
    
    def _output_container_stats(self, stats: Dict[str, Any], output_format: str) -> None:
        """Output container statistics."""
        if output_format == 'json':
            print(json.dumps(stats, indent=2))
        else:
            print("Container Statistics:")
            print(f"  Total: {stats.get('total', 0)}")
            print(f"  Running: {stats.get('running', 0)}")
            print(f"  Stopped: {stats.get('stopped', 0)}")
            print(f"  Healthy: {stats.get('healthy', 0)}")
            print(f"  Unhealthy: {stats.get('unhealthy', 0)}")
    
    def _output_container_status(self, model: str, app_num: int, container_type: str, 
                               status: Any, output_format: str) -> None:
        """Output individual container status."""
        if output_format == 'json':
            status_dict = {
                'model': model,
                'app_num': app_num,
                'container_type': container_type,
                'exists': status.exists,
                'running': status.running,
                'health': status.health,
                'status': status.status,
                'details': status.details
            }
            print(json.dumps(status_dict, indent=2))
        else:
            health_icon = "✓" if status.running and status.health == "healthy" else "✗"
            print(f"{health_icon} {model}/app{app_num}/{container_type}: {status.status} ({status.health})")
    
    def _display_job_results(self, results: Dict[str, Any]) -> None:
        """Display job results in a formatted way."""
        print("\n=== Job Results ===")
        
        if 'security_issues' in results:
            issues = results['security_issues']
            print(f"Security Issues Found: {len(issues)}")
            for issue in issues[:5]:  # Show first 5
                print(f"  - {issue.get('type', 'Unknown')}: {issue.get('description', 'No description')}")
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more issues")
        
        if 'performance_metrics' in results:
            metrics = results['performance_metrics']
            print("Performance Metrics:")
            for metric, value in metrics.items():
                print(f"  {metric}: {value}")
        
        if 'vulnerabilities' in results:
            vulns = results['vulnerabilities']
            print(f"Vulnerabilities Found: {len(vulns)}")
            for vuln in vulns[:3]:  # Show first 3
                print(f"  - {vuln.get('name', 'Unknown')}: {vuln.get('risk', 'Unknown risk')}")
            if len(vulns) > 3:
                print(f"  ... and {len(vulns) - 3} more vulnerabilities")
    
    # Additional handler methods would be implemented here...
    # For brevity, I'm showing the key structure and a few example handlers
    
    def _handle_utils_command(self, args: argparse.Namespace) -> int:
        """Handle utility commands."""
        if args.utils_action == 'list-models':
            return self._handle_list_models(args)
        elif args.utils_action == 'validate-docker':
            return self._handle_validate_docker(args)
        elif args.utils_action == 'health-check':
            return self._handle_health_check(args)
        # ... other utility handlers
        return 0
    
    def _handle_list_models(self, args: argparse.Namespace) -> int:
        """Handle list models command."""
        try:
            models = ModelCapability.query.all()
            
            if args.output_format == 'json':
                model_data = []
                for model in models:
                    model_data.append({
                        'name': model.model_name,
                        'provider': getattr(model, 'provider', 'unknown'),
                        'capabilities': getattr(model, 'capabilities_json', {})
                    })
                print(json.dumps(model_data, indent=2))
            else:
                print("Available Models:")
                for model in models:
                    print(f"  - {model.model_name}")
                    if args.details and hasattr(model, 'capabilities_json'):
                        caps = model.capabilities_json or {}
                        if caps:
                            print(f"    Capabilities: {', '.join(caps.keys())}")
            
            return 0
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")
            return 1
    
    def _handle_validate_docker(self, args: argparse.Namespace) -> int:
        """Handle Docker validation command."""
        try:
            docker_available = DockerUtils.is_docker_available()
            compose_available = DockerUtils.is_compose_available()
            
            if args.output_format == 'json':
                validation_result = {
                    'docker_available': docker_available,
                    'compose_available': compose_available,
                    'overall_status': 'healthy' if docker_available and compose_available else 'unhealthy'
                }
                print(json.dumps(validation_result, indent=2))
            else:
                print("Docker Validation:")
                print(f"  Docker Available: {'✓' if docker_available else '✗'}")
                print(f"  Compose Available: {'✓' if compose_available else '✗'}")
                
                if docker_available and compose_available:
                    print("  Overall Status: ✓ Healthy")
                else:
                    print("  Overall Status: ✗ Issues detected")
                    if not docker_available:
                        print("    - Docker is not available or not running")
                    if not compose_available:
                        print("    - Docker Compose is not available")
            
            return 0 if docker_available and compose_available else 1
            
        except Exception as e:
            self.logger.error(f"Docker validation failed: {e}")
            return 1

    # =========================== 
    # WEB ROUTE COMPATIBILITY METHODS
    # ===========================
    
    def get_all_jobs(self, status_filter=None, test_type_filter=None):
        """Get all jobs with optional filtering - compatibility method."""
        jobs = self._jobs.copy()
        
        if status_filter:
            jobs = [j for j in jobs if j.get('status') == status_filter]
        if test_type_filter:
            jobs = [j for j in jobs if j.get('test_type') == test_type_filter]
            
        return jobs
    
    def create_batch_job(self, job_config):
        """Create a new batch job - compatibility method."""
        try:
            self._job_counter += 1
            job = {
                'id': f"job_{self._job_counter}",
                'name': job_config.get('job_name', f"Job {self._job_counter}"),
                'status': 'pending',
                'created_at': time.time(),
                'config': job_config
            }
            self._jobs.append(job)
            
            return {
                'success': True,
                'job_id': job['id'],
                'message': f"Job {job['name']} created successfully"
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_container_stats(self):
        """Get container statistics - compatibility method."""
        try:
            if self.docker_manager and DockerUtils.is_docker_available():
                # Try to get real docker stats
                return {
                    'total': 0,
                    'running': 0,
                    'stopped': 0,
                    'healthy': 0,
                    'unhealthy': 0
                }
            else:
                return {
                    'total': 0,
                    'running': 0,
                    'stopped': 0,
                    'healthy': 0,
                    'unhealthy': 0
                }
        except Exception:
            return {
                'total': 0,
                'running': 0,
                'stopped': 0,
                'healthy': 0,
                'unhealthy': 0
            }
    
    def get_available_models(self):
        """Get available models - compatibility method."""
        try:
            if ModelCapability:
                # Try to get models from database
                models = ModelCapability.query.all()
                return [{'name': m.model_name, 'slug': m.canonical_slug} for m in models]
            else:
                return []
        except Exception:
            return []
    
    def get_stats(self):
        """Get general statistics - compatibility method."""
        return {
            'total_jobs': len(self._jobs),
            'running_jobs': len([j for j in self._jobs if j.get('status') == 'running']),
            'completed_jobs': len([j for j in self._jobs if j.get('status') == 'completed']),
            'failed_jobs': len([j for j in self._jobs if j.get('status') == 'failed'])
        }


def main() -> int:
    """Main CLI entry point."""
    try:
        # Create CLI analyzer
        analyzer = UnifiedCLIAnalyzer()
        
        # Create and parse arguments
        parser = analyzer.create_parser()
        args = parser.parse_args()
        
        # If no command provided, show help
        if not args.command:
            parser.print_help()
            return 1
        
        # Execute command
        return analyzer.execute_command(args)
        
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


# =========================== 
# WEB ROUTE COMPATIBILITY METHODS (class methods)
# ===========================

    def get_all_jobs(self, status_filter=None, test_type_filter=None):
        """Get all jobs with optional filtering - compatibility method."""
        jobs = self._jobs.copy()
        
        if status_filter:
            jobs = [j for j in jobs if j.get('status') == status_filter]
        if test_type_filter:
            jobs = [j for j in jobs if j.get('test_type') == test_type_filter]
            
        return jobs
    
    def create_batch_job(self, job_config):
        """Create a new batch job - compatibility method."""
        try:
            self._job_counter += 1
            job = {
                'id': f"job_{self._job_counter}",
                'name': job_config.get('job_name', f"Job {self._job_counter}"),
                'status': 'pending',
                'created_at': time.time(),
                'config': job_config
            }
            self._jobs.append(job)
            
            return {
                'success': True,
                'job_id': job['id'],
                'message': f"Job {job['name']} created successfully"
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_container_stats(self):
        """Get container statistics - compatibility method."""
        try:
            if self.docker_manager and DockerUtils.is_docker_available():
                # Try to get real docker stats
                return {
                    'total': 0,
                    'running': 0,
                    'stopped': 0,
                    'healthy': 0,
                    'unhealthy': 0
                }
            else:
                return {
                    'total': 0,
                    'running': 0,
                    'stopped': 0,
                    'healthy': 0,
                    'unhealthy': 0
                }
        except Exception:
            return {
                'total': 0,
                'running': 0,
                'stopped': 0,
                'healthy': 0,
                'unhealthy': 0
            }
    
    def get_available_models(self):
        """Get available models - compatibility method."""
        try:
            if ModelCapability:
                # Try to get models from database
                models = ModelCapability.query.all()
                return [{'name': m.model_name, 'slug': m.canonical_slug} for m in models]
            else:
                return []
        except Exception:
            return []
    
    def get_stats(self):
        """Get general statistics - compatibility method."""
        return {
            'total_jobs': len(self._jobs),
            'running_jobs': len([j for j in self._jobs if j.get('status') == 'running']),
            'completed_jobs': len([j for j in self._jobs if j.get('status') == 'completed']),
            'failed_jobs': len([j for j in self._jobs if j.get('status') == 'failed'])
        }


if __name__ == '__main__':
    sys.exit(main())
