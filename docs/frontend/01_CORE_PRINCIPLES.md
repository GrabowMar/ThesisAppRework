# Core Frontend Principles

These principles guide every change during the rewrite. Any exception must be justified in `14_RISKS_DECISIONS.md`.

## 1. Server-First Rendering
Render complete pages on the server; HTMX only fetches deltas. Benefits: SEO, accessibility, reduced complexity.

## 2. Separation of Concerns
- Business / data logic: Python services (ServiceLocator)
- Presentation & flow: Routes + templates
- Styling: Theme CSS + tokens, zero inline styles
- Micro-interactions: HTMX attributes, optional minimal JS modules

## 3. Progressive Enhancement
Baseline experience works without JS. HTMX requests augment but never gate core functionality (view list, start analysis, download report).

## 4. Consistent Template Hierarchy
`layouts/` → skeletons; `pages/<domain>/` → full pages; `ui/elements/<category>/` → reusable leaf components; `utils/macros/` → logic helpers.

## 5. Single Source of Truth
A component's markup lives in one file or macro. No copy-paste duplication; derive variants via context variables or small wrapper partials.

## 6. Explicit Boundaries
Routes never import concrete services directly (use ServiceLocator). Templates never perform unbounded queries (route supplies prepared data dicts).

## 7. Deterministic Naming & Paths
Predictable imports & includes; path changes require updating taxonomy doc.

## 8. Small, Composable Partials
Prefer many small semantic partials over monoliths—each with a clear responsibility named accordingly.

## 9. Observability by Design
Structural comments (e.g., `<!-- component:analysis-task-row -->`) or `data-component="analysis-task-row"` allow test hooks and runtime diagnostics.

## 10. Accessibility as a First-Class Constraint
Implement semantic HTML, label controls, manage focus for dynamic swaps, and maintain color contrast.

## 11. Performance Discipline
Keep DOM lean, minimize duplicate libraries, avoid giant tables without pagination or virtualization triggers.

## 12. Idempotent GET, Intentful POST
Ensure safe refresh & bookmarking; POST endpoints return updated fragment to replace the relevant region.

## 13. Document Everything Material
New component? Update taxonomy + style guide. Deviations? Log an ADR entry.

## 14. Quality Gates
A change merges only if: lint passes, tests pass, docs updated, no increase in duplicate component patterns.

## 15. Iterative Refactoring
Ship value each migration stage; do not attempt big-bang rewrite.
