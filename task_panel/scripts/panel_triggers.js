/**
 * panel_triggers.js
 * Trigger list rendering + inline hotkey editing with conflict detection.
 */

let _allTriggers = [];
let _triggerFilter = 'all';
let _editingTriggerId = null;
let _recordingKeys = new Set();

function setTriggerFilter(f) {
  _triggerFilter = f;
  document.querySelectorAll('#trigger-filters .filter-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.filter === f);
  });
  renderTriggers();
}

function renderTriggers() {
  const list = document.getElementById('trigger-list');
  const empty = document.getElementById('trigger-empty');
  if (!list) return;

  let filtered = _allTriggers;
  if (_triggerFilter === 'hotkey') {
    filtered = _allTriggers.filter(t => t.hotkey);
  } else if (_triggerFilter === 'voice') {
    filtered = _allTriggers.filter(t => t.voice_phrase);
  } else if (_triggerFilter === 'snap') {
    filtered = _allTriggers.filter(t => t.audio_pattern);
  } else if (_triggerFilter === 'workspace') {
    filtered = _allTriggers.filter(t => t.action_type === 'open_workspace');
  }

  if (filtered.length === 0) {
    list.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }

  empty.style.display = 'none';
  list.style.display = 'flex';
  list.innerHTML = '';

  filtered.forEach((trigger, i) => {
    list.appendChild(renderTriggerCard(trigger, i));
  });
}

function renderTriggerCard(trigger, index) {
  const card = document.createElement('div');
  card.className = `trigger-card ${!trigger.enabled ? 'disabled' : ''}`;
  card.id = `trig-${trigger.id}`;
  card.style.animationDelay = `${index * 30}ms`;

  const iconMap = {
    open_app: '<path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><path d="M15 3h6v6"/><path d="M10 14L21 3"/>',
    open_url: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/>',
    open_file: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    open_folder: '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>',
    open_workspace: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    run_command: '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    seven_action: '<circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v6M4.22 4.22l4.24 4.24m7.08 7.08l4.24 4.24M1 12h6m6 0h6M4.22 19.78l4.24-4.24m7.08-7.08l4.24-4.24"/>',
  };

  const actionIcon = iconMap[trigger.action_type] || iconMap.seven_action;

  let methodBadge = '';
  if (trigger.hotkey) {
    methodBadge = `
      <span class="trigger-badge hotkey">
        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"/>
        </svg>
        ${formatHotkey(trigger.hotkey)}
      </span>
    `;
  } else if (trigger.voice_phrase) {
    methodBadge = `
      <span class="trigger-badge">
        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8"/>
        </svg>
        "${escHtml(trigger.voice_phrase)}"
      </span>
    `;
  } else if (trigger.audio_pattern) {
    const count = trigger.audio_pattern.split('_')[0];
    methodBadge = `
      <span class="trigger-badge">
        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M2 12h3l3-9 4 18 3-9h5"/>
        </svg>
        ${count} snap${count > 1 ? 's' : ''}
      </span>
    `;
  }

  card.innerHTML = `
    <div class="trigger-icon">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)"
           stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        ${actionIcon}
      </svg>
    </div>
    <div class="trigger-info">
      <div class="trigger-name">${escHtml(trigger.name)}</div>
      <div class="trigger-meta">
        ${methodBadge}
        ${trigger.fire_count > 0 ? `<span class="trigger-fire-count">${trigger.fire_count} fires</span>` : ''}
      </div>
      <div class="hotkey-edit-wrap" id="edit-${trigger.id}">
        <input type="text" class="hotkey-edit-input" id="hotkey-input-${trigger.id}"
               placeholder="Press keys..." readonly>
        <div class="hotkey-edit-hint">Press key combo to record. Esc to cancel.</div>
        <div class="hotkey-edit-error" id="hotkey-error-${trigger.id}"></div>
      </div>
    </div>
    <div class="trigger-actions">
      ${trigger.hotkey ? `
        <button class="trigger-action-btn" onclick="startEditHotkey(${trigger.id})" title="Edit hotkey">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.8" stroke-linecap="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
      ` : ''}
      <button class="trigger-action-btn fire" onclick="fireTriggerPanel(${trigger.id})" title="Test">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
      </button>
    </div>
  `;
  return card;
}

/* ── Inline hotkey editor ── */
function startEditHotkey(triggerId) {
  if (_editingTriggerId && _editingTriggerId !== triggerId) {
    cancelEditHotkey(_editingTriggerId);
  }
  _editingTriggerId = triggerId;

  const wrap = document.getElementById(`edit-${triggerId}`);
  const input = document.getElementById(`hotkey-input-${triggerId}`);
  const error = document.getElementById(`hotkey-error-${triggerId}`);
  if (!wrap || !input) return;

  wrap.classList.add('visible');
  input.value = '';
  input.classList.add('recording');
  error.classList.remove('visible');
  input.focus();

  _recordingKeys.clear();

  const keyDownHandler = (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.key === 'Escape') {
      cancelEditHotkey(triggerId);
      return;
    }

    const parts = [];
    if (e.ctrlKey) parts.push('ctrl');
    if (e.shiftKey) parts.push('shift');
    if (e.altKey) parts.push('alt');
    if (e.metaKey) parts.push('win');

    const key = e.key.toLowerCase();
    if (!['control', 'shift', 'alt', 'meta'].includes(key)) {
      parts.push(key === ' ' ? 'space' : key);
      const combo = parts.join('+');
      input.value = formatHotkey(combo);
      input.dataset.rawCombo = combo;

      setTimeout(() => commitHotkey(triggerId, combo), 300);
    }
  };

  input._keyHandler = keyDownHandler;
  document.addEventListener('keydown', keyDownHandler, true);
}

function cancelEditHotkey(triggerId) {
  const wrap = document.getElementById(`edit-${triggerId}`);
  const input = document.getElementById(`hotkey-input-${triggerId}`);
  if (input && input._keyHandler) {
    document.removeEventListener('keydown', input._keyHandler, true);
  }
  if (wrap) wrap.classList.remove('visible');
  _editingTriggerId = null;
}

async function commitHotkey(triggerId, combo) {
  const input = document.getElementById(`hotkey-input-${triggerId}`);
  const error = document.getElementById(`hotkey-error-${triggerId}`);
  if (!input) return;

  input.classList.remove('recording');

  const result = await editHotkeyInline(triggerId, combo);
  if (result.ok) {
    const trigger = _allTriggers.find(t => t.id === triggerId);
    if (trigger) trigger.hotkey = result.trigger.hotkey;
    setTimeout(() => {
      cancelEditHotkey(triggerId);
      renderTriggers();
    }, 400);
  } else {
    error.textContent = result.error || 'Update failed';
    error.classList.add('visible');
    input.classList.add('recording');
  }
}

async function fireTriggerPanel(triggerId) {
  const card = document.getElementById(`trig-${triggerId}`);
  if (card) {
    card.style.opacity = '0.6';
    setTimeout(() => { card.style.opacity = ''; }, 800);
  }
  await fireTrigger(triggerId);
}