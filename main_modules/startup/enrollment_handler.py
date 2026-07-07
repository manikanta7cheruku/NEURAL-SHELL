"""
main_modules/startup/enrollment_handler.py

Voice enrollment flow.
Two entry points:
  handle_pending_enrollment(ctx)   — called each loop iteration
  handle_voice_command_enrollment(ctx, user_input)  — triggered by "enroll my voice"
"""

import os
import wave
import shutil
import random
import time
from colorama import Fore


def handle_pending_enrollment(ctx, api_set_state):
    """
    Check if UI-triggered enrollment is pending.
    If yes, run full 5-clip enrollment flow.
    Returns True if enrollment ran (main loop should skip listen()).
    Returns False otherwise.
    """
    try:
        from backend.api_server import get_state as _gs, set_state as _ss
        _pending_name = _gs().get("pending_enrollment")

        if not _pending_name:
            return False

        _ss("pending_enrollment", None)
        _ss("enrollment_clips_done", 0)
        _ss("enrollment_done", None)
        api_set_state("listening", False)
        api_set_state("thinking",  True)

        try:
            from ears.core import set_force_return as _clr_fr
            _clr_fr(False)
        except Exception:
            pass

        ctx.mouth.speak(f"Ready, {_pending_name}. Five clips.")
        ctx.update_status(f"ENROLLING {_pending_name}...", "#ff00ff")
        time.sleep(0.5)

        _clip_prompts = [
            ["Clip one. Speak."],
            ["Clip two. Speak."],
            ["Clip three. Speak."],
            ["Clip four. Speak."],
            ["Last clip. Speak."],
        ]

        _clips = []
        for _i in range(5):
            ctx.mouth.speak(random.choice(_clip_prompts[_i]))
            ctx.update_status(
                f"ENROLLING — Recording {_i+1}/5... speak now", "#ff00ff"
            )
            print(Fore.CYAN + f"[ENROLL] Waiting for clip {_i+1}/5...")

            _clip = None
            try:
                import speech_recognition as _sr_enroll
                _rec_enroll = _sr_enroll.Recognizer()
                _rec_enroll.energy_threshold = 300
                _rec_enroll.pause_threshold  = 1.0
                with _sr_enroll.Microphone() as _src_enroll:
                    _rec_enroll.adjust_for_ambient_noise(_src_enroll, duration=0.2)
                    print(Fore.CYAN + f"[ENROLL] Listening for clip {_i+1}...")
                    _audio_enroll = _rec_enroll.listen(
                        _src_enroll, timeout=30, phrase_time_limit=10
                    )
                    _clip_path = os.path.join(
                        os.environ.get('APPDATA', ''), 'SEVEN',
                        f'enroll_clip_{_i+1}.wav'
                    )
                    _wav_bytes = _audio_enroll.get_wav_data()
                    with open(_clip_path, 'wb') as _cf:
                        _cf.write(_wav_bytes)
                    _clip = _clip_path
                    print(Fore.GREEN + f"[ENROLL] Clip {_i+1} captured: {len(_wav_bytes)} bytes")
            except _sr_enroll.WaitTimeoutError:
                print(Fore.YELLOW + f"[ENROLL] Clip {_i+1} timeout")
                ctx.mouth.speak("I did not hear anything. Try again.")
            except Exception as _ce:
                print(Fore.RED + f"[ENROLL] Clip {_i+1} error: {_ce}")

            if _clip and os.path.exists(_clip):
                _clips.append(_clip)
                _ss("enrollment_clips_done", len(_clips))
                if _i < 4:
                    ctx.mouth.speak("Got it.")
            else:
                print(Fore.YELLOW + f"[ENROLL] Clip {_i+1} empty")
                ctx.mouth.speak("I did not catch that. Try again — speak clearly.")
                _, _clip = ctx.listen()
                if _clip and os.path.exists(_clip):
                    _clips.append(_clip)
                    _ss("enrollment_clips_done", len(_clips))

        _ok = _merge_and_save_enrollment(_clips, _pending_name, ctx)

        _ss("enrollment_clips_done", 0)
        _ss("enrollment_done", {
            "name": _pending_name,
            "success": _ok,
            "message": (
                f"Voice enrolled for {_pending_name}. Enable Speaker Verification in Voice Security settings to activate it."
                if _ok else
                "Enrollment failed. No clear audio captured. Speak clearly for each clip."
            )
        })

        if _ok:
            ctx.mouth.speak(
                f"Voice enrollment complete for {_pending_name}. "
                f"To activate it, go to Settings, Voice Security, and turn on Speaker Verification."
            )
        else:
            ctx.mouth.speak(
                "Enrollment did not complete. The audio was unclear. Try again."
            )

        ctx.update_status("SYSTEM ONLINE", "#00ff00")
        api_set_state("thinking", False)
        return True

    except Exception as _enroll_err:
        print(Fore.YELLOW + f"[ENROLL] Error: {_enroll_err}")
        import traceback; traceback.print_exc()
        return False


