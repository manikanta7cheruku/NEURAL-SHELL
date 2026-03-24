import useStatus from '../stores/useStatus';

export default function StatusOrb() {
  const { getState } = useStatus();
  const state = getState();

  return (
    <div className="flex items-center gap-4">
      <div className="relative">
        {/* Outer glow ring */}
        <div
          className={`absolute inset-0 rounded-full ${state.animation}`}
          style={{ background: `radial-gradient(circle, ${state.color}30, transparent 70%)`, transform: 'scale(1.8)' }}
        />
        {/* Main orb */}
        <div
          className={`relative w-14 h-14 rounded-full ${state.animation} flex items-center justify-center`}
          style={{
            background: `radial-gradient(circle at 35% 35%, ${state.color}90, ${state.color}40)`,
            border: `2px solid ${state.color}60`,
          }}
        >
          {/* Inner highlight */}
          <div
            className="w-4 h-4 rounded-full"
            style={{
              background: `radial-gradient(circle at 40% 40%, white, ${state.color}80)`,
              opacity: 0.6,
            }}
          />
        </div>
      </div>
      <div>
        <div className="text-sm font-bold tracking-wider" style={{ color: state.color }}>
          {state.label}
        </div>
        <div className="text-[10px] text-seven-text-muted">Seven AI Engine</div>
      </div>
    </div>
  );
}