/**
 * panel_summary.js
 * Today's summary card at top of panel.
 */

function updateSummaryCard(stats, completedToday) {
  const pendingEl = document.getElementById('sum-pending');
  const overdueEl = document.getElementById('sum-overdue');
  const completedEl = document.getElementById('sum-completed');

  if (pendingEl) pendingEl.textContent = stats.pending || 0;
  if (overdueEl) overdueEl.textContent = stats.overdue || 0;
  if (completedEl) completedEl.textContent = completedToday || 0;
}