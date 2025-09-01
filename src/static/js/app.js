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

// Sidebar / layout responsive controller
ThesisApp.layout = (function(){
  const AUTO_COLLAPSE_BREAKPOINT = 1200;
  const MOBILE_BREAKPOINT = 992;
  const LS_KEY = 'sidebarPref';
  function getSidebar(){ return document.getElementById('sidebar'); }
  function getToggle(){ return document.getElementById('sidebar-toggle'); }
  function applyCollapsed(collapsed){
    const sb = getSidebar();
    if(!sb) return;
    sb.classList.toggle('collapsed', collapsed);
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    const t = getToggle();
    if(t){
      t.setAttribute('aria-expanded', (!collapsed).toString());
      t.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    }
  }
  function getPref(){ try{return localStorage.getItem(LS_KEY);}catch(_){return null;} }
  function setPref(v){ try{localStorage.setItem(LS_KEY, v);}catch(_){}}
  function autoDetermine(){
    const w = window.innerWidth;
    if(w < MOBILE_BREAKPOINT){ applyCollapsed(false); return; }
    const pref = getPref();
    if(pref === 'collapsed') return applyCollapsed(true);
    if(pref === 'expanded') return applyCollapsed(false);
    applyCollapsed(w < AUTO_COLLAPSE_BREAKPOINT);
  }
  function toggleUser(){
    const sb = getSidebar(); if(!sb) return;
    const next = !sb.classList.contains('collapsed');
    applyCollapsed(next); setPref(next ? 'collapsed':'expanded');
  }
  function onResize(){
    autoDetermine();
    if(window.innerWidth >= MOBILE_BREAKPOINT){
      const sb = getSidebar(); if(sb) sb.classList.remove('show');
    }
  }
  function init(){
    autoDetermine();
    const t = getToggle(); if(t){ t.addEventListener('click', e=>{ e.preventDefault(); toggleUser(); }); }
    window.addEventListener('resize', onResize);
  }
  document.addEventListener('DOMContentLoaded', init);
  return { init, toggleUser };
})();
