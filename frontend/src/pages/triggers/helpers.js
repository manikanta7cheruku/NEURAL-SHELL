export const ACTION_CONFIG = {
  open_app:       { icon: 'Zap',        label: 'Open app' },
  open_url:       { icon: 'Globe',      label: 'Open site' },
  open_file:      { icon: 'FileText',   label: 'Open file' },
  open_folder:    { icon: 'FolderOpen', label: 'Open folder' },
  open_workspace: { icon: 'Layout',     label: 'Open workspace' },
  run_command:    { icon: 'Terminal',   label: 'Run command' },
  seven_action:   { icon: 'Settings2',  label: 'Seven command' },
};

export function formatHotkey(hk) {
  if (!hk) return '';
  return hk.split('+').map(k => k.charAt(0).toUpperCase() + k.slice(1)).join(' + ');
}

export function timeAgo(iso) {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff <= 0) return 'Just now';
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'Just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}