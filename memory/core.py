"""
=============================================================================
PROJECT SEVEN - memory.py (The Hippocampus)
Version: 1.1
Purpose: Long-term memory system using ChromaDB vector database.
         Allows Seven to remember conversations and user facts FOREVER.

HOW IT WORKS (Simple Explanation):
    1. Every conversation gets converted into a "vector" (a list of numbers)
       Example: "My favorite color is blue" → [0.23, -0.45, 0.67, ...]
    
    2. These vectors are stored in ChromaDB (a local database on your disk)
    
    3. When the user says something new, we convert THAT into a vector too
       and search for the CLOSEST matching vectors in the database
       
    4. "Closest" means SEMANTICALLY similar, not keyword matching:
       - User says: "What color do I like?"
       - Search finds: "My favorite color is blue" (because meanings are close)
       - This is called "semantic search" and it's the magic of RAG

ARCHITECTURE:
    ears.py → main.py → memory.py (search + store) → brain.py
                              ↓
                    ./seven_data/memory/ (ChromaDB files on disk)
=============================================================================
"""

import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Suppress ChromaDB telemetry errors completely
import logging
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.WARNING)

import chromadb.config
try:
    chromadb.config.Settings(anonymized_telemetry=False)
except:
    pass

import chromadb
from chromadb.utils import embedding_functions
import datetime
import json
from colorama import Fore

# =============================================================================
# CONFIGURATION
# =============================================================================

# Where the database files are stored on disk
# This folder will contain ChromaDB's internal files
MEMORY_DIR = "./seven_data/memory"

# How many memories to retrieve per search
# More = more context for the LLM, but uses more tokens
# 5 is a sweet spot: enough context without flooding the prompt
TOP_K_RESULTS = 5

# The embedding model that converts text → vectors
# all-MiniLM-L6-v2: Only 80MB, runs on CPU, very fast (5ms per embedding)
# This does NOT use your GPU VRAM — Llama3 keeps full VRAM access
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# =============================================================================
# MEMORY SYSTEM CLASS
# =============================================================================

