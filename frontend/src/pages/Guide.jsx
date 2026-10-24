/**
 * Guide
 *
 * How to use Seven, written for people who just installed it. It opens with
 * live commands the user can run with one click, then walks through every
 * ability with phrases that work today, the first-run setup, privacy facts,
 * common questions, shortcuts and what is planned next.
 *
 * Commands and example phrases live in ../guide/guide.json. A backend test
 * (tests/test_guide_commands.py) sends each one through the brain, so the
 * Guide can't promise something Seven no longer understands.
 */
/* SEVEN_DOC {"purpose": "Learn how to use Seven: try live commands, see everything Seven can do with example phrases, set it up, privacy facts, questions and shortcuts",
              "keywords": ["guide", "help", "how", "tutorial", "learn", "examples", "commands", "faq", "shortcuts", "what can you do"],
              "controls": [
                {"label": "Try it now", "description": "Run real commands like max brightness or open Chrome with one click."},
                {"label": "What Seven can do", "description": "Every ability with phrases you can say or type."},
                {"label": "Set up Seven", "description": "A short checklist: your name, your voice, a workspace, a trigger and your documents."},
                {"label": "Questions", "description": "Answers about privacy, the internet, models and troubleshooting."}
              ]} */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Play, RotateCcw, Copy, Check, ArrowRight, Loader2, Mic, MessageSquare, PanelRight, ShieldCheck, WifiOff,
  HardDrive, Search, ChevronDown, Sparkles, AppWindow, SlidersHorizontal, Cpu, FolderSearch, LayoutGrid,
  ListChecks, AlarmClock, Brain, Settings2, CircleCheck,
} from 'lucide-react';
import api from '../api';
import useConfig from '../stores/useConfig';
import useStatus from '../stores/useStatus';
import { PageShell, Badge, Button, Input } from '../components/ui';
import { cx } from '../lib/cx';
import { toast } from '../lib/toast';
import GUIDE from '../guide/guide.json';

const GROUP_ICONS = {
  apps: AppWindow, system: SlidersHorizontal, pc: Cpu, files: FolderSearch, workspaces: LayoutGrid,
  tasks: ListChecks, schedules: AlarmClock, memory: Brain, personality: Settings2,
};

const NAV = [
  ['try', 'Try it'], ['talk', 'Talk to Seven'], ['abilities', 'What it can do'], ['setup', 'Set up'],
  ['privacy', 'Privacy'], ['questions', 'Questions'], ['shortcuts', 'Shortcuts'], ['next', 'Coming next'],
];

const FAQ = [
  ['Does Seven need the internet?',
    'No. Talking, memory, tasks, reminders, apps, windows, files and system controls all work offline. The internet is only used for live lookups such as weather and news, checking for updates, plan activation and sending feedback, and each of these says so when you are offline.'],
  ['Is anything I say sent to a server?',
    'No. Speech recognition, the language model and your memory all run on this computer. Seven does not upload your conversations, files or voice. You can see and delete everything Seven stores on the Memory page and in Settings, Privacy & data.'],
  ['Which AI model does Seven use?',
    'A local model running through Ollama. On "auto", Seven picks one that fits your graphics card and memory. You can switch models in Settings, Brain, or just say "use the mistral model".'],
  ['Seven did not hear me.',
    'Check that the right microphone is selected in Settings, Voice. You can also hold Shift to talk without the wake word, or type in the Console. If background noise wakes Seven by mistake, raise the listening threshold in the same section.'],
  ['Seven opened the wrong app or file.',
    'Say the full name the first time, like "open Visual Studio Code". If Seven gets it wrong, tell it the right one. It remembers corrections and offers to save the name for next time.'],
  ['How do I stop Seven while it is talking?',
    'Say "stop", or simply start talking. Seven stops and listens. To pause listening altogether, say "hold on" or "not you", and "wake up" when you need it again.'],
  ['Can Seven see my screen or click buttons for me?',
    'Not yet. Seven can open, close and arrange apps and change system settings. Reading the screen and controlling the mouse and keyboard are next on the roadmap.'],
  ['How does Seven read my documents if it cannot see?',
    'It reads the text stored inside the file: each page of a PDF, the paragraphs and tables of a Word file, the text on slides and the cells of a sheet. That happens once, on this computer, when you add the file. A PDF that is only a scan has pictures of pages and no text, so convert it with OCR first. Answers point to the page they came from.'],
  ['Why are some browser tabs missing from a workspace?',
    'Windows tells Seven the title of every tab but only the address of the tab you are looking at. Add the Seven extension to Chrome, Edge or Brave (Triggers, Workspaces, at the bottom) and every tab is saved with its address. Private windows are never saved.'],
  ['What is the difference between the plans?',
    'Every plan runs fully on your computer. Paid plans raise limits on schedules, triggers and documents and add extras such as voice recognition. The Plans page shows the exact limits.'],
  ['Something is broken. How do I tell you?',
    'Open Feedback in the sidebar. Your report goes straight to the team, and if you are offline it is saved and sent automatically later.'],
];

