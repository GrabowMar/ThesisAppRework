#!/usr/bin/env python3
"""
Quick script to check and populate models in the database
"""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Use the existing app factory
from app import create_app

def check_and_populate_models():
    """Check if models exist in database and populate from JSON if needed."""
    app = create_app()
    
    with app.app_context():
        from models import ModelCapability
        from extensions import db
        
        # Check existing models
        try:
            existing_count = ModelCapability.query.count()
            print(f"Existing models in database: {existing_count}")
        except Exception as e:
            print(f"Database error: {e}")
            print("Creating tables...")
            db.create_all()
            existing_count = 0
        
        if existing_count == 0:
            print("Database is empty, populating from JSON files...")
            
            # Load model capabilities from JSON
            capabilities_file = 'misc/model_capabilities.json'
            if os.path.exists(capabilities_file):
                with open(capabilities_file, 'r') as f:
                    capabilities_data = json.load(f)
                
                # Load models summary for display names
                summary_file = 'misc/models_summary.json'
                summary_data = {}
                if os.path.exists(summary_file):
                    with open(summary_file, 'r') as f:
                        summary_data = json.load(f)
                
                models_added = 0
                for model_id, capabilities in capabilities_data.items():
                    try:
                        # Get display info from summary
                        display_info = summary_data.get(model_id, {})
                        
                        model = ModelCapability(
                            model_id=model_id,
                            canonical_slug=model_id,
                            provider=capabilities.get('provider', 'Unknown'),
                            model_name=display_info.get('name', model_id),
                            is_free=capabilities.get('is_free', False),
                            context_window=capabilities.get('context_window', 0),
                            max_output_tokens=capabilities.get('max_output_tokens', 0),
                            supports_function_calling=capabilities.get('supports_function_calling', False),
                            supports_vision=capabilities.get('supports_vision', False),
                            supports_streaming=capabilities.get('supports_streaming', False),
                            supports_json_mode=capabilities.get('supports_json_mode', False),
                            input_price_per_token=capabilities.get('input_price_per_token', 0.0),
                            output_price_per_token=capabilities.get('output_price_per_token', 0.0),
                            cost_efficiency=capabilities.get('cost_efficiency', 0.0),
                            safety_score=capabilities.get('safety_score', 0.0),
                            capabilities_json=json.dumps(capabilities),
                            metadata_json=json.dumps(display_info)
                        )
                        
                        db.session.add(model)
                        models_added += 1
                        
                    except Exception as e:
                        print(f"Error adding model {model_id}: {e}")
                
                try:
                    db.session.commit()
                    print(f"Successfully added {models_added} models to database")
                except Exception as e:
                    print(f"Error committing to database: {e}")
                    db.session.rollback()
            else:
                print(f"Capabilities file not found: {capabilities_file}")
        
        # Show current models
        models = ModelCapability.query.all()
        print(f"\nModels in database ({len(models)}):")
        for model in models[:5]:  # Show first 5
            print(f"  - {model.provider} - {model.model_name} ({model.canonical_slug})")
        
        if len(models) > 5:
            print(f"  ... and {len(models) - 5} more")

if __name__ == '__main__':
    check_and_populate_models()
