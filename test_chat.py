"""
=============================================================================
PROJECT SEVEN - test_chat.py (V1.6 - Developer Console)
=============================================================================
"""

import brain
import hands.core as core
import re
import colorama
from colorama import Fore
from memory import seven_memory
from memory.command_log import command_log
from memory.mood import mood_engine
from ears.voice_id import get_enrolled_speakers, remove_speaker, is_voice_id_enabled
from hands.system import manage_system, get_system_status
from hands.scheduler import manage_schedule, get_all_schedules, get_active_count, list_schedules

colorama.init(autoreset=True)
# V1.2: Simulated speaker for text mode
active_speaker = "default"
# V1.8: Start scheduler background thread (uses print instead of speak in text mode)
def _test_speak(text):
    """Speak callback for test mode — prints AND speaks aloud."""
    print(Fore.YELLOW + f"\n  🔔 [SCHEDULER FIRES]: {text}")
    try:
        import mouth
        mouth.speak(text)
    except Exception as e:
        print(Fore.RED + f"  [SPEAK ERROR] {e}")
    print(Fore.YELLOW + f"\nYOU: ", end="")

from hands.scheduler import start_background as _start_sched
_start_sched(speak_fn=_test_speak)

print(Fore.CYAN + "=" * 60)
print(Fore.CYAN + "  SEVEN TEXT DEBUGGER (V1.8 - THE SCHEDULER)")
print(Fore.CYAN + "=" * 60)
print(Fore.WHITE + "  Commands: /memory | /facts | /convos | /stats")
print(Fore.WHITE + "  Commands: /logs | /logs N | /mood")
print(Fore.WHITE + "  Commands: /add fact [text] | /delete fact [n]")
print(Fore.WHITE + "  Commands: /delete convo [n]")
print(Fore.WHITE + "  Commands: /clear all | /clear logs | /clear mood | quit")
print(Fore.WHITE + "  Commands: /help (show all commands)")
print(Fore.WHITE + "  Commands: /speaker [name] | /speakers | /remove speaker [name]")
print(Fore.WHITE + "  Commands: /windows | /window [cmd]")
print(Fore.WHITE + "  Commands: /system | /sys [cmd]")
print(Fore.WHITE + "  Commands: /schedules | /sched [cmd]")
print(Fore.CYAN + "=" * 60)

# Show mood on startup
mood_status = mood_engine.get_status()
print(Fore.MAGENTA + f"  Mood: {mood_status['mood_value']:.2f} ({mood_status['label']})")

# V1.2: Voice ID status
if is_voice_id_enabled():
    speakers = get_enrolled_speakers()
    print(Fore.CYAN + f"  Voice ID: Active | Enrolled: {', '.join(speakers)}")
else:
    print(Fore.YELLOW + "  Voice ID: No speakers enrolled (voice mode only)")
print(Fore.CYAN + f"  Active speaker: {active_speaker}")
print()


def show_facts():
    if seven_memory.user_facts.count() == 0:
        print(Fore.YELLOW + "\n  No facts stored yet.")
        return
    all_facts = seven_memory.user_facts.get()
    print(Fore.GREEN + f"\n  {'='*50}")
    print(Fore.GREEN + f"  STORED FACTS ({len(all_facts['documents'])} total)")
    print(Fore.GREEN + f"  {'='*50}")
    for i, doc in enumerate(all_facts['documents']):
        meta = all_facts['metadatas'][i]
        fact_id = all_facts['ids'][i]
        category = meta.get('category', '?')
        timestamp = meta.get('timestamp', '?')
        print(Fore.GREEN + f"  [{i}] ({category}) {doc}")
        print(Fore.WHITE + f"       Saved: {timestamp} | ID: {fact_id}")
    print(Fore.GREEN + f"  {'='*50}")


def show_conversations():
    if seven_memory.conversations.count() == 0:
        print(Fore.YELLOW + "\n  No conversations stored yet.")
        return
    all_convos = seven_memory.conversations.get()
    total = len(all_convos['documents'])
    print(Fore.MAGENTA + f"\n  {'='*50}")
    print(Fore.MAGENTA + f"  STORED CONVERSATIONS ({total} total)")
    print(Fore.MAGENTA + f"  {'='*50}")
    start = max(0, total - 20)
    for i in range(start, total):
        doc = all_convos['documents'][i]
        meta = all_convos['metadatas'][i]
        timestamp = meta.get('timestamp', '?')
        print(Fore.MAGENTA + f"  [{i}] {doc}")
        print(Fore.WHITE + f"       Saved: {timestamp}")
    if start > 0:
        print(Fore.YELLOW + f"\n  (Showing last 20 of {total}. Older conversations hidden.)")
    print(Fore.MAGENTA + f"  {'='*50}")


