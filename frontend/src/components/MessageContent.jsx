/**
 * MessageContent.jsx
 * Dependency-free renderer for assistant text: fenced code, tables, headings, bullet and numbered lists,
 * inline code, bold, page citations like (p. 4), and paragraphs. React escapes everything, so model output
 * can never inject markup.
 */
import { useState } from 'react';
import { Check, Copy } from 'lucide-react';

function CodeBlock({ code, lang }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="my-2.5 overflow-hidden rounded-lg border border-s-border bg-s-bg">
      <div className="flex items-center justify-between border-b border-s-border bg-s-card px-3 h-7 text-[11px] text-s-text-3">
        <span>{lang || 'code'}</span>
        <button
          onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
          className="flex items-center gap-1 transition-colors hover:text-s-text"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}{copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto whitespace-pre p-3 font-mono text-[12px] leading-relaxed text-s-text-2">{code}</pre>
    </div>
  );
}

const CITE = /\((?:[^()]*?, )?(?:p{1,2}\.|pages?|slides?|sheet) ?[\w\s.,–-]{1,24}\)/;
const INLINE = new RegExp(`(\`[^\`]+\`|\\*\\*[^*]+\\*\\*|${CITE.source})`, 'g');

function Inline({ text }) {
  const parts = text.split(INLINE).filter(Boolean);
  return parts.map((p, i) => {
    if (p.startsWith('`')) return <code key={i} className="rounded bg-s-card-h px-1 py-px font-mono text-[12px] text-s-text">{p.slice(1, -1)}</code>;
    if (p.startsWith('**')) return <strong key={i} className="font-semibold text-s-text">{p.slice(2, -2)}</strong>;
    if (CITE.test(p) && p.startsWith('(')) {
      return <span key={i} className="mx-0.5 whitespace-nowrap rounded border border-s-border px-1 py-px align-[1px] font-mono text-[10.5px] text-s-text-3">{p.slice(1, -1)}</span>;
    }
    return <span key={i}>{p}</span>;
  });
}

const cells = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
const isRule = line => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);

function Table({ lines }) {
  const head = cells(lines[0]);
  const body = lines.slice(isRule(lines[1] || '') ? 2 : 1).filter(l => !isRule(l)).map(cells);
  return (
    <div className="my-1 overflow-x-auto rounded-lg border border-s-border">
      <table className="w-full border-collapse text-left text-[12.5px]">
        <thead className="bg-s-card">
          <tr>{head.map((h, i) => <th key={i} className="border-b border-s-border px-3 py-2 font-semibold text-s-text"><Inline text={h} /></th>)}</tr>
        </thead>
        <tbody>
          {body.map((row, r) => (
            <tr key={r} className="border-b border-s-border last:border-0 even:bg-s-card/40">
              {head.map((_, c) => <td key={c} className="px-3 py-1.5 align-top text-s-text-2"><Inline text={row[c] || ''} /></td>)}
            </tr>))}
        </tbody>
      </table>
    </div>
  );
}

// Splits a text block into tables, headings, lists and paragraphs, line by line, so a table directly under a
// sentence (no blank line between) still renders as a table.
function blocksOf(body) {
  const out = [];
  const lines = body.split('\n');
  let i = 0;
  const push = (type, ls) => out.push({ type, lines: ls });
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }
    if (line.includes('|') && isRule(lines[i + 1] || '')) {
      const ls = [line];
      i += 1;
      while (i < lines.length && lines[i].includes('|')) { ls.push(lines[i]); i += 1; }
      push('table', ls); continue;
    }
    if (/^#{1,4}\s+/.test(line)) { push('heading', [line.replace(/^#{1,4}\s+/, '')]); i += 1; continue; }
    const kind = /^\s*[-*•]\s+/.test(line) ? 'ul' : /^\s*\d+[.)]\s+/.test(line) ? 'ol' : 'p';
    const ls = [];
    while (i < lines.length && lines[i].trim() && !(lines[i].includes('|') && isRule(lines[i + 1] || ''))
           && !/^#{1,4}\s+/.test(lines[i])) {
      const k = /^\s*[-*•]\s+/.test(lines[i]) ? 'ul' : /^\s*\d+[.)]\s+/.test(lines[i]) ? 'ol' : 'p';
      if (k !== kind && !(kind !== 'p' && /^\s{2,}\S/.test(lines[i]))) break;
      ls.push(lines[i]); i += 1;
    }
    push(kind, ls);
  }
  return out;
}

export default function MessageContent({ text }) {
  const clean = (text || '').replace(/###[A-Z_]+:[^\n#]*/g, '').trim();
  if (!clean) return null;
  const parts = [];
  const re = /```(\w*)\n?([\s\S]*?)```/g;
  let last = 0;
  let m;
  while ((m = re.exec(clean)) !== null) {
    if (m.index > last) parts.push({ type: 'text', body: clean.slice(last, m.index) });
    parts.push({ type: 'code', lang: m[1], body: m[2].replace(/\n$/, '') });
    last = m.index + m[0].length;
  }
  if (last < clean.length) parts.push({ type: 'text', body: clean.slice(last) });

  return (
    <div className="space-y-2.5 text-[13px] leading-[1.65] text-s-text-2">
      {parts.map((part, i) => {
        if (part.type === 'code') return <CodeBlock key={i} code={part.body} lang={part.lang} />;
        return blocksOf(part.body).map((b, j) => {
          const key = `${i}-${j}`;
          if (b.type === 'table') return <Table key={key} lines={b.lines} />;
          if (b.type === 'heading') return <h4 key={key} className="pt-1 text-[13px] font-semibold text-s-text"><Inline text={b.lines[0]} /></h4>;
          if (b.type === 'ul') {
            return <ul key={key} className="list-disc space-y-1 pl-5 marker:text-s-text-4">{b.lines.map((l, k) => <li key={k}><Inline text={l.replace(/^\s*[-*•]\s+/, '')} /></li>)}</ul>;
          }
          if (b.type === 'ol') {
            return <ol key={key} className="list-decimal space-y-1 pl-5 marker:text-s-text-4">{b.lines.map((l, k) => <li key={k}><Inline text={l.replace(/^\s*\d+[.)]\s+/, '')} /></li>)}</ol>;
          }
          return <p key={key} className="whitespace-pre-wrap"><Inline text={b.lines.join('\n')} /></p>;
        });
      })}
    </div>
  );
}
