// Applications table helpers (flat table version)
// Assumptions: server currently returns full list; simple client-side pagination placeholder

window.changeAppsPerPage = function(perPage){
  // Future: apply via query param & HTMX reload
  const url = new URL(window.location.href);
  url.searchParams.set('apps_per_page', perPage);
  htmx.ajax('GET', url.toString(), {target:'#apps-table-section', select:'#apps-table-section'});
};

window.toggleSelectAllApps = function(){
  const master = document.getElementById('select-all-apps');
  document.querySelectorAll('#applications-table-body .app-select').forEach(cb => { cb.checked = master.checked; });
  updateSelectedAppsCount();
};

function updateSelectedAppsCount(){
  const count = document.querySelectorAll('#applications-table-body .app-select:checked').length;
  // Could surface count in future UI element
  document.dispatchEvent(new CustomEvent('apps-selection-changed', {detail:{count}}));
}

document.addEventListener('change', (e)=>{
  if(e.target.classList.contains('app-select')) updateSelectedAppsCount();
});

document.addEventListener('htmx:afterSwap', (e)=>{
  if(e.detail.target && e.detail.target.id==='apps-table-section'){
    // Re-sync master checkbox
    const master = document.getElementById('select-all-apps');
    if(master) master.checked = false;
  }
});
