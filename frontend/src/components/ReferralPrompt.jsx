import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

export default function ReferralPrompt({ type, onDismiss }) {
  const navigate = useNavigate();
  const [show, setShow] = useState(false);
  const [referralStats, setReferralStats] = useState(null);

  useEffect(() => {
    checkIfShouldShow();
  }, [type]);

  const checkIfShouldShow = async () => {
    // Check localStorage to avoid annoying user
    const lastShown = localStorage.getItem(`referral_prompt_${type}`);
    const now = Date.now();
    
    // Different cooldowns for different prompt types
    const cooldowns = {
      'welcome': 7 * 24 * 60 * 60 * 1000,      // 7 days
      'plan_expired': 3 * 24 * 60 * 60 * 1000, // 3 days
      'friend_completed': 0,                    // Always show (important!)
      'dashboard_hint': 14 * 24 * 60 * 60 * 1000, // 14 days
    };
    
    const cooldown = cooldowns[type] || (7 * 24 * 60 * 60 * 1000);
    
    if (lastShown && (now - parseInt(lastShown)) < cooldown) {
      return; // Don't show yet
    }
    
    // Fetch referral stats
    try {
      const r = await api.get('/referral/stats');
      setReferralStats(r.data);
    } catch {
      // No stats yet
    }
    
    setShow(true);
  };

  const dismiss = () => {
    localStorage.setItem(`referral_prompt_${type}`, Date.now().toString());
    setShow(false);
    if (onDismiss) onDismiss();
  };

  const goToSettings = () => {
    dismiss();
    navigate('/settings');
  };

  if (!show) return null;

  // Different content for different prompt types
  const prompts = {
    welcome: {
      icon: '🎁',
      title: 'Share Seven, Get Premium Free',
      message: 'Share Seven with a friend. When they use it for 7 hours, you both get premium access free for a month!',
      button: 'Learn More',
    },
    plan_expired: {
      icon: '⏰',
      title: 'Your Premium Expired',
      message: 'Share Seven with a friend to get another free month of Ultimate! They get Pro free too.',
      button: 'Share Now',
    },
    friend_completed: {
      icon: '🎉',
      title: 'Congratulations!',
      message: `Your friend used Seven for 7 hours! Check your email for your free Ultimate license key.`,
      button: 'View Details',
    },
    dashboard_hint: {
      icon: '💡',
      title: 'Enjoying Seven?',
      message: 'Share with friends to unlock Ultimate features free. Your friend gets Pro free too!',
      button: 'Start Sharing',
    },
  };

  const prompt = prompts[type] || prompts.welcome;

  return (
    <div className="bg-gradient-to-r from-s-accent/10 to-s-accent/5 border border-s-accent/30 rounded p-3 mb-3">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <span className="text-2xl">{prompt.icon}</span>
          <div>
            <div className="text-[12px] font-medium text-s-text">{prompt.title}</div>
            <p className="text-[10px] text-s-text-3 mt-0.5">{prompt.message}</p>
          </div>
        </div>
        <button 
          onClick={dismiss} 
          className="text-s-text-4 hover:text-s-text-3 text-sm"
        >
          ✕
        </button>
      </div>
      <div className="flex gap-2 mt-3 ml-9">
        <button 
          onClick={goToSettings}
          className="px-3 py-1.5 bg-s-accent text-white rounded text-[10px] font-medium hover:bg-s-accent/90"
        >
          {prompt.button}
        </button>
        <button 
          onClick={dismiss}
          className="px-3 py-1.5 text-s-text-4 hover:text-s-text-3 text-[10px]"
        >
          Maybe Later
        </button>
      </div>
    </div>
  );
}