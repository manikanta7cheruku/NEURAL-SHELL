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
    <div className="my-2 rounded-lg border border-white/8 bg-black/40 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1 border-b border-white/6 text-[9px] text-white/35 font-mono">
        <span>{lang || 'code'}</span>
        <button
          onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
          className="flex items-center gap-1 hover:text-white/70 transition-colors"
        >
          {copied ? <Check size={10} /> : <Copy size={10} />}{copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="p-3 text-[11px] leading-relaxed text-white/75 font-mono overflow-x-auto whitespace-pre">{code}</pre>
    </div>
  );
}

function Inline({ text }) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((p, i) => {
    if (p.startsWith('`')) return <code key={i} className="px-1 py-px rounded bg-white/8 text-[11px] font-mono text-s-accent/90">{p.slice(1, -1)}</code>;
    if (p.startsWith('**')) return <strong key={i} className="font-semibold text-white/90">{p.slice(2, -2)}</strong>;
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
    <div className="text-[12.5px] leading-relaxed text-white/75 space-y-2">
      {blocks.map((b, i) => {
        if (b.type === 'code') return <CodeBlock key={i} code={b.body} lang={b.lang} />;
        return b.body.split(/\n{2,}/).map((para, j) => {
          const lines = para.split('\n');
          if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
            return <ul key={`${i}-${j}`} className="list-disc pl-5 space-y-0.5">{lines.map((l, k) => <li key={k}><Inline text={l.replace(/^\s*[-*]\s+/, '')} /></li>)}</ul>;
          }
          if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) {
            return <ol key={`${i}-${j}`} className="list-decimal pl-5 space-y-0.5">{lines.map((l, k) => <li key={k}><Inline text={l.replace(/^\s*\d+[.)]\s+/, '')} /></li>)}</ol>;
          }
          return <p key={`${i}-${j}`} className="whitespace-pre-wrap"><Inline text={para} /></p>;
        });
      })}
    </div>
  );
}
