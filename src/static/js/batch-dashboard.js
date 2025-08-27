// Batch dashboard functions isolated to guarantee availability for inline onclick handlers
(function(global){
  function go(u){ window.location.href = u; }
  function createBatchOperation(){ go('/batch/create'); }
  function createSecurityBatch(){ go('/batch/create?type=security'); }
  function createPerformanceBatch(){ go('/batch/create?type=performance'); }
  function createDynamicBatch(){ go('/batch/create?type=dynamic'); }
  function createComprehensiveBatch(){ go('/batch/create?type=comprehensive'); }
  global.createBatchOperation = global.createBatchOperation || createBatchOperation;
  global.createSecurityBatch = global.createSecurityBatch || createSecurityBatch;
  global.createPerformanceBatch = global.createPerformanceBatch || createPerformanceBatch;
  global.createDynamicBatch = global.createDynamicBatch || createDynamicBatch;
  global.createComprehensiveBatch = global.createComprehensiveBatch || createComprehensiveBatch;
  console.log('🧩 Batch dashboard helpers loaded');
})(window);
