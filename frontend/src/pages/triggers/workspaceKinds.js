/**
 * How a saved app is described in the Workspaces UI: what kind it is and one short line about it.
 */
import { AppWindow, Code2, FileText, Folder, Globe, Terminal } from 'lucide-react';

export const KINDS = {
  browser:  { icon: Globe,     label: 'Browser windows', one: 'browser window' },
  code:     { icon: Code2,     label: 'Code projects',   one: 'code project' },
  document: { icon: FileText,  label: 'Documents',       one: 'document' },
  folder:   { icon: Folder,    label: 'Folders',         one: 'folder' },
  terminal: { icon: Terminal,  label: 'Terminals',       one: 'terminal' },
  app:      { icon: AppWindow, label: 'Apps',            one: 'app' },
};
export const ORDER = ['browser', 'code', 'document', 'folder', 'terminal', 'app'];

export function kindOf(app) {
  const t = (app.type || '').toLowerCase();
  if (['chrome', 'edge', 'brave', 'firefox'].includes(t)) return 'browser';
  if (t === 'vscode') return 'code';
  if (t === 'explorer') return 'folder';
  if (['powershell', 'cmd', 'terminal', 'pwsh'].includes(t)) return 'terminal';
  if (app.open_files?.length || ['word', 'excel', 'powerpoint', 'notepad', 'notepad++'].includes(t)) return 'document';
  return 'app';
}

const base = p => (p || '').split(/[\\/]/).filter(Boolean).pop() || '';

/** One readable line per saved item: "Chrome, Mani: 12 tabs", "SEVEN", "notes.docx". */
export function describe(app) {
  const kind = kindOf(app);
  if (kind === 'browser') {
    const n = app.tabs?.length || 0;
    const browser = { chrome: 'Chrome', edge: 'Edge', brave: 'Brave', firefox: 'Firefox' }[app.type] || 'Browser';
    return `${browser}${app.profile_name ? `, ${app.profile_name}` : ''}: ${n} tab${n === 1 ? '' : 's'}`;
  }
  if (kind === 'code') return base(app.workspace_path) || 'VS Code';
  if (kind === 'folder') return base(app.folder_path) || (app.name || '').replace(/^File Explorer:\s*/, '') || 'Folder';
  if (kind === 'document') return base(app.open_files?.[0]) || app.name;
  if (kind === 'terminal') return base(app.working_dir) ? `Terminal in ${base(app.working_dir)}` : 'Terminal';
  return (app.name || app.type || 'App').replace(/\s+-\s+.*$/, '');
}

export function summarize(apps = []) {
  const groups = {};
  apps.forEach(a => { const k = kindOf(a); (groups[k] = groups[k] || []).push(a); });
  const tabs = apps.reduce((n, a) => n + (a.tabs?.length || 0), 0);
  const noAddress = apps.reduce((n, a) => n + (a.tabs_without_url || 0), 0);
  return { groups, tabs, noAddress };
}

export function summaryLine(apps = []) {
  const { groups, tabs } = summarize(apps);
  const parts = ORDER.filter(k => groups[k]).map(k => {
    const n = groups[k].length;
    return k === 'browser' ? `${tabs} tab${tabs === 1 ? '' : 's'}` : `${n} ${KINDS[k].one}${n === 1 ? '' : 's'}`;
  });
  return parts.join(' · ');
}
