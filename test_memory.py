"""
=============================================================================
PROJECT SEVEN - test_memory.py
Purpose: Test the memory system independently before integrating.

RUN THIS FIRST:
    python test_memory.py

EXPECTED OUTPUT:
    - Memory initializes
    - Facts are stored
    - Conversations are stored  
    - Search finds relevant results
    - All tests pass
=============================================================================
"""

import colorama
from colorama import Fore
colorama.init(autoreset=True)

print(Fore.CYAN + "=" * 60)
print(Fore.CYAN + "  SEVEN MEMORY SYSTEM - TEST SUITE")
print(Fore.CYAN + "=" * 60)

# --- TEST 1: Import and Initialize ---
print(Fore.YELLOW + "\n[TEST 1] Importing memory system...")
try:
    from memory.core import seven_memory
    print(Fore.GREEN + "  ✅ Memory system initialized successfully!")
except Exception as e:
    print(Fore.RED + f"  ❌ FAILED: {e}")
    exit(1)

# --- TEST 2: Store Facts ---
print(Fore.YELLOW + "\n[TEST 2] Storing facts...")
try:
    seven_memory.store_fact("User's name is Mani", category="identity")
    seven_memory.store_fact("User loves Python programming", category="preference")
    seven_memory.store_fact("User's favorite color is blue", category="preference")
    print(Fore.GREEN + "  ✅ Facts stored successfully!")
except Exception as e:
    print(Fore.RED + f"  ❌ FAILED: {e}")

# --- TEST 3: Store Conversations ---
print(Fore.YELLOW + "\n[TEST 3] Storing conversations...")
try:
    seven_memory.store_conversation(
        "What can you do?",
        "I can open apps, chat with you, and remember our conversations."
    )
    seven_memory.store_conversation(
        "Open Chrome and Notepad",
        "Opening Chrome and Notepad for you."
    )
    seven_memory.store_conversation(
        "Tell me about machine learning",
        "Machine learning is a subset of AI where systems learn from data."
    )
    print(Fore.GREEN + "  ✅ Conversations stored successfully!")
except Exception as e:
    print(Fore.RED + f"  ❌ FAILED: {e}")

# --- TEST 4: Search by Meaning (Semantic Search) ---
print(Fore.YELLOW + "\n[TEST 4] Semantic search tests...")

# Test 4a: Search for name (should find the identity fact)
print(Fore.CYAN + "\n  Searching: 'What is my name?'")
result = seven_memory.search("What is my name?")
if result:
    print(Fore.GREEN + f"  ✅ Found memories:\n{result}")
else:
    print(Fore.RED + "  ❌ No memories found (expected to find name fact)")

# Test 4b: Search for color preference
print(Fore.CYAN + "\n  Searching: 'What color do I like?'")
result = seven_memory.search("What color do I like?")
if result:
    print(Fore.GREEN + f"  ✅ Found memories:\n{result}")
else:
    print(Fore.RED + "  ❌ No memories found")

# Test 4c: Search for a past topic
print(Fore.CYAN + "\n  Searching: 'Did we discuss AI?'")
result = seven_memory.search("Did we discuss AI?")
if result:
    print(Fore.GREEN + f"  ✅ Found memories:\n{result}")
else:
    print(Fore.RED + "  ❌ No memories found")

# Test 4d: Search for something NOT in memory (should return empty)
print(Fore.CYAN + "\n  Searching: 'What is quantum physics?'")
result = seven_memory.search("What is quantum physics?")
if not result:
    print(Fore.GREEN + "  ✅ Correctly returned empty (no relevant memories)")
else:
    print(Fore.YELLOW + f"  ⚠️ Found something (may be low relevance):\n{result}")

# --- TEST 5: Fact Extraction ---
print(Fore.YELLOW + "\n[TEST 5] Automatic fact extraction...")
try:
    extracted = seven_memory.extract_and_store_facts("I love playing guitar")
    print(Fore.GREEN + f"  ✅ 'I love playing guitar' → Extracted: {extracted}")
    
    extracted = seven_memory.extract_and_store_facts("Open Chrome")
    print(Fore.GREEN + f"  ✅ 'Open Chrome' → Extracted: {extracted} (should be False)")
    
    extracted = seven_memory.extract_and_store_facts("Remember that my meeting is at 3pm")
    print(Fore.GREEN + f"  ✅ 'Remember that...' → Extracted: {extracted}")
except Exception as e:
    print(Fore.RED + f"  ❌ FAILED: {e}")

# --- TEST 6: Memory Stats ---
print(Fore.YELLOW + "\n[TEST 6] Memory statistics...")
stats = seven_memory.get_stats()
print(Fore.GREEN + f"  ✅ Stats: {stats}")

# --- FINAL SUMMARY ---
print(Fore.CYAN + "\n" + "=" * 60)
print(Fore.GREEN + "  ALL TESTS COMPLETE!")
print(Fore.CYAN + f"  Total Conversations: {stats['total_conversations']}")
print(Fore.CYAN + f"  Total Facts: {stats['total_facts']}")
print(Fore.CYAN + f"  Storage: {stats['storage_path']}")
print(Fore.CYAN + "=" * 60)

# --- CLEANUP OPTION ---
print(Fore.YELLOW + "\n  Do you want to CLEAR test data? (y/n): ", end="")
choice = input().strip().lower()
if choice == "y":
    seven_memory.clear_all()
    print(Fore.GREEN + "  ✅ Test data cleared. Clean slate for real use.")
else:
    print(Fore.GREEN + "  ✅ Test data kept. Seven will remember these in real use.")