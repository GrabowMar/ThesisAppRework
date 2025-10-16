# Documentation Restructuring Script

"""
This script organizes the ThesisApp documentation by moving historical/redundant
files to the archive folder while preserving current, consolidated documentation.

Run this script to complete the documentation restructuring:
    python scripts/reorganize_docs.py
"""

import shutil
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
ARCHIVE = DOCS / "archive"

# Files to archive (historical, redundant, or superseded)
FILES_TO_ARCHIVE = [
    # Cleanup documentation (consolidated in CHANGELOG)
    "CLEANUP_COMPLETE.md",
    "CLEANUP_QUICK_REF.md",
    "CLEANUP_SUMMARY.md",
    "DATABASE_CLEANUP_GUIDE.md",
    
    # Application detail redesign (consolidated in features/)
    "APPLICATION_DETAIL_REDESIGN.md",
    "APPLICATION_DETAIL_SUMMARY.md",
    "APPLICATION_DETAIL_TESTING.md",
    
    # Template enhancements (consolidated in CHANGELOG and features/GENERATION)
    "APP_TEMPLATE_ENHANCEMENT_GUIDE.md",
    "COMPLETE_GENERATION_SYSTEM_SUMMARY.md",
    "FINAL_GENERATOR_IMPROVEMENTS.md",
    "FRONTEND_ENHANCEMENT_COMPLETE.md",
    "FRONTEND_VERIFICATION.md",
    "GENERATOR_CHANGES_QUICK_REF.md",
    "QUICK_REFERENCE.md",
    "SAMPLE_GENERATOR_IMPROVEMENTS.md",
    "SAMPLE_GENERATOR_REWORK.md",
    "TEMPLATE_ENHANCEMENT_RESULTS.md",
    "TEMPLATE_ENHANCEMENTS_COMPLETE.md",
    "TEMPLATE_ENHANCEMENTS_QUICK_REFERENCE.md",
    "TEMPLATE_GUARDRAILS.md",
    "TEMPLATE_GUARDRAILS_SUMMARY.md",
    "TEMPLATE_ROBUSTNESS_IMPROVEMENTS.md",
    "TEMPLATE_STRUCTURE_REFACTOR.md",
    
    # Multi-tier system (consolidated in features/GENERATION)
    "MULTI_TIER_TEMPLATES_QUICK_REF.md",
    "MULTI_TIER_TEMPLATE_SYSTEM.md",
    "MULTI_TIER_VISUAL_GUIDE.md",
    "WEAK_MODEL_SUPPORT_SUMMARY.md",
    
    # Port allocation (consolidated in features/PORT_ALLOCATION)
    "PORT_ALLOCATION_AUTOMATIC.md",
    "PORT_ALLOCATION_CHANGES.md",
    "PORT_ALLOCATION_REFACTORING.md",
    
    # Bug fixes and changes (consolidated in CHANGELOG)
    "CODE_CHANGES_SUMMARY.md",
    "DUPLICATE_APPS_FIX.md",
    "GENERATION_FIXES.md",
    "SLUG_NORMALIZATION_FIX.md",
    "STATISTICS_IMPROVEMENTS.md",
    "TABLE_STANDARDIZATION.md",
    
    # Other superseded docs
    "JS_TRIMMING.md",
    "RAW_OUTPUTS.md",
]

# Files to keep in root (will be updated/replaced)
FILES_TO_KEEP = [
    "README.md",  # Will be replaced with README_NEW.md
    "ARCHITECTURE.md",  # Will be enhanced
    "GETTING_STARTED.md",  # New file
    "CHANGELOG.md",  # New file
]

# Files to move to reference/
FILES_TO_REFERENCE = [
    "API_REFERENCE.md",
    "PROJECT_STRUCTURE.md",
]

