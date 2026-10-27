"""
brain_modules/resource_usage.py
What Seven itself costs this PC, next to what everything else is using.

People blame a new app when their PC feels slow. The home screen answers that honestly: how much of the processor,
memory and graphics memory belongs to Seven (its own processes, and the local AI model it runs through Ollama), and
which other apps are using the most memory right now.

    usage() -> {
      "total": {"cpu": 23, "ram_used_gb": 11.2, "ram_total_gb": 16.0, "ram_percent": 70, "gpu": {...} | None},
      "seven": {"cpu": 1.4, "ram_gb": 0.9, "ram_percent": 5.6, "vram_gb": 1.1,
                "parts": [{"name": "Seven", ...}, {"name": "AI model", ...}]},
      "top":   [{"name": "Chrome", "ram_gb": 2.3, "cpu": 4.1, "count": 31}, ...],   # five, Seven not included
    }

CPU is a share of the whole processor (all cores), measured since the previous reading, so the first reading after
start shows 0. Readings are reused for 2 seconds; the home screen asks every 3.
"""
import os
import threading
import time

_ROOT = os.path.normcase(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SEVEN_NAMES = {"seven.exe", "sevenoverlaydaemon.exe", "sevenpanelhost.exe"}
_MODEL_NAMES = {"ollama.exe", "ollama app.exe", "ollama_llama_server.exe", "llama-server.exe"}
# Windows' own plumbing: always running, never the reason a PC is slow, and noise in a "what's using memory" list.
_SYSTEM = {"system", "registry", "memory compression", "secure system", "system idle process", "smss.exe",
           "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe",
           "dwm.exe", "winlogon.exe", "lsaiso.exe", "vmmem", "vmmemwsl"}
_FRIENDLY = {
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "brave.exe": "Brave",
    "opera.exe": "Opera", "code.exe": "VS Code", "explorer.exe": "File Explorer", "teams.exe": "Teams",
    "ms-teams.exe": "Teams", "slack.exe": "Slack", "discord.exe": "Discord", "spotify.exe": "Spotify",
    "whatsapp.exe": "WhatsApp", "whatsapp.root.exe": "WhatsApp", "outlook.exe": "Outlook",
    "olk.exe": "Outlook", "winword.exe": "Word", "excel.exe": "Excel", "powerpnt.exe": "PowerPoint",
    "onedrive.exe": "OneDrive", "msmpeng.exe": "Windows Security", "searchhost.exe": "Windows Search",
    "steam.exe": "Steam", "steamwebhelper.exe": "Steam", "zoom.exe": "Zoom", "notion.exe": "Notion",
    "figma.exe": "Figma", "obs64.exe": "OBS", "vlc.exe": "VLC", "photoshop.exe": "Photoshop",
    "idea64.exe": "IntelliJ IDEA", "pycharm64.exe": "PyCharm", "devenv.exe": "Visual Studio",
    "windowsterminal.exe": "Terminal", "node.exe": "Node.js", "python.exe": "Python", "java.exe": "Java",
    "phoneexperiencehost.exe": "Phone Link", "widgets.exe": "Widgets", "cursor.exe": "Cursor",
    "claude.exe": "Claude", "postman.exe": "Postman", "docker desktop.exe": "Docker",
}

_lock = threading.Lock()
_cache = {"at": 0.0, "value": None}
_gpu_cache = {"at": 0.0, "value": {}}
_desc_cache = {}


def _is_seven(name: str, exe: str) -> bool:
    if name in _SEVEN_NAMES:
        return True
    return bool(exe) and os.path.normcase(exe).startswith(_ROOT)


def _friendly(name: str, exe: str) -> str:
    """A name a person recognises: a known one, else the program's own description, else the file name."""
    if name in _FRIENDLY:
        return _FRIENDLY[name]
    if exe and exe not in _desc_cache:
        _desc_cache[exe] = ""
        try:
            import win32api
            lang, page = win32api.GetFileVersionInfo(exe, "\\VarFileInfo\\Translation")[0]
            d = win32api.GetFileVersionInfo(exe, f"\\StringFileInfo\\{lang:04x}{page:04x}\\FileDescription")
            _desc_cache[exe] = (d or "").strip()[:40]
        except Exception:
            pass
    return _desc_cache.get(exe) or os.path.splitext(name)[0].replace("_", " ").title()


_pdh = {"query": None, "counter": None}


def _gpu_by_pid() -> dict:
    """pid -> dedicated graphics memory in GB, from Windows' own GPU counters (any vendor; the same numbers Task
    Manager shows). nvidia-smi can't report this on most laptops, where Windows manages the GPU's memory."""
    if time.time() - _gpu_cache["at"] < 10:
        return _gpu_cache["value"]
    out = {}
    try:
        import win32pdh
        if _pdh["query"] is None:                    # kept open: collecting again is much cheaper than reopening
            _pdh["query"] = win32pdh.OpenQuery()
            _pdh["counter"] = win32pdh.AddEnglishCounter(_pdh["query"], r"\GPU Process Memory(*)\Dedicated Usage")
        win32pdh.CollectQueryData(_pdh["query"])
        for instance, value in win32pdh.GetFormattedCounterArray(_pdh["counter"], win32pdh.PDH_FMT_LARGE).items():
            parts = instance.split("_")              # pid_1234_luid_0x..._phys_0
            if len(parts) > 1 and parts[1].isdigit():
                pid = int(parts[1])
                out[pid] = out.get(pid, 0.0) + value / 1024 ** 3
    except Exception:
        _pdh["query"] = None
    _gpu_cache.update(at=time.time(), value=out)
    return out


def _processes() -> dict:
    """pid -> (name, private memory in bytes, CPU time in 100 ns units), for every process, in one system call.
    Asking each process separately (psutil) takes ~1.7 s of CPU on a busy PC, because protected processes fall back
    to a slow path; this takes ~15 ms, so measuring Seven doesn't make Seven heavy. Private working set is what Task
    Manager shows as "Memory"."""
    import ctypes
    import struct
    ntdll = ctypes.WinDLL("ntdll")
    size = 1 << 20
    while True:
        buf = ctypes.create_string_buffer(size)
        need = ctypes.c_ulong()
        status = ntdll.NtQuerySystemInformation(5, buf, size, ctypes.byref(need)) & 0xFFFFFFFF   # process list
        if status == 0xC0000004:                                      # buffer too small: processes were started
            size = max(size * 2, need.value + 65536)
            continue
        if status:
            raise OSError(f"NtQuerySystemInformation failed: {status:#x}")
        break
    raw, off, out = buf.raw, 0, {}
    while True:
        nxt, = struct.unpack_from("<I", raw, off)
        private, = struct.unpack_from("<q", raw, off + 8)
        user, kernel = struct.unpack_from("<qq", raw, off + 40)
        length, = struct.unpack_from("<H", raw, off + 56)
        ptr, = struct.unpack_from("<Q", raw, off + 64)
        pid, = struct.unpack_from("<Q", raw, off + 80)
        name = ctypes.wstring_at(ptr, length // 2) if ptr else "System Idle Process"
        out[pid] = (name, private, user + kernel)
        if not nxt:
            break
        off += nxt
    return out


def usage() -> dict:
    with _lock:
        if _cache["value"] is not None and time.time() - _cache["at"] < 2:
            return _cache["value"]
        _cache.update(at=time.time(), value=_read())
        return _cache["value"]


_last = {"at": 0.0, "cpu": {}}
_exe = {}


def _exe_of(pid: int) -> str:
    if pid not in _exe:
        try:
            import psutil
            _exe[pid] = psutil.Process(pid).exe()
        except Exception:
            _exe[pid] = ""
    return _exe[pid]


def _read() -> dict:
    import psutil
    from brain_modules import system_info
    cores = psutil.cpu_count() or 1
    vm = psutil.virtual_memory()
    gpu_mem = _gpu_by_pid()
    me = os.getpid()
    procs = _processes()
    now = time.time()
    elapsed = now - _last["at"] if _last["at"] else 0.0
    before = _last["cpu"]

    seven = {"Seven": {"cpu": 0.0, "ram": 0, "vram": 0.0, "count": 0},
             "AI model": {"cpu": 0.0, "ram": 0, "vram": 0.0, "count": 0}}
    apps = {}
    idle = None
    for pid, (name, private, cpu_time) in procs.items():
        name = name.lower()
        # CPU since the last reading, as a share of every core (cpu_time is in 100 ns units)
        cpu = 0.0
        if elapsed > 0 and pid in before:
            cpu = max(0.0, (cpu_time - before[pid]) / 1e7 / elapsed / cores * 100)
        if pid == 0:                                 # the idle process: what's left is the PC's total load
            idle = cpu if elapsed > 0 and pid in before else None
        if not name or name in _SYSTEM or pid in (0, 4):
            continue
        exe = _exe_of(pid)
        if pid == me or _is_seven(name, exe):
            part = seven["Seven"]
        elif name in _MODEL_NAMES:
            part = seven["AI model"]
        else:
            a = apps.setdefault(_friendly(name, exe), {"cpu": 0.0, "ram": 0, "count": 0})
            a["cpu"] += cpu
            a["ram"] += private
            a["count"] += 1
            continue
        part["cpu"] += cpu
        part["ram"] += private
        part["vram"] += gpu_mem.get(pid, 0.0)
        part["count"] += 1
    _last.update(at=now, cpu={pid: v[2] for pid, v in procs.items()})
    for pid in list(_exe):                           # forget processes that ended
        if pid not in procs:
            _exe.pop(pid, None)

    gb = lambda b: round(b / 1024 ** 3, 2)
    parts = [{"name": k, "cpu": round(v["cpu"], 1), "ram_gb": gb(v["ram"]), "vram_gb": round(v["vram"], 2),
              "running": v["count"] > 0} for k, v in seven.items()]
    seven_ram = sum(v["ram"] for v in seven.values())
    top = sorted(apps.items(), key=lambda kv: kv[1]["ram"], reverse=True)[:5]
    snap = system_info.snapshot()
    return {
        "total": {"cpu": round(max(0.0, 100.0 - idle), 1) if idle is not None else snap.get("cpu_load", 0), "ram_used_gb": gb(vm.total - vm.available),
                  "ram_total_gb": gb(vm.total), "ram_percent": int(vm.percent), "gpu": snap.get("gpu"),
                  "cpu_name": snap.get("cpu", "")},
        "seven": {"cpu": round(sum(v["cpu"] for v in seven.values()), 1), "ram_gb": gb(seven_ram),
                  "ram_percent": round(seven_ram / vm.total * 100, 1) if vm.total else 0,
                  "vram_gb": round(sum(v["vram"] for v in seven.values()), 2), "parts": parts},
        "top": [{"name": k, "ram_gb": gb(v["ram"]), "cpu": round(v["cpu"], 1), "count": v["count"]} for k, v in top],
    }
