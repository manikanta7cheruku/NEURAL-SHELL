/**
 * MessageContent.jsx
 * Dependency-free renderer for assistant text: fenced code blocks, inline code,
 * bold, bullet and numbered lists, and paragraphs. React escapes everything, so
 * model output can never inject markup.
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

function Inline({ text }) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((p, i) => {
    if (p.startsWith('`')) return <code key={i} className="rounded bg-s-card-h px-1 py-px font-mono text-[12px] text-s-text">{p.slice(1, -1)}</code>;
    if (p.startsWith('**')) return <strong key={i} className="font-semibold text-s-text">{p.slice(2, -2)}</strong>;
    return <span key={i}>{p}</span>;
  });
}

export default function MessageContent({ text }) {
  const clean = (text || '').replace(/###[A-Z_]+:[^\n#]*/g, '').trim();
  if (!clean) return null;
  const blocks = [];
  const re = /```(\w*)\n?([\s\S]*?)```/g;
  let last = 0;
  let m;
  while ((m = re.exec(clean)) !== null) {
    if (m.index > last) blocks.push({ type: 'text', body: clean.slice(last, m.index) });
    blocks.push({ type: 'code', lang: m[1], body: m[2].replace(/\n$/, '') });
    last = m.index + m[0].length;
  }
  if (last < clean.length) blocks.push({ type: 'text', body: clean.slice(last) });

  return (
    <div className="space-y-2.5 text-[13px] leading-[1.65] text-s-text-2">
      {blocks.map((b, i) => {
        if (b.type === 'code') return <CodeBlock key={i} code={b.body} lang={b.lang} />;
        return b.body.split(/\n{2,}/).map((para, j) => {
          const lines = para.split('\n');
          if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
            return <ul key={`${i}-${j}`} className="list-disc space-y-1 pl-5 marker:text-s-text-4">{lines.map((l, k) => <li key={k}><Inline text={l.replace(/^\s*[-*]\s+/, '')} /></li>)}</ul>;
          }
          if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) {
            return <ol key={`${i}-${j}`} className="list-decimal space-y-1 pl-5 marker:text-s-text-4">{lines.map((l, k) => <li key={k}><Inline text={l.replace(/^\s*\d+[.)]\s+/, '')} /></li>)}</ol>;
          }
          return <p key={`${i}-${j}`} className="whitespace-pre-wrap"><Inline text={para} /></p>;
        });
      })}
    </div>
  );
}
