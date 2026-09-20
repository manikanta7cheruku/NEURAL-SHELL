/**
 * panel_triggers.js
 * Trigger rendering, filtering, test-firing, enable/disable toggle,
 * delete, and live Hotkey recording.
 *
 * Classification uses the CONFIRMED real backend/routes/triggers.py
 * schema (hotkey / voice_phrase / audio_pattern / action_type) instead
 * of guessed field names. Falls back to guessed fields only if none of
 * the confirmed ones are present, in case the compact endpoint differs.
 */

let _triggerFilter = 'all';
const _deleteConfirm = {};

const OFFLINE_TRIGGER_QUEUE_KEY = 'offlineTriggerActions';
// Trigger state override system removed - using API fallbacks instead

async function isSevenOnline() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 150); // fast 150ms timeout
    const resp = await fetch('http://127.0.0.1:7777/api/status', { signal: controller.signal });
    clearTimeout(timeout);
    return resp.ok;
  } catch (e) {
    return false;
  }
}

async function isSevenOnline() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60); // ultra-fast 60ms probe
    const resp = await fetch('http://127.0.0.1:7777/api/status', { signal: controller.signal });
    clearTimeout(timeout);
    return resp.ok;
  } catch (e) {
    return false;
  }
}

async function safeFireTrigger(id) {
  const online = await isSevenOnline();
  
  if (online) {
    try {
      if (typeof sevenAPI === 'function') {
        const r = await sevenAPI(`/triggers/${id}/fire`, 'POST');
        if (r && r.success) return r;
      }
    } catch (err) {}
  }
  
  try {
    if (typeof panelAPI === 'function') {
      return await panelAPI(`/panel/triggers/${id}/fire`, 'POST');
    } else {
      const resp = await fetch(`http://127.0.0.1:7778/panel/triggers/${id}/fire`, { method: 'POST' });
      return await resp.json();
    }
  } catch (err) {
    console.error('[PANEL] Fire trigger failed:', err);
    return null;
  }
}

