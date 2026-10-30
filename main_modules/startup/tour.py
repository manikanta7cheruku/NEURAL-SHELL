"""
main_modules/startup/tour.py
Seven's first-run welcome: it makes sure you can hear and see it, introduces itself, walks through the home screen
and opens a welcome card, while the screen highlights each thing as Seven mentions it.

    audio     if the volume is muted or low, raise it (never above 60, never lower) and say so, so the rest is heard
    screen    if the screen is dim (under 60 percent, laptops and monitors that allow it), raise it to 60
    intro     who Seven is                                 highlights the orb
    listen    "Hey Seven" and the listening switch         highlights the switch
    mic       the Test mic button                          highlights the button
    log       the voice log under the clock                highlights it (example lines if nothing was said yet)
    bar       the voice bar at the top of the screen       nothing to highlight: it is its own window
    pages     each page along the bottom, one by one       highlights each link, then Search, then Welcome guide
    card      the welcome card opens; Seven says why feedback matters (the card shows its Feedback tab), then
              points to Replay the tour on the About tab

The screen follows the `tour` value in the status feed ({step, n}); a Skip button on screen calls skip(). The whole
tour is spoken as one stream, so sentences follow each other without gaps, and each sentence sets the step when it
starts playing. Only the first launch after setup runs it (greeting.greet); the welcome card's "Replay the tour"
runs it again, and opening the card by hand has Seven say the short message (speak_welcome).
"""
import threading
import time

from main_modules.startup import greeting

LOW_VOLUME = 40          # at or below this (or muted) the volume is raised
TARGET_VOLUME = 60       # to this: audible, never alarming
MIN_BRIGHTNESS = 60      # a dimmer screen is raised to this, so the tour can be seen

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


# The words Seven says about feedback. The same message is said when the tour ends and when the card is opened by hand.
FEEDBACK_LINES = [
    "Seven is early, and your feedback is what shapes it.",
    "Every note you send is read, and what comes up most decides what we build next.",
    "So please tell me what is wrong, what is missing, and what you want first. Send feedback is right there on the card.",
]


def script(name: str) -> list:
    """[(step, sentence)] in the order Seven says them. Each sentence is one sentence, so the voice never splits it."""
    return [
        ("intro", f"Hi {name}, I'm Seven." if name else "Hi, I'm Seven."),
        ("intro", "I'm an assistant that lives on your PC, and everything I do stays on it."),
        ("listen", 'To talk to me, just say "Hey Seven", then ask for something.'),
        ("listen", "You can change how I listen up here: wake word, always on, or push to talk."),
        ("mic", "Not sure I can hear you?"),
        ("mic", "Press Test mic and say anything, and I'll show you exactly what I heard."),
        ("log", "Whenever you speak, the lines under the clock show what I heard, or why I ignored it."),
        ("log", "That's your voice log, so you can always see what I picked up."),
        ("bar", "At the very top of your screen is my voice bar, with live captions of you and me."),
        ("bar", "Right click it to open any page or put it back in the middle, and in Settings you can set it to show while talking, always, or off."),
        ("pages", "Along the bottom are your everyday pages."),
        ("nav-1", "Overview shows how Seven and your PC are doing."),
        ("nav-2", "Chat is where you type to me and see every conversation."),
        ("nav-3", "Tasks is your to-do list."),
        ("nav-4", "Reminders holds your alarms, timers and reminders."),
        ("nav-5", "Memory is everything I remember about you, and you can edit or erase it."),
        ("search", "Search, or Control K, finds any page or action."),
        ("welcome-link", "And Welcome guide, on the left, brings this tour and our roadmap back whenever you like."),
        ("card", "I've put a short welcome on your screen."),
        ("feedback", FEEDBACK_LINES[0]),
        ("feedback", FEEDBACK_LINES[1]),
        ("feedback", FEEDBACK_LINES[2]),
        ("about", "You can replay this tour from the card at any time."),
    ]


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def step_for(text: str, steps, fallback=None):
    """
    The step a spoken sentence belongs to. The voice may split a long sentence at a comma or a question mark, so a
    part is matched to the scripted sentence it came from (exact, else contained in it, else it starts it), and only
    when nothing matches does it keep the step before it. (Matching only whole sentences left "Press Test mic" on the
    listening switch.)
    """
    t = _norm(text)
    if not t:
        return fallback
    scripted = [(s, _norm(x)) for s, x in steps]
    for s, x in scripted:
        if x == t:
            return s
    for s, x in scripted:
        if t in x or x in t:
            return s
    for s, x in scripted:
        if x.startswith(t[:24]) or t.startswith(x[:24]):
            return s
    return fallback


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


