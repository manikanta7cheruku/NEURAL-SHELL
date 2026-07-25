"""
hands/app_closer.py
App closing logic for Seven.

Close strategies in priority order:
  1. Process name map (lightning fast taskkill)
  2. Custom alias registry (for user-defined paths)
  3. Special case handlers (camera, whatsapp, browser, explorer)
  4. Smart psutil process scan

Public API:
  close_app(app_name) -> bool
"""

import subprocess
import psutil
import pyautogui
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine
from hands.app_launcher import (
    _resolve_alias,
    _get_custom_paths,
    _custom_alias_to_process,
    _EXTENSION_PROCESS_MAP,
)

SAFE_APPS = ["system", "registry", "service", "nvidia", "antivirus", "explorer"]

_PROCESS_NAME_MAP = {
    "monitor":          ["perfmon.exe", "resmon.exe"],
    "resource monitor": ["perfmon.exe", "resmon.exe"],
    "calculator":       ["CalculatorApp.exe", "calc.exe"],
    "photos":           ["Microsoft.Photos.exe", "Photos.exe"],
    "store":            ["WinStore.App.exe"],
    "mail":             ["HxOutlook.exe", "HxTsr.exe"],
    "maps":             ["Maps.exe"],
    "clock":            ["TimeDate.CPL"],
    "settings":         ["SystemSettings.exe"],
    "paint":            ["mspaint.exe"],
    "notepad":          ["notepad.exe"],
    "explorer":         ["explorer.exe"],
    "chrome":           ["chrome.exe"],
    "firefox":          ["firefox.exe"],
    "edge":             ["msedge.exe"],
    "brave":            ["brave.exe"],
    "spotify":          ["Spotify.exe"],
    "discord":          ["Discord.exe"],
    "telegram":         ["Telegram.exe"],
    "whatsapp":         ["WhatsApp.exe", "WhatsAppDesktop.exe"],
    "vlc":              ["vlc.exe"],
    "zoom":             ["Zoom.exe"],
    "teams":            ["Teams.exe", "ms-teams.exe"],
    "outlook":          ["OUTLOOK.EXE"],
    "word":             ["WINWORD.EXE"],
    "excel":            ["EXCEL.EXE"],
    "powerpoint":       ["POWERPNT.EXE"],
    "obs":              ["obs64.exe", "obs32.exe"],
    "steam":            ["steam.exe"],
    "vs code":          ["Code.exe"],
    "vscode":           ["Code.exe"],
    "code":             ["Code.exe"],
    "task manager":     ["Taskmgr.exe"],
    "powershell":       ["powershell.exe", "pwsh.exe"],
    "cmd":              ["cmd.exe"],
    "terminal":         ["WindowsTerminal.exe"],
}


