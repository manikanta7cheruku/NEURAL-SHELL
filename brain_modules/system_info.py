"""
brain_modules/system_info.py

Answers questions about the user's own machine from live readings, never from
the language model: "what CPU do I have", "how much RAM is free", "which GPU",
"how much disk space is left", "what Windows version am I on", "how long has
my PC been on", "what are my specs".

Static facts (processor name, OS edition, GPU name) are cached for ten
minutes; usage numbers are read when asked. Only questions about THIS machine
match: "what is a GPU" or "how does a CPU work" stay general knowledge.
"""

import logging
import os
import platform
import re
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

_log = logging.getLogger("seven.system_info")
_lock = threading.Lock()
_static: Dict[str, Any] = {}
_static_ts = 0.0
_STATIC_TTL = 600.0
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# --------------------------------------------------------------------------
# Readings
# --------------------------------------------------------------------------


def _reg(path: str, name: str) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            return str(winreg.QueryValueEx(key, name)[0]).strip()
    except Exception:
        return None


def cpu_name() -> str:
    name = _reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
    return re.sub(r"\s+", " ", name) if name else (platform.processor() or "an unknown processor")


def os_name() -> str:
    if os.name != "nt":
        return f"{platform.system()} {platform.release()}".strip()
    product = _reg(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName") or "Windows"
    build = _reg(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuildNumber") or ""
    display = _reg(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion") or ""
    if build.isdigit() and int(build) >= 22000:
        product = product.replace("Windows 10", "Windows 11")    # the registry still says 10 on 11
    parts = [product]
    if display:
        parts.append(f"version {display}")
    if build:
        parts.append(f"build {build}")
    return ", ".join(parts[:1]) + (f" ({', '.join(parts[1:])})" if len(parts) > 1 else "")


def _nvidia() -> Optional[Dict[str, Any]]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            timeout=2, creationflags=_NO_WINDOW, stderr=subprocess.DEVNULL).decode("utf-8", "ignore").strip()
        if not out:
            return None
        name, total, used, util, temp = [p.strip() for p in out.splitlines()[0].split(",")]
        return {"name": name, "vram_gb": round(float(total) / 1024, 1), "vram_used_gb": round(float(used) / 1024, 1),
                "load": int(float(util)), "temp_c": int(float(temp))}
    except Exception:
        return None


def _windows_gpus() -> List[str]:
    if os.name != "nt":
        return []
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_VideoController).Name"],
            timeout=4, creationflags=_NO_WINDOW, stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
        return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def _static_info() -> Dict[str, Any]:
    global _static, _static_ts
    with _lock:
        if _static and time.time() - _static_ts < _STATIC_TTL:
            return dict(_static)
    info = {"cpu": cpu_name(), "os": os_name(), "host": platform.node()}
    try:
        import psutil
        info["cores"] = psutil.cpu_count(logical=False) or os.cpu_count() or 0
        info["threads"] = psutil.cpu_count(logical=True) or os.cpu_count() or 0
    except Exception:
        info["cores"] = info["threads"] = os.cpu_count() or 0
    nv = _nvidia()
    info["gpus"] = [nv["name"]] if nv else _windows_gpus()
    with _lock:
        _static, _static_ts = info, time.time()
    return dict(info)


def snapshot() -> Dict[str, Any]:
    """Everything, with live usage. Never raises."""
    info = _static_info()
    try:
        import psutil
        vm = psutil.virtual_memory()
        info["ram"] = {"total_gb": round(vm.total / 1024 ** 3, 1), "used_gb": round(vm.used / 1024 ** 3, 1),
                       "free_gb": round(vm.available / 1024 ** 3, 1), "percent": int(vm.percent)}
        info["cpu_load"] = int(psutil.cpu_percent(interval=0.3))
        info["uptime_s"] = int(time.time() - psutil.boot_time())
        disks = []
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in (part.opts or "") or not part.fstype:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            disks.append({"drive": part.mountpoint.rstrip("\\/") or part.mountpoint,
                          "total_gb": round(u.total / 1024 ** 3), "free_gb": round(u.free / 1024 ** 3),
                          "percent": int(u.percent)})
        info["disks"] = disks
    except Exception as exc:
        _log.debug("psutil readings unavailable: %s", exc)
    info["gpu"] = _nvidia()
    return info


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

_ASPECTS = {
    "cpu": re.compile(r"\b(?:cpu|processor|cores?|threads)\b"),
    "ram": re.compile(r"\b(?:ram|memory installed|system memory|(?:pc|computer|laptop)s? memory|"
                      r"how much memory (?:do i|does (?:my|this))|memory usage)\b"),
    "gpu": re.compile(r"\b(?:gpu|graphics(?: card)?|video card|vram)\b"),
    "disk": re.compile(r"\b(?:disk|drive|drives|ssd|hdd|storage space|disk space|free space|space left|"
                       r"storage (?:left|free)|how much storage)\b"),
    "os": re.compile(r"\b(?:operating system|which windows|what windows|windows version|version of windows|"
                     r"what os|which os|my os)\b"),
    "uptime": re.compile(r"\b(?:uptime|been (?:on|running|up) for|how long (?:has|have) (?:my|this) "
                         r"(?:pc|computer|laptop|system|machine) been)\b"),
    "specs": re.compile(r"\b(?:specs|specifications|hardware|system info(?:rmation)?|system configuration|"
                        r"(?:pc|computer|laptop|machine|system) (?:details|config))\b"),
}
_MINE = re.compile(r"\b(?:my|i|im|i'm|this|our|me|installed|left|free|usage|used|using|remaining|available|"
                   r"pc|computer|laptop|machine|desktop|rig)\b")
_ABOUT_SEVEN = re.compile(r"\b(?:you|your|yourself|seven)\b")
_REASONING = re.compile(r"\b(?:enough|can (?:my|this|i) \w* ?(?:run|handle|play)|good enough|able to run|"
                        r"handle|upgrade|bottleneck|fast enough|is it good|should i upgrade)\b")
_MACHINE = re.compile(r"\b(?:my|this) (?:pc|computer|laptop|machine|system|rig|desktop|hardware)\b")
_GENERAL = re.compile(r"\b(?:what is an?|what are|how does an?|how do|explain|define|difference between|"
                      r"best|recommend|should i buy|vs|versus)\b")


def match(text: str) -> List[str]:
    """Aspects asked about ("cpu", "ram", ...), or [] when it isn't about this machine."""
    t = re.sub(r"[?!.,]", " ", (text or "").lower()).replace("’", "'")
    t = re.sub(r"\s+", " ", t).strip()
    if not t or not _MINE.search(t):
        return []
    if _GENERAL.search(t) and not re.search(r"\b(?:my|i have|do i|does my|this pc|this computer)\b", t):
        return []
    found = [name for name, rx in _ASPECTS.items() if rx.search(t)]
    if "ram" not in found and re.search(r"\bmemory\b", t) and not _ABOUT_SEVEN.search(t) and \
            re.search(r"\b(?:pc|computer|laptop|system|machine|gb|free|usage|installed)\b", t):
        found.append("ram")
    if found and _ABOUT_SEVEN.search(t) and not re.search(r"\b(?:my|i|this pc|this computer)\b", t):
        return []                                     # "how much storage are you using" is about Seven
    return found


# --------------------------------------------------------------------------
# Answers
# --------------------------------------------------------------------------

def _gb(v: float) -> str:
    if v < 1:
        return f"{int(round(v * 1024))} MB"
    if v >= 1000:
        return f"{v / 1024:.1f} TB"
    return f"{v:g} GB"


def _duration(seconds: int) -> str:
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = [f"{d} day{'s' * (d != 1)}"] if d else []
    if h:
        parts.append(f"{h} hour{'s' * (h != 1)}")
    if m or not parts:
        parts.append(f"{m} minute{'s' * (m != 1)}")
    return " and ".join(parts[:2]) if len(parts) <= 2 else f"{parts[0]}, {parts[1]} and {parts[2]}"


def _cpu(s) -> str:
    cores = f" with {s['cores']} cores and {s['threads']} threads" if s.get("cores") else ""
    load = f" It's at {s['cpu_load']}% load right now." if "cpu_load" in s else ""
    return f"Your processor is an {s['cpu']}{cores}.{load}" if s["cpu"][:1].lower() in "aeiou" \
        else f"Your processor is a {s['cpu']}{cores}.{load}"


def _ram(s) -> str:
    r = s.get("ram")
    if not r:
        return "I can't read your memory usage right now."
    return (f"You have {_gb(r['total_gb'])} of RAM. {_gb(r['used_gb'])} is in use ({r['percent']}%), "
            f"so {_gb(r['free_gb'])} is available.")


def _gpu(s) -> str:
    g = s.get("gpu")
    if g:
        return (f"Your graphics card is an {g['name']} with {g['vram_gb']:g} GB of VRAM. It's at {g['load']}% load "
                f"and {g['temp_c']}°C, using {g['vram_used_gb']:g} GB of VRAM.")
    gpus = s.get("gpus") or []
    if not gpus:
        return "I couldn't detect a graphics card."
    if len(gpus) == 1:
        return f"Your graphics adapter is {gpus[0]}."
    return "Your graphics adapters are " + ", ".join(gpus[:-1]) + f" and {gpus[-1]}."


def _disk(s) -> str:
    disks = s.get("disks") or []
    if not disks:
        return "I can't read your drives right now."
    return " ".join(f"{d['drive']} has {_gb(d['free_gb'])} free of {_gb(d['total_gb'])}." for d in disks)


def _os(s) -> str:
    return f"You're running {s['os']}."


def _uptime(s) -> str:
    if "uptime_s" not in s:
        return "I can't tell how long your PC has been on."
    return f"Your PC has been on for {_duration(s['uptime_s'])}."


def _specs(s) -> str:
    gpu = s.get("gpu", {}) or {}
    gpu_text = f"{gpu['name']} ({gpu['vram_gb']:g} GB VRAM)" if gpu else ", ".join(s.get("gpus") or []) or "no dedicated GPU"
    ram = _gb(s["ram"]["total_gb"]) + " RAM" if s.get("ram") else "unknown RAM"
    storage = ""
    if s.get("disks"):
        total = sum(d["total_gb"] for d in s["disks"])
        free = sum(d["free_gb"] for d in s["disks"])
        storage = f", and {_gb(total)} of storage with {_gb(free)} free"
    cores = f" ({s['cores']} cores, {s['threads']} threads)" if s.get("cores") else ""
    return f"You're on {s['os']} with an {s['cpu']}{cores}, {ram}, {gpu_text}{storage}." \
        if s["cpu"][:1].lower() in "aeiou" else \
        f"You're on {s['os']} with a {s['cpu']}{cores}, {ram}, {gpu_text}{storage}."


_ANSWER = {"cpu": _cpu, "ram": _ram, "gpu": _gpu, "disk": _disk, "os": _os, "uptime": _uptime, "specs": _specs}


def answer(text: str, reader=None) -> Optional[str]:
    """A grounded reply about this machine, or None when the question isn't one."""
    aspects = match(text)
    if not aspects or needs_reasoning(text):
        return None
    s = (reader or snapshot)()
    if "specs" in aspects:
        return _specs(s)
    return " ".join(_ANSWER[a](s) for a in aspects)


def needs_reasoning(text: str) -> bool:
    """'is my RAM enough for X', 'can my laptop run Y': the model answers, with the specs attached."""
    t = (text or "").lower()
    return bool(_REASONING.search(t) and (_MACHINE.search(t) or match_aspects_only(t)))


def match_aspects_only(t: str) -> bool:
    return any(rx.search(t) for rx in _ASPECTS.values())


def prompt_context(reader=None) -> str:
    """One line of machine facts for the model, used when a question depends on the hardware."""
    s = (reader or snapshot)()
    return "User's computer: " + _specs(s)[len("You're on "):]
