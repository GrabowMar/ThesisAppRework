/**
 * Reusable UI Components
 * Modular components for common interface patterns
 */

class DataTable {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      sortable: true,
      filterable: true,
      pagination: true,
      pageSize: 25,
      stickyHeader: true,
      ...options
    };
    this.init();
  }

  init() {
    if (this.options.stickyHeader) {
      this.element.querySelector('thead').style.position = 'sticky';
      this.element.querySelector('thead').style.top = '0';
      this.element.querySelector('thead').style.zIndex = '10';
    }

    if (this.options.sortable) {
      this.initSorting();
    }

    if (this.options.filterable) {
      this.initFiltering();
    }
  }

  initSorting() {
    const headers = this.element.querySelectorAll('th[data-sortable]');
    headers.forEach(header => {
      header.style.cursor = 'pointer';
      header.innerHTML += ' <i class="fas fa-sort text-muted ms-1"></i>';
      
      header.addEventListener('click', () => {
        const column = header.dataset.sortable;
        const direction = header.dataset.sortDir === 'asc' ? 'desc' : 'asc';
        this.sortTable(column, direction);
        
        // Update UI
        headers.forEach(h => {
          h.dataset.sortDir = '';
          h.querySelector('i').className = 'fas fa-sort text-muted ms-1';
        });
        header.dataset.sortDir = direction;
        header.querySelector('i').className = `fas fa-sort-${direction === 'asc' ? 'up' : 'down'} text-primary ms-1`;
      });
    });
  }

  sortTable(column, direction) {
    const tbody = this.element.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
      const aVal = a.querySelector(`[data-sort-value="${column}"]`)?.textContent.trim() || 
                   a.cells[this.getColumnIndex(column)]?.textContent.trim() || '';
      const bVal = b.querySelector(`[data-sort-value="${column}"]`)?.textContent.trim() || 
                   b.cells[this.getColumnIndex(column)]?.textContent.trim() || '';
      
      const result = isNaN(aVal) ? aVal.localeCompare(bVal) : parseFloat(aVal) - parseFloat(bVal);
      return direction === 'asc' ? result : -result;
    });

    rows.forEach(row => tbody.appendChild(row));
  }

  getColumnIndex(columnName) {
    const headers = Array.from(this.element.querySelectorAll('th'));
    return headers.findIndex(h => h.dataset.sortable === columnName);
  }

  initFiltering() {
    // Create search input if not exists
    let searchContainer = document.querySelector('.table-search');
    if (!searchContainer) {
      searchContainer = document.createElement('div');
      searchContainer.className = 'table-search mb-3';
      searchContainer.innerHTML = `
        <div class="input-group">
          <input type="search" class="form-control" placeholder="Search table..." id="table-search-${Date.now()}">
          <button class="btn btn-outline-secondary" type="button" onclick="this.previousElementSibling.value=''; this.previousElementSibling.dispatchEvent(new Event('input'))">
            <i class="fas fa-times"></i>
          </button>
        </div>
      `;
      this.element.parentElement.insertBefore(searchContainer, this.element);
    }

    const searchInput = searchContainer.querySelector('input');
    searchInput.addEventListener('input', window.appCore.debounce((e) => {
      this.filterTable(e.target.value);
    }, 300));
  }

  filterTable(searchTerm) {
    const rows = this.element.querySelectorAll('tbody tr');
    const term = searchTerm.toLowerCase();

    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(term) ? '' : 'none';
    });

    // Update row count if exists
    const countElement = document.querySelector('.table-row-count');
    if (countElement) {
      const visibleRows = Array.from(rows).filter(row => row.style.display !== 'none').length;
      countElement.textContent = `${visibleRows} of ${rows.length} rows`;
    }
  }
}

class ProgressTracker {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      animated: true,
      showPercentage: true,
      color: 'primary',
      ...options
    };
    this.init();
  }

  init() {
    this.element.innerHTML = `
      <div class="progress mb-1" style="height: 8px;">
        <div class="progress-bar bg-${this.options.color} ${this.options.animated ? 'progress-bar-animated' : ''}" 
             role="progressbar" style="width: 0%"></div>
      </div>
      ${this.options.showPercentage ? '<small class="text-muted">0%</small>' : ''}
    `;
    this.progressBar = this.element.querySelector('.progress-bar');
    this.percentageText = this.element.querySelector('small');
  }

  setProgress(percentage) {
    percentage = Math.max(0, Math.min(100, percentage));
    this.progressBar.style.width = `${percentage}%`;
    this.progressBar.setAttribute('aria-valuenow', percentage);
    
    if (this.percentageText) {
      this.percentageText.textContent = `${Math.round(percentage)}%`;
    }

    // Change color based on progress
    if (percentage >= 100) {
      this.progressBar.className = this.progressBar.className.replace(/bg-\w+/, 'bg-success');
    } else if (percentage >= 75) {
      this.progressBar.className = this.progressBar.className.replace(/bg-\w+/, 'bg-info');
    }
  }

  setStatus(status, message) {
    const statusColors = {
      success: 'success',
      error: 'danger',
      warning: 'warning',
      info: 'info'
    };

    this.progressBar.className = this.progressBar.className.replace(/bg-\w+/, `bg-${statusColors[status] || 'primary'}`);
    
    if (message && this.percentageText) {
      this.percentageText.textContent = message;
    }
  }
}

