# Cookie Manager Migration Guide

This guide shows how to update existing code to respect user cookie preferences.

## Quick Reference

### Before (Direct localStorage)
```javascript
localStorage.setItem('myKey', 'myValue');
const value = localStorage.getItem('myKey');
```

### After (Cookie-Aware)
```javascript
// Option 1: Use safe wrapper (recommended)
window.safeLocalStorage.setItem('myKey', 'myValue', 'functional');
const value = window.safeLocalStorage.getItem('myKey', 'functional');

// Option 2: Check permission first
if (window.canUseStorage('analytics')) {
  localStorage.setItem('analytics_data', data);
}
```

## Category Guidelines

Choose the appropriate category for your data:

| Category | Use When | Examples |
|----------|----------|----------|
| `essential` | Required for core functionality | Session data, auth tokens, theme, language |
| `functional` | Enhances UX but not required | UI state, table prefs, saved filters |
| `analytics` | Tracks usage/performance | Page views, feature usage, timing metrics |
| `ai` | AI-related caching | Model configs, analysis cache, prompt history |

## Migration Examples

### Example 1: Table Preferences (Functional)

**Before:**
```javascript
function saveTablePreferences(tableId, prefs) {
  localStorage.setItem('table_' + tableId, JSON.stringify(prefs));
}

function loadTablePreferences(tableId) {
  const stored = localStorage.getItem('table_' + tableId);
  return stored ? JSON.parse(stored) : null;
}
```

**After:**
```javascript
function saveTablePreferences(tableId, prefs) {
  window.safeLocalStorage.setItem(
    'table_' + tableId,
    JSON.stringify(prefs),
    'functional'
  );
}

function loadTablePreferences(tableId) {
  const stored = window.safeLocalStorage.getItem('table_' + tableId, 'functional');
  return stored ? JSON.parse(stored) : null;
}
```

### Example 2: Analytics Tracking

**Before:**
```javascript
function trackPageView(page) {
  const views = JSON.parse(localStorage.getItem('page_views') || '{}');
  views[page] = (views[page] || 0) + 1;
  localStorage.setItem('page_views', JSON.stringify(views));
}
```

**After:**
```javascript
function trackPageView(page) {
  // Only track if analytics enabled
  if (!window.canUseStorage('analytics')) {
    return;
  }

  const stored = localStorage.getItem('page_views');
  const views = stored ? JSON.parse(stored) : {};
  views[page] = (views[page] || 0) + 1;
  localStorage.setItem('page_views', JSON.stringify(views));
}

// Or use the safe wrapper
function trackPageView(page) {
  const stored = window.safeLocalStorage.getItem('page_views', 'analytics');
  const views = stored ? JSON.parse(stored) : {};
  views[page] = (views[page] || 0) + 1;
  window.safeLocalStorage.setItem('page_views', JSON.stringify(views), 'analytics');
}
```

### Example 3: AI Model Preferences

**Before:**
```javascript
function saveModelPreference(modelId) {
  localStorage.setItem('preferred_model', modelId);
}

function getModelPreference() {
  return localStorage.getItem('preferred_model') || 'gpt-4';
}
```

**After:**
```javascript
function saveModelPreference(modelId) {
  window.safeLocalStorage.setItem('preferred_model', modelId, 'ai');
}

function getModelPreference() {
  return window.safeLocalStorage.getItem('preferred_model', 'ai') || 'gpt-4';
}
```

### Example 4: Sidebar State (Functional)

**Before:**
```javascript
function toggleSidebar() {
  const collapsed = document.body.classList.toggle('sidebar-collapsed');
  localStorage.setItem('sidebarPref', collapsed ? 'collapsed' : 'expanded');
}

function initSidebar() {
  const pref = localStorage.getItem('sidebarPref');
  if (pref === 'collapsed') {
    document.body.classList.add('sidebar-collapsed');
  }
}
```

**After:**
```javascript
function toggleSidebar() {
  const collapsed = document.body.classList.toggle('sidebar-collapsed');
  window.safeLocalStorage.setItem(
    'sidebarPref',
    collapsed ? 'collapsed' : 'expanded',
    'functional'
  );
}

function initSidebar() {
  const pref = window.safeLocalStorage.getItem('sidebarPref', 'functional');
  if (pref === 'collapsed') {
    document.body.classList.add('sidebar-collapsed');
  }
}
```

### Example 5: Essential Data (Always Allowed)

**Before:**
```javascript
function saveTheme(theme) {
  localStorage.setItem('app_theme', theme);
}
```

**After:**
```javascript
// Theme is essential, so no category check needed
// But you can still be explicit:
function saveTheme(theme) {
  window.safeLocalStorage.setItem('app_theme', theme, 'essential');
  // Or just use localStorage directly for essential data:
  localStorage.setItem('app_theme', theme);
}
```

## Handling Consent Changes

Listen for consent updates and react accordingly:

