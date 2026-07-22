import { Cpu, HardDrive, MemoryStick, Package } from 'lucide-react';

export default function HardwareCard({ hw }) {
  if (!hw) {
    return (
      <div className="bg-white/[0.02] border border-white/8 rounded-2xl p-5">
        <div className="text-[10px] text-white/40">Loading hardware...</div>
      </div>
    );
  }

  const specs = [
    { icon: Cpu,         label: 'GPU',    value: hw.gpu?.name || 'None' },
    { icon: MemoryStick, label: 'VRAM',   value: `${hw.gpu?.vram_gb || 0} GB` },
    { icon: HardDrive,   label: 'RAM',    value: `${hw.ram_gb} GB` },
    { icon: Cpu,         label: 'CPU',    value: `${hw.cpu?.cores || '?'} cores` },
  ];

  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-white/[0.05] flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/8
                        flex items-center justify-center">
          <Cpu size={13} className="text-white/45" />
        </div>
        <div>
          <h2 className="text-[12px] font-semibold text-white/85">Hardware</h2>
          <p className="text-[9px] text-white/35 mt-0.5">Your machine's capabilities</p>
        </div>
      </div>

      <div className="p-5">
        <div className="grid grid-cols-4 gap-2">
          {specs.map(({ icon: Icon, label, value }) => (
            <div key={label} className="bg-white/[0.015] border border-white/6 rounded-xl p-3">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Icon size={10} className="text-white/30" />
                <span className="text-[8px] text-white/30 uppercase tracking-widest font-medium">
                  {label}
                </span>
              </div>
              <div className="text-[11px] text-white/80 font-mono font-medium truncate">
                {value}
              </div>
            </div>
          ))}
        </div>

        {hw.installed_models?.length > 0 && (
          <div className="mt-4 pt-4 border-t border-white/[0.05]">
            <div className="flex items-center gap-1.5 mb-2">
              <Package size={10} className="text-white/30" />
              <span className="text-[8px] text-white/30 uppercase tracking-widest font-medium">
                Installed Models
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {hw.installed_models.map(m => (
                <span key={m} className="text-[9px] text-s-accent/70 bg-s-accent/6
                                          border border-s-accent/12 px-2 py-0.5 rounded-md
                                          font-mono">
                  {m}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}