import { useState } from 'react';
import useSetup from '../../stores/useSetup';

export default function StepAboutYou() {
  const { data, setField, next, back, error, setError, clearError } = useSetup();
  const [showReferral, setShowReferral] = useState(false);

  const validate = () => {
    if (!data.name.trim()) {
      setError('Name is required.');
      return false;
    }
    if (data.name.trim().length < 2) {
      setError('Name must be at least 2 characters.');
      return false;
    }
    if (!data.email.trim()) {
      setError('Email is required.');
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email.trim())) {
      setError('Enter a valid email address.');
      return false;
    }
    return true;
  };

  const handleNext = () => {
    if (validate()) next();
  };

  return (
    <div className="grid grid-cols-5 gap-10">

      {/* ── Left: Info panel ── */}
      <div className="col-span-2 space-y-6 pt-2">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
            <span className="text-[10px] text-s-accent tracking-[0.2em] font-medium">STEP 2</span>
          </div>
          <h2 className="text-2xl font-bold text-s-text tracking-tight leading-tight">
            Identity
          </h2>
          <p className="text-xs text-s-text-3 font-light leading-relaxed">
            Seven uses your name to personalize every interaction.
            Your email is stored locally and used only for license
            management and referral rewards.
          </p>
        </div>

        {/* Privacy assurance */}
        <div className="space-y-3 pt-4 border-t border-s-border">
          <p className="text-[10px] text-s-text-4 tracking-[0.15em] font-medium">DATA HANDLING</p>
          {[
            'Name is stored in local config only',
            'Email is used for license keys & referrals',
            'Nothing is sold or shared with third parties',
            'You can change these anytime in Settings',
          ].map(line => (
            <div key={line} className="flex items-start gap-2.5">
              <div className="w-3 h-3 rounded flex items-center justify-center flex-shrink-0 mt-0.5 border border-s-border">
                <svg width="6" height="6" viewBox="0 0 6 6" fill="none">
                  <path d="M1 3L2.5 4.5L5 1.5" stroke="#6366f1" strokeWidth="0.8" strokeLinecap="round"/>
                </svg>
              </div>
              <span className="text-[11px] text-s-text-3 font-light">{line}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right: Form ── */}
      <div className="col-span-3 space-y-6">

        {/* Name field */}
        <div className="space-y-2">
          <label className="flex items-baseline justify-between">
            <span className="text-[11px] font-medium text-s-text-2 tracking-[0.15em]">FULL NAME</span>
            <span className="text-[10px] text-s-red/70">Required</span>
          </label>
          <input
            type="text"
            value={data.name}
            onChange={e => { setField('name', e.target.value); clearError(); }}
            placeholder="Enter your name"
            maxLength={48}
            autoFocus
            onKeyDown={e => e.key === 'Enter' && handleNext()}
            className="w-full px-4 py-3.5 rounded-xl bg-s-card border border-s-border text-s-text text-sm placeholder:text-s-text-4 hover:border-s-border-l focus:border-s-accent transition-all duration-150"
          />
          {data.name.trim() && (
            <div className="flex items-center gap-2 pl-1">
              <div className="w-1 h-1 rounded-full bg-s-green" />
              <p className="text-[11px] text-s-text-4">
                Seven will address you as <span className="text-s-text-3 font-medium">{data.name.trim()}</span>
              </p>
            </div>
          )}
        </div>

        {/* Email field */}
        <div className="space-y-2">
          <label className="flex items-baseline justify-between">
            <span className="text-[11px] font-medium text-s-text-2 tracking-[0.15em]">EMAIL ADDRESS</span>
            <span className="text-[10px] text-s-red/70">Required</span>
          </label>
          <input
            type="email"
            value={data.email}
            onChange={e => { setField('email', e.target.value); clearError(); }}
            placeholder="you@example.com"
            onKeyDown={e => e.key === 'Enter' && handleNext()}
            className="w-full px-4 py-3.5 rounded-xl bg-s-card border border-s-border text-s-text text-sm placeholder:text-s-text-4 hover:border-s-border-l focus:border-s-accent transition-all duration-150"
          />
        </div>

        {/* Referral */}
        <div className="space-y-3">
          <button
            onClick={() => setShowReferral(v => !v)}
            className="flex items-center gap-2.5 text-[11px] text-s-text-4 hover:text-s-text-3 transition-colors duration-150 tracking-wide group"
          >
            <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all duration-150 ${
              showReferral ? 'bg-s-accent border-s-accent' : 'border-s-border group-hover:border-s-border-l'
            }`}>
              {showReferral && (
                <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                  <path d="M1.5 4L3.5 6L6.5 2" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </div>
            I have a referral code
          </button>

          {showReferral && (
            <div className="fin space-y-2">
              <input
                type="text"
                value={data.referralCode}
                onChange={e => setField('referralCode', e.target.value.toUpperCase())}
                placeholder="REF-XXXXXXXX"
                maxLength={16}
                className="w-full px-4 py-3.5 rounded-xl bg-s-card border border-s-border text-s-text text-sm placeholder:text-s-text-4 font-mono tracking-[0.15em] hover:border-s-border-l focus:border-s-accent transition-all duration-150"
              />
              <p className="text-[10px] text-s-text-4 pl-1">
                Your referrer will be rewarded once you reach 7 hours of active use.
              </p>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-s-red/5 border border-s-red/15">
            <div className="w-1.5 h-1.5 rounded-full bg-s-red flex-shrink-0" />
            <p className="text-xs text-s-red">{error}</p>
          </div>
        )}

        {/* Nav */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={back}
            className="group px-5 py-3 rounded-xl text-sm text-s-text-3 border border-s-border hover:border-s-border-l hover:text-s-text transition-all duration-150 flex items-center gap-2"
          >
            <svg
              width="14" height="14" viewBox="0 0 14 14" fill="none"
              className="group-hover:-translate-x-0.5 transition-transform duration-200"
            >
              <path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Back
          </button>
          <button
            onClick={handleNext}
            className="group flex-1 py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white text-sm font-medium tracking-wide transition-all duration-150 flex items-center justify-center gap-2"
          >
            Continue
            <svg
              width="14" height="14" viewBox="0 0 14 14" fill="none"
              className="group-hover:translate-x-0.5 transition-transform duration-200"
            >
              <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}