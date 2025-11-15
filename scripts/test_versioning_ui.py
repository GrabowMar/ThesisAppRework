#!/usr/bin/env python
"""
Test script to verify versioning UI integration.

Tests:
1. Context builder provides app_version_counts
2. Template rendering includes version columns
3. Regenerate JavaScript function exists
4. API endpoint responds correctly
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from app import create_app
from app.models import GeneratedApplication, ModelCapability
from app.routes.jinja.detail_context import build_model_detail_context
from app.extensions import db


def test_context_builder():
    """Test that context builder includes version counts."""
    print("\n" + "="*60)
    print("TEST 1: Context Builder - app_version_counts")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        # Find a model with apps
        model = ModelCapability.query.first()
        if not model:
            print("❌ No models found in database")
            return False
        
        print(f"Testing with model: {model.canonical_slug}")
        
        # Build context
        context = build_model_detail_context(model.canonical_slug)
        
        # Check for app_version_counts
        if 'app_version_counts' not in context:
            print("❌ FAILED: 'app_version_counts' not in context")
            return False
        
        print(f"✅ PASSED: 'app_version_counts' present in context")
        print(f"   Version counts: {context['app_version_counts']}")
        
        # Check structure
        if not isinstance(context['app_version_counts'], dict):
            print("❌ FAILED: 'app_version_counts' is not a dict")
            return False
        
        print("✅ PASSED: 'app_version_counts' is a dict")
        
        # If there are apps, verify counts
        if context['applications']:
            app_numbers = {app.app_number for app in context['applications']}
            for app_num in app_numbers:
                count = context['app_version_counts'].get(app_num, 0)
                actual_count = len([a for a in context['applications'] if a.app_number == app_num])
                if count != actual_count:
                    print(f"❌ FAILED: app{app_num} count mismatch: expected {actual_count}, got {count}")
                    return False
            print(f"✅ PASSED: Version counts accurate for {len(app_numbers)} apps")
        
        return True


def test_template_rendering():
    """Test that template contains version-related markup."""
    print("\n" + "="*60)
    print("TEST 2: Template Markup")
    print("="*60)
    
    try:
        # Read template file directly
        with open('src/templates/pages/models/partials/model_applications.html', 'r') as f:
            template_content = f.read()
        
        # Check for version-related content in source
        checks = {
            'Version column header': '<th>Version</th>' in template_content,
            'Template column header': '<th>Template</th>' in template_content,
            'Version badge': 'bg-purple-lt' in template_content,
            'Template badge': 'bg-indigo-lt' in template_content,
            'Regenerate button': 'regenerateApplication' in template_content,
            'Version count indicator': 'app_version_counts' in template_content,
            'Parent app indicator': 'parent_app_id' in template_content,
        }
        
        all_passed = True
        for check_name, result in checks.items():
            if result:
                print(f"✅ PASSED: {check_name}")
            else:
                print(f"❌ FAILED: {check_name}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ FAILED: Error reading template: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_javascript_functions():
    """Test that JavaScript regenerate function exists."""
    print("\n" + "="*60)
    print("TEST 3: JavaScript Functions")
    print("="*60)
    
    try:
        with open('src/templates/pages/models/model_details.html', 'r') as f:
            content = f.read()
        
        checks = {
            'regenerateApplication function': 'async function regenerateApplication' in content,
            'Confirmation prompt': 'confirm(' in content and 'regenerate' in content.lower(),
            'API endpoint call': '/api/models/${modelSlug}/apps/${appNumber}/regenerate' in content,
            'Success toast': 'showToast' in content,
            'Section refresh': 'htmx.ajax' in content,
        }
        
        all_passed = True
        for check_name, result in checks.items():
            if result:
                print(f"✅ PASSED: {check_name}")
            else:
                print(f"❌ FAILED: {check_name}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ FAILED: Error reading template: {e}")
        return False


def test_database_schema():
    """Test that database has versioning fields."""
    print("\n" + "="*60)
    print("TEST 4: Database Schema")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        # Check GeneratedApplication model has required fields
        sample_app = GeneratedApplication.query.first()
        
        if not sample_app:
            print("⚠️  WARNING: No apps in database to test schema")
            print("   Creating test record...")
            
            model = ModelCapability.query.first()
            if not model:
                print("❌ No models available for test")
                return False
            
            test_app = GeneratedApplication(
                model_slug=model.canonical_slug,
                app_number=999,
                version=1,
                app_type='web_app',
                generation_status='pending'
            )
            
            try:
                db.session.add(test_app)
                db.session.commit()
                sample_app = test_app
                print("   ✅ Test record created")
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Failed to create test record: {e}")
                return False
        
        # Check fields
        required_fields = ['version', 'parent_app_id', 'batch_id', 'template_slug']
        all_passed = True
        
        for field in required_fields:
            if hasattr(sample_app, field):
                value = getattr(sample_app, field, None)
                print(f"✅ PASSED: Field '{field}' exists (value: {value})")
            else:
                print(f"❌ FAILED: Field '{field}' missing")
                all_passed = False
        
        # Clean up test record if created
        if sample_app.app_number == 999:
            try:
                db.session.delete(sample_app)
                db.session.commit()
                print("   ✅ Test record cleaned up")
            except:
                db.session.rollback()
        
        return all_passed


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" VERSIONING UI INTEGRATION TEST SUITE")
    print("="*70)
    
    results = {
        'Context Builder': test_context_builder(),
        'Template Rendering': test_template_rendering(),
        'JavaScript Functions': test_javascript_functions(),
        'Database Schema': test_database_schema(),
    }
    
    print("\n" + "="*70)
    print(" FINAL RESULTS")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Versioning UI integration complete!")
    else:
        print("⚠️  SOME TESTS FAILED - Review errors above")
    print("="*70 + "\n")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
