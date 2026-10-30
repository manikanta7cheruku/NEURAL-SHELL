/**
 * TourLayer: while Seven gives its first-run tour, the thing it is talking about is brightened and the rest of the
 * screen dims (a spotlight). It follows the `tour` step in the status feed (main_modules/startup/tour.py): each
 * step names a data-tour target on the home screen, one for each link along the bottom. A Skip button stops the
 * talking and goes straight to the card. (The steps card, feedback and about belong to WelcomeCard.)
 */
import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api';
import useStatus from '../stores/useStatus';

const NAV_STEPS = ['nav-1', 'nav-2', 'nav-3', 'nav-4', 'nav-5'];
const TARGET = { intro: 'orb', listen: 'listen', mic: 'mic', log: 'voicelog', pages: 'footer', search: 'search', 'welcome-link': 'welcome-link' };
// 'bar' points at the voice bar, which is its own window at the top of the screen: nothing on this page to spotlight.
const STEPS = ['audio', 'intro', 'listen', 'mic', 'log', 'bar', 'pages', ...NAV_STEPS, 'search', 'welcome-link', 'outro'];
// How far the glow stands off its target. Big things get room; the small links along the bottom get a snug fit, so the
// glow hugs one link instead of swallowing its neighbours and spilling out of the bar.
const PAD = { x: 12, y: 12 };
const SNUG = { x: 7, y: 3 };
const PAD_FOR = { footer: { x: 0, y: 0 }, search: SNUG, 'welcome-link': SNUG, nav: SNUG };
const padFor = target => PAD_FOR[target] || (target?.startsWith('nav-') ? PAD_FOR.nav : PAD);

export default function TourLayer() {
  const step = useStatus(s => s.tour?.step);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const target = TARGET[step] || (NAV_STEPS.includes(step) ? step : undefined);
  const [rect, setRect] = useState(null);

  useEffect(() => {
    if (STEPS.includes(step) && pathname !== '/') navigate('/');
  }, [step, pathname, navigate]);

  useEffect(() => {
    if (!target) { setRect(null); return undefined; }
    let raf = 0;
    let last = '';
    const measure = () => {
      const els = [...document.querySelectorAll(`[data-tour="${target}"]`)];
      if (els.length) {
        const rs = els.map(e => e.getBoundingClientRect());
        const pad = padFor(target);
        const left = Math.min(...rs.map(r => r.left)) - pad.x, top = Math.min(...rs.map(r => r.top)) - pad.y;
        const right = Math.max(...rs.map(r => r.right)) + pad.x, bottom = Math.max(...rs.map(r => r.bottom)) + pad.y;
        const next = { left, top, width: right - left, height: bottom - top };
        const key = [next.left, next.top, next.width, next.height].map(Math.round).join(',');
        if (key !== last) { last = key; setRect(next); }
      }
      raf = requestAnimationFrame(measure);
    };
    measure();
    return () => cancelAnimationFrame(raf);
  }, [target, pathname]);

  if (!STEPS.includes(step)) return null;
  return (
    <>
      {rect && (
        <div aria-hidden className={`pointer-events-none fixed z-[900] ${target === 'footer' ? 'rounded-none' : padFor(target) === PAD ? 'rounded-2xl' : 'rounded-lg'} transition-[left,top,width,height] duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]`}
             style={{
               ...rect,
               boxShadow: '0 0 0 9999px var(--s-scrim), 0 0 0 1.5px var(--color-s-accent), 0 0 30px 2px color-mix(in oklab, var(--color-s-accent) 40%, transparent)',
             }} />)}
      <button onClick={() => api.post('/tour/skip').catch(() => {})}
              className="fixed bottom-14 right-6 z-[901] h-8 rounded-full border border-s-border bg-s-surface px-4 text-[12px] text-s-text-2 shadow-[var(--s-shadow-raised)] transition-colors hover:text-s-text">
        Skip tour
      </button>
    </>
  );
}
