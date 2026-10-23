/**
 * Fallback for the Feedback page when Seven's backend can't take the report
 * (still starting, or an older backend without /api/feedback). The page then
 * posts straight to the Google Form. Keep these in sync with FORM_URL and
 * FIELDS in backend/routes/feedback.py.
 */
const FORM_ID = '1FAIpQLScbQrtJLGQR0fVB2PkG_7uM8xcrRMSF7D9184Fq0X-L1tKnoA';
const FIELDS = { category: 'entry.1403735424', severity: 'entry.813819414', details: 'entry.2134832696', email: 'entry.1297852434' };

/** Resolves when the request left the app. The browser can't read Google's reply, so delivery isn't confirmed. */
export async function sendDirect({ category, severity, details, email }) {
  const body = new URLSearchParams({
    [FIELDS.category]: category,
    [FIELDS.severity]: severity || 'N/A',
    [FIELDS.details]: details,
    [FIELDS.email]: email || 'anonymous',
  });
  await fetch(`https://docs.google.com/forms/d/e/${FORM_ID}/formResponse`, { method: 'POST', mode: 'no-cors', body });
}
