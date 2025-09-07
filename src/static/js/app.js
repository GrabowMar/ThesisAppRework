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
  function getMobileToggle(){ return document.getElementById('mobile-sidebar-toggle'); }
  
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
  
  function getPref(){ 
    try{ return localStorage.getItem(LS_KEY); }
    catch(_){ return null; }
  }
  
  function setPref(v){ 
    try{ localStorage.setItem(LS_KEY, v); }
    catch(_){}
  }
  
  function autoDetermine(){
    const w = window.innerWidth;
    if(w < MOBILE_BREAKPOINT){ 
      applyCollapsed(false); 
      return; 
    }
    const pref = getPref();
    if(pref === 'collapsed') return applyCollapsed(true);
    if(pref === 'expanded') return applyCollapsed(false);
    applyCollapsed(w < AUTO_COLLAPSE_BREAKPOINT);
  }
  
  function toggleUser(){
    const sb = getSidebar(); 
    if(!sb) return;
    const next = !sb.classList.contains('collapsed');
    applyCollapsed(next); 
    setPref(next ? 'collapsed':'expanded');
  }
  
  function onResize(){
    autoDetermine();
    if(window.innerWidth >= MOBILE_BREAKPOINT){
      const sb = getSidebar(); 
      if(sb) sb.classList.remove('show');
      // Close mobile sidebar offcanvas if open
      const mobileOffcanvas = document.getElementById('mobile-sidebar');
      if(mobileOffcanvas && window.bootstrap){
        const bsOffcanvas = bootstrap.Offcanvas.getInstance(mobileOffcanvas);
        if(bsOffcanvas) bsOffcanvas.hide();
      }
    }
  }
  
  function updateActiveNavLink(){
    try{
      const path = window.location.pathname;
      // Clear all active states first
      document.querySelectorAll('.sidebar .nav-link, .offcanvas .nav-link').forEach(a => {
        a.classList.remove('active');
      });
      
      // Set active state using stricter segment-based matching to avoid spurious matches
      const segments = path.split('/').filter(Boolean); // e.g. /analysis/tasks -> ['analysis','tasks']
      document.querySelectorAll('.sidebar .nav-link[data-nav-target], .offcanvas .nav-link[data-nav-target]').forEach(a => {
        const href = a.getAttribute('href') || '';
        const target = a.getAttribute('data-nav-target');
        if(!target) return;
        // Determine primary segment for current path
        const primary = segments[0] || 'dashboard';
        // Normalize href (ignore trailing slash)
        const normHref = href.replace(/\/$/, '');
        const normPath = path.replace(/\/$/, '');
        const hrefPrimary = normHref.split('/').filter(Boolean)[0] || 'dashboard';
        const isMatch = (primary === target) || (hrefPrimary === primary && target === primary);
        if(isMatch){ a.classList.add('active'); }
      });
    }catch(e){
      console.warn('Active nav update failed:', e);
    }
  }
  
  function setupEventListeners(){
    // Desktop sidebar toggle
    const toggle = getToggle();
    if(toggle){
      // Remove any existing listeners to prevent duplicates
      toggle.replaceWith(toggle.cloneNode(true));
      const newToggle = getToggle();
      newToggle.addEventListener('click', e => {
        e.preventDefault();
        toggleUser();
      });
    }
    
    // Mobile toggle (already handled by Bootstrap offcanvas)
    const mobileToggle = getMobileToggle();
    if(mobileToggle){
      // Ensure proper ARIA attributes
      mobileToggle.setAttribute('aria-expanded', 'false');
    }
  }
  
  function init(){
    console.log('Initializing sidebar layout...');
    autoDetermine();
    setupEventListeners();
    updateActiveNavLink();
    
    // Listen for window resize
    window.addEventListener('resize', onResize);
    
    // HTMX event handlers for robust reinitialization
    if(window.htmx){
      // After any HTMX content swap/settlement
      document.body.addEventListener('htmx:afterSettle', function(evt){
        console.log('HTMX content settled, reinitializing sidebar...');
        // Small delay to ensure DOM is fully updated
        setTimeout(() => {
          autoDetermine();
          setupEventListeners();
          updateActiveNavLink();
        }, 50);
      });
      
      // Before HTMX swap to preserve state
      document.body.addEventListener('htmx:beforeSwap', function(evt){
        // Store current sidebar state
        const sb = getSidebar();
        if(sb && sb.classList.contains('collapsed')){
          setPref('collapsed');
        }
      });
    }
  }
  
  // Also reinitialize on DOM content changes (for dynamic content)
  function reinitialize(){
    console.log('Reinitializing sidebar...');
    init();
  }
  
  // Initialize on DOM ready
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  return { 
    init, 
    reinitialize,
    toggleUser, 
    updateActiveNavLink,
    autoDetermine
  };
})();
