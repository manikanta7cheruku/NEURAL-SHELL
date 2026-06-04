"""
gui.py — DEPRECATED in Seven 1.1.4
Replaced by React frontend + ConversationPanel component.
This file is kept as a stub to prevent import errors.
"""

class SevenGUI:
    """Stub — no longer used. Main UI is now React/Electron."""
    def __init__(self, root=None):
        pass
    def update_status(self, text, color):
        pass
    def close(self):
        import os
        os._exit(0)