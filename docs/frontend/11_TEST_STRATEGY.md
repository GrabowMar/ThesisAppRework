# Test Strategy (Frontend)

## Test Layers
1. Route Rendering Tests – Ensure each page route returns HTTP 200 and expected structural markers.
2. Fragment (HTMX) Tests – Simulate HTMX request headers; assert partial HTML root element id/class and absence of full layout wrapper.
3. Macro Unit Tests – Render macro with sample contexts; assert HTML snippet correctness.
4. Integration Tests – Trigger task creation endpoint, then poll fragment endpoint to simulate progress chain.
5. Visual Regression (Deferred) – Snapshot key pages after migration stabilized.

## Tooling
- pytest + Flask test client for HTML assertions.
- Use BeautifulSoup or lxml for structured parsing if needed.
- Add helper: `render_fragment(path, headers={'HX-Request': 'true'})`.

## Conventions
- Test ids: use `data-testid` attributes in components needing direct selection (avoid coupling to complex class chains).
- Keep fixtures minimal; stub services for deterministic outputs (ServiceLocator patching).

## Example Route Test
```
resp = client.get('/analysis/dashboard')
assert resp.status_code == 200
html = resp.text
assert '<!-- component:stats-cards -->' in html
```

## Example Fragment Test
```
resp = client.get('/analysis/dashboard', headers={'HX-Request': 'true'})
assert 'html>' not in resp.text  # no full layout
```

## Coverage Goals
- 100% of page routes
- 80% of HTMX-enabled partial endpoints (or branches in route returning partials)
- 100% macros providing logic beyond trivial markup

## Failure Diagnostics
On test failure: dump fragment HTML to `logs/test_failures/<test_name>.html` (future enhancement) for inspection.

## CI Gate
Add job ensuring new templates touched in PR have at least one test referencing them (simple heuristic: search path names in tests).
