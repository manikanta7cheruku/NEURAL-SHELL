"""
=============================================================================
PROJECT SEVEN - mouth/core.py (Speech Controller with Interrupt)
Version: 1.3

PURPOSE:
    Manages TTS as a subprocess that can be killed mid-sentence.
    Provides speak() and interrupt() functions.
    
ARCHITECTURE:
    speak() spawns speaker.py as subprocess
    interrupt() kills that subprocess instantly
    is_speaking() returns current state
=============================================================================
"""

import subprocess
import sys
import io
import os
import threading

# Fix Windows console encoding only if not already configured
# Do NOT re-wrap if main.py already called reconfigure() — causes thread deadlock
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
    try:
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        elif not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# State tracking
_current_process = None
_lock = threading.Lock()
_interrupted = threading.Event()

# ── In-app natural voice (mouth/engine.py) ────────────────────────────────
# The Seven app turns this on at startup (main_modules/startup/module_loader.py): the voice stays loaded and speech
# streams sentence by sentence. Helper processes (reminders with Seven closed) leave it off and use the one-shot
# subprocess below, which speaks with the same natural voice but doesn't keep it in memory.
_inprocess = False


def enable_inprocess() -> bool:
    global _inprocess
    from mouth.engine import ENGINE
    if not ENGINE.available():
        print("[MOUTH] Natural voice not installed yet; using the basic voice")
        return False
    _inprocess = True
    ENGINE.warm()
    return True


def _voice_choice():
    """(voice_id, speed factor) from config, read each time so a change in Settings applies to the next sentence."""
    from mouth import voices
    try:
        import json as _json
        p = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "config.json")
        with open(p, encoding="utf-8") as f:
            v = _json.load(f).get("voice", {})
    except Exception:
        v = {}
    vid = v.get("voice_id") if voices.is_natural(v.get("voice_id", "")) else voices.DEFAULT_VOICE
    return vid, voices.speed_factor(v.get("speed", 1.0))


def _engine():
    if not _inprocess:
        return None
    from mouth.engine import ENGINE
    return ENGINE


def _build_run_cmd():
    """Build the Python command and env for speaker subprocess."""
    here     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_path = os.environ.get("SEVEN_APP_PATH", here)
    env      = os.environ.copy()
    env["SEVEN_APP_PATH"] = app_path
    return here, app_path, env


