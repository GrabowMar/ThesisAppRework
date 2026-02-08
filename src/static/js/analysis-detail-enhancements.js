/**
 * Analysis Detail Page Enhancements
 * - Severity donut chart + per-service bar chart (Chart.js)
 * - Section jump nav with IntersectionObserver
 * - Expand/Collapse all accordion sections
 * - Copy to clipboard (Task ID, Share Link)
 */
(function () {
  'use strict';

  // ========== C3: Charts ==========
  function initCharts() {
    if (typeof Chart === 'undefined') return;

    const data = window.ANALYSIS_DATA;
    if (!data) return;

    // --- Severity Donut ---
    const donutCanvas = document.getElementById('severityDonutChart');
    if (donutCanvas) {
      const sev = (data.results && data.results.summary && data.results.summary.severity_breakdown) || {};
      const labels = [];
      const values = [];
      const colors = [];
      const colorMap = {
        critical: '#d63939',
        high: '#f76707',
        medium: '#f59f00',
        low: '#4299e1',
        info: '#adb5bd'
      };
      for (const [key, val] of Object.entries(sev)) {
        if (val && val > 0) {
          labels.push(key.charAt(0).toUpperCase() + key.slice(1));
          values.push(val);
          colors.push(colorMap[key] || '#adb5bd');
        }
      }
      if (values.length > 0) {
        new Chart(donutCanvas, {
          type: 'doughnut',
          data: {
            labels: labels,
            datasets: [{
              data: values,
              backgroundColor: colors,
              borderWidth: 1,
              borderColor: '#fff'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
              legend: { position: 'right', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } }
            }
          }
        });
      }
    }

    // --- Service Findings Bar Chart ---
    const barCanvas = document.getElementById('serviceBarChart');
    if (barCanvas) {
      const services = (data.results && data.results.services) || {};
      const svcLabels = [];
      const svcValues = [];
      const svcColors = [];
      const svcColorMap = {
        static: '#206bc4',
        dynamic: '#2fb344',
        performance: '#4299e1',
        ai: '#f76707'
      };

      for (const [key, svc] of Object.entries(services)) {
        if (!svc) continue;
        const label = key.charAt(0).toUpperCase() + key.slice(1);
        let count = 0;
        // Count findings from analysis results
        const analysis = svc.analysis || {};
        const results = analysis.results || analysis.tools || {};
        if (typeof results === 'object') {
          for (const [tk, tv] of Object.entries(results)) {
            if (tk.startsWith('_') || tk === 'tool_status' || tk === 'error') continue;
            if (tv && typeof tv === 'object') {
              // Count issues arrays or issue_count fields
              if (Array.isArray(tv.issues)) count += tv.issues.length;
              else if (typeof tv.issue_count === 'number') count += tv.issue_count;
              else if (typeof tv.total_issues === 'number') count += tv.total_issues;
              else if (tv.results && typeof tv.results === 'object') {
                for (const lang of Object.values(tv.results)) {
                  if (lang && typeof lang === 'object') {
                    for (const tool of Object.values(lang)) {
                      if (tool && Array.isArray(tool.issues)) count += tool.issues.length;
                    }
                  }
                }
              }
            }
          }
        }
        svcLabels.push(label);
        svcValues.push(count);
        svcColors.push(svcColorMap[key] || '#adb5bd');
      }

      if (svcLabels.length > 0) {
        new Chart(barCanvas, {
          type: 'bar',
          data: {
            labels: svcLabels,
            datasets: [{
              label: 'Findings',
              data: svcValues,
              backgroundColor: svcColors,
              borderRadius: 4,
              barThickness: 32
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
              legend: { display: false }
            },
            scales: {
              x: { beginAtZero: true, ticks: { stepSize: 1, font: { size: 11 } }, grid: { display: false } },
              y: { ticks: { font: { size: 12 } }, grid: { display: false } }
            }
          }
        });
      }
    }
  }

  // ========== D2: Section Jump Nav with IntersectionObserver ==========
  function initSectionNav() {
    const navLinks = document.querySelectorAll('.section-nav-link');
    const sections = [];
    navLinks.forEach(function (link) {
      const sectionId = link.getAttribute('data-section');
      const section = document.getElementById(sectionId);
      if (section) sections.push({ id: sectionId, el: section, link: link });
    });

    // Smooth scroll on click
    navLinks.forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        const sectionId = this.getAttribute('data-section');
        const target = document.getElementById(sectionId);
        if (!target) return;

        // Expand the accordion if collapsed
        const accordionItem = target.closest('.accordion-item');
        if (accordionItem) {
          const btn = accordionItem.querySelector('.accordion-button');
          if (btn && btn.classList.contains('collapsed')) btn.click();
        }

        // Scroll with offset for sticky nav
        const offset = 60;
        const top = target.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });

        // Update active state
        navLinks.forEach(function (l) { l.classList.remove('active'); });
        this.classList.add('active');
      });
    });

    // IntersectionObserver for active state tracking
    if ('IntersectionObserver' in window && sections.length > 0) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            navLinks.forEach(function (l) { l.classList.remove('active'); });
            var match = sections.find(function (s) { return s.id === entry.target.id; });
            if (match) match.link.classList.add('active');
          }
        });
      }, { rootMargin: '-80px 0px -60% 0px', threshold: 0 });

      sections.forEach(function (s) { observer.observe(s.el); });
    }

    // Make nav sticky on scroll
    var nav = document.getElementById('sectionJumpNav');
    if (nav) {
      var navTop = nav.offsetTop;
      window.addEventListener('scroll', function () {
        if (window.pageYOffset > navTop - 10) {
          nav.classList.add('sticky-active');
        } else {
          nav.classList.remove('sticky-active');
        }
      }, { passive: true });
    }
  }

  // ========== E2: Expand/Collapse All ==========
  function initToggleAll() {
    var btn = document.getElementById('toggleAllSections');
    if (!btn) return;
    var expanded = false;

    btn.addEventListener('click', function () {
      var accordion = document.getElementById('analysisAccordion');
      if (!accordion) return;

      var collapses = accordion.querySelectorAll('.accordion-collapse');
      expanded = !expanded;

      collapses.forEach(function (collapse) {
        var bsCollapse = bootstrap.Collapse.getOrCreateInstance(collapse, { toggle: false });
        if (expanded) {
          bsCollapse.show();
        } else {
          bsCollapse.hide();
        }
      });

      var icon = btn.querySelector('i');
      var text = btn.querySelector('span');
      if (expanded) {
        icon.className = 'fa-solid fa-angles-up me-1';
        text.textContent = 'Collapse All';
      } else {
        icon.className = 'fa-solid fa-angles-down me-1';
        text.textContent = 'Expand All';
      }
    });
  }

  // ========== F3: Copy to Clipboard ==========
  function initCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var text = this.getAttribute('data-copy');
        if (!text) return;
        navigator.clipboard.writeText(text).then(function () {
          var toastEl = document.getElementById('copyToast');
          if (toastEl) {
            var toast = bootstrap.Toast.getOrCreateInstance(toastEl);
            toast.show();
          }
        }).catch(function () {
          // Fallback for older browsers
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        });
      });
    });
  }

  // ========== Init on DOM ready ==========
  function init() {
    initCharts();
    initSectionNav();
    initToggleAll();
    initCopyButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
