"""
=============================================================================
PROJECT SEVEN - knowledge/indexer.py (Document Indexer)
Version: 1.10

PURPOSE:
    Reads text files, chunks them, and stores in knowledge base.
    Supports: .txt, .md files
    Tracks indexed files to avoid re-indexing (manifest)

ARCHITECTURE:
    User drops files in seven_data/knowledge/custom/
    indexer reads → chunks into ~500 char paragraphs → stores in ChromaDB
    Manifest tracks what's been indexed (file hash + name)
=============================================================================
"""

import os
import json
import hashlib
from colorama import Fore
from knowledge.core import store_chunk
import config

# =========================================================================
# CONFIGURATION
# =========================================================================

KNOWLEDGE_DIR = os.path.join("seven_data", "knowledge")
CUSTOM_DIR = os.path.join(KNOWLEDGE_DIR, "custom")
MANIFEST_FILE = os.path.join(KNOWLEDGE_DIR, "index_manifest.json")

os.makedirs(CUSTOM_DIR, exist_ok=True)

# Supported file extensions
SUPPORTED_EXTENSIONS = {".txt", ".md"}


# =========================================================================
# MANIFEST — Tracks what's been indexed
# =========================================================================

def _load_manifest():
    """Load the index manifest."""
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def _save_manifest(manifest):
    """Save the index manifest."""
    try:
        with open(MANIFEST_FILE, 'w') as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(Fore.RED + f"[INDEXER] Manifest save error: {e}")


def _file_hash(filepath):
    """Get MD5 hash of a file for change detection."""
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except:
        return None


def get_index_manifest():
    """Get the current index manifest."""
    return _load_manifest()


# =========================================================================
# TEXT CHUNKING
# =========================================================================

def _chunk_text(text, chunk_size=None):
    """
    Split text into chunks of approximately chunk_size characters.
    Splits on paragraph boundaries first, then sentence boundaries.
    
    Returns: list of text chunks
    """
    if chunk_size is None:
        chunk_size = config.KEY.get("knowledge", {}).get("chunk_size", 500)
    
    # Split by double newlines (paragraphs) first
    paragraphs = text.split("\n\n")
    
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # If paragraph fits in current chunk, add it
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += para + "\n\n"
        else:
            # Save current chunk if it has content
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            # If paragraph itself is too long, split by sentences
            if len(para) > chunk_size:
                sentences = para.replace(". ", ".\n").split("\n")
                current_chunk = ""
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    if len(current_chunk) + len(sent) + 1 <= chunk_size:
                        current_chunk += sent + " "
                    else:
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = sent + " "
            else:
                current_chunk = para + "\n\n"
    
    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


# =========================================================================
# FILE INDEXING
# =========================================================================

def index_file(filepath):
    """
    Index a single file into the knowledge base.
    
    Args:
        filepath: Path to .txt or .md file
    
    Returns: (success, chunks_added, message)
    """
    filepath = os.path.abspath(filepath)
    
    # Validate file
    if not os.path.exists(filepath):
        return False, 0, f"File not found: {filepath}"
    
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False, 0, f"Unsupported format: {ext}. Use .txt or .md"
    
    # Check manifest — skip if already indexed and unchanged
    manifest = _load_manifest()
    file_hash = _file_hash(filepath)
    filename = os.path.basename(filepath)
    
    if filename in manifest and manifest[filename].get("hash") == file_hash:
        return True, 0, f"Already indexed: {filename} (unchanged)"
    
    # Read file
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    except Exception as e:
        return False, 0, f"Read error: {e}"
    
    if not text.strip():
        return False, 0, f"Empty file: {filename}"
    
    # Chunk and store
    chunks = _chunk_text(text)
    
    if not chunks:
        return False, 0, f"No content to index in {filename}"
    
    stored = 0
    for i, chunk in enumerate(chunks):
        chunk_id = f"{filename}_chunk_{i}_{file_hash[:8]}"
        store_chunk(
            text=chunk,
            chunk_id=chunk_id,
            source=filename,
            category="document"
        )
        stored += 1
    
    # Update manifest
    manifest[filename] = {
        "hash": file_hash,
        "chunks": stored,
        "path": filepath
    }
    _save_manifest(manifest)
    
    print(Fore.GREEN + f"[INDEXER] Indexed {filename}: {stored} chunks")
    return True, stored, f"Indexed {filename}: {stored} chunks"


def index_directory(dirpath=None):
    """
    Index all supported files in a directory.
    
    Args:
        dirpath: Directory to scan (default: seven_data/knowledge/custom/)
    
    Returns: (total_files, total_chunks, messages)
    """
    if dirpath is None:
        dirpath = CUSTOM_DIR
    
    if not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)
        return 0, 0, ["Directory created. Drop .txt or .md files there."]
    
    total_files = 0
    total_chunks = 0
    messages = []
    
    for filename in os.listdir(dirpath):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        
        filepath = os.path.join(dirpath, filename)
        success, chunks, msg = index_file(filepath)
        messages.append(msg)
        
        if success and chunks > 0:
            total_files += 1
            total_chunks += chunks
    
    if total_files == 0 and not messages:
        messages.append(f"No files found in {dirpath}. Drop .txt or .md files there.")
    
    return total_files, total_chunks, messages