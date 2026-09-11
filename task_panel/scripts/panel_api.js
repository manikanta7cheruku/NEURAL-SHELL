/**
 * panel_api.js
 * All API calls for the panel. Talks to panel_server (7778) + Seven (7777).
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
  const r = await sevenAPI('/tasks', 'POST', {
    text: text,
    priority: 'medium',
  });
  if (r && r.success) return true;
  const fallback = await panelAPI('/panel/tasks', 'POST', { text });
  return fallback && fallback.success;
}

async function completeTaskAPI(taskId) {
  return panelAPI(`/panel/tasks/${taskId}/complete`, 'PUT');
}

async function updateTaskAPI(taskId, patch) {
  return sevenAPI(`/tasks/${taskId}`, 'PUT', patch);
}

async function deleteTaskAPI(taskId) {
  return sevenAPI(`/tasks/${taskId}`, 'DELETE');
}

async function updateSubtasksAPI(taskId, subtasks) {
  return panelAPI(`/panel/tasks/${taskId}/subtasks`, 'PUT', { subtasks });
}

/* ── Triggers ── */
async function fetchTriggersCompact() {
  return (await sevenAPI('/panel-extras/nothing')) || null || (await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/triggers-compact`).then(r => r.json()).catch(() => []));
}

async function fetchTriggersList() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/triggers-compact`);
    return await r.json();
  } catch {
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
    return { ok: false, error: data.detail || 'Update failed' };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

async function fireTrigger(triggerId) {
  return sevenAPI(`/triggers/${triggerId}/fire`, 'POST');
}

/* ── Schedules ── */
async function fetchSchedules() {
  const data = await sevenAPI('/schedules');
  if (!data || !Array.isArray(data)) return [];
  return data.filter(s => s.status === 'active');
}

async function cancelSchedule(schedId) {
  return sevenAPI(`/schedules/${schedId}`, 'DELETE');
}

/* ── Close All ── */
async function closeAllAPI(saveWorkspace = true, skipMedia = true) {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/close-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ save_workspace: saveWorkspace, skip_media: skipMedia }),
    });
    return await r.json();
  } catch (e) {
    return { success: false, error: String(e) };
  }
}

async function restoreLastWorkspaceAPI() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/panel/restore-last`, {
      method: 'POST',
    });
    return await r.json();
  } catch (e) {
    return { success: false, error: String(e) };
  }
}

/* ── Status ── */
async function isSevenAlive() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/api/status`, {
      signal: AbortSignal.timeout(1500),
    });
    return r.ok;
  } catch {
    return false;
  }
}

/* ── App Count for Close All ── */
async function getOpenAppCount() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/api/workspaces/scan`, {
      method: 'POST',
      signal: AbortSignal.timeout(4000),
    });
    const d = await r.json();
    return (d.apps || []).length;
  } catch {
    return 0;
  }
}