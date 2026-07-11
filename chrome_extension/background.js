/**
 * Seven Tab Sync — Chrome Extension Background Script
 * 
 * Sends all open tab data to Seven's local API every 3 seconds.
 * 100% local. No external servers. No data leaves the machine.
 * 
 * Data sent: tab URL, title, window ID, active status, pinned status
 * Data NOT sent: page content, cookies, passwords, history
 */

const SEVEN_API = 'http://127.0.0.1:7777/api/chrome/tabs';
const SYNC_INTERVAL = 3000; // 3 seconds

let lastSyncTime = 0;
let syncActive = true;

/**
 * Collect all tabs from all windows and send to Seven.
 */
async function syncTabs() {
  if (!syncActive) return;

  try {
    // Get ALL windows with their tabs
    const windows = await chrome.windows.getAll({ populate: true });
    
    const payload = {
      timestamp: new Date().toISOString(),
      browser: 'chrome',
      profile: await getProfileName(),
      windows: windows.map(win => ({
        id: win.id,
        focused: win.focused,
        state: win.state, // normal, minimized, maximized, fullscreen
        type: win.type,   // normal, popup, panel, app
        incognito: win.incognito,
        tabs: win.tabs.map(tab => ({
          id: tab.id,
          url: tab.url || '',
          title: tab.title || '',
          active: tab.active,
          pinned: tab.pinned,
          index: tab.index,
          windowId: tab.windowId,
          // Don't send favIconUrl — unnecessary data
        }))
      }))
    };

    // Send to Seven's local API
    const response = await fetch(SEVEN_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      lastSyncTime = Date.now();
      // Update badge to show active
      chrome.action.setBadgeText({ text: '✓' });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    } else {
      // Seven not responding — show warning
      chrome.action.setBadgeText({ text: '!' });
      chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
    }

  } catch (error) {
    // Seven backend not running — silently continue
    // Will retry next interval
    chrome.action.setBadgeText({ text: '' });
  }
}

/**
 * Get Chrome profile name from the user data directory.
 */
async function getProfileName() {
  try {
    // Chrome doesn't expose profile name directly to extensions
    // Use a workaround: check the profile path from chrome.runtime
    const info = await chrome.runtime.getPlatformInfo();
    
    // Try to identify profile from extension ID path
    // Each profile has unique extension storage
    const profileKey = await chrome.storage.local.get('seven_profile_name');
    if (profileKey.seven_profile_name) {
      return profileKey.seven_profile_name;
    }
    
    // Auto-detect: ask user on first run or use "default"
    return 'default';
  } catch {
    return 'default';
  }
}

// ── Start sync loop ──────────────────────────────────────────────────────

// Initial sync
syncTabs();

// Periodic sync
setInterval(syncTabs, SYNC_INTERVAL);

// Also sync on tab events for faster updates
chrome.tabs.onCreated.addListener(() => syncTabs());
chrome.tabs.onRemoved.addListener(() => syncTabs());
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  // Only sync on URL or title change (not loading status)
  if (changeInfo.url || changeInfo.title) {
    syncTabs();
  }
});
chrome.windows.onCreated.addListener(() => syncTabs());
chrome.windows.onRemoved.addListener(() => syncTabs());

// Extension icon click — manual sync + show status
chrome.action.onClicked.addListener(async () => {
  await syncTabs();
  
  const elapsed = Date.now() - lastSyncTime;
  if (elapsed < 5000) {
    chrome.action.setBadgeText({ text: '✓' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  }
});

console.log('[Seven Tab Sync] Extension loaded. Syncing every 3 seconds.');