# Files to move to features/
FILES_TO_FEATURES = [
    "ANALYSIS_PIPELINE.md",  # Rename to ANALYSIS.md
    "ANALYSIS_TOOLS.md",  # Merge into ANALYSIS.md
    "APPLICATION_STATUS_SYSTEM.md",  # Rename to CONTAINERS.md
    "PORT_ALLOCATION.md",  # Already correct
    "GENERATION_INTERFACE_GUIDE.md",  # Merge into GENERATION.md
]

# Files to move to guides/
FILES_TO_GUIDES = [
    "DEVELOPMENT_GUIDE.md",
    "USER_GUIDE.md",
    "SAMPLE_GENERATOR_QUICK_START.md",
]


def archive_files():
    """Move historical files to archive/"""
    print("📦 Archiving historical documentation...")
    moved = 0
    
    for filename in FILES_TO_ARCHIVE:
        src = DOCS / filename
        if src.exists():
            dst = ARCHIVE / filename
            shutil.move(str(src), str(dst))
            print(f"  ✓ Archived: {filename}")
            moved += 1
        else:
            print(f"  ⚠ Not found: {filename}")
    
    print(f"\n✓ Archived {moved} files\n")


def organize_structure():
    """Move files to appropriate folders"""
    print("📁 Organizing documentation structure...")
    
    # Move to reference/
    print("\n📖 Moving to reference/...")
    for filename in FILES_TO_REFERENCE:
        src = DOCS / filename
        if src.exists():
            dst = DOCS / "reference" / filename
            shutil.move(str(src), str(dst))
            print(f"  ✓ Moved: {filename} → reference/")
    
    # Move to guides/
    print("\n📚 Moving to guides/...")
    for filename in FILES_TO_GUIDES:
        src = DOCS / filename
        if src.exists():
            dst = DOCS / "guides" / filename
            shutil.move(str(src), str(dst))
            print(f"  ✓ Moved: {filename} → guides/")
    
    print("\n✓ Structure organized\n")


def update_readme():
    """Replace old README with new comprehensive version"""
    print("📄 Updating main README...")
    
    old_readme = DOCS / "README.md"
    new_readme = DOCS / "README_NEW.md"
    backup = DOCS / "archive" / "README_OLD.md"
    
    if old_readme.exists():
        shutil.move(str(old_readme), str(backup))
        print("  ✓ Backed up: README.md → archive/README_OLD.md")
    
    if new_readme.exists():
        shutil.move(str(new_readme), str(old_readme))
        print("  ✓ Activated: README_NEW.md → README.md")
    
    print("\n✓ README updated\n")


