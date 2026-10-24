"""
knowledge: the user's document library.

    store.py     documents, passages, reading in the background, hybrid search
    extract.py   PDF, Word, PowerPoint, Excel and text readers with page labels
    core.py      the context block the model reads, and its formatting rules
"""

from knowledge.core import search_knowledge, get_knowledge_stats, clear_knowledge  # noqa: F401
from knowledge.indexer import index_file, index_directory, get_index_manifest  # noqa: F401