class SevenMemory:
    """
    Seven's Long-Term Memory System.
    
    Think of this like a brain's hippocampus:
    - store_conversation(): Saves what was said (like forming a memory)
    - store_fact():         Saves important facts (like remembering a name)
    - search():            Finds relevant memories (like recalling something)
    
    Everything is stored locally in ./seven_data/memory/
    Nothing ever leaves your computer.
    """

    def __init__(self):
        """
        Initialize the memory system.
        This runs ONCE when Seven starts up.
        
        What happens here:
        1. Create the storage folder if it doesn't exist
        2. Load the embedding model (text → vector converter)
        3. Connect to ChromaDB (or create it if first run)
        4. Set up two "collections" (like database tables):
           - conversations: Stores chat history with timestamps
           - user_facts:    Stores permanent facts about the user
        """
        
        print(Fore.CYAN + "[MEMORY] Initializing Long-Term Memory System...")
        
        # --- CREATE STORAGE FOLDER ---
        # os.makedirs creates the folder AND any parent folders needed
        # exist_ok=True means "don't crash if folder already exists"
        os.makedirs(MEMORY_DIR, exist_ok=True)
        
        # --- LOAD EMBEDDING MODEL ---
        # This model converts text into vectors (lists of 384 numbers)
        # It runs on CPU so it doesn't compete with Llama3 for VRAM
        # First run: Downloads ~80MB model (cached after that)
        print(Fore.CYAN + "[MEMORY] Loading embedding model (first time may download ~80MB)...")
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        
        # --- CONNECT TO CHROMADB ---
        # PersistentClient = data survives restarts (saved to disk)
        # This is different from Client() which only lives in RAM
        self.client = chromadb.PersistentClient(path=MEMORY_DIR)
        
        # --- CREATE COLLECTIONS (like database tables) ---
        # get_or_create = "use existing if found, create new if not"
        # This prevents data loss on restart
        
        # Collection 1: CONVERSATIONS
        # Stores every exchange between user and Seven
        # Metadata: timestamp, user_id, speaker (user/seven)
        self.conversations = self.client.get_or_create_collection(
            name="conversations",
            embedding_function=self.embedding_function,
            metadata={"description": "Stores all conversation history"}
        )
        
        # Collection 2: USER FACTS  
        # Stores extracted facts like "User's name is Mani"
        # These are permanent and ranked higher in search results
        self.user_facts = self.client.get_or_create_collection(
            name="user_facts",
            embedding_function=self.embedding_function,
            metadata={"description": "Stores permanent user facts"}
        )
        
        # --- MEMORY STATS ---
        conv_count = self.conversations.count()
        fact_count = self.user_facts.count()
        print(Fore.GREEN + f"[MEMORY] Online. Conversations: {conv_count} | Facts: {fact_count}")

    # =========================================================================
    # STORE METHODS (Saving Memories)
    # =========================================================================
    
    def store_conversation(self, user_input, seven_response, user_id="mani"):
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
        Saves an important fact permanently.
        
        Facts are things like:
        - "User's name is Mani"
        - "User's favorite color is blue"  
        - "User prefers dark mode"
        
        WHY facts are separate from conversations:
        - Facts are PERMANENT and should always be found
        - Conversations are temporal (happened at a specific time)
        - In search, facts get PRIORITY over old conversations
        
        Args:
            fact_text:  The fact to remember (e.g., "User likes Python")
            category:   Type of fact: "identity", "preference", "general"
            user_id:    Who this fact is about (ready for V1.2)
        """
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fact_id = f"fact_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Before storing, check if a similar fact already exists
        # This prevents duplicate facts like "name is Mani" stored 100 times
        existing = self._search_collection(self.user_facts, fact_text, n_results=1)
        
        if existing and existing[0]["relevance"] > 0.85:
            # Very similar fact exists — UPDATE it instead of duplicating
            print(Fore.YELLOW + f"[MEMORY] Updating existing fact: '{fact_text[:50]}...'")
            # Delete old version
            self.user_facts.delete(ids=[existing[0]["id"]])
        
        # Store the fact
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
        Searches ALL memory (facts + conversations) for relevant information.
        
        This is the main method called by brain.py before generating a response.
        
        HOW SEMANTIC SEARCH WORKS:
        1. Your query "What color do I like?" becomes a vector
        2. ChromaDB compares this vector to ALL stored vectors
        3. Returns the closest matches by MEANING (not keywords!)
        4. So "What color do I like?" finds "My favorite color is blue"
           even though they share almost no words
        
        Args:
            query:      What to search for (usually the user's current input)
            user_id:    Filter memories to this user only
            n_results:  How many memories to return (default 5)
            
        Returns:
            A formatted string of relevant memories ready to inject into the prompt
            Returns empty string if no relevant memories found
        """
        
        all_results = []
        
        # Search FACTS first (they get priority)
        fact_results = self._search_collection(
            self.user_facts, query, n_results=n_results, user_id=user_id
        )
        for r in fact_results:
            r["source"] = "fact"  # Tag where this came from
        all_results.extend(fact_results)
        
        # Search CONVERSATIONS
        conv_results = self._search_collection(
            self.conversations, query, n_results=n_results, user_id=user_id
        )
        for r in conv_results:
            r["source"] = "conversation"
        all_results.extend(conv_results)
        
        # Sort by relevance (highest first)
        # Facts naturally score higher for direct questions
        all_results.sort(key=lambda x: x["relevance"], reverse=True)
        
        # Take only top N results overall
        all_results = all_results[:n_results]
        
        # Filter out low-relevance noise
        # 0.3 threshold = only return memories that are somewhat related
        # Below 0.3 = probably irrelevant random matches
        RELEVANCE_THRESHOLD = 0.3
        all_results = [r for r in all_results if r["relevance"] >= RELEVANCE_THRESHOLD]
        
        if not all_results:
            return ""
        
        # Format memories into a string for the brain's prompt
        return self._format_memories(all_results)
    
    
    def _search_collection(self, collection, query, n_results=5, user_id=None):
        """
        Internal helper: Searches a single ChromaDB collection.
        
        Returns a list of dicts with:
        - text: The memory content
        - relevance: How relevant it is (0.0 to 1.0)
        - metadata: Extra info (timestamp, user_id, etc.)
        - id: The unique memory ID
        
        WHY this is a separate method:
        - Both search() and store_fact() need to search
        - DRY principle: Don't Repeat Yourself
        """
        
        # Don't search empty collections
        if collection.count() == 0:
            return []
        
        # Build the WHERE filter for user_id
        # This ensures Mani's memories don't leak to other users (V1.2 ready)
        where_filter = None
        if user_id:
            where_filter = {"user_id": user_id}
        
        # Ensure we don't request more results than exist
        actual_n = min(n_results, collection.count())
        
        try:
            # ChromaDB query: converts query to vector, finds nearest neighbors
            results = collection.query(
                query_texts=[query],
                n_results=actual_n,
                where=where_filter
            )
            
            # Parse results into clean format
            parsed = []
            for i in range(len(results["documents"][0])):
                # ChromaDB returns "distance" (lower = more similar)
                # We convert to "relevance" (higher = more similar) for clarity
                distance = results["distances"][0][i]
                relevance = max(0, 1 - (distance / 2))  # Normalize to 0-1 range
                
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
        Automatically detects if the user's input contains a fact worth remembering.
        
        This runs on EVERY user input. It checks patterns like:
        - "My name is Mani"        → Stores: "User's name is Mani"
        - "I love Python"          → Stores: "User loves Python"
        - "My favorite movie is X" → Stores: "User's favorite movie is X"
        
        WHY automatic extraction:
        - User shouldn't have to say "Remember this"
        - Seven should learn passively, like a real assistant
        - Facts are stored separately so they're ALWAYS findable
        
        Args:
            user_input: Raw text from the user
            user_id:    Who said it
        """
        
        clean = user_input.lower().strip()
        
        # --- PATTERN 1: Identity Facts ---
        # "My name is Mani" / "I am Mani" / "Call me Mani"
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
            
        # --- PATTERN 2: Preference Facts ---
        # "My favorite X is Y" / "I love X" / "I like X" / "I prefer X"
        # if "my favorite" in clean or "my favourite" in clean:
        #     self.store_fact(
        #         f"User said: {user_input}",
        #         category="preference",
        #         user_id=user_id
        #     )
        #     return True

        if "my favorite" in clean or "my favourite" in clean:
            # Skip if it's a QUESTION about favorites, not a statement
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
            
        # --- PATTERN 3: Personal Info ---
        # "I am a developer" / "I work at Google" / "I study at MIT"
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
        
        if "i study at" in clean or "i study" in clean and "studying" not in clean:
            self.store_fact(
                f"User said: {user_input}",
                category="personal",
                user_id=user_id
            )
            return True
        
        # --- PATTERN 4: "Remember that" (Explicit Memory Request) ---
        # "Remember that I have a meeting tomorrow"
        if clean.startswith("remember that") or clean.startswith("remember this"):
            fact = user_input.split("that", 1)[-1].strip() if "that" in user_input else user_input.split("this", 1)[-1].strip()
            self.store_fact(
                f"User asked to remember: {fact}",
                category="explicit",
                user_id=user_id
            )
            return True
        
        # No fact detected — that's fine, not every sentence is a fact
        return False

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_stats(self):
        """
        Returns memory statistics for debugging or display.
        Useful for future V3.0 User Console.
        """
        return {
            "total_conversations": self.conversations.count(),
            "total_facts": self.user_facts.count(),
            "storage_path": os.path.abspath(MEMORY_DIR)
        }
    
    def clear_all(self):
        """
        Nuclear option: Deletes ALL memories.
        Used for testing or privacy reset.
        
        WARNING: This is irreversible!
        """
        self.client.delete_collection("conversations")
        self.client.delete_collection("user_facts")
        
        # Recreate empty collections
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
# We create ONE instance that gets imported everywhere
# This ensures all parts of Seven share the same memory
# 
# Usage in other files:
#   from memory import seven_memory
#   seven_memory.search("what's my name?")
#   seven_memory.store_conversation("Hi", "Hello Mani")

seven_memory = SevenMemory()