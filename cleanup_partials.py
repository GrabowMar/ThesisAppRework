
import os
import re
from pathlib import Path

def find_unused_partials():
    """
    Finds and removes unused partial templates.
    """
    project_root = Path(__file__).parent
    partials_dir = project_root / "src" / "templates" / "partials"
    source_dir = project_root / "src"

    if not partials_dir.is_dir() or not source_dir.is_dir():
        print("Error: Partials or source directory not found.")
        return

    all_partials = {f.name for f in partials_dir.glob("*.html")}
    used_partials = set()

    print(f"Found {len(all_partials)} partials to check.")

    # Regex to find partial usages, e.g., "partials/file.html"
    # This handles quotes and ensures we match the full path segment.
    partial_usage_pattern = re.compile(r"['\"](partials/[a-zA-Z0-9_.-]+\.html)['\"]")

    for filepath in source_dir.rglob("*"):
        if filepath.suffix in (".py", ".html"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    found = partial_usage_pattern.findall(content)
                    for partial_path in found:
                        partial_name = Path(partial_path).name
                        if partial_name in all_partials:
                            used_partials.add(partial_name)
            except Exception as e:
                print(f"Could not read file {filepath}: {e}")

    unused_partials = all_partials - used_partials

    print("\n--- Analysis Complete ---")
    print(f"Total Partials: {len(all_partials)}")
    print(f"Used Partials: {len(used_partials)}")
    print(f"Unused Partials: {len(unused_partials)}")

    if not unused_partials:
        print("\nNo unused partials found. Great job!")
        return

    print("\nUnused partials:")
    for partial in sorted(list(unused_partials)):
        print(f"- {partial}")

    # Asynchronously delete files without asking for user input
    print("\nRemoving unused partials...")
    deleted_count = 0
    for partial_name in unused_partials:
        try:
            file_to_delete = partials_dir / partial_name
            file_to_delete.unlink()
            print(f"Deleted: {partial_name}")
            deleted_count += 1
        except OSError as e:
            print(f"Error deleting {partial_name}: {e}")

    print(f"\nSuccessfully deleted {deleted_count} unused partials.")

if __name__ == "__main__":
    find_unused_partials()
