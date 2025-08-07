#!/usr/bin/env python3
"""
Migration Script: JSON to Database
==================================

This script migrates data from JSON files to database models.
Run this script to replace JSON file dependencies with database storage.

Usage:
    python migrate_to_database.py [--force]

Options:
    --force     Force migration even if database already has data
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from models import ModelCapability, PortConfiguration, db


def load_json_file(file_path: Path) -> dict:
    """Load JSON file safely."""
    try:
        with open(file_path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {file_path}: {e}")
        return {}


def migrate_model_capabilities(app, force=False):
    """Migrate model capabilities from JSON to database."""
    print("\n📊 Migrating Model Capabilities...")

    with app.app_context():
        # Check if data already exists
        existing_count = ModelCapability.query.count()
        if existing_count > 0 and not force:
            print(f"⚠️  Database already contains {existing_count} model capabilities")
            print("   Use --force to overwrite existing data")
            return False

        # Clear existing data if force mode
        if force and existing_count > 0:
            print(f"🗑️  Clearing {existing_count} existing model capabilities...")
            ModelCapability.query.delete()
            db.session.commit()

        # Load JSON data
        json_path = Path(__file__).parent.parent / "misc" / "model_capabilities.json"
        data = load_json_file(json_path)

        if not data or 'models' not in data:
            print("❌ No model capabilities data found in JSON")
            return False

        models_data = data['models']
        success_count = 0
        error_count = 0

        for model_id, capabilities in models_data.items():
            try:
                # Create ModelCapability instance
                model = ModelCapability(
                    model_id=model_id,
                    canonical_slug=model_id.replace('/', '_').replace('-', '_'),
                    provider=capabilities.get('provider', 'unknown'),
                    model_name=capabilities.get('name', model_id),
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
                    safety_score=capabilities.get('safety_score', 0.0)
                )

                # Store additional capabilities as JSON
                additional_capabilities = {
                    k: v for k, v in capabilities.items()
                    if k not in {
                        'provider', 'name', 'is_free', 'context_window', 'max_output_tokens',
                        'supports_function_calling', 'supports_vision', 'supports_streaming',
                        'supports_json_mode', 'input_price_per_token', 'output_price_per_token',
                        'cost_efficiency', 'safety_score'
                    }
                }

                if additional_capabilities:
                    model.set_capabilities(additional_capabilities)

                db.session.add(model)
                success_count += 1

            except Exception as e:
                print(f"❌ Error migrating model {model_id}: {e}")
                error_count += 1

        # Commit changes
        try:
            db.session.commit()
            print(f"✅ Migrated {success_count} model capabilities to database")
            if error_count > 0:
                print(f"⚠️  {error_count} models failed to migrate")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ Failed to commit model capabilities: {e}")
            return False


def migrate_port_configurations(app, force=False):
    """Migrate port configurations from JSON to database."""
    print("\n🔌 Migrating Port Configurations...")

    with app.app_context():
        # Check if data already exists
        existing_count = PortConfiguration.query.count()
        if existing_count > 0 and not force:
            print(f"⚠️  Database already contains {existing_count} port configurations")
            print("   Use --force to overwrite existing data")
            return False

        # Clear existing data if force mode
        if force and existing_count > 0:
            print(f"🗑️  Clearing {existing_count} existing port configurations...")
            PortConfiguration.query.delete()
            db.session.commit()

        # Load JSON data
        json_path = Path(__file__).parent.parent / "misc" / "port_config.json"
        port_data = load_json_file(json_path)

        if not port_data:
            print("❌ No port configuration data found in JSON")
            return False

        success_count = 0
        error_count = 0

        for config in port_data:
            try:
                port_config = PortConfiguration(
                    model=config['model_name'],
                    app_num=config['app_number'],
                    frontend_port=config['frontend_port'],
                    backend_port=config['backend_port'],
                    is_available=True
                )

                # Add metadata if available
                metadata = {
                    'source': 'json_migration',
                    'migrated_at': datetime.now().isoformat()
                }
                port_config.set_metadata(metadata)

                db.session.add(port_config)
                success_count += 1

            except Exception as e:
                print(f"❌ Error migrating port config {config}: {e}")
                error_count += 1

        # Commit changes
        try:
            db.session.commit()
            print(f"✅ Migrated {success_count} port configurations to database")
            if error_count > 0:
                print(f"⚠️  {error_count} port configs failed to migrate")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ Failed to commit port configurations: {e}")
            return False


def verify_migration(app):
    """Verify the migration was successful."""
    print("\n🔍 Verifying Migration...")

    with app.app_context():
        model_count = ModelCapability.query.count()
        port_count = PortConfiguration.query.count()

        print(f"📊 Database contains:")
        print(f"   • {model_count} model capabilities")
        print(f"   • {port_count} port configurations")

        # Sample verification
        if model_count > 0:
            sample_model = ModelCapability.query.first()
            print(f"   • Sample model: {sample_model.model_id} ({sample_model.provider})")

        if port_count > 0:
            sample_port = PortConfiguration.query.first()
            print(f"   • Sample port: {sample_port.model} app {sample_port.app_num} -> {sample_port.frontend_port}/{sample_port.backend_port}")

        return model_count > 0 and port_count > 0


def main():
    """Main migration script."""
    parser = argparse.ArgumentParser(description="Migrate data from JSON files to database")
    parser.add_argument('--force', action='store_true',
                       help='Force migration even if database already has data')
    args = parser.parse_args()

    print("🚀 Starting JSON to Database Migration")
    print("=" * 50)

    # Create Flask app
    app = create_app()

    # Perform migrations
    success = True

    success &= migrate_model_capabilities(app, force=args.force)
    success &= migrate_port_configurations(app, force=args.force)

    if success:
        success &= verify_migration(app)

    if success:
        print("\n🎉 Migration completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Test the application to ensure database integration works")
        print("   2. Consider backing up the JSON files before removing them")
        print("   3. Update any scripts that directly read JSON files")
    else:
        print("\n❌ Migration completed with errors")
        print("   Please check the error messages above and try again")
        sys.exit(1)


if __name__ == "__main__":
    main()
