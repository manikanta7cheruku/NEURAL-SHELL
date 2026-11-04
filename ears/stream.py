"""
ears/stream.py
Seven's microphone: one always-open stream that hands over whole utterances.

The old ears decided "is someone talking?" by loudness (an RMS threshold with calibration and crest checks).
Loudness can't tell a voice from a fan, a keyboard or a TV, so noise got through and Whisper invented words for
it, while quiet speech fell under the threshold. Here a neural speech detector (Silero, the ONNX model that ships
with faster-whisper) scores every 32 ms of sound, and a small state machine turns those scores into utterances:

    mic (16 kHz) ─► 32 ms frames ─► Silero: speech probability ─► start / continue / end ─► Utterance queue
                          └─► live level and state for the app (the orb, "Hearing you")

    start     speech probability above the start threshold for ~100 ms (sensitivity decides the threshold),
              keeping ~300 ms from before it so the first syllable isn't cut
    continue  above a lower threshold (hysteresis), so pauses between words don't split a sentence
    end       ~0.6 s below it, or 15 s at most
    reject    under 0.35 s of actual speech (a cough, a click)

Utterances that begin while Seven is speaking are marked, so the main loop ignores Seven's own voice and the
interrupt listener can still catch "stop".

Push to talk replaces start and end with the key: holding it starts an utterance (with the same ~300 ms pre-roll),
letting go ends it at once. The speech detector still has to find real speech in it, so a tap of the key is nothing.
"""
import collections
import os
import queue
import threading
import time
from dataclasses import dataclass, field

import numpy as np

RATE = 16000
FRAME = 512                         # 32 ms: the frame size Silero expects at 16 kHz
DEAD_PEAK = 1e-4                    # about -80 dBFS: below this the device delivers nothing at all
# Some microphone arrays (AMD's, among others) apply a noise gate and send exact silence until someone speaks, so silence alone
# does not prove a device is dead. Seven looks for another microphone only when this long has passed in silence AND the
# current one has never been heard carrying speech since Seven started (or not for SPEECH_EVIDENCE_S).
DEAD_AFTER_S = 60.0
RETRY_DEAD_S = 120.0                # and it looks again after this long, so a plugged-in headset is found
SPEECH_EVIDENCE_S = 1800.0
SKIP_DEVICES = ("stereo mix", "loopback", "what u hear", "sound mapper", "primary sound")

# sensitivity -> (start probability, keep-going probability, silence that ends an utterance in seconds)
SENSITIVITY = {
    "relaxed":  (0.40, 0.25, 0.75),   # hears soft voices; a little more likely to react to noise
    "balanced": (0.55, 0.35, 0.60),
    "strict":   (0.70, 0.45, 0.55),   # noisy rooms: only clear, close speech
}


@dataclass
class Utterance:
    audio: np.ndarray                # float32, 16 kHz mono
    started: float
    ended: float
    during_speech: bool = False      # began while Seven was talking
    peak: float = 0.0                # highest speech probability
    speech_seconds: float = 0.0
    meta: dict = field(default_factory=dict)

    @property
    def seconds(self) -> float:
        return len(self.audio) / RATE


