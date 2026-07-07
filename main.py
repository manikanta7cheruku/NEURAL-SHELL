"""
PROJECT SEVEN - main.py (The Controller)
Version: 1.4.0 - Full modular monolith

Voice loop orchestrator.
All heavy lifting delegated to main_modules/.
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# PATH SETUP
# ============================================================================

_app_path = os.environ.get('SEVEN_APP_PATH', '')
if _app_path and _app_path not in sys.path:
    sys.path.insert(0, _app_path)

if _app_path:
    _embedded_python = os.path.join(_app_path, 'python', 'python.exe')
    _embedded_sp     = os.path.join(_app_path, 'python', 'Lib', 'site-packages')
    _embedded_lib    = os.path.join(_app_path, 'python', 'Lib')
    _embedded_dlls   = os.path.join(_app_path, 'python', 'DLLs')

    print(f"[SYSTEM] App path: {_app_path}")
    print(f"[SYSTEM] Site-packages exists: {os.path.exists(_embedded_sp)}")

    _running_embedded = (
        os.path.exists(_embedded_python) and
        os.path.normcase(sys.executable) == os.path.normcase(_embedded_python)
    )

    if not _running_embedded and os.path.exists(_embedded_python):
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

    for _p in [_embedded_sp, _embedded_lib, _embedded_dlls, os.path.join(_app_path, 'python')]:
        if os.path.exists(_p) and _p not in sys.path:
            sys.path.insert(0, _p)

_cwd = os.getcwd()
if _cwd not in sys.path:
    sys.path.insert(0, _cwd)


# ============================================================================
# PACKAGE CHECK
# ============================================================================

def _packages_ready():
    import subprocess
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    embedded_python = os.path.join(app_path, 'python', 'python.exe') if app_path else ''
    if app_path and os.path.exists(embedded_python):
        python = embedded_python
        print(f"[SYSTEM] Checking embedded Python: {embedded_python}")
    else:
        python = sys.executable
        print(f"[SYSTEM] Checking system Python: {python}")
    if app_path:
        sp = os.path.join(app_path, 'python', 'Lib', 'site-packages')
        print(f"[SYSTEM] Site-packages exists: {os.path.exists(sp)}")
    for pkg in ['fastapi', 'uvicorn', 'pyttsx3', 'speech_recognition']:
        result = subprocess.run([python, '-c', f'import {pkg.replace("-","_")}'], capture_output=True)
        if result.returncode != 0:
            print(f"[SYSTEM] Missing package: {pkg}")
            return False
    print("[SYSTEM] Core packages ready.")
    return True


def _detect_electron_mode():
    if os.environ.get('SEVEN_ELECTRON_MODE') == '1':
        return True
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    if app_path:
        if os.path.exists(os.path.join(app_path, 'python', 'python311.dll')):
            return True
        if os.path.exists(os.path.join(app_path, 'python', 'python3.dll')):
            return True
    if 'resources' in sys.executable.replace('\\', '/').lower() and 'app' in sys.executable.replace('\\', '/').lower():
        return True
    try:
        import tkinter as _tk_test
        _tk_test
        return False
    except ImportError:
        print("[SYSTEM] tkinter not available - forcing Electron mode")
        return True


IS_ELECTRON_MODE = _detect_electron_mode()
print(f"[SYSTEM] Electron mode: {IS_ELECTRON_MODE}")

if not _packages_ready():
    print("[SYSTEM] Core packages not installed - starting in pre-setup mode")
    from backend.startup import run_minimal_server
    run_minimal_server(host="127.0.0.1", port=7777)
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        os._exit(0)
    os._exit(0)


# ============================================================================
# FULL STARTUP
# ============================================================================

print("[SYSTEM] Packages ready - starting full Seven...")

import threading
import re

import colorama
from colorama import Fore
colorama.init()

import config
from backend.api_server import start_api_server, set_state as api_set_state
from backend.admin_server import start_admin_server
import telemetry

from main_modules.startup.context             import SevenContext
from main_modules.startup.module_loader       import load_all_modules
from main_modules.startup.morning_brief       import speak_morning_brief
from main_modules.startup.daemon_launcher     import launch_schedule_daemon
from main_modules.startup.battery_monitor     import start_battery_monitor
from main_modules.startup.enrollment_handler  import (
    handle_pending_enrollment,
    handle_voice_enrollment_command,
)
from main_modules.handlers                    import register_all, execute_all
from main_modules.handlers.pre_executor       import pre_execute

app_ui = None


# ============================================================================
# SEVEN LOGIC THREAD
# ============================================================================

def seven_logic():
    global app_ui

    # Build shared context
    ctx = SevenContext()
    ctx.app_ui        = app_ui
    ctx.api_set_state = api_set_state
    ctx.config        = config

    # Load all AI modules onto ctx
    if not load_all_modules(ctx):
        return  # critical load failure

    # Voice loop configuration
    is_active = True
    interrupt_config   = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED  = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS    = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]

    interrupt_context = ctx.interrupt_context

    WAKE_WORDS  = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                   "pause", "stop listening", "sleep", "silence", "stop",
                   "enough", "quiet", "shut up", "be quiet"]
    KILL_WORDS  = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]

    # PTT listener
    _is_ptt_active_fn = lambda: True
    try:
        from ears.push_to_talk import start as _ptt_start, is_ptt_active
        _ptt_start()
        _is_ptt_active_fn = is_ptt_active
        print(Fore.CYAN + "[GATES] PTT keyboard listener started")
    except Exception as _ptt_err:
        print(Fore.YELLOW + f"[GATES] PTT init failed: {_ptt_err}")

    # Speak with interrupt helper
    def speak_with_interrupt(text):
        import time as _time
        if not INTERRUPT_ENABLED or (_time.time() - last_interrupt_time[0] < INTERRUPT_COOLDOWN):
            ctx.mouth.speak(text)
            return True
        stop_listening  = threading.Event()
        was_interrupted = threading.Event()
        def on_interrupt():
            was_interrupted.set()
            ctx.mouth_interrupt()
            last_interrupt_time[0] = _time.time()
        interrupt_thread = threading.Thread(
            target=ctx.listen_for_interrupt,
            args=(INTERRUPT_WORDS, on_interrupt, stop_listening),
            daemon=True
        )
        interrupt_thread.start()
        completed = ctx.mouth.speak(text)
        stop_listening.set()
        interrupt_thread.join(timeout=2)
        if was_interrupted.is_set():
            print("[SYSTEM] Speech interrupted")
            app_ui.update_status("INTERRUPTED", "#ffaa00")
            interrupt_context["was_interrupted"] = True
            interrupt_context["last_response"]   = text
            ctx.mouth.speak("Yeah?")
            return False
        return True

    ctx.speak_with_interrupt = speak_with_interrupt

    # Silence watcher
    _silence_watcher = None
    _last_topic_ref  = [None]
    try:
        from brain_modules.silence_watcher import SilenceWatcher
        _silence_watcher = SilenceWatcher(
            speak_fn=speak_with_interrupt,
            get_last_topic_fn=lambda: _last_topic_ref[0],
        )
        threading.Thread(target=_silence_watcher.start, daemon=True).start()
        ctx.silence_watcher = _silence_watcher
        print(Fore.CYAN + "[SYSTEM] Silence watcher started")
    except Exception as _sw_err:
        print(Fore.YELLOW + f"[SYSTEM] Silence watcher skipped: {_sw_err}")

    # Scheduler
    try:
        from backend.api_server import set_schedule_alert as _alert_fn
        ctx.scheduler_mod.start_background(speak_fn=ctx.mouth.speak, alert_fn=_alert_fn)
        print(Fore.GREEN + "[SYSTEM] Scheduler started with banner support")
    except Exception:
        ctx.scheduler_mod.start_background(speak_fn=ctx.mouth.speak)
        print(Fore.YELLOW + "[SYSTEM] Scheduler started without banner support")

    sched_count = ctx.scheduler_mod.get_active_count()
    if sched_count > 0:
        print(Fore.CYAN + f"[SYSTEM] Scheduler: {sched_count} active schedules.")

    # Morning brief
    speak_morning_brief(ctx, config)

    # Daemon launcher
    launch_schedule_daemon()

    # Register handlers
    try:
        register_all(ctx)
    except Exception as _hr_err:
        print(Fore.RED + f"[HANDLERS] Registration failed: {_hr_err}")
        import traceback; traceback.print_exc()

    app_ui.update_status("SYSTEM ONLINE", "#00ff00")

    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    while True:
        try:
            # Enrollment check
            if handle_pending_enrollment(ctx, api_set_state):
                continue

            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00")
                api_set_state("listening", True)
                api_set_state("thinking",  False)
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555")
                api_set_state("listening", False)

            user_input, audio_path = ctx.listen()
            if not user_input:
                # Battery alert check
                try:
                    from backend.api_server import get_state as _gs
                    if _gs().get("battery_alert_pending"):
                        from backend.api_server import set_state as _ss
                        _bat_msg = _gs().get("battery_alert_msg") or "Battery low. Please plug in."
                        _ss("battery_alert_pending", False)
                        _ss("battery_alert_msg", "")
                        speak_with_interrupt(_bat_msg)
                except Exception:
                    pass
                continue

            # Voice gates
            _vg          = config.KEY.get("voice_gates", {})
            _ptt_enabled = _vg.get("push_to_talk",   {}).get("enabled", False)
            _ww_enabled  = _vg.get("wake_word",      {}).get("enabled", False)
            _ww_words    = _vg.get("wake_word",      {}).get("words", ["hey seven", "ok seven", "seven"])
            _sv_enabled  = _vg.get("speaker_verify", {}).get("enabled", False)

            try:
                from ears.push_to_talk import set_enabled as _ptt_set
                _ptt_set(_ptt_enabled)
            except Exception:
                pass

            if _ptt_enabled and not _is_ptt_active_fn():
                print(Fore.YELLOW + "[GATE1-PTT] Shift not held — audio discarded")
                continue

            if _silence_watcher:
                _silence_watcher.on_user_spoke()
            _last_topic_ref[0] = user_input

            if _ww_enabled:
                try:
                    from ears.wake_word import check_and_strip as _ww_check
                    user_input, _ww_found = _ww_check(user_input, _ww_words)
                    if not _ww_found:
                        print(Fore.YELLOW + f"[GATE2-WW] No wake word — discarded")
                        continue
                except Exception as _ww_err:
                    print(Fore.YELLOW + f"[GATE2-WW] Error: {_ww_err}")

            text_lower = user_input.lower().strip()

            _hallucinations = {
                "thank you", "thanks", "thank you.", "thanks.",
                "you", "the", "bye", "bye.", "yes", "no",
                "thanks for watching", "thank you for watching",
                ".", "..", "...", " ", ""
            }
            if text_lower in _hallucinations or len(text_lower) < 2:
                print(Fore.YELLOW + f"[EARS] Filtered: '{user_input}'")
                continue

            # Interrupt resume
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
                        response = ctx.brain.think(resume_prompt, speaker_id="default")
                        if response:
                            speak_with_interrupt(response)
                        else:
                            ctx.mouth.speak("Sorry, lost my train of thought.")
                    else:
                        ctx.mouth.speak("Sorry, lost my train of thought. Ask me again?")
                else:
                    interrupt_context.update({"was_interrupted": False, "last_response": None, "last_input": None})
                continue

            # Speaker ID
            speaker_id = "default"
            if audio_path and ctx.is_voice_id_enabled():
                speaker_id = ctx.identify_speaker(audio_path)
                print(Fore.CYAN + f"[VOICE ID] Speaker: {speaker_id}")
                api_set_state("current_speaker", speaker_id)

            if _sv_enabled and ctx.is_voice_id_enabled() and speaker_id == "unknown":
                print(Fore.YELLOW + "[GATE3-SV] Unknown speaker — audio discarded")
                continue

            # Voice enrollment trigger
            if "enroll my voice" in text_lower or "enroll voice" in text_lower:
                handle_voice_enrollment_command(ctx, api_set_state)
                continue

            # Kill / wake / pause
            if any(trigger in text_lower for trigger in KILL_WORDS):
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                ctx.mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            if any(trigger in text_lower for trigger in WAKE_WORDS):
                if not is_active:
                    is_active = True
                    ctx.mouth.speak("Listening.")
                    app_ui.update_status("RESUMED", "#00ff00")
                    if _silence_watcher:
                        _silence_watcher.set_paused(False)
                continue

            if is_active and any(trigger in text_lower for trigger in PAUSE_WORDS):
                is_active = False
                ctx.mouth.speak("Standing by.")
                app_ui.update_status("PAUSED", "#555555")
                if _silence_watcher:
                    _silence_watcher.set_paused(True)
                api_set_state("user_text",  "")
                api_set_state("seven_text", "")
                continue

            if not is_active:
                continue

            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status("THINKING...", "#ff00ff")
            api_set_state("thinking",  True)
            api_set_state("listening", False)
            api_set_state("user_text", user_input)
            api_set_state("seven_text", "")

            # Facts limit check
            if any(t in user_input.lower() for t in [
                "remember that", "remember this", "my name is", "call me",
                "i love", "i like", "i prefer", "i am a",
                "i work at", "i study at", "my favorite", "my favourite"
            ]):
                try:
                    import voice_limits
                    if ctx.seven_memory:
                        _current_facts = ctx.seven_memory.user_facts.count()
                        _fact_ok, _fact_msg = voice_limits.check("facts_limit", _current_facts)
                        if not _fact_ok:
                            api_set_state("speaking", True)
                            ctx.mouth.speak(_fact_msg)
                            api_set_state("speaking", False)
                            app_ui.update_status("PLAN LIMIT", "#ffaa00")
                            continue
                except Exception:
                    pass

            # Web search hint
            _web_needed = any(w in user_input.lower() for w in [
                "weather", "news", "price", "score", "latest",
                "what is", "who is", "when did", "how much",
                "tell me about", "explain", "define",
            ])
            _is_convo = any(w in user_input.lower() for w in [
                "yourself", "you are", "about you", "who are you",
                "what are you", "place", "feel", "think",
            ])
            if _web_needed and not _is_convo and len(user_input.split()) > 5:
                import random as _rand
                ctx.mouth.speak(_rand.choice(["One moment.", "Let me check.", "Checking."]))

            # Brain response
            response = ctx.brain.think(user_input, speaker_id=speaker_id)
            telemetry.log_activity()

            if response == "":
                continue
            if not response:
                response = "Processing error."

            is_streaming = (
                isinstance(response, tuple) and
                len(response) == 2 and
                response[0] == "__STREAM__"
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

            # Update context for handlers
            ctx.speaker_id  = speaker_id
            ctx.speech_part = speech_part
            ctx.user_input  = user_input

            # Pre-execute
            if isinstance(response, str):
                try:
                    pre_execute(response, ctx)
                except Exception as _pe_err:
                    print(Fore.RED + f"[PRE-EXEC] Error: {_pe_err}")

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
                ctx.speech_part = speech_part
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
            if should_store and isinstance(response, str) and ctx.seven_memory:
                try:
                    import voice_limits
                    current_convos = ctx.seven_memory.conversations.count()
                    allowed, limit_msg = voice_limits.check("conversation_history", current_convos)
                    if allowed:
                        clean_response = re.sub(r'###\w+:\s*\S+', '', response).strip()
                        if not completed and clean_response:
                            clean_response = f"[INTERRUPTED] {clean_response}"
                        if clean_response:
                            _default_uid = config.KEY.get('identity', {}).get('user_name', 'default').lower() or "default"
                            ctx.seven_memory.store_conversation(
                                user_input, clean_response,
                                user_id=speaker_id if speaker_id not in ("default", "unknown") else _default_uid
                            )
                    else:
                        print(Fore.YELLOW + f"[LIMIT] Conversation memory full ({current_convos})")
                except Exception as e:
                    print(Fore.RED + f"[MEMORY ERROR] {e}")

            if not isinstance(response, str):
                continue

            # Dispatch to handlers
            try:
                execute_all(response, ctx)
            except Exception as _hd_err:
                print(Fore.RED + f"[HANDLERS] Dispatch error: {_hd_err}")
                import traceback; traceback.print_exc()

            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        except OSError as e:
            if "Stream closed" in str(e) or "9988" in str(e) or "9999" in str(e):
                print(Fore.YELLOW + f"[EARS] Mic device change detected — recovering")
                import time as _rec_t
                _rec_t.sleep(1.5)
                try:
                    from ears.core import _do_initial_calibration
                    _do_initial_calibration()
                except Exception:
                    pass
            else:
                print(Fore.RED + f"[CRITICAL ERROR] Main loop: {e}")
                import traceback; traceback.print_exc()
            app_ui.update_status("LISTENING...", "#00ff00")
        except Exception as e:
            print(Fore.RED + f"[CRITICAL ERROR] Main loop: {e}")
            import traceback; traceback.print_exc()
            app_ui.update_status("ERROR RECOVERED", "#ff0000")


# ============================================================================
# START APP
# ============================================================================

def start_app():
    global app_ui

    is_electron = IS_ELECTRON_MODE

    if is_electron:
        print(Fore.CYAN + "[SYSTEM] Running in ELECTRON mode")
    else:
        print(Fore.YELLOW + "[SYSTEM] Running in STANDALONE mode")

    start_api_server(host="127.0.0.1", port=7777)
    print(Fore.GREEN + "[SYSTEM] API server up")

    try:
        telemetry.start_telemetry()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Telemetry skipped: {e}")

    try:
        start_admin_server()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Admin server skipped: {e}")

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

    if is_electron:
        print(Fore.GREEN + "[SYSTEM] Backend running. Electron handles UI.")
    else:
        print(Fore.GREEN + "[SYSTEM] Backend running. Open http://localhost:5173 in browser.")

    start_battery_monitor()

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