```javascript
document.addEventListener('cookieConsentUpdated', function(e) {
  const prefs = e.detail; // { essential, analytics, functional, ai }

  if (prefs.analytics) {
    // User enabled analytics - initialize tracking
    initializeAnalytics();
  } else {
    // User disabled analytics - stop tracking
    stopAnalytics();
  }

  if (prefs.functional) {
    // Load saved preferences
    loadUserPreferences();
  }

  if (prefs.ai) {
    // Initialize AI cache
    initializeAICache();
  }
});
```

## Graceful Degradation

Always provide fallbacks when storage is disabled:

```javascript
function getTablePageSize(tableId) {
  // Try to get saved preference
  const saved = window.safeLocalStorage.getItem('table_pagesize_' + tableId, 'functional');

  // Fall back to default if not available
  return saved ? parseInt(saved) : 25;
}

function saveTablePageSize(tableId, size) {
  // Attempt to save, but don't error if it fails
  window.safeLocalStorage.setItem('table_pagesize_' + tableId, size, 'functional');
}
```

## Common Patterns

### Pattern 1: Feature Initialization

```javascript
function initFeature() {
  // Check if we can use the storage category
  if (!window.canUseStorage('functional')) {
    // Use default behavior without preferences
    console.log('Using defaults (functional storage disabled)');
    return;
  }

  // Load and apply saved preferences
  const prefs = loadPreferences();
  applyPreferences(prefs);
}
```

### Pattern 2: Conditional Tracking

```javascript
function logFeatureUsage(feature) {
  // Only log if analytics enabled
  if (window.canUseStorage('analytics')) {
    trackEvent('feature_used', { feature });
  }
}
```

### Pattern 3: Cache Management

```javascript
function cacheAnalysisResult(id, result) {
  if (!window.canUseStorage('ai')) {
    console.log('AI caching disabled, using memory only');
    // Store in memory cache only
    memoryCache[id] = result;
    return;
  }

  // Store in localStorage for persistence
  window.safeLocalStorage.setItem('analysis_' + id, JSON.stringify(result), 'ai');
}
```

## Testing

### Test Without Cookie Manager

During development, if `window.cookieManager` is not available, the safe wrapper provides fallbacks:

```javascript
// safeLocalStorage.setItem will check for cookieManager
// If not available, it returns false but doesn't throw
const saved = window.safeLocalStorage.setItem('key', 'value', 'functional');
if (!saved) {
  console.warn('Storage not available or not permitted');
}
```

### Test Different Consent States

In browser console:

```javascript
// Simulate enabling analytics
window.cookieManager.saveConsent({ analytics: true, functional: true, ai: false });

// Check current permissions
console.log(window.canUseStorage('analytics')); // true
console.log(window.canUseStorage('ai')); // false

// View current preferences
console.log(window.cookieManager.getPreferences());
```

## Checklist for Migration

- [ ] Identify all `localStorage.setItem()` calls
- [ ] Categorize each storage use (essential/functional/analytics/ai)
- [ ] Replace with `safeLocalStorage` or permission checks
- [ ] Add fallbacks for when storage is disabled
- [ ] Test with all consent combinations
- [ ] Update documentation if adding new storage keys
- [ ] Consider privacy implications of stored data

## Need Help?

- Review `COOKIE_MANAGEMENT.md` for architecture details
- Check `src/static/js/cookie-manager.js` for API reference
- See privacy policy page for user-facing information

## Pro Tips

1. **Group Related Keys**: Use prefixes like `table_`, `model_`, `analytics_`
2. **Document Categories**: Add comments explaining why each category was chosen
3. **Test Edge Cases**: What happens if localStorage is full? If it's blocked by browser?
4. **Respect User Choice**: Don't nag users to enable optional categories
5. **Minimize Essential**: Only mark truly essential data as `essential`
6. **Clean Up**: Remove old keys when features are deprecated

## Example: Complete Feature Migration

**Before: Feature with localStorage**
```javascript
// Old analytics.js
(function() {
  function trackEvent(event, data) {
    const events = JSON.parse(localStorage.getItem('events') || '[]');
    events.push({ event, data, timestamp: Date.now() });
    localStorage.setItem('events', JSON.stringify(events));
  }

  window.analytics = { trackEvent };
})();
```

**After: Cookie-aware feature**
```javascript
// New analytics.js
(function() {
  function trackEvent(event, data) {
    // Check permission first
    if (!window.canUseStorage('analytics')) {
      return; // Silently skip if analytics disabled
    }

    const stored = localStorage.getItem('events');
    const events = stored ? JSON.parse(stored) : [];
    events.push({ event, data, timestamp: Date.now() });

    // Save with safe wrapper
    window.safeLocalStorage.setItem('events', JSON.stringify(events), 'analytics');
  }

  // Clean up when analytics disabled
  document.addEventListener('cookieConsentUpdated', function(e) {
    if (!e.detail.analytics) {
      console.log('Analytics disabled, clearing data');
      localStorage.removeItem('events');
    }
  });

  window.analytics = { trackEvent };
})();
```
