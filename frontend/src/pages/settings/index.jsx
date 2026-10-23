/**
 * Settings
 *
 * Left: section list. Right: the active section. Every control saves on change
 * (see save.js); the header shows one shared save status. Config is refetched
 * when the window regains focus, so a change made by chat ("set honesty to 75%")
 * shows up here without a reload. ?section=brain deep-links to a section.
 */
/* SEVEN_DOC {"purpose": "Everything you can configure: your profile and plan, the brain (model, personality, answers), voice, privacy and data, and system options",
              "keywords": ["settings", "preferences", "configure", "options", "voice", "model", "personality", "privacy", "hardware", "backup"]} */
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { User, Cpu, Mic, ShieldCheck, Monitor, Check, Loader2, AlertCircle } from 'lucide-react';
import useConfig from '../../stores/useConfig';
import { PageShell, LoadingRows } from '../../components/ui';
import { cx } from '../../lib/cx';
import { useSaveStatus } from './save';

import AccountSection from './AccountSection';
import BrainSection from './BrainSection';
import VoiceSection from './VoiceSection';
import PrivacySection from './PrivacySection';
import SystemSection from './SystemSection';

const SECTIONS = [
  { key: 'account', label: 'Account', icon: User, desc: 'Profile, plan and referrals', component: AccountSection },
  { key: 'brain', label: 'Brain', icon: Cpu, desc: 'Model, personality and how Seven answers', component: BrainSection },
  { key: 'voice', label: 'Voice', icon: Mic, desc: 'Speech, listening and voice security', component: VoiceSection },
  { key: 'privacy', label: 'Privacy & data', icon: ShieldCheck, desc: 'What leaves this computer, backups and memory', component: PrivacySection },
  { key: 'system', label: 'System', icon: Monitor, desc: 'Hardware, panels, shortcuts and repair', component: SystemSection },
];

function SaveIndicator() {
  const { status } = useSaveStatus();
  if (status === 'saving') {
    return <span className="flex items-center gap-1.5 text-[12px] text-s-text-3"><Loader2 size={13} className="animate-spin" />Saving</span>;
  }
  if (status === 'saved') {
    return <span className="flex items-center gap-1.5 text-[12px] text-s-text-3"><Check size={13} className="text-s-green" />All changes saved</span>;
  }
  if (status === 'error') {
    return <span className="flex items-center gap-1.5 text-[12px] text-s-red"><AlertCircle size={13} />Last change not saved</span>;
  }
  return <span className="text-[12px] text-s-text-4">Changes save automatically</span>;
}

export default function Settings() {
  const { config, loading, fetch } = useConfig();
  const [params, setParams] = useSearchParams();
  const active = SECTIONS.find(s => s.key === params.get('section')) || SECTIONS[0];
  const Active = active.component;

  useEffect(() => {
    fetch();
    useSaveStatus.setState({ status: 'idle' });
    const onFocus = () => fetch();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [fetch]);

  return (
    <PageShell title="Settings" description={active.desc} actions={<SaveIndicator />}>
      <div className="mx-auto flex max-w-[980px] gap-6 px-6 py-5">
        <nav aria-label="Settings sections" className="w-44 shrink-0">
          <ul className="sticky top-0 space-y-0.5">
            {SECTIONS.map(s => {
              const Icon = s.icon;
              const on = s.key === active.key;
              return (
                <li key={s.key}>
                  <button onClick={() => setParams({ section: s.key })} aria-current={on ? 'page' : undefined}
                          className={cx('flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-[12.5px] transition-colors',
                                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60',
                                        on ? 'bg-s-card-h text-s-text font-medium' : 'text-s-text-3 hover:bg-s-card hover:text-s-text')}>
                    <Icon size={15} className={on ? 'text-s-accent-h' : 'text-s-text-3'} />
                    {s.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div key={active.key} className="page-in min-w-0 flex-1 space-y-3.5 pb-10">
          {loading || !config ? <LoadingRows rows={5} /> : <Active config={config} />}
        </div>
      </div>
    </PageShell>
  );
}