class StatusIndicator {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      showText: true,
      blinking: false,
      ...options
    };
    this.init();
  }

  init() {
    this.element.classList.add('status-indicator');
    if (this.options.blinking) {
      this.element.classList.add('status-blinking');
    }
  }

  setStatus(status, text) {
    const statusConfig = {
      online: { class: 'status-success', icon: 'fas fa-circle', color: 'success' },
      offline: { class: 'status-danger', icon: 'fas fa-circle', color: 'danger' },
      warning: { class: 'status-warning', icon: 'fas fa-exclamation-circle', color: 'warning' },
      loading: { class: 'status-info', icon: 'fas fa-spinner fa-spin', color: 'info' },
      idle: { class: 'status-secondary', icon: 'fas fa-pause', color: 'secondary' }
    };

    const config = statusConfig[status] || statusConfig.offline;
    
    // Remove existing status classes
    this.element.className = this.element.className.replace(/status-\w+/g, '');
    this.element.classList.add(config.class);

    this.element.innerHTML = `
      <i class="${config.icon}"></i>
      ${this.options.showText && text ? `<span class="ms-1">${text}</span>` : ''}
    `;
  }
}

class CodeViewer {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      language: 'javascript',
      theme: 'dark',
      lineNumbers: true,
      copyButton: true,
      maxHeight: '400px',
      ...options
    };
    this.init();
  }

  init() {
    this.element.classList.add('code-viewer');
    this.element.style.maxHeight = this.options.maxHeight;
    this.element.style.overflow = 'auto';

    if (this.options.copyButton) {
      this.addCopyButton();
    }

    this.highlightCode();
  }

  addCopyButton() {
    const button = document.createElement('button');
    button.className = 'btn btn-sm btn-outline-secondary position-absolute top-0 end-0 m-2';
    button.innerHTML = '<i class="fas fa-copy"></i>';
    button.style.zIndex = '10';
    
    button.addEventListener('click', () => {
      window.App.copyToClipboard(this.element.textContent);
      button.innerHTML = '<i class="fas fa-check text-success"></i>';
      setTimeout(() => {
        button.innerHTML = '<i class="fas fa-copy"></i>';
      }, 2000);
    });

    this.element.style.position = 'relative';
    this.element.appendChild(button);
  }

  highlightCode() {
    // Basic syntax highlighting (can be enhanced with Prism.js or highlight.js)
    if (this.options.language === 'json') {
      this.highlightJSON();
    } else if (this.options.language === 'javascript') {
      this.highlightJavaScript();
    }
  }

  highlightJSON() {
    try {
      const content = this.element.textContent;
      const json = JSON.parse(content);
      const formatted = JSON.stringify(json, null, 2);
      
      this.element.innerHTML = `<pre><code>${this.escapeHtml(formatted)}</code></pre>`;
    } catch (e) {
      console.warn('Invalid JSON for highlighting');
    }
  }

  highlightJavaScript() {
    const content = this.element.textContent;
    // Basic keyword highlighting
    const highlighted = content
      .replace(/\b(function|const|let|var|if|else|for|while|return|class|import|export)\b/g, '<span class="text-primary fw-bold">$1</span>')
      .replace(/('.*?'|".*?")/g, '<span class="text-success">$1</span>')
      .replace(/(\/\/.*$)/gm, '<span class="text-muted">$1</span>');
    
    this.element.innerHTML = `<pre><code>${highlighted}</code></pre>`;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Auto-initialization for data attributes
document.addEventListener('DOMContentLoaded', () => {
  // Auto-init data tables
  document.querySelectorAll('[data-table]').forEach(table => {
    new DataTable(table, JSON.parse(table.dataset.table || '{}'));
  });

  // Auto-init progress trackers
  document.querySelectorAll('[data-progress]').forEach(element => {
    new ProgressTracker(element, JSON.parse(element.dataset.progress || '{}'));
  });

  // Auto-init status indicators
  document.querySelectorAll('[data-status]').forEach(element => {
    const indicator = new StatusIndicator(element, JSON.parse(element.dataset.statusOptions || '{}'));
    indicator.setStatus(element.dataset.status, element.dataset.statusText);
  });

  // Auto-init code viewers
  document.querySelectorAll('[data-code-viewer]').forEach(element => {
    new CodeViewer(element, JSON.parse(element.dataset.codeViewer || '{}'));
  });
});

// Export for manual initialization (defensive)
if (typeof window.Components === 'undefined') {
  window.Components = {
    DataTable,
    ProgressTracker,
    StatusIndicator,
    CodeViewer
  };
}