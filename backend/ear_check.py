"""
backend/ear_check.py
A five second microphone check that works without Seven running: what the microphone delivers, what the voice detector makes of
it, and what the speech model would transcribe, with the reason Seven would give for ignoring it.

It is for the case Diagnostics cannot settle: Seven says it is listening, the microphone is open, and still nothing is acted on.
Quit Seven first, then run it with Seven's own Python and speak when it asks:

    & "$env:LOCALAPPDATA\Programs\SEVEN\resources\app\python\python.exe" .\ear_check.py      (PowerShell)

(Start menu, "SEVEN Microphone Check", does the same.) The result is shown, saved to the Desktop as Seven-Mic-Check.txt and copied
to the clipboard. It records for five seconds, keeps nothing but numbers and the transcript, and sends nothing anywhere.
"""
import json
import os
import platform
import subprocess
import sys
import time

RATE, FRAME, SECONDS = 16000, 512, 6
START_P = {"relaxed": 0.40, "balanced": 0.55, "strict": 0.70}
LINES = []


def say(text=""):
    print(text)
    LINES.append(text)


def db(v):
    import math
    return round(20 * math.log10(max(v, 1e-6)), 1)


def settings():
    """The listening settings as Seven reads them (ears/core.py, voice_settings)."""
    path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as exc:
        say(f"  could not read {path}: {exc}")
        return {"mode": "wake", "sensitivity": "balanced", "mic": ""}
    voice, gates = cfg.get("voice", {}), cfg.get("voice_gates", {})
    mode = voice.get("listen_mode")
    if mode not in ("wake", "always", "ptt"):
        mode = "ptt" if gates.get("push_to_talk", {}).get("enabled") else "wake"
    sens = voice.get("sensitivity") if voice.get("sensitivity") in START_P else "balanced"
    say(f"  voice.listen_mode in the file: {voice.get('listen_mode', '(not set)')}")
    say(f"  voice_gates.push_to_talk.enabled in the file: {gates.get('push_to_talk', {}).get('enabled', '(not set)')}")
    say(f"  mode Seven uses: {mode}    sensitivity: {sens}    chosen microphone: {voice.get('mic') or '(Windows default)'}")
    return {"mode": mode, "sensitivity": sens, "mic": voice.get("mic", "") or ""}


def record(pa, mic_name):
    import pyaudio
    import numpy as np
    index = None
    if mic_name:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0 and mic_name.lower() in info.get("name", "").lower():
                index = i
                break
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=FRAME, input_device_index=index)
    frames = []
    for _ in range(int(SECONDS * RATE / FRAME)):
        frames.append(np.frombuffer(stream.read(FRAME, exception_on_overflow=False), dtype=np.int16).astype(np.float32) / 32768.0)
    stream.stop_stream()
    stream.close()
    return frames


def vad_scores(frames):
    import numpy as np
    import onnxruntime as ort
    from faster_whisper.vad import get_assets_path
    opts = ort.SessionOptions()
    opts.log_severity_level = 4
    session = ort.InferenceSession(os.path.join(get_assets_path(), "silero_vad_v6.onnx"), opts, providers=["CPUExecutionProvider"])
    h = np.zeros((1, 1, 128), dtype=np.float32)
    c = np.zeros((1, 1, 128), dtype=np.float32)
    context = np.zeros(64, dtype=np.float32)
    scores = []
    for frame in frames:
        x = np.concatenate([context, frame]).reshape(1, -1).astype(np.float32)
        out, h, c = session.run(None, {"input": x, "h": h, "c": c})
        context = frame[-64:]
        scores.append(float(np.asarray(out).reshape(-1)[0]))
    return scores


def transcribe(audio):
    from faster_whisper import WhisperModel
    for name in ("small.en", "base.en"):
        try:
            model = WhisperModel(name, device="cpu", compute_type="int8", local_files_only=True)
        except Exception:
            continue
        segments, _ = model.transcribe(audio, language="en", beam_size=2, temperature=0.0, condition_on_previous_text=False,
                                       without_timestamps=True, vad_filter=False)
        return name, list(segments)
    return None, []


