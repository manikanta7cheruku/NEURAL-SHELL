/**
 * panel_summary.js
 * Today, in one line: how many to do, how many are late, how many are done, and a bar for the share that's done.
 */

function updateSummaryCard(stats, completedToday) {
  const pending = stats.pending || 0;
  const overdue = stats.overdue || 0;
  const done = completedToday || 0;

  const pendingEl = document.getElementById('sum-pending');
  const overdueEl = document.getElementById('sum-overdue');
  const completedEl = document.getElementById('sum-completed');
  const bar = document.getElementById('sum-progress');

  if (pendingEl) pendingEl.textContent = pending;
  if (overdueEl) { overdueEl.textContent = overdue; overdueEl.classList.toggle('late', overdue > 0); }
  if (completedEl) completedEl.textContent = done;
  if (bar) bar.style.width = `${done + pending ? Math.round((done / (done + pending)) * 100) : 0}%`;
}