def show_all_memory():
    show_facts()
    show_conversations()


def show_stats():
    stats = seven_memory.get_stats()
    cmd_stats = command_log.get_stats()
    m_status = mood_engine.get_status()

    print(Fore.CYAN + f"\n  {'='*50}")
    print(Fore.CYAN + f"  SYSTEM STATISTICS (V1.2)")
    print(Fore.CYAN + f"  {'='*50}")
    print(Fore.CYAN + f"  Conversations:     {stats['total_conversations']}")
    print(Fore.CYAN + f"  Facts:             {stats['total_facts']}")
    print(Fore.CYAN + f"  Storage:           {stats['storage_path']}")
    print(Fore.CYAN + f"  {'─'*50}")
    print(Fore.CYAN + f"  Commands executed: {cmd_stats['total']}")
    print(Fore.CYAN + f"  Opens:             {cmd_stats['opens']}")
    print(Fore.CYAN + f"  Closes:            {cmd_stats['closes']}")
    print(Fore.CYAN + f"  Success rate:      {cmd_stats['success_rate']}")
    print(Fore.CYAN + f"  {'─'*50}")
    print(Fore.MAGENTA + f"  Current mood:      {m_status['mood_value']:.2f} ({m_status['label']})")
    print(Fore.MAGENTA + f"  Interactions:      {m_status['interaction_count']}")
    print(Fore.CYAN + f"  {'='*50}")


def show_logs(count=10):
    """Show recent command logs."""
    print(Fore.CYAN + f"\n  {'='*50}")
    print(Fore.CYAN + f"  COMMAND LOGS (Last {count})")
    print(Fore.CYAN + f"  {'='*50}")

    recent = command_log.get_recent(count)
    if not recent:
        print(Fore.YELLOW + "  No commands logged yet.")
        print(Fore.CYAN + f"  {'='*50}")
        return

    for entry in recent:
        ts = entry["timestamp"][11:]  # Just time portion
        action = entry["action"]
        target = entry["target"]
        status = "✅" if entry["success"] else "❌"
        detail = entry.get("detail", "")
        print(Fore.CYAN + f"  [{ts}] {status} {action} {target}  {detail}")

    # Summary
    stats = command_log.get_stats()
    print(Fore.CYAN + f"  {'─'*50}")
    print(Fore.CYAN + f"  Total: {stats['total']} | Opens: {stats['opens']} | Closes: {stats['closes']} | Rate: {stats['success_rate']}")

    most_used = command_log.get_most_used(3)
    if most_used:
        apps = ", ".join([f"{app}({c})" for app, c in most_used])
        print(Fore.CYAN + f"  Most used: {apps}")
    print(Fore.CYAN + f"  {'='*50}")


def show_mood():
    """Show current mood state with visual bar."""
    status = mood_engine.get_status()
    mood_val = status["mood_value"]

    print(Fore.MAGENTA + f"\n  {'='*50}")
    print(Fore.MAGENTA + f"  MOOD ENGINE")
    print(Fore.MAGENTA + f"  {'='*50}")

    # Visual mood bar
    bar_pos = int((mood_val + 1) * 15)  # Map -1..1 to 0..30
    bar = list("──────────────────────────────")
    if 0 <= bar_pos < 30:
        bar[bar_pos] = "●"
    bar_str = "".join(bar)
    print(Fore.MAGENTA + f"  Frustrated [{bar_str}] Excited")
    print(Fore.MAGENTA + f"  Value: {mood_val:.3f} | Label: {status['label']}")
    print(Fore.MAGENTA + f"  Interactions: {status['interaction_count']}")

    if status["recent_changes"]:
        print(Fore.MAGENTA + f"\n  Recent mood shifts:")
        for change in status["recent_changes"]:
            direction = "↑" if change["delta"] > 0 else "↓"
            print(Fore.WHITE + f"    {direction} {change['delta']:+.3f} → {change['new_mood']:.3f} ({change['label']}) — \"{change['text']}\"")
    print(Fore.MAGENTA + f"  {'='*50}")