def main():
    import numpy as np
    say(f"SEVEN MICROPHONE CHECK   {time.strftime('%Y-%m-%d %H:%M:%S')}   {platform.platform()}")
    say("\nSettings Seven reads")
    cfg = settings()
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
    except Exception as exc:
        say(f"\nFAIL: the audio library did not start ({type(exc).__name__}: {exc})")
        return finish()
    names = [pa.get_device_info_by_index(i).get("name") for i in range(pa.get_device_count())
             if pa.get_device_info_by_index(i).get("maxInputChannels", 0) > 0]
    try:
        default = pa.get_default_input_device_info().get("name")
    except Exception:
        default = "none"
    say(f"\nMicrophones: {len(names)} found, Windows default: {default}")
    say(f"\nRecording {SECONDS} seconds. Say, clearly and at your normal distance:  Hey Seven, what time is it?")
    time.sleep(1.0)
    try:
        frames = record(pa, cfg["mic"])
    except Exception as exc:
        say(f"\nFAIL: the microphone could not be opened ({type(exc).__name__}: {exc}). Close other apps that use it and check Windows "
            "Settings, Privacy and security, Microphone.")
        return finish()
    scores = vad_scores(frames)
    audio = np.concatenate(frames)

    say("\nLevel and speech score per second (dBFS: 0 is the loudest; speech usually peaks above -30)")
    per = int(RATE / FRAME)
    for s in range(SECONDS):
        chunk = frames[s * per:(s + 1) * per]
        if chunk:
            say(f"  second {s + 1}: peak {db(max(float(np.max(np.abs(f))) for f in chunk))}  "
                f"average {db(float(np.mean([np.sqrt(np.mean(f ** 2)) for f in chunk])))}  best speech score {max(scores[s * per:(s + 1) * per]):.2f}")
    peak, best = db(float(np.max(np.abs(audio)))), max(scores)
    start = START_P[cfg["sensitivity"]]
    run = best_run = 0
    for p in scores:
        run = run + 1 if p >= start else 0
        best_run = max(best_run, run)

    say("\nWhat that means")
    if peak < -60:
        say("  FAIL  The microphone delivered silence. It is muted, it is the wrong device, or Windows blocks it.")
    elif peak < -40:
        say(f"  WARN  Very quiet (peak {peak} dBFS). Raise the microphone volume in Windows Sound settings, Input.")
    else:
        say(f"  OK    The level is fine (peak {peak} dBFS).")
    if best < 0.1 and peak > -45:
        say(f"  WARN  Sound arrives but the voice detector found no speech in it (best score {best:.2f}). Noise only, heavy noise "
            "suppression, or speech too far from the microphone.")
    elif best_run >= 3:
        say(f"  OK    The voice detector found speech (best score {best:.2f}, needs {start} for {cfg['sensitivity']}).")
    else:
        say(f"  WARN  The voice detector saw only weak speech (best score {best:.2f}, needs {start} for {cfg['sensitivity']}). "
            "Try sensitivity Relaxed in Settings, Voice.")

    say("\nWhat the speech model hears")
    name, segments = transcribe(audio)
    if name is None:
        say("  the speech model could not be loaded (it is not downloaded, or this PC cannot run it)")
    else:
        text = "".join(seg.text for seg in segments).strip()
        say(f"  model {name}: '{text or '(nothing)'}'")
        for seg in segments:
            why = ""
            if seg.no_speech_prob > 0.6 and seg.avg_logprob < -0.5:
                why = "Seven would ignore this: the model thinks there is no speech"
            elif seg.avg_logprob < -1.1:
                why = "Seven would ignore this: the model is guessing"
            elif seg.compression_ratio > 2.6:
                why = "Seven would ignore this: the same phrase repeated"
            say(f"    '{seg.text.strip()}'  confidence {seg.avg_logprob:.2f}  no-speech {seg.no_speech_prob:.2f}  {why}")
        if text:
            low = text.lower()
            if cfg["mode"] == "wake" and not any(w in low for w in ("seven", "7")):
                say("  NOTE  Seven is in Wake word mode and this did not contain 'Seven', so it would be ignored. Say 'Hey Seven' first, "
                    "or choose Always on.")
    if cfg["mode"] == "ptt":
        say("\n  NOTE  Push to talk is ON: Seven hears you only while Shift is held. That alone explains 'not listening'.")
    finish()


def finish():
    text = "\n".join(LINES)
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    path = os.path.join(desktop if os.path.isdir(desktop) else os.getcwd(), "Seven-Mic-Check.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["clip"], input=text.encode("utf-16"), timeout=5, creationflags=0x08000000 if os.name == "nt" else 0)
        print(f"\nSaved to {path} and copied to the clipboard: paste it to the Seven team.")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:                                  # whatever happens, the person gets something to send
        say(f"\nThe check itself failed: {type(exc).__name__}: {exc}")
        finish()
    if sys.stdin and sys.stdin.isatty():
        input("\nPress Enter to close")
