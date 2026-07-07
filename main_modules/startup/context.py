"""
main_modules/startup/context.py
Shared runtime context object passed to all handlers.
"""


class SevenContext:
    """
    Runtime context for Seven's voice loop.
    Passed to handlers so they have access to modules and state.
    """

    def __init__(self):
        # Module references (set by module_loader)
        self.brain = None
        self.mouth = None
        self.mouth_interrupt = None
        self.is_speaking = None
        self.core = None
        self.system_mod = None
        self.scheduler_mod = None
        self.hands_windows = None
        self.seven_memory = None
        self.mood_engine = None
        self.command_log = None
        self.listen = None
        self.identify_speaker = None
        self.enroll_speaker = None
        self.is_voice_id_enabled = None
        self.get_enrolled_speakers = None
        self.listen_for_interrupt = None

        # Set by main.py
        self.app_ui = None
        self.api_set_state = None
        self.config = None

        # Runtime state
        self.speaker_id = "default"
        self.user_input = ""
        self.speech_part = ""
        self.pre_executed_sys = False
        self.pre_executed_open = False
        self.pre_executed_close = False
        self.interrupt_context = {
            "last_response": None,
            "last_input": None,
            "was_interrupted": False,
        }
        self.silence_watcher = None

        # Helper callables (set by main.py)
        self.speak_with_interrupt = None

    def update_status(self, text, color):
        """Update UI status via app_ui."""
        if self.app_ui:
            self.app_ui.update_status(text, color)

    def speak(self, text):
        """Speak text without interrupt support."""
        if self.mouth:
            self.mouth.speak(text)