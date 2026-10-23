/**
 * Console: chat with Seven (the same brain as voice). Saved chats on the left
 * (resizable, collapsible), the conversation in the middle, and an optional
 * "What I know about you" panel on the right. Type "/" for commands.
 */
import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import useChatSessions from '../stores/useChatSessions';
import api from '../api';
import {
  ArrowUp, Paperclip, X, FileText, AlertCircle, Upload, Square, RotateCcw, ThumbsUp, ThumbsDown, Copy, Check,
  PanelLeftClose, PanelLeftOpen, Brain, ArrowDown, Globe, Database, FileSearch, Plus, Sparkles,
} from 'lucide-react';
import FileResultCards from '../components/FileResultCards';
import TaskResultCard from '../components/TaskResultCard';
import MessageContent from '../components/MessageContent';
import ConversationSidebar from '../components/ConversationSidebar';
import KnowledgePanel from '../components/KnowledgePanel';
import { Button } from '../components/ui';
import { cx } from '../lib/cx';

const COMMANDS = [
  ['/memory', 'What Seven remembers'], ['/facts', 'Stored facts'], ['/convos', 'Recent conversations'],
  ['/stats', 'Memory statistics'], ['/logs', 'Recent actions'], ['/mood', 'Mood history'],
  ['/add fact ', 'Remember something'], ['/delete fact ', 'Forget a fact by number'], ['/new', 'Start a new chat'],
  ['/export', 'Export this chat'], ['/clear', 'Clear this chat'], ['/windows', 'Open windows'],
  ['/system', 'System status'], ['/schedules', 'Your reminders'], ['/knowledge', 'Indexed documents'],
  ['/knowledge search ', 'Search your documents'], ['/speakers', 'Enrolled voices'], ['/help', 'All commands'],
];
const SUGGESTIONS = [
  ['What can you do?', 'See what Seven can help with'],
  ['Show my tasks', 'Your pending tasks'],
  ['What do you know about me?', 'Facts Seven has learned'],
  ['What are my system specs?', 'Your computer at a glance'],
];
const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md'];
const SOURCE_ICON = { memory: Brain, web: Globe, documents: FileSearch, earlier_chats: Database, goals: Brain };
const OPEN_KEY = 'seven.chats.open';
const EASE = 'ease-[cubic-bezier(0.32,0.72,0,1)]';

function readOpen() {
  try { return localStorage.getItem(OPEN_KEY) !== '0'; } catch { return true; }
}

function Thinking({ since }) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSecs(Math.floor((Date.now() - since) / 1000)), 500);
    return () => clearInterval(t);
  }, [since]);
  return (
    <div className="flex items-center gap-2.5 text-[12.5px] text-s-text-3" aria-live="polite">
      <span className="flex items-center gap-1">
        {[0, 1, 2].map(i => (
          <span key={i} className="h-1.5 w-1.5 rounded-full bg-s-text-3"
                style={{ animation: `sevenDot 1.3s ease-in-out ${i * 0.16}s infinite` }} />
        ))}
      </span>
      <span>{secs < 2 ? 'Thinking' : secs < 8 ? `Thinking for ${secs}s` : `Still working, ${secs}s. The model may be loading.`}</span>
    </div>
  );
}

function SourceChips({ meta }) {
  const sources = meta?.sources || [];
  if (!sources.length && !meta?.uncertainty) return null;
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
      {sources.map(s => {
        const Icon = SOURCE_ICON[s] || Brain;
        return (
          <span key={s} className="flex h-5 items-center gap-1 rounded-full border border-s-border px-2 text-[11px] capitalize text-s-text-3">
            <Icon size={11} />{s.replace('_', ' ')}
          </span>);
      })}
      {meta?.uncertainty && <span className="flex h-5 items-center rounded-full border border-s-border px-2 text-[11px] text-s-text-3">Not certain</span>}
    </div>
  );
}

