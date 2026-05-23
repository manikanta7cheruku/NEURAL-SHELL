"""
=============================================================================
PROJECT SEVEN - main.py (The Controller)
Version: 1.1 (Memory Integration)
Version: 1.1.1 (Memory + Mood + Command Logging)
Version: 1.1.2 (Memory + Mood + Command Logging + Polish)
Version: 1.2 (Memory + Mood + Command Logging + Voice Identity)
Version: 1.3 (Interruption & Full Duplex)

CHANGES FROM V1.5:
    1. NEW: Memory system initialized on startup
    2. NEW: Every conversation stored in long-term memory after response
    3. REMOVED: Commented-out V2.0 vision code (clean slate for when we need it)
    4. KEPT: All V1.5 app control logic (unchanged, still working)
    
ARCHITECTURE:
    GUI Thread (tkinter) ←→ Logic Thread (seven_logic)
        └→ ears.listen() → brain.think() → mouth.speak()    
                              ↑                ↓
                         memory.search()   memory.store()
=============================================================================
"""

"""
PROJECT SEVEN - main.py (The Controller)
Version: 1.3 + Packaged App Support (Phase 8 Fixed)
"""

import sys
import os

# Fix Windows encoding issues
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# MUST BE FIRST — Path setup before ANY other import
# ============================================================================

# Add SEVEN_APP_PATH (set by Electron for packaged app)
_app_path = os.environ.get('SEVEN_APP_PATH', '')
if _app_path and _app_path not in sys.path:
    sys.path.insert(0, _app_path)

# Add embedded Python paths (packaged app only)
if _app_path:
    _embedded_python = os.path.join(_app_path, 'python', 'python.exe')
    _embedded_sp     = os.path.join(_app_path, 'python', 'Lib', 'site-packages')
    _embedded_lib    = os.path.join(_app_path, 'python', 'Lib')
    _embedded_dlls   = os.path.join(_app_path, 'python', 'DLLs')

    print(f"[SYSTEM] App path: {_app_path}")
    print(f"[SYSTEM] Site-packages exists: {os.path.exists(_embedded_sp)}")

    # ── If we are running under WRONG Python, re-launch under embedded Python ──
    # This happens when developer runs `python main.py` with system Python
    # In packaged app, Electron always spawns the embedded python.exe correctly
    _running_embedded = (
        os.path.exists(_embedded_python) and
        os.path.normcase(sys.executable) == os.path.normcase(_embedded_python)
    )

    if not _running_embedded and os.path.exists(_embedded_python):
        # Check if we are in packaged app (not dev mode test)
        _is_packaged = os.path.exists(
            os.path.join(_app_path, 'python', 'python311.dll')
        ) or os.path.exists(
            os.path.join(_app_path, 'python', 'python3.dll')
        )

        if _is_packaged:
            print(f"[SYSTEM] Wrong Python detected. Re-launching under embedded Python...")
            import subprocess
            result = subprocess.run(
                [_embedded_python] + sys.argv,
                env={**os.environ, 'SEVEN_RELAUNCHED': '1'}
            )
            sys.exit(result.returncode)

    # Add embedded paths to sys.path
    _embedded_paths = [
        _embedded_sp,
        _embedded_lib,
        _embedded_dlls,
        os.path.join(_app_path, 'python'),
    ]
    for _p in _embedded_paths:
        if os.path.exists(_p) and _p not in sys.path:
            sys.path.insert(0, _p)

# Add CWD
_cwd = os.getcwd()
if _cwd not in sys.path:
    sys.path.insert(0, _cwd)

# ============================================================================
# PACKAGE CHECK — Must happen AFTER path setup
# ============================================================================

