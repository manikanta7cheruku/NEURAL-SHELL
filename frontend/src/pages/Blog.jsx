import { useState } from 'react';
import PageHeader from '../components/PageHeader';

// ── Data ──────────────────────────────────────────────────────────────────────

const OVERVIEW_STATS = [
  { value: '100%',  label: 'Local AI',        sub: 'Nothing leaves your PC' },
  { value: '20+',   label: 'Voice Actions',   sub: 'Natural language control' },
  { value: '13',    label: 'Think Layers',    sub: 'Before every response' },
  { value: '0',     label: 'Cloud Calls',     sub: 'For core features' },
];

const HOW_IT_WORKS = [
  {
    step: '01',
    title: 'You Speak or Type',
    body: 'Seven listens through your microphone or accepts typed input in the Console. Voice goes through noise filtering, echo cancellation, and speech-to-text before reaching the brain.',
  },
  {
    step: '02',
    title: 'Seven Routes Your Request',
    body: 'Before the AI even runs, Seven checks if your request matches a direct action — launch an app, set a timer, complete a task. Direct actions fire instantly without waiting for the AI.',
  },
  {
    step: '03',
    title: 'The AI Thinks Locally',
    body: 'If no direct action matches, Ollama runs a local language model on your PC. Seven injects your memory, facts about you, and conversation history so the AI always has context.',
  },
  {
    step: '04',
    title: 'You Hear and See the Response',
    body: 'Seven speaks the response aloud using local text-to-speech. The Status Orb shows the current state. The conversation panel shows what was said.',
  },
];

const FEATURE_GROUPS = [
  {
    title: 'Voice Control',
    color: '#22c55e',
    features: [
      { name: 'Wake Word', desc: 'Say "Hey Seven" to activate from any state' },
      { name: 'Push to Talk', desc: 'Hold Shift to speak — no wake word needed' },
      { name: 'Pause / Resume', desc: 'Say "not you" to pause, "wake up" to resume' },
      { name: 'Interrupt', desc: 'Say "stop" mid-response to cut Seven off' },
      { name: 'Speaker Verify', desc: 'Only respond to your enrolled voice' },
    ],
  },
  {
    title: 'Tasks',
    color: '#6366f1',
    features: [
      { name: 'Create tasks by voice', desc: '"Add buy groceries to my tasks"' },
      { name: 'Complete tasks', desc: '"Mark the grocery task as done"' },
      { name: 'View tasks', desc: '"What do I have today?" or open the Tasks page' },
      { name: 'Subtasks', desc: 'Break tasks into steps — tracked separately' },
      { name: 'Due dates and priorities', desc: 'Set via voice or the Tasks page' },
    ],
  },
  {
    title: 'Schedules',
    color: '#f59e0b',
    features: [
      { name: 'Reminders', desc: '"Remind me to take medicine at 8pm"' },
      { name: 'Alarms', desc: '"Set a daily alarm for 7am"' },
      { name: 'Timers', desc: '"Set a timer for 25 minutes"' },
      { name: 'Recurring', desc: 'Daily, weekdays, or specific day each week' },
      { name: 'Overlay alerts', desc: 'Fires even when Seven window is hidden' },
    ],
  },
  {
    title: 'System Control',
    color: '#0ea5e9',
    features: [
      { name: 'App launcher', desc: '"Open Chrome", "Close Spotify"' },
      { name: 'Volume and brightness', desc: '"Mute", "Set brightness to 60 percent"' },
      { name: 'Window layout', desc: '"Snap Chrome left", "Minimize all"' },
      { name: 'File search', desc: '"Find my resume on this PC"' },
      { name: 'Battery status', desc: '"What is my battery level?"' },
    ],
  },
  {
    title: 'Memory',
    color: '#a855f7',
    features: [
      { name: 'Conversation history', desc: 'ChromaDB stores every exchange locally' },
      { name: 'User facts', desc: '"My name is..." saved permanently' },
      { name: 'Context recall', desc: 'Relevant past conversations injected into AI prompts' },
      { name: 'Knowledge base', desc: 'Upload PDFs and docs — ask questions from them' },
      { name: 'Export and backup', desc: 'Full memory export from Settings' },
    ],
  },
  {
    title: 'Triggers',
    color: '#ec4899',
    features: [
      { name: 'Voice triggers', desc: 'Custom phrase fires any action instantly' },
      { name: 'Hotkey triggers', desc: 'Keyboard shortcut fires an action' },
      { name: 'Workspaces', desc: 'Restore a full app and window layout in one command' },
      { name: 'Chrome tab sync', desc: 'Workspaces include browser tabs' },
      { name: 'Multi-action', desc: 'One trigger can open multiple apps and URLs' },
    ],
  },
];

