// Live Tasks Dashboard Client
// Minimal bespoke JS retained (cannot trivially express via htmx/hyperscript due to
// incremental, streaming style updates + websocket). Feature flag:
//   Add data-disable-live-tasks to body (or #tasks-live-table parent) to skip init.
// Falls back to polling /api/tasks/events when Socket.IO not present.

(function(){
  const log = (...args) => console.debug('[tasks-live]', ...args);
  const tableBody = () => document.querySelector('#tasks-live-table tbody');
  const queueSummaryEl = () => document.querySelector('#queue-summary');
  let eventsSince = null;
  const rows = new Map(); // task_id -> tr element
  const state = new Map(); // task_id -> { core: {}, tools: { toolName: {status, findings, severity:{...}} } }

  const severityOrder = ['critical','high','medium','low','info'];
  const sevColor = (sev) => ({critical:'danger',high:'danger',medium:'warning',low:'secondary',info:'info'})[sev] || 'secondary';

  function mergeCore(taskId, data){
    const entry = state.get(taskId) || { core: {}, tools: {} };
    entry.core = { ...entry.core, ...data };
    state.set(taskId, entry);
  }

  function ensureRow(taskId){
    let tr = rows.get(taskId);
    if(!tr){
      tr = document.createElement('tr');
      tr.dataset.taskId = taskId;
      rows.set(taskId, tr);
      const body = tableBody();
      if(body) body.appendChild(tr);
    }
    return tr;
  }

  function renderToolsCell(tools){
    const parts = Object.entries(tools).sort(([a],[b]) => a.localeCompare(b)).map(([tool, info]) => {
      const statusBadge = info.status === 'completed' ? 'success' : 'primary';
      const count = info.findings ?? 0;
      return `<span class="badge bg-${statusBadge} me-1 mb-1">${tool}${count?` (${count})`:''}</span>`;
    });
    return parts.join('');
  }

  function renderSeverityAggregate(tools){
    const aggregate = {};
    for(const t of Object.values(tools)){
      if(t.severity){
        for(const [k,v] of Object.entries(t.severity)){
          aggregate[k] = (aggregate[k]||0)+v;
        }
      }
    }
    if(Object.keys(aggregate).length===0) return '';
    return severityOrder.filter(s => aggregate[s]).map(sev => `<span class="badge bg-${sevColor(sev)} me-1 mb-1" title="${sev}">${sev[0].toUpperCase()}${sev==='critical'?'!':''}: ${aggregate[sev]}</span>`).join('');
  }

  function renderRow(taskId){
    const entry = state.get(taskId);
    if(!entry) return;
    const c = entry.core;
    const tr = ensureRow(taskId);
    tr.innerHTML = `
      <td>${taskId}</td>
      <td>${c.analysis_type || ''}</td>
      <td>${c.status || ''}</td>
      <td>${(c.progress_percentage ?? 0).toFixed(0)}%</td>
      <td>${c.target_model || ''}</td>
      <td>${c.target_app_number || ''}</td>
      <td>${c.started_at ? new Date(c.started_at).toLocaleTimeString() : ''}</td>
      <td>${c.completed_at ? new Date(c.completed_at).toLocaleTimeString() : ''}</td>
      <td>${renderToolsCell(entry.tools)}</td>
      <td>${renderSeverityAggregate(entry.tools)}</td>
    `;
  }

  function upsertRow(data){
    if(!data || !data.task_id) return;
    mergeCore(data.task_id, data);
    renderRow(data.task_id);
  }

  function handleToolStarted(d){
    const entry = state.get(d.task_id) || { core: {}, tools: {} };
    const t = entry.tools[d.tool] || {};
    if(t.status !== 'completed'){ // don't override completed
      t.status = 'started';
    }
    entry.tools[d.tool] = t;
    state.set(d.task_id, entry);
    renderRow(d.task_id);
  }

  function handleToolCompleted(d){
    const entry = state.get(d.task_id) || { core: {}, tools: {} };
    const t = entry.tools[d.tool] || {};
    t.status = 'completed';
    t.findings = d.findings_count;
    t.severity = d.severity_breakdown || {};
    entry.tools[d.tool] = t;
    state.set(d.task_id, entry);
    renderRow(d.task_id);
  }

  function handleEvent(evt){
    if(!evt || !evt.event) return;
    const d = evt.data || {};
    if(evt.event === 'task.tool.started'){
      handleToolStarted(d);
    } else if(evt.event === 'task.tool.completed'){
      handleToolCompleted(d);
    } else if(evt.event.startsWith('task.')){
      upsertRow(d);
    } else if(evt.event === 'queue.status'){
      if(queueSummaryEl()){
        queueSummaryEl().textContent = `Running: ${d.total_running} Pending: ${d.total_pending} Slots: ${d.available_slots}`;
      }
    }
  }

  async function poll(){
    try{
      const url = '/api/tasks/events' + (eventsSince? `?since=${encodeURIComponent(eventsSince)}`:'');
      const res = await fetch(url);
      if(!res.ok) throw new Error('poll failed');
      const payload = await res.json();
      if(Array.isArray(payload.events)){
        payload.events.forEach(handleEvent);
        if(payload.events.length){
          eventsSince = payload.events[payload.events.length-1].timestamp;
        }
      }
    }catch(e){
      log('poll error', e);
    }finally{
      setTimeout(poll, 4000);
    }
  }

  function initSocket(){
    if(!(window.io)){
      log('Socket.IO not available, using polling');
      poll();
      return;
    }
    try{
      const socket = io('/', { transports: ['websocket','polling'] });
      socket.on('connect', () => log('connected'));
      ['task.created','task.updated','task.progress','task.completed','task.tool.started','task.tool.completed','queue.status'].forEach(ev => {
        socket.on(ev, (payload) => handleEvent(payload));
      });
      socket.on('disconnect', () => {
        log('disconnected - switching to polling');
        poll();
      });
    }catch(e){
      log('socket init failed', e);
      poll();
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const table = document.getElementById('tasks-live-table');
    if(table && !table.closest('[data-disable-live-tasks]') && !document.body.hasAttribute('data-disable-live-tasks')){
      initSocket();
    }
  });
})();
