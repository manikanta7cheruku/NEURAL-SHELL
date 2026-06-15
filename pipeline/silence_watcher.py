"""
pipeline/silence_watcher.py
Seven — Proactive silence detection.

Watches for silence after the user stops talking.
After 30 seconds of no user input, Seven speaks based on context:

  Scenario A — keyboard activity detected:
    User is working but not talking to Seven.
    Seven makes an observational comment.

  Scenario B — complete idle (no keyboard, no voice):
    User might have walked away or forgotten Seven is on.
    Seven checks in briefly.

  Scenario C — mid-conversation silence:
    User was talking to Seven and then stopped.
    Seven follows up on the last topic.

The watcher runs in a background thread.
It is paused while Seven is speaking (to avoid talking over itself).
It resets whenever the user speaks.
"""

import threading
import time
import random
from colorama import Fore


# How long to wait before Seven speaks proactively (seconds)
SILENCE_THRESHOLD = 30

# After Seven speaks proactively, wait this long before speaking again
# (don't spam the user if they're just busy)
PROACTIVE_COOLDOWN = 120


class SilenceWatcher:
    """
    Background thread that monitors user activity and triggers
    proactive speech when Seven has been silent for too long.
    """

    def __init__(self, speak_fn, get_last_topic_fn=None):
        """
        Args:
            speak_fn:          Function to call to make Seven speak. 
                               Signature: speak_fn(text: str)
            get_last_topic_fn: Optional function that returns the last 
                               thing the user said (for scenario C).
                               Signature: () -> str or None
        """
        self._speak         = speak_fn
        self._get_last_topic = get_last_topic_fn

        self._last_user_input_time  = time.time()
        self._last_proactive_time   = 0
        self._is_seven_speaking     = False
        self._is_paused             = False   # True when Seven is in pause/sleep mode
        self._keyboard_active       = False   # True if keys pressed recently
        self._keyboard_last_time    = 0
        self._running               = False
        self._thread                = None

        # Keyboard monitor (pynput) — optional, degrades gracefully if not available
        self._keyboard_listener = None
        self._start_keyboard_monitor()

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC INTERFACE — called from main.py / voice loop
    # ─────────────────────────────────────────────────────────────────────────

    def on_user_spoke(self):
        """Call this every time the user says something. Resets the silence timer."""
        self._last_user_input_time = time.time()
        self._keyboard_active      = False  # Voice resets keyboard flag too

    def on_seven_speaking(self, is_speaking: bool):
        """Call this when Seven starts/stops speaking. Prevents talking over itself."""
        self._is_seven_speaking = is_speaking

    def set_paused(self, paused: bool):
        """Call this when Seven goes into pause/sleep mode. Stops proactive speech."""
        self._is_paused = paused

    def start(self):
        """Start the background watcher thread."""
        self._running = True
        self._thread  = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        print(Fore.CYAN + "[SILENCE] Watcher started (threshold: 30s)")

    def stop(self):
        """Stop the background watcher thread."""
        self._running = False
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # KEYBOARD MONITOR
    # ─────────────────────────────────────────────────────────────────────────

    def _start_keyboard_monitor(self):
        """Start listening for keyboard activity. Fails silently if pynput unavailable."""
        try:
            from pynput import keyboard

            def on_key_press(key):
                self._keyboard_active    = True
                self._keyboard_last_time = time.time()

            self._keyboard_listener = keyboard.Listener(on_press=on_key_press)
            self._keyboard_listener.daemon = True
            self._keyboard_listener.start()
            print(Fore.CYAN + "[SILENCE] Keyboard monitor active")
        except ImportError:
            print(Fore.YELLOW + "[SILENCE] pynput not available — keyboard detection disabled")
            print(Fore.YELLOW + "[SILENCE] Install with: pip install pynput")
        except Exception as e:
            print(Fore.YELLOW + f"[SILENCE] Keyboard monitor failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO DETECTION
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_scenario(self) -> str:
        """
        Returns 'A', 'B', or 'C' based on current context.
        
        A = keyboard active (user is working)
        B = complete idle (no keyboard, no voice for a while)
        C = mid-conversation silence (user was talking to Seven recently)
        """
        now             = time.time()
        last_topic      = self._get_last_topic() if self._get_last_topic else None
        keyboard_recent = (now - self._keyboard_last_time) < 60  # Active in last 60s

        if last_topic and (now - self._last_user_input_time) < 120:
            # User was in a conversation and went quiet
            return 'C'
        elif keyboard_recent and self._keyboard_active:
            # User is typing but not talking
            return 'A'
        else:
            # Nobody home
            return 'B'

    # ─────────────────────────────────────────────────────────────────────────
    # PROACTIVE SPEECH LINES
    # ─────────────────────────────────────────────────────────────────────────

    def _get_proactive_line(self, scenario: str) -> str:
        """Returns a proactive line for the given scenario."""

        # Scenario A — user is working, Seven observes
        scenario_a_lines = [
            "Still here if you need me.",
            "Working on something? I'm around.",
            "Quiet out there. Just checking the lights are still on.",
            "You've been at it a while. Need anything?",
            "I'm here. Just not sure you remembered.",
            "Whenever you're ready.",
        ]

        # Scenario B — complete idle
        scenario_b_lines = [
            "Everything alright?",
            "You went quiet on me.",
            "Still there?",
            "I'm here. Just checking.",
            "Hello? Still online over here.",
            "You've gone silent. I'll be here when you need me.",
        ]

        # Scenario C — mid-conversation follow-up
        last_topic = self._get_last_topic() if self._get_last_topic else None

        if scenario == 'C' and last_topic:
            topic_followups = [
                f"Did that answer what you needed, or should I go further?",
                f"Anything else on that?",
                f"Was that useful, or did I miss something?",
                f"Let me know if you want more on that.",
                f"Still thinking about it, or are we done?",
            ]
            return random.choice(topic_followups)

        if scenario == 'A':
            return random.choice(scenario_a_lines)
        else:
            return random.choice(scenario_b_lines)

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN WATCH LOOP
    # ─────────────────────────────────────────────────────────────────────────

    def _watch_loop(self):
        """Background loop. Checks silence every 5 seconds."""
        while self._running:
            time.sleep(5)

            # Don't interrupt if Seven is already speaking
            if self._is_seven_speaking:
                continue

            # Don't speak if Seven is in pause/sleep mode
            if self._is_paused:
                continue

            now             = time.time()
            silent_for      = now - self._last_user_input_time
            since_proactive = now - self._last_proactive_time

            # Wait for silence threshold
            if silent_for < SILENCE_THRESHOLD:
                continue

            # Respect cooldown between proactive lines
            if since_proactive < PROACTIVE_COOLDOWN:
                continue

            # Determine what kind of silence this is
            scenario = self._detect_scenario()
            line     = self._get_proactive_line(scenario)

            print(Fore.CYAN + f"[SILENCE] Scenario {scenario} — proactive: '{line}'")

            try:
                self._speak(line)
                self._last_proactive_time = now
                # Reset keyboard flag after speaking
                # so next cycle evaluates fresh
                self._keyboard_active = False
            except Exception as e:
                print(Fore.RED + f"[SILENCE] Speak failed: {e}")