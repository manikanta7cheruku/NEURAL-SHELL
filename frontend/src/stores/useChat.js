import { create } from 'zustand';
import api from '../api';

const useChat = create((set, get) => ({
  messages: [],
  sending: false,
  draft: '',

  setDraft: (draft) => set({ draft }),

  clear: () => set({ messages: [], draft: '' }),

  send: async (text, attachedFile = null) => {
    if (!text.trim()) return;

    const userMsg = { role: 'user', text, time: new Date(), attachedFile };
    set((s) => ({ messages: [...s.messages, userMsg], sending: true }));
    get().setDraft('');

    try {
      // Check if it's a local command (starts with /)
      if (text.startsWith('/')) {
        const response = await get().handleCommand(text);
        const botMsg = { role: 'assistant', text: response, time: new Date(), isCommand: true };
        set((s) => ({ messages: [...s.messages, botMsg], sending: false }));
        return;
      }

      // Normal chat — send to backend
      const r = await api.post('/chat', { text });
      const botMsg = {
        role: 'assistant',
        text: r.data.response,
        actions: r.data.actions || [],
        fileResults: r.data.file_results || null,
        time: new Date(),
      };
      set((s) => ({ messages: [...s.messages, botMsg], sending: false }));
    } catch (e) {
      const errMsg = {
        role: 'assistant',
        text: e.response?.data?.detail || 'Connection error',
        error: true,
        time: new Date(),
      };
      set((s) => ({ messages: [...s.messages, errMsg], sending: false }));
    }
  },

  handleCommand: async (cmd) => {
    const lower = cmd.toLowerCase().trim();

    // =========================================================================
    // HELP
    // =========================================================================
    if (lower === '/help') {
      return `SEVEN CONSOLE COMMANDS
${'='.repeat(60)}

MEMORY COMMANDS:
  /memory              Show all memories (facts + conversations)
  /facts               Show stored facts only
  /convos              Show stored conversations only
  /stats               Show system statistics
  /add fact [text]     Manually add a fact
  /delete fact [n]     Delete fact by index
  /delete convo [n]    Delete conversation by index

LOGS & MOOD:
  /logs                Show last 10 command logs
  /logs [n]            Show last N command logs
  /mood                Show current mood state with visual bar

SPEAKERS (Voice ID):
  /speakers            List enrolled speakers
  /speaker [name]      Show info about specific speaker

SYSTEM CONTROL:
  /system              Show system status & available commands
  /sys volume          Show volume commands
  /sys brightness      Show brightness commands
  /sys power           Show power & network commands
  /sys media           Show media control commands

WINDOW MANAGEMENT:
  /windows             Show all window commands
  /win control         Show window control commands
  /win snap            Show window snapping commands
  /win layout          Show multi-window layout commands

SCHEDULER:
  /schedules           Show all schedules (active, fired, cancelled)
  /sched active        Show only active schedules
  /sched create        Show how to create schedules

KNOWLEDGE BASE:
  /knowledge           Show knowledge base stats
  /knowledge search X  Search knowledge base for X
  /knowledge files     Show indexed files

HARDWARE & SPEED:
  /speed               Show latency stats
  /hardware            Show GPU/RAM/CPU info + recommended model

TELEMETRY:
  /telemetry           Show your usage stats (local only)

OTHER:
  /version             Show Seven version info
  /clear               Clear chat history
  /export              Export chat history

${'='.repeat(60)}
Type any command above or ask Seven naturally in chat.`;
    }

    // =========================================================================
    // VERSION
    // =========================================================================
    if (lower === '/version') {
      try {
        const res = await api.get('/version');
        const v = res.data;
        return `SEVEN VERSION INFO
${'='.repeat(50)}
Version:     ${v.version}
Name:        ${v.name}
Build Date:  ${v.build_date}
${'='.repeat(50)}`;
      } catch (e) {
        return `Error: ${e.message}`;
      }
    }

    // =========================================================================
    // CLEAR CHAT
    // =========================================================================
    if (lower === '/clear') {
      get().clear();
      return 'Chat history cleared.';
    }

    // =========================================================================
    // EXPORT CHAT
    // =========================================================================
    if (lower === '/export') {
      const messages = get().messages;
      if (messages.length === 0) {
        return 'No messages to export.';
      }
      
      let exportText = `SEVEN CHAT EXPORT\n`;
      exportText += `Exported: ${new Date().toLocaleString()}\n`;
      exportText += `${'='.repeat(50)}\n\n`;
      
      messages.forEach((m) => {
        const time = m.time.toLocaleTimeString();
        const role = m.role === 'user' ? 'YOU' : 'SEVEN';
        exportText += `[${time}] ${role}:\n${m.text}\n\n`;
      });
      
      // Create download
      const blob = new Blob([exportText], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `seven-chat-${Date.now()}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      
      return `Exported ${messages.length} messages to file.`;
    }

    // =========================================================================
    // MEMORY
    // =========================================================================
    if (lower === '/memory' || lower === '/facts' || lower === '/convos') {
      try {
        let result = '';
        
        if (lower === '/memory' || lower === '/facts') {
          const factsRes = await api.get('/memory/facts');
          const facts = factsRes.data;
          if (facts.length === 0) {
            result += 'No facts stored yet.\n\n';
          } else {
            result += `STORED FACTS (${facts.length} total)\n${'='.repeat(50)}\n`;
            facts.forEach((f, i) => {
              result += `[${i}] (${f.category}) ${f.text}\n`;
              result += `    Saved: ${f.timestamp} | Speaker: ${f.speaker}\n`;
            });
            result += '='.repeat(50) + '\n\n';
          }
        }

        if (lower === '/memory' || lower === '/convos') {
          const convosRes = await api.get('/memory/conversations?limit=20');
          const convos = convosRes.data.conversations;
          if (convos.length === 0) {
            result += 'No conversations stored yet.';
          } else {
            result += `STORED CONVERSATIONS (${convos.length} shown, ${convosRes.data.total} total)\n${'='.repeat(50)}\n`;
            convos.forEach((c, i) => {
              result += `[${i}] ${c.text.substring(0, 80)}${c.text.length > 80 ? '...' : ''}\n`;
              result += `    Saved: ${c.timestamp} | Speaker: ${c.speaker}\n`;
            });
            result += '='.repeat(50);
          }
        }

        return result || 'No memory data found.';
      } catch (e) {
        return `Error loading memory: ${e.message}`;
      }
    }

    // =========================================================================
    // STATS
    // =========================================================================
    if (lower === '/stats') {
      try {
        const [memRes, logsRes, statusRes, schedRes] = await Promise.all([
          api.get('/memory/stats'),
          api.get('/commands/log?limit=10'),
          api.get('/status'),
          api.get('/schedules')
        ]);

        const mem = memRes.data;
        const logs = logsRes.data.stats;
        const status = statusRes.data;
        const scheds = schedRes.data;
        const activeScheds = scheds.filter(s => s.status === 'active').length;

        return `SYSTEM STATISTICS
${'='.repeat(50)}

MEMORY:
  Conversations:    ${mem.total_conversations}
  Facts:            ${mem.total_facts}
  Storage:          ${mem.storage_mb || 0} MB

COMMANDS:
  Total executed:   ${logs.total}
  Opens:            ${logs.opens}
  Closes:           ${logs.closes}
  Success rate:     ${logs.success_rate}

STATUS:
  Model:            ${status.model}
  Mood:             ${status.mood} (${status.mood_value?.toFixed(2) || 0})
  Streaming:        ${status.streaming ? 'ON' : 'OFF'}
  Uptime:           ${status.uptime}
  Speaker:          ${status.speaker}

SCHEDULES:
  Active:           ${activeScheds}
  Total:            ${scheds.length}

${'='.repeat(50)}`;
      } catch (e) {
        return `Error loading stats: ${e.message}`;
      }
    }

    // =========================================================================
    // LOGS
    // =========================================================================
    if (lower === '/logs' || lower.startsWith('/logs ')) {
      try {
        const parts = lower.split(' ');
        const count = parts[1] && !isNaN(parts[1]) ? parseInt(parts[1]) : 10;
        const res = await api.get(`/commands/log?limit=${count}`);
        const logs = res.data.recent;
        const stats = res.data.stats;

        if (!logs || logs.length === 0) {
          return 'No commands logged yet.';
        }

        let result = `COMMAND LOGS (Last ${logs.length})\n${'='.repeat(50)}\n`;
        logs.forEach((log) => {
          const status = log.success ? '✅' : '❌';
          const time = log.timestamp?.split(' ')[1] || '??:??';
          result += `[${time}] ${status} ${log.action.padEnd(6)} ${log.target}\n`;
        });
        result += `${'─'.repeat(50)}\n`;
        result += `Total: ${stats.total} | Opens: ${stats.opens} | Closes: ${stats.closes}\n`;
        result += `Success Rate: ${stats.success_rate}`;
        
        return result;
      } catch (e) {
        return `Error loading logs: ${e.message}`;
      }
    }

    // =========================================================================
    // MOOD
    // =========================================================================
    if (lower === '/mood') {
      try {
        const res = await api.get('/mood');
        const mood = res.data;
        
        // Visual mood bar
        const barPos = Math.floor((mood.mood_value + 1) * 15);
        const bar = Array(30).fill('─');
        if (barPos >= 0 && barPos < 30) bar[barPos] = '●';
        
        let result = `MOOD ENGINE\n${'='.repeat(50)}\n\n`;
        result += `Frustrated [${bar.join('')}] Excited\n\n`;
        result += `Value:        ${mood.mood_value.toFixed(3)}\n`;
        result += `Label:        ${mood.label}\n`;
        result += `Interactions: ${mood.interaction_count}\n`;
        
        if (mood.recent_changes && mood.recent_changes.length > 0) {
          result += `\nRecent Mood Shifts:\n${'─'.repeat(50)}\n`;
          mood.recent_changes.slice(0, 5).forEach(change => {
            const direction = change.delta > 0 ? '↑' : '↓';
            result += `${direction} ${change.delta > 0 ? '+' : ''}${change.delta.toFixed(3)} → ${change.label}\n`;
          });
        }
        
        result += `\n${'='.repeat(50)}`;
        return result;
      } catch (e) {
        return `Error loading mood: ${e.message}`;
      }
    }

    // =========================================================================
    // ADD FACT
    // =========================================================================
    if (lower.startsWith('/add fact ')) {
      const factText = cmd.substring(10).trim();
      if (!factText) {
        return `❌ Usage: /add fact I love programming

Examples:
  /add fact My favorite color is blue
  /add fact I work at Google
  /add fact My birthday is January 15`;
      }
      try {
        await api.post('/memory/facts', { text: factText, category: 'manual' });
        return `✅ Fact added successfully!\n\nStored: "${factText}"\nCategory: manual\n\nView all facts with /facts`;
      } catch (e) {
        return `❌ Error adding fact: ${e.message}`;
      }
    }

    // =========================================================================
    // DELETE FACT
    // =========================================================================
    if (lower.startsWith('/delete fact ')) {
      const index = parseInt(cmd.substring(13).trim());
      if (isNaN(index)) {
        return `❌ Usage: /delete fact [index]

Example: /delete fact 0

First, use /facts to see all facts with their indices.`;
      }
      try {
        const factsRes = await api.get('/memory/facts');
        const facts = factsRes.data;
        if (index < 0 || index >= facts.length) {
          return `❌ Invalid index. Valid range: 0 to ${facts.length - 1}\n\nUse /facts to see all facts.`;
        }
        const fact = facts[index];
        await api.delete(`/memory/facts/${fact.id}`);
        return `✅ Deleted fact [${index}]\n\nRemoved: "${fact.text}"`;
      } catch (e) {
        return `❌ Error deleting fact: ${e.message}`;
      }
    }

    // =========================================================================
    // DELETE CONVO
    // =========================================================================
    if (lower.startsWith('/delete convo ')) {
      const index = parseInt(cmd.substring(14).trim());
      if (isNaN(index)) {
        return `❌ Usage: /delete convo [index]

Example: /delete convo 0

First, use /convos to see all conversations with their indices.`;
      }
      try {
        const convosRes = await api.get('/memory/conversations?limit=100');
        const convos = convosRes.data.conversations;
        if (index < 0 || index >= convos.length) {
          return `❌ Invalid index. Valid range: 0 to ${convos.length - 1}\n\nUse /convos to see all conversations.`;
        }
        const convo = convos[index];
        await api.delete(`/memory/conversations/${convo.id}`);
        return `✅ Deleted conversation [${index}]`;
      } catch (e) {
        return `❌ Error deleting conversation: ${e.message}`;
      }
    }

    // =========================================================================
    // CLEAR ALL
    // =========================================================================
    if (lower === '/clear all') {
      return `⚠️ CLEAR ALL MEMORY

This will permanently delete:
• All stored facts
• All conversation history
• Command logs
• Mood data

For safety, please use the Settings page to clear all memory.

Dashboard → Settings → Clear Memory`;
    }

    // =========================================================================
    // SPEAKERS
    // =========================================================================
    if (lower === '/speakers') {
      try {
        const res = await api.get('/speakers');
        
        if (!res.data.enabled || !res.data.speakers || res.data.speakers.length === 0) {
          return `VOICE ID — ENROLLED SPEAKERS
${'='.repeat(50)}

No speakers enrolled yet.

HOW TO ENROLL YOUR VOICE:
${'─'.repeat(50)}
1. Run Seven in voice mode (Run_Seven.bat)
2. Say: "Enroll my voice"
3. When prompted, say your name
4. Speak a few sentences so Seven can learn your voice

BENEFITS OF VOICE ID:
${'─'.repeat(50)}
• Seven recognizes who is speaking
• Personalized responses per user
• Separate memory per speaker
• Multi-user household support

${'='.repeat(50)}`;
        }
        
        const speakers = res.data.speakers;
        let result = `VOICE ID — ENROLLED SPEAKERS\n${'='.repeat(50)}\n\n`;
        result += `Total Enrolled: ${speakers.length}\n\n`;
        speakers.forEach((s, i) => {
          result += `${i + 1}. ${s.name}\n`;
        });
        result += `\n${'─'.repeat(50)}\n`;
        result += `To remove a speaker: Use voice mode and say\n`;
        result += `"Remove speaker [name]"\n`;
        result += `${'='.repeat(50)}`;
        
        return result;
      } catch (e) {
        return `Error loading speakers: ${e.message}`;
      }
    }

    if (lower.startsWith('/speaker ')) {
      const name = cmd.substring(9).trim();
      if (!name) {
        return '❌ Usage: /speaker [name]\n\nExample: /speaker mani';
      }
      try {
        const res = await api.get('/speakers');
        if (!res.data.speakers) {
          return 'No speakers enrolled yet.';
        }
        const speaker = res.data.speakers.find(s => 
          s.name.toLowerCase() === name.toLowerCase()
        );
        if (!speaker) {
          return `Speaker "${name}" not found.\n\nUse /speakers to see all enrolled speakers.`;
        }
        return `SPEAKER: ${speaker.name}\n${'='.repeat(50)}\nStatus: Enrolled\n${'='.repeat(50)}`;
      } catch (e) {
        return `Error: ${e.message}`;
      }
    }

    // =========================================================================
    // SYSTEM
    // =========================================================================
    if (lower === '/system') {
      try {
        const [configRes, statusRes] = await Promise.all([
          api.get('/config'),
          api.get('/status')
        ]);
        const config = configRes.data;
        const status = statusRes.data;
        
        return `SYSTEM STATUS
${'='.repeat(50)}

CORE:
  Version:        ${config.version || '1.10'}
  Model:          ${config.brain?.model_name || 'Unknown'}
  Streaming:      ${config.brain?.streaming ? 'Enabled' : 'Disabled'}
  Status:         ${status.listening ? 'Listening' : status.thinking ? 'Thinking' : status.speaking ? 'Speaking' : 'Idle'}
  Uptime:         ${status.uptime}

AVAILABLE COMMANDS:
${'─'.repeat(50)}
  /sys volume      Volume control commands
  /sys brightness  Brightness control commands
  /sys power       Power & network commands
  /sys media       Media playback commands
  /sys modes       System mode toggles

QUICK REFERENCE:
${'─'.repeat(50)}
  "increase volume"       "check battery"
  "set brightness 80%"    "turn on wifi"
  "mute"                  "enable dark mode"
  "play music"            "turn off bluetooth"

${'='.repeat(50)}
Type commands naturally in chat to execute.`;
      } catch (e) {
        return `Error loading system info: ${e.message}`;
      }
    }

    if (lower === '/sys volume') {
      return `VOLUME CONTROL COMMANDS
${'='.repeat(50)}

VOICE COMMANDS:
  "increase volume"
  "decrease volume"
  "set volume to 50%"
  "set volume to 80"
  "mute"
  "unmute"
  "what's the volume?"

EXAMPLES:
  "Turn up the volume"
  "Volume to max"
  "Lower the volume a bit"
  "Mute the sound"

${'='.repeat(50)}
Type any command above in chat to execute.`;
    }

    if (lower === '/sys brightness') {
      return `BRIGHTNESS CONTROL COMMANDS
${'='.repeat(50)}

VOICE COMMANDS:
  "increase brightness"
  "decrease brightness"
  "set brightness to 50%"
  "set brightness to 80"
  "max brightness"
  "min brightness"
  "what's the brightness?"

EXAMPLES:
  "Make the screen brighter"
  "Dim the screen"
  "Brightness to 100%"

${'='.repeat(50)}
Type any command above in chat to execute.`;
    }

    if (lower === '/sys power') {
      return `POWER & NETWORK COMMANDS
${'='.repeat(50)}

BATTERY:
  "check battery"
  "what's my battery level?"
  "am I plugged in?"

WIFI:
  "turn on wifi"
  "turn off wifi"
  "wifi status"
  "connect to wifi"

BLUETOOTH:
  "turn on bluetooth"
  "turn off bluetooth"
  "bluetooth status"

POWER:
  "shut down computer"
  "restart computer"
  "sleep"
  "lock screen"

${'='.repeat(50)}
Type any command above in chat to execute.`;
    }

    if (lower === '/sys media') {
      return `MEDIA CONTROL COMMANDS
${'='.repeat(50)}

PLAYBACK:
  "play" / "pause"
  "play music"
  "pause music"
  "stop"

NAVIGATION:
  "next track" / "next song"
  "previous track" / "previous song"
  "skip"

EXAMPLES:
  "Play the music"
  "Skip to next song"
  "Pause"

${'='.repeat(50)}
These control system-wide media playback.`;
    }

    if (lower === '/sys modes') {
      return `SYSTEM MODE COMMANDS
${'='.repeat(50)}

DARK MODE:
  "enable dark mode"
  "disable dark mode"
  "turn on dark mode"
  "turn off dark mode"

NIGHT LIGHT:
  "enable night light"
  "disable night light"
  "turn on blue light filter"

DO NOT DISTURB:
  "enable do not disturb"
  "disable do not disturb"
  "turn on focus mode"

AIRPLANE MODE:
  "enable airplane mode"
  "disable airplane mode"
  "turn on flight mode"

${'='.repeat(50)}
Type any command above in chat to execute.`;
    }

    // =========================================================================
    // WINDOWS
    // =========================================================================
    if (lower === '/windows') {
      return `WINDOW MANAGEMENT COMMANDS
${'='.repeat(50)}

CATEGORIES:
  /win control     Basic window controls
  /win snap        Window snapping & positioning
  /win layout      Multi-window layouts
  /win effects     Transparency & effects
  /win utils       Utilities (minimize all, etc.)

QUICK REFERENCE:
${'─'.repeat(50)}
  "minimize chrome"         "snap code to left"
  "maximize notepad"        "split chrome and code"
  "close spotify"           "make chrome transparent"
  "focus on code"           "minimize all windows"

${'='.repeat(50)}
Type commands naturally in chat to execute.
Example: "minimize chrome" or "snap code to the right"`;
    }

    if (lower === '/win control') {
      return `WINDOW CONTROL COMMANDS
${'='.repeat(50)}

MINIMIZE:
  "minimize chrome"
  "minimize all windows"

MAXIMIZE:
  "maximize notepad"
  "maximize current window"

RESTORE:
  "restore chrome"
  "restore all windows"

CLOSE:
  "close chrome"
  "close spotify"

FOCUS:
  "focus on chrome"
  "switch to code"
  "bring up notepad"

CENTER:
  "center chrome"
  "center current window"

${'='.repeat(50)}
Replace "chrome" with any app name.`;
    }

    if (lower === '/win snap') {
      return `WINDOW SNAPPING COMMANDS
${'='.repeat(50)}

SNAP POSITIONS:
  "snap chrome to left"
  "snap chrome to right"
  "snap chrome to top"
  "snap chrome to bottom"

CORNERS:
  "snap chrome to top-left"
  "snap chrome to top-right"
  "snap chrome to bottom-left"
  "snap chrome to bottom-right"

QUICK SNAP:
  "put chrome on the left"
  "move code to the right side"

${'='.repeat(50)}
Replace "chrome" with any app name.`;
    }

    if (lower === '/win layout') {
      return `MULTI-WINDOW LAYOUT COMMANDS
${'='.repeat(50)}

SPLIT SCREEN:
  "split screen chrome and code"
  "split chrome and notepad"

GRID LAYOUTS:
  "grid layout chrome, code, notepad"
  "tile all windows"

SWAP POSITIONS:
  "swap chrome and code"
  "switch positions of chrome and notepad"

EXAMPLES:
  "Put chrome on left and code on right"
  "Split my screen with chrome and spotify"

${'='.repeat(50)}
Great for multi-tasking!`;
    }

    if (lower === '/win effects') {
      return `WINDOW EFFECTS COMMANDS
${'='.repeat(50)}

TRANSPARENCY:
  "make chrome transparent"
  "make chrome 50% transparent"
  "make chrome solid" (remove transparency)

FULLSCREEN:
  "make chrome fullscreen"
  "exit fullscreen"

PIN/UNPIN (Always on Top):
  "pin chrome" (keep on top)
  "unpin chrome" (normal)

${'='.repeat(50)}
Replace "chrome" with any app name.`;
    }

    if (lower === '/win utils') {
      return `WINDOW UTILITY COMMANDS
${'='.repeat(50)}

MINIMIZE ALL:
  "minimize all windows"
  "hide all windows"

SHOW DESKTOP:
  "show desktop"
  "clear desktop"

UNDO:
  "undo last window change"
  "restore last window"

LIST WINDOWS:
  "list all windows"
  "what windows are open?"

${'='.repeat(50)}`;
    }

    // =========================================================================
    // SCHEDULES
    // =========================================================================
    if (lower === '/schedules' || lower === '/sched') {
      try {
        const res = await api.get('/schedules');
        const all = res.data;
        const active = all.filter(s => s.status === 'active');
        const fired = all.filter(s => s.status === 'fired');
        const cancelled = all.filter(s => s.status === 'cancelled');

        let result = `SCHEDULES\n${'='.repeat(50)}\n\n`;
        
        if (active.length === 0) {
          result += 'No active schedules.\n';
        } else {
          result += `ACTIVE (${active.length}):\n${'─'.repeat(50)}\n`;
          active.forEach((s) => {
            const type = s.type?.toUpperCase() || 'UNKNOWN';
            result += `[${s.id}] ${type}: ${s.message}\n`;
            result += `    Time: ${s.time || '?'} | Speaker: ${s.speaker_id || 'default'}\n`;
            if (s.recur && s.recur !== 'none') {
              result += `    Recurs: ${s.recur}\n`;
            }
          });
        }
        
        result += `\n${'─'.repeat(50)}\n`;
        result += `Active: ${active.length} | Fired: ${fired.length} | Cancelled: ${cancelled.length}\n`;
        result += `\n${'='.repeat(50)}\n`;
        result += `Use /sched create to see how to create schedules.`;
        
        return result;
      } catch (e) {
        return `Error loading schedules: ${e.message}`;
      }
    }

    if (lower === '/sched active') {
      try {
        const res = await api.get('/schedules');
        const active = res.data.filter(s => s.status === 'active');
        
        if (active.length === 0) {
          return 'No active schedules.\n\nCreate one by saying "Set a timer for 10 minutes"';
        }
        
        let result = `ACTIVE SCHEDULES (${active.length})\n${'='.repeat(50)}\n`;
        active.forEach((s) => {
          result += `\n[${s.id}] ${s.type?.toUpperCase()}\n`;
          result += `    Message: ${s.message}\n`;
          result += `    Time: ${s.time}\n`;
          result += `    Speaker: ${s.speaker_id}\n`;
        });
        return result;
      } catch (e) {
        return `Error: ${e.message}`;
      }
    }

    if (lower === '/sched create') {
      return `HOW TO CREATE SCHEDULES
${'='.repeat(50)}

TIMERS:
  "Set a timer for 10 minutes"
  "Set a timer for 2 hours"
  "Timer for 30 seconds"

ALARMS:
  "Set an alarm for 7am"
  "Wake me up at 6:30"
  "Alarm at 9pm"

REMINDERS:
  "Remind me to call mom at 5pm"
  "Remind me in 30 minutes to check the oven"
  "Remind me tomorrow to pay bills"

RECURRING:
  "Every Monday remind me to submit report"
  "Every day at 9am remind me to exercise"
  "Remind me every hour to drink water"

CANCEL:
  "Cancel my timer"
  "Cancel the 5pm reminder"
  "Cancel all reminders"

CHECK:
  "What reminders do I have?"
  "How much time left on my timer?"
  "List my alarms"

${'='.repeat(50)}
Type commands naturally in chat.`;
    }

    // =========================================================================
    // KNOWLEDGE
    // =========================================================================
    if (lower === '/knowledge') {
      try {
        const res = await api.get('/knowledge/stats');
        const stats = res.data;
        
        let result = `KNOWLEDGE BASE\n${'='.repeat(50)}\n\n`;
        result += `Total Chunks:   ${stats.total_chunks || 0}\n`;
        result += `Total Sources:  ${stats.source_count || 0}\n`;
        result += `Storage:        ${stats.storage_mb || 0} MB\n`;
        
        if (stats.sources && stats.sources.length > 0) {
          result += `\nIndexed Files:\n${'─'.repeat(50)}\n`;
          stats.sources.forEach(src => {
            result += `  • ${src}\n`;
          });
        }
        
        result += `\n${'='.repeat(50)}\n`;
        result += `Commands:\n`;
        result += `  /knowledge search X   Search for X\n`;
        result += `  /knowledge files      List indexed files\n`;
        result += `\nTo add knowledge:\n`;
        result += `  Drop files in: seven_data/knowledge/custom/\n`;
        result += `  Supported: .txt, .md, .pdf`;
        
        return result;
      } catch (e) {
        return `Error loading knowledge stats: ${e.message}`;
      }
    }

    if (lower.startsWith('/knowledge search ')) {
      const query = cmd.substring(18).trim();
      if (!query) {
        return '❌ Usage: /knowledge search [query]\n\nExample: /knowledge search machine learning';
      }
      try {
        const res = await api.get(`/knowledge/search?q=${encodeURIComponent(query)}`);
        if (!res.data.results || res.data.results === 'No results found.') {
          return `No results found for "${query}"\n\nMake sure you have indexed some files.`;
        }
        return `KNOWLEDGE SEARCH: "${query}"\n${'='.repeat(50)}\n\n${res.data.results}`;
      } catch (e) {
        return `Error searching: ${e.message}`;
      }
    }

    if (lower === '/knowledge files') {
      try {
        const res = await api.get('/knowledge/stats');
        const stats = res.data;
        
        if (!stats.sources || stats.sources.length === 0) {
          return `No files indexed yet.\n\nTo add knowledge:\n1. Create folder: seven_data/knowledge/custom/\n2. Drop .txt, .md, or .pdf files there\n3. Restart Seven or say "reindex knowledge"`;
        }
        
        let result = `INDEXED FILES (${stats.sources.length})\n${'='.repeat(50)}\n`;
        stats.sources.forEach((src, i) => {
          result += `${i + 1}. ${src}\n`;
        });
        return result;
      } catch (e) {
        return `Error: ${e.message}`;
      }
    }

    if (lower === '/knowledge clear') {
      return `⚠️ CLEAR KNOWLEDGE BASE

This will permanently delete all indexed knowledge.

For safety, please use the Knowledge page to clear.

Dashboard → Knowledge → Clear Knowledge Base`;
    }

    // =========================================================================
    // SPEED
    // =========================================================================
    if (lower === '/speed') {
      try {
        const res = await api.get('/speed');
        const speed = res.data;
        
        if (!speed.count || speed.count === 0) {
          return `LATENCY STATS\n${'='.repeat(50)}\n\nNo data yet.\n\nSend a few messages to collect latency data.`;
        }
        
        return `LATENCY STATS
${'='.repeat(50)}

Model:       ${speed.model}
Streaming:   ${speed.streaming ? 'ON' : 'OFF'}

Samples:     ${speed.count}
Average:     ${speed.avg}ms
Fastest:     ${speed.min}ms
Slowest:     ${speed.max}ms

${'='.repeat(50)}
Lower is better. Average < 2000ms is good.`;
      } catch (e) {
        return `Error loading speed stats: ${e.message}`;
      }
    }

    // =========================================================================
    // HARDWARE
    // =========================================================================
    if (lower === '/hardware') {
      try {
        const res = await api.get('/hardware');
        const hw = res.data;
        
        return `HARDWARE DETECTION
${'='.repeat(50)}

GPU:
  Name:           ${hw.gpu?.name || 'None detected'}
  VRAM:           ${hw.gpu?.vram_gb || 0} GB

MEMORY:
  RAM:            ${hw.ram_gb} GB

CPU:
  Processor:      ${hw.cpu?.processor || 'Unknown'}
  Cores:          ${hw.cpu?.cores || '?'}

OS:               ${hw.os}

${'─'.repeat(50)}
RECOMMENDATION:
  Model:          ${hw.recommended_model}
  Tier:           ${hw.recommended_tier}
  Reason:         ${hw.recommendation_reason}

${'='.repeat(50)}`;
      } catch (e) {
        return `Error loading hardware info: ${e.message}`;
      }
    }

    // =========================================================================
    // TELEMETRY
    // =========================================================================
    if (lower === '/telemetry') {
      return `TELEMETRY (Local Usage Stats)
${'='.repeat(50)}

Your usage data is stored LOCALLY only.

What we track (anonymously):
  • Device ID (random UUID, not tied to you)
  • Country (from IP, then IP deleted)
  • Active hours (session-based)
  • Email (only if you provided it)

What we DON'T track:
  • What you say to Seven
  • What apps you open
  • Your schedules/reminders
  • Your memory/facts
  • Your IP address

Admin dashboard: http://localhost:8888
(Only accessible on your machine)

${'='.repeat(50)}
Your privacy is our priority.`;
    }

    // =========================================================================
    // UNKNOWN COMMAND
    // =========================================================================
    return `❌ Unknown command: ${cmd}

Type /help to see all available commands.

Or just type naturally — Seven will understand!
Example: "What's the weather like?"`;
  },
}));

export default useChat;