# Versioning UI Integration - Quick Reference

## Summary of Changes

This document provides a quick reference for the UI changes made to support application versioning.

**Date**: January 2025  
**Status**: ✅ Implemented and tested

## Files Modified

### 1. Template Updates

#### `src/templates/pages/models/partials/model_applications.html`
**Changes**:
- Added **Version** column showing version badge (v1, v2, v3...)
- Added **Template** column displaying template_slug or "Default"
- Added **version count badge** next to app number when multiple versions exist
- Added **regenerate button** (refresh icon) for each app
- Added **parent app indicator** (arrow icon) for regenerated versions

**New columns**:
```html
<th>Version</th>
<th>Template</th>
```

**Version badge**:
```html
<span class="badge bg-purple-lt">v{{ app.version or 1 }}</span>
```

**Regenerate button**:
```html
<button class="btn btn-sm btn-icon btn-cyan" 
        onclick="regenerateApplication('{{ model_slug }}', {{ app.app_number }})" 
        title="Regenerate this application (creates new version)">
  <i class="ti ti-refresh"></i>
</button>
```

#### `src/templates/pages/models/model_details.html`
**Changes**:
- Added `regenerateApplication()` JavaScript function
- Handles user confirmation
- Calls `/api/models/{slug}/apps/{num}/regenerate` endpoint
- Shows success/error toasts
- Auto-refreshes applications section after regeneration

**Function signature**:
```javascript
async function regenerateApplication(modelSlug, appNumber)
```

### 2. Backend Context Updates

#### `src/app/routes/jinja/detail_context.py`
**Changes**:
- Added version count query to `build_model_detail_context()`
- Computes `app_version_counts` dict mapping app_number → version count
- Added to context return dict

**Query**:
```python
version_count_query = db.session.query(
    GeneratedApplication.app_number,
    func.count(GeneratedApplication.id).label('version_count')
).filter_by(
    model_slug=model.canonical_slug
).group_by(
    GeneratedApplication.app_number
).all()
```

**Context addition**:
```python
return {
    ...
    'app_version_counts': app_version_counts,  # NEW
    ...
}
```

## UI Features

### Visual Indicators

1. **Version Badge**: Purple badge showing "v1", "v2", etc.
2. **Template Badge**: Indigo badge showing template name (or "Default")
3. **Version Count**: Cyan badge with count icon showing "3" when app has 3 versions
4. **Regeneration Arrow**: Small arrow icon indicating version was regenerated from previous

### User Actions

1. **View Application**: Eye icon → `/applications/{model}/{app_num}`
2. **Open Running App**: External link icon → `http://localhost:{port}` (only if running)
3. **Regenerate**: Refresh icon → Creates new version

### Regeneration Workflow

1. User clicks regenerate button (🔄)
2. Confirmation dialog: "Are you sure you want to regenerate application #X? This will create a new version."
3. If confirmed:
   - POST to `/api/models/{slug}/apps/{num}/regenerate`
   - Toast: "Starting regeneration..."
   - On success: "Application #X vY regeneration started"
   - Auto-refresh applications section after 1.5s
4. New version appears in table with updated badge

## Testing

### Manual Testing Steps

1. **Navigate to model detail page** (e.g., `/models/openai_gpt-4`)
2. **Check applications table** - Should see Version and Template columns
3. **Verify version badges** - Should show v1, v2, etc.
4. **Click regenerate button** on any app
5. **Confirm dialog** and wait for completion
6. **Verify new version** appears with incremented version number

### Automated Testing

Run test suite:
```powershell
python scripts/test_versioning_ui.py
```

Expected output: All 4 tests pass
- ✅ Context Builder
- ✅ Template Rendering
- ✅ JavaScript Functions
- ✅ Database Schema

## API Endpoint

### Regenerate Application
```http
POST /api/models/{model_slug}/apps/{app_number}/regenerate
Content-Type: application/json
```

**Optional Request Body**:
```json
{
  "template_slug": "minimal",
  "app_type": "web_app"
}
```

**Response** (201 Created):
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

## Browser Developer Tools

### Console Commands for Testing

```javascript
// Regenerate app #1 for current model
regenerateApplication('openai_gpt-4', 1);

// Check if function exists
typeof regenerateApplication;  // Should be "function"

// Manually refresh applications section
htmx.ajax('GET', '/models/detail/openai_gpt-4/section/applications', {
  target: '#section-applications',
  swap: 'innerHTML'
});
```

### Network Tab Monitoring

When regenerating, watch for:
1. **POST** to `/api/models/{slug}/apps/{num}/regenerate`
   - Status: 201 Created
   - Response body contains new version info

2. **GET** to `/models/detail/{slug}/section/applications` (after 1.5s)
   - Status: 200 OK
   - Response body is updated HTML partial

## Troubleshooting

### Issue: Regenerate button does nothing
**Check**:
1. Browser console for JavaScript errors
2. `regenerateApplication` function exists in page source
3. Network tab for failed API requests

### Issue: Version counts not showing
**Check**:
1. `app_version_counts` in template context (view page source, search for "app_version_counts")
2. Database has multiple versions: `SELECT model_slug, app_number, version FROM generated_applications;`

### Issue: Template column shows "Default" for all apps
**Check**:
1. Database field: `SELECT template_slug FROM generated_applications;`
2. Apps were generated with explicit template_slug (older apps may be NULL)

### Issue: New version not appearing after regeneration
**Check**:
1. Backend logs for errors during generation
2. Database for new record: `SELECT * FROM generated_applications WHERE app_number = X ORDER BY version DESC;`
3. `generation_status` field (should be 'pending' or 'completed')

## Related Documentation

- [Full Versioning Guide](./VERSIONING.md) - Comprehensive documentation
- [Analysis Workflow](./ANALYSIS_WORKFLOW.md) - Generation and analysis process
- [API Documentation](./API_AUTH_AND_METHODS.md) - API endpoints and authentication

---

**Last Updated**: January 2025  
**Test Status**: ✅ All tests passing
