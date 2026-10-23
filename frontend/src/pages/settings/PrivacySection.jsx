/**
 * Privacy & data: what can leave this computer, where memory lives, backups,
 * and clearing memory. "Clear all memory" removes the facts, conversations and
 * learned preferences the brain actually uses (not only the legacy index).
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, Upload } from 'lucide-react';
import api from '../../api';
import { Section, Row, Toggle, Button, Input, Dialog } from '../../components/ui';
import { toast } from '../../lib/toast';
import { saveConfig } from './save';

function Network({ config }) {
  const flags = {
    web: config.web?.enabled ?? true,
    telemetry: config.privacy?.telemetry_enabled ?? true,
    updates: config.updates?.auto_check ?? true,
  };
  return (
    <Section title="Online features" description="Seven's language model always runs on this computer. These are the only things that use the internet.">
      <Row label="Web search" description="Look up live information such as news and weather. Only the search text is sent to the search provider.">
        <Toggle checked={flags.web} onChange={v => saveConfig({ web: { enabled: v } })} label="Web search" />
      </Row>
      <Row label="Usage statistics" description="Send a device id, your email if you added one, your country and how long Seven is active. Conversations and memories are never sent.">
        <Toggle checked={flags.telemetry} onChange={v => saveConfig({ privacy: { telemetry_enabled: v } })} label="Usage statistics" />
      </Row>
      <Row label="Check for updates" description="Ask GitHub once a day whether a new version of Seven is available.">
        <Toggle checked={flags.updates} onChange={v => saveConfig({ updates: { auto_check: v } })} label="Check for updates" />
      </Row>
    </Section>
  );
}

function Storage({ overview }) {
  const navigate = useNavigate();
  return (
    <Section title="Your memory" description="Facts and conversations are stored only on this computer."
             actions={<Button size="sm" onClick={() => navigate('/memory')}>Open Memory</Button>}>
      <Row label="Stored">
        <span className="text-[13px] text-s-text-2 tabular-nums">
          {overview ? `${overview.facts.active} facts, ${overview.conversations.count} conversations` : 'Loading'}
        </span>
      </Row>
      <Row label="Size on disk">
        <span className="text-[13px] text-s-text-2 tabular-nums">{overview ? `${overview.storage.total_mb} MB` : ''}</span>
      </Row>
      {overview?.storage.folder && (
        <Row label="Location" stacked>
          <code className="block break-all rounded-lg border border-s-border bg-s-bg px-3 py-2 font-mono text-[12px] text-s-text-2">
            {overview.storage.folder}
          </code>
        </Row>
      )}
    </Section>
  );
}

function Backup() {
  const fileRef = useRef(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);

  const exportData = async () => {
    setExporting(true);
    try {
      const r = await api.get('/memory/export');
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `seven-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Backup downloaded');
    } catch {
      toast.error('Export failed', 'Check that Seven is running, then try again.');
    }
    setExporting(false);
  };

  const importData = async e => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setImporting(true);
    try {
      const data = JSON.parse(await file.text());
      const r = await api.post('/memory/import', data);
      toast.success('Backup imported', r.data.message);
    } catch {
      toast.error('Import failed', 'That file is not a valid Seven backup.');
    }
    setImporting(false);
  };

  return (
    <Section title="Backup" description="A single JSON file with your facts, conversations, schedules, tasks, triggers and workspaces.">
      <Row label="Export" description="Save a copy you can restore on this or another computer.">
        <Button icon={Download} onClick={exportData} loading={exporting}>Download backup</Button>
      </Row>
      <Row label="Import" description="Adds the backup to what you already have. Nothing is replaced.">
        <Button icon={Upload} onClick={() => fileRef.current?.click()} loading={importing}>Choose file</Button>
        <input ref={fileRef} type="file" accept=".json,application/json" onChange={importData} className="hidden" />
      </Row>
    </Section>
  );
}

function ClearMemory({ onCleared }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);

  const clear = async () => {
    setBusy(true);
    try {
      const r = await api.delete('/memory/clear');
      if (!r.data?.success) throw new Error(r.data?.error);
      toast.success('Memory cleared', r.data.message);
      setOpen(false);
      onCleared();
    } catch (e) {
      toast.error('Could not clear memory', e.message || 'Check that Seven is running.');
    }
    setBusy(false);
  };

  return (
    <Section title="Clear all memory" tone="danger">
      <Row label="Delete everything Seven remembers"
           description="Every fact, conversation, goal and learned preference. This can't be undone, so download a backup first.">
        <Button variant="danger" onClick={() => { setTyped(''); setOpen(true); }}>Clear memory</Button>
      </Row>
      <Dialog open={open} tone="danger" title="Clear all memory?" busy={busy} confirmLabel="Delete everything"
              confirmDisabled={typed !== 'DELETE'} onConfirm={clear} onCancel={() => setOpen(false)}
              description="Seven will forget every fact, conversation, goal and preference. Type DELETE to confirm.">
        <Input value={typed} onChange={e => setTyped(e.target.value)} placeholder="DELETE" aria-label="Type DELETE to confirm" className="w-full" />
      </Dialog>
    </Section>
  );
}

export default function PrivacySection({ config }) {
  const [overview, setOverview] = useState(null);
  const load = () => api.get('/memory/overview').then(r => setOverview(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  return (
    <>
      <Network config={config} />
      <Storage overview={overview} />
      <Backup />
      <ClearMemory onCleared={load} />
    </>
  );
}
