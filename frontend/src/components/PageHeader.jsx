export default function PageHeader({ title, sub, right }) {
  return (
    <div className="bg-s-bg border-b border-s-border px-5 py-3 flex items-center justify-between">
      <div>
        <h1 className="text-[15px] font-semibold text-s-text tracking-tight">{title}</h1>
        {sub && <p className="text-[11px] text-s-text-4 mt-0.5">{sub}</p>}
      </div>
      {right}
    </div>
  );
}