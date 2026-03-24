import { useEffect, useState } from 'react';
import useSchedules from '../stores/useSchedules';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

export default function Schedules() {
  const { schedules, loading, fetch, add, cancel } = useSchedules();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ type: 'reminder', message: '', time: '', duration: '' });

  useEffect(() => { fetch(); const i = setInterval(fetch, 15000); return () => clearInterval(i); }, []);

  const submit = async () => { const d = { type: form.type, message: form.message }; if (form.type === 'timer') d.duration = parseInt(form.duration || 0) * 60; else if (form.time) d.time = form.time; const r = await add(d); if (r.ok) { setShow(false); setForm({ type: 'reminder', message: '', time: '', duration: '' }); } };
  const active = schedules.filter(s => s.status === 'active');
  const fired = schedules.filter(s => s.status === 'fired').slice(-10);

  if (loading) return <Spinner t="Loading..." />;

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Schedules" sub={`${active.length} active`}
        right={<button onClick={() => setShow(!show)} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium">+ New</button>} />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {show && (
          <div className="bg-s-card border border-s-border rounded p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })} className="bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text"><option value="reminder">Reminder</option><option value="alarm">Alarm</option><option value="timer">Timer</option><option value="event">Event</option></select>
              {form.type === 'timer' ? <input type="number" value={form.duration} onChange={e => setForm({ ...form, duration: e.target.value })} placeholder="Minutes" className="bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4" />
              : <input value={form.time} onChange={e => setForm({ ...form, time: e.target.value })} placeholder="5pm, tomorrow, in 30 min" className="bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4" />}
            </div>
            <input value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} placeholder="Message..." className="w-full bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4" />
            <div className="flex justify-end gap-2"><button onClick={() => setShow(false)} className="text-[10px] text-s-text-4 px-2 py-1">Cancel</button><button onClick={submit} disabled={!form.message} className="px-3 py-1 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium disabled:opacity-40">Create</button></div>
          </div>
        )}

        <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">Active ({active.length})</div>
        {active.length === 0 ? <div className="bg-s-card border border-s-border rounded py-5 text-center text-[11px] text-s-text-4">No active schedules</div>
        : <div className="space-y-px">{active.map(s => (
          <div key={s.id} className="flex items-center gap-2 px-3 py-2 bg-s-card border border-s-border rounded hover:bg-s-card-h group">
            <span className="text-[9px] text-s-accent font-mono w-16 uppercase font-medium">{s.type}</span>
            <span className="text-[12px] text-s-text-2 flex-1 truncate">{s.message || '—'}</span>
            <span className="text-[9px] text-s-text-4 font-mono">{new Date(s.time).toLocaleString()}</span>
            {s.recur !== 'none' && <span className="text-[8px] text-s-purple bg-s-purple/8 px-1.5 py-0.5 rounded font-medium">{s.recur}</span>}
            <button onClick={() => cancel(s.id)} className="text-[9px] text-s-text-4 hover:text-s-red opacity-0 group-hover:opacity-100">cancel</button>
          </div>
        ))}</div>}

        {fired.length > 0 && <>
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mt-2">Fired</div>
          <div className="space-y-px">{fired.map(s => (
            <div key={s.id} className="flex items-center gap-2 px-3 py-1.5 text-[11px] text-s-text-4">
              <span className="w-1 h-1 rounded-full bg-s-green" /><span className="flex-1 truncate">{s.message || s.type}</span><span className="text-[9px] font-mono">{new Date(s.time).toLocaleString()}</span>
            </div>
          ))}</div>
        </>}
      </div>
    </div>
  );
}