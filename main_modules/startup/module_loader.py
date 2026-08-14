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

    # ── Ears (core only - no heavy models on startup) ──────────────────────
    try:
        from ears import listen
        from ears.core import listen_for_interrupt

        ctx.listen               = listen
        ctx.listen_for_interrupt = listen_for_interrupt

        # Safe fallbacks - replaced by background loader when ready
        ctx.identify_speaker      = lambda path: "default"
        ctx.enroll_speaker        = lambda: None
        ctx.is_voice_id_enabled   = lambda: False
        ctx.get_enrolled_speakers = lambda: []

        print(Fore.GREEN + "[SYSTEM] Ears loaded")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Ears failed: {e}")
        import traceback; traceback.print_exc()
        if ctx.app_ui:
            ctx.app_ui.update_status("EARS ERROR", "#ff0000")
        return False

    # ── Brain ───────────────────────────────────────────────────────────────
    try:
        import brain
        import brain_manager
        ctx.brain = brain
        print(Fore.GREEN + "[SYSTEM] Brain loaded")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Brain failed: {e}")
        import traceback; traceback.print_exc()
        if ctx.app_ui:
            ctx.app_ui.update_status("BRAIN ERROR", "#ff0000")
        return False

    # ── Hands ───────────────────────────────────────────────────────────────
    try:
        import hands.core as core
        import hands.system as system_mod
        import hands.scheduler as scheduler_mod
        import hands.windows as hands_windows

        ctx.core          = core
        ctx.system_mod    = system_mod
        ctx.scheduler_mod = scheduler_mod
        ctx.hands_windows = hands_windows
        print(Fore.GREEN + "[SYSTEM] Hands loaded")
    except Exception as e:
        print(Fore.RED + f"[SYSTEM] Hands failed: {e}")
        import traceback; traceback.print_exc()

    # ── Mouth ───────────────────────────────────────────────────────────────
    print(Fore.CYAN + "[SYSTEM] Loading mouth...")
    try:
        import pythoncom
        pythoncom.CoInitialize()
        print(Fore.CYAN + "[SYSTEM] COM initialized")
    except Exception as _com_err:
        print(Fore.YELLOW + f"[SYSTEM] COM init skipped: {_com_err}")

    try:
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

    # ── Memory (background - ChromaDB downloads models on first run) ────────
    # Loading synchronously blocks the API server from starting.
    # We set safe None fallbacks here. The background thread updates
    # ctx in-place when models finish downloading. All callers
    # already guard with: if ctx.seven_memory:
    ctx.seven_memory = None
    ctx.mood_engine  = None
    ctx.command_log  = None

    def _load_heavy_modules_bg():
        """
        Load memory and voice ID in background.
        Both require HuggingFace model downloads on first run
        which can take 2-5 minutes on a slow connection.
        Neither should block the API server from starting.
        """
        import time as _t

        # ── Memory ──────────────────────────────────────────────────────
        try:
            print(Fore.CYAN + "[SYSTEM] [BG] Loading memory...")
            _t0 = _t.time()
            from memory import seven_memory as _sm
            from memory.mood import mood_engine as _me
            from memory.command_log import command_log as _cl

            ctx.seven_memory = _sm
            ctx.mood_engine  = _me
            ctx.command_log  = _cl

            stats = _sm.get_stats()
            elapsed = round(_t.time() - _t0, 1)
            print(Fore.GREEN + f"[SYSTEM] [BG] Memory ready in {elapsed}s — "
                  f"{stats['total_conversations']} conversations, "
                  f"{stats['total_facts']} facts")

            mood_status = _me.get_status()
            print(Fore.MAGENTA + f"[SYSTEM] [BG] Mood: "
                  f"{mood_status['mood_value']:.2f} ({mood_status['label']})")

            cmd_stats = _cl.get_stats()
            print(Fore.CYAN + f"[SYSTEM] [BG] Commands: "
                  f"{cmd_stats['total']} (success: {cmd_stats['success_rate']})")

        except Exception as _me_err:
            print(Fore.RED + f"[SYSTEM] [BG] Memory failed: {_me_err}")
            import traceback; traceback.print_exc()

        # ── Voice ID ─────────────────────────────────────────────────────
        try:
            print(Fore.CYAN + "[SYSTEM] [BG] Loading Voice ID...")
            _t1 = _t.time()
            from ears.voice_id import (
                identify_speaker, enroll_speaker,
                is_voice_id_enabled, get_enrolled_speakers
            )
            ctx.identify_speaker      = identify_speaker
            ctx.enroll_speaker        = enroll_speaker
            ctx.is_voice_id_enabled   = is_voice_id_enabled
            ctx.get_enrolled_speakers = get_enrolled_speakers

            elapsed = round(_t.time() - _t1, 1)
            if is_voice_id_enabled():
                speakers = get_enrolled_speakers()
                print(Fore.GREEN + f"[SYSTEM] [BG] Voice ID ready in {elapsed}s — "
                      f"speakers: {', '.join(speakers)}")
            else:
                print(Fore.YELLOW + f"[SYSTEM] [BG] Voice ID ready in {elapsed}s — inactive")

        except Exception as _vi_err:
            print(Fore.YELLOW + f"[SYSTEM] [BG] Voice ID skipped: {_vi_err}")

    threading.Thread(
        target=_load_heavy_modules_bg,
        daemon=True,
        name="HeavyModuleLoader"
    ).start()

    print(Fore.GREEN + "[SYSTEM] Core modules ready. Memory and Voice ID loading in background.")
    return True