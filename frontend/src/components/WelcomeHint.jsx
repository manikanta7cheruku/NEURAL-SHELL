/**
 * WelcomeHint: a quiet pill on the home screen and the Overview page, for everyone, that opens the welcome card
 * (what Seven is about, where it is going, and a way to give feedback). "Hide the home hint" in the card removes it;
 * the card stays reachable from the Welcome guide link in the home footer, Guide and Ctrl+K.
 */
import useStatus from '../stores/useStatus';
import { cx } from '../lib/cx';

export default function WelcomeHint({ className }) {
  const hidden = useStatus(s => !!s.welcome?.hint_dismissed);
  const touring = useStatus(s => !!s.tour?.step && s.tour.step !== 'card');
  if (hidden || touring) return null;
  return (
    <button onClick={() => window.dispatchEvent(new Event('seven:welcome'))}
            className={cx('page-in group/h flex h-8 max-w-full items-center gap-2.5 rounded-full border border-s-border bg-s-surface/80 px-3.5 text-[12px] backdrop-blur-md',
                          'transition-colors duration-200 hover:border-s-accent/50', className)}>
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-s-accent" />
      <span className="min-w-0 truncate text-s-text-2">Seven beta: where it is going, and how to tell us what you think</span>
      <span className="shrink-0 text-s-text-4 transition-colors group-hover/h:text-s-accent-h">Open</span>
    </button>
  );
}
