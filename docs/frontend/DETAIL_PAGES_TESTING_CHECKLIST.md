# Detail Pages Redesign - Testing Checklist

**Date:** January 23, 2025  
**Tester:** _________________  
**Browser:** _________________  
**Screen Size:** _________________

---

## Pre-Test Setup

- [ ] Pull latest code from main branch
- [ ] Verify CSS file exists: `src/static/css/detail-pages.css`
- [ ] Verify macro file exists: `src/templates/components/detail_macros.html`
- [ ] Clear browser cache and reload
- [ ] Open browser DevTools (Console + Network tabs)
- [ ] Verify no CSS/JS errors in console

---

## Test 1: Applications Detail Page

### URL
`http://localhost:5000/applications/{model_slug}/{app_number}`

Example: `/applications/openai_gpt-4/1`

### Visual Verification
- [ ] Header displays with icon, title, subtitle
- [ ] Status badge shows container state (Running/Stopped)
- [ ] Action buttons visible (Start, Stop, Restart, Build, View, etc.)
- [ ] Buttons show icons only on mobile (<992px), icons + text on desktop
- [ ] Metric grid shows 6 cards on desktop (≥1200px)
- [ ] Metric grid shows 4 cards on tablet (768-1199px)
- [ ] Metric grid shows 1 card on mobile (<768px)
- [ ] Sticky navigation appears below header
- [ ] All section links visible in navigation
- [ ] First section (Overview) is active by default

### Lazy Loading
- [ ] Overview section loads immediately (first section)
- [ ] Scroll to Files section - content loads when visible
- [ ] Scroll to Ports section - content loads when visible
- [ ] Check Network tab - sections load individually
- [ ] Skeleton loaders visible before content loads
- [ ] No duplicate requests (check `revealed once` works)

### Scroll Spy
- [ ] Scroll to Files section - nav link highlights
- [ ] Scroll to Container section - nav link highlights
- [ ] Click on Analyses link - page scrolls smoothly
- [ ] Active link has underline indicator
- [ ] Navigation scrolls horizontally if needed

### Interactions
- [ ] Click Start button - shows toast notification
- [ ] Click Stop button - shows toast notification
- [ ] Click View button - opens new tab (if running)
- [ ] Click on Prompts button - opens modal
- [ ] Modal closes properly
- [ ] Container logs button works (if applicable)

### Responsive
- [ ] Resize to 375px (mobile) - layout stacks vertically
- [ ] Resize to 768px (tablet) - 4-column metric grid
- [ ] Resize to 1200px (desktop) - 6-column metric grid
- [ ] Header wraps properly on small screens
- [ ] Navigation scrolls horizontally on small screens

### Dark Theme
- [ ] Toggle dark theme - page adapts immediately
- [ ] Metric cards have proper contrast
- [ ] Navigation remains visible
- [ ] No white flashes or transitions
- [ ] All text remains readable

---

## Test 2: Model Detail Page

### URL
`http://localhost:5000/models/{model_slug}`

Example: `/models/openai_gpt-4`

### Visual Verification
- [ ] Header displays with robot icon, model name
- [ ] Badges show provider, capabilities (if any)
- [ ] Action buttons visible (Generate App, Compare, etc.)
- [ ] Metric grid shows 6 cards (Apps, Tests, Cost, etc.)
- [ ] Sticky navigation appears
- [ ] All section links visible (Overview, Applications, Capabilities, etc.)

### Lazy Loading
- [ ] Overview section loads immediately
- [ ] Scroll to Applications section - loads when visible
- [ ] Scroll to Capabilities section - loads when visible
- [ ] Check Network tab - sections load individually
- [ ] Skeleton loaders visible before content
- [ ] Error section shows retry button if content fails

### Scroll Spy
- [ ] Scroll through sections - nav updates actively
- [ ] Click on Pricing link - scrolls to section
- [ ] Active section highlighted correctly
- [ ] Navigation scrolls horizontally if needed

### Interactions
- [ ] Click Generate Application - shows toast
- [ ] Click Compare Models - opens new window
- [ ] Any other action buttons work properly

### Responsive
- [ ] Test at 375px, 768px, 1200px widths
- [ ] Metric grid adjusts column count
- [ ] Header stacks on mobile
- [ ] Navigation scrolls on mobile

### Dark Theme
- [ ] Toggle dark theme - page adapts
- [ ] All components remain visible
- [ ] Text contrast sufficient

---

## Test 3: Analysis Result Detail Page

### URL
`http://localhost:5000/analysis/results/{result_id}`

Example: `/analysis/results/abc123def456...`

