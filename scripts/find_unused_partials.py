"""
Analyze Jinja template partials usage and remove empty partial files.

Features:
- Scans src/templates for Jinja usage: include/import/from/extends
- Builds a mapping of partial -> list of files that reference it (direct parents)
- Computes reachability from all non-partial templates to identify unused partials
- Deletes whitespace-only/empty partial files (dry-run by default)

Usage examples:
  python scripts/find_unused_partials.py --dry-run
  python scripts/find_unused_partials.py --apply
  python scripts/find_unused_partials.py --output json > partials_report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Regex patterns to detect Jinja template references
RE_JINJA_COMMENT = re.compile(r"{#.*?#}", re.DOTALL)
RE_INCLUDE = re.compile(r"{%\s*include\s+['\"]([^'\"]+)['\"]")
RE_IMPORT = re.compile(r"{%\s*import\s+['\"]([^'\"]+)['\"]")
RE_FROM_IMPORT = re.compile(r"{%\s*from\s+['\"]([^'\"]+)['\"]\s+import\s+")
RE_EXTENDS = re.compile(r"{%\s*extends\s+['\"]([^'\"]+)['\"]")


def to_posix_relative(path: Path, root: Path) -> str:
    """Return a POSIX-style path relative to root."""
    return path.relative_to(root).as_posix()


def normalize_ref(ref: str) -> str:
    """Normalize template reference to POSIX style, strip leading './' or '/'"""
    ref = ref.strip()
    ref = ref.replace("\\", "/")
    while ref.startswith("./"):
        ref = ref[2:]
    if ref.startswith("/"):
        ref = ref[1:]
    return ref


def strip_jinja_comments(text: str) -> str:
    return RE_JINJA_COMMENT.sub("", text)


def find_references_in_text(text: str) -> Set[str]:
    text = strip_jinja_comments(text)
    refs = set()
    for rx in (RE_INCLUDE, RE_IMPORT, RE_FROM_IMPORT, RE_EXTENDS):
        refs.update(normalize_ref(m) for m in rx.findall(text))
    return refs


def resolve_reference_path(ref: str, templates_root: Path) -> Path | None:
    """Resolve a Jinja ref string to an actual file path under templates_root, if it exists.

    Strategy:
    - Try the ref as-is relative to templates_root
    - If no suffix, try with common suffixes (".html", ".jinja", ".j2")
    - If not found, return None (unresolved)
    """
    candidate = templates_root / ref
    if candidate.exists():
        return candidate
    base = Path(ref)
    if base.suffix == "":
        for suf in (".html", ".jinja", ".j2", ".jinja2"):
            c2 = templates_root / (ref + suf)
            if c2.exists():
                return c2
    return None


@dataclass
class AnalysisResult:
    templates_root: str
    partials_dir: str
    total_templates: int
    total_partials: int
    empty_partials: List[str] = field(default_factory=list)
    unused_partials: List[str] = field(default_factory=list)
    partial_usage: Dict[str, List[str]] = field(default_factory=dict)  # direct parents
    unresolved_references: Dict[str, List[str]] = field(default_factory=dict)  # file -> list of unresolved refs


def analyze_templates(templates_root: Path, partials_subdir: str = "partials") -> AnalysisResult:
    # Collect all template files
    exts = {".html", ".jinja", ".j2", ".jinja2"}
    all_files: List[Path] = [p for p in templates_root.rglob("*") if p.is_file() and p.suffix in exts]
    total_templates = len(all_files)

    # Identify partials
    partials_root = templates_root / partials_subdir
    partials_set: Set[Path] = set()
    if partials_root.exists():
        partials_set = {p for p in all_files if partials_root in p.parents or p == partials_root}
    total_partials = len(partials_set)

    # Graph: file -> referenced files
    adjacency: Dict[Path, Set[Path]] = {p: set() for p in all_files}
    reverse_usage: Dict[Path, Set[Path]] = {p: set() for p in all_files}
    unresolved_by_file: Dict[Path, Set[str]] = {}

    for f in all_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            # Skip files that cannot be read
            continue
        refs = find_references_in_text(text)
        for ref in refs:
            resolved = resolve_reference_path(ref, templates_root)
            if resolved and resolved in adjacency:
                adjacency[f].add(resolved)
                reverse_usage[resolved].add(f)
            else:
                unresolved_by_file.setdefault(f, set()).add(ref)

    # Reachability from non-partials
    entrypoints = [p for p in all_files if p not in partials_set]
    visited: Set[Path] = set()
    stack: List[Path] = entrypoints[:]
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        stack.extend(adjacency.get(cur, ()))

    used_partials = {p for p in partials_set if p in visited}
    unused_partials = sorted((to_posix_relative(p, templates_root) for p in (partials_set - used_partials)))

    # Empty partials: zero or whitespace-only
    empty_partials: List[str] = []
    for p in partials_set:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if content.strip() == "":
            empty_partials.append(to_posix_relative(p, templates_root))

    # Partial usage map (direct parents only)
    partial_usage: Dict[str, List[str]] = {}
    for part in partials_set:
        parents = [to_posix_relative(pp, templates_root) for pp in sorted(reverse_usage.get(part, set()))]
        partial_usage[to_posix_relative(part, templates_root)] = parents

    unresolved_references: Dict[str, List[str]] = {
        to_posix_relative(f, templates_root): sorted(refs)
        for f, refs in unresolved_by_file.items()
        if refs
    }

    return AnalysisResult(
        templates_root=str(templates_root),
        partials_dir=str(partials_root),
        total_templates=total_templates,
        total_partials=total_partials,
        empty_partials=sorted(empty_partials),
        unused_partials=unused_partials,
        partial_usage=dict(sorted(partial_usage.items())),
        unresolved_references=dict(sorted(unresolved_references.items())),
    )


def delete_empty_partials(result: AnalysisResult) -> Tuple[int, List[str]]:
    root = Path(result.templates_root)
    deleted: List[str] = []
    for rel in result.empty_partials:
        p = root / rel
        try:
            if p.exists():
                p.unlink()
                deleted.append(rel)
        except Exception as e:
            print(f"Failed to delete {rel}: {e}", file=sys.stderr)
    return len(deleted), deleted


def print_text_report(result: AnalysisResult) -> None:
    print(f"Templates root: {result.templates_root}")
    print(f"Partials dir:   {result.partials_dir}")
    print(f"Total templates: {result.total_templates}")
    print(f"Total partials:   {result.total_partials}")
    print()
    print(f"Empty partials ({len(result.empty_partials)}):")
    for p in result.empty_partials:
        print(f"  - {p}")
    print()
    print(f"Unused partials by reachability ({len(result.unused_partials)}):")
    for p in result.unused_partials:
        print(f"  - {p}")
    print()
    print("Partial usage (direct parents):")
    for part, parents in result.partial_usage.items():
        parents_disp = ", ".join(parents) if parents else "<no direct references>"
        print(f"  {part}: {parents_disp}")
    if result.unresolved_references:
        print()
        print("Unresolved references (not found on disk):")
        for f, refs in result.unresolved_references.items():
            print(f"  {f} -> {', '.join(refs)}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find unused Jinja partials and remove empty ones.")
    parser.add_argument(
        "--templates-root",
        default=str(Path("src") / "templates"),
        help="Root directory of Jinja templates (default: src/templates)",
    )
    parser.add_argument(
        "--partials-subdir",
        default="partials",
        help="Subdirectory under templates root containing partials (default: partials)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not delete anything; just report (default)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply actions: delete empty partial files",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Report output format (default: text)",
    )

    args = parser.parse_args(argv)

    templates_root = Path(args.templates_root).resolve()
    if not templates_root.exists():
        print(f"Templates root not found: {templates_root}", file=sys.stderr)
        return 2

    result = analyze_templates(templates_root, args.partials_subdir)

    if args.output == "json":
        print(json.dumps(result.__dict__, indent=2))
    else:
        print_text_report(result)

    if args.apply and not args.dry_run:
        deleted_count, deleted_files = delete_empty_partials(result)
        if args.output == "text":
            print()
            print(f"Deleted empty partials: {deleted_count}")
            for p in deleted_files:
                print(f"  - {p}")
    else:
        # Explicit dry-run feedback
        if args.output == "text":
            print()
            print("Dry run: no files were deleted. Re-run with --apply to delete empty partials.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