def handle_voice_enrollment_command(ctx, api_set_state):
    """
    Handle "enroll my voice" voice command.
    Prompts for name, records 5 clips, saves voice profile.
    Returns True if handled (main loop should continue).
    """
    ctx.mouth.speak("What name should I save this voice as?")
    ctx.update_status("ENROLLING — Say your name...", "#ff00ff")

    name_input, _ = ctx.listen()
    if not name_input:
        ctx.mouth.speak("I did not catch your name. Try again.")
        return True

    enroll_name = name_input.strip().replace(".", "").replace("!", "").strip()
    if len(enroll_name) < 2:
        ctx.mouth.speak("Name too short. Try again.")
        return True

    ctx.mouth.speak(f"Got it, {enroll_name}. Now speak for about 10 seconds. Say anything — a few sentences work best.")
    ctx.update_status(f"ENROLLING {enroll_name} — Speak now...", "#ff00ff")

    collected_audio = []
    for clip_num in range(5):
        if clip_num > 0:
            ctx.mouth.speak("Got it. Keep going.")
            ctx.update_status(f"ENROLLING — Keep speaking... ({clip_num+1}/5)", "#ff00ff")
        _, clip_path = ctx.listen()
        if clip_path and os.path.exists(clip_path):
            collected_audio.append(clip_path)

    if not collected_audio:
        ctx.mouth.speak("Did not capture any audio. Try again.")
        return True

    success = _merge_and_save_enrollment(collected_audio, enroll_name, ctx)

    if success:
        ctx.mouth.speak(f"Voice enrolled. I will recognize {enroll_name} from now on.")
        try:
            api_set_state("enrollment_updated", True)
        except Exception:
            pass
    else:
        ctx.mouth.speak("Enrollment failed. Try again with clearer audio.")

    return True


def _merge_and_save_enrollment(clips, name, ctx):
    """Merge audio clips and save as voice profile. Returns True on success."""
    if not clips:
        return False

    merged_path = os.path.join(
        os.environ.get('APPDATA', ''), 'SEVEN', 'enroll_merge.wav'
    )

    try:
        _all_frames, _wp = [], None
        for _cp in clips:
            with wave.open(_cp, 'rb') as _wf:
                if _wp is None:
                    _wp = _wf.getparams()
                _all_frames.append(_wf.readframes(_wf.getnframes()))

        if _wp and _all_frames:
            with wave.open(merged_path, 'wb') as _out:
                _out.setparams(_wp)
                for _f in _all_frames:
                    _out.writeframes(_f)

            # Save sample copy
            _sample_dir = os.path.join(os.getcwd(), 'seven_data', 'voice_prints')
            os.makedirs(_sample_dir, exist_ok=True)
            shutil.copy(clips[0], os.path.join(
                _sample_dir, f"{name.lower()}_sample.wav"
            ))

            _ok = ctx.enroll_speaker(name, merged_path)
            try:
                os.remove(merged_path)
            except Exception:
                pass
            return _ok
    except Exception as _me:
        print(Fore.RED + f"[ENROLL] Merge error: {_me}")
        # Fallback: use first clip only
        return ctx.enroll_speaker(name, clips[0])

    return False