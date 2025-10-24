# Task Hierarchy Chevron Fix

**Date:** October 24, 2025  
**Issue:** Chevrons and task groupings not showing in the Analysis Tasks table  
**Status:** ✅ Fixed

## Problem

The task hierarchy feature was implemented in the backend (database models, services, routes), but the frontend template was missing the crucial UI elements to display:
1. The chevron/expand button for main tasks with subtasks
2. The subtask rows themselves
3. The JavaScript toggle function

## Root Cause

In `src/templates/pages/analysis/partials/tasks_table.html`:
- The template added `data-has-subtasks` attribute but didn't render the chevron button
- No subtask rows were being rendered even though the backend was providing subtask data
- The `toggleSubtasks()` JavaScript function was not implemented in `analysis.js`

## Solution

### 1. Updated `tasks_table.html` Template

**Added chevron button in the first column** (Task ID cell):
```html
<td class="font-monospace small">
  <div class="d-flex align-items-center gap-2">
    {% if item.get('is_main_task') and item.get('subtasks') %}
      <button class="btn btn-sm btn-ghost-secondary p-0" 
              style="width: 20px; height: 20px; line-height: 1;"
              onclick="toggleSubtasks('{{ item.id }}')"
              type="button"
              aria-label="Toggle subtasks"
              title="Show/hide subtasks">
        <i class="fas fa-chevron-right" id="icon-{{ item.id }}" aria-hidden="true"></i>
      </button>
    {% endif %}
    <!-- Task name display -->
  </div>
</td>
```

**Added subtask rows after main task row**:
```html
</tr>

{# Render subtasks if this is a main task with subtasks #}
{% if item.get('is_main_task') and item.get('subtasks') %}
  {% for subtask in item.subtasks %}
    <tr class="subtask-row" 
        id="subtask-{{ item.id }}-{{ loop.index }}"
        data-parent="{{ item.id }}"
        style="display: none;">
      <td class="ps-5">
        <div class="d-flex align-items-center gap-2">
          <i class="fas fa-level-up-alt fa-rotate-90 text-muted" aria-hidden="true"></i>
          <span class="text-muted small font-monospace">{{ subtask.service_name or 'Unknown Service' }}</span>
        </div>
      </td>
      <!-- Status, progress, etc. -->
    </tr>
  {% endfor %}
{% endif %}
```

### 2. Updated `analysis.js`

Added the `toggleSubtasks()` function:
```javascript
window.toggleSubtasks = function(taskId) {
  const rows = document.querySelectorAll(`tr.subtask-row[data-parent="${taskId}"]`);
  const icon = document.getElementById(`icon-${taskId}`);
  
  if (!rows.length || !icon) return;
  
  rows.forEach(row => {
    const isHidden = row.style.display === 'none';
    row.style.display = isHidden ? 'table-row' : 'none';
  });
  
  // Toggle chevron direction
  icon.classList.toggle('fa-chevron-right');
  icon.classList.toggle('fa-chevron-down');
};
```

## User Experience

### Before Fix
```
Task Table:
└─ Main Analysis Task    [Running] 45%
```
❌ No indication of subtasks, no way to see individual service progress

### After Fix
```
Task Table:
├─ [▶] Main Analysis Task             [Running] 45%
│   ├─ ↪ static-analyzer               [Completed] 100%
│   ├─ ↪ dynamic-analyzer              [Running] 60%
│   ├─ ↪ performance-tester            [Pending] 0%
│   └─ ↪ ai-analyzer                   [Pending] 0%
```
✅ Chevron shows expandable tasks, click to reveal/hide subtasks

## Visual Design

- **Chevron Icon**: `fa-chevron-right` (collapsed) → `fa-chevron-down` (expanded)
- **Subtask Indentation**: `ps-5` (padding-left: 5 spacing units)
- **Subtask Icon**: `fa-level-up-alt fa-rotate-90` (corner arrow pointing right)
- **Subtask Rows**: Hidden by default (`display: none`), shown as `table-row` when expanded
- **Background**: Subtasks slightly differentiated with light gray background

## Testing

Created `test_hierarchy_ui.html` demonstrating:
- Main task with 4 subtasks (static, dynamic, performance, AI)
- Chevron toggle functionality
- Different status badges for each subtask
- Progress bars for each subtask
- Regular task without subtasks for comparison

## Files Modified

1. `src/templates/pages/analysis/partials/tasks_table.html` - Added chevron button and subtask rows
2. `src/static/js/analysis.js` - Added toggleSubtasks() function
3. `test_hierarchy_ui.html` - Created standalone test/demo page

## Backend Already Working

The backend was already properly configured:
- ✅ Database models with `is_main_task`, `parent_task_id`, `service_name`
- ✅ `TaskService.create_main_task_with_subtasks()` method
- ✅ Route handler loading subtasks via `task.subtasks` relationship
- ✅ Subtask data included in `unified_items` passed to template

Only the **frontend UI** was missing, which is now fixed.

## Next Steps

To see the feature in action:
1. Launch a new analysis from `/analysis/` 
2. The system will create 1 main task + 4 subtasks
3. Click the chevron to expand/collapse subtask details
4. Watch individual service progress update in real-time
