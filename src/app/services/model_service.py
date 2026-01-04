"""
Model Service
============

Service for managing AI model data and capabilities.
Provides database-first access to model information with JSON file synchronization.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from flask import Flask

from app.models import db, ModelCapability, PortConfiguration, GeneratedApplication
from app.paths import PORT_CONFIG_JSON, GENERATED_APPS_DIR

logger = logging.getLogger(__name__)


class ModelService:
    """Service for managing AI model data and operations."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.config = app.config
        self.logger = logger
        
    def get_all_models(self, provider: Optional[str] = None) -> List[ModelCapability]:
        """Get all models, optionally filtered by provider."""
        query = ModelCapability.query
        if provider:
            query = query.filter_by(provider=provider)
        return query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
    
    def get_used_models(self, provider: Optional[str] = None) -> List[ModelCapability]:
        """Get only models that have generated applications (used models)."""
        query = (
            ModelCapability.query
            .join(GeneratedApplication, ModelCapability.canonical_slug == GeneratedApplication.model_slug)
            .distinct()
        )
        if provider:
            query = query.filter(ModelCapability.provider == provider)
        return query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
    
    def get_used_providers(self) -> List[str]:
        """Get list of providers that have models with generated applications."""
        return [
            provider[0] for provider in 
            db.session.query(ModelCapability.provider)
            .join(GeneratedApplication, ModelCapability.canonical_slug == GeneratedApplication.model_slug)
            .distinct()
            .order_by(ModelCapability.provider)
        ]
    
    def get_model_by_slug(self, canonical_slug: str) -> Optional[ModelCapability]:
        """Get a specific model by its canonical slug."""
        return ModelCapability.query.filter_by(canonical_slug=canonical_slug).first()
    
    def get_model_by_id(self, model_id: str) -> Optional[ModelCapability]:
        """Get a specific model by its model ID."""
        return ModelCapability.query.filter_by(model_id=model_id).first()
    
    def get_providers(self) -> List[str]:
        """Get list of all available providers."""
        return [provider[0] for provider in db.session.query(ModelCapability.provider).distinct()]
    
    def get_model_apps(self, canonical_slug: str) -> List[GeneratedApplication]:
        """Get all applications for a specific model with live Docker status detection."""
        apps = GeneratedApplication.query.filter_by(model_slug=canonical_slug).all()
        
        # Apply live Docker status detection using the status cache (not direct Docker API)
        try:
            from .service_locator import ServiceLocator
            status_cache = ServiceLocator.get_docker_status_cache()
            
            if status_cache:
                # Prepare list of (model_slug, app_number) tuples for bulk lookup
                apps_list = [(app.model_slug, app.app_number) for app in apps]
                
                # Use bulk status lookup (single Docker API call, cached)
                bulk_status = status_cache.get_bulk_status(apps_list)  # type: ignore[union-attr]
                
                # Update each app's container status based on cache results
                for app in apps:
                    key = (app.model_slug, app.app_number)
                    cache_entry = bulk_status.get(key)
                    
                    if cache_entry:
                        # Update the app's status (without committing to DB - cache handles persistence)
                        app.container_status = cache_entry.status
        except Exception as e:
            # If Docker status detection fails, fall back to DB status
            self.logger.warning(f"Docker status detection failed for model {canonical_slug}: {e}")
        
        # Sort naturally by app_number (1, 2, 3, ... 10, 11, ... instead of 1, 10, 11, ... 2, 3)
        return sorted(apps, key=lambda app: app.app_number)
    
    def get_app(self, canonical_slug: str, app_number: int) -> Optional[GeneratedApplication]:
        """Get a specific application."""
        return GeneratedApplication.query.filter_by(
            model_slug=canonical_slug, 
            app_number=app_number
        ).first()
    
    def get_app_ports(self, model_slug: str, app_number: int) -> Optional[Dict[str, Any]]:
        """Get port configuration for an application.

        Returns a canonical dict with keys: { 'frontend', 'backend', 'is_available' } or None.
        """
        # Try exact match first
        pc = PortConfiguration.query.filter_by(model=model_slug, app_num=app_number).first()
        if pc:
            return {
                'frontend': pc.frontend_port,
                'backend': pc.backend_port,
                'is_available': bool(pc.is_available)
            }

        # Try matching via ModelCapability (some codepaths store the model name differently)
        try:
            model_cap = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        except Exception:
            model_cap = None

        if model_cap:
            # Try the model_name stored in ModelCapability
            if getattr(model_cap, 'model_name', None):
                pc = PortConfiguration.query.filter_by(model=model_cap.model_name, app_num=app_number).first()
                if pc:
                    return {
                        'frontend': pc.frontend_port,
                        'backend': pc.backend_port,
                        'is_available': bool(pc.is_available)
                    }

            # Also try the canonical slug stored on the capability
            if getattr(model_cap, 'canonical_slug', None):
                pc = PortConfiguration.query.filter_by(model=model_cap.canonical_slug, app_num=app_number).first()
                if pc:
                    return {
                        'frontend': pc.frontend_port,
                        'backend': pc.backend_port,
                        'is_available': bool(pc.is_available)
                    }

        # Try some common normalizations (dash/underscore/space variations)
        candidates = set([
            model_slug.replace('-', '_'),
            model_slug.replace('_', '-'),
            model_slug.replace(' ', '_'),
            model_slug.replace(' ', '-')
        ])
        for cand in candidates:
            if not cand:
                continue
            pc = PortConfiguration.query.filter_by(model=cand, app_num=app_number).first()
            if pc:
                return {
                    'frontend': pc.frontend_port,
                    'backend': pc.backend_port,
                    'is_available': bool(pc.is_available)
                }

        # Final fallback: compare normalized alphanumeric forms across all PortConfiguration
        # entries for this app number. This handles mixed separators (.-_) and minor
        # canonicalization differences introduced by different import formats.
        def _normalize_alnum(s: str) -> str:
            return re.sub(r'[^0-9a-z]+', '', (s or '').lower())

        norm_target = _normalize_alnum(model_slug)
        if norm_target:
            pcs = PortConfiguration.query.filter_by(app_num=app_number).all()
            for pc in pcs:
                if _normalize_alnum(pc.model) == norm_target:
                    return {
                        'frontend': pc.frontend_port,
                        'backend': pc.backend_port,
                        'is_available': bool(pc.is_available)
                    }

        # Nothing found — log for diagnostics
        self.logger.debug(f"PortConfiguration not found for model_slug='{model_slug}' app_number={app_number}")
        return None
    
    def populate_database_from_files(self) -> Dict[str, int]:
        """
        Populate database from JSON files in misc/ directory.
        Returns count of created/updated records.
        """
        populated = {'models': 0, 'ports': 0, 'apps': 0}
        
        try:
            # Legacy model capabilities loading is deprecated - models now loaded from OpenRouter API
            self.logger.info("Legacy model capabilities loading skipped - using OpenRouter API")
            
            # Populate port configurations  
            port_config_file = PORT_CONFIG_JSON
            if port_config_file.exists():
                populated['ports'] = self._populate_port_configurations(port_config_file)
                self.logger.info(f"Populated {populated['ports']} port configurations")
            
            # Scan for generated applications
            # New unified structure lives under generated/apps
            models_dir = GENERATED_APPS_DIR
            if models_dir.exists():
                populated['apps'] = self._populate_generated_applications(models_dir)
                self.logger.info(f"Populated {populated['apps']} generated applications")
                
        except Exception as e:
            self.logger.error(f"Error populating database from files: {e}")
            raise
        
        return populated
    
    def _populate_port_configurations(self, file_path: Path) -> int:
        """Populate port configurations from JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            port_configs = json.load(f)
        
        count = 0
        for config in port_configs:
            # Check if configuration exists
            existing = PortConfiguration.query.filter_by(
                model=config['model_name'],
                app_num=config['app_number']
            ).first()
            
            if not existing:
                port_config = PortConfiguration()
                port_config.model = config['model_name']
                port_config.app_num = config['app_number']
                port_config.backend_port = config['backend_port']
                port_config.frontend_port = config['frontend_port']
                db.session.add(port_config)
                count += 1
        
        db.session.commit()
        return count
    
    def _populate_generated_applications(self, models_dir: Path) -> int:
        """Scan models directory and populate generated applications."""
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
                    
                    # Determine app type and frameworks by checking directories
                    has_backend = (app_dir / 'backend').exists()
                    has_frontend = (app_dir / 'frontend').exists() 
                    has_docker_compose = (app_dir / 'docker-compose.yml').exists()
                    
                    # Detect frameworks (basic detection)
                    backend_framework = None
                    frontend_framework = None
                    
                    if has_backend:
                        if (app_dir / 'backend' / 'requirements.txt').exists():
                            backend_framework = 'python'
                        elif (app_dir / 'backend' / 'package.json').exists():
                            backend_framework = 'node'
                    
                    if has_frontend:
                        if (app_dir / 'frontend' / 'package.json').exists():
                            frontend_framework = 'react'  # Default assumption
                        elif (app_dir / 'frontend' / 'index.html').exists():
                            frontend_framework = 'vanilla'
                    
                    app = GeneratedApplication()
                    app.model_slug = model_slug
                    app.app_number = app_number
                    app.app_type = (
                        'fullstack' if has_backend and has_frontend
                        else 'backend' if has_backend
                        else 'frontend'
                    )
                    app.provider = provider
                    app.has_backend = has_backend
                    app.has_frontend = has_frontend
                    app.has_docker_compose = has_docker_compose
                    app.backend_framework = backend_framework
                    app.frontend_framework = frontend_framework
                    app.container_status = 'stopped'
                    
                    # Store additional metadata
                    metadata = {
                        'directory_path': str(app_dir),
                        'backend_path': str(app_dir / 'backend') if has_backend else None,
                        'frontend_path': str(app_dir / 'frontend') if has_frontend else None,
                        'docker_compose_path': str(app_dir / 'docker-compose.yml') if has_docker_compose else None
                    }
                    app.set_metadata(metadata)
                    
                    db.session.add(app)
                    count += 1
        
        db.session.commit()
        return count

    def get_model_summary(self) -> Dict[str, Any]:
        """Get summary of all models (equivalent to models_summary.json)."""
        models = self.get_all_models()
        
        # Group by provider for color assignment
        provider_colors = {
            'anthropic': '#D97706',
            'openai': '#14B8A6', 
            'google': '#3B82F6',
            'deepseek': '#9333EA',
            'mistralai': '#8B5CF6',
            'qwen': '#F43F5E',
            'minimax': '#7E22CE',
            'x-ai': '#B91C1C',
            'moonshotai': '#10B981',
            'nvidia': '#0D9488',
            'nousresearch': '#059669'
        }
        
        summary = {
            'extraction_timestamp': datetime.now(timezone.utc).isoformat(),
            'total_models': len(models),
            'apps_per_model': 30,  # Assuming 30 apps per model
            'models': []
        }
        
        for model in models:
            model_entry = {
                'name': model.canonical_slug,
                'color': provider_colors.get(model.provider, '#666666'),
                'provider': model.provider
            }
            summary['models'].append(model_entry)
        
        return summary
