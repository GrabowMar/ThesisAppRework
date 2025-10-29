# Task Hierarchy Implementation

**Date:** October 23, 2025  
**Status:** ✅ Implemented

## Overview

Implemented a parent-child task hierarchy system where clicking "Launch Analysis" creates one main task with subordinate analyzer service tasks, instead of showing individual analyzer results as separate tasks.

## Problem

Previously, the Analysis Tasks table showed individual analyzer result files (static, dynamic, performance, AI) as separate rows, making it confusing and cluttered. There was no indication these were part of a single unified analysis.

## Solution

Implemented a hierarchical task system where:
- **Main Task**: Represents the overall analysis request (e.g., "Analyze GPT-4 App #5")
- **Subtasks**: Individual analyzer services (static-analyzer, dynamic-analyzer, etc.)
- **UI**: Main tasks display with expandable rows showing subordinate subtasks

## Changes Made

### 1. Database Model Enhancement (`src/app/models/analysis_models.py`)

Added three new fields to `AnalysisTask`:

```python
# Parent-child relationship
parent_task_id = db.Column(db.String(36), db.ForeignKey('analysis_tasks.task_id'), nullable=True)

# Main task flag (for efficient querying)
is_main_task = db.Column(db.Boolean, default=False, index=True, nullable=False)

# Service identifier for subtasks
service_name = db.Column(db.String(50), nullable=True)

# Relationships
subtasks = db.relationship(
    'AnalysisTask',
    backref=db.backref('parent_task', remote_side=[task_id]),
    foreign_keys=[parent_task_id],
    lazy='joined'
)
```

### 2. Migration Script (`src/migrate_add_task_hierarchy.py`)

- Adds `parent_task_id`, `is_main_task`, `service_name` columns
- Clears old tasks (as requested)
- Migration completed successfully ✅

### 3. Task Service Enhancement (`src/app/services/task_service.py`)

Added new method `create_main_task_with_subtasks()`:

```python
def create_main_task_with_subtasks(
    self,
    model_name: str,
    app_number: int,
    analysis_type: str,
    tools_by_service: Dict[str, List[str]],
    metadata: Optional[Dict] = None
) -> AnalysisTask:
    """
    Create a main analysis task with subordinate service subtasks.
    
    Example:
        tools_by_service = {
            'static-analyzer': ['bandit', 'eslint'],
            'dynamic-analyzer': ['zap'],
            'performance-tester': ['locust'],
            'ai-analyzer': ['openrouter']
        }
        
        main_task = service.create_main_task_with_subtasks(
            model_name='openai_gpt-4',
            app_number=5,
            analysis_type='unified',
            tools_by_service=tools_by_service
        )
        
        # Result: 1 main task + 4 subtasks (one per service)
    """
```

Features:
- Creates one main task marked with `is_main_task=True`
- Creates one subtask per analyzer service
- Links subtasks to parent via `parent_task_id`
- Sets `service_name` on each subtask
- Distributes tools configuration to relevant subtasks

Also added `get_main_tasks()` method for efficient querying:

```python
def get_main_tasks(
    self,
    status: Optional[AnalysisStatus] = None,
    limit: int = 50
) -> List[AnalysisTask]:
    """Get main tasks (no parent) with subtasks eagerly loaded."""
```

### 4. Task Execution Updates (`src/app/services/task_execution_service.py`)

Modified `_execute_unified_analysis()` to update subtask statuses:

```python
# Before executing a service
subtask = next((st for st in subtasks if st.service_name == service_name), None)
if subtask:
    subtask.status = AnalysisStatus.RUNNING
    db.session.commit()

# After service completes successfully
if subtask:
    subtask.status = AnalysisStatus.COMPLETED
    db.session.commit()

# On service failure
if subtask:
    subtask.status = AnalysisStatus.FAILED
    db.session.commit()
```

This provides real-time progress tracking as each analyzer service runs.

### 5. Route Updates (`src/app/routes/jinja/analysis.py`)

#### Launch Analysis Endpoint (Security Profile)
```python
# Create main task with subtasks
main_task = task_service.create_main_task_with_subtasks(
    model_name=model_name,
    app_number=app_number,
    analysis_type='security',
    tools_by_service=tools_by_service,
    metadata={...}
)

# Queue the main task (subtasks execute automatically)
task_execution_service.queue_task(main_task.task_id)
```

#### Launch Analysis Endpoint (Custom Mode)
```python
# When multiple services selected
if len(tools_by_service) > 1:
    main_task = task_service.create_main_task_with_subtasks(
        model_name=model_name,
        app_number=app_number,
        analysis_type='unified',
        tools_by_service=tools_by_service,
        metadata={...}
    )
else:
    # Single service - no hierarchy needed
    task = task_service.create_task(...)
```

