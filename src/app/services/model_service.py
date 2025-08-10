"""
Model Service
============

Service for managing AI model data and capabilities.
Provides database-first access to model information.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict

from flask import Flask

from app.models import db, ModelCapability, PortConfiguration, GeneratedApplication


class ModelService:
    """Service for managing AI model data and operations."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.config = app.config
        
    def get_all_models(self, provider: Optional[str] = None) -> List[ModelCapability]:
        """Get all models, optionally filtered by provider."""
        query = ModelCapability.query
        if provider:
            query = query.filter_by(provider=provider)
        return query.all()
    
    def get_model_by_slug(self, model_slug: str) -> Optional[ModelCapability]:
        """Get a specific model by its slug."""
        return ModelCapability.query.filter_by(model_slug=model_slug).first()
    
    def get_providers(self) -> List[str]:
        """Get list of all available providers."""
        return [provider[0] for provider in db.session.query(ModelCapability.provider).distinct()]
    
    def get_model_apps(self, model_slug: str) -> List[GeneratedApplication]:
        """Get all applications for a specific model."""
        return GeneratedApplication.query.filter_by(model_slug=model_slug).all()
    
    def get_app(self, model_slug: str, app_number: int) -> Optional[GeneratedApplication]:
        """Get a specific application."""
        return GeneratedApplication.query.filter_by(
            model_slug=model_slug, 
            app_number=app_number
        ).first()
    
    def get_app_ports(self, model_slug: str, app_number: int) -> Optional[PortConfiguration]:
        """Get port configuration for an application."""
        return PortConfiguration.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
    
    def sync_from_files(self) -> Dict[str, int]:
        """
        Sync database from JSON files in misc/ directory.
        Returns count of synced records.
        """
        synced = {'models': 0, 'ports': 0, 'apps': 0}
        
        # Sync model capabilities
        capabilities_file = Path(self.config['MODEL_CAPABILITIES_FILE'])
        if capabilities_file.exists():
            synced['models'] = self._sync_model_capabilities(capabilities_file)
        
        # Sync port configurations
        port_config_file = Path(self.config['PORT_CONFIG_FILE'])
        if port_config_file.exists():
            synced['ports'] = self._sync_port_configurations(port_config_file)
        
        # Sync generated applications
        models_dir = Path(self.config['MODELS_DIR'])
        if models_dir.exists():
            synced['apps'] = self._sync_generated_applications(models_dir)
        
        return synced
    
    def _sync_model_capabilities(self, file_path: Path) -> int:
        """Sync model capabilities from JSON file."""
        with open(file_path) as f:
            data = json.load(f)
        
        count = 0
        models_data = data.get('models', {})
        
        for model_slug, model_info in models_data.items():
            # Check if model exists
            existing = ModelCapability.query.filter_by(model_slug=model_slug).first()
            
            if not existing:
                # Create new model
                model = ModelCapability(
                    model_slug=model_slug,
                    provider=model_info.get('provider', 'unknown'),
                    model_name=model_info.get('name', model_slug),
                    display_name=model_info.get('display_name'),
                    supports_vision=model_info.get('supports_vision', False),
                    supports_function_calling=model_info.get('supports_function_calling', False),
                    is_free=model_info.get('is_free', False),
                    input_price=model_info.get('pricing', {}).get('input'),
                    output_price=model_info.get('pricing', {}).get('output'),
                    context_length=model_info.get('context_length'),
                    max_output_tokens=model_info.get('max_output_tokens')
                )
                db.session.add(model)
                count += 1
        
        db.session.commit()
        return count
    
    def _sync_port_configurations(self, file_path: Path) -> int:
        """Sync port configurations from JSON file."""
        with open(file_path) as f:
            port_configs = json.load(f)
        
        count = 0
        for config in port_configs:
            # Check if configuration exists
            existing = PortConfiguration.query.filter_by(
                model_slug=config['model_name'],
                app_number=config['app_number']
            ).first()
            
            if not existing:
                port_config = PortConfiguration(
                    model_slug=config['model_name'],
                    app_number=config['app_number'],
                    backend_port=config['backend_port'],
                    frontend_port=config['frontend_port']
                )
                db.session.add(port_config)
                count += 1
        
        db.session.commit()
        return count
    
    def _sync_generated_applications(self, models_dir: Path) -> int:
        """Scan models directory and sync generated applications."""
        count = 0
        
        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir():
                continue
                
            model_slug = model_dir.name
            
            # Find app directories
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue
                
                try:
                    app_number = int(app_dir.name.replace('app', ''))
                except ValueError:
                    continue
                
                # Check if app exists in database
                existing = GeneratedApplication.query.filter_by(
                    model_slug=model_slug,
                    app_number=app_number
                ).first()
                
                if not existing:
                    # Extract provider from model_slug
                    provider = model_slug.split('_')[0] if '_' in model_slug else 'unknown'
                    
                    app = GeneratedApplication(
                        model_slug=model_slug,
                        app_number=app_number,
                        provider=provider,
                        backend_path=str(app_dir / 'backend'),
                        frontend_path=str(app_dir / 'frontend'),
                        docker_compose_path=str(app_dir / 'docker-compose.yml')
                    )
                    db.session.add(app)
                    count += 1
        
        db.session.commit()
        return count
