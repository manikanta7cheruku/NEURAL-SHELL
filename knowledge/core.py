"""
=============================================================================
PROJECT SEVEN - knowledge/core.py (Knowledge Store)
Version: 1.10

PURPOSE:
    ChromaDB collection for offline knowledge.
    Separate from user memory — stores general facts, articles, documents.
    Uses same embedding model as memory (all-MiniLM-L6-v2) — zero extra VRAM.

ARCHITECTURE:
    knowledge/indexer.py chunks documents → stores here
    brain.py Layer 5.3 searches here for factual questions
    Results injected into LLM context (same pattern as web search)
=============================================================================
"""

import os
import chromadb
from chromadb.utils import embedding_functions
from colorama import Fore
import config

# =========================================================================
# INITIALIZATION
# =========================================================================

KNOWLEDGE_DIR = os.path.join("seven_data", "knowledge")
CHROMA_DIR = os.path.join(KNOWLEDGE_DIR, "chroma_knowledge")

os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)

# Use same embedding model as memory — already loaded, zero extra cost
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

_client = chromadb.PersistentClient(path=CHROMA_DIR)

knowledge_collection = _client.get_or_create_collection(
    name="seven_knowledge",
    embedding_function=_embedding_fn,
    metadata={"hnsw:space": "cosine"}
)

print(Fore.GREEN + f"[KNOWLEDGE] Loaded: {knowledge_collection.count()} chunks indexed.")


# =========================================================================
# SEARCH
# =========================================================================

def search_knowledge(query, top_k=None):
    """
    Search the knowledge base for relevant information.
    
    Args:
        query: The question or search text
        top_k: Number of results to return (default from config)
    
    Returns:
        str: Formatted knowledge context for LLM injection, or empty string
    """
    if knowledge_collection.count() == 0:
        return ""
    
    if top_k is None:
        top_k = config.KEY.get("knowledge", {}).get("top_k", 3)
    
    try:
        results = knowledge_collection.query(
            query_texts=[query],
            n_results=min(top_k, knowledge_collection.count())
        )
        
        if not results or not results['documents'] or not results['documents'][0]:
            return ""
        
        docs = results['documents'][0]
        distances = results['distances'][0] if results.get('distances') else [0] * len(docs)
        metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(docs)
        
        # Filter by relevance — cosine distance < 0.8 means reasonably relevant
        relevant = []
        for doc, dist, meta in zip(docs, distances, metadatas):
            if dist < 0.8:
                source = meta.get("source", "unknown")
                relevant.append((doc, dist, source))
        
        if not relevant:
            return ""
        
        # Format for LLM context injection
        context = "=== OFFLINE KNOWLEDGE BASE RESULTS ===\n"
        for doc, dist, source in relevant:
            context += f"[Source: {source}]\n{doc}\n\n"
        context += "=== END KNOWLEDGE ===\n"
        context += "Use this information to answer accurately. Cite it naturally."
        
        print(Fore.GREEN + f"[KNOWLEDGE] Found {len(relevant)} relevant chunks (best distance: {relevant[0][1]:.3f})")
        
        return context
    
    except Exception as e:
        print(Fore.RED + f"[KNOWLEDGE] Search error: {e}")
        return ""


# =========================================================================
# STORAGE
# =========================================================================

def store_chunk(text, chunk_id, source="unknown", category="general"):
    """
    Store a single text chunk in the knowledge base.
    
    Args:
        text: The text content
        chunk_id: Unique identifier
        source: Where it came from (filename, URL, etc)
        category: Type of content
    """
    try:
        knowledge_collection.add(
            documents=[text],
            ids=[chunk_id],
            metadatas=[{
                "source": source,
                "category": category
            }]
        )
    except Exception as e:
        # Duplicate ID — skip silently
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            pass
        else:
            print(Fore.RED + f"[KNOWLEDGE] Store error: {e}")


# =========================================================================
# MANAGEMENT
# =========================================================================

def get_knowledge_stats():
    """Get knowledge base statistics."""
    count = knowledge_collection.count()
    
    # Get unique sources
    sources = set()
    if count > 0:
        try:
            all_meta = knowledge_collection.get()
            if all_meta and all_meta['metadatas']:
                for meta in all_meta['metadatas']:
                    sources.add(meta.get("source", "unknown"))
        except:
            pass
    
    storage_size = 0
    for root, dirs, files in os.walk(CHROMA_DIR):
        for f in files:
            storage_size += os.path.getsize(os.path.join(root, f))
    
    return {
        "total_chunks": count,
        "sources": list(sources),
        "source_count": len(sources),
        "storage_mb": round(storage_size / (1024 * 1024), 2)
    }


def clear_knowledge():
    """Clear all knowledge base data."""
    global knowledge_collection
    try:
        _client.delete_collection("seven_knowledge")
        knowledge_collection = _client.get_or_create_collection(
            name="seven_knowledge",
            embedding_function=_embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        print(Fore.GREEN + "[KNOWLEDGE] Knowledge base cleared.")
        return True
    except Exception as e:
        print(Fore.RED + f"[KNOWLEDGE] Clear error: {e}")
        return False