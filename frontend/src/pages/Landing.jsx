import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import useStatus from '../stores/useStatus';
import useTasks  from '../stores/useTasks';
import api       from '../api';

// ── Canvas particle orb ───────────────────────────────────────────────────

function OrbCanvas({ state }) {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);
  const particles = useRef([]);
  const time      = useRef(0);

  const STATE_COLORS = {
    idle:      { core: '#6366f1', glow: '#4f46e5', ring: '#818cf8' },
    listening: { core: '#22c55e', glow: '#16a34a', ring: '#4ade80' },
    thinking:  { core: '#a855f7', glow: '#9333ea', ring: '#c084fc' },
    speaking:  { core: '#6366f1', glow: '#4f46e5', ring: '#818cf8' },
  };

  const colors = STATE_COLORS[state] || STATE_COLORS.idle;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width  = 420;
    const H = canvas.height = 420;
    const cx = W / 2;
    const cy = H / 2;

    // Initialize particles
    particles.current = Array.from({ length: 120 }, (_, i) => {
      const angle  = (i / 120) * Math.PI * 2;
      const radius = 80 + Math.random() * 60;
      const speed  = 0.003 + Math.random() * 0.006;
      const size   = 0.8 + Math.random() * 2.2;
      const offset = Math.random() * Math.PI * 2;
      const drift  = (Math.random() - 0.5) * 0.002;
      return { angle, radius, speed, size, offset, drift, opacity: 0.2 + Math.random() * 0.6 };
    });

    const draw = () => {
      time.current += 0.016;
      ctx.clearRect(0, 0, W, H);

      // Outer ambient glow
      const outerGlow = ctx.createRadialGradient(cx, cy, 60, cx, cy, 200);
      outerGlow.addColorStop(0, colors.glow + '18');
      outerGlow.addColorStop(1, 'transparent');
      ctx.fillStyle = outerGlow;
      ctx.fillRect(0, 0, W, H);

      // Pulsing rings
      const pulseCount = state === 'listening' ? 3 : state === 'thinking' ? 4 : 2;
      for (let r = 0; r < pulseCount; r++) {
        const phase  = (time.current * (0.4 + r * 0.15) + r * 1.2) % 1;
        const radius = 90 + phase * 110;
        const alpha  = (1 - phase) * (state === 'idle' ? 0.06 : 0.12);
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.strokeStyle = colors.ring + Math.round(alpha * 255).toString(16).padStart(2, '0');
        ctx.lineWidth   = 1;
        ctx.stroke();
      }

      // Particles
      particles.current.forEach(p => {
        const speedMult = state === 'idle' ? 0.4 : state === 'thinking' ? 2.2 : state === 'listening' ? 1.4 : 1.8;
        p.angle += p.speed * speedMult;
        p.drift  = (Math.random() - 0.5) * 0.001;

        const wobble = Math.sin(time.current * 1.2 + p.offset) * 18;
        const r      = p.radius + wobble;
        const x      = cx + Math.cos(p.angle) * r;
        const y      = cy + Math.sin(p.angle) * r * 0.55;

        const distFromCenter = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
        const depthAlpha     = Math.min(1, distFromCenter / 60);
        const flicker        = 0.7 + Math.sin(time.current * 3 + p.offset) * 0.3;

        ctx.beginPath();
        ctx.arc(x, y, p.size * (state === 'idle' ? 0.7 : 1), 0, Math.PI * 2);
        ctx.fillStyle = colors.ring + Math.round(p.opacity * depthAlpha * flicker * 255).toString(16).padStart(2, '0');
        ctx.fill();
      });

      // Core orb body
      const coreGrad = ctx.createRadialGradient(cx - 18, cy - 18, 4, cx, cy, 72);
      coreGrad.addColorStop(0, '#ffffff22');
      coreGrad.addColorStop(0.3, colors.core + 'cc');
      coreGrad.addColorStop(0.7, colors.glow + '88');
      coreGrad.addColorStop(1,   colors.glow + '11');
      ctx.beginPath();
      ctx.arc(cx, cy, 72, 0, Math.PI * 2);
      ctx.fillStyle = coreGrad;
      ctx.fill();

      // Inner glow
      const innerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 50);
      innerGlow.addColorStop(0, '#ffffff18');
      innerGlow.addColorStop(1, 'transparent');
      ctx.beginPath();
      ctx.arc(cx, cy, 50, 0, Math.PI * 2);
      ctx.fillStyle = innerGlow;
      ctx.fill();

      // Glass highlight
      const hlGrad = ctx.createRadialGradient(cx - 22, cy - 22, 0, cx - 22, cy - 22, 32);
      hlGrad.addColorStop(0, 'rgba(255,255,255,0.22)');
      hlGrad.addColorStop(1, 'transparent');
      ctx.beginPath();
      ctx.ellipse(cx - 22, cy - 22, 28, 18, -0.4, 0, Math.PI * 2);
      ctx.fillStyle = hlGrad;
      ctx.fill();

      // Orbiting dots (3 main satellites)
      const satelliteCount = state === 'thinking' ? 5 : 3;
      for (let s = 0; s < satelliteCount; s++) {
        const baseAngle = time.current * (0.6 + s * 0.2) + (s * Math.PI * 2) / satelliteCount;
        const orbitR    = 95 + s * 12;
        const sx        = cx + Math.cos(baseAngle) * orbitR;
        const sy        = cy + Math.sin(baseAngle) * orbitR * 0.55;
        const sSize     = 2.5 - s * 0.3;

        // Trail
        for (let t = 1; t <= 6; t++) {
          const trailAngle = baseAngle - t * 0.08;
          const tx = cx + Math.cos(trailAngle) * orbitR;
          const ty = cy + Math.sin(trailAngle) * orbitR * 0.55;
          ctx.beginPath();
          ctx.arc(tx, ty, sSize * (1 - t / 8), 0, Math.PI * 2);
          ctx.fillStyle = colors.ring + Math.round((0.4 - t * 0.06) * 255).toString(16).padStart(2, '0');
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(sx, sy, sSize, 0, Math.PI * 2);
        ctx.fillStyle = colors.ring + 'ee';
        ctx.fill();

        // Satellite glow
        const satGlow = ctx.createRadialGradient(sx, sy, 0, sx, sy, sSize * 4);
        satGlow.addColorStop(0, colors.ring + '40');
        satGlow.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(sx, sy, sSize * 4, 0, Math.PI * 2);
        ctx.fillStyle = satGlow;
        ctx.fill();
      }

      animRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [state, colors.core, colors.glow, colors.ring]);

  return (
    <canvas ref={canvasRef}
            width={420} height={420}
            className="w-[210px] h-[210px]"
            style={{ imageRendering: 'auto' }} />
  );
}

