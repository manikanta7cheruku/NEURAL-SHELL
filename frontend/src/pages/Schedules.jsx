/**
 * Schedules: reminders, alarms, timers and events on a day-grouped timeline.
 * They fire whether or not the app is open. Seven can list and create them
 * too: "what are my reminders", "remind me to drink water at 5pm".
 */
/* SEVEN_DOC {"purpose": "Reminders, alarms, timers and events, grouped by day. They fire even when the app is closed",
              "keywords": ["schedules", "reminders", "alarms", "timers", "events", "repeat", "recurring"],
              "controls": [
                {"label": "New schedule", "description": "Create a reminder, alarm, timer or event. Type a time like 5pm, tomorrow 9am or in 30 min."},
                {"label": "Repeat", "description": "Make a schedule repeat every day, on weekdays, or on one day each week."},
                {"label": "Cancel a schedule", "description": "Hover it and press the trash icon."}
              ]} */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, Calendar, Timer, Plus, Pencil, Trash2, AlarmClock, Repeat, CheckCircle2, CalendarClock } from 'lucide-react';
import api from '../api';
import useSchedules from '../stores/useSchedules';
import { PageShell, Button, Input, Segmented, Dialog, EmptyState, LoadingRows } from '../components/ui';
import { cx } from '../lib/cx';
import { toast } from '../lib/toast';

const TYPES = {
  reminder: { label: 'Reminder', icon: Bell },
  alarm: { label: 'Alarm', icon: AlarmClock },
  timer: { label: 'Timer', icon: Timer },
  event: { label: 'Event', icon: Calendar },
};
const REPEAT = [
  ['none', 'Once'], ['daily', 'Every day'], ['weekdays', 'Weekdays'], ['weekly_0', 'Mon'], ['weekly_1', 'Tue'],
  ['weekly_2', 'Wed'], ['weekly_3', 'Thu'], ['weekly_4', 'Fri'], ['weekly_5', 'Sat'], ['weekly_6', 'Sun'],
];
const repeatLabel = r => {
  if (!r || r === 'none') return null;
  if (r === 'daily') return 'Every day';
  if (r === 'weekdays') return 'Weekdays';
  const day = REPEAT.find(([k]) => k === r)?.[1];
  return day ? `Every ${day}` : 'Repeats';
};

function relative(iso) {
  const diff = new Date(iso) - new Date();
  const abs = Math.abs(diff);
  const m = Math.round(abs / 60000), h = Math.floor(abs / 3600000), d = Math.floor(abs / 86400000);
  const span = d >= 1 ? `${d}d` : h >= 1 ? `${h}h ${Math.floor((abs % 3600000) / 60000)}m` : `${m}m`;
  return diff >= 0 ? `in ${span}` : `${span} ago`;
}

function dayKey(iso) {
  const d = new Date(iso); d.setHours(0, 0, 0, 0);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = Math.round((d - today) / 86400000);
  if (diff < 0) return 'Overdue';
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Tomorrow';
  return new Date(iso).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
}

