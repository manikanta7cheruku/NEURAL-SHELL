/**
 * Fallback for the Feedback page when Seven's backend can't take the report
 * (still starting, or an older backend without /api/feedback). The page then
 * posts straight to the Google Form. Keep these in sync with FORM_URL and
 * FIELDS in backend/routes/feedback.py.
 */
const FORM_ID = '1FAIpQLSdwmjvMIDzJRGo2xTTqdcvUgzCiDzQV2wzsOBAZhd6Ea2lIuw';
const FIELDS = { email: 'entry.1666026261', message: 'entry.480930978' };

/** The form has only Email and Message, so the category and severity lead the message: "[Bug Report, Critical]". */
export const composeMessage = ({ category, severity, details, name }) =>
  `[${[category, severity && severity.toUpperCase() !== 'N/A' ? severity : ''].filter(Boolean).join(', ')}]${name ? `\nFrom: ${name}` : ''}\n\n${details}`;

/** Resolves when the request left the app. The browser can't read Google's reply, so delivery isn't confirmed. */
export async function sendDirect({ category, severity, details, email, name }) {
  const body = new URLSearchParams({
    [FIELDS.email]: email || 'anonymous',
    [FIELDS.message]: composeMessage({ category, severity, details, name }),
  });
  await fetch(`https://docs.google.com/forms/d/e/${FORM_ID}/formResponse`, { method: 'POST', mode: 'no-cors', body });
}