#### Task List API Endpoint
```python
# Filter to show only main tasks or tasks without parents
active_tasks = AnalysisTask.query.filter(
    AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING]),
    db.or_(
        AnalysisTask.is_main_task == True,
        AnalysisTask.parent_task_id.is_(None)
    )
).order_by(AnalysisTask.created_at.desc()).all()

# Subtasks are eagerly loaded via relationship
```

### 6. Template Updates (`src/templates/pages/analysis/partials/tasks_table.html`)

Enhanced table to display hierarchical structure:

#### Main Task Row
```html
<tr data-type="task" data-status="{{ task.status.value }}">
    <td>
        {% if task.subtasks %}
            <button class="btn btn-sm btn-ghost-secondary" 
                    onclick="toggleSubtasks('{{ task.task_id }}')">
                <i class="fas fa-chevron-right" id="icon-{{ task.task_id }}"></i>
            </button>
        {% endif %}
        {{ task.task_id[:15] }}...
    </td>
    <!-- Model, App, Type, Status columns -->
</tr>
```

#### Subtask Rows
```html
{% for subtask in task.subtasks %}
<tr class="subtask-row" 
    id="subtask-{{ task.task_id }}-{{ loop.index }}"
    data-parent="{{ task.task_id }}"
    style="display: none;">
    <td class="ps-5">
        <i class="fas fa-level-up-alt fa-rotate-90 text-muted me-2"></i>
        <span class="text-muted small">
            {{ subtask.service_name or 'Unknown Service' }}
        </span>
    </td>
    <!-- Status and progress for this specific service -->
</tr>
{% endfor %}
```

#### Toggle JavaScript
```javascript
function toggleSubtasks(taskId) {
    const rows = document.querySelectorAll(`tr.subtask-row[data-parent="${taskId}"]`);
    const icon = document.getElementById(`icon-${taskId}`);
    
    rows.forEach(row => {
        const isHidden = row.style.display === 'none';
        row.style.display = isHidden ? 'table-row' : 'none';
    });
    
    // Toggle chevron direction
    icon.classList.toggle('fa-chevron-right');
    icon.classList.toggle('fa-chevron-down');
}
```

## User Experience

### Before
```
Task Table:
├─ amazon_nova-pro-v1_app2_ai_20251023...        [Completed]
├─ amazon_nova-pro-v1_app2_dynamic_20251023...   [Completed]
├─ amazon_nova-pro-v1_app2_static_20251023...    [Completed]
└─ amazon_nova-pro-v1_app2_performance_20251023...[Completed]
```
❌ **Problem**: 4 separate rows, unclear they're related

### After
```
Task Table:
├─ [▶] amazon_nova-pro-v1_app2_unified_20251023... [Completed]
│   ├─ ↪ ai-analyzer                 [Completed]
│   ├─ ↪ dynamic-analyzer            [Completed]
│   ├─ ↪ static-analyzer             [Completed]
│   └─ ↪ performance-tester          [Completed]
```
✅ **Better**: 1 main task, expandable to show 4 service subtasks

## Workflow

### 1. User Clicks "Launch Analysis"
```
[Button Click] → Launch Analysis Endpoint
```

### 2. System Creates Task Hierarchy
```python
main_task = {
    'task_id': 'abc-123',
    'is_main_task': True,
    'analysis_type': 'unified',
    'status': 'PENDING'
}

subtasks = [
    {'task_id': 'abc-123-1', 'parent_task_id': 'abc-123', 'service_name': 'static-analyzer'},
    {'task_id': 'abc-123-2', 'parent_task_id': 'abc-123', 'service_name': 'dynamic-analyzer'},
    {'task_id': 'abc-123-3', 'parent_task_id': 'abc-123', 'service_name': 'performance-tester'},
    {'task_id': 'abc-123-4', 'parent_task_id': 'abc-123', 'service_name': 'ai-analyzer'},
]
```

### 3. Task Execution
```python
# Main task queued
task_execution_service.queue_task('abc-123')

# Execution begins
for service in ['static-analyzer', 'dynamic-analyzer', ...]:
    # Find subtask for this service
    subtask = get_subtask_by_service(service)
    
    # Mark as running
    subtask.status = RUNNING
    
    # Execute service
    result = execute_service(service)
    
    # Mark as completed/failed
    subtask.status = COMPLETED if result.success else FAILED
```

### 4. UI Display
```
[GET /analysis/api/tasks/list]
  ↓
[Filter: is_main_task=True OR parent_task_id IS NULL]
  ↓
[Load subtasks via relationship]
  ↓
[Render main task row + hidden subtask rows]
  ↓
[User clicks chevron to expand]
  ↓
[JavaScript shows subtask rows]
```

