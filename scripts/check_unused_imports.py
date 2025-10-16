#!/usr/bin/env python3
"""
Check for unused imports in Python files using AST analysis.
This is a simple static analysis that can run without Pylance MCP.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ImportChecker(ast.NodeVisitor):
    """AST visitor to track imports and their usage."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.imports: Dict[str, Tuple[int, str]] = {}  # name -> (line, module)
        self.used_names: Set[str] = set()
        self.in_import = False
        
    def visit_Import(self, node: ast.Import) -> None:
        """Track 'import X' statements."""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports[name] = (node.lineno, alias.name)
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track 'from X import Y' statements."""
        for alias in node.names:
            if alias.name == '*':
                continue  # Skip star imports
            name = alias.asname if alias.asname else alias.name
            module = node.module or ''
            self.imports[name] = (node.lineno, f"{module}.{alias.name}")
        self.generic_visit(node)
        
    def visit_Name(self, node: ast.Name) -> None:
        """Track name usage."""
        if not self.in_import:
            self.used_names.add(node.id)
        self.generic_visit(node)
        
    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Track attribute access (e.g., module.function)."""
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)


def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Check a single file for unused imports.
    Returns list of (line_number, import_name, module).
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        checker = ImportChecker(str(file_path))
        checker.visit(tree)
        
        # Find unused imports
        unused = []
        for name, (line, module) in checker.imports.items():
            if name not in checker.used_names:
                # Ignore some common patterns that are intentionally imported
                if name.startswith('_') and not name.startswith('__'):
                    continue  # Private imports might be for side effects
                if name in ['annotations']:  # from __future__
                    continue
                unused.append((line, name, module))
        
        return sorted(unused)
        
    except SyntaxError as e:
        print(f"⚠️  Syntax error in {file_path}: {e}")
        return []
    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}")
        return []


def main():
    """Main entry point."""
    root_dir = Path(__file__).resolve().parent.parent
    src_dir = root_dir / "src"
    
    if not src_dir.exists():
        print(f"❌ Source directory not found: {src_dir}")
        sys.exit(1)
    
    print("🔍 Checking for unused imports in Python files...\n")
    
    # Find all Python files
    py_files = list(src_dir.rglob("*.py"))
    print(f"📁 Analyzing {len(py_files)} Python files...\n")
    
    # Check each file
    files_with_issues = {}
    total_unused = 0
    
    for py_file in py_files:
        unused = check_file(py_file)
        if unused:
            rel_path = py_file.relative_to(root_dir)
            files_with_issues[rel_path] = unused
            total_unused += len(unused)
    
    # Print results
    if not files_with_issues:
        print("✅ No unused imports found! Code is clean.\n")
        return
    
    print(f"📊 Found {total_unused} unused imports in {len(files_with_issues)} files:\n")
    print("=" * 80)
    
    for file_path, unused in sorted(files_with_issues.items()):
        print(f"\n📄 {file_path}")
        for line, name, module in unused:
            print(f"   Line {line:4d}: {name:20s} (from {module})")
    
    print("\n" + "=" * 80)
    print("\n💡 To fix: Remove unused imports manually or use tools like:")
    print("   - autoflake: pip install autoflake")
    print("   - autoflake --remove-all-unused-imports --in-place <file>")
    print()


if __name__ == '__main__':
    main()
