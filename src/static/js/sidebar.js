// ThesisSidebar: robust, idempotent sidebar controller with persistence & HTMX resilience
(function(){
  if(window.ThesisSidebar && window.ThesisSidebar.__v){ return; }
  var LS_KEY = 'sidebarPref';
  var MOBILE_BP = 992; // < lg
  var AUTO_COLLAPSE_BP = 1200; // auto collapse threshold for large but not huge screens
  var MOBILE_CLASS = 'sidebar-mobile-open';
  var INIT_DONE = false;

  function getSidebar(){ return document.getElementById('sidebar'); }
  function getToggle(){ return document.getElementById('sidebar-toggle'); }
  function getMobileToggle(){ return document.getElementById('mobile-sidebar-toggle'); }
  function getBackdrop(){ return document.getElementById('sidebar-backdrop'); }
  function readPref(){ try { return localStorage.getItem(LS_KEY); } catch(_){ return null; } }
  function writePref(v){ try { localStorage.setItem(LS_KEY, v); } catch(_){} }
  function isMobileOpen(){ return document.body.classList.contains(MOBILE_CLASS); }

  function setMobileState(open){
    var sb = getSidebar();
    if(sb){ sb.classList.toggle('sidebar-open', !!open); }
    document.body.classList.toggle(MOBILE_CLASS, !!open);
    var backdrop = getBackdrop();
    if(backdrop){ backdrop.classList.toggle('show', !!open); }
    var toggleBtn = getMobileToggle();
    if(toggleBtn){
      toggleBtn.setAttribute('aria-expanded', (!!open).toString());
      toggleBtn.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
    }
  }

  function closeMobile(){ if(isMobileOpen()) setMobileState(false); }
  function openMobile(){ if(!isMobileOpen()) setMobileState(true); }
  function toggleMobile(force){
    var next = typeof force === 'boolean' ? force : !isMobileOpen();
    setMobileState(next);
  }

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
    if(w >= MOBILE_BP){ closeMobile(); }
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

  // Map URL path segments to nav targets (for routes where they differ)
  var PATH_TO_NAV = {
    'statistics': 'stats',
    'sample-generator': 'sample-generator',
    'models_overview': 'models'
  };

  function highlight(){
    try {
      var path = window.location.pathname.replace(/\/$/, '');
      var primary = path.split('/').filter(Boolean)[0] || 'dashboard';
      // Normalize path segment to nav target
      var navTarget = PATH_TO_NAV[primary] || primary;
      document.querySelectorAll('.sidebar .nav-link[data-nav-target]').forEach(function(a){
        var target = a.getAttribute('data-nav-target');
        var isActive = target === navTarget;
        a.classList.toggle('active', isActive);
        a.classList.toggle('bg-primary', isActive);
        a.classList.toggle('text-white', isActive);
        a.classList.toggle('shadow-sm', isActive);
        a.classList.toggle('hover-bg-white-10', !isActive);
        // Update icon color
        var icon = a.querySelector('i');
        if(icon){
          icon.classList.toggle('text-white', isActive);
          icon.classList.toggle('text-white-50', !isActive);
        }
        // Update aria-current
        if(isActive){
          a.setAttribute('aria-current', 'page');
        } else {
          a.removeAttribute('aria-current');
        }
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
      setMobileState(false);
      highlight();
      return;
    }
    INIT_DONE = true;
    setMobileState(false);
    auto();
    highlight();
  }

  // Delegated clicks (supports dynamically reloaded header/sidebars)
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('#sidebar-toggle, #mobile-sidebar-toggle, [data-action="toggle-sidebar"]');
    if(btn){
      e.preventDefault();
      if(btn.id === 'mobile-sidebar-toggle'){ toggleMobile(); }
      else { toggle(); }
      return;
    }

    var backdrop = e.target.closest && e.target.closest('#sidebar-backdrop');
    if(backdrop){
      e.preventDefault();
      closeMobile();
      return;
    }

    var navLink = e.target.closest && e.target.closest('.sidebar .nav-link');
    if(navLink && isMobileOpen()){
      closeMobile();
    }
  });

  document.addEventListener('keydown', function(e){
    if((e.key === 'Escape' || e.key === 'Esc') && isMobileOpen()){
      closeMobile();
    }
  });
  window.addEventListener('resize', auto);
  // HTMX lifecycle: afterSettle handles fragment swaps; also cover afterSwap for safety
  function onHtmxUpdate(){
    // Ensure classes restored if sidebar fragment re-rendered
    reapplyPersisted();
    closeMobile();
    highlight();
  }
  document.addEventListener('htmx:afterSettle', onHtmxUpdate);
  document.addEventListener('htmx:afterSwap', onHtmxUpdate);
  document.addEventListener('htmx:afterOnLoad', onHtmxUpdate);
  document.addEventListener('htmx:historyRestore', onHtmxUpdate);
  // Custom thesis navigation event
  document.addEventListener('thesis:pageInit', onHtmxUpdate);

  // Public API
  window.ThesisSidebar = {
    __v: 2,
    init: init,
    toggle: toggle,
    toggleMobile: toggleMobile,
    openMobile: openMobile,
    closeMobile: closeMobile,
    highlight: highlight,
    auto: auto,
    _test: { apply: apply }
  };

  // Early init
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();
