# Application Versioning System

## Overview

The ThesisAppRework platform implements a comprehensive versioning system for generated applications. This allows tracking multiple iterations of the same application, enabling experimentation, comparison, and iterative improvement.

## Core Concepts

### Version Lineage
Each application version maintains a parent-child relationship:
- **v1**: Initial generation (parent_app_id = NULL)
- **v2**: First regeneration (parent_app_id = ID of v1)
- **v3**: Second regeneration (parent_app_id = ID of v2)
- And so on...

### Unique Identification
Applications are uniquely identified by the combination:
```
(model_slug, app_number, version)
```

This allows multiple versions of the same logical application:
- `openai_gpt-4` / app 1 / v1
- `openai_gpt-4` / app 1 / v2
- `openai_gpt-4` / app 1 / v3

### Batch Tracking
Each generation operation receives a `batch_id` for grouping:
- **Single generation**: `single_YYYYMMDD_HHMMSS_{uuid8}`
- **Batch generation**: `batch_YYYYMMDD_HHMMSS_{uuid8}`
- **Regeneration**: `regen_YYYYMMDD_HHMMSS_{uuid8}`

## Database Schema

### GeneratedApplication Fields

| Field | Type | Description |
|-------|------|-------------|
| `app_number` | INTEGER | Logical application number (1, 2, 3, ...) |
| `version` | INTEGER | Version number for this app (1, 2, 3, ...) |
| `parent_app_id` | INTEGER (FK) | Points to previous version's ID |
| `batch_id` | VARCHAR(100) | Groups related generations |
| `template_slug` | VARCHAR(100) | Template used for generation |

### Unique Constraint
```sql
UNIQUE (model_slug, app_number, version)
```

Prevents duplicate versions and ensures data integrity.

### Indexes
```sql
INDEX idx_model_template (model_slug, template_slug)
INDEX idx_batch_id (batch_id)
INDEX idx_parent_app (parent_app_id)
```

## Using the Versioning System

### 1. UI Workflow (Web Interface)

#### Viewing Version Information
Navigate to any model detail page:
- **App # column**: Shows application number with version count badge if multiple versions exist
- **Version column**: Displays current version (e.g., "v2") with regeneration indicator
- **Template column**: Shows which template was used for generation

#### Regenerating an Application
1. Locate the application in the model's application roster
2. Click the regenerate button (🔄 icon)
3. Confirm the regeneration prompt
4. System creates new version automatically (v2, v3, etc.)
5. New version appears in the list after generation completes

### 2. API Workflow (Programmatic)

#### Regenerate Endpoint
```http
POST /api/models/{model_slug}/apps/{app_number}/regenerate
Content-Type: application/json
```

**Request Body** (optional):
```json
{
  "template_slug": "minimal",
  "app_type": "web_app"
}
```

**Response**:
```json
{
  "id": 42,
  "model_slug": "openai_gpt-4",
  "app_number": 1,
  "version": 2,
  "parent_app_id": 15,
  "batch_id": "regen_20250115_143052_a1b2c3d4",
  "template_slug": "minimal",
  "generation_status": "pending",
  "created_at": "2025-01-15T14:30:52.123456"
}
```

#### Batch Generation with Auto-Allocation
```http
POST /api/generate/batch
Content-Type: application/json
```

**Request Body**:
```json
{
  "model_slugs": ["openai_gpt-4", "anthropic_claude-3.7-sonnet"],
  "count_per_model": 3,
  "template_slug": "compact"
}
```

System automatically:
- Allocates app numbers (app1, app2, app3 for each model)
- Generates shared `batch_id` for all apps
- Prevents race conditions via atomic reservation

### 3. CLI Workflow (Direct Service)

#### Using Generation Service
```python
from app.services.generation import GenerationService
from app import create_app

app = create_app()
with app.app_context():
    service = GenerationService()
    
    # Generate new app (auto-allocated app number)
    result = service.generate_application(
        model_slug="openai_gpt-4",
        app_num=None,  # Auto-allocate next available
        template_slug="compact"
    )
    print(f"Created: app{result.app_number} v{result.version}")
    
    # Regenerate existing app
    regen_result = service.regenerate_application(
        model_slug="openai_gpt-4",
        app_number=1
    )
    print(f"Regenerated: app{regen_result.app_number} v{regen_result.version}")
```

## Version Query Patterns

### Finding All Versions of an App
```python
from app.models import GeneratedApplication

versions = GeneratedApplication.query.filter_by(
    model_slug="openai_gpt-4",
    app_number=1
).order_by(GeneratedApplication.version).all()

for v in versions:
    print(f"v{v.version}: created {v.created_at}, status: {v.generation_status}")
```

### Finding Latest Version
```python
latest = GeneratedApplication.query.filter_by(
    model_slug="openai_gpt-4",
    app_number=1
).order_by(GeneratedApplication.version.desc()).first()

print(f"Latest: v{latest.version}")
```

### Tracing Version Lineage
```python
def trace_lineage(app):
    """Recursively trace parent versions."""
    lineage = [app]
    current = app
    while current.parent_app_id:
        parent = GeneratedApplication.query.get(current.parent_app_id)
        if parent:
            lineage.append(parent)
            current = parent
        else:
            break
    return lineage[::-1]  # Return oldest to newest

# Usage
app_v3 = GeneratedApplication.query.get(42)
history = trace_lineage(app_v3)
for app in history:
    print(f"v{app.version} (ID {app.id})")
# Output:
# v1 (ID 10)
# v2 (ID 25)
# v3 (ID 42)
```

