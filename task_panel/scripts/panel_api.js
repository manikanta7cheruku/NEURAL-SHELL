/**
 * panel_api.js
 * All API calls for the panel.
 *   PANEL_PORT (7778) -> panel_server.py            (independent of Seven — tasks, triggers/schedules fallback)
 *   SEVEN_PORT (7777) /api/*   -> real CRUD routers (only alive while Seven's main app is running)
 *   SEVEN_PORT (7777) /panel/* -> panel_extras.py    (only alive while Seven's main app is running)
 */

const PANEL_PORT = 7778;
const SEVEN_PORT = 7777;

async function panelAPI(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  try {
    const r = await fetch(`http://127.0.0.1:${PANEL_PORT}${path}`, opts);
    return r.json();
  } catch {
    return null;
  }
}

async function sevenAPI(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/api${path}`, opts);
    return r.json();
  } catch {
    return null;
  }
}

/* ── Tasks ── */
async function fetchTasks() {
  return (await panelAPI('/panel/tasks')) || [];
}

async function fetchTaskStats() {
  return (await panelAPI('/panel/stats')) || { pending: 0, due_today: 0, overdue: 0 };
}

async function createTask(text) {
  const r = await sevenAPI('/tasks', 'POST', { text, priority: 'medium' });
  if (r && r.success) return true;
  const fallback = await panelAPI('/panel/tasks', 'POST', { text });
  return fallback && fallback.success;
}

async function completeTaskAPI(taskId) {
  return panelAPI(`/panel/tasks/${taskId}/complete`, 'PUT');
}

async function updateTaskAPI(taskId, patch) {
  const r = await sevenAPI(`/tasks/${taskId}`, 'PUT', patch);
  if (r && r.success) return r;
  return panelAPI(`/panel/tasks/${taskId}`, 'PUT', patch);
}

async function deleteTaskAPI(taskId) {
  const r = await sevenAPI(`/tasks/${taskId}`, 'DELETE');
  if (r && r.success) return r;
  return panelAPI(`/panel/tasks/${taskId}`, 'DELETE');
}

async function updateSubtasksAPI(taskId, subtasks) {
  return panelAPI(`/panel/tasks/${taskId}/subtasks`, 'PUT', { subtasks });
}

/* ── Triggers ──
   Online: full data + all fields via panel_extras.py (port 7777, Seven only)
   Offline: read-only fallback direct from triggers.db (port 7778, always alive)
   window._triggersSource is set so the UI can show which path was used —
   check this in DevTools console or the empty-state text if triggers look wrong.
*/
async function fetchTriggersList() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/triggers-compact`, { signal: AbortSignal.timeout(1500) });
    if (r.ok) {
      const data = await r.json();
      window._triggersSource = 'seven-online';
      console.log('[PANEL] triggers via Seven (online):', Array.isArray(data) ? data.length : data);
      return data;
    }
    console.warn('[PANEL] Seven trigger endpoint responded but not ok:', r.status);
  } catch (e) {
    console.warn('[PANEL] Seven trigger endpoint unreachable, falling back:', e.message);
  }
  try {
    const r2 = await fetch(`http://127.0.0.1:${PANEL_PORT}/panel/triggers`);
    const data2 = await r2.json();
    window._triggersSource = 'offline-fallback';
    console.log('[PANEL] triggers via offline fallback:', Array.isArray(data2) ? data2.length : data2);
    return Array.isArray(data2) ? data2 : [];
  } catch (e2) {
    window._triggersSource = 'failed';
    console.error('[PANEL] Both trigger sources failed:', e2);
    return [];
  }
}

