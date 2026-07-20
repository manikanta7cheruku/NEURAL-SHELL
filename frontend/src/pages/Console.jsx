import { useRef, useEffect, useState, useCallback } from 'react';
import useChat from '../stores/useChat';
import api from '../api';
import {
  Send, Paperclip, X, FileText, ChevronRight,
  Cpu, User, AlertCircle, Upload,
} from 'lucide-react';

const CMDS = [
  { c: 'Memory',    d: ['/memory', '/facts', '/convos', '/stats'] },
  { c: 'Logs',      d: ['/logs', '/mood'] },
  { c: 'Manage',    d: ['/add fact [text]', '/delete fact [n]', '/delete convo [n]'] },
  { c: 'Clear',     d: ['/clear all', '/clear logs', '/clear mood'] },
  { c: 'Speakers',  d: ['/speaker [name]', '/speakers'] },
  { c: 'Control',   d: ['/windows', '/system', '/schedules'] },
  { c: 'Knowledge', d: ['/knowledge', '/knowledge search X', '/knowledge files'] },
  { c: 'Help',      d: ['/help'] },
];

const EXT_COLORS = {
  '.pdf':  'text-red-400',
  '.docx': 'text-blue-400',
  '.pptx': 'text-orange-400',
  '.xlsx': 'text-green-400',
  '.txt':  'text-white/50',
  '.md':   'text-purple-400',
};

