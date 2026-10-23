# Ears (voice input)

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `ears/`, `main_modules/startup/voice_loop.py` |

## Purpose

Turns microphone audio into clean text for the brain, and decides whether the speech was meant for Seven.

## What exists today

- Pipeline in `ears/core.py`: microphone capture (SpeechRecognition, adaptive threshold), automatic gain (`agc.py`), echo cancellation while Seven speaks (`aec.py`), voice activity detection with Silero (`vad.py`), noise floor and signal gates (`noise_floor.py`, `signal_gates.py`), speech-to-text with faster-whisper, a hallucination filter (`hallucination_filter.py`, `hallucinations.json`) and autocorrect.
- Wake word with fuzzy matching for common mishearings (`wake_word.py`); words come from `identity.wake_words`.
- Push to talk while Shift is held (`push_to_talk.py`).
- Speaker verification with NVIDIA TitaNet embeddings (`voice_id.py`, `voice_id_gate.py`); Ultimate plan.
- Audio triggers (clap, snap) with a YAMNet model (`audio_triggers*.py`, `yamnet_wrapper.py`).
- Pause, resume and interrupt phrases come from `identity.pause_words`, `resume_words` and the interrupt config.

## To be written

These sections will follow the structure of the brain document:

- [ ] Purpose
- [ ] How it works
- [ ] Data and configuration
- [ ] Interfaces (what calls it, what it calls)
- [ ] Failure modes and recovery
- [ ] Tests
- [ ] Known limitations
- [ ] Planned work
