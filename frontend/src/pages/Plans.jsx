/**
 * Plans
 *
 * Limits and prices come from /api/license/pricing, which reads license.py:
 * the same table the app enforces, so this page can't drift from reality.
 * Seven runs fully on the user's computer on every plan; paid plans raise
 * limits and add extras.
 */
/* SEVEN_DOC {"purpose": "Compare Free, Pro and Ultimate, buy a plan, activate a license key or start a free trial",
              "keywords": ["plans", "pricing", "price", "upgrade", "pro", "ultimate", "license", "trial", "subscription"],
              "controls": [
                {"label": "Compare plans", "description": "Limits for schedules, triggers, knowledge files and more on each plan."},
                {"label": "Activate a license key", "description": "Paste the key from your purchase email."},
                {"label": "Start trial", "description": "Try Pro free for 14 days."}
              ]} */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Minus, KeyRound, Sparkles, Gift } from 'lucide-react';
import api from '../api';
import useConfig from '../stores/useConfig';
import useLicense from '../stores/useLicense';
import { PageShell, Section, Row, Button, Input, Badge, Segmented, LoadingRows } from '../components/ui';
import { cx } from '../lib/cx';
import { toast } from '../lib/toast';

const TIERS = ['free', 'pro', 'ultimate'];
const NAMES = { free: 'Free', pro: 'Pro', ultimate: 'Ultimate' };
const TAGLINES = {
  free: 'Everything you need to run Seven every day.',
  pro: 'Higher limits for people who use Seven all day.',
  ultimate: 'No limits, voice recognition and every future feature.',
};
const PERIODS = [{ value: 'monthly', label: 'Monthly' }, { value: 'yearly', label: 'Yearly' }, { value: 'lifetime', label: 'Lifetime' }];
const PERIOD_SUFFIX = { monthly: '/month', yearly: '/year', lifetime: 'one time' };
const WINDOW = { basic: 'Basic', advanced: 'Advanced', full: 'Full' };

// Rows of the comparison table: [label, value(features) => display]
const ROWS = [
  ['Facts and conversation history', () => 'Unlimited'],
  ['Tasks and workspaces', () => 'Unlimited'],
  ['Schedules and reminders', f => f.schedules],
  ['Triggers and hotkeys', f => f.triggers],
  ['Knowledge files', f => f.knowledge_files],
  ['Web searches per day', f => f.web_searches_per_day],
  ['App aliases', f => f.app_aliases],
  ['URL shortcuts', f => f.url_shortcuts],
  ['Custom commands', f => f.custom_commands],
  ['Window control', f => WINDOW[f.window_control] || f.window_control],
  ['Recurring schedules', f => f.recurring_schedules],
  ['Voice recognition', f => f.voice_recognition],
  ['Memory export', f => f.memory_export],
  ['Devices', f => f.max_devices],
];

const ROADMAP = [
  ['Screen understanding', 'Seven sees what is on your screen and can help with it.'],
  ['Click and type by voice', 'Press buttons, fill fields and move the cursor by asking.'],
  ['Presence detection', 'Wake and sleep automatically when you sit down or leave.'],
  ['Multi-monitor control', 'Arrange windows across two or three screens by voice.'],
];

function show(v) {
  if (v === true) return <Check size={15} className="mx-auto text-s-green" aria-label="Included" />;
  if (v === false || v === 0) return <Minus size={15} className="mx-auto text-s-text-4" aria-label="Not included" />;
  if (v === -1) return 'Unlimited';
  return v;
}

function highlights(f) {
  const lim = (v, noun) => (v === -1 ? `Unlimited ${noun}` : `${v} ${v === 1 ? noun.replace(/s$/, '') : noun}`);
  const out = ['Unlimited memory and conversations', lim(f.schedules, 'schedules'), lim(f.triggers, 'triggers and hotkeys'),
               lim(f.knowledge_files, 'knowledge files')];
  if (f.voice_recognition) out.push('Voice recognition');
  if (f.max_devices > 1) out.push(`Use on ${f.max_devices} devices`);
  return out;
}

function money(n) {
  return `₹${Number(n).toLocaleString('en-IN')}`;
}

