import { Download, Upload, Database } from 'lucide-react';

export default function BackupSection({
  exporting, importing, importResult,
  importRef, exportData, importData
}) {
  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-white/[0.05] flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/8
                        flex items-center justify-center">
          <Database size={13} className="text-white/45" />
        </div>
        <div>
          <h2 className="text-[12px] font-semibold text-white/85">Backup & Restore</h2>
          <p className="text-[9px] text-white/35 mt-0.5">Export or import your data</p>
        </div>
      </div>

      <div className="p-5 space-y-4">
        <p className="text-[10.5px] text-white/50 leading-relaxed">
          Export your facts, conversations, and schedules as a backup file.
          Import to restore on the same or a new device.
        </p>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/[0.015] border border-white/8 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Download size={12} className="text-s-accent/70" />
              <div className="text-[11px] font-semibold text-white/80">Export</div>
            </div>
            <p className="text-[10px] text-white/40 leading-relaxed">
              Download all your data as JSON. Safe to store or transfer.
            </p>
            <button
              onClick={exportData}
              disabled={exporting}
              className="w-full py-2 border border-s-accent/20 bg-s-accent/8 text-s-accent
                         rounded-lg text-[10.5px] font-medium hover:bg-s-accent/15
                         disabled:opacity-40 transition-all"
            >
              {exporting ? 'Exporting...' : 'Download Backup'}
            </button>
          </div>

          <div className="bg-white/[0.015] border border-white/8 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Upload size={12} className="text-white/50" />
              <div className="text-[11px] font-semibold text-white/80">Import</div>
            </div>
            <p className="text-[10px] text-white/40 leading-relaxed">
              Restore from backup. Adds to existing data — does not replace.
            </p>
            <button
              onClick={() => importRef.current?.click()}
              disabled={importing}
              className="w-full py-2 border border-white/8 bg-white/[0.02] text-white/60
                         rounded-lg text-[10.5px] font-medium hover:bg-white/[0.05]
                         hover:text-white/80 disabled:opacity-40 transition-all"
            >
              {importing ? 'Importing...' : 'Choose Backup File'}
            </button>
            <input
              ref={importRef}
              type="file"
              accept=".json"
              onChange={importData}
              className="hidden"
            />
            {importResult && (
              <div className={`text-[10px] px-2 py-1.5 rounded-lg border
                ${importResult.success
                  ? 'text-green-400 bg-green-500/[0.06] border-green-500/15'
                  : 'text-red-400 bg-red-500/[0.06] border-red-500/15'}`}>
                {importResult.msg}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}