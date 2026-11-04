"""
ears/doctor.py
When Seven is not hearing you, say why, in the app, without anyone running a command.

assess() turns what the ears already measure (backend/diagnostics.py, ears.core.hearing_stats) and the app's live state into a
short list of problems, each with a title, what was seen, and what to do about it. The home screen shows the most important
one, Settings, System, Hearing shows all of them next to a live microphone meter, and every change is written to
logs\\hearing_debug.log with the numbers behind it, so a report from a friend's PC says what went wrong and when.

It decides nothing about speech itself; it only reads. Pure functions, so the tests give it any situation.
"""
import json
import os
import time

LOOP_STUCK_S = 15           # the voice loop beats about twice a second
SPEAKING_STUCK_S = 120      # no answer of Seven's lasts this long
SILENT_DB = -80             # below this a microphone is delivering nothing (a quiet room's own noise is -60 to -75)
MIN_EVENTS = 5              # fewer than this many ignored sounds in a row says nothing yet

ERROR, WARN, INFO = "error", "warn", "info"
ORDER = {ERROR: 0, WARN: 1, INFO: 2}


_SILENCE_FIX = ("unmute it (many laptops have a mute key), choose the right microphone in Windows Settings, System, Sound, Input, "
                "and turn off its Audio enhancements or noise suppression (some laptop microphone arrays send silence with them on). "
                "Or choose another microphone in Seven, Settings, Voice.")


def _issue(id_, level, title, detail, fix):
    return {"id": id_, "level": level, "title": title, "detail": detail, "fix": fix}


def assess(stats, state, now=None):
    """The problems with hearing right now, most important first. `stats` is ears.core.hearing_stats() (None when the ears are not
    loaded), `state` the app's live state dictionary."""
    now = now or time.time()
    out = []
    state = state or {}
    if state.get("safe_mode"):
        reason = (state["safe_mode"] or {}).get("reason") or "it failed to start three times in a row"
        out.append(_issue("safe_mode", ERROR, "Seven is in safe mode", reason, "Press Try again. If it comes back, send the Diagnostics report."))
    elif state.get("voice_problem"):
        out.append(_issue("startup", ERROR, "Seven could not start its hearing", state["voice_problem"],
                          "Restart Seven. If it stays, send the Diagnostics report."))
    if not state.get("ready"):
        return sorted(out, key=lambda i: ORDER[i["level"]])        # still loading: nothing else can be judged yet
    sm = state.get("speech_model") or {}
    if sm.get("state") == "error":
        out.append(_issue("speech_model", ERROR, "Speech recognition could not start", sm.get("detail") or "the speech model failed to load",
                          "Check the internet connection and restart Seven."))
    elif sm.get("state") in ("downloading", "loading"):
        out.append(_issue("speech_model", INFO, "Speech recognition is still getting ready", f"{sm.get('state')} {sm.get('progress', 0)}%",
                          "Seven cannot hear you until this finishes. Typing works."))
    beat = state.get("voice_loop_beat")
    if beat and now - float(beat) > LOOP_STUCK_S:
        out.append(_issue("loop_stuck", ERROR, "Seven stopped acting on what it hears", f"its main loop has not run for {now - float(beat):.0f} s",
                          "Restart Seven, then send the Diagnostics report: it shows the line the loop is stuck at."))
    if stats is None:
        if not out:
            out.append(_issue("ears_missing", ERROR, "Seven's hearing is not loaded", "the ears were never started",
                              "Restart Seven. If it stays, send the Diagnostics report."))
        return sorted(out, key=lambda i: ORDER[i["level"]])

    mic = stats["mic_stats"]
    if not mic["alive"] or (mic["since_last_frame"] is not None and mic["since_last_frame"] > 3):
        out.append(_issue("mic_stream", ERROR, "Seven's microphone stream is not running", mic.get("last_error") or "no audio is arriving",
                          "Check that the microphone is plugged in and that no other app has taken it, then restart Seven."))
    elif mic.get("problem"):
        out.append(_issue("mic_silent", WARN, "The microphone has sent only silence for a minute", mic["problem"], _SILENCE_FIX))
    elif mic["peak_db"] is not None and mic["peak_db"] < SILENT_DB and mic["frames"] > 300:
        out.append(_issue("mic_quiet_now", INFO, "The microphone is sending silence right now",
                          f"nothing above {mic['peak_db']} dBFS in the last 10 s. Some microphones do this until someone speaks",
                          "Speak, and watch the meter in Settings, System, Hearing. If it does not move when you speak: " + _SILENCE_FIX))
    if mic.get("notice"):
        out.append(_issue("mic_switched", INFO, "Seven changed microphone", mic["notice"], "Choose another in Settings, Voice if this is the wrong one."))
    if stats["mode"] == "ptt":
        listener = stats.get("push_to_talk_listener")
        out.append(_issue("ptt", ERROR if not listener else WARN, "Push to talk is on",
                          "Seven hears you only while Shift is held" + ("" if listener else ", and its keyboard listener is not running"),
                          "Choose Always on or Wake word at the top of the home screen to talk without a key."))
    if stats["speaking_for_s"] > SPEAKING_STUCK_S:
        out.append(_issue("speaking_stuck", ERROR, "Seven thinks it has been talking for minutes", f"{stats['speaking_for_s']:.0f} s",
                          "While it believes it is talking it ignores everything it hears. Restart Seven; headphones also help."))

    outcomes = stats["outcomes"]
    total = sum(outcomes.values())
    if total >= MIN_EVENTS and not outcomes.get("heard"):
        top = max(outcomes, key=outcomes.get)
        share = outcomes[top] / total
        said = f"the last {total} sounds it picked up were all ignored ({top}: {outcomes[top]})"
        if "wake word" in top and share >= 0.5:
            out.append(_issue("wake_word", WARN, "Seven hears you but waits for 'Hey Seven'", said,
                              "Say 'Hey Seven' first, or choose Always on at the top of the home screen."))
        elif "own voice" in top and share >= 0.5:
            out.append(_issue("own_voice", WARN, "Seven keeps mistaking its own voice for yours", said,
                              "Use headphones, lower the speaker volume, or move the microphone away from the speakers."))
        elif top in ("too short",) and share >= 0.5:
            out.append(_issue("noise", WARN, "Seven only picks up short noises", said,
                              "Background noise or clicks. Speak closer to the microphone, or try Strict sensitivity in Settings, Voice."))
        elif share >= 0.5:
            out.append(_issue("no_words", WARN, "Seven hears sound but cannot find words in it", said,
                              "Speak closer and clearly, try Relaxed sensitivity in Settings, Voice, or choose another microphone."))
    return sorted(out, key=lambda i: ORDER[i["level"]])