def _packages_ready():
    """
    Check if minimum packages for FULL server are installed.
    Uses embedded Python when running in packaged app.
    Uses sys.executable in dev mode.
    """
    import subprocess

    # ── Find correct Python to check against ──
    # In packaged app: SEVEN_APP_PATH points to resources/app
    # Embedded Python is at resources/app/python/python.exe
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    embedded_python = os.path.join(app_path, 'python', 'python.exe') if app_path else ''

    if app_path and os.path.exists(embedded_python):
        python = embedded_python
        print(f"[SYSTEM] Checking embedded Python: {embedded_python}")
    else:
        python = sys.executable
        print(f"[SYSTEM] Checking system Python: {python}")

    # ── Check site-packages path ──
    if app_path:
        sp = os.path.join(app_path, 'python', 'Lib', 'site-packages')
        print(f"[SYSTEM] Site-packages exists: {os.path.exists(sp)}")

    critical = ['fastapi', 'uvicorn', 'pyttsx3', 'speech_recognition']

    for pkg in critical:
        result = subprocess.run(
            [python, '-c', f'import {pkg.replace("-","_")}'],
            capture_output=True
        )
        if result.returncode != 0:
            print(f"[SYSTEM] Missing package: {pkg}")
            return False

    print("[SYSTEM] Core packages ready.")
    return True


# ── Detect Electron mode ──
# Multiple signals because env var alone is unreliable in packaged apps:
#   1. SEVEN_ELECTRON_MODE explicitly set (preferred)
#   2. SEVEN_APP_PATH set AND embedded python311.dll exists (packaged install)
#   3. Running under embedded python.exe (not system Python)
# If ANY signal says we're in Electron, skip tkinter entirely.
def _detect_electron_mode():
    if os.environ.get('SEVEN_ELECTRON_MODE') == '1':
        return True
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    if app_path:
        # Embedded Python distribution always has python311.dll alongside python.exe
        if os.path.exists(os.path.join(app_path, 'python', 'python311.dll')):
            return True
        if os.path.exists(os.path.join(app_path, 'python', 'python3.dll')):
            return True
    # Last resort: check if we're running embedded python.exe
    if 'resources' in sys.executable.replace('\\', '/').lower() and 'app' in sys.executable.replace('\\', '/').lower():
        return True
    # Final check: tkinter not importable = treat as Electron mode (safe default)
    try:
        import tkinter as _tk_test
        _tk_test  # silence unused
        return False
    except ImportError:
        print("[SYSTEM] tkinter not available — forcing Electron mode")
        return True

IS_ELECTRON_MODE = _detect_electron_mode()
print(f"[SYSTEM] Electron mode: {IS_ELECTRON_MODE}")

if not _packages_ready():
    print("[SYSTEM] Core packages not installed — starting in pre-setup mode")
    print("[SYSTEM] Waiting for setup wizard to install packages...")

    from backend.startup import run_minimal_server
    run_minimal_server(host="127.0.0.1", port=7777)

    print("[SYSTEM] Minimal server started. Waiting for setup to complete...")

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        os._exit(0)

    os._exit(0)

# ============================================================================
# FULL STARTUP — All packages available
# ============================================================================

print("[SYSTEM] Packages ready — starting full Seven...")

# ── These are safe to import immediately (no heavy models) ──
import threading
import re
import random

import colorama
from colorama import Fore
colorama.init()

import config

# ── API server imports (FastAPI only — no AI models) ──
from backend.api_server import start_api_server, set_state as api_set_state

# ── Admin server ──
from backend.admin_server import start_admin_server

# ── Telemetry (SQLite only — fast) ──
import telemetry

# ── Heavy imports done LAZILY inside seven_logic thread ──
# ears, brain, mouth, memory load AFTER API server is already up
# This means the frontend can connect within 2-3 seconds

# ============================================================================
# GLOBAL STATE
# ============================================================================

app_ui = None

# ============================================================================
# SEVEN LOGIC THREAD
# ============================================================================

