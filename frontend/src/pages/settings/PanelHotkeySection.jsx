import { useState, useEffect, useRef } from 'react';
import { Keyboard, X, Check } from 'lucide-react';
import api from '../../api';

export default function PanelHotkeySection() {
  const [currentHotkey, setCurrentHotkey] = useState('Alt+Shift+T');
  const [recording, setRecording] = useState(false);
  const [pending, setPending] = useState('');
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    fetchHotkey();
  }, []);

  const fetchHotkey = async () => {
    try {
      const r = await api.get('/panel/get-hotkey');
      setCurrentHotkey(r.data?.hotkey || 'Alt+Shift+T');
    } catch {}
  };

  const handleKeyDown = (e) => {
    if (!recording) return;
    e.preventDefault();
    e.stopPropagation();

    if (e.key === 'Escape') {
      setRecording(false);
      setPending('');
      return;
    }

    const parts = [];
    if (e.ctrlKey)  parts.push('ctrl');
    if (e.shiftKey) parts.push('shift');
    if (e.altKey)   parts.push('alt');
    if (e.metaKey)  parts.push('win');

    const key = e.key.toLowerCase();
    if (!['control', 'shift', 'alt', 'meta'].includes(key)) {
      parts.push(key === ' ' ? 'space' : key);
      setPending(parts.join('+'));
      setRecording(false);
    }
  };

  const saveHotkey = async () => {
    if (!pending) return;
    setSaving(true);
    setStatus(null);
    try {
      const r = await api.post('/panel/set-hotkey', { hotkey: pending });
      if (r.data?.success) {
        setCurrentHotkey(r.data.hotkey);
        setPending('');
        setStatus({ ok: true, msg: 'Hotkey updated' });
        setTimeout(() => setStatus(null), 2500);
      } else {
        setStatus({ ok: false, msg: 'Update failed' });
      }
    } catch (e) {
      setStatus({ ok: false, msg: e?.response?.data?.detail || 'Failed to update' });
    }
    setSaving(false);
  };

  const cancel = () => {
    setPending('');
    setRecording(false);
    setStatus(null);
  };

  const formatDisplay = (hk) => {
    return hk
      .split('+')
      .map(p => p.charAt(0).toUpperCase() + p.slice(1))
      .join(' + ');
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[12px] font-semibold text-white/85 flex items-center gap-2">
            <Keyboard size={13} className="text-white/50" />
            Panel Hotkey
          </h3>
          <p className="text-[10px] text-white/45 mt-0.5">
            Global shortcut to open the floating task panel from anywhere.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div
          ref={inputRef}
          tabIndex={0}
          onClick={() => { setRecording(true); inputRef.current?.focus(); }}
          onKeyDown={handleKeyDown}
          onBlur={() => setTimeout(() => setRecording(false), 150)}
          className={`flex-1 px-3 py-2.5 rounded-lg border cursor-pointer
                      text-[11px] font-medium transition-all outline-none
            ${recording
              ? 'bg-s-accent/8 border-s-accent/25 text-s-accent'
              : pending
                ? 'bg-white/[0.04] border-white/12 text-white/85'
                : 'bg-white/[0.02] border-white/8 text-white/70 hover:border-white/12'}`}
        >
          {recording
            ? 'Press key combination...'
            : pending
              ? `New: ${formatDisplay(pending)}`
              : formatDisplay(currentHotkey)}
        </div>

        {pending && !saving && (
          <>
            <button
              onClick={saveHotkey}
              className="w-9 h-9 rounded-lg flex items-center justify-center
                         bg-s-accent/10 border border-s-accent/20 text-s-accent
                         hover:bg-s-accent/18 transition-all"
              title="Save"
            >
              <Check size={13} />
            </button>
            <button
              onClick={cancel}
              className="w-9 h-9 rounded-lg flex items-center justify-center
                         bg-white/[0.03] border border-white/8 text-white/40
                         hover:text-white/70 hover:bg-white/[0.06] transition-all"
              title="Cancel"
            >
              <X size={13} />
            </button>
          </>
        )}

        {saving && (
          <div className="w-9 h-9 flex items-center justify-center">
            <div className="w-4 h-4 border-2 border-white/10 border-t-s-accent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {status && (
        <div className={`text-[10px] px-3 py-2 rounded-lg
          ${status.ok
            ? 'bg-green-500/8 border border-green-500/15 text-green-300'
            : 'bg-red-500/8 border border-red-500/15 text-red-300'}`}>
          {status.msg}
        </div>
      )}

      <p className="text-[9px] text-white/30 leading-relaxed">
        Click the box, press your combination, then click the check mark.
        The panel host reloads automatically — no restart needed.
      </p>
    </div>
  );
}