const SHORTCUTS = [
  [['Alt', 'S'], 'Show or hide Seven'],
  [['Alt', 'Shift', 'T'], 'Open the floating task panel'],
  [['Shift'], 'Hold to talk without the wake word'],
  [['Ctrl', 'N'], 'New chat in the Console'],
  [['Ctrl', 'Shift', 'S'], 'Show or hide the chats list'],
  [['Enter'], 'Send a message'],
  [['Shift', 'Enter'], 'New line in a message'],
  [['1', '4'], 'Jump to a page from the home screen'],
];

const ROADMAP = [
  ['Sees your screen', 'Ask what an error says, have an email read aloud, or get a summary of the page in front of you.'],
  ['Mouse and keyboard control', 'Click buttons by name, scroll, type into any app and fill forms from what Seven knows about you.'],
  ['Multi-step tasks', 'One request becomes a plan you approve, like "download this PDF and summarize it".'],
  ['Looks after your PC', 'Warns when the disk is nearly full or an app is eating memory, and retries failed actions another way.'],
  ['Organizes your files', '"Organize my Downloads by type" or "move yesterday\'s screenshots into a folder".'],
  ['Messages and email', 'Draft replies in your style. Nothing is sent until you approve it.'],
  ['Phone companion', 'Control Seven on your PC from your phone, with memory that follows you.'],
  ['Plugins and shared workflows', 'Add new skills to Seven and share the routines you build.'],
  ['More languages', 'Seven understands and replies in your language.'],
  ['Safety shield', 'Your voice or a PIN is required before anything destructive.'],
];

function useRun() {
  const [runs, setRuns] = useState({});
  const run = async (key, say) => {
    setRuns(r => ({ ...r, [key]: { state: 'running' } }));
    try {
      const { data } = await api.post('/chat', { text: say, speaker_id: 'default', stream: false });
      // Seven reconciles its reply with what actually happened; a failed receipt means it didn't work.
      const failed = (data?.receipts || []).some(rc => rc.status === 'failed');
      setRuns(r => ({ ...r, [key]: { state: failed ? 'failed' : 'done', reply: (data?.response || 'Done.').trim() } }));
    } catch (err) {
      const reply = err?.response ? 'Seven could not finish that. Try it in the Console to see why.' : 'Seven is not running yet. Give it a moment and try again.';
      setRuns(r => ({ ...r, [key]: { state: 'failed', reply } }));
    }
  };
  return [runs, run];
}

function copy(text) {
  navigator.clipboard?.writeText(text).then(() => toast.success('Copied')).catch(() => {});
}

