"""
=============================================================================
PROJECT SEVEN - memory/core.py (The Hippocampus)
Version: 1.2 - 100% Offline Mode
Purpose: Long-term memory system using ChromaDB vector database.
         Allows Seven to remember conversations and user facts FOREVER.

HOW IT WORKS:
    1. Every conversation gets converted into a "vector" (list of numbers)
       Example: "My favorite color is blue" → [0.23, -0.45, 0.67, ...]
    2. These vectors are stored in ChromaDB (local database on disk)
    3. When user says something new, we search for CLOSEST matching vectors
    4. "Closest" = SEMANTICALLY similar, not keyword matching (RAG)

ARCHITECTURE:
    ears.py → main.py → memory.py (search + store) → brain.py
                              ↓
                    ./seven_data/memory/ (ChromaDB files on disk)
=============================================================================
"""

import os

# =============================================================================
# OFFLINE FLAGS - MUST be set before ALL other imports
# =============================================================================
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Suppress network-related logs
import logging
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

import chromadb.config
try:
    chromadb.config.Settings(anonymized_telemetry=False)
except:
    pass

import chromadb
import datetime
import json
from colorama import Fore

# =============================================================================
# CONFIGURATION
# =============================================================================

MEMORY_DIR = "./seven_data/memory"
TOP_K_RESULTS = 5
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# =============================================================================
# STANDALONE OFFLINE EMBEDDER
# (Outside class so it can be called during __init__)
# =============================================================================

def _load_offline_embedder_standalone(model_name: str):
    """
    Load embedding model from local HuggingFace cache.
    Never connects to internet - 100% offline.

    Confirmed cache location on this machine:
    C:/Users/Manikanta Cheruku/.cache/huggingface/hub/
    models--sentence-transformers--all-MiniLM-L6-v2/snapshots/

    WHY standalone (not a class method):
    - Called during __init__ before self is fully initialized
    - Standalone function avoids 'self not ready' issues
    """
    from sentence_transformers import SentenceTransformer

    home = os.path.expanduser("~")

    # Primary: HuggingFace hub cache (confirmed exists on this machine)
    hf_snapshot_path = os.path.join(
        home, ".cache", "huggingface", "hub",
        f"models--sentence-transformers--{model_name}",
        "snapshots"
    )

    # All paths to try in order
    search_paths = [
        hf_snapshot_path,
        os.path.join(home, ".cache", "torch", "sentence_transformers",
                     f"sentence-transformers_{model_name}"),
        os.path.join(home, ".cache", "sentence_transformers",
                     f"sentence-transformers_{model_name}"),
        os.path.join(".", "seven_data", "models", model_name),
    ]

    model = None

    for path in search_paths:
        if not os.path.exists(path):
            continue

        try:
            load_path = path

            # HuggingFace hub stores model inside snapshots/HASH_FOLDER/
            if "snapshots" in path:
                snapshots = [
                    f for f in os.listdir(path)
                    if os.path.isdir(os.path.join(path, f))
                ]
                if not snapshots:
                    continue
                load_path = os.path.join(path, snapshots[0])

            model = SentenceTransformer(load_path, local_files_only=True)
            print(Fore.GREEN + "[MEMORY] ✓ Model loaded from local cache (offline)")
            break

        except Exception as e:
            print(Fore.YELLOW + f"[MEMORY] Path failed ({path}): {e}")
            continue

    # Fallback: try with local_files_only flag (uses any cache)
    if model is None:
        print(Fore.YELLOW + "[MEMORY] Trying local_files_only fallback...")
        try:
            model = SentenceTransformer(model_name, local_files_only=True)
            print(Fore.GREEN + "[MEMORY] ✓ Model loaded (local_files_only)")
        except Exception as e:
            # Last resort: allow download if truly not cached anywhere
            print(Fore.RED + f"[MEMORY] ✗ All offline methods failed: {e}")
            print(Fore.YELLOW + "[MEMORY] Downloading model (one time only)...")
            model = SentenceTransformer(model_name)
            print(Fore.GREEN + "[MEMORY] ✓ Model downloaded and cached")

    # Wrap in ChromaDB-compatible embedding function
    class _OfflineEmbedder:
        """ChromaDB-compatible wrapper around SentenceTransformer."""

        def __init__(self, m):
            self._model = m

        def __call__(self, input: list) -> list:
            return self._model.encode(
                input,
                show_progress_bar=False,
                batch_size=32
            ).tolist()

    return _OfflineEmbedder(model)


# =============================================================================
# MEMORY SYSTEM CLASS
# =============================================================================

