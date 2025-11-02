# Stop All Tasks Feature

## Overview
Added a "Stop All" button to the analysis tasks page that allows users to cancel all pending and running tasks with a single click.

## Implementation Details

### Backend API Endpoint
- **Route**: `POST /analysis/api/tasks/stop-all`
- **Location**: `src/app/routes/jinja/analysis.py`
- **Functionality**: 
  - Queries all tasks with status `PENDING` or `RUNNING`
  - Calls `AnalysisTaskService.cancel_task()` for each active task
  - Returns JSON response with count of cancelled/failed tasks

### Frontend UI
- **Button Location**: Analysis tasks table header (next to Refresh and New Analysis buttons)
- **Visibility**: Only shown when there are active tasks (`pagination.active_count > 0`)
- **Styling**: Red danger button with stop-circle icon
- **Template**: `src/templates/pages/analysis/partials/tasks_table.html`

### JavaScript Handler
- **Function**: `stopAllTasks()`
- **Location**: `src/static/js/analysis.js`
- **Features**:
  - Confirmation dialog before executing
  - Loading state during execution
  - Success/error feedback
  - Auto-refresh tasks table after completion

## Usage

### From Web UI:
1. Navigate to `/analysis`
2. If active tasks exist, click the red "Stop All" button
3. Confirm the action in the dialog
4. All pending and running tasks will be cancelled
5. Tasks table automatically refreshes to show updated status

### Programmatically:
```python
from app.services.task_service import AnalysisTaskService
from app.models import AnalysisTask
from app.constants import AnalysisStatus

# Get all active tasks
active_tasks = AnalysisTask.query.filter(
    AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])
).all()

# Cancel each task
for task in active_tasks:
    AnalysisTaskService.cancel_task(task.task_id)
```

## Testing
Run the test script to verify functionality:
```bash
python scripts/diagnostics/test_stop_all_tasks.py
```

## Notes
- Cancelled tasks are marked with status `CANCELLED`
- The action cannot be undone
- Running tasks may take a moment to fully stop
- Completed tasks cannot be cancelled (safety check in `cancel_task()`)
