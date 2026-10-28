"""
main_modules/startup/tour.py
Seven's first-run welcome: it makes sure you can hear it, introduces itself and walks through the home screen,
while the screen highlights each thing as Seven mentions it, then a welcome card opens.

    audio     if the volume is muted or low, raise it (never above 60, never lower) and say so, so the rest is heard
    intro     who Seven is                                 highlights the orb
    listen    "Hey Seven" and the listening switch         highlights the switch
    mic       the Test mic button                          highlights the button
    pages     the pages along the bottom and Ctrl+K        highlights the footer
    card      "I've put a short welcome guide on your screen"; the card opens

The screen follows the `tour` value in the status feed ({step, n}); a Skip button on screen calls skip(). The whole
tour is spoken as one stream, so sentences follow each other without gaps, and each sentence sets the step when it
starts playing. Only the first launch after setup runs it (greeting.greet); "Replay welcome tour" runs it again.
"""
import threading
import time

from main_modules.startup import greeting

LOW_VOLUME = 40          # at or below this (or muted) the volume is raised
TARGET_VOLUME = 60       # to this: audible, never alarming

_skip = threading.Event()
_busy = threading.Lock()
_ctx = None
_config = None
_n = 0


def attach(ctx, config) -> None:
    """Remember what the replay needs; called once by the voice loop."""
    global _ctx, _config
    _ctx, _config = ctx, config


def _set(key, value) -> None:
    try:
        from backend.api_server import set_state
        set_state(key, value)
    except Exception:
        pass


def _step(step) -> None:
    global _n
    _n += 1
    _set("tour", {"step": step, "n": _n})


def script(name: str) -> list:
    """[(step, sentence)] in the order Seven says them."""
    return [
        ("intro", f"Hi {name}, I'm Seven." if name else "Hi, I'm Seven."),
        ("intro", "I'm an assistant that lives on your PC, and everything I do stays on it."),
        ("listen", 'To talk to me, just say "Hey Seven", then ask for something.'),
        ("listen", "You can change how I listen up here: wake word, always on, or push to talk."),
        ("mic", "Not sure I can hear you? Press Test mic, and say anything."),
        ("pages", "Your everyday pages are along the bottom, and Control K searches everything."),
        ("outro", "I've put a short welcome guide on your screen."),
        ("outro", "Your first command is waiting there."),
    ]


def ensure_audible(ctx) -> str:
    """Raise the volume if it is muted or low, so the tour can be heard. Returns what to say, or '' if untouched."""
    try:
        vol = ctx.system_mod._get_volume()
        if not vol:
            return ""
        level = int(vol.GetMasterVolumeLevelScalar() * 100)
        muted = bool(vol.GetMute())
    except Exception:
        return ""
    if not muted and level > LOW_VOLUME:
        return ""
    try:
        if muted:
            ctx.system_mod._volume_unmute()
        if level < TARGET_VOLUME:
            ctx.system_mod._volume_set(TARGET_VOLUME)
    except Exception:
        return ""
    if level >= TARGET_VOLUME:
        return "First, I've unmuted your speakers so you can hear me."
    return (f"First, I've turned your volume up to {TARGET_VOLUME} percent so you can hear me. "
            "Say, set volume to 30, whenever you'd like it different.")


def _say_all(ctx, steps, speak=None) -> None:
    """Speak every sentence, setting the tour step and the caption as each one starts."""
    steps = [(s, t) for s, t in steps if t]
    by_text = {}
    for step, text in steps:
        by_text.setdefault(" ".join(text.split()), step)

    current = [None]

    def starting(text):
        # The voice may split a long sentence at a comma; a part it split keeps the step it came from.
        current[0] = by_text.get(" ".join(text.split())) or current[0]
        _set("seven_text", text)
        _step(current[0])

    eng = None
    if speak is None:
        try:
            from mouth.core import _engine, _voice_choice
            eng = _engine()
        except Exception:
            eng = None
    if eng:                                               # one stream: no gaps between sentences
        voice, speed = _voice_choice()
        eng.say([t for _, t in steps], voice=voice, speed=speed, on_sentence=starting)
        return
    for step, text in steps:                              # basic voice (or a test): one sentence at a time
        if _skip.is_set():
            return
        starting(text)
        (speak or ctx.mouth.speak)(text)


def run(ctx, config, speak=None) -> None:
    """Speak the welcome tour. Blocks until it ends or is skipped, then opens the welcome card."""
    if not _busy.acquire(blocking=False):
        return
    try:
        _skip.clear()
        name = greeting._name(config)
        note = ensure_audible(ctx) if ctx is not None and speak is None else ""
        _set("user_text", "")
        _set("voice_turn", time.time())                  # the voice bar shows the captions
        _set("speaking", True)
        steps = ([("audio", note)] if note else []) + script(name)
        print("[TOUR] " + " ".join(t for _, t in steps))
        try:
            _say_all(ctx, steps, speak)
        except Exception as e:
            print(f"[TOUR] could not speak: {e}")
    finally:
        _set("speaking", False)
        _set("seven_text", "")                            # the captions were for the tour; don't leave them behind
        greeting.update_welcome(tour_done=True)
        _step("card")                                     # the screen opens the welcome card
        _busy.release()


def skip() -> bool:
    """The Skip button: stop talking and go straight to the card."""
    if not _busy.locked():
        return False
    _skip.set()
    try:
        _ctx.mouth_interrupt()
    except Exception:
        pass
    return True


def acknowledge() -> None:
    """The screen has opened the card."""
    _step(None)


def replay() -> bool:
    """Run the tour again, on request."""
    if _ctx is None or _busy.locked():
        return False
    threading.Thread(target=run, args=(_ctx, _config), daemon=True, name="Tour").start()
    return True
