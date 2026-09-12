/**
 * panel_app.js
 * Main panel controller: loading, tabs, search, keyboard navigation, and lifecycle.
 */

let _currentTab = 'tasks';
let _taskFilter = 'all';
let _sevenAlive = false;
let _loadInFlight = false;
window._allTasks = [];
let _filteredTasks = [];

window.addEventListener('DOMContentLoaded', () => {
  requestAnimationFrame(() => setTimeout(() => document.getElementById('panel')?.classList.add('open'), 20));
  const date = document.getElementById('summary-date');
  if (date) date.textContent = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date());
  loadAll();

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (typeof _editingTriggerId !== 'undefined' && _editingTriggerId) return;
      const modal = document.getElementById('closeall-modal');
      if (modal?.style.display === 'flex') { dismissCloseAll(); return; }
      if (document.getElementById('search-wrap')?.classList.contains('visible')) { toggleSearch(); return; }
      closePanel();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); toggleSearch(); }
    if (_currentTab === 'tasks' && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const n = Number.parseInt(e.key, 10);
      if (n >= 1 && n <= 9 && _filteredTasks[n - 1]) startComplete(_filteredTasks[n - 1].id);
    }
  });

  const quickInput = document.getElementById('quick-input');
  quickInput?.addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter' || e.isComposing || e.keyCode === 229 || !quickInput.value.trim()) return;
    const text = quickInput.value.trim(); quickInput.value = ''; quickInput.disabled = true; quickInput.placeholder = 'Adding to Seven…';
    const ok = await createTask(text); quickInput.disabled = false; quickInput.placeholder = ok ? 'Added. Capture another task…' : 'Could not add task. Try again.';
    if (ok) loadAll(); setTimeout(() => { quickInput.placeholder = 'Capture a task…'; }, 1800);
  });
  document.getElementById('search-input')?.addEventListener('input', () => { if (_currentTab === 'tasks') applyTaskFilter(); });
  setInterval(loadAll, 15000);
});

async function loadAll() {
  if (_loadInFlight) return; _loadInFlight = true;
  try {
    const [tasks, stats, sched, triggers, alive] = await Promise.all([fetchTasks(), fetchTaskStats(), fetchSchedules(), fetchTriggersList(), isSevenAlive()]);
    window._allTasks = Array.isArray(tasks) ? tasks : []; _allSchedules = Array.isArray(sched) ? sched : []; _allTriggers = Array.isArray(triggers) ? triggers : []; _sevenAlive = alive;
    updateBrand(alive); updateSummaryCard(stats || {}, countCompletedToday(window._allTasks)); updateTabCounts();
    if (_currentTab === 'tasks') applyTaskFilter(); else if (_currentTab === 'triggers') renderTriggers(); else renderSchedules();
  } finally { _loadInFlight = false; }
}
function countCompletedToday(tasks) { const today = new Date().toISOString().split('T')[0]; return tasks.filter(t => t.completed && t.completed_at?.startsWith(today)).length; }
function updateBrand(alive) { document.getElementById('brand-dot')?.classList.toggle('alive', alive); const sub = document.getElementById('header-sub'); if (sub) sub.textContent = alive ? 'connected' : 'offline'; }
function updateTabCounts() { const t = document.getElementById('tab-cnt-tasks'); const tr = document.getElementById('tab-cnt-triggers'); const s = document.getElementById('tab-cnt-schedules'); if (t) t.textContent = window._allTasks.filter(x => !x.completed).length; if (tr) tr.textContent = _allTriggers.length; if (s) s.textContent = _allSchedules.length; }
function switchTab(tab) { _currentTab = tab; document.querySelectorAll('.tab').forEach(el => { const active = el.dataset.tab === tab; el.classList.toggle('active', active); el.setAttribute('aria-selected', String(active)); }); document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden')); document.getElementById(`tab-${tab}`)?.classList.remove('hidden'); const quickAdd = document.getElementById('quick-add'); if (quickAdd) quickAdd.style.display = tab === 'tasks' ? 'block' : 'none'; if (tab === 'tasks') applyTaskFilter(); else if (tab === 'triggers') renderTriggers(); else renderSchedules(); }
function setTaskFilter(f) { _taskFilter = f; document.querySelectorAll('#task-filters .filter-chip').forEach(c => c.classList.toggle('active', c.dataset.filter === f)); applyTaskFilter(); }
function applyTaskFilter() { const today = new Date(); today.setHours(0,0,0,0); const search = (document.getElementById('search-input')?.value || '').toLowerCase(); let list = window._allTasks.filter(t => !t.completed); if (_taskFilter === 'today') list = list.filter(t => t.due_date && new Date(`${t.due_date}T00:00:00`).getTime() <= today.getTime()); if (_taskFilter === 'overdue') list = list.filter(t => t.due_date && new Date(`${t.due_date}T00:00:00`).getTime() < today.getTime()); if (_taskFilter === 'pinned') list = list.filter(t => (t.tags || []).includes('pinned')); if (search) list = list.filter(t => `${t.text || ''} ${t.description || ''}`.toLowerCase().includes(search)); list.sort((a,b) => Number(!(a.tags || []).includes('pinned')) - Number(!(b.tags || []).includes('pinned'))); _filteredTasks = list; renderTaskList(); }
function renderTaskList() { const list = document.getElementById('task-list'); const empty = document.getElementById('task-empty'); if (!list || !empty) return; if (!_filteredTasks.length) { list.style.display = 'none'; empty.style.display = 'flex'; return; } empty.style.display = 'none'; list.style.display = 'flex'; list.replaceChildren(..._filteredTasks.map((task, index) => renderTaskCard(task, index))); }
function onTaskRemoved(taskId) { window._allTasks = window._allTasks.filter(t => t.id !== taskId); _filteredTasks = _filteredTasks.filter(t => t.id !== taskId); updateTabCounts(); renderTaskList(); fetchTaskStats().then(s => updateSummaryCard(s, countCompletedToday(window._allTasks))); }
function reloadTasks() { loadAll(); }
function toggleSearch() { const wrap = document.getElementById('search-wrap'); const input = document.getElementById('search-input'); if (!wrap || !input) return; const visible = wrap.classList.toggle('visible'); if (visible) setTimeout(() => input.focus(), 50); else { input.value = ''; if (_currentTab === 'tasks') applyTaskFilter(); } }
function closePanel() { Object.values(_countdowns || {}).forEach(clearInterval); Object.values(_deleteTimers || {}).forEach(clearInterval); if (typeof _restoreTimer !== 'undefined' && _restoreTimer) clearInterval(_restoreTimer); const panel = document.getElementById('panel'); panel?.classList.add('closing'); setTimeout(() => window.electronAPI?.closePanel ? window.electronAPI.closePanel() : window.close(), 320); }
function openSevenTasks() { window.electronAPI?.openSevenTasks?.(); closePanel(); }
