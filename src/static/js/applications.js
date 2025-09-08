(function(){
  // Single refresh dispatcher: listens for custom event OR button click with data-action
  function refresh(){
    if(!window.htmx) return;
    // Prefer unified refresher target
    const refresher = document.querySelector('#apps-table-refresher, #grid-refresher');
    if(refresher){ window.htmx.trigger(refresher, 'refresh-apps-table'); }
  }

  document.addEventListener('refresh-apps-table', refresh, { passive:true });
  // Backwards compatibility
  document.addEventListener('refresh-grid', refresh, { passive:true });
  // Delegate button clicks
  document.addEventListener('click', function(e){
    const btn = e.target.closest('[data-action="refresh-apps"]');
    if(btn){ e.preventDefault(); refresh(); }
  });
  // Soft notice once
  if(!window.__APPS_JS_NOTICE){
    window.__APPS_JS_NOTICE = true;
    console.info('[applications.js] Legacy generate prefill helper removed; use hyperscript instead.');
  }
})();
