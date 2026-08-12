import { useState } from 'react';
import useSetup from '../../stores/useSetup';

export default function StepAboutYou() {
  const { data, setField, next, back, error, setError, clearError } = useSetup();
  const [showReferral, setShowReferral] = useState(false);
  const [nameFocused,  setNameFocused]  = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);

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

  const firstName = data.name.trim().split(' ')[0];

  return (
    <div className="space-y-8 max-w-lg">

      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
          <span className="text-[9px] text-s-accent tracking-[0.25em] font-semibold">
            STEP 2 OF 6
          </span>
        </div>
        <h2 className="text-[28px] font-bold text-s-text tracking-tight leading-tight">
          {data.name.trim()
            ? `Nice to meet you, ${firstName}.`
            : 'Who are you?'}
        </h2>
        <p className="text-[12px] text-s-text-3 font-light leading-relaxed">
          Seven uses your name to personalize every interaction.
          Your email is used only for license activation and referral rewards.
        </p>
      </div>

      {/* Name field */}
      <div className="space-y-2">
        <label className="text-[10px] font-semibold text-s-text-3 tracking-[0.18em]">
          YOUR NAME
        </label>
        <div className={`relative rounded-xl border transition-all duration-200
                         ${nameFocused
                           ? 'border-s-accent bg-s-card shadow-[0_0_0_3px_rgba(99,102,241,0.08)]'
                           : 'border-s-border bg-s-card hover:border-s-border-l'}`}>
          <input
            type="text"
            value={data.name}
            onChange={e => { setField('name', e.target.value); clearError(); }}
            onFocus={() => setNameFocused(true)}
            onBlur={() => setNameFocused(false)}
            onKeyDown={e => e.key === 'Enter' && handleNext()}
            placeholder="Enter your full name"
            maxLength={48}
            autoFocus
            className="w-full px-4 py-4 bg-transparent text-s-text text-[14px]
                       placeholder:text-s-text-4 outline-none rounded-xl"
          />
        </div>
        {data.name.trim() && (
          <div className="flex items-center gap-2 pl-1">
            <div className="w-1 h-1 rounded-full bg-s-green" />
            <p className="text-[10px] text-s-text-4">
              Seven will call you{' '}
              <span className="text-s-text-3 font-medium">{firstName}</span>
            </p>
          </div>
        )}
      </div>

      {/* Email field */}
      <div className="space-y-2">
        <label className="text-[10px] font-semibold text-s-text-3 tracking-[0.18em]">
          EMAIL ADDRESS
        </label>
        <div className={`relative rounded-xl border transition-all duration-200
                         ${emailFocused
                           ? 'border-s-accent bg-s-card shadow-[0_0_0_3px_rgba(99,102,241,0.08)]'
                           : 'border-s-border bg-s-card hover:border-s-border-l'}`}>
          <input
            type="email"
            value={data.email}
            onChange={e => { setField('email', e.target.value); clearError(); }}
            onFocus={() => setEmailFocused(true)}
            onBlur={() => setEmailFocused(false)}
            onKeyDown={e => e.key === 'Enter' && handleNext()}
            placeholder="you@example.com"
            className="w-full px-4 py-4 bg-transparent text-s-text text-[14px]
                       placeholder:text-s-text-4 outline-none rounded-xl"
          />
        </div>
        <p className="text-[9.5px] text-s-text-4 pl-1 font-light">
          Used for license keys and referral rewards. Never shared.
        </p>
      </div>

      {/* Referral code */}
      <div className="space-y-3">
        <button
          onClick={() => setShowReferral(v => !v)}
          className="flex items-center gap-2 text-[10px] text-s-text-4
                     hover:text-s-text-3 transition-colors duration-150"
        >
          <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center
                           transition-all duration-150
                           ${showReferral
                             ? 'bg-s-accent border-s-accent'
                             : 'border-s-border hover:border-s-border-l'}`}>
            {showReferral && (
              <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                <path d="M1.5 4L3.5 6L6.5 2" stroke="white"
                      strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </div>
          I have a referral code
        </button>

        {showReferral && (
          <div className="space-y-1.5">
            <input
              type="text"
              value={data.referralCode}
              onChange={e => setField('referralCode', e.target.value.toUpperCase())}
              placeholder="REF-XXXXXXXX"
              maxLength={16}
              className="w-full px-4 py-3.5 rounded-xl bg-s-card border border-s-border
                         text-s-text text-sm placeholder:text-s-text-4
                         font-mono tracking-[0.15em]
                         hover:border-s-border-l focus:border-s-accent
                         transition-all duration-150"
            />
            <p className="text-[9px] text-s-text-4 pl-1 font-light">
              Your referrer earns a reward after you use Seven for 7 hours.
            </p>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl
                        bg-s-red/5 border border-s-red/15">
          <div className="w-1.5 h-1.5 rounded-full bg-s-red flex-shrink-0" />
          <p className="text-[11px] text-s-red">{error}</p>
        </div>
      )}

      {/* Navigation */}
      <div className="flex gap-3 pt-1">
        <button
          onClick={back}
          className="group px-5 py-3.5 rounded-xl text-sm text-s-text-3
                     border border-s-border hover:border-s-border-l hover:text-s-text
                     transition-all duration-150 flex items-center gap-2"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
               className="group-hover:-translate-x-0.5 transition-transform duration-200">
            <path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>
        <button
          onClick={handleNext}
          className="group flex-1 py-3.5 rounded-xl bg-s-accent hover:bg-s-accent-h
                     text-white text-sm font-semibold tracking-wide
                     transition-all duration-150 flex items-center justify-center gap-2"
        >
          Continue
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
               className="group-hover:translate-x-0.5 transition-transform duration-200">
            <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>

      {/* Privacy note at bottom */}
      <div className="flex items-start gap-2 pt-1 border-t border-s-border/50">
        <div className="w-3 h-3 rounded flex items-center justify-center flex-shrink-0 mt-0.5
                        border border-s-border">
          <svg width="6" height="6" viewBox="0 0 6 6" fill="none">
            <path d="M1 3L2.5 4.5L5 1.5" stroke="#6366f1"
                  strokeWidth="0.9" strokeLinecap="round"/>
          </svg>
        </div>
        <p className="text-[9.5px] text-s-text-4 font-light leading-relaxed">
          Name stored locally in config. Email used only for license and referrals.
          Nothing is sold or shared with third parties. Change anytime in Settings.
        </p>
      </div>
    </div>
  );
}