def _screen_brightness():
    """The first screen's brightness in percent, or None when it can't be read (most desktop monitors)."""
    try:
        import screen_brightness_control as sbc
        levels = sbc.get_brightness()
        return int(levels[0]) if levels else None
    except Exception:
        return None


def ensure_visible(ctx) -> str:
    """Raise the screen brightness to MIN_BRIGHTNESS if it is lower, so the tour can be seen. Returns what to say."""
    level = _screen_brightness()
    if level is None or level >= MIN_BRIGHTNESS:
        return ""
    try:
        ok, _ = ctx.system_mod._brightness_set(MIN_BRIGHTNESS)
    except Exception:
        return ""
    if not ok:
        return ""
    return (f"I've turned your screen brightness up to {MIN_BRIGHTNESS} percent so you can see everything. "
            "Say, set brightness to 40, whenever you'd like it different.")


def _say_all(ctx, steps, speak=None, set_steps=True) -> bool:
    """
    Speak every sentence, setting the caption (and, for the tour, the step) as each one starts.
    Returns True if the welcome card step was reached.
    """
    steps = [(s, t) for s, t in steps if t]
    current = [None]
    reached = [False]

    def starting(text):
        found = step_for(text, steps, fallback=current[0])
        _set("seven_text", text)
        if set_steps and found != current[0]:             # only a change of step tells the screen to move
            current[0] = found
            if found in ("card", "feedback"):
                reached[0] = True
            _step(found)
        elif set_steps:
            current[0] = found

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
        return reached[0]
    for step, text in steps:                              # basic voice (or a test): one sentence at a time
        if _skip.is_set():
            return reached[0]
        starting(text)
        (speak or ctx.mouth.speak)(text)
    return reached[0]


def run(ctx, config, speak=None) -> None:
    """Speak the welcome tour. Blocks until it ends or is skipped, then makes sure the welcome card is open."""
    if not _busy.acquire(blocking=False):
        return
    reached_card = False
    try:
        _skip.clear()
        name = greeting._name(config)
        notes = []
        if ctx is not None and speak is None:
            notes = [n for n in (ensure_audible(ctx), ensure_visible(ctx)) if n]
        _set("user_text", "")
        _set("voice_turn", time.time())                  # the voice bar shows the captions
        _set("speaking", True)
        steps = [("audio", n) for n in notes] + script(name)
        print("[TOUR] " + " ".join(t for _, t in steps))
        try:
            reached_card = _say_all(ctx, steps, speak)
        except Exception as e:
            print(f"[TOUR] could not speak: {e}")
    finally:
        _set("speaking", False)
        _set("seven_text", "")                            # the captions were for the tour; don't leave them behind
        greeting.update_welcome(tour_done=True)
        if not reached_card:                              # skipped, or the voice failed: the card still opens
            _step("card")
        _busy.release()


def skip() -> bool:
    """The Skip button, or closing the card: stop talking. The tour goes straight to the card."""
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


def speak_welcome() -> bool:
    """The welcome card was opened by hand: Seven says, briefly, what the card is for and why feedback matters."""
    if _ctx is None or _busy.locked():
        return False

    def _go():
        if not _busy.acquire(blocking=False):
            return
        try:
            _skip.clear()
            _set("voice_turn", time.time())
            _set("speaking", True)
            lines = [("card", "This is your welcome guide.")] + [("card", t) for t in FEEDBACK_LINES]
            _say_all(_ctx, lines, set_steps=False)
        except Exception as e:
            print(f"[TOUR] could not speak the welcome: {e}")
        finally:
            _set("speaking", False)
            _set("seven_text", "")
            _busy.release()

    threading.Thread(target=_go, daemon=True, name="WelcomeSpeech").start()
    return True
