import { useState } from 'react';
import useSetup from '../../stores/useSetup';

export default function StepAboutYou() {
  const { data, setField, next, back, error, setError, clearError } = useSetup();
  const [showReferral, setShowReferral] = useState(false);
  const [nameFocused, setNameFocused] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);

  const validate = () => {
    if (!data.name.trim()) { setError('Name is required.'); return false; }
    if (data.name.trim().length < 2) { setError('Name must be at least 2 characters.'); return false; }
    if (!data.email.trim()) { setError('Email is required.'); return false; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email.trim())) { setError('Enter a valid email address.'); return false; }
    return true;
  };

  const handleNext = () => { if (validate()) next(); };
  const firstName = data.name.trim().split(' ')[0];
  const initial = firstName?.charAt(0).toUpperCase() || '?';

  return (
    <div className="grid grid-cols-5 gap-10 max-w-5xl">
      <div className="col-span-2 space-y-4">
        <div className="text-[9px] text-white/40 tracking-[0.3em] font-semibold uppercase">Profile Preview</div>
        <div className="p-7 rounded-2xl bg-[#0e0e11] border border-white/[0.08] space-y-6">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="relative">
              <div className="w-28 h-28 rounded-full bg-white/[0.05] border border-white/[0.1] flex items-center justify-center shadow-lg">
                <span className="text-5xl font-light text-white/80">{initial}</span>
              </div>
            </div>
            <div className="space-y-1.5 pt-1">
              <div className="text-[17px] font-medium text-white tracking-tight">{firstName || 'Your Name'}</div>
              <div className="text-[10.5px] text-white/40 font-mono truncate max-w-full">{data.email || 'your@email.com'}</div>
            </div>
          </div>
          <div className="w-full pt-4 border-t border-white/[0.06]">
            <div className="text-[9px] text-white/30 tracking-[0.2em] font-semibold mb-2">SYSTEM GREETING</div>
            <div className="italic text-[11.5px] text-white/60 leading-relaxed">
              "{(() => {
                const hour = new Date().getHours();
                const greeting = hour < 5 ? 'Good evening' : hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : hour < 21 ? 'Good evening' : 'Good night';
                return `${greeting}, ${firstName || 'friend'}.`;
              })()}"
            </div>
          </div>
        </div>
      </div>

      <div className="col-span-3 space-y-7">
        <div className="space-y-3">
          <div className="text-[10px] text-white/40 tracking-[0.3em] font-semibold uppercase">Step 2 of 6</div>
          <h2 className="text-[32px] font-bold text-white tracking-tight leading-tight">Establish Identity</h2>
          <p className="text-[13px] text-white/40 font-light leading-relaxed max-w-md">
            Seven personalizes every interaction using your name. Your email secures license activation and referral rewards.
          </p>
        </div>

        <div className="space-y-2.5">
          <label className="text-[10px] font-semibold text-white/50 tracking-[0.2em] uppercase">Full Name</label>
          <div className={`relative rounded-xl border transition-all duration-300 ${nameFocused ? 'border-white/40 bg-white/[0.03]' : 'border-white/[0.08] bg-[#0e0e11] hover:border-white/[0.15]'}`}>
            <input type="text" value={data.name} onChange={e => { setField('name', e.target.value); clearError(); }} onFocus={() => setNameFocused(true)} onBlur={() => setNameFocused(false)} onKeyDown={e => e.key === 'Enter' && handleNext()} placeholder="Enter your full name" maxLength={48} autoFocus className="w-full px-5 py-4 bg-transparent text-white text-[14px] placeholder:text-white/25 outline-none font-light" />
          </div>
        </div>

        <div className="space-y-2.5">
          <label className="text-[10px] font-semibold text-white/50 tracking-[0.2em] uppercase">Email Address</label>
          <div className={`relative rounded-xl border transition-all duration-300 ${emailFocused ? 'border-white/40 bg-white/[0.03]' : 'border-white/[0.08] bg-[#0e0e11] hover:border-white/[0.15]'}`}>
            <input type="email" value={data.email} onChange={e => { setField('email', e.target.value); clearError(); }} onFocus={() => setEmailFocused(true)} onBlur={() => setEmailFocused(false)} onKeyDown={e => e.key === 'Enter' && handleNext()} placeholder="you@example.com" className="w-full px-5 py-4 bg-transparent text-white text-[14px] placeholder:text-white/25 outline-none font-light" />
          </div>
        </div>

        <div className="space-y-3">
          <button onClick={() => setShowReferral(v => !v)} className="flex items-center gap-2.5 text-[11px] text-white/45 hover:text-white transition-colors duration-300 group">
            <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all duration-300 ${showReferral ? 'bg-white border-white text-black' : 'border-white/20 group-hover:border-white/50'}`}>
              {showReferral && <svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1.5 4.5L3.5 6.5L7.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
            </div>
            I have a referral code
          </button>
          
          <div className={`grid transition-all duration-500 ease-in-out ${showReferral ? 'grid-rows-[1fr] opacity-100 mt-2' : 'grid-rows-[0fr] opacity-0 mt-0'}`}>
            <div className="overflow-hidden">
              <input type="text" value={data.referralCode || ''} onChange={e => setField('referralCode', e.target.value.toUpperCase())} placeholder="REF-XXXXXXXX" maxLength={16} className="w-full px-5 py-3.5 rounded-xl bg-[#0e0e11] border border-white/[0.08] text-white text-[13px] placeholder:text-white/25 font-mono tracking-[0.15em] outline-none focus:border-white/30 transition-all duration-300" />
              <p className="text-[9.5px] text-white/30 pl-1 font-light mt-2">Your referrer earns Ultimate for 1 month once you use Seven for 7 hours.</p>
            </div>
          </div>
        </div>

        {error && <div className="px-4 py-3.5 rounded-xl bg-white/[0.05] border border-white/20"><p className="text-[11.5px] text-white font-medium">{error}</p></div>}

        <div className="flex items-center gap-3 pt-4 border-t border-white/[0.05]">
          <button onClick={back} className="px-6 py-4 rounded-xl text-[13px] text-white/40 border border-white/[0.08] hover:border-white/[0.2] hover:text-white transition-all">Back</button>
          <button onClick={handleNext} className="flex-1 py-4 rounded-xl bg-white text-black text-[13px] font-semibold tracking-wide transition-all shadow-[0_10px_30px_-10px_rgba(255,255,255,0.2)] hover:-translate-y-0.5">Continue</button>
        </div>
      </div>
    </div>
  );
}