def close_app(app_name: str) -> bool:
    """
    Close an application by name.

    Tries multiple strategies in order, returns True on first success.
    """
    raw_name = app_name.strip()
    close_all = False

    if raw_name.upper().startswith("ALL_"):
        close_all = True
        raw_name = raw_name[4:]

    clean_name = _resolve_alias(raw_name.lower().strip())
    _CREATE_NO_WINDOW = 0x08000000
    _flag = "/F" if close_all else ""

    # Strategy 1: Process name map (instant taskkill)
    _target_processes = _PROCESS_NAME_MAP.get(clean_name, [])
    if _target_processes:
        for proc_exe in _target_processes:
            try:
                result = subprocess.call(
                    f"taskkill /IM {proc_exe} {_flag}",
                    shell=True,
                    creationflags=_CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result == 0:
                    print(Fore.GREEN + f"   -> Lightning kill: {proc_exe}")
                    command_log.log_command("CLOSE", clean_name, True, f"Lightning: {proc_exe}")
                    mood_engine.on_command_result(True)
                    return True
            except Exception:
                continue
        print(Fore.YELLOW + f"   -> Process map miss for '{clean_name}', scanning...")
    else:
        direct_exe = f"{clean_name}.exe"
        try:
            result = subprocess.call(
                f"taskkill /IM {direct_exe} {_flag}",
                shell=True,
                creationflags=_CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result == 0:
                print(Fore.GREEN + f"   -> Direct taskkill: {direct_exe}")
                command_log.log_command("CLOSE", clean_name, True, f"Direct: {direct_exe}")
                mood_engine.on_command_result(True)
                return True
        except Exception:
            pass

    # Strategy 2: Custom alias registry
    process_names_to_try = _custom_alias_to_process.get(clean_name, [])
    if not process_names_to_try:
        custom_paths = _get_custom_paths()
        if clean_name in custom_paths:
            file_path = custom_paths[clean_name]
            import os
            ext = os.path.splitext(file_path)[1].lower()
            process_names_to_try = _EXTENSION_PROCESS_MAP.get(ext, [])

    _is_custom_alias = (
        clean_name in _custom_alias_to_process or
        clean_name in _get_custom_paths()
    )

    if process_names_to_try:
        flat = []
        for item in process_names_to_try:
            if isinstance(item, list):
                flat.extend(item)
            else:
                flat.append(item)

        for proc_name in flat:
            if not isinstance(proc_name, str):
                continue
            pn_lower = proc_name.lower().replace('.exe', '')
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    p_lower = proc.info['name'].lower()
                    if pn_lower in p_lower or p_lower.startswith(pn_lower):
                        proc.kill()
                        print(Fore.GREEN + f"   -> Closed {proc.info['name']} for '{clean_name}'")
                        command_log.log_command("CLOSE", clean_name, True,
                                               f"Via alias -> {proc.info['name']}")
                        mood_engine.on_command_result(True)
                        return True
                except Exception:
                    continue

        if _is_custom_alias:
            command_log.log_command("CLOSE", clean_name, False, "Process not running")
            mood_engine.on_command_result(False)
            return False

    # Strategy 3: Special case handlers
    if clean_name in ["current", "this", "it", "active window"]:
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
        except Exception:
            pyautogui.hotkey('alt', 'f4')
        command_log.log_command("CLOSE", clean_name, True, "Active window WM_CLOSE")
        mood_engine.on_command_result(True)
        return True

    if "control panel" in clean_name:
        subprocess.Popen(
            'powershell -command "(New-Object -ComObject Shell.Application)'
            '.Windows() | Where-Object { $_.LocationName -match \'Control Panel\' }'
            ' | ForEach-Object { $_.quit() }"',
            shell=True
        )
        command_log.log_command("CLOSE", "control panel", True, "PowerShell COM")
        mood_engine.on_command_result(True)
        return True

    if "explorer" in clean_name or "file" in clean_name:
        cmd = ("(New-Object -ComObject Shell.Application).Windows() | foreach-object { $_.quit() }"
               if close_all else
               "(New-Object -ComObject Shell.Application).Windows() | Select-Object -Last 1 | foreach-object { $_.quit() }")
        subprocess.Popen(['powershell', '-command', cmd])
        command_log.log_command("CLOSE", "explorer", True,
                               "All windows" if close_all else "1 window")
        mood_engine.on_command_result(True)
        return True

    if "calculator" in clean_name or "calc" in clean_name:
        subprocess.Popen("taskkill /im CalculatorApp.exe /f", shell=True)
        command_log.log_command("CLOSE", "calculator", True, "Force kill")
        mood_engine.on_command_result(True)
        return True

    if "whatsapp" in clean_name:
        killed = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'whatsapp' in proc.info['name'].lower():
                    proc.kill()
                    killed = True
            except Exception:
                continue
        if not killed:
            for wname in ["WhatsApp.exe", "whatsapp.exe", "WhatsAppDesktop.exe"]:
                subprocess.Popen(
                    f"taskkill /im {wname} /f", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        command_log.log_command("CLOSE", "whatsapp", True, "Force kill")
        mood_engine.on_command_result(True)
        return True

    if "camera" in clean_name:
        cam_killed = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if any(cn in proc.info['name'].lower() for cn in ["windowscamera", "camera"]):
                    proc.kill()
                    cam_killed = True
            except Exception:
                continue
        if not cam_killed:
            subprocess.Popen(
                ['powershell', '-command',
                 'Get-Process | Where-Object {$_.Name -like "*camera*"} | Stop-Process -Force'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            cam_killed = True
        command_log.log_command("CLOSE", "camera", cam_killed, "UWP kill via psutil")
        mood_engine.on_command_result(cam_killed)
        return cam_killed

    if "task manager" in clean_name:
        subprocess.Popen(
            'powershell -Command "Start-Process taskkill -ArgumentList \'/im Taskmgr.exe /f\' -Verb RunAs"',
            shell=True
        )
        command_log.log_command("CLOSE", "task manager", True, "Admin kill")
        mood_engine.on_command_result(True)
        return True

    browsers = ["chrome", "firefox", "edge", "brave", "opera"]
    if any(b in clean_name for b in browsers):
        if close_all:
            proc_names = {
                "chrome": "chrome.exe", "firefox": "firefox.exe",
                "edge": "msedge.exe", "brave": "brave.exe", "opera": "opera.exe",
            }
            for b, pname in proc_names.items():
                if b in clean_name:
                    subprocess.Popen(f"taskkill /im {pname} /f", shell=True)
                    command_log.log_command("CLOSE", clean_name, True, f"All {pname} killed")
                    break
        else:
            import time
            try:
                subprocess.Popen(
                    f'powershell -command "(New-Object -ComObject WScript.Shell)'
                    f'.AppActivate(\'chrome\')"',
                    shell=True
                )
                time.sleep(0.3)
                pyautogui.hotkey('alt', 'f4')
                command_log.log_command("CLOSE", clean_name, True, "Alt+F4 frontmost window")
            except Exception as e:
                command_log.log_command("CLOSE", clean_name, False, str(e))
                mood_engine.on_command_result(False)
                return False
        mood_engine.on_command_result(True)
        return True

    # Strategy 4: Smart psutil scan
    matching = []
    for proc in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            pname = proc.info['name'].lower()
            if clean_name in pname and not any(s in pname for s in SAFE_APPS):
                matching.append(proc)
        except Exception:
            pass

    if not matching:
        print(Fore.RED + f"HANDS: Could not find process for '{clean_name}'")
        command_log.log_command("CLOSE", clean_name, False, "Process not found")
        mood_engine.on_command_result(False)
        return False

    if close_all:
        for proc in matching:
            try:
                proc.kill()
            except Exception:
                pass
        command_log.log_command("CLOSE", clean_name, True, f"All {len(matching)} terminated")
        mood_engine.on_command_result(True)
        return True

    try:
        matching.sort(key=lambda p: p.info.get('create_time', 0), reverse=True)
        matching[0].kill()
        command_log.log_command("CLOSE", clean_name, True,
                               f"1 terminated, {len(matching)-1} remaining")
        mood_engine.on_command_result(True)
        return True
    except Exception as e:
        print(Fore.RED + f"HANDS: Failed to close '{clean_name}': {e}")
        command_log.log_command("CLOSE", clean_name, False, str(e))
        mood_engine.on_command_result(False)
        return False