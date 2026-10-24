/**
 * System: live hardware readings (the same ones Seven uses to answer "what CPU
 * do I have"), the ambient panel, the task panel shortcut and installation repair.
 */
import { useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import api from '../../api';
import { Section, Row, Body, Segmented, Button, Badge, Dialog, Skeleton } from '../../components/ui';
import { cx } from '../../lib/cx';
import { applyTheme, getThemePref } from '../../lib/theme';
import { toast } from '../../lib/toast';
import { saveConfig, saveWith } from './save';

const gb = v => (v == null ? '' : v >= 1000 ? `${(v / 1024).toFixed(1)} TB` : `${v} GB`);

function uptime(s) {
  if (!s) return '';
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return [d && `${d}d`, h && `${h}h`, `${m}m`].filter(Boolean).join(' ');
}

function Meter({ percent }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-s-card-h">
      <div className="h-full rounded-full bg-s-text-3 transition-[width] duration-500"
           style={{ width: `${Math.min(100, percent || 0)}%` }} />
    </div>
  );
}

function Usage({ percent, warn = 90 }) {
  return (
    <div className="mt-1.5 flex items-center gap-2">
      <Meter percent={percent} />
      <span className="w-9 text-right text-[12px] tabular-nums text-s-text-3">{percent}%</span>
      {percent >= warn && <span className="shrink-0 text-[11px] font-medium text-s-text-2">Nearly full</span>}
    </div>
  );
}

function Hardware() {
  const [info, setInfo] = useState(null);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);

  const read = () => api.get('/system/info').then(r => setInfo(r.data)).catch(() => setInfo({}));
  const refresh = () => { setLoading(true); read().finally(() => setLoading(false)); };
  useEffect(() => {
    read();
    api.get('/hardware').then(r => setModels(r.data?.installed_models || [])).catch(() => {});
  }, []);

  const gpu = info?.gpu;
  return (
    <Section title="This computer" description="Live hardware readings. Seven uses the same values when you ask about your PC."
             actions={<Button size="sm" variant="ghost" icon={RefreshCw} onClick={refresh} loading={loading}>Refresh</Button>}>
      {!info ? <Body><Skeleton className="h-32 w-full" /></Body> : (
        <>
          <Row label="Operating system"><span className="text-[13px] text-s-text-2">{info.os}</span></Row>
          <Row label="Processor" description={info.cores ? `${info.cores} cores, ${info.threads} threads` : undefined}>
            <div className="w-64 text-right">
              <div className="truncate text-[13px] text-s-text-2" title={info.cpu}>{info.cpu}</div>
              {info.cpu_load != null && <Usage percent={info.cpu_load} warn={101} />}
            </div>
          </Row>
          {info.ram && (
            <Row label="Memory" description={`${gb(info.ram.free_gb)} available`}>
              <div className="w-64 text-right">
                <div className="text-[13px] text-s-text-2 tabular-nums">{gb(info.ram.used_gb)} of {gb(info.ram.total_gb)}</div>
                <Usage percent={info.ram.percent} />
              </div>
            </Row>
          )}
          <Row label="Graphics" description={gpu ? `${gpu.vram_gb} GB VRAM, ${gpu.temp_c}°C` : undefined}>
            <div className="w-64 text-right">
              <div className="truncate text-[13px] text-s-text-2">{gpu?.name || (info.gpus || []).join(', ') || 'No dedicated graphics card'}</div>
              {gpu && <Usage percent={gpu.load} warn={101} />}
            </div>
          </Row>
          {(info.disks || []).map(d => (
            <Row key={d.drive} label={`Drive ${d.drive}`} description={`${gb(d.free_gb)} free`}>
              <div className="w-64 text-right">
                <div className="text-[13px] text-s-text-2 tabular-nums">{gb(d.total_gb - d.free_gb)} of {gb(d.total_gb)} used</div>
                <Usage percent={d.percent} />
              </div>
            </Row>
          ))}
          {info.uptime_s != null && <Row label="Running for"><span className="text-[13px] text-s-text-2 tabular-nums">{uptime(info.uptime_s)}</span></Row>}
          {models.length > 0 && (
            <Row label="Installed models" stacked>
              <div className="flex flex-wrap gap-1.5">{models.map(m => <Badge key={m}>{m}</Badge>)}</div>
            </Row>
          )}
        </>
      )}
    </Section>
  );
}

