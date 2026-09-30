/**
 * TaskResultCard.jsx
 * 
 * Renders task action results inline in chat.
 * Matches Console.jsx design language.
 */

const PRIORITY_COLORS = {
  high:   { text: 'text-red-400/85',     border: 'border-red-400/20',     bg: 'bg-red-400/[0.04]' },
  medium: { text: 'text-amber-400/85',   border: 'border-amber-400/20',   bg: 'bg-amber-400/[0.04]' },
  low:    { text: 'text-emerald-400/85', border: 'border-emerald-400/20', bg: 'bg-emerald-400/[0.04]' },
};

function formatDue(iso) {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const target = new Date(d);
    target.setHours(0, 0, 0, 0);
    if (target.getTime() === today.getTime()) return 'today';
    if (target.getTime() === tomorrow.getTime()) return 'tomorrow';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}

export default function TaskResultCard({ data }) {
  if (!data) return null;
  const { action } = data;

  if (action === 'created' && data.task) {
    const t = data.task;
    const pri = (t.priority || 'medium').toLowerCase();
    const c = PRIORITY_COLORS[pri] || PRIORITY_COLORS.medium;
    const due = formatDue(t.due_date);
    return (
      <div className="mt-3 pt-3 border-t border-white/[0.05]">
        <div className="text-[8px] text-white/30 uppercase tracking-widest font-medium mb-1.5">
          Task added
        </div>
        <div className={`rounded-lg border px-2.5 py-2 ${c.border} ${c.bg}`}>
          <div className="flex items-start gap-2">
            <span className={`text-[10px] mt-0.5 ${c.text}`}>◇</span>
            <div className="flex-1 min-w-0">
              <div className="text-[10.5px] text-white/85 font-medium">{t.text}</div>
              <div className="flex items-center gap-1.5 mt-0.5 text-[7.5px] uppercase tracking-wider">
                <span className={c.text}>{pri}</span>
                {due && (
                  <>
                    <span className="text-white/30">·</span>
                    <span className="text-white/50">due {due}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (action === 'list' && data.tasks) {
    if (data.tasks.length === 0) {
      return (
        <div className="mt-3 pt-3 border-t border-white/[0.05]">
          <div className="text-[10px] text-white/40 italic">No pending tasks.</div>
        </div>
      );
    }
    return (
      <div className="mt-3 pt-3 border-t border-white/[0.05] space-y-1.5">
        <div className="text-[8px] text-white/30 uppercase tracking-widest font-medium mb-1">
          {data.tasks.length} pending task{data.tasks.length !== 1 ? 's' : ''}
        </div>
        {data.tasks.slice(0, 8).map((t, idx) => {
          const pri = (t.priority || 'medium').toLowerCase();
          const c = PRIORITY_COLORS[pri] || PRIORITY_COLORS.medium;
          const due = formatDue(t.due_date);
          return (
            <div key={t.id || idx} className={`rounded-lg border px-2.5 py-1.5 ${c.border} ${c.bg}`}>
              <div className="flex items-start gap-2">
                <span className="text-[8px] font-mono text-white/35 mt-0.5 w-3 shrink-0">{idx + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[10.5px] text-white/80">{t.text}</div>
                  {due && (
                    <div className="text-[7.5px] text-white/45 mt-0.5 uppercase tracking-wider">
                      due {due}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {data.tasks.length > 8 && (
          <div className="text-[8px] text-white/35 text-center pt-1">
            + {data.tasks.length - 8} more
          </div>
        )}
      </div>
    );
  }

  if (action === 'completed') {
    return (
      <div className="mt-3 pt-3 border-t border-white/[0.05]">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.04]">
          <span className="text-emerald-400/85 text-[11px]">✓</span>
          <span className="text-[10px] text-white/70">Task marked complete</span>
        </div>
      </div>
    );
  }

  if (action === 'deleted') {
    return (
      <div className="mt-3 pt-3 border-t border-white/[0.05]">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-white/[0.08] bg-white/[0.02]">
          <span className="text-white/55 text-[11px]">×</span>
          <span className="text-[10px] text-white/55">Task removed</span>
        </div>
      </div>
    );
  }

  return null;
}