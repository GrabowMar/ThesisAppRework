#!/usr/bin/env python3
"""
Unused Code Detector
====================
Scans the codebase for potentially unused Python files, JavaScript files,
and templates based on import analysis and reference counts.
"""
import os
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Root directory
ROOT = Path(__file__).parent.parent
SRC = ROOT / 'src'

class UnusedCodeDetector:
    def __init__(self):
        self.python_files: Set[Path] = set()
        self.js_files: Set[Path] = set()
        self.template_files: Set[Path] = set()
        self.python_imports: Dict[Path, Set[str]] = defaultdict(set)
        self.import_references: Dict[str, int] = defaultdict(int)
        self.file_references: Dict[Path, int] = defaultdict(int)
        
    def scan_files(self):
        """Scan all code files."""
        print("📁 Scanning files...")
        
        for root, dirs, files in os.walk(SRC):
            # Skip virtual environments, __pycache__, node_modules
            dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', 'node_modules', '.pytest_cache'}]
            
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                
                if file.endswith('.py'):
                    self.python_files.add(file_path)
                elif file.endswith('.js'):
                    self.js_files.add(file_path)
                elif file.endswith('.html'):
                    self.template_files.add(file_path)
        
        print(f"   Found {len(self.python_files)} Python files")
        print(f"   Found {len(self.js_files)} JavaScript files")
        print(f"   Found {len(self.template_files)} HTML templates")
    
    def analyze_python_imports(self):
        """Analyze Python imports and count references."""
        print("\n🔍 Analyzing Python imports...")
        
        import_pattern = re.compile(r'^\s*(?:from|import)\s+([a-zA-Z0-9_.]+)', re.MULTILINE)
        
        for py_file in self.python_files:
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                
                # Find all imports
                for match in import_pattern.finditer(content):
                    module = match.group(1)
                    self.python_imports[py_file].add(module)
                    self.import_references[module] += 1
                
                # Count file references (simple grep-like search)
                file_stem = py_file.stem
                if file_stem != '__init__':
                    # Search for references in other files
                    pattern = re.compile(rf'\b{re.escape(file_stem)}\b')
                    ref_count = 0
                    
                    for other_file in self.python_files:
                        if other_file != py_file:
                            try:
                                other_content = other_file.read_text(encoding='utf-8', errors='ignore')
                                ref_count += len(pattern.findall(other_content))
                            except Exception:
                                pass
                    
                    self.file_references[py_file] = ref_count
                    
            except Exception as e:
                print(f"   Warning: Could not analyze {py_file}: {e}")
    
    def analyze_js_usage(self):
        """Analyze JavaScript file usage."""
        print("\n🔍 Analyzing JavaScript usage...")
        
        for js_file in self.js_files:
            js_name = js_file.name
            ref_count = 0
            
            # Search in HTML templates
            for template in self.template_files:
                try:
                    content = template.read_text(encoding='utf-8', errors='ignore')
                    if js_name in content:
                        ref_count += content.count(js_name)
                except Exception:
                    pass
            
            self.file_references[js_file] = ref_count
    
    def analyze_template_usage(self):
        """Analyze template file usage."""
        print("\n🔍 Analyzing template usage...")
        
        for template in self.template_files:
            template_name = template.name
            ref_count = 0
            
            # Search in Python files for render_template calls
            for py_file in self.python_files:
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    if template_name in content:
                        ref_count += content.count(template_name)
                except Exception:
                    pass
            
            self.file_references[template] = ref_count
    
    def find_unused_python_files(self, threshold: int = 1) -> List[Tuple[Path, int]]:
        """Find Python files with low reference counts."""
        unused = []
        
        for py_file, ref_count in self.file_references.items():
            if py_file.suffix == '.py' and ref_count <= threshold:
                # Skip __init__.py files
                if py_file.name == '__init__.py':
                    continue
                    
                # Skip entry points
                if py_file.name in {'main.py', 'worker.py', 'init_db.py', 'process_manager.py'}:
                    continue
                
                # Skip test files
                if 'test' in py_file.name or 'conftest' in py_file.name:
                    continue
                
                unused.append((py_file, ref_count))
        
        return sorted(unused, key=lambda x: x[1])
    
    def find_unused_js_files(self, threshold: int = 0) -> List[Tuple[Path, int]]:
        """Find JavaScript files with no references."""
        unused = []
        
        for js_file, ref_count in self.file_references.items():
            if js_file.suffix == '.js' and ref_count <= threshold:
                unused.append((js_file, ref_count))
        
        return sorted(unused, key=lambda x: x[1])
    
    def find_unused_templates(self, threshold: int = 0) -> List[Tuple[Path, int]]:
        """Find templates with no references."""
        unused = []
        
        for template, ref_count in self.file_references.items():
            if template.suffix == '.html' and ref_count <= threshold:
                # Skip layout/component templates (often indirectly included)
                if 'layout' in str(template) or 'component' in str(template) or 'macro' in str(template):
                    continue
                    
                unused.append((template, ref_count))
        
        return sorted(unused, key=lambda x: x[1])
    
    def print_report(self):
        """Print comprehensive report."""
        print("\n" + "="*80)
        print("UNUSED CODE DETECTION REPORT")
        print("="*80)
        
        # Python files
        unused_py = self.find_unused_python_files(threshold=1)
        print(f"\n📄 PYTHON FILES (≤1 reference): {len(unused_py)} candidates")
        print("-" * 80)
        
        for file_path, refs in unused_py[:20]:  # Top 20
            rel_path = file_path.relative_to(ROOT)
            size = file_path.stat().st_size
            print(f"  {refs:3d} refs | {size:6d} bytes | {rel_path}")
        
        if len(unused_py) > 20:
            print(f"  ... and {len(unused_py) - 20} more")
        
        # JavaScript files
        unused_js = self.find_unused_js_files(threshold=0)
        print(f"\n📜 JAVASCRIPT FILES (0 references): {len(unused_js)} candidates")
        print("-" * 80)
        
        for file_path, refs in unused_js[:10]:
            rel_path = file_path.relative_to(ROOT)
            size = file_path.stat().st_size
            print(f"  {refs:3d} refs | {size:6d} bytes | {rel_path}")
        
        # Templates
        unused_templates = self.find_unused_templates(threshold=0)
        print(f"\n📋 TEMPLATES (0 references): {len(unused_templates)} candidates")
        print("-" * 80)
        
        for file_path, refs in unused_templates[:10]:
            rel_path = file_path.relative_to(ROOT)
            size = file_path.stat().st_size
            print(f"  {refs:3d} refs | {size:6d} bytes | {rel_path}")
        
        # Summary
        total_unused = len(unused_py) + len(unused_js) + len(unused_templates)
        print("\n" + "="*80)
        print(f"TOTAL CANDIDATES: {total_unused}")
        print("="*80)
        print("\n⚠️  NOTE: Review each file carefully before deletion!")
        print("   Some files may be entry points, dynamically loaded, or external APIs.")

def main():
    detector = UnusedCodeDetector()
    detector.scan_files()
    detector.analyze_python_imports()
    detector.analyze_js_usage()
    detector.analyze_template_usage()
    detector.print_report()

if __name__ == '__main__':
    main()
