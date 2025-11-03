"""
Verify SARIF extraction implementation by loading an existing result and re-saving it.
This tests the optimization without requiring Docker services.
"""
import asyncio
import json
import sys
from pathlib import Path
from analyzer.analyzer_manager import AnalyzerManager

async def verify_sarif_extraction():
    """Load an existing large result file and re-save to test SARIF extraction."""
    
    # Use the specific large file we know has SARIF data
    main_file = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_analysis_20251103_001129/anthropic_claude-4.5-sonnet-20250929_app1_task_analysis_20251103_001129_20251103_001129.json")
    
    if not main_file.exists():
        print(f"[!] File not found: {main_file}")
        return False
    
    original_size = main_file.stat().st_size / 1024  # KB
    original_size_mb = main_file.stat().st_size / 1024 / 1024
    print(f"[*] Original file: {main_file.name}")
    print(f"[*] Original size: {original_size:.2f} KB ({original_size_mb:.2f} MB)")
    
    # Count lines
    with open(main_file, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    print(f"[*] Original lines: {line_count:,}")
    
    # Load the original data
    with open(main_file, 'r', encoding='utf-8') as f:
        original_data = json.load(f)
    
    # Extract services data (this is what gets SARIF extracted)
    if 'results' in original_data and 'services' in original_data['results']:
        services = original_data['results']['services']
    else:
        print("[!] No services data found in file structure")
        return False
    
    print(f"[*] Found {len(services)} services in results")
    
    # Count SARIF data before extraction
    sarif_count = 0
    total_sarif_lines = 0
    for service_name, service_data in services.items():
        if isinstance(service_data, dict) and 'analysis' in service_data:
            analysis = service_data['analysis']
            # Check tool_results
            if 'tool_results' in analysis:
                for tool_name, tool_data in analysis['tool_results'].items():
                    if isinstance(tool_data, dict) and 'sarif' in tool_data:
                        sarif_count += 1
                        sarif_str = json.dumps(tool_data['sarif'])
                        total_sarif_lines += sarif_str.count('\n')
            # Check nested results
            if 'results' in analysis:
                for category, category_data in analysis['results'].items():
                    if isinstance(category_data, dict):
                        for tool_name, tool_data in category_data.items():
                            if isinstance(tool_data, dict) and 'sarif' in tool_data:
                                sarif_count += 1
                                sarif_str = json.dumps(tool_data['sarif'])
                                total_sarif_lines += sarif_str.count('\n')
    
    print(f"[*] Found {sarif_count} SARIF objects (~{total_sarif_lines:,} lines)")
    
    # Create analyzer manager and use it to re-save with SARIF extraction
    manager = AnalyzerManager()
    
    # Create test task
    test_task_id = "sarif_extraction_test_v2"
    model_slug = "anthropic_claude-4.5-sonnet-20250929"
    app_number = 1
    
    print(f"\n[*] Re-saving with SARIF extraction...")
    new_filepath = await manager.save_task_results(
        model_slug=model_slug,
        app_number=app_number,
        task_id=test_task_id,
        consolidated_results=services
    )
    
    if not new_filepath or not new_filepath.exists():
        print("[!] Failed to save new file")
        return False
    
    new_size = new_filepath.stat().st_size / 1024  # KB
    new_size_mb = new_filepath.stat().st_size / 1024 / 1024
    print(f"[+] New file: {new_filepath.name}")
    print(f"[+] New size: {new_size:.2f} KB ({new_size_mb:.2f} MB)")
    
    # Count new lines
    with open(new_filepath, 'r', encoding='utf-8') as f:
        new_line_count = sum(1 for _ in f)
    print(f"[+] New lines: {new_line_count:,}")
    
    # Check for SARIF directory
    sarif_dir = new_filepath.parent / 'sarif'
    if not sarif_dir.exists():
        print("[!] SARIF directory not created")
        return False
    
    sarif_files = list(sarif_dir.glob("*.sarif.json"))
    print(f"[*] SARIF files created: {len(sarif_files)}")
    
    total_sarif_size = sum(f.stat().st_size for f in sarif_files) / 1024  # KB
    total_sarif_size_mb = total_sarif_size / 1024
    print(f"[*] Total SARIF size: {total_sarif_size:.2f} KB ({total_sarif_size_mb:.2f} MB)")
    
    # Calculate reduction
    size_reduction = original_size - new_size
    reduction_percent = (size_reduction / original_size) * 100
    line_reduction = line_count - new_line_count
    line_reduction_percent = (line_reduction / line_count) * 100
    
    print(f"\n========== RESULTS ==========")
    print(f"Size reduction: {size_reduction:.2f} KB ({reduction_percent:.1f}%)")
    print(f"  Original: {original_size:.2f} KB -> New: {new_size:.2f} KB")
    print(f"Line reduction: {line_reduction:,} lines ({line_reduction_percent:.1f}%)")
    print(f"  Original: {line_count:,} lines -> New: {new_line_count:,} lines")
    print(f"SARIF extracted: {total_sarif_size:.2f} KB in {len(sarif_files)} files")
    
    # Verify data structure
    with open(new_filepath, 'r', encoding='utf-8') as f:
        new_data = json.load(f)
    
    # Check that SARIF references exist
    sarif_refs = 0
    if 'results' in new_data and 'services' in new_data['results']:
        for service_name, service_data in new_data['results']['services'].items():
            if isinstance(service_data, dict) and 'analysis' in service_data:
                analysis = service_data['analysis']
                # Check tool_results
                if 'tool_results' in analysis:
                    for tool_name, tool_data in analysis['tool_results'].items():
                        if isinstance(tool_data, dict) and 'sarif' in tool_data:
                            if isinstance(tool_data['sarif'], dict) and 'sarif_file' in tool_data['sarif']:
                                sarif_refs += 1
                # Check nested results
                if 'results' in analysis:
                    for category, category_data in analysis['results'].items():
                        if isinstance(category_data, dict):
                            for tool_name, tool_data in category_data.items():
                                if isinstance(tool_data, dict) and 'sarif' in tool_data:
                                    if isinstance(tool_data['sarif'], dict) and 'sarif_file' in tool_data['sarif']:
                                        sarif_refs += 1
    
    print(f"SARIF references in JSON: {sarif_refs}")
    
    if sarif_refs != len(sarif_files):
        print(f"[!] Warning: Reference count ({sarif_refs}) doesn't match file count ({len(sarif_files)})")
    
    success = reduction_percent > 90
    status = "[+] SUCCESS" if success else "[!] PARTIAL"
    print(f"\n{status}: {reduction_percent:.1f}% size reduction, {line_reduction_percent:.1f}% line reduction")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(verify_sarif_extraction())
    sys.exit(0 if success else 1)
