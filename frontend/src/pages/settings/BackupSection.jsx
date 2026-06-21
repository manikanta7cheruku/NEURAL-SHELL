/**
 * frontend/src/pages/settings/BackupSection.jsx
 *
 * Shows: export button (downloads JSON backup),
 *        import button (restores from JSON file).
 *
 * Export: GET /api/memory/export -> Blob -> download link
 * Import: POST /api/memory/import -> reads JSON file
 *
 * Both operations bypass plan limits (your own data).
 *
 * PROPS:
 *   exporting    bool — export in progress
 *   importing    bool — import in progress
 *   importResult object {success, msg} or null
 *   importRef    ref attached to hidden file input
 *   exportData   function — triggers export
 *   importData   function(event) — handles file selection
 */

export default function BackupSection({
  exporting, importing, importResult,
  importRef, exportData, importData
}) {
  return (
    <div className="bg-s-card border border-s-border rounded p-4 space-y-3">
      <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
        Data Backup
      </div>
      <p className="text-[11px] text-s-text-3">
        Export your facts, conversations, and schedules as a backup file.
        Import to restore on the same or a new device.
      </p>

      <div className="grid grid-cols-2 gap-3">

        {/* Export card */}
        <div className="bg-s-bg border border-s-border rounded p-3 space-y-2">
          <div className="text-[11px] font-medium text-s-text-2">Export Data</div>
          <p className="text-[10px] text-s-text-4 leading-relaxed">
            Downloads a JSON file with all your facts, conversations, and schedules.
          </p>
          <button
            onClick={exportData}
            disabled={exporting}
            className="w-full py-2 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20 transition-colors disabled:opacity-50"
          >
            {exporting ? 'Exporting...' : 'Download Backup'}
          </button>
        </div>

        {/* Import card */}
        <div className="bg-s-bg border border-s-border rounded p-3 space-y-2">
          <div className="text-[11px] font-medium text-s-text-2">Import Data</div>
          <p className="text-[10px] text-s-text-4 leading-relaxed">
            Restore from a backup file. Adds to existing data, does not replace.
          </p>
          <button
            onClick={() => importRef.current?.click()}
            disabled={importing}
            className="w-full py-2 border border-s-border bg-s-bg text-s-text-3 rounded text-[11px] font-medium hover:bg-s-card-h transition-colors disabled:opacity-50"
          >
            {importing ? 'Importing...' : 'Choose Backup File'}
          </button>
          {/* Hidden file input — triggered by button above */}
          <input
            ref={importRef}
            type="file"
            accept=".json"
            onChange={importData}
            className="hidden"
          />
          {importResult && (
            <p className={`text-[10px] ${importResult.success ? 'text-s-green' : 'text-s-red'}`}>
              {importResult.msg}
            </p>
          )}
        </div>

      </div>
    </div>
  );
}