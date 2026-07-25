/**
 * panel_app.js - Main panel application logic.
 */

let allTasks = [];
let tasks = [];
let schedules = [];
let currentFilter = 'all';
let sevenAlive = false;

// Initialize
window.addEventListener('DOMContentLoaded', () => {
  requestAnimationFrame(() => {
    setTimeout(() => document.getElementById('panel').classList.add('open'), 30);
  });

  loadAll();

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePanel();
    const n = parseInt(e.key);
    if (n >= 1 && n <= 9 && tasks[n - 1]) startComplete(tasks[n - 1].id);
  });

  // Quick add
  const quickInput = document.getElementById('quick-input');
  if (quickInput) {
    quickInput.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter' && quickInput.value.trim()) {
        const text = quickInput.value.trim();
        quickInput.value = '';
        quickInput.placeholder = 'Adding...';
        const ok = await createTask(text);
        quickInput.placeholder = ok ? 'Added! Type another...' : 'Failed. Try again...';
        setTimeout(() => { quickInput.placeholder = 'Quick add task... (Enter to save)'; }, 1500);
        if (ok) loadAll();
      }
    });
  }

  // Search
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      applyFilter();
    });
  }

  // Periodic refresh
  setInterval(loadAll, 15000);
});

async function loadAll() {
  const [taskData, statsData, schedData, alive] = await Promise.all([
    fetchTasks(),
    fetchStats(),
    fetchSchedules(),
    isSevenAlive(),
  ]);

  allTasks = taskData;
  schedules = schedData;
  sevenAlive = alive;

  updateStats(statsData);
  updateSevenStatus(alive);
  updateFilterCounts();
  updateSchedules();
  applyFilter();

  document.getElementById('loading').style.display = 'none';
}

function updateStats(s) {
  document.getElementById('stat-pending').textContent = s.pending ?? 0;
  document.getElementById('stat-today').textContent = s.due_today ?? 0;
  document.getElementById('stat-overdue').textContent = s.overdue ?? 0;
  document.getElementById('header-sub').textContent = `${s.pending} pending`;
}

function updateSevenStatus(alive) {
  const dot = document.getElementById('seven-dot');
  if (dot) {
    dot.className = `seven-dot ${alive ? 'alive' : 'dead'}`;
    dot.title = alive ? 'Seven is running' : 'Seven is not running';
  }
}

function updateFilterCounts() {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const todayCount = allTasks.filter(t => t.due_date &&
    new Date(t.due_date + 'T00:00:00').getTime() <= today.getTime()).length;
  const overdueCount = allTasks.filter(t => t.due_date &&
    new Date(t.due_date + 'T00:00:00').getTime() < today.getTime()).length;

  document.getElementById('cnt-all').textContent = allTasks.length;
  document.getElementById('cnt-today').textContent = todayCount;
  document.getElementById('cnt-overdue').textContent = overdueCount;
}

