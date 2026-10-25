"""
seven_overlay/_glass.py
Called by electron/overlay_daemon.js with window handles: python _glass.py <hwnd> [<hwnd> ...]

The overlay cards are windows of Windows' own acrylic glass. Windows draws a drop shadow around such a window that
Electron's hasShadow:false does not remove, and with it a second dark edge. This turns off DWM's non-client rendering
(which is the shadow) and asks for Windows 11 rounded corners, so a card is one clean pane of glass.
"""
import ctypes
import sys

DWMWA_NCRENDERING_POLICY = 2
DWMNCRP_DISABLED = 1
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


def glass(hwnd: int) -> bool:
    dwm = ctypes.windll.dwmapi
    off = ctypes.c_int(DWMNCRP_DISABLED)
    round_ = ctypes.c_int(DWMWCP_ROUND)
    a = dwm.DwmSetWindowAttribute(hwnd, DWMWA_NCRENDERING_POLICY, ctypes.byref(off), 4)
    dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(round_), 4)   # fails on Windows 10
    return a == 0


if __name__ == "__main__":
    print(" ".join(f"{h}:{'ok' if glass(int(h)) else 'failed'}" for h in sys.argv[1:]))
