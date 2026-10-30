/**
 * CompanionSettings: how Seven reaches out. Opens from the gear in Seven's chat thread, and nowhere else: quiet hours,
 * pace, voice and topics are chosen here. Every control saves the moment it changes.
 */
import { Moon } from 'lucide-react';
import useCompanion from '../stores/useCompanion';
import { Sheet, Row, Toggle, Segmented, Input, Button } from './ui';
import { cx } from '../lib/cx';

const PACES = [
  { value: 'auto', label: 'Natural', hint: 'A different number each day, 3, 5 or 7, a few minutes apart. Like a friend, not a timer.' },
  { value: 'calm', label: 'Calm', hint: 'About 3 a day, well spaced.' },
  { value: 'lively', label: 'Lively', hint: 'Up to 7 a day, close together.' },
];

function Group({ title, children }) {
  return (
    <section className="mb-5">
      <h3 className="px-4 pb-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-s-text-4">{title}</h3>
      <div className="divide-y divide-s-border/70 rounded-lg border border-s-border bg-s-bg">{children}</div>
    </section>
  );
}

function until(iso) {
  if (!iso) return '';
  const d = new Date(iso.replace(' ', 'T'));
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export default function CompanionSettings({ open, onClose }) {
  const { settings: s, save, snoozedUntil, snooze, today, quietNow } = useCompanion();
  if (!s) return null;
  const pace = PACES.find(p => p.value === s.pace) || PACES[0];

  return (
    <Sheet open={open} onClose={onClose} width={440} title="How Seven reaches out"
           description="Seven writes to you here like a friend would. You decide how much, and when it should be quiet.">
      <Group title="Messages">
        <Row label="Seven can message me" description="It asks about you, tells you about itself, and follows up on what you shared.">
          <Toggle checked={s.enabled} onChange={v => save({ enabled: v })} label="Seven can message me" />
        </Row>
        <Row label="Say them aloud" description="Only when you are idle: paused for a moment, and not in the middle of talking to Seven. They are always written here too.">
          <Toggle checked={s.voice} onChange={v => save({ voice: v })} disabled={!s.enabled} label="Say messages aloud" />
        </Row>
      </Group>

      <Group title="How often">
        <div className={cx('px-4 py-3', !s.enabled && 'opacity-50')}>
          <Segmented value={s.pace} options={PACES.map(p => ({ value: p.value, label: p.label }))} onChange={v => s.enabled && save({ pace: v })} />
          <p className="mt-2 text-[11.5px] leading-relaxed text-s-text-3">{pace.hint}</p>
          {today && <p className="mt-1.5 text-[11.5px] tabular-nums text-s-text-4">Today: {today.sent} so far, about {today.target} planned.</p>}
        </div>
      </Group>

      <Group title="Quiet hours">
        <Row label="Stay quiet at night" description="No messages and no voice between these times.">
          <Toggle checked={s.quiet.enabled} onChange={v => save({ quiet: { enabled: v } })} disabled={!s.enabled} label="Quiet hours" />
        </Row>
        {s.quiet.enabled && (
          <div className="flex items-center gap-3 px-4 py-3">
            <label className="flex items-center gap-2 text-[12px] text-s-text-3">From
              <Input type="time" value={s.quiet.start} onChange={e => e.target.value && save({ quiet: { start: e.target.value } })} aria-label="Quiet hours start" className="w-[110px]" />
            </label>
            <label className="flex items-center gap-2 text-[12px] text-s-text-3">to
              <Input type="time" value={s.quiet.end} onChange={e => e.target.value && save({ quiet: { end: e.target.value } })} aria-label="Quiet hours end" className="w-[110px]" />
            </label>
          </div>
        )}
        {quietNow && <p className="flex items-center gap-1.5 px-4 py-2.5 text-[11.5px] text-s-text-3"><Moon size={12} /> It is quiet hours now.</p>}
      </Group>

      <Group title="What Seven talks about">
        <Row label="About you" description="Getting to know you: what you do, what you like, what you are working towards.">
          <Toggle checked={s.topics.you} onChange={v => save({ topics: { you: v } })} disabled={!s.enabled} label="About you" />
        </Row>
        <Row label="About Seven" description="What Seven is becoming, how it works, features worth trying.">
          <Toggle checked={s.topics.seven} onChange={v => save({ topics: { seven: v } })} disabled={!s.enabled} label="About Seven" />
        </Row>
        <Row label="Did you know" description="A small, true fact now and then, with a question.">
          <Toggle checked={s.topics.facts} onChange={v => save({ topics: { facts: v } })} disabled={!s.enabled} label="Did you know" />
        </Row>
      </Group>

      <Group title="Need some space?">
        <div className="flex flex-wrap items-center gap-2 px-4 py-3">
          {snoozedUntil ? (
            <>
              <span className="text-[12px] text-s-text-2">Quiet until {until(snoozedUntil)}.</span>
              <Button size="sm" variant="secondary" onClick={() => snooze(0)}>Resume now</Button>
            </>
          ) : (
            <>
              <Button size="sm" variant="secondary" onClick={() => snooze(60)}>Quiet for an hour</Button>
              <Button size="sm" variant="secondary" onClick={() => snooze(Math.max(60, (24 * 60) - (new Date().getHours() * 60 + new Date().getMinutes())))}>Rest of today</Button>
            </>
          )}
        </div>
        <p className="px-4 pb-3 text-[11.5px] leading-relaxed text-s-text-4">
          You can also just tell Seven in the chat: "not now" and it will give you a few hours.
        </p>
      </Group>
    </Sheet>
  );
}
