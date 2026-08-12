import { useEffect, useState } from 'react';
import useSetup from '../stores/useSetup';
import StepWelcome     from './setup/StepWelcome';
import StepAboutYou    from './setup/StepAboutYou';
import StepPersonalize from './setup/StepPersonalize';
import StepEnvironment from './setup/StepEnvironment';
import StepModel       from './setup/StepModel';
import StepDone        from './setup/StepDone';

const STEPS  = [StepWelcome, StepAboutYou, StepPersonalize, StepEnvironment, StepModel, StepDone];
const LABELS = ['Welcome', 'Identity', 'Voice', 'Environment', 'Model', 'Launch'];

function WindowControls() {
  const minimize = () => window.electronAPI?.minimize?.();
  const close    = () => window.electronAPI?.closeWindow?.();

  return (
    <div className="flex items-center gap-1.5" style={{ WebkitAppRegion: 'no-drag' }}>
      <button
        onClick={minimize}
        className="w-3 h-3 rounded-full bg-white/[0.08] hover:bg-white/20
                   transition-colors duration-150 flex items-center justify-center group"
        title="Minimize"
      >
        <div className="w-1.5 h-px bg-white/0 group-hover:bg-white/60
                        transition-colors duration-150 rounded-full" />
      </button>
      <button
        onClick={close}
        className="w-3 h-3 rounded-full bg-white/[0.08] hover:bg-red-500/70
                   transition-colors duration-150"
        title="Close"
      />
    </div>
  );
}

export default function Setup({ onComplete }) {
  const { step, total } = useSetup();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, []);

  const progress      = ((step - 1) / (total - 1)) * 100;
  const StepComponent = STEPS[step - 1];

  return (
    <div className="h-screen w-screen bg-s-bg flex flex-col overflow-hidden">

      {/* Title bar with drag region and window controls */}
      <div
        className="flex-shrink-0 flex items-center justify-between px-5 h-9
                   border-b border-white/[0.04]"
        style={{ WebkitAppRegion: 'drag' }}
      >
        <span className="text-[10px] font-mono text-white/15 tracking-[0.3em] font-semibold">
          SEVEN SETUP
        </span>
        <WindowControls />
      </div>

      {/* Progress rail */}
      <div className="flex-shrink-0 w-full h-px bg-s-border">
        <div
          className="h-full bg-s-accent transition-all duration-700 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Step indicators */}
      <div className="flex-shrink-0 flex items-center justify-center gap-3 py-4 px-6
                      border-b border-white/[0.03]">
        {LABELS.map((label, i) => {
          const n        = i + 1;
          const isActive = n === step;
          const isDone   = n < step;

          return (
            <div key={label} className="flex items-center gap-2">
              <div className="relative flex items-center justify-center">
                <div className={`w-5 h-5 rounded-full border flex items-center
                                justify-center transition-all duration-300
                                ${isDone
                                  ? 'bg-s-accent border-s-accent'
                                  : isActive
                                  ? 'border-s-accent bg-s-accent/10'
                                  : 'border-white/[0.08] bg-transparent'}`}>
                  {isDone ? (
                    <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                      <path d="M1.5 4.5L3.5 6.5L7.5 2.5" stroke="white"
                            strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  ) : (
                    <span className={`text-[8px] font-mono font-semibold
                                     ${isActive ? 'text-s-accent' : 'text-white/20'}`}>
                      {n}
                    </span>
                  )}
                </div>
                {isActive && (
                  <div className="absolute inset-0 rounded-full bg-s-accent/15
                                  animate-pulse" />
                )}
              </div>

              <span className={`text-[9px] tracking-wide transition-colors duration-300
                               hidden sm:inline
                               ${isActive
                                 ? 'text-white/70 font-medium'
                                 : isDone
                                 ? 'text-s-accent/60'
                                 : 'text-white/20'}`}>
                {label}
              </span>

              {i < LABELS.length - 1 && (
                <div className={`w-5 h-px ml-1 transition-colors duration-300
                                ${isDone ? 'bg-s-accent/30' : 'bg-white/[0.06]'}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <div className="flex-1 overflow-y-auto
                      scrollbar-thin scrollbar-thumb-white/[0.06]
                      scrollbar-track-transparent">
        <div className="min-h-full flex items-start justify-center px-8 py-8">
          <div
            className="w-full max-w-2xl animate-[fadeSlideIn_280ms_ease-out]"
            key={step}
          >
            <StepComponent onComplete={onComplete} />
          </div>
        </div>
      </div>
    </div>
  );
}