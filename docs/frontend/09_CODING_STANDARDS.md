# Coding Standards (Frontend)

## HTML / Jinja
- Use semantic tags (`section`, `nav`, `main`, `header`, `footer`, `article`) appropriately.
- One `<h1>` per page (in `content` block); subsections use descending order.
- Attribute ordering: `id`, `class`, `data-*`, `hx-*`, `aria-*`, others.
- Avoid inline conditional clutter; pre-compute in route or macro.
- Include explanatory comments for complex conditional rendering blocks.

## HTMX
- Always specify `hx-target` & `hx-swap`.
- Use `hx-headers='{"X-Requested-Fragment": "component-name"}'` for server-side logic differentiating fragment vs full page if required.
- Use event triggers to cascade updates instead of chaining multiple polling fragments.

## Macros
- Minimal logic only (if/else, loops). Heavy transformation belongs in route/service.
- Document parameters at macro top with a comment block.

## CSS
- No inline `<style>` blocks unless print-specific and justified.
- Prefer utility classes (Bootstrap/AdminLTE) before creating new ones.
- Custom class names prefixed with `c-` (component) or `u-` (utility) if added.
- Do not override vendor classes directly; wrap with a custom class.

## JavaScript
- Avoid global functions. Use module scope and IIFE pattern if needed.
- Guard DOM queries with existence checks.
- No direct DOM mutation for HTMX-managed regions except post-swap enhancements.

## Accessibility
- Provide `aria-live="polite"` for dynamic status regions (task progress) and `role="status"` where appropriate.
- Forms: associate labels using `<label for>` or wrapping.
- Provide keyboard navigable structures; avoid click-only handlers.

## Security
- Escape all variables by default (Jinja autoescape on). If using `|safe`, justify and sanitize upstream.
- Avoid injecting raw JSON into script tags; use `|tojson` filter if needed.

## Template Inclusion
- Limit include depth to 3 levels to keep cognition manageable.
- Prefer macros for repeating pattern with variant logic.

## Comments
- Use `<!-- component:<name> -->` at start of significant partial root.
- ADR references: `<!-- decision:ADR-0003 -->` if implementation ties to a decision record.

## Lint / Validation (Future Automation)
- HTML validation via tidy or html5validator in CI.
- Stylelint for CSS (scoped with ignore for vendor).
- Simple custom script to flag duplicate component markup > N similarity.

## Example Snippet
```
<section id="analysis-progress" class="c-analysis-progress" data-component="analysis-progress" aria-live="polite">
  {% include 'ui/elements/dashboard/stats-cards.html' %}
</section>
```
