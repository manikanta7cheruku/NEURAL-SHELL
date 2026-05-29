import { useEffect, useState } from 'react';
import useSchedules from '../stores/useSchedules';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

const TYPE_COLORS = {
  reminder: 'text-s-accent bg-s-accent/8',
  alarm:    'text-s-yellow bg-s-yellow/8',
  timer:    'text-s-green bg-s-green/8',
  event:    'text-purple-400 bg-purple-400/8',
};

function formatTime(isoStr) {
  try {
    return new Date(isoStr).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return isoStr; }
}

export default function Schedules() {
  const { schedules, loading, fetch, add, cancel } = useSchedules();

  const [show,     setShow]     = useState(false);
  const [form,     setForm]     = useState({ type: 'reminder', message: '', time: '', duration: '' });
  const [editing,  setEditing]  = useState(null);   // schedule being edited
  const [editForm, setEditForm] = useState({});
  const [saving,   setSaving]   = useState(false);
  const [tier,     setTier]     = useState('free');
  const [limitMsg, setLimitMsg] = useState('');
  const [createError,  setCreateError]  = useState('');

  const SCHEDULE_LIMITS = { free: 7, pro: 17, ultimate: Infinity };

  useEffect(() => {
    fetch();
    api.get('/license/status').then(r => setTier(r.data.tier || 'free')).catch(() => {});
    const i = setInterval(fetch, 15000);
    return () => clearInterval(i);
  }, []);

  const active = schedules.filter(s => s.status === 'active');
  const fired  = schedules.filter(s => s.status === 'fired').slice(-10);
  const limit  = SCHEDULE_LIMITS[tier] ?? 7;
  const atLimit = active.length >= limit;

    const submit = async () => {
    setCreateError('');
    if (atLimit) {
      setLimitMsg(
        tier === 'free'
          ? `Free plan limit is ${limit} schedules. Upgrade to Pro for 17.`
          : `Pro plan limit is ${limit} schedules. Upgrade to Ultimate for unlimited.`
      );
      return;
    }
    if (!form.message.trim()) {
      setCreateError('Please enter a message.');
      return;
    }
    if (form.type !== 'timer' && !form.time.trim()) {
      setCreateError('Please enter a time — e.g. 5pm, tomorrow, in 30 min.');
      return;
    }
    if (form.type === 'timer' && !form.duration) {
      setCreateError('Please enter duration in minutes.');
      return;
    }
    setSaving(true);
    const d = { type: form.type, message: form.message.trim() };
    if (form.type === 'timer') d.duration = parseInt(form.duration || 0) * 60;
    else d.time = form.time.trim();
    const r = await add(d);
    setSaving(false);
    if (r.ok) {
      setShow(false);
      setForm({ type: 'reminder', message: '', time: '', duration: '' });
      setLimitMsg('');
      setCreateError('');
    } else {
      setCreateError(r.msg || 'Failed to create. Check time format and try again.');
    }
  };

  const startEdit = (s) => {
    setEditing(s.id);
    setEditForm({
      message: s.message || '',
      time:    s.time ? s.time.slice(0, 16) : '',   // datetime-local format
      type:    s.type
    });
  };

  const saveEdit = async () => {
    if (!editing) return;
    try {
      // Cancel old → create new with updated values
      await cancel(editing);
      const d = { type: editForm.type, message: editForm.message };
      if (editForm.type === 'timer') d.duration = 0;
      else if (editForm.time) d.time = editForm.time;
      await add(d);
      setEditing(null);
      fetch();
    } catch {}
  };

  if (loading) return <Spinner t="Loading schedules..." />;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        title="Schedules"
        sub={`${active.length}${limit === Infinity ? '' : `/${limit}`} active`}
        right={
          <button
            onClick={() => { setShow(p => !p); setLimitMsg(''); }}
            className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
          >
            + New
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">

        {/* PLAN LIMIT BANNER */}
        {limitMsg && (
          <div className="bg-s-yellow/8 border border-s-yellow/30 rounded p-3 flex items-start justify-between">
            <div>
              <div className="text-[11px] text-s-yellow font-medium">Schedule Limit Reached</div>
              <div className="text-[10px] text-s-text-3 mt-0.5">{limitMsg}</div>
            </div>
            <button onClick={() => setLimitMsg('')} className="text-s-text-4 hover:text-s-text-2 text-[11px]">✕</button>
          </div>
        )}

        {/* USAGE BAR */}
        {limit !== Infinity && (
          <div className="bg-s-card border border-s-border rounded px-3 py-2 flex items-center gap-3">
            <div className="flex-1 h-1 bg-s-border rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  atLimit ? 'bg-s-red' : active.length / limit > 0.7 ? 'bg-s-yellow' : 'bg-s-accent'
                }`}
                style={{ width: `${Math.min(100, (active.length / limit) * 100)}%` }}
              />
            </div>
            <span className={`text-[9px] font-mono shrink-0 ${atLimit ? 'text-s-red' : 'text-s-text-4'}`}>
              {active.length}/{limit}
            </span>
          </div>
        )}

        {/* ADD FORM */}
        {show && (
          <div className="bg-s-card border border-s-border rounded p-3 space-y-2">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-1">
              New Schedule
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={form.type}
                onChange={e => setForm({ ...form, type: e.target.value })}
                className="bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text"
              >
                <option value="reminder">Reminder</option>
                <option value="alarm">Alarm</option>
                <option value="timer">Timer</option>
                <option value="event">Event</option>
              </select>

              {form.type === 'timer'
                ? <input
                    type="number"
                    value={form.duration}
                    onChange={e => setForm({ ...form, duration: e.target.value })}
                    placeholder="Minutes"
                    className="bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4"
                  />
                : <input
                    value={form.time}
                    onChange={e => setForm({ ...form, time: e.target.value })}
                    placeholder="5pm, tomorrow, in 30 min"
                    className="bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4"
                  />
              }
            </div>
            <input
              value={form.message}
              onChange={e => setForm({ ...form, message: e.target.value })}
              onKeyDown={e => e.key === 'Enter' && submit()}
              placeholder="Message..."
              className="w-full bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4"
            />
            {createError && (
              <div className="text-[10px] text-s-red bg-s-red/8 border border-s-red/20 rounded px-2 py-1.5">
                {createError}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShow(false); setLimitMsg(''); setCreateError(''); }}
                className="text-[10px] text-s-text-4 px-2 py-1 hover:text-s-text-3"
              >
                Cancel
              </button>
              <button
                onClick={submit}
                disabled={saving}
                className="px-3 py-1 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium disabled:opacity-40 hover:bg-s-accent/20"
              >
                {saving ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        )}

        {/* ACTIVE SCHEDULES */}
        <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
          Active ({active.length})
        </div>

        {active.length === 0
          ? <div className="bg-s-card border border-s-border rounded py-6 text-center text-[11px] text-s-text-4">
              No active schedules — click + New to add one
            </div>
          : <div className="space-y-1">
              {active.map(s => (
                <div key={s.id}>
                  {/* VIEW ROW */}
                  {editing !== s.id && (
                    <div className="flex items-center gap-2 px-3 py-2.5 bg-s-card border border-s-border rounded hover:bg-s-card-h group transition-colors">
                      <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded uppercase ${TYPE_COLORS[s.type] || 'text-s-text-4 bg-s-border'}`}>
                        {s.type}
                      </span>
                      <span className="text-[11px] text-s-text-2 flex-1 truncate">{s.message || '—'}</span>
                      <span className="text-[9px] text-s-text-4 font-mono shrink-0">{formatTime(s.time)}</span>
                      {s.recur && s.recur !== 'none' && (
                        <span className="text-[8px] text-purple-400 bg-purple-400/8 px-1.5 py-0.5 rounded font-medium">
                          {s.recur.replace('weekly_', 'wk ')}
                        </span>
                      )}
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => startEdit(s)}
                          className="text-[9px] text-s-text-4 hover:text-s-accent px-1.5 py-0.5 rounded hover:bg-s-accent/8"
                        >
                          edit
                        </button>
                        <button
                          onClick={() => cancel(s.id)}
                          className="text-[9px] text-s-text-4 hover:text-s-red px-1.5 py-0.5 rounded hover:bg-s-red/8"
                        >
                          cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {/* EDIT ROW */}
                  {editing === s.id && (
                    <div className="bg-s-card border border-s-accent/30 rounded p-3 space-y-2">
                      <div className="text-[9px] text-s-accent uppercase tracking-wider font-medium mb-1">
                        Editing Schedule
                      </div>
                      <input
                        value={editForm.message}
                        onChange={e => setEditForm(p => ({ ...p, message: e.target.value }))}
                        placeholder="Message..."
                        className="w-full bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4"
                      />
                      {s.type !== 'timer' && (
                        <input
                          value={editForm.time}
                          onChange={e => setEditForm(p => ({ ...p, time: e.target.value }))}
                          placeholder="5pm, tomorrow, in 30 min"
                          className="w-full bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4"
                        />
                      )}
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => setEditing(null)}
                          className="text-[10px] text-s-text-4 px-2 py-1"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={saveEdit}
                          className="px-3 py-1 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium"
                        >
                          Save
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
        }

        {/* FIRED HISTORY */}
        {fired.length > 0 && (
          <>
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mt-2">
              Recent ({fired.length})
            </div>
            <div className="space-y-px">
              {fired.map(s => (
                <div key={s.id} className="flex items-center gap-2 px-3 py-1.5 text-[11px] text-s-text-4 bg-s-card border border-s-border/50 rounded">
                  <span className="w-1.5 h-1.5 rounded-full bg-s-green shrink-0" />
                  <span className="flex-1 truncate">{s.message || s.type}</span>
                  <span className="text-[9px] font-mono">{formatTime(s.time)}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}