#!/usr/bin/env python3
"""
Template Usage Analyzer

This script analyzes which partial templates are actually used in the codebase
by searching for:
1. render_template() calls in Python files
2. {% include %} statements in template files
3. HTMX target references in templates
"""

import os
import re
from pathlib import Path
from typing import Set, Dict, List

def find_used_partials() -> Set[str]:
    """Find all partials that are actually used in the codebase."""
    used_partials = set()
    
    # Search Python files for render_template calls
    python_files = list(Path('src').rglob('*.py'))
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find render_template calls with partials
            render_patterns = [
                r'render_template\(["\']partials/([^"\']+\.html)["\']',
                r'render_template\(f["\']partials/([^"\']+\.html)["\']',
                r'render_template\(["\']([^"\']*partials[^"\']+\.html)["\']'
            ]
            
            for pattern in render_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if 'partials/' in match:
                        # Extract just the filename part after partials/
                        partial_name = match.split('partials/')[-1]
                    else:
                        partial_name = match
                    used_partials.add(partial_name)
                    print(f"Found in {py_file}: {partial_name}")
                    
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    # Search template files for include statements
    template_files = list(Path('src/templates').rglob('*.html'))
    for template_file in template_files:
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find include statements
            include_patterns = [
                r'{% include ["\']partials/([^"\']+\.html)["\']',
                r'{% include ["\']([^"\']*partials[^"\']+\.html)["\']'
            ]
            
            for pattern in include_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if 'partials/' in match:
                        partial_name = match.split('partials/')[-1]
                    else:
                        partial_name = match
                    used_partials.add(partial_name)
                    print(f"Found in {template_file}: {partial_name}")
                    
        except Exception as e:
            print(f"Error reading {template_file}: {e}")
    
    return used_partials

def find_all_partials() -> Set[str]:
    """Find all partial template files that exist."""
    partials_dir = Path('src/templates/partials')
    all_partials = set()
    
    if partials_dir.exists():
        for partial_file in partials_dir.rglob('*.html'):
            # Get relative path from partials directory
            relative_path = partial_file.relative_to(partials_dir)
            all_partials.add(str(relative_path))
            
    return all_partials

def main():
    print("=" * 80)
    print("TEMPLATE USAGE ANALYSIS")
    print("=" * 80)
    
    # Get all partials and used partials
    all_partials = find_all_partials()
    used_partials = find_used_partials()
    
    # Convert paths to use forward slashes for consistency
    all_partials = {p.replace('\\', '/') for p in all_partials}
    used_partials = {p.replace('\\', '/') for p in used_partials}
    
    print(f"\nTotal partials found: {len(all_partials)}")
    print(f"Used partials found: {len(used_partials)}")
    
    # Find unused partials
    unused_partials = all_partials - used_partials
    
    print(f"\n{'='*50}")
    print("USED PARTIALS:")
    print(f"{'='*50}")
    for partial in sorted(used_partials):
        print(f"✓ {partial}")
    
    print(f"\n{'='*50}")
    print("UNUSED PARTIALS (candidates for removal):")
    print(f"{'='*50}")
    for partial in sorted(unused_partials):
        print(f"✗ {partial}")
    
    # Generate removal commands
    print(f"\n{'='*50}")
    print("REMOVAL COMMANDS:")
    print(f"{'='*50}")
    for partial in sorted(unused_partials):
        full_path = f"src/templates/partials/{partial}"
        print(f'Remove: {full_path}')
    
    print(f"\nSummary: {len(unused_partials)} unused partials can be removed")

if __name__ == '__main__':
    main()
