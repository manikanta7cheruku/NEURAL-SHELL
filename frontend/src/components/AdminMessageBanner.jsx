import { useEffect, useState } from 'react';
import api from '../api';

export default function AdminMessageBanner() {
  const [message, setMessage] = useState(null);
  const [dismissed, setDismissed] = useState(new Set());

  useEffect(() => {
    const check = async () => {
      try {
        const r = await api.get('/status');
        const msg = r.data?.admin_message;
        if (msg && msg.id && !dismissed.has(msg.id)) {
          setMessage(msg);
        } else if (!msg) {
          setMessage(null);
        }
      } catch {}
    };

    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, [dismissed]);

  if (!message) return null;

  const priorityStyles = {
    info:     'bg-blue-500/8 border-blue-500/20 text-blue-300',
    warning:  'bg-amber-500/8 border-amber-500/20 text-amber-300',
    critical: 'bg-red-500/8 border-red-500/20 text-red-300',
    success:  'bg-green-500/8 border-green-500/20 text-green-300',
  };

  const dotStyles = {
    info:     'bg-blue-400',
    warning:  'bg-amber-400 animate-pulse',
    critical: 'bg-red-400 animate-pulse',
    success:  'bg-green-400',
  };

  const style = priorityStyles[message.priority] || priorityStyles.info;
  const dotStyle = dotStyles[message.priority] || dotStyles.info;

  return (
    <div className={`flex-shrink-0 flex items-center justify-between px-5 py-2.5
                     border-b ${style}`}>
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotStyle}`} />
        <div className="min-w-0">
          <span className="text-[11px] font-semibold">{message.title}</span>
          {message.body && (
            <span className="text-[10px] opacity-80 ml-2">{message.body}</span>
          )}
        </div>
      </div>
      {message.priority !== 'critical' && (
        <button
          onClick={() => {
            setDismissed(prev => new Set([...prev, message.id]));
            setMessage(null);
          }}
          className="opacity-40 hover:opacity-80 transition-opacity p-1 flex-shrink-0 ml-3"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
        </button>
      )}
    </div>
  );
}