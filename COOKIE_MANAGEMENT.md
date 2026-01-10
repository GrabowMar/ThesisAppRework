# Cookie & Data Management Implementation

This document describes the cookie consent and data management system implemented in the Thesis Platform web application, based on Tabler's cookie banner design.

## Overview

The implementation provides a comprehensive GDPR-compliant cookie consent system that:
- Informs users about data collection practices
- Allows granular control over different data categories
- Provides a dedicated privacy policy page
- Integrates seamlessly with the existing Tabler UI

## Components

### 1. Cookie Banner Component
**File:** `src/templates/shared/ui/_cookie_banner.html`

A fixed-position banner that appears at the bottom of the screen for new users. Features:
- Modern Tabler-styled design with card layout
- Three action buttons: Settings, Accept All, Reject Optional
- Animated slide-up entrance
- Responsive layout for mobile and desktop

### 2. Cookie Settings Modal
**Included in:** `src/templates/shared/ui/_cookie_banner.html`

A detailed modal dialog allowing users to:
- View all data categories (Essential, Analytics, Functional, AI Processing)
- See exactly what data is stored in each category
- Enable/disable optional categories
- Understand the purpose of each data type

### 3. Cookie Manager JavaScript Module
**File:** `src/static/js/cookie-manager.js`

Core functionality includes:
- Consent storage in localStorage
- Version management for consent updates
- Category-based permission checking
- Safe localStorage wrapper functions
- Automatic data cleanup when categories are disabled
- Event system for consent changes

### 4. Privacy Policy Page
**Route:** `/privacy-policy`
**Template:** `src/templates/pages/privacy/privacy_main.html`
**Controller:** `src/app/routes/jinja/main.py`

Comprehensive privacy information page featuring:
- Detailed explanation of all data categories
- User rights and controls
- Security measures
- Contact information
- Quick links to manage preferences

### 5. Floating Settings Button
**Included in:** `src/templates/shared/ui/_cookie_banner.html`

A persistent floating button (bottom-left) that appears after initial consent, allowing users to:
- Re-open cookie settings at any time
- Change their preferences
- Review their current settings

## Data Categories

### Essential (Required)
**Always Enabled** - Cannot be disabled

Stores:
- Session tokens and authentication state
- CSRF protection tokens
- Theme preferences (dark/light mode)
- Language settings
- Security state

### Analytics & Performance (Optional)
**Default:** Disabled

Collects:
- Page views and navigation patterns
- Feature usage statistics
- Performance metrics (load times, API response times)
- Error logs and failed requests
- Session duration

Purpose: Improve application performance and user experience

### Functional & Preferences (Optional)
**Default:** Disabled

Stores:
- UI state (sidebar collapsed/expanded)
- Table preferences (columns, sorting, page size)
- Filter configurations
- Dashboard layout
- Recent searches

Purpose: Personalize user experience and remember preferences

### AI Processing & History (Optional)
**Default:** Disabled

Caches:
- Analysis results
- Model configurations
- Prompt history
- Result previews
- Model ratings and feedback

Purpose: Faster access to AI features and improved recommendations

## API & Integration

### JavaScript API

```javascript
// Check if a category is allowed
if (window.canUseStorage('analytics')) {
  // Track analytics
}

// Use safe localStorage wrapper
window.safeLocalStorage.setItem('key', 'value', 'functional');
window.safeLocalStorage.getItem('key', 'functional');

// Get current preferences
const prefs = window.cookieManager.getPreferences();

// Listen for consent changes
document.addEventListener('cookieConsentUpdated', function(e) {
  console.log('New preferences:', e.detail);
});

// Open settings programmatically
window.cookieManager.openSettings();
```

### Storage Keys

- `cookie_consent` - Stores user consent preferences
- Version: `1.0` - Current consent version

Consent object structure:
```json
{
  "version": "1.0",
  "timestamp": "2026-01-10T12:00:00.000Z",
  "preferences": {
    "essential": true,
    "analytics": false,
    "functional": false,
    "ai": false
  }
}
```

## User Flows

### First Visit
1. User loads the application
2. Cookie banner slides up from bottom after 500ms
3. User can:
   - Click "Accept All" - enables all categories
   - Click "Reject Optional" - keeps only essential
   - Click "Settings" - opens detailed modal

### Changing Preferences
1. User clicks cookie icon in footer or floating button
2. Modal opens with current settings
3. User toggles categories
4. Clicks "Save Preferences"
5. Settings saved and data cleaned up accordingly

### Privacy Policy
1. User clicks "Privacy" link in footer
2. Full privacy policy page loads
3. Detailed information about each category
4. Direct access to cookie settings from page

## Files Modified/Created

### New Files
- `src/templates/shared/ui/_cookie_banner.html` - Banner and modal UI
- `src/static/js/cookie-manager.js` - Cookie management logic
- `src/templates/pages/privacy/privacy_main.html` - Privacy policy page

### Modified Files
- `src/templates/layouts/base.html` - Added cookie banner include and script
- `src/templates/shared/ui/_footer.html` - Added privacy and cookie links
- `src/app/routes/jinja/main.py` - Added privacy policy route

## Best Practices

### For Developers

1. **Always check permissions before storing optional data:**
   ```javascript
   if (window.canUseStorage('analytics')) {
     // Your analytics code
   }
   ```

2. **Use the safe wrapper for localStorage:**
   ```javascript
   window.safeLocalStorage.setItem('pref', value, 'functional');
   ```

3. **Tag your localStorage keys by category:**
   - Analytics: `page_views`, `feature_usage`, `performance_metrics`
   - Functional: `table_preferences`, `filter_settings`, `ui_state`
   - AI: `analysis_cache`, `model_preferences`, `prompt_history`

4. **Listen for consent changes:**
   ```javascript
   document.addEventListener('cookieConsentUpdated', function(e) {
     if (e.detail.analytics) {
       initializeAnalytics();
     } else {
       disableAnalytics();
     }
   });
   ```

### For Users

- Access cookie settings via:
  - Footer "Cookies" link
  - Floating cookie button (bottom-left)
  - Privacy policy page buttons

- View detailed data usage information:
  - Visit `/privacy-policy` page
  - Open cookie settings modal

- Export or delete data:
  - Visit profile settings
  - Request data export
  - Request account deletion

## Testing

### Manual Testing Checklist

- [ ] Banner appears on first visit
- [ ] "Accept All" enables all categories
- [ ] "Reject Optional" keeps only essential
- [ ] Settings modal opens and saves preferences
- [ ] Floating button appears after consent
- [ ] Footer links open settings modal
- [ ] Privacy policy page loads correctly
- [ ] Settings persist across page reloads
- [ ] Data cleanup occurs when disabling categories
- [ ] Theme preference works (essential category)

### Browser Testing

Tested on:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

## Compliance

This implementation helps with:
- **GDPR** - User consent and right to data deletion
- **CCPA** - Transparency and opt-out options
- **ePrivacy Directive** - Cookie consent

Notes:
- Essential cookies don't require consent under most regulations
- Optional categories are opt-in by default
- Clear information about data usage is provided
- Easy access to preference management

## Future Enhancements

Potential improvements:
1. Server-side consent storage (sync across devices)
2. Consent analytics dashboard (admin view)
3. Automated data retention policies
4. Integration with third-party cookie scanning tools
5. Multi-language support for privacy policy
6. Consent expiration and re-prompting
7. Advanced analytics with consent-aware tracking

## Support

For questions or issues:
- Review the privacy policy: `/privacy-policy`
- Check the cookie settings modal
- Contact: privacy@thesisplatform.com

## License

Part of the Thesis Platform - see main project LICENSE file.
