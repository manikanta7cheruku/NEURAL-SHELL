/**
 * panel_schedules.js
 * Active schedule list with countdown chips.
 */

let _allSchedules = [];

function renderSchedules() {
  const list = document.getElementById('schedule-list');
  const empty = document.getElementById('schedule-empty');
  if (!list) return;

  if (_allSchedules.length === 0) {
    list.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }

  empty.style.display = 'none';
  list.style.display = 'flex';
  list.innerHTML = '';

  _allSchedules.sort((a, b) => new Date(a.time) - new Date(b.time));

  _allSchedules.forEach((sched, i) => {
    list.appendChild(renderScheduleCard(sched, i));
  });
}

function renderScheduleCard(sched, index) {
  const card = document.createElement('div');
  card.className = 'sched-card';
  card.style.animationDelay = `${index * 30}ms`;

  const type = sched.type || 'reminder';
  const iconMap = {
    reminder: '<path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>',
    alarm: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M5 3L2 6"/><path d="M22 6l-3-3"/>',
    timer: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    event: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
  };

  const remain = timeRemaining(sched.time);
  const urgent = isUrgent(sched.time);
  const timeStr = formatSchedTime(sched.time);

  card.innerHTML = `
    <div class="sched-icon">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)"
           stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        ${iconMap[type] || iconMap.reminder}
      </svg>
    </div>
    <div class="sched-info">
      <div class="sched-msg">${escHtml(sched.message || 'Untitled')}</div>
      <div class="sched-time">${timeStr}</div>
    </div>
    ${remain ? `<div class="sched-remain ${urgent ? 'urgent' : ''}">${remain}</div>` : ''}
    <div class="sched-actions">
      <button class="sched-action-btn" onclick="dismissSchedule(${sched.id})" title="Dismiss">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>
    </div>
  `;
  return card;
}

async function dismissSchedule(schedId) {
  const card = document.querySelector(`.sched-card`);
  await cancelSchedule(schedId);
  _allSchedules = _allSchedules.filter(s => s.id !== schedId);
  renderSchedules();
  updateTabCounts();
}