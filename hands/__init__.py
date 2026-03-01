"""
=============================================================================
PROJECT SEVEN - hands/__init__.py (Bridge)
Version: 1.7 (System God)

Re-exports all hand functions so existing imports still work:
    import hands → hands.open_app(), hands.manage_window(), hands.manage_system()
=============================================================================
"""

from hands.core import open_app, close_app, search_web, system_control
from hands.windows import manage_window, get_window_list
from hands.system import manage_system, get_system_status
from hands.scheduler import manage_schedule, start_background, get_all_schedules, get_active_count, list_schedules