const OPACITY = [{ value: 0.4, label: 'Light' }, { value: 0.65, label: 'Balanced' }, { value: 0.85, label: 'Solid' }];

function AmbientPanel({ config }) {
  const current = config.ambient_panel?.opacity ?? 0.65;
  const nearest = OPACITY.reduce((a, b) => (Math.abs(b.value - current) < Math.abs(a.value - current) ? b : a)).value;
  const change = async value => {
    await saveConfig({ ambient_panel: { opacity: value } });
    try { await api.post('/config/ambient-opacity', { opacity: value }); }
    catch {
      try { localStorage.setItem('seven_panel_opacity', String(value)); localStorage.setItem('seven_panel_opacity_ts', String(Date.now())); } catch {}
    }
  };
  return (
    <Section title="Floating panel" description="The panel that appears next to the Seven orb.">
      <Row label="Background" description="How much of your desktop shows through. Applies immediately.">
        <div className="flex items-center gap-3">
          <div className="h-8 w-14 rounded-md border border-s-border-l" style={{ background: `rgba(9,9,11,${nearest})`,
               backgroundImage: 'linear-gradient(45deg,var(--color-s-border-l) 25%,transparent 25%,transparent 75%,var(--color-s-border-l) 75%),linear-gradient(45deg,var(--color-s-border-l) 25%,transparent 25%,transparent 75%,var(--color-s-border-l) 75%)',
               backgroundSize: '8px 8px', backgroundPosition: '0 0,4px 4px', backgroundBlendMode: 'multiply' }} />
          <Segmented value={nearest} options={OPACITY} onChange={change} />
        </div>
      </Row>
    </Section>
  );
}

const pretty = hk => hk.split('+').map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' + ');

function PanelShortcut() {
  const [hotkey, setHotkey] = useState('alt+shift+t');
  const [recording, setRecording] = useState(false);
  const [pending, setPending] = useState('');
  const boxRef = useRef(null);

  useEffect(() => { api.get('/panel/get-hotkey').then(r => setHotkey(r.data?.hotkey || 'alt+shift+t')).catch(() => {}); }, []);

  const onKey = e => {
    if (!recording) return;
    e.preventDefault();
    if (e.key === 'Escape') { setRecording(false); setPending(''); return; }
    const parts = [];
    if (e.ctrlKey) parts.push('ctrl');
    if (e.shiftKey) parts.push('shift');
    if (e.altKey) parts.push('alt');
    if (e.metaKey) parts.push('win');
    const key = e.key.toLowerCase();
    if (!['control', 'shift', 'alt', 'meta'].includes(key)) {
      parts.push(key === ' ' ? 'space' : key);
      setPending(parts.join('+'));
      setRecording(false);
    }
  };

  const save = async () => {
    const r = await saveWith(() => api.post('/panel/set-hotkey', { hotkey: pending }));
    if (r?.data?.success) { setHotkey(r.data.hotkey); setPending(''); toast.success('Shortcut updated'); }
  };

  return (
    <Section title="Task panel shortcut" description="Opens the floating task panel from anywhere in Windows.">
      <Row label="Shortcut" description={recording ? 'Press the new key combination. Esc cancels.' : 'Click the box, then press a new combination.'}>
        <div className="flex items-center gap-2">
          <button ref={boxRef} onClick={() => { setRecording(true); setPending(''); }} onKeyDown={onKey}
                  onBlur={() => setRecording(false)}
                  className={cx('h-8 min-w-[150px] rounded-lg border px-3 text-[13px] font-medium transition-colors',
                                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/40',
                                recording ? 'border-s-accent bg-s-accent/10 text-s-accent-h' : 'border-s-border bg-s-bg text-s-text hover:border-s-border-l')}>
            {recording ? 'Press keys' : pretty(pending || hotkey)}
          </button>
          {pending && <><Button size="sm" variant="primary" onClick={save}>Save</Button><Button size="sm" variant="ghost" onClick={() => setPending('')}>Cancel</Button></>}
        </div>
      </Row>
    </Section>
  );
}

