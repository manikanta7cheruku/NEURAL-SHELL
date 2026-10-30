/**
 * CompanionIntro: what Seven's own thread is, shown while it is still empty. Short, warm, and honest about what Seven will
 * and will not do, with the two things worth doing first: ask me something, and set how Seven reaches out.
 */
import { Sparkles, SlidersHorizontal } from 'lucide-react';
import Mark from './Mark';
import { Button } from './ui';

export default function CompanionIntro({ onAsk, onSettings, name }) {
  return (
    <div className="mx-auto flex max-w-[460px] flex-col items-center pt-[8vh] text-center">
      <Mark size={52} />
      <h2 className="mt-5 text-[20px] font-light tracking-[-0.01em] text-s-text">{name ? `Hi ${name}, this is our space.` : 'This is our space.'}</h2>
      <p className="mt-2 text-[13px] leading-relaxed text-s-text-3">
        Seven will write to you here the way a friend does: now and then, about you, about itself and what it is becoming,
        and about small things worth knowing. You can answer, ask it anything about Seven, or ignore it. Nothing is ever urgent.
      </p>
      <ul className="mt-5 space-y-2 text-left text-[12.5px] text-s-text-2">
        {['Messages are written here, and said aloud only when you are idle.',
          'What you tell Seven is remembered, and you can see and change it any time in Memory.',
          'Say "not now" and Seven gives you space. Quiet hours are in the settings.'].map(t => (
          <li key={t} className="flex gap-2.5"><span aria-hidden className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-s-text-4" />{t}</li>))}
      </ul>
      <div className="mt-7 flex items-center gap-2">
        <Button variant="primary" icon={Sparkles} onClick={onAsk}>Ask me something</Button>
        <Button variant="secondary" icon={SlidersHorizontal} onClick={onSettings}>How Seven reaches out</Button>
      </div>
    </div>
  );
}
