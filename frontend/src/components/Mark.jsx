/**
 * Seven's identity, set in Geist (a grotesque made for interfaces, bundled so it works offline).
 *
 *   <Wordmark />  "Seven" for places with room: the title bar, the sidebar header.
 *   <Mark />      an "S" monogram in a tile, for small square places: the collapsed sidebar, Seven's replies.
 *
 * Change the brand here only; every screen uses these two.
 */
import { cx } from '../lib/cx';

const FONT = "'Geist Sans', 'Inter', system-ui, sans-serif";

export function Wordmark({ size = 14, className }) {
  return (
    <span className={cx('select-none font-semibold text-s-text', className)}
          style={{ fontFamily: FONT, fontSize: size, letterSpacing: '-0.025em', lineHeight: 1 }}>
      Seven
    </span>
  );
}

export default function Mark({ size = 26, className, tone = 'tile' }) {
  return (
    <span aria-hidden="true"
          className={cx('relative inline-flex shrink-0 select-none items-center justify-center overflow-hidden font-semibold',
                        tone === 'tile' && 'border border-s-border-l bg-s-card text-s-text',
                        tone === 'accent' && 'bg-s-accent text-s-on-accent',
                        className)}
          style={{ width: size, height: size, borderRadius: Math.round(size * 0.3), fontFamily: FONT,
                   fontSize: Math.round(size * 0.52), letterSpacing: '-0.04em', lineHeight: 1 }}>
      {/* a faint highlight along the top edge, like light on a key */}
      <span className="pointer-events-none absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-white/[0.07] to-transparent" />
      <span className="relative" style={{ transform: 'translateY(-0.02em)' }}>S</span>
    </span>
  );
}
