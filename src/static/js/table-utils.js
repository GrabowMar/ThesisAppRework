/**
 * Shared Table Utilities
 * =======================
 * Reusable components for all data tables in the application
 * Provides: sorting, filtering, debouncing, export functionality
 * 
 * Design: Framework-agnostic, works with HTMX or client-side rendering
 */

(function(window) {
  'use strict';

  // Prevent multiple initialization
  if (window.__TABLE_UTILS_LOADED__) {
    console.debug('table-utils.js already loaded – skipping re-init');
    return;
  }
  window.__TABLE_UTILS_LOADED__ = true;

  // ========================================
  // Debounce Utility
  // ========================================
  
  /**
   * Generic debounce function for input fields
   * @param {Function} func - Function to debounce
   * @param {number} delay - Delay in milliseconds (default: 300)
   * @returns {Function} Debounced function
   */
  function debounce(func, delay = 300) {
    let timeoutId;
    return function(...args) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
  }

  // ========================================
  // Table Sorting
  // ========================================

  /**
   * TableSorter class for client-side sorting
   * Usage: const sorter = new TableSorter('my-table-id');
   */
  class TableSorter {
    constructor(tableId, options = {}) {
      this.table = document.getElementById(tableId);
      if (!this.table) {
        console.warn(`TableSorter: table #${tableId} not found`);
        return;
      }

      this.options = {
        sortableClass: 'sortable',
        ascIcon: 'ti ti-arrow-up',
        descIcon: 'ti ti-arrow-down',
        neutralIcon: 'ti ti-arrows-sort',
        onSort: null, // Callback: (column, direction) => {}
        persistKey: null, // localStorage key for persistence
        ...options
      };

      this.currentSort = { column: null, direction: 'asc' };
      this.init();
    }

    init() {
      const headers = this.table.querySelectorAll(`th.${this.options.sortableClass}`);
      headers.forEach(header => {
        header.style.cursor = 'pointer';
        header.classList.add('sortable-header');
        
        // Add sort icon container
        if (!header.querySelector('.sort-icon')) {
          const icon = document.createElement('i');
          icon.className = `sort-icon ${this.options.neutralIcon} ms-1`;
          icon.style.fontSize = '0.875rem';
          icon.setAttribute('aria-hidden', 'true');
          header.appendChild(icon);
        }

        header.addEventListener('click', () => this.handleSort(header));
      });

      // Restore sort state from localStorage
      if (this.options.persistKey) {
        this.restoreSortState();
      }
    }

    handleSort(header) {
      const column = header.dataset.column;
      if (!column) return;

      // Toggle direction if same column, else default to asc
      if (this.currentSort.column === column) {
        this.currentSort.direction = this.currentSort.direction === 'asc' ? 'desc' : 'asc';
      } else {
        this.currentSort.column = column;
        this.currentSort.direction = 'asc';
      }

      this.updateSortIndicators();
      
      // Persist state
      if (this.options.persistKey) {
        localStorage.setItem(this.options.persistKey, JSON.stringify(this.currentSort));
      }

      // Trigger callback (for HTMX or API calls)
      if (typeof this.options.onSort === 'function') {
        this.options.onSort(this.currentSort.column, this.currentSort.direction);
      } else {
        // Default: client-side sort
        this.sortTableRows();
      }
    }

    updateSortIndicators() {
      const headers = this.table.querySelectorAll(`th.${this.options.sortableClass}`);
      headers.forEach(header => {
        const icon = header.querySelector('.sort-icon');
        if (!icon) return;

        const column = header.dataset.column;
        if (column === this.currentSort.column) {
          icon.className = `sort-icon ${this.currentSort.direction === 'asc' ? this.options.ascIcon : this.options.descIcon} ms-1`;
          header.classList.add('sorted');
        } else {
          icon.className = `sort-icon ${this.options.neutralIcon} ms-1`;
          header.classList.remove('sorted');
        }
      });
    }

    sortTableRows() {
      const tbody = this.table.querySelector('tbody');
      if (!tbody) return;

      const rows = Array.from(tbody.querySelectorAll('tr'));
      const columnIndex = this.getColumnIndex(this.currentSort.column);
      if (columnIndex === -1) return;

      rows.sort((a, b) => {
        const aCell = a.cells[columnIndex];
        const bCell = b.cells[columnIndex];
        if (!aCell || !bCell) return 0;

        // Use data-sort-value if available, else text content
        const aValue = aCell.dataset.sortValue || aCell.textContent.trim();
        const bValue = bCell.dataset.sortValue || bCell.textContent.trim();

        // Detect numeric values
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
          return this.currentSort.direction === 'asc' ? aNum - bNum : bNum - aNum;
        }

        // String comparison
        const comparison = aValue.localeCompare(bValue, undefined, { numeric: true, sensitivity: 'base' });
        return this.currentSort.direction === 'asc' ? comparison : -comparison;
      });

      // Re-append sorted rows
      rows.forEach(row => tbody.appendChild(row));
    }

    getColumnIndex(columnName) {
      const headers = this.table.querySelectorAll('th');
      for (let i = 0; i < headers.length; i++) {
        if (headers[i].dataset.column === columnName) {
          return i;
        }
      }
      return -1;
    }

    restoreSortState() {
      try {
        const saved = localStorage.getItem(this.options.persistKey);
        if (saved) {
          this.currentSort = JSON.parse(saved);
          this.updateSortIndicators();
          if (!this.options.onSort) {
            this.sortTableRows();
          }
        }
      } catch (e) {
        console.warn('Failed to restore sort state:', e);
      }
    }

    reset() {
      this.currentSort = { column: null, direction: 'asc' };
      this.updateSortIndicators();
      if (this.options.persistKey) {
        localStorage.removeItem(this.options.persistKey);
      }
    }
  }

  // ========================================
  // Advanced Filter Panel
  // ========================================

  /**
   * AdvancedFilterPanel class for collapsible filter UI
   * Usage: const panel = new AdvancedFilterPanel('filter-panel-id');
   */
  class AdvancedFilterPanel {
    constructor(panelId, options = {}) {
      this.panel = document.getElementById(panelId);
      if (!this.panel) {
        console.warn(`AdvancedFilterPanel: panel #${panelId} not found`);
        return;
      }

      this.options = {
        toggleButtonId: null,
        badgeId: 'active-filters-count',
        onFilterChange: null, // Callback when filters change
        persistKey: null, // localStorage key
        ...options
      };

      this.activeFiltersCount = 0;
      this.init();
    }

    init() {
      // Set up toggle button
      if (this.options.toggleButtonId) {
        const toggleBtn = document.getElementById(this.options.toggleButtonId);
        if (toggleBtn) {
          toggleBtn.addEventListener('click', () => this.toggle());
        }
      }

      // Monitor all filter inputs
      const inputs = this.panel.querySelectorAll('input, select');
      inputs.forEach(input => {
        input.addEventListener('change', () => {
          this.updateActiveCount();
          if (typeof this.options.onFilterChange === 'function') {
            this.options.onFilterChange();
          }
        });
      });

      // Initial count
      this.updateActiveCount();

      // Restore state
      if (this.options.persistKey) {
        this.restoreState();
      }
    }

    toggle() {
      const isHidden = this.panel.style.display === 'none' || !this.panel.style.display;
      this.panel.style.display = isHidden ? 'block' : 'none';
      
      // Animate
      if (isHidden) {
        this.panel.style.opacity = '0';
        this.panel.style.transform = 'translateY(-10px)';
        setTimeout(() => {
          this.panel.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
          this.panel.style.opacity = '1';
          this.panel.style.transform = 'translateY(0)';
        }, 10);
      }
    }

    show() {
      this.panel.style.display = 'block';
    }

    hide() {
      this.panel.style.display = 'none';
    }

    updateActiveCount() {
      const inputs = this.panel.querySelectorAll('input, select');
      let count = 0;

      inputs.forEach(input => {
        if (input.type === 'checkbox' && input.checked) {
          count++;
        } else if (input.type === 'text' && input.value.trim()) {
          count++;
        } else if (input.tagName === 'SELECT' && input.value && input.value !== '') {
          count++;
        }
      });

      this.activeFiltersCount = count;
      
      // Update badge
      const badge = document.getElementById(this.options.badgeId);
      if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? 'inline-block' : 'none';
      }
    }

    clear() {
      const inputs = this.panel.querySelectorAll('input, select');
      inputs.forEach(input => {
        if (input.type === 'checkbox') {
          input.checked = false;
        } else if (input.type === 'text') {
          input.value = '';
        } else if (input.tagName === 'SELECT') {
          input.selectedIndex = 0;
        }
      });
      this.updateActiveCount();
    }

    getValues() {
      const values = {};
      const inputs = this.panel.querySelectorAll('input, select');
      
      inputs.forEach(input => {
        const name = input.name || input.id;
        if (!name) return;

        if (input.type === 'checkbox') {
          if (input.checked) {
            if (!values[name]) values[name] = [];
            values[name].push(input.value);
          }
        } else if (input.value && input.value.trim()) {
          values[name] = input.value.trim();
        }
      });

      return values;
    }

    restoreState() {
      try {
        const saved = localStorage.getItem(this.options.persistKey);
        if (saved) {
          const values = JSON.parse(saved);
          Object.keys(values).forEach(key => {
            const input = this.panel.querySelector(`[name="${key}"], #${key}`);
            if (input) {
              if (input.type === 'checkbox') {
                input.checked = values[key];
              } else {
                input.value = values[key];
              }
            }
          });
          this.updateActiveCount();
        }
      } catch (e) {
        console.warn('Failed to restore filter state:', e);
      }
    }

    saveState() {
      if (this.options.persistKey) {
        localStorage.setItem(this.options.persistKey, JSON.stringify(this.getValues()));
      }
    }
  }

  // ========================================
  // Export Functionality
  // ========================================

  /**
   * Export table data to various formats
   * @param {string} endpoint - API endpoint for export
   * @param {string} format - Export format: 'json', 'csv', 'excel'
   * @param {Object} filters - Current filter values
   */
  function exportTable(endpoint, format, filters = {}) {
    const params = new URLSearchParams({ format, ...filters });
    const url = `${endpoint}?${params.toString()}`;

    // Create temporary link for download
    const link = document.createElement('a');
    link.href = url;
    link.download = `export_${format}_${Date.now()}.${format}`;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Show toast notification
    if (typeof window.showToast === 'function') {
      window.showToast(`Exporting data as ${format.toUpperCase()}...`, 'info');
    }
  }

  // ========================================
  // Bulk Selection Manager
  // ========================================

  /**
   * BulkSelectionManager for checkbox selection in tables
   * Usage: const bulkSelector = new BulkSelectionManager('table-id', 'master-checkbox-id');
   */
  class BulkSelectionManager {
    constructor(tableId, masterCheckboxId, options = {}) {
      this.table = document.getElementById(tableId);
      this.masterCheckbox = document.getElementById(masterCheckboxId);
      
      if (!this.table) {
        console.warn(`BulkSelectionManager: table #${tableId} not found`);
        return;
      }

      this.options = {
        rowCheckboxClass: 'row-checkbox',
        selectionIndicatorId: null,
        onSelectionChange: null, // Callback: (selectedIds) => {}
        ...options
      };

      this.selectedIds = [];
      this.init();
    }

    init() {
      // Master checkbox toggle all
      if (this.masterCheckbox) {
        this.masterCheckbox.addEventListener('change', () => this.toggleAll());
      }

      // Monitor individual checkboxes
      this.updateCheckboxListeners();
      this.updateSelectionState();
    }

    updateCheckboxListeners() {
      const checkboxes = this.table.querySelectorAll(`.${this.options.rowCheckboxClass}`);
      checkboxes.forEach(cb => {
        cb.removeEventListener('change', this.handleCheckboxChange); // Prevent duplicates
        cb.addEventListener('change', () => this.handleCheckboxChange());
      });
    }

    handleCheckboxChange() {
      this.updateSelectionState();
      
      if (typeof this.options.onSelectionChange === 'function') {
        this.options.onSelectionChange(this.getSelectedIds());
      }
    }

    toggleAll() {
      const checked = this.masterCheckbox.checked;
      const checkboxes = this.table.querySelectorAll(`.${this.options.rowCheckboxClass}`);
      
      checkboxes.forEach(cb => {
        cb.checked = checked;
      });

      this.updateSelectionState();
      
      if (typeof this.options.onSelectionChange === 'function') {
        this.options.onSelectionChange(this.getSelectedIds());
      }
    }

    updateSelectionState() {
      const checkboxes = Array.from(this.table.querySelectorAll(`.${this.options.rowCheckboxClass}`));
      const checkedCount = checkboxes.filter(cb => cb.checked).length;
      
      this.selectedIds = this.getSelectedIds();

      // Update master checkbox state
      if (this.masterCheckbox) {
        this.masterCheckbox.checked = checkedCount > 0 && checkedCount === checkboxes.length;
        this.masterCheckbox.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
      }

      // Update selection indicator
      if (this.options.selectionIndicatorId) {
        const indicator = document.getElementById(this.options.selectionIndicatorId);
        if (indicator) {
          indicator.textContent = checkedCount > 0 ? `${checkedCount} selected` : '';
          indicator.style.display = checkedCount > 0 ? 'inline-block' : 'none';
        }
      }
    }

    getSelectedIds() {
      const checkboxes = this.table.querySelectorAll(`.${this.options.rowCheckboxClass}:checked`);
      return Array.from(checkboxes).map(cb => cb.value).filter(Boolean);
    }

    clearSelection() {
      const checkboxes = this.table.querySelectorAll(`.${this.options.rowCheckboxClass}`);
      checkboxes.forEach(cb => { cb.checked = false; });
      
      if (this.masterCheckbox) {
        this.masterCheckbox.checked = false;
        this.masterCheckbox.indeterminate = false;
      }

      this.updateSelectionState();
    }

    selectAll() {
      if (this.masterCheckbox) {
        this.masterCheckbox.checked = true;
        this.toggleAll();
      }
    }
  }

  // ========================================
  // Loading States
  // ========================================

  /**
   * Show loading skeleton/spinner for table
   * @param {string} tableId - Table element ID
   * @param {boolean} show - Show or hide loading state
   */
  function setTableLoading(tableId, show = true) {
    const table = document.getElementById(tableId);
    if (!table) return;

    if (show) {
      table.classList.add('loading');
      table.style.opacity = '0.6';
      table.style.pointerEvents = 'none';
    } else {
      table.classList.remove('loading');
      table.style.opacity = '1';
      table.style.pointerEvents = 'auto';
    }
  }

  // ========================================
  // Export Public API
  // ========================================

  window.TableUtils = {
    debounce,
    TableSorter,
    AdvancedFilterPanel,
    BulkSelectionManager,
    exportTable,
    setTableLoading
  };

  console.debug('TableUtils initialized:', Object.keys(window.TableUtils));

})(window);
