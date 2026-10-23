/**
 * Orb.jsx
 *
 * Seven's presence: a fluid, glassy sphere drawn on a HiDPI canvas. Its colour
 * and energy ease between states instead of jumping, the surface flows with a
 * few slow harmonics, and each state has one signature motion:
 *   idle       calm breathing
 *   listening  soft ripples outward
 *   thinking   a slow rotating sheen
 *   speaking   a gentle pulse
 * Honours prefers-reduced-motion.
 */
import { useEffect, useRef } from 'react';

const PALETTE = {
  idle:      { a: [99, 102, 241], b: [129, 140, 248], energy: 0.18 },
  listening: { a: [34, 197, 94], b: [74, 222, 128], energy: 0.55 },
  thinking:  { a: [168, 85, 247], b: [192, 132, 252], energy: 0.7 },
  speaking:  { a: [99, 102, 241], b: [34, 211, 238], energy: 0.85 },
};

const lerp = (a, b, t) => a + (b - a) * t;
const rgba = (c, alpha) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${alpha})`;

export default function Orb({ state = 'idle', size = 260 }) {
  const canvas = useRef(null);
  const target = useRef(PALETTE.idle);
  useEffect(() => { target.current = PALETTE[state] || PALETTE.idle; }, [state]);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return undefined;
    const ctx = el.getContext('2d');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = size * 1.8;
    el.width = W * dpr;
    el.height = W * dpr;
    el.style.width = `${W}px`;
    el.style.height = `${W}px`;
    ctx.scale(dpr, dpr);

    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const cur = { a: [...PALETTE.idle.a], b: [...PALETTE.idle.b], energy: PALETTE.idle.energy, sheen: 0, ripple: 0, pulse: 0 };
    const cx = W / 2, cy = W / 2, R = size * 0.36;
    let t = 0, raf = 0, last = performance.now();

    const blob = (radius, e, time) => {
      ctx.beginPath();
      const n = 120;
      for (let i = 0; i <= n; i++) {
        const th = (i / n) * Math.PI * 2;
        const k = 1
          + e * 0.045 * Math.sin(3 * th + time * 1.1)
          + e * 0.03 * Math.sin(5 * th - time * 1.6)
          + 0.012 * Math.sin(2 * th + time * 0.5);
        const x = cx + Math.cos(th) * radius * k;
        const y = cy + Math.sin(th) * radius * k;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();
    };

    const draw = now => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      t += dt * (reduce ? 0.25 : 1);
      const tg = target.current;
      const ease = 1 - Math.pow(0.02, dt);             // frame-rate independent smoothing
      for (let i = 0; i < 3; i++) { cur.a[i] = lerp(cur.a[i], tg.a[i], ease); cur.b[i] = lerp(cur.b[i], tg.b[i], ease); }
      cur.energy = lerp(cur.energy, tg.energy, ease);
      cur.sheen = lerp(cur.sheen, tg === PALETTE.thinking ? 1 : 0, ease);
      cur.ripple = lerp(cur.ripple, tg === PALETTE.listening ? 1 : 0, ease);
      cur.pulse = lerp(cur.pulse, tg === PALETTE.speaking ? 1 : 0, ease);

      const e = cur.energy;
      const breathe = 1 + 0.018 * Math.sin(t * 1.15) + cur.pulse * 0.045 * Math.max(0, Math.sin(t * 5.2));
      const r = R * breathe;
      ctx.clearRect(0, 0, W, W);

      // Ambient glow
      const glow = ctx.createRadialGradient(cx, cy, r * 0.6, cx, cy, r * 2.3);
      glow.addColorStop(0, rgba(cur.a, 0.22 + e * 0.12));
      glow.addColorStop(0.45, rgba(cur.b, 0.06 + e * 0.05));
      glow.addColorStop(1, rgba(cur.b, 0));
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, W, W);

      // Listening ripples
      if (cur.ripple > 0.01) {
        for (let k = 0; k < 3; k++) {
          const p = (t * 0.45 + k / 3) % 1;
          ctx.beginPath();
          ctx.arc(cx, cy, r * (1.08 + p * 0.85), 0, Math.PI * 2);
          ctx.strokeStyle = rgba(cur.b, (1 - p) * 0.28 * cur.ripple);
          ctx.lineWidth = 1.25;
          ctx.stroke();
        }
      }

      // Body
      blob(r, e, t);
      const body = ctx.createRadialGradient(cx - r * 0.35, cy - r * 0.4, r * 0.05, cx, cy, r * 1.15);
      body.addColorStop(0, rgba(cur.b.map(c => lerp(c, 255, 0.55)), 0.95));
      body.addColorStop(0.22, rgba(cur.b, 0.95));
      body.addColorStop(0.62, rgba(cur.a, 0.95));
      body.addColorStop(1, rgba(cur.a.map(c => c * 0.45), 0.98));
      ctx.fillStyle = body;
      ctx.fill();

      ctx.save();
      blob(r, e, t);
      ctx.clip();
      // Two slow light lobes give the inside depth and movement
      const lobes = [
        [cx + Math.cos(t * 0.55) * r * 0.42, cy + Math.sin(t * 0.75) * r * 0.36, cur.b, 0.55],
        [cx + Math.cos(t * 0.4 + 2.4) * r * 0.48, cy + Math.sin(t * 0.5 + 1.7) * r * 0.42, [56, 189, 248], 0.22 + e * 0.12],
      ];
      for (const [lx, ly, col, a] of lobes) {
        const g = ctx.createRadialGradient(lx, ly, 0, lx, ly, r * 0.85);
        g.addColorStop(0, rgba(col, a));
        g.addColorStop(1, rgba(col, 0));
        ctx.fillStyle = g;
        ctx.fillRect(cx - r * 1.3, cy - r * 1.3, r * 2.6, r * 2.6);
      }
      // Thinking sheen
      if (cur.sheen > 0.01 && ctx.createConicGradient) {
        const sheen = ctx.createConicGradient(t * 1.4, cx, cy);
        sheen.addColorStop(0, rgba([255, 255, 255], 0));
        sheen.addColorStop(0.12, rgba([255, 255, 255], 0.22 * cur.sheen));
        sheen.addColorStop(0.24, rgba([255, 255, 255], 0));
        sheen.addColorStop(1, rgba([255, 255, 255], 0));
        ctx.fillStyle = sheen;
        ctx.fillRect(cx - r * 1.3, cy - r * 1.3, r * 2.6, r * 2.6);
      }
      // Lower shade for depth
      const shade = ctx.createLinearGradient(cx, cy - r, cx, cy + r);
      shade.addColorStop(0.55, rgba([0, 0, 0], 0));
      shade.addColorStop(1, rgba([0, 0, 0], 0.22));
      ctx.fillStyle = shade;
      ctx.fillRect(cx - r * 1.3, cy - r * 1.3, r * 2.6, r * 2.6);
      ctx.restore();

      // Glass highlight and rim
      const hl = ctx.createRadialGradient(cx - r * 0.38, cy - r * 0.45, 0, cx - r * 0.38, cy - r * 0.45, r * 0.42);
      hl.addColorStop(0, rgba([255, 255, 255], 0.32));
      hl.addColorStop(1, rgba([255, 255, 255], 0));
      ctx.fillStyle = hl;
      ctx.beginPath();
      ctx.ellipse(cx - r * 0.36, cy - r * 0.44, r * 0.34, r * 0.22, -0.55, 0, Math.PI * 2);
      ctx.fill();
      // Luminous rim
      blob(r, e, t);
      ctx.save();
      ctx.shadowColor = rgba(cur.b, 0.7);
      ctx.shadowBlur = 18 + e * 14;
      ctx.strokeStyle = rgba(cur.b.map(c => lerp(c, 255, 0.35)), 0.45);
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.restore();

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [size]);

  return <canvas ref={canvas} aria-hidden className="pointer-events-none" />;
}
