import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Share2, X, ChevronRight } from 'lucide-react';
import api from '../api';

export default function ReferralPrompt({ type, onDismiss }) {
  const navigate  = useNavigate();
  const [show,    setShow]    = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const lastShown = localStorage.getItem(`referral_prompt_${type}`);
    const cooldowns = {
      welcome:          7  * 24 * 3600 * 1000,
      plan_expired:     3  * 24 * 3600 * 1000,
      friend_completed: 0,
      dashboard_hint:   14 * 24 * 3600 * 1000,
    };
    const cooldown = cooldowns[type] ?? 7 * 24 * 3600 * 1000;
    if (lastShown && Date.now() - parseInt(lastShown) < cooldown) return;
    setShow(true);
    setTimeout(() => setVisible(true), 50);
  }, [type]);

  const dismiss = () => {
    setVisible(false);
    setTimeout(() => {
      localStorage.setItem(`referral_prompt_${type}`, Date.now().toString());
      setShow(false);
      if (onDismiss) onDismiss();
    }, 250);
  };

  const go = () => { dismiss(); navigate('/settings'); };

  if (!show) return null;

  const content = {
    welcome:          { title: 'Share Seven, Get Ultimate Free', msg: 'Share with a friend. When they use it for 7 hours you both get Ultimate free for one month.' },
    plan_expired:     { title: 'Your Premium Expired',           msg: 'Share Seven with a friend to unlock another free month of Ultimate.' },
    friend_completed: { title: 'Referral Complete',              msg: 'Your friend used Seven for 7 hours. Check your email for your Ultimate license.' },
    dashboard_hint:   { title: 'Enjoying Seven?',                msg: 'Share with friends to unlock Ultimate features free for both of you.' },
  };

  const c = content[type] || content.welcome;

  return (
    <div className={`bg-white/[0.015] border border-s-accent/12 rounded-2xl p-4
                     transition-all duration-250 ease-out overflow-hidden
                     ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-s-accent/8 border border-s-accent/15
                          flex items-center justify-center flex-shrink-0 mt-0.5">
            <Share2 size={13} className="text-s-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-white/80">{c.title}</p>
            <p className="text-[9px] text-white/35 mt-1 leading-relaxed">{c.msg}</p>
            <div className="flex items-center gap-2 mt-2.5">
              <button onClick={go}
                      className="flex items-center gap-1 px-3 py-1.5 bg-s-accent/8
                                 border border-s-accent/15 text-[9px] text-s-accent
                                 font-medium rounded-lg hover:bg-s-accent/15 transition-all">
                Get started <ChevronRight size={8} />
              </button>
              <button onClick={dismiss}
                      className="text-[8.5px] text-white/25 hover:text-white/50
                                 transition-colors px-1">
                Maybe later
              </button>
            </div>
          </div>
        </div>
        <button onClick={dismiss}
                className="text-white/20 hover:text-white/50 transition-colors flex-shrink-0">
          <X size={13} />
        </button>
      </div>
    </div>
  );
}