/**
 * Account: profile (name and email), current plan, and referrals.
 * Saving the profile also re-registers the device with Seven's server, as before.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Copy, Check, Share2 } from 'lucide-react';
import api from '../../api';
import useConfig from '../../stores/useConfig';
import useLicense from '../../stores/useLicense';
import { Section, Row, Body, Button, Input, Badge, Dialog } from '../../components/ui';
import { toast } from '../../lib/toast';

const DOWNLOAD_URL = 'https://github.com/manikanta7cheruku/seven-releases/releases/latest';
const PLAN_NAMES = { free: 'Free', pro: 'Pro', ultimate: 'Ultimate' };

function hours(h) {
  if (!h) return '0 min';
  const m = Math.round(h * 60);
  if (m < 60) return `${m} min`;
  return m % 60 ? `${Math.floor(m / 60)} hr ${m % 60} min` : `${Math.floor(m / 60)} hr`;
}

function Profile({ config }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(config.identity?.user_name || '');
  const [email, setEmail] = useState(config.email || '');
  const [saving, setSaving] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState(false);

  const reset = () => {
    setName(config.identity?.user_name || '');
    setEmail(config.email || '');
    setEditing(false);
  };

  const persist = async () => {
    setConfirmEmail(false);
    setSaving(true);
    try {
      await api.put('/config', { updates: { email: email.trim(), identity: { ...config.identity, user_name: name.trim() } } });
      try { await api.post('/email/save', { email: email.trim() }); } catch {}
      try {
        const device = await api.get('/usage/stats');
        await fetch('https://seven-server-u2rp.onrender.com/api/register', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_id: device.data?.device_id || '', name: name.trim(), email: email.trim(), country: null }),
        });
      } catch {}
      await useConfig.getState().fetch();
      setEditing(false);
      toast.success('Profile saved');
    } catch {
      toast.error('Could not save your profile', 'Check that Seven is running, then try again.');
    }
    setSaving(false);
  };

  const save = () => {
    if (!name.trim()) return;
    const licensed = config.license?.tier && config.license.tier !== 'free';
    if (licensed && email.trim() !== (config.email || '').trim()) setConfirmEmail(true);
    else persist();
  };

  return (
    <Section title="Profile" description="How Seven addresses you, and the email linked to your license."
             actions={editing
               ? <><Button variant="ghost" size="sm" onClick={reset} disabled={saving}>Cancel</Button>
                   <Button variant="primary" size="sm" onClick={save} loading={saving} disabled={!name.trim()}>Save</Button></>
               : <Button size="sm" onClick={() => setEditing(true)}>Edit</Button>}>
      <Row label="Name" htmlFor="profile-name">
        {editing
          ? <Input id="profile-name" value={name} onChange={e => setName(e.target.value)} className="w-64" autoFocus />
          : <span className="text-[13px] text-s-text">{config.identity?.user_name || 'Not set'}</span>}
      </Row>
      <Row label="Email" htmlFor="profile-email">
        {editing
          ? <Input id="profile-email" type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-64" placeholder="you@example.com" />
          : <span className="text-[13px] text-s-text">{config.email || 'Not set'}</span>}
      </Row>
      <Dialog open={confirmEmail} title="Change the email on your license?"
              description={`Your license stays active on this device. The email changes from ${config.email || 'none'} to ${email.trim()}.`}
              confirmLabel="Change email" onConfirm={persist} onCancel={() => setConfirmEmail(false)} />
    </Section>
  );
}

function Plan() {
  const navigate = useNavigate();
  const { tier, licenseKey, isTrial, daysUntilExpiry, fetchStatus } = useLicense();
  useEffect(() => { fetchStatus(); }, [fetchStatus]);
  const paid = tier === 'pro' || tier === 'ultimate';

  return (
    <Section title="Plan" actions={<Button size="sm" onClick={() => navigate('/plans')}>{paid ? 'Manage plan' : 'See plans'}</Button>}>
      <Row label="Current plan" description="Facts and conversation history are unlimited on every plan.">
        <div className="flex items-center gap-2">
          {isTrial && <Badge tone="warning">Trial</Badge>}
          <Badge tone={paid ? 'accent' : 'neutral'}>{PLAN_NAMES[tier] || 'Free'}</Badge>
        </div>
      </Row>
      {daysUntilExpiry != null && paid && (
        <Row label={isTrial ? 'Trial ends' : 'Renews or expires'}>
          <span className="text-[13px] text-s-text tabular-nums">in {daysUntilExpiry} day{daysUntilExpiry === 1 ? '' : 's'}</span>
        </Row>
      )}
      {paid && licenseKey && (
        <Row label="License key">
          <span className="font-mono text-[12px] text-s-text-2">{licenseKey.slice(0, 9)}{'•'.repeat(8)}</span>
        </Row>
      )}
    </Section>
  );
}

function Referrals() {
  const [stats, setStats] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/referral/stats');
        const s = r.data;
        if (!s.referral_code) {
          try { s.referral_code = (await api.post('/referral/create', {})).data.referral_code; } catch {}
        }
        setStats(s);
      } catch { setStats({}); }
    })();
  }, []);

  const code = stats?.referral_code;
  const message = `I use Seven, a private AI voice assistant that runs entirely on my PC. Nothing leaves the device.\n\n`
    + `Download: ${DOWNLOAD_URL}\n\nEnter my referral code during setup: ${code}\n\n`
    + 'Use Seven for 7 hours and you get Pro free for a month.';

  const copy = () => {
    navigator.clipboard.writeText(message);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  const share = async () => {
    if (navigator.share) {
      try { await navigator.share({ title: 'Seven', text: message, url: DOWNLOAD_URL }); return; } catch {}
    }
    copy();
  };
  const open = url => window.open(url, '_blank');

  return (
    <Section title="Referrals" description="When a friend you invite uses Seven for 7 hours, they get Pro and you get Ultimate, each free for one month.">
      {!stats ? (
        <Body className="text-[13px] text-s-text-3">Loading referral details</Body>
      ) : !code ? (
        <Body className="text-[13px] text-s-text-3">Add your email in Profile to get a referral code.</Body>
      ) : (
        <>
          <Row label="Your code" description="Copying includes a short message and the download link.">
            <div className="flex items-center gap-2">
              <span className="rounded-lg border border-s-border bg-s-bg px-3 h-8 inline-flex items-center font-mono text-[13px] tracking-[0.15em] text-s-text">
                {code}
              </span>
              <Button size="sm" icon={copied ? Check : Copy} onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
            </div>
          </Row>
          <Row label="Share">
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => open(`https://wa.me/?text=${encodeURIComponent(message)}`)}>WhatsApp</Button>
              <Button size="sm" onClick={() => open(`https://x.com/intent/tweet?text=${encodeURIComponent(`Seven is a private AI voice assistant that runs 100% on your PC. Use code ${code} during setup. ${DOWNLOAD_URL}`)}`)}>X</Button>
              <Button size="sm" icon={Share2} onClick={share}>More</Button>
            </div>
          </Row>
          <Row label="Progress">
            <div className="flex items-center gap-5 text-[13px] text-s-text-2">
              <span><span className="font-semibold text-s-text tabular-nums">{stats.completed_referrals ?? 0}</span> completed</span>
              <span><span className="font-semibold text-s-text tabular-nums">{stats.pending_referrals ?? 0}</span> in progress</span>
            </div>
          </Row>
          {stats.pending_details?.map((ref, i) => (
            <Body key={i}>
              <div className="flex items-center justify-between text-[12px]">
                <span className="truncate text-s-text-2">{ref.email}</span>
                <span className="tabular-nums text-s-text-3">{hours(ref.usage_hours)} of 7 hr</span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-s-card-h">
                <div className="h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${ref.progress_percent}%` }} />
              </div>
            </Body>
          ))}
        </>
      )}
    </Section>
  );
}

export default function AccountSection({ config }) {
  return (
    <>
      <Profile config={config} />
      <Plan />
      <Referrals />
    </>
  );
}
