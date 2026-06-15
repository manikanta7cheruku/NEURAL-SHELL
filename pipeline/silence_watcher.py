"""
pipeline/silence_watcher.py
Seven proactive silence detection.

After SILENCE_THRESHOLD seconds of no user input, Seven speaks.
Three scenarios based on context.
"""

import threading
import time
import random
from colorama import Fore

SILENCE_THRESHOLD  = 60   # seconds before Seven speaks
PROACTIVE_COOLDOWN = 180  # seconds before Seven speaks again


class SilenceWatcher:

    def __init__(self, speak_fn, get_last_topic_fn=None):
        self._speak            = speak_fn
        self._get_last_topic   = get_last_topic_fn
        self._last_user_time   = time.time()
        self._last_proactive   = 0
        self._seven_speaking   = False
        self._paused           = False
        self._keyboard_active  = False
        self._keyboard_time    = 0
        self._running          = False
        self._thread           = None
        self._start_keyboard()

    def on_user_spoke(self):
        self._last_user_time  = time.time()
        self._keyboard_active = False

    def on_seven_speaking(self, is_speaking: bool):
        self._seven_speaking = is_speaking
        if is_speaking:
            # Reset silence timer when Seven speaks so it
            # doesnt immediately fire again right after
            self._last_user_time = time.time()

    def set_paused(self, paused: bool):
        self._paused = paused

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(Fore.CYAN + "[SILENCE] Watcher started")

    def stop(self):
        self._running = False
        if hasattr(self, '_listener') and self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

    def _start_keyboard(self):
        try:
            from pynput import keyboard
            def _on_key(key):
                self._keyboard_active = True
                self._keyboard_time   = time.time()
            self._listener = keyboard.Listener(on_press=_on_key)
            self._listener.daemon = True
            self._listener.start()
        except Exception:
            self._listener = None

    def _scenario(self) -> str:
        now            = time.time()
        topic          = self._get_last_topic() if self._get_last_topic else None
        keyboard_recent = (now - self._keyboard_time) < 90

        if topic and (now - self._last_user_time) < 180:
            return 'C'
        if keyboard_recent and self._keyboard_active:
            return 'A'
        return 'B'

    def _line(self, scenario: str) -> str:
        topic = self._get_last_topic() if self._get_last_topic else None

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
        while self._running:
            time.sleep(5)

            if self._seven_speaking:
                continue
            if self._paused:
                continue

            now           = time.time()
            silent_for    = now - self._last_user_time
            since_last    = now - self._last_proactive

            if silent_for < SILENCE_THRESHOLD:
                continue
            if since_last < PROACTIVE_COOLDOWN:
                continue

            scenario = self._scenario()
            line     = self._line(scenario)

            print(Fore.CYAN + f"[SILENCE] Scenario {scenario} speaking: {line}")

            try:
                self._speak(line)
                self._last_proactive = now
                self._keyboard_active = False
            except Exception as e:
                print(Fore.RED + f"[SILENCE] Speak error: {e}")