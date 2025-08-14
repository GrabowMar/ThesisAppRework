(function(){
  const STORAGE_KEY = 'theme';
  const CLASS_DARK = 'theme-dark';
  function applyTheme(theme){
    const body = document.body;
    if(theme === 'dark') body.classList.add(CLASS_DARK); else body.classList.remove(CLASS_DARK);
  }
  function loadTheme(){
    try { return localStorage.getItem(STORAGE_KEY) || 'light'; } catch { return 'light'; }
  }
  function saveTheme(theme){ try { localStorage.setItem(STORAGE_KEY, theme); } catch {} }
  function toggle(){
    const current = loadTheme();
    const next = current === 'dark' ? 'light' : 'dark';
    saveTheme(next); applyTheme(next);
    const evt = new CustomEvent('theme:changed', { detail: { theme: next } });
    window.dispatchEvent(evt);
  }
  window.Theme = { toggle, load: loadTheme, apply: applyTheme };
  document.addEventListener('DOMContentLoaded', function(){ applyTheme(loadTheme()); });
})();