const VOICE_EXAMPLES = [
  { category: 'Task',     phrase: '"Add finishing the report to my tasks"' },
  { category: 'Reminder', phrase: '"Remind me to call mom at 6pm"' },
  { category: 'App',      phrase: '"Open VS Code and Spotify"' },
  { category: 'File',     phrase: '"Find the project proposal on my PC"' },
  { category: 'Memory',   phrase: '"Remember I prefer concise answers"' },
  { category: 'Search',   phrase: '"Latest news about electric vehicles"' },
  { category: 'Layout',   phrase: '"Snap Chrome to the left side"' },
  { category: 'System',   phrase: '"What is my battery percentage?"' },
  { category: 'Timer',    phrase: '"Set a 20 minute focus timer"' },
  { category: 'Fact',     phrase: '"My team standup is at 10am daily"' },
];

const PRIVACY_POINTS = [
  { label: 'Voice audio',       stored: false, where: 'Processed locally, never saved' },
  { label: 'Conversations',     stored: true,  where: 'Your PC only — ChromaDB' },
  { label: 'User facts',        stored: true,  where: 'Your PC only — ChromaDB' },
  { label: 'Tasks and schedules', stored: true, where: 'Your PC only — SQLite' },
  { label: 'AI responses',      stored: false, where: 'Generated locally via Ollama' },
  { label: 'Usage statistics',  stored: false, where: 'Not collected' },
];

const SHORTCUTS = [
  { key: 'Alt + S',          action: 'Show or hide Seven window' },
  { key: 'Alt + Shift + T',  action: 'Open floating task panel' },
  { key: 'Shift (hold)',      action: 'Push to talk (when PTT enabled)' },
];

const ORB_STATES = [
  { color: '#3f3f46', label: 'Idle',      ring: 'rgba(255,255,255,0.04)', desc: 'Waiting — no input active' },
  { color: '#22c55e', label: 'Listening', ring: 'rgba(34,197,94,0.35)',   desc: 'Microphone active, ready for input' },
  { color: '#a855f7', label: 'Thinking',  ring: 'rgba(168,85,247,0.35)', desc: 'AI model generating response' },
  { color: '#6366f1', label: 'Speaking',  ring: 'rgba(99,102,241,0.35)', desc: 'Text to speech playing' },
];

// ── Components ────────────────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return (
    <p className="text-[8.5px] text-white/25 uppercase tracking-[0.2em] font-semibold mb-4">
      {children}
    </p>
  );
}

