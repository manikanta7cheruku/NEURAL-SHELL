/**
 * panel_tasks.js - Task card rendering and interactions.
 */

const countdowns = {};

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function getDueBadge(task) {
  if (!task.due_date || task.completed) return null;
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const due = new Date(task.due_date + 'T00:00:00');
  const d = Math.round((due - now) / 86400000);
  if (d < 0)   return { label: 'Overdue',  color: 'rgba(255,255,255,0.8)',  bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.08)' };
  if (d === 0) return { label: 'Today',    color: 'rgba(255,255,255,0.75)', bg: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.07)' };
  if (d === 1) return { label: 'Tomorrow', color: 'rgba(255,255,255,0.55)', bg: 'rgba(255,255,255,0.03)', border: 'rgba(255,255,255,0.05)' };
  if (d <= 7) return {
    label: due.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
    color: 'rgba(255,255,255,0.4)', bg: 'rgba(255,255,255,0.02)', border: 'rgba(255,255,255,0.04)',
  };
  return {
    label: due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    color: 'rgba(255,255,255,0.3)', bg: 'rgba(255,255,255,0.02)', border: 'rgba(255,255,255,0.03)',
  };
}

function getDeadline(task) {
  if (!task.due_date || task.completed) return null;
  const ds  = task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59:59`;
  const due = new Date(ds);
  const diff = due - new Date();
  if (diff <= 0) return { text: 'past', urgent: true };
  const m = Math.floor(diff / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return { text: `${d}d ${h % 24}h`, urgent: d <= 1 };
  if (h > 0) return { text: `${h}h ${m % 60}m`, urgent: h <= 3 };
  return { text: `${m}m`, urgent: true };
}

function makeTaskCard(task, index) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.id = `card-${task.id}`;
  card.style.animationDelay = `${index * 40}ms`;

  const pri = task.priority || 'medium';
  const priDot = pri === 'high' ? 'rgba(255,255,255,0.7)' :
                 pri === 'medium' ? 'rgba(255,255,255,0.35)' :
                 'rgba(255,255,255,0.15)';
  const priColor = pri === 'high' ? 'rgba(255,255,255,0.7)' :
                   pri === 'medium' ? 'rgba(255,255,255,0.45)' :
                   'rgba(255,255,255,0.25)';

  const badge = getDueBadge(task);
  const dl = getDeadline(task);
  const subs = task.subtasks || [];
  const subDone = subs.filter(s => s.completed).length;
  const subPct = subs.length > 0 ? Math.round((subDone / subs.length) * 100) : null;

  let html = `<div class="card-inner">`;

  // Top: title + check button
  html += `
    <div class="card-top">
      <div class="card-title" id="title-${task.id}">${escHtml(task.text)}</div>
      <button class="check-btn" id="btn-${task.id}" onclick="startComplete(${task.id})">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round">
          <path d="M20 6L9 17l-5-5"/>
        </svg>
      </button>
    </div>
  `;

  // Description
  if (task.description) {
    html += `<div class="card-desc">${escHtml(task.description)}</div>`;
  }

  // Countdown placeholder
  html += `<div id="countdown-${task.id}" style="display:none"></div>`;

  // Subtasks
  if (subs.length > 0) {
    html += `
      <div class="sub-section">
        <div class="sub-header">
          <span class="sub-label">Subtasks</span>
          <span class="sub-count" id="sub-count-${task.id}">${subDone}/${subs.length}</span>
        </div>
        <div style="max-height:80px;overflow-y:auto">
    `;

    subs.forEach(sub => {
      const done = sub.completed;
      html += `
        <div class="sub-row" id="sub-${task.id}-${sub.id}" onclick="toggleSub(${task.id},'${sub.id}')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
               stroke="${done ? 'var(--accent)' : 'rgba(255,255,255,0.15)'}"
               stroke-width="2" style="flex-shrink:0">
            ${done
              ? '<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>'
              : '<circle cx="12" cy="12" r="10"/>'}
          </svg>
          <span class="sub-text ${done ? 'done' : ''}" style="color:${done ? 'var(--text-4)' : 'var(--text-2)'}">
            ${escHtml(sub.text)}
          </span>
        </div>
      `;
    });

    html += `</div>`;

    // Progress bar
    html += `
      <div class="progress-track">
        <div class="progress-bar">
          <div class="progress-fill" id="progress-${task.id}"
               style="width:${subPct}%;background:${subPct === 100 ? 'rgba(255,255,255,0.45)' : 'var(--accent)'}"></div>
        </div>
        <span class="progress-pct" id="pct-${task.id}">${subPct}%</span>
      </div>
    `;

    html += `</div>`;
  }

  // Meta row
  html += `
    <div class="meta-row">
      <div style="display:flex;align-items:center;gap:4px">
        <div class="pri-dot" style="background:${priDot}"></div>
        <span class="pri-label" style="color:${priColor}">${pri}</span>
      </div>
  `;

  if (badge) {
    html += `<span class="badge" style="color:${badge.color};background:${badge.bg};border-color:${badge.border}">${badge.label}</span>`;
  }

  if (dl) {
    html += `<span class="deadline" style="color:${dl.urgent ? 'rgba(255,255,255,0.65)' : 'rgba(255,255,255,0.3)'}">${dl.text}</span>`;
  }

  html += `</div></div>`;
  card.innerHTML = html;
  return card;
}

function startComplete(taskId) {
  const card  = document.getElementById(`card-${taskId}`);
  const btn   = document.getElementById(`btn-${taskId}`);
  const title = document.getElementById(`title-${taskId}`);
  if (!card || card.classList.contains('completing')) return;

  title.classList.add('struck');
  card.classList.add('completing');
  btn.classList.add('checked');

  let secs = 3;
  const cdEl = document.getElementById(`countdown-${taskId}`);
  cdEl.style.display = 'block';
  cdEl.innerHTML = renderCountdown(secs, taskId);

  countdowns[taskId] = setInterval(() => {
    secs--;
    if (secs <= 0) {
      clearInterval(countdowns[taskId]);
      delete countdowns[taskId];
      doComplete(taskId);
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
  if (countdowns[taskId]) {
    clearInterval(countdowns[taskId]);
    delete countdowns[taskId];
  }
  const card = document.getElementById(`card-${taskId}`);
  const btn = document.getElementById(`btn-${taskId}`);
  const title = document.getElementById(`title-${taskId}`);
  if (card) card.classList.remove('completing');
  if (btn) btn.classList.remove('checked');
  if (title) title.classList.remove('struck');
  const cd = document.getElementById(`countdown-${taskId}`);
  if (cd) { cd.style.display = 'none'; cd.innerHTML = ''; }
}

async function doComplete(taskId) {
  try { await completeTask(taskId); } catch {}

  const card = document.getElementById(`card-${taskId}`);
  if (card) {
    card.classList.add('done');
    setTimeout(() => {
      card.remove();
      if (typeof onTaskCompleted === 'function') onTaskCompleted(taskId);
    }, 450);
  }
}

async function toggleSub(taskId, subId) {
  if (typeof onSubtaskToggle === 'function') {
    onSubtaskToggle(taskId, subId);
  }
}