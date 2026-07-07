"""
main_modules/startup/module_loader.py

Loads all AI modules Seven needs to run:
  ears, brain, hands, mouth, memory, voice_id.

Returns loaded modules attached to the passed SevenContext.
Fails gracefully with fallback mouth if anything crashes.
"""

import sys
import threading
from colorama import Fore


def load_all_modules(ctx):
    """
    Load every AI module Seven needs and attach to ctx.
    Returns True on success, False if a critical module failed.
    """
    print("[SYSTEM] Loading AI modules...")

    # Ears
    try:
        from ears import listen
        from ears.voice_id import (identify_speaker, enroll_speaker,
                                    is_voice_id_enabled, get_enrolled_speakers)
        from ears.core import listen_for_interrupt

        ctx.listen                = listen
        ctx.identify_speaker      = identify_speaker
        ctx.enroll_speaker        = enroll_speaker
        ctx.is_voice_id_enabled   = is_voice_id_enabled
        ctx.get_enrolled_speakers = get_enrolled_speakers
        ctx.listen_for_interrupt  = listen_for_interrupt
        print("[SYSTEM] Ears loaded")
    except Exception as e:
        print(f"[SYSTEM] Ears failed: {e}")
        import traceback; traceback.print_exc()
        if ctx.app_ui:
            ctx.app_ui.update_status("EARS ERROR", "#ff0000")
        return False

    # Brain
    try:
        import brain
        import brain_manager
        ctx.brain = brain
        print("[SYSTEM] Brain loaded")
    except Exception as e:
        print(f"[SYSTEM] Brain failed: {e}")
        import traceback; traceback.print_exc()
        if ctx.app_ui:
            ctx.app_ui.update_status("BRAIN ERROR", "#ff0000")
        return False

    # TitaNet preload in background
    try:
        from ears.voice_id import _get_model as _preload_titanet

        def _load_titanet_bg():
            _preload_titanet()
            print(Fore.GREEN + "[SYSTEM] TitaNet speaker model ready")

        threading.Thread(target=_load_titanet_bg, daemon=True).start()
    except Exception as _tne:
        print(Fore.YELLOW + f"[SYSTEM] TitaNet preload skipped: {_tne}")

    # Hands
    try:
        import hands.core as core
        import hands.system as system_mod
        import hands.scheduler as scheduler_mod
        import hands.windows as hands_windows

        ctx.core          = core
        ctx.system_mod    = system_mod
        ctx.scheduler_mod = scheduler_mod
        ctx.hands_windows = hands_windows
        print("[SYSTEM] Hands loaded")
    except Exception as e:
        print(f"[SYSTEM] Hands failed: {e}")
        import traceback; traceback.print_exc()

    # Mouth
    print(Fore.CYAN + "[SYSTEM] Loading mouth...")
    try:
        import pythoncom
        pythoncom.CoInitialize()
        print(Fore.CYAN + "[SYSTEM] COM initialized")
    except Exception as _com_err:
        print(Fore.YELLOW + f"[SYSTEM] COM init skipped: {_com_err}")

    try:
        # Clean import cache
        for _k in list(sys.modules.keys()):
            if 'mouth' in _k.lower() or 'pyttsx' in _k.lower():
                del sys.modules[_k]

        import mouth as _mouth_mod
        from mouth import interrupt as mouth_interrupt, is_speaking

        ctx.mouth           = _mouth_mod
        ctx.mouth_interrupt = mouth_interrupt
        ctx.is_speaking     = is_speaking
        print(Fore.GREEN + "[SYSTEM] Mouth loaded")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Mouth failed: {e}")
        import traceback; traceback.print_exc()

        class _FallbackMouth:
            def speak(self, text): print(f"[MOUTH FALLBACK] {text}")
            def interrupt(self): pass
            def is_speaking(self): return False

        _fb = _FallbackMouth()
        ctx.mouth           = _fb
        ctx.mouth_interrupt = _fb.interrupt
        ctx.is_speaking     = _fb.is_speaking
        print(Fore.YELLOW + "[SYSTEM] Using fallback mouth")

    # Memory
    try:
        print(Fore.CYAN + "[SYSTEM] Loading memory...")
        from memory import seven_memory as _sm
        from memory.mood import mood_engine as _me
        from memory.command_log import command_log as _cl

        ctx.seven_memory = _sm
        ctx.mood_engine  = _me
        ctx.command_log  = _cl
        _ = _sm.get_stats()
        print(Fore.GREEN + "[SYSTEM] Memory loaded")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Memory failed: {e}")
        import traceback; traceback.print_exc()

    print(Fore.GREEN + "[SYSTEM] AI modules loaded.")

    # Startup stats
    try:
        if ctx.seven_memory:
            stats = ctx.seven_memory.get_stats()
            print(Fore.GREEN + f"[SYSTEM] Memory: {stats['total_conversations']} conversations, {stats['total_facts']} facts")
        if ctx.mood_engine:
            mood_status = ctx.mood_engine.get_status()
            print(Fore.MAGENTA + f"[SYSTEM] Mood: {mood_status['mood_value']:.2f} ({mood_status['label']})")
        if ctx.command_log:
            cmd_stats = ctx.command_log.get_stats()
            print(Fore.CYAN + f"[SYSTEM] Commands: {cmd_stats['total']} (success: {cmd_stats['success_rate']})")
    except Exception as _stats_err:
        print(Fore.YELLOW + f"[SYSTEM] Stats skipped: {_stats_err}")

    try:
        if ctx.is_voice_id_enabled and ctx.is_voice_id_enabled():
            speakers = ctx.get_enrolled_speakers()
            print(Fore.CYAN + f"[SYSTEM] Voice ID active. Speakers: {', '.join(speakers)}")
        else:
            print(Fore.YELLOW + "[SYSTEM] Voice ID inactive.")
    except Exception:
        pass

    return True