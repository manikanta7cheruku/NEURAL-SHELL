# ears/__init__.py
# listen() and listen_for_interrupt() load ears.core (and with it Whisper) on first use, not on import: the trigger
# daemon imports ears.snap_detector and ears.audio_triggers and must not load a speech model to listen for snaps.


def listen():
    from ears.core import listen as _listen
    return _listen()


def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    from ears.core import listen_for_interrupt as _lfi
    return _lfi(interrupt_words, on_interrupt_callback, stop_event)
