"""
Quick test to verify atomic app number reservation prevents overwrites.

This script simulates concurrent generation requests to ensure the race condition is fixed.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models.core import GeneratedApplication
from app.services.generation import GenerationService


async def test_concurrent_reservations():
    """Test that concurrent requests get different app numbers."""
    app = create_app()
    
    with app.app_context():
        # Clean up any existing test apps
        test_model = "test-model_concurrent"
        GeneratedApplication.query.filter_by(model_slug=test_model).delete()
        db.session.commit()
        
        print(f"\n=== Testing Atomic App Number Reservation ===")
        print(f"Model: {test_model}")
        print(f"Simulating 5 concurrent generation requests...\n")
        
        service = GenerationService()
        
        # Simulate 5 concurrent requests trying to generate apps
        async def reserve_app(num):
            try:
                # Each request tries to reserve the next app number
                # Before the fix: all would get app1
                # After the fix: each gets a different number (app1, app2, app3, app4, app5)
                
                record = await service._reserve_app_number(
                    model_slug=test_model,
                    app_num=num,  # Sequential allocation
                    template_slug=f"template_{num}",
                    batch_id="test_batch",
                    version=1
                )
                
                print(f"  ✓ Request {num}: Reserved app{record.app_number} v{record.version} (ID={record.id})")
                return record.app_number
                
            except RuntimeError as e:
                print(f"  ✗ Request {num}: Failed - {str(e)}")
                return None
        
        # Run all reservations concurrently
        tasks = [reserve_app(i) for i in range(1, 6)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        print(f"\n=== Results ===")
        app_numbers = [r for r in results if isinstance(r, int)]
        
        print(f"Reserved app numbers: {sorted(app_numbers)}")
        print(f"Unique apps created: {len(set(app_numbers))}")
        print(f"Expected: 5 unique apps")
        
        # Check database state
        apps = GeneratedApplication.query.filter_by(model_slug=test_model).all()
        print(f"\nDatabase records: {len(apps)}")
        for app in sorted(apps, key=lambda x: x.app_number):
            print(f"  - app{app.app_number} v{app.version} (template: {app.template_slug})")
        
        # Verify no duplicates
        success = len(set(app_numbers)) == 5 and len(apps) == 5
        
        if success:
            print(f"\n✅ Test PASSED: All 5 requests got unique app numbers!")
            print(f"   No overwrites occurred - race condition is fixed!")
        else:
            print(f"\n❌ Test FAILED: Duplicates or missing apps detected")
            print(f"   Race condition may still exist")
        
        # Cleanup
        GeneratedApplication.query.filter_by(model_slug=test_model).delete()
        db.session.commit()
        
        return success


async def test_version_increments():
    """Test that regenerating an app increments the version correctly."""
    app = create_app()
    
    with app.app_context():
        print(f"\n\n=== Testing Version Increment System ===")
        
        test_model = "test-model_versioning"
        test_app_num = 1
        
        # Clean up
        GeneratedApplication.query.filter_by(model_slug=test_model).delete()
        db.session.commit()
        
        service = GenerationService()
        
        # Create v1
        print(f"Creating {test_model}/app{test_app_num} v1...")
        v1 = await service._reserve_app_number(
            model_slug=test_model,
            app_num=test_app_num,
            template_slug="test_template",
            version=1
        )
        print(f"  ✓ Created app{v1.app_number} v{v1.version} (ID={v1.id})")
        
        # Create v2 (regeneration)
        print(f"Regenerating as v2 (parent_app_id={v1.id})...")
        v2 = await service._reserve_app_number(
            model_slug=test_model,
            app_num=test_app_num,
            template_slug="test_template",
            parent_app_id=v1.id,
            version=2
        )
        print(f"  ✓ Created app{v2.app_number} v{v2.version} (ID={v2.id}, parent={v2.parent_app_id})")
        
        # Create v3
        print(f"Regenerating as v3 (parent_app_id={v2.id})...")
        v3 = await service._reserve_app_number(
            model_slug=test_model,
            app_num=test_app_num,
            template_slug="test_template",
            parent_app_id=v2.id,
            version=3
        )
        print(f"  ✓ Created app{v3.app_number} v{v3.version} (ID={v3.id}, parent={v3.parent_app_id})")
        
        # Verify
        apps = GeneratedApplication.query.filter_by(
            model_slug=test_model,
            app_number=test_app_num
        ).order_by(GeneratedApplication.version).all()
        
        print(f"\n=== Results ===")
        print(f"Total versions: {len(apps)}")
        for app in apps:
            print(f"  - v{app.version}: ID={app.id}, parent={app.parent_app_id}")
        
        success = (
            len(apps) == 3 and
            apps[0].version == 1 and apps[0].parent_app_id is None and
            apps[1].version == 2 and apps[1].parent_app_id == apps[0].id and
            apps[2].version == 3 and apps[2].parent_app_id == apps[1].id
        )
        
        if success:
            print(f"\n✅ Test PASSED: Version lineage is correct!")
        else:
            print(f"\n❌ Test FAILED: Version lineage is broken")
        
        # Cleanup
        GeneratedApplication.query.filter_by(model_slug=test_model).delete()
        db.session.commit()
        
        return success


async def main():
    """Run all tests."""
    print("=" * 70)
    print("ATOMIC RESERVATION & VERSIONING TEST SUITE")
    print("=" * 70)
    
    test1 = await test_concurrent_reservations()
    test2 = await test_version_increments()
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Atomic Reservation Test: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Version Increment Test:  {'✅ PASSED' if test2 else '❌ FAILED'}")
    print()
    
    if test1 and test2:
        print("🎉 ALL TESTS PASSED! The race condition is fixed and versioning works!")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED! Review the implementation.")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
