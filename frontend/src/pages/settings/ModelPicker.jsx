/**
 * Model picker for Settings > Brain.
 *
 * A compact list of every model in the catalog (brain_modules/model_catalog.py
 * via GET /api/models): name, size and status on one line. Selecting a model
 * opens a window inside the app with what it is good at, whether it suits this
 * PC, and the actions: download (with live progress), use, or remove.
 * Switching saves brain.model_name and applies from Seven's next message.
 */
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronRight, Download, Loader2, Trash2, Sparkles, X, Cpu, HardDrive, Gauge, MessageSquareText } from 'lucide-react';
import api from '../../api';
import { Row, Body, Button, Badge, Toggle } from '../../components/ui';
import { cx } from '../../lib/cx';
import { toast } from '../../lib/toast';

const words = tokens => `${(Math.round((tokens * 0.75) / 100) * 100).toLocaleString()} words`;
const shortParams = p => (p || '').replace(' billion', 'B');

function Status({ m, auto, pulling }) {
  if (pulling) return <span className="font-mono text-[11px] text-s-accent-h">{pulling.progress || 0}%</span>;
  if (m.in_use && !auto) return <Badge tone="accent"><Check size={10} />In use</Badge>;
  if (m.installed) return <Badge>Installed</Badge>;
  if (m.recommended) return <Badge tone="success"><Sparkles size={10} />Best for this PC</Badge>;
  return <Download size={13} className="text-s-text-4 transition-colors group-hover/m:text-s-text-2" />;
}

function ModelWindow({ m, data, auto, pulling, busy, onClose, onDownload, onUse, onRemove }) {
  const titleId = useId();
  const closeRef = useRef(null);
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    const t = setTimeout(() => closeRef.current?.focus(), 30);
    return () => { window.removeEventListener('keydown', onKey); clearTimeout(t); };
  }, [onClose]);

  const inUse = m.in_use && !auto;
  const isPulling = pulling?.model === m.id;
  const hw = data?.hardware || {};
  const need = m.vram <= 2 ? 'Any PC' : `${m.vram} GB graphics or ${m.ram} GB memory`;

  // Rendered into <body>: the Settings page animates its content, which would otherwise trap a fixed window inside it.
  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6" onMouseDown={onClose}>
      <div className="absolute inset-0 bg-[var(--s-scrim)] animate-[fadeIn_120ms_ease-out]" />
      <div role="dialog" aria-modal="true" aria-labelledby={titleId} onMouseDown={e => e.stopPropagation()}
           className="relative w-full max-w-[460px] overflow-hidden rounded-xl border border-s-border bg-s-surface
                      shadow-[var(--s-shadow-raised)] animate-[dialogReveal_160ms_ease-out]">
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div className="min-w-0">
            <h3 id={titleId} className="text-[15px] font-semibold text-s-text">{m.name}</h3>
            <p className="mt-0.5 text-[12px] text-s-text-3">{m.maker} · {m.params} parameters</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {inUse && <Badge tone="accent"><Check size={10} />In use</Badge>}
              {m.recommended && <Badge tone="success"><Sparkles size={10} />Best for this PC</Badge>}
              {m.installed && !inUse && <Badge>Installed</Badge>}
              {!m.fits && <Badge tone="warning">May be slow here</Badge>}
            </div>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label="Close"
                  className="rounded-md p-1 text-s-text-3 transition-colors hover:bg-s-card hover:text-s-text">
            <X size={15} />
          </button>
        </div>

        <div className="space-y-3 px-5 pt-4 text-[12.5px] leading-relaxed">
          <p className="text-s-text-2"><span className="text-s-text">Good at</span> {m.good_at}.</p>
          <p className="text-s-text-2"><span className="text-s-text">Less suited to</span> {m.weak_at}.</p>
          <p className="text-s-text-2"><span className="text-s-text">Best for</span> {m.best_for}.</p>
        </div>

        <div className="mx-5 mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-s-border bg-s-border">
          {[
            [HardDrive, 'Download', `${m.size_gb} GB`],
            [Gauge, 'Speed', m.speed],
            [MessageSquareText, 'Reads at once', `About ${words(m.context)}`],
            [Cpu, 'Needs', need],
          ].map(([I, k, v]) => (
            <div key={k} className="bg-s-surface px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-[11px] text-s-text-4"><I size={11} />{k}</div>
              <div className="mt-0.5 text-[12.5px] text-s-text">{v}</div>
            </div>
          ))}
        </div>

        <p className={cx('mx-5 mt-3 text-[11.5px]', m.fits ? 'text-s-text-3' : 'text-s-yellow')}>
          {m.fits
            ? `Runs well on this PC${hw.gpu ? ` (${hw.gpu.replace(/NVIDIA GeForce /, '')}, ${hw.vram_gb} GB)` : ''}.`
            : `This PC has ${hw.has_gpu ? `${hw.vram_gb} GB of graphics memory` : 'no dedicated graphics card'} and ${Math.round(hw.ram_gb || 0)} GB of memory, so replies may be slow.`}
        </p>

        {isPulling && (
          <div className="mx-5 mt-4">
            <div className="h-1.5 overflow-hidden rounded-full bg-s-card-h">
              <div className="h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${pulling.progress || 0}%` }} />
            </div>
            <div className="mt-1.5 flex justify-between font-mono text-[10.5px] text-s-text-4">
              <span className="truncate">{pulling.current || 'Starting download'}</span>
              <span>{pulling.progress || 0}%</span>
            </div>
            <p className="mt-1 text-[11px] text-s-text-4">You can close this window. The download keeps going.</p>
          </div>
        )}

        <div className="mt-5 flex items-center justify-between gap-2 border-t border-s-border bg-s-card/40 px-5 py-3.5">
          <div>
            {m.installed && !inUse && !m.in_use && (
              <Button variant="ghost" icon={busy ? undefined : Trash2} loading={busy} onClick={() => onRemove(m)}
                      className="text-s-text-3 hover:text-s-red">Remove</Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {inUse && <span className="text-[12px] text-s-text-3">Seven is using this model</span>}
            {m.installed && !inUse && <Button variant="primary" onClick={() => onUse(m.id)}>Use this model</Button>}
            {!m.installed && (
              <Button variant="primary" icon={isPulling ? undefined : Download} loading={isPulling}
                      disabled={(!!pulling && !isPulling) || !data?.ollama_running} onClick={() => onDownload(m)}>
                {isPulling ? 'Downloading' : `Download ${m.size_gb} GB`}
              </Button>
            )}
          </div>
        </div>
        {!m.installed && pulling && !isPulling && (
          <p className="px-5 pb-3 text-[11px] text-s-text-4">Another model is downloading. This one can start when it finishes.</p>
        )}
      </div>
    </div>,
    document.body,
  );
}

