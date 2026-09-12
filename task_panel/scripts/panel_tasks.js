/**
 * panel_tasks.js
 * Task rendering, completion countdown, inline edit, delete with undo, pin.
 */

const _countdowns = {};
const _deleteTimers = {};

function renderTaskCard(task, index) {
  const card = document.createElement('div');
  card.className = 'task-card';

  try {
  const taskId = task.id;
  card.id = `card-${taskId}`;
  card.style.animationDelay = `${index * 30}ms`;

  const pri = task.priority || 'medium';
  const badge = typeof getDueBadge === 'function' ? getDueBadge(task) : null;
  const dl = typeof getDeadline === 'function' ? getDeadline(task) : null;

  // tags may be array, JSON string, or comma-separated string
  let tags = task.tags;
  if (typeof tags === 'string') {
    try { tags = JSON.parse(tags); } catch (_) {
      tags = tags.split(',').map(s => s.trim()).filter(Boolean);
    }
  }
  if (!Array.isArray(tags)) tags = [];

  // subtasks may be array or JSON string — .filter on a string crashes the whole list
  let subs = task.subtasks;
  if (typeof subs === 'string') {
    try { subs = JSON.parse(subs); } catch (_) { subs = []; }
  }
  if (!Array.isArray(subs)) subs = [];

  const subDone = subs.filter(s => s && s.completed).length;
  const subPct = subs.length > 0 ? Math.round((subDone / subs.length) * 100) : null;
  const pinned = tags.includes('pinned');

  let html = '<div class="card-inner">';

  html += `
    <div class="card-top">
      <div class="card-title" id="title-${taskId}"
           ondblclick="startEditTitle(${taskId})">${escHtml(task.text || '')}</div>
      <div class="card-actions">
        <button class="card-action-btn pin ${pinned ? 'pinned' : ''}"
                onclick="togglePin(${taskId})" title="${pinned ? 'Unpin' : 'Pin'}">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="${pinned ? 'currentColor' : 'none'}"
               stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 17v5"/><path d="M9 10.76a2 2 0 01-1.11 1.79l-1.78.9A2 2 0 005 15.24V16h14v-.76a2 2 0 00-1.11-1.79l-1.78-.9A2 2 0 0115 10.76V7a1 1 0 011-1 2 2 0 000-4H8a2 2 0 000 4 1 1 0 011 1z"/>
          </svg>
        </button>
        <button class="card-action-btn delete" onclick="startDeleteTask(${taskId})" title="Delete">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.8" stroke-linecap="round">
            <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
          </svg>
        </button>
        <button class="card-action-btn check" id="check-${taskId}"
                onclick="startComplete(${taskId})" title="Complete">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--accent)"
               stroke-width="2.5" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg>
        </button>
      </div>
    </div>
  `;

  if (task.description) {
    html += `<div class="card-desc">${escHtml(task.description)}</div>`;
  }

  html += `<div id="countdown-${taskId}" style="display:none"></div>`;

  if (subs.length > 0) {
    html += `
      <div class="sub-section">
        <div class="sub-header">
          <span class="sub-label">Subtasks</span>
          <span class="sub-count" id="sub-count-${taskId}">${subDone}/${subs.length}</span>
        </div>
        <div style="max-height:80px;overflow-y:auto">
    `;
    subs.forEach(sub => {
      if (!sub) return;
      const done = !!sub.completed;
      const sid = sub.id != null ? sub.id : '';
      html += `
        <div class="sub-row" id="sub-${taskId}-${sid}" onclick="toggleSubtask(${taskId},'${sid}')">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
               stroke="${done ? 'var(--accent)' : 'rgba(255,255,255,0.15)'}"
               stroke-width="2" style="flex-shrink:0">
            ${done
              ? '<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>'
              : '<circle cx="12" cy="12" r="10"/>'}
          </svg>
          <span class="sub-text ${done ? 'done' : ''}">${escHtml(sub.text || '')}</span>
        </div>
      `;
    });
    html += '</div>';
    html += `
      <div class="progress-track">
        <div class="progress-bar">
          <div class="progress-fill" id="progress-${taskId}"
               style="width:${subPct}%;background:${subPct === 100 ? 'var(--success)' : 'var(--accent)'}"></div>
        </div>
        <span class="progress-pct" id="pct-${taskId}">${subPct}%</span>
      </div>
    </div>
    `;
  }

  html += `
    <div class="meta-row">
      <div style="display:flex;align-items:center;gap:4px" onclick="cyclePriority(${taskId})">
        <div class="pri-dot" style="background:${priorityColor(pri)}"></div>
        <span class="pri-label" style="color:${priorityLabelColor(pri)}">${pri}</span>
      </div>
  `;

  if (badge) {
    html += `<span class="badge" style="color:${badge.color};background:${badge.bg};border-color:${badge.border}">${badge.label}</span>`;
  }

  if (dl) {
    html += `<span class="deadline" style="color:${dl.urgent ? 'rgba(255,255,255,0.65)' : 'rgba(255,255,255,0.3)'}">${dl.text}</span>`;
  }

  html += '</div></div>';
  card.innerHTML = html;
  } catch (err) {
    console.error('Failed to render task:', task, err);
    card.innerHTML = `<div class="card-inner"><div class="card-top"><div class="card-title">${escHtml((task && task.text) || 'Task')}</div></div></div>`;
  }
  return card;
}

