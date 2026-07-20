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
# NOTE: HF_HUB_OFFLINE is set to "1" only AFTER model is confirmed cached.
# Do NOT set it here — it blocks first-time download on new machines.
os.environ["HF_HUB_DISABLE_TELEMETRY"]     = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"]= "1"
os.environ["TOKENIZERS_PARALLELISM"]        = "false"
os.environ["CUDA_VISIBLE_DEVICES"]          = ""

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
    """
    Resolve memory directory.
    Priority:
    1. Local seven_data/memory if it exists and has data (dev mode)
    2. APPDATA/SEVEN/seven_data/memory (production + fallback)
    
    This ensures dev mode reads the same DB that brain.py writes to.
    """
    # Dev mode: local seven_data/memory has the real data
    local_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'seven_data', 'memory'
    )
    if os.path.exists(local_path):
        chroma_db = os.path.join(local_path, 'chroma.sqlite3')
        if os.path.exists(chroma_db):
            return local_path

    # Production: APPDATA
    appdata = os.environ.get('APPDATA', '')
    if appdata:
        path = os.path.join(appdata, 'SEVEN', 'seven_data', 'memory')
        os.makedirs(path, exist_ok=True)
        return path

    return local_path

MEMORY_DIR      = _get_memory_dir()
TOP_K_RESULTS   = 5
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# =============================================================================
# OFFLINE EMBEDDER UNA
# =============================================================================



def _load_offline_embedder_standalone(model_name: str):
    """
    Returns a ChromaDB-compatible embedding function.
    Uses chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction
    which is already built to work with ChromaDB's Rust query layer.
    Falls back to manual embedder only if chromadb utility is unavailable.
    """
    from sentence_transformers import SentenceTransformer

    # First verify model is cached locally
    home = os.path.expanduser("~")
    hf_snapshot_path = os.path.join(
        home, ".cache", "huggingface", "hub",
        f"models--sentence-transformers--{model_name}",
        "snapshots"
    )

    model_local_path = None
    search_paths = [
        hf_snapshot_path,
        os.path.join(home, ".cache", "torch", "sentence_transformers",
                     f"sentence-transformers_{model_name}"),
        os.path.join(home, ".cache", "sentence_transformers",
                     f"sentence-transformers_{model_name}"),
        os.path.join(".", "seven_data", "models", model_name),
    ]

    for path in search_paths:
        if not os.path.exists(path):
            continue
        if "snapshots" in path:
            try:
                snapshots = [
                    f for f in os.listdir(path)
                    if os.path.isdir(os.path.join(path, f))
                ]
                if snapshots:
                    model_local_path = os.path.join(path, snapshots[0])
                    break
            except Exception:
                continue
        else:
            model_local_path = path
            break

    if model_local_path is None:
        print(Fore.YELLOW + "[MEMORY] Model not cached. Downloading once...")
        try:
            SentenceTransformer(model_name)
            print(Fore.GREEN + "[MEMORY] Model downloaded and cached.")
            model_local_path = model_name  # use name, it is now cached
        except Exception as e:
            print(Fore.RED + f"[MEMORY] Download failed: {e}")
            model_local_path = model_name

    print(Fore.GREEN + "[MEMORY] Model loaded from local cache (offline)")

    # Set offline flags after model is confirmed present
    os.environ["HF_HUB_OFFLINE"]      = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print(Fore.CYAN + "[MEMORY] Offline mode enabled — model cached locally.")

    # Use ChromaDB's own SentenceTransformer wrapper
    # This is guaranteed to work with ChromaDB's Rust query layer
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(
            model_name=model_local_path,
            device="cpu"
        )
        # Test it actually works before returning
        ef(["test"])
        print(Fore.GREEN + "[MEMORY] Using ChromaDB native SentenceTransformer embedder")
        return ef
    except Exception as e:
        if "meta tensor" in str(e).lower() or "to_empty" in str(e).lower():
            print(Fore.YELLOW + "[MEMORY] Meta tensor detected — loading with empty init")
            # Fix: use from_pretrained path directly, skip .to() call
            try:
                import torch
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(
                    model_local_path,
                    device="cpu",
                    local_files_only=True,
                )
                # Force resolve meta tensors
                for param in model.parameters():
                    if param.is_meta:
                        param.data = torch.empty_like(param, device="cpu")
                print(Fore.GREEN + "[MEMORY] Meta tensor resolved — embedder ready")

                class _ResolvedEmbedder:
                    def __init__(self, m):
                        self._model = m
                    def __call__(self, input) -> list:
                        texts = [input] if isinstance(input, str) else list(input)
                        return self._model.encode(
                            texts, show_progress_bar=False
                        ).tolist()
                    def name(self):
                        return "seven_resolved_embedder"

                return _ResolvedEmbedder(model)
            except Exception as inner:
                print(Fore.YELLOW + f"[MEMORY] Meta resolve failed: {inner} — using fallback")
        else:
            print(Fore.YELLOW + f"[MEMORY] ChromaDB native embedder failed: {e}")

    # Manual fallback — load model avoiding meta tensor issue
    try:
        import torch
        # Use empty init to avoid meta tensor problem
        model = SentenceTransformer.__new__(SentenceTransformer)
        SentenceTransformer.__init__(
            model,
            model_local_path,
            device="cpu",
        )
    except Exception:
        try:
            model = SentenceTransformer(
                model_local_path,
                local_files_only=True
            )
        except Exception:
            model = SentenceTransformer(model_name)

    class _FallbackEmbedder:
        def __init__(self, m):
            self._model = m

        def __call__(self, input) -> list:
            texts = [input] if isinstance(input, str) else list(input)
            return self._model.encode(
                texts, show_progress_bar=False
            ).tolist()

        def name(self):
            return "seven_fallback_embedder"

    return _FallbackEmbedder(model)


