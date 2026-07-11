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
 * Get Chrome profile name.
 * Each profile has a unique extension ID, so we use that as identifier.
 * Also tries to read the profile name from Chrome's identity API.
 */
async function getProfileName() {
  try {
    // Method 1: Check if we already saved a profile name
    const stored = await chrome.storage.local.get('seven_profile_name');
    if (stored.seven_profile_name) {
      return stored.seven_profile_name;
    }

    // Method 2: Use extension ID as unique identifier per profile
    // Each Chrome profile gets a DIFFERENT extension ID for unpacked extensions
    // This naturally separates profiles
    const extId = chrome.runtime.id;
    
    // Method 3: Try to get user's email from Chrome identity
    try {
      const userInfo = await chrome.identity.getProfileUserInfo({ accountStatus: 'ANY' });
      if (userInfo && userInfo.email) {
        const profileName = userInfo.email.split('@')[0];
        await chrome.storage.local.set({ seven_profile_name: profileName });
        return profileName;
      }
    } catch {
      // identity API not available or no user signed in
    }

    // Method 4: Use a hash of the extension ID as profile identifier
    // Different profile = different extension ID = different hash
    const shortId = extId.substring(0, 8);
    const profileName = `profile_${shortId}`;
    await chrome.storage.local.set({ seven_profile_name: profileName });
    return profileName;

  } catch {
    return 'unknown';
  }
}

// ── Start sync loop ──────────────────────────────────────────────────────

// Initial sync
syncTabs();

// ── Sync strategies ──────────────────────────────────────────────────────

// Strategy 1: Periodic sync
setInterval(syncTabs, SYNC_INTERVAL);

// Strategy 2: Sync on any tab event
chrome.tabs.onCreated.addListener(() => syncTabs());
chrome.tabs.onRemoved.addListener(() => syncTabs());
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url || changeInfo.title) syncTabs();
});
chrome.windows.onCreated.addListener(() => syncTabs());
chrome.windows.onRemoved.addListener(() => syncTabs());

// Strategy 3: Keep service worker alive
// Manifest V3 suspends service workers after 30 seconds of inactivity
// We use chrome.alarms to wake up periodically
chrome.alarms.create('seven-tab-sync', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'seven-tab-sync') {
    syncTabs();
  }
});

// Strategy 4: Sync on window focus change
chrome.windows.onFocusChanged.addListener(() => syncTabs());

// Extension icon click — manual sync
chrome.action.onClicked.addListener(async () => {
  await syncTabs();
});

// Initial sync
syncTabs();

console.log('[Seven Tab Sync] Extension loaded. Syncing every 3 seconds + on events.');

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