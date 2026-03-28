import React from 'react';

export default function TitleBar() {
  const handleMinimize = () => {
    if (window.electron) {
      window.electron.minimize();
    }
  };

  const handleMaximize = () => {
    if (window.electron) {
      window.electron.maximize();
    }
  };

  const handleClose = () => {
    if (window.electron) {
      window.electron.close();
    }
  };

  // Only show in Electron
  if (!window.electron) {
    return null;
  }

  return (
    <div
      className="h-7 bg-s-bg border-b border-s-border flex items-center justify-between px-3 select-none"
      style={{ WebkitAppRegion: 'drag' }}
    >
      <div className="font-serif text-sm tracking-wider text-white/70" style={{ fontFamily: 'Georgia, serif' }}>
        VII
      </div>
      
      <div className="flex items-center gap-3" style={{ WebkitAppRegion: 'no-drag' }}>
        <button
          onClick={handleMinimize}
          className="text-white/40 hover:text-white/80 transition-colors text-base leading-none w-6 h-6 flex items-center justify-center"
          title="Minimize"
        >
          —
        </button>
        
        <button
          onClick={handleMaximize}
          className="text-white/40 hover:text-white/80 transition-colors text-base leading-none w-6 h-6 flex items-center justify-center"
          title="Maximize"
        >
          □
        </button>
        
        <button
          onClick={handleClose}
          className="text-white/40 hover:text-red-400 transition-colors text-base leading-none w-6 h-6 flex items-center justify-center"
          title="Close (minimize to tray)"
        >
          ×
        </button>
      </div>
    </div>
  );
}