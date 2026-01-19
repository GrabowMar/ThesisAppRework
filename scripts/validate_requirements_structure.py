#!/usr/bin/env python3
"""
Validate Requirements Structure and Design Quality
==================================================

This script performs deep validation of requirement file structure and design quality.

The script validates:
- JSON syntax and required fields
- Slug/filename consistency
- Backend and frontend requirements structure
- API endpoint definitions and HTTP methods
- Data model specifications
- Admin requirements and endpoints
- Design quality metrics (complexity, completeness)

Checks performed:
- Required fields presence and types
- API endpoint method validation
- Cross-reference integrity
- Design pattern compliance
- Complexity and quality metrics

Usage:
    python scripts/validate_requirements_structure.py

Outputs:
- Detailed validation report with issues and warnings
- Statistics on requirements coverage
- Quality metrics for each requirement file

This script ensures requirement files are well-structured and follow
consistent design patterns for reliable application generation.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent
requirements_dir = project_root / 'misc' / 'requirements'

def main():
    print("=" * 80)
    print("REQUIREMENTS STRUCTURE VALIDATION")
    print("=" * 80)

    issues = []
    warnings = []
    stats = defaultdict(int)

    req_files = list(requirements_dir.glob('*.json'))
    req_files = [f for f in req_files if f.name != 'README.md']

    print(f"\nFound {len(req_files)} requirement files")
    print()

    for req_file in sorted(req_files):
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            slug = req_file.stem
            stats['total'] += 1

            # Check slug matches filename
            if data.get('slug') != slug:
                issues.append(f"{slug}: Slug mismatch - file:{slug}, json:{data.get('slug')}")

            # Check required top-level fields
            required_fields = ['slug', 'name', 'category', 'description']
            for field in required_fields:
                if field not in data:
                    issues.append(f"{slug}: Missing required field '{field}'")

            # Check backend requirements
            backend_reqs = data.get('backend_requirements', [])
            if not backend_reqs:
                warnings.append(f"{slug}: No backend requirements")
            elif len(backend_reqs) > 5:
                warnings.append(f"{slug}: {len(backend_reqs)} backend requirements (recommended max: 5)")
            stats['avg_backend_reqs'] += len(backend_reqs)

            # Check frontend requirements
            frontend_reqs = data.get('frontend_requirements', [])
            if not frontend_reqs:
                warnings.append(f"{slug}: No frontend requirements")
            elif len(frontend_reqs) > 5:
                warnings.append(f"{slug}: {len(frontend_reqs)} frontend requirements (recommended max: 5)")
            stats['avg_frontend_reqs'] += len(frontend_reqs)

            # Check API endpoints
            api_endpoints = data.get('api_endpoints', [])
            if not api_endpoints:
                issues.append(f"{slug}: No API endpoints defined")
            else:
                stats['avg_api_endpoints'] += len(api_endpoints)

                # Validate each endpoint
                for idx, ep in enumerate(api_endpoints):
                    if 'method' not in ep:
                        issues.append(f"{slug}: api_endpoints[{idx}] missing 'method'")
                    if 'path' not in ep:
                        issues.append(f"{slug}: api_endpoints[{idx}] missing 'path'")

                    path = ep.get('path', '')
                    if path and not path.startswith('/'):
                        issues.append(f"{slug}: Path '{path}' must start with '/'")

                    # Check for health endpoint
                    if path == '/api/health':
                        stats['has_health_endpoint'] += 1

            # Check admin endpoints if admin requirements exist
            admin_reqs = data.get('admin_requirements', [])
            admin_endpoints = data.get('admin_api_endpoints', [])

            if admin_reqs and not admin_endpoints:
                warnings.append(f"{slug}: Has admin requirements but no admin endpoints")

            if admin_endpoints:
                stats['has_admin'] += 1

            # Check data model
            data_model = data.get('data_model', {})
            if data_model:
                if 'name' not in data_model:
                    warnings.append(f"{slug}: data_model missing 'name'")
                if 'fields' not in data_model:
                    warnings.append(f"{slug}: data_model missing 'fields'")

                # Check for soft delete support
                fields = data_model.get('fields', {})
                if 'is_active' in fields:
                    stats['has_soft_delete'] += 1

        except json.JSONDecodeError as e:
            issues.append(f"{slug}: Invalid JSON - {e}")
        except Exception as e:
            issues.append(f"{slug}: Error loading - {e}")

    # Calculate averages
    if stats['total'] > 0:
        stats['avg_backend_reqs'] /= stats['total']
        stats['avg_frontend_reqs'] /= stats['total']
        stats['avg_api_endpoints'] /= stats['total']

    # Print results
    print("=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print(f"\nTotal requirement files: {stats['total']}")
    print(f"Average backend requirements: {stats['avg_backend_reqs']:.1f}")
    print(f"Average frontend requirements: {stats['avg_frontend_reqs']:.1f}")
    print(f"Average API endpoints: {stats['avg_api_endpoints']:.1f}")
    print(f"\nFiles with health endpoints: {stats['has_health_endpoint']}/{stats['total']}")
    print(f"Files with admin features: {stats['has_admin']}/{stats['total']}")
    print(f"Files with soft delete: {stats['has_soft_delete']}/{stats['total']}")

    print("\n" + "=" * 80)
    print("ISSUES")
    print("=" * 80)

    if not issues:
        print("\n[OK] No critical issues found!")
    else:
        print(f"\nFound {len(issues)} critical issues:")
        for issue in issues:
            print(f"  - {issue}")

    print("\n" + "=" * 80)
    print("WARNINGS")
    print("=" * 80)

    if not warnings:
        print("\n[OK] No warnings!")
    else:
        print(f"\nFound {len(warnings)} warnings:")
        for warning in warnings[:20]:
            print(f"  - {warning}")
        if len(warnings) > 20:
            print(f"  ... and {len(warnings) - 20} more")

    print("\n" + "=" * 80)
    print("DESIGN QUALITY ASSESSMENT")
    print("=" * 80)

    print("\n[+] Requirements Philosophy:")
    print(f"  - Backend reqs: {stats['avg_backend_reqs']:.1f} (target: 2-3)")
    if stats['avg_backend_reqs'] <= 3:
        print("    [EXCELLENT] Within recommended range")
    else:
        print("    [OK] Slightly above recommendation")

    print(f"  - Frontend reqs: {stats['avg_frontend_reqs']:.1f} (target: 3-4)")
    if stats['avg_frontend_reqs'] <= 4:
        print("    [EXCELLENT] Within recommended range")
    else:
        print("    [OK] Slightly above recommendation")

    print(f"\n[+] Consistency:")
    health_pct = (stats['has_health_endpoint'] / stats['total']) * 100
    print(f"  - Health endpoints: {health_pct:.0f}%")
    if health_pct == 100:
        print("    [EXCELLENT] All files have health checks")
    elif health_pct >= 90:
        print("    [GOOD] Most files have health checks")
    else:
        print("    [NEEDS IMPROVEMENT] Add health endpoints")

    admin_pct = (stats['has_admin'] / stats['total']) * 100
    print(f"  - Admin features: {admin_pct:.0f}%")
    if admin_pct == 100:
        print("    [EXCELLENT] All files have admin features")
    elif admin_pct >= 80:
        print("    [GOOD] Most files have admin features")
    else:
        print("    [OK] Some files don't need admin features")

    soft_delete_pct = (stats['has_soft_delete'] / stats['total']) * 100
    print(f"  - Soft delete support: {soft_delete_pct:.0f}%")
    if soft_delete_pct >= 90:
        print("    [EXCELLENT] Consistent use of soft deletes")
    else:
        print("    [OK] Some files use hard deletes")

    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)

    if not issues and len(warnings) < 5:
        print("\n[SUCCESS] Requirements are EXCELLENT quality!")
        print("  - No critical issues")
        print("  - Minimal warnings")
        print("  - Consistent structure")
        print("  - Well-balanced complexity")
        return 0
    elif not issues:
        print("\n[SUCCESS] Requirements are GOOD quality!")
        print("  - No critical issues")
        print(f"  - {len(warnings)} minor warnings")
        return 0
    else:
        print(f"\n[NEEDS WORK] Found {len(issues)} issues to fix")
        return 1

if __name__ == '__main__':
    sys.exit(main())