## API Response Structure

```json
{
  "tasks": [
    {
      "task_id": "abc-123",
      "model_name": "openai_gpt-4",
      "app_number": 5,
      "analysis_type": "unified",
      "status": "COMPLETED",
      "is_main_task": true,
      "created_at": "2025-10-23T16:30:00Z",
      "subtasks": [
        {
          "task_id": "abc-123-1",
          "service_name": "static-analyzer",
          "status": "COMPLETED",
          "parent_task_id": "abc-123"
        },
        {
          "task_id": "abc-123-2",
          "service_name": "dynamic-analyzer",
          "status": "COMPLETED",
          "parent_task_id": "abc-123"
        },
        {
          "task_id": "abc-123-3",
          "service_name": "performance-tester",
          "status": "COMPLETED",
          "parent_task_id": "abc-123"
        },
        {
          "task_id": "abc-123-4",
          "service_name": "ai-analyzer",
          "status": "FAILED",
          "parent_task_id": "abc-123"
        }
      ]
    }
  ]
}
```

## Benefits

1. **Cleaner UI**: One row per analysis instead of 4-6 rows
2. **Clear Hierarchy**: Obvious which subtasks belong to which analysis
3. **Better Tracking**: See status of individual services in real-time
4. **Expandable Detail**: Hide/show subtasks as needed
5. **Backward Compatible**: Single-service tasks still work (no subtasks)

## Testing

### Manual Testing Steps

1. **Start the application**:
   ```bash
   cd src
   python main.py
   ```

2. **Navigate to Analysis page**: http://localhost:5000/analysis

3. **Launch a unified analysis**:
   - Select a model (e.g., GPT-4)
   - Select an app number
   - Choose "Custom" mode
   - Select multiple services (e.g., Static, Dynamic, Performance)
   - Click "Launch Analysis"

4. **Verify in table**:
   - Should see **ONE** main task row
   - Row should have a chevron icon (▶)
   - Click chevron to expand
   - Should see subtask rows indented underneath
   - Each subtask shows its service name and individual status

5. **Watch progress**:
   - Main task shows overall status
   - Individual subtasks update as services complete
   - Failed subtasks clearly marked

### Database Verification

```sql
-- Check main tasks
SELECT task_id, is_main_task, parent_task_id, service_name 
FROM analysis_tasks 
WHERE is_main_task = 1;

-- Check subtasks for a main task
SELECT task_id, service_name, status, parent_task_id
FROM analysis_tasks
WHERE parent_task_id = 'abc-123';

-- Verify hierarchy
SELECT 
    parent.task_id as main_task,
    parent.status as main_status,
    child.task_id as subtask,
    child.service_name,
    child.status as subtask_status
FROM analysis_tasks parent
LEFT JOIN analysis_tasks child ON child.parent_task_id = parent.task_id
WHERE parent.is_main_task = 1;
```

## Files Modified

1. ✅ `src/app/models/analysis_models.py` - Added hierarchy columns
2. ✅ `src/migrate_add_task_hierarchy.py` - Migration script
3. ✅ `src/app/services/task_service.py` - Task creation methods
4. ✅ `src/app/services/task_execution_service.py` - Subtask status updates
5. ✅ `src/app/routes/jinja/analysis.py` - Launch & list endpoints
6. ✅ `src/templates/pages/analysis/partials/tasks_table.html` - UI rendering

## Migration Status

✅ **Migration completed successfully**
- Added `parent_task_id` column
- Added `is_main_task` column (indexed)
- Added `service_name` column
- Cleared 3 old tasks
- Database ready for new hierarchy system

## Next Steps

1. **Test with live analysis** - Launch actual analyses and verify hierarchy
2. **WebSocket updates** - Ensure real-time progress updates work for subtasks
3. **Result aggregation** - Verify results page handles hierarchical tasks
4. **Filtering** - Test filters work correctly with main tasks only
5. **Performance** - Monitor query performance with eager-loaded subtasks

## Notes

- Single-service tasks (non-unified) still work without subtasks
- Old result files remain unchanged (backward compatible)
- Subtasks use same execution engine, just tracked separately
- UI automatically hides expand button for tasks without subtasks
- Chevron icon rotates (▶ → ▼) when expanded

## Rollback Plan

If issues arise:

```python
# Revert to showing all tasks
active_tasks = AnalysisTask.query.filter(
    AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])
).order_by(AnalysisTask.created_at.desc()).all()

# Remove hierarchy rendering from template
# Use old task creation method
```

Database columns are nullable, so can be ignored without breaking existing code.