function Receipts({ receipts }) {
  if (!receipts?.length) return null;
  const tone = { success: 'text-s-green', failed: 'text-s-red', unconfirmed: 'text-s-yellow' };
  const label = { success: 'Done', failed: 'Failed', unconfirmed: 'Not confirmed' };
  return (
    <div className="mt-2.5 space-y-1">
      {receipts.map((r, i) => (
        <div key={i} className="flex items-center gap-2 text-[11.5px] text-s-text-3">
          <span className={cx('h-1.5 w-1.5 rounded-full bg-current', tone[r.status] || 'text-s-text-4')} />
          <span className="capitalize">{r.kind.toLowerCase()}</span>
          <span className="text-s-text-2">{r.target}</span>
          <span className={tone[r.status]}>{label[r.status] || r.status}</span>
          {r.detail && <span className="truncate text-s-text-4">{r.detail}</span>}
        </div>))}
    </div>
  );
}

function IconAction({ label, onClick, active, children }) {
  return (
    <button aria-label={label} title={label} onClick={onClick}
            className={cx('flex h-6 w-6 items-center justify-center rounded-md transition-colors duration-150',
                          active ? 'text-s-text' : 'text-s-text-4 hover:bg-s-card hover:text-s-text-2')}>
      {children}
    </button>
  );
}

