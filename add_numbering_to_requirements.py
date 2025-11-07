"""Add numbering to all requirement files for better readability."""
import json
from pathlib import Path

REQUIREMENTS_DIR = Path('misc/requirements')

def add_numbering_to_list(items):
    """Add numbering to a list of items if not already numbered."""
    if not items:
        return items
    
    numbered_items = []
    for i, item in enumerate(items, 1):
        # Check if already numbered (starts with "N. " pattern)
        if item.strip().startswith(f"{i}. "):
            numbered_items.append(item)
        else:
            numbered_items.append(f"{i}. {item}")
    
    return numbered_items

def process_requirements_file(filepath):
    """Add numbering to backend and frontend requirements in a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified = False
        
        # Add numbering to backend_requirements
        if 'backend_requirements' in data and isinstance(data['backend_requirements'], list):
            original = data['backend_requirements']
            numbered = add_numbering_to_list(original)
            if numbered != original:
                data['backend_requirements'] = numbered
                modified = True
        
        # Add numbering to frontend_requirements
        if 'frontend_requirements' in data and isinstance(data['frontend_requirements'], list):
            original = data['frontend_requirements']
            numbered = add_numbering_to_list(original)
            if numbered != original:
                data['frontend_requirements'] = numbered
                modified = True
        
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✓ Updated {filepath.name}")
            return True
        else:
            print(f"  Skipped {filepath.name} (already numbered)")
            return False
            
    except Exception as e:
        print(f"✗ Error processing {filepath.name}: {e}")
        return False

def main():
    """Process all JSON files in requirements directory."""
    if not REQUIREMENTS_DIR.exists():
        print(f"Error: Requirements directory not found: {REQUIREMENTS_DIR}")
        return
    
    json_files = list(REQUIREMENTS_DIR.glob('*.json'))
    if not json_files:
        print(f"No JSON files found in {REQUIREMENTS_DIR}")
        return
    
    print(f"Processing {len(json_files)} requirement files...\n")
    
    updated_count = 0
    for filepath in sorted(json_files):
        if process_requirements_file(filepath):
            updated_count += 1
    
    print(f"\n✓ Complete! Updated {updated_count}/{len(json_files)} files")

if __name__ == '__main__':
    main()
