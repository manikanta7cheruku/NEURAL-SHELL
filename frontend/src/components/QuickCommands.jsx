import { useState } from 'react';
import { Terminal, ChevronRight, Copy, Check } from 'lucide-react';

const COMMANDS = [
  { category: 'Memory', commands: ['/memory', '/facts', '/convos', '/stats'] },
  { category: 'Logs', commands: ['/logs', '/logs N', '/mood'] },
  { category: 'Manage', commands: ['/add fact [text]', '/delete fact [n]', '/delete convo [n]'] },
  { category: 'Clear', commands: ['/clear all', '/clear logs', '/clear mood'] },
  { category: 'Speakers', commands: ['/speaker [name]', '/speakers', '/remove speaker [name]'] },
  { category: 'Control', commands: ['/windows', '/window [cmd]', '/system', '/sys [cmd]'] },
  { category: 'Schedule', commands: ['/schedules', '/sched [cmd]'] },
  { category: 'Help', commands: ['/help'] },
];

export default function QuickCommands({ onCommand }) {
  const [copiedCmd, setCopiedCmd] = useState(null);

  const handleClick = (cmd) => {
    if (onCommand) {
      const clean = cmd.replace('[text]', '').replace('[n]', '').replace('[name]', '').replace('[cmd]', '').trim();
      onCommand(clean);
    }
    setCopiedCmd(cmd);
    setTimeout(() => setCopiedCmd(null), 1500);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-seven-text-muted">
        <Terminal size={13} />
        <span className="uppercase tracking-wider font-medium">Quick Commands</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {COMMANDS.map((group) => (
          <div key={group.category} className="rounded-xl bg-seven-bg/60 border border-seven-border p-3">
            <div className="text-[10px] text-seven-accent uppercase tracking-wider mb-2 font-medium">
              {group.category}
            </div>
            <div className="space-y-1">
              {group.commands.map((cmd) => (
                <button
                  key={cmd}
                  onClick={() => handleClick(cmd)}
                  className="flex items-center gap-2 w-full text-left px-2 py-1.5 rounded-lg hover:bg-seven-card text-xs text-seven-text-dim hover:text-seven-text transition-smooth group"
                >
                  <ChevronRight size={10} className="text-seven-text-muted group-hover:text-seven-accent shrink-0" />
                  <code className="flex-1 font-mono text-[11px]">{cmd}</code>
                  {copiedCmd === cmd ? (
                    <Check size={10} className="text-seven-success shrink-0" />
                  ) : (
                    <Copy size={10} className="text-seven-text-muted opacity-0 group-hover:opacity-100 shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}