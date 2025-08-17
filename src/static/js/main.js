// Main project JavaScript
// Safe to load even if features are unused on a page.
(function(){
  document.addEventListener('DOMContentLoaded', function(){
    // HTMX global error logging (optional)
    if (window.htmx) {
      document.body.addEventListener('htmx:responseError', function(evt){
        console.error('HTMX error:', evt.detail);
      });
    }
  });
})();