function Repair() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const repair = async () => {
    setBusy(true);
    try {
      await api.put('/config', { updates: { setup_complete: false } });
      await api.post('/bootstrap/restart', {});
    } catch {
      toast.error('Could not start the repair', 'Restart Seven and try again.');
      setBusy(false);
    }
  };
  return (
    <Section title="Repair installation">
      <Row label="Reinstall missing components" description="Runs setup again to fix the AI engine, models or dependencies. Your memory, tasks, schedules and triggers are kept.">
        <Button onClick={() => setOpen(true)}>Repair</Button>
      </Row>
      <Dialog open={open} title="Repair Seven?" busy={busy} confirmLabel="Restart and repair"
              description="Seven restarts and opens setup. Your data is not touched."
              onConfirm={repair} onCancel={() => setOpen(false)} />
    </Section>
  );
}

// Preview colours are fixed per tile so each one shows its own theme.
const THEMES = [
  { value: 'dark', label: 'Dark', bg: '#0d0e10', side: '#121316', line: '#26272d', text: '#34363d', accent: '#3cc8b4' },
  { value: 'light', label: 'Light', bg: '#f6f5f2', side: '#ffffff', line: '#e3e0d9', text: '#d2cec5', accent: '#0f8a7b' },
  { value: 'system', label: 'Match Windows', split: true },
];

function ThemePreview({ t }) {
  const pane = (c, clip) => (
    <div className="absolute inset-0 flex" style={{ background: c.bg, clipPath: clip }}>
      <div className="h-full w-[28%] border-r" style={{ background: c.side, borderColor: c.line }}>
        <div className="m-2 h-1.5 w-8 rounded-full" style={{ background: c.accent }} />
        {[0, 1, 2].map(i => <div key={i} className="mx-2 mt-1.5 h-1 rounded-full" style={{ background: c.text, width: `${70 - i * 12}%` }} />)}
      </div>
      <div className="flex-1 p-2">
        <div className="h-1.5 w-1/2 rounded-full" style={{ background: c.text }} />
        <div className="mt-2 h-7 rounded border" style={{ background: c.side, borderColor: c.line }} />
        <div className="mt-1.5 h-1 w-2/3 rounded-full" style={{ background: c.text }} />
      </div>
    </div>
  );
  return (
    <div className="relative h-[84px] overflow-hidden rounded-md border border-s-border">
      {t.split ? <>{pane(THEMES[1])}{pane(THEMES[0], 'polygon(0 0, 50% 0, 50% 100%, 0 100%)')}</> : pane(t)}
    </div>
  );
}

function Appearance() {
  const [pref, setPref] = useState(getThemePref);
  const choose = value => {
    setPref(value);
    applyTheme(value);
    saveConfig({ appearance: { theme: value } });
  };
  return (
    <Section title="Appearance" description="Choose how Seven looks. Match Windows follows your Windows light or dark setting.">
      <Body>
        <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-3">
          {THEMES.map(t => {
            const on = pref === t.value;
            return (
              <button key={t.value} role="radio" aria-checked={on} onClick={() => choose(t.value)}
                      className={cx('rounded-lg border p-2 text-left transition-colors',
                                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60',
                                    on ? 'border-s-accent ring-1 ring-s-accent' : 'border-s-border hover:border-s-border-l')}>
                <ThemePreview t={t} />
                <div className="mt-2 flex items-center gap-2 px-0.5">
                  <span className={cx('flex h-3.5 w-3.5 items-center justify-center rounded-full border',
                                      on ? 'border-s-accent bg-s-accent' : 'border-s-border-l')}>
                    {on && <span className="h-1.5 w-1.5 rounded-full bg-s-on-accent" />}
                  </span>
                  <span className="text-[13px] font-medium text-s-text">{t.label}</span>
                </div>
              </button>
            );
          })}
        </div>
      </Body>
    </Section>
  );
}

export default function SystemSection({ config }) {
  return (
    <>
      <Hardware />
      <AmbientPanel config={config} />
      <PanelShortcut />
      <Repair />
      <Appearance />
    </>
  );
}
