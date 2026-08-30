import api from '../../api';

export default function DangerSection() {

  const clearMemory = async () => {
    const confirmed = window.confirm(
      'Delete ALL facts and conversations? This cannot be undone.\n\nTip: Export your data first from Data Backup above.'
    );
    if (!confirmed) return;

    try {
      await api.delete('/memory/clear');
      alert('Memory cleared successfully.');
    } catch {
      alert('Failed to clear memory.');
    }
  };

  const repairInstallation = async () => {
    const confirmed = window.confirm(
      'Repair Installation\n\n' +
      'This will restart the setup wizard to reinstall missing components ' +
      '(AI engine, models, dependencies).\n\n' +
      'Your data (memory, triggers, schedules, tasks) will NOT be deleted.\n\n' +
      'Seven will restart after you click OK.'
    );
    if (!confirmed) return;

    try {
      // Reset setup flag so wizard runs on next launch
      await api.put('/config', {
        updates: { setup_complete: false }
      });
      // Restart Python process
      await api.post('/bootstrap/restart', {});
    } catch {
      alert('Failed to start repair. Please restart Seven manually.');
    }
  };

  return (
    <div className="bg-s-card border border-s-red/20 rounded p-4 space-y-4">
      <div className="text-[9px] text-s-red uppercase tracking-wider font-medium">
        Danger Zone
      </div>

      {/* Repair Installation */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] text-s-text-2">Repair Installation</div>
          <p className="text-[9px] text-s-text-4">
            Re-run the setup wizard to fix missing AI engine, models, or dependencies. Your data is preserved.
          </p>
        </div>
        <button
          onClick={repairInstallation}
          className="px-3 py-1.5 border border-amber-500/30 bg-amber-500/8 text-amber-400 rounded text-[10px] font-medium hover:bg-amber-500/15 transition-colors"
        >
          Repair
        </button>
      </div>

      <div className="h-px bg-white/5" />

      {/* Clear Memory */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] text-s-text-2">Clear All Memory</div>
          <p className="text-[9px] text-s-text-4">
            Permanently delete all facts and conversations. Export first if needed.
          </p>
        </div>
        <button
          onClick={clearMemory}
          className="px-3 py-1.5 border border-s-red/30 bg-s-red/8 text-s-red rounded text-[10px] font-medium hover:bg-s-red/15 transition-colors"
        >
          Clear Memory
        </button>
      </div>
    </div>
  );
}