def delete_fact(index):
    try:
        all_facts = seven_memory.user_facts.get()
        if index < 0 or index >= len(all_facts['ids']):
            print(Fore.RED + f"  ❌ Invalid index. Use 0 to {len(all_facts['ids'])-1}")
            return
        fact_text = all_facts['documents'][index]
        fact_id = all_facts['ids'][index]
        print(Fore.YELLOW + f"  Deleting: {fact_text}")
        confirm = input(Fore.YELLOW + "  Are you sure? (y/n): ").strip().lower()
        if confirm == 'y':
            seven_memory.user_facts.delete(ids=[fact_id])
            print(Fore.GREEN + "  ✅ Fact deleted.")
        else:
            print(Fore.WHITE + "  Cancelled.")
    except Exception as e:
        print(Fore.RED + f"  ❌ Error: {e}")


def delete_conversation(index):
    try:
        all_convos = seven_memory.conversations.get()
        if index < 0 or index >= len(all_convos['ids']):
            print(Fore.RED + f"  ❌ Invalid index. Use 0 to {len(all_convos['ids'])-1}")
            return
        convo_text = all_convos['documents'][index]
        convo_id = all_convos['ids'][index]
        print(Fore.YELLOW + f"  Deleting: {convo_text[:80]}...")
        confirm = input(Fore.YELLOW + "  Are you sure? (y/n): ").strip().lower()
        if confirm == 'y':
            seven_memory.conversations.delete(ids=[convo_id])
            print(Fore.GREEN + "  ✅ Conversation deleted.")
        else:
            print(Fore.WHITE + "  Cancelled.")
    except Exception as e:
        print(Fore.RED + f"  ❌ Error: {e}")


def add_manual_fact(fact_text):
    if not fact_text.strip():
        print(Fore.RED + "  ❌ Empty fact. Usage: /add fact I love pizza")
        return
    seven_memory.store_fact(fact_text, category="manual")
    print(Fore.GREEN + f"  ✅ Fact added: '{fact_text}'")


def clear_all_memory():
    print(Fore.RED + "\n  ⚠️  WARNING: This will delete ALL memories permanently!")
    print(Fore.RED + "  This cannot be undone.")
    confirm = input(Fore.RED + "  Type 'DELETE EVERYTHING' to confirm: ").strip()
    if confirm == "DELETE EVERYTHING":
        seven_memory.clear_all()
        brain.reset_session()
        command_log.clear()
        mood_engine.reset()
        print(Fore.GREEN + "  ✅ All memories, logs, and mood cleared. Clean slate.")
    else:
        print(Fore.WHITE + "  Cancelled.")


# =============================================================================
# MAIN LOOP
# =============================================================================

