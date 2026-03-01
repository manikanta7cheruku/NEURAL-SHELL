"""
=============================================================================
PROJECT SEVEN - knowledge/__init__.py (Bridge)
Version: 1.10 (Offline Knowledge Base)

Re-exports knowledge functions:
    from knowledge import search_knowledge, index_file, get_knowledge_stats
=============================================================================
"""

from knowledge.core import search_knowledge, get_knowledge_stats, clear_knowledge
from knowledge.indexer import index_file, index_directory, get_index_manifest