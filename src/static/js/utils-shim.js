// Simple Utils shim to avoid ReferenceError if utils.js hasn't loaded yet
(function(global){
  if (!global.Utils) {
    global.Utils = {
      formatNumber: function(n){ try { return new Intl.NumberFormat().format(n); } catch(e){ return String(n); } },
      clamp: function(v,min,max){ return Math.min(max, Math.max(min, v)); },
      noop: function(){},
      version: 'shim-1'
    };
    console.log('🔧 Utils shim applied');
  }
  // Ensure a basic Storage helper exists
  if (!global.Utils.Storage) {
    try {
      global.Utils.Storage = {
        get: function(key, fallback){
          try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch(e){ return fallback; }
        },
        set: function(key, value){ try { localStorage.setItem(key, JSON.stringify(value)); } catch(e){} },
        remove: function(key){ try { localStorage.removeItem(key); } catch(e){} }
      };
    } catch(e) { /* ignore */ }
  }
})(window);
