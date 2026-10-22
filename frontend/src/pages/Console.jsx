import { useRef, useEffect, useState, useCallback } from 'react';
import useChatSessions from '../stores/useChatSessions';
import api from '../api';
import {
  Send, Paperclip, X, FileText, ChevronRight, Cpu, AlertCircle, Upload, Square, RotateCcw,
  ThumbsUp, ThumbsDown, Copy, Check, PanelLeft, Brain, ArrowDown, Globe, Database, FileSearch,
} from 'lucide-react';
import FileResultCards from '../components/FileResultCards';
import TaskResultCard from '../components/TaskResultCard';
import MessageContent from '../components/MessageContent';
import ConversationSidebar from '../components/ConversationSidebar';
import KnowledgePanel from '../components/KnowledgePanel';

const CMDS = [
  { c: 'Memory',    d: ['/memory', '/facts', '/convos', '/stats'] },
  { c: 'Logs',      d: ['/logs', '/mood'] },
  { c: 'Manage',    d: ['/add fact [text]', '/delete fact [n]'] },
  { c: 'Chat',      d: ['/new', '/export', '/clear'] },
  { c: 'Control',   d: ['/windows', '/system', '/schedules'] },
  { c: 'Knowledge', d: ['/knowledge', '/knowledge search X'] },
  { c: 'Speakers',  d: ['/speakers'] },
  { c: 'Help',      d: ['/help'] },
];
const SUGGESTIONS = ['What can you do?', 'What do you know about me?', 'Open camera', 'What am I working on?'];
const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md'];
const SOURCE_ICON = { memory: Brain, web: Globe, documents: FileSearch, earlier_chats: Database, goals: Brain };

/* ---- thinking indicator: blinking dots, live elapsed time, honest phase label ---- */
function Thinking({ since }) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSecs(Math.floor((Date.now() - since) / 1000)), 500);
    return () => clearInterval(t);
  }, [since]);
  return (
    <div className="flex items-center gap-2 text-[11px] text-white/40" aria-live="polite">
      <span className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span key={i} className="w-1.5 h-1.5 rounded-full bg-s-accent/70"
                style={{ animation: `sevenBlink 1.2s ease-in-out ${i * 0.2}s infinite` }} />
        ))}
      </span>
      <span>{secs < 2 ? 'Thinking' : secs < 8 ? `Thinking · ${secs}s` : `Still working · ${secs}s (the model may be loading)`}</span>
    </div>
  );
}

function SourceChips({ meta }) {
  const sources = meta?.sources || [];
  if (!sources.length && !meta?.first_token_ms) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-2">
      {sources.map((s) => {
        const Icon = SOURCE_ICON[s] || Brain;
        return (
          <span key={s} className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-[8.5px] text-white/40">
            <Icon size={9} />{s.replace('_', ' ')}
          </span>);
      })}
      {meta?.uncertainty && (
        <span className="px-1.5 py-0.5 rounded-full bg-yellow-500/[0.07] border border-yellow-500/15 text-[8.5px] text-yellow-200/60">unsure, said so</span>)}
      {meta?.first_token_ms != null && <span className="text-[8.5px] text-white/20 font-mono">{meta.first_token_ms} ms</span>}
    </div>
  );
}

function Receipts({ receipts }) {
  if (!receipts?.length) return null;
  const color = { success: 'text-emerald-300/70', failed: 'text-red-300/80', unconfirmed: 'text-yellow-200/60' };
  return (
    <div className="mt-2 pt-2 border-t border-white/[0.05] space-y-0.5">
      {receipts.map((r, i) => (
        <div key={i} className={`text-[9px] font-mono ${color[r.status] || 'text-white/40'}`}>
          {r.kind.toLowerCase()} {r.target} · {r.status}{r.detail ? ` (${r.detail})` : ''}
        </div>))}
    </div>
  );
}

