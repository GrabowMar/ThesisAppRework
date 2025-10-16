# Application Status System

## Overview

The ThesisApp platform includes an intelligent application status management system that provides accurate, real-time information about Docker container states while minimizing unnecessary API calls through smart caching.

## Architecture

### Database Schema

```sql
-- Enhanced GeneratedApplication table
CREATE TABLE generated_applications (
    id INTEGER PRIMARY KEY,
    model_slug VARCHAR(200) NOT NULL,
    app_number INTEGER NOT NULL,
    app_type VARCHAR(50) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    generation_status VARCHAR(20),
    has_backend BOOLEAN DEFAULT FALSE,
    has_frontend BOOLEAN DEFAULT FALSE,
    backend_framework VARCHAR(50),
    frontend_framework VARCHAR(50),
    container_status VARCHAR(50) DEFAULT 'stopped',
    last_status_check DATETIME(timezone=TRUE),  -- NEW: Status verification timestamp
    metadata_json TEXT,
    created_at DATETIME(timezone=TRUE) DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME(timezone=TRUE) DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_slug, app_number)
);

CREATE INDEX ix_generated_applications_last_status_check 
ON generated_applications(last_status_check);
```

### Status Types

| Status | Description | Icon | Color |
|--------|-------------|------|-------|
| `running` | Containers are active and accessible | ▶️ | Green |
| `stopped` | Containers exist but are not running | ⏹️ | Gray |
| `not_created` | Compose file exists but no containers | ➕ | Yellow |
| `no_compose` | Missing docker-compose.yml file | ⚠️ | Red |
| `unknown` | Status being determined | ❓ | Muted |

## Service Layer

### Core Service Methods

```python
# app/services/application_service.py

def refresh_all_application_statuses() -> Dict[str, Any]:
    """
    Refresh all application container statuses from Docker and update database.
    
    Returns:
        Dict containing:
        - total_checked: Number of applications checked
        - updated: Number of statuses that changed
        - errors: Number of applications with errors
        - timestamp: When the refresh completed
    """

def update_container_status(self, status: str) -> None:
    """Update container status and timestamp on GeneratedApplication model."""

def is_status_fresh(self, max_age_minutes: int = 5) -> bool:
    """Check if cached status is recent enough to trust without Docker check."""
```

### Status Determination Logic

```python
def determine_docker_status(model_slug: str, app_number: int) -> str:
    """
    Determine actual container status from Docker.
    
    Logic:
    1. Check if containers are running → 'running'
    2. Check if containers exist but stopped → 'stopped' 
    3. Check if compose file exists → 'not_created'
    4. No compose file found → 'no_compose'
    """
    summary = docker_mgr.container_status_summary(model_slug, app_number)
    states = summary.get('states', [])
    
    if any(s.lower() == 'running' for s in states):
        return 'running'
    elif states:  # Has containers but not running
        return 'stopped'
    else:  # No containers
        preflight = docker_mgr.compose_preflight(model_slug, app_number)
        if preflight.get('compose_file_exists'):
            return 'not_created'
        else:
            return 'no_compose'
```

## API Endpoints

### Bulk Status Refresh

```http
POST /api/applications/refresh-all-statuses
Content-Type: application/json

Response:
{
  "success": true,
  "message": "Refreshed status for 15 applications. Updated: 3, Errors: 0",
  "data": {
    "total_checked": 15,
    "updated": 3,
    "errors": 0,
    "timestamp": "2025-09-22T12:30:45Z"
  }
}
```

### Enhanced Individual Status

```http
GET /api/app/{model_slug}/{app_number}/status

Response:
{
  "success": true,
  "message": "Status retrieved",
  "data": {
    "model_slug": "openai_gpt-4",
    "app_number": 1,
    "docker_status": "running",
    "cached_status": "running", 
    "running": true,
    "containers": ["app_frontend", "app_backend"],
    "states": ["running", "running"],
    "last_check": "2025-09-22T12:25:30Z",
    "status_age_minutes": 2.5,
    "status_is_fresh": true,
    "compose_file_exists": true,
    "docker_connected": true
  }
}
```

## Frontend Integration

### Smart Polling Strategy

```javascript
// Optimized polling that minimizes Docker API calls
function pollApplicationStatuses() {
    const rows = Array.from(document.querySelectorAll('#applications-table-body tr[data-model][data-app]'));
    
    // Priority-based checking
    const batch = rows.slice(0, 15).filter(row => {
        const statusText = row.querySelector('td:nth-child(5) .badge').textContent.trim().toLowerCase();
        
        // Always check uncertain statuses
        if (statusText.includes('unknown') || statusText.includes('pending')) {
            return true;
        }
        
        // Check definitive statuses less frequently (every 5th cycle)
        if (!row.dataset.pollCount) row.dataset.pollCount = '0';
        const pollCount = parseInt(row.dataset.pollCount) + 1;
        row.dataset.pollCount = pollCount.toString();
        
        return pollCount % 5 === 0;
    });
    
    // Process batch with error handling
    batch.forEach(row => {
        // Individual status check with UI update
    });
}

// Reduced polling frequency (60 seconds vs 45 seconds)
setInterval(() => {
    if (document.visibilityState === 'visible') {
        pollApplicationStatuses();
    }
}, 60000);
```

