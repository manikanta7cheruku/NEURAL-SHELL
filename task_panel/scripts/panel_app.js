/**
 * panel_app.js
 * Main panel controller: tab switching, initialization, keyboard nav.
 */

let _currentTab = 'tasks';
let _taskFilter = 'all';
let _sevenAlive = false;
window._allTasks = [];
let _filteredTasks = [];

window.addEventListener('DOMContentLoaded', () => {
  requestAnimationFrame(() => {
    setTimeout(() => document.getElementById('panel').classList.add('open'), 20);
  });

  loadAll();

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (_editingTriggerId) return;
      const modal = document.getElementById('closeall-modal');
      if (modal && modal.style.display === 'flex') {
        dismissCloseAll();
        return;
      }
      closePanel();
    }

    if (e.ctrlKey && e.key === 'f') {
      e.preventDefault();
      toggleSearch();
    }

    if (_currentTab === 'tasks') {
      const n = parseInt(e.key);
      if (n >= 1 && n <= 9 && _filteredTasks[n - 1]) {
        startComplete(_filteredTasks[n - 1].id);
      }
    }
  });

  const quickInput = document.getElementById('quick-input');
  if (quickInput) {
    quickInput.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter' && quickInput.value.trim()) {
        const text = quickInput.value.trim();
        quickInput.value = '';
        quickInput.placeholder = 'Adding...';
        const ok = await createTask(text);
        quickInput.placeholder = ok ? 'Added. Type another...' : 'Failed. Try again.';
        setTimeout(() => { quickInput.placeholder = 'Add a task... (Enter)'; }, 1500);
        if (ok) loadAll();
      }
    });
  }

  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      if (_currentTab === 'tasks') applyTaskFilter();
    });
  }

  setInterval(loadAll, 15000);
});

async function loadAll() {
  const [tasks, stats, sched, triggers, alive] = await Promise.all([
    fetchTasks(),
    fetchTaskStats(),
    fetchSchedules(),
    fetchTriggersList(),
    isSevenAlive(),
  ]);

  window._allTasks = tasks;
  _allSchedules = sched;
  _allTriggers = triggers;
  _sevenAlive = alive;

  updateBrand(alive);
  updateSummaryCard(stats, countCompletedToday(tasks));
  updateTabCounts();

  if (_currentTab === 'tasks') applyTaskFilter();
  else if (_currentTab === 'triggers') renderTriggers();
  else if (_currentTab === 'schedules') renderSchedules();
}

function countCompletedToday(tasks) {
  const today = new Date().toISOString().split('T')[0];
  return tasks.filter(t => t.completed && t.completed_at && t.completed_at.startsWith(today)).length;
}

function updateBrand(alive) {
  const dot = document.getElementById('brand-dot');
  const sub = document.getElementById('header-sub');
  if (dot) dot.classList.toggle('alive', alive);
  if (sub) sub.textContent = alive ? 'connected' : 'offline';
}

function updateTabCounts() {
  const t = document.getElementById('tab-cnt-tasks');
  const tr = document.getElementById('tab-cnt-triggers');
  const s = document.getElementById('tab-cnt-schedules');
  if (t) t.textContent = (window._allTasks || []).filter(x => !x.completed).length;
  if (tr) tr.textContent = _allTriggers.length;
  if (s) s.textContent = _allSchedules.length;
}

function switchTab(tab) {
  _currentTab = tab;

  document.querySelectorAll('.tab').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.add('hidden');
  });
  document.getElementById(`tab-${tab}`).classList.remove('hidden');

  const quickAdd = document.getElementById('quick-add');
  if (quickAdd) quickAdd.style.display = tab === 'tasks' ? 'block' : 'none';

  if (tab === 'tasks') applyTaskFilter();
  else if (tab === 'triggers') renderTriggers();
  else if (tab === 'schedules') renderSchedules();
}

function setTaskFilter(f) {
  _taskFilter = f;
  document.querySelectorAll('#task-filters .filter-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.filter === f);
  });
  applyTaskFilter();
}

function applyTaskFilter() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const search = (document.getElementById('search-input')?.value || '').toLowerCase();

  let list = (window._allTasks || []).filter(t => !t.completed);

  if (_taskFilter === 'today') {
    list = list.filter(t => t.due_date && new Date(t.due_date + 'T00:00:00').getTime() <= today.getTime());
  } else if (_taskFilter === 'overdue') {
    list = list.filter(t => t.due_date && new Date(t.due_date + 'T00:00:00').getTime() < today.getTime());
  } else if (_taskFilter === 'pinned') {
    list = list.filter(t => (t.tags || []).includes('pinned'));
  }

  if (search) {
    list = list.filter(t =>
      (t.text || '').toLowerCase().includes(search) ||
      (t.description || '').toLowerCase().includes(search)
    );
  }

  list.sort((a, b) => {
    const aP = (a.tags || []).includes('pinned') ? 0 : 1;
    const bP = (b.tags || []).includes('pinned') ? 0 : 1;
    if (aP !== bP) return aP - bP;
    return 0;
  });

  _filteredTasks = list;
  renderTaskList();
}

function renderTaskList() {
  const list = document.getElementById('task-list');
  const empty = document.getElementById('task-empty');
  if (!list) return;

  if (_filteredTasks.length === 0) {
    list.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }

  empty.style.display = 'none';
  list.style.display = 'flex';
  list.innerHTML = '';
  _filteredTasks.forEach((t, i) => list.appendChild(renderTaskCard(t, i)));
}

function onTaskRemoved(taskId) {
  window._allTasks = window._allTasks.filter(t => t.id !== taskId);
  _filteredTasks = _filteredTasks.filter(t => t.id !== taskId);
  updateTabCounts();
  if (_filteredTasks.length === 0) renderTaskList();
  fetchTaskStats().then(s => updateSummaryCard(s, countCompletedToday(window._allTasks)));
}

function reloadTasks() {
  loadAll();
}

function toggleSearch() {
  const wrap = document.getElementById('search-wrap');
  const input = document.getElementById('search-input');
  if (!wrap || !input) return;
  const visible = wrap.classList.contains('visible');
  if (visible) {
    wrap.classList.remove('visible');
    input.value = '';
    if (_currentTab === 'tasks') applyTaskFilter();
  } else {
    wrap.classList.add('visible');
    setTimeout(() => input.focus(), 50);
  }
}

function closePanel() {
  Object.values(_countdowns).forEach(clearInterval);
  Object.values(_deleteTimers).forEach(clearInterval);
  if (_restoreTimer) clearInterval(_restoreTimer);

  const panel = document.getElementById('panel');
  if (panel) {
    panel.classList.remove('open');
    panel.classList.add('closing');
  }
  setTimeout(() => {
    if (window.electronAPI?.closePanel) window.electronAPI.closePanel();
    else window.close();
  }, 320);
}

function openSevenTasks() {
  if (window.electronAPI?.openSevenTasks) window.electronAPI.openSevenTasks();
  closePanel();
}