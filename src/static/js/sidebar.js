// ThesisSidebar: robust, idempotent sidebar controller with persistence & HTMX resilience
(function(){
  if(window.ThesisSidebar && window.ThesisSidebar.__v){ return; }
  var LS_KEY = 'sidebarPref';
  var MOBILE_BP = 992; // < lg
  var AUTO_COLLAPSE_BP = 1200; // auto collapse threshold for large but not huge screens
  var INIT_DONE = false;

  function getSidebar(){ return document.getElementById('sidebar'); }
  function getToggle(){ return document.getElementById('sidebar-toggle'); }
  function readPref(){ try { return localStorage.getItem(LS_KEY); } catch(_){ return null; } }
  function writePref(v){ try { localStorage.setItem(LS_KEY, v); } catch(_){} }

  function apply(collapsed){
    var sb = getSidebar(); if(!sb) return;
    var isCollapsed = sb.classList.contains('collapsed');
    if(isCollapsed === collapsed) return; // idempotent
    sb.classList.toggle('collapsed', collapsed);
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    var t = getToggle();
    if(t){
      t.setAttribute('aria-expanded', (!collapsed).toString());
      t.setAttribute('aria-label', collapsed? 'Expand sidebar':'Collapse sidebar');
    }
    document.dispatchEvent(new CustomEvent('sidebar:changed', {detail:{collapsed:collapsed}}));
  }

  function auto(){
    var w = window.innerWidth;
    if(w < MOBILE_BP){ // always expanded in true mobile view (offcanvas handles hiding)
      apply(false); return;
    }
    var pref = readPref();
    if(pref === 'collapsed'){ apply(true); return; }
    if(pref === 'expanded'){ apply(false); return; }
    apply(w < AUTO_COLLAPSE_BP);
  }

  function toggle(){
    var sb = getSidebar(); if(!sb) return;
    var next = !sb.classList.contains('collapsed');
    apply(next);
    writePref(next? 'collapsed':'expanded');
  }

  function highlight(){
    try {
      var path = window.location.pathname.replace(/\/$/, '');
      var primary = path.split('/').filter(Boolean)[0] || 'dashboard';
      document.querySelectorAll('.sidebar .nav-link[data-nav-target]').forEach(function(a){
        var target = a.getAttribute('data-nav-target');
        a.classList.toggle('active', target === primary);
      });
    } catch(e){ /* silent */ }
  }

  function reapplyPersisted(){
    var pref = readPref();
    if(pref === 'collapsed'){ apply(true); }
    else if(pref === 'expanded'){ apply(false); }
  }

  function init(){
    if(INIT_DONE){
      // Re-highlight & ensure persisted state re-applied (template may have been swapped)
      reapplyPersisted();
      highlight();
      return;
    }
    INIT_DONE = true;
    auto();
    highlight();
  }

  // Delegated clicks (supports dynamically reloaded header/sidebars)
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('#sidebar-toggle, [data-action="toggle-sidebar"]');
    if(btn){ e.preventDefault(); toggle(); }
  });
  window.addEventListener('resize', auto);
  // HTMX lifecycle: afterSettle handles fragment swaps; also cover afterSwap for safety
  function onHtmxUpdate(){
    // Ensure classes restored if sidebar fragment re-rendered
    reapplyPersisted();
    highlight();
  }
  document.addEventListener('htmx:afterSettle', onHtmxUpdate);
  document.addEventListener('htmx:afterSwap', onHtmxUpdate);
  document.addEventListener('htmx:afterOnLoad', onHtmxUpdate);

  // Public API
  window.ThesisSidebar = { __v:2, init:init, toggle:toggle, highlight:highlight, auto:auto, _test: { apply:apply } };

  // Early init
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();