### Bulk Refresh UI

```javascript
function refreshAllStatuses() {
    const button = event.target.closest('button');
    const originalHtml = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    showNotification('Refreshing all application statuses from Docker...', 'info');
    
    fetch('/api/applications/refresh-all-statuses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            setTimeout(refreshApplications, 500);
        } else {
            showNotification(`Status refresh failed: ${data.error}`, 'danger');
        }
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = originalHtml;
    });
}
```

## Performance Optimizations

### Caching Strategy

1. **Database First**: UI displays cached status from database
2. **Smart Refresh**: Only check Docker for uncertain or stale statuses
3. **Bulk Operations**: Efficient batch updates instead of individual calls
4. **Age Tracking**: Status freshness prevents unnecessary Docker calls

### Polling Frequency

| Status Type | Check Frequency | Reason |
|-------------|----------------|---------|
| Unknown/Pending | Every poll cycle (60s) | Needs resolution |
| Running/Stopped | Every 5th cycle (5min) | Stable states |
| Error states | Every cycle | May need attention |

### Resource Usage

**Before Optimization:**
- 20 applications × 45-second polling = ~27 Docker API calls/minute
- No caching, direct Docker checks

**After Optimization:**
- Smart filtering: ~5-8 Docker API calls/minute
- Database caching with 5-minute freshness
- Bulk refresh available for manual sync

## Database Schema

The database schema is automatically managed by the application. The `last_status_check` field is created automatically when the application starts.

### Database Structure

The `generated_applications` table includes:
- `last_status_check`: DateTime(timezone=True) field with index
- Automatically created on application startup
- No manual migration required

### Deployment Steps

1. **Deploy Code**: Deploy application with new status management code
2. **Database Schema**: Schema is automatically updated on application startup
3. **Verify**: Test status refresh and individual status endpoints
3. **Initial Sync**: Run bulk refresh to populate status timestamps
4. **Monitor**: Check that status accuracy improves

## Testing

### Test Script

```bash
python test_status_system.py
```

### Test Cases

```python
def test_bulk_refresh():
    """Test bulk status refresh functionality."""
    response = requests.post("/api/applications/refresh-all-statuses")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "total_checked" in data["data"]

def test_individual_status_with_cache():
    """Test individual status endpoint updates database."""
    response = requests.get("/api/app/test_model/1/status")
    assert response.status_code == 200
    data = response.json()
    assert "cached_status" in data["data"]
    assert "status_age_minutes" in data["data"]

def test_status_freshness():
    """Test status freshness checking."""
    app = GeneratedApplication.query.first()
    assert app.is_status_fresh(max_age_minutes=5)
```

## Monitoring

### Status Metrics

Track these metrics to monitor system health:

- **Accuracy Rate**: Percentage of status checks that match Docker reality
- **Cache Hit Rate**: Percentage of requests served from database cache
- **Docker API Rate**: Number of Docker API calls per minute
- **Status Age Distribution**: How old cached statuses typically are

### Debugging

**Status appears incorrect:**
1. Check `last_status_check` timestamp in database
2. Compare `cached_status` vs `docker_status` in API response
3. Verify Docker daemon connectivity
4. Use bulk refresh to force synchronization

**Performance issues:**
1. Monitor Docker API call frequency
2. Check status polling JavaScript execution time
3. Verify database query performance on status-related operations

## Best Practices

### For Users

1. **Use Bulk Refresh**: When you notice multiple status inconsistencies
2. **Check Tooltips**: Hover over status badges to see last check time
3. **Monitor Age**: Fresh status (< 5 minutes) is most reliable

### For Developers

1. **Always Update Timestamps**: Use `update_container_status()` method
2. **Check Freshness**: Use `is_status_fresh()` before Docker calls
3. **Handle Errors Gracefully**: Continue with other apps if one fails
4. **Test Both Paths**: Verify both cache hits and Docker sync

### For Operations

1. **Monitor Docker Connectivity**: Ensure Docker daemon is accessible
2. **Database Performance**: Index on `last_status_check` is crucial
3. **Log Analysis**: Track status refresh frequency and success rates

## Future Enhancements

1. **WebSocket Updates**: Real-time status broadcast to all clients
2. **Background Sync**: Automatic periodic status refresh via Celery
3. **Health Monitoring**: Alerts when status consistency degrades
4. **Metrics Dashboard**: Visual tracking of status accuracy and performance
5. **Configuration**: Make timing parameters configurable via admin UI