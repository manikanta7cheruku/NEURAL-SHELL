"""
seven_overlay/
Seven's screen overlay system.

Uses Electron for rendering (60fps CSS animations, glassmorphic blur).
Falls back to Windows toast when Electron is not available.

Architecture:
  notification.html    — the visual UI (HTML/CSS/JS)
  notifications.py     — Python API to trigger notifications
  styles.py            — shared constants
  animations.py        — easing functions (kept for future Python overlays)
  
  electron/notif_host.js — Electron window host (spawned per notification)
"""