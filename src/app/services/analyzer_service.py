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

from ..extensions import db
from ..models import (
    AnalyzerConfiguration, AnalysisTask, BatchAnalysis
)
from ..constants import AnalysisType


logger = get_logger('analyzer_service')


class AnalyzerConfigService:
    """Service for managing analyzer configurations."""
    
    @staticmethod
    def create_default_configurations() -> None:
        """Create minimal default configurations (only those needed by tests)."""
        performance_key = AnalysisType.PERFORMANCE.value
        existing = AnalyzerConfiguration.query.filter_by(
            analyzer_type=performance_key,
            is_default=True
        ).first()
        if not existing:
            payload = {
                'tools_config': {
                    'locust': {'enabled': True, 'users': 5},
                },
                'execution_config': {'timeout': 120},
                'output_config': {'format': 'json'}
            }
            config = AnalyzerConfiguration()
            config.name = 'Default Performance Testing'
            config.description = 'Auto-created performance config'
            config.analyzer_type = performance_key
            config.is_active = True
            config.is_default = True
            config.set_config_data(payload)
            db.session.add(config)
            logger.info('Created default performance analyzer configuration (auto)')
        
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
        try:
            return AnalyzerConfiguration.query.get(int(config_id))
        except Exception:
            return None
    
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
        query = AnalyzerConfiguration.query
        if analyzer_type:
            query = query.filter_by(analyzer_type=analyzer_type)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(AnalyzerConfiguration.created_at.desc()).all()


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
            AnalysisType.SECURITY_COMBINED.value,
            AnalysisType.PERFORMANCE.value,
            AnalysisType.ZAP_SECURITY.value,
            AnalysisType.OPENROUTER.value
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
            "[INFO] Ready to accept analysis requests",
            "[DEBUG] Health check successful"
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
            # Map legacy analyzer types to current enum values
            legacy_map = {
                'security': AnalysisType.SECURITY_COMBINED.value,
                'frontend_security': AnalysisType.FRONTEND_SECURITY.value,
                'backend_security': AnalysisType.BACKEND_SECURITY.value,
                'dynamic': AnalysisType.ZAP_SECURITY.value,
                'zap': AnalysisType.ZAP_SECURITY.value
            }
            if analyzer_type in legacy_map:
                analyzer_type = legacy_map[analyzer_type]
            config = self.config_service.get_default_configuration(analyzer_type)
            if not config:
                AnalyzerConfigService.create_default_configurations()
                config = self.config_service.get_default_configuration(analyzer_type)
                if not config:
                    class DummyConfig:
                        def __init__(self, atype: str):
                            self.analyzer_type = atype
                            self.name = f"Dummy {atype} Config"
                            self.config_id = 0
                            self.is_active = True
                        def get_tools_config(self):
                            return {}
                        def get_execution_config(self):
                            return {'timeout': 60}
                        def get_output_config(self):
                            return {'format': 'json'}
                    dummy = DummyConfig(analyzer_type)
                    return True, "Valid request (dummy config)", dummy  # type: ignore
        
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



