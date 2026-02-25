"""
=============================================================================
PROJECT SEVEN - hands/system.py (System God)
Version: 1.7

CAPABILITIES:
    - Volume control (up, down, mute, unmute, set to specific %)
    - Brightness control (up, down, set to specific %)
    - Battery status (percentage, plugged in, time remaining)
    - WiFi control (on/off, current network, signal strength)
    - Bluetooth control (on/off, paired devices)
    - Media control (play/pause, next, previous, stop)
    - Dark mode toggle
    - Night light toggle
    - Do Not Disturb / Focus Assist toggle
    - Airplane mode toggle

TAG FORMAT:
    ###SYS: action=volume_up value=10
    ###SYS: action=volume_set value=50
    ###SYS: action=volume_mute
    ###SYS: action=brightness_set value=70
    ###SYS: action=battery
    ###SYS: action=wifi_status
    ###SYS: action=media_next
    ###SYS: action=dark_mode_on
    ###SYS: action=night_light_on
    ###SYS: action=dnd_on
    ###SYS: action=airplane_on
=============================================================================
"""

import subprocess
import ctypes
import os
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine

# =========================================================================
# VOLUME CONTROL (pycaw — COM audio endpoint)
# =========================================================================

_volume_interface = None


def _get_volume():
    """Get the Windows audio endpoint volume interface. Works with all pycaw versions."""
    global _volume_interface
    if _volume_interface is not None:
        return _volume_interface
    try:
        import comtypes
        from comtypes import GUID, CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume
        
        # Bypass pycaw's AudioUtilities entirely — go straight to COM
        MMDeviceEnumeratorCLSID = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
        IMMDeviceEnumeratorIID = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
        
        # Define the COM interface manually
        class IMMDevice(comtypes.IUnknown):
            _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
            _methods_ = [
                comtypes.COMMETHOD([], comtypes.HRESULT, 'Activate',
                    (['in'], comtypes.POINTER(GUID), 'iid'),
                    (['in'], comtypes.c_ulong, 'dwClsCtx'),
                    (['in'], comtypes.POINTER(comtypes.c_ulong), 'pActivationParams'),
                    (['out', 'retval'], comtypes.POINTER(comtypes.POINTER(comtypes.IUnknown)), 'ppInterface')),
            ]
        
        class IMMDeviceEnumerator(comtypes.IUnknown):
            _iid_ = IMMDeviceEnumeratorIID
            _methods_ = [
                comtypes.COMMETHOD([], comtypes.HRESULT, 'GetDefaultAudioEndpoint',
                    (['in'], comtypes.c_uint, 'dataFlow'),
                    (['in'], comtypes.c_uint, 'role'),
                    (['out', 'retval'], comtypes.POINTER(comtypes.POINTER(IMMDevice)), 'ppEndpoint')),
            ]
        
        enumerator = comtypes.CoCreateInstance(
            MMDeviceEnumeratorCLSID,
            IMMDeviceEnumerator,
            comtypes.CLSCTX_INPROC_SERVER
        )
        
        # 0 = eRender (speakers), 1 = eMultimedia
        device = enumerator.GetDefaultAudioEndpoint(0, 1)
        
        interface = device.Activate(
            IAudioEndpointVolume._iid_,
            CLSCTX_ALL,
            None
        )
        
        _volume_interface = comtypes.cast(interface, comtypes.POINTER(IAudioEndpointVolume))
        print(Fore.GREEN + "[SYSTEM] Volume control initialized (direct COM)")
        return _volume_interface
        
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Volume COM init failed: {e}")
        print(Fore.YELLOW + "[SYSTEM] Falling back to nircmd for volume control")
        return None