async function safeToggleTriggerEnabled(id, enabled) {
  const online = await isSevenOnline();

  if (online) {
    try {
      if (typeof sevenAPI === 'function') {
        const r = await sevenAPI(`/triggers/${id}`, 'PUT', { enabled });
        if (r && r.success) return r;
      }
    } catch (err) {}
  }

  try {
    if (typeof panelAPI === 'function') {
      return await panelAPI(`/panel/triggers/${id}`, 'PUT', { enabled });
    } else {
      const resp = await fetch(`http://127.0.0.1:7778/panel/triggers/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      return await resp.json();
    }
  } catch (err) {
    console.error('[PANEL] Toggle trigger failed:', err);
    return null;
  }
}

async function safeDeleteTrigger(id) {
  const online = await isSevenOnline();

  if (online) {
    try {
      if (typeof sevenAPI === 'function') {
        const r = await sevenAPI(`/triggers/${id}`, 'DELETE');
        if (r && r.success) return r;
      }
    } catch (err) {}
  }

  try {
    if (typeof panelAPI === 'function') {
      return await panelAPI(`/panel/triggers/${id}`, 'DELETE');
    } else {
      const resp = await fetch(`http://127.0.0.1:7778/panel/triggers/${id}`, { method: 'DELETE' });
      return await resp.json();
    }
  } catch (err) {
    console.error('[PANEL] Delete trigger failed:', err);
    return null;
  }
}

function queueOfflineAction(action) {
  const queue = JSON.parse(localStorage.getItem(OFFLINE_TRIGGER_QUEUE_KEY) || '[]');
  queue.push(action);
  localStorage.setItem(OFFLINE_TRIGGER_QUEUE_KEY, JSON.stringify(queue));
}

function getOfflineTriggerQueue() {
  return JSON.parse(localStorage.getItem(OFFLINE_TRIGGER_QUEUE_KEY) || '[]');
}

function clearOfflineTriggerQueue() {
  localStorage.removeItem(OFFLINE_TRIGGER_QUEUE_KEY);
}

function triggerIdOf(t) {
  if (!t) return null;
  return t.id != null ? t.id : (t.trigger_id != null ? t.trigger_id : null);
}

function triggerIsEnabled(t) {
  if (!t) return true;
  if (t.status === 'disabled') return false;
  if (t.enabled === false || t.enabled === 0 || t.enabled === '0') return false;
  return true;
}

function classifyTrigger(t) {
  // Used for FILTER TAB matching only. Action category takes priority
  // over activation method: an open_workspace trigger should file under
  // "Workspace" even when it's also bound to a hotkey — those are two
  // independent things in the real schema, and workspace triggers are
  // commonly activated by hotkey, which is exactly why this was broken.
  if (!t) return 'other';
  if (t.action_type === 'open_workspace') return 'workspace';
  if (t.audio_pattern) return 'snap';
  if (t.voice_phrase) return 'voice';
  if (t.hotkey) return 'hotkey';

  const raw = String(t.type || t.trigger_type || t.kind || t.category || '').toLowerCase();
  if (raw.includes('voice') || raw.includes('speech')) return 'voice';
  if (raw.includes('snap') || raw.includes('audio') || raw.includes('anchor')) return 'snap';
  if (raw.includes('hotkey') || raw.includes('key') || raw.includes('shortcut')) return 'hotkey';
  if (raw.includes('workspace') || raw.includes('window')) return 'workspace';
  return 'other';
}

function activationMethod(t) {
  // Used for the CARD BADGE/ICON only — shows what actually fires the
  // trigger, independent of its action category, so a workspace trigger
  // bound to a hotkey still visibly shows its hotkey on the card.
  if (!t) return 'other';
  if (t.audio_pattern) return 'snap';
  if (t.voice_phrase) return 'voice';
  if (t.hotkey) return 'hotkey';
  if (t.action_type === 'open_workspace') return 'workspace';
  return 'other';
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
  const filtered = _triggerFilter === 'all'
    ? triggers
    : triggers.filter(t => classifyTrigger(t) === _triggerFilter);

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
  const enabled = triggerIsEnabled(t);
  card.className = `trigger-card ${!enabled ? 'disabled' : ''}`;

  try {
    const id = triggerIdOf(t);
    if (id == null) throw new Error('trigger missing id/trigger_id');

    card.id = `trigger-${id}`;
    card.style.animationDelay = `${index * 25}ms`;

    const category = activationMethod(t);
    const icon = getTriggerIcon(category);
    const isHotkey = category === 'hotkey';

    let badgeVal;
    if (category === 'hotkey') {
      badgeVal = (typeof formatHotkey === 'function' ? formatHotkey(t.hotkey) : t.hotkey) || 'hotkey';
    } else if (category === 'voice') {
      badgeVal = t.voice_phrase ? `"${t.voice_phrase}"` : 'voice';
    } else if (category === 'snap') {
      badgeVal = t.audio_pattern ? t.audio_pattern.replace(/_/g, ' ') : 'snap';
    } else if (category === 'workspace') {
      badgeVal = 'workspace';
    } else {
      badgeVal = t.action_type || t.type || 'trigger';
    }

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
          <button class="trigger-action-btn fire" onclick="testFireTrigger(${id}, event)" title="Fire Trigger">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
          </button>
          <button class="trigger-action-btn delete" id="trig-del-${id}" onclick="handleDeleteTrigger(${id}, event)" title="Delete">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
            </svg>
          </button>
          <button class="mini-toggle ${enabled ? 'on' : ''}" id="trig-toggle-${id}" onclick="handleToggleTrigger(${id}, event)" title="${enabled ? 'Disable trigger' : 'Enable trigger'}" aria-pressed="${enabled}">
            <span class="mini-toggle-knob"></span>
          </button>
        </div>
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

function getTriggerIcon(category) {
  if (category === 'hotkey') {
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M18 12h.01M7 16h10"/></svg>`;
  }
  if (category === 'voice') {
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"/></svg>`;
  }
  if (category === 'snap') {
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg>`;
  }
  if (category === 'workspace') {
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`;
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
  const result = await safeFireTrigger(id);
  if (!result || !result.success) {
    console.warn('[PANEL] Offline trigger execution failed:', result);
    return;
  }
  console.log('[PANEL] Trigger fired successfully:', id);
}

async function handleToggleTrigger(id, event) {
  if (event) event.stopPropagation();
  const t = (window._allTriggers || []).find(x => triggerIdOf(x) === id);
  if (!t) return;

  const next = !triggerIsEnabled(t);

  const btn = document.getElementById(`trig-toggle-${id}`);
  const card = document.getElementById(`trigger-${id}`);
  if (btn) { btn.classList.toggle('on', next); btn.setAttribute('aria-pressed', String(next)); }
  if (card) card.classList.toggle('disabled', !next);

  // Update the trigger object to reflect the new state for consistency
  t.enabled = next;
  t.status = next ? 'active' : 'disabled';

  const ok = await safeToggleTriggerEnabled(id, next);
  if (!ok) {
    // Queue the toggle action as last resort if both Seven and panel server are unavailable
    queueOfflineAction({ type: 'toggle', triggerId: id, payload: { enabled: next } });
  } else {
    // If the API call succeeded (to either Seven or panel server), we can remove any queued toggle actions for this trigger
    const queue = getOfflineTriggerQueue();
    const newQueue = queue.filter(action => !(action.type === 'toggle' && action.triggerId === id));
    if (newQueue.length !== queue.length) {
      localStorage.setItem(OFFLINE_TRIGGER_QUEUE_KEY, JSON.stringify(newQueue));
    }
  }
}

async function handleDeleteTrigger(id, event) {
  if (event) event.stopPropagation();
  const btn = document.getElementById(`trig-del-${id}`);
  if (!btn) return;

  if (_deleteConfirm[id]) {
    clearTimeout(_deleteConfirm[id]);
    delete _deleteConfirm[id];
    const t = (window._allTriggers || []).find(x => triggerIdOf(x) === id);
    if (!t) return; // already removed?

    const ok = await finishDeleteTrigger(id); // now returns the result of deleteTriggerAPI
    if (ok) {
      // Successfully deleted via API, remove from UI and clean queue
      window._allTriggers = (window._allTriggers || []).filter(x => triggerIdOf(x) !== id);
      if (typeof updateTabCounts === 'function') updateTabCounts();
      if ((window._allTriggers || []).length === 0) setTimeout(renderTriggers, 240);
      // Remove any queued delete actions for this trigger
      const queue = getOfflineTriggerQueue();
      const newQueue = queue.filter(action => !(action.type === 'delete' && action.triggerId === id));
      if (newQueue.length !== queue.length) {
        localStorage.setItem(OFFLINE_TRIGGER_QUEUE_KEY, JSON.stringify(newQueue));
      }
    } else {
      // Failed to delete via API, queue the delete action and show error
      queueOfflineAction({ type: 'delete', triggerId: id });
      alert('Failed to delete trigger. Seven may not be running. The delete will be retried when Seven is available.');
      // Re-arm the button for next click? The user can try again.
      btn.classList.add('confirm');
      btn.title = 'Click again to delete';
      _deleteConfirm[id] = setTimeout(() => {
        btn.classList.remove('confirm');
        btn.title = 'Delete';
        delete _deleteConfirm[id];
      }, 2500);
    }
    return;
  }

  btn.classList.add('confirm');
  btn.title = 'Click again to delete';
  _deleteConfirm[id] = setTimeout(() => {
    btn.classList.remove('confirm');
    btn.title = 'Delete';
    delete _deleteConfirm[id];
  }, 2500);
}

async function finishDeleteTrigger(id) {
  const card = document.getElementById(`trigger-${id}`);
  if (card) {
    card.classList.add('leaving');
    setTimeout(() => card.remove(), 220);
  }
  return await safeDeleteTrigger(id);
}

// Edit functionality removed as per user request