/* ── Complete with 3s countdown ── */
function startComplete(taskId) {
  const card = document.getElementById(`card-${taskId}`);
  const check = document.getElementById(`check-${taskId}`);
  const title = document.getElementById(`title-${taskId}`);
  if (!card || card.classList.contains('completing')) return;

  title.classList.add('struck');
  card.classList.add('completing');
  check.classList.add('checked');

  let secs = 3;
  const cdEl = document.getElementById(`countdown-${taskId}`);
  cdEl.style.display = 'block';
  cdEl.innerHTML = renderCountdown(secs, taskId);

  _countdowns[taskId] = setInterval(() => {
    secs--;
    if (secs <= 0) {
      clearInterval(_countdowns[taskId]);
      delete _countdowns[taskId];
      finishComplete(taskId);
    } else {
      cdEl.innerHTML = renderCountdown(secs, taskId);
    }
  }, 1000);
}

function renderCountdown(secs, taskId) {
  return `
    <div class="countdown">
      <div class="cd-left">
        <span class="cd-num">${secs}s</span>
        <span class="cd-text">completing</span>
      </div>
      <button class="undo-btn" onclick="undoComplete(${taskId})">Undo</button>
    </div>
  `;
}

function undoComplete(taskId) {
  if (_countdowns[taskId]) {
    clearInterval(_countdowns[taskId]);
    delete _countdowns[taskId];
  }
  const card = document.getElementById(`card-${taskId}`);
  const check = document.getElementById(`check-${taskId}`);
  const title = document.getElementById(`title-${taskId}`);
  if (card) card.classList.remove('completing');
  if (check) check.classList.remove('checked');
  if (title) title.classList.remove('struck');
  const cd = document.getElementById(`countdown-${taskId}`);
  if (cd) { cd.style.display = 'none'; cd.innerHTML = ''; }
}

async function finishComplete(taskId) {
  try { await completeTaskAPI(taskId); } catch {}
  const card = document.getElementById(`card-${taskId}`);
  if (card) {
    card.classList.add('done');
    setTimeout(() => {
      card.remove();
      if (typeof onTaskRemoved === 'function') onTaskRemoved(taskId);
    }, 400);
  }
}

/* ── Delete with 3s undo ── */
function startDeleteTask(taskId) {
  const card = document.getElementById(`card-${taskId}`);
  const title = document.getElementById(`title-${taskId}`);
  if (!card) return;

  title.classList.add('struck');
  card.style.opacity = '0.4';

  let secs = 3;
  const cdEl = document.getElementById(`countdown-${taskId}`);
  cdEl.style.display = 'block';
  cdEl.innerHTML = `
    <div class="countdown" style="background: rgba(255, 120, 120, 0.08); border-color: rgba(255, 120, 120, 0.15);">
      <div class="cd-left">
        <span class="cd-num" style="color: var(--danger);">${secs}s</span>
        <span class="cd-text">deleting</span>
      </div>
      <button class="undo-btn" onclick="undoDelete(${taskId})">Undo</button>
    </div>
  `;

  _deleteTimers[taskId] = setInterval(() => {
    secs--;
    if (secs <= 0) {
      clearInterval(_deleteTimers[taskId]);
      delete _deleteTimers[taskId];
      finishDelete(taskId);
    } else {
      const numEl = cdEl.querySelector('.cd-num');
      if (numEl) numEl.textContent = `${secs}s`;
    }
  }, 1000);
}

function undoDelete(taskId) {
  if (_deleteTimers[taskId]) {
    clearInterval(_deleteTimers[taskId]);
    delete _deleteTimers[taskId];
  }
  const card = document.getElementById(`card-${taskId}`);
  const title = document.getElementById(`title-${taskId}`);
  if (card) card.style.opacity = '';
  if (title) title.classList.remove('struck');
  const cd = document.getElementById(`countdown-${taskId}`);
  if (cd) { cd.style.display = 'none'; cd.innerHTML = ''; }
}

