// Lean application JS for ThesisAppRework
// Goal: minimise bespoke JS now that htmx + hyperscript + Tabler/Bootstrap handle
// most dynamic behaviour. Keep public API surface for templates while internally
// delegating to simple, small helpers. (Safe to remove more after template audit.)

window.ThesisApp = window.ThesisApp || {};

// 1. Very small htmx wrapper (legacy templates may still call it)
ThesisApp.htmxAjax = function(method, url, target){
  if (window.htmx?.ajax){
    try { window.htmx.ajax(method, url, target); } catch(e){ console.warn('htmxAjax failed', e); }
  } else if (window.fetch){ fetch(url, { method }).catch(()=>{}); }
};

// 2. Chart helper kept as a light progressive enhancement; returns null if missing
ThesisApp.initDashboardChart = function(ctx){
  if(!ctx || !window.Chart) return null;
  try { return new Chart(ctx, { type:'line', data:{labels:[],datasets:[]}, options:{responsive:true,maintainAspectRatio:false}}); }
  catch(e){ console.warn('Chart init failed', e); return null; }
};

// 3. Sidebar / navigation minimal controller
// Instead of re‑binding listeners after every htmx swap we rely on:
//  - data-action attributes (delegated click)
//  - a single resize listener
//  - simple localStorage flag for user preference
ThesisApp.layout = (function(){
  const LS_KEY = 'sidebarPref';
  const MOBILE_BP = 992; // match bootstrap md/lg break
  const AUTO_COLLAPSE_BP = 1200;

  function qs(id){ return document.getElementById(id); }
  function pref(v){ try { if(v===undefined) return localStorage.getItem(LS_KEY); localStorage.setItem(LS_KEY, v); } catch(_){} }
  function sidebar(){ return qs('sidebar'); }

  function apply(collapsed){
    const sb = sidebar();
    if(!sb) return;
    sb.classList.toggle('collapsed', collapsed);
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    const t = qs('sidebar-toggle');
    if(t){
      t.setAttribute('aria-expanded', (!collapsed).toString());
      t.setAttribute('aria-label', collapsed? 'Expand sidebar':'Collapse sidebar');
    }
  }

  function auto(){
    const w = window.innerWidth;
    if(w < MOBILE_BP){ apply(false); return; }
    const p = pref();
    if(p === 'collapsed') return apply(true);
    if(p === 'expanded') return apply(false);
    apply(w < AUTO_COLLAPSE_BP);
  }

  function toggle(){
    const sb = sidebar();
    if(!sb) return;
    const next = !sb.classList.contains('collapsed');
    apply(next);
    pref(next? 'collapsed':'expanded');
  }

  function markActive(){
    try{
      const path = window.location.pathname.replace(/\/$/, '');
      const primary = path.split('/').filter(Boolean)[0] || 'dashboard';
      document.querySelectorAll('.sidebar .nav-link[data-nav-target]').forEach(a => {
        const target = a.getAttribute('data-nav-target');
        a.classList.toggle('active', target === primary);
      });
    }catch(e){ console.debug('nav highlight failed', e); }
  }

  // Event delegation: any element with data-action="toggle-sidebar"
  function delegateClicks(e){
    const act = e.target.closest('[data-action="toggle-sidebar"]');
    if(act){ e.preventDefault(); toggle(); }
  }

  function init(){
    auto();
    markActive();
  }

  // Initialisation
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  window.addEventListener('click', delegateClicks);
  window.addEventListener('resize', auto);

  // htmx integration: after any swap re-mark active (no expensive rebinds)
  document.body.addEventListener('htmx:afterSettle', markActive);

  return { init, toggleUser: toggle, updateActiveNavLink: markActive, autoDetermine: auto };
})();

// 4. Convenience reinitialise alias kept for backwards compatibility
ThesisApp.layout.reinitialize = ThesisApp.layout.init;

// Soft deprecation notice (only once)
if(!window.__APP_JS_DEPRECATION){
  window.__APP_JS_DEPRECATION = true;
  console.info('[ThesisApp] app.js trimmed. Prefer hyperscript/htmx attributes over manual JS.');
}