def live(stats, state, now=None):
    """The numbers for the live meter in Settings, System, Hearing."""
    now = now or time.time()
    state = state or {}
    mic = (stats or {}).get("mic_stats") or {}
    beat = state.get("voice_loop_beat")
    return {"mode": (stats or {}).get("mode"), "peak_db": mic.get("peak_db"), "avg_db": mic.get("avg_db"),
            "speech_score": mic.get("best_speech_score"), "start_threshold": mic.get("start_threshold"),
            "frames": mic.get("frames", 0), "device": mic.get("device"), "outcomes": (stats or {}).get("outcomes", {}),
            "loop_age": round(now - float(beat), 1) if beat else None, "listening": bool(state.get("listening"))}


# ── the record that goes with a report ───────────────────────────────────────────────────────────────────────────
_last = {"ids": None, "at": 0.0}


def log_path():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "logs", "hearing_debug.log")


def record(issues, stats, now=None):
    """Write a line when the set of problems changes: when, which, and the numbers behind them. Kept small: it is what a friend
    sends when Seven 'did not work yesterday'."""
    now = now or time.time()
    ids = sorted(i["id"] for i in issues if i["level"] != INFO)
    if ids == (_last["ids"] or []) or now - _last["at"] < 30:
        return False
    _last.update(ids=ids, at=now)
    try:
        os.makedirs(os.path.dirname(log_path()), exist_ok=True)
        if os.path.exists(log_path()) and os.path.getsize(log_path()) > 200_000:
            os.replace(log_path(), log_path() + ".1")
        line = {"at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), "problems": ids or ["none"],
                "titles": [i["title"] for i in issues if i["level"] != INFO],
                "mic": {k: (stats or {}).get("mic_stats", {}).get(k) for k in ("peak_db", "avg_db", "best_speech_score", "device", "frames")},
                "mode": (stats or {}).get("mode"), "outcomes": (stats or {}).get("outcomes")}
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
        return True
    except OSError:
        return False


def recent_log(n=6):
    try:
        with open(log_path(), encoding="utf-8") as f:
            return [ln.rstrip() for ln in f.readlines()[-n:]]
    except OSError:
        return []
