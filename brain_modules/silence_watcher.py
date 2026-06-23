"""
=============================================================================
brain_modules/silence_watcher.py
PROJECT SEVEN -- Proactive Silence Detection

MOVED FROM: pipeline/silence_watcher.py
REASON FOR MOVE:
    Silence watching is brain-level behavior. It controls WHEN Seven speaks
    proactively. It belongs with other brain behavior files, not in a
    separate pipeline/ folder. Co-location of related code is an engineering
    best practice called "high cohesion".

WHAT THIS FILE DOES:
    After SILENCE_THRESHOLD seconds of no user input, Seven speaks.
    It detects three scenarios and picks appropriate lines:
        Scenario A -- User is typing (keyboard active) but not speaking
        Scenario B -- User has gone completely idle
        Scenario C -- User spoke recently but went quiet after Seven answered

DESIGN PATTERN: Observer Pattern (passive monitoring, event-driven response)
    The watcher runs in a background daemon thread.
    It does not block the main voice loop.
    It fires only when conditions are met.

WHY DAEMON THREAD:
    daemon=True means this thread dies automatically when main.py exits.
    We never need to explicitly stop it on shutdown.
    Non-daemon threads would keep the process alive even after Ctrl+C.

INTERVIEW TALKING POINT:
    "I used a daemon thread for the silence watcher because it should
     never block program exit. It is a background observer -- if the
     main thread dies, this dies with it. This is the correct pattern
     for monitoring threads in Python."

THRESHOLDS (tunable):
    SILENCE_THRESHOLD  = 300 seconds (5 minutes) before Seven speaks
    PROACTIVE_COOLDOWN = 600 seconds (10 minutes) between proactive lines
    These are conservative because speaking too often becomes annoying.
=============================================================================
"""

import threading
import time
import random
from colorama import Fore

# ---------------------------------------------------------------------------
# THRESHOLDS
# These are module-level constants so they can be seen and changed in one
# place. If you want Seven to speak after 2 minutes instead of 5, change
# SILENCE_THRESHOLD = 120 here.
# ---------------------------------------------------------------------------
SILENCE_THRESHOLD  = 300   # seconds of silence before Seven speaks
PROACTIVE_COOLDOWN = 600   # seconds between proactive lines (anti-spam)