def seven_logic():
    global app_ui

    # ── Load heavy modules here — AFTER API server is already running ──
    # This is why startup is fast — API responds in 2s, models load in background
    print("[SYSTEM] Loading AI modules...")

    from ears import listen
    from ears.voice_id import (identify_speaker, enroll_speaker,
                                is_voice_id_enabled, get_enrolled_speakers)
    from ears.core import listen_for_interrupt
    import brain
    import brain_manager
    import hands.core as core
    import hands.system as system_mod
    import hands.scheduler as scheduler_mod
    import hands.windows as hands_windows
    import mouth
    from mouth import interrupt as mouth_interrupt, is_speaking
    from memory import seven_memory
    from memory.mood import mood_engine
    from memory.command_log import command_log

    print("[SYSTEM] AI modules loaded.")

    is_active = True

    # ── Interrupt configuration ──
    interrupt_config = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED   = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS     = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN  = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]

    interrupt_context = {
        "last_response":    None,
        "last_input":       None,
        "was_interrupted":  False
    }

    # ── Wake / pause / kill words ──
    WAKE_WORDS  = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                   "pause", "stop listening", "sleep", "silence"]
    KILL_WORDS  = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]

    def speak_with_interrupt(text):
        """Speak with interrupt detection. Returns True if completed."""
        import time as _time
        if not INTERRUPT_ENABLED or (_time.time() - last_interrupt_time[0] < INTERRUPT_COOLDOWN):
            mouth.speak(text)
            return True

        stop_listening  = threading.Event()
        was_interrupted = threading.Event()

        def on_interrupt():
            was_interrupted.set()
            mouth_interrupt()
            last_interrupt_time[0] = _time.time()

        interrupt_thread = threading.Thread(
            target=listen_for_interrupt,
            args=(INTERRUPT_WORDS, on_interrupt, stop_listening),
            daemon=True
        )
        interrupt_thread.start()

        completed = mouth.speak(text)

        stop_listening.set()
        interrupt_thread.join(timeout=2)

        if was_interrupted.is_set():
            print("[SYSTEM] ⚡ Speech interrupted by user")
            app_ui.update_status("INTERRUPTED", "#ffaa00")
            interrupt_context["was_interrupted"] = True
            interrupt_context["last_response"]   = text
            mouth.speak("Yeah?")
            return False

        return True

    # ── Startup stats ──
    stats      = seven_memory.get_stats()
    mood_status = mood_engine.get_status()
    cmd_stats  = command_log.get_stats()

    print(Fore.GREEN   + f"[SYSTEM] Memory: {stats['total_conversations']} conversations, "
                         f"{stats['total_facts']} facts")
    print(Fore.MAGENTA + f"[SYSTEM] Mood: {mood_status['mood_value']:.2f} ({mood_status['label']})")
    print(Fore.CYAN    + f"[SYSTEM] Commands: {cmd_stats['total']} (success: {cmd_stats['success_rate']})")

    if is_voice_id_enabled():
        speakers = get_enrolled_speakers()
        print(Fore.CYAN + f"[SYSTEM] Voice ID active. Speakers: {', '.join(speakers)}")
    else:
        print(Fore.YELLOW + "[SYSTEM] Voice ID inactive.")

    # ── Initial greeting ──
    mouth.speak(f"{config.KEY['identity']['name']} online.")
    scheduler_mod.start_background(speak_fn=mouth.speak)
    sched_count = scheduler_mod.get_active_count()
    if sched_count > 0:
        print(Fore.CYAN + f"[SYSTEM] Scheduler: {sched_count} pending schedule(s).")
    app_ui.update_status("SYSTEM ONLINE", "#00ff00")

    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    while True:
        try:
            # ── GUI / API state ──
            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00")
                api_set_state("listening", True)
                api_set_state("thinking",  False)
                api_set_state("speaking",  False)
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555")
                api_set_state("listening", False)

            # ── Listen ──
            user_input, audio_path = listen()
            if not user_input:
                continue

            text_lower = user_input.lower()

            # ── Interrupt context handler ──
            if interrupt_context["was_interrupted"]:
                resume_words = ["continue", "resume", "go on", "go ahead",
                                "keep going", "carry on"]
                if any(w in text_lower for w in resume_words):
                    old_response = interrupt_context["last_response"]
                    old_input    = interrupt_context["last_input"]
                    interrupt_context.update(
                        {"was_interrupted": False, "last_response": None, "last_input": None}
                    )
                    if old_response and old_input:
                        resume_prompt = (
                            f"I was interrupted while answering: '{old_input}'. "
                            f"I had said: '{old_response}'. "
                            f"Continue from where I left off naturally."
                        )
                        response = brain.think(resume_prompt, speaker_id="default")
                        if response:
                            speak_with_interrupt(response)
                        else:
                            mouth.speak("Sorry, I lost my train of thought.")
                    else:
                        mouth.speak("Sorry, I lost my train of thought. Ask me again?")
                else:
                    interrupt_context.update(
                        {"was_interrupted": False, "last_response": None, "last_input": None}
                    )
                continue

            # ── Voice ID ──
            speaker_id = "default"
            if audio_path and is_voice_id_enabled():
                speaker_id = identify_speaker(audio_path)
                print(Fore.CYAN + f"[VOICE ID] Speaker: {speaker_id}")
                api_set_state("current_speaker", speaker_id)

            # ── Voice enrollment ──
            if "enroll my voice" in text_lower or "enroll voice" in text_lower:
                mouth.speak("What name should I save this voice as?")
                app_ui.update_status("ENROLLING — Speak your name...", "#ff00ff")
                name_input, name_audio = listen()
                if name_input:
                    enroll_name = name_input.strip().replace(".", "").replace("!", "")
                    mouth.speak(f"Now say a few sentences, {enroll_name}.")
                    app_ui.update_status(f"ENROLLING {enroll_name}...", "#ff00ff")
                    enroll_input, enroll_audio = listen()
                    if enroll_audio:
                        success = enroll_speaker(enroll_name, enroll_audio)
                        mouth.speak(
                            f"Got it, {enroll_name}." if success
                            else "I couldn't capture your voice clearly. Try again."
                        )
                    else:
                        mouth.speak("I didn't hear anything. Try again.")
                else:
                    mouth.speak("I didn't catch your name. Try again.")
                continue

            # ── Kill command ──
            if any(trigger in text_lower for trigger in KILL_WORDS):
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            # ── Wake command ──
            if any(trigger in text_lower for trigger in WAKE_WORDS):
                if not is_active:
                    is_active = True
                    mouth.speak("I'm listening.")
                    app_ui.update_status("RESUMED", "#00ff00")
                continue

            # ── Pause command ──
            if is_active and any(trigger in text_lower for trigger in PAUSE_WORDS):
                is_active = False
                mouth.speak("Standing by.")
                app_ui.update_status("PAUSED", "#555555")
                continue

            if not is_active:
                continue

            # ── Core processing ──
            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status("THINKING...", "#ff00ff")
            api_set_state("thinking", True)
            api_set_state("listening", False)

            response = brain.think(user_input, speaker_id=speaker_id)
            telemetry.log_activity()

            if not response:
                response = "Processing error."

            is_streaming = (
                isinstance(response, tuple)
                and len(response) == 2
                and response[0] == "__STREAM__"
            )
            completed = True

            # ── Memory storage ──
            should_store = True
            if isinstance(response, str) and response.strip().startswith("###"):
                should_store = False
            if len(user_input.strip()) <= 3:
                should_store = False
            if user_input.lower().strip() in ["hi", "hello", "hey"]:
                should_store = False

            # ── Speech part ──
            speech_part = response
            if isinstance(response, str) and "###" in response:
                speech_part = response.split("###")[0].strip()

            api_set_state("speaking", True)

            if is_streaming:
                _, sentence_gen = response
                interrupt_context["last_input"] = user_input
                full_parts = []
                for sentence in sentence_gen:
                    full_parts.append(sentence)
                    if "###" in sentence:
                        continue
                    completed = speak_with_interrupt(sentence)
                    if not completed:
                        break
                response    = " ".join(full_parts)
                speech_part = response.split("###")[0].strip() if "###" in response else response
                app_ui.update_status(
                    "⚡ INTERRUPTED" if not completed else speech_part[:80],
                    "#ffaa00" if not completed else "#00ccff"
                )
            elif speech_part:
                interrupt_context["last_input"] = user_input
                completed = speak_with_interrupt(speech_part)
                app_ui.update_status(
                    "⚡ INTERRUPTED" if not completed else speech_part,
                    "#ffaa00" if not completed else "#00ccff"
                )

            api_set_state("speaking", False)
            api_set_state("thinking", False)

            # ── Store conversation ──
            if should_store and isinstance(response, str):
                try:
                    clean_response = re.sub(r'###\w+:\s*\S+', '', response).strip()
                    if not completed and clean_response:
                        clean_response = f"[INTERRUPTED] {clean_response}"
                    if clean_response:
                        seven_memory.store_conversation(
                            user_input, clean_response,
                            user_id=speaker_id if speaker_id not in ("default", "unknown")
                                   else "default"
                        )
                except Exception as e:
                    print(Fore.RED + f"[MEMORY ERROR] {e}")

            # ── Command pipeline ──
            if not isinstance(response, str):
                continue

            # Window commands
            window_cmds = re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", response)
            for param_str in window_cmds:
                params = {}
                for pair in param_str.strip().split():
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip()
                if params:
                    try:
                        success, msg = hands_windows.manage_window(params)
                        if success:
                            app_ui.update_status(f"🪟 {msg}", "#00ff00")
                            if params.get("action") == "list" and msg:
                                speak_with_interrupt(msg)
                        else:
                            api_set_state("speaking", True)
                            mouth.speak(msg)
                            api_set_state("speaking", False)
                            app_ui.update_status(f"🪟 FAILED: {msg}", "#ff0000")
                    except Exception as e:
                        print(Fore.RED + f"[WINDOW CMD ERROR] {e}")

            # Scheduler commands
            sched_cmds = re.findall(r"###SCHED:\s*(.*?)(?=###|$)", response)
            for param_str in sched_cmds:
                params = {"speaker_id": speaker_id}
                for pair in param_str.strip().split():
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip()
                if params:
                    success, msg = scheduler_mod.manage_schedule(params)
                    telemetry.log_activity()
                    if success:
                        app_ui.update_status(f"📅 {msg}", "#00ff00")
                        if msg:
                            speak_with_interrupt(msg)
                    else:
                        api_set_state("speaking", True)
                        mouth.speak(msg)
                        api_set_state("speaking", False)
                        app_ui.update_status(f"📅 FAILED: {msg}", "#ff0000")

            # System commands
            sys_cmds = re.findall(r"###SYS:\s*(.*?)(?=###|$)", response)
            for param_str in sys_cmds:
                params = {}
                for pair in param_str.strip().split():
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip()
                if params:
                    success, msg = system_mod.manage_system(params)
                    if success:
                        app_ui.update_status(f"⚙️ {msg}", "#00ff00")
                        action = params.get("action", "")
                        if action in ["battery", "volume_get", "brightness_get",
                                      "wifi_status", "bluetooth_status"] and msg:
                            speak_with_interrupt(msg)
                    else:
                        api_set_state("speaking", True)
                        mouth.speak(msg)
                        api_set_state("speaking", False)
                        app_ui.update_status(f"⚙️ FAILED: {msg}", "#ff0000")

            # App open/close/search commands
            commands = re.findall(r"###(OPEN|CLOSE|SEARCH):\s*(.*?)(?=###|$)", response)
            for cmd_type, arg in commands:
                clean_arg = arg.replace('"','').replace("'","").replace(",","").replace(".","").strip()
                if not clean_arg:
                    continue

                # Split multiple apps
                if " and " in clean_arg:
                    sub_apps = clean_arg.split(" and ")
                elif "," in clean_arg:
                    sub_apps = clean_arg.split(",")
                elif "&" in clean_arg:
                    sub_apps = clean_arg.split("&")
                else:
                    sub_apps = [clean_arg]

                for app_name in sub_apps:
                    app_name = app_name.strip()
                    if not app_name:
                        continue

                    if cmd_type == "OPEN":
                        app_ui.update_status(f"OPENING: {app_name}", "#00ff00")
                        success = core.open_app(app_name)
                        telemetry.log_activity()
                        if not success:
                            api_set_state("speaking", True)
                            mouth.speak(f"Can't find {app_name}. Is it installed?")
                            api_set_state("speaking", False)

                    elif cmd_type == "CLOSE":
                        app_ui.update_status(f"CLOSING: {app_name}", "#ff0000")
                        success = core.close_app(app_name)
                        telemetry.log_activity()
                        if not success:
                            api_set_state("speaking", True)
                            mouth.speak(f"{app_name} doesn't seem to be running.")
                            api_set_state("speaking", False)

                    elif cmd_type == "SEARCH":
                        app_ui.update_status(f"SEARCHING: {app_name}", "#0000ff")
                        core.search_web(app_name)

            # Clean up temp audio
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        except Exception as e:
            print(Fore.RED + f"[CRITICAL ERROR] Main loop: {e}")
            import traceback
            traceback.print_exc()
            app_ui.update_status("ERROR RECOVERED", "#ff0000")


