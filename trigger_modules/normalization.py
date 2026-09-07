"""
trigger_modules/normalization.py
Hotkey string normalization.

Handles:
  - Modifier order: 'Ctrl+Shift+F' == 'shift+ctrl+f' → 'ctrl+shift+f'
  - Shift symbols: 'Shift+!' → 'shift+1'
  - Case insensitive
"""

# Shift+number produces these symbols — map them back to the base key
_SHIFT_SYMBOLS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", "~": "`", "{": "[", "}": "]",
    "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".",
    "?": "/",
}


def normalize_hotkey(hotkey: str) -> str:
    """Normalize a hotkey string for consistent comparison and lookup."""
    MODIFIERS = {"ctrl", "shift", "alt", "win"}
    parts = [
        p.strip().lower()
        for p in hotkey.replace(" ", "").split("+")
        if p.strip()
    ]

    mods = sorted(p for p in parts if p in MODIFIERS)
    keys = []
    for p in parts:
        if p in MODIFIERS:
            continue
        if p in _SHIFT_SYMBOLS:
            keys.append(_SHIFT_SYMBOLS[p])
            if "shift" not in mods:
                mods.append("shift")
                mods.sort()
        else:
            keys.append(p)

    keys.sort()
    return "+".join(mods + keys)