function MessageBubble({ msg, isLast, onRetry, onRate }) {
  const [copied, setCopied] = useState(false);
  const isUser = msg.role === 'user';
  const time = msg.time?.toLocaleTimeString?.([], { hour: '2-digit', minute: '2-digit' });

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%]">
          {msg.attachedFile && (
            <div className="flex justify-end mb-1.5">
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-s-accent/8 border border-s-accent/12 rounded-lg">
                <FileText size={10} className="text-s-accent/70" />
                <span className="text-[9px] text-s-accent/80 font-medium">{msg.attachedFile}</span>
              </div>
            </div>)}
          <div className="bg-s-accent/90 rounded-2xl rounded-tr-sm px-4 py-2.5">
            <p className="text-[12.5px] text-white leading-relaxed whitespace-pre-wrap">{msg.text}</p>
          </div>
          <div className="text-[8px] text-white/25 text-right mt-1 pr-1">{time}</div>
        </div>
      </div>
    );
  }

  const streaming = msg.status === 'streaming';
  return (
    <div className="flex gap-2.5 group">
      <div className="w-6 h-6 rounded-lg bg-white/[0.04] border border-white/8 flex items-center justify-center shrink-0 mt-1">
        <Cpu size={11} className="text-white/40" />
      </div>
      <div className="max-w-[78%] min-w-0">
        <div className={`rounded-2xl rounded-tl-sm px-4 py-2.5 ${msg.status === 'error' ? 'bg-red-500/[0.06] border border-red-500/15' : 'bg-white/[0.03] border border-white/[0.06]'}`}>
          {msg.isCommand ? (
            <pre className="text-[11px] leading-relaxed whitespace-pre-wrap font-mono overflow-x-auto text-white/60">{msg.text}</pre>
          ) : msg.status === 'error' ? (
            <p className="text-[12.5px] text-red-300">{msg.text}</p>
          ) : (
            <>
              <MessageContent text={msg.text} />
              {streaming && msg.text && <span className="inline-block w-[7px] h-[13px] ml-0.5 align-middle bg-s-accent/70" style={{ animation: 'sevenCaret 1s steps(1) infinite' }} />}
            </>)}
          {msg.fileResults?.count > 0 && <FileResultCards data={msg.fileResults} />}
          {msg.taskResults && <TaskResultCard data={msg.taskResults} />}
          <Receipts receipts={msg.receipts} />
          {!streaming && <SourceChips meta={msg.meta} />}
        </div>
        <div className="flex items-center gap-2 mt-1 pl-1 h-4">
          <span className="text-[8px] text-white/20">{time}</span>
          {!streaming && !msg.isCommand && (
            <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button title="Copy" onClick={() => { navigator.clipboard.writeText(msg.text); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
                className="text-white/30 hover:text-white/70">{copied ? <Check size={10} /> : <Copy size={10} />}</button>
              {msg.serverId && (
                <>
                  <button title="Good answer" onClick={() => onRate(msg, 'up')} className={msg.rating === 'up' ? 'text-emerald-300' : 'text-white/30 hover:text-white/70'}><ThumbsUp size={10} /></button>
                  <button title="Bad answer" onClick={() => onRate(msg, 'down')} className={msg.rating === 'down' ? 'text-red-300' : 'text-white/30 hover:text-white/70'}><ThumbsDown size={10} /></button>
                </>)}
              {isLast && <button title="Try again" onClick={onRetry} className="text-white/30 hover:text-white/70"><RotateCcw size={10} /></button>}
            </div>)}
        </div>
      </div>
    </div>
  );
}

export default function Console() {
  const s = useChatSessions();
  const { messages, sending, phase, sentAt, warning, init, send, stop, retry, rate, newChat } = s;
  const [draft, setDraft] = useState('');
  const [showSidebar, setShowSidebar] = useState(true);
  const [showKnowledge, setShowKnowledge] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [atBottom, setAtBottom] = useState(true);
  const scroller = useRef(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => { init(); }, []);

  useEffect(() => { if (atBottom) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, phase]);
  useEffect(() => { if (!sending) inputRef.current?.focus(); }, [sending]);

  // auto-growing composer
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
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

  const handleFileSelect = (file) => {
    if (!file) return;
    const ext = `.${file.name.split('.').pop().toLowerCase()}`;
    if (!SUPPORTED_EXTENSIONS.includes(ext)) { setUploadErr(`Unsupported: ${ext}. Use PDF, DOCX, PPTX, XLSX, TXT, or MD`); return; }
    setUploadErr(''); setPendingFile(file);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0]);
  }, []);

  const lastBotIndex = [...messages].map((m) => m.role).lastIndexOf('assistant');
  const waiting = sending && phase === 'thinking';

  return (
    <div className="h-full flex bg-s-bg relative"
         onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
         onDragLeave={() => setDragOver(false)} onDrop={onDrop}>
      <style>{`
        @keyframes sevenBlink { 0%,80%,100% { opacity: .2; transform: scale(.8);} 40% { opacity: 1; transform: scale(1);} }
        @keyframes sevenCaret { 0%,50% { opacity: 1;} 51%,100% { opacity: 0;} }
        @keyframes sevenRise { from { opacity: 0; transform: translateY(4px);} to { opacity: 1; transform: none;} }
      `}</style>

      {dragOver && (
        <div className="absolute inset-0 z-50 bg-s-accent/[0.06] border-2 border-s-accent/30 border-dashed flex items-center justify-center pointer-events-none">
          <div className="flex flex-col items-center gap-2"><Upload size={28} className="text-s-accent/60" />
            <p className="text-[13px] text-s-accent/70 font-medium">Drop to add to your knowledge</p></div>
        </div>)}

      {showSidebar && <ConversationSidebar />}

      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/8">
          <div className="flex items-center gap-3 min-w-0">
            <button onClick={() => setShowSidebar(!showSidebar)} className="text-white/30 hover:text-white/70" title="Chats"><PanelLeft size={14} /></button>
            <div className="min-w-0">
              <h1 className="text-[14px] font-semibold text-white/95 tracking-tight">Console</h1>
              <p className="text-[9px] text-white/35 truncate">Same brain as voice. Saved on this computer.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowKnowledge(!showKnowledge)}
              className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1.5 rounded-lg border transition-colors ${showKnowledge ? 'border-s-accent/40 text-s-accent bg-s-accent/10' : 'border-white/8 text-white/40 hover:text-white/70'}`}>
              <Brain size={11} /> What I know about you
            </button>
            <button onClick={newChat} className="text-[10px] px-2.5 py-1.5 rounded-lg border border-white/8 text-white/40 hover:text-white/70 transition-colors">New chat</button>
          </div>
        </div>

        {warning && (
          <div className="mx-5 mt-3 flex items-center gap-2 px-3 py-2 bg-yellow-500/[0.06] border border-yellow-500/15 rounded-lg" role="alert">
            <AlertCircle size={12} className="text-yellow-300/80 shrink-0" />
            <span className="text-[10.5px] text-yellow-100/80">{warning}</span>
          </div>)}

        <div ref={scroller} onScroll={onScroll} className="flex-1 overflow-y-auto px-5 py-4 relative scrollbar-thin scrollbar-thumb-white/8 scrollbar-track-transparent">
          {messages.length === 0 && (
            <div className="space-y-5" style={{ animation: 'sevenRise .3s ease-out' }}>
              <div className="flex flex-col items-center py-8 gap-2">
                <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/6 flex items-center justify-center"><Cpu size={18} className="text-white/25" /></div>
                <p className="text-[13px] text-white/50 font-medium">What are we working on?</p>
                <p className="text-[9.5px] text-white/25 text-center">Type a message, use a / command, or drop a file to learn from it.</p>
                <div className="flex flex-wrap justify-center gap-2 pt-2">
                  {SUGGESTIONS.map((t) => (
                    <button key={t} onClick={() => send(t)}
                      className="px-3 py-1.5 rounded-full border border-white/8 bg-white/[0.02] text-[10.5px] text-white/50 hover:text-white/80 hover:border-white/20 transition-colors">{t}</button>))}
                </div>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {CMDS.map((g) => (
                  <div key={g.c} className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-3">
                    <div className="text-[9px] text-s-accent/70 font-semibold mb-2 uppercase tracking-wider">{g.c}</div>
                    {g.d.map((cmd) => (
                      <button key={cmd} onClick={() => { setDraft(`${cmd.replace(/\[.*?\]/g, '').trim()} `); inputRef.current?.focus(); }}
                        className="flex items-center gap-1 w-full text-left py-0.5 text-[9.5px] text-white/35 hover:text-white/60 transition-colors font-mono truncate group">
                        <ChevronRight size={8} className="text-white/15 group-hover:text-s-accent/50 shrink-0" />{cmd}
                      </button>))}
                  </div>))}
              </div>
            </div>)}

          <div className="space-y-4 max-w-[860px] mx-auto">
            {messages.map((m, i) => (
              m.role === 'assistant' && m.status === 'streaming' && !m.text
                ? (<div key={m.id} className="flex gap-2.5" style={{ animation: 'sevenRise .2s ease-out' }}>
                    <div className="w-6 h-6 rounded-lg bg-white/[0.04] border border-white/8 flex items-center justify-center shrink-0"><Cpu size={11} className="text-white/40" /></div>
                    <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl rounded-tl-sm px-4 py-3"><Thinking since={sentAt || Date.now()} /></div>
                  </div>)
                : <div key={m.id} style={{ animation: 'sevenRise .2s ease-out' }}>
                    <MessageBubble msg={m} isLast={i === lastBotIndex && !sending} onRetry={retry} onRate={rate} />
                  </div>))}
            <div ref={endRef} />
          </div>

          {!atBottom && (
            <button onClick={() => endRef.current?.scrollIntoView({ behavior: 'smooth' })}
              className="sticky bottom-2 left-full -translate-x-2 ml-auto flex items-center justify-center w-8 h-8 rounded-full bg-s-card border border-white/10 text-white/60 hover:text-white shadow-lg" title="Jump to latest">
              <ArrowDown size={13} /></button>)}
        </div>

        <div className="px-5 py-3 border-t border-white/[0.06] bg-s-bg space-y-2">
          {pendingFile && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.04] border border-white/8 rounded-lg max-w-[260px]">
              <FileText size={11} className="text-white/50" /><span className="text-[10px] text-white/60 truncate flex-1">{pendingFile.name}</span>
              <button onClick={() => { setPendingFile(null); setUploadErr(''); }} className="text-white/25 hover:text-white/55"><X size={10} /></button>
            </div>)}
          {uploadErr && (
            <div className="flex items-center gap-2 px-3 py-2 bg-red-500/[0.06] border border-red-500/12 rounded-lg">
              <AlertCircle size={11} className="text-red-400 shrink-0" /><span className="text-[9.5px] text-red-300 flex-1">{uploadErr}</span>
              <button onClick={() => setUploadErr('')} className="text-white/20 hover:text-white/50"><X size={10} /></button>
            </div>)}
          <div className="flex items-end gap-2 max-w-[860px] mx-auto w-full">
            <button onClick={() => fileRef.current?.click()} disabled={sending || uploading} title="Attach document"
              className="p-2.5 rounded-xl border border-white/6 bg-white/[0.02] text-white/30 hover:text-white/60 hover:bg-white/[0.04] disabled:opacity-30 transition-all"><Paperclip size={15} /></button>
            <input ref={fileRef} type="file" accept={SUPPORTED_EXTENSIONS.join(',')} className="hidden" onChange={(e) => handleFileSelect(e.target.files[0])} />
            <div className="flex-1 bg-white/[0.02] border border-white/8 rounded-2xl px-4 py-2.5 focus-within:border-white/20 transition-colors">
              <textarea ref={inputRef} rows={1} value={draft} onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } if (e.key === 'Escape' && sending) stop(); }}
                placeholder={pendingFile ? `Ask about ${pendingFile.name} or press Enter to index it...` : 'Message Seven   (Enter to send, Shift+Enter for a new line)'}
                disabled={uploading}
                className="w-full bg-transparent text-[12.5px] text-white/80 placeholder-white/20 outline-none resize-none disabled:opacity-40 leading-relaxed" />
            </div>
            {sending ? (
              <button onClick={stop} title="Stop (Esc)" className="p-2.5 rounded-xl bg-white/10 text-white/80 hover:bg-white/15 transition-colors"><Square size={14} /></button>
            ) : (
              <button onClick={submit} disabled={(!draft.trim() && !pendingFile) || uploading} title="Send"
                className="p-2.5 rounded-xl bg-s-accent/90 text-white hover:bg-s-accent disabled:opacity-25 disabled:bg-white/[0.04] disabled:text-white/20 transition-all">
                {uploading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Send size={15} />}
              </button>)}
          </div>
        </div>
      </div>

      {showKnowledge && <KnowledgePanel onClose={() => setShowKnowledge(false)} />}
    </div>
  );
}
