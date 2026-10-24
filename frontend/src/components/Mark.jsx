/**
 * Seven's mark: the Roman numeral VII set in a small tile. Used for the app header, Seven's replies and empty
 * states, in place of a plain "7".
 */
import { cx } from '../lib/cx';

export default function Mark({ size = 26, className, tone = 'tile' }) {
  const font = Math.round(size * 0.4);
  return (
    <span aria-hidden="true"
          className={cx('inline-flex shrink-0 select-none items-center justify-center rounded-[28%] font-semibold',
                        tone === 'tile' && 'border border-s-border-l bg-s-card text-s-text',
                        tone === 'accent' && 'bg-s-accent text-s-on-accent',
                        className)}
          style={{ width: size, height: size, fontSize: font, letterSpacing: '0.06em',
                   fontFamily: "'Cormorant Garamond', 'Iowan Old Style', Georgia, 'Times New Roman', serif" }}>
      VII
    </span>
  );
}