function Divider() {
  return <div className="h-px bg-white/[0.05] my-8" />;
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Blog() {
  const [activeGroup, setActiveGroup] = useState(0);

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        title="Guide"
        sub="How Seven works and what you can do with it"
      />

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-6 space-y-0">

          {/* ── Overview stats ── */}
          <SectionLabel>At a glance</SectionLabel>
          <div className="grid grid-cols-4 gap-3 mb-8">
            {OVERVIEW_STATS.map(s => (
              <div
                key={s.label}
                className="bg-white/[0.02] border border-white/6 rounded-2xl p-4"
              >
                <div className="text-[22px] font-bold font-mono text-white/80 leading-none">
                  {s.value}
                </div>
                <div className="text-[10px] font-semibold text-white/50 mt-2">
                  {s.label}
                </div>
                <div className="text-[8.5px] text-white/25 mt-0.5 leading-relaxed">
                  {s.sub}
                </div>
              </div>
            ))}
          </div>

          <Divider />

          {/* ── How it works ── */}
          <SectionLabel>How it works</SectionLabel>
          <div className="space-y-3 mb-2">
            {HOW_IT_WORKS.map((step, i) => (
              <div
                key={step.step}
                className="flex gap-5 bg-white/[0.015] border border-white/6
                           rounded-2xl px-5 py-4"
              >
                <div className="text-[11px] font-mono text-white/15 font-bold
                                pt-0.5 shrink-0 w-6">
                  {step.step}
                </div>
                <div>
                  <div className="text-[12px] font-semibold text-white/75 mb-1.5">
                    {step.title}
                  </div>
                  <div className="text-[11px] text-white/40 leading-relaxed font-light">
                    {step.body}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Divider />

          {/* ── What you can say ── */}
          <SectionLabel>What you can say</SectionLabel>
          <div className="grid grid-cols-2 gap-2 mb-2">
            {VOICE_EXAMPLES.map(ex => (
              <div
                key={ex.phrase}
                className="flex items-start gap-3 bg-white/[0.015] border border-white/6
                           rounded-xl px-4 py-3"
              >
                <span className="text-[8px] text-white/20 font-mono uppercase
                                 tracking-wider shrink-0 pt-0.5 w-14">
                  {ex.category}
                </span>
                <span className="text-[10.5px] text-white/55 font-light leading-relaxed italic">
                  {ex.phrase}
                </span>
              </div>
            ))}
          </div>

          <Divider />

          {/* ── Features by group ── */}
          <SectionLabel>Features</SectionLabel>

          {/* Tab row */}
          <div className="flex gap-1 mb-4 flex-wrap">
            {FEATURE_GROUPS.map((g, i) => (
              <button
                key={g.title}
                onClick={() => setActiveGroup(i)}
                className={`px-3 py-1.5 rounded-lg text-[9.5px] font-medium
                            transition-all duration-150 border
                  ${activeGroup === i
                    ? 'text-white/80 border-white/15 bg-white/[0.06]'
                    : 'text-white/30 border-transparent hover:text-white/50'}`}
              >
                {g.title}
              </button>
            ))}
          </div>

          {/* Feature list for active group */}
          {(() => {
            const g = FEATURE_GROUPS[activeGroup];
            return (
              <div
                className="border border-white/6 rounded-2xl overflow-hidden
                           bg-white/[0.015]"
              >
                {g.features.map((f, i) => (
                  <div
                    key={f.name}
                    className="flex items-start gap-4 px-5 py-3.5
                               border-b border-white/[0.04] last:border-0"
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                      style={{ background: g.color, opacity: 0.7 }}
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-[11px] font-semibold text-white/65">
                        {f.name}
                      </span>
                      <span className="text-[11px] text-white/30 font-light ml-2">
                        {f.desc}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            );
          })()}

          <Divider />

          {/* ── Status Orb ── */}
          <SectionLabel>Status orb</SectionLabel>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {ORB_STATES.map(s => (
              <div
                key={s.label}
                className="flex items-center gap-4 bg-white/[0.015] border
                           border-white/6 rounded-2xl px-4 py-3.5"
              >
                {/* Mini orb preview */}
                <div className="relative shrink-0 w-8 h-8 flex items-center justify-center">
                  <div
                    className="absolute w-8 h-8 rounded-full opacity-20 blur-sm"
                    style={{ background: s.color }}
                  />
                  <div
                    className="relative w-5 h-5 rounded-full border"
                    style={{
                      background: `radial-gradient(ellipse at 35% 30%, ${s.color}33 0%, #0a0a12 100%)`,
                      borderColor: s.ring,
                    }}
                  />
                </div>
                <div>
                  <div className="text-[11px] font-semibold text-white/65">{s.label}</div>
                  <div className="text-[9px] text-white/30 mt-0.5 leading-relaxed">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-white/[0.015] border border-white/6 rounded-2xl px-5 py-4 mb-2">
            <div className="text-[10px] font-semibold text-white/50 mb-3">Orb controls</div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { action: 'Left click',  result: 'Show or hide Seven' },
                { action: 'Right click', result: 'Navigation menu' },
                { action: 'Drag',        result: 'Move to any position' },
              ].map(c => (
                <div key={c.action} className="text-center">
                  <div className="text-[9px] font-mono text-white/30 bg-white/[0.04]
                                  border border-white/8 rounded-lg px-2 py-1 mb-1.5">
                    {c.action}
                  </div>
                  <div className="text-[9px] text-white/35">{c.result}</div>
                </div>
              ))}
            </div>
          </div>

          <Divider />

          {/* ── Privacy ── */}
          <SectionLabel>Privacy</SectionLabel>
          <div className="border border-white/6 rounded-2xl overflow-hidden
                          bg-white/[0.015] mb-4">
            <div className="grid grid-cols-3 px-5 py-2.5 border-b border-white/[0.06]">
              <span className="text-[8.5px] text-white/20 uppercase tracking-widest font-semibold">
                Data type
              </span>
              <span className="text-[8.5px] text-white/20 uppercase tracking-widest font-semibold">
                Stored
              </span>
              <span className="text-[8.5px] text-white/20 uppercase tracking-widest font-semibold">
                Location
              </span>
            </div>
            {PRIVACY_POINTS.map((p, i) => (
              <div
                key={p.label}
                className="grid grid-cols-3 px-5 py-3 border-b border-white/[0.04]
                           last:border-0 items-center"
              >
                <span className="text-[10.5px] text-white/55 font-light">{p.label}</span>
                <span className={`text-[9px] font-mono font-semibold
                  ${p.stored ? 'text-white/40' : 'text-white/20'}`}>
                  {p.stored ? 'Local only' : 'Never'}
                </span>
                <span className="text-[9.5px] text-white/30 font-light">{p.where}</span>
              </div>
            ))}
          </div>

          <Divider />

          {/* ── Shortcuts ── */}
          <SectionLabel>Keyboard shortcuts</SectionLabel>
          <div className="border border-white/6 rounded-2xl overflow-hidden
                          bg-white/[0.015]">
            {SHORTCUTS.map(s => (
              <div
                key={s.key}
                className="flex items-center gap-5 px-5 py-3.5
                           border-b border-white/[0.04] last:border-0"
              >
                <code className="text-[10px] font-mono text-white/45
                                 bg-white/[0.05] border border-white/10
                                 rounded-lg px-2.5 py-1 shrink-0 min-w-[120px]
                                 text-center">
                  {s.key}
                </code>
                <span className="text-[11px] text-white/45 font-light">{s.action}</span>
              </div>
            ))}
          </div>

          {/* Bottom padding */}
          <div className="h-6" />

        </div>
      </div>
    </div>
  );
}