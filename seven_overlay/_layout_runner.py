import sys, json, os, importlib.util

# Load hands/window_layout.py DIRECTLY without triggering hands/__init__.py
# This skips 500ms of unrelated module loading (config, mood, scheduler, etc.)
_root = r"M:\\Manikanta\\Apps\\MK-Projects\\SEVEN"
os.chdir(_root)

_layout_path = os.path.join(_root, "hands", "window_layout.py")
_spec = importlib.util.spec_from_file_location("window_layout_direct", _layout_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
arrange_specific_windows = _mod.arrange_specific_windows

try:
    raw = sys.stdin.read()
    data = json.loads(raw)
    layout = data.get("layout", "maximize")
    hwnd_list = data.get("hwnd_list", [])
    minimize_hwnds = data.get("minimize_hwnds", [])

    try:
        import win32gui, win32con
        for h in minimize_hwnds:
            try:
                win32gui.ShowWindow(int(float(h)), win32con.SW_MINIMIZE)
            except Exception:
                pass
    except Exception:
        pass

    ok, msg = arrange_specific_windows(hwnd_list, layout)
    print("RESULT:" + json.dumps({"success": ok, "message": msg}))
except Exception as e:
    import traceback; traceback.print_exc()
    print("RESULT:" + json.dumps({"success": False, "message": str(e)}))