async function editHotkeyInline(triggerId, newHotkey) {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/triggers/${triggerId}/hotkey`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trigger_id: triggerId, new_hotkey: newHotkey }),
    });
    const data = await r.json();
    if (r.ok) return { ok: true, trigger: data.trigger };
    return { ok: false, error: data.detail || 'Update failed — is Seven running? Hotkey editing needs the main app.' };
  } catch (e) {
    return { ok: false, error: 'Seven is not running — hotkey editing requires the main app.' };
  }
}

async function toggleTriggerEnabled(triggerId, enabled) {
  // Try Seven backend first
  try {
    const r = await sevenAPI(`/triggers/${triggerId}`, 'PUT', { enabled });
    if (r && r.success) return true;
  } catch (e) {
    // Seven backend unavailable, try panel server fallback
    console.log('[PANEL] Seven backend unavailable for toggle, trying panel server fallback');
  }

  // Fallback to panel server
  try {
    const r = await panelAPI(`/panel/triggers/${triggerId}`, 'PUT', { enabled });
    return r && r.success;
  } catch (e) {
    console.error('[PANEL] Panel server fallback also failed for toggle:', e);
    return false;
  }
}

async function deleteTriggerAPI(triggerId) {
  // Try Seven backend first
  try {
    const r = await sevenAPI(`/triggers/${triggerId}`, 'DELETE');
    return r && r.success;
  } catch (e) {
    // Seven backend unavailable, try panel server fallback
    console.log('[PANEL] Seven backend unavailable for delete, trying panel server fallback');
  }

  // Fallback to panel server
  try {
    const r = await panelAPI(`/panel/triggers/${triggerId}`, 'DELETE');
    return r && r.success;
  } catch (e) {
    console.error('[PANEL] Panel server fallback also failed for delete:', e);
    return false;
  }
}

async function fireTrigger(triggerId) {
  // Try Seven backend first
  try {
    const r = await sevenAPI(`/triggers/${triggerId}/fire`, 'POST');
    if (r && r.success) return true;
  } catch (e) {
    // Seven backend unavailable, try panel server fallback
    console.log('[PANEL] Seven backend unavailable for fire, trying panel server fallback');
  }

  // Fallback to panel server
  try {
    const r = await panelAPI(`/panel/triggers/${triggerId}/fire`, 'POST');
    return r && r.success;
  } catch (e) {
    console.error('[PANEL] Panel server fallback also failed for fire:', e);
    return false;
  }
}

/* ── Schedules ── */
async function fetchSchedules() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/api/schedules`, { signal: AbortSignal.timeout(1500) });
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data)) return data.filter(s => s.status === 'active');
    }
  } catch (e) {
    console.warn('[PANEL] Seven offline — falling back to direct schedules read:', e.message);
  }
  try {
    const r2 = await fetch(`http://127.0.0.1:${PANEL_PORT}/panel/schedules`);
    const data2 = await r2.json();
    return Array.isArray(data2) ? data2.filter(s => s.status === 'active') : [];
  } catch (e2) {
    return [];
  }
}

async function cancelSchedule(schedId) {
  const r = await sevenAPI(`/schedules/${schedId}`, 'DELETE');
  if (r && r.success) return true;
  const r2 = await panelAPI(`/panel/schedules/${schedId}`, 'DELETE');
  return !!(r2 && r2.success);
}

/* ── Close All ── */
async function closeAllAPI(saveWorkspace = true, skipMedia = true) {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/close-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ save_workspace: saveWorkspace, skip_media: skipMedia }),
    });
    const data = await r.json();
    if (!r.ok) return { success: false, detail: data.detail || `HTTP ${r.status}` };
    return data;
  } catch (e) {
    return { success: false, error: String(e) };
  }
}

async function restoreLastWorkspaceAPI() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/restore-last`, { method: 'POST' });
    return await r.json();
  } catch (e) {
    return { success: false, error: String(e) };
  }
}

/* ── Status ── */
async function isSevenAlive() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/api/status`, { signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch {
    return false;
  }
}

/* ── App Count for Close All ── */
async function getOpenAppCount() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/api/workspaces/scan`, { method: 'POST', signal: AbortSignal.timeout(4000) });
    const d = await r.json();
    return (d.apps || []).length;
  } catch {
    return 0;
  }
}