class _Silero:
    """Silero VAD run one frame at a time, keeping its recurrent state between frames."""

    def __init__(self):
        import onnxruntime as ort
        from faster_whisper.vad import get_assets_path
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 4
        self.session = ort.InferenceSession(os.path.join(get_assets_path(), "silero_vad_v6.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self):
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros(64, dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        x = np.concatenate([self.context, frame]).reshape(1, -1).astype(np.float32)
        out, self.h, self.c = self.session.run(None, {"input": x, "h": self.h, "c": self.c})
        self.context = frame[-64:]
        return float(np.asarray(out).reshape(-1)[0])


class MicStream:
    def __init__(self):
        self.utterances: "queue.Queue[Utterance]" = queue.Queue(maxsize=8)
        self.sensitivity = "balanced"
        self.device_name = ""
        self._is_speaking = lambda: False
        self._publish = lambda key, value: None
        self._listeners = []         # functions given every frame (float32), e.g. the snap detector
        self._thread = None
        self._running = threading.Event()
        self._paused = threading.Event()
        self._ptt = None             # push to talk: a function, True while the key is held; None in other modes
        self.level = 0.0
        self.state = "idle"          # idle | hearing | processing
        self.last_error = ""
        # What the microphone has actually been giving us, for Diagnostics: a PC that "ignores everything" is either
        # hearing silence, hearing noise, or hearing speech it then rejects, and these numbers say which.
        self._recent = collections.deque(maxlen=310)     # (time, rms, peak amplitude, speech probability), ~10 s
        self.frames = 0
        self.last_frame_at = 0.0
        self.counts = {"utterances": 0, "too_short": 0}
        self._force_index = None     # a microphone found by looking, when the chosen or default one delivers nothing
        self._silent_since = None
        self._last_search = 0.0
        self.last_speech_at = 0.0    # when this microphone was last heard carrying speech: proof that it works
        self.notice = ""             # "Switched to X because Y was silent"
        self.problem = ""            # "No microphone is delivering any sound"

    # ── wiring ───────────────────────────────────────────────────────────
    def set_speaking_fn(self, fn):
        self._is_speaking = fn

    def set_publisher(self, fn):
        """fn(key, value): live state for the app (mic_level 0..1, voice_state)."""
        self._publish = fn

    def add_listener(self, fn):
        self._listeners.append(fn)

    def configure(self, sensitivity: str = None, device_name: str = None):
        if sensitivity in SENSITIVITY:
            self.sensitivity = sensitivity
        if device_name is not None and device_name != self.device_name:
            self.device_name = device_name
            self._force_index = None                     # the person chose a microphone: that choice wins
            self._reopen = True

    def set_push_to_talk(self, held_fn):
        """held_fn() -> True while the push-to-talk key is held. None turns push to talk off."""
        self._ptt = held_fn

    def pause(self, paused: bool):
        """Push-to-talk off, or the mic muted: frames are read but nothing is turned into utterances."""
        (self._paused.set if paused else self._paused.clear)()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MicStream")
        self._thread.start()

    def stop(self):
        self._running.clear()

    def next(self, timeout: float = 0.5):
        try:
            return self.utterances.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self):
        while not self.utterances.empty():
            try:
                self.utterances.get_nowait()
            except queue.Empty:
                break

    # ── capture ──────────────────────────────────────────────────────────
    def _device_index(self, pa):
        """The chosen mic, on Windows' standard audio system (it converts to 16 kHz; WASAPI would refuse). Settings
        shows WASAPI's full names, the standard list cuts them to 31 characters, so match either way round."""
        if not self.device_name:
            return None
        want = self.device_name.lower()
        default_api = pa.get_default_host_api_info().get("index")
        found = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            name = info.get("name", "").lower().strip()
            if info.get("maxInputChannels", 0) > 0 and name and (want in name or name in want):
                found.append((info.get("hostApi") != default_api, i))
        return min(found)[1] if found else None

    def _open(self, pa):
        import pyaudio
        from seven_utils import audio
        index = self._force_index if self._force_index is not None else self._device_index(pa)
        return audio.open_stream(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=FRAME,
                                 input_device_index=index)

    def _run(self):
        from seven_utils import audio
        vad = _Silero()
        pa = audio.pa()                                  # shared: PortAudio must not be initialised twice at once
        stream = None
        backoff = 1.0
        self._reopen = False
        while self._running.is_set():
            try:
                if stream is None or self._reopen:
                    audio.close_stream(stream)
                    stream = self._open(pa)
                    self._reopen = False
                    vad.reset()
                    backoff = 1.0
                    self.last_error = ""
                    print(f"[EARS] Microphone open{f' ({self.device_name})' if self.device_name else ''}")
                self._listen(stream, vad)
            except Exception as e:                       # unplugged headset, device busy: wait and reopen
                self.last_error = str(e)
                print(f"[EARS] Microphone error: {e}. Retrying in {backoff:.0f}s")
                audio.close_stream(stream)
                stream = None
                time.sleep(backoff)
                backoff = min(backoff * 2, 15.0)
        audio.close_stream(stream)

    # ── a microphone that delivers nothing ───────────────────────────────────────────────────────────
    def _candidates(self, pa):
        """Input devices Seven can open at 16 kHz (the standard Windows audio system and DirectSound convert for us), without
        the loopback and mapper entries that are not microphones."""
        wanted = {pa.get_default_host_api_info().get("index")}
        for i in range(pa.get_host_api_count()):
            if "directsound" in pa.get_host_api_info_by_index(i).get("name", "").lower():
                wanted.add(i)
        out = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            name = info.get("name", "")
            if info.get("maxInputChannels", 0) > 0 and info.get("hostApi") in wanted and not any(k in name.lower() for k in SKIP_DEVICES):
                out.append((i, name))
        return out

    def _peak_of(self, index, seconds=0.7):
        """The loudest sample from one device over a moment, or None when it cannot be opened."""
        import pyaudio
        from seven_utils import audio
        stream = None
        try:
            stream = audio.open_stream(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=FRAME,
                                       input_device_index=index)
            peak = 0.0
            for _ in range(max(1, int(seconds * RATE / FRAME))):
                data = np.frombuffer(stream.read(FRAME, exception_on_overflow=False), dtype=np.int16).astype(np.float32) / 32768.0
                peak = max(peak, float(np.max(np.abs(data))))
            return peak
        except Exception:
            return None
        finally:
            audio.close_stream(stream)

    def _find_working_device(self, pa, current):
        """Try the other microphones for a moment each and use the first that has a sound floor. Returns True when it switched."""
        best = None
        for index, name in self._candidates(pa):
            if index == current:
                continue
            peak = self._peak_of(index)
            if peak is not None and peak > DEAD_PEAK * 1.3 and (best is None or peak > best[0]):
                best = (peak, index, name)
        if best is None:
            return False
        self._force_index = best[1]
        self.notice = f"Seven's microphone was silent, so it switched to {best[2]}."
        self.problem = ""
        self._publish("mic_notice", self.notice)
        self._publish("mic_problem", "")
        print(f"[EARS] {self.notice}")
        return True

    def _watch_silence(self, pa, peak, now):
        """Called for every frame. A device that has delivered only digital silence for a while is dead (muted at the
        hardware, a driver that gives nothing): look for one that works instead of listening to nothing for ever."""
        if peak > DEAD_PEAK:
            if self.problem:
                self.problem = ""
                self._publish("mic_problem", "")
            self._silent_since = None
            return False
        if self._silent_since is None:
            self._silent_since = now
            return False
        if now - self._silent_since < DEAD_AFTER_S or now - self._last_search < RETRY_DEAD_S:
            return False
        if self.last_speech_at and now - self.last_speech_at < SPEECH_EVIDENCE_S:
            return False                                 # it carried speech not long ago: it works, the room is just quiet
        self._last_search = now
        try:
            current = self._force_index if self._force_index is not None else self._device_index(pa)
            if self._find_working_device(pa, current):
                self._silent_since = None
                return True
        except Exception as exc:
            print(f"[EARS] Looking for a working microphone failed: {exc}")
        self.problem = ("The microphone has sent only silence for a minute and no other microphone works. If Seven does not hear you "
                        "when you speak: check that it is not muted (many laptops have a mute key), pick the right device in Windows "
                        "Sound settings, Input, and turn off its audio enhancements or noise suppression.")
        self._publish("mic_problem", self.problem)
        return False

    def _listen(self, stream, vad):
        from seven_utils import audio
        pre_roll = collections.deque(maxlen=10)          # ~320 ms kept from before speech starts
        frames, probs = [], []
        above = 0                                        # consecutive frames over the start threshold
        quiet = 0.0
        speaking_at_start = False
        started = 0.0
        last_pub = 0.0
        while self._running.is_set() and not self._reopen:
            raw = stream.read(FRAME, exception_on_overflow=False)
            frame = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            for fn in self._listeners:
                try:
                    fn(frame)
                except Exception:
                    pass
            p = vad(frame)
            rms = float(np.sqrt(np.mean(frame ** 2)) + 1e-9)
            self.frames += 1
            self.last_frame_at = time.time()
            self._recent.append((self.last_frame_at, rms, float(np.max(np.abs(frame))), p))
            if p >= 0.5:
                self.last_speech_at = self.last_frame_at
            if self._watch_silence(audio.pa(), float(np.max(np.abs(frame))), self.last_frame_at):
                self._reopen = True
                break
            self.level = max(0.0, min(1.0, (20 * np.log10(rms) + 60) / 50))   # -60 dBFS..-10 dBFS -> 0..1

            now = time.time()
            if now - last_pub > 0.08:
                last_pub = now
                self._publish("mic_level", round(self.level, 3))

            if self._paused.is_set():
                frames, probs, above = [], [], 0
                pre_roll.clear()
                self._set_state("idle")
                continue

            start_p, keep_p, end_s = SENSITIVITY[self.sensitivity]
            ptt = self._ptt
            if ptt is not None:                          # push to talk: the key decides where speech starts and ends
                try:
                    held = bool(ptt())
                except Exception:
                    held = False
                if held:
                    if not frames:
                        frames = list(pre_roll)
                        probs = [0.0] * len(frames)
                        started = now - len(frames) * FRAME / RATE
                        speaking_at_start = bool(self._is_speaking())
                        self._set_state("hearing")
                    frames.append(frame)
                    probs.append(p)
                    if len(frames) * FRAME / RATE <= 15.0:
                        continue
                if frames:
                    self._finish(frames, probs, keep_p, 0.0, started, now, speaking_at_start, ptt=True)
                    frames, probs = [], []
                    pre_roll.clear()
                    continue
                pre_roll.append(frame)
                continue

            if not frames:
                pre_roll.append(frame)
                above = above + 1 if p >= start_p else 0
                if above >= 3:                           # ~100 ms of confident speech
                    frames = list(pre_roll)
                    probs = [p] * len(frames)
                    started = now - len(frames) * FRAME / RATE
                    speaking_at_start = bool(self._is_speaking())
                    quiet = 0.0
                    self._set_state("hearing")
                continue

            frames.append(frame)
            probs.append(p)
            quiet = quiet + FRAME / RATE if p < keep_p else 0.0
            too_long = len(frames) * FRAME / RATE > 15.0
            if quiet >= end_s or too_long:
                self._finish(frames, probs, keep_p, quiet, started, now, speaking_at_start)
                frames, probs, above = [], [], 0
                pre_roll.clear()

    def _finish(self, frames, probs, keep_p, quiet, started, now, speaking_at_start, ptt=False):
        """Turn the collected frames into an Utterance, or drop them if there's too little actual speech."""
        speech_s = sum(1 for x in probs if x >= keep_p) * FRAME / RATE
        audio = np.concatenate(frames)
        trim = int(max(0.0, quiet - 0.25) * RATE)          # keep a little silence at the end
        if trim:
            audio = audio[:-trim]
        if speech_s < 0.35:
            self.counts["too_short"] += 1
            self._publish("voice_ignored", {"reason": "too short", "at": now})
            self._set_state("idle")
            return
        utt = Utterance(audio=audio, started=started, ended=now, during_speech=speaking_at_start,
                        peak=max(probs) if probs else 0.0, speech_seconds=speech_s, meta={"ptt": ptt})
        self.counts["utterances"] += 1
        try:
            self.utterances.put_nowait(utt)
        except queue.Full:                               # nobody is listening (Seven is busy): keep the newest
            try:
                self.utterances.get_nowait()
            except queue.Empty:
                pass
            self.utterances.put_nowait(utt)
        self._set_state("processing")

    def stats(self) -> dict:
        """The microphone's last ten seconds in numbers: level in dBFS (0 is the loudest possible), the best speech score the
        detector gave, and whether frames are arriving at all."""
        recent = [r for r in list(self._recent) if time.time() - r[0] <= 10]
        db = lambda v: round(20 * float(np.log10(max(v, 1e-6))), 1)
        return {"frames": self.frames, "since_last_frame": round(time.time() - self.last_frame_at, 1) if self.last_frame_at else None,
                "alive": bool(self._thread and self._thread.is_alive()), "last_error": self.last_error,
                "avg_db": db(float(np.mean([r[1] for r in recent]))) if recent else None,
                "peak_db": db(max(r[2] for r in recent)) if recent else None,
                "best_speech_score": round(max(r[3] for r in recent), 2) if recent else None,
                "start_threshold": SENSITIVITY[self.sensitivity][0], "sensitivity": self.sensitivity,
                "push_to_talk": self._ptt is not None, "paused": self._paused.is_set(), "device": self.device_name or "(Windows default)",
                "notice": self.notice, "problem": self.problem, "switched": self._force_index is not None,
                "speech_heard_ago": round(time.time() - self.last_speech_at, 0) if self.last_speech_at else None,
                **self.counts}

    def _set_state(self, state):
        if state != self.state:
            self.state = state
            self._publish("voice_state", state)


STREAM = MicStream()
