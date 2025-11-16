#!/usr/bin/env python3
"""
Test script to verify SARIF extraction in service snapshots.
Compares file sizes before/after the fix.
"""

import json
import sys
from pathlib import Path

def analyze_service_snapshot(filepath):
    """Analyze a service snapshot file for SARIF content."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    file_size = filepath.stat().st_size
    
    # Count lines
    with open(filepath, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    
    # Check if SARIF is embedded or referenced
    has_embedded_sarif = False
    has_sarif_refs = False
    sarif_sections = []
    
    def check_for_sarif(obj, path=""):
        nonlocal has_embedded_sarif, has_sarif_refs
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if key == "sarif" and isinstance(value, dict) and "$schema" in value:
                    has_embedded_sarif = True
                    sarif_sections.append(new_path)
                elif key == "sarif_file" and isinstance(value, str):
                    has_sarif_refs = True
                    sarif_sections.append(f"{new_path} (ref: {value})")
                else:
                    check_for_sarif(value, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_for_sarif(item, f"{path}[{i}]")
    
    check_for_sarif(data)
    
    return {
        'filepath': str(filepath),
        'size_bytes': file_size,
        'size_mb': file_size / (1024 * 1024),
        'line_count': line_count,
        'has_embedded_sarif': has_embedded_sarif,
        'has_sarif_refs': has_sarif_refs,
        'sarif_sections': sarif_sections
    }

def main():
    # Test the known bloated file
    old_file = Path("results/anthropic_claude-4.5-haiku-20251001/app4/task_6196ea8b2e21/services/anthropic_claude-4.5-haiku-20251001_app4_static.json")
    
    if not old_file.exists():
        print(f"❌ File not found: {old_file}")
        return 1
    
    print("=" * 80)
    print("SARIF Extraction Test - Service Snapshot Analysis")
    print("=" * 80)
    
    old_analysis = analyze_service_snapshot(old_file)
    
    print(f"\n📄 OLD FILE (before fix):")
    print(f"   Path: {old_analysis['filepath']}")
    print(f"   Size: {old_analysis['size_mb']:.2f} MB ({old_analysis['size_bytes']:,} bytes)")
    print(f"   Lines: {old_analysis['line_count']:,}")
    print(f"   Embedded SARIF: {'✅ YES (bloated)' if old_analysis['has_embedded_sarif'] else '❌ NO'}")
    print(f"   SARIF References: {'✅ YES' if old_analysis['has_sarif_refs'] else '❌ NO'}")
    
    if old_analysis['sarif_sections']:
        print(f"\n   SARIF sections found:")
        for section in old_analysis['sarif_sections'][:5]:  # Show first 5
            print(f"     - {section}")
        if len(old_analysis['sarif_sections']) > 5:
            print(f"     ... and {len(old_analysis['sarif_sections']) - 5} more")
    
    # Check for newer results
    app_dir = Path("results/anthropic_claude-4.5-haiku-20251001/app4")
    if app_dir.exists():
        task_dirs = sorted([d for d in app_dir.iterdir() if d.is_dir() and d.name.startswith("task_")], 
                          key=lambda x: x.stat().st_mtime, reverse=True)
        
        if len(task_dirs) > 1:
            new_task_dir = task_dirs[0]
            new_file = new_task_dir / "services" / "anthropic_claude-4.5-haiku-20251001_app4_static.json"
            
            if new_file.exists() and new_file != old_file:
                new_analysis = analyze_service_snapshot(new_file)
                
                print(f"\n📄 NEW FILE (after fix):")
                print(f"   Path: {new_analysis['filepath']}")
                print(f"   Size: {new_analysis['size_mb']:.2f} MB ({new_analysis['size_bytes']:,} bytes)")
                print(f"   Lines: {new_analysis['line_count']:,}")
                print(f"   Embedded SARIF: {'✅ YES (bloated)' if new_analysis['has_embedded_sarif'] else '❌ NO (fixed!)'}")
                print(f"   SARIF References: {'✅ YES (fixed!)' if new_analysis['has_sarif_refs'] else '❌ NO'}")
                
                # Calculate improvements
                size_reduction = old_analysis['size_bytes'] - new_analysis['size_bytes']
                size_reduction_pct = (size_reduction / old_analysis['size_bytes']) * 100
                line_reduction = old_analysis['line_count'] - new_analysis['line_count']
                line_reduction_pct = (line_reduction / old_analysis['line_count']) * 100
                
                print(f"\n📊 IMPROVEMENT:")
                print(f"   Size reduction: {size_reduction / (1024 * 1024):.2f} MB ({size_reduction_pct:.1f}%)")
                print(f"   Line reduction: {line_reduction:,} lines ({line_reduction_pct:.1f}%)")
                
                if new_analysis['has_sarif_refs'] and not new_analysis['has_embedded_sarif']:
                    print(f"\n✅ FIX VERIFIED: Service snapshots now use SARIF references!")
                else:
                    print(f"\n⚠️  FIX INCOMPLETE: Still has embedded SARIF data")
            else:
                print(f"\n⏳ No new results found yet. Run a new analysis to test the fix.")
        else:
            print(f"\n⏳ Only one task found. Run a new analysis to test the fix.")
    
    print("\n" + "=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
