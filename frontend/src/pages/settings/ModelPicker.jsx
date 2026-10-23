/**
 * Model picker for Settings > Brain. Lists every model in the catalog
 * (brain_modules/model_catalog.py via GET /api/models) with what it is good at,
 * whether it suits this PC, and lets the user download, switch or remove one.
 * Switching saves brain.model_name and applies from Seven's next message.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Download, Loader2, Trash2, Sparkles } from 'lucide-react';
import api from '../../api';
import { Row, Body, Button, Badge, Toggle } from '../../components/ui';
import { cx } from '../../lib/cx';
import { toast } from '../../lib/toast';

export default function ModelPicker({ value, onChange }) {
  const [data, setData] = useState(null);
  const [pull, setPull] = useState(null);
  const [busy, setBusy] = useState('');
  const poll = useRef(null);

  const load = useCallback(() => {
    api.get('/models').then(r => { setData(r.data); setPull(r.data.pull); })
      .catch(() => setData({ ollama_running: false, models: [], other_installed: [] }));
  }, []);

  useEffect(() => { load(); return () => clearInterval(poll.current); }, [load]);

  const watchPull = name => {
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const { data: st } = await api.get('/models/pull');
        setPull(st);
        if (st.status === 'done' || st.status === 'error') {
          clearInterval(poll.current);
          setBusy('');
          if (st.status === 'done') { toast.success(`${name} downloaded`, 'Select Use to switch to it.'); load(); }
          else toast.error("The download didn't finish", st.error || 'Check your internet connection and try again.');
        }
      } catch { /* backend busy, keep polling */ }
    }, 1000);
  };

  const download = async m => {
    setBusy(m.id);
    try {
      await api.post('/models/pull', { name: m.id });
      setPull({ status: 'running', model: m.id, progress: 0 });
      watchPull(m.name);
    } catch (e) {
      setBusy('');
      toast.error("Couldn't start the download", e?.response?.data?.detail || 'Try again in a moment.');
    }
  };

  const use = async id => {
    await onChange(id);
    load();
  };

  const remove = async m => {
    setBusy(m.id || m);
    try {
      await api.delete(`/models/${encodeURIComponent(m.id || m)}`);
      toast.success('Model removed', 'The disk space is free again.');
      load();
    } catch (e) {
      toast.error("Couldn't remove it", e?.response?.data?.detail || 'Try again in a moment.');
    }
    setBusy('');
  };

  const auto = (value || 'auto') === 'auto';
  const pulling = pull?.status === 'running' ? pull : null;
  const hw = data?.hardware;

  return (
    <>
      <Row label="Choose automatically"
           description={data?.recommended
             ? `Seven uses the best installed model for this PC. For yours: ${data.models.find(m => m.id === data.recommended.id)?.name || data.recommended.id}, because ${data.recommended.reason}.`
             : 'Seven uses the best installed model for this PC.'}>
        <Toggle checked={auto} onChange={on => use(on ? 'auto' : (data?.active || data?.recommended?.id || 'llama3.2:1b'))}
                label="Choose automatically" />
      </Row>

      {data && !data.ollama_running && (
        <Body className="text-[12px] text-s-yellow">Ollama isn't running, so models can't be listed or downloaded. Start Ollama, then come back.</Body>
      )}

      <div className="divide-y divide-s-border/70">
        {(data?.models || []).map(m => {
          const inUse = m.in_use && !auto;
          const isPulling = pulling?.model === m.id;
          return (
            <div key={m.id} className={cx('px-4 py-3 transition-colors', inUse && 'bg-s-accent/[0.05]')}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[12.5px] font-medium text-s-text">{m.name}</span>
                    {inUse && <Badge tone="accent"><Check size={10} />In use</Badge>}
                    {m.recommended && <Badge tone="success"><Sparkles size={10} />Best for this PC</Badge>}
                    {m.installed && !inUse && <Badge>Installed</Badge>}
                    {!m.fits && <Badge tone="warning">May be slow here</Badge>}
                  </div>
                  <p className="mt-0.5 text-[11.5px] leading-relaxed text-s-text-3">
                    Good at {m.good_at}. Less suited to {m.weak_at}.
                  </p>
                  <p className="mt-0.5 font-mono text-[10.5px] text-s-text-4">
                    {m.params} parameters · {m.size_gb} GB · {m.maker} · {m.speed.toLowerCase()} · remembers about {Math.round(m.context * 0.75 / 100) * 100} words at once
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {m.installed && !inUse && (
                    <Button size="sm" variant="primary" onClick={() => use(m.id)}>Use</Button>
                  )}
                  {m.installed && !inUse && !m.in_use && (
                    <Button size="sm" variant="ghost" icon={busy === m.id ? undefined : Trash2} loading={busy === m.id}
                            onClick={() => remove(m)} aria-label={`Remove ${m.name}`} />
                  )}
                  {!m.installed && (
                    <Button size="sm" icon={isPulling ? undefined : Download} loading={isPulling || busy === m.id}
                            disabled={!!pulling || !data?.ollama_running} onClick={() => download(m)}>
                      {isPulling ? `${pulling.progress || 0}%` : 'Download'}
                    </Button>
                  )}
                </div>
              </div>
              {isPulling && (
                <div className="mt-2">
                  <div className="h-1 overflow-hidden rounded-full bg-s-card-h">
                    <div className="h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${pulling.progress || 0}%` }} />
                  </div>
                  <p className="mt-1 font-mono text-[10.5px] text-s-text-4">{pulling.current || 'Starting download'}</p>
                </div>
              )}
            </div>
          );
        })}
        {(data?.other_installed || []).map(name => {
          const inUse = !auto && (data.active === name || data.configured === name);
          return (
            <div key={name} className="flex items-center justify-between gap-4 px-4 py-2.5">
              <div className="flex items-center gap-1.5">
                <span className="text-[12.5px] text-s-text">{name}</span>
                {inUse ? <Badge tone="accent"><Check size={10} />In use</Badge> : <Badge>Installed</Badge>}
              </div>
              {!inUse && <Button size="sm" variant="secondary" onClick={() => use(name)}>Use</Button>}
            </div>
          );
        })}
        {!data && (
          <div className="flex items-center gap-2 px-4 py-3 text-[12px] text-s-text-3"><Loader2 size={13} className="animate-spin" />Checking models</div>
        )}
      </div>

      {hw && (
        <Body className="font-mono text-[10.5px] text-s-text-4">
          This PC: {hw.gpu ? `${hw.gpu.replace(/NVIDIA GeForce /, '')}, ${hw.vram_gb} GB graphics memory` : 'no dedicated graphics card'}, {Math.round(hw.ram_gb)} GB memory
        </Body>
      )}
    </>
  );
}