function CurrentPlan({ tier, isTrial, daysUntilExpiry }) {
  const paid = tier !== 'free';
  let status = 'Free forever. Upgrade any time.';
  let tone = 'text-s-text-3';
  if (paid) {
    if (daysUntilExpiry == null) { status = 'Lifetime access'; tone = 'text-s-green'; }
    else if (daysUntilExpiry <= 0) { status = 'Expired. Activate a new key to keep your plan.'; tone = 'text-s-red'; }
    else {
      status = `${isTrial ? 'Trial ends' : 'Renews or expires'} in ${daysUntilExpiry} day${daysUntilExpiry === 1 ? '' : 's'}`;
      tone = daysUntilExpiry <= 3 ? 'text-s-red' : daysUntilExpiry <= 7 ? 'text-s-yellow' : 'text-s-text-3';
    }
  }
  return (
    <div className="flex items-center justify-between rounded-xl border border-s-border bg-s-surface px-5 py-4 shadow-[var(--s-shadow)]">
      <div>
        <div className="text-[12px] text-s-text-3">Your plan</div>
        <div className="mt-0.5 flex items-center gap-2">
          <span className="text-[17px] font-semibold text-s-text">{NAMES[tier] || 'Free'}</span>
          {isTrial && <Badge tone="warning">Trial</Badge>}
        </div>
        <div className={cx('mt-0.5 text-[12px]', tone)}>{status}</div>
      </div>
      <Button variant="ghost" onClick={() => window.__navigate?.('/blog')}>How to use Seven</Button>
    </div>
  );
}

function PlanCard({ tier, features, price, period, current, onChoose }) {
  const featured = tier === 'pro';
  return (
    <div className={cx('flex flex-col rounded-xl border bg-s-surface p-5 shadow-[var(--s-shadow)]',
                       featured ? 'border-s-accent/60' : 'border-s-border')}>
      <div className="flex h-5 items-center justify-between">
        <span className="text-[14px] font-semibold text-s-text">{NAMES[tier]}</span>
        {featured && <span className="text-[12px] font-medium text-s-accent-h">Most popular</span>}
      </div>
      <p className="mt-1 min-h-[36px] text-[12px] leading-relaxed text-s-text-3">{TAGLINES[tier]}</p>
      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="text-[28px] font-semibold tracking-[-0.02em] text-s-text tabular-nums">{tier === 'free' ? money(0) : money(price)}</span>
        <span className="text-[12px] text-s-text-3">{tier === 'free' ? 'forever' : PERIOD_SUFFIX[period]}</span>
      </div>
      <ul className="mt-4 flex-1 space-y-2">
        {highlights(features).map(h => (
          <li key={h} className="flex items-start gap-2 text-[13px] text-s-text-2">
            <Check size={14} className="mt-0.5 shrink-0 text-s-accent-h" />{h}
          </li>
        ))}
      </ul>
      <div className="mt-5">
        {current ? (
          <Button className="w-full" disabled>Current plan</Button>
        ) : tier === 'free' ? (
          <Button className="w-full" variant="ghost" disabled>Included</Button>
        ) : (
          <Button className="w-full" variant={featured ? 'primary' : 'secondary'} onClick={onChoose}>
            Get {NAMES[tier]}
          </Button>
        )}
      </div>
    </div>
  );
}

function Activate({ tier }) {
  const { activate, startTrial } = useLicense();
  const { config } = useConfig();
  const [key, setKey] = useState('');
  const [email, setEmail] = useState(config?.email || '');
  const [busy, setBusy] = useState(null);

  const run = async (which) => {
    setBusy(which);
    const result = which === 'key' ? await activate(key.trim(), config?.email || null) : await startTrial(email.trim());
    setBusy(null);
    if (result.success) {
      toast.success(which === 'key' ? 'License activated' : 'Pro trial started', result.message);
      setKey('');
    } else {
      toast.error(which === 'key' ? 'Activation failed' : 'Could not start the trial', result.message);
    }
  };

  return (
    <Section title="License">
      <Row label={tier === 'free' ? 'Activate a license key' : 'Use a different license key'}
           description="Paste the key from your purchase email.">
        <div className="flex gap-2">
          <Input value={key} onChange={e => setKey(e.target.value)} placeholder="VII-XXXX-XXXX-XXXX" className="w-60 font-mono"
                 aria-label="License key" onKeyDown={e => e.key === 'Enter' && key.trim() && run('key')} />
          <Button variant="primary" icon={KeyRound} onClick={() => run('key')} disabled={!key.trim()} loading={busy === 'key'}>Activate</Button>
        </div>
      </Row>
      {tier === 'free' && (
        <Row label="Try Pro free for 14 days" description="No payment needed. Your plan returns to Free when the trial ends.">
          <div className="flex gap-2">
            <Input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" className="w-60"
                   aria-label="Email for trial" />
            <Button onClick={() => run('trial')} disabled={!email.includes('@')} loading={busy === 'trial'}>Start trial</Button>
          </div>
        </Row>
      )}
    </Section>
  );
}

