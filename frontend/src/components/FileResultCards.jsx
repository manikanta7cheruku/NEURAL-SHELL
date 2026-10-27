/**
 * FileResultCards.jsx
 *
 * File search results under a reply: one quiet row per file with its type, name, folder and age. The file Seven
 * opened is marked. Hovering a row offers Open and Show in folder. Five rows show at first; the rest on request.
 */
import { createElement, useState } from 'react';
import {
  File, FileAudio, FileCode, FileDoc, FileImage, FilePdf, FilePpt, FileText, FileVideo, FileXls, FileZip, Folder,
  FolderOpen, ArrowSquareOut,
} from '@phosphor-icons/react';
import api from '../api';
import { cx } from '../lib/cx';

const KIND = [
  [['pdf'], FilePdf], [['doc', 'docx', 'rtf', 'odt'], FileDoc], [['txt', 'md'], FileText],
  [['xls', 'xlsx', 'csv'], FileXls], [['ppt', 'pptx'], FilePpt],
  [['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'heic'], FileImage],
  [['mp4', 'mkv', 'avi', 'mov', 'wmv', 'webm'], FileVideo], [['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'], FileAudio],
  [['zip', 'rar', '7z', 'tar', 'gz'], FileZip],
  [['py', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'json', 'xml', 'java', 'cpp', 'c', 'cs'], FileCode],
];

function iconFor(item) {
  const ext = (item.ext || '').toLowerCase().replace('.', '');
  if (item.is_folder || ext === 'folder') return Folder;
  return (KIND.find(([exts]) => exts.includes(ext)) || [null, File])[1];
}

function age(value) {
  if (!value) return '';
  const d = new Date(String(value).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return '';
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} wk ago`;
  if (days < 365) return `${Math.floor(days / 30)} mo ago`;
  return `${Math.floor(days / 365)} yr ago`;
}

function folderOf(path = '') {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts.length > 1 ? parts[parts.length - 2] : '';
}

const open = (path, reveal = false) => api.post('/files/open', { path, reveal }).catch(() => {});

function Row({ item, opened }) {
  const when = age(item.modified);
  return (
    <div className="group/row flex h-11 items-center gap-3 rounded-md px-2.5 hover:bg-s-card">
      {createElement(iconFor(item), { size: 18, weight: 'light', className: 'shrink-0 text-s-text-3' })}
      <button onClick={() => open(item.path)} title={item.path} className="min-w-0 flex-1 text-left">
        <div className="flex items-center gap-2">
          <span className="truncate text-[12.5px] text-s-text">{item.name}</span>
          {opened && <span className="shrink-0 rounded px-1.5 text-[10.5px] text-s-text-3 ring-1 ring-s-border">Opened</span>}
        </div>
        <div className="truncate text-[11px] text-s-text-4">
          {[folderOf(item.path), when].filter(Boolean).join(' · ')}
        </div>
      </button>
      <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity duration-200 group-hover/row:opacity-100 focus-within:opacity-100">
        <button onClick={() => open(item.path)} title="Open" aria-label={`Open ${item.name}`}
                className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-3 hover:bg-s-card-h hover:text-s-text">
          <ArrowSquareOut size={15} />
        </button>
        <button onClick={() => open(item.path, true)} title="Show in folder" aria-label={`Show ${item.name} in its folder`}
                className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-3 hover:bg-s-card-h hover:text-s-text">
          <FolderOpen size={15} />
        </button>
      </div>
    </div>
  );
}

export default function FileResultCards({ data }) {
  const [all, setAll] = useState(false);
  if (!data?.results?.length) return null;
  const { query, results } = data;
  const opened = data.opened === true;             // the backend says whether the first one was opened
  const near = !!data.similar_to;                  // nothing matched as typed: these are close names
  const shown = all ? results : results.slice(0, 5);

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-s-border bg-s-surface">
      <div className="flex h-8 items-center justify-between border-b border-s-border px-3 text-[11px] text-s-text-4">
        <span className="truncate">
          {near ? <>Close matches for <span className="text-s-text-3">"{query}"</span></>
            : query ? <>Files for <span className="text-s-text-3">"{query}"</span></> : 'Files'}
        </span>
        <span className="tabular-nums">{results.length}</span>
      </div>
      <div className="p-1">
        {shown.map((item, i) => <Row key={`${item.path}-${i}`} item={item} opened={opened && i === 0} />)}
      </div>
      {results.length > 5 && (
        <button onClick={() => setAll(!all)}
                className={cx('flex h-8 w-full items-center justify-center border-t border-s-border text-[11.5px] text-s-text-3 hover:bg-s-card hover:text-s-text')}>
          {all ? 'Show fewer' : `Show ${results.length - 5} more`}
        </button>)}
    </div>
  );
}
