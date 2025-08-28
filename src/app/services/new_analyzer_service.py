"""
Analyzer Configuration and Management Service
============================================

Modern service for managing analyzer configurations, tool settings, and analyzer lifecycle.
Supports multiple analyzer types with flexible configuration profiles.
"""

from app.utils.logging_config import get_logger
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..extensions import db
# Temporarily commented out due to missing models
# from ..models import (
#     AnalyzerConfiguration, AnalysisType, AnalysisTask, BatchAnalysis
# )


logger = get_logger('analyzer_service')


class AnalyzerConfigService:
    """Service for managing analyzer configurations."""
    
    @staticmethod
    def create_default_configurations() -> None:
        """Create default analyzer configurations if they don't exist."""
        default_configs = [
            {
                'name': 'Default Security Analysis',
                'analyzer_type': AnalysisType.SECURITY.value,
                'description': 'Standard security analysis with common tools',
                'tools_config': {
                    'bandit': {
                        'enabled': True,
                        'severity_level': 'LOW',
                        'confidence_level': 'LOW',
                        'exclude_tests': True,
                        'skip_paths': ['*/tests/*', '*/test_*']
                    },
                    'safety': {
                        'enabled': True,
                        'check_dependencies': True,
                        'ignore_ids': []
                    },
                    'semgrep': {
                        'enabled': True,
                        'rulesets': ['owasp-top-10', 'cwe-top-25'],
                        'severity_threshold': 'INFO'
                    }
                },
                'execution_config': {
                    'timeout': 600,
                    'max_memory': '1GB',
                    'parallel_execution': True,
                    'fail_fast': False
                },
                'output_config': {
                    'format': 'json',
                    'include_code_snippets': True,
                    'max_snippet_lines': 10,
                    'group_by_severity': True
                },
                'is_default': True
            },
            {
                'name': 'Default Performance Testing',
                'analyzer_type': AnalysisType.PERFORMANCE.value,
                'description': 'Standard performance testing configuration',
                'tools_config': {
                    'locust': {
                        'enabled': True,
                        'users': 10,
                        'spawn_rate': 2,
                        'run_time': '2m',
                        'host': 'http://localhost:5000'
                    },
                    'lighthouse': {
                        'enabled': True,
                        'categories': ['performance', 'accessibility', 'best-practices'],
                        'throttling': 'simulated3G'
                    }
                },
                'execution_config': {
                    'timeout': 300,
                    'warmup_time': 30,
                    'cooldown_time': 10,
                    'retry_on_failure': True,
                    'max_retries': 3
                },
                'output_config': {
                    'format': 'json',
                    'include_raw_metrics': True,
                    'generate_charts': True,
                    'percentiles': [50, 90, 95, 99]
                },
                'is_default': True
            },
            {
                'name': 'Default Static Analysis',
                'analyzer_type': AnalysisType.STATIC.value,
                'description': 'Code quality and static analysis',
                'tools_config': {
                    'pylint': {
                        'enabled': True,
                        'rcfile': None,
                        'disable': ['C0114', 'C0115', 'C0116'],  # Missing docstrings
                        'score_threshold': 7.0
                    },
                    'flake8': {
                        'enabled': True,
                        'max_line_length': 100,
                        'ignore': ['E203', 'W503'],
                        'exclude': ['*/migrations/*', '*/venv/*']
                    },
                    'mypy': {
                        'enabled': True,
                        'strict_mode': False,
                        'ignore_missing_imports': True
                    }
                },
                'execution_config': {
                    'timeout': 300,
                    'parallel_execution': True,
                    'continue_on_error': True
                },
                'output_config': {
                    'format': 'json',
                    'include_metrics': True,
                    'group_by_file': True,
                    'sort_by_severity': True
                },
                'is_default': True
            },
            {
                'name': 'Default Dynamic Analysis',
                'analyzer_type': AnalysisType.DYNAMIC.value,
                'description': 'Runtime security and vulnerability testing',
                'tools_config': {
                    'zap': {
                        'enabled': True,
                        'spider_enabled': True,
                        'active_scan_enabled': True,
                        'spider_max_children': 10,
                        'active_scan_policy': 'Default Policy',
                        'exclude_urls': []
                    },
                    'nikto': {
                        'enabled': False,  # Optional secondary tool
                        'scan_type': 'basic',
                        'timeout': 600
                    }
                },
                'execution_config': {
                    'timeout': 1800,
                    'startup_wait': 60,
                    'scan_delay': 5,
                    'max_alerts': 1000
                },
                'output_config': {
                    'format': 'json',
                    'include_request_response': True,
                    'group_by_risk': True,
                    'filter_false_positives': True
                },
                'is_default': True
            },
            {
                'name': 'Default AI Code Review',
                'analyzer_type': AnalysisType.AI_REVIEW.value,
                'description': 'AI-powered code analysis and review',
                'tools_config': {
                    'openrouter': {
                        'enabled': True,
                        'model': 'anthropic/claude-3-sonnet',
                        'temperature': 0.2,
                        'max_tokens': 4000
                    },
                    'analysis_types': [
                        'code_quality',
                        'security_review',
                        'performance_analysis',
                        'best_practices',
                        'documentation_review'
                    ]
                },
                'execution_config': {
                    'timeout': 600,
                    'chunk_size': 2000,
                    'overlap_size': 200,
                    'rate_limit_delay': 1
                },
                'output_config': {
                    'format': 'json',
                    'include_explanations': True,
                    'include_suggestions': True,
                    'confidence_threshold': 0.7
                },
                'is_default': True
            }
        ]
        
        for config_data in default_configs:
            existing = AnalyzerConfiguration.query.filter_by(
                analyzer_type=config_data['analyzer_type'],
                is_default=True
            ).first()
            
            if not existing:
                config = AnalyzerConfiguration(**config_data)
                db.session.add(config)
                logger.info(f"Created default configuration for {config_data['analyzer_type']}")
        
        try:
            db.session.commit()
            logger.info("Default analyzer configurations created successfully")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create default configurations: {e}")
            raise
    
    @staticmethod
    def get_configuration(config_id: str) -> Optional[AnalyzerConfiguration]:
        """Get configuration by ID."""
        return AnalyzerConfiguration.query.filter_by(config_id=config_id).first()
    
    @staticmethod
    def get_default_configuration(analyzer_type: str) -> Optional[AnalyzerConfiguration]:
        """Get default configuration for analyzer type."""
        return AnalyzerConfiguration.query.filter_by(
            analyzer_type=analyzer_type,
            is_default=True,
            is_active=True
        ).first()
    
    @staticmethod
    def list_configurations(
        analyzer_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[AnalyzerConfiguration]:
        """List analyzer configurations."""
        query = AnalyzerConfiguration.query
        
        if analyzer_type:
            query = query.filter_by(analyzer_type=analyzer_type)
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        return query.order_by(AnalyzerConfiguration.is_default.desc(), AnalyzerConfiguration.name).all()
    
    @staticmethod
    def create_configuration(
        name: str,
        analyzer_type: str,
        description: str = None,
        tools_config: Dict[str, Any] = None,
        execution_config: Dict[str, Any] = None,
        output_config: Dict[str, Any] = None,
        is_default: bool = False
    ) -> AnalyzerConfiguration:
        """Create new analyzer configuration."""
        config = AnalyzerConfiguration(
            name=name,
            analyzer_type=analyzer_type,
            description=description,
            is_default=is_default
        )
        
        if tools_config:
            config.set_tools_config(tools_config)
        if execution_config:
            config.set_execution_config(execution_config)
        if output_config:
            config.set_output_config(output_config)
        
        db.session.add(config)
        db.session.commit()
        
        logger.info(f"Created analyzer configuration: {name} ({analyzer_type})")
        return config
    
    @staticmethod
    def update_configuration(
        config_id: str,
        **updates
    ) -> Optional[AnalyzerConfiguration]:
        """Update analyzer configuration."""
        config = AnalyzerConfigService.get_configuration(config_id)
        if not config:
            return None
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
            elif key == 'tools_config':
                config.set_tools_config(value)
            elif key == 'execution_config':
                config.set_execution_config(value)
            elif key == 'output_config':
                config.set_output_config(value)
        
        db.session.commit()
        logger.info(f"Updated analyzer configuration: {config.name}")
        return config
    
    @staticmethod
    def delete_configuration(config_id: str) -> bool:
        """Delete analyzer configuration."""
        config = AnalyzerConfigService.get_configuration(config_id)
        if not config:
            return False
        
        if config.is_default:
            raise ValueError("Cannot delete default configuration")
        
        db.session.delete(config)
        db.session.commit()
        
        logger.info(f"Deleted analyzer configuration: {config.name}")
        return True
    
    @staticmethod
    def clone_configuration(
        config_id: str,
        new_name: str,
        description: str = None
    ) -> Optional[AnalyzerConfiguration]:
        """Clone an existing configuration."""
        original = AnalyzerConfigService.get_configuration(config_id)
        if not original:
            return None
        
        cloned = AnalyzerConfiguration(
            name=new_name,
            analyzer_type=original.analyzer_type,
            description=description or f"Copy of {original.name}",
            is_default=False,
            is_active=True,
            version="1.0.0"
        )
        
        cloned.set_tools_config(original.get_tools_config())
        cloned.set_execution_config(original.get_execution_config())
        cloned.set_output_config(original.get_output_config())
        
        db.session.add(cloned)
        db.session.commit()
        
        logger.info(f"Cloned configuration: {original.name} -> {new_name}")
        return cloned


class AnalyzerLifecycleService:
    """Service for managing analyzer lifecycle and health."""
    
    def __init__(self):
        self.analyzer_status = {}
        self.last_health_check = {}
    
    def check_analyzer_health(self, analyzer_type: str) -> Dict[str, Any]:
        """Check health of specific analyzer service."""
        # This would integrate with the actual analyzer services
        # For now, return mock data
        health_status = {
            'analyzer_type': analyzer_type,
            'status': 'healthy',
            'last_check': datetime.now(timezone.utc).isoformat(),
            'response_time': 150,
            'version': '1.0.0',
            'capabilities': [],
            'resource_usage': {
                'cpu_percent': 25.0,
                'memory_mb': 512,
                'disk_usage_mb': 1024
            }
        }
        
        self.analyzer_status[analyzer_type] = health_status
        self.last_health_check[analyzer_type] = datetime.now(timezone.utc)
        
        return health_status
    
    def get_all_analyzer_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all analyzer services."""
        analyzer_types = [
            AnalysisType.SECURITY.value,
            AnalysisType.PERFORMANCE.value,
            AnalysisType.STATIC.value,
            AnalysisType.DYNAMIC.value,
            AnalysisType.AI_REVIEW.value
        ]
        
        status_map = {}
        for analyzer_type in analyzer_types:
            status_map[analyzer_type] = self.check_analyzer_health(analyzer_type)
        
        return status_map
    
    def start_analyzer(self, analyzer_type: str) -> Dict[str, Any]:
        """Start analyzer service."""
        # This would integrate with Docker/container management
        logger.info(f"Starting analyzer service: {analyzer_type}")
        
        return {
            'analyzer_type': analyzer_type,
            'action': 'start',
            'status': 'starting',
            'message': f'{analyzer_type} analyzer service is starting...'
        }
    
    def stop_analyzer(self, analyzer_type: str) -> Dict[str, Any]:
        """Stop analyzer service."""
        # This would integrate with Docker/container management
        logger.info(f"Stopping analyzer service: {analyzer_type}")
        
        return {
            'analyzer_type': analyzer_type,
            'action': 'stop',
            'status': 'stopping',
            'message': f'{analyzer_type} analyzer service is stopping...'
        }
    
    def restart_analyzer(self, analyzer_type: str) -> Dict[str, Any]:
        """Restart analyzer service."""
        logger.info(f"Restarting analyzer service: {analyzer_type}")
        
        return {
            'analyzer_type': analyzer_type,
            'action': 'restart',
            'status': 'restarting',
            'message': f'{analyzer_type} analyzer service is restarting...'
        }
    
    def get_analyzer_logs(self, analyzer_type: str, lines: int = 100) -> List[str]:
        """Get recent logs from analyzer service."""
        # This would integrate with actual log retrieval
        logger.info(f"Retrieving logs for {analyzer_type} (last {lines} lines)")
        
        # Mock log data
        return [
            f"[INFO] {analyzer_type} analyzer service started",
            f"[INFO] Loaded configuration for {analyzer_type}",
            f"[INFO] Ready to accept analysis requests",
            f"[DEBUG] Health check successful"
        ]


class AnalyzerManagerService:
    """High-level service for coordinating analyzer operations."""
    
    def __init__(self):
        self.config_service = AnalyzerConfigService()
        self.lifecycle_service = AnalyzerLifecycleService()
    
    def validate_analysis_request(
        self,
        analyzer_type: str,
        model_slug: str,
        app_number: int,
        config_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[AnalyzerConfiguration]]:
        """Validate analysis request and return configuration."""
        # Check if analyzer type is valid
        valid_types = [t.value for t in AnalysisType]
        if analyzer_type not in valid_types:
            return False, f"Invalid analyzer type: {analyzer_type}", None
        
        # Get configuration
        if config_id:
            config = self.config_service.get_configuration(config_id)
            if not config:
                return False, f"Configuration not found: {config_id}", None
            if config.analyzer_type != analyzer_type:
                return False, f"Configuration type mismatch: {config.analyzer_type} != {analyzer_type}", None
        else:
            config = self.config_service.get_default_configuration(analyzer_type)
            if not config:
                return False, f"No default configuration found for {analyzer_type}", None
        
        # Check if configuration is active
        if not config.is_active:
            return False, f"Configuration is inactive: {config.name}", None
        
        # Validate model and app (would integrate with actual validation)
        if not model_slug or not isinstance(app_number, int) or app_number < 1:
            return False, "Invalid model_slug or app_number", None
        
        return True, "Valid request", config
    
    def prepare_analysis_config(
        self,
        config: AnalyzerConfiguration,
        model_slug: str,
        app_number: int,
        custom_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare complete analysis configuration."""
        analysis_config = {
            'analyzer_type': config.analyzer_type,
            'config_id': config.config_id,
            'config_name': config.name,
            'model_slug': model_slug,
            'app_number': app_number,
            'tools_config': config.get_tools_config(),
            'execution_config': config.get_execution_config(),
            'output_config': config.get_output_config(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Apply custom options if provided
        if custom_options:
            analysis_config['custom_options'] = custom_options
            
            # Allow overriding specific config sections
            if 'tools_config' in custom_options:
                tools_config = analysis_config['tools_config'].copy()
                tools_config.update(custom_options['tools_config'])
                analysis_config['tools_config'] = tools_config
            
            if 'execution_config' in custom_options:
                exec_config = analysis_config['execution_config'].copy()
                exec_config.update(custom_options['execution_config'])
                analysis_config['execution_config'] = exec_config
        
        return analysis_config
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get comprehensive system overview."""
        # Get analyzer status
        analyzer_status = self.lifecycle_service.get_all_analyzer_status()
        
        # Get configuration counts
        config_counts = {}
        for analyzer_type in [t.value for t in AnalysisType]:
            configs = self.config_service.list_configurations(analyzer_type)
            config_counts[analyzer_type] = len(configs)
        
        # Get recent activity (would integrate with actual task data)
        recent_tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(10).all()
        recent_batches = BatchAnalysis.query.order_by(BatchAnalysis.created_at.desc()).limit(5).all()
        
        return {
            'analyzer_status': analyzer_status,
            'configuration_counts': config_counts,
            'recent_tasks': [task.to_dict() for task in recent_tasks],
            'recent_batches': [batch.to_dict() for batch in recent_batches],
            'system_health': {
                'overall_status': 'healthy',
                'active_analyzers': len([s for s in analyzer_status.values() if s['status'] == 'healthy']),
                'total_analyzers': len(analyzer_status),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
        }


# Initialize service instances
analyzer_config_service = AnalyzerConfigService()
analyzer_lifecycle_service = AnalyzerLifecycleService()
analyzer_manager_service = AnalyzerManagerService()



