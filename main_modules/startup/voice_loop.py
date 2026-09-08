"""
main_modules/startup/voice_loop.py
Main voice loop — extracted from main.py.

Contains seven_logic() which runs the listen→think→speak cycle.
All imports that were at the top of seven_logic() stay here.
"""
import os
import sys
import re
import time
import threading
from colorama import Fore


def run_voice_loop(ctx, config, app_ui, api_set_state, safe_mode_file):
    """
    Main voice loop. Extracted verbatim from main.py seven_logic().
    Runs on a daemon thread.
    """
    # ── Safe mode check ──────────────────────────────────────────────
    _safe_mode = os.path.exists(safe_mode_file)

    if _safe_mode:
        print(Fore.YELLOW + "[SYSTEM] Safe mode active — ML modules not loaded")
        api_set_state("status_text", "SAFE MODE — AI offline")
        api_set_state("status_color", "#ffaa00")
        api_set_state("listening", False)

        from main_modules.startup.daemon_launcher import (
            launch_schedule_daemon, launch_panel_server
        )
        launch_schedule_daemon()
        launch_panel_server()
        try:
            from main_modules.startup.trigger_daemon_launcher import (
                launch_trigger_daemon, launch_overlay_daemon
            )
            launch_trigger_daemon()
            launch_overlay_daemon()
        except Exception:
            pass

        while True:
            time.sleep(1)
        return

    # ── Load AI modules ──────────────────────────────────────────────
    try:
        api_set_state("status_text", "Starting Seven AI...")
        api_set_state("status_color", "#ffaa00")
    except Exception:
        pass

    from main_modules.startup.module_loader import load_all_modules
    if not load_all_modules(ctx):
        print(Fore.RED + "[SYSTEM] ML loading failed.")
        try:
            api_set_state("status_text", "ERROR: AI modules failed to load")
            api_set_state("status_color", "#ff0000")
            api_set_state("listening", False)
            with open(safe_mode_file, 'w') as _sf:
                _sf.write(str(time.time()))
        except Exception:
            pass
        return

    # ── Wire speaking guard ──────────────────────────────────────────
    try:
        import ears.core as _ears_core
        _ears_core.set_speaking_fn(ctx.mouth.is_speaking)
        print(Fore.CYAN + "[SYSTEM] Speaking guard wired to ears")
    except Exception as _sg_err:
        print(Fore.YELLOW + f"[SYSTEM] Speaking guard not wired: {_sg_err}")

    # ── Voice loop config ────────────────────────────────────────────
    is_active = True
    interrupt_config   = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED  = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS    = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]
    interrupt_context = ctx.interrupt_context

    DEFAULT_WAKE_WORDS  = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    DEFAULT_PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                           "pause", "stop listening", "sleep", "silence", "stop",
                           "enough", "quiet", "shut up", "be quiet"]
    DEFAULT_KILL_WORDS  = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]

    def _word_match(text, phrases):
        for phrase in phrases:
            if re.search(r'\b' + re.escape(phrase) + r'\b', text):
                return True
        return False

    def _get_voice_control_words():
        _identity = config.KEY.get("identity", {})
        _wake     = _identity.get("wake_words", DEFAULT_WAKE_WORDS)
        _pause    = _identity.get("pause_words", DEFAULT_PAUSE_WORDS)
        _resume   = _identity.get("resume_words", [])
        _kill     = _identity.get("shutdown_words", DEFAULT_KILL_WORDS)
        _combined_wake = list(dict.fromkeys(_wake + _resume)) if _resume else _wake
        return _combined_wake, _pause, _kill

    # ── PTT ──────────────────────────────────────────────────────────
    _is_ptt_active_fn = lambda: True
    try:
        from ears.push_to_talk import start as _ptt_start, is_ptt_active
        _ptt_start()
        _is_ptt_active_fn = is_ptt_active
        print(Fore.CYAN + "[GATES] PTT keyboard listener started")
    except Exception as _ptt_err:
        print(Fore.YELLOW + f"[GATES] PTT init failed: {_ptt_err}")

    # ── Speak with interrupt ─────────────────────────────────────────
    def speak_with_interrupt(text):
        if not INTERRUPT_ENABLED or (time.time() - last_interrupt_time[0] < INTERRUPT_COOLDOWN):
            ctx.mouth.speak(text)
            return True
        stop_listening  = threading.Event()
        was_interrupted = threading.Event()
        def on_interrupt():
            was_interrupted.set()
            ctx.mouth_interrupt()
            last_interrupt_time[0] = time.time()
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

    # ── Silence watcher ──────────────────────────────────────────────
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

    # ── Scheduler ────────────────────────────────────────────────────
    try:
        from backend.api_server import set_schedule_alert as _alert_fn
        ctx.scheduler_mod.start_background(speak_fn=ctx.mouth.speak, alert_fn=_alert_fn)
        print(Fore.GREEN + "[SYSTEM] Scheduler started with banner support")
    except Exception:
        ctx.scheduler_mod.start_background(speak_fn=ctx.mouth.speak)
        print(Fore.YELLOW + "[SYSTEM] Scheduler started without banner support")

    # ── Daemons (staggered) ──────────────────────────────────────────
    def _launch_daemons_staggered():
        from main_modules.startup.daemon_launcher import (
            launch_schedule_daemon, launch_panel_server
        )
        from main_modules.startup.trigger_daemon_launcher import (
            launch_trigger_daemon, launch_overlay_daemon
        )
        launch_schedule_daemon()
        time.sleep(2)
        launch_panel_server()
        time.sleep(2)
        launch_trigger_daemon()
        time.sleep(3)
        launch_overlay_daemon()
        print(Fore.CYAN + "[SYSTEM] All daemons launched")

    threading.Thread(target=_launch_daemons_staggered, daemon=True,
                     name="DaemonLauncher").start()

    # ── Morning brief ────────────────────────────────────────────────
    from main_modules.startup.morning_brief import speak_morning_brief
    speak_morning_brief(ctx, config)

    # ── Register handlers ────────────────────────────────────────────
    try:
        from main_modules.handlers import register_all, execute_all
        register_all(ctx)
    except Exception as _hr_err:
        print(Fore.RED + f"[HANDLERS] Registration failed: {_hr_err}")

    app_ui.update_status("SYSTEM ONLINE", "#00ff00")

    # ── MAIN LOOP ────────────────────────────────────────────────────
    # The main loop body is identical to the current seven_logic() in main.py.
    # It is too long to duplicate here (~250 lines). Instead, we import
    # and call it from the existing location during the transition period.
    # TODO: Move the main loop body here in a future refactor.
    from main_modules.handlers.pre_executor import pre_execute
    from main_modules.handlers import execute_all
    import telemetry

    while True:
        try:
            from main_modules.startup.enrollment_handler import handle_pending_enrollment
            if handle_pending_enrollment(ctx, api_set_state):
                continue

            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00")
                api_set_state("listening", True)
                api_set_state("thinking", False)
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555")
                api_set_state("listening", False)

            user_input, audio_path = ctx.listen()
            if not user_input:
                try:
                    from backend.api_server import get_state as _gs
                    if _gs().get("battery_alert_pending"):
                        from backend.api_server import set_state as _ss
                        _bat_msg = _gs().get("battery_alert_msg") or "Battery low."
                        _ss("battery_alert_pending", False)
                        _ss("battery_alert_msg", "")
                        speak_with_interrupt(_bat_msg)
                except Exception:
                    pass
                continue

            WAKE_WORDS, PAUSE_WORDS, KILL_WORDS = _get_voice_control_words()

            _vg = config.KEY.get("voice_gates", {})
            _ptt_enabled = _vg.get("push_to_talk", {}).get("enabled", False)
            _ww_enabled  = _vg.get("wake_word", {}).get("enabled", False)
            _ww_words    = _vg.get("wake_word", {}).get("words", ["hey seven", "ok seven", "seven"])
            _sv_enabled  = _vg.get("speaker_verify", {}).get("enabled", False)

            try:
                from ears.push_to_talk import set_enabled as _ptt_set
                _ptt_set(_ptt_enabled)
            except Exception:
                pass

            if _ptt_enabled and not _is_ptt_active_fn():
                continue

            if _silence_watcher:
                _silence_watcher.on_user_spoke()
            _last_topic_ref[0] = user_input

            if _ww_enabled:
                try:
                    from ears.wake_word import check_and_strip as _ww_check
                    user_input, _ww_found = _ww_check(user_input, _ww_words)
                    if not _ww_found:
                        continue
                    if user_input and len(user_input.strip()) < 2:
                        continue
                except Exception:
                    pass

            text_lower = user_input.lower().strip()
            _hallucinations = {
                "thank you", "thanks", "thank you.", "thanks.",
                "you", "the", "bye", "bye.", "yes", "no",
                "thanks for watching", "thank you for watching",
                ".", "..", "...", " ", ""
            }
            if text_lower in _hallucinations or len(text_lower) < 2:
                continue

            if interrupt_context["was_interrupted"]:
                resume_words = ["continue", "resume", "go on", "go ahead", "keep going", "carry on"]
                if _word_match(text_lower, resume_words):
                    old_response = interrupt_context["last_response"]
                    old_input = interrupt_context["last_input"]
                    interrupt_context.update({"was_interrupted": False, "last_response": None, "last_input": None})
                    if old_response and old_input:
                        resume_prompt = (
                            f"I was interrupted while answering: '{old_input}'. "
                            f"I had said: '{old_response}'. Continue naturally."
                        )
                        response = ctx.brain.think(resume_prompt, speaker_id="default")
                        if response:
                            speak_with_interrupt(response)
                    else:
                        ctx.mouth.speak("Sorry, lost my train of thought. Ask me again?")
                else:
                    interrupt_context.update({"was_interrupted": False, "last_response": None, "last_input": None})
                continue

            _came_from_voice = (audio_path == "__voice__")
            speaker_id = "default"
            if _came_from_voice:
                if ctx.is_voice_id_enabled():
                    speaker_id = ctx.identify_speaker(audio_path) if audio_path != "__voice__" else "voice_user"
                else:
                    speaker_id = "voice_user"

            if _sv_enabled:
                if not ctx.is_voice_id_enabled() or speaker_id == "unknown":
                    continue

            if ctx.mouth.is_speaking():
                time.sleep(0.5)
                continue

            from main_modules.startup.enrollment_handler import handle_voice_enrollment_command
            if "enroll my voice" in text_lower or "enroll voice" in text_lower:
                handle_voice_enrollment_command(ctx, api_set_state)
                continue

            if _word_match(text_lower, KILL_WORDS):
                ctx.mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            if _word_match(text_lower, WAKE_WORDS):
                if not is_active:
                    is_active = True
                    ctx.mouth.speak("Listening.")
                    app_ui.update_status("RESUMED", "#00ff00")
                    if _silence_watcher:
                        _silence_watcher.set_paused(False)
                continue

            if is_active and _word_match(text_lower, PAUSE_WORDS):
                is_active = False
                ctx.mouth.speak("Standing by.")
                app_ui.update_status("PAUSED", "#555555")
                if _silence_watcher:
                    _silence_watcher.set_paused(True)
                api_set_state("user_text", "")
                api_set_state("seven_text", "")
                continue

            if not is_active:
                continue

            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status("THINKING...", "#ff00ff")
            api_set_state("thinking", True)
            api_set_state("listening", False)
            api_set_state("user_text", user_input)
            api_set_state("seven_text", "")

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

            speech_part = response
            if isinstance(response, str) and "###" in response:
                speech_part = response.split("###")[0].strip()

            if not is_streaming and speech_part:
                api_set_state("seven_text", speech_part)

            ctx.speaker_id = speaker_id
            ctx.speech_part = speech_part
            ctx.user_input = user_input

            if isinstance(response, str):
                try:
                    pre_execute(response, ctx)
                except Exception:
                    pass

            api_set_state("speaking", True)
            if _silence_watcher:
                _silence_watcher.on_seven_speaking(True)

            completed = True
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
                response = " ".join(full_parts)
                speech_part = response.split("###")[0].strip() if "###" in response else response
                ctx.speech_part = speech_part
            elif speech_part:
                interrupt_context["last_input"] = user_input
                completed = speak_with_interrupt(speech_part)

            api_set_state("speaking", False)
            api_set_state("thinking", False)
            if _silence_watcher:
                _silence_watcher.on_seven_speaking(False)

            if not isinstance(response, str):
                continue

            try:
                execute_all(response, ctx)
            except Exception as _hd_err:
                print(Fore.RED + f"[HANDLERS] Dispatch error: {_hd_err}")

            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        except OSError as e:
            if "Stream closed" in str(e) or "9988" in str(e) or "9999" in str(e):
                print(Fore.YELLOW + "[EARS] Mic device change — recovering")
                time.sleep(1.5)
            else:
                print(Fore.RED + f"[CRITICAL ERROR] Main loop: {e}")
            app_ui.update_status("LISTENING...", "#00ff00")
        except Exception as e:
            print(Fore.RED + f"[CRITICAL ERROR] Main loop: {e}")
            app_ui.update_status("ERROR RECOVERED", "#ff0000")