async function finishDelete(taskId) {
  try { await deleteTaskAPI(taskId); } catch {}
  const card = document.getElementById(`card-${taskId}`);
  if (card) {
    card.classList.add('done');
    setTimeout(() => {
      card.remove();
      if (typeof onTaskRemoved === 'function') onTaskRemoved(taskId);
    }, 400);
  }
}

/* ── Inline edit title ── */
function startEditTitle(taskId) {
  const title = document.getElementById(`title-${taskId}`);
  if (!title || title.classList.contains('editing')) return;

  const original = title.textContent;
  title.classList.add('editing');
  title.contentEditable = 'true';
  title.focus();

  const range = document.createRange();
  range.selectNodeContents(title);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);

  const commit = async () => {
    title.classList.remove('editing');
    title.contentEditable = 'false';
    const newText = title.textContent.trim();
    if (!newText || newText === original) {
      title.textContent = original;
      return;
    }
    await updateTaskAPI(taskId, { text: newText });
  };

  const cancel = () => {
    title.classList.remove('editing');
    title.contentEditable = 'false';
    title.textContent = original;
  };

  title.addEventListener('blur', commit, { once: true });
  title.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); title.blur(); }
    if (e.key === 'Escape') { e.preventDefault(); cancel(); }
  }, { once: true });
}

/* ── Cycle priority ── */
async function cyclePriority(taskId) {
  if (!window._allTasks) return;
  const task = window._allTasks.find(t => t.id === taskId);
  if (!task) return;

  const order = ['low', 'medium', 'high'];
  const idx = order.indexOf(task.priority || 'medium');
  const next = order[(idx + 1) % 3];

  task.priority = next;
  const card = document.getElementById(`card-${taskId}`);
  if (card) {
    const dot = card.querySelector('.pri-dot');
    const lbl = card.querySelector('.pri-label');
    if (dot) dot.style.background = priorityColor(next);
    if (lbl) { lbl.style.color = priorityLabelColor(next); lbl.textContent = next; }
  }

  await updateTaskAPI(taskId, { priority: next });
}

/* ── Toggle pin ── */
async function togglePin(taskId) {
  if (!window._allTasks) return;
  const task = window._allTasks.find(t => t.id === taskId);
  if (!task) return;

  let tags = task.tags;
  if (typeof tags === 'string') {
    try { tags = JSON.parse(tags); } catch (_) {
      tags = tags.split(',').map(s => s.trim()).filter(Boolean);
    }
  }
  if (!Array.isArray(tags)) tags = [];
  tags = [...tags];
  const pinned = tags.includes('pinned');

  if (pinned) {
    const idx = tags.indexOf('pinned');
    tags.splice(idx, 1);
  } else {
    tags.push('pinned');
  }

  task.tags = tags;
  await updateTaskAPI(taskId, { tags: tags.join(',') });
  if (typeof reloadTasks === 'function') reloadTasks();
}

/* ── Toggle subtask ── */
async function toggleSubtask(taskId, subId) {
  if (!window._allTasks) return;
  const task = window._allTasks.find(t => t.id === taskId);
  if (!task) return;

  let subtasks = task.subtasks;
  if (typeof subtasks === 'string') {
    try { subtasks = JSON.parse(subtasks); } catch (_) { subtasks = []; }
  }
  if (!Array.isArray(subtasks) || subtasks.length === 0) return;

  const updated = subtasks.map(s =>
    s && String(s.id) === String(subId) ? { ...s, completed: !s.completed } : s
  );
  task.subtasks = updated;

  const subDone = updated.filter(s => s.completed).length;
  const subPct = Math.round((subDone / updated.length) * 100);

  const subRow = document.getElementById(`sub-${taskId}-${subId}`);
  if (subRow) {
    const sub = updated.find(s => s.id === subId);
    const svg = subRow.querySelector('svg');
    const span = subRow.querySelector('.sub-text');
    if (sub.completed) {
      svg.setAttribute('stroke', 'var(--accent)');
      svg.innerHTML = '<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>';
      span.classList.add('done');
    } else {
      svg.setAttribute('stroke', 'rgba(255,255,255,0.15)');
      svg.innerHTML = '<circle cx="12" cy="12" r="10"/>';
      span.classList.remove('done');
    }
  }

  const bar = document.getElementById(`progress-${taskId}`);
  const pct = document.getElementById(`pct-${taskId}`);
  const cnt = document.getElementById(`sub-count-${taskId}`);
  if (bar) {
    bar.style.width = subPct + '%';
    bar.style.background = subPct === 100 ? 'var(--success)' : 'var(--accent)';
  }
  if (pct) pct.textContent = subPct + '%';
  if (cnt) cnt.textContent = `${subDone}/${updated.length}`;

  try { await updateSubtasksAPI(taskId, updated); } catch {}
}