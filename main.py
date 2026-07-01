"""
PROJECT SEVEN - main.py (The Controller)
Version: 1.2.8
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
import random

import colorama
from colorama import Fore
colorama.init()

import config
from backend.api_server import start_api_server, set_state as api_set_state
from backend.admin_server import start_admin_server
import telemetry

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
        print("[SYSTEM] Ears loaded")
    except Exception as e:
        print(f"[SYSTEM] Ears failed: {e}")
        import traceback; traceback.print_exc()
        app_ui.update_status("EARS ERROR", "#ff0000")
        return

    try:
        import brain
        import brain_manager
        print("[SYSTEM] Brain loaded")
    except Exception as e:
        print(f"[SYSTEM] Brain failed: {e}")
        import traceback; traceback.print_exc()
        app_ui.update_status("BRAIN ERROR", "#ff0000")
        return

    try:
        import hands.core as core
        import hands.system as system_mod
        import hands.scheduler as scheduler_mod
        import hands.windows as hands_windows
        print("[SYSTEM] Hands loaded")
    except Exception as e:
        print(f"[SYSTEM] Hands failed: {e}")
        import traceback; traceback.print_exc()

    print(Fore.CYAN + "[SYSTEM] Loading mouth...")

    try:
        import pythoncom
        pythoncom.CoInitialize()
        print(Fore.CYAN + "[SYSTEM] COM initialized")
    except Exception as _com_err:
        print(Fore.YELLOW + f"[SYSTEM] COM init skipped: {_com_err}")

    mouth = None
    mouth_interrupt = None
    is_speaking = None
    try:
        import sys as _sys
        for _k in list(_sys.modules.keys()):
            if 'mouth' in _k.lower() or 'pyttsx' in _k.lower():
                del _sys.modules[_k]
        import mouth as _mouth_mod
        mouth = _mouth_mod
        from mouth import interrupt as mouth_interrupt, is_speaking
        print(Fore.GREEN + "[SYSTEM] Mouth loaded")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Mouth failed: {e}")
        import traceback; traceback.print_exc()
        class _FallbackMouth:
            def speak(self, text): print(f"[MOUTH FALLBACK] {text}")
            def interrupt(self): pass
            def is_speaking(self): return False
        mouth = _FallbackMouth()
        mouth_interrupt = mouth.interrupt
        is_speaking = mouth.is_speaking
        print(Fore.YELLOW + "[SYSTEM] Using fallback mouth")

    seven_memory = None
    mood_engine  = None
    command_log  = None
    try:
        print(Fore.CYAN + "[SYSTEM] Loading memory...")
        from memory import seven_memory as _sm
        from memory.mood import mood_engine as _me
        from memory.command_log import command_log as _cl
        seven_memory = _sm
        mood_engine  = _me
        command_log  = _cl
        _ = seven_memory.get_stats()
        print(Fore.GREEN + "[SYSTEM] Memory loaded")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Memory failed: {e}")
        import traceback; traceback.print_exc()

    print(Fore.GREEN + "[SYSTEM] AI modules loaded.")

    is_active = True
    interrupt_config   = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED  = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS    = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]

    interrupt_context = {
        "last_response":   None,
        "last_input":      None,
        "was_interrupted": False
    }

    WAKE_WORDS  = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                   "pause", "stop listening", "sleep", "silence", "stop",
                   "enough", "quiet", "shut up", "be quiet"]
    KILL_WORDS  = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]

    # Start PTT keyboard listener once — runs for entire session
    _is_ptt_active_fn = lambda: True
    try:
        from ears.push_to_talk import start as _ptt_start, set_enabled as _ptt_set, is_ptt_active
        _ptt_start()
        _is_ptt_active_fn = is_ptt_active
        print(Fore.CYAN + "[GATES] PTT keyboard listener started")
    except Exception as _ptt_err:
        print(Fore.YELLOW + f"[GATES] PTT init failed: {_ptt_err}")

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
            print("[SYSTEM] Speech interrupted")
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
        from brain_modules.silence_watcher import SilenceWatcher
        _silence_watcher = SilenceWatcher(
            speak_fn=speak_with_interrupt,
            get_last_topic_fn=lambda: _last_topic_ref[0],
        )
        threading.Thread(target=_silence_watcher.start, daemon=True).start()
        print(Fore.CYAN + "[SYSTEM] Silence watcher started")
    except Exception as _sw_err:
        print(Fore.YELLOW + f"[SYSTEM] Silence watcher skipped: {_sw_err}")

    # Startup stats
    try:
        if seven_memory:
            stats = seven_memory.get_stats()
            print(Fore.GREEN + f"[SYSTEM] Memory: {stats['total_conversations']} conversations, {stats['total_facts']} facts")
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

    # Greeting
    try:
        print(Fore.GREEN + "[SYSTEM] Speaking startup greeting...")
        mouth.speak(f"{config.KEY['identity']['name']} online.")
        print(Fore.GREEN + "[SYSTEM] Greeting spoken")
    except Exception as _greet_err:
        print(Fore.RED + f"[SYSTEM] Greeting failed: {_greet_err}")
        import traceback; traceback.print_exc()

    # Scheduler
    try:
        from backend.api_server import set_schedule_alert as _alert_fn
        scheduler_mod.start_background(speak_fn=mouth.speak, alert_fn=_alert_fn)
        print(Fore.GREEN + "[SYSTEM] Scheduler started with banner support")
    except Exception:
        scheduler_mod.start_background(speak_fn=mouth.speak)
        print(Fore.YELLOW + "[SYSTEM] Scheduler started without banner support")

    sched_count = scheduler_mod.get_active_count()
    if sched_count > 0:
        print(Fore.CYAN + f"[SYSTEM] Scheduler: {sched_count} active schedules.")

    # Daemon - check if already running before starting
    # SevenScheduleDaemon in schtasks handles login startup
    # We only start one here if none is running
    try:
        import subprocess as _sp
        import os as _os

        _daemon  = _os.path.join(_os.getcwd(), "schedule_daemon.py")
        _python  = sys.executable
        _pythonw = _python.replace("python.exe", "pythonw.exe")
        if not _os.path.exists(_pythonw):
            _pythonw = _python

        # Count running daemon instances
        _daemon_count = 0
        try:
            import psutil as _psu
            for _proc in _psu.process_iter(['pid', 'cmdline']):
                try:
                    _cmd = " ".join(_proc.info['cmdline'] or [])
                    if "schedule_daemon" in _cmd:
                        _daemon_count += 1
                except Exception:
                    pass
        except Exception:
            pass

        if _daemon_count == 0 and _os.path.exists(_daemon):
            _CREATE_NO_WINDOW = 0x08000000
            _DETACHED_PROCESS = 0x00000008
            _sp.Popen(
                [_pythonw, _daemon],
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                stdin=_sp.DEVNULL,
                creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS
            )
            print(Fore.CYAN + "[SYSTEM] Schedule daemon started (hidden)")
        elif _daemon_count > 0:
            print(Fore.CYAN + f"[SYSTEM] Daemon already running ({_daemon_count} instance). Skipping.")

    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Daemon skipped: {_de}")

    app_ui.update_status("SYSTEM ONLINE", "#00ff00")

    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    while True:
        try:
            # ── Check pending voice enrollment BEFORE listen() ────────
            # Must be here — enrollment needs to intercept the listen() cycle
            try:
                from backend.api_server import get_state as _gs, set_state as _ss
                _pending_name = _gs("pending_enrollment")
                if _pending_name:
                    _ss("pending_enrollment", None)  # clear immediately
                    mouth.speak(f"Ready. Speak now, {_pending_name}. Say a few sentences.")
                    app_ui.update_status(f"ENROLLING {_pending_name}...", "#ff00ff")
                    api_set_state("listening", False)
                    api_set_state("thinking",  True)

                    import wave as _wave, shutil as _shutil

                    _clips = []
                    for _i in range(3):
                        app_ui.update_status(
                            f"ENROLLING {_pending_name} — clip {_i+1}/3...", "#ff00ff"
                        )
                        _, _clip = listen()
                        if _clip and os.path.exists(_clip):
                            _clips.append(_clip)
                            print(Fore.CYAN + f"[ENROLL] Clip {_i+1} captured: {_clip}")
                        else:
                            print(Fore.YELLOW + f"[ENROLL] Clip {_i+1} empty — skipping")

                    _ok = False
                    if _clips:
                        _merged = os.path.join(
                            os.environ.get('APPDATA', ''), 'SEVEN', 'enroll_merge.wav'
                        )
                        try:
                            _all_frames, _wp = [], None
                            for _cp in _clips:
                                with _wave.open(_cp, 'rb') as _wf:
                                    if _wp is None:
                                        _wp = _wf.getparams()
                                    _all_frames.append(_wf.readframes(_wf.getnframes()))
                            if _wp and _all_frames:
                                with _wave.open(_merged, 'wb') as _out:
                                    _out.setparams(_wp)
                                    for _f in _all_frames:
                                        _out.writeframes(_f)
                                # Save first clip as playback sample
                                _sample_dir = os.path.join(os.getcwd(), 'seven_data', 'voice_prints')
                                os.makedirs(_sample_dir, exist_ok=True)
                                _shutil.copy(_clips[0], os.path.join(
                                    _sample_dir, f"{_pending_name.lower()}_sample.wav"
                                ))
                                _ok = enroll_speaker(_pending_name, _merged)
                                try:
                                    os.remove(_merged)
                                except Exception:
                                    pass
                        except Exception as _me:
                            print(Fore.RED + f"[ENROLL] Merge error: {_me}")
                            _ok = enroll_speaker(_pending_name, _clips[0])

                    _ss("enrollment_done", {
                        "name":    _pending_name,
                        "success": _ok,
                        "message": (
                            f"Voice enrolled for {_pending_name}."
                            if _ok else
                            "Enrollment failed. No clear audio captured."
                        )
                    })
                    mouth.speak(
                        f"Done. I will recognize {_pending_name} from now on."
                        if _ok else
                        "Enrollment failed. Try speaking more clearly."
                    )
                    app_ui.update_status("SYSTEM ONLINE", "#00ff00")
                    api_set_state("thinking", False)
                    continue   # Skip normal listen() this iteration
            except Exception as _enroll_err:
                print(Fore.YELLOW + f"[ENROLL] Error: {_enroll_err}")
                import traceback; traceback.print_exc()

            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00")
                api_set_state("listening", True)
                api_set_state("thinking",  False)
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555")
                api_set_state("listening", False)

            user_input, audio_path = listen()
            if not user_input:
                # Check for pending battery alert
                try:
                    from backend.api_server import get_state as _gs
                    if _gs("battery_alert_pending"):
                        from backend.api_server import set_state as _ss
                        _bat_msg = _gs("battery_alert_msg") or "Battery low. Please plug in."
                        _ss("battery_alert_pending", False)
                        _ss("battery_alert_msg", "")
                        speak_with_interrupt(_bat_msg)
                except Exception:
                    pass
                continue

            # ── Read gates fresh every loop — config can change from Settings UI
            _vg          = config.KEY.get("voice_gates", {})
            _ptt_enabled = _vg.get("push_to_talk",   {}).get("enabled", False)
            _ww_enabled  = _vg.get("wake_word",      {}).get("enabled", False)
            _ww_words    = _vg.get("wake_word",      {}).get("words", ["hey seven", "ok seven", "seven"])
            _sv_enabled  = _vg.get("speaker_verify", {}).get("enabled", False)

            # Sync PTT enabled state to keyboard listener
            try:
                from ears.push_to_talk import set_enabled as _ptt_set
                _ptt_set(_ptt_enabled)
            except Exception:
                pass

            # ── Gate 1: Push to Talk ──────────────────────────────────
            if _ptt_enabled and not _is_ptt_active_fn():
                print(Fore.YELLOW + "[GATE1-PTT] Shift not held — audio discarded")
                continue

            if _silence_watcher:
                _silence_watcher.on_user_spoke()
            _last_topic_ref[0] = user_input

            # ── Gate 2: Wake Word ─────────────────────────────────────
            if _ww_enabled:
                try:
                    from ears.wake_word import check_and_strip as _ww_check
                    user_input, _ww_found = _ww_check(user_input, _ww_words)
                    if not _ww_found:
                        print(Fore.YELLOW + f"[GATE2-WW] No wake word — discarded: '{user_input[:40]}'")
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

            speaker_id = "default"
            if audio_path and is_voice_id_enabled():
                speaker_id = identify_speaker(audio_path)
                print(Fore.CYAN + f"[VOICE ID] Speaker: {speaker_id}")
                api_set_state("current_speaker", speaker_id)

            # ── Gate 3: Speaker Verification ──────────────────────────
            if _sv_enabled and is_voice_id_enabled() and speaker_id == "unknown":
                print(Fore.YELLOW + "[GATE3-SV] Unknown speaker — audio discarded")
                continue

            if "enroll my voice" in text_lower or "enroll voice" in text_lower:
                mouth.speak("What name should I save this voice as?")
                app_ui.update_status("ENROLLING — Say your name...", "#ff00ff")
                name_input, _ = listen()
                if not name_input:
                    mouth.speak("I did not catch your name. Try again.")
                    continue

                enroll_name = name_input.strip().replace(".", "").replace("!", "").strip()
                if len(enroll_name) < 2:
                    mouth.speak("Name too short. Try again.")
                    continue

                # Collect 3 clips for better voice coverage
                mouth.speak(f"Got it, {enroll_name}. Now speak for about 10 seconds. Say anything — a few sentences work best.")
                app_ui.update_status(f"ENROLLING {enroll_name} — Speak now...", "#ff00ff")

                import tempfile, wave as _wave, numpy as _np

                collected_audio = []
                for clip_num in range(3):
                    if clip_num > 0:
                        app_ui.update_status(f"ENROLLING — Keep speaking... ({clip_num+1}/3)", "#ff00ff")
                    _, clip_path = listen()
                    if clip_path and os.path.exists(clip_path):
                        collected_audio.append(clip_path)

                if not collected_audio:
                    mouth.speak("Did not capture any audio. Try again.")
                    continue

                # Merge audio clips into one file for better embedding
                try:
                    merged_path = os.path.join(
                        os.environ.get('APPDATA', ''), 'SEVEN', 'enroll_temp.wav'
                    )
                    frames = []
                    params = None
                    for path in collected_audio:
                        try:
                            with _wave.open(path, 'rb') as wf:
                                if params is None:
                                    params = wf.getparams()
                                frames.append(wf.readframes(wf.getnframes()))
                        except Exception:
                            pass

                    if frames and params:
                        with _wave.open(merged_path, 'wb') as out:
                            out.setparams(params)
                            for f in frames:
                                out.writeframes(f)
                        success = enroll_speaker(enroll_name, merged_path)
                        try:
                            os.remove(merged_path)
                        except Exception:
                            pass
                    else:
                        success = enroll_speaker(enroll_name, collected_audio[0])

                except Exception as _enroll_err:
                    print(Fore.RED + f"[ENROLL] Merge failed: {_enroll_err}")
                    success = enroll_speaker(enroll_name, collected_audio[0])

                if success:
                    mouth.speak(f"Voice enrolled. I will recognize {enroll_name} from now on.")
                    # Push enrolled status to frontend
                    try:
                        api_set_state("enrollment_updated", True)
                    except Exception:
                        pass
                else:
                    mouth.speak("Enrollment failed. Try again with clearer audio.")
                continue

            if any(trigger in text_lower for trigger in KILL_WORDS):
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            if any(trigger in text_lower for trigger in WAKE_WORDS):
                if not is_active:
                    is_active = True
                    mouth.speak("Listening.")
                    app_ui.update_status("RESUMED", "#00ff00")
                    if _silence_watcher:
                        _silence_watcher.set_paused(False)
                continue

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

            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status("THINKING...", "#ff00ff")
            api_set_state("thinking",  True)
            api_set_state("listening", False)
            api_set_state("user_text", user_input)
            api_set_state("seven_text", "")

            if any(t in user_input.lower() for t in [
                "remember that", "remember this", "my name is", "call me",
                "i love", "i like", "i prefer", "i am a",
                "i work at", "i study at", "my favorite", "my favourite"
            ]):
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

            # For questions going to LLM — say "just a moment" naturally
            # Only say "one moment" for web searches and long factual questions
            # Not for conversation or capability questions
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
                _thinking_phrases = [
                    "One moment.",
                    "Let me check.",
                    "Checking.",
                ]
                mouth.speak(_rand.choice(_thinking_phrases))

            response = brain.think(user_input, speaker_id=speaker_id)
            telemetry.log_activity()

            if response == "":
                # Empty string = intentional silence (acknowledgement filtered)
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

            # Pre-execute SYS commands before speaking
            # Mark as pre-executed so main handler skips them
                       # Pre-execute OPEN and CLOSE commands before speaking
            _pre_executed_sys  = False
            _pre_executed_open = False
            if isinstance(response, str) and "###SYS:" in response:
                import re as _re_presys
                _pre_sys = _re_presys.findall(r"###SYS:\s*(.*?)(?=###|$)", response)
                for _ps in _pre_sys:
                    _ps_params = {}
                    for _pair in _ps.strip().split():
                        if "=" in _pair:
                            _k, _v = _pair.split("=", 1)
                            _ps_params[_k] = _v
                    if _ps_params:
                        try:
                            system_mod.manage_system(_ps_params)
                            _pre_executed_sys = True
                        except Exception as _pre_err:
                            print(f"[PRE-EXEC] SYS error: {_pre_err}")

            # Pre-execute OPEN and CLOSE commands before speaking
            # User hears confirmation while app is already launching
            if isinstance(response, str) and "###OPEN:" in response:
                import re as _re_preopen
                _pre_opens = _re_preopen.findall(r"###OPEN:\s*(.*?)(?=###|$)", response)
                for _app in _pre_opens:
                    _app = _app.strip().replace('"','').replace("'","")
                    if _app:
                        threading.Thread(
                            target=core.open_app,
                            args=(_app,),
                            daemon=True
                        ).start()
                        _pre_executed_open = True

            _pre_executed_close = False
            if isinstance(response, str) and "###CLOSE:" in response:
                import re as _re_preclose
                _pre_closes = _re_preclose.findall(r"###CLOSE:\s*(.*?)(?=###|$)", response)
                for _app in _pre_closes:
                    _app = _app.strip().replace('"','').replace("'","")
                    if _app:
                        threading.Thread(
                            target=core.close_app,
                            args=(_app,),
                            daemon=True
                        ).start()
                        _pre_executed_close = True

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
                            _default_uid = config.KEY.get('identity', {}).get('user_name', 'default').lower() or "default"
                            seven_memory.store_conversation(
                                user_input, clean_response,
                                user_id=speaker_id if speaker_id not in ("default", "unknown") else _default_uid
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
                            if params.get("action") == "list" and msg and not speech_part:
                                speak_with_interrupt(msg)
                        else:
                            if not speech_part:
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
                        # Only speak scheduler confirmation if brain gave no speech part
                        # brain already said "On it." or "Locked in." before the tag
                        if msg and not speech_part and any(x in msg for x in [
                            "AM", "PM", "today", "tomorrow", "minutes", "seconds",
                            "hours", "Monday", "Tuesday", "Wednesday", "Thursday",
                            "Friday", "Saturday", "Sunday"
                        ]):
                            speak_with_interrupt(msg)
                    else:
                        mouth.speak(msg)
                        app_ui.update_status(f"Schedule failed: {msg}", "#ff0000")

            # System commands — skip if already pre-executed before speaking
            if _pre_executed_sys:
                sys_cmds = []
            else:
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

            # App commands — skip if already pre-executed
            if _pre_executed_open and _pre_executed_close:
                commands = re.findall(r"###(SEARCH):\s*(.*?)(?=###|$)", response)
            elif _pre_executed_open:
                commands = re.findall(r"###(CLOSE|SEARCH):\s*(.*?)(?=###|$)", response)
            elif _pre_executed_close:
                commands = re.findall(r"###(OPEN|SEARCH):\s*(.*?)(?=###|$)", response)
            else:
                commands = re.findall(r"###(OPEN|CLOSE|SEARCH):\s*(.*?)(?=###|$)", response)
            for cmd_type, arg in commands:
                clean_arg = arg.replace('"','').replace("'","").replace(".","").strip()
                if not clean_arg:
                    continue

                # Normalize separators
                _normalized = clean_arg.replace(" and ", ",").replace(" & ", ",")
                sub_apps = [a.strip() for a in _normalized.split(",") if a.strip()]
                if not sub_apps:
                    sub_apps = [clean_arg]

                if cmd_type == "OPEN":
                    if len(sub_apps) > 1:
                        def _open_one(name):
                            if not name:
                                return
                            core.open_app(name)
                            telemetry.log_activity()
                        _threads = []
                        for _app in sub_apps:
                            _t = threading.Thread(target=_open_one, args=(_app.strip(),), daemon=True)
                            _t.start()
                            _threads.append(_t)
                        for _t in _threads:
                            _t.join(timeout=5)
                        app_ui.update_status(f"Opened {len(sub_apps)} apps", "#00ff00")
                    else:
                        app_name = sub_apps[0]
                        app_ui.update_status(f"Opening: {app_name}", "#00ff00")
                        telemetry.log_activity()

                elif cmd_type == "CLOSE":
                    for app_name in sub_apps:
                        app_name = app_name.strip()
                        if not app_name:
                            continue
                        # Skip if app_name looks like leftover garbage
                        # (brain validation should have caught this already)
                        _skip_words = {"me", "it", "this", "that", "the", "a", "an"}
                        if app_name.lower() in _skip_words:
                            continue
                        app_ui.update_status(f"Closing: {app_name}", "#ff0000")

                        def _close_and_report(name):
                            success = core.close_app(name)
                            if not success:
                                # App was not found running — tell user
                                try:
                                    mouth.speak(f"{name} is not running.")
                                except Exception:
                                    pass

                        threading.Thread(
                            target=_close_and_report,
                            args=(app_name,),
                            daemon=True
                        ).start()
                        telemetry.log_activity()

                elif cmd_type == "SEARCH":
                    for app_name in sub_apps:
                        app_name = app_name.strip()
                        if app_name:
                            app_ui.update_status(f"Searching: {app_name}", "#0000ff")
                            core.search_web(app_name)

            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

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

    # Battery monitor
    def _battery_monitor():
        import time as _bt
        _alerted_30 = False
        _alerted_20 = False
        _alerted_10 = False
        _alerted_5  = False
        while True:
            try:
                _bt.sleep(300)
                import psutil
                bat = psutil.sensors_battery()
                if bat is None:
                    continue
                if bat.power_plugged:
                    _alerted_30 = _alerted_20 = _alerted_10 = _alerted_5 = False
                    continue
                pct = int(bat.percent)

                def _alert(msg, title):
                    try:
                        import mouth as _m
                        _m.speak(msg)
                    except Exception:
                        pass
                    try:
                        from winotify import Notification, audio
                        t = Notification(app_id="Seven AI", title=title, msg=msg, duration="long")
                        t.set_audio(audio.Default, loop=False)
                        t.show()
                    except Exception:
                        pass

                if pct <= 5 and not _alerted_5:
                    _alert(f"Battery at {pct} percent. Shutting down soon. Plug in immediately.", "Seven - BATTERY CRITICAL")
                    _alerted_5 = True
                elif pct <= 10 and not _alerted_10:
                    _alert(f"Battery at {pct} percent. Getting critical. Plug in now.", "Seven - Battery Critical")
                    _alerted_10 = True
                elif pct <= 20 and not _alerted_20:
                    _alert(f"Battery at {pct} percent. Should plug in soon.", "Seven - Battery Low")
                    _alerted_20 = True
                elif pct <= 30 and not _alerted_30:
                    _alert(f"Battery at {pct} percent. Just a heads up.", "Seven - Battery Notice")
                    _alerted_30 = True
            except Exception:
                pass

    threading.Thread(target=_battery_monitor, daemon=True).start()
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