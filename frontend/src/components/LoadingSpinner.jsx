export default function LoadingSpinner({ text = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="relative w-12 h-12 mb-4">
        <div className="absolute inset-0 rounded-full border-2 border-seven-border" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-seven-accent animate-spin" />
        <div className="absolute inset-2 rounded-full border-2 border-transparent border-t-seven-accent/50 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '0.8s' }} />
      </div>
      <p className="text-xs text-seven-text-muted">{text}</p>
    </div>
  );
}