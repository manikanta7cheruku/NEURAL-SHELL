import { useState } from 'react';
import { RotateCcw, Trash2, Layout } from 'lucide-react';

export default function WorkspaceCard({ workspace, onRestore, onDelete }) {
  const [restoring, setRestoring] = useState(false);
  const [hovered,   setHovered]   = useState(false);
  const apps = workspace.apps || [];

  const handleRestore = async () => {
    setRestoring(true);
    await onRestore(workspace.id);
    setTimeout(() => setRestoring(false), 3000);
  };

  return (
    <div className={`rounded-2xl border overflow-hidden transition-all duration-300
                     bg-white/[0.02] border-white/8 hover:border-white/12
                     ${restoring ? 'scale-[0.98]' : ''}`}
         onMouseEnter={() => setHovered(true)}
         onMouseLeave={() => setHovered(false)}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-[13px] font-semibold text-white/90 leading-tight">
              {workspace.name}
            </h3>
            {workspace.description && (
              <p className="text-[9px] text-white/35 mt-0.5">{workspace.description}</p>
            )}
          </div>
          <span className="text-[9px] text-white/40 bg-white/[0.03] border border-white/6
                           px-2 py-0.5 rounded-md font-mono flex items-center gap-1 flex-shrink-0">
            <Layout size={8} /> {apps.length}
          </span>
        </div>

        <div className="flex flex-wrap gap-1 mb-3 max-h-[80px] overflow-y-auto
                        scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
          {apps.map((app, i) => (
            <span key={i} className="text-[8px] text-white/35 bg-[#0a0a0c]
                                      border border-white/5 px-1.5 py-0.5 rounded">
              {app.name || app.type}
            </span>
          ))}
        </div>

        <div className="flex items-center justify-between pt-2.5 border-t border-white/5">
          <span className="text-[8px] text-white/25 flex items-center gap-0.5">
            <RotateCcw size={7} /> {workspace.use_count || 0} restores
          </span>
          <div className={`flex items-center gap-1 transition-opacity duration-200
                           ${hovered ? 'opacity-100' : 'opacity-0'}`}>
            <button onClick={handleRestore} disabled={restoring}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg
                               bg-s-accent/8 border border-s-accent/15
                               text-[8.5px] text-s-accent font-medium
                               hover:bg-s-accent/15 transition-all disabled:opacity-30">
              <RotateCcw size={9} />
              {restoring ? 'Opening...' : 'Restore'}
            </button>
            <button onClick={() => onDelete(workspace.id)}
                    className="p-1.5 rounded-lg text-white/25 hover:text-white/60
                               hover:bg-white/[0.04] transition-all">
              <Trash2 size={10} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}