/**
 * panel_api.js - All API calls for the task panel.
 */

const PANEL_PORT = 7778;
const SEVEN_PORT = 7777;

async function panelAPI(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`http://127.0.0.1:${PANEL_PORT}${path}`, opts);
  return r.json();
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

async function fetchTasks() {
  try {
    return await panelAPI('/panel/tasks');
  } catch {
    return [];
  }
}

async function fetchStats() {
  try {
    return await panelAPI('/panel/stats');
  } catch {
    return { pending: 0, due_today: 0, overdue: 0 };
  }
}

async function fetchSchedules() {
  try {
    const data = await sevenAPI('/schedules');
    if (!data || !Array.isArray(data)) return [];
    return data.filter(s => s.status === 'active').slice(0, 5);
  } catch {
    return [];
  }
}

async function completeTask(taskId) {
  return panelAPI(`/panel/tasks/${taskId}/complete`, 'PUT');
}

async function updateSubtasks(taskId, subtasks) {
  return panelAPI(`/panel/tasks/${taskId}/subtasks`, 'PUT', { subtasks });
}

async function createTask(text) {
  try {
    const r = await sevenAPI('/tasks', 'POST', {
      text: text,
      priority: 'medium',
    });
    return r && r.success;
  } catch {
    // Fallback: direct DB via panel server
    try {
      return await panelAPI('/panel/tasks', 'POST', { text });
    } catch {
      return false;
    }
  }
}

async function isSevenAlive() {
  try {
    const r = await fetch(`http://127.0.0.1:${SEVEN_PORT}/api/status`, { signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch {
    return false;
  }
}

async function closeAllWindows() {
  try {
    await sevenAPI('/chat', 'POST', { text: 'minimize all windows', speaker_id: 'default' });
    return true;
  } catch {
    return false;
  }
}