### Visual Verification
- [ ] Header shows microscope icon, analysis type
- [ ] Badges show status (Completed/Failed), type, tool count
- [ ] Action buttons: Back, View JSON, Download
- [ ] Metric grid shows findings, tools, services, etc.
- [ ] Sticky navigation shows all analysis sections
- [ ] First section (Static Analysis) visible immediately

### Static Content Loading
- [ ] All sections load immediately (NO lazy loading for analysis)
- [ ] All tab partials included server-side
- [ ] Network tab shows single page load
- [ ] No HTMX requests for sections

### Scroll Spy
- [ ] Scroll through sections - nav highlights active
- [ ] Click on Performance link - scrolls to section
- [ ] Click on AI Requirements - scrolls to section
- [ ] Smooth scroll behavior works

### Interactions
- [ ] Click Back button - returns to analysis list
- [ ] Click View JSON - opens JSON in new tab
- [ ] Click Download - downloads result file
- [ ] JSON file opens/downloads correctly

### Data Display
- [ ] Static analysis findings display properly
- [ ] Dynamic analysis results show if present
- [ ] Performance metrics render correctly
- [ ] AI requirements section shows data
- [ ] Metadata section displays all info

### Responsive
- [ ] Test at multiple widths
- [ ] Tables remain readable on mobile
- [ ] Code blocks don't overflow
- [ ] Metric grid adjusts properly

### Dark Theme
- [ ] Toggle dark theme
- [ ] Syntax highlighting remains readable
- [ ] Tables have proper contrast
- [ ] All sections visible

---

## Test 4: Cross-Browser Compatibility

### Chrome/Edge (90+)
- [ ] All features work
- [ ] Scroll spy activates
- [ ] Lazy loading works
- [ ] Animations smooth

### Firefox (88+)
- [ ] All features work
- [ ] Scroll spy activates
- [ ] Lazy loading works
- [ ] Animations smooth

### Safari (14+)
- [ ] All features work
- [ ] Scroll spy activates
- [ ] Lazy loading works
- [ ] Scrollbar styling graceful fallback

### Mobile Safari (iOS 14+)
- [ ] All features work
- [ ] Touch scrolling smooth
- [ ] Buttons properly sized for touch
- [ ] No layout shifts

---

## Test 5: Accessibility

### Keyboard Navigation
- [ ] Tab through all interactive elements
- [ ] Focus indicators visible
- [ ] Enter/Space activates buttons
- [ ] Escape closes modals
- [ ] Arrow keys navigate (if applicable)

### Screen Reader (NVDA/VoiceOver)
- [ ] Page title announced
- [ ] Section headings announced
- [ ] Button labels descriptive
- [ ] Loading states announced
- [ ] Form fields have labels

### ARIA Attributes
- [ ] Inspect header - proper `aria-label` on icon buttons
- [ ] Inspect sections - `aria-labelledby` links to heading
- [ ] Inspect nav - `aria-label="Section navigation"`
- [ ] Inspect skeletons - `aria-live="polite"` and `aria-busy="true"`

### Color Contrast
- [ ] Run axe DevTools - 0 violations
- [ ] Body text passes 4.5:1 ratio
- [ ] Large text passes 3:1 ratio
- [ ] UI components pass 3:1 ratio
- [ ] Dark theme passes contrast checks

---

## Test 6: Performance

### Initial Load
- [ ] Open DevTools Performance tab
- [ ] Hard refresh page (Cmd+Shift+R / Ctrl+Shift+R)
- [ ] First Paint < 500ms
- [ ] Skeleton loaders visible immediately
- [ ] No layout shifts after load

### Lazy Loading
- [ ] Check Network tab waterfall
- [ ] First section loads on page load
- [ ] Other sections load on scroll
- [ ] No duplicate requests
- [ ] Sections load in < 200ms each

### Scroll Performance
- [ ] Smooth 60fps scrolling
- [ ] No janky animations
- [ ] Scroll spy updates quickly
- [ ] Navigation follows scroll smoothly

### Memory Usage
- [ ] Open DevTools Memory tab
- [ ] Record heap snapshot
- [ ] Navigate through sections
- [ ] No memory leaks
- [ ] Heap size reasonable

### Lighthouse Audit
- [ ] Run Lighthouse audit
- [ ] Performance > 80
- [ ] Accessibility > 90
- [ ] Best Practices > 90
- [ ] SEO > 80

---

## Test 7: Error Handling

### Network Errors
- [ ] Disconnect network
- [ ] Scroll to lazy-loaded section
- [ ] Error UI displays with retry button
- [ ] Reconnect network
- [ ] Click retry - content loads

### 404 Errors
- [ ] Navigate to invalid URL
- [ ] 404 page displays
- [ ] Back button works