def create_index():
    """Create index file in archive/"""
    print("📑 Creating archive index...")
    
    index_content = """# Documentation Archive

This folder contains historical documentation that has been superseded by the new organized structure.

## Why These Files Were Archived

- **Redundant**: Information consolidated into fewer, more comprehensive documents
- **Historical**: Documents specific changes/improvements now captured in CHANGELOG.md
- **Superseded**: Replaced by better-organized feature/guide documentation

## What to Use Instead

| Old Document | New Location |
|--------------|--------------|
| Multiple cleanup docs | [CHANGELOG.md](../CHANGELOG.md) |
| Template enhancement docs | [features/GENERATION.md](../features/GENERATION.md) |
| Port allocation docs | [features/PORT_ALLOCATION.md](../features/PORT_ALLOCATION.md) |
| Multi-tier system docs | [features/GENERATION.md](../features/GENERATION.md) |
| Analysis pipeline docs | [features/ANALYSIS.md](../features/ANALYSIS.md) |
| Application status docs | [features/CONTAINERS.md](../features/CONTAINERS.md) |

## Archive Contents

These files are preserved for historical reference but are no longer actively maintained.

### Cleanup & Database
- CLEANUP_COMPLETE.md
- CLEANUP_QUICK_REF.md
- CLEANUP_SUMMARY.md
- DATABASE_CLEANUP_GUIDE.md

### UI Redesigns
- APPLICATION_DETAIL_REDESIGN.md
- APPLICATION_DETAIL_SUMMARY.md
- APPLICATION_DETAIL_TESTING.md
- FRONTEND_ENHANCEMENT_COMPLETE.md
- FRONTEND_VERIFICATION.md
- STATISTICS_IMPROVEMENTS.md
- TABLE_STANDARDIZATION.md

### Template System Evolution
- APP_TEMPLATE_ENHANCEMENT_GUIDE.md
- COMPLETE_GENERATION_SYSTEM_SUMMARY.md
- FINAL_GENERATOR_IMPROVEMENTS.md
- GENERATOR_CHANGES_QUICK_REF.md
- QUICK_REFERENCE.md
- SAMPLE_GENERATOR_IMPROVEMENTS.md
- SAMPLE_GENERATOR_REWORK.md
- TEMPLATE_ENHANCEMENT_RESULTS.md
- TEMPLATE_ENHANCEMENTS_COMPLETE.md
- TEMPLATE_ENHANCEMENTS_QUICK_REFERENCE.md
- TEMPLATE_GUARDRAILS.md
- TEMPLATE_GUARDRAILS_SUMMARY.md
- TEMPLATE_ROBUSTNESS_IMPROVEMENTS.md
- TEMPLATE_STRUCTURE_REFACTOR.md

### Multi-Tier System
- MULTI_TIER_TEMPLATES_QUICK_REF.md
- MULTI_TIER_TEMPLATE_SYSTEM.md
- MULTI_TIER_VISUAL_GUIDE.md
- WEAK_MODEL_SUPPORT_SUMMARY.md

### Port Allocation
- PORT_ALLOCATION_AUTOMATIC.md
- PORT_ALLOCATION_CHANGES.md
- PORT_ALLOCATION_REFACTORING.md

### Bug Fixes & Changes
- CODE_CHANGES_SUMMARY.md
- DUPLICATE_APPS_FIX.md
- GENERATION_FIXES.md
- SLUG_NORMALIZATION_FIX.md

### Miscellaneous
- JS_TRIMMING.md
- RAW_OUTPUTS.md

---

**Note**: If you need information from these documents, check the new organized documentation first. The archived files are kept for historical reference only.

**Last Updated**: October 2025
"""
    
    index_file = ARCHIVE / "README.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print("  ✓ Created: archive/README.md")
    print("\n✓ Archive indexed\n")


def print_summary():
    """Print summary of what was done"""
    print("=" * 60)
    print("📚 Documentation Restructuring Complete!")
    print("=" * 60)
    print("\n✅ New Structure:")
    print("  docs/")
    print("    ├── README.md              (Navigation hub)")
    print("    ├── GETTING_STARTED.md     (Setup guide)")
    print("    ├── ARCHITECTURE.md        (System design)")
    print("    ├── CHANGELOG.md           (All changes)")
    print("    ├── features/              (Feature documentation)")
    print("    │   ├── GENERATION.md")
    print("    │   ├── ANALYSIS.md")
    print("    │   ├── CONTAINERS.md")
    print("    │   └── PORT_ALLOCATION.md")
    print("    ├── guides/                (How-to guides)")
    print("    │   ├── GENERATING_APPS.md")
    print("    │   ├── RUNNING_ANALYSIS.md")
    print("    │   ├── MANAGING_APPS.md")
    print("    │   └── ...")
    print("    ├── reference/             (Technical reference)")
    print("    │   ├── API.md")
    print("    │   ├── DATABASE.md")
    print("    │   └── ...")
    print("    └── archive/               (Historical docs)")
    print("\n📖 Start here: docs/README.md")
    print("\n")


def main():
    """Run complete reorganization"""
    print("\n" + "=" * 60)
    print("🔧 ThesisApp Documentation Restructuring")
    print("=" * 60 + "\n")
    
    # Ensure folders exist
    ARCHIVE.mkdir(exist_ok=True)
    (DOCS / "features").mkdir(exist_ok=True)
    (DOCS / "guides").mkdir(exist_ok=True)
    (DOCS / "reference").mkdir(exist_ok=True)
    
    # Run steps
    archive_files()
    organize_structure()
    update_readme()
    create_index()
    print_summary()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
