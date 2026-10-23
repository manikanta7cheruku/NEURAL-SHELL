/**
 * OrbGL
 *
 * Seven's presence: a ray-marched glass sphere with light flowing inside it.
 * The shell moves slowly and stays smooth; inside, a short volumetric walk
 * along the refracted ray shows a living nebula in Seven's colours. The rim
 * carries a thin-film iridescence and a soft halo is computed from how close
 * each ray passed to the surface.
 *
 * Cursor: the key light follows the pointer, the sphere leans toward it and
 * its surface swells gently on the side nearest the cursor, all eased so it
 * feels like it is aware of you rather than tracking you.
 *
 * States ease into each other:
 *   idle       slow breathing, deep indigo
 *   listening  emerald, fine ripples travel across the surface
 *   thinking   violet, the inner light turns and a sheen sweeps slowly around
 *   speaking   indigo to cyan, the surface pulses
 *
 * Falls back to the 2D canvas orb when WebGL is unavailable and slows down
 * under prefers-reduced-motion.
 */
import { useEffect, useRef, useState } from 'react';
import Orb from './Orb';

const STATES = {
  idle:      { a: [0.23, 0.22, 0.75], b: [0.47, 0.50, 1.00], energy: 0.25, listen: 0, think: 0, speak: 0 },
  listening: { a: [0.03, 0.45, 0.32], b: [0.30, 0.95, 0.66], energy: 0.55, listen: 1, think: 0, speak: 0 },
  thinking:  { a: [0.36, 0.14, 0.72], b: [0.80, 0.55, 1.00], energy: 0.65, listen: 0, think: 1, speak: 0 },
  speaking:  { a: [0.20, 0.25, 0.85], b: [0.20, 0.85, 1.00], energy: 0.90, listen: 0, think: 0, speak: 1 },
};

const VERT = `attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }`;

