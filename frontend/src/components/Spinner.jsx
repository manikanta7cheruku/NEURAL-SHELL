export default function Spinner({ t = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-2">
      <div className="w-5 h-5 border-[1.5px] border-s-border border-t-s-accent rounded-full animate-spin" />
      <span className="text-[11px] text-s-text-4">{t}</span>
    </div>
  );
}