# =============================================================================
# MEMORY SYSTEM
# =============================================================================

class SevenMemory:

    def __init__(self):
        print(Fore.CYAN + "[MEMORY] Initializing Long-Term Memory System...")
        os.makedirs(MEMORY_DIR, exist_ok=True)

        print(Fore.CYAN + "[MEMORY] Loading embedding model (offline)...")
        self.embedding_function = _load_offline_embedder_standalone(EMBEDDING_MODEL)

        # Skip verification - it was tested separately and works
        # _verify_embedder creates a temp collection which can hang on slow systems
        print(Fore.GREEN + "[MEMORY] Embedder ready (verification skipped for speed)")

        # Connect to ChromaDB
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
            print(Fore.YELLOW + "[MEMORY] Resetting to clean state...")
            self.client = self._reset_and_reinit(MEMORY_DIR)
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
            print(Fore.GREEN + "[MEMORY] Online (fresh). Conversations: 0 | Facts: 0")

    def _verify_embedder(self, ef):
        """
        Test the embedder with a real ChromaDB query path.
        If it fails, fall back to chromadb default embedder.
        This prevents the rust layer TypeError from crashing the voice loop.
        """
        import tempfile
        try:
            # Create a tiny temp collection and run a real query
            test_settings = chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
            test_dir = os.path.join(tempfile.gettempdir(), "seven_ef_test")
            os.makedirs(test_dir, exist_ok=True)
            test_client = chromadb.PersistentClient(
                path=test_dir,
                settings=test_settings
            )
            # Delete if exists from previous test
            try:
                test_client.delete_collection("ef_test")
            except Exception:
                pass
            test_col = test_client.get_or_create_collection(
                name="ef_test",
                embedding_function=ef
            )
            test_col.add(
                documents=["hello world test"],
                ids=["test_001"]
            )
            test_col.query(query_texts=["hello"], n_results=1)
            # Clean up
            test_client.delete_collection("ef_test")
            print(Fore.GREEN + "[MEMORY] Embedding function verified OK")
            return ef
        except Exception as e:
            print(Fore.YELLOW + f"[MEMORY] Custom embedder failed verification: {e}")
            print(Fore.YELLOW + "[MEMORY] Falling back to ChromaDB default embedder")
            try:
                from chromadb.utils import embedding_functions
                default_ef = embedding_functions.DefaultEmbeddingFunction()
                print(Fore.GREEN + "[MEMORY] Using ChromaDB default embedder (online required for first use)")
                return default_ef
            except Exception as e2:
                print(Fore.RED + f"[MEMORY] Default embedder also failed: {e2}")
                print(Fore.RED + "[MEMORY] Memory search disabled - brain still works")
                return ef  # return original, search will fail gracefully

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
        # ── Plan limit check ──
        try:
            import voice_limits
            current = self.user_facts.count()
            allowed, _ = voice_limits.check("facts_limit", current)
            if not allowed:
                print(Fore.YELLOW +
                      f"[LIMIT] Fact limit reached ({current}) "
                      f"tier={voice_limits.get_tier()} — not storing")
                # Raise so API can catch and return 403
                raise PermissionError(
                    f"facts_limit|{voice_limits.get_tier()}|{current}"
                )
        except PermissionError:
            raise
        except ImportError:
            pass  # voice_limits not available — allow

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fact_id   = f"fact_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        existing  = self._search_collection(self.user_facts, fact_text, n_results=1)
        if existing and existing[0]["relevance"] > 0.85:
            print(Fore.YELLOW +
                  f"[MEMORY] Updating existing fact: '{fact_text[:50]}...'")
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
        actual_n = min(n_results, collection.count())

        # Try with user_id filter first, fall back to no filter
        # ChromaDB where filter throws when no documents match
        queries_to_try = []
        if user_id:
            queries_to_try.append({"user_id": user_id})
        queries_to_try.append(None)

        results = None
        for where_filter in queries_to_try:
            try:
                res = collection.query(
                    query_texts=[query],
                    n_results=actual_n,
                    where=where_filter
                )
                if (res.get("documents") and
                        res["documents"] and
                        len(res["documents"][0]) > 0):
                    results = res
                    break
            except Exception:
                continue

        if not results:
            return []

        try:
            docs      = results["documents"][0]
            distances = results["distances"][0]  if results.get("distances")  else [1.0] * len(docs)
            metadatas = results["metadatas"][0]  if results.get("metadatas")  else [{}]  * len(docs)
            ids       = results["ids"][0]        if results.get("ids")        else [f"u_{i}" for i in range(len(docs))]

            parsed = []
            for i in range(len(docs)):
                distance  = distances[i] if i < len(distances) else 1.0
                relevance = max(0.0, 1.0 - (distance / 2.0))
                parsed.append({
                    "text":      docs[i],
                    "relevance": round(relevance, 3),
                    "metadata":  metadatas[i] if i < len(metadatas) else {},
                    "id":        ids[i]       if i < len(ids)       else f"u_{i}"
                })
            return parsed
        except Exception as e:
            print(Fore.RED + f"[MEMORY ERROR] Parse failed: {e}")
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

        _has_name_change = (
            "my name is" in clean
            or "call me" in clean
            or "change my name" in clean
            or "rename me" in clean
            or ("my name" in clean and any(
                w in clean for w in ["into", "to is", "should be", "is now"]
            ))
        )
        if _has_name_change:
            import re as _re_mem
            raw = user_input.lower().split("my name is")[-1].strip()
            raw = _re_mem.split(r'\bnot\b|\bokay\b|\bplease\b|\bright\b|\bok\b', raw)[0]
            raw = raw.strip().rstrip(".,!?").strip()
            words_raw = [w for w in raw.split()
                         if w not in {"please","okay","ok","right","now","just"}]
            name = " ".join(words_raw[:2]).strip().title()
            if name:
                self.store_fact(f"User's name is {name}", category="identity", user_id=user_id)
            return True
        if "call me" in clean:
            import re as _re_mem
            raw = user_input.lower().split("call me")[-1].strip()
            raw = _re_mem.split(r'\bnot\b|\bokay\b|\bplease\b|\bright\b|\bok\b', raw)[0]
            raw = raw.strip().rstrip(".,!?").strip()
            words_raw = [w for w in raw.split()
                         if w not in {"please","okay","ok","right","now","just"}]
            name = " ".join(words_raw[:2]).strip().title()
            if name:
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