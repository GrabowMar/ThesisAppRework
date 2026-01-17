// Centralized theme management to persist mode across page loads & HTMX swaps
// Emits a custom 'theme:changed' event on document when toggled or initialized
(function(){
  if(window.ThesisTheme && window.ThesisTheme.__v){ return; }
  var ROOT = document.documentElement;
  var _initDone = false;
  function apply(t, persist){
    var current = ROOT.getAttribute('data-bs-theme');
  if(current === t){ return; }
    ROOT.setAttribute('data-bs-theme', t);
    if(persist) try { localStorage.setItem('app_theme', t); } catch(_){ }
    try {
      var btn = document.getElementById('theme-toggle');
      var icon = document.getElementById('theme-toggle-icon');
      if(icon){ icon.className = t==='dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon'; icon.setAttribute('data-icon-theme', t); }
      if(btn){ btn.setAttribute('aria-pressed', t==='dark'); }
    } catch(_) {}
    document.dispatchEvent(new CustomEvent('theme:changed', {detail:{theme:t}}));
  }
  function determineInitial(){
    var stored;
    try { stored = localStorage.getItem('app_theme'); } catch(_){ }
    if(stored){ return stored; }
    var prefers = false;
    try { prefers = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; } catch(_){ }
    return prefers ? 'dark' : 'light';
  }
  function init(){
  if(_initDone){ return; }
    _initDone = true;
    var initial = determineInitial();
    apply(initial, false);
    if(!localStorage.getItem('app_theme') && window.matchMedia){
      try {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e){
          if(!localStorage.getItem('app_theme')) apply(e.matches? 'dark':'light', false);
        });
      } catch(_){ }
    }
  }
  var api = {
    __v: 2,
    init: init,
    set: function(t){ apply(t, true); },
    toggle: function(){
      var cur = ROOT.getAttribute('data-bs-theme') || determineInitial();
      apply(cur==='dark' ? 'light' : 'dark', true);
    }
  };
  window.ThesisTheme = api;
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else { init(); }
  document.addEventListener('htmx:afterSwap', function(){
    // Only re-sync UI if button/icon inserted; do NOT re-apply same theme to avoid toggling illusion
    var t = ROOT.getAttribute('data-bs-theme') || determineInitial();
    apply(t, false);
  });
  document.addEventListener('click', function(e){
    var target = e.target.closest && e.target.closest('#theme-toggle');
    if(!target) return;
    api.toggle();
  });
})();
