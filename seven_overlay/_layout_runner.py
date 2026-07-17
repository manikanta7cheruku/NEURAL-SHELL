import sys, json, os
sys.path.insert(0, r"M:\\Manikanta\\Apps\\MK-Projects\\SEVEN")
os.chdir(r"M:\\Manikanta\\Apps\\MK-Projects\\SEVEN")

print("[LAYOUT RUNNER] started", flush=True)
try:
    raw = sys.stdin.read()
    print("[LAYOUT RUNNER] stdin bytes:", len(raw), flush=True)
    data = json.loads(raw)
    layout = data.get("layout", "maximize")
    hwnd_list = data.get("hwnd_list", [])
    minimize_hwnds = data.get("minimize_hwnds", [])
    print(f"[LAYOUT RUNNER] layout={layout} hwnds={len(hwnd_list)} minimize={len(minimize_hwnds)}", flush=True)

    try:
        import win32gui, win32con
        for h in minimize_hwnds:
            try:
                win32gui.ShowWindow(int(float(h)), win32con.SW_MINIMIZE)
            except Exception as me:
                print(f"[LAYOUT RUNNER] minimize {h} failed: {me}", flush=True)
    except Exception as we:
        print(f"[LAYOUT RUNNER] pywin32 error: {we}", flush=True)

    from hands.window_layout import arrange_specific_windows
    ok, msg = arrange_specific_windows(hwnd_list, layout)
    print(f"[LAYOUT RUNNER] result: ok={ok} msg={msg}", flush=True)
    print("RESULT:" + json.dumps({"success": ok, "message": msg}), flush=True)
except Exception as e:
    import traceback
    print("[LAYOUT RUNNER] EXCEPTION:", e, flush=True)
    traceback.print_exc()
    print("RESULT:" + json.dumps({"success": False, "message": str(e)}), flush=True)
