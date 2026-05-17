"""
=============================================================================
PROJECT SEVEN - memory/core.py (The Hippocampus)
Version: 1.3 - Packaged App + ChromaDB Recovery
=============================================================================
"""

import os
import shutil

# =============================================================================
# OFFLINE FLAGS - MUST be set before ALL other imports
# =============================================================================
os.environ["ANONYMIZED_TELEMETRY"]          = "False"
os.environ["HF_HUB_OFFLINE"]               = "1"
os.environ["TRANSFORMERS_OFFLINE"]          = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"]     = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"]= "1"
os.environ["TOKENIZERS_PARALLELISM"]        = "false"

import logging
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

import chromadb
import datetime
from colorama import Fore


# =============================================================================
# PATH
# =============================================================================

def _get_memory_dir():
    appdata = os.environ.get('APPDATA', '')
    if appdata:
        path = os.path.join(appdata, 'SEVEN', 'seven_data', 'memory')
        os.makedirs(path, exist_ok=True)
        return path
    return "./seven_data/memory"

MEMORY_DIR      = _get_memory_dir()
TOP_K_RESULTS   = 5
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# =============================================================================
# OFFLINE EMBEDDER
# =============================================================================

def _load_offline_embedder_standalone(model_name: str):
    from sentence_transformers import SentenceTransformer

    home = os.path.expanduser("~")

    hf_snapshot_path = os.path.join(
        home, ".cache", "huggingface", "hub",
        f"models--sentence-transformers--{model_name}",
        "snapshots"
    )

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

    if model is None:
        print(Fore.YELLOW + "[MEMORY] Trying local_files_only fallback...")
        try:
            model = SentenceTransformer(model_name, local_files_only=True)
            print(Fore.GREEN + "[MEMORY] ✓ Model loaded (local_files_only)")
        except Exception as e:
            print(Fore.RED + f"[MEMORY] ✗ All offline methods failed: {e}")
            print(Fore.YELLOW + "[MEMORY] Downloading model (one time only)...")
            model = SentenceTransformer(model_name)
            print(Fore.GREEN + "[MEMORY] ✓ Model downloaded and cached")

    class _OfflineEmbedder:
        def __init__(self, m):
            self._model = m
        def __call__(self, input: list) -> list:
            return self._model.encode(
                input, show_progress_bar=False, batch_size=32
            ).tolist()
        def name(self) -> str:
            return "seven_offline_embedder"

    return _OfflineEmbedder(model)


# =============================================================================
# MEMORY SYSTEM
# =============================================================================