const FRAG = `
precision highp float;
uniform vec2 uRes;
uniform float uTime, uEnergy, uListen, uThink, uSpeak, uHover, uSpin;
uniform vec2 uMouse;
uniform vec3 uColA, uColB;

vec3 mod289(vec3 x){ return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x){ return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x){ return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r){ return 1.79284291400159 - 0.85373472095314 * r; }
float snoise(vec3 v){
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0))
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}

mat3 rotY(float a){ float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }
mat3 rotX(float a){ float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }

float fbm(vec3 q){
  return snoise(q) * 0.55 + snoise(q * 2.03 + 7.1) * 0.3 + snoise(q * 4.1 - 3.7) * 0.15;
}

// Smooth glass shell: only slow, low-frequency motion in the geometry.
float map(vec3 p){
  vec3 q = rotX(uMouse.y * 0.3) * rotY(uTime * 0.08 - uMouse.x * 0.4) * p;
  float d = snoise(q * 1.05 + vec3(0.0, uTime * 0.16, uTime * 0.11)) * (0.025 + 0.05 * uEnergy);
  d += uSpeak * 0.032 * sin(uTime * 4.6 + q.y * 4.0) * (0.55 + 0.45 * sin(uTime * 1.6));
  d += uListen * 0.014 * sin(length(q.xy) * 13.0 - uTime * 3.4);
  vec3 toward = normalize(vec3(uMouse * 0.9, 1.0));
  d += uHover * 0.085 * pow(max(dot(normalize(p), toward), 0.0), 6.0);
  return length(p) - (0.9 + 0.014 * sin(uTime * 1.05) + d);
}

vec3 normalAt(vec3 p){
  vec2 e = vec2(0.002, 0.0);
  return normalize(vec3(map(p + e.xyy) - map(p - e.xyy), map(p + e.yxy) - map(p - e.yxy), map(p + e.yyx) - map(p - e.yyx)));
}

void main(){
  vec2 uv = (gl_FragCoord.xy * 2.0 - uRes) / min(uRes.x, uRes.y);
  vec3 ro = vec3(0.0, 0.0, 3.4);
  vec3 rd = normalize(vec3(uv * 0.62, -1.0));

  float t = 0.0, minD = 10.0;
  bool hit = false;
  for (int i = 0; i < 56; i++){
    float d = map(ro + rd * t);
    minD = min(minD, d);
    if (d < 0.0012){ hit = true; break; }
    t += d * 0.9;
    if (t > 6.0) break;
  }

  vec3 glow = mix(uColA, uColB, 0.55);
  // The halo fades to nothing well inside the canvas, so its square edge is never visible.
  float halo = exp(-max(minD, 0.0) * 3.6) * (0.3 + 0.34 * uEnergy) * (1.0 - smoothstep(0.5, 0.96, length(uv)));
  if (!hit){
    float a = clamp(halo, 0.0, 1.0) * 0.8;
    gl_FragColor = vec4(glow * a, a);
    return;
  }

  vec3 p = ro + rd * t;
  vec3 n = normalAt(p);
  vec3 v = -rd;
  float ndv = max(dot(n, v), 0.0);
  float fres = pow(1.0 - ndv, 3.0);

  // Light flowing inside the glass: a short volumetric walk along the refracted ray.
  vec3 rr = refract(rd, n, 0.78);
  vec3 flow = vec3(uTime * 0.09, -uTime * 0.13, uTime * 0.07);
  mat3 spin = rotY(uSpin);      // phase accumulated on the CPU, so a state change never makes it race
  vec3 inner = vec3(0.0);
  float acc = 0.0;
  for (int i = 1; i <= 7; i++){
    vec3 q = p + rr * (float(i) * 0.24);
    float r = length(q);
    float f = fbm(spin * q * 1.35 + flow);
    float dens = smoothstep(-0.05, 0.75, f) * (1.0 - smoothstep(0.35, 0.95, r));
    dens *= 0.55 + 0.6 * uEnergy + 0.5 * uSpeak * (0.5 + 0.5 * sin(uTime * 3.6 + r * 9.0));
    vec3 c = mix(uColA, uColB, smoothstep(-0.3, 0.6, f + q.y * 0.4));
    inner += c * dens * (1.0 - acc) * 0.78;
    acc += dens * 0.16;
  }
  float core = pow(ndv, 2.2);
  inner += uColB * core * (0.26 + 0.3 * uEnergy);

  // Glass shell: tinted body, iridescent rim, a sharp highlight that follows the cursor.
  vec3 L = normalize(vec3(uMouse.x * 1.5 - 0.4, uMouse.y * 1.3 + 0.6, 1.0));
  float spec = pow(max(dot(reflect(-L, n), v), 0.0), 90.0);
  float sheen = pow(max(dot(reflect(-L, n), v), 0.0), 12.0) * 0.18;
  float hue = dot(n, vec3(0.3, 0.55, 0.2)) * 0.8 + fres * 1.2 + uTime * 0.035;
  vec3 irid = 0.5 + 0.5 * cos(6.28318 * (hue + vec3(0.0, 0.33, 0.67)));
  vec3 rimCol = mix(uColB, irid, 0.45) * 1.25;

  vec3 col = uColA * 0.07 + inner;
  col = mix(col, rimCol, fres * 0.85);
  col += vec3(1.0) * (spec * 1.1 + sheen);

  float ang = atan(n.y, n.x);
  float sweep = smoothstep(0.9, 1.0, sin(ang * 2.0 + uSpin * 1.6)) * (0.3 + fres);
  col += vec3(0.92, 0.88, 1.0) * sweep * 0.5 * uThink;

  col += glow * halo * 0.25;
  col = col / (1.0 + col * 0.3);
  gl_FragColor = vec4(col, 1.0);
}`;

const lerp = (a, b, t) => a + (b - a) * t;

function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'shader failed');
  return s;
}