### Server Errors
- [ ] Trigger 500 error (if possible)
- [ ] Toast notification shows
- [ ] Error logged in console
- [ ] Page remains functional

### Missing Data
- [ ] Navigate to page with no metrics
- [ ] Empty state displays properly
- [ ] Navigate to page with no sections
- [ ] Page doesn't break

---

## Test 8: Edge Cases

### Long Content
- [ ] Model with 100+ applications
- [ ] Analysis with 1000+ findings
- [ ] Very long model names
- [ ] Very long file paths
- [ ] Content doesn't overflow
- [ ] Pagination/truncation works

### Special Characters
- [ ] Model slug with underscores
- [ ] Model slug with dashes
- [ ] Unicode characters in names
- [ ] Emojis in descriptions (if any)
- [ ] All render correctly

### Empty States
- [ ] Application with no files
- [ ] Model with no applications
- [ ] Analysis with no findings
- [ ] Empty state UI displays
- [ ] Call-to-action buttons work

### Concurrent Actions
- [ ] Click multiple buttons quickly
- [ ] Scroll rapidly through sections
- [ ] Open multiple modals
- [ ] No race conditions
- [ ] State remains consistent

---

## Test 9: Print Output

### Print Preview
- [ ] Open print preview (Cmd+P / Ctrl+P)
- [ ] Header visible
- [ ] Metrics visible
- [ ] Navigation hidden
- [ ] Actions hidden
- [ ] All sections visible
- [ ] No content cut off
- [ ] Page breaks appropriate

### PDF Export
- [ ] Export to PDF
- [ ] Open PDF
- [ ] All content readable
- [ ] Layout preserved
- [ ] Links functional (if supported)

---

## Test 10: Integration Testing

### Application Detail
- [ ] Start application - container status updates
- [ ] Stop application - container status updates
- [ ] Build application - shows progress
- [ ] View application - opens correct URL
- [ ] Run analysis - redirects to results
- [ ] View prompts - modal shows correct data

### Model Detail
- [ ] Generate application - creates new app
- [ ] View application - opens app detail
- [ ] Compare models - opens comparison page
- [ ] Applications list loads correctly
- [ ] Pricing info displays if available

### Analysis Detail
- [ ] Back button returns to list
- [ ] JSON view shows valid JSON
- [ ] Download saves correct file
- [ ] All findings render properly
- [ ] Severity colors correct
- [ ] Tool results visible

---

## Test 11: Regression Testing

### Existing Functionality
- [ ] Container manager still works
- [ ] Container logs modal still works
- [ ] Port configuration still works
- [ ] File browser still works
- [ ] Analysis creation still works
- [ ] Batch operations still work

### Data Integrity
- [ ] Application data correct
- [ ] Model data correct
- [ ] Analysis data correct
- [ ] Timestamps correct
- [ ] Metrics calculated correctly

### Routes
- [ ] All detail page routes work
- [ ] Section partial routes work
- [ ] Modal routes work
- [ ] API endpoints work
- [ ] No 404 errors

---

## Test 12: Documentation Verification

### Design System Doc
- [ ] Open `DETAIL_PAGES_DESIGN_SYSTEM.md`
- [ ] All code examples valid
- [ ] All component classes exist in CSS
- [ ] All macros exist in template
- [ ] Examples render correctly

### Migration Guide
- [ ] Follow migration steps
- [ ] Create test detail page
- [ ] All steps work as documented
- [ ] No missing dependencies

---

## Bug Report Template

If any test fails, document here:

### Bug #1
- **Test:** _______________________
- **Expected:** _______________________
- **Actual:** _______________________
- **Steps to Reproduce:**
  1. _______________________
  2. _______________________
  3. _______________________
- **Browser:** _______________________
- **Screen Size:** _______________________
- **Screenshot:** _______________________

### Bug #2
- **Test:** _______________________
- **Expected:** _______________________
- **Actual:** _______________________
- **Steps to Reproduce:**
  1. _______________________
  2. _______________________
  3. _______________________
- **Browser:** _______________________
- **Screen Size:** _______________________
- **Screenshot:** _______________________

---

## Sign-Off

### Testing Complete
- [ ] All tests passed
- [ ] All bugs documented
- [ ] All critical bugs fixed
- [ ] Ready for production

**Tester Name:** _______________________  
**Date:** _______________________  
**Signature:** _______________________

### Review Complete
- [ ] Tests reviewed
- [ ] Bugs triaged
- [ ] Documentation updated
- [ ] Approved for deployment

**Reviewer Name:** _______________________  
**Date:** _______________________  
**Signature:** _______________________
