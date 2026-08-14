"""
ears/voice_id_gate.py
Voice ID gate: if enabled and speaker is unknown, discard audio.
"""

from ears.voice_id import identify_speaker, is_voice_id_enabled

def should_process(audio_path: str, enabled: bool) -> bool:
    """
    Should this audio be processed?
    If Voice ID is enabled and speaker is unknown: False.
    """
    if not enabled:
        return True
    if not is_voice_id_enabled():
        return False  # Gate on but no profiles enrolled
    speaker_id = identify_speaker(audio_path)
    return speaker_id != "unknown"