function Heading({ id, eyebrow, title, description }) {
  return (
    <div id={id} className="scroll-mt-16 mb-3">
      {eyebrow && <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-s-accent-h">{eyebrow}</div>}
      <h2 className="mt-0.5 text-[14px] font-semibold text-s-text tracking-[-0.01em]">{title}</h2>
      {description && <p className="mt-0.5 max-w-[620px] text-[12px] leading-relaxed text-s-text-3">{description}</p>}
    </div>
  );
}

function Kbd({ children }) {
  return <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-s-border bg-s-card px-1.5 text-[10.5px] font-medium text-s-text-2">{children}</kbd>;
}

function Reply({ run }) {
  if (!run || run.state === 'running') return null;
  return (
    <p className={cx('mt-2 rounded-md px-2.5 py-1.5 text-[11.5px] leading-relaxed animate-[fadeIn_.25s_ease-out]',
                     run.state === 'failed' ? 'bg-s-red/10 text-s-red' : 'bg-s-card text-s-text-2')}>
      {run.reply}
    </p>
  );
}

function TryCard({ item, run, onRun }) {
  const busy = run?.state === 'running';
  const done = run?.state === 'done';
  return (
    <div className="group/t flex flex-col rounded-lg border border-s-border bg-s-surface p-3 shadow-[var(--s-shadow)] transition-colors hover:border-s-border-l">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[12.5px] font-medium text-s-text">{item.title}</div>
          <div className="mt-0.5 text-[11.5px] text-s-text-3">{item.detail}</div>
        </div>
        {done && <Check size={14} className="mt-0.5 shrink-0 text-s-green" />}
      </div>
      <button onClick={() => copy(item.say)} title="Copy"
              className="mt-2.5 flex items-center justify-between gap-2 rounded-md border border-dashed border-s-border px-2 py-1 text-left text-[11.5px] text-s-text-2 transition-colors hover:border-s-border-l hover:text-s-text">
        <span className="truncate">"{item.say}"</span>
        <Copy size={11} className="shrink-0 opacity-0 transition-opacity group-hover/t:opacity-60" />
      </button>
      <Reply run={run} />
      <div className="mt-auto flex items-center gap-1.5 pt-2.5">
        <Button size="sm" variant={done ? 'secondary' : 'primary'} icon={busy ? undefined : Play} loading={busy}
                onClick={() => onRun(item.id, item.say)}>
          {busy ? 'Running' : done ? 'Run again' : 'Run'}
        </Button>
        {item.undo && done && (
          <Button size="sm" variant="ghost" icon={RotateCcw} onClick={() => onRun(item.id, item.undo.say)}>{item.undo.label}</Button>
        )}
      </div>
    </div>
  );
}

function GroupCard({ group, runs, onRun, navigate }) {
  const Icon = GROUP_ICONS[group.id] || Sparkles;
  const last = group.examples.map((ex, i) => runs[`${group.id}:${i}`]).filter(Boolean).pop();
  return (
    <div className="rounded-lg border border-s-border bg-s-surface p-3.5 shadow-[var(--s-shadow)]">
      <div className="flex items-start gap-2.5">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-s-border bg-s-card">
          <Icon size={14} className="text-s-text-2" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[12.5px] font-semibold text-s-text">{group.title}</h3>
            <button onClick={() => navigate(group.page)}
                    className="flex items-center gap-1 text-[11px] text-s-text-3 transition-colors hover:text-s-accent-h">
              {group.pageLabel}<ArrowRight size={11} />
            </button>
          </div>
          <p className="mt-0.5 text-[11.5px] leading-relaxed text-s-text-3">{group.summary}</p>
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {group.examples.map((ex, i) => {
          const key = `${group.id}:${i}`;
          const busy = runs[key]?.state === 'running';
          return (
            <button key={ex.say} onClick={() => onRun(key, ex.say)} disabled={busy} title="Click to run, right-click to copy"
                    onContextMenu={e => { e.preventDefault(); copy(ex.say); }}
                    className="flex h-6 items-center gap-1 rounded-full border border-s-border bg-s-card px-2.5 text-[11.5px] text-s-text-2
                               transition-colors hover:border-s-accent/40 hover:text-s-text disabled:opacity-60">
              {busy && <Loader2 size={10} className="animate-spin" />}
              {ex.say}
            </button>
          );
        })}
      </div>
      <Reply run={last} />
    </div>
  );
}

function SetupStep({ n, title, body, done, action, onAction }) {
  return (
    <div className="flex items-start gap-3 px-3.5 py-3">
      {done ? <CircleCheck size={16} className="mt-0.5 shrink-0 text-s-green" />
            : <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-s-border-l text-[9.5px] font-semibold text-s-text-3">{n}</span>}
      <div className="min-w-0 flex-1">
        <div className={cx('text-[12.5px] font-medium', done ? 'text-s-text-3 line-through decoration-s-text-4' : 'text-s-text')}>{title}</div>
        <p className="mt-0.5 text-[11.5px] leading-relaxed text-s-text-3">{body}</p>
      </div>
      {action && <Button size="sm" variant="secondary" onClick={onAction}>{action}</Button>}
    </div>
  );
}

export default function Guide() {
  const navigate = useNavigate();
  const { config } = useConfig();
  const version = useStatus(s => s.version);
  const [runs, run] = useRun();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(0);
  const [counts, setCounts] = useState({ workspaces: null, triggers: null });

  useEffect(() => {
    api.get('/workspaces').then(r => setCounts(c => ({ ...c, workspaces: (r.data?.workspaces || r.data || []).length }))).catch(() => {});
    api.get('/triggers').then(r => setCounts(c => ({ ...c, triggers: (r.data?.triggers || r.data || []).length }))).catch(() => {});
  }, []);

  const identity = config?.identity || {};
  const wake = (identity.wake_words || ['seven', 'hey seven']).map(w => `"${w}"`).join(' or ');
  const pause = (identity.pause_words || ['hold on', 'not you']).slice(0, 2).map(w => `"${w}"`).join(' or ');
  const resume = (identity.resume_words || ['wake up'])[0];

  const q = query.trim().toLowerCase();
  const groups = useMemo(() => GUIDE.groups.filter(g => !q || [g.title, g.summary, ...g.examples.map(e => e.say)]
    .some(t => t.toLowerCase().includes(q))), [q]);
  const faq = useMemo(() => FAQ.filter(([a, b]) => !q || `${a} ${b}`.toLowerCase().includes(q)), [q]);

  const jump = id => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const steps = [
    { title: 'Tell Seven your name', body: 'Seven greets you by name and keeps your memories under it.',
      done: !!(identity.user_name || '').trim(), action: 'Account', to: '/settings?section=account' },
    { title: 'Teach Seven your voice', body: `Pick your microphone and try the wake word: say ${wake}. Voice recognition lets Seven tell you apart from others in the room.`,
      action: 'Voice settings', to: '/settings?section=voice' },
    { title: 'Save your first workspace', body: 'Open the apps and tabs you use for work, then say "Save this workspace as Work". Next time, "Restore workspace Work" brings everything back. You can also scan and save from the Triggers page.',
      done: counts.workspaces > 0, action: 'Workspaces', to: '/triggers' },
    { title: 'Make a trigger', body: 'Pick a phrase or hotkey and the apps, sites or actions it should run. One sentence can set up your whole morning.',
      done: counts.triggers > 0, action: 'Triggers', to: '/triggers' },
    { title: 'Add your documents', body: 'Add PDFs, notes and docs to Knowledge and ask questions about them. They are indexed on this computer.',
      action: 'Knowledge', to: '/knowledge' },
    { title: 'Make Seven sound like you want', body: 'Choose the model and set humor, honesty and answer length. Or just say "set humor to 40%".',
      action: 'Brain settings', to: '/settings?section=brain' },
  ];
  const doneCount = steps.filter(s => s.done).length;

  return (
    <PageShell title="Guide" description="What Seven can do and how to get the most from it"
               actions={<div className="relative w-56">
                 <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-s-text-4" />
                 <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search the guide" className="pl-7" />
               </div>}
               toolbar={<nav className="-mb-1 flex gap-1 overflow-x-auto">
                 {NAV.map(([id, label]) => (
                   <button key={id} onClick={() => jump(id)}
                           className="h-6 shrink-0 rounded-md px-2 text-[11.5px] text-s-text-3 transition-colors hover:bg-s-card hover:text-s-text">{label}</button>
                 ))}
               </nav>}>
      <div className="mx-auto max-w-[980px] space-y-10 px-6 py-6">

        {!q && (
          <section className="relative overflow-hidden rounded-xl border border-s-border bg-s-surface px-6 py-6 shadow-[var(--s-shadow)]">
            <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full"
                 style={{ background: 'radial-gradient(circle, color-mix(in oklab, var(--color-s-accent) 16%, transparent), transparent 70%)' }} />
            <Badge tone="accent">Seven {version || ''}</Badge>
            <h1 className="mt-3 max-w-[560px] text-[20px] font-semibold leading-snug tracking-[-0.02em] text-s-text">
              The layer between you and your computer.
            </h1>
            <p className="mt-2 max-w-[600px] text-[12.5px] leading-relaxed text-s-text-2">
              Say it or type it, and Seven does it on this PC: opens and arranges apps, changes settings, finds files,
              runs your routines and remembers what matters to you. It all runs on this computer and keeps working without the internet.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {[[HardDrive, 'Runs on this PC'], [WifiOff, 'Works offline'], [ShieldCheck, 'Your data stays here']].map(([I, t]) => (
                <span key={t} className="flex h-6 items-center gap-1.5 rounded-full border border-s-border bg-s-card px-2.5 text-[11.5px] text-s-text-2">
                  <I size={12} className="text-s-accent-h" />{t}
                </span>
              ))}
            </div>
          </section>
        )}

        {!q && (
          <section>
            <Heading id="try" eyebrow="Start here" title="Try it now"
                     description="These run for real on your computer, exactly as if you had said them. Press Run and watch." />
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
              {GUIDE.tryIt.map(item => <TryCard key={item.id} item={item} run={runs[item.id]} onRun={run} />)}
            </div>
          </section>
        )}

        {!q && (
          <section>
            <Heading id="talk" title="Three ways to talk to Seven" description="Use whichever fits the moment. They all reach the same Seven with the same memory." />
            <div className="grid grid-cols-1 gap-2.5 md:grid-cols-3">
              {[
                [Mic, 'Voice', <>Say {wake}, then what you need. Hold <Kbd>Shift</Kbd> to talk without the wake word. Talk over Seven or say "stop" to interrupt. Say {pause} to pause and "{resume}" to resume.</>],
                [MessageSquare, 'Console', <>Type anything, the same as speaking. Seven shows what it did after each reply, and chats are saved so you can pick them up later.</>, '/console'],
                [PanelRight, 'Task panel', <>Press <Kbd>Alt</Kbd> <Kbd>Shift</Kbd> <Kbd>T</Kbd> anywhere for a small panel with your tasks and reminders, on top of whatever you are doing.</>],
              ].map(([I, title, body, to]) => (
                <div key={title} className="rounded-lg border border-s-border bg-s-surface p-3.5 shadow-[var(--s-shadow)]">
                  <div className="flex items-center gap-2">
                    <I size={14} className="text-s-accent-h" />
                    <span className="text-[12.5px] font-semibold text-s-text">{title}</span>
                    {to && <button onClick={() => navigate(to)} className="ml-auto text-s-text-3 hover:text-s-accent-h"><ArrowRight size={13} /></button>}
                  </div>
                  <p className="mt-1.5 text-[11.5px] leading-relaxed text-s-text-3">{body}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <Heading id="abilities" title="What Seven can do today"
                   description="Click a phrase to run it, right-click to copy it. You don't have to use these exact words; say it the way you normally would." />
          {groups.length ? (
            <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-2">
              {groups.map(g => <GroupCard key={g.id} group={g} runs={runs} onRun={run} navigate={navigate} />)}
            </div>
          ) : <p className="text-[12px] text-s-text-3">Nothing here matches "{query}".</p>}
        </section>

        {!q && (
          <section>
            <Heading id="setup" title="Set Seven up in five minutes"
                     description={`${doneCount} of ${steps.length} done. Each step makes Seven a little more yours.`} />
            <div className="divide-y divide-s-border/70 rounded-lg border border-s-border bg-s-surface shadow-[var(--s-shadow)]">
              {steps.map((s, i) => <SetupStep key={s.title} n={i + 1} {...s} onAction={() => navigate(s.to)} />)}
            </div>
          </section>
        )}

        {!q && (
          <section>
            <Heading id="privacy" title="Privacy, in plain words" />
            <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
              {[
                ['Everything runs here', 'Speech recognition, the AI model, voice and memory all run on this computer. There is no Seven cloud reading your conversations.'],
                ['Your data is yours', 'Conversations, memories, tasks and settings live in a folder on this PC. See, edit or delete any of it on the Memory page, or wipe everything from Settings.'],
                ['Online only when you ask', 'Weather, news and prices need the internet. So do updates, plan activation and feedback. Seven tells you when it is offline instead of guessing.'],
                ['Risky actions ask first', 'Before something hard to undo, Seven checks with you. It also tells you plainly when an action failed instead of pretending it worked.'],
              ].map(([t, b]) => (
                <div key={t} className="rounded-lg border border-s-border bg-s-surface p-3.5 shadow-[var(--s-shadow)]">
                  <div className="flex items-center gap-2 text-[12.5px] font-semibold text-s-text"><ShieldCheck size={13} className="text-s-green" />{t}</div>
                  <p className="mt-1 text-[11.5px] leading-relaxed text-s-text-3">{b}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <Heading id="questions" title="Questions" />
          {faq.length ? (
            <div className="divide-y divide-s-border/70 rounded-lg border border-s-border bg-s-surface shadow-[var(--s-shadow)]">
              {faq.map(([question, answer], i) => {
                const isOpen = open === i || !!q;
                return (
                  <div key={question}>
                    <button onClick={() => setOpen(isOpen && !q ? -1 : i)}
                            className="flex w-full items-center justify-between gap-4 px-3.5 py-2.5 text-left text-[12.5px] font-medium text-s-text hover:bg-s-card/50">
                      {question}
                      <ChevronDown size={14} className={cx('shrink-0 text-s-text-3 transition-transform duration-200', isOpen && 'rotate-180')} />
                    </button>
                    <div className={cx('grid transition-all duration-200 ease-out', isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}>
                      <p className="overflow-hidden px-3.5 text-[12px] leading-relaxed text-s-text-3">
                        <span className="block pb-3">{answer}</span>
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : <p className="text-[12px] text-s-text-3">No questions match "{query}".</p>}
        </section>

        {!q && (
          <section>
            <Heading id="shortcuts" title="Keyboard shortcuts" />
            <div className="grid grid-cols-1 gap-x-6 rounded-lg border border-s-border bg-s-surface px-3.5 py-1 shadow-[var(--s-shadow)] md:grid-cols-2">
              {SHORTCUTS.map(([keys, label]) => (
                <div key={label} className="flex items-center justify-between gap-4 border-b border-s-border/60 py-2 last:border-0 md:[&:nth-last-child(2)]:border-0">
                  <span className="text-[12px] text-s-text-2">{label}</span>
                  <span className="flex items-center gap-1">
                    {keys.map((k, i) => <span key={k} className="flex items-center gap-1">{i > 0 && <span className="text-[10px] text-s-text-4">{keys[0] === '1' ? 'to' : '+'}</span>}<Kbd>{k}</Kbd></span>)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {!q && (
          <section>
            <Heading id="next" eyebrow="Roadmap" title="Coming next"
                     description="Where Seven is heading. These are planned, not available yet, and Seven will tell you so if you ask for them today." />
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {ROADMAP.map(([t, b]) => (
                <div key={t} className="flex items-start gap-2.5 rounded-lg border border-dashed border-s-border px-3.5 py-2.5">
                  <Sparkles size={13} className="mt-0.5 shrink-0 text-s-purple" />
                  <div>
                    <div className="text-[12.5px] font-medium text-s-text">{t}</div>
                    <p className="mt-0.5 text-[11.5px] leading-relaxed text-s-text-3">{b}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-s-border pt-4 text-[11.5px] text-s-text-4">
              <span>Seven {version} by Seven Labs. Runs on this computer.</span>
              <span className="flex gap-3">
                <button onClick={() => navigate('/feedback')} className="hover:text-s-text-2">Send feedback</button>
                <button onClick={() => navigate('/updates')} className="hover:text-s-text-2">What's new</button>
                <button onClick={() => navigate('/plans')} className="hover:text-s-text-2">Plans</button>
              </span>
            </div>
          </section>
        )}
      </div>
    </PageShell>
  );
}
