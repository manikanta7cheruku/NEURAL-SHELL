import { useRef, useEffect } from 'react';
import useChat from '../stores/useChat';
import PageHeader from '../components/PageHeader';

const CMDS = [
  { c: 'Memory', d: ['/memory', '/facts', '/convos', '/stats'] },
  { c: 'Logs', d: ['/logs', '/mood'] },
  { c: 'Manage', d: ['/add fact [text]', '/delete fact [n]', '/delete convo [n]'] },
  { c: 'Clear', d: ['/clear all', '/clear logs', '/clear mood'] },
  { c: 'Speakers', d: ['/speaker [name]', '/speakers'] },
  { c: 'Control', d: ['/windows', '/system', '/schedules'] },
  { c: 'Help', d: ['/help'] },
];

export default function Console() {
  const { messages, sending, draft, setDraft, send } = useChat();
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { inputRef.current?.focus(); }, [sending]);

  const submit = () => { if (!draft.trim() || sending) return; send(draft); };
  const ins = (c) => { setDraft(c.replace(/\[.*?\]/g, '').trim() + ' '); inputRef.current?.focus(); };

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Console" sub="Same brain as voice, all commands available"
        right={messages.length > 0 && <button onClick={useChat.getState().clear} className="text-[10px] text-s-text-4 hover:text-s-text-3">Clear</button>} />

      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 && (
          <div className="p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Commands</div>
            <div className="grid grid-cols-4 gap-1.5">
              {CMDS.map(g => (
                <div key={g.c} className="bg-s-card border border-s-border rounded p-2">
                  <div className="text-[10px] text-s-accent font-medium mb-1">{g.c}</div>
                  {g.d.map(cmd => (
                    <button key={cmd} onClick={() => ins(cmd)}
                      className="block w-full text-left text-[10.5px] text-s-text-3 hover:text-s-text-2 py-[2px] font-mono truncate">{cmd}</button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="px-4 py-3 space-y-2.5">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : ''} fin`}>
              <div className={`max-w-[72%] rounded px-3 py-2 ${
                m.role === 'user' ? 'bg-s-accent text-white'
                : m.error ? 'bg-s-red/8 border border-s-red/15 text-red-300'
                : 'bg-s-card border border-s-border text-s-text-2'
              }`}>
                <p className="text-[12.5px] leading-[1.6] whitespace-pre-wrap">{m.text}</p>
                {m.actions?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {m.actions.map((a, j) => <span key={j} className="px-1.5 py-0.5 bg-white/8 text-[8px] rounded font-mono">{a}</span>)}
                  </div>
                )}
                <div className={`text-[8px] mt-1 ${m.role === 'user' ? 'text-white/40 text-right' : 'text-s-text-4'}`}>
                  {m.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex fin">
              <div className="bg-s-card border border-s-border rounded px-3 py-2.5 flex gap-1">
                {[0,1,2].map(d => <div key={d} className="w-1 h-1 rounded-full bg-s-accent animate-pulse" style={{ animationDelay: `${d * 150}ms` }} />)}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="px-4 py-3 border-t border-s-border bg-s-bg">
        <div className="flex gap-2">
          <input ref={inputRef} value={draft} onChange={e => setDraft(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), submit())}
            placeholder="Message Seven or type / for commands..."
            disabled={sending}
            className="flex-1 bg-s-card border border-s-border rounded px-3 py-2 text-[12.5px] text-s-text placeholder-s-text-4 disabled:opacity-40 font-sans" />
          <button onClick={submit} disabled={!draft.trim() || sending}
            className="px-4 py-2 border border-s-accent/30 bg-s-accent/8 text-s-accent hover:bg-s-accent/15 disabled:border-s-border disabled:bg-transparent disabled:text-s-text-4 rounded text-[12px] font-medium">
            Send
          </button>
        </div>
      </div>
    </div>
  );
}