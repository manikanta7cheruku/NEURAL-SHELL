"""
=============================================================================
PROJECT SEVEN - test_chat.py (V1.6 - Developer Console)
=============================================================================
"""

import brain
import hands
import re
import colorama
from colorama import Fore
from memory import seven_memory
from memory.command_log import command_log
from memory.mood import mood_engine
from ears.voice_id import get_enrolled_speakers, remove_speaker, is_voice_id_enabled

colorama.init(autoreset=True)
# V1.2: Simulated speaker for text mode
active_speaker = "default"

print(Fore.CYAN + "=" * 60)
print(Fore.CYAN + "  SEVEN TEXT DEBUGGER (V1.2 - VOICE IDENTITY)")
print(Fore.CYAN + "=" * 60)
print(Fore.WHITE + "  Commands: /memory | /facts | /convos | /stats")
print(Fore.WHITE + "  Commands: /logs | /logs N | /mood")
print(Fore.WHITE + "  Commands: /add fact [text] | /delete fact [n]")
print(Fore.WHITE + "  Commands: /delete convo [n]")
print(Fore.WHITE + "  Commands: /clear all | /clear logs | /clear mood | quit")
print(Fore.WHITE + "  Commands: /help (show all commands)")
print(Fore.WHITE + "  Commands: /speaker [name] | /speakers | /remove speaker [name]")
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
    cmd_words = ["open", "close", "start", "kill", "launch"]
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
                hands.open_app(clean_arg)
            elif cmd_type == "CLOSE":
                hands.close_app(clean_arg)
            elif cmd_type == "SEARCH":
                hands.search_web(clean_arg)