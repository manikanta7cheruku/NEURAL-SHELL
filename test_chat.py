"""
=============================================================================
PROJECT SEVEN - test_chat.py (V1.1 - Developer Console)
=============================================================================
"""

import brain
import hands
import re
import colorama
from colorama import Fore
from memory import seven_memory

colorama.init(autoreset=True)

print(Fore.CYAN + "=" * 60)
print(Fore.CYAN + "  SEVEN TEXT DEBUGGER (V1.1 - MEMORY ACTIVE)")
print(Fore.CYAN + "=" * 60)
print(Fore.WHITE + "  Commands: /memory | /facts | /convos | /stats")
print(Fore.WHITE + "  Commands: /add fact [text] | /delete fact [n]")
print(Fore.WHITE + "  Commands: /delete convo [n] | /clear all | quit")
print(Fore.CYAN + "=" * 60)


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
    print(Fore.CYAN + f"\n  {'='*50}")
    print(Fore.CYAN + f"  MEMORY STATISTICS")
    print(Fore.CYAN + f"  Conversations: {stats['total_conversations']}")
    print(Fore.CYAN + f"  Facts:         {stats['total_facts']}")
    print(Fore.CYAN + f"  Storage:       {stats['storage_path']}")
    print(Fore.CYAN + f"  {'='*50}")


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
        print(Fore.GREEN + "  ✅ All memories cleared. Clean slate.")
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
    response = brain.think(user_input)
    print(Fore.GREEN + f"SEVEN: {response}")

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

    if should_store:
        try:
            clean_response = re.sub(r'###\w+:\s*\S+', '', response).strip()
            if clean_response:
                seven_memory.store_conversation(user_input, clean_response)
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