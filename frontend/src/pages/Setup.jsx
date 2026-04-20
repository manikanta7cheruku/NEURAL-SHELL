import useSetup from '../stores/useSetup';
import StepWelcome from './setup/StepWelcome';
import StepAboutYou from './setup/StepAboutYou';
import StepPersonalize from './setup/StepPersonalize';
import StepModel from './setup/StepModel';
import StepDone from './setup/StepDone';

const STEPS = [StepWelcome, StepAboutYou, StepPersonalize, StepModel, StepDone];
const LABELS = ['Welcome', 'Identity', 'Personalize', 'Model', 'Launch'];

export default function Setup({ onComplete }) {
  const { step, total } = useSetup();
  const progress = ((step - 1) / (total - 1)) * 100;
  const StepComponent = STEPS[step - 1];

  return (
    <div className="h-screen w-screen bg-s-bg flex flex-col">

      {/* ── Top bar: draggable + progress ── */}
      <div className="flex-shrink-0">
        {/* Drag region */}
        <div
          className="h-8 flex items-center justify-between px-6"
          style={{ WebkitAppRegion: 'drag' }}
        >
          <span className="font-mono text-[11px] tracking-[0.3em] text-white/15 font-semibold">
            VII
          </span>
          <span
            className="text-[10px] text-white/15 tracking-[0.3em] font-mono"
            style={{ WebkitAppRegion: 'no-drag' }}
          >
            SETUP
          </span>
        </div>

        {/* Progress rail */}
        <div className="w-full h-[1px] bg-s-border">
          <div
            className="h-full bg-gradient-to-r from-s-accent to-s-accent-h transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Step indicators — desktop width */}
        <div className="flex items-center justify-center gap-8 py-4 px-6">
          {LABELS.map((label, i) => {
            const n = i + 1;
            const isActive = n === step;
            const isDone = n < step;
            return (
              <div key={label} className="flex items-center gap-2">
                {/* Step dot */}
                <div className={`relative flex items-center justify-center`}>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all duration-300 ${
                    isDone
                      ? 'bg-s-accent border-s-accent'
                      : isActive
                      ? 'border-s-accent bg-s-accent/10'
                      : 'border-s-border bg-transparent'
                  }`}>
                    {isDone ? (
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M2 5L4.5 7.5L8 3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    ) : (
                      <span className={`text-[9px] font-mono font-medium ${
                        isActive ? 'text-s-accent' : 'text-s-text-4'
                      }`}>{n}</span>
                    )}
                  </div>
                  {isActive && (
                    <div className="absolute inset-0 rounded-full bg-s-accent/20 animate-pulse" />
                  )}
                </div>
                <span className={`text-[11px] tracking-wide transition-colors duration-300 hidden sm:inline ${
                  isActive
                    ? 'text-s-text font-medium'
                    : isDone
                    ? 'text-s-accent/70'
                    : 'text-s-text-4'
                }`}>
                  {label}
                </span>
                {/* Connector line */}
                {i < LABELS.length - 1 && (
                  <div className={`w-12 h-[1px] ml-2 transition-colors duration-300 ${
                    isDone ? 'bg-s-accent/40' : 'bg-s-border'
                  }`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Step content — scrollable ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="min-h-full flex items-start justify-center px-8 py-6">
          <div className="w-full max-w-3xl fin" key={step}>
            <StepComponent onComplete={onComplete} />
          </div>
        </div>
      </div>
    </div>
  );
}