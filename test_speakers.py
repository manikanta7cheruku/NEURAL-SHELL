# test_speakers.py — Quick test to check user_id in stored data

from memory import seven_memory

# Check facts
facts = seven_memory.user_facts.get()
print("=== FACTS ===")
for i, doc in enumerate(facts['documents']):
    uid = facts['metadatas'][i].get('user_id', 'NONE')
    print(f"  [{i}] user_id={uid} | {doc}")

# Check last 5 conversations
convos = seven_memory.conversations.get()
total = len(convos['documents'])
print(f"\n=== CONVERSATIONS (last 10 of {total}) ===")
start = max(0, total - 10)
for i in range(start, total):
    uid = convos['metadatas'][i].get('user_id', 'NONE')
    doc = convos['documents'][i][:70]
    print(f"  [{i}] user_id={uid} | {doc}")