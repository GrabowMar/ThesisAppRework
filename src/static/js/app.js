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

// 4. Progress meter helper shared across dashboard tables
(function(){
  function clampProgress(val){
    var num = parseFloat(val);
    if(!isFinite(num)) return 0;
    return Math.min(100, Math.max(0, num));
  }

  function setAriaAttributes(el, value){
    el.setAttribute('role', 'progressbar');
    el.setAttribute('aria-valuemin', '0');
    el.setAttribute('aria-valuemax', '100');
    el.setAttribute('aria-valuenow', value.toFixed ? value.toFixed(0) : value);
  }

  function updateProgressBars(root){
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('.progress[data-progress]').forEach(function(progressEl){
      var value = clampProgress(progressEl.getAttribute('data-progress'));
      var bar = progressEl.querySelector('.progress-bar');
      if(bar){
        bar.style.width = value + '%';
        bar.setAttribute('aria-valuenow', value.toFixed(0));
        bar.setAttribute('aria-valuemin', '0');
        bar.setAttribute('aria-valuemax', '100');
        bar.textContent = value >= 45 ? value.toFixed(0) + '%' : '';
      }
      setAriaAttributes(progressEl, value);
    });
  }

  ThesisApp.refreshProgressBars = updateProgressBars;

  function onReady(fn){
    if(document.readyState === 'loading'){
      document.addEventListener('DOMContentLoaded', function handler(){
        document.removeEventListener('DOMContentLoaded', handler);
        fn();
      });
    } else {
      fn();
    }
  }

  onReady(function(){ updateProgressBars(document); });

  document.addEventListener('htmx:afterSwap', function(evt){
    if(evt && evt.target){ updateProgressBars(evt.target); }
  });
  document.addEventListener('htmx:afterSettle', function(evt){
    if(evt && evt.target){ updateProgressBars(evt.target); }
  });
  document.addEventListener('thesis:refresh-progress', function(evt){
    updateProgressBars(evt && evt.detail && evt.detail.root ? evt.detail.root : document);
  });
})();
