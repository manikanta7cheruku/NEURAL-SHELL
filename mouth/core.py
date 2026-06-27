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

    proc = subprocess.Popen(
        [sys.executable, "-c", run_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=app_path,
        env=env
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
    
    Returns:
        bool: True if something was interrupted, False if nothing playing
    """
    global _current_process

    _interrupted.set()

    with _lock:
        if _current_process and _current_process.poll() is None:
            try:
                _current_process.kill()
                _current_process.wait(timeout=2)
                print("[MOUTH] ⚡ Speech interrupted!")
                _current_process = None
                return True
            except Exception as e:
                print(f"[MOUTH] Interrupt error: {e}")
                _current_process = None
                return False
    return False


def is_speaking():
    """Check if Seven is currently speaking."""
    with _lock:
        if _current_process and _current_process.poll() is None:
            return True
    return False