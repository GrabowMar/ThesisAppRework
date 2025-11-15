#!/usr/bin/env python
"""
Demo script to showcase the versioning UI integration.

This script demonstrates:
1. Creating an initial app (v1)
2. Regenerating to create v2
3. Viewing the version information
4. Showing how the UI displays multiple versions
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from app import create_app
from app.models import GeneratedApplication, ModelCapability
from app.routes.jinja.detail_context import build_model_detail_context
from app.extensions import db


def print_header(text):
    """Print a formatted header."""
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70)


def print_app_info(app):
    """Print formatted application information."""
    parent_info = f" (parent: {app.parent_app_id})" if app.parent_app_id else ""
    template_info = app.template_slug or "default"
    batch_info = app.batch_id[:20] + "..." if app.batch_id and len(app.batch_id) > 20 else app.batch_id or "N/A"
    
    print(f"  App #{app.app_number} v{app.version}{parent_info}")
    print(f"    Template: {template_info}")
    print(f"    Batch: {batch_info}")
    print(f"    Status: {app.generation_status}")
    print(f"    Created: {app.created_at}")


def demo_versioning_ui():
    """Demonstrate the versioning UI integration."""
    
    print_header("VERSIONING UI INTEGRATION DEMO")
    print("\nThis demo shows how the versioning system works in the UI.\n")
    
    app = create_app()
    with app.app_context():
        # Find a model with apps
        model = ModelCapability.query.first()
        if not model:
            print("❌ No models found in database. Please add models first.")
            return 1
        
        print(f"📊 Using model: {model.canonical_slug}")
        
        # Get context (this is what the UI receives)
        print("\n🔍 Building UI context...")
        context = build_model_detail_context(model.canonical_slug)
        
        # Show what the UI sees
        print_header("UI CONTEXT DATA")
        
        print(f"\n✅ Applications found: {len(context.get('applications', []))}")
        print(f"✅ Version counts provided: {context.get('app_version_counts', {})}")
        
        if not context.get('applications'):
            print("\n⚠️  No applications exist for this model yet.")
            print("   Create some apps to see the versioning UI in action!")
            print("\n   Example:")
            print(f"   python scripts/test_direct_reservation.py")
            return 0
        
        # Group apps by app_number
        apps_by_number = {}
        for app in context['applications']:
            if app.app_number not in apps_by_number:
                apps_by_number[app.app_number] = []
            apps_by_number[app.app_number].append(app)
        
        # Show version information for each app number
        print_header("APPLICATION VERSIONS")
        
        for app_num in sorted(apps_by_number.keys()):
            versions = sorted(apps_by_number[app_num], key=lambda a: a.version)
            version_count = len(versions)
            
            print(f"\n📦 App #{app_num} - {version_count} version(s)")
            print("-" * 70)
            
            for app in versions:
                print_app_info(app)
            
            # Show what the UI would display
            latest = versions[-1]
            print(f"\n  🎨 UI Display:")
            print(f"     App #: [{app_num}]", end="")
            if version_count > 1:
                print(f" [🔢 {version_count}]", end="")
            print()
            print(f"     Version: [v{latest.version}]", end="")
            if latest.parent_app_id:
                print(f" [🔙]", end="")
            print()
            print(f"     Template: [{latest.template_slug or 'Default'}]")
            print(f"     Actions: [👁️ View] [🔄 Regenerate]", end="")
            if latest.container_status == 'running':
                print(f" [🔗 Open]", end="")
            print()
        
        # Show version count summary
        print_header("VERSION COUNT SUMMARY")
        
        for app_num, count in sorted(context['app_version_counts'].items()):
            status_emoji = "🔢" if count > 1 else "⚪"
            print(f"  {status_emoji} App #{app_num}: {count} version(s)")
        
        # Show UI workflow
        print_header("UI WORKFLOW EXAMPLE")
        
        print("\n1️⃣  User navigates to model detail page:")
        print(f"   URL: /models/{model.canonical_slug}")
        
        print("\n2️⃣  User sees Applications section with table:")
        print("   Columns: App # | Version | Template | Type | Status | Created | Actions")
        
        print("\n3️⃣  User clicks Regenerate (🔄) on an app:")
        print("   → Confirmation dialog appears")
        print("   → User confirms")
        print("   → API call: POST /api/models/{slug}/apps/{num}/regenerate")
        print("   → New version created with incremented number")
        print("   → Table auto-refreshes to show new version")
        
        print("\n4️⃣  Updated table shows:")
        print("   → Original version (v1)")
        print("   → New version (v2) with regeneration indicator (🔙)")
        print("   → Version count badge (🔢 2) on app number")
        
        # Show template features
        print_header("TEMPLATE FEATURES")
        
        features = [
            ("Version Column", "Purple badge (v1, v2, v3...)"),
            ("Template Column", "Indigo badge showing template name"),
            ("Version Count", "Cyan badge (🔢 X) when multiple versions exist"),
            ("Regeneration Indicator", "Arrow (🔙) for versions created from previous"),
            ("Regenerate Button", "Refresh icon (🔄) to create new version"),
            ("Auto-refresh", "Table reloads after regeneration completes"),
        ]
        
        for feature, description in features:
            print(f"  ✅ {feature}")
            print(f"     {description}")
        
        # Show next steps
        print_header("NEXT STEPS")
        
        print("\n1. Start the Flask development server:")
        print("   ./start.ps1 -Mode Dev")
        
        print("\n2. Navigate to a model detail page:")
        print(f"   http://localhost:5000/models/{model.canonical_slug}")
        
        print("\n3. Try the versioning features:")
        print("   - View the Version and Template columns")
        print("   - Click Regenerate on an existing app")
        print("   - Watch the new version appear automatically")
        
        print("\n4. Check the documentation:")
        print("   - docs/VERSIONING.md (comprehensive guide)")
        print("   - docs/VERSIONING_UI_QUICKREF.md (quick reference)")
        
        print("\n" + "="*70)
        print(" 🎉 VERSIONING UI INTEGRATION IS READY!")
        print("="*70 + "\n")
        
        return 0


if __name__ == '__main__':
    sys.exit(demo_versioning_ui())