export default function ModelPicker({ value, onChange }) {
  const [data, setData] = useState(null);
  const [pull, setPull] = useState(null);
  const [busy, setBusy] = useState('');
  const [open, setOpen] = useState(null);
  const poll = useRef(null);

  const load = useCallback(() => {
    api.get('/models').then(r => { setData(r.data); setPull(r.data.pull); })
      .catch(() => setData({ ollama_running: false, models: [], other_installed: [] }));
  }, []);

  useEffect(() => { load(); return () => clearInterval(poll.current); }, [load]);

  // A download that was started earlier (or from another screen) keeps updating here too.
  useEffect(() => {
    if (pull?.status === 'running' && !poll.current) watchPull(pull.label || pull.model);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pull?.status]);

  const watchPull = name => {
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const { data: st } = await api.get('/models/pull');
        setPull(st);
        if (st.status === 'done' || st.status === 'error') {
          clearInterval(poll.current);
          if (st.status === 'done') { toast.success(`${name} is ready`, 'Open it and choose Use this model to switch.'); load(); }
          else toast.error("The download didn't finish", st.error || 'Check your internet connection and try again.');
        }
      } catch { /* backend busy, keep polling */ }
    }, 1000);
  };

  const download = async m => {
    try {
      await api.post('/models/pull', { name: m.id });
      setPull({ status: 'running', model: m.id, progress: 0 });
      watchPull(m.name);
    } catch (e) {
      toast.error("Couldn't start the download", e?.response?.data?.detail || 'Try again in a moment.');
    }
  };

  const use = async id => {
    await onChange(id);
    setOpen(null);
    load();
  };

  const remove = async m => {
    setBusy(m.id);
    try {
      await api.delete(`/models/${encodeURIComponent(m.id)}`);
      toast.success(`${m.name} removed`, 'The disk space is free again.');
      setOpen(null);
      load();
    } catch (e) {
      toast.error("Couldn't remove it", e?.response?.data?.detail || 'Try again in a moment.');
    }
    setBusy('');
  };

  const auto = (value || 'auto') === 'auto';
  const pulling = pull?.status === 'running' ? pull : null;
  const current = (data?.models || []).find(m => m.id === open);
  const recName = data?.models?.find(m => m.id === data?.recommended?.id)?.name;

  return (
    <>
      <Row label="Choose automatically"
           description={recName ? `Seven uses the best installed model for this PC. For yours, that's ${recName}.` : 'Seven uses the best installed model for this PC.'}>
        <Toggle checked={auto} onChange={on => use(on ? 'auto' : (data?.active || data?.recommended?.id || 'llama3.2:1b'))}
                label="Choose automatically" />
      </Row>

      {pulling && (
        <div className="mx-4 my-3 rounded-lg border border-s-border bg-s-card px-4 py-3" role="status" aria-live="polite">
          <div className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] text-s-text-4">Downloading</div>
              <div className="truncate text-[13px] font-medium text-s-text">
                {pulling.label || pulling.model}
                {pulling.total_gb ? <span className="ml-2 text-[11.5px] font-normal text-s-text-4">{pulling.total_gb} GB</span> : null}
              </div>
            </div>
            <span className="font-mono text-[12px] tabular-nums text-s-accent-h">{pulling.progress || 0}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-s-card-h">
            <div className="h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${pulling.progress || 0}%` }} />
          </div>
          <p className="mt-1.5 truncate text-[11px] tabular-nums text-s-text-4">{pulling.current || 'Starting the download'}</p>
        </div>
      )}

      {data && !data.ollama_running && (
        <Body className="text-[12px] text-s-yellow">Ollama isn't running, so models can't be listed or downloaded. Start Ollama, then come back.</Body>
      )}

      <div className="divide-y divide-s-border/70">
        {(data?.models || []).map(m => (
          <button key={m.id} onClick={() => setOpen(m.id)}
                  className="group/m flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-s-card/60 focus-visible:bg-s-card/60 focus-visible:outline-none">
            <span className={cx('flex h-7 w-7 shrink-0 items-center justify-center rounded-md border font-mono text-[10.5px]',
                                m.in_use && !auto ? 'border-s-accent/40 bg-s-accent/10 text-s-accent-h' : 'border-s-border bg-s-card text-s-text-3')}>
              {shortParams(m.params)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[12.5px] font-medium text-s-text">{m.name}</span>
              <span className="block truncate text-[11px] text-s-text-4">{m.size_gb} GB · {m.speed}</span>
            </span>
            <Status m={m} auto={auto} pulling={pulling?.model === m.id ? pulling : null} />
            <ChevronRight size={14} className="shrink-0 text-s-text-4 transition-transform duration-150 group-hover/m:translate-x-0.5" />
          </button>
        ))}
        {(data?.other_installed || []).map(name => {
          const inUse = !auto && (data.active === name || data.configured === name);
          return (
            <div key={name} className="flex items-center gap-3 px-4 py-2.5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-s-border bg-s-card text-s-text-4"><Cpu size={12} /></span>
              <span className="flex-1 text-[12.5px] text-s-text">{name}</span>
              {inUse ? <Badge tone="accent"><Check size={10} />In use</Badge>
                     : <Button size="sm" variant="secondary" onClick={() => use(name)}>Use</Button>}
            </div>
          );
        })}
        {!data && (
          <div className="flex items-center gap-2 px-4 py-3 text-[12px] text-s-text-3"><Loader2 size={13} className="animate-spin" />Checking models</div>
        )}
      </div>

      {current && (
        <ModelWindow m={current} data={data} auto={auto} pulling={pulling} busy={busy === current.id}
                     onClose={() => setOpen(null)} onDownload={download} onUse={use} onRemove={remove} />
      )}
    </>
  );
}
