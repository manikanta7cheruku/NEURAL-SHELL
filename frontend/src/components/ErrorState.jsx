import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="w-14 h-14 rounded-2xl bg-seven-danger/10 flex items-center justify-center mb-4">
        <AlertTriangle size={24} className="text-seven-danger" />
      </div>
      <p className="text-sm text-seven-text-dim mb-4">{message || 'Something went wrong'}</p>
      {onRetry && (
        <button onClick={onRetry} className="flex items-center gap-2 px-4 py-2 bg-seven-card hover:bg-seven-border rounded-xl text-xs text-seven-text-dim border border-seven-border transition-smooth">
          <RefreshCw size={13} /> Retry
        </button>
      )}
    </div>
  );
}