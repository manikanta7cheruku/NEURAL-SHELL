/**
 * panel_schedules.js
 * Active Schedules rendering and live second-by-second countdown clock logic.
 */

let _scheduleInterval = null;

function renderSchedules() {
  const list = document.getElementById('schedule-list');
  const empty = document.getElementById('schedule-empty');
  if (!list) return;

  const schedules = window._allSchedules || [];

  if (schedules.length === 0) {
    list.style.display = 'none';
    empty.style.display = 'flex';
    stopSchedulesTimer();
    return;
  }

  empty.style.display = 'none';
  list.style.display = 'flex';
  list.innerHTML = '';

  schedules.forEach((s, i) => {
    list.appendChild(renderScheduleCard(s, i));
  });

  startSchedulesTimer();
}

function renderScheduleCard(s, index) {
  const card = document.createElement('div');
  card.className = 'sched-card';
  card.id = `sched-${s.id}`;
  card.style.animationDelay = `${index * 30}ms`;

  const remains = timeRemaining(s.time);
  const isUrge = remains && isUrgent(s.time);
  const remainText = remains ? remains : 'past';

  card.innerHTML = `
    <div class="sched-icon">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
      </svg>
    </div>
    <div class="sched-info">
      <div class="sched-msg">${escHtml(s.message || 'Reminder')}</div>
      <div class="sched-time">${formatSchedTime(s.time)}</div>
    </div>
    <span class="sched-remain ${isUrge ? 'urgent' : ''}" id="sched-timer-${s.id}">${remainText}</span>
    <div class="sched-actions">
      <button class="sched-action-btn cancel" onclick="executeCancelSchedule(${s.id}, event)" title="Cancel Schedule">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="12"/>
        </svg>
      </button>
    </div>
  `;

  return card;
}

async function executeCancelSchedule(id, event) {
  if (event) event.stopPropagation();
  const card = document.getElementById(`sched-${id}`);
  if (card) {
    card.style.opacity = '0.3';
    card.style.pointerEvents = 'none';
  }
  const ok = await cancelSchedule(id);
  if (ok) {
    window._allSchedules = (window._allSchedules || []).filter(s => s.id !== id);
    renderSchedules();
  } else {
    if (card) {
      card.style.opacity = '';
      card.style.pointerEvents = '';
    }
  }
}

function startSchedulesTimer() {
  if (_scheduleInterval) return;
  _scheduleInterval = setInterval(updateSchedulesClocks, 1000);
}

function stopSchedulesTimer() {
  if (_scheduleInterval) {
    clearInterval(_scheduleInterval);
    _scheduleInterval = null;
  }
}

function updateSchedulesClocks() {
  const schedules = window._allSchedules || [];
  schedules.forEach(s => {
    const el = document.getElementById(`sched-timer-${s.id}`);
    if (!el) return;
    const remains = timeRemaining(s.time);
    const isUrge = remains && isUrgent(s.time);
    
    el.textContent = remains ? remains : 'past';
    el.classList.toggle('urgent', isUrge);
  });
}