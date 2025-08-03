#!/usr/bin/env python3
"""
Database Initialization Script for Thesis Research App

This script initializes the database with model capabilities, port configurations,
and sample data for the thesis research application analyzing AI-generated apps.

Usage:
    cd src/data
    python init_db.py
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Ensure we're in the right directory and set up paths
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
src_dir = project_root / "src"

# Add source directory to Python path
sys.path.insert(0, str(src_dir))

# Import Flask components
from app import create_app
from models import ModelCapability, GeneratedApplication, PortConfiguration, AnalysisStatus
from extensions import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def main():
    """Main initialization function."""
    logger.info("=== Thesis Research App Database Initialization ===")
    
    try:
        logger.info("Creating Flask application...")
        app = create_app()
        
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()
            
            # Load model capabilities from JSON
            misc_dir = project_root / "misc"
            capabilities_file = misc_dir / "model_capabilities.json"
            models_summary_file = misc_dir / "models_summary.json"
            port_config_file = misc_dir / "port_config.json"
            
            logger.info(f"Loading model capabilities from {capabilities_file}")
            with open(capabilities_file) as f:
                capabilities_data = json.load(f)
            
            logger.info(f"Loading models summary from {models_summary_file}")
            with open(models_summary_file) as f:
                models_summary_data = json.load(f)
            
            logger.info(f"Loading port configurations from {port_config_file}")
            with open(port_config_file) as f:
                port_config_data = json.load(f)
            
            # Get the models section
            models_data = capabilities_data['models']
            
            # Filter out metadata keys to get actual model entries
            model_ids = [key for key in models_data.keys() 
                        if key not in ['metadata', 'capabilities_summary', 'models'] 
                        and isinstance(models_data[key], dict) 
                        and models_data[key].get('model_id')]
            
            logger.info(f"Found {len(model_ids)} models to process")
            
            # Clear existing data
            logger.info("Clearing existing data...")
            ModelCapability.query.delete()
            GeneratedApplication.query.delete()
            PortConfiguration.query.delete()
            
            models_created = 0
            apps_created = 0
            ports_created = 0
            
            # Process each model
            for model_id in model_ids:
                model_data = models_data[model_id]
                
                try:
                    logger.info(f"Processing model: {model_id}")
                    
                    # Create ModelCapability entry
                    model_capability = ModelCapability()
                    model_capability.model_id = model_data.get('model_id')
                    model_capability.canonical_slug = model_data.get('canonical_slug', model_id.replace('/', '_'))
                    model_capability.provider = model_data.get('provider', 'unknown')
                    model_capability.model_name = model_data.get('model_name', model_id)
                    model_capability.is_free = model_data.get('is_free', False)
                    model_capability.context_window = model_data.get('context_window', 0)
                    model_capability.max_output_tokens = model_data.get('max_output_tokens', 0)
                    model_capability.supports_function_calling = model_data.get('supports_function_calling', False)
                    model_capability.supports_vision = model_data.get('supports_vision', False)
                    model_capability.supports_streaming = model_data.get('supports_streaming', True)
                    model_capability.supports_json_mode = model_data.get('supports_json_mode', False)
                    model_capability.input_price_per_token = float(model_data.get('pricing', {}).get('prompt_tokens', 0) or 0)
                    model_capability.output_price_per_token = float(model_data.get('pricing', {}).get('completion_tokens', 0) or 0)
                    model_capability.cost_efficiency = model_data.get('performance_metrics', {}).get('cost_efficiency', 0.0)
                    model_capability.safety_score = model_data.get('quality_metrics', {}).get('safety', 0.0)
                    model_capability.capabilities_json = json.dumps(model_data.get('capabilities', {}))
                    model_capability.metadata_json = json.dumps({
                        'description': model_data.get('description', ''),
                        'architecture': model_data.get('architecture', {}),
                        'quality_metrics': model_data.get('quality_metrics', {}),
                        'performance_metrics': model_data.get('performance_metrics', {}),
                        'last_updated': model_data.get('last_updated', '')
                    })
                    
                    db.session.add(model_capability)
                    models_created += 1
                    
                    # Create a sample GeneratedApplication for the first app
                    canonical_slug = model_data.get('canonical_slug', model_id.replace('/', '_'))
                    app_entry = GeneratedApplication()
                    app_entry.model_slug = canonical_slug
                    app_entry.app_number = 1
                    app_entry.app_type = "login_system"
                    app_entry.provider = model_data.get('provider', 'unknown')
                    app_entry.generation_status = "completed"
                    app_entry.has_backend = True
                    app_entry.has_frontend = True
                    app_entry.has_docker_compose = True
                    app_entry.backend_framework = "Flask"
                    app_entry.frontend_framework = "React"
                    app_entry.container_status = "stopped"
                    app_entry.metadata_json = json.dumps({
                        "description": f"Login system application generated by {model_id}",
                        "features": ["authentication", "user management"],
                        "model_used": model_id
                    })
                    
                    db.session.add(app_entry)
                    apps_created += 1
                    
                except Exception as e:
                    logger.error(f"Error processing model {model_id}: {e}")
                    continue
            
            # Load port configurations from port_config.json
            logger.info("Loading port configurations from JSON file...")
            for port_entry in port_config_data:
                if 'model_name' in port_entry and 'app_number' in port_entry:
                    port_config = PortConfiguration()
                    port_config.model = port_entry['model_name']
                    port_config.app_num = port_entry['app_number']
                    port_config.frontend_port = port_entry['frontend_port']
                    port_config.backend_port = port_entry['backend_port']
                    port_config.is_available = True
                    port_config.metadata_json = json.dumps({
                        'model_name': port_entry['model_name'],
                        'app_type': f'app_{port_entry["app_number"]}',
                        'source': 'port_config_json'
                    })
                    
                    db.session.add(port_config)
                    ports_created += 1
            
            # Commit all changes
            logger.info("Committing database changes...")
            db.session.commit()
            
            logger.info("=== Database initialization completed successfully! ===")
            logger.info(f"Models created: {models_created}")
            logger.info(f"Applications created: {apps_created}")
            logger.info(f"Port configurations created: {ports_created}")
            
            # Show sample data
            logger.info("\nSample models:")
            for model in ModelCapability.query.limit(5).all():
                logger.info(f"  {model.model_id} ({model.provider})")
            
            return True
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