export default function OrbGL({ state = 'idle', size = 260 }) {
  const canvas = useRef(null);
  const target = useRef(STATES.idle);
  const [fallback, setFallback] = useState(false);
  useEffect(() => { target.current = STATES[state] || STATES.idle; }, [state]);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return undefined;
    const gl = el.getContext('webgl', { alpha: true, premultipliedAlpha: true, antialias: true });
    if (!gl) { setFallback(true); return undefined; }

    let program;
    try {
      program = gl.createProgram();
      gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERT));
      gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('link failed');
    } catch {
      setFallback(true);
      return undefined;
    }
    gl.useProgram(program);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(program, 'p');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const u = name => gl.getUniformLocation(program, name);
    const U = {
      res: u('uRes'), time: u('uTime'), energy: u('uEnergy'), listen: u('uListen'), think: u('uThink'),
      speak: u('uSpeak'), hover: u('uHover'), spin: u('uSpin'), mouse: u('uMouse'), a: u('uColA'), b: u('uColB'),
    };

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = Math.round(size * 1.6);
    el.width = W * dpr;
    el.height = W * dpr;
    el.style.width = `${W}px`;
    el.style.height = `${W}px`;
    gl.viewport(0, 0, el.width, el.height);
    gl.uniform2f(U.res, el.width, el.height);

    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const s0 = STATES.idle;
    const cur = { a: [...s0.a], b: [...s0.b], energy: s0.energy, listen: 0, think: 0, speak: 0, mx: 0, my: 0, hover: 0, spin: 0 };
    const pointer = { x: 0, y: 0, near: 0 };

    const onMove = e => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const dx = (e.clientX - cx) / (r.width / 2), dy = (cy - e.clientY) / (r.height / 2);
      const dist = Math.hypot(dx, dy);
      pointer.x = Math.max(-1, Math.min(1, dx / Math.max(1, dist)));
      pointer.y = Math.max(-1, Math.min(1, dy / Math.max(1, dist)));
      pointer.near = Math.max(0, 1 - (dist - 0.45) / 2.2);
    };
    const onLeave = () => { pointer.x = 0; pointer.y = 0; pointer.near = 0; };
    window.addEventListener('pointermove', onMove, { passive: true });
    document.addEventListener('pointerleave', onLeave);

    let raf = 0, last = performance.now(), t = Math.random() * 100;
    const frame = now => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      t += dt * (reduce ? 0.3 : 1);
      const tg = target.current;
      const e = 1 - Math.pow(0.015, dt);            // frame-rate independent easing
      const ep = 1 - Math.pow(0.08, dt);            // the pointer eases a little faster
      for (let i = 0; i < 3; i++) { cur.a[i] = lerp(cur.a[i], tg.a[i], e); cur.b[i] = lerp(cur.b[i], tg.b[i], e); }
      cur.energy = lerp(cur.energy, tg.energy, e);
      cur.listen = lerp(cur.listen, tg.listen, e);
      cur.think = lerp(cur.think, tg.think, e);
      cur.speak = lerp(cur.speak, tg.speak, e);
      cur.mx = lerp(cur.mx, pointer.x * pointer.near, ep);
      cur.my = lerp(cur.my, pointer.y * pointer.near, ep);
      cur.hover = lerp(cur.hover, pointer.near, ep);
      cur.spin += dt * (reduce ? 0.05 : 0.14 + 0.22 * cur.think + 0.08 * cur.speak);   // calm even while thinking

      gl.uniform1f(U.time, t);
      gl.uniform1f(U.energy, cur.energy);
      gl.uniform1f(U.listen, cur.listen);
      gl.uniform1f(U.think, cur.think);
      gl.uniform1f(U.speak, cur.speak);
      gl.uniform1f(U.hover, reduce ? 0 : cur.hover);
      gl.uniform1f(U.spin, cur.spin);
      gl.uniform2f(U.mouse, cur.mx, cur.my);
      gl.uniform3fv(U.a, cur.a);
      gl.uniform3fv(U.b, cur.b);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    const onLost = ev => { ev.preventDefault(); cancelAnimationFrame(raf); setFallback(true); };
    el.addEventListener('webglcontextlost', onLost);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerleave', onLeave);
      el.removeEventListener('webglcontextlost', onLost);
      gl.deleteBuffer(buf);
      gl.deleteProgram(program);
    };
  }, [size]);

  if (fallback) return <Orb state={state} size={size} />;
  return <canvas ref={canvas} aria-hidden className="pointer-events-none" />;
}
