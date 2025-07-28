#!/usr/bin/env python3
"""
Test port configuration loading with fixed field mapping
"""

import os
import sys
import json
import logging
from pathlib import Path

# Ensure we're in the right directory and set up paths
script_dir = Path(__file__).parent
project_root = script_dir
src_dir = project_root / "src"

# Add source directory to Python path
sys.path.insert(0, str(src_dir))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_port_configurations():
    """Load port configurations from JSON file."""
    from extensions import db
    from models import PortConfiguration
    from app import create_app
    
    logger.info("Loading port configurations...")
    
    misc_dir = project_root / "misc"
    port_file = misc_dir / "port_config.json"
    
    with open(port_file, 'r', encoding='utf-8') as f:
        port_data = json.load(f)
    
    logger.info(f"Successfully loaded port_config.json with {len(port_data)} items")
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        ports_loaded = 0
        for i, port_entry in enumerate(port_data):
            try:
                frontend_port = port_entry.get('frontend_port')
                backend_port = port_entry.get('backend_port')
                
                if not frontend_port or not backend_port:
                    logger.warning(f"Invalid port entry at index {i}: {port_entry}")
                    continue
                
                # Check if port configuration already exists
                existing = PortConfiguration.query.filter_by(
                    frontend_port=frontend_port
                ).first()
                
                if existing:
                    continue
                
                # Check what's in the entry
                model_name = port_entry.get('model_name', '')
                if not model_name and i < 5:  # Debug first few entries
                    logger.info(f"Port entry {i}: {port_entry}")
                
                # Create new port configuration - FIXED: use 'model_name' instead of 'model'
                port_config = PortConfiguration(
                    frontend_port=frontend_port,
                    backend_port=backend_port,
                    is_available=True,
                    metadata_json=json.dumps({
                        'model': port_entry.get('model_name', ''),  # FIXED: changed from 'model' to 'model_name'
                        'app_number': port_entry.get('app_number', 0),
                        'app_type': port_entry.get('app_type', ''),
                        'source': 'initial_load'
                    })
                )
                
                db.session.add(port_config)
                ports_loaded += 1
                
                if ports_loaded <= 5:  # Debug first few
                    metadata = json.loads(port_config.metadata_json)
                    logger.info(f"Created port config {ports_loaded}: frontend={frontend_port}, model={metadata['model']}")
                
            except Exception as e:
                logger.error(f"Error processing port entry {i}: {e}")
                continue
        
        db.session.commit()
        logger.info(f"Successfully loaded {ports_loaded} port configurations")

if __name__ == "__main__":
    load_port_configurations()
