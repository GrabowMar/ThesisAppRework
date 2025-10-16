#!/usr/bin/env python3
"""
Comprehensive dead code and redundancy analyzer for ThesisAppRework.
Identifies unused files, legacy code, bloated modules, and redundant patterns.
"""

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

class DeadCodeAnalyzer:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.src_dir = root_dir / "src"
        self.imports = defaultdict(set)
        self.definitions = defaultdict(set)
        self.files_analyzed = set()
        self.suspicious_files = []
        self.bloated_files = []
        self.legacy_patterns = []
        self.unused_imports = defaultdict(list)
        
    def analyze(self):
        """Run all analysis passes."""
        print("🔍 Analyzing codebase for dead code and redundancies...\n")
        
        # Pass 1: Find all Python files
        py_files = self._find_python_files()
        print(f"📁 Found {len(py_files)} Python files\n")
        
        # Pass 2: Parse imports and definitions
        for file_path in py_files:
            self._analyze_file(file_path)
        
        # Pass 3: Find unused code
        self._find_unused_definitions()
        self._find_suspicious_files()
        self._find_bloated_files()
        self._find_legacy_patterns()
        
        # Generate report
        self._generate_report()
        
    def _find_python_files(self) -> List[Path]:
        """Find all Python files in src directory."""
        py_files = []
        for root, dirs, files in os.walk(self.src_dir):
            # Skip __pycache__, .venv, etc.
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for file in files:
                if file.endswith('.py'):
                    py_files.append(Path(root) / file)
        return py_files
    
    def _analyze_file(self, file_path: Path):
        """Analyze a single Python file for imports and definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check file size
            size_kb = len(content) / 1024
            if size_kb > 50:  # Files larger than 50KB might be bloated
                self.bloated_files.append((file_path, size_kb))
            
            tree = ast.parse(content, filename=str(file_path))
            
            # Track imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.imports[file_path].add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for alias in node.names:
                            self.imports[file_path].add(f"{node.module}.{alias.name}")
                
                # Track definitions
                elif isinstance(node, ast.FunctionDef):
                    self.definitions[file_path].add(('function', node.name))
                elif isinstance(node, ast.ClassDef):
                    self.definitions[file_path].add(('class', node.name))
            
            self.files_analyzed.add(file_path)
            
        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")
    
    def _find_unused_definitions(self):
        """Find definitions that are never imported/used."""
        # This is a simplified heuristic
        all_imports = set()
        for imports in self.imports.values():
            all_imports.update(imports)
        
        # Check if definitions are used
        for file_path, defs in self.definitions.items():
            for def_type, def_name in defs:
                # Skip special names
                if def_name.startswith('_') and not def_name.startswith('__'):
                    continue
                
                # Check if this definition is imported anywhere
                module_name = self._get_module_name(file_path)
                full_name = f"{module_name}.{def_name}"
                
                # Heuristic: if not found in imports, might be unused
                # (This is not perfect but gives us a starting point)
                if not any(full_name in imp or def_name in imp for imp in all_imports):
                    if def_type == 'function' and def_name not in ['main', 'create_app', '__init__']:
                        self.suspicious_files.append((file_path, def_type, def_name))
    
    def _find_suspicious_files(self):
        """Find files that might be unused based on naming and content."""
        suspicious_patterns = [
            'legacy', 'old', 'backup', 'deprecated', 'unused', 
            'temp', 'tmp', 'test_old', '_bak'
        ]
        
        for file_path in self.files_analyzed:
            file_name = file_path.name.lower()
            if any(pattern in file_name for pattern in suspicious_patterns):
                self.legacy_patterns.append((file_path, "Suspicious filename"))
            
            # Check for legacy markers in content
            try:
                content = file_path.read_text(encoding='utf-8')
                if 'DEPRECATED' in content or 'LEGACY' in content or 'TODO: remove' in content:
                    self.legacy_patterns.append((file_path, "Contains legacy markers"))
            except Exception:
                pass
    
    def _find_bloated_files(self):
        """Already populated in _analyze_file."""
        self.bloated_files.sort(key=lambda x: x[1], reverse=True)
    
    def _find_legacy_patterns(self):
        """Find legacy code patterns in the codebase."""
        # Check docs/archive for content that might be deleted
        archive_dir = self.root_dir / "docs" / "archive"
        if archive_dir.exists():
            archive_files = list(archive_dir.glob("*.md"))
            if len(archive_files) > 30:  # Lots of archive files
                self.legacy_patterns.append(
                    (archive_dir, f"{len(archive_files)} archive files - consider cleanup")
                )
    
    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to Python module name."""
        rel_path = file_path.relative_to(self.src_dir)
        parts = list(rel_path.parts[:-1]) + [rel_path.stem]
        return '.'.join(parts)
    
    def _generate_report(self):
        """Generate comprehensive report."""
        print("\n" + "="*80)
        print("🎯 DEAD CODE ANALYSIS REPORT")
        print("="*80 + "\n")
        
        # Section 1: Bloated Files
        print("📦 BLOATED FILES (>50KB)")
        print("-" * 80)
        if self.bloated_files:
            for file_path, size_kb in self.bloated_files[:10]:
                rel_path = file_path.relative_to(self.root_dir)
                print(f"  • {rel_path}")
                print(f"    Size: {size_kb:.1f}KB")
        else:
            print("  ✅ No significantly large files found")
        print()
        
        # Section 2: Legacy Patterns
        print("🗑️  LEGACY/SUSPICIOUS FILES")
        print("-" * 80)
        if self.legacy_patterns:
            seen = set()
            for item, reason in self.legacy_patterns:
                if item not in seen:
                    seen.add(item)
                    try:
                        rel_path = item.relative_to(self.root_dir)
                    except Exception:
                        rel_path = item
                    print(f"  • {rel_path}")
                    print(f"    Reason: {reason}")
        else:
            print("  ✅ No obvious legacy patterns found")
        print()
        
        # Section 3: Import Analysis
        print("📊 IMPORT STATISTICS")
        print("-" * 80)
        total_imports = sum(len(imps) for imps in self.imports.values())
        print(f"  Total imports: {total_imports}")
        print(f"  Files with imports: {len(self.imports)}")
        if self.imports:
            avg_imports = total_imports / len(self.imports)
            print(f"  Average imports per file: {avg_imports:.1f}")
        print()
        
        # Section 4: Files with most imports (might be overly coupled)
        print("🔗 FILES WITH MOST IMPORTS (Potential refactoring candidates)")
        print("-" * 80)
        sorted_imports = sorted(self.imports.items(), key=lambda x: len(x[1]), reverse=True)
        for file_path, imps in sorted_imports[:10]:
            if len(imps) > 15:  # Threshold for "too many imports"
                rel_path = file_path.relative_to(self.root_dir)
                print(f"  • {rel_path}: {len(imps)} imports")
        print()
        
        # Section 5: Specific recommendations
        print("💡 SPECIFIC RECOMMENDATIONS")
        print("-" * 80)
        
        # Check for template_paths.py legacy code
        template_paths = self.src_dir / "app" / "utils" / "template_paths.py"
        if template_paths.exists():
            print("  • template_paths.py contains legacy compatibility layer")
            print("    Consider: Remove if all templates have been migrated")
        
        # Check archive directory
        archive_dir = self.root_dir / "docs" / "archive"
        if archive_dir.exists():
            archive_count = len(list(archive_dir.glob("*.md")))
            if archive_count > 30:
                print(f"  • docs/archive contains {archive_count} old documentation files")
                print("    Consider: Archive to separate repo or compress to single legacy.md")
        
        # Check for __pycache__
        pycache_dirs = list(self.root_dir.rglob("__pycache__"))
        if pycache_dirs:
            print(f"  • Found {len(pycache_dirs)} __pycache__ directories")
            print("    Consider: Add to .gitignore and clean up")
        
        # Check for .pyc files
        pyc_files = list(self.root_dir.rglob("*.pyc"))
        if pyc_files:
            print(f"  • Found {len(pyc_files)} .pyc files")
            print("    Consider: Clean up bytecode files")
        
        print()
        print("="*80)
        print("✅ Analysis complete!")
        print("="*80)

def main():
    root_dir = Path(__file__).resolve().parent.parent
    analyzer = DeadCodeAnalyzer(root_dir)
    analyzer.analyze()

if __name__ == '__main__':
    main()
