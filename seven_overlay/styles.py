"""
seven_overlay/styles.py
Shared visual constants for the overlay system.
Apple-inspired design language.
"""

# Colors
BG_COLOR       = "#0d0d0f"     # near-black background
BG_GLASS       = "#12121a"     # slightly lighter for glass effect
BORDER_COLOR   = "#2a2a3a"     # subtle border
BORDER_GLOW    = "#3a3a5a"     # active border
TEXT_PRIMARY    = "#f0f0f5"     # bright white text
TEXT_SECONDARY  = "#6a6a80"     # muted subtitle
TEXT_ACCENT     = "#7c8cff"     # Seven accent (blue-purple)
SHADOW_COLOR    = "#000000"

# Dimensions
NOTIF_WIDTH      = 380
NOTIF_HEIGHT     = 72
NOTIF_MARGIN_TOP = 24
NOTIF_RADIUS     = 16

# Layout tiles
TILE_WIDTH       = 380
TILE_HEIGHT      = 200
TILE_MARGIN_TOP  = 8

# Animation
ANIM_SLIDE_DURATION = 0.45   # seconds
ANIM_HOLD_DURATION  = 3.0    # seconds visible
ANIM_HIDE_DURATION  = 0.35   # seconds
ANIM_FPS           = 60

# Typography
FONT_TITLE     = ("Segoe UI Variable", 14)
FONT_SUBTITLE  = ("Segoe UI", 9)
FONT_TINY      = ("Segoe UI", 8)
FONT_MONO      = ("Cascadia Code", 8)

# Check if Segoe UI Variable exists, fallback to Segoe UI
try:
    import tkinter as tk
    _root = tk.Tk()
    _root.withdraw()
    _families = tk.font.families()
    if "Segoe UI Variable" not in _families:
        FONT_TITLE = ("Segoe UI", 14)
    _root.destroy()
except Exception:
    FONT_TITLE = ("Segoe UI", 14)