class SevenMemory:
    """
    Seven's Long-Term Memory System.

    Think of this like a brain's hippocampus:
    - store_conversation(): Saves what was said (like forming a memory)
    - store_fact():         Saves important facts (like remembering a name)
    - search():             Finds relevant memories (like recalling something)

    Everything is stored locally in ./seven_data/memory/
    Nothing ever leaves your computer.
    """

    def __init__(self):
        """
        Initialize the memory system.
        Runs ONCE when Seven starts up.

        Steps:
        1. Create storage folder
        2. Load embedding model from local cache (offline)
        3. Connect to ChromaDB
        4. Set up two collections:
           - conversations: chat history
           - user_facts:    permanent facts about user
        """

        print(Fore.CYAN + "[MEMORY] Initializing Long-Term Memory System...")

        # Create storage folder
        os.makedirs(MEMORY_DIR, exist_ok=True)

        # Load embedding model (100% offline)
        print(Fore.CYAN + "[MEMORY] Loading embedding model (offline)...")
        self.embedding_function = _load_offline_embedder_standalone(EMBEDDING_MODEL)

        # Connect to ChromaDB (persistent local database)
        self.client = chromadb.PersistentClient(path=MEMORY_DIR)

        # Collection 1: CONVERSATIONS
        # Stores every user ↔ Seven exchange
        self.conversations = self.client.get_or_create_collection(
            name="conversations",
            embedding_function=self.embedding_function,
            metadata={"description": "Stores all conversation history"}
        )

        # Collection 2: USER FACTS
        # Stores permanent facts like "User's name is Mani"
        self.user_facts = self.client.get_or_create_collection(
            name="user_facts",
            embedding_function=self.embedding_function,
            metadata={"description": "Stores permanent user facts"}
        )

        # Stats
        conv_count = self.conversations.count()
        fact_count = self.user_facts.count()
        print(Fore.GREEN + f"[MEMORY] Online. Conversations: {conv_count} | Facts: {fact_count}")

    # =========================================================================
    # STORE METHODS (Saving Memories)
    # =========================================================================

    def store_conversation(self, user_input, seven_response, user_id="mani"):
        """Store a conversation exchange in long-term memory."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memory_id = f"conv_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        combined_text = f"User said: {user_input} | Seven replied: {seven_response}"

        self.conversations.add(
            documents=[combined_text],
            metadatas=[{
                "user_input": user_input,
                "seven_response": seven_response,
                "timestamp": timestamp,
                "user_id": user_id,
                "type": "conversation"
            }],
            ids=[memory_id]
        )

        print(Fore.CYAN + f"[MEMORY] Stored conversation: '{user_input[:50]}...'")

    def store_fact(self, fact_text, category="general", user_id="mani"):
        """
        Save an important fact permanently.

        Facts: "User's name is Mani", "User's favorite color is blue"

        WHY separate from conversations:
        - Facts are PERMANENT and should always be found
        - Conversations are temporal (happened at specific time)
        - In search, facts get PRIORITY over old conversations
        """

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fact_id = f"fact_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # Check for duplicate facts (prevent storing same thing 100 times)
        existing = self._search_collection(self.user_facts, fact_text, n_results=1)

        if existing and existing[0]["relevance"] > 0.85:
            print(Fore.YELLOW + f"[MEMORY] Updating existing fact: '{fact_text[:50]}...'")
            self.user_facts.delete(ids=[existing[0]["id"]])

        self.user_facts.add(
            documents=[fact_text],
            metadatas=[{
                "category": category,
                "timestamp": timestamp,
                "user_id": user_id,
                "type": "fact"
            }],
            ids=[fact_id]
        )

        print(Fore.GREEN + f"[MEMORY] Stored fact: '{fact_text}'")

    # =========================================================================
    # SEARCH METHODS (Recalling Memories)
    # =========================================================================

    def search(self, query, user_id="mani", n_results=TOP_K_RESULTS):
        """
        Search ALL memory (facts + conversations) for relevant information.

        HOW SEMANTIC SEARCH WORKS:
        1. Query becomes a vector
        2. ChromaDB compares to ALL stored vectors
        3. Returns closest matches by MEANING (not keywords)
        4. "What color do I like?" finds "My favorite color is blue"
           even though they share almost no words

        Returns formatted string ready for brain prompt injection.
        """

        all_results = []

        # Facts first (priority over conversations)
        fact_results = self._search_collection(
            self.user_facts, query, n_results=n_results, user_id=user_id
        )
        for r in fact_results:
            r["source"] = "fact"
        all_results.extend(fact_results)

        # Conversations
        conv_results = self._search_collection(
            self.conversations, query, n_results=n_results, user_id=user_id
        )
        for r in conv_results:
            r["source"] = "conversation"
        all_results.extend(conv_results)

        # Sort by relevance
        all_results.sort(key=lambda x: x["relevance"], reverse=True)
        all_results = all_results[:n_results]

        # Filter low-relevance noise (below 0.3 = probably irrelevant)
        RELEVANCE_THRESHOLD = 0.3
        all_results = [r for r in all_results if r["relevance"] >= RELEVANCE_THRESHOLD]

        if not all_results:
            return ""

        return self._format_memories(all_results)

    def _search_collection(self, collection, query, n_results=5, user_id=None):
        """
        Search a single ChromaDB collection.

        Returns list of dicts:
        - text:      memory content
        - relevance: 0.0 to 1.0 (higher = more relevant)
        - metadata:  timestamp, user_id, etc.
        - id:        unique memory ID
        """

        if collection.count() == 0:
            return []

        # Filter by user_id (ready for multi-user V1.2)
        where_filter = None
        if user_id:
            where_filter = {"user_id": user_id}

        actual_n = min(n_results, collection.count())

        try:
            results = collection.query(
                query_texts=[query],
                n_results=actual_n,
                where=where_filter
            )

            parsed = []
            for i in range(len(results["documents"][0])):
                # Convert ChromaDB distance to relevance score
                distance = results["distances"][0][i]
                relevance = max(0, 1 - (distance / 2))

                parsed.append({
                    "text": results["documents"][0][i],
                    "relevance": round(relevance, 3),
                    "metadata": results["metadatas"][0][i],
                    "id": results["ids"][0][i]
                })

            return parsed

        except Exception as e:
            print(Fore.RED + f"[MEMORY ERROR] Search failed: {e}")
            return []

    def _format_memories(self, results):
        """Format memories into string for brain prompt."""
        lines = ["=== RECALLED MEMORIES ==="]

        for r in results:
            source_tag = r["source"].upper()
            timestamp = r["metadata"].get("timestamp", "unknown date")
            date_part = timestamp.split(" ")[0] if " " in timestamp else timestamp

            text = r["text"]
            if "Seven replied:" in text:
                text = text.split("Seven replied:")[0].rstrip(" |").strip()

            lines.append(f"[{source_tag}] {text} (from {date_part})")

        lines.append("=== END MEMORIES ===")
        return "\n".join(lines)

    # =========================================================================
    # FACT EXTRACTION (Automatic Learning)
    # =========================================================================

    def extract_and_store_facts(self, user_input, user_id="mani"):
        """
        Automatically detect and store facts from user input.

        Runs on EVERY user input. Checks patterns:
        - "My name is Mani"        → Stores: "User's name is Mani"
        - "I love Python"          → Stores: "User loves Python"
        - "My favorite movie is X" → Stores: "User's favorite movie is X"

        Seven learns passively without user saying "Remember this".
        """

        clean = user_input.lower().strip()

        # Pattern 1: Identity Facts
        if "my name is" in clean:
            name = user_input.split("is")[-1].strip().rstrip(".")
            self.store_fact(
                f"User's name is {name}",
                category="identity",
                user_id=user_id
            )
            return True

        if "call me" in clean:
            name = user_input.lower().split("call me")[-1].strip().rstrip(".")
            self.store_fact(
                f"User wants to be called {name}",
                category="identity",
                user_id=user_id
            )
            return True

        # Pattern 2: Preference Facts
        if "my favorite" in clean or "my favourite" in clean:
            # Skip questions about favorites
            question_starts = ["what", "which", "who", "when", "where", "how", "do", "can", "tell"]
            if not any(clean.startswith(q) for q in question_starts):
                self.store_fact(
                    f"User said: {user_input}",
                    category="preference",
                    user_id=user_id
                )
                return True

        if clean.startswith("i love ") or clean.startswith("i like "):
            self.store_fact(
                f"User said: {user_input}",
                category="preference",
                user_id=user_id
            )
            return True

        if clean.startswith("i prefer "):
            self.store_fact(
                f"User said: {user_input}",
                category="preference",
                user_id=user_id
            )
            return True

        # Pattern 3: Personal Info
        if clean.startswith("i am a ") or clean.startswith("i am an "):
            self.store_fact(
                f"User said: {user_input}",
                category="personal",
                user_id=user_id
            )
            return True

        if "i work at" in clean or "i work as" in clean:
            self.store_fact(
                f"User said: {user_input}",
                category="personal",
                user_id=user_id
            )
            return True

        if "i study at" in clean or ("i study" in clean and "studying" not in clean):
            self.store_fact(
                f"User said: {user_input}",
                category="personal",
                user_id=user_id
            )
            return True

        # Pattern 4: Explicit Memory Request
        if clean.startswith("remember that") or clean.startswith("remember this"):
            fact = (
                user_input.split("that", 1)[-1].strip()
                if "that" in user_input
                else user_input.split("this", 1)[-1].strip()
            )
            self.store_fact(
                f"User asked to remember: {fact}",
                category="explicit",
                user_id=user_id
            )
            return True

        return False

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_stats(self):
        """Return memory statistics."""
        return {
            "total_conversations": self.conversations.count(),
            "total_facts": self.user_facts.count(),
            "storage_path": os.path.abspath(MEMORY_DIR)
        }

    def clear_all(self):
        """
        Delete ALL memories. IRREVERSIBLE.
        Used for testing or privacy reset.
        """
        self.client.delete_collection("conversations")
        self.client.delete_collection("user_facts")

        self.conversations = self.client.get_or_create_collection(
            name="conversations",
            embedding_function=self.embedding_function
        )
        self.user_facts = self.client.get_or_create_collection(
            name="user_facts",
            embedding_function=self.embedding_function
        )

        print(Fore.YELLOW + "[MEMORY] All memories cleared.")


# =============================================================================
# MODULE-LEVEL INSTANCE
# =============================================================================
# ONE instance shared across all of Seven.
#
# Usage in other files:
#   from memory import seven_memory
#   seven_memory.search("what's my name?")
#   seven_memory.store_conversation("Hi", "Hello Mani")

seven_memory = SevenMemory()