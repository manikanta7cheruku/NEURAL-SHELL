/**
 * panel_app.js
 * Main panel controller: tab switching, initialization, keyboard nav, state sync.
 */

let _currentTab = 'tasks';
let _taskFilter = 'all';
let _sevenAlive = false;
window._allTasks = [];
window._allSchedules = [];
window._allTriggers = [];
let _filteredTasks = [];

/** tags may be array, JSON string, or comma-separated string */
function normalizeTags(tags) {
  if (Array.isArray(tags)) return tags.filter(Boolean).map(String);
  if (typeof tags === 'string') {
    const s = tags.trim();
    if (!s) return [];
    try {
      const parsed = JSON.parse(s);
      if (Array.isArray(parsed)) return parsed.filter(Boolean).map(String);
    } catch (_) { /* comma list */ }
    return s.split(',').map(x => x.trim()).filter(Boolean);
  }
  return [];
}

function taskHasPin(t) {
  return normalizeTags(t && t.tags).includes('pinned');
}

window.addEventListener('DOMContentLoaded', () => {
  // FAST-BOOT: Load cached data immediately so UI is instantly populated
  try {
    const cachedTasks = localStorage.getItem('seven_cached_tasks');
    if (cachedTasks) {
      window._allTasks = JSON.parse(cachedTasks);
      applyTaskFilter();
    }
  } catch(e) {}

  requestAnimationFrame(() => {
    setTimeout(() => {
      const panel = document.getElementById('panel');
      if (panel) panel.classList.add('open');
    }, 20);
  });

  loadAll();

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (typeof _editingTriggerId !== 'undefined' && _editingTriggerId) {
        if (typeof cancelHotkeyRecording === 'function') {
          cancelHotkeyRecording(_editingTriggerId);
        }
        return;
      }
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
      const n = parseInt(e.key, 10);
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
        quickInput.placeholder = 'Adding task...';
        const ok = await createTask(text);
        quickInput.placeholder = ok ? 'Added. Type another...' : 'Failed. Try again.';
        setTimeout(() => {
          quickInput.placeholder = 'Add a task... (Enter to save)';
        }, 1500);
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

  // Periodic poll for sync
  setInterval(loadAll, 10000);
});

async function loadAll() {
  const [tasks, stats, sched, triggers, alive] = await Promise.all([
    fetchTasks(),
    fetchTaskStats(),
    fetchSchedules(),
    fetchTriggersList(),
    isSevenAlive(),
  ]);

  window._allTasks = tasks || [];
  window._allSchedules = sched || [];
  window._allTriggers = triggers || [];
  _sevenAlive = alive;

  // FAST-BOOT: Save to cache for the next time the window opens
  try { localStorage.setItem('seven_cached_tasks', JSON.stringify(window._allTasks)); } catch(e) {}

  updateBrand(alive);
  updateSummaryCard(stats, countCompletedToday(window._allTasks));
  updateTabCounts();

  if (_currentTab === 'tasks') {
    if (typeof stopSchedulesTimer === 'function') stopSchedulesTimer();
    applyTaskFilter();
  } else if (_currentTab === 'triggers') {
    if (typeof stopSchedulesTimer === 'function') stopSchedulesTimer();
    renderTriggers();
  } else if (_currentTab === 'schedules') {
    renderSchedules();
  }
}

function countCompletedToday(tasks) {
  const today = new Date().toISOString().split('T')[0];
  return (tasks || []).filter(
    (t) => t.completed && t.completed_at && t.completed_at.startsWith(today)
  ).length;
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
  if (t) t.textContent = (window._allTasks || []).filter((x) => !x.completed).length;
  if (tr) tr.textContent = (window._allTriggers || []).length;
  if (s) s.textContent = (window._allSchedules || []).length;
}