def _spawn_speaker(text):
    """
    Spawn speaker.py subprocess for one piece of text.
    Passes text via environment variable — no string escaping issues.
    Apostrophes, quotes, special chars all safe.
    """
    here, app_path, env = _build_run_cmd()

    # Pass text via env var — avoids ALL quote/escape issues in -c command
    env["SEVEN_SPEAK_TEXT"] = text.replace("\n", " ")

    run_cmd = (
        f"import sys, os; "
        f"sys.path.insert(0, r'{app_path}'); "
        f"sys.path.insert(0, r'{here}'); "
        f"_text = os.environ.pop('SEVEN_SPEAK_TEXT', ''); "
        f"from mouth.speaker import speak_text; "
        f"speak_text(_text)"
    )

    # Use pythonw.exe instead of python.exe to prevent console window flash
    # sys.executable may be pythonw.exe already, but if not we force it
    _python_exe = sys.executable
    if sys.platform == 'win32':
        import os as _os
        _pythonw = _python_exe.replace('python.exe', 'pythonw.exe')
        if _os.path.exists(_pythonw):
            _python_exe = _pythonw

    _cflags = 0x08000000 if sys.platform == 'win32' else 0
    proc = subprocess.Popen(
        [_python_exe, "-c", run_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        cwd=app_path,
        env=env,
        creationflags=_cflags
    )
    return proc, app_path


def _wait_and_drain(proc):
    """
    Wait for subprocess to finish.
    Drains stderr to prevent buffer deadlock.
    """
    try:
        _, err = proc.communicate(timeout=60)
        if err:
            err_text = err.decode("utf-8", errors="replace").strip()
            if err_text:
                print(f"[SPEAKER] {err_text}")
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
    except Exception as e:
        print(f"[MOUTH] Wait error: {e}")


def speak(text):
    """
    Speak text aloud via subprocess.
    Can be interrupted by calling interrupt().
    
    Returns:
        bool: True if completed normally, False if interrupted
    """
    global _current_process

    # Print visual log
    print(f"SEVEN: {text}")

    # Filter out technical commands
    if "###" in text:
        return True

    eng = _engine()
    if eng:
        voice, speed = _voice_choice()
        return eng.say([text], voice=voice, speed=speed)

    _interrupted.clear()

    try:
        with _lock:
            proc, _ = _spawn_speaker(text)
            _current_process = proc

        _wait_and_drain(proc)

        with _lock:
            _current_process = None

        if _interrupted.is_set():
            return False

        return True

    except Exception as e:
        print(f"[MOUTH] Speech error: {e}")
        with _lock:
            _current_process = None
        return True
    

# V1.9

def speak_streamed(sentence_generator):
    """
    V1.9: Speak sentences as they arrive from a generator.
    Each sentence is spoken immediately — no waiting for full response.
    
    Args:
        sentence_generator: yields strings (one sentence at a time)
    
    Returns:
        tuple: (completed: bool, full_text: str)
    """
    global _current_process

    full_text = []
    completed = True

    eng = _engine()
    if eng:
        # Synthesis runs one sentence ahead of playback while the reply is still being written.
        def spoken():
            for sentence in sentence_generator:
                full_text.append(sentence)
                if sentence.strip() and "###" not in sentence:
                    yield sentence
        voice, speed = _voice_choice()
        completed = eng.say(spoken(), voice=voice, speed=speed)
        return completed, " ".join(full_text)

    for sentence in sentence_generator:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Skip technical tags
        if "###" in sentence:
            full_text.append(sentence)
            continue
        
        full_text.append(sentence)
        # print(f"\U0001f50a SEVEN: {sentence}")
        print(f"[VII]: {sentence}")
        
        _interrupted.clear()
        
        try:
            with _lock:
                proc, _ = _spawn_speaker(sentence)
                _current_process = proc

            _wait_and_drain(proc)

            with _lock:
                _current_process = None

            if _interrupted.is_set():
                completed = False
                break

        except Exception as e:
            print(f"[MOUTH] Stream speech error: {e}")
            with _lock:
                _current_process = None
    
    return completed, " ".join(full_text)

#v1.9 Ends

def interrupt():
    """
    Kill speech immediately. Called when user interrupts.

    Kills the entire process tree, not just the wrapper process.
    The wrapper spawns piper.exe as a child. Killing only the wrapper
    (previous behavior) left piper.exe running as an orphan, which is
    why interrupt did not always stop audio playback.

    Returns:
        bool: True if something was interrupted, False if nothing playing
    """
    global _current_process

    _interrupted.set()
    eng = _engine()
    if eng and eng.stop():
        print("[MOUTH] Speech interrupted")
        return True

    with _lock:
        if _current_process and _current_process.poll() is None:
            _pid = _current_process.pid
            try:
                if sys.platform == 'win32':
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(_pid)],
                        capture_output=True,
                        timeout=3
                    )
                else:
                    _current_process.kill()
                _current_process.wait(timeout=2)
                print("[MOUTH] Speech interrupted")
                _current_process = None
                return True
            except Exception as e:
                print(f"[MOUTH] Interrupt error: {e}")
                try:
                    _current_process.kill()
                except Exception:
                    pass
                _current_process = None
                return False
    return False


def is_speaking():
    """Check if Seven is currently speaking."""
    eng = _engine()
    if eng and eng.is_speaking():
        return True
    with _lock:
        if _current_process and _current_process.poll() is None:
            return True
    return False