function FileAttachment({ file, onRemove }) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  const color = EXT_COLORS[ext] || 'text-white/50';
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.04]
                    border border-white/8 rounded-lg max-w-[260px]">
      <FileText size={11} className={color} />
      <span className="text-[10px] text-white/60 truncate flex-1">{file.name}</span>
      <button onClick={onRemove} className="text-white/25 hover:text-white/55 flex-shrink-0">
        <X size={10} />
      </button>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';

  const cleanText = (text) => {
    if (!text) return '';
    return text.replace(/###[A-Z_]+:[^\n#]*/g, '').replace(/\s{2,}/g, ' ').trim();
  };

  if (isUser) {
    return (
      <div className="flex justify-end gap-2.5">
        <div className="max-w-[75%]">
          {msg.attachedFile && (
            <div className="flex justify-end mb-1.5">
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-s-accent/8
                              border border-s-accent/12 rounded-lg">
                <FileText size={10} className="text-s-accent/70" />
                <span className="text-[9px] text-s-accent/80 font-medium">
                  {msg.attachedFile}
                </span>
              </div>
            </div>
          )}
          <div className="bg-s-accent/90 rounded-2xl rounded-tr-sm px-4 py-2.5">
            <p className="text-[12.5px] text-white leading-relaxed whitespace-pre-wrap">
              {msg.text}
            </p>
          </div>
          <div className="text-[8px] text-white/25 text-right mt-1 pr-1">
            {msg.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    );
  }

  const displayText = cleanText(msg.text);

  return (
    <div className="flex gap-2.5">
      <div className="w-6 h-6 rounded-lg bg-white/[0.04] border border-white/8
                      flex items-center justify-center flex-shrink-0 mt-1">
        <Cpu size={11} className="text-white/40" />
      </div>
      <div className="max-w-[75%]">
        <div className={`rounded-2xl rounded-tl-sm px-4 py-2.5
                         ${msg.error
                           ? 'bg-red-500/[0.06] border border-red-500/15'
                           : 'bg-white/[0.03] border border-white/[0.06]'}`}>
          {msg.isCommand ? (
            <pre className={`text-[11px] leading-relaxed whitespace-pre-wrap font-mono
                             overflow-x-auto
                             ${msg.error ? 'text-red-300' : 'text-white/60'}`}>
              {msg.text}
            </pre>
          ) : (
            <p className={`text-[12.5px] leading-relaxed whitespace-pre-wrap
                           ${msg.error ? 'text-red-300' : 'text-white/70'}`}>
              {displayText}
            </p>
          )}

          {/* File results */}
          {msg.fileResults?.count > 0 && (
            <div className="mt-3 pt-3 border-t border-white/[0.05] space-y-1.5">
              <div className="text-[8px] text-white/30 uppercase tracking-widest font-medium">
                {msg.fileResults.count} file{msg.fileResults.count > 1 ? 's' : ''} found
              </div>
              {msg.fileResults.results.map((f, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-[8px] font-mono text-white/30 bg-white/[0.04]
                                   px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0">
                    {f.ext || 'file'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[10px] text-white/60 font-medium truncate">{f.name}</div>
                    <button onClick={() => navigator.clipboard.writeText(f.path)}
                            className="text-[8px] text-white/25 hover:text-s-accent
                                       font-mono truncate block w-full text-left transition-colors">
                      {f.path}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          {msg.actions?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2.5 pt-2 border-t border-white/[0.05]">
              {msg.actions.map((a, j) => (
                <span key={j} className="px-1.5 py-0.5 bg-white/[0.05] border border-white/6
                                          text-[8px] text-white/40 rounded font-mono">
                  {a}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="text-[8px] text-white/20 mt-1 pl-1">
          {msg.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-2.5">
      <div className="w-6 h-6 rounded-lg bg-white/[0.04] border border-white/8
                      flex items-center justify-center flex-shrink-0">
        <Cpu size={11} className="text-white/40" />
      </div>
      <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl rounded-tl-sm
                      px-4 py-3 flex items-center gap-1.5">
        {[0, 1, 2].map(d => (
          <div key={d}
               className="w-1.5 h-1.5 rounded-full bg-s-accent/50"
               style={{ animation: `pulse 1.2s ease-in-out ${d * 0.2}s infinite` }} />
        ))}
      </div>
    </div>
  );
}

const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md'];

export default function Console() {
  const { messages, sending, draft, setDraft, send } = useChat();
  const endRef    = useRef(null);
  const inputRef  = useRef(null);
  const fileRef   = useRef(null);

  const [pendingFile, setPendingFile]   = useState(null);
  const [uploading,   setUploading]     = useState(false);
  const [uploadErr,   setUploadErr]     = useState('');
  const [dragOver,    setDragOver]      = useState(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  useEffect(() => {
    if (!sending) inputRef.current?.focus();
  }, [sending]);

  const submit = async () => {
    if ((!draft.trim() && !pendingFile) || sending) return;

    if (pendingFile) {
      // Upload file first then send context message
      setUploading(true);
      setUploadErr('');
      try {
        const fd = new FormData();
        fd.append('file', pendingFile);
        const r = await api.post('/knowledge/upload', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });

        const filename    = pendingFile.name;
        const chunks      = r.data.chunks;
        const contextMsg  = draft.trim()
          ? draft.trim()
          : `I just uploaded "${filename}" (${chunks} sections indexed). What does it contain?`;

        // Attach file metadata to message for display
        const originalSend = useChat.getState().send;
        setPendingFile(null);
        setDraft('');
        setUploading(false);

        // Add user message with file tag then send
        await send(contextMsg, filename);
      } catch (e) {
        setUploadErr(e.response?.data?.detail || 'Upload failed');
        setUploading(false);
      }
      return;
    }

    send(draft);
  };

  const handleFileSelect = (file) => {
    if (!file) return;
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      setUploadErr(`Unsupported: ${ext}. Use PDF, DOCX, PPTX, XLSX, TXT, or MD`);
      return;
    }
    setUploadErr('');
    setPendingFile(file);
  };

  const onDrop = useCallback(e => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }, []);

  const ins = (c) => {
    setDraft(c.replace(/\[.*?\]/g, '').trim() + ' ');
    inputRef.current?.focus();
  };

  const clearChat = () => useChat.getState().clear();

  return (
    <div className="h-full flex flex-col bg-s-bg"
         onDragOver={e => { e.preventDefault(); setDragOver(true); }}
         onDragLeave={() => setDragOver(false)}
         onDrop={onDrop}>

      {/* Drag overlay */}
      {dragOver && (
        <div className="absolute inset-0 z-50 bg-s-accent/[0.06] border-2 border-s-accent/30
                        border-dashed flex items-center justify-center pointer-events-none">
          <div className="flex flex-col items-center gap-2">
            <Upload size={28} className="text-s-accent/60" />
            <p className="text-[13px] text-s-accent/70 font-medium">Drop to add to knowledge</p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">Console</h1>
          <p className="text-[9px] text-white/35 mt-0.5">
            Same brain as voice, all commands available
          </p>
        </div>
        {messages.length > 0 && (
          <button onClick={clearChat}
                  className="text-[9px] text-white/25 hover:text-white/50 transition-colors
                             px-3 py-1.5 rounded-lg hover:bg-white/[0.03]">
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4
                      scrollbar-thin scrollbar-thumb-white/8 scrollbar-track-transparent">

        {/* Empty state — command reference */}
        {messages.length === 0 && (
          <div className="space-y-4">
            <div className="flex flex-col items-center py-8 gap-2">
              <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/6
                              flex items-center justify-center">
                <Cpu size={18} className="text-white/20" />
              </div>
              <p className="text-[12px] text-white/35 font-medium">Ask Seven anything</p>
              <p className="text-[9px] text-white/20 text-center">
                Type a message, use a / command, or drop a file to index
              </p>
            </div>

            <div className="grid grid-cols-4 gap-2">
              {CMDS.map(g => (
                <div key={g.c}
                     className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-3">
                  <div className="text-[9px] text-s-accent/70 font-semibold mb-2
                                  uppercase tracking-wider">
                    {g.c}
                  </div>
                  {g.d.map(cmd => (
                    <button key={cmd} onClick={() => ins(cmd)}
                            className="flex items-center gap-1 w-full text-left py-0.5
                                       text-[9.5px] text-white/35 hover:text-white/60
                                       transition-colors font-mono truncate group">
                      <ChevronRight size={8}
                                    className="text-white/15 group-hover:text-s-accent/50
                                               flex-shrink-0 transition-colors" />
                      {cmd}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Message list */}
        <div className="space-y-4">
          {messages.map((m, i) => (
            <MessageBubble key={i} msg={m} />
          ))}
          {sending && <TypingIndicator />}
          <div ref={endRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="px-6 py-4 border-t border-white/[0.06] bg-s-bg space-y-2">

        {/* Pending file preview */}
        {pendingFile && (
          <FileAttachment
            file={pendingFile}
            onRemove={() => { setPendingFile(null); setUploadErr(''); }}
          />
        )}

        {/* Upload error */}
        {uploadErr && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/[0.06]
                          border border-red-500/12 rounded-lg">
            <AlertCircle size={11} className="text-red-400 flex-shrink-0" />
            <span className="text-[9px] text-red-300 flex-1">{uploadErr}</span>
            <button onClick={() => setUploadErr('')}
                    className="text-white/20 hover:text-white/50 transition-colors">
              <X size={10} />
            </button>
          </div>
        )}

        {/* Input row */}
        <div className="flex items-end gap-2">
          {/* File attach button */}
          <div className="relative group flex-shrink-0">
            <button
              onClick={() => fileRef.current?.click()}
              disabled={sending || uploading}
              className="p-2.5 rounded-xl border border-white/6 bg-white/[0.02]
                         text-white/30 hover:text-white/60 hover:bg-white/[0.04]
                         hover:border-white/10 disabled:opacity-30
                         transition-all duration-150 mb-px block">
              <Paperclip size={15} />
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5
                            px-3 py-1.5 bg-[#18181c] border border-white/10
                            rounded-lg pointer-events-none z-50
                            opacity-0 group-hover:opacity-100
                            transition-opacity duration-150
                            shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
              <p className="text-[9px] text-white/60 whitespace-nowrap font-medium">
                Attach document
              </p>
              <p className="text-[7.5px] text-white/25 whitespace-nowrap mt-0.5">
                PDF, DOCX, PPTX, XLSX, TXT, MD
              </p>
              <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0
                              border-l-4 border-r-4 border-t-4
                              border-l-transparent border-r-transparent
                              border-t-[#18181c]" />
            </div>
          </div>
          <input ref={fileRef} type="file"
                 accept={SUPPORTED_EXTENSIONS.join(',')}
                 className="hidden"
                 onChange={e => handleFileSelect(e.target.files[0])} />

          {/* Text input */}
          <div className="flex-1 bg-white/[0.02] border border-white/8 rounded-2xl
                          px-4 py-2.5 focus-within:border-white/15 transition-colors">
            <input
              ref={inputRef}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
              placeholder={pendingFile
                ? `Ask about ${pendingFile.name} or press Enter to index it...`
                : 'Message Seven or type / for commands...'}
              disabled={sending || uploading}
              className="w-full bg-transparent text-[12.5px] text-white/75
                         placeholder-white/20 outline-none disabled:opacity-40" />
          </div>

          {/* Send button */}
          <button
            onClick={submit}
            disabled={(!draft.trim() && !pendingFile) || sending || uploading}
            className="p-2.5 rounded-xl bg-s-accent/90 text-white
                       hover:bg-s-accent disabled:opacity-25 disabled:bg-white/[0.04]
                       disabled:text-white/20 transition-all duration-150
                       flex-shrink-0 mb-px">
            {uploading
              ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              : <Send size={15} />}
          </button>
        </div>
      </div>
    </div>
  );
}