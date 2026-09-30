/**
 * FileResultCards.jsx
 * 
 * Renders file search results as numbered cards inline in chat.
 * Top match highlighted with s-accent border. Click to open file.
 * Matches Console.jsx design language (compact, 10px, glassmorphic).
 */

import api from '../api';

const EXT_ICONS = {
  pdf:  '📄',
  doc:  '📝', docx: '📝', txt: '📝', md: '📝', rtf: '📝',
  xls:  '📊', xlsx: '📊', csv: '📊',
  ppt:  '📽', pptx: '📽',
  jpg:  '🖼', jpeg: '🖼', png: '🖼', gif: '🖼', webp: '🖼', bmp: '🖼', svg: '🖼',
  mp4:  '🎬', mkv: '🎬', avi: '🎬', mov: '🎬', wmv: '🎬', webm: '🎬',
  mp3:  '🎵', wav: '🎵', flac: '🎵', ogg: '🎵', m4a: '🎵',
  zip:  '📦', rar: '📦', '7z': '📦', tar: '📦', gz: '📦',
  exe:  '⚙', msi: '⚙',
  py:   '💻', js: '💻', jsx: '💻', ts: '💻', tsx: '💻',
  html: '💻', css: '💻', json: '💻', xml: '💻',
  folder: '📁',
};

function getIcon(item) {
  if (item.is_folder) return EXT_ICONS.folder;
  const ext = (item.ext || '').toLowerCase().replace('.', '');
  return EXT_ICONS[ext] || '📄';
}

function formatSize(mb) {
  if (!mb || mb === 0) return '';
  if (mb < 1) return `${Math.round(mb * 1024)} KB`;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

function formatModified(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'today';
    if (diffDays === 1) return 'yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
    return `${Math.floor(diffDays / 365)}y ago`;
  } catch {
    return '';
  }
}

async function openFile(path) {
  try {
    await api.post('/files/open', { path });
  } catch (e) {
    console.error('Failed to open file:', e);
  }
}

export default function FileResultCards({ data }) {
  if (!data || !data.results || data.results.length === 0) return null;

  const { query, count, shown, results } = data;
  const displayCount = shown || results.length;

  return (
    <div className="mt-3 pt-3 border-t border-white/[0.05] space-y-1.5">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[8px] text-white/30 uppercase tracking-widest font-medium">
          {query ? `Files matching "${query}"` : 'Files found'}
        </span>
        <span className="text-[8px] text-white/25 font-mono">
          {displayCount < count ? `${displayCount} of ${count}` : `${count}`}
        </span>
      </div>

      {/* Cards */}
      {results.map((item, idx) => {
        const isTop = idx === 0;
        return (
          <button
            key={`${item.path}-${idx}`}
            onClick={() => openFile(item.path)}
            className={`w-full text-left group transition-all duration-150 rounded-lg border ${
              isTop
                ? 'border-s-accent/25 bg-s-accent/[0.04] hover:bg-s-accent/[0.08] hover:border-s-accent/40'
                : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/[0.12]'
            }`}
          >
            <div className="flex items-start gap-2.5 px-2.5 py-2">
              {/* Number + Icon */}
              <div className="flex flex-col items-center gap-0.5 shrink-0 pt-0.5 w-4">
                <span
                  className={`text-[8px] font-mono font-semibold ${
                    isTop ? 'text-s-accent/90' : 'text-white/35'
                  }`}
                >
                  {idx + 1}
                </span>
                <span className="text-[11px] leading-none">{getIcon(item)}</span>
              </div>

              {/* Details */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`text-[10.5px] font-medium truncate ${
                      isTop ? 'text-white/90' : 'text-white/70'
                    }`}
                  >
                    {item.name}
                  </span>
                  {isTop && (
                    <span className="text-[7.5px] uppercase tracking-wider text-s-accent/70 font-semibold shrink-0">
                      Opened
                    </span>
                  )}
                </div>
                <div className="text-[8px] text-white/30 truncate mt-0.5 font-mono" title={item.path}>
                  {item.folder || item.path}
                </div>
                <div className="flex items-center gap-1.5 mt-0.5 text-[8px] text-white/25">
                  {item.size_mb > 0 && <span>{formatSize(item.size_mb)}</span>}
                  {item.modified && (
                    <>
                      {item.size_mb > 0 && <span>·</span>}
                      <span>{formatModified(item.modified)}</span>
                    </>
                  )}
                  {item.score != null && (
                    <>
                      <span>·</span>
                      <span className="font-mono opacity-70">{item.score}</span>
                    </>
                  )}
                </div>
              </div>

              {/* Chevron */}
              <div className="text-white/20 group-hover:text-white/50 transition-colors pt-1 shrink-0">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}