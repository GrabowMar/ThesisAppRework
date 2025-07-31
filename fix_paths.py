#!/usr/bin/env python3
"""
Fix path resolution issues in security_analysis_service.py
"""
import re

def fix_security_analysis_paths():
    """Fix all path resolution issues in security_analysis_service.py"""
    
    # Read the file
    with open('src/security_analysis_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count current occurrences
    models_count = content.count('/ "models" / model /')
    workspace_root_count = content.count('workspace_root = self.base_path.parent')
    
    print(f"Found {models_count} instances of '/ \"models\" / model /'")
    print(f"Found {workspace_root_count} instances of 'workspace_root = self.base_path.parent'")
    
    # Fix Pattern 1: workspace_root calculation 
    # Only replace if not already followed by 'if'
    old_pattern = 'workspace_root = self.base_path.parent'
    new_pattern = 'workspace_root = self.base_path.parent if self.base_path.name == "src" else self.base_path'
    
    # Replace only the ones that don't already have the if condition
    content = re.sub(
        r'workspace_root = self\.base_path\.parent(?!\s+if)',
        new_pattern,
        content
    )
    
    # Fix Pattern 2: models path to misc/models
    content = content.replace('/ "models" / model /', '/ "misc" / "models" / model /')
    
    # Write the fixed content back
    with open('src/security_analysis_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Count after changes
    with open('src/security_analysis_service.py', 'r', encoding='utf-8') as f:
        new_content = f.read()
    
    new_models_count = new_content.count('/ "misc" / "models" / model /')
    new_workspace_root_count = new_content.count('if self.base_path.name == "src"')
    
    print(f"\nAfter fixes:")
    print(f"- {new_models_count} instances now use '/ \"misc\" / \"models\" / model /'")
    print(f"- {new_workspace_root_count} instances now have workspace_root with src condition")
    print("✓ All path resolution issues fixed!")

if __name__ == "__main__":
    fix_security_analysis_paths()
