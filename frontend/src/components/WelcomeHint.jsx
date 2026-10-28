/**
 * WelcomeHint: after the welcome card is closed, a quiet clue stays on the home screen and the Overview page.
 * It names the next thing to try (the first command) and, once that's done, simply points back to the guide.
 * Clicking opens the welcome card; "Hide this hint" inside the card removes it for good.
 */
import useStatus from '../stores/useStatus';
import { cx } from '../lib/cx';

export const FIRST_COMMAND = 'Hey Seven, set volume to 50';

export default function WelcomeHint({ className }) {
  const welcome = useStatus(s => s.welcome);
  if (!welcome?.tour_done || welcome.hint_dismissed) return null;
  const done = !!welcome.first_command;
  return (
    <button onClick={() => window.dispatchEvent(new Event('seven:welcome'))}
            className={cx('page-in group/h flex h-8 max-w-full items-center gap-2.5 rounded-full border border-s-border bg-s-surface/80 px-3.5 text-[12px] backdrop-blur-md',
                          'transition-colors duration-200 hover:border-s-accent/50', className)}>
      <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', done ? 'bg-s-text-4' : 'animate-pulse bg-s-accent')} />
      <span className="min-w-0 truncate text-s-text-2">
        {done ? 'Welcome guide: tips and feedback' : <>Try it: say <span className="text-s-text">“{FIRST_COMMAND}”</span></>}
      </span>
      <span className="shrink-0 text-s-text-4 transition-colors group-hover/h:text-s-accent-h">Open guide</span>
    </button>
  );
}
