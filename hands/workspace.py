"""
hands/workspace.py — Thin re-export.
All logic lives in hands/workspace_modules/.
Same pattern as main.py → main_modules/.
"""
from hands.workspace_modules.scanner import scan_current
from hands.workspace_modules.restore import smart_restore, restore