export const ACTION_CONFIG = {
  open_app:       { icon: 'Zap',        label: 'Open App' },
  open_url:       { icon: 'Globe',      label: 'Open URL' },
  open_file:      { icon: 'FileText',   label: 'Open File' },
  open_folder:    { icon: 'FolderOpen', label: 'Open Folder' },
  open_workspace: { icon: 'Layout',     label: 'Open Workspace' },
  run_command:    { icon: 'Terminal',   label: 'Run Command' },
  seven_action:   { icon: 'Settings2',  label: 'Seven Action' },
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