### Counting Versions Per App
```python
from sqlalchemy import func

version_counts = db.session.query(
    GeneratedApplication.app_number,
    func.count(GeneratedApplication.id).label('count')
).filter_by(
    model_slug="openai_gpt-4"
).group_by(
    GeneratedApplication.app_number
).all()

for app_num, count in version_counts:
    print(f"app{app_num}: {count} version(s)")
```

## Filesystem Organization

### Template-Based Structure
When using templates, apps are organized as:
```
generated/apps/{model_slug}/{template_slug}/app{N}/
```

Example:
```
generated/apps/openai_gpt-4/compact/app1/  # v1
generated/apps/openai_gpt-4/compact/app1/  # v2 (overwrites)
generated/apps/openai_gpt-4/minimal/app1/  # Different template
```

**Note**: Multiple versions of the same app overwrite the filesystem directory. Use version metadata in the database to track history.

### Flat Structure (Legacy)
Without templates:
```
generated/apps/{model_slug}/app{N}/
```

## Best Practices

### 1. Use Regeneration for Iterative Improvement
- Start with v1 baseline
- Regenerate to test different configurations
- Compare versions via analysis results

### 2. Leverage Batch IDs for Grouping
```python
# Find all apps in a batch operation
batch_apps = GeneratedApplication.query.filter_by(
    batch_id="batch_20250115_140000_xyz123"
).all()

print(f"Batch contained {len(batch_apps)} apps")
```

### 3. Clean Up Old Versions Selectively
```python
# Keep latest 3 versions per app, delete older
from sqlalchemy import func

apps_to_prune = db.session.query(
    GeneratedApplication
).filter(
    GeneratedApplication.version < (
        db.session.query(func.max(GeneratedApplication.version) - 2)
        .filter_by(
            model_slug=GeneratedApplication.model_slug,
            app_number=GeneratedApplication.app_number
        )
        .correlate(GeneratedApplication)
        .scalar_subquery()
    )
).all()

# Delete carefully after backing up
```

### 4. Document Template Changes
When regenerating with different templates:
```python
result = service.regenerate_application(
    model_slug="openai_gpt-4",
    app_number=1,
    template_slug="minimal"  # Switching from 'compact' to 'minimal'
)
# template_slug is stored in DB for tracking
```

## Migration from Legacy Data

### Handling Pre-Versioning Apps
Apps created before versioning system:
- Automatically assigned `version=1` via migration
- `parent_app_id=NULL` (root version)
- No `batch_id` (can be backfilled if needed)

### Unique Constraint Migration
Old constraint:
```sql
UNIQUE (model_slug, app_number)
```

New constraint:
```sql
UNIQUE (model_slug, app_number, version)
```

Migration handled by `scripts/migrate_add_versioning.py`:
1. Detects old constraint
2. Rebuilds table with new schema
3. Preserves all existing data
4. Sets default values for new fields

## Troubleshooting

### Issue: "UNIQUE constraint failed"
**Cause**: Trying to create duplicate (model_slug, app_number, version)

**Solution**: System should auto-increment version. Check code path:
```python
# Correct (auto-increments version)
service.regenerate_application(model_slug, app_number)

# Incorrect (manual version may conflict)
new_app = GeneratedApplication(
    model_slug="...",
    app_number=1,
    version=2  # May conflict if v2 exists
)
```

### Issue: Apps Overwriting Each Other
**Cause**: Race condition in concurrent batch generation

**Solution**: System uses atomic reservation via `_reserve_app_number()`:
1. Creates DB record immediately with PENDING status
2. Database enforces uniqueness constraint
3. Generation proceeds only after reservation succeeds

### Issue: Missing Version Count in UI
**Cause**: Template context not including `app_version_counts`

**Solution**: Ensure `build_model_detail_context()` includes:
```python
app_version_counts = {}
version_count_query = db.session.query(
    GeneratedApplication.app_number,
    func.count(GeneratedApplication.id).label('version_count')
).filter_by(
    model_slug=model.canonical_slug
).group_by(
    GeneratedApplication.app_number
).all()

for app_num, count in version_count_query:
    app_version_counts[app_num] = count

return {
    ...
    'app_version_counts': app_version_counts,
    ...
}
```

## Related Documentation

- [Generation Workflow](./ANALYSIS_WORKFLOW.md) - Overall generation and analysis process
- [API Authentication](./API_AUTH_AND_METHODS.md) - API token usage for automation
- [Maintenance Service](./implementation/MAINTENANCE_SERVICE_IMPLEMENTATION.md) - Cleanup and recovery
- [Database Migrations](../migrations/) - Schema evolution scripts

## Future Enhancements

### Planned Features
- [ ] Version comparison UI (side-by-side diff)
- [ ] Automated version tagging (stable, experimental, etc.)
- [ ] Version rollback functionality
- [ ] Bulk regeneration across models
- [ ] Version-specific analysis results archival
- [ ] Export/import of version lineage

### API Extensions
- [ ] `GET /api/models/{slug}/apps/{num}/versions` - List all versions
- [ ] `GET /api/models/{slug}/apps/{num}/versions/{version}` - Get specific version
- [ ] `DELETE /api/models/{slug}/apps/{num}/versions/{version}` - Delete version
- [ ] `POST /api/models/{slug}/apps/{num}/versions/{version}/restore` - Restore old version

---

**Last Updated**: January 2025  
**Maintained By**: ThesisAppRework Development Team
