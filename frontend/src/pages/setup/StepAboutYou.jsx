import { useState } from 'react';
import useSetup from '../../stores/useSetup';

export default function StepAboutYou() {
  const { data, setField, next, back, error, setError, clearError } = useSetup();
  const [showReferral, setShowReferral] = useState(false);

  const validate = () => {
    if (!data.name.trim()) { setError('Name is required.'); return false; }
    if (!data.email.trim() || !data.email.includes('@')) { setError('Valid email required.'); return false; }
    return true;
  };

  const firstName = data.name.trim().split(' ')[0];
  const initial = firstName?.charAt(0).toUpperCase() || '?';

  return (
    <div className="grid grid-cols-5 gap-10 max-w-4xl">
      <div className="col-span-2 space-y-4">
        <div className="text-[9px] text-white/40 tracking-[0.3em] font-semibold uppercase">Profile Preview</div>
        <div className="p-7 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-6">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="w-24 h-24 rounded-full bg-white/[0.05] border border-white/[0.1] flex items-center justify-center">
              <span className="text-4xl font-light text-white/80">{initial}</span>
            </div>
            <div className="space-y-1">
              <div className="text-[15px] font-medium text-white tracking-tight">{firstName || 'Your Name'}</div>
              <div className="text-[10px] text-white/40 font-mono">{data.email || 'your@email.com'}</div>
            </div>
          </div>
          <div className="w-full pt-4 border-t border-white/[0.06]">
            <div className="text-[9px] text-white/30 tracking-[0.2em] font-semibold mb-2">SYSTEM GREETING</div>
            <div className="text-[11px] text-white/60 italic">"Good morning, {firstName || 'friend'}."</div>
          </div>
        </div>
      </div>

      <div className="col-span-3 space-y-7">
        <div className="space-y-2">
          <div className="text-[10px] text-white/50 tracking-[0.3em] font-semibold uppercase">Step 2 of 6</div>
          <h2 className="text-[28px] font-bold text-white tracking-tight">Establish Identity</h2>
          <p className="text-[12px] text-white/40 font-light max-w-md">Your credentials secure your local license. Data is never shared.</p>
        </div>

        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-[10px] text-white/50 tracking-[0.2em] font-medium uppercase">Full Name</label>
            <input type="text" value={data.name} onChange={e => { setField('name', e.target.value); clearError(); }} autoFocus
                   placeholder="Enter your name" className="w-full px-4 py-3 bg-white/[0.03] border border-white/[0.1] rounded-lg text-white text-[13px] outline-none focus:border-white/40 transition-colors" />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] text-white/50 tracking-[0.2em] font-medium uppercase">Email Address</label>
            <input type="email" value={data.email} onChange={e => { setField('email', e.target.value); clearError(); }}
                   placeholder="Enter your email" className="w-full px-4 py-3 bg-white/[0.03] border border-white/[0.1] rounded-lg text-white text-[13px] outline-none focus:border-white/40 transition-colors" />
          </div>
          
          <button onClick={() => setShowReferral(!showReferral)} className="text-[10px] text-white/40 hover:text-white/80 transition-colors uppercase tracking-widest font-semibold pt-2">
            {showReferral ? '- Hide Referral Code' : '+ Add Referral Code'}
          </button>
          
          {showReferral && (
            <input type="text" value={data.referralCode || ''} onChange={e => setField('referralCode', e.target.value.toUpperCase())}
                   placeholder="REF-XXXXXXXX" className="w-full px-4 py-3 bg-white/[0.03] border border-white/[0.1] rounded-lg text-white font-mono text-[12px] outline-none focus:border-white/40 transition-colors" />
          )}
        </div>

        {error && <div className="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg text-[11px] text-red-400">{error}</div>}

        <div className="flex gap-3 pt-4 border-t border-white/[0.05]">
          <button onClick={back} className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05] transition-colors">Back</button>
          <button onClick={() => validate() && next()} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-colors">Continue</button>
        </div>
      </div>
    </div>
  );
}