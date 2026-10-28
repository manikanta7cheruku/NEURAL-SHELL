/**
 * WelcomeHint: a quiet pill on the home screen and the Overview page, for everyone, that opens the welcome card.
 * Until the first command is done it names it as a clue; after that it just points to the guide. "Hide the home hint"
 * in the card removes it; the card stays reachable from the Welcome link in the home footer, Guide and Ctrl+K.
 */
import useStatus from '../stores/useStatus';
import { cx } from '../lib/cx';

export const FIRST_COMMAND = 'Hey Seven, set volume to 50';

export default function WelcomeHint({ className }) {
  const welcome = useStatus(s => s.welcome);
  const touring = useStatus(s => !!s.tour?.step && s.tour.step !== 'card');
  if (welcome?.hint_dismissed || touring) return null;
  const done = !!welcome?.first_command;
  return (
    <button onClick={() => window.dispatchEvent(new Event('seven:welcome'))}
            className={cx('page-in group/h flex h-8 max-w-full items-center gap-2.5 rounded-full border border-s-border bg-s-surface/80 px-3.5 text-[12px] backdrop-blur-md',
                          'transition-colors duration-200 hover:border-s-accent/50', className)}>
      <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', done ? 'bg-s-text-4' : 'animate-pulse bg-s-accent')} />
      <span className="min-w-0 truncate text-s-text-2">
        {done ? 'Welcome guide: tips, feedback and what\u2019s coming' : <>Try it: say <span className="text-s-text">“{FIRST_COMMAND}”</span></>}
      </span>
      <span className="shrink-0 text-s-text-4 transition-colors group-hover/h:text-s-accent-h">Open</span>
    </button>
  );
}
