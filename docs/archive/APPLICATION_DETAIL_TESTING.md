# Application Detail Page Testing Guide

**Testing the redesigned application detail system**

---

## Prerequisites

1. **Flask app running**: `cd src && python main.py`
2. **At least one application generated**: Check via `/applications` page or API
3. **Browser with dev tools**: Chrome, Firefox, or Edge

---

## Quick Tests

### 1. Basic Page Load
```bash
# Open in browser
http://localhost:5000/applications/{model_slug}/{app_number}

# Or test with curl
curl http://localhost:5000/applications/google_gemini-2_0-flash-exp_free/1
```

**Expected:**
- Page loads without errors
- Header with application title visible
- Metrics cards showing status, files, ports, etc.
- Tab navigation visible
- Overview tab loads automatically

### 2. Section Loading (HTMX)
```bash
# Test each section endpoint
curl http://localhost:5000/applications/{model_slug}/{app_number}/section/overview
curl http://localhost:5000/applications/{model_slug}/{app_number}/section/files
curl http://localhost:5000/applications/{model_slug}/{app_number}/section/container
curl http://localhost:5000/applications/{model_slug}/{app_number}/section/ports
```

**Expected:**
- Each endpoint returns valid HTML
- No template errors or missing variables
- Data displays correctly (not showing raw objects)

### 3. Interactive Features

#### File Explorer
1. Click **Files** tab
2. Click on any file in the tree
3. Preview should load in the right panel

#### Port Testing
1. Click **Ports** tab
2. If ports exist, click **Test All**
3. Toast notification should appear
4. Port status updates

#### Container Controls
1. Click **Container** tab
2. Try **Start**, **Stop**, or **Restart** buttons
3. Toast notifications should show progress
4. Status should update

#### Prompts Modal
1. Click **View Prompts** button in header
2. Modal should open with backend/frontend prompts
3. **Copy** button should work
4. Modal dismisses properly

---

## Browser Dev Tools Tests

### Console Errors
```javascript
// Open Console (F12)
// Should see:
✓ HTMX request successful: /applications/.../section/overview
✓ No JavaScript errors
✓ No 404s for assets

// Should NOT see:
✗ Uncaught TypeError
✗ Failed to load resource
✗ HTMX request failed
```

### Network Tab
```
Check HTMX requests:
✓ Status: 200 OK
✓ Type: xhr
✓ Response: HTML (not JSON)
✓ Size: Reasonable (< 50KB per section)
```

### Lighthouse Audit
```
Performance: > 90
Accessibility: > 95
Best Practices: > 90
```

---

## Visual Regression Tests

### Desktop (1920x1080)
- [ ] Metrics cards: 4 columns
- [ ] Overview: 3 cards + 1 full-width
- [ ] Files: Split view (40/60)
- [ ] Container: 4 equal columns
- [ ] No horizontal scrolling

### Tablet (768x1024)
- [ ] Metrics cards: 2 columns
- [ ] Overview: 2 cards per row
- [ ] Files: Stacked layout
- [ ] Container: 2 cards per row

### Mobile (375x667)
- [ ] Metrics cards: 1 column
- [ ] All cards full width
- [ ] Tab navigation scrollable
- [ ] Buttons stack vertically

---

## API Response Tests

### Application Data Structure
```python
# Test via Python REPL
import requests
r = requests.get('http://localhost:5000/api/applications')
print(r.json())

# Should have:
{
  "data": [
    {
      "id": int,
      "app_number": int,
      "model_slug": str,
      "app_type": str,
      "container_status": str,
      "created_at": str
    }
  ],
  "success": true
}
```

### Section Endpoints
```python
# Test each section
sections = ['overview', 'files', 'container', 'ports', 'analyses', 'metadata']
for section in sections:
    url = f'http://localhost:5000/applications/{model_slug}/{app_num}/section/{section}'
    r = requests.get(url)
    assert r.status_code == 200
    assert '<div class="row' in r.text or '<div class="card' in r.text
```

---

## Component-Specific Tests

### Overview Tab
```
✓ Identity card shows: model, provider, app number, created date, frameworks
✓ Lifecycle card shows: container status, ports count, generation status
✓ Code Footprint shows: total LOC, file count, breakdown by language
✓ Highlights shows: sibling apps, last check, docker compose badge
```

### Files Tab
```
✓ File tree displays all files with icons
✓ Directories shown but not clickable
✓ Clicking file loads preview
✓ Active file highlighted
✓ Metrics show: total files, total size, code files, config files
✓ File types table displays extension breakdown
```

### Container Tab
```
✓ Lifecycle state card shows status with badge
✓ Runtime summary shows: image, uptime, health check, restart policy
✓ Controls card has: Start, Stop, Restart, Rebuild buttons
✓ Diagnostics shows: logs preview, resource usage, network info
```

