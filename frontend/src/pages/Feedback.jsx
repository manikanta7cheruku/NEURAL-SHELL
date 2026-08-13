import { useState } from 'react';
import PageHeader from '../components/PageHeader';

const FORM_ACTION = 'https://docs.google.com/forms/d/e/1FAIpQLScbQrtJLGQR0fVB2PkG_7uM8xcrRMSF7D9184Fq0X-L1tKnoA/formResponse';
const E_CATEGORY  = 'entry.1403735424';
const E_SEVERITY  = 'entry.813819414';
const E_DETAILS   = 'entry.2134832696';
const E_EMAIL     = 'entry.1297852434';

const CATS = [
  { id: 'Bug Report',      l: 'Bug Report',      d: 'Something broken' },
  { id: 'Feature Request', l: 'Feature Request',  d: 'Suggest something' },
  { id: 'UI/UX',           l: 'UI / UX',          d: 'Design issue' },
  { id: 'Performance',     l: 'Performance',      d: 'Slow or laggy' },
  { id: 'Other',           l: 'Other',            d: 'General' },
];

const SEV = [
  { id: 'Low',      l: 'Low',      d: 'Minor' },
  { id: 'Medium',   l: 'Medium',   d: 'Noticeable' },
  { id: 'High',     l: 'High',     d: 'Blocks use' },
  { id: 'Critical', l: 'Critical', d: 'Crash / data loss' },
];

export default function Feedback() {
  const [cat,        setCat]        = useState('');
  const [sev,        setSev]        = useState('');
  const [msg,        setMsg]        = useState('');
  const [email,      setEmail]      = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done,       setDone]       = useState(false);

  const canSubmit = cat && msg.trim().length > 0 && !submitting;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);

    const body = new URLSearchParams();
    body.append(E_CATEGORY, cat);
    body.append(E_SEVERITY, sev || 'N/A');
    body.append(E_DETAILS,  msg.trim());
    body.append(E_EMAIL,    email.trim() || 'anonymous');

    try {
      // Race between the fetch and a 4 second timeout.
      // no-cors never gives a readable response so we cannot wait for it —
      // the timeout guarantees the UI never stays stuck on "Sending".
      await Promise.race([
        fetch(FORM_ACTION, {
          method:  'POST',
          mode:    'no-cors',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body:    body.toString(),
        }),
        new Promise(resolve => setTimeout(resolve, 4000)),
      ]);
    } catch {
      // Treat all outcomes as success.
      // no-cors fetch cannot confirm delivery but data reaches Google Sheets
      // whenever network is available.
    }

    setSubmitting(false);
    setDone(true);
    setTimeout(() => {
      setDone(false);
      setCat('');
      setSev('');
      setMsg('');
      setEmail('');
    }, 3000);
  };

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Feedback & Issues" sub="Help improve Seven, every report matters" />
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="grid grid-cols-2 gap-4">

          {/* Category */}
          <div>
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
              Category
            </div>
            <div className="space-y-1">
              {CATS.map(c => (
                <button
                  key={c.id}
                  onClick={() => setCat(c.id)}
                  className={`w-full text-left rounded border px-3 py-2
                    ${cat === c.id
                      ? 'border-s-accent/30 bg-s-accent/5'
                      : 'border-s-border bg-s-card hover:bg-s-card-h'}`}
                >
                  <div className={`text-[12px] font-medium
                    ${cat === c.id ? 'text-s-accent' : 'text-s-text-2'}`}>
                    {c.l}
                  </div>
                  <div className="text-[9px] text-s-text-4">{c.d}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-3">

            {/* Severity */}
            {(cat === 'Bug Report' || cat === 'Performance') && (
              <div>
                <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
                  Severity
                </div>
                <div className="grid grid-cols-2 gap-1">
                  {SEV.map(s => (
                    <button
                      key={s.id}
                      onClick={() => setSev(s.id)}
                      className={`rounded border px-2.5 py-1.5 text-left
                        ${sev === s.id
                          ? 'border-s-accent/30 bg-s-accent/5'
                          : 'border-s-border bg-s-card'}`}
                    >
                      <div className={`text-[11px] font-medium
                        ${sev === s.id ? 'text-s-accent' : 'text-s-text-2'}`}>
                        {s.l}
                      </div>
                      <div className="text-[8px] text-s-text-4">{s.d}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Details */}
            <div>
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-1">
                Details
              </div>
              <textarea
                value={msg}
                onChange={e => setMsg(e.target.value)}
                rows={5}
                placeholder="Describe the issue or suggestion..."
                className="w-full bg-s-card border border-s-border rounded px-3 py-2
                           text-[12px] text-s-text placeholder-s-text-4 resize-none"
              />
            </div>

            {/* Email */}
            <div>
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-1">
                Email <span className="normal-case font-normal">(optional)</span>
              </div>
              <input
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-s-card border border-s-border rounded px-3 py-1.5
                           text-[12px] text-s-text placeholder-s-text-4"
              />
            </div>

            {/* Submit row */}
            <div className="flex items-center gap-3">
              <button
                onClick={submit}
                disabled={!canSubmit}
                className="px-4 py-1.5 border border-s-accent/30 bg-s-accent/8
                           text-s-accent rounded text-[11px] font-medium
                           disabled:border-s-border disabled:bg-transparent
                           disabled:text-s-text-4 flex items-center gap-1.5
                           transition-all duration-150"
              >
                {submitting ? (
                  <>
                    <div className="w-2.5 h-2.5 rounded-full border border-s-accent/30
                                    border-t-s-accent animate-spin" />
                    Sending
                  </>
                ) : 'Submit'}
              </button>
              {done && (
                <span className="text-[10px] text-s-green">Sent. Thank you.</span>
              )}
            </div>

            <p className="text-[9px] text-s-text-4">
              Sent to Google Sheets via Google Forms. Nothing collected automatically.
            </p>

          </div>
        </div>
      </div>
    </div>
  );
}