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
import os
import threading

# State tracking
_current_process = None
_lock = threading.Lock()
_interrupted = threading.Event()


def speak(text):
    """
    Speak text aloud via subprocess.
    Can be interrupted by calling interrupt().
    
    Returns:
        bool: True if completed normally, False if interrupted
    """
    global _current_process

    # Print visual log
    print(f"🔊 SEVEN: {text}")

    # Filter out technical commands
    if "###" in text:
        return True

    _interrupted.clear()

    try:
        with _lock:
            # Spawn speaker.py as separate process
            _current_process = subprocess.Popen(
                [sys.executable, "-m", "mouth.speaker", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

        # Wait for speech to finish OR be interrupted
        _current_process.wait()

        with _lock:
            proc = _current_process
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
        print(f"🔊 SEVEN: {sentence}")
        
        _interrupted.clear()
        
        try:
            with _lock:
                _current_process = subprocess.Popen(
                    [sys.executable, "-m", "mouth.speaker", sentence],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            
            _current_process.wait()
            
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