def _volume_up(step=10):
    """Increase volume by step percent."""
    vol = _get_volume()
    if vol:
        try:
            current = vol.GetMasterVolumeLevelScalar()
            new_level = min(1.0, current + (step / 100.0))
            vol.SetMasterVolumeLevelScalar(new_level, None)
            pct = int(new_level * 100)
            print(Fore.GREEN + f"   -> Volume up to {pct}%")
            command_log.log_command("SYS", f"volume_up +{step}", True, f"Now {pct}%")
            mood_engine.on_command_result(True)
            return True, f"Volume's at {pct}%."
        except Exception as e:
            print(Fore.YELLOW + f"   -> COM volume failed, using keypress: {e}")
    
    # Fallback: use media keys via pyautogui
    import pyautogui
    presses = max(1, step // 2)  # Each press ≈ 2%
    pyautogui.press("volumeup", presses=presses)
    print(Fore.GREEN + f"   -> Volume up ({presses} key presses)")
    command_log.log_command("SYS", f"volume_up +{step}", True, f"Keypress x{presses}")
    mood_engine.on_command_result(True)
    return True, "Volume up."


def _volume_down(step=10):
    """Decrease volume by step percent."""
    vol = _get_volume()
    if vol:
        try:
            current = vol.GetMasterVolumeLevelScalar()
            new_level = max(0.0, current - (step / 100.0))
            vol.SetMasterVolumeLevelScalar(new_level, None)
            pct = int(new_level * 100)
            print(Fore.GREEN + f"   -> Volume down to {pct}%")
            command_log.log_command("SYS", f"volume_down -{step}", True, f"Now {pct}%")
            mood_engine.on_command_result(True)
            return True, f"Volume's at {pct}%."
        except Exception as e:
            print(Fore.YELLOW + f"   -> COM volume failed, using keypress: {e}")
    
    # Fallback: use media keys via pyautogui
    import pyautogui
    presses = max(1, step // 2)
    pyautogui.press("volumedown", presses=presses)
    print(Fore.GREEN + f"   -> Volume down ({presses} key presses)")
    command_log.log_command("SYS", f"volume_down -{step}", True, f"Keypress x{presses}")
    mood_engine.on_command_result(True)
    return True, "Volume down."


def _volume_set(level):
    """Set volume to exact percentage (0-100)."""
    vol = _get_volume()
    if vol:
        try:
            level = max(0, min(100, int(level)))
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
            print(Fore.GREEN + f"   -> Volume set to {level}%")
            command_log.log_command("SYS", f"volume_set {level}", True, f"Set {level}%")
            mood_engine.on_command_result(True)
            return True, f"Volume at {level}%."
        except Exception as e:
            print(Fore.YELLOW + f"   -> COM volume set failed: {e}")
    
    # Fallback: use PowerShell to set volume directly (no keypress nonsense)
    try:
        level = max(0, min(100, int(level)))
        ps_cmd = (
            f"$wshShell = New-Object -ComObject WScript.Shell; "
            f"1..50 | ForEach-Object {{ $wshShell.SendKeys([char]174) }}; "  # Vol down to 0
            f"Start-Sleep -Milliseconds 200; "
            f"1..{level // 2} | ForEach-Object {{ $wshShell.SendKeys([char]175) }}"  # Vol up to target
        )
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=10)
        print(Fore.GREEN + f"   -> Volume set to ~{level}% (PowerShell)")
        command_log.log_command("SYS", f"volume_set {level}", True, f"PS ~{level}%")
        mood_engine.on_command_result(True)
        return True, f"Volume at {level}%."
    except Exception as e:
        print(Fore.RED + f"   -> Volume set fallback failed: {e}")
        command_log.log_command("SYS", f"volume_set {level}", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't set exact volume."


def _volume_mute():
    """Toggle mute."""
    vol = _get_volume()
    if vol:
        try:
            is_muted = vol.GetMute()
            vol.SetMute(not is_muted, None)
            state = "unmuted" if is_muted else "muted"
            print(Fore.GREEN + f"   -> Volume {state}")
            command_log.log_command("SYS", f"volume_{state}", True, state)
            mood_engine.on_command_result(True)
            return True, f"{state.title()}."
        except Exception as e:
            print(Fore.YELLOW + f"   -> COM mute failed, using keypress: {e}")
    
    # Fallback
    import pyautogui
    pyautogui.press("volumemute")
    print(Fore.GREEN + "   -> Mute toggled (keypress)")
    command_log.log_command("SYS", "volume_mute", True, "Keypress toggle")
    mood_engine.on_command_result(True)
    return True, "Mute toggled."


def _volume_unmute():
    """Explicitly unmute."""
    vol = _get_volume()
    if vol:
        try:
            vol.SetMute(False, None)
            print(Fore.GREEN + "   -> Volume unmuted")
            command_log.log_command("SYS", "volume_unmute", True, "Unmuted")
            mood_engine.on_command_result(True)
            return True, "Unmuted."
        except Exception as e:
            print(Fore.YELLOW + f"   -> COM unmute failed, using keypress: {e}")
    
    # Fallback: just press mute key (toggle)
    import pyautogui
    pyautogui.press("volumemute")
    print(Fore.GREEN + "   -> Unmute toggled (keypress)")
    command_log.log_command("SYS", "volume_unmute", True, "Keypress toggle")
    mood_engine.on_command_result(True)
    return True, "Unmuted."


def _volume_get():
    """Get current volume level."""
    vol = _get_volume()
    if vol:
        try:
            current = vol.GetMasterVolumeLevelScalar()
            is_muted = vol.GetMute()
            pct = int(current * 100)
            mute_str = ", muted" if is_muted else ""
            print(Fore.GREEN + f"   -> Volume: {pct}%{mute_str}")
            command_log.log_command("SYS", "volume_get", True, f"{pct}%{mute_str}")
            return True, f"Volume's at {pct}%{mute_str}."
        except Exception as e:
            print(Fore.RED + f"   -> Volume get failed: {e}")
    
    return False, "Can't read volume level right now. But I can still adjust it — try 'louder' or 'quieter'."


# =========================================================================
# BRIGHTNESS CONTROL (screen_brightness_control)
# =========================================================================

def _brightness_set(level):
    """Set screen brightness to exact percentage."""
    try:
        import screen_brightness_control as sbc
        level = max(0, min(100, int(level)))
        sbc.set_brightness(level)
        print(Fore.GREEN + f"   -> Brightness set to {level}%")
        command_log.log_command("SYS", f"brightness_set {level}", True, f"Set {level}%")
        mood_engine.on_command_result(True)
        return True, f"Brightness set to {level}%."
    except Exception as e:
        print(Fore.RED + f"   -> Brightness set failed: {e}")
        command_log.log_command("SYS", f"brightness_set {level}", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't set brightness. This may not work on desktop monitors."


def _brightness_up(step=10):
    """Increase brightness by step percent."""
    try:
        import screen_brightness_control as sbc
        current = sbc.get_brightness()[0]
        new_level = min(100, current + step)
        sbc.set_brightness(new_level)
        print(Fore.GREEN + f"   -> Brightness up to {new_level}%")
        command_log.log_command("SYS", f"brightness_up +{step}", True, f"Now {new_level}%")
        mood_engine.on_command_result(True)
        return True, f"Brightness at {new_level}%."
    except Exception as e:
        print(Fore.RED + f"   -> Brightness up failed: {e}")
        command_log.log_command("SYS", "brightness_up", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't adjust brightness."


def _brightness_down(step=10):
    """Decrease brightness by step percent."""
    try:
        import screen_brightness_control as sbc
        current = sbc.get_brightness()[0]
        new_level = max(0, current - step)
        sbc.set_brightness(new_level)
        print(Fore.GREEN + f"   -> Brightness down to {new_level}%")
        command_log.log_command("SYS", f"brightness_down -{step}", True, f"Now {new_level}%")
        mood_engine.on_command_result(True)
        return True, f"Brightness at {new_level}%."
    except Exception as e:
        print(Fore.RED + f"   -> Brightness down failed: {e}")
        command_log.log_command("SYS", "brightness_down", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't adjust brightness."


def _brightness_get():
    """Get current brightness level."""
    try:
        import screen_brightness_control as sbc
        current = sbc.get_brightness()[0]
        print(Fore.GREEN + f"   -> Brightness: {current}%")
        command_log.log_command("SYS", "brightness_get", True, f"{current}%")
        return True, f"Brightness is at {current}%."
    except Exception as e:
        print(Fore.RED + f"   -> Brightness get failed: {e}")
        return False, "Couldn't read brightness level."


# =========================================================================
# BATTERY STATUS (psutil — already in project)
# =========================================================================

def _battery_status():
    """Get battery percentage, plugged-in status, and time remaining."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return True, "No battery detected. This is likely a desktop."
        
        pct = battery.percent
        plugged = battery.power_plugged
        
        if plugged:
            status = f"Battery at {pct}%, plugged in and charging." if pct < 100 else f"Battery fully charged at {pct}%, plugged in."
        else:
            secs = battery.secsleft
            if secs and secs > 0 and secs != -1:
                hours = secs // 3600
                mins = (secs % 3600) // 60
                if hours > 0:
                    time_str = f"{hours} hour{'s' if hours > 1 else ''} and {mins} minutes"
                else:
                    time_str = f"{mins} minutes"
                status = f"Battery at {pct}%, not plugged in. About {time_str} remaining."
            else:
                status = f"Battery at {pct}%, not plugged in."
        
        print(Fore.GREEN + f"   -> {status}")
        command_log.log_command("SYS", "battery", True, f"{pct}% {'plugged' if plugged else 'unplugged'}")
        mood_engine.on_command_result(True)
        return True, status
    except Exception as e:
        print(Fore.RED + f"   -> Battery check failed: {e}")
        command_log.log_command("SYS", "battery", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't check battery status."


# =========================================================================
# WIFI CONTROL (netsh via subprocess)
# =========================================================================

def _wifi_status():
    """Get current WiFi network name and signal strength."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout
        
        if "disconnected" in output.lower() or "there is no wireless" in output.lower():
            return True, "WiFi is disconnected."
        
        # Parse SSID and signal
        ssid = None
        signal = None
        state = None
        
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("SSID") and "BSSID" not in line:
                ssid = line.split(":", 1)[1].strip()
            elif line.startswith("Signal"):
                signal = line.split(":", 1)[1].strip()
            elif line.startswith("State"):
                state = line.split(":", 1)[1].strip()
        
        if ssid and signal:
            status = f"Connected to '{ssid}' with {signal} signal strength."
        elif ssid:
            status = f"Connected to '{ssid}'."
        elif state:
            status = f"WiFi state: {state}."
        else:
            status = "WiFi info unavailable."
        
        print(Fore.GREEN + f"   -> {status}")
        command_log.log_command("SYS", "wifi_status", True, status)
        mood_engine.on_command_result(True)
        return True, status
    except Exception as e:
        print(Fore.RED + f"   -> WiFi status failed: {e}")
        command_log.log_command("SYS", "wifi_status", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't check WiFi status."


def _wifi_on():
    """Enable WiFi adapter."""
    try:
        subprocess.run(
            ["netsh", "interface", "set", "interface", "Wi-Fi", "enabled"],
            capture_output=True, timeout=5
        )
        print(Fore.GREEN + "   -> WiFi enabled")
        command_log.log_command("SYS", "wifi_on", True, "Enabled")
        mood_engine.on_command_result(True)
        return True, "WiFi turned on."
    except Exception as e:
        print(Fore.RED + f"   -> WiFi on failed: {e}")
        command_log.log_command("SYS", "wifi_on", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't enable WiFi. May need admin rights."


def _wifi_off():
    """Disable WiFi adapter."""
    try:
        subprocess.run(
            ["netsh", "interface", "set", "interface", "Wi-Fi", "disabled"],
            capture_output=True, timeout=5
        )
        print(Fore.GREEN + "   -> WiFi disabled")
        command_log.log_command("SYS", "wifi_off", True, "Disabled")
        mood_engine.on_command_result(True)
        return True, "WiFi turned off."
    except Exception as e:
        print(Fore.RED + f"   -> WiFi off failed: {e}")
        command_log.log_command("SYS", "wifi_off", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't disable WiFi. May need admin rights."


# =========================================================================
# BLUETOOTH CONTROL (PowerShell + Windows Radio Manager)
# =========================================================================

def _bluetooth_on():
    """Enable Bluetooth via PowerShell."""
    try:
        # Uses the Windows device management approach
        ps_cmd = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
            "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
            "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
            "$radioTask = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync(); "
            "$asTask = $asTaskGeneric.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]); "
            "$task = $asTask.Invoke($null, @($radioTask)); "
            "$task.Wait(); "
            "$radios = $task.Result; "
            "foreach ($radio in $radios) { "
            "if ($radio.Kind -eq 'Bluetooth') { "
            "$setTask = $radio.SetStateAsync('On'); "
            "$asTaskAction = $asTaskGeneric.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]); "
            "$t = $asTaskAction.Invoke($null, @($setTask)); $t.Wait() } }"
        )
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, timeout=10
        )
        print(Fore.GREEN + "   -> Bluetooth enabled")
        command_log.log_command("SYS", "bluetooth_on", True, "Enabled")
        mood_engine.on_command_result(True)
        return True, "Bluetooth turned on."
    except Exception as e:
        print(Fore.RED + f"   -> Bluetooth on failed: {e}")
        command_log.log_command("SYS", "bluetooth_on", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't enable Bluetooth."


def _bluetooth_off():
    """Disable Bluetooth via PowerShell."""
    try:
        ps_cmd = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
            "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
            "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
            "$radioTask = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync(); "
            "$asTask = $asTaskGeneric.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]); "
            "$task = $asTask.Invoke($null, @($radioTask)); "
            "$task.Wait(); "
            "$radios = $task.Result; "
            "foreach ($radio in $radios) { "
            "if ($radio.Kind -eq 'Bluetooth') { "
            "$setTask = $radio.SetStateAsync('Off'); "
            "$asTaskAction = $asTaskGeneric.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]); "
            "$t = $asTaskAction.Invoke($null, @($setTask)); $t.Wait() } }"
        )
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, timeout=10
        )
        print(Fore.GREEN + "   -> Bluetooth disabled")
        command_log.log_command("SYS", "bluetooth_off", True, "Disabled")
        mood_engine.on_command_result(True)
        return True, "Bluetooth turned off."
    except Exception as e:
        print(Fore.RED + f"   -> Bluetooth off failed: {e}")
        command_log.log_command("SYS", "bluetooth_off", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't disable Bluetooth."


def _bluetooth_status():
    """Check Bluetooth status and list paired devices."""
    try:
        ps_cmd = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
            "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
            "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
            "$radioTask = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync(); "
            "$asTask = $asTaskGeneric.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]); "
            "$task = $asTask.Invoke($null, @($radioTask)); "
            "$task.Wait(); "
            "$radios = $task.Result; "
            "foreach ($radio in $radios) { "
            "if ($radio.Kind -eq 'Bluetooth') { Write-Output $radio.State } }"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        state = result.stdout.strip()
        
        if state.lower() == "on":
            status = "Bluetooth is on."
        elif state.lower() == "off":
            status = "Bluetooth is off."
        else:
            status = f"Bluetooth state: {state if state else 'unknown'}."
        
        print(Fore.GREEN + f"   -> {status}")
        command_log.log_command("SYS", "bluetooth_status", True, status)
        mood_engine.on_command_result(True)
        return True, status
    except Exception as e:
        print(Fore.RED + f"   -> Bluetooth status failed: {e}")
        command_log.log_command("SYS", "bluetooth_status", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't check Bluetooth status."


# =========================================================================
# MEDIA CONTROL (ctypes + virtual key codes — zero dependencies)
# =========================================================================

# Windows virtual key codes for media buttons
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _send_media_key(vk_code, key_name):
    """Send a media key press via ctypes (no dependencies needed)."""
    try:
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        print(Fore.GREEN + f"   -> Media: {key_name}")
        command_log.log_command("SYS", f"media_{key_name}", True, key_name)
        mood_engine.on_command_result(True)
        return True, f"Media: {key_name}."
    except Exception as e:
        print(Fore.RED + f"   -> Media key failed: {e}")
        command_log.log_command("SYS", f"media_{key_name}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't send media {key_name}."


def _media_play_pause():
    return _send_media_key(VK_MEDIA_PLAY_PAUSE, "play/pause")


def _media_next():
    return _send_media_key(VK_MEDIA_NEXT_TRACK, "next track")


def _media_prev():
    return _send_media_key(VK_MEDIA_PREV_TRACK, "previous track")


def _media_stop():
    return _send_media_key(VK_MEDIA_STOP, "stop")


# =========================================================================
# DARK MODE TOGGLE (Registry + restart explorer)
# =========================================================================

def _dark_mode(enable=True):
    """Toggle Windows dark/light mode via registry."""
    try:
        import winreg
        value = 0 if enable else 1  # 0 = dark, 1 = light
        
        # Set for apps
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        
        mode = "dark" if enable else "light"
        print(Fore.GREEN + f"   -> {mode.title()} mode enabled")
        command_log.log_command("SYS", f"dark_mode_{'on' if enable else 'off'}", True, f"{mode} mode")
        mood_engine.on_command_result(True)
        return True, f"{mode.title()} mode enabled. Some apps may need restart."
    except Exception as e:
        print(Fore.RED + f"   -> Dark mode toggle failed: {e}")
        command_log.log_command("SYS", "dark_mode", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't toggle dark mode."


# =========================================================================
# NIGHT LIGHT TOGGLE (Windows Settings URI)
# =========================================================================

def _night_light(enable=True):
    """Toggle night light / blue light filter."""
    try:
        # Windows 10/11: Toggle via registry (BlueLightReduction)
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreduction.bluelightreductionstate\windows.data.bluelightreduction.bluelightreductionstate"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, 
                                 winreg.KEY_READ | winreg.KEY_SET_VALUE)
            data, reg_type = winreg.QueryValueEx(key, "Data")
            
            # Toggle the enable byte (byte at index 18)
            data_list = list(data)
            if len(data_list) > 18:
                if enable:
                    data_list[18] = 0x15  # ON
                else:
                    data_list[18] = 0x13  # OFF
                winreg.SetValueEx(key, "Data", 0, reg_type, bytes(data_list))
            winreg.CloseKey(key)
            
            state = "on" if enable else "off"
            print(Fore.GREEN + f"   -> Night light {state}")
            command_log.log_command("SYS", f"night_light_{state}", True, state)
            mood_engine.on_command_result(True)
            return True, f"Night light turned {state}."
        except FileNotFoundError:
            # Fallback: open Night Light settings page
            os.system("start ms-settings:nightlight")
            state = "on" if enable else "off"
            print(Fore.YELLOW + f"   -> Opened Night Light settings (direct toggle not available)")
            command_log.log_command("SYS", f"night_light_{state}", True, "Opened settings")
            mood_engine.on_command_result(True)
            return True, f"Opened Night Light settings. Toggle it {state} there."
    except Exception as e:
        print(Fore.RED + f"   -> Night light toggle failed: {e}")
        command_log.log_command("SYS", "night_light", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't toggle night light."


# =========================================================================
# DO NOT DISTURB / FOCUS ASSIST (Registry)
# =========================================================================

def _dnd(enable=True):
    """Toggle Do Not Disturb / Focus Assist."""
    try:
        import winreg
        # Focus Assist registry key
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                             winreg.KEY_SET_VALUE)
        # NOGlobalCount: 0 = off, 1 = priority only, 2 = alarms only
        value = 2 if enable else 0
        winreg.SetValueEx(key, "NOGlobalCount", 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        
        state = "on" if enable else "off"
        print(Fore.GREEN + f"   -> Do Not Disturb {state}")
        command_log.log_command("SYS", f"dnd_{state}", True, state)
        mood_engine.on_command_result(True)
        return True, f"Do Not Disturb turned {state}."
    except Exception as e:
        print(Fore.RED + f"   -> DND toggle failed: {e}")
        command_log.log_command("SYS", "dnd", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't toggle Do Not Disturb."


# =========================================================================
# AIRPLANE MODE (PowerShell Radio Manager)
# =========================================================================

def _airplane_mode(enable=True):
    """Toggle airplane mode."""
    try:
        # Use Windows Settings URI as reliable method
        if enable:
            # Turn on airplane mode via RadioManager
            ps_cmd = (
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
                "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
                "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
                "$radioTask = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync(); "
                "$asTask = $asTaskGeneric.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]); "
                "$task = $asTask.Invoke($null, @($radioTask)); "
                "$task.Wait(); "
                "$radios = $task.Result; "
                "foreach ($radio in $radios) { "
                "$setTask = $radio.SetStateAsync('Off'); "
                "$asTaskAction = $asTaskGeneric.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]); "
                "$t = $asTaskAction.Invoke($null, @($setTask)); $t.Wait() }"
            )
        else:
            ps_cmd = (
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
                "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
                "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
                "$radioTask = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync(); "
                "$asTask = $asTaskGeneric.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]); "
                "$task = $asTask.Invoke($null, @($radioTask)); "
                "$task.Wait(); "
                "$radios = $task.Result; "
                "foreach ($radio in $radios) { "
                "$setTask = $radio.SetStateAsync('On'); "
                "$asTaskAction = $asTaskGeneric.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]); "
                "$t = $asTaskAction.Invoke($null, @($setTask)); $t.Wait() }"
            )
        
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, timeout=15
        )
        
        state = "on" if enable else "off"
        print(Fore.GREEN + f"   -> Airplane mode {state}")
        command_log.log_command("SYS", f"airplane_{state}", True, state)
        mood_engine.on_command_result(True)
        return True, f"Airplane mode turned {state}."
    except Exception as e:
        print(Fore.RED + f"   -> Airplane mode failed: {e}")
        command_log.log_command("SYS", "airplane", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't toggle airplane mode."


# =========================================================================
# PUBLIC API — Main entry point
# =========================================================================

def manage_system(params):
    """
    Main entry point. Receives parsed params dict from ###SYS: tag:
        {"action": "volume_up", "value": "10"}
    Returns (success: bool, message: str)
    """
    action = params.get("action", "").lower()
    value = params.get("value", "")
    
    print(Fore.CYAN + f"⚙️ SYSTEM: action={action} value={value}")
    
    # --- VOLUME ---
    if action == "volume_up":
        step = int(value) if value and value.isdigit() else 10
        return _volume_up(step)
    elif action == "volume_down":
        step = int(value) if value and value.isdigit() else 10
        return _volume_down(step)
    elif action == "volume_set":
        if value and value.isdigit():
            return _volume_set(int(value))
        return False, "Need a percentage. Example: 'set volume to 50'."
    elif action == "volume_mute":
        return _volume_mute()
    elif action == "volume_unmute":
        return _volume_unmute()
    elif action == "volume_get":
        return _volume_get()
    
    # --- BRIGHTNESS ---
    elif action == "brightness_up":
        step = int(value) if value and value.isdigit() else 10
        return _brightness_up(step)
    elif action == "brightness_down":
        step = int(value) if value and value.isdigit() else 10
        return _brightness_down(step)
    elif action == "brightness_set":
        if value and value.isdigit():
            return _brightness_set(int(value))
        return False, "Need a percentage. Example: 'set brightness to 70'."
    elif action == "brightness_get":
        return _brightness_get()
    
    # --- BATTERY ---
    elif action == "battery":
        return _battery_status()
    
    # --- WIFI ---
    elif action == "wifi_status":
        return _wifi_status()
    elif action == "wifi_on":
        return _wifi_on()
    elif action == "wifi_off":
        return _wifi_off()
    
    # --- BLUETOOTH ---
    elif action == "bluetooth_on":
        return _bluetooth_on()
    elif action == "bluetooth_off":
        return _bluetooth_off()
    elif action == "bluetooth_status":
        return _bluetooth_status()
    
    # --- MEDIA ---
    elif action == "media_play_pause":
        return _media_play_pause()
    elif action == "media_next":
        return _media_next()
    elif action == "media_prev":
        return _media_prev()
    elif action == "media_stop":
        return _media_stop()
    
    # --- DARK MODE ---
    elif action == "dark_mode_on":
        return _dark_mode(enable=True)
    elif action == "dark_mode_off":
        return _dark_mode(enable=False)
    
    # --- NIGHT LIGHT ---
    elif action == "night_light_on":
        return _night_light(enable=True)
    elif action == "night_light_off":
        return _night_light(enable=False)
    
    # --- DO NOT DISTURB ---
    elif action == "dnd_on":
        return _dnd(enable=True)
    elif action == "dnd_off":
        return _dnd(enable=False)
    
    # --- AIRPLANE MODE ---
    elif action == "airplane_on":
        return _airplane_mode(enable=True)
    elif action == "airplane_off":
        return _airplane_mode(enable=False)
    
    else:
        return False, f"Unknown system action: {action}"


def get_system_status():
    """Get a combined system status report (for dev console)."""
    lines = []
    
    # Volume
    vol = _get_volume()
    if vol:
        try:
            pct = int(vol.GetMasterVolumeLevelScalar() * 100)
            muted = " (MUTED)" if vol.GetMute() else ""
            lines.append(f"Volume:     {pct}%{muted}")
        except:
            lines.append("Volume:     unavailable")
    else:
        lines.append("Volume:     unavailable")
    
    # Brightness
    try:
        import screen_brightness_control as sbc
        bright = sbc.get_brightness()[0]
        lines.append(f"Brightness: {bright}%")
    except:
        lines.append("Brightness: unavailable (desktop monitor?)")
    
    # Battery
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            plug = "plugged in" if battery.power_plugged else "on battery"
            lines.append(f"Battery:    {battery.percent}% ({plug})")
        else:
            lines.append("Battery:    no battery (desktop)")
    except:
        lines.append("Battery:    unavailable")
    
    # WiFi
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=3
        )
        ssid = None
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("SSID") and "BSSID" not in line:
                ssid = line.split(":", 1)[1].strip()
                break
        if ssid:
            lines.append(f"WiFi:       connected to '{ssid}'")
        else:
            lines.append("WiFi:       disconnected")
    except:
        lines.append("WiFi:       unavailable")
    
    return "\n".join(lines)