class SevenMemory:

    def __init__(self):
        print(Fore.CYAN + "[MEMORY] Initializing Long-Term Memory System...")
        os.makedirs(MEMORY_DIR, exist_ok=True)

        print(Fore.CYAN + "[MEMORY] Loading embedding model (offline)...")
        self.embedding_function = _load_offline_embedder_standalone(EMBEDDING_MODEL)

        # Connect to ChromaDB — with auto-recovery if database is corrupt
        self.client = self._safe_init_client(MEMORY_DIR)

        self.conversations = self.client.get_or_create_collection(
            name="conversations",
            embedding_function=self.embedding_function,
            metadata={"description": "Stores all conversation history"}
        )
        self.user_facts = self.client.get_or_create_collection(
            name="user_facts",
            embedding_function=self.embedding_function,
            metadata={"description": "Stores permanent user facts"}
        )

        try:
            conv_count = self.conversations.count()
            fact_count = self.user_facts.count()
            print(Fore.GREEN + f"[MEMORY] Online. Conversations: {conv_count} | Facts: {fact_count}")
        except Exception as e:
            print(Fore.YELLOW + f"[MEMORY] DB schema incompatible: {e}")
            print(Fore.YELLOW + "[MEMORY] Resetting database to clean state...")
            self.client      = self._reset_and_reinit(MEMORY_DIR)
            self.conversations = self.client.get_or_create_collection(
                name="conversations",
                embedding_function=self.embedding_function,
                metadata={"description": "Stores all conversation history"}
            )
            self.user_facts    = self.client.get_or_create_collection(
                name="user_facts",
                embedding_function=self.embedding_function,
                metadata={"description": "Stores permanent user facts"}
            )
            print(Fore.GREEN + "[MEMORY] Online (fresh). Conversations: 0 | Facts: 0")

    # -------------------------------------------------------------------------

    def _safe_init_client(self, memory_dir):
        """Create ChromaDB client, reset if corrupted."""
        try:
            settings = chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
            return chromadb.PersistentClient(path=memory_dir, settings=settings)
        except Exception as e:
            print(Fore.YELLOW + f"[MEMORY] Client init failed: {e} — resetting...")
            return self._reset_and_reinit(memory_dir)

    def _reset_and_reinit(self, memory_dir):
        """Backup corrupt DB, create fresh one."""
        backup = memory_dir + "_backup"
        if os.path.exists(backup):
            shutil.rmtree(backup, ignore_errors=True)
        if os.path.exists(memory_dir):
            shutil.move(memory_dir, backup)
        os.makedirs(memory_dir, exist_ok=True)
        settings = chromadb.Settings(
            anonymized_telemetry=False,
            allow_reset=True,
        )
        return chromadb.PersistentClient(path=memory_dir, settings=settings)

    # =========================================================================
    # STORE
    # =========================================================================

    def store_conversation(self, user_input, seven_response, user_id="mani"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memory_id = f"conv_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        combined_text = f"User said: {user_input} | Seven replied: {seven_response}"
        self.conversations.add(
            documents=[combined_text],
            metadatas=[{
                "user_input":      user_input,
                "seven_response":  seven_response,
                "timestamp":       timestamp,
                "user_id":         user_id,
                "type":            "conversation"
            }],
            ids=[memory_id]
        )
        print(Fore.CYAN + f"[MEMORY] Stored conversation: '{user_input[:50]}...'")

    def store_fact(self, fact_text, category="general", user_id="mani"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fact_id   = f"fact_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        existing  = self._search_collection(self.user_facts, fact_text, n_results=1)
        if existing and existing[0]["relevance"] > 0.85:
            print(Fore.YELLOW + f"[MEMORY] Updating existing fact: '{fact_text[:50]}...'")
            self.user_facts.delete(ids=[existing[0]["id"]])
        self.user_facts.add(
            documents=[fact_text],
            metadatas=[{
                "category":  category,
                "timestamp": timestamp,
                "user_id":   user_id,
                "type":      "fact"
            }],
            ids=[fact_id]
        )
        print(Fore.GREEN + f"[MEMORY] Stored fact: '{fact_text}'")

    # =========================================================================
    # SEARCH
    # =========================================================================

    def search(self, query, user_id="mani", n_results=TOP_K_RESULTS):
        all_results = []

        fact_results = self._search_collection(
            self.user_facts, query, n_results=n_results, user_id=user_id
        )
        for r in fact_results:
            r["source"] = "fact"
        all_results.extend(fact_results)

        conv_results = self._search_collection(
            self.conversations, query, n_results=n_results, user_id=user_id
        )
        for r in conv_results:
            r["source"] = "conversation"
        all_results.extend(conv_results)

        all_results.sort(key=lambda x: x["relevance"], reverse=True)
        all_results = all_results[:n_results]
        all_results = [r for r in all_results if r["relevance"] >= 0.3]

        if not all_results:
            return ""
        return self._format_memories(all_results)

    def _search_collection(self, collection, query, n_results=5, user_id=None):
        if collection.count() == 0:
            return []
        where_filter = {"user_id": user_id} if user_id else None
        actual_n     = min(n_results, collection.count())
        try:
            results = collection.query(
                query_texts=[query],
                n_results=actual_n,
                where=where_filter
            )
            parsed = []
            for i in range(len(results["documents"][0])):
                distance  = results["distances"][0][i]
                relevance = max(0, 1 - (distance / 2))
                parsed.append({
                    "text":      results["documents"][0][i],
                    "relevance": round(relevance, 3),
                    "metadata":  results["metadatas"][0][i],
                    "id":        results["ids"][0][i]
                })
            return parsed
        except Exception as e:
            print(Fore.RED + f"[MEMORY ERROR] Search failed: {e}")
            return []

    def _format_memories(self, results):
        lines = ["=== RECALLED MEMORIES ==="]
        for r in results:
            source_tag = r["source"].upper()
            timestamp  = r["metadata"].get("timestamp", "unknown date")
            date_part  = timestamp.split(" ")[0] if " " in timestamp else timestamp
            text       = r["text"]
            if "Seven replied:" in text:
                text = text.split("Seven replied:")[0].rstrip(" |").strip()
            lines.append(f"[{source_tag}] {text} (from {date_part})")
        lines.append("=== END MEMORIES ===")
        return "\n".join(lines)

    # =========================================================================
    # FACT EXTRACTION
    # =========================================================================

    def extract_and_store_facts(self, user_input, user_id="mani"):
        clean = user_input.lower().strip()

        if "my name is" in clean:
            name = user_input.split("is")[-1].strip().rstrip(".")
            self.store_fact(f"User's name is {name}", category="identity", user_id=user_id)
            return True
        if "call me" in clean:
            name = user_input.lower().split("call me")[-1].strip().rstrip(".")
            self.store_fact(f"User wants to be called {name}", category="identity", user_id=user_id)
            return True
        if "my favorite" in clean or "my favourite" in clean:
            question_starts = ["what","which","who","when","where","how","do","can","tell"]
            if not any(clean.startswith(q) for q in question_starts):
                self.store_fact(f"User said: {user_input}", category="preference", user_id=user_id)
                return True
        if clean.startswith("i love ") or clean.startswith("i like "):
            self.store_fact(f"User said: {user_input}", category="preference", user_id=user_id)
            return True
        if clean.startswith("i prefer "):
            self.store_fact(f"User said: {user_input}", category="preference", user_id=user_id)
            return True
        if clean.startswith("i am a ") or clean.startswith("i am an "):
            self.store_fact(f"User said: {user_input}", category="personal", user_id=user_id)
            return True
        if "i work at" in clean or "i work as" in clean:
            self.store_fact(f"User said: {user_input}", category="personal", user_id=user_id)
            return True
        if "i study at" in clean or ("i study" in clean and "studying" not in clean):
            self.store_fact(f"User said: {user_input}", category="personal", user_id=user_id)
            return True
        if clean.startswith("remember that") or clean.startswith("remember this"):
            fact = (
                user_input.split("that", 1)[-1].strip()
                if "that" in user_input
                else user_input.split("this", 1)[-1].strip()
            )
            self.store_fact(f"User asked to remember: {fact}", category="explicit", user_id=user_id)
            return True
        return False

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_stats(self):
        try:
            return {
                "total_conversations": self.conversations.count(),
                "total_facts":         self.user_facts.count(),
                "storage_path":        MEMORY_DIR
            }
        except Exception:
            return {
                "total_conversations": 0,
                "total_facts":         0,
                "storage_path":        MEMORY_DIR
            }

    def clear_all(self):
        self.client.delete_collection("conversations")
        self.client.delete_collection("user_facts")
        self.conversations = self.client.get_or_create_collection(
            name="conversations", embedding_function=self.embedding_function
        )
        self.user_facts = self.client.get_or_create_collection(
            name="user_facts", embedding_function=self.embedding_function
        )
        print(Fore.YELLOW + "[MEMORY] All memories cleared.")


# =============================================================================
# LAZY MODULE-LEVEL INSTANCE
# Loads embedding model only on first actual use — not at import time
# =============================================================================

_instance = None

def _get_instance():
    global _instance
    if _instance is None:
        _instance = SevenMemory()
    return _instance

class _LazyMemory:
    """Proxy — SevenMemory initializes only on first attribute access."""
    def __getattr__(self, name):
        return getattr(_get_instance(), name)
    def __bool__(self):
        return True

seven_memory = _LazyMemory()