class SilenceWatcher:
    """
    Monitors how long the user has been silent.
    Speaks proactively when silence exceeds SILENCE_THRESHOLD.

    CONSTRUCTOR ARGS:
        speak_fn         -- the speak_with_interrupt() function from main.py
                           We inject this dependency instead of importing mouth
                           directly. This is Dependency Injection.
        get_last_topic_fn -- lambda that returns the last thing the user said
                            Used to pick which scenario line to speak.

    WHY DEPENDENCY INJECTION HERE:
        SilenceWatcher does not own the TTS engine.
        main.py owns it. We pass the function in.
        This means SilenceWatcher can be tested independently by passing
        a mock speak function. This is the Inversion of Control principle.
    """

    def __init__(self, speak_fn, get_last_topic_fn=None):
        # The TTS function -- injected from main.py
        self._speak           = speak_fn

        # Lambda that returns last user utterance -- used for Scenario C
        self._get_last_topic  = get_last_topic_fn

        # Timestamps -- float (Unix epoch seconds)
        self._last_user_time  = time.time()  # When user last spoke
        self._last_proactive  = 0            # When Seven last spoke proactively

        # State flags
        self._seven_speaking  = False  # True while Seven is outputting TTS
        self._paused          = False  # True when user said "pause" / "sleep"

        # Keyboard detection state
        # We track keyboard activity so we know if user is working
        # (typing) vs truly idle
        self._keyboard_active = False
        self._keyboard_time   = 0      # When keyboard was last active

        # Thread control
        self._running         = False
        self._thread          = None
        self._listener        = None   # pynput keyboard listener

        # NOTE: Keyboard listener starts in start(), not here.
        # Reason: faster_whisper imports numpy. pynput also touches audio.
        # Starting pynput here causes a circular import race condition
        # with faster_whisper during startup. Delay until all modules loaded.

    # -----------------------------------------------------------------------
    # PUBLIC INTERFACE -- called from main.py
    # -----------------------------------------------------------------------

    def on_user_spoke(self):
        """
        Call this every time the user finishes speaking.
        Resets the silence timer so we don't fire while user is active.
        """
        self._last_user_time  = time.time()
        self._keyboard_active = False  # Speaking resets keyboard flag too

    def on_seven_speaking(self, is_speaking: bool):
        """
        Call this when Seven starts or stops speaking.
        We reset silence timer when Seven speaks -- otherwise the watcher
        fires immediately after Seven finishes a proactive line.
        """
        self._seven_speaking = is_speaking
        if is_speaking:
            # Reset silence timer when Seven speaks
            # This prevents: Seven speaks -> 5 seconds pass -> Seven speaks again
            self._last_user_time = time.time()

    def set_paused(self, paused: bool):
        """
        Pause or resume the watcher.
        Called when user says 'pause' or 'wake up'.
        When paused, Seven will not speak proactively.
        """
        self._paused = paused

    def start(self):
        """
        Start the watcher. Called from main.py in a daemon thread.
        Starts keyboard monitoring first (safe to do here -- all imports done).
        Then starts the main monitoring loop.
        """
        self._running = True

        # Start keyboard listener here -- after all modules are loaded
        # This avoids the numpy/pynput circular import race
        self._start_keyboard()

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(Fore.CYAN + "[SILENCE] Watcher started")

    def stop(self):
        """
        Stop the watcher cleanly.
        Called on shutdown if needed (optional -- daemon thread auto-dies).
        """
        self._running = False
        if hasattr(self, '_listener') and self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # PRIVATE -- internal logic
    # -----------------------------------------------------------------------

    def _start_keyboard(self):
        """
        Start pynput keyboard listener.
        Sets _keyboard_active=True on any keypress.
        Uses daemon listener so it dies with main thread.

        WHY PYNPUT:
            pynput is a cross-platform keyboard/mouse monitoring library.
            It works without admin rights on Windows.
            Alternative would be keyboard library but pynput is more stable.

        ERROR HANDLING:
            If pynput is not installed or fails (e.g. headless server),
            we silently skip it. Keyboard detection becomes unavailable
            but everything else works fine. This is graceful degradation.
        """
        try:
            from pynput import keyboard

            def _on_key(key):
                # Called on every keypress -- keep it fast
                self._keyboard_active = True
                self._keyboard_time   = time.time()

            self._listener = keyboard.Listener(on_press=_on_key)
            self._listener.daemon = True
            self._listener.start()

        except Exception:
            # pynput not installed or failed -- keyboard detection disabled
            # System continues working without it
            self._listener = None

    def _scenario(self) -> str:
        """
        Determine which scenario applies right now.

        SCENARIOS:
            A -- User is at keyboard (working) but not speaking
                 Best line: "Working on something? I'm around."
            B -- User is completely idle (no keyboard, no speech)
                 Best line: "Still there?"
            C -- User spoke recently, got an answer, then went quiet
                 Best line: "Did that answer what you needed?"

        LOGIC:
            C wins if: there is a topic AND it was recent (< 3 minutes ago)
            A wins if: keyboard was active in last 90 seconds
            B is the fallback

        Returns: 'A', 'B', or 'C'
        """
        now             = time.time()
        topic           = self._get_last_topic() if self._get_last_topic else None
        keyboard_recent = (now - self._keyboard_time) < 90  # 90 second window

        # Scenario C: recent conversation exists
        if topic and (now - self._last_user_time) < 180:
            return 'C'

        # Scenario A: user is typing
        if keyboard_recent and self._keyboard_active:
            return 'A'

        # Scenario B: completely idle
        return 'B'

    def _line(self, scenario: str) -> str:
        """
        Pick a random line for the given scenario.

        WHY RANDOM:
            If Seven always said the same line, users would tune it out.
            Random selection from a curated list keeps it natural.
            This is the same approach used in commercial voice assistants.

        TARS PERSONALITY:
            Lines are dry and brief. Not chatty. Not needy.
            "Still there?" not "Oh I haven't heard from you in a while!"
        """
        topic = self._get_last_topic() if self._get_last_topic else None

        # Lines for each scenario -- TARS-style: dry, brief, not annoying
        a_lines = [
            "Still here if you need anything.",
            "Working on something? I am around.",
            "You have been at it a while. Need anything?",
            "Whenever you are ready.",
            "I am here. Just not sure you remembered.",
        ]
        b_lines = [
            "Everything alright?",
            "You went quiet.",
            "Still there?",
            "Hello? Still online over here.",
            "I will be here when you need me.",
        ]
        c_lines = [
            "Did that answer what you needed?",
            "Anything else on that?",
            "Was that useful or did I miss something?",
            "Let me know if you want more on that.",
            "Still thinking about it or are we done?",
        ]

        if scenario == 'C' and topic:
            return random.choice(c_lines)
        if scenario == 'A':
            return random.choice(a_lines)
        return random.choice(b_lines)

    def _loop(self):
        """
        Main monitoring loop. Runs in a daemon thread.
        Checks every 5 seconds -- lightweight, no busy-waiting.

        LOOP LOGIC:
            Every 5 seconds, check:
            1. Is Seven already speaking? Skip.
            2. Is the watcher paused? Skip.
            3. Has enough silence passed? If not, skip.
            4. Is the cooldown period over? If not, skip.
            5. All checks pass -> pick scenario -> speak.

        WHY time.sleep(5):
            Checking every second wastes CPU.
            Checking every 60 seconds is too slow.
            5 seconds is the right granularity for a 5-minute threshold.

        API STATE SYNC:
            We update the FastAPI state before and after speaking.
            This keeps the React frontend orb in sync with what Seven is doing.
            The import is inside the loop (not at top) because the API server
            starts after this module loads -- top-level import would fail.
        """
        while self._running:
            time.sleep(5)  # Check every 5 seconds

            # Guard 1: Do not interrupt Seven mid-sentence
            if self._seven_speaking:
                continue

            # Guard 2: Do not speak when paused
            if self._paused:
                continue

            now        = time.time()
            silent_for = now - self._last_user_time
            since_last = now - self._last_proactive

            # Guard 3: Not enough silence yet
            if silent_for < SILENCE_THRESHOLD:
                continue

            # Guard 4: Too soon since last proactive line
            if since_last < PROACTIVE_COOLDOWN:
                continue

            # All guards passed -- time to speak
            scenario = self._scenario()
            line     = self._line(scenario)

            print(Fore.CYAN + f"[SILENCE] Scenario {scenario} -- speaking: {line}")

            try:
                # Update React frontend state before speaking
                try:
                    from backend.api_server import set_state as _api_set
                    _api_set("seven_text", line)
                    _api_set("speaking",   True)
                    _api_set("thinking",   False)
                    _api_set("listening",  False)
                except Exception:
                    pass  # API server may not be ready -- non-fatal

                # Speak the proactive line
                self._speak(line)

                # Update React frontend state after speaking
                try:
                    from backend.api_server import set_state as _api_set
                    _api_set("speaking",  False)
                    _api_set("listening", False)
                    # Main loop will set listening=True on next listen() call
                except Exception:
                    pass

                # Record when we last spoke proactively
                self._last_proactive  = now
                self._keyboard_active = False

            except Exception as e:
                print(Fore.RED + f"[SILENCE] Speak error: {e}")