export default function Plans() {
  const navigate = useNavigate();
  const { tier, isTrial, daysUntilExpiry, fetchStatus } = useLicense();
  const [catalog, setCatalog] = useState(null);
  const [period, setPeriod] = useState('lifetime');

  useEffect(() => {
    fetchStatus();
    api.get('/license/pricing').then(r => setCatalog(r.data)).catch(() => setCatalog({ error: true }));
  }, [fetchStatus]);

  const savings = useMemo(() => {
    if (!catalog?.pricing?.pro) return null;
    const p = catalog.pricing.pro;
    return Math.round((1 - p.yearly / (p.monthly * 12)) * 100);
  }, [catalog]);

  const choose = t => navigate('/purchase', { state: { plan: `${t}_${period}` } });

  return (
    <PageShell title="Plans" description="Seven runs entirely on your computer on every plan. Paid plans raise limits and add extras.">
      <div className="mx-auto max-w-[1080px] space-y-6 px-8 py-6">
        <CurrentPlan tier={tier} isTrial={isTrial} daysUntilExpiry={daysUntilExpiry} />

        {!catalog ? <LoadingRows rows={3} /> : catalog.error ? (
          <p className="text-[13px] text-s-text-3">Plan details couldn't be loaded. Check that Seven is running.</p>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <h2 className="text-[14px] font-semibold text-s-text">Choose a plan</h2>
              <div className="flex items-center gap-3">
                {period === 'yearly' && savings > 0 && <span className="text-[12px] text-s-green">Save {savings}% on yearly</span>}
                <Segmented value={period} options={PERIODS} onChange={setPeriod} />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              {TIERS.map(t => (
                <PlanCard key={t} tier={t} features={catalog.tiers[t]} period={period}
                          price={catalog.pricing[t]?.[period]} current={tier === t} onChoose={() => choose(t)} />
              ))}
            </div>

            <section className="overflow-hidden rounded-xl border border-s-border bg-s-surface shadow-[var(--s-shadow)]">
              <div className="px-5 pt-4 pb-3"><h2 className="text-[14px] font-semibold text-s-text">Compare plans</h2></div>
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-y border-s-border text-[12px] text-s-text-3">
                    <th className="px-5 py-2.5 text-left font-medium">Feature</th>
                    {TIERS.map(t => (
                      <th key={t} className={cx('w-40 px-5 py-2.5 text-center font-medium', tier === t && 'text-s-text')}>
                        {NAMES[t]}{tier === t ? ' (yours)' : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-s-border/70">
                  {ROWS.map(([label, get]) => (
                    <tr key={label}>
                      <td className="px-5 py-2.5 text-s-text-2">{label}</td>
                      {TIERS.map(t => (
                        <td key={t} className={cx('px-5 py-2.5 text-center tabular-nums text-s-text', tier === t && 'bg-s-card/60')}>
                          {show(get(catalog.tiers[t]))}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        )}

        <Activate tier={tier} />

        <div className="grid grid-cols-2 gap-4">
          <section className="rounded-xl border border-s-border bg-s-surface px-5 py-4">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-s-accent-h" />
              <h2 className="text-[14px] font-semibold text-s-text">On the roadmap</h2>
            </div>
            <p className="mt-1 text-[12px] text-s-text-3">Included with Ultimate when they ship.</p>
            <ul className="mt-3 space-y-2.5">
              {ROADMAP.map(([title, desc]) => (
                <li key={title}>
                  <div className="text-[13px] font-medium text-s-text">{title}</div>
                  <div className="text-[12px] text-s-text-3">{desc}</div>
                </li>
              ))}
            </ul>
          </section>
          <section className="flex flex-col rounded-xl border border-s-border bg-s-surface px-5 py-4">
            <div className="flex items-center gap-2">
              <Gift size={15} className="text-s-accent-h" />
              <h2 className="text-[14px] font-semibold text-s-text">Get a paid plan free</h2>
            </div>
            <p className="mt-1 flex-1 text-[13px] leading-relaxed text-s-text-3">
              Invite a friend. When they've used Seven for 7 hours, they get Pro and you get Ultimate, each free for a month.
            </p>
            <div className="mt-4">
              <Button onClick={() => navigate('/settings?section=account')}>Get your referral code</Button>
            </div>
          </section>
        </div>
      </div>
    </PageShell>
  );
}
