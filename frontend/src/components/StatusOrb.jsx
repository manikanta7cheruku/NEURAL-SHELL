import useStatus from '../stores/useStatus';
import ConversationPanel from './ConversationPanel';

/**
 * StatusOrb — the always-visible Seven indicator.
 * 
 * States:
 *   Idle      → dim grey, slow breathing pulse
 *   Listening → green, soft glow
 *   Thinking  → purple, faster pulse
 *   Speaking  → accent blue, active glow
 * 
 * ConversationPanel sits BELOW the orb.
 * It shows user speech + Seven reply with auto-fade.
 * No slide animation — text simply appears cleanly.
 */
export default function StatusOrb() {
  const { listening, thinking, speaking, connected } = useStatus();

  // Derive visual state from boolean flags
  const orbState = (() => {
    if (thinking)  return { color: '#a855f7', label: 'Thinking',  ring: 'shadow-purple-500/40',  anim: 'animate-pulse' };
    if (speaking)  return { color: '#6366f1', label: 'Speaking',  ring: 'shadow-indigo-500/40',  anim: 'animate-pulse' };
    if (listening) return { color: '#22c55e', label: 'Listening', ring: 'shadow-green-500/30',   anim: '' };
    return           { color: '#3f3f46',  label: 'Idle',      ring: 'shadow-zinc-700/20',    anim: '' };
  })();

  if (!connected) {
    return (
      <div className="flex flex-col items-center gap-3 w-full">
        <div className="relative">
          <div className="w-12 h-12 rounded-full bg-zinc-800 border border-zinc-700/50 flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-zinc-600" />
          </div>
        </div>
        <p className="text-[9px] text-zinc-600 tracking-widest uppercase">Connecting</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 w-full">

      {/* ── The Orb ── */}
      <div className="relative flex items-center justify-center">

        {/* Outer ambient glow — appears on active states */}
        {(listening || thinking || speaking) && (
          <div
            className="absolute rounded-full opacity-20 blur-xl"
            style={{
              width:      '80px',
              height:     '80px',
              background: orbState.color,
            }}
          />
        )}

        {/* Mid ring — subtle */}
        <div
          className="absolute rounded-full opacity-15 blur-md"
          style={{
            width:      '56px',
            height:     '56px',
            background: orbState.color,
          }}
        />

        {/* Main orb body */}
        <div
          className={`relative w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500 ${orbState.anim}`}
          style={{
            background: `radial-gradient(circle at 35% 30%, ${orbState.color}cc, ${orbState.color}55)`,
            border:     `1.5px solid ${orbState.color}50`,
            boxShadow:  `0 0 16px ${orbState.color}30, inset 0 1px 0 rgba(255,255,255,0.15)`,
          }}
        >
          {/* Inner highlight — glass effect */}
          <div
            className="absolute top-1.5 left-2 w-2.5 h-1.5 rounded-full opacity-50"
            style={{ background: 'rgba(255,255,255,0.7)', filter: 'blur(1px)' }}
          />
          {/* Core dot */}
          <div
            className="w-2 h-2 rounded-full"
            style={{
              background: `radial-gradient(circle, white, ${orbState.color})`,
              opacity: 0.7,
            }}
          />
        </div>
      </div>

      {/* ── State label ── */}
      <div
        className="text-[9px] font-medium tracking-[0.2em] uppercase transition-colors duration-500"
        style={{ color: orbState.color }}
      >
        {orbState.label}
      </div>

      {/* ── Conversation Panel ── */}
      <ConversationPanel />

    </div>
  );
}