# ============================================================================
# START APP
# ============================================================================

def start_app():
    global app_ui

    is_electron = IS_ELECTRON_MODE

    if is_electron:
        print(Fore.CYAN + "[SYSTEM] Running in ELECTRON mode (no Tkinter GUI)")
    else:
        print(Fore.YELLOW + "[SYSTEM] Running in STANDALONE mode (with Tkinter GUI)")

    # ── Start API server FIRST — frontend can connect immediately ──
    start_api_server(host="127.0.0.1", port=7777)
    print(Fore.GREEN + "[SYSTEM] API server up — frontend can connect now")

    # ── Start telemetry (SQLite only — fast) ──
    try:
        telemetry.start_telemetry()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Telemetry skipped: {e}")

    # ── Admin server ──
    try:
        start_admin_server()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Admin server skipped: {e}")

    if is_electron:
        class DummyUI:
            def update_status(self, text, color):
                pass
            def close(self):
                print(Fore.RED + "[SYSTEM] Shutdown requested")
                os._exit(0)

        app_ui = DummyUI()

        logic_thread = threading.Thread(target=seven_logic, daemon=True)
        logic_thread.start()

        print(Fore.GREEN + "[SYSTEM] Backend running. Electron handles UI.")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(Fore.RED + "\n[SYSTEM] Interrupted by user")
            os._exit(0)

    else:
        # Try standalone tkinter mode. If tkinter is missing, fall back to headless.
        try:
            import tkinter as tk
            import gui as gui_module

            root   = tk.Tk()
            app_ui = gui_module.SevenGUI(root)

            logic_thread = threading.Thread(target=seven_logic, daemon=True)
            logic_thread.start()

            root.mainloop()
        except ImportError as e:
            print(Fore.YELLOW + f"[SYSTEM] tkinter unavailable ({e}) — running headless")

            class DummyUI:
                def update_status(self, text, color):
                    pass
                def close(self):
                    print(Fore.RED + "[SYSTEM] Shutdown requested")
                    os._exit(0)

            app_ui = DummyUI()
            logic_thread = threading.Thread(target=seven_logic, daemon=True)
            logic_thread.start()

            print(Fore.GREEN + "[SYSTEM] Headless mode active — API server running")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(Fore.RED + "\n[SYSTEM] Interrupted by user")
                os._exit(0)


if __name__ == "__main__":
    start_app()