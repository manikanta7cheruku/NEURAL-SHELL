/**
 * panel_triggers.js
 * Comprehensive Trigger rendering, filtering, active test-firing,
 * and a premium live Hotkey recording interface.
 */

let _triggerFilter = 'all';
let _editingTriggerId = null;

function triggerIdOf(t) {
  if (!t) return null;
  return t.id != null ? t.id : (t.trigger_id != null ? t.trigger_id : null);
}

function setTriggerFilter(filter) {
  _triggerFilter = filter;
  document.querySelectorAll('#trigger-filters .filter-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.filter === filter);
  });
  renderTriggers();
}

function renderTriggers() {
  const list = document.getElementById('trigger-list');
  const empty = document.getElementById('trigger-empty');
  if (!list) return;

  const triggers = window._allTriggers || [];
  let filtered = triggers;

  if (_triggerFilter !== 'all') {
    filtered = triggers.filter(t => {
      if (!t) return false;
      const rawType = String(t.type || t.trigger_type || t.kind || t.category || '').toLowerCase();
      const rawName = String(t.name || '').toLowerCase();

      if (_triggerFilter === 'hotkey') {
        return rawType.includes('hotkey') || rawType.includes('key') || rawType.includes('shortcut') || Boolean(t.hotkey);
      }
      if (_triggerFilter === 'voice') {
        return rawType.includes('voice') || rawType.includes('speech') || rawType.includes('audio') || rawName.includes('voice');
      }
      if (_triggerFilter === 'snap') {
        return rawType.includes('snap') || rawType.includes('anchor') || rawType.includes('dock') || rawName.includes('snap');
      }
      if (_triggerFilter === 'workspace') {
        return rawType.includes('workspace') || rawType.includes('process') || rawType.includes('app') || rawType.includes('window');
      }
      return rawType === _triggerFilter || rawType.includes(_triggerFilter);
    });
  }

  if (filtered.length === 0) {
    list.style.display = 'none';
    if (empty) empty.style.display = 'flex';
    return;
  }

  if (empty) empty.style.display = 'none';
  list.style.display = 'flex';
  list.innerHTML = '';

  filtered.forEach((t, i) => {
    try {
      list.appendChild(renderTriggerCard(t, i));
    } catch (err) {
      console.error('Failed to append trigger card:', t, err);
    }
  });
}

function renderTriggerCard(t, index) {
  const card = document.createElement('div');
  card.className = `trigger-card ${(t && t.status) === 'disabled' ? 'disabled' : ''}`;

  try {
  const id = triggerIdOf(t);
  if (id == null) throw new Error('trigger missing id/trigger_id');

  card.id = `trigger-${id}`;
  card.style.animationDelay = `${index * 25}ms`;

  const type = (t.type || 'hotkey').toLowerCase();
  const icon = getTriggerIcon(type);
  const isHotkey = type === 'hotkey';
  const rawBadge = isHotkey
    ? (typeof formatHotkey === 'function' ? formatHotkey(t.hotkey) : (t.hotkey || 'hotkey'))
    : (t.type || type);
  const badgeVal = rawBadge == null ? type : String(rawBadge);

  card.innerHTML = `
    <div style="display:flex; align-items:center; width:100%; gap:12px;">
      <div class="trigger-icon">${icon}</div>
      <div class="trigger-info">
        <div class="trigger-name">${escHtml(t.name || 'Unnamed Trigger')}</div>
        <div class="trigger-meta">
          <span class="trigger-badge ${isHotkey ? 'hotkey' : ''}">${escHtml(badgeVal)}</span>
          ${t.fire_count ? `<span class="trigger-fire-count">${t.fire_count} fires</span>` : ''}
        </div>
      </div>
      <div class="trigger-actions">
        ${isHotkey ? `
          <button class="trigger-action-btn edit" onclick="startHotkeyRecording(${id})" title="Edit Hotkey">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 113 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </button>
        ` : ''}
        <button class="trigger-action-btn fire" onclick="testFireTrigger(${id}, event)" title="Fire Trigger">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="hotkey-edit-wrap" id="hk-wrap-${id}">
      <input type="text" class="hotkey-edit-input" id="hk-input-${id}"
             placeholder="Press your hotkey combo..." readonly spellcheck="false" />
      <div class="hotkey-edit-hint">Press Esc to cancel. Press Enter to save.</div>
      <div class="hotkey-edit-error" id="hk-error-${id}"></div>
    </div>
  `;
  } catch (err) {
    console.error('Failed to render trigger:', t, err);
    const fallbackId = triggerIdOf(t);
    card.id = fallbackId != null ? `trigger-${fallbackId}` : `trigger-unknown-${index}`;
    card.innerHTML = `
      <div style="display:flex;align-items:center;width:100%;gap:12px;">
        <div class="trigger-info">
          <div class="trigger-name">${escHtml((t && t.name) || 'Trigger')}</div>
          <div class="trigger-meta"><span class="trigger-badge">error</span></div>
        </div>
      </div>
    `;
  }

  return card;
}

