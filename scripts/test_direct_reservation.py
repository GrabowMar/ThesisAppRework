"""
Direct test of atomic reservation by calling GenerationService.
This bypasses authentication and tests the core functionality.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.services.service_locator import ServiceLocator
from app.models.core import GeneratedApplication
from app.extensions import db
import asyncio
from datetime import datetime
import uuid

def generate_batch_id():
    """Generate a batch ID like the wizard does."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = str(uuid.uuid4())[:8]
    return f"batch_{timestamp}_{random_suffix}"

async def test_direct_reservation():
    """Test direct reservation through GenerationService."""
    
    print("\n" + "="*80)
    print("DIRECT ATOMIC RESERVATION TEST")
    print("="*80)
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        service = ServiceLocator.get_generation_service()
        
        batch_id = generate_batch_id()
        print(f"\nBatch ID: {batch_id}")
        
        # Test 1: Reserve multiple app numbers sequentially
        print("\nTest 1: Sequential reservations")
        print("-" * 40)
        
        model_slug = "test-direct-model"
        reservations = []
        
        for i in range(3):
            template = f"template_{chr(97+i)}"  # template_a, template_b, template_c
            print(f"  Reserving app for {template}...")
            
            try:
                app_record = await service._reserve_app_number(
                    model_slug=model_slug,
                    app_num=None,  # Auto-allocate
                    template_slug=template,
                    batch_id=batch_id,
                    parent_app_id=None,
                    version=1
                )
                reservations.append(app_record)
                print(f"    ✓ Reserved app{app_record.app_number} (ID={app_record.id})")
            except Exception as e:
                print(f"    ✗ Failed: {e}")
        
        # Test 2: Verify all got unique app numbers
        print("\nTest 2: Uniqueness check")
        print("-" * 40)
        
        app_numbers = [r.app_number for r in reservations]
        print(f"  App numbers: {app_numbers}")
        print(f"  Unique count: {len(set(app_numbers))}")
        print(f"  Total count: {len(app_numbers)}")
        
        if len(set(app_numbers)) == len(app_numbers):
            print("  ✅ All app numbers are unique!")
        else:
            print("  ❌ Duplicate app numbers found!")
            return False
        
        # Test 3: Verify batch tracking
        print("\nTest 3: Batch tracking")
        print("-" * 40)
        
        batch_apps = GeneratedApplication.query.filter_by(batch_id=batch_id).all()
        print(f"  Apps in batch {batch_id}: {len(batch_apps)}")
        
        for app in batch_apps:
            print(f"    - app{app.app_number} ({app.template_slug})")
        
        if len(batch_apps) == 3:
            print("  ✅ Batch tracking works!")
        else:
            print(f"  ❌ Expected 3 apps, found {len(batch_apps)}")
            return False
        
        # Test 4: Test versioning
        print("\nTest 4: Versioning")
        print("-" * 40)
        
        # Get first app and create a new version
        original_app = reservations[0]
        print(f"  Original: app{original_app.app_number} v{original_app.version} (ID={original_app.id})")
        
        v2 = await service._reserve_app_number(
            model_slug=model_slug,
            app_num=original_app.app_number,  # Same app number
            template_slug=original_app.template_slug,
            batch_id=f"regen_{generate_batch_id()}",
            parent_app_id=original_app.id,  # Link to parent
            version=2  # v2
        )
        
        print(f"  Version 2: app{v2.app_number} v{v2.version} (ID={v2.id}, parent={v2.parent_app_id})")
        
        if v2.app_number == original_app.app_number and v2.version == 2 and v2.parent_app_id == original_app.id:
            print("  ✅ Versioning works correctly!")
        else:
            print("  ❌ Versioning failed!")
            return False
        
        print("\n" + "="*80)
        print("FINAL RESULT")
        print("="*80)
        print("✅ ALL TESTS PASSED!")
        print(f"\nCreated {len(reservations)} apps in batch {batch_id}")
        print(f"Plus 1 version increment (v2)")
        print("\nAtomic reservation and versioning are working correctly!")
        
        return True

if __name__ == "__main__":
    result = asyncio.run(test_direct_reservation())
    sys.exit(0 if result else 1)
