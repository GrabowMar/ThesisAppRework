# Performance & Accessibility

## Performance Budgets
| Metric | Target |
|--------|--------|
| Initial HTML (dashboard) | < 120KB uncompressed |
| Fragment response | < 40KB typical |
| Time To First Byte (server) | < 400ms P95 (compute route side) |
| DOM Nodes (dashboard main) | < 1500 |

## Monitoring
- Add lightweight logging of fragment render duration (Flask before/after request for HTMX flagged requests).
- Periodic Lighthouse run (manual initially) archived in `reports/`.

## Optimization Techniques
- Streaming partial updates only if full page heavy (not immediate need).
- Paginate large tables (apps, tasks) after 50 rows.
- Defer non-critical HTMX requests via `hx-trigger="revealed"` for below-the-fold content.
- Cache static aggregated metrics in memory for short TTL if query cost high.

## Accessibility Checklist
- Semantic landmarks: `<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>`.
- Forms have associated labels; placeholders not used as labels.
- Color contrast meets WCAG AA: run automated check.
- Keyboard: all interactive elements reachable via Tab; focus styles visible.
- Dynamic updates announce in `aria-live` region where user expectation of change is implicit.
- Tables: `<th scope="col">` for headers; summary or caption if complex.

## A11y Testing Flow
1. Render page with test client.
2. Run axe-core against HTML snapshot (future automation).
3. Validate no critical issues; log new ones in issue tracker.

## Internationalization (Future Consideration)
- Wrap user-visible strings in helper if i18n introduced later.
- Avoid concatenating translatable strings.

## Print & Export Views
- `print.html` layout minimalizes navigation; ensure content readable in monochrome.

## Animations / Motion
- Keep subtle; respect prefers-reduced-motion (future enhancement if animations added).

## Dark Mode (Optional Later)
- Plan tokens such that alternate theme can flip color variables.
