/**
 * frontend/src/pages/settings/DangerSection.jsx
 *
 * Shows: Clear All Memory button.
 * Calls DELETE /api/memory/clear after user confirms.
 * Kept separate because danger actions should be isolated —
 * harder to accidentally include in other logic.
 */

import api from '../../api';

export default function DangerSection() {

  const clearMemory = async () => {
    const confirmed = window.confirm(
      'Delete ALL facts and conversations? This cannot be undone.\n\nTip: Export your data first from Data Backup above.'
    );
    if (!confirmed) return;

    try {
      await api.delete('/memory/clear');
      alert('Memory cleared');
    } catch {
      alert('Failed to clear memory');
    }
  };

  return (
    <div className="bg-s-card border border-s-red/20 rounded p-4">
      <div className="text-[9px] text-s-red uppercase tracking-wider font-medium mb-3">
        Danger Zone
      </div>
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