"""
=============================================================================
PROJECT SEVEN - hands/__init__.py (Bridge)
Version: 1.6 (Window Mastery)

Re-exports all hand functions so existing imports still work:
    import hands → hands.open_app(), hands.close_app(), hands.manage_window()
=============================================================================
"""

from hands.core import open_app, close_app, search_web, system_control
from hands.windows import manage_window, get_window_list