while True:
    user_input = input(Fore.YELLOW + "\nYOU: ")

    if user_input.lower() in ["quit", "exit"]:
        break

    if not user_input.strip():
        continue

    cmd = user_input.lower().strip()

    if cmd == "/memory":
        show_all_memory()
        continue

    if cmd == "/facts":
        show_facts()
        continue

    if cmd == "/convos":
        show_conversations()
        continue

    if cmd == "/stats":
        show_stats()
        continue

    #1.2

    print(Fore.CYAN + f"  {'─'*50}")
    enrolled = get_enrolled_speakers()
    print(Fore.CYAN + f"  Enrolled speakers: {len(enrolled)}")
    if enrolled:
        print(Fore.CYAN + f"  Speakers: {', '.join(enrolled)}")
    print(Fore.CYAN + f"  Active speaker:    {active_speaker}")


    #Add /speaker, /speakers, /remove speaker commands
    if cmd.startswith("/speaker ") and not cmd.startswith("/speakers"):
        new_speaker = user_input[9:].strip().lower()
        if new_speaker:
            active_speaker = new_speaker
            print(Fore.GREEN + f"  ✅ Active speaker set to: {active_speaker}")
            print(Fore.WHITE + f"  (Memory will be stored/searched under '{active_speaker}')")
        else:
            print(Fore.RED + "  ❌ Usage: /speaker mani")
        print()
        continue

    if cmd == "/speakers":
        enrolled = get_enrolled_speakers()
        print(Fore.CYAN + f"\n  {'='*50}")
        print(Fore.CYAN + f"  ENROLLED SPEAKERS")
        print(Fore.CYAN + f"  {'='*50}")
        if enrolled:
            for s in enrolled:
                marker = " ← active" if s == active_speaker else ""
                print(Fore.CYAN + f"  • {s}{marker}")
        else:
            print(Fore.YELLOW + "  No speakers enrolled yet.")
            print(Fore.WHITE + "  Use voice mode (Run_Seven.bat) and say 'Enroll my voice'")
        print(Fore.CYAN + f"  {'─'*50}")
        print(Fore.WHITE + f"  Active speaker (text mode): {active_speaker}")
        print(Fore.WHITE + f"  Use /speaker [name] to switch in text mode")
        print(Fore.CYAN + f"  {'='*50}")
        continue

    if cmd.startswith("/remove speaker "):
        name = cmd.split("/remove speaker ")[1].strip()
        if name:
            confirm = input(Fore.YELLOW + f"  Remove speaker '{name}'? (y/n): ").strip().lower()
            if confirm == 'y':
                remove_speaker(name)
                print(Fore.GREEN + f"  ✅ Speaker '{name}' removed.")
            else:
                print(Fore.WHITE + "  Cancelled.")
        else:
            print(Fore.RED + "  ❌ Usage: /remove speaker mani")
        continue

     # --- V1.6: NEW COMMANDS ---
    if cmd == "/help":
        print(Fore.CYAN + f"\n  {'='*50}")
        print(Fore.CYAN + f"  SEVEN DEVELOPER CONSOLE — COMMANDS")
        print(Fore.CYAN + f"  {'='*50}")
        print(Fore.WHITE + "  /memory          Show all memories (facts + conversations)")
        print(Fore.WHITE + "  /facts           Show stored facts only")
        print(Fore.WHITE + "  /convos          Show stored conversations only")
        print(Fore.WHITE + "  /stats           Show system statistics")
        print(Fore.WHITE + "  /logs            Show last 10 command logs")
        print(Fore.WHITE + "  /logs N          Show last N command logs")
        print(Fore.WHITE + "  /mood            Show current mood state")
        print(Fore.WHITE + "  /add fact [text]  Manually add a fact")
        print(Fore.WHITE + "  /delete fact N   Delete fact by index")
        print(Fore.WHITE + "  /delete convo N  Delete conversation by index")
        print(Fore.WHITE + "  /clear all       Delete everything (memory + logs + mood)")
        print(Fore.WHITE + "  /clear logs      Clear command logs only")
        print(Fore.WHITE + "  /clear mood      Reset mood to neutral")
        print(Fore.WHITE + "  /speaker [name]  Switch active speaker profile (text mode)")
        print(Fore.WHITE + "  /speakers        List enrolled speakers")
        print(Fore.WHITE + "  /remove speaker  Remove a speaker's voice print")
        print(Fore.WHITE + "  /windows         List all visible windows")
        print(Fore.WHITE + "  /window [cmd]    Test window command (e.g., /window minimize chrome)")
        print(Fore.WHITE + "                   Actions: focus minimize maximize restore snap center")
        print(Fore.WHITE + "                   pin unpin fullscreen transparent solid swap undo list")
        print(Fore.WHITE + "")
        print(Fore.WHITE + "")
        print(Fore.CYAN +  "  --- Scheduler (V1.8) ---")
        print(Fore.WHITE + "  /schedules       Show all schedules (active, fired, cancelled)")
        print(Fore.WHITE + "  /sched clear     Clear all schedules")
        print(Fore.WHITE + "  /sched cancel N  Cancel schedule by ID")
        print(Fore.WHITE + "  /sched cancel X  Cancel by matching text")
        print(Fore.WHITE + "  /sched test      Create test reminder (fires in 30 seconds)")
        print(Fore.WHITE + "")
        print(Fore.CYAN +  "  --- Natural Language Scheduler ---")
        print(Fore.WHITE + '  "Set a timer for 10 minutes"')
        print(Fore.WHITE + '  "Remind me to call Mom at 5pm"')
        print(Fore.WHITE + '  "Wake me up at 7am"')
        print(Fore.WHITE + '  "Remind me in 30 minutes to check the oven"')
        print(Fore.WHITE + '  "Schedule a meeting with John on Friday at 3pm"')
        print(Fore.WHITE + '  "Every Monday remind me to submit report"')
        print(Fore.WHITE + '  "Cancel my 5pm reminder"')
        print(Fore.WHITE + '  "What reminders do I have?"')
        print(Fore.WHITE + '  "How much time left on my timer?"')
        print(Fore.CYAN +  "  --- System Control (V1.7) ---")
        print(Fore.WHITE + "  /system          Show system status (volume, brightness, battery, WiFi)")
        print(Fore.WHITE + "  /sys [cmd]       Test system command (e.g., /sys volume_up)")
        print(Fore.WHITE + "                   Volume: volume_up volume_down volume_set volume_mute volume_get")
        print(Fore.WHITE + "                   Brightness: brightness_up brightness_down brightness_set brightness_get")
        print(Fore.WHITE + "                   Battery: battery")
        print(Fore.WHITE + "                   WiFi: wifi_status wifi_on wifi_off")
        print(Fore.WHITE + "                   Bluetooth: bluetooth_on bluetooth_off bluetooth_status")
        print(Fore.WHITE + "                   Media: media_play_pause media_next media_prev media_stop")
        print(Fore.WHITE + "                   Modes: dark_mode_on/off night_light_on/off dnd_on/off airplane_on/off")
        print(Fore.WHITE + "  quit / exit      Exit the console")
        print(Fore.CYAN + f"  {'='*50}")
        continue
    if cmd == "/logs" or cmd.startswith("/logs "):
        parts = cmd.split()
        count = 10
        if len(parts) > 1 and parts[1].isdigit():
            count = int(parts[1])
        show_logs(count)
        continue

    if cmd == "/mood":
        show_mood()
        continue

    if cmd == "/clear logs":
        command_log.clear()
        print(Fore.GREEN + "  ✅ Command logs cleared.")
        continue

    if cmd == "/clear mood":
        mood_engine.reset()
        print(Fore.GREEN + "  ✅ Mood reset to neutral.")
        continue
    # --- END V1.6 NEW COMMANDS ---

    if cmd.startswith("/add fact "):
        fact_text = user_input[10:].strip()
        add_manual_fact(fact_text)
        continue

    if cmd.startswith("/delete fact "):
        try:
            index = int(cmd.split("/delete fact ")[1])
            delete_fact(index)
        except ValueError:
            print(Fore.RED + "  ❌ Usage: /delete fact 0")
        continue

    if cmd.startswith("/delete convo "):
        try:
            index = int(cmd.split("/delete convo ")[1])
            delete_conversation(index)
        except ValueError:
            print(Fore.RED + "  ❌ Usage: /delete convo 0")
        continue

    if cmd == "/clear all":
        clear_all_memory()
        continue

    if cmd == "/windows":
        from hands.windows import get_window_list
        windows = get_window_list()
        print(Fore.CYAN + f"\n  {'='*50}")
        print(Fore.CYAN + f"  VISIBLE WINDOWS ({len(windows)} total)")
        print(Fore.CYAN + f"  {'='*50}")
        for i, (hwnd, title) in enumerate(windows):
            print(Fore.CYAN + f"  [{i}] {title}")
            print(Fore.WHITE + f"       hwnd: {hwnd}")
        print(Fore.CYAN + f"  {'='*50}")
        continue

    if cmd == "/schedules":
        print(Fore.CYAN + f"\n  {'='*50}")
        print(Fore.CYAN + f"  ACTIVE SCHEDULES (V1.8)")
        print(Fore.CYAN + f"  {'='*50}")
        all_sched = get_all_schedules()
        active = [s for s in all_sched if s["status"] == "active"]
        fired = [s for s in all_sched if s["status"] == "fired"]
        cancelled = [s for s in all_sched if s["status"] == "cancelled"]
        
        if not active:
            print(Fore.YELLOW + "  No active schedules.")
        else:
            for s in active:
                stype = s["type"].upper()
                msg = s.get("message", "")
                time_str = s.get("time", "?")
                recur = s.get("recur", "none")
                speaker = s.get("speaker_id", "?")
                sid = s.get("id", "?")
                recur_tag = f" [RECUR: {recur}]" if recur != "none" else ""
                print(Fore.GREEN + f"  [{sid}] {stype}: {msg}")
                print(Fore.WHITE + f"       Time: {time_str} | Speaker: {speaker}{recur_tag}")
        
        print(Fore.CYAN + f"  {'─'*50}")
        print(Fore.CYAN + f"  Active: {len(active)} | Fired: {len(fired)} | Cancelled: {len(cancelled)} | Total: {len(all_sched)}")
        print(Fore.CYAN + f"  {'='*50}")
        continue

    if cmd.startswith("/sched "):
        sched_cmd = cmd[7:].strip()
        
        if sched_cmd == "clear":
            confirm = input(Fore.YELLOW + "  Clear all schedules? (y/n): ").strip().lower()
            if confirm == 'y':
                success, msg = manage_schedule({"action": "cancel", "cancel_type": "all"})
                print(Fore.GREEN + f"  ✅ {msg}" if success else Fore.RED + f"  ❌ {msg}")
            else:
                print(Fore.WHITE + "  Cancelled.")
            continue
        
        if sched_cmd.startswith("cancel "):
            cancel_arg = sched_cmd[7:].strip()
            if cancel_arg.isdigit():
                success, msg = manage_schedule({"action": "cancel", "id": cancel_arg})
            else:
                success, msg = manage_schedule({"action": "cancel", "match": cancel_arg})
            print(Fore.GREEN + f"  ✅ {msg}" if success else Fore.RED + f"  ❌ {msg}")
            continue
        
        if sched_cmd == "test":
            # Quick test: reminder 30 seconds from now
            from datetime import datetime, timedelta
            test_time = datetime.now() + timedelta(seconds=30)
            success, msg = manage_schedule({
                "action": "reminder",
                "time": f"in_30_seconds",
                "message": "test_reminder_from_dev_console",
                "speaker_id": active_speaker
            })
            print(Fore.GREEN + f"  ✅ {msg}" if success else Fore.RED + f"  ❌ {msg}")
            print(Fore.WHITE + "  (Will fire in ~30 seconds. Check console for output.)")
            continue
        
        print(Fore.RED + "  ❌ Usage:")
        print(Fore.WHITE + "    /sched clear          Clear all schedules")
        print(Fore.WHITE + "    /sched cancel 3       Cancel schedule by ID")
        print(Fore.WHITE + "    /sched cancel [text]  Cancel by matching text")
        print(Fore.WHITE + "    /sched test           Create test reminder (30s)")
        continue

    if cmd == "/system":
        print(Fore.CYAN + f"\n  {'='*50}")
        print(Fore.CYAN + f"  SYSTEM STATUS (V1.7)")
        print(Fore.CYAN + f"  {'='*50}")
        status = get_system_status()
        for line in status.split("\n"):
            print(Fore.CYAN + f"  {line}")
        print(Fore.CYAN + f"  {'='*50}")
        continue

    if cmd.startswith("/sys "):
        # Direct system command: /sys volume_up
        # /sys volume_set 50
        # /sys battery
        # /sys media_next
        sys_cmd = cmd[5:].strip()
        print(Fore.CYAN + f"  [SYS TEST] Command: {sys_cmd}")
        
        parts = sys_cmd.split()
        if not parts:
            print(Fore.RED + "  ❌ Usage: /sys volume_up")
            print(Fore.WHITE + "  Actions: volume_up volume_down volume_set volume_mute volume_unmute volume_get")
            print(Fore.WHITE + "           brightness_up brightness_down brightness_set brightness_get")
            print(Fore.WHITE + "           battery wifi_status wifi_on wifi_off")
            print(Fore.WHITE + "           bluetooth_on bluetooth_off bluetooth_status")
            print(Fore.WHITE + "           media_play_pause media_next media_prev media_stop")
            print(Fore.WHITE + "           dark_mode_on dark_mode_off night_light_on night_light_off")
            print(Fore.WHITE + "           dnd_on dnd_off airplane_on airplane_off")
            print(Fore.WHITE + "  Examples:")
            print(Fore.WHITE + "    /sys volume_up")
            print(Fore.WHITE + "    /sys volume_set 50")
            print(Fore.WHITE + "    /sys battery")
            print(Fore.WHITE + "    /sys media_next")
            print(Fore.WHITE + "    /sys dark_mode_on")
            continue
        
        params = {"action": parts[0]}
        if len(parts) >= 2:
            params["value"] = parts[1]
        
        success, msg = manage_system(params)
        if success:
            print(Fore.GREEN + f"  ✅ {msg}")
        else:
            print(Fore.RED + f"  ❌ {msg}")
        continue

    if cmd.startswith("/window "):
        # Direct window command: /window minimize chrome
        # /window snap chrome left
        # /window layout split chrome,code
        # /window focus notepad
        # /window minimize_all
        # /window show_desktop
        window_cmd = cmd[8:].strip()
        print(Fore.CYAN + f"  [WINDOW TEST] Command: {window_cmd}")
        
        # Parse into params dict
        parts = window_cmd.split()
        if not parts:
            print(Fore.RED + "  ❌ Usage: /window minimize chrome")
            print(Fore.WHITE + "  Actions: focus, minimize, maximize, restore, snap, center")
            print(Fore.WHITE + "           minimize_all, show_desktop, layout, swap")
            print(Fore.WHITE + "           pin, unpin, fullscreen, transparent, solid")
            print(Fore.WHITE + "           close_window, undo, list")
            print(Fore.WHITE + "  Examples:")
            print(Fore.WHITE + "    /window focus chrome")
            print(Fore.WHITE + "    /window snap chrome left")
            print(Fore.WHITE + "    /window layout split chrome,code")
            print(Fore.WHITE + "    /window minimize_all")
            continue
        
        from hands.windows import manage_window
        
        action = parts[0]
        params = {"action": action}
        
        # No-target commands
        if action in ["minimize_all", "show_desktop", "undo", "list"]:
            pass
        elif action == "layout":
            if len(parts) >= 3:
                params["mode"] = parts[1]
                params["targets"] = parts[2]
            else:
                print(Fore.RED + "  ❌ Usage: /window layout split chrome,code")
                continue
        elif action == "snap":
            if len(parts) >= 3:
                params["target"] = parts[1]
                params["position"] = parts[2]
            elif len(parts) == 2:
                params["target"] = parts[1]
                params["position"] = "left"
            else:
                print(Fore.RED + "  ❌ Usage: /window snap chrome left")
                continue
        elif action == "swap":
            if len(parts) >= 2:
                params["targets"] = parts[1]
            else:
                print(Fore.RED + "  ❌ Usage: /window swap chrome,notepad")
                continue
        elif action == "transparent":
            if len(parts) >= 2:
                params["target"] = parts[1]
                # Accept: /window transparent chrome 0.5
                # Accept: /window transparent chrome more
                # Accept: /window transparent chrome less
                params["opacity"] = parts[2] if len(parts) >= 3 else "0.8"
            else:
                print(Fore.RED + "  ❌ Usage: /window transparent chrome 0.7")
                print(Fore.WHITE + "         /window transparent chrome more")
                print(Fore.WHITE + "         /window transparent chrome less")
                continue
        elif action == "solid":
            if len(parts) >= 2:
                params["target"] = parts[1]
            else:
                print(Fore.RED + "  ❌ Usage: /window solid chrome")
                continue
        elif action == "move_monitor":
            if len(parts) >= 3:
                params["target"] = parts[1]
                params["monitor"] = parts[2]
            else:
                print(Fore.RED + "  ❌ Usage: /window move_monitor chrome 1")
                continue
        elif action == "resize":
            if len(parts) >= 4:
                params["target"] = parts[1]
                params["width"] = parts[2]
                params["height"] = parts[3]
            else:
                print(Fore.RED + "  ❌ Usage: /window resize chrome 800 600")
                continue
        else:
            # Simple: focus, minimize, maximize, restore, center
            if len(parts) >= 2:
                params["target"] = " ".join(parts[1:])
            else:
                print(Fore.RED + f"  ❌ Usage: /window {action} <target>")
                continue
        
        success, msg = manage_window(params)
        if success:
            print(Fore.GREEN + f"  ✅ {msg}")
        else:
            print(Fore.RED + f"  ❌ {msg}")
        continue

    # --- NORMAL CHAT ---
    print(Fore.MAGENTA + "Seven is thinking...")
    response = brain.think(user_input, speaker_id=active_speaker)
    print(Fore.GREEN + f"SEVEN: {response}")

    # Show mood inline after each response
    m_status = mood_engine.get_status()
    speaker_tag = f" | speaker: {active_speaker}" if active_speaker != "default" else ""
    print(Fore.MAGENTA + f"  [mood: {m_status['mood_value']:.2f} ({m_status['label']}){speaker_tag}]")


        # --- STORE CONVERSATION IN MEMORY ---
    should_store = True
    if response.strip().startswith("###"):
        should_store = False
    if len(user_input.strip()) <= 3:
        should_store = False
    if user_input.lower().strip() in ["hi", "hello", "hey"]:
        should_store = False
    cmd_words = ["open", "close", "start", "kill", "launch",
                 "minimize", "maximize", "maximise", "restore", "snap",
                 "switch to", "bring up", "focus", "center", "centre",
                 "put", "show desktop", "hide all",
                 "set a timer", "set an alarm", "set alarm", "remind me",
                 "wake me up", "cancel my", "cancel the", "cancel all",
                 "schedule a meeting", "clear all timers"]
    if any(w in user_input.lower() for w in cmd_words):
        should_store = False
    # Don't store identity responses (they pollute memory with duplicates)
    identity_phrases = ["i am seven", "you are mani", "you are mk", "you are admin",
                        "you can call me seven", f"you are {brain.USER_NAME.lower()}",
                        "still seven", "you just asked", "you've asked me this",
                        "you haven't told me that"]
    response_lower = response.lower()
    if any(phrase in response_lower for phrase in identity_phrases):
        should_store = False

    if should_store:
        try:
            clean_response = re.sub(r'###\w+:\s*\S+', '', response).strip()
            if clean_response:
                store_uid = active_speaker if active_speaker != "default" else "mani"
                seven_memory.store_conversation(user_input, clean_response, user_id=store_uid)
        except Exception as e:
            print(Fore.RED + f"[MEMORY ERROR] {e}")



    # --- EXECUTE WINDOW COMMANDS (V1.6) ---
    window_cmds = re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", response)
    if window_cmds:
        from hands.windows import manage_window
        for param_str in window_cmds:
            param_str = param_str.strip()
            print(Fore.CYAN + f"  [WINDOW CMD] Params: {param_str}")
            
            # Parse key=value pairs
            params = {}
            for pair in param_str.split():
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    params[key.strip()] = val.strip()
            
            if params:
                success, msg = manage_window(params)
                if success:
                    print(Fore.GREEN + f"  ✅ {msg}")
                else:
                    print(Fore.RED + f"  ❌ {msg}")

    # --- EXECUTE SYSTEM COMMANDS (V1.7) ---
    sys_cmds = re.findall(r"###SYS:\s*(.*?)(?=###|$)", response)
    if sys_cmds:
        for param_str in sys_cmds:
            param_str = param_str.strip()
            print(Fore.CYAN + f"  [SYS CMD] Params: {param_str}")
            
            params = {}
            for pair in param_str.split():
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    params[key.strip()] = val.strip()
            
            if params:
                success, msg = manage_system(params)
                if success:
                    print(Fore.GREEN + f"  ✅ {msg}")
                else:
                    print(Fore.RED + f"  ❌ {msg}")

    # --- EXECUTE SCHEDULER COMMANDS (V1.8) ---
    sched_cmds = re.findall(r"###SCHED:\s*(.*?)(?=###|$)", response)
    if sched_cmds:
        for param_str in sched_cmds:
            param_str = param_str.strip()
            print(Fore.CYAN + f"  [SCHED CMD] Params: {param_str}")
            
            params = {}
            for pair in param_str.split():
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    params[key.strip()] = val.strip()
            
            params["speaker_id"] = active_speaker
            
            if params:
                success, msg = manage_schedule(params)
                if success:
                    print(Fore.GREEN + f"  ✅ {msg}")
                else:
                    print(Fore.RED + f"  ❌ {msg}")

    # --- EXECUTE COMMANDS ---
    commands = re.findall(r"###(OPEN|CLOSE|SEARCH|SYS): (.*?)(?=###|$)", response)

    for cmd_type, arg in commands:
        arg = arg.replace('"', '').replace("'", "").strip()
        sub_apps = []
        if " and " in arg:
            sub_apps = arg.split(" and ")
        elif "," in arg:
            sub_apps = arg.split(",")
        else:
            sub_apps = [arg]

        for clean_arg in sub_apps:
            clean_arg = clean_arg.strip()
            print(Fore.BLUE + f"[HANDS ACTION] Executing: {cmd_type} -> {clean_arg}")
            if cmd_type == "OPEN":
                core.open_app(clean_arg)
            elif cmd_type == "CLOSE":
                core.close_app(clean_arg)
            elif cmd_type == "SEARCH":
                core.search_web(clean_arg)