"""
Quick utility: find templates under src/templates that are not referenced by any
Python route or other templates. Intended for local use to keep the codebase lean.

Usage:
  python scripts/find_unused_templates.py
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "templates"
INCLUDE_DIRS = [ROOT / "src"]

def gather_template_files():
    return [p for p in TEMPLATES.rglob("*.html")]

def gather_source_texts():
    texts = []
    patterns = ["*.py", "*.html"]
    for base in INCLUDE_DIRS:
        for pat in patterns:
            for f in base.rglob(pat):
                try:
                    texts.append(f.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    pass
    return "\n".join(texts)

def main():
    files = gather_template_files()
    haystack = gather_source_texts()
    unused = []
    for f in files:
        # Use forward slashes for Jinja paths and search both absolute and partial path forms
        rel = f.relative_to(TEMPLATES).as_posix()
        jinja_path = rel
        used = False
        # common include patterns
        candidates = [
            re.escape(jinja_path),
            re.escape(jinja_path.replace("\\", "/")),
        ]
        for pat in candidates:
            if re.search(pat, haystack):
                used = True
                break
        if not used:
            unused.append(rel)

    if unused:
        print("Unused templates (candidate):")
        for u in sorted(unused):
            print(" -", u)
    else:
        print("No unused templates detected.")

# Deprecated no-op to avoid repo bloat
if __name__ == '__main__':
    pass
