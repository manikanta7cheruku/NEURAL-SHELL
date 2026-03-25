import PageHeader from '../components/PageHeader';

const GUIDES = [
  {
    title: 'Getting Started with Seven',
    content: 'Seven is a 100% local AI assistant for Windows. Everything runs on your machine — no cloud, no data leaves your PC. After installation, the setup wizard detects your hardware and downloads the best AI model for your system.',
  },
  {
    title: 'Voice Commands',
    content: 'Talk to Seven naturally. Say "open chrome" to launch apps, "set volume to 50" for system control, "remind me in 30 minutes to call mom" for scheduling. Seven understands context — say "make it louder" after a volume command and it knows what "it" means.',
  },
  {
    title: 'App Control',
    content: 'Seven opens and closes any app. Use custom aliases to rename apps (say "browser" instead of "chrome"). Add custom .exe paths for portable apps. You can even add URLs — say "open youtube" to launch youtube.com in your browser. Note: Seven can close apps (like Chrome) but cannot close specific browser tabs. "Close youtube" won\'t work because YouTube runs inside Chrome, not as a separate process.',
  },
  {
    title: 'Window Management',
    content: 'Snap windows to sides, pin them on top, adjust transparency, swap positions, go fullscreen, or arrange split-screen layouts. Say "minimize everything" to clear your desktop. Pro users get multi-monitor support and advanced layouts.',
  },
  {
    title: 'System Control',
    content: 'Control volume, brightness, check battery, toggle WiFi and Bluetooth, switch dark/light mode, enable night light or do-not-disturb, and control media playback. All by voice or through the dashboard.',
  },
  {
    title: 'Memory & Learning',
    content: 'Seven remembers your conversations and learns facts about you. Say "my name is Mani" and Seven remembers forever. It uses semantic search — ask "what sport do I play?" and it finds "User likes cricket" even though the words are different.',
  },
  {
    title: 'Scheduling',
    content: 'Set alarms ("wake me up at 7am"), reminders ("remind me to call mom at 5pm"), timers ("set a timer for 10 minutes"), and calendar events. Supports recurring schedules — "remind me every Monday to submit the report".',
  },
  {
    title: 'Knowledge Base',
    content: 'Upload .txt and .md files to teach Seven about specific topics. Seven chunks and indexes documents locally. When you ask a question, it searches your knowledge base before answering — perfect for studying or work reference.',
  },
  {
    title: 'Console Commands',
    content: 'Use the Console (text chat) for quick commands: /memory to see stats, /facts to list facts, /add fact [text] to add facts, /clear all to reset, /help for all commands. Same brain as voice — everything works.',
  },
  {
    title: 'Privacy',
    content: 'Seven runs 100% locally. Your conversations, facts, voice data, and documents never leave your machine. No cloud servers, no telemetry, no tracking. The AI model runs on your GPU/CPU. Even web searches go through DuckDuckGo for privacy.',
  },
];

export default function Blog() {
  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Guide" sub="Learn what Seven can do" />
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {GUIDES.map((g, i) => (
          <details key={i} className="bg-s-card border border-s-border rounded group">
            <summary className="px-4 py-2.5 cursor-pointer text-[13px] text-s-text-2 font-medium hover:text-s-text select-none list-none flex justify-between items-center">
              {g.title}
              <span className="text-s-text-4 text-[10px] group-open:rotate-90 transition-transform">▸</span>
            </summary>
            <div className="px-4 pb-3 text-[12px] text-s-text-3 leading-relaxed border-t border-s-border pt-2">{g.content}</div>
          </details>
        ))}
      </div>
    </div>
  );
}