function switchTab(tab) {
  _currentTab = tab;

  document.querySelectorAll('.tab').forEach((el) => {
    const isActive = el.dataset.tab === tab;
    el.classList.toggle('active', isActive);
    el.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  document.querySelectorAll('.tab-content').forEach((el) => {
    el.classList.add('hidden');
    el.classList.remove('active');
  });

  const activeContent = document.getElementById(`tab-${tab}`);
  if (activeContent) {
    activeContent.classList.remove('hidden');
    activeContent.classList.add('active');
  }

  const quickAdd = document.getElementById('quick-add');
  if (quickAdd) quickAdd.style.display = tab === 'tasks' ? 'block' : 'none';

  if (tab === 'tasks') {
    if (typeof stopSchedulesTimer === 'function') stopSchedulesTimer();
    applyTaskFilter();
  } else if (tab === 'triggers') {
    if (typeof stopSchedulesTimer === 'function') stopSchedulesTimer();
    renderTriggers();
  } else if (tab === 'schedules') {
    renderSchedules();
  }
}

function setTaskFilter(f) {
  _taskFilter = f;
  document.querySelectorAll('#task-filters .filter-chip').forEach((c) => {
    c.classList.toggle('active', c.dataset.filter === f);
  });
  applyTaskFilter();
}

function applyTaskFilter() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const search = (document.getElementById('search-input')?.value || '').toLowerCase();

  // Bulletproof SQLite completion check (handles 0, 1, "0", "1", true, false)
  let list = (window._allTasks || []).filter(t => {
    const isDone = t.completed === true || t.completed === 1 || t.completed === '1';
    return !isDone;
  });

  if (_taskFilter === 'today') {
    list = list.filter(t => t.due_date && new Date(t.due_date + 'T00:00:00').getTime() <= today.getTime());
  } else if (_taskFilter === 'overdue') {
    list = list.filter(t => t.due_date && new Date(t.due_date + 'T00:00:00').getTime() < today.getTime());
  } else if (_taskFilter === 'pinned') {
    list = list.filter(t => taskHasPin(t));
  }

  if (search) {
    list = list.filter(t => 
      (t.text || '').toLowerCase().includes(search) ||
      (t.description || '').toLowerCase().includes(search)
    );
  }

  // Sort pinned to top safely
  list = list.sort((a, b) => {
    const aP = taskHasPin(a) ? 0 : 1;
    const bP = taskHasPin(b) ? 0 : 1;
    return aP - bP;
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
    if (empty) empty.style.display = 'flex';
    return;
  }

  if (empty) empty.style.display = 'none';
  list.style.display = 'flex';
  list.innerHTML = '';
  _filteredTasks.forEach((t, i) => {
    try {
      list.appendChild(renderTaskCard(t, i));
    } catch (err) {
      console.error('Failed to append task card:', t, err);
    }
  });
}

function onTaskRemoved(taskId) {
  window._allTasks = (window._allTasks || []).filter((t) => t.id !== taskId);
  _filteredTasks = _filteredTasks.filter((t) => t.id !== taskId);
  updateTabCounts();
  if (_filteredTasks.length === 0) renderTaskList();
  fetchTaskStats().then((s) => updateSummaryCard(s, countCompletedToday(window._allTasks)));
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
  if (typeof _countdowns !== 'undefined') {
    Object.values(_countdowns).forEach(clearInterval);
  }
  if (typeof _deleteTimers !== 'undefined') {
    Object.values(_deleteTimers).forEach(clearInterval);
  }
  if (typeof _restoreTimer !== 'undefined' && _restoreTimer) {
    clearInterval(_restoreTimer);
  }
  if (typeof stopSchedulesTimer === 'function') {
    stopSchedulesTimer();
  }

  const panel = document.getElementById('panel');
  if (panel) {
    panel.classList.remove('open');
    panel.classList.add('closing');
  }
  setTimeout(() => {
    if (window.electronAPI?.closePanel) {
      window.electronAPI.closePanel();
    } else {
      window.close();
    }
  }, 320);
}

function openSevenTasks() {
  if (window.electronAPI?.openSevenTasks) {
    window.electronAPI.openSevenTasks();
  }
  closePanel();
}