function updateSchedules() {
  const container = document.getElementById('sched-list');
  const section = document.getElementById('sched-section');
  if (!container || !section) return;

  if (schedules.length === 0) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  container.innerHTML = '';

  schedules.forEach(s => {
    const type = s.type || 'reminder';
    const icons = {
      reminder: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
      alarm:    '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M5 3L2 6"/><path d="M22 6l-3-3"/>',
      timer:    '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
      event:    '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    };

    const remain = timeRemaining(s.time);
    const timeStr = formatSchedTime(s.time);

    const card = document.createElement('div');
    card.className = 'sched-card';
    card.innerHTML = `
      <div class="sched-icon">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
             stroke="var(--text-3)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          ${icons[type] || icons.reminder}
        </svg>
      </div>
      <div class="sched-info">
        <div class="sched-msg">${escHtml(s.message)}</div>
        <div class="sched-time">${timeStr}</div>
      </div>
      ${remain ? `<div class="sched-remain">${remain}</div>` : ''}
    `;
    container.appendChild(card);
  });
}

function timeRemaining(iso) {
  const diff = new Date(iso) - new Date();
  if (diff <= 0) return null;
  const m = Math.floor(diff / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ${h % 24}h`;
  if (h > 0) return `${h}h ${m % 60}m`;
  return `${m}m`;
}

function formatSchedTime(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function setFilter(f) {
  currentFilter = f;
  document.querySelectorAll('.filter-tab').forEach(c => {
    c.classList.toggle('active', c.dataset.filter === f);
  });
  applyFilter();
}

function applyFilter() {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const searchVal = (document.getElementById('search-input')?.value || '').toLowerCase();

  let filtered = allTasks;

  if (currentFilter === 'today') {
    filtered = allTasks.filter(t => t.due_date &&
      new Date(t.due_date + 'T00:00:00').getTime() <= today.getTime());
  } else if (currentFilter === 'overdue') {
    filtered = allTasks.filter(t => t.due_date &&
      new Date(t.due_date + 'T00:00:00').getTime() < today.getTime());
  }

  if (searchVal) {
    filtered = filtered.filter(t =>
      (t.text || '').toLowerCase().includes(searchVal) ||
      (t.description || '').toLowerCase().includes(searchVal)
    );
  }

  tasks = filtered;
  renderTasks();
}

function renderTasks() {
  const list = document.getElementById('task-list');
  const empty = document.getElementById('empty');

  if (!tasks || tasks.length === 0) {
    list.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }

  empty.style.display = 'none';
  list.style.display = 'flex';
  list.innerHTML = '';
  tasks.forEach((t, i) => list.appendChild(makeTaskCard(t, i)));
}

function toggleSearch() {
  const wrap = document.getElementById('search-wrap');
  const input = document.getElementById('search-input');
  const visible = wrap.classList.contains('visible');
  if (visible) {
    wrap.classList.remove('visible');
    input.value = '';
    applyFilter();
  } else {
    wrap.classList.add('visible');
    setTimeout(() => input.focus(), 50);
  }
}

// Callbacks from panel_tasks.js
function onTaskCompleted(taskId) {
  allTasks = allTasks.filter(t => t.id !== taskId);
  tasks = tasks.filter(t => t.id !== taskId);
  updateFilterCounts();
  if (tasks.length === 0) renderTasks();
  fetchStats().then(updateStats);
}

async function onSubtaskToggle(taskId, subId) {
  const task = allTasks.find(t => t.id === taskId);
  if (!task || !task.subtasks) return;

  const updated = task.subtasks.map(s =>
    s.id === subId ? { ...s, completed: !s.completed } : s
  );
  task.subtasks = updated;

  const inFiltered = tasks.find(t => t.id === taskId);
  if (inFiltered) inFiltered.subtasks = updated;

  const subDone = updated.filter(s => s.completed).length;
  const subPct = Math.round((subDone / updated.length) * 100);

  // Update DOM directly without re-rendering
  const subRow = document.getElementById(`sub-${taskId}-${subId}`);
  if (subRow) {
    const sub = updated.find(s => s.id === subId);
    const svg = subRow.querySelector('svg');
    const span = subRow.querySelector('.sub-text');
    if (sub.completed) {
      svg.setAttribute('stroke', 'var(--accent)');
      svg.innerHTML = '<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>';
      span.classList.add('done');
      span.style.color = 'var(--text-4)';
    } else {
      svg.setAttribute('stroke', 'rgba(255,255,255,0.15)');
      svg.innerHTML = '<circle cx="12" cy="12" r="10"/>';
      span.classList.remove('done');
      span.style.color = 'var(--text-2)';
    }
  }

  const bar = document.getElementById(`progress-${taskId}`);
  const pct = document.getElementById(`pct-${taskId}`);
  const cnt = document.getElementById(`sub-count-${taskId}`);
  if (bar) {
    bar.style.width = subPct + '%';
    bar.style.background = subPct === 100 ? 'rgba(255,255,255,0.45)' : 'var(--accent)';
  }
  if (pct) pct.textContent = subPct + '%';
  if (cnt) cnt.textContent = `${subDone}/${updated.length}`;

  try { await updateSubtasks(taskId, updated); } catch {}
}

async function closeAllWindows_click() {
  const btn = document.getElementById('close-all-btn');
  if (btn) {
    btn.textContent = 'Closing...';
    btn.disabled = true;
  }
  const ok = await closeAllWindows();
  if (btn) {
    btn.textContent = ok ? 'Done' : 'Failed';
    btn.disabled = false;
    setTimeout(() => {
      btn.innerHTML = `
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
        Close All
      `;
    }, 1500);
  }
}

function closePanel() {
  Object.values(countdowns).forEach(clearInterval);
  document.getElementById('panel').classList.remove('open');
  setTimeout(() => {
    if (window.electronAPI?.closePanel) window.electronAPI.closePanel();
    else window.close();
  }, 400);
}

function openSevenTasks() {
  if (window.electronAPI?.openSevenTasks) window.electronAPI.openSevenTasks();
  closePanel();
}