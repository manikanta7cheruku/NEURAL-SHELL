/**
 * Feedback: sends a report to the team's Google Form (responses go to a Google
 * Sheet) through the backend, which only reports "sent" when Google accepted it
 * and keeps offline reports in a queue that is retried automatically.
 * Form settings live in backend/routes/feedback.py.
 */
/* SEVEN_DOC {"purpose": "Report a bug, request a feature or tell the team what to improve",
              "keywords": ["feedback", "bug", "report", "issue", "feature request", "support", "contact"]} */
import { useEffect, useState } from 'react';
import { Bug, Lightbulb, Palette, Gauge, MessageCircle, Check, CloudOff, Send } from 'lucide-react';
import api from '../api';
import useConfig from '../stores/useConfig';
import { PageShell, Section, Row, Body, Button, Input, Segmented } from '../components/ui';
import { cx } from '../lib/cx';
import { toast } from '../lib/toast';

const CATEGORIES = [
  { id: 'Bug Report', label: 'Bug', hint: 'Something is broken', icon: Bug },
  { id: 'Feature Request', label: 'Idea', hint: 'Something new', icon: Lightbulb },
  { id: 'UI/UX', label: 'Design', hint: 'Looks or feels off', icon: Palette },
  { id: 'Performance', label: 'Speed', hint: 'Slow or laggy', icon: Gauge },
  { id: 'Other', label: 'Other', hint: 'Anything else', icon: MessageCircle },
];
const SEVERITY = ['Low', 'Medium', 'High', 'Critical'].map(v => ({ value: v, label: v }));

export default function Feedback() {
  const { config } = useConfig();
  const [category, setCategory] = useState('');
  const [severity, setSeverity] = useState('Medium');
  const [details, setDetails] = useState('');
  const [email, setEmail] = useState(config?.email || '');
  const [appInfo, setAppInfo] = useState(true);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);         // 'sent' | 'queued'
  const [status, setStatus] = useState(null);

  useEffect(() => {
    api.post('/feedback/retry').then(r => setStatus(r.data)).catch(() => {});
  }, []);

  const bug = category === 'Bug Report' || category === 'Performance';
  const ready = category && details.trim().length >= 5 && !sending;

  const send = async () => {
    if (!ready) return;
    setSending(true);
    try {
      const r = await api.post('/feedback', { category, severity: bug ? severity : '', details: details.trim(),
                                              email: email.trim(), include_app_info: appInfo });
      setResult(r.data.sent ? 'sent' : 'queued');
      setStatus(s => ({ ...(s || {}), queued: r.data.queued }));
      setDetails('');
      setCategory('');
    } catch (e) {
      toast.error("Couldn't send your feedback", e?.response?.data?.detail || 'Check that Seven is running, then try again.');
    }
    setSending(false);
  };

  return (
    <PageShell title="Feedback" description="Tell the team what's broken or what would make Seven better. Every report is read.">
      <div className="mx-auto max-w-[720px] space-y-4 px-6 py-5">
        {result && (
          <div className="page-in flex items-start gap-3 rounded-lg border border-s-border bg-s-surface px-4 py-3 shadow-[var(--s-shadow)]">
            <span className={cx('mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                                result === 'sent' ? 'bg-s-green/15 text-s-green' : 'bg-s-card-h text-s-text-2')}>
              {result === 'sent' ? <Check size={14} /> : <CloudOff size={13} />}
            </span>
            <div className="flex-1">
              <p className="text-[13px] font-medium text-s-text">{result === 'sent' ? 'Thanks, your feedback was sent.' : 'Saved. It will send when you are online.'}</p>
              <p className="mt-0.5 text-[12px] text-s-text-3">
                {result === 'sent' ? 'If you left an email, the team may reply there.' : 'Seven keeps it on this computer and retries automatically.'}
              </p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => setResult(null)}>Send another</Button>
          </div>
        )}

        {status && !status.configured && (
          <div className="rounded-lg border border-s-yellow/30 bg-s-yellow/5 px-4 py-3 text-[12px] text-s-text-2">
            Feedback isn't connected to a form yet. The form settings are in backend/routes/feedback.py.
          </div>
        )}

        {!result && (
          <div className="page-in space-y-4">
            <Section title="What is it about?">
              <Body>
                <div role="radiogroup" aria-label="Category" className="grid grid-cols-5 gap-2">
                  {CATEGORIES.map(c => {
                    const on = category === c.id;
                    return (
                      <button key={c.id} role="radio" aria-checked={on} onClick={() => setCategory(c.id)}
                              className={cx('flex flex-col items-start rounded-lg border px-3 py-2.5 text-left transition-all duration-200',
                                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60',
                                            on ? 'border-s-accent bg-s-accent/5 ring-1 ring-s-accent' : 'border-s-border hover:border-s-border-l hover:bg-s-card')}>
                        <c.icon size={16} className={on ? 'text-s-accent-h' : 'text-s-text-3'} />
                        <span className="mt-2 text-[12.5px] font-medium text-s-text">{c.label}</span>
                        <span className="text-[11px] text-s-text-3">{c.hint}</span>
                      </button>
                    );
                  })}
                </div>
              </Body>
              {bug && (
                <Row label="How bad is it?" description="Critical means a crash or lost data.">
                  <Segmented value={severity} onChange={setSeverity} options={SEVERITY} />
                </Row>
              )}
            </Section>

            <Section title="Details">
              <Body>
                <textarea value={details} onChange={e => setDetails(e.target.value)} rows={6} aria-label="Details"
                          placeholder={bug ? 'What happened, what you expected, and the steps to make it happen again.' : 'Describe your idea or what you noticed.'}
                          className="w-full resize-y rounded-md border border-s-border bg-s-bg px-3 py-2 text-[13px] leading-relaxed text-s-text
                                     placeholder:text-s-text-4 focus:border-s-accent focus:ring-2 focus:ring-s-accent/20" />
              </Body>
              <Row label="Email" description="Optional. Only if you'd like a reply.">
                <Input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" className="w-64" aria-label="Email" />
              </Row>
              <Row label="Include app details" description="Adds your Seven version and Windows version so bugs are easier to reproduce. Nothing else is sent.">
                <input type="checkbox" checked={appInfo} onChange={e => setAppInfo(e.target.checked)} aria-label="Include app details"
                       className="h-4 w-4 accent-[var(--color-s-accent)]" />
              </Row>
            </Section>

            <div className="flex items-center justify-between">
              <p className="text-[11.5px] text-s-text-4">
                {status?.queued ? `${status.queued} earlier report${status.queued > 1 ? 's' : ''} waiting to send. ` : ''}
                Sent to the Seven team through Google Forms.
              </p>
              <Button variant="primary" icon={Send} onClick={send} loading={sending} disabled={!ready}>Send feedback</Button>
            </div>
          </div>
        )}
      </div>
    </PageShell>
  );
}
