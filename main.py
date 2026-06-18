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

    print("[SYSTEM] Loading AI modules...")

    try:
        from ears import listen
        from ears.voice_id import (identify_speaker, enroll_speaker,
                                    is_voice_id_enabled, get_enrolled_speakers)
        from ears.core import listen_for_interrupt
        print("[SYSTEM] Ears loaded ✓")
    except Exception as e:
        print(f"[SYSTEM] ✗ Ears failed to load: {e}")
        import traceback
        traceback.print_exc()
        app_ui.update_status("EARS ERROR - check logs", "#ff0000")
        return

    try:
        import brain
        import brain_manager
        print("[SYSTEM] Brain loaded ✓")
    except Exception as e:
        print(f"[SYSTEM] ✗ Brain failed to load: {e}")
        import traceback
        traceback.print_exc()
        app_ui.update_status("BRAIN ERROR - check logs", "#ff0000")
        return

    try:
        import hands.core as core
        import hands.system as system_mod
        import hands.scheduler as scheduler_mod
        import hands.windows as hands_windows
        print("[SYSTEM] Hands loaded ✓")
    except Exception as e:
        print(f"[SYSTEM] ✗ Hands failed to load: {e}")
        import traceback
        traceback.print_exc()

    print(Fore.CYAN + "[SYSTEM] Past hands block, entering mouth/memory block...")

    # Initialize Windows COM for this thread before importing pyttsx3/mouth
    # pyttsx3 uses COM objects which must be initialized on the calling thread
    try:
        import pythoncom
        pythoncom.CoInitialize()
        print(Fore.CYAN + "[SYSTEM] COM initialized for voice thread")
    except Exception as _com_err:
        print(Fore.YELLOW + f"[SYSTEM] COM init skipped: {_com_err}")

    # Import mouth - if it fails, use a fallback that just prints
    mouth = None
    mouth_interrupt = None
    is_speaking = None
    try:
        print(Fore.CYAN + "[SYSTEM] About to import mouth...")
        # Force reimport - clear any cached module state
        import sys as _sys
        for _k in list(_sys.modules.keys()):
            if 'mouth' in _k.lower() or 'pyttsx' in _k.lower():
                del _sys.modules[_k]
        import mouth as _mouth_mod
        mouth = _mouth_mod
        from mouth import interrupt as mouth_interrupt, is_speaking
        print(Fore.GREEN + "[SYSTEM] Mouth loaded ✓")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Mouth failed: {e}")
        import traceback
        traceback.print_exc()
        # Do NOT return - create a fallback mouth so voice loop still starts
        class _FallbackMouth:
            def speak(self, text):
                print(f"[MOUTH FALLBACK] {text}")
            def interrupt(self):
                pass
            def is_speaking(self):
                return False
        mouth = _FallbackMouth()
        mouth_interrupt = mouth.interrupt
        is_speaking = mouth.is_speaking
        print(Fore.YELLOW + "[SYSTEM] Using fallback mouth - no audio output")

    print(Fore.CYAN + "[SYSTEM] Past mouth block, entering memory block...")

    seven_memory = None
    mood_engine  = None
    command_log  = None
    try:
        print(Fore.CYAN + "[SYSTEM] Importing memory...")
        from memory import seven_memory as _sm
        from memory.mood import mood_engine as _me
        from memory.command_log import command_log as _cl
        seven_memory = _sm
        mood_engine  = _me
        command_log  = _cl
        print(Fore.CYAN + "[SYSTEM] Memory imported, forcing init...")
        _ = seven_memory.get_stats()
        print(Fore.GREEN + "[SYSTEM] Memory loaded ✓")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Memory failed: {e}")
        import traceback
        traceback.print_exc()

    print(Fore.GREEN + "[SYSTEM] AI modules loaded.")

    is_active = True

    interrupt_config  = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS   = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]

    interrupt_context = {
        "last_response":   None,
        "last_input":      None,
        "was_interrupted": False
    }

    WAKE_WORDS  = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                   "pause", "stop listening", "sleep", "silence"]
    KILL_WORDS  = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]

    def speak_with_interrupt(text):
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
            print("[SYSTEM] Speech interrupted by user")
            app_ui.update_status("INTERRUPTED", "#ffaa00")
            interrupt_context["was_interrupted"] = True
            interrupt_context["last_response"]   = text
            mouth.speak("Yeah?")
            return False

        return True

    # Silence watcher
    _silence_watcher = None
    _last_topic_ref  = [None]
    try:
        from pipeline.silence_watcher import SilenceWatcher
        _silence_watcher = SilenceWatcher(
            speak_fn          = speak_with_interrupt,
            get_last_topic_fn = lambda: _last_topic_ref[0],
        )
        _sw_thread = threading.Thread(target=_silence_watcher.start, daemon=True)
        _sw_thread.start()
        print(Fore.CYAN + "[SYSTEM] Silence watcher started ✓")
    except Exception as _sw_err:
        print(Fore.YELLOW + f"[SYSTEM] Silence watcher skipped: {_sw_err}")

    # Startup stats
    try:
        if seven_memory:
            stats = seven_memory.get_stats()
            print(Fore.GREEN + f"[SYSTEM] Memory: {stats['total_conversations']} conversations, "
                               f"{stats['total_facts']} facts")
        if mood_engine:
            mood_status = mood_engine.get_status()
            print(Fore.MAGENTA + f"[SYSTEM] Mood: {mood_status['mood_value']:.2f} ({mood_status['label']})")
        if command_log:
            cmd_stats = command_log.get_stats()
            print(Fore.CYAN + f"[SYSTEM] Commands: {cmd_stats['total']} (success: {cmd_stats['success_rate']})")
    except Exception as _stats_err:
        print(Fore.YELLOW + f"[SYSTEM] Stats skipped: {_stats_err}")

    try:
        if is_voice_id_enabled():
            speakers = get_enrolled_speakers()
            print(Fore.CYAN + f"[SYSTEM] Voice ID active. Speakers: {', '.join(speakers)}")
        else:
            print(Fore.YELLOW + "[SYSTEM] Voice ID inactive.")
    except Exception:
        pass

        # Initial greeting
    try:
        print(Fore.GREEN + "[SYSTEM] Speaking startup greeting...")
        mouth.speak(f"{config.KEY['identity']['name']} online.")
        print(Fore.GREEN + "[SYSTEM] Greeting spoken")
    except Exception as _greet_err:
        print(Fore.RED + f"[SYSTEM] Greeting failed: {_greet_err}")
        import traceback
        traceback.print_exc()

    # Start scheduler
    try:
        from backend.api_server import set_schedule_alert as _alert_fn
        scheduler_mod.start_background(
            speak_fn=mouth.speak,
            alert_fn=_alert_fn
        )
        print(Fore.GREEN + "[SYSTEM] Scheduler started with banner support")
    except Exception:
        scheduler_mod.start_background(speak_fn=mouth.speak)
        print(Fore.YELLOW + "[SYSTEM] Scheduler started without banner support")

    # Register and start background schedule daemon
    try:
        import subprocess as _sp
        import sys as _sys
        import os as _os

        _daemon = _os.path.join(_os.getcwd(), "schedule_daemon.py")
        _python = _sys.executable

        _task_check = _sp.run(
            ["schtasks", "/query", "/tn", "SevenScheduleDaemon"],
            capture_output=True
        )
        if _task_check.returncode != 0:
            # Use Windows startup folder instead of schtasks (no admin needed)
            try:
                _startup_folder = _os.path.join(
                    _os.environ.get('APPDATA', ''),
                    'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
                )
                _shortcut_path = _os.path.join(_startup_folder, 'SevenDaemon.bat')
                with open(_shortcut_path, 'w') as _sf:
                    _sf.write(f'@echo off\nstart /b "" "{_python}" "{_daemon}"\n')
                print(Fore.GREEN + "[SYSTEM] Schedule daemon registered in Startup folder")
            except Exception as _reg_err:
                print(Fore.YELLOW + f"[SYSTEM] Daemon startup registration failed: {_reg_err}")

        if _os.path.exists(_daemon):
            _sp.Popen(
                [_python, _daemon],
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                stdin=_sp.DEVNULL,
                creationflags=0x00000008 | 0x00000200 | 0x08000000
            )
            print(Fore.CYAN + "[SYSTEM] Schedule daemon running in background")
    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Daemon skipped: {_de}")

    # Register background daemon for schedules when Seven is closed
    try:
        scheduler_mod.register_daemon_startup()
    except Exception:
        pass

        # Start daemon in background for this session too
    try:
        import subprocess
        import sys
        import os
        _daemon_path = os.path.join(os.getcwd(), "schedule_daemon.py")
        if os.path.exists(_daemon_path):
            subprocess.Popen(
                [sys.executable, _daemon_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            print(Fore.CYAN + "[SYSTEM] Schedule daemon started in background")
    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Daemon start skipped: {_de}")

    app_ui.update_status("SYSTEM ONLINE", "#00ff00")

    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    while True:
        try:
            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00")
                api_set_state("listening", True)
                api_set_state("thinking",  False)
                # Only clear speaking if it was set - avoid resetting fade timer
                # api_set_state("speaking", False) removed - speaking cleared after each response
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555")
                api_set_state("listening", False)

            user_input, audio_path = listen()
            if not user_input:
                continue

            if _silence_watcher:
                _silence_watcher.on_user_spoke()
            _last_topic_ref[0] = user_input

            text_lower = user_input.lower().strip()

            # Filter Whisper hallucinations
            _hallucinations = {
                "thank you", "thanks", "thank you.", "thanks.",
                "you", "the", "bye", "bye.", "yes", "no",
                "thanks for watching", "thank you for watching",
                ".", "..", "...", " ", ""
            }
            if text_lower in _hallucinations or len(text_lower) < 2:
                print(Fore.YELLOW + f"[EARS] Filtered: '{user_input}'")
                continue

            # Interrupt context
            if interrupt_context["was_interrupted"]:
                resume_words = ["continue", "resume", "go on", "go ahead", "keep going", "carry on"]
                if any(w in text_lower for w in resume_words):
                    old_response = interrupt_context["last_response"]
                    old_input    = interrupt_context["last_input"]
                    interrupt_context.update({"was_interrupted": False, "last_response": None, "last_input": None})
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
                            mouth.speak("Sorry, lost my train of thought.")
                    else:
                        mouth.speak("Sorry, lost my train of thought. Ask me again?")
                else:
                    interrupt_context.update({"was_interrupted": False, "last_response": None, "last_input": None})
                continue

            # Voice ID
            speaker_id = "default"
            if audio_path and is_voice_id_enabled():
                speaker_id = identify_speaker(audio_path)
                print(Fore.CYAN + f"[VOICE ID] Speaker: {speaker_id}")
                api_set_state("current_speaker", speaker_id)

            # Voice enrollment
            if "enroll my voice" in text_lower or "enroll voice" in text_lower:
                mouth.speak("What name should I save this voice as?")
                app_ui.update_status("ENROLLING - Speak your name...", "#ff00ff")
                name_input, name_audio = listen()
                if name_input:
                    enroll_name = name_input.strip().replace(".", "").replace("!", "")
                    mouth.speak(f"Now say a few sentences, {enroll_name}.")
                    app_ui.update_status(f"ENROLLING {enroll_name}...", "#ff00ff")
                    enroll_input, enroll_audio = listen()
                    if enroll_audio:
                        success = enroll_speaker(enroll_name, enroll_audio)
                        mouth.speak(f"Got it, {enroll_name}." if success else "Could not capture your voice clearly. Try again.")
                    else:
                        mouth.speak("I did not hear anything. Try again.")
                else:
                    mouth.speak("I did not catch your name. Try again.")
                continue

            # Kill
            if any(trigger in text_lower for trigger in KILL_WORDS):
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            # Wake
            if any(trigger in text_lower for trigger in WAKE_WORDS):
                if not is_active:
                    is_active = True
                    mouth.speak("Listening.")
                    app_ui.update_status("RESUMED", "#00ff00")
                    if _silence_watcher:
                        _silence_watcher.set_paused(False)
                continue

            # Pause
            if is_active and any(trigger in text_lower for trigger in PAUSE_WORDS):
                is_active = False
                mouth.speak("Standing by.")
                app_ui.update_status("PAUSED", "#555555")
                if _silence_watcher:
                    _silence_watcher.set_paused(True)
                api_set_state("user_text",  "")
                api_set_state("seven_text", "")
                continue

            if not is_active:
                continue

            # Core processing
            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status("THINKING...", "#ff00ff")
            api_set_state("thinking",  True)
            api_set_state("listening", False)
            api_set_state("user_text", user_input)
            api_set_state("seven_text", "")

            # Fact limit pre-check
            _fact_triggers = [
                "remember that", "remember this", "my name is",
                "call me", "i love", "i like", "i prefer",
                "i am a", "i work at", "i study at",
                "my favorite", "my favourite"
            ]
            if any(t in user_input.lower() for t in _fact_triggers):
                try:
                    import voice_limits
                    if seven_memory:
                        _current_facts = seven_memory.user_facts.count()
                        _fact_ok, _fact_msg = voice_limits.check("facts_limit", _current_facts)
                        if not _fact_ok:
                            api_set_state("speaking", True)
                            mouth.speak(_fact_msg)
                            api_set_state("speaking", False)
                            app_ui.update_status("PLAN LIMIT", "#ffaa00")
                            continue
                except Exception:
                    pass

            # Brain think - THIS IS THE KEY FIX: brain.think not brain_modules.think
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

            should_store = True
            if isinstance(response, str) and response.strip().startswith("###"):
                should_store = False
            if len(user_input.strip()) <= 3:
                should_store = False
            if user_input.lower().strip() in ["hi", "hello", "hey"]:
                should_store = False

            speech_part = response
            if isinstance(response, str) and "###" in response:
                speech_part = response.split("###")[0].strip()

            if not is_streaming and speech_part:
                api_set_state("seven_text", speech_part)

            api_set_state("speaking", True)
            if _silence_watcher:
                _silence_watcher.on_seven_speaking(True)

            if is_streaming:
                _, sentence_gen = response
                interrupt_context["last_input"] = user_input
                full_parts = []
                for sentence in sentence_gen:
                    full_parts.append(sentence)
                    if "###" in sentence:
                        continue
                    api_set_state("seven_text", " ".join(p for p in full_parts if "###" not in p))
                    completed = speak_with_interrupt(sentence)
                    if not completed:
                        break
                response    = " ".join(full_parts)
                speech_part = response.split("###")[0].strip() if "###" in response else response
                app_ui.update_status(
                    "INTERRUPTED" if not completed else speech_part[:80],
                    "#ffaa00" if not completed else "#00ccff"
                )
            elif speech_part:
                interrupt_context["last_input"] = user_input
                completed = speak_with_interrupt(speech_part)
                app_ui.update_status(
                    "INTERRUPTED" if not completed else speech_part,
                    "#ffaa00" if not completed else "#00ccff"
                )

            api_set_state("speaking", False)
            api_set_state("thinking", False)
            if _silence_watcher:
                _silence_watcher.on_seven_speaking(False)

            # Store conversation
            if should_store and isinstance(response, str) and seven_memory:
                try:
                    import voice_limits
                    current_convos = seven_memory.conversations.count()
                    allowed, limit_msg = voice_limits.check("conversation_history", current_convos)
                    if allowed:
                        clean_response = re.sub(r'###\w+:\s*\S+', '', response).strip()
                        if not completed and clean_response:
                            clean_response = f"[INTERRUPTED] {clean_response}"
                        if clean_response:
                            # Use configured user name as default user_id
                            # Falls back to "default" if name not configured
                            _default_uid = config.KEY.get(
                                'identity', {}
                            ).get('user_name', 'default').lower() or "default"
                            seven_memory.store_conversation(
                                user_input, clean_response,
                                user_id=speaker_id if speaker_id not in
                                        ("default", "unknown") else _default_uid
                            )
                    else:
                        print(Fore.YELLOW + f"[LIMIT] Conversation memory full ({current_convos})")
                except Exception as e:
                    print(Fore.RED + f"[MEMORY ERROR] {e}")

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
                            app_ui.update_status(f"Window: {msg}", "#00ff00")
                            if params.get("action") == "list" and msg:
                                speak_with_interrupt(msg)
                        else:
                            mouth.speak(msg)
                            app_ui.update_status(f"Window failed: {msg}", "#ff0000")
                    except Exception as e:
                        print(Fore.RED + f"[WINDOW ERROR] {e}")

            # Scheduler commands
            sched_cmds = re.findall(r"###SCHED:\s*(.*?)(?=###|$)", response)
            for param_str in sched_cmds:
                params = {"speaker_id": speaker_id}
                for pair in param_str.strip().split():
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip()
                if params:
                    action = params.get("action", "")
                    if action in ("alarm", "reminder", "timer", "event"):
                        try:
                            import voice_limits
                            recur = params.get("recur", "")
                            if recur and recur not in ("", "none"):
                                rec_ok, rec_msg = voice_limits.check_bool("recurring_schedules")
                                if not rec_ok:
                                    mouth.speak(rec_msg)
                                    app_ui.update_status("PLAN LIMIT", "#ffaa00")
                                    continue
                            current_scheds = scheduler_mod.get_active_count()
                            sched_ok, sched_msg = voice_limits.check("schedules", current_scheds)
                            if not sched_ok:
                                mouth.speak(sched_msg)
                                app_ui.update_status("PLAN LIMIT", "#ffaa00")
                                continue
                        except Exception:
                            pass
                    success, msg = scheduler_mod.manage_schedule(params)
                    telemetry.log_activity()
                    if success:
                        app_ui.update_status(f"Schedule: {msg}", "#00ff00")
                        # Only speak scheduler message if brain gave no ack
                        # Brain ack is in speech_part already spoken above
                        # Scheduler msg would be a duplicate confirmation
                        # Only speak if it contains time info (genuinely new info)
                        if msg and any(x in msg for x in [
                            "AM", "PM", "today", "tomorrow", "minutes", "seconds",
                            "hours", "Monday", "Tuesday", "Wednesday", "Thursday",
                            "Friday", "Saturday", "Sunday"
                        ]):
                            speak_with_interrupt(msg)
                    else:
                        mouth.speak(msg)
                        app_ui.update_status(f"Schedule failed: {msg}", "#ff0000")

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
                        app_ui.update_status(f"System: {msg}", "#00ff00")
                        action = params.get("action", "")
                        if action in ["battery", "volume_get", "brightness_get",
                                      "wifi_status", "bluetooth_status"] and msg:
                            speak_with_interrupt(msg)
                    else:
                        mouth.speak(msg)
                        app_ui.update_status(f"System failed: {msg}", "#ff0000")

            # App commands
            commands = re.findall(r"###(OPEN|CLOSE|SEARCH):\s*(.*?)(?=###|$)", response)
            for cmd_type, arg in commands:
                clean_arg = arg.replace('"','').replace("'","").replace(",","").replace(".","").strip()
                if not clean_arg:
                    continue
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
                        app_ui.update_status(f"Opening: {app_name}", "#00ff00")
                        already = core._check_already_running(app_name)
                        if already:
                            mouth.speak(f"{app_name} is already running.")
                        else:
                            success = core.open_app(app_name)
                            telemetry.log_activity()
                            if not success:
                                mouth.speak(
                                    f"Cannot find {app_name}. "
                                    f"If it keeps failing, report it in the feedback section."
                                )
                    elif cmd_type == "CLOSE":
                        app_ui.update_status(f"Closing: {app_name}", "#ff0000")
                        success = core.close_app(app_name)
                        telemetry.log_activity()
                        if not success:
                            mouth.speak(f"{app_name} does not seem to be running.")
                    elif cmd_type == "SEARCH":
                        app_ui.update_status(f"Searching: {app_name}", "#0000ff")
                        core.search_web(app_name)

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
                # Push status text to React frontend via api_set_state
                # This is how the conversation panel gets updated
                try:
                    api_set_state("status_text", text)
                    api_set_state("status_color", color)
                except Exception:
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
        # Standalone mode — no Electron, no Tkinter
        # gui.py is removed. Use DummyUI that pushes to API state.
        print(Fore.YELLOW + "[SYSTEM] Standalone mode — headless with API frontend")

        class DummyUI:
            def update_status(self, text, color):
                try:
                    api_set_state("status_text", text)
                    api_set_state("status_color", color)
                except Exception:
                    pass
            def close(self):
                print(Fore.RED + "[SYSTEM] Shutdown requested")
                os._exit(0)

        app_ui = DummyUI()
        logic_thread = threading.Thread(target=seven_logic, daemon=True)
        logic_thread.start()

        print(Fore.GREEN + "[SYSTEM] Backend running. Open http://localhost:5173 in browser.")

        # Battery monitor - speaks AND shows notification
        def _battery_monitor():
            import time as _bt
            _alerted_20 = False
            _alerted_10 = False
            while True:
                try:
                    _bt.sleep(300)
                    import psutil
                    bat = psutil.sensors_battery()
                    if bat is None:
                        continue
                    if bat.power_plugged:
                        _alerted_20 = False
                        _alerted_10 = False
                        continue
                    pct = int(bat.percent)
                    if pct <= 10 and not _alerted_10:
                        msg = f"Battery critically low at {pct} percent. Plug in now."
                        # Speak it
                        try:
                            import mouth as _m
                            _m.speak(msg)
                        except Exception:
                            pass
                        # Also show notification
                        try:
                            from winotify import Notification, audio
                            t = Notification(
                                app_id="Seven AI",
                                title="Seven - Battery Critical",
                                msg=msg,
                                duration="long"
                            )
                            t.set_audio(audio.Default, loop=False)
                            t.show()
                        except Exception:
                            pass
                        _alerted_10 = True
                    elif pct <= 20 and not _alerted_20:
                        msg = f"Heads up. Battery at {pct} percent. Consider plugging in."
                        try:
                            import mouth as _m
                            _m.speak(msg)
                        except Exception:
                            pass
                        try:
                            from winotify import Notification, audio
                            t = Notification(
                                app_id="Seven AI",
                                title="Seven - Battery Low",
                                msg=msg,
                                duration="long"
                            )
                            t.set_audio(audio.Default, loop=False)
                            t.show()
                        except Exception:
                            pass
                        _alerted_20 = True
                except Exception:
                    pass

        _bat_thread = threading.Thread(target=_battery_monitor, daemon=True)
        _bat_thread.start()
        print(Fore.CYAN + "[SYSTEM] Battery monitor active")

        try:
            import time
            while True:
                time.sleep(5)
                if not logic_thread.is_alive():
                    print(Fore.RED + "[WATCHDOG] Voice loop crashed. Restarting...")
                    logic_thread = threading.Thread(target=seven_logic, daemon=True)
                    logic_thread.start()
        except KeyboardInterrupt:
            print(Fore.RED + "\n[SYSTEM] Interrupted by user")
            os._exit(0)


if __name__ == "__main__":
    start_app()