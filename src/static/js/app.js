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

// 3. Sidebar logic moved to dedicated sidebar.js (ThesisSidebar). Backwards compatibility shim.
ThesisApp.layout = {
  init: function(){ if(window.ThesisSidebar) window.ThesisSidebar.init(); },
  toggleUser: function(){ if(window.ThesisSidebar) window.ThesisSidebar.toggle(); },
  updateActiveNavLink: function(){ if(window.ThesisSidebar) window.ThesisSidebar.highlight(); },
  autoDetermine: function(){ if(window.ThesisSidebar) window.ThesisSidebar.auto(); },
  reinitialize: function(){ if(window.ThesisSidebar) window.ThesisSidebar.init(); }
};

// Soft deprecation notice (only once)
if(!window.__APP_JS_DEPRECATION){
  window.__APP_JS_DEPRECATION = true;
  console.info('[ThesisApp] app.js trimmed. Prefer hyperscript/htmx attributes over manual JS.');
}