function getTriggerIcon(type) {
  if (type === 'hotkey') {
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M18 12h.01M7 16h10"/></svg>`;
  }
  if (type === 'voice') {
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"/></svg>`;
  }
  if (type === 'snap' || type === 'anchor') {
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg>`;
  }
  return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>`;
}

async function testFireTrigger(id, event) {
  if (event) {
    event.stopPropagation();
    const btn = event.currentTarget;
    btn.style.transform = 'scale(0.85)';
    setTimeout(() => { btn.style.transform = ''; }, 150);
  }
  await fireTrigger(id);
}

/* ── Live Key Capture Controller ── */
let _activeKeysPressed = new Set();
let _recordedComboString = '';

function startHotkeyRecording(triggerId) {
  if (_editingTriggerId) {
    cancelHotkeyRecording(_editingTriggerId);
  }

  _editingTriggerId = triggerId;
  _recordedComboString = '';
  _activeKeysPressed.clear();

  const wrap = document.getElementById(`hk-wrap-${triggerId}`);
  const input = document.getElementById(`hk-input-${triggerId}`);
  const errEl = document.getElementById(`hk-error-${triggerId}`);

  if (!wrap || !input) return;

  wrap.classList.add('visible');
  input.classList.add('recording');
  input.value = 'Recording keys...';
  if (errEl) errEl.classList.remove('visible');

  // Capture user inputs safely inside target elements
  input.focus();
  input.onkeydown = handleHotkeyKeyDown;
  input.onkeyup = handleHotkeyKeyUp;
}

function cancelHotkeyRecording(triggerId) {
  const wrap = document.getElementById(`hk-wrap-${triggerId}`);
  const input = document.getElementById(`hk-input-${triggerId}`);
  if (wrap) wrap.classList.remove('visible');
  if (input) {
    input.classList.remove('recording');
    input.onkeydown = null;
    input.onkeyup = null;
  }
  if (_editingTriggerId === triggerId) _editingTriggerId = null;
}

function handleHotkeyKeyDown(e) {
  e.preventDefault();
  e.stopPropagation();

  const key = e.key;

  if (key === 'Escape') {
    cancelHotkeyRecording(_editingTriggerId);
    return;
  }

  if (key === 'Enter' && _recordedComboString) {
    saveHotkeyCombo(_editingTriggerId, _recordedComboString);
    return;
  }

  const parts = [];
  if (e.ctrlKey) parts.push('ctrl');
  if (e.shiftKey) parts.push('shift');
  if (e.altKey) parts.push('alt');
  if (e.metaKey) parts.push('win');

  // Extract non-modifier key signatures
  const primaryKeys = ['Control', 'Shift', 'Alt', 'Meta', 'Windows'];
  if (!primaryKeys.includes(key) && key !== ' ') {
    parts.push(key.toLowerCase());
  } else if (key === ' ') {
    parts.push('space');
  }

  if (parts.length > 0) {
    _recordedComboString = parts.join('+');
    e.target.value = formatHotkey(_recordedComboString);
  }
}

function handleHotkeyKeyUp(e) {
  e.preventDefault();
  e.stopPropagation();
}

async function saveHotkeyCombo(id, combo) {
  const input = document.getElementById(`hk-input-${id}`);
  const errEl = document.getElementById(`hk-error-${id}`);
  
  if (input) {
    input.placeholder = 'Saving changes...';
    input.value = '';
    input.classList.remove('recording');
  }

  const res = await editHotkeyInline(id, combo);
  if (res && res.ok) {
    cancelHotkeyRecording(id);
    loadAll(); // Hot-reload triggers
  } else {
    if (errEl) {
      errEl.textContent = res?.error || 'Failed to save.';
      errEl.classList.add('visible');
    }
    if (input) input.classList.add('recording');
  }
}