"""Template Restructuring Utility

Usage (dry run by default):
  python scripts/restructure_templates.py --dry-run
Apply changes:
  python scripts/restructure_templates.py --apply
Rollback to backup:
  python scripts/restructure_templates.py --rollback 20250823_120000

Features:
- Computes mapping from old convoluted structure (components/, fragments/, partials/, views/) into
  new consolidated structure (pages/<domain>/, ui/elements/, layouts/, errors/)
- Updates Jinja `{% include %}` and `{% extends %}` path references
- Adds slug header comment to moved files if missing
- Creates timestamped backup of every file changed under `template_backups/<timestamp>/`
- Generates JSON report `RESTRUCTURE_MAPPING.json`
- Idempotent: running again will skip already-moved files unless `--force` provided

Heuristics:
- Domain list: analysis, applications, models, batch, statistics, system
- If original path starts with views/<domain>/ => page template root becomes pages/<domain>/<filename>
- Domain-specific components / partials / fragments containing domain keyword and not also used by another domain => pages/<domain>/partials/<filename>
- Shared reusable (navigation, forms, common, statistics widgets, model widgets, etc.) => ui/elements/<subfolder>/<filename>

Limitations:
- Heuristic usage graph not perfect; user can manually adjust after run.
- Does not modify Python code referencing templates; ensure your Flask `render_template` calls don't rely on removed prefixes.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Iterable

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "src" / "templates"
BACKUP_ROOT = TEMPLATE_ROOT / "template_backups"
REPORT_FILE = TEMPLATE_ROOT / "RESTRUCTURE_MAPPING.json"
DOMAINS = ["analysis", "applications", "models", "batch", "statistics", "system"]
SHARED_FOLDERS = {
    "navigation": "navigation",
    "forms": "forms",
    "common": "common",
    "dashboard": "dashboard",
    "statistics": "statistics",
    "models": "models",
    "applications": "applications",  # some may be domain-specific; filter separately
}
INCLUDE_EXTENDS_RE = re.compile(r"{%\s*(include|extends)\s*['\"]([^'\"]+)['\"][^%]*%}")
SELF_INCLUDE_RE = re.compile(r"{%\s*include\s*['\"]([^'\"]+)['\"][^%]*%}")

@dataclass
class MappingEntry:
    old: str
    new: str
    reason: str
    domain: str | None


def rel(path: Path) -> str:
    return path.relative_to(TEMPLATE_ROOT).as_posix()


def discover_html_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.html") if p.is_file()]


def build_usage_index(files: List[Path]) -> Dict[str, List[str]]:
    """Map template logical path to list of files that reference it."""
    index: Dict[str, List[str]] = defaultdict(list)
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for m in INCLUDE_EXTENDS_RE.finditer(text):
            target = m.group(2)
            index[target].append(rel(fp))
    return index


def detect_domain(name: str) -> str | None:
    parts = name.split('/')
    for part in parts:
        if part in DOMAINS:
            return part
    return None


def classify_file(path: Path, usage_index: Dict[str, List[str]]) -> Tuple[str | None, bool]:
    r = rel(path)
    # Determine if domain-specific
    domain = detect_domain(r)
    filename = path.name.lower()
    # If inside components/forms etc but referenced only by one domain -> domain-specific
    refs = usage_index.get(r, [])
    ref_domains = {detect_domain(ref) for ref in refs if detect_domain(ref)}
    if domain:
        return domain, True  # already inside domain view
    derived_domain = None
    # Check filename heuristics
    for d in DOMAINS:
        if d in filename:
            derived_domain = d
            break
    if not derived_domain and len(ref_domains) == 1:
        derived_domain = next(iter(ref_domains))
    # Domain-specific if we found exactly one domain
    if derived_domain:
        return derived_domain, True
    return None, False


def target_path_for(path: Path, usage_index: Dict[str, List[str]]) -> MappingEntry | None:
    r = rel(path)
    # Skip layouts and errors (keep as-is)
    if r.startswith("layouts/") or r.startswith("errors/") or r.startswith("template_backups/"):
        return None
    domain, domain_specific = classify_file(path, usage_index)
    if r.startswith("views/"):
        if domain:
            new_rel = f"pages/{domain}/{path.name}"
        else:
            # views/<file>.html -> pages/<file>/<file>.html
            new_rel = f"pages/{path.stem}/{path.name}"
        return MappingEntry(r, new_rel, "page view", domain)
    # components / fragments / partials
    if any(r.startswith(prefix + "/") for prefix in ("components", "fragments", "partials")):
        if domain_specific and domain:
            new_rel = f"pages/{domain}/partials/{path.name}"
            return MappingEntry(r, new_rel, "domain partial", domain)
        # shared
        # Determine bucket name
        subfolder = r.split('/')[1] if '/' in r else ''
        bucket = SHARED_FOLDERS.get(subfolder, None)
        if bucket is None:
            bucket = 'misc'
        new_rel = f"ui/elements/{bucket}/{path.name}"
        return MappingEntry(r, new_rel, "shared element", None)
    # spa handling -> treat as pages root content
    if r.startswith("spa/"):
        name = path.stem.replace('_content', '')
        for d in DOMAINS:
            if d in name:
                return MappingEntry(r, f"pages/{d}/spa/{path.name}", "spa content", d)
        return MappingEntry(r, f"pages/misc/spa/{path.name}", "spa content", None)
    return None


def compute_mapping(files: List[Path]) -> Dict[str, MappingEntry]:
    usage_index = build_usage_index(files)
    mapping: Dict[str, MappingEntry] = {}
    for f in files:
        m = target_path_for(f, usage_index)
        if m:
            if m.old != m.new:  # ignore unchanged
                mapping[m.old] = m
    return mapping


def ensure_backup_dir(ts: str) -> Path:
    d = BACKUP_ROOT / ts
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_file(src: Path, backup_root: Path):
    rel_path = rel(src)
    dest = backup_root / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def rewrite_content(path: Path, content: str, mapping: Dict[str, MappingEntry]) -> str:
    # Remove self-includes
    def replace_include(match: re.Match) -> str:
        directive, target = match.group(1), match.group(2)
        if target in mapping:
            target = mapping[target].new
        # remove if self-include after mapping
        if target == rel(path):
            return f"{{# removed self-include of {target} #}}"
        return f"{{% {directive} '{target}' %}}"

    new = INCLUDE_EXTENDS_RE.sub(replace_include, content)
    # Add slug header if missing
    if 'slug:' not in new.split('\n', 3)[0].lower():
        slug = rel(path).replace('.html', '')
        header = f"{{# slug: {slug} (auto-migrated) #}}\n"
        new = header + new
    return new


def apply_mapping(mapping: Dict[str, MappingEntry], apply: bool, force: bool = False) -> Dict[str, str]:
    changed: Dict[str, str] = {}
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_root = ensure_backup_dir(ts) if apply else None

    # First move files
    for old_rel, entry in mapping.items():
        src = TEMPLATE_ROOT / old_rel
        dst = TEMPLATE_ROOT / entry.new
        if not src.exists():
            continue
        if dst.exists() and not force:
            # Already moved earlier
            continue
        if apply and backup_root:
            backup_file(src, backup_root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            changed[old_rel] = entry.new
        else:
            changed[old_rel] = entry.new

    # Then update references across all files (including newly copied ones)
    all_files = discover_html_files(TEMPLATE_ROOT)
    for f in all_files:
        original = f.read_text(encoding='utf-8', errors='ignore')
        updated = rewrite_content(f, original, mapping)
        # Replace old rel references inside content -> new rel
        for old_rel, entry in mapping.items():
            updated = updated.replace(f"'{old_rel}'", f"'{entry.new}'")
            updated = updated.replace(f'"{old_rel}"', f'"{entry.new}"')
        if updated != original:
            if apply and backup_root:
                backup_file(f, backup_root)
                f.write_text(updated, encoding='utf-8')
            else:
                changed.setdefault(rel(f), rel(f))
    # Optionally delete old files after copy
    if apply:
        for old_rel in mapping.keys():
            old_path = TEMPLATE_ROOT / old_rel
            # Only delete if different and copy succeeded
            if old_path.exists():
                try:
                    old_path.unlink()
                except OSError:
                    pass
    # Write report
    report = {
        'timestamp': ts,
        'applied': apply,
        'changed_files': changed,
        'mapping': {k: entry.__dict__ for k, entry in mapping.items()},
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return changed


def rollback(ts: str):
    backup_dir = BACKUP_ROOT / ts
    if not backup_dir.exists():
        print(f"Backup timestamp {ts} not found.")
        return 1
    for backup_file_path in backup_dir.rglob('*'):
        if backup_file_path.is_file():
            rel_path = backup_file_path.relative_to(backup_dir)
            target = TEMPLATE_ROOT / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file_path, target)
    print(f"Rollback complete from backup {ts}")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restructure Jinja templates")
    parser.add_argument('--apply', action='store_true', help='Apply changes (otherwise dry-run)')
    parser.add_argument('--force', action='store_true', help='Overwrite already moved targets')
    parser.add_argument('--rollback', metavar='TS', help='Rollback to backup timestamp')
    parser.add_argument('--prune-empty', action='store_true', help='After operations, delete now-empty legacy directories')
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.rollback:
        return rollback(args.rollback)

    if not TEMPLATE_ROOT.exists():
        print(f"Template root not found: {TEMPLATE_ROOT}")
        return 2

    files = discover_html_files(TEMPLATE_ROOT)
    mapping = compute_mapping(files)
    if not mapping:
        print("No files need restructuring (mapping empty).")
        return 0
    changed = apply_mapping(mapping, apply=args.apply, force=args.force)
    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f"[{mode}] Proposed/Performed changes: {len(changed)} files")
    for old, new in sorted(changed.items()):
        if old == new:
            print(f"  updated refs: {old}")
        else:
            print(f"  {old} -> {new}")
    print(f"Report written to {REPORT_FILE}")
    if not args.apply:
        print("Re-run with --apply to perform these moves. Backups will be created automatically.")
    # Optional prune
    if args.apply and args.prune_empty:
        removed: list[str] = []
        # Walk bottom-up deleting empty dirs limited to legacy roots
        legacy_roots = [TEMPLATE_ROOT / p for p in ['components','fragments','partials','views']]
        for root in legacy_roots:
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root, topdown=False):
                if not dirnames and not filenames:
                    try:
                        Path(dirpath).rmdir()
                        removed.append(str(Path(dirpath).relative_to(TEMPLATE_ROOT)))
                    except OSError:
                        pass
            # Remove root if now empty
            try:
                root.rmdir()
                removed.append(str(root.relative_to(TEMPLATE_ROOT)))
            except OSError:
                pass
        if removed:
            print("Pruned empty directories:")
            for d in removed:
                print(f"  {d}")
        else:
            print("No empty legacy directories to prune.")
    return 0

if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