### Ports Tab
```
✓ Table shows: container port, host port, protocol, status
✓ Actions per port: Copy URL, Open, Test
✓ Bulk actions: Test All, Refresh, Report
✓ Empty state when no ports
```

---

## Error Handling Tests

### Network Errors
```javascript
// Simulate offline
// In dev tools: Network > Offline
// Try any HTMX action
// Should see: Toast "A server error occurred"
```

### 404 Responses
```bash
# Invalid application
curl http://localhost:5000/applications/invalid_model/999

# Should: 404 page or error message
```

### Missing Data
```python
# Application with no files
# Should show: "No files discovered" empty state with "Scan again" button

# Application with no ports
# Should show: "No published ports" empty state
```

---

## Performance Benchmarks

### Page Load Time
```
First Load: < 500ms (server-side render)
HTMX Section Load: < 200ms per section
File Preview Load: < 100ms
```

### Memory Usage
```
Initial page: ~5-10MB
After all tabs loaded: ~15-20MB
No memory leaks on tab switching
```

### Bundle Sizes
```
No custom CSS bundle (removed ~300 lines)
No custom JS bundle for layout
Only Tabler + Bootstrap + HTMX
```

---

## Accessibility Tests

### Keyboard Navigation
```
Tab key: Moves through interactive elements
Enter/Space: Activates buttons and tabs
Arrow keys: Navigate between tabs
Escape: Closes modals
```

### Screen Reader Test
```
NVDA/JAWS should announce:
- "Application #1, heading level 2"
- "Tab list with 8 tabs"
- "Overview tab, selected"
- "Loading overview"
- "Identity, heading level 3"
```

### Color Contrast
```
All text: > 4.5:1 contrast ratio
Interactive elements: > 3:1 contrast ratio
Focus indicators: Visible on all elements
```

---

## Automated Test Script

```bash
#!/bin/bash
# Quick smoke test for application detail pages

BASE_URL="http://localhost:5000"
MODEL="google_gemini-2_0-flash-exp_free"
APP=1

echo "Testing application detail page..."

# Test main page
curl -f -s "$BASE_URL/applications/$MODEL/$APP" > /dev/null && echo "✓ Main page loads" || echo "✗ Main page failed"

# Test sections
for section in overview files container ports; do
  curl -f -s "$BASE_URL/applications/$MODEL/$APP/section/$section" > /dev/null && echo "✓ $section section loads" || echo "✗ $section section failed"
done

# Test prompts modal
curl -f -s "$BASE_URL/applications/$MODEL/$APP/prompts/modal" > /dev/null && echo "✓ Prompts modal loads" || echo "✗ Prompts modal failed"

echo "Done!"
```

---

## Common Issues & Fixes

### Issue: Tabs not loading
**Cause:** HTMX not initialized or network error  
**Fix:** Check browser console for errors, verify Flask app is running

### Issue: Styles look broken
**Cause:** Missing Tabler CSS or Bootstrap  
**Fix:** Check `base.html` includes correct CSS CDN links

### Issue: JavaScript functions undefined
**Cause:** Function called before DOM ready  
**Fix:** Ensure scripts block at end of template

### Issue: Empty states not showing
**Cause:** Template logic checking wrong variable  
**Fix:** Verify `{% if files %}` and similar checks

### Issue: HTMX targets not found
**Cause:** Tab ID mismatch  
**Fix:** Ensure `#tab-{section.id}` matches between template and endpoints

---

## Reporting Bugs

When reporting issues, include:

1. **URL tested**: Full application detail URL
2. **Browser**: Chrome 120, Firefox 121, etc.
3. **Console errors**: Copy/paste from dev tools
4. **Network tab**: Screenshots of failed requests
5. **Expected vs Actual**: What should happen vs what does
6. **Steps to reproduce**: Numbered list of actions

---

## Test Results Template

```markdown
## Test Results - [Date]

**Tester:** [Your Name]
**Environment:** Local dev / Staging / Production
**Browser:** Chrome 120.0.6099.109

### Summary
- Tests Run: 15
- Tests Passed: 14
- Tests Failed: 1
- Blockers: 0

### Passed ✓
- Page loads without errors
- All sections render correctly
- File explorer interactive
- Port actions work
- Toast notifications display
- ...

### Failed ✗
- [ ] Container restart button gives 500 error
  - **Severity:** Medium
  - **Logs:** `AttributeError: 'NoneType' object has no attribute 'id'`
  - **Steps:** Click Container tab → Click Restart button
  - **Expected:** Container restarts
  - **Actual:** Error toast appears

### Notes
- Overall performance excellent
- Mobile layout needs minor spacing adjustment
- Consider adding keyboard shortcuts for common actions
```

---

This testing guide covers all aspects of the redesigned application detail system. Use it to verify functionality, performance, and user experience before deploying to production.