function ScheduleForm({ value, onChange }) {
  const set = (k, v) => onChange({ ...value, [k]: v });
  return (
    <div className="space-y-3.5">
      <div>
        <div className="mb-1.5 text-[11.5px] font-medium text-s-text-2">Type</div>
        <Segmented value={value.type} onChange={v => set('type', v)}
                   options={Object.entries(TYPES).map(([k, t]) => ({ value: k, label: t.label }))} />
      </div>
      <div>
        <label htmlFor="sch-msg" className="mb-1.5 block text-[11.5px] font-medium text-s-text-2">Message</label>
        <Input id="sch-msg" autoFocus value={value.message} onChange={e => set('message', e.target.value)} className="w-full"
               placeholder="What should Seven remind you about?" />
      </div>
      {value.type === 'timer' ? (
        <div>
          <label htmlFor="sch-dur" className="mb-1.5 block text-[11.5px] font-medium text-s-text-2">Duration in minutes</label>
          <Input id="sch-dur" type="number" min="1" value={value.duration} onChange={e => set('duration', e.target.value)} className="w-32" placeholder="30" />
        </div>
      ) : (
        <>
          <div>
            <label htmlFor="sch-when" className="mb-1.5 block text-[11.5px] font-medium text-s-text-2">When</label>
            <Input id="sch-when" value={value.time} onChange={e => set('time', e.target.value)} className="w-full"
                   placeholder="5pm, tomorrow 9am, in 30 min, 25 Dec" />
            <div className="mt-1.5 flex flex-wrap gap-1">
              {['in 15 min', 'in 1 hour', 'tomorrow 9am', 'tomorrow 5pm', 'monday 9am'].map(ex => (
                <button key={ex} onClick={() => set('time', ex)}
                        className={cx('h-6 rounded-md px-2 text-[11.5px] transition-colors',
                                      value.time === ex ? 'bg-s-accent text-s-on-accent' : 'bg-s-card text-s-text-3 hover:bg-s-card-h hover:text-s-text-2')}>{ex}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-1.5 text-[11.5px] font-medium text-s-text-2">Repeat</div>
            <div className="flex flex-wrap gap-1">
              {REPEAT.map(([k, label]) => (
                <button key={k} onClick={() => set('recur', k)}
                        className={cx('h-6 rounded-md px-2 text-[11.5px] transition-colors',
                                      value.recur === k ? 'bg-s-accent text-s-on-accent' : 'bg-s-card text-s-text-3 hover:bg-s-card-h hover:text-s-text-2')}>{label}</button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ s, onEdit, onCancel }) {
  const t = TYPES[s.type] || TYPES.reminder;
  const overdue = new Date(s.time) < new Date();
  const when = new Date(s.time);
  const rep = repeatLabel(s.recur);
  return (
    <li className="group/row flex items-center gap-4 rounded-lg border border-transparent px-3 py-2 transition-colors duration-200 hover:border-s-border hover:bg-s-surface">
      <div className="w-16 shrink-0 text-right">
        <div className={cx('text-[13px] font-medium tabular-nums', overdue ? 'text-s-red' : 'text-s-text')}>
          {when.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
        </div>
        <div className="text-[11px] text-s-text-4">{relative(s.time)}</div>
      </div>
      <span className="h-8 w-px shrink-0 bg-s-border" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] text-s-text">{s.message || t.label}</div>
        <div className="mt-0.5 flex items-center gap-3 text-[11.5px] text-s-text-3">
          <span className="flex items-center gap-1"><t.icon size={12} />{t.label}</span>
          {rep && <span className="flex items-center gap-1"><Repeat size={12} />{rep}</span>}
          {overdue && <span className="text-s-red">Missed</span>}
        </div>
      </div>
      <div className="flex items-center opacity-0 transition-opacity duration-200 group-hover/row:opacity-100 focus-within:opacity-100">
        <button aria-label="Edit" onClick={() => onEdit(s)} className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-4 hover:bg-s-card hover:text-s-text-2"><Pencil size={13} /></button>
        <button aria-label="Cancel schedule" onClick={() => onCancel(s)} className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-4 hover:bg-s-card hover:text-s-red"><Trash2 size={13} /></button>
      </div>
    </li>
  );
}

const BLANK = { type: 'reminder', message: '', time: '', duration: '', recur: 'none' };

export default function Schedules() {
  const { schedules, loading, fetch, add, cancel } = useSchedules();
  const [limit, setLimit] = useState(-1);
  const [form, setForm] = useState(null);           // { mode: 'new'|'edit', id, value }
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState(null);

  useEffect(() => {
    fetch();
    api.get('/license/features').then(r => setLimit(r.data?.schedules ?? -1)).catch(() => {});
    const i = setInterval(fetch, 15000);
    return () => clearInterval(i);
  }, [fetch]);

  const active = useMemo(() => schedules.filter(s => s.status === 'active')
    .sort((a, b) => new Date(a.time) - new Date(b.time)), [schedules]);
  const fired = useMemo(() => schedules.filter(s => s.status === 'fired').slice(-8).reverse(), [schedules]);
  const atLimit = limit !== -1 && active.length >= limit;

  const groups = useMemo(() => {
    const out = [];
    active.forEach(s => {
      const k = dayKey(s.time);
      if (!out.length || out[out.length - 1][0] !== k) out.push([k, []]);
      out[out.length - 1][1].push(s);
    });
    return out;
  }, [active]);

  const open = useCallback((mode, s) => {
    setError('');
    if (mode === 'new' && atLimit) {
      toast.error('Schedule limit reached', `Your plan allows ${limit} active schedules. Upgrade on the Plans page for more.`);
      return;
    }
    setForm({ mode, id: s?.id, value: s ? { ...BLANK, type: s.type, message: s.message || '', time: s.time?.slice(0, 16).replace('T', ' ') || '', recur: s.recur || 'none' } : BLANK });
  }, [atLimit, limit]);

  const save = async () => {
    const v = form.value;
    if (!v.message.trim()) return setError('Enter a message.');
    if (v.type === 'timer' && !(parseInt(v.duration) > 0)) return setError('Enter a duration in minutes.');
    if (v.type !== 'timer' && !v.time.trim()) return setError('Enter a time.');
    const data = { type: v.type, message: v.message.trim() };
    if (v.type === 'timer') data.duration = parseInt(v.duration) * 60; else data.time = v.time.trim();
    if (v.type !== 'timer' && v.recur !== 'none') data.recur = v.recur;
    setSaving(true);
    if (form.mode === 'edit') await cancel(form.id);
    const r = await add(data);
    setSaving(false);
    if (!r.ok) return setError(r.msg || "Couldn't understand that time. Try 5pm or tomorrow 9am.");
    toast.success(form.mode === 'edit' ? 'Schedule updated' : 'Schedule created', r.msg);
    setForm(null);
  };

  const summary = `${active.length} active${limit !== -1 ? ` of ${limit} on your plan` : ''}`;

  return (
    <PageShell title="Schedules" description={summary}
               actions={<Button variant="primary" icon={Plus} onClick={() => open('new')}>New schedule</Button>}>
      <div className="mx-auto max-w-[820px] space-y-5 px-6 py-5">
        {loading ? <LoadingRows rows={4} /> : active.length === 0 ? (
          <EmptyState icon={CalendarClock} title="Nothing scheduled"
                      description='Create a reminder, alarm, timer or event, or ask Seven: "remind me to stretch at 4pm".'
                      action={<Button variant="primary" icon={Plus} onClick={() => open('new')}>New schedule</Button>} />
        ) : (
          <div className="page-in space-y-4">
            {groups.map(([label, items]) => (
              <section key={label}>
                <h2 className={cx('mb-1 px-3 text-[11.5px] font-medium', label === 'Overdue' ? 'text-s-red' : 'text-s-text-3')}>{label}</h2>
                <ul className="space-y-0.5">{items.map(s => <Row key={s.id} s={s} onEdit={x => open('edit', x)} onCancel={setCancelling} />)}</ul>
              </section>
            ))}
          </div>
        )}

        {fired.length > 0 && (
          <section>
            <h2 className="mb-1 px-3 text-[11.5px] font-medium text-s-text-3">Recently fired</h2>
            <ul className="space-y-0.5">
              {fired.map(s => (
                <li key={s.id} className="flex h-8 items-center gap-3 px-3 text-[12.5px]">
                  <CheckCircle2 size={14} className="shrink-0 text-s-text-4" />
                  <span className="flex-1 truncate text-s-text-3">{s.message || TYPES[s.type]?.label}</span>
                  <span className="text-[11.5px] tabular-nums text-s-text-4">{relative(s.time)}</span>
                </li>))}
            </ul>
          </section>
        )}
      </div>

      <Dialog open={!!form} title={form?.mode === 'edit' ? 'Edit schedule' : 'New schedule'}
              confirmLabel={form?.mode === 'edit' ? 'Save' : 'Create'} busy={saving}
              onConfirm={save} onCancel={() => setForm(null)}>
        {form && <ScheduleForm value={form.value} onChange={value => setForm(f => ({ ...f, value }))} />}
        {error && <p className="mt-3 text-[12px] text-s-red">{error}</p>}
      </Dialog>

      <Dialog open={!!cancelling} tone="danger" title="Remove this schedule?" confirmLabel="Remove"
              description={cancelling ? `"${cancelling.message || 'This schedule'}" won't fire.` : ''}
              onConfirm={async () => { await cancel(cancelling.id); setCancelling(null); toast.success('Schedule removed'); }}
              onCancel={() => setCancelling(null)} />
    </PageShell>
  );
}
