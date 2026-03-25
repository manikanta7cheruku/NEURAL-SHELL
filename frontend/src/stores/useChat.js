import { create } from 'zustand';
import api from '../api';

const useChat = create((set, get) => ({
  messages: [],
  sending: false,
  draft: '',

  setDraft: (t) => set({ draft: t }),

  send: async (text, sid = 'default') => {
  if (!text.trim()) return;

  const userMsg = { role: 'user', text, time: new Date() };
  set((s) => ({ messages: [...s.messages, userMsg], sending: true }));
  get().setDraft('');

  try {
    // Check if it's a local command (starts with /)
    if (text.startsWith('/')) {
      const response = await get().handleCommand(text);
      const botMsg = { role: 'assistant', text: response, time: new Date() };
      set((s) => ({ messages: [...s.messages, botMsg], sending: false }));
      return;
    }

    // Normal chat — send to backend
    const r = await api.post('/chat', { text });
    const botMsg = {
      role: 'assistant',
      text: r.data.response,
      actions: r.data.actions || [],
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

  // === HELP ===
  if (lower === '/help') {
    return `SEVEN CONSOLE COMMANDS

Memory:
  /memory          Show all memories (facts + conversations)
  /facts           Show stored facts only
  /convos          Show stored conversations only
  /stats           Show system statistics
  /add fact [text] Manually add a fact
  /delete fact N   Delete fact by index
  /delete convo N  Delete conversation by index
  /clear all       Delete everything (requires confirmation)

Logs & Mood:
  /logs            Show last 10 command logs
  /logs N          Show last N command logs
  /mood            Show current mood state

Speakers (Voice ID):
  /speaker [name]  Switch active speaker profile
  /speakers        List enrolled speakers
  /remove speaker  Remove a speaker's voice print

System Control:
  /system          Show system status (volume, battery, WiFi, etc.)
  /sys [cmd]       Execute system command
    Examples: /sys volume_up, /sys battery, /sys wifi_status

Window Management:
  /windows         List all visible windows
  /window [cmd]    Execute window command
    Examples: /window minimize chrome, /window snap code left

Scheduler:
  /schedules       Show all active/fired/cancelled schedules
  /sched clear     Clear all schedules
  /sched cancel N  Cancel schedule by ID
  /sched test      Create test reminder (fires in 30s)

Knowledge Base:
  /knowledge           Show knowledge stats
  /knowledge search X  Search knowledge base
  /knowledge clear     Clear knowledge base

Hardware & Speed:
  /speed       Show latency stats
  /hardware    Show GPU/RAM/CPU info + recommended model`;
  }

  // === MEMORY ===
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
            result += `[${i}] ${c.text}\n`;
            result += `    User: "${c.user_input}"\n`;
            result += `    Seven: "${c.seven_response}"\n`;
            result += `    Saved: ${c.timestamp} | Speaker: ${c.speaker}\n`;
          });
          result += '='.repeat(50);
        }
      }

      return result;
    } catch (e) {
      return `Error loading memory: ${e.message}`;
    }
  }

  // === STATS ===
  if (lower === '/stats') {
    try {
      const [memRes, logsRes, statusRes] = await Promise.all([
        api.get('/memory/stats'),
        api.get('/commands/log?limit=10'),
        api.get('/status')
      ]);

      const mem = memRes.data;
      const logs = logsRes.data.stats;
      const status = statusRes.data;

      return `SYSTEM STATISTICS
${'='.repeat(50)}
Memory:
  Conversations:  ${mem.total_conversations}
  Facts:          ${mem.total_facts}
  Storage:        ${mem.storage_mb || 0} MB

Commands:
  Total executed: ${logs.total}
  Opens:          ${logs.opens}
  Closes:         ${logs.closes}
  Success rate:   ${logs.success_rate}

Mood:
  Current:        ${status.mood_value?.toFixed(2)} (${status.mood})

Model:
  Active:         ${status.model}
  Streaming:      ${status.streaming ? 'ON' : 'OFF'}
${'='.repeat(50)}`;
    } catch (e) {
      return `Error loading stats: ${e.message}`;
    }
  }

  // === LOGS ===
  if (lower.startsWith('/logs')) {
    try {
      const parts = lower.split(' ');
      const count = parts[1] && !isNaN(parts[1]) ? parseInt(parts[1]) : 10;
      const res = await api.get(`/commands/log?limit=${count}`);
      const logs = res.data.recent;
      const stats = res.data.stats;

      if (!logs || logs.length === 0) {
        return 'No commands logged yet.';
      }

      let result = `COMMAND LOGS (Last ${count})\n${'='.repeat(50)}\n`;
      logs.forEach((log) => {
        const status = log.success ? '✅' : '❌';
        const time = log.timestamp.split(' ')[1]; // Just time portion
        result += `[${time}] ${status} ${log.action} ${log.target}\n`;
      });
      result += `${'─'.repeat(50)}\n`;
      result += `Total: ${stats.total} | Opens: ${stats.opens} | Closes: ${stats.closes} | Success: ${stats.success_rate}\n`;
      result += '='.repeat(50);
      return result;
    } catch (e) {
      return `Error loading logs: ${e.message}`;
    }
  }

  // === MOOD ===
  if (lower === '/mood') {
    try {
      const res = await api.get('/mood');
      const mood = res.data;
      
      // Visual mood bar (text-based)
      const barPos = Math.floor((mood.mood_value + 1) * 15); // Map -1..1 to 0..30
      const bar = Array(30).fill('─');
      if (barPos >= 0 && barPos < 30) bar[barPos] = '●';
      
      return `MOOD ENGINE
${'='.repeat(50)}
Frustrated [${bar.join('')}] Excited
Value: ${mood.mood_value.toFixed(3)} | Label: ${mood.label}
Interactions: ${mood.interaction_count}
${'='.repeat(50)}`;
    } catch (e) {
      return `Error loading mood: ${e.message}`;
    }
  }

  // === ADD FACT ===
  if (lower.startsWith('/add fact ')) {
    const factText = cmd.substring(10).trim();
    if (!factText) {
      return '❌ Usage: /add fact I love pizza';
    }
    try {
      // Store via memory endpoint (you may need to add this endpoint to backend)
      await api.post('/memory/facts', { text: factText, category: 'manual' });
      return `✅ Fact added: "${factText}"`;
    } catch (e) {
      return `Error adding fact: ${e.message}`;
    }
  }

  // === DELETE FACT ===
  if (lower.startsWith('/delete fact ')) {
    const index = parseInt(cmd.substring(13).trim());
    if (isNaN(index)) {
      return '❌ Usage: /delete fact 0';
    }
    try {
      const factsRes = await api.get('/memory/facts');
      const facts = factsRes.data;
      if (index < 0 || index >= facts.length) {
        return `❌ Invalid index. Use 0 to ${facts.length - 1}`;
      }
      const fact = facts[index];
      await api.delete(`/memory/facts/${fact.id}`);
      return `✅ Deleted: "${fact.text}"`;
    } catch (e) {
      return `Error deleting fact: ${e.message}`;
    }
  }

  // === DELETE CONVO ===
  if (lower.startsWith('/delete convo ')) {
    const index = parseInt(cmd.substring(14).trim());
    if (isNaN(index)) {
      return '❌ Usage: /delete convo 0';
    }
    try {
      const convosRes = await api.get('/memory/conversations?limit=100');
      const convos = convosRes.data.conversations;
      if (index < 0 || index >= convos.length) {
        return `❌ Invalid index. Use 0 to ${convos.length - 1}`;
      }
      const convo = convos[index];
      await api.delete(`/memory/conversations/${convo.id}`);
      return `✅ Deleted conversation`;
    } catch (e) {
      return `Error deleting conversation: ${e.message}`;
    }
  }

  // === CLEAR ALL ===
  if (lower === '/clear all') {
    return '⚠️ Use the Settings page to clear all memory (safety measure)';
  }

  // === SPEAKERS ===
  if (lower === '/speakers') {
    try {
      const res = await api.get('/speakers');
      if (!res.data.enabled) {
        return 'Voice ID not enabled. No speakers enrolled yet.\nUse voice mode and say "Enroll my voice"';
      }
      const speakers = res.data.speakers;
      if (speakers.length === 0) {
        return 'No speakers enrolled yet.';
      }
      let result = `ENROLLED SPEAKERS\n${'='.repeat(50)}\n`;
      speakers.forEach((s) => {
        result += `• ${s.name}\n`;
      });
      result += '='.repeat(50);
      return result;
    } catch (e) {
      return `Error loading speakers: ${e.message}`;
    }
  }

  // === SYSTEM ===
  if (lower === '/system') {
    return 'System status commands not yet implemented in web console.\nUse voice mode or test_chat.py for full system control.';
  }

  // === WINDOWS ===
  if (lower === '/windows') {
    return 'Window management not yet implemented in web console.\nUse voice mode or test_chat.py for window control.';
  }

  // === SCHEDULES ===
  if (lower === '/schedules') {
    try {
      const res = await api.get('/schedules');
      const all = res.data;
      const active = all.filter(s => s.status === 'active');
      const fired = all.filter(s => s.status === 'fired');
      const cancelled = all.filter(s => s.status === 'cancelled');

      if (active.length === 0) {
        return 'No active schedules.';
      }

      let result = `ACTIVE SCHEDULES\n${'='.repeat(50)}\n`;
      active.forEach((s) => {
        result += `[${s.id}] ${s.type.toUpperCase()}: ${s.message}\n`;
        result += `    Time: ${s.time} | Speaker: ${s.speaker_id}\n`;
        if (s.recur && s.recur !== 'none') {
          result += `    Recurs: ${s.recur}\n`;
        }
      });
      result += `${'─'.repeat(50)}\n`;
      result += `Active: ${active.length} | Fired: ${fired.length} | Cancelled: ${cancelled.length}\n`;
      result += '='.repeat(50);
      return result;
    } catch (e) {
      return `Error loading schedules: ${e.message}`;
    }
  }

  // === KNOWLEDGE ===
  if (lower === '/knowledge') {
    try {
      const res = await api.get('/knowledge/stats');
      const stats = res.data;
      let result = `KNOWLEDGE BASE\n${'='.repeat(50)}\n`;
      result += `Total chunks:  ${stats.total_chunks}\n`;
      result += `Sources:       ${stats.source_count}\n`;
      if (stats.sources && stats.sources.length > 0) {
        stats.sources.forEach(src => {
          result += `  • ${src}\n`;
        });
      }
      result += `Storage:       ${stats.storage_mb} MB\n`;
      result += '='.repeat(50);
      return result;
    } catch (e) {
      return `Error loading knowledge stats: ${e.message}`;
    }
  }

  if (lower.startsWith('/knowledge search ')) {
    const query = cmd.substring(18).trim();
    if (!query) {
      return '❌ Usage: /knowledge search quantum physics';
    }
    try {
      const res = await api.get(`/knowledge/search?q=${encodeURIComponent(query)}`);
      return `Knowledge search results for "${query}":\n\n${res.data.results}`;
    } catch (e) {
      return `Error searching knowledge: ${e.message}`;
    }
  }

  if (lower === '/knowledge clear') {
    return '⚠️ Use the Knowledge page to clear the knowledge base (safety measure)';
  }

  // === SPEED ===
  if (lower === '/speed') {
    try {
      const res = await api.get('/speed');
      const speed = res.data;
      if (speed.count === 0) {
        return 'No latency data yet. Send a few messages first.';
      }
      return `SPEED & LATENCY
${'='.repeat(50)}
Model:      ${speed.model}
Streaming:  ${speed.streaming ? 'ON' : 'OFF'}
Samples:    ${speed.count}
Average:    ${speed.avg}ms
Fastest:    ${speed.min}ms
Slowest:    ${speed.max}ms
${'='.repeat(50)}`;
    } catch (e) {
      return `Error loading speed stats: ${e.message}`;
    }
  }

  // === HARDWARE ===
  if (lower === '/hardware') {
    try {
      const res = await api.get('/hardware');
      const hw = res.data;
      return `HARDWARE DETECTION
${'='.repeat(50)}
GPU:         ${hw.gpu?.name || 'None'}
VRAM:        ${hw.gpu?.vram_gb || 0} GB
RAM:         ${hw.ram_gb} GB
CPU:         ${hw.cpu?.processor || '?'} (${hw.cpu?.cores || '?'} cores)
OS:          ${hw.os}
${'─'.repeat(50)}
Recommended: ${hw.recommended_model}
Tier:        ${hw.recommended_tier}
Reason:      ${hw.recommendation_reason}
${'='.repeat(50)}`;
    } catch (e) {
      return `Error loading hardware info: ${e.message}`;
    }
  }

  // === UNKNOWN COMMAND ===
  return `Unknown command: ${cmd}\nType /help to see all available commands.`;
},

  clear: () => set({ messages: [], draft: '' }),
}));

export default useChat;