// ── Conversation drawer ───────────────────────────────────────────────────

function ConversationText({ userText, sevenText, visible }) {
  return (
    <div className={`absolute bottom-12 left-0 right-0 flex flex-col items-center
                     transition-all duration-700 ease-out
                     ${visible ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
      {userText && (
        <p className="text-[11px] text-white/30 font-light tracking-wide mb-2
                      max-w-[400px] text-center leading-relaxed">
          {userText}
        </p>
      )}
      {sevenText && (
        <p className="text-[13px] text-white/60 font-light tracking-wide
                      max-w-[420px] text-center leading-relaxed">
          {sevenText}
        </p>
      )}
    </div>
  );
}

// ── Console info panel ────────────────────────────────────────────────────

function ConsolePanel({ tasks, schedules, triggers, mem, speed, hw }) {
  const now  = new Date();
  const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  const date = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });

  const [tick, setTick] = useState(0);
  useEffect(() => {
    const i = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(i);
  }, []);

  const activeScheds  = schedules.filter(s => s.status === 'active');
  const pendingTasks  = tasks.filter(t => !t.completed);
  const overdueTasks  = pendingTasks.filter(t => {
    if (!t.due_date) return false;
    return new Date(t.due_date + 'T00:00:00') < new Date(new Date().setHours(0,0,0,0));
  });

  const lines = [
    { label: 'SYS',   value: `Seven v${hw?.version || '1.3.1'} · ${date}`,     dim: false },
    { label: 'TIME',  value: time,                                                dim: false },
    { label: '─────', value: '',                                                  dim: true  },
    { label: 'TASKS', value: `${pendingTasks.length} pending · ${overdueTasks.length} overdue`, dim: pendingTasks.length === 0 },
    { label: 'SCHED', value: `${activeScheds.length} active schedules`,           dim: activeScheds.length === 0 },
    { label: 'TRIG',  value: `${triggers} active triggers`,                       dim: triggers === 0 },
    { label: '─────', value: '',                                                  dim: true  },
    { label: 'MEM',   value: `${mem?.total_conversations ?? 0} convos · ${mem?.total_facts ?? 0} facts`, dim: false },
    { label: 'RESP',  value: speed?.count > 0 ? `avg ${speed.avg}ms` : 'no data', dim: !speed?.count },
    { label: 'CPU',   value: hw?.cpu_percent != null ? `${Math.round(hw.cpu_percent)}%` : '—', dim: false },
    { label: 'RAM',   value: hw?.ram_percent != null ? `${Math.round(hw.ram_percent)}%` : '—', dim: false },
  ];

  if (pendingTasks.length > 0) {
    lines.push({ label: '─────', value: '', dim: true });
    pendingTasks.slice(0, 3).forEach((t, i) => {
      lines.push({
        label: `T${String(i + 1).padStart(2, '0')}`,
        value: t.text.length > 28 ? t.text.slice(0, 28) + '...' : t.text,
        dim:   false,
      });
    });
    if (pendingTasks.length > 3) {
      lines.push({ label: '   +', value: `${pendingTasks.length - 3} more`, dim: true });
    }
  }

  if (activeScheds.length > 0) {
    lines.push({ label: '─────', value: '', dim: true });
    activeScheds.slice(0, 2).forEach((s, i) => {
      const remain = (() => {
        const diff = new Date(s.time) - new Date();
        if (diff <= 0) return 'now';
        const m = Math.floor(diff / 60000);
        const h = Math.floor(m / 60);
        if (h > 0) return `in ${h}h ${m % 60}m`;
        return `in ${m}m`;
      })();
      lines.push({
        label: `S${String(i + 1).padStart(2, '0')}`,
        value: `${(s.message || '').slice(0, 20)} · ${remain}`,
        dim:   false,
      });
    });
  }

  return (
    <div className="flex flex-col h-full"
         style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace" }}>
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-white/[0.06]">
        <div className="w-1.5 h-1.5 rounded-full bg-s-accent/60 animate-pulse" />
        <span className="text-[8px] text-white/25 uppercase tracking-[0.2em]">system console</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-0.5
                      scrollbar-thin scrollbar-thumb-white/6 scrollbar-track-transparent">
        {lines.map((line, i) => (
          <div key={i} className="flex items-baseline gap-2">
            <span className={`text-[8px] flex-shrink-0 w-10 text-right
                              ${line.label.includes('─')
                                ? 'text-white/10'
                                : 'text-s-accent/50'}`}>
              {line.label.includes('─') ? '' : line.label}
            </span>
            {line.label.includes('─') ? (
              <div className="flex-1 h-px bg-white/[0.05] mt-1" />
            ) : (
              <span className={`text-[9px] leading-5 flex-1
                                ${line.dim ? 'text-white/20' : 'text-white/55'}`}>
                {line.value}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Cursor blink */}
      <div className="mt-3 pt-2 border-t border-white/[0.04] flex items-center gap-1.5">
        <span className="text-[8px] text-s-accent/40">$</span>
        <span className="text-[8px] text-white/20">_</span>
        <div className="w-1.5 h-3 bg-s-accent/40 animate-[blink_1s_step-end_infinite]" />
      </div>
    </div>
  );
}

function InfoLine({ label, value, dim, right }) {
  return (
    <div className={`flex items-baseline gap-2 ${right ? 'flex-row-reverse' : ''}`}
         style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
      <span className="text-[7px] text-s-accent/30 flex-shrink-0 w-8"
            style={{ textAlign: right ? 'left' : 'right' }}>
        {label}
      </span>
      <span className={`text-[8.5px] leading-5
                        ${dim ? 'text-white/12' : 'text-white/30'}`}>
        {value}
      </span>
    </div>
  );
}

// ── Main Landing page ─────────────────────────────────────────────────────

export default function Landing() {
  const navigate = useNavigate();
  const st = useStatus();
  const { tasks, fetch: fetchTasks } = useTasks();

  const [scheds,    setScheds]    = useState([]);
  const [triggers,  setTriggers]  = useState(0);
  const [mem,       setMem]       = useState(null);
  const [speed,     setSpeed]     = useState(null);
  const [hw,        setHw]        = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);

  useEffect(() => {
    st.fetch();
    fetchTasks();
    const loadData = () => {
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/triggers/stats').then(r => setTriggers(r.data?.enabled ?? 0)).catch(() => {});
      api.get('/memory/stats').then(r => setMem(r.data)).catch(() => {});
      api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});
      api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
    };
    loadData();
    const si = setInterval(st.fetch, 3000);
    const di = setInterval(loadData, 15000);
    return () => { clearInterval(si); clearInterval(di); };
  }, []);

  // Show drawer when there is conversation content
  useEffect(() => {
    const hasContent = !!(st.userText || st.sevenText);
    if (hasContent) {
      setDrawerVisible(true);
    }
    // Fade out after 5 seconds of no change
    const t = setTimeout(() => setDrawerVisible(false), hasContent ? 5000 : 1500);
    return () => clearTimeout(t);
  }, [st.userText, st.sevenText]);

  const orbState = st.thinking  ? 'thinking'
                 : st.speaking  ? 'speaking'
                 : st.listening ? 'listening'
                 : 'idle';

  const stateLabel = st.thinking  ? 'Processing'
                   : st.speaking  ? 'Speaking'
                   : st.listening ? 'Listening'
                   : 'Ready';

  const stateColor = orbState === 'thinking'  ? '#a855f7'
                   : orbState === 'speaking'  ? '#6366f1'
                   : orbState === 'listening' ? '#22c55e'
                   : 'rgba(255,255,255,0.2)';

  return (
    <div className="h-full relative overflow-hidden bg-s-bg"
         style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>

      {/* Subtle background radial */}
      <div className="absolute inset-0 pointer-events-none"
           style={{
             background: `radial-gradient(ellipse 60% 50% at 40% 50%,
               ${stateColor}08 0%,
               transparent 70%)`,
             transition: 'background 1s ease',
           }} />

      {/* Main layout: orb centered, info scattered */}
      <div className="h-full relative flex items-center justify-center">

        {/* Brand - top center */}
        <div className="absolute top-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1">
          <span className="text-[14px] font-semibold tracking-[0.35em] text-white/80
                           font-mono uppercase">
            SEVEN
          </span>
          <span className="text-[8px] text-white/15 tracking-[0.2em] uppercase">
            Private AI Voice Assistant
          </span>
        </div>

        {/* Left info column */}
        <div className="absolute left-8 top-1/2 -translate-y-1/2
                        flex flex-col gap-1"
             style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
          <InfoLine label="TASKS" value={`${tasks.filter(t => !t.completed).length} pending`}
                    dim={tasks.filter(t => !t.completed).length === 0} />
          <InfoLine label="SCHED" value={`${scheds.filter(s => s.status === 'active').length} active`}
                    dim={scheds.filter(s => s.status === 'active').length === 0} />
          <InfoLine label="TRIG"  value={`${triggers} enabled`}
                    dim={triggers === 0} />
          <div className="h-2" />
          {tasks.filter(t => !t.completed).slice(0, 3).map((t, i) => (
            <InfoLine key={t.id}
                      label={`T${i + 1}`}
                      value={t.text.length > 24 ? t.text.slice(0, 24) + '...' : t.text}
                      dim={false} />
          ))}
        </div>

        {/* Right info column */}
        <div className="absolute right-8 top-1/2 -translate-y-1/2
                        flex flex-col gap-1 items-end"
             style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
          <InfoLine label="MEM"  value={`${mem?.total_conversations ?? 0} convos`} dim={false} right />
          <InfoLine label="FACT" value={`${mem?.total_facts ?? 0} facts`} dim={false} right />
          <InfoLine label="RESP" value={speed?.count > 0 ? `${speed.avg}ms avg` : 'no data'} dim={!speed?.count} right />
          <div className="h-2" />
          <InfoLine label="CPU"  value={hw?.cpu_percent != null ? `${Math.round(hw.cpu_percent)}%` : '--'} dim={false} right />
          <InfoLine label="RAM"  value={hw?.ram_percent != null ? `${Math.round(hw.ram_percent)}%` : '--'} dim={false} right />
          <InfoLine label="VER"  value={`v${st.version}`} dim={true} right />
        </div>

        {/* Center: Orb */}
        <div className="flex flex-col items-center gap-6">
          <div className="relative">
            <OrbCanvas state={orbState} />
          </div>

          {/* State label */}
          <div className="flex flex-col items-center gap-1.5">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full transition-all duration-500"
                   style={{ backgroundColor: stateColor }} />
              <span className="text-[11px] font-light tracking-[0.25em] uppercase"
                    style={{ color: stateColor, transition: 'color 0.5s ease' }}>
                {stateLabel}
              </span>
            </div>
            <span className="text-[9px] text-white/15 font-mono tracking-wider">
              {st.uptime} uptime
            </span>
          </div>

          {/* Navigation */}
          <div className="flex items-center gap-2 mt-1">
            {[
              {
                label: 'Console',
                path: '/console',
                desc: 'Live command log',
                side: 'left',
              },
              {
                label: 'Guide',
                path: '/blog',
                desc: 'Docs and tips',
                side: 'center',
              },
              {
                label: 'Dashboard',
                path: '/dashboard',
                desc: 'Overview and tasks',
                side: 'right',
              },
            ].map(({ label, path, desc, side }) => (
              <button key={path}
                      onClick={() => navigate(path)}
                      className="flex flex-col items-center gap-1 px-5 py-2.5 rounded-xl
                                 border border-white/[0.04] hover:border-white/[0.10]
                                 bg-white/[0.01] hover:bg-white/[0.03]
                                 transition-all duration-200 group min-w-[90px]">
                <span className="text-[9px] text-white/35 hover:text-white/65
                                 transition-colors duration-200 tracking-[0.18em]
                                 uppercase font-medium group-hover:text-white/65">
                  {label}
                </span>
                <span className="text-[7px] text-white/12 group-hover:text-white/25
                                 transition-colors duration-200 tracking-wider">
                  {desc}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Conversation text */}
      <ConversationText
        userText={st.userText}
        sevenText={st.sevenText}
        visible={drawerVisible}
      />

      {/* Footer */}
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-center
                      gap-6 px-8 py-3 border-t border-white/[0.04]">
        <div className="flex items-center gap-2">
          <kbd className="text-[7px] font-mono text-white/20 bg-white/[0.04]
                          border border-white/[0.08] rounded px-1.5 py-0.5 leading-none
                          tracking-wider">
            Alt + Shift + T
          </kbd>
          <span className="text-[7px] text-white/15 tracking-wider">
            Toggle task panel
          </span>
        </div>
        <div className="w-px h-3 bg-white/[0.06]" />
        <span className="text-[7px] text-white/10 tracking-widest font-mono uppercase">
          All processing local · Zero cloud
        </span>
        <div className="w-px h-3 bg-white/[0.06]" />
        <div className="flex items-center gap-2">
          <div className="w-1 h-1 rounded-full bg-white/15 animate-pulse" />
          <span className="text-[7px] text-white/15 tracking-wider font-mono">
            Seven v{hw?.version || '1.3.1'}
          </span>
        </div>
      </div>
    </div>
  );
}