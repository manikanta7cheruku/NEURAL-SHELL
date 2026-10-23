/**
 * KnowledgePanel.jsx
 * "What I know about you": every stored fact with its history, your goals, how you
 * asked Seven to talk, and the questions Seven is still curious about. Edit by
 * forgetting; nothing here is hidden from you.
 */
import { useEffect } from 'react';
import { X, Trash2 } from 'lucide-react';
import useChatSessions from '../stores/useChatSessions';

export default function KnowledgePanel({ onClose }) {
  const { profile, loadProfile, forgetFact } = useChatSessions();
  useEffect(() => { loadProfile(); }, []);
  const p = profile || { facts: [], goals: [], open_questions: [], style: {} };

  return (
    <div className="w-[300px] shrink-0 border-l border-white/[0.06] bg-white/[0.015] h-full overflow-y-auto">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div>
          <div className="text-[12px] font-semibold text-white/85">What I know about you</div>
          <div className="text-[11.5px] text-white/30">Stored only on this computer</div>
        </div>
        <button onClick={onClose} className="text-white/30 hover:text-white/70"><X size={13} /></button>
      </div>

      <Section title="Facts and preferences" empty="Nothing yet. Tell me something and I'll keep it.">
        {p.facts.map((f) => (
          <div key={f.id} className="group rounded-lg bg-white/[0.03] border border-white/[0.05] px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <span className="text-[11px] text-white/70">{f.text}</span>
              <button onClick={() => forgetFact(f.id)} title="Forget this" className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400"><Trash2 size={11} /></button>
            </div>
            <div className="text-[11.5px] text-white/30 mt-0.5">
              {f.origin === 'explicit' ? 'You said it' : 'Inferred'} · since {String(f.since).slice(0, 10)}
              {f.history?.length ? ` · before: ${f.history.join(', ')}` : ''}
            </div>
          </div>))}
      </Section>

      <Section title="Goals" empty="No goals yet.">
        {p.goals.map((g) => (
          <div key={g.id} className="text-[11px] text-white/65 rounded-lg bg-white/[0.03] border border-white/[0.05] px-3 py-2">
            {g.title}{g.deadline_text ? <span className="text-white/30"> · by {g.deadline_text}</span> : null}
          </div>))}
      </Section>

      <Section title="How you like me to talk" empty="">
        <div className="text-[12px] text-white/50 px-1">
          Answers: {p.style.verbosity || 'normal'} · Humor adjustment: {p.style.humor_bias || 0} · Tone: {p.style.formality || 'casual'}
        </div>
      </Section>

      <Section title="Things I'm curious about" empty="Nothing right now.">
        {p.open_questions.map((q) => (
          <div key={q.id} className="text-[12px] text-white/45 px-1">{q.kind.replace(/_/g, ' ')}: {q.subject}</div>))}
      </Section>
    </div>
  );
}

function Section({ title, empty, children }) {
  const items = Array.isArray(children) ? children.flat().filter(Boolean) : [children].filter(Boolean);
  return (
    <div className="px-4 py-3 space-y-1.5">
      <div className="text-[11px] text-white/25 pb-0.5">{title}</div>
      {items.length ? items : (empty ? <p className="text-[12px] text-white/30">{empty}</p> : null)}
    </div>
  );
}
