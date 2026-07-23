import { useEffect, useRef } from 'react';
import { AlertTriangle, X } from 'lucide-react';

export default function ConfirmDialog({ open, title, message, confirmLabel = 'Delete', onConfirm, onCancel }) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => confirmRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center"
         onClick={onCancel}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Dialog */}
      <div className="relative w-[320px] bg-[#111114] border border-white/10 rounded-2xl
                      shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_24px_48px_rgba(0,0,0,0.6)]
                      animate-[dialogReveal_180ms_ease-out_forwards]"
           onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="flex items-start justify-between p-5 pb-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/8
                            flex items-center justify-center flex-shrink-0">
              <AlertTriangle size={14} className="text-white/50" />
            </div>
            <h3 className="text-[13px] font-semibold text-white/90 leading-tight">
              {title}
            </h3>
          </div>
          <button onClick={onCancel}
                  className="text-white/20 hover:text-white/50 transition-colors ml-2 mt-0.5">
            <X size={13} />
          </button>
        </div>

        {/* Message */}
        <p className="px-5 pb-5 text-[11px] text-white/45 leading-relaxed">
          {message}
        </p>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 px-5 pb-5">
          <button onClick={onCancel}
                  className="px-4 py-2 text-[10px] text-white/35 hover:text-white/65
                             transition-colors rounded-lg border border-transparent
                             hover:border-white/8 hover:bg-white/[0.03]">
            Cancel
          </button>
          <button ref={confirmRef} onClick={onConfirm}
                  className="px-4 py-2 text-[10px] font-semibold text-white/70
                             bg-white/[0.04] border border-white/10 rounded-lg
                             hover:bg-white/[0.07] hover:text-white/90
                             hover:border-white/15 transition-all">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}