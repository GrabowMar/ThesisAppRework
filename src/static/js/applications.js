// applications.js - behavior for Applications page (extracted from inline script)
// Handles: prefill generate modal, manual refresh triggers

(function(){
  function prefillAndShowGenerate(modelSlug, appNumber) {
    const modelSelect = document.querySelector('#generateAppForm select[name="model_slug"]');
    if (modelSelect) modelSelect.value = modelSlug;
    const appInput = document.querySelector('#generateAppForm input[name="app_number"]');
    if (appInput) appInput.value = appNumber;
    const modalEl = document.getElementById('generateAppModal');
    if (modalEl && window.bootstrap) {
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  }
  window.prefillAndShowGenerate = prefillAndShowGenerate; // expose global for template button

  function triggerAppsTableRefresh(){
    if(window.htmx){
      // New table refresher
      if(document.querySelector('#apps-table-refresher')){
        window.htmx.trigger('#apps-table-refresher','refresh-apps-table');
      }
      // Legacy grid support (safe no-op if removed)
      if(document.querySelector('#grid-refresher')){
        window.htmx.trigger('#grid-refresher','refresh-grid');
      }
    }
  }
  document.addEventListener('refresh-apps-table', triggerAppsTableRefresh);
  document.addEventListener('refresh-grid', triggerAppsTableRefresh); // backward compatibility
  document.getElementById('refreshGridBtn')?.addEventListener('click', triggerAppsTableRefresh);
})();