function Message({ msg, canRetry, onRetry, onRate, since }) {
  const [copied, setCopied] = useState(false);
  const time = msg.time?.toLocaleTimeString?.([], { hour: 'numeric', minute: '2-digit' });

  if (msg.role === 'user') {
    return (
      <div className="flex flex-col items-end">
        {msg.attachedFile && (
          <div className="mb-1.5 flex items-center gap-1.5 rounded-md border border-s-border bg-s-surface px-2 h-6 text-[11.5px] text-s-text-2">
            <FileText size={12} className="text-s-text-3" />{msg.attachedFile}
          </div>)}
        <div className="max-w-[78%] rounded-2xl rounded-br-md bg-s-card-h px-3.5 py-2 text-[13px] leading-[1.6] text-s-text whitespace-pre-wrap">
          {msg.text}
        </div>
        <span className="mt-1 pr-1 text-[11px] text-s-text-4">{time}</span>
      </div>
    );
  }

  const streaming = msg.status === 'streaming';
  const waiting = streaming && !msg.text;
  return (
    <div className="group/msg flex gap-3">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-s-accent text-[11px] font-semibold text-s-on-accent">7</div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[12px]">
          <span className="font-medium text-s-text">Seven</span>
          {!waiting && <span className="text-s-text-4">{time}</span>}
        </div>
        {waiting ? <Thinking since={since || Date.now()} /> : msg.isCommand ? (
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-s-border bg-s-surface p-3 font-mono text-[12px] leading-relaxed text-s-text-2">{msg.text}</pre>
        ) : msg.status === 'error' ? (
          <div className="flex items-start gap-2 rounded-lg border border-s-red/25 bg-s-red/5 px-3 py-2 text-[12.5px] text-s-red">
            <AlertCircle size={14} className="mt-0.5 shrink-0" />{msg.text}
          </div>
        ) : (
          <div className="relative">
            <MessageContent text={msg.text} />
            {streaming && <span className="ml-0.5 inline-block h-[14px] w-[2px] translate-y-[2px] rounded-full bg-s-accent" style={{ animation: 'sevenCaret 1s ease-in-out infinite' }} />}
          </div>
        )}
        {msg.fileResults?.count > 0 && <FileResultCards data={msg.fileResults} />}
        {msg.taskResults && <TaskResultCard data={msg.taskResults} />}
        <Receipts receipts={msg.receipts} />
        {!streaming && <SourceChips meta={msg.meta} />}
        {!streaming && !msg.isCommand && msg.text && (
          <div className="mt-1.5 flex h-6 items-center gap-0.5 opacity-0 transition-opacity duration-200 group-hover/msg:opacity-100 focus-within:opacity-100">
            <IconAction label={copied ? 'Copied' : 'Copy'} onClick={() => { navigator.clipboard.writeText(msg.text); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>
              {copied ? <Check size={13} /> : <Copy size={13} />}
            </IconAction>
            {msg.serverId && (
              <>
                <IconAction label="Good answer" active={msg.rating === 'up'} onClick={() => onRate(msg, 'up')}><ThumbsUp size={13} /></IconAction>
                <IconAction label="Bad answer" active={msg.rating === 'down'} onClick={() => onRate(msg, 'down')}><ThumbsDown size={13} /></IconAction>
              </>)}
            {canRetry && <IconAction label="Try again" onClick={onRetry}><RotateCcw size={13} /></IconAction>}
            {msg.meta?.first_token_ms != null && <span className="ml-1.5 text-[11px] tabular-nums text-s-text-4">{(msg.meta.first_token_ms / 1000).toFixed(1)}s</span>}
          </div>
        )}
      </div>
    </div>
  );
}

function Empty({ onPick }) {
  return (
    <div className="mx-auto flex max-w-[640px] flex-col items-center pt-[12vh]" style={{ animation: 'sevenRise .4s cubic-bezier(0.32,0.72,0,1)' }}>
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-s-accent text-[15px] font-semibold text-s-on-accent">7</div>
      <h2 className="mt-4 text-[18px] font-semibold tracking-[-0.01em] text-s-text">What can I help with?</h2>
      <p className="mt-1 text-[12.5px] text-s-text-3">Ask anything, type / for commands, or drop a document to learn from it.</p>
      <div className="mt-6 grid w-full grid-cols-2 gap-2">
        {SUGGESTIONS.map(([text, hint]) => (
          <button key={text} onClick={() => onPick(text)}
                  className="group/s rounded-lg border border-s-border bg-s-surface px-3.5 py-2.5 text-left shadow-[var(--s-shadow)]
                             transition-[border-color,transform,background-color] duration-200 hover:-translate-y-px hover:border-s-border-l hover:bg-s-card">
            <div className="text-[12.5px] font-medium text-s-text">{text}</div>
            <div className="mt-0.5 text-[11.5px] text-s-text-3">{hint}</div>
          </button>))}
      </div>
    </div>
  );
}

export default function Console() {
  const s = useChatSessions();
  const { messages, sending, phase, sentAt, warning, init, send, stop, retry, rate, newChat, conversations, conversationId } = s;
  const [draft, setDraft] = useState('');
  const [panel, setPanel] = useState(readOpen);
  const [showKnowledge, setShowKnowledge] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [atBottom, setAtBottom] = useState(true);
  const [cmdIndex, setCmdIndex] = useState(0);
  const scroller = useRef(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);

  const setPanelOpen = useCallback(open => {
    setPanel(open);
    try { localStorage.setItem(OPEN_KEY, open ? '1' : '0'); } catch { /* per-device convenience only */ }
  }, []);

  useEffect(() => { init(); }, [init]);
  useEffect(() => {
    const onChats = e => setPanelOpen(e.detail);
    const onKey = e => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 's') { e.preventDefault(); setPanelOpen(!panel); }
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'n') { e.preventDefault(); newChat(); }
    };
    window.addEventListener('seven:chats', onChats);
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('seven:chats', onChats); window.removeEventListener('keydown', onKey); };
  }, [panel, newChat, setPanelOpen]);

  useEffect(() => { if (atBottom) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, phase, atBottom]);
  useEffect(() => { if (!sending) inputRef.current?.focus(); }, [sending]);
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [draft]);

  const commands = useMemo(() => {
    if (!/^\/\S*$/.test(draft)) return [];                // only while typing the command word
    const q = draft.toLowerCase();
    return COMMANDS.filter(([c]) => c.startsWith(q)).slice(0, 8);
  }, [draft]);

  const onScroll = () => {
    const el = scroller.current;
    if (el) setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  };

  const submit = async () => {
    if ((!draft.trim() && !pendingFile) || sending) return;
    if (pendingFile) {
      setUploading(true);
      setUploadErr('');
      try {
        const fd = new FormData();
        fd.append('file', pendingFile);
        const r = await api.post('/knowledge/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        const name = pendingFile.name;
        const text = draft.trim() || `I just uploaded "${name}" (${r.data.chunks} sections indexed). What does it contain?`;
        setPendingFile(null); setDraft(''); setUploading(false);
        await send(text, name);
      } catch (e) {
        setUploadErr(e.response?.data?.detail || 'Upload failed');
        setUploading(false);
      }
      return;
    }
    const text = draft;
    setDraft('');
    await send(text);
  };

  const pickCommand = c => { setDraft(c.endsWith(' ') ? c : `${c} `); setCmdIndex(0); inputRef.current?.focus(); };

  const handleFileSelect = file => {
    if (!file) return;
    const ext = `.${file.name.split('.').pop().toLowerCase()}`;
    if (!SUPPORTED_EXTENSIONS.includes(ext)) { setUploadErr(`${ext} isn't supported. Use PDF, DOCX, PPTX, XLSX, TXT or MD.`); return; }
    setUploadErr(''); setPendingFile(file);
  };

  const onDrop = useCallback(e => {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0]);
  }, []);

  const onKeyDown = e => {
    if (commands.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setCmdIndex(i => (i + 1) % commands.length); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setCmdIndex(i => (i - 1 + commands.length) % commands.length); return; }
      if (e.key === 'Tab' || (e.key === 'Enter' && draft.trim() !== commands[cmdIndex]?.[0].trim())) {
        e.preventDefault(); pickCommand(commands[cmdIndex][0]); return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
    if (e.key === 'Escape' && sending) stop();
  };

  const lastBotIndex = messages.map(m => m.role).lastIndexOf('assistant');
  const title = conversations.find(c => c.id === conversationId)?.title || 'New chat';

  return (
    <div className="relative flex h-full bg-s-bg"
         onDragOver={e => { e.preventDefault(); setDragOver(true); }}
         onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setDragOver(false); }} onDrop={onDrop}>
      <style>{`
        @keyframes sevenDot { 0%,80%,100% { opacity: .25; transform: translateY(0);} 40% { opacity: 1; transform: translateY(-2px);} }
        @keyframes sevenCaret { 0%,100% { opacity: 1;} 50% { opacity: .15;} }
        @keyframes sevenRise { from { opacity: 0; transform: translateY(6px);} to { opacity: 1; transform: none;} }
      `}</style>

      <div className={cx('pointer-events-none absolute inset-3 z-50 flex items-center justify-center rounded-xl border-2 border-dashed border-s-accent/40 bg-s-accent/5',
                         'transition-opacity duration-200', dragOver ? 'opacity-100' : 'opacity-0')}>
        <div className="flex flex-col items-center gap-2 text-s-accent-h">
          <Upload size={22} /><p className="text-[13px] font-medium">Drop to add to your knowledge</p>
        </div>
      </div>

      <ConversationSidebar open={panel} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-s-border px-4">
          <div className="flex min-w-0 items-center gap-2">
            <button onClick={() => setPanelOpen(!panel)} aria-label={panel ? 'Hide chats' : 'Show chats'} title={`${panel ? 'Hide' : 'Show'} chats (Ctrl+Shift+S)`}
                    className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-3 transition-colors hover:bg-s-card hover:text-s-text">
              {panel ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
            </button>
            <h1 className="truncate text-[13px] font-medium text-s-text">{title}</h1>
          </div>
          <div className="flex items-center gap-1.5">
            <Button size="sm" variant={showKnowledge ? 'secondary' : 'ghost'} icon={Brain} onClick={() => setShowKnowledge(!showKnowledge)}>What I know about you</Button>
            <Button size="sm" variant="ghost" icon={Plus} onClick={newChat} title="New chat (Ctrl+N)">New chat</Button>
          </div>
        </header>

        {warning && (
          <div className="mx-auto mt-3 flex w-full max-w-[760px] items-center gap-2 rounded-lg border border-s-yellow/30 bg-s-yellow/5 px-3 py-2" role="alert">
            <AlertCircle size={14} className="shrink-0 text-s-yellow" />
            <span className="text-[12px] text-s-text-2">{warning}</span>
          </div>)}

        <div ref={scroller} onScroll={onScroll} className="relative flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[760px] px-6 py-6">
            {messages.length === 0 ? <Empty onPick={send} /> : (
              <div className="space-y-6">
                {messages.map((m, i) => (
                  <div key={m.id} style={{ animation: `sevenRise .28s cubic-bezier(0.32,0.72,0,1)` }}>
                    <Message msg={m} since={sentAt} canRetry={i === lastBotIndex && !sending} onRetry={retry} onRate={rate} />
                  </div>))}
              </div>
            )}
            <div ref={endRef} className="h-1" />
          </div>
          <button onClick={() => endRef.current?.scrollIntoView({ behavior: 'smooth' })} aria-label="Jump to latest"
                  className={cx('sticky bottom-3 left-1/2 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border border-s-border bg-s-surface',
                                'text-s-text-2 shadow-[var(--s-shadow-raised)] transition-all duration-200 hover:text-s-text',
                                atBottom ? 'pointer-events-none translate-y-2 opacity-0' : 'opacity-100')}>
            <ArrowDown size={14} />
          </button>
        </div>

        <div className="shrink-0 px-6 pb-4 pt-2">
          <div className="relative mx-auto w-full max-w-[760px]">
            <div className={cx('absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-lg border border-s-border bg-s-surface shadow-[var(--s-shadow-raised)]',
                               `origin-bottom transition-all duration-200 ${EASE}`,
                               commands.length ? 'scale-100 opacity-100' : 'pointer-events-none scale-[0.98] opacity-0')}>
              <div className="px-3 pt-2 pb-1 text-[11px] font-medium text-s-text-4">Commands</div>
              {commands.map(([c, d], i) => (
                <button key={c} onMouseEnter={() => setCmdIndex(i)} onClick={() => pickCommand(c)}
                        className={cx('flex w-full items-center gap-3 px-3 h-8 text-left transition-colors duration-100',
                                      i === cmdIndex ? 'bg-s-card' : '')}>
                  <span className="w-36 font-mono text-[12px] text-s-text">{c.trim()}</span>
                  <span className="truncate text-[12px] text-s-text-3">{d}</span>
                </button>))}
            </div>

            {(pendingFile || uploadErr) && (
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {pendingFile && (
                  <span className="flex h-7 items-center gap-1.5 rounded-md border border-s-border bg-s-surface pl-2 pr-1 text-[12px] text-s-text-2">
                    <FileText size={13} className="text-s-text-3" /><span className="max-w-[240px] truncate">{pendingFile.name}</span>
                    <button aria-label="Remove file" onClick={() => { setPendingFile(null); setUploadErr(''); }}
                            className="flex h-5 w-5 items-center justify-center rounded text-s-text-4 hover:bg-s-card hover:text-s-text-2"><X size={12} /></button>
                  </span>)}
                {uploadErr && <span className="flex items-center gap-1.5 text-[12px] text-s-red"><AlertCircle size={13} />{uploadErr}</span>}
              </div>)}

            <div className="flex items-end gap-1.5 rounded-xl border border-s-border bg-s-surface p-1.5 shadow-[var(--s-shadow)]
                            transition-[border-color,box-shadow] duration-200 focus-within:border-s-border-l focus-within:shadow-[var(--s-shadow-raised)]">
              <button onClick={() => fileRef.current?.click()} disabled={sending || uploading} aria-label="Attach a document" title="Attach a document"
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-s-text-3 transition-colors hover:bg-s-card hover:text-s-text disabled:opacity-40">
                <Paperclip size={16} />
              </button>
              <input ref={fileRef} type="file" accept={SUPPORTED_EXTENSIONS.join(',')} className="hidden" onChange={e => handleFileSelect(e.target.files[0])} />
              <textarea ref={inputRef} rows={1} value={draft} onChange={e => { setDraft(e.target.value); setCmdIndex(0); }} onKeyDown={onKeyDown}
                        placeholder={pendingFile ? `Ask about ${pendingFile.name}, or press Enter to add it` : 'Message Seven'}
                        disabled={uploading} aria-label="Message"
                        className="max-h-[180px] min-h-[32px] flex-1 resize-none bg-transparent py-1.5 text-[13px] leading-[1.55] text-s-text outline-none placeholder:text-s-text-4 disabled:opacity-50" />
              {sending ? (
                <button onClick={stop} aria-label="Stop" title="Stop (Esc)"
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-s-text text-s-bg transition-transform duration-150 hover:scale-105">
                  <Square size={12} fill="currentColor" />
                </button>
              ) : (
                <button onClick={submit} disabled={(!draft.trim() && !pendingFile) || uploading} aria-label="Send"
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-s-accent text-s-on-accent transition-all duration-200
                                   hover:bg-s-accent-h disabled:bg-s-card-h disabled:text-s-text-4">
                  {uploading ? <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" /> : <ArrowUp size={16} />}
                </button>
              )}
            </div>
            <div className="mt-1.5 flex items-center justify-center gap-1 text-[11px] text-s-text-4">
              <Sparkles size={11} /> Runs on this computer. Enter to send, Shift+Enter for a new line, / for commands.
            </div>
          </div>
        </div>
      </div>

      {showKnowledge && <KnowledgePanel onClose={() => setShowKnowledge(false)} />}
    </div>
  );
}
