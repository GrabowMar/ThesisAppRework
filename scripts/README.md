# Scripts Directory

This directory contains utility, diagnostic, and testing scripts for the ThesisAppRework project.

## Directory Structure

### diagnostics/
Database and system checking scripts for troubleshooting and inspection:
- `check_app_exists.py` - Verify if specific app exists in DB and filesystem
- `check_model.py` - Verify model existence in database by canonical slug
- `check_orphan_tasks.py` - List orphan analysis tasks for specific apps
- `check_users.py` - List users and create default admin if none exist
- `analyze_task_creation.py` - Analyze task creation patterns to debug mass creation
- `find_task_source.py` - Show most recently created tasks with metadata
- `debug_async_db.py` - Test model lookup issues in async/Flask context

### maintenance/
Cleanup and maintenance scripts:
- `cleanup_orphan_apps.py` - Delete DB records without filesystem directories
- `cleanup_orphan_tasks.py` - Delete PENDING tasks for non-existent apps
- `delete_orphan_tasks.py` - Delete all tasks for specific orphan app

### verification/
System verification and validation scripts:
- `verify_cleanup.py` - Post-cleanup verification (orphans, pending/running tasks)
- `verify_generation_system.py` - Comprehensive generation system verification (3 test apps)
- `verify_maintenance_implementation.py` - Verify maintenance service integration

### testing/generation/
Manual generation test scripts (complementing automated tests in `tests/`):
- `generate_fresh_apps.py` - Generate 3 test apps with different models
- `test_compact_templates.py` - Test compact templates with codex-mini
- `test_compact_vs_standard.py` - Compare compact vs standard template performance
- `test_flask_app.py` - Manual fix test for generated backend
- `test_generation_fixes.py` - Test file locks, queue mode, timezone fixes
- `test_maintenance.py` - Test maintenance service functionality
- `test_new_merger.py` - Test simplified CodeMerger with existing responses
- `test_single_gen.py` - Generate single app with detailed output (GPT-4o)
- `test_template_fix.py` - Verify template API_URL fixes
- `test_template_type_option.py` - Test template type selection logic
- `test_three_apps.py` - Generate 3 apps to validate compact templates

### utilities/
One-off utilities and batch operations:
- `update_requirements.py` - Main requirements update script
- `update_requirements_phase1.py` - Phase 1 of requirement updates (6 files)
- `update_requirements_phase2.py` - Phase 2 of requirement updates
- `update_requirements_phase3.py` - Phase 3 of requirement updates

## Usage

All scripts are designed to be run from the project root directory:

```powershell
# Example: Run diagnostic check
python scripts/diagnostics/check_app_exists.py

# Example: Run cleanup
python scripts/maintenance/cleanup_orphan_apps.py

# Example: Verify system
python scripts/verification/verify_generation_system.py
```

## Note on Testing

Scripts in `testing/generation/` are **manual/exploratory tests** used during development and debugging. For **automated testing**, see the main `tests/` directory which contains the comprehensive test suite run via pytest.
