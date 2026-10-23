/**
 * Light / dark theme. The preference ('dark' | 'light' | 'system') is kept in
 * localStorage so it applies before the first paint (no flash), and mirrored to
 * config.appearance.theme by the Settings page. 'system' follows Windows and
 * updates live when Windows switches.
 */
const KEY = 'seven.theme';
const media = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
let current = 'dark';

export function getThemePref() {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'light' || v === 'system' || v === 'dark' ? v : 'dark';
  } catch {
    return 'dark';
  }
}

function resolve(pref) {
  return pref === 'system' ? (media?.matches ? 'light' : 'dark') : pref;
}

function paint() {
  document.documentElement.dataset.theme = resolve(current);
}

/** Apply a preference now and remember it on this device. */
export function applyTheme(pref = getThemePref()) {
  current = pref;
  try { localStorage.setItem(KEY, pref); } catch { /* private mode: still applies for this session */ }
  paint();
}

media?.addEventListener?.('change', () => { if (current === 'system') paint(); });
