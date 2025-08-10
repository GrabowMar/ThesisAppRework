/**
 * Dynamic Styles Handler
 * Applies CSS values that were moved from inline styles to data attributes
 */

// Apply dynamic widths from data-width attributes
function applyDynamicWidths() {
    const elements = document.querySelectorAll('.dynamic-width[data-width]');
    elements.forEach(el => {
        const width = el.getAttribute('data-width');
        if (width) {
            el.style.width = width;
        }
    });
}

// Apply dynamic left padding from --level CSS custom property
function applyFileTreePadding() {
    const elements = document.querySelectorAll('.file-tree-item[style*="--level"]');
    elements.forEach(el => {
        const level = el.style.getPropertyValue('--level') || 0;
        const padding = (parseInt(level) * 20 + 15) + 'px';
        el.style.paddingLeft = padding;
    });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    applyDynamicWidths();
    applyFileTreePadding();
});

// Re-apply when HTMX content is swapped
document.body.addEventListener('htmx:afterSettle', function() {
    applyDynamicWidths();
    applyFileTreePadding();
});

// Export functions for manual calls if needed
window.dynamicStyles = {
    applyDynamicWidths,
    applyFileTreePadding
};
