/**
 * panel_closeall.js
 * Close all apps with recovery workspace + restore banner.
 */

let _restoreTimer = null;
let _restoreSecondsLeft = 60;

async function showCloseAllModal() {
  const modal = document.getElementById('closeall-modal');
  const desc = document.getElementById('closeall-desc');
  if (!modal || !desc) return;

  desc.textContent = 'Counting open applications...';
  modal.style.display = 'flex';

  const count = await getOpenAppCount();
  if (count === 0) {
    desc.textContent = 'No applications are open right now.';
  } else {
    desc.textContent = `${count} application${count !== 1 ? 's' : ''} will be closed. A recovery workspace will be saved automatically so you can restore everything.`;
  }
}

function dismissCloseAll() {
  const modal = document.getElementById('closeall-modal');
  if (modal) modal.style.display = 'none';
}

async function executeCloseAll() {
  const modal = document.getElementById('closeall-modal');
  if (modal) modal.style.display = 'none';

  const result = await closeAllAPI(true, true);
  if (result && result.success) {
    showRestoreBanner(result.closed_count || 0);
  }
}

function showRestoreBanner(count) {
  const banner = document.getElementById('restore-banner');
  const text = document.getElementById('restore-text');
  const timer = document.getElementById('restore-timer');
  if (!banner || !text || !timer) return;

  text.textContent = `${count} application${count !== 1 ? 's' : ''} closed`;
  banner.style.display = 'flex';

  _restoreSecondsLeft = 60;
  timer.textContent = `${_restoreSecondsLeft}s`;

  if (_restoreTimer) clearInterval(_restoreTimer);
  _restoreTimer = setInterval(() => {
    _restoreSecondsLeft--;
    if (_restoreSecondsLeft <= 0) {
      hideRestoreBanner();
    } else {
      timer.textContent = `${_restoreSecondsLeft}s`;
    }
  }, 1000);
}

function hideRestoreBanner() {
  const banner = document.getElementById('restore-banner');
  if (banner) banner.style.display = 'none';
  if (_restoreTimer) {
    clearInterval(_restoreTimer);
    _restoreTimer = null;
  }
}

async function restoreLastWorkspace() {
  hideRestoreBanner();
  const result = await restoreLastWorkspaceAPI();
  if (result && result.success) {
    const banner = document.getElementById('restore-banner');
    if (banner) {
      banner.style.display = 'flex';
      const text = document.getElementById('restore-text');
      const restoreBtn = banner.querySelector('.restore-btn');
      const timer = document.getElementById('restore-timer');
      if (text) text.textContent = `Restoring ${result.app_count} apps...`;
      if (restoreBtn) restoreBtn.style.display = 'none';
      if (timer) timer.style.display = 'none';
      setTimeout(() => {
        banner.style.display = 'none';
        if (restoreBtn) restoreBtn.style.display = '';
        if (timer) timer.style.display = '';
      }, 3000);
    }
  }
}