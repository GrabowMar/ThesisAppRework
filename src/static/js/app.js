// Minimal application JS stub for ThesisAppRework
// Provides small helpers and avoids 404s when templates include app.js
window.ThesisApp = window.ThesisApp || {};

// Safe htmx wrapper for older pages
ThesisApp.htmxAjax = function(method, url, target){
  if (window.htmx && typeof window.htmx.ajax === 'function'){
    try { window.htmx.ajax(method, url, target); } catch(e) { console.warn('htmx.ajax failed', e); }
  } else if (window.fetch){
    fetch(url, {method: method}).then(()=>{}).catch(()=>{});
  }
};

// Expose a no-op init for charts to be called from templates
ThesisApp.initDashboardChart = function(ctx){
  // templates may call this; Chart.js availability is optional
  if (!ctx || !window.Chart) return null;
  try{
    return new Chart(ctx, { type: 'line', data: { labels: [], datasets: [] }, options: { responsive: true, maintainAspectRatio: false } });
  }catch(e){ console.warn('Chart init failed', e); return null; }
};
